"""The owner's cut of (P), 2026-09-30: «удали всё, что связано с (P), в том
числе и локации».

What the cut is, each part held here:

  1. the places: the premium masters' camps 124 (Вади-Хальфа, 5968,1726),
     125 (Донгола, 5876,2012) and 130 (Абу-Хамед, 6182,1975) are off the
     map and nothing else moved -- the valley's Arena 167 with Сет's stall
     still on 6270,1831 (data/test_retired_places.py runs the placer itself
     and holds the table to exactly those three cells);
  2. the creatures: every premium creature a location file, data/
     placements.json, a window of data/schedule.json, a camp's fill or a
     stand-in could put down -- the _pm masters of 124, 125, 130 and of the
     camp 94, the fifteen «Подмастерье …[P]» of the quarters 452/456/457,
     the premium bar's people (804 at the door in 79, 812 in the port 445,
     and the bar 1010 itself), the premium quest places' mobs -- is in
     data/retired.json, every one of the cut's rows there is such a
     creature (the black market's 639 beside them is test_halfa_cut's),
     and no room stands one; a hand-kept row or a window naming one is
     refused;
  3. the ways: Мастер Азам's «Квартал ремесленников» (414) and the way back
     (415) are off, their passages and the quarter's no_map gone;
  4. quest 158 no longer promises a ride for holders of a residence
     permit, nor Мортимер's cashing (301-303) a free one: the rows' own
     starts, kept by own_texts over the original's and cleaned as the
     original's are -- no escaped quote shows, and no quest speaks of a
     residence permit or citizenship at all;
  5. no premium thing changes hands or comes from a quest: not in a letter,
     not at the auction, not at the barter, no quest row names one;
  6. the database: whoever is in 124, 125, 130 or 447, or calls one home,
     goes to Причал, and every premium thing in a bag, a bank, on the
     ground, at the auction or in a letter goes -- once, by run_once under
     new names -- and a process without the client's tables leaves the
     second for a start that has them.

The admin's gift of a premium thing, online and offline, is refused in
test_admin; the names over the map in test_map_labels; the stalls in
test_shops.

    LAVA_RES=.../lava/res python3 server/test_premium_cut.py
"""
import glob
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "premium_cut.db")
os.environ["LAVA_DB"] = DB
for _knob in ("LAVA_PASSAGES", "LAVA_PLACEMENTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import auction  # noqa: E402
import barter  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


with open(os.path.join(DATA, "retired.json"), encoding="utf-8") as _fh:
    RETIRED = json.load(_fh)
# The cut of (P)'s own places: data/retired.json holds the cut of Вади-Хальфа
# (2026-10-09) and of its ФСЦ (2026-10-10) beside them, which
# server/test_halfa_cut.py holds.
PLACES = {int(k): v for k, v in RETIRED["places"].items()
          if v.startswith("The owner's cut of (P)")}
# And its own creatures: the black market's 639 (2026-10-10), no premium
# creature, stands beside them, and server/test_halfa_cut.py holds it.
CREATURES = {int(k): v for k, v in RETIRED["creatures"].items()
             if not v.startswith("The owner's cut of Вади-Хальфа")}
CELLS = {124: (5968, 1726), 125: (5876, 2012), 130: (6182, 1975)}
QUARTER, AZAM, QUARTER_MASTER, WAY_IN, WAY_OUT = 447, 704, 5771, 414, 415
PRICHAL = 41
MT = world.mob_types()

# A premium creature by its own words: a _pm or pm_ token in its mobs.xml
# name (the masters wh_trmodif_rifle_pm, the bar's dn_pm_*, the quest
# places' pm_Ramires_10lvl), or a (P)/[P] -- Latin or Cyrillic -- in the name
# the client shows (the apprentices' «…[6][P]»).
PM_TOKEN = re.compile(r"(?:^|_)pm(?:_|$)", re.IGNORECASE)
P_MARK = re.compile(r"[(\[](?:P|Р)[)\]]")


def premium_creature(t):
    return bool(PM_TOKEN.search(MT[t][1]) or P_MARK.search(names.ALL.get(t, "") or ""))


# --- 1. the places ----------------------------------------------------------------------
print("the places")
try:
    table = world.settlements()
    check("data/retired.json takes out the three premium masters' camps, each with its why",
          (sorted(PLACES), all(v.strip() for v in PLACES.values())), ([124, 125, 130], True))
    check("  ..none of them on any cell, and their old cells lead into the wasteland",
          ([c for c, i in table.items() if i in PLACES],
           {i: world.location_at(*c) == world.pack(*c) for i, c in CELLS.items()}),
          ([], {i: True for i in CELLS}))
    check("  ..their files stay, so a character saved inside still loads",
          [world.location(i).fn for i in sorted(PLACES)],
          ["Upgraders_VH_P", "Upgraders_DN_P", "Upgraders_AH_P"])
    # Абу-Хамед's resistance camp 432, which stood on 6160,1975, went with
    # the cut of the camps across the river (2026-10-12,
    # server/test_river_camps_cut.py); the masters' camp 131 and the quarter
    # 127 beside 130's cell stay.
    check("the neighbours stay: Причал, the quarter 447, the valley's Arena 167 (Сет's"
          " stall), Донгола's 79 and 96, Абу-Хамед's 131 and 127",
          [table.get(c) for c in ((5965, 1728), (5968, 1719), (6270, 1831), (5877, 2011),
                                  (5876, 2011), (6183, 1977), (6183, 1975))],
          [PRICHAL, QUARTER, 167, 79, 96, 131, 127])
    check("the run_once's places are the retired ones and the quarter they cut off,"
          " and its Причал is 41's own cell",
          (sorted(accounts.RETIRED_PLACES), accounts.RETIRED_PLACES_TO),
          (sorted(set(PLACES) | {QUARTER}), (PRICHAL,) + world.cell_of(PRICHAL)))
except Exception:
    import traceback
    fails.append("the places broke:\n" + traceback.format_exc())


# --- 2. the creatures -------------------------------------------------------------------
print("the creatures")
try:
    put = {}                                          # type -> where it could be put down
    for path in glob.glob(os.path.join(world.RES, "locations", "static", "*.xml")):
        lid = int(os.path.basename(path)[:-4])
        try:
            loc = world.location(lid)
        except (KeyError, OSError, AttributeError, ValueError):
            continue
        for _cell, t in loc.spawns:
            put.setdefault(t, set()).add("file %d" % lid)
        for t in world.camp_fill(lid):
            put.setdefault(t, set()).add("fill %d" % lid)
    for lid, recs in world.placements().items():
        for rec in recs:
            put.setdefault(int(rec["type"]), set()).add("placed %d" % lid)
    for rec in events.table().spawns:
        for t in events._types(rec.get("types")):
            put.setdefault(t, set()).add("window %s" % rec.get("loc"))
    for t in list(put):
        stand_in = world.substitute(t)
        if stand_in is not None:
            put.setdefault(stand_in, set()).add("stand-in for %d" % t)
    found = {t for t in put if t in MT and premium_creature(t)}
    check("every premium creature the world could put down is in data/retired.json",
          sorted((t, MT[t][1], sorted(put[t])) for t in found - set(CREATURES)), [])
    check("  ..and every creature there is one, with its why",
          ([t for t in CREATURES if t not in MT or not premium_creature(t)],
           [t for t, why in CREATURES.items() if not why.strip()]), ([], []))
    check("  ..the ones the cut names among them: the camps' masters, 2012 in 94, the fifteen"
          " apprentices [P], the bouncer 804 and the customs officer 812",
          sorted({702, 704, 705, 706, 708, 709, 710, 743, 745, 746, 747, 4582, 2012, 804, 812}
                 | set(range(5784, 5797, 3)) | set(range(5829, 5842, 3))
                 | set(range(5874, 5887, 3))) == sorted(
              t for t in CREATURES if t < 800 or t > 813 or t in (804, 812)), True)
    check("  ..where each stood", {t: sorted(put[t]) for t in (2012, 804, 812, 704, 5784, 5886)},
          {2012: ["file 94"], 804: ["file 79"], 812: ["file 445"], 704: ["file 124"],
           5784: ["file 452"], 5886: ["file 457"]})

    rooms_of = sorted({int(w.split()[1]) for t in CREATURES for w in put.get(t, ())
                       if w.startswith(("file", "fill", "placed"))})
    stood = {}
    for lid in rooms_of:
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        stood[lid] = sorted(npc.type_id for npc in room.npcs.values())
    check("no room stands one, wherever the file puts it",
          {lid: [t for t in ts if t in CREATURES] for lid, ts in stood.items()},
          {lid: [] for lid in rooms_of})
    check("  ..the camps 124, 125, 130 open empty; 94, 79, 445 and the quarters keep their other"
          " people",
          ([stood[i] for i in (124, 125)], 2020 in stood[130],
           all(stood[i] for i in (94, 79, 445, 452, 456, 457))),
          ([[], []], True, True))
    check("  ..world.belongs_here refuses one in any place, at war or at peace",
          {t: [world.belongs_here(t, MT[t][1], MT[t][0], war, lid)
               for war, lid in ((0, 124), (1, 94), (0, None))] for t in (704, 2012, 804)},
          {t: [False] * 3 for t in (704, 2012, 804)})

    loc79 = world.location(79)
    free = next(c for c in range(loc79.width * loc79.height)
                if c not in loc79.obstacles and c not in {s for s, _t in loc79.spawns})
    row = {"type": 804, "cell": [free % loc79.width, free // loc79.width], "why": "t"}
    check("a hand-kept row naming one is refused (rooms.placement_problems)",
          [p for p in rooms.placement_problems(MT, {79: [row]}) if "out of the game" in p],
          ["loc 79: 804 on %d,%d: a creature out of the game (data/retired.json)"
           % tuple(row["cell"])])
    probe = events.Schedule({"windows": {"w": {"daily": ["12:00"], "minutes": 5, "why": "t"}},
                             "spawns": [{"window": "w", "loc": 79, "types": [804],
                                         "why": "t"}]})
    check("  ..and so is a window that would stand one (events.Schedule.problems)",
          [p for p in probe.problems(MT) if "out of the game" in p],
          ["spawns 79 [804]: 804 is a creature out of the game (data/retired.json)"])
    check("  ..while the real tables have none", (rooms.placement_problems(MT),
                                                  events.table().problems(MT)), ([], []))
    check("  ..and the names stay in the string table: an unknown id sends the client to"
          " the login screen", [t for t in CREATURES if not names.known(t)], [])
except Exception:
    import traceback
    fails.append("the creatures broke:\n" + traceback.format_exc())


# --- 3. the ways ------------------------------------------------------------------------
print("the ways")
try:
    with open(os.path.join(DATA, "passages.json"), encoding="utf-8") as _fh:
        PASSAGES = json.load(_fh)
    check("«Квартал ремесленников» (414) and «Назад, в лагерь мастеров» (415) are off, each"
          " with its why",
          [(quests.get(t).give, quests.get(t).take) for t in (WAY_IN, WAY_OUT)],
          [([], [])] * 2)
    check("  ..no quest way from 124 or 447, neither is a way any more, and 447 is no"
          " no_map place",
          (travel.quest_ways(world.location(124)), travel.quest_ways(world.location(QUARTER)),
           [travel.is_quest_way(t) for t in (WAY_IN, WAY_OUT)], travel.no_map(QUARTER),
           sorted({"124", "447"} & (set(PASSAGES["quest"]) | set(PASSAGES["no_map"])))),
          ([], [], [False, False], False, []))
    check("  ..nobody gives or takes either", [quests.given_by(t) for t in (AZAM, QUARTER_MASTER)
                                                if WAY_IN in quests.given_by(t)
                                                or WAY_OUT in quests.given_by(t)], [])
    rows = {int(r["type"]): r for r in quests.table_rows()}
    check("  ..and their rows say why", [rows[t]["why"].startswith("OFF") for t in
                                         (WAY_IN, WAY_OUT)], [True, True])
except Exception:
    import traceback
    fails.append("the ways broke:\n" + traceback.format_exc())


# --- 4. quest 158, Мортимер's cashing -------------------------------------------------
print("quest 158, Мортимер's cashing")
try:
    PERMIT = "вид на жительство или гражданство"
    PERMIT_RE = re.compile(r"гражданств|на жительств|ВНЖ", re.IGNORECASE)
    q158 = quests.get(158)
    row158 = {int(r["type"]): r for r in quests.table_rows()}[158]
    check("«Охранник санатория особого режима» no longer asks for a residence permit",
          PERMIT in q158.texts[quests.START], False)
    check("  ..the row's own start, kept over the original's, which still has it",
          (q158.own_texts, q158.texts[quests.START] == row158["start"],
           PERMIT in (orig_texts.quests()[158]["start"] or "")),
          (frozenset({"start"}), True, True))
    check("  ..the rest of it the original's", q158.texts[quests.FINISH],
          orig_texts.quests()[158]["finish"])
    check("  ..ending on the guarding's half hour, not on a dangling break",
          q158.texts[quests.START].endswith("нужно в течение 30 минут.</i>"), True)
    # Word for word the original's start, cleaned, up to the cut sentence: the
    # row was once copied from texts.xml with the original's '\"Охранять\"',
    # which orig_texts unescapes and an own text kept, and the tooltip
    # showed the backslashes (2026-10-02).
    START158 = orig_texts.quests()[158]["start"]
    CUT158 = "<Br><Br><b>Если вы хотите быстро добраться до тюрьмы"
    check("  ..and up to it the original's start, word for word, quotes plain",
          (CUT158 in START158, q158.texts[quests.START] == START158[:START158.index(CUT158)]
             .replace("12:00", "13:00").replace("16:00", "17:00").replace("23:00", "21:00"),
           '"Охранять"' in q158.texts[quests.START]),
          (True, True, True))
    check("  ..the row itself written clean, not cleaned at load",
          '\\"' in row158["start"], False)
    check("no quest's text carries an escaped quote the tooltip would show",
          sorted((t, i) for t, q in quests.QUESTS.items()
                 for i, s in enumerate(q.texts) if s and '\\"' in s), [])

    # An own text is cleaned as the original's would be: a row copied by hand
    # from texts.xml cannot bring its escaped quotes or doubled "%sex??" back.
    _mock = quests.Quest({"type": 1, "kind": "del_obj", "name": "x", "own_texts": ["start"],
                          "start": 'a \\"b\\" %sex??:а%', "finish": "f"})
    _saved = dict(quests.QUESTS)
    try:
        quests.QUESTS.clear()
        quests.QUESTS[1] = _mock
        quests._lay_original()
    finally:
        quests.QUESTS.clear()
        quests.QUESTS.update(_saved)
    check("  ..an own text gets orig_texts' cleaning", _mock.texts[quests.START],
          'a "b" %sex?:а%')

    # Мортимер's cashing (301-303), the only other quests that spoke of the
    # residence permit: «Как для лица не имеющего гражданства или вида на
    # жительство, будет взята комиссия» -- a citizen cashed for free. Here
    # everybody pays the 0.05 (rew_gold 95/495/995), so the start says that.
    CASH_WAS = "Как для лица не имеющего гражданства или вида на жительство, будет"
    for t, ounces in ((301, 95), (302, 495), (303, 995)):
        q, o = quests.get(t), orig_texts.quests()[t]["start"]
        check("Мортимер's %d: no residence permit, the original's start but for it" % t,
              (q.own_texts, PERMIT_RE.search(q.texts[quests.START]) is None,
               CASH_WAS in o, q.texts[quests.START] == o.replace(CASH_WAS, "Будет"),
               q.rew_gold),
              (frozenset({"start"}), True, True, True, ounces))
    check("only the two paid residence quests mention permits; legacy premium quests stay cut",
          sorted(t for t, q in quests.QUESTS.items()
                 if any(s and PERMIT_RE.search(s) for s in q.texts)), [2129, 2130])
    try:
        quests.Quest({"type": 1, "kind": "del_obj", "name": "x", "own_texts": ["title"]})
        bad = None
    except ValueError as exc:
        bad = str(exc)
    check("  ..own_texts names only the four texts", bad,
          "quest 1: own_texts names no text ['title']")
except Exception:
    import traceback
    fails.append("quest 158 broke:\n" + traceback.format_exc())


# --- 5. the things ----------------------------------------------------------------------
print("the things")
MASK_P, BERETTA = 6511, 25586               # hermit_mask_pm (P); Беретта 92
try:
    check("a premium thing: (P), and but for that tradable -- exchang, a price, no quest flag",
          (items.premium(MASK_P), items.params_of(MASK_P)["exchang"],
           items.params_of(MASK_P)["cost"] > 0, bool(items.params_of(MASK_P).get("quest"))),
          (True, 1, True, False))
    check("  ..goes into no letter and no barter; a Беретта does",
          [(mail.postable(t), barter.tradable(t)) for t in (MASK_P, BERETTA)],
          [(False, False), (True, True)])

    class _Inv:
        def __init__(self, row):
            self.row = row

        def find(self, _oid):
            return self.row

    class _Sess:
        char_id, room = 1, None

        def __init__(self, row):
            self.inv, self.said = _Inv(row), []

        def say(self, text):
            self.said.append(text)

    class _AtTheAuctioneer(auction.Auction):
        def at_auctioneer(self, p):
            return True

    _st = accounts.Store(DB)
    sess = _Sess({"type_id": MASK_P, "slot": 2048, "root": 1, "uniq": 1})
    res, then = _AtTheAuctioneer(sess, _st, None)._create({"obj": "x1", "time": 72,
                                                           "a_bid": 10})
    then()
    _st.close()
    check("  ..nor onto the auction: refused, «Этот предмет непередаваемый»",
          (res, sess.said), (auction.RES_REFUSED, ["Этот предмет непередаваемый"]))

    check("no quest row names one, on or off (quests.check_items)", quests.check_items(), None)
    probe = dict(quests.QUESTS)
    probe[99990] = quests.Quest({"type": 99990, "kind": "del_obj", "name": "x",
                                 "give": [], "take": [], "rew_obj": [MASK_P]})
    try:
        quests.check_items(probe)
        bad = None
    except ValueError as exc:
        bad = str(exc)
    check("  ..and one that did would stop the server", bad,
          "quest 99990 names premium things, out of the game: rew_obj %d" % MASK_P)
except Exception:
    import traceback
    fails.append("the things broke:\n" + traceback.format_exc())


# --- 6. the database --------------------------------------------------------------------
print("the database")
try:
    check("the run_once's mail numbers are mail's own",
          (accounts._TRADE_LETTERS, accounts._SYSTEM_SENDER, accounts._LETTER),
          ((mail.TRADE, mail.TRADE_EXPRESS), mail.SYSTEM_SENDER, mail.LETTER))
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    st = accounts.Store(path)
    acc, _ = st.register("old", "secret")
    ids = {}
    for name, loc, home in (("in124", 124, None), ("in447", QUARTER, None),
                            ("in125", 125, None), ("in130", 130, None),
                            ("home124", 36, 124), ("pier", PRICHAL, None)):
        cid, _ = st.create_character(acc, name, 0, "1")
        st.db.execute("UPDATE characters SET loc = ?, pos = 77, gx = 5968, gy = 1726,"
                      " on_map = 0 WHERE id = ?", (loc, cid))
        if home is not None:
            st.db.execute("UPDATE characters SET home_loc = ?, home_gx = 5968, home_gy = 1726"
                          " WHERE id = ?", (home, cid))
        ids[name] = cid
    st.db.commit()
    keeper, buyer = ids["pier"], ids["home124"]
    in_bag = st.create_item(keeper, MASK_P, 1)
    in_bank = st.create_item(keeper, MASK_P, 1, slot=4096)
    beretta = st.create_item(keeper, BERETTA, 3)
    lying = st.create_item(0, MASK_P, 1)
    st.lay_down({lying["uniq"]: 9e9}, (36, None, None), 100)
    on_sale = st.create_item(keeper, MASK_P, 1)

    def lot_of(row, **kw):
        snap = {"uniq": row["uniq"], "type_id": row["type_id"], "root": row["root"]}
        return dict(dict(type_id=row["type_id"], root=row["root"], item_json=json.dumps(snap),
                         seller=keeper, seller_name="pier", currency=0, start_bid=100,
                         buyout=0, fee=5, hours=24, created_at=1, ends_at=9e9), **kw)

    lot = st.auction_list(on_sale["uniq"], keeper, lot_of(on_sale))
    st.db.execute("UPDATE auction_lots SET bid = 150, bidder = ?, bidder_name = 'home124'"
                  " WHERE id = ?", (buyer, lot["id"]))
    gold_sale = st.create_item(keeper, MASK_P, 1)
    st.auction_list(gold_sale["uniq"], keeper, lot_of(gold_sale, currency=1))
    plain_sale = st.create_item(keeper, BERETTA, 3)
    st.auction_list(plain_sale["uniq"], keeper, lot_of(plain_sale))
    mixed = st.mail_send(buyer, keeper, mail.LETTER, "mixed", "", 10, 0, json.dumps(
        [{"uniq": 900, "type_id": MASK_P, "root": 1}, {"uniq": 901, "type_id": BERETTA,
                                                       "root": 3}]))
    trade = st.mail_send(buyer, keeper, mail.TRADE, "trade", "", 500, 0, json.dumps(
        [{"uniq": 902, "type_id": MASK_P, "root": 1}]))
    plain = st.mail_send(buyer, keeper, mail.LETTER, "plain", "", 0, 0, json.dumps(
        [{"uniq": 903, "type_id": BERETTA, "root": 3}]))
    st.db.execute("DELETE FROM migrations WHERE name IN (?, ?)",
                  (accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX))
    st.db.commit()
    st.close()

    # A process without the client's tables: the places move, the things wait.
    _premium_test = accounts.premium_test
    accounts.premium_test = lambda: None
    try:
        st = accounts.Store(path)
    finally:
        accounts.premium_test = _premium_test
    check("without the client's tables the things' fix waits, unwritten; the places' runs",
          (accounts.ran(st.db, accounts.PREMIUM_THINGS_FIX),
           accounts.ran(st.db, accounts.RETIRED_PLACES_FIX), st.item(in_bag["uniq"]) is None),
          (False, True, False))
    st.close()

    st = accounts.Store(path)
    chars = {n: st.character(c) for n, c in ids.items()}
    check("whoever was in 124, 447, 125 or 130 is at Причал, on its cell, off the map, with"
          " no cell of the old file",
          {n: (r["loc"], r["gx"], r["gy"], r["on_map"], r["pos"]) for n, r in chars.items()
           if n.startswith("in")},
          {n: (PRICHAL, 5965, 1728, 0, None) for n in ("in124", "in447", "in125", "in130")})
    check("  ..a home in 124 is Причал now, the character himself left where he was;"
          " the one at Причал untouched",
          ((chars["home124"]["home_loc"], chars["home124"]["home_gx"],
            chars["home124"]["home_gy"], chars["home124"]["loc"]),
           (chars["pier"]["loc"], chars["pier"]["pos"])),
          ((PRICHAL, 5965, 1728, 36), (PRICHAL, 77)))
    check("every premium thing gone from the bag, the bank and the ground, the Беретта kept",
          ([st.item(r["uniq"]) is None for r in (in_bag, in_bank, lying)],
           st.item(beretta["uniq"]) is not None,
           st.db.execute("SELECT COUNT(*) c FROM ground").fetchone()["c"]),
          ([True] * 3, True, 0))
    check("  ..its lots gone, the plain one kept",
          sorted(r["type_id"] for r in st.db.execute("SELECT type_id FROM auction_lots")),
          [BERETTA])
    letters = {r["subject"]: r for r in st.db.execute("SELECT * FROM mail ORDER BY id")}
    check("  ..the standing bid back to its bidder by letter, in its own currency",
          [(r["to_char"], r["from_char"], r["afro"], r["gold"], r["items_json"])
           for s, r in letters.items() if s == "Аукцион: ставка возвращена"],
          [(buyer, 0, 150, 0, "[]")])
    check("  ..out of the letters: the mixed one keeps its Беретта and its money, the trade"
          " one asks nothing for nothing, the plain one is untouched",
          [(json.loads(letters[s]["items_json"]), letters[s]["afro"])
           for s in ("mixed", "trade", "plain")],
          [([{"uniq": 901, "type_id": BERETTA, "root": 3}], 10), ([], 0),
           ([{"uniq": 903, "type_id": BERETTA, "root": 3}], 0)])
    check("  ..the counts as the log has them",
          accounts.retire_premium_things(st.db, items.premium),
          dict(items=0, types=0, ground=0, lots=0, bids=0, letters=0, parcels=0))
    st.create_item(keeper, MASK_P, 1)
    st.db.execute("UPDATE characters SET loc = 124 WHERE id = ?", (keeper,))
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          (st.character(keeper)["loc"], [r["type_id"] for r in st.items_of(keeper)].count(MASK_P),
           sorted(r["name"] for r in st.db.execute("SELECT name FROM migrations")
                  if r["name"] in (accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX))),
          (124, 1, sorted([accounts.RETIRED_PLACES_FIX, accounts.PREMIUM_THINGS_FIX])))
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
print("premium cut OK")
