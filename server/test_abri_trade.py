"""Абри's trade (the Абри restoration, 2026-10-12, package TRADE): what each
of its sellers sells, at what price, the knife craft of its whetstone and its
plant -- the owner's «Добавь каждому продавцу нужные предметы».

In process:
  1. the things: the bus tickets, the lottery tickets, Хаксли's coupons, the
     junkyard's tools, Одноухий's gypsum, wire and bandages and Фрея Каплан's
     24 gifts, each named and described by the original (data/
     build_orig_items.py rule 7k), at its article's price -- in afro, or in
     gold alone for the gold ones, which are gold things no stall buys back;
     the gifts the articles' trinkets, 1-1 damage and 30 000 wear, never the
     designed frame's weapons;
  2. the stalls: every trader standing in a place of Абри has its stall
     pinned here (data/npcs.json, the town's band of data/shop_bands.json, or
     the wiki's list kept as it was), the lists the wiki tied to the wrong
     trader of the port market moved to their own (Алима's pouches, Торси's
     battle medicine, Мухсим's food), Хассир sells both tickets in
     Вади-Хальфа; nothing on them out of Абри's band 8-12, premium, or under
     objects.xml's own words, each gun's rounds on sale in the town;
  3. the knife craft: «Точильный камень Абри» (2280) sharpens Нож кастет
     (10у) and Штык нож (12у) three ways each, its blueprints on sale at
     Одноухий beside it;
  4. the plant: the rocks of Абри's six mine tiers and nothing else of the
     object role, each leaving the (Аб) ore, the CrBQ rows 13100-13131 of
     Абри (the control rooms' sorting, the base 207's lines, the factory
     206's 9 mm NATO and 5.7x28), in the band 8-12, and no way through them
     from afro to more afro or from gold to afro.
Then one session, in process, on the wire: Хассир's two tickets in
Вади-Хальфа, Луиджи's in Абри, Одноухий's blueprint for gold and gypsum for
afro, a gold ingot refused for afro at Мортимер (Трущобы), a coupon at
Хаксли, a tool at МакКэндлесс, a gift at Фрея; the gold things not bought
back.

    LAVA_RES=.../res python3 server/test_abri_trade.py
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

DB = os.path.join(tempfile.mkdtemp(), "abri_trade.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START", "LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import production  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "торговля Абри: лавки, цены, точильный камень и завод"

OFF = items.STRING_ID_OFFSET
cat = items.catalogue()
MT = world.mob_types()
items.preload()
with open(os.path.join(ROOT, "data", "orig_items.json"), encoding="utf-8") as _fh:
    ORIG = json.load(_fh)["items"]

# --- the places, the people, the things --------------------------------------------------
PORT, QUARTER, SLUMS, OASIS, CLOTHES, FIELDS, DUMP, STATION = 187, 188, 255, 76, 378, 261, 289, 37
ABRI_PLACES = (PORT, QUARTER, SLUMS, OASIS, CLOTHES, FIELDS, DUMP)
HASSIR, LUIGI, ONE_EAR, ALIMA, GALI, TORSI, MUKHSIM, SHOTGUNS = 105, 1179, 1164, 1165, 1166, \
    1167, 1168, 1162
PILOT, LOTTERY, GOLD_LOTTERY, KHAN_SELL, MORTIMER = 4672, 1172, 1171, 2391, 1188
FREYA, AMMO_OASIS, JUT, HUXLEY, MCCANDLESS = 1962, 1228, 207, 5766, 2390
WHETSTONE = 2280
TICKET_TO_ABRI, TICKET_TO_HALFA = 6544, 6545
KEYS, GOLD_KEYS = (2646, 2647), (2649, 2650)
COUPONS = (6294, 6295, 6296)
TOOLS = (7025, 7026, 7027, 7028, 7029, 7036, 7037, 7038, 7039, 7040, 7041, 7042)
CHAIN = (5740, 5741, 5742)                      # гипс, проволока, бинты (Марис Дамбис)
GIFTS = tuple(range(4329, 4353))                # gift_kid_1..10, gift_girl_1..10, gift_0..3
KNIFE_PRINTS = tuple(range(6620, 6626))         # Заточка / Эргономика / both, 10у and 12у
INGOTS = (7620, 4796, 4797)
# 5162/5163 (the Дредноут's and Паладин's sets, 17-19) are held out of the
# clothing market by the package WORLD (data/schedule.json held_out): until it
# is merged they stand there with empty stalls, no seller of Абри's. And the
# package WORLD stands the lottery men in the port market all year
# (world.SEASON_KEPT) and Мортимер there too (data/placements.json): until it
# is merged they stand nowhere there, their lists decided all the same.
HELD_OUT = {CLOTHES: {5162, 5163}}
WORLD_PUTS = {PORT: {LOTTERY, GOLD_LOTTERY, MORTIMER}}

# Each trader of Абри's places and what decides its stall there, 2026-10-12
# (DESIGN.md 6.2): "band" the town's band of its kinds before its own list
# (data/shop_bands.json SELLERS), "own" data/npcs.json's list, "wiki" the
# wiki's list as it was (items.stock_table).
DECIDED = {
    PORT: {1159: "band", 1161: "band", 1163: "band", SHOTGUNS: "band", ONE_EAR: "band",
           ALIMA: "band", GALI: "band", TORSI: "own", MUKHSIM: "band", LUIGI: "own",
           PILOT: "own", LOTTERY: "own", GOLD_LOTTERY: "own", KHAN_SELL: "band",
           MORTIMER: "own"},
    QUARTER: {1013: "wiki", 1196: "wiki", 2016: "wiki"},
    SLUMS: {MORTIMER: "own", FREYA: "own"},
    OASIS: {1225: "band", AMMO_OASIS: "own", JUT: "own"},
    CLOTHES: {5160: "band", 5161: "band", 5181: "own"},
    FIELDS: {HUXLEY: "own"},
    DUMP: {MCCANDLESS: "own"},
}
# The lists of data/npcs.json this restoration wrote (or kept: Мортимер's).
OWN = {
    SHOTGUNS: [6096, 6108, 6120],
    ONE_EAR: list(KNIFE_PRINTS) + list(CHAIN),
    ALIMA: [3577, 3581, 5613, 3578, 3579],
    TORSI: [6056, 6057, 6058, 6062, 6063, 6064, 6074, 6075, 6076],
    MUKHSIM: [6051, 6907, 6906, 6905, 6046, 6050, 6898, 6901, 6044, 6052, 6900, 6045, 6899],
    LUIGI: [TICKET_TO_HALFA],
    PILOT: [],
    LOTTERY: list(KEYS),
    GOLD_LOTTERY: list(GOLD_KEYS),
    HASSIR: [TICKET_TO_ABRI, TICKET_TO_HALFA],
    FREYA: list(GIFTS),
    AMMO_OASIS: [6104, 6105, 6106, 6108, 6107, 6110, 6111, 6115, 6116, 6117, 6118, 6120, 6119,
                 6122, 6123, 6127, 6113, 6125],
    JUT: [6904, 6905, 6906, 6907, 6073, 6074, 6075, 6076],
    HUXLEY: list(COUPONS),
    MCCANDLESS: list(TOOLS),
    MORTIMER: list(INGOTS),
}
# The plant.
ABRI_TIERS = {1028: (1317, 15), 1221: (1356, 10), 1030: (1309, 15), 1223: (1346, 15),
              1029: (1313, 10), 1222: (1351, 10)}
ABRI_ORE = {"copper": 3645, "plumbum": 3637, "nitre": 3641}
ROCK_ORE = {1317: 3645, 1356: 3645, 1309: 3637, 1346: 3637, 1313: 3641, 1351: 3641}
SORTERS = {"plumbum": (1360, 662), "nitre": (1364, 661), "copper": (1368, 660)}
LINES = {"plumbum": 1372, "nitre": 1376, "copper": 1380}
BASE, FACTORY, ASSEMBLER = 207, 206, 1384
SORTED = {"plumbum": 3673, "nitre": 3677, "copper": 3681}
SACK = {"plumbum": 3649, "nitre": 3653, "copper": 3657}
NINE_MM, SS190 = 6092, 6101
GEN = list(range(13100, 13132))


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
    nothing for a thing with no afro price or a quest's (inventory.SELL_GOLD_ONLY
    off)."""
    si = items.params_of(t)
    if not si.get("cost") or si.get("quest"):
        return 0
    return max(1, int(math.floor(si["cost"] / float(si.get("sell_num", 1)) * n
                                 * inventory.SMOD * si.get("sell_mod", 1))))


