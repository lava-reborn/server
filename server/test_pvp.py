"""Two players shooting at each other, and the places where they may not.

The client decides nothing here: ItemActivator.fire refuses a peaceful
location on its own, but a modified one would not, so every rule is the
server's. Two of them are being held to:

  * a blow lands on another player only where the location says pvp="1"
    (world.Location.pvp, off the location's own XML -- 828 of the 1353
    static files carry it, and the wasteland tiles do not);
  * a duel holds both of its sides, the one who opened it as much as the one
    who was struck, or every exchange would end the moment it went badly.

The second rule is the other half of the one test_combat checks from the
mob's side: what shuts the way out is being fought, not having fired.
"""
import os
import threading
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# Свалка Вади-Хальфы: pvp="1" war="1" in its own XML, and the suites already
# use it for fighting. The black market (102) is the peaceful half of the
# comparison -- war="0" there, and nothing may be fired at all.
DUMP = 100
MARKET = 102


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts   # noqa: E402
import mobs       # noqa: E402
import progression  # noqa: E402
import rooms      # noqa: E402
import world      # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("hunter", "secret")
_store.register("quarry", "secret")
_store.close()
CRED_A = accounts.credential("hunter", "secret")
CRED_B = accounts.credential("quarry", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


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
        self.s.settimeout(2)
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
        """Everything up to and including the first frame of that name."""
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


def enter(c, cred, nick):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return int(param(named(got, "lenter")[0], "pos"))


def goto(c, loc):
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until("lcall")
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    return int(param(named(got, "lenter")[0], "pos"))


def entity(eid):
    """An ss_use target: one hex digit of type (1 = entity, 0 = a hex of the
    floor) and the id padded to eight (MDString.createBigUINT)."""
    return "x1%08x" % eid


try:
    a = Client(connect())
    b = Client(connect())
    enter(a, CRED_A, "hunter")
    enter(b, CRED_B, "quarry")

    # A player's entity id is their character id plus the register's base
    # (rooms.player_id), and the two characters were created in this order,
    # so there is nothing to discover by listening.
    pid_a, pid_b = rooms.player_id(1), rooms.player_id(2)

    # --- the peaceful half: the market refuses a blow at all ----------------
    # The hunter settles first, so the quarry's arrival is announced to them
    # rather than being listed in a snapshot taken before it happened.
    goto(a, MARKET)
    a.frames(1.0)
    goto(b, MARKET)
    got = a.frames(1.5)
    check("they stand in the market together",
          [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f],
          [pid_b])
    b.frames(1.0)

    a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_b))
    got = a.frames(1.0)
    check("a blow in a peaceful location is refused",
          [param(f, "res") for f in named(got, "cmdAck")], ["3"])
    check("and nothing is thrown", named(got, "faAim") + named(got, "caHit"), [])

    # --- the dump: pvp="1", and the blow lands -------------------------------
    # The hunter goes first and is already standing there when the quarry
    # walks in, so the arrival is announced to the hunter rather than listed
    # in a snapshot taken before it happened.
    pos_a = goto(a, DUMP)
    a.frames(1.0)
    pos_b = goto(b, DUMP)
    got = a.frames(1.5)
    check("the hunter is told the quarry walked into the dump",
          [int(param(f, "newUser")) for f in named(got, "lch") if "newUser" in f],
          [pid_b])
    b.frames(1.0)

    # A fist reaches one hex and no further, and a cell is not adjacent to
    # itself -- which is where the two of them are, because Location.
    # entry_cell hands every arrival the same doorway. So the hunter steps
    # off it, and from beside the quarry the blow can actually land.
    loc = world.location(DUMP)
    check("both arrivals land on the same entry cell", pos_a, pos_b)
    spot = next(n for n in progression.hex_neighbours(pos_b, loc.width, loc.height)
                if n not in loc.obstacles)
    a.send("moveTo;path=|%d|%d|;" % (pos_a, spot))
    a.frames(0.5 + mobs.HEX_MS / 1000.0)
    b.frames(0.5)
    check("the hunter is standing next to the quarry",
          mobs.hex_distance(spot, pos_b, loc.width), 1)

    # A bare fist can miss, and does: melee_hit against the other's dodge is
    # a roll like any other. So the claim under test is that a blow between
    # players *can* land, and it is swung until one does or the attempts run
    # out -- ten of them would be a remarkable run of luck to lose.
    # Each swing has to be let finish before the next is thrown: the strike
    # bar runs strike_time from the command to the caHit, and a second ss_use
    # in the meantime cancels the first (Fighter.strike is one timer).
    acks, hits, seen = [], [], []
    for _ in range(10):
        a.send("ss_use;type=16;obj=x0;target=%s;" % entity(pid_b))
        got, end = [], time.time() + 3.0
        while time.time() < end:
            got += a.frames(0.3)
            if named(got, "caHit") or named(got, "caMiss"):
                break
        acks += [param(f, "res") for f in named(got, "cmdAck")]
        hits += named(got, "caHit")
        seen += b.frames(0.3)
        if hits:
            break
    check("a blow between players is accepted where pvp is declared",
          acks[:1], ["0"])
    # A strike is one frame, hit or miss -- no faAim, that is for a firearm.
    check("it lands on the other player",
          [param(f, "target") for f in hits][:1], [str(pid_b)])
    check("with damage on it",
          [int(param(f, "dmg")) + int(param(f, "sdmg")) > 0 for f in hits][:1],
          [True])

    seen += b.frames(0.6)
    check("the struck player sees the war state",
          [f for f in named(seen, "lch") if "ws=1" in f] != [], True)
    check("and their own bar drops",
          [f for f in named(seen, "usrUp") if param(f, "id") == "0"] != [], True)

    # --- neither of them may simply walk out ---------------------------------
    b.send("chWorld;")
    got = b.frames(0.8)
    check("the one who was struck is held",
          [(f.split(";")[0], param(f, "res")) for f in got
           if f.split(";")[0] in ("cmdAck", "gmap", "lcall")],
          [("cmdAck", "39")])
    a.send("chWorld;")
    got = a.frames(0.8)
    check("and so is the one who struck",
          [(f.split(";")[0], param(f, "res")) for f in got
           if f.split(";")[0] in ("cmdAck", "gmap", "lcall")],
          [("cmdAck", "39")])

    a.send("logout;")
    b.send("logout;")
    a.frames(0.3)
    b.frames(0.3)
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("pvp OK")
