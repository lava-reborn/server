"""Read-only boundary proposals. No game bindings or terrain files are written.

Blue cells are blocked river. Preserve manual walls and keep one accessible
rock rim, backed immediately by blocked water or generated walls. Generated
walls are a separate proposal; the original manual draft is never changed.
"""
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

VERSION = 17
STEP = {'N':(0,-1),'E':(1,0),'S':(0,1),'W':(-1,0)}
OPPOSITE = {'N':'S','E':'W','S':'N','W':'E'}
DIAGONAL = {'NE':(1,-1),'SE':(1,1),'SW':(-1,1),'NW':(-1,-1)}
COAST = {17:'NE',18:'S',19:'W',20:'SW',21:'SE',22:'E',23:'NW',24:'N'}
ROCK = {1:'E',2:'E',12:'W',13:'W',10:'N',11:'N',15:'S',16:'S',5:'NS',6:'EW',
        0:'SW',3:'NW',8:'SE',9:'NE',4:'NSW',7:'NEW',14:'NES',40:'ESW'}
CONNECTORS = {30:'coast',51:'rock'}
BINS = 64


def cell_key(p):
    return '%d,%d' % p


def point(key):
    if not isinstance(key,str) or len(key.split(',')) != 2:
        raise ValueError('Некорректные координаты')
    return tuple(map(int,key.split(',')))


def normalise(doc,bounds):
    if not isinstance(doc,dict):
        raise ValueError('Некорректная разметка')
    x0,y0,x1,y1=bounds
    def cells(name):
        rows=doc.get(name,[])
        if not isinstance(rows,list):
            raise ValueError('Некорректный слой: '+name)
        values={point(k) for k in rows}
        if any(not (x0<=x<=x1 and y0<=y<=y1) for x,y in values):
            raise ValueError('Клетка вне карты')
        return values
    water,rocks,coast=cells('water'),cells('rocks'),cells('coast')
    cells('passable') # Validate legacy input, but unmarked land is now open by default.
    opened=set()
    # Legacy editors union all typed obstacles into blocked. Preserve just
    # the actual red marks separately; never erase them during generation.
    walls=cells('blocked')-water-rocks
    if water & rocks or coast & (water|rocks|walls):
        raise ValueError('У клетки указаны несовместимые ручные типы')
    overrides=doc.get('overrides',{})
    if not isinstance(overrides,dict):
        raise ValueError('Некорректные точечные назначения')
    clean={}
    for k,value in overrides.items():
        x,y=point(k)
        if not (x0<=x<=x1 and y0<=y<=y1):
            raise ValueError('Назначение вне карты')
        if value is not None and (type(value) is not int or value not in COAST and value not in ROCK and value not in CONNECTORS):
            raise ValueError('Недопустимый шаблон')
        clean[cell_key((x,y))]=value
    opacity=doc.get('opacity',70)
    if isinstance(opacity,bool) or not isinstance(opacity,(float,int)) or not 0<=opacity<=100:
        raise ValueError('Непрозрачность должна быть от 0 до 100%')
    mountain_trails=doc.get('mountain_trails',False)
    if type(mountain_trails) is not bool:raise ValueError('Некорректный режим горных троп')
    from boundary_complexes import normalise as complexes
    return dict(mountain_complexes=complexes(doc.get('mountain_complexes',{}),bounds),water=water,rocks=rocks,coast=coast,walls=walls,patrol=cells('patrol'),tunnels=cells('tunnels'),passable=opened,
                overrides=clean,opacity=opacity,bounds=bounds,mountain_trails=mountain_trails)


def document(layers):
    return dict(mountain_complexes=layers.get('mountain_complexes',{}),water=sorted(map(cell_key,layers['water'])),
                coast=sorted(map(cell_key,layers.get('coast',set()))),
                rocks=sorted(map(cell_key,layers['rocks'])),
                patrol=sorted(map(cell_key,layers.get('patrol',set()))),
                tunnels=sorted(map(cell_key,layers.get('tunnels',set()))),
                mountain_trails=layers.get('mountain_trails',False),
                blocked=sorted(map(cell_key,layers['walls']|layers['water']|layers['rocks'])),
                passable=sorted(map(cell_key,layers['passable'])),
                overrides=layers['overrides'],opacity=layers['opacity'])


