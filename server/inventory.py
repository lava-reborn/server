"""Item instances: the bag, the eight slots, a stall, and loading a gun.

Everything the client does with an item goes through an instance id on the
wire, and the client takes the item's class and type out of that id rather
than out of any frame name, so the id layout is the contract this module is
built around.

The oid, as the client reads it
-------------------------------

    <uniq hex><type_id: exactly 4 hex><root: exactly 2 hex>

ItemFactory.create hands the string to MDString.parseBigUINT(oid, 4, 2), which
slices from the END: the last 2 characters become the root class, the 4 before
them the type id, and whatever is left in front, `buint.slice(0, length-6)`,
is the serial, read as Number("0x" + rest). Three things follow:

  * The serial has no fixed width. One hex digit is the minimum, because
    Number("0x") is NaN, and StuffManager.createItem drops any id shorter
    than two characters or equal to "0" anyway. There is no maximum short of
    the double the client parses into, exact to 2^53; the rowid used here
    stays many orders below that.
  * Item.set id also computes uID = Number(oid.substr(0, length-6)) -- a
    DECIMAL parse of the same hex serial, NaN whenever a letter appears.
    uID is written there and read nowhere (grepped across all 395 classes),
    so it costs nothing, but it is why the layout is hex-with-fixed-tail and
    not something friendlier.
  * The client never rebuilds the id: BigUINT.toString prefixes "x" and
    concatenates the clusters, and BigUINTCluster(oid) with no size calls
    toString(16) on a String, which returns it unchanged. What is sent back
    in ss_get_di/ss_move/ss_use is byte for byte what ss_ack carried. The
    parser strips the "x" (SCDataParser.getBigUINTData) and keys
    ItemFactory.itemStore on the rest, so every ss_di_*/ss_obj_status frame
    must spell the id exactly as the list did: lowercase, no padding of the
    serial, type and root zero-padded to 4 and 2.

An empty slot is the element "0" (sent as x0): createItem skips it, and the
bank and loot windows treat the first "0" after the bag as the divider
between the bag and the session's own contents.

Containers, in the order ss_ack must list them (PersEquip.ss_ack)
--------------------------------------------------------------

The client reads the ss_ack list against the mask it sent in ss_get -- not
against anything in the frame -- and slices in a fixed order:

    bit 1   splice(0, 6)   head, camouflage, armor, belt, legs, boots
    bit 2   splice(0, 2)   primary, secondary
    bit 8   the rest       bag
    bit 16  Bank/Loot: everything after the first "0" is the session

A slot code in ss_move/ss_obj_move is maskIndex << 8 | index, which gives the
numbers below (PersEquip constructor).

The bank (Хранилище)
--------------------

One storage per character, shared by every city bank: its rows are ordinary
items rows with slot BANK (16 << 8, the session bit), so nothing new is
needed to keep them, and a stored thing keeps its oid -- the client takes an
item back out under the very id it put it in with. The code never reaches
the wire: the bank window addresses a stored thing by its oid alone and
never sends ss_move, and find() does not see these rows at all, so selling,
posting, using, splitting or moving one is refused as "not found" by the
same check that refuses somebody else's item. They are not carried weight
and are not in the backpack the corpse drops from.
"""
import asyncio
import contextlib
import json
import logging
import math
import os
import random

import items
import pace
import progression
import quests
import sets
import setcraft
import trophies
import world
from protocol import BigUInt, Str

log = logging.getLogger("lava")

# --- the oid ----------------------------------------------------------------

def oid(uniq, type_id, root):
    return "%x%04x%02x" % (uniq, type_id, root)


def oid_of(row):
    return oid(row["uniq"], row["type_id"], row["root"])


def parse_oid(text):
    """(uniq, type_id, root) from a wire id without its "x", or None."""
    text = str(text or "").strip().lower()
    if len(text) < 7:
        return None
    try:
        return int(text[:-6], 16), int(text[-6:-2], 16), int(text[-2:], 16)
    except ValueError:
        return None


EMPTY = BigUInt("0")

# --- containers -------------------------------------------------------------

HEAD, CAMO, ARMOR, BELT, LEGS, BOOTS = 256, 257, 258, 259, 260, 261
PRIMARY, SECONDARY = 512, 513
BAG = 2048

WEAR_SLOTS = (HEAD, CAMO, ARMOR, BELT, LEGS, BOOTS)
HAND_SLOTS = (PRIMARY, SECONDARY)
# On the character rather than in the bag: what the level rule guards.
BODY_SLOTS = WEAR_SLOTS + HAND_SLOTS
# The five a clothing set is counted over (PersEquip.getNumOfSetItem): the
# belt is never one of them.
SET_SLOTS = (HEAD, CAMO, ARMOR, LEGS, BOOTS)

# ss_get masks (Bag/Slot.maskIndex in the PersEquip constructor)
MASK_WEAR, MASK_HANDS, MASK_BAG, MASK_SESSION = 1, 2, 8, 16

# Carry limit in grams. rp_info sends the same figure as max_weight; the
# client only warns from it, the refusal is ours (WeightPan.count sums the
# bag and all eight slots, so the total here does the same).
MAX_WEIGHT = 50000

# Trader multipliers, as sent in userInfo_Trader (server.send_npc_info). The
# client multiplies prices by them before it shows them, so a change on one
# side without the other shows one price and charges another.
# Which piece of clothing a blow lands on. Seeded from the environment like
# combat's own, so a test that fixes LAVA_SEED gets the same wear twice.
RNG = (random.Random(int(os.environ["LAVA_SEED"])) if os.environ.get("LAVA_SEED")
       else random.Random())

PMOD = 1
# What the trader pays back. The owner's rule: a thing loses three tenths of
# its worth the moment it is bought, and after that it is worth whatever is
# left of it -- the quality factor in sell() carries the rest.
#
# It has to be a number the CLIENT is told rather than a discount applied
# behind its back: ItemContainer.showCost multiplies by smod itself before it
# draws the price, so a server that sent one number and charged another would
# be showing the player a lie.
SMOD = 0.7
# Whether a stall buys a thing priced in gold alone (cost 0, g_cost > 0) for
# afro: its gold price at the one rate (progression.GOLD_TO_AFRO_RATE), then
# SMOD and the quality as any sale. Off (2026-09-28, with the rate at
# 50 000): the shipped client never offers such a sale -- TradeInterface.
# checkSellItem answers cost 0 with «Вы не можете продать некоторые
# предметы» before anything is sent -- and the wiki marks 426 of 437 G
# columns «Допустимость продажи/обмена: Нет». At the rate a G thing got
# for nothing (a quest's reward, a drop) would sell for ten to twelve times
# its afro twin, a tap of afro only a patched client reaches. True turns
# the sale back on.
SELL_GOLD_ONLY = False
# The repair multiplier, likewise sent and likewise obeyed:
# RepairInterface.repairCostCount draws floor(rmod * (1-q) * cost * repair_mod).
# At 1 a thing worn to nothing cost its whole price to mend, a Walther P99
# 2800 afro, and came back with nine tenths of its ceiling (REPAIR_KEEPS):
# never cheaper than a new one, so nobody had a reason to mend anything.
# Neither rmod nor any type's repair_mod survives from the original; this
# one figure, sent with every trader, sets the price for every thing:
# three tenths of the price for a gun mended from broken, 840 afro for the
# P99. LAVA_REPAIR_MOD moves it.
RMOD = float(os.environ.get("LAVA_REPAIR_MOD", "0.3"))
# What a repair leaves of the ceiling (max_break_cur), whichever currency
# pays for it. The original says so in its own words, the hint of «Мертвые
# беззащитны» (texts.xml 59813; quest 23 here, Ибрахим's in the valley,
# whose start the player reads): «При ремонте экипировка чинится на 90%
# от своего предыдущего максимума. Как следствие, чем чаще вы
# ремонтируете снаряжение, тем быстрее оно станет не ремонтопригодным.»
# So a repair brings the thing up to nine tenths of the ceiling it had,
# rounded down, and that is its ceiling from then on; the wiki's «Ремонт»
# adds that once it is worn to nothing and «ремонт не возможен, то предмет
# можно восстановить только за Голд» (UPD_RESTORE). It used to be two per
# cent of the factory ceiling per afro repair and nothing at all for a gold
# one: neither is the original's, and the game's own hint told the player
# the rule it did not keep.
#
# A thing worn by less than a tenth is made whole where it stands: its
# ceiling comes down to its durability, which is less than the tenth, and
# the durability stays. The hint read to the letter would bring it DOWN to
# nine tenths, a repair that takes durability away; refusing it instead is
# worse on the client: the window lists such a thing, prices it and
# enables both buttons, a refusal is a press that does nothing, and in
# «Отремонтировать все» any answer but 0 puts up «Некоторые предметы не
# удалось отремонтировать» and leaves the rest of the list standing though
# mended (RepairInterface.repAllAck). DESIGNED (2026-09-29); the literal
# reading is Inventory.repair without the max() that keeps the durability.
REPAIR_KEEPS = 0.9
# What the client divides an afro repair by to price it in gold, sent in the
# constants frame (server.py, gold_repair_mod; GConstatns falls back to
# 10000 when it is missing): the patched button asks round(afro / this * 100)
# hundredths of an ounce. The intent is par -- the same repair paid in the
# other currency, at the game's one rate (progression.GOLD_TO_AFRO_RATE):
#
#   * the original offers the two as one service, «Ремонт можно произвести
#     как и за Афро так и за Голд» (the wiki's «Ремонт»), and its hint gives
#     every repair the same ceiling rule (REPAIR_KEEPS), whatever it is
#     paid with -- there is no repair that spares the ceiling to charge a
#     premium for;
#   * the one figure the original gives for gold against afro is its rate,
#     «по официальному курсу 1 голд – 40000 афро» (the wiki's «Покупка
#     голд»), and a divisor equal to the rate is exactly par;
#   * «Обмен золота на афро» (c_ga) changes gold at the rate anywhere, so a
#     divisor under it only makes the gold button a worse way to pay the
#     same afro: 40 000 against the rate of 50 000 (the figure set when the
#     rate moved, 2026-09-28) asked a quarter more than changing the gold
#     and pressing the afro button, 10 000 (GConstatns' own default) five
#     times as much.
#
# Round to the nearest hundredth, positive halves up, with a 0.01 minimum.
# The original floor nearly halved some prices: 975 afro is 0.0195 G,
# formerly displayed and charged as 0.01 G. The owner's rule (2026-10-05)
# makes it 0.02 G in both the slot and repair-all, on client and server.
GOLD_REPAIR_MOD = progression.GOLD_TO_AFRO_RATE
# The restore button's price, sent as gold_repair_price_mod (GConstatns
# keeps it as gold_restore_price_mod): the window shows
# Math.round(g_cost * mod) / 100 ounces for anything with a g_cost, whatever
# its wear, and offers no restore for anything without
# (RepairInterface.repairCostCount). At 1 a restore costs the thing's gold
# price -- a new one, but this one kept, its modification with it -- and
# makes it as new (Inventory.repair). The server sent 1 before; no source
# gives the original's figure.
GOLD_RESTORE_PRICE_MOD = 1

# cmdAck codes the client words (ErrorReport.as:58-81)
RES_OK = 0
RES_REFUSED = 3
RES_NO_AP = 11
RES_NOT_FOUND = 12
RES_NO_AMMO = 13
RES_WRONG_AMMO = 14
RES_LOADED = 15
RES_BROKEN = 16
RES_NOT_READY = 17
RES_NO_ITEM = 19
RES_NO_MONEY = 21
RES_OVERLOAD = 27
# "У вас не хватает навыков для использования этого предмета." -- the words
# the client has for a thing the character is not up to, and the refusal of
# the level rule (below); the chat names the two levels.
RES_LEVEL = progression.ERR_SKILL
# And one it does not word, so it puts nothing up: for a refusal the chat
# explains better than any of the texts above (barter.RES_CANT is the same).
RES_UNWORDED = 31

