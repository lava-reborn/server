"""Deterministic source-generated examples; never imported by the game server.

Expected outputs come from the pinned simulator, not from the range engine.
Keep this fixture separate from runtime metadata so players do not load tests.
"""
from types import SimpleNamespace as NS
from unittest.mock import patch
import math


def reference_cases(reference, snapshot):
    from training.config import PROTOTYPE_FIRST

    keys = ('dmin', 'dmax', 'sdmin', 'sdmax', 'cone', 'opt_lo', 'opt_hi')
    selected = set()
    for kind in ('pistol', 'shotgun', 'smg', 'assault', 'rifle', 'machinegun'):
        candidates = [int(t) for t in snapshot['weapon_bases']
                      if reference.weapons[int(t)]['class'] == kind
                      and int(t) not in reference.withdrawn]
        first = min(candidates, key=lambda t: (reference.need(reference.weapons[t]), t))
        last = max(candidates, key=lambda t: (reference.need(reference.weapons[t]), t))
        selected.update((first, last))
        selected.update(twin for t in (first, last)
                        if (twin := reference.gun_twin(t, 'G')) in candidates)
    selected.update(reference.new_guns)
    ranged, calibrated = [], []
    for type_id in sorted(selected):
        gun = reference.weapons[type_id]
        source = PROTOTYPE_FIRST + type_id - 900000 if type_id in reference.new_guns else type_id
        need = max(1, min(20, reference.need(gun)))
        ammo_ids = [t for t in gun['comp_array'] if t in reference.ammo]
        ammo_ids = sorted({ammo_ids[0], ammo_ids[-1]}) if ammo_ids else [None]
        for level in sorted({need, max(1, need - 2)}):
            for intellect in (5, 13):
                for mode, shots in enumerate(gun['fire_mods']):
                    if not shots:
                        continue
                    for ammo_id in ammo_ids:
                        spec = dict(skills={'shooting': level}, specs={gun['class']: 3},
                                    attribs={'int': intellect}, weapon=type_id, mode=mode, ammo=ammo_id)
                        fighter = reference.build(spec)
                        row = dict(source=source, simulator_id=type_id, level=level, mode=mode,
                                   kind=gun['class'], attrs=fighter.x['attrs'], shooting=level,
                                   ammo={k: v for k, v in reference.ammo.get(ammo_id, {}).items()
                                         if k in ('piercing', 'acc_mod', 'dam_mod', 'st_mod', 'range_mod')},
                                   expected={k: fighter.attack.data.get(k, 0) for k in keys},
                                   reach=fighter.attack.reach, shots=fighter.attack.projectiles,
                                   ap=fighter.attack.ap, time=fighter.attack.windup)
                        ranged.append(row)
                        if source == type_id and need > 1 and intellect == 13 and mode == 0 and len(calibrated) < 12:
                            own = .6 if len(calibrated) % 2 else 1.2
                            tables = dict(weapon_scale={type_id: 1.3},
                                          class_scale={gun['class']: {level: own, need: .8}})
                            with patch.multiple(reference, **tables):
                                changed = reference.build(spec)
                            calibrated.append(dict(row, calibration=dict(
                                weapon_scale={str(type_id): 1.3},
                                class_scale={gun['class']: {str(level): own, str(need): .8}}),
                                expected={k: changed.attack.data.get(k, 0) for k in keys}))

    melee = []
    blades = sorted(int(t) for t in snapshot['melee_bases'])
    for source in (None, blades[0], blades[-1]):
        for level in (1, 12, 20):
            for intellect in (5, 13):
                spec = dict(skills={'melee': level}, specs={'blade': 3, 'fist': 3},
                            attribs={'str': 17, 'int': intellect}, weapon=source)
                fighter = reference.build(spec)
                melee.append(dict(source=source, level=level, attrs=fighter.x['attrs'],
                                  expected=[fighter.attack.data[k] for k in ('dmin', 'dmax')]))

    critical = []
    for player in (False, True):
        for target_player in (False, True):
            for optimal in (False, True):
                for chance in (-5, 30, 160):
                    # Use ranged attacks: melee hit-range checks belong to combat.
                    attacker = NS(x={'player': player})
                    target = NS(x={'player': target_player, 'ranged_crit_evade': 0, 'crit_evade': 0})
                    attack = NS(kind='ranged', reach=10, data=dict(crit=chance, opt_lo=2, opt_hi=4))
                    expected = reference.crit_chance(attacker, attack, target, 3 if optimal else 6)
                    critical.append(dict(player=player, target_player=target_player, optimal=optimal,
                                         chance=chance, expected=expected * 100))
    return dict(version=1, source_commit=snapshot['source_commit'], ranged=ranged,
                melee=melee, critical=critical, calibrated=calibrated)


