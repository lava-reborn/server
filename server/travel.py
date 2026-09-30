"""Leaving a location through an exit, and where that exit leads.

The client never says which exit it is leaving by. Location.finishMove opens
the exit window when the player's own walker stops on a cell with the zone
flag, and the window's two buttons send chWorld; for the map and chWorld;to=1;
for "the other location" -- nothing more (ExitLocationInterface.exitLoc and
exitGmap, Location.exitLoc). Which exit that is has to be read off the cell
the player stands on, and what lies beyond it sat in the serverdata node
that every shipped file lost.

What survived is the side. outzones lists the same cells the client reads as
zones with one more character each: 1 west, 2 north, 3 east, 4 south, and a
or b for a door into an interior (recon/analysis/world.md §5, tabulated in
data/exits_sides.json). A side 1..4 needs no data at all: the exit leads to
the neighbouring cell of the global map, and the player arrives at the
opposite edge of whatever stands there, a settlement out of
data/settlements.json or open desert -- but for the interiors that open into
each other by their sides, the quarry's pits, which data/passages.json
'sides' lists (side_way). A door is a lookup in data/exits.json,
and only entries recovered with some confidence are followed; the rest are
refused with a word in chat rather than sent somewhere wrong. Where the
client's own files know better than that table's guess, data/passages.json
corrects it. It also lists the two kinds of way that have no zone at all:
walk-ins, cells a file draws as a way somewhere without marking them as
zones, which the server acts on when a walk ends there, since the client
will not; and quest ways, where an inhabitant's quest is the way -- Рудо's
down into the Nubian mine, Камал's back up -- and handing it in moves the
player.

The rim of the world is a ring of rock scenes standing on the rim cells
themselves (data/borders.json, world.borders): a wall is a location with no
outzone that way, which is the only kind of wall LAVA ever had. Walking into
one is walking into a place, and there is simply no exit cell on its outward
side to stand on. Where the way still runs out -- the last cell before a
cell nobody can enter -- the answer is one of the kit's four dead-end
pockets, entered over the edge the player came in by.

Past the map's rectangle lie the four "Граница пустоши" files,
locations/deadloc/0..3: no inhabitants, no obstacles, and zones along one
edge only, west, north, east, south by file number. The ring stands in front
of them now, so they are what a cell outside the world resolves to -- a
character whose saved home fell outside it, or a /goto past the edge -- and
the way back in is their one row of zones.

Everything here is a function of the location, the cell and the map
position; the Session applies the answer and sends the frames.
"""
import json
import math
import os
from collections import namedtuple

import world
from protocol import Str

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The playable rectangle of the global map, written down in world and
# re-exported here because everything else asks travel for it. Why it ends
# where it does: world.MAP_X.
MAP_X = world.MAP_X
MAP_Y = world.MAP_Y

W, N, E, S = "W", "N", "E", "S"
SIDES = (W, N, E, S)
OPPOSITE = {W: E, E: W, N: S, S: N}

# Map and location share one axis convention. DisplayGlobalMap puts a figure
# at _y = mapScale * y, so north is up on the screen and one LESS in gy; the
# location grid counts rows from the top as well, and its northern zones are
# the rows y <= 2 (build_exits_sides). So a northern exit leads to gy - 1.
STEP = {W: (-1, 0), N: (0, -1), E: (1, 0), S: (0, 1)}

# outzones side codes, as data/build_exits_sides.py reads them
SIDE_CODE = {"1": W, "2": N, "3": E, "4": S, "a": "a", "b": "b"}

# deadloc/<k> keeps its only exit on SIDES[k]: file 0 has its zones at x <= 1
# coded 1, file 1 at y <= 1 coded 2, file 2 at x >= 62 coded 3, file 3 at
# y >= 126 coded 4. The id is what SSEmulator.getLocDescription unpacks,
# (id >> 26) & 3 for the file behind 0x4 in the top nibble.
DEADLOC_BASE = 4 << 28

# Door entries followed; "low" ones are guesses by file-name family
# (441 of them) and "none" has no target at all.
DOOR_CONFIDENCE = ("high", "medium")

# How far in from an edge an entry cell still counts as being on that edge.
# The desert templates keep their inzones one to three cells in, settlements
# ring theirs at one or three.
EDGE_BAND = 4

