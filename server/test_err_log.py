"""The error log the admin panel shows (LAVA_ERR_LOG), held to its contract.

server/errlog.py writes WARNING and above of both services to a file on the
volume the panel shares with them (README «Журнал ошибок»), and the panel
reads it by the contract in errlog's docstring: a record is a first line
«date time,ms LEVEL logger: message» and continuation lines that never begin
with a timestamp; UTF-8; rotated at a size into .1 and .2. This holds the
real processes to it -- the game and the http service, started here with
the variable set and without it:

  * the contract's sizes, and compose giving each service a file of its own;
  * a warning and an error with its traceback sent down the wire land as
    whole records, and nothing of INFO does; a warning a module gives as it
    is imported (LAVA_BOSS_TZ with no such zone) lands too;
  * stdout and stderr are what they are without the file, line for line:
    the deploy gate reads them (lava-gate.sh "THE LOGS");
  * a file too small rotates into .1 and .2, the newer in .1, no record cut
    and none lost but the ones past the last backup; LAVA_LOG_LEVEL=ERROR
    quiets stderr and not the file;
  * a flood of unknown commands and bad frames from a socket that never
    said hello is held to twenty of a kind a minute, counted, and leaves
    what the server wrote at start where it was;
  * a crash -- at import, or in main once the file is open -- is in the
    file as well as on stderr, and on stderr once;
  * a file that cannot be opened is one warning, and the server serves;
    a log call with the wrong arguments is no failure of the file;
  * a letter the SMTP side refuses is in the file, try by try, with no
    address in full.
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
ERR_VARS = ("LAVA_ERR_LOG", "LAVA_ERR_LOG_BYTES", "LAVA_ERR_LOG_RATE")
for _k in ERR_VARS:
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
try:
    raise ValueError("GET /account/reset?t=SeCrEt42abc&x=1 failed")
except ValueError:
    lg.exception("request /account/confirm?t=KeY99zz failed")
recs, orphans, stamped = parse(read(unit))
check("format: a link's token never reaches the file, the link does",
      (any("SeCrEt42abc" in line or "KeY99zz" in line
           for r in recs for line in [r["msg"]] + r["more"]),
       recs[-1]["msg"], any("reset?t=...&x=1" in line for line in recs[-1]["more"])),
      (False, "request /account/confirm?t=... failed", True))
recs = recs[:-1]
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

# --- the contract's sizes, and compose -----------------------------------------
#
# The suites below shrink the file (LAVA_ERR_LOG_BYTES) and lift the limit
# (LAVA_ERR_LOG_RATE); what production gets is pinned here.
check("contract: 2 MiB a file and two backups",
      (errlog.MAX_BYTES, errlog.BACKUPS, errlog.max_bytes()), (2 * 1024 * 1024, 2, 2 * 1024 * 1024))
check("contract: twenty records of a kind a minute",
      (errlog.RATE, errlog.WINDOW, errlog.rate()), (20, 60.0, 20))


def compose_err_logs():
    """{service: its LAVA_ERR_LOG} in docker-compose.yml."""
    found, service = {}, None
    for line in io.open(os.path.join(ROOT, "docker-compose.yml"), encoding="utf-8"):
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m or re.match(r"^\S", line):
            service = m.group(1) if m else None
            continue
        m = re.match(r"^\s+LAVA_ERR_LOG:\s*(\S+)\s*$", line)
        if m and service:
            found[service] = m.group(1)
    return found


# Two processes cannot share one rotating file: each rotates the other's.
check("compose: the game and http each write a file of their own on the volume",
      compose_err_logs(), {"game": "/var/lib/lava/logs/game.err",
                           "http": "/var/lib/lava/logs/http.err"})

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

# --- a log call with the wrong arguments: the call's fault, not the file's -------
#
# logging's handler on stderr prints its "--- Logging error ---" for it; the
# file's must not add "cannot be written" to that, nor lose the record.
bad_path = os.path.join(TMP, "unit", "bad.err")
bh = errlog.FileHandler(bad_path)
blg = logging.getLogger("errlog-bad")
blg.propagate = False
blg.addHandler(bh)
err = io.StringIO()
with contextlib.redirect_stderr(err):
    blg.warning("  ??    count %d", "not a number")
    blg.warning("a good one after it")
bh.close()
check("a bad log call: a record that shows the call, and the next one",
      [(r["level"], r["msg"]) for r in parse(read(bad_path))[0]],
      [("WARNING", "a log call that cannot be formatted (TypeError: %d format: a real number"
        " is required, not str): '  ??    count %d' % ('not a number',)"),
       ("WARNING", "a good one after it")])
check("a bad log call: not a failing file, nothing on stderr from it",
      (bh.failing, err.getvalue()), (False, ""))

# --- the limit: twenty of a kind a minute, once the server serves -------------------
#
# On a clock of the test's own: Throttle.admit takes the time it is given.


def rec(name, msg, *args):
    return logging.makeLogRecord(dict(name=name, msg=msg, args=args,
                                      levelno=logging.WARNING, levelname="WARNING"))


UNKNOWN = "  ??    unimplemented command %r"
t = errlog.Throttle(3)
check("limit: not armed (the start), everything is written",
      [t.admit(rec("lava", UNKNOWN, "c%d" % i), 1.0 + i)[1] for i in range(5)], [True] * 5)
t.armed = True
got = [t.admit(rec("lava", UNKNOWN, "c%d" % i), 10.0 + i) for i in range(6)]
check("limit: three of a kind written, whatever the command, then held",
      [keep for _n, keep in got], [True, True, True, False, False, False])
check("limit: one record of the file's own when the holding starts",
      [[(n.name, n.levelname, n.getMessage()) for n in notes] for notes, _k in got],
      [[], [], [], [("lava", "WARNING", "  ..    more than 3 a minute of '  ??    unimplemented"
                     " command %r': the rest of this minute's are not written here")], [], []])
check("limit: another kind, or another logger, is counted apart",
      [t.admit(rec("lava", "other %s", 1), 20.0)[1],
       t.admit(rec("lava.http", UNKNOWN, "x"), 20.0)[1]], [True, True])
notes, keep = t.admit(rec("lava", UNKNOWN, "again"), 70.5)
check("limit: the minute over, its count comes first and the next one is written",
      ([bool(re.match(r"^  \.\.    3 more of '  \?\?    unimplemented command %r' in the minute"
                      r" from \d\d:\d\d:\d\d were not written here$", n.getMessage()))
        for n in notes], keep), ([True], True))
for i in range(3):
    t.admit(rec("lava", "other %s", i), 71.0 + i)


def clockless(text):
    return re.sub(r"\b\d\d:\d\d:\d\d\b", "HH:MM:SS", text)


check("limit: what is still owed is counted at the close",
      [clockless(n.getMessage()) for n in t.owed()],
      ["  ..    1 more of 'other %s' in the minute from HH:MM:SS were not written here"])
check("limit: and only once", t.owed(), [])
check("limit: a message that is no string is a kind by its type",
      errlog.Throttle.kind_of(rec("lava", ValueError("x"))), ("lava", "ValueError"))
kinds = errlog.KINDS
errlog.KINDS = 2
t = errlog.Throttle(1)
t.armed = True
got = [t.admit(rec("lava", m), 5.0) for m in ("a", "b", "c", "d")]
errlog.KINDS = kinds
check("limit: past KINDS kinds the rest are counted as one",
      [(keep, [n.getMessage() for n in notes]) for notes, keep in got],
      [(True, []), (True, []), (True, []),
       (False, ["  ..    more than 1 a minute of records of any other kind: the rest of this"
                " minute's are not written here"])])

# The handler: held records are not written, and the count goes in at the
# close -- the server's stop, through logging.shutdown.
lim_path = os.path.join(TMP, "unit", "limit.err")
lh = errlog.FileHandler(lim_path, rate=2)
lh.throttle.armed = True
llg = logging.getLogger("errlog-limit")
llg.propagate = False
llg.addHandler(lh)
for i in range(5):
    llg.warning(UNKNOWN, "c%d" % i)
lh.close()
check("limit: the file has two, the note, and the count from the close",
      [clockless(r["msg"]) for r in parse(read(lim_path))[0]],
      ["  ??    unimplemented command 'c0'", "  ??    unimplemented command 'c1'",
       "  ..    more than 2 a minute of '  ??    unimplemented command %r': the rest of this"
       " minute's are not written here",
       "  ..    3 more of '  ??    unimplemented command %r' in the minute from HH:MM:SS"
       " were not written here"])

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


def snippet(code=SNIPPET, **extra):
    """(stdout, stderr) of code run in a process of its own."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **extra)
    p = subprocess.run([sys.executable, "-c", code, HERE], env=env, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=60)
    return p.stdout, re.sub(r"0x[0-9a-f]+", "0x?", p.stderr)


