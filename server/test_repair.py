"""Repair, restore and the price of a gold round (2026-09-28).

The owner's «поправь ремонт и восстановление снаряжения» and «цену патронам
снизь до 0.01 голды (которые голдовые)». What the original says and what
was wrong is written where it is kept: inventory.py (REPAIR_KEEPS,
GOLD_REPAIR_MOD, GOLD_RESTORE_PRICE_MOD, repair_window, repair_prices,
Inventory.repair) and items.py (GOLD_AMMO_ROUND); in Russian, the README's
«Ремонт и восстановление».

In process:
  * the repair window's figures (inventory.repair_window) against
    RepairInterface transcribed here on its own, over a grid of prices,
    wear and multipliers; the charge (inventory.repair_prices) never above
    either of the window's two figures for a repair -- the slot's and the
    thing's share of «Отремонтировать все» -- and the slot's where they
    agree;
  * the gold button at par with the one rate;
  * Inventory.repair on a character: nine tenths of the ceiling a repair,
    in either currency, and a thing worn less than that made whole where
    it stands; a press with nothing to do answered 0 for nothing; the one
    refusal a listed thing gets, past mending at 0 of 1; a thing priced in
    gold alone repaired from its gold valuation and restored for its price;
    a registrar that mends nothing; the money ledger;
  * the admin panel's gifts to players not in the game, given bare before
    (inventory.OFFLINE_GIFTS_FIX): filled once, in the bag, in a letter and
    on the auction, and nothing else touched;
  * every gold round at a hundredth of an ounce a round, the other rounds
    as they were.
Then one server over the socket, on Вади-Хальфа's black market (102,
5970x1730), where «Пистолеты и патроны» (1200) mends and sells gold rounds
both: the constants and the trader's rmod as the window reads them, each
repair and restore charged what the window computes from the frames the
server sent, the thing's new break and ceiling on the wire, «Отремонтировать
все» as the client sends it -- a burst, each ack a 0 -- and a press on what
it mended, a broken piece of a set on the body counted again the moment it
is mended, and gold rounds bought at the window's price.

    LAVA_RES=.../lava/res python3 server/test_repair.py
"""
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

