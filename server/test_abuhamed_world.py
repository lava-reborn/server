"""Абу-Хамед's map and population, made ready for the town (the owner's
«сделай потом абу хамед в таком же формате», 2026-10-14: Абу-Хамед the
way Абри and Донгола were made before it -- «В Абри добавь мобов в лагеря и
в окрестности ... Восстанови все квесты и все имена мобов»):

  * the places that opened as plain wasteland stand on their cells (data/
    settlements_verified.json): the pirates' camp 132 and their chief's
    place 133, the Северный Альянс's outpost 168 on its own label and its
    base's chief's place 274 beside the base 263, the saltpetre pit's mouth
    214, the ammunition works 216, the UFO's crash 123, the two places of
    Ан-Насир's chase 222 and 223; the owner's wall lets the station 126 and
    the masters' camp 131 go; each cell leads into its file and the file
    back to it, each is walkable and reached on foot from Вади-Хальфа;
  * who stands there: the camps and the chiefs' places filled with the
    pirates and the Альянс in their bands (data/camp_fill.json), the
    captains and colonels rank and file, the prototype at 20; the five
    bosses keep the hours, the treasurers and the bookkeeper stand all day;
    the named men stand by their camps by hand and in no ambush, the second
    Кленз nowhere; the patrols ring the three camps; the bandits of
    Абимбола's instances at 20 and all day, their men and Гвала's
    crocodiles at 18;
  * the miners' diamond: a row for a quest at the Dark Mine's miners and
    nobody else's, never an ordinary drop;
  * the ambushes: the wasteland round the three camps is theirs, without
    the named ones; every cell of it a walk from the station reaches is on
    the town's bank -- the far bank's part of the ring is beyond the river
    --; Вади-Хальфа's, Абри's and Донгола's rings are the same cell for
    cell;
  * the objects and the people: the camps' boxes and the quarry's stones
    stand, the events' sand and Рэт stand on their places, the lottery
    sellers stand all year in the port, Веласкес registers trophies and
    keeps his stall, Мортимер stands in the port;
  * the names: nobody who stands in a place of Абу-Хамед or an interior its
    doors and ways reach shows his mobs.xml name, and every place on a cell
    round the town a walk reaches is one of those looked at;
  * the interiors: the prison's blocks, the quarry's pits, the Dark Mine's
    tiers, the Academy and the instances never open onto the map
    ('no_map'), the blocks and the pits into each other by their sides
    (data/passages.json 'sides'); from the Dark Mine's entrance every tier
    is reached and back; the quarry's healer registers no home; the doors of
    the copper, saltpetre and lead mines (high, by the signs) and of the
    Dark Mine (medium, by design) are followed; the mountain trail 53 and
    Вади-Хальфа's 623 open into each other both ways.

    LAVA_RES=.../res python3 server/test_abuhamed_world.py
"""
import collections
import json
import math
import os
import sys
from types import SimpleNamespace

os.environ["LAVA_BOSS_HOURS"] = "14,18,22"
os.environ["LAVA_BOSS_STAY"] = "60"
os.environ["LAVA_BOSS_CLOCK"] = "2026-10-14T12:00:00"
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bosses        # noqa: E402
import encounters    # noqa: E402
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

# cell -> the place it opens since 2026-10-14
CELLS = {(6160, 1975): 132, (6161, 1973): 133, (6210, 1986): 168, (6274, 1952): 274,
         (6273, 1953): 263, (6116, 1925): 214, (6139, 1950): 216, (6102, 1848): 123,
         (6225, 1895): 223, (6172, 1902): 222}
# the owner's wall let these two go (data/terrain_verified.json 'blocked')
WALL = {(6182, 1976): 126, (6183, 1977): 131}
STATION, STATION_CELL = 126, (6182, 1976)
PORT = 446
DIAMOND = 5545
BOSSES = (777, 778, 8620, 1037, 1038)
TREASURERS = (764, 1024, 1736)
NAMED = {1750: 132, 1749: 168, 1751: 263, 2170: 263, 1752: 156}
INSTANCE_BOSSES = (1702, 1708, 1709, 1710, 1711, 1718, 1720)
INSTANCE_MEN = (1703, 1719, 1722, 1723, 1724, 1725)
CROCODILE = 1706