def gold_only(t):
    p = items.params_of(t)
    return p["g_cost"] > 0 and not p["cost"]


# --- 1. the things ----------------------------------------------------------------------
print("the things")
check("the bus tickets: «Билет в Абри из Вади Хальфы» 100 afro, «Билет в Вади Хальфу из"
      " Абри» 150, their articles' prices (the designed 10 afro before)",
      [(shown(t), price(t)) for t in (TICKET_TO_ABRI, TICKET_TO_HALFA)],
      [("Билет в Абри из Вади Хальфы", (100, 0)), ("Билет в Вади Хальфу из Абри", (150, 0))])
check("the lottery tickets of Абри's lottery men: [10] 1000 and [12] 1700 afro, the gold [G][10]"
      " 2 G and [G][12] 2.5 G in gold alone (as Вади-Хальфа's gold one, 1333)",
      [(cat[t][1], price(t)) for t in KEYS + GOLD_KEYS],
      [("DnLoteryKey_9_10", (1000, 0)), ("DnLoteryKey_11_12", (1700, 0)),
       ("DnLoteryKey_g_9_10", (0, 200)), ("DnLoteryKey_g_11_12", (0, 250))])
check("  ..named by the original's tickets' run (6921, 6922, 6924, 6925), the [8] ticket's"
      " words (6919) for each", [orig(t) for t in KEYS + GOLD_KEYS],
      [(6921, 6919), (6922, 6919), (6924, 6919), (6925, 6919)])
