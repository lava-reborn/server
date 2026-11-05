"""What every suite checks with, and the report the runner reads.

check(label, got, want) is the one the suites always had: a line «  ok  label»
when got equals want, a failure kept in fails otherwise, printed by the suite
at its end. It also writes one JSON line per check to the file LAVA_TEST_REPORT
names (tools/suite.py sets it for each suite it runs), so that a run can be
read as a table rather than a scroll:

  suite      the script, test_bosses
  mechanic   what the suite is about: MECHANIC in the suite if it sets one,
             else the first line of its docstring
  section    the test inside it: the last «# --- name ---» header above the
             check in the suite's source, the way the suites are already cut
  check      the label
  ok         true or false; got and want on a failure
  seconds    the time since the check before it (since the suite began, for
             the first): what this check cost to reach

No LAVA_TEST_REPORT, no file: a suite run by hand prints what it always did.

connect(port, proc, log) is how a suite waits for the server it started: a
socket once the port answers, the server's own last lines if it died first.
"""
import json
import linecache
import os
import re
import socket
import sys
import time

fails = []

_HEADER = re.compile(r"^\s*# -{2,}\s*(.+?)\s*-*\s*$")
_started = time.time()
_last = [_started]
_out = [None]
_headers = {}


def _report():
    if _out[0] is None:
        path = os.environ.get("LAVA_TEST_REPORT")
        _out[0] = open(path, "a", encoding="utf-8") if path else False
    return _out[0]


def _main():
    return sys.modules.get("__main__")


def suite():
    path = getattr(_main(), "__file__", None) or sys.argv[0] or "?"
    return os.path.splitext(os.path.basename(path))[0]


def mechanic():
    main = _main()
    named = getattr(main, "MECHANIC", None)
    if named:
        return named
    doc = (getattr(main, "__doc__", None) or "").strip()
    return doc.splitlines()[0].strip() if doc else suite()


def _sections(path):
    """Line number -> the header above it, for one source file."""
    if path not in _headers:
        marks, current = [], None
        for n, line in enumerate(linecache.getlines(path), 1):
            m = _HEADER.match(line)
            if m:
                current = m.group(1)
            marks.append(current)
        _headers[path] = marks
    return _headers[path]


def section(depth=2):
    """The header above the line that called check, in the suite's own file:
    the first frame up the stack that is not this module's."""
    frame = sys._getframe(depth)
    here = os.path.abspath(__file__)
    while frame is not None and os.path.abspath(frame.f_code.co_filename) == here:
        frame = frame.f_back
    if frame is None:
        return None
    marks = _sections(frame.f_code.co_filename)
    n = frame.f_lineno
    return marks[n - 1] if 0 < n <= len(marks) else None


def _short(v, limit=2000):
    s = repr(v)
    return s if len(s) <= limit else s[:limit] + " ..."


def check(label, got, want):
    ok = got == want
    if ok:
        print("  ok  %s" % label)
    else:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    out = _report()
    if out:
        now = time.time()
        row = dict(suite=suite(), mechanic=mechanic(), section=section(), check=label,
                   ok=ok, seconds=round(now - _last[0], 3))
        if not ok:
            row.update(got=_short(got), want=_short(want))
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()
        _last[0] = now
    return ok


def run_cases(*classes):
    """Run explicitly named regression cases through the common check report.

    TestCase supplies assertions, async loop isolation and fixture cleanup;
    testkit remains the reporting/exit interface used by the suite runner.
    Imported fixture classes are not collected a second time.
    """
    import io
    import unittest

    reported = set()

    class Result(unittest.TextTestResult):
        def stopTest(self, test):
            errors = [detail for case, detail in self.failures + self.errors
                      if case == test or getattr(case, "test_case", None) == test]
            errors += ["skipped: " + reason for case, reason in self.skipped if case == test]
            errors += [detail for case, detail in self.expectedFailures if case == test]
            if test in self.unexpectedSuccesses:
                errors.append("unexpected success")
            label = test.shortDescription() or test._testMethodName.removeprefix("test_").replace("_", " ")
            check(label, "\n".join(errors) if errors else True, True)
            reported.add(test)
            super().stopTest(test)

    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in classes)
    if not suite.countTestCases():
        check("the regression suite contains test cases", False, True)
    result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=Result).run(suite)
    for test, detail in result.errors + result.failures:
        if test not in reported and getattr(test, "test_case", None) not in reported:
            check("fixture: " + str(test), detail, True)
    if fails:
        print("\n".join(fails))
    raise SystemExit(1 if fails or not result.wasSuccessful() else 0)


