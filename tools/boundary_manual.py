"""Direct scene editing: keep authored cells and native exits; report conflicts only.

The old outline is a frozen starting point. Saving never runs its solver,
repairs corridors, paints neighbours or removes an incompatible scene.
"""
from copy import deepcopy

def eden_outer_ring(cells):
    cells=set(cells)
    return {c for c in cells if any((c[0]+dx,c[1]+dy) not in cells for dx in (-1,0,1) for dy in (-1,0,1))}

import boundary_planner as p

TYPES={'water','wall','rocks','coast','erase'}


def scene_edits(doc,bounds):
    rows=doc.get('scene_edits',{})
    if not isinstance(rows,dict):raise ValueError('Некорректные ручные изменения')
    result={}
    for key,kind in rows.items():
        cell=p.point(key)
        if not p.inside(cell,bounds) or kind not in TYPES:raise ValueError('Некорректная ручная клетка')
        result[p.cell_key(cell)]=kind
    return result


def choice_masks(layers,placements,generated):
    assigned={p.point(k) for k in placements}
    return {'coast':(layers['water']|layers['walls']|generated)-assigned,'rock':(layers['walls']|layers['water']|layers['rocks']|generated)-assigned}


def native_context(kind,cell,layers,catalog,placements,generated,masks=None,special=None):
    back=(masks if masks is not None else choice_masks(layers,placements,generated))[kind]
    closed=frozenset(side for side in p.STEP if not p.inside(p.neighbour(cell,side),layers['bounds']) or p.neighbour(cell,side) in back)
    neighbours=[]
    for side in p.STEP:
        other=p.neighbour(cell,side);row=placements.get(p.cell_key(other))
        profile=catalog.get(row.get('template')) if row else p.existing_profile(special[other]) if special and other in special else None
        if profile is not None and other not in back:neighbours.append((side,profile))
    return closed,neighbours


def native_score(ident,closed,neighbours,catalog):
    profile=catalog[ident];seams=[p.seam(profile,other,side) for side,other in neighbours]
    return (len(profile.closed^closed),sum(v is None for v in seams),
            len(profile.closed-closed),sum(v for v in seams if v is not None),ident)


def choose(kind,cell,layers,catalog,placements,generated,masks=None,special=None):
    closed,neighbours=native_context(kind,cell,layers,catalog,placements,generated,masks,special)
    candidates=[i for i,pr in catalog.items() if pr.kind==kind and i not in p.CONNECTORS]
    if not candidates:return None
    # An imperfect new assignment is kept and reported, never replaced by a wall.
    from boundary_selection import variant_rank
    return min(candidates,key=lambda ident:(*native_score(ident,closed,neighbours,catalog)[:-1],variant_rank(p.cell_key(cell),ident)))


