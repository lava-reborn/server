"""Publishing from an editor of the admin panel straight to a branch: what
the quest editor (tools/quest_editor.py --repo) and the location editor
(tools/location_editor.py --repo) share.

The panel runs each editor in a container of its own, on a clone of
lvrbrn/server whose origin is the source of truth. «Опубликовать» there is a
commit pushed straight to the branch -- for main that is a deploy (CI tests
it and rolls it out). The editor never writes its checkout: an edit is
merged onto what origin has now, checked, and the commit is made out of git
objects alone (commit-tree in an index of its own), so the running checkout
is never touched and two publishes never step on each other's files.

Publisher holds the clone and does the git side:

  fetch, fetch_now_and_then   origin/<branch> now, or at most every FETCH_EVERY
  rev, has, show, info, ls    reading commits and their files
  ensure(base)                a page's base commit in a shallow clone (deepened once)
  engine_moved(rev)           the files of ENGINE that differ between the checkout
                              and rev, the editor's own merged files aside: when
                              origin's engine is not the checkout's, a check would
                              run stale code, so the editor restarts first
  commit(head, files, ...)    a commit on head with files in place (None: taken
                              out), built in a temporary GIT_INDEX_FILE
  push(sha)                   sha:refs/heads/<branch>; False when the branch moved
  worktree(rev)               a git worktree of rev, for running main's own code on
                              a candidate tree (the location editor's checks, L4)
  restart()                   exit with RESTART_CODE once no publish runs: the
                              container's entrypoint checks the new commit out and
                              starts the editor again from it

The merge itself, the checks and the publish loop (PUSH_TRIES attempts when
the branch moves between fetch and push) are the editor's own. run_suites
runs suites of a tree the way tools/run_suite.sh --known does, for a check
before a push.
"""
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

FETCH_EVERY = 15          # seconds: a page load fetches at most this often
GIT_TIMEOUT = 60
PUSH_TIMEOUT = 120
PUSH_TRIES = 3            # a branch that moved between fetch and push: again
DEEPEN = 500              # a shallow clone's history, deepened once for a base
RESTART_CODE = 75         # the entrypoint checks out the new commit and restarts
SHA = re.compile(r"^[0-9a-f]{7,64}$")

# What a 502 says above git's own words (in English, LC_ALL=C). {section}:
# the README section of the panel that says how the deploy key is set up.
FETCH_FAILED = ("Свежий {branch} получить не удалось: GitHub не ответил или не пустил. "
                "Если так и останется, проверьте ключ развёртывания на сервере "
                "(README панели, раздел «{section}»).")
PUSH_FAILED = ("GitHub не принял коммит, и в {branch} он не попал. Проверьте, что у ключа "
               "развёртывания есть право записи и что защита ветки {branch} его пропускает "
               "(README панели, раздел «{section}»).")
GIT_FAILED = "Git в контейнере редактора не справился; его слова ниже."
RESTARTING = "Редактор подтягивает свежий %s, повторите через несколько секунд"
ENGINE_MOVED = ("В %s новый код проверок: редактор перезапускается на нём, "
                "повторите через несколько секунд")


class GitError(Exception):
    """A git command that failed; the text is its stderr, trimmed."""


class FetchError(GitError):
    """The fetch from origin failed: origin did not answer or let us in."""


class BaseMissing(Exception):
    """The commit the page was opened on is not in the clone, even deepened."""


class EngineMoved(Exception):
    """origin's engine (ENGINE) is not the checkout's: restart before checking."""


def trim(text, limit=600):
    lines = [l.strip() for l in (text or "").replace("\r", "\n").split("\n") if l.strip()]
    out = "\n".join(lines)
    return out if len(out) <= limit else "…" + out[-limit:]


# What git says after any failed fetch or clone, whatever the cause.
_GENERIC = ("could not read from remote repository", "please make sure you have the correct access",
            "and the repository exists")


def reason(text, limit=200):
    """The line of git's stderr that says what went wrong: the first
    "fatal:" or "error:" one that is not git's closing boilerplate ("Please
    make sure you have the correct access rights and the repository
    exists."), else the first other line (ssh's own "Permission denied
    (publickey)" has no prefix), else the last."""
    lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
    told = [l for l in lines if not any(g in l.lower() for g in _GENERIC)]
    pick = [l for l in told if l.lower().startswith(("fatal:", "error:"))] or told or lines[-1:]
    line = pick[0] if pick else ""
    return line if len(line) <= limit else line[:limit] + "…"