plain = snippet()[1]
side = os.path.join(TMP, "snippet", "x.err")
filed = snippet(LAVA_ERR_LOG=side)[1]
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

# A log call with the wrong arguments, where logging is set up: stderr has
# logging's own "--- Logging error ---" for it, with the file as without.
BADCALL = r"""
import logging, sys
sys.path.insert(0, sys.argv[1])
import errlog
logging.basicConfig(level="INFO", format="%(message)s")
errlog.install()
log = logging.getLogger("lava")
log.warning("  ??    count %d", "not a number")
log.warning("a good one after it")
"""
plain = snippet(BADCALL)[1]
side = os.path.join(TMP, "badcall", "x.err")
filed = snippet(BADCALL, LAVA_ERR_LOG=side)[1]
check("a bad log call: stderr is the same with the file", filed.splitlines(), plain.splitlines())
check("a bad log call: logging's own report is there", "--- Logging error ---" in filed, True)
check("a bad log call: both records in the file",
      [r["msg"][:36] for r in parse(read(side))[0]],
      ["a log call that cannot be formatted ", "a good one after it"])

# --- letters that do not leave -----------------------------------------------------
#
# emailer prints its "  MAIL " lines and logs nothing; a letter the SMTP side
# refuses is a fault the owner has to see (a wrong password for outside
# programs), so each failed try and the giving up go to the file as well --
# except an address the server refuses, the player's typo, which is only
# printed.
MAIL = r"""
import sys
sys.path.insert(0, sys.argv[1])
import errlog, emailer
errlog.install()
emailer.PAUSES = (0, 0)
emailer.OUTBOX = "unused"            # enabled(): a letter leaves at all

def refused(msg):
    raise ConnectionRefusedError(111, "Connection refused")

emailer._deliver = refused
emailer.send("someone@example.com", "Подтверждение адреса", "text")
emailer._queue.join()
"""
plain = snippet(MAIL)
side = os.path.join(TMP, "mail", "http.err")
filed = snippet(MAIL, LAVA_ERR_LOG=side)
check("mail: stdout and stderr are the same with the file", filed, plain)
check("mail: and stderr has nothing, as the prints never went there", filed[1], "")
check("mail: the print is still there", "  MAIL gave up: Подтверждение адреса to s***@example.com"
      in filed[0].splitlines(), True)
