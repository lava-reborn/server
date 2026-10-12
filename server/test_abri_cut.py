"""The owner's cut of Абри, 2026-10-12: «Убери локации: все ремесленники по
одежде; Авиабаза ЦСЦ; улучшение сетов 10-12; слева от ремесленников по
одежде 12 есть зеленая метка, её тоже убрать; убери кланбазу Либерти».

What the cut is, each part held here (the pattern of server/test_halfa_cut.py):

  1. the places: the clothing craftsmen's quarters 453, 454, 458, 459
     (5860,1836, 5861,1836, 5860,1837, 5863,1837), the ЦСЦ's air base 427
     (5866,1836) and the clan base Liberty's entrance 328 and block post 327
     (5906,1888-1889) are off the map; the quarter 450 behind «Улучшение
     сетов 10-12» and the base's nine other files, which never had a cell,
     are out of the game with them (data/retired.json, data/settlements_
     verified.json); their cells, the set upgrade's label cell 5866,1837,
     the green mark 5862,1837, the second «Автосвалка» 5863,1836 and the
     second «Кланбаза Liberty» by Абу-Хамед (6248,1979-1980) lead into the
     wasteland; the files stay; the neighbours stay -- the ФСЦ airfield 529
     on 5865,1835 among them (the plan's decision 13);
  2. no way in: no door the server follows, no passage, side or quest way,
     no quest's ride and no quest's marker leads into one of them, none has
     a way out;
  3. the people: whoever stands only in them gives and takes no quest, and
     keeps his name in the string table; the airfield's upgraders stand on;
  4. the map's names: hidden on exactly the cut's cells and the second
     «Автосвалка»; every other name over Абри is the file's own, row for
     row, but the three lines the town's labels lose or gain (Базиль's
     exchange, Мортимер in the port market, the slums' New Year tree), the
     boss clock's and the camps' gold, and the (P) factory's;
  5. the shops' band of Абри holds no place of the cut; held out of their
     rooms for good: the Dreadnought's and the Paladin's traders 5162/5163
     in the clothing market 378, the banknote machine 2402 in the smelter
     766 and the assembly shop 1055; the New Year of 2014's 2426/2427 stand
     in the quarter 188 only in the window 'ny';
  6. the town's ground: the cut's cells are the town's still for the
     encounters (world.retired_cells), so no ambush is met on them or beside
     them;
  7. the database: whoever is in one of the cut's places, or calls one home,
     goes to the Портовый рынок 187 (5860,1835) -- once, by the run_once
     «retire-abri-cut-2026-10-12»; the journals stay. On Postgres:
     server/test_storage_pg.py.

    LAVA_RES=.../res python3 server/test_abri_cut.py
"""
import datetime
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
DB = os.path.join(tempfile.mkdtemp(), "abri_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import encounters  # noqa: E402
import events  # noqa: E402
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
with io.open(os.path.join(DATA, "schedule.json"), encoding="utf-8") as _fh:
    SCHEDULE = json.load(_fh)
ALL_RETIRED = {int(k) for k in RETIRED["places"]}
CUT_WHY = "The owner's cut of Абри, 2026-10-12"
CELLS = {453: (5860, 1836), 454: (5861, 1836), 458: (5860, 1837), 459: (5863, 1837),
         427: (5866, 1836), 328: (5906, 1888), 327: (5906, 1889)}
OFF_CELL = (450, 326, 329, 936, 937, 939, 940, 1190, 148, 610)
CUT = tuple(CELLS) + OFF_CELL
# The cells with a name or a mark and no place, wasteland as before: the set
# upgrade's label, the green mark, the second «Автосвалка», the second
# «Кланбаза Liberty» and the square below it.
LABEL_ONLY = [(5866, 1837), (5862, 1837), (5863, 1836), (6248, 1979), (6248, 1980)]
PORT, PORT_CELL = 187, (5860, 1835)
AIRFIELD, AIRFIELD_CELL = 529, (5865, 1835)
FSC_UPGRADERS = (8213, 8214)
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
    check("data/retired.json takes out the four craftsmen's quarters, the air base, the set"
          " upgraders' quarter and the clan base Liberty's eleven files, each with its why",
          sorted(cut), sorted(CUT))
    check("  ..every why quotes the order",
          [i for i, v in cut.items() if "«" not in v or not ("Убери локации" in v or "Либерти" in v
                                                            or "Авиабаза ЦСЦ" in v
                                                            or "улучшение сетов" in v
                                                            or "ремесленники" in v)], [])
    check("  ..and lists the seven cells they stood on, the town's ground still for the encounters",
          {i: c for c, i in world.retired_cells().items() if i in CUT}, CELLS)
    table = world.settlements()
    check("none of them on any cell", [c for c, i in table.items() if i in CUT], [])
    check("  ..the seven old cells nulled with their why in data/settlements_verified.json",
          {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"),
               "the owner's cut of Абри (2026-10-12" in VERIFIED["why"].get("%d,%d" % c, ""))
           for i, c in CELLS.items()}, {i: (None, True) for i in CELLS})
    leads = {c: world.location_at(*c) == world.pack(*c) for c in list(CELLS.values()) + LABEL_ONLY}
    check("the seven cells, the set upgrade's label, the green mark, the second «Автосвалка» and"
          " the second «Кланбаза Liberty» with the square below it lead into the wasteland",
          leads, {c: True for c in leads})
    check("  ..the second «Автосвалка» nulled with its why, so the dump spreads no further",
          (VERIFIED["cells"].get("5863,1836", "absent"), "автосвалки" in VERIFIED["why"].get("5863,1836", "")),
          (None, True))
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in CUT],
          ["Ab_district1", "Ab_district2", "Ab_district4", "Ab_district7", "Abri_Mi-8",
           "KB_Liberty_Enter", "KB_Liberty_Block_post", "Ab_master_01", "KB_Liberty_Block_post1",
           "Backdoor_Liberty2", "KB_Liberty_lvl2_01", "KB_Liberty_Lvl2_Transport",
           "KB_Liberty_Sorting", "KB_Liberty2_Sorting", "KB_Liberty_Bunker_glavaria_klana",
           "Clan_Base_Gold", "Clan_Base_Gold_lvl2"])
    check("the neighbours stay: the port market 187, the quarter 188, the slums 255, the dump 289"
          " and the abandoned factory 290, Хаксли's fields 261, the graveyard 368, the clothing"
          " market 378, the hippies 191, the totem 262, and the ФСЦ airfield 529",
          [table.get(c) for c in (PORT_CELL, (5861, 1835), (5862, 1835), (5863, 1835),
                                  (5864, 1835), (5862, 1836), (5864, 1836), (5865, 1836),
                                  (5860, 1838), (5864, 1838), AIRFIELD_CELL)],
          [PORT, 188, 255, 289, 290, 261, 368, 378, 191, 262, AIRFIELD])
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
    with io.open(os.path.join(DATA, "passages.json"), encoding="utf-8") as _fh:
        PASSAGES = json.load(_fh)
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
    check("no passage, side or quest way of data/passages.json leads into or out of one, none"
          " is a no_map place",
          (into, sorted({str(i) for i in CUT} & set(PASSAGES.get("no_map") or {}))), ([], []))
    GEO = {world.pack(*c) for c in list(CELLS.values()) + LABEL_ONLY}
    rows = quests.table_rows()
    named = sorted({int(r["type"]) for r in rows for key in ("loc", "finish_loc", "rew_loc")
                    if set(place_ids(r.get(key))) & GEO}
                   | {int(r["type"]) for r in rows for key in ("loc_id", "stay_in")
                      if set(place_ids(r.get(key))) & set(CUT)}
                   | {int(r["type"]) for r in rows if isinstance(r.get("way"), dict)
                      and int(r["way"].get("target_loc_id") or 0) in CUT})
    check("no quest row rides anybody there, sends him there, marks one of the cells, waits or"
          " pays there", named, [])
    check("  ..nor does any quest as the server reads it",
          sorted(t for t, q in quests.QUESTS.items()
                 if {q.loc, q.finish_loc, q.rew_loc} & GEO or set(q.stay_in) & set(CUT)), [])
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
    check("every craftsman of 453, 454, 458, 459 and the air base's people (Эван, Кондрат and"
          " the ЦСЦ's) stand nowhere but in a retired place",
          [t for t in list(range(6009, 6039)) + list(range(6054, 6069)) + list(range(6099, 6114))
           + [5117, 5118, 5119, 5120, 5121, 5122, 5123, 5124, 5261, 5668, 5670, 5671, 5672]
           if t not in only_here], [])
    check("nobody standing only in a retired place gives or takes a quest",
          {t: (quests.given_by(t), quests.taken_by(t)) for t in only_here
           if quests.given_by(t) or quests.taken_by(t)}, {})
    check("  ..and their names stay in the string table: an unknown id sends the client to the"
          " login screen", [t for t in sorted(people) if t in MT and not names.known(t)], [])
    check("Гуго Борхардт of the quarter 450 stands in Вади-Хальфа's quarter 447 still",
          5770 in standing(447), True)
    check("the ФСЦ airfield 529 stays on 5865,1835 (the plan's decision 13), its upgraders with it",
          (world.cell_of(AIRFIELD), [t for t in FSC_UPGRADERS if t in stood_in(AIRFIELD)]),
          (AIRFIELD_CELL, list(FSC_UPGRADERS)))
