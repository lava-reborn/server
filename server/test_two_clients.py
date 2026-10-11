"""Two clients in one world: they see each other, walk, and talk.

The scenario is recon/analysis/architecture.md section 4 (the two-socket test
after the migration table), and the frame shapes are what
lol/core/location/Location.as, lol/core/globmap/GlobalMap.as,
lol/core/player/PlayerRegister.as and lol/core/Chat.as read. The one rule
underneath: id 0 in a frame is always the receiver (Gamer.as:31), so the same
step reaches its walker as id=0 and everyone else as the walker's real id.
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


def free_port():
    """A port nobody holds: the suites run side by side in several
    checkouts, and a fixed number puts two servers on one socket."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()

# A throwaway database with two accounts: the server refuses any digest it
# does not know, and both players need one of their own.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
import mobs
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("alice", "secret")
_store.register("bob", "secret")
_store.close()
CRED_A = accounts.credential("alice", "secret")
CRED_B = accounts.credential("bob", "secret")

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_CHEATS="1", LAVA_GX="5970", LAVA_GY="1730")

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
        """Collect whatever arrives within the window, as decoded strings.

        The window is exact: the heartbeat checks below count frames per
        second, so a call must return at the deadline and not a socket
        timeout later. A frame cut by the window's end stays in the buffer.
        """
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

    def names(self, wait=0.5):
        return [f.split(";")[0] for f in self.frames(wait)]


def param(frame, key):
    """One value out of a frame, as text, or None."""
    for part in frame.split(";")[1:]:
        if part.startswith(key + "="):
            return part[len(key) + 1:]
    return None


