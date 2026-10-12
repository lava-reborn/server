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

A place of ours (data/locations) put on the map gets a square the same way
round: data/map_cells.json "paint" names its cell and one colour of PALETTE,
and the square is painted on in the original's style (square, paint), its
blocks alone encoded anew -- unless the cell has a square already.

Before the squares, the war zones go (clear_zones; data/map_cells.json
"tint" and "zones"): round each camp across the river the makers painted a
red tint over a circle 245 pixels across and dark blue arrows into it, on
the camp's own tiles. The tint is taken back out of every pixel under it --
the photograph comes back as it was under the red laid over it, the line on
the rim measured where it is and taken off with it -- and the arrows (and
Донгола's seam, where its two tiles meet) are painted over with the
photograph from near by, a piece at a time; the squares and the letters
painted over them stay as they are. The squares are then found and painted
over on the picture without the zones.

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
import math
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
    is hidden; paint {(x, y): (colour, why)}: cells that get a square, a
    place of ours (data/locations) put on the map; zones [Zone]: the war
    zones painted round a place that is gone, a tinted circle and its arrows,
    and tint: how the circles are painted (clear_zones)."""

    def __init__(self, cells, captions, keep, paint=None, zones=(), tint=None):
        self.cells, self.captions, self.keep = cells, captions, keep
        self.paint = dict(paint or {})
        self.zones, self.tint = list(zones), tint

    def tiles(self):
        """The tiles a change can touch: a square's frame reaches one pixel
        past its cell; a zone's are listed with it."""
        out = set()
        for x, y in list(self.cells) + list(self.paint):
            for X in (CELL * x - 1, CELL * x + CELL):
                for Y in (CELL * y - 1, CELL * y + CELL):
                    out.add(tile_of(X, Y))
        for (x0, y0, x1, y1), _was, _why in self.captions:
            for X in (x0, x1):
                for Y in (y0, y1):
                    out.add(tile_of(X, Y))
        for z in self.zones:
            out |= set(z.tiles)
        return sorted(out)


class Tint:
    """How a war zone's circle is painted (data/map_cells.json "tint"): the
    colour rgb laid over the photograph at alpha, nothing of it within
    `clear` pixels of the centre, rising evenly to the whole alpha at `full`
    and so to the rim, where it ends over `edge` pixels."""

    def __init__(self, rgb, alpha, clear, full, edge):
        self.rgb, self.alpha, self.clear, self.full, self.edge = tuple(rgb), alpha, clear, full, edge
        r, g, b = self.rgb
        # the colour as the tiles' samples have it (JFIF), unrounded
        self.ycc = (0.299 * r + 0.587 * g + 0.114 * b,
                    128 - 0.168736 * r - 0.331264 * g + 0.5 * b,
                    128 + 0.5 * r - 0.418688 * g - 0.081312 * b)


class Zone:
    """One war zone (data/map_cells.json "zones"): the circle at centre with
    its radius (pixels of the full map), its own alpha when it has one, the
    arrows and seams drawn over it (polygons of the map's pixels, painted
    over whole), the boxes of letters painted over the arrows that stay, and
    the tiles it was painted on: nothing outside them changes."""

    def __init__(self, was, why, tiles, centre, radius, alpha=None, arrows=(), seams=(), letters=()):
        self.was, self.why = was, why
        self.tiles = sorted(tiles)
        self.centre, self.radius, self.alpha = tuple(centre), radius, alpha
        self.arrows = [[tuple(p) for p in poly] for poly in arrows]
        self.seams = [[tuple(p) for p in poly] for poly in seams]
        self.letters = [tuple(b) for b in letters]


def _zone(e, tint):
    """A Zone from its row of data/map_cells.json, refused when it is not one."""
    was = e.get("was")
    if not was or not e.get("why"):
        raise ValueError("map_cells: zone %r has no words or no why" % was)
    if tint is None:
        raise ValueError("map_cells: zone %r and no tint to take off" % was)
    tiles = e.get("tiles") or []
    if not tiles or not all(isinstance(n, int) and 0 <= n < ROW * ROW for n in tiles):
        raise ValueError("map_cells: zone %r: tiles %r" % (was, tiles))
    try:
        cx, cy = (float(v) for v in e["centre"])
        radius = float(e["radius"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("map_cells: zone %r has no centre or radius" % was)
    if not 8 <= radius <= 512 or tile_of(int(cx), int(cy)) not in tiles:
        raise ValueError("map_cells: zone %r: a circle of %r round %r, not in its tiles" % (was, radius, (cx, cy)))
    alpha = e.get("alpha")
    if alpha is not None and not 0 < alpha < 0.5:
        raise ValueError("map_cells: zone %r: alpha %r" % (was, alpha))
    boxes = [(n % ROW * TILE, n // ROW * TILE, n % ROW * TILE + TILE - 1, n // ROW * TILE + TILE - 1)
             for n in tiles]

    def on_tiles(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in boxes)
    polys = {}
    for kind in ("arrows", "seams"):
        polys[kind] = []
        for poly in e.get(kind, []):
            pts = [(float(p[0]), float(p[1])) for p in poly]
            if len(pts) < 3 or not all(on_tiles(x, y) for x, y in pts):
                raise ValueError("map_cells: zone %r: a polygon of %s off its tiles or of fewer than three"
                                 " points" % (was, kind))
            polys[kind].append(pts)
    letters = []
    for box in e.get("letters", []):
        x0, y0, x1, y1 = (int(v) for v in box)
        if (not (x0 <= x1 and y0 <= y1) or (x1 - x0 + 1) * (y1 - y0 + 1) > 64 * 64
                or not (on_tiles(x0, y0) and on_tiles(x1, y1))):
            raise ValueError("map_cells: zone %r: letters %r" % (was, box))
        letters.append((x0, y0, x1, y1))
    return Zone(was, e["why"], tiles, (cx, cy), radius, alpha, polys["arrows"], polys["seams"], letters)


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
    paint = {}
    for key, e in doc.get("paint", {}).items():
        if key.startswith("_"):
            continue
        c = _cell(key)
        if c in cells or c in keep:
            raise ValueError("map_cells: %s is both painted on and erased or kept" % key)
        if not isinstance(e, dict) or e.get("colour") not in PALETTE or not e.get("why"):
            raise ValueError("map_cells: painted %s needs a colour of %s and a why"
                             % (key, "/".join(sorted(PALETTE))))
        paint[c] = (e["colour"], e["why"])
    tint = None
    t = doc.get("tint")
    if t is not None:
        try:
            tint = Tint([int(v) for v in t["rgb"]], float(t["alpha"]), float(t["clear"]), float(t["full"]),
                        float(t["edge"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError("map_cells: the tint %r" % (t,))
        if (len(tint.rgb) != 3 or not all(0 <= v <= 255 for v in tint.rgb) or not 0 < tint.alpha < 0.5
                or not 0 <= tint.clear < tint.full or not 0 < tint.edge <= 8 or not t.get("why")):
            raise ValueError("map_cells: the tint %r" % (t,))
    zones = [_zone(e, tint) for e in doc.get("zones", [])]
    if len({z.was for z in zones}) != len(zones):
        raise ValueError("map_cells: two zones of one name")
    return Plan(cells, captions, keep, paint, zones, tint)


# --- the picture ---------------------------------------------------------------------

class Canvas:
    """The full-scale map as one picture, tiles read as they are needed.

    Values are the tiles' own samples, (Y, Cb, Cr), at full resolution (a
    subsampled component repeated over its footprint). put() records a
    changed pixel; lay() changes the picture itself, so that what is done
    after it starts from the new value (the war zones are taken off before
    the squares are found); encode() writes the tiles with changes, every
    changed block encoded anew and nothing else."""

    def __init__(self, read):
        self._read = read
        self._tiles = {}
        self._blocks = {}
        self._laid = {}
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
        """The picture's value at a pixel: the tile's, or what lay() put
        there; None off the map or where this client has no tile."""
        v = self._laid.get((X, Y))
        if v is not None:
            return v
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

    def lay(self, X, Y, value):
        self.put(X, Y, value)
        self._laid[(X, Y)] = self.edits[(X, Y)]

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


# --- painting on -----------------------------------------------------------------------------

# The dotted tan the squares are framed in.
OUTLINE = (177, 139, 102)


def ycc(p):
    """(Y, Cb, Cr) of an (R, G, B), as JFIF converts it: rgb() backwards."""
    r, g, b = p
    return (0.299 * r + 0.587 * g + 0.114 * b,
            128 - 0.168736 * r - 0.331264 * g + 0.5 * b,
            128 + 0.5 * r - 0.418688 * g - 0.081312 * b)


def square(x, y, colour):
    """{pixel: (R, G, B)} of a square in the original's way on cell (x, y):
    a 7 x 7 fill of the colour inside a 9 x 9 frame on the cell's corner,
    dotted -- three pixels of every four of it, the fourth the ground's."""
    X0, Y0 = CELL * x, CELL * y
    ring = ([(X0 + i, Y0) for i in range(9)] + [(X0 + 8, Y0 + j) for j in range(1, 9)]
            + [(X0 + i, Y0 + 8) for i in range(7, -1, -1)] + [(X0, Y0 + j) for j in range(7, 0, -1)])
    out = {p: OUTLINE for k, p in enumerate(ring) if k % 4}
    for j in range(1, 8):
        for i in range(1, 8):
            out[(X0 + i, Y0 + j)] = colour
    return out


def paint(canvas, plan):
    """Paint a square on each cell of plan.paint, in its colour of PALETTE:
    the place of ours on that cell, as the original's places are drawn
    (Squares). A cell whose picture has a square already is left alone, and
    so is one this client has no tile for. Report lines."""
    squares = Squares(canvas)
    report = []
    for c, (colour, _why) in sorted(plan.paint.items()):
        n = tile_of(CELL * c[0], CELL * c[1])
        if canvas.tile(n) is None:
            report.append("%d,%d: no tile %s in this client, left alone" % (c[0], c[1], tile_path(n)))
            continue
        if squares.at(*c) is not None:
            report.append("%d,%d: a square is painted there already, left alone" % c)
            continue
        px = 0
        for (X, Y), rgb_ in sorted(square(c[0], c[1], PALETTE[colour]).items()):
            if canvas.original(X, Y) is not None:
                canvas.put(X, Y, ycc(rgb_))
                px += 1
        report.append("%d,%d: %s square painted on, %d pixels" % (c[0], c[1], colour, px))
    return report


# --- the war zones -----------------------------------------------------------------------

# A war zone's arrows (and Донгола's seam) are painted over a piece at a
# time, about PIECE pixels each, from one end to the other, each piece with
# a patch from no further than MARK_REACH pixels, or MARK_REACH_FAR after
# that, blended into the ground and the pieces done before it.
PIECE = 360
MARK_REACH = 32
MARK_REACH_FAR = 64
# Of the MARK_TRY patches that fit a piece best, the first whose blend bends
# it by no more than MARK_BEND (Y, Cb, Cr) over the piece is taken (bend).
MARK_TRY = 6
MARK_BEND = (48, 16, 16)
# When none does, the one that goes past the ground's bounds least, and of
# those bends least, held to the bounds, if no more than MARK_PAST of its
# pixels go past them.
MARK_PAST = 0.1


def polygon_pixels(poly):
    """The pixels (X, Y) whose point lies inside the polygon or on its edge
    ([(x, y)] of the map's pixels, a pixel's point being its own
    coordinates), by rows: an edge crosses a row y when it starts at or
    above it and ends below it."""
    out = set()
    n = len(poly)
    ys = [p[1] for p in poly]
    for Y in range(int(math.floor(min(ys))), int(math.ceil(max(ys))) + 1):
        xs = []
        for i in range(n):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
            if y1 == y2 == Y:
                # an edge along the row is all edge
                for X in range(int(math.ceil(min(x1, x2))), int(math.floor(max(x1, x2))) + 1):
                    out.add((X, Y))
            elif min(y1, y2) <= Y < max(y1, y2):
                xs.append(x1 + (Y - y1) * (x2 - x1) / (y2 - y1))
            elif Y == max(y1, y2):
                # the lower end of an edge is its own point
                x = x1 if y1 == Y else x2
                if x == int(x):
                    out.add((int(x), Y))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            for X in range(int(math.ceil(a - 1e-9)), int(math.floor(b + 1e-9)) + 1):
                out.add((X, Y))
    return out


def _smoothstep(e0, e1, x):
    t = (x - e0) / (e1 - e0)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def zone_alpha(tint, zone, r):
    """How much of the tint lies on a pixel r pixels from the zone's centre."""
    alpha = zone.alpha if zone.alpha is not None else tint.alpha
    ramp = (r - tint.clear) / (tint.full - tint.clear)
    ramp = 0.0 if ramp < 0 else 1.0 if ramp > 1 else ramp
    half = tint.edge / 2
    return alpha * ramp * (1 - _smoothstep(zone.radius - half, zone.radius + half, r))


# The line on a circle's rim: what is left on the rim once the tint is off is
# a thin line, yellowish (blue down by up to 8) and darker towards the lower
# right, as if lit from the upper left, up to 25 levels of luma there. It is
# taken off where it is. Across the rim, out to RIM_FIX either way in steps
# of RIM_BIN, each RIM_ARC of the rim is measured (the middle of the pixels of
# RIM_SPAN arcs each way) against the ground RIM_REF pixels inside and
# outside the rim: what it differs by there is the line's profile across the
# rim. Whether that is a line is read from a peak fitted to it (RIM_WIDTH
# pixels to either side of its middle, the middle and the peak's height in
# each of Y, Cb, Cr those that fit best): a line within RIM_MOST (Y, Cb, Cr)
# is the circle's. On the side it is lit from (the left and the top) the line
# is a light one, up to 40 levels of luma above the ground and greener (Cr
# down by up to 15): one within RIM_LIGHT is the circle's too where the
# ground on either side of the rim is alike, within RIM_ALIKE (the owner's
# Донгола, 2026-10-12: a pale green arc was left on its west rim). Any other
# line is the photograph's (a rock's edge, a shore) and stays. The circle's
# line is taken off as measured, its profile itself (held to the bounds of
# its kind), the line being wider and flatter than the peak that tells it;
# over the last RIM_TAPER pixels to RIM_FIX less and less of it.
RIM_FIX = 2.5
RIM_TAPER = 0.75
RIM_REF = (3.0, 6.0)
RIM_BIN = 0.5
RIM_ARC = 3.0
RIM_SPAN = 5
RIM_WIDTH = 1.25
RIM_MOST = ((-40, 8), (-16, 6), (-12, 14))
RIM_LIGHT = ((8, 45), (-16, 6), (-18, 4))
RIM_ALIKE = (24, 6, 8)


def _median(values, i):
    s = sorted(v[i] for v in values)
    n = len(s)
    return (s[(n - 1) // 2] + s[n // 2]) / 2


def _peak(d, middle):
    w = 1 - abs(d - middle) / RIM_WIDTH
    return w if w > 0 else 0.0


def _profile_at(profile, d):
    """A profile [(d, [Y, Cb, Cr])], in order of d, at d: straight between
    its points, as at its end past it."""
    if d <= profile[0][0]:
        return profile[0][1]
    for (d0, e0), (d1, e1) in zip(profile, profile[1:]):
        if d <= d1:
            t = (d - d0) / (d1 - d0)
            return [a + t * (b - a) for a, b in zip(e0, e1)]
    return profile[-1][1]


def rim_fix(canvas, zone, inside, skip):
    """{pixel: value}: the pixels within RIM_FIX of the zone's rim, on the
    zone's tiles (inside), with the line on it taken off, measured on the
    canvas as it is (the tint off); pixels of skip neither count nor change.
    The ground RIM_REF away from the rim is measured on the tiles round the
    zone's too: where a circle comes within a few pixels of its tile's edge
    (Вади-Хальфа's west and north, Абри's east) the ground outside it lies on
    the next tile, unpainted, and the line along there is measured by it."""
    cx, cy = zone.centre
    R = zone.radius
    far = RIM_REF[1]
    nb = max(8, int(round(2 * math.pi * R / RIM_ARC)))
    nd = int(round(2 * far / RIM_BIN))
    bins = {}
    pix = []
    for Y in range(int(math.floor(cy - R - far)), int(math.ceil(cy + R + far)) + 1):
        for X in range(int(math.floor(cx - R - far)), int(math.ceil(cx + R + far)) + 1):
            if (X, Y) in skip:
                continue
            dx, dy = X + 0.5 - cx, Y + 0.5 - cy
            d = math.hypot(dx, dy) - R
            if not -far <= d < far:
                continue
            on = tile_of(X, Y) in inside
            if not on and abs(d) <= RIM_REF[0]:
                # the line was painted on the zone's tiles alone
                continue
            v = canvas.original(X, Y)
            if v is None:
                continue
            ab = int((math.atan2(dy, dx) + math.pi) / (2 * math.pi) * nb) % nb
            db = min(nd - 1, int((d + far) / RIM_BIN))
            bins.setdefault((ab, db), []).append(v)
            if on and abs(d) < RIM_FIX:
                pix.append((X, Y, ab, d, v))
    centre = [db * RIM_BIN - far + RIM_BIN / 2 for db in range(nd)]
    inner = [db for db in range(nd) if centre[db] < -RIM_REF[0]]
    outer = [db for db in range(nd) if centre[db] > RIM_REF[0]]
    line = [db for db in range(nd) if abs(centre[db]) < RIM_FIX]
    mid_in = sum(centre[db] for db in inner) / len(inner)
    mid_out = sum(centre[db] for db in outer) / len(outer)
    middles = [k * 0.25 for k in range(-6, 5)]
    est = {}
    for ab in range(nb):
        arcs = [(ab + k) % nb for k in range(-RIM_SPAN, RIM_SPAN + 1)]

        def gather(dbs):
            return [v for a_ in arcs for db_ in dbs for v in bins.get((a_, db_), ())]
        inn, out = gather(inner), gather(outer)
        if len(inn) < 20 or len(out) < 20:
            continue
        ri = [_median(inn, i) for i in range(3)]
        ro = [_median(out, i) for i in range(3)]
        diffs = []
        for db in line:
            vals = gather([db])
            if len(vals) < 5:
                continue
            t = (centre[db] - mid_in) / (mid_out - mid_in)
            diffs.append((centre[db], [_median(vals, i) - (ri[i] + t * (ro[i] - ri[i])) for i in range(3)]))
        if len(diffs) < len(line) * 2 // 3:
            continue
        fit = None
        for middle in middles:
            w = [_peak(d, middle) for d, _e in diffs]
            ww = sum(x * x for x in w)
            if not ww:
                continue
            height = [sum(x * e[i] for x, (_d, e) in zip(w, diffs)) / ww for i in range(3)]
            err = sum((e[i] - height[i] * x) ** 2 for x, (_d, e) in zip(w, diffs) for i in range(3))
            if fit is None or err < fit[0]:
                fit = (err, middle, height)
        if fit is None:
            continue
        if all(lo <= h <= hi for h, (lo, hi) in zip(fit[2], RIM_MOST)):
            kind = RIM_MOST
        elif (all(lo <= h <= hi for h, (lo, hi) in zip(fit[2], RIM_LIGHT))
              and all(abs(ri[i] - ro[i]) <= RIM_ALIKE[i] for i in range(3))):
            kind = RIM_LIGHT
        else:
            continue
        est[ab] = [(d, [min(max(e[i], min(lo, 0)), max(hi, 0)) for i, (lo, hi) in enumerate(kind)])
                   for d, e in diffs]
    out_ = {}
    for X, Y, ab, d, v in pix:
        profile = est.get(ab)
        if profile is not None:
            w = min(1.0, (RIM_FIX - abs(d)) / RIM_TAPER)
            e = _profile_at(profile, d)
            out_[(X, Y)] = [v[i] - e[i] * w for i in range(3)]
    return out_


# A letter painted over an arrow is a pixel darker than the middle of its box
# by LETTER_DARK; it and the pixels round it stay.
LETTER_DARK = 40


def letters_pixels(canvas, box):
    """The letters painted in a box of the map and the pixels round them:
    those darker than the middle of the box by LETTER_DARK, and their
    neighbours."""
    x0, y0, x1, y1 = box
    vals = [((X, Y), canvas.original(X, Y)) for X in range(x0, x1 + 1) for Y in range(y0, y1 + 1)]
    vals = [(p, v[0]) for p, v in vals if v is not None]
    if not vals:
        return set()
    mid = _median([(y,) for _p, y in vals], 0)
    dark = [p for p, y in vals if y < mid - LETTER_DARK]
    return {(X + dx, Y + dy) for X, Y in dark for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def painted_square(canvas, sq):
    """Whether a square found is paint: a fill of one colour has the
    palette's very colour (the ground's dark rocks pass for a dark red
    square by their colour alone, and a square under a zone is painted over
    its tint, the ground around it under it)."""
    X0, Y0, kind = sq
    if len(kind) != 1:
        return True
    px = [rgb(canvas.original(X0 + i, Y0 + j)) for j in range(2, 7) for i in range(2, 7)]
    mean = [sum(p[c] for p in px) / len(px) for c in range(3)]
    return max(abs(m - c) for m, c in zip(mean, PALETTE[kind[0]])) <= 12


def _pieces(pixels):
    """The pixels in pieces of about PIECE, each group that touches cut
    across its longest way, from one end to the other."""
    out = []
    for g in _groups(pixels):
        n = len(g)
        mx = sum(p[0] for p in g) / n
        my = sum(p[1] for p in g) / n
        sxx = sum((p[0] - mx) ** 2 for p in g)
        syy = sum((p[1] - my) ** 2 for p in g)
        sxy = sum((p[0] - mx) * (p[1] - my) for p in g)
        angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
        ux, uy = math.cos(angle), math.sin(angle)
        order = sorted(g, key=lambda p: ((p[0] - mx) * ux + (p[1] - my) * uy, p))
        k = max(1, int(round(n / PIECE)))
        size = n / k
        out.extend(order[int(round(i * size)):int(round((i + 1) * size))] for i in range(k))
    return out


def bend(canvas, values, offset):
    """How far the blend of a patch bends it to meet the ground round it:
    the range over the piece of what solve() added to the patch, in each of
    Y, Cb and Cr, as a share of MARK_BEND (the largest of the three). A patch
    bent more than that is the ground of one side smeared over the other
    (dark rock lifted into grey over sand)."""
    dx, dy = offset
    lo = [None] * 3
    hi = [None] * 3
    for (X, Y), v in values.items():
        g = canvas.original(X + dx, Y + dy)
        for i in range(3):
            d = v[i] - g[i]
            if lo[i] is None or d < lo[i]:
                lo[i] = d
            if hi[i] is None or d > hi[i]:
                hi[i] = d
    return max((hi[i] - lo[i]) / MARK_BEND[i] for i in range(3)) if values else 0.0


def paint_marks(canvas, marks, every_mark, protect, squares, laid):
    """Paint the pixels of marks over (canvas.lay, each added to laid) a
    piece at a time (_pieces), the pieces before it ground already, each from
    the patch of photograph near by that fits the ground round it best
    (find_patch, solve): the first that stays within the ground's bounds and
    whose blend bends it little (bend); when none does, the one that goes
    past the bounds least, no more than MARK_PAST of its pixels, and of
    those the one bent least (by a rock's edge the blend lifts the rock
    towards the sand: the less, the less of a smear), held to the bounds;
    when none comes that near, smooth from its edge. The other marks not yet
    painted, the squares and the letters are no ground (apart) and no patch
    is taken from them, nor from any square near (bad). Counter of patch,
    bent, smooth."""
    how = collections.Counter()
    left = set(marks)
    for piece in _pieces(marks):
        left -= set(piece)
        apart = left | (every_mark - marks) | protect
        bad = every_mark | protect
        bounds = None
        tried = set()
        done = None
        least = None
        for reach in (MARK_REACH, MARK_REACH_FAR):
            xs = [p[0] for p in piece]
            ys = [p[1] for p in piece]
            for x in range((min(xs) - reach - 4) // CELL - 1, (max(xs) + reach + 4) // CELL + 2):
                for y in range((min(ys) - reach - 4) // CELL - 1, (max(ys) + reach + 4) // CELL + 2):
                    if canvas.tile(tile_of(CELL * x, CELL * y)) is not None:
                        sq = squares.at(x, y)
                        if sq is not None:
                            bad = bad | frame_pixels(sq)
            if bounds is None:
                # the pieces painted already are ground the piece meets
                bounds = ground_bounds(canvas, piece, apart | (bad - every_mark))
            for offset in find_patch(canvas, piece, bad, apart, reach, bounds, best=MARK_TRY):
                if offset in tried:
                    continue
                tried.add(offset)
                values = solve(canvas, piece, apart, offset)
                off = outside(values.values(), bounds)
                if off > MARK_PAST * len(piece):
                    continue
                b_ = bend(canvas, values, offset)
                if not off and b_ <= 1:
                    done = values
                    break
                if least is None or (off, b_) < least[0]:
                    least = ((off, b_), offset, values)
            if done:
                break
        if done:
            how["patch"] += 1
        elif least is not None:
            # held to the ground's bounds
            done = least[2] if bounds is None else {
                p: [lo if v < lo else hi if v > hi else v for v, (lo, hi) in zip(val, bounds)]
                for p, val in least[2].items()}
            how["bent"] += 1
        else:
            done = solve(canvas, piece, apart, None)
            how["smooth"] += 1
        for p, v in done.items():
            canvas.lay(p[0], p[1], v)
            laid.add(p)
    return how


def clear_zones(canvas, plan):
    """Take each war zone off the picture (canvas.lay, so that the squares
    and captions are found and painted over on the picture without it).
    (pixels changed, report lines).

    The circle is a tint of plan.tint's colour laid over the photograph at an
    alpha rising from the middle to the rim (zone_alpha): every pixel under
    it, outside the squares painted over it, is the photograph again,
    (value - alpha * colour) / (1 - alpha), and the line on its rim is taken
    off where it is (rim_fix). The arrows and the seams are paint: their
    polygons, less the squares and the letters painted over them
    (letters_pixels), are painted over with the photograph's texture from
    near by as a square is, a piece at a time (paint_marks). Nothing outside
    the zone's tiles changes."""
    tint = plan.tint
    laid = set()
    report = []
    marks_all = {}
    for z in plan.zones:
        inside = set(z.tiles)
        px = set()
        for poly in z.arrows + z.seams:
            px |= {p for p in polygon_pixels(poly) if tile_of(*p) in inside}
        marks_all[z.was] = px
    every_mark = set().union(*marks_all.values()) if marks_all else set()
    for z in plan.zones:
        missing = [n for n in z.tiles if canvas.tile(n) is None]
        if missing:
            report.append("zone %s: no tile %s in this client, left alone"
                          % (z.was, ", ".join(tile_path(n) for n in missing)))
            continue
        inside = set(z.tiles)
        cx, cy = z.centre
        reach = z.radius + tint.edge / 2 + 1
        marks = marks_all[z.was]
        xs = [p[0] for p in marks] + [cx - reach, cx + reach]
        ys = [p[1] for p in marks] + [cy - reach, cy + reach]
        # the squares painted over the zone stay as they are
        squares = Squares(canvas)
        protect = set()
        kept = 0
        for y in range(int(min(ys)) // CELL - 1, int(max(ys)) // CELL + 2):
            for x in range(int(min(xs)) // CELL - 1, int(max(xs)) // CELL + 2):
                if canvas.tile(tile_of(CELL * x, CELL * y)) is None:
                    continue
                sq = squares.at(x, y)
                if sq is not None and painted_square(canvas, sq):
                    protect |= frame_pixels(sq)
                    kept += 1
        # and so do the letters painted over its arrows
        for box in z.letters:
            protect |= letters_pixels(canvas, box)
        marks = marks - protect
        # the tint
        tinted = 0
        T = tint.ycc
        for Y in range(int(math.floor(cy - reach)), int(math.ceil(cy + reach)) + 1):
            for X in range(int(math.floor(cx - reach)), int(math.ceil(cx + reach)) + 1):
                if tile_of(X, Y) not in inside or (X, Y) in protect or (X, Y) in marks:
                    continue
                a = zone_alpha(tint, z, math.hypot(X + 0.5 - cx, Y + 0.5 - cy))
                if not a:
                    continue
                v = canvas.original(X, Y)
                new = [(v[i] - a * T[i]) / (1 - a) for i in range(3)]
                if any(abs(n - o) >= 0.5 for n, o in zip(new, v)):
                    canvas.lay(X, Y, new)
                    laid.add((X, Y))
                    tinted += 1
        # the line on the rim; the captions that go are no ground to measure it by
        skip = protect | every_mark
        for (x0, y0, x1, y1), _was, _why in plan.captions:
            skip |= {(X, Y) for X in range(x0 - 1, x1 + 2) for Y in range(y0 - 1, y1 + 2)}
        lined = 0
        for p, v in sorted(rim_fix(canvas, z, inside, skip).items()):
            old_v = canvas.original(*p)
            if any(abs(n - o) >= 0.5 for n, o in zip(v, old_v)):
                canvas.lay(p[0], p[1], v)
                laid.add(p)
                lined += 1
        report.append("zone %s: the circle round %.1f,%.1f of radius %.1f, %d pixels of it under its tint,"
                      " %d on its rim's line; %d squares over it left as they are"
                      % (z.was, cx, cy, z.radius, tinted, lined, kept))
        # the arrows and the seams
        how = paint_marks(canvas, marks, every_mark, protect, squares, laid)
        report.append("zone %s: %d arrows and %d seams, %d pixels painted over in %d pieces (%d from a patch of"
                      " photograph, %d of them bent by the blend; %d smooth from their edge)"
                      % (z.was, len(z.arrows), len(z.seams), len(marks), sum(how.values()),
                         how["patch"] + how["bent"], how["bent"], how["smooth"]))
    return laid, report


def apply(read, plan=None):
    """({path: new bytes}, report lines): the tiles with the plan's war zones
    taken off, its squares and captions painted over, and its new squares
    painted on. read(path) gives a tile of the original (a path under res/)
    or None when this client has none."""
    plan = load() if plan is None else plan
    canvas = Canvas(read)
    _laid, report = clear_zones(canvas, plan)
    _found, _kept, _region, more = erase(canvas, plan)
    report += more
    report += paint(canvas, plan)
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
    made once, on the first request for a tile a change can touch (or ahead
    of it, warm()), from the data as it stood then (a change to it is served
    after a restart, as the server's other tables are). Painting the whole
    map takes half a minute with the war zones: a request that comes while
    it is made waits for it."""

    def __init__(self, root, plan=None):
        self.root = root
        self._plan = plan
        self._paths = None
        self._tiles = None
        self._lock = threading.Lock()

    def _plan_paths(self):
        if self._paths is None:
            if self._plan is None:
                self._plan = load()
            self._paths = {tile_path(n) for n in self._plan.tiles()}
        return self._paths

    def _make(self):
        if self._tiles is None:
            try:
                self._plan_paths()
                self._tiles, report = apply(reader(self.root), self._plan)
                print("  map squares: %s" % "; ".join(report), flush=True)
            except (ValueError, OSError) as e:
                # the player's own picture rather than none
                print("  map squares NOT painted over: %s" % e, flush=True)
                self._tiles = {}

    def warm(self):
        """Start making the tiles in the background now, so that the first
        player to open the map does not wait for it."""
        def run():
            with self._lock:
                self._make()
        threading.Thread(target=run, name="map-tiles", daemon=True).start()

    def get(self, rel):
        """The bytes to serve for res/<rel> in place of the file's own, or
        None to serve the file as it is."""
        if not rel.startswith("globalmap/full/"):
            return None
        with self._lock:
            if rel not in self._plan_paths():
                return None
            self._make()
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
        boxes = [(CELL * x - 32, CELL * y - 32, CELL * x + 40, CELL * y + 40)
                 for x, y in sorted(plan.cells) + sorted(plan.paint)]
        boxes += [(x0 - 24, y0 - 24, x1 + 24, y1 + 24) for (x0, y0, x1, y1), _, _ in plan.captions]
        boxes += [(int(z.centre[0] - z.radius) - 16, int(z.centre[1] - z.radius) - 16,
                   int(z.centre[0] + z.radius) + 16, int(z.centre[1] + z.radius) + 16) for z in plan.zones]
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
                fh.write(preview(before, after, box, 6 if box[2] - box[0] <= 160 else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
