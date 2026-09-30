"""Carry the wiki's quests for the starting town into data/quests.json.

data/quests_wiki.json shapes all 1191 wiki quests for server/quests.py but
leaves items and rewards as page titles and binds givers wherever the NPC
page put them. This pass takes the few that can actually run in the four
Wadi Halfa locations the player starts in -- the black market (102), the old
market (35), the residential quarter (36) and the station (37) -- and only
where nothing has to be guessed:

  * the giver's wiki page is tied to a type id with confidence high or
    better (data/npc_wiki.json), that type spawns in one of the four
    locations, and the taker, when a different NPC, is tied the same way;
  * the kind is one quests.py runs: a delivery with nothing to carry
    (del_obj, obj=0: the server cannot hand out the object yet), or
    bring_l_obj whose every item resolves to exactly one type id through
    data/wiki_links.json; kill_mobs waits for a mob-name resolver;
  * rewards are the wiki's: items that resolve, afro and gold as written;
    an item that does not resolve is dropped, and a quest left with nothing
    to give is not imported.

The hand-written quests already in the table -- the market's six, the
Nubian mine's two ways, 7 and 8, and Камал's «Золотоискатель», 9 -- stay as
they are; rows
this script wrote before (marked wiki_type) are replaced where they stand,
so a rerun is idempotent and keeps the file's order, and a wiki quest a hand
row stands for (by its name, or the type the import would give it) is not
imported. Imported types are 1000 + the wiki quest's number in
quests_wiki.json, which keeps their string ids stable (quests.md 4.4).
Texts the builder left empty are read again off the wikitext here, where the
article puts the quest's name on the same line as the opening speech.

Wiki text is CC-BY-SA (https://lava-online.fandom.com/ru).

    wsl.exe -e python3 data/build_quests_start.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import items  # noqa: E402
import world  # noqa: E402

TARGET = {102: "Чёрный рынок Вади-Хальфы", 35: "Старый рынок", 36: "Жилой квартал",
          37: "Вокзал"}
TRUSTED = ("verified", "high", "medium")
TYPE_BASE = 1000
QUESTS = os.path.join(HERE, "quests.json")

# Pages the linker has no icon for, tied by hand. The certificate is the
# object of quest 4 (Пистолетчик, written from the same article in the first
# wave) and objects.xml calls it qTIRcertificate; its five sibling quests ask
# for the same thing.
MANUAL_ITEMS = {"Сертификат Берта Гаммера": 3742}

SECTION = {
    "start": r"'''Начало квеста\s*:?'''\s*:?",
    "notfinish": r"'''Незаконченный квест\s*:?'''\s*:?",
    "finish": r"'''Конец квеста\s*:?'''\s*:?",
}
STOP = r"(?=\n\s*'''|\n==|\Z)"
LEVEL = re.compile(r"(?:от|с)\s+(\d+)(?:-?го)?\s+уровня", re.I)
COUNT = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*\((\d+)\s*шт")
PARENT = re.compile(r"Родительск\w*\s+квест\w*[:'\s]*(.*)")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def trusted_places(npcs, title):
    """(type_id, location) pairs a wiki NPC page is tied to, trusted ones."""
    out = []
    for p in (npcs.get(title) or {}).get("places", []):
        if not p.get("type_id") or p.get("confidence") not in TRUSTED:
            continue
        locs = set(p.get("loc_ids") or [])
        if p.get("location"):
            locs.add(p["location"])
        for loc in locs:
            out.append((p["type_id"], loc))
    return out


def spawned(type_id, loc):
    return any(t == type_id for _cell, t in world.location(loc).spawns)


def section(txt, key):
    m = re.search(SECTION[key] + r"(.*?)" + STOP, txt, re.S)
    return m.group(1).strip() if m else ""


def speech(txt, key, name):
    """The text of one of the three speeches, cleaned; the builder's own
    result where it found one, the wikitext otherwise."""
    raw = section(txt, key)
    # "'''Начало квеста:''' Муж<br />Что-то я..." -- the name first
    raw = re.sub(r"^%s\s*(<br\s*/?>|\n)" % re.escape(name), "", raw)
    return items.clean_text(raw)


def counts(txt):
    return {title: int(n) for title, n in COUNT.findall(txt)}


def parents(q, txt):
    """Parent quest titles: the builder's, plus the article's own line,
    which the builder misses when the link sits after the header's quotes."""
    out = list(q["parents"])
    for line in PARENT.findall(txt):
        out += [t for t in LINK.findall(line) if t not in out]
    return out


