"""Вади-Хальфа's story (the owner's «займись фулл восстановлением
Вади-Хальфы», 2026-09-28), types 101-155 of the real data/quests.json: the
newest edition's act straight on from «Добро пожаловать в Хальфу» (45),
the older block's dailies and side chains, the gold rush and the Магриб
base.

  bridge  «Обучение» (Шульц in the valley -> Зоричев in the city), after
          «Назад, в большой мир» (42)
  act 1   Саид, Генри ст, Генри мл., Кшиштоф, Каспар, Назир: «Рэкетиры» ...
          «Потерянная группа» (102-114)
  daily   «Раббин аль-Гуд», «Как слышно?», «Бандитская активность»,
          «Местные предпочтения», «Заказ» (115-119)
  Муж     Иви -> Кшиштоф -> (1761) -> the sentry -> Иви -> Назир -> (1762)
          -> Иви (120-123 around the wiki's 1761/1762)
  others  Рахат (124-128), «Порядок» (129-131), «Чертежи» (132),
          «Пропавший товарищ» (133-135), «Слухи», «Гарантии безопасности»,
          «Бомба» (136-139)
  gold    Винс's debt, Тиль, the rides to the mine and back, the ore,
          «К шахте» (140-146)
  base    Касим, Раис, Сейид, Мария (147-155)

In process: every row -- its giver and taker, the chain, the pay, the
repeats, the ways; the texts are the original's (data/orig_misc.json, the
builder's VERIFIED), all but the two whose start names the owner's boss
hours; every string id in the launcher's table; every thing a thing of the
game; every giver and taker standing where the quest sends the player,
every creature to kill standing where the mark is, every thing to bring
carried by the creatures the slot names, and only while a quest wants it
(«Учет»'s records).

On a socket, one character: «Обучение» from Шульц to Зоричев; Демир's
welcome to Саид; act 1 from «Рэкетиры» (five Лазутчики shot, they come
back) to «Потерянная группа», each giver offering its row only after its
parent, the money box of «Недельная добыча» empty for a player without the
quest and holding the sack for one with it; the dailies refused a second
time the same day; «Муж» through (the spirit from the box of 64, the tests
from the sectarians of 65); «Бомба» through the box of 52 into Мауризио's
hands; the gold rush with the rides 102 <-> 117 and back.

    LAVA_RES=.../lava/res python3 server/test_halfa_story.py
"""
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_WEAR_DROP",
              "LAVA_BAG_DROP", "LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ",
              "LAVA_BOSS_CLOCK", "LAVA_START"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import bosses  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


STORY = list(range(101, 156))
WAYS = [143, 146]
# The people.
SCHULZ, ZORICH, SAID, HENRY_SR, HENRY, HENRY_JR = 5221, 4, 44, 5104, 93, 46
KSH, KASPAR, NAZIR, IVY, SENTRY, RAHAT, WIFE, JOE = 47, 49, 48, 101, 72, 67, 68, 103
MAURIZIO, HERMIT, BOMB_BOX, VINS, TIL, DRIVER = 6522, 74, 75, 668, 5, 666
KASIM, RAIS, SEYID, MARIA, DEMIR_H = 718, 859, 719, 697, 30
# The places.
VILLAGE, OLD_MARKET, PORT_MARKET, BLACK_MARKET, QUARTER, PIER = 186, 35, 104, 102, 36, 41
BASE, CAMP_NC, CHIEF_NC, HENRY_JR_LOC, COURIER_LOC, INTERCEPT = 52, 80, 82, 43, 45, 46
PASTURE, LOST_SQUAD, JA_CAMP, LU_CAMP, MG_CAMP, MG_CHIEF, SPIRIT = 44, 48, 84, 81, 85, 87, 64
GATHERING, WIFE_LOC, HERMIT_LOC, OASIS, PETROL, DEBTORS = 65, 47, 61, 62, 60, 108
GOLD_MINE, DRIVER_LOC, MARIA_LOC, AMBUSH, DSR_LOC = 116, 117, 119, 121, 122
# The creatures.
SCOUT, TREASURER, KHALID, SABOTEUR, SECTARIAN4, KAIS, AGNES = 258, 586, 855, 291, 854, 314, 270
OFFICER, CASH_BOX, CARGO_BOX, COURIER, BANDIT_LEADER, SPIRIT_BOX = 1040, 41, 50, 852, 853, 102
SECTARIAN6, MASTER6 = 110, 111
# The things.
RECORDS, SACK, CARGO, PARCEL, REPORTS, PURSE, EAR, DOG_MEAT = 253, 254, 255, 256, 257, 258, 259, 216
PARTS = (228, 229, 230, 231)
SPIRIT_T, TESTS, BOMB, GOLD_BAG, ORE, PASS, TOKEN = 287, 291, 266, 1305, 1306, 1544, 264
JERKY, OLD_BAG, BP2, BP4 = 6046, 1535, 1131, 1132
EK = [6152, 6159, 6158, 6155, 6156, 6157]
ADMIN_GUN, GUN_ROUNDS = 1534, 6092
MEDICINE = progression.MEDICINE

GIVE_TAKE = {
    101: ([SCHULZ], [ZORICH]), 102: ([SAID], [SAID]), 103: ([SAID], [SAID]),
    104: ([SAID], [HENRY_SR]), 105: ([HENRY_SR], [HENRY_JR]), 106: ([HENRY_JR], [SAID]),
    107: ([SAID], [KSH]), 108: ([KSH], [KSH]), 109: ([KSH], [KASPAR]), 110: ([KASPAR], [KSH]),
    111: ([KSH], [NAZIR]), 112: ([NAZIR], [NAZIR]), 113: ([NAZIR], [NAZIR]),
    114: ([NAZIR], [NAZIR]), 115: ([SAID], [SAID]), 116: ([KASPAR], [KASPAR]),
    117: ([NAZIR], [NAZIR]), 118: ([KSH], [KSH]), 119: ([HENRY_SR, HENRY], [HENRY_SR, HENRY]),
    120: ([IVY], [KSH]), 121: ([SENTRY], [IVY]), 122: ([IVY], [NAZIR]), 123: ([NAZIR], [IVY]),
    124: ([RAHAT], [WIFE]), 125: ([WIFE], [RAHAT]), 126: ([RAHAT], [RAHAT]),
    127: ([KASPAR], [JOE]), 128: ([JOE], [RAHAT]), 129: ([KSH], [SAID]), 130: ([SAID], [SAID]),
    131: ([SAID], [SAID]), 132: ([HENRY_SR, HENRY], [HENRY_SR, HENRY]),
    133: ([SENTRY], [MAURIZIO]), 134: ([MAURIZIO], [HERMIT]), 135: ([HERMIT], [SENTRY]),
    136: ([NAZIR], [KSH]), 137: ([MAURIZIO], [MAURIZIO]), 138: ([NAZIR], [BOMB_BOX]),
    139: ([BOMB_BOX], [NAZIR]), 140: ([VINS], [VINS]), 141: ([VINS], [TIL]),
    142: ([TIL], [TIL]), 143: ([DRIVER], [DRIVER]), 144: ([DRIVER], [DRIVER]),
    145: ([VINS], [VINS]), 146: ([TIL], [TIL]), 147: ([KASIM], [KASIM]),
    148: ([KASIM], [KASIM]), 149: ([RAIS], [RAIS]), 150: ([RAIS], [RAIS]),
    151: ([SEYID], [MARIA]), 152: ([MARIA], [SEYID]), 153: ([SEYID], [SEYID]),
    154: ([SEYID], [SEYID]), 155: ([SEYID], [SEYID])}
