"""A thing on the ground lies fifteen minutes, whoever is there or nobody.

The owner's rule of 2026-09-28: «лут должен быть на локации 15 минут, даже
если там никого нет». Every pile alike -- a creature's loot, what fell off a
dead player, a thing thrown down (a trophy rides in the dead one's bag) --
lies combat.LOOT_LIFETIME from the moment it was put down, each thing on its
own clock, and then it is gone, the room full or empty. Whoever walks in
meanwhile is shown the bags (one ss_loot with every hex, combat.Fighter.
entered); before, a bag was drawn only for whoever stood there when it was
put down, and lay two minutes. Anybody may pick anything up, as before.

A restart does not cut it short: where each thing lies and until when is a
row of the ground table (accounts.SCHEMA), and the server puts back what is
still due as it starts (combat.restore_ground); what ran out meanwhile, or
has no row, is cleared as before. A pack met on the map (encounters.py)
hands its ground to the cell's own wasteland as its room goes.

In process: the owner's number, the store's side of the table (lay_down,
on_ground, pick_up, sweep_ground, clear_ground) on SQLite -- test_storage_pg
runs the same on Postgres -- and RoomCombat's clocks on a real loop, with the
wall clock set by hand so that every boundary is exact: a thing put into a
bag lying there keeps its own time and leaves the others theirs, to the
second; the timer never sleeps more than half of what is left, so a step of
the wall clock costs one step at most; a window open on the bag keeps what
ran out for its take-all; a pack's room hands its bags over; a restart puts
them back into rooms.

On a socket, three runs of the server over one database:
  1. the owner's number: in the dump a hunter kills the bum (his loot) and
     throws a thing down; in the desert he kills the victim (what fell off
     her, at 100 per cent); everybody leaves; a stranger who walks into the
     empty places later is shown every bag; the ground table has each thing
     fifteen minutes from its putting down;
  2. a restart: the stranger comes back to the same bags, stands on the dead
     woman's, and takes it all -- anyone may; and a walker waylaid by a pack
     throws a thing down in its room, steps out, and finds it on the cell's
     own wasteland when he comes back;
  3. a restart with LAVA_LOOT_LIFETIME at 45 seconds, the quarter of an hour
     in small: a thing thrown down in the empty desert is there for a
     newcomer with a third of its time to run, and once its time is out --
     nobody there -- it is gone from the room and from the database; in the
     dump the hunter holds a bag's window open while the first of its two
     things runs out, and his take-all gets the second, with the first taken
     back out of his bag (ss_obj_status 0); the dump's bags, put down under
     the owner's number, keep theirs.

No check waits on a race with a boundary. A time is either set by hand (in
process), or bracketed by the moments before and after what put the thing
down, or met with a third of the lifetime to spare, or waited out by
polling the database until the sweep is seen: the server takes nothing
before its time, and is late by a step of the wall clock at most.

    LAVA_RES=.../lava/res python3 server/test_ground.py
"""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
# The owner's numbers are what the in-process part checks; each server below
# gets its own environment.
for _knob in ("LAVA_LOOT_LIFETIME", "LAVA_WEAR_DROP", "LAVA_BAG_DROP",
              "LAVA_ENCOUNTER_CHANCE", "LAVA_ENCOUNTER_COOLDOWN", "LAVA_ENCOUNTERS_PER_DAY"):
    os.environ.pop(_knob, None)

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import encounters    # noqa: E402
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import progression   # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from inventory import BAG, PRIMARY  # noqa: E402
from protocol import decode  # noqa: E402

from testkit import check, fails  # noqa: E402


DUMP = 100
BUM_HOME = 4363             # an m05_bich of the dump, clear of the dogs (test_loot)
BUM = 411
KNIFE = 6229                # knife_lvl1_A
SAND = 2258                 # Золотой песок: a thing to throw down
AFRO_GUN = 25566            # Наган 1895: falls off the dead
DESERT = (5992, 1760)       # open desert, pvp and nobody else in it (test_pvp)
QUARTER = 15 * 60

# --- in process: the number ----------------------------------------------------------
check("the owner's number: a thing lies fifteen minutes", combat.LOOT_LIFETIME, 900.0)

# --- in process: the store's side, on SQLite ----------------------------------------------
st = accounts.Store(os.path.join(tempfile.mkdtemp(), "ground.db"))


def lying(type_id, owner=combat.LOOT_OWNER):
    f = inventory.new_fields(type_id, 1)
    return st.create_item(owner, type_id, f.pop("root"), **f)["uniq"]


