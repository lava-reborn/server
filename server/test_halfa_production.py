"""Вади-Хальфа's mining and production (halfa-production, stage 3): ore out of
the three ore mines' rock, the mines' sorting terminals, the processing base
(199) and the ammunition factory (198) as the original's CrBQ rows
(data/questgen_production.json, data/build_questgen_production.py); the
Вади-Хальфа mine (154/158/160) joined to its tiers by DESIGNED doors and
sides, with Фрэнк's raid (221) switched on; the quarry's leftovers
(quests.json 320-323).

In process: the things (named from the original, their numbers, what a
stall pays for them piece by piece), the rocks standing in the ore mines'
tiers and nowhere else, what a rock leaves, and that it teaches nothing (as
no object does, combat.OBJECTS_PAY_XP), the generated rows (givers where they
stand, the band, the chain, what each asks and makes, no (P) round, the
heaviest ask carried beside the band's heaviest kit), the cooldown key, the
quarry's rows and their texts, each paying more a stone than the plain
blocks capped a day, the mine's doors and sides -- every exit of every tier
covered, each way back where it came from, the three doors up into the
entrances arriving on their own cells (own_cell) and every other door of the
game keeping the player's cell, every tier reached from each entrance alone,
none of them onto the map (no_map), five minutes to a respawn there -- the
miners it opens, their sub-machine guns and their loot, and 221 on.

On a socket:

  * a miner (level 6): the copper mine's gate and door; a rock broken with a
    gun leaves a piece of copper ore in its bag and teaches nothing;
    the terminal sorts ten pieces into 150 parts; the base's line makes
    three boxes of cases and rests (cooldown) until twenty minutes have
    passed; the factory makes 600 rounds of 12-gauge, not the (P) ones; the
    second line prepared, the gold line takes its 0.02 G; the gates and the
    rows closed above the band and below it;
  * a raider (level 8): «Индийское кино» and Фрэнк's raid taken; the
    Вади-Хальфа mine entered by the door of 154, the Ефрейторы and miners
    shot, the ring off a miner, five miners counted, the way back up; the
    second tier walked end to end by its sides, 1016 through the tunnels
    and 1024 to 1012, and a door up into the third entrance landing on its
    own cell; the raid and the ring handed in;
  * a quarry worker: the polishing mix's components off the quarry's
    stones, the mix, the polished blocks at Большой Сэм, the foundation
    stones and the polished ones at Варон's building site, three a day.

    LAVA_RES=.../lava/res python3 server/test_halfa_production.py
"""
import collections
import json
import math
import os
import random
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_START_AFRO"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import production  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import sets  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- the places, the people, the things ------------------------------------------------
COPPER_TOP, COPPER_ROOM, COPPER_1 = 200, 657, 1025
LEAD_ROOM, NITRE_ROOM = 658, 659
ORE_TIERS = {1025: 1316, 1218: 1354, 1255: 1355, 1027: 1308, 1220: 1344, 1257: 1345,
             1026: 1312, 1219: 1349, 1256: 1350}
ROCKS_STAND = {1025: 20, 1218: 10, 1255: 5, 1027: 20, 1220: 15, 1257: 12, 1026: 10, 1219: 9,
               1256: 7}
PANEL, GUARD = 2022, 1714
BASE, FACTORY, STATION, PIER, QUARRY_N, QUARRY_C, SITE = 199, 198, 37, 41, 627, 626, 165
MARKET = 104                    # Портовый рынок, Фрэнк's stall
VH_TOP = {154: (5983, 1735), 158: (5984, 1735), 160: (5988, 1735)}
VH_TIERS = [613, 617, 1012, 1016, 1024, 1215]
VH_TUNNELS = [1017, 1018, 1019]
DOORS_WANT = {(154, "b"): 613, (613, "a"): 154, (613, "b"): 1024, (158, "b"): 617,
              (617, "a"): 158, (617, "b"): 1012, (160, "b"): 1016, (1012, "a"): 617,
              (1016, "a"): 160, (1024, "a"): 613, (1024, "b"): 1215, (1215, "a"): 1024}
# The second tier, one gallery west to east: 1016, the tunnels 1017-1019, 1024, 1012.
VH_GALLERY = [1016, 1017, 1018, 1019, 1024, 1012]
SIDES_WANT = {}
for _w, _e in zip(VH_GALLERY, VH_GALLERY[1:]):
    SIDES_WANT[(_w, "E")], SIDES_WANT[(_e, "W")] = _e, _w
SORTERS = {"plumbum": (1359, LEAD_ROOM), "nitre": (1363, NITRE_ROOM),
           "copper": (1367, COPPER_ROOM)}
LINES = {"plumbum": 1371, "nitre": 1375, "copper": 1379}
ASSEMBLER, GATE_COPPER, EXIT_COPPER = 1383, 1328, 1340
SAM, VARON, STONE, FRANK, OLD_WOMAN, CORPORAL, MINER, MINER_9 = 979, 1005, 977, 698, 1685, \
    312, 838, 839
ORE = {"plumbum": 3636, "nitre": 3640, "copper": 3644}
SORTED = {"plumbum": 3672, "nitre": 3676, "copper": 3680}
SACK = {"plumbum": 3648, "nitre": 3652, "copper": 3656}
KS_12, KS_SP10, P_12, P_SP10 = 6096, 6103, 6132, 6139
BLOCK, MIX, PARTS, RING = 2944, 2945, (2946, 2947, 2948, 2949), 3939
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
# The quests.
GEN = list(range(13000, 13032))
SORT = {"plumbum": [13000, 13001, 13002, 13003], "nitre": [13004, 13005, 13006, 13007],
        "copper": [13008, 13009, 13010, 13011]}
LINE = {"plumbum": [13012, 13013, 13014, 13015], "nitre": [13016, 13017, 13018, 13019],
        "copper": [13020, 13021, 13022, 13023]}
AMMO = {KS_12: [13024, 13025, 13026, 13027], KS_SP10: [13028, 13029, 13030, 13031]}
POLISHED, MIX_Q, FOUNDATION, POLISHED_V = 320, 321, 322, 323
GATES, RAID, CINEMA, SHAWARMA = [406, 407, 408], 221, 208, 220
MT = world.mob_types()


def room(loc_id):
    return rooms.Room(world.location(loc_id), rooms.IdAllocator(), MT)


def stood(loc_id):
    return collections.Counter(n.type_id for n in room(loc_id).npcs.values())


