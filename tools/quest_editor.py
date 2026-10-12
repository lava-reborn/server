#!/usr/bin/env python3
"""The quest editor: the quest table as a graph, every field of a row, the
engine's own checks, and data/quests.json written the way it is written.

    python3 tools/quest_editor.py [--port 8095] [--no-browser]

Opens a page on 127.0.0.1:8095 (LAVA_QUEST_EDITOR_PORT). Quests are nodes; a
prerequisite (need_quest), one of several (need_any) and the other branch of
a choice (excludes) are edges, drawn by dragging from one quest to another.
Clicking a quest opens every field of its row: the four texts with what a
player will read in their place, who hands it out and who takes it, what it
asks for, what it pays, what it costs, what it hands over at the take and
when it is offered. Every change is checked by the table's own checks
(quests.check_rows, quests.item_problems) as it is made, and "Сохранить"
refuses a table the server would refuse to start on.

The page is a React Flow application built once (tools/quest_editor_ui:
`bash tools/quest_editor_ui/build.sh`); its output, static/, is in the
repository, so running the editor needs Python and the game's res folder,
not Node.

What is written, and what is not:

  * data/quests.json, row by row, in the file's own layout (dumps_row: the
    keys in their order, scalar lists and a bring quest's objects on one
    line), with the line endings the file had. A row the page did not
    change is written as it was read, so a save diffs only what was edited.
  * data/quest_layout.json, where the quests stand on the page. The server
    never reads it.
  * Not the generated tables (data/questgen_*.json): their builders write
    them by the hundred and would write over a hand's change, so the page
    shows them and does not edit them. They are checked with the rest,
    because load reads them with the rest.

Nothing here touches a running game. Going live is a commit: on a branch,
merged to main when the owner says so (README «CI/CD»: a push to main is a
deploy), and the client release that deploy builds carries the new texts.

A save is refused when data/quests.json changed on disk since the page read
it -- another editor, another session, a merge -- unless the page says to
write over it; a table with an error the server would stop on is refused
always. Locally the editor answers under 127.0.0.1 and localhost only and
reads JSON bodies only, so another site open in the same browser can
neither post to /api/save nor rebind its own name to this port.

Publish mode, for the admin panel (lava-admin runs this in a container of
its own and shows the page at /admin/quests):

    python3 DIR/tools/quest_editor.py --repo DIR [--branch main] --host 0.0.0.0

DIR is a git clone whose origin is the source of truth (lvrbrn/server); the
editor runs from it and reads its data/. Nothing is written to disk there:
"Опубликовать" merges the page's rows onto a fresh origin/<branch> quest by
quest (Publisher.prepare), checks the result, builds the commit in an index
of its own and pushes it straight to the branch -- for main that is a deploy
(CI tests it and rolls it out). When origin moves, the next page load is
answered 503 and the process exits with RESTART_CODE: the container's
entrypoint checks the new commit out and starts the editor again from it.
A preview or a publish does the same when origin's engine (ENGINE: the
server's code, the tables beside the quest table, this file) is not the
checkout's: the merged table is checked by main's own code.
"""
import argparse
import datetime
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault("LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res")
if not os.environ.get("LAVA_ORIG_TEXTS"):
    for _candidate in (os.path.join(os.environ["LAVA_RES"], "xml", "texts.xml"),
                       "/mnt/c/Users/gmkrt/Downloads/texts.xml"):
        if os.path.isfile(_candidate):
            os.environ["LAVA_ORIG_TEXTS"] = _candidate
            break

import quests  # noqa: E402
import items   # noqa: E402  -- item_problems asks it; read once, here
import mobs    # noqa: E402
import names   # noqa: E402
import travel  # noqa: E402  -- which quests are rides (way_types)
import world   # noqa: E402

PORT = int(os.environ.get("LAVA_QUEST_EDITOR_PORT", "8095"))
TABLE = os.path.join(ROOT, "data", "quests.json")
LAYOUT = os.path.join(ROOT, "data", "quest_layout.json")
UI = os.path.join(HERE, "quest_editor_ui", "static")
# Item icons, as the admin panel extracted them from the client
# (lava-admin/tools/build_catalog.py): its catalog names each type's icon,
# static/icons holds the pictures. Optional: without it the page shows a
# category glyph instead.
ADMIN = os.environ.get("LAVA_ADMIN_DIR") or next(
    (p for p in (os.path.join(os.path.dirname(ROOT), "lava-admin"),
                 "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-admin")
     if os.path.isfile(os.path.join(p, "catalog.json"))),
    os.path.join(os.path.dirname(ROOT), "lava-admin"))
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "lava-quest-editor")

# Where a new quest's type comes from: the first free one from here on. Below
# 3000 sit the hand rows and the original's quests (4..2128), from 10000 the
# generated families; a type the original has would get the original's texts
# laid over whatever the page writes (quests._lay), so those are never given.
NEW_TYPES_FROM = 5000
NEW_TYPES_TO = 9999

# Keys every row has (the table's own convention, held to by the page).
CORE_KEYS = ("type", "kind", "name", "start", "give", "take", "rew_afro", "rew_gold",
             "repeatable", "level", "q_type")


# --- the table file ---------------------------------------------------------

def dumps_row(row):
    """One quest as the table writes it: keys in order, scalar lists and the
    objects of a bring quest on one line, the way the hand-written rows were
    laid out (the same as data/build_quests_start.py's)."""
    out = []
    for key, value in row.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            body = ",\n".join("        " + json.dumps(o, ensure_ascii=False) for o in value)
            text = "[\n" + body + "\n      ]"
        else:
            text = json.dumps(value, ensure_ascii=False)
        # json.dumps for the key too: a plain name comes out as "name", the
        # same bytes; anything else is escaped, never written raw
        out.append('      %s: %s' % (json.dumps(key, ensure_ascii=False), text))
    return "    {\n" + ",\n".join(out) + "\n    }"


def dumps_table(doc):
    """The whole file, LF: the head keys, then the rows (dumps_row)."""
    head = ",\n".join("  %s: %s" % (json.dumps(k, ensure_ascii=False),
                                     json.dumps(v, ensure_ascii=False))
                      for k, v in doc.items() if k != "quests")
    rows = ",\n".join(dumps_row(r) for r in doc["quests"])
    return "{\n" + head + (",\n" if head else "") + '  "quests": [\n' + rows + "\n  ]\n}\n"


def read_table(path=None):
    """{doc, eol, sha}: the parsed file, its line ending, and the hash of its
    bytes as they are on disk (what a save is checked against)."""
    path = path or TABLE
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    return {"doc": json.loads(text), "eol": eol, "sha": hashlib.sha256(raw).hexdigest()}


