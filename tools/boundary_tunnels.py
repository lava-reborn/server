"""A reversible corridor overlay, separate from the owner's terrain marks."""
from copy import deepcopy
import boundary_planner as p

TEMPLATE=6
MOUNTAIN_ENTRIES={162:'MP_Enter1',598:'MP_Enter1',163:'MP_Enter2',53:'MP_Enter3',623:'MP_Enter3'}
ENTRY_APPROACH={162:'S',598:'N',163:'S',53:'N',623:'S'}


def mountain_entry(layers,cell,special):
    return bool(layers.get('mountain_trails') and special.get(cell) in MOUNTAIN_ENTRIES)


def restore(rows):
    result={}
    for key,row in rows.items():
        if row.get('tunnel'):
            if row.get('tunnel_underlay') is not None:result[key]=deepcopy(row['tunnel_underlay'])
        else:result[key]=row
    return result


def install(layers,rows,catalog,special,generated):
    issues=[];active={}
    for cell in sorted(layers.get('tunnels',set())):
        key=p.cell_key(cell)
        if cell in layers['water']|layers['walls']|layers['coast'] or rows.get(key,{}).get('kind')=='coast':
            issues.append(dict(cell=key,code='tunnel_terrain_conflict'));continue
        is_entry=mountain_entry(layers,cell,special)
        if cell in special and cell not in layers.get('_retired_existing',set()) and not is_entry:
            issues.append(dict(cell=key,code='tunnel_existing_location',existing=special[cell]));continue
        if TEMPLATE not in catalog or catalog[TEMPLATE].closed!=frozenset('EW') or catalog[TEMPLATE].exits!=set('NS'):
            issues.append(dict(cell=key,code='tunnel_template_unavailable'));continue
        underlay=deepcopy(rows.get(key))
        rows[key]=dict(template=TEMPLATE,kind='rock',tunnel=True,tunnel_underlay=underlay,
                       tunnel_generated_wall=cell in generated,global_map_exit=False,global_map_entry=False,manual=True)
        if is_entry:
            import travel
            ident=special[cell]
            rows[key].update(mountain_trail=True,source_location=ident,preserve_source_binding=True,
                             trail_family=MOUNTAIN_ENTRIES[ident],source_doors={s:deepcopy(travel.door(ident,s)) for s in 'ab' if travel.door(ident,s)})
            g=p.geometry(TEMPLATE);portal_side=p.OPPOSITE[ENTRY_APPROACH[ident]]
            rows[key]['door_designs']=[dict(source_side=s,target_loc_id=door.get('target_loc_id'),side=portal_side,
                cells=sorted(c for c,side in g['exits'].items() if side==portal_side and g['components'].get(c)==g['main']))
                for s,door in rows[key]['source_doors'].items()]
        generated.discard(cell)
        active[key]=dict(template=TEMPLATE,global_map_exit=False,global_map_entry=False,exit_sides=['N','S'])
        if is_entry:active[key].update(source_location=special[cell],trail_family=MOUNTAIN_ENTRIES[special[cell]])
    return active,issues
