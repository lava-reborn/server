"""Лавки по уровню городов: every weapon and set seller of a city sells its
city's band, the ordinary and the gold version both.

The owner's order of 2026-10-10: «у всех продавцов оружия и сетов добавь
всё, что есть, но только по уровню городов: в Вади-Хальфе 8 уровень
потолок; чтобы была и голдовая версия, и обычная. Нижняя граница есть у
каждого города: старт от максимального для предыдущего города»
(data/shop_bands.json, server/shop_bands.py).

In process:
  1. the chain of cities: Нубийская долина 0-4, Вади-Хальфа 4-8, Абри 8-12,
     Донгола 12-16, Абу-Хамед 16-20, each floor the ceiling of the city
     before it -- held by the file's shape, so moving a ceiling moves the
     next floor;
  2. who sells: the sellers of the file stand in its cities' places, and no
     trader standing there that is not one offers a weapon line, a knife or
     a set piece of its own; one that is not keeps its own list there whole;
  3. what: each seller, at each place of its city, sells exactly the band's
     things of its kinds -- worked out here from the catalogue on its own,
     not through shop_bands -- the ordinary and the gold one both, and after
     them its own list without weapons or set pieces; a seller of no kinds
     keeps its own list cut to the band; the counts, city by city, pinned;
  4. nothing out of band on any of those stalls, nothing excluded (no (P),
     no modification, no quest or (Q) thing, no designed stand-in), every
     thing priced in its own currency and named (name and description ids
     in names.ALL: an id the preload lacks sends the player to the login
     screen), the order a window reads well; every gun a city sells has a
     round it chambers on sale in that city;
  5. the stall a size the client draws: no stall of a city longer than 64,
     and its userInfo_Trader frame under 4 KiB;
  6. the gold pouches (the owner's «добавь еще голдовые подсумки»,
     2026-10-11): the seven base belts and their (G) copies, named, shown and
     drawn; the three linked that day with their articles' numbers, all seven
     against the mirror's tables; every stall that sells an ordinary one
     sells its (G) right after it, the pouch sellers pinned; a (G) one no
     way to afro or gold; tools/npc_editor.py shows the (G) apart and its
     Save, untouched or after an edit, never writes them into data/npcs.json
     (a copy of it), so an empty GOLD_POUCHES takes them off every stall.
Then one session, in process, on the wire: the same trader type (5161)
offers each city's band at its markets, the purchase index takes what the
window of that place shows, a gold thing is paid in gold and an ordinary one
in afro with one cmdAck each, and the wrong currency is refused; Ваккас
sells a (G) belt for gold alone and does not buy it back.

The medicine sellers of the same file (combat_meds, peace_meds, the owner's
«чтобы везде всё было по уровням» of 2026-10-12) are server/test_med_stalls'
to pin: here they are sellers like the others, with no weapon or set piece
on their stalls, and their medicine is neither a seller's band nor its own
list.

    LAVA_RES=.../res python3 server/test_stall_bands.py
"""
import asyncio
import functools
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DB = os.path.join(tempfile.mkdtemp(), "stall_bands.db")
os.environ["LAVA_DB"] = DB
os.environ["LAVA_CHEATS"] = "1"
for _knob in ("LAVA_LOC", "LAVA_START"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import protocol  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import shop_bands  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "лавки по уровню городов: оружие и комплекты полосы города, обычные и (G)"

OFF = items.STRING_ID_OFFSET
cat = items.catalogue()
BY_NAME = {n: t for t, (_r, n) in cat.items()}
SLOTS = ("helm", "shirt", "armor", "pants", "boots")
with open(os.path.join(ROOT, "data", "sets.json"), encoding="utf-8") as _fh:
    SETS_DOC = json.load(_fh)["sets"]
with open(os.path.join(ROOT, "data", "shop_bands.json"), encoding="utf-8") as _fh:
    BANDS_DOC = json.load(_fh)

# --- 1. the chain ------------------------------------------------------------------------
print("the chain of cities")
OWNER = [("Нубийская долина", 0, 4), ("Вади-Хальфа", 4, 8), ("Абри", 8, 12),
         ("Донгола", 12, 16), ("Абу-Хамед", 16, 20)]
check("the owner's bands, each floor the ceiling of the city before (Вади-Хальфа's"
      " ceiling 8)", [c[:3] for c in shop_bands.CITIES], OWNER)
check("  ..the file writes ceilings only, the floors are the rule's",
      [sorted(k for k in row if not k.startswith("_")) for row in BANDS_DOC["cities"]],
      [["name", "places", "top"]] * len(OWNER))
moved = json.loads(json.dumps(BANDS_DOC))
moved["cities"][1]["top"] = 9
check("  ..so a ceiling moved (Вади-Хальфа 9) moves the next floor (Абри 9-12)",
      [c[:3] for c in shop_bands.parse(moved)[0]][1:3], [("Вади-Хальфа", 4, 9), ("Абри", 9, 12)])
bad = []
for broken in ({"cities": [{"name": "А", "top": 8, "places": []},
                           {"name": "Б", "top": 4, "places": []}]},
               {"cities": [{"name": "А", "top": 4, "places": [1]},
                           {"name": "Б", "top": 8, "places": [1]}]},
               {"cities": [], "sellers": {"1": {"sells": ["swords"]}}}):
    try:
        shop_bands.parse(broken)
        bad.append(broken)
    except RuntimeError:
        pass
check("  ..and a file that breaks it (a ceiling below the floor, a place in two cities,"
      " a kind nobody sells) stops the server", bad, [])
unsorted = shop_bands._WARES is None
items.preload()
check("the server sorts the bands' wares out at start (items.preload), not at the first"
      " stall a player opens: built inside a handler, they held the loop for over a second",
      (unsorted, shop_bands._WARES is not None), (True, True))

# --- 2. who sells ------------------------------------------------------------------------
print()
print("who sells")
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
WHERE = {}
for p, types in AT.items():
    for t in types:
        if t in shop_bands.SELLERS:
            WHERE.setdefault(t, []).append(p)
check("every seller of the file stands in its cities' places",
      sorted(t for t in shop_bands.SELLERS if t not in WHERE), [])
check("  ..where it stands: the clothing markets' 5161 and Хан Сэлл in several cities",
      {t: WHERE[t] for t in (5161, 2391, 5212, 1200, 1225, 1229, 1216)},
      {5161: [378, 467, 469], 2391: [41, 187, 445, 446], 5212: [185], 1200: [102],
       1225: [76], 1229: [195], 1216: [126]})
LINE = re.compile(r"^(pistols|shotgun|sub_machine_guns|assault_rifle|rifle|machine_gun)"
                  r"_([1-9]\d*)_lvl_(\d+)(_gold)?$")
KNIFE = re.compile(r"^knife_lvl(\d+)_(A|G)$")
PIECES = {s["members"][slot]["type"]: s for s in SETS_DOC.values() for slot in SLOTS
          if slot in s["members"]}


def weapon_or_piece(t):
    """A gun or knife of any kind, or a piece of any set: what the bands decide."""
    return items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM) or t in PIECES


