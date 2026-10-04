"""Clan diplomacy over real sockets: three clients against a server of its
own -- two members of one clan and the head of another, standing together.

What test_clan_diplomacy.py checks in process, seen from the wire where the
cmdAck queue is real: the prices; a step with the treasury empty (21, which
the page words «Не хватает денег на клановом счете»); a step to war -- the
actor's 0 BEFORE his res=8, the fresh tag of the enemy on both our screens
after the res=8 it will be painted by, res=9 to the other side and nothing
more; «Спросить» from the other side; a step past war refused 20; the
price in the clan's journal; and, across a restart of the server, the war
still in our standings at login and still ours alone.

    LAVA_RES=.../lava/res python3 server/test_clan_diplomacy_wire.py
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
DB = os.path.join(tempfile.mkdtemp(), "clan_diplomacy_wire.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _l in ("alice", "bob", "carol"):
    _st.register(_l + RUN, "secret")
_st.close()
CRED = {l: accounts.credential(l + RUN, "secret") for l in ("alice", "bob", "carol")}
ALICE, BOB, CAROL = "Alice" + RUN, "Bob" + RUN, "Carol" + RUN
WOLVES, FOXES = "Волки %s" % RUN, "Лисы %s" % RUN

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
                   LAVA_CLAN_DEAF_CHECK="0")
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
        return [decode(f.decode(ENC)) for f in parts if f]

    def close(self):
        self.s.close()


CLAN = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code", "userInfo_Player")


def shape(frames):
    """(name, code) of each clan frame: an answer's or a list's res, a
    fellow's reg."""
    return [(n, p.get("reg") if n == "fellow" else p.get("res"))
            for n, p in frames if n in CLAN]


def named(frames, name):
    return [p for n, p in frames if n == name]


def standings(frames, mine):
    return [{c: s for c, s in zip(p["data"], p["stats"]) if c in mine}
            for p in named(frames, "gg_list") if p["res"] == 0]


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
    return pre, got


def found(c, name):
    c.send("userMsg;entry=@/money 0 1000@;group=0;")
    c.frames()
    c.send("head;reg=@x@;soc=@%s@;" % name)
    got = c.frames()
    clan = named(got, "fellow")[0]["reg"] if named(got, "fellow") else None
    # What ClanInspector.firstRequest sends on that fellow.
    c.send("gg_info;det=1;")
    c.send("gg_info;det=5;")
    c.frames()
    return clan


srv = Server()
try:
    a, b, c = srv.connect(), srv.connect(), srv.connect()
    enter(a, "alice", ALICE)
    enter(b, "bob", BOB)
    enter(c, "carol", CAROL)
    for x in (a, b, c):
        x.frames()

    a.send("gg_info;det=6;")
    got = a.frames()
    check("det=6: the prices, a step down 100, a step up 1 000, then 0",
          (shape(got), named(got, "gg_list")[0]["data"]),
          ([("gg_list", 6), ("cmdAck", 0)], [1000, 100, 1000]))

    wolves = found(a, WOLVES)
    foxes = found(c, FOXES)
    mine = {wolves, foxes}
    a.send("admit;char=@%s@;perm=2;post=@@;" % BOB)
    a.frames()
    b.frames()
    b.send("apply;number=0;action=2;")
    b.frames()
    b.send("gg_info;det=1;")
    b.send("gg_info;det=5;")
    got = b.frames()
    check("the member's standings: the other clan, at neutral", standings(got, mine),
          [{foxes: 0}])
    for x in (a, b, c):
        x.frames()

    # --- the treasury empty -----------------------------------------------------------
    a.send("apply;number=%d;action=6;" % foxes)
    check("a step down with the treasury empty: 21 alone", shape(a.frames()), [("cmdAck", 21)])
    check("  ..nobody else hears a thing", (shape(b.frames(0.3)), shape(c.frames(0.3))), ([], []))

    # --- war ----------------------------------------------------------------------------
    st = accounts.Store(DB)
    st.clan_treasury_adjust(wolves, 150, "admin")
    st.close()
    a.send("apply;number=%d;action=6;" % foxes)
    got = a.frames()
    check("war: the actor's 0 FIRST, his res=8, then the enemy's fresh tag, then the"
          " treasury's balance (the head holds 0x400: clan_treasury.tell_balance)",
          shape(got), [("cmdAck", 0), ("gg_list", 8), ("fellow", foxes), ("gg_list", 3)])
    check("  ..res=8 names them, at war; res=3 has the 50 left", named(got, "gg_list"),
          [{"res": 8, "data": [foxes], "names": [FOXES], "stats": [-1]},
           {"res": 3, "data": [50]}])
    got = b.frames()
    check("  ..our other member: res=8, then the tag -- no balance, he has no 0x400",
          shape(got), [("gg_list", 8), ("fellow", foxes)])
    got = c.frames()
    check("  ..their head: res=9 alone -- her colours of us did not move",
          (shape(got), named(got, "gg_list")),
          ([("gg_list", 9)], [{"res": 9, "data": [wolves], "names": [WOLVES], "stats": [-1]}]))

    c.send("apply;number=%d;action=7;" % wolves)
    got = c.frames()
    check("«Спросить» from their side: res=5 with our war on them, then 0",
          (shape(got), named(got, "gg_list")[0]["stats"]),
          ([("gg_list", 5), ("cmdAck", 0)], [-1]))
    a.send("apply;number=%d;action=6;" % foxes)
    check("a step past war: 20 alone", shape(a.frames()), [("cmdAck", 20)])
    a.send("apply;number=%d;action=5;" % foxes)
    check("a step back up with 50 left: 21 alone", shape(a.frames()), [("cmdAck", 21)])
    b.send("apply;number=%d;action=5;" % foxes)
    check("our member without the right: gg_code 20, then 20",
          shape(b.frames()), [("gg_code", 20), ("cmdAck", 20)])

    st = accounts.Store(DB)
    check("the journal: the admin's 150, then 100 for the war, ref them, by her",
          [(r["source"], r["afro"], r["ref"]) for r in reversed(st.clan_ledger_rows(wolves))],
          [("admin", 150, 0), ("diplomacy", -100, foxes)])
    check("  ..one-sided in the rows", (st.clan_relation(wolves, foxes),
                                        st.clan_relation(foxes, wolves)), (-1, 0))
    st.close()
    for x in (a, b, c):
        x.send("logout;")
        x.close()
    time.sleep(0.5)
    srv.stop()

    # --- a restart -----------------------------------------------------------------------
    srv = Server()
    a, c = srv.connect(), srv.connect()
    pre, got = enter(a, "alice", ALICE, new=False)
    check("after a restart our head's login standings carry the war",
          standings(pre + got, mine), [{foxes: -1}])
    a.send("gg_info;det=1;")
    a.send("gg_info;det=5;")
    got = a.frames()
    check("  ..and so does her client's own det=5", (shape(got), standings(got, mine)),
          ([("gg_list", 1), ("cmdAck", 0), ("gg_list", 0), ("cmdAck", 0)], [{foxes: -1}]))
    pre, got = enter(c, "carol", CAROL, new=False)
    check("  ..their head's: we are still neutral to them -- one-sided",
          standings(pre + got, mine), [{wolves: 0}])
    a.close()
    c.close()
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("clan diplomacy over the wire OK")
