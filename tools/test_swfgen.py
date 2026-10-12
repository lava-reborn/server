"""Own location objects: the sprite files, the manifest and placing them.

tools/swfgen.py writes an object's pictures into an ext sprite file the way
the original client's own files are written (CL_BW.png.swf for a picture,
a_campfire.png.swf for an animation, Oasis.jpg.swf for a JPEG), and
tools/custom_objects.py turns client/objects/ into those files and places
an object in a location. Every file is read back here by a parser written
apart from swfgen's code: tags, the bitmap's pixels, the shape's edges, and
which picture the timeline shows on every frame. Pictures are made by a PNG
encoder of this file, every colour type, depth and row filter.

What the original files look like is pinned below from their bytes, so CI,
which has no art, checks it too. With the client's art in LAVA_RES
(locations/libs/sprite/CL_BW.png.swf and a_campfire.png.swf,
locations/libs/background/Oasis.jpg.swf) the originals' own pictures are
re-wrapped and compared tag by tag; without it those checks are skipped.
That the client draws these files right was seen in the real Flash Player
32 (tools/flash_headless/README.md); that is not run here.
"""
import json
import os
import random
import shutil
import struct
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import custom_objects as co  # noqa: E402
import swfgen  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "own location objects: sprite files, manifest, placement"

RES = os.environ.get("LAVA_RES", "")
W = tempfile.mkdtemp(prefix="test-swfgen-")


# --- an independent SWF reader ------------------------------------------------------------

class Bits:
    def __init__(self, data, pos=0):
        self.data, self.bit = data, pos * 8

    def u(self, n):
        v = 0
        for _ in range(n):
            byte = self.data[self.bit >> 3]
            v = (v << 1) | ((byte >> (7 - (self.bit & 7))) & 1)
            self.bit += 1
        return v

    def s(self, n):
        v = self.u(n)
        return v - (1 << n) if n and v >> (n - 1) else v

    def align(self):
        self.bit = (self.bit + 7) & ~7
        return self.bit >> 3


def read_rect(data, pos):
    b = Bits(data, pos)
    n = b.u(5)
    r = tuple(b.s(n) for _ in range(4))
    return r, b.align()


def read_swf(raw):
    """(header, [(code, body)]) of a CWS or FWS file."""
    sig, version, length = raw[:3], raw[3], struct.unpack("<I", raw[4:8])[0]
    body = zlib.decompress(raw[8:]) if sig == b"CWS" else raw[8:]
    assert sig in (b"CWS", b"FWS") and 8 + len(body) == length, (sig, length, len(body))
    stage, p = read_rect(body, 0)
    fps = body[p + 1] + body[p] / 256.0
    frames = struct.unpack("<H", body[p + 2:p + 4])[0]
    p += 4
    tags = []
    while p < len(body):
        cl = struct.unpack("<H", body[p:p + 2])[0]
        code, ln, p = cl >> 6, cl & 63, p + 2
        if ln == 63:
            ln, p = struct.unpack("<I", body[p:p + 4])[0], p + 4
        tags.append((code, body[p:p + ln]))
        p += ln
        if code == 0:
            break
    assert p == len(body), "bytes after End"
    return dict(sig=sig, version=version, stage=stage, fps=fps, frames=frames), tags


def read_matrix(b):
    m = dict(sx=1.0, sy=1.0, r0=0.0, r1=0.0, tx=0, ty=0)
    if b.u(1):
        n = b.u(5)
        m["sx"], m["sy"] = b.s(n) / 65536.0, b.s(n) / 65536.0
    if b.u(1):
        n = b.u(5)
        m["r0"], m["r1"] = b.s(n) / 65536.0, b.s(n) / 65536.0
    n = b.u(5)
    m["tx"], m["ty"] = b.s(n), b.s(n)
    return m


def read_shape(body):
    """DefineShape (1): id, bounds, fill styles, and the outline as points."""
    sid = struct.unpack("<H", body[:2])[0]
    bounds, p = read_rect(body, 2)
    fills = []
    for _ in range(body[p]):
        t = body[p + 1]
        bid = struct.unpack("<H", body[p + 2:p + 4])[0]
        b = Bits(body, p + 4)
        m = read_matrix(b)
        fills.append((t, bid, m, body[p + 4:b.align()]))
        p = b.align() - 1
    p += 1
    nlines = body[p]
    p += 1
    b = Bits(body, p)
    nf, nl = b.u(4), b.u(4)
    x = y = 0
    path, fill1 = [("start", 0, 0)], None
    while True:
        if b.u(1) == 0:
            flags = b.u(5)
            if flags == 0:
                break
            if flags & 1:
                n = b.u(5)
                x, y = b.s(n), b.s(n)
                path.append(("move", x, y))
            if flags & 2:
                b.u(nf)
            if flags & 4:
                fill1 = b.u(nf)
            if flags & 8:
                b.u(nl)
            assert not flags & 16, "new styles"
        elif b.u(1) == 1:
            n = b.u(4) + 2
            if b.u(1):
                dx, dy = b.s(n), b.s(n)
            elif b.u(1):
                dx, dy = 0, b.s(n)
            else:
                dx, dy = b.s(n), 0
            x, y = x + dx, y + dy
            path.append(("line", x, y))
        else:
            raise AssertionError("curved edge")
    return dict(id=sid, bounds=bounds, fills=fills, lines=nlines, fill1=fill1, path=path)