def generate(layers,catalog,special,base,version='native',edits=None,repair=False):
    edits=scene_edits(base,layers['bounds']) if edits is None else edits
    previous=base.get('boundary_preview',{})
    plan=deepcopy({k:v for k,v in previous.items() if not k.startswith('_')})
    from boundary_tunnels import restore,install
    placements={k:r for k,r in restore(plan.get('placements',{})).items() if r.get('template') in catalog}
    plan['placements']=placements
    generated={p.point(k) for k in plan.get('generated_walls',[])}
    generated|={p.point(k) for k,r in previous.get('placements',{}).items() if r.get('tunnel_generated_wall')}
    before=p.normalise(base,layers['bounds'])
    marked=lambda value:{p.cell_key(c):kind for kind,field in (('water','water'),('wall','walls'),('rocks','rocks'),('coast','coast')) for c in value[field]}
    old_marks,new_marks=marked(before),marked(layers)
    changed={k for k in old_marks.keys()|new_marks.keys() if old_marks.get(k)!=new_marks.get(k)}
    changed|={k for k in before['overrides'].keys()|layers['overrides'].keys() if before['overrides'].get(k,'auto')!=layers['overrides'].get(k,'auto')}
    old_edits=scene_edits(base,layers['bounds'])
    changed|={k for k in old_edits.keys()|edits.keys() if old_edits.get(k)!=edits.get(k)}
    # Existing manual shores and exact template choices also become authoritative.
    authored=changed|edits.keys()|set(map(p.cell_key,layers['coast']))|layers['overrides'].keys()
    suppressed=set()
    for key in sorted(authored):
        cell=p.point(key);kind=edits.get(key,new_marks.get(key))
        override=layers['overrides'].get(key,'auto')
        if key in changed or override!='auto':
            placements.pop(key,None);generated.discard(cell)
        if override is None:
            placements.pop(key,None);suppressed.add(key);continue
        if override!='auto':
            pr=catalog[override];placements[key]=dict(template=override,kind=pr.kind,manual=True);continue
        if kind in ('rocks','coast'):
            placements.setdefault(key,dict(kind='rock' if kind=='rocks' else 'coast',manual=True))
    # Pick newly authored cells; do not rebuild the frozen boundary layout.
    masks=choice_masks(layers,placements,generated)
    for key in sorted(authored):
        row=placements.get(key)
        if row and layers['overrides'].get(key,'auto')=='auto' and (key in changed or 'template' not in row):
            ident=choose(row['kind'],p.point(key),layers,catalog,placements,generated,masks,special)
            if ident is not None:row['template']=ident
    # Fit adjoining native maps jointly. This changes resources only: authored
    # colours, depth marks, pins and existing non-boundary locations stay put.
    from boundary_complexes import annotate
    annotate(placements,layers)
    tunnels,tunnel_issues=install(layers,placements,catalog,special,generated)
    annotate(placements,layers)
    masks=choice_masks(layers,placements,generated)
    from boundary_selection import fit
    plan['template_updates']=fit(placements,layers,catalog,generated,special,
        lambda kind,cell:(frozenset('EW'),native_context(kind,cell,layers,catalog,placements,generated,masks,special)[1])
            if p.cell_key(cell) in tunnels else native_context(kind,cell,layers,catalog,placements,generated,masks,special),repair=repair)
    placements={k:r for k,r in placements.items() if r.get('template') in catalog}
    assigned={p.point(k) for k in placements}
    retired=layers.get('_retired_existing',set())
    preserved={p.point(k) for k in plan.get('preserved_land',[])}-set(map(p.point,changed))-retired
    preserved|=layers.get('_preserved_land',set())-set(map(p.point,authored))-retired
    preserved-=layers.get('_retired_complex_sources',set())
    preserved|={p.point(k) for k in layers.get('_complex_bindings',{})}
    water=layers['water']-assigned
    generated-=assigned|preserved|set(map(p.point,changed))
    plan.update(version=p.VERSION,editing_mode='manual',issues_block_movement=False,
        input_fingerprint=p.fingerprint(layers,version),catalog_version=version,
        approved=False,apply_supported=False,placements=placements,issues=[],tunnels=tunnels,
        generated_walls=sorted(map(p.cell_key,generated)),effective_water=sorted(map(p.cell_key,water)),
        retained_river=sorted(map(p.cell_key,water)),replaced_water=sorted(map(p.cell_key,layers['water']&assigned)),
        preserved_land=sorted(map(p.cell_key,preserved)),cleared_land=sorted(k for k in suppressed if k not in new_marks),
        note='Ручной режим. Назначения сохраняются; замечания не блокируют запись. Автоперестроения границ нет.')
    # Closed native faces define the depth immediately behind the boundary.
    # Keep a conflicting authored scene visible, but do not make it walkable.
    depth={p.neighbour(p.point(key),side) for key,row in placements.items()
           for side in catalog[row['template']].closed
           if p.inside(p.neighbour(p.point(key),side),layers['bounds'])}
    protected=depth&preserved
    depth-=preserved
    # Insetting retires palm resources, not an explicitly assigned new shore.
    # Unassigned retired cells stay closed; native faces can still close a
    # replacement when its actual geometry conflicts with a neighbour.
    depth|=retired-assigned
    plan['depth_cells']=sorted(map(p.cell_key,depth))
    plan['retired_existing']=sorted(map(p.cell_key,retired))
    plan.pop('_blocked',None)
    # Special places retain native geometry unless explicitly replaced in this draft.
    traversal={**layers,'_special':special,'_preserved_land':preserved}
    issues=list(tunnel_issues)
    depth_back={'coast':water|layers['walls']|generated,'rock':water|layers['walls']|generated|(layers['rocks']-assigned)}
    def warn(key,code,**data):issues.append(dict(cell=key,code=code,**data))
    for key,row in placements.items():
        cell=p.point(key);ident=row['template'];pr=catalog[ident]
        row.update(kind=pr.kind,closed=sorted(pr.closed),native_exits=sorted(pr.exits),allowed_exits=[],
            instance_key='boundary:'+key,resource_only=True,manual=key in authored or row.get('manual',False),
            role='mountain_trail' if row.get('mountain_trail') else 'tunnel' if row.get('tunnel') else 'dry_connector' if ident in p.CONNECTORS else 'boundary',wall_outline=row.get('wall_outline',False),
            replaces='water' if cell in layers['water'] else 'rocks' if cell in layers['rocks'] else 'land',
            spawn_policy='none' if layers.get('_regions',{}).get(cell)=='eden' else 'not_configured')
        if cell in depth:warn(key,'scene_inside_depth')
        if key in authored and cell in special and cell not in retired and not row.get('mountain_trail') and not row.get('mountain_portal'):warn(key,'existing_location_overlap',existing=special[cell])
        if not row.get('tunnel') and (key in authored or row.get('manual')):
            back=depth_back[pr.kind]
            wanted={s for s in p.STEP if p.neighbour(cell,s) in back or not p.inside(p.neighbour(cell,s),layers['bounds'])}
            if set(pr.closed)!=wanted:warn(key,'manual_direction_conflict',expected=sorted(wanted),actual=sorted(pr.closed))
            if any(p.inside(p.neighbour(cell,s),layers['bounds']) and p.neighbour(cell,s) not in back for s in pr.closed):warn(key,'missing_depth_backing')
        row['allowed_exits']=[s for s in p.STEP if p.can_step(traversal,plan,cell,p.neighbour(cell,s),catalog)]
        if not row['allowed_exits']:warn(key,'no_safe_return')
        for side in ('E','S'):
            other=p.neighbour(cell,side);other_key=p.cell_key(other)
            if other_key in placements and p.seam(pr,catalog[placements[other_key]['template']],side) is None:
                warn(key,'incompatible_neighbour',neighbour=other_key)
    for key in sorted(authored):
        if key not in placements and p.point(key) in depth and edits.get(key,new_marks.get(key))=='erase':
            warn(key,'manual_depth_conflict')
    for cell in sorted(protected):warn(p.cell_key(cell),'depth_hits_existing',existing=special.get(cell))
    for key in suppressed:
        if key in new_marks and new_marks[key] in ('coast','rocks'):warn(key,'assignment_suppressed')
    if base.get('physical_boundary_audit'):
        from boundary_repair import exposed_faces
        seen={r['cell'] for r in issues}
        issues.extend(r for r in exposed_faces(layers,plan,special) if r['cell'] not in seen)
    plan['issues']=issues
    links=sum(s in row['allowed_exits'] and p.cell_key(p.neighbour(p.point(key),s)) in placements for key,row in placements.items() for s in ('E','S'))
    plan['summary']={**plan.get('summary',{}), 'water':len(water),'source_water':len(layers['water']),
        'replaced_water':len(layers['water']&assigned),'retained_river':len(water),'depth_cells':len(depth),'retired_existing':len(retired),'walls':len(layers['walls']),'rocks':len(layers['rocks']),
        'coast':sum(r['kind']=='coast' for r in placements.values()),'rock_locations':sum(r['kind']=='rock' for r in placements.values()),'tunnels':len(tunnels),
        'unresolved':len({r['cell'] for r in issues}),'added_walls':len(generated),'face_links':links,
        'walkable_face_links':links,'dry_connectors':sum(r['template'] in p.CONNECTORS for r in placements.values()),
        'wall_outline':sum(r.get('wall_outline',False) for r in placements.values()),'protected_repairs':0,'access_corridors':0}
    return plan


