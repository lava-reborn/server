"""The owner's cut of Вади-Хальфа, 2026-10-09: «убери из хальфы следующие
локации: торговцы одеждой, улучшение сетов 6-8, ремесленники по одежде 6, 7
и 8, а также кланбазу KKND».

What the cut is, each part held here:

  1. the places: the clothing market 468 (5969,1729) and the craftsmen's
     quarters 452, 456, 457 (5969,1731, 5969,1732, 5970,1732) are off the
     map, their cells and the set upgrade's label cell 5969,1730 lead into
     the wasteland, and the KKND clan base's six files (297, 383, 384, 938,
     961, 1189), which never had a cell, are out of the game with them --
     data/retired.json, data/settlements_verified.json; nothing else moved
     (data/test_retired_places.py runs the placer itself);
  2. no way in: no door the server follows, no passage, no side, no quest
     way and no quest's ride leads into one of them;
  3. the people: whoever stands in them stands nowhere else -- every place
     that could put one down is one of the cut's or another retired one --
     but the traders 5160, 5161, 5181 of the other towns' markets and the
     mobs 5316/5317 of Le_Mon; nobody of them gives or takes a quest, and
     their names stay in the string table;
  4. the quests: the talks about the set upgrade's window (238, 239) and the
     clothing craftsmen's rows (11000-11407) are OFF, each with its why; no
     quest anybody gives or takes speaks of a place or service of the cut;
  5. the rest of the town as it was: Причал on its cell and «В Хальфу!»
     (43) landing there, the black market's and the Magrib base's clothing
     stalls, Генри's, Генри ст's and Тиль's other quests; and its streets
     as safe: the cut's cells still the town's for the encounters
     (world.retired_cells), so the wasteland around holds exactly the
     ambush cells it held before;
  6. the clans: nothing of a clan stands on a place -- the tables have no
     column for one -- so a clan named KKND is a clan like any other;
  7. the database: whoever is in one of the cut's places, or calls one
     home, goes to Причал, and its quests leave the journals -- once, by
     the run_once «retire-halfa-cut-2026-10-09»; the history, the ledger,
     the bags and the clans stay as they are. On Postgres:
     server/test_storage_pg.py;
  8. the ФСЦ, the owner's word of 2026-10-10 («убери фсц тоже»): the FSC
     airfield 528 (5970,1727) and the FSC base «НИЛ-1» 522 (5942,1723)
     off the map the same way -- no way in or out through them, nobody
     of theirs retired (the upgraders 8213/8214 stand in four other
     towns' airfields, the base stands nobody), no quest tied to them, no
     ambush opened, and the run_once «retire-halfa-fsc-2026-10-10» sending
     whoever is in one, or calls one home, to Причал.

The names over the map are test_map_labels'; the windows and the rows in
detail test_halfa_setcraft's.

    LAVA_RES=.../lava/res python3 server/test_halfa_cut.py
"""
import glob
import io
import json
import logging
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "halfa_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import encounters  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import setcraft  # noqa: E402
import sets  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


with io.open(os.path.join(DATA, "retired.json"), encoding="utf-8") as _fh:
    RETIRED = json.load(_fh)
with io.open(os.path.join(DATA, "settlements_verified.json"), encoding="utf-8") as _fh:
    VERIFIED = json.load(_fh)
ALL_RETIRED = {int(k) for k in RETIRED["places"]}
CUT_WHY = "The owner's cut of Вади-Хальфа, 2026-10-09"
CELLS = {468: (5969, 1729), 452: (5969, 1731), 456: (5969, 1732), 457: (5970, 1732)}
KKND = (297, 383, 384, 938, 961, 1189)
CUT = tuple(CELLS) + KKND
SET_UPGRADE_CELL, KKND_CELL = (5969, 1730), (5984, 1759)
PRICHAL = 41
MT = world.mob_types()


def standing(loc_id):
    return {t for _cell, t in world.location(loc_id).spawns}


