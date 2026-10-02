"""Run the suites, N at a time, and read the run as a table.

    python tools/suite.py                      every suite
    python tools/suite.py --only test_combat,test_death
    python tools/suite.py --affected           only what the change touches
    python tools/suite.py --affected --list    say which, run nothing
    python tools/suite.py --record-map         every suite, and remember which
                                               functions each one runs

The output directory (--out, default %TEMP%/lava_suite) gets, per suite,
<name>.out and <name>.err (what it printed) and <name>.jsonl (one line per
check, server/testkit.py); then summary.txt (exit code, seconds, name; a zero
in front is a green suite) and report.html: mechanic, test, check, status,
time (tools/suite_report.py). tools/run_suite.ps1 runs the suites through
this. tools/run_suite.sh, the runner CI uses, keeps its own loop (known
failures, reruns, the job summary) and asks this only which suites --only
and --affected pick (--list) and to write the map of its --record-map
(--save-map); it writes the same .jsonl and report.html.

As in run_suite.sh: longest first by the summary.txt a previous run left in
--out (a suite it does not know goes first), and each suite on a database
and a TMPDIR of its own, empty at its start. Under GitHub Actions only the
whole set runs: --only and --affected are refused there (exit 2), so that no
push is ever tested, and deployed, on part of it.

--affected compares the working tree with --base (origin/main) and runs:

  * a suite that changed, itself;
  * for a changed function of server/, every suite that ran it (the map);
  * for a changed line outside any function -- a constant, a table -- every
    suite that ran a function naming what the line assigns;
  * for a changed file of data/, every suite that ran a function whose
    source names the file, and the suites of data/ that name it;
  * everything, for a change to the runner, testkit, or a file the map has
    never seen run, and when there is no map at all.

The map is tools/impact_map.json, written by --record-map (a full run, with
tools/impact/sitecustomize.py on the path of every process of it) and kept
out of git (tools/* is ignored but for *.py). It goes stale slowly: a
function is kept by name, so moving code does not lose it; a new function
nobody has run yet is found through the names its callers use.
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import suite_report  # noqa: E402

MAP = os.path.join(HERE, "impact_map.json")
LEFT_OUT = {"test_storage_pg"}            # wants Postgres
FIRST = "test_halfa_training"             # the longest: started first
EVERYTHING = ("server/testkit.py", "tools/suite.py", "tools/run_suite.ps1",
              "tools/run_suite.sh", "tools/impact/sitecustomize.py", "tools/suite_report.py",
              "tools/known_failures.txt")


def suites():
    """Every suite, longest first: the order a pool of N finishes soonest in."""
    found = []
    for sub in ("server", "data", "tools"):
        d = os.path.join(ROOT, sub)
        for f in os.listdir(d):
            if f.startswith("test_") and f.endswith(".py") and f[:-3] not in LEFT_OUT:
                found.append(os.path.join(d, f))
    server = sorted((p for p in found if os.sep + "server" + os.sep in p),
                    key=lambda p: (os.path.basename(p)[:-3] != FIRST, -os.path.getsize(p)))
    rest = sorted(p for p in found if p not in server)
    return server + rest


def name_of(path):
    return os.path.splitext(os.path.basename(path))[0]


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


# --- what a change touches ------------------------------------------------------------
def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def changed_lines(base):
    """{path: set of changed line numbers in the working tree, or None for a
    file that is new or gone}: the commits since base and what is not
    committed yet, together."""
    out = {}
    merge_base = git("merge-base", base, "HEAD").strip() or base
    diff = git("diff", "-U0", "--no-color", merge_base, "--")
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            p = line[4:].strip()
            path = None if p == "/dev/null" else p[2:] if p.startswith("b/") else p
            if path is not None:
                out.setdefault(path, set())
        elif line.startswith("--- ") and path is None:
            continue
        elif line.startswith("@@") and path is not None:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            start, n = int(m.group(1)), int(m.group(2) or 1)
            # A pure deletion (n == 0) still touches the line it was cut beside.
            out[path].update(range(start, start + max(n, 1)))
    for p in git("ls-files", "--others", "--exclude-standard").splitlines():
        out[p] = None
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            p = line[6:].strip()
            if p not in out:
                out[p] = None                     # deleted
    return out


class Source(object):
    """One file of server/ read with ast: its functions by qualname with
    their lines, and the names each function's body uses."""

    def __init__(self, path):
        self.functions = {}       # qualname -> (first, last)
        self.names = {}           # qualname -> set of names used
        try:
            tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
        except (OSError, SyntaxError, ValueError):
            return
        self._walk(tree, "")

    def _walk(self, node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = prefix + child.name
                if not isinstance(child, ast.ClassDef):
                    first = min([d.lineno for d in child.decorator_list] + [child.lineno])
                    self.functions[q] = (first, child.end_lineno)
                    used = set()
                    for n in ast.walk(child):
                        if isinstance(n, ast.Name):
                            used.add(n.id)
                        elif isinstance(n, ast.Attribute):
                            used.add(n.attr)
                        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                            used.add(n.value)
                    self.names[q] = used
                    self._walk(child, q + ".<locals>.")
                else:
                    self._walk(child, q + ".")

    def owner(self, line):
        """The innermost function a line is in, or None for module level."""
        best = None
        for q, (a, b) in self.functions.items():
            if a <= line <= b and (best is None or a >= self.functions[best][0]):
                best = q
        return best


def assigned_names(path, lines):
    """The names module-level statements on these lines bind."""
    try:
        tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    except (OSError, SyntaxError, ValueError):
        return set()
    names = set()
    for stmt in tree.body:
        if not any(stmt.lineno <= n <= stmt.end_lineno for n in lines):
            continue
        targets = []
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(stmt.name)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in stmt.names)
        for t in targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    names.add(n.id)
    return names


