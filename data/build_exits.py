"""Build data/exits.json (doors into interiors) and data/settlements_wiki.json.

The client sends chWorld;to=1 and nothing else when a player leaves a
location; the side is read off outzones (data/exits_sides.json). Sides
W/N/E/S lead to the neighbouring map cell and need no table: the server
looks the cell up in settlements.json or opens the desert tile. Sides a and
b are doors into interiors, and where each door led was in the serverdata
node that was emptied in every file. This script rebuilds that table from
three weaker sources, each pick carrying its confidence and its source:

  wiki    the 192 location pages list sub-locations ("==Локации==") and
          name their parent in "==Координаты==" ([[Бункер Мантикоры]] under
          "Бункер Мантикоры II"); both ends are resolved to static files by
          title, region-aware (Resolver of data/build_npc_wiki.py)
  fn      files built as one family share a name stem and differ by a
          suffix: WH_Stone_Mine_N / _C / _S / _E2 / _W2, Prison_1..5_WH,
          Arenda_tt_I..IV, X_Enter / X_lvl1 / X_lvl2, Up_Camp_6LVL_01 /
          _boss. The member with map sides is the entrance; the others hang
          off it in suffix order
  single  an interior with one door and one known relative: the door goes
          back to it

Door a is taken as the way forward (deeper) and b the way back; the wiki
never says which letter is which, so an a/b pair that both resolve is
rated low. Everything unresolved is listed too, so the gaps are visible.

settlements_wiki.json proposes map cells for named locations from the
wiki's coordinates (location pages and NPC pages), with a tolerance of
three cells and a confidence. It never touches settlements.json or
settlements_verified.json; a person moves entries over after standing on
the cell.

    wsl.exe -e python3 data/build_exits.py
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
from build_npc_wiki import (CITIES, CITY_ALIAS, XY, Resolver, city_of_internal,  # noqa: E402
                            links, npc_spawns, sections, settlement_cells,
                            static_index)

MAP_SIDES = "WNES"


def dump(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def family_key(fn):
    """The stem shared by files built as one place with several rooms."""
    key = fn
    for _ in range(3):
        key = re.sub(r"(_(lvl|Lvl|LVL)_?\d+[a-z]?|_[IVX]+|_[Ee]nter|_Sorting|"
                     r"_Transport|_boss|_[NSEWC]\d?|_\d+|_glavaria_klana|"
                     r"_old|_new|_in|_out|_up|_dwn|_top|_bottom|_room\d*|"
                     r"_floor\d*|_[A-Z])$", "", key)
    return key


def suffix_rank(fn):
    """Order within a family: lvl2 after lvl1, _S after _N, boss last."""
    m = re.search(r"(?:lvl|Lvl|LVL)_?(\d+)", fn)
    if m:
        return 10 + int(m.group(1))
    m = re.search(r"_(\d+)$", fn)
    if m:
        return 10 + int(m.group(1))
    m = re.search(r"_([IVX]+)$", fn)
    if m:
        roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
        return 10 + roman.get(m.group(1), 9)
    if re.search(r"_boss$", fn):
        return 99
    if re.search(r"_[Ee]nter$", fn):
        return 0
    return 5


def main():
    static = static_index()
    with io.open(os.path.join(HERE, "wiki_world", "locations.json"), encoding="utf-8") as fh:
        loc_pages = json.load(fh)["pages"]
    with io.open(os.path.join(HERE, "npc_wiki.json"), encoding="utf-8") as fh:
        npcs = json.load(fh)["npcs"]
    mt = world.mob_types()
    cells = settlement_cells()

    spawn_city = {}
    for loc_id in static:
        votes = collections.Counter(city_of_internal(name)
                                    for _t, _r, name in npc_spawns(loc_id, mt))
        votes.pop(None, None)
        if votes:
            city, n = votes.most_common(1)[0]
            if n >= 2 and n > sum(votes.values()) / 2:
                spawn_city[loc_id] = city
    resolver = Resolver(static, cells, loc_pages, spawn_city)

    # --- wiki: parents and sub-locations of every location page ------------
    wiki = {}
    for title, txt in loc_pages.items():
        rec = {"subs": [], "parents": [], "city": None, "xy": None, "npcs": []}
        for lvl, name, body in sections(txt):
            key = name.strip("'").replace(":", "").strip()
            if key.startswith("Координ"):
                for target, _l in links(body):
                    if target in CITIES:
                        rec["city"] = rec["city"] or CITY_ALIAS.get(target, target)
                    else:
                        rec["parents"].append(target)
                m = XY.search(body) or XY.search(name)
                if m:
                    rec["xy"] = (int(m.group(1)), int(m.group(2)))
            elif key in ("Локации", "Под локации", "Подлокации"):
                rec["subs"] += [t for t, _l in links(body)]
            elif key.upper().startswith("NPC") or key.startswith("НПС"):
                rec["npcs"] += [t for t, _l in links(body)]
            elif lvl == 2 and key in CITIES and rec["city"] is None:
                rec["city"] = CITY_ALIAS.get(key, key)
        if rec["xy"] is None:
            m = XY.search(txt)
            if m:
                rec["xy"] = (int(m.group(1)), int(m.group(2)))
        wiki[title] = rec

    resolved = {}
    for title, rec in wiki.items():
        ids, how, city = resolver.resolve(title, rec["xy"], rec["city"])
        resolved[title] = {"loc_ids": ids, "how": how, "city": city}

    def files_of(title, city_hint=None):
        if title in resolved and resolved[title]["loc_ids"]:
            return resolved[title]["loc_ids"]
        ids, _how, _city = resolver.resolve(title, None, city_hint)
        return ids

    # Relations between wiki pages, both directions.
    related = collections.defaultdict(set)   # static id -> {(static id, source)}
    wiki_pairs = 0
    for title, rec in wiki.items():
        here = resolved[title]["loc_ids"]
        if not here:
            continue
        for other in rec["subs"] + rec["parents"]:
            there = files_of(other, resolved[title]["city"])
            if not there:
                continue
            wiki_pairs += 1
            for a in here:
                for b in there:
                    if a != b:
                        related[a].add((b, "wiki"))
                        related[b].add((a, "wiki"))

    # --- fn families: a chain in suffix order -------------------------------
    # The entrance (the member with map sides, or the lowest suffix) opens
    # on the first room, each room on the next; a room's b goes back, its
    # a goes on. Families of two are a plain pair and rate better.
    def is_interior(i):
        return not any(s in MAP_SIDES for s in static[i]["sides"])

    def has_door(i):
        return any(s in "ab" for s in static[i]["sides"])

    families = collections.defaultdict(list)
    for loc_id, m in static.items():
        if "test" in m["fn"].lower():
            continue
        families[family_key(m["fn"])].append(loc_id)
    chain_prev, chain_next, fam_size = {}, {}, {}
    for key, members in families.items():
        members = [i for i in members if has_door(i) or not is_interior(i)]
        if len(members) < 2 or len(members) > 30:
            continue
        # Arenda_tt_I..IV are four copies of one rental office, one per
        # city, not four rooms of one: same title, same sides, no chain.
        shapes = {(static[i]["title"], "".join(static[i]["sides"])) for i in members}
        if len(shapes) == 1:
            continue
        members.sort(key=lambda i: (is_interior(i), suffix_rank(static[i]["fn"]), i))
        for n, i in enumerate(members):
            fam_size[i] = len(members)
            if n > 0:
                chain_prev[i] = members[n - 1]
            if n + 1 < len(members):
                chain_next[i] = members[n + 1]

    # --- doors --------------------------------------------------------------
    doors, unresolved = {}, {}
    n_doors = n_bound = 0
    for loc_id in sorted(static, key=int):
        m = static[loc_id]
        sides = [s for s in m["sides"] if s in "ab"]
        if not sides:
            continue
        n_doors += len(sides)
        fam = family_key(m["fn"])
        # Candidates: wiki relations that have a door to come back through,
        # then the family neighbours.
        cands = []
        for other, source in sorted(related.get(loc_id, ()), key=lambda p: p[0]):
            if source == "wiki" and other in static and has_door(other):
                cands.append((other, "wiki"))
        for other in (chain_prev.get(loc_id), chain_next.get(loc_id)):
            if other is not None and other not in [c for c, _s in cands]:
                cands.append((other, "fn"))
        back = [c for c in cands if not is_interior(c[0]) or c[0] == chain_prev.get(loc_id)]
        forward = [c for c in cands if c not in back]
        entries = []
        for side in sides:
            pool = None
            if side == "b" and back:
                pool = back
            elif side == "a" and forward:
                pool = forward
            elif side == "a" and back and "b" not in sides:
                pool = back
            elif side == "b" and forward and "a" not in sides:
                pool = forward
            elif cands:
                pool = cands
            if not pool:
                entries.append({"side": side, "cells": m["door_cells"].get(side, []),
                                "target_loc_id": None, "confidence": "none",
                                "source": None, "alternatives": []})
                continue
            target, source = pool[0]
            alts = [t for t, _s in pool[1:]]
            if source == "wiki" and len(pool) == 1 and len(sides) == 1:
                conf = "high"
            elif source == "wiki" and len(pool) == 1:
                conf = "medium"
            elif source == "fn" and fam_size.get(loc_id) == 2 and len(sides) == 1:
                conf = "medium"
            else:
                conf = "low"
            entries.append({"side": side, "cells": m["door_cells"].get(side, []),
                            "target_loc_id": target, "confidence": conf,
                            "source": source, "alternatives": alts[:6],
                            "target_title": static[target]["title"],
                            "target_fn": static[target]["fn"]})
            n_bound += 1
        doors[str(loc_id)] = {"fn": m["fn"], "title": m["title"], "family": fam,
                              "doors": entries}
        if any(e["target_loc_id"] is None for e in entries):
            unresolved[str(loc_id)] = [e["side"] for e in entries if e["target_loc_id"] is None]

    dump(os.path.join(HERE, "exits.json"), {
        "_": "Doors (outzones side a/b) -> target static location. Sides "
             "W/N/E/S are not here: they lead to the neighbouring map cell "
             "(settlements.json or desert). confidence high/medium/low; "
             "source wiki (sub-location lists and parents on the location "
             "pages, CC-BY-SA), fn (files built as one family), single. "
             "a = forward/deeper, b = back, by convention, unverified. "
             "Built by data/build_exits.py.",
        "doors": doors,
        "unresolved": unresolved,
        "wiki_resolution": {t: r for t, r in resolved.items()},
    })

    # --- settlements_wiki.json -------------------------------------------------
    by_loc = collections.defaultdict(list)
    for cell, loc in cells.items():
        by_loc[loc].append(cell)

    claims = []
    for title, rec in wiki.items():
        if rec["xy"] and resolved[title]["loc_ids"]:
            claims.append((rec["xy"], resolved[title]["loc_ids"], "location:" + title))
    for title, rec in npcs.items():
        for p in rec["places"]:
            if p.get("xy") and p["loc_ids"] and p["how"] in ("title", "title+cell"):
                claims.append((tuple(p["xy"]), p["loc_ids"], "npc:" + title))

    proposals = collections.defaultdict(lambda: {"claims": [], "candidates": collections.Counter()})
    for xy, ids, source in claims:
        key = "%d,%d" % xy
        proposals[key]["claims"].append({"source": source, "loc_ids": ids})
        for i in ids:
            proposals[key]["candidates"][i] += 1

    out = {}
    for key, rec in proposals.items():
        x, y = (int(v) for v in key.split(","))
        existing = cells.get((x, y))
        ranked = rec["candidates"].most_common()
        top, votes = ranked[0]
        near_same = [c for c in by_loc.get(top, ()) if abs(c[0] - x) <= 3 and abs(c[1] - y) <= 3]
        far = [c for c in by_loc.get(top, ()) if c not in near_same]
        if existing == top:
            status, conf = "already", "verified"
        elif near_same:
            status, conf = "consistent", "high"
        elif existing is not None:
            status, conf = "occupied", "low"
        elif far:
            status, conf = "conflict", "low"
        elif len(ranked) == 1 and votes >= 2 and not any(s in MAP_SIDES for s in []) :
            status, conf = "proposed", "medium"
        elif len(ranked) == 1:
            status, conf = "proposed", "low"
        else:
            status, conf = "ambiguous", "low"
        # An interior cannot stand on a map cell.
        if not any(s in MAP_SIDES for s in static[top]["sides"]):
            status, conf = "interior", "none"
        out[key] = {
            "loc_id": top, "title": static[top]["title"], "fn": static[top]["fn"],
            "confidence": conf, "status": status, "votes": votes,
            "other_candidates": [{"loc_id": i, "title": static[i]["title"], "votes": n}
                                 for i, n in ranked[1:6]],
            "existing_loc_id": existing,
            "known_cells_of_loc": ["%d,%d" % c for c in by_loc.get(top, ())],
            "claims": rec["claims"],
        }
    dump(os.path.join(HERE, "settlements_wiki.json"), {
        "_": "Map cell -> location proposed from wiki coordinates (location "
             "pages and NPC pages, CC-BY-SA), tolerance 3 cells. status: "
             "already (same as settlements.json), consistent (the location "
             "is pinned within 3 cells), proposed (free cell, one candidate), "
             "ambiguous (several candidates), occupied (cell taken by another "
             "location), conflict (location pinned elsewhere), interior "
             "(file has no map side). Nothing here is applied: move a row "
             "into settlements_verified.json after standing on it. Built by "
             "data/build_exits.py.",
        "cells": dict(sorted(out.items())),
    })

    n_files = len(doors)
    n_full = sum(1 for d in doors.values() if all(e["target_loc_id"] for e in d["doors"]))
    by_conf = collections.Counter(e["confidence"] for d in doors.values() for e in d["doors"])
    by_src = collections.Counter(e["source"] for d in doors.values() for e in d["doors"] if e["source"])
    print("wiki location pages: %d, resolved to files: %d, wiki pairs: %d" % (
        len(wiki), sum(1 for r in resolved.values() if r["loc_ids"]), wiki_pairs))
    print("files with doors: %d, door sides: %d, with a target: %d, files fully "
          "resolved: %d" % (n_files, n_doors, n_bound, n_full))
    print("by confidence:", dict(by_conf), "by source:", dict(by_src))
    st = collections.Counter(v["status"] for v in out.values())
    print("settlement proposals: %d cells, status: %s" % (len(out), dict(st)))


if __name__ == "__main__":
    main()