def dumps_row(row):
    """One quest as the table writes it: keys in order, scalar lists and
    the objects of a bring quest on one line, the way the hand-written rows
    were laid out."""
    out = []
    for key, value in row.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            body = ",\n".join("        " + json.dumps(o, ensure_ascii=False) for o in value)
            text = "[\n" + body + "\n      ]"
        else:
            text = json.dumps(value, ensure_ascii=False)
        out.append('      "%s": %s' % (key, text))
    return "    {\n" + ",\n".join(out) + "\n    }"


def one_type(title):
    """The single type id a page title stands for, or None."""
    if title in MANUAL_ITEMS:
        return MANUAL_ITEMS[title]
    ids = items.resolve_title(title)
    return ids[0] if len(ids) == 1 else None


def main():
    wiki = load("quests_wiki.json")["quests"]
    npcs = load("npc_wiki.json")["npcs"]
    pages = load(os.path.join("wiki", "pages.json"))
    table = load("quests.json")

    rows, skipped = [], []
    by_name = {}
    for key in sorted(wiki, key=int):
        q = wiki[key]
        name = q["name"]
        # --- who gives it, and where
        givers = [(t, loc) for t, loc in trusted_places(npcs, q["giver"])
                  if loc in TARGET and spawned(t, loc)]
        if not givers:
            continue
        give_type, loc = givers[0]
        why = None
        if q["kind"] not in ("del_obj", "bring_l_obj"):
            why = "kind %s not importable yet" % q["kind"]
        # A hand row stands for the wiki's quest by its name, or by the type
        # the import would give it (TYPE_BASE + the wiki's number: 1682 is
        # the wiki's 682, renamed by hand). Never by the wiki's own number
        # as a type: hand rows 5, 7, 11 ... are other quests than the wiki's
        # #5, #7, #11 («30 Каменных Блоков» was skipped for row 5).
        elif any(r.get("name") == name or int(r.get("type", 0)) == TYPE_BASE + int(key)
                 for r in table["quests"] if "wiki_type" not in r):
            why = "already in the table by hand"
        if why:
            skipped.append((key, name, q["giver"], loc, why))
            continue
        # --- who takes it
        if q["taker"] and q["taker"] != q["giver"]:
            takers = [t for t, l in trusted_places(npcs, q["taker"]) if spawned(t, l)]
            if not takers:
                skipped.append((key, name, q["giver"], loc, "taker %r not tied to a type id" % q["taker"]))
                continue
            take = [takers[0]]
        else:
            take = [give_type]
        txt = (pages.get(name) or {}).get("wikitext", "")
        num = counts(txt)
        # --- the goal
        row = {"type": TYPE_BASE + int(key), "kind": q["kind"], "name": name}
        if q["kind"] == "del_obj":
            if q["items"]:
                skipped.append((key, name, q["giver"], loc, "a delivery with an object: not runnable yet"))
                continue
            row["obj"] = 0
        else:
            objs, bad = [], []
            for title in q["items"]:
                t = one_type(title)
                (objs if t else bad).append({"obj": t, "num": num.get(title, 1), "mobs": []} if t else title)
            if bad or not objs or len(objs) > 6:
                skipped.append((key, name, q["giver"], loc, "items unresolved: %s" % ", ".join(bad or ["none"])))
                continue
            row["objs"] = objs
        # --- the reward
        rew, dropped = [], []
        for title in q["rew_items"]:
            t = one_type(title)
            if t and t not in rew:
                rew.append(t)
            elif not t:
                dropped.append(title)
        if not rew and not q["rew_afro"] and not q["rew_gold"]:
            skipped.append((key, name, q["giver"], loc, "nothing to give: rewards %s" % (dropped or "none")))
            continue
        for k in ("start", "notfinish", "finish"):
            row[k] = items.clean_text(q[k + "_desc"]) or speech(txt, k, name)
        row.update(give=[give_type], take=take,
                   rew_obj=rew, num_rew_obj=[num.get(t, 1) for t in q["rew_items"] if one_type(t) in rew][:len(rew)],
                   rew_afro=q["rew_afro"], rew_gold=q["rew_gold"],
                   repeatable=1 if q["repeatable"] else 0,
                   level=0 if "любого уровня" in txt else
                   (int(LEVEL.search(txt).group(1)) if LEVEL.search(txt) else q["level"]),
                   q_type=0, need_quest=0, loc=q["loc"] or 0, finish_loc=q["finish_loc"] or -1,
                   parents=parents(q, txt), wiki_type=int(key), source=q["source"],
                   loc_id=loc, giver=q["giver"], taker=q["taker"] or q["giver"],
                   dropped_rewards=dropped)
        if len(row["num_rew_obj"]) != len(rew):
            row["num_rew_obj"] = [1] * len(rew)
        rows.append(row)
        by_name[name] = row["type"]
    for row in rows:
        row["need_quest"] = next((by_name[p] for p in row.pop("parents") if p in by_name), 0)

    kept = [r for r in table["quests"] if "wiki_type" not in r]
    # The file's order stays: a row imported before is replaced where it
    # stands, one the wiki no longer gives is dropped, a new one goes last.
    fresh = {r["type"]: r for r in rows}
    ordered = [r if "wiki_type" not in r else fresh.get(r["type"])
               for r in table["quests"]]
    placed = {r["type"] for r in ordered if r is not None}
    ordered = [r for r in ordered if r is not None] + \
        [r for r in rows if r["type"] not in placed]
    table["_source"] = ("Quest 4 is the article 'Пистолетчик' on https://lava-online.fandom.com/ru "
                        "(CC-BY-SA); rows carrying wiki_type/source were imported from the wiki "
                        "by data/build_quests_start.py; the rest are written for this server.")
    head = ",\n".join('  "%s": %s' % (k, json.dumps(v, ensure_ascii=False))
                      for k, v in table.items() if k != "quests")
    body = ",\n".join(dumps_row(r) for r in ordered)
    with io.open(QUESTS, "w", encoding="utf-8") as fh:
        fh.write("{\n%s,\n  \"quests\": [\n%s\n  ]\n}\n" % (head, body))
    json.loads(io.open(QUESTS, encoding="utf-8").read())   # what was written parses

    print("imported %d wiki quests, %d hand-written kept" % (len(rows), len(kept)))
    for row in rows:
        print("  %4d  %-28s %-14s -> %-14s loc %3d %s  give %s take %s objs %s rew %s +%d afro +%d gold lvl %d%s" % (
            row["type"], row["name"][:28], row["giver"][:14], row["taker"][:14], row["loc_id"],
            row["kind"], row["give"], row["take"],
            [(o["obj"], o["num"]) for o in row.get("objs", [])], row["rew_obj"],
            row["rew_afro"], row["rew_gold"], row["level"],
            "  dropped rewards: %s" % ", ".join(row["dropped_rewards"]) if row["dropped_rewards"] else ""))
    print("skipped %d candidates in the four locations:" % len(skipped))
    for key, name, giver, loc, why in skipped:
        print("  %4s  %-32s %-16s loc %3d  %s" % (key, name[:32], giver[:16], loc, why))


if __name__ == "__main__":
    main()
