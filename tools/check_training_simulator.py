"""Compare range tables/equations with a pinned simulator checkout; no battles or RNG."""
import json
import logging
import hashlib
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace as NS

def compare_checkout(checkout):
    source=Path(checkout).resolve()
    repo=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(repo/'server'),str(source)]
    logging.disable(logging.CRITICAL)
    from rulesets.lava_fixed import LavaFixed
    from rulesets.lava import LavaRules
    import combat
    import items
    import inventory
    from training import catalog as range_catalog
    from training.engines import install
    install()
    from training import items as training_items
    from training.engines import simulator_v1 as f
    from training.rules import Rules
    ref=LavaFixed()
    training_items.prepare(range_catalog.item_catalogue())
    raw=f.data(); counts=dict(equipment=0,mobs=0,weapons=0,splits=0)
    revision=subprocess.check_output(['git','-c','safe.directory='+source.as_posix(),'-C',str(source),'rev-parse','HEAD'],text=True).strip()
    assert raw['source_commit']==revision, 'Checkout does not match the pinned snapshot'
    for name,digest in raw['source_hashes'].items():
     assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest,name
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
    print(json.dumps(dict(engine=engine.KEY, source=raw['source_commit'],
                          golden_cases=len(cases), equipment=len(raw['equipment']))))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', nargs='?', help='Pinned source checkout for the full comparison')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    check_snapshot()
    if args.checkout:
        compare_checkout(args.checkout)
