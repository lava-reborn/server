"""Map interception catches moving players at contact, before either stops.

Drive the real Session movement and catch handlers with a deterministic
clock: crossing between pursuit beats, changed vectors, delayed callbacks,
cancelled pursuits and the map cell sent to both clients. GlobalMap.as
extrapolates each moveAck/userMove vector continuously; the chase must do
the same instead of sampling distance once per second.
"""
import heapq
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["LAVA_DB"] = os.path.join(tempfile.mkdtemp(), "intercept.db")
sys.path.insert(0, HERE)
import server  # noqa: E402
from testkit import check, fails  # noqa: E402


class Handle:
    def __init__(self, at, callback, args):
        self.at, self.callback, self.args = at, callback, args
        self.cancelled = False

    def when(self):
        return self.at

    def cancel(self):
        self.cancelled = True


class Clock:
    def __init__(self):
        self.now, self.serial, self.queue = 0.0, 0, []

    def time(self):
        return self.now

    def call_later(self, delay, callback, *args):
        self.serial += 1
        handle = Handle(self.now + delay, callback, args)
        heapq.heappush(self.queue, (handle.at, self.serial, handle))
        return handle

    def advance(self, until, late=False):
        if late:
            self.now = until
        steps = 0
        while self.queue and self.queue[0][0] <= until:
            at, _, handle = heapq.heappop(self.queue)
            if handle.cancelled:
                continue
            if not late:
                self.now = at
            handle.callback(*handle.args)
            steps += 1
            if steps > 1000:
                raise RuntimeError("chase timer did not advance")
        self.now = until


class Walker(server.Session):
    def __init__(self, ident, x, y=1730.5, speed=1.4):
        self.char_id, self.active = ident, {"name": "walker%d" % ident}
        self.gx, self.gy, self.speed = x, y, speed
        self.on_map, self.closed = True, False
        self.leg = self.arrival = self.chase = self.chase_timer = None
        self.chase_until = 0.0
        self.sent = []
        server.ONLINE.add(self)

    def travel_speed(self):
        return self.speed / server.TRAVEL_SPEED

    def send(self, name, **params):
        self.sent.append((name, params))

    def say(self, text, group=0):
        self.send("userMsg", entry=text)

    def go_to(self, loc_id):
        self.loc = SimpleNamespace(id=loc_id)
        self.send("lcall", id=loc_id)


def calls(walker):
    return [p["id"] for name, p in walker.sent if name == "lcall"]


def scene():
    server.ONLINE.by_char.clear()
    return Walker(1, 5970.8), Walker(2, 5972.2)


# --- contact and movement changes, in process ------------------------------
try:
    with patch.object(server, "ONLINE", server.rooms.Directory()), \
            patch.object(server, "GMAP", SimpleNamespace(moved=lambda s: None,
                                                         leave=lambda s: None)), \
            patch.object(server, "ENCOUNTERS", SimpleNamespace(arm=lambda *a: None,
                                                               disarm=lambda s: None)), \
            patch.object(server.travel, "walk", lambda x, y, dx, dy: (x + dx, y + dy)):
        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            b.step_on_map(-5, 0)
            a.intercept(b.pid)
            clock.advance(0.39)
            check("no interception before contact", (calls(a), calls(b)), ([], []))
            clock.advance(0.5)
            cell = server.world.location_at(5971, 1730)
            check("crossing players enter the contact cell before the first pursuit beat",
                  (calls(a), calls(b)), ([cell], [cell]))
            stops = [p for n, p in a.sent if n == "userMove"]
            check("the map figure stops at contact, not at the quarry's destination",
                  round(stops[-1]["dx"], 6) if stops else None, 5971.65)
            clock.advance(5)
            check("old arrival callbacks cannot move either player after the catch",
                  (a.gx, a.gy, b.gx, b.gy, a.leg, b.leg),
                  (5971, 1730, 5971, 1730, None, None))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            b.step_on_map(-5, 0)
            a.intercept(b.pid)
            clock.advance(1.2, late=True)
            check("a late event-loop callback retains the actual contact cell",
                  (calls(a), calls(b)), ([cell], [cell]))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            b.step_on_map(5, 0)
            a.intercept(b.pid)
            clock.advance(0.1)
            b.step_on_map(-5, 0)
            clock.advance(0.6)
            check("a target turning toward the hunter reschedules contact before the beat",
                  (len(calls(a)), len(calls(b))), (1, 1))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            b.step_on_map(-5, 0)
            a.intercept(b.pid)
            clock.advance(0.1)
            b.step_on_map(5, 0)
            clock.advance(0.9)
            check("a target turning away cancels the obsolete contact prediction",
                  (calls(a), calls(b)), ([], []))

        for speed, caught_by in ((1.4, 0), (2.8, 1)):
            clock = Clock()
            with patch.object(server.asyncio, "get_running_loop", return_value=clock):
                a, b = scene()
                a.speed = speed
                b.step_on_map(10, 0)
                a.intercept(b.pid)
                clock.advance(1)
                check("parallel movement: only a faster hunter closes the gap (%s)" % speed,
                      (len(calls(a)), len(calls(b))), (caught_by, caught_by))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            b.step_on_map(-0.14, 0)  # Stops before contact, so its old velocity must expire.
            a.intercept(b.pid)
            clock.advance(0.6)
            check("arrival invalidates extrapolation beyond the target's destination",
                  (calls(a), calls(b)), ([], []))
            clock.advance(0.8)
            check("a stopped target is caught on the remaining approach",
                  (len(calls(a)), len(calls(b))), (1, 1))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            a.intercept(b.pid)
            b.intercept(a.pid)
            clock.advance(2)
            check("mutual pursuit enters each player once without recursive re-aiming",
                  (len(calls(a)), len(calls(b))), (1, 1))

        clock = Clock()
        with patch.object(server.asyncio, "get_running_loop", return_value=clock):
            a, b = scene()
            a.CHASE_LIMIT = 0.2
            b.step_on_map(-5, 0)
            a.intercept(b.pid)
            clock.advance(0.9)
            check("the pursuit deadline cancels a later predicted contact",
                  (a.chase, calls(a), calls(b)), (None, [], []))

        for change in ("cancel", "leave", "close", "new target"):
            clock = Clock()
            with patch.object(server.asyncio, "get_running_loop", return_value=clock):
                a, b = scene()
                b.step_on_map(-5, 0)
                a.intercept(b.pid)
                clock.advance(0.1)
                if change == "cancel":
                    a.stop_chase()
                elif change == "leave":
                    b.on_map = False
                elif change == "close":
                    b.closed = True
                    server.ONLINE.remove(b)
                else:
                    c = Walker(3, 5980)
                    a.intercept(c.pid)
                clock.advance(0.9)
                check(change + ": an obsolete chase cannot pull players into a location",
                      (calls(a), calls(b)), ([], []))
except Exception:
    import traceback
    fails.append("interception scene crashed:\n" + traceback.format_exc())

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("intercept OK")
