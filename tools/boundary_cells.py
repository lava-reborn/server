"""Current cell inspection and draft-only per-cell inhabitant positions."""
import hashlib,json
from pathlib import Path
from functools import lru_cache
import boundary_planner as p


@lru_cache(maxsize=1)
def assets_version():
    root=Path(__file__).resolve().parent
    return hashlib.sha256(b''.join((root/name).read_bytes() for name in
        ('map_editor_preview.py','boundary_cells.py','boundary_art.py','location_art.py','boundary_manual.py','boundary_selection.py','boundary_planner.py','boundary_crocodiles.py','boundary_patrols.py','boundary_tunnels.py','boundary_repair.py','boundary_complexes.py'))).hexdigest()[:16]


@lru_cache(maxsize=2048)
def _art_key(path,mtime,size):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def art_key(ident):
    import world
    source=Path(world.path_for(ident));stat=source.stat()
    return _art_key(str(source),stat.st_mtime_ns,stat.st_size)


def valid_template(ident,bounds):
    import world
    if type(ident) is not int or ident<0:raise ValueError('Некорректная локация')
    if ident<world.NEW_ID_LIMIT and world.static_path(ident):return ident
    if ident>>26==0 and p.inside(world.unpack(ident),bounds):return ident
    raise ValueError('Локация вне карты')


@lru_cache(maxsize=8192)
def inhabitants(ident):
    import world,rooms,names
    room=rooms.Room(world.location(ident),rooms.IdAllocator(),world.mob_types())
    return tuple(dict(cell=n.cell,type=n.type_id,root=n.root,name=names.text(n.type_id).replace('<br>',' / '))
                 for n in room.npcs.values())


def signature(ident):
    return hashlib.sha256(json.dumps(inhabitants(ident),sort_keys=True).encode()).hexdigest()


def validate_overrides(rows,bounds,locations=None):
    import world
    if not isinstance(rows,dict) or len(rows)>10000:raise ValueError('Некорректный черновик мобов')
    result={}
    for key,row in rows.items():
        cell=p.point(key)
        if not p.inside(cell,bounds):raise ValueError('Клетка мобов вне карты')
        original=world.location_at(*cell);planned=(locations or {}).get(cell,original)
        if not isinstance(row,dict):raise ValueError('Некорректная позиция обитателя')
        ident=row.get('location_id')
        if ident not in (original,planned):raise ValueError('Состав текущей или предложенной локации изменился')
        if not isinstance(row,dict) or row.get('location_id')!=ident or row.get('spawn_signature')!=signature(ident):
            raise ValueError('Состав мобов или текущая локация изменились — обнови предпросмотр')
        positions=row.get('positions');base=inhabitants(ident);g=p.geometry(ident);loc=g['loc']
        if not isinstance(positions,list) or len(positions)!=len(base):raise ValueError('Нельзя менять состав мобов этим инструментом')
        for i,target in enumerate(positions):
            if type(target) is int and target==base[i]['cell']:continue
            if type(target) is not int or target not in g['components']:raise ValueError('Моб не может стоять на препятствии или за краем карты')
            if target in set(loc.entries)|g['exits'].keys():raise ValueError('Не ставь моба на вход или выход локации')
            original=base[i]['cell'];source_component=g['components'].get(original)
            if source_component is not None and g['components'][target]!=source_component:
                raise ValueError('Моб не может оказаться в изолированном участке')
            if any(j!=i and other==target and not(base[j]['cell']==original==target) for j,other in enumerate(positions)):
                raise ValueError('Клетка занята другим мобом')
        result[key]=dict(location_id=ident,spawn_signature=row['spawn_signature'],positions=list(positions))
    return result