# Bookmarks per character. The client has no limit of its own; this one
# keeps a runaway list from bloating every gmap.
MARKS_MAX = 50

# Where an exit leads: the location to open, the cell to stand on, and the
# map cell the player is on afterwards.
Exit = namedtuple("Exit", "loc_id pos gx gy")


class Refused(Exception):
    """This exit leads nowhere the server knows of. The text is for the
    player's chat: Master.changeWorldAck shows nothing on a refusal."""


# --- data ------------------------------------------------------------------
_TABLES = {}


def _table(name, key):
    """One of the data/*.json tables, read once."""
    if name not in _TABLES:
        with open(os.path.join(HERE, "data", name), encoding="utf-8") as fh:
            _TABLES[name] = json.load(fh)[key]
    return _TABLES[name]


_SIDES = {}
_WAR_ENTRIES = {}


def _read_zones(loc, tag, step):
    path = world.path_for(loc.id)
    txt = world._read(path) if path else ""
    return world._chunks(txt, tag, step)


def exit_sides(loc):
    """cell -> side for every exit cell of the location.

    Static files come from data/exits_sides.json. The desert templates and
    the deadloc files are not in it (it was built over locations/static
    alone), so their outzones are read straight from the file the client
    resolves the id to; the record layout is the same.
    """
    sides = _SIDES.get(loc.id)
    if sides is None:
        raw = _table("exits_sides.json", "locations").get(str(loc.id))
        if raw is not None:
            sides = {int(c): s for c, s in raw.items()}
        else:
            sides = {}
            for chunk in _read_zones(loc, "outzones", 5):
                side = SIDE_CODE.get(chunk[4])
                if side is not None:
                    sides[loc._cell(chunk)] = side
        _SIDES[loc.id] = sides
    return sides


def war_entries(loc):
    """warinzones: where players appear in a war=1 location. world.Location
    keeps inzones only, and these are read the same way."""
    cells = _WAR_ENTRIES.get(loc.id)
    if cells is None:
        cells = _WAR_ENTRIES[loc.id] = [
            loc._cell(c) for c in _read_zones(loc, "warinzones", 4)]
    return cells


def side_at(loc, pos):
    """The side of the exit the player stands on, or None off any exit."""
    return exit_sides(loc).get(int(pos))


_PASSAGES = None


def passages_path():
    """Where the ways kept by hand are read from: data/passages.json, or
    the file LAVA_PASSAGES names. The variable is for a test that needs a
    way the world does not have -- test_walk_in keeps the walk-in mechanism
    running on a table of its own, now that no place uses one -- and it
    replaces the table rather than adding to it, so what a run follows is
    exactly one file."""
    return (os.environ.get("LAVA_PASSAGES")
            or os.path.join(HERE, "data", "passages.json"))


def _passages():
    """The ways kept by hand, read once.

    Missing or broken, it is simply empty: every door falls back to
    data/exits.json and no cell or quest leads anywhere its file does not
    say, which is how the world stood before the table existed.
    """
    global _PASSAGES
    if _PASSAGES is None:
        try:
            with open(passages_path(), encoding="utf-8") as fh:
                doc = json.load(fh)
            _PASSAGES = doc if isinstance(doc, dict) else {}
        except (OSError, ValueError):
            _PASSAGES = {}
    return _PASSAGES


def door(loc_id, side):
    """The record for door a or b of a location, or None.

    data/exits.json guessed most doors from file names, and where the
    client's own files say better -- the Nubian mine signs its ladders "up"
    and "down" -- data/passages.json corrects it. The correction keeps the
    door's cells from exits.json, or reads them off outzones when that table
    has no row, since door_arrival needs them to put a player beside it.
    """
    rec = None
    entry = _table("exits.json", "doors").get(str(loc_id))
    for r in (entry or {}).get("doors", ()):
        if r.get("side") == side:
            rec = r
            break
    fixed = ((_passages().get("doors") or {}).get(str(loc_id)) or {}).get(side)
    if not fixed:
        return rec
    # Only the cells survive from the guess: its target_title, target_fn and
    # alternatives describe the place it guessed, not this one.
    out = dict(fixed, side=side, cells=list((rec or {}).get("cells") or ()))
    if not out["cells"]:
        out["cells"] = sorted(c for c, s in exit_sides(world.location(loc_id)).items()
                              if s == side)
    return out