# How long a suite waits for its server to listen. Alone one starts in about
# two seconds; CI on GitHub's runners started a dozen at once on two cores,
# and a window of ten made a quarter of the suites fail in the crowd and pass
# alone, the reruns then outlasting the job (the self-hosted runner starts
# eight at once on four). A server that died says so at once below, so a
# long window costs nothing but on a server that hangs.
START_WAIT = float(os.environ.get("LAVA_START_WAIT") or 120)


def _tail(log, size=2000):
    if log is None:
        return ""
    if isinstance(log, str):
        try:
            with open(log, encoding="utf-8", errors="replace") as f:
                return f.read()[-size:]
        except OSError:
            return ""
    return "".join(log)[-size:]


def connect(port, proc=None, log=None, timeout=None, host="127.0.0.1"):
    """A socket to the server on port, as soon as it listens. proc is the
    server's Popen: if it exits first, the suite stops with its exit code and
    the tail of log (the drained lines, or the path of its log file) instead
    of waiting out the window. timeout defaults to START_WAIT."""
    window = START_WAIT if timeout is None else timeout
    end = time.time() + window
    while True:
        if proc is not None and proc.poll() is not None:
            raise SystemExit("server exited (%s) before it listened:\n%s"
                             % (proc.returncode, _tail(log)))
        try:
            return socket.create_connection((host, port), 0.5)
        except OSError:
            if time.time() > end:
                raise SystemExit("server did not start in %ds:\n%s"
                                 % (window, _tail(log)))
            time.sleep(0.1)


def scene_client(cls):
    """Record real placement frames for explicit socket-fixture navigation.

    No commands are rewritten: tests still send and assert the actual wire.
    """
    from functools import wraps
    from protocol import decode
    def observe(client, frames):
        for raw in frames:
            cmd, params = decode(raw) if isinstance(raw, str) else raw
            if not params.get('id') and params.get('recovery_ms', 0) > 0:
                client.scene_recovery_until = time.monotonic() + params['recovery_ms'] / 1000
            if cmd == 'lcall':
                client.scene_id = params['id']
                client.scene_cells = {}
            elif cmd == 'lenter':
                client.scene_pos = params['pos']
            elif cmd == 'lch':
                cells = getattr(client, 'scene_cells', {})
                if 'newUser' in params:
                    cells[params['newUser']] = params['pos']
                for key in ('lostUser', 'dead'):
                    cells.pop(params.get(key), None)
                client.scene_cells = cells
            elif cmd in ('userMove', 'actionCancel', 'breakMv'):
                cell = params.get('pos')
                if cmd == 'userMove':
                    if 'path' not in params:  # Global-map velocity packet, not a room route.
                        continue
                    cell = params['path'][-1]
                if cell is not None:
                    if not params.get('id'):
                        client.scene_pos = cell
                    else:
                        getattr(client, 'scene_cells', {})[params['id']] = cell
    for name in ('frames', 'until'):
        original = getattr(cls, name, None)
        if original is None:
            continue
        def wrap(original):
            @wraps(original)
            def receive(self, *args, **kwargs):
                frames = original(self, *args, **kwargs)
                observe(self, frames)
                return frames
            return receive
        setattr(cls, name, wrap(original))
    return cls


def walk_to(client, target, blocked=()):
    """Send a real path during fixture setup, then allow it to complete.

    Older socket fixtures used one-cell teleports, or jumps across the room.
    A stationary one-cell request is now only a stop. Approach occupied NPC
    cells instead, just as the real client's contact pathfinder does. Leave
    the reply on the socket so the calling test can check it normally.
    """
    import mobs
    import progression
    import world
    loc = world.location(client.scene_id)
    start = client.scene_pos
    occupied = set(getattr(client, 'scene_cells', {}).values())
    blocked = set(blocked) | occupied
    blocked.discard(start)
    goal = (lambda c: progression.within_reach(c, target, loc.width, loc.height)
            if target in occupied else c == target)
    path = mobs.find_path(loc, start, goal, blocked, limit=loc.width * loc.height, toward=target)
    assert path and goal(path[-1]), (loc.id, start, target, 'no fixture route')
    client.fixture_path = path
    client.send('moveTo;path=|%s|;' % '|'.join(map(str, path)))
    time.sleep((len(path) - 1) * mobs.HEX_MS / 1000 + 0.05)
    return path[-1]


