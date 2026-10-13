"""Донгола's map and population, made ready for the town (the owner's «и
потом сделай донголу тоже», 2026-10-13: Донгола the way Абри was made the
day before -- «В Абри добавь мобов в лагеря и в окрестности ... Восстанови
все квесты и все имена мобов»; then «делай как считаешь нужным»):

  * the places that opened as plain wasteland stand on their cells (data/
    settlements_verified.json): Мастер Люшера Вельс's house 147, Зубери's
    dig 253, the three roads of Люшер's masters 144-146, the mine's second
    and third entrances 157 and 161, the saltpetre pit's mouth 209, the
    ammunition works 211, the dump 1042, the gladiators' arena 697, the
    fallen satellite 77, the Магриб's patrol 115, the chiefs' places 91 and
    99 on their camps' second cells; each cell leads into its file and the
    file back to it, each is walkable and reached on foot from the station;
  * who stands there: the camps 93/98 and the chiefs' places 91/99 filled
    with the ДСР and the Peacekeepers in their bands (data/camp_fill.json),
    the ДСР's commanders rank and file, Джохар and Амин at their rows'
    levels; the bosses keep the hours, the treasurers stand all day;
    Вильям Блейд stands in his camp by hand and in no ambush; the camps'
    boxes, Вельс's boxes and the quarry's stones stand; the patrols ring
    both camps; Мортимер stands in the new market; the lottery sellers stand
    all year; Нур-ад-Дин registers trophies; Люшер's masters stand on their
    roads only in their minutes of each hour;
  * the ambushes: the wasteland round Донгола's two camps is theirs,
    without the named ones; every cell of it a walk from the station
    reaches is on the east bank -- the far bank's part of the ring is beyond
    the river and the owner's wall --; Вади-Хальфа's and Абри's rings are
    the same cell for cell;
  * the names: nobody who stands in a place of Донгола or an interior its
    doors and ways reach shows his mobs.xml name, and every place on a cell
    round the town a walk reaches is one of those looked at; the prisoners,
    their godfather, the dump's tramps and Люшер's fanatics show the
    original's rows;
  * the interiors: the prison's blocks, the quarry's pits, the mine's
    tiers and tunnels, the sewers and Зона 49 open into each other by their
    sides (data/passages.json 'sides') and never onto the map ('no_map'):
    every side of each is listed and leads into the interior it names;
    from each of the mine's three entrances every tier and tunnel is
    reached; the quarry's healer registers no home; the doors of the
    copper, saltpetre and lead mines and of the town's mine are followed
    (high or medium), each where the file's sign or Вади-Хальфа's twin
    puts it.

    LAVA_RES=.../res python3 server/test_dongola_world.py
"""
import collections
import datetime
import json
import math
import os
import sys
from types import SimpleNamespace

os.environ["LAVA_BOSS_HOURS"] = "14,18,22"
os.environ["LAVA_BOSS_STAY"] = "60"
os.environ["LAVA_BOSS_CLOCK"] = "2026-10-13T12:00:00"
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bosses        # noqa: E402
import encounters    # noqa: E402
import events        # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import quests        # noqa: E402
import rooms         # noqa: E402
import server        # noqa: E402
import travel        # noqa: E402
import trophies      # noqa: E402
import world         # noqa: E402

from testkit import check, fails  # noqa: E402

MT = world.mob_types()
with open(os.path.join(ROOT, "data", "orig_names_manual.json"), encoding="utf-8") as _fh:
    REMAINDER = {int(k) for k in json.load(_fh)["none"]}
with open(os.path.join(ROOT, "data", "passages.json"), encoding="utf-8") as _fh:
    PASSAGES = json.load(_fh)

# cell -> the place it opens since 2026-10-13
CELLS = {(5878, 2012): 147, (5899, 2003): 253, (5900, 2017): 144, (5894, 2019): 145,
         (5876, 2031): 146, (5896, 2026): 157, (5900, 2026): 161, (5943, 1960): 209,
         (5921, 1982): 211, (5879, 2013): 1042, (5875, 2009): 697, (5877, 2004): 77,
         (5889, 2003): 115, (5882, 2036): 91, (5920, 2010): 99}
