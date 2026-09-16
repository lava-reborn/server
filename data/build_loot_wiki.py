"""Build data/loot_wiki.json: which mob drops which item, with designed chances.

Nothing in the client says what a creature carries. The fan wiki does, in
two places that mirror each other: every trash-loot and quest-item page has
a "Мобы-хранители" list naming the group that drops it, and each of the 32
mob-group pages has a "Лут" section sorted into "Ценный", "Обычный" and
"Квестовый". Both are read and merged into one edge list.

The wiki names groups (Новые Колонисты, Секта Люшер, Собака), not client
types (m05_NewColonShotgun_lvl3, lu_Fanatic_lvl12, mStarvingDog). The bridge
is the camps: each camp location is titled after its faction (Лагерь Новых
Колонистов) and spawns types with one name prefix (nc_, m05_NewColon), so a
faction word maps to a prefix by counting who stands in which camp. The
animals and the stone are matched by transliteration, and the few that
neither method reaches are listed in GROUPS by hand.

Drop chances were never published; they are designed here per tier (the
wiki's own three headings) and marked as such. Item pages are still named
by title; the type ids behind them arrive with data/wiki_links.json.

Wiki text is CC-BY-SA (https://lava-online.fandom.com/ru).

    wsl.exe -e python3 data/build_loot_wiki.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402
from build_npc_wiki import LINK, links, sections, skel, tokens  # noqa: E402

# Designed: the wiki gives three tiers and no numbers. One roll per kill
# per listed item; quest loot drops only while the quest is open.
TIERS = {
    "Ценный": {"chance": 0.06, "quest_only": False},
    "Обычный": {"chance": 0.30, "quest_only": False},
    "Квестовый": {"chance": 0.25, "quest_only": True},
    "unknown": {"chance": 0.15, "quest_only": False},
}
MAX_DROPS_PER_KILL = 2

# Faction word in a wiki group name -> word in the camp titles of the
# client, so the camp census can say which name prefix the faction uses.
FACTION_WORDS = {
    "колонист": "колонист", "люшер": "люшер", "джанджавид": "джанджавид",
    "магриб": "магриб", "работорговц": "работорговц", "живодер": "живодер",
    "живодёр": "живодер", "дср": "дср", "миротворц": "миротворц",
    "пират": "пират", "альянс": "альянс", "мантикор": "мантикор",
    "туарег": "туарег", "бандит": "бандит",
}

# Groups no census reaches: a stem of the wiki name -> a pattern over the
# internal names. Stems, because the wiki says Гиена on one page and Гиены
# on the next.
GROUPS = [
    ("собак", r"Dog(?!_)|StarvingDog|Bich_Hangry_Dog"),
    ("гиен", r"Hyena"),
    ("крыс", r"^mRat"),
    ("антилоп", r"Antilope"),
    ("верблюд", r"^mCamel|kv_Camel"),
    ("крокодил", r"Crocodile"),
    ("козел", r"Kozel"),
    ("козёл", r"Kozel"),
    ("шакал", r"Jacal"),
    ("горная порода", r"Stone_(WH|DN|AH|NZ)$"),
    ("свинцовая порода", r"Stone_Plumbum"),
    ("медная порода", r"Stone_Copper"),
    ("селитр", r"Source_Nitre"),
    ("камень (дн)", r"^Stone_DN$"),
    ("камень (вх)", r"^Stone_WH$"),
    ("камень (ах)", r"^Stone_AH$"),
    ("камень", r"^Stone_(WH|DN|AH|NZ)$"),
    ("осколок скалы", r"_Rock$"),
    ("каторжник", r"prisoner"),
    ("мантикор", r"Manticore"),
    ("контрабандист", r"^me_"),
    ("караван", r"^kv_"),
    ("бандит", r"Bandit"),
    ("туарег", r"Touareg"),
    ("корова", r"nz_Cow"),
    ("кукуруза", r"CornPlant"),
    ("рейнджер", r"na_ranger"),
    ("меткий стрелок", r"na_sharpshooter"),
    ("дезертир", r"Desert|dezertir|na_scout"),
    ("бухгалтер", r"Kaznachei"),
    ("санденс кид", r"SundanceKid"),
    ("бен ганн", r"BenGann|Ben_Gann"),
]


def guardian_edges(pages, source):
    """(guardian, item, tier) from the item pages' Мобы-хранители lists."""
    out = []
    for title, txt in pages.items():
        for lvl, name, body in sections(txt):
            if name.startswith("Мобы-хранители") or name.startswith("Мобы хранители"):
                for target, _label in links(body):
                    out.append((target.strip(), title, "unknown", source))
    return out


