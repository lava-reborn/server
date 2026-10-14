"""The owner's cut of Донгола, 2026-10-13: «и потом сделай донголу тоже» --
Донгола made the way Абри was the day before, and with it the cut of Абри's
kinds, by the decisions taken for him («делай как считаешь нужным»): the
clothing craftsmen, the set upgrade, the clothing market, the ФСЦ airfield,
the clan bases by the town; the (P) remnants, the names with no file under
them, the 33 cells «Засада».

What the cut is, each part held here (the pattern of server/test_abri_cut.py):

  1. the places: the clothing craftsmen's quarters 455, 460, 518 (5876,2013,
     5878,2014, 5878,2015), the clothing market 469 (5878,2013), the ФСЦ
     airfield 530 (5879,2011) and the clan base Delta Force's block post 382
     (5955,2032) are off the map; the set upgraders' quarter 448, Delta
     Force's eleven other files, the clan bases «Хогвартс» (HWS_, ten) and
     «Врачи без границ» (VBG_, fifteen), which never had a cell, and the copy
     1171 of the Peacekeepers' camp are out of the game with them (data/
     retired.json, data/settlements_verified.json); and the quest file 389
     «Засада», whose 33 cells are the Peacekeepers' wasteland now; their cells
     lead into the wasteland; the files stay; the neighbours stay;
  2. no way in: no door the server follows, no passage, side or quest way,
     no quest's ride and no quest's marker leads into one of them, none has a
     way out;
  3. the people: whoever stands only in them gives and takes no quest, and
     keeps his name in the string table; who stands elsewhere too stands
     there still;
  4. the map's names: hidden on exactly the cut's cells, the clan bases', the
     (P) remnants', «Памятник Воину-Освободителю», «Лагерь экспедиции» and
     «Мясники, скупка трофеев»; every other name over Донгола is the file's
     own, row for row, but the lines the town's labels lose («Обмен G
     комплектов», the quarter's ingot exchange, the pier's New Year tree, the
     masters' armour), the camps' gold and clock and the (P) of the others;
  5. the shops' band of Донгола keeps the clothing market among its places,
     as Абри's keeps 378 (nobody opens its room); held out of their rooms for
     good: the set upgraders Адольф 5106 (197) and Муаз 232 (50), Мастер Тиль
     5 and the test trader 5113 (103), Майор Свейн 6560 of Delta Force (445),
     the two of «Упавший спутник» (77), «Макисе Курису» 2176 in the prison's
     two gated blocks (618, 619), the two machine-gun masters with no row
     5110/5111 in the masters' camp 96 (the review of 2026-10-14);
  6. the town's ground: the cut's cells are the town's still for the
     encounters (world.retired_cells), so no ambush is met on them or beside
     them; the cells «Засада» are not -- the Peacekeepers' ambushes are met
     there, but beside the mountain paths;
  7. the database: whoever is in one of the cut's places, or calls one home,
     goes to the station of Донгола 49 (5877,2010) -- once, by the run_once
     «retire-dongola-cut-2026-10-13»; the journals stay. On Postgres:
     server/test_storage_pg.py.

    LAVA_RES=.../res python3 server/test_dongola_cut.py
"""
import glob
import html
import io
import json
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "dongola_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import encounters  # noqa: E402
import items  # noqa: E402
import map_cells  # noqa: E402
import map_labels  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import shop_bands  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


with io.open(os.path.join(DATA, "retired.json"), encoding="utf-8") as _fh:
    RETIRED = json.load(_fh)
with io.open(os.path.join(DATA, "settlements_verified.json"), encoding="utf-8") as _fh:
    VERIFIED = json.load(_fh)
with io.open(os.path.join(DATA, "shop_bands.json"), encoding="utf-8") as _fh:
    BANDS = json.load(_fh)
with io.open(os.path.join(DATA, "map_labels.json"), encoding="utf-8") as _fh:
    LABELS = json.load(_fh)["labels"]
with io.open(os.path.join(DATA, "map_cells.json"), encoding="utf-8") as _fh:
    CELLS_DOC = json.load(_fh)
with io.open(os.path.join(DATA, "schedule.json"), encoding="utf-8") as _fh:
    SCHEDULE = json.load(_fh)