def side_way(loc_id, side):
    """The record for side W, N, E or S of a location that data/passages.json
    'sides' leads into another interior, or None: the files of one place
    that open into each other by their sides -- the quarry's five pits --
    and have no cells of their own on the map to lead to. Only the
    locations listed there; every other side exit leads to the neighbouring
    map cell (plan_exit)."""
    rec = ((_passages().get("sides") or {}).get(str(loc_id)) or {}).get(side)
    return rec if isinstance(rec, dict) and rec.get("target_loc_id") else None


def no_map(loc_id):
    """Whether data/passages.json 'no_map' lists the location: an interior
    left only by its own ways -- the quest ways out of Берт's bunker, the
    quarry's way out and its sides -- and never straight onto the global
    map. The client is told it is a sublocation (geo_id) and greys both map
    buttons out, and the server refuses chWorld to the map and /home from
    it (server.py Session.cmd_chWorld, cmd_userMsg): a course that is
    walked once, or a tool that is lent for one place (quests.json
    stay_in), is not left behind by a button. A death still sends the
    player home (and stay_in takes the tool back on arrival)."""
    return isinstance((_passages().get("no_map") or {}).get(str(int(loc_id))), dict)


_WAYS = {}


def _ways(section, loc):
    """[(cells, record)] of one section of the table for a location, the
    cells numbered y * width + x as the client numbers them; those off the
    grid are dropped."""
    key = (section, loc.id)
    found = _WAYS.get(key)
    if found is None:
        found = []
        for rec in (_passages().get(section) or {}).get(str(loc.id)) or ():
            cells = frozenset(int(y) * loc.width + int(x)
                              for x, y in rec.get("cells") or ()
                              if 0 <= int(x) < loc.width
                              and 0 <= int(y) < loc.height)
            found.append((cells, rec))
        _WAYS[key] = found
    return found


def walk_ins(loc):
    """[(cells, record)] of the walk-in passages of a location.

    A walk-in is a way the location file draws but does not mark: the client
    only opens its exit window on a cell with the zone flag
    (Location.finishMove). The server moves the player itself once their
    walk ends on one of these cells (server.py, Session.arm_passage). Cells
    come as [x, y] of the location's own grid. A row with none leads from
    nowhere and is left out.

    No place has one now: the Nubian mine's mouth and its EXIT sign were
    walk-ins until the quests of Рудо and Камал took over (quest_ways).
    """
    return [(cells, rec) for cells, rec in _ways("walk_in", loc) if cells]


def quest_ways(loc):
    """[(cells, record)] of the ways a quest of this location's inhabitants
    takes a player: record["quest"] is the quest type, target_loc_id where
    it leads.

    The client has no way to go anywhere through a quest except the one the
    server makes: taking it is a q_st, a cmdAck and the q_di that journals
    it; handing it in to the same inhabitant is a q_co and a cmdAck
    (QuestInspector.takeQuest), and the lcall that follows is ours
    (server.py, Session.hand_in_way). The cells are not a trigger --
    nothing happens on them -- but where the file draws the way: a player
    coming the other way arrives beside them (door_arrival), at the mouth
    of the mine or under its EXIT sign.
    """
    return _ways("quest", loc)


def quest_way(loc, quest_type):
    """The quest way of this location that quest_type is, or None."""
    for _cells, rec in quest_ways(loc):
        try:
            if int(rec.get("quest")) == int(quest_type):
                return rec
        except (TypeError, ValueError):
            continue
    return None


def is_quest_way(quest_type):
    """Whether the table makes quest_type a way from anywhere at all.

    Such a quest is journalled like any other and its hand-in is the way:
    nothing paid, nothing counted against the day (server.py,
    Session.hand_in_way). Asked of the whole table, not of one location's
    rows, so that wherever it is given or handed in, the question of where
    it leads from there is asked (plan_quest_way) and a place the table has
    not caught up with -- an inhabitant who gives it standing somewhere else
    -- is refused rather than taken for an ordinary quest.
    """
    for rows in (_passages().get("quest") or {}).values():
        for rec in rows or ():
            try:
                if int(rec.get("quest")) == int(quest_type):
                    return True
            except (TypeError, ValueError, AttributeError):
                continue
    return False


def walk_in_at(loc, pos):
    """The walk-in record whose cells include pos, or None."""
    for cells, rec in walk_ins(loc):
        if int(pos) in cells:
            return rec
    return None


