"""Draft boundary completion with native dry corner resources, without spawns."""
from collections import deque
import boundary_planner as p


def profile_for(kind,cell,water,blocked,catalog):
    back=water if kind=='coast' else blocked
    closed=frozenset(s for s in p.STEP if p.neighbour(cell,s) in back)
    if not closed:return 30 if kind=='coast' else 51
    choices=[i for i,pr in catalog.items() if pr.kind==kind and pr.closed==closed]
    return min(choices) if choices else None


def linked(a,b,side,catalog):
    return bool(catalog[a].edges.get(side) and catalog[b].edges.get(p.OPPOSITE[side])
                and p.seam(catalog[a],catalog[b],side) is not None)


def groups(assigned,catalog,regions):
    labels={};result=[]
    for seed in sorted(assigned):
        if seed in labels:continue
        number=len(result);group={seed};labels[seed]=number;queue=[seed]
        while queue:
            cell=queue.pop()
            for side in p.STEP:
                n=p.neighbour(cell,side)
                if n in assigned and n not in labels and regions.get(n)==regions.get(cell) and linked(assigned[cell],assigned[n],side,catalog):
                    labels[n]=number;group.add(n);queue.append(n)
        result.append(group)
    return labels,result


def complete(layers,legacy,catalog,special):
    if 30 not in catalog or 51 not in catalog:return legacy
    raw=layers['water'];rocks=layers['rocks'];walls=layers['walls'];bounds=layers['bounds']
    preserved=layers.get('_preserved_land',set())|special.keys();regions=layers.get('_regions',{})
    hard=raw|rocks|walls
    excluded=layers.get('_excluded_scenes',set())
    painted=layers.get('coast',set())-preserved
    explicit=painted-excluded
    bank,rim=p._inset_coast(layers,special);bank-=preserved|excluded
    # A painted shore replaces the automatic bank at this edge, not a
    # second row of river cells behind it. Keep its water-facing core blue.
    bank-={p.neighbour(c,s) for c in painted for s in p.STEP}
    # A source-water corner must remain a real corner map. Dry resources are
    # only allowed on genuine land, never in a cell containing marked river.
    while True:
        changed=False;water=raw-bank
        for cell in sorted(bank):
            if cell not in bank:continue
            closed={side for side in p.STEP if p.neighbour(cell,side) in water}
            if not closed:
                diagonal=[side for side,(dx,dy) in p.DIAGONAL.items() if (cell[0]+dx,cell[1]+dy) in water]
                sides=set(diagonal[0]) if len(diagonal)==1 else set()
                backing={p.neighbour(cell,side) for side in sides}
                if sides and backing<=raw:
                    removed=backing&bank
                    bank-=removed;water|=removed;changed|=bool(removed)
                    closed=sides
                else:bank.remove(cell);water.add(cell);changed=True;continue
            ident=profile_for('coast',cell,water,set(),catalog)
            if ident is None or ident==30 or layers['overrides'].get(p.cell_key(cell),ident)!=ident:
                bank.remove(cell);water.add(cell);changed=True
        if not changed:break
    water=raw-bank
    assigned={p.point(k):r['template'] for k,r in legacy['placements'].items() if r['kind']=='rock' and p.point(k) not in excluded}
    assigned.update({c:profile_for('coast',c,water,set(),catalog) for c in bank})
    explicit_warnings=[dict(cell=p.cell_key(c),code='manual_coast_no_template') for c in sorted(painted&excluded)]
    for c in sorted(explicit):
        ident=profile_for('coast',c,water,set(),catalog)
        if ident is not None and ident!=30 and layers['overrides'].get(p.cell_key(c),ident)==ident:assigned[c]=ident
        else:explicit_warnings.append(dict(cell=p.cell_key(c),code='manual_coast_no_template'))
    blocked=(rocks|walls|water)-assigned.keys()-preserved
    # Only source/manual walls receive an outer rock rim. Generated backing
    # walls must not grow another ring on every calculation. Water, native
    # places and protected access corridors keep their own identity.
    wall_rim={(x+dx,y+dy) for x,y in walls for dx in (-1,0,1) for dy in (-1,0,1)}-hard-preserved-excluded
    wall_rim={c for c in wall_rim if p.inside(c,bounds)}
    for c in sorted(wall_rim-assigned.keys()):
        kind='coast' if any(p.neighbour(c,side) in water for side in p.STEP) else 'rock'
        ident=profile_for(kind,c,water,blocked,catalog)
        if ident is not None and layers['overrides'].get(p.cell_key(c),ident)==ident:assigned[c]=ident
    for c in sorted(rocks-assigned.keys()-preserved-excluded):
        if any(p.neighbour(c,s) in water for s in p.STEP) and any(
                p.inside(p.neighbour(c,s),bounds) and p.neighbour(c,s) not in hard for s in p.STEP):
            ident=profile_for('coast',c,water,set(),catalog)
            if ident is not None and layers['overrides'].get(p.cell_key(c),ident)==ident:assigned[c]=ident;blocked.discard(c)
    forbidden=hard|preserved|excluded
    for c in sorted({p.neighbour(q,s) for q in rim-bank for s in p.STEP}):
        if c in forbidden or not p.inside(c,bounds):continue
        if not any(p.neighbour(c,s) in water for s in p.STEP):continue
        if any(p.neighbour(c,s) in bank for s in p.STEP):continue
        ident=profile_for('coast',c,water,set(),catalog)
        if ident is not None and layers['overrides'].get(p.cell_key(c),ident)==ident:assigned[c]=ident
    anchors=set(assigned);candidates={};hard=raw|rocks|walls
    for c in sorted({(x+dx,y+dy) for x,y in anchors for dx in (-1,0,1) for dy in (-1,0,1)}-anchors):
        if c in hard or c in excluded or not p.inside(c,bounds):continue
        wet=any((c[0]+dx,c[1]+dy) in water for dx in (-1,0,1) for dy in (-1,0,1))
        kind='coast' if wet else 'rock'
        if c in preserved:
            if c in special:candidates[c]=('existing',special[c])
            continue
        ident=profile_for(kind,c,water,blocked,catalog)
        if ident is not None and layers['overrides'].get(p.cell_key(c),ident)==ident:candidates[c]=(kind,ident)
    profiles=dict(catalog);ids=dict(assigned);existing={};next_id=-1
    for c,(kind,ident) in candidates.items():
        if kind=='existing':
            profiles[next_id]=p.existing_profile(ident);ids[c]=next_id;existing[c]=next_id;next_id-=1
        else:ids[c]=ident
    fixed=dict(assigned);fixed.update(existing)
    for _ in range(4):
        labels,parts=groups(fixed,profiles,regions)
        owner=dict(labels);previous={c:None for c in fixed};distance={c:0 for c in fixed}
        queue=deque(sorted(fixed));meetings=[]
        while queue:
            c=queue.popleft()
            for side in p.STEP:
                n=p.neighbour(c,side)
                if n not in ids or regions.get(c)!=regions.get(n) or not linked(ids[c],ids[n],side,profiles):continue
                if n not in owner:
                    owner[n]=owner[c];previous[n]=c;distance[n]=distance[c]+1;queue.append(n)
                elif owner[c]!=owner[n]:meetings.append((distance[c]+distance[n],c,n))
        parents=list(range(len(parts)))
        def root(i):
            while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
            return i
        added=False
        for _,a,b in sorted(meetings):
            ra,rb=root(owner[a]),root(owner[b])
            if ra==rb:continue
            path=set()
            for c in (a,b):
                while c is not None and c not in fixed:path.add(c);c=previous[c]
            parents[ra]=rb
            for c in path:fixed[c]=ids[c];added=True
        if not added:break
    for c,i in fixed.items():
        if c not in existing:assigned[c]=i
    marked=raw|rocks
    for c in sorted(set(assigned)-anchors):
        if c in marked or assigned[c] not in (30,51):continue
        x,y=c
        if not any(all((xx+dx,yy+dy) in assigned for dx,dy in ((0,0),(1,0),(0,1),(1,1)))
                   for xx in (x-1,x) for yy in (y-1,y)):continue
        neighbours={p.neighbour(c,side) for side in p.STEP if p.neighbour(c,side) in assigned
                    and linked(assigned[c],assigned[p.neighbour(c,side)],side,catalog)}
        if not neighbours:continue
        seen={min(neighbours)};queue=list(seen)
        while queue:
            a=queue.pop()
            for side in p.STEP:
                n=p.neighbour(a,side)
                if n!=c and n in assigned and n not in seen and abs(n[0]-x)<=1 and abs(n[1]-y)<=1 and linked(assigned[a],assigned[n],side,catalog):
                    seen.add(n);queue.append(n)
        if neighbours<=seen:assigned.pop(c)
    replacements=raw&assigned.keys();water=raw-replacements
    generated=(set(map(p.point,legacy['generated_walls']))|rocks)-assigned.keys()-raw-preserved
    # A former rock back may now be an accessible joining scene. Re-select
    # the rock from its final blocked neighbours; never leave a closed face
    # pointing at another location, and never invent a backing wall over it.
    rejected=set();final_back=generated|water|walls
    for c,ident in list(assigned.items()):
        if catalog[ident].kind!='rock':continue
        closed=frozenset(side for side in p.STEP if p.neighbour(c,side) in final_back
                         or not p.inside(p.neighbour(c,side),bounds))
        options=[i for i,pr in catalog.items() if pr.kind=='rock' and pr.closed==closed]
        override=layers['overrides'].get(p.cell_key(c),'auto')
        if override!='auto':options=[i for i in options if i==override]
        if not options:rejected.add(c)
        elif ident not in options:assigned[c]=min(options)
    if rejected:return complete({**layers,'_excluded_scenes':excluded|rejected},legacy,catalog,special)
    resolutions=[]
    for row in legacy['issues']:
        c=p.point(row['cell'])
        action=('coast' if c in assigned and catalog[assigned[c]].kind=='coast' else
                'rock' if c in assigned else 'river' if c in water else
                'preserved' if c in preserved else 'wall')
        resolutions.append({**row,'resolution':action})
    placements={}
    for c,i in sorted(assigned.items()):
        pr=catalog[i];key=p.cell_key(c)
        placements[key]=dict(kind=pr.kind,template=i,closed=sorted(pr.closed),
            native_exits=sorted(pr.exits),allowed_exits=[],instance_key='boundary:'+key,
            manual=key in layers['overrides'] or c in explicit,resource_only=True,
            role='dry_connector' if i in (30,51) else 'boundary',
            wall_outline=c in wall_rim,
            replaces='water' if c in raw else 'rocks' if c in rocks else 'land',
            spawn_policy='none' if regions.get(c)=='eden' else 'not_configured')
    warnings=[r for r in legacy['issues'] if r['code'] in ('override_conflict','override_outside_boundary')
              and not (r['code']=='override_outside_boundary' and layers['overrides'].get(r['cell']) is None)
              and not (r['code']=='override_outside_boundary' and r['cell'] in placements
                       and placements[r['cell']]['template']==layers['overrides'].get(r['cell']))]+explicit_warnings
    plan={**legacy,'placements':placements,'issues':warnings, 'resolutions':resolutions,
        'generated_walls':sorted(map(p.cell_key,generated)), 'review_walls':[],
        'effective_water':sorted(map(p.cell_key,water)), 'retained_river':sorted(map(p.cell_key,water)),
        'replaced_water':sorted(map(p.cell_key,replacements)),
        'note':'Граничная линия с родными сухими переходами; за ней непроходимое русло или стены. Только черновик.'}
    plan.pop('_blocked',None)
    dead=set()
    for key,row in placements.items():
        c=p.point(key)
        row['allowed_exits']=[s for s in p.STEP if p.can_step(layers,plan,c,p.neighbour(c,s),catalog)]
        if not row['allowed_exits']:dead.add(c)
    if dead:
        return complete({**layers,'_excluded_scenes':excluded|dead},legacy,catalog,special)
    _,parts=groups(assigned,catalog,regions);links=[];sealed=0
    for key,row in placements.items():
        c=p.point(key)
        for side in ('E','S'):
            other=placements.get(p.cell_key(p.neighbour(c,side)))
            if other:
                if side in row['allowed_exits']:links.append((key,side))
                else:sealed+=1
    plan['boundary_components']=[dict(size=len(g),region=regions.get(min(g),'world'),sample=p.cell_key(min(g))) for g in parts]
    plan['summary']={**legacy['summary'], 'face_links':len(links),'walkable_face_links':len(links),
        'sealed_adjacent_faces':sealed,'water':len(water),'replaced_water':len(replacements),'retained_river':len(water),
        'coast':sum(r['kind']=='coast' for r in placements.values()),
        'rock_locations':sum(r['kind']=='rock' for r in placements.values()),
        'dry_connectors':sum(r['role']=='dry_connector' for r in placements.values()),
        'wall_outline':sum(r['wall_outline'] for r in placements.values()),
        'manual_coast':sum(p.cell_key(c) in placements for c in explicit),
        'resolved':len({r['cell'] for r in resolutions}),'unresolved':len({r['cell'] for r in warnings}),'review_walls':0,'added_walls':len(generated),
        'boundary_components':len(parts),'converted_rock_walls':len(generated&rocks)}
    return plan
