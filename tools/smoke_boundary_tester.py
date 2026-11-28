"""Replay real local-client frames against the installed tester on a disposable DB."""
import argparse,hashlib,json,os,socket,subprocess,sys,threading,time,urllib.request
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tester',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    target=args.tester.resolve();args.out.mkdir(exist_ok=True);db=args.out/'smoke.sqlite'
    os.environ.update(LAVA_DB=str(db),LAVA_RES=str(target/'res'),LAVA_BOUNDARY_WORLD=str(target/'data/boundary_world.json'),LAVA_HTTP_RES='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    sys.path.insert(0,str(target/'server'))
    import accounts,world,travel,boundary_world as bw,mobs,coasts,rooms,combat
    assert str(target).lower() in str(Path(world.__file__).resolve()).lower()
    store=accounts.Store(str(db));scenarios=[];chosen=set()
    keys=['6016,1742','6211,1945','5908,2001','6016,1743','6211,1946','6015,1747','6210,1950']
    for key,record in bw.manifest()['cells'].items():
        city=record.get('crocodile',{}).get('city')
        if city and city not in chosen:chosen.add(city);keys.append(key)
    for n,key in enumerate(keys):
        record=bw.manifest()['cells'].get(key) or dict(id=world.location_at(*map(int,key.split(','))))
        loc=world.location(record['id']);exits=[(c,s) for c,s in travel.exit_sides(loc).items() if c not in loc.obstacles]
        pos,side=next((c,s) for c,s in exits if s in travel.SIDES)
        name='boundary-smoke-'+str(n);password='disposable-local-fixture';aid,_=store.register(name,password);cid,_=store.create_character(aid,'Boundary'+str(n),0,'1')
        x,y=map(int,key.split(','));store.save_position(cid,loc.id,pos,x,y,False)
        scenarios.append(dict(key=key,id=loc.id,side=side,pos=pos,credential=accounts.credential(name,password)))
    store.close()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=dict(os.environ,LAVA_PORT=str(port),LAVA_HOST='127.0.0.1',LAVA_POLICY_PORT='0',LAVA_CHEATS='1')
    logpath=args.out/'server.log';log=logpath.open('w',encoding='utf-8');hidden=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    proc=subprocess.Popen([sys.executable,'-B','-u',str(target/'server/server.py')],cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=hidden)
    results=[]
    class Client:
        def __init__(self):self.sock=socket.create_connection(('127.0.0.1',port),1);self.buf=b''
        def send(self,text):self.sock.sendall(text.encode()+b'\0')
        def frames(self):
            self.sock.settimeout(.4);end=time.monotonic()+2;parts=[]
            while time.monotonic()<end:
                try:data=self.sock.recv(65536)
                except socket.timeout:break
                if not data:break
                self.buf+=data
            chunks=self.buf.split(b'\0');self.buf=chunks.pop()
            return [p.decode() for p in chunks if p]
    try:
        deadline=time.monotonic()+90
        while True:
            if proc.poll() is not None:raise RuntimeError('Installed server failed: '+logpath.read_text(encoding='utf-8')[-3000:])
            try:
                with socket.create_connection(('127.0.0.1',port),.2):break
            except OSError:
                if time.monotonic()>deadline:raise RuntimeError('Installed server startup timeout')
                time.sleep(.15)
        for rec in scenarios:
            c=Client();c.send('hello;minor=2;major=0;');c.send('login;hash=@'+rec['credential']+'@;');frames=c.frames()
            assert any(f.startswith('accountInfo;') for f in frames),frames
            c.send('selPers;num=0;');frames=c.frames();assert any(f.startswith('lcall;id='+str(rec['id'])+';') for f in frames),frames
            c.send('lenter;accept=1;');frames=c.frames();assert any(f.startswith('lenter;') for f in frames),frames
            expected=travel.plan_exit(world.location(rec['id']),rec['pos'],*map(int,rec['key'].split(',')))
            c.send('chWorld;to=1;');frames=c.frames()
            assert any(f.startswith('lcall;id='+str(expected.loc_id)+';') for f in frames),(rec['key'],frames)
            c.send('lenter;accept=1;');frames=c.frames();assert any(f.startswith('lenter;') for f in frames),frames
            c.send('logout;');c.sock.close();results.append(dict(cell=rec['key'],destination=expected.loc_id,arrival=expected.pos));print('Socket entry/exit OK:',rec['key'],flush=True)
        # Serve the exact installed HTTP resource route; no launcher or user DB.
        import bootstrap_http as web
        from http.server import ThreadingHTTPServer
        http=ThreadingHTTPServer(('127.0.0.1',0),web.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            origin='http://127.0.0.1:'+str(http.server_address[1])+'/res/'
            with urllib.request.urlopen(origin+'xml/loc_defs.xml') as r:defs=r.read()
            for rec in scenarios:
                ident=rec['id'];record=bw.row(ident)
                assert ('locations/static/%d.xml'%ident).encode() in defs
                with urllib.request.urlopen(origin+'locations/static/%d.xml'%ident) as r:raw=r.read()
                expected=record['md5'] if record else hashlib.md5(Path(world.source_path_for(ident)).read_bytes()).hexdigest()
                assert hashlib.md5(raw).hexdigest()==expected
            for resource in ('locations/libs/Mountains.swf','locations/libs/Sides.swf'):
                with urllib.request.urlopen(origin+resource) as r:assert r.read(3) in (b'FWS',b'CWS',b'ZWS')
        finally:http.shutdown();http.server_close();thread.join()
        report=dict(installed_package=str(target),socket_cases=results,resources_verified=True,user_database_used=False)
        (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(socket_cases=len(results),resources_verified=True),ensure_ascii=False),flush=True)
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()
    assert 'Traceback' not in logpath.read_text(encoding='utf-8'),logpath

if __name__=='__main__':main()