# --- 1. the places -------------------------------------------------------------------------
print("the places")
try:
    cut = {int(k): v for k, v in RETIRED["places"].items() if v.startswith(CUT_WHY)}
    check("data/retired.json takes out the market, the three quarters and the KKND base's six"
          " files, each with its why", sorted(cut), sorted(CUT))
    check("  ..every why quotes the order",
          [i for i, v in cut.items() if "убери из хальфы" not in v and "кланбазу KKND" not in v
           and "with the base 297" not in v], [])
    table = world.settlements()
    check("none of them on any cell",
          [c for c, i in table.items() if i in CUT], [])
    check("  ..the four old cells nulled with their why in data/settlements_verified.json",
          {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"),
               "the owner's cut of Вади-Хальфа (2026-10-09" in VERIFIED["why"].get("%d,%d" % c, ""))
           for i, c in CELLS.items()}, {i: (None, True) for i in CELLS})
    leads = {c: world.location_at(*c) == world.pack(*c)
             for c in list(CELLS.values()) + [SET_UPGRADE_CELL, KKND_CELL]}
    check("the four cells, the set upgrade's label cell and the KKND label's lead into the"
          " wasteland", leads, {c: True for c in leads})
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in CUT],
          ["Sets_Market_WH", "WH_district1", "WH_district4", "WH_district7", "KB_KKND_Enter_2",
           "KB_KKND_Block_Post", "KB_Backdoor_KKND", "KB_KKND_Sorting", "KB_KKND_lvl2_01",
           "KB_KKND_Bunker_glavaria_klana"])
    check("the neighbours stay: Причал, the masters' camps 94 and 95, the arena 78, the black"
          " market 102, the quest places 43 and 108, the walled quarter 447, the old and the new"
          " market, the valley's Arena 167",
          [table.get(c) for c in ((5965, 1728), (5968, 1728), (5969, 1728), (5970, 1729),
                                  (5970, 1730), (5969, 1733), (5971, 1731), (5968, 1719),
                                  (5968, 1727), (5967, 1728), (6270, 1831))],
          [PRICHAL, 94, 95, 78, 102, 43, 108, 447, 35, 104, 167])
except Exception:
    import traceback
    fails.append("the places broke:\n" + traceback.format_exc())