# --- in process: the things --------------------------------------------------------------
try:
    cat = items.catalogue()
    check("the chain's things are the (ВХ) copies of objects.xml's series, one a city in order",
          ([cat[t][1] for t in production.ORE["plumbum"]],
           [cat[t][1] for t in production.SORTED["copper"]],
           [cat[t][1] for t in production.SACKS["powder"]]),
          (["plumbum_ore_%d" % k for k in range(1, 6)],
           ["copper_ore_sorting_%d" % k for k in range(1, 6)],
           ["powder_sack_%d" % k for k in range(1, 6)]))
    shown = {t: names.ALL.get(items.STRING_ID_OFFSET + t)
             for t in list(ORE.values()) + list(SORTED.values()) + list(SACK.values())
             + [MIX] + list(PARTS)}
    check("they show the original's names (data/build_orig_items.py rule 7i), not objects.xml's",
          shown, {3636: "(ВХ) Свинцовая руда", 3640: "(ВХ) Селитра сырьевая",
                  3644: "(ВХ) Медная руда", 3672: "(ВХ) Сорт. Свинцовая руда",
                  3676: "(ВХ) Сорт. Селитра сырьевая", 3680: "(ВХ) Сорт. Медная руда",
                  3648: "(ВХ) Ящик пуль", 3652: "(ВХ) Мешок пороха", 3656: "(ВХ) Коробка гильз",
                  2945: "Полировочная смесь", 2946: "Компонент №1", 2947: "Компонент №2",
                  2948: "Компонент №3", 2949: "Компонент №4"})
    check("  ..and their words: a description on every one of them",
          [t for t in shown if not items.params_of(t).get("desc")
           or items.DESC_ID_OFFSET + t not in names.ALL], [])
    every = [t for kind in (production.ORE, production.SORTED, production.SACKS)
             for ts in kind.values() for t in ts] + [MIX] + list(PARTS)
    check("every thing of the chain in all five cities has a name the client can be sent",
          [t for t in every if items.STRING_ID_OFFSET + t not in names.ALL], [])

    def nums(t):
        p = items.params_of(t)
        return (p["cost"], p["weight"], p["max_count"], p["exchang"], p["quest"])
    check("the ore: 1 afro, 100 to a stack, changes hands (the (АХ) articles); 750 g of lead,"
          " 500 of copper and saltpetre (under the articles' 4000/2000: the flat 50 kg)",
          [nums(ORE[o]) for o in ("plumbum", "nitre", "copper")],
          [(1, 750, 100, 1, 0), (1, 500, 100, 1, 0), (1, 500, 100, 1, 0)])
    check("  ..the sorted parts and the sacks: no stall pays for them, light, a run to a stack",
          [nums(SORTED["plumbum"]), nums(SACK["nitre"])],
          [(0, 25, 1000, 1, 0), (0, 250, 100, 1, 0)])
    check("  ..the quarry's mix and components: worth nothing at a stall (no 7-afro sale)",
          [items.params_of(t)["cost"] for t in (MIX,) + PARTS], [0] * 5)
    def sold(t, n):
        """What a stall pays for n of a thing sold at once: inventory's sale
        (ss_upd at a trader), never under 1 afro, nothing for a thing priced
        in gold alone (inventory.SELL_GOLD_ONLY off)."""
        si = items.params_of(t)
        if not si.get("cost"):
            return 0
        return max(1, int(math.floor(si["cost"] / float(si.get("sell_num", 1)) * n
                                     * inventory.SMOD * si.get("sell_mod", 1))))
    check("  ..what the whole chain is worth at a stall: ten ore 7 afro at once, 10 one by"
          " one; the 600 rounds a first factory line makes 420 at once, 600 one by one -- a"
          " piece or a round at most 1 afro",
          (sold(ORE["plumbum"], 10), 10 * sold(ORE["plumbum"], 1), sold(KS_12, 600),
           600 * sold(KS_12, 1), sold(KS_SP10, 1)), (7, 10, 420, 600, 1))
    check("the rounds made are the ordinary 12-gauge and СП-10 КС, not their (P) twins",
          ([items.premium(t) for t in (KS_12, KS_SP10)], [items.premium(t) for t in (P_12, P_SP10)],
           [names.ALL.get(items.STRING_ID_OFFSET + t) for t in (KS_12, KS_SP10)]),
          ([False, False], [True, True], ["12–й калибр $КС", "СП–10 $КС"]))

    # --- the rocks -------------------------------------------------------------------------
    check("each ore mine tier stands the rocks its file puts there (production.ORE_ROCKS)",
          {i: stood(i)[t] for i, t in ORE_TIERS.items()}, ROCKS_STAND)
    check("  ..and its two guards, but not the electrical panel (an object not listed)",
          {i: (stood(i)[GUARD], stood(i)[PANEL]) for i in ORE_TIERS},
          {i: (2, 0) for i in ORE_TIERS})
    check("world.STANDING_OBJECTS is unchanged: the rocks stand by production's own table",
          any(i in world.STANDING_OBJECTS for i in ORE_TIERS), False)
    others = {i: world.location(i) for i in range(1, 1400)
              if world.path_for(i) and i not in ORE_TIERS
              and any(t in production.ORE_YIELD for _c, t in world.location(i).spawns)}
    check("no other file stands the town's rocks", {i: stood(i) for i in others if
                                                    any(t in production.ORE_YIELD
                                                        for t in stood(i))}, {})
    check("a rock is an immobile, harmless object of level 5",
          [(mobs.stats(t).role, mobs.stats(t).moves, mobs.stats(t).can_attack, mobs.stats(t).level)
           for t in sorted(set(ORE_TIERS.values()))], [("object", False, False, 5)] * 9)
    check("  ..and leaves one piece of the town's ore of its kind (production.yield_of)",
          {t: production.yield_of(t) for t in sorted(set(ORE_TIERS.values()))},
          {1308: [(3636, 1)], 1312: [(3640, 1)], 1316: [(3644, 1)], 1344: [(3636, 1)],
           1345: [(3636, 1)], 1349: [(3640, 1)], 1350: [(3640, 1)], 1354: [(3644, 1)],
           1355: [(3644, 1)]})
    check("  ..nothing else: no table of loot of its own, no quest's thing",
          [(mobs.loot_table(t), mobs.quest_table(t)) for t in sorted(set(ORE_TIERS.values()))],
          [([], [])] * 9)
    check("  ..teaching nothing, as no object does (production.MINING_PAYS_XP is"
          " combat.OBJECTS_PAY_XP, off)", (production.MINING_PAYS_XP, combat.OBJECTS_PAY_XP),
          (False, False))

    class _Sess(object):
        def push_stats(self, **_changed):
            pass

        def push_vitals(self):
            pass

    class _Miner(object):
        sess = _Sess()

        def __init__(self):
            self.ch = progression.Character()
            self.ch.skill[progression.SHOOTING] = [4, 0, progression.skill_xp_max(4)]
            self.ch.spec[production.MINING_SPEC] = [0, 0, progression.SPEC_XP_START]
            self.ch.recalc()

        def character(self):
            return self.ch

    class _Rock(object):
        type_id, stats, level = 1316, mobs.stats(1316), mobs.stats(1316).level

    def mined(n):
        f = _Miner()
        for _ in range(n):
            production.mined_by(f, _Rock())
        return (f.ch.level, f.ch.skill[progression.INDUSTRY][:2],
                f.ch.spec[production.MINING_SPEC][:2])
    check("  ..so 1500 rocks broken leave a level-4 shooter as he was (production.mined_by)",
          mined(1500), (4, [0, 0], [0, 0]))
    production.MINING_PAYS_XP = True
    try:
        check("  ..where the owner's switch on would pay Промышленность on the kills' curve up to"
              " its grey gap (level 7), and the character's level with it: 10 a rock at 0",
              ([progression.mob_xp(5, L, 1.0, mobs.stats(1316).xp_mult) for L in (0, 4, 6, 7)],
               mined(1)[1], mined(1500)[0] > 4), ([10.0, 32.0, 8.0, 0.0], [0, 10], True))
    finally:
        production.MINING_PAYS_XP = False

    # --- the generated rows ----------------------------------------------------------------
    rows = {t: quests.get(t) for t in GEN}
    check("the plant's 32 rows are in the table (data/questgen_production.json), 13000-13031",
          [t for t in GEN if rows[t] is None], [])
    with open(os.path.join(ROOT, "data", "questgen_production.json"), encoding="utf-8") as fh:
        GEN_DOC = json.load(fh)
    check("  ..and only those, each saying it is generated and from which CrBQ row",
          ([r["type"] for r in GEN_DOC["quests"]],
           [r["type"] for r in GEN_DOC["quests"] if not r["why"].startswith("GENERATED")
            or "CrBQ№" not in r["why"]]), (GEN, []))
    where = {}
    for o, (term, rm) in SORTERS.items():
        where.update({t: (term, rm) for t in SORT[o]})
        where.update({t: (LINES[o], BASE) for t in LINE[o]})
    for t in AMMO[KS_12] + AMMO[KS_SP10]:
        where[t] = (ASSEMBLER, FACTORY)
    check("each is given and taken by the terminal or line that stands where it works",
          [t for t in GEN if rows[t].give != [where[t][0]] or rows[t].take != [where[t][0]]
           or where[t][0] not in {s for _c, s in world.location(where[t][1]).spawns}], [])
    check("  ..in the mines' band, 4-8, services outside the daily limit and the journal",
          {(q.level, q.max_level, q.service) for q in rows.values()}, {(4, 8, True)})

    def asks(t):
        return [(o, n) for o, n, _m in rows[t].objs]

    def makes(t):
        return (rows[t].rew_obj[0], rows[t].num_rew_obj[0])
    check("sorting: 10, 40, 20 and 20 pieces with 0.02 G -> the parts of one, four, two and"
          " two and a half of the base's first line",
          {o: [(asks(t), makes(t), rows[t].cost_gold) for t in SORT[o]] for o in SORT},
          {"plumbum": [([(3636, 10)], (3672, 120), 0), ([(3636, 40)], (3672, 480), 0),
                       ([(3636, 20)], (3672, 240), 0), ([(3636, 20)], (3672, 300), 2)],
           "nitre": [([(3640, 10)], (3676, 200), 0), ([(3640, 40)], (3676, 800), 0),
                     ([(3640, 20)], (3676, 400), 0), ([(3640, 20)], (3676, 500), 2)],
           "copper": [([(3644, 10)], (3680, 150), 0), ([(3644, 40)], (3680, 600), 0),
                      ([(3644, 20)], (3680, 300), 0), ([(3644, 20)], (3680, 375), 2)]})
    check("  ..and each first sorting run is exactly one first line of the base",
          [makes(SORT[o][0])[1] == asks(LINE[o][0])[0][1] for o in SORT], [True] * 3)
    check("the base: 120 lead / 200 saltpetre / 150 copper parts a line -> three sacks, the"
          " prepared second line twice, the gold line a quarter more",
          {o: [(asks(t)[0][1], makes(t), rows[t].cost_gold) for t in LINE[o]] for o in LINE},
          {"plumbum": [(120, (3648, 3), 0), (480, (3648, 12), 0), (240, (3648, 6), 0),
                       (240, (3648, 8), 2)],
           "nitre": [(200, (3652, 3), 0), (800, (3652, 12), 0), (400, (3652, 6), 0),
                     (400, (3652, 8), 2)],
           "copper": [(150, (3656, 3), 0), (600, (3656, 12), 0), (300, (3656, 6), 0),
                      (300, (3656, 8), 2)]})
    check("the factory: 3 bullets, 12 powder, 9 cases -> 600 rounds, of the two calibres its"
          " label names, ordinary ones",
          {r: [(asks(t), makes(t), rows[t].cost_gold) for t in AMMO[r]] for r in AMMO},
          {r: [([(3648, 3), (3652, 12), (3656, 9)], (r, 600), 0),
               ([(3648, 12), (3652, 48), (3656, 36)], (r, 2400), 0),
               ([(3648, 6), (3652, 24), (3656, 18)], (r, 1200), 0),
               ([(3648, 6), (3652, 24), (3656, 18)], (r, 1500), 2)] for r in AMMO})
    # What a character of the band carries anyway: the heaviest set it may wear
    # (data/sets.json), the heaviest gun it may hold, 600 rounds -- all of it
    # counted against the flat inventory.MAX_WEIGHT, as a loot bag's pick-up is.
    kit = (max(sum(items.params_of(t)["weight"] for t in s["members"].values())
               for s in sets.SETS.values()
               if max(inventory.item_level(t) for t in s["members"].values()) <= 8)
           + max(items.params_of(t)["weight"] for t in cat
                 if items.root_of(t) == items.FIRE_ARM and items.params_of(t)
                 and not items.premium(t) and 1 <= inventory.item_level(t) <= 8)
           + 600 * items.params_of(KS_12)["weight"])
    load = {t: sum(items.params_of(o)["weight"] * n for o, n in asks(t)) for t in GEN}
    check("what any row asks fits the bag beside the band's heaviest set, gun and 600 rounds"
          " (%d g): 13001's 40 pieces of lead the heaviest, 30 kg" % kit,
          ([t for t in GEN if kit + load[t] > inventory.MAX_WEIGHT],
           max(load, key=load.get), load[13001]), ([], 13001, 30000))
    check("no row pays a (P) thing, money, or anything but its one product",
          [t for t in GEN if any(items.premium(o) for o in rows[t].rew_obj)
           or rows[t].rew_afro or rows[t].rew_gold or rows[t].rew_also or rows[t].rew_random],
          [])
    check("the second and gold lines open once their one-off preparation is handed in",
          {t: (rows[t].repeatable, rows[t].need_all) for fam in
           list(SORT.values()) + list(LINE.values()) + list(AMMO.values()) for t in fam},
          {t: ((0, []) if i == 1 else (1, [fam[1]] if i > 1 else []))
           for fam in list(SORT.values()) + list(LINE.values()) + list(AMMO.values())
           for i, t in enumerate(fam)})
    check("the base's and the factory's lines rest 20 minutes (cooldown), the sorting does not",
          ({rows[t].cooldown for o in LINE for t in LINE[o] if rows[t].repeatable}
           | {rows[t].cooldown for r in AMMO for t in AMMO[r] if rows[t].repeatable},
           {rows[t].cooldown for o in SORT for t in SORT[o]}), ({1200}, {0}))
    check("  ..the base's first line saying so in the original's words",
          rows[LINE["plumbum"][0]].texts[quests.FINISH],
          "Цикл закончен.<Br><Br><b>Повторное использование возможно через 20 минут.</b>")
    check("experience into Промышленность and «Добыча» (sorting) or «Переработка» (the plant)",
          {t: (rows[t].rew_xp, rows[t].rew_spec_xp) for t in (13000, 13003, 13012, 13015,
                                                              13024, 13027)},
          {13000: ([(progression.INDUSTRY, 20)], [(10, 20)]),
           13003: ([(progression.INDUSTRY, 200)], [(10, 200)]),
           13012: ([(progression.INDUSTRY, 30)], [(11, 30)]),
           13015: ([(progression.INDUSTRY, 300)], [(11, 300)]),
           13024: ([(progression.INDUSTRY, 60)], [(11, 60)]),
           13027: ([(progression.INDUSTRY, 600)], [(11, 600)])})
    try:
        quests.Quest(dict(type=99999, kind="del_obj", name="x", cooldown=60, repeatable=0))
        once = "accepted"
    except ValueError:
        once = "refused"
    check("a cooldown is refused on a one-off row (quests.Quest)", once, "refused")
    quests.check_items()
    check("every thing the table names is one the game has (quests.check_items)", True, True)

    # --- the quarry's leftovers --------------------------------------------------------
    q = {t: quests.get(t) for t in (POLISHED, MIX_Q, FOUNDATION, POLISHED_V)}
    check("320-323 in the table, after Мортимер's and the lotteries' 301-309",
          [r["type"] for r in quests.table_rows(quests.PATH)][
              [r["type"] for r in quests.table_rows(quests.PATH)].index(309) + 1:][:4],
          [320, 321, 322, 323])
    check("  ..their texts the original's (data/orig_misc.json, VERIFIED)",
          [q[t].texts[quests.NAME] for t in q],
          ["Полированные камни.", "Создать Полировочную смесь", "Камни для фундамента",
           "Полированные Камни"])
    check("  ..Большой Сэм's in the quarry's north pit, Варон's at the building site",
          [(q[t].give, q[t].take, q[t].give[0] in {s for _c, s in world.location(
              QUARRY_N if t < 322 else SITE).spawns}) for t in q],
          [([SAM], [SAM], True)] * 2 + [([VARON], [VARON], True)] * 2)
    check("  ..asking the blocks, the mix, the four components; paying 255, the mix, 200, 360",
          [(q[t].wants(), q[t].rew_obj, q[t].rew_afro) for t in q],
          [([(BLOCK, 10), (MIX, 1)], [], 255), ([(p, 1) for p in PARTS], [MIX], 0),
           ([(BLOCK, 10)], [], 200), ([(BLOCK, 10), (MIX, 1)], [], 360)])
    check("  ..services; the polished blocks and Варон's three times a day",
          [(q[t].service, q[t].per_day) for t in q],
          [(True, 3), (True, 0), (True, 3), (True, 3)])

    def stones_for(qtype, rng):
        """Stones broken until one hand-in of qtype is in the bag, the mix's
        components dropping off the same stones for «Создать Полировочную
        смесь» (321) open beside it (quests.wanted_things joins every open
        row's wants; mobs.quest_roll rolls each wanted thing a stone)."""
        need = collections.Counter(dict(quests.get(qtype).wants()))
        if need.pop(MIX, 0):
            need.update({p_: 1 for p_ in PARTS})
        bag, n = collections.Counter(), 0
        while any(bag[t] < k for t, k in need.items()):
            n += 1
            for t, k in mobs.quest_roll(STONE, {t for t in need if bag[t] < need[t]}, rng):
                bag[t] += k
        return n
    rng_ = random.Random(7)
    per_stone = {t: quests.get(t).rew_afro * 2000.0 / sum(stones_for(t, rng_) for _ in range(2000))
                 for t in (403, 404, POLISHED, FOUNDATION, POLISHED_V)}
    check("every quarry row paying more a stone than the plain blocks (403) is capped a day"
          " (afro a stone: %s)" % ", ".join("%d %.1f" % (t, v) for t, v in sorted(per_stone.items())),
          [t for t, v in sorted(per_stone.items())
           if v > per_stone[403] + 0.5 and not quests.get(t).per_day], [])
    check("  ..so the new rows pay one character at most 765 + 600 + 1080 afro a day",
          sum(q[t].rew_afro * q[t].per_day for t in q), 2445)
    check("a quarry stone drops the block (1.0) and each component (0.2) for who wants them",
          quests.quest_drops(STONE), [(BLOCK, 1.0)] + [(p, 0.2) for p in PARTS] + [(3186, 0.05)])

    # --- the Вади-Хальфа mine ------------------------------------------------------------
    for lid in VH_TIERS + VH_TUNNELS:
        loc = world.location(lid)
        open_ = sorted(set(travel.exit_sides(loc).values()))
        leak = [s for s in open_ if (travel.door(lid, s) if s in "ab" else travel.side_way(lid, s))
                is None]
        check("%d %s: every exit of it leads inside the mine (%s)" % (lid, loc.fn, ",".join(open_)),
              (world.cell_of(lid), leak), (None, []))
    check("the doors lead where the design says, each followed (medium, designed)",
          {(k, s): (travel.door(k, s) or {}).get("target_loc_id") for k, s in DOORS_WANT},
          DOORS_WANT)
    check("  ..and every one's far side has a door back",
          [(k, s) for (k, s), t in DOORS_WANT.items()
           if not any((travel.door(t, b) or {}).get("target_loc_id") == k for b in "ab")], [])
    check("the sides: the second tier one gallery, 1016 - the tunnels - 1024 - 1012",
          {k: travel.side_way(*k)["target_loc_id"] for k in SIDES_WANT}, SIDES_WANT)
    check("  ..each one back over the opposite edge",
          [k for k, t in SIDES_WANT.items()
           if (travel.side_way(t, travel.OPPOSITE[k[1]]) or {}).get("target_loc_id") != k[0]], [])

    def door_cell(lid, side):
        loc = world.location(lid)
        return sorted(c for c, s in travel.exit_sides(loc).items() if s == side)[0]
    ex = travel.plan_exit(world.location(154), door_cell(154, "b"), *VH_TOP[154])
    check("down 154's door: the first tier, on 154's cell", (ex.loc_id, ex.gx, ex.gy),
          (613,) + VH_TOP[154])
    ex = travel.plan_exit(world.location(1016), door_cell(1016, "a"), *VH_TOP[158])
    check("up 1016's door from the side of 158: the third entrance, on its own cell"
          " (travel.plan_exit)", (ex.loc_id, ex.gx, ex.gy), (160,) + VH_TOP[160])
    ex = travel.plan_exit(world.location(613), door_cell(613, "a"), *VH_TOP[154])
    check("  ..and up 613's door into 154, where it came from: its cell",
          (ex.loc_id, ex.gx, ex.gy), (154,) + VH_TOP[154])
    # Every door of the game a player can take (data/exits.json, corrected by
    # data/passages.json), from its location's own cell or, for an interior,
    # some other: only a door whose record says own_cell moves the player
    # onto its far side's cell; every other keeps the cell it is taken from.
    with open(os.path.join(ROOT, "data", "exits.json"), encoding="utf-8") as fh:
        ids = {int(k) for k in json.load(fh)["doors"] if k.isdigit()}
    with open(travel.passages_path(), encoding="utf-8") as fh:
        ids |= {int(k) for k in json.load(fh)["doors"] if k.isdigit()}
    own, shifted, taken = [], [], {}
    for lid in sorted(ids - set(travel.SCENE_IDS)):
        for s in "ab":
            rec = travel.door(lid, s)
            if not rec or rec.get("target_loc_id") is None \
                    or rec.get("confidence") not in travel.DOOR_CONFIDENCE:
                continue
            try:
                loc = world.location(lid)
                start = world.cell_of(lid) or VH_TOP[158]
                ex = travel.plan_exit(loc, door_cell(lid, s), *start)
            except (IndexError, KeyError, OSError, travel.Refused):
                continue
            if rec.get("own_cell"):
                own.append((lid, s))
            far = world.cell_of(int(rec["target_loc_id"]))
            want = far if rec.get("own_cell") and far else start
            taken[(lid, s)] = (ex.loc_id, ex.gx, ex.gy)
            if (ex.gx, ex.gy) != tuple(want):
                shifted.append((lid, s, start, (ex.gx, ex.gy)))
    check("only the mine's three doors up into its entrances arrive on the far side's cell"
          " (own_cell)", own, [(613, "a"), (617, "a"), (1016, "a")])
    check("  ..every other of the game's %d doors keeps the cell it is taken from" % len(taken),
          shifted, [])
    check("  ..among them the «Горные тропы» doors 598/162 and 623/53, as before the mine",
          [taken.get(k) for k in ((598, "a"), (162, "b"), (623, "a"), (53, "b"))],
          [(162, 6015, 1747), (598, 5908, 2001), (53, 6017, 1747), (623, 6212, 1948)])

    def reached(start):
        seen, todo = set(start), list(start)
        while todo:
            lid = todo.pop()
            ts = [(travel.door(lid, s) or {}).get("target_loc_id") for s in "ab"] + \
                 [(travel.side_way(lid, s) or {}).get("target_loc_id") for s in "WNES"]
            for t in ts:
                if t and t not in seen:
                    seen.add(t)
                    todo.append(t)
        return seen
    check("from each of the three entrances alone every tier and tunnel is reached",
          [(e, sorted(set(VH_TIERS + VH_TUNNELS) - reached({e}))) for e in VH_TOP],
          [(e, []) for e in VH_TOP])
    check("  ..and none of them opens onto the map: out only by the doors up (no_map)",
          [lid for lid in VH_TIERS + VH_TUNNELS if not travel.no_map(lid)], [])
    check("  ..their creatures back in five minutes, the rest of the world's in %d s"
          % combat.RESPAWN_DELAY,
          ({combat.respawn_delay(lid) for lid in list(VH_TOP) + VH_TIERS + VH_TUNNELS},
           combat.respawn_delay(STATION)),
          ({combat.RESPAWN_DELAY * 300 / 45}, combat.RESPAWN_DELAY))
    check("  ..and the miners shoot a sub-machine gun (the wiki's «Кустарный ПП»), not a knife",
          [mobs.stats(m).weapon_class for m in (MINER, MINER_9)], ["smg", "smg"])
    miners = {i: stood(i)[MINER] for i in VH_TIERS + VH_TUNNELS}
    check("  ..and the [8] miners stand in them", sum(miners.values()) >= 30 and all(
        miners[i] for i in (613, 617, 1012, 1024)), True)
    rng_ = random.Random(5)
    corpse = {m: sum(sold(t, n) for _ in range(4000)
                     for t, n in mobs.loot_for(mobs.stats(m), rng_)) / 4000.0
              for m in (MINER, MINER_9, CORPORAL)}
    check("the mine opens 31 [8] and 16 [9] miners to the band (about %d and %d afro a corpse"
          " at a stall, the Ефрейтор at 154 %d)" % (corpse[MINER], corpse[MINER_9],
                                                    corpse[CORPORAL]),
          (sum(miners.values()), sum(stood(i)[MINER_9] for i in VH_TIERS + VH_TUNNELS)),
          (31, 16))
    check("  ..their loot no richer than the men of their level already on the map: the"
          " [8] miner's table the Ефрейтор's, the [9]'s the same but for its level's valuable",
          (mobs.loot_table(MINER) == mobs.loot_table(CORPORAL),
           [r for r in mobs.loot_table(MINER_9) if not r[2]]
           == [r for r in mobs.loot_table(MINER) if not r[2]]), (True, True))
    check("«Просьба о помощи» (221) is on, at Фрэнк (the wiki's «Боец сопротивления»)",
          (quests.get(RAID).give, quests.get(RAID).take), ([FRANK], [FRANK]))
    check("«Индийское кино»'s ring drops off the mine's miners (the slot's drop)",
          [dict(mobs.quest_table(m)).get(RING) for m in (MINER, MINER_9)], [0.2, 0.2])
    check("the ore mines' gates keep their band, 4-8",
          [(quests.get(t).level, quests.get(t).max_level) for t in GATES], [(4, 8)] * 3)
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "production.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _login in ("miner", "raider", "mason", "novice"):
    _store.register(_login, "secret")