check("Хаксли's coupons «Купон на 20 / 300 / 5000 патронов»: 0.1, 1 and 10 G, gold alone",
      [(cat[t][1], orig(t), price(t)) for t in COUPONS],
      [("kupon_ammo_20", (6684, 6685), (0, 10)), ("kupon_ammo_300", (6686, 6687), (0, 100)),
       ("kupon_ammo_5000", (6689, 6690), (0, 1000))])
# The wiki's discount: «Купон на 5000 патронов» for 10 G, where 5000 gold rounds
# bought at a stall cost a hundredth each (items.GOLD_AMMO_ROUND), 50 G.
check("  ..a coupon the wiki's discount on the gold rounds: 5000 of them 50 G at a stall, 10 G"
      " by the coupon", (5000 * items.GOLD_AMMO_ROUND, price(6296)[1]), (5000, 1000))
check("the junkyard's twelve tools, 100 afro each («Все по 100 афро»), by the original's words"
      " (8238-8260; the geologist's hammer «Молоток геолога» 1610 with its words 8240)",
      [(shown(t), price(t)) for t in TOOLS],
      [(w, (100, 0)) for w in ("Паяльная лампа", "Молоток геолога", "Жестяная банка", "Бутыль",
                               "Воронка", "Перчатки", "Пассатижы", "Отвертка",
                               "Нож для грязной работы", "Клизма", "Респиратор",
                               "Пластиковый пакет")])
check("  ..the hammer's own words, its article's", (orig(7026), names.ALL.get(
    items.DESC_ID_OFFSET + 7026, "").startswith("Незаменимая вещь")), ((1610, 8240), True))
check("Одноухий's gypsum, wire and bandages for Марис Дамбис's chain: the original's names"
      " (49079-49084), 50 afro each (DESIGNED)",
      [(shown(t), price(t)) for t in CHAIN],
      [("Гипс", (50, 0)), ("Проволока с искривлением", (50, 0)), ("Бинты для гипса", (50, 0))])
GIFT_WORDS = ["Пистолет", "Рогатка", "Амулет", "Машинка", "Печатка", "GPS-навигатор",
              "Набор солдатиков", "Гантеля", "Гитара", "Zippo", "Цветок", "Кукла", "Тедди",
              "Букет", "Сердечко", "Амулет", "Медальон", "Зайчонок", "Духи", "Шоколадка",
              "Черная метка", "Открытка", "Открытка", "Открытка"]