def off_walk_in(loc, pos):
    """pos, or where to stand instead when pos is on a walk-in passage:
    beside it, where one comes out of it (door_arrival).

    For a character put back where the last session left it. Standing on
    a walk-in is not a way to take it -- only the end of a walk is, and the
    client sends no walk to the cell its figure is already on -- so a
    player left there would stand on the way through unable to use it
    until they stepped off and back on.
    """
    rec = walk_in_at(loc, pos)
    if rec is None:
        return pos
    return door_arrival(loc, rec.get("target_loc_id"))


def walk_seconds(path_len):
    """How long the client takes to walk a path of path_len cells.

    Every figure goes at 200 ms a hex whatever it is (LocWalker.startMove,
    the number mobs.HEX_MS cites too), and a walk-in waits that long before
    it moves the player, so the figure is seen to reach the way through
    before the next location starts loading. The small margin covers
    the frame the client needs to act on the last step.
    """
    return 0.2 * max(0, int(path_len) - 1) + 0.3


# --- the map ---------------------------------------------------------------
def in_map(gx, gy):
    return MAP_X[0] <= gx <= MAP_X[1] and MAP_Y[0] <= gy <= MAP_Y[1]


def clamp(gx, gy):
    """The nearest cell of the map proper: where a player standing beyond
    its edge is put when they go to the map."""
    return (min(max(gx, MAP_X[0]), MAP_X[1]),
            min(max(gy, MAP_Y[0]), MAP_Y[1]))


def neighbour(gx, gy, side):
    dx, dy = STEP[side]
    return int(gx) + dx, int(gy) + dy


# How far short of a mountain a walker is left. A step of a cell is 8 pixels
# of map, so two hundredths of a cell is well under a pixel, but it keeps the
# stopping position inside the last open cell whichever way the client rounds
# its own float.
CLEARANCE = 0.02

# A ceiling on how many cell boundaries one move may cross. The traversal
# below ends when the ray reaches t = 1, and for any honest move it does --
# but t is measured in units of the move itself, so a move of 1e30 cells
# advances t by 1e-30 per boundary and the loop never finishes. That is not
# hypothetical: a destination outside the map, or a float the client rounded
# oddly, reaches walk() before travel clamps anything, and the server then
# spins inside a coroutine with nobody to interrupt it -- every player on the
# process stops, not just the one who clicked.
#
# The diagonal of the world is the most boundaries any real move can cross;
# twice that, plus a few, is past anything legitimate and still finite.
MAX_STEPS = 2 * ((MAP_X[1] - MAP_X[0]) + (MAP_Y[1] - MAP_Y[0])) + 4


def walk(gx, gy, dx, dy):
    """The far end of a move, cut short at the first cell nobody can enter.

    The walker crosses cells, not points: this is the grid traversal every
    tile engine uses (Amanatides & Woo), stepping to whichever cell boundary
    comes first and asking world.passable about the cell beyond it. The whole
    move is kept when nothing blocks it, and otherwise the position just
    inside the last open cell is returned.

    A player standing on blocked ground -- through a location's side exit,
    which hands out the neighbouring cell without asking, or through /goto --
    is not trapped there: the cut only starts once the ray has been on open
    ground, so the first move always carries them out of the rock.
    """
    if not dx and not dy:
        return gx, gy
    x, y = int(math.floor(gx)), int(math.floor(gy))
    open_yet = world.passable(x, y)
    step_x = 1 if dx > 0 else -1
    step_y = 1 if dy > 0 else -1
    inf = float("inf")
    # The ray is parametrised over the move itself: t = 1 is the target.
    next_x = (x + 1 - gx) / dx if dx > 0 else (x - gx) / dx if dx < 0 else inf
    next_y = (y + 1 - gy) / dy if dy > 0 else (y - gy) / dy if dy < 0 else inf
    span_x = abs(1.0 / dx) if dx else inf
    span_y = abs(1.0 / dy) if dy else inf
    for _ in range(MAX_STEPS):
        if next_x < next_y:
            t, x = next_x, x + step_x
            next_x += span_x
        else:
            t, y = next_y, y + step_y
            next_y += span_y
        if t >= 1.0:
            return gx + dx, gy + dy
        if world.passable(x, y):
            open_yet = True
            continue
        if not open_yet:
            continue                    # still walking out of the rock
        back = max(0.0, t - CLEARANCE / math.hypot(dx, dy))
        return gx + dx * back, gy + dy * back
    # Out of steps, which only a move no player can make gets to. Stay put
    # rather than guess: the caller clamps and the client asks again.
    return gx, gy


