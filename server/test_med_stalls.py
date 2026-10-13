"""Медицина по уровню городов: every city sells its tiers of «Боевая медицина»
and «Еда, вода, лекарства», each tier in afro and in gold, the gold one the
stronger.

The owner's order of 2026-10-12: «сделай во всех городах нормальную продажу
медикаментов и боевой медицины, чтобы везде всё было по уровням, были
версии афро и голд, афро меньше статов должна давать. Короче продумай
нормально всё и реализуй, а то тут намешано кое-как» (data/shop_bands.json
combat_meds / peace_meds and only, server/shop_bands.py MED_REACH,
data/heal_manual.json 7100-7105).

The expectation is worked out here on its own, from the client's catalogue
(objects.xml) and this suite's own reading of the internal names, not through
shop_bands: a tier is the levels in the name (0_3 .. 20), its level the floor;
a city sells the tiers whose floor lies from its band's floor less 4 to its
ceiling (the band's and the one under it, as six of the seven medicine stalls
of the original the wiki describes did); a tier's rows go bandage, energy
drink, injector (G), its 20 doses (G) / food, food of ten, water, kit (G).

In process:
  1. the catalogue: the 48 types of the two lines, 6 tiers of 4 rows each,
     are the band's wares at their tier's floor, (G) by the name, priced in
     their own currency alone at the original's prices (but «Эгоист»'s,
     0.02 G over its article's 0.01), named by the original and drawn by
     the client; the (P), the thousand-dose pack, the May and test ones are
     not;
  2. the packs of 20 doses: the single injector's numbers, twenty uses,
     twenty times the price, gold alone, a gold thing, the injector's words;
     7103 and 7104 the packs Серхио's article sells, 7105 ours;
  3. afro is weaker: tier by tier the injector heals twice the bandage's
     health (the maximum exactly, the minimum one short at most) and at
     least the energy drink's stamina, both in one action for fewer AP; the
     kit twice the food's health and at least the water's stamina; and afro
     is cheaper, a dose in a fight and a use out of one, every tier;
  4. the stalls: every medicine seller at every place of its city sells
     exactly its city's tiers of its kinds, in one currency where the file
     says only, in the order above, then its own list; pinned stall by
     stall, the «Патроны и лекарства» of the valley's truck and of the
     prison yards among them (the supply men's rounds their article's);
     the apothecary Джут three oases, three stalls; nothing without a
     price on any stall of a city's place (Донгола's grocer no quest
     parcel);
  5. coverage: every city has a seller of each line, and its city's tiers
     are on sale in both currencies; every trader of a city's place the
     original titles a medicine or food seller is one, and none of them
     opens an empty window;
  6. nothing out of a city's tiers on any stall of its places, no medicine
     of the lines on a seller's of no medicine kind, the currencies of only,
     no list of data/npcs.json carrying what the band gives;
  7. outside the cities a stall is its own list, Киплер's and Курт's in
     Мероэ their articles'; Донгола's black market has its machine-gun
     trader (1208) back, and he and the four medics of Донгола and Абу-Хамед
     the original's names;
  8. no way to more afro: a medicine sells back for 0.7 of its price at most,
     the gold ones not at all;
  9. the switches: MED_REACH 0 leaves two tiers a city, a file without only
     both currencies; a file giving only to a weapon seller stops the server;
 10. «Свежий хлеб» (482) still finds its water at Мухсим's.
Then one session, in process, on the wire: Люций's window at the black market
of Вади-Хальфа, a bandage bought for afro and an injector for gold by the
window's index, the wrong currency refused, the bandage sold back for 0.7, the
injector not; Джут's one index buying another thing at another oasis.

    LAVA_RES=.../res python3 server/test_med_stalls.py
"""
import asyncio
import json
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB = os.path.join(tempfile.mkdtemp(), "med_stalls.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START", "LAVA_PLACEMENTS"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "медицина по уровню городов: боевая медицина и медикаменты по ярусам, афро и (G)"

OFF = items.STRING_ID_OFFSET
cat = items.catalogue()
BY_NAME = {n: t for t, (_r, n) in cat.items()}
items.preload()
with open(os.path.join(ROOT, "data", "shop_bands.json"), encoding="utf-8") as _fh:
    BANDS_DOC = json.load(_fh)
with open(os.path.join(ROOT, "data", "heal_manual.json"), encoding="utf-8") as _fh:
    MANUAL = json.load(_fh)["items"]

# --- the reading of the names, this suite's own ----------------------------------------------
TIERS = ("0_3", "4_7", "8_11", "12_15", "16_19", "20")
FLOOR = {tier: int(tier.split("_")[0]) for tier in TIERS}
LINE_WORD = {"combat_meds": "Battle", "peace_meds": "Pacific"}
# A tier's rows in the stall's order: what, variant. The afro ones first.
ROWS = {"combat_meds": (("Heal", "A"), ("Rest", "A"), ("HR", "G"), ("HR", "G_Pack")),
        "peace_meds": (("Heal", "A"), ("Heal", "Ax10"), ("Rest", "A"), ("HR", "G"))}
REACH = 4          # a tier under the band: the design's (2026-10-12), shop_bands.MED_REACH
NAME = re.compile(r"^Med_(Battle|Pacific)_")


def med(kind, tier, row):
    """The type of a tier's row."""
    what, variant = ROWS[kind][row]
    return BY_NAME["Med_%s_%s_%s_%s" % (LINE_WORD[kind], what, tier, variant)]


def gold_row(kind, row):
    return ROWS[kind][row][1].startswith("G")


LADDER = {(kind, tier, row): med(kind, tier, row) for kind in ROWS for tier in TIERS
          for row in range(4)}
OF = {t: key for key, t in LADDER.items()}


def tiers_of(low, top, reach=REACH):
    return [tier for tier in TIERS if low - reach <= FLOOR[tier] <= top]


def expect(kinds, low, top, only=None, reach=REACH):
    """A seller's medicine at a city low-top, in the stall's order."""
    out = []
    for kind in kinds:
        for tier in tiers_of(low, top, reach):
            for row in range(4):
                gold = gold_row(kind, row)
                if (only == "afro" and gold) or (only == "gold" and not gold):
                    continue
                out.append(LADDER[(kind, tier, row)])
    return out


def line_med(t):
    """A medicine of the two lines, any variant: what the city's band decides."""
    return cat[t][0] == items.HEAL and bool(NAME.match(cat[t][1]))


def price(t):
    p = items.params_of(t)
    return p["cost"], p["g_cost"]


def gold_only(t):
    cost, g = price(t)
    return g > 0 and not cost


def shown(t):
    return names.ALL.get(OFF + t, "")


# --- 1. the catalogue ------------------------------------------------------------------------
print("the catalogue")
WARES = shop_bands.wares()
check("the two lines: 6 tiers of 4 rows each, 48 types of objects.xml under the medicine root",
      (len(LADDER), len(set(LADDER.values())), {cat[t][0] for t in LADDER.values()}),
      (48, 48, {items.HEAL}))
check("  ..each a ware of the band: its kind, the floor of its tier for its level, its row, (G)"
      " by its name",
      {t: WARES.get(t) for (kind, tier, row), t in LADDER.items()
       if WARES.get(t) != (kind, FLOOR[tier], row, 1 if gold_row(kind, row) else 0)}, {})
check("  ..and no other medicine is one: not the (P) kits 6067-6072, the thousand-dose pack"
      " 31746, the May ones, the tests",
      sorted(t for t, w in WARES.items() if w[0] in shop_bands.MED_KINDS and t not in OF), [])
check("  ..those left out are out for their reasons: the (P) premium, 31746 and the tests no"
      " numbers of an article",
      ([items.premium(t) for t in range(6067, 6073)], 31746 in items.wiki() or 31746 in MANUAL,
       sorted(t for t, (r, n) in cat.items() if n.startswith("may_Med_") and t in WARES)),
      ([True] * 6, False, []))
check("each priced in its own currency alone: afro for the afro rows, gold for the (G)",
      sorted(t for (kind, _tier, row), t in LADDER.items()
             if gold_only(t) != gold_row(kind, row) or bool(price(t)[0]) == bool(price(t)[1])),
      [])
# The original's prices, off the wiki's articles (items_wiki.json) and the packs' rule
# (heal_manual.json: twenty single doses): afro, and gold in hundredths of an ounce. All
# but «Эгоист»'s (6904), 0.02 G over its article's 0.01 (heal_manual.json over_article):
# at 0.01 a use of the gold kit cost less afro than food and water (below).
PRICES = {
    ("combat_meds", 0): [22, 34, 61, 105, 196, 306],         # bandages
    ("combat_meds", 1): [19, 46, 82, 127, 183, 307],         # energy drinks
    ("combat_meds", 2): [1, 2, 3, 4, 5, 6],                  # injectors (G)
    ("combat_meds", 3): [20, 40, 60, 80, 100, 120],          # 20 doses (G)
    ("peace_meds", 0): [12, 21, 42, 76, 150, 242],           # food
    ("peace_meds", 1): [118, 210, 416, 761, 1501, 2415],     # food of ten
    ("peace_meds", 2): [171, 527, 1062, 1778, 2700, 4725],   # water of ten uses
    ("peace_meds", 3): [2, 6, 11, 18, 31, 51],               # kits of twenty (G)
}
check("  ..at the original's prices, tier by tier, «Эгоист» at 0.02 G",
      {key: [max(price(LADDER[(key[0], tier, key[1])])) for tier in TIERS] for key in PRICES},
      PRICES)
check("  ..the article's own 0.01 G under it, overruled by data/heal_manual.json alone, which"
      " says why (DESIGNED)",
      (items.wiki()[6904]["g_cost"], sorted(items.heal_over_article()),
       "29" in items.heal_over_article()[6904]["_designed"]), (1, [6904], True))
check("each named by the original, never by objects.xml, its description in the preload, and"
      " drawn: classes/Heal_Item/<name>/ico.swf",
      sorted(t for t in LADDER.values()
             if not shown(t) or shown(t) == cat[t][1]
             or (items.params_of(t)["desc"] != "" and not names.known(items.params_of(t)["desc"]))
             or not os.path.isfile(os.path.join(world.RES, "classes", "Heal_Item", cat[t][1],
                                                "ico.swf"))), [])
check("  ..the gold ones with their (G), the afro ones without",
      sorted(t for t in LADDER.values() if ("(G)" in shown(t)) != gold_only(t)), [])
check("the peace line is no use in a fight (items.no_combat), the battle line is",
      sorted({(OF[t][0], items.no_combat(t)) for t in LADDER.values()}),
      [("combat_meds", False), ("peace_meds", True)])

# --- 2. the packs of 20 doses ----------------------------------------------------------------
print()
print("the packs of 20 doses")
NUMBERS = ("min_h_rest", "max_h_rest", "min_st_rest", "max_st_rest", "heal_cost", "weight")
packs = {}
for tier in TIERS:
    pack, single = LADDER[("combat_meds", tier, 3)], LADDER[("combat_meds", tier, 2)]
    p, s = items.params_of(pack), items.params_of(single)
    packs[pack] = ([p[k] for k in NUMBERS] == [s[k] for k in NUMBERS], p["use_count"],
                   p["g_cost"] == 20 * s["g_cost"], p["cost"], combat.gold_item(pack),
                   names.text(p["desc"]) == names.text(s["desc"]),
                   shown(pack).startswith("20 доз " + shown(single).split(" (G)")[0]))
check("7100-7105: the single injector's numbers, twenty uses, twenty times its gold price and no"
      " afro one, a gold thing, the injector's own words, named «20 доз ...»",
      packs, {t: (True, 20, True, 0, True, True, True) for t in range(7100, 7106)})
check("  ..7103-7105 off data/heal_manual.json, the frame's 60 afro and one use no more; 7103 and"
      " 7104 the packs the wiki's «Серхио» sold (RECOVERED), 7105 sold by the rule (DESIGNED)",
      ([t for t in (7103, 7104, 7105) if str(t) not in MANUAL],
       ["Серхио" in MANUAL[str(t)]["_source"] for t in (7103, 7104, 7105)],
       "that it is sold" in MANUAL["7105"]["_designed"]),
      ([], [True, True, False], True))

# --- 3. afro is weaker, and cheaper ----------------------------------------------------------
print()
print("afro is weaker, and cheaper")


def hp(t):
    p = items.params_of(t)
    return p["min_h_rest"], p["max_h_rest"]


def st(t):
    p = items.params_of(t)
    return p["min_st_rest"], p["max_st_rest"]


def ap(t):
    return items.params_of(t)["heal_cost"]


weak = {}
for tier in TIERS:
    bandage, drink, injector = (LADDER[("combat_meds", tier, r)] for r in range(3))
    food, _ten, water, kit = (LADDER[("peace_meds", tier, r)] for r in range(4))
    why = []
    if hp(injector)[1] != 2 * hp(bandage)[1] or not 2 * hp(bandage)[0] - 1 <= hp(injector)[0] \
            <= 2 * hp(bandage)[0]:
        why.append("injector's health %r, bandage's %r" % (hp(injector), hp(bandage)))
    if st(injector)[0] < st(drink)[0] or st(injector)[1] < st(drink)[1]:
        why.append("injector's stamina %r, drink's %r" % (st(injector), st(drink)))
    if not ap(injector) < min(ap(bandage), ap(drink)):
        why.append("AP %d against %d and %d" % (ap(injector), ap(bandage), ap(drink)))
    if st(bandage)[1] > 10 or hp(drink)[1] > 10:
        why.append("an afro one heals both")
    if hp(kit)[1] != 2 * hp(food)[1] or not 2 * hp(food)[0] - 1 <= hp(kit)[0] <= 2 * hp(food)[0]:
        why.append("kit's health %r, food's %r" % (hp(kit), hp(food)))
    if st(kit)[0] < st(water)[0] or st(kit)[1] < st(water)[1]:
        why.append("kit's stamina %r, water's %r" % (st(kit), st(water)))
    if why:
        weak[tier] = why
check("tier by tier the gold one gives more: the injector twice the bandage's health (the maximum"
      " exactly, the minimum one short at most) and no less stamina than the energy drink, both"
      " in one action for fewer AP than either; the kit twice the food's health and no less"
      " stamina than the water", weak, {})
check("  ..what the bandage and the drink cost in AP for both bars, and the injector",
      [(ap(LADDER[("combat_meds", tier, 0)]) + ap(LADDER[("combat_meds", tier, 1)]),
        ap(LADDER[("combat_meds", tier, 2)])) for tier in TIERS],
      [(14, 5), (19, 6), (24, 7), (29, 8), (34, 9), (39, 10)])
RATE = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE      # afro a hundredth
check("afro is cheaper a dose in a fight: a bandage and an energy drink cost less afro than one"
      " injector at the rate (50 000 afro the ounce), every tier",
      [(price(LADDER[("combat_meds", tier, 0)])[0] + price(LADDER[("combat_meds", tier, 1)])[0],
        int(price(LADDER[("combat_meds", tier, 2)])[1] * RATE)) for tier in TIERS],
      [(41, 500), (80, 1000), (143, 1500), (232, 2000), (379, 2500), (613, 3000)])
per_use = [(int(math.floor(price(LADDER[("peace_meds", tier, 0)])[0]
                            + price(LADDER[("peace_meds", tier, 2)])[0] / 10.0 + 0.5)),
            int(price(LADDER[("peace_meds", tier, 3)])[1] * RATE / 20)) for tier in TIERS]
check("  ..and out of one a use of food and water costs less than a kit's, every tier: at 0_3"
      " «Эгоист» 50 afro a use against 29 (0.02 G; the article's 0.01 made it 25, the cheaper"
      " of the two -- decision 9), each kit 1.7 to 2 times its tier's food and water",
      (per_use, all(a < g <= 2.1 * a for a, g in per_use)),
      ([(29, 50), (74, 150), (148, 275), (254, 450), (420, 775), (715, 1275)], True))

# --- 4. the stalls ---------------------------------------------------------------------------
print()
print("the stalls")
mt = world.mob_types()


def stood(loc_id):
    """The trader types standing in a place, as its room puts them down."""
    room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), mt)
    out = []
    for npc in room.npcs.values():
        if npc.root == world.TRADER and npc.type_id not in out:
            out.append(npc.type_id)
    return out


