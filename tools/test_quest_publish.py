"""The quest editor's publish mode (tools/quest_editor.py --repo), without a
browser and without GitHub: origin is a bare repository made here from the
current tables (LF, as GitHub has them), the editor works on a shallow clone
of it, and a second clone plays everybody else pushing to main meanwhile.

  * the table says publish mode and the commit it comes from; save and diff
    are refused (403), a publish without X-Lava-Admin or a base (400);
  * an edit publishes one commit whose file is dumps_table of the merged
    table byte for byte (LF), touching only that row, by the admin, with the
    summary in its message; the layout goes with it, unknown types out;
  * a commit to another row pushed meanwhile is merged in; the same row
    changed on both sides is a conflict (409) and nothing is pushed, and
    the reply says what the page becomes if it takes main's version of it
    (which then publishes the page's other edits);
  * a row deleted in main and untouched on the page stays deleted; a new
    quest is appended, and a fresh one skips a number main took meanwhile;
    a new quest whose number main took after all goes out under the next
    free one, the page's links to it moved along;
  * a table with an error is refused (422) and nothing is pushed; so is a
    row key that is no plain name (400), and a table that would read back
    otherwise than it was checked (422); no change is "nothing";
  * a push the branch moved under is tried again and goes through; a push
    origin refuses is a 502 in the page's words, git's own below;
  * a base the shallow clone lacks is fetched by deepening; one origin
    never had is a 409;
  * a fetch that fails serves the checkout, "stale", and a preview says so
    (502); main moved on makes /api/table answer 503 and the editor ask to
    be restarted (exit 75); main's engine moved on does the same to a
    publish, before anything is pushed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TMP = tempfile.mkdtemp(prefix="quest-publish-test-")
# git as a fresh machine has it: none of this user's settings (signing,
# hooks, templates) in the way.
_cfg = os.path.join(TMP, "gitconfig")
open(_cfg, "w").close()
os.environ["GIT_CONFIG_GLOBAL"] = _cfg
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
for _k in ("LAVA_QUESTS_AUTHOR_EMAIL", "LAVA_QUESTS_COMMITTER_NAME", "LAVA_QUESTS_COMMITTER_EMAIL"):
    os.environ.pop(_k, None)

import quest_editor as qe  # noqa: E402
import quests  # noqa: E402

fails = []


def check(what, got, want):
    if got == want:
        print("ok   ", what)
    else:
        print("FAIL ", what, "\n      got: %r\n     want: %r" % (got, want))
        fails.append(what)


def gitb(cwd, *args):
    done = subprocess.run(["git", "-C", cwd, "-c", "user.name=Somebody Else",
                           "-c", "user.email=else@example.invalid"] + list(args),
                          capture_output=True, timeout=120)
    if done.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), done.stderr.decode("utf-8", "replace")))
    return done.stdout


def git(cwd, *args):
    return gitb(cwd, *args).decode("utf-8").strip()


def lf(path):
    with open(path, "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def as_js(v):
    """What comes back from the page: JavaScript's one kind of number."""
    if isinstance(v, dict):
        return {k: as_js(x) for k, x in v.items()}
    if isinstance(v, list):
        return [as_js(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


# --- origin, the editor's clone, somebody else's clone ---------------------------
seed = os.path.join(TMP, "seed")
os.makedirs(os.path.join(seed, "data"))
table_lf = lf(qe.TABLE)
for p in quests.companion_paths(qe.TABLE):
    with open(os.path.join(seed, "data", os.path.basename(p)), "wb") as fh:
        fh.write(lf(p))
git(TMP, "init", "-q", "-b", "main", seed)
# An older commit under the current one: the shallow clone will not have it.
older = json.loads(table_lf)
older["quests"][0]["name"] += " (старое)"
with open(os.path.join(seed, "data", "quests.json"), "wb") as fh:
    fh.write(qe.dumps_table(older).encode("utf-8"))
git(seed, "add", "-A")
git(seed, "commit", "-q", "-m", "older")
with open(os.path.join(seed, "data", "quests.json"), "wb") as fh:
    fh.write(table_lf)
git(seed, "commit", "-q", "-am", "current")
OLD = git(seed, "rev-parse", "HEAD~1")
bare = os.path.join(TMP, "origin.git")
git(TMP, "clone", "-q", "--bare", seed, bare)
clone = os.path.join(TMP, "clone")
git(TMP, "clone", "-q", "--depth", "1", "--single-branch", "--branch", "main",
    "file://" + bare, clone)
other = os.path.join(TMP, "other")
git(TMP, "clone", "-q", "file://" + bare, other)
HEAD0 = git(bare, "rev-parse", "main")
check("the table round-trips as dumps_table writes it (LF)",
      qe.dumps_table(json.loads(table_lf)).encode("utf-8"), table_lf)

WEB = "https://example.invalid/lava/server"
pub = qe.configure(clone, "main", WEB)
exits = []
pub.exit = exits.append
srv = qe.serve(0)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def call(url, body=None, admin="tester"):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if admin:
        headers["X-Lava-Admin"] = admin
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, url), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw, code = resp.read(), resp.status
    except urllib.error.HTTPError as exc:
        raw, code = exc.read(), exc.code
    try:
        return code, json.loads(raw.decode("utf-8"))
    except ValueError:
        return code, raw.decode("utf-8", "replace")


def origin_head():
    return git(bare, "rev-parse", "main")


def rows_at(rev):
    return json.loads(gitb(bare, "show", "%s:data/quests.json" % rev))["quests"]


def somebody(change, message="somebody else"):
    """A commit to main from another clone, the way a merged PR lands."""
    git(other, "fetch", "-q", "origin")
    git(other, "reset", "-q", "--hard", "origin/main")
    path = os.path.join(other, "data", "quests.json")
    doc = json.loads(lf(path))
    change(doc["quests"])
    with open(path, "wb") as fh:
        fh.write(qe.dumps_table(doc).encode("utf-8"))
    git(other, "commit", "-q", "-am", message)
    git(other, "push", "-q", "origin", "main")
    return git(other, "rev-parse", "HEAD")


def renamed(rows, t, name):
    for r in rows:
        if r["type"] == t:
            r["name"] = name


def by_type(rows):
    return {r["type"]: r for r in rows}


# --- the table, and what publish mode refuses ---------------------------------------
code, table = call("/api/table")
check("GET /api/table: publish mode and the commit the table comes from",
      (code, table.get("mode"), table.get("commit"), table.get("branch"), table.get("web")),
      (200, "publish", HEAD0, "main", WEB))
check("with that commit's details", (table["head"]["sha"], table["head"]["subject"], "stale" in table),
      (HEAD0, "current", False))
check("and the rows of the clone", table["rows"], json.loads(table_lf)["quests"])
with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=30) as resp:
    check("GET /health", (resp.status, resp.read()), (200, b"ok"))
