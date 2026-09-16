"""Mass-produced firearms: wiki article <-> <class>_<index>_lvl_<level> line.

    wsl.exe -e python3 data/firearm_families.py   -> data/firearm_families.json

The client names 7073 guns by class, line index and level only
(pistols_1_lvl_4, plus _pm/_gold copies and _mod_* variants), the wiki
names real models (Glock 17). The only shared key is the class (wiki
category) and the required "Стрельба N" (= level), which leaves up to four
candidate lines per article. This pass narrows the candidates with what
else the two sides state:

  mods     an article lists its "Mod IX/XI" pages; the line must own the
           matching _mod_* variants (MOD_SUFFIX in wiki_links.py)
  tiers    an article with (P)/(G) columns needs a line with _pm/_gold copies

and resolves an article only when exactly one line fits it and no other
article at that class/level fits that line. Everything else stays a list
of candidates with confidence 0.6 / candidates; nothing is guessed.
Icon hashes (TASKS 7.5) are the next key for the remainder.
"""
import collections
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import (HERE, FIREARM_CLASS, MASS_FIREARM, load_objects, load_json,
                         parse_name, dump_json)
from wiki_links import MOD_SUFFIX, KNIFE_MOD

LINKS = os.path.join(HERE, "wiki_links.json")
ITEMS = os.path.join(HERE, "wiki_items.json")
OUT = os.path.join(HERE, "firearm_families.json")
MOD_TITLE = re.compile(r"^(.*?)\s+Mod\s*([IVX]+)\s*$")


def families(objects):
    """line base -> {class, index, level, members: {variant: id}, mods, tiers}."""
    fams = {}
    for tid, (root, name) in objects.items():
        m = MASS_FIREARM.match(name)
        if not m:
            continue
        base, tier, mod, extra = parse_name(name)
        if not MASS_FIREARM.match(base) or MASS_FIREARM.match(base).group(4):
            continue
        fam = fams.setdefault(base, dict(
            cls=m.group(1), index=int(m.group(2)), level=int(m.group(3)),
            members={}, extra={}))
        if mod == "speedshot":     # 17 names spell the shot-speed mod backwards
            mod = "shotspeed"
        key = tier + (":" + mod if mod else "")
        if extra:
            fam["extra"].setdefault(key + "+" + "_".join(extra), tid)
        else:
            fam["members"].setdefault(key, tid)
    for fam in fams.values():
        fam["mods"] = sorted({k.split(":")[1] for k in fam["members"] if ":" in k})
        fam["tiers"] = sorted({k.split(":")[0] for k in fam["members"]})
        # Lines that exist only as _mob copies are creature weapons.
        fam["mob_only"] = not fam["members"]
    return fams


def article_facts(title, rec, items):
    """(class list, base title, own mod, mods it lists, tiers its table has)."""
    m = MOD_TITLE.match(title)
    base = m.group(1) if m else title
    own = MOD_SUFFIX.get(m.group(2)) if m else None
    mods = set()
    for t in items.get(base, {}).get("lists", {}).get("modifications", []):
        mm = MOD_TITLE.match(t)
        if mm and mm.group(2) in MOD_SUFFIX:
            mods.add(MOD_SUFFIX[mm.group(2)])
    if own:
        mods.add(own)
    tiers = set()
    for l in rec["links"]:
        if l["method"] == "firearm_class_level":
            tiers.add(l["key"].split(" mod ")[0].split()[-1])
    return base, own, mods, tiers


