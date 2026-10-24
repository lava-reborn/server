"""Steyr TMP and Chang Feng out of the game, the owner's word of 2026-10-14:
«у STEYR TMP нет картинки и у Chang Feng тоже, убери их из игры».

What the cut is, each part held here:

  1. the list: data/retired.json "items" holds every type the original names
     Steyr TMP or Chang Feng -- 106: the A, (G) and (P) guns, every
     modification, the mobs' copies and Le Mon's (S) (CL) ones -- each with
     its why, and nothing else; items.retired and items.out_of_game say so
     for all of them. Where the client's icons are real files (the owner's
     client), the ones without a picture are pinned: classes/FireArm/<name>/
     ico.swf is no SWF for the whole line of Steyr TMP and for twelve types
     of Chang Feng's; the other 41 of Chang Feng's have one and went with
     their line. The rounds they took (9 mm НАТО) stay: other guns take them;
  2. no stall: no city's band (shop_bands.wares, goods of any kinds and
     levels -- Абу-Хамед's 16-20 and a whole 0-20 alike), no stall of any
     trader at any place of a city or without one, no list written by hand
     (data/npcs.json, the wiki's) that names one -- while UMP and Бизон ПП-19,
     the other lines of the same levels, stay where they were;
  3. no loot: no creature's table, quest drops or one-of groups, no corpse's
     bag even when a table names one (combat.RoomCombat.drop_loot), no
     schedule row (events), no fall off a dead player;
  4. no quest and no craft: no row of the table or its companions names one,
     and a row that did would stop the server (quests.check_items); the
     twelve recipes of Донгола's sub-machine gun masters Басам (347) and
     Фахад (387) are gone from data/questgen_weaponcraft.json, their types
     kept in its registry so that no other recipe takes them, and the
     masters offer 26 recipes each where they offered 32, UMP's and Бизон's
     among them; no bench takes one apart;
  5. no hands: no letter, lot or barter takes one;
  6. the admin: no gift, in the game or out of it, with a line that says why;
  7. on the wire: Донгола's «Пистолет-пулеметы и патроны» (1211, 103) and
     «Оружие» (1229, 195) show neither gun, and Басам's frame offers no
     recipe of them;
  8. the database: run_once retire-guns-2026-10-14 takes every copy out of
     the bags, banks, bodies, the ground, the auction and the letters, pays
     each owner a stall's price back into the purse (the ledger's
     "retired"), tells him by letter, sends a standing bid back, empties an
     offer, sends an offer that keeps the rest of its parcel back to its
     sender asking nothing (its price was for the whole parcel, and he is
     paid for what went), takes the twelve recipes out of the journals --
     once; a process
     without the client's tables waits. The same on Postgres:
     server/test_storage_pg.py.

    LAVA_RES=.../lava/res python3 server/test_retired_guns.py
"""
import asyncio
import json
import os
import re
import sys
import tempfile
import types as pytypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DB = os.path.join(tempfile.mkdtemp(), "retired_guns.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START", "LAVA_QUESTS", "LAVA_PLACEMENTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)

import accounts  # noqa: E402
import auction  # noqa: E402
import barter  # noqa: E402
import combat  # noqa: E402
import craft  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
import mobs  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import own_items  # noqa: E402
import production  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402

MECHANIC = "Steyr TMP и Chang Feng выведены из игры: ни лавки, ни лута, ни квеста, ни крафта"

cat = items.catalogue()
BY_NAME = {n: t for t, (_r, n) in cat.items()}
with open(os.path.join(DATA, "retired.json"), encoding="utf-8") as _fh:
    DOC = json.load(_fh)["items"]
GONE = {int(k): v for k, v in DOC.items() if not k.startswith("_")}
STEYR, STEYR_G, STEYR_P = 25501, 25502, 25503
CHANG, CHANG_G = 25527, 25528
STEYR_CLIP = 25504                      # sub_machine_guns_1_lvl_13_mod_clipsize
UMP, UMP_G = BY_NAME["sub_machine_guns_2_lvl_13"], BY_NAME["sub_machine_guns_2_lvl_13_gold"]
BIZON, BIZON_G = BY_NAME["sub_machine_guns_2_lvl_14"], BY_NAME["sub_machine_guns_2_lvl_14_gold"]
KEPT = (UMP, UMP_G, BIZON, BIZON_G)
NATO_9 = (6092, 6104, 6116)             # 9мм НАТО КС / СТ / ОТ
BASAM, FAHAD = 347, 387                 # Донгола's sub-machine gun masters, A and G
SMG_STALL, WEAPONS = 1211, 1229         # «Пистолет-пулеметы и патроны» (103), «Оружие» (195)
RECIPES = (10283, 10284, 10285, 10289, 10290, 10291, 10315, 10316, 10317, 10321, 10322, 10323)


def shown(t):
    return (orig_texts.item_names().get(t) or "").split("$")[0].strip()


# --- 1. the list -----------------------------------------------------------------------------
print("the list")
NAMED = sorted(t for t, v in orig_texts.item_names().items()
               if re.match(r"^(Steyr TMP|Chang Feng)\b", v or ""))
check("data/retired.json items: every type the original names Steyr TMP or Chang Feng, 106,"
      " and nothing else", (sorted(GONE), len(GONE)), (NAMED, 106))
check("  ..each with its why, the section with its own, the owner's words in it",
      ([t for t, why in GONE.items() if len(why) < 20],
       "убери их из игры" in DOC.get("_", "")), ([], True))
check("  ..each a gun of the two lines (sub_machine_guns_1_lvl_13 Steyr TMP, _14 Chang Feng),"
      " its name the line's",
      [t for t in GONE if items.root_of(t) != items.FIRE_ARM
       or not re.match(r"^sub_machine_guns_1_lvl_(13|14)(_|$)", cat[t][1])
       or shown(t).startswith("Steyr TMP") != ("_lvl_13" in cat[t][1])], [])
check("the server reads it: items.retired and out_of_game for every one, premium for the 52"
      " (P) and (S) (CL) copies alone",
      (sorted(items.retired_items()) == sorted(GONE),
       [t for t in GONE if not (items.retired(t) and items.out_of_game(t))],
       sum(1 for t in GONE if items.premium(t)),
       [t for t in KEPT if items.out_of_game(t)]),
      (True, [], 52, []))
check("  ..read once, at start (items.preload), like every table a handler asks",
      "retired_items()" in open(os.path.join(HERE, "items.py"), encoding="utf-8").read()
      .split("def preload():", 1)[1], True)

# The pictures. CI's icons are empty files under the real names (README «Ресурсы для
# тестов»); the owner's client has the real ones, and there the head says it.
NO_PICTURE = sorted([t for t in GONE if shown(t).startswith("Steyr TMP")]
                    + [25527, 25528, 25539, 38856, 38857, 38858, 38865, 38866, 38867, 38873,
                       39611, 39616])


def head(t):
    root, name = cat[t]
    path = os.path.join(world.RES, own_items.icon_path(root, name))
    try:
        with open(path, "rb") as fh:
            return fh.read(3)
    except OSError:
        return None


heads = {t: head(t) for t in GONE}
if all(h for h in heads.values()):
    swf = (b"CWS", b"FWS", b"ZWS")
    check("the pictures: every Steyr TMP type and twelve of Chang Feng's (the A and (G) guns,"
          " the mobs' copy, «время прицеливания», «ловкость», (G) «точность и дистанция»"
          " and two Le Mon ones) have an ico.swf that is no SWF, 65 in all",
          sorted(t for t, h in heads.items() if h not in swf), NO_PICTURE)
    check("  ..the other 41 of Chang Feng's draw: they went with their line",
          (len([t for t, h in heads.items() if h in swf]),
           all(shown(t).startswith("Chang Feng") for t, h in heads.items() if h in swf)),
          (41, True))
    check("  ..and the why of each says which", sorted(t for t in GONE if "картинки нет" in GONE[t]),
          NO_PICTURE)
else:
    print("  -- the client's icons are empty files here (CI): the pictures are checked where"
          " they are real")
    check("the why of each says whether it has a picture",
          (sorted(t for t in GONE if "картинки нет" in GONE[t]),
           len([t for t in GONE if "картинка есть" in GONE[t]])), (NO_PICTURE, 41))

ROUNDS = {a for t in GONE for a in items.params_of(t)["comp_array"]}
check("their rounds stay: 9 мм НАТО, every one of which UMP takes too, the КС, СТ and ОТ still"
      " on Донгола's «Пистолет-пулеметы и патроны»",
      (set(NATO_9) <= ROUNDS, sorted(ROUNDS - set(items.params_of(UMP)["comp_array"])),
       [t for t in ROUNDS if items.out_of_game(t) and not items.premium(t)],
       [a for a in NATO_9 if a not in items.stock_for(SMG_STALL, 103)]),
      (True, [], [], []))

# --- 2. no stall -----------------------------------------------------------------------------
print()
print("no stall")
mt = world.mob_types()


def stood(loc_id):
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), mt)
    return sorted({npc.type_id for npc in room.npcs.values() if npc.root == world.TRADER})


