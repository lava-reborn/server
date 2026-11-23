"""Eligible clean A weapons for the shared ordinary equipment loot slot."""
from functools import lru_cache

import camp_loot


BASE_CHANCE = .005
MAX_LEVEL = 17


@lru_cache(maxsize=1)
def _ordinary_types():
    import battle_balance
    return frozenset(row[2] for rows in battle_balance.mob_weapons().values() for row in rows)


def is_afro_weapon(type_id):
    import item_templates
    return item_templates.source_type(type_id) in _ordinary_types()


def weapon_type(stats, loc_id=None):
    if (getattr(stats, 'role', None) not in ('mob', 'boss')
            or not getattr(stats, 'can_attack', False)
            or not camp_loot.is_humanoid(stats)):
        return None
    import holdings
    if holdings.site_at(loc_id) is not None:
        return None
    import battle_balance
    import items
    kind = getattr(stats, 'weapon_class', None) if getattr(stats, 'ranged', False) else 'knife'
    ceiling = min(MAX_LEVEL, stats.level)
    choices = [row for row in battle_balance.mob_weapons().get(kind, ())
               if row[0] <= ceiling and not items.acquisition_blocked(row[2])]
    return max(choices, default=(0, 0, None))[2]
