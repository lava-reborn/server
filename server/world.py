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

# Where a trophy is registered (trophies.py). The six «Сумасшедший живодер»
# of «Мясники» (VH_Butchers, location 164, the map's "Мясники, скупка
# трофеев" at 5979,1721 in Вади-Хальфа) -- собиратель пальцев, ушей, рук,
# скальпов, черепов, рогов и копыт (texts.xml 60521..60526) -- and the
# original's own "Регистрация трофеев", Tr_registr_cor/_a/_b (Одноглазый Джо,
# Михалыч, Герцль, texts.xml 50639..50641) and _c, which no location puts
# down. mobs.xml makes the butchers Commoners, but a trophy is registered in
# a trade session (Trade.regTrophy, ss_upd 6), and the client opens one only
# with a Trader (Gamer.proposeContact) and offers "regTrophy" only for a
# Trader's can_trophy (NPCService.openService): so they are built as
# Traders (entity_root) that sell and repair nothing.
# And one DESIGNED, where the owner put him (2026-09-25: «унеси сохранение
# трофея от адама к демиру»): Демир (5193), the valley's taxi driver, in
# «Караван» (186, 6271,1829). Every character starts inside the walled
# Nubian valley and the butchers are out of its reach, so without him
# «Навык бойца» could not rise at all. mobs.xml makes him a Commoner, and
# a Commoner's only service here was «Прописка»; as a Trader he cannot keep
# it -- NPCService.openService gives a Trader trade, repair and regTrophy
# and never the "support" tab, and a Commoner never gets the Trade session
# RegTrophyInterface works in (Gamer.proposeContact) -- so the caravan's
# «Прописка» is Крысолов's and the Точильный камень's (5194, 5192), both
# Commoners standing in the same location; home is the location, not the
# person. His quests («Нет больше покоя» and the valley's way out,
# «В Хальфу!») still show: the quests tab is every class's. Адам (5216,
# Нубийский рынок), who stood in for him before, is an ordinary Trader
# again. And Хассир (105) at the station of Вади-Хальфы,
# whose map label says he registers trophies; a Trader already, he keeps his
# stall and his repairs besides (trophies.KEEPS_STALL).
TROPHY_REGISTRARS = frozenset({939, 940, 941, 942, 943, 1132,
                               2033, 2034, 2035, 2036,
                               5193, 105})


def entity_root(type_id, root):
    """The class an inhabitant is built as on the client (lch rtype): the
    root of mobs.xml, but a trophy registrar is a Trader."""
    return TRADER if type_id in TROPHY_REGISTRARS else root


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

# The rectangle the world is played on, and the single place it is written
# down (travel re-exports it; travel imports this module and not the other way
# round).
#
# West and north are the client's own word. The captions on gx=5833 and
# gy=1600 read "Западные Предгорья" and "Северные Предгорья", and the two
# locations the placer stood there -- 182 on 5833,1607 and 322 on 5840,1600
# -- have no outzone pointing outward at all (recon/analysis/borders.md §8).
# 182 has since moved to the valley's «Поля и Пастбища» (6268,1818, data/
# settlements_verified.json), the cows' place it is; the captions stay.
#
# East and south are not that: 5833..6305 by 1600..2110 is the bounding box of
# the 414 map captions, and the settlements on its east and south rim (303
# "Выход с карьера" on 6305,1841, 280 "Шахта Мероэ" on 5943,2110) do have
# exits pointing outward, so the world went on past them. It is taken to the
# last cell the client can draw: res/globalmap/full covers tiles tx 182..197
# by ty 50..66 at 32 cells a tile, that is gx 5824..6335 by gy 1600..2143, and
# past that the map screen has no picture to show at all. That keeps both of
# those exits leading onto drawn ground instead of into a refusal.
MAP_X = (5833, 6335)
MAP_Y = (1600, 2143)