CHAIN = {101: [42], 102: [45], 103: [102], 104: [103], 105: [104], 106: [105], 107: [106],
         108: [107], 109: [108], 110: [109], 111: [110], 112: [111], 113: [112], 114: [113],
         115: [106], 116: [110], 117: [114], 118: [107], 119: [105], 120: [118], 121: [1761],
         122: [121], 123: [1762], 124: [], 125: [124], 126: [125], 127: [126], 128: [127],
         129: [106], 130: [129], 131: [130], 132: [102], 133: [111], 134: [133], 135: [134],
         136: [114], 137: [139], 138: [114], 139: [138], 140: [], 141: [140], 142: [141],
         143: [], 144: [142], 145: [144], 146: [], 147: [], 148: [147], 149: [148],
         150: [149], 151: [149], 152: [151], 153: [152], 154: [153], 155: [154]}
MED = {"medicine": 20}
# (the thing chosen: [(type, pieces)], afro, experience)
PAYS = {101: ([], 0, MED), 102: ([], 100, {}), 103: ([], 150, {}), 104: ([], 0, MED),
        105: ([], 0, MED), 106: ([], 300, {}), 107: ([], 0, MED), 108: ([], 200, {}),
        109: ([], 250, {}), 110: ([], 0, MED), 111: ([], 0, MED), 112: ([], 250, {}),
        113: ([], 0, {}), 114: ([], 300, {}), 115: ([], 600, {}), 116: ([], 600, {}),
        117: ([], 600, {}), 118: ([(JERKY, 5)], 200, {}), 119: ([], 1500, {}),
        120: ([], 0, MED), 121: ([], 0, MED), 122: ([], 0, MED), 123: ([], 0, MED),
        124: ([], 0, MED), 125: ([], 0, MED), 126: ([], 200, {}), 127: ([], 0, MED),
        128: ([], 0, MED), 129: ([], 0, MED), 130: ([], 400, {}), 131: ([], 1500, {}),
        132: ([(BP2, 1)], 0, {}), 133: ([], 0, MED), 134: ([], 0, MED), 135: ([], 500, {}),
        136: ([], 0, MED), 137: ([], 100, {}), 138: ([], 0, MED), 139: ([(BOMB, 1)], 0, {}),
        140: ([(t, 50) for t in EK], 0, {}), 141: ([], 0, MED), 142: ([], 0, MED),
        143: ([], 0, {}), 144: ([], 0, {}), 145: ([], 600, {}), 146: ([], 0, {}),
        147: ([(OLD_BAG, 1)], 0, {}), 148: ([], 600, {}), 149: ([], 2000, {}),
        150: ([], 1500, {}), 151: ([], 0, MED), 152: ([], 0, MED), 153: ([(BP4, 1)], 0, {}),
        154: ([], 1000, {}), 155: ([], 800, {})}
DAILY = [115, 116, 117, 118, 119]
# Where each giver and taker stands (not as a mob), among the places scanned.
WHERE = {SCHULZ: {VILLAGE}, ZORICH: {OLD_MARKET, PORT_MARKET}, SAID: {QUARTER},
         HENRY_SR: {OLD_MARKET}, HENRY: {PORT_MARKET}, HENRY_JR: {HENRY_JR_LOC},
         KSH: {QUARTER}, KASPAR: {QUARTER}, NAZIR: {QUARTER}, IVY: {OLD_MARKET},
         SENTRY: {BASE}, RAHAT: {PIER}, WIFE: {WIFE_LOC}, JOE: {OASIS},
         MAURIZIO: {PETROL}, HERMIT: {HERMIT_LOC}, BOMB_BOX: {BASE}, VINS: {OLD_MARKET},
         TIL: {BLACK_MARKET}, DRIVER: {DRIVER_LOC}, KASIM: {BASE}, RAIS: {BASE},
         SEYID: {BASE}, MARIA: {MARIA_LOC}}
KILLS = {102: (SCOUT, CAMP_NC), 108: (TREASURER, CAMP_NC), 113: (KHALID, PASTURE),
         117: (SABOTEUR, JA_CAMP), 126: (SECTARIAN4, SPIRIT), 131: (KAIS, MG_CHIEF),
         132: (AGNES, CAMP_NC), 150: (OFFICER, DSR_LOC)}
SCANNED = sorted(set().union(*WHERE.values()) | {
    CAMP_NC, CHIEF_NC, HENRY_JR_LOC, COURIER_LOC, INTERCEPT, PASTURE, LOST_SQUAD, JA_CAMP, 86,
    LU_CAMP, 83, MG_CAMP, MG_CHIEF, SPIRIT, GATHERING, DEBTORS, GOLD_MINE, AMBUSH, DSR_LOC,
    100, 138})
# The two starts that name the owner's boss hours (14, 18 and 22) where the
# original says 18 and 22: the only lines of the story that are not the
# original's.
HOURS = {131: (47391, "в 18:00 и 22:00", bosses.say_hours()),
         132: (47395, "в 18 и 22 часа.", bosses.say_hours(short=True) + ".")}


def pack(gx, gy):
    return (gx << 13) | gy


