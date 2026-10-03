"""Home registration belongs to healers and explicitly listed residents.

The owner's rule of 2026-10-03: ordinary Commoners, things and animals do
not register homes. Said is listed by the wiki's service; the caravan's
healer keeps registration, its ratcatcher and grindstone lose it.
Real Sessions and rooms run in process, recording the same frames the
client reads (NPC.userInfo, Attendance.SET_HOME). The command must agree
with the advertised service, refuse with exactly one ack, preserve an
existing home on refusal, and still forbid registration in enclosed rooms.

    LAVA_RES=.../client/res python server/test_home.py
"""
import asyncio
import io
import json
import logging
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(tempfile.mkdtemp(), "home.db")
os.environ.update(LAVA_DB=DB, LAVA_CHEATS="1", LAVA_START="181")
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import npcs  # noqa: E402
import rooms  # noqa: E402
import world  # noqa: E402
import server  # noqa: E402
from protocol import decode  # noqa: E402
from testkit import check, fails  # noqa: E402


class Writer:
    def __init__(self):
        self.frames = []

    def write(self, data):
        self.frames.append(decode(data[:-1].decode("utf-8")))

    def close(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


def run(sess, text):
    sess.writer.frames.clear()
    sess.handle(*decode(text))
    return list(sess.writer.frames)


def visit(sess, loc):
    run(sess, "userMsg;entry=@/goto %d@;group=0;" % loc)
    frames = run(sess, "lenter;accept=1;")
    return {p["name"]: p for n, p in frames
            if n.startswith("userInfo_") and n != "userInfo_Player"}


def home(sess):
    row = server.STORE.character(sess.char_id)
    return tuple(row[k] for k in ("home_loc", "home_gx", "home_gy"))


def register(sess, info):
    return run(sess, "on_conv;mob=%d;op=0;" % info["id"])


# --- the rule, in process ----------------------------------------------------
QUARTER_CELL = world.cell_of(36)  # The shipped map, not the wiki's older coordinates.
check("the explicit registrar is Said; every exception has its source",
      (sorted(npcs.HOME), all(row.get("why", "").strip()
       for key, row in json.load(open(npcs.PATH, encoding="utf-8"))["home"].items()
       if not key.startswith("_"))), ([44], True))
check("Said and the caravan's healer register homes",
      [server.Session.offers_home(t) for t in (44, 5202)], [True, True])
check("corn, palm, defender, cow, ratcatcher, grindstone and technogeek do not",
      [server.Session.offers_home(t) for t in (1682, 2021, 40, 5195, 5194, 5192, 652)],
      [False] * 7)
check("banks, trophy traders and unknown types do not register homes",
      [server.Session.offers_home(t) for t in (2424, 729, 5193, 939, 999999)], [False] * 5)


async def main():
    server.STORE.register("resident", "secret")
    sess = server.Session(Writer(), "home-test")
    try:
        run(sess, "login;hash=@%s@;" % accounts.credential("resident", "secret"))
        run(sess, "newPers;res=1;sex=0;name=@Resident@;")
        run(sess, "actPlayer;")
        run(sess, "lenter;accept=1;")
        # A previously saved home remains valid, even with no registrar left.
        server.STORE.set_home(sess.char_id, 153, 6273, 1829)
        legacy = home(sess)

        # --- the caravan's service and refusals ------------------------------
        people = visit(sess, 186)
        for t in (5194, 5192, 5193):
            before = home(sess)
            check("caravan type %d advertises no registration and refuses one command" % t,
                  (people[t].get("can_set_home", 0), register(sess, people[t]), home(sess)),
                  (0, [("cmdAck", {"res": server.RES_WRONG_NPC})], before))
        run(sess, "userMsg;entry=@/home@;group=0;")
        check("a refused registration leaves the legacy home usable",
              (sess.loc.id, home(sess)), (153, legacy))
        run(sess, "lenter;accept=1;")
        people = visit(sess, 186)
        check("the caravan's healer advertises and accepts registration",
              (people[5202]["can_set_home"], register(sess, people[5202]), home(sess)),
              (1, [("cmdAck", {"res": 0})], (186, 6271, 1829)))

        # --- explicitly listed commoner and bank -----------------------------
        people = visit(sess, 36)
        check("Said advertises registration and saves his location and map cell",
              (people[44]["can_set_home"], register(sess, people[44]), home(sess)),
              (1, [("cmdAck", {"res": 0})], (36,) + QUARTER_CELL))
        saved = home(sess)
        people = visit(sess, 102)
        for t in (652, 2424):
            check("market type %d refuses without changing the registered home" % t,
                  (people[t]["can_set_home"], register(sess, people[t]), home(sess)),
                  (0, [("cmdAck", {"res": server.RES_WRONG_NPC})], saved))

        npcs.HOME[2424] = True
        try:
            check("even an explicit mark cannot add registration to a bank",
                  (server.Session.offers_home(2424), register(sess, people[2424]), home(sess)),
                  (False, [("cmdAck", {"res": server.RES_WRONG_NPC})], saved))
        finally:
            npcs.HOME.pop(2424)

        # Actual unlisted craftsmen keep their figures and quests, but
        # must no longer open a support tab just because they are Commoners.
        people = visit(sess, 451)
        commoners = [p for t, p in people.items() if server.MOB_TYPES[t][0] == world.COMMONER]
        check("the craftsmen scene has residents", bool(commoners), True)
        check("the craftsmen advertise no home registration",
              [p["name"] for p in commoners if p.get("can_set_home")], [])
        if commoners:
            check("a craftsman refuses the command and keeps Said's saved home",
                  (register(sess, commoners[0]), home(sess)),
                  ([("cmdAck", {"res": server.RES_WRONG_NPC})], saved))

        # --- a healer's exception and the enclosed-location restriction ------
        people = visit(sess, 37)
        npcs.HOME[100] = False
        try:
            frames = run(sess, "getInfo;type=1;id=%d;lvl=0;" % people[100]["id"])
            check("an explicit false disables both a healer's menu and registration",
                  ([p["can_set_home"] for n, p in frames if n == "userInfo_Medic"],
                   register(sess, people[100]), home(sess)),
                  ([0], [("cmdAck", {"res": server.RES_WRONG_NPC})], saved))
        finally:
            npcs.HOME.pop(100)
        # Put a healer in the enclosed quarry for this scene only. Even an
        # otherwise eligible NPC must not create a way past its quest gate.
        visit(sess, 626)
        eid = max(sess.room.npcs, default=0) + 1
        sess.room.npcs[eid] = rooms.NPC(sess.pos, 100, world.HEALER)
        try:
            frames = run(sess, "getInfo;type=1;id=%d;lvl=0;" % eid)
            check("a healer in an enclosed location cannot register a home",
                  ([p["can_set_home"] for n, p in frames if n == "userInfo_Medic"],
                   register(sess, {"id": eid}), home(sess)),
                  ([0], [("cmdAck", {"res": server.RES_WRONG_NPC})], saved))
        finally:
            del sess.room.npcs[eid]
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
print("home registration OK")
