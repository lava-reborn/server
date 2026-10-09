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
always.
"""
import argparse
import datetime
import difflib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import threading
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
        out.append('      "%s": %s' % (key, text))
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
    """[{source, rows}] of the generated tables beside the real one."""
    path = path or TABLE
    if os.path.abspath(path) != os.path.abspath(quests.PATH):
        return []
    out = []
    for p in quests.companion_paths(path):
        with open(p, encoding="utf-8") as fh:
            out.append({"source": os.path.basename(p), "rows": json.load(fh)["quests"]})
    return out


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


def check(rows, places=None):
    """Every problem of the hand rows given, read with the generated tables on
    disk, as load and check_items would meet them, and the warnings."""
    every = list(rows)
    for g in generated():
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
    base = os.path.join(world.RES, "locations", "static")
    try:
        return sorted(int(f[:-4]) for f in os.listdir(base)
                      if f.endswith(".xml") and f[:-4].isdigit())
    except OSError:
        return []


def _scan(ids):
    """{"where": type -> sorted locations it stands in, "titles": location ->
    title}, from the location files; cached on disk by the files' count and
    newest change, because the scan reads 1381 files and takes a dozen
    seconds over /mnt/c."""
    base = os.path.join(world.RES, "locations", "static")
    try:
        stamp = "%d-%d" % (len(ids), int(max(os.path.getmtime(os.path.join(base, "%d.xml" % i))
                                              for i in ids)) if ids else 0)
    except OSError:
        stamp = "none"
    key = hashlib.sha256((world.RES + stamp).encode()).hexdigest()[:16]
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


def write_layout(layout, path=None):
    """data/quest_layout.json: one line per quest, "type": [x, y] in whole
    pixels, so that moving one quest is a one-line change."""
    positions = layout.get("positions") or {}
    lines = []
    for k in sorted(positions, key=lambda s: int(s) if str(s).isdigit() else 0):
        p = positions[k]
        x, y = (p["x"], p["y"]) if isinstance(p, dict) else (p[0], p[1])
        lines.append('    "%s": [%d, %d]' % (k, round(x), round(y)))
    rest = {k: v for k, v in layout.items() if k != "positions"}
    head = "".join('  %s: %s,\n' % (json.dumps(k, ensure_ascii=False), json.dumps(v, ensure_ascii=False))
                   for k, v in sorted(rest.items()))
    text = ("{\n" + head + '  "positions": {\n' + ",\n".join(lines)
            + ("\n" if lines else "") + "  }\n}\n")
    with open(path or LAYOUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


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
    pos = layout.get("positions") or {}
    layout["positions"] = {k: ({"x": v[0], "y": v[1]} if isinstance(v, list) else v)
                           for k, v in pos.items()}
    return layout


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

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        url = self.path.split("?", 1)[0]
        if url == "/" or url == "/index.html":
            return self._file(UI, "index.html")
        if url.startswith("/assets/"):
            return self._file(UI, url[1:])
        if url.startswith("/icon/") and url.endswith(".png"):
            return self._file(os.path.join(ADMIN, "static", "icons"), url[len("/icon/"):])
        if url == "/api/table":
            cur = read_table()
            return self._send({"rows": cur["doc"]["quests"], "sha": cur["sha"],
                               "generated": generated(), "layout": read_layout(),
                               "order": key_order(cur["doc"]["quests"]),
                               "new_types": [NEW_TYPES_FROM, NEW_TYPES_TO]})
        if url == "/api/refs":
            return self._send(refs())
        if url == "/api/diff":
            return self._send({"diff": diff()})
        return self._send({"error": "not found"}, code=404)

    def do_POST(self):
        url = self.path.split("?", 1)[0]
        try:
            body = self._body()
        except ValueError:
            return self._send({"error": "bad json"}, code=400)
        if url == "/api/check":
            return self._send({"problems": check(body.get("rows") or [], current_where())})
        if url == "/api/texts":
            return self._send(texts(body.get("row") or {}))
        if url == "/api/new":
            try:
                return self._send({"row": new_row(body.get("kind") or quests.DEL_OBJ,
                                                  body.get("rows") or [])})
            except ValueError as exc:
                return self._send({"error": str(exc)}, code=400)
        if url == "/api/save":
            code, out = save(body.get("rows") or [], body.get("layout"),
                             body.get("sha"), bool(body.get("force")))
            return self._send(out, code=code)
        return self._send({"error": "not found"}, code=404)


def serve(port=PORT):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(UI, "index.html")):
        sys.exit("the page is not built: bash tools/quest_editor_ui/build.sh")
    srv = serve(args.port)
    url = "http://127.0.0.1:%d/" % args.port
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
