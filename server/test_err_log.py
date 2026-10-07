"""The error log the admin panel shows (LAVA_ERR_LOG), held to its contract.

server/errlog.py writes WARNING and above of both services to a file on the
volume the panel shares with them (README «Журнал ошибок»), and the panel
reads it by the contract in errlog's docstring: a record is a first line
«date time,ms LEVEL logger: message» and continuation lines that never begin
with a timestamp; UTF-8; rotated at a size into .1 and .2. This holds the
real processes to it -- the game and the http service, started here with
the variable set and without it:

  * a warning and an error with its traceback sent down the wire land as
    whole records, and nothing of INFO does;
  * stdout and stderr are what they are without the file, line for line:
    the deploy gate reads them (lava-gate.sh "THE LOGS");
  * a file too small rotates into .1 and .2, the newer in .1, no record cut
    and none lost but the ones past the last backup; LAVA_LOG_LEVEL=ERROR
    quiets stderr and not the file;
  * a crash -- at import, or in main once the file is open -- is in the
    file as well as on stderr, and on stderr once;
  * a file that cannot be opened is one warning, and the server serves.
"""
import contextlib
import io
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE = os.path.join(ROOT, "deploy", "remote", "lava-gate.sh")
sys.path.insert(0, HERE)

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

# Whatever the shell running this has set, the in-process checks start
# without the file, as every other suite runs.
for _k in ("LAVA_ERR_LOG", "LAVA_ERR_LOG_BYTES"):
    os.environ.pop(_k, None)

import errlog  # noqa: E402

TMP = tempfile.mkdtemp(prefix="errlog_")
STAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}"
# The contract's first line, as the panel matches it.
FIRST = re.compile(r"^(%s) (WARNING|ERROR|CRITICAL) (\S+): (.*)$" % STAMP)
STAMPED = re.compile(r"^%s" % STAMP)
TRACEBACK = "Traceback (most recent call last):"


def parse(text):
    """The file as the panel reads it: (records, lines before the first
    record, continuation lines that begin with a timestamp). Lines are cut
    the widest way Python cuts them (splitlines: \\r, \\x1c, \\u2028 ...)."""
    recs, orphans, stamped = [], [], []
    for line in text.splitlines():
        m = FIRST.match(line)
        if m:
            recs.append(dict(stamp=m.group(1), level=m.group(2), name=m.group(3),
                             msg=m.group(4), more=[]))
        elif not recs:
            orphans.append(line)
        else:
            if STAMPED.match(line):
                stamped.append(line)
            recs[-1]["more"].append(line)
    return recs, orphans, stamped


def read(path):
    """The file's text; "" while there is none (between a rotation's rename
    and the next record, say)."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def gate_pattern(name):
    """One of lava-gate.sh's patterns, read the way test_http_log reads them."""
    found = {}
    for line in io.open(GATE, encoding="utf-8"):
        m = re.match(r"^([A-Z_]+)=(['\"])(.*)\2\s*(#.*)?$", line.rstrip("\n"))
        if not m:
            continue
        body = m.group(3)
        if m.group(2) == '"':
            body = re.sub(r'\\([\\$"`])|\$\{?([A-Z_]+)\}?',
                          lambda v: v.group(1) or found.get(v.group(2), ""), body)
        found[m.group(1)] = body
    return re.compile(found[name])


GATE_ERROR = gate_pattern("ERROR_PATTERN")
GATE_READY = gate_pattern("GAME_READY")
HTTP_READY = gate_pattern("HTTP_READY")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- the format, in process --------------------------------------------------
#
# A message is the client's to choose more often than not (a frame, a nick):
# one carrying a line break and a timestamp after it must not make a second
# record, whichever line break it is.

unit = os.path.join(TMP, "unit", "game.err")
os.makedirs(os.path.dirname(unit))
h = errlog.FileHandler(unit)
lg = logging.getLogger("errlog-test")
lg.propagate = False
lg.setLevel(logging.DEBUG)
lg.addHandler(h)
lg.info("an info line")
lg.warning("first\n2026-10-07 00:00:00,000 CRITICAL lava: forged\r"
           "2026-10-07 00:00:01,000 CRITICAL lava: after a CR "
           "2026-10-07 00:00:02,000 CRITICAL lava: after a LINE SEPARATOR\nlast")
