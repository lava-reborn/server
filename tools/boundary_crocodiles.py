"""Draft-only regional crocodiles on authored coasts; never installs game bindings."""
from collections import deque,Counter
from functools import lru_cache
import hashlib,json
import boundary_planner as p

# The four user-supplied screenshot rectangles, registered to the native map.
# A one-cell margin includes a shore cut by the screenshot edge.
REGIONS={
    'Вади-Хальфа':dict(bounds=(5919,1660,6034,1765),mob=2418,level=4),
    'Абри':dict(bounds=(5833,1798,5937,1899),mob=2419,level=11),
    'Донгола':dict(bounds=(5833,1910,6079,2143),mob=130,level=12),
    'Абу-Хамед':dict(bounds=(6087,1945,6237,2063),mob=2420,level=17),
}
EXIT_DISTANCE=10
OBJECT_CLEARANCE=3
MOB_DISTANCE=12
LAND_PER_MOB=450
MAX_MOBS=10
VARIANTS=8


def city_at(cell):
    found=[name for name,row in REGIONS.items() if p.inside(cell,row['bounds'])]
    return found[0] if len(found)==1 else None


def distances(width,height,seeds,allowed=None):
    import progression
    seeds=set(seeds);result=dict.fromkeys(seeds,0);queue=deque(sorted(seeds))
    while queue:
        c=queue.popleft()
        for n in progression.hex_neighbours(c,width,height):
            if n not in result and (allowed is None or n in allowed):
                result[n]=result[c]+1;queue.append(n)
    return result


def hex_steps(a,b,width):
    """Exact distance on the client's odd-row hex grid, without obstacles."""
    ax,ay=a%width,a//width;bx,by=b%width,b//width
    aq=ax-(ay-(ay&1))//2;bq=bx-(by-(by&1))//2
    dq,dr=aq-bq,ay-by
    return max(abs(dq),abs(dr),abs(dq+dr))