def line_ware(t):
    """A gun of a mass line, a knife of the series, or a ladder piece."""
    name = cat[t][1]
    return bool(LINE.match(name) or KNIFE.match(name) or t in PIECES)


def med_line(t):
    """A medicine of the two lines the bands sell by tier (Med_Battle_, Med_Pacific_):
    server/test_med_stalls' to pin, neither a band of this suite nor an own list."""
    return cat[t][0] == items.HEAL and cat[t][1].startswith(("Med_Battle_", "Med_Pacific_"))


check("no trader of a city's place that is no seller offers a gun of a line, a knife or a"
      " set piece of its own",
      sorted((p, t) for p, types in AT.items() for t in types
             if t not in shop_bands.SELLERS and any(line_ware(x) for x in items.stock_for(t))),
      [])
check("  ..and no seller's own list in data/npcs.json holds one: they come from the band",
      sorted(t for t, kinds in shop_bands.SELLERS.items() if kinds and npcs.stock(t)
             and any(weapon_or_piece(x) for x in npcs.stock(t))), [])
LEFT_ALONE = sorted((p, t) for p, types in AT.items() for t in types
                    if t not in shop_bands.SELLERS)
# The bouquets: «Букет» (gift_girl_4) in Абри's slums and Абу-Хамед's living quarter.
# Донгола's black market had a third, «Цветы для любимого» (stv_flowers_m_g), on Фарюк's
# (1215) list by a shifted link of the wiki; he sells Донгола's medicine since 2026-10-12.
LEFT_HOLDING = [(127, 1968), (255, 1962)]
check("  ..and every trader of a city's place that is no seller sells its own list there, as"
      " anywhere: the bands take nothing off it (the flower sellers keep their bouquets,"
      " a cold arm to the client)",
      [(p, t) for p, t in LEFT_ALONE if items.stock_for(t, p) != items.stock_for(t)], [])
check("  ..not idly: these of them hold a cold arm or a gun of no line, which a cut would take",
      sorted((p, t) for p, t in LEFT_ALONE if any(shop_bands.band_ware(x)
                                                  for x in items.stock_for(t))), LEFT_HOLDING)

# --- 3. what -----------------------------------------------------------------------------
print()
print("what each sells")
KIND_LINE = {"pistols": "pistols", "shotguns": "shotgun", "smgs": "sub_machine_guns",
             "rifles": "rifle", "assault_rifles": "assault_rifle", "machine_guns": "machine_gun"}
WIKI = items.wiki()


def level_of(t):
    """The highest «Необходимые навыки» of the frame: the level the client shows."""
    return max((items.params_of(t) or {}).get("need_skills") or [0])


def gold_of(t):
    p = items.params_of(t)
    return p["g_cost"] > 0


@functools.lru_cache(maxsize=None)
def expect(kind, lo, hi):
    """The band's things of a kind, worked out from the catalogue and data/sets.json;
    nothing for a kind of medicine, which server/test_med_stalls works out."""
    out = set()
    if kind in shop_bands.MED_KINDS:
        return out
    if kind == "sets":
        for s in SETS_DOC.values():
            if s["variant"] in ("A", "G") and lo <= s["level"] <= hi:
                out |= {s["members"][slot]["type"] for slot in SLOTS}
        return out
    for t, (root, name) in cat.items():
        if kind == "knives":
            m = KNIFE.match(name)
            gold = bool(m) and m.group(2) == "G"
        else:
            m = LINE.match(name)
            m = m if m and m.group(1) == KIND_LINE[kind] else None
            gold = bool(m) and bool(m.group(4))
        if not m or t not in WIKI:
            continue
        p = items.params_of(t)
        priced = (p["g_cost"] > 0 and not p["cost"]) if gold else (p["cost"] > 0 and not p["g_cost"])
        text = names.ALL.get(OFF + t, "")
        if not priced or items.premium(t) or p.get("quest") or quests.lent(t) \
                or text == name or "(Q)" in text:
            continue
        if lo <= level_of(t) <= hi:
            out.add(t)
    return out


