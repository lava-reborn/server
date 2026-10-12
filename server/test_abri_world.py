"""Абри's map and population, made ready for the town (the owner's «Делаем
Абри», 2026-10-12: «В Абри добавь мобов в лагеря и в окрестности ...
Восстанови все квесты и все имена мобов»; and «Также надо будет восстановить
локации: хижина Хаксли; автосвалки (2 штуки, непонятно зачем); хиппи в
пустыне; тотем - это пустоши»):

  * the places that opened as plain wasteland or stood empty stand on their
    cells (data/settlements_verified.json): Хаксли's fields 261 on «Хижина
    Говарда Хаксли», the car dump 289 on the first «Автосвалка» (the second,
    5863,1836, wasteland with no way in), the Тотем 262, the hippies 191,
    «Сокровища» 189, Зубери's three digs 251/252/256, the oasis of Карло
    Меони 283, the date palm 285 and Марис Дамбис 284, the chiefs' places 89
    and 90 on their camps' second cells, the saltpetre pit's mouth 204 and
    the ammunition works 206; each cell leads into its file and the file
    back to it, each is walkable (the Тотем's east exit too, a repair of
    data/terrain_repairs.json);
  * who stands there: the camps 88/92 and the chiefs' places 89/90 filled
    with their factions in their bands (data/camp_fill.json), the hippies at
    9-11, the hyenas of the fields and the totem, the dump's rats; the bosses
    keep the hours, the treasurers stand all day; Санденс Кид and Бутч
    Кэссиди stand in their camps by hand and in no ambush; the camps'
    ammunition boxes and the dracaenas of 189 stand to be broken; the dump's
    eight junk piles stand against its drawn junk; Мортимер stands in the
    port market as well; the lottery sellers stand all year; Луиджи
    registers trophies;
  * the ambushes: the wasteland round Абри's two camps is theirs, without
    the named ones, and Вади-Хальфа's ring is the same cell for cell;
  * the names: nobody who stands in an open place of Абри, or in an
    interior its doors and ways reach, shows his mobs.xml name -- the
    remainder data/orig_names_manual.json lists under "none" included --,
    and every place on a cell round the town a walk reaches is one of those
    looked at; the smelter's machines name no work of the cut diamond line;
  * the doors of the mines' tiers and of the smelter are followed (high or
    medium), each where the file's sign points, but the smelter's door on
    to the cut assembly shop;
  * the client's copy of the Тотем's file is the original's, as
    client/base.txt has it, but for its title -- whatever copy the res the
    server reads holds (the launcher installs the release's own into the
    owner's).

    LAVA_RES=.../res python3 server/test_abri_world.py
"""
import collections
import hashlib
import json
import math
import os
import re
import sys

os.environ["LAVA_BOSS_HOURS"] = "14,18,22"
os.environ["LAVA_BOSS_STAY"] = "60"
os.environ["LAVA_BOSS_CLOCK"] = "2026-10-12T12:00:00"
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bosses        # noqa: E402
import encounters    # noqa: E402
import mobs          # noqa: E402
import names         # noqa: E402
import rooms         # noqa: E402
import travel        # noqa: E402
import trophies      # noqa: E402
import world         # noqa: E402

from testkit import check, fails  # noqa: E402

MT = world.mob_types()
with open(os.path.join(ROOT, "data", "orig_names_manual.json"), encoding="utf-8") as _fh:
    REMAINDER = {int(k) for k in json.load(_fh)["none"]}

# cell -> the place it opens since 2026-10-12
CELLS = {(5862, 1836): 261, (5863, 1835): 289, (5864, 1838): 262, (5860, 1838): 191,
         (5862, 1846): 189, (5870, 1838): 251, (5865, 1859): 252, (5892, 1866): 256,
         (5867, 1844): 283, (5861, 1844): 285, (5900, 1832): 284, (5881, 1843): 89,
         (5869, 1855): 90, (5914, 1854): 204, (5890, 1848): 206}
CAMPS = {(5880, 1844): 88, (5868, 1854): 92}
SECOND_DUMP = (5863, 1836)