# The places of Абу-Хамед a player can walk into (settlements in its box) and
# the interiors their doors, sides and quest ways lead to.
TOWN = [126, 127, 128, 129, 131, 446, 71, 1261]
QUEST_PLACES = [53, 66, 123, 163, 177, 196, 213, 214, 215, 216, 217, 222, 223, 624]
CAMP_PLACES = [132, 133, 168, 263, 274]
WORKS = [666, 667, 668, 1034, 1035, 1036, 1227, 1228, 1229]
PRISON = [649, 650, 651, 652, 653]
QUARRY = [636, 637, 638, 639, 640]
MINE_TOP = [156]
MINE = [615, 1014, 1216, 1254, 1273]
ACADEMY = [1295]
INSTANCES = [690, 691, 692, 693, 694]
PLACES = (TOWN + QUEST_PLACES + CAMP_PLACES + WORKS + PRISON + QUARRY + MINE_TOP + MINE + ACADEMY
          + INSTANCES)
BOX = (6076, 6300, 1840, 2030)                 # x0, x1, y0, y1 round the town


def room(lid):
    return rooms.Room(world.location(lid), rooms.IdAllocator(), MT)


def stood(r):
    return collections.Counter(n.type_id for n in r.npcs.values())


def internal(t):
    return names.ALL.get(t, MT[t][1]) == MT[t][1]


walked = set()

# --- the cells --------------------------------------------------------------------------------
print("the cells")
try:
    check("every restored cell leads into its file", {c: world.location_at(*c) for c in CELLS}, CELLS)
    check("  ..and every file back to its cell (world.cell_of)",
          {c: world.cell_of(i) for c, i in CELLS.items()}, {c: c for c in CELLS})
    check("every restored cell is walkable", [c for c in CELLS if not world.passable(*c)], [])
    check("the station 126 and the masters' camp 131 stand on their cells, walkable since the owner's wall"
          " let them go (data/terrain_verified.json)",
          ({c: world.location_at(*c) for c in WALL}, [c for c in WALL if not world.passable(*c)]),
          (WALL, []))
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import test_borders  # noqa: E402
    walked = test_borders.walk_from(test_borders.START)
    check("  ..and a walk from Вади-Хальфа's start on the owner's map reaches each of them, the station and"
          " the masters' camp",
          sorted(c for c in list(CELLS) + list(WALL) if c not in walked), [])
    check("  ..the same land as a walk from the station: the town is on Вади-Хальфа's side of the wall",
          test_borders.walk_from(STATION_CELL) == walked, True)
    check("  ..and every place on a cell round the town that walk reaches is one this suite looks at"
          " (a place left out would show its people unchecked; the places of ours aside)",
          sorted((i, c) for c, i in world.settlements().items()
                 if BOX[0] <= c[0] <= BOX[1] and BOX[2] <= c[1] <= BOX[3] and c in walked
                 and i not in PLACES and not (i >= world.FIRST_NEW_ID and i in world.overlay_ids())), [])
    check("each place's way out of its file is open: the pirates' camp's three (the river south of it),"
          " the works' three, the crash's three, the others' four",
          {i: sorted({s for s in travel.exit_sides(world.location(i)).values() if s in travel.SIDES})
           for i in (132, 133, 168, 274, 263, 214, 216, 123, 222, 223)},
          {132: ["E", "N", "W"], 133: ["E", "N", "S", "W"], 168: ["E", "N", "S", "W"],
           274: ["E", "N", "S", "W"], 263: ["E", "N", "S", "W"], 214: ["E", "N", "S", "W"],
           216: ["E", "S", "W"], 123: ["E", "N", "S"], 222: ["E", "N", "S", "W"],
           223: ["E", "N", "S", "W"]})
    check("the places of Ан-Насир's chase stand their own: the dug sand 1422 on «Костёр» and Рэт 1423"
          " on «Место преступления», all year (world.SEASON_KEPT)",
          (stood(room(222))[1422], stood(room(223))[1423], world.SEASON_KEPT.get(222),
           world.SEASON_KEPT.get(223)),
          (1, 1, frozenset({1422}), frozenset({1423})))
