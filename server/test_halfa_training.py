"""Вади-Хальфа's schools and workplaces (halfa-training-ways, types
351-413): Берт Гаммер's course in his bunker, the newest edition's, and
Мастер Тиль's six trainings it opens; the base of Magrib's self-teachers
and exams; Равшан's quarry and its pits; the gates of the town's three ore
mines and the doors of their tiers; the boat to Заречье, built and switched
off, and since the cut of the camps across the river (2026-10-12) without
its ways: the camp 429 it rowed to is out of the game.

In process: the rows and their texts (the original's, pinned in
data/build_orig_misc.py VERIFIED, laid over), the chain, what each lesson
counts against what its range stands and what its start says, what is lent
and what the lent things are (no stall, barter, letter or lot), where the
lent things stay (stay_in), the training guns chambering the Tir's rounds
alone and no other gun taking them, the pick's 8 action points a strike,
the ways of data/passages.json with their cells, every door row beside the
sign it follows, the quarry's sides (data/passages.json 'sides',
travel.plan_exit), the bunker and the quarry with no way to the map
('no_map', travel.geo_id) and no exit leading out, the gates' levels, the
exams' fees and experience, and the boat off in the shipped table, its
rows kept and its ways gone.

On a socket:

  * a newcomer (level 0) takes «Тир Берта Гаммера» from Берт at the market
    and lands in TIR_00, told it is a sublocation; the seven lessons, one
    range each: the training gun and rounds lent at the take, the gun in
    hand loaded with those rounds -- his own «9мм даренные» do not fit --
    the targets shot from the booth with them alone (more of the Tir's
    rounds asked for when they run out) and counted, the gun
    and rounds taken back at the hand-in, the way on; the map button
    refused in the range; the free rounds of «Получить боеприпасы»; the
    last lesson pays the certificate and brings him back to the market,
    and the course is not offered again; Мастер Тиль then takes the
    certificate for «Охотник»: a part of the self-teacher chosen and the
    coin beside it;
  * another breaks the course off in TIR_01, the map button refused first:
    back at the market, no second chance, the pistol and the rounds taken
    back on the way out (stay_in), the lesson still his until dropped;
  * a worker (level 6): the ore mine's gate lets him in, the doors of the
    tiers by their signs, the way up; the quarry: Равшан's contract into
    the north pit, the map button refused, ten blocks for 140 with the pick
    lent and taken back, the pits by their sides with the pick along; the
    pick never turned on a rival in the pit, a stone broken with it in one
    blow for 8 action points; felled by the rival, he wakes at home without
    the pick, the work still his; back in, and out by «Покинуть
    каменоломню.» with the work open: the pick taken back on the way out;
  * a scholar with the pistols specialisation: «Самоучители», the exam for
    afro -- not complete while the purse is short, 25 000 taken, the book
    used up, experience into the specialisation and the skill -- and the one
    for gold; an exam whose specialisation is not open is not offered.

    LAVA_RES=.../lava/res python3 server/test_halfa_training.py
"""
import collections
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
# A quest type no table has: Client.sync's beacon.
BEACON = 999999
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_START_AFRO"):
    os.environ.pop(_knob, None)

# The places.
MARKET, BLACK_MARKET, BASE, PIER, CAMP = 35, 102, 52, 41, 429
RANGE = [732, 1048, 1233, 1260, 1276, 1280, 1282]            # TIR_00..06
QUARRY_N, QUARRY_C, QUARRY_S, QUARRY_W, QUARRY_E = 627, 626, 628, 629, 630
COPPER_TOP, LEAD_TOP, NITRE_TOP = 200, 202, 201
COPPER_ROOM, LEAD_ROOM, NITRE_ROOM = 657, 658, 659
COPPER_1, COPPER_2, COPPER_3 = 1025, 1218, 1255
# The quests.
COURSE = 1682
LESSONS = list(range(351, 358))
ABORTS = list(range(358, 365))
AMMO_Q, AUTOMATCHIK, SELF_TEACHERS = 365, 366, 367
ASSEMBLE = list(range(368, 379))
EXAMS_A, EXAMS_G = list(range(379, 390)), list(range(390, 401))
# Exam quests keep their own levels; only initial specialisation learning was opened.
EXAM_LEVELS = [0, 0, 0, 4, 12, 6, 16, 8, 0, 0, 0, 0, 0, 0, 0]
QUARRY_IN, QUARRY_OUT, BLOCKS_10, BLOCKS_30, ANKH_Q = range(401, 406)
MINES_IN, MINES_OUT = [406, 407, 408], [409, 410, 411]
BOAT_OUT, BOAT_BACK = 412, 413
TRAININGS = [4, 1829, 1895, 1971, 2128, AUTOMATCHIK]
ALL = LESSONS + ABORTS + [AMMO_Q, AUTOMATCHIK, SELF_TEACHERS] + ASSEMBLE + EXAMS_A + EXAMS_G \
    + [QUARRY_IN, QUARRY_OUT, BLOCKS_10, BLOCKS_30, ANKH_Q] + MINES_IN + MINES_OUT \
    + [BOAT_OUT, BOAT_BACK]
# Who gives them.
BERT, BERT_TI = 2088, [2089, 2090, 2091, 2092, 2093, 2094, 2095]
TIL, WATCHER, ASSEMBLER = 5, 72, 6764
KASIM, SEYID, UMAR, RAIS = 718, 719, 858, 859
RAVSHAN, SAM = 978, 979
ONEILL, DOBERMAN = 5685, 5694
# The things.
ROUNDS, GUNS, CERT, COIN = 3727, [3728, 3729, 3730, 3731, 3732, 3733], 3742, 46652
PICK, BLOCK, ANKH, STONE = 2943, 2944, 3186, 977
TARGETS = [1397, 1398, 1399, 1400, 1401, 1402]              # nz_Target1..6
PISTOLS_BOOK, SHOTGUN_PARTS = 4312, list(range(5065, 5071))
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
DESIGNED_TEXTS = MINES_IN + MINES_OUT                       # no line of the original
NUMBER = {"три": 3, "одну": 1}

# The table as shipped: the boat off. Until 2026-10-12 the run switched it
# on and rowed over to the camp 429 and back; the camp is out of the game
# since the owner's «убери во всех городах лагеря за рекой», and the boat's
# ways with it (server/test_river_camps_cut.py).
with open(os.path.join(ROOT, "data", "quests.json"), encoding="utf-8") as _fh:
    _TABLE = json.load(_fh)
BOAT_SHIPPED = [(r["give"], r["take"]) for r in _TABLE["quests"]
                if r["type"] in (BOAT_OUT, BOAT_BACK)]
with open(os.path.join(ROOT, "data", "retired.json"), encoding="utf-8") as _fh:
    RETIRED_PLACES = json.load(_fh)["places"]

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def spawned(loc_id):
    """type -> count of what a location's file stands (objects only where
    world.STANDING_OBJECTS lets them)."""
    loc = world.location(loc_id)
    out = collections.Counter()
    for _c, t in loc.spawns:
        if world.creature_role(t) == "object" and t not in world.STANDING_OBJECTS.get(loc_id, ()):
            continue
        out[t] += 1
    return out


def zones_of(loc):
    return {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)), "zones", 4)}


SIGN = re.compile(r'<sprite id="((?:W_Pointer_\w+|W_ladder\w*|DN_Backdoor\w+)\.png)"[^>]*>'
                  r'([0-9a-f]*)</sprite>')


def signs(loc):
    """[(sprite, cell)] of the pointers, ladders and drawn doors of a file."""
    out = []
    for m in SIGN.finditer(world._read(world.path_for(loc.id))):
        body = m.group(2)
        for i in range(0, len(body) - 3, 4):
            out.append((m.group(1)[:-4], int(body[i + 2:i + 4], 16) * loc.width
                        + int(body[i:i + 2], 16)))
    return out


