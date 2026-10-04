"""Clans over real sockets: three clients against a server of its own.

What test_clans.py checks in process, seen from the wire where the cmdAck
queue is real: the prices, a founding and the two questions its client
asks straight after (the answers in the order asked), the tag under a name
on getInfo, an invitation and its answer, the roster's names raw on the
wire (O'Neil&50%, not O%27Neil%2650%25), channel 2, a kick, a leave, the
last member leaving with the treasury paid into his purse, and -- across a
restart of the server -- a dead member's login answered with his roster,
never «Сервер не отвечает», and a client that never asks told to reload.

    LAVA_RES=.../lava/res python3 server/test_clans_wire.py
"""
import os
import random
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
sys.path.insert(0, HERE)
import accounts  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
DB = os.path.join(tempfile.mkdtemp(), "clans_wire.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _l in ("alice", "bob", "oneil"):
    _st.register(_l + RUN, "secret")
_st.close()
CRED = {l: accounts.credential(l + RUN, "secret") for l in ("alice", "bob", "oneil")}
ALICE, BOB, ONEIL = "Alice" + RUN, "Bob" + RUN, "O'Neil&50%" + RUN
DEAF = 1.5

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self):
        self.port = free_port()
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
                   LAVA_GX="6268", LAVA_GY="1819", LAVA_CHEATS="1", LAVA_POLICY_PORT="0",
                   LAVA_CLAN_DEAF_CHECK=str(DEAF))
        self.proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True)
        # Drained as it comes: a full pipe would stall the server.
        self.log = []
        threading.Thread(target=lambda: self.log.extend(self.proc.stdout), daemon=True).start()

    def connect(self, timeout=None):
        return Client(testkit.connect(self.port, self.proc, self.log, timeout))

    def stop(self):
        self.proc.send_signal(signal.SIGTERM)
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""
        self.raw = []

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
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
        texts = [f.decode(ENC) for f in parts if f]
        self.raw = texts
        return [decode(t) for t in texts]

    def close(self):
        self.s.close()


CLAN = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code", "userInfo_Player")


def only(frames, *keep):
    return [(n, p) for n, p in frames if n in (keep or CLAN)]


def shape(frames):
    """(name, code) of each clan frame: an answer's or a list's res, a
    fellow's reg, a gg_struct's act."""
    out = []
    for n, p in only(frames):
        out.append((n, p.get("act") if n == "gg_struct" else p.get("reg") if n == "fellow"
                    else p.get("res") if n in ("cmdAck", "gg_list", "gg_code") else None))
    return out


def named(frames, name):
    return [p for n, p in frames if n == name]


def enter(c, login, name, new=True):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED[login])
    c.frames()
    if new:
        c.send("newPers;res=1;sex=0;name=@%s@;" % escape(name))
        c.frames()
        c.send("actPlayer;")
    else:
        c.send("selPers;num=0;")
    pre = c.frames()
    c.send("lenter;accept=1;")
    got = c.frames(1.0)
    return pre, got, [p["newUser"] for n, p in got if n == "lch" and p.get("rtype") == -1]