def one_line(text):
    """text as one line of a commit message: control characters (an escape,
    a newline) and other unprintable ones become spaces, spaces squeezed."""
    text = "".join(ch if ch.isprintable() else " " for ch in str(text))
    return re.sub(r"\s+", " ", text).strip()


def clean_login(raw):
    """X-Lava-Admin as it may stand in a commit: printable, no <>, at most 64."""
    text = "".join(ch for ch in (raw or "") if ch.isprintable() and ch not in "<>\r\n")
    return text.strip()[:64].strip()


def clean_note(raw, limit=2000):
    """The admin's own words for the commit message: lines kept, no control
    characters, not longer than limit."""
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch.isprintable())
    return text.strip()[:limit].strip()


def header_text(raw):
    """A header http.server read as Latin-1, back to the UTF-8 it was sent in
    (the panel sends a Cyrillic login as its UTF-8 bytes)."""
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def _exit_now(code):
    os._exit(code)


class Publisher:
    """The clone publish mode works on: fetches, reads, commits and pushes to
    origin/<branch>, one publish at a time (lock).

    engine: the paths (files or folders) whose change in origin means the
    checkout's code would check stale; merged: those of them the editor
    merges itself (a file, or a folder ending in "/"), never a reason to
    restart. section: the panel README's section for the error texts.
    ident: {"author_email", "committer_name", "committer_email"}: (the
    environment variable, its default), read at each commit."""

    def __init__(self, repo, branch="main", web="", engine=(), merged=(), section="Квесты",
                 ident=None, tmp_prefix="publish-"):
        self.repo = os.path.abspath(repo)
        self.branch = branch
        self.web = (web or "").rstrip("/")
        self.engine = tuple(engine)
        self.merged = tuple(merged)
        self.section = section
        self.ident = dict(ident or {})
        self.tmp_prefix = tmp_prefix
        self.lock = threading.Lock()          # one publish at a time
        self._fetch_lock = threading.Lock()
        self._fetched = 0.0
        self._fetch_error = None
        self.restarting = False
        self.exit = _exit_now                 # a test puts its own here
        self.before_push = None               # and a hook here, to move the branch

    # -- git --------------------------------------------------------------------
    def git(self, *args, data=None, env=None, timeout=GIT_TIMEOUT, cwd=None):
        """git -C repo args...: its stdout; GitError with its stderr. An
        argument list and a timeout, never a shell."""
        full = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C", LANG="C")
        full.update(env or {})
        try:
            done = subprocess.run(["git", "-C", cwd or self.repo] + list(args), input=data,
                                  capture_output=True, timeout=timeout, env=full)
        except subprocess.TimeoutExpired:
            raise GitError("git %s: no answer in %d s" % (args[0], timeout)) from None
        except OSError as exc:
            raise GitError("git: %s" % exc) from None
        if done.returncode:
            raise GitError(trim(done.stderr.decode("utf-8", "replace"))
                           or "git %s failed (%d)" % (args[0], done.returncode))
        return done.stdout

    @property
    def remote_ref(self):
        return "refs/remotes/origin/" + self.branch

    def fetch(self):
        """git fetch of the branch, now. Raises FetchError."""
        with self._fetch_lock:
            try:
                self.git("fetch", "--quiet", "--no-tags", "origin",
                         "+refs/heads/%s:%s" % (self.branch, self.remote_ref))
                self._fetch_error = None
            except GitError as exc:
                self._fetch_error = str(exc)
                raise FetchError(str(exc)) from None
            finally:
                self._fetched = time.monotonic()

    def fetch_now_and_then(self):
        """fetch, at most once per FETCH_EVERY: the reason it failed, or None."""
        with self._fetch_lock:
            if self._fetched and time.monotonic() - self._fetched < FETCH_EVERY:
                return self._fetch_error
        try:
            self.fetch()
        except GitError as exc:
            return str(exc)
        return None

    def rev(self, name):
        return self.git("rev-parse", "--verify", name + "^{commit}").decode().strip()

    def has(self, sha):
        try:
            self.git("cat-file", "-e", sha + "^{commit}")
            return True
        except GitError:
            return False

    def show(self, rev, path):
        """The file's bytes at rev, or None when it has no such file."""
        try:
            return self.git("cat-file", "blob", "%s:%s" % (rev, path))
        except GitError:
            return None

    def ls(self, rev, path):
        """The names under path at rev (git ls-tree --name-only), [] when
        there is no such folder."""
        try:
            out = self.git("ls-tree", "--name-only", rev, path.rstrip("/") + "/")
        except GitError:
            return []
        return [n for n in out.decode("utf-8").split("\n") if n]

    def info(self, rev="HEAD"):
        out = self.git("log", "-1", "--format=%H%x00%cI%x00%an%x00%s", rev)
        sha, date, author, subject = (out.decode("utf-8", "replace").strip().split("\0")
                                      + ["", "", "", ""])[:4]
        return {"sha": sha, "date": date, "author": author, "subject": subject}

    def is_merged(self, path):
        for m in self.merged:
            if path == m or (m.endswith("/") and path.startswith(m)):
                return True
        return False

    def engine_moved(self, rev):
        """The files under ENGINE that differ between the checkout and rev,
        the editor's merged files aside: what a check would read stale."""
        if not self.engine:
            return []
        names = self.git("diff", "--no-renames", "--name-only", "HEAD", rev, "--", *self.engine)
        return [n for n in names.decode("utf-8").split("\n") if n and not self.is_merged(n)]

    def ensure(self, base):
        """The base commit in the clone, deepening a shallow one once."""
        if self.has(base):
            return
        if self.git("rev-parse", "--is-shallow-repository").strip() == b"true":
            try:
                self.git("fetch", "--quiet", "--no-tags", "--deepen=%d" % DEEPEN, "origin",
                         "+refs/heads/%s:%s" % (self.branch, self.remote_ref),
                         timeout=PUSH_TIMEOUT)
            except GitError:
                pass
            if self.has(base):
                return
        raise BaseMissing(base)

    def failed(self, lead, exc):
        """A 502's body: what happened in the page's words, git's own below."""
        return {"error": lead.format(branch=self.branch, section=self.section), "git": str(exc)}

    # -- the commit ---------------------------------------------------------------
    def _ident(self, key, default):
        env, value = self.ident.get(key, (None, default))
        return (os.environ.get(env) if env else None) or value

    def commit(self, head, files, message, login):
        """A commit on head with files ({path: bytes, or None to take the
        file out}) in place, built in a temporary index: the checkout and its
        index are never touched."""
        tmp = tempfile.mkdtemp(prefix=self.tmp_prefix)
        try:
            env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
            self.git("read-tree", head, env=env)
            for path, data in sorted(files.items()):
                if data is None:
                    self.git("update-index", "--force-remove", "--", path, env=env)
                    continue
                blob = self.git("hash-object", "-w", "--stdin", data=data).decode().strip()
                listed = self.git("ls-tree", head, "--", path).decode().split()
                mode = listed[0] if listed else "100644"
                self.git("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, blob, path),
                         env=env)
            tree = self.git("write-tree", env=env).decode().strip()
            env.update(
                GIT_AUTHOR_NAME="%s (админка)" % login,
                GIT_AUTHOR_EMAIL=self._ident("author_email", "editor@lava-reborn.ru"),
                GIT_COMMITTER_NAME=self._ident("committer_name", "Редактор админки"),
                GIT_COMMITTER_EMAIL=self._ident("committer_email", "editor@lava-reborn.ru"))
            return self.git("commit-tree", tree, "-p", head, "-F", "-",
                            data=message.encode("utf-8"), env=env).decode().strip()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def push(self, sha):
        """True when origin took it, False when the branch moved meanwhile (a
        non-fast-forward); GitError for anything else."""
        try:
            self.git("push", "--quiet", "origin", "%s:refs/heads/%s" % (sha, self.branch),
                     timeout=PUSH_TIMEOUT)
            return True
        except GitError as exc:
            text = str(exc)
            if "[rejected]" in text or "non-fast-forward" in text or "fetch first" in text:
                return False
            raise

    def _about(self, sha):
        """info(sha), or as much as is known: a reply about a commit already
        pushed must not turn into an error."""
        try:
            return self.info(sha)
        except GitError:
            return {"sha": sha, "date": "", "author": "", "subject": ""}

    # -- a tree of a commit -----------------------------------------------------------
    @contextlib.contextmanager
    def worktree(self, rev, under=None):
        """A git worktree of rev (detached), taken away afterwards: main's own
        code and tables on disk, to run on a candidate tree."""
        parent = under or tempfile.gettempdir()
        os.makedirs(parent, exist_ok=True)
        path = tempfile.mkdtemp(prefix=self.tmp_prefix + "tree-", dir=parent)
        os.rmdir(path)
        self.git("worktree", "add", "--quiet", "--detach", path, rev, timeout=PUSH_TIMEOUT)
        try:
            yield path
        finally:
            try:
                self.git("worktree", "remove", "--force", path, timeout=PUSH_TIMEOUT)
            except GitError:
                shutil.rmtree(path, ignore_errors=True)
            try:
                self.git("worktree", "prune")
            except GitError:
                pass

    def changed_in(self, tree, paths):
        """{path: bytes or None (gone)} of what differs in a worktree from its
        HEAD under paths: modified, new (untracked too) and deleted files."""
        out = self.git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames",
                       "--", *paths, cwd=tree)
        files = {}
        for item in out.decode("utf-8").split("\0"):
            if len(item) < 4:
                continue
            path = item[3:]
            full = os.path.join(tree, *path.split("/"))
            if os.path.isfile(full):
                with open(full, "rb") as fh:
                    files[path] = fh.read()
            else:
                files[path] = None
        return files

    # -- restarting --------------------------------------------------------------------
    def restart(self):
        """Exit with RESTART_CODE once no publish is running, so the entrypoint
        checks out what origin has now and starts the editor from it."""
        if self.restarting:
            return
        self.restarting = True

        def go():
            with self.lock:
                time.sleep(0.2)               # the 503 is on its way out
                sys.stdout.flush()
                sys.stderr.flush()
                self.exit(RESTART_CODE)
        threading.Thread(target=go, daemon=True).start()


