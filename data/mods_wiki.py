"""Blueprints and weapon modifications off the wiki -> data/mods_wiki.json.

    wsl.exe -e python3 data/mods_wiki.py

Two sources describe the upgrader's work:

  * the 198 "Чертежи" articles - one blueprint per effect and level
    ("Урон (10у)", "Заточка Кукри (18у)"): what it changes, its price,
    which mobs drop it, which quests use it, and the type_id it maps to;
  * the 278 "<gun> Mod IX" articles - the modified weapon itself, whose
    description states the effect ("У оружия увеличен размер обоймы до 31
    патрона") and whose table holds the modified figures.

The effects are parsed into numbers where the text gives them; the Mod
numeral -> _mod_* suffix table is shared with wiki_links.py.
"""
import collections
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import HERE, ROMAN, load_pages, load_json, categories, clean_cell, dump_json
from wiki_links import MOD_SUFFIX, KNIFE_MOD, BLUEPRINT_EFFECT, BLUEPRINT_COMBO, KNIFE_BLUEPRINT

LINKS = os.path.join(HERE, "wiki_links.json")
ITEMS = os.path.join(HERE, "wiki_items.json")
OUT = os.path.join(HERE, "mods_wiki.json")

TITLE = re.compile(r"^(.*?)\s*\((\d+)\s*у\)$")
KNIFE_TITLE = re.compile(r"^(Заточка и Эргономика|Заточка|Эргономика)\s+(.+?)\s*\((\d+)у\)$")
MOD_TITLE = re.compile(r"^(.*?)\s+Mod\s*([IVX]+)\s*$")
BP_DESC = re.compile(r"'''Описание'''\s*\n(.+?)(?:\n\s*\n|\n\*)", re.S)

# (regex over the effect text, field, value transform). Percentages are
# kept as signed percent, counts as signed units.
EFFECTS = [
    (r"Урон\s*\+\s*(\d+)\s*%?", "damage_pct", int),
    (r"повреждение на (\d+)\s*%", "damage_pct", int),
    (r"на (\d+)\s*% (?:увеличены|улучшены) убойные", "damage_pct", int),
    (r"Вес\s*-\s*(\d+)\s*%", "weight_pct", lambda v: -int(v)),
    (r"Вес[^.]*?снижен на (\d+)\s*%", "weight_pct", lambda v: -int(v)),
    (r"на (\d+)\s*% легче", "weight_pct", lambda v: -int(v)),
    (r"Броня\s*\+\s*(\d+)\s*%", "armor_pct", int),
    (r"Восприятие\s*\+\s*(\d+)", "perception", int),
    (r"Ловкость\s*\+\s*(\d+)", "agility", int),
    (r"Время прицеливания\s*-\s*(\d+)\s*%", "aim_time_pct", lambda v: -int(v)),
    (r"ОД на перезарядку\s*-\s*(\d+)\s*%", "reload_cost_pct", lambda v: -int(v)),
    (r"Прочность\s*\+\s*(\d+)\s*%", "durability_pct", int),
    (r"Прочность увеличена в (\d+) раза", "durability_x", int),
    (r"ОД на выстрел\s*-\s*(\d+)\s*%", "fire_cost_pct", lambda v: -int(v)),
    (r"Точность(?: стрельбы из оружия повышена на|\s*\+)\s*(\d+)\s*%", "precision_pct", int),
    (r"дальность стрельбы на (\d+) единиц", "max_range", int),
    (r"размер обоймы до (\d+)", "clip_size", int),
    (r"выносливость\s*\+\s*(\d+)\s*%", "stamina_pct", int),
]
FLAGS = [
    (r"дальнобойност", "max_range_up"),
    (r"размер обоймы увеличен|увеличена обойма|увеличить размер обоймы|Увеличен размер обоймы", "clip_size_up"),
    (r"Скорость перезарядки увеличена", "reload_speed_up"),
    (r"дальность эффективн", "max_range_up"),
    (r"увеличите\s*Урон|заточк", "damage_up"),
    (r"Очки действия|эргономик", "action_points_down"),
]


def parse_effects(text):
    out = {}
    t = re.sub(r"\s+", " ", clean_cell(text))
    for pat, field, conv in EFFECTS:
        m = re.search(pat, t, re.I)
        if m and field not in out:
            out[field] = conv(m.group(1))
    for pat, flag in FLAGS:
        if re.search(pat, t, re.I):
            out.setdefault(flag, True)
    return out


def blueprint_target(effect):
    if effect in ("Броня", "Броня и вес", "Вес", "Восприятие", "Ловкость", "Прочность"):
        return "wear or weapon"
    return "weapon"


