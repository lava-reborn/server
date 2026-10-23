"""Донгола's trade (the Донгола restoration, 2026-10-13, package TRADE): what
each of its sellers sells, at what price, its weapon craft -- the masters'
recipes, their blueprint stalls, the gunsmiths, the decoder and the
whetstone -- and its plant: the owner's «и потом сделай донголу тоже», made
as Абри was the day before («Добавь каждому продавцу нужные предметы»).

In process:
  1. the things: the bus tickets of Луиджи and Нур-ад-Дин, the lottery
     tickets [14] and [G][14], Тариф's envelope, each named by the original,
     at its article's price -- the ticket from Абри at the fare of the same
     ride (DESIGNED), the gold one in gold alone, a gold thing no stall buys
     back; the envelope a quest thing no stall buys back either;
  2. the stalls: every trader standing in a place of Донгола has its stall
     decided here (data/npcs.json, the town's band of data/shop_bands.json,
     the wiki's list kept, or nothing at all), the lists the wiki tied to the
     wrong trader set right (Галия's pouches off Дари, Тариф's envelope off
     Али-Малистик); nothing on them out of Донгола's band 12-16 (its
     medicine 8_11-16_19), premium, lent or under objects.xml's own words,
     both currencies of the band, Чёрный Ловелас[12] among the sets, each
     gun's rounds on sale in the town; the healers' fees; the upgraders'
     windows;
  3. the weapon craft: the masters of the two camps 96 and 97 (assault
     rifles, machine guns, rifles, sub-machine guns, A and G), the band
     9-16, the blueprints off the chiefs of the camps of their level, on
     sale at the stall of their class in the markets 50 and 197 -- Донгола's
     alone there, and none of Донгола's at Вади-Хальфа's stalls; the
     gunsmiths of «Горные тропы» (625), the decoder (651) and «Точильный
     камень Донголы» (2281) with its blueprints at Одноногий;
  4. the plant: the rocks of Донгола's six mine tiers, each leaving the (Дн)
     ore, the CrBQ rows 13200-13231 (the control rooms' sorting, the
     processing centre 212's lines, the factory 211's 5.56x45 and ПАБ-9), in
     the band of the mines' gates 12-15, and no way through them from afro
     to more afro or from gold to afro.
Then one session, in process, on the wire: Нур-ад-Дин's ticket, Луиджи's
three, Тариф's envelope, a set piece from Дари and a pouch from Галия, a
knife blueprint from Одноногий for gold (for afro refused), an ingot refused
for afro at Мортимер (197), rounds at the oasis, a gift at Элизабет Стюарт.

    LAVA_RES=.../res python3 server/test_dongola_trade.py
"""
import asyncio
import collections
import json
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB = os.path.join(tempfile.mkdtemp(), "dongola_trade.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START", "LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import production  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "торговля Донголы: лавки, цены, улучшение оружия, точильный камень и завод"

OFF = items.STRING_ID_OFFSET
cat = items.catalogue()
MT = world.mob_types()
items.preload()
with open(os.path.join(ROOT, "data", "orig_items.json"), encoding="utf-8") as _fh:
    ORIG = json.load(_fh)["items"]

# --- the places, the people, the things --------------------------------------------------
STATION, MARKET, QUARTER, BLACK, YARD, OASIS, NEW_MARKET, PIER = 49, 50, 79, 103, 159, 195, 197, 445
WAREHOUSES = (112, 113, 114)
ABRI_PORT, HALFA_STATION = 187, 37
# Донгола's places a player gets into where a trader stands: the town's places of
# data/shop_bands.json but the clothing market 469, which the package WORLD cuts with
# its «Торговцы одеждой» (as Абри's 378: in the band's places still, nobody gets in),
# and the three warehouses.
DONGOLA_PLACES = (STATION, MARKET, QUARTER, BLACK, YARD, OASIS, NEW_MARKET, PIER) + WAREHOUSES
# Every place of Донгола the plan's walk reaches (DESIGN.md 7.2): no trader stands in
# any of them but those above.
REACHED = (49, 50, 72, 73, 74, 77, 79, 91, 93, 96, 97, 98, 99, 103, 105, 112, 113, 114, 115,
           144, 145, 146, 147, 155, 157, 159, 161, 162, 195, 197, 208, 209, 210, 211, 212, 253,
           445, 625, 697, 1042, 607, 608, 1009, 597, 1007, 631, 632, 633, 634, 635, 663, 664,
           665, 1031, 1032, 1033, 1224, 1225, 1226, 614, 616, 1013, 1015, 1020, 1021, 1022, 1023,
           1214, 618, 619, 620, 621, 622, 702, 703, 704, 705, 150)

NUR, LUIGI, HASSIR, TARIF, ALI, ONE_LEG, DARI, GALIA = 156, 1179, 105, 678, 6513, 1153, 1213, 1233
LOTTERY, GOLD_LOTTERY, ELIZABETH, PILOT, MORTIMER, AMMO_OASIS = 663, 712, 1965, 4676, 1188, 1230
FOOD, SUPPLY, KHAN_SELL, JUT, SAMUEL, FLAG = 155, 2181, 2391, 207, 893, 1011
BLUEPRINT_STALLS = {"assault": 580, "mg": 583, "rifle": 584, "smg": 585}
TICKET_TO_ABRI, TICKET_TO_HALFA, TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA = 6544, 6545, 6546, 6547
KEY, GOLD_KEY, ENVELOPE = 2648, 2651, 1309
GIFTS = tuple(range(4329, 4353))                # gift_kid_1..10, gift_girl_1..10, gift_0..3
KNIFE_PRINTS = tuple(range(6626, 6632))         # Заточка / Эргономика / both, 14у and 16у
INGOTS = (7620, 4796, 4797)
POUCHES = [3577, 3580, 5613, 3578, 3579]        # автоматчика, пулеметчика, рукопашника, снайпера,
                                                # спецназовца: Галия's article, its order
LOVELACE = tuple(range(11721, 11726)) + tuple(range(60000, 60005))
OASIS_ROUNDS = [6104, 6105, 6106, 6108, 6107, 6110, 6111, 6115, 6116, 6117, 6118, 6120, 6119,
                6122, 6123, 6127, 6113, 6125, 6109, 6121, 6114, 6126, 6112, 6124]
# The package WORLD holds the test trader 5113 out of the black market (data/
# schedule.json held_out) and stands the lottery men all year (world.SEASON_KEPT):
# 663 in both markets, 712 in the black market. Until it is merged 5113 stands there
# with the wiki's empty stall and the lottery men nowhere -- their lists decided all
# the same.
HELD_OUT = {BLACK: {5113}}
WORLD_PUTS = {MARKET: {LOTTERY}, NEW_MARKET: {LOTTERY}, BLACK: {GOLD_LOTTERY}}

# Each trader of Донгола's places and what decides its stall there, 2026-10-13
# (DESIGN.md 6.2): "band" the town's band of its kinds before its own list
# (data/shop_bands.json SELLERS), "own" data/npcs.json's list, "wiki" the wiki's list
# as it was (items.stock_table; Гофус, Бернар and the doctor's junior helper, as in
# Абри's quarter), "none" no list anywhere and an empty stall (Самуэль, whose service
# is a quest; the warehouses' flag, whose is the repair).
BAND, OWN_, WIKI, NONE = "band", "own", "wiki", "none"
DECIDED = {
    STATION: {NUR: OWN_},
    MARKET: {FOOD: BAND, 580: OWN_, 583: OWN_, 584: OWN_, 585: OWN_, LOTTERY: OWN_},
    QUARTER: {TARIF: OWN_, ALI: OWN_},
    BLACK: {SAMUEL: NONE, ONE_LEG: BAND, 1208: BAND, 1209: BAND, 1210: BAND, 1211: BAND,
            DARI: BAND, 1214: BAND, 1215: BAND, GALIA: BAND, GOLD_LOTTERY: OWN_},
    YARD: {SUPPLY: BAND},
    OASIS: {JUT: BAND, 1229: BAND, AMMO_OASIS: OWN_},
    NEW_MARKET: {FOOD: BAND, 580: OWN_, 583: OWN_, 584: OWN_, 585: OWN_, LOTTERY: OWN_,
                 1013: WIKI, MORTIMER: OWN_, 1196: WIKI, 2017: WIKI},
    PIER: {ELIZABETH: OWN_, KHAN_SELL: BAND, PILOT: OWN_},
    112: {FLAG: NONE}, 113: {FLAG: NONE}, 114: {FLAG: NONE},
}
# The lists of data/npcs.json this restoration wrote (or kept: Мортимер's, Абу-бакр's
# beans, Хассир's). The blueprint stalls' are build_weaponcraft --stock's (below).
OWN = {
    # and since 2026-10-14 the tickets of Абу-Хамед's ride, there and back
    # (server/test_abuhamed_trade.py)
    NUR: [TICKET_FROM_DONGOLA, 1567, 1639],
    LUIGI: [TICKET_TO_HALFA, TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA],
    HASSIR: [TICKET_TO_ABRI, TICKET_TO_HALFA],
    TARIF: [ENVELOPE],
    ALI: [],
    DARI: [],
    GALIA: POUCHES,
    LOTTERY: [KEY],
    GOLD_LOTTERY: [GOLD_KEY],
    ELIZABETH: list(GIFTS),
    PILOT: [],
    AMMO_OASIS: OASIS_ROUNDS,
    ONE_LEG: list(KNIFE_PRINTS),
    # the bag of beans, as before, and since the integration of 2026-10-13
    # «Фуль» (334): «Старые приятели» (647) and «Фуль ему!» (658) send the
    # player to buy it «в местной лавке»; until then only Вади-Хальфа's 81
    # sold it.
    FOOD: [333, 334],
    MORTIMER: list(INGOTS),
}
LO, HI = 12, 16

with open(os.path.join(ROOT, "data", "questgen_weaponcraft.json"), encoding="utf-8") as _fh:
    CRAFT_DOC = json.load(_fh)


def city_of(r):
    return r["craft"]["key"].split(":")[1]


DN_ROWS = [r for r in CRAFT_DOC["quests"] if city_of(r) == "dongola"]


def stood(loc_id):
    """The trader types standing in a place, as its room puts them down."""
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    out = []
    for npc in room.npcs.values():
        if npc.root == world.TRADER and npc.type_id not in out:
            out.append(npc.type_id)
    return out


def standing(loc_id):
    """Every type standing in a place, counted."""
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)
    return collections.Counter(npc.type_id for npc in room.npcs.values())