recs, orphans, stamped = parse(read(side))
letter = "Подтверждение адреса to s***@example.com"
check("mail: each failed try and the giving up, in the file",
      [(r["level"], r["name"], r["msg"]) for r in recs],
      [("WARNING", "lava.mail", "try %d of 3 failed: %s: ConnectionRefusedError: "
        "[Errno 111] Connection refused" % (n, letter)) for n in (1, 2, 3)]
      + [("ERROR", "lava.mail", "gave up: %s" % letter)])

# A recipient the server refuses: smtplib names the address in the
# exception, and the reply repeats it. One try, a masked print, and nothing
# in the file: the panel's lamp is for the server, not for a player's typo.
REFUSED = MAIL.replace("""def refused(msg):
    raise ConnectionRefusedError(111, "Connection refused")
""", """import smtplib
def refused(msg):
    raise smtplib.SMTPRecipientsRefused({msg["To"]: (
        550, b"5.1.1 <" + msg["To"].encode() + b">: Recipient address rejected")})
""").replace("someone@example.com", "ivan.petrov.1990@example.com")
plain = snippet(REFUSED)
side = os.path.join(TMP, "refused", "http.err")
filed = snippet(REFUSED, LAVA_ERR_LOG=side)
text = read(side)
check("mail refused: stdout is the same with the file", filed, plain)
check("mail refused: the address in full nowhere",
      ["ivan.petrov" in s for s in (filed[0], filed[1], text)], [False, False, False])