def mob_page_edges(pages):
    """(group, item, tier) from the mob pages' Лут sections."""
    out = []
    for title, txt in pages.items():
        in_loot, tier = False, "unknown"
        for lvl, name, body in sections(txt):
            if lvl == 2:
                in_loot = name.startswith("Лут")
                tier = "unknown"
                if not in_loot:
                    continue
            elif in_loot and lvl >= 3:
                tier = "Квестовый" if name.startswith("Квест") else \
                    "Ценный" if name.startswith("Цен") else \
                    "Обычный" if name.startswith("Обыч") else "unknown"
            if in_loot:
                for target, _label in links(body):
                    out.append((title, target.strip(), tier, "mob_page"))
    return out


def camp_census(mt):
    """faction word -> Counter of name prefixes of the mobs in its camps."""
    static = os.path.join(world.RES, "locations", "static")
    census = collections.defaultdict(collections.Counter)
    for fn in os.listdir(static):
        if not fn.endswith(".xml"):
            continue
        txt = world._read(os.path.join(static, fn))
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        title = attrs.get("title", "").lower().replace("ё", "е")
        if not title.startswith("лагерь"):
            continue
        words = [w for w in FACTION_WORDS.values() if w in title]
        if not words:
            continue
        for c in world._chunks(txt, "mobs", 8):
            tid = int(c[4:8], 16)
            if tid in mt and mt[tid][0] == 0:
                name = mt[tid][1]
                prefix = re.match(r"^(m\d+_[A-Za-z]{2,6}|[a-z]{2,3}_|[A-Za-z]+_)", name)
                if prefix:
                    for w in words:
                        census[w][prefix.group(1)] += 1
    return census