PLACE_CITY = {p: (name, lo, hi) for name, lo, hi, places in shop_bands.CITIES for p in places}
AT = {p: stood(p) for p in sorted(PLACE_CITY)}
MEDICS = {t: kinds for t, kinds in shop_bands.SELLERS.items()
          if kinds and all(k in shop_bands.MED_KINDS for k in kinds)}
check("the medicine sellers of data/shop_bands.json sell medicine alone, and one currency only"
      " where the file says so: Джут gold, the grocers afro",
      ({t: k for t, k in shop_bands.SELLERS.items() if set(k) & set(shop_bands.MED_KINDS)
        and t not in MEDICS}, shop_bands.ONLY),
      ({}, {207: "gold", 5217: "afro", 81: "afro", 155: "afro"}))
STALLS = {(p, t): items.stock_for(t, p) for p, types in AT.items() for t in types}
wrong = {}
where = {}
for (p, t), stall in STALLS.items():
    if t not in MEDICS:
        continue
    where.setdefault(t, []).append(p)
    _name, lo, hi = PLACE_CITY[p]
    want = expect(MEDICS[t], lo, hi, shop_bands.only(t))
    own = [x for x in items.stock_for(t) if not line_med(x)]
    if stall != want + own:
        wrong[(p, t)] = (stall, want + own)
