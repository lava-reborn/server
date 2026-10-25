"""Explicit completion of missing A/G services (owner request 2026-10-24).

Use documented Mod tables, not every placeholder modification in objects.xml.
Starter weapons have no Mod tables: damage and precision are designed services.
Samostrel uses existing level-1 blueprints, available to a level-0 player.
All existing recipes and their identifiers remain authoritative.
"""
import json
from pathlib import Path


DATA = Path(__file__).resolve().parent
FAMILIES = {
    "pistols_1_lvl_0": "halfa",
    "assault_rifle_1_lvl_1": "halfa",
    "pistols_1_lvl_6": "halfa",
    "sub_machine_guns_1_lvl_9": "dongola",
    "sub_machine_guns_2_lvl_9": "dongola",
    "sub_machine_guns_1_lvl_10": "dongola",
    **{"shotgun_%d_lvl_%d" % (i, level): "halfa"
       for level in range(9, 13) for i in (1, 2)},
    "machine_gun_2_lvl_16": "dongola",
    "assault_rifle_1_lvl_17": "abu_hamed",
}
STARTERS = {"pistols_1_lvl_0", "assault_rifle_1_lvl_1"}
MISSING_GUNS = frozenset({
    25562, 26242, 25657, 25320,
    25373, 25374, 25389, 25390, 25405, 25406,
    25983, 25984, 25996, 25997, 26009, 26010, 26022, 26023,
    26035, 26036, 26048, 26049, 26061, 26062, 26074, 26075,
})


def owns_recipe(row):
    """Keep completion keys stable even if a repaired source row now resolves."""
    c = row["craft"]
    return c["gun"] in MISSING_GUNS or (c["gun"] == 25006 and c["effect"] == "attrition_x2")


def additions(city, existing, *, blueprint, eligible, params, service,
              camp_mobs, titles):
    """New rows before numbering; callbacks use the builder's real catalogue.

    Halfa's shotgun masters also serve 9-12: Abri and Dongola have none.
    Its rifle apprentice handles the starter AK. Other cities keep their masters.
    """
    load = lambda name: json.loads((DATA / name).read_text(encoding="utf-8"))
    families = load("firearm_families.json")["lines"]
    wiki = load("items_wiki.json")["items"]
    seen = {(r["craft"]["gun"], r["craft"]["effect"])
            for r in existing if r.get("craft", {}).get("family") == "upgrade"}
    classes = {"pistols": "pistol", "assault_rifle": "assault",
               "shotgun": "shotgun", "sub_machine_guns": "smg", "machine_gun": "mg"}
    out = []
    for family, home in sorted(FAMILIES.items()):
        if home != city["name"]:
            continue
        entry = families[family]
        cls = classes[entry["cls"]]
        level = entry["level"]
        for line in ("A", "G"):
            gun = entry["members"].get(line)
            if str(gun) not in wiki or not eligible(gun):
                continue
            effects = {k.split(":", 1)[1] for k, t in entry["members"].items()
                       if k.startswith(line + ":") and str(t) in wiki}
            # A documented counterpart's service must not disappear merely
            # because this variant has no separate wiki article. Use only
            # existing matching modification types, never invent new items.
            effects |= {k.split(":", 1)[1] for k, t in entry["members"].items()
                        if k.startswith(("A:", "G:")) and str(t) in wiki
                        and entry["members"].get(line + ":" + k.split(":", 1)[1]) is not None}
            if not effects:
                # FN F2000 has no Mod tables: mirror the existing A recipes.
                bases = {entry["members"].get(v) for v in ("A", "G")}
                effects = {r["craft"]["effect"] for r in existing
                           if r.get("craft", {}).get("family") == "upgrade"
                           and r["craft"]["gun"] in bases}
            if family in STARTERS:
                effects = {"damage", "precision"}
            for effect in sorted(effects):
                if (gun, effect) in seen:
                    continue
                mod = entry["members"][line + ":" + effect]
                bp_level = max(level, 1)
                bp = blueprint(effect, bp_level, line)
                if not eligible(mod) or not eligible(bp):
                    raise ValueError("missing completion item: %s %s %s" % (family, line, effect))
                if params(mod)["max_break_abs"] < params(gun)["max_break_abs"]:
                    raise ValueError("completion would reduce durability: %s" % mod)
                masters = city["masters"].get((cls, line))
                if not masters:
                    raise ValueError("no completion master: %s %s %s" % (home, cls, line))
                name = wiki[str(gun)]["name_ru"] + (" (G)" if line == "G" else "")
                slot = {"obj": bp, "num": 1}
                chiefs = camp_mobs(city, bp_level, chiefs_only=True)
                if chiefs:
                    slot.update(mobs=chiefs, drop=0.1, one_of="craft_blueprint")
                craft = dict(family="upgrade", gun=gun, mod=mod, blueprint=bp,
                             effect=effect, line=line, level=level,
                             key="upgrade:%s:completion-%d-%s" % (home, gun, effect))
                if bp_level != level:
                    craft["blueprint_level"] = bp_level
                row = dict(
                    kind="bring_l_obj", name="%s: %s" % (name, titles[effect].lower()),
                    start=("Хочешь улучшить свое оружие? Мне нужен соответствующий чертеж и, "
                           "собственно, само оружие.<Br><b>Задача:</b> принести %s и "
                           "Чертеж: %s (%dу)<Br><Br><b>Внимание!!! Каждый экземпляр оружия "
                           "можно улучшить только один раз.</b>" % (name, titles[effect], bp_level)),
                    notfinish="Само собой ничего не сделается.", finish="Готово, пользуйся.",
                    give=list(masters), take=list(masters),
                    objs=[{"obj": gun, "num": 1}, slot], rew_obj=[mod], num_rew_obj=[1],
                    craft=craft,
                    why=("DESIGNED, owner 2026-10-24: complete missing A/G upgrades with "
                         "existing items; documented Mod tables, or damage/precision for "
                         "starter weapons. Samostrel uses level-1 blueprints. "
                         "Halfa shotgun masters also serve levels 9-12; its rifle apprentice "
                         "serves the starter AK. No existing recipe is replaced."))
                out.append(service(city, row))
                seen.add((gun, effect))
    return out
