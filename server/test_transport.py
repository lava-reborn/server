"""Renting a vehicle from a lessor, and riding it across the map.

The sequence is the rental window's (lol/gpui/TransRentInterface.as ->
Rent.getTransport): standing at the desk, userInfo_Lessor lists what it lets
out in give_transport, the factory asks ts_get_si for each type and waits for
a ts_si apiece, and "Арендовать" sends on_conv;op=2;p1=<type>;p2=<days>.
Rent.getTransportAck reads nothing but res, so everything the player then
sees -- the purse, the icon in the corner, the hours left -- rides the
userInfo_Player the server pushes behind the acknowledgement.

What the tests pin: the frame has every field TransObject.initialize reads;
a desk refuses what it does not stock, a stranger's desk and a desk across
the room; money is actually taken and actually required; tr/tr_hours appear
only while the rental runs and survive a relogin; and the map speed moves by
the vehicle's own multiplier, in the velocity and in the arrival alike.

The two timed legs run over the same stretch of desert, once with the donkey
and once after the rental has expired. The velocity is compared exactly; the
arrival, being wall-clock, is bounded rather than divided, because this
machine can stall for a second at a time reading the client's files.
"""
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import progression  # noqa: E402
import transport  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

DB = os.path.join(tempfile.mkdtemp(), "transport.db")
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# The log outgrows a pipe nobody drains: at 64 KB the write blocks and the
# server stops answering mid-test. Drain it as it arrives, like the other sets.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


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
        self.s.settimeout(2)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [decode(f.decode(ENC)) for f in out if f]

    def until(self, name, timeout=15, settle=0.5):
        got = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            got += self.frames(0.3)
            if any(n == name for n, _p in got):
                return got + (self.frames(settle) if settle else [])
        raise RuntimeError("no %s within %ds; got %r"
                           % (name, timeout, [n for n, _p in got]))

    def names(self, wait=0.5):
        return [n for n, _p in self.frames(wait)]


def one(frames, name):
    return next(p for n, p in frames if n == name)


def enter(c):
    """lenter;accept=1 and everything the room sends behind it."""
    c.send("lenter;accept=1;")
    return c.until("lenter", settle=1.5)


def ack(c):
    """Everything up to and including the acknowledgement, however slow.

    Not a fixed window: reading a location's file off the Windows drive can
    stall the server for a second or two under load, and a refusal that
    arrives late is still the refusal being tested.
    """
    return c.until("cmdAck", settle=0)


def walk(c, cell):
    """Stand on a cell. The server checks only the path's shape, so one
    hop is enough to be where the client would have walked to."""
    c.send("moveTo;path=|%d|;" % cell)
    check("stood on %d" % cell,
          [n for n, _p in c.until("userMove", settle=0)], ["cmdAck", "userMove"])


def to_map(c):
    c.send("chWorld;")
    check("out on the map", [n for n, _p in c.until("gmap")][:2],
          ["cmdAck", "gmap"])


def to_location(c):
    c.send("chWorld;")
    c.until("lcall")
    return enter(c)


def goto_cell(c, gx, gy):
    """Stand on a named map cell, through the server's own /goto.

    Both timed legs start here, so they cross the same ground: the mountains
    clip a leg before the speed is ever applied (travel.walk), and two legs
    over different stretches of desert would not be comparable.
    """
    c.send("userMsg;entry=@/goto %d %d@;group=0;" % (gx, gy))
    c.until("lcall")
    return enter(c)


def leg(c, dx):
    """One leg of map travel: (velocity, seconds until the server stops us).

    moveAck carries the velocity the client extrapolates from; the trip is
    over when a userMove with zero speed arrives, which is the server's own
    timer firing. Both have to move together when a vehicle is under the
    player, so both are measured -- and measured here rather than through
    frames(), whose window can block for a whole socket timeout and would
    put seconds of its own into the answer.
    """
    started = time.time()
    c.send("moveTo;dx=%d;dy=0;" % dx)
    vector, stopped = None, None
    c.s.settimeout(0.1)
    try:
        deadline = time.time() + 30
        while time.time() < deadline and stopped is None:
            try:
                chunk = c.s.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                break
            c.buf += chunk
            parts = c.buf.split(b"\x00")
            c.buf = parts.pop()             # keep the unfinished tail
            for raw in parts:
                if not raw:
                    continue
                name, params = decode(raw.decode(ENC))
                if name == "moveAck":
                    vector = params
                elif name == "userMove" and not params.get("vx"):
                    stopped = time.time()
    finally:
        c.s.settimeout(2)
    if vector is None or stopped is None:
        raise RuntimeError("the leg never ended (moveAck=%r)" % (vector,))
    return abs(vector["vx"]), stopped - started


