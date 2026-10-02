"""The admin's clan tools end to end: the game server, the panel
(bootstrap_http.py) and tools/admin_account.py as separate processes with
only the database between them, and three players on real sockets.

A clan of three -- the head, an officer who may see the treasury, a
member. From the panel: the clan in the list and on a page of its own; the
treasury raised, and the balance arriving on both screens allowed to see
it; the lead handed to the officer, both told their new rights; the member
kicked, put out on his screen, his row gone from the others' rosters. From
the tool, while the game runs: a rename, answered with the game's own
words. From the panel again: a disband refused without its tick, then done
-- the treasury into the new head's purse on his screen and in the ledger,
everyone put out -- and the page of the clan that is no more still showing
what was done to it.

    LAVA_RES=.../lava/res python3 server/test_clan_admin_wire.py
"""
import http.client
import os
import random
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import accounts  # noqa: E402
from protocol import decode, escape  # noqa: E402

RUN = "%04d" % random.randrange(10000)
DB = os.path.join(tempfile.mkdtemp(), "clan_admin_wire.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _l in ("alice", "bob", "carol"):
    _st.register(_l + RUN, "secret")
_st.register("tester", "secret")
_st.close()
CRED = {l: accounts.credential(l + RUN, "secret") for l in ("alice", "bob", "carol")}
NAMES = {l: l.capitalize() + RUN for l in ("alice", "bob", "carol")}
CLAN = "Волки %s" % RUN
R_AFRO, R_CHAT = 0x400, 0x2

from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT, HTTP_PORT = free_port(), free_port()
BASE_ENV = dict(os.environ, LAVA_DB=DB)
BASE_ENV.pop("LAVA_DB_URL", None)


def spawn(script, **env):
    proc = subprocess.Popen([sys.executable, script], cwd=HERE, env=dict(BASE_ENV, **env),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []
    threading.Thread(target=lambda: log.extend(proc.stdout), daemon=True).start()
    return proc, log


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode("utf-8") + b"\x00")

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
        return [decode(f.decode("utf-8")) for f in parts if f]

    def until(self, pred, wait=5.0):
        """Frames until one satisfies pred (or the wait is over), and a
        little after it, for what follows in the same breath."""
        got = []
        end = time.time() + wait
        while time.time() < end:
            got += self.frames(0.2)
            if any(pred(n, p) for n, p in got):
                return got + self.frames(0.3)
        return got

    def close(self):
        self.s.close()


def clan_frames(frames):
    """The clan's frames about this client itself: a fellow about another
    player (his tag, id = his entity) is left out."""
    keep = ("cmdAck", "fellow", "gg_list", "gg_struct", "userInfo_Player")
    return [(n, p) for n, p in frames if n in keep and (n != "fellow" or p.get("id") == 0)]


def get(path, cookie):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (HTTP_PORT, path))
    req.add_header("Cookie", "lava_admin=" + cookie)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(fields, cookie):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request("http://127.0.0.1:%d/admin/do" % HTTP_PORT, data)
    req.add_header("Cookie", "lava_admin=" + cookie)
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.read().decode("utf-8", "replace")