except Exception:
    import traceback
    fails.append("the cells broke:\n" + traceback.format_exc())

# --- who stands there -------------------------------------------------------------------------
print("who stands there")
try:
    fill = {lid: world.camp_fill(lid) for lid in CAMP_PLACES}
    check("the table fills every empty slot of the three camps and the two chiefs' places",
          {lid: len(v) for lid, v in fill.items()},
          {lid: sum(1 for _c, t in world.location(lid).spawns if t == 0) for lid in fill})
    BAND = {132: (16, 18), 133: (16, 18), 168: (16, 18), 263: (19, 20), 274: (19, 20)}
    check("  ..each in its band (the prototype 2315 at 20 by data/build_mob_types.py DESIGNED_KINDS, whose"
          " name says 21)",
          ({lid: [t for t in v if not BAND[lid][0] <= mobs.stats(t).level <= BAND[lid][1]]
            for lid, v in fill.items()}, mobs.stats(2315).level),
          ({lid: [] for lid in fill}, 20))
    check("  ..with their factions' own, the pirates pt_ and the Альянс na_",
          {lid: sorted({MT[t][1].split("_")[0] for t in fill[lid]}) for lid in fill},
          {132: ["pt"], 133: ["pt"], 168: ["na"], 263: ["na"], 274: ["na"]})
    in_files = {lid: {t for _c, t in world.location(lid).spawns if t} for lid in CAMP_PLACES}
    check("  ..and every rank of each faction stands in one of its places: the pirates' twelve, the"
          " outpost's eleven without the captain 1035 (a boss of the file's kind, no slot left for him),"
          " the base's thirteen",
          (sorted((set(fill[132]) | set(fill[133]) | in_files[133]) - {778}),
           sorted(set(fill[168])), sorted(set(fill[263]) | set(fill[274]))),
          (list(range(764, 777)), list(range(1025, 1035)) + [1036],
           list(range(1728, 1737)) + list(range(2315, 2320))))
    r132, r133, r168, r263, r274 = (room(i) for i in CAMP_PLACES)
    check("the pirates' camp 132: Коммодор Марабу, eleven of the fill with the treasurer, Йохан Демперс,"
          " two boxes",
          stood(r132),
          collections.Counter({777: 1, 765: 1, 766: 1, 767: 1, 768: 1, 769: 1, 770: 1, 772: 1, 773: 1,
                               774: 1, 776: 1, 764: 1, 1750: 1, 2169: 2}))
    check("  ..their chief's place 133: Капитан Нгоро, the file's Мичман and Кавторанг, nine of the fill",
          stood(r133),
          collections.Counter({778: 1, 769: 1, 771: 1, 765: 1, 766: 1, 767: 1, 768: 1, 770: 1, 772: 1,
                               774: 1, 775: 1, 776: 1}))
    check("the Альянс's outpost 168: Генерал Шерхан, eleven of the fill, Гейнц Тейлор and the treasurer"
          " by hand, two boxes",
          stood(r168),
          collections.Counter({8620: 1, 1025: 1, 1026: 1, 1027: 1, 1028: 1, 1029: 1, 1030: 1, 1031: 1,
                               1032: 1, 1033: 1, 1034: 1, 1036: 1, 1749: 1, 1024: 1, 2171: 2}))
    check("the Альянс's base 263: Генерал Шерхан, ten of the fill with the bookkeeper, Рудольф Треурнихт"
          " and Джеймс Бейкер, three boxes",
          stood(r263),
          collections.Counter({1037: 1, 1728: 1, 1729: 1, 1730: 1, 1731: 1, 1732: 1, 1733: 1, 1734: 1,
                               1735: 1, 2315: 1, 1736: 1, 1751: 1, 2170: 1, 2171: 3}))
    check("  ..its chief's place 274: Бригадир Табаки and eight of the fill",
          stood(r274),
          collections.Counter({1038: 1, 2316: 1, 2317: 1, 2318: 1, 2319: 1, 1731: 1, 1735: 1, 2315: 1,
                               1733: 1}))
    LEVELS = {764: 18, 1024: 18, 1736: 19, 2169: 17, 2171: 18, 1749: 19, 1750: 17, 1751: 19, 2170: 20,
              1752: 19, 2315: 20, 981: 18}
    check("the levels set by hand (data/build_mob_types.py DESIGNED_LEVELS and DESIGNED_KINDS), Кленз's by"
          " the wiki, the bookkeeper's by his name, the stones' by the town's band",
          {t: mobs.stats(t).level for t in LEVELS}, LEVELS)
    check("the captains and colonels are rank and file (DESIGNED_KINDS): no hours, no boss's slot",
          {t: (world.creature_role(t), bosses.keeps_hours(t)) for t in (767, 771, 775, 1730, 2318)},
          {t: ("mob", False) for t in (767, 771, 775, 1730, 2318)})
    check("the five bosses keep the hours, at the levels of their files; the treasurers and the"
          " bookkeeper stand all day (bosses.ALL_DAY)",
          ({t: (bosses.keeps_hours(t), mobs.stats(t).level) for t in BOSSES},
           {t: (world.creature_role(t), bosses.keeps_hours(t), t in bosses.ALL_DAY) for t in TREASURERS}),
          ({777: (True, 32), 778: (True, 30), 8620: (True, 33), 1037: (True, 32), 1038: (True, 30)},
           {t: ("boss", False, True) for t in TREASURERS}))
    placed = {lid: sorted(int(r["type"]) for r in world.placed_in(lid)) for lid in (132, 168, 263)}
    check("the named men stand by their camps by hand (data/placements.json), Кленз in the Dark Mine's"
          " entrance by its file",
          (placed, stood(room(156))[1752]),
          ({132: [1750], 168: [1024, 1749], 263: [1751, 2170]}, 1))
    check("  ..and none of them, no treasurer and no box is in any ambush's band",
          sorted({t for b, _r in encounters.bands() for t in b.types}
                 & (set(NAMED) | {1760, 2168} | set(TREASURERS) | {2169, 2171})), [])
    world.substitute(0)
    check("  ..nor stands in for anyone (data/build_spawn_substitutes.py NAMED)",
          sorted((set(NAMED) | {1760, 2168}) & set(world._SUBSTITUTES.values())), [])
    files_1760 = []
    for lid in world.static_ids():
        try:
            if 1760 in {t for _c, t in world.location(lid).spawns}:
                files_1760.append(lid)
        except Exception:
            pass
    check("the second Кленз (1760) stands nowhere: no file, no row of data/placements.json, no camp's fill",
          (files_1760, [k for k, recs in world.placements().items() for r in recs if int(r["type"]) == 1760],
           [lid for lid in CAMP_PLACES if 1760 in fill[lid]]),
          ([], [], []))
    check("every row of data/placements.json can stand (rooms.placement_problems)",
          rooms.placement_problems(MT), [])
    patrols = collections.defaultdict(list)
    for key, recs in world.placements().items():
        for r in recs:
            if r.get("patrol") in (132, 168, 263):
                patrols[r["patrol"]].append((world.unpack(key), int(r["type"])))
    check("patrols ring the three camps, eight of the camp's own fighters a cell, on every walkable cell"
          " round the camp and its chief's place: the pirates' eleven (the river south of them), the"
          " outpost's eight (no chief's place), the base's twelve",
          {c: (len({cell for cell, _t in v}), len(v)) for c, v in patrols.items()},
          {132: (11, 88), 168: (8, 64), 263: (12, 96)})
    check("  ..of the faction's ranks only, no boss, treasurer, named man or box",
          {c: sorted({t for _cell, t in v} - set(range(765, 777)) - set(range(1025, 1037))
                     - set(range(1728, 1736)) - set(range(2315, 2320)))
           for c, v in patrols.items()}, {132: [], 168: [], 263: []})
    chief = {132: 133, 168: None, 263: 274}
    check("  ..each cell touching the camp or its chief's place, walkable",
          [cell for c, v in patrols.items() for cell, _t in v
           if min(max(abs(cell[0] - p[0]), abs(cell[1] - p[1]))
                  for p in [world.cell_of(c)] + ([world.cell_of(chief[c])] if chief[c] else [])) != 1
           or not world.passable(*cell)], [])