check("mail refused: one print, masked, with the server's code",
      [s for s in filed[0].splitlines() if s.startswith("  MAIL ")],
      ["  MAIL address refused: Подтверждение адреса to i***@example.com: SMTPRecipientsRefused: "
       "{'i***@example.com': (550, b'5.1.1 <i***@example.com>: Recipient address rejected')}"])
check("mail refused: nothing in the file", parse(text)[0], [])


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
           if k not in ERR_VARS + ("LAVA_LOG_LEVEL", "LAVA_DB_URL")}
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


# A zone that does not exist: bosses warns of it as it is imported, long
# before main() sets logging up, and that warning is the file's too.
NO_ZONE = "  !!    no time zone 'Mars/Olympus', boss hours are read in UTC"
port_a, plain = play("plain", LAVA_BOSS_TZ="Mars/Olympus")
game_err = os.path.join(TMP, "game", "logs", "game.err")
port_b, filed = play("filed", LAVA_ERR_LOG=game_err, LAVA_BOSS_TZ="Mars/Olympus")

check("game: the directory is made and the file written", os.path.isfile(game_err), True)
text = read(game_err) if os.path.isfile(game_err) else ""
recs, orphans, stamped = parse(text)
check("game: whole records, nothing before the first, no stamped continuation",
      (orphans, stamped, text.endswith("\n")), ([], [], True))
warn = [r for r in recs if r["msg"] == "  ??    unimplemented command 'zz_nope'"]
check("game: the warning, one line", [(r["level"], r["name"], r["more"]) for r in warn],
      [("WARNING", "lava", [])])
bad = [r for r in recs if r["msg"].startswith("  bad frame b'zz_bad;")]
check("game: a warning given at import is in the file",
      [(r["level"], r["name"], r["more"]) for r in recs if r["msg"] == NO_ZONE],
      [("WARNING", "lava", [])])
check("game: and on stderr, once, as it always was (no stamp: logging is not set up yet)",
      [filed.err().count(NO_ZONE), plain.err().count(NO_ZONE)], [1, 1])
# The traders' «stock: ...», one record per trader and all of one kind, are
# more than the limit lets through in a minute: the start is written whole.
check("game: every «stock:» line of the start is in the file, none held back",
      sum(r["msg"].startswith("stock: ") for r in recs),
      sum(bool(re.match(r"^%s stock: " % STAMP, l)) for l in filed.err()))
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
# What came before main's basicConfig is on stderr bare, as logging prints
# a record with no handler set up (logging.lastResort).
missing = []
lines = filed.err()
for r in recs:
    head = "%s %s" % (r["stamp"], r["msg"])
    at = [i for i, l in enumerate(lines) if l in (head, r["msg"])]
    if not at or lines[at[0] + 1:at[0] + 1 + len(r["more"])] != r["more"]:
        missing.append(head)
check("game: every record of the file is on stderr, same time, same lines", missing, [])
check("game: the traceback is on stderr once", lines.count(TRACEBACK), 1)