# --- in process: the rows -----------------------------------------------------------------
MT = world.mob_types()
try:
    check("the shipped table has the boat switched off: nobody gives or takes it",
          BOAT_SHIPPED, [([], []), ([], [])])
    check("  ..and its ways are gone with the camp 429 (data/passages.json): neither row moves anybody,"
          " and the camp is out of the game",
          ([travel.is_quest_way(t) for t in (BOAT_OUT, BOAT_BACK)],
           travel.quest_way(world.location(PIER), BOAT_OUT), travel.quest_way(world.location(CAMP), BOAT_BACK),
           str(CAMP) in RETIRED_PLACES),
          ([False, False], None, None, True))
    check("the package's rows are all there, 351-413",
          [t for t in ALL if quests.get(t) is None], [])
    check("  ..and rows 4, 1682, 1829, 1895, 1971, 2128 no longer carry the importer's mark",
          [r["type"] for r in _TABLE["quests"]
           if r["type"] in [COURSE] + TRAININGS and "wiki_type" in r], [])
    check("  ..every row says what is the original's and what is ours",
          [t for t in ALL + [COURSE] + TRAININGS
           if not re.search(r"RECOVERED|DESIGNED", next(r for r in _TABLE["quests"]
                                                     if r["type"] == t).get("why", ""))], [])
    with open(os.path.join(ROOT, "data", "orig_misc.json"), encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    orig = orig_texts.quests()
    check("the texts are the original's (data/orig_misc.json), but the ore mines' gates",
          sorted(t for t in ALL + [COURSE] + TRAININGS if t not in pinned), DESIGNED_TEXTS)
    check("  ..laid over the table's",
          [t for t in pinned if t in ALL + [COURSE] for k, key in
           enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and quests.get(t).texts[k] != quests.served(quests.get(t), k, orig[t][key])], [])
    check("  ..the course the newest edition's: free, for levels 0-5, no letter",
          (pinned[COURSE], "0- 5 Уровня" in quests.get(COURSE).texts[1],
           "письма" in "".join(quests.get(COURSE).texts), quests.get(COURSE).texts[2]),
          ([41446, 59767, None, 59768], True, False, ""))
    check("  ..the lessons' starts the newest edition's (59769-59778), the abort's «второго "
          "шанса не будет», the rounds free",
          ([pinned[t][1] for t in LESSONS], "второго шанса не будет" in quests.get(ABORTS[0]).texts[1],
           "сегодня" in quests.get(ABORTS[0]).texts[1], pinned[AMMO_Q]),
          ([59769, 59770, 59771, 59773, 59774, 59776, 59778], True, False,
           [59782, 59783, None, 59784]))

    # The course.
    course = quests.get(COURSE)
    check("«Тир Берта Гаммера»: Берт at the market, a way into TIR_00, one-off, no level asked,"
          " nothing paid",
          (course.give, course.take, course.kind, course.obj, course.repeatable, course.level,
           course.max_level, course.rew_obj, course.rew_afro, course.rew_loc, course.need_all),
          ([BERT], [BERT], quests.DEL_OBJ, 0, 0, 0, None, [], 0, 1, []))
    check("  ..its way from the market to TIR_00",
          (travel.quest_way(world.location(MARKET), COURSE) or {}).get("target_loc_id"), RANGE[0])
    for k, (t, loc_id) in enumerate(zip(LESSONS, RANGE)):
        q = quests.get(t)
        nxt = RANGE[k + 1] if k + 1 < len(RANGE) else MARKET
        check("lesson %d (%d): Берт's copy in TIR_0%d gives and takes it, one-off, after the %s,"
              " a way on to %d" % (k + 1, t, k, "course" if not k else "lesson before", nxt),
              (q.give, q.take, q.repeatable, q.need_all, q.rew_loc,
               (travel.quest_way(world.location(loc_id), t) or {}).get("target_loc_id")),
              ([BERT_TI[k]], [BERT_TI[k]], 0, [COURSE if not k else t - 1], 1, nxt))
        if not k:
            check("  ..the theory: a talk, complete once taken", (q.kind, q.obj,
                                                                  q.is_complete(q.fresh_progress())),
                  (quests.DEL_OBJ, 0, True))
            continue
        told = collections.Counter()
        task = q.texts[1][q.texts[1].find("Задача"):]
        for word, num in re.findall(r"(три|одну)\s+(?:цел\w*\s+)?(?:под\s+)?№\s*(\d)", task):
            told[TARGETS[int(num) - 1]] += NUMBER[word]
        stands = spawned(loc_id)
        check("  ..counts the kills its start asks (%s)" % task[:60].replace("\n", " "),
              dict(zip(q.mobs_kill, q.num_kill)), dict(told))
        check("  ..and TIR_0%d stands exactly those targets" % k,
              {tt: n for tt, n in stands.items() if tt in TARGETS}, dict(told))
        check("  ..lending the lesson's training gun and a hundred rounds, kept in TIR_0%d"
              " (stay_in)" % k,
              (q.start_obj, sorted(q.lent), q.returns(), sorted(q.stay_in)),
              ([(GUNS[k - 1], 1), (ROUNDS, 100)], sorted([GUNS[k - 1], ROUNDS]),
               [(GUNS[k - 1], 1), (ROUNDS, 100)], [loc_id]))
    last = quests.get(LESSONS[-1])
    check("the last lesson pays the certificate and leads back to the market",
          (last.rew_obj, last.num_rew_obj,
           (travel.quest_way(world.location(RANGE[-1]), LESSONS[-1]) or {}).get("target_loc_id")),
          ([CERT], [1], MARKET))
    for k, (t, loc_id) in enumerate(zip(ABORTS, RANGE)):
        q = quests.get(t)
        check("«Прервать обучение» in TIR_0%d (%d): one-off, a way back to the market" % (k, t),
              (q.give, q.take, q.kind, q.repeatable, q.per_day, q.rew_loc,
               (travel.quest_way(world.location(loc_id), t) or {}).get("target_loc_id")),
              ([BERT_TI[k]], [BERT_TI[k]], quests.DEL_OBJ, 0, 0, 1, MARKET))
    ammo = quests.get(AMMO_Q)
    check("«Получить боеприпасы»: Берт's copies with the targets hand out a hundred rounds, free,"
          " a service", (ammo.give, ammo.rew_also, ammo.cost_afro, ammo.service, ammo.repeatable,
                         travel.is_quest_way(AMMO_Q)),
          (BERT_TI[1:], [(ROUNDS, 100)], 0, True, 1, False))
    check("what the course lends is the quest's: the quest flag, no exchange, kept at a death,"
          " not thrown down, sold at no stall",
          [(t, quests.lent(t), items.params_of(t)["quest"], items.params_of(t)["exchang"],
            quests.kept_on_death(t), quests.not_on_ground(t)) for t in GUNS + [ROUNDS, PICK]],
          [(t, True, 1, 0, True, True) for t in GUNS + [ROUNDS, PICK]])
    sold = {t for trader in set(items.stock_table()) | set(npcs.STOCK)
            for t in items.stock_for(trader)}
    check("  ..and the table passes the server's own check (quests.check_items)",
          (sorted(set(GUNS + [ROUNDS, PICK]) & sold), quests.check_items()), ([], None))
    # The training guns take the Tir's own rounds and nothing else, each of
    # the class its lesson teaches; no other gun takes those rounds.
    CLASSES = [items.PISTOL, items.SHOTGUN, items.SMG, items.ASSAULT, items.MACHINEGUN,
               items.RIFLE]
    check("the training guns: one of each class the lessons teach, chambering the Tir's rounds"
          " alone («особыми пулями кал. 5,6 мм», texts.xml 1815)",
          [(items.params_of(g)["weapon_type"], items.params_of(g)["comp_array"]) for g in GUNS],
          [(k, [ROUNDS]) for k in CLASSES])
    check("  ..and no other gun takes them («только в специальном, тренировочном оружии», 1095)",
          [t for t, (root, _n) in sorted(items.catalogue().items())
           if root == items.FIRE_ARM and t not in GUNS
           and ROUNDS in ((items.params_of(t) or {}).get("comp_array") or [])], [])
    pick = items.params_of(PICK)
    check("the pick: the article's 2250-2750 and reach, and 8 action points a strike, not the"
          " article's 0 (data/coldarm_manual.json)",
          (pick["h_damage_min"], pick["h_damage_max"], pick["max_range"], pick["strike_cost"]),
          (2250, 2750, 1.7, 8))

    # Мастер Тиль.
    for t in TRAININGS:
        q = quests.get(t)
        check("Тиль's %s (%d): the certificate for one of six self-teacher parts, the coin beside,"
              " after the course's last lesson" % (q.name, t),
              (q.give, q.take, q.wants(), len(q.rew_obj), q.rew_also, q.need_all,
               [items.params_of(p) is not None for p in q.rew_obj]),
              ([TIL], [TIL], [(CERT, 1)], 6, [(COIN, 1)], [LESSONS[-1]], [True] * 6))
    check("  ..the parts are those of the assemblies of the base",
          {p for t in TRAININGS for p in quests.get(t).rew_obj}
          <= {o for t in ASSEMBLE for o, _n, _m in quests.get(t).objs}, True)

    # The base of Magrib.
    st = quests.get(SELF_TEACHERS)
    check("«Самоучители»: Часовой, a talk, one-off",
          (st.give, st.kind, st.repeatable, st.is_complete(st.fresh_progress())),
          ([WATCHER], quests.DEL_OBJ, 0, True))
    for t in ASSEMBLE:
        q = quests.get(t)
        check("assembly %d: six parts at Бюльбюль-Оглы for a self-teacher, 25 000 afro, a service"
              % t, (q.give, len(q.objs), sorted({n for _o, n, _m in q.objs}), q.cost_afro,
                    q.service, q.repeatable, [items.root_of(b) for b in q.rew_obj]),
              ([ASSEMBLER], 6, [1], 25000, True, 1, [items.TRASH]))
    for t in EXAMS_A + EXAMS_G:
        q = quests.get(t)
        gold = t in EXAMS_G
        spec = q.requires_spec[0] if q.requires_spec else None
        check("exam %d: at the base, the book asked, %s, spec experience, its spec asked, its"
              " level, after «Самоучители»" % (t, "1 ounce" if gold else "25 000 afro"),
              (q.give[0] in (KASIM, SEYID, UMAR, RAIS), q.kind, len(q.objs),
               (q.cost_afro, q.cost_gold), [s for s, _xp in q.rew_spec_xp],
               [xp for _s, xp in q.rew_spec_xp], [xp for _s, xp in q.rew_xp],
               [s for s, _xp in q.rew_xp] == ([] if gold else [progression.SPEC_SKILL[spec]]),
               q.level, q.need_all, q.service),
              (True, quests.BRING_L_OBJ, 1, (0, 100) if gold else (25000, 0), [spec],
               [80000] if gold else [40000], [] if gold else [40000], True,
               EXAM_LEVELS[spec], [SELF_TEACHERS], True))

    # The quarry.
    q_in, q_out = quests.get(QUARRY_IN), quests.get(QUARRY_OUT)
    check("the quarry: Равшан's contract, levels 6-10, a way into the north pit; Сэм's way out,"
          " no level", ((q_in.give, q_in.level, q_in.max_level,
                         travel.quest_way(world.location(PIER), QUARRY_IN)["target_loc_id"]),
                        (q_out.give, q_out.level, q_out.max_level,
                         travel.quest_way(world.location(QUARRY_N), QUARRY_OUT)["target_loc_id"])),
          (([RAVSHAN], 6, 10, QUARRY_N), ([SAM], 0, None, PIER)))
    QUARRY = sorted([QUARRY_C, QUARRY_N, QUARRY_S, QUARRY_W, QUARRY_E])
    check("  ..Сэм's blocks: 10 for 140 and 30 for 420, the pick lent and kept in the quarry's"
          " five pits (stay_in); the Анкх once a day",
          [(quests.get(t).wants(), quests.get(t).rew_afro, sorted(quests.get(t).lent),
            sorted(quests.get(t).stay_in), quests.get(t).per_day, quests.get(t).service)
           for t in (BLOCKS_10, BLOCKS_30, ANKH_Q)],
          [([(BLOCK, 10)], 140, [PICK], QUARRY, 0, True),
           ([(BLOCK, 30)], 420, [PICK], QUARRY, 0, True),
           ([(ANKH, 1)], 750, [], [], 1, True)])
    check("  ..and no other row of the package keeps what it lends anywhere",
          [t for t in ALL + [COURSE] + TRAININGS if quests.get(t).stay_in
           and t not in LESSONS[1:] + [BLOCKS_10, BLOCKS_30]], [])
    check("  ..the quarry's stones drop the blocks and the Анкх for those who have the work open",
          [d for d in quests.quest_drops(STONE) if d[0] in (BLOCK, ANKH)],
          [(BLOCK, 1.0), (ANKH, 0.05)])
    check("  ..and stand in the four pits, the north pit being Сэм's",
          [spawned(p).get(STONE, 0) > 0 for p in (QUARRY_C, QUARRY_S, QUARRY_W, QUARRY_E,
                                                  QUARRY_N)], [True, True, True, True, False])

    # The ore mines.
    for t_in, t_out, top, room in zip(MINES_IN, MINES_OUT, (COPPER_TOP, LEAD_TOP, NITRE_TOP),
                                      (COPPER_ROOM, LEAD_ROOM, NITRE_ROOM)):
        a, b = quests.get(t_in), quests.get(t_out)
        check("ore mine %d: the gate lets levels 4-8 in, down to %d; the way up asks no level"
              % (top, room),
              ((a.level, a.max_level, a.over_cap(8), a.over_cap(9),
                travel.quest_way(world.location(top), t_in)["target_loc_id"],
                a.give == [s for _c, s in world.location(top).spawns if s in a.give]),
               (b.level, b.max_level, travel.quest_way(world.location(room), t_out)["target_loc_id"],
                b.give == [s for _c, s in world.location(room).spawns if s in b.give])),
              ((4, 8, False, True, room, True), (0, None, top, True)))

    # The ways of the package in data/passages.json: drawn on free ground.
    with open(os.path.join(ROOT, "data", "passages.json"), encoding="utf-8") as fh:
        PASSAGES = json.load(fh)
    for key, rows in sorted(PASSAGES["quest"].items(), key=lambda kv: int(kv[0])):
        loc = world.location(int(key))
        zones = zones_of(loc)
        for rec in rows:
            if rec["quest"] not in ALL + [COURSE]:
                continue
            way = {y * loc.width + x for x, y in rec["cells"]}
            check("%s: the way of quest %d on ground a walker stands on, no window, nobody"
                  " arrives there, with its reason" % (key, rec["quest"]),
                  (sorted(way & loc.obstacles), sorted(way & zones), sorted(way & set(loc.entries)),
                   len(way), rec.get("why", "").startswith(("RECOVERED", "DESIGNED"))),
                  ([], [], [], len(rec["cells"]), True))

    # Every door followed by the table stands beside its sign; the ore mines'
    # doors by the sign's own word.
    for key, doors in sorted(PASSAGES["doors"].items(), key=lambda kv: int(kv[0])):
        loc = world.location(int(key))
        for side, rec in sorted(doors.items()):
            if rec.get("source") == "designed":
                continue            # no sign to follow: test_halfa_production holds those
            if rec.get("source") == "editor":
                continue            # a place of ours, the owner's: tools/test_location_editor.py holds those
            cells = [c for c, s in travel.exit_sides(loc).items() if s == side]
            near = sorted({name for name, cell in signs(loc)
                           if min(mobs.hex_distance(cell, c, loc.width) for c in cells) <= 10})
            check("%s %s: a door the file has, beside a sign (%s), followed to %d"
                  % (key, side, ", ".join(near) or "none", rec["target_loc_id"]),
                  (bool(cells), bool(near), rec["source"],
                   travel.plan_exit(loc, cells[0], 5965, 1728).loc_id if cells else None),
                  (True, True, "sign", rec["target_loc_id"]))
    DEEPER = {("657", "b"): "W_Pointer_Enter", ("1025", "a"): "W_Pointer_Exit",
              ("1025", "b"): "W_Pointer_Down", ("1218", "a"): "W_Pointer_Up",
              ("1218", "b"): "W_Pointer_Down", ("1255", "a"): "W_Pointer_Up",
              ("658", "b"): "W_Pointer_Enter", ("1027", "a"): "W_Pointer_Exit",
              ("1027", "b"): "W_Pointer_Down", ("1220", "a"): "W_Pointer_Up",
              ("1220", "b"): "W_Pointer_Down", ("1257", "a"): "W_Pointer_Up",
              ("659", "b"): "W_Pointer_Enter", ("1026", "a"): "W_Pointer_Exit",
              ("1026", "b"): "W_Pointer_Down", ("1219", "a"): "W_Pointer_Up",
              ("1219", "b"): "W_Pointer_Down", ("1256", "a"): "W_Pointer_Up"}
    TIERS = {657: 0, 1025: 1, 1218: 2, 1255: 3, 658: 0, 1027: 1, 1220: 2, 1257: 3,
             659: 0, 1026: 1, 1219: 2, 1256: 3}
    for (key, side), word in sorted(DEEPER.items()):
        loc = world.location(int(key))
        cells = [c for c, s in travel.exit_sides(loc).items() if s == side]
        pointers = [sc for sc in signs(loc) if sc[0].startswith("W_Pointer")]
        nearest = min(pointers, key=lambda sc: min(mobs.hex_distance(sc[1], c, loc.width)
                                                   for c in cells))[0]
        target = PASSAGES["doors"][key][side]["target_loc_id"]
        down = word in ("W_Pointer_Enter", "W_Pointer_Down")
        check("ore mine %s %s: the nearest sign says %s, and the door leads %s"
              % (key, side, word[10:], "deeper" if down else "up"),
              (nearest, TIERS[target] - TIERS[int(key)]), (word, 1 if down else -1))

    # The quarry's pits open into each other by their sides, and nowhere else.
    SIDES_WANT = {(QUARRY_C, "N"): QUARRY_N, (QUARRY_C, "S"): QUARRY_S,
                  (QUARRY_C, "W"): QUARRY_W, (QUARRY_C, "E"): QUARRY_E,
                  (QUARRY_N, "S"): QUARRY_C, (QUARRY_S, "N"): QUARRY_C,
                  (QUARRY_W, "E"): QUARRY_C, (QUARRY_E, "W"): QUARRY_C}
    # (The prison's five blocks have theirs too: test_halfa_events; and so
    # do the Вади-Хальфа mine's tiers: test_halfa_production.)
    check("data/passages.json 'sides' has the quarry's five pits, each side the file has",
          sorted((int(k), s) for k, v in PASSAGES["sides"].items()
                 if k != "_" and int(k) in QUARRY for s in v),
          sorted(SIDES_WANT))
    for (lid, side), target in sorted(SIDES_WANT.items()):
        loc = world.location(lid)
        cells = sorted(c for c, s in travel.exit_sides(loc).items() if s == side)
        ex = travel.plan_exit(loc, cells[len(cells) // 2], 5965, 1728)
        dest = world.location(target)
        opposite = travel.OPPOSITE[side]
        check("%d %s leads into %d, arriving over its %s edge, the map cell kept"
              % (lid, side, target, opposite),
              (ex.loc_id, (ex.gx, ex.gy), ex.pos in dest.obstacles,
               ex.pos == travel.arrival_cell(dest, opposite)),
              (target, (5965, 1728), False, True))
    check("a side no row names still leads to the neighbouring map cell (the market's east)",
          travel.plan_exit(world.location(BLACK_MARKET), 638, 5970, 1730)[2:],
          (5971, 1730))

    # Берт's bunker and the quarry have no way to the map: a course walked
    # once and a tool lent for one place are not left behind by a button.
    ENCLOSED = RANGE + QUARRY
    check("data/passages.json 'no_map' holds Берт's bunker and the quarry, each with its reason",
          ([t for t in ENCLOSED if not travel.no_map(t)],
           [k for k, v in PASSAGES["no_map"].items() if k != "_"
            and not v.get("why", "").startswith(("RECOVERED", "DESIGNED"))]), ([], []))
    check("  ..told to the client as a sublocation (the lcall's g_id: z = 1, the cell kept);"
          " the market, Причал and the ore mines not",
          [(travel.geo_id(world.location(t), 5965, 1728) >> 26,
            travel.geo_id(world.location(t), 5965, 1728) & ((1 << 26) - 1))
           for t in ENCLOSED + [MARKET, PIER, COPPER_ROOM]],
          [(1, world.pack(5965, 1728))] * len(ENCLOSED) + [(0, world.pack(5965, 1728))] * 3)
    def leaks(t, s):
        """Whether exit s of location t leads out of the enclosed places: a
        side not into one of them, or a door the server follows."""
        if s in travel.SIDES:
            rec = travel.side_way(t, s)
            return not rec or rec["target_loc_id"] not in ENCLOSED
        rec = travel.door(t, s)
        return bool(rec) and rec.get("target_loc_id") is not None \
            and rec.get("confidence") in travel.DOOR_CONFIDENCE
    check("  ..and no exit of theirs leads out: their sides lead into each other, their doors"
          " nowhere, so the ways out are the quest ways",
          sorted({(t, s) for t in ENCLOSED
                  for _c, s in travel.exit_sides(world.location(t)).items() if leaks(t, s)}),
          [])

    # Whether objects pay experience when broken (data/mob_curves.json role
    # «object», switched by combat.OBJECTS_PAY_XP, the fixups package's):
    # said here so a run shows it.
    with open(os.path.join(ROOT, "data", "mob_curves.json"), encoding="utf-8") as fh:
        _obj = json.load(fh).get("roles", {}).get("object", {})
    print("  NOTE the Tir's targets and the quarry's stones pay kill experience: %s"
          % ("roles.object.xp_mult = %s (data/mob_curves.json)" % _obj.get("xp_mult")
             if combat.OBJECTS_PAY_XP else "none (combat.OBJECTS_PAY_XP)"))
except Exception:
    import traceback
    fails.append("the tables in process broke:\n" + traceback.format_exc())


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "training.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _login in ("cadet", "quitter", "worker", "scholar", "rival"):
    _store.register(_login, "secret")
_store.close()
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_RESPAWN="3",
           LAVA_SEED="11", LAVA_LEAVE_COMBAT="2",
           # The aims at the Tir's targets are some four hundred: at a
           # twentieth of the client's 0.7 s they are seconds, not minutes.
           LAVA_ACTION_SCALE="0.05",
           # The AP come back on the creatures' beat (RoomCombat._step, every
           # AI_TICK), which the scale leaves alone. Fifty a tick kept up with
           # aims of 0.7 s; with aims twenty times quicker the bar runs dry
           # between beats, so one beat has to fill it whole, and shoot()
           # waits out a refusal for want of AP (res=11) as a player would.
           LAVA_AP_REGEN="1000")
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)


def connect(timeout=None):
    return testkit.connect(PORT, srv, LOG, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.seen = []

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
        out = [decode(f.decode(ENC)) for f in parts if f]
        self.seen += out
        return out

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def sync(self, wait=5.0):
        """Everything the server sent for the commands so far, and no more
        waiting than that takes. The server answers one command at a time,
        each handler to its end, so the reply to one more command is behind
        every frame of the ones before it: q_status of a type no table has,
        which changes nothing and is owed a frame (server.cmd_q_status).
        That reply is left out. A frame a timer sends later is not caught
        here: wait for it by name with until()."""
        self.send("q_status;q_type=%d;" % BEACON)
        got = self.until(lambda f: f[0] == "q_status" and f[1].get("type") == BEACON, wait)
        return [f for f in got if not (f[0] == "q_status" and f[1].get("type") == BEACON)]

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
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
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
    return where


def arrive(c):
    c.send("lenter;accept=1;")
    return c.sync()


def goto(c, loc_id):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.sync()
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
    got = c.sync()
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id, obj_idx=0):
    npc = here.get(npc_type, [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.sync()


def moved(c, got, wait=8):
    """The lcall a way's hand-in is followed by (a fight holds it for the
    exit timer), and the arrival's frames: (lcall params, arrival)."""
    call = first(got, "lcall") or first(c.until(lambda f: f[0] == "lcall", wait), "lcall")
    return call, (arrive(c) if call else [])


def way(c, got, wait=8):
    """As moved, with the frames that came before the lcall: (lcall params,
    those frames, the arrival)."""
    if not first(got, "lcall"):
        got = got + c.until(lambda f: f[0] == "lcall", wait)
    order = [n for n, _p in got]
    cut = order.index("lcall") if "lcall" in order else len(got)
    call = got[cut][1] if cut < len(got) else {}
    return call, got[:cut], (arrive(c) if call else [])


def cid_of(name):
    st = accounts.Store(DB)
    row = st.character_by_name(name)
    st.close()
    return row["id"]


def held(cid):
    """type id -> pieces the character has, wherever (bag, hands, body, bank)."""
    st = accounts.Store(DB)
    out = collections.Counter()
    for r in st.items_of(cid):
        out[r["type_id"]] += r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
    st.close()
    return out


def journal(cid):
    st = accounts.Store(DB)
    got = sorted(r["type"] for r in st.quests(cid))
    st.close()
    return got


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


def reshape(name, skill=None, spec=None):
    """A logged-out character's skill level and a learned specialisation."""
    st = accounts.Store(DB)
    ch = progression.Character.load(st, st.character_by_name(name)["id"])
    if skill is not None:
        ch.skill[progression.SHOOTING] = [skill, 0, progression.skill_xp_max(skill)]
    if spec is not None:
        ch.spec[spec] = [0, 0, progression.SPEC_XP_START]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(st)
    st.close()


def oid(cid, type_id):
    """The oid of a thing of a type the character has in the bag or the
    hands -- of a stack, the largest -- or None."""
    st = accounts.Store(DB)
    rows = [r for r in st.items_of(cid) if r["type_id"] == type_id
            and r["slot"] in (inventory.BAG,) + inventory.HAND_SLOTS]
    st.close()
    rows.sort(key=lambda r: -r["count"])
    return inventory.oid_of(rows[0]) if rows else None


def wield(c, thing):
    """Into the hand (primary), whatever was there back into the bag."""
    c.send("ss_get;target=0;slot=11;")
    held_ = [str(x) for x in first(c.sync(), "ss_ack").get("o_list", [])]
    if len(held_) > 6 and held_[6] not in ("0", thing):
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held_[6])
        c.sync()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % thing)
    return acks(c.sync())


def arm(c):
    """The admin gun in hand and loaded: (gun oid, rounds oid)."""
    gun, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 500)
    wield(c, gun)
    load(c, gun, rounds)
    return gun, rounds