GIFT_PRICES = [(500, 0), (0, 30), (1000, 0), (1500, 0), (2000, 0), (0, 50), (2500, 0),
               (3000, 0), (3000, 0), (0, 100), (500, 0), (1000, 0), (0, 100), (1500, 0),
               (0, 30), (2500, 0), (2500, 0), (0, 50), (3000, 0), (4000, 0), (0, 100),
               (1000, 0), (1000, 0), (1000, 0)]
check("Фрея Каплан's 24 gifts, her article's order: gift_kid_1..10, gift_girl_1..10,"
      " gift_0..3, named by the original's run 1265-1308",
      [(cat[t][1], shown(t)) for t in GIFTS],
      [("gift_kid_%d" % k, w) for k, w in zip(range(1, 11), GIFT_WORDS[:10])]
      + [("gift_girl_%d" % k, w) for k, w in zip(range(1, 11), GIFT_WORDS[10:20])]
      + [("gift_%d" % k, w) for k, w in zip(range(4), GIFT_WORDS[20:])])
check("  ..each at its article's price, afro or gold alone", [price(t) for t in GIFTS],
      GIFT_PRICES)
check("  ..each the articles' trinket: 1-1 damage, 30 000 wear, 100 g, no exchange, 5 AP a"
      " strike (data/coldarm_manual.json), never the designed frame's weapon",
      sorted({(p["h_damage_min"], p["h_damage_max"], p["st_damage_min"], p["st_damage_max"],
               p["max_break_abs"], p["weight"], p["exchang"], p["strike_cost"])
              for p in map(items.params_of, GIFTS)}), [(1, 1, 1, 1, 30000, 100, 0, 5)])
check("  ..the three postcards one «Открытка» with three verses, the shell amulet and the"
      " perfume named by the rows of their words (1269, 766)",
      ([orig(t) for t in (4350, 4351, 4352)], orig(4344), orig(4347)),
      ([(1305, 1306), (1305, 1307), (1305, 1308)], (1269, 1295), (766, 1300)))
EVERY = (TICKET_TO_ABRI, TICKET_TO_HALFA) + KEYS + GOLD_KEYS + COUPONS + TOOLS + CHAIN + GIFTS
check("every one of them named and described by the original (names.ALL), not by"
      " objects.xml's words; no premium, no quest thing, a type the client draws",
      [t for t in EVERY if shown(t) in (None, cat[t][1]) or not names.known(
          items.params_of(t)["desc"]) or items.premium(t) or items.params_of(t)["quest"]], [])
GOLD_THINGS = [t for t in EVERY if gold_only(t)]
check("the gold ones (the gold tickets, the coupons, seven gifts) are gold things: never off"
      " a body, and no stall buys them back (cost 0, inventory.SELL_GOLD_ONLY off)",
      (len(GOLD_THINGS), sorted({(combat.gold_item(t), sold_for(t)) for t in GOLD_THINGS}),
       inventory.SELL_GOLD_ONLY), (12, [(True, 0)], False))
check("  ..and every afro one sells back for 0.7 of its price at most",
      [t for t in EVERY if not gold_only(t) and sold_for(t) > 0.7 * price(t)[0]], [])

# --- 2. the stalls ------------------------------------------------------------------------
print()
print("the stalls")
AT = {p: [t for t in stood(p) if t not in HELD_OUT.get(p, ())] for p in ABRI_PLACES}
check("every trader standing in a place of Абри has its stall decided (data/npcs.json, the"
      " town's band, or the wiki's list kept), and the table names nobody who stands nowhere",
      ({p: sorted(t for t in AT[p] if t not in DECIDED[p]) for p in ABRI_PLACES},
       {p: sorted(t for t in DECIDED[p] if t not in AT[p] and t not in WORLD_PUTS.get(p, ()))
        for p in ABRI_PLACES}),
      ({p: [] for p in ABRI_PLACES}, {p: [] for p in ABRI_PLACES}))
how = {}
for p, decided in DECIDED.items():
    for t, kind in decided.items():
        if kind == "band":
            ok = t in shop_bands.SELLERS
        elif kind == "own":
            ok = npcs.stock(t) is not None
        else:
            ok = npcs.stock(t) is None and t not in shop_bands.SELLERS \
                and items.stock_for(t, p) == items.stock_table().get(t)
        if not ok:
            how[(p, t)] = kind
check("  ..each the way the table says: a seller of the band, a list of the owner's file, or"
      " the wiki's list untouched (Гофус, Бернар, the doctor's junior helper)", how, {})
