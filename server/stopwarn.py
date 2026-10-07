"""A stop announced ahead of time: the countdown players see before a restart.

Until this, a deploy stopped the game the moment it restarted the container:
shutdown() sends every session «shutdown;seconds=0;» and closes it in the
same breath, so the client's alert -- «Сервер будет остановлен через N
секунд» (Session.as:216) -- came up with the game already gone (issue #73).
Now the deploy announces the stop, waits it out, and only then restarts; the
players count it down in the client's own alert.

WHAT THE PLAYERS SEE

The frame is the one the client always had, shutdown;seconds=N, and the
client has nothing else to say it with: the server's own chat lines are off
in production (server.SERVER_CHAT). Its alert is modal -- it takes the
location's cursor and the hot keys until OK is pressed -- and while one is
open the next does not replace it (SceneShifter.openNewWindow only
re-centres the open one). So the frames are few: one when the stop is
announced, one at every whole minute left, then MARKS_LAST (30 and 10
seconds) before; the stop itself sends 0, as it always has
(server.shutdown). Every number told is a multiple of STEP: the client
pastes it in front of " секунд" as it is, and 5, 10, 35 read right where
1, 2 or 21 would not.

Who logs in during a countdown is told what is left at once, rounded down
to STEP, and no mark he has been told already is repeated to him. Everybody
with an account gets the frames -- in the world, on the map, at the
character screen; in a fight too, which close() ends at the stop. There is
no separate warning for fights: the alert is the same for all.

A countdown called off is not unsaid: the client has no frame that closes
its alert, so an alert already open stays until the player closes it, and
no further one comes.

WHO MAY START ONE

The admins and root on the host, nobody else. An order is a row in
admin_actions -- kind 'stop' with its seconds, or 'stop_cancel' -- the queue
the admin panel already writes and the game already reads once a second
(server.drain_admin_actions): no port, and no frame a client could send
(Session has no cmd_ for it). The panel writes it behind its sign-in
(bootstrap_http, «Остановка сервера»); the deploy writes it with this
file's command line, run inside the game's container (docker exec), where
the database is:

    python3 stopwarn.py start SECONDS [--by WHO] [--skip-empty] [--wait S]
    python3 stopwarn.py cancel [--by WHO] [--wait S]
    python3 stopwarn.py status
    python3 stopwarn.py cancelled SECONDS

The first three print one line, "LEFT PLAYERS": the seconds to the stop
announced (0 once its time is up) or "-" when none is, and how many are
logged in now.
start announces SECONDS from now, MIN_SECONDS to MAX_SECONDS; with
--skip-empty it announces nothing when nobody is logged in, and the deploy
then restarts at once. A countdown already running is left as it is --
what the players were told stands -- and start answers with what is left
of it. start and cancel wait up to --wait seconds for the game to carry
the order out; one it never took up is withdrawn, so a game started later
does not act on it, and the game refuses a stop order older than
ORDER_FRESH seconds anyway.

cancelled prints how many countdowns an order called off in the last
SECONDS: stop_cancel orders the game carried out with one running (CANCELLED
in their result). The deploy asks it when the countdown it waits on is gone:
gone with such an order, somebody called it off and nothing is restarted;
gone without one, it went with the game's process -- a crash docker brought
back, a stop by hand, whose players are cut off already -- and the restart
goes on. A process that ends drops its countdown (forget(), and the next one
starts with none), so stop_plan alone cannot tell the two apart.

Exit status: 0 done; 2 a wrong command line, or an order the game refused;
3 a game that does not know the order (older than this file); 4 no answer
from the game -- not running, or not within --wait.

THE END OF A COUNTDOWN

The game does not stop itself at zero: restart: unless-stopped would bring
the same old image straight back, and the deploy's "up" would then restart
it a second time. The deploy restarts it (deploy/deploy.sh,
deploy/remote/lava-gate.sh), and the SIGTERM that brings is the stop the
players were told of, everyone saved as at every stop. A countdown whose
time is up waits DUE_GRACE seconds for that and is then forgotten (a deploy
that died half-way, a button pressed with no deploy behind it); a restart
forgets it as well.

WHERE IT IS WRITTEN

stop_plan (accounts.SCHEMA), one row, rewritten by the game whenever what
it says changes: the stop's second, when and by whom it was announced, and
how many are logged in. The panel and `status` read it, with the game's
heartbeat for whether it is current.
"""
import argparse
import asyncio
import json
import logging
import math
import os
import sys
import time

