"""Replay the client's real path from login to standing in a location.

The sequence and the frame shapes come from lol/core/Session.as,
lol/core/player/PersGenerator.as and lol/core/Master.as.
"""
import os
import threading
import socket
import subprocess
import tempfile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
def free_port():
    """A port nobody holds right now.

    Fixed ports made the verdict depend on who else was testing: with two
    checkouts running the suites at once, the second server failed to bind
    and the test talked to the first one's, passing or failing on code it
    was not built from.
    """
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
ENC = "utf-8"

# This test walks the character-creation path, so it needs the empty
# roster; the server otherwise ships a ready character and auto-enters.
# A throwaway database per run, with one account registered in it: the server
# now refuses any digest it does not know, so the test has to own a real one.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
import items
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
# The purse buys one pistol of the black market's stall (102), which sells
# Вади-Хальфа's band, 4-8 (shop_bands.py): its cheapest, a Glock 17, is
# 2800 afro, more than a new character's 1000.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730",
           LAVA_START_AFRO="9000")

# The lines the server says by itself (Session.say) are off on a served
# server; this suite reads them as the server's reasons, so it asks for
# them by name.
env["LAVA_SERVER_CHAT"] = "1"
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


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
    c.send("newPers;res=1;sex=0;name=@Archivist@;")
    check("newPers acked", c.names(), ["cmdAck"])

    c.send("actPlayer;")
    check("actPlayer opens a location", c.names(), ["cmdAck", "lcall"])

    # ie=0 in lcall means the client confirms once its assets have loaded.
    # The location's own inhabitants follow immediately, one lch frame each.
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    names = [f.split(";")[0] for f in got]
    # Kept for later: ids are handed out per room in file order, so which
    # number the pistol stall gets depends on who else stands there.
    entry = list(got)
    # No acknowledgement on success: the client cancels the one it registered
    # as soon as the lenter frame arrives.
    check("positioned without an ack", names[0], "lenter")
    check("spawn cell sent", "pos=" in got[0], True)
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
    check("name survives the collision", "name=@Archivist@;" in got[0], True)
    # Gamer.userInfo hands tr to TransportFactory.create unconditionally, and
    # that builds a vehicle of type 0 and asks for its description. A player
    # on foot has no tr key at all.
    check("no transport reported without one", "tr=" in got[0], False)

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

    # slot=32 (PersEquip.requestPublicTrophy) registers on both the ss_ack
    # and the cmdAck queue and drops the other handler on the first answer.
    # Answering twice would feed the second to the next command's handler.
    c.send("ss_get;target=0;slot=32;")
    check("public trophies answered once, with ss_ack only",
          c.names(), ["ss_ack"])

    # Nothing moves until the server echoes the path back, and every step also
    # registers a handler on the client's acknowledgement queue. That queue is
    # strictly ordered, so an unanswered move hands each later reply to a stale
    # mover and quietly breaks whatever asked for it.
    c.send("moveTo;path=|490|491|492|;")
    got = c.frames()
    check("movement acknowledged", got[0], "cmdAck;res=0;")
    check("movement echoed", got[1], "userMove;id=0;path=|490|491|492|;")

    # A path the server will not take is refused with breakMv INSTEAD of an
    # acknowledgement: Location.breakMv itself skipCalls the handler the
    # move registered, then snaps the walker to pos. A cmdAck as well would
    # be handed to whatever the player does next.
    c.send("moveTo;path=|492|99999|;")
    got = c.frames()
    check("a bad path is refused with breakMv alone",
          got, ["breakMv;id=0;pos=492;"])
    c.send("moveTo;path=|;")
    check("an empty path too", c.frames(), ["breakMv;id=0;pos=492;"])

    # Mail is asked for the moment a location opens, and it expects an
    # acknowledgement of its own.
    c.send("chkml;mode=0;")
    check("mail answered", c.names(), ["cmdAck", "lsml"])

    # A command that registers a handler must be answered even when what it
    # asks makes no sense, or the same desynchronisation follows: a clan
    # question naming no det (clans.py) is refused -- with the clan's own
    # silent 20, never 3, which the client shows as «Сервер не отвечает».
    c.send("gg_info;id=0;")
    got = c.frames()
    check("a clan question with no det: acknowledged", got[0].split(";")[0], "cmdAck")
    check("and refused rather than accepted, with 20", got, ["cmdAck;res=20;"])
    # The auction is implemented now, and an operation that names no
    # auctioneer is still answered by exactly one refusal.
    c.send("ah_op;type=0;obj=x0;target=0;")
    check("ah_op with no auctioneer: one refusal", c.frames(), ["cmdAck;res=3;"])

    # And the reverse: commands the client sends without registering anything
    # must get no acknowledgement at all, or it lands on the next handler.
    # Auction.search waits on ah_sresult, GlobalMap.editMark just sends.
    c.send("ah_search;target=0;page=0;")
    check("ah_search is not acknowledged, only answered on its own queue",
          c.frames(), ["ah_sresult;page=0;count=0;next=0;"])
    c.send("updMark;id=0;title=@a@;info=@b@;")
    check("updMark is not acknowledged", c.frames(), [])
    # bg_op registers for joining (0) and leaving (2) the queue only;
    # BattleGroundManager sends 3..7 bare.
    c.send("bg_op;op=6;ts=1;type=1;")
    check("bg_op info request is not acknowledged", c.frames(), [])
    c.send("bg_op;op=2;ts=1;type=1;")
    check("bg_op leave queue is", c.names(), ["cmdAck"])
    # p_op op=5 asks for the party list from PartyManager.errorReport with
    # no handler; an invite (0) registers Gamer.invitePlayer.
    c.send("p_op;id=0;op=5;")
    check("party list request is not acknowledged", c.frames(), [])
    c.send("p_op;id=7;op=0;")
    check("party invite is", c.names(), ["cmdAck"])

    # An unknown command must be logged, not fatal.
    c.send("no_such_command;x=1;")
    c.send("q_list;")
    check("unknown command is survivable", c.names(), ["q_list"])


    # --- a trader's stock -------------------------------------------------
    # The price list rides in userInfo as type_list, and the client refers to a
    # purchase by its index in that list rather than by the item's own id.
    # The stall is known by the head of its own price list, not by a fixed id:
    # what a pistol stall sells first changed once the guns had names, and
    # again with the city's band (shop_bands.py): the list as the black
    # market (102) of the starting cell has it.
    STALL = items.stock_for(1200, 102)
    head = "type_list=|%d|" % STALL[0]
    trader_id = int(next(f for f in entry if f.startswith("userInfo_Trader")
                         and head in f).split("id=")[1].split(";")[0])
    c.send("getInfo;lvl=0;id=%d;type=1;" % trader_id)
    got = c.frames()
    trader = got[0]
    check("trader carries a price list", "type_list=|" in trader, True)
    first = int(trader.split("type_list=|")[1].split("|")[0])

    c.send("ss_create;s_type=1;target=%d;" % trader_id)
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

    # Buying registers Trade.transferAck; closing the shop (s_status=0) is
    # sent from Trade.close with no handler at all. Acknowledging the close
    # was enough to put the queue off by one for the rest of the session.
    # A real purchase now: the client adds nothing to the bag by itself, so
    # the acknowledgement is followed by the new object, its dynamic info
    # and the purse (userInfo_Player is the only frame carrying money).
    # The first gun priced in afro, not simply the first: the head of the
    # list may be sold for gold only, and the afro code (1) rightly refuses
    # that -- it used to hand gold items over for a price of 0.
    stock = STALL
    buy = next(i for i, t in enumerate(stock)
               if items.root_of(t) == items.FIRE_ARM and items.params_of(t)["cost"] > 0)
    c.send("ss_upd;s_status=1;obj=x%x;param=1;" % buy)
    check("a purchase is acknowledged, then delivered", c.names(),
          ["cmdAck", "ss_obj_status", "ss_di_firearm", "userInfo_Player"])
    c.send("ss_upd;s_status=0;obj=x0;")
    check("closing the shop is not", c.frames(), [])

    # Barter uses the same command with its own numbering, and three of its
    # values go out bare: 2 deny, 5 apply, 6 break. In a trade session the
    # same numbers (sell, gold repair, trophy) do register, so the session
    # decides. A barter needs another player (test_barter has two and three
    # of them); proposed to an inhabitant it is refused -- the cmdAck the
    # proposer waits for, the ss_upd 0 its Barter needs to die, and why --
    # and what the window may still send after that is answered the way
    # that close left the client's queue.
    c.send("ss_create;s_type=2;target=105;")
    check("a barter with an inhabitant is refused, and the client's Barter closed",
          c.names(), ["cmdAck", "ss_upd", "userMsg"])
    for status in (2, 5, 6):
        c.send("ss_upd;s_status=%d;obj=x0;" % status)
        check("barter s_status=%d is not acknowledged" % status,
              c.frames(), [])
    c.send("ss_upd;s_status=1;obj=x0;")
    check("barter agree is", c.names(), ["cmdAck"])
    c.send("ss_upd;s_status=0;obj=x0;")
    check("barter close is not", c.frames(), [])

    # --- the global map ---------------------------------------------------
    c.send("chWorld;")
    got = c.frames()
    # Master.gmap builds a fresh GlobalMap each time, and its mark list only
    # exists once GlobalMap.marks() has run, so every gmap is followed by a
    # marks frame, empty or not.
    check("leaving for the map", [f.split(";")[0] for f in got],
          ["cmdAck", "gmap", "marks"])
    check("map position sent", "x=5970;y=1730;" in got[1], True)
    check("marks initialised", got[2], "marks;dxdy=|;title=|;info=|;")

    # The same command goes both ways: the client's map and location screens
    # both call changeWorld with no argument, so the direction is decided here.
    c.send("chWorld;")
    got = c.frames()
    check("button toggles back into the location",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    # and the cell the settlement occupies rides packed into g_id
    check("map cell packed into g_id", "g_id=48907970;" in got[1], True)
    c.send("lenter;accept=1;")
    c.frames(wait=2)
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

    # The button does it, and it opens whatever is under the player.
    c.send("chWorld;")
    got = c.frames()
    check("button enters the cell under the player",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    check("on this cell that is the settlement", "id=102;" in got[1], True)
    c.send("lenter;accept=1;")
    c.frames(wait=2)

    # --- the wilderness ---------------------------------------------------
    # A cell with no settlement is still somewhere to go: the client resolves
    # it to a desert tile from the cell's own coordinates, so the map has no
    # holes in it and no table has to exist for a cell to lead anywhere.
    c.send("chWorld;")
    c.frames()
    c.send("moveTo;dy=0;dx=-100;")
    c.frames()
    c.frames(wait=5)
    c.send("chWorld;")
    got = c.frames()
    check("an empty cell can be entered too",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    wild = (5969 << 13) | 1730
    check("wilderness is its own location id", "id=%d;" % wild in got[1], True)
    check("standing on the cell it was entered from",
          "g_id=%d;" % wild in got[1], True)
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    # The tile's file lists one inhabitant, and it is a clan-event trader
    # (VOV_T001 and friends): the wasteland templates were reused for events.
    # world.belongs_here keeps such entries out, so the desert opens empty
    # until the combat code spawns creatures of its own.
    check("the wasteland opens without the event vendors from its file",
          any(f.startswith("lch") for f in got), False)

    # Leaving goes back to that cell, not to wherever the session started.
    c.send("chWorld;")
    got = c.frames()
    check("leaving returns to the cell walked in from",
          "x=5969;y=1730;" in got[1], True)

    # --- travel by name ---------------------------------------------------
    # Most of the 1381 locations are interiors the map cannot reach: an
    # outzone says only that leaving is possible here, never where to, and
    # the destination lived in the stripped serverdata node.
    c.send("userMsg;entry=@/goto 183@;group=0;")
    got = c.frames()
    check("goto is acknowledged, then opens the location",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    check("the named location opened", "id=183;" in got[1], True)

    # Ids above the wilderness range resolve to no file at all, and saying so
    # must not cost the connection.
    c.send("userMsg;entry=@/goto %d@;group=0;" % (1 << 26))
    got = c.frames()
    check("an id with no file behind it is refused, not fatal",
          [f.split(";")[0] for f in got], ["cmdAck", "userMsg"])

    # The answer must come back on the channel the question was asked in.
    # Chat.userMsg drops a message for a channel that is neither open nor
    # switched on -- event, help, world and trade each hang off a UserSettings
    # flag -- and drops it silently. Answering on the event channel looked
    # fine on the wire and showed the player nothing at all.
    c.send("userMsg;entry=@/where@;group=4;")
    got = c.frames()
    check("where answers", [f.split(";")[0] for f in got], ["cmdAck", "userMsg"])
    check("on the channel it was asked in", "group=4;" in got[1], True)
    check("and names the file behind the cell", "static/183.xml" in got[1], True)

    # Ordinary chat is only acknowledged: Chat.delivery prints the sender's
    # own line the moment cmdAck;res=0 lands, so an echo would show it twice.
    # Alone in the location, nobody else is there to receive it either.
    c.send("userMsg;entry=@привет@;group=0;")
    got = c.frames()
    check("chat is acknowledged and not echoed",
          [f.split(";")[0] for f in got], ["cmdAck"])
    check("and accepted", got[0], "cmdAck;res=0;")

    c.send("logout;")
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
print("world entry OK")