_store.close()
# A fallen creature is back after 20 s: time enough to take its bag and go
# before it stands there again (and falls on whoever is beside its cell).
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_AP_REGEN="50", LAVA_RESPAWN="20",
           LAVA_SEED="23", LAVA_LEAVE_COMBAT="2")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


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

    def frames(self, wait=0.5):
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


def first(frames, name):
    got = named(frames, name)
    return got[0] if got else {}


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(eid):
    return "x1%08x" % eid


def inhabitants(frames):
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def positions(frames):
    where = {}
    for n, p in frames:
        if n == "lch" and "newUser" in p:
            where[p["newUser"]] = p["pos"]
        elif n == "userMove" and p.get("id") in where and p.get("path"):
            where[p["id"]] = p["path"][-1]
    return where


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, loc_id):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, here, npc_type, qtype):
    npc = here.get(npc_type, [0])[0]
    offered = quests.given_by(npc_type)
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, offered.index(qtype) if qtype in offered else 99))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id, obj_idx=0, wait=1.0):
    npc = here.get(npc_type, [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def moved(c, got, wait=8):
    call = first(got, "lcall") or first(c.until(lambda f: f[0] == "lcall", wait), "lcall")
    return call, (arrive(c) if call else [])


def cid_of(name):
    st = accounts.Store(DB)
    row = st.character_by_name(name)
    st.close()
    return row["id"]


def held(cid):
    st = accounts.Store(DB)
    out = collections.Counter()
    for r in st.items_of(cid):
        out[r["type_id"]] += r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
    st.close()
    return out


def purse(cid):
    st = accounts.Store(DB)
    row = st.character(cid)
    st.close()
    return row["afro"], row["gold"]


def industry(cid):
    st = accounts.Store(DB)
    ch = progression.Character.load(st, cid)
    st.close()
    return tuple(ch.skill[progression.INDUSTRY][:2])


def login(login_, name, first_time=True):
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % accounts.credential(login_, "secret"))
    c.frames()
    if first_time:
        c.send("newPers;res=1;sex=0;name=@%s@;" % name)
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    return c


def logout(c):
    c.send("logout;")
    c.frames(0.5)
    c.s.close()
    time.sleep(0.3)


def reshape(name, skill):
    """A logged-out character's best skill (Стрельба)."""
    st = accounts.Store(DB)
    ch = progression.Character.load(st, st.character_by_name(name)["id"])
    ch.skill[progression.SHOOTING] = [skill, 0, progression.skill_xp_max(skill)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(st)
    st.close()


def arm(c):
    """The admin gun in hand and loaded: its oid."""
    gun, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 900)
    c.send("ss_get;target=0;slot=11;")
    held_ = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held_) > 6 and held_[6] not in ("0", gun):
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held_[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % gun)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
    c.until(lambda f: f[0] == "ss_di_firearm")
    return gun