def price(t):
    p = items.params_of(t)
    return (p["cost"], p["g_cost"])


def shown(t):
    return names.ALL.get(OFF + t)


def orig(t):
    rec = ORIG.get(str(t)) or {}
    return (rec.get("name_id"), rec.get("desc_id"))


def sold_for(t, n=1):
    """What a stall pays for n of a thing sold at once (inventory's sale), or 0:
    nothing for a thing with no afro price or a quest's."""
    si = items.params_of(t)
    if not si.get("cost") or si.get("quest"):
        return 0
    return max(1, int(math.floor(si["cost"] / float(si.get("sell_num", 1)) * n
                                 * inventory.SMOD * si.get("sell_mod", 1))))


def gold_only(t):
    p = items.params_of(t)
    return p["g_cost"] > 0 and not p["cost"]


def level_of_bp(t):
    return int(cat[t][1].rsplit("lvl", 1)[1].split("_")[0])


# --- 1. the things ----------------------------------------------------------------------
print("the things")
check("the bus tickets: «Билет в Донголу из Абри» 100 afro (its article says 200; the fare of"
      " the same ride, 275, is 100: DESIGNED), «Билет в Абри из Донголы» 110, its article's",
      [(shown(t), price(t)) for t in (TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA)],
      [("Билет в Донголу из Абри", (100, 0)), ("Билет в Абри из Донголы", (110, 0))])
check("  ..no ticket dearer than its ride for afro: 6546 against Луиджи's fare (data/quests.json"
      " 275), as Абри's 6544 against Хассир's 273",
      (price(TICKET_TO_DONGOLA)[0] <= quests.get(275).cost_afro,
       price(TICKET_TO_ABRI)[0] <= quests.get(273).cost_afro), (True, True))
