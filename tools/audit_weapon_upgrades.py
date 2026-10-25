"""Read-only weapon recipe audit against runtime shops, quests and loot.

No game clients or combat loops. Location reachability is conservative:
map settlements plus configured doors/side/quest ways, excluding retired
places. It validates source data, not passage conditions or a full story.
"""
import collections
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
os.environ.setdefault('LAVA_RES', 'D:/lava-reborn/res')
sys.path.insert(0, str(ROOT / 'server'))
logging.disable(logging.CRITICAL)
import craft  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import world  # noqa: E402


def audit():
    data = ROOT / 'data'
    retired = json.loads((data / 'retired.json').read_text(encoding='utf-8'))
    cut = {int(k) for k in retired['places'] if k.isdigit()}
    passages = json.loads((data / 'passages.json').read_text(encoding='utf-8'))
    reachable = set(world.settlements().values()) - cut
    while True:
        extra = set()
        for section in ('doors', 'sides', 'quest', 'walk_in'):
            for source, records in passages[section].items():
                if not source.isdigit() or int(source) not in reachable:
                    continue
                records = records.values() if isinstance(records, dict) else records
                for record in records:
                    if record.get('confidence', 'high') not in ('high', 'manual'):
                        continue
                    if section == 'quest' and quests.get(record['quest']) is None:
                        continue
                    if record.get('target_loc_id') is not None:
                        extra.add(int(record['target_loc_id']))
        extra -= reachable | cut
        if not extra:
            break
        reachable |= extra

    manager = rooms.Rooms(world.mob_types())
    npcs = collections.defaultdict(set)
    sources = collections.defaultdict(set)
    for loc in sorted(reachable):
        room = manager.get(loc)
        for npc in room.npcs.values():
            npcs[npc.type_id].add(loc)
            if npc.root == world.TRADER:
                for t in items.stock_for(npc.type_id, loc):
                    sources[t].add('shop:%d:%d' % (loc, npc.type_id))
    for npc in npcs:
        for t, chance, _valuable in mobs.loot_table(npc):
            if chance > 0:
                sources[t].add('loot:%d' % npc)
    for q in quests.QUESTS.values():
        if not set(q.give) & npcs.keys() or not set(q.take) & npcs.keys():
            continue
        for t in q.rew_obj:
            sources[t].add('quest:%d' % q.type)
        for t, _n in q.rew_also:
            sources[t].add('quest:%d' % q.type)
        for t, _n in q.start_obj:
            sources[t].add('quest-start:%d' % q.type)
        for t, _n, weight in q.rew_random:
            if weight > 0:
                sources[t].add('quest:%d' % q.type)
    sources[inventory.STARTER_PISTOL].add('starter')
    weapons = {t for t in sources if items.root_of(t) in (items.FIRE_ARM, items.COLD_ARM)
               and not items.out_of_game(t)}
    doc = json.loads((data / 'questgen_weaponcraft.json').read_text(encoding='utf-8'))
    recipes = [r for r in doc['quests'] if r['craft']['family'] in ('upgrade', 'knife')]
    covered = {r['craft']['gun'] for r in recipes}
    missing = []
    for t in sorted(weapons - covered):
        if craft.mod_of(t) or '_mod' in items.catalogue()[t][1]:
            continue
        missing.append(dict(type=t, internal=items.catalogue()[t][1],
                            sources=sorted(sources[t])[:8], wiki=t in items.wiki()))
    missing_effects = []
    for family, entry in json.loads((data / 'firearm_families.json').read_text(encoding='utf-8'))['lines'].items():
        for line in ('A', 'G'):
            gun = entry['members'].get(line)
            if gun not in weapons:
                continue
            effects = {r['craft']['effect'] for r in recipes if r['craft']['gun'] == gun}
            for member, mod in entry['members'].items():
                if (member.startswith(line + ':') and mod in items.wiki()
                        and member.split(':', 1)[1] not in effects):
                    missing_effects.append(dict(gun=gun, mod=mod, effect=member.split(':', 1)[1], family=family))
    report = dict(locations=len(reachable), npc_types=len(npcs), weapons=len(weapons),
                  base_weapons=len(weapons & covered), recipes=len(recipes),
                  missing=missing, missing_effects=missing_effects)
    report['missing_blueprint_sources'] = sorted({r['craft']['blueprint'] for r in recipes
        if r['craft']['blueprint'] not in sources})
    report['unavailable_pairs'] = sorted({(r['craft']['gun'], r['craft']['mod']) for r in recipes
        if not any(x['craft']['gun'] == r['craft']['gun'] and x['craft']['mod'] == r['craft']['mod']
                   and set(x['give']) & npcs.keys() and set(x['take']) & npcs.keys()
                   for x in recipes)})
    report['recipe_structure_errors'] = []
    report['effect_errors'] = []
    for r in recipes:
        c = r['craft']
        want = collections.Counter({c['gun']: 1, c['blueprint']: 1})
        got = collections.Counter({o['obj']: o['num'] for o in r['objs'] if 'obj' in o})
        if got != want or r['rew_obj'] != [c['mod']] or r.get('num_rew_obj', [1]) != [1]:
            report['recipe_structure_errors'].append(r['type'])
        if c['family'] != 'upgrade':
            continue
        a, b = items.params_of(c['gun']), items.params_of(c['mod'])
        modes = [i for i, v in enumerate(a['fire_mods']) if v]
        e = c['effect']
        checks = []
        def increase(field):
            return all(b[field][i] >= a[field][i] for i in modes) and any(b[field][i] > a[field][i] for i in modes)

        def decrease(field):
            return all(b[field][i] <= a[field][i] for i in modes) and any(b[field][i] < a[field][i] for i in modes)

        if 'damage' in e:
            checks.append(increase('h_damage_max') or increase('st_damage_max'))
        if 'precision' in e:
            checks.append(
                all(b['target_size'][i] / b['max_range'][i]
                    <= a['target_size'][i] / a['max_range'][i] for i in modes)
                and any(b['target_size'][i] / b['max_range'][i]
                        < a['target_size'][i] / a['max_range'][i] for i in modes))
        if 'shotrange' in e:
            checks.append(increase('max_range'))
        if e == 'attrition_x2':
            checks.append(a['max_break_abs'] < b['max_break_abs'] <= a['max_break_abs'] * 2.5)
        if 'clipsize' in e:
            checks.append(b['clip_size'] > a['clip_size'])
        if e == 'aimtime':
            checks.append(decrease('fire_times'))
        if e == 'shotspeed':
            checks.append(decrease('fire_costs'))
        if e == 'reloadspeed':
            checks.append(b['reload_cost'] < a['reload_cost'])
        if e == 'weight':
            checks.append(b['weight'] < a['weight'])
        if e in ('agility', 'perception'):
            index = 1 if e == 'agility' else 3

            def bonus(p):
                dense = iter(p.get('bonus_attribs', []))
                values = {i: next(dense) for i in range(5)
                          if p.get('bonus_attribs_m', 0) & (1 << i)}
                return values.get(index, 0)

            checks.append(bonus(b) > bonus(a))
        if checks and not all(checks):
            report['effect_errors'].append(dict(quest=r['type'], gun=c['gun'], mod=c['mod'], effect=e,
                base={k:a[k] for k in ('h_damage_max','target_size','max_range','fire_times','fire_costs','max_break_abs','clip_size','reload_cost','weight')},
                result={k:b[k] for k in ('h_damage_max','target_size','max_range','fire_times','fire_costs','max_break_abs','clip_size','reload_cost','weight')}))
    outputs = {r['craft']['mod'] for r in recipes}
    report['uncovered_base_weapons'] = [x for x in missing if x['type'] not in outputs]
    report.pop('missing')
    report['weapon_types'] = sorted(weapons)
    report['obtainable_blueprints'] = sorted({r['craft']['blueprint'] for r in recipes} & sources.keys())
    report['sources'] = {str(t): sorted(sources[t]) for t in sorted(weapons | {r['craft']['blueprint'] for r in recipes})}
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    report = audit()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k:len(v) if isinstance(v,(list,dict)) else v for k,v in report.items()}))
