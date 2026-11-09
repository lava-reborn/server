"""Range-only item normalization; original tables are never mutated."""
import copy
from functools import lru_cache
import math
import re

RATIOS = {'A': 1.0, 'P': 1.06, 'G': 1.12}
INTELLECT_BASE = 5
INTELLECT_DAMAGE_STEP = 0.01


def rounded(value):
    return int(math.floor(value + 0.5))


def family(name):
    name = re.sub(r'_([AGP])_mod', '_X_mod', name)
    return re.sub(r'_(?:gold|pm|g|p)$', '', name, flags=re.I)


def line(source):
    import items
    import combat
    return 'P' if items.premium(source) else 'G' if combat.gold_item(source) else 'A'


@lru_cache(maxsize=1)
def afro_index():
    import items
    return {family(name): source for source, (_root, name) in items.catalogue().items()
            if line(source) == 'A'}


def afro_of(source):
    import items
    import training_sets
    selected = training_sets.for_source(source)
    if selected is not None:
        record = selected[1]
        slot = next((slot for slot, member in record['members'].items() if member == source), None)
        if slot is not None:
            base = next((base for base in training_sets.records().values()
                         if base['variant'] == 'A' and base['family'] == record['family']
                         and base['level'] == record['level']), None)
            if base is not None:
                return base['members'][slot]
    return afro_index().get(family(items.catalogue()[source][1]))


def scaled(value, factor):
    if isinstance(value, list):
        return [scaled(part, factor) for part in value]
    return rounded(value * factor) if value > 0 else value


def apply(source, params):
    import items
    import training_sets
    base = afro_of(source)
    factor = RATIOS[line(source)]
    reference = items.params_of(base) if base is not None else None
    if reference is not None:
        if items.premium(source) and not params.get('need_skills_m') and reference.get('need_skills_m'):
            params['need_skills_m'], params['need_skills'] = reference['need_skills_m'], copy.deepcopy(reference['need_skills'])
        if items.root_of(source) in (items.FIRE_ARM, items.COLD_ARM):
            for field in ('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max'):
                if field in reference:
                    params[field] = scaled(reference[field], factor)
        elif items.root_of(source) == items.WEAR:
            for field in ('armor_class', 'bonus_hp', 'bonus_st', 'bonus_od', 'bonus_cp', 'bonus_ce',
                          'bonus_attribs', 'bonus_skills', 'bonus_specs'):
                if field in reference:
                    params[field] = scaled(reference[field], factor)
            for field in ('bonus_attribs_m', 'bonus_skills_m', 'bonus_specs_m'):
                if field in reference:
                    params[field] = reference[field]
    if items.root_of(source) == items.FIRE_ARM:
        # An optimal interval cannot extend past the actual firing range.
        for mode, maximum in enumerate(params['max_range']):
            params['opt_range'][mode] = min(params['opt_range'][mode], maximum)
            params['end_opt_range'][mode] = min(maximum, max(params['opt_range'][mode], params['end_opt_range'][mode]))
    record = training_sets.for_source(source)
    if record is not None:
        params['set_type'] = record[0]
    return params


def intellect_multiplier(character):
    import progression
    return 1 + max(0, character.attr(progression.INTELLECT) - INTELLECT_BASE) * INTELLECT_DAMAGE_STEP
