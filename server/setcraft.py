"""Set craft: the upgrader's window, the gold-set exchange, the clothing
rework and the parts upgrade -- and the reworked pieces themselves.

THE PIECES. Every piece of clothing in objects.xml comes in eleven copies,
<slot>_<series>_<variant>_mod00 .. _mod10, and the original reached the ten
above mod00 only by craft (the whole-game survey: A 3 761 and G 4 712 types
«reachable only via rework or set upgrade»). Nothing of theirs survived --
no number, and the original's words for the owner's ladder are another
set's (sets.py). So a reworked piece of the owner's ladder (data/sets.json,
A and G; the quest pieces Q are not reworked, P is out of the game) is its
rung's piece, stepped up, DESIGNED: MOD_ARMOR of its armour class, MOD_WEAR
of its wear and MOD_PRICE of its price for every mod, the same needs and
bonuses, and the same set -- «Новый комплект дает большие бонусы» is the
rung's, and a set of reworked pieces is still that set, on the character's
card and in its figure. Named the owner's way with the mod after it, the way
the original's own names read («Гоглы с фильтром (G) (мод01)»):
«Армейский шлем (G) (мод01)», and described by its rung's words under its
rung's id (desc_of): the same text, not ten copies of it in every client's
preload. items.static_info lays record() over the frame, names.py puts
strings() into names.ALL, and inventory counts a reworked piece as its
rung's (base_of) wherever it counts a set.

A rung is reworked where its pieces are the original's A or G of their
series, named so. Чёрный Ловелас[12] (sold for afro and gold since the
owner's «за афро и за голд», 2026-10-13) is neither: its A is the
original's quest series, whose mods the client has no pictures for, and its
G five types of our own (data/own_items.json) with no mods at all. Its ten
pieces are NOT_REWORKED, as they were while the set was a quest set; the
window still upgrades into it and out of it at mod00 (window_entries). So
are Тёмное Эхо[17]'s, sold the same way since the Абу-Хамед restoration
(2026-10-14): nothing here names either, the rule reads the pieces.

THE UPGRADER'S WINDOW (ss_create;s_type=5; the window itself is upgrader.py's,
shared with the weapon recipes of craft.py). userInfo_Upgrader carries three
parallel lists (Upgrader.as:13-19): in_types, out_types and costs, the costs
in hundredths of an ounce (UpgradeItem shows "G " + cost * 0.01, and the
window's purse is the gold one). The client lists what of its bag is an
in_type; a click shows the out_type and its cost, and «Улучшить» sends
ss_upd;s_status=1;obj=x<oid>;param=<out type> (Upgrade._upgradeItem),
waiting on exactly one cmdAck (upgrAck: 0 is the success picture, anything
else the failure one). For a piece of clothing (upgrade) the server takes
the piece, charges the gold and puts the new one in the bag --
ss_obj_status 0 and 1, its ss_di, the purse: the client moves nothing by
itself. The window is the upgrader's beside him: one left behind in
another room upgrades nothing. Two services, by the upgrader (SLICES; the
entries of window and cost_of):

  upgrade   a set's piece, any mod, for the same piece of the next rung of
            the ladder at mod00, «со скидкой в 40%» (the wiki's Генри and
            Генри ст: «улучшить свой сет на следующий уровень со скидкой в
            40%»): UPGRADE_SHARE of the new piece's price. «Внимание!
            Обменять можно только (G) вещи» (24573): UPGRADE_VARIANTS;
  exchange  a gold piece at mod10 for the next rung's at mod05, «Новую
            часть комплекта вы получите со скидкой, равной 50% от стоимости
            новой части комплекта» (24377, «Обмен б/у снаряжения»): the old
            market's Генри ст, whom the wiki calls «Обмен G Сетов».

A town's upgraders lead up to the rungs of its own band -- Вади-Хальфа's
«Улучшение сетов 6-8[G]» (the map, 5969,1730): Странник[4] to Магриб[6] and
Магриб[6] to Налетчик[8].

THE REWORK AND THE PARTS UPGRADE (data/questgen_setcraft.json, written by
data/build_setcraft.py from generate()). Quest rows, as the original had
them, given and taken by the town's clothing craftsmen: «Мастер ...<Br>Шлем
легионера[6][G]», «Ученик ...[6][A]» -- one master (G) and one pupil (A) per
slot and level, their apprentices (P) idle (texts 9691-9795; Вади-Хальфа's
452, 456 and 457 are the levels 6, 7 and 8). Each takes a piece at modN of
his rung, his slot and his variant and gives it back at modN+1:

  rework    with «Чек на одежду» of the level and variant (27723-40290,
            «Требуется открытая специализация "Переработка" для зачисления
            опыта» 9 x the level). The cheque's price is the owner's
            decision 13 (DESIGNED): CHEQUE_SHARE of the piece's price for a
            step, sold by the craftsmen's treasurers (5767-5769, «дадут тебе
            красивую и ооочень ценную бумажку, увидев которую мастер улучшит
            твою одежду», 24567) -- who stand only in the craft quarters
            behind the owner's wall (447-450), so until those open the
            craftsman sells his own;
  parts     «Я смогу улучшить» (52139-58933): per step 4 000 x the level of
            afro, 2 x the level ounces of silver, a tenth of the level in
            ounces of gold for a G piece, and 40 x the level of «Переработка».
            Silver has no source yet: its ounces are asked in gold at the
            ФСЦ's rate, an ounce of gold for ten of silver (44112), DESIGNED.

Both are services (quests: service -- outside the daily limit and the
server's count of the journal), repeatable, and offered only within the
town's band and only to a bag that holds the piece they work on (offered):
a craftsman's list is his cheques and the step of the piece in hand, not
his twenty rows. A step changes the mod, not the wear: the new piece
keeps the old one's share of wear and of its sagged ceiling (wear,
keep_wear), so it is no repair at a tenth of the price -- a worn piece is
mended at the stall first or reworked worn. The window's upgrade is not a step: its new
piece is new, «независимо от состояния старого».

The rows are written once, by the builder, and the prices in them are the
ladder's of that day; the server does not start on a file the generator
would now write otherwise (check_rows), or a ladder rebuilt with the
wardrobe could sell the cheques below what a stall pays for them.

(P) is filtered everywhere: no variant but A and G is looked at, and
generate() refuses a row naming a premium thing.

OFF IN VADI-HALFA SINCE 2026-10-09. The owner's order «убери из хальфы ...
улучшение сетов 6-8; ремесленники по одежде 6, 7 и 8» switched both of the
town's services off (its slice's "off", one why a service): the windows of
Генри, Генри ст and Тиль are empty again (entries) -- by the type, so
Тиль's in Донгола's black market 103 too, which is open to walkers like
every region; keeping it there would take a window that looks at the room
it stands in -- and the rows stay in
data/questgen_setcraft.json, numbered and worded as they were, with give and
take [] and the why saying so (generate) -- so no string id leaves the
table and a journal that held one names a quest the server still knows.
The town's was the only slice: nobody in the game upgrades, exchanges or reworks
a set or sells a clothing cheque now. The pieces and the cheques already
made keep their names and their set (CHAINS, MOD_OF, strings, record do not
read SLICES). Deleting a line of "off" brings that service back.
"""
import io
import json
import logging
import math
import os
import re