# --- in process -------------------------------------------------------------------------
MT = world.mob_types()
try:
    rows = {t: quests.get(t) for t in STORY}
    check("the fifty-five quests of the story are in the table, 101-155",
          [t for t, q in rows.items() if q is None], [])
    check("  ..and nothing else of 101-179 but the later gold rush and the prison"
          " (156-169, test_halfa_events)",
          [t for t in range(156, 180) if quests.get(t) is not None and not 156 <= t <= 169], [])
    check("  ..given and taken by the NPCs the texts, the wiki and each row's why name",
          {t: (q.give, q.take) for t, q in rows.items()}, GIVE_TAKE)
    check("  ..in the chain the original draws, or each row's why designs",
          {t: q.need_all + q.need_any for t, q in rows.items()}, CHAIN)
    check("  ..the wiki's «Муж» stages hang between ours: 1761 after Иви's start, 1762"
          " after Иви's plea", (quests.get(1761).need_all, quests.get(1762).need_all),
          ([120], [122]))
    check("  ..paying what the original pays, or what each row's why designs",
          {t: (list(zip(q.rew_obj, q.num_rew_obj)), q.rew_afro,
               {k: xp for k, i in quests.SKILL_KEYS.items() for s, xp in q.rew_xp if s == i})
           for t, q in rows.items()}, PAYS)
    check("  ..no gold, no fee, nothing beside the reward, no random prize, no spec",
          [t for t, q in rows.items() if q.rew_gold or q.has_fee or q.rew_also
           or q.rew_random or q.rew_spec_xp or q.requires_spec or q.lent or q.service], [])
    check("  ..repeatable: the five dailies once a day, the rides back and forth, Сейид's"
          " partners (no once-a-day in its text)",
          ({t: q.per_day for t, q in rows.items() if q.repeatable}),
          {115: 1, 116: 1, 117: 1, 118: 1, 119: 1, 143: 0, 146: 0, 155: 0})
    check("  ..levels: the dog meat and the order at 2, the lost comrade at 3, the gold rush"
          " at 4 (lavabook)", {t: q.level for t, q in rows.items() if q.level},
          {118: 2, 119: 2, 133: 3, 135: 3, 140: 4})
    check("  ..no cap on any", [t for t, q in rows.items() if q.max_level is not None], [])
    check("the ways: Тиль's «К шахте» and his driver's «В Вади-Хальфу»",
          ([t for t in STORY if travel.is_quest_way(t)], [t for t in STORY if rows[t].rew_loc]),
          (WAYS, WAYS))
    check("  ..each a way and nothing else, as test_mine holds every way: again and"
          " again, no chain, nothing asked or paid",
          [(rows[t].kind, rows[t].obj, rows[t].objs, rows[t].repeatable, rows[t].need_all,
            rows[t].rew_obj, rows[t].rew_afro, rows[t].rew_xp) for t in WAYS],
          [(quests.DEL_OBJ, 0, [], 1, [], [], 0, [])] * 2)
    check("«Обучение» hangs off «Назад, в большой мир», while Шульц is still at hand; he"
          " gives it before his own three, including preparation for Mwamba (the table's order)",
          (rows[101].need_all, quests.given_by(SCHULZ)), ([42], [101, 57, 68, 58]))
    check("Тиль's «Пистолетчик» keeps its q_idx 0", quests.given_by(TIL)[0], 4)

    orig = orig_texts.quests()
    with open(os.path.join(os.path.dirname(HERE), "data", "orig_misc.json"),
              encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("the texts are the original's (data/orig_misc.json), all but the two starts that"
          " name the boss hours", [t for t in STORY if t not in pinned], sorted(HOURS))
    check("  ..laid over the table's",
          [t for t in STORY for k, key in enumerate(("name", "start", "notfinish", "finish"))
           if orig.get(t, {}).get(key) and rows[t].texts[k] != quests.served(rows[t], k, orig[t][key])], [])
    texts_xml = {}
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "data"))
        sys.dont_write_bytecode = True     # nothing left behind in data/
        import build_orig_misc  # noqa: E402
        texts_xml = build_orig_misc.load_texts(os.environ.get("LAVA_ORIG_TEXTS")
                                               or build_orig_misc.DEFAULT_SOURCE)[0]
    except (OSError, SystemExit):
        print("  ..  texts.xml not here: the two boss-hour starts are not read against it")
    if texts_xml:
        check("  ..the two boss-hour starts are the original's but for the hour",
              {t: rows[t].texts[quests.START] == orig_texts.clean(texts_xml[i]).replace(a, b)
               and a in texts_xml[i] for t, (i, a, b) in HOURS.items()}, {131: True, 132: True})
        check("  ..and their name, notfinish and finish are the original's words",
              {t: [rows[t].texts[k] == orig_texts.clean(texts_xml[i - 1 + k])
                   for k in (0, 2, 3)] for t, (i, _a, _b) in HOURS.items()},
              {131: [True] * 3, 132: [True] * 3})
    check("  ..the name lines the file lacks are the things' own: the bomb (6200), the"
          " pass (6230)", [pinned[t][0] for t in (138, 139, 151)], [6200, 6200, 6230])
    check("  ..the rides back and «К шахте» end in the original's words for a ride",
          [(pinned[t][3], rows[t].texts[quests.FINISH]) for t in (143, 146)],
          [(59830, "Ну, поехали!"), (62701, "Собирайся и езжай.")])
    check("  ..the later edition's gold rush (62711-62714) is not ours",
          sorted({i for t in STORY for i in pinned.get(t, []) if i and 62711 <= i <= 62714}),
          [])
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in rows.values() for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("every thing they name is one the game has, and what they hand over is worth"
          " nothing away from them", quests.check_items(), None)
    things = sorted({t for q in rows.values() for _f, t in q.things()})
    check("  ..and every thing and creature they name has a name the preload carries",
          ([t for t in things if not names.known(items.STRING_ID_OFFSET + t)],
           [m for q in rows.values() for m in q.mobs_kill + q.give + q.take
            + [x for _o, _n, ms in q.objs for x in ms] if not names.known(m)]), ([], []))
    check("no (P) thing is paid or asked for", [t for t in things if items.premium(t)], [])

    # Who stands where.
    stand = {}
    for lid in SCANNED:
        room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
        for n in room.npcs.values():
            stand.setdefault(n.type_id, set()).add((lid, n.root))
    check("each giver and taker stands where the quests send the player, not a mob",
          {npc: {lid for lid, root in stand.get(npc, ()) if root != world.MOB}
           for npc in WHERE}, WHERE)
    at = {lid: pack(*world.cell_of(lid)) for lid in SCANNED}
    by_mark = {v: k for k, v in at.items()}
    marks = {t: by_mark.get(q.finish_loc) for t, q in rows.items() if q.finish_loc not in (0, -1)}
    check("each hand-in's mark is the taker's place",
          {t: lid in WHERE[rows[t].take[0]] for t, lid in marks.items()},
          {t: True for t in marks})
    check("  ..every row but the two ways has one", sorted(set(STORY) - set(marks)),
          [143, 146])
    check("the kills: each creature standing, a mob, where the quest's mark is",
          {t: ((rows[t].mobs_kill, rows[t].num_kill), by_mark.get(rows[t].loc),
               (lid, world.MOB) in stand.get(m, ())) for t, (m, lid) in KILLS.items()},
          {t: (([m], [q.num_kill[0]]), lid, True) for t, (m, lid) in KILLS.items()
           for q in [rows[t]]})
    check("  ..five Лазутчики, the treasurer, Халид, five saboteurs, three novices, Кайс,"
          " Агнес, five officers", [rows[t].num_kill[0] for t in sorted(KILLS)],
          [5, 1, 1, 5, 3, 1, 1, 5])
    slots = {(t, o): (n, ms) for t, q in rows.items() for o, n, ms in q.objs}
    carried = {(t, o): [m for m in ms if not any(r == world.MOB for _l, r in stand.get(m, ()))
                        or o not in dict(mobs.quest_table(m))]
               for (t, o), (n, ms) in slots.items()}
    check("every thing to bring off a creature: each carrier stands, a mob, around the"
          " city, and carries it for a quest that wants it",
          {k: v for k, v in carried.items() if v}, {})
    check("  ..and the place the quest marks holds one of them",
          [t for t, q in rows.items() if q.kind == quests.BRING_L_OBJ and q.loc
           and not any((by_mark.get(q.loc), world.MOB) in stand.get(m, ())
                       for _o, _n, ms in q.objs for m in ms)], [])
    check("  ..the boxes and the couriers are certain; the rest by chance",
          sorted({(t, o) for (t, o), _v in slots.items()
                  for m, oo, ch in rows[t].drops if oo == o and ch == 1.0}),
          sorted({(106, SACK), (109, CARGO), (112, PARCEL), (114, REPORTS), (118, DOG_MEAT),
                  (154, 1543)}))
    check("  ..the Муж stages the wiki imported get theirs: the spirit from the box of 64,"
          " the tests from the sectarians of 65",
          (quests.get(1761).drops, quests.get(1762).drops),
          ([(SPIRIT_BOX, SPIRIT_T, 1.0)], [(SECTARIAN6, TESTS, 0.5), (MASTER6, TESTS, 0.5)]))
    check("  ..things with no creature: the bomb (from «Бомба»), the spoons (every man's junk),"
          " the Фуль (Бартоломью's), Генри's certificate-free parts have carriers",
          sorted((t, o) for (t, o), (n, ms) in slots.items() if not ms),
          [(137, BOMB), (147, 6911), (148, 334)])
    check("  ..the Фуль is on sale, the spoon is junk a man carries",
          (334 in items.stock_for(81), 6911 in mobs.series(mobs.TRASH_SERIES)), (True, True))
    check("«Местные предпочтения» asks for the dogs' meat (216), not the valley's antelope"
          " meat (260)", ([o for o, _n, _m in rows[118].objs],
                          [q.type for q in quests.QUESTS.values()
                           if 260 in [o for o, _n, _m in q.objs] + [q.obj]]),
          ([DOG_MEAT], [61, 62]))

    # «Учет»'s records drop only while a quest wants them.
    rng = random.Random(7)
    st = mobs.stats(261)
    plain = sum(RECORDS in [t for t, _n in mobs.loot_for(st, rng)] for _ in range(300))
    wanted = sum(RECORDS in [t for t, _n in mobs.loot_for(st, rng, {RECORDS})]
                 for _ in range(300))
    check("«Учет»'s records: a Каратель never drops them for nobody, about a third of the"
          " time for a player whose quest wants them", (plain, 50 < wanted < 150), (0, True))
    bags = {}
    for mob, thing in ((CARGO_BOX, CARGO), (COURIER, PARCEL), (BANDIT_LEADER, REPORTS),
                       (SPIRIT_BOX, SPIRIT_T), (SECTARIAN6, TESTS), (MASTER6, TESTS)):
        st = mobs.stats(mob)
        bags[mob] = (sum(thing in [t for t, _n in mobs.loot_for(st, rng)] for _ in range(100)),
                     sum(thing in [t for t, _n in mobs.loot_for(st, rng, {thing})]
                         for _ in range(100)) // 10 * 10)
    check("  ..and so the box of 46, the courier, the bandits' leader and the box of spirit"
          " hold theirs every time for a quest that wants it, the sectarians of 65 about"
          " half the time; for nobody, never",
          {m: (p, w >= 30 and (w == 100 or m in (SECTARIAN6, MASTER6)))
           for m, (p, w) in bags.items()}, {m: (0, True) for m in bags})
    check("  ..the bomb is handed over by the box, taken, and handed back; kept at a death,"
          " never on the ground", (rows[139].start_obj, rows[139].obj, rows[139].rew_obj,
                                   quests.kept_on_death(BOMB), quests.not_on_ground(BOMB)),
          ([(BOMB, 1)], BOMB, [BOMB], True, True))
    check("  ..so is Сейид's pass to Мария", (rows[151].start_obj, rows[151].obj,
                                              quests.kept_on_death(PASS)), ([(PASS, 1)], PASS, True))

    # The ways, in data/passages.json.
    for key, qtype, target, npc in ((BLACK_MARKET, 146, DRIVER_LOC, TIL),
                                    (DRIVER_LOC, 143, BLACK_MARKET, DRIVER)):
        loc = world.location(key)
        rec = travel.quest_way(loc, qtype)
        check("%d: quest %d is a way to %d" % (key, qtype, target),
              rec and rec.get("target_loc_id"), target)
        if not rec:
            continue
        way = {y * loc.width + x for x, y in rec["cells"]}
        zones = {loc._cell(c) for c in world._chunks(world._read(world.path_for(loc.id)),
                                                       "zones", 4)}
        home = [c for c, t in loc.spawns if t == npc]
        check("  ..drawn beside the car, on ground a walker stands on, where no window"
              " opens and nobody arrives",
              (sorted(way & loc.obstacles), sorted(way & zones), sorted(way & set(loc.entries)),
               bool(home) and min(mobs.hex_distance(c, home[0], loc.width) for c in way) <= 2),
              ([], [], [], True))
        check("  ..with its reason", rec.get("why", "").startswith(("DESIGNED", "RECOVERED")),
              True)
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server ------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "halfa_story.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("wanderer", "secret")
_store.close()
CRED = accounts.credential("wanderer", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="6268", LAVA_GY="1819", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="1", LAVA_SEED="11")
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


def order(frames):
    return [n for n, _p in frames]


def upto_ack(frames):
    seq = order(frames)
    return seq[:seq.index("cmdAck") + 1] if "cmdAck" in seq else seq


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def entity(target_id):
    return "x1%08x" % target_id


def inhabitants(frames):
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


def goto(c, loc_id):
    """/goto a location: the arrival's frames."""
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def give(c, type_id, n=1):
    c.send("userMsg;entry=@/give %d %d@;group=0;" % (type_id, n))
    got = c.until(lambda f: f[0] == "userMsg") + c.frames(0.3)
    new = named(got, "ss_obj_status")
    return (str(new[0]["obj"]) if new else None), got


def ints(v):
    if v in (None, "", []):
        return []
    return [int(x) for x in (v if isinstance(v, list) else [v])]


def quest_lists(c, here, npc_type):
    """(give_quests, take_quests) of the first inhabitant of a type here."""
    c.send("getInfo;lvl=0;id=%d;type=0;" % here.get(npc_type, [0])[0])
    got = [p for n, p in c.until(lambda f: f[0].startswith("userInfo_"), 2)
           if n.startswith("userInfo_") and p.get("name") == npc_type]
    return (ints(got[0].get("give_quests")), ints(got[0].get("take_quests"))) if got else None


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def take(c, here, qtype, npc_type=None):
    """q_st of a type from the first NPC of its giver's type here."""
    npc_type = npc_type or GIVE_TAKE[qtype][0][0]
    npc = here.get(npc_type, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return got, (ids[0] if ids else 0)


def hand_in(c, here, qtype, q_id, obj_idx=0, npc_type=None, wait=0.9):
    npc = here.get(npc_type or GIVE_TAKE[qtype][1][0], [0])[0]
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(wait)


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = 'Wanderer'").fetchone()
    st.close()
    return row["id"]


def owned(cid, slot=inventory.BAG):
    st = store()
    out = {}
    for r in st.items_of(cid):
        if r["slot"] == slot:
            n = r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1
            out[r["type_id"]] = out.get(r["type_id"], 0) + n
    st.close()
    return out


def done(cid):
    st = store()
    got = sorted(r["type"] for r in st.db.execute(
        "SELECT type FROM char_quests_done WHERE char_id = ?", (cid,)).fetchall())
    st.close()
    return got


def new_things(frames):
    out = []
    for p in named(frames, "ss_obj_status"):
        oid = inventory.parse_oid(str(p["obj"]).lstrip("x"))
        if p.get("status") == 1 and oid:
            out.append(oid[1])
    return out


def purse(frames):
    got = named(frames, "userInfo_Player")
    return got[-1].get("afro") if got else None


def afro_seen(c):
    """The purse before a hand-in: as the client was last told of it, or as
    the server last wrote it (a hand-in saves the Character, and nothing else
    in this walk moves money)."""
    got = [p.get("afro") for n, p in c.seen if n == "userInfo_Player" and "afro" in p]
    if got:
        return got[-1]
    st = store()
    afro = st.money(CID)[0]
    st.close()
    return afro


def counts(frames, kind):
    key = "kill_num" if kind == quests.KILL_MOBS else "obj_num"
    return [(p[key], p["complete"]) for p in named(frames, "q_di_" + kind)]


def positions(frames):
    where = {}
    for n, p in frames:
        if n == "lch" and "newUser" in p:
            where[p["newUser"]] = p["pos"]
        elif n == "userMove" and p.get("id") in where and p.get("path"):
            where[p["id"]] = p["path"][-1]
    return where


def hunt(c, got, loc_id, targets, pos):
    """Shoot one creature of each type in targets, in order, each from a cell
    with a clear line to it and out of every hostile's reach (the admin gun
    fells anything with one shot) -- as test_valley_story does. (frames,
    types killed, where the player stands, type -> the cell it fell on, the
    cells within reach of the hostiles still standing)."""
    loc = world.location(loc_id)
    cells = range(loc.width * loc.height)
    types = {}
    for t, es in inhabitants(got).items():
        for e in es:
            types[e] = t
    hostile = {e for e, t in types.items() if MT.get(t, (None,))[0] == world.MOB}
    reach = max([mobs.stats(types[e]).aggro for e in hostile] or [0]) + 0.5
    out, killed, fell, dead = [], [], {}, set()
    for want in targets:
        where = positions(got + out)
        for eid in [e for e, t in types.items() if t == want and e not in dead]:
            home = where.get(eid)
            if home is None:
                continue
            others = [where[e] for e in hostile if e not in dead and e != eid and e in where]
            wary = {cell for cell in cells
                    if any(mobs.hex_distance(cell, o, loc.width) <= reach
                           for o in others + [home])}
            spots = sorted((mobs.hex_distance(cell, home, loc.width), cell) for cell in cells
                           if cell not in loc.obstacles and cell not in wary
                           and travel.side_at(loc, cell) is None
                           and cell not in where.values()
                           and mobs.hex_distance(cell, home, loc.width) <= 40
                           and mobs.line_of_fire(loc, cell, home) is None)
            if not spots:
                continue
            goal = spots[0][1]
            path = mobs.find_path(loc, pos, lambda cell: cell == goal, wary, limit=20000)
            c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in (path or [goal])))
            out += c.frames(mobs.HEX_MS / 1000.0 * len(path or [0]) + 0.8)
            pos = goal
            for _ in range(30):
                c.send("ss_use;type=16;obj=x%s;target=%s;" % (GUN, entity(eid)))
                got_ = c.until(lambda f: f[0] == "ss_di_firearm"
                               or (f[0] == "cmdAck" and f[1].get("res")), 3) + c.frames(0.4)
                out += got_
                if [p for p in named(got_, "lch") if p.get("dead") == eid]:
                    killed.append(want)
                    dead.add(eid)
                    fell[want] = positions(got + out).get(eid, home)
                    break
                time.sleep(0.3)
            if want in killed:
                break
    where = positions(got + out)
    standing = [where[e] for e in hostile if e not in dead and e in where]
    wary = {cell for cell in cells
            if any(mobs.hex_distance(cell, o, loc.width) <= reach for o in standing)}
    return out, killed, pos, fell, wary


