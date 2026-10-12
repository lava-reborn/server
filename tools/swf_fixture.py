"""Small SWFs for the tests of tools/swfx.py and tools/location_art.py:
just enough of the format (rectangles, matrices, shapes with one fill,
sprites, PlaceObject2, ExportAssets, DefineBitsLossless2, DefineBitsJPEG3)
to build a library or a sprite file with known bounds. Standard library
only. Not a writer for the game: the owner's objects have their own.
"""
import struct
import zlib


class Bits:
    def __init__(self):
        self.bits = []

    def u(self, n, v):
        self.bits += [(v >> (n - 1 - i)) & 1 for i in range(n)]

    def s(self, n, v):
        self.u(n, v & ((1 << n) - 1))

    def bytes(self):
        b = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int("".join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def nbits(*vals):
    return max([1] + [abs(int(v)).bit_length() + 1 for v in vals])


def rect(x0, x1, y0, y1):
    b = Bits()
    n = nbits(x0, x1, y0, y1)
    b.u(5, n)
    for v in (x0, x1, y0, y1):
        b.s(n, v)
    return b.bytes()


def matrix(sx=1.0, sy=1.0, tx=0, ty=0):
    b = Bits()
    if (sx, sy) != (1.0, 1.0):
        a, d = int(round(sx * 65536)), int(round(sy * 65536))
        n = nbits(a, d)
        b.u(1, 1)
        b.u(5, n)
        b.s(n, a)
        b.s(n, d)
    else:
        b.u(1, 0)
    b.u(1, 0)
    n = nbits(tx, ty) if (tx or ty) else 0
    b.u(5, n)
    if n:
        b.s(n, tx)
        b.s(n, ty)
    return b.bytes()


def tag(code, body):
    if len(body) >= 63:
        return struct.pack("<HI", code << 6 | 63, len(body)) + body
    return struct.pack("<H", code << 6 | len(body)) + body


def shape(cid, bounds, bitmap=None, fill=(1.0, 1.0, 0, 0), code=2, edges=None):
    body = struct.pack("<H", cid) + rect(*bounds)
    if code == 83:
        body += rect(*(edges or bounds)) + b"\0"
    if bitmap is None:
        body += b"\1" + b"\0" + b"\xff\0\0" + (b"\xff" if code >= 32 else b"")   # one solid fill
    else:
        body += b"\1" + b"\x41" + struct.pack("<H", bitmap) + matrix(*fill)
    return tag(code, body + b"\0" + b"\x10" + b"\0")


def place(depth, cid, mat=b"\0"):
    return tag(26, bytes([0x06]) + struct.pack("<HH", depth, cid) + mat)


def sprite(cid, frames):
    body = struct.pack("<HH", cid, len(frames))
    for f in frames:
        body += b"".join(f) + tag(1, b"")
    return tag(39, body + tag(0, b""))


def export(pairs):
    body = struct.pack("<H", len(pairs))
    for cid, name in pairs:
        body += struct.pack("<H", cid) + name.encode() + b"\0"
    return tag(56, body)


def lossless2(cid, w, h, argb):
    return tag(36, struct.pack("<HBHH", cid, 5, w, h) + zlib.compress(argb))


def jpeg3(cid, jpg, alpha):
    return tag(35, struct.pack("<HI", cid, len(jpg)) + jpg + zlib.compress(alpha))


def swf(tags, version=9):
    body = (rect(0, 11000, 0, 8000) + struct.pack("<HH", 12 << 8, 1) + b"".join(tags)
            + tag(1, b"") + tag(0, b""))
    return b"FWS" + bytes([version]) + struct.pack("<I", 8 + len(body)) + body
