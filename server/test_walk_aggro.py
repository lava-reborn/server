"""A creature meets a walking player where the figure is, not where the
walk will end.

The client draws a walk one hex every mobs.HEX_MS from the server's echo
(LocWalker.startMove), and moves its own idea of the player's cell only
when each step is done (LocWalker.finishPathPart). The server used to put
the player on the last cell of the path the moment the moveTo came in, so
a creature beside that cell bit a player who was still running towards it
on his screen, and one whose aggro radius held it took him as its target
at the first tick, seconds before he got there.

What is held to here:

  * in process, on a real RoomCombat: the fight asks Fighter.cell, and a
    session that walks answers with its live cell (Session.live_cell), not
    its pos. A dog with the player's pos inside its radius and his figure
    outside takes nobody; a dog beside his pos but not beside his figure
    does not bite and goes after the figure instead, and does not step on
    the hex the figure stands on;
  * in process, on a real Session: only a path the client could have sent
    is followed (Session.walk_of) -- not one padded with repeats, not a
    jump, not one that starts away from the figure; a turn sent from a hex
    the figure has passed is;
  * on a socket, in the dump (100): a walk of nineteen hexes into a dog's
    radius, crossed on the seventeenth. The dog takes him (lch;enemy) and
    first goes for him no sooner than the figure is inside its radius, not
    one AI tick after the moveTo.

Written against the code before the change, both parts fail: the dog takes
the player and bites at his pos.
"""
import asyncio
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

sys.path.insert(0, HERE)
import accounts      # noqa: E402
import combat        # noqa: E402
import mobs          # noqa: E402
import progression   # noqa: E402
import rooms         # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

DUMP = 100
DOG_HOME, DOG = 4551, 82              # mStarvingDog_lvl1
STEP = mobs.HEX_MS / 1000.0

from testkit import check, fails  # noqa: E402


LOC = world.location(DUMP)
W = LOC.width
AGGRO = mobs.stats(DOG).aggro


def _open(cell):
    return 0 <= cell < W * LOC.height and cell not in LOC.obstacles


# Every other creature here that would take him, and the ground around it.
_OTHERS = [(cell, mobs.stats(t)) for cell, t in LOC.spawns
           if cell != DOG_HOME and mobs.stats(t).can_attack]
WARY = {cell for cell in range(W * LOC.height)
        if any(mobs.hex_distance(cell, o, W) <= st.aggro + 1.5 for o, st in _OTHERS)}


# --- in process: a real RoomCombat, a seat whose figure is somewhere else ---------
class _Room(object):
    def __init__(self):
        self.loc = LOC
        self.npcs = {}
        self.players = {}
        self.ws = False
        self.sent = []

    def broadcast(self, frame, exclude=None):
        self.sent.append(frame)


class _Inv(object):
    store = None

    def wear_worn(self, n):
        pass


class _Walker(object):
    """A session half way through a walk: pos is where it ends, live is the
    hex the figure has reached (what server.Session.live_cell answers)."""
    char_id = 0
    on_map = False

    def __init__(self, room, pos, live):
        self.room, self.pos, self.live = room, pos, live
        self.pid = rooms.player_id(1)
        self.inv = _Inv()
        self.sent = []
        self.char = progression.Character()
        self.combat = combat.Fighter(self)
        self.combat.regen_at = float("inf")
        room.players[self] = None

    def live_cell(self):
        return self.live

    def send(self, *cmd, **params):
        self.sent.append((cmd[0], params))

    def character(self):
        return self.char


def _scene(pos, live):
    room = _Room()
    room.combat = rc = combat.RoomCombat(room, None)
    seat = _Walker(room, pos, live)
    dog = rc.mobs[1] = mobs.Mob(1, DOG, DOG_HOME)
    return room, rc, seat, dog