except Exception:
    import traceback
    fails.append("who stands there broke:\n" + traceback.format_exc())

# --- Абимбола's instances ---------------------------------------------------------------------
print("the instances")
try:
    check("the bandits Абимбола sends one after: bosses at 20, standing all day (bosses.ALL_DAY), no hours",
          {t: (world.creature_role(t), mobs.stats(t).level, t in bosses.ALL_DAY, bosses.keeps_hours(t))
           for t in INSTANCE_BOSSES},
          {t: ("boss", 20, True, False) for t in INSTANCE_BOSSES})
    check("  ..their men at 18, rank and file",
          {t: (world.creature_role(t), mobs.stats(t).level) for t in INSTANCE_MEN},
          {t: ("mob", 18) for t in INSTANCE_MEN})
    check("  ..and Гвала's eight crocodiles in 691 beasts at 18 (DESIGNED_KINDS), not eight bosses, no"
          " hours, not all day",
          (stood(room(691))[CROCODILE], world.creature_role(CROCODILE), mobs.stats(CROCODILE).level,
           CROCODILE in bosses.ALL_DAY, bosses.keeps_hours(CROCODILE)),
          (8, "animal", 18, False, False))
    WHO = {690: {1702: 1, 1703: 4}, 691: {1708: 1, 1706: 8}, 692: {1709: 1, 1710: 1, 1711: 1},
           693: {1718: 1, 1719: 4}, 694: {1720: 1, 1722: 1, 1723: 1, 1724: 1, 1725: 1}}
    got = {lid: stood(room(lid)) for lid in WHO}
    check("  ..each instance stands its bandit and his men, Гатера's car and the bandit's box",
          {lid: ({t: c[t] for t in WHO[lid]}, c[1693], sum(c[t] for t in range(2113, 2118)))
           for lid, c in got.items()},
          {lid: (WHO[lid], 1, 1) for lid in WHO})