def enter(c, cred, nick):
    """Log in, create the character, and stand in the starting location."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % cred)
    check("%s logs in" % nick, c.names(),
          ["hello", "cmdAck", "constants", "accountInfo"])
    c.send("newPers;res=1;sex=0;name=@%s@;" % nick)
    check("%s is created" % nick, c.names(), ["cmdAck"])
    c.send("actPlayer;")
    got = c.frames()
    check("%s is called into a location" % nick,
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    check("%s starts in 102" % nick, "id=102;" in got[1], True)
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    check("%s is positioned" % nick, got[0].split(";")[0], "lenter")
    return got, int(param(got[0], "pos"))


try:
    a = Client(connect())
    b = Client(connect())

    # --- presence in a location --------------------------------------------
    got_a, pos_a = enter(a, CRED_A, "Alice")
    # A is alone: every lch is an inhabitant, each followed by its details.
    check("no other player yet for Alice",
          any("rtype=-1;" in f for f in got_a), False)
    # The traders keep their ids: room 102 is built once, and its first
    # inhabitants take the same ids the single-player replay relies on.
    npc_ids = [int(param(f, "newUser")) for f in got_a if f.startswith("lch")]
    check("inhabitants numbered from 100", npc_ids[0], 100)

    got_b, pos_b = enter(b, CRED_B, "Bob")
    # The newcomer gets the room as it stands: the same inhabitants under the
    # same ids, plus the player already there, as a Player (rtype=-1).
    check("Bob sees the same inhabitants",
          [int(param(f, "newUser")) for f in got_b
           if f.startswith("lch") and "rtype=-1;" not in f], npc_ids)
    seen = [f for f in got_b if f.startswith("lch") and "rtype=-1;" in f]
    check("Bob sees one other player", len(seen), 1)
    pid_a = int(param(seen[0], "newUser"))
    check("players are numbered above every NPC", pid_a >= 1_000_000, True)
    check("Alice stands where she was put", param(seen[0], "pos"), str(pos_a))
    # ... and the one already there is told about the newcomer.
    got = a.frames()
    check("Alice is told of Bob", [f.split(";")[0] for f in got], ["lch"])
    check("as a player on his cell",
          "pos=%d;rtype=-1;" % pos_b in got[0], True)
    pid_b = int(param(got[0], "newUser"))
    check("two players, two ids", pid_a != pid_b, True)

    # --- a stranger's details ---------------------------------------------
    # The client sends both of these by itself the moment it builds the
    # Player entity (Entity.as:38-41, Player.as:11-18).
    b.send("getInfo;lvl=0;id=%d;type=0;" % pid_a)
    got = b.frames()
    check("stranger described", [f.split(";")[0] for f in got],
          ["userInfo_Player", "usrUp"])
    check("under her own id", "id=%d;" % pid_a in got[0], True)
    check("by name, as text", "name=@Alice@;" in got[0], True)
    check("as an ally, or every service is refused", "ally=1;" in got[0], True)
    check("money is only ever about oneself", "afro=" in got[0], False)
    check("health bars filled under her id", got[1].startswith(
        "usrUp;id=%d;hcur=" % pid_a), True)

    b.send("ss_get;target=%d;slot=3;" % pid_a)
    got = b.frames()
    check("stranger's gear answered", got[0].split(";")[0], "ss_ack")
    # PersEquip.ss_ack splices six wear slots and then two hands off the list
    # regardless of what came, so an empty answer is eight empty entries.
    # Six wear slots empty, then the two hands: the kit puts a pistol in the
    # first of them, so a stranger's gear is not eight zeroes any more.
    fields = got[0].split("o_list=|")[1].rstrip("|;").split("|")
    check("six wear slots, all empty", fields[:6], ["x0"] * 6)
    check("a pistol in the hand and nothing in the other",
          (fields[6] != "x0", fields[7]), (True, "x0"))

    # --- walking -----------------------------------------------------------
    path = "|%d|%d|" % (pos_a, pos_a + 1)
    a.send("moveTo;path=%s;" % path)
    got = a.frames()
    check("walker acknowledged and moved as id 0",
          got, ["cmdAck;res=0;", "userMove;id=0;path=%s;" % path])
    got = b.frames()
    check("the other sees the same walk under her id",
          got, ["userMove;id=%d;path=%s;" % (pid_a, path)])

    # --- chat ---------------------------------------------------------------
    a.send("userMsg;entry=@привет@;group=0;")
    got = a.frames()
    check("speaker gets only the acknowledgement", got, ["cmdAck;res=0;"])
    got = b.frames()
    check("listener gets the line with the speaker's id and nick",
          got, ["userMsg;group=0;nick=@Alice@;entry=@привет@;from=%d;"
                % pid_a])

    # Private: addressed by nick, no group either way.
    b.send("userMsg;entry=@псст@;to=@Alice@;")
    check("whisper accepted", b.frames(), ["cmdAck;res=0;"])
    got = a.frames()
    check("whisper delivered without a group",
          got, ["userMsg;nick=@Bob@;entry=@псст@;from=%d;" % pid_b])
    b.send("userMsg;entry=@эй@;to=@Nobody@;")
    check("nobody there: res=9, the client's 'offline' wording",
          b.frames(), ["cmdAck;res=9;"])
    check("and nothing reaches anyone", a.frames(0.3), [])

    # World channel reaches everyone online.
    a.send("userMsg;entry=@всем@;group=6;")
    check("world channel acknowledged", a.frames(), ["cmdAck;res=0;"])
    check("world channel heard elsewhere",
          b.frames(), ["userMsg;group=6;nick=@Alice@;entry=@всем@;from=%d;"
                       % pid_a])

    # Trade retains its own group, including the long-message chunk markers.
    for raw in ("selling", "^0^first", "^1^middle", "^2L^last"):
        a.send("userMsg;entry=@%s@;group=4;" % raw)
        check("trade: one ack and no duplicate to the speaker", a.frames(),
              ["cmdAck;res=0;"])
        check("trade: the listener receives the exact text in channel 4",
              b.frames(), ["userMsg;group=4;nick=@Alice@;entry=@%s@;from=%d;"
                           % (raw, pid_a)])

    # Server answers to our own commands still come back to the asker.
    a.send("userMsg;entry=@/where@;group=0;")
    got = a.frames()
    check("/where still answers the asker",
          [f.split(";")[0] for f in got], ["cmdAck", "userMsg"])
    check("and nobody else hears it", b.frames(0.3), [])

    # --- an intruder without a login --------------------------------------
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("selPers;num=0;")
    c.send("lenter;accept=1;")
    c.send("moveTo;path=|1|2|;")
    got = c.frames()
    check("intruder is greeted", got[0].split(";")[0], "hello")
    check("then called nowhere and let in nowhere",
          [f for f in got if f.split(";")[0] in ("lcall", "lenter")], [])
    check("Alice notices nothing", a.frames(0.3), [])
    check("Bob notices nothing", b.frames(0.3), [])
    c.s.close()

    # --- throwing a thing on the ground -------------------------------------
    # PersEquip.dropItem: a thing dragged out of the equipment window onto
    # the ground opens a loot session with no window on the player's own
    # cell (Loot.createSession(walker.numPos, true)), bag or no bag, and each
    # thing then goes into it as a Loot transfer (2). Refused, Loot.status
    # stays false and every later drop waits in dropStack for ever.
    here = pos_a + 1
    guns = []
    for _ in range(2):
        a.send("userMsg;entry=@/give 25586@;group=0;")
        guns += [param(f, "obj") for f in a.frames()
                 if f.startswith("ss_obj_status") and param(f, "status") == "1"]
    check("Alice is given two Berettas to throw away", len(guns), 2)
    a.send("ss_create;s_type=0;target=%d;" % here)
    check("the drop opens a session on her own empty cell",
          a.frames(), ["cmdAck;res=0;"])
    a.send("ss_upd;s_status=2;obj=%s;param=1;" % guns[0])
    got = a.frames()
    check("the first thing goes down: acked, then a bag drawn on her cell",
          [f for f in got if f.split(";")[0] in ("cmdAck", "ss_loot")],
          ["cmdAck;res=0;", "ss_loot;s_status=1;hex=|%d|;" % here])
    check("Bob sees the bag appear", b.frames(),
          ["ss_loot;s_status=1;hex=|%d|;" % here])
    # Bob, beside it, takes it: the bag is empty and goes -- while Alice's
    # equipment window, and so her session, is still open.
    b.send("ss_create;s_type=0;target=%d;" % here)
    check("Bob opens the bag", b.frames(), ["cmdAck;res=0;"])
    b.send("ss_upd;s_status=1;obj=%s;param=1;" % guns[0])
    got = b.frames()
    check("and takes the Beretta; the empty bag goes",
          [f for f in got if f.split(";")[0] in ("cmdAck", "ss_loot")],
          ["cmdAck;res=0;", "ss_loot;s_status=0;hex=|%d|;" % here])
    b.send("ss_upd;s_status=0;obj=x0;param=1;")
    check("Bob closes the bag, unanswered", b.frames(0.3), [])
    check("Alice sees the bag go", a.frames(), ["ss_loot;s_status=0;hex=|%d|;" % here])
    a.send("ss_upd;s_status=2;obj=%s;param=1;" % guns[1])
    got = a.frames()
    check("her next drop still lands: a new bag, not an ack for nothing",
          [f for f in got if f.split(";")[0] in ("cmdAck", "ss_loot")],
          ["cmdAck;res=0;", "ss_loot;s_status=1;hex=|%d|;" % here])
    check("Bob sees that bag too", b.frames(),
          ["ss_loot;s_status=1;hex=|%d|;" % here])
    a.send("ss_upd;s_status=0;obj=x0;param=1;")
    check("the equipment window shuts the session, unanswered", a.frames(0.3), [])
    a.send("ss_get;target=0;slot=8;")
    bag_a = a.frames()[0]
    b.send("ss_get;target=0;slot=8;")
    bag_b = b.frames()[0]
    check("the Berettas are out of Alice's bag, the first one in Bob's",
          (guns[0] in bag_a, guns[1] in bag_a, guns[0] in bag_b),
          (False, False, True))

    # --- a bag's session under a stall ---------------------------------------
    # Every session window is modal, so a new ss_create means the last one is
    # gone even when its close never came -- and a bag left open would read
    # the stall's codes as its own, cmd_ss_upd asking the bag first: the
    # repair window's afro repair (3) is the bag's "take all".
    a.send("ss_get;target=0;slot=11;")
    pistol = a.frames()[0].split("o_list=|")[1].rstrip("|;").split("|")[6]
    stall = next(int(param(f, "id")) for f in got_a if f.startswith("userInfo_Trader"))
    a.send("ss_create;s_type=0;target=%d;" % here)
    check("Alice opens the bag on her cell", a.frames(), ["cmdAck;res=0;"])
    a.send("ss_create;s_type=1;target=%d;" % stall)
    check("then a stall, the bag's close never sent", a.frames(), ["cmdAck;res=0;"])
    a.send("ss_upd;s_status=3;obj=%s;param=1;" % pistol)
    got = a.frames()
    # A whole pistol: the stall has nothing to do, answers 0, charges
    # nothing and sends the pistol's own state back (Inventory.repair).
    check("the repair is the stall's to answer (a whole pistol: nothing to do), not"
          " the bag's take-all",
          ([f for f in got if f.startswith("cmdAck")],
           [f.split(";")[0] for f in got if f.split(";")[0] in ("cmdAck", "ss_loot", "ss_di_firearm")]),
          (["cmdAck;res=0;"], ["cmdAck", "ss_di_firearm"]))
    check("and the Beretta still lies in the bag", b.frames(0.3), [])
    a.send("ss_upd;s_status=0;obj=x0;param=1;")
    a.frames(0.3)
    a.send("ss_get;target=0;slot=8;")
    check("not in Alice's bag", guns[1] in a.frames()[0], False)

    # --- leaving for the map ------------------------------------------------
    a.send("chWorld;")
    got = a.frames()
    check("Alice leaves for the map",
          [f.split(";")[0] for f in got], ["cmdAck", "gmap", "marks"])
    check("Bob sees her go", b.frames(), ["lch;lostUser=%d;" % pid_a])
    check("and Alice, alone on the map, hears nothing", a.frames(0.3), [])

    b.send("chWorld;")
    got = b.frames()
    check("Bob leaves for the map",
          [f.split(";")[0] for f in got], ["cmdAck", "gmap", "marks", "newUser", "userMove"])
    # newUser is an offset the client subtracts from its own cell
    # (GlobalMap.newUser: x = my.x - dx): same cell, zero offset.
    # cmdAck, gmap, marks, then the neighbours
    check("Alice appears beside him", got[3],
          "newUser;id=%d;dx=0;dy=0;" % pid_a)
    check("standing still at her absolute cell",
          got[4], "userMove;id=%d;dx=5970;dy=1730;vx=0;vy=0;t=0;" % pid_a)
    got = a.frames()
    # the first heartbeat may already follow within the window
    check("Bob appears beside her", got[:2],
          ["newUser;id=%d;dx=0;dy=0;" % pid_b,
           "userMove;id=%d;dx=5970;dy=1730;vx=0;vy=0;t=0;" % pid_b])

    # Heartbeat: a figure on the client fades after 3 s without a userMove
    # and is removed after 6 (MapObject.checkLive), so each side must hear
    # about the other again within 3 s of the last frame.
    beats_a = [f for f in a.frames(3) if f.startswith("userMove;id=%d;" % pid_b)]
    beats_b = [f for f in b.frames(0.2) if f.startswith("userMove;id=%d;" % pid_a)]
    check("Alice keeps hearing about Bob", len(beats_a) >= 1, True)
    check("Bob keeps hearing about Alice", len(beats_b) >= 1, True)

    a.send("userMsg;entry=@map neighbours@;group=0;")
    check("location chat on the map: one ack and no echo",
          [f for f in a.frames() if not f.startswith("userMove")], ["cmdAck;res=0;"])
    check("location chat on the map reaches a nearby player",
          [f for f in b.frames() if f.startswith("userMsg")],
          ["userMsg;group=0;nick=@Alice@;entry=@map neighbours@;from=%d;" % pid_a])

    # A leg of travel reaches the other side at once, with the velocity.
    # Bob's heartbeat (every 2 s) may land in Alice's socket during the
    # window just before, and so ahead of her moveAck: it is not hers.
    a.send("moveTo;dy=0;dx=-100;")
    got = [f for f in a.frames() if not f.startswith("userMove;id=%d;" % pid_b)]
    check("travel acknowledged", got[0].split(";")[0], "moveAck")
    got = [f for f in b.frames() if f.startswith("userMove;id=%d;" % pid_a)]
    check("Bob sees her set off", len(got) >= 1, True)
    check("westward", any("vx=-0.35;vy=0;" in f for f in got), True)
    got = [f for f in b.frames(4) if f.startswith("userMove;id=%d;" % pid_a)]
    check("and arrive one cell west",
          any("dx=5969;dy=1730;vx=0;vy=0;" in f for f in got), True)
    a.frames(0.2)

    # --- перехват: the map's shift-click menu -------------------------------
    # DisplayGlobalMap.playerMcOnPress offers "перехват" on another player,
    # and GlobalMap.interceptPlayer sends moveTo carrying nothing but their
    # id: where they are is the server's to work out, and they are walking.
    b.send("moveTo;trg=%d;" % pid_a)
    got = b.frames(1.0)
    # Alice's heartbeat may come ahead of his moveAck, as above.
    check("the pursuit sets off",
          [f.split(";")[0] for f in got if not f.startswith("userMove;id=%d;" % pid_a)][:1],
          ["moveAck"])
    check("westward, towards her", any("vx=-0.35" in f for f in got), True)
    # She is standing still one cell away, so he is on her inside a few
    # seconds; the chase re-aims once a second until then.
    got = b.frames(6)
    check("he runs her down",
          any("настигли" in f for f in got if f.startswith("userMsg")), True)
    # Catching somebody and then standing beside them on the map would be an
    # escort, not an interception: the ground decides instead, and takes both.
    check("and both are taken into the cell",
          [f.split(";")[0] for f in got if f.startswith("lcall")], ["lcall"])
    got = a.frames(0.5)
    check("she is told who by",
          any("настиг вас" in f for f in got if f.startswith("userMsg")), True)
    check("and pulled in after him, without being asked",
          [f.split(";")[0] for f in got if f.startswith("lcall")], ["lcall"])
    b.send("lenter;accept=1;")
    entered_b = b.frames(wait=2)
    check("the intercepted pair gets a visible preparation countdown",
          any(f.startswith("prepare;") and param(f, "id") == "0"
              and 2 < int(param(f, "time")) <= 17 for f in entered_b), True)
    a.send("lenter;accept=1;")
    entered_a = a.frames(wait=2)
    entry_a = int(param(next(f for f in entered_a if f.startswith("lenter;")), "pos"))
    entry_b = int(param(next(f for f in entered_b if f.startswith("lenter;")), "pos"))
    check("interception places the clients 8..15 hexes apart in the desert",
          8 <= mobs.hex_distance(entry_a, entry_b, 64) <= 15, True)
    check("a later loader receives the remaining shared countdown",
          any(f.startswith("prepare;") and param(f, "id") == "0"
              and 2 < int(param(f, "time")) < 17 for f in entered_a), True)
    check("into the same location",
          [f for f in b.frames(1.5) if "rtype=-1;" in f] != [], True)
    got = a.frames(15)
    check("the real timer starts the duel without either player attacking",
          (any(f.startswith("lch;") and param(f, "ws") == "1" for f in got),
           any(f.startswith("lch;") and param(f, "enemy") == str(pid_b) for f in got),
           any(f.startswith("prepare;") and param(f, "id") == "0"
               and param(f, "time") == "0" for f in got)), (True, True, True))
    got = b.frames(0.1)
    check("both sides see each other as enemies after preparation",
          any(f.startswith("lch;") and param(f, "enemy") == str(pid_a) for f in got), True)
    # Back out to the map, where the rest of the scene expects them.
    for who in (a, b):
        who.send("chWorld;")
        check("out to the map again",
              any(f.startswith("gmap") for f in who.frames(wait=2)), True)
    a.frames(0.5)
    b.frames(0.5)

    # Intercepting somebody who is not on the map at all does nothing: the
    # client has no frame for a refusal (GlobalMap.interceptAck is empty),
    # so silence is the whole answer.
    b.send("moveTo;trg=%d;" % (pid_a + 4242))
    # The map's own heartbeat keeps arriving whatever happens here, so only
    # what is not a heartbeat counts as an answer.
    check("a chase after nobody sets off nothing",
          [f for f in b.frames(0.5) if not f.startswith("userMove")], [])
    a.frames(0.3)

    # --- into a cell, and gone ----------------------------------------------
    a.send("chWorld;")
    got = a.frames()
    # a heartbeat about Bob may land in the same window; only the answer counts
    check("Alice walks into the cell under her",
          [f.split(";")[0] for f in got if not f.startswith("userMove")],
          ["cmdAck", "lcall"])
    # No userLost: the client's map drops a figure only when its own timer
    # runs out (MapObject.checkLive), and a userLost would stop that timer
    # and leave her drawn for good (rooms.GlobalMapRoom; test_gmap_presence).
    got = b.frames()
    check("Bob is told nothing of her going",
          [f for f in got if str(pid_a) in f and not f.startswith("userMove")], [])
    check("and hears no more of her, so his map lets her go",
          [f for f in b.frames(2.5) if str(pid_a) in f], [])
    a.send("lenter;accept=1;")
    got = a.frames(wait=2)
    check("the wasteland has no other player in it",
          any("rtype=-1;" in f for f in got), False)
    alice_pos = int(param(next(f for f in got if f.startswith("lenter;")), "pos"))

    # Bob is still on the map above Alice's cell. Location chat does not
    # cross between the map and a local scene; trade/world do, both ways.
    for speaker, listener, nick, pid in ((a, b, "Alice", pid_a), (b, a, "Bob", pid_b)):
        speaker.send("userMsg;entry=@only neighbours@;group=0;")
        check("map and local scene do not share location chat: ack only",
              [f for f in speaker.frames() if not f.startswith("userMove")],
              ["cmdAck;res=0;"])
        check("  ..the other scene hears nothing",
              [f for f in listener.frames() if f.startswith("userMsg")], [])
        for group in (4, 6):
            speaker.send("userMsg;entry=@across scenes@;group=%d;" % group)
            check("trade/world between map and scene: one ack, no echo",
                  [f for f in speaker.frames() if not f.startswith("userMove")],
                  ["cmdAck;res=0;"])
            check("  ..delivered with the original channel, id and nick",
                  [f for f in listener.frames() if f.startswith("userMsg")],
                  ["userMsg;group=%d;nick=@%s@;entry=@across scenes@;from=%d;"
                   % (group, nick, pid)])

    # --- one leaves, the other lives on ---------------------------------------
    a.send("logout;")
    a.s.close()
    time.sleep(0.3)
    b.send("chWorld;")
    got = b.frames()
    check("Bob can still enter a cell",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    b.send("lenter;accept=1;")
    got = b.frames(wait=2)
    check("Bob is positioned", got[0].split(";")[0], "lenter")
    check("Alice's disconnected body is still visible under the same player id",
          [f for f in got if "rtype=-1;" in f],
          ["lch;newUser=%d;pos=%d;rtype=-1;" % (pid_a, alice_pos)])
    b.send("moveTo;path=|490|491|;")
    check("and can still walk",
          b.frames(), ["cmdAck;res=0;", "userMove;id=0;path=|490|491|;"])
    b.send("logout;")

    # The rim is one file standing on hundreds of cells, so a room keyed by
    # location id alone would put the whole western wall in one room: two
    # players a hundred cells apart would see each other through the rock.
    print("\nстена мира -- не одна комната на всю длину")
    a = Client(connect())
    b = Client(connect())
    a.send("hello;minor=2;major=0;")
    a.send("login;hash=@%s@;" % CRED_A)
    a.frames()
    a.send("selPers;num=0;")
    a.frames()
    a.send("userMsg;entry=@/goto 5833 1700@;group=0;")
    got = a.frames(wait=2)
    wall = [f for f in got if f.startswith("lcall")]
    check("Алиса встала на западную стену", bool(wall), True)
    a.send("lenter;accept=1;")
    a.frames(wait=2)

    b.send("hello;minor=2;major=0;")
    b.send("login;hash=@%s@;" % CRED_B)
    b.frames()
    b.send("selPers;num=0;")
    b.frames()
    b.send("userMsg;entry=@/goto 5833 1900@;group=0;")
    got = b.frames(wait=2)
    far = [f for f in got if f.startswith("lcall")]
    check("Боб встал на ту же стену двумястами клетками южнее", bool(far), True)
    check("и это та же локация",
          bool(wall) and bool(far) and param(wall[0], "id") == param(far[0], "id"),
          True)
    b.send("lenter;accept=1;")
    got = b.frames(wait=2)
    check("но Алисы там нет", any("rtype=-1;" in f for f in got), False)
    check("и Алисе о Бобе не сказали",
          any(f.startswith("newUser") for f in a.frames(wait=1)), False)
    a.send("userMsg;entry=@distant trade@;group=4;")
    check("trade reaches a distant room: the sender gets only its ack",
          a.frames(), ["cmdAck;res=0;"])
    check("  ..two hundred cells away the listener still gets the trade line",
          b.frames(), ["userMsg;group=4;nick=@Alice@;entry=@distant trade@;from=%d;" % pid_a])
    a.send("logout;")
    b.send("logout;")
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
print("two clients OK")
