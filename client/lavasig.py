#!/usr/bin/env python3
"""RSA signatures for the client's release documents, in pure Python.

    python3 client/lavasig.py genkey OUT.pem [--bits 3072]   new key; prints its .keys line
    python3 client/lavasig.py pubkey KEY.pem                 the .keys line of a private key
    python3 client/lavasig.py sign KEY.pem BODY [-o OUT]     BODY + "sig ..." line
    python3 client/lavasig.py verify KEYS DOC                exit 0 if DOC is signed by a key in KEYS

The format is client/FORMAT.md, "Signed document": the body, then one last
line "sig <keyid> <base64>" holding RSASSA-PKCS1-v1_5 / SHA-256 over every
byte of the body.

WHY NOT OPENSSL. Every place that signs or checks has Python and not all of
them have an openssl binary: CI runs in python:3.12-slim, the gate's builder
runs in the game's own image, the owner signs the launcher on Windows. One
module of the standard library's integers is the same everywhere, and the
launcher checks the same arithmetic in C# (launcher/Release.cs). Signing is
done offline and rarely, so the side channels a library would guard against
(timing on a shared machine) are not in play.

Keys are PEM: PKCS#1 ("RSA PRIVATE KEY", what genkey writes) or PKCS#8
("PRIVATE KEY", what `openssl genpkey` writes), unencrypted.
"""
import argparse
import base64
import hashlib
import os
import re
import secrets
import sys

E = 65537

# DigestInfo for SHA-256 (RFC 8017, 9.2, note 1).
SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


# --- integers and keys ---------------------------------------------------------

