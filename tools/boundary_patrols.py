"""The owner's level 19 Magrib overlay; populations belong to individual cells."""
from collections import Counter
from copy import deepcopy
import hashlib,json
from functools import lru_cache
import boundary_planner as p
from boundary_crocodiles import native_habitat,hex_steps,MOB_DISTANCE,EXIT_DISTANCE,OBJECT_CLEARANCE

TYPES=((98,19),)
MAX_MOBS=8
LAND_PER_MOB=700


def habitat(template):
    import world
    # Thousands of wilderness instances share four original XML resources.
    # Keep occupancy/identity per cell, but flood each native geometry once.
    if world.is_wilderness(template):
        x,y=world.unpack(template)
        template=world.pack(6000,2000+((x+y)&3))
    return native_habitat(template)


def occupied_at(key,template,doc):
    from boundary_cells import inhabitants,signature
    base=inhabitants(template)
    patch=doc.get('mob_overrides',{}).get(key)
    if patch and patch.get('location_id')==template and patch.get('spawn_signature')==signature(template) and len(patch.get('positions',[]))==len(base):
        return tuple(patch['positions'])
    return tuple(row['cell'] for row in base)


def population(key,template,occupied,catalog_version):
    return deepcopy(_population(key,template,tuple(sorted(occupied)),catalog_version))


@lru_cache(maxsize=8192)
def _population(key,template,occupied,catalog_version):
    h=habitat(template);occupied=tuple(sorted(occupied));available=set(h['candidates'])
    if occupied:available={c for c in available if all(hex_steps(c,n,h['width'])>=MOB_DISTANCE for n in occupied)}
    seed=int.from_bytes(hashlib.sha256(key.encode()).digest()[:4],'big')
    nearest={c:h['exit_distance'][c] for c in available};chosen=[]
    while available and len(chosen)<min(MAX_MOBS,max(1,len(h['land'])//LAND_PER_MOB)):
        cell=max(available,key=lambda c:(nearest[c],min(h['clearance'][c],6),((c*2654435761)^seed)&0xffffffff))
        chosen.append(cell);available.remove(cell)
        for other in list(available):
            d=hex_steps(cell,other,h['width'])
            if d<MOB_DISTANCE:available.remove(other)
            else:nearest[other]=min(nearest[other],d)
    chosen.sort()
    if not chosen:return None
    types=[TYPES[(seed+i)%len(TYPES)][0] for i in range(len(chosen))]
    levels=[TYPES[(seed+i)%len(TYPES)][1] for i in range(len(chosen))]
    signature=hashlib.sha256(json.dumps([key,template,chosen,types,occupied,catalog_version,
        EXIT_DISTANCE,OBJECT_CLEARANCE,MOB_DISTANCE,LAND_PER_MOB],sort_keys=True).encode()).hexdigest()
    return dict(template=template,positions=chosen,type_ids=types,levels=levels,signature=signature,
                occupied=list(occupied),display_name='Патруль Магриба',instance_key='patrol:'+key,
                rewards='xp_only',loot=False,xp_multiplier=1.0,preserve_existing=True)


def build(layers,plan,doc):
    import world,travel
    cells={};excluded={}
    for cell in sorted(layers.get('patrol',set())):
        key=p.cell_key(cell);row=plan['placements'].get(key)
        if cell in layers['water']|layers['walls']|layers['coast'] or row and row['kind']=='coast':reason='patrol_terrain_conflict'
        elif layers.get('_regions',{}).get(cell,'world')!='world':reason='patrol_isolated_region'
        elif not p.passable(layers,plan,cell):reason='patrol_blocked'
        else:
            ident=row['template'] if row else world.location_at(*cell)
            if not world.location(ident).war:reason='patrol_peaceful_location'
            else:
                occupied=tuple(c for door in row.get('door_designs',[]) if door['side']=='internal' for c in door['cells']) if row else occupied_at(key,ident,doc)
                value=population(key,ident,occupied,plan['catalog_version'])
                if value:
                    if row:
                        # Interior portal hexes are reserved geometry, not
                        # original NPCs. Keep them clear without making the
                        # preview mistake them for a missing native roster.
                        value['reserved']=value['occupied']
                        value['occupied']=[]
                    value['instance_key']=row.get('instance_key','boundary:'+key) if row else travel.room_key(world.location(ident),*cell)
                    cells[key]=value;continue
                reason='patrol_no_safe_area'
        excluded[key]=reason
    return dict(cells=cells,excluded=excluded,types=[dict(type_id=i,level=l) for i,l in TYPES],
        summary=dict(marked=len(layers.get('patrol',set())),locations=len(cells),mobs=sum(len(r['positions']) for r in cells.values()),
                     excluded=dict(Counter(excluded.values()))),
        rules=dict(exit_distance=EXIT_DISTANCE,mob_distance=MOB_DISTANCE,object_clearance=OBJECT_CLEARANCE,max_mobs=MAX_MOBS))


def validate_overrides(rows,plan,previous=None):
    if not isinstance(rows,dict) or len(rows)>10000:raise ValueError('Некорректные позиции патруля')
    result={};previous=previous or {}
    for key,row in rows.items():
        if key in previous and row==previous[key]:result[key]=deepcopy(row);continue
        base=plan.get('patrol_population',{}).get('cells',{}).get(key)
        if not isinstance(row,dict) or not base or row.get('template')!=base['template'] or row.get('signature')!=base['signature']:
            raise ValueError('Патруль или геометрия изменились — обнови переходы и спавны')
        positions=row.get('positions');h=habitat(base['template']);allowed=set(h['candidates'])
        if not isinstance(positions,list) or len(positions)!=len(base['positions']):raise ValueError('Перемещение не должно менять состав патруля')
        for i,cell in enumerate(positions):
            if type(cell) is not int or cell not in allowed:raise ValueError('Недопустимый гекс патруля: препятствие или точка входа рядом')
            if any(hex_steps(cell,other,h['width'])<MOB_DISTANCE for other in positions[:i]+base['occupied']+base.get('reserved',[])):
                raise ValueError('Гекс слишком близко к другому обитателю; нужно 12 гексов')
        result[key]=dict(template=base['template'],signature=base['signature'],positions=list(positions))
    return result
