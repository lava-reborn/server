"""Read a location's own XML: geometry, entry cells and mob spawns.

The shipped client kept more than artwork in res/locations. Alongside the
drawing instructions each file carries the walkability grid, the cells players
arrive on, and the spawn points with the type ids they refer to, for 1356 of
the 1396 locations. Only the serverdata node was emptied before release.

Coordinates are packed as hex byte pairs inside a single text node, read at a
fixed stride: 4 characters per cell for the plain lists, 5 where a per-cell
extra byte follows, and 8 for mob spawns, whose last four characters are the
type id. A hex cell's number is gy * width + gx.
"""
import json
import math
import os
import re

# The servers run under WSL while the client lives on the Windows drive, so
# fall back to the mounted path whenever the configured one is unreachable.
RES = os.environ.get("LAVA_RES") or ""
if not os.path.isdir(RES):
    for _candidate in (r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res",
                       "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        if os.path.isdir(_candidate):
            RES = _candidate
            break

# Entity.as: the class the client builds for an entity, taken from its
# root_type_id in mobs.xml and sent back as rtype in lch.
MOB, TRADER, TEACHER, UPGRADER, COMMONER, HEALER, LESSOR, AUCTIONER = range(8)

# The frame name is the dispatch key, so each class needs its own command.
USERINFO = {
    MOB: "userInfo",
    TRADER: "userInfo_Trader",
    TEACHER: "userInfo_SpecTrainer",
    UPGRADER: "userInfo_Upgrader",
    COMMONER: "userInfo_Commoner",
    HEALER: "userInfo_Medic",
    LESSOR: "userInfo_Lessor",
    AUCTIONER: "userInfo_Auctioneer",
}


def _read(path):
    """Location files are UTF-8 despite declaring windows-1251."""
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", "replace")


def _chunks(txt, tag, step):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), txt, re.S)
    if not m or not m.group(1).strip():
        return []
    s = "".join(m.group(1).split())
    return [s[i:i + step] for i in range(0, len(s) - step + 1, step)]


# A location id is not always a file number. SSEmulator.getLocDescription
# resolves one and the server has to agree exactly, because both sides read
# the walkability grid out of whatever file they picked: disagree, and the
# player walks through walls the client is drawing, or into ones it is not.
#
#   locations/static/<id>.xml   whenever that file exists
#   id >> 28 == 4               locations/deadloc/<(id >> 26) & 3>.xml
#   id >> 26 == 0               open desert, gx = id >> 13, gy = id & 0x1FFF,
#                               tile ((gx + gy) & 3) + 1 of four
#
# That last rule is why the whole global map is reachable without a table of
# any kind: a cell with nothing on it packs into an id that resolves, from its
# own coordinates, to one of four wasteland tiles.
GEO_SHIFT = 13
GEO_MASK = 0x1FFF


def pack(gx, gy):
    """Map cell to the id the client unpacks in LocIdToCoordinate."""
    return (int(gx) << GEO_SHIFT) | (int(gy) & GEO_MASK)


def unpack(geo):
    return geo >> GEO_SHIFT, geo & GEO_MASK


def is_wilderness(loc_id):
    """True when the id is a packed map cell rather than a location file.

    The two spaces overlap on paper -- a file number and a packed cell are
    both just integers -- but not in practice: no real map column is 0, so a
    packed cell is always far above the 1381 file numbers.
    """
    return not os.path.isfile(
        os.path.join(RES, "locations", "static", "%d.xml" % loc_id))         and loc_id >> 26 == 0


def path_for(loc_id):
    """The file behind a location id, or None where the client draws nothing."""
    static = os.path.join(RES, "locations", "static", "%d.xml" % loc_id)
    if os.path.isfile(static):
        return static
    if loc_id >> 28 == 4:
        return os.path.join(RES, "locations", "deadloc",
                            "%d.xml" % ((loc_id >> 26) & 3))
    if loc_id >> 26 == 0:
        gx, gy = unpack(loc_id)
        return os.path.join(RES, "locations", "desert",
                            "%04d.xml" % (((gx + gy) & 3) + 1))
    return None