def i2b(n, length=None):
    """Unsigned big-endian bytes, no leading zeros unless length asks for them."""
    if length is None:
        length = max(1, (n.bit_length() + 7) // 8)
    return n.to_bytes(length, "big")


def b2i(b):
    return int.from_bytes(b, "big")


def keyid(n):
    """First 16 hex digits of sha256 over the modulus (FORMAT.md, "Signed document")."""
    return hashlib.sha256(i2b(n)).hexdigest()[:16]


SMALL_PRIMES = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def probably_prime(n, rounds=64):
    if n < 2:
        return False
    for p in SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = 2 + secrets.randbelow(n - 3)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def random_prime(bits):
    while True:
        # The top two bits set so that p*q has exactly 2*bits bits; odd.
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1
        if (c - 1) % E == 0:
            continue                      # e must be invertible mod p-1
        if probably_prime(c):
            return c


class PrivateKey:
    def __init__(self, n, e, d, p, q):
        self.n, self.e, self.d, self.p, self.q = n, e, d, p, q
        self.dp = d % (p - 1)
        self.dq = d % (q - 1)
        self.qinv = pow(q, -1, p)

    @property
    def id(self):
        return keyid(self.n)

    def keys_line(self):
        return "%s %d %x" % (self.id, self.e, self.n)


def generate(bits=3072):
    half = bits // 2
    while True:
        p, q = random_prime(half), random_prime(half)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        lam = (p - 1) * (q - 1)
        d = pow(E, -1, lam)
        return PrivateKey(n, E, d, max(p, q), min(p, q))


# --- DER, as little of it as a key needs ----------------------------------------

def _der_len(n):
    if n < 0x80:
        return bytes([n])
    b = i2b(n)
    return bytes([0x80 | len(b)]) + b


def _der(tag, body):
    return bytes([tag]) + _der_len(len(body)) + body


def _der_int(n):
    b = i2b(n)
    if b[0] & 0x80:
        b = b"\x00" + b
    return _der(0x02, b)


def _der_read(buf, at):
    """(tag, body, next offset) of the element at `at`."""
    tag = buf[at]
    ln = buf[at + 1]
    at += 2
    if ln & 0x80:
        k = ln & 0x7F
        if not 1 <= k <= 4:
            raise ValueError("DER length of %d bytes" % k)
        ln = b2i(buf[at:at + k])
        at += k
    if at + ln > len(buf):
        raise ValueError("DER element runs past the end")
    return tag, buf[at:at + ln], at + ln


def _der_seq(body):
    out, at = [], 0
    while at < len(body):
        tag, val, at = _der_read(body, at)
        out.append((tag, val))
    return out


RSA_OID = bytes.fromhex("2a864886f70d010101")


def pem_private(key):
    der = _der(0x30, b"".join(_der_int(v) for v in (
        0, key.n, key.e, key.d, key.p, key.q, key.dp, key.dq, key.qinv)))
    b64 = base64.b64encode(der).decode("ascii")
    lines = [b64[i:i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN RSA PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END RSA PRIVATE KEY-----\n"


def load_private(text):
    m = re.search(r"-----BEGIN (RSA PRIVATE KEY|PRIVATE KEY)-----(.*?)-----END \1-----",
                  text, re.S)
    if not m:
        if "ENCRYPTED" in text:
            raise ValueError("encrypted keys are not supported; keep the key file safe instead")
        raise ValueError("no RSA private key in PEM")
    der = base64.b64decode("".join(m.group(2).split()))
    tag, body, _ = _der_read(der, 0)
    if tag != 0x30:
        raise ValueError("not a DER sequence")
    items = _der_seq(body)
    if m.group(1) == "PRIVATE KEY":
        # PKCS#8: version, AlgorithmIdentifier, OCTET STRING with PKCS#1 inside.
        if len(items) < 3 or items[2][0] != 0x04 or RSA_OID not in items[1][1]:
            raise ValueError("PKCS#8 key that is not RSA")
        tag, body, _ = _der_read(items[2][1], 0)
        items = _der_seq(body)
    ints = [b2i(v) for t, v in items if t == 0x02]
    if len(ints) < 6 or ints[0] != 0:
        raise ValueError("not a two-prime RSA private key")
    _, n, e, d, p, q = ints[:6]
    if p * q != n:
        raise ValueError("p*q != n")
    return PrivateKey(n, e, d, p, q)


def read_private(path):
    with open(path, "r", encoding="ascii") as fh:
        return load_private(fh.read())


# --- the .keys file ------------------------------------------------------------

def parse_keys(text):
    """{keyid: (e, n)} from a .keys file; a line whose id does not match its
    modulus is an error, not a key."""
    keys = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]{16}", parts[0]):
            raise ValueError("bad .keys line: %r" % line[:60])
        e, n = int(parts[1]), int(parts[2], 16)
        if keyid(n) != parts[0]:
            raise ValueError("key id %s does not match its modulus" % parts[0])
        if n.bit_length() < 2048 or e < 3 or e % 2 == 0:
            raise ValueError("key %s is too weak" % parts[0])
        keys[parts[0]] = (e, n)
    return keys


def read_keys(path):
    with open(path, "r", encoding="utf-8") as fh:
        return parse_keys(fh.read())


# --- PKCS#1 v1.5 ---------------------------------------------------------------

def encode(data, k):
    """EMSA-PKCS1-v1_5 of sha256(data) for a k-byte modulus."""
    t = SHA256_PREFIX + hashlib.sha256(data).digest()
    if k < len(t) + 11:
        raise ValueError("modulus too short")
    return b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t


def sign(key, data):
    k = (key.n.bit_length() + 7) // 8
    m = b2i(encode(data, k))
    # CRT, then checked: a fault in the arithmetic must not leave this
    # function as a signature (it would also leak a factor of n).
    s1 = pow(m, key.dp, key.p)
    s2 = pow(m, key.dq, key.q)
    h = (key.qinv * (s1 - s2)) % key.p
    s = s2 + h * key.q
    if pow(s, key.e, key.n) != m:
        raise RuntimeError("signature failed its own check")
    return i2b(s, k)


def verify(e, n, data, sig):
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return False
    s = b2i(sig)
    if s >= n:
        return False
    return i2b(pow(s, e, n), k) == encode(data, k)


# --- signed documents ----------------------------------------------------------

SIG_LINE = re.compile(rb"sig ([0-9a-f]{16}) ([A-Za-z0-9+/]+={0,2})\n\Z")


def sign_doc(key, body):
    """body (bytes, ending in LF) + its sig line."""
    if not body.endswith(b"\n"):
        raise ValueError("a signed body ends with a newline")
    s = base64.b64encode(sign(key, body)).decode("ascii")
    return body + ("sig %s %s\n" % (key.id, s)).encode("ascii")


def split_doc(doc):
    """(body, keyid, signature bytes); ValueError if the last line is not a sig line."""
    cut = doc.rfind(b"\n", 0, len(doc) - 1) + 1
    m = SIG_LINE.match(doc, cut)
    if not m or not doc.endswith(b"\n"):
        raise ValueError("no signature line at the end")
    return doc[:cut], m.group(1).decode("ascii"), base64.b64decode(m.group(2))


def verify_doc(keys, doc):
    """The body if doc is signed by one of keys ({keyid: (e, n)}), else ValueError."""
    body, kid, sig = split_doc(doc)
    if kid not in keys:
        raise ValueError("signed by unknown key %s" % kid)
    e, n = keys[kid]
    if not verify(e, n, body, sig):
        raise ValueError("signature does not match (key %s)" % kid)
    return body


# --- command line --------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("genkey")
    g.add_argument("out")
    g.add_argument("--bits", type=int, default=3072)
    p = sub.add_parser("pubkey")
    p.add_argument("key")
    s = sub.add_parser("sign")
    s.add_argument("key")
    s.add_argument("body")
    s.add_argument("-o", "--out")
    v = sub.add_parser("verify")
    v.add_argument("keys")
    v.add_argument("doc")
    a = ap.parse_args(argv)

    if a.cmd == "genkey":
        if os.path.exists(a.out):
            ap.error("%s exists; a key is never overwritten" % a.out)
        key = generate(a.bits)
        # Created 0600 before a byte is written, not chmod-ed afterwards.
        fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as fh:
            fh.write(pem_private(key))
        print(key.keys_line())
    elif a.cmd == "pubkey":
        print(read_private(a.key).keys_line())
    elif a.cmd == "sign":
        key = read_private(a.key)
        with open(a.body, "rb") as fh:
            doc = sign_doc(key, fh.read())
        if a.out:
            with open(a.out, "wb") as fh:
                fh.write(doc)
        else:
            sys.stdout.buffer.write(doc)
    elif a.cmd == "verify":
        with open(a.doc, "rb") as fh:
            doc = fh.read()
        try:
            verify_doc(read_keys(a.keys), doc)
        except ValueError as e:
            print("verify: %s" % e, file=sys.stderr)
            return 1
        print("verify: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
