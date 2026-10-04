"""Where a new character wakes up, and which of the valley's two tutorials is
his (the owner's «в одном месте надо инструменты получить, в другом корову
подоить», «видимо там случайный старт должен быть» -- «делай», 2026-09-26).

  start     a character made now starts at random in one of
            server.START_PLACES, half and half: «Нубийское поселение» (181,
            6268x1819), where Думисани gives the north «Добро пожаловать»
            (11), or «Западный поселок» (183, 6262x1825), where Джеррах gives
            the west one (15). LAVA_START=181|183 forces one of them.
  home      the start is the character's home until a «Прописка» moves it:
            /home, a resurrection and a login after a death all end there,
            and on its own map cell. A character made before keeps what it
            had: no home, and the old start, 181.
  branches  the two tutorials exclude each other (the rows' "excludes"):
            whoever has taken or handed in a quest of one -- the cow and the
            box included -- is not offered the other's, and q_st refuses it
            with one ack. A quest dropped commits to nothing. A character
            that walked into both before the rule keeps the one it handed a
            quest of in first and walks the rest of it, the other's rest
            shut; what its journal already holds stays walkable, and the cow
            still milks for a «Друзья» taken then.

Three servers on the real tables: LAVA_START=183, LAVA_START=181, and none
with a fixed LAVA_SEED, where both starts come up over a dozen creations.
The whole of both tutorials is walked in test_valley_quests.

    LAVA_RES=.../lava/res python3 server/test_start.py
"""
import collections
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
for _knob in ("LAVA_QUESTS", "LAVA_PLACEMENTS", "LAVA_PASSAGES", "LAVA_START", "LAVA_GX",
              "LAVA_GY", "LAVA_LOC", "LAVA_SEED"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import quests  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


VILLAGE, PASTURE, WEST, BURIALS, MARKET = 181, 182, 183, 184, 185
VILLAGE_CELL, WEST_CELL = (6268, 1819), (6262, 1825)
NORTH = [11, 12, 13, 14]        # Думисани, Зула's milk, the cow, Салех's parcel
WESTERN = [15, 16, 17, 18]      # Джеррах, Ибрахим's tools, the box, his parcel
WELCOME_N, FRIENDS_N, COW_Q, FINANCE_N = NORTH
WELCOME_W, FRIENDS_W, BOX_Q, FINANCE_W = WESTERN
DUMISANI, ZULA, COW, JERRAH, IBRAHIM, BOX = 5207, 5200, 5195, 5206, 5210, 1135
SALEH = 5190
SHORTS = 10062
RES_NOT_AVAILABLE = 4
SEED = "6"
CREATIONS = 12

# --- in process: the table and the places ---------------------------------------------
try:
    check("each branch excludes the whole of the other, both ways",
          ({t: sorted(quests.get(t).excludes) for t in NORTH},
           {t: sorted(quests.get(t).excludes) for t in WESTERN}),
          ({t: WESTERN for t in NORTH}, {t: NORTH for t in WESTERN}))
    check("  ..and each knows its own: the rows that exclude the same",
          ({t: quests.get(t).branch for t in NORTH}, {t: quests.get(t).branch for t in WESTERN}),
          ({t: NORTH for t in NORTH}, {t: WESTERN for t in WESTERN}))
    # A choice of its own later on (Вади-Хальфа's «Быть или не быть», 212/213)
    # shuts its own other row, never the tutorial's.
    check("  ..and no quest after them does: the market's chain is everybody's",
          [t for t, q in quests.QUESTS.items()
           if set(q.excludes) & set(NORTH + WESTERN) and t not in NORTH + WESTERN], [])
    table = os.path.join(os.path.dirname(HERE), "data", "quests.json")
    with open(table, encoding="utf-8") as fh:
        rows = json.load(fh)["quests"]
    by_type = {r["type"]: r for r in rows}
    for bad, why in ((dict(excludes=[123456789]), "an exclusion the table lacks"),
                     (dict(excludes=[99]), "a quest that excludes itself"),
                     (dict(need_quest=[FRIENDS_N], excludes=[WELCOME_N]),
                      "a quest that excludes what it needs, two links back")):
        row = dict(by_type[WELCOME_N], type=99, give=[DUMISANI], take=[DUMISANI], **bad)
        probe = os.path.join(tempfile.mkdtemp(), "bad.json")
        with open(probe, "w", encoding="utf-8") as fh:
            json.dump({"quests": rows + [row]}, fh, ensure_ascii=False)
        try:
            quests.load(probe)
            refused = False
        except ValueError:
            refused = True
        check("a table with %s does not load" % why, refused, True)
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())

