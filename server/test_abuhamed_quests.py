"""Абу-Хамед's quests (the owner's «сделай потом абу хамед в таком же
формате», 2026-10-14): the rows 880-999 and 771 of data/quests.json, the
Боевая Академия's lessons (data/questgen_academy.json, 12000-12074), the ways
of data/passages.json they take, the prison's and the Центр's windows of
data/schedule.json, the Центр of data/holdings.json and the rows of
Вади-Хальфа, Абри and Донгола that waited for the town (163-168, 272, 276,
277, 283, 284, 516), held on the real tables.

In process:

  * every row of 880-999 sits in its block of the plan (abuhamed/DESIGN.md
    5.0) and is on (a giver and a taker); the blocks cut stay empty -- «Вести»
    937-941 (no box, water or hole of the Масаи in any file) and the reserve;
    the rows that waited for Абу-Хамед are on;
  * the givers and takers stand in a place the map opens (a cell of
    data/settlements.json, or what a door, a side or a quest way leads to
    from one), each by a name of the original's or a DESIGNED one, never its
    mobs.xml name;
  * every string id is in the preload; the texts are the original's where
    data/build_orig_misc.py pins them, laid over the table's; the rows not
    pinned are exactly the DESIGNED ones, and no DESIGNED line says «не ...,
    а ...»;
  * every thing a row names is an objects.xml object with a name and a
    description of its own, none premium; every thing asked for can be had
    -- dropped while the quest wants it by somebody standing in the open
    places (a slot's drop, a «Квестовый» row of data/loot_manual.json), sold
    at a stall there, or handed out by a row: the diamond of Гатера's fare
    off the Тёмная шахта's miners, the bandits' keys off their bosses, «Вещи
    X» out of their boxes, the dreadnought's parts from Абимбола;
  * no row pays gold or an ingot; a fee in gold only on the rides 276/277,
    Вюрт's key (897) and the Академия's lessons; the five «Убить X» take
    100000 afro;
  * the ways: each way row has its record at the giver's place, its cells on
    the grid, walkable, off the exits, where no window opens, nobody arrives
    and nobody stands; given and taken by one inhabitant; the pairs written
    on both sides; from every interior of Абу-Хамед -- the prison, the
    quarry, the mines, the Тёмная шахта, the Академия, the hide-outs -- the
    free ways, sides and doors lead to a place of the map;
  * the prison: «Выход» (163) is a way under '651' up to the yard 177, the
    gates lead to 649 and 650, Веласкес gives 277, 284, 880 and 884, the
    windows prison_ah* keep the label's hours, the prisoners drop the
    armband 2476 in 651-653 and the one keep_in row holds the three prisons;
  * the mines' gates: three ways down at levels 15-20, three up at any level,
    the labels L317-L319 named; the lotteries: every prize worth less than
    its ticket, the town's band 16-20 covered;
  * the Центр: a site of data/holdings.json, its box's row 771 the holders',
    level 19, once a day, 48000 afro, in its own window wh_box_ah of 19:00
    for a quarter of an hour;
  * the Академия: 75 lessons, level 17, once a day, each after the one
    before it in its group, the specialisations' only for a learned one,
    the fee the text's gold and silver at 10:1; the fastest way up 17 -> 20
    by one skill's lessons alone takes nine days or more and costs 1500 G or
    more, and no skill takes more than 10.55 million a day; «Ножи для
    учеников» asks the learned unarmed specialisation and pays into it;
  * Абимбола: «Ящик X» takes the key X and gives «Вещи X», «Убить X» names
    the bandit (Гвала 1708, never his crocodiles 1706), «Собрать X» makes the
    Паладин's pieces 11559-11563;
  * «Письмо Президента Крюгера ч.2»: its parts off the miners 930/931, and
    the second Кленз 1760 stands nowhere;
  * «Коллекция водителя джихад-такси» (272): its six pieces named, a live
    collection, Уорхол gives 270, 271 and 272.

On a socket (a server of the suite's own, LAVA_CHEATS) only the rides:

  * at Донгола's station (49) «Поездка в Абу-Хамед» with no gold is refused,
    with 0,25 G it brings the player to Абу-Хамед's station (126), beside
    Веласкес's way back; «Поездка в Донголу» there costs 0,10 G and brings
    him back; «Проездной в Абу-Хамед» (283) and «Проездной в Донголу» (284)
    take their tickets and nothing else.

    LAVA_RES=.../lava/res python3 server/test_abuhamed_quests.py
"""
import itertools
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_START",
              "LAVA_START_AFRO", "LAVA_BOSS_HOURS", "LAVA_SCHEDULE"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import events  # noqa: E402
