"""What the photograph of the map says, and the one column of it believed.

data/map_terrain.json is read off the client's own map tiles by
data/build_terrain.py; the server that knew the real table is gone. Of the
two things it reads, the server takes the water only: rock in LAVA was a
location with no outzone that way and never a pixel, and the roughness that
stood in for it walled 6130 cells that would open as ordinary wasteland
(recon/analysis/borders.md §3, §9, and data/test_borders.py for the ring that
replaced it). This checks:

  * the table covers the rectangle the photograph was read over, in the
    characters its own legend declares;
  * server/world.passable takes the water from it and nothing else, and the
    world reaches past the picture's own rectangle;
  * every one of the 228 settlement cells and every one of the 414 cells
    with a map tooltip is walkable -- those are cells players stood on;
  * the reading is internally whole, and data/map_terrain_report.md still
    describes the table it was written for.

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
# The characters of the table that are ground the photograph found dry. Two
# of them are walkable to the server and so is the third: only "~" is not.
PASSABLE = ".,"
DRY = ".,#"
# The rectangle data/build_terrain.py reads the tiles over. It is not the
# world -- the world runs further east and south (world.MAP_X) -- and it is
# written here rather than imported because build_terrain needs Pillow.
PHOTO = (5833, 6305, 1600, 2110)


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
    assert (gx0, gx1, gy0, gy1) == PHOTO, \
        "terrain: bounds %s are not the rectangle the tiles were read over" % b
    assert (travel.MAP_X[0] <= gx0 and gx1 <= travel.MAP_X[1]
            and travel.MAP_Y[0] <= gy0 and gy1 <= travel.MAP_Y[1]), \
        "terrain: the picture sticks out of the world %s %s" % (travel.MAP_X,
                                                                travel.MAP_Y)
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

    # --- the server takes both, minus what the files overrule ---------------
    #
    # Rock and water alike stop a walker. The picture yields in exactly one
    # direction: a cell some location declares as its own way out is open
    # however dark the pixels are, because a location file is testimony from
    # the people who built the world and the picture is our reading of an
    # image (data/terrain_repairs.json).
    repairs = world.terrain_repairs()
    assert repairs, "terrain: no repairs at all, which cannot be right"
    # And the hand outranks both: tools/map_editor.py writes cells a person
    # walled off or opened while looking at the map, and world.passable
    # consults them before anything else. The wall round the Nubian valley
    # is drawn there.
    hand = set()
    try:
        with io.open(os.path.join(HERE, "terrain_verified.json"),
                     encoding="utf-8") as fh:
            doc = json.load(fh)
        for kind in ("blocked", "passable"):
            for key in doc.get(kind) or ():
                hand.add(tuple(int(v) for v in key.split(",")))
    except (OSError, ValueError):
        pass
    disagree = [(gx0 + x, gy0 + y)
                for y, row in enumerate(rows) for x, ch in enumerate(row)
                if (gx0 + x, gy0 + y) not in repairs
                and (gx0 + x, gy0 + y) not in hand
                and world.passable(gx0 + x, gy0 + y) is not (ch in PASSABLE)]
    assert not disagree, \
        "terrain: world.passable disagrees with the picture at %d cells: %s" % (
            len(disagree), disagree[:10])
    # A repair opens what the picture called rock, and a hand-drawn wall
    # closes it again: the order is hand, then repairs, then the picture.
    overruled = [c for c in repairs if not world.passable(*c)]
    assert all(c in hand for c in overruled), \
        "terrain: a cell a location file calls its own exit is blocked by" \
        " neither a hand nor anything else: %s" % (
            [c for c in overruled if c not in hand][:6],)
    rock_cells = [(gx0 + x, gy0 + y)
                  for y, row in enumerate(rows) for x, ch in enumerate(row)
                  if ch == "#"]
    assert len(rock_cells) > 1000, "terrain: no rock in the table"
    # Rock stops a walker unless something with more authority says
    # otherwise: a repair, or a hand that painted the cell open.
    stopped = [c for c in rock_cells if not world.passable(*c)]
    walkable_rock = [c for c in rock_cells if world.passable(*c)]
    unexplained = [c for c in walkable_rock
                   if c not in repairs and c not in hand]
    assert not unexplained, \
        "terrain: %d rock cells are walkable for no recorded reason: %s" % (
            len(unexplained), unexplained[:6])
    print("rock stops a walker on %d cells and water on %d; %d cells are open"
          " because a location file says they are"
          % (len(stopped), kinds.get("~", 0), len(repairs)))

    # --- and the world is bigger than the picture ---------------------------
    wx0, wx1 = travel.MAP_X
    wy0, wy1 = travel.MAP_Y
    assert world.passable(gx1 + 1, gy1), \
        "terrain: the ground east of the picture is not walkable"
    assert world.passable(gx0, gy1 + 1), \
        "terrain: the ground south of the picture is not walkable"
    assert not world.passable(wx0 - 1, wy0), "terrain: walkable off the world"
    assert not world.passable(wx1 + 1, wy1), "terrain: walkable off the world"
    # A position inside a cell belongs to that cell, as location_at has it.
    assert world.passable(START[0] + 0.9, START[1] + 0.9) is \
        world.passable(*START), "terrain: passable does not floor its position"
    print("the world runs %d..%d by %d..%d and ends there"
          % (wx0, wx1, wy0, wy1))

    # --- the cells players stood on ----------------------------------------
    settled = world.settlements()
    blocked = [c for c in settled if rows[c[1] - gy0][c[0] - gx0] not in PASSABLE]
    assert not blocked, "terrain: %d settlements on ground nobody can walk: %s" % (
        len(blocked), sorted(blocked)[:10])
    # 228 since the owner's Донгола (2026-10-13): the 33 «Засада» cells of 389 and the
    # six of its cut went, thirteen restored places came (254 after the cut of
    # everything across the river the same day).
    assert len(settled) >= 228, "terrain: only %d settlements to check" % len(settled)
    marks = hints()
    stuck = [c for c in marks if rows[c[1] - gy0][c[0] - gx0] not in PASSABLE]
    assert not stuck, "terrain: %d tooltip cells on ground nobody can walk: %s" % (
        len(stuck), sorted(stuck)[:10])
    assert len(marks) >= 400, "terrain: only %d tooltips to check" % len(marks)
    print("all %d settlements and all %d tooltip cells are walkable"
          % (len(settled), len(marks)))

    # --- the photograph's own reading is whole ------------------------------
    # Not a statement about the world any more -- the server walks over the
    # rock of this table, and data/test_borders.py is where "everything can
    # be reached on foot" is checked. It stays because a reading that falls
    # into islands is a reading that went wrong, and the report below quotes
    # these very numbers.
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
    # A couple may hang on a cell the picture calls rock and a location file
    # calls its own exit; the repairs open those, and whether every
    # settlement can really be walked to is data/test_borders.py's question,
    # asked of world.passable rather than of this table.
    assert len(joined) >= len(inbox) - 2, \
        "terrain: %d of the valley's %d settlements are cut off in the" \
        " reading itself, which is more than the repairs should have to" \
        " carry" % (len(inbox) - len(joined), len(inbox))
    print("the Nubian valley: %d of %d settlements joined by the picture"
          " alone, the rest by the exits their files declare"
          % (len(joined), len(inbox)))

    # --- the report says the same thing -------------------------------------
    with io.open(os.path.join(HERE, "map_terrain_report.md"), encoding="utf-8") as fh:
        report = fh.read()
    m = re.search(r"Passable: \*\*(\d+) of (\d+) cells", report)
    assert m, "report: no passable line"
    assert (int(m.group(1)), int(m.group(2))) == (walkable, total), \
        "report: says %s of %s, the table has %d of %d" % (
            m.group(1), m.group(2), walkable, total)
    # The report was written over the original's places; a place of ours
    # (data/locations, put on the map in the location editor) comes after
    # it and is not counted against it -- the editor's own checks hold its
    # cell walkable and on the walk.
    ours = {i for i in world.overlay_ids() if i >= world.FIRST_NEW_ID}
    theirs = [c for c in settled if world.settlements()[c] not in ours]
    m = re.search(r"and (\d+) of the (\d+) settlements", report)
    assert m and (int(m.group(1)), int(m.group(2))) == (
        len([c for c in reached if c in set(theirs)]), len(theirs)), \
        "report: settlement count does not match the table"
    # The report no longer claims a seal; it records how far the walker
    # gets, which is the number worth watching.
    assert "Нубийск" in report or "valley" in report.lower(), (
        "report: says nothing about the valley")
    print("the report agrees with the table")
    print("ok")


if __name__ == "__main__":
    main()