@lru_cache(maxsize=128)
def native_habitat(template):
    import progression,travel
    g=p.geometry(template);loc=g['loc']
    land={c for c,group in g['components'].items() if group==g['main']}
    doors=set(g['entries'])|g['exits'].keys()
    if loc.war:doors.update(travel.war_entries(loc))
    # Global entry may use the inward neighbour of an outzone. It must be
    # protected too, together with the location's central war entry zones.
    doors.update(n for cell,side in g['exits'].items()
                 for n in progression.hex_neighbours(cell,loc.width,loc.height)
                 if travel._edge_distance(loc,n,side)>travel._edge_distance(loc,cell,side))
    doors={c for c in doors if 0<=c<loc.width*loc.height and c not in loc.obstacles}
    # Straight hex distance ignores obstacles, so a nearby door across a bush
    # or a thin wall is still excluded from the spawn area.
    door_distance=distances(loc.width,loc.height,doors)
    rim={c for c in land if c%loc.width in (0,loc.width-1) or c//loc.width in (0,loc.height-1)
         or any(n not in land for n in progression.hex_neighbours(c,loc.width,loc.height))}
    clearance=distances(loc.width,loc.height,rim,land)
    candidates=tuple(sorted(c for c in land if door_distance.get(c,0)>=EXIT_DISTANCE
                            and clearance.get(c,0)+1>=OBJECT_CLEARANCE))
    wanted=min(MAX_MOBS,max(1,len(land)//LAND_PER_MOB))
    return dict(width=loc.width,height=loc.height,land=frozenset(land),doors=frozenset(doors),
                exit_distance=door_distance,clearance=clearance,candidates=candidates,wanted=wanted)


@lru_cache(maxsize=8)
def habitat(template):
    if template not in p.COAST:raise ValueError('Крокодилы размещаются только на родных берегах 17–24')
    return native_habitat(template)


@lru_cache(maxsize=64)
def layout(template,variant):
    h=habitat(template);available=set(h['candidates']);chosen=[]
    nearest={c:h['exit_distance'][c] for c in available}
    while available and len(chosen)<h['wanted']:
        cell=max(available,key=lambda c:(nearest[c],min(h['clearance'][c],6),
                  ((c*2654435761)^((variant+1)*2246822519))&0xffffffff))
        chosen.append(cell);available.remove(cell)
        for other in list(available):
            distance=hex_steps(cell,other,h['width'])
            if distance<MOB_DISTANCE:available.remove(other)
            else:nearest[other]=min(nearest[other],distance)
    return tuple(sorted(chosen))


def population(key,template,catalog_version='native'):
    city=city_at(p.point(key))
    if city is None or template not in p.COAST:return None
    profile=REGIONS[city]
    variant=int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%VARIANTS
    positions=layout(template,variant)
    if not positions:return None
    signature=hashlib.sha256(json.dumps([key,template,profile['mob'],profile['level'],positions,
                  catalog_version,EXIT_DISTANCE,OBJECT_CLEARANCE,MOB_DISTANCE],sort_keys=True).encode()).hexdigest()
    return dict(template=template,city=city,type_id=profile['mob'],level=profile['level'],
                positions=list(positions),signature=signature,xp_multiplier=1.0,loot=False,
                combat_profile='ordinary_level_gold_fangs',attack_name='Клыки',instance_key='boundary:'+key)


def build(layers,plan,protected=()):
    cells={};excluded={};protected=set(protected)
    for key,row in sorted(plan['placements'].items()):
        if row['kind']!='coast':continue
        cell=p.point(key);region=layers.get('_regions',{}).get(cell,'world')
        if region!='world':reason='isolated_'+region
        elif cell in protected:reason='existing_location'
        elif row['template'] not in p.COAST:reason='dry_connector'
        elif city_at(cell) is None:reason='outside_regions'
        elif not p.passable(layers,plan,cell) or not row['allowed_exits']:reason='closed_geometry'
        else:
            value=population(key,row['template'],plan['catalog_version'])
            if value:
                cells[key]=value;row['spawn_policy']='regional_crocodiles';continue
            reason='no_safe_spawn_area'
        excluded[key]=reason
    by_city={name:dict(level=r['level'],type_id=r['mob'],locations=0,mobs=0) for name,r in REGIONS.items()}
    for row in cells.values():
        stats=by_city[row['city']];stats['locations']+=1;stats['mobs']+=len(row['positions'])
    return dict(enabled=True,cells=cells,excluded=excluded,cities=by_city,
                summary=dict(locations=len(cells),mobs=sum(len(r['positions']) for r in cells.values()),
                             excluded=dict(Counter(excluded.values()))),
                rules=dict(exit_distance=EXIT_DISTANCE,object_clearance=OBJECT_CLEARANCE,
                           mob_distance=MOB_DISTANCE,land_per_mob=LAND_PER_MOB,max_mobs=MAX_MOBS))


def validate_overrides(rows,bounds,catalog_version):
    if not isinstance(rows,dict) or len(rows)>10000:raise ValueError('Некорректные позиции прибрежных мобов')
    result={}
    for key,row in rows.items():
        cell=p.point(key)
        if not p.inside(cell,bounds) or not isinstance(row,dict):raise ValueError('Клетка мобов вне карты')
        template=row.get('template')
        if type(template) is not int or template not in p.COAST:raise ValueError('Некорректная прибрежная карта')
        base=population(key,template,catalog_version)
        if base is None or row.get('signature')!=base['signature']:raise ValueError('Состав прибрежных мобов изменился — обнови предпросмотр')
        positions=row.get('positions');h=habitat(template)
        if not isinstance(positions,list) or len(positions)!=len(base['positions']):raise ValueError('Нельзя менять количество мобов перемещением')
        candidates=set(h['candidates'])
        for i,c in enumerate(positions):
            if type(c) is not int or c not in candidates:raise ValueError('Недопустимый гекс: препятствие, узкий участок или слишком близко к выходу')
            if any(hex_steps(c,other,h['width'])<MOB_DISTANCE for other in positions[:i]):raise ValueError('Между крокодилами нужно не меньше 12 гексов')
        result[key]=dict(template=template,signature=base['signature'],positions=list(positions))
    return result


def saved_overrides(rows,bounds,catalog_version,previous):
    """Keep untouched, stale draft patches without making them active again.

    A catalog update must not prevent saving unrelated map edits. The preview
    only uses a patch with the current template and population signature;
    newly submitted positions still go through strict native validation.
    """
    if not isinstance(rows,dict) or len(rows)>10000:raise ValueError('Некорректные позиции прибрежных мобов')
    from copy import deepcopy
    kept={k:deepcopy(row) for k,row in rows.items() if k in previous and row==previous[k]}
    fresh=validate_overrides({k:row for k,row in rows.items() if k not in kept},bounds,catalog_version)
    return {**kept,**fresh}