def loot(c, fight, loc_id, pos, near, wary=frozenset()):
    """Open the corpse's bag that lies nearest `near`, take all of it:
    (the types it held, the frames of the taking)."""
    loc = world.location(loc_id)
    got = list(fight)
    if not named(got, "ss_loot"):
        got += c.until(lambda f: f[0] == "ss_loot", 5)
    bags = [p["hex"][0] for p in named(got, "ss_loot") if p.get("s_status") == 1]
    if not bags:
        return None, []
    bag = min(bags, key=lambda cell: mobs.hex_distance(cell, near, loc.width))
    path = mobs.find_path(loc, pos, lambda cell: cell == bag or progression.within_reach(
        cell, bag, loc.width, loc.height), set(wary), limit=20000)
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path or [pos]))
    c.frames(0.2 * len(path or [pos]) + 1.0)
    c.send("ss_create;s_type=0;target=%d;" % bag)
    if acks(c.frames()) != [0]:
        return None, []
    c.send("ss_get;slot=24;")
    lst = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
    held = [inventory.parse_oid(o)[1] for o in lst[lst.index("0") + 1:]]
    c.send("ss_upd;s_status=3;obj=x0;param=1;")
    took = c.frames(0.8)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    return held, took


def shoot(c, loc_id, target, tries=4):
    """/goto a place and shoot one creature of a type (waiting out its
    respawn if it is down): (the fight's frames, killed?, the arrival's
    frames, where the player stands, where it fell, the wary cells)."""
    for _ in range(tries):
        got = goto(c, loc_id)
        fight, killed, pos, fell, wary = hunt(c, got, loc_id, [target],
                                              first(got, "lenter").get("pos"))
        if killed:
            return fight + c.frames(0.3), True, got, pos, fell.get(target, pos), wary
        time.sleep(2.0)
    return [], False, [], None, None, frozenset()