def main():
    def load(stem):
        with io.open(os.path.join(HERE, "wiki_world", stem + ".json"),
                     encoding="utf-8") as fh:
            return json.load(fh)["pages"]

    mt = world.mob_types()
    mobs = {tid: name for tid, (root, name, _r) in mt.items() if root == 0}
    # "Мобы-хранители" of a quest item is often the townsman who hands it
    # over; those names are NPC pages already bound to type ids.
    npc_types = {}
    npc_path = os.path.join(HERE, "npc_wiki.json")
    if os.path.exists(npc_path):
        with io.open(npc_path, encoding="utf-8") as fh:
            for title, rec in json.load(fh)["npcs"].items():
                ids = sorted({p["type_id"] for p in rec["places"]
                             if p.get("type_id") and p["confidence"] != "low"})
                if ids:
                    npc_types[title] = ids

    edges = []
    for stem in ("trash_loot", "quest_items", "items"):
        edges += guardian_edges(load(stem), "item_page")
    edges += mob_page_edges(load("mobs"))
    # The same pair from both sides: keep the tier the mob page gives.
    merged = {}
    for group, item, tier, source in edges:
        key = (group, item)
        cur = merged.get(key)
        if cur is None or (cur["tier"] == "unknown" and tier != "unknown"):
            merged[key] = {"mob": group, "item": item, "tier": tier, "source": source}
        elif cur["source"] != source:
            cur["source"] = "both"
    edges = sorted(merged.values(), key=lambda e: (e["mob"], e["item"]))

    census = camp_census(mt)
    groups = {}
    for group in sorted({e["mob"] for e in edges}):
        low = group.lower().replace("ё", "е")
        pattern, how = None, "none"
        for word, camp_word in FACTION_WORDS.items():
            if word in low and census.get(camp_word):
                prefixes = [p for p, n in census[camp_word].most_common()
                            if n >= 2]
                if prefixes:
                    pattern = "^(" + "|".join(re.escape(p) for p in prefixes) + ")"
                    how = "camp"
                break
        if pattern is None:
            for stem, pat in GROUPS:
                if stem in low:
                    pattern, how = pat, "manual"
                    break
        type_ids = []
        if pattern:
            # Hand-written patterns may name a townsman's prop (the cow, the
            # corn), so they run over every type; the census over mobs only.
            pool = mobs if how == "camp" else {t: n for t, (r, n, _x) in mt.items()}
            type_ids = sorted(t for t, n in pool.items() if re.search(pattern, n))
        if not type_ids and group in npc_types:
            type_ids, how = list(npc_types[group]), "npc"
        if not type_ids:
            # Last resort: a word of the group name spelled in the type name.
            words = {skel(w) for w in re.split(r"[^А-Яа-яЁё]+", group) if len(w) >= 4}
            words = {w for w in words if len(w) >= 3}
            for t, n in mobs.items():
                toks = {skel(x) for x in tokens(n)}
                if words & toks:
                    type_ids.append(t)
            type_ids.sort()
            if type_ids:
                how = "translit"
        groups[group] = {"pattern": pattern, "how": how, "type_ids": type_ids,
                         "type_names": [mt[t][1] for t in type_ids[:8]]}

    # Item pages -> type ids, when the item linker has run.
    item_types = {}
    links_path = os.path.join(HERE, "wiki_links.json")
    if os.path.exists(links_path):
        try:
            with io.open(links_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            table = raw.get("pages") or raw.get("links") or raw
            for title, rec in table.items():
                if isinstance(rec, dict):
                    ids = rec.get("type_ids") or ([rec["type_id"]] if rec.get("type_id") else [])
                elif isinstance(rec, list):
                    ids = rec
                else:
                    ids = [rec]
                if ids:
                    item_types[title] = [int(i) for i in ids if str(i).isdigit()]
        except (OSError, ValueError, AttributeError):
            item_types = {}

    by_type = collections.defaultdict(list)
    for e in edges:
        g = groups[e["mob"]]
        for t in g["type_ids"]:
            by_type[str(t)].append({
                "item": e["item"], "tier": e["tier"],
                "chance": TIERS[e["tier"]]["chance"],
                "quest_only": TIERS[e["tier"]]["quest_only"],
                "item_type_ids": item_types.get(e["item"], []),
            })
    for lst in by_type.values():
        lst.sort(key=lambda d: (-d["chance"], d["item"]))

    out = {
        "_": "Mob -> item drop edges read off the wiki (CC-BY-SA, "
             "https://lava-online.fandom.com/ru): item pages' Мобы-хранители "
             "and mob pages' Лут. Groups are wiki names; type_ids are the "
             "client types they cover (how: camp = prefix census of the camp "
             "locations, manual, translit, none). Chances are DESIGNED per "
             "tier, not recovered. Built by data/build_loot_wiki.py.",
        "design": {"tiers": TIERS, "max_drops_per_kill": MAX_DROPS_PER_KILL,
                   "note": "one independent roll per listed item, at most "
                           "max_drops_per_kill successes kept, valuable first"},
        "groups": groups,
        "edges": edges,
        "by_type": dict(sorted(by_type.items(), key=lambda kv: int(kv[0]))),
        "item_types_linked": len(item_types),
    }
    path = os.path.join(HERE, "loot_wiki.json")
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    n_groups = len(groups)
    n_bound = sum(1 for g in groups.values() if g["type_ids"])
    e_bound = sum(1 for e in edges if groups[e["mob"]]["type_ids"])
    print("edges: %d (mob pages %d, item pages %d, both %d)" % (
        len(edges), sum(e["source"] == "mob_page" for e in edges),
        sum(e["source"] == "item_page" for e in edges),
        sum(e["source"] == "both" for e in edges)))
    print("groups: %d, with type ids: %d; edges with type ids: %d" %
          (n_groups, n_bound, e_bound))
    print("types with a drop list: %d; item pages linked to type ids: %d" %
          (len(by_type), len(item_types)))
    print("camp census:", {k: v.most_common(3) for k, v in census.items()})
    unbound = [g for g, r in groups.items() if not r["type_ids"]]
    print("unbound groups (%d): %s" % (len(unbound), ", ".join(unbound[:40])))
    print("written", path)


if __name__ == "__main__":
    main()
