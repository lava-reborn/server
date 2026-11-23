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
    fields = {'damage_scale', 'high_gap_damage_scale', 'stamina_ratio', 'senior_stamina_ratio', 'hard_gap_stamina_scale',
              'stamina_levels', 'crit_bounds', 'crit_bonus_by_gap', 'player_damage_ratios',
              'camp_hard_gap_damage_ratios'}
    bounds = row.get('crit_bounds', ())
    if (raw['source_commit'] != data()['source_commit'] or set(row) != fields
            or len(row['stamina_levels']) != 2
            or any(type(v) is not int for v in row['stamina_levels'])
            or not 1 <= row['stamina_levels'][0] < row['stamina_levels'][1] <= 20
            or any(isinstance(row[k], bool) or not isinstance(row[k], (int, float))
                   or not math.isfinite(row[k]) or not 0 <= row[k] <= 5
                   for k in ('damage_scale', 'high_gap_damage_scale', 'stamina_ratio', 'senior_stamina_ratio', 'hard_gap_stamina_scale'))
            or not .5 <= row['damage_scale'] <= 2 or not 1 <= row['high_gap_damage_scale'] <= 3
            or not 1 <= row['hard_gap_stamina_scale'] <= 2
            or len(row['player_damage_ratios']) != 5
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 < v <= 1 for v in row['player_damage_ratios'])
            or len(row['camp_hard_gap_damage_ratios']) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) or not 0 < v <= 1 for v in row['camp_hard_gap_damage_ratios'])
            or len(bounds) != 6
            or any(len(pair) != 2 or any(type(v) is not int for v in pair)
                   or not 0 <= pair[0] <= pair[1] <= 100 for pair in bounds)
            or len(row['crit_bonus_by_gap']) != 6
            or any(type(v) is not int or not 0 <= v <= 100 for v in row['crit_bonus_by_gap'])
            or row['crit_bonus_by_gap'][:3] != [0, 0, 0]
            or list(row['crit_bonus_by_gap']) != sorted(row['crit_bonus_by_gap'])
            or any(bounds[i][j] > bounds[i + 1][j] for i in range(5) for j in range(2))):
        raise ValueError('Invalid ordinary mob pressure')
    return MappingProxyType(dict(row, crit_bounds=tuple(tuple(pair) for pair in bounds),
                                 crit_bonus_by_gap=tuple(row['crit_bonus_by_gap']),
                                 camp_hard_gap_damage_ratios=tuple(row['camp_hard_gap_damage_ratios']),
                                 stamina_levels=tuple(row['stamina_levels']),
                                 player_damage_ratios=tuple(row['player_damage_ratios'])))


def ordinary_attacker(shooter, target, ordinary):
    return (ordinary and not shooter.is_player and target.is_player
            and getattr(shooter.stats, 'role', None) in ('mob', 'animal', 'turret')
            and not getattr(shooter, '_holding_prepared', False))