def rob(c, loc_id, target, thing, tries=8):
    """Shoot creatures of a type and open their bags until one holds the
    thing: (whether one did, how many bags were opened, the last bag)."""
    opened, held = 0, []
    for _ in range(tries):
        fight, killed, _got, pos, fell, wary = shoot(c, loc_id, target)
        if not killed:
            continue
        held, _took = loot(c, fight, loc_id, pos, fell, wary)
        opened += 1
        if held and thing in held:
            return True, opened, held
        time.sleep(1.0)
    return False, opened, held


def relogin():
    c_ = Client(connect())
    c_.send("hello;minor=2;major=0;")
    c_.send("login;hash=@%s@;" % CRED)
    c_.frames()
    c_.send("selPers;num=0;")
    call = first(c_.until(lambda f: f[0] == "lcall"), "lcall")
    return c_, call, arrive(c_)


def logout(c_):
    c_.send("logout;")
    c_.frames(0.5)
    c_.s.close()
    time.sleep(0.3)


def talk(c, qtype, give_loc, take_loc, here=None):
    """Take a talk from its giver at give_loc and hand it in at take_loc:
    (the take's frames, the hand-in's frames, the inhabitants of take_loc)."""
    here = here if here is not None else inhabitants(goto(c, give_loc))
    got_t, q = take(c, here, qtype)
    if take_loc != give_loc:
        here = inhabitants(goto(c, take_loc))
    got_h = hand_in(c, here, qtype, q)
    return got_t, got_h, here