wares = shop_bands.wares()
check("no city's band has them: shop_bands.wares leaves all 106 out, and UMP and Бизон ПП-19"
      " (the same levels' other line) in",
      ([t for t in GONE if t in wares], [t for t in KEPT if t not in wares]), ([], []))
check("  ..any kinds, any levels: Абу-Хамед's 16-20, Донгола's 12-16, the whole 0-20",
      {(lo, hi): [t for t in shop_bands.goods(shop_bands.KINDS, lo, hi) if t in GONE]
       for lo, hi in ((16, 20), (12, 16), (0, 20))},
      {(16, 20): [], (12, 16): [], (0, 20): []})
CITY_PLACES = sorted(p for _n, _lo, _hi, places in shop_bands.CITIES for p in places)
AT = {p: stood(p) for p in CITY_PLACES}
TRADERS = sorted(set(items.stock_table()) | set(npcs.STOCK) | set(shop_bands.SELLERS)
                 | {t for ts in AT.values() for t in ts})
on_sale = sorted({(p, tr, t) for p, ts in AT.items() for tr in ts
                  for t in items.stock_for(tr, p) if t in GONE}
                 | {(None, tr, t) for tr in TRADERS for t in items.stock_for(tr) if t in GONE})
check("no stall of any trader sells one, at any place of a city (%d places, %d traders) or"
      " without a place" % (len(AT), len(TRADERS)), on_sale, [])