check("every medicine seller at every place of its city: its city's tiers of its kinds, the band's"
      " and the one under it, tier by tier, afro before (G), in its one currency where the file"
      " says only, then its own list -- worked out here from the catalogue", wrong, {})
check("  ..where they stand", where,
      {5211: [185], 5224: [186], 5217: [181], 5225: [26], 202: [62], 81: [35, 104],
       1206: [102], 1207: [102], 2180: [176], 1167: [187], 1168: [187], 207: [76, 195, 196],
       155: [50, 197], 1214: [103], 1215: [103], 2181: [159], 1221: [126], 1222: [126],
       880: [177]})
BTR, ROSA, VILKA, TUR, MAKS, SUPER = range(6073, 6079)
# The rounds of the wiki's article «Снабженец» (data/trader_stock_wiki.json, unbound: no
# type was tied to it), every calibre's columns as the wiki's links resolve them: the own
# list of the prisons' supply men, «Патроны и лекарства» by the original's rows.
with open(os.path.join(ROOT, "data", "trader_stock_wiki.json"), encoding="utf-8") as _fh:
    _SUPPLY_TITLES = json.load(_fh)["unbound"]["Снабженец"]["*"]
ROUNDS = []
for _title in _SUPPLY_TITLES:
    for _x in items.resolve_stock_title(_title):
        if _x in cat and items.root_of(_x) == items.AMMO and _x not in ROUNDS:
            ROUNDS.append(_x)