# ss_use bits (Item.set actions)
USE_DELETE, USE_LOAD, USE_IDLE, USE_TARGET = 0, 1, 2, 4
USE_ITEM, USE_FIRE, USE_UNLOAD, USE_MODE = 8, 16, 32, 64

# ss_upd codes inside a trade session (Trade.as:11-19)
UPD_CLOSE, UPD_BUY, UPD_SELL, UPD_REPAIR = 0, 1, 2, 3
UPD_BUY_GOLD, UPD_REPAIR_GOLD, UPD_REG_TROPHY, UPD_RESTORE = 4, 5, 6, 7
UPD_BGPOINTS_BUY = 8

SESSION_TRADE = 1

# --- the bank: ss_create s_type=3 --------------------------------------------
SESSION_BANK = 3                # StuffManager.SESSION_BANK
# ss_upd codes in a bank session (Bank.as:13-18). 3 and 4 only ever travel
# from the server: Bank.ss_upd reads them as the capacity and the load.
BANK_CLOSE, BANK_PUT, BANK_GET, BANK_MAX, BANK_CUR, BANK_INCREASE = 0, 1, 2, 3, 4, 6
# The slot code of a stored row: the session bit, the way BAG is the bag's.
BANK = MASK_SESSION << 8        # 4096
# Capacity in grams. The base is ours to choose -- neither the client, nor
# texts.xml, nor the wiki names one -- and the owner settled on 50 kg, the
# same figure a character carries. The step and its price are not: the bank
# window says in its own text (main.swf, sprite "bankInterface", DefineText
# 716) "Вы можете увеличить размер хранилища на 50 кг за 1 унцию", so every
# ounce paid buys exactly 50 kg, with no ceiling on how many are bought.
BANK_BASE = int(os.environ.get("LAVA_BANK_BASE", "50000"))
BANK_STEP = 50000
BANK_STEP_GOLD = 100            # one ounce: gold travels in hundredths
# A put that does not fit. ErrorReport has no text for 28, so the window
# shows nothing and the reason goes to chat: a worded code would name some
# other failure.
RES_BANK_FULL = 28
# Which inhabitants are banks. Kept here, not in data/npcs.json, because
# tools/npc_editor.py rewrites that file with only the keys it knows and
# would drop a new one. These are the four city banks the wiki describes as
# "Хранилище -- личный банк": the Nubian market's safe (5228), the black
# markets' and Maghreb's (2424), the banker 729 (the Wadi Halfa market, the
# Dongola and Abu Hamed stations, the township, the equipment exchange) and
# Abri's (1170). Clan banks, quest safes and the rest keep their other
# meanings. A type added here must be in names.ALL: its name travels as the
# type id.
BANK_TYPES = frozenset({5228, 2424, 729, 1170})


def is_bank(type_id):
    """Whether an inhabitant of this type opens the personal storage."""
    return type_id in BANK_TYPES


# Which ss_di_* frame describes an instance. ItemFactory registers all six
# and routes each to the same updateItemDI, so the name is documentation
# more than dispatch; the fields are what matters (items.md 1.2).
DI_COMMAND = {
    items.FIRE_ARM: "ss_di_firearm",
    items.WEAR: "ss_di_wear",
    items.HEAL: "ss_di_heal",
    items.AMMO: "ss_di_heap",
    items.TRASH: "ss_di_heap",
    items.COLD_ARM: "ss_di_coldarm",
    items.TROPHY: "ss_di_trophy",
}

# What a fresh character owns, and neither half of it is ours to pick.
#
# The wiki article on the Самострел says in as many words that it is the
# pistol handed out at the very start of the game, and the same article names
# its calibre as "9мм даренные". It used to be 4380 here -- a synthetic gun
# with no article, no name and no numbers of its own, which reached the player
# as the bare string "pistols_1" and a placeholder description.
#
# The pair is indivisible, and swapping one without the other breaks both:
# the Самострел's comp_array is the ten 9mmNato_* records ending in 6188 and
# holds no ordinary 9мм НАТО at all, so load() would answer RES_WRONG_AMMO
# either way round.
STARTER_PISTOL = 25562          # pistols_1_lvl_0, "Самострел", a clip of five
STARTER_AMMO = 6188             # "9мм даренные", sold twenty to the pack
STARTER_KIT = ((STARTER_PISTOL, 1), (STARTER_AMMO, items.AMMO_PACK))

# The gun goes into the hand, not the bag. Firing and striking both refuse
# anything whose slot is not PRIMARY, so a newborn whose pistol lies in the
# bag meets his first dog with his fists and no way of knowing why.
STARTER_SLOT = {STARTER_PISTOL: PRIMARY}


def di_params(row, store=None):
    """The dynamic fields of one instance, keyed as the client reads them.

    updateProperties copies every key onto the object as is, except "break",
    which lands in __break. cur_mode is mandatory for a firearm: getAP reads
    fire_costs[cur_mode], and an undefined there makes canUse refuse every
    shot in a battle location. A trophy adds who killed whom and when, from
    the store (trophies.di_fields).
    """
    root = row["root"]
    p = {"obj": BigUInt(oid_of(row))}
    if root in items.HEAPABLE_ROOTS:
        p["size"] = row["count"]
    elif root == items.HEAL:
        p["use_count"] = row["use_count"]
    elif root == items.TROPHY:
        p["count"] = row["count"]
        if store is not None:
            p.update(trophies.di_fields(store, row["uniq"]))
    else:
        p["break"] = row["brk"]
        p["max_break_cur"] = row["max_break_cur"]
        if root == items.FIRE_ARM:
            p["ammo_count"] = row["ammo_count"]
            p["ammo_type"] = row["ammo_type"]
            p["cur_mode"] = row["cur_mode"]
    return p


def new_fields(type_id, count=1):
    """Column values for a factory-fresh instance of a type."""
    root = items.root_of(type_id)
    si = items.params_of(type_id) or {}
    f = {"root": root, "slot": BAG, "count": 1}
    if root in items.HEAPABLE_ROOTS:
        f["count"] = max(1, min(int(count), si.get("max_count", 1)))
    elif root == items.HEAL:
        f["use_count"] = si.get("use_count", 1)
    elif root in items.BREAKABLE_ROOTS:
        f["brk"] = f["max_break_cur"] = si.get("max_break_abs", 100)
        if root == items.FIRE_ARM:
            f["cur_mode"] = items.first_mode(si.get("fire_mods", [1]))
    return f


# The admin panel's «give item» to a character not in the game wrote a bare
# row until 2026-09-29 (server.apply_admin_action), every dynamic column at
# its default 0 where the one given to a player in the game had new_fields:
# a gun or a set piece at 0 of 0, which the client reads as NaN -- no repair
# window lists it (PersEquip.getBreakedItems), no stall buys it -- a firearm
# at a fire mode that may be off, a medicine with no uses. Filled once per
# database at the server's start (server.main, accounts.run_once), letters
# and lots included, as accounts.relink_heals does its types.
OFFLINE_GIFTS_FIX = "admin-offline-gifts-2026-09-29"


def unfilled(row):
    """{column: value} a bare row of the offline gift (OFFLINE_GIFTS_FIX)
    lacks against a factory-fresh one of its type, {} for any other row. A
    row or a letter's or a lot's snapshot of one (mail.snapshot).

    Nothing else leaves these shapes behind: wear stops at 0 and a repair
    at a ceiling of 1, so a breakable thing at a ceiling of 0 is one that
    never had one -- unless its type has none (max_break_abs 0, a thing
    that does not wear), which new_fields leaves at 0 too; and a medicine
    used up is deleted (combat.use_heal)."""
    si = items.params_of(row["type_id"])
    if si is None:
        return {}
    fresh = new_fields(row["type_id"])
    if fresh["root"] != row["root"]:
        return {}
    if row["root"] in items.BREAKABLE_ROOTS:
        if row["max_break_cur"] or not fresh["max_break_cur"]:
            return {}
        fix = dict(brk=fresh["brk"], max_break_cur=fresh["max_break_cur"])
        mods = si.get("fire_mods", [1])
        if row["root"] == items.FIRE_ARM \
                and not (0 <= row["cur_mode"] < len(mods) and mods[row["cur_mode"]]):
            fix["cur_mode"] = fresh["cur_mode"]
        return fix
    if row["root"] == items.HEAL and row["use_count"] <= 0 < fresh["use_count"]:
        return dict(use_count=fresh["use_count"])
    return {}


def fill_offline_gifts(db):
    """OFFLINE_GIFTS_FIX on a database: every row unfilled() finds in items,
    and in the snapshots letters and lots carry, gets what it lacks. For
    accounts.run_once, which commits it with its record."""
    fields = ("type_id", "root", "brk", "max_break_cur", "cur_mode", "use_count")
    for row in db.execute(
            "SELECT uniq, %s FROM items WHERE (root IN (%s) AND max_break_cur = 0)"
            " OR (root = ? AND use_count <= 0)"
            % (", ".join(fields), ", ".join("?" * len(items.BREAKABLE_ROOTS))),
            tuple(items.BREAKABLE_ROOTS) + (items.HEAL,)).fetchall():
        fix = unfilled(row)
        if fix:
            db.execute("UPDATE items SET %s WHERE uniq = ?"
                       % ", ".join("%s = ?" % k for k in fix),
                       tuple(fix.values()) + (row["uniq"],))
    for table, column in (("mail", "items_json"), ("auction_lots", "item_json")):
        for row in db.execute("SELECT id, %s FROM %s" % (column, table)).fetchall():
            try:
                snaps = json.loads(row[column] or "[]")
            except ValueError:
                continue
            moved = False
            for snap in [snaps] if isinstance(snaps, dict) else snaps:
                if isinstance(snap, dict) and all(f in snap for f in fields):
                    fix = unfilled(snap)
                    snap.update(fix)
                    moved = moved or bool(fix)
            if moved:
                db.execute("UPDATE %s SET %s = ? WHERE id = ?" % (table, column),
                           (json.dumps(snaps), row["id"]))


def weight_of(row):
    """Grams, the way WeightPan reads it: per piece, times the stack."""
    si = items.params_of(row["type_id"]) or {}
    w = si.get("weight", 0)
    return w * row["count"] if row["root"] in items.HEAPABLE_ROOTS else w


def fits(row, slot):
    """Whether an instance may occupy a container.

    The client's own drag-and-drop never offers a wrong target, so this is
    the check against a modified client rather than a message to a real one.
    """
    if slot == BAG:
        return True
    root = row["root"]
    if slot in HAND_SLOTS:
        return root in items.HAND_ROOTS
    if slot in WEAR_SLOTS:
        if root != items.WEAR:
            return False
        si = items.params_of(row["type_id"]) or {}
        return si.get("slot_type") == slot - HEAD
    return False


# --- what the gear adds ------------------------------------------------------
#
# The card adds three of the gear's numbers by itself and nothing else: the
# bonus_od of the items in all eight slots and the od of the sets on top of
# ap_max (CharInterface.showOD), and bonus_cp/bonus_ce the same way on top of
# the crit it computes (showKrit). Health, stamina, attributes, skills and
# specialisations it adds nowhere, so they reach it inside rp_info's f_* and
# usrUp's maxima. The three it does add stay out of what is sent -- ap_max
# goes bare, crit is not sent at all -- and are used on this side exactly as
# the card counts them, so the number the player reads is the one rolled
# (the card's one slip, a set counted twice in the firearm's crit, included:
# card_repeat).

