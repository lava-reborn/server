"""Replay the client's real path from login to standing in a location.

The sequence and the frame shapes come from lol/core/Session.as,
lol/core/player/PersGenerator.as and lol/core/Master.as.
"""
import os
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 19776
ENC = "utf-8"

# This test walks the character-creation path, so it needs the empty
# roster; the server otherwise ships a ready character and auto-enters.
# A throwaway database per run, with one account registered in it: the server
# now refuses any digest it does not know, so the test has to own a real one.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB)

srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

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
        """Collect whatever arrives within the window, as decoded strings."""
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


try:
    c = Client(connect())

    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    check("login sequence", c.names(),
          ["hello", "cmdAck", "constants", "accountInfo"])

    # A character is created, then the client plays its intro and sends
    # actPlayer of its own accord.
    c.send("newPers;res=1;sex=0;name=@polestvr@;")
    check("newPers acked", c.names(), ["cmdAck"])

    c.send("actPlayer;")
    check("actPlayer opens a location", c.names(), ["cmdAck", "lcall"])

    # ie=0 in lcall means the client confirms once its assets have loaded.
    # The location's own inhabitants follow immediately, one lch frame each.
    c.send("lenter;accept=1;")
    got = c.frames()
    names = [f.split(";")[0] for f in got]
    check("lenter acked then positioned", names[:2], ["cmdAck", "lenter"])
    check("spawn cell sent", "pos=" in got[1], True)
    check("inhabitants placed", names.count("lch") > 0, True)
    # each placement is followed immediately by that inhabitant's details
    check("described alongside placement",
          names.count("lch") == len([n for n in names if n.startswith("userInfo")]),
          True)
    first_npc = [f for f in got if f.startswith("lch")][0]
    check("inhabitant carries a class", "rtype=" in first_npc, True)

    # Their details are pulled one at a time with getInfo type=1.
    npc_id = int(first_npc.split("newUser=")[1].split(";")[0])
    c.send("getInfo;lvl=0;id=%d;type=1;" % npc_id)
    got = c.frames()
    check("inhabitant described", got[0].split(";")[0].startswith("userInfo"), True)
    # res must be the numeric type id: the client looks the record up by it in
    # its own copy of mobs.xml and reads the art folder off that. Sending the
    # folder or the name instead leaves the creature undrawn.
    res = got[0].split("res=")[1].split(";")[0]
    check("art keyed by numeric type id", res.isdigit(), True)

    # userInfo_Player carries a parameter literally called "name"; an earlier
    # version of send() collided with it and dropped the connection.
    c.send("getInfo;lvl=0;id=0;type=0;")
    got = c.frames()
    check("getInfo answered", [f.split(";")[0] for f in got],
          ["userInfo_Player", "usrUp"])
    check("name survives the collision", "name=@polestvr@;" in got[0], True)

    c.send("rp_get_info;")
    got = c.frames()
    check("rp_info answered", got[0].split(";")[0], "rp_info")
    check("attribute mask is dense", "a_attribs_mask=31;" in got[0], True)
    check("15 specialisation slots", "a_specs_mask=32767;" in got[0], True)

    # These two are pipelined by the client and wedge it if left unanswered,
    # so an empty reply still has to arrive.
    c.send("ss_get;target=0;slot=11;")
    c.send("q_list;")
    check("empty inventory and quest log", c.names(), ["ss_ack", "q_list"])

    # Nothing moves until the server echoes the path back.
    c.send("moveTo;path=|490|491|492|;")
    got = c.frames()
    check("movement echoed", got[0], "userMove;id=0;path=|490|491|492|;")

    # An unknown command must be logged, not fatal.
    c.send("no_such_command;x=1;")
    c.send("q_list;")
    check("unknown command is survivable", c.names(), ["q_list"])


    # --- a trader's stock -------------------------------------------------
    # The price list rides in userInfo as type_list, and the client refers to a
    # purchase by its index in that list rather than by the item's own id.
    c.send("getInfo;lvl=0;id=105;type=1;")
    got = c.frames()
    trader = got[0]
    check("trader carries a price list", "type_list=|" in trader, True)
    first = int(trader.split("type_list=|")[1].split("|")[0])

    c.send("ss_create;s_type=1;target=105;")
    check("trade session opens", c.names(), ["cmdAck"])

    # ItemFactory keeps five of these in flight and frees a slot only when the
    # answer lands, so an unanswered one leaves the shop empty for good.
    c.send("ss_get_si;type=%d;" % first)
    got = c.frames()
    check("item described", got[0].split(";")[0], "ss_si_firearm")
    check("described item is the one asked for",
          "type=%d;" % first in got[0], True)
    # Fields the client divides by: a zero in either is a broken item, not a
    # weak one.
    check("range is non-zero", "max_range=|0|" not in got[0], True)
    check("target size is non-zero", "target_size=|0|" not in got[0], True)
    # fire_mods doubles as the burst length, and at least one mode must be on.
    modes = got[0].split("fire_mods=|")[1].split("|;")[0].split("|")
    check("at least one fire mode enabled", any(m != "0" for m in modes), True)

    # --- the global map ---------------------------------------------------
    c.send("chWorld;")
    got = c.frames()
    check("leaving for the map", [f.split(";")[0] for f in got],
          ["cmdAck", "gmap"])
    check("map position sent", "x=5970;y=1730;" in got[1], True)

    # The same command goes both ways: the client's map and location screens
    # both call changeWorld with no argument, so the direction is decided here.
    c.send("chWorld;")
    got = c.frames()
    check("button toggles back into the location",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    # and the cell the settlement occupies rides packed into g_id
    check("map cell packed into g_id", "g_id=48907970;" in got[1], True)
    c.send("lenter;accept=1;")
    c.frames()
    c.send("chWorld;")
    c.frames()

    # Offsets there are hundredths of a cell. moveAck only sets a velocity, so
    # the client extrapolates and the server has to time the arrival itself and
    # confirm it with a zero-speed frame.
    c.send("moveTo;dy=0;dx=-100;")
    got = c.frames()
    check("travel acknowledged", got[0].split(";")[0], "moveAck")
    check("velocity not position", "vx=" in got[0] and "dx=" not in got[0], True)

    got = c.frames(wait=5)
    check("arrival confirmed", got and got[0].split(";")[0] == "userMove", True)
    check("stopped on arrival", "vx=0;vy=0;" in got[0], True)
    check("moved one cell west", "dx=5969;" in got[0], True)

    # Coming back onto the settlement must NOT pull the player in: a cell is
    # wide enough that any short hop near one would land inside it, and the
    # map would be impossible to stay on.
    c.send("moveTo;dy=0;dx=100;")
    c.frames()
    got = c.frames(wait=6)
    names = [f.split(";")[0] for f in got]
    check("returning does not enter by itself", names, ["userMove"])

    # The button does it, and only while standing on the settlement.
    c.send("chWorld;")
    got = c.frames()
    check("button enters from the settlement",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])

    c.send("logout;")
finally:
    srv.terminate()
    out = srv.communicate(timeout=5)[0]
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-1500:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("world entry OK")
