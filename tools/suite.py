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

  * a suite that changed, itself, and a suite the map does not know yet;
  * for a changed function of server/, every suite that ran it (the map) --
    and for a line taken away, the function of the base that held it, so a
    deleted line or a deleted function counts as much as a written one;
  * for a changed assignment outside any function -- a constant, a table --
    every suite that ran a function naming what it assigns; for any other
    statement there (a call such as ALL.update(...), an if, a try, a with:
    what it does is known only by running the module), every suite that ran
    anything of the module;
  * for a tool, tools/test_<it>.py and every suite that names it; for a
    file of data/, every suite that ran a function whose source names the
    file, and the suites that name it; for any other file, the suites that
    name it -- and when nobody does, everything, unless it is the docs
    (*.md, recon/, .github/);
  * everything, for a change to the runner, testkit or the known list,
    when git cannot say what changed, and when there is no map at all.

Renames are read as a file gone and a file new (git diff --no-renames).

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
class GitFailed(Exception):
    """git could not answer: no such base, or not a checkout git can read
    from here (WSL git in a worktree whose .git names a Windows path)."""


def git(*args):
    """git's output, or GitFailed: an answer git did not give is never taken
    for «nothing changed»."""
    try:
        p = subprocess.run(["git", "-c", "core.quotepath=off"] + list(args), cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        raise GitFailed("git %s: %s" % (args[0], exc))
    if p.returncode != 0:
        raise GitFailed("git %s: %s" % (" ".join(args), (p.stderr or p.stdout).strip()[:300]))
    return p.stdout


# A whole file: new, gone, binary, or a change with no lines to read.
WHOLE = "whole"


def parse_diff(diff):
    """{path: (new, old)} of `git diff -U0 --no-renames`: the lines of the
    working tree a hunk wrote, and the lines of the base it took away, each
    a set -- or WHOLE for a file that is new or gone (a rename is both: the
    old name gone, the new one new), and for one whose change has no lines
    (binary, a mode)."""
    out = {}
    cur = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            cur = None
            if m:
                cur = m.group(2)
                out[cur] = (WHOLE, WHOLE)
        elif cur is None:
            continue
        elif line.startswith("new file mode") or line.startswith("deleted file mode"):
            continue
        elif line.startswith("--- "):
            gone_before = line[4:].strip() == "/dev/null"
            out[cur] = (out[cur][0], WHOLE if gone_before else set())
        elif line.startswith("+++ "):
            gone_now = line[4:].strip() == "/dev/null"
            out[cur] = (WHOLE if gone_now else set(), out[cur][1])
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                continue
            a, k = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            b, n = int(m.group(3)), int(m.group(4) if m.group(4) is not None else 1)
            new, old = out[cur]
            if new is not WHOLE:
                new.update(range(b, b + n))
            if old is not WHOLE:
                old.update(range(a, a + k))
    return out


def changed_lines(base):
    """(merge base, {path: (new, old)}): the commits since base and what is
    not committed yet, together (parse_diff), and the files git does not
    know yet as new. GitFailed if git cannot say."""
    merge_base = git("merge-base", base, "HEAD").strip()
    if not merge_base:
        raise GitFailed("git merge-base %s HEAD: no answer" % base)
    out = parse_diff(git("diff", "-U0", "--no-color", "--no-renames", "--no-ext-diff",
                         merge_base, "--"))
    for p in git("ls-files", "--others", "--exclude-standard").splitlines():
        if p.strip():
            out[p.strip()] = (WHOLE, WHOLE)
    return merge_base, out


class Source(object):
    """One file of server/ read with ast -- the working tree's, or the text
    given (the base's): its functions by qualname with their lines, the
    names each function's body uses, and its module-level statements."""

    def __init__(self, path, text=None):
        self.functions = {}       # qualname -> (first, last)
        self.names = {}           # qualname -> set of names used
        self.lines = []           # the text, line by line
        self.body = []            # module-level statements
        try:
            if text is None:
                text = open(os.path.join(ROOT, path), encoding="utf-8").read()
            self.lines = text.splitlines()
            tree = ast.parse(text)
        except (OSError, SyntaxError, ValueError):
            return
        self.body = tree.body
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

    def code(self, lines):
        """The lines that are code: a comment or a blank line changes
        nothing a suite could see."""
        return {n for n in lines if 1 <= n <= len(self.lines) and self.lines[n - 1].strip()
                and not self.lines[n - 1].strip().startswith("#")}

    def module_names(self, lines):
        """(names, whole): the names the module-level statements on these
        lines bind -- an assignment's targets, a def's or a class's name, an
        import's -- and whether any of them is something else, a call or a
        block (ALL.update(...), an if, a try, a with): what that does is
        known only by running the module, so the whole of it is touched."""
        names, whole = set(), False
        for stmt in self.body:
            if not any(stmt.lineno <= n <= stmt.end_lineno for n in lines):
                continue
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            names.add(n.id)
                        elif isinstance(n, ast.Attribute):
                            names.add(n.attr)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(stmt.name)
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in stmt.names)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                continue                          # a docstring
            else:
                whole = True
        return names, whole


# Paths a suite never reads unless one names them: the docs and the
# decompiled client's notes. Anything else nobody names runs every suite.
INERT_PREFIXES = ("recon/", ".github/")
INERT_SUFFIXES = (".md",)


