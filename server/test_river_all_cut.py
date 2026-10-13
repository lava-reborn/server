"""The owner's cut of everything across the river, 2026-10-13: «все локации за
рекой не нужны».

Every town on the Nile stands on one bank, inside the great bend: Вади-Хальфа
on the east shore of the lake, Абри, Керма and Донгола on the east bank,
Мероэ on the inner bank of the southern loop, Абу-Хамед on the north bank at
the turn. The far bank -- the west and the south, and the islands in the
stream -- held, after the cut of the camps across the river (2026-10-12):
the digs 433-436 with the tombs under them, the ФСЦ's bases НИЛ-2..4, the
gorges of Доктор «Д» with his bunkers, two evacuation zones, the clan
Эван's farm opposite Абри (and two of his files the placer stood in the
north-west corner beyond the lake), the clan base Le_Mon on the island by
Донгола, and the names, squares and letters the map's picture paints over
all of them. All of it goes, with the files without a cell that belong
there: Доктор «Д»'s other laboratories, the pieces of his pass and of the
gorges, the resistance camps' quest wasteland («боевые действия на западном
берегу Нила»), the event «9 мая» (the villages and staffs of the war zones
across the river), the warehouse under «Ангар в джунглях». The river and
the towns' banks stay. Each part held here (the pattern of server/
test_river_camps_cut.py):

  1. the places: the eighteen files that stood on the far bank's nineteen
     cells and the ninety-seven behind them are out of the game (data/
     retired.json), on no cell (data/settlements_verified.json nulls the
     nineteen, and holds 6174,1982 under «Ангар в джунглях» wasteland),
     every cell leads into the wasteland, the files stay; no place stands
     on a far bank any more, every place on the towns' banks stays where it
     was; the gate of the older gorges 272 and its 504, named «Перевал
     Смерти» as the towns' bank's name (5982,1866), and the jungle 727 stay,
     on no cell;
  2. no way in: no door, passage, side or quest way, no quest's ride,
     marker, waiting place or reward place leads there; the owner's wall is
     closed along Донгола's bank (data/terrain_verified.json), so no walk
     from any town reaches a far bank's cell, where from Донгола's port it
     reached the dig 435 in twenty steps; the towns' banks are walked as
     before;
  3. the people: who stood there stood there alone but for those named,
     gives or takes no quest no other giver keeps, is no boss but those
     named (who stood there alone), sells nothing, and keeps his name; no
     live quest asks to kill one of those who stood there alone;
  4. the map's names: every name over a far bank and its islands hidden
     (66), the towns' banks' names as they were;
  5. the map's squares and letters: 23 squares, the letters «Поселок»
     thrice and the island's two lines go (server/map_cells.py), the
     picture's grey crosses (on the towns' bank and in the lake as well)
     stay, the names with nothing painted are 'bare'; on the real map, when
     the original's tiles are here, no square of the palette is left on a
     far bank, every other square in the tiles that change is where it
     was, and the island's west channel runs on through where its letters
     were;
  6. the encounters: the map of the camps' wasteland is what it was, cell
     for cell (the cut's cells are the towns' ground still,
     world.retired_cells);
  7. the database: whoever is in a cut place, or calls one home, goes to
     Абри's port market (from Абри's far bank and Эван's places) or to
     Причал (from the others) -- once, by the run_once
     «retire-river-all-2026-10-13»; the journals stay. On Postgres:
     server/test_storage_pg.py.

    LAVA_RES=.../res python3 server/test_river_all_cut.py
"""
import collections
import glob
import hashlib
import html
import io
import json
import logging
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "river_all_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import bosses  # noqa: E402
import encounters  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import map_cells  # noqa: E402
import map_labels  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


