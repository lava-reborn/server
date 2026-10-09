"""The squares the global map paints on cells: taken off where a place is gone,
and nothing else on the map moves (server/map_cells.py over server/jpeg_blocks.py).

After the cut of Вади-Хальфа (2026-10-09) the owner saw the names of the
removed places gone and their squares still on the map: the squares are
pixels of the map's picture, res/globalmap/full/<n>.jpg. map_cells paints
them over in the tiles every client release carries (client/build.py) and
bootstrap_http serves on a local run.

Runs everywhere on pictures made here: the plan against data/retired.json,
data/map_labels.json and data/settlements.json; the JPEG blocks; the
painting over on a made map whose ground is known. With the client's tiles
under LAVA_RES/globalmap/full it holds the real map to the same (the owner's
client, or CI's extras once they carry the tiles):

    LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 server/test_map_cells.py
"""
import glob
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import jpeg_blocks as J  # noqa: E402
import map_cells as M  # noqa: E402
import map_labels  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "the map's squares of retired places"

RES = os.environ.get("LAVA_RES") or ""
W = tempfile.mkdtemp(prefix="test-map-cells-")


def load_json(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def cell(key):
    x, y = key.split(",")
    return int(x), int(y)


try:
    # --- the plan: what goes, from data/retired.json and data/map_cells.json -------------
    plan = M.load()
    retired = {cell(k) for k in load_json("data", "retired.json")["cells"] if not k.startswith("_")}
    LABEL_ONLY = {(5969, 1730), (5984, 1759), (6265, 1821)}
    check("every cell of data/retired.json loses its square, by itself",
          sorted(retired - set(plan.cells)), [])
    check("  ..those are the seven of the two cuts: the (P) camps 124, 125, 130 and Halfa's 468, 452,"
          " 456, 457", sorted(retired),
          [(5876, 2012), (5968, 1726), (5969, 1729), (5969, 1731), (5969, 1732), (5970, 1732), (6182, 1975)])
    check("  ..and data/map_cells.json adds the three cells that had a name and no place: «Улучшение"
          " сетов 6-8», the KKND base and the kimberlite pipe", sorted(set(plan.cells) - retired), sorted(LABEL_ONLY))
    live = {cell(k) for k in load_json("data", "settlements.json")["cells"]}
    check("no square goes from a cell a place still stands on (data/settlements.json)",
          sorted(set(plan.cells) & live), [])
    hidden = {(x, y) for x, y, _was, new in map_labels.load() if new is None}
    undecided = sorted(c for c in hidden - live if c not in plan.cells and c not in plan.keep)
    check("every hidden name with no place under it is decided: its square goes, or stays with a why",
          undecided, [])
    check("  ..the kimberlite pipe's goes too, on the owner's word of 2026-10-10; nothing is kept now",
          (sorted(plan.keep), "owner" in plan.cells.get((6265, 1821), "")), ([], True))
    check("  ..and the farm's cell keeps its square: only the New Year name over it is hidden",
          ((6266, 1822) in live, (6266, 1822) in plan.cells), (True, False))
    loc_path = os.path.join(RES, "database", "locations.xml")
    if os.path.isfile(loc_path):
        with open(loc_path, "rb") as fh:
            shown, _n = map_labels.apply(fh.read())
        named = set()
        for m in map_labels.ROW.finditer(shown):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            named.add((int(a["x"]), int(a["y"])))
        check("no cell that loses its square keeps a name over it on the map",
              sorted(set(plan.cells) & named), [])
    else:
        print("  -- no %s: the names over erased cells are test_map_labels' alone" % loc_path)
    check("the KKND caption is two boxes of tile 14011, above the base's cell",
          [(b, M.tile_of(b[0], b[1]), M.tile_of(b[2], b[3])) for b, was, _ in plan.captions],
          [((47879, 14049, 47920, 14057), 14011, 14011), ((47879, 14058, 47910, 14067), 14011, 14011)])
    check("the tiles a change can touch, a square's frame reaching a pixel past its cell: Halfa's two,"
          " KKND's and the two below it, the kimberlite pipe's, Абу-Хамед's, Донгола's",
          plan.tiles(), [13754, 14010, 14011, 14266, 14267, 14531, 15809, 16055])

    def refused(doc, retired_doc=None):
        p = os.path.join(W, "cells.json")
        r = os.path.join(W, "retired.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        with open(r, "w", encoding="utf-8") as fh:
            json.dump(retired_doc or {"cells": {"1,1": 5}}, fh)
        try:
            M.load(p, r)
        except ValueError as e:
            return str(e)
        return None

    check("a cell without its why is refused", bool(refused({"cells": {"2,2": ""}})), True)
    check("a cell of data/retired.json listed again is refused", bool(refused({"cells": {"1,1": "x"}})), True)
    check("a cell both erased and kept is refused",
          bool(refused({"cells": {"2,2": "x"}, "keep": {"2,2": "y"}})), True)
    check("a kept cell without its why is refused", bool(refused({"keep": {"2,2": ""}})), True)
    check("a caption without boxes, or with one too big, is refused",
          (bool(refused({"captions": [{"was": "A", "why": "x", "boxes": []}]})),
           bool(refused({"captions": [{"was": "A", "why": "x", "boxes": [[0, 0, 100, 100]]}]}))),
          (True, True))
    check("a good file loads", refused({"cells": {"2,2": "x"}, "keep": {"3,3": "y"},
                                        "captions": [{"was": "A", "why": "x", "boxes": [[0, 0, 9, 9]]}]}), None)

    # --- jpeg_blocks: blocks in, blocks out -------------------------------------------------
    print("jpeg_blocks")
    check("the integer DCT basis has no entry near a half, so every machine rounds it alike",
          min(abs(abs(v - math.floor(v)) - 0.5) for row in J.BASIS_EXACT for v in row) > 0.01, True)

    def picture(w, h, seed=1):
        """Three planes of a smooth picture with grain."""
        state = [seed]

        def rnd():
            state[0] = (state[0] * 1103515245 + 12345) & 0x7FFFFFFF
            return state[0] % 17 - 8
        return [[[max(0, min(255, int(c + 40 * math.sin((x + 3 * ci) / 9.0) * math.cos(y / 7.0)) + rnd()))
                  for x in range(w)] for y in range(h)] for ci, c in enumerate((150, 110, 140))]

    def coefficients(data):
        j = J.Jpeg(data)
        return [list(map(tuple, c.blocks)) for c in j.comps]

    small = J.make(40, 24, picture(40, 24))
    check("a picture made here reads and writes back byte for byte", J.Jpeg(small).encode(), small)
    check("  ..its scan padded with ones, as the standard has it and the map's tiles are",
          J.Jpeg(small).padding_ones, True)
    rst = J.make(48, 32, picture(48, 32), restart=2)
    check("  ..with restart markers every two MCUs, each in its place",
          (J.Jpeg(rst).encode() == rst, rst.count(b"\xff\xd0") >= 1, J.Jpeg(rst).restart), (True, True, 2))
    sub = picture(48, 32)
    sub420 = [sub[0]] + [[[sum(p[2 * y + a][2 * x + b] for a in (0, 1) for b in (0, 1)) // 4
                           for x in range(24)] for y in range(16)] for p in sub[1:]]
    p420 = J.make(48, 32, sub420, sampling=(2, 2))
    j420 = J.Jpeg(p420)
    check("  ..and subsampled 4:2:0, Y in 2x2 blocks to an MCU",
          (j420.encode() == p420, [(c.h, c.v, c.bw, c.bh) for c in j420.comps]),
          (True, [(2, 2, 6, 4), (1, 1, 3, 2), (1, 1, 3, 2)]))
    def ramp(X, Y):
        return (X * 13 + Y * 7) % 256

    jf = J.Jpeg(J.make(16, 16, [[[ramp(x, y) for x in range(16)] for y in range(16)]] * 3,
                       qtables=((1,) * 64, (1,) * 64)))
    check("with every quantizer 1, the samples come back within one of what was put in",
          max(abs(jf.block_samples(0, bx, by)[y * 8 + x] - ramp(8 * bx + x, 8 * by + y))
              for bx in (0, 1) for by in (0, 1) for x in range(8) for y in range(8)) <= 1, True)

    j = J.Jpeg(small)
    before = coefficients(small)
    j.set_block_samples(0, 2, 1, [200 if (x + y) % 2 else 40 for y in range(8) for x in range(8)])
    out = j.encode()
    after = coefficients(out)
    changed = [(ci, k) for ci in range(3) for k in range(len(before[ci])) if before[ci][k] != after[ci][k]]
    check("a block changed is the only one whose coefficients change (block 2,1 of Y is number 7)",
          changed, [(0, 7)])
    check("  ..a checkerboard needs codes the picture's own tables lack: they are made anew",
          j.tables_renewed, True)
    check("  ..and the new file reads back to exactly the blocks written",
          after[0][7], tuple(j.comps[0].blocks[7]))

    def refusal(data):
        try:
            J.Jpeg(data)
        except J.JpegError as e:
            return str(e)
        return None

    sof = small.index(b"\xff\xc0")
    check("a progressive file is refused", "SOF2" in (refusal(small[:sof] + b"\xff\xc2" + small[sof + 2:]) or ""), True)
    check("a 12-bit file is refused", "8-bit" in (refusal(small[:sof + 4] + b"\x0c" + small[sof + 5:]) or ""), True)
    check("a cut-off file is refused", refusal(small[:len(small) // 2]) is not None, True)
    check("what is no JPEG is refused", refusal(b"GIF89a....") is not None, True)

    # --- painting over, on a made map whose ground is known ------------------------------------
    print("a made map")
    OUTLINE = (177, 139, 102)

    def ground(X, Y):
        """The photograph under everything: sand with grain, a dark lake."""
        n = (X * 7919 + Y * 104729 + X * Y * 31) % 9 - 4
        if (X - 40) ** 2 + (Y - 210) ** 2 < 35 ** 2:
            return (30 + n, 34 + n, 30 + n)
        t = int(9 * math.sin(X * 0.7) + 7 * math.cos(Y * 0.45 + X * 0.1)) + n
        return (200 + t, 178 + t, 120 + t)

    picture_rgb = {}

    def paint(x, y, colour, off=(0, 0), centre=None):
        """A square in the original's way: a 7x7 fill in a dotted outline, its
        9x9 frame on the cell's corner or one pixel off it."""
        X0, Y0 = 8 * x + off[0], 8 * y + off[1]
        border = ([(X0 + i, Y0) for i in range(9)] + [(X0 + 8, Y0 + j) for j in range(1, 9)]
                  + [(X0 + i, Y0 + 8) for i in range(7, -1, -1)] + [(X0, Y0 + j) for j in range(7, 0, -1)])
        for k, p in enumerate(border):
            if k % 4:
                picture_rgb[p] = OUTLINE
        for j_ in range(1, 8):
            for i in range(1, 8):
                picture_rgb[(X0 + i, Y0 + j_)] = colour
        if centre:
            for j_ in range(3, 6):
                for i in range(3, 6):
                    picture_rgb[(X0 + i, Y0 + j_)] = centre

    GREEN, RED, TAN, BLUE, WHITE = (12, 104, 2), (120, 24, 30), (204, 181, 110), (16, 16, 245), (255, 255, 255)
    paint(10, 10, GREEN)              # goes
    paint(11, 10, RED)                # stays, right of it: they share an outline
    paint(10, 11, GREEN)              # goes, below the first: one region with it
    paint(9, 12, TAN)                 # stays, corner to corner with the second
    paint(31, 5, GREEN)               # goes, on the tile's right edge: its outline is in the next tile
    paint(20, 20, RED, (0, -1), WHITE)  # goes, a clan base drawn a pixel high
    paint(40, 10, BLUE, centre=WHITE)  # stays, far from everything
    for X in range(99, 141):          # a caption: letters with a light rim
        for Y in range(59, 71):
            edge = X in (99, 140) or Y in (59, 70)
            picture_rgb[(X, Y)] = (225, 215, 170) if edge else (55, 45, 35) if X % 5 < 2 or Y in (61, 68) else (225, 215, 170)
    paint(17, 7, GREEN)               # stays, drawn over the caption's right end
    # sand of the tan squares' very colour, with its grain, between four
    # squares: framed on every side by their outlines, and still no square
    for X in range(8 * 22, 8 * 23 + 1):
        for Y in range(8 * 26, 8 * 27 + 1):
            g = (X * 37 + Y * 11) % 17 - 8
            picture_rgb[(X, Y)] = (204 + g, 181 + g, 110 + g)
    for c in ((21, 26), (23, 26), (22, 25), (22, 27)):
        paint(c[0], c[1], RED)
    ERASE = {(10, 10): "t", (10, 11): "t", (31, 5): "t", (20, 20): "t", (25, 25): "nothing painted there"}
    KEPT = [(11, 10), (9, 12), (40, 10), (17, 7)]
    made_plan = M.Plan(ERASE, [((99, 59, 140, 70), "Caption", "t")], {})

    def ycc(p):
        r, g, b = p
        return (0.299 * r + 0.587 * g + 0.114 * b,
                128 - 0.168736 * r - 0.331264 * g + 0.5 * b,
                128 + 0.5 * r - 0.418688 * g - 0.081312 * b)

    def make_tile(tx, sampling=(1, 1)):
        planes = [[[0] * 256 for _ in range(256)] for _ in range(3)]
        for Y in range(256):
            for x in range(256):
                X = 256 * tx + x
                v = ycc(picture_rgb.get((X, Y)) or ground(X, Y))
                for ci in range(3):
                    planes[ci][Y][x] = max(0, min(255, int(round(v[ci]))))
        if sampling != (1, 1):
            planes = [planes[0]] + [[[sum(p[2 * y + a][2 * x + b] for a in (0, 1) for b in (0, 1)) // 4
                                      for x in range(128)] for y in range(128)] for p in planes[1:]]
        # about the quality the map's tiles were saved at
        fine = tuple(tuple(max(1, (q + 2) // 4) for q in t) for t in (J.STD_LUMA, J.STD_CHROMA))
        return J.make(256, 256, planes, sampling=sampling, qtables=fine)

    made = {M.tile_path(0): make_tile(0), M.tile_path(1): make_tile(1)}

    def run(tiles, plan_):
        read = tiles.get
        canvas = M.Canvas(read)
        before_sq = M.Squares(M.Canvas(read))
        found, kept, painted, report = M.erase(canvas, plan_)
        out, blocks = canvas.encode()
        new = {M.tile_path(n): b for n, b in out.items()}
        after_canvas = M.Canvas(lambda p: new.get(p) or read(p))
        return dict(found=found, kept=kept, painted=painted, report=report, out=new, blocks=blocks,
                    before=M.Canvas(read), after=after_canvas, before_sq=before_sq,
                    after_sq=M.Squares(after_canvas))

    r = run(made, made_plan)
    check("each square that goes is found, the clan base's a pixel high; the cell with nothing on it says so",
          ({c: (sq[0] - 8 * c[0], sq[1] - 8 * c[1], sq[2]) for c, sq in r["found"].items()},
           [line for line in r["report"] if "no square" in line]),
          ({(10, 10): (0, 0, ("green",)), (10, 11): (0, 0, ("green",)), (31, 5): (0, 0, ("green",)),
            (20, 20): (0, -1, ("red", "white"))}, ["25,25: no square painted on the cell"]))
    check("  ..and the squares beside them that stay, and the one over the caption",
          sorted(r["kept"]), [(9, 12), (11, 10), (17, 7)])
    check("tan sand with its grain between four squares is no square (a painted fill is flat)",
          (r["before_sq"].at(22, 26), [bool(r["before_sq"].at(*c)) for c in ((21, 26), (23, 26), (22, 25), (22, 27))]),
          (None, [True] * 4))
    check("both tiles change: the square on the edge has its outline in the next one",
          sorted(r["out"]), [M.tile_path(0), M.tile_path(1)])
    check("no square is left on the cells that lose theirs",
          {c: r["after_sq"].at(*c) for c in ERASE}, {c: None for c in ERASE})
    check("every square that stays is found where it was, as it was",
          [r["after_sq"].at(*c) for c in KEPT], [r["before_sq"].at(*c) for c in KEPT])

    def diff(a, b):
        return max(abs(u - v) for u, v in zip(a, b))

    def moved(rr, tiles):
        """How far the pixels not painted moved, over the tiles that changed:
        (largest, share of those that moved at all that moved by 2 or less)."""
        most, count, small = 0, 0, 0
        for path in rr["out"]:
            n = int(path.rsplit("/", 1)[1].split(".")[0])
            X0, Y0 = (n % 256) * 256, (n // 256) * 256
            for X in range(X0, X0 + 256):
                for Y in range(Y0, Y0 + 256):
                    if (X, Y) in rr["painted"]:
                        continue
                    d = diff(rr["before"].original(X, Y), rr["after"].original(X, Y))
                    if d:
                        count += 1
                        small += d <= 2
                        most = max(most, d)
        return most, (small / count if count else 1.0)

    def colour_left(rr):
        """{cell: pixels of its 7x7 fill still of its square's colours}."""
        out = {}
        for c, (X0, Y0, kind) in rr["found"].items():
            out[c] = sum(1 for j in range(1, 8) for i in range(1, 8)
                         if rr["after_sq"].colour(X0 + i, Y0 + j) in kind)
        return out

    protect = set()
    for sq in r["kept"].values():
        protect |= M.frame_pixels(sq)
    check("  ..its outline too, the line it shares with the square gone (largest change of a sample)",
          max(diff(r["before"].original(*p), r["after"].original(*p)) for p in protect) <= 16, True)
    shared = [(88, Y) for Y in range(81, 88)]
    check("  ..which is the red square's own: still the outline's colour",
          all(diff(M.rgb(r["after"].original(*p)), OUTLINE) <= 30 for p in shared if (shared.index(p) + 1) % 4),
          True)
    gone_outline = [(88, Y) for Y in range(89, 96)]
    check("the outline of the square gone, in a neighbour's block that is sand, goes with it",
          [p for p in gone_outline if diff(M.rgb(r["after"].original(*p)), OUTLINE) <= 14], [])
    errors = [abs(r["after"].original(*p)[0] - ycc(ground(*p))[0]) for p in r["painted"]]
    check("what is painted in is ground like the ground under it: luma off by %.1f on average, %d at most"
          % (sum(errors) / len(errors), max(errors)), (sum(errors) / len(errors) < 14, max(errors) < 70),
          (True, True))
    def beyond(rr, margin=15):
        """{a painted group's first pixel: how many of its pixels, as the new
        tiles show them, are darker or brighter (Y, Cb or Cr) than every
        pixel of the ground three around the group by more than margin}: the
        ground less what is painted and the squares that stay."""
        kept_px = set()
        for sq in rr["kept"].values():
            kept_px |= M.frame_pixels(sq)
        out = {}
        for g in M._groups(rr["painted"]):
            ring = [rr["before"].original(*p) for p in sorted(M._ring(g, 3))
                    if p not in rr["painted"] and p not in kept_px]
            ring = [v for v in ring if v is not None]
            lo = [min(v[i] for v in ring) - margin for i in range(3)]
            hi = [max(v[i] for v in ring) + margin for i in range(3)]
            n = sum(1 for p in g if any(not lo[i] <= rr["after"].original(*p)[i] <= hi[i] for i in range(3)))
            if n:
                out[g[0]] = n
        return out

    check("  ..and no fill keeps its square's colour", colour_left(r), {c: 0 for c in r["found"]})
    check("  ..nor brings in what the ground around it has not: no painted pixel darker or brighter than"
          " its ground by more than 15", beyond(r), {})
    dark = [p for p in [(X, Y) for X in range(99, 141) for Y in range(59, 71)]
            if r["after"].original(*p)[0] < 100 and p not in protect]
    check("the caption's letters are gone, but under the square that stays", dark, [])

    def changed_blocks(old, new):
        a, b = J.Jpeg(old), J.Jpeg(new)
        return {(ci, k) for ci in range(3) for k, (x, y) in enumerate(zip(a.comps[ci].blocks, b.comps[ci].blocks))
                if x != y}

    def painted_blocks(painted, n, j):
        out = set()
        for X, Y in painted:
            if M.tile_of(X, Y) != n:
                continue
            for ci, c in enumerate(j.comps):
                sx, sy = (X % 256) * c.h // j.hmax, (Y % 256) * c.v // j.vmax
                out.add((ci, (sy // 8) * c.bw + sx // 8))
        return out

    def only_painted(tiles_before, rr):
        """{tile: blocks changed with no pixel painted in them}, and how many
        blocks changed."""
        stray, count = {}, 0
        for path, data in rr["out"].items():
            n = int(path.rsplit("/", 1)[1].split(".")[0])
            got = changed_blocks(tiles_before[path], data)
            stray[n] = sorted(got - painted_blocks(rr["painted"], n, J.Jpeg(tiles_before[path])))
            count += len(got)
        return stray, count

    stray, count = only_painted(made, r)
    check("only blocks with a pixel painted change, in each tile; every other keeps its coefficients"
          " (%d changed)" % count, (stray, count > 0), ({0: [], 1: []}, True))
    most, share = moved(r, made)
    # this ground is grainier than the real one and the caption a block's
    # worth of contrast, so only the largest move is held here; the real map
    # below is held to both
    check("  ..and a pixel not painted in such a block moves by its rounding: %d at most (%.0f%% of those"
          " that move by 2 or less)" % (most, 100 * share), most <= 16, True)
    again = run(made, made_plan)
    check("the same picture and plan give the same bytes", again["out"] == r["out"], True)
    check("a client without the tiles gets nothing and is told",
          (M.apply(lambda p: None, made_plan)[0],
           len([x for x in M.apply(lambda p: None, made_plan)[1] if "no tile" in x])), ({}, 6))

    made420 = {M.tile_path(0): make_tile(0, (2, 2)), M.tile_path(1): make_tile(1, (2, 2))}
    r4 = run(made420, made_plan)
    check("on 4:2:0 tiles the same squares go and the same stay",
          (sorted(r4["found"]), sorted(r4["kept"]), {c: r4["after_sq"].at(*c) for c in ERASE},
           [r4["after_sq"].at(*c) == r4["before_sq"].at(*c) for c in KEPT]),
          (sorted(r["found"]), sorted(r["kept"]), {c: None for c in ERASE}, [True] * len(KEPT)))
    stray, count = only_painted(made420, r4)
    check("  ..and only blocks with a pixel painted change, a chroma block covering 16 x 16 (%d changed)"
          % count, (stray, count > 0), ({0: [], 1: []}, True))
    check("  ..and no painted pixel darker or brighter than its ground by more than 15", beyond(r4), {})

    # A square on a calm island in a striped field: every patch of
    # photograph within reach is stripes, far darker and far brighter than
    # the island, so none is taken (on Донгола's tile the patch first chosen
    # carried the river's black line in) and the square is painted smooth
    # from its edge.
    def striped_tile():
        planes = [[[128] * 256 for _ in range(256)] for _ in range(3)]
        for Y in range(256):
            for X in range(256):
                island = 72 <= X < 96 and 72 <= Y < 96
                planes[0][Y][X] = 120 if island else 50 if (X // 2) % 2 else 200
        X0 = Y0 = 80
        for k, (X, Y) in enumerate([(X0 + i, Y0) for i in range(9)] + [(X0 + 8, Y0 + j) for j in range(1, 9)]
                                   + [(X0 + i, Y0 + 8) for i in range(7, -1, -1)]
                                   + [(X0, Y0 + j) for j in range(7, 0, -1)]):
            if k % 4:
                for ci, v in enumerate(ycc(OUTLINE)):
                    planes[ci][Y][X] = int(round(v))
        for j_ in range(1, 8):
            for i in range(1, 8):
                for ci, v in enumerate(ycc(GREEN)):
                    planes[ci][Y0 + j_][X0 + i] = int(round(v))
        fine = tuple(tuple(max(1, (q + 2) // 4) for q in t) for t in (J.STD_LUMA, J.STD_CHROMA))
        return {M.tile_path(0): J.make(256, 256, planes, qtables=fine)}

    rs = run(striped_tile(), M.Plan({(10, 10): "t"}, [], {}))
    island = [rs["after"].original(*p)[0] for p in sorted(rs["painted"])]
    check("a square whose ground no patch of photograph within reach matches is painted smooth from its edge",
          ([line.strip() for line in rs["report"] if "painted" in line],
           rs["after_sq"].at(10, 10), beyond(rs), min(island) >= 105 and max(island) <= 135),
          (["81 pixels from 80,80 painted smooth from its edge, no patch of photograph fitting"], None, {}, True))
    bounds = M.ground_bounds(rs["before"], sorted(rs["painted"]), rs["painted"])
    check("  ..its bounds are the island's own range (120, give or take the JPEG's ringing by the square)"
          " and %d levels past it, and a pixel past them in any of Y, Cb, Cr is counted" % M.MARGIN,
          (120 - M.MARGIN - 10 <= bounds[0][0] <= 120 - M.MARGIN
           and 120 + M.MARGIN <= bounds[0][1] <= 120 + M.MARGIN + 10,
           M.outside([(120, 128, 128), (90, 128, 128), (120, 128, 200)], [(108, 132), (116, 140), (116, 140)]),
           M.outside([(0, 0, 0)], None)),
          (True, 2, 0))

    # The local run: bootstrap_http serves res/ through map_cells.Served.
    res = os.path.join(W, "res")
    for path, data in made.items():
        os.makedirs(os.path.dirname(os.path.join(res, path)), exist_ok=True)
        with open(os.path.join(res, path), "wb") as fh:
            fh.write(data)
    served = M.Served(res, M.Plan(ERASE, made_plan.captions, {}))
    check("a local run serves the painted tiles, and the file itself for anything else",
          (served.get(M.tile_path(0)) == r["out"][M.tile_path(0)], served.get("globalmap/full/7.jpg"),
           served.get("database/locations.xml")), (True, None, None))

    # --- the real map ------------------------------------------------------------------------------
    full = os.path.join(RES, "globalmap", "full")
    if not os.path.isdir(full):
        print("  -- no %s: the real map is not checked here (CI's extras carry no tiles)" % full)
    else:
        print("the real map")
        paths = sorted(glob.glob(os.path.join(full, "*.jpg")))
        every = {}
        for p in paths:
            with open(p, "rb") as fh:
                every["globalmap/full/" + os.path.basename(p)] = fh.read()
        read = every.get
        not_same = [p for p, data in sorted(every.items()) if J.Jpeg(data).encode() != data]
        check("every tile of the map (%d) reads and writes back byte for byte" % len(paths), not_same, [])
        base = {}
        with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 3:
                    base[parts[2]] = parts[0]
        check("the tiles a change can touch are the original's, as client/base.txt has them",
              [M.tile_path(n) for n in plan.tiles()
               if hashlib.sha256(read(M.tile_path(n))).hexdigest() != base.get(M.tile_path(n))], [])
        real = run(every, plan)
        odd = {(5984, 1759): (0, -1, ("red", "white")), (6265, 1821): (0, 0, ("black", "orange"))}
        check("each of the ten cells has its square found: eight green, KKND's dark red with white a pixel"
              " high, the kimberlite pipe's black-and-orange hatch",
              {c: (sq[0] - 8 * c[0], sq[1] - 8 * c[1], sq[2]) for c, sq in real["found"].items()},
              {c: odd.get(c, (0, 0, ("green",))) for c in plan.cells})
        check("  ..and nothing is reported missing", [x for x in real["report"] if ": no " in x], [])
        check("six tiles change: 13754 and 14010 in Halfa, 14011 for KKND, 14531 the kimberlite pipe,"
              " 15809 Абу-Хамед, 16055 Донгола",
              sorted(real["out"]), sorted(M.tile_path(n) for n in (13754, 14010, 14011, 14531, 15809, 16055)))
        check("no square is left on the ten cells", {c: real["after_sq"].at(*c) for c in plan.cells},
              {c: None for c in plan.cells})
        around = sorted({(x + dx, y + dy) for x, y in plan.cells for dx in range(-3, 4) for dy in range(-3, 4)}
                        - set(plan.cells))
        shifted = [c for c in around if real["after_sq"].at(*c) != real["before_sq"].at(*c)]
        check("every other square within three cells is where it was, as it was (%d squares)"
              % sum(1 for c in around if real["before_sq"].at(*c)), shifted, [])
        KEPT_HALFA = {(5969, 1728): ("green",), (5970, 1729): ("red",), (5970, 1730): ("black",),
                      (5969, 1733): ("tan",), (5971, 1731): ("tan",), (5968, 1727): ("green",),
                      (5970, 1727): ("blue", "white"), (5876, 2011): ("green",), (5877, 2012): ("green",),
                      (5876, 2013): ("green",), (6183, 1975): ("green",), (6182, 1976): ("green",)}
        check("  ..among them the owner's neighbours named in the research: the masters' camp 95, arena 78,"
              " the black market 102, «Генри Мл.» 43, the crates 108, the old market, the airfield; Донгола's"
              " 96, 97 and 455; Абу-Хамед's 127 and 126",
              {c: (real["after_sq"].at(*c) or (0, 0, None))[2] for c in KEPT_HALFA}, KEPT_HALFA)
        check("  ..and the squares beside those that go keep their outlines (largest change of a sample)",
              max(diff(real["before"].original(*p), real["after"].original(*p))
                  for sq in real["kept"].values() for p in M.frame_pixels(sq)) <= 16, True)
        stray, count = only_painted(every, real)
        check("only blocks with a pixel painted change; every other block of every tile keeps its"
              " coefficients (%d changed)" % count,
              (stray, count > 0), ({n: [] for n in (13754, 14010, 14011, 14531, 15809, 16055)}, True))
        most, share = moved(real, every)
        check("  ..and a pixel not painted in such a block moves by its rounding: %d at most, %.0f%% of those"
              " that move by 2 or less" % (most, 100 * share), (most <= 16, share >= 0.9), (True, True))
        boxes = [(X, Y) for (x0, y0, x1, y1), _, _ in plan.captions
                 for X in range(x0, x1 + 1) for Y in range(y0, y1 + 1)]
        dark_before = sum(1 for p in boxes if real["before"].original(*p)[0] < 110)
        dark_after = sum(1 for p in boxes if real["after"].original(*p)[0] < 110)
        check("the letters «Кланбаза KKND» are gone: dark pixels in their boxes %d before, %d after"
              % (dark_before, dark_after), (dark_before > 100, dark_after < 10), (True, True))
        check("no fill keeps its square's colour (Донгола's ground is red of its own)",
              colour_left(real), {c: 0 for c in real["found"]})
        check("  ..nor brings in what its ground has not: no painted pixel darker or brighter than the ground"
              " around it by more than 15 (Донгола's first patch carried in the river's black line, 2-3 pixels"
              " wide; Хальфа's lake shore is really there)", beyond(real), {})
        check("  ..and every square is painted from a patch of photograph",
              [line.strip() for line in real["report"] if "smooth" in line], [])
        out_real, _report = M.apply(read)
        check("map_cells.apply gives these tiles", out_real == real["out"], True)
        check("a local run serves the same bytes (bootstrap_http)",
              {p: M.Served(RES).get(p) == data for p, data in out_real.items()}, {p: True for p in out_real})

        # client/build.py's generated layer, over a store of the original tiles
        sys.path.insert(0, os.path.join(ROOT, "client"))
        import build  # noqa: E402
        store = os.path.join(W, "store")
        b = build.Build(ROOT, store, RES, os.path.join(W, "release"))
        b.base, b.files, b.origin = {}, {}, {}
        for rel, data in sorted(every.items()):
            sha = hashlib.sha256(data).hexdigest()
            os.makedirs(os.path.join(store, sha[:2]), exist_ok=True)
            with open(os.path.join(store, sha[:2], sha), "wb") as fh:
                fh.write(data)
            b.base[rel] = b.files[rel] = (sha, len(data))
            b.origin[rel] = "base"
        tiles_rel, _done = b.gen_map_tiles()
        shutil.rmtree(b.tmp, ignore_errors=True)
        check("a client release carries the same tiles (client/build.py, from the store)",
              tiles_rel == out_real, True)
        print("  " + "\n  ".join(real["report"]))
finally:
    shutil.rmtree(W, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("map_cells OK")