# --- rotation, and a log level above WARNING --------------------------------------
#
# 2 KiB instead of 2 MiB; the frames overflow it a few times over, and the
# warnings they make are below what LAVA_LOG_LEVEL=ERROR lets on stderr.
# All of them one kind, so without the limit (LAVA_ERR_LOG_RATE=0).
N = 120
rot_dir = os.path.join(TMP, "rot")
rot = os.path.join(rot_dir, "game.err")
port = free_port()
proc = Proc("server.py", env_for("rot", LAVA_PORT=port, LAVA_ERR_LOG=rot, LAVA_ERR_LOG_RATE=0,
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

# --- a flood: twenty of a kind a minute, and the start stays --------------------
#
# A socket that never says hello sends five thousand unknown commands and two
# hundred frames that cannot be read, each a traceback. Without the limit
# that is half a megabyte, the three files of 32 KiB many times over, and
# what the server wrote at start would be gone from all of them.
FLOOD, BAD = 5000, 200
flood_dir = os.path.join(TMP, "flood")
flood = os.path.join(flood_dir, "game.err")


def records(where):
    """Every record of the three files, oldest first."""
    out = []
    for name in ("game.err.2", "game.err.1", "game.err"):
        out += parse(read(os.path.join(where, name)))[0]
    return out


port = free_port()
proc = Proc("server.py", env_for("flood", LAVA_PORT=port, LAVA_ERR_LOG=flood,
                                 LAVA_ERR_LOG_BYTES=32768, LAVA_BOSS_TZ="Mars/Olympus"))
try:
    s = testkit.connect(port, proc.p, proc._err)
    # Listening: what the start wrote is in.
    start = [(r["stamp"], r["msg"]) for r in records(flood_dir)]
    s.sendall(b"".join(b"zz_flood_%d;\x00" % i for i in range(FLOOD))
              + b"zz_bad;a=@x\x00" * BAD + b"zz_last;\x00")
    proc.wait_for(lambda l: l.endswith("unimplemented command 'zz_last'"), timeout=120)
    s.close()
finally:
    proc.stop()
after = records(flood_dir)
kept = {(r["stamp"], r["msg"]) for r in after}
check("flood: the start was written (the zone warning among it)",
      any(m == NO_ZONE for _s, m in start), True)
check("flood: every record of the start is still in the files",
      [m for st, m in start if (st, m) not in kept], [])
check("flood: stderr has every one of them, as before",
      [sum("unimplemented command 'zz_flood_" in l for l in proc.err()),
       proc.err().count("ValueError: substring not found")], [FLOOD, BAD])


def flood_kind(template, first):
    """(written, holding notes, counted) of one kind in the files."""
    written = [r for r in after if r["msg"].startswith(first)]
    held = ("  ..    more than 20 a minute of %r: the rest of this minute's are not"
            " written here" % template)
    notes = [r for r in after if r["msg"] == held]
    counted = [int(m.group(1)) for r in after for m in [re.match(
        r"^  \.\.    (\d+) more of %s in the minute from \d\d:\d\d:\d\d were not"
        r" written here$" % re.escape(repr(template)), r["msg"])] if m]
    return written, notes, counted


for what, template, first, sent in (
        ("unknown commands", "  ??    unimplemented command %r", "  ??    unimplemented command", FLOOD + 1),
        ("bad frames", "  bad frame %r", "  bad frame b'zz_bad", BAD)):
    written, notes, counted = flood_kind(template, first)
    # One minute as a rule; a runner slow enough to cross into a second
    # one has a second twenty, a second note and a second count.
    check("flood, %s: twenty a minute, a note and a count for each minute" % what,
          (len(written) <= 20 * len(counted), len(notes), len(counted) >= 1),
          (True, len(counted), True))
    check("flood, %s: all accounted for, written or counted" % what,
          len(written) + sum(counted), sent)

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
      [bool(re.match(r"^(%s )?error log .*game\.err cannot be opened \(\w+: " % STAMP, l))
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