def fingerprint(layers,catalog_version='native'):
    doc=document(layers);doc.pop('opacity')
    doc.update(bounds=layers['bounds'],planner_version=VERSION,catalog_version=catalog_version,
               preserved=sorted(map(cell_key,layers.get('_preserved_land',set()))),
               regions=sorted((cell_key(c),name) for c,name in layers.get('_regions',{}).items()))
    return hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def inside(p,bounds):
    x,y=p;x0,y0,x1,y1=bounds
    return x0<=x<=x1 and y0<=y<=y1


def neighbour(p,side):
    dx,dy=STEP[side]
    return p[0]+dx,p[1]+dy


@dataclass(frozen=True)
class Profile:
    id:int
    kind:str
    closed:frozenset
    edges:dict
    name:str=''
    width:int=64
    height:int=128

    @property
    def exits(self):
        return {s for s,v in self.edges.items() if v}


def seam(a,b,side):
    left=a.edges.get(side,0);right=b.edges.get(OPPOSITE[side],0)
    if bool(left)!=bool(right) or left and not left & right:
        return None
    union=left|right
    return (left^right).bit_count()/max(1,union.bit_count())


@lru_cache(maxsize=300)
def geometry(template):
    # Imports are deferred so the normaliser and synthetic tests need no RES.
    import world,travel,progression
    loc=world.location(template)
    size=loc.width*loc.height
    free=set(range(size))-loc.obstacles
    components={};groups=[]
    for start in sorted(free):
        if start in components:continue
        number=len(groups);group={start};components[start]=number;queue=[start]
        while queue:
            current=queue.pop()
            for n in progression.hex_neighbours(current,loc.width,loc.height):
                if n in free and n not in components:
                    components[n]=number;group.add(n);queue.append(n)
        groups.append(group)
    exits={c:s for c,s in travel.exit_sides(loc).items()
           if c in free and 0<=c<size and s in STEP}
    entries=[c for c in loc.entries if c in free and 0<=c<size]
    eligible={components[c] for c in entries} & {components[c] for c in exits}
    main=max(eligible,key=lambda i:len(groups[i])) if eligible else None
    return dict(loc=loc,components=components,main=main,exits=exits,entries=entries)


@lru_cache(maxsize=1)
def native_catalog():
    catalog={};stamp=hashlib.sha256()
    for template,closed in {**ROCK,**COAST,30:'',51:''}.items():
        g=geometry(template);loc=g['loc'];edges={s:0 for s in STEP}
        for c,s in g['exits'].items():
            if g['components'][c]!=g['main']:continue
            index=c%loc.width if s in ('N','S') else c//loc.width
            length=loc.width if s in ('N','S') else loc.height
            # Cover the full source interval when normalising to 64 bins.
            lo=index*BINS//length;hi=max(lo+1,((index+1)*BINS+length-1)//length)
            for bit in range(lo,min(BINS,hi)):edges[s]|=1<<bit
        if g['main'] is None or set(closed)&{s for s,v in edges.items() if v}:
            raise ValueError('Родной шаблон не подтверждает закрытую сторону: '+str(template))
        catalog[template]=Profile(template,CONNECTORS.get(template,'coast' if template in COAST else 'rock'),
                                  frozenset(closed),edges,loc.fn,loc.width,loc.height)
        stamp.update(repr((template,closed,edges,sorted(loc.obstacles))).encode())
    return catalog,stamp.hexdigest()


