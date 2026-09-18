"""Rebuild data/map_terrain.json: which cells of the global map can be walked.

The server's own passability table is gone. What survives is the map the
client draws: res/globalmap/full, 273 JPEG tiles of 256x256 pixels, one tile
per 32x32 cells, so every cell of the world is a block of exactly 8x8 pixels
(the tile a cell belongs to is gx//32, gy//32 and its file is ty*256 + tx;
data/build_settlements.py leans on the same formula and all 262 settlements
land on a tile that exists). 256 of those tiles cover the playable rectangle
exactly, with none missing; the other 17 hang below and east of it.

The artwork is a satellite photograph of the Nubian desert, and it is read
here the way a photo-interpreter would read one:

  roughness   mountains are shaded relief -- lit slopes against black
              shadow -- so the luminance inside a cell swings wildly, while
              sand, gravel and lava plains are smooth at 8 pixels. The
              measure is the mean absolute deviation of luminance inside the
              cell, smoothed over the 3x3 block of cells around it so a
              range comes out as a range rather than as speckle.
  colour      the photograph is uniformly warm, red over green over blue.
              Where blue beats red the cell is water: that finds Lake Nasser
              and nothing else.

The map tool drew on top of the photograph -- settlement icons, hatched
markers and captions -- and a black icon square would otherwise read as the
roughest cell on the map. Those pixels are recognised by being what the
photograph never is (grey, black, green-dominant, dark red, pure yellow);
a cell more than a quarter painted over is not measured at all but filled in
from the ring of cells around it.

Two things then override the picture, because they are better evidence than
it is: the 262 cells of data/settlements.json and the 414 cells that carry a
tooltip in res/database/locations.xml are cells players stood on, so they are
passable whatever the photograph says. Each one that had to be forced is
counted in the report.

Of the two the server now believes the water only. LAVA had no terrain layer
at all: a cell was walled because the location standing on it had no outzone
that way, and every wasteland template has all four (recon/analysis/borders.md
§3, §9). The "#" column stays in the table as what the photograph says, and
data/borders.json says where the rock actually stood.

Nothing here is the original table, and the report says where the result is
least trustworthy. Run with a Python that has Pillow:

    python3 data/build_terrain.py

Writes data/map_terrain.json and data/map_terrain_report.md.
"""
import collections
import json
import os
import re
import sys

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world                                                     # noqa: E402

TILE = 32                 # cells along a tile
PX = 8                    # pixels along a cell
# The rectangle the photograph is read over. It was travel.MAP_X/MAP_Y once;
# it is written out here because the world has since grown east and south
# (world.MAP_X) while the reading has not, and because the table is a picture
# of a fixed piece of ground that should not move when the world's bounds are
# argued about. Of what comes out of it the server now believes the water
# only -- see world.BLOCKED and recon/analysis/borders.md §9.
GX0, GX1 = 5833, 6305
GY0, GY1 = 1600, 2110
W = GX1 - GX0 + 1
H = GY1 - GY0 + 1

# --- the rules, and the numbers they turn on -------------------------------
# ROUGH is the one that matters. Raising it opens the mountains up; lowering
# it walls the world off into pockets. It was first set to 20, the loosest
# value that still sealed the Nubian valley -- but the player who remembers
# the game says the valley has a footpath in, so that constraint was never
# real. At 20 only 2 of the valley's 16 settlements could be walked to and
# 17 settlements in all were cut off: roughness reads a boulder field as a
# mountain, and the valley is full of them. 26 is the tightest value at
# which every settlement of the valley connects and all but one on the whole
# map do, with 2.5% of the ground still standing as rock.
ROUGH = 26.0              # smoothed mean absolute deviation of luminance
WATER = 2.0               # mean blue over mean red, in levels
DRAWN = 0.25              # a cell painted over more than this is not measured
DARK = 120.0              # passable, but lava field or wadi rather than sand
SPECKS = 2                # a rock cell needs this many rock neighbours

