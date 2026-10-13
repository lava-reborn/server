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
    cannot honour: 0 of the 944 the settlement cells declare and 0 of the
    ring's lead off the world, and no settlement's leads into the lake. That
    count was 18 while the ground came from a photograph;
  * a way that does run out ends in one of the four dead-end pockets, entered
    over the edge the player came in by, and backing out lands where it
    started -- never an error, never a black screen;
  * and the walk: breadth-first from the cell a character starts on, every
    one of the 228 settlements of data/settlements.json is reachable on foot,
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
# Open ground north-east of the camp, on the far side of the band of rock the
# photograph drew over it: the way down to the tents the owner found shut.
ABOVE_COLONISTS = (5980, 1718)


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


def hand_drawn():
    """Cells a person walled off in tools/map_editor.py.

    They outrank everything else world.passable consults, so every check
    that asks "why is this blocked" has to know about them.
    """
    out = set()
    try:
        with io.open(os.path.join(HERE, "terrain_verified.json"),
                     encoding="utf-8") as fh:
            for key in json.load(fh).get("blocked") or ():
                out.add(tuple(int(v) for v in key.split(",")))
    except (OSError, ValueError):
        pass
    return out


def check_exits(ring):
    """Nobody the server places on the map declares an exit it cannot honour."""
    off, wet = [], []
    counted = settlement_exits = 0
    settled = world.settlements()
    placed = list(settled.items()) + list(ring.items())
    for (gx, gy), loc_id in placed:
        for side in sides_of(loc_id):
            counted += 1
            if (gx, gy) in settled:
                settlement_exits += 1
            nx, ny = travel.neighbour(gx, gy, side)
            if not world.in_map(nx, ny):
                off.append((gx, gy, loc_id, side))
            elif not world.passable(nx, ny):
                wet.append((gx, gy, loc_id, side))
    assert not off, "borders: %d exits lead off the world: %s" % (
        len(off), off[:10])
    # A settlement's declared exit must not meet blocked ground -- unless a
    # person drew the wall there deliberately. The hand layer outranks both
    # the photograph and the repairs (world.passable), and walling a valley
    # in is exactly what it exists for, so those are listed, not refused.
    drawn = hand_drawn()
    settled_wet = [e for e in wet if (e[0], e[1]) in settled]
    by_hand = [e for e in settled_wet
               if travel.neighbour(e[0], e[1], e[3]) in drawn]
    by_map = [e for e in settled_wet if e not in by_hand]
    assert not by_map, "borders: %d settlement exits lead into blocked" \
        " ground the map itself drew: %s" % (len(by_map), by_map[:10])
    if by_hand:
        print("  %d settlement exits meet a hand-drawn wall, which outranks"
              " them: %s" % (len(by_hand), by_hand[:4]))
    # 833 since the owner's Донгола (2026-10-13) took 39 settlement cells off
    # the map (the 33 «Засада» of 389 among them) and put 13 places on; 944
    # after the cut of everything across the river the same day, which took
    # nineteen.
    assert settlement_exits >= 833, \
        "borders: only %d settlement exits to check" % settlement_exits
    print("all %d exits of the %d placed locations lead onto the map, the %d"
          " of the settlements among them; %d of the ring's meet the lake and"
          " get a pocket" % (counted, len(placed), settlement_exits, len(wet)))
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

    # A real one: the cell beside the lake whose exit meets the water -- one
    # a walker can stand on: the quarter 447 stands on the owner's wall
    # itself, and a player on blocked ground is let out (travel.plan_exit).
    # Эван's farm 325, the first until the owner's cut of everything across
    # the river (2026-10-13), is off the map.
    real = [e for e in wet if world.passable(e[0], e[1])]
    if real:
        gx, gy, loc_id, side = real[0]
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


def steps_between(a, b):
    """How many cells a walker actually covers, going round whatever is in
    the way. Compared against the straight-line distance, it says whether an
    obstacle is a detour or a wall."""
    prev = {a: None}
    queue = collections.deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            n = 0
            while prev[cur]:
                cur, n = prev[cur], n + 1
            return n
        x, y = cur
        for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nb not in prev and world.passable(*nb):
                prev[nb] = cur
                queue.append(nb)
    return None


