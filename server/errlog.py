"""The warnings-and-errors file the admin panel shows (README «Журнал ошибок»).

Both services write their log to stdout and stderr, which is docker's log,
and the admin panel (lava-admin, a container of its own) cannot read that.
It can read the volume it shares with them, so WARNING and above also goes
to a file there, the one LAVA_ERR_LOG names: /var/lib/lava/logs/game.err for
the game, http.err beside it for the http service (docker-compose.yml); the
panel mounts the same volume at /data. LAVA_ERR_LOG unset -- every local run
and every suite but test_err_log -- and there is no file, and nothing here
touches logging at all.

The file is a contract with the panel, and it is written to that one shape:

  * a record is a first line «2026-10-07 14:03:11,512 ERROR lava: message»
    (FORMAT; the asctime is the process's local time, which is UTC in the
    containers: neither the image nor compose sets TZ) and then any number
    of continuation lines -- a traceback, the rest of a message -- none of
    which starts with a digit, so none can pass for the first line of a
    record: one that would is pushed in by a space (Formatter). A message
    that carries \\r or another line break is cut there too, and the pieces
    held to the same rule;
  * UTF-8, and what will not encode is written escaped, not lost;
  * RotatingFileHandler at MAX_BYTES (2 MiB; LAVA_ERR_LOG_BYTES for the
    tests) with BACKUPS (2) old ones: game.err, game.err.1 the newer,
    game.err.2 the older. A record is never split between two files.

What goes to stdout and stderr does not change: the deploy gate reads them
(deploy/remote/lava-gate.sh, "THE LOGS"), and server/test_http_log.py holds
the two to each other. Nor is the file ever a reason for a server not to
run: one that cannot be opened is one warning in the log, and one that
stops taking writes (a full disk) is one line on stderr, after which the
records go to the log alone until it takes them again.

Uncaught exceptions reach the file too (hook): the interpreter prints them
on stderr itself, without logging, and they are the ones that matter most --
a server that stopped, at start (a table that does not load) or later.
asyncio needs nothing of the kind: its default exception handler (a task
that failed with nobody awaiting it, a callback that raised) already logs,
as "asyncio" at ERROR.
"""
import logging
import logging.handlers
import os
import re
import sys
import threading

ENV = "LAVA_ERR_LOG"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 2
# Below this a rotation would be most of the writes.
MIN_BYTES = 1024

log = logging.getLogger("lava")

# A record's first line begins with its date; a continuation line that
# begins with any digit is pushed in, which keeps the rule simpler than any
# pattern a reader might match a timestamp with.
_DIGIT = re.compile(r"\d")

_state = dict(handler=None, tried=False, hooked=False)
_only = {}


class Formatter(logging.Formatter):
    """FORMAT, with no continuation line that could be read as a record."""

    def __init__(self):
        super().__init__(FORMAT)

    def format(self, record):
        lines = super().format(record).splitlines() or [""]
        return "\n".join(lines[:1] + [" " + line if _DIGIT.match(line) else line
                                      for line in lines[1:]])


class FileHandler(logging.handlers.RotatingFileHandler):
    """The file, WARNING and above, and quiet about its own failures.

    logging's own handleError prints a traceback per record that could not
    be written, and a traceback on stderr is what the deploy gate rolls a
    deploy back for: a full disk at start would undo a good deploy, and later
    every warning would bring three dozen lines with it. So a failure is one
    line on stderr, said once until a write goes through again.
    """

    def __init__(self, path, max_bytes=MAX_BYTES):
        super().__init__(path, maxBytes=max_bytes, backupCount=BACKUPS,
                         encoding="utf-8", errors="backslashreplace")
        self.setLevel(logging.WARNING)
        self.setFormatter(Formatter())
        self.failing = False
        self._failed = False

    def emit(self, record):
        self._failed = False
        super().emit(record)
        if not self._failed:
            self.failing = False

    def handleError(self, record):
        self._failed = True
        if self.failing:
            return
        self.failing = True
        exc = sys.exc_info()[1]
        try:
            sys.stderr.write("error log %s cannot be written (%s: %s); warnings and"
                             " errors go to this log only until it can\n"
                             % (self.baseFilename, type(exc).__name__, exc))
            sys.stderr.flush()
        except Exception:                                   # noqa: BLE001
            pass