CAMPS = {(5883, 2035): 93, (5921, 2011): 98}
STATION, STATION_CELL = 49, (5877, 2010)

# The places of Донгола a player can walk into (settlements in its box) and
# the interiors their doors, sides and quest ways lead to.
TOWN = [49, 50, 72, 73, 74, 79, 96, 97, 103, 105, 197, 445]
QUEST_PLACES = [67, 68, 69, 77, 112, 113, 114, 115, 144, 145, 146, 147, 150, 162, 195, 253, 625, 697,
                1042]
CAMP_PLACES = [91, 93, 98, 99]
WORKS = [208, 209, 210, 211, 212, 663, 664, 665, 1031, 1032, 1033, 1224, 1225, 1226]
PRISON = [159, 618, 619, 620, 621, 622]
QUARRY = [631, 632, 633, 634, 635]
MINE_TOP = [155, 157, 161]
MINE = [614, 616, 1013, 1015, 1020, 1021, 1022, 1023, 1214]
SEWERS = [607, 608, 1009]
ZONE49 = [702, 703, 704, 705]
DUNGEON = [597, 1007]
PLACES = (TOWN + QUEST_PLACES + CAMP_PLACES + WORKS + PRISON + QUARRY + MINE_TOP + MINE + SEWERS
          + ZONE49 + DUNGEON)
BOX = (5866, 5960, 1950, 2066)                 # x0, x1, y0, y1 round the town


def room(lid):
    return rooms.Room(world.location(lid), rooms.IdAllocator(), MT)


def stood(r):
    return collections.Counter(n.type_id for n in r.npcs.values())


def internal(t):
    return names.ALL.get(t, MT[t][1]) == MT[t][1]


# --- the cells --------------------------------------------------------------------------------
print("the cells")
try:
    check("every restored cell leads into its file", {c: world.location_at(*c) for c in CELLS}, CELLS)
    check("  ..and every file back to its cell (world.cell_of)",
          {c: world.cell_of(i) for c, i in CELLS.items()}, {c: c for c in CELLS})
    check("the two camps keep their first cell, and only it, now that the second is the chief's",
          ({c: world.location_at(*c) for c in CAMPS},
           sorted(c for c, i in world.settlements().items() if i in CAMPS.values())),
          (CAMPS, sorted(CAMPS)))
    check("the first entrance of the mine stays where the placer stood it, beside the other two",
          (world.cell_of(155), world.location_at(5895, 2026)), ((5895, 2026), 155))
    check("every restored cell is walkable", [c for c in CELLS if not world.passable(*c)], [])
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import test_borders  # noqa: E402
    walked = test_borders.walk_from(STATION_CELL)
    check("  ..and a walk from the station on the owner's map reaches each of them and the camps",
          sorted(c for c in list(CELLS) + list(CAMPS) if c not in walked), [])
    # (the places of ours, data/locations, are the owner's: the location
    # editor's checks are theirs)
    check("  ..and every place on a cell round the town that walk reaches is one this suite looks at"
          " (a place left out would show its people unchecked; the places of ours aside)",
          sorted((i, c) for c, i in world.settlements().items()
                 if BOX[0] <= c[0] <= BOX[1] and BOX[2] <= c[1] <= BOX[3] and c in walked
                 and i not in PLACES and not (i >= world.FIRST_NEW_ID and i in world.overlay_ids())), [])
    check("each place's way out of its file is open: the dump's and the arena's one side is the west,"
          " the works' three, the others' four",
          {i: sorted({s for s in travel.exit_sides(world.location(i)).values() if s in travel.SIDES})
           for i in (1042, 697, 211, 147)},
          {1042: ["W"], 697: ["W"], 211: ["E", "S", "W"], 147: ["E", "N", "S", "W"]})
except Exception:
    import traceback
    fails.append("the cells broke:\n" + traceback.format_exc())

