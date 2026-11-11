"""Compare range tables/equations with a pinned simulator checkout; no battles or RNG."""
import copy
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace as NS

source=Path(sys.argv[1]).resolve()
repo=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(repo/'server'),str(source)]
logging.disable(logging.CRITICAL)
from rulesets.lava_fixed import LavaFixed
from rulesets.lava import LavaRules,SPEC_OF_CLASS
import combat
import items
import inventory
from training import catalog as range_catalog
from training import session as training_ground
from training import items as training_items
from training import formulas as f
from training.rules import Rules
ref=LavaFixed()
training_items.prepare(range_catalog.item_catalogue())
raw=f.data(); counts=dict(equipment=0,mobs=0,weapons=0,splits=0)
assert raw['source_commit']=='6b7b28dc7b40fb57078453d536837b0edcc0059f'
for tid,fields in raw['equipment'].items():
 t=int(tid); row=(ref.weapons.get(t) or ref.melee.get(t) or ref.wear.get(t))
 for key,value in fields.items():
  assert value==row['armor' if key=='armor_class' else key],(t,key)
 si=items.params_of(training_items.copy_type(t,simulator=True))
 for key,value in fields.items():
  assert si.get(key)==value,(t,key,si.get(key),value)
 counts['equipment']+=1
for tid,idx in raw['mobs'].items():
 a=ref.build(dict(kind='mob',id=int(tid))); record=raw['mob_records'][idx]
 assert record['armor']==a.x['armor'],tid
 assert record['crit_evade']==a.x['crit_evade'],tid
 assert record['hp_max']==a.maxima['hp'],tid
 assert record['sp_max']==a.maxima['sp'],tid
 assert record['modes']==[dict(shots=m.projectiles,ap=m.ap,time=m.windup,reach=m.reach,**m.data) for m in a.x.get('modes',(a.attack,))],tid
 counts['mobs']+=1
for lv in range(1,21):
 assert f.reference_armour(lv)==ref.own_armor(lv)
 for gap in (0,1,2,3,4,6):
  for cls in ('rifle','assault'):
   for crit in (False,True):
    for left in (0,70,1000):
     a=NS(x={'player':True},card={'level':lv,'weapon':{'cls':cls}})
     d=NS(x={'player':False,'mob':{'level':lv+gap},'armor':ref.own_armor(lv+gap)},card={'level':lv+gap},pools={'sp':left})
     expected=ref.mitigate(a,NS(kind='ranged',data={'piercing':1.5}),d,(123,11),crit)
     sa=NS(is_player=True,character=lambda:NS(level=lv))
     sd=NS(is_player=False,stats=NS(level=lv+gap),armor=lambda:d.x['armor'])
     actual=f.split(sa,sd,123,1.5,crit,left,11,rifle=cls=='rifle')
     assert actual==(expected.damage['hp'],expected.damage['sp']),(lv,gap,cls,crit,left,actual,expected)
     counts['splits']+=1
# Compare all active modes of exported A/G guns and prototypes, using the actual
# range copy's requirements, timing, damage and spread at its level and below it.
weapons={int(k):int(k) for k in raw['weapon_bases'] if int(k) not in ref.withdrawn}
weapons.update({t:rec['simulator_id'] for t,rec in training_items.PROTOTYPES.items()})
fixtures=[]
for source_id,sim_id in weapons.items():
 row=ref.weapons[sim_id]
 for lv in sorted({20,max(1,min(20,ref.need(row)-2))}):
  for mode,shots in enumerate(row['fire_mods']):
   if not shots:continue
   ammo_id=next((i for i in row['comp_array'] if i in ref.ammo),None)
   spec=dict(skills={'shooting':lv},specs={row['class']:3},weapon=sim_id,mode=mode,ammo=ammo_id)
   expected=ref.build(spec)
   char=NS(level=lv,attr=lambda i:expected.x['attrs'][i])
   target=training_items.copy_type(source_id,simulator=True)
   si=items.params_of(target); ammo=ref.ammo.get(ammo_id,{})
   spread=combat.spread_factor(lv,3)
   base=combat.Weapon(shots,si['h_damage_min'][mode],si['h_damage_max'][mode],si['opt_range'][mode],si['end_opt_range'][mode],si['max_range'][mode],ammo.get('piercing',1),combat.cone_of(spread,si['target_size'][mode],ammo.get('acc_mod',1) or 1,si['max_range'][mode]),0,1,0,sdmin=(si.get('st_damage_min') or [0]*3)[mode],sdmax=(si.get('st_damage_max') or [0]*3)[mode])
   actual=f.weapon(base,char,dict(type_id=target,cur_mode=mode),ammo,Rules(simulator_formulas=True,ammo_modifiers=True))
   for key in ('dmin','dmax','sdmin','sdmax','cone','opt_lo','opt_hi'):
    assert abs(getattr(actual,key)-expected.attack.data[key])<1e-9,(source_id,sim_id,lv,mode,key,getattr(actual,key),expected.attack.data[key])
   assert actual.max_range==expected.attack.reach
   assert si['fire_costs'][mode]==expected.attack.ap
   counts['weapons']+=1
print(json.dumps(counts))
print('armour',[ref.own_armor(lv) for lv in (1,4,5,6,7,12,17,20)])
print('coefficients',ref.weapon_scale.get(25056,1),ref.weapon_scale.get(26075,1))
for tid in (6231,6241):
 a=ref.build(dict(skills={'shooting':20},weapon=tid))
 print('blade',tid,a.attack.data)
print('prototypes',len(ref.new_guns))
