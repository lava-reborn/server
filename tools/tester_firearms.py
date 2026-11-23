"""Plan additive A-firearm supplies using the ordinary released catalogue.

This module does not open a database or start the game. Callers own the
transaction and restrict the intended synthetic character/account roster.
"""
from types import SimpleNamespace
from functools import lru_cache
import re


CLASS_NAMES = ('Пистолеты', 'Дробовики', 'Автоматы', 'Винтовки', 'Пулемёты', 'ПП')
STANDARD_ROUNDS = 400


@lru_cache(maxsize=None)
def arsenal(level):
    """Candidates at each class's nearest available lower catalogue tier."""
    import inventory
    import items
    import shop_bands

    available = [type_id for type_id, ware in shop_bands.wares().items()
                 if ware[3] == 0 and items.root_of(type_id) == items.FIRE_ARM
                 and not items.params_of(type_id).get('g_cost')
                 and not items.out_of_game(type_id)
                 and not items.acquisition_blocked(type_id)
                 and standard_ammo(type_id)]
    chosen, exceptions = [], []
    for kind, title in enumerate(CLASS_NAMES):
        options = [type_id for type_id in available
                   if items.params_of(type_id)['weapon_type'] == kind
                   and inventory.item_level(type_id) <= level]
        if not options:
            exceptions.append(dict(kind=kind, cls=title, reason='No released ST-compatible A weapon at or below this level'))
            continue
        tier = max(inventory.item_level(type_id) for type_id in options)
        selected = sorted(type_id for type_id in options if inventory.item_level(type_id) == tier)
        chosen.extend(selected)
        if tier < level:
            exceptions.append(dict(kind=kind, cls=title, reason='Nearest lower catalogue tier',
                                   character_level=level, weapon_level=tier))
    return chosen, exceptions


@lru_cache(maxsize=None)
def standard_ammo(type_id):
    import items

    found = [ammo for ammo in items.params_of(type_id)['comp_array']
             if items.catalogue()[ammo][1].endswith('_ST')
             and not items.params_of(ammo).get('g_cost')]
    return sorted(set(found))


@lru_cache(maxsize=None)
def collectible_arsenal(level):
    """Verified ordinary Lamantin variants of exactly the character's level.

    Named clan copies and unfinished catalogue placeholders are not supplies.
    The name's tier must agree with the actual requirements sent to the client.
    """
    import inventory
    import items
    pattern = re.compile(r'lamantin_(?:machine_gun|pistols|assault_rifle|rifle|shotgun|sub_machine_guns)_(\d+)')
    return tuple(sorted(type_id for type_id, (root, name) in items.catalogue().items()
                        if root == items.FIRE_ARM and (match := pattern.fullmatch(name))
                        and int(match[1]) == level == inventory.item_level(type_id)
                        and not items.out_of_game(type_id) and not items.acquisition_blocked(type_id)
                        and standard_ammo(type_id)))