stalls = {}       # (place, trader) -> its stall there
wrong, gone_own = {}, {}
for t, places in sorted(WHERE.items()):
    kinds = shop_bands.SELLERS[t]
    own = items.stock_for(t)
    for p in places:
        _name, lo, hi = PLACE_CITY[p]
        stall = items.stock_for(t, p)
        stalls[(p, t)] = stall
        band_part = [x for x in stall if weapon_or_piece(x)]
        rest = [x for x in stall if not weapon_or_piece(x) and not med_line(x)]
        if kinds:
            want = set()
            for k in kinds:
                want |= expect(k, lo, hi)
            if sorted(band_part) != sorted(want) or len(band_part) != len(set(band_part)):
                wrong[(p, t)] = (sorted(set(band_part) - want), sorted(want - set(band_part)))
            if band_part != stall[:len(band_part)] or \
                    rest != [x for x in own if not weapon_or_piece(x) and not med_line(x)
                             and not items.premium(x)] or rest != stall[len(stall) - len(rest):]:
                gone_own[(p, t)] = rest
        else:
            cut = [x for x in own if not weapon_or_piece(x) or lo <= level_of(x) <= hi]
            if stall != [x for x in cut if not items.premium(x)]:
                wrong[(p, t)] = ("own list cut", stall)
check("each seller at each of its city's places: exactly the band's things of its kinds,"
      " the ordinary and the gold one both (a seller of no kinds: its own list cut)", wrong, {})
check("  ..first, and its own list after them without weapons or set pieces (rounds,"
      " blueprints, pouches)", gone_own, {})


def ag(stall):
    """(ordinary, gold) of the weapons and set pieces on a stall."""
    part = [x for x in stall if weapon_or_piece(x)]
    return (sum(1 for x in part if not gold_of(x)), sum(1 for x in part if gold_of(x)))


# The medicine sellers (2026-10-12) hold no weapon or set piece: (0, 0) each -- the
# «Патроны и лекарства» of the valley's truck (5225) and of the prison yards (2180, 2181, 880)
# among them.
COUNTS = {
    "Нубийская долина": {5212: (9, 8), 5221: (9, 8), 5222: (4, 2), 5213: (15, 15), 5223: (15, 15),
                         1187: (6, 0), 5211: (0, 0), 5224: (0, 0), 5217: (0, 0), 5225: (0, 0)},
    "Вади-Хальфа": {1200: (4, 4), 1201: (10, 10), 1202: (3, 3), 1203: (2, 2), 1152: (3, 3),
                    1224: (19, 19), 1205: (15, 15), 1204: (15, 15), 650: (15, 15), 2391: (0, 7),
                    1206: (0, 0), 1207: (0, 0), 202: (0, 0), 81: (0, 0), 2180: (0, 0)},
    "Абри": {1159: (2, 2), 1161: (4, 4), 1163: (10, 10), 1162: (10, 10), 1164: (3, 3),
             1225: (26, 26), 1166: (10, 10), 1165: (10, 10), 5160: (10, 10), 5161: (10, 10),
             1168: (0, 0), 2391: (0, 6), 1167: (0, 0), 207: (0, 0)},
    # The black market's machine guns at «Пулеметы и патроны» (1208), whom the wiki's article
    # puts there; Серхио (1214), who had his list by a shifted link, sells battle medicine.
    "Донгола": {1209: (10, 10), 1210: (5, 5), 1211: (6, 6), 1153: (3, 3), 1208: (2, 2),
                1229: (25, 25), 1213: (20, 20), 1233: (20, 20), 5161: (20, 20), 2391: (0, 8),
                207: (0, 0), 1214: (0, 0), 1215: (0, 0), 155: (0, 0), 2181: (0, 0)},
    # Киплер (1221) sells battle medicine; the town's knives are Шрам's (2274) alone.
    "Абу-Хамед": {1216: (9, 9), 1217: (3, 3), 1218: (4, 4), 2274: (3, 3), 1221: (0, 0),
                  1223: (20, 20), 1219: (20, 20), 5161: (20, 20), 2391: (0, 9), 207: (0, 0),
                  1222: (0, 0), 880: (0, 0)},
}
got = {}
for (p, t), stall in stalls.items():
    got.setdefault(PLACE_CITY[p][0], {})[t] = ag(stall)
check("the counts, (ordinary, gold), city by city: the valley's pistols 0-4 (Самострел alone"
      " has no gold line), Вади-Хальфа's guns and sets 4-8, Абри's to Абу-Хамед's",
      got, COUNTS)
pairs = []
for (p, t), stall in stalls.items():
    if not shop_bands.SELLERS[t]:
        continue
    on = set(stall)
    for x in on:
        name = cat[x][1]
        twin = None
        if LINE.match(name):
            twin = name[:-5] if name.endswith("_gold") else name + "_gold"
        elif KNIFE.match(name):
            twin = name[:-1] + ("A" if name.endswith("G") else "G")
        other = BY_NAME.get(twin) if twin else None
        if other and other in expect(shop_bands.wares()[x][0], *PLACE_CITY[p][1:]) \
                and other not in on:
            pairs.append((p, t, x))
check("  ..both versions wherever both are shop things: no ordinary gun or knife without"
      " its gold one on the stall, nor the other way", pairs, [])
check("  ..the one gun of a seller's band with no gold line: Самострел (its (G) line has no"
      " numbers)",
      sorted({x for (p, t), s in stalls.items() if shop_bands.SELLERS[t] for x in s
              if weapon_or_piece(x) and not gold_of(x) and LINE.match(cat[x][1])
              and not any(cat[y][1] == cat[x][1] + "_gold" for y in s)}), [25562])

# --- 4. nothing out of band, nothing excluded ------------------------------------------
print()
print("nothing out of band, nothing excluded")
check("no weapon or set piece out of its city's band on any stall of a city's place",
      sorted((p, t, x, level_of(x)) for (p, t), s in stalls.items() for x in s
             if weapon_or_piece(x) and not PLACE_CITY[p][1] <= level_of(x) <= PLACE_CITY[p][2]),
      [])
