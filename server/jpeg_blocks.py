"""Baseline JPEG at the level of its 8x8 blocks, in plain Python.

The global map the client draws is 273 JPEG tiles (res/globalmap/full/<n>.jpg)
with the squares of the places painted into the picture (server/map_cells.py).
Taking a square off means changing a few blocks of one tile and nothing else,
and the code that does it runs where only the standard library is: inside the
game's image when the gate builds a client release (client/build.py), and in
bootstrap_http for a local run. So this module reads a file down to the
quantized coefficients of every block and writes it back from them:

  * read and written with no block changed, a file comes back byte for byte:
    the same segments in the same order, the same Huffman tables, the same
    restart markers (server/test_map_cells.py holds every tile of the
    original to it);
  * a block that is changed is the only one whose pixels change: every other
    keeps its coefficients exactly, so any decoder draws it as before. That is
    the proof that nothing else on the map moved.

What it reads: one interleaved scan of a baseline or extended sequential
Huffman frame (SOF0, SOF1) with 8-bit samples, any sampling factors, restart
markers or none. Anything else -- progressive, arithmetic, lossless, several
scans -- is refused with JpegError; no tile of the map is such a file.

Pixels go through an integer DCT: the basis is rounded to integers once, so
the same coefficients give the same samples on every machine, and a changed
block is encoded the same way wherever the release is built.
"""
import math

__all__ = ["Jpeg", "JpegError", "ZIGZAG", "idct", "fdct_quantize"]


class JpegError(ValueError):
    """A file this module does not read, or a broken one."""


# Zigzag position k -> the natural (row-major) index of that coefficient.
ZIGZAG = (0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
          12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
          35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
          58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63)

# The 8-point DCT basis, A[u][x] = c(u) cos((2x+1)u pi/16) / 2 scaled by 2**13
# and rounded: every product in a transform is then an exact integer, and one
# division with rounding at the end makes the result. No entry lies near a
# half, so a last-digit difference of cos() between machines cannot move it
# (the suite checks that).
BASIS_BITS = 13
BASIS_EXACT = [[(1 << BASIS_BITS) * (math.sqrt(0.5) if u == 0 else 1.0)
                * math.cos((2 * x + 1) * u * math.pi / 16) / 2 for x in range(8)]
               for u in range(8)]
A = [[int(round(v)) for v in row] for row in BASIS_EXACT]
_SHIFT = 2 * BASIS_BITS
_HALF = 1 << (_SHIFT - 1)