# The places of Абри a player can walk into (settlements in its box) and the
# interiors their doors and quest ways lead to; the island (434, 502, 513,
# 523) has no boat, and Эван's farm across the river (321, 324, 325) no way
# over it. The ФСЦ airfield 529, the clan base Blackwater's block post 317
# and the assembly shop 1055 are cut (server/test_abri_cut.py).
TOWN = [76, 187, 188, 255, 290, 368, 378]
QUEST_PLACES = [189, 191, 192, 193, 219, 220, 251, 252, 256, 261, 262, 283, 284, 285, 289, 671,
                672, 1038]
CAMP_PLACES = [88, 89, 90, 92]
WORKS = [203, 204, 205, 206, 207, 660, 661, 662, 1028, 1029, 1030, 1221, 1222, 1223, 766]
PLACES = TOWN + QUEST_PLACES + CAMP_PLACES + WORKS
BOX = (5835, 5930, 1820, 1895)                 # x0, x1, y0, y1 round the town


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
    check("the second «Автосвалка» is wasteland: the dump has one cell, no way in",
          (world.location_at(*SECOND_DUMP) == world.pack(*SECOND_DUMP),
           sorted(c for c, i in world.settlements().items() if i == 289)),
          (True, [(5863, 1835)]))
    check("every restored cell is walkable, and so is the cell east of the Тотем its file leaves"
          " by (a repair: data/terrain_repairs.json)",
          [c for c in list(CELLS) + [(5865, 1838)] if not world.passable(*c)], [])
    sys.path.insert(0, os.path.join(ROOT, "data"))
    import test_borders  # noqa: E402
    outside = test_borders.walk_from(test_borders.START)
    check("  ..and a walk from Вади-Хальфа's black market on the owner's map, as data/test_borders"
          " walks it: none of them is shut away",
          sorted(c for c in list(CELLS) + list(CAMPS) if c not in outside), [])
    check("  ..and every place on a cell round the town that walk reaches is one this suite looks"
          " at (a place left out would show its people unchecked)",
          sorted((i, c) for c, i in world.settlements().items()
                 if BOX[0] <= c[0] <= BOX[1] and BOX[2] <= c[1] <= BOX[3] and c in outside
                 and i not in PLACES), [])
    # The server reads the res it is given: the original's file says «Пустошь»,
    # and an installed client the launcher keeps carries the release's copy,
    # «Тотем» (client/files), which a res synced from it would too.
    check("the places' titles as the server reads them: the quest places «Пустошь», the Тотем's"
          " the original's «Пустошь» or the release's «Тотем»",
          ({i: world.location(i).title for i in (189, 89, 90, 284, 285)},
           world.location(262).title in ("Пустошь", "Тотем")),
          ({i: "Пустошь" for i in (189, 89, 90, 284, 285)}, True))
except Exception:
    import traceback
    fails.append("the cells broke:\n" + traceback.format_exc())

