"""Walking out of a location the way the game meant it: through an exit.

The sequence is the exit window's (lol/gpui/ExitLocationInterface.as ->
Location.exitLoc -> Master.changeWorld(1)): the walker stops on a zone cell,
the "other location" button sends chWorld;to=1, and the client expects
cmdAck;res=0 followed by an lcall it will then confirm with lenter. Which
exit and where it leads is the server's to know (recon/analysis/world.md
§5); the tests pin the rules travel.py recovered: a side leads to the
neighbouring map cell and arrives at the opposite edge, a door follows
data/exits.json or is refused, and past the map's edge lies a deadloc whose
one exit faces back. Map bookmarks (GlobalMap.marks/addMark/editMark/
removeMark) and the way home (on_conv;op=0, then go_home) ride along.
"""
import os
import socket
import subprocess
import tempfile
import sys
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
import accounts
import travel
import world
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB)

# The server's log goes to a file, not a pipe. This replay walks into the
# market half a dozen times, and each entry logs the whole snapshot, some
# 25 KB of userInfo frames; a pipe nobody reads until the end fills at 64 KB
# and the server then blocks on its own logging, mid-frame, until terminate.
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)

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
        return [f.decode(ENC) for f in out if f]

    def names(self, wait=0.5):
        return [f.split(";")[0] for f in self.frames(wait)]


def param(frame_text, key):
    return frame_text.split(";%s=" % key)[1].split(";")[0]


def enter(c):
    """lenter;accept=1 and the frames that follow: (lenter frame, all)."""
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    check("positioned", got[0].split(";")[0], "lenter")
    return got[0], got


def stand_on(c, cell):
    """Walk onto a cell: the server only checks the path's shape, and the
    exit window opens when the walker stops on a zone cell."""
    c.send("moveTo;path=|%d|;" % cell)
    check("stood on %d" % cell, c.names(), ["cmdAck", "userMove"])


