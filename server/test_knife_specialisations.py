"""Blade specialisation ladder: early knives remain usable without learning it."""
import os
import re
import sys

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory
import items
import progression
from testkit import check, fails

ch = progression.Character()
ch.skill[progression.MELEE][0] = 20
pattern = re.compile(r"knife_lvl(\d+)_(A|G)(_(damage|actionpoint|damage_actionpoints))?")
early, late, errors = [], [], []
for t, (root, name) in items.catalogue().items():
    m = pattern.fullmatch(name)
    if root != items.COLD_ARM or not m:
        continue
    level = int(m[1])
    row = dict(type_id=t, root=root)
    si = items.params_of(t)
    if level < 6:
        early.append(t)
        ch.spec[1][0] = -1
        if si.get("need_specs_m", 0) or not inventory.wearable(row, ch.level, ch):
            errors.append((t, "early knife unexpectedly needs specialisation"))
        continue
    late.append(t)
    needed = (level - 2) // 4
    if (si.get("need_specs_m"), si.get("need_specs")) != (2, [needed]):
        errors.append((t, "wrong declared requirement"))
    for spec, accepted in ((-1, False), (needed - 1, False), (needed, True)):
        ch.spec[1][0] = spec
        if inventory.wearable(row, ch.level, ch) != accepted:
            errors.append((t, "equip", spec))
        if (inventory.weapon_requirement_error(row, ch) is None) != accepted:
            errors.append((t, "use", spec))
    # Losing the specialisation must revoke the same permission.
    ch.spec[1][0] = -1
    if inventory.weapon_requirement_error(row, ch) is None:
        errors.append((t, "reset bypass"))

check("all twelve early variants including rock need no specialisation", len(early), 12)
check("all forty standard variants from level six are covered", len(late), 40)
check("declared ladder and equip/use/reset boundaries agree for every variant", errors, [])
new = progression.Character()
check("blade specialisation can be learned without first training it", new.learn_spec(1), 0)
check("learning starts at zero", new.spec_level(1), 0)
progression_character = progression.Character()
progression_character.skill[progression.MELEE][0] = 1
check("level-one melee with no specialisation can use the awl",
      inventory.wearable(dict(type_id=6229, root=items.COLD_ARM), 1, progression_character), True)
if fails:
    print("\n".join(fails))
    raise SystemExit(1)
