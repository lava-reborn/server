"""The quest table's checks, all at once, and the texts as a player reads them.

What the quest editor (tools/quest_editor) stands on, held to here without it:

  * check_rows finds every problem of a table in one pass, in the order load
    meets them -- a row that makes no quest, a type listed twice, a
    prerequisite or an exclusion the table does not have, a ring, an
    exclusion of what the quest needs -- and load still raises the first,
    as it was found;
  * item_problems tells every thing a table names wrong, and check_items
    still raises the first of them;
  * player_texts gives, for every row of the real table, exactly the texts
    the server serves for it (the original laid over, the daily note, the
    boss hours), so that what the editor previews is what a player reads.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import quests  # noqa: E402

fails = []


def check(what, got, want):
    if got == want:
        print("ok   ", what)
    else:
        print("FAIL ", what, "\n      got: %r\n     want: %r" % (got, want))
        fails.append(what)


ROWS = quests.table_rows()

# --- the real table ---------------------------------------------------------
table, found = quests.check_rows(ROWS)
check("the real table has no problem", [str(e) for e in found], [])
check("check_rows makes the quests load makes", list(table), list(quests.load()))
check("item_problems has nothing to say of it", quests.item_problems(table), [])

# --- a table with one of each problem ---------------------------------------


def row(t, **kw):
    out = {"type": t, "kind": "del_obj", "name": "Проверка %d" % t}
    out.update(kw)
    return out


BROKEN = [
    row(90001),
    row(90002, kind="dance"),                       # no such kind
    row(90003, per_day=1),                          # per_day on a one-off
    row(90001),                                     # 90001 twice
    row(90004, need_quest=90099),                   # a prerequisite not there
    row(90005, need_quest=90006),                   # a ring: 90005 <-> 90006
    row(90006, need_quest=90005),
    row(90007, excludes=[90098]),                   # an exclusion not there
    row(90008, need_quest=90001, excludes=[90001]),  # excludes what it needs
]
got, problems = quests.check_rows(BROKEN)
words = [str(e) for e in problems]
check("every problem is told, in load's order", words, [
    "quest 90002: unknown kind 'dance'",
    "quest 90003: per_day is for a repeatable quest, at least 1",
    "quest type 90001 listed twice",
    "quest 90004 needs [90099], which the table does not have",
    "quest 90005 needs itself through its chain",
    "quest 90006 needs itself through its chain",
    "quest 90007 excludes [90098], which the table does not have",
    "quest 90008 excludes what it needs ([90001]): it would never be offered",
])
check("the rows that make a quest are still made", sorted(got),
      [90001, 90004, 90005, 90006, 90007, 90008])

# load raises the first, as before the checks were gathered

import json  # noqa: E402
import tempfile  # noqa: E402
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
    json.dump({"quests": BROKEN}, fh, ensure_ascii=False)
    broken_path = fh.name
try:
    quests.load(broken_path)
    raised = None
except ValueError as exc:
    raised = str(exc)
os.unlink(broken_path)

check("load raises the first problem", raised, words[0])

# --- items --------------------------------------------------------------------
import items  # noqa: E402,F401  -- what item_problems asks, read before it does

probe = dict(table)
probe[90010] = quests.Quest(row(90010, rew_also=[{"obj": 99999999, "num": 1}],
                                start_obj=[{"obj": 99999998, "num": 1}]))
told = quests.item_problems(probe)
check("an unknown reward and an unknown hand-over are one word for the quest",
      [w for w in told if w.startswith("quest 90010 ")],
      ["quest 90010 names things the game does not have: rew_also 99999999,"
       " start_obj 99999998"])
try:
    quests.check_items(probe)
    raised = None
except ValueError as exc:
    raised = str(exc)
check("check_items raises the first of them", raised, told[0])

# --- texts as a player reads them -------------------------------------------
differ = []
for r in ROWS:
    want = quests.QUESTS[int(r["type"])].texts
    got = tuple(quests.player_texts(r)[k] for k in quests.TEXT_KEYS)
    if got != want:
        differ.append(int(r["type"]))
check("player_texts is what the server serves, for all %d rows" % len(ROWS), differ, [])

daily = row(90020, repeatable=1, per_day=1, start="Принеси воды.<Br>")
check("a daily row's start gets the original's note",
      quests.player_texts(daily)["start"],
      "Принеси воды." + quests.PER_DAY_NOTE % "1 раза")

laid = next(r for r in ROWS if quests.original_texts(r["type"]).get("start")
            and "start" not in (r.get("own_texts") or []))
mine = dict(laid, start="Свой текст", own_texts=["start"])
check("the original's start is laid over the row's unless own_texts keeps it",
      (quests.player_texts(dict(laid, start="Свой текст"))["start"]
       == quests.QUESTS[laid["type"]].texts[quests.START],
       quests.player_texts(mine)["start"].startswith("Свой текст")),
      (True, True))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("quest checks OK")