# What lends its bonus_* while it is on the body: clothing and weapons. A
# medicine carries the same keys, but for what it does once taken, for
# bonus_act_time (the Салюс and Анестетик lines, +35..+300 health); held in
# a hand it lends nothing. The card would still add a held medicine's
# bonus_cp -- two Альфа-реагент types have one -- and that is the one place
# it and the server part.
GEAR_ROOTS = (items.WEAR, items.FIRE_ARM, items.COLD_ARM)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def unpacked(mask, dense, n):
    """A mask and its dense list as Item.parseNeedBonus reads them: bit i
    takes the next value of the list. A full list of n, zeros elsewhere."""
    out = [0] * n
    if not isinstance(mask, int) or not isinstance(dense, list):
        return out
    j = 0
    for i in range(n):
        if mask >> i & 1:
            if j < len(dense):
                out[i] = _num(dense[j])
            j += 1
    return out


def item_bonus(si):
    """One item's own bonus_* out of its static info, as sets.zero()."""
    b = sets.zero()
    for key in sets.SCALARS:
        b[key] = _num(si.get("bonus_" + key))
    for kind, titles in sets.LISTS:
        b[kind] = unpacked(si.get("bonus_%s_m" % kind), si.get("bonus_%s" % kind), len(titles))
    return b


def _add(total, b):
    for key in sets.SCALARS:
        total[key] += b[key]
    for kind, _titles in sets.LISTS:
        total[kind] = [x + y for x, y in zip(total[kind], b[kind])]


def _on_body(rows):
    return {r["slot"]: r for r in rows if r["slot"] in WEAR_SLOTS or r["slot"] in HAND_SLOTS}


def _counted(on):
    """The type ids that count towards their sets: in SET_SLOTS, unbroken --
    a reworked piece as its rung's (setcraft.base_of), whose set it is."""
    return [setcraft.base_of(r["type_id"]) for s, r in on.items()
            if s in SET_SLOTS and r["brk"] > 0]


def gear_bonus(rows):
    """Everything the things on the body add, as sets.zero(): the character's
    bonus_* (Character.set_gear) for these item rows.

    An item's own bonus_* counts in any of the eight slots, whole or broken:
    showOD and showKrit read it off whatever is in a slot, as showArmorLevel
    reads armor_class, and Fighter.armor already counts a broken piece's
    armour the same way. A set counts only its pieces in SET_SLOTS that are
    not broken, which is what lights the tooltip's lines
    (PersEquip.getNumOfSetItem), and adds every K up to that count
    (sets.bonuses) once per set, however many slots it fills.

    Each set once, crit and anti-crit included: what the card's firearm
    line counts a second time is card_repeat's.
    """
    on = _on_body(rows)
    total = sets.zero()
    for row in on.values():
        if row["root"] in GEAR_ROOTS:
            _add(total, item_bonus(items.params_of(row["type_id"]) or {}))
    _add(total, sets.bonuses(_counted(on)))
    return total


def card_repeat(rows):
    """(crit, anti-crit) the card counts a second time, for these rows.

    showKrit's belt step compares the belt's set with the head, shirt and
    armour and then adds the set of the LEGS, and the legs' own step adds it
    again. So whenever the belt's set is none of those three -- which is
    always once head, shirt and armour are on, the belt being in no set --
    the legs' set gives its cp and ce twice. The player reads that figure
    off the card for a firearm, so the firearm's roll takes it too
    (progression.crit_chance). Nothing else does: the card shows no melee
    crit, and none at all without a firearm in hand (CharInterface.as:383),
    so a blade and a bare-handed target get each set once, as it is.
    """
    on = _on_body(rows)

    def set_in(slot):
        # None for an empty slot, as the card's undefined: two empty slots
        # are "the same set" to its != and an empty one differs from set 0.
        row = on.get(slot)
        return None if row is None else sets.set_of(setcraft.base_of(row["type_id"]))

    belt = set_in(BELT)
    legs = set_in(LEGS)
    if legs and belt != set_in(CAMO) and belt != set_in(ARMOR) and belt != set_in(HEAD):
        again = sets.bonuses([t for t in _counted(on) if sets.set_of(t) == legs])
        return again["cp"], again["ce"]
    return 0, 0


# --- the level: who may wear what --------------------------------------------
#
# The owner's rule (2026-09-25, «вещи по уровню только можно носить»): a
# piece of clothing goes on, and a weapon into a hand, only once the
# character's level has reached the thing's.
#
# The thing's level is the one number the client shows the player about it:
# the highest of its "Необходимые навыки" (need_skills, Annotation.as), a
# Стрельба N for guns and for every piece of the owner's set ladder, which
# writes each set's rung there (data/sets.json, "Requirement Стрельба = the
# set's level"), a Ближний бой N for blades. The internal names carry a
# level too (pistols_1_lvl_4, helm_Bs_M_LVL_0) but it is the series' and
# not the wearer's -- 86 types whose frame names a requirement disagree with
# their own name, the whole Беженец rung among them -- and a rule the
# tooltip never shows would be a rule nobody could follow. So a thing that
# asks for nothing is for everybody. The character's level is its best
# skill (progression.Character.level), the figure the client shows as
# "уровень"; which skill the thing names does not matter, only how high,
# and so a knife-fighter of level 8 may wear the Налетчик set that says
# "Стрельба 8". The client's own check stays what it always was: a
# warning that a thing whose skill is not met "будет ломаться быстрее",
# which the player may wave away (EquipInterface.checkForWarning).
#
# Attributes, specialisations and the fighter's reputation a thing may ask
# for are no level and stay that warning. Medicine is outside the rule
# altogether: it is not worn, lends nothing held (GEAR_ROOTS), and the
# client's quick heal takes it straight from the bag, so a gate on the hand
# would only be a refusal the heal button walks around. Rounds ask for no
# skill at all, so loading a gun is not gated either; a gun that may not be
# held can still be loaded in the bag.
#
# The only way onto the body is ss_move (PersEquip.requestTranfer); buying,
# looting, the bank, the post and a barter all land in the bag, and so does
# a thing above one's level: buying it is allowed, as in the original,
# whose stall says nothing about levels. What an existing character already
# wears above its level goes back to the bag at the next login
# (Inventory.over_level_to_bag), which costs nothing -- the bag has no
# cells, and the weight counts the bag and the body alike.

def item_level(type_id):
    """The level a type asks of whoever wears or holds it; 0 for none."""
    si = items.params_of(type_id) or {}
    return max(unpacked(si.get("need_skills_m"), si.get("need_skills"), progression.SKILLS))


def wearable(row, level):
    """Whether a character of this level may have this row on the body."""
    return row["root"] not in GEAR_ROOTS or item_level(row["type_id"]) <= level


def item_title(type_id):
    """The name the player reads, for a line in chat."""
    import names            # late: names reads every table, inventory is imported by all
    return names.text(items.STRING_ID_OFFSET + type_id).partition("$")[0].strip()


def level_line(row, level):
    """Why a row may not go on, the thing's level against the character's:
    «Наган 1895»: взять в руки можно с 1-го уровня, у вас 0-й."""
    verb = "надеть" if row["root"] == items.WEAR else "взять в руки"
    return "«%s»: %s можно с %d-го уровня, у вас %d-й" % (
        item_title(row["type_id"]), verb, item_level(row["type_id"]), level)


# --- the figure: a full set's look -------------------------------------------
#
# All five counted pieces of one set draw the character as the set's res
# instead of its own body (sets.look). Every client works that out for
# itself about ITS OWN character, from the slots it holds and the res of
# ss_si_set (PersEquip.checkFullSet on every addItem/removeItem). About
# anybody else it cannot: a stranger's ss_ack only stores the wear list
# (PersEquip.ss_ack, `wear_arr = ...`), no slot is filled, and so the look
# has to be told. Two frames can do it, and each only half of it:
#
#   ss_ack;set_res=<res>  -- sets PersInfo.setResID, which PersInfo.persType
#       then prefers to the sex. But only when it is not 0 (`if(set_res)`),
#       so it can never take a set's figure away again; and an ss_ack is
#       only ever the answer to the client's own ss_get, since XMLCCallStack
#       hands every ss_ack to the oldest waiting handler, whoever's it is.
#       So it rides the ss_ack the client asks for when it places somebody
#       (lch;newUser;rtype=-1 -> Player/PlayerRegister.addPlayer ->
#       getStuff(3, id)) and nothing else, and the wearer's own ss_ack
#       carries it too, as the client's `isGamer` branch there expects.
#   ss_obj_move;id=<player>  -- the frame PlayerRegister routes to that
#       player's PersEquip, which empties the `from` slot and fills the
#       `to` slot (from>>8 == 1, to>>8 == 1) and runs checkFullSet after
#       each: setResID becomes null unless all five slots then hold one
#       set, and that set's res if they do. Unasked, and with no queue.
#
# So when a figure changes, everybody else in the room gets look_frames: one
# ss_obj_move per counted slot, head to boots, each naming the slot as both
# `from` and `to` and carrying what is in it now (x0 for nothing). Each
# frame empties its slot first, so setResID is null after the first one
# whatever the client held -- checkFullSet leaves it alone for a full set of
# res 0, and a stale figure would otherwise survive the sequence -- and the
# last one leaves the client's copy of those five slots exactly as they are
# on the server, so its own checkFullSet comes out as sets.look does. What
# it has to learn on the way (ss_si_wear for a type, ss_si_set for a set)
# it asks for itself, and those always come back.
#
# The belt is never sent: getFullSetID does not read it. Nor are the hands:
# a primary in `to` swaps the stranger's gun and plays the holster
# animation (Char.changeWeapon), which is not what happened.
#
# The client picks the new figure up at the next frame it draws of it -- a
# step, a shot, a hit (Char.persType is read per frame by playAnimation).
# Outside war locations a figure standing still has stopped drawing, the
# wearer's own included: a "stand" pass followed by another sets
# one_pass_left, and playAnimation stops after one more frame. In a war
# location it never stops -- extendedStand alternates stand_mili and stand,
# so no pass repeats the last -- and the new figure shows at once. Nothing
# in the protocol restarts a stopped one, and nothing here tries to.
#
# One place no frame reaches: the inspect window. InspectInterface.setPlayer
# calls parseWear with no list, which puts wear_arr -- the list the last
# ss_ack brought -- back on the slots (an empty entry leaves its slot as it
# was) and runs checkFullSet on the result; a player who changed since is
# shown in the old clothes and, until the next frames about them, the old
# figure. The client asks for no fresh list there, and an ss_ack cannot be
# pushed. What can be done is not to take the viewer's copy on trust later:
# ss_get remembers the figure of the wear list it last sent about each
# player, and an answer that is the body's own after one that made a figure
# is followed by look_frames, as after a figure that was shown.


def look_of(rows):
    """What these item rows make of the character's figure: the res of the
    full set on it (sets.look), or 0 for its own body."""
    on = _on_body(rows)
    return sets.look(setcraft.base_of(on[s]["type_id"]) if s in on else None
                     for s in SET_SLOTS)


def look_frames(pid, rows):
    """The five ss_obj_move that bring another client's copy of this
    player's counted slots in line with these rows (see above)."""
    on = _on_body(rows)
    return [("ss_obj_move", {"id": pid,
                             "obj": BigUInt(oid_of(on[s])) if s in on else EMPTY,
                             "to": s, "from": s})
            for s in SET_SLOTS]


# --- the price of a purchase --------------------------------------------------

def js_round(x):
    """AS2's Math.round: halves go up, towards +infinity."""
    return math.floor(x + 0.5)


def as_sent(v):
    """A number as the client parses it off the wire: protocol.encode writes
    a float with %g, six significant digits, and the client computes with
    what it read, not with what we meant."""
    return float("%g" % v) if isinstance(v, float) else v


def repair_gold(afro):
    """Patched RepairInterface price in hundredths of G, nearest hundredth.

    Math.round rounds positive halves up; Python round would use ties to
    even. Keep the client's minimum of 0.01 G.
    """
    return max(1, int(js_round(afro / float(GOLD_REPAIR_MOD) * 100)))


def repair_base_price(si):
    """Afro valuation for repairs only; gold prices are hundredths of G.

    The client patch supplies this value from Item.getProp("cost") while
    the repair window is open. Trade prices and sale eligibility stay intact.
    """
    cost = as_sent(si.get("cost", 0) or 0)
    if not cost:
        cost = (as_sent(si.get("g_cost", 0) or 0)
                * as_sent(GOLD_REPAIR_MOD) / 100)
    return cost