def split(shooter, target, damage, piercing, critical, stamina_left, stamina_damage=0, melee=False, rifle=False, ordinary=False):
    pressure_stamina = 0
    if ordinary_attacker(shooter, target, ordinary) and not getattr(shooter.stats, 'plain_weapon', False):
        pressure = ordinary_mob_pressure()
        scale = pressure['damage_scale']
        if level(shooter) - level(target) >= 5:
            scale *= pressure['high_gap_damage_scale']
        damage = max(1, int(damage * scale)) if damage > 0 else 0
        low, high = pressure['stamina_levels']
        step = max(0, min(1, (level(shooter) - low) / (high - low)))
        ratio = pressure['stamina_ratio'] + step * (pressure['senior_stamina_ratio'] - pressure['stamina_ratio'])
        if level(shooter) - level(target) >= 2:
            ratio *= pressure['hard_gap_stamina_scale']
        stamina_damage = int(stamina_damage * scale)
        pressure_stamina = int(damage * ratio)
    if shooter.is_player and not target.is_player and getattr(target.stats, 'role', None) != 'object':
        player_level = level(shooter)
        gap = level(target) - player_level
        camp = (ordinary and getattr(target.stats, 'role', None) in ('mob', 'animal', 'turret')
                and not getattr(target, '_holding_prepared', False))
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
        if ordinary and gap >= 1:
            pressure = ordinary_mob_pressure()
            factor *= (pressure['camp_hard_gap_damage_ratios'][min(gap - 2, 2)]
                       if camp and gap >= 2 else pressure['player_damage_ratios'][min(gap, 4)])
        # At +5 and above, do not turn an absorbed pellet into guaranteed
        # one-point damage. Keep fractional penetration until this rounding.
        floor = 0 if camp and gap >= 4 else 1
        damage = max(floor, int(damage * factor)) if damage > 0 else 0
        stamina_damage = int(stamina_damage * factor)
    elif (ordinary and not shooter.is_player and target.is_player
            and getattr(shooter.stats, 'role', None) in ('mob', 'animal', 'turret')
            and level(shooter) - level(target) == 4):
        factor = ordinary_plus_three()['mob_damage_ratio']
        damage = max(1, int(damage * factor)) if damage > 0 else 0
        stamina_damage = int(stamina_damage * factor)
        pressure_stamina = int(pressure_stamina * factor)
    left = max(0, stamina_left)
    if critical:
        stamina = 0 if melee else min(damage, left)
        return damage, stamina + min(pressure_stamina, max(0, left - stamina))
    armour = max(0, target.armor()) / max(.5, piercing)
    if rifle and not melee:
        share = min(MAX_ARMOUR_SHARE, armour / (armour + reference_armour(level(target))))
    else:
        share = min(1, armour / max(1, reference_armour(level(shooter) - ARMOUR_LEVEL_GAP)))
    moved = int(damage * share)
    stamina = stamina_damage + moved
    spent = min(stamina, left)
    return (damage - moved + max(0, stamina - left),
            spent + min(pressure_stamina, max(0, left - spent)))


def critical_chance(shooter, target, chance, optimal=True, *, ordinary=False):
    if shooter.is_player and not optimal and not ordinary:
        return 0
    if not shooter.is_player and target.is_player:
        if ordinary_attacker(shooter, target, ordinary):
            gap = max(0, min(5, level(shooter) - level(target)))
            pressure = ordinary_mob_pressure()
            low, high = pressure['crit_bounds'][gap]
            # Add before clamping: the player's full antikrit still offsets it.
            chance = max(low, min(high, chance + pressure['crit_bonus_by_gap'][gap]))
        else:
            chance = max(MOB_CRIT_FLOOR, chance)
    chance = max(0, min(100, chance))
    if ordinary and not optimal:
        chance *= .5
    return chance


def critical(shooter, target, chance, optimal=True, *, ordinary=False):
    if shooter.is_player and not optimal and not ordinary:
        return False
    import combat
    return combat.roll(critical_chance(shooter, target, chance, optimal, ordinary=ordinary))


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
        if (str(type_id) not in data()['mobs'] or set(row) not in (
                {'damage_scale', 'hp_scale'}, {'damage_scale', 'hp_scale', 'level'})
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) or not 0 < v <= 2
                       for v in (row['damage_scale'], row['hp_scale']))
                or row['hp_scale'] not in (.5, 1)
                or ('level' in row and (type(row['level']) is not int or not 1 <= row['level'] <= 20))):
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
    damage_scales = {int(key): value for key, value in raw.get('ordinary_mob_damage_scales', {}).items()}
    if any(type(t) is not int or t <= 0 or isinstance(v, bool) or not isinstance(v, (int, float))
           or not math.isfinite(v) or not .9 <= v <= 1 for t, v in damage_scales.items()):
        raise ValueError('Invalid ordinary mob damage reduction')
    return references, fallbacks, damage_scales