def outline(sh):
    """The corners an outline passes and whether it ends where it began."""
    begin = [(x, y) for kind, x, y in sh["path"] if kind != "line"][-1]
    pts = [(x, y) for _, x, y in sh["path"]]
    return sorted(set(pts)), pts[-1] == begin


def read_lossless2(body):
    cid, fmt, w, h = struct.unpack("<HBHH", body[:7])
    return cid, fmt, w, h, zlib.decompress(body[7:])


def timeline(tags):
    """The character at depth 1 on every root frame, PlaceObject2 by
    PlaceObject2, and every character id defined."""
    shown, frames, defined = None, [], {}
    for code, body in tags:
        if code in (2, 21, 36):
            defined[struct.unpack("<H", body[:2])[0]] = (code, body)
        elif code == 26:
            flags, depth = body[0], struct.unpack("<H", body[1:3])[0]
            assert depth == 1 and flags & 2, (flags, depth)
            assert bool(flags & 1) == (shown is not None), "a move only over a placed character"
            shown = struct.unpack("<H", body[3:5])[0]
        elif code == 1:
            frames.append(shown)
    return frames, defined


def bitmap_of(defined, shape_id):
    """The bitmap a shape is filled with: ('png', w, h, premultiplied ARGB)
    or ('jpeg', bytes)."""
    sh = read_shape(defined[shape_id][1])
    code, body = defined[sh["fills"][0][1]]
    if code == 36:
        _, _, w, h, px = read_lossless2(body)
        return ("png", w, h, px)
    return ("jpeg", body[2:])