T = 1_800_000_000.0
a, b, c, d = (lying(SAND) for _ in range(4))
mine = lying(SAND, owner=7)
st.lay_down({a: T + 100, b: T - 1}, (DUMP, None, None), 11)
st.lay_down({c: T + 50}, (7, 5833, 1600), 9)
st.lay_down({mine: T + 100}, (DUMP, None, None), 12)     # a ground row gone stale
words = dict(killer_id=1, killer_name="Охотник", killer_lvl=3, victim_id=2,
             victim_name="Жертва", victim_lvl=3, victim_clan="", killed_at=int(T))
ear = st.create_trophy(combat.LOOT_OWNER, BAG, 1495, items.TROPHY, words)["uniq"]
st.lay_down({ear: T - 5}, (DUMP, None, None), 11)
check("clear_ground at a start: the run-out, the one with no ground row at all and the"
      " run-out trophy go -- three -- and a stale row of somebody's thing, not the thing",
      (st.clear_ground(combat.LOOT_OWNER, T), [st.item(u) is None for u in (a, b, c, d, ear)],
       st.item(mine)["char_id"], st.trophy(ear)),
      (3, [False, True, False, True, True], 7, None))
check("on_ground: what is left, where it lies and until when, by serial",
      [(r["uniq"], r["loc"], r["gx"], r["gy"], r["cell"], r["expires_at"])
       for r in st.on_ground(combat.LOOT_OWNER)],
      [(a, DUMP, None, None, 11, T + 100), (c, 7, 5833, 1600, 9, T + 50)])
st.lay_down({a: T + 300}, (DUMP, None, None), 13)
check("lay_down over a row already written moves it",
      [(r["cell"], r["expires_at"]) for r in st.on_ground(combat.LOOT_OWNER) if r["uniq"] == a],
      [(13, T + 300)])
st.pick_up([a], 7, BAG)
check("pick_up: the thing is the picker's under its own serial, off the ground table",
      ((st.item(a)["char_id"], st.item(a)["slot"]), [r["uniq"] for r in st.on_ground(0)]),
      ((7, BAG), [c]))
st.lay_down({mine: T + 100}, (DUMP, None, None), 12)
st.sweep_ground([c, mine], combat.LOOT_OWNER)
check("sweep_ground: the run-out thing and its row gone; somebody's thing left alone",
      (st.item(c), st.item(mine)["char_id"], st.on_ground(combat.LOOT_OWNER)), (None, 7, []))
st.close()


# --- in process: the clocks, on a real loop ------------------------------------------------
class _Room(object):
    """What RoomCombat reads of a room, and the frames it would send."""

    def __init__(self, key, loc_id=DUMP):
        self.key = key
        self.loc = SimpleNamespace(id=loc_id, title="loc %d" % loc_id)
        self.npcs, self.players, self.ws, self.combat = {}, {}, False, None
        self.sent = []

    def broadcast(self, frame, exclude=None):
        self.sent.append((frame[0], frame[1].get("s_status"), frame[1].get("hex")))


class _Rooms(object):
    """rooms.Rooms as restore_ground asks it: a room per key, built once."""

    def __init__(self):
        self.made = {}

    def get(self, key):
        if key == 424242:
            raise KeyError("no such location")
        if key not in self.made:
            self.made[key] = _Room(key, key if isinstance(key, int) else key[0])
        return self.made[key]


class _Clock(object):
    """combat's wall clock, set by hand (combat.time). The deadlines are the
    wall clock's and the loop's timers count on another one: a test that
    slept across a deadline raced the two, and under WSL the wall clock is
    stepped now and then. Set by hand, every boundary is exact."""

    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t


def wake(rc, cell):
    """What the loop does when a bag's timer comes: its callback, now."""
    rc.loot[cell].expiry.cancel()
    rc.expire_bag(cell)


def sleeps(bag):
    """How long the bag's timer has yet to sleep, on the loop's clock."""
    return bag.expiry.when() - asyncio.get_running_loop().time()


st = accounts.Store(os.path.join(tempfile.mkdtemp(), "clocks.db"))