def main():
    objects = load_objects()
    links = load_json(LINKS)["pages"]
    items = load_json(ITEMS)
    fams = families(objects)

    # Articles (per required level: a I..V table is one article at several
    # levels) that only have class + level to go on.
    articles = {}
    for title, rec in links.items():
        levels = collections.defaultdict(set)
        for l in rec["links"]:
            if l["method"] == "firearm_class_level":
                for c in l["candidates"]:
                    levels[l["level"]].add(c["family"])
        if not levels or rec["confidence"] >= 0.5:
            continue
        base, own, mods, tiers = article_facts(title, rec, items)
        for level, cands in levels.items():
            key = title if len(levels) == 1 else "%s @%d" % (title, level)
            articles[key] = dict(title=title, base=base, level=level, mod=own,
                                 mods=sorted(mods), tiers=sorted(tiers),
                                 candidates=sorted(cands))

    # Narrow with the evidence, then resolve unique pairs per class/level.
    by_pair = collections.defaultdict(list)
    for key, a in articles.items():
        fits = []
        for fam in a["candidates"]:
            f = fams.get(fam)
            if not f:
                continue
            if not set(a["mods"]) <= set(f["mods"]):
                continue
            if not set(a["tiers"]) <= set(f["tiers"]):
                continue
            fits.append(fam)
        a["compatible"] = fits
        if fits:
            f = fams[fits[0]]
            by_pair[(f["cls"], f["level"], a["mod"])].append(key)
        else:
            a["resolved"], a["confidence"], a["method"] = None, 0, "no compatible line"

    for pair, keys in by_pair.items():
        for key in keys:
            a = articles[key]
            fits = a["compatible"]
            rivals = [k for k in keys if k != key and articles[k]["base"] != a["base"]]
            # An article that fits one line only is that line, unless a
            # rival article also fits nothing but the same line.
            taken = any(articles[k]["compatible"] == fits for k in rivals)
            if len(fits) == 1 and not taken:
                only_pair = not rivals and len(a["candidates"]) == 1
                a["resolved"] = fits[0]
                a["confidence"] = 0.8 if only_pair else 0.6
                a["method"] = "unique pair" if only_pair else "mods/tiers fingerprint"
            else:
                a["resolved"] = None
                a["confidence"] = round(0.6 / len(fits), 2)
                a["method"] = "ambiguous: %d lines fit" % len(fits)

    # A Mod page follows its base article.
    for key, a in articles.items():
        if a["mod"] and not a["resolved"]:
            base = articles.get(a["base"]) or articles.get("%s @%d" % (a["base"], a["level"]))
            if base and base.get("resolved") and base["resolved"] in a["compatible"]:
                a["resolved"] = base["resolved"]
                a["confidence"] = base["confidence"]
                a["method"] = "follows " + base["title"]

    # Attach the outcome to the lines.
    for fam in fams.values():
        fam["wiki"], fam["wiki_confidence"], fam["wiki_candidates"] = None, 0, []
    for key, a in articles.items():
        for fam in a["compatible"]:
            if a["mod"]:
                continue
            f = fams[fam]
            f["wiki_candidates"].append(a["title"])
            if a["resolved"] == fam and a["confidence"] > f["wiki_confidence"]:
                f["wiki"], f["wiki_confidence"] = a["title"], a["confidence"]

    resolved = sum(1 for a in articles.values() if a["resolved"])
    lines_named = sum(1 for f in fams.values() if f["wiki"])
    meta = dict(
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        source="data/wiki_links.json + data/wiki_items.json + objects.xml",
        articles=len(articles), resolved=resolved,
        ambiguous=len(articles) - resolved, lines=len(fams), lines_named=lines_named,
        mod_suffix=MOD_SUFFIX, knife_mod=KNIFE_MOD,
        note="resolved = exactly one line fits the article's mods and tiers "
             "and no rival article fits it; confidence 0.8 when the class/level "
             "pair has one article and one line, 0.6 on the fingerprint; "
             "ambiguous articles keep their candidate list")
    dump_json(OUT, dict(_meta=meta, articles=articles,
                        lines={k: v for k, v in sorted(fams.items())}))
    print("articles %d: resolved %d, ambiguous %d; lines %d, named %d -> %s" % (
        len(articles), resolved, len(articles) - resolved, len(fams), lines_named, OUT),
        file=sys.stderr)
    counts = collections.Counter(a["method"].split(":")[0] for a in articles.values())
    print(dict(counts), file=sys.stderr)


if __name__ == "__main__":
    main()