with io.open(os.path.join(DATA, "passages.json"), encoding="utf-8") as _fh:
    PASSAGES = json.load(_fh)
ALL_RETIRED = {int(k) for k in RETIRED["places"]}
CUT_WHY = "The owner's cut of Донгола, 2026-10-13"
CELLS = {455: (5876, 2013), 460: (5878, 2014), 518: (5878, 2015), 469: (5878, 2013),
         530: (5879, 2011), 382: (5955, 2032)}
DELTA = (380, 381, 385, 386, 387, 388, 958, 959, 960, 1196)
HWS = (534, 535, 536, 537, 593, 594, 991, 992, 993, 1207)
VBG = (337, 338, 339, 342, 346, 350, 354, 358, 362, 366, 955, 956, 957, 1195)
OFF_CELL = (448,) + DELTA + HWS + VBG + (1171,)
AMBUSH, AMBUSH_FILE = 389, "Q_IV_Interception"
CUT = tuple(CELLS) + OFF_CELL + (AMBUSH,)
# The 33 cells the map names «Засада» (L235-L267), 389's until the cut.
AMBUSH_CELLS = [(5911, 2001), (5912, 2001), (5913, 2001), (5908, 2002), (5909, 2002), (5910, 2002),
                (5911, 2002), (5912, 2002), (5913, 2002), (5907, 2003), (5908, 2003), (5909, 2003),
                (5910, 2003), (5911, 2003), (5912, 2003), (5913, 2003), (5905, 2004), (5906, 2004),
                (5907, 2004), (5908, 2004), (5909, 2004), (5910, 2004), (5911, 2004), (5912, 2004),
                (5913, 2004), (5907, 2005), (5908, 2005), (5909, 2005), (5910, 2005), (5911, 2005),
                (5912, 2005), (5911, 2006), (5912, 2006)]
# The cells with a name or a square and no place, wasteland as before.
LABEL_ONLY = [(5877, 2013), (5928, 1976), (5927, 1976), (5937, 2004), (5936, 2004), (5955, 2031),
              (5955, 2030), (5956, 2030), (5912, 1993), (5885, 2035), (5873, 2008), (5876, 2004),
              (5876, 2007), (5881, 2005)]
STATION, STATION_CELL = 49, (5877, 2010)
VALLEY_AMBUSH = (6270, 1830)                    # the Nubian valley's own «Засада»
BOX = (5866, 5960, 1950, 2066)                  # x0, x1, y0, y1 round the town
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


