"""A stop announced ahead: the countdown the players see before a restart.

A deploy used to restart the game with no word before it: the one frame
the players got, «shutdown;seconds=0;», came with the socket closing behind
it (issue #73). Now the deploy announces the stop and waits it out
(server/stopwarn.py), and the client's own alert counts it down.

The game server, the panel (bootstrap_http.py) and stopwarn.py's command
line run as separate processes with only the database between them, and
the players are real sockets:

  - the numbers told: a minute apart, then 30 and 10, all multiples of five;
  - nobody logged in: nothing announced, nothing to wait for;
  - what may not announce one: a player's frame, an order out of range or
    stale, the panel without its tick or its cookie, the command line out
    of range;
  - the panel announces one, shows it and calls it off, and a second
    announcement leaves the time the players were told as it was;
  - called off, the frames stop and the game plays on;
  - a countdown nobody ends -- the deploy died -- is forgotten after its
    grace, and the players hear nothing more of it;
  - a countdown to its end: the frames in order and on time, a player who
    logs in half-way told what is left once and not again; then the stop
    itself, its 0 to everyone, the position saved (test_shutdown's half);
  - the game gone: the command line says so and withdraws its order.

    LAVA_RES=.../lava/res python3 server/test_stopwarn.py
"""
import http.client
import os
import re
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
ENC = "utf-8"
sys.path.insert(0, HERE)
import accounts  # noqa: E402
import storage  # noqa: E402
import stopwarn  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
HTTP_PORT = free_port()

# Three accounts: the admin, and two players with a character each. Under
# LAVA_DB_URL the Store and the processes below all follow it to Postgres.
DB = os.path.join(tempfile.mkdtemp(), "stopwarn.db")
accounts.DB_PATH = DB
_st = accounts.Store(DB)
for _login in ("tester", "alice", "bob"):
    _acc, _err = _st.register(_login, "secret")
    _st.create_character(_acc, _login, 0, "1")
_st.close()
CRED = {l: accounts.credential(l, "secret") for l in ("tester", "alice", "bob")}

# The market of test_shutdown, so a walk ends on a cell it knows; the queue
# read five times a second, so an order is answered in a moment; and a
# countdown whose time is up forgotten after GRACE seconds rather than two
# minutes -- long enough for the stop below to come inside it.
GRACE = 8
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_GX="5970", LAVA_GY="1730", LAVA_ADMIN_POLL="0.2",
           LAVA_POLICY_PORT="0", LAVA_STOP_GRACE=str(GRACE))
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

http_env = dict(os.environ, LAVA_HTTP_PORT=str(HTTP_PORT), LAVA_HTTP_HOST="127.0.0.1",
                LAVA_DB=DB, LAVA_GAME_PORT=str(PORT), LAVA_ADMINS="tester")
web = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=http_env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_hlog = []
threading.Thread(target=lambda: _hlog.extend(web.stdout), daemon=True).start()