ALL_ON = sorted({x for s in stalls.values() for x in s})
BAND_ON = sorted({x for (p, t), s in stalls.items() if shop_bands.SELLERS[t]
                  for x in s if weapon_or_piece(x)})
check("  ..no premium, no modification, no quest or lent thing, no (Q), no designed stand-in"
      " on a seller's band", [x for x in BAND_ON if items.premium(x) or craft.mod_of(x)
                              or items.params_of(x).get("quest") or quests.lent(x)
                              or "(Q)" in names.ALL.get(OFF + x, "")
                              or (x not in PIECES and x not in WIKI)], [])
check("  ..each priced in its own currency: afro alone for the ordinary, gold alone for the"
      " (G) -- never both, which the stall would buy back for afro",
      [x for x in BAND_ON if bool(items.params_of(x)["cost"]) == bool(items.params_of(x)["g_cost"])],
      [])
check("  ..the gold ones are gold things: they never fall off a body",
      sorted({__import__("combat").gold_item(x) for x in BAND_ON if gold_of(x)}), [True])
unnamed, undescribed = [], []
for x in ALL_ON:
    p = items.params_of(x)
    if OFF + x not in names.ALL or names.ALL[OFF + x] == cat[x][1]:
        unnamed.append(x)
    if isinstance(p.get("desc"), int) and p["desc"] not in names.ALL:
        undescribed.append(x)
check("every thing on every stall of a city's place has a name of its own in names.ALL, and"
      " its description id is there too", (unnamed, undescribed), ([], []))
order = []
for (p, t), s in stalls.items():
    kinds = shop_bands.SELLERS[t]
    if not kinds:
        continue
    part = [x for x in s if weapon_or_piece(x)]
    keys = [(kinds.index(shop_bands.wares()[x][0]), level_of(x)) for x in part]
    if keys != sorted(keys):
        order.append((p, t, "kind or level"))
    for i, x in enumerate(part):
        name = cat[x][1]
        if name.endswith("_gold") or (KNIFE.match(name) and name.endswith("_G")):
            twin = name[:-5] if name.endswith("_gold") else name[:-1] + "A"
            if i and cat[part[i - 1]][1] != twin and any(cat[y][1] == twin for y in part):
                order.append((p, t, x))
    pieces = [x for x in part if x in PIECES]
    for i in range(0, len(pieces), 5):
        five = pieces[i:i + 5]
        s5 = PIECES[five[0]]
        if [PIECES[y] is s5 for y in five] != [True] * 5 or \
                five != [s5["members"][slot]["type"] for slot in SLOTS]:
            order.append((p, t, "set", five))
        if s5["variant"] == "G" and (i < 5 or PIECES[pieces[i - 5]]["level"] != s5["level"]
                                     or PIECES[pieces[i - 5]]["variant"] != "A"):
            order.append((p, t, "G set before its A", five))
check("the order: kind by kind as the seller lists them, by level within; an ordinary gun"
      " or knife right before its (G); a set whole, helm to boots, its A before its G", order, [])

# A gun takes only the rounds of its comp_array: the client checks it before it asks to
# load (FireArm.compare) and the server again (inventory.py). A city that sells a gun
# sells, at some stall of its places, a round it takes.
ROUNDS_IN, GUNS_IN = {}, {}
for p, types in AT.items():
    city_name = PLACE_CITY[p][0]
    for t in types:
        for x in items.stock_for(t, p):
            if items.root_of(x) == items.AMMO:
                ROUNDS_IN.setdefault(city_name, set()).add(x)
            elif items.root_of(x) == items.FIRE_ARM:
                GUNS_IN.setdefault(city_name, set()).add(x)
check("every gun on a stall of a city has a round it chambers on sale in that city: Абри's"
      " and Донгола's 9 mm sub-machine guns and 12-bore shotguns, Донгола's АС Вал, and Хан"
      " Сэлл's ПП-19-01 Витязь at Абу-Хамед's port too since 2026-10-12, whose 9 mm no stall of"
      " the city sold before the prison yard's supply man (880) sold every calibre of his"
      " article «Снабженец»",
      sorted((c, x) for c, guns in GUNS_IN.items() for x in guns
             if not set(items.params_of(x)["comp_array"]) & ROUNDS_IN.get(c, set())),
      [])
check("  ..and the band's guns of the class stalls, which the wiki had sell other rounds, find"
      " theirs at the stall itself: 9 mm at Абри's and Донгола's «Пистолет-пулеметы и патроны»,"
      " 12-bore at Абри's «Дробовики и патроны»",
      sorted((p, t, x) for (p, t), s in stalls.items() if t in (1163, 1211, 1162)
             for x in s if items.root_of(x) == items.FIRE_ARM
             and not set(items.params_of(x)["comp_array"]) & set(s)), [])

# --- 5. the size of a stall --------------------------------------------------------------
print()
print("the size of a stall")
biggest = max(stalls.items(), key=lambda kv: len(kv[1]))
frame = max(len(protocol.frame("userInfo_Trader", id=1, name=t, type_list=s, pmod=1, smod=0.7,
                               rmod=0.3)) for (p, t), s in stalls.items())
check("no stall of a city longer than 64 things (Локсли's 51 was the longest the live game"
      " drew before), and its frame under 4 KiB: the longest the prison yards' supply men's"
      " (2026-10-12), 61, their town's battle line and the 49 rounds of their article -- 880"
      " of Абу-Хамед's the first of the three by type; of the weapon stalls 1229 at Донгола's"
      " oasis, 53",
      (len(biggest[1]) <= 64, frame < 4096, biggest[0], len(biggest[1]),
       max((len(s), (p, t)) for (p, t), s in stalls.items() if t not in (880, 2180, 2181))),
      (True, True, (177, 880), 61, (53, (195, 1229))))
