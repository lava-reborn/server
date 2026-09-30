"""The auction house: ah_search, ah_create and ah_op.

The client is lol/core/player/Auction.as (the model, a new one per contact
with an auctioneer), lol/gpui/AuctionInterface.as (the "Аукцион" tab) and
lol/gpui/AuctionMyLotsInterface.as ("Свои товары"). The rules are the wiki's
own article "Аукцион" (data/wiki/pages.json, 2013), written while the game
ran:

  * every auctioneer is one and the same auction house;
  * a bid leaves the purse at once; an outbid bidder gets it back by mail;
    the least next bid is the last one plus 10 %;
  * a buyout is paid at once and the item reaches the buyer by mail;
  * an afro lot costs its seller a commission when it is listed, never
    refunded; the item comes back by mail when it is taken off or unsold,
    and the price reaches the seller by mail when it sells.

Where the wiki is silent or the original cannot be repeated, the owner
decided:

  * the money reaches the seller and the outbid bidder at once, not an
    hour later as on the original;
  * the commission on a stack is exactly what the window prints: the
    item's wire cost (for rounds the price of a pack) times the rate times
    every piece in the stack;
  * gold lots are accepted, although the shipped client cannot make one
    (checkCreateLot enables its button only for an afro starting bid);
  * at most MAX_LOTS lots per seller at once;
  * a lot may be taken off while it carries a bid, and the bid goes back
    to its bidder by mail;
  * the first bid may meet the starting price, every later one must beat
    the last by 10 %;
  * a weapon is sold as it lies in the bag, rounds in the magazine
    included: the snapshot keeps ammo_count and ammo_type, the lot's DI
    shows them, and the buyer's letter delivers them loaded;
  * a letter from the house that still holds money or an item cannot be
    deleted (mail.rmvml): there is nobody to return it to.

On the wire, as the client reads it:

  ah_search;target;page;name;cat;subcat;min_lvl;max_lvl;min_a;max_a;min_g;max_g;sort;s_mode
      -> ah_sresult;page;count;next  on its own queue, NEVER a cmdAck
         then count x ah_lot, each followed by the item's ss_di_*
         (Lot.setItem builds the item with notRequestDI, so nobody asks)
  ah_create;target;obj;time;a_bid;a_buyout;g_bid;g_buyout
      -> cmdAck 0 | 9 (no money for the commission) | 3
  ah_op;target;type;obj;[amount]   type 0 bid, 1 buyout, 2 take off, 3 sell
      -> cmdAck 0 | 40 (no such lot) | 9 (bid too low) | 21 (no money) | 3

Every ah_create and ah_op is answered by exactly one cmdAck, whatever goes
wrong, and every ah_search by exactly one ah_sresult: both queues are FIFO
and global (XMLCCallStack), and Auction.kill never skips the ah_sresult
handler, so one lost answer hands every later one to a stale handler. That
includes a player the server holds dead: combat.Fighter.blocks answers an
ah_search with an empty page rather than swallow it.

Exactly one ss_di_* goes out per lot shown. Each unasked DI also counts
down the client's window of five item requests (ItemFactory.updateCall), so
more than the one the lot needs would open that window wider still.
"""
import functools
import json
import logging
import math
import os
import re
import time

import inventory
import items
import mail
import names
import progression
import rooms
import world
from protocol import BigUInt, Str

log = logging.getLogger("lava")

# Seconds in an auction hour. Tests shrink it to watch a lot run out.
HOUR = float(os.environ.get("LAVA_AUCTION_HOUR", "3600"))
# How often the sweep settles lots that have run out.
SWEEP_SECONDS = float(os.environ.get("LAVA_AUCTION_SWEEP", "30"))
# Lots per page. The pane shows eleven rows and scrolls; the client only
# reads page/count/next and pages with next/prev.
PAGE_SIZE = int(os.environ.get("LAVA_AUCTION_PAGE", "20"))

MY_LOTS = 101          # AuctionMyLotsInterface.getSearchObject: cat=101
ANY = -1
BID, BUYOUT, TAKEOFF, SELL = 0, 1, 2, 3     # Auction.as:25-28
AFRO, GOLD = 0, 1