# --- 1. the places -------------------------------------------------------------------------
print("the places")
try:
    cut = {int(k): v for k, v in RETIRED["places"].items() if v.startswith(CUT_WHY)}
    check("data/retired.json takes out the three craftsmen's quarters, the set upgraders' quarter, the"
          " clothing market, the ФСЦ airfield, the three clan bases' 35 files, the copy of the"
          " Peacekeepers' camp and the file of «Засада», each with its why",
          sorted(cut), sorted(CUT))
    check("  ..every why quotes the order and says the cut is of Абри's kinds or names its decision",
          [i for i, v in cut.items() if "«и потом сделай донголу тоже»" not in v
           or not ("Абри's kinds" in v or "decision" in v)], [])
    check("  ..and lists the six cells they stood on, the town's ground still for the encounters; the"
          " cells «Засада» are not among them",
          ({i: c for c, i in world.retired_cells().items() if i in CUT}, AMBUSH in world.retired_cells().values()),
          (CELLS, False))
    table = world.settlements()
    check("none of them on any cell", [c for c, i in table.items() if i in CUT], [])
    check("  ..the six old cells nulled with their why in data/settlements_verified.json",
          {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"),
               "the owner's cut of Донгола (2026-10-13" in VERIFIED["why"].get("%d,%d" % c, ""))
           for i, c in CELLS.items()}, {i: (None, True) for i in CELLS})
    check("  ..and the 33 cells «Засада» nulled, each saying so",
          [c for c in AMBUSH_CELLS if VERIFIED["cells"].get("%d,%d" % c, "absent") is not None
           or "«Засада»" not in VERIFIED["why"].get("%d,%d" % c, "")], [])
    leads = {c: world.location_at(*c) == world.pack(*c)
             for c in list(CELLS.values()) + LABEL_ONLY + AMBUSH_CELLS + [VALLEY_AMBUSH]}
    check("the six cells, the 33 «Засада», the names and squares with no place under them and the"
          " valley's own «Засада» (where the placer would take 389 if it were in the running) lead into"
          " the wasteland", leads, {c: True for c in leads})
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in CUT],
          ["Dn_district1", "Dn_district4", "Dn_district7", "Sets_Market_Dn", "air_point_Dn_map",
           "KB_Delta_Force_Block_Post", "Dangola_master_01", "KB_DeltaForce_Enter",
           "KB_Backdoor_Delta_Force", "KB_Delta_Force_Arena", "KB_Delta_Force_Arena2",
           "KB_Delta_Force_Arena3", "KB_Delta_Force_point_01", "KB_Delta_Force_lvl2_01",
           "KB_Delta_Force_Lvl2_Transport", "KB_Delta_Force_Sorting",
           "KB_Delta_Force_Bunker_glavaria_klana", "HWS_KB_Enter", "HWS_KB_Block_Post",
           "HWS_KB_Backdoor", "HWS_KB_point_01", "HWS_KB_point_03", "HWS_KB_point_02", "HWS_KB_lvl2_01",
           "HWS_KB_Lvl2_Transport", "HWS_KB_Sorting", "HWS_KB_Bunker_glavaria_klana",
           "VBG_KB_Block_Post", "VBG_KB_Enter", "VBG_KB_Backdoor", "VBG_KB_point_01", "VBG_KB_point_02",
           "VBG_KB_point_03", "VBG_KB_point_04", "VBG_KB_point_06", "VBG_KB_point_05",
           "KB_VBG_Desert_point_07", "VBG_KB_Lvl2_Transport", "VBG_KB_lvl2_01", "VBG_KB_Sorting",
           "VBG_KB_Bunker_glavaria_klana", "Up_Camp_00LVL_08_boss", AMBUSH_FILE])
    check("the neighbours stay: the station 49, the old market 50, the quarter 79, the masters' camps"
          " 96 and 97, the flayers 73, the black market 103, the new market 197, the port 445, the"
          " railway's end 74, the graveyard 72",
          [table.get(c) for c in (STATION_CELL, (5878, 2010), (5877, 2011), (5876, 2011), (5877, 2012),
                                  (5878, 2011), (5879, 2012), (5878, 2009), (5873, 2012), (5877, 2009),
                                  (5880, 2008))],
          [STATION, 50, 79, 96, 97, 73, 103, 197, 445, 74, 72])
    check("  ..and the mountain paths 162 and 625 round the cells «Засада»",
          [table.get(c) for c in ((5908, 2001), (5907, 2006), (5909, 2006))], [162, 625, 625])
    check("Берт Гаммер's ranges HWS_TIR_* stay in the game: copies of Вади-Хальфа's",
          [i for i in (1002, 1208, 1253, 1272, 1277, 1281) if i in ALL_RETIRED], [])
    hws_fns = sorted(i for i in world.static_ids() if world.location(i).fn.startswith(("HWS_KB", "VBG_KB",
                                                                                       "KB_VBG",
                                                                                       "KB_Delta",
                                                                                       "KB_DeltaForce",
                                                                                       "KB_Backdoor_Delta")))
    check("  ..and every file of the three clan bases is out", [i for i in hws_fns if i not in ALL_RETIRED], [])
except Exception:
    import traceback
    fails.append("the places broke:\n" + traceback.format_exc())