def affected(base, impact):
    """(suite names, why): what the change since base asks to run.

    Whatever cannot be told runs: no map, git failing, a file nobody is
    known to read. A run of too much costs minutes; one of too little is a
    change that looked tested and was not."""
    every = {name_of(p): p for p in suites()}
    if impact is None:
        return sorted(every), {"*": "no map (python tools/suite.py --record-map)"}
    try:
        merge_base, changes = changed_lines(base)
    except GitFailed as exc:
        return sorted(every), {"*": "git cannot say what changed, so everything: %s" % exc}
    ran = {s: set(keys) for s, keys in impact["suites"].items()}
    by_key = {}
    for s, keys in ran.items():
        for k in keys:
            by_key.setdefault(k, set()).add(s)
    texts = {}

    def text_of(n):
        if n not in texts:
            texts[n] = open(every[n], encoding="utf-8").read()
        return texts[n]

    sources = {}

    def src(path):
        if path not in sources:
            sources[path] = Source(path)
        return sources[path]

    def old_src(path):
        key = (merge_base, path)
        if key not in sources:
            try:
                sources[key] = Source(path, git("show", "%s:%s" % (merge_base, path)))
            except GitFailed:
                sources[key] = None
        return sources[key]

    # A function nearly every suite runs -- read at import, the way a
    # setting is (bosses.stay_from), or the session's own dispatch -- says
    # nothing about which mechanic a name belongs to.
    common = len(ran) * 3 // 4

    def naming(words):
        """Suites whose own source names any of these words."""
        return {n for n in every if any(w in text_of(n) for w in words)}

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
        stem = os.path.splitext(os.path.basename(path))[0] if path else None
        return naming([stem] if stem else names)

    def whole_module(path):
        """Every suite that ran any function of the file, else every one
        that names it, else all of them."""
        hit = set()
        for k, who in by_key.items():
            if k.startswith(path + ":"):
                hit |= who
        return hit or naming([os.path.splitext(os.path.basename(path))[0]]) or set(every)

    picked, why = set(), {}

    def take(names, reason):
        for n in names:
            if n in every and n not in picked:
                picked.add(n)
                why[n] = reason

    # A suite the map has never seen run (added since it was recorded) is
    # never anyone's user: it runs, whatever changed.
    take(sorted(set(every) - set(ran)), "not in the map yet")

    def server_lines(path, source, lines, side):
        module = set()
        for n in source.code(lines):
            q = source.owner(n)
            if q is None:
                module.add(n)
                continue
            key = "%s:%s" % (path, q)
            if key in by_key:
                take(by_key[key], "ran %s%s" % (key, side))
            else:
                # Nobody ran it yet (new, or renamed): whoever runs a
                # function that calls it by name.
                take(users_of({q.split(".")[-1]}) or whole_module(path),
                     "calls %s%s (not in the map)" % (key, side))
        if module:
            names, whole = source.module_names(module)
            if whole:
                take(whole_module(path), "%s runs at import%s" % (path, side))
            elif names:
                take(users_of(names, path) or whole_module(path),
                     "uses %s of %s%s" % (", ".join(sorted(names)), path, side))

    for path, (new, old) in sorted(changes.items()):
        if path in EVERYTHING:
            return sorted(every), {"*": "the runner or testkit changed: %s" % path}
        base_name = os.path.basename(path)
        stem = os.path.splitext(base_name)[0]
        if base_name.startswith("test_") and base_name.endswith(".py"):
            take([name_of(path)], "the suite itself changed")
            continue
        if path.startswith("server/") and path.endswith(".py"):
            if new is WHOLE or old is WHOLE:
                take(whole_module(path), "%s is new or gone" % path)
                continue
            server_lines(path, src(path), new, "")
            # What was taken away, by the base's own lines: a deleted line
            # (or a whole function) belongs to what held it there, not to
            # the line the cut now stands beside.
            before = old_src(path)
            if before is None:
                take(whole_module(path), "%s: the base cannot be read" % path)
            else:
                server_lines(path, before, old, " (taken away)")
            continue
        if path.startswith("tools/") and path.endswith(".py"):
            # A tool runs in its own suite (tools/test_X.py), and in any
            # suite that names it (test_clan_admin_wire runs admin_account).
            hit = {n for n in ("test_" + stem,) if n in every} | naming([stem])
            take(hit or set(every), "runs %s" % path)
            continue
        if path.startswith("data/"):
            hit = users_of({base_name, stem}) | naming([base_name])
            take(hit or set(every), "reads %s" % path)
            continue
        hit = naming([base_name, path])
        if hit:
            take(hit, "names %s" % path)
        elif not (path.startswith(INERT_PREFIXES) or path.endswith(INERT_SUFFIXES)):
            # Nobody names it, and it is not the docs: whether a suite reads
            # it cannot be told from here.
            take(set(every), "%s: no suite names it, so everything" % path)
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


# Each suite in a process group of its own, so that a timeout takes the
# servers it started along with it, as GNU timeout does for run_suite.sh: a
# server left behind keeps its port and a CPU for the rest of the run.
OWN_GROUP = (dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt"
             else dict(start_new_session=True))


def kill_group(p):
    """The suite and everything it started."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           capture_output=True)
        else:
            import signal
            os.killpg(p.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        p.kill()
    except OSError:
        pass


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
                                 env=env, stdout=fo, stderr=fe, **OWN_GROUP)
            running[p.pid] = (p, n, time.time(), fo, fe)
            last_start = time.time()
        time.sleep(0.5)
        for pid in list(running):
            p, n, t0, fo, fe = running[pid]
            code = p.poll()
            if code is None and time.time() - t0 > timeout:
                kill_group(p)
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
