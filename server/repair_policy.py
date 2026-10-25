"""Repair-only A/G counterparts; sale prices and restoration are independent."""
from functools import lru_cache
import json

LEVEL_MULTIPLIERS = {
    10: 4.75, 11: 4.5, 12: 4.25, 13: 3.75, 14: 3.5, 15: 2.75,
    16: 2, 17: 1.8, 18: 1.6, 19: 1.4, 20: 1.2,
}


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

    cat = items.catalogue()
    by_name = {name: t for t, (_, name) in cat.items()}
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
    with open(sets.PATH, encoding='utf-8') as source:
        ladder = json.load(source)['sets'].values()
    afro = {(s['level'], s['family']): s for s in ladder
            if s['variant'] == 'A'}
    for s in ladder:
        a = afro.get((s['level'], s['family']))
        if s['variant'] != 'G' or not a:
            continue
        for slot, piece in s['members'].items():
            gold = piece['type']
            base = a['members'][slot]['type']
            pairs[gold] = base
            gc, ac = setcraft.chain_of(gold), setcraft.chain_of(base)
            if gc and ac:
                pairs.update(zip(gc, ac))
    return pairs


def valuation(type_id, params):
    """Repair valuation from the corresponding A type and the item's level."""
    import items

    if not params.get('g_cost') or not params.get('max_break_abs'):
        return None
    # Pouches have no item level. The owner's separate rule retains their
    # gold valuation, converted at 10,000 afro/G for repair only.
    if type_id in items.GOLD_POUCHES.values():
        return params['g_cost'] * 10000 / 100
    base = counterparts().get(type_id)
    if base is None:
        return None
    # Skills carry the public item level, unlike several internal set names.
    level = max(params.get('need_skills') or [0])
    if level < 1:
        return None
    a = items.static_info(base)[1]
    if not a.get('cost'):
        return None
    return a['cost'] * multiplier(level)
