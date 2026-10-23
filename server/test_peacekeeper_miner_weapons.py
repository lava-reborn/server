"""Peacekeeper miners use level-appropriate rifles and scoped AP pools, not shop damage."""
import ast
import os
import random
from pathlib import Path
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
import mobs
import items
from testkit import check, fails

# --- generator, effective stats and the weapon sent to the client ---
source = Path(__file__).resolve().parents[1] / 'data/build_mob_types.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'DESIGNED_KINDS' for t in n.targets))
designed = ast.literal_eval(node.value)
for t, level, ap, weapon in ((840, 16, 110, 25265), (841, 17, 115, 25303)):
    st = mobs.stats(t)
    check('%d: level retained and automatic weapon profile applied' % t,
          (st.level, st.weapon_class, st.weapon_type_id, st.ranged,
           st.ap_max, st.attack_ap, st.shots, st.range),
          (level, 'assault_rifle', weapon, True, ap, 10, 2, 7))
    expected = designed['pc_miner_lvl%d' % level]
    check('%d: generated data matches generator overrides' % t,
          {k: mobs.TYPES[str(t)][k] for k in expected}, expected)
    si = items.params_of(weapon)
    check('%d: aim time and scatter match the held rifle' % t,
          (st.attack_time, st.scatter),
          (si['fire_times'][0] / 1000, si['target_size'][0] / si['max_range'][0]))
    check('%d: damage still comes from mob curve' % t,
          (st.dmg_min, st.dmg_max),
          tuple(int(round(mobs.LEVELS[str(level)][k] * 0.9 * mobs.ROLES[st.role]['dmg_mult']))
                for k in ('dmg_min', 'dmg_max')))
    check('%d: virtual weapon loaded with compatible ammo' % t,
          mobs.virtual_di(mobs.VIRTUAL_BASE + 1, weapon, items.FIRE_ARM)[1]['ammo_type'],
          si['comp_array'][0])
# --- premium afro ammunition for miners; neutral ammunition for elite ---
for t, ammo, standard in ((840, 6121, 6109), (841, 6124, 6112)):
    st = mobs.stats(t)
    bullet = items.params_of(ammo)
    check('%d: improved ammo compatible with held rifle' % t,
          ammo in items.params_of(st.weapon_type_id)['comp_array'], True)
    check('%d: ammo costs more afro than standard, never gold' % t,
          (bullet['cost'] > items.params_of(standard)['cost'], bullet['g_cost']), (True, 0))
    check('%d: improved accuracy and range' % t,
          (bullet['acc_mod'] < 1, bullet['range_mod'] > 1), (True, True))
    for seed in range(30):
        drops = mobs.carried(st, random.Random(seed))
        check('%d: actual drop keeps 2-6 improved rounds' % t,
              (drops[0][0], 2 <= drops[0][1] <= 6), (ammo, True))
elite = mobs.stats(406)
standard = items.params_of(6110)
check('elite ammunition is compatible and neutral',
      (6110 in items.params_of(elite.weapon_type_id)['comp_array'],
       [standard[k] for k in ('acc_mod', 'dam_mod', 'st_mod', 'range_mod', 'piercing')]),
      (True, [1.0] * 5))
check('elite override survives generator rebuild',
      designed['pc_shturmovik_lvl16'], {'loot_ammo_type': 6110})
for seed in range(30):
    drops = mobs.carried(elite, random.Random(seed))
    check('elite drops 3-10 standard rounds',
          (drops[0][0], 3 <= drops[0][1] <= 10), (6110, True))

# --- no changes to Magrib miners or global curves ---
for t in (838, 839):
    check('%d: Magrib retains its existing weapon profile' % t,
          mobs.stats(t).weapon_class, 'smg')
check('global level-16/17 AP curves retained',
      [mobs.LEVELS[str(l)]['ap'] for l in (16, 17)], [130, 135])
for weapon in (25265, 25303):
    check('%d: weapon remains afro-only' % weapon,
          (items.params_of(weapon)['cost'] > 0, items.params_of(weapon)['g_cost']), (True, 0))
for t, chance in ((840, 0.05), (841, 0.05)):
    check('%d: individual gold-case drop chance' % t,
          [(c, v) for obj, c, v in mobs.loot_table(t) if obj == 6953], [(chance, True)])
if fails:
    for failure in fails: print(failure)
    raise SystemExit(1)
print('Peacekeeper miner weapons OK')
