"""Design stand-ins for the creatures the client cannot draw: data/spawn_substitutes.json.

The location files spawn 2947 distinct creature types; 664 of them are gone
from the shipped res/database/mobs.xml (recon/analysis/data.md §4), so the
server skips them and the battle camps open empty: Up_Camp_06LVL_03_boss
lists two creatures the client has no record of, and nothing else that can
fight. This table maps each such type id to a known creature of the SAME
FACTION and the NEAREST LEVEL, so that a camp holds the kind of fighters it
was built for. It is a DESIGN, not a recovery: the original creature is
unknowable, only its company and its level are.

Faction
  The camp files name their faction outright: Bandit_Camp3 and every
  Up_Camp_*LVL_03* are "Лагерь Джанджавидов", whose known inhabitants are
  ja_box_ammo, and the known ja_* creatures (ja_Boevik_lvl4 ...) share the
  prefix. CAMP_FACTIONS is that reading of the ten camp families, checked
  below against the prefixes actually found in each family's files. Any
  other file takes the faction its known hostile inhabitants carry in their
  own prefix, when two or more of them agree and no other prefix rivals
  them. A type standing in files of two factions, or in files with no
  faction, is left unresolved: a wrong company is worse than an empty slot.

Level
  The camp level is in the file name (Up_Camp_07LVL_03_boss -> 7); elsewhere
  the median level of the file's known hostile inhabitants
  (data/mob_types.json); failing both, the faction's own median, marked so.

Choice
  Among the faction's known creatures of role "mob" the ones nearest the
  level, and within that group the k-th for the k-th unknown id of the file,
  so that a camp of four unknowns gets four different fighters rather than
  four copies of one.

    wsl.exe -e python3 data/build_spawn_substitutes.py
"""
import collections
import io
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

# Camp family number (Bandit_CampN, Up_Camp_*LVL_NN) -> faction prefix.
CAMP_FACTIONS = {
    1: "nc",   # Лагерь Новых Колонистов
    2: "lu",   # Лагерь Сектантов Люшеров
    3: "ja",   # Лагерь Джанджавидов
    4: "mg",   # Лагерь Магриба
    5: "st",   # Лагерь Работорговцев (slave traders)
    6: "zd",   # Лагерь Живодеров
    7: "jm",   # Лагерь ДСР
    8: "pc",   # Лагерь Миротворцев (peacekeepers)
    9: "pt",   # Лагерь Пиратов Сомали
    10: "na",  # Лагерь Северного Альянса
    11: "na",  # База Северного Альянса
}
# Prefixes that are a season or a test, never a company.
EVENT_PREFIXES = {"vov", "may", "event", "eventboss", "test", "admin", "ny",
                  "hw", "xmas", "vbg", "clan", "kb"}
MIN_POOL = 3


def prefix_of(name):
    m = re.match(r"^([A-Za-z]+?)_", name)
    return m.group(1).lower() if m else None


def camp_family(fn):
    m = re.match(r"^Bandit_Camp_?(\d+)$", fn)
    if m:
        return int(m.group(1))
    m = re.match(r"^Up_Camp_\d+LVL_(\d+)", fn)
    if m:
        return int(m.group(1))
    return None


def camp_level(fn):
    m = re.search(r"(\d+)LVL", fn)
    return int(m.group(1)) if m else None