def repair_window(si, brk, max_break_cur, rmod=RMOD):
    """Every figure the repair window prints for one thing, the gold ones in
    hundredths of an ounce: ((afro, gold, restore) in its slot, (afro, gold)
    as its share of the two «Отремонтировать все» sums), restore None where
    the window offers no restore. The same doubles in the client's order,
    so a floor lands where the client's lands.

    The slot, RepairInterface.repairCostCount:

      q       = break / max_break_cur                (Breakable.getCurQuality)
      afro    = floor((q ? rmod * (1 - q) : rmod) * cost * repair_mod),
                and 1 where that comes to 0
      gold    = repair_gold(afro) -- of the afro figure shown, its 1 included
      restore = Math.round(g_cost * gold_repair_price_mod) / 100, only
                when g_cost is set

    The two sums, countAllRepairAfroCost and countAllRepairGoldCost, go
    over the same broken things and add floor(cost * (rmod * repair_mod) *
    (1 - q)) and repair_gold of that: no 1 for a 0, and nothing at all for
    a thing with no valuation (their `if (cost)`). Gold-only things use
    their gold price converted at the repair rate, in the slot and sums.
    tools/widescreen.py supplies that valuation only in the repair UI.
    """
    cost = repair_base_price(si)
    g_cost = as_sent(si.get("g_cost", 0) or 0)
    rmod = as_sent(rmod)
    repair_mod = as_sent(si.get("repair_mod", 1))
    q = brk / float(max_break_cur) if max_break_cur > 0 else float("nan")
    m = rmod if (not q or q != q) else rmod * (1 - q)
    afro = int(math.floor(m * float(cost) * repair_mod)) or 1
    restore = int(js_round(g_cost * as_sent(GOLD_RESTORE_PRICE_MOD))) if g_cost else None
    share = (0, 0)
    if cost:
        # A ceiling of 0 makes q NaN, and the sum NaN with it; such a thing
        # is never listed (NaN < 1 is false, PersEquip.getBreakedItems), and
        # the slot's reading of it -- the whole price -- stands in here.
        each = int(math.floor(float(cost) * (rmod * repair_mod) * (1 - q if q == q else 1)))
        share = (each, repair_gold(each))
    return (afro, repair_gold(afro), restore), share


def repair_prices(si, brk, max_break_cur, rmod=RMOD):
    """(afro, gold, restore): what a repair and a restore of this thing
    cost, gold in hundredths of an ounce, restore None where the window
    offers none -- never more than the window showed, wherever it showed it.

    The window shows a repair's price twice, in the slot and as a share of
    «Отремонтировать все», and both send the same ss_upd for each thing
    (Trade.repairItem), so the server cannot tell which the player read.
    Where the two part, the lower is charged:

      * a thing with neither an afro nor a gold price is mended for nothing;
      * a repair that comes to under one afro costs no afro (the slot says
        1, the sum adds 0) and 0.01 G, which both print;
      * anywhere else they agree but for a double's last bit at a floor,
        where the lower is the one charged.

    A restore has one figure, the slot's.
    """
    (afro, gold, restore), (all_afro, all_gold) = repair_window(si, brk, max_break_cur, rmod)
    return min(afro, all_afro), min(gold, all_gold), restore


def buy_price(si, root, n, gold=False):
    """What buying n of a type costs, to the unit as the stall window says.

    A round is priced by the "Сколько штук купить?" window
    (ExchangePan.countMoney): Math.ceil(cost_num * n * pmod), cost_num being
    the price of ONE round that Ammo.initialize has made of the pack's --
    Math.round(cost * 1000 / sell_num) / 1000 afro, or
    Math.round(g_cost / sell_num) hundredths of an ounce, a whole number, so
    a pack of 20 at 30 hundredths is 2 a round there and not 1.5. The same
    doubles in the same order here, so 5000 rounds cost what the window
    printed; cost * n / sell_num worked out in one go would part from it by
    the rounding of the unit and, over thousands, by a float's last bit.
    Anything else goes one at a time at its own price times pmod.
    """
    per = as_sent(si["g_cost"] if gold else si["cost"])
    if root == items.AMMO:
        sell = as_sent(si.get("sell_num", 1)) or 1
        unit = js_round(per / sell) if gold else js_round(per * 1000 / sell) / 1000
    else:
        unit = per / float(si.get("sell_num", 1) or 1)
    return int(math.ceil(unit * n * PMOD))


class TradeSession:
    """One open stall. The client keeps one Trade object per contact and
    builds a new one for the next, so a session is a single counterpart."""

    def __init__(self, npc_id, trader_type):
        self.s_type = SESSION_TRADE
        self.npc_id = npc_id
        self.trader_type = trader_type