except Exception:
    import traceback
    fails.append("the people broke:\n" + traceback.format_exc())


# --- 4. the map's names ----------------------------------------------------------------------
print("the map's names")
try:
    RES = world.RES
    raw = open(os.path.join(RES, "database", "locations.xml"), "rb").read()
    out, _n = map_labels.apply(raw)
    BOX = (5835, 5920, 1820, 1895)

    def rows_in(doc, box):
        x0, x1, y0, y1 = box
        got = []
        for m in map_labels.ROW.finditer(doc):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            x, y = int(a["x"]), int(a["y"])
            if x0 <= x <= x1 and y0 <= y <= y1:
                got.append((x, y, html.unescape(a["text"].decode("utf-8"))))
        return got

    HIDDEN = {(5860, 1836): "Ремесленники по одежде 10 уровень",
              (5861, 1836): "Ремесленники по одежде 10 уровень",
              (5860, 1837): "Ремесленники по одежде 11 уровень",
              (5863, 1837): "Ремесленники по одежде 12 уровень",
              (5866, 1837): "Улучшение сетов 10-12[G]<BR>Казначеи ремесленников",
              (5866, 1836): "Авиабаза ЦСЦ",
              (5863, 1836): "Автосвалка",
              (5906, 1888): "Кланбаза Liberty<br>Warning No Trespassing",
              (5906, 1889): "Плешь смерти<br>Место успокоения врагов клана Liberty"}
    hidden = {(e["x"], e["y"]): e["was"] for e in LABELS if e.get("hide")
              and BOX[0] <= e["x"] <= BOX[1] and BOX[2] <= e["y"] <= BOX[3]}
    check("over Абри the names hidden are exactly the cut's and the second «Автосвалка»",
          hidden, HIDDEN)
    check("  ..and by Абу-Хамед the second «Кланбаза Liberty»",
          [(e["x"], e["y"], e["was"]) for e in LABELS if e.get("hide") and (e["x"], e["y"]) == (6248, 1979)],
          [(6248, 1979, "Кланбаза Liberty<br>Warning No Trespassing")])
    TEXTS = {(5861, 1835): "Жилой квартал Абри:<BR>Гофус - стимуляторы<br>Обучение специализации<BR>Задания",
             (5860, 1835): "Портовый Рынок Абри:<BR>Весь спектр услуг<BR>Мортимер - обмен золотых слитков<BR>",
             (5862, 1835): "Трущобы Абри: <br>Обмен золотых слитков<BR>Задания"}
    retexts = {(e["x"], e["y"]): e["text"] for e in LABELS if "text" in e
               and BOX[0] <= e["x"] <= BOX[1] and BOX[2] <= e["y"] <= BOX[3]}
    check("the quarter loses Базиль's «обмен G комплектов», the port market names Мортимер, the"
          " slums lose the New Year tree",
          {c: retexts.get(c) for c in TEXTS}, TEXTS)
    OTHERS = {(5880, 1844), (5868, 1854), (5881, 1843), (5869, 1855), (5890, 1848), (5840, 1839)}
    check("  ..the other retexts over Абри are the camps' gold and clock, the (P) factory's and the"
          " staff's: no other", sorted(set(retexts) - set(TEXTS)), sorted(OTHERS))
    want = []
    for x, y, t in rows_in(raw, BOX):
        if (x, y) in HIDDEN and t == HIDDEN[(x, y)]:
            continue
        want.append((x, y, retexts.get((x, y), t)))
    check("every other name over Абри is the file's own, row for row", rows_in(out, BOX), want)
    check("  ..of which there are dozens", len(want) > 40, True)
