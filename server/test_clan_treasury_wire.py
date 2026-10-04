"""The clan's treasury over real sockets: three clients against a server of
its own.

What test_clan_treasury.py checks in process, seen from the wire where the
cmdAck queue is real: a deposit by a member without rights, answered with
the purse before the 0, and the balance arriving unasked on the other
holders' sockets as `gg_list;res=3;data=|N|;`; a withdrawal followed by the
page's own det=3, answered in the order asked; the refusals (no right, a
fraction, the gold, the balance to one without the right); a burst of five
treasury commands in one write, one answer each and in order; two clients
taking the whole treasury at the same moment, one of them paid; a kicked
member's page, still open; and the balance across a restart of the server.

    LAVA_RES=.../lava/res python3 server/test_clan_treasury_wire.py
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
DB = os.path.join(tempfile.mkdtemp(), "clan_treasury_wire.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _l in ("alice", "bob", "carol"):
    _st.register(_l + RUN, "secret")
_st.close()
CRED = {l: accounts.credential(l + RUN, "secret") for l in ("alice", "bob", "carol")}
ALICE, BOB, CAROL = "Alice" + RUN, "Bob" + RUN, "Carol" + RUN

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
        self.raw = []

    def send(self, *texts):
        """One write for all of them, as a burst of clicks would go."""
        self.s.sendall(b"".join(t.encode(ENC) + b"\x00" for t in texts))

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


def shape(frames):
    """(name, what tells it) of each clan frame: the purse of a
    userInfo_Player, the balance of a res=3, the code of anything else."""
    out = []
    for n, p in frames:
        if n not in CLAN:
            continue
        if n == "userInfo_Player":
            out.append((n, p.get("afro")))
        elif n == "gg_list" and p.get("res") == 3:
            out.append((n, 3, p.get("data")))
        else:
            out.append((n, p.get("res", p.get("reg"))))
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
    return pre + got


def afro_of(c):
    """The purse the client was last shown: /money 0 0 pushes it."""
    c.send("userMsg;entry=@/money 0 0@;group=0;")
    return [p["afro"] for p in named(c.frames(), "userInfo_Player")][-1]


srv = Server()
try:
    a, b, c = srv.connect(), srv.connect(), srv.connect()
    enter(a, "alice", ALICE)
    enter(b, "bob", BOB)
    enter(c, "carol", CAROL)
    a.send("userMsg;entry=@/money 0 1000@;group=0;")
    a.frames()
    a.send("head;reg=@x@;soc=@Казна %s@;" % RUN)
    got = a.frames()
    clan = named(got, "fellow")[0]["reg"]
    a.send("gg_info;det=1;")
    a.frames()
    ids = {}
    for cl, name, perm in ((b, BOB, 0x402), (c, CAROL, 0x2)):
        a.send("admit;char=@%s@;perm=%d;post=@@;" % (name, perm))
        a.frames()
        cl.frames()
        cl.send("apply;number=0;action=2;")
        ids[name] = named(cl.frames(), "fellow")[0]["char"]
        cl.send("gg_info;det=1;")
        cl.frames()
        cl.send("userMsg;entry=@/money 1000 0@;group=0;")
        cl.frames()
    a.frames()
    b.frames()
    st = accounts.Store(DB)
    check("a clan of three: the head, the officer with 0x400, the member without it",
          [p for _c, p in st.clan_member_perms(clan)], [65535, 0x402, 0x2])
    st.close()

    # --- a deposit, and the balance on the other holders' sockets -------------------------
    carol0 = afro_of(c)
    c.send("apply;number=300;action=3;")
    check("Carol, without 0x400, puts in 300: the purse, then 0",
          shape(c.frames()), [("userInfo_Player", carol0 - 300), ("cmdAck", 0)])
    got_a, got_b = a.frames(), b.frames()
    check("  ..the head and the officer get the balance unasked",
          (shape(got_a), shape(got_b)), ([("gg_list", 3, [300])], [("gg_list", 3, [300])]))
    check("  ..on the wire exactly as the page reads it", a.raw, ["gg_list;res=3;data=|300|;"])

    # --- a withdrawal, then the page's own question -----------------------------------------
    bob0 = afro_of(b)
    b.send("apply;number=-100;action=3;", "gg_info;det=3;")
    check("Bob takes 100 out and his page asks the balance: purse, 0, res=3 200, 0",
          shape(b.frames()), [("userInfo_Player", bob0 + 100), ("cmdAck", 0),
                              ("gg_list", 3, [200]), ("cmdAck", 0)])
    check("  ..the head hears 200", shape(a.frames()), [("gg_list", 3, [200])])
    check("  ..Carol, without the right, hears nothing", shape(c.frames()), [])

    # --- refusals ------------------------------------------------------------------------------
    c.send("apply;number=-50;action=3;")
    check("Carol takes 50 out without the right: gg_code 20, then 20",
          shape(c.frames()), [("gg_code", 20), ("cmdAck", 20)])
    c.send("apply;number=12.5;action=3;", "gg_info;det=3;")
    check("  ..12.5: 21; the balance, without the right: 20",
          shape(c.frames()), [("cmdAck", 21), ("cmdAck", 20)])
    a.send("gg_info;det=4;", "apply;number=100;action=4;")
    check("the head asks the gold balance, then puts gold in: 20, 21 -- the gold is off",
          shape(a.frames()), [("cmdAck", 20), ("cmdAck", 21)])
    b.frames()

    # --- a burst of five in one write ------------------------------------------------------------
    alice0 = afro_of(a)
    a.send("apply;number=10;action=3;", "gg_info;det=3;", "apply;number=-10;action=3;",
           "gg_info;det=4;", "apply;number=5;action=4;")
    check("five treasury commands in one write: one answer each, in order",
          shape(a.frames()), [("userInfo_Player", alice0 - 10), ("cmdAck", 0),
                              ("gg_list", 3, [210]), ("cmdAck", 0),
                              ("userInfo_Player", alice0), ("cmdAck", 0),
                              ("cmdAck", 20), ("cmdAck", 21)])
    check("  ..the officer saw 210, then 200", shape(b.frames()),
          [("gg_list", 3, [210]), ("gg_list", 3, [200])])

    # --- two clients take the whole treasury at the same moment -------------------------------
    alice0, bob0 = afro_of(a), afro_of(b)
    go = threading.Barrier(2)

    def take_all(cl):
        go.wait()
        cl.send("apply;number=-200;action=3;")

    workers = [threading.Thread(target=take_all, args=(cl,)) for cl in (a, b)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    got_a, got_b = a.frames(1.0), b.frames(1.0)
    answers = sorted(p["res"] for p in named(got_a, "cmdAck") + named(got_b, "cmdAck"))
    check("the head and the officer take the whole 200 at once: one 0, one 21", answers, [0, 21])
    check("  ..paid once", afro_of(a) - alice0 + afro_of(b) - bob0, 200)
    a.send("gg_info;det=3;")
    check("  ..and the treasury is empty", shape(a.frames()), [("gg_list", 3, [0]), ("cmdAck", 0)])
    b.frames()

    # --- a kicked member's page -------------------------------------------------------------------
    a.send("apply;number=%d;action=1;" % ids[CAROL])
    a.frames()
    b.frames()
    check("Carol is kicked: fellow reg=0", [p["reg"] for p in named(c.frames(), "fellow")], [0])
    carol0 = afro_of(c)
    c.send("apply;number=50;action=3;", "gg_info;det=3;")
    check("  ..her page, still open, puts 50 in and asks the balance: 20, 20",
          shape(c.frames()), [("cmdAck", 20), ("cmdAck", 20)])
    check("  ..her purse untouched", afro_of(c), carol0)

    # --- over a restart ----------------------------------------------------------------------------
    a.send("apply;number=777;action=3;")
    a.frames()
    for cl in (a, b, c):
        cl.close()
    srv.stop()
    srv = Server()
    a = srv.connect()
    enter(a, "alice", ALICE, new=False)
    a.send("gg_info;det=1;", "gg_info;det=3;")
    check("after a restart the head's page reads the treasury as it was: 777",
          shape(a.frames())[-2:], [("gg_list", 3, [777]), ("cmdAck", 0)])
    a.close()
    st = accounts.Store(DB)
    rows = st.clan_ledger_rows(clan, 1000)
    check("the treasury's journal: every move once, adding up to 777",
          (sorted({r["source"] for r in rows}), sum(r["afro"] for r in rows), st.clan_treasury(clan)),
          (["deposit", "withdraw"], 777, 777))
    moves = [r for name in (ALICE, BOB, CAROL)
             for r in st.ledger(st.character_by_name(name)["id"]) if r["source"] == "clan"]
    check("  ..and the purses' 'clan' rows are the same moves the other way round",
          (len(moves), sum(r["afro"] for r in moves)), (len(rows), -777))
    st.close()
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("clan treasury over the wire OK")