def outline_walls(layers,catalog,special,base,version='native',edits=None):
    """Explicit one-cell rim. Never paint source marks, inhabitants or erased cells."""
    edits=dict(edits or {})
    original=generate(layers,catalog,special,base,version,edits)
    walls=layers['walls']|set(map(p.point,original['generated_walls']))|set(map(p.point,original['depth_cells']))
    reserved=layers['water']|layers['walls']|layers['rocks']|layers['coast']|special.keys()|layers.get('_preserved_land',set())
    reserved|=walls|{p.point(k) for k in original['placements']}|{p.point(k) for k in edits}|{p.point(k) for k in layers['overrides']}
    reserved|=layers.get('patrol',set())|layers.get('tunnels',set())
    candidates={(x+dx,y+dy) for x,y in walls for dx in (-1,0,1) for dy in (-1,0,1)}-reserved
    candidates={c for c in candidates if p.inside(c,layers['bounds'])}
    rows=dict(original['placements']);new={**layers,**{field:set(layers[field]) for field in ('water','walls','rocks','coast')},'overrides':dict(layers['overrides'])}
    for c in sorted(candidates):
        kind='coast' if any((c[0]+dx,c[1]+dy) in layers['water'] for dx in (-1,0,1) for dy in (-1,0,1)) else 'rock'
        rows[p.cell_key(c)]={'kind':kind}
    additions={}
    masks=choice_masks(new,rows,walls)
    rim_back={'coast':layers['water'],'rock':walls|layers['water']|layers['rocks']}
    for c in sorted(candidates):
        key=p.cell_key(c);kind=rows[key]['kind']
        back=rim_back[kind]
        dry=not any(p.neighbour(c,side) in back for side in p.STEP)
        connector=30 if kind=='coast' else 51
        ident=connector if dry and connector in catalog else choose(kind,c,new,catalog,rows,walls,masks)
        if ident is None:continue
        new['rocks' if kind=='rock' else 'coast'].add(c);new['overrides'][key]=ident
        edits[key]='rocks' if kind=='rock' else 'coast';additions[key]=dict(kind=kind,template=ident)
    plan=generate(new,catalog,special,base,version,edits)
    return dict(additions=additions,plan={k:v for k,v in plan.items() if not k.startswith('_')})
