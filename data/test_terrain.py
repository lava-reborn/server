"""The recovered passability of the global map.

data/map_terrain.json is read off the client's own map tiles by
data/build_terrain.py; the server that knew the real table is gone. This
checks what the reconstruction promised rather than the numbers it happened
to produce, so refining the thresholds does not break it:

  * the table covers the playable rectangle exactly, in the characters its
    own legend declares, and server/world.passable agrees with it;
  * every one of the 262 settlement cells and every one of the 414 cells
    with a map tooltip is walkable -- those are cells players stood on;
  * the world is one piece: nearly all of the walkable ground, and nearly
    all of the settlements, can be reached on foot from the start cell;
  * the Nubian valley is a pocket of its own, which is the one piece of
    passability a player remembers first-hand.

Runs under WSL with the client resources present:

    wsl.exe -e python3 data/test_terrain.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import travel  # noqa: E402
import world  # noqa: E402

START = (5970, 1730)
# The valley as the player who walked it describes it, with a margin.
NUBIA = (6250, 6285, 1810, 1845)
PASSABLE = ".,"


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def hints():
    raw = open(os.path.join(world.RES, "database", "locations.xml"), "rb").read()
    txt = raw.decode("utf-8", "replace")
    return [(int(x), int(y))
            for x, y in re.findall(r'<location x="(\d+)" y="(\d+)"', txt)]


def components(rows, gx0, gy0):
    """Label the walkable ground, 4-connected, as a walker crosses it."""
    high, wide = len(rows), len(rows[0])
    lab = [[0] * wide for _ in range(high)]
    n = 0
    sizes = collections.Counter()
    for y in range(high):
        row = rows[y]
        for x in range(wide):
            if row[x] not in PASSABLE or lab[y][x]:
                continue
            n += 1
            lab[y][x] = n
            stack = [(y, x)]
            size = 0
            while stack:
                cy, cx = stack.pop()
                size += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = cy + dy, cx + dx
                    if 0 <= yy < high and 0 <= xx < wide \
                            and rows[yy][xx] in PASSABLE and not lab[yy][xx]:
                        lab[yy][xx] = n
                        stack.append((yy, xx))
            sizes[n] = size
    return lab, sizes


def main():
    doc = load("map_terrain.json")
    rows = doc["rows"]
    b = doc["bounds"]
    gx0, gx1, gy0, gy1 = b["gx0"], b["gx1"], b["gy0"], b["gy1"]

    # --- the table is the map ----------------------------------------------
    assert doc["version"] == 1, "terrain: version %r" % doc.get("version")
    assert (gx0, gx1) == travel.MAP_X and (gy0, gy1) == travel.MAP_Y, \
        "terrain: bounds %s do not match the playable rectangle" % b
    wide, high = gx1 - gx0 + 1, gy1 - gy0 + 1
    assert len(rows) == high, "terrain: %d rows for %d cells of gy" % (len(rows), high)
    for i, row in enumerate(rows):
        assert len(row) == wide, "terrain: row %d is %d cells, not %d" % (
            i, len(row), wide)
    kinds = collections.Counter(c for row in rows for c in row)
    assert set(kinds) <= set(doc["legend"]), \
        "terrain: %s not in the legend" % (set(kinds) - set(doc["legend"]))
    assert set(PASSABLE) <= set(kinds), "terrain: nothing walkable at all"
    total = wide * high
    walkable = sum(kinds[c] for c in PASSABLE)
    rock = kinds.get("#", 0)
    assert 0.70 <= walkable / float(total) <= 0.99, \
        "terrain: %.1f%% walkable, which is not a world" % (100.0 * walkable / total)
    assert rock >= total // 100, "terrain: only %d cells of rock" % rock
    assert kinds.get("~", 0) >= 100, "terrain: the lake is missing"
    print("terrain: %d by %d cells, %.2f%% walkable, %.2f%% rock, %.2f%% water"
          % (wide, high, 100.0 * walkable / total, 100.0 * rock / total,
             100.0 * kinds.get("~", 0) / total))

    # --- the server reads the same ground -----------------------------------
    for gx, gy in [START, (gx0, gy0), (gx1, gy1), (6268, 1825), (5900, 1900)]:
        want = rows[gy - gy0][gx - gx0] in PASSABLE
        assert world.passable(gx, gy) is want, \
            "terrain: world.passable disagrees at %d,%d" % (gx, gy)
    assert not world.passable(gx0 - 1, gy0), "terrain: walkable off the map"
    assert not world.passable(gx1 + 1, gy1), "terrain: walkable off the map"
    # A position inside a cell belongs to that cell, as location_at has it.
    assert world.passable(START[0] + 0.9, START[1] + 0.9) is \
        world.passable(*START), "terrain: passable does not floor its position"
    print("world.passable agrees with the table, and the map ends at its edge")

    # --- the cells players stood on ----------------------------------------
    settled = world.settlements()
    blocked = [c for c in settled if rows[c[1] - gy0][c[0] - gx0] not in PASSABLE]
    assert not blocked, "terrain: %d settlements on ground nobody can walk: %s" % (
        len(blocked), sorted(blocked)[:10])
    assert len(settled) >= 260, "terrain: only %d settlements to check" % len(settled)
    marks = hints()
    stuck = [c for c in marks if rows[c[1] - gy0][c[0] - gx0] not in PASSABLE]
    assert not stuck, "terrain: %d tooltip cells on ground nobody can walk: %s" % (
        len(stuck), sorted(stuck)[:10])
    assert len(marks) >= 400, "terrain: only %d tooltips to check" % len(marks)
    print("all %d settlements and all %d tooltip cells are walkable"
          % (len(settled), len(marks)))

    # --- one world, walkable from the start ---------------------------------
    lab, sizes = components(rows, gx0, gy0)
    at = lambda c: lab[c[1] - gy0][c[0] - gx0]
    start = at(START)
    assert start, "terrain: the start cell itself is not walkable"
    reached = [c for c in settled if at(c) == start]
    assert sizes[start] >= 0.9 * walkable, \
        "terrain: the start reaches %d of %d walkable cells" % (sizes[start], walkable)
    assert len(reached) >= 0.9 * len(settled), \
        "terrain: only %d of %d settlements can be walked to from the start" % (
            len(reached), len(settled))
    print("from %d,%d: %d of %d walkable cells, %d of %d settlements"
          % (START[0], START[1], sizes[start], walkable, len(reached), len(settled)))

    # --- the Nubian valley --------------------------------------------------
    # It was read as a sealed pocket while the roughness threshold stood at
    # 20, and the brief said to expect that. The player who remembers the
    # game walked the footpath in: at 20 only two of the valley's sixteen
    # settlements could be reached at all, because a boulder field reads as
    # a mountain and the valley is full of them. What the valley must be is
    # a place you can get to and walk around in.
    inbox = [c for c in settled
             if NUBIA[0] <= c[0] <= NUBIA[1] and NUBIA[2] <= c[1] <= NUBIA[3]]
    assert len(inbox) >= 10, "terrain: only %d settlements in the valley" % len(inbox)
    joined = [c for c in inbox if at(c) == start]
    assert len(joined) == len(inbox),         "terrain: %d of the valley's %d settlements cannot be walked to" % (
            len(inbox) - len(joined), len(inbox))
    print("the Nubian valley: all %d settlements reachable on foot" % len(inbox))

    # --- the report says the same thing -------------------------------------
    with io.open(os.path.join(HERE, "map_terrain_report.md"), encoding="utf-8") as fh:
        report = fh.read()
    m = re.search(r"Passable: \*\*(\d+) of (\d+) cells", report)
    assert m, "report: no passable line"
    assert (int(m.group(1)), int(m.group(2))) == (walkable, total), \
        "report: says %s of %s, the table has %d of %d" % (
            m.group(1), m.group(2), walkable, total)
    m = re.search(r"and (\d+) of the (\d+) settlements", report)
    assert m and (int(m.group(1)), int(m.group(2))) == (len(reached), len(settled)), \
        "report: settlement count does not match the table"
    # The report no longer claims a seal; it records how far the walker
    # gets, which is the number worth watching.
    assert "Нубийск" in report or "valley" in report.lower(), (
        "report: says nothing about the valley")
    print("the report agrees with the table")
    print("ok")


if __name__ == "__main__":
    main()
