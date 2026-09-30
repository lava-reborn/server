"""The Nubian valley as it plays by default: players fight in it.

The owner's call of 2026-09-24 (world.NOOB_VALLEY_SAFE): the valley's open
desert, and the pockets of rock its walls lead into, are wasteland like any
other, and a blow there lands. The original kept the valley peaceful, with
«Арена Нубии» its one place for a fight; LAVA_NOOB_VALLEY_SAFE=1 brings that
back, and test_pvp holds it.
"""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
# The default is what is being held: whatever the shell says, not set.
os.environ.pop("LAVA_NOOB_VALLEY_SAFE", None)

# Open desert inside the valley, between the settlement and the farm.
VALLEY = (6268, 1820)
# Valley desert on the western edge: its W exit ends in a pocket of rock.
WALLED = (6261, 1826)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts     # noqa: E402
import progression  # noqa: E402
import rooms        # noqa: E402
import travel       # noqa: E402
import world        # noqa: E402
from protocol import decode  # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("hunter", "secret")
_store.register("quarry", "secret")
_store.close()
CRED_A = accounts.credential("hunter", "secret")
CRED_B = accounts.credential("quarry", "secret")

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


# --- the rule, in process -------------------------------------------------------
check("the valley is not kept peaceful by default",
      getattr(world, "NOOB_VALLEY_SAFE", None), False)
_loc = world.location(world.pack(*VALLEY))
check("its open desert is open to a fight, as the client reads the template",
      (_loc.file, int(bool(_loc.pvp)), _loc.newbies), ("desert/0001.xml", 1, False))
check("and so are the pockets of rock its walls lead into",
      [travel.newbie_ground(world.location(p), *WALLED) for p in (4, 7, 14, 40)],
      [False] * 4)
check("while its settlements keep what their own files say, the arena open",
      [int(bool(world.location(i).pvp)) for i in (181, 185, 167)], [0, 0, 1])

# --- the server ------------------------------------------------------------------
# Action points refill at once, so no blow below waits on the bar.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_AP_REGEN="25")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True).start()


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

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [f.decode(ENC) for f in parts if f]

    def until(self, name, wait=3.0):
        got = []
        end = time.time() + wait
        while time.time() < end:
            got += self.frames(0.3)
            if any(f.startswith(name + ";") for f in got):
                break
        return got


def param(frame, key):
    for part in frame.split(";")[1:]:
        if part.startswith(key + "="):
            return part[len(key) + 1:]
    return None


def named(frames, name):
    return [f for f in frames if f.startswith(name + ";")]


def parsed(frames, name):
    return [decode(f)[1] for f in named(frames, name)]


def enter(c, cred, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    c.frames(wait=2)


def goto(c, cell):
    c.send("userMsg;entry=@/goto %d %d@;group=0;" % cell)
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return int(param(named(got, "lenter")[0], "pos"))


def entity(eid):
    return "x1%08x" % eid


def swing(c, target, wait=3.0):
    """One blow of the fist, and everything up to its landing or refusal."""
    c.send("ss_use;type=16;obj=x0;target=%s;" % entity(target))
    got, end = [], time.time() + wait
    while time.time() < end:
        got += c.frames(0.3)
        if named(got, "caHit") or named(got, "caMiss") or \
                [f for f in named(got, "cmdAck") if param(f, "res") != "0"]:
            break
    return got


try:
    a = Client(connect())
    b = Client(connect())
    enter(a, CRED_A, "hunter")
    enter(b, CRED_B, "quarry")
    pid_a, pid_b = rooms.player_id(1), rooms.player_id(2)

    # The hunter first, so the quarry's arrival is announced to them; then a
    # step off the doorway they share, to stand beside the quarry.
    goto(a, VALLEY)
    a.frames(1.0)
    pos_b = goto(b, VALLEY)
    got = a.frames(1.5)
    check("both stand in the valley's open desert",
          [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f],
          [pid_b])
    b.frames(1.0)
    spot = next(n for n in progression.hex_neighbours(pos_b, _loc.width, _loc.height)
                if n not in _loc.obstacles)
    a.send("moveTo;path=|%d|%d|;" % (pos_b, spot))
    a.frames(1.0)
    b.frames(0.5)

    got = swing(a, pid_b)
    check("a blow in the valley is taken, not refused",
          [param(f, "res") for f in named(got, "cmdAck")][:1], ["0"])
    check("and it lands or misses as anywhere in the wasteland",
          bool(named(got, "caHit") or named(got, "caMiss")), True)
    check("with no word about newcomers' ground",
          [p["entry"] for p in parsed(got, "userMsg")
           if "новичк" in str(p.get("entry", ""))], [])
    seen = b.frames(1.0)
    check("the one struck is told who by",
          [p["enemy"] for p in parsed(seen, "lch") if "enemy" in p][:1], [pid_a])
finally:
    srv.terminate()
    try:
        srv.wait(5)
    except subprocess.TimeoutExpired:
        srv.kill()

if fails:
    print("\nFAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    print("".join(_log[-40:]))
    sys.exit(1)
print("valley pvp OK")
