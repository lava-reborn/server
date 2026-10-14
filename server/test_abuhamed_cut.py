"""The owner's cut of Абу-Хамед, 2026-10-14: «сделай потом абу хамед в таком же
формате» -- Абу-Хамед made the way Абри and Донгола were, and with it the cut of
their kinds, by the decisions taken for him («делай как считаешь нужным»): the
clothing craftsmen, the set upgrade, the clothing market, the ФСЦ airfield,
the clan bases by the town and the abandoned clan base with its bunker; the
names with no file under them.

What the cut is, each part held here (the pattern of server/test_dongola_cut.py):

  1. the places: the clothing craftsmen's quarters 451, 461, 462, 463, 519
     (6184,1973, 6185,1975, 6184,1977, 6185,1976, 6185,1978), the clothing
     market 467 (6183,1974), the ФСЦ airfield 527 (6185,1977), the clan base
     СМЕРШ's yard 194 (6126,1980) and the abandoned clan base 118 (6154,1963)
     are off the map; the set upgraders' quarter 449, СМЕРШ's five other
     files, the clan bases ВЭС (fourteen files) and ZEON (seven), which never
     had a cell, and the abandoned base's bunker 609 are out of the game with
     them (data/retired.json, data/settlements_verified.json); their cells
     lead into the wasteland; the files stay; the neighbours stay;
  2. no way in: no door the server follows, no passage, side or quest way,
     no quest's ride and no quest's marker leads into one of them, none has a
     way out;
  3. the people: whoever stands only in them gives and takes no quest, and
     keeps his name in the string table; who stands elsewhere too stands
     there still; the clothing market's five traders stand nowhere since;
  4. the map's names: hidden on exactly the cut's cells, the clan bases',
     «Мясники, скупка трофеев», the clan Delta Force's warehouse and the stop
     of Инсар; every other name over Абу-Хамед is the file's own, row for row,
     but the lines the quarter and the pier lose (Юсуф's exchange, the New
     Year's tree), the camps' gold and clock and the (P) of the works; the
     squares of the names with no place, and the letters of the bases, go;
  5. the shops' band of Абу-Хамед keeps the clothing market among its
     places, as Абри's keeps 378 and Донгола's 469 (nobody opens its room);
     held out of their rooms for good: the set upgrader Ундольф 5107 (127),
     the trader with no row 7247 (126), the money box of another place 6521
     (123), the masters' twins 7339 and 7342 (131) and 7344 and 7341 (127);
     «Макисе Курису» 2176
     stands in the prison's two gated blocks (649, 650), the town's band being
     his;
  6. the town's ground: the cut's cells are the town's still for the
     encounters (world.retired_cells), so no ambush is met on them or beside
     them -- the abandoned base's lies in the ring of the pirates' camp 132;
  7. the database: whoever is in one of the cut's places, or calls one home,
     goes to the station of Абу-Хамед 126 (6182,1976) -- once, by the run_once
     «retire-abuhamed-cut-2026-10-14»; the journals stay. On Postgres:
     server/test_storage_pg.py.

    LAVA_RES=.../res python3 server/test_abuhamed_cut.py
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
DB = os.path.join(tempfile.mkdtemp(), "abuhamed_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import encounters  # noqa: E402
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
CUT_WHY = "The owner's cut of Абу-Хамед, 2026-10-14"
CELLS = {451: (6184, 1973), 461: (6185, 1975), 462: (6184, 1977), 463: (6185, 1976), 519: (6185, 1978),
         467: (6183, 1974), 527: (6185, 1977), 194: (6126, 1980), 118: (6154, 1963)}
SMERSH = (254, 521, 656, 942, 1193)
VES = (149, 333, 533, 343, 347, 351, 355, 359, 363, 367, 948, 949, 950, 1192)
ZEON = (309, 310, 318, 926, 930, 947, 1186)
OFF_CELL = (449,) + SMERSH + VES + ZEON + (609,)
CUT = tuple(CELLS) + OFF_CELL
# The cells with a name or a square and no place, wasteland as before.
LABEL_ONLY = [(6184, 1974), (6184, 1976), (6126, 1981), (6174, 1946), (6175, 1946), (6081, 1975),
              (6082, 1975), (6219, 1947), (6220, 1947), (6111, 2002), (6112, 2002), (6137, 1879),
              (6272, 1942), (6140, 1869)]
# The red square beside the outpost (6211,1985), the mark of a chief's place
# the client has no file for: it stays in the picture. It lies inside the
# light box the picture draws round the outpost, whose flat tan
# server/map_cells.py reads as two squares of its own (6210,1985 and
# 6211,1986) and protects; painted over, the outpost's own square beside it
# would move past the JPEG's rounding. The cell is wasteland all the same.
OUTPOST_CHIEF = (6211, 1985)
STATION, STATION_CELL = 126, (6182, 1976)
# x0, x1, y0, y1 round the town: the plan's frame, the Nubian valley's camp
# (6272,1840) left to the valley
BOX = (6076, 6300, 1841, 2030)
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
    check("data/retired.json takes out the five craftsmen's quarters, the set upgraders' quarter, the"
          " clothing market, the ФСЦ airfield, the three clan bases' 27 files and the abandoned clan base"
          " with its bunker, each with its why",
          sorted(cut), sorted(CUT))
    check("  ..every why quotes the order and says the cut is of Абри's and Донгола's kinds",
          [i for i, v in cut.items() if "«сделай потом абу хамед в таком же формате»" not in v
           or "Абри's and Донгола's kinds" not in v], [])
    check("  ..and lists the nine cells they stood on, the town's ground still for the encounters",
          {i: c for c, i in world.retired_cells().items() if i in CUT}, CELLS)
    table = world.settlements()
    check("none of them on any cell", [c for c, i in table.items() if i in CUT], [])
    check("  ..the nine old cells nulled with their why in data/settlements_verified.json",
          {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"),
               "the owner's cut of Абу-Хамед (2026-10-14" in VERIFIED["why"].get("%d,%d" % c, ""))
           for i, c in CELLS.items()}, {i: (None, True) for i in CELLS})
    leads = {c: world.location_at(*c) == world.pack(*c) for c in list(CELLS.values()) + LABEL_ONLY}
    check("the nine cells and the names and squares with no place under them lead into the wasteland",
          leads, {c: True for c in leads})
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in CUT],
          ["AH_district1", "AH_district4", "AH_district7", "AH_district9", "AH_district13", "Sets_Market_AH",
           "air_point_AH_map", "Clan_Base_A", "Clan_Base01", "AH_master_01", "Backdoor_Smersh",
           "KB_Smersh_Block_Post", "Clan_Base_A_lvl2", "KB_Smersh_Sorting", "KB_Smersh_Bunker_glavaria_klana",
           "VES_KB_Enter", "VES_KB_Block_Post", "VES_KB_Backdoor", "VES_KB_point_01", "VES_KB_point_02",
           "VES_KB_point_03", "VES_KB_point_04", "VES_KB_point_06", "VES_KB_point_05", "VES_KB_point_07",
           "VES_KB_Sorting", "VES_KB_Lvl2_Transport", "VES_KB_lvl2_01", "VES_KB_Bunker_glavaria_klana",
           "KB_ZEON_Entr", "Backdoor_ZEON", "KB_ZEON_Block_post", "KB_ZEON_lvl2_01", "KB_ZEON_Lvl2_Transport",
           "KB_ZEON_Sorting", "KB_ZEON_Bunker_glavaria_klana", "Clan_Base01_lvl2"])
    check("the neighbours stay: the station 126, the quarter 127, the centre 128, the road 129, the"
          " masters' camp 131, the port 446, the graveyard 71, the arena 1261",
          [table.get(c) for c in (STATION_CELL, (6183, 1975), (6183, 1976), (6184, 1975), (6183, 1977),
                                  (6182, 1977), (6180, 1973), (6182, 1973))],
          [STATION, 127, 128, 129, 131, 446, 71, 1261])
    bases = sorted(i for i in world.static_ids()
                   if world.location(i).fn.startswith(("VES_KB", "KB_ZEON", "Backdoor_ZEON", "KB_Smersh",
                                                       "Backdoor_Smersh", "Clan_Base_A", "Clan_Base01")))
    check("  ..and every file of the three clan bases and the abandoned one is out",
          ([i for i in bases if i not in ALL_RETIRED], len(bases)), ([], 29))
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
    CRAFTSMEN = (list(range(6279, 6293)) + list(range(6324, 6339)) + list(range(6369, 6384))
                 + list(range(6414, 6429)) + list(range(6459, 6474)))
    check("every craftsman of the five quarters stands nowhere but in a retired place",
          [t for t in CRAFTSMEN if t not in only_here], [])
    check("  ..and the clothing market's five traders neither: 467 was the last file of theirs",
          [t for t in (5161, 5162, 5163, 5164, 5181) if t not in only_here], [])
    check("nobody standing only in a retired place gives or takes a quest",
          {t: (quests.given_by(t), quests.taken_by(t)) for t in only_here
           if quests.given_by(t) or quests.taken_by(t)}, {})
    check("  ..and their names stay in the string table: an unknown id sends the client to the"
          " login screen", [t for t in sorted(people) if t in MT and not names.known(t)], [])
    elsewhere = {t: sorted(w[1] for w in put[t] if w[1] not in ALL_RETIRED)
                 for t in (5767, 5770, 8213, 8214, 655, 2172)}
    check("who stands elsewhere too stands there still: the craftsmen's treasurers and Гуго Борхардт in"
          " Вади-Хальфа's quarter 447, the ФСЦ upgraders at Керма's airfield, Донгола's lessor Марат in its"
          " black market 103, the bandits' chief in the prison's sewer 735",
          {t: [i for i in v if i in (447, 531, 103, 735)] for t, v in elsewhere.items()},
          {5767: [447], 5770: [447], 8213: [531], 8214: [531], 655: [103], 2172: [735]})
    check("  ..so none of them is a retired creature",
          [t for t in elsewhere if world.retired_creature(t)], [])
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

    CLAN = ("База Клана: <BR>Заброшенный бункер, который может стать домом для клана <BR>Если удастся "
            "выбить засевших в нем противников.<br>Хозяин присутствует с 21:00 до 22:00")
    HIDDEN = {(6184, 1973, "Ремесленники по одежде 17 уровень"),
              (6185, 1975, "Ремесленники по одежде 18 уровень"),
              (6184, 1977, "Ремесленники по одежде 19 уровень"),
              (6185, 1978, "Ремесленники по одежде 20 уровень"),
              (6185, 1976, "Ремесленники по одежде 20x2 уровень"),
              (6183, 1974, "Торговцы одеждой"),
              (6184, 1974, "Улучшение сетов 17-20[G]<BR>Казначеи ремесленников"),
              (6185, 1977, "Аэроплощадка ФСЦ"),
              (6184, 1976, "Мясники, скупка трофеев"),
              (6126, 1980, "Собственность клана СМЕРШ:<br>ПОСТОРОННИМ ВХОД ВОСПРЕЩЁН! "),
              (6175, 1946, "Собственность клана ВЭС:<br>ПОСТОРОННИМ ВХОД ВОСПРЕЩЁН!"),
              (6082, 1975, "Собственность клана ZEON:<br>ПОСТОРОННИМ ВХОД ВОСПРЕЩЁН!"),
              (6154, 1963, CLAN + " <BR>Захват возможен игроками 18 уровня при поддержке клана."),
              (6154, 1963, CLAN + "<br>Внимание!!! Необходимо прибывать за 15 минут до встречи с хозяином."),
              (6272, 1942, "Заброшенный склад<BR>Контролируеся группировкой Delta Force"),
              (6140, 1869, "Пустыня <br>Стоянка Инсара")}
    mine = ("The owner's cut of Абу-Хамед, 2026-10-14", "The owner's Абу-Хамед, 2026-10-14")
    hidden = {(e["x"], e["y"], e["was"]) for e in LABELS if e.get("hide")
              and e.get("why", "").startswith(mine)}
    check("the names Абу-Хамед's order hides are exactly the cut's, the clan bases' (the abandoned one's"
          " two rows), the butchers', Delta Force's warehouse and Инсар's stop", sorted(hidden), sorted(HIDDEN))
    check("  ..each of them the file's own text on its cell, so each is hidden on the map",
          sorted(c for c in HIDDEN if c not in rows_in(raw, BOX) or c in rows_in(out, BOX)), [])
    TEXTS = {(6183, 1975): "Жилой квартал Абу-Хамеда: <BR> Мастера: улучшение оружия (G)<br>Аукцион<br>"
                           "Каменоломня<br>Доктор Гофус - стимуляторы.",
             (6182, 1977): "Причал Абу-Хамеда:<BR> Аренда транспорта <BR>Лотерейщики<br>"
                           "Обмен золотых слитков",
             (6218, 1968): "Темная шахта Абу-Хамеда:<BR>Добыча алмазов для Гатеры."}
    retexts = {(e["x"], e["y"]): e["text"] for e in LABELS if "text" in e and not e.get("add")
               and BOX[0] <= e["x"] <= BOX[1] and BOX[2] <= e["y"] <= BOX[3]}
    check("the quarter loses Юсуф's exchange of the sets (G), the pier its New Year tree and its"
          " trader of amulets and souvenirs (the file's is the New Year's 724, out with the season),"
          " the Dark Mine's diamonds are Гатера's (they drop for his fare alone)",
          {c: retexts.get(c) for c in TEXTS}, TEXTS)
    pier = stood_in(446)
    check("  ..the pier's file has the New Year's souvenir seller (724), who does not stand there;"
          " Кирилл (762), who rents the transport, does",
          (724 in standing(446), 724 in pier, 762 in pier), (True, False, True))
    CAMPS = {(6160, 1975), (6161, 1973), (6210, 1986), (6273, 1953), (6274, 1952)}
    check("  ..the other retexts over Абу-Хамед are the camps' gold and clock and the (P) works': no other",
          sorted(set(retexts) - set(TEXTS)), sorted(CAMPS | {(6139, 1950)}))
    check("  ..the camps say they are fought for gold, the chiefs' places that the chiefs come with it",
          {c: ("Сражение за золото в 14:00, 18:00 и 22:00" in retexts[c]
               or "В 14:00, 18:00 и 22:00 часто кто-то приезжает с золотом." in retexts[c]) for c in CAMPS},
          {c: True for c in CAMPS})
    hide_any = {(e["x"], e["y"], e["was"]) for e in LABELS if e.get("hide")}
    want = [(x, y, retexts.get((x, y), t)) for x, y, t in rows_in(raw, BOX) if (x, y, t) not in hide_any]
    ours = {i for i in world.overlay_ids() if i >= world.FIRST_NEW_ID}
    added = {(e["x"], e["y"], e["text"]) for e in LABELS if e.get("add")
             and world.settlements().get((e["x"], e["y"])) in ours}
    check("every other name over Абу-Хамед is the file's own, row for row (the places of ours aside)",
          [r for r in rows_in(out, BOX) if r not in added], want)
    check("  ..of which there are twenty-nine", len(want), 29)
    painted = map_cells.load()
    check("the squares of the hidden names with no place under them, and of the places the client has no"
          " file for, are painted over or bare, each decided (data/map_cells.json): the set upgrade's, the"
          " butchers', the clan bases' (СМЕРШ's block post, ВЭС, ZEON, Доктор «Д», the nameless pair), the"
          " green mark's; the warehouse's and Инсар's stop have none",
          (sorted(c for c in LABEL_ONLY if "%d,%d" % c in CELLS_DOC["cells"]),
           sorted(c for c in LABEL_ONLY if "%d,%d" % c in CELLS_DOC["bare"])),
          (sorted(c for c in LABEL_ONLY if c not in ((6272, 1942), (6140, 1869))),
           [(6140, 1869), (6272, 1942)]))
    check("  ..and the nine cells of the cut go by themselves, as every cell of data/retired.json",
          sorted(c for c in CELLS.values() if c not in painted.cells), [])
    check("  ..while the outpost's second red square stays, in no list, its cell wasteland",
          ("%d,%d" % OUTPOST_CHIEF in CELLS_DOC["cells"], "%d,%d" % OUTPOST_CHIEF in CELLS_DOC["bare"],
           OUTPOST_CHIEF in painted.cells, world.location_at(*OUTPOST_CHIEF) == world.pack(*OUTPOST_CHIEF)),
          (False, False, False, True))
    check("  ..with the bases' letters: «База Смерш», «База ВЭС», «База Zeon», «Заброшенная база - бункер»,"
          " «База Доктора \"Д\"»",
          sorted(c["was"] for c in CELLS_DOC["captions"] if CUT_WHY in c["why"]),
          sorted(["База Смерш", "База ВЭС", "База Zeon", "Заброшенная база - бункер", "База Доктора \"Д\""]))
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())


# --- 5. the shops, the held out ----------------------------------------------------------------
print("the shops and the held out")
try:
    town = [c for c in BANDS["cities"] if c["name"] == "Абу-Хамед"][0]
    check("Абу-Хамед's band of shops keeps the clothing market among its places, as Абри's keeps 378 and"
          " Донгола's 469: nobody opens its room; no other place of the cut is in it",
          (town["places"], sorted(set(town["places"]) & set(CUT))),
          ([126, 127, 128, 129, 131, 177, 196, 446, 467], [467]))
    check("shop_bands reads the same: the airfield, the quarters and the clan bases are no town's",
          [shop_bands.city(i) for i in (527, 451, 449, 194, 118)], [None] * 5)
    HELD = {127: [5107, 7341, 7344], 126: [7247], 123: [6521], 131: [7339, 7342]}
    held = {}
    for r in SCHEDULE["held_out"]:
        if r["loc"] in HELD:
            held.setdefault(r["loc"], []).extend(r["types"])
    check("held out for good: Ундольф 5107 in the quarter, the station's trader with no row 7247, the money"
          " box 6521 of «Место крушения.», the masters' twins 7339 and 7342 (the camp) and 7344 and"
          " 7341 (the quarter)",
          {k: sorted(v) for k, v in held.items()}, HELD)
    check("  ..so the rooms stand them nowhere there, while their files have them",
          ({lid: [t for t in types if t in stood_in(lid)] for lid, types in HELD.items()},
           {lid: [t for t in types if t not in standing(lid)] for lid, types in HELD.items()}),
          ({lid: [] for lid in HELD}, {lid: [] for lid in HELD}))
    check("«Макисе Курису» (2176) stands at the entrances of the prison's two gated blocks, held out of"
          " Вади-Хальфа's and Донгола's: his level 20 is Абу-Хамед's band's top",
          ([2176 in stood_in(i) for i in (649, 650)], [r["loc"] for r in SCHEDULE["held_out"]
                                                         if 2176 in r["types"] and r["loc"] in (649, 650)]),
          ([True, True], []))
except Exception:
    import traceback
    fails.append("the shops broke:\n" + traceback.format_exc())


# --- 6. the town's ground --------------------------------------------------------------------
print("the town's ground")
try:
    check("no ambush on the cut's nine cells, nor beside them: the town's ground still",
          [(x + dx, y + dy) for x, y in CELLS.values() for dx in (-1, 0, 1) for dy in (-1, 0, 1)
           if encounters.band_at(x + dx + 0.5, y + dy + 0.5) is not None], [])
    check("  ..every one of them a town's cell for encounters.near_town",
          [c for c in CELLS.values() if not encounters.near_town(*c)], [])
    near = encounters.band_at(6154 + 3.5, 1963 + 3.5)
    check("  ..the abandoned base's cell lies in the pirates' ring all the same: three cells off it the"
          " camp 132's ambushes are met", getattr(near, "camp", None), 132)
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
    check("the run_once's places are the cut's, the station 126 its target on its cell, its name new",
          (sorted(accounts.ABUHAMED_CUT_PLACES), accounts.ABUHAMED_CUT_TO,
           accounts.ABUHAMED_CUT_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                             accounts.HALFA_FSC_FIX, accounts.ABRI_CUT_FIX,
                                             accounts.RIVER_CAMPS_FIX, accounts.ABRI_CLOTHES_FIX,
                                             accounts.RIVER_ALL_FIX, accounts.DONGOLA_CUT_FIX,
                                             accounts.PREMIUM_THINGS_FIX)),
          (sorted(CUT), (STATION,) + world.cell_of(STATION), True))
    path = os.path.join(tempfile.mkdtemp(), "abuhamed.db")
    st = accounts.Store(path)
    acc, _ = st.register("abuhamed", "secret")
    ids = {}
    for name, loc, home in (("in467", 467, None), ("in451", 451, None), ("in519", 519, None),
                            ("in449", 449, None), ("in527", 527, None), ("in194", 194, None),
                            ("in1193", 1193, None), ("in950", 950, None), ("in309", 309, None),
                            ("in118", 118, None), ("in609", 609, None),
                            ("home467", 127, 467), ("home527", 446, 527), ("home118", 196, 118),
                            ("in469", 469, None), ("in126", STATION, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 6183, gy = 1974,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 6183, home_gy = 1974"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in467"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.ABUHAMED_CUT_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    moved = ("in467", "in451", "in519", "in449", "in527", "in194", "in1193", "in950", "in309", "in118",
             "in609")
    check("whoever was in one of the cut's places is at the station 126, on its cell, off the map, with"
          " no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in moved}, {n: (STATION, 6182, 1976, 0, None) for n in moved})
    check("  ..a home in 467, 527 or 118 is the station now, the character left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home467", "home527", "home118")],
          [(STATION, 6182, 1976, 127), (STATION, 6182, 1976, 446), (STATION, 6182, 1976, 196)])
    check("  ..the one in Донгола's 469 (its own cut, run long ago) and the one at the station untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in469", "in126")], [(469, 77), (STATION, 77)])
    check("the journal is untouched", sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..and the log says so: eleven moved, three homes",
          [ln for ln in lines.lines if accounts.ABUHAMED_CUT_FIX in ln
           and "11 character(s) moved" in ln and "3 home(s) moved" in ln] != [], True)
    check("  ..nothing left to do on a second pass", accounts.relocate_abuhamed_cut(st.db),
          dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 467 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.ABUHAMED_CUT_FIX)), (467, True))
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
print("abuhamed cut OK")