# --- who stands there -------------------------------------------------------------------------
print("who stands there")
try:
    fill = {lid: world.camp_fill(lid) for lid in (88, 89, 90, 92, 191, 261, 262, 289)}
    check("the table fills every empty slot of the camps, the chiefs' places, the hippies, the"
          " fields, the totem and the dump",
          {lid: len(v) for lid, v in fill.items()},
          {lid: sum(1 for _c, t in world.location(lid).spawns if t == 0) for lid in fill})
    BAND = {88: (8, 10), 89: (8, 10), 92: (10, 12), 90: (10, 12), 191: (9, 11), 261: (6, 9),
            262: (7, 8), 289: (8, 12)}
    check("  ..each in its band",
          {lid: [t for t in v if not BAND[lid][0] <= mobs.stats(t).level <= BAND[lid][1]]
           for lid, v in fill.items()}, {lid: [] for lid in fill})
    check("  ..the camps with their factions' own, the slave traders st_ and the flayers zd_",
          {lid: sorted({MT[t][1].split("_")[0] for t in fill[lid]}) for lid in (88, 89, 90, 92)},
          {88: ["st"], 89: ["st"], 90: ["zd"], 92: ["zd"]})
    r88, r89, r90, r92 = room(88), room(89), room(90), room(92)
    check("the slave traders' camp 88: Папаша Абу, ten of the fill, Санденс Кид, two boxes",
          stood(r88), collections.Counter({327: 1, 315: 1, 316: 1, 317: 1, 318: 1, 319: 1, 320: 1,
                                           321: 1, 323: 1, 324: 1, 590: 1, 1563: 1, 2163: 2}))
    check("  ..its chief's place 89: Надзиратель Лаки, the four of the file and nine of the fill",
          (stood(r89)[328], sum(stood(r89).values())), (1, 14))
    check("the flayers' camp 92: Элфрид, Агата's son, ten of the fill, Бутч Кэссиди, two boxes",
          stood(r92), collections.Counter({360: 1, 390: 1, 348: 1, 349: 1, 350: 1, 351: 1, 352: 1,
                                           353: 1, 355: 1, 356: 1, 357: 1, 591: 1, 1564: 1,
                                           2164: 2}))
    check("  ..its chief's place 90: Бетти and ten of the fill", (stood(r90)[361], sum(stood(r90).values())),
          (1, 11))
    check("the hippies (191): twelve, four of each kind, at 9-11",
          (stood(room(191)), sorted({mobs.stats(t).level for t in (1175, 1176, 5631)})),
          (collections.Counter({1175: 4, 1176: 4, 5631: 4}), [9, 10, 11]))
    check("Хаксли's fields (261): Хаксли, thirteen corn plants and eight hyenas, two of each of four",
          stood(room(261)), collections.Counter({5766: 1, 1682: 13, 1674: 2, 1675: 2, 1676: 2, 1677: 2}))
    check("the Тотем (262): the totem, a skull, four sick hyenas and four hungry",
          stood(room(262)), collections.Counter({1686: 1, 2101: 1, 1675: 4, 1676: 4}))
    check("the car dump (289): МакКэндлесс, thirteen rats and the eight junk piles",
          stood(room(289)), collections.Counter(dict([(2390, 1), (2405, 9), (2406, 4)]
                                                     + [(t, 1) for t in range(2367, 2375)])))
    check("«Сокровища» (189): ten crocodiles, the skull and the six dracaenas that stand to be cut",
          stood(room(189)), collections.Counter({130: 10, 2102: 1, 857: 6}))
    check("  ..the dracaenas are things, standing by the table (world.STANDING_OBJECTS), as are"
          " the camps' boxes",
          (world.creature_role(857), sorted(world.STANDING_OBJECTS[189]),
           sorted(world.STANDING_OBJECTS[88]), sorted(world.STANDING_OBJECTS[92])),
          ("object", [857], [2163], [2164]))
    LEVELS = {1175: 10, 1176: 9, 5631: 11, 1177: 12, 130: 12, 590: 10, 591: 12, 1563: 10,
              1564: 12, 2163: 9, 2164: 11, 2403: 9, 1412: 12, 1413: 12, 1414: 12}
    check("the levels set by hand (data/build_mob_types.py DESIGNED_LEVELS)",
          {t: mobs.stats(t).level for t in LEVELS}, LEVELS)
    check("the bosses keep the hours; the treasurers stand all day (bosses.ALL_DAY)",
          ({t: bosses.keeps_hours(t) for t in (327, 328, 360, 361)},
           {t: (world.creature_role(t), bosses.keeps_hours(t)) for t in (590, 591)}),
          ({t: True for t in (327, 328, 360, 361)}, {590: ("boss", False), 591: ("boss", False)}))
    check("Мортимер stands in the port market 187 too, and in the slums 255 by his file",
          (stood(room(187))[1188], stood(room(255))[1188]), (1, 1))
    check("the lottery sellers stand in the port market all year (world.SEASON_KEPT)",
          (stood(room(187))[1171], stood(room(187))[1172]), (1, 1))
    check("Луиджи registers trophies and keeps his stall",
          (1179 in world.TROPHY_REGISTRARS, trophies.keeps_stall(1179), "Луиджи" in trophies.WHERE,
           world.entity_root(1179, MT[1179][0])), (True, True, True, world.TRADER))
    check("every row of data/placements.json can stand (rooms.placement_problems)",
          rooms.placement_problems(MT), [])
    dump = world.location(289)
    piles = [r for r in world.placed_in(289)]

    def touches(loc, x, y):
        c = y * loc.width + x
        return any(mobs.hex_distance(c, o, loc.width) < 1.01 for o in loc.obstacles)
    check("the dump's eight junk piles stand by hand, each against the drawn junk, apart",
          (sorted(int(r["type"]) for r in piles), [r["cell"] for r in piles if not touches(dump, *r["cell"])],
           min(math.hypot(a["cell"][0] - b["cell"][0], a["cell"][1] - b["cell"][1])
               for a in piles for b in piles if a is not b) >= 5),
          (list(range(2367, 2375)), [], True))
