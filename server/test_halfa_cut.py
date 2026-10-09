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
     stalls, Генри's, Генри ст's and Тиль's other quests;
  6. the clans: nothing of a clan stands on a place -- the tables have no
     column for one -- so a clan named KKND is a clan like any other;
  7. the database: whoever is in one of the cut's places, or calls one
     home, goes to Причал, and its quests leave the journals -- once, by
     the run_once «retire-halfa-cut-2026-10-09»; the history, the ledger,
     the bags and the clans stay as they are. On Postgres:
     server/test_storage_pg.py.

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
import events  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
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
except Exception:
    import traceback
    fails.append("the rest of the town broke:\n" + traceback.format_exc())


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


print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa cut OK")