# The black market of Wadi-Halfa, where a new character starts, and its one
# lessor: 653 wh_Lessor, the wiki's Шихаб.
MARKET = world.location(102)
LESSOR_CELL = next(cell for cell, t in MARKET.spawns if t == 653)
FAR_CELL = 0                      # the north-west corner, a long way off
DONKEY, CAMEL, GAZ = 1, 2, 8      # gold-priced, afro-priced, premium-only
# Where both timed legs start, and how far they run: 1.6 cells due east over
# open desert (world.passable is true for 5967..5974 at this row, so the
# mountain clip never shortens either of them).
START_GX, START_GY = 5970, 1730
LEG = 160

try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.until("accountInfo")
    c.send("newPers;res=45676;sex=0;name=@Каюр@;")
    c.until("cmdAck")
    c.send("actPlayer;")
    check("called into the market", one(c.until("lcall"), "lcall")["id"], 102)
    got = enter(c)
    # The market's snapshot is 21 inhabitants and can outrun the settle
    # window on a busy machine; the lessor is the frame this set is about.
    _deadline = time.time() + 20
    while not any(n == "userInfo_Lessor" for n, _p in got) \
            and time.time() < _deadline:
        got += c.frames(0.5)

    # --- the desk ----------------------------------------------------------
    lessor = one(got, "userInfo_Lessor")
    check("the market's lessor is Шихаб, type 653", lessor["res"], 653)
    check("and he lets out the seven the wiki lists",
          lessor["give_transport"], transport.offered_by(653))
    check("which is the donkey-to-airship ladder",
          lessor["give_transport"], [1, 2, 3, 4, 5, 6, 7])
    commoner = next(p["newUser"] for n, p in got
                    if n == "lch" and p.get("rtype") == world.COMMONER)

    # --- ts_get_si ----------------------------------------------------------
    c.send("ts_get_si;type=%d;" % DONKEY)
    got = c.until("ts_si")
    check("ts_get_si is answered with ts_si and nothing else",
          [n for n, _p in got], ["ts_si"])
    si = one(got, "ts_si")
    check("with every field TransObject reads", sorted(si),
          sorted(["type", "speed_mod", "aggro_mod", "g_cost", "cost", "res",
                  "premium", "name", "desc"]))
    check("the type it was asked for", si["type"], DONKEY)
    check("the icon number, which is what the container loads",
          si["res"], DONKEY)
    check("the donkey's own numbers, off the wiki",
          (si["speed_mod"], si["aggro_mod"], si["premium"]), (1.7, 0.85, 0))
    check("priced in gold, a hundredth at a time",
          (si["cost"], si["g_cost"]), (0, 10))
    check("the name is a string id in the preloaded table",
          si["name"], transport.NAME_ID_OFFSET + DONKEY)

    # A type no table knows is still answered: TransportFactory only reopens
    # its five-deep request window when a ts_si arrives.
    c.send("ts_get_si;type=60;")
    check("an unknown type is answered too, not dropped",
          one(c.until("ts_si"), "ts_si")["type"], 60)

    # --- refusals -----------------------------------------------------------
    walk(c, FAR_CELL)
    c.send("on_conv;op=2;mob=%d;p1=%d;p2=1;" % (lessor["id"], DONKEY))
    check("a desk across the room is out of reach",
          ack(c), [("cmdAck", {"res": progression.ERR_TOO_FAR})])

    walk(c, LESSOR_CELL)
    c.send("on_conv;op=2;mob=%d;p1=%d;p2=1;" % (commoner, DONKEY))
    check("a commoner rents nothing",
          ack(c), [("cmdAck", {"res": progression.ERR_NOT_FOUND})])

    # 4 is server.RES_NOT_AVAILABLE, 21 RES_NO_MONEY; spelled out rather than
    # imported, because importing server.py opens a database of its own.
    c.send("on_conv;op=2;mob=%d;p1=%d;p2=1;" % (lessor["id"], GAZ))
    check("nor does this desk stock the Газ 67 Б",
          ack(c), [("cmdAck", {"res": 4})])

    c.send("on_conv;op=2;mob=%d;p1=%d;p2=0;" % (lessor["id"], DONKEY))
    check("nor rent anything for nought days",
          ack(c), [("cmdAck", {"res": 4})])

    c.send("on_conv;op=2;mob=%d;p1=%d;p2=1;" % (lessor["id"], CAMEL))
    check("a newborn cannot afford a camel at 12000 afro a day",
          ack(c), [("cmdAck", {"res": 21})])

    c.send("getInfo;lvl=0;id=0;type=0;")
    info = one(c.until("usrUp"), "userInfo_Player")
    check("and nothing was taken for it",
          (info["afro"], info["gold"]), (progression.START_AFRO, 0))
    check("on foot there is no tr and no tr_hours",
          [k for k in ("tr", "tr_hours") if k in info], [])

    # --- the rental ---------------------------------------------------------
    c.send("userMsg;entry=@/money 0 1000@;group=0;")
    c.until("userMsg")
    c.send("on_conv;op=2;mob=%d;p1=%d;p2=2;" % (lessor["id"], DONKEY))
    got = c.until("cmdAck")
    check("two days of donkey are granted",
          [n for n, _p in got], ["userInfo_Player", "cmdAck"])
    check("with res=0, the only thing Rent.getTransportAck looks at",
          one(got, "cmdAck"), {"res": 0})
    info = one(got, "userInfo_Player")
    check("0.1 G a day, twice, out of the ten put in",
          (info["afro"], info["gold"]), (progression.START_AFRO, 1000 - 20))
    check("the vehicle and the hours arrive with the purse",
          (info["tr"], info["tr_hours"]), (DONKEY, 48))

    # --- and it is faster ---------------------------------------------------
    # The walker's own pace is measured at the end, once the rental has run
    # out, over the same stretch; the two are compared there.
    goto_cell(c, START_GX, START_GY)
    to_map(c)
    ride_v, ride_t = leg(c, LEG)
    to_location(c)

    # --- across a relogin ---------------------------------------------------
    c.send("logout;")
    c.frames()
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.until("accountInfo")
    c.send("selPers;num=0;")
    c.until("lcall")
    enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    info = one(c.until("usrUp"), "userInfo_Player")
    check("the rental is still there after a relogin",
          (info.get("tr"), info.get("tr_hours")), (DONKEY, 48))

    # --- and gone when it runs out ------------------------------------------
    c.send("logout;")
    c.frames()
    db = sqlite3.connect(DB)
    db.execute("UPDATE characters SET transport_until = ?",
               (int(time.time()) - 10,))
    db.commit()
    db.close()

    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.until("accountInfo")
    c.send("selPers;num=0;")
    c.until("lcall")
    enter(c)
    c.send("getInfo;lvl=0;id=0;type=0;")
    info = one(c.until("usrUp"), "userInfo_Player")
    check("an expired rental sends neither key, or the client rides a"
          " transport of type 0",
          [k for k in ("tr", "tr_hours") if k in info], [])

    # --- the same stretch on foot, for the comparison ------------------------
    goto_cell(c, START_GX, START_GY)
    to_map(c)
    foot_v, foot_t = leg(c, LEG)
    check("with the rental gone the map velocity is the walker's again,"
          " and under it the donkey's was exactly its multiplier",
          round(ride_v / foot_v, 3), transport.speed_mod(DONKEY))

    # The velocity above is exact; the arrival is wall-clock, so it is
    # checked as a bound rather than a ratio. What would be wrong is a
    # server that boosts the velocity and leaves the timer on foot: the ride
    # would then take as long as the walk. Each leg is allowed to run late
    # -- the machine can stall for a second under load -- but not early, and
    # the ride has to land inside the time the walk's own timer would have
    # taken.
    ride_ideal, foot_ideal = LEG / 100.0 / ride_v, LEG / 100.0 / foot_v
    print("      rode %.2fs (timer says %.2f), walked %.2fs (timer says %.2f)"
          % (ride_t, ride_ideal, foot_t, foot_ideal))
    check("neither leg beat its own timer",
          ride_t > ride_ideal - 0.1 and foot_t > foot_ideal - 0.1, True)
    check("the ride was over before a walk's timer would have finished",
          ride_t < foot_ideal, True)
    check("and the walk was not quietly boosted too",
          foot_t > ride_ideal + 0.5, True)
    c.send("logout;")
    c.frames()

    db = sqlite3.connect(DB)
    row = db.execute("SELECT transport_type, transport_until"
                     " FROM characters").fetchone()
    db.close()
    check("the expired rental is cleared from the table", row, (None, None))
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("transport OK")