check("  ..Донгола's two that had them (1211 at 103, 1229 at 195) still sell UMP and Бизон,"
      " A and (G)",
      {(tr, p): [t for t in KEPT if t not in items.stock_for(tr, p)]
       for tr, p in ((SMG_STALL, 103), (WEAPONS, 195))},
      {(SMG_STALL, 103): [], (WEAPONS, 195): []})
check("  ..the editor's lists (items.own_stock) and the craft's additions name none",
      sorted({t for tr in TRADERS for t in items.own_stock(tr) + craft.stock_extra(tr)
              if t in GONE}), [])
_stock = npcs.stock
npcs.stock = lambda tr: [STEYR, UMP, CHANG_G, STEYR_P] if tr == 1152 else _stock(tr)
try:
    check("  ..and a list written by hand that names them (data/npcs.json) loses them on the"
          " wire and in the editor, UMP kept", (items.stock_for(1152), items.own_stock(1152)),
          ([UMP], [UMP]))
finally:
    npcs.stock = _stock

# --- 3. no loot ------------------------------------------------------------------------------
print()
print("no loot")
dropped = {}
for m in sorted(mt):
    got = [t for t, _c, _v in mobs.loot_table(m)] + [t for t, _c in mobs.quest_table(m)] \
        + [t for g in mobs.one_of_groups(m) for t, _w in g] \
        + [t for t, _n in production.yield_of(m)]
    got = [t for t in got if t in GONE]
    if got:
        dropped[m] = got
check("no creature's table, quest drops, one-of groups or yield has one (%d kinds)" % len(mt),
      dropped, {})