# --- who stands there -------------------------------------------------------------------------
print("who stands there")
try:
    fill = {lid: world.camp_fill(lid) for lid in (93, 91, 98, 99)}
    check("the table fills every empty slot of the two camps and their chiefs' places",
          {lid: len(v) for lid, v in fill.items()},
          {lid: sum(1 for _c, t in world.location(lid).spawns if t == 0) for lid in fill})
    BAND = {93: (12, 14), 91: (12, 14), 98: (14, 16), 99: (14, 16)}
    check("  ..each in its band",
          {lid: [t for t in v if not BAND[lid][0] <= mobs.stats(t).level <= BAND[lid][1]]
           for lid, v in fill.items()}, {lid: [] for lid in fill})
    check("  ..with their factions' own, the ДСР jm_ and the Peacekeepers pc_",
          {lid: sorted({MT[t][1].split("_")[0] for t in fill[lid]}) for lid in fill},
          {93: ["jm"], 91: ["jm"], 98: ["pc"], 99: ["pc"]})
    check("  ..and every rank of each faction stands in one of its two places",
          (sorted(set(fill[93]) | set(fill[91])), sorted(set(fill[98]) | set(fill[99]))),
          (list(range(362, 374)) + [592], list(range(395, 407)) + [593]))
    r93, r91, r98, r99 = room(93), room(91), room(98), room(99)
    check("the ДСР's camp 93: Полковник Халил, ten of the fill with the treasurer, Вильям Блейд, two"
          " boxes", stood(r93),
          collections.Counter({374: 1, 362: 1, 363: 1, 365: 1, 366: 1, 368: 1, 369: 1, 370: 1, 372: 1,
                               373: 1, 592: 1, 1565: 1, 2165: 2}))
    check("  ..its chief's place 91: Джибрил Ибрагим and eleven of the fill",
          (stood(r91)[375], sum(stood(r91).values())), (1, 12))
    check("the Peacekeepers' camp 98: Шеф Дженсен, ten of the fill with the treasurer, two boxes",
          stood(r98),
          collections.Counter({407: 1, 395: 1, 396: 1, 397: 1, 398: 1, 399: 1, 400: 1, 401: 1, 402: 1,
                               403: 1, 593: 1, 2167: 2}))
    check("  ..its chief's place 99: Макс Коул and eleven of the fill",
          (stood(r99)[408], sum(stood(r99).values())), (1, 12))
    check("the boxes are things, standing by the table (world.STANDING_OBJECTS), as are Вельс's boxes in"
          " his house (commoners) and the quarry's stones, but its control panel",
          ([world.creature_role(t) for t in (2165, 2167, 980)],
           sorted(world.STANDING_OBJECTS[93]), sorted(world.STANDING_OBJECTS[98]),
           stood(room(147)), [stood(room(i))[980] for i in (631, 633, 634, 635)],
           [stood(room(i))[2022] for i in (631, 633, 634, 635)]),
          (["object", "object", "object"], [2165], [2167],
           collections.Counter({827: 1, 828: 3}), [20, 20, 20, 20], [0, 0, 0, 0]))
    LEVELS = {592: 14, 593: 16, 1565: 14, 2165: 13, 2167: 15, 644: 14, 134: 12, 135: 13}
    check("the levels set by hand (data/build_mob_types.py DESIGNED_LEVELS, and DESIGNED_KINDS for"
          " Джохар and Амин, whose names said 8)",
          {t: mobs.stats(t).level for t in LEVELS}, LEVELS)
    check("the ДСР's commanders are rank and file (DESIGNED_KINDS), and stand in the ambushes' bands",
          {t: world.creature_role(t) for t in (362, 366, 370)}, {362: "mob", 366: "mob", 370: "mob"})
    check("the bosses keep the hours, at the levels of their files; the treasurers stand all day"
          " (bosses.ALL_DAY)",
          ({t: (bosses.keeps_hours(t), mobs.stats(t).level) for t in (374, 375, 407, 408)},
           {t: (world.creature_role(t), bosses.keeps_hours(t)) for t in (592, 593)}),
          ({374: (True, 26), 375: (True, 24), 407: (True, 30), 408: (True, 28)},
           {592: ("boss", False), 593: ("boss", False)}))
    check("Вильям Блейд stands in the ДСР's camp by hand and is in no ambush's band",
          ([int(r["type"]) for r in world.placed_in(93)], 1565 in world.camp_fill(93),
           [b.camp for b, _r in encounters.bands() if 1565 in b.types]),
          ([1565], False, []))
    check("Мортимер stands in the new market 197 by the original's file and gives the exchanges",
          (stood(room(197))[1188], 1188 in {t for _c, t in world.location(197).spawns},
           quests.given_by(1188)), (1, True, list(range(301, 308))))
    check("the lottery sellers stand all year in the old and the new market and the black market"
          " (world.SEASON_KEPT)",
          (stood(room(50))[663], stood(room(197))[663], stood(room(103))[712]), (1, 1, 1))
    check("Нур-ад-Дин registers trophies and keeps his stall",
          (156 in world.TROPHY_REGISTRARS, trophies.keeps_stall(156), "Нур-ад-Дин" in trophies.WHERE,
           world.entity_root(156, MT[156][0])), (True, True, True, world.TRADER))
    check("every row of data/placements.json can stand (rooms.placement_problems)",
          rooms.placement_problems(MT), [])
    patrols = collections.defaultdict(list)
    for key, recs in world.placements().items():
        for r in recs:
            if r.get("patrol") in (93, 98):
                patrols[r["patrol"]].append((world.unpack(key), int(r["type"])))
    check("patrols ring both camps: twelve cells each, eight of the camp's own fighters a cell, round the"
          " camp and its chief's place",
          {c: (len({cell for cell, _t in v}), len(v)) for c, v in patrols.items()}, {93: (12, 96), 98: (12, 96)})
    check("  ..of the faction's ranks only, no boss, treasurer, named man or box",
          {c: sorted({t for _cell, t in v} - set(range(362, 374)) - set(range(395, 407)))
           for c, v in patrols.items()}, {93: [], 98: []})
    check("  ..each cell touching the camp or its chief's place",
          [cell for c, v in patrols.items() for cell, _t in v
           if min(max(abs(cell[0] - p[0]), abs(cell[1] - p[1]))
                  for p in (world.cell_of(c), world.cell_of({93: 91, 98: 99}[c]))) != 1], [])
    owned = {(lid, t): getattr(events.table().owned.get((lid, t)), "name", None)
             for lid, t in ((144, 817), (145, 818), (146, 819))}
    check("Люшер's masters stand on their roads only in their windows",
          (owned, [t for lid, t in owned if t in stood(room(lid))]),
          ({(144, 817): "lusher_road1", (145, 818): "lusher_road2", (146, 819): "lusher_road3"}, []))

    def at(h, m):
        return datetime.datetime(2026, 10, 13, h, m, tzinfo=bosses.ZONE).timestamp()
    check("  ..the first from the hour on for ten minutes, the second from ten past and the third from"
          " twenty past for five each (texts 48683, 48686, 48690)",
          [[events.is_open(w, at(h, m)) for w in ("lusher_road1", "lusher_road2", "lusher_road3")]
           for h, m in ((13, 0), (13, 9), (13, 12), (13, 16), (13, 21), (13, 26), (3, 1))],
          [[True, False, False], [True, False, False], [False, True, False], [False, False, False],
           [False, False, True], [False, False, False], [True, False, False]])
    check("  ..and the roads' Сакибы stand all the time", [stood(room(i))[t] for i, t in
                                                           ((144, 829), (145, 830), (146, 831))], [1, 1, 1])