except Exception:
    import traceback
    fails.append("who stands there broke:\n" + traceback.format_exc())

# --- the ambushes -----------------------------------------------------------------------------
print("the ambushes")
try:
    bands = {b.camp: b for b, _r in encounters.bands()}
    check("Абри's two camps have their bands, of the fill's fighters only",
          {c: (bands[c].lo, bands[c].hi, sorted(bands[c].types)) for c in (88, 92)},
          {88: (8, 10, [315, 316, 317, 318, 319, 320, 321, 323, 324]),
           92: (10, 12, [348, 349, 350, 351, 352, 353, 355, 356, 357])})
    check("  ..no named fighter, no treasurer, no box in any band",
          sorted({t for b in bands.values() for t in b.types} & {1563, 1564, 590, 591, 2163, 2164, 586}),
          [])

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
    now_halfa, now_abri = ambush_map(HALFA_RING), ambush_map(ABRI_RING)
    saved = encounters.REGIONS
    try:
        encounters.REGIONS = tuple(r for r in saved if r["town"] != "Абри")
        encounters._BANDS = None
        was_halfa, was_abri = ambush_map(HALFA_RING), ambush_map(ABRI_RING)
    finally:
        encounters.REGIONS = saved
        encounters._BANDS = None
    check("Вади-Хальфа's ring is what it was without Абри's region, cell for cell",
          (len(now_halfa) > 1500, now_halfa == was_halfa), (True, True))
    check("  ..and Абри's wasteland, empty before, is its two camps' now",
          (len(was_abri), len(now_abri) > 800, sorted(set(now_abri.values()))), (0, True, [88, 92]))
    town = list(world.settlements()) + list(world.retired_cells())
    check("  ..never on a settlement's cell or beside one, the cut's cells counted",
          [c for c in now_abri if any(math.hypot(c[0] - x, c[1] - y) < 1.5 for x, y in town)], [])
    check("  ..and every cell of it within reach of its camp",
          [c for c, camp in now_abri.items()
           if math.hypot(c[0] - world.cell_of(camp)[0], c[1] - world.cell_of(camp)[1]) > 25], [])
except Exception:
    import traceback
    fails.append("the ambushes broke:\n" + traceback.format_exc())