check("  ..the tickets the original's rows of the run 6901-6908 (rule 7i), the route of Хальфа's"
      " direct ride on sale nowhere, and Абу-Хамед's ticket from Донгола at Нур-ад-Дин since"
      " 2026-10-14 (server/test_abuhamed_trade.py)", (orig(TICKET_TO_DONGOLA),
                                                         orig(TICKET_FROM_DONGOLA),
                                                         sorted({t for tr in set(
                                                             items.stock_table()) | set(
                                                             npcs.STOCK) for t in
                                                             items.stock_for(tr)} & {290, 336,
                                                                                     1567})),
      ((6905, 6906), (6907, 6908), [1567]))
check("the lottery tickets of Донгола's lottery men: [14] 2400 afro, the gold [G][14] 3 G in gold"
      " alone (its article: 2400 afro or 3 G; Абри's and Вади-Хальфа's gold ones the same)",
      [(cat[t][1], price(t)) for t in (KEY, GOLD_KEY)],
      [("DnLoteryKey_13_14", (2400, 0)), ("DnLoteryKey_g_13_14", (0, 300))])
check("  ..named by the original's tickets' run (6923, 6926), the [8] ticket's words (6919)",
      [orig(t) for t in (KEY, GOLD_KEY)], [(6923, 6919), (6926, 6919)])
check("Тариф's «Конверт» (qEnvelope), 30 000 afro: «Конверт ты можешь купить у меня, он стоит"
      " 30 000 афро» (texts.xml 60014); a quest thing, so no stall buys it back",
      (shown(ENVELOPE), orig(ENVELOPE), price(ENVELOPE), items.params_of(ENVELOPE)["quest"],
       sold_for(ENVELOPE)), ("Конверт", (6240, 6241), (30000, 0), 1, 0))
EVERY = (TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA, KEY, GOLD_KEY, ENVELOPE) + GIFTS
check("every one of them named and described by the original (names.ALL), not by"
      " objects.xml's words; no premium, none a quest lends",
      [t for t in EVERY if shown(t) in (None, cat[t][1]) or not names.known(
          items.params_of(t)["desc"]) or items.premium(t) or quests.lent(t)], [])
check("the gold ticket is a gold thing: never off a body, and no stall buys it back",
      (combat.gold_item(GOLD_KEY), combat.drops_on_death(GOLD_KEY), sold_for(GOLD_KEY),
       inventory.SELL_GOLD_ONLY), (True, False, 0, False))
check("  ..and every afro one sells back for 0.7 of its price at most",
      [t for t in EVERY if not gold_only(t) and sold_for(t) > 0.7 * price(t)[0]], [])

# --- 2. the stalls ------------------------------------------------------------------------
print()
print("the stalls")
AT = {p: [t for t in stood(p) if t not in HELD_OUT.get(p, ())] for p in DONGOLA_PLACES}
check("every trader standing in a place of Донгола has its stall decided (data/npcs.json, the"
      " town's band, the wiki's list kept, or none), and the table names nobody who stands"
      " nowhere",
      ({p: sorted(t for t in AT[p] if t not in DECIDED[p]) for p in DONGOLA_PLACES},
       {p: sorted(t for t in DECIDED[p] if t not in AT[p] and t not in WORLD_PUTS.get(p, ()))
        for p in DONGOLA_PLACES}),
      ({p: [] for p in DONGOLA_PLACES}, {p: [] for p in DONGOLA_PLACES}))
check("  ..and no trader stands in any other place of Донгола the plan's walk reaches",
      {p: stood(p) for p in REACHED if p not in DONGOLA_PLACES and stood(p)}, {})
how = {}
for p, decided in DECIDED.items():
    for t, kind in decided.items():
        if kind == BAND:
            ok = t in shop_bands.SELLERS
        elif kind == OWN_:
            ok = npcs.stock(t) is not None
        elif kind == WIKI:
            ok = npcs.stock(t) is None and t not in shop_bands.SELLERS \
                and items.stock_for(t, p) == items.stock_table().get(t)
        else:
            ok = npcs.stock(t) is None and t not in shop_bands.SELLERS \
                and items.stock_for(t, p) == []
        if not ok:
            how[(p, t)] = kind
check("  ..each the way the table says", how, {})
check("the lists of data/npcs.json, trader by trader (DESIGN.md 6.2): Нур-ад-Дин the ticket to"
      " Абри, Луиджи all three of Абри's and Донгола's, Тариф the envelope, Дари nothing of his"
      " own, Галия her pouches, the lottery men their tickets, Элизабет Стюарт her 24 gifts, the"
      " pilot nothing, the oasis's rounds man every СТ and ОТ, Одноногий his whetstone's"
      " blueprints", {t: npcs.stock(t) for t in OWN}, OWN)
check("  ..the black market's and the quarter's lists where the wiki's links had shifted them:"
      " Галия's pouches off Дари, Тариф's envelope off Али-Малистик, Али-Малистик's key parts"
      " (the cut «Мантикора») on nobody's stall",
      (items.stock_table().get(DARI), items.stock_table().get(ALI),
       sorted(set(items.stock_table().get(TARIF)) & {t for s in AT.values() for tr in s
                                                     for t in items.stock_for(tr)})),
      (POUCHES, [ENVELOPE], []))
check("Луиджи sells both tickets of Донгола's ride beside the one home, Хассир his two",
      (items.stock_for(LUIGI, ABRI_PORT), items.stock_for(HASSIR, HALFA_STATION)),
      ([TICKET_TO_HALFA, TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA],
       [TICKET_TO_ABRI, TICKET_TO_HALFA]))

STALLS = {(p, t): items.stock_for(t, p) for p in DONGOLA_PLACES for t in AT[p]}
STALLS.update({(p, t): items.stock_for(t, p) for p, ts in WORLD_PUTS.items() for t in ts})
check("Донгола is the band 12-16 of data/shop_bands.json, its places these",
      [(c[0], c[1], c[2], sorted(c[3])) for c in shop_bands.CITIES if c[0] == "Донгола"],
      [("Донгола", LO, HI, [49, 50, 79, 103, 159, 195, 197, 445, 469])])