# AuctionMyLotsInterface.createLot:658-668 sends 24/72/168 from the buttons
# named 12/24/48, and checkComission:833-868 prints the rates the seller is
# charged: afro lots a share of the item's own afro price times the stack,
# gold lots a share of the sale price with a floor (hundredths of an ounce).
AFRO_FEE = {24: 0.05, 72: 0.07, 168: 0.09}
GOLD_FEE = {24: (0.02, 50), 72: (0.03, 75), 168: (0.04, 100)}
# AuctionInterface.RATE_PERCENT: the least next bid is the last one + 10 %.
RATE_STEP = 0.1
# The game's one rate (progression.GOLD_TO_AFRO_RATE, the constants frame's
# gold_to_afro_rate), used only to sort mixed currencies.
GOLD_TO_AFRO = progression.GOLD_TO_AFRO_RATE
MAX_LOTS = int(os.environ.get("LAVA_AUCTION_MAX_LOTS", "20"))
MAX_PRICE = 1_000_000_000
MIN_QUALITY = 0.15     # checkDragItem: "поломанный более чем на 85%"
# The shipped client cannot create a gold lot (checkCreateLot enables the
# button only for a positive afro bid), so this only decides what a
# modified one gets. The owner's answer is yes.
GOLD_ALLOWED = True

RES_OK = 0
RES_REFUSED = 3        # create: nothing shown; op: "У вас недостаточно денег"
RES_LOW = 9            # bid: "Ставка слишком низка"; create: "недостаточно денег"
RES_NO_MONEY = 21      # op: "У вас недостаточно денег"
RES_NO_LOT = 40        # op: "Лот не найден"


# --- what a type is, for the search ------------------------------------------

# AuctionInterface.changedCategory, case 3, in list order; 8 is "Остальное".
CALIBRES = ("556x45", "762x25", "762x39", "762x51", "762x54R", "9mmNato",
            "45", "12mm")
_LVL = re.compile(r"lvl_?(\d+)", re.I)


def _subcat(root, iname, si):
    low = iname.lower()
    if root == items.FIRE_ARM:
        wt = si.get("weapon_type")
        return wt if wt in range(6) else 6
    if root == items.WEAR:
        return si.get("slot_type", ANY)
    if root == items.HEAL:
        return 0 if si.get("max_h_rest", 0) >= si.get("max_st_rest", 0) else 1
    if root == items.AMMO:
        parts = iname.split("_")
        cal = parts[1] if len(parts) > 1 else ""
        return CALIBRES.index(cal) if cal in CALIBRES else 8
    if root == items.TRASH:
        if si.get("quest") or "quest" in low or low.startswith("q_"):
            return 3
        if low.startswith(("bpg_", "bpb_", "codified_bp")) or "blueprint" in low:
            return 2
        if "_part" in low or low.startswith("part_"):
            return 1
        return 0
    return ANY


def _level(iname, si):
    m = _LVL.search(iname)
    if m:
        return int(m.group(1))
    need = si.get("need_skills") or []
    return max(need) if need else 0


@functools.lru_cache(maxsize=None)
def meta(type_id):
    """(root, subcat, level, shown name) of a type. The name is the one the
    lot row draws: the text before "$", and for rounds the mod after it
    (Ammo.set name, Lot.get name)."""
    root, iname = items.catalogue().get(type_id, (None, ""))
    si = items.params_of(type_id) or {}
    raw = names.text(items.STRING_ID_OFFSET + type_id)
    head, _, tail = raw.partition("$")
    shown = head.strip()
    if root == items.AMMO and tail.strip():
        shown += " " + tail.strip()
    return root, _subcat(root, iname, si), _level(iname, si), shown


# --- money --------------------------------------------------------------------

def afro_fee(cost, size, hours):
    """The commission exactly as checkComission prints it:
    Math.ceil(Number(cost) * rate * size), evaluated in the same order, so
    100 afro for three days is 8 and not 7 (100 * 0.07 is 7.000000000000001
    in a double, on both sides). For rounds cost is the price of a pack of
    twenty and size counts single rounds, so 200 rounds of 9 mm at 20 afro a
    pack cost 200/280/360 to list; the owner chose to charge what the window
    shows rather than something the player was never told."""
    return int(math.ceil(float(cost) * AFRO_FEE[hours] * size))


def gold_fee(price, hours):
    share, floor = GOLD_FEE[hours]
    return min(price, max(int(math.ceil(price * share)), floor))


def least_bid(lot):
    """The first bid may meet the starting price; every later one has to
    beat the last by RATE_STEP. The client asks for the 10 % even on the
    first (its field starts at ceil(a_bid * 1.1)); taking less is harmless."""
    if not lot["bidder"]:
        return lot["start_bid"]
    cur = lot["bid"]
    return max(cur + 1, int(math.ceil(cur * (1 + RATE_STEP) - 1e-9)))