except Exception:
    import traceback
    fails.append("the names broke:\n" + traceback.format_exc())


# --- 5. the shops, the held out, the season -------------------------------------------------------
print("the shops and the held out")
try:
    abri = [c for c in BANDS["cities"] if c["name"] == "Абри"][0]
    check("Абри's band of shops holds no place of the cut", sorted(set(abri["places"]) & set(CUT)), [])
    check("  ..its places are the oasis, the port market, the quarter, the slums and the clothing market",
          abri["places"], [76, 187, 188, 255, 378])
    check("shop_bands reads the same: the air base is no town's", shop_bands.city(427), None)
    held = sorted((r["loc"], sorted(r["types"])) for r in SCHEDULE["held_out"]
                  if r["loc"] in (378, 766, 1055))
    check("held out for good: 5162/5163 in the clothing market 378, the banknote machine 2402 in"
          " the smelter 766 and the assembly shop 1055",
          held, [(378, [5162, 5163]), (766, [2402]), (1055, [2402])])
    check("  ..so the rooms stand them nowhere there, and the market keeps 5160, 5161, 5181",
          ([t for t in (5162, 5163) if t in stood_in(378)], 2402 in stood_in(766),
           2402 in stood_in(1055), [t for t in (5160, 5161, 5181) if t in stood_in(378)]),
          ([], False, False, [5160, 5161, 5181]))
    check("  ..while Донгола's and Абу-Хамед's clothing markets keep them",
          [sorted({5162, 5163} & standing(i)) for i in (469, 467)], [[5162, 5163], [5162, 5163]])
    owned = {t: events.table().owned.get((188, t)) for t in (2426, 2427)}
    check("the New Year of 2014's Дайсон and Канализационный люк stand in the quarter 188 by the"
          " window 'ny' alone", {t: getattr(w, "name", w) for t, w in owned.items()},
          {2426: "ny", 2427: "ny"})
    noon = lambda m, d: datetime.datetime(2026 if m > 6 else 2027, m, d, 12).timestamp()  # noqa: E731
    check("  ..open from 20 December to 15 January, shut the rest of the year",
          [events.is_open("ny", noon(m, d)) for m, d in ((12, 25), (1, 10), (10, 12), (6, 1))],
          [True, True, False, False])
    check("  ..and the room stands neither of them by itself",
          [t for t in (2426, 2427) if t in stood_in(188)], [])
    check("  ..both named, «Дайсон» and «Канализационный люк»",
          [names.ALL.get(t) for t in (2426, 2427)], ["Дайсон", "Канализационный<br>люк"])
