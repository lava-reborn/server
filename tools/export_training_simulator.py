"""Freeze an explicitly selected simulator checkout; never run simulated battles.

Usage: python tools/export_training_simulator.py /path/to/simulator
The server reads the generated JSON once, without importing the simulator.
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def encode_snapshot(data):
    """One reviewed record per line, instead of 90,000 pretty-print lines."""
    dump = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ': '), allow_nan=False)
    lines = ['{']
    rows = sorted(data.items())
    for index, (key, value) in enumerate(rows):
        suffix = ',' if index < len(rows) - 1 else ''
        prefix = '  ' + dump(key) + ': '
        if isinstance(value, dict) and value:
            entries = sorted(value.items())
            lines.append(prefix + '{')
            lines.extend('    ' + dump(name) + ': ' + dump(record) + (',' if n < len(entries) - 1 else '')
                         for n, (name, record) in enumerate(entries))
            lines.append('  }' + suffix)
        elif isinstance(value, list) and value:
            lines.append(prefix + '[')
            lines.extend('    ' + dump(record) + (',' if n < len(value) - 1 else '')
                         for n, record in enumerate(value))
            lines.append('  ]' + suffix)
        else:
            lines.append(prefix + dump(value) + suffix)
    return '\n'.join(lines + ['}']) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    source = args.checkout.resolve()
    revision = subprocess.check_output(['git', '-c', 'safe.directory=' + source.as_posix(),
                                        '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', '-c', 'safe.directory=' + source.as_posix(),
                                '-C', str(source), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Export requires a clean, explicitly pinned simulator checkout')
    repo = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo / 'server'), str(source)]
    logging.disable(logging.CRITICAL)
    from rulesets.lava_fixed import LavaFixed, GUN_NAMES, GUN_OF_MOB
    from rulesets import lava_fixed
    from rulesets.lava import LavaRules
    import items
    from training import legacy as training_legacy
    from training import ammo as training_ammo
    from training import catalog as range_catalog
    from training import content
    reference, original = LavaFixed(), LavaRules()
    path = args.output or repo / 'data/training_simulator_formulas.json'
    data = dict(version=1, engine='simulator-v1', source='https://github.com/lava-reborn/simulator',
                source_commit=revision, scope='Simulator fixed profile: equations, A/G equipment, sets and mobs',
                source_hashes={name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                               for name in ('rulesets/lava.py', 'rulesets/lava_fixed.py',
                                            'data/lava/snapshot.json', 'data/lava/fixed_rules.json')},
                equations={name: getattr(lava_fixed, name) for name in
                           ('INT_DAMAGE', 'INT_HEAL', 'INT_COOLDOWN', 'COOLDOWN_FLOOR',
                            'ARMOR_SHARE_CAP', 'ARMOR_GAP', 'MOB_CRIT_FLOOR',
                            'LEVEL_SPREAD', 'LEVEL_DAMAGE')},
                weapon_scale={str(k): v for k, v in reference.weapon_scale.items()},
                class_scale={c: {str(k): v for k, v in rows.items()} for c, rows in reference.class_scale.items()},
                armour_reference={str(i): reference.own_armor(i) for i in range(1, 21)},
                gap_table={str(k): {str(g): v for g, v in row.items()} for k, row in reference.gap_table.items()},
                rule_changes=reference.rule_changes())
    records, shared, by_type = [], {}, {}
    for type_id in sorted(range_catalog.mob_catalogue()):
        fighter = reference.build(dict(kind='mob', id=type_id))
        mob = fighter.x['mob']
        cls = GUN_OF_MOB.get(mob['weapon_class'], mob['weapon_class'])
        gun = LavaRules.best_weapon(reference, cls, max(1, min(20, mob['level'])), 5) if cls in GUN_NAMES else None
        gun = reference.new_guns.get(gun, gun)
        record = dict(level=mob['level'], hp_max=fighter.maxima['hp'], sp_max=fighter.maxima['sp'],
            ap_max=fighter.ap_max, armor=fighter.x['armor'], dodge=mob['dodge'], hit=mob['hit'],
            crit_evade=fighter.x['crit_evade'], crit=fighter.attack.data['crit'], spec=mob['spec'],
            ranged=mob['ranged'], range=fighter.attack.reach, shots=fighter.attack.projectiles,
            dmg_min=fighter.attack.data['dmin'], dmg_max=fighter.attack.data['dmax'],
            attack_ap=fighter.attack.ap, attack_time=fighter.attack.windup, gun=gun, weapon_class=cls,
            modes=[dict(shots=a.projectiles, ap=a.ap, time=a.windup, reach=a.reach, **a.data)
                   for a in fighter.x.get('modes', (fighter.attack,))])
        key = json.dumps(record, sort_keys=True)
        if key not in shared:
            shared[key] = len(records)
            records.append(record)
        by_type[str(type_id)] = shared[key]
    data.update(mob_records=records, mobs=by_type)
    extra = set()
    for level in range(1, 21):
        for cls in GUN_NAMES:
            for spec in (0, 3, 5):
                gun = reference.best_weapon(cls, level, spec)
                gun = reference.new_guns.get(gun, gun)
                if gun:
                    extra.add(gun)
                    extra.update(reference.weapons[gun]['comp_array'])
        found = reference.best_set(level)
        if found:
            extra.update(reference.sets[found]['members'].values())
    # Keep retired sources in the reviewed content/ID registry, not by reading
    # the last generated snapshot. A fresh export must be reproducible.
    data['extra_sources'] = sorted(set(content.data()['simulator_sources']) |
                                   (extra - set(range_catalog.item_catalogue())))
    data['experimental_guns'] = {str(k): dict(base=v, name=reference.weapons[k]['name'],
        level=reference.need(reference.weapons[k]), data=reference.weapons[k]) for k, v in reference.new_guns.items()}
    available = set(range_catalog.item_catalogue()) | set(data['extra_sources'])
    data['preserved_sources'] = sorted(training_legacy.CLASSIC | {training_ammo.ROCKET, training_ammo.CROSSBOW})
    available -= set(data['preserved_sources'])
    damage = ('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max')
    data['weapon_bases'] = {str(t): {k: row[k] for k in damage if k in row}
                          for t, row in reference.weapons.items() if t in available and not items.premium(t)}
    data['melee_bases'] = {str(t): {k: row[k] for k in damage if k in row}
                         for t, row in reference.melee.items() if t in available and not items.premium(t)}
    data['equipment'] = {}
    weapon_fields = set(damage) | {'fire_costs', 'fire_times', 'fire_mods', 'max_range',
        'opt_range', 'end_opt_range', 'target_size', 'clip_size', 'reload_cost', 'reload_time',
        'strike_cost', 'strike_time', 'piercing', 'need_skills_m', 'need_skills', 'need_specs_m', 'need_specs'}
    for table in (reference.weapons, reference.melee, reference.wear):
        for t, row in table.items():
            if t >= 65536 or t not in available or t not in items.catalogue() or items.premium(t):
                continue  # P placeholders have no valid simulator counterpart.
            fields = {key: value for key, value in row.items() if key.startswith('bonus_') or key in weapon_fields}
            if 'armor' in row:
                fields['armor_class'] = row['armor']
            data['equipment'][str(t)] = fields
    data['sets'] = {str(t): row['bonus'] for t, row in reference.sets.items()}
    removed = {piece for t in reference.removed_sets for piece in original.sets[t]['members'].values()}
    data['disabled_sources'] = sorted(removed | reference.withdrawn)
    # Independent golden outputs: CI can verify the port without credentials
    # to the private simulator repository and without running simulated fights.
    cases = []
    for level in (1, 12, 20):
        for gap in (0, 1, 3):
            for kind in ('rifle', 'assault'):
                for critical in (False, True):
                    for left in (0, 70, 1000):
                        attacker = SimpleNamespace(x={'player': True}, card={'level': level, 'weapon': {'cls': kind}})
                        defender = SimpleNamespace(x={'player': False, 'mob': {'level': level + gap},
                                                      'armor': reference.own_armor(level + gap)},
                                                   card={'level': level + gap}, pools={'sp': left})
                        attack = SimpleNamespace(kind='ranged', data={'piercing': 1.5})
                        expected = reference.mitigate(attacker, attack, defender, (123, 11), critical)
                        cases.append([level, gap, kind, critical, left, expected.damage['hp'], expected.damage['sp']])
    data['parity_cases'] = cases
    if 'training.session' in sys.modules or 'server' in sys.modules:
        raise RuntimeError('Snapshot export imported the game session')
    encoded = encode_snapshot(data)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(path)
    print('Frozen', revision, len(by_type), 'mobs,', len(data['equipment']), 'equipment records')


if __name__ == '__main__':
    main()
