#!/usr/bin/env python3
"""Where the drawn mountains have to give way to what a location declares.

The rock on the map is read off a photograph of the client's own map tiles,
and a photograph is evidence, not testimony. A location file is testimony: it
says in its own outzones which way a player may leave, and that came from the
people who built the world.

Where the two disagree the file wins, and this writes down every such cell so
the disagreement is a list somebody can read rather than a threshold somebody
has to trust. Eighteen exits out of 951 lead into a cell the picture calls
rock; without this the map would refuse a step the game itself promises, and
the player would walk into a wall that is not in any file.

    python3 data/build_terrain_repairs.py

Writes data/terrain_repairs.json.
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault(
    "LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res")

import world  # noqa: E402

STEP = {"W": (-1, 0), "E": (1, 0), "N": (0, -1), "S": (0, 1)}


def main():
    (gx0, gy0, _gx1, _gy1), rows = world.terrain()
    rock = {(gx0 + x, gy0 + y)
            for y, row in enumerate(rows)
            for x, c in enumerate(row) if c == "#"}

    with io.open(os.path.join(HERE, "settlements.json"), encoding="utf-8") as fh:
        cells = json.load(fh)["cells"]
    with io.open(os.path.join(HERE, "exits_sides.json"), encoding="utf-8") as fh:
        summary = json.load(fh)["summary"]

    opened = {}
    for key, loc in cells.items():
        gx, gy = (int(v) for v in key.split(","))
        rec = summary.get(str(loc))
        if not rec:
            continue
        for side in rec.get("sides", []):
            d = STEP.get(side)
            if d is None:
                continue                      # a door, not a map edge
            n = (gx + d[0], gy + d[1])
            if n in rock:
                opened.setdefault("%d,%d" % n, []).append(
                    "%s [%s] на %s" % (rec.get("title", "?"), loc, side))

    doc = {
        "_": ("Клетки, которые фотография карты называет скалой, а файл "
              "локации объявляет своим выходом. Спор решается в пользу файла: "
              "он от авторов мира, а растр — наше прочтение картинки. "
              "Построено data/build_terrain_repairs.py, применяется "
              "world.passable() поверх data/map_terrain.json."),
        "opened": {k: sorted(set(v)) for k, v in sorted(opened.items())},
    }
    out = os.path.join(HERE, "terrain_repairs.json")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print("%s: открыто %d клеток по %d объявленным выходам"
          % (out, len(opened), sum(len(v) for v in opened.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