PINNED = {
    (26, 5225): [6055, 6061, BTR, 7100, 6056, 6062, ROSA, 7101],
    (176, 2180): [6055, 6061, BTR, 7100, 6056, 6062, ROSA, 7101, 6057, 6063, VILKA, 7102]
    + ROUNDS,
    (159, 2181): [6057, 6063, VILKA, 7102, 6058, 6064, TUR, 7103, 6059, 6065, MAKS, 7104]
    + ROUNDS,
    (177, 880): [6058, 6064, TUR, 7103, 6059, 6065, MAKS, 7104, 6060, 6066, SUPER, 7105]
    + ROUNDS,
    (185, 5211): [6055, 6061, BTR, 7100, 6056, 6062, ROSA, 7101,
                  6043, 6898, 6049, 6904, 6044, 6899, 6050, 6905, 2178, 2184],
    (181, 5217): [6043, 6898, 6049, 6044, 6899, 6050, 2178, 2184],
    (102, 1206): [6055, 6061, BTR, 7100, 6056, 6062, ROSA, 7101, 6057, 6063, VILKA, 7102],
    (102, 1207): [6043, 6898, 6049, 6904, 6044, 6899, 6050, 6905, 6045, 6900, 6051, 6906],
    (62, 202): [6055, 6061, BTR, 7100, 6056, 6062, ROSA, 7101, 6057, 6063, VILKA, 7102,
                6043, 6898, 6049, 6904, 6044, 6899, 6050, 6905, 6045, 6900, 6051, 6906],
    (35, 81): [6043, 6898, 6049, 6044, 6899, 6050, 6045, 6900, 6051, 1573, 334],
    (187, 1167): [6056, 6062, ROSA, 7101, 6057, 6063, VILKA, 7102, 6058, 6064, TUR, 7103],
    (187, 1168): [6044, 6899, 6050, 6905, 6045, 6900, 6051, 6906, 6046, 6901, 6052, 6907],
    (76, 207): [6905, 6906, 6907, ROSA, 7101, VILKA, 7102, TUR, 7103],
    (195, 207): [6906, 6907, 6908, VILKA, 7102, TUR, 7103, MAKS, 7104],
    (196, 207): [6907, 6908, 6909, TUR, 7103, MAKS, 7104, SUPER, 7105],
    (103, 1214): [6057, 6063, VILKA, 7102, 6058, 6064, TUR, 7103, 6059, 6065, MAKS, 7104],
    (103, 1215): [6045, 6900, 6051, 6906, 6046, 6901, 6052, 6907, 6047, 6902, 6053, 6908],
    (50, 155): [6045, 6900, 6051, 6046, 6901, 6052, 6047, 6902, 6053, 333],
    (126, 1221): [6058, 6064, TUR, 7103, 6059, 6065, MAKS, 7104, 6060, 6066, SUPER, 7105],
    (126, 1222): [6046, 6901, 6052, 6907, 6047, 6902, 6053, 6908, 6048, 6903, 6054, 6909],
}
check("the stalls pinned (DESIGN.md 2.2): Морис, Хасани, Люций, Магдалена, Снитке, Бартоломью,"
      " Торси, Мухсим, Джут at his three oases, Серхио, Фарюк, Донгола's grocer (the sack of"
      " beans of his article after), Киплер, Курт; the valley truck's Йонас and the prisons'"
      " supply men, «Патроны и лекарства», the battle line of their town (the supply men their"
      " article's rounds after)",
      {k: STALLS.get(k) for k in PINNED}, PINNED)