async def _in_process():
    t = 1000.0
    inside = next(c for c in range(W * LOC.height)
                  if _open(c) and 2 <= mobs.hex_distance(c, DOG_HOME, W) <= AGGRO - 1)
    outside = next(c for c in range(W * LOC.height)
                   if _open(c) and AGGRO + 3 <= mobs.hex_distance(c, DOG_HOME, W) <= AGGRO + 5)
    room, rc, seat, dog = _scene(pos=inside, live=outside)
    check("the fight sees the figure, not the end of its walk",
          seat.combat.cell, outside)
    dog.think(rc, t)
    check("his walk ends %.1f hexes from the dog, his figure is still %.1f off: the dog"
          " takes nobody" % (mobs.hex_distance(inside, DOG_HOME, W),
                             mobs.hex_distance(outside, DOG_HOME, W)),
          (dog.target, room.sent), (None, []))
    seat.live = inside
    dog.think(rc, t + combat.AI_TICK)
    check("the figure in, the dog takes him", dog.target is seat.combat, True)

    # The dog after him, beside the end of his walk, his figure four hexes off.
    end = next(c for c in progression.hex_neighbours(DOG_HOME, W, LOC.height) if _open(c))
    away = next(c for c in range(W * LOC.height)
                if _open(c) and 3.5 <= mobs.hex_distance(c, DOG_HOME, W) <= 4.5
                and mobs.find_path(LOC, DOG_HOME, lambda x: mobs.adjacent(x, c, LOC)) is not None)
    room, rc, seat, dog = _scene(pos=end, live=away)
    rc.aggro(dog, seat.combat, t)
    room.sent = []
    dog.think(rc, t + 1.0)
    check("beside where his walk ends, but not beside him: the dog does not bite",
          ([n for n, p in room.sent if n in ("caHit", "caMiss")], dog.aim), ([], None))
    legs = [p["path"] for n, p in room.sent if n == "userMove" and p.get("id") == 1]
    check("it goes after the figure instead", legs != [] and away not in legs[0], True)
    check("  ..and closes on it",
          mobs.hex_distance(dog.cell, away, W) < mobs.hex_distance(DOG_HOME, away, W), True)


try:
    asyncio.run(_in_process())
except Exception:
    import traceback
    fails.append("the in-process part broke:\n" + traceback.format_exc())


# --- in process: only a walk the client could have sent is followed ---------------
# A moveTo padded with repeats ([start] * 300 + [beside the dog]) put pos
# beside the dog at once while the fight kept the figure on start for a
# minute: nothing there could take him (Session.walk_of). Such a path, and a
# jump, are taken as every walk was before the walk was followed -- the
# player at its end at once.
class _Writer(object):
    def write(self, data):
        pass

    def close(self):
        pass

    def get_extra_info(self, _name, default=None):
        return default


accounts.DB_PATH = os.path.join(tempfile.mkdtemp(), "walk_of.db")
import server        # noqa: E402  (its Store opens at import: a file of its own)


async def _walk_of():
    start = next(c for c in range(W * LOC.height)
                 if _open(c) and AGGRO + 6 <= mobs.hex_distance(c, DOG_HOME, W) <= AGGRO + 9
                 and mobs.find_path(LOC, c, lambda x: mobs.hex_distance(x, DOG_HOME, W) <= 2))
    honest = mobs.find_path(LOC, start, lambda x: mobs.hex_distance(x, DOG_HOME, W) <= 2)
    end = honest[-1]
    sess = server.Session(_Writer(), "walker")
    sess.loc = LOC
    sess.pos = start
    check("an honest walk of %d hexes is followed" % (len(honest) - 1),
          sess.walk_of(honest) is not None, True)
    check("[start] * 300 + [the end] is not: the player is at the end at once",
          sess.walk_of([start] * 300 + [end]), None)
    check("  ..nor a path that jumps", sess.walk_of([start, honest[1], end]), None)
    far = next(c for c in honest if mobs.hex_distance(c, start, W) >= 4)
    check("  ..nor one that starts away from the figure", sess.walk_of(honest[honest.index(far):]), None)
    sess.walk = sess.walk_of(honest)
    await asyncio.sleep(STEP * 3 + 0.05)
    behind = honest[1]
    check("a turn sent from a hex the figure has already passed is followed",
          sess.walk_of(mobs.find_path(LOC, behind, lambda x: x == start)) is not None, True)