def main():
    pages = load_pages()
    links = load_json(LINKS)["pages"]
    items = load_json(ITEMS)

    blueprints = {}
    for title, page in sorted(pages.items()):
        if page["ns"] != 0 or "Чертежи" not in categories(page):
            continue
        txt = page["wikitext"]
        rec = dict(level=None, effect=None, target=None, key=None, effects={},
                   description="", price=items.get(title, {}).get("price", {}),
                   mobs=items.get(title, {}).get("lists", {}).get("mobs", []),
                   quests=items.get(title, {}).get("lists", {}).get("quests", []),
                   traders=items.get(title, {}).get("lists", {}).get("traders", []),
                   type_ids=[l["type_ids"] for l in links.get(title, {}).get("links", [])
                             if l["method"] == "blueprint"])
        rec["type_ids"] = sorted({t for ids in rec["type_ids"] for t in ids})
        m = BP_DESC.search(txt)
        if m:
            rec["description"] = re.sub(r"\s+", " ", clean_cell(m.group(1))).strip()
        km = KNIFE_TITLE.match(title)
        tm = TITLE.match(title)
        if km:
            rec.update(level=int(km.group(3)), effect=km.group(1), target="knife " + km.group(2),
                       key="knife_" + KNIFE_BLUEPRINT[km.group(1)])
            rec["effects"] = {"damage_up": "Заточка" in km.group(1),
                              "action_points_down": "Эргономика" in km.group(1)}
        elif tm:
            effect = tm.group(1).strip()
            rec.update(level=int(tm.group(2)), effect=effect)
            if effect.startswith("Зашифрованный"):
                rec.update(target="any", key="codified")
            else:
                rec.update(target=blueprint_target(effect),
                           key=BLUEPRINT_EFFECT.get(effect) or BLUEPRINT_COMBO.get(effect))
            rec["effects"] = parse_effects(rec["description"])
        blueprints[title] = rec

    mod_pages = {}
    table = collections.defaultdict(lambda: dict(pages=0, texts=collections.Counter(), effects=collections.Counter()))
    for title, page in sorted(pages.items()):
        if page["ns"] != 0:
            continue
        m = MOD_TITLE.match(title)
        cats = categories(page)
        if not m or not ({"Огнестрельное оружие", "Холодное оружие"} & set(cats)):
            continue
        roman = m.group(2)
        knife = "Холодное оружие" in cats and "Огнестрельное оружие" not in cats
        suffix = (KNIFE_MOD if knife else MOD_SUFFIX).get(roman)
        desc = items.get(title, {}).get("description", "")
        if knife:
            # Knife descriptions all mention the sharpening; the numeral says
            # which of the two changes the mod actually carries.
            eff = {k: True for k, on in (("damage_up", "damage" in (suffix or "")),
                                         ("action_points_down", "actionpoint" in (suffix or "")))
                   if on}
        else:
            eff = parse_effects(desc)
        link = links.get(title, {})
        mod_pages[title] = dict(
            base=m.group(1), roman=roman, suffix=suffix, knife=knife,
            description=desc, effects=eff,
            type_ids=sorted({t for l in link.get("links", []) if l["confidence"] >= 0.5
                             for t in l["type_ids"]}),
            confidence=link.get("confidence", 0))
        key = ("knife " if knife else "") + roman
        table[key]["pages"] += 1
        table[key]["suffix"] = suffix
        if desc:
            table[key]["texts"][re.sub(r"\d+", "N", desc)[:80]] += 1
        for k, v in eff.items():
            table[key]["effects"][k if isinstance(v, bool) else "%s=%s" % (k, v)] += 1
    mod_table = {}
    for key in sorted(table, key=lambda k: (k.startswith("knife"), ROMAN.get(k.split()[-1], 0))):
        t = table[key]
        mod_table[key] = dict(pages=t["pages"], suffix=t["suffix"],
                              typical=t["texts"].most_common(1)[0][0] if t["texts"] else "",
                              effects=dict(t["effects"].most_common(4)))

    meta = dict(
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        source="data/wiki (CC BY-SA, lava-online.fandom.com/ru)",
        blueprints=len(blueprints), mod_pages=len(mod_pages),
        blueprints_linked=sum(1 for b in blueprints.values() if b["type_ids"]),
        effect_fields="*_pct signed percent, perception/agility/max_range/clip_size "
                      "absolute, durability_x multiplier, *_up/_down flags when the "
                      "text gives no number")
    dump_json(OUT, dict(_meta=meta, blueprints=blueprints, mod_table=mod_table,
                        mod_pages=mod_pages))
    print("blueprints %d (%d linked), mod pages %d, mod numerals %d -> %s" % (
        len(blueprints), meta["blueprints_linked"], len(mod_pages), len(mod_table), OUT),
        file=sys.stderr)
    for k, v in mod_table.items():
        print("  Mod %-10s %3d pages  %-22s %s" % (k, v["pages"], v["suffix"], v["effects"]),
              file=sys.stderr)


if __name__ == "__main__":
    main()