async def _clocks():
    out = {}
    clock = combat.time = _Clock(T)     # the owner's lifetime; the wall clock by hand
    try:
        room = _Room(DUMP)
        # Somebody standing on the bag with its window open (the room's
        # sessions, which RoomCombat.fighters only walks through).
        viewer = SimpleNamespace(loot=10, ran_out=[], sess=SimpleNamespace(pos=10))
        room.players = [SimpleNamespace(combat=viewer)]
        rc = combat.RoomCombat(room, st)
        first, second = lying(SAND), lying(SAND)
        rc.add_to_bag(10, [st.item(first)])
        bag = rc.loot[10]
        # (what the timer should sleep: half of what is left, or the last
        # second whole; what it does)
        out["sleeps"] = [(450.0, sleeps(bag))]
        clock.t = T + 300
        rc.add_to_bag(10, [st.item(second)])
        out["sleeps"].append((300.0, sleeps(bag)))
        out["apart"] = bag.until[second] - bag.until[first]
        out["written"] = sorted((r["uniq"], r["cell"], r["expires_at"] - T)
                                for r in st.on_ground(combat.LOOT_OWNER))
        # The timer comes a tenth of a second before the first one's time
        # (a wall clock set back would bring it so): nothing goes, and the
        # last of the wait is slept in one piece.
        clock.t = T + 899.9
        wake(rc, 10)
        out["sleeps"].append((0.1, sleeps(bag)))
        out["just before"] = (list(bag.uniqs), st.item(first) is not None, list(room.sent),
                              list(viewer.ran_out))
        # Its time: the loop's own timer takes it.
        clock.t = T + 900
        await asyncio.sleep(0.3)
        out["sleeps"].append((150.0, sleeps(bag)))
        out["at 900"] = (list(rc.loot), list(bag.uniqs), st.item(first),
                         [r["uniq"] for r in st.on_ground(combat.LOOT_OWNER)], list(room.sent),
                         [(r["uniq"], r["type_id"]) for r in viewer.ran_out])
        clock.t = T + 1200
        wake(rc, 10)
        out["at 1200"] = (list(rc.loot), st.item(second), st.on_ground(combat.LOOT_OWNER),
                          list(room.sent), [r["uniq"] for r in viewer.ran_out])
        combat.time = time

        # The place a room's ground is written down under.
        out["places"] = [combat.RoomCombat(_Room(k, 5), st).place
                         for k in (5, (5, 5833, 1600), (5, "encounter", 3))]

        # A pack's room hands its bags over, with the time each has left.
        pack = _Room((77, "encounter", 1), 77)
        prc = combat.RoomCombat(pack, st)
        thing = lying(SAND)
        prc.add_to_bag(20, [st.item(thing)])
        due = prc.loot[20].until[thing]
        plain = _Room(77, 77)
        prc.hand_over(plain)
        late = lying(SAND)
        prc.add_to_bag(21, [st.item(late)])
        heir = plain.combat
        out["handed"] = (prc.loot, sorted(heir.loot), heir.loot[20].until[thing] == due,
                         plain.sent, sorted((r["uniq"], r["loc"], r["gx"], r["cell"])
                                            for r in st.on_ground(combat.LOOT_OWNER)))
        for bag in list(heir.loot.values()):
            bag.expiry.cancel()
        st.sweep_ground([thing, late], combat.LOOT_OWNER)

        # A restart: rows written by the last run go back into rooms built
        # for them; the run-out, the unbuildable and the unwritten are cleared.
        now = time.time()
        keep1, keep2, keep3, old, lost, bare = (lying(SAND) for _ in range(6))
        st.lay_down({keep1: now + 500, keep2: now + 400}, (DUMP, None, None), 30)
        st.lay_down({keep3: now + 300}, (9, 5833, 1600), 31)
        st.lay_down({old: now - 1}, (DUMP, None, None), 32)
        st.lay_down({lost: now + 500}, (424242, None, None), 33)
        rs = _Rooms()
        out["restore"] = combat.restore_ground(rs, st)
        made = {k: {cell: (bag.uniqs, [round(bag.until[u] - now) for u in bag.uniqs])
                    for cell, bag in r.combat.loot.items()}
                for k, r in rs.made.items() if r.combat is not None}
        out["rooms"] = made
        out["gone"] = [st.item(u) is None for u in (old, lost, bare)]
        out["ids"] = (keep1, keep2, keep3)
        for r in rs.made.values():
            if r.combat is not None:
                for bag in r.combat.loot.values():
                    bag.expiry.cancel()
        # Nothing left lying: with LAVA_DB_URL every store here is the one
        # Postgres database the servers below start on.
        st.sweep_ground([keep1, keep2, keep3], combat.LOOT_OWNER)
    finally:
        combat.time = time
    return out


got = asyncio.run(_clocks())
check("the second thing into the same bag is put down five minutes later and keeps its own"
      " time", got["apart"], 300.0)
check("each written down on the ground table with its own time, to the second",
      [(cell, dt) for _u, cell, dt in got["written"]], [(10, 900.0), (10, 1200.0)])
first_uniq, second_uniq = [u for u, _c, _t in got["written"]]
check("the timer never sleeps more than half of what is left, and the last second in one"
      " piece -- a step of the wall clock the loop's clock does not take costs one step at"
      " most (each within the second it took to look)",
      [want - slept for want, slept in got["sleeps"]
       if not 0.0 <= want - slept < 1.0], [])
check("a tenth of a second before the first one's time, nothing goes",
      got["just before"], ([first_uniq, second_uniq], True, [("ss_loot", 1, [10])], []))