PASSABLE = ".,"
SAND, PLAIN, ROCK, WATER_C = ".", ",", "#", "~"

START = (6268, 1819)      # the Nubian settlement, where players begin
NUBIA = (6250, 6285, 1810, 1845)   # the valley, as the player who walked it
#                                    remembers it, with a margin


# --- reading the tiles ------------------------------------------------------
def tiles():
    """(tx, ty) -> path, for the tiles that cover the playable rectangle."""
    root = os.path.join(world.RES, "globalmap", "full")
    out = {}
    for name in os.listdir(root):
        if not name.endswith(".jpg"):
            continue
        i = int(name[:-4])
        tx, ty = i % 256, i // 256
        if GX0 // TILE <= tx <= GX1 // TILE and GY0 // TILE <= ty <= GY1 // TILE:
            out[(tx, ty)] = os.path.join(root, name)
    return out


def _drawn(im):
    """A mask of the pixels the map tool painted over the photograph.

    Grey, black, green-dominant, dark red and pure yellow: five things the
    Landsat picture of a desert never contains and every icon and caption on
    the map does.
    """
    r, g, b = im.split()
    hi = ImageChops.lighter(ImageChops.lighter(r, g), b)
    lo = ImageChops.darker(ImageChops.darker(r, g), b)
    chroma = ImageChops.subtract(hi, lo)
    limit = hi.point(lambda v: max(12, int(0.16 * v)))
    hit = lambda im_: im_.point(lambda v: 255 if v else 0)
    grey = hit(ImageChops.subtract(limit, chroma))         # chroma < limit
    black = hi.point(lambda v: 255 if v < 45 else 0)
    green = ImageChops.subtract(r, g).point(lambda v: 255 if v == 0 else 0)
    red = hit(ImageChops.subtract(r.point(lambda v: int(0.55 * v)), g))
    yellow = hit(ImageChops.subtract(r.point(lambda v: int(0.15 * v)), b))
    out = ImageChops.lighter(ImageChops.lighter(grey, black), green)
    return ImageChops.lighter(out, ImageChops.lighter(red, yellow))


def features():
    """Four numbers per cell of the playable rectangle, as flat rows.

    lum    mean luminance, 0..255
    rough  mean absolute deviation of luminance inside the cell
    blue   mean blue minus mean red: positive only on water
    drawn  fraction of the cell painted over, 0..1
    """
    lum = [None] * (W * H)
    rough = [None] * (W * H)
    blue = [None] * (W * H)
    drawn = [None] * (W * H)
    found = tiles()
    for (tx, ty), path in sorted(found.items()):
        im = Image.open(path).convert("RGB")
        if im.size != (TILE * PX, TILE * PX):
            raise SystemExit("%s is %dx%d, not %dx%d"
                             % (path, im.size[0], im.size[1], TILE * PX, TILE * PX))
        grey = im.convert("L")
        mean = grey.resize((TILE, TILE), Image.BOX)
        flat = mean.resize(im.size, Image.NEAREST)
        mad = ImageChops.difference(grey, flat).resize((TILE, TILE), Image.BOX)
        small = im.resize((TILE, TILE), Image.BOX)
        paint = _drawn(im).resize((TILE, TILE), Image.BOX)
        m, d, p, s = (list(mean.getdata()), list(mad.getdata()),
                      list(paint.getdata()), list(small.getdata()))
        for cy in range(TILE):
            gy = ty * TILE + cy
            if not GY0 <= gy <= GY1:
                continue
            for cx in range(TILE):
                gx = tx * TILE + cx
                if not GX0 <= gx <= GX1:
                    continue
                i = cy * TILE + cx
                j = (gy - GY0) * W + (gx - GX0)
                lum[j] = float(m[i])
                rough[j] = float(d[i])
                blue[j] = float(s[i][2] - s[i][0])
                drawn[j] = p[i] / 255.0
    missing = sum(1 for v in lum if v is None)
    if missing:
        raise SystemExit("%d cells of the map have no tile behind them" % missing)
    return dict(lum=lum, rough=rough, blue=blue, drawn=drawn, tiles=len(found))


