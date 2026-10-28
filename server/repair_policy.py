"""Repair-only A/G counterparts; sale prices and restoration are independent."""
from functools import lru_cache
import re

LEVEL_MULTIPLIERS = {
    10: 4.75, 11: 4.5, 12: 4.25, 13: 3.75, 14: 3.5, 15: 2.75,
    16: 2, 17: 1.8, 18: 1.6, 19: 1.4, 20: 1.2,
}

# KS-12 has no A twin. Use the ordinary weapon price at the same public
# level for repair ONLY. All A shotguns of each listed level share a price.
# At 14/15 the catalogue has no shop A shotgun: G3/M16A2 supply the same
# ordinary-weapon price tier. These are valuation references, not exchanges.
KS12_AFRO_REFERENCES = {
    4: 25856, 5: 25876, 6: 25899, 7: 25938, 8: 25967,
    9: 25983, 10: 26009, 11: 26035, 12: 26061,
    14: 25217, 15: 25249,
}


def ks12_reference(type_id, level):
    """Repair reference for a known KS-12 level, including named copies."""
    import items
    root, name = items.catalogue().get(type_id, (None, ''))
    if root == items.FIRE_ARM and re.fullmatch(r'lamantin_shotgun_\d+(?:_.*)?', name):
        return KS12_AFRO_REFERENCES.get(level)
    return None


def multiplier(level):
    """Five A valuations below 10, then the owner's decreasing premium."""
    if level < 1:
        return 1
    if level <= 9:
        return 5
    return LEVEL_MULTIPLIERS.get(level, 1.2)


@lru_cache(maxsize=1)
def counterparts():
    import items
    import sets
    import setcraft
    import craft

    cat = items.catalogue()
    by_name = craft._by_name()
    pairs = {}
    for t, (root, name) in cat.items():
        if root not in (items.FIRE_ARM, items.COLD_ARM):
            continue
        ordinary = name.replace('_gold', '', 1) if '_gold' in name else (
            name.replace('_G', '_A', 1) if '_G' in name else None)
        base = by_name.get(ordinary)
        # A knives have no sharpened types. Value an existing G sharpening
        # from its A base, without inventing an A modification or a recipe.
        if base is None and root == items.COLD_ARM and '_G_' in name:
            base = by_name.get(name.split('_G_', 1)[0] + '_A')
        if base is not None and cat[base][0] == root:
            pairs[t] = base
    # Match the actual ladder, including the sets with our own type IDs.
    ladder = sets.SETS.values()
    afro = {(s['level'], s['family']): s for s in ladder
            if s['variant'] == 'A'}
    for s in ladder:
        a = afro.get((s['level'], s['family']))
        if s['variant'] != 'G' or not a:
            continue
        for slot, gold in s['members'].items():
            base = a['members'][slot]
            pairs[gold] = base
            gc, ac = setcraft.chain_of(gold), setcraft.chain_of(base)
            if gc and ac:
                pairs.update(zip(gc, ac))
    return pairs


@lru_cache(maxsize=None)
def afro_cost(type_id):
    """Cache the fixed A valuation without sharing mutable item frames."""
    import items
    return items.static_info(type_id)[1].get('cost', 0)


def valuation(type_id, params):
    """Repair valuation from the corresponding A type and the item's level."""
    import items
    import progression

    if not params.get('g_cost') or not params.get('max_break_abs'):
        return None
    # Pouches have no item level. The owner's separate rule retains their
    # gold valuation, converted at 10,000 afro/G for repair only.
    if type_id in items.GOLD_POUCHES.values():
        return params['g_cost'] * 10000 / 100
    # Skills carry the public item level, unlike several internal set names.
    level = max(params.get('need_skills') or [0])
    if level < 1:
        return None
    ks12 = ks12_reference(type_id, level)
    base = ks12 if ks12 is not None else counterparts().get(type_id)
    if base is None:
        return None
    cost = afro_cost(base)
    if not cost:
        return None
    value = cost * multiplier(level)
    if ks12 is not None:
        # Do not raise the cheaper low-level repair while adding coverage.
        # This is the existing fallback used by inventory.repair_base_price.
        current = params.get('cost') or (
            params['g_cost'] * progression.GOLD_TO_AFRO_RATE
            / progression.GOLD_OUNCE)
        return min(value, current)
    return value