check("  ..nor may any: droppable, one_of_droppable and quest_droppable say no to all 106,"
      " a priced UMP droppable",
      ([t for t in GONE if mobs.droppable(t) or mobs.one_of_droppable(t)
        or mobs.quest_droppable(t)], mobs.droppable(UMP)), ([], True))
check("  ..no schedule row's loot: one naming Steyr TMP is a problem the server stops on",
      [p for p in events.Schedule({"loot": [{"obj": STEYR, "locs": [103], "mobs": [374],
                                             "why": "probe"}]}).problems(mt)
       if "out of the game" in p],
      ["loot %d: no thing of the game's, or one out of the game ((P), or data/retired.json"
       " items)" % STEYR])


class _Store:
    def __init__(self):
        self.made = []

    def create_item(self, owner, type_id, root, **fields):
        self.made.append(type_id)
        return dict(uniq=len(self.made), type_id=type_id)


_loot_for, _ev, _yield = mobs.loot_for, events.loot, production.yield_of
mobs.loot_for = lambda st, rng, wanted=(), **context: [(STEYR, 1), (UMP, 1), (CHANG_G, 1), (STEYR_P, 1)]
events.loot = lambda loc, mob, rng: [(CHANG, 1)]
production.yield_of = lambda t: [(STEYR_CLIP, 1)]
try:
    fake = pytypes.SimpleNamespace(store=_Store(),
                                   room=pytypes.SimpleNamespace(loc=pytypes.SimpleNamespace(id=93)))
    mob = pytypes.SimpleNamespace(stats=mobs.stats(374), type_id=374, quest_wants=())
    combat.RoomCombat.drop_loot(fake, mob)
    check("  ..and a corpse whose rolls name them (its table, an event, a yield) leaves them"
          " out of its bag: UMP alone lies there", fake.store.made, [UMP])
finally:
    mobs.loot_for, events.loot, production.yield_of = _loot_for, _ev, _yield
check("no fall off a dead player either (combat.drops_on_death): a bag on the ground would"
      " pass one on", ([t for t in GONE if combat.drops_on_death(t)], combat.drops_on_death(UMP)),
      ([], True))

# --- 4. no quest and no craft -----------------------------------------------------------------
print()
print("no quest and no craft")
check("no row of the table or its companions names one, given, asked for, at random or lent",
      sorted((q.type, t) for q in quests.QUESTS.values() for _f, t in q.things() if t in GONE),
      [])
check("  ..the table passes the start's check (quests.check_items)", quests.check_items(), None)
for field, row in (("rew_obj", {"rew_obj": [STEYR]}),
                   ("rew_random", {"rew_random": [{"obj": CHANG_G, "num": 1, "w": 1},
                                                  {"obj": UMP, "num": 1, "w": 1}]}),
                   ("objs", {"kind": "bring_l_obj", "objs": [{"obj": STEYR_CLIP, "num": 1}]})):
    probe = dict(quests.QUESTS)
    probe[99990] = quests.Quest(dict({"type": 99990, "kind": "del_obj", "name": "x",
                                      "give": [], "take": []}, **row))
    try:
        quests.check_items(probe)
        bad = None
    except ValueError as exc:
        bad = str(exc)
    t = {"rew_obj": STEYR, "rew_random": CHANG_G, "objs": STEYR_CLIP}[field]
    check("  ..a row with one in %s would stop the server, named" % field, bad,
          "quest 99990 names things out of the game (data/retired.json items): %s %d"
          % (field, t))
with open(os.path.join(DATA, "questgen_weaponcraft.json"), encoding="utf-8") as _fh:
    CRAFT = json.load(_fh)
check("the weapon craft: no recipe takes or gives one; the twelve of Донгола's masters are"
      " gone from the table and their types stay in its registry, so no other key takes them",
      ([r["type"] for r in CRAFT["quests"]
        if {r["craft"].get("gun"), r["craft"].get("mod")} & set(GONE)],
       [t for t in RECIPES if quests.get(t) is not None],
       sorted(t for t in CRAFT["types"].values() if t in RECIPES)),
      ([], [], sorted(RECIPES)))
