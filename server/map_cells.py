"""The squares the global map paints on its cells, taken off where a place is gone.

The full-scale map is a photograph cut into 273 JPEG tiles,
res/globalmap/full/<ty*256+tx>.jpg, 256 x 256 pixels each, one cell 8 x 8
pixels. The game's makers painted every place into that picture: a 7 x 7
square of the place's colour on its cell (green for a town's places, dark red
for a fight, a hatch for a work site, blue with «!» for an airfield...) inside
a 1-pixel dotted outline, and a few captions in letters. No data row and no
frame of the server draws them, so hiding a place's name (data/map_labels.json)
leaves its square where it was -- the owner saw them after the cut of
Вади-Хальфа on 2026-10-09.

What goes, then, is drawn over: every cell of data/retired.json "cells" (a
retired place's cell is wasteland, and its square goes with it the day it is
listed there), the cells and captions data/map_cells.json adds, each with its
why. On each such cell the square is found in the picture (Squares.at), and
its pixels -- the fill and the outline, less any pixel a kept neighbour's own
square covers -- are painted over with the photograph's texture from a spot
near by, blended into what surrounds them (find_patch, solve), a spot taken
only if the pixels it paints stay within the darkest and the brightest of
the ground around (ground_bounds: Донгола's nearest fitting spot held the
river's black line); where no spot near does, the pixels are painted smooth
from what surrounds them. Only the 8 x 8
blocks of the JPEG those pixels fall in are encoded anew (jpeg_blocks): every
other block of every tile keeps its coefficients exactly, so nothing else on
the map can move.

Where it is laid on:

  * client/build.py, which puts the edited tiles into every client release
    (the generated layer), so the launcher installs them as they are;
  * bootstrap_http, for a local run over the owner's own res/.

Launchers before the self-updating one (2026-10-06) show the player's own
files and cannot be given these: they keep the squares until the player
installs the current launcher.

    python3 server/map_cells.py --res RES [--out DIR] [--preview DIR]

prints what would be erased, writes the edited tiles into DIR and before /
after pictures (PNG, magnified) into the preview folder.
"""
import collections
import json
import os
import struct
import sys
import threading
import zlib

import jpeg_blocks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "map_cells.json")
RETIRED = os.path.join(ROOT, "data", "retired.json")

TILE = 256           # pixels on a side of a tile
CELL = 8             # pixels on a side of a cell
ROW = 256            # tiles per row in the tile numbering, n = ty * ROW + tx

# The colours the squares are painted in (RGB). The outline around them is
# dotted tan, (177, 139, 102), or on a few black; neither is looked for: the
# fill is what tells a square from the photograph.
PALETTE = {
    "green": (12, 104, 2),       # a town's places
    "red": (120, 24, 30),        # fights, bandit camps, arenas; with white, a clan base
    "blue": (16, 16, 245),       # with a white «!», an airfield
    "black": (0, 0, 0),          # black markets; with «!», butchers; with a colour, a hatch
    "white": (255, 255, 255),    # capturable stores
    "orange": (235, 170, 12),    # with black, the hatch of a work site
    "yellow": (250, 250, 10),    # with black, the other hatch
    "tan": (204, 181, 110),      # quest spots, yards, digs
}
# How close a pixel must be to count as that colour (largest channel
# difference). Tan and black are the photograph's own sand and lake too, so
# they are held closer; what tells such a square from sand is that its frame
# is not of its colour and its fill is flat (Squares.at).
NEAR = {"tan": 20, "black": 30}
NEAR_DEFAULT = 40

SEARCH = 48          # how far (pixels) a patch of photograph is looked for
SEARCH_FAR = 112     # and, when nothing near will do, how far after that
# How far (sample levels, each of Y, Cb, Cr) a painted pixel may go past the
# darkest and the brightest of the ground around it (GROUND pixels deep, less
# any square or caption): a patch that would bring in what is not there -- a
# river's black line, a rock -- is not taken.
GROUND = 3
MARGIN = 12