@lru_cache(maxsize=256)
def existing_profile(template):
    g=geometry(template);loc=g['loc'];edges={s:0 for s in STEP}
    for c,side in g['exits'].items():
        if g['components'][c]!=g['main']:continue
        index=c%loc.width if side in ('N','S') else c//loc.width
        length=loc.width if side in ('N','S') else loc.height
        lo=index*BINS//length;hi=max(lo+1,((index+1)*BINS+length-1)//length)
        for bit in range(lo,min(BINS,hi)):edges[side]|=1<<bit
    return Profile(template,'existing',frozenset(s for s in STEP if not edges[s]),edges,loc.fn,loc.width,loc.height)


def _component_assignment(nodes,domains,catalog):
    """Exact dynamic programming on chains/cycles, constrained relaxation on forks."""
    adjacent={p:[(neighbour(p,s),s) for s in STEP if neighbour(p,s) in nodes] for p in nodes}
    if max((len(v) for v in adjacent.values()),default=0)<=2:
        first=min((p for p in nodes if len(adjacent[p])<2),default=min(nodes))
        order=[];seen=set();last=None;current=first
        while current is not None and current not in seen:
            order.append(current);seen.add(current)
            following=[n for n,s in adjacent[current] if n!=last and n not in seen]
            last,current=current,(min(following) if following else None)
        cycle=len(order)>2 and first in [n for n,s in adjacent[order[-1]]]
        best=None
        for initial in sorted(domains[first]):
            states={initial:(0,[initial])}
            for a,b in zip(order,order[1:]):
                side=next(s for n,s in adjacent[a] if n==b);new={}
                for value in sorted(domains[b]):
                    choices=[]
                    for prev,(cost,path) in states.items():
                        extra=seam(catalog[prev],catalog[value],side)
                        if extra is not None:choices.append((cost+extra,path+[value]))
                    if choices:new[value]=min(choices)
                states=new
            for last_id,(cost,path) in states.items():
                if cycle:
                    side=next(s for n,s in adjacent[order[-1]] if n==first)
                    extra=seam(catalog[last_id],catalog[initial],side)
                    if extra is None:continue
                    cost+=extra
                candidate=(cost,path)
                if best is None or candidate<best:best=candidate
        if best is not None:return dict(zip(order,best[1])),False
    chosen={}
    for p in sorted(nodes):
        compatible=[i for i in sorted(domains[p]) if all(
            seam(catalog[i],catalog[chosen[n]],s) is not None for n,s in adjacent[p] if n in chosen)]
        if not compatible:return {},True
        chosen[p]=compatible[0]
    for _ in range(8):
        changed=False
        for p in sorted(nodes):
            options=[]
            for i in sorted(domains[p]):
                values=[seam(catalog[i],catalog[chosen[n]],s) for n,s in adjacent[p]]
                if all(v is not None for v in values):options.append((sum(values),i))
            if options:
                value=min(options)[1];changed|=value!=chosen[p];chosen[p]=value
        if not changed:break
    return chosen,True


def _simple_river_edge(cell,water,walls,rocks,bounds):
    """Peel only a topologically simple edge: retain river and land connectivity."""
    ring={(cell[0]+dx,cell[1]+dy) for dx in (-1,0,1) for dy in (-1,0,1)
          if (dx or dy) and inside((cell[0]+dx,cell[1]+dy),bounds)}
    cardinal={neighbour(cell,s) for s in STEP}
    def connected(values):
        targets=values&cardinal
        if not targets:return False
        seen={next(iter(targets))};queue=list(seen)
        while queue:
            current=queue.pop()
            for side in STEP:
                n=neighbour(current,side)
                if n in values and n not in seen:seen.add(n);queue.append(n)
        return targets<=seen
    return connected(ring&water) and connected(ring-water-walls-rocks)


