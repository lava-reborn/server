"""Isolated map editor preview. No installation, publish or source-save route.

python -B tools/map_editor_preview.py --source SNAPSHOT --workspace OUTPUT_DIR
    --map-image CURRENT_MAP_PNG --port 8091

Only workspace/working.json can be saved. The original snapshot is read-only.
The game's terrain/configuration are never written; both editor ports share one draft.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import sys
import threading
import subprocess
import uuid
from functools import lru_cache
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'server'))
import boundary_planner as planner
from boundary_preview_page import PAGE


def public(plan):
    return {k:v for k,v in plan.items() if not k.startswith('_')}


class Store:
    def __init__(self,source,workspace,bounds,catalog,special,catalog_version='native',accessibility=None,policy=None,coastal_population=False,installed_world=None):
        self.source=Path(source).resolve();self.workspace=Path(workspace).resolve()
        self.path=self.workspace/'working.json';self.bounds=bounds
        if self.path==self.source or self.workspace==ROOT or ROOT/'data' in self.workspace.parents or self.workspace==ROOT/'data':
            raise ValueError('Нужна отдельная папка предпросмотра вне игровых данных')
        self.catalog=catalog;self.special=special;self.catalog_version=catalog_version;self.coastal_population=coastal_population
        self.installed_world_path=Path(installed_world) if installed_world else None;self._installed_world_cache=None
        self.lock=threading.RLock();self.art_render_lock=threading.Lock();self.cache={};self._inspection_cache=None;self.accessibility=accessibility;self.policy=policy
        self.workspace.mkdir(parents=True,exist_ok=True)
        if not self.path.exists():
            raw=self.source.read_bytes();doc=json.loads(raw)
            planner.normalise(doc,bounds)
            meta=dict(source=str(self.source),sha256=hashlib.sha256(raw).hexdigest())
            # Immutable copy and editable copy are separate files.
            with (self.workspace/'snapshot.json').open('xb') as f:f.write(raw)
            (self.workspace/'source-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            with self.path.open('xb') as f:f.write(raw)
        self.meta=json.loads((self.workspace/'source-info.json').read_text(encoding='utf-8'))

    def read(self):
        raw=self.path.read_bytes()
        return json.loads(raw),hashlib.sha256(raw).hexdigest()

    def installed_world(self):
        path=self.installed_world_path
        if path is None or not path.is_file():return {}
        stat=path.stat();stamp=(stat.st_mtime_ns,stat.st_size)
        if self._installed_world_cache is None or self._installed_world_cache[0]!=stamp:
            self._installed_world_cache=(stamp,json.loads(path.read_bytes()))
        return self._installed_world_cache[1]

    def layers(self,doc):
        layers=planner.normalise(doc,self.bounds)
        layers['_special']={**(self.policy.special if self.policy else {}),**self.special}
        if self.policy:self.policy.attach(layers)
        if doc.get('eden_inset')==1:
            from boundary_manual import eden_outer_ring
            from boundary_cells import inhabitants
            import world
            retired={c for c in eden_outer_ring(world.eden_map.CELL_TO_LOC)
                     if all(n['type']==1790 for n in inhabitants(world.eden_map.CELL_TO_LOC[c]))}
            layers['_retired_existing']=retired
            layers['_preserved_land']=layers.get('_preserved_land',set())-retired
        from boundary_complexes import project
        project(layers,layers['_special'])
        return layers

    def plan(self,layers,base=None,revision=None,edits=None,mob_overrides=None):
        from boundary_manual import generate,scene_edits
        if base is None:base,revision=self.read()
        if mob_overrides is None:mob_overrides=base.get('mob_overrides',{})
        if edits is None:edits=scene_edits(base,self.bounds)
        signature=(planner.fingerprint(layers,self.catalog_version),revision,json.dumps(edits,sort_keys=True),json.dumps(mob_overrides,sort_keys=True),bool(base.get('physical_boundary_audit')))
        with self.lock:
            if signature not in self.cache:
                special=layers['_special']
                value=generate(layers,self.catalog,special,base,self.catalog_version,edits)
                if self.coastal_population:
                    from boundary_crocodiles import build
                    value['coastal_population']=build(layers,value,special)
                else:value.pop('coastal_population',None)
                from boundary_complexes import links
                value['portal_links']=links(layers,value)
                from boundary_patrols import build
                value['patrol_population']=build(layers,value,{'mob_overrides':mob_overrides})
                value['issues'].extend(dict(cell=k,code=reason) for k,reason in value['patrol_population']['excluded'].items())
                value['summary']['unresolved']=len({r['cell'] for r in value['issues']})
                if len(self.cache)>=3:self.cache.pop(next(iter(self.cache)))
                self.cache[signature]=value
            # Engine traversal caches must not be shared between requests.
            return dict(public(self.cache[signature]))

    def inspection_context(self,with_revision=False):
        # A coordinate click must not parse and hash the entire map again.
        # Check the file stamp so externally saved drafts are still picked up.
        with self.lock:
            stat=self.path.stat();stamp=(stat.st_mtime_ns,stat.st_size)
            if self._inspection_cache is None or self._inspection_cache[0]!=stamp:
                doc,revision=self.read();layers=self.layers(doc);plan=self.plan(layers,doc,revision)
                # This traversal cache is immutable and safe to share between
                # coordinate requests of the same saved revision.
                planner.passable(layers,plan,(self.bounds[0],self.bounds[1]))
                self._inspection_cache=(stamp,doc,layers,plan,revision)
            _,doc,layers,plan,revision=self._inspection_cache
            result=(doc,layers,dict(plan))
            return (*result,revision) if with_revision else result

    def state(self):
        from boundary_cells import assets_version,art_key
        doc,layers,plan,revision=self.inspection_context(with_revision=True)
        return dict(**planner.document(layers),bounds=self.bounds,revision=revision,
            applied_game={'fingerprint':self.installed_world().get('draft_fingerprint')} if self.installed_world() else None,
            geometry=plan['input_fingerprint'],plan=public(plan),eden_inset=doc.get('eden_inset',0),
            source=self.meta,assets_revision=assets_version(),mode='isolated_preview',apply_supported=False,
            physical_boundary_audit=bool(doc.get('physical_boundary_audit')),
            mob_overrides=doc.get('mob_overrides',{}),coastal_mob_overrides=doc.get('coastal_mob_overrides',{}),patrol_mob_overrides=doc.get('patrol_mob_overrides',{}),scene_edits=doc.get('scene_edits',{}),manual_editing=True,
            accessibility=self.accessibility if self.accessibility
                and self.accessibility.get('snapshot_sha256')==self.meta['sha256']
                and self.accessibility.get('geometry')==plan['input_fingerprint'] else None,
            settlements={planner.cell_key(k):v for k,v in layers['_special'].items() if k not in layers.get('_retired_existing',set())},
            catalog={str(k):dict(kind=p.kind,name=p.name,art_key=art_key(k),closed=sorted(p.closed),exits=sorted(p.exits),width=p.width,height=p.height,edges={side:format(mask,'x') for side,mask in p.edges.items()}) for k,p in self.catalog.items()})

    def save(self,doc):
        if not all(k in doc for k in ('water','rocks','blocked','passable','overrides')):
            raise ValueError('Обновите страницу предпросмотра перед сохранением')
        current,_=self.read()
        doc={**doc,'eden_inset':current.get('eden_inset',0)}
        for field in ('patrol','tunnels','mountain_trails','mountain_complexes'):
            if field not in doc:doc[field]=current.get(field,{} if field=='mountain_complexes' else False if field=='mountain_trails' else [])
        layers=self.layers(doc)
        from boundary_manual import scene_edits
        edits=scene_edits(doc,self.bounds) if 'scene_edits' in doc else None
        from boundary_cells import validate_overrides
        mob_overrides=validate_overrides(doc['mob_overrides'],self.bounds,layers['_special']) if 'mob_overrides' in doc else None
        from boundary_crocodiles import saved_overrides
        coastal_overrides=saved_overrides(doc['coastal_mob_overrides'],self.bounds,self.catalog_version,current.get('coastal_mob_overrides',{})) if 'coastal_mob_overrides' in doc else None
        with self.lock:
            old,revision=self.read()
            if revision!=doc.get('revision'):
                return 409,dict(error='Копия изменена в другой вкладке. Отметки на экране сохранены; запись остановлена.')
            if edits is None:edits=scene_edits(old,self.bounds)
            if doc.get('physical_boundary_audit') is True:old['physical_boundary_audit']=True
            plan=self.plan(layers,old,revision,edits,mob_overrides)
            from boundary_patrols import validate_overrides as validate_patrols
            patrol_overrides=validate_patrols(doc['patrol_mob_overrides'],plan,old.get('patrol_mob_overrides',{})) if 'patrol_mob_overrides' in doc else None
            old.update(planner.document(layers));old['preview_only']=True;old['scene_edits']=edits
            if mob_overrides is not None:old['mob_overrides']=mob_overrides
            if coastal_overrides is not None:old['coastal_mob_overrides']=coastal_overrides
            if patrol_overrides is not None:old['patrol_mob_overrides']=patrol_overrides
            # Recomputed server-side; browser-supplied plan/approval is never trusted.
            old['boundary_preview']=public(plan)
            raw=(json.dumps(old,ensure_ascii=False,indent=1)+'\n').encode('utf-8')
            temp=self.workspace/('working-'+uuid.uuid4().hex+'.tmp')
            try:
                with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                os.replace(temp,self.path);self._inspection_cache=None
            finally:
                if temp.exists():temp.unlink()
            return 200,dict(saved=True,revision=hashlib.sha256(raw).hexdigest(),geometry=planner.fingerprint(layers,self.catalog_version),plan=public(plan))


@lru_cache(maxsize=64)
def template_svg(template,grid=True,background=True,collision=True):
    import lavaloc as L
    g=planner.geometry(template);loc=g['loc'];width=loc.width;height=loc.height
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width*40} {height*15}" width="{width*40}" height="{height*15}">',
           ('<rect width="100%" height="100%" fill="#ddc99c"/>' if background else '')]
    def polygon(c,colour):
        points=' '.join('%g,%g'%xy for xy in L.hex_points(c%width,c//width))
        if collision:parts.append(f'<polygon points="{points}" fill="{colour}" fill-opacity="{1 if background else .48}"/>')
    for c in sorted(loc.obstacles):
        if 0<=c<width*height:polygon(c,'#544d43')
    for c in g['entries']:
        if g['components'][c]==g['main']:polygon(c,'#148444')
    for c in g['exits']:
        if g['components'][c]==g['main']:polygon(c,'#2d77ce')
    if grid:
        parts.append('<defs><pattern id="hexGrid" width="40" height="30" patternUnits="userSpaceOnUse">')
        for cx,cy in ((0,0),(40,0),(20,15),(0,30),(40,30)):
            points=' '.join('%g,%g'%(cx+dx,cy+dy) for dx,dy in L.HEX)
            parts.append(f'<polygon points="{points}" fill="none" stroke="#fff" stroke-opacity=".4" stroke-width="1.5"/>')
        parts.append('</pattern></defs><rect width="100%" height="100%" fill="url(#hexGrid)"/>')
    parts.append('</svg>');return ''.join(parts)


def handler(store,map_image,art_dir=None,art_python=None):
    render_lock=store.art_render_lock
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data,code=200,ctype='application/json; charset=utf-8',cacheable=False):
            if not isinstance(data,(str,bytes)):data=json.dumps(data,ensure_ascii=False)
            if isinstance(data,str):data=data.encode('utf-8')
            cache='no-store';etag=None
            if cacheable and code==200:
                etag='"'+hashlib.sha256(data).hexdigest()+'"'
                cache='private, max-age=86400, immutable' if parse_qs(urlsplit(self.path).query).get('v') else 'private, no-cache'
                if self.headers.get('If-None-Match')==etag:code=304;data=b''
            try:
                self.send_response(code);self.send_header('Content-Type',ctype)
                if code!=304:self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control',cache)
                if etag:self.send_header('ETag',etag)
                self.end_headers();self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        def do_GET(self):
            path=urlsplit(self.path)
            try:
                if path.path=='/':self.send(PAGE,ctype='text/html; charset=utf-8')
                elif path.path=='/state':self.send(store.state())
                elif path.path=='/cell':
                    from boundary_cells import cell_info
                    query=parse_qs(path.query);cell=(int(query.get('x',[''])[0]),int(query.get('y',[''])[0]))
                    self.send(cell_info(store,cell))
                elif path.path=='/map.png':self.send(Path(map_image).read_bytes(),ctype='image/png')
                elif path.path in ('/mob-sprite-info','/mob-sprite'):
                    import world
                    ident=int(parse_qs(path.query).get('type',['-1'])[0])
                    if ident not in world.mob_types():raise ValueError('Нет такого обитателя')
                    metadata=store.workspace/('mob-%d.json'%ident);picture=metadata.with_suffix('.png')
                    if not metadata.is_file() or not picture.is_file():
                        with render_lock:
                            if not metadata.is_file() or not picture.is_file():
                                if not art_python:raise ValueError('Нужен графический runtime редактора')
                                result=subprocess.run([str(art_python),'-X','utf8','-B',str(HERE/'boundary_art.py'),'--mob',str(ident),'--out',str(metadata)],cwd=ROOT,capture_output=True,timeout=60)
                                if result.returncode:raise ValueError('Модель обитателя недоступна')
                    if path.path=='/mob-sprite-info':self.send(dict(**json.loads(metadata.read_text(encoding='utf-8')),url='/mob-sprite?type=%d&v=%d'%(ident,metadata.stat().st_mtime_ns)))
                    else:self.send(picture.read_bytes(),ctype='image/png',cacheable=True)
                elif path.path=='/template':
                    template=int(parse_qs(path.query).get('id',['-1'])[0])
                    from boundary_cells import valid_template
                    valid_template(template,store.bounds)
                    self.send(template_svg(template,parse_qs(path.query).get('grid',['1'])[0]!='0',parse_qs(path.query).get('background',['1'])[0]!='0',parse_qs(path.query).get('geometry',['1'])[0]!='0'),ctype='image/svg+xml',cacheable=True)
                elif path.path=='/art':
                    template=int(parse_qs(path.query).get('id',['-1'])[0])
                    image=Path(art_dir)/('template-%d.png'%template) if art_dir else None
                    if image is not None and not image.is_file():image=Path(art_dir)/('coast-%d.png'%template)
                    from boundary_cells import valid_template
                    valid_template(template,store.bounds)
                    if (image is None or not image.is_file()) and art_python:
                        import world
                        source=Path(world.path_for(template));digest=hashlib.sha256(source.read_bytes()).hexdigest()
                        image=store.workspace/('art-'+digest+'.png')
                        if not image.is_file():
                            with render_lock:
                                if not image.is_file():
                                    temporary=image.with_name(image.stem+'-'+uuid.uuid4().hex+'.tmp.png')
                                    try:
                                        result=subprocess.run([str(art_python),'-X','utf8','-B',str(HERE/'location_art.py'),'render',str(source),'-o',str(temporary),'--scale','0.3'],cwd=ROOT,capture_output=True,timeout=60)
                                        if result.returncode:raise ValueError('Изображение недоступно; родная геометрия показана отдельно')
                                        os.replace(temporary,image)
                                    finally:
                                        if temporary.exists():temporary.unlink()
                    if image is None or not image.is_file():
                        self.send(dict(error='Изображение не подготовлено; доступна схема геометрии'),404)
                    else:self.send(image.read_bytes(),ctype='image/png',cacheable=True)
                else:self.send(dict(error='Нет такой страницы'),404)
            except (ValueError,KeyError) as error:self.send(dict(error=str(error)),400)
            except subprocess.SubprocessError:self.send(dict(error='Превышено время подготовки изображения; повтори запрос'),503)
            except OSError:self.send(dict(error='Не удалось прочитать файл предпросмотра'),500)
        def do_POST(self):
            path=urlsplit(self.path).path
            if path not in ('/calculate','/save','/route','/local-probe','/validate-mobs','/validate-coastal-mobs','/validate-patrol-mobs','/outline-walls','/repair-boundaries'):
                self.send(dict(error='Только предпросмотр. Применения в игру нет.'),404);return
            try:
                if self.headers.get_content_type()!='application/json':raise ValueError('Нужен JSON')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16*1024*1024:raise ValueError('Некорректный размер запроса')
                doc=json.loads(self.rfile.read(size))
                if not isinstance(doc,dict):raise ValueError('Некорректный запрос')
                if path=='/save':code,result=store.save(doc);self.send(result,code);return
                if path=='/validate-coastal-mobs':
                    if not store.coastal_population:raise ValueError('Прибрежные спавны не включены в предпросмотре')
                    from boundary_crocodiles import validate_overrides
                    self.send(validate_overrides(doc.get('coastal_mob_overrides'),store.bounds,store.catalog_version));return
                if path=='/validate-mobs':
                    from boundary_cells import validate_overrides
                    current_layers=store.inspection_context()[1]
                    self.send(validate_overrides(doc.get('mob_overrides'),store.bounds,current_layers['_special']));return
                if path=='/local-probe':
                    template=doc.get('template');start=doc.get('start');end=doc.get('end')
                    from boundary_cells import valid_template
                    valid_template(template,store.bounds)
                    if type(start) is not int or type(end) is not int:
                        raise ValueError('Укажите шаблон и номера гексов')
                    self.send(planner.local_probe(template,start,end));return
                from boundary_manual import scene_edits
                current,_=store.read()
                for field in ('patrol','tunnels','mountain_trails','mountain_complexes'):
                    if field not in doc:doc[field]=current.get(field,{} if field=='mountain_complexes' else False if field=='mountain_trails' else [])
                layers=store.layers(doc);plan=store.plan(layers,edits=scene_edits(doc,store.bounds),mob_overrides=doc.get('mob_overrides'))
                if path=='/validate-patrol-mobs':
                    from boundary_patrols import validate_overrides
                    self.send(validate_overrides(doc.get('patrol_mob_overrides'),plan));return
                if path=='/repair-boundaries':
                    from boundary_repair import repair
                    special=layers['_special']
                    result=repair(layers,store.catalog,special,{**current,**doc},store.catalog_version,
                                  scene_edits(doc,store.bounds),initial=plan)
                    repaired=store.layers(result['draft'])
                    if store.coastal_population:
                        from boundary_crocodiles import build
                        result['plan']['coastal_population']=build(repaired,result['plan'],store.special)
                    from boundary_patrols import build as build_patrols
                    result['plan']['patrol_population']=build_patrols(repaired,result['plan'],doc)
                    result['plan']['issues'].extend(dict(cell=k,code=reason) for k,reason in result['plan']['patrol_population']['excluded'].items())
                    result['plan']['summary']['unresolved']=len({r['cell'] for r in result['plan']['issues']})
                    result['plan']=public(result['plan'])
                    result['draft']['boundary_preview']=result['plan']
                    self.send(result);return
                if path=='/outline-walls':
                    from boundary_manual import outline_walls
                    base,_=store.read();special=layers['_special']
                    result=outline_walls(layers,store.catalog,special,base,store.catalog_version,scene_edits(doc,store.bounds))
                    if store.coastal_population:
                        from boundary_crocodiles import build
                        for key,row in result['additions'].items():layers['coast' if row['kind']=='coast' else 'rocks'].add(planner.point(key))
                        result['plan']['coastal_population']=build(layers,result['plan'],store.special)
                    from boundary_patrols import build as build_patrols
                    result['plan']['patrol_population']=build_patrols(layers,result['plan'],doc)
                    result['plan']['issues'].extend(dict(cell=k,code=reason) for k,reason in result['plan']['patrol_population']['excluded'].items())
                    result['plan']['summary']['unresolved']=len({r['cell'] for r in result['plan']['issues']})
                    result['plan']=public(result['plan'])
                    self.send(result)
                elif path=='/calculate':self.send(public(plan))
                else:
                    start=planner.point(doc.get('start'));end=planner.point(doc.get('end'))
                    result=planner.route(layers,plan,start,end,store.catalog)
                    result['geometry']=planner.fingerprint(layers,store.catalog_version)
                    self.send(result)
            except (ValueError,TypeError,KeyError) as error:self.send(dict(error=str(error)),400)
            except OSError:self.send(dict(error='Не удалось записать отдельную копию'),500)
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--art-python',type=Path,default=Path(os.environ.get('LAVA_EDITOR_ART_PYTHON') or sys.executable),help='Existing Python runtime with Pillow for native artwork')
    seed=ROOT/'data'/'boundary_editor_draft.json'
    parser.add_argument('--source',type=Path,default=seed if seed.is_file() else ROOT/'data'/'terrain_verified.json')
    parser.add_argument('--workspace',type=Path,default=ROOT/'outputs'/'boundary-editor')
    parser.add_argument('--map-image',type=Path,default=ROOT/'data'/'map_editor_base.png')
    parser.add_argument('--art-dir',type=Path)
    parser.add_argument('--port',type=int,default=8091)
    parser.add_argument('--access-report',type=Path)
    parser.add_argument('--coastal-population',action=argparse.BooleanOptionalAction,default=True,help='Preview regional crocodiles without installing game bindings')
    parser.add_argument('--alias-port',type=int,action='append',default=[])
    args=parser.parse_args()
    ports=[args.port,*args.alias_port]
    if len(set(ports))!=len(ports) or any(not 1<=port<=65535 for port in ports):raise ValueError('Неверные порты редактора')
    if not args.map_image.is_file():raise ValueError('Нужна готовая актуальная карта')
    # Planning keeps the original binding baseline; the installed manifest is
    # read separately for the actual-game comparison in the cell inspector.
    os.environ['LAVA_BOUNDARY_WORLD']='off'
    import world
    catalog,version=planner.native_catalog()
    bounds=world.MAP_X[0],world.MAP_Y[0],world.MAP_X[1],world.MAP_Y[1]
    special=dict(world.settlements());special.update(world.eden_map.CELL_TO_LOC)
    version=hashlib.sha256((version+repr(sorted(special.items()))).encode()).hexdigest()
    accessibility=json.loads(args.access_report.read_text(encoding='utf-8')) if args.access_report else None
    from boundary_policy import native_policy
    store=Store(args.source,args.workspace,bounds,catalog,special,version,accessibility,native_policy(),coastal_population=args.coastal_population,installed_world=ROOT/'data/boundary_world.json')
    servers=[]
    try:
        for port in ports:servers.append(ThreadingHTTPServer(('127.0.0.1',port),handler(store,args.map_image,args.art_dir,args.art_python)))
    except OSError:
        for opened in servers:opened.server_close()
        raise
    server=servers[0]
    for alias in servers[1:]:threading.Thread(target=alias.serve_forever,daemon=True).start()
    print('Предпросмотр: http://127.0.0.1:%d/; сохраняет только %s'%(args.port,store.path),flush=True)
    server.serve_forever()


if __name__=='__main__':main()
