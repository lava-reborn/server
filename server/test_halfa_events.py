"""Timed events (server/events.py, data/schedule.json) and what Вади-Хальфа
gets from them: the prison's uprising, the seasons' calendar and the late
gold rush -- the events package of the restoration's third stage.

In process:
  * the windows on the Moscow clock: the prison's three a day, its gates a
    quarter of an hour before, its medics for the last five minutes; the
    seasons by the owner's dates; a window over midnight, a window before
    it, weekdays, a daily window inside a season and one laid over that;
    a table that does not hold together is refused;
  * the rows: the invitation, the rides, the gates, Томас's way out, the
    medics' five, Самуэль's talon, the late gold rush -- their texts the
    original's where VERIFIED pins them, nothing premium, the ways bare;
    the talons at the original's rate and no faster; the armband the
    blocks' own (no post, lot, barter, stall or death takes it out); the
    blocks' sides and their being left only by their ways;
  * real rooms on a clock the test turns by hand: the prisoners break out
    at noon and leave at half past, one killed comes back while it lasts and
    not after, the godfather comes once, the medics for the last five
    minutes under new ids each time, the guard of the blocks never; a room
    built in the middle of it has it at once (a restart remembers nothing
    and needs nothing); the guards and Хассир shown under new ids at each
    edge of the gates, and the southern guard when the invitation is taken
    with them shut -- the client asks q_status of an NPC id only once;
  * a season on a table of its own, switched on and off by the date.
On a socket:
  * a server whose clock starts just before noon, on a table where the
    uprising lasts ninety seconds (the real one's rows, shorter windows) and
    a season holds Савин's stall in the black market: the stall in season,
    the gate shut and then open to a client that asks q_status as the real
    one does (on first sight of an NPC id, never by hand), the way down,
    the empty cells and the breakout, no «Прописка» in the blocks, the
    medics at the end, ten armbands handed in, Томас's way out taking the
    rest, the gates shut again to the same client, and all of it gone;
  * a second server started in the middle of the real uprising: the
    prisoners are there at once; the gold rush's later steps walked to the
    ounce Тиль takes.

    LAVA_RES=.../lava/res python3 server/test_halfa_events.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
ENC = "utf-8"

for _k in ("LAVA_BOSS_HOURS", "LAVA_BOSS_STAY", "LAVA_BOSS_TZ", "LAVA_BOSS_CLOCK",
           "LAVA_SCHEDULE", "LAVA_QUESTS", "LAVA_PASSAGES", "LAVA_START"):
    os.environ.pop(_k, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import barter  # noqa: E402
import bosses  # noqa: E402
import combat  # noqa: E402
import events  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
import names  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


def at(h, m=0, s=0, day=28, month=9, year=2026):
    """A moment on the Moscow clock, as seconds since the epoch."""
    return datetime(year, month, day, h, m, s, tzinfo=bosses.ZONE).timestamp()


MT = world.mob_types()
YARD, WEST, SOUTH, CENTRE, NORTH_CELLS, EAST_CELLS = 176, 644, 645, 646, 647, 648
BLOCKS = [WEST, SOUTH, CENTRE, NORTH_CELLS, EAST_CELLS]
STATION, BLACK_MARKET, OLD_MARKET = 37, 102, 35
PRISONERS = [1113, 1114, 1115, 1116, 1117]
GODFATHER, TOMAS, MEDICS, GUARD_IN = 2173, 876, [877, 878, 879], 2176
WEST_GUARD, SOUTH_GUARD, SUPPLY, HASSIR, SAMUEL = 1791, 1794, 2180, 105, 893
VINS, TIL, SAVIN = 668, 5, 636
BAND, TALON = 2476, 3570
LATE_1, LATE_2, INVITE, RIDE, BACK, GATE_W, GATE_S, EXIT = range(156, 164)
TEN, TWENTY_FIVE, FIFTY, SEVENTY_FIVE, HUNDRED, TALON_Q = range(164, 170)
EK_G = [6152, 6159, 6158, 6155, 6156, 6157]
SCHEDULE = events.table()


def slots(name, moments):
    w = SCHEDULE.window(name)
    return [w.is_open(t) for t in moments]


# --- the windows --------------------------------------------------------------------------------
try:
    events.check(MT)
    check("the real table holds together (events.check)", True, True)
    check("the prison's uprising: 12:00, 16:00 and 23:00 for half an hour, on the Moscow clock",
          [slots("prison_wh", [at(h, m) for m, _ in ((0, 0),)]) for h in (12, 16, 23)]
          + [slots("prison_wh", [at(11, 59, 59), at(12, 29, 59), at(12, 30), at(15, 59), at(23, 29),
                                 at(23, 30), at(0, 10, day=29), at(18), at(20)])],
          [[True], [True], [True], [False, True, False, False, True, False, False, False, False]])
    check("  ..which is not the bosses' 18/20: the prison keeps its label's hours",
          (bosses.slot(at(12)), bosses.slot(at(18)) is not None), (None, True))
    check("its gates: from a quarter of an hour before to the end ('прибывать за 15 минут')",
          slots("prison_wh_gates", [at(11, 44, 59), at(11, 45), at(12, 29, 59), at(12, 30),
                                    at(22, 45), at(15, 50)]),
          [False, True, True, False, True, True])
    check("its medics: the last five minutes ('появятся за 5 минут до завершения')",
          slots("prison_wh_medics", [at(12, 24, 59), at(12, 25), at(12, 29, 59), at(12, 30),
                                     at(16, 27), at(23, 26)]),
          [False, True, True, False, True, True])
    check("the opening is named by when it began, as the bosses' are",
          (SCHEDULE.window("prison_wh").slot(at(16, 10)),
           SCHEDULE.window("prison_wh_gates").slot(at(11, 50))), (at(16), at(11, 45)))
    SEASONS = [("ny", (12, 20), (1, 15)), ("may9", (5, 9), (8, 2)),
               ("halloween", (10, 30), (12, 1)), ("feb23", (2, 20), (2, 26))]
    for name, (m0, d0), (m1, d1) in SEASONS:
        y1 = 2027 if (m1, d1) < (m0, d0) or m0 >= 10 else 2026
        y0 = 2026 if m0 >= 5 else 2027
        first, last = at(0, 0, 0, d0, m0, y0), at(23, 59, 59, d1, m1, y1)
        check("the season %s: from the first moment of %02d.%02d to the last of %02d.%02d"
              " (the owner's default 22)" % (name, d0, m0, d1, m1),
              [SCHEDULE.window(name).is_open(t) for t in (first - 1, first, last, last + 1)],
              [False, True, True, False])
    check("  ..and outside every season today nothing is in season",
          [w.name for w in SCHEDULE.windows.values() if w.kind == "dates" and w.is_open(at(12))], [])
    check("  ..the New Year's why says who stands all year as world.SEASON_KEPT has it: the"
          " children, the refugee, the lottery men -- and Ольсен nowhere",
          (sorted({t for kept in world.SEASON_KEPT.values() for t in kept}
                  & {423, 425, 1977, 662, 711, 431}),
           "Ольсен 431 stands nowhere" in SCHEDULE.window("ny").why),
          ([423, 425, 662, 711, 1977], True))

    probe = events.Schedule({"windows": {
        "late": {"daily": ["23:50"], "minutes": 20, "why": "t"},
        "midnight": {"daily": ["00:10"], "minutes": 10, "why": "t"},
        "early": {"of": "midnight", "from": -15, "to": 0, "why": "t"},
        "weekend": {"daily": ["12:00"], "minutes": 60, "weekdays": [5, 6], "why": "t"},
        "leap": {"dates": [["02-29", "03-01"]], "why": "t"},
        "winter": {"dates": [["12-30", "01-02"]], "why": "t"},
        "winter_noon": {"daily": ["12:00"], "minutes": 60, "within": "winter", "why": "t"},
        "winter_gates": {"of": "winter_noon", "from": -15, "to": 60, "why": "t"}}})
    check("a window opened yesterday is still open past midnight",
          probe.window("late").slot(at(0, 5, day=29)), at(23, 50))
    check("a window laid a quarter of an hour before a midnight one opens the day before",
          (probe.window("early").slot(at(23, 56)), probe.window("early").is_open(at(0, 10, day=29))),
          (at(23, 55), False))
    check("weekdays: Saturday and Sunday only (2026-09-26/27), not Monday the 28th",
          [probe.window("weekend").is_open(at(12, 30, day=d)) for d in (26, 27, 28)],
          [True, True, False])
    check("the 29th of February of a year that has none is the 28th",
          [probe.window("leap").is_open(at(12, day=d, month=2, year=2027)) for d in (27, 28)],
          [False, True])
    check("a daily window within a season: at noon in it, not out of it",
          [probe.window("winter_noon").is_open(t) for t in
           (at(12, 30, day=31, month=12), at(12, 30, day=1, month=1, year=2027),
            at(12, 30, day=3, month=1, year=2027), at(13, 30, day=31, month=12))],
          [True, True, False, False])
    check("  ..and a window laid over it keeps to the season too: its gates at 11:50 on the"
          " 30th of December and the 2nd of January, not on the 28th of September or the 3rd"
          " of January", [probe.window("winter_gates").is_open(t) for t in
                          (at(11, 50, day=30, month=12), at(11, 50, day=2, month=1, year=2027),
                           at(11, 50), at(11, 50, day=3, month=1, year=2027),
                           at(12, 30, day=31, month=12))],
          [True, True, False, False, True])

    def refused(doc):
        try:
            events.Schedule(doc)
        except (ValueError, KeyError, TypeError) as exc:
            return type(exc).__name__
        return None

    check("a window with two kinds, one laid over nothing, a gate of no kind: refused",
          [refused({"windows": {"w": {"daily": ["12:00"], "dates": [["01-01", "01-02"]],
                                      "minutes": 5}}}),
           refused({"windows": {"w": {"of": "none", "from": 0, "to": 5}}}),
           refused({"windows": {"w": {"daily": ["25:00"], "minutes": 5}}}),
           refused({"windows": {"w": {"daily": ["12:00"], "minutes": 5}},
                    "quests": [{"window": "w", "types": [158], "gate": "sometimes"}]})],
          ["ValueError"] * 4)
    bad = events.Schedule({"windows": {"w": {"daily": ["12:00"], "minutes": 5}},
                           "spawns": [{"window": "w", "loc": CENTRE, "types": [1113]}],
                           "loot": [{"window": "w", "locs": [CENTRE], "mobs": [1113],
                                     "obj": 999999, "why": "t"}],
                           "quests": [{"window": "w", "types": [99999], "why": "t"}]})
    check("and what cannot work is named: no why, a creature the file has not, no thing,"
          " no quest", len(bad.problems(MT)), 5)
except Exception:
    fails.append("the windows broke:\n" + traceback.format_exc())


# --- the rows ------------------------------------------------------------------------------------
try:
    Q = {t: quests.get(t) for t in range(LATE_1, TALON_Q + 1)}
    check("the package's rows are 156-169, and nothing else of 156-179",
          ([t for t, q in Q.items() if q is None],
           [t for t in range(170, 180) if quests.get(t) is not None]), ([], []))
    check("given and taken by: Винс -> Тиль, Тиль; Хассир -> the southern guard; Хассир;"
          " the supply man; the two guards; Томас; the medics; Самуэль",
          {t: (q.give, q.take) for t, q in Q.items()},
          {LATE_1: ([VINS], [TIL]), LATE_2: ([TIL], [TIL]), INVITE: ([HASSIR], [SOUTH_GUARD]),
           RIDE: ([HASSIR], [HASSIR]), BACK: ([SUPPLY], [SUPPLY]),
           GATE_W: ([WEST_GUARD], [WEST_GUARD]), GATE_S: ([SOUTH_GUARD], [SOUTH_GUARD]),
           EXIT: ([TOMAS], [TOMAS]), TEN: ([877], [877]), TWENTY_FIVE: ([877], [877]),
           FIFTY: ([878], [878]), SEVENTY_FIVE: ([879], [879]), HUNDRED: ([879], [879]),
           TALON_Q: ([SAMUEL], [SAMUEL])})
    check("by the original's names", [Q[t].name for t in range(LATE_1, TALON_Q + 1)],
          ["Золотая лихорадка", "Золотая лихорадка", "Охранник санатория особого режима",
           "Поехали!", "Назад в Вади Хальфу", "Тюрьма: западные ворота", "Тюрьма: южные ворота",
           "Выход", "Сдать 10 повязок", "25 повязок", "50 повязок", "75 двухсотых",
           "Сдать 100 повязок", "500 патронов (За работу в тюрьме)"])
    with open(os.path.join(DATA, "orig_misc.json"), encoding="utf-8") as fh:
        pinned = {int(k): v["ids"] for k, v in json.load(fh)["quests"].items()}
    check("every row but the paid step is pinned to the original's lines (VERIFIED)",
          {t: pinned.get(t) for t in Q},
          {LATE_1: [62695, 62711, None, 62712], LATE_2: None, INVITE: [62257, 62258, None, 62259],
           RIDE: [62262, 62263, None, 59830], BACK: [62266, 62267, None, 59830],
           GATE_W: [None, 62272, 62273, None], GATE_S: [None, 62272, 62273, None],
           EXIT: [62276, 62277, None, 62278], TEN: [62279, 62280, None, 62281],
           TWENTY_FIVE: [62282, 62283, None, 62284], FIFTY: [62285, 62286, None, 62287],
           SEVENTY_FIVE: [62288, 62292, None, None], HUNDRED: [62290, 62291, None, None],
           TALON_Q: [61934, 61935, None, None]})
    check("the paid step keeps the original's first words, and no link to buy gold",
          (Q[LATE_2].texts[1].startswith("Да, теперь к шахте той доступ перекрыт. Но не все так плохо"),
           "PutGold" in Q[LATE_2].texts[1], Q[LATE_2].texts[3]), (True, False, "Удачи тебе."))
    check("the late gold rush follows 145, one step after the other, once each",
          [(Q[t].need_all, Q[t].repeatable) for t in (LATE_1, LATE_2)], [([145], 0), ([LATE_1], 0)])
    late = Q[LATE_2]
    check("the paid step: one ounce at the hand-in, ten (G) ЭК rounds of 140's six calibres",
          (late.cost_gold, late.cost_afro, late.rew_obj, late.num_rew_obj, late.rew_afro, late.rew_gold),
          (100, 0, EK_G, [10] * 6, 0, 0))
    worth = {t: (items.params_of(t)["g_cost"], items.params_of(t)["sell_num"], items.params_of(t)["cost"])
             for t in EK_G}
    # Worth the ounce at 2 G for 20; a gold round is a hundredth of an ounce
    # since the owner's word of 2026-09-28 (items.GOLD_AMMO_ROUND), so the
    # ten are a tenth of it now -- left for the owner to settle (UNDONE,
    # «Решения владельца по Хальфе»).
    check("  ..a tenth of the ounce it costs, at the stalls' own price: 0,20 G for 20, no afro"
          " price",
          {t: g * 10 // n for t, (g, n, _c) in worth.items()} == {t: late.cost_gold // 10
                                                                  for t in EK_G}
          and all(c == 0 for _g, _n, c in worth.values()), True)
    check("  ..1 G is 50 000 afro at the one rate", progression.GOLD_TO_AFRO_RATE * late.cost_gold // 100,
          50000)
    ways = [RIDE, BACK, GATE_W, GATE_S, EXIT]
    check("the rides, the gates and Томас's way are ways, bare: complete at the take, nothing"
          " paid or asked, repeatable, rew_loc", [(travel.is_quest_way(t), Q[t].kind, Q[t].obj,
                                                    Q[t].pays, Q[t].has_fee, Q[t].repeatable,
                                                    Q[t].rew_loc, Q[t].level, Q[t].need_all,
                                                    Q[t].is_complete(Q[t].fresh_progress()))
                                                   for t in ways],
          [(True, quests.DEL_OBJ, 0, False, False, 1, 1, 0, [], True)] * 5)
    targets = {t: travel.plan_quest_way(world.location(src), t, *world.cell_of(YARD)).loc_id
               for src, t in ((STATION, RIDE), (YARD, BACK), (YARD, GATE_W), (YARD, GATE_S),
                              (CENTRE, EXIT))}
    check("  ..leading: the station to the yard and back, the western gate into 644, the"
          " southern into 645, Томас up to the yard",
          targets, {RIDE: YARD, BACK: STATION, GATE_W: WEST, GATE_S: SOUTH, EXIT: YARD})
    check("the invitation is a talk of level 6, handed in only while the gates are open",
          (Q[INVITE].kind, Q[INVITE].level, Q[INVITE].repeatable, SCHEDULE.gates[INVITE][1],
           SCHEDULE.gates[INVITE][0].name), (quests.DEL_OBJ, 6, 0, "hand_in", "prison_wh_gates"))
    check("the ride and the gates are the gates' window's, both ways",
          [(SCHEDULE.gates[t][0].name, SCHEDULE.gates[t][1]) for t in (RIDE, GATE_W, GATE_S)],
          [("prison_wh_gates", "both")] * 3)
    check("the way back and Томас's are anybody's, any time",
          [t in SCHEDULE.gates for t in (BACK, EXIT)], [False, False])
    _clock = bosses.clock
    try:
        opened = []
        for moment in (at(11), at(11, 50)):
            bosses.clock = lambda: moment
            opened.append([events.quest_open(INVITE, carried) for carried in (False, True)]
                          + [events.quest_open(GATE_W, carried) for carried in (False, True)]
                          + [events.quest_open(TEN, False)])
    finally:
        bosses.clock = _clock
    check("  ..(events.quest_open: at 11:00 the invitation is taken but not handed in, the gate"
          " neither; at 11:50 both; a row it does not keep, always)",
          opened, [[True, False, False, False, True], [True, True, True, True, True]])
    medic = [(Q[t].kind, Q[t].objs[0][:2], Q[t].rew_afro, Q[t].rew_obj, Q[t].num_rew_obj,
              Q[t].per_day, Q[t].repeatable, Q[t].service)
             for t in (TEN, TWENTY_FIVE, FIFTY, SEVENTY_FIVE, HUNDRED)]
    check("the medics: 10 for 500 afro, 25 for 1250, 50 for 5000, 75 for two talons, 100 for"
          " 15 000; all but the ten once a day; all a day's tasks",
          medic,
          [(quests.BRING_L_OBJ, (BAND, 10), 500, [], [], 0, 1, False),
           (quests.BRING_L_OBJ, (BAND, 25), 1250, [], [], 1, 1, False),
           (quests.BRING_L_OBJ, (BAND, 50), 5000, [], [], 1, 1, False),
           (quests.BRING_L_OBJ, (BAND, 75), 0, [TALON], [2], 1, 1, False),
           (quests.BRING_L_OBJ, (BAND, 100), 15000, [], [], 1, 1, False)])
    talon = Q[TALON_Q]
    check("Самуэль: a talon for 500 rounds of one of the prison stores' twelve calibres,"
          " a service", (talon.objs[0][:2], talon.rew_obj, set(talon.num_rew_obj), talon.service,
                         talon.repeatable), ((TALON, 1), list(range(6140, 6152)), {500}, True, 1))
    check("  ..the (Q) ОТ 'Бережно хранились на тюремных складах', priced in gold alone",
          {(names.text(3_000_000 + t).endswith("Бережно хранились на тюремных складах."),
            items.params_of(t)["cost"], items.params_of(t)["g_cost"] > 0) for t in talon.rew_obj},
          {(True, 0, True)})
    payers = {t: (q.num_rew_obj[q.rew_obj.index(TALON)], [o[1] for o in q.objs if o[0] == BAND],
                  q.per_day) for t, q in quests.QUESTS.items() if TALON in q.rew_obj}
    per_talon = {500 * items.params_of(t)["g_cost"] // items.params_of(t)["sell_num"]
                 for t in talon.rew_obj}
    check("the talons come from Томпсон's 75 alone, two once a day: 37.5 armbands a talon, the"
          " original's rate (62292), and no row of the whole table pays one faster",
          payers, {SEVENTY_FIVE: (2, [75], 1)})
    check("  ..a talon is 500 rounds, 5 G at the stalls' gold price: 10 G of rounds a day at"
          " most, 500 000 afro at the one rate, which no stall buys back",
          (per_talon, 2 * max(per_talon) * progression.GOLD_TO_AFRO_RATE // 100),
          ({500}, 500_000))
    paid = sorted({t for q in Q.values() for t in q.rew_obj + [o for o, _n in q.rew_also]})
    check("nothing any of them pays is premium (the owner's (P) out of the game)",
          [t for t in paid + [BAND] if items.premium(t)], [])
    check("every thing they name is the game's (quests.check_items)", quests.check_items(), None)
    blob = names.document_bytes()
    check("every string id of theirs is in the preload and the launcher's table",
          [sid for q in Q.values() for sid in q.string_ids()
           if not names.known(sid) or ("<s id='%d'>" % sid).encode() not in blob], [])
    check("the armband goes by the original's name and description (7323/7324)",
          (names.text(1_000_000 + BAND), names.text(3_000_000 + BAND)),
          ("Красная повязка ВХ", "Красная повязка, сорванная с ваших соперников"))
    band = items.params_of(BAND)
    check("  ..and is the blocks' own (events.kept): the quest flag and no exchange, so no letter,"
          " lot, barter or stall takes it out, and a death does not drop it; the talon is not kept",
          (events.kept(BAND), band["quest"], band["exchang"], mail.postable(BAND),
           barter.tradable(BAND), combat.drops_on_death(BAND), events.kept(TALON)),
          (True, 1, 0, False, False, False, False))
    # The level each fights at in front of a mob's name (names._mob_level):
    # which also says events.py did not leave mobs half-imported when
    # names.ALL was built.
    check("the prison's people and prisoners go by theirs, a mob with its level",
          [names.text(t) for t in [TOMAS] + MEDICS + [GODFATHER, 1113, 1117, GUARD_IN]],
          ["Томас<br>Выход из тюрьмы", "Джеф<br>Патологоанатом", "Аль-Назир<br>Коронер",
           "Томпсон<br>Судмедэксперт", "[8] Беглый каторжник<br>Хранитель общака",
           "[8] Заключенный", "[8] Заключенный", "[20] Макисе Курису"])

    # The blocks: sides into each other, no map, the armbands kept in.
    ends = {}
    for lid in BLOCKS:
        loc = world.location(lid)
        for side in travel.SIDES:
            cells = sorted(c for c, s in travel.exit_sides(loc).items() if s == side)
            if cells:
                ends[(lid, side)] = travel.plan_exit(loc, cells[0], *world.cell_of(YARD)).loc_id
    check("the centre opens on all four sides into the other four, each of which opens back",
          ends, {(CENTRE, "W"): WEST, (CENTRE, "S"): SOUTH, (CENTRE, "N"): NORTH_CELLS,
                 (CENTRE, "E"): EAST_CELLS, (WEST, "E"): CENTRE, (SOUTH, "N"): CENTRE,
                 (NORTH_CELLS, "S"): CENTRE, (EAST_CELLS, "W"): CENTRE})
    check("the blocks are left only by their ways: no map from them (travel.no_map)",
          [travel.no_map(lid) for lid in BLOCKS + [YARD]], [True] * 5 + [False])
    check("the armbands stay in the blocks, and drop only there, off the prisoners and the"
          " godfather, one each",
          (SCHEDULE.keep_in, sorted(SCHEDULE.loot)),
          ([(frozenset([BAND]), frozenset(BLOCKS))],
           sorted((loc, mob) for loc in (CENTRE, NORTH_CELLS, EAST_CELLS)
                  for mob in PRISONERS + [GODFATHER])))
    rng = __import__("random").Random(3)
    check("  ..(events.loot: a prisoner in the cells, nobody in the yard)",
          (events.loot(NORTH_CELLS, 1113, rng), events.loot(YARD, 1113, rng)), ([(BAND, 1)], []))

    # Who stands: the file's own, left to the room or to the schedule.
    def stands(lid):
        return sorted(n.type_id for n in rooms.Room(world.location(lid), rooms.IdAllocator(),
                                                    MT).npcs.values())
    check("the rooms build none of the uprising's people themselves, and never the guard:"
          " Томас alone in the centre, the cells and the blocks empty",
          [stands(lid) for lid in BLOCKS], [[], [], [TOMAS], [], []])
    check("  ..the yard as it was: the healer, the guards, the supply man",
          stands(YARD), sorted([2111, WEST_GUARD, SOUTH_GUARD, SUPPLY]))
    check("world.belongs_here leaves them to the schedule (events.owns), place by place",
          [world.belongs_here(t, MT[t][1], MT[t][0], True, lid) for t, lid in
           ((1113, NORTH_CELLS), (GODFATHER, CENTRE), (877, CENTRE), (GUARD_IN, WEST),
            (TOMAS, CENTRE), (1113, None))],
          [False, False, False, False, True, True])
except Exception:
    fails.append("the rows broke:\n" + traceback.format_exc())


# --- real rooms on a clock turned by hand --------------------------------------------------------
class _Seat(object):
    """A session standing in the room: whatever reaches it is kept."""
    pid = rooms.player_id(1)

    def __init__(self):
        self.sent = []
        self.combat = type("F", (), {"aim": None, "strike": None, "last_pvp": -1e9,
                                     "dead": False})()

    def send(self, cmd, **params):
        self.sent.append((cmd, params))

    def send_npc_info(self, npc_id):
        self.sent.append(("npc_info", dict(id=npc_id)))

    def take(self):
        out, self.sent = self.sent, []
        return out


NOW = [0.0]


def news(frames):
    return [p["newUser"] for n, p in frames if n == "lch" and "newUser" in p]


def gone(frames):
    return [p["lostUser"] for n, p in frames if n == "lch" and "lostUser" in p]


def built(lid, store):
    room = rooms.Room(world.location(lid), rooms.IdAllocator(), MT)
    rc = combat.RoomCombat(room, store)
    seat = _Seat()
    room.players[seat] = True
    return room, rc, seat


async def _rooms():
    store = accounts.Store(os.path.join(tempfile.mkdtemp(), "events.db"))
    combat.CORPSE_DELAY, combat.RESPAWN_DELAY = 0.05, 0.1
    real_clock = bosses.clock
    bosses.clock = lambda: NOW[0]
    try:
        NOW[0] = at(11, 59)
        cells, rc, seat = built(NORTH_CELLS, store)
        rc.keep_hours()
        check("at 11:59 the northern cells are empty", (seat.take(), cells.npcs), ([], {}))
        NOW[0] = at(12)
        rc.keep_hours()
        got = seat.take()
        spots = sorted((c, t) for c, t in world.location(NORTH_CELLS).spawns)
        check("at noon ten prisoners break out, each on its own cell, as mobs, with their details",
              (sorted((n.cell, n.type_id) for n in cells.npcs.values()), len(news(got)),
               sorted(p["rtype"] for n, p in got if n == "lch"),
               len([1 for n, _p in got if n == "npc_info"])),
              (spots, 10, [world.MOB] * 10, 10))
        check("  ..numbered apart, above the rooms' counter (events.FIRST_ID)",
              min(cells.npcs) >= events.FIRST_ID, True)
        rc.keep_hours()
        check("  ..and a second look changes nothing", seat.take(), [])

        eid = min(cells.npcs)
        mob = rc.mobs[eid]
        NOW[0] = at(12, 10)
        rc.kill(mob, None)
        await asyncio.sleep(0.12)                 # the corpse fades, the bag drops
        bag = [store.item(u)["type_id"] for b in rc.loot.values() for u in b.uniqs]
        check("one killed leaves the red armband in its bag", BAND in bag, True)
        await asyncio.sleep(0.2)                  # the respawn delay passes
        check("  ..and is back after the respawn delay, while the uprising lasts",
              (eid in cells.npcs, mob.alive, news(seat.take())[-1:]), (True, True, [eid]))

        other = rc.mobs[sorted(cells.npcs)[1]]
        other.target = object()
        NOW[0] = at(12, 30)
        rc.keep_hours()
        got = seat.take()
        check("at half past the other nine go back to the cells, the one in a fight stays",
              (len(gone(got)), other.eid in cells.npcs, other.leaving), (9, True, True))
        other.target = None
        rc.keep_hours()
        check("  ..and goes when the fight is over", (gone(seat.take()), cells.npcs),
              ([other.eid], {}))

        NOW[0] = at(16)
        rc.keep_hours()
        victim = rc.mobs[eid]
        NOW[0] = at(16, 29, 59)
        rc.kill(victim, None)
        NOW[0] = at(16, 30)
        rc.keep_hours()
        await asyncio.sleep(0.4)
        check("one killed as the uprising ends is not made again when its respawn comes",
              (eid in cells.npcs, victim.alive, victim.away), (False, False, True))
        seat.take()
        NOW[0] = at(23)
        rc.keep_hours()
        check("  ..but breaks out with the others at the next one, whole",
              (len(news(seat.take())), eid in cells.npcs, victim.hp == victim.hp_max),
              (10, True, True))
        for b in rc.loot.values():
            if b.expiry is not None:
                b.expiry.cancel()

        # The centre: Томас always, the godfather once an uprising, the medics
        # for its last five minutes.
        NOW[0] = at(11, 50)
        centre, rc2, seat2 = built(CENTRE, store)
        rc2.keep_hours()
        check("at 11:50 the centre holds Томас alone", sorted(n.type_id for n in centre.npcs.values()),
              [TOMAS])
        NOW[0] = at(12)
        rc2.keep_hours()
        check("at noon the godfather comes", [centre.npcs[i].type_id for i in news(seat2.take())],
              [GODFATHER])
        boss = [m for m in rc2.mobs.values() if m.type_id == GODFATHER][0]
        NOW[0] = at(12, 5)
        rc2.kill(boss, None)
        await asyncio.sleep(0.4)
        NOW[0] = at(12, 20)
        rc2.keep_hours()
        check("killed, he is not back while the uprising lasts (a boss comes once an opening)",
              (boss.eid in centre.npcs, boss.away), (False, True))
        seat2.take()
        NOW[0] = at(12, 25)
        rc2.keep_hours()
        got = seat2.take()
        first_medics = news(got)
        check("at 12:25 the three medics come, as Commoners, with their details",
              (sorted(centre.npcs[i].type_id for i in news(got)),
               sorted(p["rtype"] for n, p in got if n == "lch")),
              (MEDICS, [world.COMMONER] * 3))
        NOW[0] = at(12, 30)
        rc2.keep_hours()
        check("at half past they go, and Томас stays",
              (len(gone(seat2.take())), sorted(n.type_id for n in centre.npcs.values())), (3, [TOMAS]))
        NOW[0] = at(16)
        rc2.keep_hours()
        check("the godfather is back at four, whole",
              (boss.eid in centre.npcs, boss.hp == boss.hp_max), (True, True))
        seat2.take()
        NOW[0] = at(16, 25)
        rc2.keep_hours()
        again = news(seat2.take())
        check("  ..and at 16:25 the medics come again under new ids: the client asks their rows"
              " afresh (a day's task done yesterday is on offer again)",
              (sorted(centre.npcs[i].type_id for i in again), set(again) & set(first_medics)),
              (MEDICS, set()))
        for b in rc2.loot.values():
            if b.expiry is not None:
                b.expiry.cancel()

        # The western block: its guard never.
        west, rc3, seat3 = built(WEST, store)
        rc3.keep_hours()
        check("the western block at the uprising: nobody (the guard is held out)",
              (west.npcs, seat3.take()), ({}, []))

        # A room made in the middle of the uprising -- after a restart, with
        # nothing remembered -- has it at once.
        NOW[0] = at(23, 10)
        fresh, rc4, seat4 = built(EAST_CELLS, store)
        rc4.keep_hours()
        check("a room built in the middle of an uprising has its ten prisoners at once",
              len(fresh.npcs), 10)

        # The marks (events._remark): the client asks q_status of an NPC id
        # once, so whoever gives or takes a row the gates keep is shown
        # under a new id at each of their edges, and nobody else.
        NOW[0] = at(11, 44)
        yard, rc5, seat5 = built(YARD, store)
        rc5.keep_hours()
        seat5.take()
        before = {i: n.type_id for i, n in yard.npcs.items()}
        NOW[0] = at(11, 45)
        rc5.keep_hours()
        got = seat5.take()
        now_ = {i: n.type_id for i, n in yard.npcs.items()}
        check("at 11:45 the gates open: both guards of the yard go (lostUser) and come back under"
              " new ids with their details; the supply man and the healer keep theirs",
              (sorted(before[i] for i in gone(got)), sorted(now_[i] for i in news(got)),
               sorted(now_[p["id"]] for n, p in got if n == "npc_info"),
               sorted(t for i, t in before.items() if i in now_),
               min(news(got)) >= events.FIRST_ID),
              (sorted([WEST_GUARD, SOUTH_GUARD]),) * 3 + (sorted([2111, SUPPLY]), True))
        NOW[0] = at(12, 10)
        rc5.keep_hours()
        check("  ..not again while the gates stay open (the uprising's start is no edge of theirs)",
              seat5.take(), [])
        NOW[0] = at(12, 30)
        rc5.keep_hours()
        check("  ..and again at 12:30, when they shut",
              sorted(yard.npcs[i].type_id for i in news(seat5.take())),
              sorted([WEST_GUARD, SOUTH_GUARD]))
        NOW[0] = at(13)
        events.taken(TEN)                   # a row of no window
        events.taken(RIDE)                  # both ways: carried or not, the window's
        rc5.keep_hours()
        quiet = seat5.take()
        events.taken(INVITE)                # the invitation, the gates shut
        rc5.keep_hours()
        check("the invitation taken with the gates shut: its taker, the southern guard, is shown"
              " again (the client asks nothing after a take, and would offer a hand-in the"
              " server refuses); a row of no window, or of both ways, changes nothing",
              (quiet, [yard.npcs[i].type_id for i in news(seat5.take())]), ([], [SOUTH_GUARD]))
        NOW[0] = at(15, 50)
        events.taken(INVITE)                # the gates open: its status stands
        rc5.keep_hours()
        check("  ..taken with the gates open, nothing but their edge (both guards, once)",
              sorted(yard.npcs[i].type_id for i in news(seat5.take())),
              sorted([WEST_GUARD, SOUTH_GUARD]))
        NOW[0] = at(22, 40)
        station, rc6, seat6 = built(STATION, store)
        rc6.keep_hours()
        seat6.take()
        NOW[0] = at(22, 45)
        rc6.keep_hours()
        check("at the station Хассир, whose ride keeps the gates' hours, is shown again at 22:45,"
              " and nobody else", [station.npcs[i].type_id for i in news(seat6.take())], [HASSIR])
        check("  ..the marked are Хассир and the two guards alone, by the gates' window: nobody in"
              " the blocks (Томас's way and the medics' rows are no window's)",
              {t: [w.name for w in ws] for t, ws in SCHEDULE.marked().items()},
              {HASSIR: ["prison_wh_gates"], WEST_GUARD: ["prison_wh_gates"],
               SOUTH_GUARD: ["prison_wh_gates"]})
    finally:
        bosses.clock = real_clock
        store.close()


try:
    asyncio.run(_rooms())
except Exception:
    fails.append("the rooms on a hand-turned clock broke:\n" + traceback.format_exc())


# --- a season on a table of its own --------------------------------------------------------------
VALENTINE = {"windows": {"valentine": {"dates": [["02-10", "02-18"]], "why": "the test's season"}},
             "spawns": [{"window": "valentine", "loc": BLACK_MARKET, "types": [SAVIN],
                         "why": "the test's: Савин's presents stall"}]}
try:
    real_table, real_clock = events._TABLE, bosses.clock
    events._TABLE = events.Schedule(VALENTINE)
    try:
        check("the test's season holds together", events.table().problems(MT), [])
        market = rooms.Room(world.location(BLACK_MARKET), rooms.IdAllocator(), MT)
        check("the market's room never builds the stall itself: the season's",
              SAVIN in [n.type_id for n in market.npcs.values()], False)
        store = accounts.Store(os.path.join(tempfile.mkdtemp(), "season.db"))
        rc = combat.RoomCombat(market, store)
        seat = _Seat()
        market.players[seat] = True
        seen = []
        for day, month, year in ((9, 2, 2027), (10, 2, 2027), (18, 2, 2027), (19, 2, 2027),
                                 (10, 2, 2028)):
            NOW[0] = at(12, day=day, month=month, year=year)
            bosses.clock = lambda: NOW[0]
            rc.keep_hours()
            got = seat.take()
            seen.append((SAVIN in [n.type_id for n in market.npcs.values()],
                         len(news(got)), len(gone(got))))
        check("switched on by the date and off again: out on the 9th, in on the 10th and the"
              " 18th, out on the 19th, in the next year",
              seen, [(False, 0, 0), (True, 1, 0), (True, 0, 0), (False, 0, 1), (True, 1, 0)])
        store.close()
    finally:
        events._TABLE, bosses.clock = real_table, real_clock
except Exception:
    fails.append("the season broke:\n" + traceback.format_exc())


# --- the server ----------------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.watch = None               # an Inspector fed every frame read

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

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        out = [decode(f.decode(ENC)) for f in parts if f]
        if self.watch is not None:
            self.watch.feed(out)
        return out

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._split()

    def until(self, pred, wait=3.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._split()
            out += new
            if any(pred(f) for f in new):
                break
        return out


class Inspector(object):
    """The client's QuestInspector, as far as it decides when to ask
    q_status: once per quest type, and again only for an NPC id it has not
    met (checkQStatus: !checkedQuests[type] || !checkedNPC[npc], asked from
    NPC.userInfo for each give and take type). Its other way to ask again,
    after a hand-in or a drop answered 0 (requestAllNPC), is left out: the
    edges of a window are proved without it. Nothing is asked by hand --
    what the server does not make the client ask, it never learns."""

    def __init__(self, client):
        self.c = client
        self.checked_q, self.checked_npc = set(), set()
        self.here = {}                  # npc id -> its type, of the location
        self.available = {}             # quest type -> the last status heard
        self.asked = []

    def feed(self, frames):
        for name, p in frames:
            if name == "lcall":
                self.here = {}
            elif name == "lch" and "lostUser" in p:
                self.here.pop(p["lostUser"], None)
            elif name.startswith("userInfo") and name != "userInfo_Player" \
                    and "give_quests" in p:
                self.here[p["id"]] = p["name"]
                for t in list(p["give_quests"]) + list(p["take_quests"]):
                    if t not in self.checked_q or p["id"] not in self.checked_npc:
                        self.checked_q.add(t)
                        self.checked_npc.add(p["id"])
                        self.asked.append(t)
                        self.c.send("q_status;q_type=%d;" % t)
            elif name == "q_status":
                self.available[p["type"]] = p["status"]

    def npc(self, type_id):
        """The id the NPC of this type goes by here now."""
        ids = [i for i, t in self.here.items() if t == type_id]
        return ids[0] if ids else None


def asked_of(c, qtype, wait=4.0):
    """Frames read until the client's own q_status about the type is answered."""
    return c.until(lambda f: f[0] == "q_status" and f[1].get("type") == qtype, wait)


