"""Stance steps ordered on the site, over real sockets: the game in a
process of its own, and the site's rows written into its database through
a connection of their own, the way lava-site writes them (api/db.py
queue_stance) -- three clients, two members of one clan and the head of
another, standing together.

What test_site_orders.py checks in process, seen from the wire: a row
carried out by the game's admin loop within a pass or two, its answer the
words the site shows; the frames the in-game button sends, res=8 with the
enemy's fresh tag to our side, res=9 to theirs, the balance to the head --
and no cmdAck, there being no command; a refusal that nobody hears; an
order for a character who is not playing; nothing in the admin's queue.
And a stop: a row the site wrote while the game was down and still fresh
when it comes back is carried out then, one older than a minute is refused
with the stance untouched, and the stance made is in our head's standings
at her next login.

    LAVA_RES=.../lava/res python3 server/test_site_orders_wire.py
"""
import os
import random
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"
# The site's connection here is a sqlite3 one to the server's file: the
# game, the suite's Store and the "site" all on that file, Postgres or not.
os.environ.pop("LAVA_DB_URL", None)
sys.path.insert(0, HERE)
import accounts  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
DB = os.path.join(tempfile.mkdtemp(), "site_orders_wire.db")
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
        # The admin loop's pass, short, so that an order waits a moment.
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
                   LAVA_GX="6268", LAVA_GY="1819", LAVA_CHEATS="1", LAVA_POLICY_PORT="0",
                   LAVA_CLAN_DEAF_CHECK="0", LAVA_ADMIN_POLL="0.2")
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


CLAN = ("cmdAck", "fellow", "invite", "gg_list", "gg_struct", "gg_code", "userInfo_Player",
        "userMsg")


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


def site():
    """The site's own connection to the database, not the game's Store."""
    return sqlite3.connect(DB, timeout=5)


def order(char_id, login, clan_id, other, stat_from, step, made_at=None):
    """A row as lava-site's queue_stance writes it: bound parameters only."""
    with site() as db:
        cur = db.execute(
            "INSERT INTO site_orders (made_at, login, char_id, clan_id, other, stat_from, dir)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (time.time() if made_at is None else made_at, login + RUN, char_id, clan_id,
             other, stat_from, step))
        return cur.lastrowid


def answer(oid, wait=6.0):
    """What the site would read back, polling as it does: (code, result)
    once done_at is set, None if it never is within `wait`."""
    deadline = time.time() + wait
    while True:
        with site() as db:
            row = db.execute("SELECT done_at, code, result FROM site_orders WHERE id = ?",
                             (oid,)).fetchone()
        if row[0] is not None:
            return row[1], row[2]
        if time.time() > deadline:
            return None
        time.sleep(0.1)


def char_id(name):
    with site() as db:
        return db.execute("SELECT id FROM characters WHERE name = ?", (name,)).fetchone()[0]


def queued():
    with site() as db:
        return db.execute("SELECT COUNT(*) FROM admin_actions").fetchone()[0]


