"""The film the projector plays: host.as compiled (Dockerfile, stage "film")
with the client's OWN compiled AS2 location classes in front of its frame
script, copied byte for byte out of main.swf: each class's DefineSprite,
its "__Packages.<class>" export and its DoInitAction, in main.swf's order.
Nothing of main.swf is changed and nothing of it is kept: the film is made
afresh in the container on every run from the main.swf it is given.

    python3 mkhost.py MAIN.swf HOST_SCRIPT.swf OUT.swf
"""
import hashlib
import struct
import sys
import zlib

CLASSES = [
    "mx.utils.Delegate", "lol.events.LEventDispatcher", "lol.core.SSettings",
    "lol.services.SSEmulator", "lol.display.DisplaySprite", "lol.display.ExternalSource",
    "lol.display.SpriteSource", "lol.display.SourceLibrary", "lol.display.LibSource",
    "lol.display.AnimationSprite", "lol.utils.MCFabric", "lol.core.location.LocInfo",
    "lol.core.location.LocSourceLoader", "lol.core.location.LDParser",
    "lol.core.location.LocDeclaration",
]


def load(path):
    """(body after the 8-byte header, offset of the first tag)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:3] == b"CWS":
        body = zlib.decompress(raw[8:])
    elif raw[:3] == b"FWS":
        body = raw[8:]
    else:
        raise SystemExit("%s: not a CWS/FWS film" % path)
    nbits = body[0] >> 3
    return raw, body, (5 + 4 * nbits + 7) // 8 + 4


def tags(body, p):
    out = []
    while p < len(body):
        cl = struct.unpack("<H", body[p:p + 2])[0]
        code, ln, hl = cl >> 6, cl & 63, 2
        if ln == 63:
            ln, hl = struct.unpack("<I", body[p + 2:p + 6])[0], 6
        out.append((code, body[p + hl:p + hl + ln]))
        p += hl + ln
        if code == 0:
            break
    return out


def raw_tag(code, body):
    if len(body) >= 63:
        return struct.pack("<HI", code << 6 | 63, len(body)) + body
    return struct.pack("<H", code << 6 | len(body)) + body


def exports(body):
    n, r, out = struct.unpack("<H", body[:2])[0], 2, []
    for _ in range(n):
        cid = struct.unpack("<H", body[r:r + 2])[0]
        e = body.index(b"\0", r + 2)
        out.append((cid, body[r + 2:e].decode("utf-8", "replace")))
        r = e + 1
    return out


def main(main_swf, script_swf, out):
    raw, body, p = load(main_swf)
    print("main.swf sha256 %s" % hashlib.sha256(raw).hexdigest())
    tl = tags(body, p)
    exp = {}
    for c, b in tl:
        if c == 56:
            for cid, name in exports(b):
                exp[name] = cid
    want = {}
    for cl in CLASSES:
        cid = exp.get("__Packages." + cl)
        if cid is None:
            raise SystemExit("main.swf exports no class %s" % cl)
        want[cid] = cl
    sprites = [raw_tag(c, b) for c, b in tl if c == 39 and struct.unpack("<H", b[:2])[0] in want]
    inits = [(struct.unpack("<H", b[:2])[0], raw_tag(c, b)) for c, b in tl
             if c == 59 and struct.unpack("<H", b[:2])[0] in want]
    if len(sprites) != len(want) or len(inits) != len(want):
        raise SystemExit("main.swf: %d classes, %d sprites, %d class inits" % (len(want), len(sprites), len(inits)))
    export_body = struct.pack("<H", len(want))
    for cid, cl in want.items():
        export_body += struct.pack("<H", cid) + ("__Packages." + cl).encode() + b"\0"
    classes = b"".join(sprites) + raw_tag(56, export_body) + b"".join(t for _, t in inits)
    _, sbody, sp = load(script_swf)
    film = b""
    for c, b in tags(sbody, sp):
        if c == 12:                      # the frame script goes after the classes
            film += classes
        film += raw_tag(c, b)
    payload = sbody[:sp] + film
    with open(out, "wb") as fh:
        fh.write(b"CWS" + bytes([9]) + struct.pack("<I", 8 + len(payload)) + zlib.compress(payload, 9))
    print("%s: %d client classes: %s" % (out, len(want), ", ".join(want[cid] for cid, _ in inits)))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