import items
import progression
import quests
import sets

log = logging.getLogger("lava")

# --- the numbers ---------------------------------------------------------------

MODS = 10                  # mod01 .. mod10 above a rung's piece
VARIANTS = ("A", "G")      # the ladder's variants that are reworked
# What a mod adds to its rung's piece, per mod: DESIGNED (nothing survived).
# Ten mods are +40% armour, +50% wear and twice the price -- which is what
# ten steps of the rework cost (CHEQUE_SHARE), so a stall's SMOD of it never
# pays for the step.
MOD_ARMOR = 0.04
MOD_WEAR = 0.05
MOD_PRICE = 0.10

# The upgrader's window (upgrader.py).
UPGRADE_SHARE = 0.60      # «со скидкой в 40%» (the wiki's Генри, Генри ст)
# «Внимание! Обменять можно только (G) вещи» (24573, «Как менять старые
# комплекты»), and the window's purse and prices are gold. Add "A" to
# upgrade an afro set too, priced in gold at the one rate.
UPGRADE_VARIANTS = ("G",)
EXCHANGE_SHARE = 0.50      # «со скидкой, равной 50%» (24377)
EXCHANGE_FROM, EXCHANGE_TO = 10, 5     # «обменять mod10 на mod05 следующего уровня»

# The rework's cheque: CHEQUE_SHARE of the piece's price for a step (the
# owner's decision 13, DESIGNED), bought one or five at a time.
CHEQUE_SHARE = 0.10
CHEQUE_PACKS = (1, 5)
REWORK_XP = 9              # «Переработка» per level: 54, 63, 72 at 6, 7, 8
# The parts upgrade, per level of the rung (52139-58933).
PARTS_AFRO = 4000
PARTS_SILVER = 2           # ounces of silver
PARTS_GOLD = 10            # hundredths of an ounce, a G piece only
PARTS_XP = 40
SILVER_OUNCE = 10          # hundredths of an ounce of gold: 44112, «Одна унция
                           # золота на 10 слитков в одну унцию серебра»

# The craftsmen's treasurers (texts 9688-9690), in every craft quarter.
TREASURERS = (5767, 5768, 5769)
# A craftsman's place among the fifteen of a level: master (G), apprentice
# (P), pupil (A), slot by slot, helm to boots (9691-9705).
RANK = {"G": 0, "P": 1, "A": 2}

# The rows this module's generator writes (data/questgen_setcraft.json).
TYPE_RANGE = range(11000, 13000)