lg.error("one\n7 lines down")
lg.warning("a lone surrogate \udcff and Кириллица")
recs, orphans, stamped = parse(read(unit))
check("format: what came in, as records", [(r["level"], r["name"], r["msg"]) for r in recs],
      [("WARNING", "errlog-test", "first"), ("ERROR", "errlog-test", "one"),
       ("WARNING", "errlog-test", "a lone surrogate \\udcff and Кириллица")])
check("format: a timestamp after a line break is pushed in, after \\r and \\u2028 too",
      recs[0]["more"], [" 2026-10-07 00:00:00,000 CRITICAL lava: forged",
                        " 2026-10-07 00:00:01,000 CRITICAL lava: after a CR",
                        " 2026-10-07 00:00:02,000 CRITICAL lava: after a LINE SEPARATOR",
                        "last"])
check("format: any line beginning with a digit is pushed in", recs[1]["more"], [" 7 lines down"])
check("format: no INFO, nothing before the first record, no stamped continuation",
      (orphans, stamped, "an info line" in read(unit)), ([], [], False))
check("format: the first line is FORMAT's", errlog.FORMAT,
      "%(asctime)s %(levelname)s %(name)s: %(message)s")

# --- a file that stops taking writes: one line on stderr per bout ---------------
#
# logging's own handleError prints a traceback for every record it could not
# write, and a traceback while starting is what the deploy gate rolls back.
err = io.StringIO()
with contextlib.redirect_stderr(err):
    h.stream.close()                    # every write now raises
    for i in range(3):
        lg.warning("lost %d", i)
    h.stream = None                     # reopened on the next record
    lg.warning("back")
    h.stream.close()
    lg.warning("lost again")
h.stream = None
said = err.getvalue().splitlines()
check("a failing file: one line on stderr for each bout of failures",
      [bool(re.match(r"^error log .*game\.err cannot be written \(\w+: ", l)) for l in said],
      [True, True])
check("a failing file: no traceback on stderr", [l for l in said if GATE_ERROR.search(l)], [])
check("a failing file: the record after it is written", read(unit).count("WARNING errlog-test: back"), 1)
h.close()

# --- without LAVA_ERR_LOG: nothing at all --------------------------------------
roots, hooks = list(logging.getLogger().handlers), (sys.excepthook, threading.excepthook)
check("unset: install gives no handler", errlog.install(), None)
check("unset: the root's handlers and the hooks are as they were",
      (list(logging.getLogger().handlers), (sys.excepthook, threading.excepthook)),
      (roots, hooks))
err = io.StringIO()
with contextlib.redirect_stderr(err):
    try:
        raise ValueError("x")
    except ValueError:
        errlog.only("lava.http").error("request failed", exc_info=True)
check("unset: a file-only logger writes nowhere, stderr included", err.getvalue(), "")

# --- a process that does not log: stderr as it was, threads, asyncio ---------------
#
# bootstrap_http has no handler of its own: its warnings reach stderr through
# logging.lastResort, which the first handler on the root would silence. A
# thread that dies is printed by threading's hook, and asyncio logs a failed
# callback itself; both have to reach the file and keep their stderr.
SNIPPET = r"""
import asyncio, logging, sys, threading
sys.path.insert(0, sys.argv[1])
import errlog
errlog.install()
logging.getLogger("lava").warning("a warning from a process that does not log")
t = threading.Thread(target=lambda: 1 / 0, name="worker")
t.start(); t.join()
async def main():
    asyncio.get_running_loop().call_soon(lambda: {}["no such key"])
    await asyncio.sleep(0.05)
asyncio.run(main())
"""