def named(frames, name):
    return [p for n, p in frames if n == name]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def infos(frames):
    """type id -> its npc id, of a population (userInfo_* but a player's)."""
    return {p["name"]: p["id"] for n, p in frames
            if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p}


class Server:
    def __init__(self, clock, schedule=None, tag="srv"):
        self.port = free_port()
        self.db = os.path.join(tempfile.mkdtemp(), "events_%s.db" % tag)
        accounts.DB_PATH = self.db
        st = accounts.Store(self.db)
        st.register(tag, "secret")
        st.close()
        self.cred = accounts.credential(tag, "secret")
        self.start = clock
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1", LAVA_DB=self.db,
                   LAVA_CHEATS="1", LAVA_GX="5985", LAVA_GY="1744", LAVA_SEED="5",
                   LAVA_POLICY_PORT="0",
                   LAVA_BOSS_CLOCK=datetime.fromtimestamp(clock, bosses.ZONE)
                   .replace(tzinfo=None).isoformat())
        if schedule:
            env["LAVA_SCHEDULE"] = schedule
        self.launched = time.time()
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.log = []
        self.drain = threading.Thread(target=lambda: self.log.extend(self.proc.stdout), daemon=True)
        self.drain.start()

    def est(self):
        """The server's clock by now, or a moment ahead of it."""
        return self.start + (time.time() - self.launched)

    def wait_until(self, t):
        left = t - self.est()
        if left > 0:
            time.sleep(left)

    def connect(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            try:
                return Client(socket.create_connection(("127.0.0.1", self.port), 0.5))
            except OSError:
                time.sleep(0.1)
        raise SystemExit("server did not start")

    def login(self, nick):
        c = self.connect()
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % self.cred)
        c.frames()
        c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
        c.frames()
        c.send("actPlayer;")
        c.until(lambda f: f[0] == "lcall")
        c.send("lenter;accept=1;")
        return c, c.frames(1.5)

    def char_id(self):
        st = accounts.Store(self.db)
        cid = st.db.execute("SELECT id FROM characters ORDER BY id DESC LIMIT 1").fetchone()["id"]
        st.close()
        return cid

    def owned(self):
        st = accounts.Store(self.db)
        out = {}
        for r in st.items_of(self.char_id()):
            out[r["type_id"]] = out.get(r["type_id"], 0) + (
                r["count"] if r["root"] in items.HEAPABLE_ROOTS else 1)
        st.close()
        return out

    def purse(self):
        st = accounts.Store(self.db)
        got = tuple(st.money(self.char_id()))
        st.close()
        return got

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self.drain.join(timeout=5)
        out = "".join(self.log)
        if "Traceback" in out:
            fails.append("server logged a traceback:\n" + out[-2500:])
        elif fails:
            story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
            fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return c.frames(1.5)


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = c.until(lambda f: f[0] == "q_status", 2)
    return [p["status"] for p in named(got, "q_status")]