check("the lists of data/npcs.json, trader by trader (DESIGN.md 6.2)",
      {t: npcs.stock(t) for t in OWN}, OWN)
check("  ..the port market's lists where the wiki's links had shifted them: Алима's pouches"
      " off the driver Луиджи, Торси's battle medicine off the pilot, Мухсим's food in place of"
      " Хан Сэлл's contraband, the shotgun man's 12-bore without the knife blueprints",
      ([t for t in items.stock_table().get(LUIGI, []) if t in OWN[ALIMA]] == OWN[ALIMA],
       sorted(items.stock_table().get(PILOT, [])) == sorted(OWN[TORSI]),
       sorted(items.stock_table().get(ALIMA, [])) == sorted(OWN[MUKHSIM]),
       sorted(items.stock_table().get(MUKHSIM, [])) == sorted(items.stock_table().get(KHAN_SELL)),
       [t for t in items.stock_table().get(SHOTGUNS, []) if t in (6622, 6625)]),
      (True, True, True, True, [6622, 6625]))
check("Хассир sells both tickets at Вади-Хальфа's station: the way home is bought before the"
      " ride", (HASSIR in stood(STATION), items.stock_for(HASSIR, STATION)),
      (True, [TICKET_TO_ABRI, TICKET_TO_HALFA]))

STALLS = {(p, t): items.stock_for(t, p) for p in ABRI_PLACES for t in AT[p]}
LO, HI = 8, 12
check("Абри is the band 8-12 of data/shop_bands.json, its places these",
      [(c[0], c[1], c[2]) for c in shop_bands.CITIES if c[0] == "Абри"], [("Абри", LO, HI)])


def band_thing(t):
    return shop_bands.band_ware(t)


check("no gun, knife or set piece out of 8-12 on a seller's stall of Абри; every one of a"
      " seller's band both ways, the ordinary for afro and the (G) for gold (Фрея's gifts,"
      " cold arms of level 0, are no seller's: her own list, test_stall_bands' LEFT_HOLDING)",
      (sorted((p, t, x) for (p, t), s in STALLS.items() for x in s if t in shop_bands.SELLERS
              and band_thing(x) and not LO <= inventory.item_level(x) <= HI),
       sorted((p, t) for (p, t), s in STALLS.items() if t in shop_bands.SELLERS
              and shop_bands.SELLERS[t]
              and not {gold_only(x) for x in s if band_thing(x)} >= {True, False})),
      ([], []))
check("nothing premium on a stall of Абри, nothing a quest lends, each thing priced in one"
      " currency but Мортимер's ingots (items.GOLD_INGOTS: sold for gold, loot worth afro)",
      sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
             if items.premium(x) or quests.lent(x)
             or (bool(price(x)[0]) == bool(price(x)[1]) and x not in items.GOLD_INGOTS)), [])
check("no thing on a stall of Абри shows objects.xml's own words, or a description the"
      " preload lacks", sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
                               if shown(x) in (None, cat[x][1])
                               or (items.params_of(x)["desc"] != ""
                                   and not names.known(items.params_of(x)["desc"]))), [])
ROUNDS = {x for s in STALLS.values() for x in s if items.root_of(x) == items.AMMO}
check("every gun on a stall of Абри has a round it chambers on sale in the town",
      sorted({x for s in STALLS.values() for x in s if items.root_of(x) == items.FIRE_ARM
              and not set(items.params_of(x)["comp_array"]) & ROUNDS}), [])
check("  ..the P90's 5.7x28 among them: the oasis's «Торговец патронами» (1228) sells its СТ and"
      " ОТ beside Вади-Хальфа's oasis list", [x for x in STALLS[(OASIS, AMMO_OASIS)]
                                              if x in (6101, 6113, 6125)], [6113, 6125])
check("the stalls' sizes: none longer than 64, the knife trader's band and his own list",
      (max(len(s) for s in STALLS.values()) <= 64, STALLS[(PORT, ONE_EAR)]),
      (True, [6245, 6246, 6250, 6251, 6255, 6256] + OWN[ONE_EAR]))
check("Алима: the town's sets, then her pouches, each with its (G) right after it",
      STALLS[(PORT, ALIMA)][-10:], [3577, 3599, 3581, 3603, 5613, 5614, 3578, 3600, 3579, 3601])