# --- the names --------------------------------------------------------------------------------
print("the names")
try:
    shown = {}
    for lid in PLACES:
        loc = world.location(lid)
        for _c, t in loc.spawns:
            if not t or t not in MT:
                continue
            if world._name_tokens(MT[t][1]) & world.EVENT_TOKENS \
                    and not world.belongs_here(t, MT[t][1], MT[t][0], True, lid):
                continue                         # a season's or the developers', nobody sees it
            if internal(t):
                shown.setdefault(t, set()).add(lid)
        for n in room(lid).npcs.values():
            if internal(n.type_id):
                shown.setdefault(n.type_id, set()).add(lid)
    check("nobody who stands in Абри's places shows his mobs.xml name, the remainder the manual"
          " file lists under \"none\" included: none of it stands here (the ФСЦ airfield's two went"
          " with 529)", {t: sorted(w) for t, w in shown.items()}, {})
    check("  ..that remainder is the six types the original has no name for, Абри's none of them",
          sorted(REMAINDER), [639, 5208, 7660, 8213, 8214, 8236])
    check("  ..the New Year of 2014's two in the quarter named too, for their season",
          [t for t in (2426, 2427) if internal(t)], [])
    check("the smelter's machines name what they do and no work of the cut diamond line"
          " (orig_texts.NAME_CUTS)",
          {t: names.ALL.get(t) for t in (2393, 2394, 2395, 2396)},
          {2393: "Выплавка свинца и латуни", 2394: "Изготовление пороха, гремучей ртути",
           2395: "Очистка гильз, изготовление капсюлей", 2396: "Пресс<br>Изготовление пуль"})
    RANKS = {315: "Проводник", 323: "Караван-Баши", 326: "Конвоир", 327: "Папаша Абу",
             328: "Надзиратель Лаки", 348: "Псих", 359: "Изверг", 590: "Казначей<br>Работорговцы",
             591: "Казначей<br>Живодеры Элфрида", 1563: "Санденс Кид", 1564: "Бутч Кэссиди"}
    check("the factions' ranks by their own block, the typo of 8904 mended (Надзиратель Лаки)",
          {t: w in names.ALL.get(t, "") for t, w in RANKS.items()}, {t: True for t in RANKS})
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())

# --- the doors --------------------------------------------------------------------------------
print("the doors")
try:
    WANT = {(660, "b"): 1028, (661, "b"): 1029, (662, "b"): 1030,
            (1028, "a"): 660, (1028, "b"): 1221, (1029, "a"): 661, (1029, "b"): 1222,
            (1030, "a"): 662, (1030, "b"): 1223,
            (1221, "a"): 1028, (1222, "a"): 1029, (1223, "a"): 1030,
            (290, "b"): 766, (766, "a"): 290, (766, "b"): None}
    got = {}
    for (lid, side) in WANT:
        rec = travel.door(lid, side)
        ok = rec and rec.get("confidence") in travel.DOOR_CONFIDENCE
        got[(lid, side)] = int(rec["target_loc_id"]) if ok else None
    check("the mines' control rooms lead to their first tiers, the tiers to each other and back,"
          " the abandoned factory down to the smelter and the smelter back up, every door followed;"
          " the smelter's door on to the assembly shop 1055 none, the shop being cut",
          got, WANT)
    WANT = {k: v for k, v in WANT.items() if v is not None}
    got = {k: v for k, v in got.items() if v is not None}
    check("  ..each room's doors lead between the rooms of its own mine or works and nowhere else",
          sorted((lid, side) for (lid, side), t in got.items()
                 if {lid, t} - set(WORKS + [290])), [])
except Exception:
    import traceback
    fails.append("the doors broke:\n" + traceback.format_exc())

# --- the Тотем's title ------------------------------------------------------------------------
print("the Тотем's title")
try:
    # Held to the original's own bytes, as client/base.txt has them: the res
    # the server reads may be an installed client, which the launcher gives
    # the release's copy of this very file.
    REL = "locations/static/262.xml"
    base = {}
    with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3 and parts[2] == REL:
                base[REL] = (parts[0], int(parts[1]))
    with open(os.path.join(ROOT, "client", "files", *REL.split("/")), "rb") as fh:
        ours = fh.read()
    back = ours.replace('title="Тотем"'.encode(), 'title="Пустошь"'.encode(), 1)
    check("the client's copy of Q_Abri_Totem is the original's (client/base.txt) but for its title",
          ((hashlib.sha256(back).hexdigest(), len(back)), len(re.findall(rb'title="', ours)),
           'title="Тотем"'.encode() in ours),
          (base[REL], 1, True))
    with open(world.path_for(262), "rb") as fh:
        served = fh.read()
    check("  ..and the server's file is one of the two: the original's, or the release's copy",
          served in (back, ours), True)
except Exception:
    import traceback
    fails.append("the Тотем's title broke:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("abri world OK")