def take(c, npc, qtype, npc_type):
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    return c.frames(0.8)


def hand_in(c, npc, q_id, obj_idx=0):
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(0.8)


def q_id_of(frames):
    ids = [p["q_id"] for n, p in frames if n.startswith("q_di_")]
    return ids[0] if ids else 0


def complete_of(frames):
    return [p["complete"] for n, p in frames if n.startswith("q_di_")]


# The first server: the real table's rows, the uprising at noon for ninety
# seconds, its gates half a minute before, its medics the last thirty; and a
# season holding Савин's stall in the black market, the clock in it.
with open(os.path.join(DATA, "schedule.json"), encoding="utf-8") as _fh:
    SHORT = json.load(_fh)
SHORT["windows"]["prison_wh"].update(daily=["12:00"], minutes=1.5)
SHORT["windows"]["prison_wh_gates"].update({"from": -0.5, "to": 1.5})
SHORT["windows"]["prison_wh_medics"].update({"from": 1.0, "to": 1.5})
SHORT["windows"].update(VALENTINE["windows"])
SHORT["spawns"] += VALENTINE["spawns"]
SHORT_FILE = os.path.join(tempfile.mkdtemp(), "schedule.json")
with open(SHORT_FILE, "w", encoding="utf-8") as _fh:
    json.dump(SHORT, _fh, ensure_ascii=False)
