"""Opt-in range equations from simulator 6b7b28d, rulesets/lava_fixed.py.

The simulator profile uses each weapon's own source coefficient and A/G
damage bases. Old sandbox P/G normalization and minute regen stay separate.
The pinned source has no weapon_scale/class_scale overrides: both use x1.
Nonempty calibration tables are exercised by source-generated CI fixtures.
Mob copies use frozen source records and modes. Old profiles never use these values.
No imported simulator engine, Monte Carlo work, database or per-hit file I/O.
"""
from functools import lru_cache
import math

import combat
import inventory
import progression
import items
from training import display as training_display
from training import items as training_items

from battle_balance import (data, coefficients, intellect, healing_multiplier,
    cooldown_seconds, level, reference_armour, split, critical, ranged_critical,
    DAMAGE_PER_INTELLECT, MIN_LEVEL_DAMAGE, LEVEL_DAMAGE, LEVEL_SPREAD, KEY)


@lru_cache(maxsize=1)
def disabled_sources():
    return frozenset(data().get('disabled_sources', ()))


def enabled(actor):
    ground = (getattr(getattr(actor, 'sess', None), 'ground', None)
              or getattr(actor, 'training_ground', None))
    return bool(ground and ground.rules.simulator_formulas)


def damage_multiplier(character, row):
    missing = 0
    power = 1
    if row is not None:
        source = training_items.profile_source(row['type_id'])
        missing = max(0, inventory.item_level(row['type_id']) - character.level)
        power, kind = weapon_reference(source)
        curve = data()['class_scale'].get(kind, {})
        own = curve.get(str(character.level), 1)
        at_weapon = curve.get(str(min(20, inventory.item_level(row['type_id']))), 1)
        power *= min(own, at_weapon) if missing else own
    multiplier = power * (1 + DAMAGE_PER_INTELLECT * intellect(character)) * max(MIN_LEVEL_DAMAGE, 1 - LEVEL_DAMAGE * missing)
    return multiplier, 1 + LEVEL_SPREAD * missing


@lru_cache(maxsize=None)
def weapon_reference(source):
    if source in training_items.PROTOTYPES:
        record = training_items.PROTOTYPES[source]
        return data()['weapon_scale'].get(str(record['simulator_id']), 1), record['data']['class']
    kind = ('blade' if items.root_of(source) == items.COLD_ARM else
            {items.PISTOL: 'pistol', items.SHOTGUN: 'shotgun', items.SMG: 'smg',
             items.ASSAULT: 'assault', items.RIFLE: 'rifle', items.MACHINEGUN: 'machinegun'}.get(
                 training_display.weapon_class(source), 'fist'))
    return data()['weapon_scale'].get(str(source), 1), kind


def configure_mob(mob, ground):
    """Copy a frozen source record at spawn, never change shared MobStats."""
    record = data()['mob_records'][data()['mobs'][str(mob.type_id)]]
    for field in ('level', 'hp_max', 'sp_max', 'ap_max', 'armor', 'dodge', 'hit', 'crit_evade',
                  'crit', 'spec', 'ranged', 'range', 'shots', 'dmg_min', 'dmg_max', 'attack_ap', 'attack_time'):
        setattr(mob.stats, field, record[field])
    mob.stats.armor = (mob.stats.armor + ground.rules.effect_armour) * ground.rules.armour
    gun = record['gun']
    mob.training_weapon_class = record['weapon_class']
    if gun in training_items.COPIES:
        mob.stats.weapon_type_id = training_items.copy_type(gun, simulator=True)
    modes = []
    for row in record['modes']:
        weapon = combat.Weapon(row['shots'], row['dmin'], row['dmax'], row.get('opt_lo', 1),
            row.get('opt_hi', row['reach']), row['reach'], row.get('piercing', 1), row.get('cone', 0),
            row['crit'], None, None, sdmin=row.get('sdmin', 0), sdmax=row.get('sdmax', 0))
        weapon = weapon._replace(cone=weapon.cone * ground.rules.spread)
        modes.append((weapon, row['ap'], row['time']))
    mob.training_modes = tuple(modes)
    mob.training_weapon = max(modes, key=lambda mode: mode[0].max_range)[0]


def mob_mode(mob, distance):
    choices = []
    for weapon, cost, delay in mob.training_modes:
        if distance <= weapon.max_range:
            worth = combat.hit_probability(weapon.cone, distance) * (weapon.dmin + weapon.dmax) * weapon.num_shots / max(1, cost)
            choices.append((worth, weapon, cost, delay))
    return max(choices, key=lambda choice: choice[0])[1:] if choices else None


def weapon(weapon, character, row, ammo, rules, mode=None):
    if row is not None:
        source = training_items.profile_source(row['type_id'])
        base = data()['weapon_bases'].get(str(source))
        selected = row.get('cur_mode') if mode is None else mode
        if base is not None and selected is not None:
            weapon = weapon._replace(**{field: base[key][selected]
                for key, field in (('h_damage_min', 'dmin'), ('h_damage_max', 'dmax'),
                                   ('st_damage_min', 'sdmin'), ('st_damage_max', 'sdmax')) if key in base})
    multiplier, spread = damage_multiplier(character, row)
    damage, stamina, reach = rules.ammunition(ammo)
    # Scale just once, as in LavaFixed, with the shared sandbox limits.
    # The simulator changes maximum reach; its original cone and optimal band stay.
    return weapon._replace(dmin=max(1, round(weapon.dmin * multiplier * damage)),
        dmax=max(1, round(weapon.dmax * multiplier * damage)),
        sdmin=round(weapon.sdmin * multiplier * stamina), sdmax=round(weapon.sdmax * multiplier * stamina),
        max_range=math.floor(weapon.max_range * reach + 1e-9), cone=weapon.cone * spread * rules.spread)


def melee(bounds, character, row):
    if row is not None:
        source = training_items.profile_source(row['type_id'])
        base = data()['melee_bases'].get(str(source))
        if base is not None:
            strength = character.attr(progression.STRENGTH)
            bounds = tuple(max(1, base[field] + strength) for field in ('h_damage_min', 'h_damage_max'))
    multiplier, _spread = damage_multiplier(character, row)
    return tuple(max(1, round(value * multiplier)) for value in bounds)


def profile():
    from training.profiles import Profile
    from training.rules import Rules, simulator_notes
    return Profile(KEY, 'Ребаланс после симуляций - 11.11.2026',
                   Rules(revision=KEY, ammo_modifiers=True, simulator_formulas=True),
                   simulator_notes() + ('Особые предметы: классические излучатели, арбалет и ракетница '
                   'сохраняют восстановленные параметры полигона. P-варианты без данных симулятора '
                   'не заменяются предполагаемыми A/G-значениями.',))
