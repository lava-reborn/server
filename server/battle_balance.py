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
ORDINARY_LEVEL_ACCURACY = .05
MOB_BALANCE_DIVISOR = 1.5


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


@lru_cache(maxsize=1)
def ordinary_plus_three():
    """Reviewed ordinary +3 encounter curve, separate from bosses and the range."""
    raw = json.loads(PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
    if raw['source_commit'] != data()['source_commit']:
        raise ValueError('Combat catalogue and equations have different sources')
    factors = raw['ordinary_plus_three']
    if (set(factors) != {'player_damage_ratio', 'mob_damage_ratio'}
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) or not 0 < value <= 1 for value in factors.values())):
        raise ValueError('Invalid ordinary +3 damage coefficients')
    return MappingProxyType(factors)


@lru_cache(maxsize=1)
def ordinary_mob_pressure():
    """Live camp pressure; private range, bosses and site copies stay separate."""
    raw = json.loads(PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
    row = raw['ordinary_mob_pressure']
    fields = {'damage_scale', 'high_gap_damage_scale', 'stamina_ratio', 'senior_stamina_ratio',
              'stamina_levels', 'crit_bounds'}
    bounds = row.get('crit_bounds', ())
    if (raw['source_commit'] != data()['source_commit'] or set(row) != fields
            or len(row['stamina_levels']) != 2
            or any(type(v) is not int for v in row['stamina_levels'])
            or not 1 <= row['stamina_levels'][0] < row['stamina_levels'][1] <= 20
            or any(isinstance(row[k], bool) or not isinstance(row[k], (int, float))
                   or not math.isfinite(row[k]) or not 0 <= row[k] <= 5
                   for k in ('damage_scale', 'high_gap_damage_scale', 'stamina_ratio', 'senior_stamina_ratio'))
            or not .5 <= row['damage_scale'] <= 2 or not 1 <= row['high_gap_damage_scale'] <= 3
            or len(bounds) != 6
            or any(len(pair) != 2 or any(type(v) is not int for v in pair)
                   or not 0 <= pair[0] <= pair[1] <= 25 for pair in bounds)
            or any(bounds[i][j] > bounds[i + 1][j] for i in range(5) for j in range(2))):
        raise ValueError('Invalid ordinary mob pressure')
    return MappingProxyType(dict(row, crit_bounds=tuple(tuple(pair) for pair in bounds),
                                 stamina_levels=tuple(row['stamina_levels'])))


def ordinary_attacker(shooter, target, ordinary):
    return (ordinary and not shooter.is_player and target.is_player
            and getattr(shooter.stats, 'role', None) in ('mob', 'animal', 'turret')
            and not getattr(shooter, '_holding_prepared', False))


def split(shooter, target, damage, piercing, critical, stamina_left, stamina_damage=0, melee=False, rifle=False, ordinary=False):
    if ordinary_attacker(shooter, target, ordinary):
        pressure = ordinary_mob_pressure()
        scale = pressure['damage_scale']
        if level(shooter) - level(target) >= 5:
            scale *= pressure['high_gap_damage_scale']
        damage = max(1, int(damage * scale)) if damage > 0 else 0
        low, high = pressure['stamina_levels']
        step = max(0, min(1, (level(shooter) - low) / (high - low)))
        ratio = pressure['stamina_ratio'] + step * (pressure['senior_stamina_ratio'] - pressure['stamina_ratio'])
        stamina_damage = int(stamina_damage * scale) + int(damage * ratio)
    if shooter.is_player and not target.is_player and getattr(target.stats, 'role', None) != 'object':
        player_level = level(shooter)
        gap = level(target) - player_level
        # Ordinary PvE moves the reviewed difficulty steps up one level:
        # +1 uses the former equal-level factor, +5 the former +4 factor.
        # The private simulator and player-versus-player formulas stay pinned.
        if ordinary:
            gap -= 1
        if ordinary and getattr(target.stats, 'role', None) == 'boss':
            gap -= 2
        factors = coefficients()[1].get(max(1, min(20, player_level)), {})
        factor = factors.get(min(gap, GAP_MAX), 1) if gap >= 1 else 1
        if ordinary and gap == 2:
            factor = ordinary_plus_two().get(player_level, factor)
        elif ordinary and gap == 3 and getattr(target.stats, 'role', None) in ('mob', 'animal', 'turret'):
            factor = max(factors.get(GAP_MAX, 1), ordinary_plus_two().get(player_level, factors.get(2, 1))
                         * ordinary_plus_three()['player_damage_ratio'])
        damage = max(1, int(damage * factor)) if damage > 0 else 0
        stamina_damage = int(stamina_damage * factor)
    elif (ordinary and not shooter.is_player and target.is_player
            and getattr(shooter.stats, 'role', None) in ('mob', 'animal', 'turret')
            and level(shooter) - level(target) == 4):
        factor = ordinary_plus_three()['mob_damage_ratio']
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


def critical(shooter, target, chance, optimal=True, *, ordinary=False):
    if shooter.is_player and not optimal and not ordinary:
        return False
    chance = max(0, min(100, chance))
    if not shooter.is_player and target.is_player:
        if ordinary_attacker(shooter, target, ordinary):
            gap = max(0, min(5, level(shooter) - level(target)))
            low, high = ordinary_mob_pressure()['crit_bounds'][gap]
            chance = max(low, min(high, chance))
        else:
            chance = max(MOB_CRIT_FLOOR, chance)
    if ordinary and not optimal:
        chance *= .5
    import combat
    return combat.roll(chance)


def ranged_critical(shooter, target, weapon, optimal, *, ordinary=False):
    return critical(shooter, target, weapon.crit - target.crit_evade_ranged(), optimal,
                    ordinary=ordinary)


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
    power = 1 + DAMAGE_PER_INTELLECT * intellect(character)
    damage, stamina, reach = (ammo.get(key, 1) for key in ('dam_mod', 'st_mod', 'range_mod'))
    return weapon._replace(dmin=max(1, round(weapon.dmin * power * damage)),
        dmax=max(1, round(weapon.dmax * power * damage)),
        sdmin=round(weapon.sdmin * power * stamina), sdmax=round(weapon.sdmax * power * stamina),
        max_range=math.floor(weapon.max_range * reach + 1e-9),
        cone=weapon.cone / (1 - ORDINARY_LEVEL_ACCURACY * min(inventory.GEAR_LEVEL_ALLOWANCE, missing)))


def melee(bounds, character, row):
    power = 1 + DAMAGE_PER_INTELLECT * intellect(character)
    return tuple(max(1, round(value * power)) for value in bounds)


@lru_cache(maxsize=1)
def boss_adjustments():
    """Reviewed ordinary bosses only; site defenders use local room copies."""
    raw = json.loads(PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
    result = {int(key): row for key, row in raw.get('boss_adjustments', {}).items()}
    for type_id, row in result.items():
        if (str(type_id) not in data()['mobs'] or set(row) != {'damage_scale', 'hp_scale'}
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) or not 0 < v <= 2 for v in row.values())
                or row['hp_scale'] not in (.5, 1)):
            raise ValueError('Invalid ordinary boss adjustment: ' + str(type_id))
    return result