def through(c, loc_id, side):
    """Walk onto a door or side of a location and take it: (acks, the lcall)."""
    loc = world.location(loc_id)
    cells = sorted(cc for cc, s in travel.exit_sides(loc).items() if s == side
                   and cc not in loc.obstacles)
    c.send("moveTo;path=|%d|;" % cells[len(cells) // 2])
    c.frames(0.5)
    for _ in range(6):
        c.send("chWorld;to=1;")
        got = c.frames(0.8)
        if not first(got, "lcall"):
            got += c.until(lambda f: f[0] == "lcall" or (f[0] == "cmdAck" and f[1]["res"]), 4)
        if acks(got) != [39]:           # still in a fight: the exit timer
            break
        time.sleep(2.5)
    call = first(got, "lcall")
    return acks(got), call, (arrive(c) if call else [])


def hunt(c, got, loc_id, gun, want, pos, done=()):
    """Shoot one creature of type want (not one of done) from a cell with a
    clear line to it and out of every hostile's reach, its own included (the
    admin gun fells anything in one shot, from afar): (frames, its id or
    None, where the player stands, where it fell, the cells within reach of
    the other hostiles). The fallen (done) are not among them: the mine
    keeps them down for minutes (combat.SLOW_RESPAWN), longer than a hunt,
    and the caller empties done once it has waited them back."""
    loc = world.location(loc_id)
    cells = range(loc.width * loc.height)
    types = {e: t for t, es in inhabitants(got).items() for e in es}
    hostile = {e for e, t in types.items() if MT.get(t, (None,))[0] == world.MOB
               and mobs.stats(t).can_attack}
    reach = max([mobs.stats(types[e]).aggro for e in hostile] or [0]) + 0.5
    out = []
    where = positions(got)
    for eid in [e for e, t in types.items() if t == want and e not in done]:
        home = where.get(eid)
        if home is None:
            continue
        others = [where[e] for e in hostile if e != eid and e not in done and e in where]
        wary = {cell for cell in cells
                if any(mobs.hex_distance(cell, o, loc.width) <= reach for o in others)}
        spots = sorted((mobs.hex_distance(cell, home, loc.width), cell) for cell in cells
                       if cell not in loc.obstacles and cell not in wary
                       and travel.side_at(loc, cell) is None and cell not in where.values()
                       and (eid not in hostile
                            or mobs.hex_distance(cell, home, loc.width) > reach)
                       and mobs.hex_distance(cell, home, loc.width) <= 30
                       and mobs.line_of_fire(loc, cell, home) is None)
        if not spots:
            continue
        goal = spots[0][1]
        path = mobs.find_path(loc, pos, lambda cell: cell == goal, wary, limit=20000)
        if path is None and goal != pos:
            continue
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
        out += c.frames(0.15 * len(path or [0]) + 0.8)
        pos = goal
        for _ in range(20):
            c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
            got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                           or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
            out += got_
            if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                return out, eid, pos, home, wary
            time.sleep(0.3)
        break
    return out, None, pos, None, frozenset()


def loot(c, fight, loc_id, pos, near, wary=frozenset()):
    """Open the bag nearest `near`, take all of it: the types it held."""
    loc = world.location(loc_id)
    got = list(fight)
    if not [p for p in named(got, "ss_loot") if p.get("s_status") == 1]:
        got += c.until(lambda f: f[0] == "ss_loot" and f[1].get("s_status") == 1, 6)
    bags = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    if not bags:
        return None
    bag = min(bags, key=lambda cell: mobs.hex_distance(cell, near, loc.width))
    path = mobs.find_path(loc, pos, lambda cell: cell == bag or progression.within_reach(
        cell, bag, loc.width, loc.height), set(wary), limit=20000)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
    c.frames(0.2 * len(path or [pos]) + 1.0)
    c.send("ss_create;s_type=0;target=%d;" % bag)
    if acks(c.frames()) != [0]:
        return None
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
    types = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return types, (path[-1] if path else pos)


def rewind(cid, qtype, seconds):
    """The history of a hand-in moved back in time (a cooldown waited out)."""
    st = accounts.Store(DB)
    st.db.execute("UPDATE char_quests_done SET done_at = done_at - ? WHERE char_id = ?"
                  " AND type = ?", (int(seconds), cid, qtype))
    st.db.commit()
    st.close()


try:
    # --- a miner: mining, sorting, the base, the factory ------------------------------------
    c = login("miner", "Miner")
    logout(c)
    reshape("Miner", 6)
    c = login("miner", "Miner", first_time=False)
    MINER_ID = cid_of("Miner")
    check("level 6: the copper mine's gate is offered, and the plant's first rows",
          [status(c, t) for t in (GATES[0], 13008, 13020, 13024)], [1, 1, 1, 1])
    check("  ..not the second lines before their preparation",
          [status(c, t) for t in (13010, 13022, 13026, 13027)], [0, 0, 0, 0])
    here = inhabitants(goto(c, COPPER_TOP))
    got, q = take(c, here, GATE_COPPER, GATES[0])
    call, arrival = moved(c, hand_in(c, here, GATE_COPPER, q))
    check("the gate: down to the control room", call.get("id"), COPPER_ROOM)
    res, call, arrival = through(c, COPPER_ROOM, "b")
    check("  ..its door into the first tier", (res, call.get("id")), ([0], COPPER_1))
    here = inhabitants(arrival)
    check("  ..where twenty rocks of copper stand to be broken, and no panel",
          (len(here.get(1316, [])), len(here.get(PANEL, []))), (20, 0))
    gun = arm(c)
    before = industry(MINER_ID)
    pos = first(arrival, "lenter").get("pos")
    fight, rock, pos, fell, wary = hunt(c, arrival, COPPER_1, gun, 1316, pos)
    check("a rock shot with a gun breaks (a creature of the object role)", bool(rock), True)
    bag = loot(c, fight, COPPER_1, pos, fell, wary)
    check("  ..its bag holds one piece of (ВХ) copper ore and nothing else",
          bag[0] if bag else None, [ORE["copper"]])
    have = held(MINER_ID)
    check("  ..now in the miner's bag", have[ORE["copper"]], 1)
    after = industry(MINER_ID)
    check("  ..and nothing learned from it (production.MINING_PAYS_XP off)",
          (after[0] * 10 ** 6 + after[1]) - (before[0] * 10 ** 6 + before[1]), 0)
    give(c, ORE["copper"], 9)
    res, call, arrival = through(c, COPPER_1, "a")
    check("back to the control room by the tier's door a", (res, call.get("id")),
          ([0], COPPER_ROOM))
    here = inhabitants(arrival)
    got, q = take(c, here, 1367, 13008)
    check("«Сортировка» at the copper terminal: ten pieces in the bag, complete at once",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, 1367, q)
    have = held(MINER_ID)
    check("  ..handed in: the ten pieces gone, 150 parts of sorted copper in the bag",
          (acks(got), have[ORE["copper"]], have[SORTED["copper"]]), ([0], 0, 150))
    check("  ..the sorting rests not: offered again", status(c, 13008), 1)
    here = inhabitants(goto(c, BASE))
    got, q = take(c, here, LINES["copper"], 13020)
    got = hand_in(c, here, LINES["copper"], q)
    have = held(MINER_ID)
    check("the base's case line: the 150 parts into three boxes of cases",
          (acks(got), have[SORTED["copper"]], have[SACK["copper"]]), ([0], 0, 3))
    check("  ..and the line rests: not offered again at once (cooldown)", status(c, 13020), 0)
    rewind(MINER_ID, 13020, 1199)
    check("  ..nor a second before the twenty minutes are out", status(c, 13020), 0)
    rewind(MINER_ID, 13020, 2)
    check("  ..and offered again once they are", status(c, 13020), 1)
    give(c, SACK["plumbum"], 3)
    give(c, SACK["nitre"], 12)
    give(c, SACK["copper"], 6)
    here = inhabitants(goto(c, FACTORY))
    got, q = take(c, here, ASSEMBLER, 13024)
    got = hand_in(c, here, ASSEMBLER, q)
    have = held(MINER_ID)
    check("the factory's 12-gauge line: 3 + 12 + 9 sacks into 600 rounds of 12-gauge КС",
          (acks(got), have[KS_12], have[SACK["plumbum"]], have[SACK["nitre"]],
           have[SACK["copper"]]), ([0], 600, 0, 0, 0))
    check("  ..and no (P) round in the bag", [t for t in have if items.premium(t)], [])
    check("  ..the line rests", status(c, 13024), 0)
    give(c, SACK["plumbum"], 12)
    give(c, SACK["nitre"], 48)
    give(c, SACK["copper"], 36)
    got, q = take(c, here, ASSEMBLER, 13025)
    got = hand_in(c, here, ASSEMBLER, q)
    check("«Подготовить вторую линию сборки 12мм.»: 2400 rounds, and once only",
          (acks(got), held(MINER_ID)[KS_12], status(c, 13025)), ([0], 3000, 0))
    check("  ..the two lines and the gold one now offered", [status(c, t) for t in (13026, 13027)],
          [1, 1])
    logout(c)
    st = accounts.Store(DB)
    afro0 = st.character(MINER_ID)["afro"]
    st.set_money(MINER_ID, afro0, 10)
    st.close()
    c = login("miner", "Miner", first_time=False)
    here = inhabitants(goto(c, FACTORY))
    give(c, SACK["plumbum"], 6)
    give(c, SACK["nitre"], 24)
    give(c, SACK["copper"], 18)
    got, q = take(c, here, ASSEMBLER, 13027)
    got = hand_in(c, here, ASSEMBLER, q)
    check("the gold line: 0.02 G taken, 1500 rounds", (acks(got), purse(MINER_ID),
                                                       held(MINER_ID)[KS_12]),
          ([0], (afro0, 8), 4500))
    st = accounts.Store(DB)
    fees = [(r["source"], r["ref"], r["afro"], r["gold"]) for r in st.db.execute(
        "SELECT * FROM money_ledger WHERE char_id = ? AND ref = 13027", (MINER_ID,))]
    st.close()
    check("  ..booked in the money ledger", fees, [("quest", 13027, 0, -2)])
    logout(c)
    reshape("Miner", 9)
    c = login("miner", "Miner", first_time=False)
    check("past the band (level 9): no gate, no plant", [status(c, t) for t in (GATES[0], 13008,
                                                                                13020, 13024)],
          [0, 0, 0, 0])
    logout(c)
    c = login("novice", "Novice")
    check("below it (level 0): none either", [status(c, t) for t in (GATES[0], 13000, 13012,
                                                                     13028)], [0, 0, 0, 0])
    logout(c)
except Exception:
    import traceback
    fails.append("the miner broke:\n" + traceback.format_exc())

try:
    # --- a raider: the Вади-Хальфа mine --------------------------------------------------
    c = login("raider", "Raider")
    logout(c)
    RAIDER = cid_of("Raider")
    reshape("Raider", 8)
    st = accounts.Store(DB)
    st.finish_quest(0, RAIDER, SHAWARMA)
    st.close()
    c = login("raider", "Raider", first_time=False)
    here = inhabitants(goto(c, STATION))
    got, q_ring = take(c, here, OLD_WOMAN, CINEMA)
    check("«Индийское кино ч.1» taken from the old woman at the station", acks(got), [0])
    here = inhabitants(goto(c, MARKET))
    check("«Просьба о помощи» offered by Фрэнк after the shawarma", status(c, RAID), 1)
    got, q_raid = take(c, here, FRANK, RAID)
    check("  ..taken: nought of five miners", named(got, "q_di_kill_mobs")[0]["kill_num"], [0])
    gun = arm(c)
    arrival = goto(c, 154)
    check("the mine's first entrance stands its Ефрейторы, away from its door",
          len(inhabitants(arrival).get(CORPORAL, [])), 5)
    res, call, arrival = through(c, 154, "b")
    check("  ..and its drawn door leads down to the first tier", (res, call.get("id")),
          ([0], 613))
    ring, kills, tier, done = False, 0, 613, set()
    pos = first(arrival, "lenter").get("pos")
    for _ in range(40):
        fight, eid, pos, fell, wary = hunt(c, arrival, tier, gun, MINER, pos, done)
        if not eid:
            if tier == 613:
                res, call, arrival = through(c, 613, "b")
                check("  ..the first tier's door b down into the second tier's middle",
                      (res, call.get("id")), ([0], 1024))
                tier = 1024
                pos = first(arrival, "lenter").get("pos")
            elif tier == 1024:
                # On east along the gallery rather than wait out the mine's
                # slow respawn: its east end, 1012, has seven more.
                res, call, arrival = through(c, 1024, "E")
                check("  ..and on east by the gallery's side into its east end",
                      (res, call.get("id")), ([0], 1012))
                tier = 1012
                pos = first(arrival, "lenter").get("pos")
            else:
                # the fallen are back (LAVA_RESPAWN, the mine's slower clock)
                time.sleep(float(env["LAVA_RESPAWN"]) * combat.SLOW_RESPAWN[tier]
                           / combat.RESPAWN_DEFAULT + 1)
            done = set()
            continue
        kills += 1
        done.add(eid)
        if not ring:
            bag = loot(c, fight, tier, pos, fell, wary)
            if bag:
                ring = RING in bag[0]
                pos = bag[1]
        if kills >= 5 and ring:
            break
    got = c.frames(0.5)
    check("five miners shot and the ring found on one of them", (kills >= 5, ring,
                                                                  held(RAIDER)[RING]),
          (True, True, 1))
    st = accounts.Store(DB)
    raid = [json.loads(r["progress_json"]) for r in st.quests(RAIDER) if r["type"] == RAID]
    st.close()
    check("  ..the raid counts them", raid[0]["kill_num"], [5])
    if tier == 1012:
        res, call, arrival = through(c, 1012, "W")
        check("back west from the gallery's east end into its middle", (res, call.get("id")),
              ([0], 1024))
        tier = 1024
    if tier == 1024:
        res, call, arrival = through(c, 1024, "a")
        check("up from the second tier by its door a, to the first", (res, call.get("id")),
              ([0], 613))
    res, call, arrival = through(c, 613, "a")
    check("  ..and up the first tier's door a to the entrance, on its own cell",
          (res, call.get("id"), call.get("g_id", 0) & ((1 << 26) - 1)),
          ([0], 154, (VH_TOP[154][0] << 13) | VH_TOP[154][1]))
    arrival = goto(c, 1016)
    walked = []
    for here_, nxt in zip(VH_GALLERY, VH_GALLERY[1:]):
        res, call, arrival = through(c, here_, "E")
        walked.append((res, call.get("id")))
    check("the second tier walked east by its sides, 1016 to 1012 through the tunnels and 1024",
          walked, [([0], t_) for t_ in VH_GALLERY[1:]])
    res, call, arrival = through(c, 1012, "a")
    check("  ..whose door goes up to the first tier's other file", (res, call.get("id")),
          ([0], 617))
    res, call, arrival = through(c, 617, "a")
    check("  ..and up to the second entrance, on its cell",
          (res, call.get("id"), call.get("g_id", 0) & ((1 << 26) - 1)),
          ([0], 158, (VH_TOP[158][0] << 13) | VH_TOP[158][1]))
    arrival = goto(c, 1016)
    res, call, arrival = through(c, 1016, "a")
    check("a door up into the third entrance lands on its own cell, whichever way one came",
          (res, call.get("id"), call.get("g_id", 0) & ((1 << 26) - 1)),
          ([0], 160, (VH_TOP[160][0] << 13) | VH_TOP[160][1]))
    here = inhabitants(goto(c, MARKET))
    afro0, gold0 = purse(RAIDER)
    got = hand_in(c, here, FRANK, q_raid)
    check("the raid handed in to Фрэнк: 1000 afro and 0.05 G",
          (acks(got), purse(RAIDER)[0] - afro0, purse(RAIDER)[1] - gold0), ([0], 1000, 5))
    here = inhabitants(goto(c, STATION))
    got = hand_in(c, here, OLD_WOMAN, q_ring)
    check("  ..and the ring to the old woman: 5000", (acks(got), purse(RAIDER)[0] - afro0),
          ([0], 6000))
    logout(c)
except Exception:
    import traceback
    fails.append("the raider broke:\n" + traceback.format_exc())

try:
    # --- a quarry worker: the polishing mix, the blocks ---------------------------------
    c = login("mason", "Mason")
    logout(c)
    MASON = cid_of("Mason")
    reshape("Mason", 6)
    c = login("mason", "Mason", first_time=False)
    here = inhabitants(goto(c, QUARRY_N))
    got, q = take(c, here, SAM, MIX_Q)
    check("«Создать Полировочную смесь» taken from Большой Сэм", acks(got), [0])
    gun = arm(c)
    arrival = goto(c, QUARRY_C)
    pos = first(arrival, "lenter").get("pos")
    found = collections.Counter()
    done = set()
    for _ in range(16):
        fight, eid, pos, fell, wary = hunt(c, arrival, QUARRY_C, gun, STONE, pos, done)
        if not eid:
            break
        done.add(eid)
        bag = loot(c, fight, QUARRY_C, pos, fell, wary)
        if bag:
            found.update(t for t in bag[0] if t in PARTS)
            pos = bag[1]
        if len(found) == 4:
            break
    check("the quarry's stones drop the components for the one who wants them",
          bool(found) and all(n == 1 for n in found.values()), True)
    for p_ in PARTS:
        if not held(MASON)[p_]:
            give(c, p_, 1)
    here = inhabitants(goto(c, QUARRY_N))
    got = hand_in(c, here, SAM, q)
    have = held(MASON)
    check("  ..mixed: the four components gone, the polishing mix in the bag",
          (acks(got), [have[p_] for p_ in PARTS], have[MIX]), ([0], [0, 0, 0, 0], 1))
    afro0 = purse(MASON)[0]
    got, q = take(c, here, SAM, POLISHED)
    give(c, BLOCK, 10)
    got = hand_in(c, here, SAM, q)
    have = held(MASON)
    check("«Полированные камни.»: ten blocks and the mix for 255",
          (acks(got), purse(MASON)[0] - afro0, have[BLOCK], have[MIX]), ([0], 255, 0, 0))
    here = inhabitants(goto(c, SITE))
    paid = []
    for _ in range(3):
        a0 = purse(MASON)[0]
        got, q = take(c, here, VARON, FOUNDATION)
        give(c, BLOCK, 10)
        got = hand_in(c, here, VARON, q)
        paid.append((acks(got), purse(MASON)[0] - a0))
    check("Варон's «Камни для фундамента» at the building site: 200 for ten blocks, thrice",
          paid, [([0], 200)] * 3)
    check("  ..and not a fourth time today", status(c, FOUNDATION), 0)
    a0 = purse(MASON)[0]
    got, q = take(c, here, VARON, POLISHED_V)
    give(c, BLOCK, 10)
    give(c, MIX, 1)
    got = hand_in(c, here, VARON, q)
    check("  ..his «Полированные Камни»: 360", (acks(got), purse(MASON)[0] - a0), ([0], 360))
    st = accounts.Store(DB)
    booked = sorted({(r["source"], r["ref"]) for r in st.db.execute(
        "SELECT * FROM money_ledger WHERE char_id = ? AND source = 'quest'", (MASON,))})
    st.close()
    check("  ..every payment booked in the money ledger", booked,
          [("quest", POLISHED), ("quest", FOUNDATION), ("quest", POLISHED_V)])
    logout(c)
except Exception:
    import traceback
    fails.append("the mason broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    try:
        srv.wait(10)
    except subprocess.TimeoutExpired:
        srv.kill()

with open(LOG, encoding="utf-8", errors="replace") as fh:
    tb = [line for line in fh if "Traceback" in line]
check("the server logged no traceback", tb, [])

if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    print("server log: %s" % LOG)
    sys.exit(1)
print("\nall ok")