NOON = at(12, day=14, month=2, year=2027)
GATES, MEDIC_TIME, END = NOON - 30, NOON + 60, NOON + 90

srv = Server(NOON - 55, SHORT_FILE, "warden")
try:
    c, _arrival = srv.login("Warden")
    here = infos(goto(c, BLACK_MARKET))
    check("in season (the test's table) Савин's stall stands in the black market",
          SAVIN in here, True)
    # From here on the client asks q_status as the real one does, and never
    # by hand: on first sight of an NPC id alone.
    marks = c.watch = Inspector(c)
    yard = infos(goto(c, YARD))
    asked_of(c, GATE_W)
    print("  ..  %.1f s to spare before the gates open" % (GATES - srv.est()))
    check("(and that was before the gates opened on the server's clock)", srv.est() < GATES, True)
    check("the yard: its guards, its supply man, its healer",
          sorted(t for t in yard if t in (WEST_GUARD, SOUTH_GUARD, SUPPLY, 2111)),
          sorted([WEST_GUARD, SOUTH_GUARD, SUPPLY, 2111]))
    check("before the gates open the client, asking on first sight of the guard, has the western"
          " gate shut", marks.available.get(GATE_W), 0)
    got = take(c, marks.npc(WEST_GUARD), GATE_W, WEST_GUARD)
    check("  ..and taking it is refused, one ack", acks(got), [4])
    shut_ids = {t: marks.npc(t) for t in (WEST_GUARD, SOUTH_GUARD, SUPPLY, 2111)}
    asked = len(marks.asked)
    srv.wait_until(GATES + 1)
    asked_of(c, GATE_W)
    check("the gates open before a player standing by: both guards shown again under new ids,"
          " the client asks of itself, and the western gate is on offer (nothing asked by hand)",
          ({t: marks.npc(t) != i for t, i in shut_ids.items()}, marks.available.get(GATE_W),
           GATE_W in marks.asked[asked:], GATE_S in marks.asked[asked:]),
          ({WEST_GUARD: True, SOUTH_GUARD: True, SUPPLY: False, 2111: False}, 1, True, True))
    open_west = marks.npc(WEST_GUARD)
    got = take(c, open_west, GATE_W, WEST_GUARD)
    check("  ..taken, it is complete at once", (acks(got), complete_of(got)), ([0], [1]))
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (open_west, q_id_of(got)))
    got = c.until(lambda f: f[0] == "lcall", 3)
    check("  ..handed back: the ack, then down into the western block",
          ([n for n, _p in got][-2:], named(got, "lcall")[0]["id"] if named(got, "lcall") else None),
          (["cmdAck", "lcall"], WEST))
    c.send("lenter;accept=1;")
    down = c.frames(1.5)
    check("  ..where the guard of the blocks does not stand, and the map is out of reach"
          " (the sublocation bit)", (infos(down), bool(named(got, "lcall")[0]["g_id"] >> 26 & 1)),
          ({}, True))
    cells = goto(c, NORTH_CELLS)
    check("before noon the northern cells are empty", infos(cells), {})
    srv.wait_until(NOON)
    got = c.until(lambda f: f[0] == "lch" and "newUser" in f[1], 6)
    got += c.frames(1.0)
    check("at noon ten prisoners break out in front of the player",
          (len([p for p in named(got, "lch") if "newUser" in p]),
           sorted({p["name"] for n, p in got if n == "userInfo"})),
          (10, PRISONERS))
    got = goto(c, CENTRE)
    centre = infos(got)
    check("the centre: Томас and the godfather, no medics yet",
          sorted(t for t in centre if t in [TOMAS, GODFATHER] + MEDICS), sorted([TOMAS, GODFATHER]))
    homes = {p["name"]: p.get("can_set_home") for n, p in got if n == "userInfo_Commoner"}
    c.send("on_conv;mob=%d;op=0;" % centre[TOMAS])
    check("Томас offers no «Прописка» where the map is out of reach, and on_conv;op=0 at him is"
          " refused (Session.home_here): /home never leads past the gates",
          (homes.get(TOMAS), acks(c.frames(0.6))), (0, [2]))
    srv.wait_until(MEDIC_TIME)
    got = c.until(lambda f: f[0] == "lch" and "newUser" in f[1], 6)
    got += c.frames(1.0)
    medics = infos(got)
    check("for the last half minute (the test's table) the three medics come",
          sorted(t for t in medics if t in MEDICS), MEDICS)
    check("  ..offering no «Прописка» either",
          sorted(p.get("can_set_home") for n, p in got if n == "userInfo_Commoner"
                 and p["name"] in MEDICS), [0, 0, 0])
    c.send("userMsg;entry=@/give %d 15@;group=0;" % BAND)
    c.frames()
    got = take(c, medics[877], TEN, 877)
    check("Джеф's ten armbands: taken, complete with fifteen in the bag",
          (acks(got), complete_of(got)), ([0], [1]))
    afro0 = srv.purse()[0]
    got = hand_in(c, medics[877], q_id_of(got))
    check("  ..handed in: ten armbands out, 500 afro in",
          (acks(got), srv.purse()[0] - afro0, srv.owned().get(BAND)), ([0], 500, 5))
    got = take(c, centre[TOMAS], EXIT, TOMAS)
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (centre[TOMAS], q_id_of(got)))
    got = c.until(lambda f: f[0] == "lcall", 3)
    c.send("lenter;accept=1;")
    c.frames(1.5)
    check("Томас's way out: up in the yard, the five armbands left below",
          (named(got, "lcall")[0]["id"] if named(got, "lcall") else None,
           srv.owned().get(BAND), [p["status"] for p in named(got, "ss_obj_status")]),
          (YARD, None, [0]))
    open_ids = {t: marks.npc(t) for t in (WEST_GUARD, SOUTH_GUARD)}
    asked = len(marks.asked)
    srv.wait_until(END + 1)
    asked_of(c, GATE_W)
    check("the uprising over before a player standing in the yard: both guards shown again,"
          " the client asks of itself, and the gates are shut to it",
          ({t: marks.npc(t) not in (None, i) for t, i in open_ids.items()},
           marks.available.get(GATE_W), GATE_S in marks.asked[asked:]),
          ({WEST_GUARD: True, SOUTH_GUARD: True}, 0, True))
    after_c = infos(goto(c, CENTRE))
    after_n = infos(goto(c, NORTH_CELLS))
    check("the uprising over: the godfather and the medics gone, the cells empty, Томас stays",
          (sorted(t for t in after_c if t in [TOMAS, GODFATHER] + MEDICS), after_n), ([TOMAS], {}))
    c.send("logout;")
    c.frames(0.3)
