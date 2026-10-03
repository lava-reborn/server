"""Walking out of a location the way the game meant it: through an exit.

The sequence is the exit window's (lol/gpui/ExitLocationInterface.as ->
Location.exitLoc -> Master.changeWorld(1)): the walker stops on a zone cell,
the "other location" button sends chWorld;to=1, and the client expects
cmdAck;res=0 followed by an lcall it will then confirm with lenter. Which
exit and where it leads is the server's to know (recon/analysis/world.md
§5); the tests pin the rules travel.py recovered: a side leads to the
neighbouring map cell and arrives at the opposite edge -- or, where
data/passages.json 'sides' lists it (the quarry's pits), into the interior
beyond, the map cell kept -- a door follows
data/exits.json or is refused, the rim of the world is a cell with rocks
standing on it and no exit facing out, and a way that does run out -- an
exit pointing into the lake -- ends in a pocket the player backs out of.
Map bookmarks (GlobalMap.marks/addMark/editMark/removeMark) and the way home
(on_conv;op=0, then go_home) ride along.
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

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
# /goto, /give and /money are off on a served server and belong to
# the admin panel; this suite uses them to set a scene, so it asks
# for them by name.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730")
# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"

# The server's log goes to a file, not a pipe. This replay walks into the
# market half a dozen times, and each entry logs the whole snapshot, some
# 25 KB of userInfo frames; a pipe nobody reads until the end fills at 64 KB
# and the server then blocks on its own logging, mid-frame, until terminate.
LOG = os.path.join(os.path.dirname(DB), "server.log")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=open(LOG, "w"), stderr=subprocess.STDOUT, text=True)

from testkit import check, fails  # noqa: E402


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
ROW = 1730
LAST_X = world.MAP_X[1] - 1                # the last open cell before the rim
LAST = world.pack(LAST_X, ROW)
RIM_X = world.MAP_X[1]                     # the rim itself, rock standing on it
RIM = world.pack(RIM_X, ROW)
RIM_LOC = world.location_at(RIM_X, ROW)    # one of the ring's "Скалы" files


def shore():
    """A dry cell with the lake to its east, and room to its west.

    Found rather than named: the water is read off the client's map tiles
    and its outline moves a little when the reading is refined.
    """
    for gy in range(1600, 1800):
        for gx in range(5900, 6200):
            if (world.passable(gx, gy) and world.water(gx + 1, gy)
                    and world.passable(gx - 1, gy)):
                return gx, gy
    raise SystemExit("no lake on the map: data/map_terrain.json is wrong")


SHORE = shore()

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
    # Ordinary commoners no longer register homes, even outside a bank.
    homes = [int(param(f, "id")) for f in frames
             if f.startswith("userInfo_Commoner;") and ";can_set_home=1;" in f]
    check("the market's unlisted commoners offer no home registration", homes, [])
    check("and it is not the bank",
          [param(f, "can_set_home") for f in frames
           if f.startswith("userInfo_Commoner;") and ";name=2424;" in f], ["0"])

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

    # --- sides that lead into another interior -------------------------------
    # The quarry's pits have no map cells and open into each other by their
    # sides (data/passages.json 'sides'): the north pit's south side is the
    # centre's north, not the map cell south of wherever the player came in.
    pit, centre = world.location(627), world.location(626)
    check("the table sends the north pit's south side into the centre",
          (travel.side_way(627, travel.S) or {}).get("target_loc_id"), 626)
    check("and names no side of a place it does not list",
          (travel.side_way(102, travel.E), travel.side_way(626, "a")), (None, None))
    goto(c, "627")
    enter(c)
    stand_on(c, exit_cell(pit, travel.S))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("a side the table lists opens the interior beyond it",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=626;" in got[1], True)
    g_id = int(param(got[1], "g_id"))
    check("keeping the map cell, as a door into an interior does, and told a sublocation:"
          " the quarry has no way to the map (data/passages.json 'no_map')",
          (g_id & 0x3FFFFFF, g_id >> 26), (CELL_102, 1))
    lenter, _ = enter(c)
    pos = int(param(lenter, "pos"))
    check("arriving at its northern edge, having come from the north",
          (pos // centre.width <= travel.EDGE_BAND, pos in centre.obstacles), (True, False))
    c.send("chWorld;")
    got = c.frames()
    check("and the map, which the client's buttons no longer offer there, is refused to the"
          " hotkey too: one cmdAck, nothing else", got, ["cmdAck;res=4;"])
    stand_on(c, exit_cell(centre, travel.N))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("and its north side leads back into the pit",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=627;" in got[1], True)
    lenter, _ = enter(c)
    pos = int(param(lenter, "pos"))
    check("arriving at the pit's southern edge",
          pit.height - 1 - pos // pit.width <= travel.EDGE_BAND, True)
    goto(c, "102")
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
    # The rim is a ring of the client's own rock scenes standing on the rim
    # cells themselves (data/borders.json). So walking east off the last open
    # cell is an ordinary step onto the next cell -- and that cell is a place
    # with no exit facing east, which is the only kind of wall LAVA had.
    lcall = goto(c, "%d %d" % (LAST_X, ROW))
    check("on the last open cell before the rim", "id=%d;" % LAST in lcall, True)
    enter(c)
    border = world.location(LAST)
    stand_on(c, exit_cell(border, travel.E))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("east of it stands the rock of the rim",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % RIM_LOC in got[1], True)
    rock = world.location(RIM_LOC)
    check("one of the border scenes the client ships",
          (rock.title, rock.fn.startswith("B_")), ("Скалы", True))
    g_id = int(param(got[1], "g_id"))
    check("standing on the rim cell itself", g_id & 0x3FFFFFF, RIM)
    check("an ordinary location, not a sub-location", g_id >> 26, 0)
    lenter, frames = enter(c)
    pos = int(param(lenter, "pos"))
    # Heading east, the scene is entered over its western edge -- the wall
    # is the far side, the one the player was trying to walk through.
    check("arriving over the edge one came in by", pos % rock.width <= 8, True)
    check("with the wall ahead", travel.E in travel.ROCK_WALL[rock.id], True)
    check("nobody lives there", any(f.startswith("lch") for f in frames), False)
    check("and no cell to stand on to leave the world by",
          any(travel.side_at(rock, cell) == travel.E
              for cell in range(rock.width * rock.height)), False)

    # The map from the rim is the rim, and walking back into it is the rocks.
    c.send("chWorld;")
    got = c.frames()
    check("the map from the rim",
          [f.split(";")[0] for f in got], ["cmdAck", "gmap", "marks"])
    check("puts the player on the last cell of the map",
          "x=%d;y=%d;" % (RIM_X, ROW) in got[1], True)
    c.send("chWorld;")
    got = c.frames()
    check("which opens the rocks again", "id=%d;" % RIM_LOC in got[1], True)
    enter(c)

    # Out of the rocks the way one came: west, onto the cell west of them.
    stand_on(c, exit_cell(rock, travel.W))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("walking west out of the rim is the cell west of it",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % LAST in got[1], True)
    check("as an ordinary cell again", "g_id=%d;" % LAST in got[1], True)
    enter(c)

    # --- a way that runs out: the lake ----------------------------------------
    # Water is the one thing left on the map nobody can enter, and an exit
    # pointing into it gets the scene a dead end deserves: one of the kit's
    # four pockets, open only on the side the player came in over. The map
    # cell does not move, so backing out lands exactly where it started.
    lcall = goto(c, "%d %d" % SHORE)
    check("on the shore of the lake", "id=%d;" % world.pack(*SHORE) in lcall,
          True)
    enter(c)
    beach = world.location(world.location_at(*SHORE))
    stand_on(c, exit_cell(beach, travel.E))
    c.send("chWorld;to=1;")
    got = c.frames()
    pocket = world.location(travel.POCKET[travel.E])
    check("the exit into the water opens a pocket of rock",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % pocket.id in got[1], True)
    check("also one of the border scenes",
          (pocket.title, travel.E), ("Скалы", "E"))
    check("and the map cell has not moved",
          "g_id=%d;" % world.pack(*SHORE) in got[1], True)
    enter(c)
    check("the pocket opens on one side only, the one walked in over",
          {s for s in travel.exit_sides(pocket).values() if s in travel.SIDES},
          {travel.W})
    stand_on(c, exit_cell(pocket, travel.W))
    c.send("chWorld;to=1;")
    got = c.frames()
    check("and backing out of it lands on the cell it was entered from",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=%d;" % world.pack(*SHORE) in got[1], True)
    enter(c)

    # Back to a cell in the middle of nowhere for the marks below.
    goto(c, "6305 1730")
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
    # Said is explicitly listed as a registrar in the residential quarter.
    goto(c, "36")
    _, frames = enter(c)
    said = [f for f in frames if f.startswith("userInfo_Commoner;") and ";name=44;" in f]
    check("Said offers home registration", [param(f, "can_set_home") for f in said], ["1"])
    c.send("on_conv;mob=%d;op=0;" % int(param(said[0], "id")))
    check("home registered", c.frames(), ["cmdAck;res=0;"])
    row = accounts.Store(DB).character(1)
    check("with the location and its cell",
          (row["home_loc"], row["home_gx"], row["home_gy"]), (36,) + world.cell_of(36))
    goto(c, "6000 1800")
    enter(c)
    c.send("userMsg;entry=@/home@;group=0;")
    got = c.frames()
    check("home from the desert is the residential quarter on its own cell",
          [f.split(";")[0] for f in got] == ["cmdAck", "lcall"]
          and "id=36;" in got[1] and "g_id=%d;" % world.pack(*world.cell_of(36)) in got[1], True)
    enter(c)
    c.send("chWorld;")
    got = c.frames()
    check("and the map cell is the quarter's", "x=%d;y=%d;" % world.cell_of(36) in got[1], True)
    # Keep the bookmark scene at its original reference cell.
    goto(c, "102")
    enter(c)

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
    # The well was set 1,1 from the cell 6305,1730 the marks were made on, so
    # it sits on 6306,1731; seen from the market that is 336,1 away.
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