check("no gun, knife or set piece out of 12-16 on a seller's stall of Донгола, no medicine out"
      " of its tiers 8_11-16_19; every one of a seller's band both ways, the ordinary for afro"
      " and the (G) for gold, but the apothecary Джут's gold alone and Абу-бакр's afro alone",
      (sorted((p, t, x) for (p, t), s in STALLS.items() for x in s if t in shop_bands.SELLERS
              and shop_bands.band_ware(x) and not shop_bands.fits(x, LO, HI)),
       sorted((p, t) for (p, t), s in STALLS.items() if t in shop_bands.SELLERS
              and shop_bands.SELLERS[t] and not shop_bands.only(t)
              and not {gold_only(x) for x in s if shop_bands.band_ware(x)} >= {True, False}),
       sorted({(t, shop_bands.only(t)) for (p, t) in STALLS if shop_bands.only(t)})),
      ([], [], [(FOOD, "afro"), (JUT, "gold")]))
MEDS = sorted({shop_bands.level_of(x) for s in STALLS.values() for x in s
               if shop_bands.medicine(x)})
check("  ..the medicine of three tiers by their floors: 8_11, 12_15, 16_19 (the band's and the"
      " one under it)", MEDS, [8, 12, 16])
check("Чёрный Ловелас[12], A and G, on the set sellers' stalls (Дари, Галия): the band's floor"
      " 12 is Донгола's too", {t: sorted(set(LOVELACE) - set(STALLS[(BLACK, t)]))
                               for t in (DARI, GALIA)}, {DARI: [], GALIA: []})
check("Дари: the town's sets and nothing of his own; Галия: the town's sets, then her"
      " pouches, each with its (G) right after it",
      (STALLS[(BLACK, DARI)] == shop_bands.goods(("sets",), LO, HI), STALLS[(BLACK, GALIA)][-10:],
       len(STALLS[(BLACK, GALIA)])),
      (True, [3577, 3599, 3580, 3602, 5613, 5614, 3578, 3600, 3579, 3601], 60))
check("Одноногий: the town's knives and his whetstone's six blueprints after them",
      STALLS[(BLACK, ONE_LEG)], shop_bands.goods(("knives",), LO, HI) + list(KNIFE_PRINTS))
check("the oasis's «Торговец патронами» (1230): every СТ and ОТ of his list, nothing cut",
      STALLS[(OASIS, AMMO_OASIS)], OASIS_ROUNDS)
CRAFT_PRINTS = {r["craft"]["blueprint"] for r in CRAFT_DOC["quests"]
                if r["craft"]["family"] == "upgrade"}
check("nothing premium on a stall of Донгола, nothing a quest lends, each thing priced in one"
      " currency but Мортимер's ingots (items.GOLD_INGOTS: sold for gold, loot worth afro) and"
      " the masters' blueprints the afro line asks, which their articles price both ways (as at"
      " Вади-Хальфа's stalls, server/test_halfa_weaponcraft.py)",
      sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
             if items.premium(x) or quests.lent(x)
             or (bool(price(x)[0]) == bool(price(x)[1]) and x not in items.GOLD_INGOTS
                 and x not in CRAFT_PRINTS)), [])
check("no thing on a stall of Донгола shows objects.xml's own words, or a description the"
      " preload lacks", sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
                               if shown(x) in (None, cat[x][1])
                               or (items.params_of(x)["desc"] != ""
                                   and not names.known(items.params_of(x)["desc"]))), [])
ROUNDS = {x for s in STALLS.values() for x in s if items.root_of(x) == items.AMMO}
check("every gun on a stall of Донгола has a round it chambers on sale in the town",
      sorted({x for s in STALLS.values() for x in s if items.root_of(x) == items.FIRE_ARM
              and not set(items.params_of(x)["comp_array"]) & ROUNDS}), [])
check("the stalls' sizes: none longer than 64 (the prison's supply man's 61 the longest)",
      max(len(s) for s in STALLS.values()) <= 64, True)
check("the healers' fees: Грегори (138) and the oasis's Лекарь (1268) 500, the prison's"
      " Андрей Евгеньевич (2109) 600 (server/test_healer_fees.py)",
      {t: npcs.healer_price(t, 10) for t in (138, 1268, 2109)}, {138: 500, 1268: 500, 2109: 600})
# The upgraders of Донгола's places: Элизабет Стюарт's children (2004/2005), Альма
# (1797, her amulet's «Посланник Смерти» cut), the special forces' changer (2242) --
# empty windows, as Абри's; Жозеф де Гобино (7548) in the oasis the [Q] Маузер's twelve,
# as in every oasis.
check("the upgraders of Донгола's places: empty windows, Жозеф де Гобино's in the oasis the [Q]"
      " Маузер's twelve, given by him",
      ({t: len(craft.upgrader_lists(t)["out_types"]) for t in (2004, 2005, 1797, 2242, 7548)},
       7548 in standing(OASIS), len(quests.given_by(7548))),
      ({2004: 0, 2005: 0, 1797: 0, 2242: 0, 7548: 12}, True, 12))

# --- 3. the weapon craft --------------------------------------------------------------------
print()
print("the weapon craft")
MASTERS = {335: ("assault", "A"), 382: ("assault", "G"), 345: ("mg", "A"), 385: ("mg", "G"),
           346: ("rifle", "A"), 386: ("rifle", "G"), 347: ("smg", "A"), 387: ("smg", "G")}
GUNSMITHS = {"rifle": 244, "mg": 246, "assault": 247, "smg": 249}
WHETSTONE, DECODER = 2281, 651
CHIEFS = {(12, 14): (93, 91), (15, 16): (98, 99)}


def fam(name):
    return [r for r in DN_ROWS if r["craft"]["family"] == name]