# --- turning the numbers into ground ----------------------------------------
def _box(values, known, k=1):
    """Mean of each (2k+1) square, counting only the cells marked known."""
    out = [0.0] * (W * H)
    for y in range(H):
        y0, y1 = max(0, y - k), min(H - 1, y + k)
        for x in range(W):
            x0, x1 = max(0, x - k), min(W - 1, x + k)
            s = n = 0
            for yy in range(y0, y1 + 1):
                base = yy * W
                for xx in range(x0, x1 + 1):
                    if known[base + xx]:
                        s += values[base + xx]
                        n += 1
            out[y * W + x] = s / n if n else 0.0
    return out


def _fill(values, known):
    """Give the painted-over cells the mean of the nearest measured ring."""
    out = list(values)
    have = list(known)
    todo = [i for i in range(W * H) if not have[i]]
    k = 1
    while todo and k <= 8:
        left, done = [], []
        for i in todo:
            y, x = divmod(i, W)
            s = n = 0
            for yy in range(max(0, y - k), min(H - 1, y + k) + 1):
                base = yy * W
                for xx in range(max(0, x - k), min(W - 1, x + k) + 1):
                    if have[base + xx]:
                        s += out[base + xx]
                        n += 1
            if n:
                out[i] = s / n
                done.append(i)
            else:
                left.append(i)
        for i in done:                  # only after the whole ring, or the
            have[i] = True              # fill would creep along the scan
        todo = left
        k += 1
    for i in todo:                      # nothing measured anywhere near: rock
        out[i] = 255.0
    return out


def evidence():
    """Cells a player is known to have stood on: settlements and tooltips."""
    cells = set(world.settlements())
    txt = open(os.path.join(world.RES, "database", "locations.xml"), "rb").read()
    try:
        txt = txt.decode("utf-8")
    except UnicodeDecodeError:
        txt = txt.decode("cp1251", "replace")
    hints = [(int(m.group(1)), int(m.group(2)))
             for m in re.finditer(r'<location x="(\d+)" y="(\d+)"', txt)]
    return cells, hints


def classify(f, rough=ROUGH, water=WATER, drawn=DRAWN, dark=DARK, specks=SPECKS):
    """The terrain, one character per cell, as H strings of W characters."""
    wet = [f["blue"][i] > water for i in range(W * H)]
    known = [f["drawn"][i] <= drawn and not wet[i] for i in range(W * H)]
    rough_f = _fill(f["rough"], known)
    lum_f = _fill(f["lum"], known)
    smooth = _box(rough_f, [True] * (W * H), 1)
    rock = [smooth[i] > rough for i in range(W * H)]
    # A single rough cell in the middle of a plain is a bush or a rock, not a
    # mountain; a wall of them is a range. Drop the ones standing alone.
    lone = []
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if not rock[i]:
                continue
            n = 0
            for yy in range(max(0, y - 1), min(H - 1, y + 1) + 1):
                for xx in range(max(0, x - 1), min(W - 1, x + 1) + 1):
                    if (yy != y or xx != x) and rock[yy * W + xx]:
                        n += 1
            if n < specks:
                lone.append(i)
    for i in lone:
        rock[i] = False
    grid = []
    for i in range(W * H):
        if wet[i]:
            grid.append(WATER_C)
        elif rock[i]:
            grid.append(ROCK)
        elif lum_f[i] < dark:
            grid.append(PLAIN)
        else:
            grid.append(SAND)
    return grid