except Exception:
    import traceback
    fails.append("who stands there broke:\n" + traceback.format_exc())

# --- the ambushes -----------------------------------------------------------------------------
print("the ambushes")
try:
    bands = {b.camp: b for b, _r in encounters.bands()}
    check("Донгола's two camps have their bands, of the fill's fighters only",
          {c: (bands[c].lo, bands[c].hi, sorted(bands[c].types)) for c in (93, 98)},
          {93: (12, 14, [362, 363, 365, 366, 368, 369, 370, 372, 373]),
           98: (14, 16, [395, 396, 397, 398, 399, 400, 401, 402, 403])})
    check("  ..no named fighter, no treasurer, no box in any band",
          sorted({t for b in bands.values() for t in b.types} & {1563, 1564, 1565, 590, 591, 592, 593,
                                                                  2163, 2164, 2165, 2167, 586}), [])

    def ambush_map(box):
        x0, x1, y0, y1 = box
        out = {}
        for x in range(x0, x1):
            for y in range(y0, y1):
                b = encounters.band_at(x + 0.5, y + 0.5)
                if b is not None:
                    out[(x, y)] = b.camp
        return out

    HALFA_RING = (5930, 6030, 1690, 1775)
    ABRI_RING = (5845, 5910, 1820, 1885)
    DONGOLA_RING = (5850, 5950, 1980, 2066)
    now = {k: ambush_map(b) for k, b in (("halfa", HALFA_RING), ("abri", ABRI_RING),
                                         ("dongola", DONGOLA_RING))}
    saved = encounters.REGIONS
    try:
        encounters.REGIONS = tuple(r for r in saved if r["town"] != "Донгола")
        encounters._BANDS = None
        was = {k: ambush_map(b) for k, b in (("halfa", HALFA_RING), ("abri", ABRI_RING),
                                             ("dongola", DONGOLA_RING))}
    finally:
        encounters.REGIONS = saved
        encounters._BANDS = None
    check("Вади-Хальфа's and Абри's rings are what they were without Донгола's region, cell for cell",
          (len(now["halfa"]) > 1500, now["halfa"] == was["halfa"], len(now["abri"]) > 800,
           now["abri"] == was["abri"]), (True, True, True, True))
    ring = now["dongola"]
    check("  ..and Донгола's wasteland, empty before, is its two camps' now",
          (len(was["dongola"]), len(ring) > 2500, sorted(set(ring.values()))), (0, True, [93, 98]))
    town = list(world.settlements()) + list(world.retired_cells())
    check("  ..never on a settlement's cell or beside one, the cut's cells counted",
          [c for c in ring if any(math.hypot(c[0] - x, c[1] - y) < 1.5 for x, y in town)], [])
    check("  ..and every cell of it within reach of its camp",
          [c for c, camp in ring.items()
           if math.hypot(c[0] - world.cell_of(camp)[0], c[1] - world.cell_of(camp)[1]) > 25], [])
    # An ambush is met only on a cell a player walks onto; the ring reaches
    # over the Nile to the west, where the owner's wall and the river keep
    # everybody out. One walk from the station, here, instead of a search on
    # every step.
    reach = [c for c in ring if c in walked]
    off = [c for c in ring if c not in walked]
    rows = collections.defaultdict(lambda: [[], []])
    for x, y in reach:
        rows[y][0].append(x)
    for x, y in off:
        rows[y][1].append(x)
    check("every cell of the ring a walk from the station reaches is on the east bank: on each row the"
          " cells no walk reaches lie west of every cell one does, across the river",
          sorted(y for y, (r, o) in rows.items() if r and o and max(o) >= min(r)), [])
    check("  ..the most of the ring is walked to, and the far bank's part of it is not",
          (len(reach) > 3000, 200 < len(off) < 600, max(x for x, _y in off) < 5877), (True, True, True))
    check("  ..nor is any cell of the far bank the cut of everything across the river emptied: the dig"
          " 435's, the base НИЛ-3's, the camp 431's",
          [c for c in ((5864, 2001), (5863, 2002), (5864, 2002)) if c in walked], [])