# A town's slice: the band of rungs its upgraders lead up to and its
# craftsmen rework, the band of its parts upgrade, which upgrader does
# what, the first of each level's fifteen craftsmen, and where its rows
# are numbered. A town adds a slice; the code stays as it is. "off" names
# the services of the slice that are switched off, each with its why:
# "window" empties its upgraders' windows (entries), "rows" leaves its rows
# in the table with nobody to give or take them (generate). Delete the line
# to switch the service on again.
SLICES = {
    "Вади-Хальфа": dict(
        band=(6, 8),            # «Улучшение сетов 6-8[G]»; the craftsmen of 6, 7, 8
        parts_band=(5, 8),      # «апгрейд деталей» 5-8
        # Генри (the new market 104) upgrades; Генри ст (the old market
        # 35, «Обмен G комплектов» 5968,1727) upgrades and exchanges; Мастер
        # Тиль (the black market 102, Simple_Upgrader) upgrades. The town's
        # other upgraders have services of their own that are not this
        # module's: the pathologist of the butchers (6765), the gift
        # packers of the pier (2000, 2001), the ФСЦ at the airfields (8213,
        # 8214; Вади-Хальфа's, 528, off the map since 2026-10-10, they stand
        # in the other towns') -- their windows stay empty.
        upgraders={93: ("upgrade",), 5104: ("upgrade", "exchange"), 5: ("upgrade",)},
        craftsmen={6: 5783, 7: 5828, 8: 5873},      # in 452, 456, 457
        types={"rework": 11000, "parts": 11200, "cheque": 11400, "end": 11500},
        off={
            "window": "the owner's order of 2026-10-09 («убери из хальфы ... улучшение "
                      "сетов 6-8»): Генри (93), Генри ст (5104) and Тиль (5) upgrade and "
                      "exchange no set any more, the map's «Улучшение сетов 6-8[G]» "
                      "(5969,1730) and the old market's «Обмен G комплектов» are gone "
                      "(data/map_labels.json), and the talks about the window, 238 and "
                      "239, are off",
            "rows": "the owner's order of 2026-10-09 («убери из хальфы ... ремесленники по "
                    "одежде 6, 7 и 8»): the craftsmen's quarters 452, 456 and 457 are off "
                    "the map (data/retired.json places), so the rework, the parts upgrade "
                    "and the cheques have nobody to give or take them",
        },
    ),
}


def off(slice_, service):
    """The why a slice's service ("window", "rows") is switched off for,
    or None while it is on."""
    return (slice_.get("off") or {}).get(service)


# The original's lines the rows quote or follow, pinned by
# data/build_setcraft.py against texts.xml: «no paper, no work» (24568, the
# end of «Лучшая одежда»), the parts upgrade's finish (52140) and the ФСЦ's
# rate of silver (44112).
ORIGINAL = {
    24568: "Эх, в наше время без бумажки никуда!",
    44112: "Одна унция золота на 10 слитков в одну унцию серебра",
    52140: "Отлично, сейчас сделаем тебе Шлем легионера [5](G)[мод 01]",
}
# The cheques' rows: «Чек на одежду [5][A]», its description, «[6][A]» ...
# level by level from these ids, two rows a level (7099-7178).
CHEQUE_ROWS = {"A": 7099, "G": 7159}
CHEQUE_LEVELS = (5, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20)   # then 20x2

_MOD_NAME = re.compile(r"^(helm|shirt|armor|pants|boots)_(.+)_(A|G|P|Q)_mod(\d\d)$")


def _half_up(x):
    return int(math.floor(x + 0.5))


def _share(price, share):
    """A share of a price, never less than one unit and rounded up: what
    a player is asked is never a fraction the purse cannot hold."""
    return max(1, int(math.ceil(price * share - 1e-9)))


# --- the ladder ------------------------------------------------------------------

def _load_ladder():
    """The owner's rungs as the file writes them: set_type, level, variant,
    family and the five pieces, by level (data/sets.json; sets.py leaves
    the level and the family out of its table)."""
    with io.open(sets.PATH, encoding="utf-8") as fh:
        raw = json.load(fh)["sets"]
    out = []
    for key, rec in raw.items():
        st = int(key)
        out.append(dict(set_type=st, level=int(rec["level"]), variant=rec["variant"],
                        family=rec.get("family", ""), members=dict(sets.SETS[st]["members"])))
    return sorted(out, key=lambda r: (r["level"], r["variant"]))


LADDER = _load_ladder()


def rung(level, variant):
    """The rung of that level and variant, or None."""
    for r in LADDER:
        if r["level"] == level and r["variant"] == variant:
            return r
    return None


def _catalogue():
    """items.catalogue(), or nothing where the client's res is not there (a
    data check run without LAVA_RES): no mods and no cheques then."""
    try:
        return items.catalogue()
    except OSError:
        log.warning("setcraft: no objects.xml, no reworked pieces and no cheques")
        return {}


def _chains():
    """base type -> its eleven copies [mod00 .. mod10] for every A and G
    piece of the ladder whose ten mods objects.xml has; the ones it has
    not, for the record; and the pieces that are not reworked at all: a
    piece that is no A or G of its series by its internal name (Чёрный
    Ловелас's A, the quest series _Q_), or a type of our own (its G,
    items.own) -- the module's docstring."""
    cat = _catalogue()
    if not cat:
        return {}, [], []
    by_name = {n: t for t, (_r, n) in cat.items()}
    chains, missing, unworked = {}, [], []
    for r in LADDER:
        if r["variant"] not in VARIANTS:
            continue
        for slot, base in r["members"].items():
            m = _MOD_NAME.match(cat[base][1])
            if items.own(base) or (m and m.group(3) != r["variant"]):
                unworked.append(base)
                continue
            if not m or m.group(4) != "00":
                missing.append(base)
                continue
            stem = cat[base][1][:-2]
            chain = [base] + [by_name.get("%s%02d" % (stem, k)) for k in range(1, MODS + 1)]
            if None in chain:
                missing.append(base)
                continue
            chains[base] = chain
    return chains, missing, unworked


CHAINS, MISSING, NOT_REWORKED = _chains()
# type -> (its rung's piece, the mod), mod00 included.
MOD_OF = {t: (base, k) for base, chain in CHAINS.items() for k, t in enumerate(chain)}


def base_of(type_id):
    """The rung's piece a reworked one is (itself for a mod00, and for
    anything else): what a set is counted by (inventory)."""
    got = MOD_OF.get(type_id)
    return got[0] if got else type_id