@lru_cache(maxsize=1)
def ordinary_mob_reference():
    """One reviewed level ladder for ordinary mobs, including legacy types."""
    raw = json.loads(PATH.with_name('combat_balance.json').read_text(encoding='utf-8'))
    if raw['source_commit'] != data()['source_commit']:
        raise ValueError('Mob references and equations have different sources')
    references = {int(key): row for key, row in raw['ordinary_mob_reference'].items()}
    fields = {'hp_max', 'sp_max', 'armor', 'dodge', 'hit', 'crit', 'crit_evade', 'spec', 'damage_per_ap'}
    if (set(references) != set(range(1, 21))
            or any(set(row) != fields or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or v < 0 for v in row.values())
                   or row['hp_max'] <= 0 or row['damage_per_ap'] <= 0 for row in references.values())):
        raise ValueError('Invalid ordinary mob references')
    if any(references[level][field] > references[level + 1][field]
           for level in range(1, 20) for field in fields):
        raise ValueError('Ordinary mob references must not decrease with level')
    fallbacks = {}
    for key, index in raw['ordinary_mob_fallbacks'].items():
        level, weapon_class = key.split(':')
        if type(index) is not int or not 0 <= index < len(data()['mob_records']):
            raise ValueError('Invalid ordinary mob fallback')
        row = data()['mob_records'][index]
        if row['level'] != int(level) or row['weapon_class'] != weapon_class:
            raise ValueError('Ordinary mob fallback has a different level or weapon')
        fallbacks[(int(level), weapon_class)] = index
    return references, fallbacks


