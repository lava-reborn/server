#!/usr/bin/env python3
"""Ext sprite files for the owner's own location objects, written in the
forms the original client's own sprite files have (tools/custom_objects.py,
client/objects/README.md). Standard library only: client/build.py runs this
inside the game's image, network off, with no Pillow.

How the client uses such a file. A location names it with
<sprite id="ID" type="ext">: LocSourceLoader fetches
locations/libs/sprite/ID.swf on its own, outside the location's library, and
LocBuilder hands it to AnimationSprite.display, a MovieClipLoader.loadClip.
The file stays a live clip: its root timeline plays at main.swf's 25 frames
a second, whatever the file's own header says, and loops. The picture's
top-left pixel is the clip's (0,0), which lands at the anchor cell's centre
plus (dx, dy). A <bgdecoration type="ext"> or <background type="ext"> draws
the same kind of file once, frame 1 only (SpriteSource.getBitmap).

One picture is the form of the original locations/libs/sprite/CL_BW.png.swf:

    FileAttributes SetBackgroundColor DefineBitsLossless2 DefineShape
    PlaceObject2 ShowFrame End

with the shape a w x h rectangle at (0,0) filled with the bitmap (clipped,
not smoothed: fill 0x43, scale 20 twips a pixel). Several pictures of one
size are the form of the original a_campfire.png.swf: one root frame per
picture, each held round(25 / fps) frames, the next picture swapped in at
depth 1 with the matrix kept. A PNG goes in losslessly (DefineBitsLossless2,
premultiplied ARGB); an opaque picture can instead be the owner's baseline
JPEG, carried byte for byte in DefineBitsJPEG2 (the form of the original
background Oasis.jpg.swf).

Both forms were run in the real Flash Player 32 projector the launcher ships
(tools/flash_headless/README.md): drawn where the client's own classes put
them, alpha exact, colour within 1 of the source, the animation advancing a
picture per hold and looping.

Refused, with the reason: anything but PNG or baseline JPEG, an interlaced
PNG, a progressive or CMYK JPEG, a side over MAX_SIDE pixels, an animation
whose pictures differ in size.

    python3 tools/swfgen.py OUT.swf A.png [B.png ...] [--fps N]
"""
import struct
import sys
import zlib

# The longest side a picture may have. Flash Player 32 itself allows 8191
# pixels a side and 16.7 million pixels for the bitmaps the client draws
# frames into; 2880 is the old Flash 8 limit, below both, and far above any
# object of the original game.
MAX_SIDE = 2880

# main.swf runs at 25 frames a second, and a loaded clip plays at its host's
# rate, never at its own (checked in Flash Player 32 with a header saying
# 5): an animation's speed is how many game frames each picture is held.
HOST_FPS = 25

PNG_SIG = b"\x89PNG\r\n\x1a\n"


class Refused(ValueError):
    """A picture or a set of them this writer will not wrap, and why."""


# --- pictures ------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def png_header(data):
    """(width, height, bit depth, colour type, interlace) of a PNG's IHDR."""
    if data[:8] != PNG_SIG:
        raise Refused("not a PNG")
    if len(data) < 33 or data[12:16] != b"IHDR":
        raise Refused("PNG: no IHDR first")
    w, h, depth, ctype, _comp, _filt, interlace = struct.unpack(">IIBBBBB", data[16:29])
    return w, h, depth, ctype, interlace


def _check_side(w, h, what):
    if not (1 <= w <= MAX_SIDE and 1 <= h <= MAX_SIDE):
        raise Refused("%s %dx%d: each side must be 1..%d pixels" % (what, w, h, MAX_SIDE))