# --- 2. no way in --------------------------------------------------------------------------
print("no way in")
try:
    files = sorted(int(os.path.basename(p)[:-4])
                   for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")))
    followed = []
    for lid in files:
        for side in "ab":
            rec = travel.door(lid, side)
            if (rec and int(rec.get("target_loc_id") or 0) in CUT
                    and rec.get("confidence") in travel.DOOR_CONFIDENCE and lid not in ALL_RETIRED):
                followed.append((lid, side, int(rec["target_loc_id"])))
    check("no door the server follows leads into one of them from a place still in the game",
          followed, [])
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
    check("no passage, side or quest way of data/passages.json leads into or out of one, none is a"
          " no_map place",
          (into, sorted({str(i) for i in CUT} & set(PASSAGES.get("no_map") or {}))), ([], []))
    GEO = {world.pack(*c) for c in list(CELLS.values()) + LABEL_ONLY}
    rows = quests.table_rows()
    named = sorted({int(r["type"]) for r in rows for key in ("loc", "finish_loc", "rew_loc")
                    if set(place_ids(r.get(key))) & GEO}
                   | {int(r["type"]) for r in rows for key in ("loc_id", "stay_in")
                      if set(place_ids(r.get(key))) & set(CUT)}
                   | {int(r["type"]) for r in rows if isinstance(r.get("way"), dict)
                      and int(r["way"].get("target_loc_id") or 0) in CUT})
    check("no quest row rides anybody there, sends him there, marks one of the cells, waits or pays"
          " there", named, [])
    check("  ..nor does any quest as the server reads it",
          sorted(t for t, q in quests.QUESTS.items()
                 if {q.loc, q.finish_loc, q.rew_loc} & GEO or set(q.stay_in) & set(CUT)), [])
    ways = [(k, int(r.get("quest") or 0), int(r.get("target_loc_id") or 0))
            for k, recs in (PASSAGES.get("quest") or {}).items() if not k.startswith("_")
            for r in recs or ()]
    check("  ..every quest way of the table, wherever it starts, leads somewhere still in the game",
          [w for w in ways if w[2] in ALL_RETIRED], [])
    check("  ..and none of them has a quest way out", [i for i in CUT if travel.quest_ways(world.location(i))],
          [])
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
    people = {t for lid in CUT for t in standing(lid) if t}
    only_here = sorted(t for t in people
                       if not [w for w in put[t] if not (w[0] in ("file", "fill") and w[1] in ALL_RETIRED)])
    check("every craftsman of 455, 460, 518 stands nowhere but in a retired place",
          [t for t in list(range(6144, 6159)) + list(range(6189, 6204)) + list(range(6234, 6249))
           if t not in only_here], [])
    check("nobody standing only in a retired place gives or takes a quest",
          {t: (quests.given_by(t), quests.taken_by(t)) for t in only_here
           if quests.given_by(t) or quests.taken_by(t)}, {})
    check("  ..and their names stay in the string table: an unknown id sends the client to the"
          " login screen", [t for t in sorted(people) if t in MT and not names.known(t)], [])
    elsewhere = {t: sorted(w[1] for w in put[t] if w[1] not in ALL_RETIRED)
                 for t in (5161, 5162, 5163, 5181, 5767, 5770, 8213, 8214, 407, 2167)}
    # Абу-Хамед's clothing market 467, its set upgraders' quarter 449 and its
    # airfield 527 went with the owner's cut of Абу-Хамед (2026-10-14,
    # server/test_abuhamed_cut.py): the clothing market's traders stand nowhere
    # since, the treasurers and Гуго Борхардт in Вади-Хальфа's quarter 447, the
    # upgraders at Керма's airfield.
    check("who stands elsewhere too stands there still: the craftsmen's treasurers and Гуго Борхардт in"
          " Вади-Хальфа's quarter 447, the ФСЦ upgraders at Керма's airfield, Шеф Дженсен and his boxes in"
          " the camp 98; the clothing market's traders, whose other market was Абу-Хамед's 467, nowhere",
          {t: [i for i in v if i in (467, 447, 449, 527, 531, 98)] for t, v in elsewhere.items()},
          {5161: [], 5162: [], 5163: [], 5181: [], 5767: [447], 5770: [447],
           8213: [531], 8214: [531], 407: [98], 2167: [98]})
    check("  ..so none of them is a retired creature",
          [t for t in elsewhere if world.retired_creature(t)], [])
    check("Шеф Дженсен stands in one place now, the camp 98: its copy 1171 is out",
          sorted(w[1] for w in put[407] if w[1] not in ALL_RETIRED), [98])
    check("the file «Засада» stood Сержант Чугункин and a wounded soldier and nobody else, who give"
          " and take no quest and stand in no other file",
          (sorted(standing(AMBUSH)), [t for t in (5230, 5231) if t not in only_here],
           [t for t in (5230, 5231) if quests.given_by(t) or quests.taken_by(t)]),
          ([5230, 5231], [], []))
except Exception:
    import traceback
    fails.append("the people broke:\n" + traceback.format_exc())


# --- 4. the map's names ----------------------------------------------------------------------
print("the map's names")
try:
    RES = world.RES
    raw = open(os.path.join(RES, "database", "locations.xml"), "rb").read()
    out, _n = map_labels.apply(raw)

    def rows_in(doc, box):
        x0, x1, y0, y1 = box
        got = []
        for m in map_labels.ROW.finditer(doc):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            x, y = int(a["x"]), int(a["y"])
            if x0 <= x <= x1 and y0 <= y <= y1:
                got.append((x, y, html.unescape(a["text"].decode("utf-8"))))
        return got

    HIDDEN = {(5876, 2013): "Ремесленники по одежде 14 уровень",
              (5878, 2014): "Ремесленники по одежде 15 уровень",
              (5878, 2015): "Ремесленники по одежде 16 уровень",
              (5877, 2013): "Улучшение сетов 14-16[G]<BR>Казначеи ремесленников",
              (5878, 2013): "Торговцы одеждой",
              (5879, 2011): "Аэроплощадка ФСЦ",
              (5928, 1976): "Собственность клана Хогвартс:<br>ПОСТОРОННИМ СМЕРТЬ! ",
              (5937, 2004): "Собственность клана Врачи без границ:<br>ПОСТОРОННИМ СМЕРТЬ! ",
              (5955, 2032): "Собственность клана Delta Force:<br>ПОСТОРОННИМ СМЕРТЬ! ",
              (5955, 2030): "Арена №1<BR>Delta Force",
              (5956, 2030): "Арена №2<BR>Delta Force",
              (5956, 2031): "Арена №3<BR>Delta Force",
              (5912, 1993): "Песчаная Кобра",
              (5885, 2035): "Еретик Альберт",
              (5873, 2008): "Побережье",
              (5876, 2004): "Памятник Воину-Освободителю",
              (5876, 2007): "Лагерь экспедиции",
              (5881, 2005): "Мясники, скупка трофеев"}
    mine = ("The owner's cut of Донгола, 2026-10-13", "The owner's Донгола, 2026-10-13")
    hidden = {(e["x"], e["y"]): e["was"] for e in LABELS if e.get("hide")
              and e.get("why", "").startswith(mine)}
    check("the names Донгола's order hides are exactly the cut's, the clan bases', the (P) remnants' and"
          " the three with no file under them", hidden, HIDDEN)
    check("  ..each of them the file's own text on its cell, so each is hidden on the map",
          sorted(c for c, t in HIDDEN.items() if (c[0], c[1], t) not in rows_in(raw, BOX)
                 or (c[0], c[1], t) in rows_in(out, BOX)), [])
    TEXTS = {(5878, 2009): "Новый Рынок Донголы:<BR>Каменоломня<BR>Улучшение (G) Оружия<br>Лотерея<br>"
                           "Доктор Гофус - стимуляторы<br>Обмен золотых слитков<br>Лекарь",
             (5877, 2011): "Жилой квартал Донголы:<BR>Задания.",
             (5873, 2012): "Причал Донголы:<BR>Задания.",
             (5876, 2011): "Лагерь мастеров: улучшение автоматов(A,G), Пулеметов (A и G) "}
    retexts = {(e["x"], e["y"]): e["text"] for e in LABELS if "text" in e and not e.get("add")
               and BOX[0] <= e["x"] <= BOX[1] and BOX[2] <= e["y"] <= BOX[3]}
    check("the new market loses «Обмен G комплектов», the quarter its ingot exchange, the pier its New"
          " Year tree, the masters' camp its armour", {c: retexts.get(c) for c in TEXTS}, TEXTS)
    OTHERS = {(5883, 2035), (5882, 2036), (5921, 2011), (5920, 2010), (5921, 1982)}
    check("  ..the other retexts over Донгола are the camps' gold and clock and the (P) factory's: no other",
          sorted(set(retexts) - set(TEXTS)), sorted(OTHERS))
    check("  ..the camps say they are fought for gold, the chiefs' places that the chiefs come with it",
          {c: ("Сражение за золото в 14:00, 18:00 и 22:00" in retexts[c]
               or "В 14:00, 18:00 и 22:00 часто кто-то приезжает с золотом." in retexts[c])
           for c in OTHERS - {(5921, 1982)}}, {c: True for c in OTHERS - {(5921, 1982)}})
    hide_any = {(e["x"], e["y"], e["was"]) for e in LABELS if e.get("hide")}
    want = [(x, y, retexts.get((x, y), t)) for x, y, t in rows_in(raw, BOX) if (x, y, t) not in hide_any]
    ours = {i for i in world.overlay_ids() if i >= world.FIRST_NEW_ID}
    added = {(e["x"], e["y"], e["text"]) for e in LABELS if e.get("add")
             and world.settlements().get((e["x"], e["y"])) in ours}
    check("every other name over Донгола is the file's own, row for row (the places of ours aside)",
          [r for r in rows_in(out, BOX) if r not in added], want)
    check("  ..of which there are more than sixty, the 33 «Засада» among them",
          (len(want) > 60, sum(1 for _x, _y, t in want if t == "Засада")), (True, 33))
    painted = map_cells.load()
    check("the squares of the hidden names with no place under them are painted over or bare, each"
          " decided (data/map_cells.json): the set upgrade's, the clan bases' and their arenas', the"
          " monument's and the butchers'; the (P) remnants and the expedition's camp have none",
          (sorted(c for c in LABEL_ONLY if "%d,%d" % c in CELLS_DOC["cells"]),
           sorted(c for c in LABEL_ONLY if "%d,%d" % c in CELLS_DOC["bare"])),
          (sorted([(5877, 2013), (5928, 1976), (5927, 1976), (5937, 2004), (5936, 2004), (5955, 2031),
                   (5955, 2030), (5956, 2030), (5876, 2004), (5881, 2005)]),
           sorted([(5912, 1993), (5885, 2035), (5873, 2008), (5876, 2007)])))
    check("  ..the arena «№3»'s square goes as a cell of its own (5956,2031), and the six cells of the"
          " cut go by themselves, as every cell of data/retired.json",
          (sorted(c for c in [(5956, 2031)] + list(CELLS.values()) if c not in painted.cells), []),
          ([], []))
    check("  ..and the three bases' letters «База …» go with them",
          sorted(c["was"] for c in CELLS_DOC["captions"] if c["was"].startswith("База ")
                 and c["why"].startswith("The owner's cut of Донгола")),
          ["База Delta Force", "База Врачи без границ", "База Хогвартс"])
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())