check("  ..and every thing on them a type the client has (objects.xml), so it draws an icon",
      [x for x in ALL_ON if x not in cat], [])
check("the place decides: 5161 sells Абри's 8-12, Донгола's 12-16 and Абу-Хамед's 16-20, so"
      " a purchase index taken at another place would buy another thing",
      (sorted({level_of(x) for x in stalls[(378, 5161)]}), sorted({level_of(x) for x in stalls[(469, 5161)]}),
       sorted({level_of(x) for x in stalls[(467, 5161)]}), stalls[(378, 5161)][0] != stalls[(469, 5161)][0]),
      ([8, 10], [13, 14, 15, 16], [16, 18, 19, 20], True))
check("  ..outside the cities' places, and with no place at all, a stall is its own list",
      (items.stock_for(2391, 287) == items.stock_for(2391), items.stock_for(5161, None),
       items.stock_for(1201)[:2]), (True, [], [25938, 25951]))

# --- 6. the gold pouches -----------------------------------------------------------------
# The owner's «добавь еще голдовые подсумки» (2026-10-11): the base belt of each weapon
# class, the seven lines of the original's run of belts (texts.xml 47822-47856), and its
# gold copy; every stall that sells the ordinary one sells the (G) right after it.
print()
print("the gold pouches")
POUCH_LINES = {"belt_pistols": "Подсумки пистолетные", "belt_shotguns": "Подсумки охотника",
               "belt_rifles": "Подсумки снайпера", "belt_sub_machineguns": "Подсумки спецназовца",
               "belt_knife": "Подсумки рукопашника", "belt_assault_rifles": "Подсумки автоматчика",
               "belt_machineguns": "Подсумки пулемётчика"}
POUCHES = items.GOLD_POUCHES
GOLD_POUCH = set(POUCHES.values())
check("items.GOLD_POUCHES: the seven base belts of objects.xml, each to its _g copy",
      sorted((cat[a][1], cat[g][1]) for a, g in POUCHES.items()),
      sorted((n, n + "_g") for n in POUCH_LINES))
check("  ..named by the original, the gold copy with its (G)",
      {cat[t][1]: names.text(OFF + t) for pair in POUCHES.items() for t in pair},
      dict([(n, ru) for n, ru in POUCH_LINES.items()]
           + [(n + "_g", ru + " (G)") for n, ru in POUCH_LINES.items()]))
PROBLEMS = {}
for t in sorted(set(POUCHES) | GOLD_POUCH):
    info = items.static_info(t)
    p = info[1] if info else {}
    why = []
    if not info or info[0] != "ss_si_wear":
        why.append("frame")
    if not names.known(p.get("name")) or names.text(p.get("name")) == cat[t][1]:
        why.append("name")
    if p.get("desc") != "" and not names.known(p.get("desc")):
        why.append("desc")
    if not os.path.isfile(os.path.join(world.RES, "classes", "WearItem", cat[t][1], "ico.swf")):
        why.append("icon")
    if why:
        PROBLEMS[t] = why
check("  ..each a stall can show: its ss_si_wear, its name and description ids in names.ALL"
      " (an id the preload lacks sends the player to the login screen), its icon", PROBLEMS, {})


def unpacked(p, key, n):
    return inventory.unpacked(p.get(key + "_m"), p.get(key), n)


def numbers(t):
    """The numbers the article's table gives a belt, as the frame carries them."""
    p = items.params_of(t)
    return (p["cost"], p["g_cost"], p["armor_class"], p["max_break_abs"], p["weight"],
            p["exchang"], unpacked(p, "need_attribs", 5), unpacked(p, "bonus_attribs", 5),
            unpacked(p, "bonus_skills", 5), unpacked(p, "bonus_specs", 8))


NEED = [0, 0, 5, 0, 0]                 # «Необходимые атрибуты: Телосложение 5»
NO5, NO8 = [0] * 5, [0] * 8
SPEC = lambda i: [1 if k == i else 0 for k in range(8)]   # noqa: E731
ATTR = lambda i: [1 if k == i else 0 for k in range(5)]   # noqa: E731
# The three linked on 2026-10-11 (data/wiki_links.py MANUAL), by their articles: «Базовая
# цена 50000 Афро / 10 G», «100000 Афро / 20 G», «40000 Афро / 8 G»; «Уровень брони 5»,
# «Износ 300 / 600», «Вес 700 г», «Допустимость обмена Да / Нет»; the specialisation of
# both columns -- «Автоматы 1», «Ручные пулемёты 1»; «Рукопашный бой» in the A column of
# «Подсумки рукопашника» and «Режущие оружие» in its G, as the article writes them, with
# «Ближний бой 1» of the skills in both -- and the G column's attribute: «Ловкость 1»,
# «Сила 1», «Ловкость 1». Prices in gold are hundredths of an ounce.
check("the three belts linked on 2026-10-11 carry their articles' numbers: (cost, g_cost,"
      " armour, wear, weight, exchang, need, attributes, skills, specialisations)",
      {t: numbers(t) for t in (3577, 3599, 3580, 3602, 5613, 5614)},
      {3577: (50000, 0, 5, 300, 700, 1, NEED, NO5, NO5, SPEC(4)),
       3599: (0, 1000, 5, 600, 700, 0, NEED, ATTR(1), NO5, SPEC(4)),
       3580: (100000, 0, 5, 300, 700, 1, NEED, NO5, NO5, SPEC(6)),
       3602: (0, 2000, 5, 600, 700, 0, NEED, ATTR(0), NO5, SPEC(6)),
       5613: (40000, 0, 5, 300, 700, 1, NEED, NO5, ATTR(0), SPEC(0)),
       5614: (0, 800, 5, 600, 700, 0, NEED, ATTR(1), ATTR(0), SPEC(1))})