DB = os.path.join(tempfile.mkdtemp(), "repair.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import sets  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


cat = items.catalogue()
by_name = {v[1]: k for k, v in cat.items()}
RATE = progression.GOLD_TO_AFRO_RATE
WALTHER = 25636                                     # Walther P99 (A), 2800 afro
GWALTHER = 25637                                    # Walther P99 (G), 0.13 G
GVEST = by_name["armor_Set_M_LVL_8_G_mod00"]        # Бронежилет налетчика (G), 3 G
DEMIR, HASSIR = 5193, 105                           # a registrar alone; one with a stall
PISTOLS, MARKET_CELL = 1200, (5970, 1730)           # «Пистолеты и патроны», Чёрный рынок
SHOCK, OT = 6189, 6140                              # 9мм НАТО (G) ШК, 9мм НАТО (Q) ОТ


# --- the window, transcribed ---------------------------------------------------------
# RepairInterface.as as the client runs it, written out here apart from
# inventory.repair_window, which it checks. Gold in ounces, as the window
# holds it; the checks compare hundredths.
def js_round(x):
    return math.floor(x + 0.5)


def calc_gold(afro_cost, K):
    """calcGoldCostFromAfroCost."""
    g = math.floor(afro_cost / float(K["gold_repair_mod"]) * 100) / 100
    if g < 0.01:
        g = 0.01
    return g


def window(si, brk, top, rmod, K):
    """((afro, gold, restore) of repairCostCount, (afro, gold) of this thing
    in countAllRepairAfroCost / countAllRepairGoldCost or None where their
    `if (cost)` leaves it out). getCurQuality is break / max_break_cur."""
    # Item.getProp("cost") in the patched repair UI, including bulk sums.
    si = dict(si)
    if not si["cost"] and si.get("g_cost"):
        si["cost"] = si["g_cost"] * K["gold_repair_mod"] / 100
    q = brk / float(top)
    loc7 = rmod if not q else rmod * (1 - q)
    loc6 = si.get("repair_mod")
    if loc6 is not None:
        afro = math.floor(loc7 * float(si["cost"]) * loc6)
    else:
        afro = math.floor(loc7 * float(si["cost"]))
    afro = afro if afro != 0 else 1
    restore = (js_round(si["g_cost"] * K["gold_repair_price_mod"]) / 100.0
               if si.get("g_cost") else None)
    share = None
    if si["cost"]:
        mod = rmod
        if loc6 is not None:
            mod *= loc6
        each = math.floor(si["cost"] * mod * (1 - q))
        share = (each, calc_gold(each, K))
    return (afro, calc_gold(afro, K), restore), share


def cents(g):
    return None if g is None else int(round(g * 100))


K_OURS = dict(gold_repair_mod=inventory.GOLD_REPAIR_MOD,
              gold_repair_price_mod=inventory.GOLD_RESTORE_PRICE_MOD)

# --- in process: the figures and the charge -----------------------------------------------
print("the window and the charge")
grid_off, over, parted, agreed_off = [], [], {}, []
for cost in (0, 1, 7, 9, 10, 99, 100, 120, 2800, 12200, 233000, 1234.5):
    for g_cost in (0, 13, 300, 5825):
        for repair_mod in (1, 0.5, 1.3):
            for rmod in (1, 0.5):
                for top in (1, 2, 10, 120, 500, 1250, 4038):
                    for brk in sorted({0, 1, top // 3, top // 2, top * 89 // 100, top - 1}):
                        if brk >= top:
                            continue
                        si = dict(cost=cost, g_cost=g_cost, repair_mod=repair_mod)
                        (a, g, r), share = window(si, brk, top, rmod, K_OURS)
                        want = ((a, cents(g), cents(r)),
                                (share[0], cents(share[1])) if share else (0, 0))
                        got = inventory.repair_window(si, brk, top, rmod)
                        if got != want:
                            grid_off.append((si, brk, top, rmod, got, want))
                        pa, pg, pr = inventory.repair_prices(si, brk, top, rmod)
                        lows = [want[0][:2]] + ([want[1]] if share else [(0, 0)])
                        if any(pa > la or pg > lg for la, lg in lows) or pr != want[0][2]:
                            over.append((si, brk, top, rmod, (pa, pg, pr), lows))
                        if share and share == (a, g) and (pa, pg) != (a, cents(g)):
                            agreed_off.append((si, brk, top, rmod, (pa, pg), (a, g)))
                        if (pa, pg) != want[0][:2]:
                            why = ("no afro price" if not cost else
                                   "under one afro" if want[1][0] == 0 else
                                   "the floors part" if want[1] != want[0][:2] else
                                   "unexplained")
                            parted[why] = parted.get(why, 0) + 1
check("repair_window prints what RepairInterface prints, over the grid", grid_off[:3], [])
check("repair_prices never above the slot's figure or the «все» share, restore the slot's",
      over[:3], [])
check("  ..and exactly the slot's where the two agree", agreed_off[:3], [])
print("      (the charge under the slot's figure: %r)" % parted)
check("  ..below it only for a thing with no afro price, a repair under one afro, or where"
      " the client's two floors themselves part", parted.get("unexplained", 0), 0)

g_vest = items.params_of(GVEST)
check("a broken 3 G vest costs 45000 afro or 0.90 G to repair in the slot and bulk sum",
      (inventory.repair_window(g_vest, 0, 1250), inventory.repair_prices(g_vest, 0, 1250)),
      (((45000, 90, 300), (45000, 90)), (45000, 90, 300)))
check("half-worn gold Walther: 975 afro, or 0.01 G after rounding down; restore 0.13 G",
      inventory.repair_prices(items.params_of(GWALTHER), 250, 500), (975, 1, 13))
check("repair valuation does not enable afro purchases or sales of gold weapons",
      (items.params_of(GWALTHER)["cost"], items.params_of(GWALTHER)["g_cost"]), (0, 13))
check("  ..a repair under one afro: no afro (the slot's 1, the sum's 0), the 0.01 G both print",
      inventory.repair_prices(dict(cost=9, g_cost=0, repair_mod=1), 90, 100), (0, 1, None))

check("the gold button is at par: gold_repair_mod is the one rate",
      (inventory.GOLD_REPAIR_MOD, RATE), (RATE, RATE))
check("  ..so a gold repair is the afro one changed at the rate, rounded down, 0.01 at least",
      [(a, inventory.repair_gold(a)) for a in (1, 499, 500, 999, 1400, 12200, 50000, 233000)],
      [(1, 1), (499, 1), (500, 1), (999, 1), (1400, 2), (12200, 24), (50000, 100), (233000, 466)])
check("  ..never dearer than the afro it stands for, from 0.01 G up",
      [a for a in range(RATE // 100, 3 * RATE, 37) if inventory.repair_gold(a) * RATE // 100 > a],
      [])
check("a repair keeps nine tenths of the ceiling (the original's hint, texts.xml 59813)",
      inventory.REPAIR_KEEPS, 0.9)
check("a repair costs three tenths of the price: a Walther mended from broken for 840 afro,"
      " from half worn for 420, against 2800 for a new one",
      (inventory.RMOD, inventory.repair_prices(items.params_of(WALTHER), 0, 500)[0],
       inventory.repair_prices(items.params_of(WALTHER), 250, 500)[0]), (0.3, 840, 420))

# --- in process: Inventory.repair on a character ---------------------------------------------
print()
print("Inventory.repair")
rstore = accounts.Store(os.path.join(tempfile.mkdtemp(), "mend.db"))
racc, _ = rstore.register("mender", "secret")
rcid, _ = rstore.create_character(racc, "Починщик", 0, 1)
# Enough for a gun mended from broken forty-odd times at its full 2800.
rstore.set_money(rcid, 10000000, 10000)


class Mender:
    """The parts of server.Session that Inventory.repair touches."""
    char_id = rcid

    def __init__(self):
        self.char = progression.Character.load(rstore, rcid)
        self.frames = []

    def character(self):
        return self.char

    def send(self, *cmd, **params):
        self.frames.append((cmd[0], params))

    def send_player_info(self):
        self.send("userInfo_Player", afro=self.char.afro, gold=self.char.gold)

    def say(self, text, group=0):
        self.send("userMsg", entry=text, **{"from": 0})


mender = Mender()
minv = inventory.Inventory(mender, rstore)
minv.trade = inventory.TradeSession(1, PISTOLS)
W_ABS = items.params_of(WALTHER)["max_break_abs"]
G_ABS = g_vest["max_break_abs"]


def thing(type_id, brk, top):
    row = minv.create(type_id)
    rstore.update_item(row["uniq"], brk=brk, max_break_cur=top)
    return rstore.item(row["uniq"])


def press(row, code):
    """(cmdAck codes, frames after them, (brk, top) now, purse paid)."""
    mender.frames = []
    a0, g0 = mender.char.afro, mender.char.gold
    minv.repair({"obj": inventory.oid_of(row)}, code)
    r = rstore.item(row["uniq"])
    return ([p["res"] for n, p in mender.frames if n == "cmdAck"],
            [n for n, _p in mender.frames if n not in ("cmdAck", "userMsg")],
            (r["brk"], r["max_break_cur"]), (a0 - mender.char.afro, g0 - mender.char.gold))


def said():
    return [p["entry"] for n, p in mender.frames if n == "userMsg"]


def short(row, code, afro=None, gold=None):
    """A press with the purse held down for it, and put back as it was: the
    refusal writes nothing, so the saved purse and the ledger never see it."""
    kept = mender.char.afro, mender.char.gold
    if afro is not None:
        mender.char.afro = afro
    if gold is not None:
        mender.char.gold = gold
    try:
        return press(row, code)
    finally:
        mender.char.afro, mender.char.gold = kept


REP, GOLD, RESTORE = inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE
OK, BROKEN = inventory.RES_OK, inventory.RES_BROKEN
MENDED = ["ss_di_firearm", "userInfo_Player"]
gun = thing(WALTHER, W_ABS // 2, W_ABS)
check("Walther half worn, for afro: the window's 420 (rmod 0.3), back to 450 of 450 -- the"
      " ceiling down a tenth; the ack, the thing, the money",
      press(gun, REP), ([OK], MENDED, (450, 450), (420, 0)))
rstore.update_item(gun["uniq"], brk=100)
want_gold = inventory.repair_gold(int(math.floor(inventory.RMOD * (1 - 100 / 450.0) * 2800)))
check("  ..worn to 100 again, for gold: 0.%02d G, and the ceiling falls the same way, to 405"
      % want_gold, press(gun, GOLD), ([OK], MENDED, (405, 405), (0, want_gold)))
rstore.update_item(gun["uniq"], brk=380)
want_light = inventory.repair_prices(items.params_of(WALTHER), 380, 405)[0]
check("  ..at 380 of 405, worn less than a tenth (364): made whole where it stands, 380 of"
      " 380, for the window's %d afro -- no durability taken away, and no refusal the"
      " window has no words for" % want_light,
      (want_light, press(gun, REP)), (51, ([OK], MENDED, (380, 380), (51, 0))))
check("  ..whole, a repair has nothing to do: 0, nothing paid, nothing moves -- what takes"
      " a thing «Отремонтировать все» mended out of the slot",
      press(gun, REP), ([OK], MENDED, (380, 380), (0, 0)))
check("  ..and the same for gold", press(thing(WALTHER, W_ABS, W_ABS), GOLD),
      ([OK], MENDED, (W_ABS, W_ABS), (0, 0)))
tops, steps, dead = [], 0, thing(WALTHER, 0, W_ABS)
while steps < 200:
    rstore.update_item(dead["uniq"], brk=0)
    acks, _f, (b, t), _paid = press(dead, REP)
    steps += 1
    if acks != [OK]:
        break
    tops.append(t)
check("broken and mended over and over: 450, 405, 364 ... the ceiling never reaches 0, and at"
      " 1 the gun is past mending: «Предмет сломан»",
      (tops[:3], tops[-1], acks, rstore.item(dead["uniq"])["max_break_cur"]),
      ([450, 405, 364], 1, [BROKEN], 1))
check("  ..which the chat says, with no restore to offer for a thing with no gold price",
      [("исчерпана" in t, "золото" in t) for t in said()], [(True, False)])
check("  ..and its restore is refused: the window offers none", press(dead, RESTORE)[0],
      [inventory.RES_REFUSED])
check("short of the price, 839 for 840: 21, nothing moves",
      short(thing(WALTHER, 0, W_ABS), REP, afro=839),
      ([inventory.RES_NO_MONEY], [], (0, W_ABS), (0, 0)))

vest = thing(GVEST, G_ABS // 2, G_ABS)
check("gold repairs refuse insufficient afro without changing money or durability",
      short(vest, REP, afro=22499),
      ([inventory.RES_NO_MONEY], [], (625, 1250), (0, 0)))
check("gold repairs refuse insufficient gold without changing money or durability",
      short(vest, GOLD, gold=44),
      ([inventory.RES_NO_MONEY], [], (625, 1250), (0, 0)))
check("the G vest half worn, for afro: 22500,"
      " to 1125 of 1125", press(vest, REP), ([OK], ["ss_di_wear", "userInfo_Player"],
                                             (1125, 1125), (22500, 0)))
rstore.update_item(vest["uniq"], brk=100)
check("  ..for gold: 0.82 G, to 1012", press(vest, GOLD)[2:], ((1012, 1012), (0, 82)))
check("  ..restored for its gold price, 3.00 G, as new: break and ceiling the factory's",
      press(vest, RESTORE), ([OK], ["ss_di_wear", "userInfo_Player"], (G_ABS, G_ABS), (0, 300)))
check("  ..as new, a restore has nothing to do: 0, nothing paid",
      press(vest, RESTORE), ([OK], ["ss_di_wear", "userInfo_Player"], (G_ABS, G_ABS), (0, 0)))
rstore.update_item(vest["uniq"], brk=416)
check("  ..a worn one with its ceiling whole is restored too, as the window offers",
      press(vest, RESTORE)[2:], ((G_ABS, G_ABS), (0, 300)))
worn_out = thing(GVEST, 0, 1)
check("the G vest worn to 0 of 1: past mending, in gold as in afro",
      [press(worn_out, code)[0] for code in (REP, GOLD)], [[BROKEN], [BROKEN]])
check("  ..and the chat offers the restore", ["восстановлением за золото" in t for t in said()],
      [True])
check("  ..a restore short of 3.00 G: 21", short(worn_out, RESTORE, gold=299)[::2],
      ([inventory.RES_NO_MONEY], (0, 1)))
check("  ..with it, as new", press(worn_out, RESTORE)[2:], ((G_ABS, G_ABS), (0, 300)))

minv.trade = inventory.TradeSession(1, DEMIR)
check("Демир registers trophies and mends nothing (can_repair=0): a repair frame at him is"
      " refused", press(thing(WALTHER, 10, W_ABS), REP)[::2], ([inventory.RES_REFUSED], (10, W_ABS)))
minv.trade = inventory.TradeSession(1, HASSIR)
check("  ..Хассир keeps his stall and mends", press(thing(WALTHER, 10, W_ABS), REP)[0], [OK])
minv.trade = inventory.TradeSession(1, PISTOLS)
book = [(r["source"], r["ref"], r["afro"], r["gold"]) for r in rstore.ledger(rcid)
        if r["source"] != "start" and r["ref"] != 0]
check("the ledger: every repair and restore paid for, under «repair» and the thing's type;"
      " presses with nothing to do write nothing",
      (book[:3], len(book), sorted(set(b[0] for b in book)), [b for b in book if b[1] == GVEST]),
      ([("repair", WALTHER, -420, 0), ("repair", WALTHER, 0, -want_gold),
        ("repair", WALTHER, -51, 0)],
       3 + len(tops) + 1 + 5, ["repair"],
       [("repair", GVEST, -22500, 0), ("repair", GVEST, 0, -82)]
       + [("repair", GVEST, 0, -300)] * 3))
rstore.close()

# --- in process: the admin panel's offline gifts ------------------------------------------------
print()
print("the admin panel's gifts to players not in the game")
SHOTGUN = 7072                  # lamantin_shotgun_4: fire_mods [0, 0, 12], mode 0 off
MEDICINE = 6049                 # Med_Pacific_Rest_0_3_A, ten uses
gstore = accounts.Store(os.path.join(tempfile.mkdtemp(), "gifts.db"))
gacc, _ = gstore.register("gifted", "secret")
gcid, _ = gstore.create_character(gacc, "Одарённый", 0, 1)


def bare(type_id):
    """The row apply_admin_action's offline branch wrote before: no fields."""
    return gstore.create_item(gcid, type_id, items.root_of(type_id))


def fields_of(row):
    return (row["brk"], row["max_break_cur"], row["cur_mode"], row["use_count"])


gifts = {t: bare(t) for t in (WALTHER, SHOTGUN, GVEST, MEDICINE)}
# Broken, not bare: its ceiling is there; and one past mending, at 1.
worn = gstore.create_item(gcid, WALTHER, items.FIRE_ARM, brk=0, max_break_cur=W_ABS)
spent = gstore.create_item(gcid, WALTHER, items.FIRE_ARM, brk=0, max_break_cur=1)
posted = bare(WALTHER)
snap = {f: posted[f] for f in accounts.ITEM_FIELDS}
snap.update(uniq=posted["uniq"], type_id=WALTHER, root=items.FIRE_ARM)
gstore.delete_item(posted["uniq"])
letter = gstore.mail_send(gcid, gcid, 0, "подарок", "", 0, 0, json.dumps([snap]))
listed = bare(SHOTGUN)
lsnap = {f: listed[f] for f in accounts.ITEM_FIELDS}
lsnap.update(uniq=listed["uniq"], type_id=SHOTGUN, root=items.FIRE_ARM)
lot = gstore.auction_list(listed["uniq"], gcid, dict(
    type_id=SHOTGUN, root=items.FIRE_ARM, item_json=json.dumps(lsnap), seller=gcid,
    seller_name="Одарённый", currency=0, start_bid=1, buyout=0, fee=0, hours=24,
    created_at=int(time.time()), ends_at=time.time() + 86400))
check("a bare gift is 0 of 0 -- NaN to the client, so no repair window lists it --"
      " a shotgun at the fire mode it has off, a medicine with no uses",
      [fields_of(gifts[t]) for t in (WALTHER, SHOTGUN, GVEST, MEDICINE)],
      [(0, 0, 0, 0)] * 4)
first = accounts.run_once(gstore.db, inventory.OFFLINE_GIFTS_FIX, inventory.fill_offline_gifts)
again = accounts.run_once(gstore.db, inventory.OFFLINE_GIFTS_FIX, inventory.fill_offline_gifts)
S_ABS = items.params_of(SHOTGUN)["max_break_abs"]
check("filled once: each as a new one of its type is (new_fields) -- the shotgun at its first"
      " mode that fires, the medicine at its ten uses; the second start finds it done",
      (first, again, [fields_of(gstore.item(gifts[t]["uniq"]))
                      for t in (WALTHER, SHOTGUN, GVEST, MEDICINE)]),
      (True, False, [(W_ABS, W_ABS, 0, 0), (S_ABS, S_ABS, 2, 0), (G_ABS, G_ABS, 0, 0),
                     (0, 0, 0, 10)]))
check("  ..and the same in a letter and on the auction",
      ([fields_of(s) for s in json.loads(gstore.mail_letter(letter["id"])["items_json"])],
       fields_of(json.loads(gstore.auction_lot(lot["id"])["item_json"]))),
      ([(W_ABS, W_ABS, 0, 0)], (S_ABS, S_ABS, 2, 0)))
check("  ..a broken gun keeps its wear, and one past mending its ceiling of 1",
      [fields_of(gstore.item(r["uniq"])) for r in (worn, spent)],
      [(0, W_ABS, 0, 0), (0, 1, 0, 0)])
gstore.close()

# --- in process: gold rounds -------------------------------------------------------------------
print()
print("gold rounds")
rounds = {t: items.params_of(t) for t, (root, _n) in cat.items() if root == items.AMMO}
gold = sorted(t for t, p in rounds.items() if items.gold_round(p))
check("43 kinds of round are gold -- priced in gold alone, not premium: (G) ЭК, ББ, СБ, ШК"
      " and the prison's (Q) ОТ", (len(gold), sorted({cat[t][1].split("_")[-2] if t != SHOCK
                                                      else "shock" for t in gold})),
      (43, ["BB", "EK", "OT", "SB", "shock"]))
check("  ..every one a hundredth of an ounce a round: a pack of sell_num at sell_num hundredths",
      [t for t in gold if rounds[t]["g_cost"] != items.GOLD_AMMO_ROUND * rounds[t]["sell_num"]
       or items.GOLD_AMMO_ROUND != 1], [])
wiki = items.wiki()
check("  ..in place of the wiki's 0.10 G (ЭК, ББ, ОТ, ШК) and 0.20 G (СБ) a round",
      sorted({(cat[t][1].split("_")[-2], wiki[t]["g_cost"]) for t in gold if t in wiki
              and t != SHOCK} | {("shock", wiki[SHOCK]["g_cost"])}),
      [("BB", 10), ("EK", 10), ("OT", 10), ("SB", 20), ("shock", 10)])
check("  ..ЭК(G) 9мм: the pack of 20 was 2 G, now 0.20 G; the tooltip's 0.01 G",
      (rounds[6152]["g_cost"], rounds[6152]["sell_num"],
       inventory.js_round(rounds[6152]["g_cost"] / float(rounds[6152]["sell_num"]))), (20, 20, 1))
check("  ..bought at a hundredth a round, 5000 for 50 G",
      [inventory.buy_price(rounds[t], items.AMMO, n, True) for t in (6152, 6179, OT)
       for n in (1, 7, 20, 5000)], [1, 7, 20, 5000] * 3)
check("the premium КС keep their 2 G a pack, out of the game; the 9мм даренные their 0.20 G"
      " and 20 afro; the stun bolts, the snowballs and «Бьют прямо в сердце» both prices",
      ([(rounds[t]["cost"], rounds[t]["g_cost"], rounds[t]["premium"]) for t in (6128, 6188)],
       [(rounds[t]["cost"], rounds[t]["g_cost"]) for t in (4780, 3819, 6201)]),
      ([(0, 200, 1), (20, 20, 0)], [(20, 20), (2000, 2000), (20000, 300)]))
check("«Пистолеты и патроны» sells gold rounds at a hundredth a round",
      [(t, inventory.buy_price(rounds[t], items.AMMO, 1, True))
       for t in items.stock_for(PISTOLS) if t in rounds and items.gold_round(rounds[t])],
      [(t, 1) for t in items.stock_for(PISTOLS) if t in rounds and items.gold_round(rounds[t])])


# --- over the socket ---------------------------------------------------------------------------
print()
print("on the wire")


def free_port():
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


PORT = free_port()
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("fixer", "secret")
# A bare gift of the old admin panel, there before the server starts: its
# start fills it (server.main, OFFLINE_GIFTS_FIX).
_gacc, _ = _store.register("giftee", "secret")
_gcid, _ = _store.create_character(_gacc, "Одарённый", 0, 1)
_bare_gift = _store.create_item(_gcid, WALTHER, items.FIRE_ARM)["uniq"]
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_POLICY_PORT="0", LAVA_GX=str(MARKET_CELL[0]), LAVA_GY=str(MARKET_CELL[1]))
for _knob in ("LAVA_LOC", "LAVA_CHEATS", "LAVA_START", "LAVA_DB_URL"):
    env.pop(_knob, None)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def until(self, name, timeout=15):
        got = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            got += self.frames(0.3)
            if any(n == name for n, _p in got):
                return got + self.frames(0.6)
        return got


def named(frames, name):
    return [p for n, p in frames if n == name]


def enter(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential("fixer", "secret"))
    got = c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@fixer@;")
        got += c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    got += c.until("lcall")
    c.send("lenter;accept=1;")
    return got + c.until("lenter")


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()


SI_OF = {items.FIRE_ARM: "ss_si_firearm", items.WEAR: "ss_si_wear", items.AMMO: "ss_si_ammo"}
DI_OF = {items.FIRE_ARM: "ss_di_firearm", items.WEAR: "ss_di_wear"}

try:
    c = Client(connect())
    enter(c, first=True)
    leave(c)
    time.sleep(0.5)
    st = accounts.Store(DB)
    gift = st.item(_bare_gift)
    check("the server's start filled the old panel's bare gift: 500 of 500, once",
          ((gift["brk"], gift["max_break_cur"]), [r["name"] for r in st.db.execute(
              "SELECT name FROM migrations WHERE name = ?",
              (inventory.OFFLINE_GIFTS_FIX,)).fetchall()]),
          ((W_ABS, W_ABS), [inventory.OFFLINE_GIFTS_FIX]))
    cid = st.db.execute("SELECT id FROM characters WHERE name = ?", ("fixer",)).fetchone()["id"]
    # Level 8, so the two pieces of Налетчик (G) below stay on the body at
    # the login (inventory.over_level_to_bag).
    ch = progression.Character.load(st, cid)
    ch.skill[progression.SHOOTING] = [8, 0, progression.skill_xp_max(8)]
    ch.recalc()
    ch.save(st)
    st.set_money(cid, 100000, 10000)
    CASES = [("Walther half worn, afro", WALTHER, W_ABS // 2, W_ABS, REP),
             ("Walther a third worn, gold", WALTHER, W_ABS * 2 // 3, W_ABS, GOLD),
             ("Walther at 96%, afro", WALTHER, W_ABS * 96 // 100, W_ABS, REP),
             ("G vest half worn, afro", GVEST, G_ABS // 2, G_ABS, REP),
             ("G vest half worn, gold", GVEST, G_ABS // 2, G_ABS, GOLD),
             ("G vest sagged, restore", GVEST, G_ABS // 3, G_ABS - G_ABS // 5, RESTORE),
             ("G vest 0 of 1, restore", GVEST, 0, 1, RESTORE),
             ("G Walther half worn, afro", GWALTHER, 250, 500, REP),
             ("G Walther half worn, gold", GWALTHER, 250, 500, GOLD)]
    made = []
    for label, t, brk, top, code in CASES:
        f = inventory.new_fields(t)
        f.update(brk=brk, max_break_cur=top)
        made.append(st.create_item(cid, t, f.pop("root"), **f))
    # For «Отремонтировать все»: a gun lightly worn, one badly, and one
    # past mending.
    burst = []
    for brk, top in ((W_ABS - 20, W_ABS), (100, W_ABS), (0, 1)):
        f = inventory.new_fields(WALTHER)
        f.update(brk=brk, max_break_cur=top)
        burst.append(st.create_item(cid, WALTHER, f.pop("root"), **f))
    f = inventory.new_fields(GWALTHER)
    f.update(brk=250, max_break_cur=500)
    bulk_gold = st.create_item(cid, GWALTHER, f.pop("root"), **f)
    # On the body: Налетчик (G)'s helmet whole and its vest broken, one
    # piece of the set that counts (a broken one does not, sets.pieces).
    body = {}
    for t, slot, brk in ((by_name["helm_Set_M_LVL_8_G_mod00"], inventory.HEAD, None),
                         (GVEST, inventory.ARMOR, 0)):
        f = inventory.new_fields(t)
        f.update(slot=slot)
        if brk is not None:
            f.update(brk=brk)
        body[slot] = st.create_item(cid, t, f.pop("root"), **f)
    st.close()

    c = Client(connect())
    arrival = enter(c)
    K = (named(arrival, "constants") or [{}])[0]
    check("the constants frame: the gold divisor at the one rate, the restore's at 1",
          (K.get("gold_repair_mod"), K.get("gold_repair_price_mod"), K.get("gold_to_afro_rate")),
          (RATE, 1, RATE))
    shop = [p for p in named(arrival, "userInfo_Trader") if p.get("res") == PISTOLS]
    check("«Пистолеты и патроны» on the black market trades and mends, rmod 0.3",
          [(p.get("can_trade"), p.get("can_repair"), p.get("rmod")) for p in shop], [(1, 1, 0.3)])
    shop = shop[0] if shop else {}
    si = {}
    for t in (WALTHER, GWALTHER, GVEST, SHOCK, OT):
        cmd = SI_OF[items.root_of(t)]
        c.send("ss_get_si;type=%d;" % t)
        si[t] = (named(c.until(cmd), cmd) or [{}])[0]
    c.send("ss_create;s_type=1;target=%d;" % shop.get("id", 0))
    check("the stall opens", named(c.frames(), "cmdAck"), [{"res": 0}])

    def purse():
        c.send("getInfo;lvl=0;id=0;type=0;")
        p = named(c.until("userInfo_Player"), "userInfo_Player")[-1]
        return p["afro"], p["gold"]

    results, wants = {}, {}
    for (label, t, brk, top, code), row in zip(CASES, made):
        obj = inventory.oid_of(row)
        cmd = DI_OF[items.root_of(t)]
        c.send("ss_get_di;obj=x%s;" % obj)
        di = named(c.until(cmd), cmd)[-1]
        (a, g, r), share = window(si[t], di["break"], di["max_break_cur"], shop["rmod"], K)
        a0, g0 = purse()
        c.send("ss_upd;s_status=%d;obj=x%s;" % (code, obj))
        got = c.frames(0.8)
        a1, g1 = purse()
        after = [(p.get("break"), p.get("max_break_cur")) for p in named(got, cmd)]
        results[label] = ([p.get("res") for p in named(got, "cmdAck")], (a0 - a1, g0 - g1), after)
        # What the window printed, and so what may be charged: the restore's
        # one figure; for a repair the lower of the slot's and the thing's
        # share of «Отремонтировать все» -- nothing for one the sums leave out.
        if code == RESTORE:
            pay = (0, cents(r))
        elif code == GOLD:
            pay = (0, min(cents(g), cents(share[1])) if share else 0)
        else:
            pay = (min(a, share[0]) if share else 0, 0)
        abs_top = si[t]["max_break_abs"]
        new = (abs_top, abs_top) if code == RESTORE else (max(int(top * 0.9), brk),) * 2
        wants[label] = ([0], pay, [new])
    check("each press charged what the window computes from the frames, and the thing came"
          " back as the rule says", results, wants)
    check("  ..in figures: 420 afro, 0.01 G, 33 afro (made whole at 480), 22500 afro, 0.45 G,"
          " 3.00 G, 3.00 G, 975 afro, 0.01 G", [results[label][1] for label, *_r in CASES],
          [(420, 0), (0, 1), (33, 0), (22500, 0), (0, 45), (0, 300), (0, 300),
           (975, 0), (0, 1)])

    # «Отремонтировать все», as the client sends it: every listed thing's
    # ss_upd at once, then one repAck per answer, each a 0 or the list
    # stops (RepairInterface.repAllAck). A lightly worn gun among them is
    # mended like the rest; the sum charged is the dialog's.
    shares = [window(si[WALTHER], r["brk"], r["max_break_cur"], shop["rmod"], K)[1][0]
              for r in burst[:2]]
    shares.append(window(si[GWALTHER], 250, 500, shop["rmod"], K)[1][0])
    a0, g0 = purse()
    for r in burst[:2] + [bulk_gold]:
        c.send("ss_upd;s_status=3;obj=x%s;" % inventory.oid_of(r))
    got = c.frames(1.2)
    a1, g1 = purse()
    check("«Отремонтировать все» over guns at %d of %d and 100, plus half-worn gold Walther:"
          " three acks, the dialog's %d afro, all whole" % (W_ABS - 20, W_ABS, sum(shares)),
          ([p.get("res") for p in named(got, "cmdAck")], (a0 - a1, g0 - g1),
           [(p["break"], p["max_break_cur"]) for p in named(got, "ss_di_firearm")]),
          ([0, 0, 0], (sum(shares), 0), [(W_ABS - 20, W_ABS - 20), (450, 450), (450, 450)]))
    c.send("ss_upd;s_status=3;obj=x%s;" % inventory.oid_of(burst[1]))
    got = c.frames(0.8)
    check("  ..pressed again from a list left standing: 0, nothing charged",
          ([p.get("res") for p in named(got, "cmdAck")], purse() == (a1, g1)), ([0], True))
    c.send("ss_upd;s_status=3;obj=x%s;" % inventory.oid_of(burst[2]))
    got = c.frames(0.8)
    check("  ..a gun at 0 of 1, past mending: «Предмет сломан» (16), nothing charged",
          ([p.get("res") for p in named(got, "cmdAck")], purse() == (a1, g1)), ([16], True))

    # The broken vest on the body, mended: the set counts two pieces again at
    # once (ss_upd is one of server.GEAR_COMMANDS), and its second bonus --
    # stamina -- reaches the bars by usrUp after the ack.
    c.send("getInfo;lvl=0;id=0;type=0;")
    smax = [p["smax"] for p in named(c.until("usrUp"), "usrUp") if "smax" in p]
    c.send("ss_upd;s_status=3;obj=x%s;" % inventory.oid_of(body[inventory.ARMOR]))
    got = c.frames(0.8)
    order = [n for n, _p in got if n in ("cmdAck", "ss_di_wear", "usrUp")]
    check("a broken piece of Налетчик (G) on the body, mended: the ack, the piece at nine"
          " tenths, then the set's second bonus, %d stamina more"
          % sets.frame(sets.set_of(GVEST))["bonus_2_st"],
          ([p.get("res") for p in named(got, "cmdAck")],
           [(p["break"], p["max_break_cur"]) for p in named(got, "ss_di_wear")],
           order[:2], [p["smax"] - smax[-1] for p in named(got, "usrUp") if smax]),
          ([0], [(G_ABS * 9 // 10,) * 2], ["cmdAck", "ss_di_wear"],
           [sets.frame(sets.set_of(GVEST))["bonus_2_st"]]))

    stock = list(shop.get("type_list") or [])
    bought = {}
    for t, n in ((SHOCK, 100), (OT, 20)):
        p = si[t]
        shown = math.ceil(js_round(p["g_cost"] / float(p["sell_num"])) * n * shop["pmod"])
        a0, g0 = purse()
        c.send("ss_upd;s_status=4;obj=x%x;param=%d;" % (stock.index(t), n))
        acks = [q.get("res") for q in named(c.frames(0.8), "cmdAck")]
        a1, g1 = purse()
        bought[t] = (p.get("g_cost"), p.get("sell_num"), p.get("cost"), shown, acks, (a0 - a1, g0 - g1))
    check("gold rounds at the stall: a pack of 20 at 0.20 G, and 100 ШК for 1.00 G, 20 ОТ for"
          " 0.20 G -- what the «Сколько штук купить?» window asks, taken",
          bought, {SHOCK: (20, 20, 0, 100, [0], (0, 100)), OT: (20, 20, 0, 20, [0], (0, 20))})
    c.send("ss_upd;s_status=0;obj=x0;")
    leave(c)

    st = accounts.Store(DB)
    book = [(r["source"], r["ref"], r["afro"], r["gold"]) for r in st.ledger(cid)
            if r["source"] in ("repair", "shop_buy")]
    st.close()
    check("the ledger has each of them, and no row for a press"
          " with nothing to do",
          book, [("repair", WALTHER, -420, 0), ("repair", WALTHER, 0, -1),
                 ("repair", WALTHER, -33, 0),
                 ("repair", GVEST, -22500, 0), ("repair", GVEST, 0, -45),
                 ("repair", GVEST, 0, -300), ("repair", GVEST, 0, -300),
                 ("repair", GWALTHER, -975, 0), ("repair", GWALTHER, 0, -1),
                 ("repair", WALTHER, -33, 0), ("repair", WALTHER, -672, 0),
                 ("repair", GWALTHER, -975, 0),
                 ("repair", GVEST, -45000, 0),
                 ("shop_buy", SHOCK, 0, -100), ("shop_buy", OT, 0, -20)])
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-6000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("repair OK")
