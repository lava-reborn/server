"""Walking on the global map: the lake stops it, and the rim is a place.

The client is told a velocity and nothing else (GlobalMap.moveAck ->
MapObject.startMove), extrapolates from its own figure and never asks again,
so the ground is entirely the server's to keep: move_on_map cuts the leg at
the first cell world.passable refuses and times the arrival there, and a move
with nowhere to go is answered with the frame an arrival uses -- userMove for
id 0 with zero speed, which is the only thing that both puts the figure back
and stops it.

Three things refuse a walker: the lake, the mountains the map draws, and the
edge of the world. The first two are read off the same picture and both stop
a leg where it meets them; the edge is a location standing on a cell with no
outzone facing out (data/borders.json), so walking into the rim means walking
into a scene of rocks and finding no way on -- which is what this checks from
the client's side of the socket.

The mountains yield to one thing: a cell some location declares as its own
exit is open however dark the pixels are (data/terrain_repairs.json). The
ring itself, and the walk to all 262 settlements, are checked in
data/test_borders.py.

    wsl.exe -e python3 server/test_terrain_move.py
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


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts                                                  # noqa: E402
import travel                                                    # noqa: E402
import world                                                     # noqa: E402

accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
# /goto, /give and /money are off on a served server and belong to
# the admin panel; this suite uses them to set a scene, so it asks
# for them by name.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730")
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


def shore():
    """An open cell with water to the west of it and room to its east.

    Found rather than named: Lake Nasser is read off the map's own tiles and
    its outline moves a little when the reading is refined, but the lake is
    always a few dozen cells north-west of the market.
    """
    for gy in range(1660, 1760):
        for gx in range(5880, 6100):
            if (world.passable(gx, gy) and world.water(gx - 1, gy)
                    and all(world.passable(gx + d, gy) for d in (1, 2))):
                return gx, gy
    raise SystemExit("no lake anywhere near the start: the table is wrong")


def steps_between(a, b):
    """Cells a walker actually covers, going round whatever is in the way.
    Against the straight-line distance it says whether the map's rock is a
    detour or a wall."""
    prev = {a: None}
    queue = collections.deque([a])
    while queue:
        cur = queue.popleft()
        if cur == b:
            n = 0
            while prev[cur]:
                cur, n = prev[cur], n + 1
            return n
        x, y = cur
        for nb in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nb not in prev and world.passable(*nb):
                prev[nb] = cur
                queue.append(nb)
    return None


# The valley the owner walked, its market, the old market this suite starts
# on, and the eastern rim of the world.
NUBIA = (6250, 6285, 1810, 1845)
MARKET_CELL = (5970, 1730)
VALLEY_CELL = (6268, 1825)
RIM_CELL = (world.MAP_X[1], 1700)

try:
    SHORE_X, SHORE_Y = shore()
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

    # --- into the lake: stopped on its shore -------------------------------
    print("  ..  the lake reaches %d,%d, open ground to its east"
          % (SHORE_X - 1, SHORE_Y))
    goto(c, SHORE_X + 1, SHORE_Y)
    c.send("moveTo;dy=0;dx=-1000;")
    got = c.frames()
    check("a leg into the water is acknowledged, it is the client that walks",
          [f.split(";")[0] for f in got], ["moveAck"])
    check("westwards", float(param(got[0], "vx")) < 0, True)
    got = c.frames(wait=6)
    check("and the server stops it early, on its own timer",
          [f.split(";")[0] for f in got], ["userMove"])
    stopped = float(param(got[0], "dx"))
    check("just inside the last dry cell, not in the water",
          SHORE_X <= stopped < SHORE_X + 0.1, True)
    check("at rest, and not moved off its row",
          (param(got[0], "vx"), param(got[0], "vy"), param(got[0], "dy")),
          ("0", "0", str(SHORE_Y)))

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
    check("walking into the map from there enters the cell on the shore",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "g_id=%d;" % world.pack(SHORE_X, SHORE_Y) in got[1], True)
    c.send("lenter;accept=1;")
    enter(c)

    # --- the Nubian valley: walked out of, round the rock and not through ---
    #
    # The map draws a boulder field immediately west of the valley's market,
    # and since the mountains stop a walker again a run due west is cropped
    # in front of it rather than crossing it. That is the picture being
    # obeyed, and it is not the valley being sealed: the way out costs
    # exactly the straight-line distance, 393 cells to Wadi Halfa against
    # 393 straight, because the outcrop is walked around at no cost.
    #
    # A walker crosses 0.35 of a cell a second, so this leg is a slow twelve
    # seconds even when it is cut short.
    goto(c, *VALLEY_CELL)
    c.send("moveTo;dy=0;dx=-400;")
    got = c.frames()
    check("a run west out of the valley starts",
          [f.split(";")[0] for f in got], ["moveAck"])
    got = c.frames(wait=25)
    check("and it ends", [f.split(";")[0] for f in got], ["userMove"])
    out = float(param(got[0], "dx"))
    check("the run west stops in front of the boulder field, not past it",
          VALLEY_CELL[0] - 4 <= out < VALLEY_CELL[0], True)
    # And the valley is shut, which is the point: the owner drew a wall round
    # it in tools/map_editor.py, because the rest of the world is not ready
    # to be visited yet and the way out is meant to be a quest. So there is
    # no walk from here to the old market at all -- and if one ever appears,
    # the wall has a hole in it.
    check("the valley cannot be walked out of",
          steps_between(VALLEY_CELL, MARKET_CELL), None)

    # --- a walker who ends up in the water is not trapped there -------------
    # A location's side exit hands out the neighbouring cell without asking
    # the ground, and /goto asks nothing at all; the first move then carries
    # them back out (travel.walk).
    wet = (SHORE_X - 1, SHORE_Y)
    check("the cell west of the shore really is water", world.passable(*wet),
          False)
    goto(c, *wet)
    c.send("moveTo;dy=0;dx=100;")
    got = c.frames()
    check("a move out of the water is allowed",
          [f.split(";")[0] for f in got], ["moveAck"])
    got = c.frames(wait=8)
    check("and lands on dry ground", [f.split(";")[0] for f in got],
          ["userMove"])
    landed = float(param(got[0], "dx"))
    check("east of the water, on ground the table allows",
          world.passable(landed, SHORE_Y), True)

    # --- the edge of the world is a scene, not an error ---------------------
    # The rim cell carries one of the client's own "Скалы" files, and that
    # file has no outzone facing out, so there is nothing to walk off.
    goto(c, RIM_CELL[0] - 1, RIM_CELL[1])
    c.send("moveTo;dy=0;dx=1000;")
    got = c.frames()
    check("a run east at the rim starts", [f.split(";")[0] for f in got],
          ["moveAck"])
    got = c.frames(wait=8)
    check("and stops on the last cell of the world",
          [f.split(";")[0] for f in got], ["userMove"])
    edge = float(param(got[0], "dx"))
    check("inside the rim cell, not past it",
          RIM_CELL[0] <= edge < RIM_CELL[0] + 1, True)
    c.send("moveTo;dy=0;dx=500;")
    got = c.frames(wait=2)
    check("and there is nowhere further east to walk",
          [f.split(";")[0] for f in got], ["userMove"])
    check("the figure put back where it stands, at rest",
          (float(param(got[0], "dx")), param(got[0], "vx"),
           param(got[0], "vy")), (edge, "0", "0"))
    c.send("chWorld;")
    got = c.frames()
    rim_loc = world.location(world.location_at(*RIM_CELL))
    check("walking into the rim opens the rocks that stand on it",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % rim_loc.id in got[1], True)
    check("one of the border scenes the client ships",
          (rim_loc.title, rim_loc.fn.startswith("B_")), ("Скалы", True))
    check("an ordinary location on an ordinary cell, not a sub-location",
          (int(param(got[1], "g_id")) >> 26,
           int(param(got[1], "g_id")) & 0x3FFFFFF),
          (0, world.pack(*RIM_CELL)))
    check("with no exit cell facing out of the world",
          travel.E in {s for s in travel.exit_sides(rim_loc).values()
                       if s in travel.SIDES}, False)
    c.send("lenter;accept=1;")
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("and the map puts the player on the rim, not beyond it",
          "x=%d;y=%d;" % RIM_CELL in got[1], True)

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


def _exit_cell_on(loc, side):
    """A cell of this location whose outzone leads that way, or raise."""
    for cell in range(loc.width * loc.height):
        if travel.side_at(loc, cell) == side:
            return cell
    raise LookupError(side)


# --- the valley can be stepped out of, too ---------------------------------
# A location's side exit hands over the neighbouring cell, and it used to be
# stopped by the photograph: six of the valley's exits pointed at cells the
# roughness called rock, so the settlement's own file said "east from here"
# and the server answered with a wall. What a file declares is now honoured.
valley = [(gx, gy) for (gx, gy) in world.settlements()
          if NUBIA[0] <= gx <= NUBIA[1] and NUBIA[2] <= gy <= NUBIA[3]]
check("the valley holds settlements", len(valley) >= 10, True)
walked = []
for gx, gy in valley:
    loc = world.location(world.location_at(gx, gy))
    for side in travel.SIDES:
        try:
            cell = _exit_cell_on(loc, side)
        except LookupError:
            continue
        ex = travel.plan_exit(loc, cell, gx, gy)
        target = travel.neighbour(gx, gy, side)
        # An exit that meets the hand-drawn wall is refused on purpose: the
        # drawing outranks what the file declares (world.passable), and
        # walling the valley in is what it was drawn for.
        if not world.passable(*target):
            continue
        walked.append((ex.gx, ex.gy) == target)
check("every exit the valley's files declare leads to the cell it names",
      (len(walked) >= 20, set(walked)), (True, {True}))

# --- the rocks face the right way ------------------------------------------
# A scene walled on the wrong side leaves the way on open, which is how the
# barrier looked "random" from inside. The wall is the side its outzones
# never touch, and the file names point the other way: B_LeftSide is walled
# on the east.
for _side in travel.SIDES:
    _tile = travel.rock_for(_side, 6000, 1800)
    check("walking %s ends against a wall facing %s" % (_side, _side),
          _side in travel.ROCK_WALL[_tile], True)
    check("and %s is one of the client's border scenes" % _side,
          world.location(_tile).title, "Скалы")
for _h, _v in ((travel.W, travel.N), (travel.W, travel.S),
               (travel.E, travel.N), (travel.E, travel.S)):
    _corner = travel.ROCK_CORNER[(_h, _v)]
    check("the %s%s corner is walled both ways" % (_h, _v),
          set(travel.ROCK_WALL[_corner]), {_h, _v})
# And the pocket a way that runs out ends in opens only backwards.
for _side in travel.SIDES:
    _pocket = world.location(travel.POCKET[_side])
    _open = {s for s in travel.exit_sides(_pocket).values() if s in travel.SIDES}
    check("the pocket for walking %s opens only %s back"
          % (_side, travel.OPPOSITE[_side]), _open, {travel.OPPOSITE[_side]})

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("terrain OK")
