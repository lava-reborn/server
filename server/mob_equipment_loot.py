"""One mutually exclusive worn A item per corpse, with native quest exceptions."""
import camp_loot
import mob_weapon_loot
import equipment_release


POUCHES = {'assault_rifle': 3577, 'rifle': 3578, 'smg': 3579,
           'machine_gun': 3580, 'shotgun': 3581, 'pistol': 3582, 'knife': 5613}
# Remaining repair ceiling, as a percentage of factory durability.
CONDITION = {'armour': (60, 80), 'weapon': (40, 60), 'pouch': (30, 60)}


def kind_of(type_id):
    import item_templates
    source = item_templates.source_type(type_id)
    if source in POUCHES.values() or source == 4323:
        return 'pouch'
    if camp_loot.is_afro_set_piece(source):
        return 'armour'
    if mob_weapon_loot.is_afro_weapon(source):
        return 'weapon'
    return None


def without_equipment(drops):
    """Native G rewards and personal quests are filtered separately by caller."""
    return [(type_id, count) for type_id, count in drops if kind_of(type_id) is None]


def random_drop_allowed(type_id):
    """Release/retail guard for ordinary equipment, never for personal quest rewards."""
    import items
    return (not items.out_of_game(type_id) and not items.acquisition_blocked(type_id)
            and (kind_of(type_id) is None or equipment_release.available(type_id)))


def categories(stats, loc_id=None, ambush_camp=None):
    """Fixed base rates; an unavailable category does not subsidise another."""
    parts = tuple(t for t in camp_loot.piece_types(stats, loc_id, ambush_camp)
                  if random_drop_allowed(t))
    weapon = mob_weapon_loot.weapon_type(stats, loc_id)
    kind = getattr(stats, 'weapon_class', None) if getattr(stats, 'ranged', False) else 'knife'
    pouch = POUCHES.get(kind) if weapon else None
    if pouch is not None and not random_drop_allowed(pouch):
        pouch = None
    return (('armour', parts, camp_loot.BASE_CHANCE),
            ('weapon', (weapon,) if weapon else (), mob_weapon_loot.BASE_CHANCE),
            ('pouch', (pouch,) if pouch else (), .005))


def roll(stats, rng, *, loc_id=None, ambush_camp=None, multiplier=1, protected=()):
    if any(count > 0 and kind_of(type_id) for type_id, count in protected):
        return []
    factor = camp_loot.drop_chance(multiplier) / camp_loot.BASE_CHANCE
    if factor <= 0:
        return []
    options = categories(stats, loc_id, ambush_camp)
    if not any(types for _kind, types, _chance in options):
        return []
    draw = rng.random()
    threshold = 0
    for _kind, types, chance in options:
        threshold += chance
        if draw < threshold * factor:
            chosen = rng.choice(types) if types else None
            return [(chosen, 1)] if chosen is not None and random_drop_allowed(chosen) else []
    return []


def condition_bounds(type_id):
    """Inclusive integer repair ceilings, or None for non-ordinary equipment."""
    import items
    kind = kind_of(type_id)
    if kind is None:
        return None
    factory = (items.params_of(type_id) or {}).get('max_break_abs', 0)
    low, high = CONDITION[kind]
    lower, upper = (factory * low + 99) // 100, factory * high // 100
    return (lower, upper) if 0 < lower <= upper else None


def worn_fields(type_id, rng):
    bounds = condition_bounds(type_id)
    if bounds is None:
        return {}
    ceiling = rng.randint(*bounds)
    return dict(max_break_cur=ceiling, brk=rng.randint((ceiling + 1) // 2, ceiling))
