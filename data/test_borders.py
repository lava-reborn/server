"""The edge of the world, and the walk to everything inside it.

A wall in LAVA is a location with no outzone on that side -- never a bitmap,
because the client carries no terrain of any kind and every wasteland template
has all four sides (recon/analysis/borders.md). So the rim of the world is a
ring of the rock scenes the client ships, laid down by data/build_borders.py
with each tile's wall facing outward, and the only ground a walker cannot
stand on is the lake.

What is checked here:

  * data/borders.json covers the rim of world.MAP_X/MAP_Y exactly, one of the
    client's own "Скалы" tiles per cell, and each tile's own outzones -- read
    from the shipped file, not from its name -- leave out exactly the sides
    that face out of the world;
  * the ring agrees cell for cell with travel.rock_for, so the server's
    tables and the data file cannot drift apart;
  * not one location the server places on the map declares an exit the server
    cannot honour: 0 of the 949 settlement exits and 0 of the ring's lead off
    the world. This is the count that was 18 while the ground came from a
    photograph;
  * a way that does run out ends in one of the four dead-end pockets, entered
    over the edge the player came in by, and backing out lands where it
    started -- never an error, never a black screen;
  * and the walk: breadth-first from the cell a character starts on, every
    one of the 262 settlements of data/settlements.json is reachable on foot,
    the Nubian valley and the camp of the New Colonists among them.

Runs under WSL with the client resources present:

    wsl.exe -e python3 data/test_borders.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import travel  # noqa: E402
import world  # noqa: E402

# Where a character starts: the black market of Wadi Halfa (server.GLOBAL_X).
START = (5970, 1730)
# The Nubian valley as the player who walked it describes it, with a margin.
# It is the piece of the map the owner checked on foot: the roughness of the
# photograph read its boulder fields as mountains and sealed it off.
NUBIA = (6250, 6285, 1810, 1845)
# Two places named in the complaints, by cell: the northern Nubian village
# (181 "Нубийское поселение") and the camp of the New Colonists (80), which
# has to be walkable to from the market a few cells away.
NUBIAN_VILLAGE = (6268, 1819)
NEW_COLONISTS = ((5970, 1724), (5971, 1723))


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def sides_of(loc_id):
    """The map sides a location lets a player leave by, from its own file."""
    return {s for s in travel.exit_sides(world.location(loc_id)).values()
            if s in travel.SIDES}


def outward(gx, gy):
    """The sides of a cell that point out of the world."""
    out = []
    if gx == world.MAP_X[0]:
        out.append(travel.W)
    if gx == world.MAP_X[1]:
        out.append(travel.E)
    if gy == world.MAP_Y[0]:
        out.append(travel.N)
    if gy == world.MAP_Y[1]:
        out.append(travel.S)
    return out


def check_ring():
    doc = load("borders.json")
    b = doc["bounds"]
    assert doc["version"] == 1, "borders: version %r" % doc.get("version")
    assert (b["gx0"], b["gx1"]) == world.MAP_X \
        and (b["gy0"], b["gy1"]) == world.MAP_Y, \
        "borders: built for %s, the world is %s %s" % (b, world.MAP_X,
                                                       world.MAP_Y)
    ring = world.borders()
    assert len(ring) == len(doc["cells"]), "borders: the server reads %d of %d" \
        % (len(ring), len(doc["cells"]))

    wide = world.MAP_X[1] - world.MAP_X[0] + 1
    high = world.MAP_Y[1] - world.MAP_Y[0] + 1
    rim = {(gx, gy)
           for gx in range(world.MAP_X[0], world.MAP_X[1] + 1)
           for gy in range(world.MAP_Y[0], world.MAP_Y[1] + 1)
           if outward(gx, gy)}
    assert len(rim) == 2 * (wide + high) - 4, "borders: %d rim cells" % len(rim)
    settled = world.settlements()
    on_rim = {c: settled[c] for c in rim if c in settled}
    assert set(ring) == rim - set(on_rim), \
        "borders: the ring is not the rim; %d cells differ" % len(
            set(ring) ^ (rim - set(on_rim)))
    assert not set(ring) & set(settled), "borders: the ring covers a settlement"
    print("the ring: %d cells of the %d on the rim, %d left to a settlement"
          % (len(ring), len(rim), len(on_rim)))

    # The wall is the side the file's own outzones never touch. Names lie:
    # B_LeftSide is walled on the east.
    for (gx, gy), loc_id in ring.items():
        loc = world.location(loc_id)
        assert loc.title == "Скалы", \
            "borders: %d on %d,%d is %r" % (loc_id, gx, gy, loc.title)
        walls = set(travel.SIDES) - sides_of(loc_id)
        assert walls == set(outward(gx, gy)), \
            "borders: %d on %d,%d walls %s, the world faces %s" % (
                loc_id, gx, gy, "".join(sorted(walls)),
                "".join(outward(gx, gy)))
        assert set(travel.ROCK_WALL.get(loc_id, ())) == walls, \
            "borders: travel.ROCK_WALL disagrees about %d" % loc_id
        assert travel.rock_for(outward(gx, gy)[0], gx, gy) == loc_id, \
            "borders: travel.rock_for would put another tile on %d,%d" % (gx, gy)
    kinds = collections.Counter(ring.values())
    print("every tile walls exactly the sides that face out; %d files used: %s"
          % (len(kinds), ", ".join("%d x%d" % kv for kv in sorted(kinds.items()))))
    return ring


def check_exits(ring):
    """Nobody the server places on the map declares an exit it cannot honour."""
    off, wet = [], []
    counted = 0
    placed = list(world.settlements().items()) + list(ring.items())
    for (gx, gy), loc_id in placed:
        for side in sides_of(loc_id):
            counted += 1
            nx, ny = travel.neighbour(gx, gy, side)
            if not world.in_map(nx, ny):
                off.append((gx, gy, loc_id, side))
            elif not world.passable(nx, ny):
                wet.append((gx, gy, loc_id, side))
    assert not off, "borders: %d exits lead off the world: %s" % (
        len(off), off[:10])
    settled_wet = [e for e in wet if (e[0], e[1]) in world.settlements()]
    assert not settled_wet, "borders: %d settlement exits lead into water: %s" \
        % (len(settled_wet), settled_wet[:10])
    print("all %d exits of the %d placed locations lead onto the map; %d of the"
          " ring's meet the lake and get a pocket" % (counted, len(placed),
                                                      len(wet)))
    return wet


def check_pockets(wet):
    """Where the way runs out there is a scene, not an error."""
    for side in travel.SIDES:
        loc_id = travel.POCKET[side]
        opens = sides_of(loc_id)
        assert opens == {travel.OPPOSITE[side]}, \
            "borders: pocket %d for walking %s opens %s" % (
                loc_id, side, "".join(sorted(opens)) or "nothing")
        assert travel.POCKET_OPEN[loc_id] == travel.OPPOSITE[side], \
            "borders: travel.POCKET_OPEN disagrees about %d" % loc_id
        loc = world.location(loc_id)
        assert loc.title == "Скалы", "borders: pocket %d is %r" % (loc_id,
                                                                   loc.title)
        ex = travel.dead_end(side, *START)
        assert ex.loc_id == loc_id and (ex.gx, ex.gy) == START, \
            "borders: walking %s gives %s" % (side, (ex.loc_id, ex.gx, ex.gy))
        assert ex.pos not in loc.obstacles, \
            "borders: pocket %d drops the player on an obstacle" % loc_id
        # Standing on its one row of zones, to=1 goes back to the cell.
        cell = next(c for c, s in travel.exit_sides(loc).items()
                    if s in travel.SIDES)
        back = travel.plan_exit(loc, cell, *START)
        assert back.loc_id == world.location_at(*START) \
            and (back.gx, back.gy) == START, \
            "borders: backing out of pocket %d lands on %s" % (
                loc_id, (back.loc_id, back.gx, back.gy))
    print("the four pockets open the way they were walked into, and back out"
          " onto the cell they were entered from")

    # A real one: the cell beside the lake whose exit meets the water.
    if wet:
        gx, gy, loc_id, side = wet[0]
        loc = world.location(loc_id)
        cell = next(c for c, s in travel.exit_sides(loc).items() if s == side)
        ex = travel.plan_exit(loc, cell, gx, gy)
        assert ex.loc_id == travel.POCKET[side], \
            "borders: the lake at %d,%d answers with %d" % (gx, gy, ex.loc_id)
        print("  and %d,%d, whose %s exit meets the lake, opens pocket %d"
              % (gx, gy, side, ex.loc_id))

    # The rim itself: a tile of the ring has no exit cell facing out at all,
    # so there is nothing to stand on to leave the world, and walking in from
    # inside lands on ground.
    for side in travel.SIDES:
        gx, gy = {travel.W: (world.MAP_X[0], 1700),
                  travel.E: (world.MAP_X[1], 1700),
                  travel.N: (5900, world.MAP_Y[0]),
                  travel.S: (5900, world.MAP_Y[1])}[side]
        loc = world.location(world.location_at(gx, gy))
        assert side not in sides_of(loc.id), \
            "borders: the %s rim can be walked out of" % side
        pos = travel.arrival_cell(loc, travel.OPPOSITE[side])
        assert pos not in loc.obstacles, \
            "borders: arriving in %d lands on an obstacle" % loc.id
        inward = next(c for c, s in travel.exit_sides(loc).items()
                      if s == travel.OPPOSITE[side])
        ex = travel.plan_exit(loc, inward, gx, gy)
        assert (ex.gx, ex.gy) == travel.neighbour(gx, gy, travel.OPPOSITE[side]), \
            "borders: leaving the %s rim inward goes to %s" % (side,
                                                               (ex.gx, ex.gy))
    print("no rim cell has an exit facing out of the world, and all four lead"
          " back in")

    # And a cell outside the world still answers with something enterable:
    # the "Граница пустоши" whose one row of zones faces back in. Nobody can
    # walk out to one any more, but a character who logged out beyond the
    # rim before it was drawn there has to be able to log in again.
    for side, cell in ((travel.W, (world.MAP_X[0] - 1, 1700)),
                       (travel.E, (world.MAP_X[1] + 1, 1700)),
                       (travel.N, (5900, world.MAP_Y[0] - 1)),
                       (travel.S, (5900, world.MAP_Y[1] + 1))):
        back = travel.OPPOSITE[side]
        loc_id = travel.destination(*cell)
        assert loc_id == travel.deadloc_id(back), \
            "borders: %s past the %s rim is location %d" % (cell, side, loc_id)
        loc = world.location(loc_id)
        assert sides_of(loc_id) == {back}, \
            "borders: the %s border of the wasteland opens %s" % (
                side, "".join(sorted(sides_of(loc_id))))
        assert travel.arrival_cell(loc, side) not in loc.obstacles, \
            "borders: arriving in %d lands on an obstacle" % loc_id
    print("and a cell outside the world is still the wasteland's border,"
          " facing back in")


def walk_from(start):
    """Every cell reachable on foot, breadth-first as a walker moves."""
    seen = {start}
    queue = collections.deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and world.passable(*n):
                seen.add(n)
                queue.append(n)
    return seen


def check_walk():
    assert world.passable(*START), "borders: the start cell is not walkable"
    seen = walk_from(START)
    wide = world.MAP_X[1] - world.MAP_X[0] + 1
    high = world.MAP_Y[1] - world.MAP_Y[0] + 1
    blocked = [(gx, gy)
               for gy in range(world.MAP_Y[0], world.MAP_Y[1] + 1)
               for gx in range(world.MAP_X[0], world.MAP_X[1] + 1)
               if not world.passable(gx, gy)]
    dry = [c for c in blocked if not world.water(*c)]
    assert not dry, "borders: %d cells blocked by something other than water: %s" \
        % (len(dry), dry[:10])
    print("the world is %d by %d cells; %d are blocked, every one of them water"
          % (wide, high, len(blocked)))

    settled = world.settlements()
    missing = sorted(c for c in settled if c not in seen)
    assert not missing, "borders: %d settlements cannot be walked to: %s" % (
        len(missing), missing[:10])
    assert len(settled) >= 262, "borders: only %d settlements" % len(settled)
    print("from %d,%d on foot: %d cells, and all %d settlements"
          % (START[0], START[1], len(seen), len(settled)))

    valley = [c for c in settled if NUBIA[0] <= c[0] <= NUBIA[1]
              and NUBIA[2] <= c[1] <= NUBIA[3]]
    assert len(valley) >= 10, "borders: only %d settlements in the valley" \
        % len(valley)
    assert all(c in seen for c in valley), "borders: the Nubian valley is sealed"
    assert NUBIAN_VILLAGE in seen and NUBIAN_VILLAGE in settled, \
        "borders: the Nubian village on %s is not there to walk to" \
        % (NUBIAN_VILLAGE,)
    print("the Nubian valley: all %d settlements on foot, the village among them"
          % len(valley))

    for cell in NEW_COLONISTS:
        assert cell in seen, "borders: the New Colonists on %s are cut off" \
            % (cell,)
        # And the walk there from the market is a straight line, not a detour
        # around anything: travel.walk keeps the whole move.
        dx, dy = cell[0] - START[0], cell[1] - START[1]
        end = travel.walk(START[0] + 0.5, START[1] + 0.5, dx, dy)
        assert (int(end[0]), int(end[1])) == cell, \
            "borders: the way down to the New Colonists is cut at %s" % (end,)
    print("the way to the New Colonists' camp is open, and straight")

    # The rim can be walked onto -- it is a place, with rocks in it -- and
    # nothing beyond it can.
    for cell in ((world.MAP_X[0], 1700), (world.MAP_X[1], 1700),
                 (5900, world.MAP_Y[0]), (5900, world.MAP_Y[1])):
        assert cell in seen, "borders: the rim cell %s cannot be reached" % (cell,)
    for cell in ((world.MAP_X[0] - 1, 1700), (world.MAP_X[1] + 1, 1700),
                 (5900, world.MAP_Y[0] - 1), (5900, world.MAP_Y[1] + 1)):
        assert not world.passable(*cell), "borders: %s is off the world and" \
            " walkable" % (cell,)
    print("every rim cell is walked onto, and nothing past it")


def main():
    ring = check_ring()
    wet = check_exits(ring)
    check_pockets(wet)
    check_walk()
    print("ok")


if __name__ == "__main__":
    main()