code, ent = call("/api/entry")
check("GET /api/entry: the built page's script and styles",
      (code, ent["js"].startswith("assets/") and ent["js"].endswith(".js"),
       bool(ent["css"]) and all(c.startswith("assets/") and c.endswith(".css") for c in ent["css"])),
      (200, True, True))
check("POST /api/save is refused in publish mode", call("/api/save", {"rows": table["rows"]})[0], 403)
check("GET /api/diff too", call("/api/diff")[0], 403)
check("a publish without X-Lava-Admin is refused",
      call("/api/publish", {"rows": table["rows"], "base": HEAD0}, admin=None)[0], 400)
check("and one without a base",
      call("/api/publish", {"rows": table["rows"], "base": "main; rm -rf /"})[0], 400)

rows0 = json.loads(table_lf)["quests"]
hand = [r for r in rows0 if r.get("name") and "<" not in r["name"]]
referenced = set()
for r in quests.table_rows(quests.PATH):
    for k in ("need_quest", "need_any", "excludes"):
        v = r.get(k)
        referenced |= set(v if isinstance(v, list) else [v] if v else [])
free = [r["type"] for r in hand if r["type"] not in referenced]
X, Y, Z, V, U, T = [r["type"] for r in hand[1:7]]
W = next(t for t in free if t not in (X, Y, Z, V, U, T))