def deadloc_id(exit_side):
    """The edge-of-the-world location whose one exit is on exit_side."""
    return DEADLOC_BASE | (SIDES.index(exit_side) << 26)


def is_deadloc(loc_id):
    return loc_id >> 28 == 4


# The rock kit the client ships: files titled "Скалы", library "Mountains",
# all war=1 -- four sides in two variants, four corners, four dead-end
# pockets. Which way each one is walled is read off its own outzones: the one
# side with no cell to leave by. The file names are no guide at all --
# B_LeftSide is the tile walled on the EAST, B_DownSide the one walled on the
# NORTH -- so every table here is the data's and not the name's.
ROCK_WALL = {1: (E,), 2: (E,), 12: (W,), 13: (W,),
             10: (N,), 11: (N,), 15: (S,), 16: (S,),
             0: (W, S), 3: (W, N), 8: (E, S), 9: (E, N)}
ROCK_SIDE = {E: (1, 2), W: (12, 13), N: (10, 11), S: (15, 16)}
ROCK_CORNER = {(W, S): 0, (W, N): 3, (E, S): 8, (E, N): 9}
ROCK_IDS = frozenset(ROCK_WALL)

# The four pockets, by the direction the player was walking when the way ran
# out. A pocket is open on exactly one side, and the side that has to be open
# is the one the player comes in over: walking east, they arrive at the
# scene's western edge, so the scene wanted is the one whose only opening
# faces west -- 14, whose file is called B_LeftPocket. Again, not the name.
POCKET = {E: 14, W: 4, N: 7, S: 40}
POCKET_OPEN = {14: W, 4: E, 7: S, 40: N}
POCKET_IDS = frozenset(POCKET.values())

# A scene of rock is a place, not a cell: standing in one, the map cell is
# still the cell the player walked in from, exactly as for an interior. So
# to=1 out of it goes back to that cell's own location -- unless the rock IS
# that cell's location, which is what the ring around the world is, and then
# it is walked out of like any other place, by whichever sides its file
# leaves open.
SCENE_IDS = ROCK_IDS | POCKET_IDS


def room_key(loc, gx, gy):
    """What rooms.Rooms should file this location under.

    A settlement or an interior is one place and one room. A rock scene is
    not: the same file stands on every cell of a wall, and four deadloc files
    stand on everything outside the map. Those are split by cell, or the rim
    would be one room from corner to corner.
    """
    if loc.id in SCENE_IDS or is_deadloc(loc.id):
        return (loc.id, int(gx), int(gy))
    return loc.id


def newbie_ground(loc, gx, gy):
    """Whether standing in this location on map cell gx, gy is standing on
    the Nubian valley's ground, where no player may attack another.

    The valley's own tiles are lost (world.NOOB_VALLEY), and two kinds of
    file stand in for them: open desert for its wasteland (world.Location.
    newbies), and the scenes of rock for its walls -- a side exit of a valley
    cell into the owner's wall ends in a pocket (dead_end), and the rock
    around the valley was NoPvP_* in the original, pvp="0" all of it. The
    pocket files say otherwise or nothing, being the rim's (14 even says
    pvp="1"), and the map cell is the only thing that knows where the
    pocket is: the same cell the room is filed under (room_key), so everyone
    in one room is under one rule. A settlement or an interior has a file of
    its own and keeps what that says -- "Арена Нубии" included.

    Nothing is, unless the valley is kept peaceful (world.NOOB_VALLEY_SAFE).
    """
    if not world.NOOB_VALLEY_SAFE:
        return False
    if loc.newbies:
        return True
    return loc.id in SCENE_IDS and world.in_noob_valley(int(gx), int(gy))