check("at its time the loop's timer takes it, from the database and the ground table; the"
      " second lies on in the same bag, which is still drawn: nothing shortened, nothing"
      " stretched; the window open on it keeps what went, for its take-all",
      got["at 900"], ([10], [second_uniq], None, [second_uniq], [("ss_loot", 1, [10])],
                      [(first_uniq, SAND)]))
check("at the second's time it is gone too, and the bag with it: ss_loot;s_status=0, once",
      got["at 1200"], ([], None, [], [("ss_loot", 1, [10]), ("ss_loot", 0, [10])],
                       [first_uniq, second_uniq]))
check("the place written down: the location for a place that is one room, the map cell"
      " too for a scene split by cell, and the location for a pack's room",
      got["places"], [(5, None, None), (5, 5833, 1600), (5, None, None)])
handed, cells, same_time, drawn, written = got["handed"]
check("a pack's room going: its bag onto the same cell of the location's room with the"
      " time it had, drawn for whoever is there; a corpse fading after goes there too;"
      " the ground table had them under the location all along",
      (handed, cells, same_time, drawn, [(loc, gx, cell) for _u, loc, gx, cell in written]),
      ({}, [20, 21], True, [("ss_loot", 1, [20]), ("ss_loot", 1, [21])],
       [(77, None, 20), (77, None, 21)]))
keep1, keep2, keep3 = got["ids"]
check("a restart: two things back into the dump on their cell, one into the scene of"
      " 5833,1600 -- each with the time it had left -- and the run-out one, the one whose"
      " room cannot be built and the one never written down cleared",
      (got["restore"], got["rooms"], got["gone"]),
      ((3, 3), {DUMP: {30: ([keep1, keep2], [500, 400])},
                (9, 5833, 1600): {31: ([keep3], [300])}}, [True, True, True]))
st.close()


# --- the server --------------------------------------------------------------------------
def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "ground_srv.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
for _login in ("hunter", "victim", "stranger", "walker"):
    _store.register(_login, "secret")
_store.close()
CRED = {n: accounts.credential(n, "secret") for n in ("hunter", "victim", "stranger", "walker")}

BASE_ENV = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
                LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730", LAVA_RESPAWN="600",
                LAVA_AP_REGEN="25", LAVA_SEED="7", LAVA_POLICY_PORT="0",
                LAVA_WEAR_DROP="100", LAVA_BAG_DROP="100",
                LAVA_ENCOUNTER_CHANCE="1", LAVA_ENCOUNTER_COOLDOWN="600")
_log = []
srv = None
_drain = None


def start(**extra):
    global srv, _drain
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=dict(BASE_ENV, **extra),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
    _drain.start()


def stop():
    srv.terminate()
    srv.wait(timeout=10)
    _drain.join(timeout=5)


def connect(timeout=15):
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


def bags(frames):
    """(s_status, hexes) of every ss_loot among the frames."""
    return [(p["s_status"], sorted(p["hex"])) for p in named(frames, "ss_loot")]


def acks(frames):
    return [p["res"] for p in named(frames, "cmdAck")]


def newcomer(name):
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED[name])
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % name)
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.frames(1.0)
    return c