# --- an edit -----------------------------------------------------------------------------
page = as_js(rows0)
renamed(page, X, by_type(rows0)[X]["name"] + " (правка из админки)")
layout = {"positions": {str(X): {"x": 10.4, "y": -3.6}, "999999": {"x": 1, "y": 2}}}
code, prev = call("/api/preview", {"rows": page, "layout": layout, "base": HEAD0})
check("POST /api/preview: the edit and the layout, nothing in the way",
      (code, prev.get("head"), prev.get("conflicts"), prev.get("layout_changed"), prev.get("nothing"),
       [p for p in prev.get("problems", []) if p["level"] == "error"]),
      (200, HEAD0, [], True, False, []))
check("its summary", prev.get("summary"),
      ["правка #%d «%s»: name" % (X, qe.plain_name(by_type(page)[X])), "раскладка графа: 1"])
check("its diff is the one line", [l for l in prev.get("diff", "").split("\n")
                                   if l[:1] in ("+", "-") and not l.startswith(("+++", "---"))],
      ['-      "name": %s,' % json.dumps(by_type(rows0)[X]["name"], ensure_ascii=False),
       '+      "name": %s,' % json.dumps(by_type(page)[X]["name"], ensure_ascii=False)])

# A login in Cyrillic, sent as UTF-8 the way a proxy sends it.
code, done = call("/api/publish", {"rows": page, "layout": layout, "base": HEAD0,
                                   "message": "проверка публикации"},
                  admin="Грач".encode("utf-8"))
C1 = origin_head()
check("POST /api/publish: pushed to main", (code, done.get("commit"), done.get("url")),
      (200, C1, WEB + "/commit/" + C1))
check("and the reply names the new commit", (done.get("head") or {}).get("sha"), C1)
want = json.loads(table_lf)
renamed(want["quests"], X, by_type(page)[X]["name"])
got = gitb(bare, "show", "main:data/quests.json")
check("the file is dumps_table of the merged table, byte for byte, LF",
      (got == qe.dumps_table(want).encode("utf-8"), b"\r" in got), (True, False))
check("one line of it changed", git(bare, "diff", "--numstat", HEAD0, C1, "--", "data/quests.json"),
      "1\t1\tdata/quests.json")
check("the reply carries the merged rows", done.get("rows"), want["quests"])
check("author and committer",
      git(bare, "log", "-1", "--format=%an|%ae|%cn|%ce", C1),
      "Грач (админка)|quests@lava-reborn.ru|Квест-редактор админки|quests@lava-reborn.ru")
msg = git(bare, "log", "-1", "--format=%B", C1)
check("the message: the summary, the admin's words, who",
      (msg.split("\n")[0], "правка #%d" % X in msg, "проверка публикации" in msg,
       msg.rstrip().endswith("Опубликовано из админки: Грач")),
      ("Квесты: правок: 1, раскладка", True, True, True))
lay = gitb(bare, "show", "main:data/quest_layout.json").decode("utf-8")
check("the layout went with it, whole pixels, unknown types dropped",
      ('"%d": [10, -4]' % X in lay, "999999" in lay), (True, False))
check("and the reply's layout is the page's form",
      done.get("layout", {}).get("positions", {}).get(str(X)), {"x": 10, "y": -4})