except Exception:
    fails.append("the uprising on a socket broke:\n" + traceback.format_exc())
finally:
    srv.stop()


# The second server: the real table, started in the middle of the real
# uprising -- nothing remembered, all of it computed.
srv = Server(at(12, 0, 40), None, "prospector")
try:
    c, _arrival = srv.login("Prospector")
    cells = infos(goto(c, NORTH_CELLS))
    check("a server started in the middle of the uprising: the prisoners are there at once",
          sorted(t for t in cells if t in PRISONERS), PRISONERS)
    check("  ..and out of season Савин's stall is not in the black market (world.EVENT_TOKENS)",
          SAVIN in infos(goto(c, BLACK_MARKET)), False)

    st = accounts.Store(srv.db)
    st.db.execute("INSERT INTO char_quests_done (char_id, type, done_at) VALUES (?, ?, ?)",
                  (srv.char_id(), 145, int(time.time())))
    st.db.commit()
    st.close()
    market = infos(goto(c, OLD_MARKET))
    check("after Винс's reward (145) his word on the mine is on offer", status(c, LATE_1), [1])
    got = take(c, market[VINS], LATE_1, VINS)
    check("  ..a talk, complete at the take", (acks(got), complete_of(got)), ([0], [1]))
    q1 = q_id_of(got)
    black = infos(goto(c, BLACK_MARKET))
    got = hand_in(c, black[TIL], q1)
    check("  ..handed in to Тиль", acks(got), [0])
    check("Тиль's paid step is on offer now, once", status(c, LATE_2), [1])
    got = take(c, black[TIL], LATE_2, TIL)
    check("  ..taken with no gold: the journal says not complete (the fee is part of it)",
          (acks(got), complete_of(got)), ([0], [0]))
    q2 = q_id_of(got)
    c.send("userMsg;entry=@/money 0 100@;group=0;")
    got = c.frames(1.0)
    check("  ..an ounce in the purse and the journal is told complete",
          [p["complete"] for n, p in got if n.startswith("q_di_") and p.get("q_id") == q2], [1])
    afro1, gold1 = srv.purse()
    got = hand_in(c, black[TIL], q2, obj_idx=0)
    check("  ..handed in: the ounce taken, ten rounds of the calibre chosen, no afro",
          (acks(got), srv.purse(), srv.owned().get(EK_G[-1])), ([0], (afro1, gold1 - 100), 10))
    check("  ..and never again", status(c, LATE_2), [0])
    c.send("userMsg;entry=@/give %d 1@;group=0;" % TALON)
    c.frames()
    got = take(c, black[SAMUEL], TALON_Q, SAMUEL)
    check("Самуэль takes a talon: complete with one in the bag", (acks(got), complete_of(got)),
          ([0], [1]))
    got = hand_in(c, black[SAMUEL], q_id_of(got), obj_idx=11)
    check("  ..for 500 rounds of the calibre chosen (the first of the list), no q_sys (a service)",
          (acks(got), srv.owned().get(TALON), srv.owned().get(6140), "q_sys" in [n for n, _p in got]),
          ([0], None, 500, False))
    c.send("logout;")
    c.frames(0.3)
except Exception:
    fails.append("the restart and the gold rush on a socket broke:\n" + traceback.format_exc())
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("halfa events OK")