def load(c, gun, rounds):
    """Load the gun from the stack: the ack (and the magazine report)."""
    out = []
    for _ in range(100):
        c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, gun))
        got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "cmdAck" and f[1]["res"]), 3)
        got += c.sync()
        if inventory.RES_NO_AP not in acks(got):
            return out + got
        # Reload now pays its own AP cost. As with shooting, wait for the
        # authoritative refill rather than abandoning the training quest.
        out += [f for f in got if f[0] != 'cmdAck']
        out += c.frames(0.1)
    raise AssertionError('AP did not recover for reloading')


def more_rounds(c, arrival, loc_id):
    """«Получить боеприпасы» from Берт's copy in the range: a hundred more of
    the Tir's rounds, free (the frames)."""
    here, npc = inhabitants(arrival), BERT_TI[RANGE.index(loc_id)]
    got, q = take(c, here, npc, AMMO_Q)
    return got + (hand_in(c, here, npc, q) if q else [])


def shoot(c, arrival, loc_id, want, gun, cid, mode=0):
    """Shoot from the booth, over its counter, as many targets of each type
    as want asks (type -> pieces), with the gun in hand in the given fire
    mode, loading it from the character's rounds of the Tir whenever it
    runs dry, and with none left asking Берт for more («Получить
    боеприпасы»), as a player out of them would: the targets teach nothing
    (combat.OBJECTS_PAY_XP), so the newcomer shoots the whole course at
    level 0, and a lesson's hundred may not see its targets down: (the
    fight's frames, the types felled, the aims taken)."""
    loc = world.location(loc_id)
    W = loc.width
    reach = items.params_of(inventory.parse_oid(gun)[1])["max_range"][mode]
    ents = {e: t for t, es in inhabitants(arrival).items() for e in es}
    where = positions(arrival)
    pos = first(arrival, "lenter").get("pos")
    booth, todo = {pos}, collections.deque([pos])
    while todo:
        cur = todo.popleft()
        for nb in progression.hex_neighbours(cur, W, loc.height):
            if nb not in booth and nb not in loc.obstacles and nb not in where.values():
                booth.add(nb)
                todo.append(nb)
    out, felled, shots = [], [], 0
    for t, n in sorted(want.items()):
        for eid in [e for e, tt in sorted(ents.items()) if tt == t][:n]:
            cell = where[eid]
            # The nearest spot of the booth with a clear shot, within the
            # gun's reach: the nearer, the likelier a hit.
            spots = sorted((mobs.hex_distance(b, cell, W), mobs.hex_distance(b, pos, W), b)
                           for b in booth if combat.shot_wall(loc, b, cell) is None
                           and mobs.hex_distance(b, cell, W) <= reach)
            if not spots:
                continue
            goal = spots[0][2]
            if goal != pos:
                path = mobs.find_path(loc, pos, lambda x: x == goal, set(where.values()),
                                      limit=20000)
                c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
                out += c.frames(0.3 + 0.25 * len(path or [goal]))
                pos = goal
            tries = waited = 0
            while tries < 80:
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(eid)))
                got = c.until(lambda f: f[0] == "ss_di_firearm" or (f[0] == "lch" and f[1].get(
                    "dead") == eid) or (f[0] == "cmdAck" and f[1]["res"]), 3)
                # The kill follows the magazine's report, in the same step
                # of the server (Fighter.fire_now); one that came later would
                # still be seen, in the frames of the next shot.
                got += c.sync()
                out += got
                # Out of AP, a player waits for the bar. The AP come back on
                # the creatures' beat (RoomCombat._step), and the server's
                # LAVA_ACTION_SCALE aims come quicker than that beat; one
                # beat is a full bar at this suite's LAVA_AP_REGEN, and the
                # refusal costs no try.
                if inventory.RES_NO_AP in acks(got):
                    waited += 1
                    if waited > 2000:           # the bar never came back
                        return out, felled, shots
                    # Short looks rather than a whole beat: the refill lands
                    # somewhere inside one, and a refusal costs a round trip.
                    out += c.frames(0.1)
                    continue
                tries += 1
                if inventory.RES_NO_AMMO in acks(got):
                    rounds = oid(cid, ROUNDS)
                    if rounds is None:
                        out += more_rounds(c, arrival, loc_id)
                        rounds = oid(cid, ROUNDS)
                    loaded = load(c, gun, rounds) if rounds else []
                    out += loaded
                    if acks(loaded) != [0]:
                        return out, felled, shots
                    continue
                shots += 1
                if any(nm == "lch" and p.get("dead") == eid for nm, p in got):
                    felled.append(t)
                    break
    return out + c.sync(), felled, shots