def premul(rgba):
    """Premultiplied ARGB of straight RGBA, rounding half up, by the book."""
    out = bytearray()
    for i in range(0, len(rgba), 4):
        r, g, b, a = rgba[i:i + 4]
        out += bytes((a,) + tuple((c * a * 2 + 255) // 510 for c in (r, g, b)))
    return bytes(out)


def unpremul(argb):
    out = bytearray()
    for i in range(0, len(argb), 4):
        a, r, g, b = argb[i:i + 4]
        out += bytes(((c * 255 + a // 2) // a if a else 0 for c in (r, g, b))) + bytes((a,))
    return bytes(out)


# --- an independent PNG writer --------------------------------------------------------------

def chunk(typ, body):
    return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)


def make_png(w, h, ctype, depth, rows, plte=None, trns=None, interlace=0, crc_ok=True):
    """rows: per row, the samples of every pixel in channel order. Row y is
    filtered with type y % 5, so every filter is decoded."""
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, chans * depth // 8)
    raw, prev = b"", None
    for y, samples in enumerate(rows):
        if depth == 16:
            line = b"".join(struct.pack(">H", v) for v in samples)
        elif depth == 8:
            line = bytes(samples)
        else:
            bits = "".join(format(v, "0%db" % depth) for v in samples)
            bits += "0" * (-len(bits) % 8)
            line = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        prev = prev if prev is not None else bytes(len(line))
        f = y % 5
        out = bytearray()
        for i, c in enumerate(line):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            cc = prev[i - bpp] if i >= bpp else 0
            pred = (0, a, b, (a + b) // 2)[f] if f < 4 else min(
                (abs(b - cc), 0, a), (abs(a - cc), 1, b), (abs(a + b - 2 * cc), 2, cc))[2]
            out.append((c - pred) & 255)
        raw += bytes((f,)) + bytes(out)
        prev = line
    ihdr = struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, interlace)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if plte:
        png += chunk(b"PLTE", plte)
    if trns:
        png += chunk(b"tRNS", trns)
    idat = chunk(b"IDAT", zlib.compress(raw))
    if not crc_ok:
        idat = idat[:-1] + bytes((idat[-1] ^ 1,))
    return png + idat + chunk(b"IEND", b"")


def rgba_png(w, h, pixels):
    """A colour type 6, 8-bit PNG of straight RGBA bytes."""
    rows = [list(pixels[y * w * 4:(y + 1) * w * 4]) for y in range(h)]
    return make_png(w, h, 6, 8, rows)


def picture(w, h, seed, opaque=False):
    """A picture with every kind of pixel: clear, half-clear, opaque."""
    rnd = random.Random(seed)
    out = bytearray()
    for y in range(h):
        for x in range(w):
            a = 255 if opaque else rnd.choice((0, 0, 255, 255, 255, rnd.randrange(1, 255)))
            out += bytes((rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), a))
    return bytes(out)


# Baseline JPEG headers: the writer reads markers only and carries the bytes
# as they are, so a frame header and a scan are all a test needs.
def make_jpeg(w, h, sof=0xC0, comps=3):
    sof_body = struct.pack(">BHHB", 8, h, w, comps) + b"".join(bytes((i + 1, 0x11, 0)) for i in range(comps))
    return (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + bytes((0xFF, sof)) + struct.pack(">H", 2 + len(sof_body)) + sof_body
            + b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00" + b"\x12\x34\x56" + b"\xff\xd9")


def refused(fn, *args, **kw):
    """The reason fn refused, or None if it did not."""
    try:
        fn(*args, **kw)
    except swfgen.Refused as e:
        return str(e)
    return None


def pic(w, h, seed=1, opaque=False):
    return swfgen.Picture("png", w, h, rgba=picture(w, h, seed, opaque))


# What the originals are, pinned from their bytes (locations/libs/sprite/
# CL_BW.png.swf, 75x75; a_campfire.png.swf, six pictures held two frames).
CL_BW = dict(version=9, stage=(0, 11000, 0, 8000), fps=12.0, frames=1,
             codes=[69, 9, 36, 2, 26, 1, 0], file_attrs=bytes(4), background=b"\xff\xff\xff",
             place=bytes.fromhex("060100020000"),
             shape=bytes.fromhex("020060002ee0002ee001430100d9400005000000001013d0bb9d2bb9d1449d344800"))
CAMPFIRE = dict(fps=25.0, frames=12, codes=[69, 9] + [35, 2, 26, 1, 1] * 6 + [0],
                moves=[bytes.fromhex("03010%s00" % c) for c in ("004", "006", "008", "00a", "00c")])


try:
    # --- PNG: every colour type, depth and filter -------------------------------------------
    rnd = random.Random(7)
    cases = []
    for ctype, depths in ((0, (1, 2, 4, 8, 16)), (2, (8, 16)), (3, (1, 2, 4, 8)), (4, (8, 16)), (6, (8, 16))):
        for depth in depths:
            cases.append((ctype, depth, False))
            if ctype in (0, 2, 3):
                cases.append((ctype, depth, True))
    for ctype, depth, with_trns in cases:
        w, h = 7, 6
        chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
        top = (1 << depth) - 1
        plte = trns = None
        if ctype == 3:
            n = min(top + 1, 12)
            pal = [(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(n)]
            plte = b"".join(bytes(c) for c in pal)
            alphas = [rnd.randrange(256) for _ in range(n // 2)] if with_trns else []
            trns = bytes(alphas) or None
            rows = [[rnd.randrange(n) for _ in range(w)] for _ in range(h)]
        else:
            rows = [[rnd.randrange(top + 1) for _ in range(w * chans)] for _ in range(h)]
            if with_trns:
                key = rows[1][:chans]
                trns = b"".join(struct.pack(">H", v) for v in key)
        want = bytearray()
        for row in rows:
            for x in range(w):
                s = row[x * chans:(x + 1) * chans]
                to8 = (lambda v: v >> 8) if depth == 16 else (lambda v: v * 255 // top)
                if ctype == 3:
                    r, g, b = pal[s[0]]
                    a = alphas[s[0]] if with_trns and s[0] < len(alphas) else 255
                elif ctype in (0, 4):
                    r = g = b = to8(s[0])
                    a = to8(s[1]) if ctype == 4 else (0 if with_trns and s == key else 255)
                else:
                    r, g, b = (to8(v) for v in s[:3])
                    a = to8(s[3]) if ctype == 6 else (0 if with_trns and s == key else 255)
                want += bytes((r, g, b, a))
        got = swfgen.png_decode(make_png(w, h, ctype, depth, rows, plte, trns))
        check("png: colour type %d, %d-bit%s decodes to the pixels written" % (
            ctype, depth, " with tRNS" if with_trns else ""), got, (w, h, bytes(want)))

    one = make_png(1, 1, 6, 8, [[1, 2, 3, 4]])
    check("png: interlaced is refused", "interlac" in (refused(swfgen.png_decode, make_png(1, 1, 6, 8, [[1, 2, 3, 4]], interlace=1)) or ""), True)
    wide = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2881, 1, 8, 6, 0, 0, 0)) + one[33:]
    check("png: a side over 2880 is refused from the header", "2880" in (refused(swfgen.png_decode, wide) or ""), True)
    check("  ..and picture_size, which reads nothing else, says so too", "2880" in (refused(swfgen.picture_size, wide) or ""), True)
    check("png: a bad CRC is refused", "CRC" in (refused(swfgen.png_decode, make_png(1, 1, 6, 8, [[1, 2, 3, 4]], crc_ok=False)) or ""), True)
    check("png: cut short is refused", refused(swfgen.png_decode, one[:40]) is not None, True)
    check("png: not a PNG at all is refused", refused(swfgen.picture, b"GIF89a....") is not None, True)
    bomb = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(bytes(50 << 20))) + chunk(b"IEND", b"")
    t0 = time.time()
    check("png: image data that inflates to 50 MB for one pixel is read only as far as the pixel",
          (swfgen.png_decode(bomb), time.time() - t0 < 5), ((1, 1, bytes(4)), True))

    # --- JPEG ----------------------------------------------------------------------------------
    jpg = make_jpeg(120, 90)
    check("jpeg: baseline size from its frame header", swfgen.jpeg_size(jpg), (120, 90))
    check("jpeg: progressive is refused", "baseline" in (refused(swfgen.jpeg_size, make_jpeg(9, 9, sof=0xC2)) or ""), True)
    check("jpeg: extended sequential is refused too", refused(swfgen.jpeg_size, make_jpeg(9, 9, sof=0xC1)) is not None, True)
    check("jpeg: CMYK is refused", "CMYK" in (refused(swfgen.jpeg_size, make_jpeg(9, 9, comps=4)) or ""), True)
    check("jpeg: a side over 2880 is refused", refused(swfgen.jpeg_size, make_jpeg(3000, 9)) is not None, True)
    check("jpeg: grey (one component) is fine", swfgen.jpeg_size(make_jpeg(5, 4, comps=1)), (5, 4))

    # --- one picture: the form of CL_BW.png.swf ----------------------------------------------------
    src = picture(75, 75, seed=3)
    data = swfgen.sprite_swf([swfgen.picture(rgba_png(75, 75, src))])
    hdr, tags = read_swf(data)
    check("one picture: compressed SWF 9, the originals' stage, 12 fps, one frame",
          (hdr["sig"], hdr["version"], hdr["stage"], hdr["fps"], hdr["frames"]),
          (b"CWS", CL_BW["version"], CL_BW["stage"], CL_BW["fps"], CL_BW["frames"]))
    check("one picture: CL_BW's tags, in its order", [c for c, _ in tags], CL_BW["codes"])
    check("one picture: FileAttributes, background and PlaceObject2 byte for byte as CL_BW's",
          (tags[0][1], tags[1][1], tags[4][1]), (CL_BW["file_attrs"], CL_BW["background"], CL_BW["place"]))
    check("one picture: a 75x75 shape byte for byte as CL_BW's own", tags[3][1], CL_BW["shape"])
    cid, fmt, w, h, px = read_lossless2(tags[2][1])
    check("one picture: DefineBitsLossless2 id 1, format 5, 75x75", (cid, fmt, w, h), (1, 5, 75, 75))
    check("one picture: its pixels are the picture's, premultiplied", px, premul(src))
    check("  ..and a clear pixel is 0,0,0,0", all(px[i:i + 4] == bytes(4) for i in range(0, len(px), 4) if src[i + 3] == 0), True)
    sh = read_shape(tags[3][1])
    t, bid, m, _raw = sh["fills"][0]
    check("one picture: the shape is the bitmap, clipped, one pixel to 20 twips, at 0,0",
          (sh["id"], t, bid, m["sx"], m["sy"], m["r0"], m["r1"], m["tx"], m["ty"], sh["lines"], sh["fill1"]),
          (2, 0x43, 1, 20.0, 20.0, 0.0, 0.0, 0, 0, 0, 1))
    check("one picture: the outline is the w x h rectangle from 0,0, closed",
          (sh["bounds"], outline(sh)),
          ((0, 1500, 0, 1500), ([(0, 0), (0, 1500), (1500, 0), (1500, 1500)], True)))
    for w, h in ((1, 1), (2880, 1), (1, 2880), (333, 7)):
        sh = read_shape(swfgen.shape(2, 1, w, h)[6:])
        check("shape %dx%d: bounds and outline in twips" % (w, h),
              (sh["bounds"], outline(sh)),
              ((0, w * 20, 0, h * 20), (sorted({(0, 0), (0, h * 20), (w * 20, 0), (w * 20, h * 20)}), True)))
    check("one picture: the same picture gives the same bytes", swfgen.sprite_swf([swfgen.picture(rgba_png(75, 75, src))]), data)

    # --- an animation: the form of a_campfire.png.swf -------------------------------------------------
    six = [pic(30, 20, seed=s) for s in range(6)]
    data = swfgen.sprite_swf(six, fps=12)
    hdr, tags = read_swf(data)
    codes = [36 if c == 36 else c for c, _ in tags]
    check("animation: six pictures at 12 fps are a_campfire's twelve frames at 25",
          (hdr["fps"], hdr["frames"]), (CAMPFIRE["fps"], CAMPFIRE["frames"]))
    check("animation: a_campfire's tags, a lossless bitmap where it has JPEG3",
          codes, [36 if c == 35 else c for c in CAMPFIRE["codes"]])
    check("animation: the next picture swapped in as a_campfire does it",
          [b for c, b in tags if c == 26][1:], CAMPFIRE["moves"])
    frames, defined = timeline(tags)
    check("animation: frame by frame, each picture held two frames",
          [six.index(next(p for p in six if premul(p.rgba) == bitmap_of(defined, s)[3])) for s in frames],
          [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5])
    for fps, hold in ((25, 1), (12, 2), (8, 3), (5, 5), (4, 6), (1, 25)):
        check("animation at %d fps: each picture held %d game frames" % (fps, hold), swfgen.hold_for(fps), hold)
        hdr, tags = read_swf(swfgen.sprite_swf(six[:3], fps=fps))
        frames, _ = timeline(tags)
        check("  ..%d frames in the header and on the timeline" % (3 * hold), (hdr["frames"], len(frames)), (3 * hold, 3 * hold))
    for bad in (0, 26, 2.5, "4", None):
        check("animation: fps %r is refused" % (bad,), refused(swfgen.sprite_swf, six[:2], fps=bad) is not None, True)
    check("animation: pictures of two sizes are refused",
          "same size" in (refused(swfgen.sprite_swf, [pic(30, 20), pic(30, 21)], fps=5) or ""), True)
    abc = [pic(8, 8, seed=s) for s in (1, 2, 1)]
    hdr, tags = read_swf(swfgen.sprite_swf(abc, fps=25, keys=["a.png", "b.png", "a.png"]))
    frames, defined = timeline(tags)
    check("animation: a picture that comes back is stored once and shown again",
          (sum(1 for c, _ in tags if c == 36), [bitmap_of(defined, s)[3] == premul(abc[0].rgba) for s in frames]),
          (2, [True, False, True]))
    check("animation: the same pictures give the same bytes", swfgen.sprite_swf(six, fps=12), data)

    # --- a JPEG: carried byte for byte ---------------------------------------------------------------
    hdr, tags = read_swf(swfgen.sprite_swf([swfgen.picture(jpg)]))
    check("jpeg: tags as the original background Oasis.jpg.swf", [c for c, _ in tags], [69, 9, 21, 2, 26, 1, 0])
    check("jpeg: DefineBitsJPEG2 holds the file unchanged", tags[2][1], b"\x01\x00" + jpg)
    sh = read_shape(tags[3][1])
    check("jpeg: the shape is 120x90, clipped", (sh["bounds"], sh["fills"][0][0]), ((0, 2400, 0, 1800), 0x43))
    mixed = [swfgen.picture(jpg), swfgen.Picture("png", 120, 90, rgba=picture(120, 90, 5, opaque=True))]
    frames, defined = timeline(read_swf(swfgen.sprite_swf(mixed, fps=25))[1])
    check("jpeg: a JPEG and a PNG of one size animate together",
          [bitmap_of(defined, s)[0] for s in frames], ["jpeg", "png"])

    # --- the originals themselves, when the client's art is here --------------------------------------
    sprite_dir = os.path.join(RES, "locations", "libs", "sprite")
    orig = os.path.join(sprite_dir, "CL_BW.png.swf")
    if RES and os.path.exists(orig):
        with open(orig, "rb") as fh:
            ohdr, otags = read_swf(fh.read())
        _, _, w, h, opx = read_lossless2(otags[2][1])
        ours_hdr, ours = read_swf(swfgen.sprite_swf([swfgen.Picture("png", w, h, rgba=unpremul(opx))]))
        check("CL_BW.png.swf: its own picture re-wrapped has its header and tags",
              ((ours_hdr["version"], ours_hdr["stage"], ours_hdr["fps"], ours_hdr["frames"]), [c for c, _ in ours]),
              ((ohdr["version"], ohdr["stage"], ohdr["fps"], ohdr["frames"]), [c for c, _ in otags]))
        check("CL_BW.png.swf: every tag byte for byte but the bitmap's packing",
              [b for c, b in ours if c != 36], [b for c, b in otags if c != 36])
        check("CL_BW.png.swf: the bitmap's pixels byte for byte", read_lossless2(ours[2][1]), read_lossless2(otags[2][1]))
        check("CL_BW.png.swf: what is pinned above is still the original", (otags[3][1], otags[4][1]), (CL_BW["shape"], CL_BW["place"]))
        camp = os.path.join(sprite_dir, "a_campfire.png.swf")
        with open(camp, "rb") as fh:
            chdr, ctags = read_swf(fh.read())
        cframes, cdefined = timeline(ctags)
        sh = read_shape(cdefined[cframes[0]][1])
        cw, ch = sh["bounds"][1] // 20, sh["bounds"][3] // 20
        ours_hdr, ours = read_swf(swfgen.sprite_swf([pic(cw, ch, seed=s) for s in range(6)], fps=12))
        check("a_campfire.png.swf: six pictures of its size at 12 fps have its header",
              (ours_hdr["fps"], ours_hdr["frames"]), (chdr["fps"], chdr["frames"]))
        check("a_campfire.png.swf: and its placements byte for byte",
              [b for c, b in ours if c == 26], [b for c, b in ctags if c == 26])

        def shapes(tags):
            out = []
            for c, b in tags:
                if c == 2:
                    sh = read_shape(b)
                    out.append((sh["id"], sh["bounds"], [f[:2] + (f[3],) for f in sh["fills"]], outline(sh)))
            return out
        check("a_campfire.png.swf: and its shapes: ids, bounds, fills, outlines (it starts at the far corner)",
              shapes(ours), shapes(ctags))
        check("a_campfire.png.swf: what is pinned above is still the original",
              ([c for c, _ in ctags], [b for c, b in ctags if c == 26][1:]), (CAMPFIRE["codes"], CAMPFIRE["moves"]))
        oasis = os.path.join(RES, "locations", "libs", "background", "Oasis.jpg.swf")
        with open(oasis, "rb") as fh:
            _, otags = read_swf(fh.read())
        ojpeg = otags[2][1][2:]
        ours = read_swf(swfgen.sprite_swf([swfgen.picture(ojpeg)]))[1]
        check("Oasis.jpg.swf: its JPEG re-wrapped is its tags byte for byte",
              [b for _, b in ours], [b for _, b in otags])
    else:
        print("  --  no CL_BW.png.swf under LAVA_RES=%r; the re-wraps of the originals are skipped,"
              " the pinned forms ran above" % RES)

    # --- the manifest --------------------------------------------------------------------------
    good = {"title": "Флажок", "frames": ["0.png"], "anchor": [3, 7]}

    def entry_refused(oid, **kw):
        e = dict(good)
        e.update(kw)
        for k in [k for k, v in kw.items() if v is KeyError]:
            del e[k]
        return refused(co.check_entry, oid, e)

    check("manifest: an entry with defaults filled in",
          co.check_entry("c_flag", good),
          {"title": "Флажок", "frames": ["0.png"], "fps": None, "kind": "sprite", "note": None,
           "anchor": (3, 7), "front": [(0, 0)], "footprint": []})
    for oid in ("flag", "c_", "c_Flag", "c_флаг", "c_" + "x" * 41, "c_a.png", "C_flag"):
        check("manifest: id %r is refused" % oid, entry_refused(oid) is not None, True)
    check("manifest: an id of 40 after c_ is fine", entry_refused("c_" + "x" * 40), None)
    for name, kw in (("an unknown field", dict(colour="red")),
                     ("no title", dict(title=KeyError)), ("an empty title", dict(title=" ")),
                     ("a title of two lines", dict(title="a\nb")), ("a title of 81", dict(title="я" * 81)),
                     ("a note that is not text", dict(note=3)),
                     ("kind decal", dict(kind="decal")), ("no frames", dict(frames=[])),
                     ("121 frames", dict(frames=["0.png"] * 121, fps=5)),
                     ("a frame up a folder", dict(frames=["../0.png"])), ("a frame in a folder", dict(frames=["a/0.png"])),
                     ("a GIF", dict(frames=["0.gif"])), ("a frame in capitals", dict(frames=["0.PNG"])),
                     ("an animation without fps", dict(frames=["0.png", "1.png"])),
                     ("fps 0", dict(fps=0)), ("fps 26", dict(fps=26)), ("fps as text", dict(fps="4")),
                     ("fps 4.0", dict(fps=4.0)), ("no anchor", dict(anchor=KeyError)),
                     ("an anchor of one number", dict(anchor=[3])), ("an anchor of text", dict(anchor=["3", "7"])),
                     ("an empty front", dict(front=[])), ("a front cell past 127", dict(front=[[128, 0]])),
                     ("a footprint cell twice", dict(footprint=[[0, 0], [0, 0]])),
                     ("a footprint cell of three", dict(footprint=[[0, 0, 0]])),
                     ("a background of two pictures", dict(kind="background", frames=["0.png", "1.png"], fps=5, anchor=KeyError)),
                     ("a background with a footprint", dict(kind="background", footprint=[[0, 0]], anchor=KeyError))):
        check("manifest: %s is refused" % name, entry_refused("c_flag", **kw) is not None, True)
    check("manifest: a background needs no anchor", entry_refused("c_sand", kind="background", anchor=KeyError), None)
    check("manifest: a picture may repeat in an animation",
          entry_refused("c_flag", frames=["0.png", "1.png", "0.png"], fps=5), None)

    def objdir(manifest, files, name="objects"):
        d = os.path.join(W, name)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as fh:
            fh.write(manifest if isinstance(manifest, str) else json.dumps(manifest, ensure_ascii=False))
        for p, data in files.items():
            os.makedirs(os.path.dirname(os.path.join(d, p)), exist_ok=True)
            with open(os.path.join(d, p), "wb") as fh:
                fh.write(data)
        return d

    flag = [rgba_png(12, 20, picture(12, 20, s)) for s in (1, 2)]
    m = {"c_flag": {"title": "Флажок", "frames": ["0.png", "1.png"], "fps": 5, "anchor": [6, 19],
                    "front": [[0, 0]], "footprint": [[0, 0], [1, 0]]},
         "c_sand": {"title": "Песок", "frames": ["0.jpg"], "kind": "background"}}
    files = {"c_flag/0.png": flag[0], "c_flag/1.png": flag[1], "c_sand/0.jpg": make_jpeg(64, 32)}
    d = objdir(m, files)
    built, report = co.build(d)
    check("build: a sprite and a background, at their release paths",
          sorted(built), ["locations/libs/background/c_sand.swf", "locations/libs/sprite/c_flag.swf"])
    frames, defined = timeline(read_swf(built["locations/libs/sprite/c_flag.swf"])[1])
    check("build: the sprite is its two pictures at 5 fps, five frames each",
          [bitmap_of(defined, s)[3] == premul(swfgen.png_decode(flag[i // 5])[2]) for i, s in enumerate(frames)],
          [True] * 10)
    check("build: a report line per object",
          [line.split()[2:4] for line in report],
          [["locations/libs/sprite/c_flag.swf", "(12x20,"], ["locations/libs/background/c_sand.swf", "(64x32,"]])
    d2 = objdir(m, files, "objects2")
    check("build: the same folder elsewhere gives the same bytes", co.build(d2)[0], built)
    check("build: no manifest, nothing", co.build(os.path.join(W, "nowhere")), ({}, []))
    taken = ["locations/libs/sprite/C_FLAG.swf", "main.swf"]
    check("build: an id whose file the game has, in another case, is refused",
          "C_FLAG" in (refused(co.build, d, taken) or ""), True)
    check("build: an id that is a library of the game is refused",
          refused(co.build, d, ["locations/libs/c_sand.swf"]) is not None, True)
    check("build: an id that is the game's background of that name is refused",
          refused(co.build, d, ["locations/libs/background/c_flag.swf"]) is not None, True)
    for name, change in (
            ("a folder the manifest does not name", {"c_other/0.png": flag[0]}),
            ("a picture the entry does not list", {"c_flag/2.png": flag[0]})):
        dd = objdir(m, dict(files, **change), "objects3")
        check("build: %s is refused" % name, refused(co.build, dd) is not None, True)
    dd = objdir(m, {k: v for k, v in files.items() if k != "c_flag/1.png"}, "objects3")
    check("build: a frame that is not there is refused", "1.png" in (refused(co.build, dd) or ""), True)
    dd = objdir(m, dict(files, **{".DS_Store": b"x", "c_flag/.thumbs": b"x"}), "objects3")
    check("build: a desktop's dot files are no business of it", sorted(co.build(dd)[0]), sorted(built))
    dd = objdir(dict(m, c_flag=dict(m["c_flag"], anchor=[13, 19])), files, "objects3")
    check("build: an anchor outside the picture is refused", "outside" in (refused(co.build, dd) or ""), True)
    dd = objdir(m, dict(files, **{"c_flag/1.png": rgba_png(12, 21, picture(12, 21, 2))}), "objects3")
    check("build: an animation of two sizes is refused, naming the object",
          (refused(co.build, dd) or "").startswith("c_flag: "), True)
    dd = objdir(m, dict(files, **{"c_flag/1.png": b"\x89PNG\r\n\x1a\nbroken"}), "objects3")
    check("build: a broken picture is refused with its path", "c_flag/1.png" in (refused(co.build, dd) or ""), True)
    dd = objdir('{"c_flag": %s, "c_flag": %s}' % (json.dumps(m["c_flag"]), json.dumps(m["c_flag"])), files, "objects3")
    check("build: an id twice in the manifest is refused", "twice" in (refused(co.build, dd) or ""), True)
    dd = objdir("{", files, "objects3")
    check("build: a manifest that is not JSON is refused", "JSON" in (refused(co.build, dd) or ""), True)
    shuffled = {"c_sand": dict(reversed(list(m["c_sand"].items()))), "c_flag": dict(reversed(list(m["c_flag"].items())))}
    text = co.manifest_text(shuffled)
    dd = objdir(text, files, "objects3")
    check("manifest_text: written back, the same manifest", co.load_raw(dd), m)
    check("manifest_text: ids sorted, fields in their order, one a line",
          text.splitlines()[:4], ["{", '  "c_flag": {', '    "title": "Флажок",', '    "frames": ["0.png", "1.png"],'])
    check("manifest_text: what it writes reads back to the same bytes", co.manifest_text(co.load_raw(dd)), text)
    check("manifest_text: an unknown field is refused", refused(co.manifest_text, {"c_x": {"colour": 1}}) is not None, True)
    check("manifest_text: no objects is an empty object", co.manifest_text({}), "{}\n")
    keep = co.MAX_PICTURE_BYTES, co.MAX_TOTAL_BYTES
    try:
        co.MAX_PICTURE_BYTES = len(flag[0]) - 1
        check("build: a picture over the size a deploy may carry is refused", "extra.txt" in (refused(co.build, d) or ""), True)
        co.MAX_PICTURE_BYTES, co.MAX_TOTAL_BYTES = keep[0], len(flag[0]) + 10
        check("build: pictures over the total a deploy may carry are refused", "extra.txt" in (refused(co.build, d) or ""), True)
    finally:
        co.MAX_PICTURE_BYTES, co.MAX_TOTAL_BYTES = keep

    # --- placing an object ----------------------------------------------------------------------------
    import world  # noqa: E402

    def client_cells(front, ax, ay):
        """LDParser.getHexCoord(front, ax - 128, ay - 128), as the client reads it."""
        out = []
        for i in range(0, len(front), 4):
            bx, by = int(front[i:i + 2], 16), int(front[i + 2:i + 4], 16)
            out.append((bx + ax - 128 + (1 if ay % 2 == 1 and by % 2 == 1 else 0), by + ay - 128))
        return out

    e = co.check_entry("c_wide", {"title": "Ряд", "frames": ["0.png"], "anchor": [40, 60],
                                  "front": [[-1, 0], [0, 0], [1, 0], [-1, -1], [0, 1]],
                                  "footprint": [[0, 0], [-1, -1], [0, -1], [-1, 1]]})
    for gx, gy in ((30, 64), (30, 65)):
        r = co.place("c_wide", e, gx, gy)
        check("place at %d:%d (%s row): the sprite element in the originals' attribute order" % (gx, gy, "odd" if gy % 2 else "even"),
              r["sprite"], '<sprite id="c_wide" dx="-40" dy="-60" front="7f80808081807f7f8081" type="ext">%02x%02x</sprite>' % (gx, gy))
        check("place at %d:%d: front cells as the client decodes the attribute" % (gx, gy),
              r["front"], client_cells(dict(r["attrs"])["front"], gx, gy))
        obst = world._chunks("<obstacles>%s</obstacles>" % r["obstacles"], "obstacles", 5)
        check("place at %d:%d: the footprint, as the server reads <obstacles>, walls (f) on the client's cells" % (gx, gy),
              [(int(c[:2], 16), int(c[2:4], 16), c[4]) for c in obst],
              [(x, y, "f") for x, y in client_cells(co.encode_cells(e["footprint"]), gx, gy)])
    check("place on an odd row: a cell on an odd relative row moves one to the right",
          co.place("c_wide", e, 30, 65)["footprint"], [(30, 65), (30, 64), (31, 64), (30, 66)])
    check("place on an even row: no cell moves",
          co.place("c_wide", e, 30, 64)["footprint"], [(30, 64), (29, 63), (30, 63), (29, 65)])
    check("place: a footprint off the grid is refused", refused(co.place, "c_wide", e, 0, 0) is not None, True)
    check("place: a background is not placed on a cell",
          refused(co.place, "c_sand", co.check_entry("c_sand", m["c_sand"]), 3, 3) is not None, True)

    # --- the repository's own objects -------------------------------------------------------------------
    sys.path.insert(0, os.path.join(ROOT, "client"))
    import build as client_build  # noqa: E402  (client/build.py: the original's paths, the path rules)
    base = client_build.read_entries(os.path.join(ROOT, "client", "base.txt"), "lava-base 1")
    extra = client_build.read_entries(os.path.join(ROOT, "client", "extra.txt"), "lava-extra 1")
    objs = co.load()
    files, report = co.build(taken=set(base) | set(extra))
    check("client/objects: every object builds against client/base.txt and extra.txt",
          sorted(files), sorted(co.release_path(o, e) for o, e in objs.items()))
    check("client/objects: every path passes the release's path rules",
          [p for p in files if client_build.check_path(p)], [])
    for p, data in sorted(files.items()):
        hdr, tags = read_swf(data)
        frames, defined = timeline(tags)
        oid = p.rsplit("/", 1)[1][:-4]
        n = len(objs[oid]["frames"])
        check("client/objects: %s reads back, %d picture%s" % (p, n, "" if n == 1 else "s"),
              (hdr["version"], len(frames), len({s for s in frames})),
              (9, n * (swfgen.hold_for(objs[oid]["fps"]) if n > 1 else 1), len(set(objs[oid]["frames"]))))
    check("client/objects: the sample «Тестовый флажок» is there", objs.get("c_test_flag", {}).get("title"), "Тестовый флажок")
    with open(os.path.join(co.OBJDIR, "manifest.json"), "rb") as fh:
        check("client/objects: manifest.json is written the one way manifest_text writes it",
              fh.read().decode("utf-8"), co.manifest_text(co.load_raw()))
except Exception:
    import traceback
    fails.append("crashed:\n" + traceback.format_exc())
finally:
    shutil.rmtree(W, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("swfgen OK")