with open(os.path.join(ROOT, "data", "wiki_items.json"), encoding="utf-8") as _fh:
    WIKI_PAGES = json.load(_fh)
off_page = []
for title, (a, g) in (("Подсумки автоматчика", (3577, 3599)),
                      ("Подсумки пулеметчика", (3580, 3602)),
                      ("Подсумки рукопашника", (5613, 5614)),
                      ("Подсумки пистолетные", (3582, 3604)),
                      ("Подсумки охотника", (3581, 3603)),
                      ("Подсумки снайпера", (3578, 3600)),
                      ("Подсумки спецназовца", (3579, 3601))):
    rows = WIKI_PAGES[title]["tables"][0]["sections"]["общие"]
    price = rows["Базовая цена"]
    page = [(price[0]["afro"], 0, rows["Износ"][0], rows["Вес"][0], rows["Уровень брони"][0]),
            (0, int(round(price[1]["g"] * 100)), rows["Износ"][1], rows["Вес"][1],
             rows["Уровень брони"][1])]
    frame = [(items.params_of(t)["cost"], items.params_of(t)["g_cost"],
              items.params_of(t)["max_break_abs"], items.params_of(t)["weight"],
              items.params_of(t)["armor_class"]) for t in (a, g)]
    if frame != page:
        off_page.append((title, frame, page))
check("  ..and all seven lines, read off the mirror's tables (data/wiki_items.json) on their"
      " own: the A column's afro price on the ordinary, the G column's gold one on the (G),"
      " wear, weight and armour", off_page, [])

TRADERS = sorted(set(items.stock_table()) | set(npcs.STOCK))
LISTS = [("own", t, items.stock_for(t)) for t in TRADERS] + \
    [(p, t, items.stock_for(t, p)) for p, types in sorted(AT.items()) for t in types]
unpaired = []
for where, t, s in LISTS:
    for i, x in enumerate(s):
        if x in POUCHES and s[i + 1:i + 2] != [POUCHES[x]]:
            unpaired.append((where, t, x))
        if x in GOLD_POUCH and (not i or POUCHES.get(s[i - 1]) != x):
            unpaired.append((where, t, x))
    if len(set(s)) != len(s):
        unpaired.append((where, t, "twice"))
check("every stall that sells an ordinary pouch sells its (G) right after it -- every trader's"
      " own list and every stall of a city's place -- and no (G) pouch stands alone",
      unpaired, [])
POUCH_STALLS = {(where, t): [x for x in s if x in POUCHES or x in GOLD_POUCH]
                for where, t, s in LISTS if any(x in POUCHES for x in s)}
check("  ..the pouch sellers and their pouches: Ваккас (Вади-Хальфа, 102) his four and"
      " «Подсумки рукопашника», which his article lists; Алима (Абри, 187: 1165 by her own"
      " list since 2026-10-12, the wiki's link had given it to the driver Луиджи, 1179) and"
      " Галия (Донгола, 103) what their articles list, «автоматчика», «пулеметчика» and"
      " «рукопашника» among them since their link",
      POUCH_STALLS,
      {("own", 1165): [3577, 3599, 3581, 3603, 5613, 5614, 3578, 3600, 3579, 3601],
       ("own", 1204): [3582, 3604, 3581, 3603, 3579, 3601, 3578, 3600, 5613, 5614],
       ("own", 1213): [3577, 3599, 3580, 3602, 5613, 5614, 3578, 3600, 3579, 3601],
       (102, 1204): [3582, 3604, 3581, 3603, 3579, 3601, 3578, 3600, 5613, 5614],
       (103, 1213): [3577, 3599, 3580, 3602, 5613, 5614, 3578, 3600, 3579, 3601],
       (187, 1165): [3577, 3599, 3581, 3603, 5613, 5614, 3578, 3600, 3579, 3601]})
check("items.with_gold_pouches: a (G) already on a list moves after its ordinary one, a (G)"
      " without it stays put, nothing else moves, and twice is once",
      (items.with_gold_pouches([3604, 7, 3582, 8]), items.with_gold_pouches([9, 3603, 10]),
       items.with_gold_pouches(items.with_gold_pouches([3577, 11, 5613]))),
      ([7, 3582, 3604, 8], [9, 3603, 10], [3577, 3599, 11, 5613, 5614]))
import barter  # noqa: E402
import combat  # noqa: E402
import mail  # noqa: E402
check("a (G) pouch is no way to afro or gold: priced in gold alone, a gold thing that never"
      " falls off a body, cannot change hands (barter, post, auction: barter.tradable),"
      " and no stall buys it back (cost 0, inventory.SELL_GOLD_ONLY off)",
      (sorted({(items.params_of(g)["cost"], items.params_of(g)["g_cost"] > 0, combat.gold_item(g),
                combat.drops_on_death(g), barter.tradable(g), mail.postable(g))
               for g in GOLD_POUCH}), inventory.SELL_GOLD_ONLY),
      ([(0, True, True, False, False, False)], False))
check("  ..an ordinary one sells back for at most 0.7 of what it cost (inventory.SMOD), and"
      " is an afro thing that may change hands",
      sorted({(items.params_of(a)["cost"] > 0, items.params_of(a)["g_cost"], inventory.SMOD
               * items.params_of(a).get("sell_mod", 1) <= 0.7, combat.gold_item(a),
               barter.tradable(a)) for a in POUCHES}),
      [(True, 0, True, False, True)])