try:
    # --- a newcomer walks Берт's course --------------------------------------------------
    # With nothing but what a newcomer has -- the Самострел and its «9мм
    # даренные» -- and what the course lends in each range.
    c = login("cadet", "Cadet")
    CADET = cid_of("Cadet")
    check("a newcomer is offered Берт's course, not the lessons, not Тиль's trainings, not the"
          " ore mines' gates, not the quarry",
          [status(c, t) for t in [COURSE] + LESSONS + [4, 1829, AUTOMATCHIK]
           + MINES_IN + [QUARRY_IN]],
          [1] + [0] * 7 + [0] * 3 + [0] * 3 + [0])
    here = inhabitants(goto(c, MARKET))
    got, q = take(c, here, BERT, COURSE)
    check("«Тир Берта Гаммера» taken from Берт: the ack, the journal, complete",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, BERT, q)
    call, arrival = moved(c, got)
    check("  ..handed back: the ack, then into his bunker, TIR_00, told as a sublocation (no map)",
          (acks(got), call.get("id"), call.get("g_id", 0) >> 26), ([0], RANGE[0], 1))
    check("  ..and the course is a one-off: not offered again", status(c, COURSE), 0)
    booth0 = first(arrival, "lenter").get("pos")
    check("  ..arriving in the booth, on an entry beside Берт",
          (booth0 in world.location(RANGE[0]).entries,
           mobs.hex_distance(booth0, 29 * 32 + 8, 32) <= 3), (True, True))
    for k, t in enumerate(LESSONS):
        loc_id = RANGE[k]
        here = inhabitants(arrival)
        check("TIR_0%d: Берт's copy (%d) stands here" % (k, BERT_TI[k]),
              len(here.get(BERT_TI[k], [])), 1)
        got, q = take(c, here, BERT_TI[k], t)
        if k:
            have = held(CADET)
            check("lesson %d taken: the ack and the journal, nought killed; the training gun and"
                  " a hundred rounds lent" % (k + 1),
                  (acks(got), [p.get("complete") for p in named(got, "q_di_kill_mobs")],
                   have[GUNS[k - 1]], have[ROUNDS] >= 100), ([0], [0], 1, True))
            gun, rounds = oid(CADET, GUNS[k - 1]), oid(CADET, ROUNDS)
            wielded = wield(c, gun)
            if k == 1:
                c.send("chWorld;")
                got_m = c.frames(0.8)
                check("  ..the map is no way out of the range: chWorld refused, no map, no move",
                      (acks(got_m), named(got_m, "gmap"), named(got_m, "lcall")), ([7], [], []))
                got_w = load(c, gun, oid(CADET, inventory.STARTER_AMMO))
                check("  ..the newcomer's own rounds do not go into the training pistol («особыми"
                      " пулями кал. 5,6 мм»)", acks(got_w), [inventory.RES_WRONG_AMMO])
                got_a, qa = take(c, here, BERT_TI[k], AMMO_Q)
                rounds0 = held(CADET)[ROUNDS]
                purse0 = progression.Character.load(accounts.Store(DB), CADET).afro
                got_a = hand_in(c, here, BERT_TI[k], qa)
                check("«Получить боеприпасы»: a hundred more rounds, free, no move, no day's"
                      " hand-in spent",
                      (acks(got_a), held(CADET)[ROUNDS] - rounds0, first(got_a, "lcall"),
                       progression.Character.load(accounts.Store(DB), CADET).afro - purse0,
                       named(got_a, "q_sys")), ([0], 100, {}, 0, []))
            got_l = load(c, gun, rounds)
            check("  ..the training gun in hand, loaded with the rounds lent with it",
                  (wielded, acks(got_l), len(named(got_l, "ss_di_firearm"))), ([0], [0], 1))
            # «Попробуй использовать различные режимы стрельбы»: a burst
            # where the class has one.
            mode = 1 if items.params_of(GUNS[k - 1])["fire_mods"][1] else 0
            if mode:
                c.send("ss_use;target=x%x;obj=x%s;type=64;" % (mode, gun))
                check("  ..switched to its burst", acks(c.sync()), [0])
            got = hand_in(c, here, BERT_TI[k], q)
            check("  ..not handed in before the targets", acks(got), [3])
            want = dict(zip(quests.get(t).mobs_kill, quests.get(t).num_kill))
            fight, felled, shots = shoot(c, arrival, loc_id, want, gun, CADET, mode)
            check("  ..the targets shot from the booth, over the counter, with the lent gun and"
                  " rounds alone (%d aims)" % shots,
                  sorted(felled), sorted(tt for tt, n in want.items() for _ in range(n)))
            check("  ..and the journal counted them to complete",
                  (named(fight, "q_di_kill_mobs") or [{}])[-1].get("complete"), 1)
            st = accounts.Store(DB)
            worn = [(r["brk"], r["max_break_cur"]) for r in st.items_of(CADET)
                    if r["type_id"] == GUNS[k - 1]]
            st.close()
            check("  ..the lent gun came through unworn (a quest's loan does not wear)",
                  all(b == m for b, m in worn) and len(worn) == 1, True)
        else:
            check("lesson 1 taken: the theory, complete at once",
                  (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
        before = held(CADET)
        got = hand_in(c, here, BERT_TI[k], q)
        call, arrival = moved(c, got)
        after = held(CADET)
        nxt = RANGE[k + 1] if k + 1 < len(RANGE) else MARKET
        check("lesson %d handed in: the ack, then %s" % (
            k + 1, "on to TIR_0%d, no map from there" % (k + 1) if nxt != MARKET
            else "back to the market, the map there again"),
            (acks(got)[:1], call.get("id"), call.get("g_id", 0) >> 26),
            ([0], nxt, 1 if nxt != MARKET else 0))
        if k:
            check("  ..the training gun taken back, and of the rounds up to the hundred lent",
                  (after[GUNS[k - 1]], after[ROUNDS]), (0, max(0, before[ROUNDS] - 100)))
    have = held(CADET)
    check("the course over: the certificate in the bag, no training gun, the journal empty of"
          " lessons", (have[CERT], [g for g in GUNS if have[g]],
                       [t for t in journal(CADET) if t in LESSONS]), (1, [], []))
    check("  ..and nothing of the course offered again; Тиль's trainings are",
          [status(c, t) for t in [COURSE] + LESSONS + TRAININGS],
          [0] * 8 + [1] * 6)
    here = inhabitants(goto(c, BLACK_MARKET))
    got, q = take(c, here, TIL, 1829)
    check("«Охотник» at Мастер Тиль: the certificate in the bag, complete",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, TIL, q, obj_idx=0)
    have = held(CADET)
    check("  ..handed in: the certificate out, the part chosen (the first of the six) and the coin"
          " in", (acks(got), have[CERT], have[SHOTGUN_PARTS[0]], have[COIN]), ([0], 0, 1, 1))
    check("the ore mines' gate refuses a level-0 player, carried or not",
          [status(c, t) for t in MINES_IN], [0, 0, 0])
    check("an exam is not offered without «Самоучители» and the specialisation",
          [status(c, t) for t in (EXAMS_A[2], EXAMS_G[2])], [0, 0])
    logout(c)

    # --- another breaks the course off --------------------------------------------------------
    c = login("quitter", "Quitter")
    QUITTER = cid_of("Quitter")
    here = inhabitants(goto(c, MARKET))
    got, q = take(c, here, BERT, COURSE)
    call, arrival = moved(c, hand_in(c, here, BERT, q))
    here = inhabitants(arrival)
    got, q = take(c, here, BERT_TI[0], LESSONS[0])
    call, arrival = moved(c, hand_in(c, here, BERT_TI[0], q))
    check("the second into TIR_01", call.get("id"), RANGE[1])
    here = inhabitants(arrival)
    got, q_lesson = take(c, here, BERT_TI[1], LESSONS[1])
    check("  ..lesson 2 taken, its pistol and rounds lent",
          (held(QUITTER)[GUNS[0]], held(QUITTER)[ROUNDS]), (1, 100))
    # The map button in the middle of the course: before 2026-09-28 it put
    # him on the map with the lesson, the pistol and the rounds, and the
    # course lost for good.
    c.send("chWorld;")
    got = c.frames(0.8)
    check("  ..the map button is no way out of the range: refused, no map, no move, all still his",
          (acks(got), named(got, "gmap"), named(got, "lcall"), held(QUITTER)[GUNS[0]],
           LESSONS[1] in journal(QUITTER)), ([7], [], [], 1, True))
    c.send("userMsg;entry=@/home@;group=0;")
    got = c.frames(0.8)
    check("  ..nor is /home: the message acknowledged, a line in answer, no move",
          (acks(got), len(named(got, "userMsg")), named(got, "lcall"), held(QUITTER)[GUNS[0]]),
          ([0], 1, [], 1))
    got, q = take(c, here, BERT_TI[1], ABORTS[1])
    check("«Прервать обучение» taken from Берт in TIR_01", acks(got), [0])
    got = hand_in(c, here, BERT_TI[1], q)
    call, before_call, arrival = way(c, got)
    check("  ..handed back: to the market", (acks(got)[:1], call.get("id")), ([0], MARKET))
    check("  ..no second chance: Берт's course is not offered again, nor this abort, nor the"
          " lessons after the one carried",
          [status(c, t) for t in [COURSE, ABORTS[1]] + LESSONS[2:]], [0] * 7)
    check("  ..the pistol and the rounds stay in their range (stay_in): taken back on the way"
          " out, before the lcall; the lesson carried is still his (the journal keeps it offered)",
          (held(QUITTER)[GUNS[0]], held(QUITTER)[ROUNDS],
           [p["status"] for p in named(before_call, "ss_obj_status")],
           LESSONS[1] in journal(QUITTER), status(c, LESSONS[1])),
          (0, 0, [0, 0], True, 1))
    c.send("q_ca;q_id=%d;" % q_lesson)
    check("  ..dropped: nothing more to give back (the lesson itself stays his to take, in a"
          " range nothing leads to any more)",
          (acks(c.sync()), held(QUITTER)[GUNS[0]], held(QUITTER)[ROUNDS],
           status(c, LESSONS[1])), ([0], 0, 0, 1))
    logout(c)

    # --- a worker: the ore mine, the quarry ---------------------------------------------------
    c = login("worker", "Worker")
    logout(c)
    reshape("Worker", skill=6)
    c = login("worker", "Worker", first_time=False)
    WORKER = cid_of("Worker")
    check("level 6: the ore mines' gates and the quarry's contract are offered",
          [status(c, t) for t in MINES_IN + [QUARRY_IN]], [1, 1, 1, 1])
    here = inhabitants(goto(c, COPPER_TOP))
    got, q = take(c, here, 1328, MINES_IN[0])
    call, arrival = moved(c, hand_in(c, here, 1328, q))
    check("the copper mine's gate: down to the control room", call.get("id"), COPPER_ROOM)

    def through(c, loc_id, side, arrival):
        loc = world.location(loc_id)
        cells = sorted(cc for cc, s in travel.exit_sides(loc).items() if s == side
                       and cc not in loc.obstacles)
        c.send("moveTo;path=|%d|;" % cells[len(cells) // 2])
        c.frames(0.5)
        c.send("chWorld;to=1;")
        got = c.frames(0.8)
        call = first(got, "lcall")
        return acks(got), call.get("id"), (arrive(c) if call else [])

    res, where, arrival = through(c, COPPER_ROOM, "b", arrival)
    check("  ..its door b, under W_Pointer_Enter, into the first tier", (res, where),
          ([0], COPPER_1))
    res, where, arrival = through(c, COPPER_1, "b", arrival)
    check("  ..the first tier's door b, under W_Pointer_Down, into the second", (res, where),
          ([0], COPPER_2))
    res, where, arrival = through(c, COPPER_2, "b", arrival)
    check("  ..the second's door b, W_Pointer_Down, into the third", (res, where),
          ([0], COPPER_3))
    res, where, arrival = through(c, COPPER_3, "a", arrival)
    check("  ..the third's door a, W_Pointer_Up, back to the second", (res, where),
          ([0], COPPER_2))
    res, where, arrival = through(c, COPPER_2, "a", arrival)
    check("  ..the second's door a, W_Pointer_Up, back to the first", (res, where),
          ([0], COPPER_1))
    res, where, arrival = through(c, COPPER_1, "a", arrival)
    check("  ..the first's door a, W_Pointer_Exit, back to the control room", (res, where),
          ([0], COPPER_ROOM))
    here = inhabitants(arrival)
    got, q = take(c, here, 1340, MINES_OUT[0])
    call, arrival = moved(c, hand_in(c, here, 1340, q))
    check("  ..and «Выйти из шахты» up to the surface", call.get("id"), COPPER_TOP)

    here = inhabitants(goto(c, PIER))
    got, q = take(c, here, RAVSHAN, QUARRY_IN)
    call, arrival = moved(c, hand_in(c, here, RAVSHAN, q))
    check("Равшан's contract: into the quarry's north pit, told as a sublocation (no map)",
          (call.get("id"), call.get("g_id", 0) >> 26), (QUARRY_N, 1))
    here = inhabitants(arrival)
    check("  ..where Большой Сэм stands", len(here.get(SAM, [])), 1)
    afro0 = progression.Character.load(accounts.Store(DB), WORKER).afro
    got, q = take(c, here, SAM, BLOCKS_10)
    check("«Каменные блоки» taken: the pick lent", (acks(got), held(WORKER)[PICK]), ([0], 1))
    # The map button with the pick in the bag: before 2026-09-28 it put him
    # on the map with it.
    c.send("chWorld;")
    got = c.frames(0.8)
    check("  ..the map is no way out of the quarry: chWorld refused, no map, no move, the pick"
          " still here", (acks(got), named(got, "gmap"), named(got, "lcall"), held(WORKER)[PICK]),
          ([7], [], [], 1))
    give(c, BLOCK, 10)
    got = hand_in(c, here, SAM, q)
    have = held(WORKER)
    check("  ..ten blocks handed in: 140 afro, the blocks and the pick gone",
          (acks(got), (named(got, "userInfo_Player") or [{}])[-1].get("afro"), have[BLOCK],
           have[PICK]), ([0], afro0 + 140, 0, 0))
    got, q30 = take(c, here, SAM, BLOCKS_30)
    check("«30 Каменных Блоков» taken: the pick lent again", (acks(got), held(WORKER)[PICK]),
          ([0], 1))
    res, where, arrival = through(c, QUARRY_N, "S", arrival)
    check("the north pit's south side leads into the centre, not onto the map; the pick goes"
          " along, the pits being where it is used", (res, where, held(WORKER)[PICK]),
          ([0], QUARRY_C, 1))
    res, where, arrival = through(c, QUARRY_C, "E", arrival)
    check("  ..the centre's east side into the east pit", (res, where), ([0], QUARRY_E))
    res, where, arrival = through(c, QUARRY_E, "W", arrival)
    check("  ..and back", (res, where), ([0], QUARRY_C))

    # A rival walks into the centre pit, where the file lets players fight.
    r = login("rival", "Rival")
    RIVAL = cid_of("Rival")
    r_arrival = goto(r, QUARRY_C)
    seen = c.frames(1.0)
    pick = oid(WORKER, PICK)
    check("the pick in the worker's hand", wield(c, pick), [0])
    c.send("ss_use;type=16;obj=x%s;target=%s;" % (pick, entity(rooms.player_id(RIVAL))))
    got = c.frames(1.2)
    check("  ..never turned on a player, though the pit lets them fight (pvp=\"1\"): the weapon"
          " lowered (22), no blow", (world.location(QUARRY_C).pvp, acks(got),
                                     named(got, "caHit"), named(got, "caMiss")), (1, [22], [], []))
    loc = world.location(QUARRY_C)
    where_ = positions(arrival)
    occupied = set(where_.values()) | set(positions(seen).values()) \
        | {first(r_arrival, "lenter").get("pos")}
    pos = first(arrival, "lenter").get("pos")
    best = None
    for eid in inhabitants(arrival).get(STONE, []):
        for nb in progression.hex_neighbours(where_[eid], loc.width, loc.height):
            if nb in loc.obstacles or nb in occupied:
                continue
            path = mobs.find_path(loc, pos, lambda x, nb=nb: x == nb, occupied, limit=20000)
            if path is not None and (best is None or len(path) < len(best[2])):
                best = (eid, nb, path)
    stone, spot, path = best
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [spot])))
    c.frames(0.6 + 0.3 * len(path or [spot]))
    amax = first(arrival, "lenter").get("amax")
    blows = []
    for _ in range(15):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (pick, entity(stone)))
        blows += c.until(lambda f: f[0] in ("caHit", "caMiss") or (f[0] == "cmdAck"
                                                                   and f[1]["res"]), 3)
        blows += c.sync()
        if any(n == "lch" and p.get("dead") == stone for n, p in blows):
            break
    check("  ..a stone of the pit it breaks in one blow that lands, for 8 action points (the"
          " article's 0 was a free swing without end)",
          (len(named(blows, "caHit")), any(n == "lch" and p.get("dead") == stone
                                           for n, p in blows),
           min([p["ap"] for p in named(blows, "c_ap")] or [amax]) <= amax - 8),
          (1, True, True))

    # A death in the pit: the worker falls with the pick and wakes at home.
    logout(c)
    st_ = accounts.Store(DB)
    st_.save_character_state(WORKER, hp=1, sp=0)
    w_pos = st_.character_by_name("Worker")["pos"]
    st_.close()
    c = login("worker", "Worker", first_time=False)
    r.frames(1.0)
    check("back after a logout, in the pit: the pick is still his, this being where it is used",
          held(WORKER)[PICK], 1)
    r_pos = first(r_arrival, "lenter").get("pos")
    near = [nb for nb in progression.hex_neighbours(w_pos, loc.width, loc.height)
            if nb not in loc.obstacles and nb not in set(where_.values())]
    path = mobs.find_path(loc, r_pos, lambda x: x in near, set(where_.values()) | {w_pos},
                          limit=20000)
    r.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or near[:1])))
    r.frames(0.6 + 0.3 * len(path or near[:1]))
    fell = []
    for _ in range(40):
        r.send("ss_use;type=16;obj=x0;target=%s;" % entity(rooms.player_id(WORKER)))
        r.until(lambda f: f[0] in ("caHit", "caMiss") or (f[0] == "cmdAck" and f[1]["res"]), 3)
        fell += [p for n, p in c.sync() if n == "lch" and p.get("dead") == 0]
        if fell:
            break
    check("  ..the rival's fist is let fight there: the worker falls", bool(fell), True)
    c.send("resurrect;res_type=0;")
    call, before_call, arrival = way(c, c.frames(0.8))
    check("  ..and wakes at home: the pick stayed in the quarry (stay_in), taken back before the"
          " lcall, the work still his",
          (acks(before_call)[:1], call.get("id") in QUARRY, held(WORKER)[PICK],
           [p["status"] for p in named(before_call, "ss_obj_status")], BLOCKS_30 in journal(WORKER)),
          ([0], False, 0, [0], True))
    logout(r)

    # Back in, and out by Сэм's way with the work open.
    here = inhabitants(goto(c, PIER))
    got, q = take(c, here, RAVSHAN, QUARRY_IN)
    call, arrival = moved(c, hand_in(c, here, RAVSHAN, q))
    here = inhabitants(arrival)
    check("back in the quarry: the work still open, the pick not handed out again",
          (call.get("id"), BLOCKS_30 in journal(WORKER), held(WORKER)[PICK]),
          (QUARRY_N, True, 0))
    c.send("q_ca;q_id=%d;" % q30)
    got_ca = c.sync()
    got, q = take(c, here, SAM, BLOCKS_10)
    check("  ..the work dropped and another taken: the pick lent again",
          (acks(got_ca), acks(got), held(WORKER)[PICK]), ([0], [0], 1))
    res, where, arrival = through(c, QUARRY_N, "S", arrival)
    res2, where2, arrival = through(c, QUARRY_C, "N", arrival)
    check("  ..the centre's north side back to the north pit", (res, where, res2, where2),
          ([0], QUARRY_C, [0], QUARRY_N))
    here = inhabitants(arrival)
    got, q = take(c, here, SAM, QUARRY_OUT)
    call, before_call, arrival = way(c, hand_in(c, here, SAM, q))
    check("«Покинуть каменоломню.» with the work open: back to Причал, «прежде я заберу у тебя"
          " казённое имущество» -- the pick taken back before the lcall, the work still his",
          (call.get("id"), held(WORKER)[PICK],
           [p["status"] for p in named(before_call, "ss_obj_status")],
           BLOCKS_10 in journal(WORKER)), (PIER, 0, [0], True))
    check("  ..arriving by Равшан", mobs.hex_distance(first(arrival, "lenter").get("pos"),
                                                      18 * 64 + 52, 64) <= 3, True)
    here = inhabitants(arrival)
    check("  ..where Лейтенант О'Нилл offers no boat", ONEILL in here and BOAT_OUT not in quests.given_by(ONEILL),
          True)
    logout(c)

    # --- a scholar: the base's exams ----------------------------------------------------------
    c = login("scholar", "Scholar")
    logout(c)
    reshape("Scholar", spec=quests.SPEC_KEYS["pistols"])
    c = login("scholar", "Scholar", first_time=False)
    SCHOLAR = cid_of("Scholar")
    here = inhabitants(goto(c, BASE))
    got, q = take(c, here, WATCHER, SELF_TEACHERS)
    got = hand_in(c, here, WATCHER, q)
    check("«Самоучители» at the Часовой: taken and handed in", acks(got), [0])
    check("the pistols exams are offered now, the blades' (no specialisation) not",
          [status(c, t) for t in (EXAMS_A[2], EXAMS_G[2], EXAMS_A[1], EXAMS_G[1])], [1, 1, 0, 0])
    got, q = take(c, here, SEYID, EXAMS_A[1])
    check("  ..and taking the blades' is refused", acks(got), [4])
    give(c, PISTOLS_BOOK)
    got, q = take(c, here, SEYID, EXAMS_A[2])
    check("the pistols exam for afro, the book in the bag: not complete while the purse is short",
          (acks(got), first(got, "q_di_bring_l_obj").get("complete")), ([0], 0))
    c.send("userMsg;entry=@/money 30000@;group=0;")
    got = c.sync()
    check("  ..complete once it covers the 25 000",
          [p.get("complete") for p in named(got, "q_di_bring_l_obj")][-1:], [1])
    st_ = accounts.Store(DB)
    ch0 = progression.Character.load(st_, SCHOLAR)
    st_.close()
    ch0.gain_xp(progression.SHOOTING, 40000)
    ch0.gain_spec_xp(quests.SPEC_KEYS["pistols"], 40000)
    got = hand_in(c, here, SEYID, q)
    st_ = accounts.Store(DB)
    ch1 = progression.Character.load(st_, SCHOLAR)
    st_.close()
    check("  ..handed in: 25 000 taken, the book used up, 40 000 into the specialisation and"
          " 40 000 into Стрельба",
          (acks(got), ch1.afro, held(SCHOLAR)[PISTOLS_BOOK],
           ch1.spec[quests.SPEC_KEYS["pistols"]][:2], ch1.skill[progression.SHOOTING][:2]),
          ([0], 1000 + 30000 - 25000, 0, ch0.spec[quests.SPEC_KEYS["pistols"]][:2],
           ch0.skill[progression.SHOOTING][:2]))
    give(c, PISTOLS_BOOK)
    c.send("userMsg;entry=@/money 0 100@;group=0;")
    c.sync()
    ch0 = ch1
    ch0.gain_spec_xp(quests.SPEC_KEYS["pistols"], 80000)
    got, q = take(c, here, KASIM, EXAMS_G[2])
    got += hand_in(c, here, KASIM, q)
    st_ = accounts.Store(DB)
    ch1 = progression.Character.load(st_, SCHOLAR)
    st_.close()
    check("the pistols exam for gold: one ounce taken, 80 000 into the specialisation alone",
          (acks(got), ch1.gold, ch1.afro, held(SCHOLAR)[PISTOLS_BOOK],
           ch1.spec[quests.SPEC_KEYS["pistols"]][:2], ch1.skill[progression.SHOOTING][:2]),
          ([0, 0], 0, 1000 + 30000 - 25000, 0, ch0.spec[quests.SPEC_KEYS["pistols"]][:2],
           ch0.skill[progression.SHOOTING][:2]))
    logout(c)
except Exception:
    import traceback
    fails.append("the socket part broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [ln for ln in out.splitlines() if "C->S" in ln or "  ..  " in ln]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa training OK")