@lru_cache(maxsize=1)
def mob_weapons():
    """Existing plain A items, indexed once by NPC class and required level."""
    import items
    import inventory
    classes = {items.PISTOL: 'pistol', items.SHOTGUN: 'shotgun', items.SMG: 'smg',
               items.ASSAULT: 'assault_rifle', items.RIFLE: 'rifle', items.MACHINEGUN: 'machine_gun'}
    standard = re.compile(r'(?:(?:pistols?|shotgun|assault_rifle|rifle|machine_gun|sub_machine_guns)_\d+_lvl_\d+'
                          r'|knife_lvl\d+_A)')
    result = {}
    for type_id, (root, name) in items.catalogue().items():
        if root not in (items.FIRE_ARM, items.COLD_ARM) or not standard.fullmatch(name):
            continue
        params = items.params_of(type_id)
        if not params or not params.get('cost') or params.get('g_cost') or items.out_of_game(type_id):
            continue
        kind = 'knife' if root == items.COLD_ARM else classes.get(params.get('weapon_type'))
        if kind is not None:
            result.setdefault(kind, []).append((inventory.item_level(type_id), params['cost'], type_id))
    return MappingProxyType({kind: tuple(sorted(rows)) for kind, rows in result.items()})


def equip_mob(stats, damage_scale, *, site=False):
    """Plain A item modes; camps use KS, defended sites retain their ST profile."""
    if not stats.can_attack or stats.role not in ('mob', 'boss', 'turret', 'animal'):
        return False
    kind = {'assault': 'assault_rifle', 'machinegun': 'machine_gun'}.get(stats.weapon_class, stats.weapon_class)
    if site and stats.role == 'boss' and kind == 'pistol':
        # Named pistol bosses retain their reviewed, stronger NPC attacks.
        return False
    if not stats.ranged:
        kind = 'knife'
    weapons = mob_weapons()
    choices = [row for row in weapons.get(kind, ()) if row[0] == stats.level]
    if not choices and stats.ranged:
        alternatives = {
            'pistol': ('smg', 'assault_rifle', 'shotgun', 'rifle', 'machine_gun'),
            'shotgun': ('assault_rifle', 'smg', 'machine_gun', 'rifle', 'pistol'),
            'assault_rifle': ('machine_gun', 'smg', 'rifle', 'shotgun', 'pistol'),
            'rifle': ('assault_rifle', 'smg', 'machine_gun', 'shotgun', 'pistol'),
            'smg': ('assault_rifle', 'shotgun', 'machine_gun', 'rifle', 'pistol'),
            'machine_gun': ('assault_rifle', 'smg', 'rifle', 'shotgun', 'pistol'),
        }.get(kind, ())
        if stats.level < min((row[0] for row in weapons.get(kind, ())), default=math.inf):
            alternatives = ('pistol', *alternatives)
        for candidate in alternatives:
            choices = [row for row in weapons.get(candidate, ()) if row[0] == stats.level]
            if choices:
                kind = candidate
                break
    if not choices:
        choices = [row for row in weapons.get(kind, ()) if row[0] <= stats.level]
    if not choices:
        return False
    import items
    import combat
    type_id = max(choices, key=lambda row: (row[0], row[1], -row[2]))[2]
    params = items.params_of(type_id)
    factor = damage_scale / MOB_BALANCE_DIVISOR
    if not site:
        factor = min(1, factor)
        stats.plain_weapon = True
    if stats.role == 'animal':
        # A knife is a damage ceiling, not an item put in an animal's paws.
        stats.dmg_min = max(1, round(min(stats.dmg_min, params['h_damage_min']) * factor))
        stats.dmg_max = max(stats.dmg_min, round(min(stats.dmg_max, params['h_damage_max']) * factor))
        stats.weapon_type_id = stats.loot_ammo_type = None
        if hasattr(stats, 'balanced_modes'):
            del stats.balanced_modes
        return True
    stats.weapon_type_id = type_id
    stats.weapon_class = kind
    if not stats.ranged:
        stats.dmg_min = max(1, round(params['h_damage_min'] * factor))
        stats.dmg_max = max(stats.dmg_min, round(params['h_damage_max'] * factor))
        stats.attack_ap = params['strike_cost']
        stats.attack_time = params['strike_time'] / 1000
        stats.shots, stats.range = 1, 1
        stats.loot_ammo_type = None
        if hasattr(stats, 'balanced_modes'):
            del stats.balanced_modes
        stats.ap_max = max(stats.ap_max, stats.attack_ap)
        return True
    quality = '_ST' if site else '_KS'
    ammo_type = next(t for t in params['comp_array'] if items.catalogue()[t][1].endswith(quality))
    ammo = items.params_of(ammo_type)
    stats.loot_ammo_type = ammo_type
    modes = []
    for mode, shots in enumerate(params['fire_mods']):
        if not shots or not params['max_range'][mode]:
            continue
        damage = factor * ammo.get('dam_mod', 1)
        stamina = factor * ammo.get('st_mod', 1)
        modes.append(dict(shots=shots, ap=params['fire_costs'][mode], time=params['fire_times'][mode] / 1000,
            reach=math.floor(params['max_range'][mode] * ammo.get('range_mod', 1) + 1e-9),
            opt_lo=params['opt_range'][mode], opt_hi=params['end_opt_range'][mode],
            dmin=max(1, round(params['h_damage_min'][mode] * damage)),
            dmax=max(1, round(params['h_damage_max'][mode] * damage)),
            sdmin=round(params.get('st_damage_min', [0, 0, 0])[mode] * stamina),
            sdmax=round(params.get('st_damage_max', [0, 0, 0])[mode] * stamina),
            piercing=ammo.get('piercing', 1), crit=stats.crit, hit=stats.hit,
            cone=combat.cone_of(combat.spread_factor(stats.level, stats.spec), params['target_size'][mode],
                                ammo.get('acc_mod', 1) or 1, params['max_range'][mode])))
    stats.balanced_modes = tuple(modes)
    row = max(modes, key=lambda row: row['reach'])
    stats.range, stats.shots = row['reach'], row['shots']
    stats.dmg_min, stats.dmg_max = row['dmin'], row['dmax']
    stats.attack_ap, stats.attack_time = row['ap'], row['time']
    stats.ap_max = max(stats.ap_max, max(row['ap'] for row in modes))
    return True