def path():
    """The file LAVA_ERR_LOG names, or None."""
    return os.environ.get(ENV, "").strip() or None


def max_bytes():
    try:
        wanted = int(os.environ.get("LAVA_ERR_LOG_BYTES") or MAX_BYTES)
    except ValueError:
        wanted = MAX_BYTES
    return max(MIN_BYTES, wanted)


def handler():
    """The file's handler, opened on the first call; None without one.

    Tried once per process: a file that cannot be opened says so once, as a
    warning in the log, and the server carries on without it.
    """
    if _state["handler"] is not None or _state["tried"]:
        return _state["handler"]
    _state["tried"] = True
    where = path()
    if where is None:
        return None
    try:
        os.makedirs(os.path.dirname(os.path.abspath(where)), exist_ok=True)
        h = FileHandler(where, max_bytes())
    except OSError as exc:
        log.warning("error log %s cannot be opened (%s: %s); warnings and errors"
                    " go to this log only", where, type(exc).__name__, exc)
        return None
    _state["handler"] = h
    for lg in _only.values():
        lg.addHandler(h)
    return h


def only(name):
    """A logger that writes to the file and nowhere else.

    For what already reaches stderr by a way of its own -- the interpreter's
    traceback of an uncaught exception, socketserver's of a request that
    failed -- and through the root logger would be there twice. Without the
    file it writes nowhere: the NullHandler is what keeps a record off
    logging.lastResort, which is stderr.
    """
    lg = _only.get(name)
    if lg is None:
        lg = _only[name] = logging.getLogger(name)
        lg.propagate = False
        lg.setLevel(logging.WARNING)
        lg.addHandler(logging.NullHandler())
        if _state["handler"] is not None:
            lg.addHandler(_state["handler"])
    return lg


def _uncaught(level, msg, exc_info, *args):
    # Never in the way of the hook it stands in front of.
    try:
        if handler() is not None:
            only("lava.uncaught").log(level, msg, *args, exc_info=exc_info)
    except Exception:                                       # noqa: BLE001
        pass


def hook():
    """Uncaught exceptions to the file as well, the main thread's and any
    other's; the hooks that were there before still run after, so stderr
    gets what it always got. Nothing at all without LAVA_ERR_LOG.

    The entry scripts call it before importing the game's modules, which
    read their tables as they are imported: a table that stops the server
    there is a crash the panel should show too. The file is opened when the
    first one comes, so this costs nothing until then.
    """
    if _state["hooked"] or path() is None:
        return
    _state["hooked"] = True
    before_main, before_thread = sys.excepthook, threading.excepthook

    def main_hook(kind, exc, tb):
        if not (isinstance(kind, type) and issubclass(kind, KeyboardInterrupt)):
            _uncaught(logging.CRITICAL, "uncaught exception, the process stops",
                      (kind, exc, tb))
        before_main(kind, exc, tb)

    def thread_hook(args):
        # SystemExit ends a thread without a word from the default hook.
        if args.exc_type is not SystemExit:
            _uncaught(logging.ERROR, "uncaught exception in thread %s",
                      (args.exc_type, args.exc_value, args.exc_traceback),
                      args.thread.name if args.thread is not None else "?")
        before_thread(args)

    sys.excepthook = main_hook
    threading.excepthook = thread_hook


def install():
    """WARNING and above to the file, from every logger, if LAVA_ERR_LOG
    names one. Called once logging is set up (server.main after basicConfig,
    bootstrap_http at start); returns the handler, or None.

    Two things are kept as they were on stderr. A process with no handler
    of its own (bootstrap_http) has its warnings printed by
    logging.lastResort, which stops the moment the root has any handler: so
    it becomes one of the root's. And a LAVA_LOG_LEVEL above WARNING would
    keep warnings from the file as well: the level moves from the root to
    the handlers that were already there, and the root takes WARNING.
    """
    hook()
    h = handler()
    if h is None:
        return None
    root = logging.getLogger()
    if h in root.handlers:
        return h
    if not root.handlers and logging.lastResort is not None:
        root.addHandler(logging.lastResort)
    if root.level > logging.WARNING:
        for other in root.handlers:
            if other.level < root.level:
                other.setLevel(root.level)
        root.setLevel(logging.WARNING)
    root.addHandler(h)
    return h
