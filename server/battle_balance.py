"""Shared combat equations from the pinned 11.11.2026 simulator profile.

The game and the training adapter use one implementation. Static tables are
read once; hit resolution does not import the range or read files/databases.
"""
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

import progression

PATH = Path(__file__).resolve().parents[1] / 'data/training_simulator_formulas.json'
KEY = 'simulator-v1'
SNAPSHOT_VERSION = 1
INTELLECT_BASE = 5
DAMAGE_PER_INTELLECT = .03
HEAL_PER_INTELLECT = .04
COOLDOWN_PER_INTELLECT = .1
MIN_COOLDOWN = 2.0
SIMULATOR_MEDICINE_COOLDOWN = 4.0
MAX_ARMOUR_SHARE = .9
ARMOUR_LEVEL_GAP = 1
MOB_CRIT_FLOOR = 5.0
LEVEL_SPREAD = .6
LEVEL_DAMAGE = .12
MIN_LEVEL_DAMAGE = .1
GAP_MAX = 3


@lru_cache(maxsize=1)
def data():
    raw = json.loads(PATH.read_text(encoding='utf-8'))
    if raw.get('version') != SNAPSHOT_VERSION or raw.get('engine') != KEY:
        raise ValueError('Unsupported simulator snapshot')
    if not re.fullmatch(r'[0-9a-f]{40}', raw.get('source_commit', '')):
        raise ValueError('Simulator source revision must be pinned')
    expected = dict(INT_DAMAGE=DAMAGE_PER_INTELLECT, INT_HEAL=HEAL_PER_INTELLECT,
                    INT_COOLDOWN=COOLDOWN_PER_INTELLECT, COOLDOWN_FLOOR=MIN_COOLDOWN,
                    ARMOR_SHARE_CAP=MAX_ARMOUR_SHARE, ARMOR_GAP=ARMOUR_LEVEL_GAP,
                    MOB_CRIT_FLOOR=MOB_CRIT_FLOOR / 100,
                    LEVEL_SPREAD=LEVEL_SPREAD, LEVEL_DAMAGE=LEVEL_DAMAGE)
    if raw.get('equations') != expected:
        raise ValueError('Simulator equations changed; port and version the engine before exporting')
    tables = [raw['weapon_scale'], *raw['class_scale'].values()]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= 100
           for table in tables for v in table.values()):
        raise ValueError('Invalid simulator calibration')
    if (len(raw['mob_records']) > 2048 or any(type(index) is not int or not 0 <= index < len(raw['mob_records'])
                                           for index in raw['mobs'].values())
            or any(not 1 <= len(record['modes']) <= 3 for record in raw['mob_records'])):
        raise ValueError('Invalid simulator mob profiles')
    return raw


@lru_cache(maxsize=1)
def coefficients():
    raw = data()
    armour = {int(k): v for k, v in raw['armour_reference'].items()}
    gaps = {int(k): {int(g): v for g, v in row.items()} for k, row in raw['gap_table'].items()}
    valid = lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
    if (set(armour) != set(range(1, 21)) or any(not valid(v) or v <= 0 for v in armour.values())
            or any(k not in range(1, 21) or any(g not in (1, 2, 3) or not valid(v) or not 0 < v <= 1
                for g, v in row.items()) for k, row in gaps.items())):
        raise ValueError('Invalid simulator equation coefficients')
    return MappingProxyType(armour), MappingProxyType({k: MappingProxyType(row) for k, row in gaps.items()})


def intellect(character):
    return max(0, character.attr(progression.INTELLECT) - INTELLECT_BASE)


def healing_multiplier(character):
    return 1 + HEAL_PER_INTELLECT * intellect(character)


def cooldown_seconds(character):
    return max(MIN_COOLDOWN, SIMULATOR_MEDICINE_COOLDOWN - COOLDOWN_PER_INTELLECT * intellect(character))


def level(actor):
    return actor.character().level if actor.is_player else actor.stats.level


def reference_armour(target_level):
    return coefficients()[0][max(1, min(20, target_level))]


@lru_cache(maxsize=1)
def ordinary_plus_two():
    """Ordinary fights use the reviewed +2 curve; the pinned range stays intact."""
    raw = json.loads(PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
    if raw['source_commit'] != data()['source_commit']:
        raise ValueError('Combat catalogue and equations have different sources')
    factors = {int(key): value for key, value in raw['ordinary_plus_two'].items()}
    original = coefficients()[1]
    if any(level not in original or isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) or not original[level][2] <= value <= original[level][1]
           for level, value in factors.items()):
        raise ValueError('Invalid ordinary +2 damage coefficients')
    return MappingProxyType(factors)


