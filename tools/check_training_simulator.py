"""Compare range tables/equations with a pinned simulator checkout; no battles or RNG."""
import json
import logging
import hashlib
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace as NS

def compare_checkout(checkout):
    source = Path(checkout).resolve()
    repo = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo / 'server'), str(source)]
    logging.disable(logging.CRITICAL)
    from rulesets.lava_fixed import LavaFixed
    from rulesets.lava import LavaRules
    import combat
    import items
    from training import catalog as range_catalog
    from training.engines import install
    from training import items as training_items
    from training.engines import simulator_v1 as engine
    from training.rules import Rules
    from training_simulator_parity import reference_cases

    install()
    reference = LavaFixed()
    training_items.prepare(range_catalog.item_catalogue())
    raw = engine.data()
    counts = dict(equipment=0, mobs=0, weapons=0, splits=0)
    revision = subprocess.check_output(
        ['git', '-c', 'safe.directory=' + source.as_posix(), '-C', str(source), 'rev-parse', 'HEAD'],
        text=True).strip()
    assert raw['source_commit'] == revision, 'Checkout does not match the pinned snapshot'
    for name, digest in raw['source_hashes'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
    fixture = json.loads((repo / 'data/training_simulator_cases.json').read_text(encoding='utf-8'))
    assert reference_cases(reference, raw) == fixture, 'Equation fixtures differ from the pinned simulator'
    for tid, fields in raw['equipment'].items():
        type_id = int(tid)
        row = (reference.weapons.get(type_id) or reference.melee.get(type_id) or reference.wear.get(type_id))
        for key, value in fields.items():
            assert value == row['armor' if key == 'armor_class' else key], (type_id, key)
        params = items.params_of(training_items.copy_type(type_id, simulator=True))
        for key, value in fields.items():
            assert params.get(key) == value, (type_id, key, params.get(key), value)
        counts['equipment'] += 1
    for tid, index in raw['mobs'].items():
        actor = reference.build(dict(kind='mob', id=int(tid)))
        record = raw['mob_records'][index]
        assert record['armor'] == actor.x['armor'], tid
        assert record['crit_evade'] == actor.x['crit_evade'], tid
        assert record['hp_max'] == actor.maxima['hp'], tid
        assert record['sp_max'] == actor.maxima['sp'], tid
        assert record['modes'] == [dict(shots=mode.projectiles, ap=mode.ap, time=mode.windup,
                                       reach=mode.reach, **mode.data)
                                   for mode in actor.x.get('modes', (actor.attack,))], tid
        counts['mobs'] += 1
    for level in range(1, 21):
        assert engine.reference_armour(level) == reference.own_armor(level)
        for gap in (0, 1, 2, 3, 4, 6):
            for kind in ('rifle', 'assault'):
                for critical in (False, True):
                    for left in (0, 70, 1000):
                        attacker = NS(x={'player': True}, card={'level': level, 'weapon': {'cls': kind}})
                        defender = NS(x={'player': False, 'mob': {'level': level + gap},
                                         'armor': reference.own_armor(level + gap)},
                                      card={'level': level + gap}, pools={'sp': left})
                        expected = reference.mitigate(
                            attacker, NS(kind='ranged', data={'piercing': 1.5}), defender, (123, 11), critical)
                        shooter = NS(is_player=True, character=lambda: NS(level=level))
                        target = NS(is_player=False, stats=NS(level=level + gap), armor=lambda: defender.x['armor'])
                        actual = engine.split(shooter, target, 123, 1.5, critical, left, 11, rifle=kind == 'rifle')
                        assert actual == (expected.damage['hp'], expected.damage['sp']), (level, gap, kind, critical, left)
                        counts['splits'] += 1
    # All active A/G modes and prototypes, at their level and below it.
    weapons = {int(key): int(key) for key in raw['weapon_bases'] if int(key) not in reference.withdrawn}
    weapons.update({key: record['simulator_id'] for key, record in training_items.PROTOTYPES.items()})
    for source_id, simulator_id in weapons.items():
        row = reference.weapons[simulator_id]
        for level in sorted({20, max(1, min(20, reference.need(row) - 2))}):
            for mode, shots in enumerate(row['fire_mods']):
                if not shots:
                    continue
                ammo_id = next((key for key in row['comp_array'] if key in reference.ammo), None)
                spec = dict(skills={'shooting': level}, specs={row['class']: 3},
                            weapon=simulator_id, mode=mode, ammo=ammo_id)
                expected = reference.build(spec)
                character = NS(level=level, attr=lambda index: expected.x['attrs'][index])
                target_type = training_items.copy_type(source_id, simulator=True)
                params, ammo = items.params_of(target_type), reference.ammo.get(ammo_id, {})
                spread = combat.spread_factor(level, 3)
                weapon = combat.Weapon(shots, params['h_damage_min'][mode], params['h_damage_max'][mode],
                    params['opt_range'][mode], params['end_opt_range'][mode], params['max_range'][mode],
                    ammo.get('piercing', 1), combat.cone_of(spread, params['target_size'][mode],
                    ammo.get('acc_mod', 1) or 1, params['max_range'][mode]), 0, 1, 0,
                    sdmin=(params.get('st_damage_min') or [0]*3)[mode],
                    sdmax=(params.get('st_damage_max') or [0]*3)[mode])
                actual = engine.weapon(weapon, character, dict(type_id=target_type, cur_mode=mode), ammo,
                                       Rules(simulator_formulas=True, ammo_modifiers=True))
                for key in ('dmin', 'dmax', 'sdmin', 'sdmax', 'cone', 'opt_lo', 'opt_hi'):
                    assert abs(getattr(actual, key) - expected.attack.data[key]) < 1e-9, (source_id, level, mode, key)
                assert actual.max_range == expected.attack.reach
                assert params['fire_costs'][mode] == expected.attack.ap
                counts['weapons'] += 1
    print(json.dumps(counts))


def check_snapshot():
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / 'server'))
    from training.engines import install
    install()
    from training import catalog, items as copies
    from training.engines import simulator_v1 as engine
    copies.prepare(catalog.item_catalogue())
    raw = engine.data()
    cases = raw['parity_cases']
    expected_inputs = {(level, gap, kind, critical, left)
                       for level in (1, 12, 20) for gap in (0, 1, 3)
                       for kind in ('rifle', 'assault') for critical in (False, True)
                       for left in (0, 70, 1000)}
    if len(cases) != len(expected_inputs) or {tuple(row[:5]) for row in cases} != expected_inputs:
        raise ValueError('Incomplete simulator golden-case coverage')
    for level, gap, kind, critical, left, hp, sp in cases:
        shooter = NS(is_player=True, character=lambda: NS(level=level))
        target = NS(is_player=False, stats=NS(level=level + gap),
                    armor=lambda: engine.reference_armour(level + gap))
        actual = engine.split(shooter, target, 123, 1.5, critical, left, 11, rifle=kind == 'rifle')
        if actual != (hp, sp):
            raise ValueError(('Simulator golden case mismatch', level, gap, kind, critical, left, actual, (hp, sp)))
    import items
    for source, fields in raw['equipment'].items():
        if not copies.available(int(source), True):
            continue
        params = items.params_of(copies.copy_type(int(source), True))
        if any(params.get(key) != value for key, value in fields.items()):
            raise ValueError('Simulator equipment mismatch: ' + source)
    from training_simulator_parity import check_cases
    cases_path = repo / 'data/training_simulator_cases.json'
    equations = check_cases(json.loads(cases_path.read_text(encoding='utf-8')), engine, raw)
    print(json.dumps(dict(engine=engine.KEY, source=raw['source_commit'],
                          golden_cases=len(cases), equipment=len(raw['equipment']), equations=equations)))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', nargs='?', help='Pinned source checkout for the full comparison')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    check_snapshot()
    if args.checkout:
        compare_checkout(args.checkout)