def sign_in():
    conn = http.client.HTTPConnection("127.0.0.1", HTTP_PORT, timeout=5)
    body = urllib.parse.urlencode({"login": "tester", "password": "secret"})
    conn.request("POST", "/admin/login", body,
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    raw = resp.getheader("Set-Cookie") or ""
    conn.close()
    return raw.split(";")[0].split("=", 1)[1] if "=" in raw else ""


def wait_http(proc, log):
    end = time.time() + 20
    while time.time() < end:
        if proc.poll() is not None:
            raise SystemExit("panel exited:\n" + "".join(log)[-2000:])
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/status" % HTTP_PORT, timeout=1).read()
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit("panel did not start")


def queue_empty(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        st = accounts.Store(DB)
        try:
            left = st.db.execute("SELECT COUNT(*) c FROM admin_actions"
                                 " WHERE done_at IS NULL").fetchone()["c"]
        finally:
            st.close()
        if left == 0:
            return True
        time.sleep(0.2)
    return False


def db(fn):
    st = accounts.Store(DB)
    try:
        return fn(st)
    finally:
        st.close()


game, game_log = spawn("server.py", LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
                       LAVA_GX="6268", LAVA_GY="1819", LAVA_CHEATS="1",
                       LAVA_POLICY_PORT="0", LAVA_CLAN_DEAF_CHECK="0",
                       LAVA_ADMIN_POLL="0.2")
panel, panel_log = spawn("bootstrap_http.py", LAVA_HTTP_PORT=str(HTTP_PORT),
                         LAVA_GAME_PORT=str(PORT), LAVA_ADMINS="tester")
clients = []
try:
    def connect():
        end = time.time() + 15
        while time.time() < end:
            if game.poll() is not None:
                raise SystemExit("server exited:\n" + "".join(game_log)[-2000:])
            try:
                c = Client(socket.create_connection(("127.0.0.1", PORT), 0.5))
                clients.append(c)
                return c
            except OSError:
                time.sleep(0.1)
        raise SystemExit("server did not start")

    def enter(c, login):
        c.send("hello;minor=2;major=0;")
        c.send("login;hash=@%s@;" % CRED[login])
        c.frames()
        c.send("newPers;res=1;sex=0;name=@%s@;" % escape(NAMES[login]))
        c.frames()
        c.send("actPlayer;")
        c.frames()
        c.send("lenter;accept=1;")
        c.frames(1.0)

    a, b, c = connect(), connect(), connect()
    for cl, l in ((a, "alice"), (b, "bob"), (c, "carol")):
        enter(cl, l)
    a.send("userMsg;entry=@/money 0 1000@;group=0;")
    a.frames()
    a.send("head;reg=@x@;soc=@%s@;" % CLAN)
    got = a.frames()
    clan_id = [p["reg"] for n, p in got if n == "fellow" and p.get("id") == 0][0]
    for cl, l, perm in ((b, "bob", R_AFRO | R_CHAT), (c, "carol", R_CHAT)):
        a.send("admit;char=@%s@;perm=%d;post=@@;" % (NAMES[l], perm))
        a.frames()
        cl.frames()
        cl.send("apply;number=0;action=2;")
        cl.frames()
    for cl in (a, b, c):
        cl.send("gg_info;det=1;")
        cl.frames()
    ids = db(lambda s: {l: s.character_by_name(NAMES[l])["id"] for l in NAMES})

    wait_http(panel, panel_log)
    cookie = sign_in()
    check("the panel lets the admin in", bool(cookie), True)

    # --- the lists --------------------------------------------------------------------
    _code, page = get("/admin", cookie)
    check("the main page lists the clan, its head and its three members, linked to its page",
          ('href="/admin/clan?id=%d"' % clan_id in page, CLAN in page,
           "<td>%s</td><td class=num>3</td>" % NAMES["alice"] in page), (True, True, True))
    _code, page = get("/admin/clan?id=%d" % clan_id, cookie)
    check("the clan's page: the three members, the forms for the five orders",
          (all(NAMES[l] in page for l in NAMES),
           [('value=%s>' % op) in page for op in ("rename", "head", "treasury", "kick",
                                                  "disband")]),
          (True, [True] * 5))
    check("  ..the head's rights shown with his rank",
          "глава <span class=num>0xFFFF</span>" in page, True)

    # --- the treasury, from the panel -----------------------------------------------------
    _code, page = post({"kind": "clan", "op": "treasury", "clan": clan_id, "afro": 400},
                       cookie)
    check("the panel queues the treasury order and says so",
          "Правка казны поставлена в очередь" in page, True)
    res3 = lambda n, p: n == "gg_list" and p.get("res") == 3  # noqa: E731
    seen_a, seen_b = a.until(res3), b.until(res3)
    check("the game carries it out: the head and the officer with 0x400 see 400 at once",
          ([p["data"] for n, p in seen_a if res3(n, p)],
           [p["data"] for n, p in seen_b if res3(n, p)]), ([[400]], [[400]]))
    check("  ..the member without the right sees nothing of it",
          [p for n, p in c.frames(0.3) if res3(n, p)], [])
    check("  ..one 'admin' row in the clan's journal",
          db(lambda s: [(r["source"], r["afro"]) for r in s.clan_ledger_rows(clan_id)]),
          [("admin", 400)])

    # --- the lead, from the panel -------------------------------------------------------------
    post({"kind": "clan", "op": "head", "clan": clan_id, "char": ids["bob"]}, cookie)
    own = lambda n, p: n == "fellow" and p.get("id") == 0  # noqa: E731
    got_b, got_a = b.until(own), a.until(own)
    check("the lead to Bob: his client is told 65535, Alice's 0x2F67",
          ([p["perm"] for n, p in got_b if own(n, p)], [p["perm"] for n, p in got_a if own(n, p)]),
          ([65535], [0x2F67]))
    check("  ..and both rows reach every roster: act=3 twice to Carol",
          sorted((p["id"], p["perm"]) for n, p in c.until(lambda n, p: n == "gg_struct")
                 if n == "gg_struct"),
          sorted([(ids["alice"], 0x2F67), (ids["bob"], 65535)]))

    # --- a kick, from the panel -----------------------------------------------------------------
    post({"kind": "clan", "op": "kick", "clan": clan_id, "char": ids["carol"]}, cookie)
    got_c = c.until(own)
    check("Carol kicked: her client is put out -- fellow reg=0, standings emptied",
          [(n, p.get("reg", p.get("res"))) for n, p in clan_frames(got_c)],
          [("fellow", 0), ("gg_list", 0)])
    check("  ..and the rosters lose her row",
          ([(p["id"], p["act"]) for n, p in a.until(lambda n, p: n == "gg_struct")
            if n == "gg_struct"],
           [(p["id"], p["act"]) for n, p in b.until(lambda n, p: n == "gg_struct")
            if n == "gg_struct"]),
          ([(ids["carol"], 2)], [(ids["carol"], 2)]))

    # --- a rename, from the tool, while the game runs ---------------------------------------------
    new_name = "Серые %s" % RUN
    tool = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "admin_account.py"),
                           "clan-rename", CLAN, "--name", new_name, "--db", DB,
                           "--wait", "10"], env=BASE_ENV, capture_output=True, text=True,
                          timeout=60)
    check("the tool queues a rename and prints the game's answer (exit 0)",
          (tool.returncode, "done: «%s» → «%s»" % (CLAN, new_name) in tool.stdout),
          (0, True))
    check("  ..the clan is renamed", db(lambda s: s.clan(clan_id)["name"]), new_name)
    tool = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "admin_account.py"),
                           "clan-rename", new_name, "--name", "x", "--db", DB,
                           "--wait", "10"], env=BASE_ENV, capture_output=True, text=True,
                          timeout=60)
    check("  ..a name the game refuses: the refusal printed, in its words",
          (tool.returncode, "done: название не годится" in tool.stdout), (0, True))

    # --- the page after all that ------------------------------------------------------------------
    _code, page = get("/admin/clan?id=%d" % clan_id, cookie)
    check("the clan's page shows what the queue did: the treasury, the lead, the kick, the"
          " rename, by whom",
          ("казна «%s»: +400 афро, теперь 400" % CLAN in page,
           "глава «%s» теперь %s" % (CLAN, NAMES["bob"]) in page,
           "%s исключён из «%s»" % (NAMES["carol"], CLAN) in page,
           "<td>console</td>" in page, "<td>tester</td>" in page), (True,) * 5)
    check("  ..its journal the admin row, its roster two", (
        "<td>admin</td>" in page, NAMES["carol"] + "</b>" in page), (True, False))

    # --- a disband, from the panel --------------------------------------------------------------------
    _code, page = post({"kind": "clan", "op": "disband", "clan": clan_id, "payout": 0},
                       cookie)
    check("a disband without its tick is not queued",
          ("Роспуск не поставлен" in page, queue_empty(1)), (True, True))
    afro_b = db(lambda s: s.money(ids["bob"])[0])
    post({"kind": "clan", "op": "disband", "clan": clan_id, "payout": 0, "confirm": 1},
         cookie)
    got_b = b.until(lambda n, p: own(n, p) and p.get("reg") == 0)
    check("disbanded, the treasury to the head (Bob, playing): his purse on his screen, then"
          " he is put out",
          [(n, p.get("afro") if n == "userInfo_Player" else p.get("reg", p.get("res")))
           for n, p in clan_frames(got_b) if n != "gg_struct"],
          [("userInfo_Player", afro_b + 400), ("fellow", 0), ("gg_list", 0)])
    check("  ..Alice put out too",
          [(n, p.get("reg", p.get("res"))) for n, p in
           clan_frames(a.until(lambda n, p: own(n, p) and p.get("reg") == 0))],
          [("fellow", 0), ("gg_list", 0)])
    check("  ..both journals: clan_disband into Bob's purse, 'disband' out of the treasury;"
          " the clan gone",
          db(lambda s: ([(r["source"], r["afro"]) for r in s.ledger(ids["bob"])][-1],
                        s.clan_ledger_rows(clan_id)[0]["source"], s.clan(clan_id))),
          (("clan_disband", 400), "disband", None))
    b.send("logout;")
    b.frames()
    check("  ..and Bob's save at logout keeps it", db(lambda s: s.money(ids["bob"])[0]),
          afro_b + 400)
    _code, page = get("/admin/clan?id=%d" % clan_id, cookie)
    check("the page of a clan that is no more says so, and what was done to it",
          ("Клана #%d нет" % clan_id in page,
           "клан «%s» распущен (членов: 2)" % new_name in page), (True, True))
    _code, page = get("/admin", cookie)
    check("the main page: no clans left", "Кланов пока нет." in page, True)
finally:
    for cl in clients:
        try:
            cl.close()
        except OSError:
            pass
    for proc in (panel, game):
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    if os.environ.get("LAVA_TEST_LOG"):
        print("".join(game_log)[-4000:])
    sys.exit(1)
print("clan admin over the wire OK")