# The upgraders of Абри's places: the clothes' Рудольф (5105, «Обмен одежды на
# вырост [9-12]») with the set upgrades off everywhere since 2026-10-09, Фрея's
# Альфред and Алиса (2002/2003), the legionnaire's changer (2241) -- empty
# windows; Жозеф де Гобино (7548) in the oasis the [Q] Маузер's twelve, as in
# Вади-Хальфа's.
import craft  # noqa: E402
check("the upgraders of Абри's places: empty windows, Жозеф де Гобино's the [Q] Маузер's twelve",
      {t: len(craft.upgrader_lists(t)["out_types"]) for t in (5105, 2002, 2003, 2241, 7548)},
      {5105: 0, 2002: 0, 2003: 0, 2241: 0, 7548: 12})

# --- 3. the knife craft ---------------------------------------------------------------------
print()
print("the knife craft")
with open(os.path.join(ROOT, "data", "questgen_weaponcraft.json"), encoding="utf-8") as _fh:
    CRAFT_DOC = json.load(_fh)
stone = [r for r in CRAFT_DOC["quests"] if r["give"] == [WHETSTONE]]
check("«Точильный камень Абри» (2280, the port market) sharpens Нож кастет (G) and Штык нож (G)"
      " three ways each, for the band 8-12, repeatable services",
      sorted((r["craft"]["gun"], r["craft"]["blueprint"], r["rew_obj"][0], r["level"],
              r["max_level"], r["repeatable"], r["service"]) for r in stone),
      [(6251, 6620, 6252, 8, 12, 1, True), (6251, 6621, 6253, 8, 12, 1, True),
       (6251, 6622, 6254, 8, 12, 1, True), (6256, 6623, 6257, 8, 12, 1, True),
       (6256, 6624, 6258, 8, 12, 1, True), (6256, 6625, 6259, 8, 12, 1, True)])
check("  ..in the original's words, loaded (quests.get), the whetstone standing in the port"
      " market", ([quests.get(r["type"]).texts[quests.NAME] for r in stone],
                  WHETSTONE in standing(PORT)),
      (["Заточка Нож кастета", "Эргономика Нож кастета", "Заточка и Эргономика Нож кастета",
        "Заточка Штык ножа", "Эргономика Штык ножа", "Заточка и Эргономика Штык ножа"], True))
check("  ..its blueprints and knives (G) on Одноухий's stall beside it, the blueprints for gold"
      " alone", (sorted({r["craft"]["blueprint"] for r in stone} - set(STALLS[(PORT, ONE_EAR)])),
                 sorted({r["craft"]["gun"] for r in stone} - set(STALLS[(PORT, ONE_EAR)])),
                 [gold_only(t) for t in KNIFE_PRINTS]), ([], [], [True] * 6))
check("  ..and no other craft of Абри's: no upgrade, salvage, assembly or decoding row in the"
      " band 8-12 (no upgrader of Абри's in the client)",
      sorted({r["craft"]["family"] for r in CRAFT_DOC["quests"]
              if (r["level"], r["max_level"]) == (LO, HI)}), ["knife"])

# --- 4. the plant ---------------------------------------------------------------------------
print()
print("the plant")
check("each of Абри's six mine tiers stands the rocks its file puts there (production.ORE_ROCKS)"
      " and its two guards, not the electrical panel",
      {i: (standing(i)[rock], standing(i)[1715], standing(i)[2022])
       for i, (rock, _n) in ABRI_TIERS.items()},
      {i: (n, 2, 0) for i, (_r, n) in ABRI_TIERS.items()})
check("  ..an immobile, harmless object each, leaving one piece of Абри's ore of its kind, the"
      " (Аб) copy", ({(mobs.stats(r).role, mobs.stats(r).moves, mobs.stats(r).can_attack)
                      for r in ROCK_ORE},
                     {r: production.yield_of(r) for r in sorted(ROCK_ORE)},
                     [shown(o) for o in (3637, 3641, 3645)]),
      ({("object", False, False)}, {r: [(o, 1)] for r, o in sorted(ROCK_ORE.items())},
       ["(Аб) Свинцовая руда", "(Аб) Селитра сырьевая", "(Аб) Медная руда"]))