try:
    # accounts read LAVA_DB at their own import, above: the path is set on
    # the module too, or the server's Store would open data/lava.db.
    os.environ["LAVA_DB"] = accounts.DB_PATH = os.path.join(tempfile.mkdtemp(), "inproc.db")
    import server  # noqa: E402  (after LAVA_DB: it opens a Store at import)
    check("two places to start in, the two settlements the tutorial begins in, even odds",
          [(world.location_at(x, y), (x, y), w) for x, y, w in server.START_PLACES],
          [(VILLAGE, VILLAGE_CELL, 1), (WEST, WEST_CELL, 1)])
    check("  ..both drawn from when no knob is set",
          [(loc, (gx, gy)) for loc, gx, gy, _w in server.STARTS],
          [(VILLAGE, VILLAGE_CELL), (WEST, WEST_CELL)])
    check("  ..and the old start, 181, is still where a character with no home and"
          " no saved place goes", (server.START_LOC, server.GLOBAL_X, server.GLOBAL_Y),
          (VILLAGE,) + VILLAGE_CELL)
except Exception:
    import traceback
    fails.append("the server in process broke:\n" + traceback.format_exc())


# --- the servers --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe_:
        probe_.bind(("127.0.0.1", 0))
        return probe_.getsockname()[1]


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


def inhabitants(frames):
    """type id -> [entity id] of the userInfo_* frames of an arrival."""
    out = {}
    for n, p in frames:
        if n.startswith("userInfo") and n != "userInfo_Player" and "name" in p:
            out.setdefault(p["name"], []).append(p["id"])
    return out


class Server:
    """One server on its own port and its own database, with these knobs."""

    def __init__(self, tag, logins, seed_db=None, **knobs):
        self.port = free_port()
        self.db = os.path.join(tempfile.mkdtemp(), "start_%s.db" % tag)
        st = accounts.Store(self.db)
        self.cred = {}
        for login in logins:
            st.register(login, "secret")
            self.cred[login] = accounts.credential(login, "secret")
        if seed_db:
            seed_db(st)
        st.close()
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1",
                   LAVA_DB=self.db, LAVA_CHEATS="1", LAVA_POLICY_PORT="0", **knobs)
        self.log = os.path.join(os.path.dirname(self.db), "server.log")
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                                     stdout=open(self.log, "w"),
                                     stderr=subprocess.STDOUT, text=True)

    def connect(self, timeout=None):
        return testkit.connect(self.port, self.proc, self.log, timeout)

    def login(self, login):
        c = Client(self.connect())
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % self.cred[login])
        c.frames()
        return c

    def row(self, name):
        st = accounts.Store(self.db)
        try:
            r = st.db.execute("SELECT * FROM characters WHERE name = ?", (name,)).fetchone()
            return dict(r) if r is not None else None
        finally:
            st.close()

    def write(self, sql, args):
        st = accounts.Store(self.db)
        try:
            st.db.execute(sql, args)
            st.db.commit()
        finally:
            st.close()

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=5)
        with open(self.log, encoding="utf-8", errors="replace") as fh:
            out = fh.read()
        if "Traceback" in out:
            fails.append("server logged a traceback:\n" + out[-2500:])
        elif fails:
            story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
            fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))


def arrive(c):
    c.send("lenter;accept=1;")
    return c.frames(wait=1.5)