# --- somebody else's commit meanwhile: merged ------------------------------------------
C2 = somebody(lambda rows: renamed(rows, Y, "Игрек из ветки"))
page = as_js(done["rows"])
renamed(page, Z, "Зет из админки")
code, done = call("/api/publish", {"rows": page, "layout": done["layout"], "base": C1})
C3 = origin_head()
now = by_type(rows_at("main"))
check("a commit to another row meanwhile is merged in",
      (code, done.get("commit"), now[Y]["name"], now[Z]["name"], now[X]["name"]),
      (200, C3, "Игрек из ветки", "Зет из админки", by_type(page)[X]["name"]))
check("on top of it", git(bare, "rev-parse", C3 + "^"), C2)

# --- the same row both ways: a conflict ----------------------------------------------------
page = as_js(done["rows"])
somebody(lambda rows: renamed(rows, Y, "Игрек ещё раз из ветки"))
renamed(page, Y, "Игрек из админки")
renamed(page, Z, "Зет со страницы")
before = origin_head()
code, out = call("/api/publish", {"rows": page, "layout": done["layout"], "base": C3})
check("the same row changed on both sides: 409 with that quest",
      (code, [c["type"] for c in out.get("conflicts", [])]), (409, [Y]))
check("and nothing pushed", origin_head(), before)
code, prev = call("/api/preview", {"rows": page, "layout": done["layout"], "base": C3})
check("the preview says so too", (code, [c["type"] for c in prev.get("conflicts", [])]), (200, [Y]))
reb = out.get("rebase") or {}
took = by_type(reb.get("rows") or [])
check("the 409 says what the page becomes taking main's version of that quest: main's commit, "
      "main's #Y, the page's other edit, something left to publish",
      (reb.get("commit"), reb.get("head", {}).get("sha"), took.get(Y, {}).get("name"),
       took.get(Z, {}).get("name"), reb.get("changed"), (prev.get("rebase") or {}).get("rows") == reb.get("rows")),
      (before, before, "Игрек ещё раз из ветки", "Зет со страницы", True, True))
code, done = call("/api/publish", {"rows": reb["rows"], "layout": reb["layout"], "base": reb["commit"]})
now = by_type(rows_at("main"))
check("and that publishes the other edit, main's #Y kept",
      (code, done.get("summary"), now[Y]["name"], now[Z]["name"]),
      (200, ["правка #%d «Зет со страницы»: name" % Z], "Игрек ещё раз из ветки", "Зет со страницы"))

# --- a deletion in main, the page untouched there --------------------------------------------
B4 = origin_head()
page = as_js(rows_at(B4))
somebody(lambda rows: rows.remove(next(r for r in rows if r["type"] == W)), "delete a row")
renamed(page, V, "Вэ из админки")
code, done = call("/api/publish", {"rows": page, "layout": None, "base": B4})
now = by_type(rows_at("main"))
check("a row deleted in main and not edited here stays deleted",
      (code, W in now, now[V]["name"]), (200, False, "Вэ из админки"))
check("no layout sent, no layout touched",
      git(bare, "diff", "--name-only", done["commit"] + "^", done["commit"]), "data/quests.json")

# --- a new quest -------------------------------------------------------------------------------
B5 = origin_head()
page = as_js(rows_at(B5))
code, made = call("/api/new", {"kind": "del_obj", "rows": page})
page.append(made["row"])
code, done = call("/api/publish", {"rows": page, "layout": None, "base": B5})
last = rows_at("main")[-1]
check("a new quest is appended", (code, last["type"], done["summary"]),
      (200, made["row"]["type"], ["новый #%d «Новое задание»" % made["row"]["type"]]))
page = as_js(rows_at(origin_head()))
fresh = qe.new_row("del_obj", page)
somebody(lambda rows: rows.append(dict(fresh, name="Чужое новое задание")), "a new quest elsewhere")
pub.fetch()
code, made = call("/api/new", {"kind": "del_obj", "rows": page})
check("a new quest skips a number main took meanwhile", (code, made["row"]["type"] > fresh["type"]),
      (200, True))