except Exception:
    import traceback
    fails.append("the instances broke:\n" + traceback.format_exc())

# --- the diamond ------------------------------------------------------------------------------
print("the diamond")
try:
    check("the miners of the Dark Mine (930, 931) carry the diamond for a quest (tier «Квестовый»,"
          " data/loot_manual.json), at 0.1",
          {t: [r for r in mobs.quest_table(t) if r[0] == DIAMOND] for t in (930, 931)},
          {930: [(DIAMOND, 0.1)], 931: [(DIAMOND, 0.1)]})
    check("  ..and nobody else does, for a quest or as ordinary loot (mobs.loot_table)",
          (sorted(int(t) for t in mobs.TYPES if DIAMOND in {r[0] for r in mobs.quest_table(int(t))}),
           sorted(int(t) for t in mobs.TYPES if DIAMOND in {r[0] for r in mobs.loot_table(int(t))})),
          ([930, 931], []))
    check("  ..the miners stand on the Dark Mine's five tiers",
          [sum(stood(room(i))[t] for t in (930, 931)) for i in MINE], [2, 4, 6, 8, 11])
except Exception:
    import traceback
    fails.append("the diamond broke:\n" + traceback.format_exc())

# --- the ambushes -----------------------------------------------------------------------------
print("the ambushes")
try:
    bands = {b.camp: b for b, _r in encounters.bands()}
    check("Абу-Хамед's three camps have their bands, of the fill's fighters only",
          {c: (bands[c].lo, bands[c].hi, sorted(bands[c].types)) for c in (132, 168, 263)},
          {132: (16, 18, [765, 766, 767, 768, 769, 770, 772, 773, 774, 776]),
           168: (16, 18, [1025, 1026, 1027, 1028, 1029, 1030, 1031, 1032, 1033, 1034, 1036]),
           263: (19, 20, [1728, 1729, 1730, 1731, 1732, 1733, 1734, 1735, 2315])})

    def ambush_map(box):
        x0, x1, y0, y1 = box
        out = {}
        for x in range(x0, x1):
            for y in range(y0, y1):
                b = encounters.band_at(x + 0.5, y + 0.5)
                if b is not None:
                    out[(x, y)] = b.camp
        return out

    RINGS = {"halfa": (5930, 6030, 1690, 1775), "abri": (5845, 5910, 1820, 1885),
             "dongola": (5850, 5950, 1980, 2066), "abuhamed": (6120, 6310, 1920, 2015)}
    now = {k: ambush_map(b) for k, b in RINGS.items()}
    saved = encounters.REGIONS
    try:
        encounters.REGIONS = tuple(r for r in saved if r["town"] != "Абу-Хамед")
        encounters._BANDS = None
        was = {k: ambush_map(b) for k, b in RINGS.items()}
    finally:
        encounters.REGIONS = saved
        encounters._BANDS = None
    check("Вади-Хальфа's, Абри's and Донгола's rings are what they were without Абу-Хамед's region, cell"
          " for cell",
          {k: (len(now[k]) > 800, now[k] == was[k]) for k in ("halfa", "abri", "dongola")},
          {k: (True, True) for k in ("halfa", "abri", "dongola")})
    ring = now["abuhamed"]
    check("  ..and Абу-Хамед's wasteland, empty before, is its three camps' now",
          (len(was["abuhamed"]), len(ring) > 4000, sorted(set(ring.values()))), (0, True, [132, 168, 263]))
    check("  ..inside the box looked at", [c for c in ring if c[0] in (RINGS["abuhamed"][0],
                                                                      RINGS["abuhamed"][1] - 1)
                                           or c[1] in (RINGS["abuhamed"][2], RINGS["abuhamed"][3] - 1)],
          [])
    town = list(world.settlements()) + list(world.retired_cells())
    check("  ..never on a settlement's cell or beside one, the cut's cells counted",
          [c for c in ring if any(math.hypot(c[0] - x, c[1] - y) < 1.5 for x, y in town)], [])
    check("  ..and every cell of it within reach of its camp",
          [c for c, camp in ring.items()
           if math.hypot(c[0] - world.cell_of(camp)[0], c[1] - world.cell_of(camp)[1]) > 25], [])
    # An ambush is met only on a cell a player walks onto; the ring reaches
    # over the Nile to the south-west, where the river keeps everybody out.
    # One walk, here, instead of a search on every step.
    station_walk = test_borders.walk_from(STATION_CELL)
    reach = [c for c in ring if c in station_walk]
    off = [c for c in ring if c not in station_walk]
    far = test_borders.walk_from((6160, 1990))
    check("every cell of the ring a walk from the station reaches is on the town's bank: the cells no walk"
          " reaches are the far bank's, one land of its own with no place on it, and a single walkable cell"
          " the hills shut in (6293,1944)",
          (len(reach) > 4000, sorted(c for c in off if c not in far), len(off) > 400,
           sorted(c for c in far if c in station_walk),
           sorted(i for c, i in world.settlements().items() if c in far)),
          (True, [(6293, 1944)], True, [], []))
    check("  ..the far bank holds the cut across the river: «Ангар в джунглях» and the camp 432's cell",
          [c in far for c in ((6174, 1982), (6168, 1989))], [True, True])
