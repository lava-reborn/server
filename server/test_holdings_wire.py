"""The warehouses' flag over real sockets (server/holdings.py): three clients
against a server of its own.

What test_holdings.py checks in process, seen from the wire. In the Северный
склад (111) a clan holds, the flag's userInfo_Trader carries clan= and is
followed at once by a fellow about the flag's own id, which names the clan
for any viewer -- a member of the holding clan with repair, a member of
another clan and a player in no clan without it, nothing for sale to
anybody. Донгола's flag (112), a warehouse nobody can take yet, is drawn as
before: for sale, mending, no clan, no fellow. Then the admin's orders,
queued as the panel and tools/admin_account.py queue them (clan_admin.py
hold and release): a release sends everybody in the room the flag again
naming nobody and, on the room's next tick, the money box under a new id,
so the client asks its rows afresh; a hold for another clan names it, and
mends for its member alone.

    LAVA_RES=.../lava/res python3 server/test_holdings_wire.py
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
import clans  # noqa: E402
from protocol import decode  # noqa: E402

RUN = "%04d" % random.randrange(10000)
DB = os.path.join(tempfile.mkdtemp(), "holdings_wire.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _l in ("alice", "bob", "carol"):
    _st.register(_l + RUN, "secret")
_st.close()
CRED = {l: accounts.credential(l + RUN, "secret") for l in ("alice", "bob", "carol")}
ALICE, BOB, CAROL = "Alice" + RUN, "Bob" + RUN, "Carol" + RUN
WOLVES, JACKALS = "Волки " + RUN, "Шакалы " + RUN
SEVER, DONGOLA = 111, 112
FLAG, BOX = 1011, 6824

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self):
        self.port = free_port()
        # Noon in Moscow: no box window opens or shuts on its own while the
        # suite runs, so a box shown anew is the holder's change.
        env = dict(os.environ, LAVA_PORT=str(self.port), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
                   LAVA_GX="6268", LAVA_GY="1819", LAVA_CHEATS="1", LAVA_POLICY_PORT="0",
                   LAVA_CLAN_DEAF_CHECK="0", LAVA_ADMIN_POLL="0.2",
                   LAVA_BOSS_CLOCK="2026-10-09T12:00:00")
        env.pop("LAVA_SERVER_CHAT", None)
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

    def _recv(self, timeout):
        self.s.settimeout(max(0.01, timeout))
        try:
            chunk = self.s.recv(65536)
        except socket.timeout:
            return False
        if not chunk:
            return False
        self.buf += chunk
        return True

    def _drain(self):
        parts = self.buf.split(b"\x00")
        self.buf = parts.pop()
        return [decode(f.decode(ENC)) for f in parts if f]

    def frames(self, wait=0.6):
        deadline = time.time() + wait
        while time.time() < deadline:
            if not self._recv(deadline - time.time()):
                break
        return self._drain()

    def until(self, pred, wait=4.0):
        out = []
        deadline = time.time() + wait
        while time.time() < deadline:
            self._recv(deadline - time.time())
            new = self._drain()
            out += new
            if any(pred(f) for f in new):
                break
        return out

    def close(self):
        self.s.close()


def named(frames, name):
    return [p for n, p in frames if n == name]


def enter(c, login, name):
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED[login])
    c.frames()
    c.send("newPers;res=1;sex=0;name=@%s@;" % name)
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    c.frames()


def goto(c, loc):
    """/goto and the client's lenter: the frames of the arrival."""
    c.send("userMsg;entry=@/goto %d@;group=0;" % loc)
    c.until(lambda f: f[0] == "lcall")
    c.send("lenter;accept=1;")
    return c.frames(1.2)


def flag_of(frames):
    """The flag's userInfo_Trader and the frame right after it."""
    for i, (n, p) in enumerate(frames):
        if n == "userInfo_Trader" and p.get("name") == FLAG:
            return p, (frames[i + 1] if i + 1 < len(frames) else None)
    return None, None


def about(frames, eid, name=None):
    return [(n, p) for n, p in frames if p.get("id") == eid and (name is None or n == name)]


def order(op, clan, site="wh_sever", wait=5.0):
    """One clan order queued as the panel queues it, and the game's answer."""
    st = accounts.Store(DB)
    try:
        aid = st.admin_push("tester", "clan", op=op, clan=clan, site=site)
        end = time.time() + wait
        while time.time() < end:
            st.db.commit()
            row = st.db.execute("SELECT done_at, result FROM admin_actions WHERE id = ?",
                                (aid,)).fetchone()
            if row["done_at"] is not None:
                return row["result"]
            time.sleep(0.1)
        return None
    finally:
        st.close()