check("  ..the supply men's rounds: their own list (data/npcs.json), the same at the three"
      " prison yards, every calibre of the article, 49 types, each with a price",
      ([npcs.stock(t) == ROUNDS for t in (2180, 2181, 880)], len(ROUNDS),
       [x for x in ROUNDS if price(x) == (0, 0)], max(len(STALLS[k]) for k in PINNED)),
      ([True] * 3, 49, [], 61))
check("  ..Донгола's grocer's own list (data/npcs.json) is the sack of beans: the «Коробка"
      " вяленого мяса» of his article is the food of ten of 12_15 (6901), the band's, which the"
      " name tied to the valley's quest parcel 3481, a thing with no price no stall can sell",
      (npcs.stock(155), 6901 in STALLS[(50, 155)], 3481 in STALLS[(50, 155)],
       price(3481)), ([333], True, False, (0, 0)))
check("nothing on any stall of a city's place goes without a price: the client would show it and"
      " the stall refuse it in both currencies",
      sorted((p, t, x) for (p, t), s in STALLS.items() for x in s if price(x) == (0, 0)), [])
check("  ..Эрикесэм at the Caravan sells what Морис does at the market, Бартоломью at the port"
      " what he does at the market, Донгола's grocer at the new market what at the old",
      (STALLS[(186, 5224)] == STALLS[(185, 5211)], STALLS[(104, 81)] == STALLS[(35, 81)],
       STALLS[(197, 155)] == STALLS[(50, 155)]), (True, True, True))