def write_table(doc, eol, path=None):
    path = path or TABLE
    text = dumps_table(doc)
    if eol != "\n":
        text = text.replace("\n", eol)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(text.encode("utf-8"))
    os.replace(tmp, path)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generated(path=None):
    """[{source, rows}] of the generated tables beside the real one: the
    server's own (quests.companion_paths), or, in publish mode, the ones
    beside the checkout's table, found the same way."""
    path = path or TABLE
    if os.path.abspath(path) == os.path.abspath(quests.PATH):
        paths = quests.companion_paths(path)
    elif os.path.abspath(path) == os.path.abspath(TABLE):
        here = os.path.dirname(path)
        paths = [os.path.join(here, f) for f in sorted(os.listdir(here))
                 if f.startswith("questgen_") and f.endswith(".json")]
    else:
        return []
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            out.append({"source": os.path.basename(p), "rows": json.load(fh)["quests"]})
    return out


def way_types(rows):
    """The types data/passages.json makes rides (travel.is_quest_way). The
    game counts them apart from the day's tasks (server.py
    Session.counts_daily), and so does the page's «суточные» filter: a
    repeatable quest that is neither a service nor one of these."""
    return sorted(int(r["type"]) for r in rows if travel.is_quest_way(r["type"]))


def key_order(rows):
    """The table's own order of keys: each key by where it stands on average.
    A key a row did not have before goes where the table puts it."""
    pos = {}
    for r in rows:
        keys = list(r)
        for i, k in enumerate(keys):
            pos.setdefault(k, []).append(i / max(1, len(keys) - 1))
    return sorted(pos, key=lambda k: sum(pos[k]) / len(pos[k]))


# Keys whose values are chances, written as fractions whatever arrives.
FLOAT_KEYS = ("drop",)


def as_written(new, old):
    """new, with every number that did not change written as old wrote it.

    The page is JavaScript, which has one kind of number: a slot's "drop":
    1.0 comes back as 1, and a save would rewrite every such line of the
    table though nobody touched it. So a value equal to what the row had
    keeps the row's own form, and a chance is a fraction however it came."""
    if isinstance(new, dict):
        out = {}
        for k, v in new.items():
            v = as_written(v, old.get(k) if isinstance(old, dict) else None)
            if k in FLOAT_KEYS and isinstance(v, int) and not isinstance(v, bool):
                v = float(v)
            out[k] = v
        return out
    if isinstance(new, list):
        olds = old if isinstance(old, list) and len(old) == len(new) else [None] * len(new)
        return [as_written(v, o) for v, o in zip(new, olds)]
    if (isinstance(new, int) and not isinstance(new, bool) and isinstance(old, float)
            and float(new) == old):
        return old
    return new


def ordered(row, before, order):
    """row with its keys in a stable order: the keys it had before where they
    were, then new ones where the table puts them, then any the table never
    had, in the order given."""
    keys = [k for k in (before or {}) if k in row]
    rest = [k for k in row if k not in keys]
    rank = {k: i for i, k in enumerate(order)}
    known = sorted((k for k in rest if k in rank), key=rank.get)
    keys += known + [k for k in rest if k not in rank]
    if before:
        # A new key goes right after its nearest predecessor in the table's
        # order, not at the end: a row keeps reading the way the others do.
        for k in known:
            keys.remove(k)
            prev = [p for p in order[:rank[k]] if p in keys]
            at = keys.index(prev[-1]) + 1 if prev else 0
            keys.insert(at, k)
    return {k: row[k] for k in keys}


# --- checks -------------------------------------------------------------------

_TYPE_IN = re.compile(r"quest(?: type)? (\d+)")

# The engine's words, in the page's language. Each pattern is one raise of
# quests.py; one the table does not know is shown as the engine said it.
RU = [
    (r"unknown kind '(.*)'", "неизвестный вид задания «%s»"),
    (r"own_texts names no text (.*)", "own_texts называет несуществующие тексты %s"),
    (r"rew_also pieces must be positive", "в «Ещё выдаётся» количество должно быть больше нуля"),
    (r"needs itself through its chain", "цепочка замыкается сама на себя"),
    (r"needs itself", "квест требует сам себя"),
    (r"excludes itself", "квест исключает сам себя"),
    (r"per_day is for a repeatable quest", "«Раз в сутки» только для повторяемого квеста"),
    (r"cooldown is for a repeatable quest", "Перерыв только для повторяемого квеста"),
    (r"start_obj pieces must be positive", "в выдаче при взятии количество должно быть больше нуля"),
    (r"stay_in keeps what is lent, and it lends nothing",
     "«Только в локациях» имеет смысл, только если квест что-то даёт на время"),
    (r"rew_xp names no skill (.*)", "опыт в несуществующий навык %s"),
    (r"rew_spec_xp/requires_spec name no specialisation (.*)", "несуществующая специализация %s"),
    (r"a fee cannot be negative", "комиссия не может быть отрицательной"),
    (r"rew_random pieces and weights must be positive",
     "в лотерее количество и вес должны быть больше нуля"),
    (r"num_kill must match mobs_kill", "у каждой цели «убить» должно быть число"),
    (r"kill_also must count for a slot of mobs_kill",
     "«Засчитывать также» должно указывать на цель из списка «убить»"),
    (r"at most (\d+) objects", "не больше %s предметов в «Принести»"),
    (r"a slot's drop is a chance in \(0, 1\] and needs its mobs",
     "шанс выпадения — от 0 до 1, и нужны мобы, с которых он падает"),
    (r"complete_skills names an unknown skill", "условие по неизвестному навыку"),
    (r"complete_skills needs a talk and levels 1..20",
     "условие по навыкам — только для разговора без предмета, уровни 1..20"),
    (r"listed twice", "этот номер квеста встречается дважды"),
    (r"needs (\[.*\]), which the table does not have", "требует квесты %s, которых нет в таблице"),
    (r"excludes (\[.*\]), which the table does not have", "исключает квесты %s, которых нет в таблице"),
    (r"excludes what it needs \((.*)\): it would never be offered",
     "исключает то, что сам требует (%s): его никому не предложат"),
    (r"names things the game does not have: (.*)", "таких предметов в игре нет: %s"),
    (r"names premium things, out of the game: (.*)", "премиум-предметы выведены из игры: %s"),
    (r"lends what a stall sells: (.*)", "даёт на время то, что продаётся в лавке: %s"),
    (r"hands over what is worth something away from it: (.*) \(",
     "при взятии выдаёт то, что ценно вне квеста: %s"),
]


def say_ru(text):
    for pattern, ru in RU:
        m = re.search(pattern, text)
        if m:
            return ru % m.groups() if "%s" in ru else ru
    return text


def problem(text, level="error"):
    m = _TYPE_IN.search(text)
    return {"type": int(m.group(1)) if m else None, "level": level,
            "text": text, "ru": say_ru(text)}