def money_text(amount, currency):
    if currency == GOLD:
        return "%.2f G" % (amount / 100.0)
    return "%d афро" % amount


def hours_left(lot, now):
    return max(1, int(math.ceil((lot["ends_at"] - now) / HOUR)))


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# --- letters ------------------------------------------------------------------

def _letter(to_char, subject, body, afro=0, gold=0, snaps=()):
    return dict(to_char=to_char, from_char=mail.SYSTEM_SENDER, kind=mail.LETTER,
                subject=subject[:mail.SUBJECT_MAX], body=body,
                afro=int(afro), gold=int(gold), items_json=json.dumps(list(snaps)))


def _pay(to_char, amount, currency, subject, body):
    afro, gold = (amount, 0) if currency == AFRO else (0, amount)
    return _letter(to_char, subject, body, afro, gold)


def notify(directory, letters):
    """Whoever is online hears of a new letter the way mail.deliver does it."""
    for row in letters or ():
        sess = directory.by_pid(rooms.player_id(row["to_char"]))
        if sess is not None:
            sess.mail.arrived(row)


def settle(lot, buyer, price, buyer_name):
    """Letters closing a sale: the item to the buyer, the price less any
    gold commission to the seller."""
    name = meta(lot["type_id"])[3]
    cur = lot["currency"]
    fee = gold_fee(price, lot["hours"]) if cur == GOLD else 0
    snap = json.loads(lot["item_json"])
    out = [_letter(buyer, "Аукцион: покупка «%s»" % name,
                   "Вы купили «%s» за %s." % (name, money_text(price, cur)),
                   snaps=[snap])]
    body = "«%s» продан игроку %s за %s." % (name, buyer_name, money_text(price, cur))
    if fee:
        body += " Комиссия аукциона: %s." % money_text(fee, cur)
    out.append(_pay(lot["seller"], price - fee, cur,
                    "Аукцион: продан «%s»" % name, body))
    return out


def refund(lot, why):
    """The escrowed bid back to whoever made it, or nothing."""
    if not lot["bidder"]:
        return []
    name = meta(lot["type_id"])[3]
    return [_pay(lot["bidder"], lot["bid"], lot["currency"],
                 "Аукцион: ставка возвращена",
                 "%s «%s». Возвращаем вашу ставку %s."
                 % (why, name, money_text(lot["bid"], lot["currency"])))]


def standing(lot):
    """The bid a settlement is written from, for Store.auction_close/rebid:
    the write lands only while the lot still holds exactly this bid. Every
    letter below names this bidder and this sum, so if an admin removed the
    bidder, or another request settled the lot, in between, nothing is sent
    rather than a "won" letter to somebody who is gone."""
    return (lot["bidder"], lot["bid"])


def give_back(lot, subject, body):
    return [_letter(lot["seller"], subject, body,
                    snaps=[json.loads(lot["item_json"])])]


def sweep(store, directory, now=None):
    """Settle every lot that has run out: sold to its last bidder, or back
    to its seller. Called on start, on a timer and before each request."""
    now = time.time() if now is None else now
    for lot in store.auction_due(now):
        name = meta(lot["type_id"])[3]
        if lot["bidder"]:
            letters = settle(lot, lot["bidder"], lot["bid"], lot["bidder_name"])
        else:
            letters = give_back(lot, "Аукцион: «%s» не продан" % name,
                                "Срок торгов истёк, предмет возвращается.")
        sent = store.auction_close(lot["id"], letters, was=standing(lot))
        if sent is not None:
            log.info("  ..    lot %d (%s) ran out: %s", lot["id"], name,
                     "sold to %s" % lot["bidder_name"] if lot["bidder"] else "unsold")
            notify(directory, sent)


async def run(store, directory):
    import asyncio
    while True:
        try:
            sweep(store, directory)
        except Exception:                                  # noqa: BLE001
            log.exception("auction sweep")
        await asyncio.sleep(SWEEP_SECONDS)


# --- one connection -----------------------------------------------------------

