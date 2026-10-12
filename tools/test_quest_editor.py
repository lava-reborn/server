"""The quest editor's server half (tools/quest_editor.py), without a browser.

  * the table is written back byte for byte as it was read, line endings
    included, so a save diffs only what was edited;
  * the real table has no error, as the editor checks it;
  * a new quest gets a free type the original has no texts for, and makes a
    quest the engine accepts;
  * a save writes an edited row in place, a key it did not have where the
    table puts that key, and leaves every other row as it was; it refuses a
    table with an error (422) and a file that moved since it was read (409,
    unless forced);
  * over HTTP: the table, the checks, a row's texts as a player reads them,
    a new row; a save is refused when it comes as anything but JSON (what
    another site may post unasked), under a name other than 127.0.0.1 or
    localhost (DNS rebinding), or with a row key that is no plain name; a
    key is escaped when written all the same.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import quest_editor as qe  # noqa: E402
import quests  # noqa: E402

fails = []


def check(what, got, want):
    if got == want:
        print("ok   ", what)
    else:
        print("FAIL ", what, "\n      got: %r\n     want: %r" % (got, want))
        fails.append(what)


# --- the file ---------------------------------------------------------------
cur = qe.read_table()
with open(qe.TABLE, "rb") as fh:
    raw = fh.read().decode("utf-8")
check("the table is written back byte for byte (LF)",
      qe.dumps_table(cur["doc"]) == raw.replace("\r\n", "\n"), True)

rows = cur["doc"]["quests"]
found = qe.check(rows)
check("the real table has no error", [p for p in found if p["level"] == "error"], [])
check("an engine word has its Russian", qe.say_ru("quest 5: unknown kind 'x'"),
      "неизвестный вид задания «x»")

# --- a new quest ----------------------------------------------------------------
fresh = qe.new_row("kill_mobs", rows)
used = qe.taken_types(rows)
check("a new quest's type is free and in the editor's range",
      (qe.NEW_TYPES_FROM <= fresh["type"] <= qe.NEW_TYPES_TO, fresh["type"] in used),
      (True, False))
check("the engine accepts it", quests.Quest(fresh).kind, "kill_mobs")
check("it has every key every row has",
      [k for k in qe.CORE_KEYS if k not in fresh], [])
second = qe.new_row("del_obj", rows + [fresh])
check("the next one takes the next free type", second["type"] > fresh["type"], True)

# --- saving, on a copy ----------------------------------------------------------
tmp = tempfile.mkdtemp(prefix="quest-editor-")
path = os.path.join(tmp, "quests.json")
layout_path = os.path.join(tmp, "quest_layout.json")
# CRLF on purpose: a Windows checkout has it, and the save must keep it
with open(path, "wb") as fh:
    fh.write(raw.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
copy = qe.read_table(path)

edited = json.loads(json.dumps(copy["doc"]["quests"]))
victim = next(r for r in edited if "per_day" not in r and r["kind"] == "del_obj"
              and r.get("repeatable"))
victim["name"] = victim["name"] + " (правка)"
victim["per_day"] = 2
code, out = qe.save(edited, {"positions": {}}, copy["sha"], path=path, layout_path=layout_path)
check("a save of a good table is done", code, 200)
after = qe.read_table(path)
check("the line endings stay", after["eol"], "\r\n")
by_type = {r["type"]: r for r in after["doc"]["quests"]}
check("the edited row is written", by_type[victim["type"]]["name"], victim["name"])
keys = list(by_type[victim["type"]])
order = qe.key_order(rows)
prev = [k for k in order[:order.index("per_day")] if k in keys]
check("a new key stands where the table puts it",
      keys.index("per_day") == keys.index(prev[-1]) + 1, True)
others = [r for r in after["doc"]["quests"] if r["type"] != victim["type"]]
check("every other row is as it was",
      others == [r for r in rows if r["type"] != victim["type"]], True)
check("the layout is written beside", os.path.isfile(layout_path), True)
qe.write_layout({"positions": {"12": {"x": 10.4, "y": -3.6}, "4": {"x": 0, "y": 5}}}, layout_path)
with open(layout_path, encoding="utf-8") as fh:
    lines = fh.read().splitlines()
check("one line a quest, whole pixels, in type order",
      [l.strip() for l in lines if l.strip().startswith('"') and "[" in l],
      ['"4": [0, 5],', '"12": [10, -4]'])
check("and it reads back as the page wants it",
      qe.read_layout(layout_path)["positions"], {"4": {"x": 0, "y": 5}, "12": {"x": 10, "y": -4}})

# What the page sends back is JavaScript's: one kind of number, so a chance
# of 1.0 arrives as 1. Saved unchanged, the file must stay as it was.


def as_js(v):
    if isinstance(v, dict):
        return {k: as_js(x) for k, x in v.items()}
    if isinstance(v, list):
        return [as_js(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


js_rows = as_js(after["doc"]["quests"])
check("the test does turn a 1.0 into a 1", json.dumps(js_rows) != json.dumps(after["doc"]["quests"]),
      True)
code, out = qe.save(js_rows, None, after["sha"], path=path)
check("rows that went through the page are written byte for byte as they were",
      (code, qe.read_table(path)["sha"]), (200, after["sha"]))
fresh_slot = {"obj": 1, "num": 1, "mobs": [14], "drop": 1}
check("a new chance is written as a fraction",
      qe.as_written({"objs": [fresh_slot]}, None)["objs"][0]["drop"], 1.0)
after = qe.read_table(path)

bad = json.loads(json.dumps(after["doc"]["quests"]))
bad[0]["kind"] = "dance"
code, out = qe.save(bad, None, after["sha"], path=path)
check("a table with an error is refused", (code, out.get("problems", [{}])[0].get("type")),
      (422, bad[0]["type"]))
check("and the file is untouched", qe.read_table(path)["sha"], after["sha"])

code, out = qe.save(after["doc"]["quests"], None, copy["sha"], path=path)
check("a file that moved since it was read is not written over", code, 409)
code, out = qe.save(after["doc"]["quests"], None, copy["sha"], force=True, path=path)
check("unless the page says to", code, 200)
shutil.rmtree(tmp)

# --- over HTTP ------------------------------------------------------------------
srv = qe.serve(0)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def call(url, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, url), data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


table = call("/api/table")
check("GET /api/table: the hand rows and the generated ones",
      (len(table["rows"]), sorted(g["source"] for g in table["generated"])),
      (len(rows), sorted(os.path.basename(p) for p in quests.companion_paths(quests.PATH))))
import travel  # noqa: E402
ways = sorted(int(r["type"]) for r in rows if travel.is_quest_way(r["type"]))
check("GET /api/table: the rides, as the game knows them (the «суточные» filter leaves them out)",
      (table["ways"], len(ways) > 0), (ways, True))
probs = call("/api/check", {"rows": table["rows"]})["problems"]
check("POST /api/check: no error", [p for p in probs if p["level"] == "error"], [])
some = next(r for r in rows if quests.original_texts(r["type"]).get("start"))
shown = call("/api/texts", {"row": some})["shown"]
check("POST /api/texts: what the server serves",
      tuple(shown[k] for k in quests.TEXT_KEYS), quests.QUESTS[some["type"]].texts)
made = call("/api/new", {"kind": "bring_l_obj", "rows": table["rows"]})["row"]
check("POST /api/new: a bring quest with its objects", (made["kind"], made["objs"]),
      ("bring_l_obj", []))


def raw_call(url, body=None, headers=None):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, url), data=body,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# What another site open in the same browser could try while the editor
# runs: on a copy of the table, never the worktree's.
tmp = tempfile.mkdtemp(prefix="quest-editor-http-")
real = qe.TABLE, qe.LAYOUT
qe.TABLE, qe.LAYOUT = os.path.join(tmp, "quests.json"), os.path.join(tmp, "quest_layout.json")
shutil.copyfile(real[0], qe.TABLE)
before = qe.read_table()["sha"]
forced = json.dumps({"rows": table["rows"], "force": True}).encode("utf-8")
code, _ = raw_call("/api/save", forced, {"Content-Type": "text/plain;charset=UTF-8"})
check("a save sent as text/plain (a form another site may post unasked) is refused",
      (code, qe.read_table()["sha"]), (415, before))
code, _ = raw_call("/api/save", forced, {"Content-Type": "application/json",
                                         "Host": "evil.example:%d" % port})
check("so is one under another site's name (DNS rebinding)", (code, qe.read_table()["sha"]),
      (403, before))
check("and a read under that name", raw_call("/api/table", headers={"Host": "evil.example:%d" % port})[0],
      403)
for key in ('x": 1, "kind": "dance', "a\nb", "имя"):
    bad = json.loads(json.dumps(table["rows"]))
    bad[0][key] = 0
    code, _ = raw_call("/api/save", json.dumps({"rows": bad, "force": True}).encode("utf-8"),
                       {"Content-Type": "application/json"})
    check("a row key %r is refused (400), the file untouched" % key, (code, qe.read_table()["sha"]),
          (400, before))
code, out = raw_call("/api/save", forced, {"Content-Type": "application/json; charset=utf-8",
                                           "Host": "localhost:%d" % port})
check("JSON under localhost is saved", (code, json.loads(out.decode("utf-8")).get("ok")), (200, True))
qe.TABLE, qe.LAYOUT = real
shutil.rmtree(tmp)
check("dumps_row escapes a key all the same",
      json.loads(qe.dumps_row({"type": 1, 'a"b\nc': 2})), {"type": 1, 'a"b\nc': 2})
check("and writes a plain one as it always did", qe.dumps_row({"type": 1, "name": "x"}),
      '    {\n      "type": 1,\n      "name": "x"\n    }')
check("so does dumps_layout", qe.dumps_layout({"positions": {"7": [1, 2]}}),
      '{\n  "positions": {\n    "7": [1, 2]\n  }\n}\n')
srv.shutdown()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("quest editor OK")