def load(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


RETIRED = load("retired.json")
VERIFIED = load("settlements_verified.json")
LABELS = load("map_labels.json")["labels"]
PASSAGES = load("passages.json")
SCHEDULE = load("schedule.json")
LOOT = load("loot_manual.json")
HOLDINGS = load("holdings.json")
TERRAIN = load("terrain_verified.json")
ALL_RETIRED = {int(k) for k in RETIRED["places"]}
CUT_WHY = "The owner's cut of everything across the river, 2026-10-13"
ORDER = "все локации за рекой не нужны"

# The places on the far banks' cells, cell by cell.
ON_CELLS = {
    (5943, 1722): 433, (5941, 1697): 508,                                   # Вади-Хальфа
    (5850, 1850): 434, (5849, 1851): 523, (5844, 1826): 513, (5844, 1831): 502,     # Абри
    (5867, 1827): 321, (5868, 1828): 325, (5868, 1829): 325, (5869, 1828): 324,     # Эван
    (5840, 1600): 322, (5840, 1601): 323,                                   # the north-west corner
    (5864, 2001): 435, (5863, 2002): 524, (5851, 1986): 516, (5851, 1991): 988,     # Донгола
    (6168, 1988): 436, (6167, 1989): 525, (6145, 1993): 517,                # Абу-Хамед
}
# And the files behind them, which never had a cell.
OFF_CELL = {963: 433, 1198: 433, 964: 434, 1199: 434, 965: 435, 1200: 435, 966: 436, 1197: 436,  # the tombs
            1003: 508, 1209: 508, 1004: 513, 1210: 513, 1005: 516, 1211: 516, 1006: 517, 1212: 517,  # Доктор «Д»
            934: 324, 962: 324,                                             # Эван's works
            474: None, 475: None, 476: None, 979: None, 980: None, 981: None, 985: None, 1206: None}  # Le_Mon
# The files without a cell that belong there all the same: Доктор «Д»'s
# other laboratories, the pieces of his pass, the ambush copy of the gorges'
# gate and the older gorges' pieces (the map's only «Ущелье Смерти» are the
# far banks' columns), the quest wasteland of the war on the west bank, the
# event «9 мая» (its staffs and villages are the war zones' across the
# river), the warehouse under «Ангар в джунглях».
DOCD_LABS = {986: 508, 987: 513, 989: 516, 990: 517}
GORGES = [268, 269, 270, 271, 273, 503, 505, 506, 514, 515, 507, 509, 510, 511, 512, 595]
WASTELAND = [441, 442, 443, 444]
MAY9 = list(range(539, 575)) + [924, 925] + list(range(994, 1002))
OFF_CELL.update(DOCD_LABS)
OFF_CELL.update({i: None for i in GORGES + WASTELAND + MAY9 + [288]})
CUT = sorted(set(ON_CELLS.values()) | set(OFF_CELL))
# Абри's own of them (to Абри's port market).
ABRI_CUT = sorted([434, 523, 513, 502, 964, 1199, 1004, 1210, 987, 321, 324, 325, 934, 962, 442]
                  + [i for i in MAY9 if world.location(i).fn.endswith("_Ab")])
CELLS = sorted(ON_CELLS)
# The far banks, box by box (gx0, gx1, gy0, gy1): the owner's wall shuts each in.
FAR = {"Вади-Хальфа": (5914, 5953, 1687, 1728), "the north-west corner": (5833, 5841, 1600, 1607),
       "Абри": (5835, 5856, 1825, 1856), "Эван": (5867, 5869, 1827, 1829), "Керма": (5854, 5866, 1927, 1933),
       "Донгола": (5833, 5868, 1978, 2020), "the island ПэЖэ": (5869, 5872, 2000, 2008),
       "Абу-Хамед": (6130, 6187, 1981, 2016)}


def far(c):
    return any(x0 <= c[0] <= x1 and y0 <= c[1] <= y1 for x0, x1, y0, y1 in FAR.values())


# The 66 names hidden: Доктор «Д»'s four columns of eight, the staffs, the
# stages, the digs, the bases, «Ангар в джунглях», Эван's six, the north-west
# corner's eight, the island «Эдем»'s four.
COLUMNS = [(5941, 1696), (5844, 1825), (5851, 1985), (6145, 1992)]
HIDDEN = ({(x, y + k) for x, y in COLUMNS for k in range(8)}
          | {(5935, 1711), (5944, 1712), (5943, 1722), (5840, 1839), (5850, 1850), (5849, 1851), (5850, 1999),
             (5850, 2008), (5864, 2001), (5863, 2002), (6153, 1994), (6158, 2000), (6149, 2009), (6168, 1988),
             (6167, 1989), (6174, 1982)}
          | {(5867, 1827), (5868, 1827), (5868, 1828), (5869, 1828), (5868, 1829), (5869, 1829)}
          | {(5840, 1600), (5840, 1601), (5841, 1601), (5838, 1603), (5836, 1605), (5833, 1607), (5834, 1607),
             (5840, 1607)}
          | {(5858, 1929), (5857, 1928), (5857, 1930), (5859, 1930)})
# Five of them had an edit of the owner's map labels of 2026-10-11 (the
# staffs' «Сражение за чертежи», the dig 433's tomb raider): a hide now.
RETEXTED = [(5935, 1711), (5850, 1999), (6158, 2000), (5840, 1839), (5943, 1722)]
# The squares the picture paints on the far banks: on the retired places'
# cells, and the others data/map_cells.json lists; the five the cut of the
# camps across the river took already.
SQ_PLACES = [(5943, 1722), (5850, 1850), (5849, 1851), (5864, 2001), (5863, 2002), (6168, 1988), (6167, 1989)]
SQ_NAMES = [(5941, 1703), (5935, 1711), (5944, 1712), (5844, 1832), (5849, 1830), (5840, 1839), (5851, 1992),
            (5850, 1999), (5850, 2008), (5871, 2003), (5871, 2004), (6145, 1999), (6153, 1994), (6158, 2000),
            (6149, 2009), (6174, 1982)]
SQ_CAMPS = [(5942, 1723), (5943, 1723), (5864, 2002), (6168, 1989), (5850, 1851)]
CAPTIONS = {"Поселок": [13753, 14774, 16054], "Частный остров / Господина ПэЖэ": [16055]}
# The picture's small grey crosses with a white middle on the far banks (by
# Вади-Хальфа and Абу-Хамед): the same mark stands on the towns' bank and in
# the lake, so it is the picture's own and stays.
CROSSES = [(5942, 1709), (6147, 1985), (5851, 1721), (5925, 1654), (5933, 1605)]
# The island's caption by Донгола, its two lines' box, and the columns of
# its left end where the island's west channel ran under the letters.
ISLAND = (46961, 16002, 47034, 16020)
CHANNEL = range(46962, 46969)
WALL_DN = [(5869, 1999), (5869, 2000)] + [(5871, y) for y in range(2007, 2015)]
PRICHAL, PRICHAL_CELL = 41, (5965, 1728)
PORT_AB, PORT_AB_CELL = 187, (5860, 1835)
PIER_DN, PIER_DN_CELL = 445, (5873, 2012)
# The towns' banks: the places that stay, their neighbours across the water
# among them (the research of 2026-10-13, FIND.md).
BANKS = {
    "Вади-Хальфа": {(5970, 1724): 80, (5971, 1723): 82, (5978, 1727): 81, (5979, 1728): 83,
                    (5974, 1739): 84, (5975, 1738): 86, (5993, 1721): 85, (5992, 1720): 87,
                    (5976, 1720): 137, (5971, 1731): 108, (5972, 1735): 139, (5966, 1728): 52,
                    (5968, 1728): 94, (5969, 1728): 95, PRICHAL_CELL: PRICHAL, (5957, 1733): 44,
                    (5968, 1719): 447},
    "Абри": {(5880, 1844): 88, (5881, 1843): 89, (5868, 1854): 92, (5869, 1855): 90,
             (5885, 1836): 220, PORT_AB_CELL: PORT_AB, (5861, 1835): 188, (5862, 1835): 255,
             (5860, 1838): 191, (5861, 1844): 285, (5862, 1846): 189},
    "Керма": {(5861, 1946): 298},
    "Донгола": {(5882, 2036): 93, (5883, 2035): 93, (5920, 2010): 98, (5921, 2011): 98,
                (5878, 2011): 73, (5876, 2011): 96, (5877, 2012): 97, PIER_DN_CELL: PIER_DN,
                (5873, 2009): 105, (5878, 2013): 469},
    "Абу-Хамед": {(6274, 1952): 168, (6273, 1953): 263, (6183, 1977): 131, (6183, 1975): 127,
                  (6182, 1977): 446, (6183, 1974): 467, (6182, 1976): 126, (6126, 1980): 194,
                  (6154, 1963): 118},
}
# Left out of the cut, and on no cell as before: the older gorges' gate 272
# «Перевал Смерти.» and its 504 «Перевал смерти» (their name stands on the
# towns' bank, 5982,1866), the eternal flame 304 «Вечный огонь» of «9 мая»
# (9may_9_new, war 0: a memorial, no room of the war on the west bank; the
# monument «Памятник Воину-Освободителю» stands on Донгола's bank), the
# jungle 727 «Джунгли» (one of the jungles of the clans, the placer's other
# candidate for «Ангар в джунглях»).
LEFT = [272, 304, 504, 727]
HANGAR = (6174, 1982)
MT = world.mob_types()


def standing(loc_id):
    return {t for _cell, t in world.location(loc_id).spawns}


def stood_in(loc_id):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    return sorted({n.type_id for n in room.npcs.values()})


def place_ids(v):
    """A quest row's place field (one id, or a list of them) as a list."""
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v if str(x).lstrip("-").isdigit()]
    return [int(v)] if str(v).lstrip("-").isdigit() else []