class Auction:
    """What one session does at an auctioneer. Owned by server.Session."""

    def __init__(self, sess, store, directory):
        self.sess = sess
        self.store = store
        self.directory = directory

    # plumbing
    def at_auctioneer(self, p):
        """The target is an auctioneer standing in this player's room. No
        distance: the window is modal and opened only from beside him."""
        room = self.sess.room
        entry = room.npc(_int(p.get("target"), 0)) if room is not None else None
        return entry is not None and entry[2] == world.AUCTIONER

    def _acked(self, what, fn, p):
        """Exactly one cmdAck, even when the handler itself fails."""
        res, then = RES_REFUSED, None
        try:
            res, then = fn(p)
        except Exception:                                  # noqa: BLE001
            log.exception("  !!    %s failed", what)
            res, then = RES_REFUSED, None
        self.sess.send("cmdAck", res=res)
        if then is not None:
            then()

    def refuse(self, why, res=RES_REFUSED):
        # The windows word only a few codes; the reason goes to the chat.
        return res, (lambda: self.sess.say(why))

    # --- ah_search ------------------------------------------------------------
    def search(self, p):
        lots, page, more = [], 0, 0
        try:
            sweep(self.store, self.directory)
            if self.sess.char_id and self.at_auctioneer(p):
                lots, page, more = self.find(p)
        except Exception:                                  # noqa: BLE001
            log.exception("  !!    ah_search failed")
            lots, page, more = [], 0, 0
        now = time.time()
        self.sess.send("ah_sresult", page=page, count=len(lots), next=more)
        for lot in lots:
            self.send_lot(lot, now)

    def find(self, p):
        now = time.time()
        rows = self.store.auction_active(now)
        cat = _int(p.get("cat"), ANY)
        if cat == MY_LOTS:
            rows = [r for r in rows if r["seller"] == self.sess.char_id]
        else:
            rows = [r for r in rows if self.matches(r, p, cat)]
        sort = _int(p.get("sort"), 0)
        key = {
            0: lambda r: meta(r["type_id"])[3].lower(),
            1: lambda r: self.count_of(r),
            2: lambda r: r["ends_at"],
            3: lambda r: r["seller_name"].lower(),
            4: lambda r: (r["bid"] or r["start_bid"]) * (GOLD_TO_AFRO / 100.0
                          if r["currency"] == GOLD else 1),
        }.get(sort, lambda r: 0)
        rows.sort(key=lambda r: (key(r), r["id"]),
                  reverse=_int(p.get("s_mode"), 1) == 0)
        page = max(0, _int(p.get("page"), 0))
        start = page * PAGE_SIZE
        chunk = rows[start:start + PAGE_SIZE]
        return chunk, page, 1 if start + PAGE_SIZE < len(rows) else 0

    @staticmethod
    def count_of(lot):
        snap = json.loads(lot["item_json"])
        return snap["count"] if snap["root"] in items.HEAPABLE_ROOTS else 1

    @staticmethod
    def matches(lot, p, cat):
        root, sub, level, shown = meta(lot["type_id"])
        if cat != ANY and root != cat:
            return False
        subcat = _int(p.get("subcat"), ANY)
        if cat != ANY and subcat != ANY and sub != subcat:
            return False
        text = str(p.get("name") or "").strip().lower()
        if text and text not in shown.lower():
            return False
        lo, hi = _int(p.get("min_lvl")), _int(p.get("max_lvl"))
        if (lo and level < lo) or (hi and level > hi):
            return False
        # A price range names a currency: bounds in afro pass only afro lots
        # that fit them, bounds in gold only gold lots. 0 is "no bound".
        price = lot["bid"] or lot["start_bid"]
        a = (_int(p.get("min_a")), _int(p.get("max_a")))
        g = (_int(p.get("min_g")), _int(p.get("max_g")))
        if any(a) or any(g):
            own = a if lot["currency"] == AFRO else g
            if not any(own):
                return False
            lo, hi = own
            if (lo and price < lo) or (hi and price > hi):
                return False
        return True

    def send_lot(self, lot, now):
        snap = json.loads(lot["item_json"])
        current = lot["bid"] or lot["start_bid"]
        # Only the lot's own pair: a 0 in the other one turns the client's
        # least-bid check (AuctionInterface.rateLot:385) into x*100 >= 0.
        bid_key, buy_key = (("a_bid", "a_buyout") if lot["currency"] == AFRO
                            else ("g_bid", "g_buyout"))
        # Strings last: SCDataParser.parse steps over a string by its
        # decoded length, so nothing after one may depend on it.
        self.sess.send("ah_lot", obj=BigUInt(inventory.oid_of(snap)),
                       **{bid_key: current, buy_key: lot["buyout"]},
                       time_left=hours_left(lot, now),
                       owner=Str(lot["seller_name"]),
                       bidder=Str(lot["bidder_name"] or ""))
        # Unasked, and exactly one: the size of a stack, the charges and the
        # wear only arrive this way. updateItemDI finds the item Lot.setItem
        # just built.
        self.sess.send(inventory.DI_COMMAND.get(snap["root"], "ss_di_heap"),
                       **inventory.di_params(snap, self.store))

    # --- ah_create ------------------------------------------------------------
    def create(self, p):
        self._acked("ah_create", self._create, p)

    def _create(self, p):
        """A thing from the bag becomes a lot.

        A part of a stack arrives as two commands, the way the bank's does:
        "Сколько штук положить?" splits it with ss_heap_c (the pieces that
        stay go into a NEW stack) and separateAck then lists the ORIGINAL
        id, which is left holding the pieces to sell. So a listing always
        takes a whole row.
        """
        sess = self.sess
        if not sess.char_id or not self.at_auctioneer(p):
            return RES_REFUSED, None
        sweep(self.store, self.directory)
        row = sess.inv.find(p.get("obj"))
        if row is None or row["slot"] != inventory.BAG:
            return self.refuse("Выставить можно только предмет из рюкзака")
        si = items.params_of(row["type_id"]) or {}
        if not si.get("exchang") or si.get("quest"):
            return self.refuse("Этот предмет непередаваемый")
        cost = si.get("cost", 0)
        if not cost:
            return self.refuse("У предмета нет цены в афро")
        if row["root"] in items.BREAKABLE_ROOTS and row["max_break_cur"] > 0 \
                and row["brk"] < MIN_QUALITY * row["max_break_cur"]:
            return self.refuse("Предмет поломан более чем на 85%")
        hours = _int(p.get("time"))
        if hours not in AFRO_FEE:
            return RES_REFUSED, None
        prices = [_int(p.get(k), -1) if p.get(k) is not None else 0
                  for k in ("a_bid", "a_buyout", "g_bid", "g_buyout")]
        if any(x < 0 or x > MAX_PRICE for x in prices):
            return RES_REFUSED, None
        a_bid, a_buy, g_bid, g_buy = prices
        if (a_bid or a_buy) and not (g_bid or g_buy):
            currency, start, buyout = AFRO, a_bid, a_buy
        elif (g_bid or g_buy) and not (a_bid or a_buy) and GOLD_ALLOWED:
            currency, start, buyout = GOLD, g_bid, g_buy
        else:
            return RES_REFUSED, None
        if start <= 0:
            return self.refuse("Начальная ставка должна быть больше нуля")
        if buyout and buyout < start:
            return self.refuse("Цена выкупа не может быть ниже начальной ставки")
        if self.store.auction_count(sess.char_id, time.time()) >= MAX_LOTS:
            return self.refuse("Больше %d лотов сразу выставить нельзя" % MAX_LOTS)
        size = row["count"] if row["root"] in items.HEAPABLE_ROOTS else 1
        fee = afro_fee(cost, size, hours) if currency == AFRO else 0
        ch = sess.character()
        if not ch.can_afford(fee, 0):
            return RES_LOW, None
        now = time.time()
        # A reload still counting down would push the gun's DI into a bag
        # that no longer holds it. The rounds already in the magazine stay
        # in the snapshot and are sold with the gun.
        sess.inv.forget_reload(row["uniq"])
        lot = self.store.auction_list(
            row["uniq"], sess.char_id,
            dict(type_id=row["type_id"], root=row["root"],
                 item_json=json.dumps(mail.snapshot(row)),
                 seller=sess.char_id, seller_name=sess.nick,
                 currency=currency, start_bid=start, buyout=buyout,
                 fee=fee, hours=hours, created_at=int(now),
                 ends_at=now + hours * HOUR),
            purse=(sess.char_id, ch.afro - fee, ch.gold))
        ch.afro -= fee
        ch.save(self.store)
        log.info("  ..    lot %d: %s x%d, %s, %dh, fee %d", lot["id"],
                 meta(row["type_id"])[3], size,
                 money_text(start, currency), hours, fee)

        def then():
            # The window has already taken it out of the bag view; the
            # model keeps it until this (PersEquip.ss_obj_status).
            sess.inv.push_status(row, 0)
            if fee:
                sess.push_money()
        return RES_OK, then

    # --- ah_op ------------------------------------------------------------------
    def op(self, p):
        self._acked("ah_op", self._op, p)

    def _op(self, p):
        if not self.sess.char_id or not self.at_auctioneer(p):
            return RES_REFUSED, None
        sweep(self.store, self.directory)
        lot = self.find_lot(p.get("obj"))
        if lot is None:
            return RES_NO_LOT, None
        kind = _int(p.get("type"), -1)
        if kind == BID:
            return self.bid(lot, _int(p.get("amount"), 0))
        if kind == BUYOUT:
            return self.buyout(lot)
        if kind == TAKEOFF:
            return self.takeoff(lot)
        if kind == SELL:
            return self.sell(lot)
        return RES_REFUSED, None

    def find_lot(self, text):
        parsed = inventory.parse_oid(text)
        if not parsed:
            return None
        lot = self.store.auction_lot_by_item(parsed[0])
        if lot is None or (lot["type_id"], lot["root"]) != parsed[1:]:
            return None
        if lot["ends_at"] <= time.time():
            return None
        return lot

    def charge(self, amount, currency):
        """The purse after paying, or None when it cannot."""
        ch = self.sess.character()
        afro, gold = (amount, 0) if currency == AFRO else (0, amount)
        if not ch.can_afford(afro, gold):
            return None
        return (self.sess.char_id, ch.afro - afro, ch.gold - gold)

    def paid(self, purse, letters):
        ch = self.sess.character()
        ch.afro, ch.gold = purse[1], purse[2]
        ch.save(self.store)

        def then():
            self.sess.push_money()
            notify(self.directory, letters)
        return then

    def bid(self, lot, amount):
        me = self.sess.char_id
        if lot["seller"] == me:
            return self.refuse("Нельзя делать ставку на свой лот")
        if lot["bidder"] == me:
            return self.refuse("Ваша ставка и так самая высокая")
        if amount < least_bid(lot) or amount > MAX_PRICE:
            return RES_LOW, None
        if lot["buyout"] and amount >= lot["buyout"]:
            # The window then says "Ваша ставка принята", which is true
            # enough: the lot is won at its buyout, not at the higher bid.
            return self.buyout(lot)
        purse = self.charge(amount, lot["currency"])
        if purse is None:
            return RES_NO_MONEY, None
        sent = self.store.auction_rebid(
            lot["id"], amount, me, self.sess.nick,
            refund(lot, "Вашу ставку перебили на"), purse, was=standing(lot))
        if sent is None:
            return RES_NO_LOT, None
        return RES_OK, self.paid(purse, sent)

    def buyout(self, lot):
        me = self.sess.char_id
        if lot["seller"] == me:
            return self.refuse("Нельзя выкупить свой лот")
        if not lot["buyout"]:
            return RES_REFUSED, None
        purse = self.charge(lot["buyout"], lot["currency"])
        if purse is None:
            return RES_NO_MONEY, None
        letters = (settle(lot, me, lot["buyout"], self.sess.nick)
                   + refund(lot, "Лот выкуплен:"))
        sent = self.store.auction_close(lot["id"], letters, purse, was=standing(lot))
        if sent is None:
            return RES_NO_LOT, None
        return RES_OK, self.paid(purse, sent)

    def takeoff(self, lot):
        """The seller's "Отменить": the item back by mail, the commission
        kept, and a standing bid returned to its bidder (the owner allows
        taking off a lot that already has one)."""
        if lot["seller"] != self.sess.char_id:
            return RES_NO_LOT, None
        name = meta(lot["type_id"])[3]
        letters = (give_back(lot, "Аукцион: «%s» снят с торгов" % name,
                             "Лот снят, предмет возвращается. Комиссия не возвращается.")
                   + refund(lot, "Продавец снял с торгов"))
        sent = self.store.auction_close(lot["id"], letters, was=standing(lot))
        if sent is None:
            return RES_NO_LOT, None
        return RES_OK, (lambda: notify(self.directory, sent))

    def sell(self, lot):
        if lot["seller"] != self.sess.char_id:
            return RES_NO_LOT, None
        if not lot["bidder"]:
            return self.refuse("На этот лот ещё никто не ставил")
        letters = settle(lot, lot["bidder"], lot["bid"], lot["bidder_name"])
        sent = self.store.auction_close(lot["id"], letters, was=standing(lot))
        if sent is None:
            return RES_NO_LOT, None
        return RES_OK, (lambda: notify(self.directory, sent))
