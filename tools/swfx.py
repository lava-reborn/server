"""Minimal SWF reader for LAVA Online assets: bitmaps, bitmap-filled shapes,
sprites and the root timeline. Enough to render every frame of a character
animation or a library symbol into a PIL image plus its offset from the
registration point -- which is exactly what the Flash client does in
SpriteSource.drawBitmap (crop to bounds, remember xMin/yMin).

Vector fills other than bitmaps are skipped: LAVA art is raster wrapped in
rectangles, and a frame that comes out empty is reported, not guessed.

Vendored from lava-godot tools/swfx.py (commit c05100f, sha256 73954d02...)
for the location editor (tools/location_art.py), with two fixes the
location research found (scratchpad loc/assets, journal of 2026-10-12):

  1. DefineBitsJPEG3 colour is stored premultiplied by its alpha plane, as
     Lossless2 is: 99.2% of half-transparent pixels have rgb <= alpha. It
     is now un-premultiplied too; before, edges and shadows came out with
     dark halos (Mountains edge01: mean RGB 51 instead of 86).
  2. The client draws a library symbol, a decal and a background as
     SpriteSource.drawBitmap does: a BitmapData of the clip's _width x
     _height, translated by -getRect().xMin/yMin -- the shapes' bounds,
     transparent margins included. render(crop="bounds"), the default now,
     returns exactly that picture and the bounds' top-left as the offset;
     crop="alpha" is the old trim to the visible pixels (Mountains edge01:
     424 px wide by its bounds, 368 trimmed, 56 px further right).
     library_bitmap() and root_bitmap() are getFromLib and getBitmap.

Also: Swf() takes bytes as well as a path, and Pillow is imported only when
a picture is decoded, so the tag reader works without it.
"""
import io
import struct
import zlib

try:
    from PIL import Image
except ImportError:          # the tag reader still works; pictures do not
    Image = None


class Bits:
    def __init__(self, data, pos=0):
        self.d = data
        self.bp = pos * 8

    def align(self):
        self.bp = (self.bp + 7) & ~7

    @property
    def pos(self):
        self.align()
        return self.bp >> 3

    def u(self, n):
        v = 0
        for _ in range(n):
            byte = self.d[self.bp >> 3]
            v = (v << 1) | ((byte >> (7 - (self.bp & 7))) & 1)
            self.bp += 1
        return v

    def s(self, n):
        if n == 0:
            return 0
        v = self.u(n)
        if v & (1 << (n - 1)):
            v -= 1 << n
        return v


def read_rect(data, pos):
    b = Bits(data, pos)
    n = b.u(5)
    r = [b.s(n) for _ in range(4)]  # xmin xmax ymin ymax, twips
    return r, b.pos


def read_matrix(data, pos):
    """Returns (a, b, c, d, tx, ty) in Flash convention: x' = a*x + c*y + tx."""
    b = Bits(data, pos)
    a = d = 1.0
    bb = c = 0.0
    if b.u(1):
        n = b.u(5)
        a = b.s(n) / 65536.0
        d = b.s(n) / 65536.0
    if b.u(1):
        n = b.u(5)
        bb = b.s(n) / 65536.0
        c = b.s(n) / 65536.0
    n = b.u(5)
    tx = b.s(n)
    ty = b.s(n)
    return (a, bb, c, d, tx, ty), b.pos


def mat_mul(m1, m2):
    """m1 applied after m2 (parent * child)."""
    a1, b1, c1, d1, x1, y1 = m1
    a2, b2, c2, d2, x2, y2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * x2 + c1 * y2 + x1, b1 * x2 + d1 * y2 + y1)


IDENT = (1.0, 0.0, 0.0, 1.0, 0, 0)


def _strip_jpeg(data):
    # Old Flash prefixes FF D9 FF D8 before the real SOI.
    if data[:4] == b"\xff\xd9\xff\xd8":
        data = data[4:]
    # And sometimes embeds an extra EOI/SOI pair mid-stream.
    return data.replace(b"\xff\xd9\xff\xd8", b"")