def mod_of(type_id):
    """(rung's piece, mod) of a piece of the ladder, or None."""
    return MOD_OF.get(type_id)


def chain_of(type_id):
    """The eleven copies of the piece a type is one of, or None."""
    got = MOD_OF.get(type_id)
    return CHAINS[got[0]] if got else None


def _mod_record(base, k):
    rec = dict(sets.item(base))
    for key, step in (("armor_class", MOD_ARMOR), ("max_break_abs", MOD_WEAR),
                      ("cost", MOD_PRICE), ("g_cost", MOD_PRICE)):
        if rec.get(key):
            rec[key] = _half_up(rec[key] * (1 + step * k))
    rec["set_type"] = sets.set_of(base)
    return rec


_RECORDS = {chain[k]: _mod_record(base, k)
            for base, chain in CHAINS.items() for k in range(1, MODS + 1)}


def price(type_id):
    """(afro, hundredths of gold) a piece of the ladder is priced at, any mod."""
    rec = _RECORDS.get(type_id) or sets.item(type_id) or {}
    return rec.get("cost", 0), rec.get("g_cost", 0)


def gold_price(type_id):
    """A piece's price in hundredths of an ounce: its gold price, or its
    afro one at the one rate (progression.GOLD_TO_AFRO_RATE)."""
    afro, gold = price(type_id)
    if gold:
        return gold
    return int(math.ceil(afro * progression.GOLD_OUNCE / float(progression.GOLD_TO_AFRO_RATE)))


# --- the cheques ------------------------------------------------------------------

def _cheque_types():
    by_name = {n: t for t, (_r, n) in _catalogue().items()}
    out = {}
    for v in VARIANTS:
        for level in CHEQUE_LEVELS:
            t = by_name.get("Chek_Set_%s_%d" % (v, level))
            if t is not None:
                out[(level, v)] = t
    return out


CHEQUES = _cheque_types()
_CHEQUE_OF = {t: key for key, t in CHEQUES.items()}