GEN_DOC = json.load(open(os.path.join(ROOT, "data", "questgen_production.json"), encoding="utf-8"))
rows = {r["type"]: r for r in GEN_DOC["quests"] if r["type"] >= 13100}
check("Абри's 32 rows, 13100-13131, of the CrBQ family, loaded",
      (sorted(rows), [t for t in rows if quests.get(t) is None],
       [t for t, r in rows.items() if "for АБ from the original's CrBQ№" not in r["why"]]),
      (GEN, [], []))
where = {}
for o, (term, room_) in SORTERS.items():
    where.update({t: (term, room_) for t, r in rows.items() if r["give"] == [term]})
    where.update({t: (LINES[o], BASE) for t, r in rows.items() if r["give"] == [LINES[o]]})
where.update({t: (ASSEMBLER, FACTORY) for t, r in rows.items() if r["give"] == [ASSEMBLER]})
check("  ..each given and taken by the terminal or line that stands where it works: the"
      " control rooms 662/661/660, the base 207, the factory 206",
      ([t for t in rows if t not in where or rows[t]["take"] != rows[t]["give"]
        or where[t][0] not in standing(where[t][1])]), [])
check("  ..in the band of the mines' gates, 8-12, repeatable or once, services",
      sorted({(r["level"], r["max_level"], r["service"]) for r in rows.values()}),
      [(8, 12, True)])
asks = {t: [(o["obj"], o["num"]) for o in r["objs"]] for t, r in rows.items()}
makes = {t: (r["rew_obj"][0], r["num_rew_obj"][0]) for t, r in rows.items()}
check("sorting: Абри's ore into Абри's sorted ore, the lines: sorted ore into its sacks, the"
      " factory: the three sacks into 9 mm NATO and 5.7x28 КС, not their (P) twins",
      (sorted({(asks[t][0][0], makes[t][0]) for t in rows if rows[t]["give"][0] in
               (1360, 1364, 1368, 1372, 1376, 1380)}),
       sorted({makes[t][0] for t in rows if rows[t]["give"] == [ASSEMBLER]}),
       sorted({o for t in rows if rows[t]["give"] == [ASSEMBLER] for o, _n in asks[t]}),
       [items.premium(t) for t in (NINE_MM, SS190)], [shown(t) for t in (NINE_MM, SS190)]),
      (sorted([(3637, 3673), (3641, 3677), (3645, 3681), (3673, 3649), (3677, 3653),
               (3681, 3657)]), [NINE_MM, SS190], [3649, 3653, 3657], [False, False],
       ["9мм НАТО $КС", "5.7x28 $КС"]))
check("  ..each first sorting run one first line of the base, as in Вади-Хальфа",
      [makes[t][1] for t in (13100, 13104, 13108)] == [asks[t][0][1] for t in (13112, 13116,
                                                                                13120)], True)