def create(c, name):
    """newPers and the intro's actPlayer: (the lcall, the arrival)."""
    c.send("newPers;res=1;sex=0;name=@%s@;" % name)
    # Until the ack, not a fixed half second: a creation is a dozen writes,
    # and on a slow disk it takes longer.
    got = c.until(lambda f: f[0] == "cmdAck", wait=5.0)
    if acks(got) != [0]:
        return {}, []
    c.send("actPlayer;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    return call, (arrive(c) if call else [])


def goto(c, loc_id):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc_id)
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    return call, (arrive(c) if call else [])


def home(c):
    """/home: the lcall it ends in, and the arrival."""
    c.send("userMsg;entry=@/home@;group=0;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    return call, (arrive(c) if call else [])


def map_cell(c):
    """Out onto the map and straight back in: the cell gmap put us on, and
    the location the way back opened."""
    c.send("chWorld;")
    gmap = first(c.until(lambda f: f[0] == "gmap"), "gmap")
    c.frames(0.3)
    c.send("chWorld;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    if call:
        arrive(c)
    return (gmap.get("x"), gmap.get("y")), call.get("id")


def status(c, qtype):
    c.send("q_status;q_type=%d;" % qtype)
    got = named(c.until(lambda f: f[0] == "q_status"), "q_status")
    return got[0]["status"] if got else None


def statuses(c, types):
    return {t: status(c, t) for t in types}


def take(c, here, npc_type, qtype):
    """q_st of a type from the first NPC of this type here: (acks, q_id)."""
    npc = here.get(npc_type, [0])[0]
    c.send("q_st;mob=%d;q_idx=%d;" % (npc, quests.given_by(npc_type).index(qtype)))
    got = c.frames(0.8)
    ids = [p["q_id"] for n, p in got if n.startswith("q_di_")]
    return acks(got), (ids[0] if ids else 0)


def hand_in(c, here, npc_type, q_id):
    npc = here.get(npc_type, [0])[0]
    c.send("q_co;obj_idx=0;mob=%d;q_id=%d;" % (npc, q_id))
    return acks(c.frames(0.9))


def carried(c, qtype):
    """The q_id of this type in the journal (q_list), or 0."""
    c.send("q_list;")
    ql = first(c.until(lambda f: f[0] == "q_list"), "q_list")
    return dict(zip(ql.get("q_types", []), ql.get("q_id", []))).get(qtype, 0)


def select(srv, login):
    """Logged in and in the location its character wakes in: (client, lcall id)."""
    c = srv.login(login)
    c.send("selPers;num=0;")
    call = first(c.until(lambda f: f[0] == "lcall"), "lcall")
    arrive(c)
    return c, call.get("id")


def leave(c):
    c.send("logout;")
    c.frames(0.4)
    c.s.close()
    time.sleep(0.2)


def legacy(st, login, name, done, journal=()):
    """A character from before the rule, written the way the old server
    wrote one: no home, no saved place; done is (type, done_at) handed in,
    in that order, journal the types still in its journal, as q_st writes
    them (a talk complete at the take)."""
    acc = st.account_by_login(login)["id"]
    cid, _slot = st.create_character(acc, name, 0, "1")
    st.db.execute("UPDATE characters SET home_loc = NULL, home_gx = NULL, home_gy = NULL,"
                  " loc = NULL, gx = NULL, gy = NULL WHERE id = ?", (cid,))
    st.db.commit()
    for t, when in done:
        q_id = st.take_quest(cid, t, {"obj": 1}, True)
        st.finish_quest(q_id, cid, t, when=when)
    for t in journal:
        progress = quests.get(t).fresh_progress()
        st.take_quest(cid, t, progress, quests.get(t).is_complete(progress))


def veteran_db(st):
    """Characters from before the rule that walked into both tutorials, each
    the way the rule's absence let it: which branch it handed a quest of in
    first is its own."""
    then = int(time.time()) - 30 * 86400
    # Both welcomes, the north's an hour first, and Зула's «Друзья» in the
    # journal, still without the milk.
    legacy(st, "veteran", "Veteran", [(WELCOME_N, then), (WELCOME_W, then + 3600)],
           [FRIENDS_N])
    # Only the north's welcome, and the box's fifty afro picked up on a
    # visit to 184 -- in the same second, as a test writes them: the row
    # written first is the first.
    legacy(st, "boxvet", "Boxvet", [(WELCOME_N, then), (BOX_Q, then)])
    # The west's welcome a day before the north's.
    legacy(st, "westvet", "Westvet", [(WELCOME_W, then), (WELCOME_N, then + 86400)])
    # The north's welcome handed in, Джеррах's still in the journal.
    legacy(st, "logvet", "Logvet", [(WELCOME_N, then)], [WELCOME_W])


# --- LAVA_START=183: the west ---------------------------------------------------------
srv = Server("west", ["westerner", "veteran", "boxvet", "westvet", "logvet"],
             seed_db=veteran_db, LAVA_START=str(WEST))
try:
    w = srv.login("westerner")
    call, got = create(w, "Westerner")
    here = inhabitants(got)
    check("LAVA_START=183: a new character wakes in «Западный поселок»",
          (call.get("id"), world.location(WEST).title), (WEST, "Западный поселок"))
    check("  ..where Джеррах stands and Думисани does not",
          (JERRAH in here, DUMISANI in here), (True, False))
    check("  ..and Джеррах's «Добро пожаловать» is offered", status(w, WELCOME_W), 1)
    r = srv.row("Westerner")
    check("  ..the start is his home, written down with its cell",
          (r["home_loc"], r["home_gx"], r["home_gy"]), (WEST,) + WEST_CELL)
    check("  ..and the map puts him on that cell, the way back into the settlement",
          map_cell(w), (WEST_CELL, WEST))

    # Taking the west's first quest closes the north.
    acked, q = take(w, here, JERRAH, WELCOME_W)
    check("«Добро пожаловать» taken from Джеррах", acked, [0])
    check("  ..and nothing of the north is offered any more: Думисани's welcome,"
          " Зула's milk, the cow, Салех's parcel", statuses(w, NORTH),
          {t: 0 for t in NORTH})
    check("  ..while the west's own box still is", status(w, BOX_Q), 1)
    check("  ..handed in to Ибрахим: one pair of shorts, and his «Друзья» is next",
          (hand_in(w, here, IBRAHIM, q), status(w, FRIENDS_W)), ([0], 1))
    check("  ..the north stays shut once it is handed in", statuses(w, NORTH),
          {t: 0 for t in NORTH})
    _call, got = goto(w, PASTURE)
    acked, q = take(w, inhabitants(got), COW, COW_Q)
    check("the cow's quest taken in the pasture anyway: refused, one ack, no journal",
          (acked, q), ([RES_NOT_AVAILABLE], 0))

    # Home, three ways, from the market.
    call, _got = goto(w, MARKET)
    check("off to the market", call.get("id"), MARKET)
    call, _got = home(w)
    check("/home with no «Прописка»: back to his own start, 183, not 181",
          call.get("id"), WEST)
    check("  ..on its map cell", map_cell(w), (WEST_CELL, WEST))
    goto(w, MARKET)
    leave(w)
    cid = srv.row("Westerner")["id"]
    srv.write("UPDATE characters SET death = 1, hp = 0 WHERE id = ?", (cid,))
    w = srv.login("westerner")
    w.send("selPers;num=0;")
    call = first(w.until(lambda f: f[0] == "lcall"), "lcall")
    check("dead at the market and logged in again: he lies where he fell",
          call.get("id"), MARKET)
    arrive(w)
    w.send("resurrect;res_type=0;")
    got = w.until(lambda f: f[0] == "lcall")
    check("  ..and the resurrection takes him home to 183",
          (acks(got), first(got, "lcall").get("id")), ([0], WEST))
    arrive(w)
    check("  ..on its map cell", map_cell(w), (WEST_CELL, WEST))
    leave(w)
    w = srv.login("westerner")
    w.send("selPers;num=0;")
    call = first(w.until(lambda f: f[0] == "lcall"), "lcall")
    check("a relog after that finds him there", call.get("id"), WEST)
    arrive(w)
    leave(w)

    # A character from before the rule keeps what it had.
    v = srv.login("veteran")
    v.send("selPers;num=0;")
    call = first(v.until(lambda f: f[0] == "lcall"), "lcall")
    check("a character made before, with no home and no saved place, still wakes in"
          " the old start, 181, whatever LAVA_START says", call.get("id"), VILLAGE)
    arrive(v)
    call, _got = home(v)
    check("  ..and /home takes it there too", call.get("id"), VILLAGE)
    check("it walked into both welcomes before the rule, the north's first: the north"
          " is its branch -- Зула's «Друзья» in its journal is still carried, the cow"
          " still milks for it --, and nothing more of the west is offered",
          statuses(v, [FRIENDS_N, COW_Q, FINANCE_N, FRIENDS_W, BOX_Q, FINANCE_W]),
          {FRIENDS_N: 1, COW_Q: 1, FINANCE_N: 0, FRIENDS_W: 0, BOX_Q: 0, FINANCE_W: 0})
    _call, got = goto(v, PASTURE)
    acked, q = take(v, inhabitants(got), COW, COW_Q)
    check("  ..the cow milked in 182", (acked, hand_in(v, inhabitants(got), COW, q)),
          ([0], [0]))
    _call, got = goto(v, VILLAGE)
    check("  ..and the milk handed to Салех in 181 for «Друзья»",
          hand_in(v, inhabitants(got), SALEH, carried(v, FRIENDS_N)), [0])
    check("  ..which opens Салех's parcel -- the panama and the hundred afro of its own"
          " branch, once, not never --, and still nothing of the west",
          statuses(v, [FINANCE_N, FRIENDS_W, BOX_Q, FINANCE_W]),
          {FINANCE_N: 1, FRIENDS_W: 0, BOX_Q: 0, FINANCE_W: 0})
    leave(v)

    v, woke = select(srv, "boxvet")
    check("one that handed in the north's welcome and, in the same second, the box's"
          " fifty afro: the row written first is the first, and its north goes on --"
          " Зула's «Друзья» and the cow are offered, the west's Друзья and parcel not",
          (woke, statuses(v, [FRIENDS_N, COW_Q, WELCOME_W, FRIENDS_W, FINANCE_W])),
          (VILLAGE, {FRIENDS_N: 1, COW_Q: 1, WELCOME_W: 0, FRIENDS_W: 0, FINANCE_W: 0}))
    leave(v)

    v, _woke = select(srv, "westvet")
    check("one that handed in the west's welcome a day before the north's: the west is"
          " its branch -- Ибрахим's «Друзья» and the box are offered, the north's not",
          statuses(v, [FRIENDS_W, BOX_Q, FRIENDS_N, COW_Q]),
          {FRIENDS_W: 1, BOX_Q: 1, FRIENDS_N: 0, COW_Q: 0})
    leave(v)

    v, _woke = select(srv, "logvet")
    check("one that handed in the north's welcome and still carries Джеррах's: the hand-in"
          " decides, the north goes on, and the welcome in the journal stays its",
          statuses(v, [FRIENDS_N, COW_Q, WELCOME_W, FRIENDS_W, BOX_Q]),
          {FRIENDS_N: 1, COW_Q: 1, WELCOME_W: 1, FRIENDS_W: 0, BOX_Q: 0})
    _call, got = goto(v, WEST)
    check("  ..handed in to Ибрахим in 183", hand_in(v, inhabitants(got), IBRAHIM,
                                                    carried(v, WELCOME_W)), [0])
    check("  ..which does not make the west its branch now: the first hand-in stays"
          " first", statuses(v, [FRIENDS_N, COW_Q, FRIENDS_W, BOX_Q]),
          {FRIENDS_N: 1, COW_Q: 1, FRIENDS_W: 0, BOX_Q: 0})
    leave(v)
except Exception:
    import traceback
    fails.append("the west's run broke:\n" + traceback.format_exc())
finally:
    srv.stop()

# --- LAVA_START=181: the north ----------------------------------------------------------
srv = Server("north", ["northerner", "boxer"], LAVA_START=str(VILLAGE))
try:
    n = srv.login("northerner")
    call, got = create(n, "Northerner")
    here = inhabitants(got)
    check("LAVA_START=181: a new character wakes in «Нубийское поселение»",
          (call.get("id"), world.location(VILLAGE).title), (VILLAGE, "Нубийское поселение"))
    check("  ..where Думисани stands and Джеррах does not",
          (DUMISANI in here, JERRAH in here), (True, False))
    check("  ..and Думисани's «Добро пожаловать» is offered, and so still is"
          " Джеррах's: nothing is taken yet",
          (status(n, WELCOME_N), status(n, WELCOME_W)), (1, 1))
    r = srv.row("Northerner")
    check("  ..his home is 181 on its cell", (r["home_loc"], r["home_gx"], r["home_gy"]),
          (VILLAGE,) + VILLAGE_CELL)
    acked, q = take(n, here, DUMISANI, WELCOME_N)
    check("«Добро пожаловать» taken from Думисани", acked, [0])
    check("  ..and nothing of the west is offered any more", statuses(n, WESTERN),
          {t: 0 for t in WESTERN})
    check("  ..while the north's own cow still is", status(n, COW_Q), 1)
    n.send("q_ca;q_id=%d;" % q)
    check("dropped: a quest let go commits to nothing, the west is open again",
          (acks(n.frames(0.6)), status(n, WELCOME_W), status(n, BOX_Q)), ([0], 1, 1))
    acked, q = take(n, here, DUMISANI, WELCOME_N)
    check("taken again and handed in to Зула",
          (acked, hand_in(n, here, ZULA, q)), ([0], [0]))
    check("  ..the west shut for good, Зула's «Друзья» next",
          (statuses(n, WESTERN), status(n, FRIENDS_N)), ({t: 0 for t in WESTERN}, 1))
    _call, got = goto(n, WEST)
    acked, q = take(n, inhabitants(got), JERRAH, WELCOME_W)
    check("Джеррах's welcome asked for in 183 anyway: refused, one ack, no journal",
          (acked, q), ([RES_NOT_AVAILABLE], 0))
    _call, got = goto(n, BURIALS)
    acked, q = take(n, inhabitants(got), BOX, BOX_Q)
    check("  ..and so is the box's in 184", (acked, q), ([RES_NOT_AVAILABLE], 0))
    call, _got = home(n)
    check("/home from 184: to 181, his start", call.get("id"), VILLAGE)
    leave(n)

    # The box is a quest of the west too: taking it first commits to the west.
    b = srv.login("boxer")
    create(b, "Boxer")
    _call, got = goto(b, BURIALS)
    acked, q = take(b, inhabitants(got), BOX, BOX_Q)
    check("a newcomer from 181 who finds the box in 184 first takes its quest",
          acked, [0])
    check("  ..and is on the west's tutorial now: Думисани's welcome is not offered,"
          " Джеррах's is", (status(b, WELCOME_N), status(b, WELCOME_W)), (0, 1))
    leave(b)
except Exception:
    import traceback
    fails.append("the north's run broke:\n" + traceback.format_exc())
finally:
    srv.stop()

# --- no knob: both ------------------------------------------------------------------------
logins = ["seed%02d" % i for i in range(CREATIONS)]
srv = Server("random", logins, LAVA_SEED=SEED)
try:
    woke, homes = [], []
    for i, login in enumerate(logins):
        c = srv.login(login)
        call, _got = create(c, "Seed%02d" % i)
        woke.append(call.get("id"))
        leave(c)
        r = srv.row("Seed%02d" % i)
        homes.append(r and (r["home_loc"], r["home_gx"], r["home_gy"]))
    count = collections.Counter(woke)
    print("  ..  %d creations with LAVA_SEED=%s: %s" % (CREATIONS, SEED, dict(count)))
    check("no knob: over %d creations (LAVA_SEED=%s) both starts come up, and nothing"
          " else" % (CREATIONS, SEED), sorted(count), [VILLAGE, WEST])
    check("  ..neither of them a stray: at least a quarter each",
          min(count.values()) >= CREATIONS // 4, True)
    check("  ..and each character's home is the start it woke in, on its cell",
          homes, [(loc,) + (VILLAGE_CELL if loc == VILLAGE else WEST_CELL) for loc in woke])
except Exception:
    import traceback
    fails.append("the random run broke:\n" + traceback.format_exc())
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("start places OK")
