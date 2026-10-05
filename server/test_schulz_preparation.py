"""Schulz's introduction waits for base Shooting 3 and opens the Mwamba quest.

The original's texts.xml 59944-59946 names level 3, but no skill or reward.
The owner approved Shooting, a one-off talk with no reward and no daily
limit, on 2026-10-05. Existing boss quests must remain playable. Real
Sessions record the frames sent to the client; test_valley_market covers
the same introduction and the subsequent boss fight on a socket.

    LAVA_RES=.../client/res python server/test_schulz_preparation.py
"""
import asyncio
import io
import json
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.update(LAVA_DB=os.path.join(tempfile.mkdtemp(), "schulz.db"),
                  LAVA_CHEATS="1", LAVA_START="181")
os.environ.pop("LAVA_QUESTS", None)
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import names  # noqa: E402
import orig_texts  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import server  # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, fails  # noqa: E402

PREP, BOSS, SCHULZ = 68, 58, 5221


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, command):
    sess.writer.frames.clear()
    sess.handle(*decode(command))
    return list(sess.writer.frames)


def acks(frames):
    return [p["res"] for n, p in frames if n == "cmdAck"]


def complete(frames):
    return [p["complete"] for n, p in frames if n == "q_di_del_obj"]


def status(sess, quest):
    return run(sess, "q_status;q_type=%d;" % quest)[0][1]["status"]


def visit(sess):
    run(sess, "userMsg;group=0;entry=@/goto 186@;")
    frames = run(sess, "lenter;accept=1;")
    return next(p["id"] for n, p in frames
                if n.startswith("userInfo_") and p.get("name") == SCHULZ)


def take(sess, npc, quest):
    frames = run(sess, "q_st;mob=%d;q_idx=%d;" %
                 (npc, quests.given_by(SCHULZ).index(quest)))
    row = next((p for n, p in frames if n.startswith("q_di_")), {})
    return frames, row.get("q_id", 0)


def hand_in(sess, npc, qid):
    return run(sess, "q_co;mob=%d;q_id=%d;obj_idx=0;" % (npc, qid))


def login(account, create=True):
    if create:
        server.STORE.register(account, "secret")
    sess = server.Session(Writer(), account)
    run(sess, "login;hash=@%s@;" % accounts.credential(account, "secret"))
    if create:
        run(sess, "newPers;res=1;sex=0;name=@%s@;" % account)
        run(sess, "actPlayer;")
    else:
        run(sess, "selPers;num=0;")
    run(sess, "lenter;accept=1;")
    return sess


# --- the table and original text, in process ----------------------------------
q = quests.get(PREP)
check("the preparation is a one-off talk with no prize or daily charge",
      (q.kind, q.obj, q.give, q.take, q.pays, q.repeatable, server.Session.counts_daily(q)),
      (quests.DEL_OBJ, 0, [SCHULZ], [SCHULZ], False, 0, False))
check("the original's three surviving lines are retained after the overlay",
      (q.name, q.texts[quests.START].startswith(orig_texts.quests()[PREP]["start"]),
       q.texts[quests.NOTFINISH]),
      ("Как стать круче", True, "Поговори со мной еще раз, когда будешь 3-го уровня"))
check("the served objective explicitly names Shooting 3, and all texts are preloaded",
      ("Стрельба: 3-й уровень" in q.texts[quests.START],
       all(names.known(q.string_id(k)) for k in range(4))), (True, True))

row = dict(type=90001, kind="del_obj", name="Skill goal", give=[SCHULZ], take=[SCHULZ])
for extra in (dict(complete_skills={"unknown": 3}),
              dict(complete_skills={"shooting": 0}),
              dict(complete_skills={"shooting": 21}),
              dict(complete_skills={"shooting": 3}, kind="kill_mobs"),
              dict(complete_skills={"shooting": 3}, obj=3480)):
    try:
        quests.Quest(dict(row, **extra))
        rejected = False
    except ValueError:
        rejected = True
    check("invalid skill goal cannot start the server: %s" % extra, rejected, True)