check("  ..Джут: one type, three oases, three stalls, each its city's tiers in gold",
      len({tuple(STALLS[(p, 207)]) for p in (76, 195, 196)}), 3)

# --- 5. coverage -----------------------------------------------------------------------------
print()
print("coverage")
COVERED_CITIES = tuple(c[0] for c in shop_bands.CITIES)
on_sale = {}
for (p, t), stall in STALLS.items():
    for x in stall:
        if x in OF:
            on_sale.setdefault(PLACE_CITY[p][0], set()).add(x)
holes = {}
for name, lo, hi, _places in shop_bands.CITIES:
    if name not in COVERED_CITIES:
        continue
    want = set(expect(("combat_meds", "peace_meds"), lo, hi))
    if want - on_sale.get(name, set()) or on_sale.get(name, set()) - want:
        holes[name] = (sorted(want - on_sale.get(name, set())),
                       sorted(on_sale.get(name, set()) - want))
check("every city has its tiers on sale, every row of both lines in afro and in gold, and nothing"
      " else of them: the valley 0_3-4_7, Вади-Хальфа 0_3-8_11, Абри 4_7-12_15, Донгола"
      " 8_11-16_19 (open since 2026-10-13), Абу-Хамед 12_15-20 (closed, its stalls laid)",
      (holes, COVERED_CITIES),
      ({}, ("Нубийская долина", "Вади-Хальфа", "Абри", "Донгола", "Абу-Хамед")))
sellers_of = {}
for (p, t) in STALLS:
    if t in MEDICS and not shop_bands.only(t):
        for k in MEDICS[t]:
            sellers_of.setdefault(PLACE_CITY[p][0], set()).add(k)
check("  ..each city a seller of each line selling both currencies",
      {c: sorted(sellers_of.get(c, ())) for c in COVERED_CITIES},
      {c: ["combat_meds", "peace_meds"] for c in COVERED_CITIES})
TITLES = ("Боевая медицина", "Лекарства и еда", "Еда, вода, лекарства", "Аптекарь",
          "Еда и Медикаменты", "Продукты", "Торговец Едой", "Патроны и лекарства")


def title(t):
    parts = re.split(r"<br>", names.ALL.get(t, ""), flags=re.I)
    return parts[1].strip() if len(parts) > 1 else ""


check("every trader of a city's place the original titles a medicine or food seller is a seller"
      " of medicine in the file: Йонас «Патроны и лекарства» on the valley's truck and the"
      " Снабженец Хальфы of the prison yard among them, whose stalls stood empty, and Донгола's"
      " of its yard (2181, standing since his name came, 2026-10-13)",
      (sorted({(t, title(t)) for (p, t) in STALLS if title(t) in TITLES and t not in MEDICS}),
       sorted({t for (p, t) in STALLS if title(t) == "Патроны и лекарства"})),
      ([], [2180, 2181, 5225]))
check("  ..and no seller of medicine there opens an empty window",
      sorted((p, t) for (p, t), s in STALLS.items() if t in MEDICS and not s), [])

# --- 6. nothing out of the tiers -------------------------------------------------------------
print()
print("nothing out of the tiers")
check("no medicine of the two lines on any stall of a city's place out of its city's tiers",
      sorted((p, t, x) for (p, t), s in STALLS.items() for x in s if line_med(x)
             and (x not in OF or OF[x][1] not in tiers_of(*PLACE_CITY[p][1:]))), [])
check("  ..none on the stall of a trader of a city's place that is no medicine seller: Марат's"
      " and Шрам's at Абу-Хамед's station, whose lists the wiki's shifted links gave Киплер's"
      " and Курт's medicine, and Серхио's machine guns at Донгола's black market among them",
      sorted((p, t) for (p, t), s in STALLS.items() if t not in MEDICS
             and any(line_med(x) for x in s)), [])
check("  ..nor the May «Перевязочный Пакет» (26590) the name of Киплер's article tied to Марат"
      " (1219): his own list is empty, his stall the town's sets",
      (npcs.stock(1219), [x for x in STALLS[(126, 1219)] if cat[x][0] == items.HEAL]), ([], []))
check("  ..the currencies of only: Джут's stalls gold alone, the grocers' afro alone",
      sorted({(t, gold_only(x)) for (p, t), s in STALLS.items() if shop_bands.only(t)
              for x in s if line_med(x)}),
      [(81, False), (155, False), (207, True), (5217, False)])
check("no list of data/npcs.json of a seller of a city's band carries a medicine of the lines,"
      " the band gives it -- but Киплер's and Курт's, their articles', which they sell in Мероэ,"
      " no city's (decision 21)",
      sorted(t for t in shop_bands.SELLERS if any(line_med(x) for x in npcs.stock(t) or [])),
      [1221, 1222])