def affected(base, impact):
    """(suite names, why): what the change since base asks to run."""
    every = {name_of(p): p for p in suites()}
    if impact is None:
        return sorted(every), {"*": "no map (python tools/suite.py --record-map)"}
    ran = {s: set(keys) for s, keys in impact["suites"].items()}
    by_key = {}
    for s, keys in ran.items():
        for k in keys:
            by_key.setdefault(k, set()).add(s)
    sources = {}

    def src(path):
        if path not in sources:
            sources[path] = Source(path)
        return sources[path]

    # A function nearly every suite runs -- read at import, the way a
    # setting is (bosses.stay_from), or the session's own dispatch -- says
    # nothing about which mechanic a name belongs to.
    common = len(ran) * 3 // 4

    def users_of(names, path=None):
        """Suites that ran a function of server/ whose body uses any of names,
        leaving out the functions nearly every suite runs; if that leaves
        nobody, the suites whose own source names the module (for a change
        in a module of server/) or one of the names."""
        out = set()
        for key, who in by_key.items():
            p, q = key.split(":", 1)
            if len(who) < common and src(p).names.get(q, set()) & names:
                out |= who
        if out:
            return out
        words = set(names)
        stem = os.path.splitext(os.path.basename(path))[0] if path else None
        for n, p in every.items():
            text = open(p, encoding="utf-8").read()
            if (stem in text) if stem else any(w in text for w in words):
                out.add(n)
        return out

    picked, why = set(), {}

    def take(names, reason):
        for n in names:
            if n in every and n not in picked:
                picked.add(n)
                why[n] = reason

    for path, lines in sorted(changed_lines(base).items()):
        if path in EVERYTHING:
            return sorted(every), {"*": "the runner or testkit changed: %s" % path}
        base_name = os.path.basename(path)
        if base_name.startswith("test_") and base_name.endswith(".py"):
            take([name_of(path)], "the suite itself changed")
            continue
        if path.startswith("server/") and path.endswith(".py"):
            s = src(path)
            if lines is None:
                hit = set()
                for k, who in by_key.items():
                    if k.startswith(path + ":"):
                        hit |= who
                if not hit and not s.functions:
                    continue                        # gone, and nobody ran it
                take(hit or every, "%s is new or gone" % path)
                continue
            text = open(os.path.join(ROOT, path), encoding="utf-8").read().splitlines()
            # A comment or a blank line changes nothing a suite could see.
            lines = {n for n in lines if n <= len(text) and text[n - 1].strip()
                     and not text[n - 1].strip().startswith("#")}
            module_lines = set()
            for n in lines:
                q = s.owner(n)
                if q is None:
                    module_lines.add(n)
                    continue
                key = "%s:%s" % (path, q)
                if key in by_key:
                    take(by_key[key], "ran %s" % key)
                else:
                    # Nobody ran it yet (new, or renamed): whoever runs a
                    # function that calls it by name.
                    take(users_of({q.split(".")[-1]}), "calls %s (not in the map)" % key)
            if module_lines:
                names = assigned_names(path, module_lines)
                if names:
                    take(users_of(names, path), "uses %s of %s" % (", ".join(sorted(names)), path))
            continue
        if path.startswith("data/"):
            stem = os.path.splitext(base_name)[0]
            take(users_of({base_name, stem}), "reads %s" % path)
            for n, p in every.items():
                if p.startswith(os.path.join(ROOT, "data")) and base_name in open(p, encoding="utf-8").read():
                    take([n], "names %s" % path)
            continue
        # Docs, the launcher, the client patcher: nothing a suite runs.
    return sorted(picked), why