def main():
    mt = world.mob_types()
    with io.open(os.path.join(HERE, "mob_types.json"), encoding="utf-8") as fh:
        types = {int(k): v for k, v in json.load(fh)["types"].items()}

    # Faction pools: known hostile creatures of role "mob" by prefix.
    pools = collections.defaultdict(list)
    for tid, rec in types.items():
        if rec["root"] != 0 or rec["role"] != "mob":
            continue
        p = prefix_of(rec["name"])
        if p and p not in EVENT_PREFIXES:
            pools[p].append(tid)
    pools = {p: sorted(v) for p, v in pools.items() if len(v) >= MIN_POOL}

    # Every file: its unknown types, its faction, its level.
    d = os.path.join(world.RES, "locations", "static")
    files = {}
    family_prefixes = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(d), key=lambda s: int(s[:-4])):
        if not fn.endswith(".xml"):
            continue
        i = int(fn[:-4])
        loc = world.location(i)
        unknown = collections.Counter(t for _c, t in loc.spawns if t and t not in mt)
        if not unknown and camp_family(loc.fn) is None:
            continue
        votes = collections.Counter()
        levels = []
        fam = camp_family(loc.fn)
        for _c, t in loc.spawns:
            if t in mt and mt[t][0] == 0 and t in types:
                p = prefix_of(mt[t][1])
                # The camp table is checked against everything known that
                # stands in the family, ammo boxes included (ja_box_ammo).
                if fam is not None and p:
                    family_prefixes[fam][p] += 1
                if types[t]["role"] == "object":
                    continue
                if p in pools:
                    votes[p] += 1
                levels.append(types[t]["level"])
        faction, how = None, ""
        if fam in CAMP_FACTIONS:
            faction, how = CAMP_FACTIONS[fam], "camp_fn"
        elif votes:
            p, n = votes.most_common(1)[0]
            if n >= 2 and n > sum(votes.values()) / 2:
                faction, how = p, "neighbours"
        level, lsrc = camp_level(loc.fn), "fn"
        if level is None and levels:
            level, lsrc = int(statistics.median(levels)), "neighbours"
        if level is None:
            lsrc = ""
        files[i] = dict(fn=loc.fn, title=loc.title, war=loc.war, unknown=unknown,
                        faction=faction, how=how, level=level, level_source=lsrc)

    # Check the camp table against what the files hold.
    for fam, want in sorted(CAMP_FACTIONS.items()):
        seen = family_prefixes.get(fam, collections.Counter())
        top = seen.most_common(1)[0][0] if seen else None
        flag = "" if top in (want, None) else "  <-- files say %s" % dict(seen)
        print("camp family %2d -> %s (files: %s)%s" % (fam, want, dict(seen) or "no known hostiles", flag))

    # One faction and one level per unknown type, from the files it stands in.
    homes = collections.defaultdict(list)
    for i, f in files.items():
        for t, n in f["unknown"].items():
            homes[t].append((i, n))
    subs, unresolved = {}, {}
    faction_median = {p: int(statistics.median(types[t]["level"] for t in ids))
                      for p, ids in pools.items()}
    for t, where in sorted(homes.items()):
        votes = collections.Counter()
        levels = []
        hows = {}
        for i, n in where:
            f = files[i]
            if f["faction"]:
                votes[f["faction"]] += n
                hows.setdefault(f["faction"], f["how"])
            if f["level"] is not None:
                levels.append(f["level"])
        if not votes:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where), reason="фракция не определена")
            continue
        ranked = votes.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where),
                                      reason="файлы разных фракций: %s" % dict(votes))
            continue
        faction = ranked[0][0]
        if faction not in pools:
            unresolved[str(t)] = dict(files=sorted(i for i, _n in where),
                                      reason="у фракции %s нет известных бойцов" % faction)
            continue
        if levels:
            level, lsrc = int(statistics.median(levels)), "files"
        else:
            level, lsrc = faction_median[faction], "faction_median"
        # The k-th unknown of the home file takes the k-th nearest creature.
        home = max(where, key=lambda p: (p[1], -p[0]))[0]
        siblings = sorted(files[home]["unknown"])
        k = siblings.index(t)
        ranked_pool = sorted(pools[faction], key=lambda x: (abs(types[x]["level"] - level), mt[x][1]))
        best = abs(types[ranked_pool[0]]["level"] - level)
        nearest = [x for x in ranked_pool if abs(types[x]["level"] - level) == best]
        pick = nearest[k % len(nearest)]
        subs[str(t)] = dict(type_id=pick, name=mt[pick][1], faction=faction,
                            level=level, level_source=lsrc, picked_level=types[pick]["level"],
                            files=sorted(i for i, _n in where), how=hows[faction])

    out = {
        "_": "DESIGNED, not recovered: unknown spawn type id (absent from the "
             "client's mobs.xml) -> a known creature of the same faction and the "
             "nearest level, so that battle camps are not empty. Applied by "
             "server/rooms.py only in war=1 locations and only for hostile "
             "(root 0) creatures. faction = name prefix (ja_ Джанджавиды, mg_ "
             "Магриб, nc_ Новые Колонисты, lu_ Люшер, st_ Работорговцы, zd_ "
             "Живодеры, jm_ ДСР, pc_ Миротворцы, pt_ Пираты, na_ Северный "
             "Альянс, ...); how = camp_fn (Bandit_CampN / Up_Camp_*LVL_NN) or "
             "neighbours (prefix of the known hostiles in the same file); level "
             "from the file name (*LVL), the known neighbours, or the faction's "
             "median. Built by data/build_spawn_substitutes.py.",
        "designed": True,
        "camp_factions": {str(k): v for k, v in CAMP_FACTIONS.items()},
        "pools": {p: len(v) for p, v in sorted(pools.items())},
        "substitutes": subs,
        "unresolved": unresolved,
    }
    path = os.path.join(HERE, "spawn_substitutes.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    reasons = collections.Counter(u["reason"].split(":")[0] for u in unresolved.values())
    by_how = collections.Counter(s["how"] for s in subs.values())
    print("unknown types: %d; substituted: %d (%s); unresolved: %d (%s)" % (
        len(homes), len(subs), dict(by_how), len(unresolved), dict(reasons)))
    print("pools:", {p: len(v) for p, v in sorted(pools.items())})
    print("written to", path)


if __name__ == "__main__":
    main()
