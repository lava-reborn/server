"""Rebuild data/borders.json: the rock scene that stands on each rim cell.

PROPOSAL, not a recovered table. The server's own cell->location table is
gone; what the client still ships is the kit the designers built rock out of,
and the kit says exactly how a wall was made. See recon/analysis/borders.md
for the evidence. The short of it:

  * Impassable ground in LAVA was never a bitmap. The client has no terrain
    of any kind (recon/analysis/borders.md §3). A cell is walled because the
    location standing on it has no outzone on that side -- the same node the
    exit code already reads. Every one of the eleven locations/desert
    templates carries all four side codes, so a cell the server names no file
    for is open in all four directions, whatever a photograph looks like.
  * res/locations/static ships a complete rock kit titled "Скалы": four
    sides in two variants each, four corners, four dead-end pockets, two
    passes, an island and a lake, all war=1, library="Mountains". Which side
    each one walls is read off its own outzones and is tabulated in
    travel.ROCK_WALL already.
  * The kit was placed cell by cell: the client also ships pvp=0 copies of
    three of the tiles (178 NoPvP_UpSide1, 179 NoPvP_UpSide2, 180
    NoPvP_LeftSide2), which only makes sense as the wall of the no-PvP
    starting area in the map's north-west corner.

So the rim of the world is a ring of these tiles, one per cell, the wall
facing out. This script writes that ring. It does not touch the server: the
ids it emits are the ones travel.ROCK_SIDE and travel.ROCK_CORNER already
name, so the table can be adopted or ignored.

A rim cell that already carries a settlement is left alone -- the two the
client lets us check (182 "Западные Предгорья" on gx 5833 and 322 "Северные
Предгорья" on gy 1600) have no outward exit of their own, which is what a
cell on the edge of the world is supposed to look like.

    python3 data/build_borders.py                    # the world's rectangle
    python3 data/build_borders.py --bounds captions  # the caption box it was
    python3 data/build_borders.py --bounds artwork   # every drawn cell
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world                                                     # noqa: E402

RES = world.RES

# The rectangle the server calls the world, and the ring is built on it.
SERVER_BOUNDS = (world.MAP_X[0], world.MAP_X[1], world.MAP_Y[0], world.MAP_Y[1])
# What it used to be: the bounding box of the 414 captions in
# res/database/locations.xml, nothing more. Its west and north edges are the
# real ones and stayed; its east and south are the ones the two settlements
# sitting on them argue with (303 "Выход с карьера" on 6305,1841 and 280
# "Шахта Мероэ" on 5943,2110 both have exits pointing outward).
CAPTION_BOUNDS = (5833, 6305, 1600, 2110)
# What res/globalmap/full actually draws: tiles tx 182..197, ty 50..66 at 32
# cells a tile. Past it the client has no picture to show at all. Its east and
# south edges are the world's; its west edge is nine cells beyond the
# "Западные Предгорья" the client's own captions put the wall at, so the world
# does not use it.
ARTWORK_BOUNDS = (5824, 6335, 1600, 2143)

# id -> the side its wall faces, read off the file's own outzones
# (recon/notes/borders_loc_geom.py). Same table as travel.ROCK_WALL.
SIDE_TILES = {          # wall faces ... : the two variants that tile a run
    "W": (12, 13),      # B_RightSide1/2_MWM  -- open N, E, S
    "E": (1, 2),        # B_LeftSide1/2_MWM   -- open W, N, S
    "N": (10, 11),      # B_DownSide1/2_MWM   -- open W, E, S
    "S": (15, 16),      # B_UpSide1/2_MWM     -- open W, N, E
}
CORNER_TILES = {        # walls facing ... : the tile
    ("W", "N"): 3,      # B_RightDownCorner_ARM -- open E, S
    ("E", "N"): 9,      # B_LeftDownCorner_ARM  -- open W, S
    ("W", "S"): 0,      # B_RightUpCorner_ARM   -- open N, E
    ("E", "S"): 8,      # B_LeftUpCorner_ARM    -- open W, N
}
CODE = {"1": "W", "2": "N", "3": "E", "4": "S"}


def load_json(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def settlement_cells():
    cells = dict(load_json("settlements.json")["cells"])
    for k, v in load_json("settlements_verified.json")["cells"].items():
        if v is None:
            cells.pop(k, None)
        else:
            cells[k] = v
    return {tuple(int(p) for p in k.split(",")): v for k, v in cells.items()}


def side_codes(loc_id):
    """The outzone side codes of a static file, as the letters W/N/E/S."""
    path = os.path.join(RES, "locations", "static", "%d.xml" % loc_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"<outzones\b[^>]*>(.*?)</outzones>", text, re.S)
    if not m:
        return set()
    body = re.sub(r"\s+", "", m.group(1))
    if len(body) % 5:
        return None
    return {CODE[body[i + 4]] for i in range(0, len(body), 5)
            if body[i + 4] in CODE}


def check_kit():
    """Refuse to write a table the shipped files do not back up."""
    for side, pair in SIDE_TILES.items():
        for loc_id in pair:
            codes = side_codes(loc_id)
            if codes is None:
                return "location %d is missing or unreadable" % loc_id
            if side in codes:
                return "location %d claims to be walled %s but has that exit" % (
                    loc_id, side)
            if codes != {"W", "N", "E", "S"} - {side}:
                return "location %d opens %s, expected the other three" % (
                    loc_id, "".join(sorted(codes)))
    for walls, loc_id in CORNER_TILES.items():
        codes = side_codes(loc_id)
        if codes is None:
            return "location %d is missing or unreadable" % loc_id
        if codes != {"W", "N", "E", "S"} - set(walls):
            return "corner %d opens %s, expected the two sides not in %s" % (
                loc_id, "".join(sorted(codes)), "".join(walls))
    return None


def ring(bounds, settlements):
    gx0, gx1, gy0, gy1 = bounds
    out = {}
    skipped = []
    for gx in range(gx0, gx1 + 1):
        for gy in range(gy0, gy1 + 1):
            walls = []
            if gx == gx0:
                walls.append("W")
            if gx == gx1:
                walls.append("E")
            if gy == gy0:
                walls.append("N")
            if gy == gy1:
                walls.append("S")
            if not walls:
                continue
            if (gx, gy) in settlements:
                skipped.append((gx, gy, settlements[(gx, gy)], walls))
                continue
            if len(walls) == 2:
                loc_id = CORNER_TILES[(walls[0], walls[1])]
            else:
                pair = SIDE_TILES[walls[0]]
                # Alternate the two variants along the run so a long wall is
                # not the same picture twice over, and so the same cell always
                # shows the same rocks.
                loc_id = pair[(gx + gy) % 2]
            out["%d,%d" % (gx, gy)] = loc_id
    return out, skipped


def main():
    bounds = SERVER_BOUNDS
    which = "server"
    if "--bounds" in sys.argv:
        arg = sys.argv[sys.argv.index("--bounds") + 1]
        if arg == "artwork":
            bounds, which = ARTWORK_BOUNDS, "artwork"
        elif arg == "captions":
            bounds, which = CAPTION_BOUNDS, "captions"
        elif arg != "server":
            gx0, gx1, gy0, gy1 = (int(v) for v in arg.split(","))
            bounds, which = (gx0, gx1, gy0, gy1), "given"

    bad = check_kit()
    if bad:
        sys.exit("the rock kit does not match the shipped files: " + bad)

    settlements = settlement_cells()
    cells, skipped = ring(bounds, settlements)
    gx0, gx1, gy0, gy1 = bounds
    w, h = gx1 - gx0 + 1, gy1 - gy0 + 1
    doc = {
        "version": 1,
        "built_by": "data/build_borders.py",
        "status": "PROPOSAL -- the original table is lost; see "
                  "recon/analysis/borders.md",
        "_": "Кольцо скал по периметру мира: клетка -> id локации из "
             "res/locations/static. Стена каждой плитки смотрит наружу; "
             "стороны чередуются двумя вариантами, углы берут свою плитку. "
             "Клетки периметра, на которых уже стоит посёлок, пропущены: "
             "их файл сам не имеет выхода наружу.",
        "bounds": {"gx0": gx0, "gx1": gx1, "gy0": gy0, "gy1": gy1,
                   "which": which},
        "tiles": {
            "side": {k: list(v) for k, v in SIDE_TILES.items()},
            "corner": {"".join(k): v for k, v in CORNER_TILES.items()},
            "note": "the side letter is the direction the wall faces, read "
                    "off each file's own outzones",
        },
        "skipped_settlement_cells": [
            {"cell": "%d,%d" % (gx, gy), "loc": loc, "walls": walls,
             "own_sides": "".join(sorted(side_codes(loc) or []))}
            for gx, gy, loc, walls in skipped],
        "cells": dict(sorted(cells.items(),
                             key=lambda kv: tuple(int(p)
                                                  for p in kv[0].split(",")))),
    }
    path = os.path.join(HERE, "borders.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("rectangle %dx%d (%s bounds %d..%d by %d..%d)"
          % (w, h, which, gx0, gx1, gy0, gy1))
    print("perimeter cells: %d" % (2 * (w + h) - 4))
    print("written: %d" % len(cells))
    print("left to their own settlement file: %d" % len(skipped))
    for gx, gy, loc, walls in skipped:
        own = "".join(sorted(side_codes(loc) or []))
        print("   %d,%d loc %-5d rim=%s own exits=%s%s"
              % (gx, gy, loc, "".join(walls), own or "-",
                 "" if not set(walls) & set(own)
                 else "   <-- still opens off the map"))
    print(path)


if __name__ == "__main__":
    main()
