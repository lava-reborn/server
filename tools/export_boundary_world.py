"""Explicit draft -> game manifest export, with no live-install side effects."""
import argparse,hashlib,json,os
from pathlib import Path
os.environ['LAVA_BOUNDARY_WORLD']='off'
import boundary_planner as p
from boundary_policy import native_policy
from boundary_cells import inhabitants,signature
from map_editor_preview import Store
import world,boundary_world,travel

def export(store,doc,prepared=None):
    layers=store.layers(doc);plan=prepared if prepared is not None else store.plan(layers,doc,hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest())
    if plan['input_fingerprint']!=p.fingerprint(layers,store.catalog_version):
        raise ValueError('Prepared plan belongs to another draft or geometry')
    if plan['issues']:raise ValueError('Resolve draft conflicts before installation: '+repr(plan['issues'][:10]))
    p.passable(layers,plan,(store.bounds[0],store.bounds[1]))
    cells={};assigned=plan['placements'];bindings=layers['_complex_bindings'];special=layers['_special']
    patrols=plan['patrol_population']['cells'];crocs=plan['coastal_population']['cells']
    keys=set(assigned)|set(bindings)|set(patrols)|set(doc.get('mob_overrides',{}))
    for key in sorted(keys):
        cell=p.point(key);placement=assigned.get(key);binding=bindings.get(key)
        if not p.passable(layers,plan,cell):continue
        source=special.get(cell,world.location_at(*cell))
        template=placement['template'] if placement else source
        # Keep existing quest/portal identity. All independent new cells use
        # their own packed coordinate, recognised via loc_defs by the client.
        original=world.settlements().get(cell,world.eden_map.CELL_TO_LOC.get(cell))
        ident=original if original is not None and not binding else world.pack(*cell)
        retiring_palms=cell in layers.get('_retired_existing',set()) and all(n['type']==1790 for n in inhabitants(source))
        if placement and inhabitants(source) and not placement.get('preserve_source_binding') and not retiring_palms:
            raise ValueError('Boundary would replace inhabitants at '+key)
        base=[] if placement else [dict(r) for r in inhabitants(template)]
        patch=doc.get('mob_overrides',{}).get(key)
        if patch and patch.get('location_id')==template and patch.get('spawn_signature')==signature(template):
            for actor,target in zip(base,patch['positions']):actor['cell']=target
        spawns=[(r['cell'],r['type']) for r in base]
        patrol=patrols.get(key);croc=crocs.get(key)
        if patrol:
            patch=doc.get('patrol_mob_overrides',{}).get(key,{})
            positions=patch.get('positions') if patch.get('signature')==patrol['signature'] else patrol['positions']
            spawns.extend(zip(positions,patrol['type_ids']))
        if croc:
            patch=doc.get('coastal_mob_overrides',{}).get(key,{})
            positions=patch.get('positions') if patch.get('signature')==croc['signature'] else croc['positions']
            spawns.extend((c,croc['type_id']) for c in positions)
        exits=[s for s in p.STEP if p.can_step(layers,plan,cell,p.neighbour(cell,s),store.catalog)]
        record=dict(id=ident,template=template,source_location=source,spawns=spawns,allowed_exits=exits,
                    boundary=bool(placement),no_map=bool(placement and placement.get('tunnel')),portals={})
        record['global_entry']=not record['no_map'] or bool(placement and placement.get('mountain_trail'))
        if croc:record['crocodile']={k:croc[k] for k in ('type_id','level','city','xp_multiplier','loot')}
        if not placement:
            record['source_doors']={s:travel.door(source,s) for s in 'ab' if travel.door(source,s)}
            # Scheduled/held-out native actors are not visible in Room.npcs,
            # but the scheduler still needs their original XML declarations.
            import events
            scheduled={t for rec in events.table().spawns+events.table().held_out if rec.get('loc')==source for t in rec.get('types',[])}
            record['scheduled_spawns']=[(c,t) for c,t in world.location(source).spawns if t in scheduled and (c,t) not in spawns]
        cells[key]=record
    for link in plan['portal_links']:
        if not link['enabled']:continue
        record=cells[link['cell']];target=cells.get(link['target_cell'])
        portal_key=link['source_side'] if link.get('internal') else 'N'
        record['portals'][portal_key]=dict(side=link['source_side'],target_id=target['id'] if target else link['target_location'],
            target_cell=list(p.point(link['target_cell'])),arrival_hex=link['arrival_hex'])
        if link.get('internal'):record['portals'][portal_key]['source_hexes']=link['source_hexes']
    for key,record in cells.items():
        raw=boundary_world.xml_bytes(record,Path(world.source_path_for(record['template'])).read_bytes())
        record.update(md5=hashlib.md5(raw).hexdigest(),size=len(raw))
    result=dict(version=1,draft_fingerprint=plan['input_fingerprint'],cells=cells,
        blocked=sorted(map(p.cell_key,plan['_blocked'])),regions=plan.get('isolated_regions',{}),
        retired=plan.get('retired_existing',[]),summary=dict(plan['summary'],instances=len(cells),
            patrol=plan['patrol_population']['summary'],crocodiles=plan['coastal_population']['summary']))
    from boundary_complexes import GROUPS
    relocated={}
    for city,(x,y) in layers.get('mountain_complexes',{}).items():
        group=GROUPS[city]
        if all(layers['_special'].get(c)==group['master'] for c in ((x-1,y+5),(x+1,y+5))):
            for ident in (*group['portals'],group['master']):
                relocated[str(ident)]=list(min(c for c,i in layers['_special'].items() if i==ident))
    if relocated:result['relocated_sources']=relocated
    return result,plan

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--draft',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();catalog,version=p.native_catalog();special={**world.settlements(),**world.eden_map.CELL_TO_LOC}
    version=hashlib.sha256((version+repr(sorted(special.items()))).encode()).hexdigest()
    bounds=world.MAP_X[0],world.MAP_Y[0],world.MAP_X[1],world.MAP_Y[1]
    store=Store(args.draft,args.out.parent/'export-check',bounds,catalog,special,version,policy=native_policy(),coastal_population=True)
    doc=json.loads(args.draft.read_bytes());manifest,plan=export(store,doc)
    args.out.write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(manifest['summary'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