# --- 5. the shops, the held out ----------------------------------------------------------------
print("the shops and the held out")
try:
    dongola = [c for c in BANDS["cities"] if c["name"] == "Донгола"][0]
    check("Донгола's band of shops keeps the clothing market among its places, as Абри's keeps 378:"
          " nobody opens its room; no other place of the cut is in it",
          (dongola["places"], sorted(set(dongola["places"]) & set(CUT))),
          ([49, 50, 79, 103, 159, 195, 197, 445, 469], [469]))
    check("shop_bands reads the same: the airfield and the clan bases are no town's",
          [shop_bands.city(i) for i in (530, 382, 448)], [None, None, None])
    HELD = {197: [5106], 50: [232], 103: [5, 5113], 445: [6560], 77: [4047, 6896], 618: [2176],
            619: [2176], 96: [5110, 5111]}
    held = {r["loc"]: sorted(r["types"]) for r in SCHEDULE["held_out"] if r["loc"] in HELD}
    check("held out for good: Адольф 5106 in the new market, Муаз 232 in the old, Мастер Тиль 5 and the"
          " test trader 5113 in the black market, Майор Свейн 6560 in the port, the two of «Упавший"
          " спутник», «Макисе Курису» 2176 in the prison's two gated blocks, the two machine-gun"
          " masters with no row 5110/5111 in the masters' camp 96", held, HELD)
    check("  ..so the rooms stand them nowhere there, while their files have them",
          ({lid: [t for t in types if t in stood_in(lid)] for lid, types in HELD.items()},
           {lid: [t for t in types if t not in standing(lid)] for lid, types in HELD.items()}),
          ({lid: [] for lid in HELD}, {lid: [] for lid in HELD}))
    check("  ..the masters' camp 96 keeps the four who upgrade there (Сафи 335, Али 345, Самир 382,"
          " Гази 385); the two held out give, take and sell nothing",
          (sorted(t for t in stood_in(96) if t in (335, 345, 382, 385)),
           [(quests.given_by(t), quests.taken_by(t), list(items.stock_for(t, 96) or ()))
            for t in (5110, 5111)]),
          ([335, 345, 382, 385], [([], [], [])] * 2))