try:
    asyncio.run(_walk_of())
except Exception:
    import traceback
    fails.append("the walk_of part broke:\n" + traceback.format_exc())


# --- on a socket: the dump, a long walk into a dog's radius -------------------------
def _approach():
    """(start, path): a walk from outside the dog's radius into it, crossed
    late, with nobody else's radius anywhere on it."""
    ends = [c for c in range(W * LOC.height)
            if _open(c) and c not in WARY and 2.5 <= mobs.hex_distance(c, DOG_HOME, W) <= AGGRO - 1]
    for end in ends:
        for start in range(W * LOC.height):
            if not _open(start) or start in WARY:
                continue
            if not AGGRO + 9 <= mobs.hex_distance(start, DOG_HOME, W) <= AGGRO + 12:
                continue
            path = mobs.find_path(LOC, start, lambda x, e=end: x == e, WARY | {DOG_HOME})
            if not path:
                continue
            k = next(i for i, c in enumerate(path) if mobs.hex_distance(c, DOG_HOME, W) <= AGGRO)
            if 12 <= k <= 20 and len(path) - k >= 2:
                return path, k
    return None, None


PATH, CROSS = _approach()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "walk_aggro.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("runner", "secret")
_store.close()
CRED = accounts.credential("runner", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730", LAVA_SEED="7")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


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
        self.seen = []            # (time.time() it came, frame)

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
        self.seen += [(time.time(), f) for f in out]
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


def walk_to(c, pos, goal, avoid):
    """Walk to goal and wait until the figure is there."""
    path = mobs.find_path(LOC, pos, lambda x: x == goal, avoid)
    if path is None:
        raise RuntimeError("no path from %d to %d" % (pos, goal))
    if len(path) > 1:
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
        c.frames(STEP * (len(path) - 1) + 0.5)
    return goal


try:
    check("a walk of %s hexes into the dog's radius, crossed on step %s"
          % (None if PATH is None else len(PATH) - 1, CROSS),
          PATH is not None and CROSS * STEP > combat.AI_TICK * 4, True)
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@runner@;")
    c.frames()
    c.send("actPlayer;")
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    c.frames(1.5)
    c.send("userMsg;entry=@/goto %d@;group=0;" % DUMP)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    arrival = c.frames(2)
    pos = named(arrival, "lenter")[0]["pos"]
    spawns = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    dog = spawns[DOG_HOME]
    wide = {cell for cell in range(W * LOC.height)
            if mobs.hex_distance(cell, DOG_HOME, W) <= AGGRO + 1.5}
    pos = walk_to(c, pos, PATH[0], WARY | wide)
    check("at the start of the walk, and nobody after him yet",
          [p for n, p in c.frames(0.5) if n == "lch" and "enemy" in p], [])

    t0 = time.time()
    c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in PATH))
    c.until(lambda f: f[0] in ("caHit", "caMiss") and f[1].get("id") == dog,
            STEP * len(PATH) + 4)
    seen = [(at - t0, n, p) for at, (n, p) in c.seen if at >= t0]
    took = [at for at, n, p in seen if n == "lch" and p.get("enemy") == dog]
    snapped = [at for at, n, p in seen if n in ("caHit", "caMiss") and p.get("id") == dog]
    crossed = CROSS * STEP
    check("the dog takes him", took != [], True)
    check("but not before his figure is inside its radius (%.1f s into the walk)" % crossed,
          took != [] and took[0] >= crossed - 0.1, True)
    check("  ..and within a tick or two of it",
          took != [] and took[0] <= crossed + STEP + 2 * combat.AI_TICK + 0.3, True)
    check("it goes for him, no sooner either", snapped != [] and snapped[0] >= crossed - 0.1, True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
except Exception:
    import traceback
    fails.append("the socket part broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=5)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails or os.environ.get("LAVA_TEST_LOG"):
        fails.append("server log tail:\n" + out[-4000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("walk aggro OK")