def force(grid, cells):
    """Open the cells we know players stood on. Returns the ones it had to."""
    forced = []
    for gx, gy in sorted(cells):
        if not GX0 <= gx <= GX1 or not GY0 <= gy <= GY1:
            continue
        i = (gy - GY0) * W + (gx - GX0)
        if grid[i] not in PASSABLE:
            forced.append(((gx, gy), grid[i]))
            grid[i] = SAND
    return forced


# --- checking it ------------------------------------------------------------
def components(grid):
    """Label the connected runs of passable cells, 4-connected as a walker
    moves: the server steps a ray cell by cell, and a diagonal squeeze
    between two rock cells is stopped by whichever one the ray enters."""
    lab = [0] * (W * H)
    n = 0
    for start in range(W * H):
        if grid[start] not in PASSABLE or lab[start]:
            continue
        n += 1
        lab[start] = n
        stack = [start]
        while stack:
            i = stack.pop()
            y, x = divmod(i, W)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W:
                    j = yy * W + xx
                    if grid[j] in PASSABLE and not lab[j]:
                        lab[j] = n
                        stack.append(j)
    return lab, n


def wall_around(lab, inside, outside):
    """For each cell on the rim of component `inside`, how many blocked cells
    lie between it and component `outside`."""
    dist = [-1] * (W * H)
    queue = collections.deque()
    for i in range(W * H):
        if lab[i] == outside:
            dist[i] = 0
            queue.append(i)
    rim = {}
    while queue:
        i = queue.popleft()
        y, x = divmod(i, W)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if not (0 <= yy < H and 0 <= xx < W):
                continue
            j = yy * W + xx
            if dist[j] >= 0:
                continue
            dist[j] = dist[i]
            if lab[j] == inside:
                rim[(xx + GX0, yy + GY0)] = dist[i]
            elif lab[j]:
                queue.append(j)
            else:
                dist[j] = dist[i] + 1
                queue.append(j)
    return rim


def titles():
    out = {}
    root = os.path.join(world.RES, "locations", "static")
    for name in os.listdir(root):
        with open(os.path.join(root, name), "rb") as fh:
            head = fh.read(400)
        try:
            txt = head.decode("utf-8")
        except UnicodeDecodeError:
            txt = head.decode("cp1251", "replace")
        m = re.search(r'title="([^"]*)"', txt)
        if m:
            out[int(name[:-4])] = m.group(1)
    return out


def check(grid, settled, hints, forced):
    """Everything the report is made of."""
    lab, n = components(grid)
    sizes = collections.Counter(lab[i] for i in range(W * H) if lab[i])
    at = lambda c: lab[(c[1] - GY0) * W + (c[0] - GX0)]
    start = at(START)
    inbox = [c for c in settled
             if NUBIA[0] <= c[0] <= NUBIA[1] and NUBIA[2] <= c[1] <= NUBIA[3]]
    valley = collections.Counter(at(c) for c in inbox).most_common(1)[0][0]
    reachable = [c for c in sorted(settled) if at(c) == start]
    stuck = [c for c in sorted(settled) if at(c) != start]
    kinds = collections.Counter(grid)
    return dict(
        labels=lab, sizes=sizes, components=n, start=start, valley=valley,
        kinds=kinds, reachable=reachable, stuck=stuck, forced=forced,
        sealed=valley != start, valley_cells=sizes[valley],
        valley_settlements=[c for c in sorted(settled) if at(c) == valley],
        blocked_hints=[c for c in hints
                       if grid[(c[1] - GY0) * W + (c[0] - GX0)] not in PASSABLE],
        rim=wall_around(lab, valley, start) if valley != start else {},
    )


# --- writing it out ---------------------------------------------------------
def rows_of(grid):
    return ["".join(grid[y * W:(y + 1) * W]) for y in range(H)]