class Location:
    def __init__(self, loc_id):
        self.id = loc_id
        path = path_for(loc_id)
        if path is None:
            raise KeyError("no file for location %d" % loc_id)
        self.file = os.path.basename(os.path.dirname(path)) + "/" +             os.path.basename(path)
        txt = _read(path)
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        self.title = attrs.get("title", "")
        # The name the location was built under. It carries the region it
        # belongs to -- WH_Gold_Traders_old against DN_Gold_Traders_old -- and
        # marks the scratch files, which is what data/build_settlements.py
        # needs to tell identically titled places apart.
        self.fn = attrs.get("fn", "")
        self.width = int(attrs["width"])
        self.height = int(attrs["height"])
        self.war = int(attrs.get("war", 0))
        self.pvp = int(attrs.get("pvp", 0))

        self.obstacles = {self._cell(c) for c in _chunks(txt, "obstacles", 5)}
        self.entries = [self._cell(c) for c in _chunks(txt, "inzones", 4)]
        self.spawns = [(self._cell(c), int(c[4:8], 16))
                       for c in _chunks(txt, "mobs", 8)]

    def _cell(self, chunk):
        gx, gy = int(chunk[0:2], 16), int(chunk[2:4], 16)
        return gy * self.width + gx

    def entry_cell(self):
        """A free entry cell, preferring one near whoever lives here.

        inzones usually rings the whole map, and its first cell tends to sit in
        a far corner with nothing around it. Spawning beside the inhabitants
        makes the location look inhabited the moment it opens.
        """
        free = [c for c in self.entries if c not in self.obstacles]
        if not free:
            return self.entries[0] if self.entries else 0
        if not self.spawns:
            return free[0]
        cx = sum(c % self.width for c, _t in self.spawns) / len(self.spawns)
        cy = sum(c // self.width for c, _t in self.spawns) / len(self.spawns)
        return min(free, key=lambda c: (c % self.width - cx) ** 2
                                       + (c // self.width - cy) ** 2)


_CACHE = {}


def location(loc_id):
    """A parsed location, kept after the first read.

    There are 1381 of them and a settlement runs to tens of kilobytes, so
    re-reading one per visit would put a disk read in the middle of every
    entry. They never change while the server runs.
    """
    loc = _CACHE.get(loc_id)
    if loc is None:
        loc = _CACHE[loc_id] = Location(loc_id)
    return loc


_SETTLEMENTS = None


def settlements():
    """Map cell -> location id, for the cells that hold a named place.

    Rebuilt by data/build_settlements.py from the client's own map tooltips
    and location titles; see that script for what is and is not recovered.
    """
    global _SETTLEMENTS
    if _SETTLEMENTS is None:
        _SETTLEMENTS = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "settlements.json"),
                      encoding="utf-8") as fh:
                for cell, loc_id in json.load(fh)["cells"].items():
                    gx, gy = cell.split(",")
                    _SETTLEMENTS[(int(gx), int(gy))] = int(loc_id)
        except (OSError, ValueError, KeyError):
            pass
    return _SETTLEMENTS


_CELL_OF = None


def cell_of(loc_id):
    """The map cell a location stands on, or None for an interior.

    The reverse of location_at. A settlement is reachable both by walking
    onto its cell and by being sent there directly, and in the second case
    the player's position on the map has to follow, or leaving puts them
    back wherever they happened to stand before. A settlement wide enough
    to cover two cells answers with the first.
    """
    global _CELL_OF
    if _CELL_OF is None:
        _CELL_OF = {}
        for cell, i in sorted(settlements().items()):
            _CELL_OF.setdefault(i, cell)
    return _CELL_OF.get(loc_id)


def location_at(gx, gy):
    """Which location a map cell leads into.

    Always answers: a cell with no settlement on it is open desert, and the
    packed cell is its own location id.
    """
    # Floor, not round: the client's own cell under a position is
    # Math.floor(x) (DisplayGlobalMap.as:207, DisplayLandscape.as:29), the
    # settlement icon is drawn from the cell's top-left corner, and a player
    # standing anywhere on that square expects to walk into it. Rounding
    # sent the half of the square past its centre into the neighbour.
    cell = (int(math.floor(gx)), int(math.floor(gy)))
    found = settlements().get(cell)
    return pack(cell[0], cell[1]) if found is None else found


_TERRAIN = None

# The characters data/map_terrain.json uses for ground nobody walks over.
BLOCKED = "#~"


def terrain():
    """The map's ground, as (bounds, rows) with one character per cell.

    RECOVERED, not original. The server that knew which cells were mountain
    is gone; data/build_terrain.py reads the passability back out of the
    client's own map tiles -- roughness of the photograph for rock, blue over
    red for water -- and checks it against every settlement and every map
    tooltip. See data/map_terrain_report.md for how far it can be trusted.

    Missing or broken, the table leaves the map as it was before: walkable
    everywhere inside its rectangle. A server that cannot read a file has no
    business freezing the world.
    """
    global _TERRAIN
    if _TERRAIN is None:
        # The rectangle is travel.MAP_X/MAP_Y, repeated here because travel
        # imports this module and not the other way round.
        _TERRAIN = ((5833, 1600, 6305, 2110), [])
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "map_terrain.json"),
                      encoding="utf-8") as fh:
                doc = json.load(fh)
            b = doc["bounds"]
            rows = doc["rows"]
            wide = b["gx1"] - b["gx0"] + 1
            high = b["gy1"] - b["gy0"] + 1
            if len(rows) != high or any(len(r) != wide for r in rows):
                raise ValueError("map_terrain.json does not fill its bounds")
            _TERRAIN = ((b["gx0"], b["gy0"], b["gx1"], b["gy1"]), rows)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return _TERRAIN