def warnings(rows, places):
    """What the server lets through and a quest writer would want to know:
    nobody to take it from or hand it to, an NPC standing nowhere, a goal
    left empty. places is refs()'s where: type -> [location]."""
    out = []
    for r in rows:
        t = r.get("type")
        if not r.get("name"):
            out.append({"type": t, "level": "warn", "text": "", "ru": "у задания нет названия"})
        if not r.get("give") and not r.get("take"):
            out.append({"type": t, "level": "warn", "text": "",
                        "ru": "выключено: никто не выдаёт и не принимает"})
        elif not r.get("give"):
            out.append({"type": t, "level": "warn", "text": "",
                        "ru": "никто не выдаёт: задание выключено"})
        elif not r.get("take"):
            out.append({"type": t, "level": "warn", "text": "", "ru": "некому сдать"})
        for side, who in (("выдаёт", r.get("give") or []), ("принимает", r.get("take") or [])):
            for npc in who:
                if places is not None and not places.get(int(npc)):
                    out.append({"type": t, "level": "warn", "text": "",
                                "ru": "%s %s, а он не стоит ни в одной локации"
                                      % (side, npc_label(int(npc)))})
        kind = r.get("kind")
        if kind == quests.KILL_MOBS and not r.get("mobs_kill"):
            out.append({"type": t, "level": "warn", "text": "", "ru": "«Убить», но цели не заданы"})
        if kind == quests.BRING_L_OBJ and not r.get("objs"):
            out.append({"type": t, "level": "warn", "text": "",
                        "ru": "«Принести», но предметы не заданы"})
    return out


def check(rows, places=None, gen=None):
    """Every problem of the hand rows given, read with the generated tables
    (those on disk, or gen: generated()'s shape, a commit's), as load and
    check_items would meet them, and the warnings."""
    every = list(rows)
    for g in (generated() if gen is None else gen):
        every += g["rows"]
    table, found = quests.check_rows(every)
    out = [problem(str(e)) for e in found]
    out += [problem(m) for m in quests.item_problems(table)]
    return out + warnings(rows, places)


def texts(row):
    """What a player reads for a row, and the original's own texts, where
    the original has them (quests.player_texts, quests.original_texts)."""
    try:
        shown, error = quests.player_texts(row), None
    except (ValueError, KeyError, TypeError) as exc:
        shown, error = None, say_ru(str(exc))
    return {"shown": shown, "original": quests.original_texts(row.get("type") or 0),
            "error": error}


# --- reference data -------------------------------------------------------------

_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def split_name(text):
    """A name as the client draws it, in two parts: "Наби ал-Асад<br>Лекарь"
    is the name and, under it, what the creature does; an item's
    "Наган$ПИСТОЛЕТ" is its name and the sub-name the client cuts off at
    the dollar."""
    text = (text or "").split("$", 1)[0]
    parts = [re.sub(r"<[^>]+>", "", p).strip() for p in _BREAK.split(text)]
    parts = [p for p in parts if p]
    return (parts[0] if parts else ""), " · ".join(parts[1:])


def npc_label(type_id):
    return "%s [%d]" % (split_name(names.text(type_id))[0], type_id)


def _icons():
    try:
        with open(os.path.join(ADMIN, "catalog.json"), encoding="utf-8") as fh:
            cat = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {int(i["id"]): i.get("icon") or "" for i in cat.get("items", [])}


def _static_ids():
    """The original's static locations and ours (data/locations), as the
    server reads them (world.static_ids)."""
    return world.static_ids()


def _scan(ids):
    """{"where": type -> sorted locations it stands in, "titles": location ->
    title}, from the location files; cached on disk by the files' count and
    newest change, because the scan reads 1381 files and takes a dozen
    seconds over /mnt/c."""
    try:
        stamp = "%d-%d" % (len(ids), int(max(os.path.getmtime(world.static_path(i))
                                              for i in ids)) if ids else 0)
    except (OSError, TypeError):
        stamp = "none"
    key = hashlib.sha256((world.RES + world.OVERLAY + stamp).encode()).hexdigest()[:16]
    cached = os.path.join(CACHE, "scan-%s.json" % key)
    try:
        with open(cached, encoding="utf-8") as fh:
            doc = json.load(fh)
        return {"where": {int(k): v for k, v in doc["where"].items()},
                "titles": {int(k): v for k, v in doc["titles"].items()}}
    except (OSError, ValueError, KeyError):
        pass
    where, titles = {}, {}
    for i in ids:
        try:
            loc = world.location(i)
        except Exception:                  # noqa: BLE001 -- a broken file is no place
            continue
        titles[i] = loc.title
        for _cell, t in loc.spawns:
            where.setdefault(t, set()).add(i)
    out = {"where": {t: sorted(v) for t, v in where.items()}, "titles": titles}
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(cached, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
    except OSError:
        pass
    return out


def current_where():
    """refs()'s where if the scan is done, None while it is not: what a
    check uses, without waiting for the scan."""
    r = _REFS
    return r.get("where") if r else None


_REFS = None
_REFS_LOCK = threading.Lock()


def refs(scan=True):
    """What the page picks from: items (with icons, no premium ones),
    creatures (with levels and roles), the NPC classes that can hand out and
    take quests, locations, and where each creature stands."""
    global _REFS
    with _REFS_LOCK:
        if _REFS is not None and (_REFS["where"] is not None or not scan):
            return _REFS
        icons = _icons()
        item_rows = []
        for t in items.catalogue():
            if items.premium(t):
                continue
            si = items.params_of(t) or {}
            item_rows.append({"t": t, "n": split_name(names.text(items.STRING_ID_OFFSET + t))[0],
                              "r": items.root_of(t), "i": icons.get(t, ""),
                              "q": 1 if si.get("quest") else 0,
                              "c": int(si.get("cost", 0) or 0)})
        roots = world.mob_types()
        creatures = []
        for k, v in mobs.TYPES.items():
            t = int(k)
            n, sub = split_name(names.text(t))
            creatures.append({"t": t, "n": n, "sub": sub, "l": int(v.get("level") or 0),
                              "role": v.get("role") or "", "root": int(v.get("root") or 0)})
        known = {c["t"] for c in creatures}
        for t, (root, _internal, _art) in roots.items():
            if t not in known:
                n, sub = split_name(names.text(t))
                creatures.append({"t": t, "n": n, "sub": sub, "l": 0, "role": "",
                                  "root": int(root)})
        locations, where = [], None
        if scan:
            found = _scan(_static_ids())
            where = found["where"]
            locations = [{"id": i, "title": t} for i, t in sorted(found["titles"].items())]
            for loc_id, rows in world.placements().items():
                for row in rows:
                    where.setdefault(int(row["type"]), [])
                    if loc_id not in where[int(row["type"])]:
                        where[int(row["type"])].append(loc_id)
        _REFS = {"items": item_rows, "creatures": sorted(creatures, key=lambda c: c["t"]),
                 "locations": locations, "where": where,
                 "skills": list(quests.SKILL_KEYS), "specs": list(quests.SPEC_KEYS),
                 "kinds": list(quests.KINDS)}
        return _REFS


# --- new quests ---------------------------------------------------------------

def taken_types(rows):
    used = {int(r["type"]) for r in rows}
    for g in generated():
        used |= {int(r["type"]) for r in g["rows"]}
    import orig_texts
    used |= set(orig_texts.quests())
    return used


def new_row(kind, rows, order=None):
    """A fresh row of the kind, on the first free type from NEW_TYPES_FROM:
    every key every row has, the four texts, and a why that says where it
    came from (the table's own habit: every row says why it is the way it
    is)."""
    if kind not in quests.KINDS:
        raise ValueError("unknown kind %r" % kind)
    used = taken_types(rows)
    t = next((n for n in range(NEW_TYPES_FROM, NEW_TYPES_TO + 1) if n not in used), None)
    if t is None:
        raise ValueError("no free quest type left in %d..%d" % (NEW_TYPES_FROM, NEW_TYPES_TO))
    row = {"type": t, "kind": kind, "name": "Новое задание", "start": "",
           "notfinish": "", "finish": "", "give": [], "take": [],
           "rew_obj": [], "num_rew_obj": [], "rew_afro": 0, "rew_gold": 0,
           "repeatable": 0, "level": 0, "q_type": 0, "loc": 0, "finish_loc": 0,
           "why": "DESIGNED in the quest editor, %s." % datetime.date.today().isoformat()}
    if kind == quests.KILL_MOBS:
        row.update(mobs_kill=[], num_kill=[])
    elif kind == quests.BRING_L_OBJ:
        row.update(objs=[])
    return ordered(row, None, order or key_order(rows))


# --- saving -------------------------------------------------------------------

def save(rows, layout=None, base_sha=None, force=False, path=None, layout_path=None):
    """Write the hand rows, after the checks. Returns (status, body): 200 and
    the new hash, 409 when the file moved since base_sha (unless force),
    422 with the problems when the table has an error."""
    path = path or TABLE
    cur = read_table(path)
    if base_sha and cur["sha"] != base_sha and not force:
        return 409, {"error": "moved",
                     "ru": "data/quests.json изменился на диске после загрузки страницы"}
    errors = [p for p in check(rows) if p["level"] == "error"]
    if errors:
        return 422, {"error": "problems", "problems": errors}
    before = {int(r["type"]): r for r in cur["doc"]["quests"]}
    order = key_order(cur["doc"]["quests"])
    doc = dict(cur["doc"])
    doc["quests"] = [ordered(as_written(r, before.get(int(r["type"]))),
                             before.get(int(r["type"])), order) for r in rows]
    sha = write_table(doc, cur["eol"], path)
    if layout is not None:
        write_layout(layout, layout_path)
    return 200, {"ok": True, "sha": sha}


def dumps_layout(layout):
    """data/quest_layout.json's text: one line per quest, "type": [x, y] in
    whole pixels, so that moving one quest is a one-line change."""
    positions = layout.get("positions") or {}
    lines = []
    for k in sorted(positions, key=lambda s: int(s) if str(s).isdigit() else 0):
        p = positions[k]
        x, y = (p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1])
        lines.append('    %s: [%d, %d]' % (json.dumps(str(k), ensure_ascii=False), round(x), round(y)))
    rest = {k: v for k, v in layout.items() if k != "positions"}
    head = "".join('  %s: %s,\n' % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False))
                   for k, v in sorted(rest.items()))
    return ("{\n" + head + '  "positions": {\n' + ",\n".join(lines)
            + ("\n" if lines else "") + "  }\n}\n")