# The Nubian valley, where every new character starts: gx0, gy0, gx1, gy1,
# inclusive. Open ground inside it is no place to attack another player.
#
# The original made it so with its own tiles. The valley's wasteland was
# Noob_000_n..Noob_026 (static 1334..1360, all "Пустошь", all pvp="0"), its
# inner walls NoPvP_UpSide1/2 and NoPvP_LeftSide2 (pvp="0" copies of the rim's
# rock), and every settlement in it is pvp="0" but the one built for the
# purpose, "Арена Нубии" (167, pvp="1"). Which cell held which of those tiles
# lived in the serverdata node and is gone, so here the valley's open cells
# fall to the generic desert templates like any other -- and those carry no
# pvp attribute, which the client reads as "allowed" (see Location.pvp).
#
# DESIGNED: the rectangle is the wiki's own coordinates for the valley's
# places -- Поля и Пастбища 6268x1818 and Северный поселок 6268x1819 to the
# north, Захоронения предков 6261x1825 to the west, Лагерь Бандитов 6272x1840
# to the south, Старая шахта 6273x1829 to the east, fifteen in all -- grown by
# one cell on each side, so that the ground right around the outermost of
# them is the valley's too. The wall the owner drew round the valley
# (data/terrain_verified.json) shuts in 112 cells, 6261..6274 by 1818..1841,
# and every one of them is inside this; it is kept as a rectangle of its own
# so that the rule does not move if the wall one day opens.
#
# But the wall is no rectangle, and 39 open cells of this one lie on its far
# side -- 6260,1828..1833, 6261,1838..1841, 6274,1818..1820 and so on, the
# common wasteland one step from anybody walking past. Counted in, they were
# a strip of the open world where nobody could be attacked, told "Нубийская
# долина" about it. So those are carved out (valley_outskirts), for as long
# as the wall keeps them out: once the valley itself can be walked into from
# outside, the rectangle is the valley again, whole.
NOOB_VALLEY = (6260, 1817, 6274, 1841)
# A cell the wall shuts in: the Нубийское поселение, where everyone starts.
NOOB_VALLEY_HEART = (6268, 1819)
# Whether the valley keeps the original's peace between players. The owner
# turned it off (2026-09-24): players fight on the valley's open ground as
# anywhere else in the wasteland. LAVA_NOOB_VALLEY_SAFE=1 brings the rule
# back -- in the valley only «Арена Нубии» then.
NOOB_VALLEY_SAFE = os.environ.get("LAVA_NOOB_VALLEY_SAFE", "0") == "1"

_OUTSKIRTS = None


def valley_outskirts():
    """The open cells of NOOB_VALLEY that lie outside the owner's wall.

    Walked from the ground around the rectangle, over passable cells only
    and a side at a time (travel.neighbour, as a player walks the map), and
    empty if that walk reaches NOOB_VALLEY_HEART: then there is no wall to
    speak of, and nothing is carved out of the valley.
    """
    global _OUTSKIRTS
    if _OUTSKIRTS is None:
        x0, y0, x1, y1 = NOOB_VALLEY

        def inside(c):
            return x0 <= c[0] <= x1 and y0 <= c[1] <= y1

        steps = ((1, 0), (-1, 0), (0, 1), (0, -1))
        todo = []
        for x in range(x0 - 1, x1 + 2):
            for y in range(y0 - 1, y1 + 2):
                if inside((x, y)) or not passable(x, y):
                    continue
                for dx, dy in steps:
                    n = (x + dx, y + dy)
                    if inside(n) and passable(*n):
                        todo.append(n)
        seen = set(todo)
        while todo:
            c = todo.pop()
            for dx, dy in steps:
                n = (c[0] + dx, c[1] + dy)
                if n not in seen and inside(n) and passable(*n):
                    seen.add(n)
                    todo.append(n)
        _OUTSKIRTS = frozenset(() if NOOB_VALLEY_HEART in seen else seen)
    return _OUTSKIRTS