def write_json(path, grid, f):
    rows = rows_of(grid)
    doc = collections.OrderedDict((
        ("version", 1),
        ("built_by", "data/build_terrain.py"),
        ("source", "res/globalmap/full: %d tiles of 256x256, 8x8 pixels a cell"
                   % f["tiles"]),
        ("method", "roughness of the photograph (smoothed mean absolute "
                   "deviation of luminance) over %.0f is rock; mean blue over "
                   "mean red is water; cells the map tool painted over are "
                   "filled in from their neighbours; settlement and tooltip "
                   "cells are passable whatever the picture says"
                   % ROUGH),
        ("bounds", collections.OrderedDict((("gx0", GX0), ("gx1", GX1),
                                            ("gy0", GY0), ("gy1", GY1)))),
        ("legend", collections.OrderedDict((
            (SAND, "sand, gravel, open plain -- passable"),
            (PLAIN, "dark smooth ground: lava field, wadi floor -- passable"),
            (ROCK, "mountain, scarp, broken rock -- not passable"),
            (WATER_C, "water -- not passable")))),
        ("rules", collections.OrderedDict((("rough", ROUGH), ("water", WATER),
                                           ("drawn", DRAWN), ("dark", DARK),
                                           ("specks", SPECKS)))),
        ("rows", rows),
    ))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def sketch(grid, step=8):
    """The world in one screen: the commonest kind in each step x step block."""
    out = []
    for y in range(0, H, step):
        line = []
        for x in range(0, W, step):
            c = collections.Counter()
            for yy in range(y, min(H, y + step)):
                for xx in range(x, min(W, x + step)):
                    c[grid[yy * W + xx]] += 1
            blocked = c[ROCK] + c[WATER_C]
            total = sum(c.values())
            if c[WATER_C] * 2 > total:
                line.append(WATER_C)
            elif blocked * 2 > total:
                line.append("#")
            elif blocked * 4 > total:
                line.append("+")
            elif blocked:
                line.append("-")
            else:
                line.append(".")
        out.append("".join(line))
    return out


def sketch_reach(grid, lab, start, step=8):
    """The same blocks, but showing what a walker can get to: `o` marks a
    block holding ground that is cut off from the start."""
    out = []
    for y in range(0, H, step):
        line = []
        for x in range(0, W, step):
            pocket = blocked = total = 0
            for yy in range(y, min(H, y + step)):
                for xx in range(x, min(W, x + step)):
                    i = yy * W + xx
                    total += 1
                    if grid[i] not in PASSABLE:
                        blocked += 1
                    elif lab[i] != start:
                        pocket += 1
            if pocket:
                line.append("o")
            elif blocked * 2 > total:
                line.append("#")
            elif blocked:
                line.append("-")
            else:
                line.append(".")
        out.append("".join(line))
    return out


def zoom(grid, gx0, gy0, w, h, settled):
    out = []
    for gy in range(gy0, gy0 + h):
        line = []
        for gx in range(gx0, gx0 + w):
            ch = grid[(gy - GY0) * W + (gx - GX0)]
            if (gx, gy) in settled:
                ch = "S"
            elif (gx, gy) == START:
                ch = "@"
            line.append(ch)
        out.append("".join(line))
    return out


