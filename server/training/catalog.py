"""Training range: catalog."""
import combat
from training import content
import craft
import inventory
import items
import mobs
import names
import npcs
import quests
import re
import sets
import shop_bands
import world
from functools import lru_cache
from training import (
    ammo as training_ammo,
    balance as training_balance,
    display as training_display,
    effects as training_effects,
    formulas as training_formulas,
    items as training_items,
    labels as training_labels,
    legacy as training_legacy,
    opponents as training_opponents,
    sets as training_sets,
)
from training.settings import CONTRABAND_TRADER, MAX_LEVEL


@lru_cache(maxsize=1)
def contraband():
    return frozenset(items.stock_for(CONTRABAND_TRADER))


@lru_cache(maxsize=1)
def obtainable_sources():
    craft._read()
    eligible, rewards = set(), set()
    for trader in set(items.stock_table()) | set(npcs.STOCK) | set(craft._STOCK):
        eligible.update(items.stock_for(trader))
    # The real stall depends on its city: stock_for(type) alone misses
    # weapons and armour supplied by city bands rather than legacy lists.
    known = set(items.stock_table()) | set(npcs.STOCK) | set(craft._STOCK) | set(shop_bands.SELLERS)
    seen = set()
    for location in shop_bands.CITY_OF:
        for _cell, trader in world.location(location).spawns:
            key = trader, shop_bands.city(location)
            if trader in known and key not in seen:
                seen.add(key)
                eligible.update(items.stock_for(trader, location))
    for quest in quests.QUESTS.values():
        if quest.give and not quests.acquisition_blocked(quest):
            rewards.update(quest.rew_obj)
            rewards.update(t for t, _n in quest.rew_also)
            rewards.update(t for t, _n, _weight in quest.rew_random)
    eligible.update(rewards)
    for type_id in tuple(eligible):
        if type_id in sets.SETS:
            eligible.update(sets.SETS[type_id]['members'].values())
    return frozenset(eligible), frozenset(rewards)


def item_family(name):
    name = re.sub(r'_([AGP])_mod', '_X_mod', name)
    return re.sub(r'_(?:gold|pm|g|p)$', '', name, flags=re.I)


def item_line(type_id):
    if items.premium(type_id):
        return 'P'
    return 'G' if combat.gold_item(type_id) else 'A'