# --- two pages add a quest before either publishes: the second is renumbered -------------------
B5b = origin_head()
page = as_js(rows_at(B5b))
code, made = call("/api/new", {"kind": "del_obj", "rows": page})
N = made["row"]["type"]
somebody(lambda rows: rows.append(dict(made["row"], name="Новое задание другого админа")),
         "another admin's new quest")
page.append(dict(made["row"], name="Моё новое задание"))
S = next(t for t in free if t not in (X, Y, Z, V, U, T, W))
by_type(page)[S]["need_quest"] = N
layout = {"positions": {str(N): {"x": 5, "y": 6}}}
code, prev = call("/api/preview", {"rows": page, "layout": layout, "base": B5b})
M = (prev.get("renumbered") or {}).get(str(N))
check("the same new number in main meanwhile: no conflict, the page's goes out under the next free one",
      (code, prev.get("conflicts"), isinstance(M, int) and M > N), (200, [], True))
code, done = call("/api/publish", {"rows": page, "layout": layout, "base": B5b})
now = by_type(rows_at("main"))
check("both new quests are in main, the page's one under its new number, its link moved along",
      (code, done.get("renumbered"), now[N]["name"], now.get(M, {}).get("name"), now[S].get("need_quest")),
      (200, {str(N): M}, "Новое задание другого админа", "Моё новое задание", M))
lay = gitb(bare, "show", "main:data/quest_layout.json").decode("utf-8")
check("and so did its place on the page", ('"%d": [5, 6]' % M in lay, '"%d": [5, 6]' % N in lay), (True, False))

# --- an error, and nothing ---------------------------------------------------------------------
B6 = origin_head()
page = as_js(rows_at(B6))
page[0]["kind"] = "dance"
code, out = call("/api/publish", {"rows": page, "layout": None, "base": B6})
check("a merged table with an error is refused",
      (code, [p["type"] for p in out.get("problems", [])][:1]), (422, [page[0]["type"]]))
check("and nothing pushed", origin_head(), B6)
code, out = call("/api/publish", {"rows": as_js(rows_at(B6)), "layout": None, "base": B6})
check("nothing changed: nothing", (code, out.get("nothing"), out.get("commit"), origin_head()),
      (200, True, B6, B6))

# --- keys that would write a table other than the one checked ---------------------------------
for key in ('zz": 0, "kind": "bogus_kind", "yy', "a\nb", "a\\b", "ключ"):
    page = as_js(rows_at(B6))
    page[1][key] = 0
    code, out = call("/api/publish", {"rows": page, "layout": None, "base": B6})
    check("a row key %r is refused (400), nothing pushed" % key, (code, origin_head()), (400, B6))
check("the preview refuses it too",
      call("/api/preview", {"rows": page, "layout": None, "base": B6})[0], 400)
page = as_js(rows_at(B6))
renamed(page, page[1]["type"], "прочти меня")
writes = qe.dumps_row
qe.dumps_row = lambda row: writes({k: v for k, v in row.items() if k != "why"})   # a writer gone wrong
try:
    code, out = call("/api/publish", {"rows": page, "layout": None, "base": B6})
finally:
    qe.dumps_row = writes
first = (out.get("problems") or [{}])[0]
check("a table whose text would read back otherwise than it was checked: 422, nothing pushed",
      (code, first.get("type"), "прочитался бы иначе" in first.get("ru", ""), origin_head()),
      (422, None, True, B6))
msg = qe.commit_message(["правка #7 «a\x1b[31mb»: name", "новый #8 «x\ny»"], "", "t")
check("summary lines in a commit message: one line each, no control characters",
      (msg.split("\n")[2:4], "\x1b" in msg), (["правка #7 «a [31mb»: name", "новый #8 «x y»"], False))
check("a name in a summary: markup and control characters out",
      qe.plain_name({"name": "a\x1bb <b>c</b>"}), "a b c")

# --- the branch moves between fetch and push --------------------------------------------------
B7 = origin_head()
page = as_js(rows_at(B7))
renamed(page, U, "Ю из админки")
moved = []