import holdings  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import keepsakes  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MT = world.mob_types()
# The plan's blocks (DESIGN.md 5.0); the cut ones stay empty.
BLOCKS = {"prison": range(880, 886), "kruger": range(886, 903), "quarry": range(903, 910),
          "gates": range(910, 916), "lottery": range(916, 922), "scarab": range(922, 925),
          "nasir": range(925, 937), "vesti": range(937, 942), "abimbola": range(942, 965),
          "academy": range(965, 968), "reserve": range(968, 1000)}
CUT = ("vesti", "reserve")
EXPECT = {"prison": list(range(880, 885)), "kruger": list(range(886, 900)),
          "quarry": list(range(903, 910)), "gates": list(range(910, 916)),
          "lottery": list(range(916, 922)), "scarab": [922, 923],
          "nasir": list(range(925, 936)), "abimbola": list(range(942, 965)),
          "academy": [965, 966, 967]}
BOX_ROW = 771
LESSONS = range(12000, 12075)
# Not pinned to the original: their texts are DESIGNED (the mines' gates,
# the lotteries' names and prize lists, «Письмо ч.2» sent to the Тёмная шахта).
DESIGNED = {888, 910, 911, 912, 913, 914, 915, 916, 917, 918, 919, 920, 921}
# The rows of Вади-Хальфа, Абри and Донгола that waited for Абу-Хамед.
WAITED = [163, 164, 165, 166, 167, 168, 272, 276, 277, 283, 284]
NUR, VELASQUEZ, DN_STATION, STATION, YARD = 156, 740, 49, 126, 177
RIDES = {276: (NUR, DN_STATION, STATION), 283: (NUR, DN_STATION, STATION),
         277: (VELASQUEZ, STATION, DN_STATION), 284: (VELASQUEZ, STATION, DN_STATION)}
TICKET_AH, TICKET_DN = 1567, 1639
GATES_DOWN = {910: (213, 666, "L317"), 911: (214, 667, "L319"), 912: (215, 668, "L318")}
GATES_UP = {913: (666, 213), 914: (667, 214), 915: (668, 215)}
LOTTERIES = {916: (2652, 3000, False, (16, 16)), 917: (2653, 3700, False, (17, 18)),
             918: (3574, 4730, False, (19, 20)), 919: (2654, 300, True, (16, 16)),
             920: (2655, 350, True, (17, 18)), 921: (3575, 450, True, (19, 20))}
# The interiors of Абу-Хамед, none of them a place of the map (DESIGN.md 4.3).
INTERIORS = ([649, 650, 651, 652, 653], [636, 637, 638, 639, 640],
             [666, 667, 668, 1034, 1035, 1036, 1227, 1228, 1229],
             [615, 1014, 1216, 1254, 1273], [1295], [690, 691, 692, 693, 694])
HIDEOUTS = [690, 691, 692, 693, 694]
# The pairs of ways written on both sides.
PAIRS = ([((DN_STATION, 276), (STATION, 277)), ((DN_STATION, 283), (STATION, 284)),
          ((STATION, 880), (YARD, 881)), ((127, 903), (636, 904)),
          ((127, 965), (1295, 966))]
         + [((place, gate), (room, 913 + k)) for k, (gate, (place, room, _l))
            in enumerate(sorted(GATES_DOWN.items()))]
         + [((446, 949 + k), (h, 954)) for k, h in enumerate(HIDEOUTS)])
NOT_BUT = re.compile(r"(?:^|[\s(«])не\s[^.!?<]*?,\s*а\s", re.I)
BAND, PRISONERS_AH = 2476, [1118, 1119, 1120, 1121, 1122, 2175]
BLOCKS_WH, BLOCKS_DN = [644, 645, 646, 647, 648], [618, 619, 620, 621, 622]
BLOCKS_AH = [649, 650, 651, 652, 653]
# Абимбола's bandits: «Убить X» -> (the bandit, his box's row, the box, his
# key, «Вещи X», the piece his parts make at Эммануил's).
BANDITS = {943: (1702, 955, 2113, 5583, 4160, 960), 944: (1708, 956, 2114, 5584, 4161, 961),
           945: (1710, 957, 2115, 5585, 4162, 962), 946: (1718, 958, 2116, 5586, 4163, 963),
           947: (1720, 959, 2117, 5587, 4164, 964)}
CROCODILE, DIAMOND, MINERS = 1706, 5545, [930, 931]
PALADIN = {960: 11559, 961: 11560, 962: 11563, 963: 11561, 964: 11562}
GOLD_FEES = {276: 25, 277: 10, 897: 50}


def passages():
    with open(travel.passages_path(), encoding=ENC) as fh:
        return json.load(fh)