def check_cases(cases, engine, snapshot):
    import combat
    import items
    from training import items as copies
    from training.rules import Rules

    if cases.get('version') != 1 or cases.get('source_commit') != snapshot['source_commit']:
        raise ValueError('Simulator equation fixture provenance mismatch')
    if ({row['kind'] for row in cases['ranged']} !=
            {'pistol', 'shotgun', 'smg', 'assault', 'rifle', 'machinegun'}
            or len(cases['melee']) != 18 or len(cases['critical']) != 24 or not cases['calibrated']):
        raise ValueError('Incomplete simulator equation fixture coverage')
    for case in cases['ranged'] + cases['calibrated']:
        row = dict(type_id=copies.copy_type(case['source'], True), cur_mode=case['mode'])
        params = items.params_of(row['type_id'])
        mode, ammo = case['mode'], case['ammo']
        character = NS(level=case['level'], attr=lambda i: case['attrs'][i])
        weapon = combat.Weapon(params['fire_mods'][mode], params['h_damage_min'][mode],
            params['h_damage_max'][mode], params['opt_range'][mode], params['end_opt_range'][mode],
            params['max_range'][mode], ammo.get('piercing', 1),
            combat.cone_of(combat.spread_factor(case['shooting'], 3), params['target_size'][mode],
                           ammo.get('acc_mod', 1) or 1, params['max_range'][mode]), 0, 1, 0,
            sdmin=(params.get('st_damage_min') or [0]*3)[mode],
            sdmax=(params.get('st_damage_max') or [0]*3)[mode])
        data = dict(snapshot, **case.get('calibration', {}))
        # Mock only the input tables; expected numbers were exported independently.
        with patch.object(engine, 'data', return_value=data):
            engine.weapon_reference.cache_clear()
            try:
                actual = engine.weapon(weapon, character, row, ammo,
                                       Rules(simulator_formulas=True, ammo_modifiers=True))
            finally:
                engine.weapon_reference.cache_clear()
        for key, expected in case['expected'].items():
            if not math.isclose(getattr(actual, key), expected, rel_tol=1e-12, abs_tol=1e-9):
                raise ValueError(('Simulator weapon mismatch', case['source'], case['level'], mode,
                                  key, getattr(actual, key), expected))
        if (actual.max_range != case['reach'] or actual.num_shots != case['shots']
                or params['fire_costs'][mode] != case['ap']
                or params['fire_times'][mode] / 1000 != case['time']):
            raise ValueError(('Simulator weapon timing/mode mismatch', case['source'], mode))
    for case in cases['melee']:
        row = dict(type_id=copies.copy_type(case['source'], True)) if case['source'] is not None else None
        strength = case['attrs'][0]
        bounds = (max(1, int(strength / 2)), max(1, int(strength * 1.5)))
        if row is not None:
            params = items.params_of(row['type_id'])
            bounds = tuple(max(1, params[key] + strength) for key in ('h_damage_min', 'h_damage_max'))
        actual = engine.melee(bounds, NS(level=case['level'], attr=lambda i: case['attrs'][i]), row)
        if list(actual) != case['expected']:
            raise ValueError(('Simulator melee mismatch', case, actual))
    for case in cases['critical']:
        with patch.object(combat, 'roll', side_effect=lambda chance: chance):
            actual = engine.critical(NS(is_player=case['player']), NS(is_player=case['target_player']),
                                     case['chance'], case['optimal'])
        if not math.isclose(actual, case['expected'], abs_tol=1e-9):
            raise ValueError(('Simulator critical mismatch', case, actual))

    fields = ('level', 'hp_max', 'sp_max', 'ap_max', 'armor', 'dodge', 'hit', 'crit_evade',
              'crit', 'spec', 'ranged', 'range', 'shots', 'dmg_min', 'dmg_max', 'attack_ap', 'attack_time')
    for type_id, index in snapshot['mobs'].items():
        mob = NS(type_id=int(type_id), stats=NS())
        engine.configure_mob(mob, NS(rules=Rules(simulator_formulas=True)))
        record = snapshot['mob_records'][index]
        if any(getattr(mob.stats, key) != record[key] for key in fields):
            raise ValueError(('Simulator mob mismatch', type_id))
        if len(mob.training_modes) != len(record['modes']):
            raise ValueError(('Simulator mob modes mismatch', type_id))
        for (weapon, cost, delay), expected in zip(mob.training_modes, record['modes']):
            expected_fields = dict(num_shots=expected['shots'], dmin=expected['dmin'],
                                   dmax=expected['dmax'], max_range=expected['reach'], crit=expected['crit'])
            if any(getattr(weapon, key) != value for key, value in expected_fields.items()) or (
                    cost != expected['ap'] or delay != expected['time']):
                raise ValueError(('Simulator mob mode mismatch', type_id))
        if record['gun'] in copies.COPIES and mob.stats.weapon_type_id != copies.copy_type(record['gun'], True):
            raise ValueError(('Simulator mob weapon mismatch', type_id))
    return dict(ranged=len(cases['ranged']), melee=len(cases['melee']), critical=len(cases['critical']),
                calibrated=len(cases['calibrated']), mobs=len(snapshot['mobs']))