def _div_round(n, d):
    """n / d rounded half away from zero, d > 0, in integers."""
    if n >= 0:
        return (2 * n + d) // (2 * d)
    return -((-2 * n + d) // (2 * d))


def idct(coef_zz, qt):
    """The 64 samples (row-major, 0..255) of a block from its quantized
    coefficients in zigzag order and the quantization table (zigzag order)."""
    F = [0] * 64
    for k in range(64):
        c = coef_zz[k]
        if c:
            F[ZIGZAG[k]] = c * qt[k]
    # rows: tmp[v][x] = sum_u A[u][x] F[v][u]
    tmp = []
    for v in range(8):
        row = F[v * 8:v * 8 + 8]
        if not any(row):
            tmp.append(None)
            continue
        tmp.append([sum(A[u][x] * row[u] for u in range(8) if row[u]) for x in range(8)])
    out = [0] * 64
    rows = [(v, t) for v, t in enumerate(tmp) if t is not None]
    for y in range(8):
        for x in range(8):
            s = 0
            for v, t in rows:
                s += A[v][y] * t[x]
            # floor((s + half) / 2**26): round half up, then level shift
            val = ((s + _HALF) >> _SHIFT) + 128
            out[y * 8 + x] = 0 if val < 0 else 255 if val > 255 else val
    return out


def fdct_quantize(samples, qt):
    """Quantized coefficients in zigzag order of 64 samples (row-major)."""
    f = [s - 128 for s in samples]
    # rows: tmp[y][u] = sum_x A[u][x] f[y][x]
    tmp = [[sum(A[u][x] * f[y * 8 + x] for x in range(8)) for u in range(8)] for y in range(8)]
    out = [0] * 64
    for k in range(64):
        n = ZIGZAG[k]
        v, u = n >> 3, n & 7
        s = 0
        for y in range(8):
            s += A[v][y] * tmp[y][u]
        q = _div_round(s, qt[k] << _SHIFT)
        # what a baseline file can carry: an AC value of 10 bits, a DC of 11
        lim = 2047 if k == 0 else 1023
        out[k] = -lim if q < -lim else lim if q > lim else q
    return out


# --- Huffman tables ------------------------------------------------------------------

def _codes(bits, vals):
    """{symbol: (code, length)} of a table given as BITS (16 counts) and HUFFVAL."""
    out = {}
    code = 0
    i = 0
    for length in range(1, 17):
        for _ in range(bits[length - 1]):
            out[vals[i]] = (code, length)
            code += 1
            i += 1
        code <<= 1
    return out


def _lut(bits, vals):
    """A 65536-entry table: the next 16 bits -> (code length, symbol); (0, 0)
    for a prefix no code has."""
    lut = [(0, 0)] * 65536
    for sym, (code, length) in _codes(bits, vals).items():
        if code >> length:
            raise JpegError("a Huffman table with more codes than its lengths allow")
        a = code << (16 - length)
        b = (code + 1) << (16 - length)
        lut[a:b] = [(length, sym)] * (b - a)
    return lut


def optimal_table(freq):
    """(BITS, HUFFVAL) of a Huffman table for {symbol: count}, no code longer
    than 16 bits and none made of ones only -- the procedure of the
    standard's Annex K.2, as libjpeg has it (jpeg_gen_optimal_table)."""
    f = [0] * 257
    for s, n in freq.items():
        f[s] = n
    f[256] = 1  # the code point no symbol may take
    codesize = [0] * 257
    others = [-1] * 257
    while True:
        c1 = -1
        best = None
        for i in range(257):
            if f[i] and (best is None or f[i] <= best):
                best, c1 = f[i], i
        c2 = -1
        best = None
        for i in range(257):
            if f[i] and i != c1 and (best is None or f[i] <= best):
                best, c2 = f[i], i
        if c2 < 0:
            break
        f[c1] += f[c2]
        f[c2] = 0
        codesize[c1] += 1
        while others[c1] >= 0:
            c1 = others[c1]
            codesize[c1] += 1
        others[c1] = c2
        codesize[c2] += 1
        while others[c2] >= 0:
            c2 = others[c2]
            codesize[c2] += 1
    bits = [0] * 33
    for i in range(257):
        if codesize[i]:
            bits[codesize[i]] += 1
    for i in range(32, 16, -1):
        while bits[i] > 0:
            j = i - 2
            while bits[j] == 0:
                j -= 1
            bits[i] -= 2
            bits[i - 1] += 1
            bits[j + 1] += 2
            bits[j] -= 1
    i = 16
    while bits[i] == 0:
        i -= 1
    bits[i] -= 1
    vals = [s for size in range(1, 33) for s in range(256) if codesize[s] == size]
    return tuple(bits[1:17]), tuple(vals)


# --- the file ----------------------------------------------------------------------------

class Component:
    def __init__(self, cid, h, v, tq):
        self.id, self.h, self.v, self.tq = cid, h, v, tq
        self.td = self.ta = None
        self.bw = self.bh = 0      # blocks per row and per column, padding included
        self.blocks = []           # row-major; each 64 quantized coefficients, zigzag order


def _size(v):
    return abs(v).bit_length()


def _magnitude(v, s):
    return format(v if v >= 0 else v + (1 << s) - 1, "0%db" % s)


class Jpeg:
    """One file, parsed down to its blocks. .comps in frame order, each with
    .blocks; .qt {table id: 64 values, zigzag}; encode() writes it back."""

    def __init__(self, data):
        data = bytes(data)
        if data[:2] != b"\xff\xd8":
            raise JpegError("not a JPEG file")
        self.head = []        # [(marker, payload)] between SOI and SOS, in order
        self.qt = {}
        self.ht = {}          # (class 0 DC / 1 AC, id) -> (BITS, HUFFVAL)
        self.restart = 0
        self.comps = None
        pos = 2
        while True:
            pos, marker = self._marker(data, pos)
            if marker == 0xD9:
                raise JpegError("the file ends before any scan")
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                raise JpegError("a stray marker %02X before the scan" % marker)
            if pos + 2 > len(data):
                raise JpegError("truncated")
            length = int.from_bytes(data[pos:pos + 2], "big")
            payload = data[pos + 2:pos + length]
            if length < 2 or len(payload) != length - 2:
                raise JpegError("truncated segment %02X" % marker)
            pos += length
            if marker == 0xDA:
                self.sos = payload
                break
            self.head.append((marker, payload))
            if marker in (0xC0, 0xC1):
                self._sof(payload)
            elif marker == 0xCC or (0xC2 <= marker <= 0xCF and marker not in (0xC4, 0xC8)):
                raise JpegError("SOF%d: only baseline and extended sequential Huffman files are read"
                                % (marker - 0xC0))
            elif marker == 0xC4:
                self._dht(payload)
            elif marker == 0xDB:
                self._dqt(payload)
            elif marker == 0xDD:
                if len(payload) != 2:
                    raise JpegError("a DRI segment of %d bytes" % len(payload))
                self.restart = int.from_bytes(payload, "big")
        if self.comps is None:
            raise JpegError("no frame header before the scan")
        self._sos(self.sos)
        end, self.segments = self._entropy(data, pos)
        pos, marker = self._marker(data, end)
        if marker != 0xD9:
            raise JpegError("more than one scan, or a marker %02X after it" % marker)
        self.tail = data[pos:]
        self._decode()

    # -- headers --

    @staticmethod
    def _marker(data, pos):
        if pos >= len(data) or data[pos] != 0xFF:
            raise JpegError("no marker at byte %d" % pos)
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            raise JpegError("truncated")
        return pos + 1, data[pos]

    def _sof(self, p):
        if self.comps is not None:
            raise JpegError("two frame headers")
        if len(p) < 6 or p[0] != 8:
            raise JpegError("only 8-bit samples are read")
        self.height = int.from_bytes(p[1:3], "big")
        self.width = int.from_bytes(p[3:5], "big")
        n = p[5]
        if not self.height or not self.width or n not in (1, 3) or len(p) != 6 + 3 * n:
            raise JpegError("a frame header this module does not read")
        self.comps = []
        for i in range(n):
            cid, hv, tq = p[6 + 3 * i], p[7 + 3 * i], p[8 + 3 * i]
            h, v = hv >> 4, hv & 15
            if not (1 <= h <= 4 and 1 <= v <= 4):
                raise JpegError("sampling factors %dx%d" % (h, v))
            self.comps.append(Component(cid, h, v, tq))
        self.hmax = max(c.h for c in self.comps)
        self.vmax = max(c.v for c in self.comps)
        self.mcux = -(-self.width // (8 * self.hmax))
        self.mcuy = -(-self.height // (8 * self.vmax))
        for c in self.comps:
            c.bw = self.mcux * c.h
            c.bh = self.mcuy * c.v
            c.blocks = [None] * (c.bw * c.bh)

    def _dqt(self, p):
        i = 0
        while i < len(p):
            pq, tq = p[i] >> 4, p[i] & 15
            if pq == 0:
                vals = list(p[i + 1:i + 65])
                i += 65
            elif pq == 1:
                vals = [int.from_bytes(p[i + 1 + 2 * k:i + 3 + 2 * k], "big") for k in range(64)]
                i += 129
            else:
                raise JpegError("a quantization table of precision %d" % pq)
            if len(vals) != 64 or not all(vals):
                raise JpegError("a broken quantization table")
            self.qt[tq] = vals
        if i != len(p):
            raise JpegError("a broken DQT segment")

    def _dht(self, p):
        i = 0
        while i < len(p):
            tc, th = p[i] >> 4, p[i] & 15
            if tc > 1 or i + 17 > len(p):
                raise JpegError("a broken DHT segment")
            bits = tuple(p[i + 1:i + 17])
            n = sum(bits)
            vals = tuple(p[i + 17:i + 17 + n])
            if len(vals) != n:
                raise JpegError("a broken DHT segment")
            self.ht[(tc, th)] = (bits, vals)
            i += 17 + n

    def _sos(self, p):
        n = p[0] if p else 0
        if len(p) != 4 + 2 * n:
            raise JpegError("a broken scan header")
        if n != len(self.comps):
            raise JpegError("a scan of %d of %d components: only one interleaved scan is read"
                            % (n, len(self.comps)))
        byid = {c.id: c for c in self.comps}
        self.scan = []
        for i in range(n):
            c = byid.get(p[1 + 2 * i])
            if c is None or c in self.scan:
                raise JpegError("a scan naming an unknown component")
            c.td, c.ta = p[2 + 2 * i] >> 4, p[2 + 2 * i] & 15
            self.scan.append(c)
        ss, se, ahal = p[1 + 2 * n], p[2 + 2 * n], p[3 + 2 * n]
        if (ss, se, ahal) != (0, 63, 0):
            raise JpegError("a scan that is not sequential")
        if n == 1 and (self.comps[0].h, self.comps[0].v) != (1, 1):
            raise JpegError("a single-component scan with sampling factors")
        for c in self.comps:
            if c.tq not in self.qt:
                raise JpegError("component %d names a missing quantization table" % c.id)
            if (0, c.td) not in self.ht or (1, c.ta) not in self.ht:
                raise JpegError("component %d names a missing Huffman table" % c.id)

    @staticmethod
    def _entropy(data, pos):
        """(position of the marker that ends the scan, [entropy-coded segments
        between restart markers, still byte-stuffed])."""
        segs = []
        start = pos
        expect = 0
        while True:
            j = data.find(b"\xff", pos)
            if j < 0 or j + 1 >= len(data):
                raise JpegError("the scan runs to the end of the file")
            nxt = data[j + 1]
            if nxt == 0x00:
                pos = j + 2
                continue
            if nxt == 0xFF:      # fill bytes before a marker
                k = j
                while k < len(data) and data[k] == 0xFF:
                    k += 1
                if k < len(data) and data[k] == 0x00:
                    raise JpegError("a stuffed byte after fill bytes")
                segs.append(data[start:j])
                return j, segs
            if 0xD0 <= nxt <= 0xD7:
                if nxt != 0xD0 + expect:
                    raise JpegError("restart markers out of order")
                expect = (expect + 1) % 8
                segs.append(data[start:j])
                start = pos = j + 2
                continue
            segs.append(data[start:j])
            return j, segs

    # -- the scan --

    def _mcu_ranges(self):
        n = self.mcux * self.mcuy
        if not self.restart:
            return [(0, n)]
        return [(a, min(n, a + self.restart)) for a in range(0, n, self.restart)]

    def _decode(self):
        ranges = self._mcu_ranges()
        if len(ranges) != len(self.segments):
            raise JpegError("%d restart intervals where the frame needs %d"
                            % (len(self.segments), len(ranges)))
        luts = {}
        for key, (bits, vals) in self.ht.items():
            luts[key] = _lut(bits, vals)
        layout = [(c, luts[(0, c.td)], luts[(1, c.ta)]) for c in self.scan]
        self.padding_ones = True
        mcux = self.mcux
        for (a, b), seg in zip(ranges, self.segments):
            raw = seg.replace(b"\xff\x00", b"\xff")
            nbits = len(raw) * 8
            bits = (bin(int.from_bytes(raw, "big"))[2:].zfill(nbits) if raw else "") + "1" * 32
            pos = 0
            preds = [0] * len(layout)
            for m in range(a, b):
                mx, my = m % mcux, m // mcux
                for ci, (c, dcl, acl) in enumerate(layout):
                    for i in range(c.v):
                        row = (my * c.v + i) * c.bw + mx * c.h
                        for j in range(c.h):
                            blk = [0] * 64
                            length, s = dcl[int(bits[pos:pos + 16], 2)]
                            if not length:
                                raise JpegError("a DC code no table has")
                            pos += length
                            if s:
                                v = int(bits[pos:pos + s], 2)
                                pos += s
                                if v < (1 << (s - 1)):
                                    v -= (1 << s) - 1
                                preds[ci] += v
                            blk[0] = preds[ci]
                            k = 1
                            while k < 64:
                                length, rs = acl[int(bits[pos:pos + 16], 2)]
                                if not length:
                                    raise JpegError("an AC code no table has")
                                pos += length
                                s = rs & 15
                                if not s:
                                    if rs == 0xF0:
                                        k += 16
                                        continue
                                    break
                                k += rs >> 4
                                if k > 63:
                                    raise JpegError("a block with more than 64 coefficients")
                                v = int(bits[pos:pos + s], 2)
                                pos += s
                                if v < (1 << (s - 1)):
                                    v -= (1 << s) - 1
                                blk[k] = v
                                k += 1
                            if k > 64:
                                raise JpegError("a block with more than 64 coefficients")
                            c.blocks[row + j] = blk
                if pos > nbits:
                    raise JpegError("the scan ends inside a block")
            rest = bits[pos:nbits]
            if len(rest) >= 8:
                raise JpegError("%d bits left over after a restart interval" % len(rest))
            if rest.count("0"):
                self.padding_ones = False

    def _events(self):
        """The scan as Huffman symbols: per restart interval, a list of
        (table key, symbol, extra bits)."""
        out = []
        mcux = self.mcux
        for a, b in self._mcu_ranges():
            ev = []
            preds = [0] * len(self.scan)
            for m in range(a, b):
                mx, my = m % mcux, m // mcux
                for ci, c in enumerate(self.scan):
                    dk, ak = (0, c.td), (1, c.ta)
                    for i in range(c.v):
                        row = (my * c.v + i) * c.bw + mx * c.h
                        for j in range(c.h):
                            blk = c.blocks[row + j]
                            d = blk[0] - preds[ci]
                            preds[ci] = blk[0]
                            s = _size(d)
                            if s > 11:
                                raise JpegError("a DC difference out of range")
                            ev.append((dk, s, _magnitude(d, s) if s else ""))
                            run = 0
                            for k in range(1, 64):
                                v = blk[k]
                                if not v:
                                    run += 1
                                    continue
                                while run > 15:
                                    ev.append((ak, 0xF0, ""))
                                    run -= 16
                                s = _size(v)
                                if s > 10:
                                    raise JpegError("an AC coefficient out of range")
                                ev.append((ak, (run << 4) | s, _magnitude(v, s)))
                                run = 0
                            if run:
                                ev.append((ak, 0x00, ""))
            out.append(ev)
        return out

    def encode(self):
        """The file's bytes from its blocks as they are now. The original
        Huffman tables are kept when they have a code for every symbol the
        blocks need; otherwise the tables the scan uses are made anew from
        the blocks (optimal_table): the old DHT segments go and one with the
        new tables stands right before the scan."""
        events = self._events()
        tables = dict(self.ht)
        used = {}
        for ev in events:
            for key, sym, _ in ev:
                used.setdefault(key, {})
                used[key][sym] = used[key].get(sym, 0) + 1
        renewed = any(key not in tables for key in used)
        if not renewed:
            codes = {key: _codes(*tables[key]) for key in used}
            renewed = any(sym not in codes[key] for key in used for sym in used[key])
        if renewed:
            for key in used:
                tables[key] = optimal_table(used[key])
            codes = {key: _codes(*tables[key]) for key in used}
        strs = {key: {sym: format(code, "0%db" % length) for sym, (code, length) in cs.items()}
                for key, cs in codes.items()}
        out = [b"\xff\xd8"]
        for marker, payload in self.head:
            if marker == 0xC4 and renewed:
                continue
            out.append(bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload)
        if renewed:
            body = b"".join(bytes([(tc << 4) | th]) + bytes(tables[(tc, th)][0]) + bytes(tables[(tc, th)][1])
                            for tc, th in sorted(used))
            out.append(b"\xff\xc4" + (len(body) + 2).to_bytes(2, "big") + body)
        out.append(b"\xff\xda" + (len(self.sos) + 2).to_bytes(2, "big") + self.sos)
        for i, ev in enumerate(events):
            if i:
                out.append(bytes([0xFF, 0xD0 + (i - 1) % 8]))
            bits = "".join(strs[key][sym] + extra for key, sym, extra in ev)
            bits += "1" * (-len(bits) % 8)
            raw = int(bits, 2).to_bytes(len(bits) // 8, "big") if bits else b""
            out.append(raw.replace(b"\xff", b"\xff\x00"))
        out.append(b"\xff\xd9")
        out.append(self.tail)
        self.tables_renewed = renewed
        return b"".join(out)

    # -- samples --

    def block_samples(self, ci, bx, by):
        """The 64 samples (row-major) of block (bx, by) of component ci."""
        c = self.comps[ci]
        return idct(c.blocks[by * c.bw + bx], self.qt[c.tq])

    def set_block_samples(self, ci, bx, by, samples):
        """Replace block (bx, by) of component ci by these 64 samples."""
        c = self.comps[ci]
        c.blocks[by * c.bw + bx] = fdct_quantize(samples, self.qt[c.tq])

    def adobe_transform(self):
        """The colour transform an Adobe APP14 segment names (0 none, 1 YCbCr),
        or None when the file has no such segment."""
        for marker, payload in self.head:
            if marker == 0xEE and payload[:5] == b"Adobe" and len(payload) >= 12:
                return payload[11]
        return None


# The example tables of the standard (Annex K.1), luminance and chrominance.
STD_LUMA = (16, 11, 12, 14, 12, 10, 16, 14, 13, 14, 18, 17, 16, 19, 24, 40,
            26, 24, 22, 22, 24, 49, 35, 37, 29, 40, 58, 51, 61, 60, 57, 51,
            56, 55, 64, 72, 92, 78, 64, 68, 87, 69, 55, 56, 80, 109, 81, 87,
            95, 98, 103, 104, 103, 62, 77, 113, 121, 112, 100, 120, 92, 101, 103, 99)
STD_CHROMA = (17, 18, 18, 24, 21, 24, 47, 26, 26, 47, 99, 66, 56, 66, 99, 99) + (99,) * 48


def make(width, height, planes, sampling=(1, 1), qtables=(STD_LUMA, STD_CHROMA), restart=0):
    """A baseline YCbCr JPEG of three planes of samples, each a list of rows at
    its component's resolution: Y full, Cb and Cr divided by sampling (1, 1 is
    4:4:4, 2, 2 is 4:2:0). qtables are in zigzag order; restart is the number
    of MCUs between restart markers, 0 for none. The suite's pictures are made
    so; the map's own tiles are only ever read and written back."""
    h, v = sampling
    j = Jpeg.__new__(Jpeg)
    j.width, j.height = width, height
    j.qt = {0: list(qtables[0]), 1: list(qtables[1])}
    j.ht = {}
    j.restart = restart
    j.comps = [Component(1, h, v, 0), Component(2, 1, 1, 1), Component(3, 1, 1, 1)]
    j.hmax, j.vmax = h, v
    j.mcux = -(-width // (8 * h))
    j.mcuy = -(-height // (8 * v))
    for ci, c in enumerate(j.comps):
        c.td = c.ta = 0 if ci == 0 else 1
        c.bw, c.bh = j.mcux * c.h, j.mcuy * c.v
        rows = planes[ci]
        ph, pw = len(rows), len(rows[0])
        c.blocks = []
        for by in range(c.bh):
            for bx in range(c.bw):
                samples = [rows[min(by * 8 + y, ph - 1)][min(bx * 8 + x, pw - 1)]
                           for y in range(8) for x in range(8)]
                c.blocks.append(fdct_quantize(samples, j.qt[c.tq]))
    j.scan = list(j.comps)
    sof = bytes([8]) + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes([3]) + b"".join(
        bytes([c.id, (c.h << 4) | c.v, c.tq]) for c in j.comps)
    dqt = b"".join(bytes([t]) + bytes(j.qt[t]) for t in (0, 1))
    j.head = [(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"), (0xDB, dqt), (0xC0, sof)]
    if restart:
        j.head.append((0xDD, restart.to_bytes(2, "big")))
    j.sos = bytes([3]) + b"".join(bytes([c.id, (c.td << 4) | c.ta]) for c in j.comps) + bytes([0, 63, 0])
    j.tail = b""
    return j.encode()
