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

What it holds: everything from the start, the warnings the modules give as
they are imported included (a LAVA_BOSS_TZ that names no zone, the account
store's migrations): the entry scripts install() before importing them.
Once a server serves (serving()), records of one kind -- one logger, one
message template, so every «unimplemented command %r» is one kind -- are
held to RATE a minute (Throttle): an anonymous socket can send a hundred
thousand unknown commands in seconds, and without the limit they would push
everything else out of the file and both backups. What is held back is
still on stderr, and the file says so in two records of its own: one when
the holding starts, one with the count once the minute is over.

What goes to stdout and stderr does not change: the deploy gate reads them
(deploy/remote/lava-gate.sh, "THE LOGS"), and server/test_err_log.py holds
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
import time

ENV = "LAVA_ERR_LOG"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
MAX_BYTES = 2 * 1024 * 1024
BACKUPS = 2
# Below this a rotation would be most of the writes.
MIN_BYTES = 1024
# Records of one kind a minute while a server serves (LAVA_ERR_LOG_RATE for
# the tests; 0 there is no limit). Twenty a minute of the worst kind there
# is, a bad frame with its traceback, is hours to fill the three files.
RATE = 20
WINDOW = 60.0
# Kinds counted at once. The game has a few dozen templates and none is
# formatted before the call; past this the rest are counted as one, so a
# log call that is (one day) would not grow the table without end.
KINDS = 512
OTHER = ("", "")

log = logging.getLogger("lava")

# A record's first line begins with its date; a continuation line that
# begins with any digit is pushed in, which keeps the rule simpler than any
# pattern a reader might match a timestamp with.
_DIGIT = re.compile(r"\d")
# bootstrap_http.TOKEN_IN_QUERY, kept here so this module imports nothing of
# the game's.
_TOKEN_IN_QUERY = re.compile(r"([?&]t=)[^&\s\"]+")

_state = dict(handler=None, tried=False, hooked=False, resort=False, serving=False)
_only = {}


class Formatter(logging.Formatter):
    """FORMAT, with no continuation line that could be read as a record."""

    def __init__(self):
        super().__init__(FORMAT)

    def format(self, record):
        # A link's token (?t=..., e-mail confirmation and password reset) is a
        # key to an account: the file keeps the link, never the key -- the
        # same cut bootstrap_http.log_message makes on the access lines.
        text = _TOKEN_IN_QUERY.sub(r"\1...", super().format(record))
        lines = text.splitlines() or [""]
        return "\n".join(lines[:1] + [" " + line if _DIGIT.match(line) else line
                                      for line in lines[1:]])


def _note(name, text):
    """A record of the file's own, at WARNING, in the name of the logger it
    is about."""
    return logging.makeLogRecord(dict(name=name, levelno=logging.WARNING,
                                      levelname="WARNING", msg=text, args=None))


def _short(value, limit=300):
    text = repr(value)
    return text if len(text) <= limit else text[:limit] + "..."


class _Kind:
    __slots__ = ("since", "wall", "written", "held", "name")

    def __init__(self, since, wall, name):
        self.since, self.wall, self.name = since, wall, name
        self.written = self.held = 0


class Throttle:
    """At most `rate` records of one kind in a minute, once armed.

    A kind is the logger and the message as the call wrote it, before its
    arguments: «unimplemented command %r» is one kind whatever the command.
    Its minute starts with its first record. The first `rate` of them are
    written; the next one is not, and in its place a record says that the
    rest of the minute's are held back; the minute over, a record gives
    their count. That one comes with the next record of any kind (looked
    for once a second at most) or when the file is closed -- the server's
    stop -- whichever is first: a filter has nothing but records to run on.

    Not armed until the server serves (serving()): what it says at start,
    the trader stocks' «stock: ...» one per trader, is written whole.
    """

    def __init__(self, rate):
        self.rate = rate
        self.armed = False
        self.kinds = {}
        self.swept = 0.0

    @staticmethod
    def kind_of(record):
        msg = record.msg if isinstance(record.msg, str) else type(record.msg).__name__
        return record.name, msg

    def admit(self, record, now):
        """(the file's own records to write first, whether to write this
        one); now is time.monotonic()."""
        if not self.armed:
            return [], True
        notes = []
        if now - self.swept >= 1.0:
            self.swept = now
            for key in [k for k, v in self.kinds.items() if now - v.since >= WINDOW]:
                notes += self._over(key)
        key = self.kind_of(record)
        if key not in self.kinds and len(self.kinds) >= KINDS:
            key = OTHER
        kind = self.kinds.get(key)
        if kind is not None and now - kind.since >= WINDOW:
            notes += self._over(key)
            kind = None
        if kind is None:
            kind = self.kinds[key] = _Kind(now, record.created, record.name)
        if kind.written < self.rate:
            kind.written += 1
            return notes, True
        kind.held += 1
        if kind.held == 1:
            notes.append(_note(kind.name, "  ..    more than %d a minute of %s: the rest"
                               " of this minute's are not written here"
                               % (self.rate, self._what(key))))
        return notes, False

    def owed(self):
        """The counts not yet given, every minute's, ended or not."""
        notes = []
        for key in list(self.kinds):
            notes += self._over(key)
        return notes

    def _over(self, key):
        kind = self.kinds.pop(key)
        if not kind.held:
            return []
        return [_note(kind.name, "  ..    %d more of %s in the minute from %s were not"
                      " written here" % (kind.held, self._what(key),
                                         time.strftime("%H:%M:%S", time.localtime(kind.wall))))]

    @staticmethod
    def _what(key):
        return "records of any other kind" if key == OTHER else _short(key[1])


class FileHandler(logging.handlers.RotatingFileHandler):
    """The file, WARNING and above, and quiet about its own failures.

    logging's own handleError prints a traceback per record that could not
    be written, and a traceback on stderr is what the deploy gate rolls a
    deploy back for: a full disk at start would undo a good deploy, and later
    every warning would bring three dozen lines with it. So a failure is one
    line on stderr, said once until a write goes through again.

    A log call whose arguments do not fit its message (a %d given a word) is
    no failure of the file: it is written as a record that shows the call
    (_unformattable), and stderr gets what it always got for it, logging's
    "--- Logging error ---" from the handler there.

    The Throttle is consulted in emit, which logging calls under the
    handler's lock: the counting needs no lock of its own.
    """

    def __init__(self, path, max_bytes=MAX_BYTES, rate=RATE):
        super().__init__(path, maxBytes=max_bytes, backupCount=BACKUPS,
                         encoding="utf-8", errors="backslashreplace")
        self.setLevel(logging.WARNING)
        self.setFormatter(Formatter())
        self.throttle = Throttle(rate) if rate > 0 else None
        self.failing = False
        self._failed = False

    def emit(self, record):
        if self.throttle is not None:
            notes, keep = self.throttle.admit(record, time.monotonic())
            for note in notes:
                self._write(note)
            if not keep:
                return
        self._write(record)

    def _write(self, record):
        try:
            record.getMessage()
        except Exception as exc:                            # noqa: BLE001
            record = self._unformattable(record, exc)
        self._failed = False
        super().emit(record)
        if not self._failed:
            self.failing = False

    @staticmethod
    def _unformattable(record, exc):
        text = ("a log call that cannot be formatted (%s: %s): %s %% %s"
                % (type(exc).__name__, exc, _short(record.msg), _short(record.args)))
        return logging.makeLogRecord(dict(record.__dict__, msg=text, args=None))

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

    def close(self):
        # The counts the Throttle still owes go in before the file shuts:
        # at the server's stop (logging.shutdown) the last flood is counted.
        self.acquire()
        try:
            for note in self.throttle.owed() if self.throttle is not None else []:
                self._write(note)
        finally:
            self.release()
        super().close()


def path():
    """The file LAVA_ERR_LOG names, or None."""
    return os.environ.get(ENV, "").strip() or None


def _env_int(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def max_bytes():
    return max(MIN_BYTES, _env_int("LAVA_ERR_LOG_BYTES", MAX_BYTES))


def rate():
    """RATE, or LAVA_ERR_LOG_RATE for a test; 0 is no limit."""
    return max(0, _env_int("LAVA_ERR_LOG_RATE", RATE))


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
        h = FileHandler(where, max_bytes(), rate())
    except OSError as exc:
        log.warning("error log %s cannot be opened (%s: %s); warnings and errors"
                    " go to this log only", where, type(exc).__name__, exc)
        return None
    if h.throttle is not None:
        h.throttle.armed = _state["serving"]
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
    gets what it always got. Nothing at all without LAVA_ERR_LOG. install()
    calls it.
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
    """WARNING and above to the file, from every logger, and the uncaught
    exceptions (hook), if LAVA_ERR_LOG names one; returns the handler, or
    None. Nothing without it.

    The entry scripts call it before they import the game's modules, which
    read their tables and the environment as they are imported: a warning
    there (a LAVA_BOSS_TZ with no such zone) or a crash (a table that does
    not load) is for the panel too. server.main sets logging up later, and
    takes the file off the root for that (detach) and calls this again.

    Two things are kept as they were on stderr. A process with no handler
    of its own -- bootstrap_http, and the game until main's basicConfig --
    has its warnings printed by logging.lastResort, which stops the moment
    the root has any handler: so it becomes one of the root's, and prints
    them as it did. And a LAVA_LOG_LEVEL above WARNING would keep warnings
    from the file as well: the level moves from the root to the handlers
    that were already there, and the root takes WARNING.
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
        _state["resort"] = True
    if root.level > logging.WARNING:
        for other in root.handlers:
            if other.level < root.level:
                other.setLevel(root.level)
        root.setLevel(logging.WARNING)
    root.addHandler(h)
    return h


def detach():
    """Take what install() put on the root off it again; the file stays
    open. For server.main before its basicConfig, which does nothing at all
    to a root that has a handler already; install() after it puts the file
    back beside basicConfig's handler."""
    root = logging.getLogger()
    h = _state["handler"]
    if h is not None and h in root.handlers:
        root.removeHandler(h)
    if _state["resort"]:
        root.removeHandler(logging.lastResort)
        _state["resort"] = False


def serving():
    """The server serves from here on: records of one kind are held to
    RATE a minute (Throttle). What came before -- the start -- was written
    whole."""
    _state["serving"] = True
    h = _state["handler"]
    if h is not None and h.throttle is not None:
        h.throttle.armed = True
