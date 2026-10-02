"""Which functions of the server a suite runs: the map tools/suite.py picks
the suites of a change with (--affected).

On PYTHONPATH only while tools/suite.py records the map (--record-map), so
every Python process of a suite loads it: the suite itself and the servers
it starts. Each function of server/ that runs is written once, the moment
it first runs, as «path:qualname» to a file of its own process in
LAVA_IMPACT_OUT -- line by line, because a suite ends its server with
terminate(), which on Windows is TerminateProcess and runs no atexit.

sys.monitoring (3.12) reports the first start of each code object and is
then told to stop for it, so a function costs one event in the whole run;
an older Python falls back to sys.setprofile, slower but the same map.
"""
import os
import sys

_OUT = os.environ.get("LAVA_IMPACT_OUT")
_ROOT = os.environ.get("LAVA_IMPACT_ROOT")


def _start():
    root = os.path.normcase(os.path.abspath(os.path.join(_ROOT, "server")))
    suite = os.environ.get("LAVA_IMPACT_SUITE", "unknown")
    path = os.path.join(_OUT, "%s-%d.txt" % (suite, os.getpid()))
    out = open(path, "a", encoding="utf-8")
    seen = set()
    files = {}

    def rel(filename):
        if filename not in files:
            files[filename] = None
            # Frozen and generated code (<frozen ...>, <string>) and the
            # suites' own files are not the server.
            if not filename.startswith("<"):
                full = os.path.normcase(os.path.abspath(filename))
                base = os.path.basename(full)
                if full.startswith(root + os.sep) and not base.startswith("test"):
                    files[filename] = os.path.relpath(full, os.path.dirname(root)).replace(os.sep, "/")
        return files[filename]

    def note(code):
        where = rel(code.co_filename)
        if where is None:
            return
        key = "%s:%s" % (where, getattr(code, "co_qualname", code.co_name))
        if key not in seen:
            seen.add(key)
            out.write(key + "\n")
            out.flush()

    mon = getattr(sys, "monitoring", None)
    if mon is not None:
        tool = mon.PROFILER_ID
        try:
            mon.use_tool_id(tool, "lava-impact")
        except ValueError:
            return
        disable = mon.DISABLE

        def on_start(code, offset):
            note(code)
            return disable

        mon.register_callback(tool, mon.events.PY_START, on_start)
        mon.set_events(tool, mon.events.PY_START)
    else:
        def prof(frame, event, arg):
            if event == "call":
                note(frame.f_code)

        sys.setprofile(prof)


if _OUT and _ROOT:
    try:
        _start()
    except Exception as exc:          # a map is not worth a suite
        sys.stderr.write("impact: not recording (%s)\n" % exc)
