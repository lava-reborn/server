"""Where the character is when the server stops, or the link breaks.

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
import sqlite3
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
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_acc, _err = _store.register("tester", "secret")
_store.create_character(_acc, "tester", 0, "1")
_store.close()
CRED = accounts.credential("tester", "secret")

env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1",
           LAVA_DB=DB)

srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

out = ""

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def connect(timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        # Only our own server may answer here. If it died before listening
        # (a port taken after all), connecting would reach whoever has it.
        if srv.poll() is not None:
            raise SystemExit("server exited before listening:\n"
                             + "".join(_log)[-1500:])
        try:
            return socket.create_connection(("127.0.0.1", PORT), 0.5)
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


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
    db = sqlite3.connect(DB)
    try:
        return db.execute("SELECT loc, pos FROM characters").fetchone()
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
    check("nothing saved yet", saved(), (None, None))
    c.send("moveTo;path=|490|491|492|;")
    check("moved", c.names(), ["cmdAck", "userMove"])
    # No logout: the client crashed, or the network went.
    c.s.close()
    time.sleep(0.5)
    check("position written when the link breaks", saved(), (loc_id, 492))

    # --- and the next login starts from there -----------------------------
    c = Client(connect())
    lcall, lenter = enter(c)
    # amax is the character's action-point ceiling, 50 + 5 * best skill, which
    # for a newborn is 50; it used to be a constant 20.
    check("restored where the link broke", lenter, "lenter;pos=492;aspd=1;amax=50;")
    c.send("moveTo;path=|492|493|;")
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
    check("position written on shutdown", saved(), (loc_id, 493))
    check("one save per session, not two",
          out.count("shutting down, 1 session(s) online"), 1)
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