ups = fam("upgrade")
check("Донгола's rows: repeatable services of the band 9-16 (the owner's decision 27), every"
      " family, loaded (quests.get)",
      (sorted({(r["repeatable"], r["service"], r["level"], r["max_level"]) for r in DN_ROWS}),
       sorted({r["craft"]["family"] for r in DN_ROWS}),
       [r["type"] for r in DN_ROWS if quests.get(r["type"]) is None]),
      ([(1, True, 9, 16), (1, True, 9, 20)], ["assembly", "decode", "knife", "salvage", "upgrade"], []))
check("the masters stand in the masters' camps the labels name: assault rifles and machine guns"
      " in 96, rifles and sub-machine guns in 97",
      ({t: t in standing(96) for t in (335, 382, 345, 385)},
       {t: t in standing(97) for t in (346, 386, 347, 387)}),
      ({t: True for t in (335, 382, 345, 385)}, {t: True for t in (346, 386, 347, 387)}))
check("each recipe at the master of its gun's class and line, A or G, its gun of the band"
      " with the wiki's table, its blueprint of its own level",
      ([r["type"] for r in ups if MASTERS.get(r["give"][0]) != (
          craft.weapon_of(r["craft"]["gun"]), r["craft"]["line"]) or r["take"] != r["give"]],
       sorted({r["craft"]["line"] for r in ups}),
       [r["type"] for r in ups if not 9 <= r["craft"]["level"] <= 16
        or r["craft"]["gun"] not in items.wiki()
        or level_of_bp(r["craft"]["blueprint"]) != r["craft"]["level"]]),
      ([], ["A", "G"], []))
check("  ..every master with recipes (no shotgun master: the shotguns of 9-12 have none)",
      sorted({r["give"][0] for r in ups}), sorted(MASTERS))
worse = []
for r in ups + fam("knife"):
    a = items.params_of(r["craft"]["gun"])["max_break_abs"]
    b = items.params_of(r["craft"]["mod"])["max_break_abs"]
    if b < a or price(r["craft"]["gun"]) != price(r["craft"]["mod"]) and r in ups:
        worse.append(r["type"])
check("  ..a modification at its gun's price and never a lower wear ceiling (the article's slip"
      " AUG /Hbar Mod VIII, 550 against 2750, makes no row)",
      (worse, [r["craft"]["key"] for r in ups if r["craft"]["key"] == "upgrade:dongola:50989"]),
      ([], []))
camp_bosses = {}
for (lo, hi), locs in CHIEFS.items():
    for loc in locs:
        for t in standing(loc):
            if mobs.stats(t).role == "boss":
                camp_bosses.setdefault(t, set()).add((lo, hi))
stray = []
for r in ups:
    for o in r["objs"][1:]:
        for m in o.get("mobs", []):
            if not any(lo <= r["craft"]["level"] <= hi for lo, hi in camp_bosses.get(m, ())):
                stray.append((r["type"], m))
check("the stat blueprints of 9-16 drop off the chiefs of the camps of their level (Лагерь"
      " ДСР 93/91 12-14, Лагерь Миротворцев 98/99 15-16), those of 10-11 off nobody: bought",
      (stray, sorted({r["craft"]["level"] for r in ups if r["objs"][1].get("mobs")}),
       sorted({r["craft"]["level"] for r in ups if not r["objs"][1].get("mobs")})),
      ([], [12, 13, 14, 15, 16], [10, 11]))
by_class = {}
for r in ups:
    by_class.setdefault(craft.weapon_of(r["craft"]["gun"]), set()).add(r["craft"]["blueprint"])
check("the masters' blueprint stalls of the markets 50 and 197 (580 Самир, 583 Гафур, 584 Умар,"
      " 585 Фахад): each the blueprints of its class's recipes of Донгола, all of them and no"
      " other, by level",
      ({cls: sorted(set(npcs.stock(s)) ^ by_class[cls]) for cls, s in BLUEPRINT_STALLS.items()},
       {cls: [level_of_bp(t) for t in npcs.stock(s)] == sorted(level_of_bp(t)
                                                               for t in npcs.stock(s))
        for cls, s in BLUEPRINT_STALLS.items()},
       {s: (s in standing(MARKET), s in standing(NEW_MARKET)) for s in BLUEPRINT_STALLS.values()}),
      ({cls: [] for cls in BLUEPRINT_STALLS}, {cls: True for cls in BLUEPRINT_STALLS},
       {s: (True, True) for s in BLUEPRINT_STALLS.values()}))
HALFA_STALLS = (576, 578, 7309, 7310, 7311)
check("  ..a city's blueprints at its own stalls: Донгола's of 10-16, Вади-Хальфа's of 8 at"
      " most, so neither town's stall sells the other's",
      (sorted({level_of_bp(t) for s in BLUEPRINT_STALLS.values() for t in npcs.stock(s)}),
       max(level_of_bp(t) for s in HALFA_STALLS for t in npcs.stock(s))),
      ([10, 11, 12, 13, 14, 15, 16], 8))
sys.path.insert(0, os.path.join(ROOT, "data"))
source = os.environ.get("LAVA_ORIG_TEXTS") or "/mnt/c/Users/gmkrt/Downloads/texts.xml"
if os.path.isfile(source):
    import build_weaponcraft  # noqa: E402
    printed = build_weaponcraft.stock(CRAFT_DOC)
    check("  ..as build_weaponcraft --stock prints them", {s: printed[s] == npcs.stock(s) for s in
                                                          list(BLUEPRINT_STALLS.values())
                                                          + [ONE_LEG]},
          {s: True for s in list(BLUEPRINT_STALLS.values()) + [ONE_LEG]})
asked = {}
for r in ups:
    asked.setdefault(r["craft"]["blueprint"], set()).add(r["craft"]["line"])
check("  ..the gold line's own blueprints (asked only by the (G) guns' rows) for gold alone, a"
      " gold thing; every blueprint the afro line asks has its afro price",
      ([t for t, ls in asked.items() if ls == {"G"} and not (gold_only(t) and combat.gold_item(t))],
       [t for t, ls in asked.items() if "A" in ls and not price(t)[0]]), ([], []))
gun_stalls = {x for s in STALLS.values() for x in s if items.root_of(x) == items.FIRE_ARM}
city_guns = {x for _n, _lo, _hi, places in shop_bands.CITIES for p in places for t in stood(p)
             for x in items.stock_for(t, p) if items.root_of(x) == items.FIRE_ARM}