def walk(starts, open_=lambda c: world.passable(*c)):
    """Every cell reached on foot from the starts."""
    seen = set(starts)
    todo = collections.deque(starts)
    while todo:
        x, y = todo.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and world.in_map(*n) and open_(n):
                seen.add(n)
                todo.append(n)
    return seen


files = sorted(int(os.path.basename(p)[:-4])
               for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")))


# --- 1. the places -------------------------------------------------------------------------
print("the places")
try:
    cut = {int(k): v for k, v in RETIRED["places"].items() if v.startswith(CUT_WHY)}
    check("data/retired.json takes out the hundred and fifteen files, each with its why quoting the order",
          (len(cut), sorted(cut), all(ORDER in v for v in cut.values())), (115, CUT, True))
    fams = ("Archeologic", "FVAviaBazaNil", "FV_Bunker", "FV_MainGate", "FV_exit", "fevral23_exit", "DocD_",
            "DethPass", "Evan", "KB_EVAN", "KB_Le_Mon", "Invaiders_qwest", "9may", "stok_AH_sever")
    check("  ..the digs, the ФСЦ's bases, Доктор «Д»'s gorges, bunkers, laboratories and pass, the older gorges'"
          " pieces, the evacuation zones, the tombs, the clan Эван's files, the clan base Le_Mon's, the quest"
          " wasteland, «9 мая» and the warehouse under «Ангар в джунглях», every one of each family",
          {fam: sorted(lid for lid in files if world.location(lid).fn.startswith(fam) and lid not in (429, 430, 431,
                                                                                                         432, 522))
           for fam in fams},
          {"Archeologic": [433, 434, 435, 436, 963, 964, 965, 966, 1197, 1198, 1199, 1200],
           "FVAviaBazaNil": [523, 524, 525], "FV_Bunker": [1003, 1004, 1005, 1006, 1209, 1210, 1211, 1212],
           "FV_MainGate": [508, 513, 516, 517, 595], "FV_exit": [502], "fevral23_exit": [988],
           "DocD_": [507, 509, 510, 511, 512, 986, 987, 989, 990],
           "DethPass": [268, 269, 270, 271, 272, 273, 503, 504, 505, 506, 514, 515],
           "Evan": [321, 322, 323, 324, 325, 934], "KB_EVAN": [962],
           "KB_Le_Mon": [474, 475, 979, 980, 981, 985, 1206], "Invaiders_qwest": WASTELAND, "9may": [304] + MAY9,
           "stok_AH_sever": [288]})
    check("  ..and every one of them is out, but the older gorges' gate 272 and its 504, «Перевал Смерти» as the"
          " towns' bank's name, and «9 мая»'s eternal flame 304, a memorial (war 0)",
          sorted(lid for fam in fams for lid in files if world.location(lid).fn.startswith(fam)
                 and lid not in (429, 430, 431, 432, 522) and lid not in ALL_RETIRED), [272, 304, 504])
    check("  ..and every one of them is out", [lid for lid in CUT if lid not in ALL_RETIRED], [])
    check("  ..and lists the nineteen cells they stood on, the towns' ground still for the encounters",
          {c: i for c, i in world.retired_cells().items() if i in CUT}, ON_CELLS)
    table = world.settlements()
    check("none of them on any cell", [c for c, i in table.items() if i in CUT], [])
    check("  ..their nineteen cells nulled with their why in data/settlements_verified.json",
          {c: (VERIFIED["cells"].get("%d,%d" % c, "absent"), ORDER in VERIFIED["why"].get("%d,%d" % c, ""))
           for c in CELLS}, {c: (None, True) for c in CELLS})
    check("every cell of theirs leads into the wasteland, but 322's on the world's north rim, a rock of the ring now",
          [c for c in CELLS if world.location_at(*c) != world.pack(*c)], [(5840, 1600)])
    check("  ..the files stay, so a character saved inside still loads",
          [lid for lid in CUT if not world.location(lid).fn], [])
    check("no place stands on a far bank or an island any more", sorted(c for c in table if far(c)), [])
    check("the towns' banks keep every place, the neighbours across the water among them",
          {town: {c: table.get(c) for c in cells} for town, cells in BANKS.items()}, BANKS)
    check("  ..none of them on a far bank", [c for cells in BANKS.values() for c in cells if far(c)], [])
    check("the placer's rivals the cut leaves alone are on no cell, as before, and not retired: the older gorges'"
          " gate 272 and its 504, the jungle 727",
          ([world.cell_of(i) for i in LEFT], [i for i in LEFT if i in ALL_RETIRED]), ([None] * len(LEFT), []))
    check("  ..and the cell under «Ангар в джунглях», which 727 would take with 288 out of the running, is held"
          " wasteland in data/settlements_verified.json, with its why",
          (table.get(HANGAR), VERIFIED["cells"].get("%d,%d" % HANGAR, "absent"),
           ORDER in VERIFIED["why"].get("%d,%d" % HANGAR, ""), world.location_at(*HANGAR) == world.pack(*HANGAR)),
          (None, None, True, True))
    check("the north-west corner's rim cell (5840,1600, 322's) is a rock of the ring now",
          (world.location(world.location_at(5840, 1600)).title, (5840, 1600) in world.borders()), ("Скалы", True))
except Exception:
    import traceback
    fails.append("the places broke:\n" + traceback.format_exc())


# --- 2. no way in --------------------------------------------------------------------------
print("no way in")
try:
    followed = []
    for lid in files:
        for side in "ab":
            rec = travel.door(lid, side)
            if (rec and int(rec.get("target_loc_id") or 0) in CUT
                    and rec.get("confidence") in travel.DOOR_CONFIDENCE and lid not in ALL_RETIRED):
                followed.append((lid, side, int(rec["target_loc_id"])))
    check("no door the server follows leads into a cut place from a place still in the game", followed, [])
    into = []
    for section in ("doors", "sides", "quest", "walk_in"):
        for key, recs in (PASSAGES.get(section) or {}).items():
            if key.startswith("_"):
                continue
            if isinstance(recs, dict):
                recs = list(recs.values())
            for rec in recs or ():
                if isinstance(rec, dict) and (int(rec.get("target_loc_id") or 0) in CUT
                                              or key in {str(i) for i in CUT}):
                    into.append((section, key))
    check("no passage, side or quest way of data/passages.json leads into or out of one, none is a no_map place",
          (into, sorted({str(i) for i in CUT} & set(PASSAGES.get("no_map") or {}))), ([], []))
    GEO = {world.pack(*c) for c in CELLS} | {world.pack(*c) for c in HIDDEN}
    rows = quests.table_rows()
    named = sorted({int(r["type"]) for r in rows for key in ("loc", "finish_loc", "rew_loc")
                    if set(place_ids(r.get(key))) & GEO}
                   | {int(r["type"]) for r in rows for key in ("loc_id", "stay_in")
                      if set(place_ids(r.get(key))) & set(CUT)}
                   | {int(r["type"]) for r in rows if isinstance(r.get("way"), dict)
                      and int(r["way"].get("target_loc_id") or 0) in CUT})
    check("no quest row rides anybody there, sends him there, marks a cell of a far bank, waits or pays there",
          named, [])
    check("  ..nor does any quest as the server reads it",
          sorted(t for t, q in quests.QUESTS.items()
                 if {q.loc, q.finish_loc, q.rew_loc} & GEO or set(q.stay_in) & set(CUT)), [])
    check("  ..and none of them has a quest way out", [i for i in CUT if travel.quest_ways(world.location(i))], [])
    blocked = set(TERRAIN["blocked"])
    check("the owner's wall is closed along Донгола's bank: ten cells, open ground before (no water there)",
          ([c for c in WALL_DN if "%d,%d" % c not in blocked], [world.passable(*c) for c in WALL_DN],
           [c in world.terrain_repairs() or not world.water(*c) for c in WALL_DN]),
          ([], [False] * 10, [True] * 10))
    starts = [PRICHAL_CELL, PORT_AB_CELL, PIER_DN_CELL, (6182, 1977), (5861, 1946)]
    walked = walk(starts)
    check("no walk from Причал, Абри's port, Донгола's port, Абу-Хамед's port or Керма's «Берег Дракона» reaches"
          " a cut place's cell, a hidden name's or a square's of the far banks",
          sorted(c for c in set(CELLS) | HIDDEN | set(SQ_NAMES) if c in walked), [])
    check("  ..while every place of the towns' banks is walked to as before (the quarter 447, the station 126"
          " and the masters' camp 131 aside: they stand on the owner's wall itself)",
          sorted(c for cells in BANKS.values() for c in cells
                 if c not in walked and c not in ((5968, 1719), (6182, 1976), (6183, 1977))), [])
    open_before = walk([PIER_DN_CELL], lambda c: c in WALL_DN or world.passable(*c))
    check("  ..where without the ten cells Донгола's port walked to the dig 435, the base 524, the gorge 516, the"
          " evacuation zone 988 and the staff",
          [c in open_before for c in ((5864, 2001), (5863, 2002), (5851, 1986), (5851, 1991), (5850, 1999))],
          [True] * 5)
    check("  ..and Донгола's port still reaches «Побережье» 105, the walk west of it and the town",
          [c in walked for c in ((5873, 2009), (5872, 2008), (5872, 2013), (5876, 2011), (5878, 2011))],
          [True] * 5)
except Exception:
    import traceback
    fails.append("the ways broke:\n" + traceback.format_exc())


# --- 3. the people -------------------------------------------------------------------------
print("the people")
try:
    put = {}                                          # type -> where it could be put down
    for lid in files:
        try:
            loc = world.location(lid)
        except (KeyError, OSError, AttributeError, ValueError):
            continue
        for _cell, t in loc.spawns:
            put.setdefault(t, set()).add(("file", lid))
        for t in world.camp_fill(lid):
            put.setdefault(t, set()).add(("fill", lid))
    for lid, recs in world.placements().items():
        for rec in recs:
            put.setdefault(int(rec["type"]), set()).add(("placed", int(lid)))
    for rec in events.table().spawns:
        for t in events._types(rec.get("types")):
            put.setdefault(t, set()).add(("window", rec.get("loc")))
    people = {t for lid in CUT for t in stood_in(lid)}
    check("the cut places stood 111 kinds of people and creatures: the four archaeologists, the tombs' mobs, Эван's"
          " clan, the cows, Le_Mon's fighters, Доктор «Д»'s laboratories' mobs, the quest wasteland's mini-bosses,"
          " «9 мая»'s bosses and staff, the warehouse's master, man and flag", len(people), 111)
    unstood = sorted({(t, i) for i in CUT for t in standing(i) if t and t not in people
                      and (t in MT or world.substitute(t) is not None) and world.substitute(t) not in people})
    check("  ..their other spawn types have no row in mobs.xml and no stand-in, or are the 45 entries of the clan"
          " base Le_Mon's people and of the developers (LeMon_*, ADMIN_*, *_TEST_CLAN, the zeon landlord) and the"
          " 63 of «9 мая»'s people of the war (VOV_*: its traders, quest people and lessor, who give no quest of the"
          " table) that the room leaves out by their names (world.belongs_here), so nothing else ever stood there",
          (len({t for t, _i in unstood}), sorted({i for _t, i in unstood}),
           [(t, i) for t, i in unstood if t not in MT
            or world.belongs_here(t, MT[t][1], world.entity_root(t, MT[t][0]), world.location(i).war, i)]),
          (108, sorted([474, 475, 476, 979, 980, 981, 985, 1206, 545, 546, 553, 554, 561, 562, 569, 570, 571, 572,
                        573, 574, 925] + list(range(994, 1002))), []))
    ELSEWHERE = {114: [44], 257: [1007], 436: [1007], 437: [1007], 438: [1007],
                 2172: [609, 656, 706, 735, 926, 928, 932, 1044], 2393: [766], 2394: [766], 2395: [766],
                 2396: [766], 2403: [766], 4017: [1010, 1186, 1187, 1191, 1192, 1193, 1194, 1195],
                 4581: [929, 930, 933, 959], 5308: [380, 381, 388], 4427: [118]}
    rooms_of = {}

    def stands(t, where):
        """Whether t stands there: a file's spawn only when its room puts it
        down (the cash machine 2402 is held out of 766 and 1055)."""
        kind, lid = where
        if kind != "file":
            return True
        if lid not in rooms_of:
            rooms_of[lid] = set(stood_in(lid))
        return t in rooms_of[lid]
    elsewhere = {t: sorted({w[1] for w in put.get(t, ()) if w[1] not in ALL_RETIRED and stands(t, w)})
                 for t in people}
    check("every one of them stood in the cut places alone, but the cows (Вади-Хальфа's pasture 44), the tombs' waves"
          " (Донгола's dungeon 1007), the band leader, Абри's ore refinery's people (its cash machine 2402 held out"
          " of it), the bankers, the clan upgrader, Delta Force and the warehouse's clan flag (the base 118)",
          {t: w[:8] for t, w in elsewhere.items() if w}, ELSEWHERE)
    alone = sorted(t for t in people if not elsewhere[t])
    givers = {t for t in people if quests.given_by(t) or quests.taken_by(t)}
    check("of those who give or take a quest every one stands in Абри's ore refinery 766 too, with his quests"
          " 532-538", (sorted(givers), sorted(givers - {t for t in people if 766 in elsewhere[t]})),
          ([2393, 2394, 2395, 2396], []))
    check("  ..the healer 4612 of Эван's village alone registered a home there (the run_once moves such homes)",
          sorted(t for t in people if world.offers_home(t)), [4612])
    clock = sorted(t for t in people if bosses.keeps_hours(t))
    check("  ..the bosses of the clock among them -- the quest wasteland's four mini-bosses, «9 мая»'s twenty-four"
          " (fash_boss_*), the warehouse's master 7455 -- stood there alone; nobody of them has loot of the owner's"
          " or keeps a site of the clans",
          (clock, [t for t in clock if elsewhere[t]],
           sorted(t for t in people if str(t) in (LOOT.get("by_type") or {})),
           sorted(k for k, v in HOLDINGS["sites"].items() if v.get("loc") in CUT or v.get("boss") in people)),
          ([5725, 5726, 5727, 5728] + [b + k for b in (6897, 6907, 6917, 6927) for k in range(6)] + [7455], [],
           [], []))
    hunted = sorted({t for q in quests.QUESTS.values()
                     for t in list(q.mobs_kill) + list(q.kill_also.values()) + [m for _o, _n, ms in q.objs for m in ms]
                     if t in alone})
    check("  ..and no quest asks to kill one of those who stood there alone, or to take a thing off him", hunted, [])
    scheduled = ({r.get("loc") for key in ("spawns", "held_out") for r in SCHEDULE.get(key, [])}
                 | {lid for key in ("loot", "keep_in") for r in SCHEDULE.get(key, [])
                    for lid in r.get("locs", [])})
    check("  ..and data/schedule.json names no cut place: no window stands anybody there or holds anybody out"
          " (feb23's why names 988, may9's the copy 9may_*_WH, and neither stands anybody there)",
          (len(scheduled) > 5, sorted(set(CUT) & scheduled)),
          (True, []))
    check("  ..and their names stay in the string table: an unknown id sends the client to the login screen",
          [t for t in sorted(people) if t in MT and not names.known(t)], [])
    traders = sorted(t for t in people if world.entity_root(t, MT[t][0]) == world.TRADER)
    check("every stall there was empty: nothing goes out of sale",
          {(i, t): items.stock_for(t, i) for i in CUT for t in traders if t in stood_in(i) and items.stock_for(t, i)},
          {})
except Exception:
    import traceback
    fails.append("the people broke:\n" + traceback.format_exc())


# --- 4. the map's names --------------------------------------------------------------------
print("the map's names")
try:
    ours = {(e["x"], e["y"]): bool(e.get("hide")) for e in LABELS if e.get("why", "").startswith(CUT_WHY)}
    check("data/map_labels.json hides the 66 names of the far banks and edits nothing else for the cut",
          (sorted(ours), set(ours.values())), (sorted(HIDDEN), {True}))
    check("  ..five of them the owner's map labels of 2026-10-11 had retexted: a hide now, of the same row",
          [(c, len([e for e in LABELS if (e["x"], e["y"]) == c])) for c in RETEXTED], [(c, 1) for c in RETEXTED])
    check("  ..every one of them over a far bank or an island", sorted(c for c in HIDDEN if not far(c)), [])
    raw = open(os.path.join(world.RES, "database", "locations.xml"), "rb").read()
    out, _n = map_labels.apply(raw)

    def rows_of(doc):
        got = []
        for m in map_labels.ROW.finditer(doc):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            got.append((int(a["x"]), int(a["y"]), html.unescape(a["text"].decode("utf-8"))))
        return got
    before = rows_of(raw)
    if len([r for r in before if r[2] == "Лагерь за рекой"]) == 3:
        after = rows_of(out)
        check("on the original's file no name is left over a far bank or an island, where it had 70",
              ([r for r in after if far(r[:2])], len([r for r in before if far(r[:2])])), ([], 70))
        others, _n = map_labels.apply(raw, [(x, y, w, t) for x, y, w, t in map_labels.load()
                                            if (x, y) not in HIDDEN])
        check("  ..and every name off the far banks is as the edits without this cut's leave it, row for row",
              [r for r in after if not far(r[:2])], [r for r in rows_of(others) if not far(r[:2])])
        check("  ..the pirates, the base СМЕРШ and the piers among them",
              sorted({(x, y) for x, y, _t in after
                      if (x, y) in ((6160, 1975), (6161, 1973), (6126, 1980), (5965, 1728), PIER_DN_CELL,
                                    (6182, 1977))}),
              sorted([(6160, 1975), (6161, 1973), (6126, 1980), (5965, 1728), PIER_DN_CELL, (6182, 1977)]))
    else:
        # An installed client's file is the release's, with names hidden.
        print("  -- %s is not the original's: the map's names are held on the edits alone"
              % os.path.join(world.RES, "database", "locations.xml"))
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())