# --- 7. outside the cities -------------------------------------------------------------------
print()
print("outside the cities")
check("Иван Сидоркин (5706) at Заречье (429, no city's) sells his wiki list as it was, and with no"
      " place a medicine seller's stall is its own list",
      (items.stock_for(5706, 429), items.stock_for(5211), items.stock_for(207)),
      ([6048, 6065, 6899], [2178, 2184], []))
check("Киплер and Курт in Мероэ (58, off the map, no city's): their articles' lists of"
      " data/npcs.json, the battle medicine of 12_15-20 without the packs and the food, water"
      " and kits of the same tiers; at Абу-Хамед's station the town's tiers in their place",
      (items.stock_for(1221, 58), items.stock_for(1222, 58),
       items.stock_for(1221, 126) != items.stock_for(1221, 58)),
      ([6058, 6064, TUR, 6059, 6065, MAKS, 6060, 6066, SUPER],
       [6046, 6901, 6052, 6907, 6047, 6902, 6053, 6908, 6048, 6903, 6054, 6909], True))

# --- Донгола's black market and the names ----------------------------------------------------
print()
print("Донгола's black market and the names")
check("«Пулеметы и патроны» (1208) stands at Донгола's black market by data/placements.json and"
      " sells the town's machine guns, then the rounds of the wiki's article, which the shifted"
      " link had given Серхио; Серхио sells no gun",
      (1208 in AT[103], STALLS[(103, 1208)],
       [x for x in STALLS[(103, 1214)] if items.root_of(x) != items.HEAL]),
      (True, [24989, 24990, 25006, 25007, 6097, 6109, 6121, 6145, 6098, 6110, 6122, 6146], []))
check("the four medics of Донгола and Абу-Хамед and the machine-gun trader by the original's rows"
      " (data/orig_names_manual.json: 62161, 62162, 62165, 62166, 50655)",
      {t: names.ALL.get(t) for t in (1214, 1215, 1221, 1222, 1208)},
      {1214: "Серхио<br>Боевая медицина", 1215: "Фарюк<br>Лекарства и еда",
       1221: "Киплер<br>Боевая медицина", 1222: "Курт<br>Лекарства и еда",
       1208: "Пулеметы и патроны"})

# --- 8. no way to more afro ------------------------------------------------------------------


def sold_for(t):
    """What a stall pays for one whole thing (Inventory.sell), or 0 where it refuses."""
    si = items.params_of(t)
    if si.get("cost", 0) <= 0 or si.get("quest"):
        return 0
    return max(1, int(math.floor(si["cost"] / float(si.get("sell_num", 1)) * inventory.SMOD
                                 * si.get("sell_mod", 1))))


print()
print("no way to more afro")
ON = sorted({x for s in STALLS.values() for x in s if x in OF})
check("an afro medicine sells back for 0.7 of its price at most; a gold one for nothing, which"
      " the stall refuses (inventory.SELL_GOLD_ONLY off), a gold thing that never falls off a"
      " body",
      (sorted(t for t in ON if not gold_only(t) and sold_for(t) > 0.7 * price(t)[0]),
       sorted({(sold_for(t), combat.gold_item(t)) for t in ON if gold_only(t)}),
       inventory.SELL_GOLD_ONLY), ([], [(0, True)], False))
check("  ..one thing, one price, whoever sells it: no stall of a city sells a medicine cheaper"
      " than another buys it back",
      max(sold_for(t) - price(t)[0] for t in ON if not gold_only(t)) < 0, True)

# --- 9. the switches -------------------------------------------------------------------------
print()
print("the switches")
kept = shop_bands.MED_REACH
shop_bands.MED_REACH = 0
two = {name: sorted({OF[t][1] for t in shop_bands.goods(("combat_meds",), lo, hi)}, key=TIERS.index)
       for name, lo, hi, _p in shop_bands.CITIES}
shop_bands.MED_REACH = kept
check("MED_REACH 0: two tiers to a city, its band's own",
      two, {"Нубийская долина": ["0_3", "4_7"], "Вади-Хальфа": ["4_7", "8_11"],
            "Абри": ["8_11", "12_15"], "Донгола": ["12_15", "16_19"], "Абу-Хамед": ["16_19", "20"]})
bare = json.loads(json.dumps(BANDS_DOC))
for row in bare["sellers"].values():
    if isinstance(row, dict):
        row.pop("only", None)
check("  ..a file without only: Джут and the grocers in both currencies (Джут 24 at Абри's oasis)",
      (shop_bands.parse(bare)[3],
       len(shop_bands.goods(shop_bands.parse(bare)[2][207], 8, 12, None))), ({}, 24))
