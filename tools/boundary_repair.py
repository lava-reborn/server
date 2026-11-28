"""Explicit, reviewable repair of native resources and their physical outer rim.

Never called by a brush stroke. No game resources, actors or source files are
written here; the result is another editable draft with a change ledger.
"""
from copy import deepcopy
from collections import Counter
import boundary_planner as p
import boundary_manual as m


def exposed_faces(layers,plan,special):
    """Report an ordinary accessible tile abutting depth without a native rim."""
    p.passable(layers,plan,(layers['bounds'][0],layers['bounds'][1]))
    hard=set(plan['_blocked']);assigned=set(map(p.point,plan['placements']))
    protected=set(special)|layers.get('_preserved_land',set())
    front={p.neighbour(c,s) for c in hard for s in p.STEP}-hard-assigned-protected
    result=[]
    for cell in sorted(front):
        if not p.inside(cell,layers['bounds']):continue
        sides=[s for s in p.STEP if p.neighbour(cell,s) in hard]
        result.append(dict(cell=p.cell_key(cell),code='boundary_missing_scene',expected=sides))
    return result


def repair(layers,catalog,special,base,version='native',edits=None,initial=None):
    layers={**layers,**{k:set(layers.get(k,set())) for k in ('water','walls','rocks','coast','patrol','tunnels')},
            'overrides':dict(layers['overrides'])}
    edits=dict(edits if edits is not None else m.scene_edits(base,layers['bounds']))
    initial=initial or m.generate(layers,catalog,special,base,version,edits)
    seed=deepcopy(base);seed['boundary_preview']=deepcopy(initial)
    ledger=[];protected=(set(special)|layers.get('_preserved_land',set()))-layers.get('_retired_existing',set())
    from boundary_tunnels import mountain_entry
    protected-={c for c in layers['tunnels'] if mountain_entry(layers,c,special)}
    bad={r['cell'] for r in initial['issues']}
    # This explicit operation may correct old pins at a conflicting boundary;
    # the normal paint/calculate/save paths still preserve every template pin.
    for key in sorted(bad):
        if p.point(key) not in protected and layers['overrides'].get(key) is not None:
            old=layers['overrides'].pop(key,None)
            if old is not None:ledger.append(dict(cell=key,action='release_conflicting_template',previous=old))

    def mark(cell,kind,reason):
        key=p.cell_key(cell)
        if cell in protected:return False
        field={'water':'water','wall':'walls','rocks':'rocks','coast':'coast'}[kind]
        if cell in layers[field]:return False
        for name in ('water','walls','rocks','coast'):layers[name].discard(cell)
        layers[field].add(cell);layers['overrides'].pop(key,None);edits[key]=kind
        ledger.append(dict(cell=key,action=kind,reason=reason));return True

    # Materialise the second layer of an authored tunnel. It cannot contain a
    # sideways room, even if the source terrain was erased or painted orange.
    for cell in sorted(layers['tunnels']):
        if cell in layers['water']|layers['walls']|layers['coast'] or cell in protected:continue
        for side in 'EW':
            n=p.neighbour(cell,side)
            if p.inside(n,layers['bounds']) and n not in layers['tunnels'] and n not in layers['water']:
                mark(n,'wall','tunnel_side_depth')
        for side in 'NS':
            n=p.neighbour(cell,side)
            if n in layers['rocks'] and n not in protected:
                edits[p.cell_key(n)]='rocks'
                layers['overrides'].pop(p.cell_key(n),None)
                # At the end, keep a native turning room between the straight
                # shaft and a protected place beside its landing. The side of
                # the shaft itself remains depth; only its landing can branch.
                if n not in layers['tunnels']:
                    for across in 'EW':
                        corner=p.neighbour(n,across)
                        if corner in layers['rocks'] and corner not in protected and any(p.neighbour(corner,s) in protected for s in p.STEP):
                            edits[p.cell_key(corner)]='rocks'
                            layers['overrides'].pop(p.cell_key(corner),None)

    plan=m.generate(layers,catalog,special,seed,version,edits,repair=True)
    # Retire an inaccessible extra row into its actual backing, rather than
    # leaving an enterable ordinary scene with its exits suppressed.
    for _ in range(3):
        sealed=False
        generated=set(map(p.point,plan['generated_walls']))
        masks=m.choice_masks(layers,plan['placements'],generated)
        codes_by_cell={}
        for issue in plan['issues']:codes_by_cell.setdefault(issue['cell'],set()).add(issue['code'])
        for key,row in list(plan['placements'].items()):
            cell=p.point(key)
            if cell in protected or cell in layers['tunnels']:continue
            codes=codes_by_cell.get(key,set())
            wanted,_=m.native_context(row['kind'],cell,layers,catalog,plan['placements'],generated,masks)
            unsupported=bool(wanted) and not any(pr.kind==row['kind'] and pr.closed==wanted for pr in catalog.values())
            if 'scene_inside_depth' not in codes and 'no_safe_return' not in codes and not unsupported:continue
            # A source-water shore with no three-sided native template retreats
            # by one cell. Other dead rock rows become real wall depth.
            kind='water' if row['kind']=='coast' and wanted and all(p.neighbour(cell,s) in layers['water'] for s in wanted) else 'wall'
            if mark(cell,kind,'retire_inaccessible_boundary'):
                plan['placements'].pop(key,None);sealed=True
        if not sealed:break
        seed.update(p.document(layers),scene_edits=deepcopy(edits),boundary_preview=plan)
        plan=m.generate(layers,catalog,special,seed,version,edits,repair=True)

    # One face-adjacent row in front of real blocked cells. In particular, no
    # ordinary wilderness tile is used as a substitute for a rock/water face.
    assigned=set(map(p.point,plan['placements']))
    hard=(layers['water']|layers['walls']|layers['rocks']|set(map(p.point,plan['generated_walls']))|set(map(p.point,plan['depth_cells'])))-assigned-protected
    candidates={p.neighbour(c,s) for c in hard for s in p.STEP}
    candidates={c for c in candidates-hard-assigned-protected if p.inside(c,layers['bounds'])}
    extra=[]
    generated=set(map(p.point,plan['generated_walls']))
    masks=m.choice_masks(layers,plan['placements'],generated)
    for cell in sorted(candidates):
        closed=frozenset(s for s in p.STEP if p.neighbour(cell,s) in hard or not p.inside(p.neighbour(cell,s),layers['bounds']))
        wet=frozenset(s for s in p.STEP if p.neighbour(cell,s) in layers['water'])
        kind='coast' if wet else 'rock'
        choices=[i for i,pr in catalog.items() if pr.kind==kind and pr.closed==closed and i not in p.CONNECTORS]
        if not choices:
            if len(closed)==4:
                mark(cell,'water' if wet else 'wall','seal_isolated_hole');continue
            extra.append(dict(cell=p.cell_key(cell),code='boundary_no_native_template',expected=sorted(closed),kind=kind));continue
        key=p.cell_key(cell);old=plan['placements'].get(key)
        neighbours=m.native_context(kind,cell,layers,catalog,plan['placements'],generated,masks)[1]
        ident=min(choices,key=lambda i:m.native_score(i,closed,neighbours,catalog))
        if mark(cell,'coast' if kind=='coast' else 'rocks','physical_front_rim'):
            plan['placements'][key]=dict(kind=kind,template=ident,manual=True,wall_outline=True)
            ledger[-1]['template']=ident
    seed.update(p.document(layers),scene_edits=deepcopy(edits),boundary_preview=plan)
    plan=m.generate(layers,catalog,special,seed,version,edits,repair=True)
    # A new physical rim can reveal an old dry connector pinned against depth.
    # Release only these newly conflicting pins, then fit its real rock/water face.
    for _ in range(2):
        release={r['cell'] for r in plan['issues'] if r['code']=='manual_direction_conflict'
                 and p.point(r['cell']) not in protected and r['cell'] in layers['overrides']}
        if not release:break
        for key in release:layers['overrides'].pop(key,None)
        seed.update(p.document(layers),scene_edits=deepcopy(edits),boundary_preview=plan)
        plan=m.generate(layers,catalog,special,seed,version,edits,repair=True)
    plan['issues'].extend(extra)
    seen={r['cell'] for r in plan['issues']}
    plan['issues'].extend(r for r in exposed_faces(layers,plan,special) if r['cell'] not in seen)
    plan['summary']['unresolved']=len({r['cell'] for r in plan['issues']})
    for key,row in plan['placements'].items():
        old=initial['placements'].get(key)
        if old and old['template']!=row['template']:
            ledger.append(dict(cell=key,action='native_template',previous=old['template'],template=row['template']))
        if not row.get('tunnel') and (not old or old['template']!=row['template'] or base.get('overrides',{}).get(key) is not None):
            # Save uses the ordinary authoritative-pins path, never trusts a
            # browser-supplied plan. Persist the exact native choice explicitly.
            layers['overrides'][key]=row['template']
    plan['input_fingerprint']=p.fingerprint(layers,version)
    plan={k:v for k,v in plan.items() if not k.startswith('_')}
    doc={**deepcopy(base),**p.document(layers), 'scene_edits':edits,'boundary_preview':plan,'physical_boundary_audit':True}
    report=dict(before=initial['summary']['unresolved'],after=plan['summary']['unresolved'],changes=ledger,
                actions=dict(Counter(r['action'] for r in ledger)),remaining=plan['issues'])
    return dict(draft=doc,plan=plan,report=report)