class Client:
    """A game socket whose every frame is kept, in order, as it arrives."""

    def __init__(self):
        self.s = testkit.connect(PORT, srv, _log)
        self.s.settimeout(None)
        self.got = []
        self.eof = False
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        buf = b""
        while True:
            try:
                chunk = self.s.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            *done, buf = buf.split(b"\x00")
            for f in done:
                if f:
                    self.got.append((time.time(), f.decode(ENC)))
        self.eof = True

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def mark(self):
        return len(self.got)

    def since(self, i=0):
        return [f for _t, f in self.got[i:]]

    def stops(self, i=0):
        """The shutdown frames since i, as their numbers."""
        return [int(re.search(r"seconds=(-?\d+)", f).group(1))
                for f in self.since(i) if f.startswith("shutdown;")]

    def wait(self, pred, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.05)
        return pred()

    def wait_frame(self, name, i=0, timeout=5.0):
        return self.wait(lambda: any(f.split(";")[0] == name for f in self.since(i)), timeout)

    def login(self, who):
        i = self.mark()
        self.send("hello;minor=2;major=0;")
        self.send("login;hash=@%s@;" % CRED[who])
        self.wait_frame("accountInfo", i)
        return i

    def enter(self):
        i = self.mark()
        self.send("selPers;num=0;")
        self.wait_frame("lcall", i)
        self.send("lenter;accept=1;")
        self.wait_frame("lenter", i)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def cli(*args):
    """stopwarn.py as the deploy runs it: (exit status, its line)."""
    p = subprocess.run([sys.executable, "stopwarn.py"] + [str(a) for a in args],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout.strip()


def db_one(sql, args=()):
    db = storage.connect(DB)
    try:
        row = db.execute(sql, args).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def order(kind, made_at=None, **args):
    """An admin_actions row as anything with the database could write it,
    and the game's answer to it."""
    import json
    db = storage.connect(DB)
    try:
        new_id = db.insert(
            "INSERT INTO admin_actions (made_at, admin, kind, char_id, account_id,"
            " args_json) VALUES (?, 'test', ?, NULL, NULL, ?)",
            (int(made_at or time.time()), kind, json.dumps(args)), returning="id")
        db.commit()
        end = time.time() + 10
        while time.time() < end:
            db.commit()
            row = db.execute("SELECT done_at, result FROM admin_actions WHERE id = ?",
                             (new_id,)).fetchone()
            if row["done_at"] is not None:
                return row["result"]
            time.sleep(0.1)
        return None
    finally:
        db.close()


def orders():
    return db_one("SELECT COUNT(*) AS n FROM admin_actions")["n"]


def wait_http(timeout=testkit.START_WAIT):
    end = time.time() + timeout
    while time.time() < end:
        if web.poll() is not None:
            raise SystemExit("http exited:\n" + "".join(_hlog)[-1500:])
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/status" % HTTP_PORT, timeout=1).read()
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit("http did not start:\n" + "".join(_hlog)[-1500:])


def sign_in():
    conn = http.client.HTTPConnection("127.0.0.1", HTTP_PORT, timeout=5)
    conn.request("POST", "/admin/login",
                 urllib.parse.urlencode({"login": "tester", "password": "secret"}),
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    resp.read()
    raw = resp.getheader("Set-Cookie") or ""
    conn.close()
    return raw.split(";")[0].split("=", 1)[1] if "=" in raw else ""


def page(path="/admin", fields=None, cookie=None):
    data = urllib.parse.urlencode(fields).encode() if fields is not None else None
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (HTTP_PORT, path), data)
    if cookie:
        req.add_header("Cookie", "lava_admin=" + cookie)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace")


def note_of(body):
    m = re.search(r'<p class="msg ok">(.*?)</p>', body, re.S)
    return m.group(1) if m else ""


def status_until(ok, timeout=5.0):
    """status, asked again until its line is what ok() wants: who is logged
    in reaches the row on the game's next pass of the queue, not at once."""
    end = time.time() + timeout
    while True:
        rc, line = cli("status")
        if (rc == 0 and ok(line)) or time.time() >= end:
            return rc, line
        time.sleep(0.2)


def left_of(line):
    """The seconds of a "LEFT PLAYERS" line, None for "-"."""
    head = line.split()[0] if line else "?"
    return None if head == "-" else int(head)


clients = []
out = ""
try:
    # --- the numbers told -------------------------------------------------
    check("180 s: the minutes below it, then 30 and 10", stopwarn.marks(180), [120, 60, 30, 10])
    check("ten minutes: every whole minute", stopwarn.marks(600),
          [540, 480, 420, 360, 300, 240, 180, 120, 60, 30, 10])
    check("200 s: from the first whole minute", stopwarn.marks(200), [180, 120, 60, 30, 10])
    check("45 s: the last minute's two", stopwarn.marks(45), [30, 10])
    check("20 s: 10 only", stopwarn.marks(20), [10])
    check("10 s: nothing after the first", stopwarn.marks(10), [])
    check("what is left, rounded down to five", [stopwarn.spoken(s) for s in (33.9, 180, 35, 4.9)],
          [30, 180, 35, 0])
    told = {m for s in range(stopwarn.MIN_SECONDS, stopwarn.MAX_SECONDS + 1)
            for m in stopwarn.marks(s) + [stopwarn.spoken(s)]}
    check("every number any countdown tells reads right before «секунд»",
          sorted(n for n in told if n % 5), [])

    wait_http()
    # The game listens, then writes the row on its first pass of the queue.
    testkit.connect(PORT, srv, _log).close()
    end = time.time() + testkit.START_WAIT
    st = (None, None)
    while time.time() < end:
        st = cli("status")
        if st[0] == 0 or srv.poll() is not None:
            break
        time.sleep(0.3)
    check("status: nobody logged in, no stop", st, (0, "- 0"))

    # --- nobody logged in: nothing to wait for ------------------------------
    # A socket at the login screen is not a player: a stop does not wait on it.
    probe = Client()
    clients.append(probe)
    probe.send("hello;minor=2;major=0;")
    probe.wait_frame("hello")
    check("start --skip-empty with nobody logged in: nothing announced",
          cli("start", 60, "--by", "test", "--skip-empty"), (0, "- 0"))
    check("and the row says so", db_one("SELECT stop_at FROM stop_plan WHERE id = 1"),
          {"stop_at": None})

    # --- a player's frame cannot announce one ---------------------------------
    alice = Client()
    clients.append(alice)
    alice.login("alice")
    alice.enter()
    check("alice is in", status_until(lambda l: l == "- 1"), (0, "- 1"))
    i = alice.mark()
    alice.send("stop;seconds=20;")
    alice.send("stop_cancel;")
    alice.send("shutdown;seconds=20;")
    time.sleep(1.0)
    check("a client's stop, stop_cancel or shutdown frame does nothing",
          (alice.stops(i), cli("status")), ([], (0, "- 1")))
    check("the game took them for unknown commands",
          sum(1 for l in _log if "unimplemented command 'stop" in l
              or "unimplemented command 'shutdown'" in l), 3)

    # --- orders it refuses --------------------------------------------------------
    i = alice.mark()
    got = order("stop", seconds=5)
    check("an order under the shortest is refused",
          (got or "").startswith(stopwarn.REFUSED), True)
    got = order("stop", seconds=stopwarn.MAX_SECONDS + 1)
    check("an order over the longest is refused", (got or "").startswith(stopwarn.REFUSED), True)
    got = order("stop", seconds="soon")
    check("an order without a number is refused", (got or "").startswith(stopwarn.REFUSED), True)
    got = order("stop", made_at=time.time() - stopwarn.ORDER_FRESH - 30, seconds=60)
    check("an order that waited past ORDER_FRESH is refused",
          (got or "").startswith(stopwarn.REFUSED) and "устарел" in got, True)
    n = orders()
    check("the command line refuses 5 s itself", cli("start", 5)[0], 2)
    check("and 601 s", cli("start", 601)[0], 2)
    check("and queues nothing for either", orders(), n)
    time.sleep(0.5)
    check("none of them told alice anything", alice.stops(i), [])
    check("nor announced a stop", cli("status"), (0, "- 1"))
    check("a cancel with nothing to cancel says so", order("stop_cancel"), "отменять нечего")

    # --- the panel ------------------------------------------------------------------
    COOKIE = sign_in()
    body = page(cookie=COOKIE)
    check("the panel offers the stop, 3 minutes by default",
          ("Объявить остановку" in body, 'name=minutes value=3 ' in body), (True, True))
    n = orders()
    body = page("/admin/do", {"kind": "stop", "minutes": "1", "confirm": "1"})
    check("without the cookie: the sign-in form", "name=password" in body, True)
    body = page("/admin/do", {"kind": "stop", "minutes": "1"}, COOKIE)
    check("without the tick: refused", note_of(body),
          "Остановка не объявлена: отметьте «да, предупредить игроков»")
    body = page("/admin/do", {"kind": "stop", "minutes": "11", "confirm": "1"}, COOKIE)
    check("eleven minutes: refused", note_of(body), "Остановка не объявлена: от 1 до 10 минут")
    body = page("/admin/do", {"kind": "stop", "minutes": "0", "confirm": "1"}, COOKIE)
    check("zero minutes: refused", note_of(body), "Остановка не объявлена: от 1 до 10 минут")
    check("none of them queued an order", orders(), n)
    check("nor told alice anything", alice.stops(i), [])

    i = alice.mark()
    body = page("/admin/do", {"kind": "stop", "minutes": "1", "confirm": "1"}, COOKIE)
    check("one minute, ticked: the game's answer on the page", note_of(body),
          "Игровой сервер: остановка через 60 с, в игре 1")
    alice.wait(lambda: alice.stops(i), 3)
    check("alice is told at once: 60 seconds", alice.stops(i), [60])
    check("the page shows the stop under way, with who and the way to call it off",
          ("Сервер будет остановлен через" in body, "объявил <b>tester</b>" in body,
           "Отменить остановку" in body, "Объявить остановку" in body),
          (True, True, True, False))
    rc, line = cli("status")
    check("status: the stop within the minute, alice logged in",
          (rc, 50 <= (left_of(line) or 0) <= 61, line.split()[-1]), (0, True, "1"))
    rc, line = cli("start", 300, "--by", "test")
    check("a second announcement leaves the first one's time",
          (rc, 0 < (left_of(line) or 0) <= 61), (0, True))
    check("the game said so", db_one("SELECT result FROM admin_actions ORDER BY id DESC")["result"]
          .startswith("уже объявлена (tester)"), True)
    time.sleep(0.5)
    check("and told alice nothing more", alice.stops(i), [60])
    body = page("/admin/do", {"kind": "stop_cancel"}, COOKIE)
    check("called off from the panel", note_of(body).startswith("Игровой сервер: отменена (оставалось"),
          True)
    check("the page offers the form again", "Объявить остановку" in body, True)
    check("the log names both, by who", ("остановка через 60 с" in body, "отмена остановки" in body,
                                         "<td>test</td><td>остановка через 300 с</td>" in body),
          (True, True, True))
    check("status: no stop", cli("status"), (0, "- 1"))

    # --- called off: the frames stop, the game plays on -----------------------------
    i = alice.mark()
    rc, line = cli("start", 15, "--by", "test")
    check("15 s announced from the command line", (rc, left_of(line) in (15, 16), line.split()[-1]),
          (0, True, "1"))
    alice.wait(lambda: alice.stops(i), 3)
    check("alice told 15", alice.stops(i), [15])
    t_start = time.time()
    check("called off from the command line", cli("cancel", "--by", "test"), (0, "- 1"))
    # The 10 would have come five seconds in.
    time.sleep(max(0.0, t_start + 7 - time.time()))
    check("no frame after the calling off", alice.stops(i), [15])
    j = alice.mark()
    alice.send("moveTo;path=|490|491|492|;")
    alice.wait(lambda: "userMove" in [f.split(";")[0] for f in alice.since(j)], 3)
    check("the game plays on: alice walks", [f.split(";")[0] for f in alice.since(j)][:2],
          ["cmdAck", "userMove"])
    check("and her socket is open", alice.eof, False)

    # --- a countdown nobody ends: forgotten after the grace -------------------------
    i = alice.mark()
    rc, line = cli("start", 10, "--by", "test")
    check("10 s announced", (rc, left_of(line) in (10, 11)), (0, True))
    alice.wait(lambda: alice.stops(i), 3)
    rc, line = status_until(lambda l: l.startswith("0 "), 15)
    t_due = time.time()
    check("its time is up and nobody restarts: status says 0", (rc, line), (0, "0 1"))
    rc, line = status_until(lambda l: l.startswith("- "), GRACE + 8)
    check("forgotten after the grace, not before",
          (rc, line, GRACE - 2 <= time.time() - t_due <= GRACE + 4), (0, "- 1", True))
    check("alice was told 10 and nothing more, and plays on", (alice.stops(i), alice.eof),
          ([10], False))

    # --- a countdown to its end --------------------------------------------------------
    i = alice.mark()
    t0 = time.time()
    rc, line = cli("start", 35, "--by", "test")
    check("35 s announced", (rc, left_of(line) in (35, 36)), (0, True))
    alice.wait(lambda: alice.stops(i), 3)
    check("alice told 35 at once", alice.stops(i), [35])
    # The game's own moment of the start, as near as a socket can see it.
    t35 = next((t for t, f in alice.got[i:] if f == "shutdown;seconds=35;"), t0)
    time.sleep(max(0.0, t35 + 1.5 - time.time()))
    bob = Client()
    clients.append(bob)
    b0 = bob.login("bob")
    bob.wait(lambda: bob.stops(b0), 3)
    check("bob, logging in at about 33 s left, is told 30 -- after his account, no ack of its own",
          [f.split(";")[0] for f in bob.since(b0)],
          ["hello", "cmdAck", "constants", "persInfo", "accountInfo", "shutdown"])
    check("the number", bob.stops(b0), [30])
    bob.enter()
    alice.wait(lambda: len(alice.stops(i)) >= 2, 10)
    check("alice's 30 comes five seconds in", alice.stops(i), [35, 30])
    t30 = next((t for t, f in alice.got[i:] if f == "shutdown;seconds=30;"), 0)
    check("on time (5 to 6 s after the 35, give or take)", 4.5 <= t30 - t35 <= 7, True)
    check("bob is not told 30 twice", bob.stops(b0), [30])
    rc, line = status_until(lambda l: l.endswith(" 2"))
    check("status: two logged in", (rc, line.split()[-1]), (0, "2"))
    alice.wait(lambda: len(alice.stops(i)) >= 3, 30)
    t10 = next((t for t, f in alice.got[i:] if f == "shutdown;seconds=10;"), 0)
    check("the 10 comes 25 seconds in", (alice.stops(i), 24.5 <= t10 - t35 <= 27), ([35, 30, 10], True))
    bob.wait(lambda: len(bob.stops(b0)) >= 2, 3)
    check("to bob as well", bob.stops(b0), [30, 10])
    j = alice.mark()
    alice.send("moveTo;path=|492|493|;")
    alice.wait(lambda: "userMove" in [f.split(";")[0] for f in alice.since(j)], 3)
    # The time runs out; the game does not stop itself -- the deploy does.
    rc, line = cli("status")
    while left_of(line) and time.time() < t0 + 45:
        time.sleep(0.5)
        rc, line = cli("status")
    check("the time is up: status says 0, two still in", (rc, line), (0, "0 2"))
    time.sleep(1.0)
    check("and nobody was dropped or told 0 by it", (alice.eof, bob.eof, alice.stops(i), bob.stops(b0)),
          (False, False, [35, 30, 10], [30, 10]))
    check("the socket at the login screen was told nothing", probe.stops(), [])

    # --- the deploy restarts: SIGTERM, and the stop as it always was ---------------------
    srv.send_signal(signal.SIGTERM)
    alice.wait(lambda: alice.eof and bob.eof, 10)
    check("alice: the last frame is 0, then the socket closes", (alice.stops(i), alice.eof),
          ([35, 30, 10, 0], True))
    check("bob too", (bob.stops(b0), bob.eof), ([30, 10, 0], True))
    srv.wait(timeout=15)
    _drain.join(timeout=2)
    out = "".join(_log)
    check("the game exits cleanly", srv.returncode, 0)
    loc = db_one("SELECT loc, pos FROM characters WHERE name = ?", ("alice",))
    check("alice's place saved where she walked during the countdown", loc["pos"], 493)
    check("the stop's row cleared on the way out",
          db_one("SELECT stop_at FROM stop_plan WHERE id = 1"), {"stop_at": None})

    # --- the game gone: the command line says so ----------------------------------------
    def beat(ago):
        db = storage.connect(DB)
        try:
            db.execute("UPDATE heartbeat SET at = ? WHERE id = 1", (int(time.time()) - ago,))
            db.commit()
        finally:
            db.close()

    # A heartbeat still fresh, and nobody reading the queue: a game hung.
    beat(0)
    n = orders()
    rc, _line = cli("start", 20, "--by", "test", "--wait", "1.5")
    check("start with no game to answer: exit 4", rc, 4)
    last = db_one("SELECT done_at, result FROM admin_actions ORDER BY id DESC")
    check("and its order is withdrawn, not left for the next start",
          (orders(), last["done_at"] is not None, last["result"]),
          (n + 1, True, "не дождались ответа игры: отозвано"))
    # A heartbeat gone stale: the game is not running, and nothing is queued.
    beat(stopwarn.BEAT_FRESH + 5)
    check("with a stale heartbeat status says nothing: exit 4", cli("status"), (4, ""))
    check("start too, at once", cli("start", 20, "--by", "test")[0], 4)
    check("and queues nothing", orders(), n + 1)
finally:
    for c in clients:
        c.close()
    if srv.poll() is None:
        srv.terminate()
        srv.wait(timeout=10)
    _drain.join(timeout=2)
    out = "".join(_log)
    web.terminate()
    try:
        web.wait(timeout=10)
    except subprocess.TimeoutExpired:
        web.kill()
    if "Traceback" in out:
        fails.append("the game logged a traceback:\n" + out[-2000:])
    if "Traceback" in "".join(_hlog):
        fails.append("the panel logged a traceback:\n" + "".join(_hlog)[-2000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("stopwarn OK")