# --- 2. no way in --------------------------------------------------------------------------
print("no way in")
try:
    files = sorted(int(os.path.basename(p)[:-4])
                   for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")))
    followed, any_door = [], []
    for lid in files:
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and int(rec.get("target_loc_id") or 0) in CUT:
                any_door.append((lid, side, int(rec["target_loc_id"]), rec.get("confidence")))
                if rec.get("confidence") in travel.DOOR_CONFIDENCE:
                    followed.append((lid, side))
    check("no door the server follows leads into one of them", followed, [])
    check("  ..the only doors there are at all are the KKND base's own, low, from inside it",
          sorted(any_door), [(938, "a", 297, "low"), (961, "a", 297, "low")])
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
                if isinstance(rec, dict) and int(rec.get("target_loc_id") or 0) in CUT:
                    into.append((section, key))
    check("no passage, side or quest way of data/passages.json leads into one, none is a"
          " no_map place", (into, sorted(set(map(str, CUT)) & set(PASSAGES.get("no_map") or {}))),
          ([], []))
    rides = [q["type"] for q in quests.table_rows()
             if isinstance(q.get("way"), dict) and int(q["way"].get("target_loc_id") or 0) in CUT]
    check("  ..nor any quest's ride", rides, [])
    check("  ..and none has a quest way out either, as a place with a way would",
          [i for i in CUT if travel.quest_ways(world.location(i))], [])
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
    for t in list(put):
        stand_in = world.substitute(t)
        if stand_in is not None:
            put.setdefault(stand_in, set()).add(("stand-in", t))
    people = {t for lid in CUT for t in standing(lid) if t}
    elsewhere = {t: sorted(w for w in put[t]
                           if not (w[0] in ("file", "fill") and w[1] in ALL_RETIRED))
                 for t in people}
    only_here = sorted(t for t, w in elsewhere.items() if not w)
    check("the traders 5158 (Беженец to Магриб) and 5159 (Налетчик, Пустынник) and every"
          " craftsman of 452, 456, 457 stand nowhere but in a retired place",
          sorted({5158, 5159} | set(range(5783, 5798)) | set(range(5828, 5843))
                 | set(range(5873, 5888))) == sorted(
              t for t in only_here if t in {5158, 5159} or 5783 <= t <= 5887), True)
    check("  ..so does the KKND bunker's people, its banker, medic, traders and auctioneer",
          [t for t in (5082, 5319, 5320, 5322, 5323, 5343, 5344, 5345, 5346, 5360, 5363)
           if t not in only_here], [])
    check("  ..the ones that stand elsewhere too: the set traders 5160, 5161 and the miner's"
          " clothes 5181 in the markets of Абри, Абу-Хамед and Донгола, KKND's mobs in Le_Mon",
          {t: elsewhere[t] for t in (5160, 5161, 5181, 5316, 5317)},
          {5160: [("file", 378)], 5161: [("file", 378), ("file", 467), ("file", 469)],
           5181: [("file", 378), ("file", 467), ("file", 469)],
           5316: [("file", 474), ("file", 979)], 5317: [("file", 474), ("file", 979)]})
    check("nobody standing only in a retired place gives or takes a quest",
          {t: (quests.given_by(t), quests.taken_by(t)) for t in only_here
           if quests.given_by(t) or quests.taken_by(t)}, {})
    check("  ..and their names stay in the string table: an unknown id sends the client to the"
          " login screen", [t for t in sorted(people) if t in MT and not names.known(t)], [])
except Exception:
    import traceback
    fails.append("the people broke:\n" + traceback.format_exc())


# --- 4. the quests -------------------------------------------------------------------------
print("the quests")
try:
    rows = {int(r["type"]): r for r in quests.table_rows()}
    check("the talks about the set upgrade's window are OFF, each saying whom it named and why",
          [(quests.get(t).give, quests.get(t).take, rows[t]["why"].split(" since ")[0],
            "убери из хальфы" in rows[t]["why"]) for t in (238, 239)],
          [([], [], "OFF (give/take [], was [93, 5104])", True),
           ([], [], "OFF (give/take [], was [5104])", True)])
    craft = [t for t in rows if t in setcraft.TYPE_RANGE]
    check("the clothing craftsmen's 408 rows (11000-11407) OFF, each with its why",
          (len(craft), min(craft), max(craft),
           [t for t in craft if quests.get(t).give or quests.get(t).take
            or not rows[t]["why"].startswith("OFF (give/take [], was [")]),
          (408, 11000, 11407, []))
    check("  ..and the slice that makes them says why, as it does for the windows",
          (bool(setcraft.off(setcraft.SLICES["Вади-Хальфа"], "rows")),
           bool(setcraft.off(setcraft.SLICES["Вади-Хальфа"], "window"))), (True, True))
    SPOKEN = re.compile(r"Торговц\w* одежд|Вещев\w* рын|Ремесленник\w* по одежде|"
                        r"казначе\w* ремесленник|KKND|Улучшени\w* сет|Обмен G компл|"
                        r"старые комплекты|mod10 на mod05", re.IGNORECASE)
    spoken = sorted(t for t, q in quests.QUESTS.items()
                    if (q.give or q.take) and any(s and SPOKEN.search(s) for s in q.texts))
    check("no quest anybody gives or takes speaks of the clothing market, the clothing"
          " craftsmen or their treasurers, the set upgrade, the exchange or KKND", spoken, [])
    check("  ..while the switched-off ones did",
          sorted(t for t in (238, 239, 11000)
                 if any(s and SPOKEN.search(s) for s in quests.get(t).texts)),
          [238, 239, 11000])
    check("the cheques and the reworked pieces keep their names: a player who holds one holds"
          " a thing the client can show",
          [t for t in list(setcraft.CHEQUES.values()) + [c[3] for c in setcraft.CHAINS.values()]
           if not names.known(items.STRING_ID_OFFSET + t)], [])
except Exception:
    import traceback
    fails.append("the quests broke:\n" + traceback.format_exc())


# --- 5. the rest of the town ---------------------------------------------------------------
print("the rest of the town")
try:
    q43 = quests.get(43)
    check("«В Хальфу!» (43) still given and taken by Демир and lands on Причал, on its cell",
          (q43.give, q43.take, travel.is_quest_way(43), world.cell_of(PRICHAL)),
          ([5193], [5193], True, (5965, 1728)))
    check("the black market keeps Ваккас, Хамис and Тиль, the Magrib base 650, the markets"
          " their Генри", ({1204, 1205, 5} <= standing(102), 650 in standing(52),
                          93 in standing(104), 5104 in standing(35)), (True, True, True, True))
    check("  ..whose stalls still sell the ladder's Колонист and Странник (Ваккас), Магриб (G)"
          " and Налетчик (Хамис), Магриб (650)",
          {t: sorted({sets.SETS[sets.set_of(i)]["name"] for i in items.stock_for(t)
                      if sets.set_of(i) in sets.SETS}) for t in (1204, 1205, 650)},
          {1204: ["Колонист", "Странник", "Странник (G)"],
           1205: ["Магриб (G)", "Налетчик", "Налетчик (G)"], 650: ["Магриб"]})
    check("Генри, Генри ст and Тиль keep their other quests",
          (sorted({119, 132} - set(quests.given_by(93))),
           sorted({105, 119, 132} - set(quests.given_by(5104))), 104 in quests.taken_by(5104),
           sorted({4, 366, 1829, 1895, 1971, 2128, 142, 146, 157} - set(quests.given_by(5))),
           sorted({141, 156} - set(quests.taken_by(5)))),
          ([], [], True, [], []))
    check("the set upgrade's window is off by the type: Тиль stands in Донгола's black market"
          " 103 too, open to walkers, and his window is empty there as well -- no set upgrade"
          " anywhere (a decision: keeping Донгола's would need a window by the room)",
          (5 in standing(103), world.cell_of(103) is not None, setcraft.window(5)["in_types"]),
          (True, True, []))
except Exception:
    import traceback
    fails.append("the rest of the town broke:\n" + traceback.format_exc())

# The town's streets: a cell beside a settlement holds no ambush
# (encounters.near_town), and the cut's cells, wasteland now, still count
# (world.retired_cells) -- left as plain wasteland they opened three cells
# inside the town to the camps' packs, on the walks from Причал to «Генри
# Мл.» 43, the crates 108 and the prison yard 176.
print("the town's streets")
try:
    RING = [(x, y) for x in range(5930, 6030) for y in range(1690, 1775)]
    OPENED = {(5968, 1730): (80, 0, 2), (5968, 1731): (80, 0, 2), (5971, 1733): (84, 4, 6)}

    def ambush_cells():
        out = {}
        for x, y in RING:
            band = encounters.band_at(x + 0.5, y + 0.5)
            if band is not None:
                out[(x, y)] = (band.camp, band.lo, band.hi)
        return out

    check("the cut's four cells are the town's ground still, with the (P) camp 124's",
          sorted(c for c, i in world.retired_cells().items() if i in CELLS or i == 124),
          sorted(list(CELLS.values()) + [(5968, 1726)]))
    now_cells = ambush_cells()
    check("no ambush on the doorsteps the cut left: 5968,1730, 5968,1731, 5971,1733",
          [encounters.band_at(x + 0.5, y + 0.5) for x, y in sorted(OPENED)], [None] * 3)
    saved = (world._SETTLEMENTS, world._RETIRED_CELLS)
    try:
        before = dict(saved[0])
        before.update({c: i for i, c in CELLS.items()})
        world._SETTLEMENTS = before
        world._RETIRED_CELLS = {c: i for c, i in saved[1].items() if i not in CELLS}
        was_cells = ambush_cells()
        world._SETTLEMENTS = saved[0]
        bare_cells = ambush_cells()
    finally:
        world._SETTLEMENTS, world._RETIRED_CELLS = saved
    check("  ..the wasteland around the town holds exactly the ambush cells it held with the"
          " market and the three quarters on the map", (len(now_cells) > 1500, now_cells == was_cells),
          (True, True))
    check("  ..which the cut's cells, counted as plain wasteland, would open by those three",
          {c: v for c, v in bare_cells.items() if was_cells.get(c) != v}, OPENED)
except Exception:
    import traceback
    fails.append("the town's streets broke:\n" + traceback.format_exc())


# --- 6. the clans --------------------------------------------------------------------------
print("the clans")
try:
    st = accounts.Store(DB)
    cols = {t: st.db.columns(t) for t in ("clans", "clan_members", "clan_relations",
                                          "clan_ledger")}
    st.close()
    check("no clan table has a column for a place, a base or a cell",
          {t: [c for c in cs if re.search(r"loc|base|gx|gy|cell|place|territ", c)]
           for t, cs in cols.items()}, {t: [] for t in cols})
    with io.open(os.path.join(HERE, "clans.py"), encoding="utf-8") as _fh:
        clans_src = _fh.read()
    check("  ..and the clans' code names no KKND and no base file",
          [w for w in ("KKND", "KB_", "297", "1189") if w in clans_src], [])
except Exception:
    import traceback
    fails.append("the clans broke:\n" + traceback.format_exc())


# --- 7. the database -----------------------------------------------------------------------
print("the database")


class Lines(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


try:
    check("the run_once's places are the cut's, its Причал 41's own cell, the name new",
          (sorted(accounts.HALFA_CUT_PLACES), accounts.RETIRED_PLACES_TO,
           accounts.HALFA_CUT_FIX not in (accounts.RETIRED_PLACES_FIX,
                                          accounts.PREMIUM_THINGS_FIX)),
          (sorted(CUT), (PRICHAL,) + world.cell_of(PRICHAL), True))
    check("  ..its quests: 238, 239 and Вади-Хальфа's block of the set craft",
          (accounts.HALFA_CUT_QUESTS, accounts.HALFA_CUT_ROWS),
          ((238, 239), (setcraft.SLICES["Вади-Хальфа"]["types"]["rework"],
                        setcraft.SLICES["Вади-Хальфа"]["types"]["end"])))
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    st = accounts.Store(path)
    acc, _ = st.register("old", "secret")
    ids = {}
    for name, loc, home in (("in468", 468, None), ("in452", 452, None), ("in456", 456, None),
                            ("in457", 457, None), ("in297", 297, None), ("in383", 383, None),
                            ("in384", 384, None), ("in938", 938, None), ("in961", 961, None),
                            ("in1189", 1189, None), ("home468", 36, 468),
                            ("home1189", 102, 1189), ("in447", 447, None),
                            ("pier", PRICHAL, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5969, gy = 1729,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5969, home_gy = 1729"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["pier"]
    for t in (238, 239, 11000, 11407, 11499, 11500, 119, 10120):
        st.take_quest(keeper, t, {}, True)
    done = st.take_quest(keeper, 239, {}, True)
    st.finish_quest(done, keeper, 239)
    mod = setcraft.CHAINS[next(iter(setcraft.CHAINS))][3]
    cheque = setcraft.CHEQUES[(6, "G")]
    for t in (mod, cheque):
        st.create_item(keeper, t, items.root_of(t))
    st.db.execute("INSERT INTO clans (name, name_key, descr, head, created_at)"
                  " VALUES ('KKND', 'kknd', '', ?, 1)", (keeper,))
    ledger_before = st.db.execute("SELECT COUNT(*) AS c FROM money_ledger").fetchone()["c"]
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.HALFA_CUT_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    check("whoever was in one of the cut's ten places is at Причал, on its cell, off the map,"
          " with no cell of the old file",
          {n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in chars.items()
           if n.startswith("in") and n != "in447"},
          {n: (PRICHAL, 5965, 1728, 0, None) for n in chars
           if n.startswith("in") and n != "in447"})
    check("  ..a home in 468 or 1189 is Причал now, the character himself left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home468", "home1189")],
          [(PRICHAL, 5965, 1728, 36), (PRICHAL, 5965, 1728, 102)])
    check("  ..the one in 447 (the cut of (P)'s, run long ago) and the one at Причал untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in447", "pier")],
          [(447, 77), (PRICHAL, 77)])
    check("the journal loses 238, 239 and the block 11000-11499, keeps 119, 10120 and 11500",
          sorted(r["type"] for r in st.quests(keeper)), [119, 10120, 11500])
    check("  ..the history keeps what was handed in, the ledger and the bag what they had,"
          " the clan KKND is a clan as before",
          (st.quest_done(keeper, 239),
           st.db.execute("SELECT COUNT(*) AS c FROM money_ledger").fetchone()["c"] == ledger_before,
           sorted(r["type_id"] for r in st.items_of(keeper)) == sorted([mod, cheque]),
           [r["name"] for r in st.db.execute("SELECT name FROM clans")]),
          (True, True, True, ["KKND"]))
    check("  ..and the log says so: ten moved, two homes, five journal rows",
          [ln for ln in lines.lines if accounts.HALFA_CUT_FIX in ln
           and "10 character(s) moved" in ln and "2 home(s) moved" in ln
           and "5 quest(s) out of the journals" in ln] != [], True)
    check("  ..the counts as the log has them, nothing left to do",
          accounts.relocate_halfa_cut(st.db), dict(moved=0, homes=0, journal=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 468 WHERE id = ?", (keeper,))
    st.db.commit()
    st.take_quest(keeper, 238, {}, True)
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], 238 in [r["type"] for r in st.quests(keeper)],
           accounts.ran(st.db, accounts.HALFA_CUT_FIX)), (468, True, True))
    st.close()
