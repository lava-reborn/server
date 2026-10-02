"""What the two services write, held to how the CI deploy gate reads it.

deploy/remote/lava-gate.sh decides whether a deploy stays or is rolled back
partly from the services' logs, and it reads them by four patterns of its
own (README «CI/CD», lava-gate.sh "THE LOGS"):

  GAME_READY, HTTP_READY   the line each service writes once it listens;
                           what is above it is the process starting, where
                           no visitor can have written anything
  ERROR_PATTERN            a traceback, the exception line that ends one, or
                           the "  !!    " marker right after the asctime
  CRASH_PATTERN            a traceback's first line

A traceback in the start-up rolls the deploy back; one after the ready line
may be anybody's doing -- a frame the game cannot decode, a launcher that
hangs up mid-download -- and is only reported. Those patterns are text in a
shell script and the lines they must find are format strings here, so this
holds the two to each other: the ready lines are what the servers write,
the marker matches the server's own failures and not a client's frame that
merely carries the same characters, and the http service writes a dropped
connection as one access line, not a traceback.
"""
import contextlib
import io
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE = os.path.join(ROOT, "deploy", "remote", "lava-gate.sh")
sys.path.insert(0, HERE)

from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- the gate's patterns, read the way bash reads its assignments ----------
#
# Only what lava-gate.sh uses for these: NAME='literal' or NAME="text" with
# $NAME expanded and \\ \( \$ \" unescaped. Bash need not be here (the suites
# run on Windows too).

def gate_vars(path):
    found = {}
    for line in io.open(path, encoding="utf-8"):
        m = re.match(r"^([A-Z_]+)=(['\"])(.*)\2\s*(#.*)?$", line.rstrip("\n"))
        if not m:
            continue
        name, quote, body = m.group(1), m.group(2), m.group(3)
        if quote == '"':
            # One pass, as bash does it: what a variable expands to is not
            # unescaped again.
            body = re.sub(r'\\([\\$"`])|\$\{?([A-Z_]+)\}?',
                          lambda v: v.group(1) or found.get(v.group(2), ""), body)
        found[name] = body
    return found


G = gate_vars(GATE)
for name in ("STAMP", "GAME_READY", "HTTP_READY", "ERROR_PATTERN", "CRASH_PATTERN"):
    check("lava-gate.sh sets %s" % name, bool(G.get(name)), True)
# The gate runs them through grep -E; these use nothing grep -E and Python
# read differently (anchors, groups, alternation, {n}, bracket classes).
GAME_READY = re.compile(G["GAME_READY"])
HTTP_READY = re.compile(G["HTTP_READY"])
ERROR = re.compile(G["ERROR_PATTERN"])
CRASH = re.compile(G["CRASH_PATTERN"])

# --- the game: its log format and its own lines -----------------------------
src = io.open(os.path.join(HERE, "server.py"), encoding="utf-8").read()
fmt = re.search(r'logging\.basicConfig\(.*?format="([^"]+)"', src, re.S).group(1)
check("the game logs with the asctime in front", fmt, "%(asctime)s %(message)s")


def game_line(msg, *args):
    """One line as server.py's logging writes it (its basicConfig format)."""
    import logging
    rec = logging.LogRecord("lava", logging.INFO, "server.py", 1, msg, args, None)
    return logging.Formatter(fmt).format(rec)


def said(pattern):
    """The format string server.py hands to log.<level>, found in the source."""
    m = re.search(r'log\.\w+\("(%s)"' % pattern, src)
    return m.group(1) if m else None


ready_fmt = said(r"game server on [^\"]*")
check("server.py logs the game's ready line", ready_fmt, "game server on %s:%d")
ready = game_line(ready_fmt, "0.0.0.0", 9775)
check("GAME_READY finds it", bool(GAME_READY.search(ready)), True)

marker_fmt = said(r"  !!    handler for %r failed")
check("server.py marks a handler that failed", marker_fmt, "  !!    handler for %r failed")
check("ERROR_PATTERN finds the server's own marker",
      bool(ERROR.search(game_line(marker_fmt, "hello"))), True)

# What a client decides: every frame is logged as it came, so a frame that
# carries the marker or the ready text puts them in the log -- after the
# asctime and the frame's own prefix, never right after the asctime.
frame_fmt = said(r"  C->S  %s %s")
check("server.py logs every frame", frame_fmt, "  C->S  %s %s")
for label, cmd, params in (
        ("the marker in a parameter", "hello", {"a": "  !!    "}),
        ("the marker in the command", "  !!    x", {}),
        ("a traceback in a parameter", "x", {"a": "Traceback (most recent call last):"}),
        ("the ready text in a parameter", "x", {"a": " game server on "})):
    line = game_line(frame_fmt, cmd, params)
    check("a frame with %s: not an error line" % label, bool(ERROR.search(line)), False)
    check("a frame with %s: not the ready line" % label, bool(GAME_READY.search(line)), False)
