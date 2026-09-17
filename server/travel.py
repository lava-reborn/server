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
data/settlements.json or open desert. A door is a lookup in data/exits.json,
and only entries recovered with some confidence are followed; the rest are
refused with a word in chat rather than sent somewhere wrong.

Past the map's rectangle lie the four "Граница пустоши" files,
locations/deadloc/0..3: no inhabitants, no obstacles, and zones along one
edge only, west, north, east, south by file number. A step off the map
opens the one whose single exit faces back in.

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

# The playable rectangle of the global map (world.md §5, TASKS 8.8): every
# recovered settlement and every tooltip cell lies within it. A neighbour
# outside is the edge of the world.
MAP_X = (5833, 6305)
MAP_Y = (1600, 2110)

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


def door(loc_id, side):
    """The data/exits.json record for door a or b of a location, or None."""
    entry = _table("exits.json", "doors").get(str(loc_id))
    if not entry:
        return None
    for rec in entry.get("doors", ()):
        if rec.get("side") == side:
            return rec
    return None


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
    while True:
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


def deadloc_id(exit_side):
    """The edge-of-the-world location whose one exit is on exit_side."""
    return DEADLOC_BASE | (SIDES.index(exit_side) << 26)


def is_deadloc(loc_id):
    return loc_id >> 28 == 4


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
    end at the world's edge is for. Bit 31 stays clear: that is a
    battleground to Location.isBGLocation.
    """
    packed = world.pack(round(gx), round(gy))
    if is_deadloc(loc.id):
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
    grid distance rather than by edge."""
    sides = exit_sides(loc)
    free = [c for c in loc.entries if c not in loc.obstacles and c not in sides]
    if not free:
        return loc.entry_cell()
    for side in ("a", "b"):
        rec = door(loc.id, side)
        if rec and rec.get("target_loc_id") == from_loc_id and rec.get("cells"):
            cells = rec["cells"]
            cx = sum(c % loc.width for c in cells) / float(len(cells))
            cy = sum(c // loc.width for c in cells) / float(len(cells))
            return _nearest(loc, free, (cx, cy))
    return _nearest(loc, free, (loc.width / 2.0, loc.height / 2.0))


# --- the decision ----------------------------------------------------------
def plan_exit(loc, pos, gx, gy):
    """Where chWorld;to=1 from this cell leads. Raises Refused when it is
    not an exit cell, or a door whose far side is not known well enough."""
    side = side_at(loc, pos)
    if side is None:
        raise Refused("Здесь нет выхода")
    if side in SIDES:
        nx, ny = neighbour(gx, gy, side)
        # The mountains hold here too. Walking the map stops at the rock
        # (move_on_map), but a location's side exit handed over the next
        # cell without looking, so a ring of peaks could be stepped over
        # one location at a time -- which is how the Nubian valley, sealed
        # on the map, was still being walked out of. A player already
        # standing on rock is not locked in: only the far side is asked.
        if not world.passable(nx, ny) and world.passable(gx, gy):
            raise Refused("Дальше горы, здесь не пройти")
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
    # An interior belongs to the cell its entrance stands on.
    return Exit(dest.id, door_arrival(dest, loc.id), int(gx), int(gy))


def home(row, start):
    """(loc_id, gx, gy) of where a character wakes up: the location
    registered with on_conv;op=0 and its cell, or the start when none was,
    or the registered one no longer resolves to a file.

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