except Exception:
    import traceback
    fails.append("the database broke:\n" + traceback.format_exc())


# --- 8. the ФСЦ ----------------------------------------------------------------------------
# The owner's word of 2026-10-10, after this cut: «убери фсц тоже». The FSC
# airfield 528 (air_point_WH_map, 5970,1727, the map's blue square with a
# white «!» beside the old market) and the FSC base «НИЛ-1» 522
# (FVAviaBazaNil_WH, 5942,1723, across the river by the resistance camp 429)
# are off the map as the cut's places are; the other towns' airfields and
# bases НИЛ-2..4 stay. Its own why, so section 1's selection by CUT_WHY
# still holds the cut of 2026-10-09 alone.
print("the ФСЦ")
FSC_WHY = "The owner's cut of Вади-Хальфа's ФСЦ, 2026-10-10"
FSC = {528: (5970, 1727), 522: (5942, 1723)}
FSC_UPGRADERS = (8213, 8214)                     # FSC_U_000001/2, art 118
FSC_PILOTS = (7921, 8210, 8211, 8212)            # ADMIN_Q_000042, 000049-51
NIL1_TYPES = (7529, 8621, 8622, 8624, 8625, 8626, 8635, 8636, 8687)
OTHER_AIRFIELDS = (527, 529, 530, 531)           # Абу-Хамед, Абри, Донгола, Керма: on cells
CSC_PEOPLE = {41: (5685, 5686), 429: (5694, 5695), 35: (2276,)}


