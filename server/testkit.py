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
"""
import json
import linecache
import os
import re
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