except Exception:
    import traceback
    fails.append("the shops broke:\n" + traceback.format_exc())


# --- 6. the town's ground --------------------------------------------------------------------
print("the town's ground")
try:
    check("no ambush on the cut's seven cells, nor beside them: the town's ground still",
          [(x + dx, y + dy) for x, y in CELLS.values() for dx in (-1, 0, 1) for dy in (-1, 0, 1)
           if encounters.band_at(x + dx + 0.5, y + dy + 0.5) is not None], [])
    check("  ..every one of them a town's cell for encounters.near_town",
          [c for c in CELLS.values() if not encounters.near_town(*c)], [])
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
    check("the run_once's places are the cut's, the port market 187 its target on its cell, its"
          " name new",
          (sorted(accounts.ABRI_CUT_PLACES), accounts.ABRI_CUT_TO,
           accounts.ABRI_CUT_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                         accounts.HALFA_FSC_FIX, accounts.PREMIUM_THINGS_FIX)),
          (sorted(CUT), (PORT,) + world.cell_of(PORT), True))
    path = os.path.join(tempfile.mkdtemp(), "abri.db")
    st = accounts.Store(path)
    acc, _ = st.register("abri", "secret")
    ids = {}
    for name, loc, home in (("in427", 427, None), ("in453", 453, None), ("in459", 459, None),
                            ("in450", 450, None), ("in328", 328, None), ("in1190", 1190, None),
                            ("in610", 610, None), ("home427", 188, 427), ("home327", 255, 327),
                            ("in528", 528, None), ("in187", PORT, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5866, gy = 1836,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5866, home_gy = 1836"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in427"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.ABRI_CUT_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    moved = ("in427", "in453", "in459", "in450", "in328", "in1190", "in610")
    check("whoever was in one of the cut's places is in the port market 187, on its cell, off"
          " the map, with no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in moved}, {n: (PORT, 5860, 1835, 0, None) for n in moved})
    check("  ..a home in 427 or 327 is the port market now, the character left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home427", "home327")],
          [(PORT, 5860, 1835, 188), (PORT, 5860, 1835, 255)])
    check("  ..the one in 528 (the cut of the ФСЦ's, run long ago) and the one in 187 untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in528", "in187")], [(528, 77), (PORT, 77)])
    check("the journal is untouched", sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..and the log says so: seven moved, two homes",
          [ln for ln in lines.lines if accounts.ABRI_CUT_FIX in ln
           and "7 character(s) moved" in ln and "2 home(s) moved" in ln] != [], True)
    check("  ..nothing left to do on a second pass", accounts.relocate_abri_cut(st.db),
          dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 427 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.ABRI_CUT_FIX)), (427, True))
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
print("abri cut OK")
