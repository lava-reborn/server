"""Абу-Хамед's trade (the Абу-Хамед restoration, 2026-10-14, package TRADE):
what each of its sellers sells, at what price, Тёмное Эхо[17] for afro and
for gold, its weapon craft -- the masters' recipes, their blueprint stalls,
the gunsmiths, the decoder and the whetstone -- and its plant: the owner's
«сделай потом абу хамед в таком же формате», made as Абри and Донгола were
(«Добавь каждому продавцу нужные предметы»).

In process:
  1. the things: the bus tickets of Нур-ад-Дин and Веласкес, 0.25 G and
     0.10 G in gold alone, each no dearer than the fare of its ride (276,
     277), the lottery tickets [16], [18], [19] and their [G] copies, each
     named by the original at its article's price, the gold ones gold
     things no stall buys back; the sharpened Мачете (G) by their articles;
  2. the stalls: every trader standing in a place of Абу-Хамед has its
     stall decided here (data/npcs.json, the town's band of
     data/shop_bands.json, the wiki's list kept, or nothing at all), the
     lists the wiki tied to the wrong trader set right (the premium
     masters' blueprints off 4583/4584, «Младший помощник»'s reagents off
     7344, Анвар Хасимбек's three gifts of 24); nothing on them out of
     Абу-Хамед's band 16-20 (its medicine 12_15-20), premium, lent or under
     objects.xml's own words, both currencies of the band, Тёмное Эхо[17]
     among the sets, each gun's rounds on sale in the town; the healers'
     fees; the upgraders' windows;
  3. the weapon craft: the masters (A) of the masters' camp 131 and (G) of
     the living quarter 127, the band 17-20, the blueprints off the chiefs
     of the camps of their level, on sale at the (G) master of their class
     -- Абу-Хамед's alone there; the gunsmiths of «Горные тропы» (624), the
     decoder (796) and «Точильный камень Абу-Хамеда» (2282) with its
     blueprints at Шрам;
  4. the plant: the rocks of Абу-Хамед's six mine tiers, each leaving the
     (АХ) ore, the CrBQ rows 13300-13335 (the control rooms' sorting, the
     processing centre 217's lines, the factory 216's 7.62x54R, 7.62x51 and
     8.6x70), in the band of the mines' gates 15-20, and no way through
     them from afro to more afro or from gold to afro.
Then one session, in process, on the wire: Нур-ад-Дин's ticket to
Абу-Хамед for gold, Веласкес's back, a pouch from Марат, Тёмное Эхо from
Марат and Симона, a knife blueprint from Шрам for gold (for afro refused),
rounds at the oasis, a gift at Анвар Хасимбек's, an ingot refused for afro
at Мортимер (446).

    LAVA_RES=.../res python3 server/test_abuhamed_trade.py
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

DB = os.path.join(tempfile.mkdtemp(), "abuhamed_trade.db")
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
import own_items  # noqa: E402
import production  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import setcraft  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "торговля Абу-Хамеда: лавки, цены, Тёмное Эхо, улучшение оружия, точильный камень и завод"

OFF = items.STRING_ID_OFFSET
cat = items.catalogue()
MT = world.mob_types()
items.preload()
with open(os.path.join(ROOT, "data", "orig_items.json"), encoding="utf-8") as _fh:
    ORIG = json.load(_fh)["items"]

# --- the places, the people, the things --------------------------------------------------
STATION, QUARTER, CENTRE, ROAD, MASTERS_CAMP, YARD, OASIS, PORT = 126, 127, 128, 129, 131, 177, 196, 446
DONGOLA_STATION = 49
# Абу-Хамед's places a player gets into where a trader stands: the town's places of
# data/shop_bands.json but the clothing market 467, which the package WORLD cuts with
# its «Торговцы одеждой» (as Абри's 378 and Донгола's 469: in the band's places still,
# nobody gets in).
ABUHAMED_PLACES = (STATION, QUARTER, CENTRE, ROAD, MASTERS_CAMP, YARD, OASIS, PORT)
# Every other place of Абу-Хамед the plan's walk reaches (DESIGN.md 7.2): no trader
# stands in any of them.
REACHED = (71, 1261, 156, 624, 163, 53, 213, 214, 215, 216, 217, 132, 133, 168, 263, 274, 123,
           222, 223, 66, 649, 650, 651, 652, 653, 636, 637, 638, 639, 640, 615, 1014, 1216, 1254,
           1273, 666, 667, 668, 1034, 1035, 1036, 1227, 1228, 1229, 1295, 690, 691, 692, 693, 694)

NUR, VELASQUEZ, MARAT, SIMONA, SCAR, PILOT, KIPLER, KURT = 156, 740, 1219, 1223, 2274, 4680, 1221, 1222
LOTTERY, GOLD_LOTTERY, ANWAR, KODOGO, MORTIMER, AMMO_OASIS = 741, 742, 1968, 2065, 1188, 1232
SUPPLY, KHAN_SELL, JUT, SAMUEL, FLAG = 880, 2391, 207, 893, 1011
GOFUS, BERNARD, JUNIOR = 1013, 1196, 2018
MG_TRADER, ASSAULT_TRADER, RIFLE_TRADER = 1216, 1217, 1218
TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA, TICKET_TO_ABRI = 1567, 1639, 6547
KEYS = (2652, 2653, 3574)                       # AhLoteryKey_15_16, _17_18, _19_19
GOLD_KEYS = (2654, 2655, 3575)                  # AhLoteryKey_g_15_16, _g_17_18, _g_19_19
GIFTS = tuple(range(4329, 4353))                # gift_kid_1..10, gift_girl_1..10, gift_0..3
KNIFE_PRINTS = tuple(range(6632, 6638))         # Заточка / Эргономика / both, 18у and 20у
INGOTS = (7620, 4796, 4797)
POUCHES = [3577, 3580, 5613, 3578, 3579]        # автоматчика, пулеметчика, рукопашника,
                                                # снайпера, спецназовца: Галия's, her order
DARK_A = tuple(range(36056, 36061))             # Тёмное Эхо[17]: the quest series' pieces
DARK_G = tuple(range(60005, 60010))             # ..and its G, types of our own
OASIS_ROUNDS = [6104, 6105, 6106, 6108, 6107, 6110, 6111, 6115, 6116, 6117, 6118, 6120, 6119,
                6122, 6123, 6127, 6113, 6125, 6109, 6121, 6114, 6126, 6112, 6124]
UNLISTED = (749, 753, 4583, 4584, 7344, 7339, 7341, 7342)   # masters with no stall of their own
# The package WORLD holds the trader 7247, with no row and no role, out of the station
# (data/schedule.json held_out) and stands the lottery men all year (world.SEASON_KEPT):
# 741 and 742 at the port. It holds out the masters' twins too, UpGuns types whose rows
# name masters standing by types of their own: 7344 of the quarter and 7339 of the
# masters' camp (Катада and Гияс, each in the other place), and, since the integration,
# 7341 and 7342 beside the very masters they double (Зияд, Имран), as Донгола's review
# held out its two empty machine-gun masters. Their stalls stay decided, empty, should
# they ever stand again.
HELD_OUT = {STATION: {7247}, QUARTER: {7344, 7341}, MASTERS_CAMP: {7339, 7342}}
WORLD_PUTS = {PORT: {LOTTERY, GOLD_LOTTERY}}

# Each trader of Абу-Хамед's places and what decides its stall there, 2026-10-14
# (DESIGN.md 6.2): "band" the town's band of its kinds before its own list
# (data/shop_bands.json SELLERS), "own" data/npcs.json's list, "wiki" the wiki's list as
# it was (items.stock_table; Гофус, Бернар and the doctor's junior helper, as in Абри's
# and Донгола's quarters), "none" no list anywhere and an empty stall (Самуэль, whose
# service is a quest; the warehouse's flag, whose is the repair).
BAND, OWN_, WIKI, NONE = "band", "own", "wiki", "none"
DECIDED = {
    STATION: {SCAR: BAND, VELASQUEZ: OWN_, RIFLE_TRADER: BAND, MG_TRADER: BAND,
              ASSAULT_TRADER: BAND, MARAT: BAND, SIMONA: BAND, KIPLER: BAND, KURT: BAND,
              PILOT: OWN_},
    QUARTER: {7344: OWN_, 7341: OWN_, 753: OWN_, 752: OWN_, 749: OWN_, 748: OWN_, 751: OWN_,
              ANWAR: OWN_, GOFUS: WIKI, SAMUEL: NONE, BERNARD: WIKI, JUNIOR: WIKI},
    CENTRE: {FLAG: NONE},
    ROAD: {KODOGO: OWN_},
    MASTERS_CAMP: {7342: OWN_, 7339: OWN_, 4583: OWN_, 4584: OWN_},
    YARD: {SUPPLY: BAND},
    OASIS: {JUT: BAND, AMMO_OASIS: BAND},
    PORT: {KHAN_SELL: BAND, MORTIMER: OWN_, LOTTERY: OWN_, GOLD_LOTTERY: OWN_},
}
# The lists of data/npcs.json this restoration wrote (or kept: Мортимер's). The
# blueprint stalls' are build_weaponcraft --stock's (below).
OWN = {
    NUR: [TICKET_TO_ABRI, TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA],
    VELASQUEZ: [TICKET_TO_DONGOLA],
    MARAT: POUCHES,
    LOTTERY: list(KEYS),
    GOLD_LOTTERY: list(GOLD_KEYS),
    ANWAR: list(GIFTS),
    AMMO_OASIS: OASIS_ROUNDS,
    SCAR: list(KNIFE_PRINTS),
    PILOT: [],
    KODOGO: [],
    MORTIMER: list(INGOTS),
}
OWN.update((t, []) for t in UNLISTED)
LO, HI = 16, 20

with open(os.path.join(ROOT, "data", "questgen_weaponcraft.json"), encoding="utf-8") as _fh:
    CRAFT_DOC = json.load(_fh)


def city_of(r):
    return r["craft"]["key"].split(":")[1]


AH_ROWS = [r for r in CRAFT_DOC["quests"] if city_of(r) == "abu_hamed"]


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
check("the bus tickets of Абу-Хамед's ride: «Билет в Абу-Хамед из Донголы» 0.25 G and «Билет"
      " в Донголу из Абу-Хамеда» 0.10 G, gold alone, their articles' (no afro price there)",
      [(shown(t), price(t)) for t in (TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA)],
      [("Билет в Абу-Хамед из Донголы", (0, 25)), ("Билет в Донголу из Абу-Хамеда", (0, 10))])
check("  ..each the fare of its ride for gold, so no ticket is dearer than the ride: Нур-ад-Дин's"
      " 276 and Веласкес's 277 (data/quests.json cost_gold)",
      [(price(t)[1], quests.get(q).cost_gold) for t, q in ((TICKET_FROM_DONGOLA, 276),
                                                           (TICKET_TO_DONGOLA, 277))],
      [(25, 25), (10, 10)])
check("  ..named by the original's tickets' run, the one to Донгола with its article's words"
      " (6906, Абри's ticket to Донгола's: build_orig_items rule 7o)",
      (orig(TICKET_FROM_DONGOLA), orig(TICKET_TO_DONGOLA), names.ALL.get(
          items.DESC_ID_OFFSET + TICKET_TO_DONGOLA)),
      ((6916, 6917), (6911, 6906),
       "Линованная бумажка. Карандашом намарано адна паездка в Данголу"))
check("the lottery tickets of Абу-Хамед's lottery men: [16] 3000, [18] 3700, [19] 4730 afro;"
      " [G][16] 3 G, [G][18] 3.5 G, [G][19] 4.5 G in gold alone (their articles: the afro and"
      " the gold price of each)",
      [(cat[t][1], price(t)) for t in KEYS + GOLD_KEYS],
      [("AhLoteryKey_15_16", (3000, 0)), ("AhLoteryKey_17_18", (3700, 0)),
       ("AhLoteryKey_19_19", (4730, 0)), ("AhLoteryKey_g_15_16", (0, 300)),
       ("AhLoteryKey_g_17_18", (0, 350)), ("AhLoteryKey_g_19_19", (0, 450))])
check("  ..named by the original's tickets' run (6927-6932), the [8] ticket's words (6919),"
      " as Абри's and Донгола's",
      [orig(t) for t in KEYS + GOLD_KEYS],
      [(6927, 6919), (6928, 6919), (6929, 6919), (6930, 6919), (6931, 6919), (6932, 6919)])
EVERY = (TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA) + KEYS + GOLD_KEYS + GIFTS + KNIFE_PRINTS
check("every one of them named and described (names.ALL), not by objects.xml's words -- but the"
      " two-effect knife blueprints, which no text describes, as every town's; no premium, none a"
      " quest lends",
      ([t for t in EVERY if shown(t) in (None, cat[t][1]) or (
          items.params_of(t)["desc"] != "" and not names.known(items.params_of(t)["desc"]))
        or items.premium(t) or quests.lent(t)],
       [t for t in EVERY if items.params_of(t)["desc"] == ""]), ([], [6634, 6637]))
GOLD_THINGS = (TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA) + GOLD_KEYS + KNIFE_PRINTS + DARK_G
check("the gold ones are gold things: never off a body, and no stall buys them back",
      sorted({(combat.gold_item(t), combat.drops_on_death(t), sold_for(t)) for t in GOLD_THINGS}),
      [(True, False, 0)])
check("  ..and every afro one sells back for 0.7 of its price at most",
      [t for t in EVERY + DARK_A if not gold_only(t) and sold_for(t) > 0.7 * price(t)[0]], [])
check("the sharpened Мачете (G) of «Точильный камень Абу-Хамеда» are their articles' «Мачете"
      " Mod III/II/I» (data/coldarm_manual.json: the articles draw the plain knife's icon, and"
      " data/items_wiki.json has no record): damage, action points, wear, gold price",
      [(t, items.params_of(t)["h_damage_min"], items.params_of(t)["h_damage_max"],
        items.params_of(t)["strike_cost"], items.params_of(t)["max_break_abs"], price(t))
       for t in (6277, 6278, 6279)],
      [(6277, 158, 337, 15, 7000, (0, 1500)), (6278, 149, 312, 11, 7000, (0, 1500)),
       (6279, 158, 337, 11, 7000, (0, 2000))])

# --- 2. the stalls ------------------------------------------------------------------------
print()
print("the stalls")
AT = {p: [t for t in stood(p) if t not in HELD_OUT.get(p, ())] for p in ABUHAMED_PLACES}
check("every trader standing in a place of Абу-Хамед has its stall decided (data/npcs.json,"
      " the town's band, the wiki's list kept, or none), and the table names nobody who stands"
      " nowhere",
      ({p: sorted(t for t in AT[p] if t not in DECIDED[p]) for p in ABUHAMED_PLACES},
       {p: sorted(t for t in DECIDED[p] if t not in AT[p] and t not in WORLD_PUTS.get(p, ())
                  and t not in HELD_OUT.get(p, ())) for p in ABUHAMED_PLACES}),
      ({p: [] for p in ABUHAMED_PLACES}, {p: [] for p in ABUHAMED_PLACES}))
check("  ..and no trader stands in any other place of Абу-Хамед the plan's walk reaches",
      {p: stood(p) for p in REACHED if stood(p)}, {})
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
      " Абри and both of Абу-Хамед's ride, Веласкес the one back, Марат Галия's pouches, the"
      " lottery men their tickets, Анвар Хасимбек his 24 gifts, the oasis's rounds man every СТ"
      " and ОТ, Шрам his whetstone's six blueprints, the pilot, Кодого and the masters with no"
      " stall nothing", {t: npcs.stock(t) for t in OWN}, OWN)
check("  ..the lists the wiki's links had put on the wrong trader, set right: the premium"
      " masters Басам's and Баха's blueprints off 4583/4584, «Младший помощник»'s reagents off"
      " 7344 -- their stalls empty now --, and three of Анвар Хасимбек's 24 gifts his whole"
      " list",
      ({t: (len(items.stock_table().get(t) or ()) > 0, items.stock_for(t, MASTERS_CAMP
                                                                       if t in (4583, 4584)
                                                                       else QUARTER))
        for t in (4583, 4584, 7344)},
       len(items.stock_table().get(ANWAR) or ()), len(items.stock_for(ANWAR, QUARTER))),
      ({4583: (True, []), 4584: (True, []), 7344: (True, [])}, 3, 24))

STALLS = {(p, t): items.stock_for(t, p) for p in ABUHAMED_PLACES for t in AT[p]}
STALLS.update({(p, t): items.stock_for(t, p) for p, ts in WORLD_PUTS.items() for t in ts})
check("Абу-Хамед is the band 16-20 of data/shop_bands.json, its places these",
      [(c[0], c[1], c[2], sorted(c[3])) for c in shop_bands.CITIES if c[0] == "Абу-Хамед"],
      [("Абу-Хамед", LO, HI, [126, 127, 128, 129, 131, 177, 196, 446, 467])])
check("no gun, knife or set piece out of 16-20 on a seller's stall of Абу-Хамед, no medicine out"
      " of its tiers 12_15-20; every one of a seller's band both ways, the ordinary for afro and"
      " the (G) for gold, but the apothecary Джут's gold alone",
      (sorted((p, t, x) for (p, t), s in STALLS.items() for x in s if t in shop_bands.SELLERS
              and shop_bands.band_ware(x) and not shop_bands.fits(x, LO, HI)),
       sorted((p, t) for (p, t), s in STALLS.items() if t in shop_bands.SELLERS
              and shop_bands.SELLERS[t] and not shop_bands.only(t)
              and not {gold_only(x) for x in s if shop_bands.band_ware(x)} >= {True, False}),
       sorted({(t, shop_bands.only(t)) for (p, t) in STALLS if shop_bands.only(t)})),
      ([], [], [(JUT, "gold")]))
MEDS = sorted({shop_bands.level_of(x) for s in STALLS.values() for x in s
               if shop_bands.medicine(x)})
check("  ..the medicine of three tiers by their floors: 12_15, 16_19, 20 (the band's and the"
      " one under it)", MEDS, [12, 16, 20])
check("Тёмное Эхо[18], A and G, sold by Симона; Марат retains only pouches",
      (sorted(set(DARK_A + DARK_G) - set(STALLS[(STATION, SIMONA)])),
       sorted(set(DARK_A + DARK_G) & set(STALLS[(STATION, MARAT)]))), ([], []))
check("  ..its pieces: the quest series' for afro (200 000, 120 000, 240 000, 160 000, 80 000),"
      " ours for gold at 4000 : 1 (50, 30, 60, 40, 20 G) -- 800 000 afro or 200 G the set",
      ([price(t) for t in DARK_A], [price(t) for t in DARK_G],
       sum(price(t)[0] for t in DARK_A), sum(price(t)[1] for t in DARK_G)),
      ([(200000, 0), (120000, 0), (240000, 0), (160000, 0), (80000, 0)],
       [(0, 5000), (0, 3000), (0, 6000), (0, 4000), (0, 2000)], 800000, 20000))
check("  ..named as the ladder names them, the quest pieces without their «(Q)», a set of A and a"
      " set of G (sets.json 11125 and 60005), not reworked (setcraft.NOT_REWORKED)",
      ([shown(t) for t in DARK_A[:1] + DARK_G[:1]], sorted({sets.set_of(t) for t in DARK_A}),
       sorted({sets.set_of(t) for t in DARK_G}),
       sorted(set(DARK_A + DARK_G) - set(setcraft.NOT_REWORKED)),
       [(own_items.load()[t]["like"], items.own(t)) for t in DARK_G]),
      (["Шлем Тёмного Эха", "Шлем Тёмного Эха (G)"], [11125], [60005], [],
       [(a, True) for a in DARK_A]))
check("Симона: all 60 set pieces; Марат: ten pouches, each with its G right after it",
      (STALLS[(STATION, SIMONA)] == shop_bands.goods(("sets",), LO, HI),
       STALLS[(STATION, MARAT)][-10:], len(STALLS[(STATION, MARAT)])),
      (True, [3577, 3599, 3580, 3602, 5613, 5614, 3578, 3600, 3579, 3601], 10))
check("  ..the pouches at their articles' prices: автоматчика 50 000 / 10 G, пулемётчика"
      " 100 000 / 20 G, рукопашника 40 000 / 8 G, снайпера 20 000 / 4 G, спецназовца 40 000 / 8 G",
      [(price(t), price(items.GOLD_POUCHES[t])) for t in POUCHES],
      [((50000, 0), (0, 1000)), ((100000, 0), (0, 2000)), ((40000, 0), (0, 800)),
       ((20000, 0), (0, 400)), ((40000, 0), (0, 800))])
check("Шрам: the town's knives and his whetstone's six blueprints after them",
      STALLS[(STATION, SCAR)], shop_bands.goods(("knives",), LO, HI) + list(KNIFE_PRINTS))
check("the oasis's «Торговец патронами» (1232): every СТ and ОТ of his list, nothing cut",
      STALLS[(OASIS, AMMO_OASIS)], OASIS_ROUNDS)
check("the lottery men at the port: Муамар the tickets [16], [18], [19], the gold lottery"
      " their [G]",
      (STALLS[(PORT, LOTTERY)], STALLS[(PORT, GOLD_LOTTERY)]), (list(KEYS), list(GOLD_KEYS)))
check("Анвар Хасимбек (127): his 24 gifts in his article's order, as Фрея Каплан's and"
      " Элизабет Стюарт's", STALLS[(QUARTER, ANWAR)], list(GIFTS))
CRAFT_PRINTS = {r["craft"]["blueprint"] for r in CRAFT_DOC["quests"]
                if r["craft"]["family"] == "upgrade"}
check("nothing premium on a stall of Абу-Хамед, nothing a quest lends, each thing priced in one"
      " currency but Мортимер's ingots (items.GOLD_INGOTS: sold for gold, loot worth afro) and"
      " the masters' blueprints the afro line asks, which their articles price both ways",
      sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
             if items.premium(x) or quests.lent(x)
             or (bool(price(x)[0]) == bool(price(x)[1]) and x not in items.GOLD_INGOTS
                 and x not in CRAFT_PRINTS)), [])
check("no thing on a stall of Абу-Хамед shows objects.xml's own words, or a description the"
      " preload lacks", sorted((p, t, x) for (p, t), s in STALLS.items() for x in s
                               if shown(x) in (None, cat[x][1])
                               or (items.params_of(x)["desc"] != ""
                                   and not names.known(items.params_of(x)["desc"]))), [])
ROUNDS = {x for s in STALLS.values() for x in s if items.root_of(x) == items.AMMO}
check("every gun on a stall of Абу-Хамед has a round it chambers on sale in the town",
      sorted({x for s in STALLS.values() for x in s if items.root_of(x) == items.FIRE_ARM
              and not set(items.params_of(x)["comp_array"]) & ROUNDS}), [])
check("the stalls' sizes: none longer than 64 (the prison's supply man's 61 the longest)",
      (max(len(s) for s in STALLS.values()), max(STALLS, key=lambda k: len(STALLS[k]))),
      (61, (YARD, SUPPLY)))
check("the healers' fees: Роуз (728) and the oasis's Лекарь (1270) 500, the prison's"
      " Альфред Петрович (2112) 600 (server/test_healer_fees.py)",
      {t: npcs.healer_price(t, 10) for t in (728, 1270, 2112)}, {728: 500, 1270: 500, 2112: 600})
# The upgraders of Абу-Хамед's places: Анвар Хасимбек's children (2006/2007) -- empty
# windows, as Элизабет Стюарт's and Фрея Каплан's; Жозеф де Гобино (7548) in the oasis the
# [Q] Маузер's twelve, as in every oasis.
check("the upgraders of Абу-Хамед's places: Анвар Хасимбек's children empty windows, Жозеф де"
      " Гобино's in the oasis the [Q] Маузер's twelve, given by him",
      ({t: len(craft.upgrader_lists(t)["out_types"]) for t in (2006, 2007, 7548)},
       7548 in standing(OASIS), len(quests.given_by(7548))),
      ({2006: 0, 2007: 0, 7548: 12}, True, 12))

# --- 3. the weapon craft --------------------------------------------------------------------
print()
print("the weapon craft")
MASTERS = {755: ("assault", "A"), 748: ("assault", "G"), 758: ("mg", "A"), 751: ("mg", "G"),
           759: ("rifle", "A"), 752: ("rifle", "G"), 4583: ("smg", "A"), 753: ("smg", "G"),
           4584: ("pistol", "A"), 749: ("pistol", "G")}
BLUEPRINT_STALLS = {"assault": 748, "mg": 751, "rifle": 752}
GUNSMITHS = {"rifle": 730, "mg": 732, "assault": 733}
WHETSTONE, DECODER, SMITHS = 2282, 796, 624
CHIEFS = {(17, 18): (132, 133, 168), (19, 20): (263, 274)}


def fam(name):
    return [r for r in AH_ROWS if r["craft"]["family"] == name]


ups = fam("upgrade")
check("Абу-Хамед's rows: repeatable services of the band 17-20 (the owner's decision 34), every"
      " family, loaded (quests.get)",
      (sorted({(r["repeatable"], r["service"], r["level"], r["max_level"]) for r in AH_ROWS}),
       sorted({r["craft"]["family"] for r in AH_ROWS}),
       [r["type"] for r in AH_ROWS if quests.get(r["type"]) is None]),
      ([(1, True, 17, 20)], ["assembly", "decode", "knife", "salvage", "upgrade"], []))
check("the masters stand where the labels put them: (A) in the masters' camp 131, (G) in the"
      " living quarter 127",
      ({t: t in standing(MASTERS_CAMP) for t in (755, 758, 759, 4583, 4584)},
       {t: t in standing(QUARTER) for t in (748, 749, 751, 752, 753)}),
      ({t: True for t in (755, 758, 759, 4583, 4584)},
       {t: True for t in (748, 749, 751, 752, 753)}))
check("each recipe at the master of its gun's class and line, A or G, its gun of the band"
      " with the wiki's table, its blueprint of its own level",
      ([r["type"] for r in ups if MASTERS.get(r["give"][0]) != (
          craft.weapon_of(r["craft"]["gun"]), r["craft"]["line"]) or r["take"] != r["give"]],
       sorted({r["craft"]["line"] for r in ups}),
       [r["type"] for r in ups if not 17 <= r["craft"]["level"] <= 20
        or r["craft"]["gun"] not in items.wiki()
        or level_of_bp(r["craft"]["blueprint"]) != r["craft"]["level"]]),
      ([], ["A", "G"], []))
check("  ..assault rifles, machine guns and rifles have recipes for both A and G",
      (sorted({r["give"][0] for r in ups}),
       collections.Counter((craft.weapon_of(r["craft"]["gun"]), r["craft"]["line"])
                           for r in ups)),
      ([748, 751, 752, 755, 758, 759], {("assault", "A"): 3, ("assault", "G"): 3, ("mg", "A"): 28, ("mg", "G"): 28,
                                   ("rifle", "A"): 12, ("rifle", "G"): 12}))
worse = []
for r in ups + fam("knife"):
    a = items.params_of(r["craft"]["gun"])["max_break_abs"]
    b = items.params_of(r["craft"]["mod"])["max_break_abs"]
    if b < a or price(r["craft"]["gun"]) != price(r["craft"]["mod"]) and r in ups:
        worse.append(r["type"])
check("  ..a modification at its gun's price and never a lower wear ceiling (a sharpened"
      " Мачете (G) too: 7000 against 3500, its articles')", worse, [])
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
check("the stat blueprints of 17-20 drop off the chiefs of the camps of their level (the pirates"
      " 132/133 and the outpost 168 17-18, the base of the Northern Alliance 263/274 19-20)",
      (stray, sorted({r["craft"]["level"] for r in ups if r["objs"][1].get("mobs")}),
       sorted({r["craft"]["level"] for r in ups if not r["objs"][1].get("mobs")})),
      ([], [17, 18, 19, 20], []))
by_class = {}
for r in ups:
    by_class.setdefault(craft.weapon_of(r["craft"]["gun"]), set()).add(r["craft"]["blueprint"])
check("the blueprint stalls, the (G) masters of 127 (748 Гияс, 751 Заки, 752 Зияд): each the"
      " blueprints of its class's recipes of Абу-Хамед, all of them and no other, by level",
      ({cls: sorted(set(npcs.stock(s)) ^ by_class[cls]) for cls, s in BLUEPRINT_STALLS.items()},
       {cls: [level_of_bp(t) for t in npcs.stock(s)] == sorted(level_of_bp(t)
                                                               for t in npcs.stock(s))
        for cls, s in BLUEPRINT_STALLS.items()}),
      ({cls: [] for cls in BLUEPRINT_STALLS}, {cls: True for cls in BLUEPRINT_STALLS}))
DONGOLA_STALLS = (580, 583, 584, 585)
check("  ..a city's blueprints at its own stalls: Абу-Хамед's of 17-20, Донгола's of 16 at most,"
      " so neither town's stall sells the other's",
      (sorted({level_of_bp(t) for s in BLUEPRINT_STALLS.values() for t in npcs.stock(s)}),
       max(level_of_bp(t) for s in DONGOLA_STALLS for t in npcs.stock(s))),
      ([17, 18, 19, 20], 16))
sys.path.insert(0, os.path.join(ROOT, "data"))
source = os.environ.get("LAVA_ORIG_TEXTS") or "/mnt/c/Users/gmkrt/Downloads/texts.xml"
if os.path.isfile(source):
    import build_weaponcraft  # noqa: E402
    printed = build_weaponcraft.stock(CRAFT_DOC)
    check("  ..as build_weaponcraft --stock prints them", {s: printed[s] == npcs.stock(s) for s in
                                                          list(BLUEPRINT_STALLS.values())
                                                          + [SCAR]},
          {s: True for s in list(BLUEPRINT_STALLS.values()) + [SCAR]})
    check("  ..and the generator reads «детали от винтовок» as a rifle's (KIND_WORDS): the"
          " rifles' assembly of the newest edition is built",
          (build_weaponcraft.kind_of("винтовок"), build_weaponcraft.kind_of("винтовки")),
          ("rifle", "rifle"))
asked = {}
for r in ups:
    asked.setdefault(r["craft"]["blueprint"], set()).add(r["craft"]["line"])
check("  ..the gold line's own blueprints (asked only by the (G) guns' rows) for gold alone, a"
      " gold thing; every blueprint the afro line asks has its afro price",
      ([t for t, ls in asked.items() if ls == {"G"} and not (gold_only(t) and combat.gold_item(t))],
       [t for t, ls in asked.items() if "A" in ls and not price(t)[0]]), ([], []))
gun_stalls = {x for s in STALLS.values() for x in s if items.root_of(x) == items.FIRE_ARM}
check("  ..and every gun of a recipe on sale in the town, the ordinary and the (G)",
      sorted({r["craft"]["gun"] for r in ups} - gun_stalls), [])
sal, ass, dec, kni = fam("salvage"), fam("assembly"), fam("decode"), fam("knife")
check("the gunsmiths of «Горные тропы: Мастера» (624): salvage and assembly at the gunsmith of"
      " the class -- the rifles' 5th class and the machine guns' 2nd-5th, the band's machine"
      " guns and HK PSG-1 and Brugger & Thomet APR 338; every part an assembly asks one a"
      " salvage row draws; the assault rifles' gunsmith stands with nothing of 17-20 to do (the"
      " class's parts are of 12-16, Донгола's)",
      (sorted({(r["give"][0], r["craft"]["weapon"]) for r in sal}),
       sorted({(r["give"][0], craft.weapon_of(r["rew_obj"][0])) for r in ass}),
       sorted(r["rew_obj"][0] for r in ass if craft.weapon_of(r["rew_obj"][0]) == "rifle"),
       sorted({o["obj"] for r in ass for o in r["objs"]}
              - {o["obj"] for r in CRAFT_DOC["quests"] if r["craft"]["family"] == "salvage"
                 for o in r["rew_random"]}),
       sorted(GUNSMITHS.values()) == sorted(t for t in standing(SMITHS) if t in (730, 732, 733))),
      ([(730, "rifle"), (732, "mg")], [(730, "rifle"), (732, "mg")], [25819, 25835], [], True))
check("the decoder Техногик (796, the living quarter): «Чертежи N-го уровня» for 17-20, a fee, a"
      " blueprint of the level drawn, the encrypted one off the camps of its level",
      ([(r["give"], r["craft"]["level"], r["cost_afro"] > 0,
         all(level_of_bp(o["obj"]) == r["craft"]["level"] for o in r["rew_random"]),
         bool(r["objs"][0].get("mobs"))) for r in dec], DECODER in standing(QUARTER)),
      ([([DECODER], n, True, True, True) for n in range(17, 21)], True))


def decode_margin(r):
    """What a decode leaves its player, the drawn blueprint sold back at once
    (the draw's mean sale less the fee), and a tenth of what the draw is worth
    (the mean price): data/build_weaponcraft.py DECODE_FEE."""
    worth = sum(items.params_of(o["obj"])["cost"] for o in r["rew_random"]) / len(r["rew_random"])
    sale = sum(sold_for(o["obj"]) for o in r["rew_random"]) / len(r["rew_random"])
    return sale - r["cost_afro"], worth / 10.0


check("  ..and no farm: a decoded blueprint sold back nets at most a tenth of its price (the fee"
      " is 60 % of the draw's)",
      [r["craft"]["level"] for r in dec if decode_margin(r)[0] > decode_margin(r)[1]], [])
check("«Точильный камень Абу-Хамеда» (2282, the station) sharpens Кукри (G) (18у) and Мачете"
      " (G) (20у) three ways each, in the original's words",
      (sorted((r["craft"]["gun"], r["craft"]["blueprint"], r["rew_obj"][0]) for r in kni),
       [quests.get(r["type"]).texts[quests.NAME] for r in kni], WHETSTONE in standing(STATION),
       {r["give"][0] for r in kni}),
      ([(6271, 6632, 6272), (6271, 6633, 6273), (6271, 6634, 6274), (6276, 6635, 6277),
        (6276, 6636, 6278), (6276, 6637, 6279)],
       ["Заточка Кукри", "Эргономика Кукри", "Заточка и Эргономика Кукри",
        "Заточка Мачете", "Эргономика Мачете", "Заточка и Эргономика Мачете"], True,
       {WHETSTONE}))
check("  ..its blueprints and knives (G) on Шрам's stall beside it, the blueprints for gold"
      " alone: 4 / 4 / 8 G (Кукри), 5 / 5 / 10 G (Мачете)",
      (sorted({r["craft"]["blueprint"] for r in kni} - set(STALLS[(STATION, SCAR)])),
       sorted({r["craft"]["gun"] for r in kni} - set(STALLS[(STATION, SCAR)])),
       [price(t) for t in KNIFE_PRINTS]),
      ([], [], [(0, 400), (0, 400), (0, 800), (0, 500), (0, 500), (0, 1000)]))

# --- 4. the plant ---------------------------------------------------------------------------
print()
print("the plant")
AH_TIERS = {1034: (1319, 10), 1227: (1358, 9), 1036: (1311, 15), 1229: (1348, 11),
            1035: (1315, 10), 1228: (1353, 10)}
AH_ORE = {"copper": 3647, "plumbum": 3639, "nitre": 3643}
ROCK_ORE = {1319: 3647, 1358: 3647, 1311: 3639, 1348: 3639, 1315: 3643, 1353: 3643}
SORTERS = {"plumbum": (1362, 668), "nitre": (1366, 667), "copper": (1370, 666)}
LINES = {"plumbum": 1374, "nitre": 1378, "copper": 1382}
CENTRE_217, FACTORY, ASSEMBLER = 217, 216, 1386
X54R, X51, X70 = 6099, 6095, 6102
GEN = list(range(13300, 13336))
check("each of Абу-Хамед's six mine tiers stands the rocks its file puts there"
      " (production.ORE_ROCKS) and its two guards, not the electrical panel",
      {i: (standing(i)[rock], standing(i)[1717], standing(i)[2022])
       for i, (rock, _n) in AH_TIERS.items()},
      {i: (n, 2, 0) for i, (_r, n) in AH_TIERS.items()})
check("  ..an immobile, harmless object each, leaving one piece of Абу-Хамед's ore of its kind,"
      " the (АХ) copy", ({(mobs.stats(r).role, mobs.stats(r).moves, mobs.stats(r).can_attack)
                         for r in ROCK_ORE},
                        {r: production.yield_of(r) for r in sorted(ROCK_ORE)},
                        [shown(o) for o in (3639, 3643, 3647)]),
      ({("object", False, False)}, {r: [(o, 1)] for r, o in sorted(ROCK_ORE.items())},
       ["(АХ) Свинцовая руда", "(АХ) Селитра сырьевая", "(АХ) Медная руда"]))
with open(os.path.join(ROOT, "data", "questgen_production.json"), encoding="utf-8") as _fh:
    GEN_DOC = json.load(_fh)
rows = {r["type"]: r for r in GEN_DOC["quests"] if 13300 <= r["type"] < 13400}
check("Абу-Хамед's 36 rows, 13300-13335, of the CrBQ family, loaded",
      (sorted(rows), [t for t in rows if quests.get(t) is None],
       [t for t, r in rows.items() if "for АХ from the original's CrBQ№" not in r["why"]]),
      (GEN, [], []))
where = {}
for o, (term, room_) in SORTERS.items():
    where.update({t: (term, room_) for t, r in rows.items() if r["give"] == [term]})
    where.update({t: (LINES[o], CENTRE_217) for t, r in rows.items() if r["give"] == [LINES[o]]})
where.update({t: (ASSEMBLER, FACTORY) for t, r in rows.items() if r["give"] == [ASSEMBLER]})
check("  ..each given and taken by the terminal or line that stands where it works: the"
      " control rooms 668/667/666, the processing centre 217, the factory 216",
      [t for t in rows if t not in where or rows[t]["take"] != rows[t]["give"]
       or where[t][0] not in standing(where[t][1])], [])
check("  ..in the band of the mines' gates, 15-20 («Вход разрешен персонажам 15-20 ур.»,"
      " L317-L319), services",
      sorted({(r["level"], r["max_level"], r["service"]) for r in rows.values()}),
      [(15, 20, True)])
asks = {t: [(o["obj"], o["num"]) for o in r["objs"]] for t, r in rows.items()}
makes = {t: (r["rew_obj"][0], r["num_rew_obj"][0]) for t, r in rows.items()}
check("sorting: Абу-Хамед's ore into its sorted ore, the lines: sorted ore into its sacks, the"
      " factory: the three sacks into 7.62x54R, 7.62x51 НАТО and 8.6x70 КС, not their (P) twins",
      (sorted({(asks[t][0][0], makes[t][0]) for t in rows if rows[t]["give"][0] in
               (1362, 1366, 1370, 1374, 1378, 1382)}),
       sorted({makes[t][0] for t in rows if rows[t]["give"] == [ASSEMBLER]}),
       sorted({o for t in rows if rows[t]["give"] == [ASSEMBLER] for o, _n in asks[t]}),
       [items.premium(t) for t in (X54R, X51, X70)], [shown(t) for t in (X54R, X51, X70)]),
      (sorted([(3639, 3675), (3643, 3679), (3647, 3683), (3675, 3651), (3679, 3655),
               (3683, 3659)]), [X51, X54R, X70], [3651, 3655, 3659], [False, False, False],
       ["7.62х54R $КС", "7.62х51мм НАТО $КС", "8.6x70 $КС"]))
check("  ..each first sorting run one first line of the centre, as in Вади-Хальфа, Абри and"
      " Донгола", [makes[t][1] for t in (13300, 13304, 13308)]
      == [asks[t][0][1] for t in (13312, 13316, 13320)], True)
check("  ..the rounds it makes are guns' of the town's band on its stalls",
      sorted({t for t in (X54R, X51, X70) if any(t in items.params_of(g)["comp_array"]
                                                  for g in gun_stalls)}), sorted([X54R, X51, X70]))
plant_in = {o for t in rows for o, _n in asks[t]}
for_sale = {x for tr in set(items.stock_table()) | set(npcs.STOCK) for x in items.stock_for(tr)}
check("no way from afro to more afro: nothing a row asks is on any stall of the game, the sorted"
      " ore and the sacks are worth nothing at one, the ore 0.7 afro a piece, a round 0.7 --"
      " less than the 1 afro a round the stalls sell it for",
      (sorted(plant_in & for_sale), sorted({sold_for(o, 100) for o in plant_in}),
       sold_for(AH_ORE["plumbum"], 10), [sold_for(t, 600) for t in (X54R, X51, X70)],
       [price(t)[0] // items.params_of(t)["sell_num"] for t in (X54R, X51, X70)]),
      ([], [0, 70], 7, [420, 420, 420], [1, 1, 1]))
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
      (len(extra), [t for t, (fee, worth) in extra.items() if worth >= fee]), (9, []))
load = {t: sum(items.params_of(o)["weight"] * n for o, n in asks[t]) for t in rows}
check("what any row asks fits the bag on its own (inventory.MAX_WEIGHT): 13301's 52 pieces of"
      " lead the heaviest, 39 kg",
      ([t for t in rows if load[t] > inventory.MAX_WEIGHT], max(load, key=load.get),
       load[13301]), ([], 13301, 39000))

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("abuhamedtrader", "secret")
_store.close()
CRED = accounts.credential("abuhamedtrader", "secret")

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
    sess = server.Session(Writer(), "abuhamedtrader")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Abuhamedtrader@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 500000 50000@;group=0;")
    BUY, GOLD = inventory.UPD_BUY, inventory.UPD_BUY_GOLD
    REFUSED = [inventory.RES_REFUSED]

    stall, opened = open_stall(sess, DONGOLA_STATION, NUR)
    check("Нур-ад-Дин (Донгола's station): his window the ticket to Абри and both of Абу-Хамед's"
          " ride; the ticket to Абу-Хамед for its 0.25 ounces in gold, for afro refused, not"
          " bought back",
          (stall, opened, buy(sess, stall, TICKET_FROM_DONGOLA, BUY),
           buy(sess, stall, TICKET_FROM_DONGOLA, GOLD), sell(sess, TICKET_FROM_DONGOLA)),
          ([TICKET_TO_ABRI, TICKET_FROM_DONGOLA, TICKET_TO_DONGOLA], [0], (REFUSED, [], 0, 0),
           ([0], [TICKET_FROM_DONGOLA], 0, 25), (REFUSED, True, 0, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, STATION, VELASQUEZ)
    check("Веласкес (Абу-Хамед's station): his window the ticket to Донгола, 0.10 ounces",
          (stall, opened, buy(sess, stall, TICKET_TO_DONGOLA, GOLD)),
          ([TICKET_TO_DONGOLA], [0], ([0], [TICKET_TO_DONGOLA], 0, 10)))
    close_stall(sess)

    stall, opened = open_stall(sess, STATION, MARAT)
    piece_g = DARK_G[0]
    check("Марат: pouches for afro and gold, no armour in his window",
          (stall == items.stock_for(MARAT, STATION), opened, buy(sess, stall, 3577, BUY),
           buy(sess, stall, 3599, GOLD), piece_g in stall),
          (True, [0], ([0], [3577], 50000, 0), ([0], [3599], 0, 1000), False))
    close_stall(sess)

    stall, opened = open_stall(sess, STATION, SIMONA)
    check("Симона sells the gold Dark Echo helmet for gold alone",
          (buy(sess, stall, piece_g, BUY), buy(sess, stall, piece_g, GOLD)),
          ((REFUSED, [], 0, 0), ([0], [piece_g], 0, 5000)))
    piece_a = DARK_A[-1]
    check("Симона: her window the town's sets; the boots of Тёмное Эхо for 80 000 afro, for gold"
          " refused; sold back for 0.7",
          (stall == items.stock_for(SIMONA, STATION), opened, buy(sess, stall, piece_a, GOLD),
           buy(sess, stall, piece_a, BUY), sell(sess, piece_a)),
          (True, [0], (REFUSED, [], 0, 0), ([0], [piece_a], 80000, 0), ([0], False, 56000, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, STATION, SCAR)
    check("Шрам: «Заточка Кукри (18у)» for its 4 ounces in gold; for afro refused; not bought"
          " back",
          (stall == items.stock_for(SCAR, STATION), opened, buy(sess, stall, 6632, GOLD),
           buy(sess, stall, 6632, BUY), sell(sess, 6632)),
          (True, [0], ([0], [6632], 0, 400), (REFUSED, [], 0, 0), (REFUSED, True, 0, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, PORT, MORTIMER)
    check("Мортимер (the port 446): an ingot for afro refused, for gold its ounces",
          (stall, opened, buy(sess, stall, 7620, BUY), buy(sess, stall, 7620, GOLD)),
          (list(INGOTS), [0], (REFUSED, [], 0, 0), ([0], [7620], 0, 100)))
    close_stall(sess)

    stall, opened = open_stall(sess, QUARTER, 751)
    check("Мастер Заки (751, the living quarter): his window the machine guns' blueprints of"
          " Абу-Хамед", (stall, opened), (npcs.stock(751), [0]))
    close_stall(sess)

    stall, opened = open_stall(sess, OASIS, AMMO_OASIS)
    check("the oasis's «Торговец патронами»: 7.62x54R СТ for 160 afro a pack of 20",
          (stall, opened, buy(sess, stall, 6111, BUY, 20)),
          (OASIS_ROUNDS, [0], ([0], [6111], 160, 0)))
    close_stall(sess)

    stall, opened = open_stall(sess, QUARTER, ANWAR)
    check("Анвар Хасимбек (the living quarter): his 24 gifts; «Пистолет» for 500 afro",
          (stall, opened, buy(sess, stall, 4329, BUY)),
          (list(GIFTS), [0], ([0], [4329], 500, 0)))
    close_stall(sess)


asyncio.run(main())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("abuhamed trade OK")