def in_noob_valley(gx, gy):
    """Whether a map cell is the Nubian valley's: in NOOB_VALLEY, and not on
    the outer side of its wall."""
    x0, y0, x1, y1 = NOOB_VALLEY
    if not (x0 <= gx <= x1 and y0 <= gy <= y1):
        return False
    return (int(gx), int(gy)) not in valley_outskirts()


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
        # Whether a player may be attacked here, read exactly as the client
        # reads it (LDParser: pvpEnabled = attributes.pvp != "0"): a file
        # that does not say is open to it. That is the whole wasteland -- the
        # desert templates, the deadloc rim, 24 rock and coast tiles and four
        # quest places -- and the client acts on it, sending the shot or the
        # blow instead of showing its own "В этой локации Вы не можете
        # нападать на других игроков". A server that read the silence as "no"
        # answered every one of them with res=3, which the client words as
        # "Сервер не отвечает", on 272 847 of the map's 273 632 cells: the
        # open world had no fighting between players at all, and the 828
        # files with pvp="1" were the only places it was left.
        self.pvp = int(attrs.get("pvp") != "0")
        # Open desert inside the Nubian valley stands in for the valley's own
        # lost tiles, which said pvp="0" (NOOB_VALLEY). The client still reads
        # the template and lets the blow go, so the refusal is the server's,
        # and combat.Fighter.refuse_pvp says in chat why -- while the valley
        # is kept peaceful at all (NOOB_VALLEY_SAFE).
        self.newbies = (NOOB_VALLEY_SAFE and self.file.startswith("desert/")
                        and in_noob_valley(*unpack(loc_id)))
        if self.newbies:
            self.pvp = 0

        self.obstacles = {self._cell(c) for c in _chunks(txt, "obstacles", 5)}
        # The counter of a range, shot over but not walked over (SHOOT_OVER).
        self.shoot_over = frozenset(
            self._cell(c) for c in _chunks(txt, "obstacles", 5)
            if c[4] == "1") if loc_id in SHOOT_OVER else frozenset()
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


_BORDERS = None