check("  ..no quest gives or takes a pouch, so none turns one into gold or afro",
      sorted((q.type, t) for q in quests.QUESTS.values() for _f, t in q.things()
             if t in POUCHES or t in GOLD_POUCH), [])
check("  ..and none of them is a weapon or set piece: no band moves them (shop_bands)",
      [t for t in sorted(set(POUCHES) | GOLD_POUCH) if shop_bands.band_ware(t)], [])

# The (G) copies are the rule's, like a city's band: tools/npc_editor.py shows the trader's
# own list (items.own_stock) and the copies apart, and its Save never writes them into
# data/npcs.json -- otherwise the first untouched Save on its default place (102, Ваккас)
# froze them there, and an empty GOLD_POUCHES no longer took them off his stall.
sys.path.append(os.path.join(ROOT, "tools"))
import npc_editor  # noqa: E402

NPCS_FILE = os.path.join(ROOT, "data", "npcs.json")
with open(NPCS_FILE, encoding="utf-8") as _fh:
    NPCS_DOC = json.load(_fh)
npc_editor.OUT = os.path.join(tempfile.mkdtemp(), "npcs.json")
with open(npc_editor.OUT, "w", encoding="utf-8") as _fh:
    json.dump(NPCS_DOC, _fh, ensure_ascii=False)
_kept = (npcs.NAMES, npcs.STOCK)


def page_payload(loc_id, edit=None):
    """What the page's «Сохранить» posts for a place, as its JS builds it; edit(n) is
    the owner's touch before the click (none: an untouched Save)."""
    shown = npc_editor.occupants(loc_id)
    for n in shown["npcs"]:
        if edit:
            edit(n)
    return shown, {"npcs": [{"type": n["type"], "name": n["name"], "fallback": n["fallback"],
                             "stock_chosen": n["stock_chosen"],
                             "stock": [s["type"] for s in n["stock"]]}
                            for n in shown["npcs"]]}


def saved():
    with open(npc_editor.OUT, encoding="utf-8") as fh:
        return json.load(fh)


shown = {}
for place, trader in ((102, 1204), (187, 1165), (103, 1213)):
    doc, payload = page_payload(place)
    n = [x for x in doc["npcs"] if x["type"] == trader][0]
    own = [s["type"] for s in n["stock"]]
    shown[trader] = (own == items.own_stock(trader), set(own) & GOLD_POUCH,
                     npc_editor.gold_added(own),
                     items.with_gold_pouches(own) == items.stock_for(trader),
                     {int(k): v["type"] for k, v in doc["gold_pouches"].items()} == POUCHES)
    npc_editor.save(payload)
check("npc_editor: a pouch seller's goods are its own list, no (G) among them; the (G) the"
      " server adds are shown apart (the page's goldOf), and the two make the stall",
      shown,
      {1204: (True, set(), [3604, 3603, 3601, 3600, 5614], True, True),
       1165: (True, set(), [3599, 3603, 5614, 3600, 3601], True, True),
       1213: (True, set(), [3599, 3602, 5614, 3600, 3601], True, True)})
check("  ..and an untouched Save on 102 (the page's default place, Ваккас), 187 and 103 leaves"
      " data/npcs.json as it was", saved() == NPCS_DOC, True)


def drop_hunter(n):
    if n["type"] == 1165:
        n["stock"] = [s for s in n["stock"] if s["type"] != 3581]
        n["stock_chosen"] = True


ALIMA_OWN = items.own_stock(1165)
npc_editor.save(page_payload(187, drop_hunter)[1])
check("  ..the owner's edit of Алима's goods (охотника taken off) writes her own list, with"
      " no (G) in it, and her stall then has no охотника of either kind, the other (G) kept",
      (saved()["stock"].get("1165"),
       [t for t in items.stock_for(1165, 187) if t in POUCHES or t in GOLD_POUCH]),
      ([t for t in ALIMA_OWN if t != 3581], [3577, 3599, 5613, 5614, 3578, 3600, 3579, 3601]))
npcs.NAMES, npcs.STOCK = _kept
_rule = dict(items.GOLD_POUCHES)
items.GOLD_POUCHES.clear()
check("  ..and an empty GOLD_POUCHES takes every (G) pouch off every stall, Ваккас's too",
      sorted({t for p, types in AT.items() for tr in types for t in items.stock_for(tr, p)
              if t in GOLD_POUCH} | {t for tr in TRADERS for t in items.stock_for(tr)
                                     if t in GOLD_POUCH}), [])
items.GOLD_POUCHES.update(_rule)

# --- on the wire -------------------------------------------------------------------------
print()
print("on the wire")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("shopper", "secret")
_store.close()
CRED = accounts.credential("shopper", "secret")

import server  # noqa: E402  (after LAVA_DB: it opens its Store at import)


class Writer:
    """What Session needs of an asyncio StreamWriter, and a record of it."""

    def __init__(self):
        self.frames = []
        self.sizes = []
        self.read = 0
        self.closed = False

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))
        self.sizes.append(len(data))

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
    """What the client is told of a trader: its userInfo_Trader."""
    got = of(run(sess, "getInfo;lvl=0;id=%d;type=0;" % npc), "userInfo_Trader")
    return got[0] if got else {}


def buy(sess, index, code):
    """One purchase by the window's index: (acks, what came, afro, gold spent)."""
    before, had = purse(sess), bag(sess)
    got = run(sess, "ss_upd;s_status=%d;obj=x%x;param=1;" % (code, index))
    now = bag(sess)
    came = [t for t in set(now) if now.count(t) > had.count(t)]
    return acks(got), came, before[0] - purse(sess)[0], before[1] - purse(sess)[1]