except Exception:
    import traceback
    fails.append("the ambushes broke:\n" + traceback.format_exc())

# --- the objects and the people ---------------------------------------------------------------
print("the objects and the people")
try:
    check("the boxes are things, standing by the table (world.STANDING_OBJECTS), as are the quarry's stones"
          " in its four pits",
          ([world.creature_role(t) for t in (2169, 2171, 981)],
           {i: sorted(world.STANDING_OBJECTS[i]) for i in (132, 168, 263, 637, 638, 639, 640)},
           [stood(room(i))[981] for i in (637, 638, 639, 640)]),
          (["object", "object", "object"],
           {132: [2169], 168: [2171], 263: [2171], 637: [981], 638: [981], 639: [981], 640: [981]},
           [20, 16, 20, 20]))
    port = stood(room(PORT))
    check("the lottery sellers stand all year in the port (world.SEASON_KEPT)",
          (port[741], port[742], world.SEASON_KEPT.get(PORT)), (1, 1, frozenset({741, 742})))
    check("Веласкес registers trophies and keeps his stall, on the station",
          (740 in world.TROPHY_REGISTRARS, trophies.keeps_stall(740), "Веласкес" in trophies.WHERE,
           world.entity_root(740, MT[740][0]), stood(room(STATION))[740]),
          (True, True, True, world.TRADER, 1))
    check("Мортимер stands in the port by the original's file and gives the exchanges",
          (port[1188], 1188 in {t for _c, t in world.location(PORT).spawns}, quests.given_by(1188)),
          (1, True, list(range(301, 308))))