def come_back(name):
    """A login; the arrival's frames in c.arrival."""
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED[name])
    c.frames()
    c.send("selPers;num=0;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.arrival = c.until(lambda f: f[0] == "lenter") + c.frames(1.0)
    return c


def goto(c, where):
    """/goto a location by number or a map cell; the arrival's frames."""
    text = "/goto %d %d" % where if isinstance(where, tuple) else "/goto %d" % where
    c.send("userMsg;entry=@%s@;group=0;" % text)
    c.until(lambda f: f[0] == "lcall", 3)
    c.send("lenter;accept=1;")
    return c.until(lambda f: f[0] == "lenter") + c.frames(1.0)


def pos_of(frames):
    return named(frames, "lenter")[0]["pos"]


def leave(c):
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    time.sleep(0.2)


def store():
    return accounts.Store(DB)


def char_id(name):
    s = store()
    row = s.db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()
    s.close()
    return row["id"]


def give(cid, type_id, count=1, slot=BAG):
    s = store()
    f = inventory.new_fields(type_id, count)
    f["slot"] = slot
    row = s.create_item(cid, type_id, f.pop("root"), **f)
    s.close()
    return row


def ground():
    """uniq -> the ground row, of every thing lying out."""
    s = store()
    out = {r["uniq"]: r for r in s.on_ground(combat.LOOT_OWNER)}
    s.close()
    return out


def item(uniq):
    s = store()
    row = s.item(uniq)
    s.close()
    return row


def lying_out(uniq):
    """(its items row, whether it has a ground row), read on one connection."""
    s = store()
    out = (s.item(uniq), uniq in {r["uniq"] for r in s.on_ground(combat.LOOT_OWNER)})
    s.close()
    return out


def wait_until(t):
    """Sleep until the wall clock reads t. The server's deadlines are the wall
    clock's (the ground table's expires_at), and time.sleep counts on another
    one: under WSL the wall clock is set now and then, and one sleep of the
    difference can wake before the deadline."""
    while time.time() < t:
        time.sleep(min(0.5, max(0.01, t - time.time())))


def swept(uniq, due, grace=10.0):
    """Its time waited out, then the database polled until the sweep shows:
    (its items row, whether it has a ground row, how long after its time it
    was seen gone). No race with the boundary: the server takes nothing
    before its time, and is late by a step of the wall clock at most
    (combat.RoomCombat.arm_bag), so the wait ends at the sweep however
    loaded the machine is; grace only bounds one that never comes."""
    wait_until(due)
    while True:
        row, on = lying_out(uniq)
        late = time.time() - due
        if (row is None and not on) or late > grace:
            return row, on, late
        time.sleep(0.1)


def given(c, cid, type_id):
    """A thing put into the character's bag by /give: its row."""
    c.send("userMsg;entry=@/give %d 1@;group=0;" % type_id)
    c.until(lambda f: f[0] == "userMsg")
    c.frames(0.5)
    s = store()
    row = max((r for r in s.items_of(cid) if r["type_id"] == type_id), key=lambda r: r["uniq"])
    s.close()
    return row


def in_window(c, cell):
    """Open the loot window on a cell, as a click on its bag does: the acks
    of ss_create and the oids behind the 0 divider of ss_get;slot=24."""
    c.send("ss_create;s_type=0;target=%d;" % cell)
    opened = acks(c.frames(0.5))
    c.send("ss_get;slot=24;")
    listed = [str(o) for o in named(c.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
    return opened, sorted(listed[listed.index("0") + 1:])


def removed(frames):
    """The oids ss_obj_status;status=0 took away."""
    return [str(p["obj"]) for p in named(frames, "ss_obj_status") if p["status"] == 0]


def throw(c, row, cell):
    """Drag a thing out of the equipment onto the ground (PersEquip.dropItem):
    a loot session on the player's own cell, then the thing into it."""
    c.send("ss_create;s_type=0;target=%d;" % cell)
    opened = acks(c.frames(0.5))
    c.send("ss_upd;s_status=2;obj=x%s;param=1;" % inventory.oid_of(row))
    got = c.until(lambda f: f[0] == "ss_loot", 2.0) + c.frames(0.3)
    c.send("ss_upd;s_status=0;obj=x0;param=1;")
    c.frames(0.2)
    return opened + acks(got), bags(got)


def cell_of(c, mob, home):
    for n, p in reversed(c.seen):
        if n == "userMove" and p.get("id") == mob:
            return p["path"][-1]
    return home


try:
    # === the characters =========================================================================
    start()
    for name in ("hunter", "victim", "stranger", "walker"):
        leave(newcomer(name))
    H, V, S, W = (char_id(n) for n in ("hunter", "victim", "stranger", "walker"))
    s = store()
    ch = progression.Character.load(s, H)
    ch.skill[progression.MELEE] = [20, 0, progression.skill_xp_max(20)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(s)
    for row in s.items_of(H):
        if row["slot"] == PRIMARY:
            s.update_item(row["uniq"], slot=BAG)
    s.save_character_state(V, hp=1, sp=0)
    s.close()
    knife = give(H, KNIFE, slot=PRIMARY)
    to_throw = give(H, SAND)
    victim_gun, victim_sand = give(V, AFRO_GUN), give(V, SAND, 2)
    walker_sand = give(W, SAND)
    stop()

    # === run 1: the owner's number ================================================================
    start()
    h = come_back("hunter")
    arrival = goto(h, DUMP)
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    bum = spawns[BUM_HOME]
    pos = pos_of(arrival)
    loc = world.location(DUMP)
    others = [(cell, mobs.stats(t)) for cell, t in loc.spawns
              if cell != BUM_HOME and mobs.stats(t).can_attack]
    spot = lambda cell: (
        mobs.hex_distance(cell, BUM_HOME, loc.width) <= mobs.stats(BUM).aggro - 0.5
        and all(mobs.hex_distance(cell, o, loc.width) > st_.aggro + 1.5 for o, st_ in others))
    path = mobs.find_path(loc, pos, spot, {BUM_HOME})
    t_bum0 = time.time()        # the bum's loot goes down after this, and before t_bum
    h.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
    pos = path[-1]
    h.until(lambda f: f[0] == "lch" and f[1].get("enemy") == bum, 6)
    dead = None
    for attempt in range(120):
        if mobs.adjacent(pos, cell_of(h, bum, BUM_HOME), loc):
            h.send("ss_use;type=16;obj=x%s;target=x1%08x;" % (inventory.oid_of(knife), bum))
            got = h.until(lambda f: f[0] == "c_ap"
                          or (f[0] == "cmdAck" and f[1]["res"] != 0), 3)
            got += h.frames(0.2)
        else:
            got = h.frames(0.4)
        if [p for n, p in got if n == "lch" and p.get("dead") == bum]:
            dead = got
            break
    check("run 1: the hunter kills the dump's bum", dead is not None, True)
    bum_cell = cell_of(h, bum, BUM_HOME)
    got = h.until(lambda f: f[0] == "ss_loot", 5)
    t_bum = time.time()
    check("  ..his bag lies where he fell", bags(got), [(1, [bum_cell])])
    t_throw0 = time.time()
    res, drawn = throw(h, to_throw, pos)
    t_throw = time.time()
    check("  ..and the hunter throws a thing down on his own cell: a bag of its own",
          (res, drawn, pos != bum_cell), ([0, 0], [(1, [pos])], True))
    thrown_cell = pos

    arrival = goto(h, DESERT)
    desert_cell = pos_of(arrival)
    check("  ..the hunter leaves the dump: nothing there lies in the desert",
          bags(arrival), [])
    v = come_back("victim")
    arrival = goto(v, DESERT)
    check("  ..the victim comes to the desert, onto the cell the hunter came in on",
          pos_of(arrival), desert_cell)
    VP = rooms.player_id(V)
    desert = world.location(world.location_at(*DESERT))
    beside = next(n for n in progression.hex_neighbours(desert_cell, desert.width, desert.height)
                  if n not in desert.obstacles)
    h.send("moveTo;path=|%d|%d|;" % (desert_cell, beside))
    h.frames(0.5 + mobs.HEX_MS / 1000.0)
    seen_h, seen_v = [], []
    t_death0 = time.time()
    for _ in range(25):
        h.send("ss_use;type=16;obj=x%s;target=x1%08x;" % (inventory.oid_of(knife), VP))
        seen_h += h.until(lambda f: f[0] in ("caHit", "caMiss", "cmdAck") and
                          (f[0] != "cmdAck" or f[1].get("res") != 0), 3.0)
        seen_v += v.frames(0.3)
        if any(n == "lch" and p.get("dead") == 0 for n, p in seen_v):
            break
    seen_h += h.until(lambda f: f[0] == "ss_loot", 3.0)
    t_death = time.time()
    check("  ..and kills her there: what fell off her lies in one bag on her cell",
          ([p for n, p in seen_v if n == "lch" and "dead" in p], bags(seen_h)),
          ([{"dead": 0}], [(1, [desert_cell])]))
    dropped = {u: r for u, r in ground().items() if r["loc"] != DUMP}
    s = store()
    kinds = sorted(s.item(u)["type_id"] for u in dropped)
    s.close()
    check("  ..her gun, her sand and a third of her rounds -- her pistol stays in her hand",
          kinds, sorted([AFRO_GUN, SAND, inventory.STARTER_AMMO]))
    v.send("resurrect;res_type=0;")
    v.until(lambda f: f[0] == "lcall", 3)
    leave(v)
    leave(h)

    # Nobody in the dump, nobody in the desert: what the ground table says.
    rows = ground()
    in_dump = {u: r for u, r in rows.items() if r["loc"] == DUMP}
    check("the ground table, the places empty: the bum's loot and the thrown thing in the"
          " dump on their cells, one room (no map cell); her things in the desert on hers",
          (sorted({r["cell"] for r in in_dump.values()}),
           sorted({(r["gx"], r["gy"]) for r in rows.values()}, key=str),
           to_throw["uniq"] in in_dump and in_dump[to_throw["uniq"]]["cell"] == thrown_cell,
           sorted({r["cell"] for u, r in rows.items() if u in dropped})),
          (sorted([bum_cell, thrown_cell]), [(None, None)], True, [desert_cell]))
    put = {u: ((t_throw0, t_throw) if u == to_throw["uniq"] else
               (t_death0, t_death) if u in dropped else (t_bum0, t_bum)) for u in rows}
    check("each fifteen minutes from the moment it was put down, not two",
          sorted({round((r["expires_at"] - put[u][1]) / 60.0) for u, r in rows.items()}), [15])
    check("  ..to the second: between fifteen minutes past the moment before what put it"
          " down and fifteen past the moment after",
          [u for u, r in rows.items()
           if not put[u][0] + QUARTER <= r["expires_at"] <= put[u][1] + QUARTER], [])

    sg = come_back("stranger")
    check("a stranger logs in elsewhere and is shown no bag there", bags(sg.arrival), [])
    arrival = goto(sg, DUMP)
    check("  ..walks into the empty dump: both bags drawn for him, in one ss_loot",
          bags(arrival), [(1, sorted([bum_cell, thrown_cell]))])
    arrival = goto(sg, DESERT)
    check("  ..and into the empty desert: the dead woman's bag, under his feet",
          (bags(arrival), pos_of(arrival)), ([(1, [desert_cell])], desert_cell))
    leave(sg)
    stop()

    # === run 2: a restart ===========================================================================
    start()
    sg = come_back("stranger")
    check("run 2, after a restart: the stranger comes back where he left, onto her bag, and"
          " it is drawn for him", (bags(sg.arrival), pos_of(sg.arrival)),
          ([(1, [desert_cell])], desert_cell))
    sg.send("ss_create;s_type=0;target=%d;" % desert_cell)
    opened = acks(sg.frames(0.5))
    sg.send("ss_get;slot=24;")
    listed = [str(o) for o in named(sg.until(lambda f: f[0] == "ss_ack"), "ss_ack")[0]["o_list"]]
    inside = listed[listed.index("0") + 1:]
    s = store()
    her = sorted(inventory.oid_of(s.item(u)) for u in dropped)
    s.close()
    check("  ..opens it, and in it is all that fell off her -- under the same serials",
          (opened, sorted(inside)), ([0], her))
    sg.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = sg.until(lambda f: f[0] == "ss_loot", 3.0) + sg.frames(0.3)
    check("  ..takes it all, as anybody may: the ack, and the empty bag gone",
          (acks(got), bags(got)), ([0], [(0, [desert_cell])]))
    s = store()
    check("  ..hers are his now, and off the ground table",
          ([s.item(u)["char_id"] for u in dropped], [u for u in dropped if u in ground()]),
          ([S] * len(dropped), []))
    s.close()
    arrival = goto(sg, DUMP)
    check("  ..and the dump's two bags lie on after the restart too",
          bags(arrival), [(1, sorted([bum_cell, thrown_cell]))])
    leave(sg)
    log_text = "".join(_log)
    check("the log says what came back",
          "%d item(s) back on the ground where the last run left them" % len(rows) in log_text,
          True)

    # A pack on the map: the walker's thing thrown down in its room is on
    # the cell's own wasteland once the pack's room is gone.
    first = next((x, y) for y in range(1700, 1720) for x in range(5940, 5965)
                 if world.location_at(x, y) == world.pack(x, y) and world.passable(x, y)
                 and all(world.passable(x + k, y) for k in range(1, 7))
                 and all((encounters.band_at(x + k, y) or encounters.Band(0, 0, 0, 0, ()))
                         .camp == 80 for k in (3, 4, 5, 6)))
    met_at = (first[0] + 3, first[1])
    w = come_back("walker")
    goto(w, first)
    w.send("chWorld;")
    w.until(lambda f: f[0] == "gmap", 3)
    w.send("moveTo;dx=600;dy=0;")
    got = w.until(lambda f: f[0] == "lcall", 30)
    check("the walker is waylaid on %d,%d" % met_at,
          [p["id"] for p in named(got, "lcall")], [world.pack(*met_at)])
    w.send("lenter;accept=1;")
    arrival = w.until(lambda f: f[0] == "lenter") + w.frames(0.5)
    pack_cell = pos_of(arrival)
    res, drawn = throw(w, walker_sand, pack_cell)
    check("  ..throws a thing down in the pack's room", (res, drawn), ([0, 0], [(1, [pack_cell])]))
    row = ground().get(walker_sand["uniq"])
    check("  ..written down under the cell's location, not the pack's room",
          row and (row["loc"], row["gx"], row["gy"], row["cell"]),
          (world.pack(*met_at), None, None, pack_cell))
    w.send("chWorld;")
    back = w.until(lambda f: f[0] == "gmap", 3)
    time.sleep(0.3)
    check("  ..steps out onto the map, and the pack's room is gone",
          ("gmap" in [n for n, _p in back],
           "the pack of %d,%d is gone" % met_at in "".join(_log)), (True, True))
    arrival = goto(w, met_at)
    check("  ..back on that cell by /goto: the cell's own wasteland, the thing in its bag",
          bags(arrival), [(1, [pack_cell])])
    w.send("ss_create;s_type=0;target=%d;" % pack_cell)
    far = acks(w.frames(0.5))
    leave(w)
    check("  ..(and the bag is real: the server opens it, or says it is too far)",
          far in ([0], [combat.RES_TOO_FAR]), True)
    stop()

    # === run 3: the quarter of an hour in small =======================================================
    # No boundary is raced: a look before a thing's time comes a third of
    # the lifetime early, and one after it waits for the sweep (swept).
    LIFE = 45.0
    EARLY = LIFE / 3.0
    GAP = 10.0                  # between the two things of the hunter's bag
    start(LAVA_LOOT_LIFETIME=str(int(LIFE)))
    h = come_back("hunter")
    arrival = goto(h, DESERT)
    here = pos_of(arrival)
    check("run 3, lifetime %d s: the hunter back in the desert, where nothing lies now"
          % LIFE, (bags(arrival), here), ([], desert_cell))
    thrown = given(h, H, SAND)
    t0 = time.time()
    res, drawn = throw(h, thrown, here)
    t1 = time.time()
    check("  ..throws a thing down on it", (res, drawn), ([0, 0], [(1, [here])]))
    due = ground()[thrown["uniq"]]["expires_at"]
    check("  ..to lie %d s from the moment it went down" % LIFE,
          t0 + LIFE <= due <= t1 + LIFE, True)
    arrival = goto(h, DUMP)
    check("  ..and walks into the dump: the two bags of run 1, still lying",
          bags(arrival), [(1, sorted([bum_cell, thrown_cell]))])

    # He stays there, with a bag of two things on his cell, its window open
    # while the first of them runs out.
    hc = pos_of(arrival)
    early = given(h, H, SAND)
    res, drawn = throw(h, early, hc)
    check("  ..throws a thing down on his own cell there: a bag of its own",
          (res, drawn), ([0, 0], [(1, [hc])]))
    due_early = ground()[early["uniq"]]["expires_at"]
    wait_until(due_early - LIFE + GAP)
    late = given(h, H, KNIFE)
    res, drawn = throw(h, late, hc)
    due_late = ground()[late["uniq"]]["expires_at"]
    check("  ..and %d s later another into the same bag, on a clock of its own" % GAP,
          (res, drawn, due_late - due_early >= GAP), ([0, 0], [], True))
    check("  ..opens its window: both in it",
          in_window(h, hc), ([0], sorted([inventory.oid_of(early), inventory.oid_of(late)])))
    mark = len(h.seen)

    sg = come_back("stranger")    # in the dump, where run 2 left him
    wait_until(due - EARLY)
    arrival = goto(sg, DESERT)
    check("with a third of its time to run, the desert empty all the while, a newcomer is"
          " shown the bag", (bags(arrival), pos_of(arrival)), ([(1, [here])], here))
    opened, inside = in_window(sg, here)
    t_in = time.time()
    check("  ..and finds the thing in it (%.1f s before its time)" % (due - t_in),
          (opened, inside, t_in < due), ([0], [inventory.oid_of(thrown)], True))
    sg.send("ss_upd;s_status=0;obj=x0;param=1;")
    goto(sg, DUMP)                # out: nobody in the desert when its time comes
    row, on, after = swept(thrown["uniq"], due)
    check("its time out, nobody there: the thing is gone from the database and the ground"
          " table (seen %.1f s after its time)" % after, (row, on), (None, False))
    arrival = goto(sg, DESERT)
    check("  ..and a newcomer to the desert is shown no bag", bags(arrival), [])

    row, on, after = swept(early["uniq"], due_early)
    h.frames(0.2)
    s = store()
    kept = s.item(late["uniq"])
    s.close()
    check("in the dump the first of the hunter's two runs out under his open window (seen %.1f"
          " s after its time): gone from the database, the second still lying, the bag"
          " still drawn -- nothing sent" % after,
          (row, on, kept and kept["char_id"], late["uniq"] in ground(), bags(h.seen[mark:])),
          (None, False, combat.LOOT_OWNER, True, []))
    h.send("ss_upd;s_status=3;obj=x0;param=1;")
    got = h.until(lambda f: f[0] == "ss_loot", 3.0) + h.frames(0.3)
    s = store()
    check("  ..his take-all: the ack, on which the client moves the whole window into his"
          " bag; the one that ran out taken back out of it (ss_obj_status 0) right behind;"
          " the bag gone; the second is his",
          ([n for n, _p in got if n in ("cmdAck", "ss_obj_status", "ss_loot")], acks(got),
           removed(got), bags(got), s.item(late["uniq"])["char_id"], s.item(early["uniq"])),
          (["cmdAck", "ss_obj_status", "ss_loot"], [0], [inventory.oid_of(early)],
           [(0, [hc])], H, None))
    s.close()
    leave(h)
    arrival = goto(sg, DUMP)
    check("  ..while the dump's, put down under the owner's number, lie on",
          bags(arrival), [(1, sorted([bum_cell, thrown_cell]))])
    leave(sg)
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    if srv is not None and srv.poll() is None:
        stop()
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-3000:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("ground OK")
