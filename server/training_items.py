"""Independent runtime-only range templates; no real item is overwritten."""
import copy
import json
import math
from pathlib import Path

FIRST = 54000
LAST = 65535
SOURCES = {}
COPIES = {}
FRAMES = {}
REFERENCE_PRICES = {}
PATH = Path(__file__).resolve().parents[1] / 'data' / 'training_items.json'
# Only combat/handling data may differ; identity, transfers and currencies cannot.
FIELDS = frozenset(('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max',
    'fire_times', 'fire_costs', 'fire_mods', 'max_range', 'opt_range', 'end_opt_range',
    'target_size', 'clip_size', 'reload_time', 'reload_cost', 'piercing',
    'armor_class', 'max_break_abs', 'weight', 'range_mod', 'acc_mod', 'dam_mod', 'st_mod',
    'bonus_hp', 'bonus_st', 'bonus_od'))


def is_copy(type_id):
    return type_id in SOURCES


def source_type(type_id):
    return SOURCES.get(type_id, type_id)


def copy_type(type_id):
    return COPIES[type_id]


def static_info(type_id):
    command, params = FRAMES[type_id]
    return command, copy.deepcopy(params)


def candidate(base, changes):
    """Checked independent values, shared by the description and real combat."""
    result = copy.deepcopy(base)
    for key, value in changes.items():
        if key not in FIELDS or key not in base:
            raise ValueError('Unsupported training field: ' + key)
        values = value if isinstance(value, list) else [value]
        if isinstance(base[key], list) != isinstance(value, list) or (
                isinstance(value, list) and len(value) != len(base[key])):
            raise ValueError('Wrong training field shape: ' + key)
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1000000 for x in values):
            raise ValueError('Invalid training number: ' + key)
        if key in ('clip_size', 'max_break_abs') and (not isinstance(value, int) or value < 1):
            raise ValueError('Positive training integer required: ' + key)
        if key in ('max_range', 'target_size', 'fire_times', 'fire_costs') and any(x <= 0 for x, mode in zip(values, result['fire_mods']) if mode):
            raise ValueError('Active mode timing/cost must be positive')
        result[key] = copy.deepcopy(value)
    for low, high in (('h_damage_min', 'h_damage_max'), ('st_damage_min', 'st_damage_max'),
                      ('opt_range', 'end_opt_range'), ('end_opt_range', 'max_range')):
        if low not in changes and high not in changes:
            continue
        if low in result and high in result:
            lower = result[low] if isinstance(result[low], list) else [result[low]]
            upper = result[high] if isinstance(result[high], list) else [result[high]]
            if any(a > b for a, b in zip(lower, upper)):
                raise ValueError('Invalid training interval: ' + low)
    return result


def validate_ammunition(frames, roots):
    """Check both directions once at preparation; never during shots/loading."""
    import items
    if set(frames) != set(roots):
        raise ValueError('Training frame/root mismatch')
    ammunition = {t for t, root in roots.items() if root == items.AMMO}
    used = set()
    for weapon, root in roots.items():
        if root != items.FIRE_ARM:
            continue
        compatible = frames[weapon][1].get('comp_array', ())
        if not compatible or any(rounds not in ammunition for rounds in compatible):
            raise ValueError('Training weapon has unavailable ammunition: %s' % weapon)
        used.update(compatible)
    if ammunition - used:
        raise ValueError('Training ammunition has no weapon: %s' % sorted(ammunition - used))


def prepare(sources):
    if COPIES:
        return
    import items
    table = items.catalogue()
    originals = sorted(sources)
    if FIRST + len(originals) - 1 > LAST or any(t in table for t in range(FIRST, FIRST + len(originals))):
        raise ValueError('Training type range collision')
    overrides = json.loads(PATH.read_text(encoding='utf-8-sig')).get('items', {})
    if any(int(t) not in sources for t in overrides):
        raise ValueError('Unknown training override source')
    copies = {t: FIRST + i for i, t in enumerate(originals)}
    frames = {}
    prices = {}
    for source, target in copies.items():
        command, base = items.static_info(source)
        import training_legacy
        import training_ammo
        base = training_ammo.parameters(source, training_legacy.apply(source, copy.deepcopy(base)))
        prices[source] = (base.get('cost', 0) or 0, base.get('g_cost', 0) or 0,
                          (base.get('sell_num', 1) or 1) if items.root_of(source) == items.AMMO else 1)
        import training_balance
        params = training_balance.apply(source, candidate(base, overrides.get(str(source), {})))
        if source in training_legacy.CLASSIC:
            params = training_legacy.apply(source, params)
        params = training_ammo.parameters(source, params)
        import training_effects
        effect = training_effects.definition(source)
        if effect is not None:
            params.update(bonus_act_time=effect['duration'], bonus_prob=100,
                          effects=[training_effects.FIRST + source], effects_prob=[100])
            for key, field in zip(('str_bonus', 'dex_bonus', 'sta_bonus', 'per_bonus', 'int_bonus'), effect['bonuses']['attribs']):
                params[key] = field
        params.update(type=target, cost=0, g_cost=0, sell_mod=0, premium=0, exchang=0)
        params.pop('bg_p_cost', None)
        if 'comp_array' in params:
            params['comp_array'] = [copies[a] for a in params['comp_array'] if a in copies]
        frames[target] = command, params
    validate_ammunition(frames, {target: table[source][0] for source, target in copies.items()})
    # Publish only a completely validated set. Sources are never changed.
    COPIES.update(copies)
    SOURCES.update({t: s for s, t in copies.items()})
    FRAMES.update(frames)
    REFERENCE_PRICES.update(prices)