except Exception:
    import traceback
    fails.append("the objects and the people broke:\n" + traceback.format_exc())

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
    check("nobody who stands in Абу-Хамед's places shows his mobs.xml name",
          {t: sorted(w) for t, w in shown.items()}, {})
    check("  ..the files' own who would are the remainder data/orig_names_manual.json lists under"
          " \"none\", each held out of its room (data/schedule.json held_out)",
          ({t: sorted(w) for t, w in in_files.items()}, sorted(set(in_files) - REMAINDER)),
          ({7247: [126], 7339: [131], 7344: [127]}, []))
    SHOWN = {777: "Коммодор Марабу<br>Пираты Сомали", 778: "Капитан Нгоро<br>Пираты Сомали",
             8620: "Генерал Шерхан<br>Северный Альянс", 1037: "Генерал Шерхан<br>Северный Альянс",
             1038: "Бригадир Табаки<br>Северный Альянс", 764: "Казначей<br>Пираты Сомали",
             1024: "Казначей<br>Северный Альянс", 1736: "Бухгалтер<br>Северный Альянс",
             1749: "Гейнц Тейлор<br>Наемник СА", 1750: "Йохан Демперс<br>Пират",
             1751: "Рудольф Треурнихт<br>Майор", 1752: "Хорст Кленз<br>Шахтер",
             2170: "Джеймс Бейкер<br>Северный Альянс", 1422: "Перекопанный песок",
             1423: "Рэт<br>Караванщик", 740: "Веласкес<br>водитель", 728: "Роуз<br>Лекарь",
             1693: "Машина Гатеры", 1706: "Злобный крокодил", 981: "Порода"}
    check("the camps' bosses and treasurers, the named men, the chase's sand and Рэт, the driver, the"
          " healer, Гатера's car, the crocodiles and the stones show the original's rows",
          {t: names.ALL.get(t) for t in SHOWN}, SHOWN)
    MENDED = {773: "Квартмейстер<br>Пираты Сомали", 1031: "Сержант-майор<br>Северный Альянс",
              1728: "Рядовой I класса<br>Северный Альянс", 1731: "Элитный снайпер<br>Северный Альянс"}
    check("  ..the ranks' typos mended on the wire (orig_texts.NAME_TYPOS: a stray space, a Latin C and I,"
          " two words run together)",
          {t: names.ALL.get(t) for t in MENDED}, MENDED)
    RANKS = {765: "Боцман", 767: "Кондуктор", 771: "Кавторанг", 775: "Капраз", 1025: "Рекрут",
             1027: "Капрал", 1036: "Снайпер", 1730: "Подполковник", 2315: "Прототип", 2318: "Полковник"}
    check("the factions' ranks by their own blocks (8962-8973, 8980-9006)",
          {t: names.ALL.get(t, "").startswith(w) for t, w in RANKS.items()}, {t: True for t in RANKS})
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())