srv = Server()
try:
    a, b, o = srv.connect(), srv.connect(), srv.connect()
    enter(a, "alice", ALICE)
    _, _, seen_b = enter(b, "bob", BOB)
    _, _, seen_o = enter(o, "oneil", ONEIL)
    pid_a = seen_b[0]
    a.frames()
    b.frames()

    # --- the prices and a founding ----------------------------------------------------
    a.send("gg_info;det=6;")
    check("det=6: the prices, then 0", shape(a.frames()), [("gg_list", 6), ("cmdAck", 0)])
    a.send("userMsg;entry=@/money 0 1000@;group=0;")
    a.frames()
    a.send("head;reg=@Стая@;soc=@Волки %s@;" % RUN)
    got = a.frames()
    wolves = named(got, "fellow")[0]["reg"] if named(got, "fellow") else None
    check("head: the purse, the fellow, the standings, then 0",
          shape(got), [("userInfo_Player", None), ("fellow", wolves), ("gg_list", 0),
                       ("cmdAck", 0)])
    char_a = named(got, "fellow")[0]["char"]
    # What ClanInspector.firstRequest sends on that fellow, queued behind
    # head's own handler.
    a.send("gg_info;det=1;")
    a.send("gg_info;det=5;")
    check("the two questions that follow are answered in the order asked, each with its ack",
          shape(a.frames()), [("gg_list", 1), ("cmdAck", 0), ("gg_list", 0), ("cmdAck", 0)])
    check("the one standing beside him sees his tag", [p for p in named(b.frames(), "fellow")],
          [{"id": pid_a, "reg": wolves, "soc": "Волки %s" % RUN}])
    b.send("getInfo;id=%d;" % pid_a)
    check("getInfo about him: userInfo_Player, usrUp, fellow",
          [n for n, _ in b.frames()], ["userInfo_Player", "usrUp", "fellow"])

    # --- invitations and answers ------------------------------------------------------
    a.send("admit;char=@%s@;perm=%d;post=@Боец@;" % (BOB, 0x42))
    check("invite: 0 to the inviter", shape(a.frames()), [("cmdAck", 0)])
    check("  ..the popup's words to the invited",
          named(b.frames(), "invite"), [{"rec": ALICE, "soc": "Волки %s" % RUN, "pos": "Боец"}])
    b.send("apply;number=0;action=2;")
    got = b.frames()
    check("yes: fellow with the clan, the standings, 0", shape(got),
          [("fellow", wolves), ("gg_list", 0), ("cmdAck", 0)])
    char_b = named(got, "fellow")[0]["char"]
    check("  ..the head, holding the roster, hears act=1",
          [(p["id"], p["act"], p["name"]) for p in named(a.frames(), "gg_struct")],
          [(char_b, 1, BOB)])
    b.send("gg_info;det=1;")
    b.frames()
    a.send("admit;char=@%s@;perm=%d;post=@@;" % (escape(ONEIL), 0x2))
    a.frames()
    o.frames()
    o.send("apply;number=0;action=2;")
    char_o = named(o.frames(), "fellow")[0]["char"]
    o.send("gg_info;det=1;")
    o.frames()
    a.frames()
    b.frames()
    a.send("gg_info;det=1;")
    a.frames()
    line = [t for t in a.raw if t.startswith("gg_list;")][0]
    check("the roster's names on the wire as they are: @%s@, no %%27, %%26 or %%25" % ONEIL,
          ("@%s@" % ONEIL in line, "%27" in line or "%26" in line), (True, False))

    # --- channel 2 ---------------------------------------------------------------------
    b.send("userMsg;entry=@привет, свои@;group=2;")
    check("channel 2: the sender's ack alone", shape(b.frames()), [("cmdAck", 0)])
    want = [{"group": 2, "player": char_b, "nick": BOB, "entry": "привет, свои"}]
    check("  ..the others hear it, player= his char id",
          (named(a.frames(), "userMsg"), named(o.frames(), "userMsg")), (want, want))

    # --- a kick and a leave --------------------------------------------------------------
    a.send("apply;number=%d;action=1;" % char_o)
    check("kick: act=2 BEFORE the kicker's 0", shape(a.frames())[:2], [("gg_struct", 2),
                                                                       ("cmdAck", 0)])
    check("  ..the kicked: fellow reg=0, then the emptied standings",
          shape(o.frames()), [("fellow", 0), ("gg_list", 0)])
    check("  ..the other roster holder: act=2", shape(b.frames())[:1], [("gg_struct", 2)])
    b.send("apply;number=0;action=1;")
    check("leave: 0 FIRST, then fellow reg=0, then the emptied standings",
          shape(b.frames()), [("cmdAck", 0), ("fellow", 0), ("gg_list", 0)])
    check("  ..the head hears act=2", shape(a.frames())[:1], [("gg_struct", 2)])

    # --- the last one out, with money in the treasury ----------------------------------
    st = accounts.Store(DB)
    st.clan_treasury_adjust(wolves, 500, "admin")
    afro0 = st.money(char_a)[0]
    st.close()
    a.send("apply;number=0;action=1;")
    got = a.frames()
    check("the lone head leaves: the purse BEFORE the 0, then put out",
          shape(got), [("userInfo_Player", None), ("cmdAck", 0), ("fellow", 0), ("gg_list", 0)])
    check("  ..500 afro more on the screen", named(got, "userInfo_Player")[0]["afro"], afro0 + 500)
    st = accounts.Store(DB)
    check("  ..and in the row, booked clan_disband; the clan is gone",
          (st.money(char_a)[0], [(r["source"], r["afro"]) for r in st.ledger(char_a)][-1],
           st.clan(wolves)), (afro0 + 500, ("clan_disband", 500), None))
    st.close()

    # --- a new clan, a dead member, a restart -------------------------------------------
    a.send("userMsg;entry=@/money 0 1000@;group=0;")
    a.frames()
    a.send("head;reg=@x@;soc=@Лисы %s@;" % RUN)
    foxes = named(a.frames(), "fellow")[0]["reg"]
    a.send("gg_info;det=1;")
    a.frames()
    a.send("admit;char=@%s@;perm=2;post=@@;" % BOB)
    a.frames()
    b.frames()
    b.send("apply;number=0;action=2;")
    b.frames()
    b.send("logout;")
    b.close()
    time.sleep(0.5)
    st = accounts.Store(DB)
    st.save_character_state(char_b, death=1)
    st.close()
    for c in (a, o):
        c.close()
    srv.stop()

    srv = Server()
    b = srv.connect()
    pre, got, _ = enter(b, "bob", BOB, new=False)
    check("after a restart the member is told his clan at login",
          [p["reg"] for p in named(pre, "fellow") if p["id"] == 0], [foxes])
    b.send("gg_info;det=1;")
    b.send("gg_info;det=5;")
    check("dead, his client's own questions get the roster and the standings, never 3",
          shape(b.frames()), [("gg_list", 1), ("cmdAck", 0), ("gg_list", 0), ("cmdAck", 0)])
    b.send("apply;number=0;action=1;")
    check("  ..and a clan action from the dead body is refused 20, not 3",
          shape(b.frames()), [("cmdAck", 20)])
    a = srv.connect()
    enter(a, "alice", ALICE, new=False)
    got = a.frames(DEAF + 1.0)
    # The server's own lines are off here, as on the served game: the deaf
    # client is noted in the log, and nothing reaches the chat.
    check("a member whose client never asks for its roster: noted in the log, nothing in the chat",
          (named(got, "userMsg"),
           any("did not ask for its clan" in line for line in srv.log)),
          ([], True))
    a.close()
    b.close()
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("clans over the wire OK")