def passable(gx, gy):
    """Whether a walker can stand on a map cell.

    Floor, not round, like location_at: the cell under a position is the one
    the client draws the figure on. Outside the map's rectangle nothing is
    walkable -- the edge of the world is crossed through a location's exit,
    not by walking off the map.
    """
    (gx0, gy0, gx1, gy1), rows = terrain()
    x, y = int(math.floor(gx)), int(math.floor(gy))
    if not (gx0 <= x <= gx1 and gy0 <= y <= gy1):
        return False
    if not rows:
        return True
    return rows[y - gy0][x - gx0] not in BLOCKED


_SUBSTITUTES = None


def substitute(type_id):
    """A known creature to stand in for one the client cannot draw, or None.

    DESIGNED, not recovered. 664 of the creature types the location files
    spawn are gone from the shipped mobs.xml, so a battle camp would open
    with its fighters missing. data/spawn_substitutes.json (built by
    data/build_spawn_substitutes.py) maps each such type to a known creature
    of the same faction -- read off the camp's own file name and the prefix
    its known inhabitants share -- and the nearest level. rooms.Room asks
    here only for hostile creatures in war=1 locations; a stand-in is never
    a shopkeeper, and never stands in a peaceful place.
    """
    global _SUBSTITUTES
    if _SUBSTITUTES is None:
        _SUBSTITUTES = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "spawn_substitutes.json"),
                      encoding="utf-8") as fh:
                for k, v in json.load(fh)["substitutes"].items():
                    _SUBSTITUTES[int(k)] = int(v["type_id"])
        except (OSError, ValueError, KeyError):
            pass
    return _SUBSTITUTES.get(type_id)


# Spawn entries that belong to a season, a clan or the developers rather than
# to the place. The location files still carry the New Year lottery stall,
# the Victory Day trader and clan-event vendors, and wasteland templates were
# reused for clan events, which is why a clan's trader stands in open desert.
# Recognised by the tokens of the internal name, split on _ and digits.
EVENT_TOKENS = {"vov", "vbg", "lemon", "ny", "9may", "presents", "lotery",
                "lottery", "hw", "xmas", "valentine", "valentines", "admin",
                "test", "event", "prazdnik"}

_ROLES = None


def creature_role(type_id):
    """'mob', 'boss', 'animal', 'object' from data/mob_types.json, or None
    for the NPC classes, which carry no role there."""
    global _ROLES
    if _ROLES is None:
        _ROLES = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "mob_types.json"),
                      encoding="utf-8") as fh:
                data = json.load(fh)
            for k, v in (data.get("types") or data).items():
                if isinstance(v, dict) and v.get("role"):
                    _ROLES[int(k)] = v["role"]
        except (OSError, ValueError):
            pass
    return _ROLES.get(type_id)


def _name_tokens(name):
    return {t for t in re.split(r"[^A-Za-z]+", name.lower()) if t}


def belongs_here(type_id, name, root, war):
    """Whether a spawn from the location file should stand in the room.

    Three kinds are left out. Seasonal, clan and developer entries, by the
    tokens of their name. Loot containers and other "objects", which the
    client would draw as creatures with a health bar and which need loot
    logic that does not exist yet. And hostile creatures (root 0) in a
    peaceful location: a market with war=0 had them in its file for events
    and quests, and a player cannot fight there anyway.
    """
    if _name_tokens(name) & EVENT_TOKENS:
        return False
    if creature_role(type_id) == "object":
        return False
    if root == MOB and not war:
        return False
    return True


def mob_types():
    """type_id -> (root_type_id, internal name, art folder).

    The art folder is the "resource" attribute, and it is what the client wants
    in the res field: it builds paths as mobs/<resource>/..., with names like
    1f_npc9 or q4-1 rather than anything numeric. Sending the type id there
    leaves the creature invisible.
    """
    txt = _read(os.path.join(RES, "database", "mobs.xml"))
    out = {}
    for m in re.finditer(r'<mob type_id="(\d+)"\s+root_type_id=\s*"(\d+)"'
                         r'\s+name="([^"]*)"(?:\s+resource="([^"]*)")?', txt):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3), m.group(4) or "")
    return out


def avatars():
    """The eight entries of avatars/list.xml as (id, sex) pairs.

    The two fields are not interchangeable and both have to come from the same
    entry. id picks the portrait, avatars/<id>_1.png. sex picks the body,
    because PersInfo.set sex assigns persType as a side effect and the walker
    resolves art as personages/<persType>. Mixing an id from one row with a sex
    from another puts a different person in the corner than the one standing in
    the location.
    """
    txt = _read(os.path.join(RES, "avatars", "list.xml"))
    return [(m.group(1), int(m.group(2)))
            for m in re.finditer(r"<a\s+id='([^']*)'\s+sex='(\d+)'", txt)]