def reached_from(start, free_only=False):
    """Every place a player gets to from start, start among them: through a
    door the server follows, a side of data/passages.json or a quest way
    (test_halfa_city's rule); with free_only, only the free ways -- level 0,
    no chain, nothing asked, no fee, no window."""
    sides = passages().get("sides") or {}
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = []
        for _c, r in travel.quest_ways(world.location(lid)):
            q = quests.get(int(r["quest"]))
            if free_only and (q is None or not q.give or q.level or q.need_all
                              or q.need_any or q.wants() or q.has_fee
                              or int(r["quest"]) in events.table().gates):
                continue
            targets.append(r.get("target_loc_id"))
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
                targets.append(rec.get("target_loc_id"))
        own = sides.get(str(lid)) if isinstance(sides, dict) else None
        targets += [r.get("target_loc_id") for r in (own or {}).values() if isinstance(r, dict)]
        for t in targets:
            if t and int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    return seen


def item_name(t):
    return names.ALL.get(items.STRING_ID_OFFSET + t)


def fastest_climb(rows, start=17, stop=20):
    """(days, gold hundredths) of the fastest way a character's level -- his
    best skill -- goes from start to stop by one skill's lessons alone: each
    lesson once a day (per_day), a lesson only after the one before it was
    handed in once (need_quest), and of the ways that fast the cheapest."""
    need = sum(progression.skill_xp_max(level) for level in range(start, stop))
    xp = [sum(v for _s, v in q.rew_xp) for q in rows]
    cost = [q.cost_gold for q in rows]
    per_day = [q.per_day for q in rows]
    day_max = sum(x * n for x, n in zip(xp, per_day))
    days = -(-need // day_max)
    best = None
    for counts in itertools.product(*[range(days * n + 1) for n in per_day]):
        if any(counts[i] and not counts[i - 1] for i in range(1, len(counts))):
            continue
        if sum(c * x for c, x in zip(counts, xp)) < need:
            continue
        price = sum(c * g for c, g in zip(counts, cost))
        best = price if best is None else min(best, price)
    return days, best, day_max


# --- in process: the table -------------------------------------------------------------
try:
    real = quests.QUESTS
    raw = {r["type"]: r for r in quests.table_rows()}
    mine = sorted(t for t in real if 880 <= t <= 999)
    check("the rows of 880-999 sit in their blocks of the plan, the cut blocks empty",
          {b: [t for t in mine if t in r] for b, r in BLOCKS.items()},
          dict({b: [] for b in CUT}, **EXPECT))
    lessons = sorted(t for t in real if t in LESSONS)
    live = mine + [BOX_ROW] + WAITED + lessons
    check("  ..and every one of them is on (a giver and a taker), the Центр's box (771), the 75"
          " lessons and the rows that waited for Абу-Хамед too",
          ([t for t in live if not (real[t].give and real[t].take)], len(lessons)), ([], 75))

    # Where the people stand: every place of the map, and what it opens.
    open_places = reached_from(set(world.settlements().values()))
    stands = {}
    for lid in sorted(open_places):
        loc = world.location(lid)
        for _cell, t in loc.spawns:
            stands.setdefault(t, set()).add(lid)
        for t in world.camp_fill(lid):
            stands.setdefault(t, set()).add(lid)
        for rec in world.placed_in(lid):
            stands.setdefault(int(rec["type"]), set()).add(lid)
    people = sorted({w for t in live for w in real[t].give + real[t].take})
    check("every giver and taker of the rows stands in a place the map opens",
          [w for w in people if not stands.get(w)], [])
    check("  ..and shows a name of the original's or a DESIGNED one, never its mobs.xml name",
          [w for w in people if not names.known(w) or names.ALL.get(w) == MT[w][1]], [])

    # The strings and the texts.
    check("every string id of the rows is in the preload",
          [(t, sid) for t in mine + [BOX_ROW] + lessons for sid in real[t].string_ids()
           if not names.known(sid)], [])
    with open(os.path.join(ROOT, "data", "orig_misc.json"), encoding=ENC) as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts pinned to the original (data/build_orig_misc.py VERIFIED): every row but"
          " the DESIGNED ones (the mines' gates, the lotteries, «Письмо ч.2»); no lesson",
          (sorted(set(mine + [BOX_ROW]) - set(pinned)), [t for t in lessons if t in pinned]),
          (sorted(DESIGNED), []))
    orig = orig_texts.quests()
    check("  ..laid over the table's (but what a row keeps as its own, own_texts)",
          [(t, key) for t in mine + [BOX_ROW] for k, key in enumerate(quests.TEXT_KEYS)
           if orig.get(t, {}).get(key) and key not in real[t].own_texts
           and real[t].texts[k] != quests.served(real[t], k, orig[t][key])], [])
    designed_lines = [(t, key, raw[t][key]) for t in mine + [BOX_ROW] + lessons
                      for key in quests.TEXT_KEYS
                      if raw[t].get(key) and (t in DESIGNED or t in LESSONS
                                              or not orig.get(t, {}).get(key)
                                              or key in real[t].own_texts)]
    check("no DESIGNED line says «не ..., а ...»",
          [(t, key) for t, key, line in designed_lines if NOT_BUT.search(line)], [])

    # The things.
    things = sorted({o for t in live for _f, o in real[t].things()})
    cat = items.catalogue()
    check("every thing the rows name is an objects.xml object (quests.check_items)",
          ([o for o in things if o not in cat], quests.check_items()), ([], None))
    check("  ..with a name and a description the client knows, the name never the internal one,"
          " none premium",
          [o for o in things if not names.known(items.STRING_ID_OFFSET + o)
           or not names.known(items.DESC_ID_OFFSET + o)
           or item_name(o) in (None, "", cat[o][1]) or items.premium(o)], [])
    traders = {w for w in stands if MT.get(w) and MT[w][0] == world.TRADER}
    on_sale = {o for w in traders for lid in stands[w] for o in items.stock_for(w, lid)}
    handed = {o for q in real.values() if q.give for o in
              q.rew_obj + [t for t, _n in q.rew_also] + [t for t, _n, _w in q.rew_random]
              + [t for t, _n in q.start_obj]} | set(keepsakes.pool())
    dropped = {o for q in real.values() if q.give for _m, o, _c in q.drops if stands.get(_m)}
    dropped |= {o for m in stands for o, _c in mobs.quest_table(m)}
    # ..and what data/schedule.json's loot puts on a creature in a place: the
    # prisons' armband (164-168).
    dropped |= {o for (lid, m), drops in events.table().loot.items()
                if lid in stands.get(m, ()) for o, _n, _c in drops}
    asked = sorted({o for t in live for o, _n in real[t].wants()})
    check("every thing a row asks for can be had: dropped while the quest wants it by somebody"
          " standing in the open places, sold at a stall there, or handed out by a row",
          [o for o in asked if o not in on_sale | handed | dropped], [])
    check("  ..the diamond of Гатера's fare off the Тёмная шахта's miners alone (the row"
          " «Квестовый» of data/loot_manual.json), the miners standing",
          (sorted(m for m in MT if DIAMOND in dict(mobs.quest_table(m))),
           all(stands.get(m) for m in MINERS)), (MINERS, True))
    check("  ..the bandits' keys off their bosses, «Вещи X» out of their boxes, the dreadnought's"
          " parts from Абимбола's «Убить X» alone",
          ({t: sorted((m, o) for m, o, _c in real[row].drops) for t, (_b, row, _x, _k, _l, _p)
            in BANDITS.items()},
           {t: (real[row].give, real[row].rew_obj) for t, (_b, row, _x, _k, _l, _p)
            in BANDITS.items()},
           sorted({o for t in BANDITS for o in real[t].rew_obj}),
           sorted(t for t, q in real.items() if q.give and set(q.rew_obj + [o for o, _n in
                                                                          q.rew_also])
                  & set(range(5546, 5576)))),
          ({t: [(b, k)] for t, (b, _r, _x, k, _l, _p) in BANDITS.items()},
           {t: ([x], [l]) for t, (_b, _r, x, _k, l, _p) in BANDITS.items()},
           list(range(5546, 5576)), sorted(BANDITS)))
    check("no row pays gold (rew_gold) or hands out an ingot; a fee in gold only on the rides,"
          " Вюрт's key and the lessons (the text's gold and silver at 10:1)",
          ([t for t in live if real[t].rew_gold],
           [t for t in live for _f, o in real[t].things() if o in items.GOLD_INGOTS],
           {t: real[t].cost_gold for t in live if real[t].cost_gold and t not in LESSONS}),
          ([], [], GOLD_FEES))
    check("  ..and the five «Убить X» take Абимбола's 100000 afro, nothing else an afro fee",
          {t: real[t].cost_afro for t in live if real[t].cost_afro},
          {t: 100000 for t in BANDITS})

    # The ways.
    ways = {}
    for t in live:
        if not real[t].rew_loc:
            continue
        for lid in sorted({p for w in real[t].give for p in stands.get(w, ())}):
            rec = travel.quest_way(world.location(lid), t)
            if rec:
                ways.setdefault(t, set()).add((lid, int(rec["target_loc_id"])))
    check("every way row has its record at the giver's place in data/passages.json",
          sorted(t for t in live if real[t].rew_loc and t not in ways), [])
    bad_cells = []
    for t in sorted(ways):
        for lid, _to in sorted(ways[t]):
            loc = world.location(lid)
            cells, _rec = next((c, r) for c, r in travel.quest_ways(loc) if int(r["quest"]) == t)
            taken = {c for c, _t in loc.spawns}
            zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                           "zones", 4)}
            here = {s for _c, s in loc.spawns}
            if not all(w in here for w in real[t].give):
                bad_cells.append((t, lid, "giver"))
            for c in cells:
                if c in loc.obstacles or c in travel.exit_sides(loc) or c in taken \
                        or c in zones or c in loc.entries:
                    bad_cells.append((t, lid, c % loc.width, c // loc.width))
    check("  ..its cells on the grid, walkable, off the exits, where no window opens, nobody"
          " arrives and nobody stands, its giver standing there (test_halfa_training's rule)",
          bad_cells, [])
    check("  ..given and taken by one inhabitant, as every way (server/test_mine)",
          [t for t in ways if real[t].give != real[t].take], [])
    check("  ..the pairs written on both sides, each leading to the other's place",
          [((a, ta), (b, tb)) for (a, ta), (b, tb) in PAIRS
           if not ((a, b) in ways.get(ta, ()) and (b, a) in ways.get(tb, ()))], [])
    traps = {}
    for group in INTERIORS:
        for lid in group:
            reach = reached_from({lid}, free_only=True)
            if not any(world.cell_of(p) is not None for p in reach):
                traps[lid] = sorted(reach)
    check("from every interior of Абу-Хамед its free ways (level 0, no chain, nothing asked, no"
          " window), sides and doors lead to a place of the map", traps, {})
    check("  ..and none of them is left by the map's buttons (data/passages.json no_map), but"
          " the mines' rooms and tiers, which have no side (as Абри's and Донгола's)",
          [lid for g in INTERIORS for lid in g
           if not travel.no_map(lid) and lid not in INTERIORS[2]], [])
    check("the rides: Нур-ад-Дин to Абу-Хамед and Веласкес back to Донгола, for the fare and"
          " for the ticket",
          {t: (real[t].give, sorted(ways.get(t, ()))) for t in RIDES},
          {t: ([d], [(frm, to)]) for t, (d, frm, to) in RIDES.items()})
    check("  ..the fares the texts name, 0,25 and 0,10 G, and the tickets 1567 and 1639",
          [(real[t].cost_gold, [o for o, _n in real[t].wants()]) for t in (276, 277, 283, 284)],
          [(25, []), (10, []), (0, [TICKET_AH]), (0, [TICKET_DN])])
    check("  ..each a way of the row's own record ('way'), at no level, repeatable",
          {t: (raw[t]["way"]["at"], raw[t]["way"]["target_loc_id"], real[t].level,
               real[t].repeatable) for t in RIDES},
          {t: (frm, to, 0, 1) for t, (_d, frm, to) in RIDES.items()})
    check("Нур-ад-Дин and Веласкес list their rides where q_idx finds them",
          (quests.given_by(NUR), quests.given_by(VELASQUEZ)),
          ([276, 282, 283, 631, 632, 636], [277, 284, 880, 884]))

    # The prison.
    sched = events.table()
    sraw = json.load(open(events.schedule_path(), encoding=ENC))
    check("the prison: «Выход» (163) leads from 651 up to the yard 177, the gates of 177 down"
          " to 649 and 650, «Поехали!» from the station to the yard and «Назад в Абу-Хамед» back",
          (sorted(w for w in ways.get(163, ()) if w[0] == 651), sorted(ways.get(882, ())),
           sorted(ways.get(883, ())), sorted(ways.get(880, ())), sorted(ways.get(881, ()))),
          ([(651, YARD)], [(YARD, 649)], [(YARD, 650)], [(STATION, YARD)], [(YARD, STATION)]))
    check("  ..the uprising at the label's 12:00, 16:00 and 23:00 (L154) for half an hour, the"
          " gates from a quarter before, the medics for the last five minutes",
          (sched.window("prison_ah").why.startswith("RECOVERED"),
           sorted(k for k in sraw["windows"] if k.startswith("prison_ah")),
           sraw["windows"]["prison_ah"]["daily"], sraw["windows"]["prison_ah"]["minutes"],
           [(sched.gates[t][0].name, sched.gates[t][1]) for t in (880, 882, 883, 884)]),
          (True, ["prison_ah", "prison_ah_gates", "prison_ah_medics"],
           ["12:00", "16:00", "23:00"], 30,
           [("prison_ah_gates", "both")] * 3 + [("prison_ah_gates", "hand_in")]))
    check("  ..the prisoners and the godfather drop the armband in 651-653, one each, and the"
          " one keep_in row of 2476 holds the three prisons' blocks",
          (sorted((loc, mob) for (loc, mob), drops in sched.loot.items()
                  if loc in BLOCKS_AH and (BAND, 1, 1.0) in drops),
           [sorted(locs) for types, locs in sched.keep_in if BAND in types]),
          (sorted((loc, mob) for loc in (651, 652, 653) for mob in PRISONERS_AH),
           [sorted(BLOCKS_WH + BLOCKS_DN + BLOCKS_AH)]))
    check("  ..the armbands' rows (164-168) name the three prisons' prisoners as who drops them",
          {t: sorted(PRISONERS_AH) == sorted(m for _o, _n, ms in real[t].objs for m in ms
                                            if m in PRISONERS_AH) for t in range(164, 169)},
          {t: True for t in range(164, 169)})
    check("  ..Абу-Хамед's «Охранник санатория особого режима» (884): Веласкес's, handed in to"
          " the southern guard 1796 at the gates, 158's start word for word, level 17",
          (real[884].give, real[884].take, raw[884]["start"] == raw[158]["start"],
           real[884].own_texts, real[884].level),
          ([VELASQUEZ], [1796], True, frozenset(["start"]), 17))

    # The mines' gates and the lotteries.
    check("the mines' gates: down at levels 15-20 from the surface to the control room, up at"
          " any level back; each names its label",
          ({t: (real[t].level, real[t].max_level, sorted(ways.get(t, ())), lab in raw[t]["why"])
            for t, (_p, _r, lab) in GATES_DOWN.items()},
           {t: (real[t].level, real[t].max_level, sorted(ways.get(t, ()))) for t in GATES_UP}),
          ({t: (15, 20, [(p, r)], True) for t, (p, r, _l) in GATES_DOWN.items()},
           {t: (0, None, [v]) for t, v in GATES_UP.items()}))

    def worth(obj, num, gold):
        return inventory.buy_price(items.params_of(obj), items.root_of(obj), num, gold)

    check("the lotteries: every prize worth less than the ticket (the house wins), the gold"
          " ones' prizes gold things",
          ({t: [worth(o, n, gold) < price for o, n, _w in real[t].rew_random]
            for t, (_k, price, gold, _b) in LOTTERIES.items()},
           [o for t, (_k, _p, gold, _b) in LOTTERIES.items() if gold
            for o, _n, _w in real[t].rew_random if not items.params_of(o).get("g_cost")]),
          ({t: [True] * len(real[t].rew_random) for t in LOTTERIES}, []))
    check("  ..each the ticket of its levels, the three covering the town's band 16-20",
          ({t: ([o for o, _n in real[t].wants()], real[t].level, real[t].max_level)
            for t in LOTTERIES},
           sorted({lv for t in (916, 917, 918) for lv in range(real[t].level,
                                                               real[t].max_level + 1)})),
          ({t: ([k], b[0], b[1]) for t, (k, _p, _g, b) in LOTTERIES.items()},
           [16, 17, 18, 19, 20]))

    # The Центр.
    with open(os.path.join(ROOT, "data", "holdings.json"), encoding=ENC) as fh:
        sites = json.load(fh)["sites"]
    s = sites.get("wh_ah_center", {})
    check("the Центр: a site of data/holdings.json (128, its master 7454, the box 6830), the"
          " box's row 771 the holders', at level 19 (L327), once a day, 48000 afro",
          ((s.get("loc"), s.get("boss"), s.get("box"), s.get("quest"), s.get("min_level")),
           real[BOX_ROW].holders, real[BOX_ROW].give, real[BOX_ROW].level,
           real[BOX_ROW].per_day, real[BOX_ROW].rew_afro, holdings.problems()),
          ((128, 7454, 6830, BOX_ROW, 19), "wh_ah_center", [6830], 19, 1, 48000, []))
    check("  ..in its own window of the label's «Дележ добычи с 19:00 до 19:15»: wh_box_ah",
          (sraw["windows"].get("wh_box_ah", {}).get("daily"),
           sraw["windows"].get("wh_box_ah", {}).get("minutes"),
           sched.gates.get(BOX_ROW, (None, None))[0] and sched.gates[BOX_ROW][0].name,
           sched.gates.get(BOX_ROW, (None, None))[1]),
          (["19:00"], 15, "wh_box_ah", "both"))

    # The Академия.
    groups = {}
    for t in lessons:
        q = real[t]
        key = ("skill", q.rew_xp[0][0]) if q.rew_xp else ("spec", q.rew_spec_xp[0][0])
        groups.setdefault(key, []).append(q)
    check("the Академия: 75 lessons, 20 of the four skills and 55 of the eleven specialisations,"
          " five each, at level 17, once a day, services",
          (sorted((k[0], len(v)) for k, v in groups.items()).count(("skill", 5)),
           sorted((k[0], len(v)) for k, v in groups.items()).count(("spec", 5)),
           {(real[t].level, real[t].per_day, real[t].repeatable, real[t].service)
            for t in lessons}),
          (4, 11, {(17, 1, 1, True)}))
    check("  ..each after the one before it in its group, the first after none",
          [q.type for g in groups.values() for n, q in enumerate(g)
           if q.need_all != ([g[n - 1].type] if n else [])], [])
    check("  ..a specialisation's only for a learned one, its experience into it alone; a skill's"
          " into the skill",
          ([q.type for (kind, idx), g in groups.items() if kind == "spec" for q in g
            if q.requires_spec != [idx] or q.rew_xp],
           [q.type for (kind, _i), g in groups.items() if kind == "skill" for q in g
            if q.requires_spec or q.rew_spec_xp]), ([], []))
    check("  ..the fee the start's gold and its silver at 10:1: 6, 12, 25, 50 and 100 G",
          sorted({tuple(q.cost_gold for q in g) for g in groups.values()}),
          [(600, 1200, 2500, 5000, 10000)])
    check("  ..given by the teacher of the group, in the Академия",
          sorted({(k[0], tuple(sorted({w for q in g for w in q.give}))) for k, g in groups.items()}
                 ), sorted({("skill", (1425,)), ("skill", (1426,)), ("skill", (1427,)),
                            ("skill", (1428,)), ("spec", (1425,)), ("spec", (1426,)),
                            ("spec", (1427,)), ("spec", (1428,))}))
    climbs = {k[1]: fastest_climb(g) for k, g in groups.items() if k[0] == "skill"}
    check("  ..the fastest way up 17 -> 20 by one skill's lessons takes eight days or more and"
          " costs 1500 G or more, and no skill takes more than 10.55 million a day",
          sorted((days >= 8, gold >= 150000, day_max <= 10550000)
                 for days, gold, day_max in climbs.values()), [(True, True, True)] * 4)
    print("  (the climb 17 -> 20 by one skill: %s)" % sorted(
        "%d days, %d G" % (d, g // 100) for d, g, _m in climbs.values()))
    check("  ..the Академия entered by Илья's way from the Жилой квартал and left by his twin's,"
          " free, any time",
          (sorted(ways.get(965, ())), sorted(ways.get(966, ())), real[966].level,
           real[966].wants(), real[966].has_fee), ([(127, 1295)], [(1295, 127)], 0, [], False))
    check("«Ножи для учеников» (967): fifty knives off the Аванпост's corporals, for a learned"
          " unarmed specialisation, paid into it",
          (real[967].requires_spec, real[967].rew_spec_xp, real[967].wants(),
           sorted({m for _o, _n, ms in real[967].objs for m in ms})),
          ([0], [(0, 200000)], [(4203, 50)], [1027]))

    # Абимбола.
    check("Абимбола's bandits: «Ящик X» takes the key X off the bandit and gives «Вещи X»;"
          " «Убить X» asks «Вещи X» of that bandit -- Гвала 1708, never his crocodiles 1706",
          ({t: (real[row].wants(), real[row].rew_obj, real[t].wants(),
                sorted({m for _o, _n, ms in real[t].objs for m in ms}))
            for t, (_b, row, _x, _k, _l, _p) in BANDITS.items()},
           CROCODILE in {m for t in BANDITS for _o, _n, ms in real[t].objs for m in ms}),
          ({t: ([(k, 1)], [loot], [(loot, 1)], [b])
            for t, (b, _r, _x, k, loot, _p) in BANDITS.items()}, False))
    check("  ..Гатера's car to each hide-out for a diamond, and back from each free",
          ({t: (real[t].wants(), sorted(ways.get(t, ()))) for t in range(949, 954)},
           sorted(ways.get(954, ()))),
          ({949 + k: ([(DIAMOND, 1)], [(446, h)]) for k, h in enumerate(HIDEOUTS)},
           sorted((h, 446) for h in HIDEOUTS)))
    check("  ..«Собрать X» at Эммануил's: the six parts a bandit's heads bring make a piece of"
          " the Паладин[19][A] (11559-11563)",
          {t: (real[t].rew_obj, sorted(o for o, _n in real[t].wants()) ==
               sorted(real[k].rew_obj)) for k, (_b, _r, _x, _y, _l, t) in BANDITS.items()},
          {t: ([PALADIN[t]], True) for t in PALADIN})

    # Крюгер and Уорхол.
    check("«Письмо Президента Крюгера ч.2» (888): its parts off the Тёмная шахта's miners, and"
          " the second Кленз (1760) stands nowhere",
          (sorted({(m, o) for m, o, _c in real[888].drops}), stands.get(1760)),
          (sorted((m, o) for m in MINERS for o in (4189, 4190, 4191, 4192)), None))
    pieces = list(range(6599, 6605))
    check("«Коллекция водителя джихад-такси» (272): its six pieces named and described, a live"
          " collection, Уорхол gives 270, 271 and 272, the reward the open road's tickets",
          ([item_name(o) for o in pieces],
           [names.known(items.DESC_ID_OFFSET + o) for o in pieces],
           [(t, live_) for t, live_, _p in keepsakes.collections()],
           quests.given_by(2259), real[272].rew_obj),
          (["Автомагнитола (Коллекция)", "Аккумулятор (Коллекция)", "Колесо (Коллекция)",
            "Автомобильный номер (Коллекция)", "Табличка маршрута (Коллекция)",
            "Руль (Коллекция)"], [True] * 6,
           [(270, True), (271, True), (272, True)], [270, 271, 272], [TICKET_AH, TICKET_DN]))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT_NO = free_port()
DB = os.path.join(tempfile.mkdtemp(), "abuhamed_quests.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("rider", "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT_NO), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_START_AFRO="0", LAVA_SEED="11",
           LAVA_POLICY_PORT="0")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def inhabitants(frames):
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(1.5)


def goto(c, where):
    c.send("userMsg;entry=@/goto %d@;group=0;" % where)
    c.until(lambda f: f[0] == "lcall")
    return inhabitants(arrive(c))


def store():
    return accounts.Store(DB)


def char_id(name):
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    st.close()
    return row["id"]


def purse(name):
    st = store()
    got = tuple(st.money(char_id(name)))
    st.close()
    return got


def owned(name):
    st = store()
    out = {}
    for r in st.items_of(char_id(name)):
        out[r["type_id"]] = out.get(r["type_id"], 0) + (
            r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
    st.close()
    return out


def login(first=False):
    c = Client(testkit.connect(PORT_NO, srv, LOG))
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential("rider", "secret"))
    c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@Rider@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    return c


def take(c, here, npc_type, qtype):
    c.send("q_st;mob=%d;q_idx=%d;" % (here[npc_type][0], quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id):
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (here[npc_type][0], q_id))
    return c.frames(1.0)


def ride(c, got):
    """The lcall a way's hand-in brings, and where the player stands after it."""
    call = named(got, "lcall") or named(c.until(lambda f: f[0] == "lcall", 6), "lcall")
    if not call:
        return None, None, {}
    arrival = arrive(c)
    pos = named(arrival, "lenter")
    return call[0].get("id"), (pos[0].get("pos") if pos else None), inhabitants(arrival)


def money(c, afro, gold=0):
    c.send("userMsg;entry=@/money %d %d@;group=0;" % (afro, gold))
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)


def give(c, obj):
    c.send("userMsg;entry=@/give %d 1@;group=0;" % obj)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)


try:
    c = login(first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.3)
    st = store()
    cid = char_id("Rider")
    st.save_stats(cid, [("skill", progression.SHOOTING, 16, 0, progression.skill_xp_max(16))])
    st.save_character_state(cid, level=16)
    st.close()
    c = login()

    # --- to Абу-Хамед for the fare
    here = goto(c, DN_STATION)
    check("Нур-ад-Дин stands at Донгола's station", NUR in here, True)
    took, q_id = take(c, here, NUR, 276)
    refused = hand_in(c, here, NUR, q_id)
    check("«Поездка в Абу-Хамед» with no gold: taken, and the hand-in refused -- nobody moves",
          (acks(took), acks(refused)[:1] != [0], bool(named(refused, "lcall"))),
          ([0], True, False))
    money(c, 0, 25)
    went = hand_in(c, here, NUR, q_id)
    lid, pos, there = ride(c, went)
    ah = world.location(STATION)
    check("  ..with 0,25 G: handed in, the fare gone, and an lcall to Абу-Хамед's station, where"
          " Веласкес stands",
          (acks(went)[:1], purse("Rider")[1], lid, VELASQUEZ in there), ([0], 0, STATION, True))
    check("  ..arrived beside the way back (travel.door_arrival on 277's cells)",
          pos == travel.door_arrival(ah, DN_STATION) if pos is not None else None, True)

    # --- back for the fare
    money(c, 0, 10)
    took, q_id = take(c, there, VELASQUEZ, 277)
    back = hand_in(c, there, VELASQUEZ, q_id)
    lid, _pos, here = ride(c, back)
    check("«Поездка в Донголу» at Веласкес's: 0,10 G, and back at Донгола's station",
          (acks(took), acks(back)[:1], purse("Rider")[1], lid, NUR in here),
          ([0], [0], 0, DN_STATION, True))

    # --- by the tickets
    give(c, TICKET_AH)
    took, q_id = take(c, here, NUR, 283)
    went = hand_in(c, here, NUR, q_id)
    lid, _pos, there = ride(c, went)
    check("«Проездной в Абу-Хамед» (283): the ticket 1567 taken, no gold, and on to Абу-Хамед's"
          " station", (acks(took), acks(went)[:1], owned("Rider").get(TICKET_AH, 0),
                       purse("Rider")[1], lid), ([0], [0], 0, 0, STATION))
    give(c, TICKET_DN)
    took, q_id = take(c, there, VELASQUEZ, 284)
    went = hand_in(c, there, VELASQUEZ, q_id)
    lid, _pos, _there = ride(c, went)
    check("«Проездной в Донголу» (284): the ticket 1639 taken, and back to Донгола's station",
          (acks(took), acks(went)[:1], owned("Rider").get(TICKET_DN, 0), lid),
          ([0], [0], 0, DN_STATION))
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    with open(LOG, encoding=ENC) as fh:
        text = fh.read()
    check("the server's log has no Traceback", "Traceback" in text, False)
except Exception:
    import traceback
    fails.append("the socket run broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print("  - " + f)
    print("server log: %s" % LOG)
    sys.exit(1)
print("\nall ok")