def _inset_coast(layers,special):
    """Use the outer water row, keeping a blocked core and both real banks."""
    water=layers['water'];walls=layers['walls'];rocks=layers['rocks'];bounds=layers['bounds']
    forbidden=water|walls|rocks
    rim={p for p in water if any(inside(neighbour(p,s),bounds) and
                              neighbour(p,s) not in forbidden for s in STEP)}
    core=water-rim;retained=set(water);bank=set()
    for cell in sorted(rim-special.keys()):
        # Never consume a thin channel or an entire isolated water patch.
        if not any(neighbour(cell,s) in core for s in STEP):continue
        if _simple_river_edge(cell,retained,walls,rocks,bounds):
            retained.remove(cell);bank.add(cell)
    # Join diagonal steps using a native corner, never an opposite-bank bridge.
    initial=set(bank);corners=set()
    for cell in initial:
        for dx,dy in DIAGONAL.values():
            q=cell[0]+dx,cell[1]+dy
            if q in initial and not any(c in initial for c in ((cell[0]+dx,cell[1]),(cell[0],cell[1]+dy))):
                corners.update(((cell[0]+dx,cell[1]),(cell[0],cell[1]+dy)))
    shapes={frozenset(s) for s in COAST.values()}
    for cell in sorted(corners&retained-special.keys()):
        adjacent={side for side in STEP if neighbour(cell,side) in bank}
        closed={side for side in STEP if neighbour(cell,side) in retained}
        if len(adjacent)>=2 and frozenset(closed) in shapes and _simple_river_edge(cell,retained,walls,rocks,bounds):
            retained.remove(cell);bank.add(cell)
    return bank,rim


