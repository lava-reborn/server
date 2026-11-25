"""Supplies from native ammunition boxes in camp centres, once per corpse."""
from functools import lru_cache

import items


# Location and object type must both match: scenery/quest boxes, the side
# scenes and global encounters do not become additional supply sources.
BOXES = {
    80: 409, 81: 641, 84: 642, 85: 2162, 88: 2163, 92: 2164,
    93: 2165, 98: 2167, 132: 2169, 168: 2171, 263: 2171,
}
AMMO_COUNT = 50
HEALTH = (6055, 6056, 6057, 6058, 6059, 6060)
STAMINA = (6061, 6062, 6063, 6064, 6065, 6066)


@lru_cache(maxsize=1)
def ammunition():
    """One native A-OT type per released firearm calibre, never G/test ammo."""
    import shop_bands
    available = set()
    for type_id in shop_bands.wares():
        if items.root_of(type_id) != items.FIRE_ARM:
            continue
        for ammo in (items.params_of(type_id) or {}).get('comp_array', ()):
            root, name = items.catalogue().get(ammo, (None, ''))
            si = items.params_of(ammo) or {}
            if (root == items.AMMO and name.startswith('Ammo_') and name.endswith('_OT')
                    and si.get('cost', 0) > 0 and not si.get('g_cost')
                    and not items.out_of_game(ammo) and not items.acquisition_blocked(ammo)):
                available.add(ammo)
    return tuple(sorted(available))


def replace(ordinary, stats, rng, *, loc_id, ambush_camp=None,
            player_kill=False, weapon_type_id=None, killer_level=None):
    """Replace only native ordinary ammunition/A battle meds; quests stay outside.

    Melee or missing gun metadata selects one random released A-OT calibre.
    Counts do not scale with scanners or level-based random-loot bonuses.
    """
    if (not player_kill or stats.role != 'object' or ambush_camp is not None
            or BOXES.get(loc_id) != stats.type_id):
        return ordinary
    pool = ammunition()
    if not pool:
        return ordinary
    gun = (items.params_of(weapon_type_id) or {}) if items.root_of(weapon_type_id) == items.FIRE_ARM else {}
    compatible = tuple(ammo for ammo in pool if ammo in gun.get('comp_array', ()))
    ammo = compatible[0] if len(compatible) == 1 else rng.choice(compatible or pool)
    tier = min(5, max(0, int(killer_level or 0) // 4))
    kept = [(t, n) for t, n in ordinary
            if items.root_of(t) != items.AMMO and t not in HEALTH + STAMINA]
    return kept + [(ammo, AMMO_COUNT), (HEALTH[tier], rng.randint(1, 2)),
                   (STAMINA[tier], rng.randint(1, 2))]
