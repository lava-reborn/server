"""Where the character is when the server stops, or the link breaks -- and
on every arrival, for a server that is killed and saves nothing at the end.

run.sh stop sends SIGTERM. Until the server handled it, that ended the loop
with every connection still parked in read(): no finally ran, no position
was written, and whoever was online came back wherever they had logged out
the time before. Session.as:216 answers a shutdown frame with an alert that
names the seconds, so the client is told first, then saved, then dropped.
A connection that simply breaks has to save the same way, with no logout
before it.
"""
import os
import threading
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"


def free_port():
    """A port nobody holds right now.

    A fixed number collided with other suites' servers when several run at
    once: this client then talked to a stranger's server, whose database
    knew the same test credential, and every check lied about it.
    """
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()

# A throwaway database with one account and one ready character, so the
# path is the returning player's: login, selPers, lenter.
DB = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, HERE)
import accounts
import storage
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_acc, _err = _store.register("tester", "secret")
_store.create_character(_acc, "tester", 0, "1")
_store.close()
CRED = accounts.credential("tester", "secret")

# The start cell is a server default and has moved since; these
# assertions name the market by number, so the suite says which
# world it wants.
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB, LAVA_GX="5970", LAVA_GY="1730")

srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       encoding="utf-8", errors="replace")

# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

out = ""

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.s.settimeout(2)
        self.buf = b""
        self.eof = False

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
                self.eof = True
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]

    def names(self, wait=0.5):
        return [f.split(";")[0] for f in self.frames(wait)]

    def until_closed(self, timeout=5):
        """Everything up to the server closing the socket."""
        deadline = time.time() + timeout
        self.s.settimeout(0.5)
        while time.time() < deadline and not self.eof:
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                self.eof = True
                break
            if not chunk:
                self.eof = True
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [f.decode(ENC) for f in out if f]


def saved():
    """(loc, pos) as the database has it right now."""
    db = storage.connect(DB)
    try:
        row = db.execute("SELECT loc, pos FROM characters").fetchone()
        return (row["loc"], row["pos"]) if row else None
    finally:
        db.close()


def enter(c):
    """The returning player's path in; returns the lcall and lenter frames."""
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    check("login sequence", c.names(),
          ["hello", "cmdAck", "constants", "persInfo", "accountInfo"])
    # selPers registers no handler, so nothing but the location call comes.
    c.send("selPers;num=0;")
    got = c.frames()
    check("character chosen opens a location without an ack",
          [f.split(";")[0] for f in got], ["lcall"])
    lcall = got[0]
    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    check("positioned", got[0].split(";")[0], "lenter")
    return lcall, got[0]


try:
    # --- a link that breaks saves where the player stood ------------------
    c = Client(connect())
    lcall, lenter = enter(c)
    loc_id = int(lcall.split("id=")[1].split(";")[0])
    # Five cells side by side that no wall stands on: a login puts somebody
    # saved on a wall at the entry instead (Session.restore), and these cells
    # are the suite's own choice, where the client's findPath walks round
    # every wall.
    import world
    _loc = world.location(loc_id)
    P = next(range(i, i + 5) for i in range(490, _loc.width * _loc.height - 5)
             if i % _loc.width + 4 < _loc.width and not any(c in _loc.obstacles for c in range(i, i + 5)))
    # Written on arrival, before any logout or break: a server killed
    # outright (serve_local.ps1's Stop-Process -Force, a crash) reaches no
    # close(), and the login then put him back where he had logged out the
    # time before -- in the Вади-Хальфа mine, a tier or a town away.
    check("the location written on arrival, before any logout or break", saved(),
          (loc_id, int(lenter.split("pos=")[1].split(";")[0])))
    c.send("moveTo;path=|%d|%d|%d|;" % (P[0], P[1], P[2]))
    check("moved", c.names(), ["cmdAck", "userMove"])
    # No logout: the client crashed, or the network went.
    c.s.close()
    time.sleep(0.5)
    check("position written when the link breaks", saved(), (loc_id, P[2]))

    # --- and the next login starts from there -----------------------------
    c = Client(connect())
    lcall, lenter = enter(c)
    # amax is the character's action-point ceiling, 50 + 5 * best skill, which
    # for a newborn is 50; it used to be a constant 20.
    check("restored where the link broke", lenter, "lenter;pos=%d;aspd=1;amax=50;" % P[2])
    c.send("moveTo;path=|%d|%d|;" % (P[2], P[3]))
    check("moved again", c.names(), ["cmdAck", "userMove"])

    # --- SIGTERM: told, saved, dropped, in that order ----------------------
    srv.send_signal(signal.SIGTERM)
    got = c.until_closed()
    check("the client is told before the socket closes",
          got, ["shutdown;seconds=0;"])
    check("and the socket does close", c.eof, True)
    srv.wait(timeout=10)
    _drain.join(timeout=2)
    out = "".join(_log)
    check("server exits cleanly", srv.returncode, 0)
    check("position written on shutdown", saved(), (loc_id, P[3]))
    check("one save per session, not two",
          out.count("shutting down, 1 session(s) online"), 1)

    # --- halt: the same stop, queued, where no signal reaches the process ---
    # Windows has no SIGTERM to send from outside, only TerminateProcess,
    # which saves nobody: serve_local.ps1 queues "halt" instead (stopwarn.py
    # halt, the admin queue), and the game stops the way SIGTERM stops it.
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           encoding="utf-8", errors="replace")
    _log = []
    _drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
    _drain.start()
    c = Client(connect())
    lcall, lenter = enter(c)
    check("back where the stop left him", lenter, "lenter;pos=%d;aspd=1;amax=50;" % P[3])
    c.send("moveTo;path=|%d|%d|;" % (P[3], P[4]))
    check("moved once more", c.names(), ["cmdAck", "userMove"])
    halt = subprocess.run([sys.executable, "stopwarn.py", "halt", "--by", "test"], cwd=HERE,
                          env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30)
    check("stopwarn.py halt is answered by the game", (halt.returncode, "останавливается"
                                                       in halt.stderr), (0, True))
    got = c.until_closed()
    check("  ..the client told before the socket closes", got, ["shutdown;seconds=0;"])
    srv.wait(timeout=10)
    _drain.join(timeout=2)
    out = "".join(_log)
    check("  ..the server exits cleanly", srv.returncode, 0)
    check("  ..and the position is written", saved(), (loc_id, P[4]))
finally:
    if srv.poll() is None:
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
print("shutdown OK")