def tile_of(X, Y):
    return (Y // TILE) * ROW + X // TILE


def tile_path(n):
    return "globalmap/full/%d.jpg" % n


def _cell(key):
    x, y = key.split(",")
    return int(x), int(y)


# --- what goes ---------------------------------------------------------------------

class Plan:
    """cells {(x, y): why}: the cells whose square goes -- data/retired.json's
    and data/map_cells.json's; captions [((x0, y0, x1, y1), was, why)], a
    box of the full map's pixels each (inclusive), a caption of two lines
    being two; keep {(x, y): why}: cells whose square stays though their name
    is hidden."""

    def __init__(self, cells, captions, keep):
        self.cells, self.captions, self.keep = cells, captions, keep

    def tiles(self):
        """The tiles a change can touch: a square's frame reaches one pixel
        past its cell."""
        out = set()
        for x, y in self.cells:
            for X in (CELL * x - 1, CELL * x + CELL):
                for Y in (CELL * y - 1, CELL * y + CELL):
                    out.add(tile_of(X, Y))
        for (x0, y0, x1, y1), _was, _why in self.captions:
            for X in (x0, x1):
                for Y in (y0, y1):
                    out.add(tile_of(X, Y))
        return sorted(out)


def load(path=PATH, retired=RETIRED):
    with open(retired, encoding="utf-8") as fh:
        ret = json.load(fh)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        doc = {}
    cells = {}
    for key, place in ret.get("cells", {}).items():
        if key.startswith("_"):
            continue
        cells[_cell(key)] = "data/retired.json: the retired place %s stood here" % place
    for key, why in doc.get("cells", {}).items():
        if key.startswith("_"):
            continue
        c = _cell(key)
        if c in cells:
            raise ValueError("map_cells: %s is data/retired.json's already" % key)
        if not why:
            raise ValueError("map_cells: %s has no why" % key)
        cells[c] = why
    captions = []
    for e in doc.get("captions", []):
        if not e.get("why") or not e.get("was"):
            raise ValueError("map_cells: caption %r has no words or no why" % e.get("was"))
        if not e.get("boxes"):
            raise ValueError("map_cells: caption %r has no boxes" % e["was"])
        for box in e["boxes"]:
            x0, y0, x1, y1 = (int(v) for v in box)
            if not (x0 <= x1 and y0 <= y1) or (x1 - x0 + 1) * (y1 - y0 + 1) > 64 * 64:
                raise ValueError("map_cells: caption box %r" % (box,))
            captions.append(((x0, y0, x1, y1), e["was"], e["why"]))
    keep = {}
    for key, why in doc.get("keep", {}).items():
        if key.startswith("_"):
            continue
        c = _cell(key)
        if c in cells:
            raise ValueError("map_cells: %s is both erased and kept" % key)
        if not why:
            raise ValueError("map_cells: kept %s has no why" % key)
        keep[c] = why
    return Plan(cells, captions, keep)


# --- the picture ---------------------------------------------------------------------

class Canvas:
    """The full-scale map as one picture, tiles read as they are needed.

    Values are the tiles' own samples, (Y, Cb, Cr), at full resolution (a
    subsampled component repeated over its footprint). put() records a
    changed pixel; encode() writes the tiles with changes, every changed
    block encoded anew and nothing else."""

    def __init__(self, read):
        self._read = read
        self._tiles = {}
        self._blocks = {}
        self.edits = {}

    def tile(self, n):
        if n not in self._tiles:
            data = self._read(tile_path(n)) if 0 <= n < ROW * ROW else None
            j = None
            if data is not None:
                j = jpeg_blocks.Jpeg(data)
                if len(j.comps) != 3 or j.adobe_transform() == 0:
                    raise jpeg_blocks.JpegError("%s: not a YCbCr picture" % tile_path(n))
                if (j.width, j.height) != (TILE, TILE):
                    raise jpeg_blocks.JpegError("%s: %dx%d, not a tile" % (tile_path(n), j.width, j.height))
            self._tiles[n] = j
        return self._tiles[n]

    def original(self, X, Y):
        if X < 0 or Y < 0 or X >= TILE * ROW:
            return None
        n = tile_of(X, Y)
        j = self.tile(n)
        if j is None:
            return None
        x, y = X % TILE, Y % TILE
        out = []
        for ci, c in enumerate(j.comps):
            sx, sy = x * c.h // j.hmax, y * c.v // j.vmax
            key = (n, ci, sx >> 3, sy >> 3)
            s = self._blocks.get(key)
            if s is None:
                s = self._blocks[key] = j.block_samples(ci, sx >> 3, sy >> 3)
            out.append(s[(sy & 7) * 8 + (sx & 7)])
        return out

    def ycc(self, X, Y):
        e = self.edits.get((X, Y))
        return e if e is not None else self.original(X, Y)

    def put(self, X, Y, value):
        self.edits[(X, Y)] = [0 if v < 0 else 255 if v > 255 else int(round(v)) for v in value]

    def encode(self):
        """({tile: bytes}, {tile: number of blocks encoded anew})."""
        by_tile = collections.defaultdict(list)
        for (X, Y), v in self.edits.items():
            by_tile[tile_of(X, Y)].append((X % TILE, Y % TILE, v))
        out, blocks = {}, {}
        for n, pixels in sorted(by_tile.items()):
            j = self.tile(n)
            changed = 0
            for ci, c in enumerate(j.comps):
                fx, fy = j.hmax // c.h, j.vmax // c.v      # pixels per sample
                sums = {}
                for x, y, v in pixels:
                    k = (x // fx, y // fy)
                    s = sums.setdefault(k, [0, 0])
                    s[0] += v[ci]
                    s[1] += 1
                per_block = collections.defaultdict(dict)
                for (sx, sy), (total, count) in sums.items():
                    orig = self._blocks.get((n, ci, sx >> 3, sy >> 3)) or j.block_samples(ci, sx >> 3, sy >> 3)
                    old = orig[(sy & 7) * 8 + (sx & 7)]
                    rest = fx * fy - count            # pixels of the footprint left as they were
                    per_block[(sx >> 3, sy >> 3)][(sy & 7) * 8 + (sx & 7)] = \
                        int(round((total + rest * old) / (fx * fy)))
                for (bx, by), vals in per_block.items():
                    orig = self._blocks.get((n, ci, bx, by)) or j.block_samples(ci, bx, by)
                    k = by * c.bw + bx
                    coef = _encode_block(orig, vals, j.qt[c.tq], c.blocks[k])
                    if coef != c.blocks[k]:
                        c.blocks[k] = coef
                        changed += 1
            out[n] = j.encode()
            blocks[n] = changed
        return out, blocks


def _encode_block(orig, vals, qt, coef0):
    """The coefficients of a block whose samples at the positions of vals
    become those values and stay as they were everywhere else. Quantizing
    spreads the change over the block, so the samples meant to stay are fed
    the error back a few times, and the coefficients that leave them closest
    to what they were are kept. A block whose samples all stay keeps its
    own coefficients, coef0."""
    if all(orig[i] == v for i, v in vals.items()):
        return coef0
    target = list(orig)
    for i, v in vals.items():
        target[i] = v
    keep = [i for i in range(64) if i not in vals]
    best = None
    for _ in range(8):
        coef = jpeg_blocks.fdct_quantize(target, qt)
        rec = jpeg_blocks.idct(coef, qt)
        err = max([abs(orig[i] - rec[i]) for i in keep] or [0])
        if best is None or err < best[0]:
            best = (err, coef)
        if not err:
            break
        for i in keep:
            target[i] += orig[i] - rec[i]
    return best[1]


def rgb(v):
    """(R, G, B) of a (Y, Cb, Cr) sample, as JFIF converts it."""
    y, cb, cr = v
    r = y + 1.402 * (cr - 128)
    g = y - 0.344136 * (cb - 128) - 0.714136 * (cr - 128)
    b = y + 1.772 * (cb - 128)
    return tuple(0 if t < 0 else 255 if t > 255 else int(round(t)) for t in (r, g, b))


# --- the squares -------------------------------------------------------------------------

class Squares:
    """Finds the squares painted on cells, by their fill.

    A square is a 7 x 7 fill inside a 9 x 9 frame that starts on its cell's
    corner or one pixel off it either way. The fill is one colour of the
    palette (40 of its 49 pixels), or one with white (a «!», a clan base's
    centre), or black with orange or yellow (a hatch); and its frame is not of
    that colour (no more than 10 of its 32 pixels: the gaps of a dotted
    outline show the ground). A tan or a black fill must also be flat, as
    paint is and sand or the lake are not."""

    def __init__(self, canvas):
        self.canvas = canvas
        self._near = {}
        self._found = {}

    def colour(self, X, Y):
        k = (X, Y)
        if k not in self._near:
            v = self.canvas.original(X, Y)
            best = None
            if v is not None:
                p = rgb(v)
                for name, c in PALETTE.items():
                    d = max(abs(p[0] - c[0]), abs(p[1] - c[1]), abs(p[2] - c[2]))
                    if d <= NEAR.get(name, NEAR_DEFAULT) and (best is None or d < best[1]):
                        best = (name, d)
            self._near[k] = best and best[0]
        return self._near[k]

    @staticmethod
    def kind(count):
        """The fill's colours from a count of a 7 x 7's colours, or None."""
        top = [t for t in count.most_common() if t[0] is not None]
        if not top:
            return None
        c, n = top[0]
        white = count.get("white", 0)
        if c in ("blue", "black", "red") and white >= 4 and n >= 22 and n + white >= 40:
            return (c, "white")
        if n >= 40:
            return (c,)
        black = count.get("black", 0)
        for h in ("orange", "yellow"):
            if black >= 12 and count.get(h, 0) >= 12 and black + count[h] >= 38:
                return ("black", h)
        return None

    def at(self, x, y):
        """(X0, Y0, colours) of the square on cell (x, y) -- X0, Y0 the top
        left pixel of its 9 x 9 frame -- or None."""
        k = (x, y)
        if k in self._found:
            return self._found[k]
        best = None
        # every 7 x 7 the frame can hold takes in the cell's middle 5 x 5, so a
        # fill of 38 needs 14 coloured pixels there
        middle = sum(1 for j in range(2, 7) for i in range(2, 7)
                     if self.colour(CELL * x + i, CELL * y + j) is not None)
        if middle < 14:
            self._found[k] = None
            return None
        for oy in (0, -1, 1):
            for ox in (0, -1, 1):
                X0, Y0 = CELL * x + ox, CELL * y + oy
                inner = [(X0 + i, Y0 + j) for j in range(1, 8) for i in range(1, 8)]
                count = collections.Counter(self.colour(*p) for p in inner)
                kind = self.kind(count)
                if not kind:
                    continue
                frame = ([(X0 + i, Y0) for i in range(9)] + [(X0 + i, Y0 + 8) for i in range(9)]
                         + [(X0, Y0 + j) for j in range(1, 8)] + [(X0 + 8, Y0 + j) for j in range(1, 8)])
                same = sum(1 for p in frame if self.colour(*p) in kind)
                if same > 10:
                    continue
                if kind in (("tan",), ("black",)):
                    # sand and the lake have these colours too, with a grain
                    # a painted fill has not
                    ys = [self.canvas.original(*p)[0] for p in inner if self.colour(*p) == kind[0]]
                    mean = sum(ys) / len(ys)
                    if sum(abs(v - mean) for v in ys) / len(ys) > 3.5:
                        continue
                fill = sum(count[c] for c in kind)
                score = (fill - same, (ox, oy) == (0, 0))
                if best is None or score > best[0]:
                    best = (score, (X0, Y0, kind))
        self._found[k] = best and best[1]
        return self._found[k]


def frame_pixels(square):
    X0, Y0, _ = square
    return {(X0 + i, Y0 + j) for j in range(9) for i in range(9)}


# --- painting over -------------------------------------------------------------------------

N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _groups(pixels):
    """The pixels in groups that touch (8 ways)."""
    left = set(pixels)
    out = []
    while left:
        start = left.pop()
        g = [start]
        todo = [start]
        while todo:
            X, Y = todo.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (X + dx, Y + dy)
                    if q in left:
                        left.remove(q)
                        g.append(q)
                        todo.append(q)
        out.append(sorted(g))
    out.sort()
    return out


def _ring(region, width):
    """The pixels within `width` steps (8 ways) outside the region."""
    reg = set(region)
    out = set()
    for X, Y in region:
        for dx in range(-width, width + 1):
            for dy in range(-width, width + 1):
                q = (X + dx, Y + dy)
                if q not in reg:
                    out.add(q)
    return out


class Window:
    """A rectangle of the canvas, x0..x1 by y0..y1 inclusive, read once: the
    samples of each pixel and a summed table of the pixels a patch may not
    take (bad, or off the map), so that whether a box of it is clear is four
    look-ups."""

    def __init__(self, canvas, box, bad):
        x0, y0, x1, y1 = box
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        w = self.w = x1 - x0 + 1
        h = y1 - y0 + 1
        self.val = []
        sat = [0] * ((w + 1) * (h + 1))
        for j in range(h):
            run = 0
            for i in range(w):
                v = canvas.original(x0 + i, y0 + j)
                self.val.append(v)
                run += 1 if v is None or (x0 + i, y0 + j) in bad else 0
                sat[(j + 1) * (w + 1) + i + 1] = sat[j * (w + 1) + i + 1] + run
        self.sat = sat

    def get(self, X, Y):
        return self.val[(Y - self.y0) * self.w + (X - self.x0)]

    def clear(self, x0, y0, x1, y1):
        if x0 < self.x0 or y0 < self.y0 or x1 > self.x1 or y1 > self.y1:
            return False
        W = self.w + 1
        i0, j0, i1, j1 = x0 - self.x0, y0 - self.y0, x1 - self.x0 + 1, y1 - self.y0 + 1
        s = self.sat
        return s[j1 * W + i1] - s[j0 * W + i1] - s[j1 * W + i0] + s[j0 * W + i0] == 0


def ground_bounds(canvas, region, bad):
    """[(lo, hi)] for Y, Cb and Cr: what a pixel painted in the region may
    be, the ground GROUND pixels around it (less what is bad: a square, a
    caption, a region) from its darkest less MARGIN to its brightest plus
    MARGIN; None where no ground is left around."""
    ground = [canvas.original(*p) for p in sorted(_ring(region, GROUND)) if p not in bad]
    ground = [v for v in ground if v is not None]
    if not ground:
        return None
    return [(min(v[i] for v in ground) - MARGIN, max(v[i] for v in ground) + MARGIN) for i in range(3)]


def outside(values, bounds):
    """How many of the values (Y, Cb, Cr each) fall outside the bounds."""
    if bounds is None:
        return 0
    return sum(1 for v in values if any(not lo <= v[i] <= hi for i, (lo, hi) in enumerate(bounds)))


def _cost(win, target, inner, spread_t, dx, dy, bounds=None):
    """How badly a patch moved by (dx, dy) fits: the spread of its
    differences with the region's surroundings (a constant difference costs
    little, Poisson blending takes it away), how far its own texture is from
    theirs, and a little for distance. None if the patch, moved by its mean
    difference as blending moves it, would have a pixel outside the
    ground's bounds."""
    n = len(target)
    sums = [0.0, 0.0, 0.0]
    sq = [0.0, 0.0, 0.0]
    for (X, Y), t in target:
        g = win.get(X + dx, Y + dy)
        for i in range(3):
            d = t[i] - g[i]
            sums[i] += d
            sq[i] += d * d
    cost = 0.0
    for i in range(3):
        m = sums[i] / n
        cost += sq[i] / n - m * m + 0.25 * m * m
    if bounds is not None:
        shift = [s / n for s in sums]
        for X, Y in inner:
            g = win.get(X + dx, Y + dy)
            for i, (lo, hi) in enumerate(bounds):
                if not lo <= g[i] + shift[i] <= hi:
                    return None
    ys = [win.get(X + dx, Y + dy)[0] for X, Y in inner]
    mean_i = sum(ys) / len(ys)
    spread_i = sum(abs(y - mean_i) for y in ys) / len(ys)
    # a patch busier than the ground around brings in what is not there (a
    # crack, a rock); a calmer one only looks a little smooth
    busy = spread_i - spread_t
    return cost + (8.0 if busy > 0 else 2.0) * busy * busy + 0.02 * (dx * dx + dy * dy) ** 0.5


def find_patch(canvas, region, bad, apart, reach, bounds=None, best=6):
    """The offsets of the patches of photograph that best fit the region's
    surroundings (the two pixels around it, less those apart: a kept square,
    another region), the best first, at most `best` of them, from no further
    than reach pixels: none of its pixels, nor the two around them, bad or
    off the map, not over the region itself, and none that would paint a
    pixel outside the ground's bounds (ground_bounds). [] if there is no
    such patch."""
    reg = set(region)
    ring = _ring(region, 2)
    xs = [p[0] for p in region]
    ys = [p[1] for p in region]
    bx0, by0, bx1, by1 = min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2
    win = Window(canvas, (bx0 - reach, by0 - reach, bx1 + reach, by1 + reach), bad)
    target = [(p, win.get(*p)) for p in sorted(ring) if p not in apart]
    target = [(p, v) for p, v in target if v is not None]
    if not target:
        return []
    # the ground's own texture, from a little further out: right next to the
    # region lies a caption's halo or a square's shadow, and no other square
    # or caption is ground (a cluster of squares around would read as a
    # busy ground and bring in a busy patch)
    around = [win.get(*p) for p in sorted(_ring(region, 6) - ring) if p not in bad]
    around = [v[0] for v in around if v is not None] or [v[0] for _, v in target]
    mean_t = sum(around) / len(around)
    spread_t = sum(abs(y - mean_t) for y in around) / len(around)
    inner = sorted(reg)
    coarse_target, coarse_inner = target[::2], inner[::3]
    w, h = bx1 - bx0 + 1, by1 - by0 + 1
    found = []
    for dy in range(-reach, reach + 1, 2):
        for dx in range(-reach, reach + 1, 2):
            if abs(dx) < w and abs(dy) < h:
                continue        # the patch would lie over the region itself
            if not win.clear(bx0 + dx, by0 + dy, bx1 + dx, by1 + dy):
                continue
            c = _cost(win, coarse_target, coarse_inner, spread_t, dx, dy, bounds)
            if c is not None:
                found.append((c, dx, dy))
    found.sort()
    fine = {}
    for _, cx, cy in found[:6]:
        for dy in (cy - 1, cy, cy + 1):
            for dx in (cx - 1, cx, cx + 1):
                if (dx, dy) in fine or (abs(dx) < w and abs(dy) < h):
                    continue
                if not win.clear(bx0 + dx, by0 + dy, bx1 + dx, by1 + dy):
                    continue
                fine[(dx, dy)] = _cost(win, target, inner, spread_t, dx, dy, bounds)
    ranked = sorted((c, dy, dx) for (dx, dy), c in fine.items() if c is not None)
    return [(dx, dy) for _, dy, dx in ranked[:best]]


def solve(canvas, region, apart, donor_offset):
    """{pixel: (Y, Cb, Cr)}: the region painted over with the patch at
    donor_offset, its seams taken away: the region is solved for the patch's
    own differences, meeting what surrounds it on every photograph pixel
    around (Poisson blending); a pixel apart (a kept square) does not pull on
    it. With no donor_offset the region is solved for no differences at all,
    smooth from what surrounds it (a membrane), which never goes past the
    darkest and the brightest of what it meets."""
    dx, dy = donor_offset or (0, 0)
    order = sorted(region)
    index = {p: i for i, p in enumerate(order)}
    zero = (0.0, 0.0, 0.0)

    def patch(X, Y):
        return zero if donor_offset is None else canvas.original(X + dx, Y + dy)
    donor = [patch(X, Y) for X, Y in order]
    links = []
    edge = []
    for k, (X, Y) in enumerate(order):
        inside, fixed = [], [0.0, 0.0, 0.0]
        count = 0
        for ddx, ddy in N4:
            q = (X + ddx, Y + ddy)
            gq = patch(*q)
            if q in index:
                inside.append((index[q], [donor[k][i] - gq[i] for i in range(3)]))
                count += 1
            elif q not in apart and canvas.original(*q) is not None:
                tq = canvas.original(*q)
                edge.append(tq)
                for i in range(3):
                    fixed[i] += tq[i] + donor[k][i] - gq[i]
                count += 1
        links.append((inside, fixed, count))
    if donor_offset is None:
        # a membrane starts from the mean of what it meets (with nothing
        # around to meet, the pixels stay as they are)
        f = ([[sum(v[i] for v in edge) / len(edge) for i in range(3)] for _ in order] if edge
             else [list(canvas.original(*p)) for p in order])
    else:
        f = [list(v) for v in donor]
    for _ in range(1000):
        change = 0.0
        for k, (inside, fixed, count) in enumerate(links):
            if not count:
                continue
            fk = f[k]
            for i in range(3):
                s = fixed[i]
                for j, g in inside:
                    s += f[j][i] + g[i]
                new = fk[i] + 1.85 * (s / count - fk[i])
                if abs(new - fk[i]) > change:
                    change = abs(new - fk[i])
                fk[i] = new
        if change < 0.01:
            break
    return dict(zip(order, f))


def erase(canvas, plan):
    """Paint over every square and caption of the plan. (found {cell:
    square}, kept {cell: square}, the pixels painted, report lines)."""
    squares = Squares(canvas)
    report = []
    found = {}
    for c in sorted(plan.cells):
        n = tile_of(CELL * c[0], CELL * c[1])
        if canvas.tile(n) is None:
            report.append("%d,%d: no tile %s in this client, left alone" % (c[0], c[1], tile_path(n)))
            continue
        sq = squares.at(*c)
        if sq is None:
            report.append("%d,%d: no square painted on the cell" % c)
            continue
        found[c] = sq
    # the squares that stay, around those that go and under the captions
    near = {(x + dx, y + dy) for x, y in found for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    for (x0, y0, x1, y1), _was, _why in plan.captions:
        near |= {(x, y) for x in range(x0 // CELL - 1, x1 // CELL + 2)
                 for y in range(y0 // CELL - 1, y1 // CELL + 2)}
    kept = {}
    for n in sorted(near - set(plan.cells)):
        if canvas.tile(tile_of(CELL * n[0], CELL * n[1])) is None:
            continue
        sq = squares.at(*n)
        if sq is not None:
            kept[n] = sq
    protect = set()
    for sq in kept.values():
        protect |= frame_pixels(sq)
    region = set()
    for c, sq in sorted(found.items()):
        px = {p for p in frame_pixels(sq) - protect if canvas.original(*p) is not None}
        region |= px
        report.append("%d,%d: %s square at %+d,%+d, %d pixels"
                      % (c[0], c[1], "+".join(sq[2]), sq[0] - CELL * c[0], sq[1] - CELL * c[1], len(px)))
    captions = set()
    for (x0, y0, x1, y1), was, _why in plan.captions:
        px = {(X, Y) for X in range(x0, x1 + 1) for Y in range(y0, y1 + 1)
              if canvas.original(X, Y) is not None} - protect
        if not px:
            report.append("caption %r at %d,%d..%d,%d: no tile in this client, left alone"
                          % (was, x0, y0, x1, y1))
            continue
        region |= px
        captions |= {(X, Y) for X in range(x0 - 2, x1 + 3) for Y in range(y0 - 2, y1 + 3)}
        report.append("caption %r at %d,%d..%d,%d: %d pixels" % (was, x0, y0, x1, y1, len(px)))
    painted = set()
    for g in _groups(region):
        # nothing is copied from a square, a caption or what is being
        # erased; a kept square or another region is no surrounding to match
        apart = region | protect
        bad = apart | captions
        xs = [p[0] for p in g]
        ys = [p[1] for p in g]
        bounds = None
        tried = set()
        done = None
        for reach in (SEARCH, SEARCH_FAR):
            x0, y0 = (min(xs) - reach - 4) // CELL, (min(ys) - reach - 4) // CELL
            x1, y1 = (max(xs) + reach + 4) // CELL, (max(ys) + reach + 4) // CELL
            for x in range(x0 - 1, x1 + 2):
                for y in range(y0 - 1, y1 + 2):
                    if canvas.tile(tile_of(CELL * x, CELL * y)) is not None:
                        sq = squares.at(x, y)
                        if sq is not None:
                            bad = bad | frame_pixels(sq)
            if reach == SEARCH:
                bounds = ground_bounds(canvas, g, bad)
            # the patch that fits best and stays within the ground's bounds,
            # the patch itself and the blend of it both
            for offset in find_patch(canvas, g, bad, apart, reach, bounds):
                if offset in tried:
                    continue
                tried.add(offset)
                values = solve(canvas, g, apart, offset)
                if not outside(values.values(), bounds):
                    done = offset, values
                    break
            if done:
                break
        if done:
            offset, values = done
            how = "from %+d,%+d" % offset
        else:
            # no patch of photograph near enough fits: smooth from the edge
            values = solve(canvas, g, apart, None)
            how = "smooth from its edge, no patch of photograph fitting"
            off = outside(values.values(), bounds)
            if off:
                how += ", %d pixels past the ground's bounds" % off
        for p, v in values.items():
            canvas.put(p[0], p[1], v)
        painted |= set(g)
        report.append("  %d pixels from %d,%d painted %s" % (len(g), g[0][0], g[0][1], how))
    return found, kept, painted, report


def apply(read, plan=None):
    """({path: new bytes}, report lines): the tiles with the plan's squares
    and captions painted over. read(path) gives a tile of the original (a
    path under res/) or None when this client has none."""
    plan = load() if plan is None else plan
    canvas = Canvas(read)
    _found, _kept, _region, report = erase(canvas, plan)
    out, blocks = canvas.encode()
    for n in sorted(out):
        report.append("%s: %d blocks encoded anew" % (tile_path(n), blocks[n]))
    return {tile_path(n): b for n, b in out.items()}, report


def reader(root):
    """read(path) over a res/ folder on disk: the file's bytes, or None."""
    def read(path):
        p = os.path.join(root, *path.split("/"))
        if not os.path.isfile(p):
            return None
        with open(p, "rb") as fh:
            return fh.read()
    return read


class Served:
    """The edited tiles for a local run (bootstrap_http), over its own res/:
    made once, on the first request for a tile a change can touch, from the
    data as it stood then (a change to it is served after a restart, as the
    server's other tables are)."""

    def __init__(self, root, plan=None):
        self.root = root
        self._plan = plan
        self._paths = None
        self._tiles = None
        self._lock = threading.Lock()

    def get(self, rel):
        """The bytes to serve for res/<rel> in place of the file's own, or
        None to serve the file as it is."""
        if not rel.startswith("globalmap/full/"):
            return None
        with self._lock:
            if self._paths is None:
                if self._plan is None:
                    self._plan = load()
                self._paths = {tile_path(n) for n in self._plan.tiles()}
            if rel not in self._paths:
                return None
            if self._tiles is None:
                try:
                    self._tiles, report = apply(reader(self.root), self._plan)
                    print("  map squares: %s" % "; ".join(report), flush=True)
                except (ValueError, OSError) as e:
                    # the player's own picture rather than none
                    print("  map squares NOT painted over: %s" % e, flush=True)
                    self._tiles = {}
        return self._tiles.get(rel)


# --- pictures for a person ------------------------------------------------------------

def png(width, height, rows):
    """A PNG of RGB rows (lists of (r, g, b))."""
    raw = b"".join(b"\x00" + bytes(v for p in row for v in p) for row in rows)

    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def preview(before, after, box, scale=6):
    """A PNG of a box of the map, before beside after, magnified; cells are
    marked by a dot on their corner."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0 + 1, y1 - y0 + 1
    rows = []
    for Y in range(y0, y1 + 1):
        line = []
        for canvas in (before, after):
            for X in range(x0, x1 + 1):
                v = canvas.ycc(X, Y)
                p = rgb(v) if v is not None else (255, 0, 255)
                line.extend([p] * scale)
            line.extend([(255, 255, 255)] * scale)
        for k in range(scale):
            row = list(line)
            if Y % CELL == 0 and k == 0:
                for side in range(2):
                    for X in range(x0, x1 + 1):
                        if X % CELL == 0:
                            row[side * (w + 1) * scale + (X - x0) * scale] = (255, 0, 255)
            rows.append(row)
    return png((2 * w + 2) * scale, h * scale, rows)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--res", required=True, help="the client's res/ folder")
    ap.add_argument("--out", help="write the edited tiles here")
    ap.add_argument("--preview", help="write before/after PNGs here")
    a = ap.parse_args(argv)
    read = reader(a.res)
    plan = load()
    tiles, report = apply(read, plan)
    print("\n".join(report))
    if a.out:
        for path, data in tiles.items():
            dest = os.path.join(a.out, *path.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        before = Canvas(read)
        after = Canvas(lambda p: tiles.get(p) or read(p))
        # one picture per neighbourhood: boxes around what goes, merged while
        # they overlap
        boxes = [(CELL * x - 32, CELL * y - 32, CELL * x + 40, CELL * y + 40) for x, y in sorted(plan.cells)]
        boxes += [(x0 - 24, y0 - 24, x1 + 24, y1 + 24) for (x0, y0, x1, y1), _, _ in plan.captions]
        merged = True
        while merged:
            merged = False
            for i in range(len(boxes)):
                for k in range(i + 1, len(boxes)):
                    a_, b_ = boxes[i], boxes[k]
                    if a_[0] <= b_[2] and b_[0] <= a_[2] and a_[1] <= b_[3] and b_[1] <= a_[3]:
                        boxes[i] = (min(a_[0], b_[0]), min(a_[1], b_[1]), max(a_[2], b_[2]), max(a_[3], b_[3]))
                        del boxes[k]
                        merged = True
                        break
                if merged:
                    break
        for i, box in enumerate(sorted(boxes)):
            with open(os.path.join(a.preview, "%d_%d_%d.png" % (i, box[0] // CELL, box[1] // CELL)), "wb") as fh:
                fh.write(preview(before, after, box))
    return 0


if __name__ == "__main__":
    sys.exit(main())