except Exception:
    import traceback
    fails.append("the ambushes broke:\n" + traceback.format_exc())

# --- the names --------------------------------------------------------------------------------
print("the names")
try:
    shown, in_files = {}, {}
    for lid in PLACES:
        loc = world.location(lid)
        for _c, t in loc.spawns:
            if not t or t not in MT:
                continue
            if world._name_tokens(MT[t][1]) & world.EVENT_TOKENS \
                    and not world.belongs_here(t, MT[t][1], MT[t][0], True, lid):
                continue                         # a season's or the developers', nobody sees it
            if internal(t):
                in_files.setdefault(t, set()).add(lid)
        for n in room(lid).npcs.values():
            if internal(n.type_id):
                shown.setdefault(n.type_id, set()).add(lid)
    check("nobody who stands in Донгола's places shows his mobs.xml name",
          {t: sorted(w) for t, w in shown.items()}, {})
    check("  ..the files' own who would are the remainder data/orig_names_manual.json lists under"
          " \"none\", each held out of its room (data/schedule.json held_out)",
          {t: sorted(w) for t, w in in_files.items()}, {4047: [77], 6896: [77], 5113: [103]})
    SHOWN = {932: "Заключенный", 933: "Заключенный", 934: "Заключенный", 935: "Заключенный",
             936: "Заключенный", 2174: "Беглый каторжник<br>Хранитель общака", 1772: "Опасный БОМЖ",
             671: "Фанатик<br>Люшер", 670: "Опасный БОМЖ", 672: "Боец<br>Люшер",
             374: "Полковник Халил<br>ДСР", 375: "Джибрил Ибрагим<br>ДСР", 407: "Шеф Дженсен<br>Миротворцы",
             408: "Макс Коул<br>Миротворцы", 1565: "Вильям Блейд<br>ДСР", 156: "Нур-ад-Дин<br>водитель",
             138: "Грегори<br>Лекарь", 230: "Собака<br>Дикое животное"}
    check("the prisoners, their godfather, the tramps and Люшер's men, the camps' bosses and Блейд, the"
          " driver, the healer and the flayers' dogs show the original's rows (the typos mended)",
          {t: names.ALL.get(t) for t in SHOWN}, SHOWN)
    RANKS = {362: "Командир", 366: "Командир Группы", 370: "Полевой Командир", 364: "Солдат",
             372: "Спецназ", 373: "Командос", 395: "Капрал", 399: "Сержант", 404: "Снайпер",
             406: "Элитный Штурмовик", 592: "Казначей<br>ДСР", 593: "Казначей<br>Миротворцы"}
    check("the factions' ranks by their own blocks (8925-8936, 8941-8953)",
          {t: names.ALL.get(t, "").startswith(w) for t, w in RANKS.items()}, {t: True for t in RANKS})
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())