log = logging.getLogger("lava")

# Seconds of warning a deploy gives when it is not told otherwise: deploy.sh
# (--warn, LAVA_STOP_WARN_SEC) and the gate (STOP_WARN_SEC in gate.conf)
# carry the same number. The panel offers it in minutes.
DEFAULT_SECONDS = 180
# The shortest and the longest countdown an order may ask for. The longest
# is also the gate's cap on its wait (STOP_WARN_MAX) and the panel's
# MAX_SECONDS // 60 minutes.
MIN_SECONDS = 10
MAX_SECONDS = 600
# Every number the players are told is a multiple of this.
STEP = 5
# The marks inside the last minute; above it, every whole minute.
MARKS_LAST = (30, 10)
# How long a countdown whose time is up waits for the restart before the
# game forgets it. LAVA_STOP_GRACE is for the suite (test_stopwarn), which
# cannot wait two minutes to see it go.
DUE_GRACE = int(os.environ.get("LAVA_STOP_GRACE") or 120)
# A stop order that waited longer than this in the queue is refused: the
# deploy that asked for it gave up long ago, and a countdown out of nowhere
# would tell the players of a stop nobody is going to make.
ORDER_FRESH = 30
# A heartbeat older than this is a game that is not running (the panel's
# own threshold, bootstrap_http._admin_panel).
BEAT_FRESH = 15
# How long start and cancel wait for the game to carry the order out.
WAIT = 15.0

# The game's answers that the command line reads: a refusal starts with
# REFUSED; an order the game does not know comes back as one of UNKNOWN
# (server.apply_admin_action's own words, before and after this file).
REFUSED = "отказ"
UNKNOWN = ("действию нужен персонаж", "неизвестное действие")
# And the start of the answer to a stop_cancel that found a countdown to call
# off (Countdown.cancel), which `cancelled` counts.
CANCELLED = "отменена"


