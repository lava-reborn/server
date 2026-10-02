"""What a quest can do beyond talk and money, on a table of its own: the
mechanics the Nubian valley's quests need (the owner's «давай готовь квесты
все», 2026-09-26), held to on a socket before those quests are written.

The table is the real data/quests.json with the suite's own quests put on top, handed
to the server and to this process through LAVA_QUESTS (quests.quests_path),
the way test_walk_in keeps a mechanism on a passages table of its own. Their
NPCs stand where the suite plays, on the Black market of Wadi Halfa (102):
Техногик 652, Аарон 2424 (a bank), Шихаб 653, Точильный камень 2279. What is
held to here:

  * every thing a row names -- the reward, what is handed over, what is to
    be delivered or brought -- is a thing the game has, and what is handed
    over is worth nothing away from its quest (quests.check_items): a
    table that breaks either does not start the server, which is tried on
    a second one;
  * a parcel (start_obj): taken, the quest puts it in the bag before the ack
    -- ss_obj_status 1 and its dynamic info -- and the delivery starts found
    and complete; the bag decides that flag from then on (Quest.counts_bag),
    so a parcel put away is a delivery that cannot be handed in, with the
    journal told; handed in, the parcel leaves the bag;
  * the reward thing (rew_obj) goes into the bag before the ack, so the
    client lists it under «Вы получили», and so does the experience
    (rew_xp: rp_info for the skill) and the money; and all of it past the
    carry limit too (server.QUEST_ITEMS_PAST_WEIGHT), since a refusal would
    read as the daily limit;
  * the daily limit counts repeatable quests only: with the day spent a
    one-off quest is still handed in, and the count it shows does not move,
    while a repeatable one is refused (44) and, handed in on a fresh day,
    brings the new count along (q_sys) before the ack;
  * a chain: need_quest (all of them) and need_any (one of them) keep a
    quest off the NPC until what comes before it is handed in; a one-off
    quest handed in is never offered again;
  * dropping a quest (q_ca) takes back what its giver handed over, from the
    bag, from the hands and the body, and from the bank, and a dropped
    one-off quest can be taken again; the hand-in takes it back as well,
    what the quest asked for and the rest of what was handed over
    (quests.START_OBJ_BACK_AT_HAND_IN);
  * a cap (max_level): past it the quest is not offered, and one carried
    from below it is no longer this player's -- not shown, not handed in;
  * what a quest hands over never falls at a death (quests.kept_on_death),
    while the rest of the bag rolls as always (LAVA_BAG_DROP at 100 here).

And what Вади-Хальфа's quests need (2026-09-28), on more rows of the same
kind and two ways of the market's own (LAVA_PASSAGES):

  * a fee (cost_afro, cost_gold) is part of completeness: short of it the
    journal says not complete and a hand-in is refused with nothing taken;
    the purse filled, the journal is told at once; handed in, the fee goes;
  * a prize drawn (rew_random) is one of its list, by weight;
  * experience into a specialisation (rew_spec_xp) is asked for learned
    (requires_spec) and goes into it alone;
  * a thing lent (lent) is sold nowhere, bartered, posted and thrown down
    by nobody, never falls at a death, and comes back at the drop and at
    the hand-in from the hand and the bank as well as the bag; a stall's
    ware cannot be lent;
  * a service is neither counted nor refused by the daily limit, and a
    journal of twenty-five quests still takes a service and a way (the
    client is told thirty-five);
  * a way is handed in like any quest -- refused before its kills, paid,
    charged, written into the history that opens its child -- and then
    moves the player; «В Хальфу!» and «Назад, в долину» still repeat;
  * a slot's own drop rolls for a quest that is open and short of the
    thing, and for nobody else.

    LAVA_RES=.../lava/res python3 server/test_quest_mechanics.py
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

PARCEL = 3481           # Коробка вяленого мяса: cost 0, 5 kg, a heap
BUCKET = 3479           # Молоко, standing in for the bucket a giver hands over
PANAMA = 10059          # Панама: a thing to wear, the reward
HIDE = 218              # Собачья шкура, 900 g: the load past the limit
BADGE = 4296            # Нагрудный знак (Q): a cold arm, held; cost 0, no trade
POCKETS = 4287          # Пояс с карманами, +3 к силе: worn; cost 0, no trade
NOT_AN_ITEM = 1895      # «Пулеметчик»'s type, the catalogue's «Наган 1895 (G)»
SOLD = 193              # a cold arm a stall pays for and a barter takes
INJECTION = 3112        # Инъекция INTUX I (G): cost 0, no trade, used up by use
SKILL_MEDICINE = 2

# Seven quests on the market's NPCs, types well clear of the real table's.
PARCEL_Q, AFTER_Q, EITHER_Q, BUCKET_Q, CAPPED_Q, DAILY_Q, KIT_Q = (
    90001, 90002, 90003, 90004, 90005, 90006, 90007)
FIXTURES = [
    dict(type=PARCEL_Q, kind="del_obj", name="Посылка Шихабу",
         start="Отнеси посылку Шихабу.", notfinish="Посылка где?",
         finish="Спасибо за посылку.", give=[652], take=[653], obj=PARCEL,
         start_obj=[dict(obj=PARCEL, num=1)], rew_obj=[PANAMA],
         num_rew_obj=[1], rew_afro=100, rew_xp=dict(medicine=30),
         repeatable=0),
    dict(type=AFTER_Q, kind="del_obj", name="После посылки",
         start="Теперь поговори со мной.", finish="Молодец.", give=[652],
         take=[652], obj=0, need_quest=[PARCEL_Q], rew_afro=10, repeatable=0),
    dict(type=EITHER_Q, kind="del_obj", name="Одна из двух",
         start="Сделай одно из двух.", finish="Готово.", give=[2424],
         take=[2424], obj=0, need_any=[PARCEL_Q, BUCKET_Q], rew_afro=5,
         repeatable=0),
    dict(type=BUCKET_Q, kind="del_obj", name="Ведро и посылка",
         start="Возьми ведро и посылку.", notfinish="А посылка?",
         finish="Хорошо.", give=[2424], take=[652], obj=PARCEL,
         start_obj=[dict(obj=PARCEL, num=1), dict(obj=BUCKET, num=2)],
         rew_afro=1, repeatable=0),
    dict(type=CAPPED_Q, kind="del_obj", name="Только для новичков",
         start="Пока ты новичок.", finish="Ступай.", give=[2279], take=[2279],
         obj=0, max_level=0, rew_afro=1, repeatable=1),
    dict(type=DAILY_Q, kind="del_obj", name="Каждый день",
         start="Приходи каждый день.", finish="До завтра.", give=[653],
         take=[653], obj=0, rew_afro=1, repeatable=1),
    dict(type=KIT_Q, kind="del_obj", name="Снаряжение напрокат",
         start="Надень пояс и возьми знак.", finish="Верни всё.", give=[652],
         take=[652], obj=0, start_obj=[dict(obj=BADGE, num=1), dict(obj=POCKETS, num=1)],
         rew_afro=1, repeatable=0),
]
# What Вади-Хальфа's quests need (the engine of 2026-09-28): a fee, a prize
# drawn, experience into a specialisation that has to be open, things lent
# and taken back, a service outside the daily limit, a slot's own drop, and
# ways handed in like any quest. Their NPCs are the same four.
TRAINING_GUN, TRAINING_ROUNDS = 3728, 3727   # noob_Pistol (cost 120), noob_ammo (AMMO)
SOLD_ROUNDS = 6104                           # 9 mm СТ: the pistol stall sells it
FISH, PONCHO = 6045, 10060                   # the prizes: dried fish, a poncho
DOG = 82                                     # the dump's dogs (test_death)
SPEC_PISTOLS = 2
FEE_AFRO, FEE_GOLD = 5000, 50
FEE_Q, RANDOM_Q, SPEC_Q, LENT_Q, SERVICE_Q, DROP_Q = (90010, 90011, 90012, 90013,
                                                      90014, 90015)
WAY_KILL, WAY_PAY, WAY_CHILD = 90020, 90021, 90022
# A repeatable errand that is neither a service nor a way, for filling the
# day and the journal by hand: the market's «Голодные собаки» (5) did it
# until it left the real table with the other placeholders (2026-09-28).
DOGS_Q = 90008
TO_HALFA, BACK_TO_VALLEY, DEMIR_VALLEY, DEMIR_PIER = 43, 44, 5193, 30
VALLEY_VILLAGE, PIER, STATION = 186, 41, 37
FIXTURES += [
    dict(type=FEE_Q, kind="del_obj", name="За плату", start="Заплати и сдай.",
         notfinish="Денег мало.", finish="Спасибо.", give=[653], take=[653], obj=0,
         cost_afro=FEE_AFRO, cost_gold=FEE_GOLD, repeatable=0),
    dict(type=RANDOM_Q, kind="del_obj", name="Лотерея", start="Тяни билет.",
         finish="Приз!", give=[652], take=[652], obj=0, repeatable=1, service=True,
         rew_random=[dict(obj=FISH, num=2, w=1), dict(obj=PONCHO, num=1, w=3)]),
    dict(type=SPEC_Q, kind="del_obj", name="Экзамен", start="Для пистолетчиков.",
         finish="Сдано.", give=[2279], take=[2279], obj=0, repeatable=0,
         requires_spec="pistols", rew_spec_xp=dict(pistols=500)),
    dict(type=LENT_Q, kind="del_obj", name="Тир", start="Вот пистолет и патроны.",
         finish="Верни всё.", give=[652], take=[652], obj=0, repeatable=0, lent=True,
         start_obj=[dict(obj=TRAINING_GUN, num=1), dict(obj=TRAINING_ROUNDS, num=30)]),
    dict(type=SERVICE_Q, kind="del_obj", name="Услуга", start="Услуга.",
         finish="Готово.", give=[653], take=[653], obj=0, repeatable=1, service=True,
         rew_afro=1),
    dict(type=DROP_Q, kind="bring_l_obj", name="Знаки с собак", start="Принеси два.",
         finish="Молодец.", give=[2424], take=[2424], repeatable=0,
         objs=[dict(obj=BADGE, num=2, mobs=[DOG], drop=1.0)]),
    dict(type=WAY_KILL, kind="kill_mobs", name="Урок", start="Убей собаку, потом иди.",
         finish="Иди.", give=[653], take=[653], mobs_kill=[DOG], num_kill=[1],
         repeatable=1, rew_loc=1),
    dict(type=WAY_PAY, kind="del_obj", name="Платная дорога", start="Поедем за сотню.",
         finish="Держи панаму, поехали.", give=[2279], take=[2279], obj=0,
         rew_obj=[PANAMA], num_rew_obj=[1], cost_afro=100, repeatable=0, rew_loc=1),
    dict(type=WAY_CHILD, kind="del_obj", name="После дороги", start="Ты вернулся.",
         finish="Хорошо.", give=[2424], take=[2424], obj=0, need_quest=[WAY_PAY],
         rew_afro=1, repeatable=0),
    dict(type=DOGS_Q, kind="kill_mobs", name="Голодные собаки", start="Отгони трёх.",
         finish="Тише стало.", give=[652], take=[652], mobs_kill=[DOG], num_kill=[3],
         rew_afro=40, repeatable=1),
]
with open(os.path.join(os.path.dirname(HERE), "data", "quests.json"),
          encoding="utf-8") as fh:
    TABLE = json.load(fh)
# «В Хальфу!» (43) switched on here: the ride has to repeat, back and forth,
# now that a way is handed in like any quest. The real table has it on again
# since 2026-10-03 (on 2026-09-28, off the same evening); this suite holds
# the ride whatever the owner's switch says.
for _row in TABLE["quests"]:
    if _row["type"] == TO_HALFA:
        _row["give"], _row["take"] = [DEMIR_VALLEY], [DEMIR_VALLEY]
TABLE["quests"] = TABLE["quests"] + FIXTURES
QUESTS_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(QUESTS_FILE, "w", encoding="utf-8") as fh:
    json.dump(TABLE, fh, ensure_ascii=False)
os.environ["LAVA_QUESTS"] = QUESTS_FILE
# The ways of the market, beside the real table's: both lead to the station.
with open(os.path.join(os.path.dirname(HERE), "data", "passages.json"),
          encoding="utf-8") as fh:
    PASSAGES = json.load(fh)
PASSAGES.setdefault("quest", {})["102"] = [
    dict(quest=WAY_KILL, cells=[[20, 20]], target_loc_id=STATION),
    dict(quest=WAY_PAY, cells=[[21, 20]], target_loc_id=STATION)]
PASSAGES_FILE = os.path.join(tempfile.mkdtemp(), "passages.json")
with open(PASSAGES_FILE, "w", encoding="utf-8") as fh:
    json.dump(PASSAGES, fh, ensure_ascii=False)
os.environ["LAVA_PASSAGES"] = PASSAGES_FILE
for _knob in ("LAVA_WEAR_DROP", "LAVA_BAG_DROP"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import barter  # noqa: E402
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mail  # noqa: E402
import mobs  # noqa: E402
import names  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import random  # noqa: E402
import world  # noqa: E402
from inventory import BAG, BANK  # noqa: E402
from protocol import decode  # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- in process: the table as the server reads it ---------------------------
# A table or a module that does not have these yet fails here and the
# socket part still runs, so each mechanic is reported on its own.
try:
    check("the suite's quests are in the table the server will read",
          all(quests.get(t) is not None for t in (PARCEL_Q, AFTER_Q, EITHER_Q,
                                                   BUCKET_Q, CAPPED_Q, DAILY_Q,
                                                   KIT_Q)), True)
    check("and their strings in the preload",
          all(names.known(sid) for t in (PARCEL_Q, AFTER_Q, EITHER_Q, BUCKET_Q,
                                         CAPPED_Q, DAILY_Q, KIT_Q)
              for sid in quests.get(t).string_ids()), True)
    check("a delivery of a thing is decided by the bag, a message is not",
          [quests.get(t).counts_bag for t in (PARCEL_Q, AFTER_Q)], [True, False])
    check("the hand-in asks for the parcel alone, the buckets beside it or not",
          (quests.get(PARCEL_Q).wants(), quests.get(BUCKET_Q).wants()),
          ([(PARCEL, 1)], [(PARCEL, 1)]))
    check("and takes back the rest of what was handed over: the buckets, the kit",
          [quests.get(t).returns() for t in (PARCEL_Q, BUCKET_Q, KIT_Q)],
          [[], [(BUCKET, 2)], [(BADGE, 1), (POCKETS, 1)]])
    check("the daily limit counts the repeatable types only",
          (DAILY_Q in quests.repeatable_types(), PARCEL_Q in quests.repeatable_types(),
           1 in quests.repeatable_types()), (True, False, False))
    check("what a quest hands over stays on the body at a death; its neighbours"
          " in the bag do not", [combat.drops_on_death(t) for t in (PARCEL, BUCKET, HIDE)],
          [False, False, True])
    check("the experience names a skill by its key",
          quests.get(PARCEL_Q).rew_xp, [(SKILL_MEDICINE, 30)])
    for bad, why in ((dict(need_quest=[123456789]), "a prerequisite the table lacks"),
                     (dict(rew_xp=dict(magic=5)), "a skill that does not exist")):
        row = dict(FIXTURES[0], type=90099, **bad)
        probe = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(probe, "w", encoding="utf-8") as fh:
            json.dump({"quests": TABLE["quests"] + [row]}, fh, ensure_ascii=False)
        try:
            quests.load(probe)
            refused = False
        except ValueError:
            refused = True
        check("a table with %s does not load" % why, refused, True)
    ring = [dict(FIXTURES[1], type=90097, need_quest=[90098]),
            dict(FIXTURES[1], type=90098, need_quest=[90097])]
    probe = os.path.join(tempfile.mkdtemp(), "ring.json")
    with open(probe, "w", encoding="utf-8") as fh:
        json.dump({"quests": TABLE["quests"] + ring}, fh, ensure_ascii=False)
    try:
        quests.load(probe)
        refused = False
    except ValueError:
        refused = True
    check("nor one whose chain runs in a ring", refused, True)
    # What the server asks of the table before its first socket, once the
    # items are read (server.main): quests.check_items.
    check("every thing the table names is one the game has, and what it"
          " hands over is worth nothing away from its quest",
          quests.check_items(), None)
    for bad, why in ((dict(rew_obj=[NOT_AN_ITEM], num_rew_obj=[1]), "a reward that is no item"),
                     (dict(start_obj=[dict(obj=NOT_AN_ITEM, num=1)]),
                      "a handed thing that is no item"),
                     (dict(obj=NOT_AN_ITEM, start_obj=[]), "a delivery of no item"),
                     (dict(kind="bring_l_obj", objs=[dict(obj=NOT_AN_ITEM, num=1)]),
                      "a thing to bring that is no item"),
                     (dict(start_obj=[dict(obj=SOLD, num=1)]),
                      "a handed thing a stall pays for"),
                     (dict(start_obj=[dict(obj=INJECTION, num=1)]),
                      "a handed thing used up by its use")):
        row = dict(FIXTURES[0], type=90096, **bad)
        probe = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(probe, "w", encoding="utf-8") as fh:
            json.dump({"quests": TABLE["quests"] + [row]}, fh, ensure_ascii=False)
        table = quests.load(probe)
        try:
            quests.check_items(table)
            refused = False
        except ValueError:
            refused = True
        check("a table with %s does not start the server" % why, refused, True)

    # --- the engine of Вади-Хальфа ---------------------------------------------
    check("a fee is read in afro and in hundredths of an ounce",
          (quests.get(FEE_Q).has_fee, quests.get(FEE_Q).cost_afro, quests.get(FEE_Q).cost_gold,
           quests.get(FEE_Q).affordable(FEE_AFRO, FEE_GOLD - 1)), (True, FEE_AFRO, FEE_GOLD, False))
    rng = random.Random(1)
    drawn = [quests.get(RANDOM_Q).draw(rng) for _ in range(2000)]
    check("rew_random draws only from its list", sorted(set(drawn)), [(FISH, 2), (PONCHO, 1)])
    share = drawn.count((PONCHO, 1)) / float(len(drawn))
    check("  ..by weight: the poncho three times the fish (seeded)", 0.7 < share < 0.8, True)
    check("  ..and the same prize for the same seed",
          [quests.get(RANDOM_Q).draw(random.Random(7)) for _ in range(3)],
          [quests.get(RANDOM_Q).draw(random.Random(7))] * 3)
    check("rew_spec_xp names a specialisation by its key, and requires_spec too",
          (quests.get(SPEC_Q).rew_spec_xp, quests.get(SPEC_Q).requires_spec),
          ([(SPEC_PISTOLS, 500)], [SPEC_PISTOLS]))
    check("a service is outside the daily limit's types",
          (SERVICE_Q in quests.repeatable_types(), RANDOM_Q in quests.repeatable_types()),
          (False, False))
    check("what is lent is the quest's: the flag and no exchange on its frame",
          [(items.params_of(t)["quest"], items.params_of(t)["exchang"])
           for t in (TRAINING_GUN, TRAINING_ROUNDS)], [(1, 0), (1, 0)])
    check("  ..no barter, no post, no fall at a death, not on the ground",
          [(barter.tradable(t), mail.postable(t), combat.drops_on_death(t),
            quests.not_on_ground(t)) for t in (TRAINING_GUN, TRAINING_ROUNDS)],
          [(False, False, False, True)] * 2)
    _back = quests.START_OBJ_BACK_AT_HAND_IN
    try:
        quests.START_OBJ_BACK_AT_HAND_IN = False
        check("  ..and taken back at the hand-in whatever START_OBJ_BACK_AT_HAND_IN says",
              quests.get(LENT_Q).returns(), [(TRAINING_GUN, 1), (TRAINING_ROUNDS, 30)])
    finally:
        quests.START_OBJ_BACK_AT_HAND_IN = _back
    for bad, why in ((dict(rew_spec_xp=dict(magic=5)), "a specialisation that does not exist"),
                     (dict(requires_spec="flying"), "a required one that does not"),
                     (dict(cost_afro=-1), "a negative fee"),
                     (dict(rew_random=[dict(obj=FISH, num=1, w=0)]), "a prize of no weight"),
                     (dict(kind="bring_l_obj", objs=[dict(obj=BADGE, num=1, drop=0.5)]),
                      "a slot's drop with no mobs")):
        row = dict(FIXTURES[0], type=90094, **bad)
        probe = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(probe, "w", encoding="utf-8") as fh:
            json.dump({"quests": TABLE["quests"] + [row]}, fh, ensure_ascii=False)
        try:
            quests.load(probe)
            refused = False
        except ValueError:
            refused = True
        check("a table with %s does not load" % why, refused, True)
    row = dict(FIXTURES[0], type=90093, lent=True, start_obj=[dict(obj=SOLD_ROUNDS, num=20)])
    probe = os.path.join(tempfile.mkdtemp(), "bad.json")
    with open(probe, "w", encoding="utf-8") as fh:
        json.dump({"quests": TABLE["quests"] + [row]}, fh, ensure_ascii=False)
    try:
        quests.check_items(quests.load(probe))
        refused = False
    except ValueError:
        refused = True
    check("a table lending what a stall sells does not start the server", refused, True)
    check("a slot's drop is a quest row of loot of its creature, and of no other",
          ((BADGE, 1.0) in mobs.quest_table(DOG), BADGE in [t for t, _c in mobs.quest_table(83)]),
          (True, False))
    check("  ..rolled for a quest that wants the thing, never without",
          (mobs.quest_roll(DOG, {BADGE}, random.Random(1)), mobs.quest_roll(DOG, set(), random.Random(1))),
          ([(BADGE, 1)], []))
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())


# --- the server ----------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "quest_mechanics.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("courier", "secret")
_store.close()
CRED = accounts.credential("courier", "secret")

# /goto and /give set the scene (LAVA_CHEATS, as test_quests has them); the
# backpack falls whole at a death, so what stays is the rule and not the dice.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730", LAVA_AP_REGEN="25",
           LAVA_RESPAWN="120", LAVA_SEED="3", LAVA_BAG_DROP="100",
           LAVA_WEAR_DROP="100", LAVA_QUESTS=QUESTS_FILE)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

# A second server, on the table with one more row whose reward is no item:
# it must not start at all (server.main asks quests.check_items before its
# first socket), where it used to write the hand-in into the history, fail
# on the reward and send no ack.
BAD_Q = 90095
BAD_FILE = os.path.join(tempfile.mkdtemp(), "quests.json")
with open(BAD_FILE, "w", encoding="utf-8") as fh:
    json.dump({"quests": TABLE["quests"] + [
        dict(FIXTURES[5], type=BAD_Q, name="Награда, которой нет",
             rew_obj=[NOT_AN_ITEM], num_rew_obj=[1], repeatable=0)]},
        fh, ensure_ascii=False)
bad_srv = subprocess.Popen(
    [sys.executable, "server.py"], cwd=HERE,
    env=dict(env, LAVA_PORT=str(free_port()), LAVA_POLICY_PORT="0",
             LAVA_QUESTS=BAD_FILE, LAVA_DB=os.path.join(tempfile.mkdtemp(), "bad.db")),
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_bad_log = []
_bad_drain = threading.Thread(target=lambda: _bad_log.extend(bad_srv.stdout), daemon=True)
_bad_drain.start()


def bad_server_outcome(timeout=60):
    """(exit code, or None while it runs; its log) once it has either gone
    or opened its socket."""
    end = time.time() + timeout
    while time.time() < end and bad_srv.poll() is None \
            and "game server on" not in "".join(_bad_log):
        time.sleep(0.1)
    code = bad_srv.poll()
    if code is not None:
        _bad_drain.join(timeout=5)
    return code, "".join(_bad_log)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


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

    def _split(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.5):
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


def named(frames, name):
    return [p for n, p in frames if n == name]


def order(frames):
    return [n for n, _p in frames]


def chat(c, line):
    c.send("userMsg;entry=@%s@;group=0;" % line)


def npcs_of(frames):
    """type id -> entity id, off the userInfo_* frames of a population."""
    return {p["name"]: p["id"] for n, p in frames
            if n.startswith("userInfo_") and n != "userInfo_Player" and "name" in p}


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=2)


# The frames the last login was answered with: the constants among them.
LOGIN = []


def newcomer(c):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    LOGIN[:] = c.frames()
    c.send("newPers;res=1;sex=0;name=@Courier@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def come_back(c):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    return arrive(c)


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.2)


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    return named(c.until(lambda f: f[0] == "q_status"), "q_status")[0]["status"]


def take(c, npc, qtype, npc_type):
    """q_st for a type by its place in the NPC's give_quests."""
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    return c.frames(0.8)


