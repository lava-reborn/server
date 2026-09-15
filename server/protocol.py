"""LAVA Online wire codec.

Reverse-engineered from res/main.swf (AS2):
  lol.server.CSMessage.toString  -> encoding
  lol.server.SCDataParser.parse  -> decoding

Frame: "<name>;<key>=<value>;..." terminated by NUL, CP1251 on the wire.
Value type is signalled by the first character of the value.
"""

# Flash decodes XMLSocket traffic as UTF-8 unless System.useCodepage is on,
# and this client only sets that inside one rarely taken branch of its login
# screen. The convertToCP1251 helper it carries belongs to MD5rus and is
# only about what gets hashed, not what travels. Sending cp1251 here left
# the client parsing a Cyrillic name into rubbish: the parser advances its
# cursor by the character length of each string it reads, so a value that
# decodes to a different length than it was written slides every field
# after it out of place.
ENCODING = "utf-8"
TERM = b"\x00"


class Str(str):
    """Force @string@ encoding for a value that looks numeric."""


class Hex(int):
    """Force H-prefixed hex encoding."""


class BigUInt(str):
    """Force x-prefixed big-unsigned encoding (kept as text, per client)."""


# --- escaping (lol.server.XMLString) -------------------------------------
# Verbatim from the client's escape table. Note the oddity: a double quote
# maps to %5C, the percent-encoding of a BACKSLASH, not %22. Reproducing the
# quirk is mandatory, since the client decodes %5C back into a double quote.
# "@" must be escaped or it would terminate an @string@ value early.
ESCAPES = [
    ("%", "%25"),   # first on encode, last on decode
    ("<", "%3C"),
    (">", "%3E"),
    ("'", "%27"),
    ('"', "%5C"),
    ("&", "%26"),
    ("@", "%40"),
]
_ESC_MAP = dict(ESCAPES)
_UNESC_MAP = {v: k for k, v in ESCAPES}


def escape(s):
    """Per-character escape, matching XMLString.escape()."""
    return "".join(_ESC_MAP.get(ch, ch) for ch in s)


def unescape(s):
    """Single left-to-right pass, so an escaped percent cannot be re-decoded."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "%" and i + 3 <= n and s[i:i + 3] in _UNESC_MAP:
            out.append(_UNESC_MAP[s[i:i + 3]])
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


# --- encoding ------------------------------------------------------------
def _enc_value(v):
    if isinstance(v, Hex):
        return "H%X" % int(v)
    if isinstance(v, BigUInt):
        return "x%s" % v
    if isinstance(v, Str):
        return "@%s@" % escape(v)
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return "%g" % v if isinstance(v, float) else str(v)
    if isinstance(v, (list, tuple)):
        if not v:
            return "|"
        first = v[0]
        if isinstance(first, BigUInt):
            return "|" + "|".join("x%s" % x for x in v) + "|"
        if isinstance(first, str):
            return "|" + "|".join("@%s@" % escape(x) for x in v) + "|"
        return "|" + "|".join(str(x) for x in v) + "|"
    return "@%s@" % escape(str(v))


def encode(*_cmd, **params):
    """Build a frame body (no NUL terminator).

    The command name is positional so that a protocol parameter literally
    called "name" (e.g. ah_search) cannot collide with it.
    """
    name = _cmd[0]
    out = name + ";"
    for k, v in params.items():
        out += "%s=%s;" % (k, _enc_value(v))
    return out


def frame(*_cmd, **params):
    """Build a complete NUL-terminated wire frame."""
    return encode(_cmd[0], **params).encode(ENCODING, "replace") + TERM


# --- decoding ------------------------------------------------------------
def _dec_list(src, i):
    """src[i] == '|'. Returns (value, index just past the closing '|;')."""
    nxt = src[i + 1] if i + 1 < len(src) else ";"
    if nxt == ";":
        return [], i + 1
    if nxt == "@":
        end = src.index("@|;", i)
        body = src[i + 2:end]
        return [unescape(x) for x in body.split("@|@")], end + 2
    end = src.index("|;", i)
    body = src[i + 1:end]
    parts = body.split("|")
    if nxt == "x":
        return [p[1:] for p in parts], end + 1
    return [float(p) if "." in p else int(p) for p in parts], end + 1


def decode(src):
    """Parse a frame body into (name, params dict)."""
    if isinstance(src, bytes):
        src = src.decode(ENCODING, "replace")
    semi = src.find(";")
    if semi < 0:
        return src, {}
    name = src[:semi]
    params = {}
    i = semi + 1
    n = len(src)
    while i < n:
        eq = src.find("=", i)
        if eq < 0:
            break
        key = src[i:eq]
        j = eq + 1
        if j >= n:
            break
        c = src[j]
        if c == "@":
            end = src.index("@;", j + 1)
            params[key] = unescape(src[j + 1:end])
            i = end + 2
        elif c in "Hh":
            end = src.index(";", j)
            params[key] = int(src[j + 1:end], 16)
            i = end + 1
        elif c == "x":
            end = src.index(";", j)
            params[key] = BigUInt(src[j + 1:end])
            i = end + 1
        elif c == "|":
            params[key], end = _dec_list(src, j)
            i = end + 1
        else:
            end = src.index(";", j)
            raw = src[j:end]
            params[key] = float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
            i = end + 1
    return name, params


class FrameReader:
    """Accumulates bytes, yields complete NUL-delimited frames."""

    def __init__(self):
        self._buf = b""

    def feed(self, data):
        self._buf += data
        out = []
        while TERM in self._buf:
            raw, self._buf = self._buf.split(TERM, 1)
            if raw:
                out.append(raw)
        return out