# --- the interiors ----------------------------------------------------------------------------
print("the interiors")
try:
    SIDES = {649: {"E": 651}, 650: {"N": 651}, 652: {"S": 651}, 653: {"W": 651},
             651: {"W": 649, "S": 650, "N": 652, "E": 653},
             637: {"N": 636, "S": 639, "W": 640, "E": 638}, 636: {"S": 637}, 639: {"N": 637},
             638: {"W": 637}, 640: {"E": 637},
             615: {}, 1014: {}, 1216: {}, 1254: {}, 1273: {}, 1295: {},
             690: {}, 691: {}, 692: {}, 693: {}, 694: {}}
    files_sides = {lid: sorted({s for s in travel.exit_sides(world.location(lid)).values()
                                if s in travel.SIDES}) for lid in SIDES}
    check("each interior's sides, as its file has them, are the table's: none left to the map",
          files_sides, {lid: sorted(v) for lid, v in SIDES.items()})
    led = {}
    for lid, want in SIDES.items():
        loc = world.location(lid)
        for side in want:
            cell = min(c for c, s in travel.exit_sides(loc).items() if s == side)
            ex = travel.plan_exit(loc, cell, *STATION_CELL)
            led[(lid, side)] = (ex.loc_id, (ex.gx, ex.gy))
    check("  ..and each side leads into the interior it names, the map cell kept",
          led, {(lid, s): (t, STATION_CELL) for lid, want in SIDES.items() for s, t in want.items()})
    check("  ..none of them opens onto the map (no_map)", [lid for lid in SIDES if not travel.no_map(lid)], [])
    check("  ..and the client is told so: a sublocation, both map buttons grey (travel.geo_id)",
          [lid for lid in SIDES if not travel.geo_id(world.location(lid), *STATION_CELL) >> 26 & 1], [])

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
    check("from the Dark Mine's entrance every tier is reached",
          sorted(set(MINE) - reached({156})), [])
    check("  ..and from the bottom tier, up, the entrance", 156 in reached({1273}), True)
    check("  ..whose cell is on the map, walked to", (world.cell_of(156), world.cell_of(156) in walked),
          ((6218, 1968), True))
    fake = SimpleNamespace(loc=world.location(636), offers_home=server.Session.offers_home)
    check("the quarry's healer Роуз (728) in its north pit registers no home: the map is out of reach there"
          " (Session.home_here), as she does on the station",
          (server.Session.offers_home(728), server.Session.home_here(fake, 728),
           server.Session.home_here(SimpleNamespace(loc=world.location(STATION),
                                                    offers_home=server.Session.offers_home), 728)),
          (True, False, True))
    WANT = {(666, "b"): 1034, (667, "b"): 1035, (668, "b"): 1036,
            (1034, "a"): 666, (1034, "b"): 1227, (1035, "a"): 667, (1035, "b"): 1228,
            (1036, "a"): 668, (1036, "b"): 1229,
            (1227, "a"): 1034, (1228, "a"): 1035, (1229, "a"): 1036,
            (156, "b"): 615, (615, "a"): 156, (615, "b"): 1014, (1014, "a"): 615, (1014, "b"): 1216,
            (1216, "a"): 1014, (1216, "b"): 1254, (1254, "a"): 1216, (1254, "b"): 1273, (1273, "a"): 1254,
            (1273, "b"): None, (156, "a"): None,
            (53, "b"): 623, (623, "a"): 53}
    got = {}
    for (lid, side) in WANT:
        rec = travel.door(lid, side)
        ok = rec and rec.get("confidence") in travel.DOOR_CONFIDENCE
        got[(lid, side)] = int(rec["target_loc_id"]) if ok else None
    check("the mines' control rooms lead to their first tiers, the tiers to each other and back; the Dark"
          " Mine's entrance down, each tier down and up, the bottom one no further; the mountain trail 53"
          " and Вади-Хальфа's 623 into each other, both ways", got, WANT)
    check("  ..the copper, saltpetre and lead mines' by the signs (high), the Dark Mine and the trail by"
          " design (medium); the door up into the entrance lands on the entrance's own cell",
          ({k: travel.door(*k).get("confidence") for k, v in WANT.items() if v},
           sorted(k for k, v in WANT.items() if v and travel.door(*k).get("own_cell"))),
          ({k: "high" if k[0] in WORKS else "medium" for k, v in WANT.items() if v},
           [(615, "a")]))
    check("  ..every room of the mines has a door the server follows",
          [lid for lid in WORKS + MINE_TOP + MINE
           if not any((travel.door(lid, s) or {}).get("confidence") in travel.DOOR_CONFIDENCE
                      for s in "ab")], [])
except Exception:
    import traceback
    fails.append("the interiors broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("abuhamed world OK")