@lru_cache(maxsize=1)
def item_catalogue():
    eligible, rewards = obtainable_sources()
    extra = {t for info in sets.SETS.values() if info['level'] <= MAX_LEVEL
             for t in info['members'].values()}
    extra.update(t for info in training_sets.records().values() if info['level'] <= MAX_LEVEL
                 for t in info['members'].values())
    for t, (root, name) in items.catalogue().items():
        if root in (items.FIRE_ARM, items.COLD_ARM) and (
                17 < inventory.item_level(t) <= MAX_LEVEL and '_lvl_' in name
                and not name.endswith('_mob') or name.startswith('ufo_gun')
                or '(R)' in names.text(items.STRING_ID_OFFSET + t)):
            extra.add(t)
    extra.update(t for t in content.data()['extra_sources'] if t in items.catalogue())
    extra.update(training_effects.definitions())
    extra.update(training_legacy.CLASSIC)
    extra.update(training_ammo.EXTRA_SOURCES)
    if training_formulas.available():
        extra.update(training_formulas.data().get('extra_sources', ()))
    extra.update(t for t, info in items.wiki().items() if items.root_of(t) == items.HEAL
                 and any(word in items.catalogue()[t][1].casefold() for word in
                         ('newyear', 'valentine', 'oct31', 'march', 'may9', 'june', 'ny20', 'febr')))
    eligible = eligible | extra
    # P counterparts are offered only inside the sandbox. Do not enumerate the
    # thousands of unused/placeholder premium templates as usable equipment.
    families = {item_family(items.catalogue()[t][1]) for t in eligible
                if t in items.catalogue() and not items.out_of_game(t)}
    premium_sources = {t for t, (root, name) in items.catalogue().items()
                       if items.premium(t) and (
                           item_family(name) in families or
                           root in (items.HEAL, items.AMMO) and
                           (t in items.wiki() or t in items.heal_manual()))}
    eligible = eligible | premium_sources
    mod_labels = {}
    for rec in craft.rows().values():
        if rec.get('family') == 'upgrade' and rec.get('line') in ('A', 'G'):
            mod_labels[int(rec['mod'])] = names.text(items.STRING_ID_OFFSET + int(rec['blueprint'])).partition('$')[0]
    out = {}
    aliases = {int(t): row['name'] for t, row in content.data()['labels'].items()}
    for type_id in eligible:
        if training_items.is_copy(type_id) or type_id in training_legacy.UNCONFIRMED:
            continue
        if type_id not in items.catalogue():
            continue
        root, name = items.catalogue()[type_id]
        if root not in (items.FIRE_ARM, items.COLD_ARM, items.WEAR, items.HEAL, items.AMMO):
            continue
        if (items.retired(type_id) or type_id in items.ADMIN_OVERRIDES):
            continue
        p = items.params_of(type_id) or {}
        if not p:
            continue
        level = inventory.item_level(type_id) if root in items.BREAKABLE_ROOTS else 0
        if root in items.BREAKABLE_ROOTS and not level:
            reference = training_balance.afro_of(type_id)
            level = inventory.item_level(reference) if reference is not None else 0
        level = training_legacy.LEVELS.get(type_id, level)
        level = training_ammo.LEVELS.get(type_id, level)
        if level > MAX_LEVEL:
            continue
        category = {items.FIRE_ARM: 'weapon', items.COLD_ARM: 'weapon',
                    items.WEAR: 'armour', items.HEAL: 'medicine', items.AMMO: 'ammo'}[root]
        if root == items.WEAR and (p.get('slot_type', -1) + inventory.HEAD) == inventory.BELT:
            category = 'pouch'
        label = training_labels.title(type_id)
        if root in (items.FIRE_ARM, items.COLD_ARM) and type_id in training_ammo.SPECIAL_WEAPONS:
            category = 'experimental_weapon'
        elif root in (items.FIRE_ARM, items.COLD_ARM) and (
                type_id in contraband() or (craft.mod_of(type_id) or (None,))[0] in contraband()
                or name.startswith('ufo_gun') or '(R)' in label
                or any(word in name.casefold() for word in ('prototype', 'experimental', '_quest'))
                or type_id in rewards and '_lvl_' not in name and type_id not in contraband() and type_id < 4000):
            category = 'special_weapon'
        elif root == items.HEAL:
            if name.startswith('ufo_gun') or any(word in name.casefold() for word in (
                    'newyear', 'valentine', 'oct31', 'march', 'may9', 'june', 'ny20', 'november', 'febr')):
                category = 'event_medicine'
            elif training_effects.definition(type_id):
                category = 'buff'
            elif items.stimulant_unavailable(type_id):
                continue

        # These are legacy wearable souvenirs, not combat equipment. Some are
        # stored under COLD_ARM or have generated HEAL fallback parameters.
        if (root == items.COLD_ARM and not level and type_id not in training_legacy.CLASSIC
                and not name.startswith('ufo_gun')) or name == 'old_flea_bag':
            category = 'accessory'
        if root == items.HEAL and training_effects.definition(type_id):
            category = 'buff'

        label = training_ammo.NAMES.get(type_id, aliases.get(type_id, label))
        if root in items.BREAKABLE_ROOTS:
            label += ' · %d ур.' % level
        if type_id in contraband():
            label += ' · Контрабанда'
        if type_id in mod_labels:
            label += ' · ' + mod_labels[type_id]
        elif root == items.FIRE_ARM:
            reference = training_balance.afro_of(type_id)
            if reference in mod_labels:
                label += ' · ' + mod_labels[reference]
        if root == items.FIRE_ARM:
            upgrade = training_display.upgrade(type_id)
            if upgrade and upgrade not in label:
                label += ' · ' + upgrade
        out[type_id] = (category, level, label)
    for source, record in training_items.prototype_rows().items():
        out[source] = ('experimental_weapon', record['level'], record['name'] + ' · Экспериментальный образец')
    return out


@lru_cache(maxsize=1)
def mob_catalogue():
    known = world.mob_types()
    return {t: '%s · %d ур.' % (row['name'], mobs.stats(t).level)
            for t, row in training_opponents.RECORDS.items()
            if t in known and known[t][0] == world.MOB and str(t) in mobs.TYPES
            and mobs.TYPES[str(t)].get('role') in ('mob', 'animal', 'boss')
            and not world.retired_creature(t)}