def borders():
    """Map cell -> location id, for the ring of rock around the world.

    PROPOSED, not recovered, and the nearest thing to the original there can
    be: the client ships the kit a wall was built out of -- four sides in two
    variants, four corners, all titled "Скалы", all war=1 -- and a tile's wall
    is the side its outzones never touch. data/build_borders.py lays one per
    rim cell with the wall facing out, so the edge of the world is a place a
    player walks into and finds rocks, rather than a line a walker is stopped
    at for no visible reason. recon/analysis/borders.md has the evidence.

    Missing or broken, the world simply has open desert on its rim and the
    rectangle alone holds the walker in.
    """
    global _BORDERS
    if _BORDERS is None:
        _BORDERS = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "borders.json"),
                      encoding="utf-8") as fh:
                for cell, loc_id in json.load(fh)["cells"].items():
                    gx, gy = cell.split(",")
                    _BORDERS[(int(gx), int(gy))] = int(loc_id)
        except (OSError, ValueError, KeyError):
            pass
    return _BORDERS


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

    Three tables in order of how well they are known: the settlement placed
    there, then the rock of the world's rim, then -- always, for every other
    cell -- open desert, whose packed cell is its own location id.

    The rim comes second because a settlement is evidence and the ring is a
    proposal; data/build_borders.py leaves those cells out of the ring for
    the same reason, and this order holds even if somebody adds a settlement
    on the rim by hand in settlements_verified.json.
    """
    # Floor, not round: the client's own cell under a position is
    # Math.floor(x) (DisplayGlobalMap.as:207, DisplayLandscape.as:29), the
    # settlement icon is drawn from the cell's top-left corner, and a player
    # standing anywhere on that square expects to walk into it. Rounding
    # sent the half of the square past its centre into the neighbour.
    cell = (int(math.floor(gx)), int(math.floor(gy)))
    found = settlements().get(cell)
    if found is None:
        found = borders().get(cell)
    return pack(cell[0], cell[1]) if found is None else found


_TERRAIN = None

# The one character of data/map_terrain.json that still stops a walker.
#
# The table also carries "#" for rock, read off how rough the photograph is,
# and that column is no longer believed: LAVA never had a terrain layer. The
# client carries none (recon/analysis/borders.md §3), every one of the eleven
# locations/desert templates the server falls back to has all four outzones,
# and so every cell the roughness called a mountain would open as plain
# wasteland with four ways out the moment a player stood in it. It walled off
# 6130 cells that way and contradicted 18 of the 949 exits the settlement
# files themselves declare. Rock is a location now (data/borders.json), not a
# pixel.
#
# Water stays, because it is the one thing the photograph finds reliably:
# blue over red is Lake Nasser and a little speckle, it is not something a
# threshold was tuned to produce, and no exit of any known location leads into
# it (0 of 949).
BLOCKED = "#~"


def terrain():
    """The map's rock and water, as (bounds, rows), one character per cell.

    RECOVERED, not original: data/build_terrain.py reads it off the client's
    own map tiles, and data/map_terrain_report.md says how far that can be
    trusted. It is a photograph, so it is evidence and not testimony -- where
    a location file declares an exit into a cell this calls rock, the file
    wins and the cell is opened (data/terrain_repairs.json).

    The rows cover the rectangle the photograph was read over, which is no
    longer the whole world (MAP_X/MAP_Y reach further east and south). A cell
    outside the rows is simply dry.

    Missing or broken, the table leaves the map walkable everywhere inside its
    rectangle. A server that cannot read a file has no business freezing the
    world.
    """
    global _TERRAIN
    if _TERRAIN is None:
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


_TERRAIN_FIX = None
_TERRAIN_OPEN = None


def terrain_overrides():
    """Cells a player has walked and the table got wrong, by cell.

    Little is left for it to correct now that only water stops anyone -- the
    footpaths it was opened for are open by construction -- but the
    arrangement stays: where somebody who has stood there says otherwise,
    their word wins over data/map_terrain.json, the same way
    settlements_verified.json wins over the placer. It cannot reach outside
    the world's rectangle, which is not a matter of opinion.
    """
    global _TERRAIN_FIX
    if _TERRAIN_FIX is None:
        _TERRAIN_FIX = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "terrain_verified.json"),
                      encoding="utf-8") as fh:
                doc = json.load(fh)
            for cell in doc.get("passable") or ():
                gx, gy = cell.split(",")
                _TERRAIN_FIX[(int(gx), int(gy))] = True
            for cell in doc.get("blocked") or ():
                gx, gy = cell.split(",")
                _TERRAIN_FIX[(int(gx), int(gy))] = False
        except (OSError, ValueError, KeyError, AttributeError):
            pass
    return _TERRAIN_FIX


def terrain_repairs():
    """Cells the picture calls rock and a location file calls its own exit.

    Eighteen declared exits out of 951 lead into one, over fifteen cells.
    Without this the server would refuse a step the game itself promises and
    the player would meet a wall that is in no file -- which is how the rock
    layer earned its removal the first time round. Built by
    data/build_terrain_repairs.py, which lists the reason for every cell.
    """
    global _TERRAIN_OPEN
    if _TERRAIN_OPEN is None:
        _TERRAIN_OPEN = set()
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "terrain_repairs.json"),
                      encoding="utf-8") as fh:
                doc = json.load(fh)
            for cell in doc.get("opened") or ():
                gx, gy = cell.split(",")
                _TERRAIN_OPEN.add((int(gx), int(gy)))
        except (OSError, ValueError, KeyError, AttributeError):
            pass
    return _TERRAIN_OPEN


def in_map(gx, gy):
    """Whether a cell is inside the world's rectangle at all.

    passable() answers no for everything outside, which is right for a
    walker but wrong for a question about the ground: the edge of the world
    is crossed deliberately, through a location's exit.
    """
    x, y = int(math.floor(gx)), int(math.floor(gy))
    return MAP_X[0] <= x <= MAP_X[1] and MAP_Y[0] <= y <= MAP_Y[1]


def water(gx, gy):
    """Whether the map's picture shows water on a cell.

    Outside the rows the photograph was read over there is no answer, and no
    answer means dry: what lies east and south of that rectangle is more of
    the same desert (recon/analysis/borders.md §8).
    """
    (gx0, gy0, gx1, gy1), rows = terrain()
    x, y = int(math.floor(gx)), int(math.floor(gy))
    if not rows or not (gx0 <= x <= gx1 and gy0 <= y <= gy1):
        return False
    return rows[y - gy0][x - gx0] in BLOCKED


def passable(gx, gy):
    """Whether a walker can stand on a map cell.

    Three things say no: the edge of the world, the lake, and the mountains
    the map draws. The mountains are read off the picture, so they yield to
    anything written down -- a cell some location declares as its own exit is
    open however dark the pixels are (terrain_repairs), and a cell a player
    has stood on is open because they say so (terrain_overrides).

    Order matters: a player's word beats the repairs, the repairs beat the
    photograph, and none of them reaches outside the world's rectangle.

    Floor, not round, like location_at: the cell under a position is the one
    the client draws the figure on.
    """
    x, y = int(math.floor(gx)), int(math.floor(gy))
    if not in_map(x, y):
        return False
    fixed = terrain_overrides().get((x, y))
    if fixed is not None:
        return fixed
    if (x, y) in terrain_repairs():
        return True
    return not water(x, y)


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


_CAMP_FILL = None


def camp_fill(loc_id):
    """Who stands in a location's empty spawn slots, in the file's order:
    the types of data/camp_fill.json, or () for a file it does not list.

    DESIGNED, not recovered. A spawn of type 0 names nobody -- the dead
    server chose who stood there -- and Вади-Хальфа's camps are made of
    them: Bandit_Camp1..4 held their chief and their ammunition boxes and
    nothing else that fights. data/build_spawn_substitutes.py (CAMP_FILL)
    gives each slot of those files, and of a few quest places beside them, a
    fighter of the camp's faction and level band, and says why. rooms.Room
    asks here only in war=1 locations; any other file's empty slot stays
    empty, as it always was.
    """
    global _CAMP_FILL
    if _CAMP_FILL is None:
        _CAMP_FILL = {}
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            with open(os.path.join(here, "data", "camp_fill.json"),
                      encoding="utf-8") as fh:
                for k, v in json.load(fh)["fill"].items():
                    _CAMP_FILL[int(k)] = tuple(int(t) for t in v["types"])
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return _CAMP_FILL.get(loc_id, ())


# Spawn entries that belong to a season, a clan or the developers rather than
# to the place. The location files still carry the New Year lottery stall,
# the Victory Day trader and clan-event vendors, and wasteland templates were
# reused for clan events, which is why a clan's trader stands in open desert.
# Recognised by the tokens of the internal name, split on _ and digits.
EVENT_TOKENS = {"vov", "vbg", "lemon", "ny", "9may", "presents", "lotery",
                "lottery", "hw", "xmas", "valentine", "valentines", "admin",
                "test", "event", "prazdnik"}

# Вади-Хальфа's own people whom a token of their name took for a season's,
# kept where they stand -- the owner's default (2026-09-28): the lottery
# sellers wh_lotery (662, both markets) and wh_lotery_g (711, the black
# market) of the town's lotteries (texts.xml 50446-50451), the Добрый беженец
# (1977) and the two children wh_ny_Kid1/3 (423, 425, «Ребенок», 59671). By
# location: the same types in other cities' files (431 in Донгола's market
# and warehouse) stay out, and so do Савин's presents (636) and the
# developers' stand-ins (7234-7236) beside them.
#
# Ольсен ny_trader (431, «Ольсен<Br>Амулеты и сувениры», 62122; the old
# market's tooltip promises «Торговец сувенирами») is in the default too, but
# waits for his goods: with no row of his own in data/npcs.json his stall is
# the wiki's low-confidence one of Донгола's «Генрих» -- Анестетик and Салюс
# МК V-VII at 33 600-50 400 afro, two of them sold nowhere else. Once a
# 'stock' row of his is written, add 431 back to rows 35 and 104.
SEASON_KEPT = {
    35: frozenset({662}),           # Вади Хальфа: рынок
    104: frozenset({662}),          # Портовый рынок
    102: frozenset({711}),          # Черный рынок
    36: frozenset({1977, 423}),     # жилой квартал
    41: frozenset({425}),           # Причал
}

# The objects that do stand, by location: the things of Вади-Хальфа's quests,
# camps and schools that are there to be broken -- the owner's default
# (2026-09-28). Henry Jr.'s chest m05_Box (41) in «Генри Мл.» (43); the box
# of «Перехват» (50 in 46); the «ящик спирта» of Люшер's sectarians (102 in
# 64); each camp's ammunition boxes nc/lu/ja/mg_box_ammo (409, 641, 642,
# 2162 in 80, 81, 84, 85); the targets nz_Target1..6 (1397-1402) of Берт
# Гаммер's range TIR_01..06; and the stones Stone_WH (977) of the quarry's
# four pits. Such a thing stands where its file puts it and never moves or
# strikes (mobs.MobStats: role "object"); it takes damage, dies, rolls its
# loot, respawns, and its kill counts for a quest like anybody's. Everywhere
# else -- the Nubian valley, the other cities, the old copies of the range
# (670, 1037 ...) and the quarry's control panel (2022) -- objects stay out.
STANDING_OBJECTS = {
    43: frozenset({41}),
    46: frozenset({50}),
    64: frozenset({102}),
    80: frozenset({409}),
    81: frozenset({641}),
    84: frozenset({642}),
    85: frozenset({2162}),
    1048: frozenset({1397, 1398}),  # TIR_01
    1233: frozenset({1398}),        # TIR_02
    1260: frozenset({1398, 1399}),  # TIR_03
    1276: frozenset({1400}),        # TIR_04
    1280: frozenset({1401}),        # TIR_05
    1282: frozenset({1402}),        # TIR_06
    626: frozenset({977}),          # WH_Stone_Mine_C
    628: frozenset({977}),          # WH_Stone_Mine_S
    629: frozenset({977}),          # WH_Stone_Mine_W2
    630: frozenset({977}),          # WH_Stone_Mine_E2
}

# The ranges where a shot goes over the booth's counter. In TIR_01..06 the
# player stands in a booth closed off by a two-hex barrier and the targets
# stand beyond it: every one of them out of a fist's reach and behind that
# barrier from every cell he can walk to. The barrier's cells carry the
# obstacle code 1 where the walls carry f (the fifth character, which the
# client drops: it only walks), so the range reads code 1 as a counter --
# not to be stepped over, to be shot over (Location.shoot_over,
# combat.RoomCombat.burst). Anywhere else every obstacle stops a bullet.
SHOOT_OVER = frozenset({1048, 1233, 1260, 1276, 1280, 1282})

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


# Creatures taken out of the game on purpose: data/retired.json 'creatures',
# type id -> why. The owner's cut of (P) (2026-09-30, «удали всё, что связано
# с (P), в том числе и локации») put every premium creature the location
# files spawn there -- the _pm masters of the three premium masters' camps
# and of the camp 94, the fifteen «Подмастерье …[P]» of the craftsmen's
# quarters, the premium bar's people (the bouncer in Донгола's quarter 79,
# the customs officer in its port 445) and the premium quest places' mobs --
# and a room never stands one, wherever a file or a hand-kept row puts it:
# belongs_here refuses it before anything else, rooms.Room leaves it out of
# data/placements.json's rows, rooms.check_placements and events.check turn
# away a row naming it. By type and everywhere, rather than place by place
# (the schedule's held_out): a premium master is premium in any file. The
# type's name stays in the string table all the same -- names are never
# taken away, since an unknown id sends the client to the login screen.
_RETIRED_CREATURES = None


def retired_creatures():
    """type id -> why, of data/retired.json 'creatures', read once. No file is
    nobody retired: the world stands as its files say."""
    global _RETIRED_CREATURES
    if _RETIRED_CREATURES is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = {}
        try:
            with open(os.path.join(here, "data", "retired.json"), encoding="utf-8") as fh:
                for k, why in (json.load(fh).get("creatures") or {}).items():
                    if not str(k).startswith("_"):
                        out[int(k)] = str(why)
        except OSError:
            pass
        _RETIRED_CREATURES = out
    return _RETIRED_CREATURES


def retired_creature(type_id):
    """Whether this creature type is out of the game (retired_creatures)."""
    return int(type_id) in retired_creatures()


def belongs_here(type_id, name, root, war, loc_id=None):
    """Whether a spawn from the location file should stand in the room.

    Never a creature out of the game (retired_creatures), wherever the file
    has it. Then three kinds are left out. Seasonal, clan and developer
    entries, by the tokens of their name, but for the town's own people
    SEASON_KEPT keeps in loc_id. Loot containers and other "objects", which
    the client draws as creatures with a health bar, but for the ones
    STANDING_OBJECTS lets stand in loc_id to be broken. And hostile
    creatures (root 0) in a peaceful location: a market with war=0 had them
    in its file for events and quests, and a player cannot fight there
    anyway. And, before those three, whoever a timed window of
    data/schedule.json stands in and sends away itself, or keeps out for
    good (events.owns): not the room's.
    """
    if retired_creature(type_id):
        return False
    import events                   # late: it imports this module
    if events.owns(loc_id, type_id):
        return False
    if _name_tokens(name) & EVENT_TOKENS \
            and type_id not in SEASON_KEPT.get(loc_id, ()):
        return False
    if creature_role(type_id) == "object" \
            and type_id not in STANDING_OBJECTS.get(loc_id, ()):
        import production        # the mines' ore rocks (production.ORE_ROCKS)
        if not production.stands(type_id, loc_id):
            return False
    if root == MOB and not war:
        return False
    return True


# Inhabitants put down by hand, beside the ones a location's own file spawns:
# the tools box of the Nubian valley's «Забрать инструменты», which mobs.xml
# has (nz_Box, 1135) and no file puts down. data/placements.json keeps them
# with the evidence for each; rooms.Room stands them after the file's own,
# and rooms.check_placements is what the server asks of the table before its
# first socket.
_PLACEMENTS = None


def placements_path():
    """data/placements.json, or the file LAVA_PLACEMENTS names. The variable
    is for a suite that needs an inhabitant the world does not have -- a
    creature to fight in a room it tests -- and, like LAVA_PASSAGES, it
    replaces the table rather than adding to it."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return (os.environ.get("LAVA_PLACEMENTS")
            or os.path.join(here, "data", "placements.json"))


def placements():
    """location id -> [row] of the table, read once: {type, cell: [x, y],
    home, why}. No file is no placements, and the world stands as its files
    say; a file that does not parse raises, and the server does not start
    on it (rooms.check_placements)."""
    global _PLACEMENTS
    if _PLACEMENTS is None:
        path = placements_path()
        table = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
            for k, rows in (doc.get("locations") or {}).items():
                table[int(k)] = list(rows or ())
        _PLACEMENTS = table
    return _PLACEMENTS


def placed_in(loc_id):
    """The rows put down by hand in one location, in table order."""
    return placements().get(int(loc_id), [])


def offers_home(type_id):
    """Whether a Commoner (or a healer) of this type registers a home
    («Прописка»), as every one does -- home is the location, not the person
    -- unless the type is a thing (data/npcs.json 'no_home': a bomb box, a
    rock, a fountain, a hole) or a placement of the type says home: false. A
    box is a thing: talked to, it gives its quest and nothing else. Per
    type, since the frame is."""
    import npcs                      # no imports of its own
    if npcs.no_home(int(type_id)):
        return False
    return not any(int(r.get("type", 0)) == int(type_id) and r.get("home") is False
                   for rows in placements().values() for r in rows)


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