check("  ..Басам's and Фахад's recipes (their quests and craft.upgrader_lists): 26 each where"
      " there were 32 (the six of Steyr TMP and Chang Feng gone), UMP's and Бизон ПП-19's three"
      " among them, none taking or giving one of the two",
      {npc: (len(quests.given_by(npc)), len(craft.upgrader_lists(npc)["in_types"]),
             [craft.upgrader_lists(npc)["in_types"].count(g) for g in guns],
             sorted(set(craft.upgrader_lists(npc)["in_types"]
                        + craft.upgrader_lists(npc)["out_types"]) & set(GONE)))
       for npc, guns in ((BASAM, (UMP, BIZON)), (FAHAD, (UMP_G, BIZON_G)))},
      {BASAM: (26, 26, [3, 3], []), FAHAD: (26, 26, [3, 3], [])})
check("  ..no bench takes one apart (craft.salvageable), as it takes UMP",
      ([t for t in GONE if craft.salvageable(t)], craft.salvageable(UMP)), ([], ("smg", 13)))

# --- 5. no hands -----------------------------------------------------------------------------
print()
print("no hands")
check("no letter and no barter takes one (mail.postable, barter.tradable), as they take UMP",
      ([t for t in GONE if mail.postable(t) or barter.tradable(t)],
       (mail.postable(UMP), barter.tradable(UMP))), ([], (True, True)))


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
_sess = _Sess({"type_id": STEYR, "slot": 2048, "root": 0, "uniq": 1})
res, then = _AtTheAuctioneer(_sess, _st, None)._create({"obj": "x1", "time": 72, "a_bid": 10})
then()
_st.close()
check("  ..nor the auction: refused, «Этот предмет непередаваемый»", (res, _sess.said),
      (auction.RES_REFUSED, ["Этот предмет непередаваемый"]))

# --- 6. the admin, 7. on the wire ------------------------------------------------------------
_store = accounts.Store(DB)
_store.register("keeper", "secret")
_store.close()
CRED = accounts.credential("keeper", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)

print()
print("the admin")
check("the admin's gift: Steyr TMP refused with its name, Chang Feng (G) too, a (P) copy as"
      " (P), UMP given (server.refused_gift)",
      [server.refused_gift(t) for t in (STEYR, CHANG_G, STEYR_P, UMP)],
      ["предмет %d (Steyr TMP) — выведен из игры, не выдаётся" % STEYR,
       "предмет %d (Chang Feng (G)) — выведен из игры, не выдаётся" % CHANG_G,
       server.PREMIUM_REFUSED % STEYR_P, None])


class Writer:
    def __init__(self):
        self.frames = []
        self.read = 0
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        self.closed = True

    async def drain(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    name, params = decode(text)
    sess.handle(name, params)
    w = sess.writer
    out, w.read = w.frames[w.read:], len(w.frames)
    return out


def of(frames, name):
    return [p for n, p in frames if n == name]


def as_list(v):
    return list(v) if isinstance(v, list) else ([] if v in (None, "") else [v])


def goto(sess, loc_id):
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % loc_id)
    run(sess, "lenter;accept=1;")
    return {npc.type_id: eid for eid, npc in sess.room.npcs.items()}


def window(sess, npc, frame):
    got = of(run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc), frame)
    return got[0] if got else {}