def hand_in(c, npc, q_id, obj_idx=0):
    c.send("q_co;obj_idx=%d;mob=%d;q_id=%d;" % (obj_idx, npc, q_id))
    return c.frames(0.8)


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def first(frames, name):
    """The first frame of that name, or an empty one: a frame missing is a
    check that fails, not a suite that stops."""
    got = named(frames, name)
    return got[0] if got else {}


def q_id_of(frames):
    ids = [p["q_id"] for n, p in frames if n.startswith("q_di_")]
    return ids[0] if ids else 0


def store():
    return accounts.Store(DB)


def char_id():
    st = store()
    row = st.db.execute("SELECT id FROM characters WHERE name = 'Courier'").fetchone()
    st.close()
    return row["id"]


def owned(cid):
    """type id -> [(slot, count)] of everything the character owns."""
    st = store()
    out = {}
    for r in st.items_of(cid):
        out.setdefault(r["type_id"], []).append((r["slot"], r["count"]))
    st.close()
    return out


def money(cid):
    """(afro, gold) as the database has them."""
    st = store()
    got = tuple(st.money(cid))
    st.close()
    return got


def spend_the_day(cid, n=10):
    """n repeatable hand-ins today, written straight into the history: the
    suite's «Голодные собаки» (DOGS_Q)."""
    st = store()
    for _ in range(n):
        st.finish_quest(0, cid, DOGS_Q)
    st.close()