bad_fmt = said(r"  bad frame %r")
check("server.py logs a frame it cannot read", bad_fmt, "  bad frame %r")
check("that line itself is no error line",
      bool(ERROR.search(game_line(bad_fmt, b"x;a=@  !!    @"))), False)

for line, want in (("Traceback (most recent call last):", True),
                   ("ValueError: could not convert string to float: 'nan'", True),
                   ("json.decoder.JSONDecodeError: Expecting value", True),
                   ("  File \"server.py\", line 1, in <module>", False),
                   ("  HTTP 1.2.3.4 \"GET /Traceback HTTP/1.1\" 404 -", False)):
    check("ERROR_PATTERN on %r" % line[:40], bool(ERROR.search(line)), want)
check("CRASH_PATTERN is a traceback's first line",
      bool(CRASH.search("Traceback (most recent call last):")), True)

# --- the http service: its ready line and a visitor who hangs up -----------
#
# In process first, where it is certain to happen: socketserver calls
# handle_error inside the except block of the failed request.
import bootstrap_http  # noqa: E402

srv = bootstrap_http.Server.__new__(bootstrap_http.Server)
for exc in (ConnectionResetError(104, "Connection reset by peer"),
            BrokenPipeError(32, "Broken pipe"), ConnectionAbortedError()):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            raise exc
        except Exception:
            srv.handle_error(None, ("203.0.113.9", 5555))
    check("%s: one access line" % type(exc).__name__, out.getvalue(),
          "  HTTP 203.0.113.9 dropped the connection (%s)\n" % type(exc).__name__)
    check("%s: nothing on stderr" % type(exc).__name__, err.getvalue(), "")
out, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    try:
        raise ValueError("a handler bug")
    except Exception:
        srv.handle_error(None, ("203.0.113.9", 5555))
# Line by line, as grep reads the log.
check("any other error still gets its traceback",
      [bool(CRASH.search(l)) for l in err.getvalue().splitlines()].count(True), 1)
check("and its exception line",
      [l for l in err.getvalue().splitlines() if ERROR.search(l) and not CRASH.search(l)],
      ["ValueError: a handler bug"])

# Then the real process: it says it listens, and launchers hanging up in the
# middle of the string table leave no traceback behind.
port = free_port()
env = dict(os.environ, LAVA_HTTP_PORT=str(port), LAVA_HTTP_HOST="127.0.0.1",
           PYTHONIOENCODING="utf-8")
http = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        encoding="utf-8", errors="replace")
# Both pipes drained as they fill (a pipe nobody reads blocks the server at
# 64 KB), and apart: the ready line is stdout's, a traceback stderr's.
_out, _err = [], []
_drains = [threading.Thread(target=lambda: _out.extend(http.stdout), daemon=True),
           threading.Thread(target=lambda: _err.extend(http.stderr), daemon=True)]
for t in _drains:
    t.start()
base = "http://127.0.0.1:%d" % port
dropped = 0
try:
    deadline = time.time() + 180
    while time.time() < deadline and not any(HTTP_READY.search(l) for l in list(_out)):
        if http.poll() is not None:
            break
        time.sleep(0.1)
    ready_lines = [l.rstrip("\n") for l in list(_out) if HTTP_READY.search(l)]
    check("bootstrap_http prints the ready line HTTP_READY finds",
          ready_lines, ["http serving on 127.0.0.1:%d" % port])
    if ready_lines:
        size = json.loads(urllib.request.urlopen(base + "/exe/lavaclient/manifest", timeout=60)
                          .read().decode("utf-8"))["resources"][0]["size"]
        for _ in range(3):
            s = socket.socket()
            # A small window before connecting, so the server is still
            # writing when the reset comes.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.connect(("127.0.0.1", port))
            s.sendall(b"GET /exe/lavaclient/texts.xml HTTP/1.1\r\nHost: x\r\n\r\n")
            s.recv(1024)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            s.close()                      # RST, mid-way through the table
            time.sleep(0.5)
        check("and still answers after three of them",
              b'"ok": true' in urllib.request.urlopen(base + "/status", timeout=10).read(), True)
        time.sleep(0.5)
        dropped = sum("dropped the connection" in l for l in list(_out))
        print("  ..  string table %d bytes; %d of 3 hang-ups came while it was "
              "still being written" % (size, dropped))
finally:
    http.terminate()
    try:
        http.wait(timeout=10)
    except Exception:
        http.kill()
    for t in _drains:
        t.join(timeout=5)
crashes = [l for l in _out + _err if CRASH.search(l) or ERROR.search(l)]
check("no traceback or error line from the http service", crashes, [])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("http log OK")