async def main():
    sess = server.Session(Writer(), "keeper")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Keeper@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    cid = sess.char_id

    before = len(server.STORE.items_of(cid))
    said = sess.admin_give(STEYR)
    frames = sess.writer.frames[sess.writer.read:]
    sess.writer.read = len(sess.writer.frames)
    check("  ..in the game (Session.admin_give, the panel's online path and /give): refused,"
          " nothing in the bag, no ss_obj_status",
          (said, len(server.STORE.items_of(cid)) - before,
           [p for n, p in frames if n == "ss_obj_status"]),
          (server.RETIRED_REFUSED % (STEYR, "Steyr TMP"), 0, []))
    out = server.apply_admin_action({"kind": "item", "char_id": cid, "account_id": None,
                                     "args_json": json.dumps({"type_id": CHANG, "count": 1})})
    away, _ = server.STORE.create_character(server.STORE.register("away", "secret")[0],
                                            "Away", 0, "1")
    gone = server.apply_admin_action({"kind": "item", "char_id": away, "account_id": None,
                                      "args_json": json.dumps({"type_id": STEYR_G, "count": 1})})
    given = server.apply_admin_action({"kind": "item", "char_id": away, "account_id": None,
                                       "args_json": json.dumps({"type_id": UMP, "count": 1})})
    check("  ..the panel's queue (apply_admin_action), online and offline: refused, said why;"
          " UMP laid in the bag of the one away",
          (out, gone, given, [r["type_id"] for r in server.STORE.items_of(cid)
                              + server.STORE.items_of(away) if r["type_id"] in GONE],
           [r["type_id"] for r in server.STORE.items_of(away)].count(UMP)),
          (server.RETIRED_REFUSED % (CHANG, "Chang Feng"),
           server.RETIRED_REFUSED % (STEYR_G, "Steyr TMP (G)"), "положено в рюкзак (не в игре)",
           [], 1))

    print()
    print("on the wire")
    for place, trader in ((103, SMG_STALL), (195, WEAPONS)):
        npc = goto(sess, place)[trader]
        stall = as_list(window(sess, npc, "userInfo_Trader").get("type_list"))
        check("%d at %d: its window as items.stock_for at the place, UMP and Бизон on it, no"
              " Steyr TMP or Chang Feng" % (trader, place),
              (stall == items.stock_for(trader, place), [t for t in KEPT if t not in stall],
               [t for t in stall if t in GONE]), (True, [], []))
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % 97)
    met = {p["name"]: (n, p) for n, p in run(sess, "lenter;accept=1;")
           if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p}
    kind, info = met.get(BASAM, (None, {}))
    offered = as_list(info.get("give_quests"))
    check("Басам (347, the masters' camp 97): the recipes his frame offers are the table's 26,"
          " none of the twelve, UMP's and Бизон's among them",
          (kind, len(offered), sorted(set(offered) & set(RECIPES)),
           sorted({quests.get(q).rew_obj[0] for q in offered} & set(GONE)),
           sorted({craft.rows()[q]["gun"] for q in offered} & {UMP, BIZON})),
          ("userInfo_Commoner", 26, [], [], sorted([UMP, BIZON])))
    sess.writer.close()


asyncio.run(main())