# --- 5. the map's squares and letters ------------------------------------------------------
print("the map's squares and letters")
try:
    plan = map_cells.load()
    check("server/map_cells.py paints over the squares of the far banks: the seven on the cut places' cells by"
          " data/retired.json, the sixteen under hidden names or none by data/map_cells.json",
          ([c for c in SQ_PLACES if c not in world.retired_cells()],
           [c for c in SQ_NAMES if not plan.cells.get(c, "").startswith(CUT_WHY)]), ([], []))
    check("  ..with the five the cut of the camps across the river took", [c for c in SQ_CAMPS if c not in plan.cells],
          [])
    caps = collections.defaultdict(set)
    for b, was, why in plan.captions:
        if why.startswith(CUT_WHY):
            caps[was] |= {map_cells.tile_of(b[0], b[1]), map_cells.tile_of(b[2], b[3])}
    check("  ..and the letters: «Поселок» by Вади-Хальфа, Абри and Донгола, the island's two lines",
          {w: sorted(t) for w, t in caps.items()}, CAPTIONS)

    def boxed(X, Y):
        return [was for (x0, y0, x1, y1), was, _why in plan.captions if x0 <= X <= x1 and y0 <= Y <= y1]
    check("  ..while the picture's small grey crosses stay: they stand on the towns' bank and in the lake as well"
          " (by 6016,1713, 6116,1632, 6018,1650), a mark of the picture's own, tied to no place",
          {c: boxed(8 * c[0] + 4, 8 * c[1] + 4) for c in CROSSES}, {c: [] for c in CROSSES})
    named_no_place = sorted(c for c in HIDDEN if c not in ON_CELLS)
    check("every hidden name with no place under it is decided: its square goes, or the picture has none there"
          " ('bare', 34)",
          ([c for c in named_no_place if c not in plan.cells and c not in plan.bare], len(plan.bare),
           sorted(c for c, why in plan.bare.items() if why.startswith(CUT_WHY)) == sorted(plan.bare)),
          ([], 34, True))
    check("  ..and no 'bare' cell is a square's", sorted(set(plan.bare) & (set(SQ_PLACES) | set(SQ_NAMES))), [])
    check("the tiles a change can touch take in 15808, the white square of «Ангар в джунглях»",
          15808 in plan.tiles(), True)
    base = {}
    with io.open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3:
                base[parts[2]] = parts[0]
    read = map_cells.reader(world.RES)
    # (12726, the row above the picture where 322's cell on the north rim
    # would have its frame, is no tile of any client)
    have = {n: read(map_cells.tile_path(n)) for n in plan.tiles() if n != 12726}
    if all(have.values()) and all(hashlib.sha256(d).hexdigest() == base.get(map_cells.tile_path(n))
                                  for n, d in have.items()):
        new, _report = map_cells.apply(read, plan)
        bc = map_cells.Canvas(read)
        ac = map_cells.Canvas(lambda p: new.get(p) or read(p))
        before, after = map_cells.Squares(bc), map_cells.Squares(ac)
        squares = SQ_PLACES + SQ_NAMES + SQ_CAMPS
        check("on the real map each of the 28 squares of the far banks is found before, none after",
              ([c for c in squares if before.at(*c) is None], [c for c in squares if after.at(*c) is not None]),
              ([], []))
        left = []
        for name, (x0, x1, y0, y1) in FAR.items():
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    if bc.tile(map_cells.tile_of(8 * x, 8 * y)) is None:
                        continue
                    sq = after.at(x, y)
                    if sq is not None and map_cells.painted_square(ac, sq):
                        left.append((name, x, y))
        check("  ..and no square of the palette's very colour is left anywhere on the far banks", left, [])
        check("  ..nor on a 'bare' cell, before or after", [c for c in plan.bare if before.at(*c) or after.at(*c)], [])
        moved = []
        for n in sorted(new):
            n_ = int(n.rsplit("/", 1)[1].split(".")[0])
            X0, Y0 = n_ % 256 * 256, n_ // 256 * 256
            for x in range(X0 // 8, (X0 + 256) // 8):
                for y in range(Y0 // 8, (Y0 + 256) // 8):
                    if (x, y) in plan.cells:
                        continue
                    sb = before.at(x, y)
                    if sb is not None and map_cells.painted_square(bc, sb) and after.at(x, y) != sb:
                        moved.append((x, y))
        check("every other square of the palette in the tiles that change is where it was, as it was (the towns'"
              " banks', the pirates', СМЕРШ's)", moved, [])

        def strokes(canvas, box):
            x0, y0, x1, y1 = box
            return sum(abs(canvas.original(X + 1, Y)[0] - canvas.original(X, Y)[0])
                       + abs(canvas.original(X, Y + 1)[0] - canvas.original(X, Y)[0])
                       for X in range(x0, x1) for Y in range(y0, y1))
        gone = {}
        for b, was, why in plan.captions:
            if why.startswith(CUT_WHY):
                gone[(was, b[0])] = (strokes(bc, b), strokes(ac, b))
        check("the letters are gone: the steps of brightness in each box after under half of before (%s)"
              % ", ".join("%s %d: %d -> %d" % (w, x, b, a) for (w, x), (b, a) in sorted(gone.items())),
              {k: a < 0.5 * b for k, (b, a) in gone.items()}, {k: True for k in gone})
        x0, y0, x1, y1 = ISLAND
        ground = [bc.original(X, Y)[0] for X in CHANNEL for Y in list(range(y0 - 3, y0)) + list(range(y1 + 1, y1 + 4))]
        band = [ac.original(X, Y)[0] for X in CHANNEL for Y in range(y0, y1 + 1)]
        g_, b_ = sum(ground) / len(ground), sum(band) / len(band)
        check("the island's west channel runs on through where its letters were, painted in strips from the ground"
              " above and below: over its columns (%d-%d) the band is as dark as the ground just above and below it,"
              " within 8 levels (%.0f against %.0f; a patch from aside left it 15 lighter, a pale smear across the"
              " channel)" % (CHANNEL[0], CHANNEL[-1], b_, g_), abs(b_ - g_) <= 8, True)
    else:
        print("  -- not the original's tiles under %s: the real map is test_map_cells' (with them)" % world.RES)
except Exception:
    import traceback
    fails.append("the squares broke:\n" + traceback.format_exc())


# --- 6. the encounters ---------------------------------------------------------------------------
print("the encounters")
try:
    now_settled, now_retired = dict(world.settlements()), dict(world.retired_cells())
    was_settled = dict(now_settled)
    was_settled.update(ON_CELLS)
    was_retired = {c: i for c, i in now_retired.items() if c not in ON_CELLS}

    def band_map(settled, retired):
        saved = world.settlements, world.retired_cells, world.location_at
        world.settlements, world.retired_cells = (lambda: settled), (lambda: retired)
        world.location_at = lambda x, y: settled.get((x, y)) or world.pack(x, y)
        try:
            return {(x, y): b.camp for x in range(5830, 6010) for y in range(1680, 1880)
                    for b in [encounters.band_at(x + 0.5, y + 0.5)] if b is not None}
        finally:
            world.settlements, world.retired_cells, world.location_at = saved
    now = band_map(now_settled, now_retired)
    was = band_map(was_settled, was_retired)
    unlisted = band_map(now_settled, was_retired)
    check("the map of the camps' wasteland round Вади-Хальфа and Абри is what it was, cell for cell (%d cells)"
          % len(now), (now == was, len(now) > 1000), (True, True))
    check("  ..which the cut's cells listed as the towns' ground keep so: unlisted, 31 cells round Абри's dig and"
          " base and Эван's farm, beyond the owner's wall, would be the camps 92's and 88's",
          (len(set(unlisted.items()) - set(was.items())), {b for _c, b in set(unlisted.items()) - set(was.items())}),
          (31, {88, 92}))
except Exception:
    import traceback
    fails.append("the encounters broke:\n" + traceback.format_exc())


# --- 7. the database -----------------------------------------------------------------------
print("the database")


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


try:
    check("the run_once's places are the hundred and fifteen, Абри's far bank, Эван's and Абри's copies to the port"
          " market 187, the rest to Причал, each on its cell, its name new",
          (sorted(accounts.RIVER_ALL_ABRI + accounts.RIVER_ALL_PRICHAL), len(set(accounts.RIVER_ALL_ABRI)
                                                                            & set(accounts.RIVER_ALL_PRICHAL)),
           sorted(accounts.RIVER_ALL_ABRI), accounts.ABRI_CUT_TO, accounts.RETIRED_PLACES_TO,
           accounts.RIVER_ALL_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                          accounts.HALFA_FSC_FIX, accounts.ABRI_CUT_FIX, accounts.RIVER_CAMPS_FIX,
                                          accounts.ABRI_CLOTHES_FIX, accounts.PREMIUM_THINGS_FIX)),
          (CUT, 0, ABRI_CUT,
           (PORT_AB,) + world.cell_of(PORT_AB), (PRICHAL,) + world.cell_of(PRICHAL), True))
    path = os.path.join(tempfile.mkdtemp(), "river_all.db")
    st = accounts.Store(path)
    acc, _ = st.register("riverall", "secret")
    ids = {}
    for name, loc, home in (("in433", 433, None), ("in1198", 1198, None), ("in435", 435, None),
                            ("in474", 474, None), ("in322", 322, None), ("in517", 517, None),
                            ("in434", 434, None), ("in325", 325, None), ("in1210", 1210, None),
                            ("in539", 539, None), ("in288", 288, None), ("in507", 507, None), ("in441", 441, None),
                            ("in547", 547, None), ("in987", 987, None),
                            ("home323", 36, 323), ("home434", 188, 434),
                            ("in429", 429, None), ("pier", PRICHAL, None), ("port", PORT_AB, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5943, gy = 1722,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5943, home_gy = 1722"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in433"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.RIVER_ALL_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    to_prichal = ("in433", "in1198", "in435", "in474", "in322", "in517", "in539", "in288", "in507", "in441")
    to_port = ("in434", "in325", "in1210", "in547", "in987")
    check("whoever was in Вади-Хальфа's, Донгола's, Абу-Хамед's or the north-west corner's cut places, a tomb,"
          " Le_Mon's base, a room of «9 мая», the warehouse 288, Доктор «Д»'s pass or the quest wasteland is at"
          " Причал, on its cell, off the map, with no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in to_prichal}, {n: (PRICHAL, 5965, 1728, 0, None) for n in to_prichal})
    check("  ..whoever was on Абри's far bank, in Эван's places or in Абри's copies (of «9 мая», of Доктор «Д»'s"
          " laboratory) at Абри's port market",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in to_port}, {n: (PORT_AB, 5860, 1835, 0, None) for n in to_port})
    check("  ..a home in 323 is Причал now, in 434 the port market, the character left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home323", "home434")],
          [(PRICHAL, 5965, 1728, 36), (PORT_AB, 5860, 1835, 188)])
    check("  ..the one in the camp 429 (the cut of the camps across the river, run long ago), at Причал and at the"
          " port market untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in429", "pier", "port")],
          [(429, 77), (PRICHAL, 77), (PORT_AB, 77)])
    check("the journal is untouched", sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..and the log says so: ten moved to Причал and five to the port market, a home each",
          ([ln for ln in lines.lines if accounts.RIVER_ALL_FIX in ln and "10 character(s) moved" in ln
            and "to 41" in ln and "1 home(s) moved" in ln] != [],
           [ln for ln in lines.lines if accounts.RIVER_ALL_FIX in ln and "5 character(s) moved" in ln
            and "to 187" in ln and "1 home(s) moved" in ln] != []),
          (True, True))
    check("  ..nothing left to do on a second pass", accounts.relocate_river_all(st.db), dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 433 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.RIVER_ALL_FIX)), (433, True))
    st.close()
except Exception:
    import traceback
    fails.append("the database broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("river all cut OK")