def plan_character(store, char_id, *, collectibles_only=False):
    """Read native rows and calculate only missing carried supplies/specs."""
    import combat
    import inventory
    import items
    import progression

    ch = progression.Character.load(store, char_id)
    before_stats = {(kind, index): (value, xp, cap) for kind, index, value, xp, cap in ch.rows()}
    rows = store.items_of(char_id)
    candidates, exceptions = arsenal(ch.level) if not collectibles_only else ((), [])
    supply_slots = (inventory.BAG, inventory.PRIMARY, inventory.SECONDARY)
    inv = inventory.Inventory(SimpleNamespace(char_id=char_id), store)
    bank_steps_added = 0
    if collectibles_only:
        supply_slots += (inventory.BANK,)
    carried = [row for row in rows if row['slot'] in supply_slots]
    healthy = {row['type_id'] for row in carried if row['root'] == items.FIRE_ARM and row['brk'] > 0}
    guns = []
    for kind in range(len(CLASS_NAMES)):
        options = [type_id for type_id in candidates if items.params_of(type_id)['weapon_type'] == kind]
        if options:
            guns.append(min(options, key=lambda type_id: (type_id not in healthy,
                             items.params_of(type_id)['weight'], type_id)))
    if collectibles_only:
        guns.extend(collectible_arsenal(ch.level))
        if not guns:
            exceptions.append(dict(reason='No verified ordinary collectible weapon at this exact level',
                                   character_level=ch.level))
    required = {}
    for type_id in guns:
        params = items.params_of(type_id)
        mask = params.get('need_specs_m', 0) or 0
        levels = inventory.unpacked(mask, params.get('need_specs'), progression.SPECS)
        for index, needed in enumerate(levels):
            if mask >> index & 1:
                required[index] = max(required.get(index, -1), needed)
        index = combat.SPEC_OF_WEAPON[params['weapon_type']]
        required[index] = max(required.get(index, -1), 0)
    changes = []
    for index, needed in sorted(required.items()):
        if index not in progression.LEARNABLE or not 0 <= needed <= progression.SPEC_MAX:
            raise ValueError('Invalid weapon specialisation requirement')
        current = ch.spec[index][0]
        if current < needed:
            ch.set_spec(index, needed)
            changes.append(dict(index=index, name=progression.SPEC_TITLES[index], before=current, after=needed))
    updates = [dict(kind=kind, index=index, value=value, xp=xp, xp_max=cap)
               for kind, index, value, xp, cap in ch.rows()
               if before_stats[kind, index] != (value, xp, cap)]
    adds, weapons = [], []
    for type_id in guns:
        params = items.params_of(type_id)
        owned = next((row for row in carried if row['type_id'] == type_id and row['brk'] > 0), None)
        if owned is None:
            fields = inventory.new_fields(type_id)
            fields.update(type_id=type_id, ammo_type=standard_ammo(type_id)[0], ammo_count=params['clip_size'])
            adds.append(fields)
        weapons.append(dict(type=type_id, name=inventory.item_title(type_id),
                            kind=params['weapon_type'], cls=CLASS_NAMES[params['weapon_type']],
                            level=inventory.item_level(type_id), existing=owned['uniq'] if owned else None,
                            ammo=standard_ammo(type_id), added=owned is None,
                            slot=owned['slot'] if owned else inventory.BAG))
    ammunition = []
    for ammo in sorted({ammo for gun in weapons for ammo in gun['ammo']}):
        current = sum(row['count'] for row in carried if row['type_id'] == ammo)
        missing = max(0, STANDARD_ROUNDS - current)
        left = missing
        while left:
            fields = inventory.new_fields(ammo, left)
            fields['type_id'] = ammo
            adds.append(fields)
            left -= fields['count']
        ammunition.append(dict(type=ammo, name=inventory.item_title(ammo), before=current,
                               added=missing, after=current + missing))
    # Validate an actual swap: a different old primary cannot provide its
    # bonus to the requirement of the candidate replacing it.
    for gun in weapons:
        swapped = [dict(row, slot=inventory.BAG if row['slot'] == inventory.PRIMARY else row['slot'])
                   for row in rows]
        swapped.append(dict(type_id=gun['type'], root=items.FIRE_ARM,
                            slot=inventory.PRIMARY, brk=items.params_of(gun['type'])['max_break_abs'], count=1))
        ch.set_gear(inventory.gear_bonus(swapped, ch), inventory.card_repeat(swapped))
        error = inventory.weapon_requirement_error(swapped[-1], ch)
        if error:
            raise ValueError('%s: %s' % (ch.name, error))
    ch.set_gear(inventory.gear_bonus(rows, ch), inventory.card_repeat(rows))
    weight = sum(inventory.weight_of(row) for row in rows if row['slot'] != inventory.BANK)
    capacity = ch.max_weight()
    if collectibles_only:
        # Preserve existing gear/progress; keep excess new test supplies in
        # personal storage instead of silently increasing strength/capacity.
        extra = sum(inventory.weight_of(row) for row in adds)
        for row in sorted(adds, key=inventory.weight_of, reverse=True):
            if weight + extra <= capacity:
                break
            row['slot'] = inventory.BANK
            extra -= inventory.weight_of(row)
        for gun in weapons:
            if gun['added']:
                gun['slot'] = next(row['slot'] for row in adds if row['type_id'] == gun['type'])
    added_weight = sum(inventory.weight_of(row) for row in adds if row['slot'] != inventory.BANK)
    bank_weight = inv.bank_weight() + sum(inventory.weight_of(row) for row in adds if row['slot'] == inventory.BANK)
    bank_capacity = inv.bank_max()
    if collectibles_only and bank_weight > bank_capacity:
        # The ordinary paid bank expansion keeps combat stats and all old
        # items intact when this synthetic profile has filled its storage.
        bank_steps_added = (bank_weight - bank_capacity + inventory.BANK_STEP - 1) // inventory.BANK_STEP
        if ch.gold < bank_steps_added * inventory.BANK_STEP_GOLD:
            raise ValueError('Insufficient test gold for collection storage')
        bank_capacity += bank_steps_added * inventory.BANK_STEP
    return dict(character=ch.name, id=char_id, level=ch.level, weapons=weapons, ammunition=ammunition,
                item_additions=adds, stat_updates=updates, specialisation_changes=changes,
                specialisations={progression.SPEC_TITLES[i]: value[0]
                                 for i, value in enumerate(ch.spec) if value[0] >= 0},
                spec_slots=max(store.spec_slots(char_id), ch.specs_learned()),
                exceptions=exceptions, weight_before=weight, added_weight=added_weight,
                weight_after=weight + added_weight, capacity=capacity,
                bank_weight_after=bank_weight, bank_capacity=bank_capacity,
                bank_steps_added=bank_steps_added,
                bank_expansion_cost_gold=bank_steps_added * inventory.BANK_STEP_GOLD,
                bank_overweight=bank_weight > bank_capacity, overweight=weight + added_weight > capacity)


def apply_character(store, profile):
    """Apply a reviewed plan inside the caller's existing atomic transaction."""
    import inventory

    if profile['overweight'] or profile['bank_overweight']:
        raise ValueError('Supplies would overload %s' % profile['character'])
    inv = inventory.Inventory(SimpleNamespace(char_id=profile['id']), store)
    for _ in range(profile.get('bank_steps_added', 0)):
        current = store.character(profile['id'])
        if current['gold'] < inventory.BANK_STEP_GOLD:
            raise ValueError('Insufficient test gold for collection storage')
        store.bank_expand(profile['id'], current['afro'], current['gold'] - inventory.BANK_STEP_GOLD)
    for fields in profile['item_additions']:
        row = inv.create(fields['type_id'], count=fields['count'], slot=fields['slot'])
        dynamic = {key: value for key, value in fields.items() if key not in ('type_id', 'root', 'count', 'slot')}
        if dynamic:
            store.update_item(row['uniq'], **dynamic)
    for row in profile['stat_updates']:
        store.db.execute('UPDATE char_stats SET value=?, xp=?, xp_max=? WHERE char_id=? AND kind=? AND idx=?',
                         (row['value'], row['xp'], row['xp_max'], profile['id'], row['kind'], row['index']))
    if store.spec_slots(profile['id']) < profile['spec_slots']:
        store.save_spec_slots(profile['id'], profile['spec_slots'])