# --- 8. the database -------------------------------------------------------------------------
print()
print("the database")
try:
    check("the run_once's name, its recipes the twelve the table lost",
          (accounts.RETIRED_ITEMS_FIX, accounts.RETIRED_RECIPES), ("retire-guns-2026-10-14", RECIPES))
    PRICE = {t: (items.params_of(t)["cost"], items.params_of(t)["g_cost"])
             for t in (STEYR, STEYR_G, STEYR_CLIP, CHANG, CHANG_G)}
    check("a stall's price: the articles' -- Steyr TMP 39 700 afro, (G) 14.28 G; Chang Feng"
          " 47 900, (G) 19.21 G; a modification its gun's",
          PRICE, {STEYR: (39700, 0), STEYR_G: (0, 1428), STEYR_CLIP: (39700, 0),
                  CHANG: (47900, 0), CHANG_G: (0, 1921)})
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    st = accounts.Store(path)
    acc, _ = st.register("old", "secret")
    ids = {}
    for name in ("holder", "seller", "bidder", "addressee", "offerer", "gone"):
        ids[name], _ = st.create_character(acc, name, 0, "1")
    holder, seller, bidder = ids["holder"], ids["seller"], ids["bidder"]
    addressee, offerer = ids["addressee"], ids["offerer"]
    money = {n: st.money(c) for n, c in ids.items()}
    in_bag = st.create_item(holder, STEYR, 0)
    in_bank = st.create_item(holder, STEYR_CLIP, 0, slot=4096)
    gold_one = st.create_item(holder, CHANG_G, 0)
    premium_one = st.create_item(holder, STEYR_P, 0)
    ump = st.create_item(holder, UMP, 0)
    lying = st.create_item(0, CHANG, 0)
    st.lay_down({lying["uniq"]: 9e9}, (103, None, None), 100)
    gone_char = st.create_item(ids["gone"], STEYR, 0)

    def lot_of(row, **kw):
        snap = {"uniq": row["uniq"], "type_id": row["type_id"], "root": row["root"], "count": 1}
        return dict(dict(type_id=row["type_id"], root=row["root"], item_json=json.dumps(snap),
                         seller=seller, seller_name="seller", currency=0, start_bid=100,
                         buyout=0, fee=5, hours=24, created_at=1, ends_at=9e9), **kw)

    selling = st.create_item(seller, CHANG, 0)
    lot = st.auction_list(selling["uniq"], seller, lot_of(selling))
    st.db.execute("UPDATE auction_lots SET bid = 150, bidder = ?, bidder_name = 'bidder'"
                  " WHERE id = ?", (bidder, lot["id"]))
    plain_sale = st.create_item(seller, UMP, 0)
    st.auction_list(plain_sale["uniq"], seller, lot_of(plain_sale))
    snap = lambda u, t: {"uniq": u, "type_id": t, "root": 0, "count": 1}  # noqa: E731
    st.mail_send(addressee, offerer, mail.LETTER, "gift", "", 10, 0,
                 json.dumps([snap(900, STEYR_G), snap(901, UMP)]))
    st.mail_send(addressee, offerer, mail.TRADE, "offer", "", 500, 0,
                 json.dumps([snap(902, CHANG)]))
    back = st.mail_send(addressee, offerer, mail.TRADE, "returned", "", 0, 0,
                        json.dumps([snap(903, STEYR)]))
    st.db.execute("UPDATE mail SET to_char = ?, returned = 1 WHERE id = ?", (offerer, back["id"]))
    # An offer of a Steyr TMP with an UMP for 80 000 afro, already read: its
    # price was for both, and the offerer is paid for the Steyr.
    mixed = st.mail_send(addressee, offerer, mail.TRADE_EXPRESS, "mixed", "", 80000, 5,
                         json.dumps([snap(904, STEYR), snap(905, UMP)]), when=1)
    st.db.execute("UPDATE mail SET read = 1 WHERE id = ?", (mixed["id"],))
    for t in (RECIPES[0], RECIPES[-1], 119):
        st.take_quest(holder, t, {}, True)
    done = st.take_quest(holder, RECIPES[1], {}, True)
    st.finish_quest(done, holder, RECIPES[1])
    st.db.execute("DELETE FROM characters WHERE id = ?", (ids["gone"],))
    st.db.execute("DELETE FROM migrations WHERE name = ?", (accounts.RETIRED_ITEMS_FIX,))
    st.db.commit()
    st.close()

    # A process without the client's tables: the fix waits, unwritten.
    _test = accounts.retired_test
    accounts.retired_test = lambda: None
    try:
        st = accounts.Store(path)
    finally:
        accounts.retired_test = _test
    check("without the client's tables the fix waits, unwritten, the things where they were",
          (accounts.ran(st.db, accounts.RETIRED_ITEMS_FIX), st.item(in_bag["uniq"]) is None),
          (False, False))
    st.close()

    st = accounts.Store(path)
    check("every copy gone from the bag, the bank and the ground (the (P) one too, and one of a"
          " character deleted since), UMP kept",
          ([st.item(r["uniq"]) is None for r in (in_bag, in_bank, gold_one, premium_one, lying,
                                                 gone_char)],
           st.item(ump["uniq"]) is not None,
           st.db.execute("SELECT COUNT(*) c FROM ground").fetchone()["c"]),
          ([True] * 6, True, 0))
    check("  ..the lot of a Chang Feng gone, UMP's kept",
          sorted(r["type_id"] for r in st.db.execute("SELECT type_id FROM auction_lots")), [UMP])
    letters = [dict(r) for r in st.db.execute("SELECT * FROM mail ORDER BY id")]
    by_subject = {r["subject"]: r for r in letters}
    check("  ..out of the letters: the gift keeps its UMP and its money, the offer asks nothing"
          " for nothing, the returned one is empty",
          [(json.loads(by_subject[s]["items_json"]), by_subject[s]["afro"])
           for s in ("gift", "offer", "returned")],
          [([snap(901, UMP)], 10), ([], 0), ([], 0)])
    m = by_subject["mixed"]
    check("  ..an offer that keeps its UMP goes back to the offerer with it, asking nothing, as"
          " «отказаться» sends it: the addressee cannot buy one gun at the price of two",
          (json.loads(m["items_json"]), m["to_char"], m["from_char"], m["returned"], m["read"],
           m["to_deleted"], m["from_deleted"], m["afro"], m["gold"], m["sent_at"] > 1),
          ([snap(905, UMP)], offerer, offerer, 1, 0, 0, 1, 0, 0, True))
    check("  ..the standing bid back to its bidder by letter",
          [(r["to_char"], r["from_char"], r["afro"], r["gold"]) for r in letters
           if r["subject"] == "Аукцион: ставка возвращена"], [(bidder, 0, 150, 0)])
    paid = {n: tuple(a - b for a, b in zip(st.money(ids[n]), money[n]))
            for n in ("holder", "seller", "bidder", "addressee", "offerer")}
    check("each owner paid a stall's price into the purse: the holder his Steyr TMP and its"
          " modification in afro, his Chang Feng (G) in gold, nothing for the (P) one; the seller"
          " his lot; the addressee the gift's Steyr TMP (G); the offerer his offers still"
          " unanswered and the letter that came back to him; the bidder nothing",
          paid, {"holder": (79400, 1921), "seller": (47900, 0), "bidder": (0, 0),
                 "addressee": (0, 1428), "offerer": (47900 + 39700 + 39700, 0)})
    rows = [r for r in st.ledger() if r["source"] == "retired"]
    check("  ..each payment a row of the ledger, «retired», the purse and the ledger agreeing",
          (sorted((r["char_id"], r["afro"], r["gold"]) for r in rows),
           all(sum(x["afro"] for x in st.ledger(c)) == st.money(c)[0]
               and sum(x["gold"] for x in st.ledger(c)) == st.money(c)[1]
               for c in (holder, seller, addressee, offerer))),
          (sorted([(holder, 79400, 1921), (seller, 47900, 0), (addressee, 0, 1428),
                   (offerer, 127300, 0)]), True))
    told = {r["to_char"]: r for r in letters if r["subject"] == accounts.RETIRED_SUBJECT}
    check("  ..and a letter to each, from the server, with no money in it, saying what went"
          " and what came",
          (sorted(told), {c: (r["from_char"], r["afro"], r["gold"], r["items_json"])
                          for c, r in told.items()}[holder],
           told[holder]["body"]),
          (sorted([holder, seller, addressee, offerer]), (0, 0, 0, "[]"),
           "У этих стволов нет картинки, и владелец убрал их из игры. Изъято: Chang Feng (G) x1,"
           " Steyr TMP x2, Steyr TMP (P) x1. Цена лавки зачислена на ваш счёт: 79400 афро и"
           " 19.21 G."))
    check("the twelve recipes out of the journal, 119 kept, the history of a hand-in kept",
          (sorted(r["type"] for r in st.quests(holder)), st.quest_done(holder, RECIPES[1])),
          ([119], True))
    check("  ..the counts as the log has them: nothing left the second time",
          accounts.retire_items(st.db, *accounts.retired_test()),
          dict(items=0, ground=0, lots=0, bids=0, letters=0, parcels=0, returned=0, journal=0,
               owners=0, afro=0, gold=0))
    st.create_item(holder, STEYR, 0)
    st.db.commit()
    st.close()
    st = accounts.Store(path)
    check("once per database: what comes after stays where it is put",
          ([r["type_id"] for r in st.items_of(holder)].count(STEYR),
           accounts.ran(st.db, accounts.RETIRED_ITEMS_FIX)), (1, True))
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
print("retired guns OK")