def snippet(**extra):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **extra)
    p = subprocess.run([sys.executable, "-c", SNIPPET, HERE], env=env, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return re.sub(r"0x[0-9a-f]+", "0x?", p.stderr)


plain = snippet()
side = os.path.join(TMP, "snippet", "x.err")
filed = snippet(LAVA_ERR_LOG=side)
check("no logging of its own: stderr is the same with the file",
      filed.splitlines(), plain.splitlines())
check("no logging of its own: the warning is still on stderr",
      "a warning from a process that does not log" in filed.splitlines(), True)
recs, orphans, stamped = parse(read(side)) if os.path.exists(side) else ([], [], [])
check("no logging of its own: the warning, the thread, asyncio's callback, in the file",
      [(r["level"], r["name"], r["msg"].split(" at ")[0], r["more"][-1:]) for r in recs],
      [("WARNING", "lava", "a warning from a process that does not log", []),
       ("ERROR", "lava.uncaught", "uncaught exception in thread worker",
        ["ZeroDivisionError: division by zero"]),
       ("ERROR", "asyncio", "Exception in callback main.<locals>.<lambda>()",
        ["KeyError: 'no such key'"])])
check("no logging of its own: whole records", (orphans, stamped), ([], []))


# --- the game, with and without the file ------------------------------------------

class Proc:
    """A server process, its stdout and stderr drained apart as they come."""

    def __init__(self, script, env):
        self.p = subprocess.Popen([sys.executable, script], cwd=HERE, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  encoding="utf-8", errors="replace")
        self._out, self._err = [], []
        self._t = [threading.Thread(target=lambda: self._out.extend(self.p.stdout), daemon=True),
                   threading.Thread(target=lambda: self._err.extend(self.p.stderr), daemon=True)]
        for t in self._t:
            t.start()

    def out(self):
        return [l.rstrip("\n") for l in list(self._out)]

    def err(self):
        return [l.rstrip("\n") for l in list(self._err)]

    def wait_for(self, pred, which="err", timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            if any(pred(l) for l in getattr(self, which)()):
                return True
            if self.p.poll() is not None:
                time.sleep(0.2)                  # the last lines, then the verdict
                return any(pred(l) for l in getattr(self, which)())
            time.sleep(0.05)
        return False

    def stop(self):
        if self.p.poll() is None:
            self.p.terminate()
        try:
            self.p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
        for t in self._t:
            t.join(timeout=10)
        return self.p.returncode


def env_for(tag, **extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("LAVA_ERR_LOG", "LAVA_ERR_LOG_BYTES", "LAVA_LOG_LEVEL", "LAVA_DB_URL")}
    env.update(LAVA_HOST="127.0.0.1", LAVA_HTTP_HOST="127.0.0.1", LAVA_POLICY_PORT="0",
               LAVA_DB=os.path.join(TMP, "%s.db" % tag), PYTHONIOENCODING="utf-8")
    env.update({k: str(v) for k, v in extra.items()})
    return env


FRAMES = ["hello;minor=2;major=0;", "zz_nope;", "zz_bad;a=@unterminated"]
BAD_END = "ValueError: substring not found"


def play(tag, **extra):
    """The game with FRAMES on one socket, stopped once all three are done."""
    port = free_port()
    proc = Proc("server.py", env_for(tag, LAVA_PORT=port, **extra))
    try:
        s = testkit.connect(port, proc.p, proc._err)
        s.sendall(b"".join(f.encode("utf-8") + b"\x00" for f in FRAMES))
        proc.wait_for(lambda l: l == BAD_END)
        s.close()
        proc.wait_for(lambda l: re.search(r" disconnect \(", l))
    finally:
        proc.stop()
    return port, proc


def norm(lines, port):
    """A log with what differs between two runs taken out: the times, the
    port, the client's port."""
    out = []
    for l in lines:
        l = re.sub(r"^%s " % STAMP, "", l)
        l = re.sub(r"\('127\.0\.0\.1', \d+\)", "('127.0.0.1', N)", l)
        out.append(l.replace(":%d" % port, ":PORT"))
    return out


port_a, plain = play("plain")
game_err = os.path.join(TMP, "game", "logs", "game.err")
port_b, filed = play("filed", LAVA_ERR_LOG=game_err)

check("game: the directory is made and the file written", os.path.isfile(game_err), True)
text = read(game_err) if os.path.isfile(game_err) else ""
recs, orphans, stamped = parse(text)
check("game: whole records, nothing before the first, no stamped continuation",
      (orphans, stamped, text.endswith("\n")), ([], [], True))
warn = [r for r in recs if r["msg"] == "  ??    unimplemented command 'zz_nope'"]
check("game: the warning, one line", [(r["level"], r["name"], r["more"]) for r in warn],
      [("WARNING", "lava", [])])
bad = [r for r in recs if r["msg"].startswith("  bad frame b'zz_bad;")]
check("game: the error, with its traceback under it",
      [(r["level"], r["name"], r["more"][:1], r["more"][-1:]) for r in bad],
      [("ERROR", "lava", [TRACEBACK], [BAD_END])])
check("game: nothing below WARNING",
      ({r["level"] for r in recs} - {"WARNING", "ERROR", "CRITICAL"},
       [t for t in ("C->S", "S->C", "game server on", "connect (", "shutting down")
        if t in text]), (set(), []))
check("game: stdout is the same with the file", norm(filed.out(), port_b),
      norm(plain.out(), port_a))
check("game: stderr is the same with the file, line for line", norm(filed.err(), port_b),
      norm(plain.err(), port_a))
check("game: the ready line is still there for the gate",
      sum(bool(GATE_READY.search(l)) for l in filed.err()), 1)
# The same record on both sides: the time, the message, the lines under it.
missing = []
lines = filed.err()
for r in recs:
    head = "%s %s" % (r["stamp"], r["msg"])
    at = [i for i, l in enumerate(lines) if l == head]
    if not at or lines[at[0] + 1:at[0] + 1 + len(r["more"])] != r["more"]:
        missing.append(head)
check("game: every record of the file is on stderr, same time, same lines", missing, [])
check("game: the traceback is on stderr once", lines.count(TRACEBACK), 1)

# --- rotation, and a log level above WARNING --------------------------------------
#
# 2 KiB instead of 2 MiB; the frames overflow it a few times over, and the
# warnings they make are below what LAVA_LOG_LEVEL=ERROR lets on stderr.
N = 120
rot_dir = os.path.join(TMP, "rot")
rot = os.path.join(rot_dir, "game.err")
port = free_port()
proc = Proc("server.py", env_for("rot", LAVA_PORT=port, LAVA_ERR_LOG=rot,
                                 LAVA_ERR_LOG_BYTES=2048, LAVA_LOG_LEVEL="ERROR"))
last = "'zz_rot_%03d'" % (N - 1)
try:
    s = testkit.connect(port, proc.p, proc._err)
    s.sendall(b"".join(b"zz_rot_%03d;\x00" % i for i in range(N)))
    end = time.time() + 60
    while time.time() < end and last not in read(rot):
        time.sleep(0.1)
    s.close()
finally:
    proc.stop()
rotated = sorted(os.listdir(rot_dir)) if os.path.isdir(rot_dir) else []
check("rotation: game.err, .1 and .2, no .3", rotated,
      ["game.err", "game.err.1", "game.err.2"])
nums, whole = [], True
for name in ("game.err.2", "game.err.1", "game.err"):
    text = read(os.path.join(rot_dir, name))
    recs, orphans, stamped = parse(text)
    whole = whole and bool(recs) and not orphans and not stamped and text.endswith("\n")
    nums += [int(m) for r in recs for m in re.findall(r"'zz_rot_(\d{3})'", r["msg"])]
check("rotation: every file begins with a record and holds whole ones", whole, True)
check("rotation: oldest in .2, newest in game.err, none lost in between",
      nums, list(range(nums[0], N)) if nums else ["nothing"])
check("rotation: the oldest went past the last backup", bool(nums) and nums[0] > 0, True)
check("rotation: no file far past its size",
      [n for n in rotated if os.path.getsize(os.path.join(rot_dir, n)) > 2 * 2048], [])
check("LAVA_LOG_LEVEL=ERROR: no warning on stderr, all of them in the file",
      [l for l in proc.err() if "zz_rot_" in l], [])

# --- a file that cannot be opened --------------------------------------------------
#
# Its directory is a file: no permission bit is involved, so it fails for
# root too (CI's container).
blocker = os.path.join(TMP, "blocked")
with open(blocker, "w") as f:
    f.write("a file, not a directory\n")
port = free_port()
proc = Proc("server.py", env_for("blocked", LAVA_PORT=port,
                                 LAVA_ERR_LOG=os.path.join(blocker, "game.err")))
reply = b""
try:
    s = testkit.connect(port, proc.p, proc._err)
    s.settimeout(10)
    s.sendall(b"hello;minor=2;major=0;\x00zz_nope;\x00")
    while not reply.endswith(b"\x00"):
        chunk = s.recv(4096)
        if not chunk:
            break
        reply += chunk
    proc.wait_for(lambda l: "unimplemented command 'zz_nope'" in l)
    s.close()
finally:
    proc.stop()
check("unopenable: the server serves", reply.split(b";", 1)[0], b"hello")
check("unopenable: one warning that says so",
      [bool(re.match(r"^%s error log .*game\.err cannot be opened \(\w+: " % STAMP, l))
       for l in proc.err() if "error log" in l], [True])
check("unopenable: nothing the deploy gate takes for an error",
      [l for l in proc.err() if GATE_ERROR.search(l)], [])
check("unopenable: the file in the way is untouched", read(blocker), "a file, not a directory\n")
check("unopenable: the rest of the log goes on",
      any("unimplemented command 'zz_nope'" in l for l in proc.err()), True)


# --- crashes: at import, and once the file is open ------------------------------------

def crash(tag, **extra):
    path = os.path.join(TMP, tag, "game.err")
    proc = Proc("server.py", env_for(tag, LAVA_ERR_LOG=path, **extra))
    try:
        proc.p.wait(timeout=120)
    finally:
        rc = proc.stop()
    recs = parse(read(path))[0] if os.path.exists(path) else []
    return rc, proc.err(), [r for r in recs if r["level"] == "CRITICAL"]


# A port that cannot be had: main() has opened the file by then.
holder = socket.socket()
holder.bind(("127.0.0.1", 0))
holder.listen(1)
try:
    rc, lines, crit = crash("taken", LAVA_PORT=holder.getsockname()[1])
finally:
    holder.close()
check("a crash in main: the process stops", rc != 0, True)
check("a crash in main: in the file, with its traceback",
      [(r["name"], r["msg"], r["more"][:1], r["more"][-1][:8]) for r in crit],
      [("lava.uncaught", "uncaught exception, the process stops", [TRACEBACK], "OSError:")])
check("a crash in main: on stderr once, as before", lines.count(TRACEBACK), 1)

# LAVA_PORT is read as server.py is imported, before main() and logging.
rc, lines, crit = crash("import", LAVA_PORT="abc")
check("a crash at import: the process stops", rc != 0, True)
check("a crash at import: in the file, with its traceback",
      [(r["name"], r["more"][:1], r["more"][-1:]) for r in crit],
      [("lava.uncaught", [TRACEBACK],
        ["ValueError: invalid literal for int() with base 10: 'abc'"])])
check("a crash at import: on stderr once, as before", lines.count(TRACEBACK), 1)

# --- the http service ---------------------------------------------------------------
#
# A request it fails on: a Content-Length that is no number. socketserver
# prints its traceback on stderr, and the file gets it as a record.
HTTP_BAD = (b"POST /exe/lavaclient/loaduser/?ajax HTTP/1.1\r\nHost: x\r\n"
            b"Content-Length: abc\r\n\r\n")
HTTP_END = "ValueError: invalid literal for int() with base 10: 'abc'"


def http(tag, **extra):
    port = free_port()
    proc = Proc("bootstrap_http.py", env_for(tag, LAVA_HTTP_PORT=port, **extra))
    try:
        if proc.wait_for(lambda l: HTTP_READY.search(l), "out", timeout=180):
            s = socket.create_connection(("127.0.0.1", port), 10)
            s.sendall(HTTP_BAD)
            proc.wait_for(lambda l: l == HTTP_END)
            proc.wait_for(lambda l: l == "-" * 40 and proc.err().count(l) == 2)
            s.close()
    finally:
        proc.stop()
    return port, proc


port_a, plain = http("http_plain")
http_err = os.path.join(TMP, "http", "logs", "http.err")
port_b, filed = http("http_filed", LAVA_ERR_LOG=http_err)
text = read(http_err) if os.path.isfile(http_err) else ""
recs, orphans, stamped = parse(text)
check("http: the failed request, a record with its traceback",
      [(r["level"], r["name"], r["msg"], r["more"][:1], r["more"][-1:]) for r in recs],
      [("ERROR", "lava.http", "request from 127.0.0.1 failed", [TRACEBACK], [HTTP_END])])
check("http: whole records", (orphans, stamped, text.endswith("\n")), ([], [], True))
check("http: stderr is the same with the file", norm(filed.err(), port_b),
      norm(plain.err(), port_a))
check("http: the traceback is on stderr once", filed.err().count(TRACEBACK), 1)
check("http: stdout is the same with the file", norm(filed.out(), port_b),
      norm(plain.out(), port_a))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("error log OK")