def png_decode(data):
    """(width, height, RGBA bytes with straight alpha) of a PNG file's bytes.
    Every colour type and depth of the PNG standard; interlaced files are
    refused (re-save them without interlacing)."""
    w, h, depth, ctype, interlace = png_header(data)
    _check_side(w, h, "PNG")
    if interlace:
        raise Refused("PNG: interlaced; save it without interlacing")
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if chans is None or depth not in ((1, 2, 4, 8, 16) if ctype in (0, 3) else (8, 16)) \
            or (ctype == 3 and depth == 16):
        raise Refused("PNG: colour type %d with bit depth %d" % (ctype, depth))
    pos = 8
    idat = []
    plte = trns = None
    while True:
        if pos + 12 > len(data):
            raise Refused("PNG: cut short before IEND")
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        if pos + 12 + ln > len(data):
            raise Refused("PNG: chunk %r cut short" % typ)
        body = data[pos + 8:pos + 8 + ln]
        crc = struct.unpack(">I", data[pos + 8 + ln:pos + 12 + ln])[0]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != crc:
            raise Refused("PNG: bad CRC in chunk %r" % typ)
        if typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
        pos += 12 + ln
    bpp = max(1, chans * depth // 8)
    stride = (w * chans * depth + 7) // 8
    need = h * (stride + 1)
    # Never inflate more than the picture can hold: a few kilobytes of
    # zeros can claim gigabytes.
    try:
        raw = zlib.decompressobj().decompress(b"".join(idat), need)
    except zlib.error as e:
        raise Refused("PNG: image data does not inflate (%s)" % e)
    if len(raw) < need:
        raise Refused("PNG: image data cut short")
    rows = []
    prev = bytes(stride)
    p = 0
    for _y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                if i >= bpp:
                    line[i] = (line[i] + _paeth(line[i - bpp], prev[i], prev[i - bpp])) & 255
                else:
                    line[i] = (line[i] + prev[i]) & 255
        elif f != 0:
            raise Refused("PNG: unknown row filter %d" % f)
        rows.append(bytes(line))
        prev = line
    if ctype == 6 and depth == 8:
        return w, h, b"".join(rows)
    if ctype == 3:
        if not plte or len(plte) % 3:
            raise Refused("PNG: palette picture without a palette")
        pal = [bytes((plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2],
                      trns[i] if trns and i < len(trns) else 255)) for i in range(len(plte) // 3)]
    key = None
    if trns and ctype == 0:
        key = struct.unpack(">H", trns[:2])[0]
    elif trns and ctype == 2:
        key = struct.unpack(">HHH", trns[:6])
    out = bytearray(w * h * 4)
    o = 0
    for line in rows:
        if depth < 8:
            per = 8 // depth
            mask = (1 << depth) - 1
            for x in range(w):
                v = (line[x // per] >> ((per - 1 - x % per) * depth)) & mask
                if ctype == 3:
                    if v >= len(pal):
                        raise Refused("PNG: palette index %d past the palette" % v)
                    out[o:o + 4] = pal[v]
                else:
                    g = v * 255 // mask
                    out[o:o + 4] = bytes((g, g, g, 0 if v == key else 255))
                o += 4
            continue
        if depth == 16:
            samples = struct.unpack(">%dH" % (w * chans), line)
            s8 = bytes(v >> 8 for v in samples)
        else:
            samples = s8 = line
        for x in range(w):
            i = x * chans
            if ctype == 6:
                px = s8[i:i + 4]
            elif ctype == 2:
                a = 0 if key is not None and tuple(samples[i:i + 3]) == key else 255
                px = bytes((s8[i], s8[i + 1], s8[i + 2], a))
            elif ctype == 4:
                px = bytes((s8[i], s8[i], s8[i], s8[i + 1]))
            elif ctype == 0:
                a = 0 if key is not None and samples[i] == key else 255
                px = bytes((s8[i], s8[i], s8[i], a))
            else:
                if s8[i] >= len(pal):
                    raise Refused("PNG: palette index %d past the palette" % s8[i])
                px = pal[s8[i]]
            out[o:o + 4] = px
            o += 4
    return w, h, bytes(out)


def jpeg_size(data):
    """(width, height) of a baseline JPEG with one or three components.
    Progressive, lossless, arithmetic-coded and CMYK files are refused: the
    bytes go into the file unchanged, and only a baseline JPEG is what the
    originals carry."""
    if data[:2] != b"\xff\xd8":
        raise Refused("not a JPEG")
    p = 2
    while p + 4 <= len(data):
        if data[p] != 0xFF:
            raise Refused("JPEG: no marker at byte %d" % p)
        m = data[p + 1]
        if m == 0xFF:                       # fill byte before a marker
            p += 1
            continue
        if m in (0x01, 0xD8) or 0xD0 <= m <= 0xD7:
            p += 2
            continue
        if m in (0xD9, 0xDA):
            break
        ln = struct.unpack(">H", data[p + 2:p + 4])[0]
        if m == 0xC0:
            if p + 10 > len(data):
                break
            h, w, n = struct.unpack(">HHB", data[p + 5:p + 10])
            if n not in (1, 3):
                raise Refused("JPEG: %d colour components (CMYK?); save it as RGB" % n)
            _check_side(w, h, "JPEG")
            return w, h
        if 0xC1 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            raise Refused("JPEG: not baseline (SOF%d: progressive, lossless or "
                          "arithmetic); save it as baseline" % (m - 0xC0))
        p += 2 + ln
    raise Refused("JPEG: no frame header")


class Picture:
    """One picture to wrap: kind "png" (rgba holds straight RGBA) or "jpeg"
    (jpeg holds the file's bytes)."""

    def __init__(self, kind, w, h, rgba=None, jpeg=None):
        self.kind, self.w, self.h, self.rgba, self.jpeg = kind, w, h, rgba, jpeg


def picture(data):
    """A Picture from a PNG's or a baseline JPEG's bytes, by their signature."""
    if data[:8] == PNG_SIG:
        w, h, rgba = png_decode(data)
        return Picture("png", w, h, rgba=rgba)
    if data[:2] == b"\xff\xd8":
        w, h = jpeg_size(data)
        return Picture("jpeg", w, h, jpeg=bytes(data))
    raise Refused("neither a PNG nor a JPEG")


def picture_size(data):
    """(width, height) from the header alone, nothing decoded."""
    if data[:8] == PNG_SIG:
        w, h = png_header(data)[:2]
        _check_side(w, h, "PNG")
        return w, h
    if data[:2] == b"\xff\xd8":
        return jpeg_size(data)
    raise Refused("neither a PNG nor a JPEG")


# --- SWF -------------------------------------------------------------------------

class BitWriter:
    def __init__(self):
        self.bits = []

    def u(self, n, v):
        for i in range(n - 1, -1, -1):
            self.bits.append((v >> i) & 1)

    def s(self, n, v):
        self.u(n, v & ((1 << n) - 1))

    def bytes(self):
        b = self.bits + [0] * (-len(self.bits) % 8)
        return bytes(int("".join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def sbits(*vals):
    """Bits a signed field needs to hold every value."""
    n = 1
    for v in vals:
        m = v if v >= 0 else ~v
        n = max(n, m.bit_length() + 1)
    return n


def rect(xmin, xmax, ymin, ymax):
    n = sbits(xmin, xmax, ymin, ymax)
    w = BitWriter()
    w.u(5, n)
    for v in (xmin, xmax, ymin, ymax):
        w.s(n, v)
    return w.bytes()


def tag(code, body, long_=False):
    if long_ or len(body) >= 0x3F:
        return struct.pack("<HI", (code << 6) | 0x3F, len(body)) + body
    return struct.pack("<H", (code << 6) | len(body)) + body


_PREMUL = None


def _premul_table():
    """round(c * a / 255) for every alpha and colour, a * 256 + c."""
    global _PREMUL
    if _PREMUL is None:
        _PREMUL = bytes((c * a + 127) // 255 for a in range(256) for c in range(256))
    return _PREMUL


def lossless2(cid, w, h, rgba):
    """DefineBitsLossless2, format 5: zlib of premultiplied ARGB rows."""
    px = bytearray(len(rgba))
    px[0::4] = rgba[3::4]
    px[1::4] = rgba[0::4]
    px[2::4] = rgba[1::4]
    px[3::4] = rgba[2::4]
    t = _premul_table()
    for i in range(0, len(px), 4):
        a = px[i]
        if a != 255:
            base = a << 8
            px[i + 1] = t[base + px[i + 1]]
            px[i + 2] = t[base + px[i + 2]]
            px[i + 3] = t[base + px[i + 3]]
    body = struct.pack("<HBHH", cid, 5, w, h) + zlib.compress(bytes(px), 9)
    return tag(36, body, True)


def jpeg2(cid, jpeg):
    """DefineBitsJPEG2: the JPEG's bytes as they are."""
    return tag(21, struct.pack("<H", cid) + jpeg, True)


# Bitmap fill matrix: scale 20 (one bitmap pixel = 20 twips), the bytes the
# Flash IDE wrote into every original (d9400005000000).
FILL_MATRIX = bytes.fromhex("d9400005000000")

# Clipped bitmap fill, not smoothed: what the original sprite and background
# files use (CL_BW.png.swf, a_campfire.png.swf, Oasis.jpg.swf).
FILL_CLIPPED = 0x43


def shape(cid, bitmap_id, w, h):
    """DefineShape: a w x h rectangle filled with the bitmap, top-left at
    (0,0), drawn the way CL_BW.png.swf and Oasis.jpg.swf draw it, the form
    of the most placed original sprite files: fill1 from (0,0), then right,
    down, left and up back to the start. (Other originals start with a
    moveTo the opposite corner; Flash draws both the same.)"""
    tw, th = w * 20, h * 20
    body = struct.pack("<H", cid) + rect(0, tw, 0, th)
    body += bytes((1, FILL_CLIPPED)) + struct.pack("<H", bitmap_id) + FILL_MATRIX
    body += b"\x00"            # no line styles
    bw = BitWriter()
    bw.u(4, 1)                 # NumFillBits
    bw.u(4, 0)                 # NumLineBits
    # StyleChangeRecord: StateFillStyle1 only, the pen at (0,0)
    bw.u(1, 0)
    bw.u(5, 0b00100)
    bw.u(1, 1)                 # fill1 = style 1
    for dx, dy in ((tw, 0), (0, th), (-tw, 0), (0, -th)):
        v = dx or dy
        k = max(2, sbits(v))
        bw.u(1, 1)             # edge
        bw.u(1, 1)             # straight
        bw.u(4, k - 2)
        bw.u(1, 0)             # not a general line
        bw.u(1, 1 if dy else 0)  # vertical?
        bw.s(k, v)
    bw.u(1, 0)
    bw.u(5, 0)                 # EndShapeRecord
    return tag(2, body + bw.bytes(), True)


def place2(depth, cid, move=False):
    """PlaceObject2 as the originals write it: a new character with an
    identity matrix (flags 0x06: '06 01 00 cc cc 00'), or, for the next
    picture of an animation, the character at that depth swapped and its
    matrix kept (flags 0x03: '03 01 00 cc cc', a_campfire.png.swf)."""
    if move:
        return tag(26, struct.pack("<BHH", 0x03, depth, cid))
    return tag(26, struct.pack("<BHH", 0x06, depth, cid) + b"\x00")


SHOW = tag(1, b"")
END = tag(0, b"")
FILE_ATTRS = tag(69, b"\x00\x00\x00\x00")
WHITE = tag(9, b"\xff\xff\xff")
STAGE = (550, 400)


def swf(body, fps, frames):
    """A compressed SWF 9 file around the tags, on the originals' 550x400
    stage (the stage of a loaded clip is not drawn)."""
    hdr = rect(0, STAGE[0] * 20, 0, STAGE[1] * 20) + struct.pack("<HH", (fps << 8) & 0xFFFF, frames)
    payload = hdr + body
    return b"CWS" + bytes((9,)) + struct.pack("<I", 8 + len(payload)) + zlib.compress(payload, 9)


def hold_for(fps):
    """Game frames each picture of an animation at `fps` pictures a second
    is held: 25 -> 1, 12 -> 2, 5 -> 5, 1 -> 25."""
    if not (type(fps) is int and 1 <= fps <= HOST_FPS):
        raise Refused("fps %r: a whole number 1..%d (the game runs at %d frames a second)"
                      % (fps, HOST_FPS, HOST_FPS))
    return max(1, int(round(HOST_FPS / float(fps))))


def sprite_swf(pictures, fps=None, keys=None):
    """The ext sprite file of one picture, or of an animation of several of
    one size shown `fps` a second. `keys`, one per picture, name pictures
    that are the same (an animation that comes back to a picture): each is
    stored once."""
    if not pictures:
        raise Refused("no picture")
    sizes = sorted({(p.w, p.h) for p in pictures})
    if len(sizes) != 1:
        raise Refused("every picture of an animation must be the same size: %s"
                      % ", ".join("%dx%d" % s for s in sizes))
    for p in pictures:
        _check_side(p.w, p.h, "picture")
    animated = len(pictures) > 1
    hold = hold_for(fps) if animated else 1
    keys = list(keys) if keys is not None else list(range(len(pictures)))
    body = FILE_ATTRS + WHITE
    cid = 1
    shapes = {}
    for i, (p, key) in enumerate(zip(pictures, keys)):
        if key not in shapes:
            if p.kind == "jpeg":
                body += jpeg2(cid, p.jpeg)
            else:
                body += lossless2(cid, p.w, p.h, p.rgba)
            body += shape(cid + 1, cid, p.w, p.h)
            shapes[key] = cid + 1
            cid += 2
        body += place2(1, shapes[key], move=i > 0) + SHOW * hold
    return swf(body + END, fps=HOST_FPS if animated else 12, frames=len(pictures) * hold)


def main(argv):
    fps = None
    files = []
    it = iter(argv)
    for a in it:
        if a == "--fps":
            fps = int(next(it))
        else:
            files.append(a)
    if len(files) < 2:
        print(__doc__)
        return 2
    out, srcs = files[0], files[1:]
    pics = []
    for path in srcs:
        with open(path, "rb") as fh:
            pics.append(picture(fh.read()))
    try:
        data = sprite_swf(pics, fps=fps if fps is not None else (HOST_FPS if len(pics) > 1 else None))
    except Refused as e:
        print("refused: %s" % e, file=sys.stderr)
        return 1
    with open(out, "wb") as fh:
        fh.write(data)
    print("%s: %d bytes, %d picture%s" % (out, len(data), len(pics), "" if len(pics) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