def iter_tags(data, pos, end):
    while pos < end:
        cl, = struct.unpack_from("<H", data, pos)
        pos += 2
        code, ln = cl >> 6, cl & 0x3F
        if ln == 0x3F:
            ln, = struct.unpack_from("<I", data, pos)
            pos += 4
        yield code, data[pos:pos + ln]
        pos += ln
        if code == 0:
            break


def _need_pil():
    if Image is None:
        raise RuntimeError("swfx: decoding pictures needs Pillow (and numpy)")


class Swf:
    def __init__(self, path):
        if isinstance(path, (bytes, bytearray)):
            raw = bytes(path)
        else:
            with open(path, "rb") as fh:
                raw = fh.read()
        sig = raw[:3]
        if sig == b"CWS":
            body = zlib.decompress(raw[8:])
        elif sig == b"FWS":
            body = raw[8:]
        elif sig == b"ZWS":
            import lzma
            props = raw[12:17]
            dict_size, = struct.unpack("<I", props[1:5])
            filt = lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)
            body = lzma.decompress(raw[17:], format=lzma.FORMAT_RAW, filters=[filt])
        else:
            raise ValueError("not a swf: %r" % sig)
        self.version = raw[3]
        rect, p = read_rect(body, 0)
        self.stage = rect
        self.rate, self.nframes = struct.unpack_from("<HH", body, p)
        p += 4
        self.chars = {}       # id -> ("bitmap", Image) | ("shape", info) | ("sprite", frames)
        self.exports = {}     # name -> id
        self.jpeg_tables = b""
        self.unknown = set()
        self.timeline = self._read_timeline(body, p, len(body))

    # -- definitions --------------------------------------------------------
    def _define(self, code, t):
        if code == 8:
            self.jpeg_tables = _strip_jpeg(t)
            if self.jpeg_tables.endswith(b"\xff\xd9"):
                self.jpeg_tables = self.jpeg_tables[:-2]
        elif code in (6, 21, 35):
            _need_pil()
            cid, = struct.unpack_from("<H", t, 0)
            if code == 35:
                aoff, = struct.unpack_from("<I", t, 2)
                jpg, alpha = t[6:6 + aoff], t[6 + aoff:]
            else:
                jpg, alpha = t[2:], b""
            jpg = _strip_jpeg(jpg)
            if code == 6:
                jpg = self.jpeg_tables + jpg[2:] if self.jpeg_tables else jpg
            if jpg[:8] == b"\x89PNG\r\n\x1a\n" or jpg[:3] == b"GIF":
                img = Image.open(io.BytesIO(jpg)).convert("RGBA")
            else:
                img = Image.open(io.BytesIO(jpg)).convert("RGBA")
                if alpha:
                    a = zlib.decompress(alpha)
                    if len(a) == img.width * img.height:
                        img.putalpha(Image.frombytes("L", img.size, a))
                        # Fix 1: the colour of a JPEG3 is premultiplied by
                        # its alpha plane, as Lossless2's is.
                        img = _unpremultiply(img)
            self.chars[cid] = ("bitmap", img)
        elif code in (20, 36):
            _need_pil()
            cid, fmt, w, h = struct.unpack_from("<HBHH", t, 0)
            p = 7
            if fmt == 3:
                ncol = t[p] + 1
                p += 1
            raw = zlib.decompress(t[p:])
            if fmt == 3:
                cs = 4 if code == 36 else 3
                pal = raw[:ncol * cs]
                pix = raw[ncol * cs:]
                stride = (w + 3) & ~3
                img = Image.new("RGBA", (w, h))
                px = img.load()
                for y in range(h):
                    row = pix[y * stride:y * stride + w]
                    for x, ci in enumerate(row):
                        if ci < ncol:
                            c = pal[ci * cs:ci * cs + cs]
                            px[x, y] = (c[0], c[1], c[2], c[3] if cs == 4 else 255)
                if code == 36:
                    img = _unpremultiply(img)
            elif fmt == 5:
                img = Image.frombytes("RGBA", (w, h), raw[:w * h * 4])
                a, r, g, b = img.split()
                img = Image.merge("RGBA", (r, g, b, a if code == 36 else Image.new("L", (w, h), 255)))
                if code == 36:
                    img = _unpremultiply(img)
            else:
                stride = (w * 2 + 3) & ~3
                img = Image.new("RGBA", (w, h))
                px = img.load()
                for y in range(h):
                    for x in range(w):
                        v, = struct.unpack_from(">H", raw, y * stride + x * 2)
                        px[x, y] = (((v >> 10) & 31) << 3, ((v >> 5) & 31) << 3, (v & 31) << 3, 255)
            self.chars[cid] = ("bitmap", img)
        elif code in (2, 22, 32, 83):
            self.chars[struct.unpack_from("<H", t, 0)[0]] = ("shape", self._parse_shape(code, t))
        elif code == 39:
            cid, nf = struct.unpack_from("<HH", t, 0)
            self.chars[cid] = ("sprite", self._read_timeline(t, 4, len(t)))
        elif code == 56 or code == 76:
            n, = struct.unpack_from("<H", t, 0)
            p = 2
            for _ in range(n):
                cid, = struct.unpack_from("<H", t, p)
                p += 2
                e = t.index(b"\0", p)
                name = t[p:e].decode("utf-8", "replace")
                p = e + 1
                self.exports[name] = cid
        else:
            self.unknown.add(code)

    def _parse_shape(self, code, t):
        bounds, p = read_rect(t, 2)
        edges = bounds
        if code == 83:
            # DefineShape4: EdgeBounds, the bounds without the strokes, are
            # what getRect() reports; ShapeBounds (with them) give _width.
            edges, p = read_rect(t, p)
            p += 1
        n = t[p]
        p += 1
        if n == 0xFF and code != 2:
            n, = struct.unpack_from("<H", t, p)
            p += 2
        fills = []
        for _ in range(n):
            ft = t[p]
            p += 1
            if ft == 0x00:
                p += 3 if code in (2, 22) else 4
                fills.append(None)
            elif ft in (0x10, 0x12, 0x13):
                _, p = read_matrix(t, p)
                cnt = t[p] & 0x0F
                p += 1 + cnt * (1 + (3 if code in (2, 22) else 4))
                if ft == 0x13:
                    p += 2
                fills.append(None)
            elif 0x40 <= ft <= 0x43:
                bid, = struct.unpack_from("<H", t, p)
                m, p = read_matrix(t, p + 2)
                fills.append((bid, m, ft in (0x41, 0x43)))
            else:
                break
        return {"bounds": bounds, "edges": edges,
                "fills": [f for f in fills if f and f[0] != 0xFFFF]}

    # -- timelines ----------------------------------------------------------
    def _read_timeline(self, data, pos, end):
        frames = []
        dl = {}  # depth -> [cid, matrix]
        for code, t in iter_tags(data, pos, end):
            if code == 1:
                frames.append({d: tuple(v) for d, v in dl.items()})
            elif code in (26, 70):
                fl = t[0]
                p = 1
                if code == 70:
                    fl2 = t[1]
                    p = 2
                depth, = struct.unpack_from("<H", t, p)
                p += 2
                if code == 70 and (fl2 & 0x08 or (fl2 & 0x10 and fl & 0x02)):
                    e = t.index(b"\0", p)
                    p = e + 1
                cur = dl.get(depth)
                if fl & 0x02:
                    cid, = struct.unpack_from("<H", t, p)
                    p += 2
                    m = cur[1] if (cur and fl & 0x01) else IDENT
                    cur = [cid, m]
                if fl & 0x04:
                    m, p = read_matrix(t, p)
                    if cur:
                        cur = [cur[0], m]
                if cur:
                    dl[depth] = cur
            elif code == 4:
                cid, depth = struct.unpack_from("<HH", t, 0)
                m, _ = read_matrix(t, 4)
                dl[depth] = [cid, m]
            elif code in (5, 28):
                depth, = struct.unpack_from("<H", t, 2 if code == 5 else 0)
                dl.pop(depth, None)
            elif code in (0, 9, 12, 43, 69, 77, 24, 64, 65, 15, 18, 19, 45, 14, 59, 86, 41):
                pass
            else:
                self._define(code, t)
        if dl and (not frames or frames[-1] != dl):
            if not frames:
                frames.append({d: tuple(v) for d, v in dl.items()})
        return frames

    # -- rendering ----------------------------------------------------------
    def _collect(self, frame, mat, out, tick, depth_guard=0):
        """Flatten a frame into a list of (bitmap Image, pixel affine)."""
        for depth in sorted(frame):
            cid, m = frame[depth]
            ch = self.chars.get(cid)
            if not ch:
                continue
            full = mat_mul(mat, m)
            kind, val = ch
            if kind == "shape":
                for bid, fm, _clip in val["fills"]:
                    bm = self.chars.get(bid)
                    if bm and bm[0] == "bitmap":
                        out.append((bm[1], mat_mul(full, fm)))
            elif kind == "bitmap":
                out.append((val, mat_mul(full, (20.0, 0, 0, 20.0, 0, 0))))
            elif kind == "sprite" and val and depth_guard < 8:
                self._collect(val[tick % len(val)], full, out, tick, depth_guard + 1)

    def rect(self, frame, mat=IDENT, tick=0, edges=True, depth_guard=0):
        """getRect() of a display-list frame (edges=True) or the box _width
        and _height are read from (edges=False, strokes included): the
        union of the shapes' bounds through the matrices, in twips, as
        (xmin, xmax, ymin, ymax); None for an empty frame."""
        xs, ys = [], []
        for depth in sorted(frame):
            cid, m = frame[depth]
            ch = self.chars.get(cid)
            if not ch:
                continue
            full = mat_mul(mat, m)
            kind, val = ch
            if kind == "shape":
                b = val["edges"] if edges else val["bounds"]
                corners = ((b[0], b[2]), (b[1], b[2]), (b[0], b[3]), (b[1], b[3]))
            elif kind == "bitmap":
                w, h = val.size
                corners = ((0, 0), (w * 20, 0), (0, h * 20), (w * 20, h * 20))
            elif kind == "sprite" and val and depth_guard < 8:
                r = self.rect(val[tick % len(val)], full, tick, edges, depth_guard + 1)
                if r:
                    xs += [r[0], r[1]]
                    ys += [r[2], r[3]]
                continue
            else:
                continue
            a, bb, c, d, tx, ty = full
            for x, y in corners:
                xs.append(a * x + c * y + tx)
                ys.append(bb * x + d * y + ty)
        if not xs:
            return None
        return (min(xs), max(xs), min(ys), max(ys))

    def render(self, frame, tick=0, crop="bounds"):
        """Render a display-list frame. Returns (Image, (ox, oy)): the
        picture and the offset of its top-left from the registration point,
        in pixels; (None, None) when there is nothing to draw.

        crop="bounds" (fix 2): the picture is SpriteSource.drawBitmap's --
        int(_width) x int(_height), its top-left at the bounds' (xMin, yMin),
        transparent margins kept; fills other than bitmaps stay transparent.
        crop="alpha": trimmed to the visible pixels (lava-godot's swfx)."""
        parts = []
        self._collect(frame, IDENT, parts, tick)
        if crop == "bounds":
            r = self.rect(frame, tick=tick)
            rw = self.rect(frame, tick=tick, edges=False)
            if r is None or rw is None:
                return None, None
            fx0, fy0 = r[0] / 20.0, r[2] / 20.0
            cw, ch = int((rw[1] - rw[0]) / 20.0), int((rw[3] - rw[2]) / 20.0)
            if cw <= 0 or ch <= 0:
                return None, None
            _need_pil()
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            self._compose(canvas, parts, fx0, fy0)
            ox = int(fx0) if float(fx0).is_integer() else fx0
            oy = int(fy0) if float(fy0).is_integer() else fy0
            return canvas, (ox, oy)
        if not parts:
            return None, None
        # fill matrices map bitmap pixels -> twips; convert to pixels
        boxes = []
        for img, m in parts:
            a, b, c, d, tx, ty = m
            a, b, c, d, tx, ty = a / 20, b / 20, c / 20, d / 20, tx / 20, ty / 20
            w, h = img.size
            xs, ys = [], []
            for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
                xs.append(a * x + c * y + tx)
                ys.append(b * x + d * y + ty)
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        x0 = int(min(bx[0] for bx in boxes) // 1)
        y0 = int(min(bx[1] for bx in boxes) // 1)
        x1 = int(-(-max(bx[2] for bx in boxes) // 1))
        y1 = int(-(-max(bx[3] for bx in boxes) // 1))
        canvas = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
        self._compose(canvas, parts, x0, y0)
        bbox = canvas.getbbox()
        if not bbox:
            return None, None
        return canvas.crop(bbox), (x0 + bbox[0], y0 + bbox[1])

    @staticmethod
    def _compose(canvas, parts, x0, y0):
        """Draw (bitmap, fill matrix in twips) parts onto canvas, whose
        top-left is the pixel (x0, y0) of the frame."""
        for img, m in parts:
            a, b, c, d, tx, ty = m
            a, b, c, d, tx, ty = a / 20, b / 20, c / 20, d / 20, tx / 20, ty / 20
            if abs(b) < 1e-6 and abs(c) < 1e-6 and abs(a - 1) < 1e-3 and abs(d - 1) < 1e-3:
                blit(canvas, img, int(round(tx - x0)), int(round(ty - y0)))
            else:
                det = a * d - b * c
                if abs(det) < 1e-9:
                    continue
                # inverse: canvas px -> bitmap px
                ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
                ox, oy = tx - x0, ty - y0
                itx = -(ia * ox + ic * oy)
                ity = -(ib * ox + id_ * oy)
                layer = img.transform(canvas.size, Image.AFFINE, (ia, ic, itx, ib, id_, ity),
                                      resample=Image.BILINEAR)
                canvas.alpha_composite(layer)

    def render_symbol(self, name, crop="bounds"):
        """Every frame of an exported symbol: [(Image, (ox, oy))]."""
        cid = self.exports[name]
        kind, val = self.chars[cid]
        if kind == "sprite":
            return [self.render(f, i, crop) for i, f in enumerate(val)] or [(None, None)]
        return [self.render({1: (cid, IDENT)}, 0, crop)]

    def library_bitmap(self, name):
        """SpriteSource.getFromLib(name) on this SWF as a loaded library:
        the symbol attached over the root's first frame and drawn by its
        bounds. A name the library does not export attaches nothing, and
        the root's own picture is drawn instead -- how the painted
        libraries, which export nothing, serve as backgrounds. (Image,
        (ox, oy)) or (None, None) when nothing is there."""
        frame = dict(self.timeline[0]) if self.timeline else {}
        cid = self.exports.get(name)
        if cid is not None:
            frame[max(frame, default=0) + 1] = (cid, IDENT)
        return self.render(frame, 0, "bounds")

    def root_bitmap(self, tick=0):
        """SpriteSource.getBitmap() of a loaded SWF (an ext decal or
        background): its first frame drawn by its bounds. For an ext sprite,
        which the client keeps as a live clip with its origin on the cell,
        the offset says where the picture sits from that origin."""
        if not self.timeline:
            return None, None
        return self.render(self.timeline[tick % len(self.timeline)], tick, "bounds")


def blit(canvas, img, x, y):
    """Alpha-composite img onto canvas with its top-left at (x, y), any part
    outside the canvas cut off."""
    w, h = img.size
    cw, ch = canvas.size
    l, t = max(0, -x), max(0, -y)
    r, b = min(w, cw - x), min(h, ch - y)
    if r <= l or b <= t:
        return
    if (l, t, r, b) != (0, 0, w, h):
        img = img.crop((l, t, r, b))
    canvas.alpha_composite(img, (x + l, y + t))


def _unpremultiply(img):
    import numpy as np
    a = np.asarray(img).astype(np.float32)
    al = a[..., 3:4]
    rgb = np.where(al > 0, np.clip(a[..., :3] * 255.0 / np.maximum(al, 1), 0, 255), 0)
    return Image.fromarray(np.concatenate([rgb, al], axis=2).astype(np.uint8), "RGBA")
