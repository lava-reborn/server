"""Peacekeeper miners use level-appropriate rifles and scoped AP pools, not shop damage."""
import ast
import os
import random
from pathlib import Path
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
import mobs
import items
import battle_balance
from testkit import check, fails

# --- generator, effective stats and the weapon sent to the client ---
source = Path(__file__).resolve().parents[1] / 'data/build_mob_types.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'DESIGNED_KINDS' for t in n.targets))
designed = ast.literal_eval(node.value)
for t, level, ap, weapon in ((840, 16, 110, 25303), (841, 17, 115, 25319)):
    st = mobs.stats(t)
    check('%d: level retained and automatic weapon profile applied' % t,
          (st.level, st.weapon_class, st.weapon_type_id, st.ranged,
           st.ap_max, st.attack_ap, st.shots, st.range),
          (level, 'assault', weapon, True, ap, 10, 2, 30))
    expected = designed['pc_miner_lvl%d' % level]
    check('%d: generated data matches generator overrides' % t,
          {k: mobs.TYPES[str(t)][k] for k in expected}, expected)
    si = items.params_of(weapon)
    profile = battle_balance.data()['mob_records'][battle_balance.data()['mobs'][str(t)]]
    check('%d: simulator modes retain aim time and spread' % t,
          (st.attack_time, st.balanced_modes[0]['cone']),
          (profile['attack_time'], profile['modes'][0]['cone']))
    check('%d: damage follows the common ordinary-mob release ladder' % t,
          (st.dmg_min, st.dmg_max),
          (81, 123) if t == 840 else (81, 124))
    check('%d: virtual weapon loaded with compatible ammo' % t,
          mobs.virtual_di(mobs.VIRTUAL_BASE + 1, weapon, items.FIRE_ARM)[1]['ammo_type'],
          si['comp_array'][0])
# --- premium afro ammunition for miners; neutral ammunition for elite ---
for t, ammo, standard in ((840, 6124, 6112), (841, 6121, 6109)):
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
standard = items.params_of(6112)
check('elite ammunition is compatible and neutral',
      (6112 in items.params_of(elite.weapon_type_id)['comp_array'],
       [standard[k] for k in ('acc_mod', 'dam_mod', 'st_mod', 'range_mod', 'piercing')]),
      (True, [1.0] * 5))
check('elite override survives generator rebuild',
      designed['pc_shturmovik_lvl16'], {'loot_ammo_type': 6110})
for seed in range(30):
    drops = mobs.carried(elite, random.Random(seed))
    check('elite drops 3-10 standard rounds',
          (drops[0][0], 3 <= drops[0][1] <= 10), (6112, True))

# --- no changes to Magrib miners or global curves ---
for t in (838, 839):
    check('%d: Magrib retains its existing weapon profile' % t,
          mobs.stats(t).weapon_class, 'smg')
check('global level-16/17 AP curves retained',
      [mobs.LEVELS[str(l)]['ap'] for l in (16, 17)], [130, 135])
for weapon in (25265, 25303):
    check('%d: weapon remains afro-only' % weapon,
          (items.params_of(weapon)['cost'] > 0, items.params_of(weapon)['g_cost']), (True, 0))
for t, chance in ((840, 0.018686), (841, 0.020981)):
    check('%d: individual gold-case drop chance' % t,
          [(c, v) for obj, c, v in mobs.loot_table(t) if obj == 6953], [(chance, True)])
if fails:
    for failure in fails: print(failure)
    raise SystemExit(1)
print('Peacekeeper miner weapons OK')