except Exception:
    import traceback
    fails.append("the shops broke:\n" + traceback.format_exc())


# --- 6. the town's ground --------------------------------------------------------------------
print("the town's ground")
try:
    check("no ambush on the cut's six cells, nor beside them: the town's ground still",
          [(x + dx, y + dy) for x, y in CELLS.values() for dx in (-1, 0, 1) for dy in (-1, 0, 1)
           if encounters.band_at(x + dx + 0.5, y + dy + 0.5) is not None], [])
    check("  ..every one of them a town's cell for encounters.near_town",
          [c for c in CELLS.values() if not encounters.near_town(*c)], [])
    met = {c: encounters.band_at(c[0] + 0.5, c[1] + 0.5) for c in AMBUSH_CELLS}
    check("the cells «Засада» are the Peacekeepers' wasteland: an ambush of the camp 98 on each, but on"
          " the doorsteps of the mountain paths 162 and 625",
          (sorted(c for c, b in met.items() if b is None),
           sorted({b.camp for b in met.values() if b is not None})),
          (sorted(c for c in AMBUSH_CELLS if encounters.near_town(*c)), [98]))
    check("  ..and most of them are", sum(1 for b in met.values() if b is not None) >= 20, True)
except Exception:
    import traceback
    fails.append("the ground broke:\n" + traceback.format_exc())