async def main():
    sess = server.Session(Writer(), "shopper")
    run(sess, "hello;minor=2;major=0;")
    run(sess, "login;hash=@%s@;" % CRED)
    run(sess, "newPers;res=1;sex=0;name=@Shopper@;")
    run(sess, "actPlayer;")
    run(sess, "lenter;accept=1;")
    run(sess, "userMsg;entry=@/money 2000000 200000@;group=0;")

    # Абри's clothing market, then Донгола's: one type, two bands.
    seen = {}
    for place in (378, 469):
        npc = goto(sess, place)[5161]
        info = window(sess, npc)
        seen[place] = as_list(info.get("type_list"))
        check("%d: the window of 5161 is %s's band, as items.stock_for at the place" % (
            place, PLACE_CITY[place][0]), seen[place], items.stock_for(5161, place))
        stall = seen[place]
        g = next(i for i, x in enumerate(stall) if gold_of(x))
        a = next(i for i, x in enumerate(stall) if not gold_of(x) and weapon_or_piece(x))
        check("  ..the stall opens: one ack", acks(run(sess, "ss_create;s_type=1;target=%d;" % npc)),
              [0])
        check("  ..a gold piece bought for gold: one ack, that piece, its g_cost in gold, no afro",
              buy(sess, g, inventory.UPD_BUY_GOLD),
              ([0], [stall[g]], 0, items.params_of(stall[g])["g_cost"]))
        check("  ..an ordinary piece for afro: one ack, that piece, its cost in afro, no gold",
              buy(sess, a, inventory.UPD_BUY), ([0], [stall[a]], items.params_of(stall[a])["cost"], 0))
        check("  ..the wrong currency refused, nothing taken, nothing given: the ordinary one"
              " for gold, the gold one for afro",
              (buy(sess, a, inventory.UPD_BUY_GOLD), buy(sess, g, inventory.UPD_BUY)),
              (([inventory.RES_REFUSED], [], 0, 0), ([inventory.RES_REFUSED], [], 0, 0)))
        run(sess, "ss_upd;s_status=0;obj=x0;param=1;")
    check("the two windows differ, and so does what one index buys at each",
          (seen[378] != seen[469], seen[378][0] != seen[469][0]), (True, True))

    # Вади-Хальфа's black market: the shotguns, 4-8, both versions.
    npc = goto(sess, 102)[1201]
    info = window(sess, npc)
    stall = as_list(info.get("type_list"))
    sizes = [n for (name, _p), n in zip(sess.writer.frames, sess.writer.sizes)
             if name == "userInfo_Trader"]
    check("102: «Дробовики и патроны» sells Вади-Хальфа's shotguns 4-8, ten and their ten (G),"
          " then his rounds", (stall == items.stock_for(1201, 102),
                               sorted({level_of(x) for x in stall if weapon_or_piece(x)}),
                               ag(stall), [x for x in stall if not weapon_or_piece(x)]),
          (True, [4, 5, 6, 7, 8], (10, 10), items.AMMO_12MM))
    check("  ..its frame on the wire under 4 KiB", (bool(sizes), max(sizes or [0]) < 4096), (True, True))
    run(sess, "ss_create;s_type=1;target=%d;" % npc)
    jack_g = stall.index(25952)
    check("  ..Jackhammer (G) for its 2.05 ounces in gold, one ack",
          buy(sess, jack_g, inventory.UPD_BUY_GOLD), ([0], [25952], 0, 205))
    check("  ..Jackhammer for 12 200 afro, one ack", buy(sess, stall.index(25951), inventory.UPD_BUY),
          ([0], [25951], 12200, 0))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")

    # Ваккас on the same market: the town's sets, then his belts, each with its (G).
    npc = goto(sess, 102)[1204]
    stall = as_list(window(sess, npc).get("type_list"))
    check("102: Ваккас's window is his stall there, the belts last, each (G) after its"
          " ordinary one", (stall == items.stock_for(1204, 102), stall[-10:]),
          (True, [3582, 3604, 3581, 3603, 3579, 3601, 3578, 3600, 5613, 5614]))
    run(sess, "ss_create;s_type=1;target=%d;" % npc)
    check("  ..«Подсумки пистолетные (G)» for its 0.50 ounces in gold, one ack, no afro",
          buy(sess, stall.index(3604), inventory.UPD_BUY_GOLD), ([0], [3604], 0, 50))
    check("  ..«Подсумки рукопашника (G)» for 8 ounces",
          buy(sess, stall.index(5614), inventory.UPD_BUY_GOLD), ([0], [5614], 0, 800))
    check("  ..a (G) belt for afro refused, nothing taken, nothing given",
          buy(sess, stall.index(3604), inventory.UPD_BUY), ([inventory.RES_REFUSED], [], 0, 0))
    check("  ..«Подсумки рукопашника» for 40 000 afro, its article's price",
          buy(sess, stall.index(5613), inventory.UPD_BUY), ([0], [5613], 40000, 0))

    def sell(type_id):
        row = [r for r in server.STORE.items_of(sess.char_id) if r["type_id"] == type_id][0]
        before = purse(sess)
        got = run(sess, "ss_upd;s_status=2;obj=x%s;param=1;" % inventory.oid_of(row))
        return acks(got), type_id in bag(sess), purse(sess)[0] - before[0], purse(sess)[1] - before[1]

    check("  ..the (G) ones are not bought back: refused, kept, no money either way",
          (sell(3604), sell(5614)),
          (([inventory.RES_REFUSED], True, 0, 0), ([inventory.RES_REFUSED], True, 0, 0)))
    check("  ..the ordinary one is, for 0.7 of its price: 28 000 afro back for 40 000",
          sell(5613), ([0], False, 28000, 0))
    run(sess, "ss_upd;s_status=0;obj=x0;param=1;")


asyncio.run(main())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("stall bands OK")