def move(attempt):
    moved.append(attempt)
    if attempt == 0:
        moved.append(somebody(lambda rows: renamed(rows, T, "Тэ в последний миг")))


pub.before_push = move
code, done = call("/api/publish", {"rows": page, "layout": None, "base": B7})
pub.before_push = None
now = by_type(rows_at("main"))
check("a push rejected because main moved is tried again and goes through",
      (code, moved[0], moved[2:], now[U]["name"], now[T]["name"]),
      (200, 0, [1], "Ю из админки", "Тэ в последний миг"))
check("on top of what moved it", git(bare, "rev-parse", done["commit"] + "^"), moved[1])

# --- a push origin refuses (a deploy key without write access) ----------------------------------
git(clone, "remote", "set-url", "--push", "origin", os.path.join(TMP, "nowhere.git"))
B8 = origin_head()
page = as_js(rows_at(B8))
renamed(page, U, "Ю без права записи")
code, out = call("/api/publish", {"rows": page, "layout": None, "base": B8})
check("a push origin refuses: 502, said in the page's words with git's below, main untouched",
      (code, "не принял коммит" in out.get("error", ""),
       "does not appear to be a git repository" in out.get("git", ""), origin_head()),
      (502, True, True, B8))
git(clone, "config", "--unset", "remote.origin.pushurl")

# --- bases --------------------------------------------------------------------------------------
check("the shallow clone lacks the older commit", pub.has(OLD), False)
code, prev = call("/api/preview", {"rows": as_js(older["quests"]), "layout": None, "base": OLD})
check("a base the clone lacks is fetched by deepening", (code, prev.get("conflicts"), pub.has(OLD)),
      (200, [], True))
code, out = call("/api/publish", {"rows": page, "layout": None, "base": "0123456789abcdef" * 2 + "01234567"})
check("a base origin never had: 409, reload", (code, out.get("conflicts"), "обновите" in out.get("error", "")),
      (409, [], True))

# --- stale, and main moved on ---------------------------------------------------------------------
url = git(clone, "remote", "get-url", "origin")
git(clone, "remote", "set-url", "origin", os.path.join(TMP, "nowhere.git"))
pub._fetched = 0
code, table = call("/api/table")
check("a fetch that fails serves the checkout, stale",
      (code, table.get("commit"), bool(table.get("stale"))), (200, HEAD0, True))
check("stale says why in git's words, not git's closing boilerplate",
      ("does not appear to be a git repository" in table.get("stale", ""),
       "repository exists" in table.get("stale", "")), (True, False))
check("the reason of an ssh failure is ssh's own line",
      qe._reason("git@github.com: Permission denied (publickey).\nfatal: Could not read from remote "
                 "repository.\n\nPlease make sure you have the correct access rights\nand the "
                 "repository exists."), "git@github.com: Permission denied (publickey).")
code, out = call("/api/preview", {"rows": table["rows"], "layout": None, "base": HEAD0})
check("a preview without origin: 502, said in the page's words with git's below",
      (code, "получить не удалось" in out.get("error", ""),
       "does not appear to be a git repository" in out.get("git", "")), (502, True, True))
git(clone, "remote", "set-url", "origin", url)
pub._fetched = 0
code, out = call("/api/table")
check("main moved on: 503, restarting", (code, out.get("restarting")), (503, True))
for _ in range(50):
    if exits:
        break
    time.sleep(0.1)
check("and the editor asks to be restarted", exits, [qe.RESTART_CODE])

# --- main's engine moved on: a publish restarts the editor before checking anything --------------
git(clone, "checkout", "-q", "--detach", "refs/remotes/origin/main")   # what the entrypoint does
pub.restarting = False
del exits[:]
B9 = origin_head()
code, out = call("/api/preview", {"rows": as_js(rows_at(B9)), "layout": None, "base": B9})
check("a checkout of origin's main previews as usual", (code, out.get("nothing")), (200, True))
git(other, "fetch", "-q", "origin")
git(other, "reset", "-q", "--hard", "origin/main")
os.makedirs(os.path.join(other, "server"), exist_ok=True)
with open(os.path.join(other, "server", "new_check.py"), "w", encoding="utf-8") as fh:
    fh.write("# a check main's table now needs\n")