def load_map():
    try:
        return json.load(open(MAP, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_map(record_dir, names):
    impact = load_map() or {"suites": {}}
    for n in names:
        keys = set()
        for f in os.listdir(record_dir):
            if f.startswith(n + "-") and f[len(n) + 1:-4].isdigit():
                keys.update(l.strip() for l in open(os.path.join(record_dir, f), encoding="utf-8") if l.strip())
        impact["suites"][n] = sorted(keys)
    impact["commit"] = git("rev-parse", "HEAD").strip()
    impact["recorded"] = time.strftime("%Y-%m-%d %H:%M")
    with open(MAP, "w", encoding="utf-8") as fh:
        json.dump(impact, fh, ensure_ascii=False, indent=0)


# --- the run -------------------------------------------------------------------------
def by_last_run(paths, out):
    """Longest first by the durations of the run before in out, the way
    tools/run_suite.sh orders them: its summary.txt becomes summary.prev.txt,
    a suite it does not know goes first, the rest keep the order given."""
    summary = os.path.join(out, "summary.txt")
    prev = os.path.join(out, "summary.prev.txt")
    if os.path.exists(summary) and os.path.getsize(summary) > 0:
        os.replace(summary, prev)
    took = {n: s["seconds"] for n, s in suite_report.read_summary(out, "summary.prev.txt").items()}
    if not took:
        return list(paths)
    return sorted(paths, key=lambda p: -took.get(name_of(p), 99999))


def run(paths, out, jobs, res, stagger, record_dir=None, timeout=1500):
    os.makedirs(out, exist_ok=True)
    summary = os.path.join(out, "summary.txt")
    open(summary, "w", encoding="utf-8").close()
    try:
        # A rerun record tools/run_suite.sh left here is not this run's.
        os.remove(os.path.join(out, "summary.rerun.txt"))
    except OSError:
        pass
    orig = os.environ.get("LAVA_ORIG_TEXTS") or os.path.join(res, "xml", "texts.xml")
    # A database file and a TMPDIR per suite, empty at its start, under a
    # folder named after the output directory: two runs side by side do not
    # share a file, and no suite starts on what an earlier run left.
    runtmp = os.path.join(tempfile.gettempdir(), "lava_suite_tmp.%d"
                          % zlib.crc32(os.path.abspath(out).encode("utf-8")))
    queue, running = list(paths), {}
    last_start = 0.0
    while queue or running:
        while queue and len(running) < jobs:
            # A server reads the world for some five seconds on Windows, and
            # eight at once take longer than the ten the suites wait for the
            # port: one launch at a time, a few seconds apart.
            wait = last_start + stagger - time.time()
            if running and wait > 0:
                break
            path = queue.pop(0)
            n = name_of(path)
            for ext in (".jsonl",):
                try:
                    os.remove(os.path.join(out, n + ext))
                except OSError:
                    pass
            own = os.path.join(runtmp, n)
            shutil.rmtree(own, ignore_errors=True)
            os.makedirs(os.path.join(own, "tmp"), exist_ok=True)
            env = dict(os.environ, LAVA_RES=res, LAVA_ORIG_TEXTS=orig, PYTHONUTF8="1",
                       PYTHONIOENCODING="utf-8",
                       LAVA_DB=os.path.join(own, "lava.db"),
                       TMPDIR=os.path.join(own, "tmp"),
                       LAVA_TEST_REPORT=os.path.join(out, n + ".jsonl"))
            if record_dir:
                env.update(LAVA_IMPACT_OUT=record_dir, LAVA_IMPACT_ROOT=ROOT, LAVA_IMPACT_SUITE=n,
                           PYTHONPATH=os.pathsep.join([os.path.join(HERE, "impact")]
                                                      + [p for p in [os.environ.get("PYTHONPATH")] if p]))
            fo = open(os.path.join(out, n + ".out"), "w", encoding="utf-8")
            fe = open(os.path.join(out, n + ".err"), "w", encoding="utf-8")
            p = subprocess.Popen([sys.executable, os.path.basename(path)], cwd=os.path.dirname(path),
                                 env=env, stdout=fo, stderr=fe)
            running[p.pid] = (p, n, time.time(), fo, fe)
            last_start = time.time()
        time.sleep(0.5)
        for pid in list(running):
            p, n, t0, fo, fe = running[pid]
            code = p.poll()
            if code is None and time.time() - t0 > timeout:
                p.kill()
                code = p.wait()
            if code is not None:
                fo.close()
                fe.close()
                with open(summary, "a", encoding="utf-8") as fh:
                    fh.write("%d %ds %s\n" % (code, int(round(time.time() - t0)), n))
                print("%s %4ds %s" % ("ok " if code == 0 else "BAD", time.time() - t0, n), flush=True)
                del running[pid]
    with open(summary, "a", encoding="utf-8") as fh:
        fh.write("DONE\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "lava_suite"))
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--res", default=os.environ.get("LAVA_RES")
                    or os.path.join(os.path.dirname(ROOT), "lava-online", "res"))
    ap.add_argument("--only", default="", help="suite names, comma separated")
    ap.add_argument("--affected", action="store_true", help="only the suites the change touches")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--list", action="store_true", help="say which suites, run nothing")
    ap.add_argument("--record-map", action="store_true")
    ap.add_argument("--save-map", metavar="DIR",
                    help="write the map from the files a recorded run left in DIR"
                         " (tools/run_suite.sh --record-map), for --only's suites or all")
    ap.add_argument("--stagger", type=float, default=4.0 if os.name == "nt" else 1.0)
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    every = suites()
    chosen = every
    if a.only:
        wanted = {w.strip() for w in a.only.replace(";", ",").split(",") if w.strip()}
        chosen = [p for p in every if name_of(p) in wanted]
        unknown = wanted - {name_of(p) for p in every}
        if unknown:
            print("no such suite: %s" % ", ".join(sorted(unknown)))
            return 2
    if a.affected:
        names, why = affected(a.base, load_map())
        chosen = [p for p in chosen if name_of(p) in set(names)]
        for n in sorted(why):
            print("  %-26s %s" % (n, why[n]))
        print("%d of %d suites" % (len(chosen), len(every)))
    if a.list:
        for p in chosen:
            print(rel(p))
        return 0
    if a.save_map:
        save_map(a.save_map, [name_of(p) for p in chosen])
        print("map: %s" % MAP)
        return 0
    if os.environ.get("GITHUB_ACTIONS") and (a.only or a.affected):
        print("CI runs every suite; --only and --affected are for a run by hand")
        return 2
    if not chosen:
        print("nothing to run")
        return 0
    # objects.xml, not main.swf, as tools/run_suite.sh: CI carries the slice
    # of res/ the server reads, and no main.swf.
    if not os.path.exists(os.path.join(a.res, "database", "objects.xml")):
        print("no client at %s (database/objects.xml missing); pass --res or set LAVA_RES" % a.res)
        return 2
    chosen = by_last_run(chosen, a.out)
    record_dir = None
    if a.record_map:
        record_dir = tempfile.mkdtemp(prefix="lava_impact_")
    t0 = time.time()
    run(chosen, a.out, a.jobs, a.res, a.stagger, record_dir)
    if record_dir:
        save_map(record_dir, [name_of(p) for p in chosen])
        shutil.rmtree(record_dir, ignore_errors=True)
        print("map: %s" % MAP)
    print("wall time: %s" % suite_report.fmt_secs(time.time() - t0))
    return suite_report.main(a.out)


if __name__ == "__main__":
    sys.exit(main())