srv = Server()
try:
    a, b, c = srv.connect(), srv.connect(), srv.connect()
    enter(a, "alice", ALICE)
    enter(b, "bob", BOB)
    enter(c, "carol", CAROL)
    for x in (a, b, c):
        x.frames()

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
    b.frames()
    for x in (a, b, c):
        x.frames()
    alice_id = char_id(ALICE)

    # --- war, ordered on the site ---------------------------------------------------------
    st = accounts.Store(DB)
    st.clan_treasury_adjust(wolves, 150, "admin")
    st.close()
    war = order(alice_id, "alice", wolves, foxes, 0, -1)
    check("the site's order answered by the game: OK, in the site's words", answer(war),
          ("OK", "Готово: отношение клана «%s» к клану «%s» теперь — война."
                 " Из казны списано 100 афро." % (WOLVES, FOXES)))
    got = a.frames()
    check("  ..our head: res=8, the enemy's fresh tag, the balance -- no cmdAck",
          shape(got), [("gg_list", 8), ("fellow", foxes), ("gg_list", 3)])
    check("  ..res=8 names them, at war; res=3 has the 50 left", named(got, "gg_list"),
          [{"res": 8, "data": [foxes], "names": [FOXES], "stats": [-1]},
           {"res": 3, "data": [50]}])
    check("  ..our other member: res=8, then the tag", shape(b.frames()),
          [("gg_list", 8), ("fellow", foxes)])
    got = c.frames()
    check("  ..their head: res=9 alone", (shape(got), named(got, "gg_list")),
          ([("gg_list", 9)], [{"res": 9, "data": [wolves], "names": [WOLVES], "stats": [-1]}]))

    # --- a refusal ---------------------------------------------------------------------------
    short = order(alice_id, "alice", wolves, foxes, -1, 1)
    check("a step up with 50 in the treasury: R5", answer(short),
          ("R5", "В казне клана «%s» меньше 1.000 афро." % WOLVES))
    check("  ..and nobody hears a thing",
          (shape(a.frames(0.3)), shape(b.frames(0.3)), shape(c.frames(0.3))), ([], [], []))

    # --- an order for a character who is not playing ----------------------------------------
    a.send("logout;")
    a.close()
    time.sleep(0.5)
    st = accounts.Store(DB)
    st.clan_treasury_adjust(wolves, 1000, "admin")
    st.close()
    calm = order(alice_id, "alice", wolves, foxes, -1, 1)
    check("our head logged out, her order still carried out", answer(calm),
          ("OK", "Готово: отношение клана «%s» к клану «%s» теперь — нейтралитет."
                 " Из казны списано 1.000 афро." % (WOLVES, FOXES)))
    check("  ..our member: res=8 with neutrality and the tag; their head: res=9",
          ([p["stats"] for p in named(b.frames(), "gg_list")],
           [p["stats"] for p in named(c.frames(), "gg_list")]), ([[0]], [[0]]))
    check("the admin's queue never saw a row", queued(), 0)
    for x in (b, c):
        x.send("logout;")
        x.close()
    time.sleep(0.5)
    srv.stop()

    # --- orders written while the game was down ---------------------------------------------
    st = accounts.Store(DB)
    st.clan_treasury_adjust(wolves, 100, "admin")
    st.close()
    stale = order(alice_id, "alice", wolves, foxes, 0, 1, made_at=time.time() - 61)
    fresh = order(alice_id, "alice", wolves, foxes, 0, -1)
    srv = Server()
    a = srv.connect()
    check("the game back: the order older than a minute refused, R6",
          answer(stale), ("R6", "Игровой сервер не успел выполнить приказ, отношения не"
                                " изменились. Попробуйте ещё раз."))
    check("  ..the fresh one carried out", answer(fresh),
          ("OK", "Готово: отношение клана «%s» к клану «%s» теперь — война."
                 " Из казны списано 100 афро." % (WOLVES, FOXES)))
    st = accounts.Store(DB)
    check("  ..one step made: war, 100 out; ours alone",
          (st.clan_relation(wolves, foxes), st.clan_relation(foxes, wolves),
           st.clan_treasury(wolves)), (-1, 0, 50))
    check("  ..the journal's 'diplomacy' rows: the three steps carried out, ref them",
          [(r["source"], r["afro"], r["ref"]) for r in reversed(st.clan_ledger_rows(wolves))
           if r["source"] == "diplomacy"],
          [("diplomacy", -100, foxes), ("diplomacy", -1000, foxes), ("diplomacy", -100, foxes)])
    st.close()
    pre, got = enter(a, "alice", ALICE, new=False)
    check("  ..and our head's login standings carry the war",
          standings(pre + got, mine), [{foxes: -1}])
    check("the site orders' lines are in the game's log, the stale one's too",
          [any(("site order %d " % oid) in line or ("site order %d:" % oid) in line
               for line in srv.log) for oid in (stale, fresh)],
          [True, True])
    a.close()
finally:
    srv.stop()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("site orders over the wire OK")