class Inventory:
    """Everything one connection does with items. Owned by server.Session.

    State lives in the database; this object holds only what a session
    needs between frames: the open stall or bank and the reload timers.
    """

    def __init__(self, sess, store):
        self.sess = sess
        self.store = store
        self.trade = None
        # Entity id of the bank NPC whose window is open, or None.
        self.bank = None
        self.reloads = {}       # uniq -> asyncio.TimerHandle
        # Serials of things this character has on the table in a barter
        # (barter.py): find() does not see them until they come off it.
        self.locked = set()
        # How many cmdAcks this object has sent, so a bank operation that
        # fails half way can tell whether its one answer already went out.
        self.acks = 0
        # The figure (look_of): what this character is drawn as, as of the
        # last count, and -- this client being a viewer -- the res it was
        # last made to draw each other player as, by player id. The client
        # keeps a Player entity for the whole connection
        # (PlayerRegister.removePlayer spares Players), setResID with it,
        # so this lives exactly as long as the socket does.
        self.look = 0
        self.shown = {}
        # And, by player id, the figure of the wear list the last ss_ack
        # about that player carried: the client keeps that list (wear_arr)
        # and an inspect window puts it back on the slots (see the figure).
        self.acked = {}
        # Whether the quests that count the bag are already due to be told
        # of a change to it (bag_changed): once per command, however many
        # things it moved.
        self._count_due = False
        # What the login took off for the level (over_level_to_bag), said in
        # chat once the character stands somewhere (taken_off_lines).
        self.level_notes = []

    # --- plumbing ----------------------------------------------------------
    @property
    def char_id(self):
        return self.sess.char_id

    def send(self, cmd, **params):
        self.sess.send(cmd, **params)

    def ack(self, res):
        self.acks += 1
        self.send("cmdAck", res=res)

    def rows(self, char_id=None):
        char_id = self.char_id if char_id is None else char_id
        return self.store.items_of(char_id) if char_id else []

    def _own_row(self, text):
        """The row behind a wire id, if it exists and is this character's,
        wherever it lies -- on them or in the bank."""
        parsed = parse_oid(text)
        if not parsed or not self.char_id:
            return None
        row = self.store.item(parsed[0])
        if not row or row["char_id"] != self.char_id:
            return None
        # The type and root ride inside the id, so a forged id that names an
        # existing serial with another type is not the same item.
        if (row["type_id"], row["root"]) != parsed[1:]:
            return None
        return row

    def find(self, text):
        """The row behind a wire id, if it exists, is this character's and
        is on them -- worn, held or in the bag.

        A thing in the bank is left out on purpose. Every verb that acts on
        an item -- sell, post, use, throw away, split, move, drop into a loot
        bag, fire -- starts here, and none of them may reach into storage;
        the bank's own "take" asks find_banked instead. So is a thing on the
        table in a barter (locked): the other side is looking at it as it
        was offered, and a stack merged into or split off, a thing sold,
        posted or put away meanwhile would be traded as something else.
        """
        row = self._own_row(text)
        if row is None or row["slot"] == BANK or row["uniq"] in self.locked:
            return None
        return row

    def find_banked(self, text):
        """The same, for a row in this character's storage only."""
        row = self._own_row(text)
        if row is None or row["slot"] != BANK:
            return None
        return row

    def banked(self):
        return [r for r in self.rows() if r["slot"] == BANK]

    def carried(self):
        return [r for r in self.rows() if r["slot"] != BANK]

    def in_slot(self, slot):
        for row in self.rows():
            if row["slot"] == slot:
                return row
        return None

    def total_weight(self):
        """What the character carries: worn, held and the bag -- not the
        bank, or a full storage would stop them buying a single round."""
        return sum(weight_of(r) for r in self.carried())

    def create(self, type_id, count=1, slot=BAG, char_id=None):
        f = new_fields(type_id, count)
        f["slot"] = slot
        root = f.pop("root")
        return self.store.create_item(char_id or self.char_id, type_id, root, **f)

    # --- what a quest counts -------------------------------------------------
    def bag_pieces(self):
        """type id -> pieces in the bag: what a quest that asks for things
        counts (quests.Quest.bring_count) and a hand-in takes. The bag only
        -- not the hands, the body or the bank -- and not what lies on the
        table in a barter (locked). A stack counts its size."""
        out = {}
        for r in self.rows():
            if r["slot"] == BAG and r["uniq"] not in self.locked:
                n = r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
                out[r["type_id"]] = out.get(r["type_id"], 0) + n
        return out

    def take_pieces(self, type_id, n, slots=(BAG,)):
        """Take n pieces of a type out of the bag, oldest first: a quest's
        hand-in. A stack that keeps some reports its new size (ss_di_heap),
        a thing or a stack used up leaves by ss_obj_status 0 -- the client
        takes nothing away by itself. The caller has counted (bag_pieces);
        returns how many were taken. slots widens it to the hands and the
        body (reclaim_pieces): ss_obj_status 0 takes an id away from
        wherever it is, and what that changes of the gear is the caller's
        to recount (server.GEAR_COMMANDS)."""
        taken = 0
        for row in self.rows():
            if taken >= n:
                break
            if row["type_id"] != type_id or row["slot"] not in slots \
                    or row["uniq"] in self.locked:
                continue
            have = row["count"] if row["root"] in items.HEAPABLE_ROOTS else 1
            use = min(have, n - taken)
            if use < have:
                row["count"] -= use
                self.store.update_item(row["uniq"], count=row["count"])
                self.push_di(row)
            else:
                self.forget_reload(row["uniq"])
                self.store.delete_item(row["uniq"])
                self.push_status(row, 0)
            taken += use
        return taken

    # --- what a quest hands over --------------------------------------------
    def give_pieces(self, type_id, n):
        """Put n pieces of a type into the bag and tell the client: what a
        quest hands over, at the take (start_obj) or as its reward. A thing
        that stacks comes as stacks of at most its max_count, anything else
        as n things -- each of them new, never merged into a stack the bag
        already holds, as a purchase is not (buy): ss_obj_status 1 is what
        makes the client build the thing and fire the addItem its quest
        window lists under «Вы получили» (QuestInspector.getRewardItem), and
        a stack that only grew would fire none. Then its dynamic info, as a
        purchase sends it. Returns the rows."""
        si = items.params_of(type_id) or {}
        per = max(1, si.get("max_count", 1)) \
            if items.root_of(type_id) in items.HEAPABLE_ROOTS else 1
        out, left = [], int(n)
        while left > 0:
            count = min(per, left)
            row = self.create(type_id, count)
            self.push_status(row, 1)
            self.push_di(row)
            out.append(row)
            left -= count
        return out

    @staticmethod
    def pieces_weight(type_id, n):
        """Grams of n pieces of a type, as weight_of counts a stack."""
        return (items.params_of(type_id) or {}).get("weight", 0) * int(n)

    def reclaim_pieces(self, type_id, n):
        """Take back up to n pieces of a type a quest handed over at the
        take (start_obj), the quest being dropped (Session.cmd_q_ca) or
        handed in (cmd_q_co, quests.Quest.returns), wherever the character
        still keeps it: out of the bag first, the way a hand-in takes
        (take_pieces), then out of the hands and off the body -- a thing
        handed over and then held or put on is still the thing handed over,
        and one left there would be one more at every take -- then out of
        the bank: a parcel put away is not a parcel kept. The hands and the
        body go by ss_obj_status 0 as the bag does, and the gear is
        recounted after the command (server.GEAR_COMMANDS). The bank's rows
        go without a frame: the client holds none of them outside the bank's
        own window, which asks for its list each time it opens (open_bank).
        A thing on the table in a barter (locked) is left where the other
        side sees it, and whatever left the character altogether (thrown
        away, posted, sold) is not looked for: what a quest may hand over
        is worth nothing away from it, and no barter takes it
        (quests.START_OBJ_WORTHLESS_ONLY). Returns how many were taken."""
        n = int(n)
        taken = self.take_pieces(type_id, n)
        taken += self.take_pieces(type_id, n - taken, slots=BODY_SLOTS)
        for row in self.banked():
            if taken >= n:
                break
            if row["type_id"] != type_id:
                continue
            have = row["count"] if row["root"] in items.HEAPABLE_ROOTS else 1
            use = min(have, n - taken)
            if use < have:
                self.store.update_item(row["uniq"], count=have - use)
            else:
                self.store.delete_item(row["uniq"])
            taken += use
        return taken

    def bag_changed(self):
        """Something came into the bag or left it. The quests that count
        what it holds are recounted (server.Session.count_bag) once the
        command at hand is done, however many things it moved: call_soon
        runs after the handler, when its cmdAck and its own frames are out.

        Every change the client is told of by ss_obj_status or a stack's new
        size comes here (push_status, push_di) -- a barter settled from the
        other side, the thing a corpse drops, what an admin hands over --
        and Session.handle adds the commands that move a thing the client
        moves by itself (BAG_COMMANDS: a bag on the ground, a letter).
        """
        count = getattr(self.sess, "count_bag", None)
        if count is None or self._count_due:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return          # no loop: an in-process test driving this by hand
        self._count_due = True
        loop.call_soon(self._count_now)

    def _count_now(self):
        self._count_due = False
        try:
            self.sess.count_bag()
        except Exception:
            log.exception("  !!    counting the bag for the quests failed")

    # --- pushes ------------------------------------------------------------
    def push_status(self, row, status):
        """ss_obj_status: 1 puts a new item in the bag (the client builds it
        and asks for its DI itself), 0 removes an id from wherever it is."""
        self.send("ss_obj_status", obj=BigUInt(oid_of(row)), status=status)
        self.bag_changed()

    def push_di(self, row):
        """Unsolicited dynamic info. This is how a reload, a partial sale or
        a merged stack reaches the client: it changes no number by itself."""
        self.send(DI_COMMAND.get(row["root"], "ss_di_heap"), **di_params(row, self.store))
        if row["root"] in items.HEAPABLE_ROOTS:
            # A stack's new size: pieces came or went.
            self.bag_changed()

    # --- wear ---------------------------------------------------------------
    #
    # Until now brk was written once, when the item was made, and never again:
    # every gun in the game stayed as new as the day it appeared. That left
    # three things dead at once -- the durability bar the client draws
    # (ItemContainer.showBreak), the "item is broken" refusal the server
    # already knows how to send (combat.py, res=16), and the resale price,
    # which is multiplied by exactly this quality in sell() and so always came
    # back as the full price paid.
    #
    # Points are whole numbers on purpose: accounts.Store writes item fields
    # through int(), so half a point would round away to nothing and wear
    # would look as broken as it did before, in a way nobody could see.

    def wear(self, row, points=1):
        """Take points off an item durability and tell the client."""
        if row is None or points <= 0:
            return row
        if row["root"] not in items.BREAKABLE_ROOTS or row["brk"] <= 0:
            return row
        if quests.lent(row["type_id"]):
            # A quest's loan (the quarry pick, the Tir's guns) goes back as
            # it came: it does not wear (combat's per-round wear says why).
            return row
        self.store.update_item(row["uniq"], brk=max(0, row["brk"] - int(points)))
        row = self.store.item(row["uniq"])
        if row is not None:
            self.push_di(row)
            # A piece of a set that has just broken no longer counts towards
            # it. The ss_di_wear above has told the client its break is 0,
            # so the card and the tooltip recount by themselves; what they
            # cannot recount is ours.
            if row["slot"] in SET_SLOTS and row["brk"] <= 0:
                self.refresh_gear()
        return row

    def wear_uniq(self, uniq, points=1):
        """The same, for a caller that holds only the id."""
        row = self.store.item(uniq)
        if row is None or row["char_id"] != self.sess.char_id:
            return None
        return self.wear(row, points)

    def wear_worn(self, points=1):
        """Wear one piece of what the player has on.

        One piece per blow rather than all six: a hit lands somewhere, and
        wearing the whole outfit on every hit would strip a player bare in an
        afternoon. Which piece takes it is the roll's business.
        """
        worn = [r for r in self.rows()
                if r["slot"] in WEAR_SLOTS and r["root"] in items.BREAKABLE_ROOTS
                and r["brk"] > 0]
        if not worn:
            return None
        return self.wear(RNG.choice(worn), points)

    def unfit_to_bag(self):
        """Take off whatever sits in a slot it does not fit, into the bag.

        fits() is asked on every move, never of what is already on: until
        the slot_type of the LVL clothing was put right, a helmet could be
        worn as a shirt, and such a row stays where it was put -- two
        helmets would then count five pieces of a set with no shirt at all,
        and lend the bonuses of both. Called once per load, before the gear
        is counted and before the client has asked for a single slot, so
        it simply finds the thing in the bag. Returns the uniqs it moved.
        """
        moved = [r["uniq"] for r in self.rows()
                 if (r["slot"] in WEAR_SLOTS or r["slot"] in HAND_SLOTS)
                 and not fits(r, r["slot"])]
        for uniq in moved:
            self.store.update_item(uniq, slot=BAG)
        if moved:
            log.info("  ..    %d item(s) in a slot they do not fit put back in the bag: %s",
                     len(moved), moved)
        return moved

    def over_level_to_bag(self):
        """Take off whatever the character's level does not reach yet.

        For those who put a thing on before the level rule existed, or
        whose thing a data file has since moved up a rung: nothing is lost
        and nothing lingers half-worn. Leaving it on without its bonuses
        would not hold -- the card adds a worn thing's action points and
        crit by itself (CharInterface.showOD/showKrit), and a gun in the
        hand fires -- while the bag takes anything, having no cells, and
        carries it at the same weight. Called once per load, like
        unfit_to_bag and after it, before the gear is counted and before
        the client has asked for a slot; the lines saying what went where
        wait in level_notes for the first lenter. The level can only grow
        (a skill never falls), so nothing needs taking off mid-session.
        Returns the uniqs it moved.
        """
        level = self.sess.character().level
        moved = [r for r in self.rows()
                 if r["slot"] in BODY_SLOTS and not wearable(r, level)]
        for r in moved:
            self.store.update_item(r["uniq"], slot=BAG)
        self.level_notes = ["Перенесено в рюкзак — %s" % level_line(r, level) for r in moved]
        if moved:
            log.info("  ..    %d item(s) above level %d put back in the bag: %s",
                     len(moved), level, [r["uniq"] for r in moved])
        return [r["uniq"] for r in moved]

    def taken_off_lines(self):
        """The level_notes, once: what the caller is to say in chat."""
        out, self.level_notes = self.level_notes, []
        return out

    def refresh_gear(self, push=True):
        """Recount what the gear adds and tell the client what that moved.

        Called whenever what is on the body may have changed -- after every
        command that can move, delete, sell, mail or mend a thing
        (server.GEAR_COMMANDS), when a worn piece breaks, and once when the
        character is loaded, with push=False because the client asks for
        rp_info and the bars itself then.

        Only a change goes out. Attributes, skills and specialisations by a
        partial rp_info for the indexes that moved; the maxima by usrUp to
        the whole room, whose bars are drawn against them too.

        The saved health and stamina are left as they are when a maximum
        falls. Character.vitals holds them to the maximum on every read, and
        damage, healing and regeneration all write from that held value, so
        a figure above the maximum is never more health than the bar shows;
        cutting it down here instead lost the difference for good to anyone
        who took a piece off and put it back on (a full 198 became 151/198).

        Action points are held to the fight's ceiling, which is the last
        lenter's (combat.Fighter.ap_max) and so does not move here: the
        client's bar keeps that ceiling until the next location
        (APManager.setAP is called nowhere else), and a change of gear
        reaches the bar and the fight together, there.

        The figure is counted here too (look_of), and a change of it goes
        to everybody else in the room (push_look); the wearer's own client
        redraws its own by itself. A piece breaking changes nothing there.
        """
        ch = self.sess.character()
        if ch.char_id is None or not self.char_id:
            return
        before = ch.vitals()
        rows = self.rows()
        changed = ch.set_gear(gear_bonus(rows), card_repeat(rows))
        fighter = self.sess.combat
        held = fighter.ap > fighter.ap_max
        if held:
            fighter.ap = fighter.ap_max
        look, was = look_of(rows), self.look
        self.look = look
        if not push:
            return
        if any(changed.values()):
            self.sess.push_stats(**changed)
        after = ch.vitals()
        if after != before:
            room = self.sess.room
            if room is not None:
                room.broadcast(("usrUp", dict(id=self.sess.pid, **after)))
            else:
                self.sess.push_vitals()
        if held and self.sess.room is not None:
            fighter.c_ap()
        if look != was:
            self.push_look(rows)

    def push_look(self, rows=None):
        """This character's figure changed: show it to the rest of the room.

        Only those standing in the same location are told, each with
        look_frames about this player, and each remembers what it was shown.
        Anybody else learns it when they next place this player -- on the
        map nobody is drawn in clothes, and whoever meets them later asks
        for their gear then (see ss_get).
        """
        room = self.sess.room
        if room is None:
            return
        rows = self.rows() if rows is None else rows
        for viewer in list(getattr(room, "players", ())):
            inv = getattr(viewer, "inv", None)
            if viewer is not self.sess and inv is not None:
                inv.show_look(self.sess.pid, rows)

    def show_look(self, pid, rows):
        """Make this client draw player `pid`, whose item rows these are, as
        they stand now: look_frames, and a note of the figure it now has."""
        for cmd, params in look_frames(pid, rows):
            self.send(cmd, **params)
        self.shown[pid] = look_of(rows)

    def money(self):
        """(afro, gold) from the one place they live while the player is on.

        The Character object is what Character.save writes back on the way
        out, so a purse kept only in the database would be overwritten by
        the stale copy in memory the moment the player logged out.
        """
        ch = self.sess.character()
        if ch.char_id is not None:
            return ch.afro, ch.gold
        return self.store.money(self.char_id) if self.char_id else (0, 0)

    def set_money(self, afro, gold, source=None, ref=0):
        """The new purse, written at once; booked in the money ledger
        under source and ref (accounts.money_ledger: shop_buy, shop_sell,
        repair and the thing's type), or under the command's own."""
        ch = self.sess.character()
        with self.booked(source, ref):
            if ch.char_id is not None:
                ch.afro, ch.gold = int(afro), int(gold)
                ch.save(self.store)
            elif self.char_id:
                self.store.set_money(self.char_id, afro, gold)

    def booked(self, source, ref=0):
        """accounts.Store.booked_as, or nothing for no source (or a store
        that keeps no ledger)."""
        how = getattr(self.store, "booked_as", None)
        return how(source, ref) if how is not None and source else contextlib.nullcontext()

    def push_money(self):
        # The only frame that carries afro/gold is a full userInfo_Player
        # (Gamer.userInfo); there is no lighter update.
        self.sess.send_player_info()

    # --- character life ----------------------------------------------------
    def starter_kit(self, char_id):
        """Everything a new character wakes up with.

        The pistol goes into the hand and the rounds into the bag, unloaded:
        loading is a verb the game teaches, with a quest of its own, and a
        magazine filled here would refuse the very command the lesson asks
        for.
        """
        for type_id, count in STARTER_KIT:
            self.create(type_id, count, slot=STARTER_SLOT.get(type_id, BAG),
                        char_id=char_id)

    def close(self):
        """Connection gone: nothing to save (the database is current), but
        a reload still pending must not fire into a closed socket."""
        for handle in self.reloads.values():
            handle.cancel()
        self.reloads.clear()
        self.trade = None
        self.bank = None
        self.locked.clear()

    # --- ss_get / ss_ack ---------------------------------------------------
    def equipment_list(self, char_id, mask, rows=None):
        """The o_list for one character and one mask, in the client's order."""
        rows = self.rows(char_id) if rows is None else rows
        by_slot = {r["slot"]: r for r in rows if r["slot"] not in (BAG, BANK)}
        out = []
        if mask & MASK_WEAR:
            out += [BigUInt(oid_of(by_slot[s])) if s in by_slot else EMPTY
                    for s in WEAR_SLOTS]
        if mask & MASK_HANDS:
            out += [BigUInt(oid_of(by_slot[s])) if s in by_slot else EMPTY
                    for s in HAND_SLOTS]
        if mask & MASK_BAG:
            out += [BigUInt(oid_of(r)) for r in rows if r["slot"] == BAG]
        if mask & MASK_SESSION:
            # The divider, then whatever the open session holds: this
            # character's storage while a bank window is open (Bank.ss_ack
            # puts everything after the first "0" into the banker's bag),
            # otherwise a loot bag on the ground (combat.py); with neither
            # open the tail stays empty. The trophy collection's list is
            # trophies.Collection.ss_get's, without the divider.
            out.append(EMPTY)
            if self.bank is not None and char_id == self.char_id:
                out += [BigUInt(oid_of(r)) for r in rows if r["slot"] == BANK]
            else:
                out += [BigUInt(oid_of(r)) for r in self.sess.combat.session_items()]
        return out

    def ss_get(self, p):
        """ss_get;target=<id>;slot=<mask> -> ss_ack;o_list=|...|

        target 0 is the player (Gamer.ID). Any other id is something on the
        player's screen asking to be drawn: another player's clothes and
        hands, or a creature's. The list has to come back in either case,
        and with the right number of entries -- the ss_ack queue is FIFO and
        the client slices by the mask it remembers, not by what arrives.

        With the clothes goes the figure: set_res when the one asked about
        wears a full set with a look of its own, and no key otherwise, 0
        being what the client reads as "none" anyway. That is the whole of
        it when the answer is a set's figure. When it is the body's own and
        this client may still draw a set's figure for that player -- it was
        last shown one, or the last ss_ack about them carried a wear list
        that makes one, which an inspect window puts back on the slots --
        set_res cannot say so, the client ignoring a 0, and look_frames
        follow the answer to take it away (see the figure, above).
        """
        mask = int(p.get("slot", 0) or 0)
        target = int(p.get("target", 0) or 0)
        char_id = self.char_id if target == 0 else self.sess.char_for_entity(target)
        rows, look = None, 0
        if char_id:
            rows = self.rows(char_id)
            o_list = self.equipment_list(char_id, mask, rows)
            if mask & MASK_WEAR:
                look = look_of(rows)
        else:
            # Nobody we know: bare hands and no clothes, one entry per slot.
            o_list = []
            if mask & MASK_WEAR:
                o_list += [EMPTY] * len(WEAR_SLOTS)
            if mask & MASK_HANDS:
                o_list += [EMPTY] * len(HAND_SLOTS)
            if mask & MASK_SESSION:
                o_list.append(EMPTY)
        if look:
            self.send("ss_ack", o_list=o_list, set_res=look)
        else:
            self.send("ss_ack", o_list=o_list)
        if target and rows is not None and mask & MASK_WEAR:
            # A figure may linger from the frames last shown, or from the
            # wear list of the ss_ack before this one: an inspect window
            # since then put that list back on the slots and counted it.
            stale = self.shown.get(target) or self.acked.get(target)
            self.acked[target] = look
            if look:
                self.shown[target] = look
            elif stale:
                self.show_look(target, rows)

    # --- ss_get_di ---------------------------------------------------------
    def ss_get_di(self, p):
        """One instance's dynamic fields.

        Shares ItemFactory's window of five with ss_get_si, and the window
        only reopens when an ss_si_*/ss_di_* frame lands. So an id we do not
        know still gets an answer, shaped by the root the id itself names.
        """
        text = p.get("obj")
        parsed = parse_oid(text)
        if not parsed:
            log.warning("  ??    ss_get_di for unparsable id %r", text)
            self.send("ss_di_heap", obj=BigUInt(str(text or "0")), size=0)
            return
        uniq, type_id, root = parsed
        row = self.store.item(uniq)
        # Not "owned by me": a public trophy on another player is asked for
        # with target=<id>, and that is the one DI the client pulls for
        # somebody else's item. Anything that exists is described.
        if row and (row["type_id"], row["root"]) == (type_id, root):
            self.push_di(row)
            return
        # An item on sale is no row in items: it lives in its lot, and is
        # described from the lot's snapshot rather than as a ghost.
        lot = self.store.auction_lot_by_item(uniq)
        if lot and (lot["type_id"], lot["root"]) == (type_id, root):
            self.push_di(json.loads(lot["item_json"]))
            return
        # Nor is a registered trophy: it lives in its owner's collection.
        kept = trophies.registered_row(self.store, uniq, type_id, root)
        if kept is not None:
            self.push_di(kept)
            return
        log.warning("  ??    ss_get_di for unknown item %s", text)
        ghost = dict(uniq=uniq, type_id=type_id, root=root, count=0, brk=0,
                     max_break_cur=0, ammo_count=0, ammo_type=0, cur_mode=0,
                     use_count=0)
        self.send(DI_COMMAND.get(root, "ss_di_heap"), **di_params(ghost, self.store))

    # --- ss_move -----------------------------------------------------------
    def ss_move(self, p):
        """ss_move;obj;from;to -> cmdAck, then ss_obj_move.

        On res=0 the client moves the item itself, and if the target slot
        was occupied it puts the displaced item back where the moved one
        came from (PersEquip.applyTransfer) -- so the swap here mirrors that
        exactly, or the two sides disagree on where things are.
        """
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        try:
            src, dst = int(p.get("from")), int(p.get("to"))
        except (TypeError, ValueError):
            self.ack(RES_REFUSED)
            return
        if row["slot"] != src or src == dst:
            # The client's picture of where the item is does not match ours;
            # moving it anyway would leave a ghost in one of the two places.
            self.ack(RES_NOT_FOUND)
            return
        if not fits(row, dst):
            self.ack(RES_NO_ITEM)
            return
        displaced = self.in_slot(dst) if dst != BAG else None
        if displaced and not fits(displaced, src):
            self.ack(RES_NO_ITEM)
            return
        # The level rule, for both halves of the move: the thing going on,
        # and whatever it pushes out, which lands where the first came from
        # -- a hand, when the two hands trade places. The client shows 45's
        # own words and puts the thing back; the chat says which level.
        level = self.sess.character().level
        for thing, slot in ((row, dst), (displaced, src)):
            if thing and slot in BODY_SLOTS and not wearable(thing, level):
                self.ack(RES_LEVEL)
                self.sess.say(level_line(thing, level))
                return
        self.store.update_item(row["uniq"], slot=dst)
        if displaced:
            self.store.update_item(displaced["uniq"], slot=src)
        self.ack(RES_OK)
        # Meant for everyone else in the location, so they redraw this
        # player's figure; PlayerRegister.ss_obj_move ignores it for
        # Gamer.ID, so the sender's own copy is harmless. There is no room
        # fan-out on the server yet; when there is, this is the frame to
        # send to the rest of the room with the sender's entity id.
        self.send("ss_obj_move", id=0, obj=BigUInt(oid_of(row)), to=dst,
                  **{"from": src})

    # --- ss_use ------------------------------------------------------------
    def ss_use(self, p):
        """ss_use;type=<bit>;obj=x<oid>;[target=x..] -> cmdAck (+ pushes)."""
        try:
            kind = int(p.get("type", -1))
        except (TypeError, ValueError):
            kind = -1
        if kind == USE_DELETE:
            self.use_delete(p)
        elif kind == USE_LOAD:
            self.use_load(p)
        elif kind == USE_UNLOAD:
            self.use_unload(p)
        elif kind == USE_MODE:
            self.use_mode(p)
        else:
            # Shooting, striking (16) and healing (2/4) are combat.py's; it
            # answers with exactly one cmdAck as well, unknown bits included.
            self.sess.combat.ss_use(kind, p)

    def use_delete(self, p):
        """type=0: throw the item away. The client removes nothing until
        ss_obj_status;status=0 arrives (ItemActivator.deleteAck)."""
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        self.forget_reload(row["uniq"])
        self.store.delete_item(row["uniq"])
        self.ack(RES_OK)
        self.push_status(row, 0)

    def use_load(self, p):
        """type=1: load obj (a firearm) from target (a stack of rounds).

        After res=0 the client shows a reload bar and waits for
        ss_di_firearm with the new ammo_count/ammo_type; the stack it loaded
        from is only ever changed by ss_di_heap or removed by ss_obj_status.
        The stack is charged at once, the gun reports after reload_time,
        which is what the bar on the client is counting down.
        """
        gun = self.find(p.get("obj"))
        stack = self.find(p.get("target"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        if not stack or stack["root"] != items.AMMO:
            self.ack(RES_NO_AMMO)
            return
        si = items.params_of(gun["type_id"]) or {}
        if stack["type_id"] not in si.get("comp_array", []):
            self.ack(RES_WRONG_AMMO)
            return
        if gun["uniq"] in self.reloads:
            self.ack(RES_NOT_READY)
            return
        clip = si.get("clip_size", 1)
        if gun["ammo_count"] >= clip and gun["ammo_type"] == stack["type_id"]:
            self.ack(RES_LOADED)
            return
        self.ack(RES_OK)
        if gun["ammo_count"] and gun["ammo_type"] != stack["type_id"]:
            # Other rounds still in it: they come back as a stack of their
            # own before the new ones go in, the way unloading does.
            self.eject(gun)
        take = min(clip - gun["ammo_count"], stack["count"])
        if take >= stack["count"]:
            self.store.delete_item(stack["uniq"])
            self.push_status(stack, 0)
        else:
            stack["count"] -= take
            self.store.update_item(stack["uniq"], count=stack["count"])
            self.push_di(stack)
        self.store.update_item(gun["uniq"], ammo_count=gun["ammo_count"] + take,
                               ammo_type=stack["type_id"])
        delay = pace.paced(si.get("reload_time", 0) / 1000.0)
        loop = asyncio.get_running_loop()
        self.reloads[gun["uniq"]] = loop.call_later(delay, self.reloaded,
                                                    gun["uniq"])

    def reloaded(self, uniq):
        self.reloads.pop(uniq, None)
        row = self.store.item(uniq)
        if row and row["char_id"] == self.char_id:
            self.push_di(row)

    def forget_reload(self, uniq):
        handle = self.reloads.pop(uniq, None)
        if handle:
            handle.cancel()

    def eject(self, gun):
        """Rounds out of the gun into a fresh stack in the bag. Always a new
        stack: the client is told about it with ss_obj_status;status=1 and
        then asks for its size itself."""
        if not gun["ammo_count"]:
            return None
        stack = self.create(gun["ammo_type"], gun["ammo_count"])
        gun["ammo_count"] = 0
        self.store.update_item(gun["uniq"], ammo_count=0)
        self.push_status(stack, 1)
        self.push_di(stack)
        return stack

    def use_unload(self, p):
        """type=32: empty the magazine into the bag, then report the gun."""
        gun = self.find(p.get("obj"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        if gun["uniq"] in self.reloads:
            self.ack(RES_NOT_READY)
            return
        if not gun["ammo_count"]:
            self.ack(RES_NO_AMMO)
            return
        self.ack(RES_OK)
        self.eject(gun)
        self.push_di(self.store.item(gun["uniq"]))

    def use_mode(self, p):
        """type=64: switch fire mode; target carries the mode number in hex.

        The client already checked fire_mods[mode] != 0 and applies the mode
        itself on res=0 (PersEquip.applyChangeFireMode); nothing to push.
        """
        gun = self.find(p.get("obj"))
        if not gun or gun["root"] != items.FIRE_ARM:
            self.ack(RES_NOT_FOUND)
            return
        try:
            mode = int(str(p.get("target", "")), 16)
        except ValueError:
            self.ack(RES_REFUSED)
            return
        modes = (items.params_of(gun["type_id"]) or {}).get("fire_mods", [])
        if not (0 <= mode < len(modes)) or not modes[mode]:
            self.ack(RES_REFUSED)
            return
        self.store.update_item(gun["uniq"], cur_mode=mode)
        self.ack(RES_OK)

    # --- ss_heap_c ---------------------------------------------------------
    def ss_heap_c(self, p):
        """Split or merge a stack (StuffManager.separateHeap / joinHeap).

        Without trg: take num pieces OUT of obj into a new stack. With trg:
        move num pieces from trg (the one being dragged) INTO obj (the one
        it was dropped on); the client computed num as what fits. Either
        way it changes no size itself: the old stack's size comes back in
        ss_di_heap, a new one arrives by ss_obj_status, an emptied one
        leaves by ss_obj_status;status=0 (items.md 2.2).
        """
        row = self.find(p.get("obj"))
        if not row or row["root"] not in items.HEAPABLE_ROOTS:
            self.ack(RES_NOT_FOUND)
            return
        try:
            num = int(p.get("num", 0) or 0)
        except (TypeError, ValueError):
            num = 0
        if "trg" not in p:
            if not (0 < num < row["count"]):
                self.ack(RES_REFUSED)
                return
            row["count"] -= num
            self.store.update_item(row["uniq"], count=row["count"])
            part = self.create(row["type_id"], num)
            self.ack(RES_OK)
            self.push_status(part, 1)
            self.push_di(part)
            self.push_di(row)
            return
        donor = self.find(p.get("trg"))
        if not donor or donor["uniq"] == row["uniq"]:
            self.ack(RES_NOT_FOUND)
            return
        if donor["type_id"] != row["type_id"]:
            self.ack(RES_NO_ITEM)
            return
        limit = (items.params_of(row["type_id"]) or {}).get("max_count", 1)
        if not num:
            num = donor["count"]
        if num > donor["count"] or row["count"] + num > limit:
            self.ack(RES_REFUSED)
            return
        row["count"] += num
        donor["count"] -= num
        self.store.update_item(row["uniq"], count=row["count"])
        if donor["count"]:
            self.store.update_item(donor["uniq"], count=donor["count"])
        else:
            self.store.delete_item(donor["uniq"])
        self.ack(RES_OK)
        self.push_di(row)
        if donor["count"]:
            self.push_di(donor)
        else:
            self.push_status(donor, 0)

    # --- the stall: ss_create s_type=1, ss_upd ------------------------------
    def open_trade(self, p):
        """ss_create;s_type=1;target=<npc> -> cmdAck.

        Gamer.proposeContact only sends this for an NPC whose userInfo said
        can_trade, so a refusal here means a forged frame or a stale id.
        """
        target = int(p.get("target", 0) or 0)
        entry = self.sess.room.npc(target)
        if not entry or entry[2] != world.TRADER or not self.char_id:
            self.ack(RES_REFUSED)
            return
        self.trade = TradeSession(target, entry[1])
        self.ack(RES_OK)

    def ss_upd(self, p):
        """An operation inside the open stall. Returns False when no stall
        is open, so the caller can fall back to whatever else ss_upd means.

        Closing (s_status=0) is answered with nothing at all: Trade.close
        sends it without registering a cmdAck handler, so an
        acknowledgement here would be consumed by the next command's.
        """
        if not self.trade:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == UPD_CLOSE:
            self.trade = None
        elif code in (UPD_BUY, UPD_BUY_GOLD, UPD_BGPOINTS_BUY):
            self.buy(p, code)
        elif code == UPD_SELL:
            self.sell(p)
        elif code in (UPD_REPAIR, UPD_REPAIR_GOLD, UPD_RESTORE):
            self.repair(p, code)
        elif code == UPD_REG_TROPHY and getattr(self.sess, "trophies", None):
            # At a trophy registrar (trophies.py); one cmdAck either way.
            self.sess.trophies.register(p)
        else:
            self.ack(RES_REFUSED)
        return True

    def repair(self, p, code):
        """ss_upd;s_status=3|5|7 -- mend a worn thing, or restore it.

        The price is not ours to choose: the window prints it before the
        button is pressed, from the frames it was sent, and the server
        charges no more than it printed (repair_prices).

        The bar fills to break/max_break_cur and its LENGTH is
        max_break_cur/max_break_abs (ItemContainer.showBreak), so the second
        number exists in order to fall, and the three buttons are the
        original's three ways with it:

          3, 5  a repair, for afro or for gold alike: the thing comes back
                to nine tenths of the ceiling it had, rounded down, which is
                its ceiling from then on (REPAIR_KEEPS); one worn less than
                that is made whole where it stands, its ceiling brought
                down to its durability. The ceiling never reaches 0 by a
                repair -- a thing at 0/0 reads NaN on the client and drops
                out of the window (PersEquip.getBreakedItems), restore and
                all -- so a thing at 0 of 1 is past mending,
                «не ремонтопригодный», and is refused with «Предмет
                сломан» (RES_BROKEN): the one refusal a listed thing gets
                from a purse that holds its price, and in «Отремонтировать
                все» the client's «Некоторые предметы не удалось
                отремонтировать» says the truth.
          7     a restore, for gold, of anything with a gold price: as new,
                durability and ceiling both at the factory's, for
                Math.round(g_cost * gold_repair_price_mod) hundredths, the
                price the window shows whatever the wear. The client
                animates the bar to full and takes the thing out of the
                slot on a 0 (RepairInterface.repAck, breakBar), so a restore
                that left the durability worn -- as it used to, lifting the
                ceiling alone at a price of its own -- showed one thing and
                did another.

        The window lists what is worn and held (getBreakedItems); a thing in
        the bag is mended by the same rule if a frame names it. Only a
        trader who mends opens the window (userInfo_Trader can_repair): a
        trophy registrar who keeps no stall is refused, as the client would
        refuse him. A worn piece of a set mended from broken counts again at
        once: ss_upd is one of server.GEAR_COMMANDS.

        A press with nothing to do -- a repair of a whole thing, a restore
        of one as new -- is answered 0 and charged nothing. The window never
        lists a whole thing, except one «Отремонтировать все» mended after
        a refusal stopped it listening (repAllAck); a 0 takes that one out
        of the slot, where a 3 said «Сервер не отвечает».
        """
        row = self.find(p.get("obj"))
        if not row or row["root"] not in items.BREAKABLE_ROOTS:
            self.ack(RES_NOT_FOUND)
            return
        trader = getattr(self.trade, "trader_type", None)
        if trophies.is_registrar(trader) and not trophies.keeps_stall(trader):
            # userInfo_Trader tells the client this one mends nothing
            # (server.py, can_repair=0), so the window never opens here.
            self.ack(RES_REFUSED)
            return
        si = items.params_of(row["type_id"]) or {}
        abs_top = si.get("max_break_abs", 0) or row["max_break_cur"]
        top = row["max_break_cur"] or abs_top
        if not top:
            self.ack(RES_REFUSED)
            return
        price_afro, price_gold, price_restore = repair_prices(
            si, row["brk"], row["max_break_cur"])
        afro, gold = self.money()

        if code == UPD_RESTORE:
            if price_restore is None:
                # No gold price, no "Восстановить": the window keeps the
                # button off (repairCostCount), so only a forged frame gets
                # here.
                self.ack(RES_REFUSED)
                return
            new_brk = new_top = abs_top
            paid = (0, price_restore)
        else:
            # Nine tenths of the ceiling, and never under the durability
            # the thing has (REPAIR_KEEPS).
            new_top = max(int(math.floor(top * REPAIR_KEEPS)), min(row["brk"], top))
            if new_top < 1:
                self.ack(RES_BROKEN)
                self.sess.say("Предмет больше не ремонтируется: максимальная"
                              " прочность исчерпана%s" % (
                                  ". Вернуть её можно восстановлением за золото"
                                  if price_restore is not None else ""))
                return
            new_brk = new_top
            paid = (0, price_gold) if code == UPD_REPAIR_GOLD else (price_afro, 0)
        idle = (new_brk, new_top) == (row["brk"], row["max_break_cur"])
        if idle:
            paid = (0, 0)
        elif afro < paid[0] or gold < paid[1]:
            self.ack(RES_NO_MONEY)
            return
        else:
            if any(paid):
                self.set_money(afro - paid[0], gold - paid[1], "repair", row["type_id"])
            self.store.update_item(row["uniq"], brk=new_brk, max_break_cur=new_top)
        log.info("  ..    %s %d: %d/%d -> %d/%d for %d afro, %d/100 G",
                 "nothing to do for" if idle else
                 "restored" if code == UPD_RESTORE else "repaired", row["type_id"],
                 row["brk"], top, new_brk, new_top, paid[0], paid[1])
        self.ack(RES_OK)
        row = self.store.item(row["uniq"])
        if row is not None:
            self.push_di(row)
        self.push_money()

    def buy(self, p, code):
        """ss_upd;s_status=1|4;obj=x<index>;param=<n> -> cmdAck, then the
        item, then the money.

        obj is the INDEX into the trader's type_list, in hex, not a type id
        (Trade.buy: tradeID.toString(16)). param is the number of rounds for
        ammunition, up to a whole stack (5000), and 1 otherwise; the rounds
        come as ONE new stack of that size, priced by buy_price. The client
        adds nothing on res=0: the new instance arrives by
        ss_obj_status;status=1 and the balance by a full userInfo_Player,
        the purse being the in-memory Character's (money/set_money).
        """
        stock = items.stock_for(self.trade.trader_type)
        try:
            index = int(str(p.get("obj", "")), 16)
            n = int(p.get("param", 1) or 1)
        except ValueError:
            self.ack(RES_REFUSED)
            return
        if not (0 <= index < len(stock)):
            self.ack(RES_NOT_FOUND)
            return
        type_id = stock[index]
        root = items.root_of(type_id)
        si = items.params_of(type_id)
        if si is None:
            self.ack(RES_NOT_FOUND)
            return
        # Only rounds are bought by the number: Trade.buy sends 1 for
        # everything else, a stack of junk included, and so does the server.
        # For rounds the "Сколько штук купить?" window runs from 1 to the
        # stall's stack, which is the type's max_count (TradeItem.initParams,
        # TradeInterface.createExchangePan): items.AMMO_STACK, 5000.
        if root != items.AMMO:
            n = 1
        if not (1 <= n <= si.get("max_count", 1)):
            self.ack(RES_REFUSED)
            return
        if code == UPD_BGPOINTS_BUY:
            self.ack(RES_REFUSED)           # no battleground points yet
            return
        # No price in the currency asked for is a refusal in either currency.
        # Only the gold one used to be checked, so an afro purchase (1) of a
        # gold-only item, whose cost is 0, came out at a price of 0: any gold
        # item free to whoever sent the other status code.
        if not (si["g_cost"] if code == UPD_BUY_GOLD else si["cost"]):
            self.ack(RES_REFUSED)
            return
        price = buy_price(si, root, n, code == UPD_BUY_GOLD)
        # The weight of all n. The client's "При покупке вы будете
        # перегружены. Купить?" adds the weight of ONE piece to the bag
        # (TradeInterface.tryToSendTransferToServer reads _weight, not the
        # stack's), measured against the card's max_weight, and sends on a
        # yes: between the card's line and MAX_WEIGHT a purchase goes
        # through overloaded, past it the answer is 27, "Вы перегружены".
        # 5000 rounds of 4 g are 20 kg; of the 100-gram kinds, refused.
        if self.total_weight() + si.get("weight", 0) * n > MAX_WEIGHT:
            self.ack(RES_OVERLOAD)
            return
        afro, gold = self.money()
        if code == UPD_BUY_GOLD:
            if gold < price:
                self.ack(RES_NO_MONEY)
                return
            gold -= price
        else:
            if afro < price:
                self.ack(RES_NO_MONEY)
                return
            afro -= price
        self.set_money(afro, gold, "shop_buy", type_id)
        row = self.create(type_id, n)
        self.ack(RES_OK)
        self.push_status(row, 1)
        self.push_di(row)
        self.push_money()

    def sell(self, p):
        """ss_upd;s_status=2;obj=x<oid>;param=<n> -> cmdAck, then the bag,
        then the money.

        Price as ItemContainer.showCost draws it: cost x smod x sell_mod x
        current quality, per piece for a stack, scaled by use_count for a
        heal item, floored. On res=0 the client removes nothing
        (Trade.applyTransfer only raises an event), so a partial sale is
        reported with ss_di_heap and a whole one with ss_obj_status 0.
        """
        row = self.find(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        si = items.params_of(row["type_id"]) or {}
        # A trophy is never sold: "Вы не можете продать трофеи", the stall
        # says by itself (TradeInterface.checkSellItem), and the cost the
        # wiki gives it is its registration fee (trophies.fee_of). A thing
        # priced in gold alone sells at its gold price in afro
        # (SELL_GOLD_ONLY).
        gold_only = SELL_GOLD_ONLY and si.get("cost", 0) <= 0 and si.get("g_cost", 0) > 0
        if (si.get("cost", 0) <= 0 and not gold_only) or si.get("quest")                 or row["root"] == items.TROPHY:
            self.ack(RES_REFUSED)
            return
        heapable = row["root"] in items.HEAPABLE_ROOTS
        try:
            n = int(p.get("param", 0) or 0)
        except (TypeError, ValueError):
            n = 0
        if not heapable:
            n = 1
        elif not (1 <= n <= row["count"]):
            n = row["count"]
        # The client will not even offer a fully broken thing for sale
        # (TradeInterface.checkSellItem), so refusing it here is agreement
        # with it rather than a rule of our own.
        if row["root"] in items.BREAKABLE_ROOTS and row["brk"] <= 0:
            self.ack(RES_REFUSED)
            return
        cost = si["g_cost"] * progression.GOLD_TO_AFRO_RATE / float(progression.GOLD_OUNCE)             if gold_only else si["cost"]
        unit = cost / float(si.get("sell_num", 1))
        quality = 1.0
        if row["root"] in items.BREAKABLE_ROOTS and row["max_break_cur"]:
            quality = row["brk"] / float(row["max_break_cur"])
        elif row["root"] == items.HEAL and si.get("use_count"):
            # Never above whole: a medicine made when its type held more uses
            # than it does now (6043 had five, 6071 twenty) would otherwise
            # sell for several of itself -- 60 afro x 0.7 x 20/1 = 840.
            quality = min(1.0, row["use_count"] / float(si["use_count"]))
        # Never nothing: the client draws "if(!cost) cost = 1", and a trader
        # who takes a thing away for free is not what the player was shown.
        price = max(1, int(math.floor(unit * n * SMOD * si.get("sell_mod", 1) * quality)))
        afro, gold = self.money()
        self.set_money(afro + price, gold, "shop_sell", row["type_id"])
        if heapable and n < row["count"]:
            row["count"] -= n
            self.store.update_item(row["uniq"], count=row["count"])
            self.ack(RES_OK)
            self.push_di(row)
        else:
            self.forget_reload(row["uniq"])
            self.store.delete_item(row["uniq"])
            self.ack(RES_OK)
            self.push_status(row, 0)
        self.push_money()

    # --- the bank: ss_create s_type=3, ss_upd 0/1/2/6 -----------------------
    #
    # The client moves nothing by itself here. Bank.applyTransfer on res=0
    # only ADDS a put item to the banker's bag and only REMOVES a taken one
    # from it; the player's own bag changes solely by ss_obj_status, which
    # PersEquip handles -- 0 takes the id out of the bag, 1 puts the same
    # object back from ItemFactory.itemStore. So every success is the ack,
    # then that frame, then the new load for the caption.

    def bank_max(self):
        """Capacity in grams: the base plus every expansion bought."""
        row = self.store.character(self.char_id) if self.char_id else None
        steps = (row["bank_steps"] or 0) if row is not None else 0
        return BANK_BASE + steps * BANK_STEP

    def bank_weight(self):
        return sum(weight_of(r) for r in self.banked())

    # Bank.ss_upd reads obj as Number("0x" + obj), and the parser hands an
    # x-value over as the raw string (SCDataParser.getBigUINTData), so the
    # grams go as a BigUInt: hex digits behind an "x". A decimal would be
    # read as hex, and protocol.Hex ("H..") parses as NaN on anything with
    # a letter in it.
    def push_bank_max(self):
        self.send("ss_upd", s_status=BANK_MAX, obj=BigUInt("%x" % self.bank_max()))

    def push_bank_cur(self):
        self.send("ss_upd", s_status=BANK_CUR, obj=BigUInt("%x" % self.bank_weight()))

    def answer_once(self, what, fn, *args):
        """Run one bank operation so the client hears exactly one cmdAck.

        Session.handle logs an exception and answers nothing, and a command
        that registered a handler and got no answer hands every later
        acknowledgement to the wrong one. So a failure before the answer
        went out is answered here with a refusal -- and one after it is only
        logged, because a second cmdAck shifts the queue just the same.
        """
        before = self.acks
        try:
            fn(*args)
        except Exception:
            log.exception("  !!    bank %s failed", what)
            if self.acks == before:
                self.ack(RES_REFUSED)

    def open_bank(self, p):
        """ss_create;s_type=3;target=<npc> -> cmdAck, then capacity and load.

        Bank.proposeBankAck opens the window on res=0 and asks ss_get;slot=24
        straight away; on anything else it shows the ErrorReport text for the
        code and nothing opens -- not the bank, and not the quests of the
        same NPC either, since the whole NPC window hangs off this answer.
        That is 2424 on the black markets, which gives and takes quests.

        So nothing is refused here that the client would have let through.
        In particular the distance is not checked. The rule is the same on
        both sides -- the NPC's cell or one of its six neighbours
        (Gamer.proposeContact, LocationGrid.getSiblings, and
        progression.within_reach) -- but the cell it is applied to is not:
        the client asks from where its walker stands at that moment, and a
        walker animates a path one hex at a time, while the server moved
        the player to the END of the path the moment it echoed it. A player
        who clicks the bank on the way past is beside it on the client and
        far off here, and a refusal would lock them out of a window their
        own client just offered. What is checked is what only a forged frame
        gets wrong: the target has to be a bank standing in the player's own
        room. A distant open is logged, not refused.

        The two weights may follow at once: Bank keeps them until the window
        is drawn, and BankInterface.init reads them from there.
        """
        self.bank = None
        self.answer_once("open", self._open_bank, p)

    def _open_bank(self, p):
        target = int(p.get("target", 0) or 0)
        room = self.sess.room
        entry = room.npc(target) if room is not None else None
        if (not entry or entry[2] != world.COMMONER or not is_bank(entry[1])
                or not self.char_id):
            self.ack(RES_NOT_FOUND)
            return
        loc = self.sess.loc
        if not progression.within_reach(self.sess.pos, entry[0], loc.width,
                                        loc.height):
            log.info("  ..    bank %d opened from cell %d, it stands on %d"
                     " (a click on the way past, or a forged frame)",
                     target, self.sess.pos, entry[0])
        self.trade = None
        self.bank = target
        self.ack(RES_OK)
        self.push_bank_max()
        self.push_bank_cur()

    def bank_upd(self, p):
        """An operation in the open bank. False when none is open, so the
        caller can fall back to whatever else ss_upd means.

        Closing (s_status=0) is answered with nothing: Bank.close sends it
        without registering a handler. Put, take and expand each register
        one, and get exactly one answer whatever happens inside.
        """
        if self.bank is None:
            return False
        try:
            code = int(p.get("s_status", -1))
        except (TypeError, ValueError):
            code = -1
        if code == BANK_CLOSE:
            self.bank = None
            return True
        self.answer_once("update %d" % code, self._bank_upd, code, p)
        return True

    def _bank_upd(self, code, p):
        room = self.sess.room
        if room is None or room.npc(self.bank) is None:
            # The banker is gone from under the window. The session stays
            # marked open, so the next put is refused here too rather than
            # falling through to ss_upd's generic yes and faking a success.
            self.ack(RES_NOT_FOUND)
            return
        if code == BANK_PUT:
            self.bank_put(p)
        elif code == BANK_GET:
            self.bank_get(p)
        elif code == BANK_INCREASE:
            self.bank_increase()
        else:
            self.ack(RES_REFUSED)

    def bank_put(self, p):
        """s_status=1: a thing from the bag into storage.

        Only the bag: the bank window shows no clothes and no hands, so a
        worn or held id is a stale or forged one. A part of a stack arrives
        as two commands -- ss_heap_c splits it (BankInterface.separateAck)
        and the part that stayed under the old id is what is put -- so a
        put always moves a whole row. Quest items may go in: the wiki
        advises keeping them there.
        """
        row = self.find(p.get("obj"))
        if not row or row["slot"] != BAG:
            self.ack(RES_NOT_FOUND)
            return
        cur, top = self.bank_weight(), self.bank_max()
        if cur + weight_of(row) > top:
            self.ack(RES_BANK_FULL)
            self.sess.say("Хранилище заполнено: занято %g кг из %g кг"
                          % (cur / 1000.0, top / 1000.0))
            return
        self.forget_reload(row["uniq"])
        self.store.update_item(row["uniq"], slot=BANK)
        self.ack(RES_OK)
        self.push_status(row, 0)
        self.push_bank_cur()

    def bank_get(self, p):
        """s_status=2: a stored thing back into the bag.

        Never refused for weight: BankInterface asks "При взятии вещи вы
        будете перегружены. Взять?" itself and sends the request only once
        the player agrees, so a refusal here would overrule the answer.
        """
        row = self.find_banked(p.get("obj"))
        if not row:
            self.ack(RES_NOT_FOUND)
            return
        self.store.update_item(row["uniq"], slot=BAG)
        self.ack(RES_OK)
        self.push_status(row, 1)
        self.push_bank_cur()

    def bank_increase(self):
        """s_status=6: one ounce for another 50 kg, as the window says.

        BankInterface.increaseBank only checks that the purse holds a
        hundredth of an ounce, and increaseAck is empty, so a refusal is
        explained in chat and a success shows itself through the new
        capacity and the purse. The count of expansions lives in a column
        of its own, which Character.save does not touch, and is written
        with the purse in one transaction (Store.bank_expand).
        """
        afro, gold = self.money()
        if gold < BANK_STEP_GOLD:
            self.ack(RES_NO_MONEY)
            self.sess.say("Не хватает золота: 50 кг хранилища стоят 1 унцию")
            return
        gold -= BANK_STEP_GOLD
        self.store.bank_expand(self.char_id, afro, gold)
        # The copy in memory follows only once the database has both: it is
        # what Character.save writes back, so charged here and not there it
        # would take the ounce at the next save with nothing given for it.
        ch = self.sess.character()
        if ch.char_id is not None:
            ch.afro, ch.gold = afro, gold
        self.ack(RES_OK)
        self.push_bank_max()
        self.push_money()