check("  ..and every gun of a recipe on sale, the ordinary and the (G): of 12-16 in the town,"
      " of 10-11 in Абри (its band 8-12)",
      (sorted({r["craft"]["gun"] for r in ups if r["craft"]["level"] >= LO} - gun_stalls),
       sorted({r["craft"]["gun"] for r in ups} - city_guns)), ([], []))
sal, ass, dec, kni = fam("salvage"), fam("assembly"), fam("decode"), fam("knife")
dec.sort(key=lambda r: r["craft"]["level"])
check("the gunsmiths of «Горные тропы» (625): salvage and assembly at the gunsmith of the class,"
      " every part an assembly asks one a salvage row draws",
      (sorted({(r["give"][0], r["craft"]["weapon"]) for r in sal}),
       sorted({(r["give"][0], craft.weapon_of(r["rew_obj"][0])) for r in ass}),
       sorted({o["obj"] for r in ass for o in r["objs"]}
              - {o["obj"] for r in CRAFT_DOC["quests"] if r["craft"]["family"] == "salvage"
                 for o in r["rew_random"]}),
       sorted(GUNSMITHS.values()) == sorted(t for t in standing(625))),
      (sorted((s, c) for c, s in GUNSMITHS.items()), sorted((s, c) for c, s in GUNSMITHS.items()),
       [], True))
check("the decoder Техногик (651, the black market): «Чертежи N-го уровня» for 9-16, including"
      " 9-11 supplied by scheduled Abri bosses, a"
      " fee, a blueprint of the level drawn",
      ([(r["give"], r["craft"]["level"], r["cost_afro"] > 0,
         all(level_of_bp(o["obj"]) == r["craft"]["level"] for o in r["rew_random"]),
         (bool(r["objs"][0].get("mobs")) or r["craft"]["level"] in (9, 10, 11))) for r in dec], DECODER in standing(BLACK)),
      ([([DECODER], n, True, True, True) for n in range(9, 17)], True))


def decode_margin(r):
    """What a decode leaves its player, the drawn blueprint sold back at once
    (the draw's mean sale less the fee), and a tenth of what the draw is worth
    (the mean price): data/build_weaponcraft.py DECODE_FEE."""
    worth = sum(items.params_of(o["obj"])["cost"] for o in r["rew_random"]) / len(r["rew_random"])
    sale = sum(sold_for(o["obj"]) for o in r["rew_random"]) / len(r["rew_random"])
    return sale - r["cost_afro"], worth / 10.0


check("  ..and no farm: a decoded blueprint sold back nets at most a tenth of its price, at 13-16"
      " too, where the articles price the blueprints over craft.LADDER (40 000 / 50 000 / 69 000 /"
      " 80 000): the fee is 60 % of the draw's price -- 18 000, 24 000, 30 000, 41 400, 48 000",
      ([r["craft"]["level"] for r in dec if decode_margin(r)[0] > decode_margin(r)[1]],
       [r["cost_afro"] for r in dec]),
      ([], [9000, 12000, 15000, 18000, 24000, 30000, 41400, 48000]))
check("«Точильный камень Донголы» (2281, the black market) sharpens Боевой нож (G) (14у) and"
      " Такоуба (G) (16у) three ways each, in the original's words",
      (sorted((r["craft"]["gun"], r["craft"]["blueprint"], r["rew_obj"][0]) for r in kni),
       [quests.get(r["type"]).texts[quests.NAME] for r in kni], WHETSTONE in standing(BLACK),
       {r["give"][0] for r in kni}),
      ([(6261, 6626, 6262), (6261, 6627, 6263), (6261, 6628, 6264), (6266, 6629, 6267),
        (6266, 6630, 6268), (6266, 6631, 6269)],
       ["Заточка Боевого ножа", "Эргономика Боевого ножа", "Заточка и Эргономика Боевого ножа",
        "Заточка Такоубы", "Эргономика Такоубы", "Заточка и Эргономика Такоубы"], True,
       {WHETSTONE}))
check("  ..its blueprints and knives (G) on Одноногий's stall beside it, the blueprints for gold"
      " alone", (sorted({r["craft"]["blueprint"] for r in kni} - set(STALLS[(BLACK, ONE_LEG)])),
                 sorted({r["craft"]["gun"] for r in kni} - set(STALLS[(BLACK, ONE_LEG)])),
                 [gold_only(t) for t in KNIFE_PRINTS]), ([], [], [True] * 6))

# --- 4. the plant ---------------------------------------------------------------------------
print()
print("the plant")
DN_TIERS = {1031: (1318, 15), 1224: (1357, 10), 1033: (1310, 15), 1226: (1347, 12),
            1032: (1314, 10), 1225: (1352, 7)}
DN_ORE = {"copper": 3646, "plumbum": 3638, "nitre": 3642}
ROCK_ORE = {1318: 3646, 1357: 3646, 1310: 3638, 1347: 3638, 1314: 3642, 1352: 3642}
SORTERS = {"plumbum": (1361, 665), "nitre": (1365, 664), "copper": (1369, 663)}
LINES = {"plumbum": 1373, "nitre": 1377, "copper": 1381}
CENTRE, FACTORY, ASSEMBLER = 212, 211, 1385
SORTED = {"plumbum": 3674, "nitre": 3678, "copper": 3682}
SACK = {"plumbum": 3650, "nitre": 3654, "copper": 3658}
NATO, PAB = 6097, 6100
GEN = list(range(13200, 13232))
check("each of Донгола's six mine tiers stands the rocks its file puts there"
      " (production.ORE_ROCKS) and its two guards, not the electrical panel",
      {i: (standing(i)[rock], standing(i)[1716], standing(i)[2022])
       for i, (rock, _n) in DN_TIERS.items()},
      {i: (n, 2, 0) for i, (_r, n) in DN_TIERS.items()})
