"""Build data/quests_wiki.json: the wiki's 1191 quests in the shape server/quests.py needs.

recon/analysis/wiki_quests_all.json already holds, for every quest page,
the title, the three texts the client shows (start / unfinished / finished),
the giver and taker by wiki name, the map coordinates, the reward names and
the repeatable flag. This script adds what that pass left in the wikitext
(the level requirement, the afro and gold amounts, the items and mobs the
quest involves, the parent quest), decides the client kind from the verb
(kill_mobs / bring_l_obj / del_obj) and, through data/npc_wiki.json, turns
the giver and taker names into type ids and locations.

A quest is usable by the server only when its giver has a type id; the
rest are written too, with empty give/take lists and a note, so nothing on
the wiki is lost and the gap is measurable. Reward and quest items stay as
page titles until data/wiki_links.json maps them to item type ids.

Quest type numbers are assigned by sorted title, so they are stable across
reruns as long as no page is added or removed; string ids for the client's
texts.xml follow quests.md §5: 2_000_000 + 4*type + {0 name, 1 start,
2 notfinish, 3 finish}.

Wiki text is CC-BY-SA (https://lava-online.fandom.com/ru).

    wsl.exe -e python3 data/build_quests_wiki.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
sys.path.insert(0, HERE)
import world  # noqa: E402
from build_npc_wiki import links, sections  # noqa: E402

STRING_BASE = 2_000_000
XY = re.compile(r"(\d{4})\s*[xхХX×]\s*(\d{4})")
LEVEL = re.compile(r"(?:от|с|до|выше|ниже)\s+(\d+)[\s-]*(?:го|ого|й)?\s*уровн", re.I)
LEVEL2 = re.compile(r"(\d+)[\s-]*(?:го|ого|й)?\s+уровн", re.I)
AFRO = re.compile(r"(\d[\d\s]*)\s*(?:афро|Афро)")
GOLD = re.compile(r"(\d[\d\s]*)\s*(?:золот|унци|G\b|голд)", re.I)
KILL_WORDS = re.compile(r"\b(убей|убить|убийств|уничтож|перебей|перестреля|"
                        r"истреби|зачист|расправ|прикончи|ликвидир)", re.I)
BRING_WORDS = re.compile(r"\b(принес|принос|добуд|добыт|достан|достав|собер|собр|"
                         r"найд|раздобуд|отдай|передай|верни|нужн[ыоа]\s)", re.I)


def number(s):
    return int(re.sub(r"\s", "", s))


def parse_page(txt):
    """Level, afro, gold, items, mobs, parents, task text from the wikitext."""
    rec = {"level": 0, "rew_afro": 0, "rew_gold": 0, "items": [], "mobs": [],
           "parents": [], "children": [], "reward_links": []}
    m = LEVEL.search(txt) or LEVEL2.search(txt)
    if m and "любого уровня" not in txt[:600]:
        rec["level"] = int(m.group(1))
    for lvl, name, body in sections(txt):
        key = name.strip("'").replace(":", "").strip()
        if key.startswith("Награда"):
            ma = AFRO.search(body)
            mg = GOLD.search(body)
            if ma:
                rec["rew_afro"] = number(ma.group(1))
            if mg:
                rec["rew_gold"] = number(mg.group(1))
            rec["reward_links"] = [t for t, _l in links(body)
                                   if not t.startswith(("Персонажи", "Квесты"))]
        elif key.startswith("Предметы"):
            rec["items"] += [t for t, _l in links(body)]
        elif "используемые" in key or key.startswith("Мобы используемые"):
            rec["mobs"] += [t for t, _l in links(body) if t != "Персонажи"]
        elif key.startswith("Родительск"):
            rec["parents"] += [t for t, _l in links(body)]
        elif key.startswith("Дочерн"):
            rec["children"] += [t for t, _l in links(body)]
    # Mob links inside the "Мобы связанные с квестом" section that are not
    # the giver/taker lines; the giver/taker lines themselves, for the pages
    # the first pass could not read ("NPC дающий задание: [[Имя]]").
    rec["givers"], rec["takers"] = [], []
    for lvl, name, body in sections(txt):
        if name.startswith("Мобы связанные") or "NPC" in name:
            for line in body.splitlines():
                who = [t for t, _l in links(line)
                       if not t.startswith(("Персонажи", "Категория", "Квесты"))]
                if "дающий" in line or "дающего" in line:
                    rec["givers"] += who
                elif "принимающий" in line or "принимающего" in line:
                    rec["takers"] += who
                elif name.startswith("Мобы связанные"):
                    rec["mobs"] += who
    rec["items"] = sorted(set(rec["items"]))
    rec["mobs"] = sorted(set(rec["mobs"]))
    return rec


def kind_of(q, page):
    text = " ".join(filter(None, [q.get("task") or "", q.get("start") or "",
                                  q.get("notfinish") or ""]))
    if q.get("kill") or KILL_WORDS.search(text) or (page["mobs"] and not page["items"]):
        return "kill_mobs"
    if q.get("bring") or page["items"] or BRING_WORDS.search(text):
        return "bring_l_obj"
    return "del_obj"


def geo(coord):
    m = XY.search(coord or "")
    return world.pack(int(m.group(1)), int(m.group(2))) if m else 0


def main():
    with io.open(os.path.join(os.path.dirname(HERE), "recon", "analysis",
                              "wiki_quests_all.json"), encoding="utf-8") as fh:
        quests = json.load(fh)
    with io.open(os.path.join(HERE, "wiki_world", "quests.json"), encoding="utf-8") as fh:
        pages = json.load(fh)["pages"]
    with io.open(os.path.join(HERE, "npc_wiki.json"), encoding="utf-8") as fh:
        npcs = json.load(fh)["npcs"]
    with io.open(os.path.join(HERE, "npc_names.json"), encoding="utf-8") as fh:
        names = json.load(fh)["names"]
    mt = world.mob_types()

    # NPC page -> bound places (type id, location, cell), trusted ones only.
    bound = {}
    for title, rec in npcs.items():
        places = [p for p in rec["places"]
                  if p.get("type_id") and p["confidence"] in ("verified", "high", "medium")]
        if places:
            bound[title] = places

    def npc_types(name, coord):
        """Type ids for an NPC name, the copy nearest the quest's cell first."""
        places = bound.get(name)
        if not places:
            return [], None
        m = XY.search(coord or "")
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            near = [p for p in places if p.get("xy")
                    and abs(p["xy"][0] - x) <= 3 and abs(p["xy"][1] - y) <= 3]
            if near:
                places = near
        ids = sorted({p["type_id"] for p in places})
        loc = places[0]["loc_ids"][0] if places[0]["loc_ids"] else None
        return ids, loc

    out = {}
    stats = collections.Counter()
    for n, q in enumerate(sorted(quests, key=lambda q: q["title"]), start=1):
        page = parse_page(pages.get(q["title"], ""))
        kind = kind_of(q, page)
        coords = q.get("coords") or []
        givers = q.get("givers") or page["givers"]
        takers = q.get("takers") or page["takers"] or givers
        q = dict(q, givers=givers, takers=takers)
        give_ids, give_loc = npc_types((givers or [None])[0], coords[0] if coords else "")
        take_ids, take_loc = npc_types((takers or [None])[0], coords[-1] if coords else "")
        if not take_ids:
            take_ids, take_loc = give_ids, give_loc
        rewards = q.get("reward") or page["reward_links"]
        rec = {
            "type": n,
            "kind": kind,
            "name": q["title"],
            "start_desc": q.get("start") or "",
            "notfinish_desc": q.get("notfinish") or "",
            "finish_desc": q.get("end") or "",
            "task": q.get("task") or "",
            "repeatable": 1 if q.get("repeatable") else 0,
            "party_size": 0,
            "level": page["level"],
            "loc": geo(coords[0]) if coords else 0,
            "finish_loc": geo(coords[-1]) if coords else -1,
            "rew_afro": page["rew_afro"],
            "rew_gold": page["rew_gold"] * 100,   # the client divides gold by 100
            "rew_items": rewards,
            "rew_choice": len(rewards) > 1,
            "rew_loc": 0,
            "need_quest": 0,
            "q_type": 0,
            "give": give_ids,
            "take": take_ids,
            "giver": (q.get("givers") or [""])[0],
            "taker": (q.get("takers") or [""])[0],
            "give_loc_id": give_loc,
            "take_loc_id": take_loc,
            "items": page["items"],
            "mobs": page["mobs"],
            "parents": page["parents"],
            "children": page["children"],
            "strings": {"name": STRING_BASE + 4 * n, "start": STRING_BASE + 4 * n + 1,
                        "notfinish": STRING_BASE + 4 * n + 2,
                        "finish": STRING_BASE + 4 * n + 3},
            "bound": bool(give_ids),
            "source": "https://lava-online.fandom.com/ru/wiki/" + q["title"].replace(" ", "_"),
        }
        if not give_ids:
            rec["note"] = ("giver has no type id yet" if q.get("givers")
                           else "giver unknown on the wiki")
        out[str(n)] = rec
        stats[kind] += 1
        stats["bound" if give_ids else "unbound"] += 1
        if give_loc:
            stats["with location"] += 1

    path = os.path.join(HERE, "quests_wiki.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({
            "_": "Quests from the wiki (CC-BY-SA) in the shape of quests.md §1: "
                 "kind by verb, the three texts, give/take as NPC type ids "
                 "through data/npc_wiki.json (bound=false where the giver has "
                 "none), loc/finish_loc as packed map cells, rewards as item "
                 "page titles until data/wiki_links.json maps them. Built by "
                 "data/build_quests_wiki.py.",
            "string_base": STRING_BASE,
            "quests": out,
        }, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    givers = collections.Counter(q["giver"] for q in out.values() if not q["bound"])
    print("quests: %d; bound to a giver type id: %d; unbound: %d; with a location: %d" % (
        len(out), stats["bound"], stats["unbound"], stats["with location"]))
    print("kinds:", {k: stats[k] for k in ("kill_mobs", "bring_l_obj", "del_obj")})
    print("levels set: %d, afro rewards: %d, gold rewards: %d" % (
        sum(1 for q in out.values() if q["level"]),
        sum(1 for q in out.values() if q["rew_afro"]),
        sum(1 for q in out.values() if q["rew_gold"])))
    print("top unbound givers:", givers.most_common(12))
    print("written", path)


if __name__ == "__main__":
    main()
