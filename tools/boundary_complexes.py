"""Mountain trail doors over the explicitly approved native binding table."""
from copy import deepcopy
import boundary_planner as p

GROUPS={
 'halfa':dict(title='Хальфа',portals=(598,623),master=599),
 'abu':dict(title='Абу-Хамед',portals=(163,53),master=624),
}

def normalise(value,bounds):
    if not isinstance(value,dict) or set(value)-GROUPS.keys():raise ValueError('Некорректные горные комплексы')
    result={}
    for city,origin in value.items():
        if not isinstance(origin,list) or len(origin)!=2 or any(type(n) is not int for n in origin):raise ValueError('Некорректный центр горных троп')
        x,y=origin
        if not p.inside((x-4,y-2),bounds) or not p.inside((x+4,y+7),bounds):raise ValueError('Горные тропы вне карты')
        result[city]=list(origin)
    return result

def project(layers,special):
    # Both bottom approaches use one existing native masters' room, as in
    # Dongola. Moving an editor pattern must never synthesize more NPC rooms.
    special=dict(special)
    layers['_complex_bindings']={};layers['_retired_complex_sources']=set()
    layers['_special']=special
    return special

def annotate(rows,layers):
    import travel,world
    if not layers.get('mountain_complexes'):return
    ids={ident for city in layers['mountain_complexes'] for ident in GROUPS[city]['portals']}|{162}
    for key,row in rows.items():
        ident=layers['_special'].get(p.point(key))
        if ident not in ids:continue
        g=p.geometry(row['template']);cells=sorted(c for c,side in g['exits'].items() if side=='N' and g['components'].get(c)==g['main'])
        doors={s:deepcopy(travel.door(ident,s)) for s in 'ab' if travel.door(ident,s)}
        internal=any(ident in GROUPS[city]['portals'] and
                     (layers['_special'].get(tuple(origin))==GROUPS[city]['master'] or
                      all(layers['_special'].get(c)==GROUPS[city]['master'] for c in
                          ((origin[0]-1,origin[1]+5),(origin[0]+1,origin[1]+5))) and p.point(key)!=tuple(origin))
                     for city,origin in layers['mountain_complexes'].items())
        if internal:
            # Keep both corridor faces usable. A separate native-free interior
            # door hex carries the old intercity link instead of consuming N/S.
            arrival=travel.arrival_cell(g['loc'],'N');target=arrival+4*g['loc'].width
            free=[c for c,component in g['components'].items() if component==g['main'] and c not in g['exits'] and c not in g['entries']]
            cells=[min(free,key=lambda c:(abs(c%g['loc'].width-target%g['loc'].width)+abs(c//g['loc'].width-target//g['loc'].width),c))]
        row.update(mountain_portal=True,trail_family=world.location(ident).fn,source_location=ident,preserve_source_binding=True,
                   source_doors=doors,portal_sides=[] if internal else ['N'] if cells else [],internal_portal=internal,
                   door_designs=[dict(source_side=s,target_loc_id=d.get('target_loc_id'),side='internal' if internal else 'N',cells=cells) for s,d in doors.items()])

def links(layers,plan):
    """Explicit native-safe portal arrivals; unknown recovered doors stay disabled."""
    import travel
    special=layers['_special'];by_id={}
    for c,ident in special.items():by_id.setdefault(ident,[]).append(c)
    result=[]
    for key,row in plan['placements'].items():
        if not row.get('portal_sides') and not row.get('internal_portal'):continue
        for door in row.get('door_designs',[]):
            target=door.get('target_loc_id');destinations=by_id.get(target,[])
            enabled=bool(destinations) and bool(door['cells']) and row['source_doors'][door['source_side']].get('confidence') in ('high','medium')
            item=dict(cell=key,source_location=row['source_location'],source_side=door['source_side'],
                      source_hexes=door['cells'],target_location=target,enabled=enabled,internal=bool(row.get('internal_portal')))
            if enabled:
                dest=min(destinations);other=plan['placements'].get(p.cell_key(dest));template=other['template'] if other else target
                side='N' if door['side']=='internal' or other and (other.get('portal_sides') or other.get('internal_portal')) else p.OPPOSITE[door['side']]
                g=p.geometry(template);arrival=travel.arrival_cell(g['loc'],side)
                if g['components'].get(arrival)!=g['main']:raise ValueError('Портал ведёт в изолированную геометрию')
                item.update(target_cell=p.cell_key(dest),target_template=template,arrival_hex=arrival,arrival_side=side)
            else:item['reason']='source_door_has_no_recovered_target'
            result.append(item)
    return result