def _conservative_generate(layers,catalog,special=None,catalog_version='native'):
    special=special or {};raw_water=layers['water'];rocks=layers['rocks'];walls=layers['walls']
    bounds=layers['bounds'];issues=[];issue_keys=set();trimmed=[]
    def issue(p,code,**extra):
        row=dict(cell=cell_key(p),code=code,**extra)
        signature=json.dumps(row,sort_keys=True)
        if signature not in issue_keys:issue_keys.add(signature);issues.append(row)
    for p in sorted((raw_water|walls|rocks)&special.keys()):
        issue(p,'protected_mark_conflict',existing=special[p])
    bank,rim=_inset_coast(layers,special)
    for p in sorted(rim-bank-special.keys()):issue(p,'coast_channel_preserved')
    rock_mass=rocks|walls
    interior={p for p in rocks if all(neighbour(p,s) in rock_mass or not inside(neighbour(p,s),bounds) for s in STEP)}
    rock_rim=rocks-interior
    # Removal only: every failed replacement returns to blocked river. Recompute
    # adjacent shapes after each retreat, rather than leaving false open edges.
    while True:
        water=raw_water-bank;rock_back=interior|walls|water
        domains={};kinds={}
        for p in sorted(bank|rock_rim):
            if p in special:
                issue(p,'protected_location',existing=special[p]);continue
            kind='coast' if p in bank else 'rock';kinds[p]=kind
            back=water if kind=='coast' else rock_back
            closed={s for s in STEP if neighbour(p,s) in back
                    or kind=='rock' and not inside(neighbour(p,s),bounds)}
            if kind=='rock' and not closed:
                corners=[s for s,(dx,dy) in DIAGONAL.items() if (p[0]+dx,p[1]+dy) in rock_back]
                if len(corners)==1:closed=set(corners[0])
            choices={i for i,profile in catalog.items() if profile.kind==kind and profile.closed==closed}
            key=cell_key(p)
            if key in layers['overrides']:
                override=layers['overrides'][key]
                if override is None:
                    issue(p,'assignment_suppressed');trimmed.append(key);continue
                if override not in choices:
                    if kind=='rock' and not closed and override in catalog and catalog[override].kind=='rock':choices={override}
                    else:issue(p,'override_conflict',template=override);continue
                else:choices={override}
            if not choices:
                issue(p,'ambiguous_rock_direction' if kind=='rock' and not closed else 'no_matching_template');continue
            domains[p]=choices
        missing=bank-domains.keys()
        if missing:bank-=missing;continue
        # Prune incompatible neighbour choices. When a mandatory shape cannot
        # meet its neighbour, quarantine a cell rather than inventing river tails.
        changed=True
        while changed:
            changed=False
            for p in sorted(list(domains)):
                if p not in domains:continue
                for side in ('E','S'):
                    q=neighbour(p,side)
                    if q not in domains:continue
                    pairs={(a,b) for a in domains[p] for b in domains[q] if seam(catalog[a],catalog[b],side) is not None}
                    if not pairs:
                        def strength(c):
                            return (cell_key(c) in layers['overrides'],sum(neighbour(c,s) in water for s in STEP),c)
                        drop=min((p,q),key=strength)
                        issue(drop,'incompatible_neighbour',neighbour=cell_key(q if drop==p else p))
                        trimmed.append(cell_key(drop));domains.pop(drop);changed=True;break
                    a={a for a,b in pairs};b={b for a,b in pairs}
                    if a!=domains[p] or b!=domains[q]:domains[p]=a;domains[q]=b;changed=True
        isolated={cell for cell in domains if not any(neighbour(cell,side) in domains for side in STEP)}
        for cell in isolated:issue(cell,'isolated_boundary');domains.pop(cell)
        chosen={};unseen=set(domains);relaxed=0
        while unseen:
            seed=min(unseen);component={seed};queue=[seed];unseen.remove(seed)
            while queue:
                current=queue.pop()
                for side in STEP:
                    n=neighbour(current,side)
                    if n in unseen:unseen.remove(n);component.add(n);queue.append(n)
            assignments,approximate=_component_assignment(component,domains,catalog);relaxed+=approximate
            if not assignments:
                for p in sorted(component):issue(p,'component_needs_manual_review')
            chosen.update(assignments)
        missing=bank-chosen.keys()
        # A coastline must join another coastline by a cardinal face.
        isolated={cell for cell in bank if not any(neighbour(cell,side) in bank for side in STEP)}
        for cell in isolated:issue(cell,'isolated_coast')
        missing|=isolated
        if missing:bank-=missing;continue
        # Exactly one row of accessible rock scenes. All remaining marked rock
        # depth becomes generated walls, not another row of scenes. A selected
        # scene must have a real blocked cell immediately on each closed side.
        # Thin strips can gain a backing cell only from an explicit orientation;
        # never consume a protected point, a bank or another scene.
        extra_walls=set();rejected=set();hard_back=water|walls
        for p,template in sorted(chosen.items()):
            profile=catalog[template]
            if profile.kind!='rock':continue
            proposed=set();conflicts=[]
            for side in sorted(profile.closed):
                q=neighbour(p,side)
                if not inside(q,bounds) or q in hard_back:continue
                if q in layers.get('_preserved_land',set()):conflicts.append(cell_key(q));continue
                if q in rocks and q not in chosen:continue
                if (cell_key(p) in layers['overrides'] and q not in
                        rocks|bank|special.keys()|chosen.keys()):
                    proposed.add(q)
                else:conflicts.append(cell_key(q))
            if conflicts:
                issue(p,'backing_wall_conflict',neighbours=conflicts);rejected.add(p)
            else:extra_walls.update(proposed)
        for p in rejected:chosen.pop(p)
        generated_walls=((rocks-set(chosen))|extra_walls)-special.keys()-layers.get('_preserved_land',set())
        for key in layers['overrides']:
            p=point(key)
            if p not in kinds and p not in special:issue(p,'override_outside_boundary')
        # Old issues on a now-valid rock are no longer blockers. All unplaced
        # uncertain cells are closed, except protected points which need review.
        active_keys={cell_key(p) for p in chosen}
        current_issues=[r for r in issues if r['cell'] not in active_keys]
        review_walls={point(r['cell']) for r in current_issues
                      if r['code']!='protected_location' and point(r['cell']) not in special and point(r['cell']) not in layers.get('_preserved_land',set())}
        generated_walls|=review_walls
        replacements={p for p,i in chosen.items() if catalog[i].kind=='coast'}
        placements={cell_key(p):dict(kind=catalog[i].kind,template=i,closed=sorted(catalog[i].closed),
            native_exits=sorted(catalog[i].exits),allowed_exits=[],instance_key='boundary:'+cell_key(p),
            manual=cell_key(p) in layers['overrides'],replaces='water' if p in replacements else 'rocks')
            for p,i in sorted(chosen.items())}
        plan=dict(version=VERSION,input_fingerprint=fingerprint(layers,catalog_version),
            catalog_version=catalog_version,placements=placements,issues=current_issues,
            trimmed=sorted(set(trimmed)),interior_rocks=sorted(map(cell_key,interior)),
            generated_walls=sorted(map(cell_key,generated_walls)),backing_walls=sorted(map(cell_key,extra_walls)),
            review_walls=sorted(map(cell_key,review_walls)),replaced_water=sorted(map(cell_key,replacements)),
            retained_river=sorted(map(cell_key,raw_water-replacements)),
            effective_water=sorted(map(cell_key,raw_water-replacements-generated_walls)),
            approved=False,apply_supported=False,solver_fork_components=relaxed,
            note='Берег заменяет край водной разметки. Русло и спорные клетки закрыты; художественные стыки требуют просмотра.')
        # Remove inaccessible scenes, never assign a location to a review wall.
        retry=False
        while placements:
            plan.pop('_blocked',None)
            for key,row in placements.items():
                p=point(key)
                row['allowed_exits']=[s for s in STEP if can_step(layers,plan,p,neighbour(p,s),catalog)]
            dead=[k for k,r in placements.items() if not r['allowed_exits']]
            if not dead:break
            for key in dead:issue(point(key),'no_safe_return')
            lost_coast={point(k) for k in dead if placements[k]['kind']=='coast'}
            if lost_coast:bank-=lost_coast;retry=True;break
            for key in dead:
                placements.pop(key);generated_walls.add(point(key));review_walls.add(point(key))
            plan['generated_walls']=sorted(map(cell_key,generated_walls))
            plan['review_walls']=sorted(map(cell_key,review_walls))
        if retry:continue
        plan['issues']=[r for r in issues if r['cell'] not in placements]
        # Overrides outside the candidate rim also remain closed for review.
        new_review={point(r['cell']) for r in issues if r['cell'] not in placements
                    and r['code']!='protected_location' and point(r['cell']) not in special and point(r['cell']) not in layers.get('_preserved_land',set())}
        generated_walls|=new_review;review_walls|=new_review
        plan.update(issues=[r for r in issues if r['cell'] not in placements],
            generated_walls=sorted(map(cell_key,generated_walls)),review_walls=sorted(map(cell_key,review_walls)),
            effective_water=sorted(map(cell_key,raw_water-replacements-generated_walls)))
        plan.pop('_blocked',None)
        links=[]
        for key,row in placements.items():
            cell=point(key)
            for side in ('E','S'):
                other=placements.get(cell_key(neighbour(cell,side)))
                if other:
                    if seam(catalog[row['template']],catalog[other['template']],side) is None:
                        raise ValueError('Несогласованный стык границы')
                    links.append((key,side,side in row['allowed_exits']))
        plan['summary']=dict(face_links=len(links),walkable_face_links=sum(link[2] for link in links),water=len(raw_water-replacements-generated_walls),source_water=len(raw_water),
            replaced_water=len(replacements),retained_river=len(raw_water-replacements),
            walls=len(walls),rocks=len(rocks),coast=len(replacements),
            rock_locations=sum(r['kind']=='rock' for r in placements.values()),
            unresolved=len({r['cell'] for r in plan['issues']}),trimmed=len(set(trimmed)),
            preserved_manual_walls=len(walls),added_walls=len(generated_walls),review_walls=len(review_walls),
            converted_rock_walls=len(generated_walls&rocks),extended_backing_walls=len(extra_walls))
        return plan