# --- suites before a push ----------------------------------------------------------------

def known_failures(path):
    """{suite path: [patterns]} of a known-failures list (tools/known_failures.txt:
    "suite | pattern[ && pattern] | reason")."""
    out = {}
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return out
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or s.count("|") < 2:
            continue
        suite, pattern, _why = (p.strip() for p in s.split("|", 2))
        out[suite] = [p for p in pattern.split(" && ") if p]
    return out


def _matches(patterns, text):
    lines = text.splitlines()
    for p in patterns:
        try:
            rx = re.compile(p)
        except re.error:
            return False
        if not any(rx.search(l) for l in lines):
            return False
    return True


def run_suites(root, suites, env=None, jobs=2, timeout=900, known=None, scratch=None, drop=()):
    """Run suites of the tree root (paths relative to it, e.g.
    server/test_locations.py), jobs at a time, each in its own folder with a
    database and a TMPDIR of its own, as tools/run_suite.sh does; env is
    laid over this process's environment, drop taken out of it. A failure
    whose output shows its known_failures.txt line is allowed, as
    run_suite.sh --known has it. [{suite, ok, code, seconds, known, tail}]
    in the order given."""
    from concurrent.futures import ThreadPoolExecutor
    known = known_failures(os.path.join(root, "tools", "known_failures.txt")) if known is None else known
    base = scratch or tempfile.mkdtemp(prefix="suites-")
    os.makedirs(base, exist_ok=True)

    def one(rel):
        name = os.path.splitext(os.path.basename(rel))[0]
        work = os.path.join(base, name)
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(os.path.join(work, "tmp"))
        e = dict(os.environ)
        for k in drop:
            e.pop(k, None)
        e.update(env or {})
        e.update(LAVA_DB=os.path.join(work, "lava.db"), TMPDIR=os.path.join(work, "tmp"),
                 PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        e.pop("LAVA_TEST_REPORT", None)
        path = os.path.join(root, *rel.split("/"))
        t0 = time.time()
        if not os.path.isfile(path):
            return {"suite": rel, "ok": False, "code": None, "seconds": 0, "known": False,
                    "tail": "нет такого набора: %s" % rel}
        try:
            p = subprocess.run([sys.executable, os.path.basename(path)], cwd=os.path.dirname(path), env=e,
                               capture_output=True, timeout=timeout)
            code = p.returncode
            text = (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            code = None
            text = ((exc.stdout or b"") + b"\n" + (exc.stderr or b"")).decode("utf-8", "replace")
            text += "\n(не уложился в %d с)" % timeout
        allowed = code not in (0, None) and rel in known and _matches(known[rel], text)
        tail = "\n".join(text.strip().splitlines()[-25:])
        return {"suite": rel, "ok": code == 0 or allowed, "code": code, "seconds": round(time.time() - t0, 1),
                "known": allowed, "tail": tail if code != 0 else ""}

    try:
        with ThreadPoolExecutor(max_workers=max(1, int(jobs))) as ex:
            return list(ex.map(one, suites))
    finally:
        if scratch is None:
            shutil.rmtree(base, ignore_errors=True)