async def main():
    sess = login("Newcomer")
    try:
        npc = visit(sess)
        check("a newcomer sees the introduction, not the boss quest",
              (status(sess, PREP), status(sess, BOSS)), (1, 0))
        got, qid = take(sess, npc, BOSS)
        check("a forged request cannot bypass the introduction", acks(got),
              [server.RES_NOT_AVAILABLE])
        got, qid = take(sess, npc, PREP)
        check("the talk enters the journal incomplete, with exactly one ack",
              ([n for n, _ in got], acks(got), complete(got)),
              (["cmdAck", "q_di_del_obj"], [0], [0]))
        got = hand_in(sess, npc, qid)
        check("a premature hand-in keeps the quest and refreshes its incomplete flag",
              (acks(got), complete(got), bool(server.STORE.quest(qid))),
              ([server.RES_NOT_READY], [0], True))
        got = run(sess, "userMsg;group=0;entry=@/skill 2 20@;")
        check("Medicine 20 does not satisfy the Shooting goal", complete(got), [])
        run(sess, "userMsg;group=0;entry=@/skill 1 2@;")
        sess.character().bonus_skills[progression.SHOOTING] = 10
        check("equipment skill bonuses do not satisfy the goal",
              complete(run(sess, "q_di;q_id=%d;" % qid)), [0])
        sess.character().bonus_skills[progression.SHOOTING] = 0
        # Normal XP, rather than the level cheat, must also update a carried quest.
        skill = sess.character().skill[progression.SHOOTING]
        skill[1] = skill[2] - 1
        sess.writer.frames.clear()
        sess.pay_xp([(progression.SHOOTING, 1)])
        check("earning Shooting 3 pushes completion without asking q_di",
              (sess.character().skill[progression.SHOOTING][0],
               complete(sess.writer.frames)), (3, [1]))
        check("reaching level 3 alone does not open the boss quest before the talk is handed in",
              status(sess, BOSS), 0)
        sess.writer.frames.clear()
        sess.push_stats()
        check("unchanged skills do not repeat journal notifications",
              complete(sess.writer.frames), [])
        run(sess, "logout;")
        sess = login("Newcomer", create=False)
        npc = visit(sess)
        check("relogin recomputes completion from saved base skills",
              complete(run(sess, "q_di;q_id=%d;" % qid)), [1])
        # A stale client's completion is never trusted, even without a stat push.
        sess.character().set_skill(progression.SHOOTING, 2)
        got = hand_in(sess, npc, qid)
        check("lowered skills invalidate a stale completed journal at hand-in",
              (acks(got), complete(got)), ([server.RES_NOT_READY], [0]))
        got = run(sess, "userMsg;group=0;entry=@/skill 1 3@;")
        check("restoring Shooting 3 makes the same quest complete", complete(got), [1])
        got = run(sess, "userMsg;group=0;entry=@/skill 1 2@;")
        check("lowering Shooting pushes incompleteness without a journal request",
              complete(got), [0])
        run(sess, "userMsg;group=0;entry=@/skill 1 3@;")
        before = (sess.inv.money(), server.STORE.items_of(sess.char_id),
                  json.dumps(sess.character().skill))
        daily_max = server.DAILY_MAX
        server.DAILY_MAX = 0
        try:
            got = hand_in(sess, npc, qid)
            check("even with the daily limit exhausted the talk pays nothing and uses none",
                  ([n for n, _ in got], acks(got), sess.daily_available(),
                   (sess.inv.money(), server.STORE.items_of(sess.char_id),
                    json.dumps(sess.character().skill)) == before),
                  (["cmdAck"], [0], 0, True))
        finally:
            server.DAILY_MAX = daily_max
        check("only a completed hand-in opens the boss quest; the talk is gone for good",
              (status(sess, PREP), status(sess, BOSS), bool(server.STORE.quest(qid)),
               qid in sess.skill_shown), (0, 1, False, False))
    finally:
        run(sess, "logout;")

    # --- a dropped talk and existing boss quests -------------------------------
    sess = login("Dropper")
    try:
        npc = visit(sess)
        _, qid = take(sess, npc, PREP)
        got = run(sess, "q_ca;q_id=%d;" % qid)
        check("dropping clears the cached goal and does not open the boss quest",
              (acks(got), qid in sess.skill_shown, status(sess, PREP), status(sess, BOSS)),
              ([0], False, 1, 0))
        run(sess, "userMsg;group=0;entry=@/skill 1 3@;")
        got, qid = take(sess, npc, PREP)
        check("someone already trained to Shooting 3 takes the talk complete at once",
              (acks(got), complete(got)), ([0], [1]))
    finally:
        run(sess, "logout;")

    sess = login("Veteran")
    try:
        npc = visit(sess)
        # A row from before the introduction was added: no type 68 in its history.
        qid = server.STORE.take_quest(sess.char_id, BOSS, {"kill_num": [0]}, False)
        check("a carried legacy boss quest hides the introduction and remains available",
              (status(sess, PREP), status(sess, BOSS)), (0, 1))
        server.STORE.update_quest(qid, {"kill_num": [1]}, True)
        got = hand_in(sess, npc, qid)
        check("a legacy boss quest can still be handed in without the new prerequisite",
              (acks(got), bool(server.STORE.quest_done(sess.char_id, BOSS)),
               bool(server.STORE.quest_done(sess.char_id, PREP))), ([0], True, False))
        check("having finished the boss quest, a veteran never gets its introduction",
              (status(sess, PREP), status(sess, BOSS)), (0, 0))
    finally:
        run(sess, "logout;")


errors = io.StringIO()
handler = logging.StreamHandler(errors)
handler.setLevel(logging.ERROR)
logger = logging.getLogger("lava")
logger.handlers = [handler]
logger.propagate = False
try:
    asyncio.run(main())
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    server.STORE.close()
    if errors.getvalue():
        fails.append("server logged an error:\n" + errors.getvalue())

if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("Schulz preparation OK")