def oids(frames, status_):
    return [str(p["obj"]) for p in named(frames, "ss_obj_status") if p["status"] == status_]


DUMP = 100
DOG_HOME = 4551          # the dog nearest the entrance (test_death)
DUMP_LOC = world.location(DUMP)

try:
    code, out = bad_server_outcome()
    check("a server whose table rewards with no item does not start",
          (code not in (None, 0), "game server on" in out), (True, False))
    check("and says which quest and which type",
          ("quest %d" % BAD_Q in out, "rew_obj %d" % NOT_AN_ITEM in out), (True, True))

    c = Client(connect())
    got = newcomer(c)
    npc = npcs_of(got)
    TECHNOGEEK, AARON, SHIHAB, GRINDSTONE = npc[652], npc[2424], npc[653], npc[2279]
    POS = first(got, "lenter").get("pos")
    check("the client is told a journal the ways and services fit beside twenty-five"
          " quests, and the one gold rate",
          [(p["quest_log_capacity"], p["gold_to_afro_rate"]) for p in named(LOGIN, "constants")],
          [(35, progression.GOLD_TO_AFRO_RATE)])
    CID = char_id()

    # --- a chain, before anything is done -----------------------------------------
    check("a quest after the parcel is not offered before it",
          [status(c, t) for t in (PARCEL_Q, AFTER_Q, EITHER_Q, BUCKET_Q)], [1, 0, 0, 1])
    c.send("q_si;q_type=%d;" % AFTER_Q)
    si = named(c.until(lambda f: f[0].startswith("q_si_")), "q_si_del_obj")[0]
    check("its description names the one it needs", si["need_quest"], PARCEL_Q)
    c.send("q_st;mob=%d;q_idx=%d;" % (TECHNOGEEK, quests.given_by(652).index(AFTER_Q)))
    got = c.frames(0.6)
    check("and taking it anyway is refused, with one ack",
          (order(got), acks(got) != [0]), (["cmdAck"], True))

    # --- the day spent and the bag past the carry limit ---------------------------
    spend_the_day(CID)
    chat(c, "/give %d 60" % HIDE)          # 54 kg of hides: past the 50
    c.frames(0.6)
    st = store()
    load = sum(inventory.weight_of(r) for r in st.items_of(CID) if r["slot"] != BANK)
    st.close()
    check("the courier carries more than the limit", load > inventory.MAX_WEIGHT, True)

    # --- the parcel, handed over at the take ----------------------------------------
    got = take(c, TECHNOGEEK, PARCEL_Q, 652)
    check("taken: the parcel into the bag, the ack, then the journal",
          order(got), ["ss_obj_status", "ss_di_heap", "cmdAck", "q_di_del_obj"])
    parcel_oid = oids(got, 1)
    check("the parcel is a new thing in the bag", len(parcel_oid), 1)
    di = first(got, "q_di_del_obj")
    check("the delivery starts found and complete",
          (di.get("obj"), di.get("complete"), acks(got)), (1, 1, [0]))
    Q1 = di.get("q_id", 0)
    check("it is in the bag, one piece, past the limit or not",
          owned(CID).get(PARCEL), [(BAG, 1)])

    # --- handed in: the parcel goes, the reward comes, before the ack --------------
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (TECHNOGEEK, Q1))
    got = c.frames(0.6)
    check("the giver is not the taker", acks(got) != [0], True)
    got = hand_in(c, SHIHAB, Q1)
    check("handed in, with the day spent and the bag over the limit: the parcel"
          " out, the panama in, the experience, the purse, then the ack -- no"
          " q_sys, a one-off quest counts for nothing",
          order(got), ["ss_obj_status", "ss_obj_status", "ss_di_wear", "rp_info",
                       "userInfo_Player", "cmdAck"])
    check("the parcel is what left", oids(got, 0), parcel_oid)
    check("and acknowledged", acks(got), [0])
    rp = first(got, "rp_info")
    check("the experience went to medicine: 30 of 100",
          (rp.get("xp_skills_mask"), rp.get("xp_skills")), (1 << SKILL_MEDICINE, [30]))
    check("the purse took the hundred", first(got, "userInfo_Player").get("afro"), 1100)
    have = owned(CID)
    check("the panama is in the bag, the parcel is gone",
          (have.get(PANAMA), have.get(PARCEL)), ([(BAG, 1)], None))
    st = store()
    xp = [(r["value"], r["xp"]) for r in st.load_stats(CID)
          if r["kind"] == "skill" and r["idx"] == SKILL_MEDICINE]
    st.close()
    check("and the experience was saved", xp, [(0, 30)])

    # --- the chain opens; the one-off quest is gone --------------------------------
    check("the parcel handed in: it is not offered again, and the two after it are",
          [status(c, t) for t in (PARCEL_Q, AFTER_Q, EITHER_Q)], [0, 1, 1])
    # A repeatable quest with the day spent: refused, as the limit is.
    got = take(c, SHIHAB, DAILY_Q, 653)
    Q2 = q_id_of(got)
    got = hand_in(c, SHIHAB, Q2)
    check("a repeatable quest with the day spent is refused as the daily limit",
          (order(got), acks(got)), (["cmdAck"], [44]))

    # --- the parcel put away, then the quest dropped --------------------------------
    got = take(c, AARON, BUCKET_Q, 2424)
    Q3 = q_id_of(got)
    check("taken: the parcel and the two buckets' worth into the bag",
          (sorted(p["status"] for p in named(got, "ss_obj_status")),
           first(got, "q_di_del_obj").get("complete")), ([1, 1], 1))
    st = store()
    for r in st.items_of(CID):
        if r["type_id"] == PARCEL:
            st.update_item(r["uniq"], slot=BANK)
    st.close()
    c.send("q_di;q_id=%d;" % Q3)
    di = named(c.until(lambda f: f[0].startswith("q_di_")), "q_di_del_obj")[0]
    check("the parcel in the bank: the journal says not found, not complete",
          (di["obj"], di["complete"]), (0, 0))
    got = hand_in(c, TECHNOGEEK, Q3)
    check("and it cannot be handed in", (order(got), acks(got)), (["cmdAck"], [3]))
    c.send("q_ca;q_id=%d;" % Q3)
    got = c.frames(0.8)
    check("dropped: the buckets leave the bag before the ack",
          (order(got), acks(got)), (["ss_obj_status", "cmdAck"], [0]))
    have = owned(CID)
    check("and the parcel leaves the bank: nothing the giver handed is kept",
          (have.get(PARCEL), have.get(BUCKET)), (None, None))
    check("a one-off quest dropped is offered again", status(c, BUCKET_Q), 1)

    # --- a kit held and worn, then dropped; taken again and handed in ---------------
    def kit():
        st = store()
        rows = {r["type_id"]: r for r in st.items_of(CID) if r["type_id"] in (BADGE, POCKETS)}
        st.close()
        return rows

    def put_on(row, slot):
        c.send("ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(row), slot, BAG))
        return acks(c.frames(0.6))

    def upto_ack(frames):
        seq = order(frames)
        return seq[:seq.index("cmdAck") + 1] if "cmdAck" in seq else seq

    got = take(c, TECHNOGEEK, KIT_Q, 652)
    Q6 = q_id_of(got)
    kit_oids = sorted(oids(got, 1))
    check("the kit taken: the badge and the belt into the bag",
          (len(kit_oids), acks(got)), (2, [0]))
    rows = kit()
    check("the badge into a hand, the belt onto the body",
          (put_on(rows[BADGE], inventory.PRIMARY), put_on(rows[POCKETS], inventory.BELT)),
          ([0], [0]))
    check("so one is held and one is worn",
          (owned(CID).get(BADGE), owned(CID).get(POCKETS)),
          ([(inventory.PRIMARY, 1)], [(inventory.BELT, 1)]))
    c.send("q_ca;q_id=%d;" % Q6)
    got = c.frames(0.8)
    check("dropped: the badge leaves the hand and the belt the body, before the ack",
          (sorted(oids(got, 0)), upto_ack(got), acks(got)),
          (kit_oids, ["ss_obj_status", "ss_obj_status", "cmdAck"], [0]))
    check("and the card loses the belt's strength after it",
          "rp_info" in order(got)[len(upto_ack(got)):], True)
    check("nothing of the kit is kept, held, worn or anywhere",
          (owned(CID).get(BADGE), owned(CID).get(POCKETS)), (None, None))
    check("the kit dropped is offered again", status(c, KIT_Q), 1)
    got = take(c, TECHNOGEEK, KIT_Q, 652)
    Q7 = q_id_of(got)
    kit_oids = sorted(oids(got, 1))
    put_on(kit()[BADGE], inventory.PRIMARY)
    got = hand_in(c, TECHNOGEEK, Q7)
    check("handed in, the badge in a hand and the belt in the bag: both go back,"
          " then the purse and the ack",
          (sorted(oids(got, 0)), upto_ack(got), acks(got)),
          (kit_oids, ["ss_obj_status", "ss_obj_status", "userInfo_Player", "cmdAck"], [0]))
    check("nothing of the kit is kept after the hand-in either",
          (owned(CID).get(BADGE), owned(CID).get(POCKETS)), (None, None))

    # --- a service, with the day spent -----------------------------------------------
    got = take(c, SHIHAB, SERVICE_Q, 653)
    got = hand_in(c, SHIHAB, q_id_of(got))
    check("a service is handed in with the day spent, and counts nothing: no q_sys",
          (order(got), acks(got)), (["userInfo_Player", "cmdAck"], [0]))

    # --- a fee: part of completeness -------------------------------------------------
    got = take(c, SHIHAB, FEE_Q, 653)
    QF = q_id_of(got)
    check("a message with a fee the purse does not cover: taken, and not complete",
          (acks(got), first(got, "q_di_del_obj").get("complete")), ([0], 0))
    afro0 = money(CID)
    got = hand_in(c, SHIHAB, QF)
    check("  ..its hand-in refused, the journal told again, nothing taken",
          (order(got), acks(got), first(got, "q_di_del_obj").get("complete"),
           money(CID)), (["q_di_del_obj", "cmdAck"], [inventory.RES_NO_MONEY], 0, afro0))
    chat(c, "/money %d %d" % (FEE_AFRO, FEE_GOLD))
    got = c.frames(0.8)
    check("  ..the purse filled: the journal is told the quest is complete",
          [(p["q_id"], p["complete"]) for p in named(got, "q_di_del_obj")], [(QF, 1)])
    got = hand_in(c, SHIHAB, QF)
    purse = first(got, "userInfo_Player")
    check("  ..handed in: the fee charged, the ack",
          (upto_ack(got), acks(got), (purse.get("afro"), purse.get("gold"))),
          (["userInfo_Player", "cmdAck"], [0], afro0))

    # --- a prize drawn ----------------------------------------------------------------
    got = take(c, TECHNOGEEK, RANDOM_Q, 652)
    got = hand_in(c, TECHNOGEEK, q_id_of(got))
    prizes = [inventory.parse_oid(str(p["obj"]).lstrip("x"))[1]
              for p in named(got, "ss_obj_status") if p["status"] == 1]
    check("a prize drawn: one of the list into the bag before the ack, no q_sys",
          (len(set(prizes)), set(prizes) <= {FISH, PONCHO}, "q_sys" in order(got), acks(got)),
          (1, True, False, [0]))

    # --- a specialisation asked for -------------------------------------------------
    check("the exam is not offered while pistols are not learned", status(c, SPEC_Q), 0)
    got = take(c, GRINDSTONE, SPEC_Q, 2279)
    check("  ..nor taken", acks(got), [4])

    # --- lent things -------------------------------------------------------------------
    got = take(c, TECHNOGEEK, LENT_Q, 652)
    QL = q_id_of(got)
    lent_oids = {inventory.parse_oid(o.lstrip("x"))[1]: o.lstrip("x") for o in oids(got, 1)}
    check("lent: the training pistol and its rounds into the bag",
          (sorted(lent_oids), acks(got)), (sorted([TRAINING_GUN, TRAINING_ROUNDS]), [0]))
    c.send("ss_create;s_type=1;target=%d;" % npc[1200])
    opened = acks(c.frames())
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % lent_oids[TRAINING_GUN])
    got = c.frames()
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    check("  ..no stall buys the lent pistol", (opened, acks(got)), ([0], [3]))
    c.send("ss_create;s_type=0;target=%d;" % POS)
    opened = acks(c.frames())
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % lent_oids[TRAINING_GUN])
    got = c.frames()
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.3)
    check("  ..nor is it thrown on the ground", (opened, acks(got)), ([0], [3]))
    rows = {r["type_id"]: r for r in store().items_of(CID)
            if r["type_id"] in (TRAINING_GUN, TRAINING_ROUNDS)}
    c.send("ss_move;obj=x%s;to=%d;from=%d;" % (inventory.oid_of(rows[TRAINING_GUN]),
                                               inventory.PRIMARY, BAG))
    c.frames(0.6)
    st = store()
    st.update_item(rows[TRAINING_ROUNDS]["uniq"], slot=BANK)
    st.close()
    check("  ..the pistol in the hand, the rounds in the bank",
          (owned(CID).get(TRAINING_GUN), owned(CID).get(TRAINING_ROUNDS)),
          ([(inventory.PRIMARY, 1)], [(BANK, 30)]))
    c.send("q_ca;q_id=%d;" % QL)
    got = c.frames(0.8)
    check("  ..dropped: both taken back, from the hand and from the bank",
          (acks(got), owned(CID).get(TRAINING_GUN), owned(CID).get(TRAINING_ROUNDS)),
          ([0], None, None))
    # Its rounds are used up by their use: lent once a day (2026-09-28,
    # quests.lends_consumables) -- but these all came back unused, so the
    # loan is struck and the quest is taken again at once.
    got = take(c, TECHNOGEEK, LENT_Q, 652)
    QL = q_id_of(got)
    check("  ..all its rounds back unused: taken again the same day, lent again",
          (acks(got), owned(CID).get(TRAINING_ROUNDS)), ([0], [(BAG, 30)]))
    st = store()
    rounds = [r for r in st.items_of(CID) if r["type_id"] == TRAINING_ROUNDS][0]
    st.update_item(rounds["uniq"], count=20)
    st.close()
    c.send("q_ca;q_id=%d;" % QL)
    got = c.frames(0.8)
    check("  ..ten of them shot, then dropped: the rest taken back",
          (acks(got), owned(CID).get(TRAINING_GUN), owned(CID).get(TRAINING_ROUNDS)),
          ([0], None, None))
    got = take(c, TECHNOGEEK, LENT_Q, 652)
    check("  ..its rounds used today: not taken again the same day",
          (acks(got), owned(CID).get(TRAINING_ROUNDS)), ([4], None))
    st = store()
    st.db.execute("UPDATE char_lent SET lent_at = lent_at - 86400 WHERE char_id = ?", (CID,))
    st.db.commit()
    st.close()
    got = take(c, TECHNOGEEK, LENT_Q, 652)
    QL = q_id_of(got)
    got = hand_in(c, TECHNOGEEK, QL)
    check("  ..taken again and handed in: both taken back at the hand-in",
          (acks(got), owned(CID).get(TRAINING_GUN), owned(CID).get(TRAINING_ROUNDS)),
          ([0], None, None))

    # --- the journal: ways and services beside a full one ----------------------------
    st = store()
    stuffed = [st.take_quest(CID, DOGS_Q, {"kill_num": [0]}, False) for _ in range(25)]
    st.close()
    got = take(c, AARON, EITHER_Q, 2424)
    check("twenty-five ordinary quests in the journal: one more is refused", acks(got), [5])
    got = take(c, SHIHAB, SERVICE_Q, 653)
    check("  ..a service is still taken", acks(got), [0])
    QS = q_id_of(got)
    got = take(c, SHIHAB, WAY_KILL, 653)
    check("  ..and a way", acks(got), [0])
    QW = q_id_of(got)
    st = store()
    for q in stuffed:
        st.drop_quest(q)
    st.close()
    c.send("q_ca;q_id=%d;" % QS)
    c.frames(0.5)

    # --- ways: handed in like any quest ----------------------------------------------
    got = hand_in(c, SHIHAB, QW)
    check("a way that counts kills is not handed in before them, and moves nobody",
          (order(got), acks(got)), (["cmdAck"], [3]))
    c.send("q_ca;q_id=%d;" % QW)
    c.frames(0.5)
    check("the child of the paid way is not offered before it", status(c, WAY_CHILD), 0)
    got = take(c, GRINDSTONE, WAY_PAY, 2279)
    afro1 = money(CID)[0]
    got = hand_in(c, GRINDSTONE, q_id_of(got))
    got += c.until(lambda f: f[0] == "lcall", 3)
    check("a way with a fee and a reward: the panama, the purse, the ack, then the ride",
          (upto_ack(got), acks(got), first(got, "lcall").get("id")),
          (["ss_obj_status", "ss_di_wear", "userInfo_Player", "cmdAck"], [0], STATION))
    check("  ..the fee charged", money(CID)[0], afro1 - 100)
    st = store()
    done = [r["type"] for r in st.db.execute(
        "SELECT type FROM char_quests_done WHERE char_id = ?", (CID,)).fetchall()]
    st.close()
    check("  ..and the way written into the history", WAY_PAY in done, True)
    arrive(c)
    chat(c, "/goto 102")
    c.until(lambda f: f[0] == "lcall", 3)
    arrive(c)
    check("  ..which opens its child", status(c, WAY_CHILD), 1)

    # --- «В Хальфу!» and «Назад, в долину» still repeat --------------------------------
    def ride(npc_type, qtype, where):
        got = arrive(c) if where is None else where
        here = npcs_of(got)
        got = take(c, here[npc_type], qtype, npc_type)
        got = hand_in(c, here[npc_type], q_id_of(got))
        got += c.until(lambda f: f[0] == "lcall", 3)
        return acks(got), first(got, "lcall").get("id"), "q_sys" in order(got)

    chat(c, "/goto %d" % VALLEY_VILLAGE)
    c.until(lambda f: f[0] == "lcall", 3)
    rides = [ride(DEMIR_VALLEY, TO_HALFA, arrive(c)), ride(DEMIR_PIER, BACK_TO_VALLEY, arrive(c)),
             ride(DEMIR_VALLEY, TO_HALFA, arrive(c)), ride(DEMIR_PIER, BACK_TO_VALLEY, arrive(c))]
    check("the rides out of the valley and back repeat, none of them the day's",
          rides, [([0], PIER, False), ([0], VALLEY_VILLAGE, False)] * 2)
    arrive(c)
    chat(c, "/goto 102")
    c.until(lambda f: f[0] == "lcall", 3)
    got = arrive(c)
    npc = npcs_of(got)
    TECHNOGEEK, AARON, SHIHAB, GRINDSTONE = npc[652], npc[2424], npc[653], npc[2279]

    # --- the cap: offered while a beginner, carried past it no more -----------------
    check("the beginner's quest is offered at level 0", status(c, CAPPED_Q), 1)
    got = take(c, GRINDSTONE, CAPPED_Q, 2279)
    Q4 = q_id_of(got)
    # Taken again: the parcel for the death below, carried out of the room.
    got = take(c, AARON, BUCKET_Q, 2424)
    Q5 = q_id_of(got)
    leave(c)
    st = store()
    st.save_stats(CID, [("skill", progression.SHOOTING, 1, 0, progression.skill_xp_max(1)),
                        ("spec", SPEC_PISTOLS, 0, 0, progression.SPEC_XP_START)])
    st.save_character_state(CID, level=1, hp=1, sp=0)
    st.close()

    c = Client(connect())
    got = come_back(c)
    npc = npcs_of(got)
    GRINDSTONE, SHIHAB = npc[2279], npc[653]
    check("a fresh login on a spent day counts the repeatable hand-ins: none left",
          [p["daily_available"] for p in named(got, "q_sys")], [0])
    check("past the cap the quest is not the player's, carried or not",
          status(c, CAPPED_Q), 0)
    check("pistols learned: the exam is offered", status(c, SPEC_Q), 1)
    got = take(c, GRINDSTONE, SPEC_Q, 2279)
    got = hand_in(c, GRINDSTONE, q_id_of(got))
    rp = first(got, "rp_info")
    check("  ..and handed in: the experience into the specialisation alone, before the ack",
          (upto_ack(got), acks(got), rp.get("xp_specs_mask"), rp.get("xp_specs"),
           rp.get("xp_skills_mask", 0)),
          (["rp_info", "cmdAck"], [0], 1 << SPEC_PISTOLS, [500], 0))
    st = store()
    spec = [(r["value"], r["xp"]) for r in st.load_stats(CID)
            if r["kind"] == "spec" and r["idx"] == SPEC_PISTOLS]
    st.close()
    check("  ..and saved", spec, [(0, 500)])
    got = hand_in(c, GRINDSTONE, Q4)
    check("and it is not handed in", (order(got), acks(got)), (["cmdAck"], [4]))
    c.send("q_ca;q_id=%d;" % Q4)
    check("the journal can still drop it", acks(c.frames(0.6)), [0])
    got = take(c, GRINDSTONE, CAPPED_Q, 2279)
    check("nor is it given any more", (order(got), acks(got)), (["cmdAck"], [4]))

    # --- a fresh day: a repeatable hand-in brings the new count ---------------------
    st = store()
    st.db.execute("DELETE FROM char_quests_done WHERE char_id = ? AND type = ?", (CID, DOGS_Q))
    st.db.commit()
    st.close()
    got = hand_in(c, SHIHAB, Q2)
    check("with the day's hand-ins gone the repeatable one goes through, the new"
          " count before the ack", (order(got), acks(got),
                                    [p["daily_available"] for p in named(got, "q_sys")]),
          (["userInfo_Player", "q_sys", "cmdAck"], [0], [9]))

    # --- a death: the parcel stays, the rest of the bag rolls -----------------------
    have = owned(CID)
    check("the parcel and the buckets are in the bag before the death",
          (have.get(PARCEL), have.get(BUCKET)), ([(BAG, 1)], [(BAG, 2)]))
    chat(c, "/goto %d" % DUMP)
    c.until(lambda f: f[0] == "lcall", 3)
    got = arrive(c)
    pos = first(got, "lenter")["pos"]
    dog_aggro = mobs.stats(82).aggro
    path = [pos]
    while mobs.hex_distance(path[-1], DOG_HOME, DUMP_LOC.width) > dog_aggro - 0.5:
        path.append(min(
            (n for n in progression.hex_neighbours(path[-1], DUMP_LOC.width,
                                                   DUMP_LOC.height)
             if n not in DUMP_LOC.obstacles and n not in path),
            key=lambda n: mobs.hex_distance(n, DOG_HOME, DUMP_LOC.width)))
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    got = c.until(lambda f: f[0] == "lch" and f[1].get("dead") == 0, 40)
    got += c.frames(0.8)
    check("bitten to death", [p for n, p in got if n == "lch" and "dead" in p], [{"dead": 0}])
    have = owned(CID)
    check("the parcel and the buckets are still the courier's, in the bag",
          (have.get(PARCEL), have.get(BUCKET)), ([(BAG, 1)], [(BAG, 2)]))
    check("while the hides fell, a third of the stack (the bag rolled)",
          have.get(HIDE), [(BAG, 40)])
    # The dead are let nothing but resurrect (combat.blocks), so the journal
    # is asked on the other side of it.
    c.send("resurrect;res_type=0;")
    c.until(lambda f: f[0] == "lcall", 3)
    arrive(c)
    c.send("q_di;q_id=%d;" % Q5)
    di = named(c.until(lambda f: f[0].startswith("q_di_")), "q_di_del_obj")[0]
    check("risen, the delivery is still found and complete",
          (di["obj"], di["complete"]), (1, 1))
    leave(c)

    # --- a slot's own drop, asked of the journal ----------------------------------------
    st = store()
    st.take_quest(CID, DROP_Q, {"obj_num": [0]}, False)
    check("a slot's drop is wanted while its quest is open and short of the thing, not"
          " once the bag holds enough, and never by a character without the quest",
          (BADGE in quests.wanted_things(st, CID, {}),
           BADGE in quests.wanted_things(st, CID, {BADGE: 2}),
           BADGE in quests.wanted_things(st, CID + 1000, {})), (True, False, False))
    st.close()
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    if bad_srv.poll() is None:
        bad_srv.terminate()
        bad_srv.wait(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-50:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("quest mechanics OK")