def configure_mob(stats, *, health_scale=1, damage_scale=1, site=False):
    """Only existing combat creatures; harvest objects keep their own rules."""
    if stats.role not in ('mob', 'boss', 'animal', 'turret'):
        return
    original_hp, original_sp = stats.hp_max, stats.sp_max
    references, fallbacks, damage_scales = ordinary_mob_reference()
    if stats.can_attack and stats.role in ('mob', 'animal', 'turret') and not site:
        damage_scale *= damage_scales.get(stats.type_id, 1)
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
        stats.level = adjustment.get('level', stats.level)
        stats.hp_max = max(1, round(stats.hp_max * adjustment['hp_scale']))
        damage_scale *= adjustment['damage_scale']
    # Apply site multipliers before the common reduction, exactly once.
    # Even creatures absent from the simulator retain the original pool floor.
    stats.hp_max = max(original_hp, round(stats.hp_max * health_scale / MOB_BALANCE_DIVISOR))
    stats.sp_max = max(original_sp, round(stats.sp_max * health_scale / MOB_BALANCE_DIVISOR))
    if equip_mob(stats, damage_scale, site=site):
        return
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
        if stats.ranged:
            compatible = items.params_of(row['gun']).get('comp_array', ())
            stats.loot_ammo_type = next((t for t in compatible
                if items.catalogue()[t][1].endswith('_ST')), None)


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