# --- 7. the database -----------------------------------------------------------------------
print("the database")


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


try:
    check("the run_once's places are the cut's, the station 49 its target on its cell, its name new",
          (sorted(accounts.DONGOLA_CUT_PLACES), accounts.DONGOLA_CUT_TO,
           accounts.DONGOLA_CUT_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                            accounts.HALFA_FSC_FIX, accounts.ABRI_CUT_FIX,
                                            accounts.RIVER_CAMPS_FIX, accounts.ABRI_CLOTHES_FIX,
                                            accounts.RIVER_ALL_FIX, accounts.PREMIUM_THINGS_FIX)),
          (sorted(CUT), (STATION,) + world.cell_of(STATION), True))
    path = os.path.join(tempfile.mkdtemp(), "dongola.db")
    st = accounts.Store(path)
    acc, _ = st.register("dongola", "secret")
    ids = {}
    for name, loc, home in (("in469", 469, None), ("in455", 455, None), ("in518", 518, None),
                            ("in448", 448, None), ("in530", 530, None), ("in382", 382, None),
                            ("in958", 958, None), ("in534", 534, None), ("in1195", 1195, None),
                            ("in1171", 1171, None), ("in389", AMBUSH, None),
                            ("home469", 50, 469), ("home530", 197, 530), ("home389", 103, AMBUSH),
                            ("in378", 378, None), ("in49", STATION, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5878, gy = 2013,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5878, home_gy = 2013"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in469"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.DONGOLA_CUT_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    moved = ("in469", "in455", "in518", "in448", "in530", "in382", "in958", "in534", "in1195", "in1171",
             "in389")
    check("whoever was in one of the cut's places is at the station 49, on its cell, off the map, with"
          " no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in moved}, {n: (STATION, 5877, 2010, 0, None) for n in moved})
    check("  ..a home in 469, 530 or 389 is the station now, the character left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home469", "home530", "home389")],
          [(STATION, 5877, 2010, 50), (STATION, 5877, 2010, 197), (STATION, 5877, 2010, 103)])
    check("  ..the one in Абри's 378 (its own cut, run long ago) and the one at the station untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in378", "in49")], [(378, 77), (STATION, 77)])
    check("the journal is untouched", sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..and the log says so: eleven moved, three homes",
          [ln for ln in lines.lines if accounts.DONGOLA_CUT_FIX in ln
           and "11 character(s) moved" in ln and "3 home(s) moved" in ln] != [], True)
    check("  ..nothing left to do on a second pass", accounts.relocate_dongola_cut(st.db),
          dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 469 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.DONGOLA_CUT_FIX)), (469, True))
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
print("dongola cut OK")
