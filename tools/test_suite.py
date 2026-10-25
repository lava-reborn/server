"""tools/suite.py --affected picks what a change touches, and runs it all when
it cannot tell.

On a throwaway repository with a module, four suites, a table, a tool and a
map of which suite ran which function, each change is made in the working
tree and handed to suite.affected, as `--affected` would:

  * a line written in a function: the suites that ran it;
  * a line taken away right after a comment, and a whole function taken
    away: the suites that ran what held them, by the base's own lines --
    the cut used to be read as the comment beside it, and dropped;
  * a module-level call (ALL.update(...)): every suite that ran anything of
    the module -- it used to be no suite at all, since it assigns no name;
  * a constant: the suites that ran a function naming it;
  * a tool: its own tools/test_<it>.py;
  * a table read by a loader nearly every suite runs: every suite that ran
    the loader -- it used to be left out as «common», and only the suite
    naming the file ran; a table named by a path a module's top level
    binds: the suites that ran a function using the path (it used to be
    only the suite naming the file); a table read at the top of a module:
    every suite that imported it;
  * a table renamed: the suites naming its old name (a rename used to show
    no lines at all);
  * the docs: nothing; a file nobody names: everything;
  * a base git does not know, and a folder git cannot read: everything, with
    the reason -- it used to say «nothing to run» and exit 0;
  * a suite the map has never seen: always.

And the map of a recorded run is written where git cannot say the commit
(a worktree of Windows git read from WSL) -- it used to be lost, run and all.

And a suite that runs past its timeout is killed with what it started.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))

import suite  # noqa: E402

from testkit import check, fails  # noqa: E402

MODULE = '''"""A module."""
import json
import os

TABLE = {"a": 1}
ALL = {}
ALL.update(TABLE)
KINDS_PATH = os.path.join("data", "kinds.json")
NAMES = json.load(open(os.path.join("data", "names.json")))


def used_by_a():
    # a comment
    x = 1
    return x


def used_by_b():
    return TABLE["a"]


def gone_soon():
    return 2


def load_table():
    return open(os.path.join("data", "table.json")).read()


def sorts():
    return open(KINDS_PATH).read()
'''

TREE = {
    "server/mod.py": MODULE,
    "server/test_a.py": "import mod\nmod.used_by_a()\n",
    "server/test_b.py": ("import mod\nmod.used_by_b()\nopen('../data/table.json')\n"
                         "open('../data/kinds.json')\n"),
    "server/test_c.py": "import mod\nmod.gone_soon()\nmod.sorts()\n",
    "data/table.json": "{}\n",
    "data/kinds.json": "{}\n",
    "data/names.json": "{}\n",
    "tools/helper.py": "def run():\n    return 1\n",
    "tools/test_helper.py": "import helper\nhelper.run()\n",
    "README.md": "# docs\n",
    "Dockerfile": "FROM scratch\n",
}
# load_table is run by three suites of four: nearly every one (suite.affected's
# «common»), as world.placements is. Only test_a is noted as importing the
# module, so that an import's read of names.json is told from the rest.
MAP = {"suites": {"test_a": ["server/mod.py:<module>", "server/mod.py:used_by_a",
                             "server/mod.py:load_table"],
                  "test_b": ["server/mod.py:used_by_b", "server/mod.py:load_table"],
                  "test_c": ["server/mod.py:gone_soon", "server/mod.py:load_table",
                             "server/mod.py:sorts"],
                  "test_helper": []}}
EVERY = ["test_a", "test_b", "test_c", "test_helper"]


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "init.defaultBranch=main", "-c", "core.autocrlf=false"]
                          + list(args), cwd=root, capture_output=True, text=True, check=True).stdout


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)
    with io.open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def edit(root, path, old, new):
    full = os.path.join(root, path)
    text = io.open(full, encoding="utf-8").read()
    assert old in text, (path, old)
    write(root, path, text.replace(old, new, 1))


ROOT = tempfile.mkdtemp(prefix="suite_affected_")
for _p, _t in TREE.items():
    write(ROOT, _p, _t)
git(ROOT, "init", "-q")
git(ROOT, "add", "-A")
git(ROOT, "commit", "-q", "-m", "base")
BASE = git(ROOT, "rev-parse", "HEAD").strip()
suite.ROOT = ROOT


def picked(change=None, impact=MAP, base=None):
    """What --affected would run for a change made in the working tree,
    the tree put back afterwards."""
    if change:
        change()
    try:
        names, why = suite.affected(base or BASE, json.loads(json.dumps(impact)))
    finally:
        git(ROOT, "reset", "-q", "--hard", BASE)
        git(ROOT, "clean", "-qfd")
    return sorted(names), why


check("the suites of the throwaway tree", sorted(suite.name_of(p) for p in suite.suites()), EVERY)
check("nothing changed, nothing to run", picked()[0], [])
check("a line written in a function: the suite that ran it",
      picked(lambda: edit(ROOT, "server/mod.py", "x = 1", "x = 3"))[0], ["test_a"])
check("a line taken away right after a comment: the suite that ran its function",
      picked(lambda: edit(ROOT, "server/mod.py", "    x = 1\n", ""))[0], ["test_a"])
check("a whole function taken away: the suite that ran it",
      picked(lambda: edit(ROOT, "server/mod.py", "\n\ndef gone_soon():\n    return 2\n", ""))[0],
      ["test_c"])
check("a module-level call taken away: every suite that ran anything of the module",
      picked(lambda: edit(ROOT, "server/mod.py", "ALL.update(TABLE)\n", ""))[0],
      ["test_a", "test_b", "test_c"])
check("a constant: the suite that ran a function naming it",
      picked(lambda: edit(ROOT, "server/mod.py", '{"a": 1}', '{"a": 2}'))[0], ["test_b"])
check("a tool: its own suite",
      picked(lambda: edit(ROOT, "tools/helper.py", "return 1", "return 7"))[0], ["test_helper"])
check("a table read by a loader nearly every suite runs: every suite that ran it",
      picked(lambda: edit(ROOT, "data/table.json", "{}", '{"a": 1}'))[0],
      ["test_a", "test_b", "test_c"])
check("a table a module's top level names by a path: the suites that ran a function"
      " using the path, and the one naming the file",
      picked(lambda: edit(ROOT, "data/kinds.json", "{}", '{"a": 1}'))[0], ["test_b", "test_c"])
check("a table a module's top level reads: every suite that imported the module",
      picked(lambda: edit(ROOT, "data/names.json", "{}", '{"a": 1}'))[0], ["test_a"])
_renamed = picked(lambda: git(ROOT, "mv", "data/table.json", "data/table2.json"))[0]
check("a table renamed: the suite naming its old name is run", "test_b" in _renamed, True)
check("the docs: nothing", picked(lambda: edit(ROOT, "README.md", "docs", "the docs"))[0], [])
_names, _why = picked(lambda: edit(ROOT, "Dockerfile", "scratch", "alpine"))
check("a file no suite names: everything", _names, EVERY)
_names, _why = picked(base="origin/no-such-branch")
check("a base git does not know: everything, and why",
      (_names, "git" in _why.get("*", "")), (EVERY, True))
_names, _why = picked(lambda: edit(ROOT, "README.md", "docs", "the docs"),
                      impact={"suites": {k: v for k, v in MAP["suites"].items() if k != "test_c"}})
check("a suite the map has never seen runs, whatever changed", _names, ["test_c"])
check("no map: everything", picked(impact=None)[0], EVERY)

# A folder git cannot read as a checkout: the tree without its .git.
_bare = tempfile.mkdtemp(prefix="suite_nogit_")
for _p, _t in TREE.items():
    write(_bare, _p, _t)
suite.ROOT = _bare
try:
    _names, _why = suite.affected("origin/main", MAP)
finally:
    suite.ROOT = ROOT
check("not a checkout git can read: everything, and why",
      (sorted(_names), "git" in _why.get("*", "")), (EVERY, True))

# A recorded run there: the map is still written, the commit unknown.
_rec, _maps = tempfile.mkdtemp(prefix="suite_rec_"), tempfile.mkdtemp(prefix="suite_map_")
write(_rec, "test_a-1.txt", "server/mod.py:used_by_a")
write(_rec, "test_a-2.txt", "server/mod.py:load_table")
_map_was, suite.MAP, suite.ROOT = suite.MAP, os.path.join(_maps, "impact_map.json"), _bare
try:
    suite.save_map(_rec, ["test_a"])
    _saved = json.load(open(suite.MAP, encoding="utf-8"))
except Exception as exc:
    _saved = {"error": repr(exc)}
finally:
    suite.MAP, suite.ROOT = _map_was, ROOT
check("a recorded run git cannot name the commit of: its map written all the same",
      (_saved.get("suites"), _saved.get("commit", "none written"), _saved.get("error")),
      ({"test_a": ["server/mod.py:load_table", "server/mod.py:used_by_a"]}, None, None))
shutil.rmtree(_rec, ignore_errors=True)
shutil.rmtree(_maps, ignore_errors=True)

check("a binary file in a diff is a whole file",
      suite.parse_diff("diff --git a/x.png b/x.png\nindex 1..2 100644\n"
                       "Binary files a/x.png and b/x.png differ\n"),
      {"x.png": (suite.WHOLE, suite.WHOLE)})


# --- a suite past its timeout goes with what it started -----------------------------
if os.name != "nt":
    _hang = tempfile.mkdtemp(prefix="suite_hang_")
    _pidfile = os.path.join(_hang, "child.pid")
    write(_hang, "test_hang.py",
          "import subprocess, sys, time\n"
          "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
          "open(%r, 'w').write(str(child.pid))\n"
          "time.sleep(120)\n" % _pidfile)
    _out = os.path.join(_hang, "out")
    suite.run([os.path.join(_hang, "test_hang.py")], _out, 1, _hang, 0, timeout=2)
    _child = int(open(_pidfile).read())
    time.sleep(0.3)
    try:
        os.kill(_child, 0)
        _alive = True
    except OSError:
        _alive = False
    if _alive:
        # Not ours to leave behind, whatever the check says.
        try:
            os.kill(_child, 9)
        except OSError:
            pass
    _summary = open(os.path.join(_out, "summary.txt")).read().split()
    check("past its timeout the suite is killed with the child it started",
          (_summary[0] != "0", _alive), (True, False))
    shutil.rmtree(_hang, ignore_errors=True)

# --- regression cases use the same JSON report and failing exit code ---------
with tempfile.TemporaryDirectory(prefix="suite_cases_") as _cases:
    _helper_path = os.path.join(os.path.dirname(HERE), "server")
    _case_bodies = {
        "success": "    def test_rule(self):\n        self.assertEqual(1, 1)\n",
        "failure": "    def test_rule(self):\n        self.assertEqual(1, 2)\n",
        "fixture": "    @classmethod\n    def setUpClass(cls):\n        raise RuntimeError('fixture failed')\n"
                   "    def test_rule(self):\n        pass\n",
        "subtest": "    def test_rule(self):\n        with self.subTest(value=1):\n            self.assertEqual(1, 2)\n",
        "skip": "    def test_rule(self):\n        self.skipTest('not exercised')\n",
    }
    for _mode, _body in _case_bodies.items():
        _report_path = os.path.join(_cases, _mode + ".jsonl")
        _source = ("import unittest\nfrom testkit import run_cases\n"
                   "class ImportedFixture(unittest.TestCase):\n"
                   "    def test_must_not_be_collected(self):\n        self.fail('duplicate fixture')\n"
                   "class Case(unittest.TestCase):\n" + _body + "run_cases(Case)\n")
        _result = subprocess.run(
            [sys.executable, "-B", "-c", _source], capture_output=True, text=True,
            env=dict(os.environ, PYTHONPATH=_helper_path, LAVA_TEST_REPORT=_report_path))
        _rows = [json.loads(line) for line in open(_report_path, encoding="utf-8")]
        _ok = _mode == "success"
        check("regression %s: one reported scenario, explicit fixture selection, correct exit" % _mode,
              (_result.returncode, [row["ok"] for row in _rows]),
              (0 if _ok else 1, [_ok]))

shutil.rmtree(ROOT, ignore_errors=True)
shutil.rmtree(_bare, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("suite OK")