def split(shooter, target, damage, piercing, critical, stamina_left, stamina_damage=0, melee=False, rifle=False, ordinary=False):
    if shooter.is_player and not target.is_player and getattr(target.stats, 'role', None) != 'object':
        player_level = level(shooter)
        gap = level(target) - player_level
        if ordinary and getattr(target.stats, 'role', None) == 'boss':
            gap -= 2
        factors = coefficients()[1].get(max(1, min(20, player_level)), {})
        factor = factors.get(min(gap, GAP_MAX), 1) if gap >= 1 else 1
        if ordinary and gap == 2:
            factor = ordinary_plus_two().get(player_level, factor)
        damage = max(1, int(damage * factor)) if damage > 0 else 0
        stamina_damage = int(stamina_damage * factor)
    left = max(0, stamina_left)
    if critical:
        return damage, 0 if melee else min(damage, left)
    armour = max(0, target.armor()) / max(.5, piercing)
    if rifle and not melee:
        share = min(MAX_ARMOUR_SHARE, armour / (armour + reference_armour(level(target))))
    else:
        share = min(1, armour / max(1, reference_armour(level(shooter) - ARMOUR_LEVEL_GAP)))
    moved = int(damage * share)
    stamina = stamina_damage + moved
    return damage - moved + max(0, stamina - left), min(stamina, left)


def critical(shooter, target, chance, optimal=True):
    if shooter.is_player and not optimal:
        return False
    chance = max(0, min(100, chance))
    if not shooter.is_player and target.is_player:
        chance = max(MOB_CRIT_FLOOR, chance)
    import combat
    return combat.roll(chance)


def ranged_critical(shooter, target, weapon, optimal):
    return critical(shooter, target, weapon.crit - target.crit_evade_ranged(), optimal)


@lru_cache(maxsize=1)
def equipment_changes():
    path = PATH.with_name('combat_balance.json')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if raw['source_commit'] != data()['source_commit']:
        raise ValueError('Combat catalogue and equations have different sources')
    return {int(key): row for key, row in raw['equipment'].items()}


def weapon(weapon, character, row, ammo):
    """Ordinary equipment already holds the reviewed base damage and ranges."""
    import inventory
    missing = max(0, inventory.item_level(row['type_id']) - character.level) if row else 0
    power = (1 + DAMAGE_PER_INTELLECT * intellect(character)) * max(MIN_LEVEL_DAMAGE, 1 - LEVEL_DAMAGE * missing)
    damage, stamina, reach = (ammo.get(key, 1) for key in ('dam_mod', 'st_mod', 'range_mod'))
    return weapon._replace(dmin=max(1, round(weapon.dmin * power * damage)),
        dmax=max(1, round(weapon.dmax * power * damage)),
        sdmin=round(weapon.sdmin * power * stamina), sdmax=round(weapon.sdmax * power * stamina),
        max_range=math.floor(weapon.max_range * reach + 1e-9),
        cone=weapon.cone * (1 + LEVEL_SPREAD * missing))


def melee(bounds, character, row):
    import inventory
    missing = max(0, inventory.item_level(row['type_id']) - character.level) if row else 0
    power = (1 + DAMAGE_PER_INTELLECT * intellect(character)) * max(MIN_LEVEL_DAMAGE, 1 - LEVEL_DAMAGE * missing)
    return tuple(max(1, round(value * power)) for value in bounds)


def configure_mob(stats):
    """Only existing combat creatures; harvest objects keep their own rules."""
    index = data()['mobs'].get(str(stats.type_id))
    if index is None or stats.role not in ('mob', 'boss', 'animal', 'turret'):
        return
    row = data()['mob_records'][index]
    for key in ('level', 'hp_max', 'sp_max', 'ap_max', 'armor', 'dodge', 'hit', 'crit_evade',
                'crit', 'spec', 'ranged', 'range', 'shots', 'dmg_min', 'dmg_max', 'attack_ap', 'attack_time'):
        setattr(stats, key, row[key])
    stats.balanced_modes = tuple(row['modes'])
    stats.weapon_class = row['weapon_class']
    import items
    if row['gun'] in items.catalogue():
        stats.weapon_type_id = row['gun']
        # Retain an explicit carried-ammo quality when the reviewed profile
        # changes calibre. Never leave a mob carrying incompatible rounds.
        ammo = stats.loot_ammo_type
        compatible = items.params_of(row['gun']).get('comp_array', ())
        if ammo is not None and ammo not in compatible:
            quality = items.catalogue()[ammo][1].rsplit('_', 1)[-1]
            stats.loot_ammo_type = next((t for t in compatible
                if items.catalogue()[t][1].rsplit('_', 1)[-1] == quality),
                compatible[0] if compatible else None)


def mob_mode(stats, distance):
    import combat
    choices = []
    for row in getattr(stats, 'balanced_modes', ()):
        if distance > row['reach']:
            continue
        weapon = combat.Weapon(row['shots'], row['dmin'], row['dmax'], row.get('opt_lo', 1),
            row.get('opt_hi', row['reach']), row['reach'], row.get('piercing', 1),
            row.get('cone', 0), row['crit'], None, None,
            sdmin=row.get('sdmin', 0), sdmax=row.get('sdmax', 0))
        worth = combat.hit_probability(weapon.cone, distance) * (weapon.dmin + weapon.dmax) * weapon.num_shots / max(1, row['ap'])
        choices.append((worth, weapon, row['ap'], row['time']))
    return max(choices, key=lambda entry: entry[0])[1:] if choices else None
