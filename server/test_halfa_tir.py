"""Берт Гаммер's range, on a socket: a target of TIR_01 (1048) is shot from
the booth until it falls, and comes back.

In every range file the player stands in a booth closed off by a two-hex
counter and the targets (nz_Target1..6, 1397-1402) stand beyond it: no cell
he can walk to is next to one, and before world.SHOOT_OVER every shot from
the booth hit the counter -- 25 shots, 25 faWall, the target's bar never
moved. Now the counter (obstacle code 1) is shot over there, and only
there (combat.shot_wall). What is held to here:

  * the target stands beyond the counter, out of a fist's reach from every
    cell of the booth, and the booth has a cell with a clear shot at it;
  * from there the kit's Самострел hits it: no faWall, faHit, its bar goes
    down, one cmdAck for every command;
  * it never turns on the shooter: no enemy mark, no aim, no blow of its own;
  * it dies (lch;dead) and stands again after LAVA_RESPAWN.

That its kill counts for a kill quest and that it rolls no stand-in
cigarette is held to in process (test_halfa_world.py): the socket goes
through the same RoomCombat.kill.

    LAVA_RES=.../lava/res python3 server/test_halfa_tir.py
"""
import collections
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
import inventory     # noqa: E402
import items         # noqa: E402
import mobs          # noqa: E402
import progression   # noqa: E402
import world         # noqa: E402
from protocol import decode   # noqa: E402

RANGE = 1048                  # TIR_01
TARGET = 1397                 # nz_Target1
CROSSBOW, BOLTS = 25562, 6188  # the kit's Самострел and its 9 mm
RESPAWN = 3                   # LAVA_RESPAWN for the scene

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


LOC = world.location(RANGE)
W = LOC.width


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "tir.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("shooter", "secret")
_store.close()
CRED = accounts.credential("shooter", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_CHEATS="1", LAVA_START="181", LAVA_RESPAWN=str(RESPAWN),
           LAVA_AP_REGEN="50", LAVA_SEED="7", LAVA_LEAVE_COMBAT="2")
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
        self.seen = []            # every frame this client was ever handed

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


def entity(eid):
    return "x1%08x" % eid


def login(c, first=False):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    got = c.frames()
    if first:
        c.send("newPers;res=1;sex=0;name=@shooter@;")
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    return got + c.until(lambda f: f[0] == "lcall")


try:
    c = Client(connect())
    login(c, first=True)
    c.send("logout;")
    c.frames(0.3)
    c.s.close()
    store = accounts.Store(DB)
    char_id = store.character_by_name("shooter")["id"]
    ch = progression.Character.load(store, char_id)
    ch.skill[progression.SHOOTING] = [50, 0, progression.skill_xp_max(50)]
    ch.recalc()
    ch.hp = ch.sp = None
    ch.save(store)
    store.close()

    c = Client(connect())
    login(c)
    c.send("lenter;accept=1;")
    c.frames(1.5)
    c.send("userMsg;entry=@/goto %d@;group=0;" % RANGE)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    arrival = c.frames(2)
    pos = named(arrival, "lenter")[0]["pos"]
    stand = {p["pos"]: p["newUser"] for p in named(arrival, "lch") if "newUser" in p}
    kinds = {p["id"]: p.get("name") for p in named(arrival, "userInfo")}
    targets = sorted((mobs.hex_distance(pos, cell, W), cell, eid)
                     for cell, eid in stand.items() if kinds.get(eid) == TARGET)
    check("the range stands its targets (nz_Target1, 1397), beyond the counter",
          len(targets) >= 1, True)
    _d, tcell, tgt = targets[0]

    # The booth: every cell he can walk to from where he came in.
    booth = {pos}
    queue = collections.deque([pos])
    while queue:
        cur = queue.popleft()
        for nb in progression.hex_neighbours(cur, W, LOC.height):
            if nb not in booth and nb not in LOC.obstacles and nb not in stand:
                booth.add(nb)
                queue.append(nb)
    check("no cell of the booth is next to the target: a fist does not reach it",
          [cell for cell in booth if mobs.adjacent(cell, tcell, LOC)], [])
    check("from every cell of the booth the counter stands in the way of a bullet as the"
          " rest of the world sees it (mobs.line_of_fire)",
          [cell for cell in booth if mobs.line_of_fire(LOC, cell, tcell) is None], [])

    c.send("userMsg;entry=@/give %d 500@;group=0;" % BOLTS)
    c.frames(0.5)
    c.send("ss_get;target=0;slot=11;")
    kit = [str(x) for x in named(c.frames(), "ss_ack")[0]["o_list"]]
    gun = next(o for o in kit if o != "0" and inventory.parse_oid(o)[1] == CROSSBOW)
    ammo = [o for o in kit if o != "0" and inventory.parse_oid(o)[1] == BOLTS][-1]
    reach = items.params_of(CROSSBOW)["max_range"][0]

    def load():
        c.send("ss_use;target=x%s;obj=x%s;type=1;" % (ammo, gun))
        c.frames(1.0)

    load()
    good = lambda cell: (mobs.hex_distance(cell, tcell, W) <= reach - 1
                         and combat.shot_wall(LOC, cell, tcell) is None)
    path = None if good(pos) else mobs.find_path(LOC, pos, good, set(stand))
    check("the booth has a cell with a clear shot at it, over the counter, within the"
          " Самострел's %d hexes" % reach, good(pos) or bool(path), True)
    if path:
        c.send("moveTo;path=|%s|;" % "|".join(str(x) for x in path))
        c.frames(0.3 + 0.25 * len(path))

    start = len(c.seen)
    sent = dead = 0
    for _ in range(40):
        c.send("ss_use;type=16;obj=x%s;target=%s;" % (gun, entity(tgt)))
        sent += 1
        got = c.frames(0.9)
        if any(n == "lch" and p.get("dead") == tgt for n, p in got):
            dead = 1
            break
        if any(n == "ss_di_firearm" and p.get("ammo_count") == 0 for n, p in got):
            load()
            sent += 1
    shots = c.seen[start:] + c.frames(0.5)
    check("no shot hits the counter (faWall), and some hit the target (faHit)",
          (len(named(shots, "faWall")), [p for p in named(shots, "faHit")
                                         if p.get("target") == tgt] != []), (0, True))
    bars = [p["hcur"] for p in named(shots, "usrUp") if p.get("id") == tgt]
    check("its bar goes down", bars != [] and min(bars) < max(bars), True)
    check("one cmdAck for every command, every one res=0",
          [p.get("res") for p in named(shots, "cmdAck")], [0] * sent)
    check("it falls (lch;dead)", dead, 1)
    check("it never turned on him: no enemy mark, no aim, no blow of its own",
          ([p for p in named(shots, "lch") if p.get("enemy") == tgt],
           [n for n, p in shots if n in ("faAim", "caHit", "caMiss") and p.get("id") == tgt]),
          ([], []))
    back = c.until(lambda f: f[0] == "lch" and f[1].get("newUser") == tgt,
                   RESPAWN + combat.CORPSE_DELAY + 6)
    check("and it stands again where it stood",
          [p.get("pos") for p in named(back, "lch") if p.get("newUser") == tgt], [tcell])
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
print("halfa tir OK")
