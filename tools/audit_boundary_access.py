"""Compare old reachable named places with the exact saved draft graph."""
import argparse,collections,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
os.environ['LAVA_BOUNDARY_WORLD']='off'
import world,boundary_planner as p
from boundary_policy import native_policy
from boundary_complexes import project

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--draft',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    doc=json.loads(args.draft.read_bytes());plan=doc['boundary_preview'];bounds=world.MAP_X[0],world.MAP_Y[0],world.MAP_X[1],world.MAP_Y[1]
    layers=p.normalise(doc,bounds);policy=native_policy();policy.attach(layers);layers['_special']=dict(policy.special)
    if doc.get('eden_inset'):
        layers['_retired_existing']=set(map(p.point,plan['retired_existing']));layers['_preserved_land']-=layers['_retired_existing']
    project(layers,layers['_special']);catalog,_=p.native_catalog()
    old_free={(x,y) for x in range(bounds[0],bounds[2]+1) for y in range(bounds[1],bounds[3]+1) if world.passable(x,y)}
    special=policy.special
    def old_step(a,b):
        if a not in old_free or b not in old_free:return False
        side=next(s for s in p.STEP if p.neighbour(a,s)==b)
        ap=p.existing_profile(special[a]) if a in special else None;bp=p.existing_profile(special[b]) if b in special else None
        if ap and not ap.edges.get(side) or bp and not bp.edges.get(p.OPPOSITE[side]):return False
        return ap is None or bp is None or p.seam(ap,bp,side) is not None
    def components(step,opened):
        labels={};sizes=[]
        for seed in sorted(policy.named):
            if seed in labels or not opened(seed):continue
            number=len(sizes);labels[seed]=number;pending=[seed];size=0
            while pending:
                cell=pending.pop();size+=1
                for side in p.STEP:
                    n=p.neighbour(cell,side)
                    if n not in labels and step(cell,n):labels[n]=number;pending.append(n)
            sizes.append(size)
        return labels,sizes
    old,old_sizes=components(old_step,lambda c:c in old_free);print('Baseline named places checked',flush=True)
    new,new_sizes=components(lambda a,b:p.can_step(layers,plan,a,b,catalog),lambda c:p.passable(layers,plan,c))
    regressions=[];pairs=collections.defaultdict(set);rows=[]
    for c,ident in policy.named.items():
        if c not in old_free:continue
        old_exits=[s for s in p.STEP if old_step(c,p.neighbour(c,s))]
        new_exits=[s for s in p.STEP if p.can_step(layers,plan,c,p.neighbour(c,s),catalog)]
        if not p.passable(layers,plan,c) or old_exits and not new_exits:regressions.append((p.cell_key(c),ident,'approach_lost'))
        if c in old and c in new:pairs[old[c]].add(new[c])
        elif c in old:regressions.append((p.cell_key(c),ident,'unreachable'))
        if layers['_special'].get(c)!=ident:regressions.append((p.cell_key(c),ident,'identity_changed'))
        rows.append(dict(cell=p.cell_key(c),id=ident,before=old_exits,after=new_exits))
    for number,parts in pairs.items():
        if len(parts)>1:regressions.append(('component',number,'split',sorted(parts)))
    report=dict(previously_accessible=len(rows),regressions=regressions,old_component_sizes=old_sizes,new_component_sizes=new_sizes,rows=rows)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(previously_accessible=len(rows),regressions=regressions),ensure_ascii=False),flush=True)
    if regressions:raise SystemExit(1)

if __name__=='__main__':main()
