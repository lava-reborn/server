"""The squares the global map paints on cells: taken off where a place is gone,
and nothing else on the map moves (server/map_cells.py over server/jpeg_blocks.py).

After the cut of Вади-Хальфа (2026-10-09) the owner saw the names of the
removed places gone and their squares still on the map: the squares are
pixels of the map's picture, res/globalmap/full/<n>.jpg. map_cells paints
them over in the tiles every client release carries (client/build.py) and
bootstrap_http serves on a local run. After the cut of the camps across the
river (2026-10-12) the owner saw their war zones still there, a red circle
with blue arrows round each camp: map_cells takes those off first.

Runs everywhere on pictures made here: the plan against data/retired.json,
data/map_labels.json and data/settlements.json; the JPEG blocks; the
painting over on a made map whose ground is known, and a war zone on
another. With the original's
tiles under LAVA_RES/globalmap/full it holds the real map to the same (CI's
extras once they carry the tiles, or a res/ whose tiles come from the
release store by client/base.txt). An installed client is no such res any
more: the launcher puts the release's painted tiles in it (the owner's since
2026-10-10), and on those the test says which tiles are not the original's
and holds nothing else of the real map:

    LAVA_RES=<res with the original tiles> python3 server/test_map_cells.py
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
    # The cut of Абри (2026-10-12) adds six: «Улучшение сетов 10-12», the
    # green mark left of the craftsmen of 12, the second «Автосвалка», the
    # two squares of «Кланбаза Liberty» by Абу-Хамед, and Blackwater's square
    # beside its block post. The cut of the camps across the river (the same
    # day) adds two: Абу-Хамед's camp's own square across the river, under
    # its hidden name, and Абри's island camp's, which no name stands over.
    LABEL_ONLY = {(5969, 1730), (5984, 1759), (6265, 1821),
                  (5866, 1837), (5862, 1837), (5863, 1836), (6248, 1979), (6248, 1980),
                  (5923, 1838), (6168, 1989), (5850, 1851)}
    ABRI_CUT = [(5860, 1836), (5860, 1837), (5861, 1836), (5863, 1837), (5866, 1836),
                (5906, 1888), (5906, 1889), (5865, 1835), (5924, 1838)]
    # The camps across the river of Вади-Хальфа (429) and Донгола (431), and
    # Абри's clothing market 378 (2026-10-12). Абу-Хамед's camp 432 stood on
    # 6160,1975, under the pirates' name and over their square, which stays:
    # that cell is no cell of data/retired.json.
    RIVER_CUT = [(5943, 1723), (5864, 2002), (5865, 1836)]
    # Two retired places had no square of their own in the picture: Абри's ФСЦ
    # airfield 529 (its name over the river's dark bank) and Blackwater's block
    # post 317 (the base's square is on 5923,1838 beside it). The plan lists
    # them as every retired cell, and the painting finds nothing there.
    NO_SQUARE = [(5865, 1835), (5924, 1838)]
    check("every cell of data/retired.json loses its square, by itself",
          sorted(retired - set(plan.cells)), [])
    check("  ..those are the twenty-one of the six cuts: the (P) camps 124, 125, 130, Halfa's 468, 452,"
          " 456, 457, its ФСЦ's airfield 528 and base НИЛ-1 522, Абри's craftsmen 453, 454, 458, 459,"
          " air base 427, clan base Liberty 328, 327, ФСЦ airfield 529 and Blackwater's block post 317,"
          " the camps across the river 429 and 431, and Абри's clothing market 378",
          sorted(retired),
          sorted([(5876, 2012), (5942, 1723), (5968, 1726), (5969, 1729), (5969, 1731), (5969, 1732),
                  (5970, 1727), (5970, 1732), (6182, 1975)] + ABRI_CUT + RIVER_CUT))
    check("  ..and data/map_cells.json adds the eleven cells that had a name or a mark and no place:"
          " «Улучшение сетов 6-8», the KKND base, the kimberlite pipe, «Улучшение сетов 10-12», Абри's"
          " green mark, the second «Автосвалка», the two of Liberty by Абу-Хамед, Blackwater's, and the"
          " camps across the river of Абу-Хамед and Абри",
          sorted(set(plan.cells) - retired), sorted(LABEL_ONLY))
    check("  ..and the pirates' square by Абу-Хамед, where the camp 432 stood, stays; so do the digs and"
          " the ФСЦ's bases beside the camps across the river",
          sorted(c for c in [(6160, 1975), (6161, 1973), (5943, 1722), (5850, 1850), (5849, 1851),
                             (5864, 2001), (5863, 2002), (6168, 1988), (6167, 1989)] if c in plan.cells), [])
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
    check("the KKND caption is two boxes of tile 14011, above the base's cell; «База Liberty» two of"
          " tile 15811, right of the base's squares by Абу-Хамед (the line and its «y»'s tail); the three"
          " «Лагерь» of the camps across the river two each, right of the camps' squares: Вади-Хальфа's in"
          " tile 13753, Абри's in 14774, Донгола's in 16055 (the line and its «р»'s tail)",
          [(b, was, M.tile_of(b[0], b[1]), M.tile_of(b[2], b[3])) for b, was, _ in plan.captions],
          [((47879, 14049, 47920, 14057), "Кланбаза KKND", 14011, 14011),
           ((47879, 14058, 47910, 14067), "Кланбаза KKND", 14011, 14011),
           ((49996, 15833, 50048, 15841), "База Liberty", 15811, 15811),
           ((50041, 15842, 50046, 15843), "База Liberty", 15811, 15811),
           ((47553, 13785, 47583, 13793), "Лагерь", 13753, 13753),
           ((47572, 13794, 47575, 13795), "Лагерь", 13753, 13753),
           ((46809, 14807, 46839, 14815), "Лагерь", 14774, 14774),
           ((46828, 14816, 46831, 14817), "Лагерь", 14774, 14774),
           ((46921, 16016, 46951, 16024), "Лагерь", 16055, 16055),
           ((46940, 16025, 46944, 16026), "Лагерь", 16055, 16055)])
    check("the tiles a change can touch, a square's frame reaching a pixel past its cell: НИЛ-1's and the"
          " camp 429's, Halfa's two, KKND's and the two below it, the kimberlite pipe's, Абри's island"
          " camp's, Абри's, Blackwater's east of it, the two of Liberty by Абри, Абу-Хамед's two, Донгола's,"
          " Абу-Хамед's camp's across the river; and the war zones' (Донгола's on two, 16054 the other)",
          plan.tiles(), [13753, 13754, 14010, 14011, 14266, 14267, 14531, 14774, 14775, 14777, 15032, 15288,
                         15809, 15811, 16054, 16055, 16064])
    # The camps across the river had each a war zone painted round them
    # (the owner, 2026-10-12: «ты с карты не убрал лагеря за рекой»): a red
    # tint over a circle 245 pixels across with dark blue arrows into it,
    # Донгола's on two tiles with a seam where they meet.
    check("the four war zones of the camps across the river, each on the tiles it was painted on, its circle"
          " round the camp's village, three arrows each and Донгола's seam",
          [(z.was, z.tiles, M.tile_of(int(z.centre[0]), int(z.centre[1])), round(z.radius),
            len(z.arrows), len(z.seams)) for z in plan.zones],
          [("429 Вади-Хальфа", [13753], 13753, 122, 3, 0), ("430 Абри", [14774], 14774, 122, 3, 0),
           ("431 Донгола", [16054, 16055], 16054, 123, 3, 1), ("432 Абу-Хамед", [16064], 16064, 122, 3, 0)])
    camp_px = {429: (5943, 1723), 430: (5850, 1851), 431: (5864, 2002), 432: (6168, 1989)}
    check("  ..each camp's square on its circle's rim or inside it",
          [round(math.hypot(8 * camp_px[int(z.was[:3])][0] + 4 - z.centre[0],
                            8 * camp_px[int(z.was[:3])][1] + 4 - z.centre[1]) - z.radius) <= 5
           for z in plan.zones], [True] * 4)
    check("  ..the tint pure red, at an alpha of 0.09-0.10, nothing of it in the middle",
          (plan.tint.rgb, [0.09 <= (z.alpha or plan.tint.alpha) <= 0.10 for z in plan.zones],
           0 < plan.tint.clear < plan.tint.full < 122), ((255, 0, 0), [True] * 4, True))
    zone_px = {z.was: set().union(*[M.polygon_pixels(p) for p in z.arrows + z.seams]) for z in plan.zones}
    check("  ..every arrow and seam on its zone's tiles, and none of them over another",
          ([sorted({M.tile_of(*p) for p in px} - set(z.tiles)) for z, px in zip(plan.zones, zone_px.values())],
           sum(len(px) for px in zone_px.values()) == len(set().union(*zone_px.values()))),
          ([[], [], [], []], True))
    check("  ..the letters «Поселок» painted over the arrows of Вади-Хальфа and Абри in a box each",
          [z.letters for z in plan.zones], [[(47489, 13688, 47525, 13696)], [(46732, 14713, 46768, 14718)], [], []])
    check("polygon_pixels: a square's points, its edges and corners counted, and a triangle's",
          (sorted(M.polygon_pixels([(0, 0), (3, 0), (3, 2), (0, 2)])) == [(x, y) for x in range(4) for y in range(3)],
           sorted(M.polygon_pixels([(0, 0), (4, 0), (0, 4)]))
           == sorted((x, y) for x in range(5) for y in range(5) if x + y <= 4)),
          (True, True))

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
    TINT = {"rgb": [255, 0, 0], "alpha": 0.09, "clear": 20, "full": 30, "edge": 2, "why": "x"}
    ZONE = {"was": "Z", "why": "x", "tiles": [0], "centre": [100, 100], "radius": 40,
            "arrows": [[[10, 10], [30, 10], [30, 20]]], "letters": [[40, 40, 60, 50]]}
    check("a zone loads with its tint; refused: with no tint, without its why, off its tiles (its centre, an"
          " arrow's point, its letters), a tint without its why or of an alpha past a half, two zones of a name",
          (refused({"tint": TINT, "zones": [ZONE]}),
           bool(refused({"zones": [ZONE]})),
           bool(refused({"tint": TINT, "zones": [dict(ZONE, why="")]})),
           bool(refused({"tint": TINT, "zones": [dict(ZONE, centre=[300, 100])]})),
           bool(refused({"tint": TINT, "zones": [dict(ZONE, arrows=[[[10, 10], [300, 10], [30, 20]]])]})),
           bool(refused({"tint": TINT, "zones": [dict(ZONE, letters=[[250, 10, 260, 20]])]})),
           bool(refused({"tint": dict(TINT, why=""), "zones": [ZONE]})),
           bool(refused({"tint": dict(TINT, alpha=0.6), "zones": [ZONE]})),
           bool(refused({"tint": TINT, "zones": [ZONE, ZONE]}))),
          (None, True, True, True, True, True, True, True, True))

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

    def paint(x, y, colour, off=(0, 0), centre=None, bang=None):
        """A square in the original's way: a 7x7 fill in a dotted outline, its
        9x9 frame on the cell's corner or one pixel off it; centre a 3x3 in
        its middle, bang an airfield's «!» as the map has it (a bar of three
        and a dot in the fill's middle column: four pixels, as few as the
        painter takes for a «!»)."""
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
        if bang:
            for j_ in (2, 3, 4, 6):
                picture_rgb[(X0 + 4, Y0 + j_)] = bang

    GREEN, RED, TAN, BLUE, WHITE = (12, 104, 2), (120, 24, 30), (204, 181, 110), (16, 16, 245), (255, 255, 255)
    paint(10, 10, GREEN)              # goes
    paint(11, 10, RED)                # stays, right of it: they share an outline
    paint(10, 11, GREEN)              # goes, below the first: one region with it
    paint(9, 12, TAN)                 # stays, corner to corner with the second
    paint(31, 5, GREEN)               # goes, on the tile's right edge: its outline is in the next tile
    paint(20, 20, RED, (0, -1), WHITE)  # goes, a clan base drawn a pixel high
    paint(40, 10, BLUE, centre=WHITE)  # stays, far from everything
    paint(36, 20, BLUE, bang=WHITE)   # goes, an airfield (Вади-Хальфа's ФСЦ, 2026-10-10)
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
    ERASE = {(10, 10): "t", (10, 11): "t", (31, 5): "t", (20, 20): "t", (36, 20): "t",
             (25, 25): "nothing painted there"}
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
        """What map_cells.apply does, kept apart: the war zones taken off
        (laid), then the squares and captions painted over (painted)."""
        read = tiles.get
        canvas = M.Canvas(read)
        before_sq = M.Squares(M.Canvas(read))
        laid, zreport = M.clear_zones(canvas, plan_)
        found, kept, painted, report = M.erase(canvas, plan_)
        out, blocks = canvas.encode()
        new = {M.tile_path(n): b for n, b in out.items()}
        after_canvas = M.Canvas(lambda p: new.get(p) or read(p))
        return dict(found=found, kept=kept, painted=painted, laid=laid, report=zreport + report, out=new,
                    blocks=blocks,
                    before=M.Canvas(read), after=after_canvas, before_sq=before_sq,
                    after_sq=M.Squares(after_canvas))

    r = run(made, made_plan)
    check("each square that goes is found, the clan base's a pixel high, the airfield's blue with its «!»;"
          " the cell with nothing on it says so",
          ({c: (sq[0] - 8 * c[0], sq[1] - 8 * c[1], sq[2]) for c, sq in r["found"].items()},
           [line for line in r["report"] if "no square" in line]),
          ({(10, 10): (0, 0, ("green",)), (10, 11): (0, 0, ("green",)), (31, 5): (0, 0, ("green",)),
            (20, 20): (0, -1, ("red", "white")), (36, 20): (0, 0, ("blue", "white"))},
           ["25,25: no square painted on the cell"]))
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
        """How far the pixels not painted (nor laid by a war zone) moved, over
        the tiles that changed: (largest, share of those that moved at all
        that moved by 2 or less)."""
        most, count, small = 0, 0, 0
        for path in rr["out"]:
            n = int(path.rsplit("/", 1)[1].split(".")[0])
            X0, Y0 = (n % 256) * 256, (n // 256) * 256
            for X in range(X0, X0 + 256):
                for Y in range(Y0, Y0 + 256):
                    if (X, Y) in rr["painted"] or (X, Y) in rr["laid"]:
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
            stray[n] = sorted(got - painted_blocks(rr["painted"] | rr["laid"], n, J.Jpeg(tiles_before[path])))
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
           len([x for x in M.apply(lambda p: None, made_plan)[1] if "no tile" in x])), ({}, 7))

    made420 = {M.tile_path(0): make_tile(0, (2, 2)), M.tile_path(1): make_tile(1, (2, 2))}
    r4 = run(made420, made_plan)
    # The airfield's «!» is a column one pixel wide: on 4:2:0 each of its
    # pixels shares its colour with a blue one beside it, comes out light
    # blue, neither white nor the fill, and the square is not seen -- so
    # nothing is painted there, and the cell says so. No tile of the map that
    # holds a square to erase is 4:2:0 (the real map's check below).
    check("on 4:2:0 tiles the same squares go and the same stay, but the airfield's: there its «!» of"
          " one pixel's width is no white, the square is not seen and is left as it was",
          (sorted(r4["found"]), sorted(r4["kept"]), {c: r4["after_sq"].at(*c) for c in ERASE},
           [r4["after_sq"].at(*c) == r4["before_sq"].at(*c) for c in KEPT],
           sorted(line for line in r4["report"] if "no square" in line),
           [p for p in r4["painted"] if 8 * 36 <= p[0] <= 8 * 36 + 8 and 8 * 20 <= p[1] <= 8 * 20 + 8]),
          (sorted(c for c in r["found"] if c != (36, 20)), sorted(r["kept"]), {c: None for c in ERASE},
           [True] * len(KEPT),
           ["25,25: no square painted on the cell", "36,20: no square painted on the cell"], []))
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

    # --- a war zone on a made map --------------------------------------------------------------
    # The circle as the map's makers painted it: pure red laid over the
    # ground at an alpha rising from the middle to the rim, on tile 0 only
    # though the circle runs on into tile 1 (Вади-Хальфа's stops at its
    # tile's top row so), a thin yellowish line on its rim; an opaque dark
    # blue arrow over it; a tan square painted over the tint.
    print("a war zone on a made map")
    tint = M.Tint((255, 0, 0), 0.09, 20, 30, 2.0)
    NAVY = (20, 40, 120)
    arrow = [(186, 92), (191, 89), (218, 110), (213, 115)]
    arrow_px = M.polygon_pixels(arrow)
    zone = M.Zone("Z", "t", [0], (225.4, 120.6), 40.0, arrows=[[(183, 91), (191, 85), (222, 109), (214, 119)]])
    zplan = M.Plan({}, [], {}, zones=[zone], tint=tint)
    zone_px = M.polygon_pixels(zone.arrows[0])
    SQ = (192, 136)

    def zone_rgb(X, Y):
        """The made picture: (r, g, b) of a pixel, and that of the ground under it."""
        g = ground(X, Y)
        p = g
        r_ = math.hypot(X + 0.5 - zone.centre[0], Y + 0.5 - zone.centre[1])
        if X < 256:
            a = M.zone_alpha(tint, zone, r_)
            p = tuple((1 - a) * c + a * t for c, t in zip(p, tint.rgb))
            # the line: a blue down by 12 at its middle, 0.3 inside the rim
            p = (p[0], p[1], p[2] - 12 * max(0.0, 1 - abs(r_ - zone.radius + 0.3) / 1.2))
        if (X, Y) in arrow_px:
            p = NAVY
        if SQ[0] <= X <= SQ[0] + 8 and SQ[1] <= Y <= SQ[1] + 8:
            edge = X in (SQ[0], SQ[0] + 8) or Y in (SQ[1], SQ[1] + 8)
            if not edge:
                p = TAN
            elif (X + Y) % 4:
                p = OUTLINE
        return p, g

    def zone_tile(tx):
        planes = [[[0] * 256 for _ in range(256)] for _ in range(3)]
        for Y in range(256):
            for x in range(256):
                v = ycc(zone_rgb(256 * tx + x, Y)[0])
                for ci in range(3):
                    planes[ci][Y][x] = max(0, min(255, int(round(v[ci]))))
        fine = tuple(tuple(max(1, (q + 2) // 4) for q in t) for t in (J.STD_LUMA, J.STD_CHROMA))
        return J.make(256, 256, planes, qtables=fine)

    zmade = {M.tile_path(0): zone_tile(0), M.tile_path(1): zone_tile(1)}
    rz = run(zmade, zplan)
    check("the arrow's polygon of the data holds the arrow painted", sorted(arrow_px - zone_px), [])
    check("only the zone's tile changes, though the circle runs on into the next one",
          sorted(rz["out"]), [M.tile_path(0)])

    def toward(canvas, pixels, ch):
        """Mean and mean size of (canvas - ground) in an RGB channel over pixels."""
        d = [M.rgb(canvas.original(*p))[ch] - zone_rgb(*p)[1][ch] for p in pixels]
        return sum(d) / len(d), sum(abs(v) for v in d) / len(d)

    sq_px = M.frame_pixels((SQ[0], SQ[1], ("tan",)))
    disk = [(X, Y) for X in range(186, 256) for Y in range(82, 160)
            if 32 <= math.hypot(X + 0.5 - 225.4, Y + 0.5 - 120.6) <= 37
            and (X, Y) not in zone_px and (X, Y) not in sq_px]
    rim = [(X, Y) for X in range(186, 256) for Y in range(82, 160)
           if abs(math.hypot(X + 0.5 - 225.4, Y + 0.5 - 120.6) - 40) < 0.8
           and (X, Y) not in zone_px and (X, Y) not in sq_px]
    gb, ga = toward(rz["before"], disk, 1), toward(rz["after"], disk, 1)
    bb, ba = toward(rz["before"], rim, 2), toward(rz["after"], rim, 2)
    check("the tint is taken off: green under the circle's strongest tint off the ground by %+.1f on average"
          " before, %+.1f after (%.1f in size); blue on the rim's line %+.1f before, %+.1f after"
          % (gb[0], ga[0], ga[1], bb[0], ba[0]),
          (gb[0] < -12, abs(ga[0]) < 1.5, ga[1] < 3, bb[0] < -5, abs(ba[0]) < 2.5), (True,) * 5)
    blue_left = [p for p in zone_px - sq_px if (lambda c: c[2] > c[0] + 20)(M.rgb(rz["after"].original(*p)))]
    errors = [abs(rz["after"].original(*p)[0] - ycc(zone_rgb(*p)[1])[0]) for p in zone_px]
    check("the arrow is gone (%d of its blue pixels left) and ground like the ground under it is in its"
          " place: luma off by %.1f on average" % (len(blue_left), sum(errors) / len(errors)),
          (blue_left, sum(errors) / len(errors) < 14), ([], True))
    check("the square painted over the tint stays where it was, as it was (largest change of a sample)",
          (rz["after_sq"].at(24, 17), max(diff(rz["before"].original(*p), rz["after"].original(*p))
                                          for p in sq_px) <= 3),
          (rz["before_sq"].at(24, 17), True))
    stray, count = only_painted(zmade, rz)
    most, share = moved(rz, zmade)
    check("only blocks with a pixel of the zone laid change (%d), and a pixel not laid moves by its rounding:"
          " %d at most" % (count, most), (stray, most <= 16), ({0: []}, True))
    check("the same picture and plan give the same bytes", run(zmade, zplan)["out"] == rz["out"], True)
    check("a client without the zone's tile gets nothing and is told",
          M.clear_zones(M.Canvas(lambda p: None), zplan),
          (set(), ["zone Z: no tile globalmap/full/0.jpg in this client, left alone"]))

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

    # --- painting a square on: a place of ours put on the map (data/map_cells.json "paint") -------
    print("a square painted on")
    PAINT = M.Plan({}, [], {}, {(25, 15): ("green", "t"), (11, 10): ("green", "t")})
    check("the plan's tiles take in a painted cell's", PAINT.tiles(), [0])
    for name, tiles in (("4:4:4", made), ("4:2:0", made420)):
        canvas = M.Canvas(tiles.get)
        report = M.paint(canvas, PAINT)
        out, _blocks = canvas.encode()
        new = {M.tile_path(n): b for n, b in out.items()}
        after = M.Squares(M.Canvas(lambda p: new.get(p) or tiles.get(p)))
        check("%s: a green square on open sand, found where the original's are, as theirs are" % name,
              after.at(25, 15), (200, 120, ("green",)))
        check("  ..a cell that has a square already is left as it is, and said so",
              (after.at(11, 10), [line for line in report if "already" in line]),
              (r["before_sq"].at(11, 10), ["11,10: a square is painted there already, left alone"]))
        stray, count = only_painted(tiles, dict(out=new, painted=set(M.square(25, 15, M.PALETTE["green"]))))
        check("  ..and only the blocks its pixels fall in change (%d)" % count, (stray, count > 0),
              ({0: []}, True))
    check("a client without the tile gets nothing and is told",
          M.apply(lambda p: None, PAINT), ({}, ["11,10: no tile globalmap/full/0.jpg in this client, left alone",
                                               "25,15: no tile globalmap/full/0.jpg in this client, left alone"]))
    mc = os.path.join(W, "map_cells.json")

    def load_paint(paint):
        with open(mc, "w", encoding="utf-8") as fh:
            json.dump({"cells": {"10,10": "t"}, "paint": paint}, fh)
        try:
            return sorted(M.load(mc, os.path.join(ROOT, "data", "retired.json")).paint.items())
        except ValueError:
            return "refused"

    check("map_cells.json 'paint': 'x,y' -> {colour, why}",
          load_paint({"25,15": {"colour": "red", "why": "a place of ours"}}),
          [((25, 15), ("red", "a place of ours"))])
    check("  ..a colour the map has not, no why, or a cell that is also erased: refused",
          [load_paint(p) for p in ({"25,15": {"colour": "pink", "why": "t"}}, {"25,15": {"colour": "red"}},
                                   {"10,10": {"colour": "red", "why": "t"}})], ["refused"] * 3)
    import world
    check("every cell the repository paints on holds a place of ours (data/settlements.json,"
          " data/locations)", [c for c in plan.paint if world.settlements().get(c) not in world.overlay_ids()],
          [])

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
        painted_already = [M.tile_path(n) for n in plan.tiles()
                           if hashlib.sha256(read(M.tile_path(n))).hexdigest() != base.get(M.tile_path(n))]
        check("the tiles a change can touch are the original's, as client/base.txt has them",
              painted_already, [])
        if painted_already:
            # An installed client (the launcher's since 2026-10-06) carries the
            # release's painted tiles, the owner's since 2026-10-10: nothing
            # below can be held on them, and the check above has said so.
            print("  -- not the original's tiles: %s; the real map needs the original ones (the"
                  " release store by client/base.txt)" % ", ".join(painted_already))
        else:
            real = run(every, plan)
            odd = {(5984, 1759): (0, -1, ("red", "white")), (6265, 1821): (0, 0, ("black", "orange")),
                   (5970, 1727): (0, 0, ("blue", "white")), (5863, 1836): (0, 0, ("red",)),
                   (5906, 1888): (0, 0, ("red", "white")), (6248, 1979): (0, 0, ("red", "white"))}
            check("each of the thirty cells with a square has it found: twenty-four green (Blackwater's"
                  " with its black centre among them), KKND's dark red with white a pixel high, Liberty's two"
                  " dark red with white, the second «Автосвалка»'s dark red, the kimberlite pipe's"
                  " black-and-orange hatch, Halfa's ФСЦ airfield's blue with «!»",
                  {c: (sq[0] - 8 * c[0], sq[1] - 8 * c[1], sq[2]) for c, sq in real["found"].items()},
                  {c: odd.get(c, (0, 0, ("green",))) for c in plan.cells if c not in NO_SQUARE})
            check("  ..and nothing is reported missing but the two retired places that had none of their"
                  " own (Абри's airfield, Blackwater's block post)",
                  [x for x in real["report"] if ": no " in x],
                  ["%d,%d: no square painted on the cell" % c for c in NO_SQUARE])
            check("  ..every tile that holds one is 4:4:4, where a «!» one pixel wide keeps its white",
                  sorted({M.tile_of(X0 + 4, Y0 + 4) for X0, Y0, _k in real["found"].values()
                          if [(c.h, c.v) for c in J.Jpeg(read(M.tile_path(M.tile_of(X0 + 4, Y0 + 4)))).comps]
                          != [(1, 1)] * 3}), [])
            check("fourteen tiles change: 13753 for НИЛ-1 and the camp 429 with its letters and war zone, 13754"
                  " and 14010 in Halfa, 14011 for KKND, 14531 the kimberlite pipe, 14774 Абри's island camp and its"
                  " zone, 14775 Абри, 14777 Blackwater, 15288 Liberty by Абри, 15809 Абу-Хамед, 15811 Liberty by"
                  " Абу-Хамед, 16054 and 16055 Донгола's camp's zone, 16055 Донгола and its camp, 16064"
                  " Абу-Хамед's camp across the river and its zone",
                  sorted(real["out"]),
                  sorted(M.tile_path(n) for n in (13753, 13754, 14010, 14011, 14531, 14774, 14775, 14777, 15288,
                                                  15809, 15811, 16054, 16055, 16064)))
            check("no square is left on the thirty-two cells", {c: real["after_sq"].at(*c) for c in plan.cells},
                  {c: None for c in plan.cells})
            around = sorted({(x + dx, y + dy) for x, y in plan.cells for dx in range(-3, 4) for dy in range(-3, 4)}
                            - set(plan.cells))
            shifted = [c for c in around if real["after_sq"].at(*c) != real["before_sq"].at(*c)]
            check("every other square within three cells is where it was, as it was (%d squares)"
                  % sum(1 for c in around if real["before_sq"].at(*c)), shifted, [])
            KEPT_HALFA = {(5969, 1728): ("green",), (5970, 1729): ("red",), (5970, 1730): ("black",),
                          (5969, 1733): ("tan",), (5971, 1731): ("tan",), (5968, 1727): ("green",),
                          (5969, 1727): ("green",), (5971, 1727): ("black", "orange"), (5970, 1728): ("red",),
                          (5943, 1722): ("tan",),
                          (5876, 2011): ("green",), (5877, 2012): ("green",),
                          (5876, 2013): ("green",), (6183, 1975): ("green",), (6182, 1976): ("green",),
                          (5864, 2001): ("tan",), (5863, 2002): ("green",), (5850, 1850): ("tan",),
                          (5849, 1851): ("green",), (6168, 1988): ("tan",), (6167, 1989): ("green",)}
            check("  ..among them the owner's neighbours named in the research: the masters' camp 95, arena 78,"
                  " the black market 102, «Генри Мл.» 43, the crates 108, the old market; around the airfield"
                  " the quarter 36, the dump 100's hatch and the arena 59, by НИЛ-1 and the camp 429 the dig"
                  " 433; Донгола's 96, 97 and 455; Абу-Хамед's 127 and 126; beside the camps across the river"
                  " the digs 435, 434, 436 and the ФСЦ's bases НИЛ-3, НИЛ-2, НИЛ-4",
                  {c: (real["after_sq"].at(*c) or (0, 0, None))[2] for c in KEPT_HALFA}, KEPT_HALFA)
            KEPT_ABRI = {(5860, 1835): ("green",), (5861, 1835): ("green",), (5862, 1835): ("green",),
                         (5863, 1835): ("red",),
                         (5862, 1836): ("tan",), (5864, 1836): ("green",),
                         (5860, 1838): ("tan",), (5864, 1838): ("tan",)}
            check("  ..and Абри's places that stay beside its cuts: the port market 187, the quarter 188, the"
                  " slums 255, the dump 289 under the first «Автосвалка»,"
                  " Хаксли's fields 261, the graveyard 368, the hippies 191, the totem 262",
                  {c: (real["after_sq"].at(*c) or (0, 0, None))[2] for c in KEPT_ABRI}, KEPT_ABRI)
            check("  ..and the pirates' two dark red squares by Абу-Хамед, where the camp 432 stood on the first,"
                  " are where they were, as they were",
                  [real["after_sq"].at(*c) == real["before_sq"].at(*c) and "red" in real["before_sq"].at(*c)[2]
                   for c in ((6160, 1975), (6161, 1973))], [True, True])
            check("  ..and the squares beside those that go keep their outlines (largest change of a sample)",
                  max(diff(real["before"].original(*p), real["after"].original(*p))
                      for sq in real["kept"].values() for p in M.frame_pixels(sq)) <= 16, True)
            stray, count = only_painted(every, real)
            check("only blocks with a pixel painted change; every other block of every tile keeps its"
                  " coefficients (%d changed)" % count,
                  (stray, count > 0),
                  ({n: [] for n in (13753, 13754, 14010, 14011, 14531, 14774, 14775, 14777, 15288, 15809, 15811,
                                    16054, 16055, 16064)}, True))
            most, share = moved(real, every)
            check("  ..and a pixel not painted in such a block moves by its rounding: %d at most, %.0f%% of those"
                  " that move by 2 or less" % (most, 100 * share), (most <= 16, share >= 0.9), (True, True))
            boxes = [(X, Y) for (x0, y0, x1, y1), was, _ in plan.captions if was != "Лагерь"
                     for X in range(x0, x1 + 1) for Y in range(y0, y1 + 1)]
            dark_before = sum(1 for p in boxes if real["before"].original(*p)[0] < 110)
            dark_after = sum(1 for p in boxes if real["after"].original(*p)[0] < 110)
            check("the letters «Кланбаза KKND» and «База Liberty» are gone: dark pixels in their boxes %d"
                  " before, %d after"
                  % (dark_before, dark_after), (dark_before > 100, dark_after < 10), (True, True))

            # The three «Лагерь» stand on ground as dark as their letters in
            # places (Донгола's red bank, Абри's river edge), so no threshold of
            # darkness tells them: their strokes do -- the step in brightness
            # from a pixel to the next, letter to rim, of which the ground's
            # grain has a fraction.
            def strokes(canvas, box):
                x0, y0, x1, y1 = box
                return sum(abs(canvas.original(X + 1, Y)[0] - canvas.original(X, Y)[0])
                           + abs(canvas.original(X, Y + 1)[0] - canvas.original(X, Y)[0])
                           for X in range(x0, x1) for Y in range(y0, y1))
            camps = {}
            for box, was, _why in plan.captions:
                if was == "Лагерь":
                    k = M.tile_of(box[0], box[1])
                    b, a = camps.get(k, (0, 0))
                    camps[k] = (b + strokes(real["before"], box), a + strokes(real["after"], box))
            check("the three «Лагерь» of the camps across the river are gone: the steps of brightness in their"
                  " boxes after are under two fifths of before (%s)"
                  % ", ".join("%d: %d -> %d" % (k, b, a) for k, (b, a) in sorted(camps.items())),
                  {k: a < 0.4 * b for k, (b, a) in camps.items()}, {13753: True, 14774: True, 16055: True})
            check("no fill keeps its square's colour (Донгола's ground is red of its own)",
                  colour_left(real), {c: 0 for c in real["found"]})
            check("  ..nor brings in what its ground has not: no painted pixel darker or brighter than the ground"
                  " around it by more than 15 (Донгола's first patch carried in the river's black line, 2-3 pixels"
                  " wide; Хальфа's lake shore is really there)", beyond(real), {})
            check("  ..and every square is painted from a patch of photograph",
                  [line.strip() for line in real["report"] if "smooth" in line and not line.startswith("zone ")],
                  [])
            out_real, _report = M.apply(read)
            check("map_cells.apply gives these tiles", out_real == real["out"], True)

            # The war zones of the camps across the river (the owner,
            # 2026-10-12: «ты с карты не убрал лагеря за рекой»).
            check("the war zones change their own tiles and none other",
                  sorted({M.tile_of(*p_) for p_ in real["laid"]}), sorted({n for z in plan.zones for n in z.tiles}))

            def rim_steps(canvas, z, skip):
                """The step across a zone's rim, the ground 3-6 pixels inside
                less that 3-6 outside, in each of Y, Cb, Cr: the middle of
                the steps of 120 arcs."""
                cx, cy = z.centre
                arcs = {}
                for Y in range(int(cy - z.radius - 7), int(cy + z.radius + 8)):
                    for X in range(int(cx - z.radius - 7), int(cx + z.radius + 8)):
                        if M.tile_of(X, Y) not in z.tiles or (X, Y) in skip:
                            continue
                        d = math.hypot(X + 0.5 - cx, Y + 0.5 - cy) - z.radius
                        if 3 <= abs(d) <= 6:
                            a = int((math.atan2(Y + 0.5 - cy, X + 0.5 - cx) + math.pi) / (2 * math.pi) * 120) % 120
                            arcs.setdefault((a, d > 0), []).append(canvas.original(X, Y))
                steps = []
                for a in range(120):
                    if len(arcs.get((a, False), ())) >= 4 and len(arcs.get((a, True), ())) >= 4:
                        steps.append([M._median(arcs[(a, False)], i) - M._median(arcs[(a, True)], i)
                                      for i in range(3)])
                return [round(M._median(steps, i), 1) for i in range(3)]

            kept_over = {}
            fills = set()
            for z in plan.zones:
                sq_ = M.Squares(real["before"])
                px = set()
                for y in range(int(z.centre[1] - z.radius) // 8 - 1, int(z.centre[1] + z.radius) // 8 + 2):
                    for x in range(int(z.centre[0] - z.radius) // 8 - 1, int(z.centre[0] + z.radius) // 8 + 2):
                        sq = sq_.at(x, y)
                        if sq is not None and M.painted_square(real["before"], sq) and (x, y) not in plan.cells:
                            px |= M.frame_pixels(sq)
                            fills |= {(sq[0] + i, sq[1] + j) for i in range(1, 8) for j in range(1, 8)}
                for box in z.letters:
                    px |= M.letters_pixels(real["before"], box)
                    fills |= M.letters_pixels(real["before"], box)
                kept_over[z.was] = px
            marks = {z.was: set().union(*[M.polygon_pixels(p_) for p_ in z.arrows + z.seams]) for z in plan.zones}
            steps = {z.was: (rim_steps(real["before"], z, marks[z.was] | kept_over[z.was]),
                             rim_steps(real["after"], z, marks[z.was] | kept_over[z.was])) for z in plan.zones}
            check("each circle's tint is gone: the step across its rim, inside less outside, in Y, Cb, Cr: %s"
                  % "; ".join("%s %s -> %s" % (w, b, a) for w, (b, a) in steps.items()),
                  {w: (b[2] >= 6, abs(a[0]) <= 4 and abs(a[1]) <= 1.5 and abs(a[2]) <= 1.5)
                   for w, (b, a) in steps.items()},
                  {z.was: (True, True) for z in plan.zones})

            def navy(canvas, pixels):
                return sum(1 for p_ in pixels if (lambda c: c[2] > c[0] + 20)(M.rgb(canvas.original(*p_))))
            gone = {z.was: (navy(real["before"], marks[z.was] - kept_over[z.was]),
                            navy(real["after"], marks[z.was] - kept_over[z.was])) for z in plan.zones}
            check("the arrows are gone: dark blue pixels in their polygons before and after: %s"
                  % "; ".join("%s %d -> %d" % (w, b, a) for w, (b, a) in gone.items()),
                  {w: (b > 500, a) for w, (b, a) in gone.items()}, {z.was: (True, 0) for z in plan.zones})
            seam_rows = [Y for Y in range(15890, 16112) if not 15991 <= Y <= 15999]

            def dip(canvas):
                d = sorted((canvas.original(46847, Y)[0] + canvas.original(46848, Y)[0]) / 2
                           - (canvas.original(46843, Y)[0] + canvas.original(46852, Y)[0]) / 2 for Y in seam_rows)
                return d[len(d) // 2]
            check("Донгола's seam is gone: the two columns where its tiles meet darker than the ground beside"
                  " them by %.1f before, %.1f after" % (-dip(real["before"]), -dip(real["after"])),
                  (dip(real["before"]) < -15, abs(dip(real["after"])) < 4), (True, True))
            check("the squares painted over the zones and the letters over their arrows stay as they were: the"
                  " squares' fills and the letters with the pixels round them (%d pixels, the largest change of a"
                  " sample; the outlines beside a camp's square that goes are the check of the squares above)"
                  % len(fills),
                  max(diff(real["before"].original(*p_), real["after"].original(*p_)) for p_ in fills) <= 3, True)
            check("a local run serves the same bytes (bootstrap_http)",
                  (lambda served_: {p: served_.get(p) == data for p, data in out_real.items()})(M.Served(RES)),
                  {p: True for p in out_real})

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