def configure_mob(stats, *, health_scale=1, damage_scale=1, site=False):
    """Only existing combat creatures; harvest objects keep their own rules."""
    if stats.role not in ('mob', 'boss', 'animal', 'turret'):
        return
    original_hp, original_sp = stats.hp_max, stats.sp_max
    references, fallbacks = ordinary_mob_reference()
    index = data()['mobs'].get(str(stats.type_id))
    if index is None and stats.role == 'mob' and stats.can_attack and not site:
        index = fallbacks.get((stats.level, stats.weapon_class))
    row = data()['mob_records'][index] if index is not None else None
    if row is not None:
        for key in ('level', 'hp_max', 'sp_max', 'ap_max', 'armor', 'dodge', 'hit', 'crit_evade',
                    'crit', 'spec', 'ranged', 'range', 'shots', 'dmg_min', 'dmg_max', 'attack_ap', 'attack_time'):
            setattr(stats, key, row[key])
        stats.weapon_class = row['weapon_class']
        stats.balanced_modes = tuple(row['modes'])
    reference = references.get(stats.level) if stats.role == 'mob' and stats.can_attack and not site else None
    if reference is not None:
        for key, value in reference.items():
            if key != 'damage_per_ap':
                setattr(stats, key, value)
    adjustment = boss_adjustments().get(stats.type_id)
    if adjustment is not None and stats.role == 'boss':
        stats.hp_max = max(1, round(stats.hp_max * adjustment['hp_scale']))
        damage_scale *= adjustment['damage_scale']
    # Apply site multipliers before the common reduction, exactly once.
    # Even creatures absent from the simulator retain the original pool floor.
    stats.hp_max = max(original_hp, round(stats.hp_max * health_scale / MOB_BALANCE_DIVISOR))
    stats.sp_max = max(original_sp, round(stats.sp_max * health_scale / MOB_BALANCE_DIVISOR))
    factor = damage_scale / MOB_BALANCE_DIVISOR
    if reference is not None and stats.shots > 0 and stats.attack_ap > 0:
        power = (stats.dmg_min + stats.dmg_max) / 2 * stats.shots / stats.attack_ap
        if power > 0:
            factor *= reference['damage_per_ap'] / power
    stats.dmg_min = max(0, round(stats.dmg_min * factor))
    stats.dmg_max = max(stats.dmg_min, round(stats.dmg_max * factor))
    if row is not None:
        # Never mutate the shared pinned modes: private range clones and
        # another mob of the same type must not accumulate this multiplier.
        modes = []
        for mode in row['modes']:
            factor = damage_scale / MOB_BALANCE_DIVISOR
            if reference is not None:
                power = (mode['dmin'] + mode['dmax']) / 2 * mode['shots'] / max(1, mode['ap'])
                if power > 0:
                    factor *= reference['damage_per_ap'] / power
            modes.append(dict(mode,
                crit=stats.crit, hit=stats.hit,
                dmin=max(1, round(mode['dmin'] * factor)),
                dmax=max(1, round(mode['dmax'] * factor)),
                sdmin=round(mode.get('sdmin', 0) * factor),
                sdmax=round(mode.get('sdmax', 0) * factor)))
        stats.balanced_modes = tuple(modes)
    import items
    if row is not None and row['gun'] in items.catalogue():
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