def write_report(path, grid, f, res, settled, hints, names):
    rows = rows_of(grid)
    total = W * H
    k = res["kinds"]
    out = []
    add = out.append
    add("# Passability of the global map, read off the map\n")
    add("Built by `data/build_terrain.py` from the %d tiles of"
        " `res/globalmap/full` that cover the rectangle it reads, 8x8 pixels"
        " a cell.\nThe server's own table is lost; this is a"
        " reconstruction, and the checks below are how far it can be"
        " trusted.\n" % f["tiles"])
    add("> **The server reads the water of this table and nothing else.**"
        " LAVA had no terrain layer: a cell was walled because the location"
        " standing on it had no outzone that way, and every wasteland"
        " template has all four. The `#` below is what the photograph says,"
        " not what the world is -- it would wall off cells that open as"
        " ordinary wasteland, and it contradicts 18 of the 949 exits the"
        " settlement files declare. Where the rock actually stood:"
        " `data/borders.json`, `recon/analysis/borders.md`,"
        " `data/test_borders.py`. Everything below is about the picture.\n")
    add("## What the picture says\n")
    add("| kind | cells | share |")
    add("| --- | ---: | ---: |")
    for ch, label in ((SAND, "sand, gravel, open plain"),
                      (PLAIN, "dark smooth ground (lava field, wadi)"),
                      (ROCK, "mountain, scarp, broken rock"),
                      (WATER_C, "water")):
        add("| `%s` %s | %d | %.2f%% |" % (ch, label, k[ch], 100.0 * k[ch] / total))
    add("")
    add("Passable: **%d of %d cells, %.2f%%**. The rectangle is %d by %d cells,"
        " gx %d..%d, gy %d..%d.\n"
        % (k[SAND] + k[PLAIN], total, 100.0 * (k[SAND] + k[PLAIN]) / total,
           W, H, GX0, GX1, GY0, GY1))
    add("## The checks\n")
    add("**Settlements.** All %d cells of `data/settlements.json` are passable."
        " %d of them the photograph alone would have walled in (an icon sits"
        " on the cell, or the place is built against a scarp); they are open"
        " because a player has stood there, not because the picture says so."
        % (len(settled), sum(1 for c, _ in res["forced"] if c in settled)))
    add("")
    add("**Map tooltips.** All %d cells of `res/database/locations.xml` are"
        " passable, %d of them forced the same way. Blocked after forcing:"
        " %d.\n" % (len(hints),
                    sum(1 for c, _ in res["forced"] if c not in settled),
                    len(res["blocked_hints"])))
    wet = [c for c, ch in res["forced"] if ch == WATER_C]
    add("Of the %d cells forced open, %d read as rock and %d as water. The"
        " wet ones are shore: %s -- a place standing on the bank of the lake"
        " covers a cell whose 8x8 block is mostly water.\n"
        % (len(res["forced"]), len(res["forced"]) - len(wet), len(wet),
           ", ".join("%d,%d" % c for c in wet)))
    add("**Connectivity.** From the start cell %d,%d (the black market of"
        " Wadi Halfa) %d cells are reachable on foot, %.1f%% of the passable"
        " ground, and %d of the %d settlements. The world falls into %d"
        " separate pieces of walkable ground; the main one holds everything"
        " but the pockets listed here.\n"
        % (START[0], START[1], res["sizes"][res["start"]],
           100.0 * res["sizes"][res["start"]] / (k[SAND] + k[PLAIN]),
           len(res["reachable"]), len(settled), res["components"]))
    add("| settlement | cell | location | pocket |")
    add("| --- | --- | ---: | ---: |")
    for c in res["stuck"]:
        loc = settled[c]
        lab = res["labels"][(c[1] - GY0) * W + (c[0] - GX0)]
        add("| %s | %d,%d | %d | %d cells |"
            % (names.get(loc, "?"), c[0], c[1], loc, res["sizes"][lab]))
    add("")
    add("## The Nubian valley\n")
    if res["sealed"]:
        add("**Sealed.** The valley is a pocket of %d cells holding %d"
            " settlements, and no chain of passable cells joins it to the rest"
            " of the world -- which is what the player who walked it"
            " remembers: out of the valley only by transport or by the"
            " carriers' errand.\n"
            % (res["valley_cells"], len(res["valley_settlements"])))
        add("Its rim, and how many blocked cells lie between each rim cell and"
            " the outside world -- the thinnest places, where a pass would be"
            " if there were one:\n")
        add("| cell of the rim | blocked cells to cross |")
        add("| --- | ---: |")
        for cell, d in sorted(res["rim"].items(), key=lambda kv: (kv[1], kv[0]))[:15]:
            add("| %d,%d | %d |" % (cell[0], cell[1], d))
        add("")
    else:
        add("**Not sealed.** The valley's ground joins the rest of the world;"
            " the reconstruction cannot close it at the rules in use.\n")
    add("The valley as the table has it (`S` a settlement, `#` rock, `.` and"
        " `,` walkable ground), gx %d..%d, gy %d..%d:\n"
        % (NUBIA[0], NUBIA[1], NUBIA[2], NUBIA[3]))
    add("```")
    for line in zoom(grid, NUBIA[0], NUBIA[2], NUBIA[1] - NUBIA[0] + 1,
                     NUBIA[3] - NUBIA[2] + 1, settled):
        add(line)
    add("```\n")
    add("## The world, eight cells to a character\n")
    add("`.` open, `-` a little broken, `+` half blocked, `#` mostly blocked,"
        " `~` water. gx %d..%d left to right, gy %d..%d top to bottom.\n"
        % (GX0, GX1, GY0, GY1))
    add("```")
    for line in sketch(grid):
        add(line)
    add("```\n")
    add("## What the walker can reach, eight cells to a character\n")
    add("The same blocks again: `o` is a block that holds ground cut off from"
        " the start -- the Nubian valley and a handful of one-cell pockets --"
        " `#` mostly blocked, `-` a little broken, `.` open and reachable.\n")
    add("```")
    for line in sketch_reach(grid, res["labels"], res["start"]):
        add(line)
    add("```\n")
    add("## Where to distrust this\n")
    add("* Cells under an icon or a caption are not measured at all, only"
        " filled in from their neighbours: %d cells of the map are more than"
        " a quarter painted over."
        % sum(1 for v in f["drawn"] if v > DRAWN))
    add("* The %d settlements listed above sit in pockets the walker cannot"
        " reach. Some of that is real -- the valley is meant to be sealed --"
        " and some is the picture being harsher than the game was."
        % len(res["stuck"]))
    add("* Roughness is a proxy for relief. A field of dark boulders reads as"
        " a mountain; a smooth dune field reads as a road. The threshold"
        " (%.0f) was chosen as the loosest one that still closes the valley."
        % ROUGH)
    add("* Water is only Lake Nasser and the Nile: %.2f%% of the map. Narrow"
        " stretches of the river are drawn thinner than a cell, so the river"
        " does not cut the map in two the way the real one does.\n"
        % (100.0 * k[WATER_C] / total))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))