refused = []
for broken in ({"cities": [], "sellers": {"1": {"sells": ["pistols"], "only": "gold"}}},
               {"cities": [], "sellers": {"1": {"sells": ["peace_meds", "sets"], "only": "afro"}}},
               {"cities": [], "sellers": {"1": {"sells": ["peace_meds"], "only": "silver"}}},
               {"cities": [], "sellers": {"1": {"sells": [], "only": "gold"}}}):
    try:
        shop_bands.parse(broken)
        refused.append(broken)
    except RuntimeError:
        pass
check("  ..and a file giving only to a weapon or set seller, to a seller of no kind, or naming"
      " another currency stops the server", refused, [])

# --- 10. «Свежий хлеб» -----------------------------------------------------------------------
print()
print("«Свежий хлеб»")
bread = quests.get(482)
waters = [x for x in STALLS[(187, 1168)] if cat[x][1].startswith("Med_Pacific_Rest_")]
check("482 asks, beside its flour, a «Кожаный бурдюк» (6050), and Мухсим sells it at the port"
      " market of Абри, the cheapest water of his stall (decision 16)",
      ((6050, 1) in bread.wants(), 6050 in STALLS[(187, 1168)],
       min(waters, key=lambda x: price(x)[0])), (True, True, 6050))

# --- on the wire -----------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("medic", "secret")
_store.close()
CRED = accounts.credential("medic", "secret")

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


def buy(sess, index, code):
    """One purchase by the window's index: (acks, what came, afro, gold spent)."""
    before, had = purse(sess), bag(sess)
    got = run(sess, "ss_upd;s_status=%d;obj=x%x;param=1;" % (code, index))
    now = bag(sess)
    came = [t for t in set(now) if now.count(t) > had.count(t)]
    return acks(got), came, before[0] - purse(sess)[0], before[1] - purse(sess)[1]


def sell(sess, type_id):
    row = [r for r in server.STORE.items_of(sess.char_id) if r["type_id"] == type_id][0]
    before = purse(sess)
    got = run(sess, "ss_upd;s_status=2;obj=x%s;param=1;" % inventory.oid_of(row))
    return acks(got), type_id in bag(sess), purse(sess)[0] - before[0], purse(sess)[1] - before[1]


async def main():
    sess = server.Session(Writer(), "medic")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Medic@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 200000 20000@;group=0;")

    npc = goto(sess, 102)[1206]
    stall = window(sess, npc)
    check("102: Люций's window is his stall there, Вади-Хальфа's tiers 0_3-8_11 of battle medicine",
          (stall == items.stock_for(1206, 102), stall), (True, PINNED[(102, 1206)]))
    check("  ..the stall opens: one ack",
          acks(run(sess, "ss_create;s_type=1;target=%d;" % npc)), [0])
    check("  ..«Тряпичный бинт» (6056) for its 34 afro, one ack, no gold",
          buy(sess, stall.index(6056), inventory.UPD_BUY), ([0], [6056], 34, 0))
    check("  ..«Р.О.С.А. (G)» (6074) for its 0.02 ounces in gold, no afro",
          buy(sess, stall.index(ROSA), inventory.UPD_BUY_GOLD), ([0], [ROSA], 0, 2))
    check("  ..«20 доз В.И.Л.К.А. (G)» (7102) for 0.60 ounces",
          buy(sess, stall.index(7102), inventory.UPD_BUY_GOLD), ([0], [7102], 0, 60))
    check("  ..the wrong currency refused, nothing taken, nothing given: the bandage for gold, the"
          " injector for afro",
          (buy(sess, stall.index(6056), inventory.UPD_BUY_GOLD),
           buy(sess, stall.index(ROSA), inventory.UPD_BUY)),
          (([inventory.RES_REFUSED], [], 0, 0), ([inventory.RES_REFUSED], [], 0, 0)))
    check("  ..the bandage sold back for 0.7 of its price (23 afro), the injector not at all",
          (sell(sess, 6056), sell(sess, ROSA)),
          (([0], False, 23, 0), ([inventory.RES_REFUSED], True, 0, 0)))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")

    bought = {}
    for place in (76, 195):
        npc = goto(sess, place)[207]
        stall = window(sess, npc)
        run(sess, "ss_create;s_type=1;target=%d;" % npc)
        bought[place] = (stall == items.stock_for(207, place), buy(sess, 0, inventory.UPD_BUY_GOLD),
                         buy(sess, 0, inventory.UPD_BUY))
        run(sess, "ss_upd;s_status=0;obj=x0;param=1;")
    check("Джут: the first of his window is «Самоспас» at Абри's oasis and «Резерв» at Донгола's,"
          " each bought for its gold; for afro he sells nothing",
          bought,
          {76: (True, ([0], [6905], 0, 6), ([inventory.RES_REFUSED], [], 0, 0)),
           195: (True, ([0], [6906], 0, 11), ([inventory.RES_REFUSED], [], 0, 0))})


try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("med stalls OK")