srv = Server()
try:
    a, b, c = srv.connect(), srv.connect(), srv.connect()
    enter(a, "alice", ALICE)
    enter(b, "bob", BOB)
    enter(c, "carol", CAROL)
    st = accounts.Store(DB)
    char_a = st.character_by_name(ALICE)["id"]
    char_b = st.character_by_name(BOB)["id"]
    wolves = st.clan_create(char_a, WOLVES, clans.name_key(WOLVES), "", None)
    jackals = st.clan_create(char_b, JACKALS, clans.name_key(JACKALS), "", None)
    st.close()
    check("the Волки hold the Северный склад by the admin's order",
          order("hold", wolves), "склад «Северный склад Вади-Хальфы» теперь за кланом «%s»"
          " (был ничей)" % WOLVES)

    # --- the flag in the site's room, per viewer --------------------------------------
    arrived = {who: goto(cl, SEVER) for who, cl in (("alice", a), ("bob", b), ("carol", c))}
    flag, after = flag_of(arrived["alice"])
    flag_id = flag["id"] if flag else None
    box_id = next((p["id"] for p in named(arrived["alice"], "userInfo_Commoner")
                   if p.get("name") == BOX), None)
    check("alice of the Волки: the flag sells nothing, mends, names the Волки",
          {k: flag.get(k) for k in ("can_trade", "can_repair", "clan")} if flag else None,
          {"can_trade": 0, "can_repair": 1, "clan": wolves})
    check("  ..and the very next frame is the fellow about the flag's id, the clan's name in"
          " soc", after, ("fellow", {"id": flag_id, "reg": wolves, "soc": WOLVES}))
    for who in ("bob", "carol"):
        flag, after = flag_of(arrived[who])
        check("%s, %s: the same caption and clan, and no repair" % (
            who, "of the Шакалы" if who == "bob" else "in no clan"),
            ({k: flag.get(k) for k in ("can_trade", "can_repair", "clan")} if flag else None,
             after), ({"can_trade": 0, "can_repair": 0, "clan": wolves},
                      ("fellow", {"id": flag_id, "reg": wolves, "soc": WOLVES})))

    # --- Донгола's flag: as it always was --------------------------------------------
    got = goto(c, DONGOLA)
    flag, after = flag_of(got)
    check("Донгола's flag (112): for sale and mending, no clan",
          {k: flag.get(k) for k in ("can_trade", "can_repair", "clan")} if flag else None,
          {"can_trade": 1, "can_repair": 1, "clan": None})
    check("  ..and no fellow about it", about(got, flag["id"] if flag else -1, "fellow"), [])
    goto(c, SEVER)
    for cl in (a, b, c):
        cl.frames(0.3)

    # --- the admin's orders, while they stand there -----------------------------------
    check("the release, queued: done", order("release", wolves),
          "склад «Северный склад Вади-Хальфы» больше не за кланом «%s»: теперь он ничей" % WOLVES)
    got = {who: cl.until(lambda f: f[0] == "lch" and f[1].get("lostUser") == box_id)
           for who, cl in (("alice", a), ("bob", b), ("carol", c))}
    for who in ("alice", "bob", "carol"):
        sent = about(got[who], flag_id)
        check("%s is sent the flag again: no clan, no repair, and no fellow" % who,
              [(n, p.get("clan"), p.get("can_repair")) for n, p in sent],
              [("userInfo_Trader", None, 0)])
    news = [p["newUser"] for n, p in got["carol"] + c.frames(0.8)
            if n == "lch" and "newUser" in p]
    check("  ..and on the room's next tick the box goes and comes back under a new id",
          (any(f == ("lch", {"lostUser": box_id}) for f in got["carol"]), len(news),
           news[0] != box_id if news else None), (True, 1, True))
    for cl in (a, b):
        cl.frames(0.5)
    check("a hold for the Шакалы, queued: done", order("hold", jackals),
          "склад «Северный склад Вади-Хальфы» теперь за кланом «%s» (был ничей)" % JACKALS)
    got = b.until(lambda f: f[0] == "fellow" and f[1].get("id") == flag_id)
    check("bob of the Шакалы is sent the flag naming his clan, mending for him, the fellow"
          " after it", [(n, p.get("clan"), p.get("can_repair")) if n == "userInfo_Trader"
                        else (n, p) for n, p in about(got, flag_id)],
          [("userInfo_Trader", jackals, 1), ("fellow", {"id": flag_id, "reg": jackals,
                                                        "soc": JACKALS})])
    got = a.until(lambda f: f[0] == "fellow" and f[1].get("id") == flag_id)
    check("  ..alice of the Волки the same caption, mending no more",
          [(n, p.get("clan"), p.get("can_repair")) for n, p in about(got, flag_id)
           if n == "userInfo_Trader"], [("userInfo_Trader", jackals, 0)])
    check("no line of it in anybody's chat",
          [n for cl in (a, b, c) for n, _p in cl.frames(0.3) if n == "userMsg"], [])
    for cl in (a, b, c):
        cl.send("logout;")
        cl.close()
finally:
    srv.stop()
    log = "".join(srv.log)
    if "Traceback" in log:
        fails.append("server logged a traceback:\n" + log[-3000:])
    elif fails:
        fails.append("server log, its end:\n" + log[-3000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("holdings over the wire OK")