def cheque_unit(r):
    """(the step's unit of price, how many units each piece is) of a rung:
    the pieces of a rung are priced 5:3:6:4:2 on the ladder, so half the
    cheapest is the unit, or their greatest common divisor where it is not.
    A cheque is CHEQUE_SHARE of the unit, and a step of a piece asks as
    many cheques as the piece has units: CHEQUE_SHARE of its price."""
    prices = [gold_price(t) if r["variant"] == "G" else price(t)[0]
              for t in r["members"].values()]
    half = min(prices) // 2
    unit = half if half and all(p % half == 0 for p in prices) else 0
    if not unit:
        for p in prices:
            unit = math.gcd(unit, p)
    return unit, {slot: price_of // unit for slot, price_of in zip(r["members"], prices)}


def cheque_price(level, variant):
    """What a cheque of the level and variant costs, afro for A and
    hundredths of gold for G, or None where no rung of the ladder has it."""
    r = rung(level, variant)
    if r is None or (level, variant) not in CHEQUES:
        return None
    unit, _counts = cheque_unit(r)
    return _share(unit, CHEQUE_SHARE)


def cheque_name(level, variant):
    """«Чек на одежду [6]», «... [6] (G)»: the original's row (CHEQUE_ROWS)
    with the level kept -- a cheque is worth nothing without it, and the
    name cleaner would drop it (orig_texts.item_name); DESIGNED."""
    return "Чек на одежду [%d]%s" % (level, " (G)" if variant == "G" else "")


def cheque_desc(level, variant):
    """The original's «Используется для улучшения одежды [6][A].», so."""
    return "Используется для улучшения одежды [%d]%s." % (level, " (G)" if variant == "G" else "")


# --- what the frames and the table of names get ----------------------------------

def _cheque_record(type_id):
    level, variant = _CHEQUE_OF[type_id]
    cost = cheque_price(level, variant)
    if cost is None:
        return None
    if variant == "G":
        # Priced in gold alone and not exchanged, as every G thing.
        return {"cost": 0, "g_cost": cost, "exchang": 0}
    return {"cost": cost, "g_cost": 0}


def record(type_id):
    """What this module lays over a type's frame (items.static_info): a
    reworked piece's numbers and set, a cheque's price -- or None."""
    rec = _RECORDS.get(type_id)
    if rec is not None:
        return rec
    if type_id in _CHEQUE_OF:
        return _cheque_record(type_id)
    return None


def _strings():
    names_ = sets.item_names()
    out = {}
    for base, chain in CHAINS.items():
        for k in range(1, MODS + 1):
            out[items.STRING_ID_OFFSET + chain[k]] = "%s (мод%02d)" % (names_[base], k)
    for (level, variant), t in CHEQUES.items():
        out[items.STRING_ID_OFFSET + t] = cheque_name(level, variant)
        out[items.DESC_ID_OFFSET + t] = cheque_desc(level, variant)
    return out


_STRINGS = _strings()


def strings():
    """Every string id this module's things carry and its text, for
    names.ALL: a reworked piece's name, its rung's and the mod; a cheque's
    name and description, the original's words. A reworked piece's
    description is its rung's, under its rung's id (desc_of)."""
    return dict(_STRINGS)


def desc_of(type_id):
    """The description id the frame of one of this module's things points
    at, or None: a cheque's own (strings), a reworked piece its rung's --
    whatever id the rung's own frame carries (items.static_info), the
    owner's words or the original's, already in names.ALL. The client asks
    the collector for the frame's desc and nothing else (Item.as
    initGDSLStringData), so ten mods of a piece share its one text."""
    if type_id in _CHEQUE_OF:
        return items.DESC_ID_OFFSET + type_id
    got = MOD_OF.get(type_id)
    if not got or not got[1]:
        return None
    info = items.static_info(got[0])
    return (info[1].get("desc") or None) if info else None


def name_of(type_id):
    """The name a piece or a cheque is shown by, for the rows' texts."""
    return _STRINGS.get(items.STRING_ID_OFFSET + type_id) \
        or sets.item_names().get(type_id) or str(type_id)


# --- the upgrader's window ---------------------------------------------------------

def _previous(r, variant, reworked=False):
    """The rung of the variant just below r on the ladder, or None; with
    reworked, the nearest one below whose pieces have their mods (CHAINS)."""
    below = [x for x in LADDER if x["variant"] == variant and x["level"] < r["level"]
             and (not reworked or all(t in CHAINS for t in x["members"].values()))]
    return below[-1] if below else None


def window_entries(slice_, services):
    """[(in type, out type, cost in hundredths)] of an upgrader of this
    slice doing these services (the module's docstring). The upgrade takes
    a piece to the next rung up at mod00, a rung that is not reworked
    (NOT_REWORKED) included, from its piece alone; the exchange is mod10
    for mod05, between rungs that have them, over one that has not."""
    lo, hi = slice_["band"]
    out = []
    for variant in UPGRADE_VARIANTS:
        for nxt in LADDER:
            if nxt["variant"] != variant or not lo <= nxt["level"] <= hi:
                continue
            prev = _previous(nxt, variant)
            if prev is None:
                continue
            swap = _previous(nxt, variant, reworked=True) \
                if "exchange" in services and variant == "G" else None
            for slot in sets.SLOTS:
                src = _copies(prev["members"][slot])
                dst = _copies(nxt["members"][slot])
                if not src or not dst:
                    continue
                if "upgrade" in services:
                    cost = _share(gold_price(dst[0]), UPGRADE_SHARE)
                    out += [(t, dst[0], cost) for t in src]
                old = CHAINS.get(swap["members"][slot]) if swap else None
                new = CHAINS.get(nxt["members"][slot])
                if old and new:
                    out.append((old[EXCHANGE_FROM], new[EXCHANGE_TO],
                                _share(gold_price(new[EXCHANGE_TO]), EXCHANGE_SHARE)))
    return out


def _copies(piece):
    """The copies of a rung's piece the window knows: its eleven mods, the
    piece alone where it is not reworked (NOT_REWORKED), None where its
    mods are missing."""
    chain = CHAINS.get(piece)
    if chain:
        return chain
    return [piece] if piece in NOT_REWORKED else None


def _slice_of_upgrader(type_id):
    """(slice, services) of an upgrader whose window is on, or (None, ())."""
    for slice_ in SLICES.values():
        if type_id in slice_["upgraders"] and not off(slice_, "window"):
            return slice_, slice_["upgraders"][type_id]
    return None, ()


_WINDOWS = {}


def entries(type_id):
    """The window's entries of this upgrader type, [] for one with none."""
    got = _WINDOWS.get(type_id)
    if got is None:
        slice_, services = _slice_of_upgrader(type_id)
        got = _WINDOWS[type_id] = window_entries(slice_, services) if slice_ else []
    return got


def window(type_id):
    """in_types, out_types and costs for this upgrader's userInfo_Upgrader."""
    got = entries(type_id)
    return dict(in_types=[i for i, _o, _c in got], out_types=[o for _i, o, _c in got],
                costs=[c for _i, _o, c in got])


def cost_of(type_id, in_type, out_type):
    """What this upgrader asks for turning in_type into out_type, or None."""
    for i, o, c in entries(type_id):
        if i == in_type and o == out_type:
            return c
    return None


def upgrade(sess, npc_type, row, out_type):
    """«Улучшить» on a piece of clothing in the upgrader's window
    (upgrader.Window: ss_upd;s_status=1;obj=x<oid>;param=<out type>) ->
    cmdAck, then the old piece out and the new one in, then the purse.

    npc_type is the upgrader who opened the window, None once the player
    has left him (upgrader.Window.master) -- the map, a death, /goto, with
    the window never closed: the upgrade is refused (3) and nothing moves.
    The piece has to be in the bag (the window lists the bag alone,
    «Снимите вещь с персонажа и переложите ее в инвентарь»), in any state
    («независимо от состояния старого»); the new one is new."""
    import inventory                   # late: inventory imports this module
    inv = sess.inv
    if npc_type is None:
        inv.ack(inventory.RES_REFUSED)
        return
    if row["slot"] != inventory.BAG:
        inv.ack(inventory.RES_NOT_FOUND)
        return
    cost = cost_of(npc_type, row["type_id"], out_type)
    if cost is None:
        inv.ack(inventory.RES_REFUSED)
        return
    afro, gold = inv.money()
    if gold < cost:
        inv.ack(inventory.RES_NO_MONEY)
        return
    inv.set_money(afro, gold - cost, "set_upgrade", out_type)
    inv.store.delete_item(row["uniq"])
    new = inv.create(out_type)
    log.info("  ..    %s upgrades %d into %d for %d hundredths at %d",
             sess.nick, row["type_id"], out_type, cost, npc_type)
    inv.ack(inventory.RES_OK)
    inv.push_status(row, 0)
    inv.push_status(new, 1)
    inv.push_di(new)
    inv.push_money()


# --- the rework, the parts upgrade, the cheques: the rows ---------------------------

def _count_word(n):
    """«чек», «чека», «чеков» after a number."""
    if n % 10 == 1 and n % 100 != 11:
        return "чек"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "чека"
    return "чеков"


def _ounces(hundredths):
    return "%d.%02d" % (hundredths // 100, hundredths % 100)


def _money(afro, gold):
    parts = []
    if afro:
        parts.append("%d афро" % afro)
    if gold:
        parts.append("%s унции золота" % _ounces(gold))
    return " и ".join(parts)


def craftsman(slice_, level, slot, variant):
    """The craftsman of the slice's level, slot and variant, or None."""
    first = slice_["craftsmen"].get(level)
    if first is None:
        return None
    return first + 3 * sets.SLOTS.index(slot) + RANK[variant]


def _rungs_in(band):
    lo, hi = band
    return [r for r in LADDER if r["variant"] in VARIANTS and lo <= r["level"] <= hi]


def rework_rows(slice_, first):
    hi = slice_["band"][1]
    rows = []
    for r in _rungs_in(slice_["band"]):
        level, variant = r["level"], r["variant"]
        cheque = CHEQUES.get((level, variant))
        if cheque is None or craftsman(slice_, level, "helm", variant) is None:
            continue
        _unit, counts = cheque_unit(r)
        xp = REWORK_XP * level
        for slot in sets.SLOTS:
            chain = CHAINS.get(r["members"][slot])
            if not chain:
                continue
            giver = craftsman(slice_, level, slot, variant)
            k = counts[slot]
            for m in range(MODS):
                a, b = name_of(chain[m]), name_of(chain[m + 1])
                rows.append(dict(
                    type=first + len(rows), kind=quests.BRING_L_OBJ,
                    name="Переделка: %s" % b,
                    start=("Приноси мне «%s» и %d %s на одежду [%d]%s — и будет тебе «%s»."
                           "<Br><Br><b>Требуется открытая специализация «Переработка» для "
                           "зачисления опыта %d.</b><Br><Br><i>Чек на одежду продают "
                           "казначеи ремесленников. Пока до них не добраться, продаю и я.</i>"
                           % (a, k, _count_word(k), level, " (G)" if variant == "G" else "",
                              b, xp)),
                    notfinish=ORIGINAL[24568],
                    finish="Отлично, сейчас сделаем тебе «%s»." % b,
                    give=[giver], take=[giver],
                    objs=[{"obj": chain[m], "num": 1}, {"obj": cheque, "num": k}],
                    rew_obj=[chain[m + 1]], num_rew_obj=[1], rew_afro=0, rew_gold=0,
                    rew_spec_xp={"recycling": xp},
                    repeatable=1, service=True, level=level, max_level=hi, q_type=0,
                    craft="rework",
                    why=("GENERATED (data/build_setcraft.py, setcraft.SLICES): the clothing "
                         "rework of the owner's ladder, %s mod%02d -> mod%02d. RECOVERED: the "
                         "family (27723-40290: a piece and «Чек на одежду» of its level and "
                         "variant for the next mod, «Переработка» 9 x the level), the "
                         "craftsman of the level, slot and variant (9691-9795), the notfinish "
                         "(24568). DESIGNED: the texts, the cheque's price and count (the "
                         "owner's decision 13: %d%% of the piece's price a step), the band."
                         % (name_of(chain[0]), m, m + 1, int(CHEQUE_SHARE * 100)))))
    return rows


def parts_rows(slice_, first):
    hi = slice_["parts_band"][1]
    rows = []
    for r in _rungs_in(slice_["parts_band"]):
        level, variant = r["level"], r["variant"]
        if craftsman(slice_, level, "helm", variant) is None:
            continue
        afro = PARTS_AFRO * level
        gold = PARTS_SILVER * level * SILVER_OUNCE \
            + (PARTS_GOLD * level if variant == "G" else 0)
        xp = PARTS_XP * level
        for slot in sets.SLOTS:
            chain = CHAINS.get(r["members"][slot])
            if not chain:
                continue
            giver = craftsman(slice_, level, slot, variant)
            for m in range(MODS):
                a, b = name_of(chain[m]), name_of(chain[m + 1])
                rows.append(dict(
                    type=first + len(rows), kind=quests.BRING_L_OBJ,
                    name="Улучшение: %s" % b,
                    start=("Принеси мне «%s». Я смогу улучшить тогда то, что ты мне принесешь. "
                           "У нас тут в пустыне очень ценится золото, серебро и конечно афро."
                           "<Br><b>Слушай внимательно что мне нужно принести:</b><Br><b>—</b>%s"
                           "<Br><b>—</b>%s унций золота (серебро — золотом: унция золота за "
                           "10 унций серебра)<Br><b>—</b>%d афро за работу<Br><Br><b>Требуется "
                           "открытая специализация \"Переработка\" для зачисления опыта %d "
                           "единиц.</b><Br><Br><b>Внимание:</b> на вашем счете должна быть "
                           "необходимая сумма в афро и унциях золота."
                           % (a, a, _ounces(gold), afro, xp)),
                    notfinish="",
                    finish="Отлично, сейчас сделаем тебе «%s»." % b,
                    give=[giver], take=[giver],
                    objs=[{"obj": chain[m], "num": 1}],
                    rew_obj=[chain[m + 1]], num_rew_obj=[1], rew_afro=0, rew_gold=0,
                    cost_afro=afro, cost_gold=gold,
                    rew_spec_xp={"recycling": xp},
                    repeatable=1, service=True, level=level, max_level=hi, q_type=0,
                    craft="parts",
                    why=("GENERATED (data/build_setcraft.py, setcraft.SLICES): the parts "
                         "upgrade of the owner's ladder, %s mod%02d -> mod%02d. RECOVERED: "
                         "the family and its price by the level (52139-58933, «Я смогу "
                         "улучшить»: %d x the level of afro, %d x the level ounces of silver, "
                         "a tenth of the level in gold for a G piece, «Переработка» %d x the "
                         "level). DESIGNED: the silver asked in gold at the ФСЦ's rate (44112; "
                         "silver has no source yet), the giver (the original names none: the "
                         "craftsman of the level, slot and variant), the texts' names, the band."
                         % (name_of(chain[0]), m, m + 1, PARTS_AFRO, PARTS_SILVER,
                            PARTS_XP))))
    return rows


def cheque_rows(slice_, first, rework):
    """The cheques the slice's rework asks for, sold by the treasurers and,
    while those stand only behind the wall, by the craftsmen who ask them."""
    hi = slice_["band"][1]
    asked = sorted({(q["level"], o["obj"]) for q in rework for o in q["objs"][1:]})
    rows = []
    for level, cheque in asked:
        _level, variant = _CHEQUE_OF[cheque]
        each = cheque_price(level, variant)
        sellers = sorted({q["give"][0] for q in rework
                          if q["level"] == level and q["objs"][1]["obj"] == cheque})
        for n in CHEQUE_PACKS:
            fee = each * n
            name = cheque_name(level, variant)
            rows.append(dict(
                type=first + len(rows), kind=quests.DEL_OBJ,
                name=name if n == 1 else "%s — %d штук" % (name, n),
                start=("Лучшую одежду делают ремесленники Великого Магриба, но каждому "
                       "встречному они ничего не предложат. Возьми у нас красивую и ооочень "
                       "ценную бумажку, увидев которую мастер улучшит твою одежду.<Br><Br>"
                       "<b>Внимание:</b> при сдаче задания с вашего счёта будет списано %s."
                       % (_money(0 if variant == "G" else fee, fee if variant == "G" else 0))),
                notfinish="",
                finish=ORIGINAL[24568],
                give=list(TREASURERS) + sellers, take=list(TREASURERS) + sellers, obj=0,
                rew_obj=[cheque], num_rew_obj=[n], rew_afro=0, rew_gold=0,
                cost_afro=0 if variant == "G" else fee, cost_gold=fee if variant == "G" else 0,
                repeatable=1, service=True, level=level, max_level=hi, q_type=0,
                craft="cheque",
                why=("GENERATED (data/build_setcraft.py, setcraft.SLICES): %d «Чек на одежду» "
                     "[%d][%s] (objects.xml Chek_Set_%s_%d; its words 7099-7178). DESIGNED "
                     "(the owner's decision 13): sold by the craftsmen's treasurers "
                     "(5767-5769, «дадут тебе красивую и ооочень ценную бумажку», 24567), "
                     "who stand only in the craft quarters behind the wall, so by the "
                     "craftsmen who ask it too; %d%% of a piece's price a step."
                     % (n, level, variant, variant, level, int(CHEQUE_SHARE * 100)))))
    return rows


def switched_off(rows, why):
    """The rows as they stand with nobody to give or take them: give and
    take [], the why first saying so, whom they named and why (the slice's
    off "rows"), then the row's own -- the way a hand-written row is
    switched off (quests.json 414). Types, kinds and texts stay, so their
    string ids stay in the table."""
    for q in rows:
        was = sorted(set(q["give"]) | set(q["take"]))
        q["why"] = "OFF (give/take [], was %s), %s. Was: %s" % (was, why, q["why"])
        q["give"], q["take"] = [], []
    return rows


def generate(slice_):
    """Every row of a slice: rework, parts upgrade, cheques, each family
    numbered from its own first type (slice_["types"]); with nobody to give
    or take them while the slice's "rows" are off (switched_off). Refuses a
    row that names a premium thing or strays out of its block."""
    types = slice_["types"]
    rework = rework_rows(slice_, types["rework"])
    parts = parts_rows(slice_, types["parts"])
    cheques = cheque_rows(slice_, types["cheque"], rework)
    blocks = (("rework", rework, types["parts"]), ("parts", parts, types["cheque"]),
              ("cheque", cheques, types["end"]))
    for family, rows, limit in blocks:
        if rows and rows[-1]["type"] >= limit:
            raise ValueError("setcraft: the %s rows run past %d" % (family, limit))
    rows = rework + parts + cheques
    for q in rows:
        if q["type"] not in TYPE_RANGE:
            raise ValueError("setcraft: quest %d is outside %r" % (q["type"], TYPE_RANGE))
        named = q["rew_obj"] + [o["obj"] for o in q.get("objs", [])]
        if any(items.premium(t) for t in named):
            raise ValueError("setcraft: quest %d names a premium thing" % q["type"])
    if off(slice_, "rows"):
        switched_off(rows, off(slice_, "rows"))
    return rows


def generate_all():
    """The rows of every slice, in the order of SLICES."""
    out = []
    for slice_ in SLICES.values():
        out += generate(slice_)
    return out


# --- who is offered a row ------------------------------------------------------------

_NEEDS = None


def _needs():
    """quest type -> the piece a rework or parts row works on, of the
    loaded table (quests.QUESTS): the first thing it asks for."""
    global _NEEDS
    if _NEEDS is None:
        _NEEDS = {q.type: q.objs[0][0] for q in quests.QUESTS.values()
                  if q.type in TYPE_RANGE and q.kind == quests.BRING_L_OBJ
                  and q.objs and q.objs[0][0] in MOD_OF}
    return _NEEDS


def offered(quest, bag):
    """Whether a row may be offered as far as this module is concerned: a
    rework or parts row only while the bag (bag(): type -> pieces,
    Inventory.bag_pieces) holds the piece it works on. Every other row,
    and every row of another module, is left to the rest of the rules."""
    need = _needs().get(quest.type)
    return need is None or bag().get(need, 0) >= 1


# --- the wear a step keeps -------------------------------------------------------------

def wear(quest, inv):
    """Before a hand-in (server.cmd_q_co): (the rung's piece, {uniq: (brk,
    max_break_cur, max_break_abs)}) of every piece in the bag the hand-in
    may take for a rework or parts row -- its type, not on the table in a
    barter, as Inventory.take_pieces looks -- or None for any other row."""
    import inventory                   # late: inventory imports this module
    need = _needs().get(quest.type)
    if need is None:
        return None
    top = (items.params_of(need) or {}).get("max_break_abs", 0)
    return base_of(need), {r["uniq"]: (r["brk"], r["max_break_cur"], top) for r in inv.rows()
                           if r["type_id"] == need and r["slot"] == inventory.BAG
                           and r["uniq"] not in inv.locked}


def worn_as(old, new_abs):
    """(brk, max_break_cur) of a new piece of factory ceiling new_abs that
    keeps the wear of old (wear): the same share of the ceiling left and the
    same share of that ceiling whole, rounded down -- never a point of
    repair the step did not charge for."""
    brk, top, old_abs = old
    top = top or old_abs
    if not old_abs or not top or not new_abs:
        return new_abs, new_abs
    new_top = new_abs if top >= old_abs else max(1, new_abs * top // old_abs)
    new_brk = new_top if brk >= top else new_top * max(0, brk) // top
    return new_brk, new_top


def keep_wear(worn, given, inv):
    """After the hand-in's take and its reward (given: the rows
    Inventory.give_pieces made): the piece that left the bag passes its
    wear to the next mod of it, which gets its dynamic info again (the
    status and the fresh one went out with it). Nothing for None (not a
    step) or for a reward of another chain."""
    if not worn:
        return given
    base, pieces = worn
    here = {r["uniq"] for r in inv.rows()}
    taken = [w for uniq, w in pieces.items() if uniq not in here]
    if not taken:
        return given
    for row in given:
        got = MOD_OF.get(row["type_id"])
        if got and got[0] == base:
            pass_wear(taken[0], row, inv)
    return given


def pass_wear(old, row, inv):
    """The wear of a piece that left (wear: (brk, max_break_cur,
    max_break_abs)) laid on the new row that stands for it (worn_as), in the
    store and on the client -- its dynamic info again, after the fresh one
    give_pieces sent. Nothing for a thing that does not wear. Shared with
    the weapon craft's upgrade (craft.keep_wear, craft.upgrade)."""
    if not row.get("max_break_cur"):
        return row
    new_abs = (items.params_of(row["type_id"]) or {}).get("max_break_abs", 0)
    brk, top = worn_as(old, new_abs)
    if (brk, top) == (row["brk"], row["max_break_cur"]):
        return row
    row["brk"], row["max_break_cur"] = brk, top
    inv.store.update_item(row["uniq"], brk=brk, max_break_cur=top)
    inv.push_di(row)
    return row


# --- the rows on disk against the generator ----------------------------------------------

OUT_NAME = "questgen_setcraft.json"


def check_rows(path=None):
    """data/questgen_setcraft.json is what generate_all() makes now, or
    ValueError naming the first rows that differ and the builder to run.

    Fatal, as quests.check_items is, and asked by the server beside it
    (server.main): the rows carry the prices of the ladder of the day they
    were built, record() prices the cheques and the mods off the ladder of
    today, and a data/sets.json rebuilt with the wardrobe (data/build_sets.py)
    and not followed by data/build_setcraft.py would sell a cheque below
    what a stall gives for it. A table that stands alone (LAVA_QUESTS: no
    companions) has none of the rows and is not asked; nor is a server
    without objects.xml, which has no mods to make rows of."""
    path = path or quests.quests_path()
    mine = [p for p in quests.companion_paths(path) if os.path.basename(p) == OUT_NAME]
    if not mine or not CHAINS:
        return
    with io.open(mine[0], encoding="utf-8") as fh:
        on_disk = json.load(fh)["quests"]
    want = json.loads(json.dumps(generate_all(), ensure_ascii=False))
    if on_disk == want:
        return
    have = {q.get("type"): q for q in on_disk}
    stale = [q["type"] for q in want if have.get(q["type"]) != q]
    stale += sorted(set(have) - {q["type"] for q in want})
    raise ValueError("%s is not what setcraft.generate_all() makes now (%d rows differ, "
                     "first %s): run data/build_setcraft.py, then data/build_orig_misc.py"
                     % (mine[0], len(stale), stale[:5]))


if MISSING:
    log.warning("setcraft: %d pieces of the ladder have no ten mods in objects.xml: %s",
                len(MISSING), MISSING)