def wait_recovery(client):
    """A protocol fixture waits for the same committed release as Flash.

    Keep incoming frames in the caller's transcript; never resend or alter
    a command, and do not consume this delay for deliberately refused actions.
    """
    out = []
    while True:
        left = getattr(client, 'scene_recovery_until', 0) - time.monotonic()
        if left <= 0:
            return out
        out += client.frames(min(left + 0.01, 0.2))


def walk_frames(client, target, blocked=(), attempts=4, exact=False):
    """Fixture navigation with authoritative stop feedback, never teleport.

    A mob can enter a route after it was accepted. Read that stop before
    finding the next leg, and keep every reply for the caller's assertions.
    """
    import progression
    import world
    frames = []
    for _ in range(attempts):
        frames += wait_recovery(client)
        walk_to(client, target, blocked)
        frames += client.frames(0.25)
        if client.scene_pos == target:
            return frames
        occupied = set(getattr(client, 'scene_cells', {}).values())
        loc = world.location(client.scene_id)
        if not exact and target in occupied and progression.within_reach(
                client.scene_pos, target, loc.width, loc.height):
            return frames
    raise AssertionError((client.scene_id, client.scene_pos, target, 'fixture walk stopped'))


def scene_positions(frames):
    """Observed current cells, including the final stop before death."""
    cells = {}
    for cmd, params in frames:
        if cmd == 'lch' and 'newUser' in params:
            cells[params['newUser']] = params['pos']
        elif cmd == 'userMove' and params.get('path'):
            cells[params['id']] = params['path'][-1]
        elif cmd in ('actionCancel', 'breakMv') and 'pos' in params:
            cells[params.get('id', 0)] = params['pos']
    return cells


def clear_approach(client, goals, fire, enemies, reach):
    """Walk a fixture through guards using real shots, never through occupied cells.

    Old story fixtures could teleport past a guard in a one-cell corridor.
    Keep the new occupancy rules intact: clear visible hostiles before each
    step, and bound the approach so a bad fixture fails with its actual cell.
    ``fire`` returns the received death frames, or None on failure.
    """
    import mobs
    import world
    loc = world.location(client.scene_id)
    goal = goals if callable(goals) else set(goals).__contains__
    enemies = set(enemies)
    frames = []
    for _ in range(min(256, loc.width * loc.height)):
        cells = client.scene_cells
        visible = sorted((mobs.hex_distance(client.scene_pos, cell, loc.width), eid)
                         for eid, cell in cells.items() if eid in enemies
                         and mobs.hex_distance(client.scene_pos, cell, loc.width) <= reach
                         and mobs.line_of_fire(loc, client.scene_pos, cell) is None)
        if visible:
            _distance, eid = visible[0]
            got = fire(eid)
            assert got is not None, (loc.id, client.scene_pos, eid, 'guard did not fall')
            frames += got
            enemies.discard(eid)
            continue
        if goal(client.scene_pos):
            return frames
        blocked = set(cells.values())
        path = mobs.find_path(loc, client.scene_pos, goal,
                              blocked, limit=loc.width * loc.height)
        if not path:
            # Plan up to a guard, then shoot it when the corridor opens sight.
            blocked = {cell for eid, cell in cells.items() if eid not in enemies}
            path = mobs.find_path(loc, client.scene_pos, goal,
                                  blocked, limit=loc.width * loc.height)
        assert path and len(path) > 1 and path[1] not in cells.values(), (
            loc.id, client.scene_pos, 'no clear fixture approach')
        # Send one leg to the next firing lane, not one request per hex.
        # This keeps socket scenarios quick while still clearing a corridor
        # before crossing the guard occupying it.
        leg = path[-1]
        for cell in path[1:]:
            if any(mobs.hex_distance(cell, other, loc.width) <= reach
                   and mobs.line_of_fire(loc, cell, other) is None
                   for eid, other in cells.items() if eid in enemies):
                leg = cell
                break
        frames += walk_frames(client, leg, exact=True)
    raise AssertionError((loc.id, client.scene_pos, 'fixture approach exhausted'))