check("  ..an immobile, harmless object each, leaving one piece of Донгола's ore of its kind,"
      " the (Дн) copy", ({(mobs.stats(r).role, mobs.stats(r).moves, mobs.stats(r).can_attack)
                         for r in ROCK_ORE},
                        {r: production.yield_of(r) for r in sorted(ROCK_ORE)},
                        [shown(o) for o in (3638, 3642, 3646)]),
      ({("object", False, False)}, {r: [(o, 1)] for r, o in sorted(ROCK_ORE.items())},
       ["(Дн) Свинцовая руда", "(Дн) Селитра сырьевая", "(Дн) Медная руда"]))
with open(os.path.join(ROOT, "data", "questgen_production.json"), encoding="utf-8") as _fh:
    GEN_DOC = json.load(_fh)
rows = {r["type"]: r for r in GEN_DOC["quests"] if 13200 <= r["type"] < 13300}
check("Донгола's 32 rows, 13200-13231, of the CrBQ family, loaded",
      (sorted(rows), [t for t in rows if quests.get(t) is None],
       [t for t, r in rows.items() if "for ДН from the original's CrBQ№" not in r["why"]]),
      (GEN, [], []))
where = {}
for o, (term, room_) in SORTERS.items():
    where.update({t: (term, room_) for t, r in rows.items() if r["give"] == [term]})
    where.update({t: (LINES[o], CENTRE) for t, r in rows.items() if r["give"] == [LINES[o]]})
where.update({t: (ASSEMBLER, FACTORY) for t, r in rows.items() if r["give"] == [ASSEMBLER]})
check("  ..each given and taken by the terminal or line that stands where it works: the"
      " control rooms 665/664/663, the processing centre 212, the factory 211",
      [t for t in rows if t not in where or rows[t]["take"] != rows[t]["give"]
       or where[t][0] not in standing(where[t][1])], [])
check("  ..in the band of the mines' gates, 12-15 («Вход разрешен персонажам 12-15 ур.»: a"
      " character of the 16th enters no mine of Донгола), services",
      sorted({(r["level"], r["max_level"], r["service"]) for r in rows.values()}),
      [(12, 15, True)])
asks = {t: [(o["obj"], o["num"]) for o in r["objs"]] for t, r in rows.items()}
makes = {t: (r["rew_obj"][0], r["num_rew_obj"][0]) for t, r in rows.items()}
check("sorting: Донгола's ore into Донгола's sorted ore, the lines: sorted ore into its sacks,"
      " the factory: the three sacks into 5.56x45 NATO and ПАБ-9 КС, not their (P) twins",
      (sorted({(asks[t][0][0], makes[t][0]) for t in rows if rows[t]["give"][0] in
               (1361, 1365, 1369, 1373, 1377, 1381)}),
       sorted({makes[t][0] for t in rows if rows[t]["give"] == [ASSEMBLER]}),
       sorted({o for t in rows if rows[t]["give"] == [ASSEMBLER] for o, _n in asks[t]}),
       [items.premium(t) for t in (NATO, PAB)], [shown(t) for t in (NATO, PAB)]),
      (sorted([(3638, 3674), (3642, 3678), (3646, 3682), (3674, 3650), (3678, 3654),
               (3682, 3658)]), [NATO, PAB], [3650, 3654, 3658], [False, False],
       ["5.56х45мм НАТО $КС", "ПАБ–9 $КС"]))
check("  ..each first sorting run one first line of the centre, as in Вади-Хальфа and Абри",
      [makes[t][1] for t in (13200, 13204, 13208)] == [asks[t][0][1] for t in (13212, 13216,
                                                                                13220)], True)
check("  ..the rounds it makes are guns' of the town's band on its stalls",
      sorted({t for t in (NATO, PAB) if any(t in items.params_of(g)["comp_array"]
                                            for g in gun_stalls)}), [NATO, PAB])
plant_in = {o for t in rows for o, _n in asks[t]}
for_sale = {x for tr in set(items.stock_table()) | set(npcs.STOCK) for x in items.stock_for(tr)}
check("no way from afro to more afro: nothing a row asks is on any stall of the game, the sorted"
      " ore and the sacks are worth nothing at one, the ore 0.7 afro a piece, a round 0.7 --"
      " less than the 1 afro a round the stalls sell it for",
      (sorted(plant_in & for_sale), sorted({sold_for(o, 100) for o in plant_in}),
       sold_for(DN_ORE["plumbum"], 10), sold_for(NATO, 600), sold_for(PAB, 600),
       price(NATO)[0] // items.params_of(NATO)["sell_num"]),
      ([], [0, 70], 7, 420, 420, 1))
gold_rows = {t: r["cost_gold"] for t, r in rows.items() if r.get("cost_gold")}
extra = {}
for t, fee in gold_rows.items():
    plain = [u for u in rows if rows[u]["give"] == rows[t]["give"] and u != t
             and asks[u] == asks[t] and not rows[u].get("cost_gold")]
    more = makes[t][1] - makes[plain[0]][1]
    extra[t] = (fee * progression.GOLD_TO_AFRO_RATE // progression.GOLD_OUNCE,
                sold_for(makes[t][0], more))
check("no way from gold to afro: a gold line's quarter more is worth less at a stall than its"
      " fee at the one rate (%s)" % ", ".join("%d: %d afro for %d" % (t, v[0], v[1])
                                             for t, v in sorted(extra.items())),
      (len(extra), [t for t, (fee, worth) in extra.items() if worth >= fee]), (8, []))

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("dongolatrader", "secret")
_store.close()
CRED = accounts.credential("dongolatrader", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

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


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def purse(sess):
    return sess.char.afro, sess.char.gold


def goto(sess, loc_id):
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % loc_id)
    run(sess, "lenter;accept=1;")
    return {npc.type_id: eid for eid, npc in sess.room.npcs.items()}


def as_list(v):
    return list(v) if isinstance(v, list) else ([] if v in (None, "") else [v])


def bag(sess):
    return sorted(r["type_id"] for r in server.STORE.items_of(sess.char_id))


def window(sess, npc):
    got = [p for n, p in run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc) if n == "userInfo_Trader"]
    return as_list(got[0].get("type_list")) if got else []