GUN = None
try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@Wanderer@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    arrive(c)
    CID = char_id()
    check("a newcomer is offered nothing of the story but Рахат's plea, Касим's spoons and"
          " the rides to the gold mine and back", [t for t in STORY if status(c, t)],
          [124, 143, 146, 147])
    logout(c)
    # The valley's story up to Наби's farewell (42) behind him, and the fourth
    # level of Стрельба for the gold rush: written, as test_valley_story walks it.
    st = store()
    st.finish_quest(0, CID, 42)
    st.save_stats(CID, [("skill", progression.SHOOTING, 4, 0, progression.skill_xp_max(4))])
    st.save_character_state(CID, level=4)
    st.close()
    c, _call, _got = relogin()
    check("after «Назад, в большой мир»: «Обучение» and Демир's welcome; the gold rush at"
          " the fourth level", [t for t in STORY + [45] if status(c, t)],
          [101, 124, 140, 143, 146, 147, 45])

    # --- the admin gun, loaded ---------------------------------------------------------
    GUN, _ = give(c, ADMIN_GUN)
    rounds, _ = give(c, GUN_ROUNDS, 99)
    c.send("ss_get;target=0;slot=11;")
    held = [str(x) for x in first(c.frames(), "ss_ack").get("o_list", [])]
    if len(held) > 6 and held[6] != "0":
        c.send("ss_move;obj=x%s;to=2048;from=512;" % held[6])
        c.frames()
    c.send("ss_move;obj=x%s;to=512;from=2048;" % GUN)
    c.frames()
    c.send("ss_use;target=x%s;obj=x%s;type=1;" % (rounds, GUN))
    c.until(lambda f: f[0] == "ss_di_firearm")

    # --- «Обучение»: Шульц in the valley, Зоричев in the city ----------------------------
    here = inhabitants(goto(c, VILLAGE))
    check("the caravan: Шульц lists «Обучение» first, and accepts preparation and the boss quest",
          quest_lists(c, here, SCHULZ), ([101, 57, 68, 58], [68, 58]))
    got, q = take(c, here, 101)
    check("«Обучение» taken from Шульц: the ack, then the journal, complete",
          (order(got), first(got, "q_di_del_obj").get("complete")),
          (["cmdAck", "q_di_del_obj"], 1))
    here = inhabitants(goto(c, OLD_MARKET))
    got = hand_in(c, here, 101, q)
    check("  ..handed in to Зоричев on the old market: the experience, the ack",
          ([n for n in upto_ack(got) if n != "usrUp"], acks(got)), (["rp_info", "cmdAck"], [0]))

    # --- Демир's welcome, and Саид's act ----------------------------------------------
    here = inhabitants(goto(c, PIER))
    got, q = take(c, here, 45, DEMIR_H)
    here = inhabitants(goto(c, QUARTER))
    check("Саид has nothing before the welcome", status(c, 102), 0)
    got = hand_in(c, here, 45, q, npc_type=SAID)
    check("«Добро пожаловать в Хальфу» handed in to Саид", acks(got), [0])
    check("  ..and «Рэкетиры» is offered now, «Учет» not yet",
          [status(c, t) for t in (102, 103)], [1, 0])
    got, q_racket = take(c, here, 102)
    check("«Рэкетиры» taken: nought of five", counts(got, quests.KILL_MOBS), [([0], 0)])
    mark, shot = len(c.seen), 0
    for i in range(12):
        _fight, killed, _g, _p, _f, _w = shoot(c, (CAMP_NC, CHIEF_NC)[i % 2], SCOUT, tries=2)
        shot += bool(killed)
        if shot == 5:
            break
    c.frames(0.5)
    fight_all = c.seen[mark:]
    check("five Лазутчики shot in the camp and at its chief's cell, coming back after each",
          shot, 5)
    check("  ..the journal counted each, complete on the fifth",
          counts(fight_all, quests.KILL_MOBS), [([n], int(n == 5)) for n in range(1, 6)])
    here = inhabitants(goto(c, QUARTER))
    afro = afro_seen(c)
    got = hand_in(c, here, 102, q_racket)
    check("  ..handed in to Саид: a hundred afro, the ack",
          (upto_ack(got), acks(got), purse(got) - afro), (["userInfo_Player", "cmdAck"], [0], 100))
    got, q = take(c, here, 103)
    check("«Учет» taken: no records yet", counts(got, quests.BRING_L_OBJ), [([0], 0)])
    _, more = give(c, RECORDS)
    check("  ..the records in the bag: complete", counts(more + c.frames(0.3), quests.BRING_L_OBJ),
          [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 103, q)
    check("  ..handed in: the records out, a hundred and fifty afro",
          (acks(got), purse(got) - afro, owned(CID).get(RECORDS)), ([0], 150, None))
    got, q = take(c, here, 104)
    here = inhabitants(goto(c, OLD_MARKET))
    check("Генри ст gives nothing before Саид's word", status(c, 105), 0)
    got = hand_in(c, here, 104, q)
    check("«Благое дело» handed in to Генри ст", acks(got), [0])
    got, q_uneasy = take(c, here, 105)
    check("«Неспокойное место» taken from him", acks(got), [0])
    # The money box, shot before the quest that wants its sack is taken.
    fight, killed, _g, pos, fell, wary = shoot(c, HENRY_JR_LOC, CASH_BOX)
    held, _ = loot(c, fight, HENRY_JR_LOC, pos, fell, wary)
    check("the money box of 43 shot before «Недельная добыча» is taken: no sack in it",
          (killed, SACK in (held or [0])), (True, False))
    here = inhabitants(goto(c, HENRY_JR_LOC))
    got = hand_in(c, here, 105, q_uneasy)
    check("«Неспокойное место» handed in to Генри мл. in 43", acks(got), [0])
    got, q_loot = take(c, here, 106)
    check("«Недельная добыча» taken from him", counts(got, quests.BRING_L_OBJ), [([0], 0)])
    time.sleep(2.0)
    found, opened, _held = rob(c, HENRY_JR_LOC, CASH_BOX, SACK, tries=3)
    check("  ..the box shot again: now it holds the sack, the first time",
          (found, opened), (True, 1))
    here = inhabitants(goto(c, QUARTER))
    afro = afro_seen(c)
    got = hand_in(c, here, 106, q_loot)
    check("  ..handed in to Саид: the sack out, three hundred afro",
          (acks(got), purse(got) - afro, owned(CID).get(SACK)), ([0], 300, None))
    check("his daily and «Слухами земля полнится» offered now; Кшиштоф's quests not yet",
          [status(c, t) for t in (107, 115, 108, 118)], [1, 1, 0, 0])
    _t, got, here = talk(c, 107, QUARTER, QUARTER, here)
    check("«Слухами земля полнится»: Саид to Кшиштоф", acks(got), [0])
    check("  ..Кшиштоф's «Реклама», his daily and «Порядок» offered now",
          [status(c, t) for t in (108, 118, 129)], [1, 1, 1])
    got, q = take(c, here, 108)
    fight, killed, *_rest = shoot(c, CAMP_NC, TREASURER)
    fight += c.frames(0.5)
    check("«Реклама»: the colonists' treasurer shot, the journal complete",
          (killed, counts(fight, quests.KILL_MOBS)), (True, [([1], 1)]))
    here = inhabitants(goto(c, QUARTER))
    afro = afro_seen(c)
    got = hand_in(c, here, 108, q)
    check("  ..handed in to Кшиштоф: two hundred afro", (acks(got), purse(got) - afro), ([0], 200))
    # The rest of the act's things lie in bags their guards stand over (the
    # box of 46, the courier's, the leader's); who carries them is held in
    # process, and here they come by /give.
    got, q = take(c, here, 109)
    _, more = give(c, CARGO)
    check("«Можно ли отказаться?»: the cargo in the bag, complete",
          counts(more + c.frames(0.3), quests.BRING_L_OBJ), [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 109, q)
    check("  ..handed in to Каспар: the cargo out, two hundred and fifty afro",
          (acks(got), purse(got) - afro, owned(CID).get(CARGO)), ([0], 250, None))
    _t, got, here = talk(c, 110, QUARTER, QUARTER, here)
    check("«Новая версия»: Каспар to Кшиштоф", acks(got), [0])
    _t, got, here = talk(c, 111, QUARTER, QUARTER, here)
    check("«Служба»: Кшиштоф to Назир", acks(got), [0])
    got, q = take(c, here, 112)
    _, more = give(c, PARCEL)
    check("«Передача»: the parcel in the bag, complete",
          counts(more + c.frames(0.3), quests.BRING_L_OBJ), [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 112, q)
    check("  ..handed in to Назир: two hundred and fifty afro", (acks(got), purse(got) - afro),
          ([0], 250))
    got, q = take(c, here, 113)
    fight, killed, *_rest = shoot(c, PASTURE, KHALID)
    fight += c.frames(0.5)
    check("«Назидание»: Халид shot on the pasture, the journal complete",
          (killed, counts(fight, quests.KILL_MOBS)), (True, [([1], 1)]))
    here = inhabitants(goto(c, QUARTER))
    afro = afro_seen(c)
    got = hand_in(c, here, 113, q)
    check("  ..handed in to Назир: nothing paid ('Какой награды ты ждешь')",
          (acks(got), purse(got)), ([0], None))
    got, q = take(c, here, 114)
    _, more = give(c, REPORTS)
    check("«Потерянная группа»: the reports in the bag, complete",
          counts(more + c.frames(0.3), quests.BRING_L_OBJ), [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 114, q)
    check("  ..handed in to Назир: three hundred afro", (acks(got), purse(got) - afro), ([0], 300))
    check("after the lost group: Назир's daily, «Слухи», «Бомба»; «Гарантии безопасности»"
          " waits for the bomb", [status(c, t) for t in (117, 136, 138, 137)], [1, 1, 1, 0])
    check("act 1 is all in the history, once", [t for t in done(CID) if 101 <= t <= 114],
          list(range(101, 115)))

    # --- the dailies -------------------------------------------------------------------------
    for qtype, thing, n, where_ in ((115, PURSE, 5, QUARTER), (116, EAR, 10, QUARTER),
                                    (118, DOG_MEAT, 5, QUARTER)):
        here = inhabitants(goto(c, where_))
        got, q = take(c, here, qtype)
        give(c, thing, n)
        c.frames(0.3)
        afro = afro_seen(c)
        got = hand_in(c, here, qtype, q)
        check("daily %d: %d of %d handed in, paid, the day's count told" % (qtype, n, thing),
              (acks(got), purse(got) - afro, "q_sys" in order(got)),
              ([0], PAYS[qtype][1], True))
        check("  ..not offered again today; taken again, refused",
              (status(c, qtype), acks(take(c, here, qtype)[0])), (0, [4]))
    check("«Местные предпочтения» paid its five pieces of jerky too", owned(CID).get(JERKY), 5)
    here = inhabitants(goto(c, OLD_MARKET))
    got, q = take(c, here, 119)
    for part in PARTS:
        give(c, part, 7)
    got = c.frames(0.3)
    afro = afro_seen(c)
    got = hand_in(c, here, 119, q)
    check("«Заказ» at Генри ст: seven of each part, fifteen hundred afro",
          (acks(got), purse(got) - afro, [owned(CID).get(p) for p in PARTS]),
          ([0], 1500, [None] * 4))
    here = inhabitants(goto(c, PORT_MARKET))
    check("  ..and not at Генри on the port market either, the same day",
          (status(c, 119), acks(take(c, here, 119, HENRY)[0])), (0, [4]))

    # --- Муж ---------------------------------------------------------------------------------
    got_t, got, here = talk(c, 120, OLD_MARKET, QUARTER)
    check("«Муж»: Иви on the old market to Кшиштоф", acks(got), [0])
    got, q = take(c, here, 1761, KSH)
    check("  ..Кшиштоф's spirit (1761) offered and taken now", acks(got), [0])
    _, more = give(c, SPIRIT_T)
    check("  ..the spirit in the bag, complete", counts(more + c.frames(0.3),
                                                   quests.BRING_L_OBJ), [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 1761, q, npc_type=KSH)
    check("  ..handed in to Кшиштоф: two hundred and fifty afro", (acks(got), purse(got) - afro),
          ([0], 250))
    _t, got, here = talk(c, 121, BASE, OLD_MARKET)
    check("  ..the sentry of the base to Иви", acks(got), [0])
    _t, got, here = talk(c, 122, OLD_MARKET, QUARTER, here)
    check("  ..Иви to Назир", acks(got), [0])
    got, q = take(c, here, 1762, NAZIR)
    _, more = give(c, TESTS)
    check("  ..Назир's tests (1762) in the bag, complete", counts(more + c.frames(0.3),
                                                               quests.BRING_L_OBJ), [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 1762, q, npc_type=NAZIR)
    check("  ..handed in to Назир: three hundred afro", (acks(got), purse(got) - afro), ([0], 300))
    _t, got, here = talk(c, 123, QUARTER, OLD_MARKET, here)
    check("  ..and Назир's refusal told to Иви: the end", acks(got), [0])
    check("«Муж» through, in the order it is told", [t for t in done(CID)
                                                      if t in (120, 121, 122, 123, 1761, 1762)],
          [120, 121, 122, 123, 1761, 1762])

    # --- «Бомба» -----------------------------------------------------------------------------
    here = inhabitants(goto(c, QUARTER))
    _t, got, here = talk(c, 138, QUARTER, BASE, here)
    check("«Бомба»: Назир's warning handed in at the box of the base", acks(got), [0])
    check("  ..the box offers the bomb now; Мауризио still wants none",
          [status(c, t) for t in (139, 137)], [1, 0])
    got, q = take(c, here, 139)
    check("  ..taken: the bomb into the bag, found and complete",
          (new_things(got), first(got, "q_di_del_obj").get("complete"), owned(CID).get(BOMB)),
          ([BOMB], 1, 1))
    here = inhabitants(goto(c, QUARTER))
    got = hand_in(c, here, 139, q)
    check("  ..handed to Назир, who hands it back: out, in, the ack",
          (upto_ack(got)[-4:-1], acks(got), owned(CID).get(BOMB)),
          (["ss_obj_status", "ss_obj_status", "ss_di_heap"], [0], 1))
    here = inhabitants(goto(c, PETROL))
    check("Мауризио's «Гарантии безопасности» is offered now", status(c, 137), 1)
    got, q = take(c, here, 137)
    check("  ..taken with the bomb in the bag: complete", counts(got, quests.BRING_L_OBJ),
          [([1], 1)])
    afro = afro_seen(c)
    got = hand_in(c, here, 137, q)
    check("  ..handed in: the bomb out, a hundred afro", (acks(got), purse(got) - afro,
                                                         owned(CID).get(BOMB)), ([0], 100, None))

    # --- the gold rush -----------------------------------------------------------------------
    here = inhabitants(goto(c, OLD_MARKET))
    got, q = take(c, here, 140)
    give(c, GOLD_BAG)
    c.frames(0.3)
    got = hand_in(c, here, 140, q, obj_idx=0)
    check("«Золотая лихорадка»: the bag of gold to Винс, fifty ЭК rounds of the one chosen",
          (acks(got), new_things(got), owned(CID).get(EK[0])), ([0], [EK[0]], 50))
    _t, got, here = talk(c, 141, OLD_MARKET, BLACK_MARKET, here)
    check("  ..Винс sends the player to Тиль", acks(got), [0])
    check("  ..Тиль's frame: «Пистолетчик» first, his step and «К шахте» after his trainings",
          [t for t in quest_lists(c, here, TIL)[0] if t in (4, 1829, 1895, 1971, 2128, 142, 146)],
          [4, 1829, 1895, 1971, 2128, 142, 146])
    _t, got, here = talk(c, 142, BLACK_MARKET, BLACK_MARKET, here)
    check("  ..his step: the mine is east, 'снова обратиться к Тилю' -- a talk, nobody moved",
          (acks(got), named(got + c.frames(0.5), "lcall")), ([0], []))
    got, q = take(c, here, 146)
    check("  ..«К шахте» taken from him: complete at once",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 1))
    got = hand_in(c, here, 146, q)
    call = first(got + ([] if named(got, "lcall") else c.until(lambda f: f[0] == "lcall", 3)),
                 "lcall")
    check("  ..handed back to Тиль: the ack, and the ride to his driver", (acks(got),
                                                                         call.get("id")),
          ([0], DRIVER_LOC))
    got = arrive(c)
    here = inhabitants(got)
    check("  ..arrived beside the way back, the driver there",
          (first(got, "lenter").get("pos"), len(here.get(DRIVER, []))),
          (travel.door_arrival(world.location(DRIVER_LOC), BLACK_MARKET), 1))
    check("  ..his frame lists the ride back and the ore", quest_lists(c, here, DRIVER),
          ([143, 144], [143, 144]))
    got, q = take(c, here, 144)
    give(c, ORE, 3)
    c.frames(0.3)
    got = hand_in(c, here, 144, q)
    check("  ..the ore: three bags into the boot ('Кидай в багажник и валим отсюда!')",
          (acks(got), owned(CID).get(ORE), named(got + c.frames(0.5), "lcall")), ([0], None, []))
    got, q = take(c, here, 143)
    got = hand_in(c, here, 143, q)
    call = first(got + ([] if named(got, "lcall") else c.until(lambda f: f[0] == "lcall", 3)),
                 "lcall")
    check("  ..«В Вади-Хальфу» from the driver: back to the black market",
          (acks(got), call.get("id")), ([0], BLACK_MARKET))
    got = arrive(c)
    check("  ..arrived beside Тиль's car", first(got, "lenter").get("pos"),
          travel.door_arrival(world.location(BLACK_MARKET), DRIVER_LOC))
    here = inhabitants(goto(c, OLD_MARKET))
    afro = afro_seen(c)
    _t, got, here = talk(c, 145, OLD_MARKET, OLD_MARKET, here)
    check("  ..Винс's reward: six hundred afro", (acks(got), purse(got) - afro), ([0], 600))
    check("  ..the rides are offered again, Тиль's step and the ore are not",
          [status(c, t) for t in (146, 143, 142, 144)], [1, 1, 0, 0])
    check("the gold rush in the history: each step once, the rides as ridden",
          [t for t in done(CID) if 140 <= t <= 146], [140, 141, 142, 143, 144, 145, 146])
    got = goto(c, QUARTER)
    check("the day's hand-ins: four dailies spent, the rides none",
          [p["daily_available"] for p in named(got, "q_sys")][-1:], [6])
    logout(c)
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-60:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa story OK")