def write_layout(layout, path=None):
    """data/quest_layout.json, as dumps_layout writes it."""
    with open(path or LAYOUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps_layout(layout))


def diff(path=None):
    """The table against the last commit, as a unified diff of its rows."""
    path = path or TABLE
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    old = _git_show("HEAD:" + rel)
    with open(path, encoding="utf-8") as fh:
        new = fh.read()
    lines = difflib.unified_diff(old.replace("\r\n", "\n").splitlines(),
                                 new.replace("\r\n", "\n").splitlines(),
                                 "HEAD:" + rel, rel, lineterm="", n=2)
    return "\n".join(lines)


def _git_show(spec):
    """git show <spec> of the checkout, as text; "" when git cannot say.
    Under WSL a worktree made by Windows git names its .git with a C:/ path
    WSL's git cannot follow, so Windows git is asked then (git.exe)."""
    try:
        return subprocess.run(["git", "-C", ROOT, "show", spec], capture_output=True,
                              check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pass
    try:
        win = subprocess.run(["wslpath", "-w", ROOT], capture_output=True,
                             check=True).stdout.decode().strip()
        return subprocess.run(["git.exe", "-C", win, "show", spec], capture_output=True,
                              check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        return ""


def read_layout(path=None):
    """The layout as the page wants it: positions as {"x", "y"}."""
    try:
        with open(path or LAYOUT, encoding="utf-8") as fh:
            layout = json.load(fh)
    except (OSError, ValueError):
        return {}
    return page_layout(layout)


def page_layout(layout):
    """A layout as the file has it (positions as [x, y]) as the page wants it."""
    layout = dict(layout)
    pos = layout.get("positions") or {}
    layout["positions"] = {k: ({"x": v[0], "y": v[1]} if isinstance(v, list) else v)
                           for k, v in pos.items()}
    return layout


# --- publishing (publish mode) ----------------------------------------------------
#
# The admin panel's editor publishes straight to the branch: the page's rows
# are merged onto what origin has now, quest by quest, the result is checked
# as the server would check it, and the commit is made out of git objects
# alone (a temporary index), so the running checkout is never touched and two
# publishes never step on each other's files.

REL_TABLE = "data/quests.json"
REL_LAYOUT = "data/quest_layout.json"
FETCH_EVERY = 15          # seconds: a page load fetches at most this often
GIT_TIMEOUT = 60
PUSH_TIMEOUT = 120
PUSH_TRIES = 3            # a branch that moved between fetch and push: again
DEEPEN = 500              # a shallow clone's history, deepened once for a base
RESTART_CODE = 75         # the entrypoint checks out the new commit and restarts
_SHA = re.compile(r"^[0-9a-f]{7,64}$")
PUB = None                # the Publisher in publish mode, None in local mode
# What check() runs and reads: the engine's code, the tables beside the quest
# table, the editor itself. When origin's differ from the checkout's, the
# merged table would be checked by the old ones: the editor restarts first.
# The two files the page edits are merged, and never a reason to restart.
ENGINE = ("server", "data", "tools/quest_editor.py")

# What a 502 says above git's own words (in English, LC_ALL=C).
FETCH_FAILED = ("Свежий {branch} получить не удалось: GitHub не ответил или не пустил. "
                "Если так и останется, проверьте ключ развёртывания на сервере "
                "(README панели, раздел «Квесты»).")
PUSH_FAILED = ("GitHub не принял коммит, и в {branch} он не попал. Проверьте, что у ключа "
               "развёртывания есть право записи и что защита ветки {branch} его пропускает "
               "(README панели, раздел «Квесты»).")
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


def _trim(text, limit=600):
    lines = [l.strip() for l in (text or "").replace("\r", "\n").split("\n") if l.strip()]
    out = "\n".join(lines)
    return out if len(out) <= limit else "…" + out[-limit:]


# What git says after any failed fetch or clone, whatever the cause.
_GENERIC = ("could not read from remote repository", "please make sure you have the correct access",
            "and the repository exists")


def _reason(text, limit=200):
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


def plain_name(row, limit=50):
    """A row's name for a summary line: markup out, one line."""
    text = one_line(re.sub(r"<[^>]+>", " ", str((row or {}).get("name") or ""))) or "без названия"
    return text if len(text) <= limit else text[:limit - 1] + "…"


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


def merge_rows(base, head, mine):
    """Three-way merge of the hand rows by quest type: (rows, conflicts).

    A quest the page left as it was at base takes head's version, a deletion
    in head included; one head left as it was takes the page's, the page's
    deletion included; the same on both sides is that; anything else is a
    conflict, and head's version stays in the rows (so that what is checked
    and shown is a whole table). Order: head's, then the quests new on the
    page in the page's order."""
    b = {int(r["type"]): r for r in base}
    h = {int(r["type"]): r for r in head}
    m = {int(r["type"]): r for r in mine}
    out, conflicts = {}, []
    for t in dict.fromkeys(list(h) + list(m) + list(b)):
        bt, ht, mt = b.get(t), h.get(t), m.get(t)
        if mt == bt:
            got = ht
        elif ht == bt:
            got = mt
        elif mt == ht:
            got = mt
        else:
            if bt is None:
                why = "квест с этим номером появился и здесь, и в main"
            elif mt is None:
                why = "удалён здесь и изменён в main"
            elif ht is None:
                why = "изменён здесь и удалён в main"
            else:
                why = "изменён и здесь, и в main"
            conflicts.append({"type": t, "name": plain_name(mt or ht or bt), "ru": why})
            got = ht
        if got is not None:
            out[t] = got
    order = [t for t in h if t in out] + [t for t in m if t in out and t not in h]
    return [out[t] for t in order], conflicts


# The keys by which one row names another quest.
LINK_KEYS = ("need_quest", "need_any", "excludes")


def renumber_new(base, head, mine, taken=()):
    """(mine, {old: new}): every quest the page added under a number head has
    also taken meanwhile, with other content, moved to the first free number
    from NEW_TYPES_FROM, and the page's links to it moved along.

    /api/new hands out the first free number of the page's rows and main as
    last fetched; two pages that each add a quest before either publishes
    get the same one. Without this the second would be a conflict over a
    quest nobody else ever saw. taken: numbers no new quest may get (the
    generated tables', the original's). Rows the page left as they were at
    base are not touched."""
    b = {int(r["type"]): r for r in base}
    h = {int(r["type"]): r for r in head}
    clash = [int(r["type"]) for r in mine
             if int(r["type"]) not in b and int(r["type"]) in h and r != h[int(r["type"])]]
    if not clash:
        return mine, {}
    used = set(taken) | set(b) | set(h) | {int(r["type"]) for r in mine}
    moved = {}
    for t in clash:
        n = next((n for n in range(NEW_TYPES_FROM, NEW_TYPES_TO + 1) if n not in used), None)
        if n is None:
            break                  # no number left: it stays, and is a conflict
        used.add(n)
        moved[t] = n

    def along(v):
        if isinstance(v, list):
            return [along(x) for x in v]
        return moved.get(v, v) if isinstance(v, int) and not isinstance(v, bool) else v

    out = []
    for r in mine:
        t = int(r["type"])
        if b.get(t) == r:
            out.append(r)
            continue
        new = dict(r)
        if t in moved:
            new["type"] = moved[t]
        for k in LINK_KEYS:
            if k in new:
                new[k] = along(new[k])
        out.append(new)
    return out, moved


def _positions(layout):
    """type -> [x, y] in whole pixels, from either form of a layout."""
    out = {}
    for k, p in ((layout or {}).get("positions") or {}).items():
        try:
            x, y = (p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1])
            out[str(k)] = [int(round(float(x))), int(round(float(y)))]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def merge_layout(base, head, page, types):
    """head's layout with the page's positions laid over it: a position the
    page moved away from base's wins; one head has no position for at all
    is placed where the page has it. Anything else keeps head's: what the
    page did not move, and what base had no place for, which the page laid
    out by itself (its whole graph when base had no layout file) -- else
    that would overwrite a hand arrangement published meanwhile. Positions
    of types not in types (the merged rows and the generated ones) are
    dropped."""
    out = {k: v for k, v in (head or {}).items() if k != "positions"}
    pos = _positions(head)
    if page is not None:
        was = _positions(base)
        for k, p in _positions(page).items():
            if k not in pos or (k in was and was[k] != p):
                pos[k] = p
    keep = {str(t) for t in types}
    out["positions"] = {k: v for k, v in pos.items() if k in keep}
    return out


_GONE = object()


def summarize(head_rows, rows):
    """What the merged rows change against head, one line a quest."""
    h = {int(r["type"]): r for r in head_rows}
    now = {int(r["type"]) for r in rows}
    lines = []
    for r in rows:
        t = int(r["type"])
        if t not in h:
            lines.append("новый #%d «%s»" % (t, plain_name(r)))
        elif r != h[t]:
            keys = [k for k in dict.fromkeys(list(h[t]) + list(r))
                    if h[t].get(k, _GONE) != r.get(k, _GONE)]
            lines.append("правка #%d «%s»: %s" % (t, plain_name(r), one_line(", ".join(keys))))
    for t, r in h.items():
        if t not in now:
            lines.append("удалён #%d «%s»" % (t, plain_name(r)))
    return lines


def commit_message(summary, note, login):
    """First line "Квесты: …" within 72 characters, the summary, the
    admin's words, who published."""
    summary = [one_line(s) for s in summary]
    if len(summary) == 1:
        short = summary[0]
    else:
        counts = [(sum(1 for s in summary if s.startswith(p)), w) for p, w in
                  (("новый", "новых"), ("правка", "правок"), ("удалён", "удалено"))]
        short = ", ".join("%s: %d" % (w, n) for n, w in counts if n)
        if any(s.startswith("раскладка") for s in summary):
            short = (short + ", раскладка") if short else "раскладка графа"
    first = "Квесты: " + short
    if len(first) > 72:
        first = first[:71] + "…"
    parts = [first, "", "\n".join(summary)]
    if note:
        parts += ["", note]
    parts += ["", "Опубликовано из админки: %s" % login]
    return "\n".join(parts) + "\n"


class Publisher:
    """The clone publish mode works on (--repo): fetches, merges, commits and
    pushes to origin/<branch>, one publish at a time."""

    def __init__(self, repo, branch="main", web=""):
        self.repo = os.path.abspath(repo)
        self.branch = branch
        self.web = (web or "").rstrip("/")
        self.lock = threading.Lock()          # one publish at a time
        self._fetch_lock = threading.Lock()
        self._fetched = 0.0
        self._fetch_error = None
        self.restarting = False
        self.exit = _exit_now                 # a test puts its own here
        self.before_push = None               # and a hook here, to move the branch

    # -- git --------------------------------------------------------------------
    def git(self, *args, data=None, env=None, timeout=GIT_TIMEOUT):
        """git -C repo args...: its stdout; GitError with its stderr. An
        argument list and a timeout, never a shell."""
        full = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C", LANG="C")
        full.update(env or {})
        try:
            done = subprocess.run(["git", "-C", self.repo] + list(args), input=data,
                                  capture_output=True, timeout=timeout, env=full)
        except subprocess.TimeoutExpired:
            raise GitError("git %s: no answer in %d s" % (args[0], timeout)) from None
        except OSError as exc:
            raise GitError("git: %s" % exc) from None
        if done.returncode:
            raise GitError(_trim(done.stderr.decode("utf-8", "replace"))
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

    def table_text(self, rev):
        raw = self.show(rev, REL_TABLE)
        if raw is None:
            raise GitError("%s has no %s" % (rev[:12], REL_TABLE))
        return raw.decode("utf-8")

    def info(self, rev="HEAD"):
        out = self.git("log", "-1", "--format=%H%x00%cI%x00%an%x00%s", rev)
        sha, date, author, subject = (out.decode("utf-8", "replace").strip().split("\0")
                                      + ["", "", "", ""])[:4]
        return {"sha": sha, "date": date, "author": author, "subject": subject}

    def engine_moved(self, rev):
        """The files under ENGINE that differ between the checkout and rev,
        the table and the layout aside: what check() would read stale."""
        names = self.git("diff", "--no-renames", "--name-only", "HEAD", rev, "--", *ENGINE)
        return [n for n in names.decode("utf-8").split("\n") if n and n not in (REL_TABLE, REL_LAYOUT)]

    def generated_at(self, rev):
        """generated()'s shape, of the commit: its data/questgen_*.json."""
        names = self.git("ls-tree", "--name-only", rev, "data/").decode("utf-8").split("\n")
        out = []
        for p in sorted(n for n in names if n):
            base = p.rsplit("/", 1)[-1]
            if base.startswith("questgen_") and base.endswith(".json"):
                out.append({"source": base, "rows": json.loads(self.show(rev, p))["quests"]})
        return out

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

    # -- the merge ----------------------------------------------------------------
    def prepare(self, rows, layout, base):
        """Fetch, then the page's rows and layout merged onto origin/<branch>
        (renumber_new, merge_rows, merge_layout) and checked. A dict: head,
        rows, doc, text (the table's new text, head's line endings),
        table_changed, layout (as the file has it), layout_text,
        layout_changed, summary, conflicts, problems, nothing, head_text,
        renumbered. EngineMoved when origin's engine is not the checkout's."""
        self.fetch()
        head = self.rev(self.remote_ref)
        moved = self.engine_moved(head)
        if moved:
            raise EngineMoved(moved[0])
        self.ensure(base)
        base_doc = json.loads(self.table_text(base))
        head_text = self.table_text(head)
        head_doc = json.loads(head_text)
        eol = "\r\n" if "\r\n" in head_text else "\n"
        before = {int(r["type"]): r for r in base_doc["quests"]}
        order = key_order(base_doc["quests"])
        mine = [ordered(as_written(r, before.get(int(r["type"]))), before.get(int(r["type"])), order)
                for r in rows]
        gen = self.generated_at(head)
        import orig_texts
        taken = {int(r["type"]) for g in gen for r in g["rows"]} | set(orig_texts.quests())
        mine, renumbered = renumber_new(base_doc["quests"], head_doc["quests"], mine, taken)
        if renumbered and layout is not None:
            layout = dict(layout, positions={
                (str(renumbered[int(k)]) if str(k).isdigit() and int(k) in renumbered else k): p
                for k, p in (layout.get("positions") or {}).items()})
        merged, conflicts = merge_rows(base_doc["quests"], head_doc["quests"], mine)
        doc = dict(head_doc)
        doc["quests"] = merged
        text = dumps_table(doc)
        if eol != "\n":
            text = text.replace("\n", eol)
        types = {int(r["type"]) for r in merged} | {int(r["type"]) for g in gen for r in g["rows"]}
        base_layout_raw = self.show(base, REL_LAYOUT)
        head_layout_raw = self.show(head, REL_LAYOUT)
        head_layout = json.loads(head_layout_raw.decode("utf-8")) if head_layout_raw else {}
        base_layout = json.loads(base_layout_raw.decode("utf-8")) if base_layout_raw else {}
        new_layout = merge_layout(base_layout, head_layout, layout, types)
        layout_text = dumps_layout(new_layout)
        if head_layout_raw is None:
            layout_changed = bool(new_layout["positions"])
        else:
            layout_changed = layout_text != head_layout_raw.decode("utf-8").replace("\r\n", "\n")
        summary = summarize(head_doc["quests"], merged)
        if layout_changed:
            was = _positions(head_layout)
            now = new_layout["positions"]
            moved = sum(1 for k in set(was) | set(now) if was.get(k) != now.get(k))
            summary.append("раскладка графа: %d" % moved)
        table_changed = merged != head_doc["quests"]
        problems = check(merged, current_where(), gen)
        if not reads_back(text, merged):
            # The bytes about to be committed must be the table just checked.
            problems.insert(0, {"type": None, "level": "error", "text": "the table reads back otherwise",
                                "ru": "%s прочитался бы иначе, чем проверенная таблица: такое "
                                      "не публикуется" % REL_TABLE})
        return {"head": head, "rows": merged, "doc": doc, "text": text, "head_text": head_text,
                "table_changed": table_changed, "layout": new_layout, "layout_text": layout_text,
                "layout_changed": layout_changed, "summary": summary, "conflicts": conflicts,
                "problems": problems, "renumbered": {str(k): v for k, v in renumbered.items()},
                "nothing": not table_changed and not layout_changed}

    def failed(self, lead, exc):
        """A 502's body: what happened in the page's words, git's own below."""
        return {"error": lead.format(branch=self.branch), "git": str(exc)}

    def rebase(self, got):
        """What the page becomes if it takes main's version of the quests in
        conflict and keeps the rest of its edits: the merged rows (head's
        version wherever there is a conflict) on head as the new base."""
        return {"commit": got["head"], "head": self._about(got["head"]), "rows": got["rows"],
                "layout": page_layout(got["layout"]), "changed": not got["nothing"]}

    def preview(self, rows, layout, base):
        """(status, body) of POST /api/preview."""
        try:
            got = self.prepare(rows, layout, base)
        except EngineMoved:
            self.restart()
            return 503, {"restarting": True, "error": ENGINE_MOVED % self.branch}
        except BaseMissing:
            return 409, {"error": "Коммит, с которого открыта страница, не найден: обновите страницу",
                         "conflicts": []}
        except FetchError as exc:
            return 502, self.failed(FETCH_FAILED, exc)
        except GitError as exc:
            return 502, self.failed(GIT_FAILED, exc)
        except (ValueError, KeyError) as exc:
            return 502, {"error": "%s в %s не читается: %s" % (REL_TABLE, self.branch, exc)}
        new = got["text"] if got["table_changed"] else got["head_text"]
        lines = difflib.unified_diff(got["head_text"].replace("\r\n", "\n").splitlines(),
                                     new.replace("\r\n", "\n").splitlines(),
                                     "origin/%s:%s" % (self.branch, REL_TABLE), REL_TABLE,
                                     lineterm="", n=2)
        out = {"head": got["head"], "summary": got["summary"], "conflicts": got["conflicts"],
               "problems": got["problems"], "diff": "\n".join(lines),
               "layout_changed": got["layout_changed"], "nothing": got["nothing"],
               "renumbered": got["renumbered"]}
        if got["conflicts"]:
            out["rebase"] = self.rebase(got)
        return 200, out

    # -- the commit -----------------------------------------------------------------
    def commit(self, head, files, message, login):
        """A commit on head with files ({path: bytes}) in place, built in a
        temporary index: the checkout and its index are never touched."""
        tmp = tempfile.mkdtemp(prefix="quest-publish-")
        try:
            env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
            self.git("read-tree", head, env=env)
            for path, data in files.items():
                blob = self.git("hash-object", "-w", "--stdin", data=data).decode().strip()
                listed = self.git("ls-tree", head, "--", path).decode().split()
                mode = listed[0] if listed else "100644"
                self.git("update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, blob, path),
                         env=env)
            tree = self.git("write-tree", env=env).decode().strip()
            env.update(
                GIT_AUTHOR_NAME="%s (админка)" % login,
                GIT_AUTHOR_EMAIL=os.environ.get("LAVA_QUESTS_AUTHOR_EMAIL") or "quests@lava-reborn.ru",
                GIT_COMMITTER_NAME=os.environ.get("LAVA_QUESTS_COMMITTER_NAME") or "Квест-редактор админки",
                GIT_COMMITTER_EMAIL=os.environ.get("LAVA_QUESTS_COMMITTER_EMAIL") or "quests@lava-reborn.ru")
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

    def publish(self, rows, layout, base, note, login):
        """(status, body) of POST /api/publish."""
        if not self.lock.acquire(timeout=PUSH_TIMEOUT * 2):
            return 503, {"error": "Идёт другая публикация, повторите через минуту"}
        try:
            return self._publish(rows, layout, base, note, login)
        finally:
            self.lock.release()

    def _publish(self, rows, layout, base, note, login):
        for attempt in range(PUSH_TRIES):
            try:
                got = self.prepare(rows, layout, base)
            except EngineMoved:
                self.restart()
                return 503, {"restarting": True, "error": ENGINE_MOVED % self.branch}
            except BaseMissing:
                return 409, {"error": "Коммит, с которого открыта страница, не найден: обновите страницу",
                             "conflicts": []}
            except FetchError as exc:
                return 502, self.failed(FETCH_FAILED, exc)
            except GitError as exc:
                return 502, self.failed(GIT_FAILED, exc)
            except (ValueError, KeyError) as exc:
                return 502, {"error": "%s в %s не читается: %s" % (REL_TABLE, self.branch, exc)}
            if got["conflicts"]:
                return 409, {"error": "Эти квесты изменились в %s после загрузки страницы" % self.branch,
                             "conflicts": got["conflicts"], "rebase": self.rebase(got)}
            errors = [p for p in got["problems"] if p["level"] == "error"]
            if errors:
                return 422, {"error": "В таблице ошибки, сервер на ней не запустится",
                             "problems": errors}
            done = {"rows": got["rows"], "layout": page_layout(got["layout"]),
                    "renumbered": got["renumbered"]}
            if got["nothing"]:
                return 200, dict(done, nothing=True, commit=got["head"], head=self._about(got["head"]))
            files = {}
            if got["table_changed"]:
                files[REL_TABLE] = got["text"].encode("utf-8")
            if got["layout_changed"]:
                files[REL_LAYOUT] = got["layout_text"].encode("utf-8")
            try:
                sha = self.commit(got["head"], files,
                                  commit_message(got["summary"], note, login), login)
            except GitError as exc:
                return 502, self.failed(GIT_FAILED, exc)
            try:
                if self.before_push:
                    self.before_push(attempt)
                pushed = self.push(sha)
            except GitError as exc:
                return 502, self.failed(PUSH_FAILED, exc)
            if pushed:
                return 200, dict(done, commit=sha, summary=got["summary"], head=self._about(sha),
                                 url=("%s/commit/%s" % (self.web, sha)) if self.web else "")
        return 502, {"error": "%s уходил вперёд во время публикации %d раза подряд: повторите"
                              % (self.branch, PUSH_TRIES)}

    def _about(self, sha):
        """info(sha), or as much as is known: a reply about a commit already
        pushed must not turn into an error."""
        try:
            return self.info(sha)
        except GitError:
            return {"sha": sha, "date": "", "author": "", "subject": ""}

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


def _exit_now(code):
    os._exit(code)


def configure(repo, branch="main", web=""):
    """Publish mode on the clone repo: the table and the layout are its."""
    global PUB, TABLE, LAYOUT
    PUB = Publisher(repo, branch, web)
    TABLE = os.path.join(PUB.repo, "data", "quests.json")
    LAYOUT = os.path.join(PUB.repo, "data", "quest_layout.json")
    return PUB


def entry():
    """The built page's script and stylesheets, for a page that embeds it
    (the admin panel's /admin/quests)."""
    with open(os.path.join(UI, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    js = re.search(r'<script[^>]*\ssrc="(?:\./|/)?(assets/[^"]+\.js)"', html)
    css = re.findall(r'<link[^>]*\shref="(?:\./|/)?(assets/[^"]+\.css)"', html)
    return {"js": js.group(1) if js else None, "css": css}


def header_text(raw):
    """A header http.server read as Latin-1, back to the UTF-8 it was sent in."""
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def good_rows(rows):
    """A list of rows, each with a numeric type and keys that are plain names
    (as every key of the table is): a key with a quote or a newline in it
    could make the file say other than the rows that were checked, or not
    parse at all."""
    return isinstance(rows, list) and all(
        isinstance(r, dict) and isinstance(r.get("type"), int) and not isinstance(r["type"], bool)
        and all(isinstance(k, str) and _KEY.fullmatch(k) for k in r)
        for r in rows)


def reads_back(text, rows):
    """Whether the table's text reads back as these rows."""
    try:
        return json.loads(text)["quests"] == rows
    except (ValueError, KeyError, TypeError):
        return False


# --- the page -------------------------------------------------------------------

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
         ".json": "application/json; charset=utf-8", ".woff2": "font/woff2"}


class Handler(BaseHTTPRequestHandler):
    server_version = "LavaQuestEditor/1"

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, base, rel):
        path = os.path.normpath(os.path.join(base, rel))
        if not path.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(path):
            return self._send({"error": "not found"}, code=404)
        with open(path, "rb") as fh:
            data = fh.read()
        self._send(data, TYPES.get(os.path.splitext(path)[1], "application/octet-stream"))

    def _local_only(self):
        """Local mode answers under a loopback name only (or the --host it
        was given): a page on another site that rebinds its own name to
        127.0.0.1 then gets nothing. Publish mode sits behind the panel,
        under the container's name. True when the request was refused."""
        if PUB:
            return False
        port = self.server.server_address[1]
        names = {"127.0.0.1", "localhost", "[::1]"}
        bound = getattr(self.server, "bound_host", "")
        if bound and bound not in ("0.0.0.0", "::"):
            names.add(bound.lower())
        if (self.headers.get("Host") or "").strip().lower() in {"%s:%d" % (n, port) for n in names}:
            return False
        self._send({"error": "Редактор отвечает только по адресу http://127.0.0.1:%d/ "
                             "или http://localhost:%d/" % (port, port)}, code=403)
        return True

    def _body(self):
        """(the body's bytes, its content type), the body read whole first:
        a refusal sent while the client is still sending breaks its pipe."""
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n > 0 else b""
        return raw, (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()

    def do_GET(self):
        url = self.path.split("?", 1)[0]
        if self._local_only():
            return
        if url == "/health":
            return self._send(b"ok", "text/plain; charset=utf-8")
        if url == "/" or url == "/index.html":
            return self._file(UI, "index.html")
        if url.startswith("/assets/"):
            return self._file(UI, url[1:])
        if url.startswith("/icon/") and url.endswith(".png"):
            return self._file(os.path.join(ADMIN, "static", "icons"), url[len("/icon/"):])
        if url == "/api/entry":
            try:
                return self._send(entry())
            except OSError:
                return self._send({"error": "страница редактора не собрана"}, code=500)
        if url == "/api/table":
            return self._table()
        if url == "/api/refs":
            return self._send(refs())
        if url == "/api/diff":
            if PUB:
                return self._send({"error": PUBLISH_ONLY}, code=403)
            return self._send({"diff": diff()})
        return self._send({"error": "not found"}, code=404)

    def _table(self):
        out = {}
        if PUB:
            stale = None if PUB.restarting else PUB.fetch_now_and_then()
            try:
                moved = not stale and PUB.rev(PUB.remote_ref) != PUB.rev("HEAD")
            except GitError as exc:
                stale, moved = str(exc), False
            if PUB.restarting or moved:
                self._send({"restarting": True, "error": RESTARTING % PUB.branch}, code=503)
                return PUB.restart()
            try:
                head = PUB.info("HEAD")
            except GitError as exc:
                return self._send({"error": str(exc)}, code=502)
            out = {"mode": "publish", "commit": head["sha"], "branch": PUB.branch,
                   "web": PUB.web, "head": head}
            if stale:
                out["stale"] = _reason(stale)
        cur = read_table()
        out.update({"rows": cur["doc"]["quests"], "sha": cur["sha"],
                    "generated": generated(), "layout": read_layout(),
                    "order": key_order(cur["doc"]["quests"]),
                    "new_types": [NEW_TYPES_FROM, NEW_TYPES_TO],
                    "ways": way_types(cur["doc"]["quests"])})
        out.setdefault("mode", "local")
        return self._send(out)

    def do_POST(self):
        url = self.path.split("?", 1)[0]
        try:
            raw, ctype = self._body()
        except ValueError:
            return self._send({"error": "bad Content-Length"}, code=400)
        if self._local_only():
            return
        # JSON only: any other type is what a page on another site may send
        # here without asking first (a CORS "simple" request); for JSON the
        # browser asks first (OPTIONS), and nothing here answers that.
        if ctype != "application/json":
            return self._send({"error": "a JSON body only (Content-Type: application/json)"}, code=415)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            return self._send({"error": "bad json"}, code=400)
        if not isinstance(body, dict):
            return self._send({"error": "bad json"}, code=400)
        if url == "/api/check":
            return self._send({"problems": check(body.get("rows") or [], current_where())})
        if url == "/api/texts":
            return self._send(texts(body.get("row") or {}))
        if url == "/api/new":
            rows = body.get("rows") or []
            if PUB and good_rows(rows):
                # numbers main took since the checkout are taken too (as last fetched)
                try:
                    have = {r["type"] for r in rows}
                    rows = rows + [r for r in json.loads(PUB.table_text(PUB.remote_ref))["quests"]
                                   if r.get("type") not in have]
                except (GitError, ValueError, KeyError):
                    pass
            try:
                return self._send({"row": new_row(body.get("kind") or quests.DEL_OBJ, rows)})
            except ValueError as exc:
                return self._send({"error": str(exc)}, code=400)
        if url == "/api/save":
            if PUB:
                return self._send({"error": PUBLISH_ONLY}, code=403)
            rows, layout = body.get("rows") or [], body.get("layout")
            if not good_rows(rows) or (layout is not None and not isinstance(layout, dict)):
                return self._send({"error": BAD_ROWS}, code=400)
            code, out = save(rows, layout, body.get("sha"), bool(body.get("force")))
            return self._send(out, code=code)
        if url in ("/api/preview", "/api/publish") and PUB:
            return self._publish(url, body)
        return self._send({"error": "not found"}, code=404)

    def _publish(self, url, body):
        if PUB.restarting:
            return self._send({"restarting": True, "error": RESTARTING % PUB.branch}, code=503)
        rows, layout, base = body.get("rows"), body.get("layout"), str(body.get("base") or "")
        login = clean_login(header_text(self.headers.get("X-Lava-Admin") or ""))
        if url == "/api/publish" and not login:
            return self._send({"error": "нет X-Lava-Admin: кто публикует?"}, code=400)
        if not _SHA.match(base):
            return self._send({"error": "нет коммита, с которого открыта страница (base)"}, code=400)
        if not good_rows(rows) or (layout is not None and not isinstance(layout, dict)):
            return self._send({"error": BAD_ROWS}, code=400)
        if url == "/api/preview":
            code, out = PUB.preview(rows, layout, base)
            return self._send(out, code=code)
        code, out = PUB.publish(rows, layout, base, clean_note(body.get("message")), login)
        print("publish by %s: %d %s" % (login, code, out.get("commit") or out.get("error", "")[:200]),
              flush=True)
        return self._send(out, code=code)


PUBLISH_ONLY = "В админке правки уходят в main кнопкой «Опубликовать»"
BAD_ROWS = ("rows: список строк с числовым type, ключи строк — простые имена "
            "(латиница, цифры, подчёркивание)")


def serve(port=PORT, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.bound_host = host
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--repo", help="publish mode: a git clone whose origin is the source of truth")
    ap.add_argument("--branch", default=os.environ.get("LAVA_QUESTS_BRANCH") or "main",
                    help="the branch publish mode pushes to (LAVA_QUESTS_BRANCH, main)")
    args = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(UI, "index.html")):
        sys.exit("the page is not built: bash tools/quest_editor_ui/build.sh")
    if args.repo:
        configure(args.repo, args.branch, os.environ.get("LAVA_QUESTS_WEB", ""))
        args.no_browser = True
    srv = serve(args.port, args.host)
    url = "http://%s:%d/" % (args.host, srv.server_address[1])
    if PUB:
        print("quest editor, publish mode: %s -> origin/%s, on %s" % (PUB.repo, PUB.branch, url),
              flush=True)
    else:
        print("quest editor on %s (Ctrl+C to stop)" % url)
    # The reference data takes a dozen seconds the first time; the page can
    # open meanwhile.
    threading.Thread(target=refs, daemon=True).start()
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:                  # noqa: BLE001 -- WSL may have none
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