def goto(c, what):
    c.send("userMsg;entry=@/goto %s@;group=0;" % what)
    got = c.frames()
    check("/goto %s opens a location" % what,
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    return got[1]


def exit_cell(loc, side):
    """An exit cell of the given side, nearest the middle of that edge."""
    cells = [c for c, s in travel.exit_sides(loc).items() if s == side]
    mx, my = travel._edge_middle(loc, side) if side in travel.SIDES else (0, 0)
    return min(cells, key=lambda c: (c % loc.width - mx) ** 2
                                    + (c // loc.width - my) ** 2)


CELL_102 = world.pack(5970, 1730)          # the black market's own cell
EAST_OF_102 = world.pack(5971, 1730)       # open desert
EDGE = world.pack(6305, 1730)              # the last cell before the border
BEYOND = world.pack(6306, 1730)            # one past it
DEADLOC_W = travel.deadloc_id(travel.W)    # exit on the west, facing back in

try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    check("login", c.names(), ["hello", "cmdAck", "constants", "accountInfo"])
    c.send("newPers;res=1;sex=0;name=@wanderer@;")
    check("character made", c.names(), ["cmdAck"])
    c.send("actPlayer;")
    got = c.frames()
    check("called into the market", "id=102;" in got[1], True)
    _, frames = enter(c)
    commoners = [int(param(f, "newUser")) for f in frames
                 if f.startswith("lch") and "rtype=4;" in f]
    check("the market has someone to register a home with",
          len(commoners) > 0, True)

    # --- a side exit ---------------------------------------------------------
    # Cell 638 is (62, 9) of the 64-wide market, coded 3 = east in outzones.
    market = world.location(102)
    check("cell 638 of 102 is an eastern exit",
          travel.side_at(market, 638), travel.E)
    stand_on(c, 638)
    c.send("chWorld;to=1;")
    got = c.frames()
    check("the exit is acknowledged, then the next location called",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    check("and accepted", got[0], "cmdAck;res=0;")
    check("east of the market is the desert cell 5971,1730",
          "id=%d;" % EAST_OF_102 in got[1], True)
    check("standing on that cell", "g_id=%d;" % EAST_OF_102 in got[1], True)
    lenter, _ = enter(c)
    desert = world.location(EAST_OF_102)
    pos = int(param(lenter, "pos"))
    check("arrived at the western edge, having come from the west",
          pos % desert.width <= travel.EDGE_BAND, True)
    check("on a cell one can stand on", pos in desert.obstacles, False)
    check("and not on the exit itself", travel.side_at(desert, pos), None)

    # and back the same way
    stand_on(c, exit_cell(desert, travel.W))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("west again leads back into the market",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=102;" in got[1], True)
    check("on the market's cell", "g_id=%d;" % CELL_102 in got[1], True)
    lenter, _ = enter(c)
    pos = int(param(lenter, "pos"))
    check("arriving at the market's eastern edge",
          market.width - 1 - pos % market.width <= travel.EDGE_BAND, True)

    # The button is a toggle only without to=: with it, never the map.
    stand_on(c, 638)
    c.send("chWorld;")
    got = c.frames()
    check("without to= the same cell still leads to the map",
          [f.split(";")[0] for f in got], ["cmdAck", "gmap", "marks"])
    c.send("chWorld;")
    c.frames()
    enter(c)

    # --- doors -------------------------------------------------------------
    # 671 "Особняк Барона" has one door, b, and the wiki says it leads to
    # 1038 (confidence high); 1038's door a leads back.
    lcall = goto(c, "671")
    check("in the mansion", "id=671;" in lcall, True)
    enter(c)
    stand_on(c, 4454)
    c.send("chWorld;to=1;")
    got = c.frames()
    check("a door with a known far side opens it",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=1038;" in got[1], True)
    check("an interior keeps the map cell it was reached from",
          "g_id=%d;" % CELL_102 in got[1], True)
    lenter, _ = enter(c)
    inner = world.location(1038)
    pos = int(param(lenter, "pos"))
    check("standing inside, off the exits",
          pos in inner.obstacles or travel.side_at(inner, pos) is not None,
          False)
    stand_on(c, 3808)
    c.send("chWorld;to=1;")
    got = c.frames()
    check("and its own door leads back",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=671;" in got[1], True)
    enter(c)

    # 1000 "Штаб": a door nobody has traced. Refused with a word in chat;
    # the client returns to its previous state on any non-zero res.
    goto(c, "1000")
    enter(c)
    stand_on(c, 1320)
    c.send("chWorld;to=1;")
    got = c.frames()
    check("an untraced door is refused, not guessed",
          [f.split(";")[0] for f in got], ["cmdAck", "userMsg"])
    check("with a non-zero res", got[0] != "cmdAck;res=0;", True)
    check("and the reason in the chat the player has open",
          "group=0;" in got[1] and "nick=@Сервер@;" in got[1], True)
    # exactly one acknowledgement: the queue must not have moved
    c.send("chkml;mode=0;")
    check("the queue is still in step", c.names(), ["cmdAck", "lsml"])

    # Not on an exit at all: also refused, also one ack.
    hq = world.location(1000)
    stand_on(c, next(cell for cell in hq.entries if cell not in hq.obstacles
                     and travel.side_at(hq, cell) is None))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("to=1 off any exit is refused",
          [f.split(";")[0] for f in got], ["cmdAck", "userMsg"])
    c.send("userMsg;entry=@/where@;group=0;")
    got = c.frames()
    check("still in the same location", "static/1000.xml" in got[1], True)

    # --- the edge of the world ------------------------------------------------
    lcall = goto(c, "6305 1730")
    check("on the last cell before the border", "id=%d;" % EDGE in lcall, True)
    enter(c)
    border = world.location(EDGE)
    stand_on(c, exit_cell(border, travel.E))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("east of the border is a wall of rock",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % travel.rock_for(travel.E, 6305, 1730) in got[1], True)
    rock = world.location(travel.rock_for(travel.E, 6305, 1730))
    check("one of the border scenes the client ships",
          (rock.title, rock.fn.startswith("B_")), ("Скалы", True))
    # The cell does not move: the rocks are a dead end entered from the cell
    # the player was standing on, so nothing can be walked around through
    # them and backing out lands where they started.
    g_id = int(param(got[1], "g_id"))
    check("standing on the same map cell", g_id & 0x3FFFFFF,
          (6305 << 13) | 1730)
    check("an ordinary location, not a sub-location", g_id >> 26, 0)
    lenter, frames = enter(c)
    pos = int(param(lenter, "pos"))
    check("arriving over the edge one came in by",
          pos % rock.width >= rock.width - 8, True)
    check("nobody lives there", any(f.startswith("lch") for f in frames), False)

    # The hotkey can still ask for the map (LocationInterface.toGlobal does
    # not look at isSubLocation): that lands on the border cell, not beyond.
    c.send("chWorld;")
    got = c.frames()
    check("the map from beyond its edge",
          [f.split(";")[0] for f in got], ["cmdAck", "gmap", "marks"])
    check("puts the player on the last cell of the map",
          "x=6305;y=1730;" in got[1], True)
    c.send("chWorld;")
    got = c.frames()
    check("which opens the border desert again", "id=%d;" % EDGE in got[1], True)
    enter(c)
    stand_on(c, exit_cell(border, travel.E))
    c.send("chWorld;to=1;")
    c.frames()
    enter(c)

    # The rocks are a dead end: whichever way they let a player walk, to=1
    # takes them back to the place the cell holds.
    rock = world.location(travel.rock_for(travel.E, 6305, 1730))
    side = next((sd for sd in travel.SIDES
                 if any(travel.side_at(rock, cell) == sd
                        for cell in range(rock.width * rock.height))), None)
    check("the rocks do have a way to walk out of", side is not None, True)
    stand_on(c, exit_cell(rock, side))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("and it leads back to the border cell",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % EDGE in got[1], True)
    check("as an ordinary cell again", "g_id=%d;" % EDGE in got[1], True)
    enter(c)

    # --- marks ---------------------------------------------------------------
    c.send("chWorld;")
    got = c.frames()
    check("no marks yet", got[2], "marks;dxdy=|;title=|;info=|;")
    # GlobalMap.addMark: offsets from the player's own figure, whole cells;
    # the client appends its copy only on res=0.
    c.send("insMark;info=@мобы@;title=@Лагерь@;dy=-2;dx=3;")
    check("a mark is accepted", c.frames(), ["cmdAck;res=0;"])
    c.send("insMark;info=@@;title=@Колодец@;dy=1;dx=1;")
    check("and another", c.frames(), ["cmdAck;res=0;"])
    # editMark sends without registering a handler: no ack, or it lands on
    # the next command's.
    c.send("updMark;info=@стая@;title=@Лагерь мобов@;id=0;")
    check("an edit is not acknowledged", c.frames(), [])
    c.send("chWorld;")
    c.frames()
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("the list comes back with every gmap, in order, edited",
          got[2], "marks;dxdy=|3|-2|1|1|;title=|@Лагерь мобов@|@Колодец@|;"
                  "info=|@стая@|@@|;")
    # removeMark: id is the index in the client's array, which splices.
    c.send("rmMark;id=0;")
    check("a removal is acknowledged", c.frames(), ["cmdAck;res=0;"])
    c.send("rmMark;id=5;")
    got = c.frames()
    check("an index that names nothing is refused",
          len(got) == 1 and got[0].startswith("cmdAck;") and got[0] != "cmdAck;res=0;",
          True)
    c.send("chWorld;")
    c.frames()
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("the survivor moved up to index 0",
          got[2], "marks;dxdy=|1|1|;title=|@Колодец@|;info=|@@|;")
    # Offsets follow the player: one cell west, the same mark is one further.
    c.send("moveTo;dy=0;dx=-100;")
    c.frames()
    c.frames(wait=5)
    c.send("chWorld;")
    c.frames()
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("a mark is a place, not an offset",
          got[2], "marks;dxdy=|2|1|;title=|@Колодец@|;info=|@@|;")
    c.send("chWorld;")
    c.frames()
    enter(c)

    # --- home ----------------------------------------------------------------
    # Nothing registered: home is the start.
    goto(c, "183")
    enter(c)
    c.send("userMsg;entry=@/home@;group=0;")
    got = c.frames()
    check("with no home registered, /home is the start",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=102;" in got[1] and "g_id=%d;" % CELL_102 in got[1], True)
    enter(c)
    # on_conv;op=0 at anyone with can_set_home=1 (Attendance.SET_HOME).
    c.send("on_conv;mob=%d;op=0;" % commoners[0])
    check("home registered", c.frames(), ["cmdAck;res=0;"])
    row = accounts.Store(DB).character(1)
    check("with the location and its cell",
          (row["home_loc"], row["home_gx"], row["home_gy"]), (102, 5970, 1730))
    goto(c, "6000 1800")
    enter(c)
    c.send("userMsg;entry=@/home@;group=0;")
    got = c.frames()
    check("home from the desert is the market on its own cell",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=102;" in got[1] and "g_id=%d;" % CELL_102 in got[1], True)
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("and the map cell is the market's", "x=5970;y=1730;" in got[1], True)

    # --- marks survive a relogin ---------------------------------------------
    c.send("logout;")
    c.frames()
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("selPers;num=0;")
    got = c.frames()
    check("back in", [f.split(";")[0] for f in got], ["lcall"])
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    # The well was set 1,1 from the border cell 6305,1730, so it sits on
    # 6306,1731; seen from the market that is 336,1 away.
    check("the marks are the character's, not the socket's",
          got[2], "marks;dxdy=|%d|%d|;title=|@Колодец@|;info=|@@|;"
                  % (6306 - 5970, 1731 - 1730))
    c.send("logout;")
except Exception:
    import traceback
    fails.append("the test itself broke:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        out = fh.read()
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    elif fails:
        # What the server was told and what it did, without the frames.
        story = [l for l in out.splitlines() if "C->S" in l or "  ..  " in l]
        fails.append("server log, commands and notes:\n" + "\n".join(story[-40:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("travel OK")