def stood_in(loc_id):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    return sorted({n.type_id for n in room.npcs.values()})


def place_ids(v):
    """A quest row's place field (one id, or a list of them) as a list."""
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v if str(x).lstrip("-").isdigit()]
    return [int(v)] if str(v).lstrip("-").isdigit() else []


try:
    fsc = {int(k): v for k, v in RETIRED["places"].items() if v.startswith(FSC_WHY)}
    check("data/retired.json takes out the airfield 528 and the base «НИЛ-1» 522, each with its"
          " why quoting the order", {i: "убери фсц тоже" in v for i, v in fsc.items()},
          {528: True, 522: True})
    check("  ..and lists their cells, the town's ground still for the encounters",
          {i: c for c, i in world.retired_cells().items() if i in FSC}, FSC)
    table = world.settlements()
    check("  ..on no cell of the table, both old cells nulled with their why",
          ([c for c, i in table.items() if i in FSC],
           {i: (VERIFIED["cells"].get("%d,%d" % c, "absent"),
                "убери фсц тоже" in VERIFIED["why"].get("%d,%d" % c, ""))
            for i, c in FSC.items()}),
          ([], {i: (None, True) for i in FSC}))
    check("  ..both cells lead into the wasteland",
          {c: world.location_at(*c) == world.pack(*c) for c in FSC.values()},
          {c: True for c in FSC.values()})
    check("  ..the files stay, so a character saved inside still loads",
          [world.location(i).fn for i in FSC], ["air_point_WH_map", "FVAviaBazaNil_WH"])
    check("the neighbours stay: the quarter 36, the masters' camp 95, the arena 59 and the dump 100"
          " around the airfield; the resistance camp 429 and the dig 433 by the base",
          [table.get(c) for c in ((5969, 1727), (5969, 1728), (5970, 1728), (5971, 1727),
                                  (5943, 1723), (5943, 1722))],
          [36, 95, 59, 100, 429, 433])
    check("  ..and so do the other towns' airfields and bases НИЛ-2..4, and Абри's air base 427",
          [world.cell_of(i) for i in OTHER_AIRFIELDS + (523, 524, 525, 427)],
          [(6185, 1977), (5865, 1835), (5879, 2011), (5863, 1946), (5849, 1851), (5863, 2002),
           (6167, 1989), (5866, 1836)])

    # no way in, and none out through them
    fsc_files = sorted(int(os.path.basename(p)[:-4])
                       for p in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")))
    doors_in = []
    for lid in fsc_files:
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and int(rec.get("target_loc_id") or 0) in FSC:
                doors_in.append((lid, side, rec.get("confidence")))
    check("no door of any confidence leads into either, and neither has a door or a quest way"
          " out: no way out of the town went through them",
          (doors_in, {i: [travel.door(i, s) for s in "ab"] for i in FSC},
           [i for i in FSC if travel.quest_ways(world.location(i))]),
          ([], {i: [None, None] for i in FSC}, []))
    with io.open(os.path.join(DATA, "passages.json"), encoding="utf-8") as _fh:
        FSC_PASSAGES = json.load(_fh)
    into = []
    for section in ("doors", "sides", "quest", "walk_in"):
        for key, recs in (FSC_PASSAGES.get(section) or {}).items():
            if key.startswith("_"):
                continue
            if isinstance(recs, dict):
                recs = list(recs.values())
            for rec in recs or ():
                if isinstance(rec, dict) and (int(rec.get("target_loc_id") or 0) in FSC
                                              or key in {str(i) for i in FSC}):
                    into.append((section, key))
    check("  ..nor a passage, side or quest way of data/passages.json, into or out of them; neither"
          " is a no_map place",
          (into, sorted({str(i) for i in FSC} & set(FSC_PASSAGES.get("no_map") or {}))), ([], []))
    # A quest's markers (loc, finish_loc, rew_loc) are geoIDs, the packed map
    # cell (quests.py «geoIDs for the map markers»); loc_id, stay_in and a
    # way's target_loc_id are place ids.
    FSC_GEO = {world.pack(*c) for c in FSC.values()}
    fsc_rows = quests.table_rows()
    named = sorted({int(r["type"]) for r in fsc_rows
                    for key in ("loc", "finish_loc", "rew_loc")
                    if set(place_ids(r.get(key))) & FSC_GEO}
                   | {int(r["type"]) for r in fsc_rows
                      for key in ("loc_id", "stay_in")
                      if set(place_ids(r.get(key))) & set(FSC)}
                   | {int(r["type"]) for r in fsc_rows
                      if isinstance(r.get("way"), dict)
                      and int(r["way"].get("target_loc_id") or 0) in FSC})
    check("  ..and no quest row rides anybody there, sends him there, waits or pays there",
          named, [])
    check("  ..nor does any quest as the server reads it",
          sorted(t for t, q in quests.QUESTS.items()
                 if {q.loc, q.finish_loc, q.rew_loc} & FSC_GEO or set(q.stay_in) & set(FSC)), [])
    check("  ..the markers this looks for are the two cells as the client unpacks them",
          sorted(world.unpack(g) for g in FSC_GEO), sorted(FSC.values()))

    # the people
    check("in the airfield a room stood the two FSC upgraders 8213/8214 alone; in the base nobody",
          {i: stood_in(i) for i in FSC}, {528: list(FSC_UPGRADERS), 522: []})
    check("  ..the upgraders stand in the airfields of Абу-Хамед, Абри, Донгола and Керма too, so"
          " neither is retired; their windows were empty there as here",
          ({i: [t for t in FSC_UPGRADERS if t in stood_in(i)] for i in OTHER_AIRFIELDS},
           [t for t in FSC_UPGRADERS if t in world.retired_creatures()],
           [setcraft.window(t)["in_types"] for t in FSC_UPGRADERS]),
          ({i: list(FSC_UPGRADERS) for i in OTHER_AIRFIELDS}, [], [[], []]))
    check("  ..the pilots in the airfield's file stand nowhere (world.EVENT_TOKENS 'admin'), the"
          " base's nine types have no record and no stand-in",
          ([t for t in FSC_PILOTS
            if not world._name_tokens(MT[t][1]) & world.EVENT_TOKENS
            or world.belongs_here(t, MT[t][1], MT[t][0], False)],
           sorted({t for _c, t in world.location(522).spawns if t}),
           [t for t in NIL1_TYPES if t in MT or world.substitute(t) is not None]),
          ([], sorted(NIL1_TYPES), []))
    check("nobody of the airfield gives or takes a quest, or registers a home",
          {t: (quests.given_by(t), quests.taken_by(t), world.offers_home(t))
           for t in FSC_UPGRADERS + FSC_PILOTS},
          {t: ([], [], False) for t in FSC_UPGRADERS + FSC_PILOTS})
    check("the ЦСЦ's people in the kept places stay, as decided: О'Нилл and Беккет at Причал,"
          " Доберман and Хэтфилд in the camp 429, Кёртис of the Фонд in the old market",
          {i: [t for t in ts if t in standing(i) and t not in world.retired_creatures()]
           for i, ts in CSC_PEOPLE.items()}, {i: list(ts) for i, ts in CSC_PEOPLE.items()})
    check("  ..and the boat into Заречье (412, О'Нилл's) stays off",
          (quests.get(412).give, quests.get(412).take, 412 in quests.given_by(5685)),
          ([], [], False))

    # the quests
    FSC_WORDS = re.compile(r"ФСЦ|ЦСЦ|Фонд\w* спасения|аэроплощадк|аэродром|авиабаз|НИЛ-?\d|"
                           r"вертол[её]т", re.IGNORECASE)
    check("no quest anybody gives or takes speaks of the ФСЦ, its airfield or a base НИЛ",
          sorted(t for t, q in quests.QUESTS.items()
                 if (q.give or q.take) and any(s and FSC_WORDS.search(s) for s in q.texts)), [])
    check("  ..the words the map had for them, as this test looks for them",
          [bool(FSC_WORDS.search(w)) for w in ("Аэроплощадка ФСЦ", "База ФСЦ \"НИЛ-1\"")],
          [True, True])

    # the town's streets: neither cell opens an ambush, listed or not
    FSC_RING = [(x, y) for x in range(5925, 6036) for y in range(1685, 1781)]

    def fsc_ambush():
        out = {}
        for x, y in FSC_RING:
            band = encounters.band_at(x + 0.5, y + 0.5)
            if band is not None:
                out[(x, y)] = (band.camp, band.lo, band.hi)
        return out

    world.settlements()
    world.retired_cells()
    fsc_now = fsc_ambush()
    saved = (world._SETTLEMENTS, world._RETIRED_CELLS)
    try:
        before = dict(saved[0])
        before.update({c: i for i, c in FSC.items()})
        world._SETTLEMENTS = before
        world._RETIRED_CELLS = {c: i for c, i in saved[1].items() if i not in FSC}
        fsc_was = fsc_ambush()
        world._SETTLEMENTS = saved[0]
        fsc_bare = fsc_ambush()
    finally:
        world._SETTLEMENTS, world._RETIRED_CELLS = saved
    check("around the town and across the river the ambush cells are those of the map with the"
          " airfield and the base on it",
          (len(fsc_now) > 1500, fsc_now == fsc_was), (True, True))
    check("  ..and the two cells as plain wasteland would open none either",
          {c: v for c, v in fsc_bare.items() if fsc_was.get(c) != v}, {})

    # the database
    check("the run_once's places are the airfield and the base, Причал its target, its name new",
          (sorted(accounts.HALFA_FSC_PLACES), accounts.RETIRED_PLACES_TO,
           accounts.HALFA_FSC_FIX not in (accounts.RETIRED_PLACES_FIX, accounts.HALFA_CUT_FIX,
                                          accounts.PREMIUM_THINGS_FIX)),
          (sorted(FSC), (PRICHAL,) + world.cell_of(PRICHAL), True))
    path = os.path.join(tempfile.mkdtemp(), "fsc.db")
    st = accounts.Store(path)
    acc, _ = st.register("fsc", "secret")
    ids = {}
    for name, loc, home in (("in528", 528, None), ("in522", 522, None), ("home528", 36, 528),
                            ("home522", 429, 522), ("in468", 468, None), ("in447", 447, None),
                            ("pier", PRICHAL, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5970, gy = 1727,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5970, home_gy = 1727"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    keeper = ids["in528"]
    for t in (119, 10120):
        st.take_quest(keeper, t, {}, True)
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.HALFA_FSC_FIX,))
    st.db.commit()
    st.close()

    lines = Lines()
    logging.getLogger("lava").addHandler(lines)
    try:
        st = accounts.Store(path)
    finally:
        logging.getLogger("lava").removeHandler(lines)
    chars = {n: st.character(c) for n, c in ids.items()}
    check("whoever was in the airfield or the base is at Причал, on its cell, off the map, with"
          " no cell of the old file",
          {n: (chars[n]["loc"], chars[n]["gx"], chars[n]["gy"], chars[n]["on_map"], chars[n]["pos"])
           for n in ("in528", "in522")}, {n: (PRICHAL, 5965, 1728, 0, None) for n in ("in528", "in522")})
    check("  ..a home in either is Причал now, the character himself left where he was",
          [(chars[n]["home_loc"], chars[n]["home_gx"], chars[n]["home_gy"], chars[n]["loc"])
           for n in ("home528", "home522")],
          [(PRICHAL, 5965, 1728, 36), (PRICHAL, 5965, 1728, 429)])
    check("  ..the one in 468 (the cut of 2026-10-09, run long ago), in 447 and at Причал untouched",
          [(chars[n]["loc"], chars[n]["pos"]) for n in ("in468", "in447", "pier")],
          [(468, 77), (447, 77), (PRICHAL, 77)])
    check("  ..and his journal as it was: no quest is tied to either place",
          sorted(r["type"] for r in st.quests(keeper)), [119, 10120])
    check("  ..the log says so: two moved, two homes",
          [ln for ln in lines.lines if accounts.HALFA_FSC_FIX in ln
           and "2 character(s) moved out of 528/522" in ln and "2 home(s) moved" in ln] != [], True)
    check("  ..the counts as the log has them, nothing left to do",
          accounts.relocate_halfa_fsc(st.db), dict(moved=0, homes=0))
    st.db.commit()
    st.db.execute("UPDATE characters SET loc = 528 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], accounts.ran(st.db, accounts.HALFA_FSC_FIX)), (528, True))
    st.close()
except Exception:
    import traceback
    fails.append("the ФСЦ broke:\n" + traceback.format_exc())


print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa cut OK")