def marks(seconds):
    """The numbers a countdown of `seconds` tells after its first: each
    whole minute below it, then MARKS_LAST. 180 -> [120, 60, 30, 10]."""
    seconds = int(seconds)
    out = [m for m in range(seconds // 60 * 60, 0, -60) if m < seconds]
    return out + [m for m in MARKS_LAST if m < seconds and m not in out]


def spoken(left):
    """What a player is told with `left` seconds to go: the multiple of STEP
    at or below it, so the stop never comes sooner than said."""
    return max(0, int(left)) // STEP * STEP


def msk(when):
    """An epoch second as Moscow's clock shows it. Moscow has kept UTC+3 all
    year round since 2014, so no time zone database is needed for it."""
    return time.strftime("%H:%M:%S", time.gmtime(int(when) + 3 * 3600))


class Countdown:
    """The game's side: the stop announced, the frames that count it down,
    and the stop_plan row that says so to the other processes.

    players() is every live session with an account, the people a stop
    disconnects (server.py hands it SESSIONS that way); store writes
    stop_plan. The timer is the event loop's, so start() and cancel() run
    on the loop -- they are called from the admin queue's pass."""

    def __init__(self, players, store, clock=time.time):
        self.players = players
        self.store = store
        self.clock = clock
        self.stop_at = None          # epoch second of the stop, or None
        self.made_at = 0             # when it was announced
        self.admin = ""              # and by whom
        self.pending = []            # marks still to tell, largest first
        self.told = {}               # session -> the last number it was told
        self.timer = None
        self.written = None          # stop_plan as last written

    # --- what is announced ------------------------------------------------
    def left(self):
        """Seconds to the stop, 0 once its time is up; None with no stop."""
        if self.stop_at is None:
            return None
        return max(0, self.stop_at - self.clock())

    def start(self, seconds, admin, made_at=None, skip_empty=False):
        """Announce a stop `seconds` from now, unless one is announced
        already; the answer for the panel's log."""
        now = self.clock()
        if made_at and now - float(made_at) > ORDER_FRESH:
            return "%s: приказ пролежал в очереди %d с, устарел" % (REFUSED, now - float(made_at))
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            return "%s: срок не число (%r)" % (REFUSED, seconds)
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            return "%s: срок от %d до %d с, а не %d" % (REFUSED, MIN_SECONDS, MAX_SECONDS, seconds)
        players = self.players()
        if self.stop_at is not None:
            self.publish()
            return "уже объявлена (%s): через %d с, в игре %d" % (
                self.admin or "?", math.ceil(self.left()), len(players))
        if skip_empty and not players:
            self.publish()
            return "в игре никого: остановка без отсчёта"
        self.stop_at = math.ceil(now + seconds)
        self.made_at = int(now)
        self.admin = str(admin or "")
        self.pending = marks(seconds)
        self.told = {}
        first = spoken(seconds)
        for sess in players:
            self._tell(sess, first)
        self._arm()
        self.publish()
        log.info("  ..    stop announced by %s: in %d s, %d player(s) told",
                 self.admin, seconds, len(players))
        return "остановка через %d с, в игре %d" % (seconds, len(players))

    def cancel(self, admin):
        """Call the stop off; the answer for the panel's log."""
        if self.stop_at is None:
            self.publish()
            return "отменять нечего"
        left = math.ceil(self.left())
        self._clear()
        self.publish()
        log.info("  ..    stop called off by %s with %d s left", admin, left)
        return "%s (оставалось %d с)" % (CANCELLED, left)

    def forget(self):
        """The game is going (server.shutdown): no countdown outlives it."""
        self._clear()
        self.publish()

    # --- the players --------------------------------------------------------
    def greet(self, sess):
        """A player who logs in during a countdown is told what is left."""
        if self.stop_at is None:
            return
        n = spoken(self.left())
        if n >= STEP:
            self._tell(sess, n)

    def _tell(self, sess, n):
        told = self.told.get(sess)
        if told is not None and told <= n:
            return
        if getattr(sess, "closed", False):
            return
        self.told[sess] = n
        try:
            sess.send("shutdown", seconds=n)
        except Exception:                                   # noqa: BLE001
            # A socket going away under the frame is that player's
            # business; the others are told all the same.
            log.info("  ..    stop frame to a closing session not sent")

    # --- the timer ------------------------------------------------------------
    def _arm(self):
        self._disarm()
        if self.stop_at is None:
            return
        now = self.clock()
        if self.pending:
            delay = self.stop_at - self.pending[0] - now
        else:
            delay = self.stop_at + DUE_GRACE - now
        self.timer = asyncio.get_running_loop().call_later(max(0.0, delay), self._tick)

    def _disarm(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def _tick(self):
        self.timer = None
        try:
            if self.stop_at is None:
                return
            left = self.stop_at - self.clock()
            # A little early is on time: the loop's clock and the wall's
            # are not the same clock. A tick that came late past two marks
            # tells the later one only.
            due = [m for m in self.pending if left <= m + 0.5]
            if due:
                self.pending = [m for m in self.pending if m not in due]
                n = min(due)
                for sess in self.players():
                    self._tell(sess, n)
            elif not self.pending and left <= 0.5 - DUE_GRACE:
                log.info("  ..    stop announced by %s was due %d s ago and"
                         " nobody restarted: forgotten", self.admin, -left)
                self._clear()
                self.publish()
                return
            self._arm()
        except Exception:                                   # noqa: BLE001
            log.exception("  ..    stop countdown tick failed")
            self._arm()

    def _clear(self):
        self._disarm()
        self.stop_at = None
        self.made_at = 0
        self.admin = ""
        self.pending = []
        self.told = {}

    # --- what the other processes read ---------------------------------------
    def publish(self):
        """Write stop_plan if what it says has changed (called on every pass
        of the admin queue, and by start and cancel before they answer, so
        the answer is never ahead of the row)."""
        row = (self.stop_at, self.made_at, self.admin, len(self.players()))
        if row != self.written:
            self.store.set_stop_plan(*row)
            self.written = row


# --- the command line (docker exec lava-game python3 stopwarn.py ...) --------

def _db():
    import accounts
    import storage
    return storage.connect(accounts.DB_PATH)


def _beat(db):
    if not db.columns("heartbeat"):
        return None
    row = db.execute("SELECT at FROM heartbeat WHERE id = 1").fetchone()
    return int(row["at"]) if row else None


def read_status(db, now=None):
    """(left, players) as the game last wrote them -- left "-" with no stop
    announced -- or None when the game is not writing (no heartbeat lately,
    or no stop_plan yet)."""
    db.commit()                     # a fresh snapshot, nothing held open
    now = time.time() if now is None else now
    beat = _beat(db)
    if beat is None or now - beat > BEAT_FRESH or not db.columns("stop_plan"):
        return None
    row = db.execute("SELECT stop_at, players FROM stop_plan WHERE id = 1").fetchone()
    if row is None:
        return None
    left = "-" if row["stop_at"] is None else max(0, math.ceil(row["stop_at"] - now))
    return left, int(row["players"])


def cancels(db, within, now=None):
    """How many countdowns an order called off in the last `within` seconds:
    the stop_cancel orders the game carried out and that found one to call
    off. An order withdrawn unanswered, or one with nothing to call off,
    does not count, and nor does a countdown gone with its process."""
    db.commit()
    now = time.time() if now is None else now
    rows = db.execute("SELECT result FROM admin_actions WHERE kind = ?"
                      " AND done_at IS NOT NULL AND done_at >= ?",
                      ("stop_cancel", int(now - within))).fetchall()
    return sum(1 for r in rows if str(r["result"] or "").startswith(CANCELLED))


def _order(db, who, kind, args, wait):
    """Queue one order and wait for the game's answer: its result, or None
    when it did not come (the row is then withdrawn)."""
    action = db.insert(
        "INSERT INTO admin_actions (made_at, admin, kind, char_id, account_id,"
        " args_json) VALUES (?, ?, ?, NULL, NULL, ?)",
        (int(time.time()), who, kind, json.dumps(args, ensure_ascii=False)),
        returning="id")
    db.commit()
    end = time.time() + wait
    while True:
        db.commit()
        row = db.execute("SELECT done_at, result FROM admin_actions WHERE id = ?",
                         (action,)).fetchone()
        if row is not None and row["done_at"] is not None:
            return str(row["result"] or "")
        if time.time() >= end:
            break
        time.sleep(0.2)
    db.execute("UPDATE admin_actions SET done_at = ?, result = ? WHERE id = ?"
               " AND done_at IS NULL",
               (int(time.time()), "не дождались ответа игры: отозвано", action))
    db.commit()
    return None


def _say(status):
    print("%s %d" % status)
    sys.stdout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="stopwarn.py",
        description="Announce a stop to the players, call it off, or say where it stands.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start", help="announce a stop SECONDS from now")
    p.add_argument("seconds", type=int)
    p.add_argument("--by", default="console", help="who, as the panel's log shows it")
    p.add_argument("--skip-empty", action="store_true",
                   help="announce nothing when nobody is logged in")
    p.add_argument("--wait", type=float, default=WAIT)
    p = sub.add_parser("cancel", help="call the stop off")
    p.add_argument("--by", default="console")
    p.add_argument("--wait", type=float, default=WAIT)
    sub.add_parser("status", help="the stop announced and who is logged in")
    p = sub.add_parser("cancelled", help="how many countdowns an order called off"
                                         " in the last SECONDS")
    p.add_argument("seconds", type=int)
    args = ap.parse_args(argv)

    if args.cmd == "start" and not MIN_SECONDS <= args.seconds <= MAX_SECONDS:
        print("stopwarn: SECONDS from %d to %d" % (MIN_SECONDS, MAX_SECONDS), file=sys.stderr)
        return 2
    if args.cmd == "cancelled" and args.seconds < 1:
        print("stopwarn: SECONDS from 1", file=sys.stderr)
        return 2
    db = _db()
    try:
        if args.cmd == "cancelled":
            # The orders' log, whether the game runs or not.
            print(cancels(db, args.seconds))
            sys.stdout.flush()
            return 0
        status = read_status(db)
        if status is None:
            print("stopwarn: the game is not running (no fresh heartbeat or stop_plan)",
                  file=sys.stderr)
            return 4
        if args.cmd == "status":
            _say(status)
            return 0
        if args.cmd == "start":
            order = {"seconds": args.seconds}
            if args.skip_empty:
                order["skip_empty"] = True
            result = _order(db, args.by, "stop", order, args.wait)
        else:
            result = _order(db, args.by, "stop_cancel", {}, args.wait)
        if result is None:
            print("stopwarn: no answer from the game in %gs; the order is withdrawn"
                  % args.wait, file=sys.stderr)
            return 4
        print("stopwarn: the game says: %s" % result, file=sys.stderr)
        if result.startswith(UNKNOWN):
            return 3
        status = read_status(db)
        if status is None:
            return 4
        _say(status)
        return 2 if result.startswith(REFUSED) else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