def check_walk():
    assert world.passable(*START), "borders: the start cell is not walkable"
    seen = walk_from(START)
    wide = world.MAP_X[1] - world.MAP_X[0] + 1
    high = world.MAP_Y[1] - world.MAP_Y[0] + 1
    blocked = [(gx, gy)
               for gy in range(world.MAP_Y[0], world.MAP_Y[1] + 1)
               for gx in range(world.MAP_X[0], world.MAP_X[1] + 1)
               if not world.passable(gx, gy)]
    # Nothing stops a walker without a reason on record: either the map drew
    # it -- the lake and the mountains, both out of the same picture, which
    # world.water answers for since BLOCKED covers both -- or a person drew
    # it by hand in terrain_verified.json.
    drawn = hand_drawn()
    unexplained = [c for c in blocked
                   if not world.water(*c) and c not in drawn]
    assert not unexplained, \
        "borders: %d cells blocked by neither the map nor a hand: %s" \
        % (len(unexplained), unexplained[:10])
    print("  %d of them drawn by hand" % len([c for c in blocked
                                              if c in drawn]))
    print("the world is %d by %d cells; %d are blocked, every one of them"
          " drawn as rock or water"
          % (wide, high, len(blocked)))

    settled = world.settlements()
    assert len(settled) >= 228, "borders: only %d settlements" % len(settled)

    # The world is no longer one piece, and that is a decision rather than a
    # fault: the owner drew a wall round the Nubian valley, so the starting
    # zone is closed and the rest of the map is outside it. What must still
    # hold is that nothing is sealed on its own -- every settlement belongs
    # to one side or the other, and both sides are whole.
    inside = walk_from(NUBIAN_VILLAGE)
    outside = walk_from(START)
    assert not (inside & outside), \
        "borders: the valley and the rest of the world are the same place," \
        " so the wall has a hole in it"
    stranded = sorted(c for c in settled
                      if c not in inside and c not in outside)
    assert not stranded, \
        "borders: %d settlements belong to neither side of the wall: %s" \
        % (len(stranded), stranded[:10])
    in_n = sum(1 for c in settled if c in inside)
    out_n = sum(1 for c in settled if c in outside)
    assert in_n + out_n == len(settled), "borders: %d + %d settlements of %d" \
        % (in_n, out_n, len(settled))
    print("the wall divides the world: %d cells and %d settlements inside,"
          " %d and %d outside, nothing stranded between them"
          % (len(inside), in_n, len(outside), out_n))

    valley = [c for c in settled if NUBIA[0] <= c[0] <= NUBIA[1]
              and NUBIA[2] <= c[1] <= NUBIA[3]]
    assert len(valley) >= 10, "borders: only %d settlements in the valley" \
        % len(valley)
    seen = inside                       # the walk that matters starts at home
    assert all(c in seen for c in valley), \
        "borders: %d of the valley's own settlements are outside its wall" \
        % len([c for c in valley if c not in seen])
    assert NUBIAN_VILLAGE in seen and NUBIAN_VILLAGE in settled, \
        "borders: the Nubian village on %s is not there to walk to" \
        % (NUBIAN_VILLAGE,)
    print("the Nubian valley: all %d settlements on foot, the village among them"
          % len(valley))

    # Everything below is the world outside the wall: the New Colonists and
    # the rim both lie there, and it is the market they are walked to from.
    seen = outside
    for cell in NEW_COLONISTS:
        assert cell in seen, "borders: the New Colonists on %s are cut off" \
            % (cell,)
        # From the market the walk is a straight line and travel.walk keeps
        # the whole move: six cells due north, nothing in the way.
        dx, dy = cell[0] - START[0], cell[1] - START[1]
        end = travel.walk(START[0] + 0.5, START[1] + 0.5, dx, dy)
        assert (int(end[0]), int(end[1])) == cell, \
            "borders: the way from the market to the New Colonists is cut" \
            " at %s" % (end,)

    # From the open ground north-east of the camp a single order does NOT
    # arrive, and should not: the map draws a band of rock over 5973..5987 by
    # 1722..1726, just east of the tents, and a walk into it is cropped in
    # front of it like any other mountain. What matters is that the band is
    # something to walk around rather than a wall: the way round costs
    # nothing, sixteen steps against sixteen in a straight line.
    camp = NEW_COLONISTS[0]
    dx, dy = camp[0] - ABOVE_COLONISTS[0], camp[1] - ABOVE_COLONISTS[1]
    end = travel.walk(ABOVE_COLONISTS[0] + 0.5, ABOVE_COLONISTS[1] + 0.5,
                      dx, dy)
    assert (int(end[0]), int(end[1])) != camp, \
        "borders: the band of rock east of the camp lets a walk straight" \
        " through, so it is not there at all"
    assert steps_between(ABOVE_COLONISTS, camp) == abs(dx) + abs(dy), \
        "borders: going round the band costs %s steps against %d straight" \
        % (steps_between(ABOVE_COLONISTS, camp), abs(dx) + abs(dy))
    print("the way to the New Colonists' camp is straight from the market,"
          " and round the rock from the north-east at no extra cost")

    # The rim can be walked onto -- it is a place, with rocks in it -- and
    # nothing beyond it can. Not every cell of it: the mountains reach the
    # northern edge in places and seal a stretch of rim behind them, which is
    # the picture being obeyed rather than a hole in the ring. What has to
    # hold is that every side of the world can be reached somewhere, and that
    # the sealed part stays small.
    rim = {tuple(int(v) for v in key.split(","))
           for key in load("borders.json")["cells"]}
    reached = rim & seen
    assert len(reached) >= 0.9 * len(rim), \
        "borders: only %d of %d rim cells can be reached" % (len(reached),
                                                             len(rim))
    for side, on_side in (
            ("west", [c for c in rim if c[0] == world.MAP_X[0]]),
            ("east", [c for c in rim if c[0] == world.MAP_X[1]]),
            ("north", [c for c in rim if c[1] == world.MAP_Y[0]]),
            ("south", [c for c in rim if c[1] == world.MAP_Y[1]])):
        got = [c for c in on_side if c in seen]
        assert len(got) >= 0.5 * len(on_side), \
            "borders: only %d of %d cells of the %s rim can be reached" \
            % (len(got), len(on_side), side)
    for cell in ((world.MAP_X[0] - 1, 1700), (world.MAP_X[1] + 1, 1700),
                 (5900, world.MAP_Y[0] - 1), (5900, world.MAP_Y[1] + 1)):
        assert not world.passable(*cell), "borders: %s is off the world and" \
            " walkable" % (cell,)
    print("%d of %d rim cells are walked onto, every side among them, and"
          " nothing past the rim" % (len(reached), len(rim)))


def main():
    ring = check_ring()
    wet = check_exits(ring)
    check_pockets(wet)
    check_walk()
    print("ok")


if __name__ == "__main__":
    main()
