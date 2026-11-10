"""Opt-in range equations from simulator 74493c7, rulesets/lava_fixed.py.

The simulator profile uses each weapon's own source coefficient and A/G
damage bases. Old sandbox P/G normalization and minute regen stay separate.
Mob copies use frozen source records and modes. Old profiles never use these values.
No imported simulator engine, Monte Carlo work, database or per-hit file I/O.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
from types import MappingProxyType

import battle_medicine
import combat
import inventory
import progression
import items
import training_display
import training_items

PATH = Path(__file__).resolve().parents[1] / 'data/training_simulator_formulas.json'
INTELLECT_BASE = 5
DAMAGE_PER_INTELLECT = .03
HEAL_PER_INTELLECT = .04
COOLDOWN_PER_INTELLECT = .1
MIN_COOLDOWN = 2.0
MAX_ARMOUR_SHARE = .9
OFF_BAND_CRIT = .5
MOB_CRIT_FLOOR = 5.0
LEVEL_SPREAD = .6
LEVEL_DAMAGE = .12
MIN_LEVEL_DAMAGE = .1
GAP_FROM = 5


@lru_cache(maxsize=1)
def data():
    raw = json.loads(PATH.read_text(encoding='utf-8'))
    tables = [raw['weapon_scale'], *raw['class_scale'].values()]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= 100
           for table in tables for v in table.values()):
        raise ValueError('Invalid simulator calibration')
    if (len(raw['mob_records']) > 2048 or any(not isinstance(index, int) or not 0 <= index < len(raw['mob_records'])
                                           for index in raw['mobs'].values())
            or any(not 1 <= len(record['modes']) <= 3 for record in raw['mob_records'])):
        raise ValueError('Invalid simulator mob profiles')
    return raw


@lru_cache(maxsize=1)
def coefficients():
    raw = data()
    armour = {int(k): v for k, v in raw['armour_reference'].items()}
    bonus = {int(k): v for k, v in raw['near_bonus'].items()}
    gap = raw['gap_damage']
    valid = lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
    if (set(armour) != set(range(1, 21)) or any(not valid(v) or v <= 0 for v in armour.values())
            or any(k not in range(1, 21) or not valid(v) or not 0 <= v <= 4 for k, v in bonus.items())
            or not valid(gap) or not 0 < gap <= 1):
        raise ValueError('Invalid simulator equation coefficients')
    return MappingProxyType(armour), MappingProxyType(bonus), gap


def enabled(actor):
    ground = (getattr(getattr(actor, 'sess', None), 'ground', None)
              or getattr(actor, 'training_ground', None))
    return bool(ground and ground.rules.simulator_formulas)


def intellect(character):
    return max(0, character.attr(progression.INTELLECT) - INTELLECT_BASE)


def healing_multiplier(character):
    return 1 + HEAL_PER_INTELLECT * intellect(character)


def cooldown_seconds(character):
    return max(MIN_COOLDOWN, battle_medicine.COOLDOWN_SECONDS - COOLDOWN_PER_INTELLECT * intellect(character))


def damage_multiplier(character, row):
    missing = 0
    power = 1
    if row is not None:
        source = training_items.profile_source(row['type_id'])
        missing = max(0, inventory.item_level(source) - character.level)
        power, kind = weapon_reference(source)
        curve = data()['class_scale'].get(kind, {})
        own = curve.get(str(character.level), 1)
        at_weapon = curve.get(str(min(20, inventory.item_level(source))), 1)
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
    if gun in training_items.COPIES:
        mob.stats.weapon_type_id = training_items.copy_type(gun)
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
        max_range=weapon.max_range * reach, cone=weapon.cone * spread * rules.spread)


def melee(bounds, character, row):
    if row is not None:
        source = training_items.profile_source(row['type_id'])
        base = data()['melee_bases'].get(str(source))
        if base is not None:
            strength = character.attr(progression.STRENGTH)
            bounds = tuple(max(1, base[field] + strength) for field in ('h_damage_min', 'h_damage_max'))
    multiplier, _spread = damage_multiplier(character, row)
    return tuple(max(1, round(value * multiplier)) for value in bounds)


def level(actor):
    return actor.character().level if actor.is_player else actor.stats.level


def reference_armour(target_level):
    return coefficients()[0][max(1, min(20, target_level))]


def split(shooter, target, damage, piercing, critical, stamina_left, stamina_damage=0, melee=False):
    if shooter.is_player and not target.is_player:
        player_level = level(shooter)
        gap = level(target) - player_level
        _armour, bonus, gap_damage = coefficients()
        factor = gap_damage if gap >= GAP_FROM else 1 + bonus.get(player_level, 0) * gap if gap > 0 else 1
        damage, stamina_damage = max(1, int(damage * factor)), int(stamina_damage * factor)
    left = max(0, stamina_left)
    if critical:
        return damage, 0 if melee else min(damage, left)
    armour = max(0, target.armor()) / max(.5, piercing)
    share = min(MAX_ARMOUR_SHARE, armour / (armour + reference_armour(level(target))))
    moved = int(damage * share)
    stamina = stamina_damage + moved
    return damage - moved + max(0, stamina - left), min(stamina, left)


def critical(shooter, target, chance, optimal=True):
    chance = max(0, min(100, chance))
    if not optimal:
        chance *= OFF_BAND_CRIT
    if not shooter.is_player and target.is_player:
        chance = max(MOB_CRIT_FLOOR, chance)
    return combat.roll(chance)


def ranged_critical(shooter, target, weapon, optimal):
    return critical(shooter, target, weapon.crit - target.crit_evade_ranged(), optimal)