def cell_info(store,cell):
    import world,travel
    if not p.inside(cell,store.bounds):raise ValueError('Координаты вне карты')
    doc,layers,plan=store.inspection_context();key=p.cell_key(cell)
    ident=world.location_at(*cell);loc=world.location(ident);native=p.existing_profile(ident)
    spawns=[dict(row,index=i,source_cell=row['cell']) for i,row in enumerate(inhabitants(ident))]
    edited=doc.get('mob_overrides',{}).get(key)
    if edited and edited.get('location_id')==ident and edited.get('spawn_signature')==signature(ident):
        for row,target in zip(spawns,edited['positions']):row['cell']=target
    actual=dict(id=ident,art_key=art_key(ident),title=loc.title or 'Пустошь',name=loc.fn or loc.file,width=loc.width,height=loc.height,
        passable=world.passable(*cell),native_exits=sorted(native.exits),
        instance_key=travel.room_key(loc,*cell),spawns=spawns,spawn_signature=signature(ident))
    original=dict(actual)
    installed=(store.installed_world() if hasattr(store,'installed_world') else {}).get('cells',{}).get(key)
    if installed:
        import names
        template=installed['template'];target=world.location(template)
        actual.update(id=template,binding_id=installed['id'],installed_snapshot=True,art_key=art_key(template),
            title=target.title or 'Пустошь',name=target.fn or target.file,width=target.width,height=target.height,
            passable=True,native_exits=installed['allowed_exits'],instance_key='boundary:'+key,
            spawns=[dict(cell=c,type=t,root=world.entity_root(t,world.mob_types()[t][0]),name=names.text(t).replace('<br>',' / '),index=i,source_cell=c)
                    for i,(c,t) in enumerate(installed['spawns'])])
        if installed.get('crocodile'):actual['coastal']=dict(installed['crocodile'])
        guards=[c for c,t in installed['spawns'] if t==98]
        if guards:actual['patrol']=dict(positions=guards,occupied=[c for c,t in installed['spawns'] if t!=98])
    row=plan['placements'].get(key)
    preview=dict(row) if row else None
    if preview:
        target=world.location(preview['template'])
        preview.update(id=preview['template'],title='Побережье' if preview['kind']=='coast' else 'Скалы',
                       name=target.fn,width=target.width,height=target.height,spawns=[])
    binding=layers.get('_complex_bindings',{}).get(key)
    planned=None
    if binding and binding['role']=='masters':
        source=binding['source_location'];target=world.location(source);profile=p.existing_profile(source)
        planned=dict(id=source,art_key=art_key(source),title=target.title,name=target.fn,width=target.width,height=target.height,
            native_exits=sorted(profile.exits),spawns=[dict(r,index=i,source_cell=r['cell']) for i,r in enumerate(inhabitants(source))],
            spawn_signature=signature(source),instance_key=binding['instance_key'],source_location=source,planned_binding=True)
    if not binding and cell in layers.get('_retired_complex_sources',set()):
        source=world.pack(*cell);target=world.location(source);profile=p.existing_profile(source)
        planned=dict(id=source,art_key=art_key(source),title=target.title or 'Пустошь',name=target.fn,width=target.width,height=target.height,
            native_exits=sorted(profile.exits),spawns=[dict(r,index=i,source_cell=r['cell']) for i,r in enumerate(inhabitants(source))],
            spawn_signature=signature(source),planned_binding=True)
    neighbours={}
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            n=cell[0]+dx,cell[1]+dy
            if p.inside(n,store.bounds):
                ni=world.location_at(*n);nl=world.location(ni)
                neighbours[p.cell_key(n)]=dict(id=ni,title=nl.title or 'Пустошь',name=nl.fn or nl.file)
    return dict(cell=key,actual=actual,original=original,preview=preview,planned=planned,neighbours=neighbours,
        draft_passable=p.passable(layers,plan,cell),
        draft_exits=[s for s in p.STEP if p.can_step(layers,plan,cell,p.neighbour(cell,s),store.catalog)],
        draft_global_map_exit=key not in plan.get('tunnels',{}),draft_global_map_entry=(key not in plan.get('tunnels',{}) or bool(row and row.get('mountain_trail'))) and p.passable(layers,plan,cell),
        patrol=plan.get('patrol_population',{}).get('cells',{}).get(key),
        region=layers.get('_regions',{}).get(cell,'world'))