git(other, "add", "-A")
git(other, "commit", "-q", "-m", "engine")
git(other, "push", "-q", "origin", "main")
E1 = origin_head()
page = as_js(rows_at(E1))
renamed(page, X, "Икс после нового кода")
code, out = call("/api/publish", {"rows": page, "layout": None, "base": E1})
check("main's engine moved on: the publish answers 503 restarting, nothing pushed",
      (code, out.get("restarting"), origin_head()), (503, True, E1))
for _ in range(50):
    if exits:
        break
    time.sleep(0.1)
check("and the editor asks to be restarted on it", exits, [qe.RESTART_CODE])
code, out = call("/api/preview", {"rows": page, "layout": None, "base": E1})
check("until then a preview is 503 restarting too", (code, out.get("restarting")), (503, True))
check("the engine's own files count, the table and the layout do not",
      (pub.engine_moved(E1), pub.engine_moved("HEAD")), (["server/new_check.py"], []))

# --- the merge itself ----------------------------------------------------------------------------
a, b, c = {"type": 1, "name": "a"}, {"type": 2, "name": "b"}, {"type": 3, "name": "c"}
rows, conf = qe.merge_rows([a, b], [b, dict(a, name="A")], [a, b, c])
check("merge: head's order, then the page's new ones", ([r["type"] for r in rows], conf), ([2, 1, 3], []))
rows, conf = qe.merge_rows([a, b], [a, b], [b])
check("merge: the page's deletion", [r["type"] for r in rows], [2])
rows, conf = qe.merge_rows([a], [a, dict(c, name="x")], [a, dict(c, name="y")])
check("merge: the same new number on both sides is a conflict",
      ([r["name"] for r in rows], [x["type"] for x in conf]), (["a", "x"], [3]))
check("merge_layout: a position the page did not move keeps main's",
      qe.merge_layout({"positions": {"1": [0, 0], "2": [5, 5]}},
                      {"positions": {"1": [7, 7], "2": [5, 5]}, "zoom": 1},
                      {"positions": {"1": {"x": 0, "y": 0}, "2": {"x": 9.6, "y": 5}, "4": {"x": 1, "y": 1}}},
                      {1, 2}),
      {"zoom": 1, "positions": {"1": [7, 7], "2": [10, 5]}})
check("merge_layout: where base had no place, the page's own layout leaves main's be "
      "and places only what main has no place for",
      qe.merge_layout({}, {"positions": {"1": [7, 7]}},
                      {"positions": {"1": {"x": 0, "y": 0}, "2": {"x": 3, "y": 3}}}, {1, 2}),
      {"positions": {"1": [7, 7], "2": [3, 3]}})
d = {"type": 4, "name": "d", "need_quest": 3, "need_any": [3, 1], "excludes": [3]}
e = {"type": 9, "name": "e", "need_quest": 3}
rows, moved = qe.renumber_new([a, e], [a, e, dict(c, name="x")], [a, e, dict(c, name="y"), d], taken={5000})
check("renumber_new: the page's new #3, which main took meanwhile, goes out as the first free "
      "number; links to it move along; a row the page left as it was is left alone",
      (moved, [r["type"] for r in rows], rows[3], rows[1]),
      ({3: 5001}, [1, 9, 5001, 4], dict(d, need_quest=5001, need_any=[5001, 1], excludes=[5001]), e))
check("renumber_new: the same new quest on both sides is no clash",
      qe.renumber_new([a], [a, c], [a, c]), ([a, c], {}))

srv.shutdown()
shutil.rmtree(TMP, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("quest publish OK")