# --- the interiors ----------------------------------------------------------------------------
print("the interiors")
try:
    SIDES = {618: {"E": 622}, 619: {"N": 622}, 620: {"S": 622}, 621: {"W": 622},
             622: {"W": 618, "S": 619, "N": 620, "E": 621},
             631: {"N": 632, "S": 633, "W": 635, "E": 634}, 632: {"S": 631}, 633: {"N": 631},
             634: {"W": 631}, 635: {"E": 631},
             1013: {"W": 1022}, 1015: {"E": 1023}, 1023: {"W": 1015, "E": 1020},
             1020: {"W": 1023, "E": 1021}, 1021: {"W": 1020, "E": 1022}, 1022: {"W": 1021, "E": 1013},
             614: {}, 616: {}, 1214: {},
             607: {"S": 608}, 608: {"N": 607}, 1009: {},
             702: {}, 703: {"S": 705}, 704: {"E": 703}, 705: {"N": 703}}
    files_sides = {lid: sorted({s for s in travel.exit_sides(world.location(lid)).values()
                                if s in travel.SIDES}) for lid in SIDES}
    check("each interior's sides, as its file has them, are the table's: none left to the map",
          files_sides, {lid: sorted(v) for lid, v in SIDES.items()})
    led = {}
    for lid, want in SIDES.items():
        loc = world.location(lid)
        for side in want:
            cell = min(c for c, s in travel.exit_sides(loc).items() if s == side)
            ex = travel.plan_exit(loc, cell, 5903, 1996)
            led[(lid, side)] = (ex.loc_id, (ex.gx, ex.gy))
    check("  ..and each side leads into the interior it names, the map cell kept",
          led, {(lid, s): (t, (5903, 1996)) for lid, want in SIDES.items() for s, t in want.items()})
    check("  ..none of them opens onto the map (no_map)", [lid for lid in SIDES if not travel.no_map(lid)], [])
    check("  ..and the client is told so: a sublocation, both map buttons grey (travel.geo_id)",
          [lid for lid in SIDES if not travel.geo_id(world.location(lid), 5903, 1996) >> 26 & 1], [])

    def reached(start):
        seen, todo = set(start), list(start)
        while todo:
            lid = todo.pop()
            ts = []
            for s in "ab":
                rec = travel.door(lid, s)
                if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
                    ts.append(rec.get("target_loc_id"))
            ts += [(travel.side_way(lid, s) or {}).get("target_loc_id") for s in "WNES"]
            for t in ts:
                if t and int(t) not in seen:
                    seen.add(int(t))
                    todo.append(int(t))
        return seen
    check("from each of the mine's three entrances alone every tier and tunnel is reached",
          [(e, sorted(set(MINE) - reached({e}))) for e in MINE_TOP], [(e, []) for e in MINE_TOP])
    check("  ..and from inside, up, each of the entrances",
          sorted(set(MINE_TOP) - reached({1214})), [])
    fake = SimpleNamespace(loc=world.location(632), offers_home=server.Session.offers_home)
    check("the quarry's healer Грегори (138) in its north pit registers no home: the map is out of"
          " reach there (Session.home_here), as he does at the station",
          (server.Session.offers_home(138), server.Session.home_here(fake, 138),
           server.Session.home_here(SimpleNamespace(loc=world.location(STATION),
                                                    offers_home=server.Session.offers_home), 138)),
          (True, False, True))
    WANT = {(663, "b"): 1031, (664, "b"): 1032, (665, "b"): 1033,
            (1031, "a"): 663, (1031, "b"): 1224, (1032, "a"): 664, (1032, "b"): 1225,
            (1033, "a"): 665, (1033, "b"): 1226,
            (1224, "a"): 1031, (1225, "a"): 1032, (1226, "a"): 1033,
            (155, "b"): 616, (157, "b"): 614, (161, "b"): 1013,
            (614, "a"): 157, (614, "b"): 1023, (616, "a"): 155, (616, "b"): 1015,
            (1013, "a"): 161, (1015, "a"): 616, (1023, "a"): 614, (1023, "b"): 1214, (1214, "a"): 1023,
            (597, "b"): 1007, (1007, "a"): 597, (597, "a"): None}
    got = {}
    for (lid, side) in WANT:
        rec = travel.door(lid, side)
        ok = rec and rec.get("confidence") in travel.DOOR_CONFIDENCE
        got[(lid, side)] = int(rec["target_loc_id"]) if ok else None
    check("the mines' control rooms lead to their first tiers, the tiers to each other and back; the"
          " town's mine as Вади-Хальфа's twin; the dungeon's ladder down and back; every door followed but"
          " the dungeon's unmarked one", got, WANT)
    check("  ..the copper, saltpetre and lead mines' by the signs (high), the town's mine and the"
          " dungeon by design (medium); the doors up into the entrances land on the entrance's own cell",
          ({k: travel.door(*k).get("confidence") for k, v in WANT.items() if v},
           sorted(k for k, v in WANT.items() if v and travel.door(*k).get("own_cell"))),
          ({k: "high" if k[0] in (663, 664, 665, 1031, 1032, 1033, 1224, 1225, 1226) else "medium"
            for k, v in WANT.items() if v},
           [(614, "a"), (616, "a"), (1013, "a")]))
except Exception:
    import traceback
    fails.append("the interiors broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("dongola world OK")