def rock_for(side, gx, gy):
    """Which wall of the ring stands on a rim cell, walking that way.

    This is the rule data/borders.json is built by (data/build_borders.py
    lays the same tiles on the same cells, and data/test_borders.py checks
    the two agree cell by cell). A corner when the ground is gone on both
    axes, otherwise one of the side's two variants, picked from the cell so
    the same spot always shows the same rocks.
    """
    if side in (W, E):
        for updown in (N, S):
            nx, ny = neighbour(gx, gy, updown)
            if not world.in_map(nx, ny):
                corner = ROCK_CORNER.get((side, updown))
                if corner is not None:
                    return corner
                break
    pair = ROCK_SIDE.get(side)
    if not pair:
        return ROCK_SIDE[W][0]
    return pair[(int(gx) + int(gy)) % len(pair)]


def dead_end(side, gx, gy):
    """An Exit into a pocket of rock: the scene for a way that runs out.

    Walking up to the edge of the world is meant to look like arriving among
    rocks with no way on, not like an error window. The pocket is a dead end
    by construction -- one opening, the one the player came in by -- and the
    map cell does not change, so nothing can be walked around through it and
    backing out lands exactly where it started.
    """
    loc_id = POCKET[side]
    rock = world.location(loc_id)
    try:
        pos = arrival_cell(rock, OPPOSITE[side])
    except Exception:
        pos = rock.entry_cell()
    return Exit(loc_id, pos, int(gx), int(gy))


def destination(gx, gy):
    """The location a map cell opens: a settlement or desert inside the
    map, and beyond it the deadloc whose exit faces back in."""
    if in_map(gx, gy):
        return world.location_at(gx, gy)
    # Which edge was crossed decides which way is back. Diagonal corners
    # are not reachable one side at a time, so one axis is always inside.
    if gx < MAP_X[0]:
        return deadloc_id(E)
    if gx > MAP_X[1]:
        return deadloc_id(W)
    return deadloc_id(S) if gy < MAP_Y[0] else deadloc_id(N)


def geo_id(loc, gx, gy):
    """g_id for lcall: the map cell packed as the client unpacks it.

    A deadloc gets z != 0 on top (LocIdToCoordinate: z = id >> 26), which
    Location.isSubLocation reads as "no way to the map from here": the exit
    window's map button and the panel's exit button both go dark
    (ExitLocationInterface.init, LocationInterface :704), and the only way
    out is the one zone leading back onto the map -- which is what a dead
    end at the world's edge is for. An interior of data/passages.json
    'no_map' gets the same bit, and the same dark buttons; its x and y are
    still the cell's, which the panel prints beside the name
    (Location.locationName). Bit 31 stays clear: that is a battleground to
    Location.isBGLocation.
    """
    packed = world.pack(round(gx), round(gy))
    if is_deadloc(loc.id) or no_map(loc.id):
        packed |= 1 << 26
    return packed


# --- arriving --------------------------------------------------------------
def _edge_distance(loc, cell, side):
    x, y = cell % loc.width, cell // loc.width
    return {W: x, N: y, E: loc.width - 1 - x, S: loc.height - 1 - y}[side]


def _edge_middle(loc, side):
    if side in (W, E):
        return (0 if side == W else loc.width - 1), loc.height / 2.0
    return loc.width / 2.0, (0 if side == N else loc.height - 1)