plant_in = {o for t in rows for o, _n in asks[t]}
for_sale = {x for tr in set(items.stock_table()) | set(npcs.STOCK) for x in items.stock_for(tr)}
check("no way from afro to more afro: nothing a row asks is on any stall of the game, the sorted"
      " ore and the sacks are worth nothing at one, the ore 0.7 afro a piece, a round 0.7 --"
      " less than the 1 afro a round the stalls sell it for",
      (sorted(plant_in & for_sale), sorted({sold_for(o, 100) for o in plant_in}),
       sold_for(ABRI_ORE["plumbum"], 10), sold_for(NINE_MM, 600), sold_for(SS190, 600),
       price(NINE_MM)[0] // items.params_of(NINE_MM)["sell_num"]),
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
      [t for t, (fee, worth) in extra.items() if worth >= fee], [])

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("abritrader", "secret")
_store.close()
CRED = accounts.credential("abritrader", "secret")

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
    sess = server.Session(Writer(), "abritrader")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Abritrader@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 500000 50000@;group=0;")
    BUY, GOLD = inventory.UPD_BUY, inventory.UPD_BUY_GOLD
    REFUSED = [inventory.RES_REFUSED]

    stall, opened = open_stall(sess, STATION, HASSIR)
    check("Хассир (Вади-Хальфа's station): his window the two tickets, the stall opens",
          (stall, opened), ([TICKET_TO_ABRI, TICKET_TO_HALFA], [0]))
    check("  ..«Билет в Абри» for 100 afro, «Билет в Вади Хальфу» for 150, one ack each",
          (buy(sess, stall, TICKET_TO_ABRI, BUY), buy(sess, stall, TICKET_TO_HALFA, BUY)),
          (([0], [TICKET_TO_ABRI], 100, 0), ([0], [TICKET_TO_HALFA], 150, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, PORT, LUIGI)
    check("Луиджи (Абри's port market): his window the ticket home, 150 afro",
          (stall, opened, buy(sess, stall, TICKET_TO_HALFA, BUY)),
          ([TICKET_TO_HALFA], [0], ([0], [TICKET_TO_HALFA], 150, 0)))
    check("  ..a ticket sold back for 0.7 of it: 105 afro", sell(sess, TICKET_TO_HALFA),
          ([0], True, 105, 0))
    close_stall(sess)

    stall, opened = open_stall(sess, PORT, ONE_EAR)
    check("Одноухий: his window the town's knives, the whetstone's blueprints, the chain's three",
          (stall == items.stock_for(ONE_EAR, PORT), opened), (True, [0]))
    check("  ..«Заточка Нож кастета (10у)» for its 1.64 ounces in gold; for afro refused",
          (buy(sess, stall, 6620, GOLD), buy(sess, stall, 6620, BUY)),
          (([0], [6620], 0, 164), (REFUSED, [], 0, 0)))
    check("  ..«Бинты для гипса» for 50 afro", buy(sess, stall, 5742, BUY), ([0], [5742], 50, 0))
    check("  ..the blueprint is not bought back", sell(sess, 6620), (REFUSED, True, 0, 0))
    close_stall(sess)

    stall, opened = open_stall(sess, PORT, TORSI)
    check("Торси: her battle medicine; «В.И.Л.К.А. (G)» for 0.03 ounces",
          (stall, opened, buy(sess, stall, 6075, GOLD)),
          (OWN[TORSI], [0], ([0], [6075], 0, 3)))
    close_stall(sess)

    stall, opened = open_stall(sess, SLUMS, MORTIMER)
    check("Мортимер (Трущобы): an ingot for afro refused, for gold its ounces",
          (stall, opened, buy(sess, stall, 7620, BUY), buy(sess, stall, 7620, GOLD)),
          (list(INGOTS), [0], (REFUSED, [], 0, 0), ([0], [7620], 0, 100)))
    close_stall(sess)

    stall, opened = open_stall(sess, SLUMS, FREYA)
    check("Фрея Каплан: her 24 gifts; «Пистолет» for 500 afro, «Zippo» for 1 ounce",
          (stall, opened, buy(sess, stall, 4329, BUY), buy(sess, stall, 4338, GOLD)),
          (list(GIFTS), [0], ([0], [4329], 500, 0), ([0], [4338], 0, 100)))
    check("  ..the gold one is not bought back", sell(sess, 4338), (REFUSED, True, 0, 0))
    close_stall(sess)

    stall, opened = open_stall(sess, FIELDS, HUXLEY)
    check("Говард Хаксли (Поля Абри): his coupons; «Купон на 300 патронов» for 1 ounce, for afro"
          " refused", (stall, opened, buy(sess, stall, 6295, GOLD), buy(sess, stall, 6295, BUY)),
          (list(COUPONS), [0], ([0], [6295], 0, 100), (REFUSED, [], 0, 0)))
    check("  ..and not bought back", sell(sess, 6295), (REFUSED, True, 0, 0))
    close_stall(sess)

    stall, opened = open_stall(sess, DUMP, MCCANDLESS)
    check("МакКэндлесс (Свалка Автомобилей): his twelve tools; «Молоток геолога» for 100 afro",
          (stall, opened, buy(sess, stall, 7026, BUY)),
          (list(TOOLS), [0], ([0], [7026], 100, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, OASIS, AMMO_OASIS)
    check("the oasis's «Торговец патронами»: 5.7x28 СТ for 160 afro a pack of 20",
          (opened, buy(sess, stall, 6113, BUY, 20)), ([0], ([0], [6113], 160, 0)))
    close_stall(sess)


asyncio.run(main())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("abri trade OK")