def generate(layers,catalog,special=None,catalog_version='native'):
    from boundary_outline import complete
    original_fingerprint=fingerprint(layers,catalog_version)
    marked=layers['water']|layers['walls']|layers['rocks']|layers.get('coast',set())
    # An erased mark uses the existing null override plus an empty manual
    # cell. It stays genuinely empty; generated walls and joining scenes
    # cannot silently fill it again. A suppressed shore over water is not
    # empty and therefore keeps its blocked river backing.
    cleared={point(k) for k,value in layers['overrides'].items() if value is None}-marked
    projected={**layers,'_preserved_land':layers.get('_preserved_land',set())|cleared}
    plan=_conservative_generate(projected,{i:pr for i,pr in catalog.items() if i not in CONNECTORS},special,catalog_version)
    plan=complete(projected,plan,catalog,special or {})
    plan['input_fingerprint']=original_fingerprint
    plan['cleared_land']=sorted(map(cell_key,cleared))
    return plan


def passable(layers,plan,p):
    if not inside(p,layers['bounds']):return False
    if '_blocked' not in plan:
        assigned={point(k) for k in plan['placements']}
        unresolved={point(r['cell']) for r in plan['issues'] if r['code'] not in ('protected_location','override_conflict','override_outside_boundary','manual_coast_no_template')} if plan.get('issues_block_movement',True) else set()
        generated={point(k) for k in plan.get('generated_walls',[])}|{point(k) for k in plan.get('depth_cells',[])}
        water={point(k) for k in plan.get('effective_water',map(cell_key,layers['water']))}
        preserved=set(map(point,plan.get('preserved_land',[])))|layers.get('_preserved_land',set())
        plan['_blocked']=frozenset((water|layers['walls']|generated|(layers['rocks']-assigned)|unresolved)-preserved)
    return p not in plan['_blocked']


