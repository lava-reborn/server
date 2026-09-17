"""Walking on the global map now stops at the mountains.

The client is told a velocity and nothing else (GlobalMap.moveAck ->
MapObject.startMove), extrapolates from its own figure and never asks again,
so the ground is entirely the server's to keep: move_on_map cuts the leg at
the first cell world.passable refuses and times the arrival there, and a move
with nowhere to go is answered with the frame an arrival uses -- userMove for
id 0 with zero speed, which is the only thing that both puts the figure back
and stops it.

Where the walls are comes from data/map_terrain.json, so this test looks up
the cells it needs rather than naming them: refining the thresholds moves the
rock about, but not what the server does when a walker meets it.

    wsl.exe -e python3 server/test_terrain_move.py
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


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts                                                  # noqa: E402
import world                                                     # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB)
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
# A pipe nobody reads fills at 64 KB and the server blocks on its own log
# mid-frame; drain it as it comes, as the other socket tests do.
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
    """The socket, and whatever it has to say within a while.

    Reading here is quarter-second sips rather than one long blocking read:
    the map answers on a timer -- moveAck now, the arrival three seconds
    later -- so a read that gives up on the first socket timeout would miss
    the half of the exchange this test is about.
    """
    QUIET = 0.25

    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(self.QUIET)
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=2.0):
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                if self.buf.endswith(b"\x00"):
                    break               # a quiet moment after a whole frame
                continue
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]

    def names(self, wait=2.0):
        return [f.split(";")[0] for f in self.frames(wait)]


def param(frame_text, key):
    return frame_text.split(";%s=" % key)[1].split(";")[0]


def enter(c):
    got = c.frames(wait=2)
    check("positioned", got[0].split(";")[0], "lenter")


def goto(c, gx, gy):
    """Stand on a map cell: into its location, then out onto the map."""
    c.send("userMsg;entry=@/goto %d %d@;group=0;" % (gx, gy))
    got = c.frames()
    check("/goto %d %d opens the cell" % (gx, gy),
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    c.send("lenter;accept=1;")
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("and the map opens on it", [f.split(";")[0] for f in got],
          ["cmdAck", "gmap", "marks"])
    return got[1]


def wall_spot():
    """An open cell with rock to the west of it and room to its east.

    Found rather than named: the table is a reconstruction and its walls move
    when its thresholds are refined, but there is always a mountain within
    sight of the market.
    """
    for gy in range(1700, 1780):
        for gx in range(5900, 6100):
            if (world.passable(gx, gy) and not world.passable(gx - 1, gy)
                    and all(world.passable(gx + d, gy) for d in (1, 2))):
                return gx, gy
    raise SystemExit("no wall anywhere near the start: the table is wrong")


# The valley the player who walked it remembers as closed, and its market.
NUBIA = (6250, 6285, 1810, 1845)
VALLEY_CELL = (6268, 1825)

try:
    WALL_X, WALL_Y = wall_spot()
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    check("login", c.names(), ["hello", "cmdAck", "constants", "accountInfo"])
    c.send("newPers;res=1;sex=0;name=@walker@;")
    check("character made", c.names(), ["cmdAck"])
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    enter(c)

    # --- open ground still works the way it did ----------------------------
    c.send("chWorld;")
    got = c.frames()
    check("on the map at the start", [f.split(";")[0] for f in got],
          ["cmdAck", "gmap", "marks"])
    check("standing on the market's cell", "x=5970;y=1730;" in got[1], True)
    c.send("moveTo;dy=0;dx=100;")
    got = c.frames()
    check("a step east is acknowledged with a velocity and nothing else",
          [f.split(";")[0] for f in got], ["moveAck"])
    check("eastwards", float(param(got[0], "vx")) > 0, True)
    got = c.frames(wait=6)
    check("and the arrival is confirmed a cell on",
          [f.split(";")[0] for f in got], ["userMove"])
    check("at rest, where it was aimed",
          (param(got[0], "dx"), param(got[0], "vx"), param(got[0], "vy")),
          ("5971", "0", "0"))

    # --- into a mountain: stopped in front of it ---------------------------
    print("  ..  the nearest mountain: %d,%d, open ground to its east"
          % (WALL_X - 1, WALL_Y))
    goto(c, WALL_X + 1, WALL_Y)
    c.send("moveTo;dy=0;dx=-1000;")
    got = c.frames()
    check("a leg into the mountain is acknowledged, it is the client that walks",
          [f.split(";")[0] for f in got], ["moveAck"])
    check("westwards", float(param(got[0], "vx")) < 0, True)
    got = c.frames(wait=6)
    check("and the server stops it early, on its own timer",
          [f.split(";")[0] for f in got], ["userMove"])
    stopped = float(param(got[0], "dx"))
    check("just inside the last open cell, not in the rock",
          WALL_X <= stopped < WALL_X + 0.1, True)
    check("at rest, and not moved off its row",
          (param(got[0], "vx"), param(got[0], "vy"), param(got[0], "dy")),
          ("0", "0", str(WALL_Y)))

    # --- and the next step is refused where it stands ----------------------
    c.send("moveTo;dy=0;dx=-1000;")
    got = c.frames(wait=2)
    check("a move with nowhere to go gets no velocity at all",
          [f.split(";")[0] for f in got], ["userMove"])
    check("only the frame that puts the figure back and stops it",
          (float(param(got[0], "dx")), param(got[0], "vx"), param(got[0], "vy")),
          (stopped, "0", "0"))
    # The refusal must not have put anything on the client's ack queue.
    c.send("chkml;mode=0;")
    check("the queue is still in step", c.names(), ["cmdAck", "lsml"])
    # And the server's own idea of where the player is agrees with the frame.
    c.send("chWorld;")
    got = c.frames()
    check("walking into the map from there enters the cell in front of the wall",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "g_id=%d;" % world.pack(WALL_X, WALL_Y) in got[1], True)
    c.send("lenter;accept=1;")
    enter(c)

    # --- the Nubian valley is walled in ------------------------------------
    goto(c, *VALLEY_CELL)
    c.send("moveTo;dy=0;dx=-2000;")
    got = c.frames()
    check("a run west out of the valley starts",
          [f.split(";")[0] for f in got], ["moveAck"])
    got = c.frames(wait=8)
    check("and ends against the valley's own rim",
          [f.split(";")[0] for f in got], ["userMove"])
    out = float(param(got[0], "dx"))
    check("still inside the valley, twenty cells short of where it was aimed",
          NUBIA[0] <= out <= VALLEY_CELL[0], True)
    check("stopped there", param(got[0], "vx"), "0")

    # --- a walker standing on rock is not trapped on it --------------------
    # A location's side exit hands out the neighbouring cell without asking
    # the ground, so a player can end up standing on a mountain; the first
    # move then carries them off it (travel.walk).
    rock = (WALL_X - 1, WALL_Y)
    check("the cell west of the wall really is rock", world.passable(*rock), False)
    goto(c, *rock)
    c.send("moveTo;dy=0;dx=100;")
    got = c.frames()
    check("a move off the rock is allowed",
          [f.split(";")[0] for f in got], ["moveAck"])
    got = c.frames(wait=8)
    check("and lands on open ground", [f.split(";")[0] for f in got], ["userMove"])
    landed = float(param(got[0], "dx"))
    check("east of the rock, on ground the table allows",
          world.passable(landed, WALL_Y), True)

    c.send("logout;")
    c.frames()
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-1500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("terrain OK")