def _nearest(loc, cells, point):
    px, py = point
    return min(cells, key=lambda c: ((c % loc.width - px) ** 2
                                     + (c // loc.width - py) ** 2, c))


def arrival_cell(loc, side):
    """A cell to stand on having come in over the given edge.

    The entry cells nearest the middle of that edge, and only those actually
    on it: inzones ring a settlement, but some entries sit around the
    inhabitants in the middle, and the middle of the map is nearer the
    middle of any edge than the edge's own far corners are. A cell with the
    zone flag is avoided while there is a choice, so the first step does
    not have to be away from the exit window.

    Files without entries on that edge -- the deadloc files have none at
    all -- fall back to the cell just inside one of that edge's exit cells,
    which is walkable by construction: it is where a player stands before
    stepping out.
    """
    sides = exit_sides(loc)
    pool = list(loc.entries) + (war_entries(loc) if loc.war else [])
    on_edge = [c for c in pool if c not in loc.obstacles
               and _edge_distance(loc, c, side) <= EDGE_BAND]
    middle = _edge_middle(loc, side)
    quiet = [c for c in on_edge if c not in sides]
    if quiet:
        return _nearest(loc, quiet, middle)
    if on_edge:
        return _nearest(loc, on_edge, middle)
    inward = STEP[OPPOSITE[side]]
    inside = []
    for c, s in sides.items():
        if s != side:
            continue
        x, y = c % loc.width + inward[0], c // loc.width + inward[1]
        n = y * loc.width + x
        if 0 <= x < loc.width and 0 <= y < loc.height \
                and n not in loc.obstacles and n not in sides:
            inside.append(n)
    if inside:
        return _nearest(loc, inside, middle)
    zone = [c for c, s in sides.items() if s == side and c not in loc.obstacles]
    if zone:
        return _nearest(loc, zone, middle)
    return loc.entry_cell()


def door_arrival(loc, from_loc_id):
    """A cell inside an interior entered through a door: beside the door
    that leads back where the player came from when the table knows it,
    otherwise any free entry cell. Doors sit anywhere, so "beside" is by
    grid distance rather than by edge.

    A walk-in passage back counts as a door here, and its cells are never
    arrived on: standing on one is what sends a player through, and coming
    out of a passage onto its far mouth would read as the server bouncing
    them. So does a quest way back: someone Камал has brought up comes out
    at the end of the rails, where the way down is drawn, and someone Рудо
    has sent down arrives under the EXIT sign.
    """
    sides = exit_sides(loc)
    passing = set()
    for cells, _rec in walk_ins(loc):
        passing |= cells
    free = [c for c in loc.entries if c not in loc.obstacles
            and c not in sides and c not in passing]
    if not free:
        return loc.entry_cell()
    back = None
    for side in ("a", "b"):
        rec = door(loc.id, side)
        if rec and rec.get("target_loc_id") == from_loc_id and rec.get("cells"):
            back = rec["cells"]
            break
    if back is None:
        for cells, rec in walk_ins(loc) + quest_ways(loc):
            if rec.get("target_loc_id") == from_loc_id and cells:
                back = sorted(cells)
                break
    if back:
        cx = sum(c % loc.width for c in back) / float(len(back))
        cy = sum(c // loc.width for c in back) / float(len(back))
        return _nearest(loc, free, (cx, cy))
    return _nearest(loc, free, (loc.width / 2.0, loc.height / 2.0))


# --- the decision ----------------------------------------------------------
def plan_exit(loc, pos, gx, gy):
    """Where chWorld;to=1 from this cell leads. Raises Refused when it is
    not an exit cell, or a door whose far side is not known well enough."""
    if loc.id in SCENE_IDS and world.location_at(gx, gy) != loc.id:
        # A scene of rock the player walked into rather than onto: whichever
        # way it lets them walk, the way out is back to the place the cell
        # holds. The ring around the world is the other case -- there the
        # rock is the cell, and its own outzones answer below.
        back = world.location(world.location_at(gx, gy))
        return Exit(back.id, back.entry_cell(), int(gx), int(gy))
    side = side_at(loc, pos)
    if side is None:
        raise Refused("Здесь нет выхода")
    inner = side_way(loc.id, side) if side in SIDES else None
    if inner is not None:
        # One interior into the next (data/passages.json 'sides'): arrived
        # at over the opposite edge, the map cell kept -- the place is the
        # cell it was entered from -- unless the far side has a cell of
        # its own.
        try:
            dest = world.location(int(inner["target_loc_id"]))
        except (KeyError, OSError, TypeError, ValueError):
            raise Refused("Локации %s за этим проходом нет" % inner["target_loc_id"])
        cell = world.cell_of(dest.id)
        if cell is not None:
            gx, gy = cell
        return Exit(dest.id, arrival_cell(dest, OPPOSITE[side]), int(gx), int(gy))
    if side in SIDES:
        nx, ny = neighbour(gx, gy, side)
        # What a location's own file says about its sides is never argued
        # with here: an outzone pointing east means the player goes east,
        # and the ground beyond is whatever stands there. Only two things
        # have no cell to offer -- the end of the world, and the lake -- and
        # both answer with a pocket of rock rather than an error window,
        # which is what walking up to a wall looks like from inside. A
        # player who somehow stands on water is not locked in: only the far
        # side is asked.
        if not in_map(nx, ny) or (not world.passable(nx, ny)
                                  and world.passable(gx, gy)):
            return dead_end(side, gx, gy)
        dest = world.location(destination(nx, ny))
        return Exit(dest.id, arrival_cell(dest, OPPOSITE[side]), nx, ny)
    rec = door(loc.id, side)
    target = rec.get("target_loc_id") if rec else None
    if target is None or rec.get("confidence") not in DOOR_CONFIDENCE:
        raise Refused("Куда ведёт этот проход, пока неизвестно")
    try:
        dest = world.location(int(target))
    except (KeyError, OSError):
        raise Refused("Локации %s за этим проходом нет" % target)
    # An interior belongs to the cell its entrance stands on -- unless the
    # door's record says own_cell (data/passages.json): a door up into one of
    # several entrances above one interior (the Вади-Хальфа mine's three)
    # arrives on that entrance's own cell, whichever it went down by.
    cell = world.cell_of(dest.id) if rec.get("own_cell") else None
    if cell is not None:
        gx, gy = cell
    return Exit(dest.id, door_arrival(dest, loc.id), int(gx), int(gy))


def _beyond(loc, rec, gx, gy):
    """The Exit at the far end of a walk-in or a quest way.

    A place that stands on the map is arrived at on its own cell, whatever
    cell the player had: someone put into the mine by /goto comes out at
    the mine's mouth, and the map then shows them there. An interior keeps
    the cell of whatever it was entered from, as behind a door.
    """
    target = rec.get("target_loc_id")
    try:
        dest = world.location(int(target))
    except (KeyError, OSError, TypeError, ValueError):
        raise Refused("Локации %s за этим проходом нет" % target)
    cell = world.cell_of(dest.id)
    if cell is not None:
        gx, gy = cell
    return Exit(dest.id, door_arrival(dest, loc.id), int(gx), int(gy))


def plan_walk_in(loc, pos, gx, gy):
    """Where the walk-in passage under pos leads. Raises Refused off any, or
    when its far side is no file."""
    rec = walk_in_at(loc, pos)
    if rec is None:
        raise Refused("Здесь нет прохода")
    return _beyond(loc, rec, gx, gy)


def plan_quest_way(loc, quest_type, gx, gy):
    """Where handing quest_type in here leads. Raises Refused when it is not a
    quest way of this location, or its far side is no file."""
    rec = quest_way(loc, quest_type)
    if rec is None:
        raise Refused("Это задание никуда не ведёт")
    return _beyond(loc, rec, gx, gy)


def home(row, start):
    """(loc_id, gx, gy) of where a character wakes up: the location
    registered with on_conv;op=0 and its cell -- or the start it was made
    in, which creation writes as its home (accounts.create_character) --
    or the start when none was, or the registered one no longer resolves
    to a file.

    row is the characters row (or None); start is (loc_id, gx, gy). A home
    saved before its cell was stored takes the cell of the settlement it
    is, its own coordinates when it is desert, and the start otherwise.
    """
    loc_id = row["home_loc"] if row is not None else None
    if not loc_id or world.path_for(int(loc_id)) is None:
        return start
    loc_id = int(loc_id)
    gx, gy = row["home_gx"], row["home_gy"]
    if gx is not None and gy is not None:
        return loc_id, int(gx), int(gy)
    if world.is_wilderness(loc_id):
        return (loc_id,) + world.unpack(loc_id)
    for cell, settled in world.settlements().items():
        if settled == loc_id:
            return loc_id, cell[0], cell[1]
    return loc_id, start[1], start[2]


# --- map marks -------------------------------------------------------------
def mark_cell(gx, gy, dx, dy):
    """The absolute cell of a mark placed dx,dy from the player.

    insMark carries floor(x - walker.x) (GlobalMap.addMark), and the client
    draws its own copy at floor(walker.x + dx) (createMark). The same sum
    here keeps both sides on one cell whatever fraction the player is at.
    """
    return int(math.floor(gx + dx)), int(math.floor(gy + dy))


def marks_frame(rows, gx, gy):
    """The marks frame that has to follow every gmap: offsets from the
    player in whole cells, titles and infos in parallel lists, in the order
    the client will later index them by (GlobalMap.marks). The offset is
    against the whole cell under the player, so that floor(walker.x + dx)
    lands on the stored cell again."""
    ox, oy = int(math.floor(gx)), int(math.floor(gy))
    dxdy, title, info = [], [], []
    for r in rows:
        dxdy += [r["x"] - ox, r["y"] - oy]
        title.append(Str(r["title"]))
        info.append(Str(r["info"]))
    return dict(dxdy=dxdy, title=title, info=info)