def buy(sess, stall, t, code, n=1):
    """One purchase of t off the open stall, n of it (rounds: n rounds):
    (acks, what came, afro, gold spent)."""
    before, had = purse(sess), bag(sess)
    got = run(sess, "ss_upd;s_status=%d;obj=x%x;param=%d;" % (code, stall.index(t), n))
    now = bag(sess)
    came = [x for x in set(now) if now.count(x) > had.count(x)]
    return acks(got), came, before[0] - purse(sess)[0], before[1] - purse(sess)[1]


def sell(sess, type_id):
    row = [r for r in server.STORE.items_of(sess.char_id) if r["type_id"] == type_id][0]
    before = purse(sess)
    got = run(sess, "ss_upd;s_status=2;obj=x%s;param=1;" % inventory.oid_of(row))
    return acks(got), type_id in bag(sess), purse(sess)[0] - before[0], purse(sess)[1] - before[1]


def open_stall(sess, place, trader):
    npc = goto(sess, place)[trader]
    stall = window(sess, npc)
    opened = acks(run(sess, "ss_create;s_type=1;target=%d;" % npc))
    return stall, opened


def close_stall(sess):
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")


async def main():
    sess = server.Session(Writer(), "dongolatrader")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Dongolatrader@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 500000 50000@;group=0;")
    BUY, GOLD = inventory.UPD_BUY, inventory.UPD_BUY_GOLD
    REFUSED = [inventory.RES_REFUSED]

    stall, opened = open_stall(sess, STATION, NUR)
    check("Нур-ад-Дин (Донгола's station): his window the ticket to Абри, 110 afro, and since"
          " 2026-10-14 Абу-Хамед's two",
          (stall, opened, buy(sess, stall, TICKET_FROM_DONGOLA, BUY)),
          ([TICKET_FROM_DONGOLA, 1567, 1639], [0], ([0], [TICKET_FROM_DONGOLA], 110, 0)))
    check("  ..a ticket sold back for 0.7 of it: 77 afro", sell(sess, TICKET_FROM_DONGOLA),
          ([0], False, 77, 0))
    close_stall(sess)

    stall, opened = open_stall(sess, ABRI_PORT, LUIGI)
    check("Луиджи (Абри's port market): the ticket to Донгола for 100 afro, back for 110",
          (stall, opened, buy(sess, stall, TICKET_TO_DONGOLA, BUY),
           buy(sess, stall, TICKET_FROM_DONGOLA, BUY)),
          ([TICKET_TO_HALFA, TICKET_TO_DONGOLA, TICKET_FROM_DONGOLA], [0],
           ([0], [TICKET_TO_DONGOLA], 100, 0), ([0], [TICKET_FROM_DONGOLA], 110, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, QUARTER, TARIF)
    check("Тариф (the living quarter 79): the envelope for 30 000 afro, not bought back",
          (stall, opened, buy(sess, stall, ENVELOPE, BUY), sell(sess, ENVELOPE)[1:]),
          ([ENVELOPE], [0], ([0], [ENVELOPE], 30000, 0), (True, 0, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, BLACK, DARI)
    piece_a = [t for t in stall if t in LOVELACE and not gold_only(t)][0]
    piece_g = [t for t in stall if t in LOVELACE and gold_only(t)][0]
    check("Дари (the black market): his window the town's sets; a Чёрный Ловелас piece for afro,"
          " its (G) for gold, at their prices",
          (stall == items.stock_for(DARI, BLACK), opened, buy(sess, stall, piece_a, BUY),
           buy(sess, stall, piece_g, GOLD)),
          (True, [0], ([0], [piece_a], price(piece_a)[0], 0),
           ([0], [piece_g], 0, price(piece_g)[1])))
    close_stall(sess)

    stall, opened = open_stall(sess, BLACK, GALIA)
    check("Галия: «Подсумки автоматчика» for afro, the (G) one for gold",
          (stall == items.stock_for(GALIA, BLACK), opened, buy(sess, stall, 3577, BUY),
           buy(sess, stall, 3599, GOLD)),
          (True, [0], ([0], [3577], price(3577)[0], 0), ([0], [3599], 0, price(3599)[1])))
    close_stall(sess)

    stall, opened = open_stall(sess, BLACK, ONE_LEG)
    check("Одноногий: «Заточка Боевого ножа (14у)» for its 2.56 ounces in gold; for afro refused;"
          " not bought back",
          (stall == items.stock_for(ONE_LEG, BLACK), opened, buy(sess, stall, 6626, GOLD),
           buy(sess, stall, 6626, BUY), sell(sess, 6626)),
          (True, [0], ([0], [6626], 0, 256), (REFUSED, [], 0, 0), (REFUSED, True, 0, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, NEW_MARKET, MORTIMER)
    check("Мортимер (the new market 197): an ingot for afro refused, for gold its ounces",
          (stall, opened, buy(sess, stall, 7620, BUY), buy(sess, stall, 7620, GOLD)),
          (list(INGOTS), [0], (REFUSED, [], 0, 0), ([0], [7620], 0, 100)))
    close_stall(sess)

    stall, opened = open_stall(sess, NEW_MARKET, 584)
    check("Мастер Умар (584, the new market): his window the rifles' blueprints of Донгола",
          (stall, opened), (npcs.stock(584), [0]))
    close_stall(sess)

    stall, opened = open_stall(sess, OASIS, AMMO_OASIS)
    check("the oasis's «Торговец патронами»: 5.56x45 СТ for 160 afro a pack of 20",
          (stall, opened, buy(sess, stall, 6109, BUY, 20)),
          (OASIS_ROUNDS, [0], ([0], [6109], 160, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, PIER, ELIZABETH)
    check("Элизабет Стюарт (the pier 445): her 24 gifts; «Пистолет» for 500 afro, «Zippo» for"
          " 1 ounce, the gold one not bought back",
          (stall, opened, buy(sess, stall, 4329, BUY), buy(sess, stall, 4338, GOLD),
           sell(sess, 4338)),
          (list(GIFTS), [0], ([0], [4329], 500, 0), ([0], [4338], 0, 100),
           (REFUSED, True, 0, 0)))
    close_stall(sess)


asyncio.run(main())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("dongola trade OK")