def main():
    f = features()
    print("tiles read: %d, cells: %d" % (f["tiles"], W * H))
    for name in ("lum", "rough", "blue", "drawn"):
        v = sorted(f[name])
        qs = [v[int(len(v) * p / 100.0) - (1 if p == 100 else 0)]
              for p in (0, 1, 25, 50, 75, 95, 99, 100)]
        print("  %-6s" % name + " ".join("%8.2f" % q for q in qs))
    print("  %-6s" % "" + " ".join("%8s" % s for s in
          ("min", "1%", "25%", "50%", "75%", "95%", "99%", "max")))
    grid = classify(f)
    settled = world.settlements()
    cells, hints = evidence()
    forced = force(grid, list(cells) + hints)
    print("forced open by evidence: %d cells" % len(forced))
    res = check(grid, settled, hints, forced)
    print("kinds: " + ", ".join("%s %d" % (ch, res["kinds"][ch])
                                for ch in (SAND, PLAIN, ROCK, WATER_C)))
    print("components: %d, start %d cells, valley %d cells, sealed %s"
          % (res["components"], res["sizes"][res["start"]], res["valley_cells"],
             res["sealed"]))
    print("settlements reachable from the start: %d of %d"
          % (len(res["reachable"]), len(settled)))
    write_json(os.path.join(HERE, "map_terrain.json"), grid, f)
    write_report(os.path.join(HERE, "map_terrain_report.md"), grid, f, res,
                 settled, hints, titles())
    print("wrote data/map_terrain.json and data/map_terrain_report.md")


if __name__ == "__main__":
    main()