def can_step(layers,plan,a,b,catalog):
    delta=b[0]-a[0],b[1]-a[1]
    side=next((s for s,d in STEP.items() if d==delta),None)
    if side is None or not passable(layers,plan,a) or not passable(layers,plan,b):return False
    regions=layers.get('_regions',{});region=regions.get(a,'world')
    if region!=regions.get(b,'world'):return False
    ar=plan['placements'].get(cell_key(a));br=plan['placements'].get(cell_key(b))
    if region in layers.get('_mask_regions',set()) and not (ar or br):return True
    special=layers.get('_special',{})
    ap=catalog[ar['template']] if ar else existing_profile(special[a]) if a in special else None
    bp=catalog[br['template']] if br else existing_profile(special[b]) if b in special else None
    if ar and side in ar.get('portal_sides',()):return False
    if br and OPPOSITE[side] in br.get('portal_sides',()):return False
    if ap and not ap.edges.get(side):return False
    if bp and not bp.edges.get(OPPOSITE[side]):return False
    return ap is None or bp is None or seam(ap,bp,side) is not None


def route(layers,plan,start,end,catalog):
    if not passable(layers,plan,start) or not passable(layers,plan,end):
        return dict(reachable=False,reason='Начало или конец пути закрыты',path=[])
    previous={start:None};queue=deque([start])
    while queue:
        current=queue.popleft()
        if current==end:
            path=[]
            while current is not None:path.append(cell_key(current));current=previous[current]
            return dict(reachable=True,path=list(reversed(path)),visited=len(previous))
        for side in STEP:
            n=neighbour(current,side)
            if n not in previous and can_step(layers,plan,current,n,catalog):
                previous[n]=current;queue.append(n)
    return dict(reachable=False,path=[],visited=len(previous),reason='Нет разрешённого маршрута')


def local_probe(template,start,end):
    g=geometry(template);loc=g['loc'];a=g['components'].get(start);b=g['components'].get(end)
    valid=type(start) is int and type(end) is int and 0<=start<loc.width*loc.height and 0<=end<loc.width*loc.height
    return dict(reachable=bool(valid and a is not None and a==b),
                start_free=bool(valid and a is not None),end_free=bool(valid and b is not None),
                entry_component=bool(valid and a is not None and a==g['main']))
