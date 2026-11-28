"""Isolated persistence, HTTP boundaries and preservation of the source editor."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch,Mock
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import map_editor_preview as editor
import boundary_planner as planner
from test_boundary_planner import catalogue
from testkit import run_cases


class PreviewEditor(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='boundary-preview-')
        self.root=Path(self.tmp.name);self.source=self.root/'user-draft.json'
        self.original={'_':'keep user metadata','water':['5,5'],'rocks':[],
                       'blocked':['5,5','1,1'],'passable':[],'opacity':70}
        self.source.write_text(json.dumps(self.original),encoding='utf-8');self.raw=self.source.read_bytes()
        self.store=editor.Store(self.source,self.root/'separate',(0,0,10,10),catalogue(),{})
    def tearDown(self):self.tmp.cleanup()
    def payload(self):
        state=self.store.state()
        return {k:state[k] for k in ('water','rocks','blocked','passable','overrides','opacity','revision')}

    def test_copy_is_independent_and_source_remains_byte_identical(self):
        data=self.payload();data['water'].append('5,6');data['blocked'].append('5,6')
        self.assertEqual(self.store.save(data)[0],200)
        self.assertEqual(self.source.read_bytes(),self.raw)
        self.assertEqual((self.store.workspace/'snapshot.json').read_bytes(),self.raw)
        saved,revision=self.store.read();self.assertIn('5,6',saved['water'])
        self.assertEqual(saved['_'],'keep user metadata')

    def test_save_does_not_generate_walls_or_rebuild_neighbouring_rocks(self):
        data=self.payload();data['rocks']=['%d,%d'%(x,y) for x in range(5,11) for y in range(11)]
        data['water']=[];data['blocked']=data['rocks']+['1,1']
        self.store.save(data);doc,revision=self.store.read()
        self.assertIn('7,5',doc['rocks'])
        self.assertEqual(doc['boundary_preview']['generated_walls'],[])
        self.assertEqual(set(doc['boundary_preview']['placements']),set(data['rocks']))
        normal=self.store.layers(doc);self.assertEqual(normal['walls'],{(1,1)})
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_access_report_is_hidden_when_geometry_or_snapshot_is_stale(self):
        state=self.store.state()
        self.store.accessibility=dict(snapshot_sha256=state['source']['sha256'],geometry=state['geometry'])
        self.assertIsNotNone(self.store.state()['accessibility'])
        data=self.payload();data['water'].append('5,6');data['blocked'].append('5,6');self.store.save(data)
        self.assertIsNone(self.store.state()['accessibility'])
        self.store.accessibility=dict(snapshot_sha256='different',geometry=self.store.state()['geometry'])
        self.assertIsNone(self.store.state()['accessibility'])

    def test_later_user_source_saves_do_not_replace_preview_copy(self):
        before=self.store.path.read_bytes();self.source.write_text('{}',encoding='utf-8')
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(self.store.state()['source']['sha256'],hashlib.sha256(self.raw).hexdigest())

    def test_stale_tab_cannot_overwrite_point_corrections(self):
        first=self.payload();stale=dict(first);first['overrides']={'4,5':None}
        self.assertEqual(self.store.save(first)[0],200);before=self.store.path.read_bytes()
        self.assertEqual(self.store.save(stale)[0],409)
        self.assertEqual(self.store.path.read_bytes(),before)

    def test_manual_assignment_is_saved_even_when_conflicting_without_running_the_solver(self):
        with patch.object(planner,'generate',side_effect=AssertionError('Automatic solver was called')):
            data=self.payload();data['rocks']=['5,5'];data['water']=[];data['overrides']={'5,5':1}
            data['scene_edits']={'5,5':'rocks'};self.assertEqual(self.store.save(data)[0],200)
            state=self.store.state()
        self.assertEqual(state['plan']['placements']['5,5']['template'],1)
        self.assertTrue(state['manual_editing']);self.assertEqual(state['scene_edits'],{'5,5':'rocks'})
        self.assertTrue(any(r['cell']=='5,5' for r in state['plan']['issues']))
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_browser_cannot_forge_approved_bindings(self):
        data=self.payload();data['boundary_preview']={'approved':True,'placements':{'0,0':{'template':17}}}
        self.store.save(data);doc,revision=self.store.read()
        self.assertFalse(doc['boundary_preview']['approved'])
        self.assertFalse(doc['boundary_preview']['apply_supported'])
        self.assertNotIn('0,0',doc['boundary_preview']['placements'])

    def test_failed_replace_preserves_copy_and_source(self):
        data=self.payload();before=self.store.path.read_bytes()
        with patch.object(editor.os,'replace',side_effect=OSError('fail')):
            with self.assertRaises(OSError):self.store.save(data)
        self.assertEqual(self.store.path.read_bytes(),before)
        self.assertEqual(self.source.read_bytes(),self.raw)
        self.assertFalse(list(self.store.workspace.glob('*.tmp')))

    def test_settings_do_not_change_geometry_and_toggle_not_required_for_save(self):
        before=self.store.state()['geometry'];data=self.payload();data['opacity']=35
        self.store.save(data);after=self.store.state()
        self.assertEqual(before,after['geometry']);self.assertEqual(after['opacity'],35)

    def test_workspace_cannot_be_the_source_or_game_data(self):
        with self.assertRaises(ValueError):
            editor.Store(self.source,editor.ROOT/'data',(),{},{})
        same=self.root/'working.json';same.write_bytes(self.raw)
        with self.assertRaises(ValueError):
            editor.Store(same,self.root,(),{},{})


    def test_http_has_no_apply_route_and_rejects_non_json(self):
        image=self.root/'map.png';image.write_bytes(b'test')
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,image))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:%d'%server.server_port
        try:
            for path in ('/apply','/publish','/install'):
                with self.assertRaises(HTTPError) as error:urlopen(Request(url+path,data=b'{}',headers={'Content-Type':'application/json'}))
                self.assertEqual(error.exception.code,404)
            with self.assertRaises(HTTPError) as error:urlopen(Request(url+'/save',data=b'{}'))
            self.assertEqual(error.exception.code,400)
            self.assertEqual(json.load(urlopen(url+'/state'))['mode'],'isolated_preview')
            current=json.load(urlopen(url+'/cell?x=5&y=5'))
            self.assertIn('actual',current);self.assertIn('spawns',current['actual'])
            self.assertIsInstance(current['actual']['id'],int)
            self.assertEqual(self.source.read_bytes(),self.raw)
            native=urlopen(url+'/template?id='+str(current['actual']['id'])+'&grid=1').read().decode()
            self.assertIn('hexGrid',native);self.assertIn('<polygon',native)
            no_grid=urlopen(url+'/template?id='+str(current['actual']['id'])+'&grid=0').read().decode()
            self.assertNotIn('hexGrid',no_grid)
        finally:server.shutdown();server.server_close();thread.join()

    def test_save_returns_fresh_issues_and_keeps_an_unrelated_conflict(self):
        data=self.payload();data['overrides']={'5,5':22,'8,8':10}
        code,result=self.store.save(data);self.assertEqual(code,200)
        self.assertEqual({r['cell'] for r in result['plan']['issues']},{'5,5','8,8'})
        self.assertNotIn('_blocked',result['plan'])
        # Water to the east fixes only the first coast's facing direction.
        data=self.payload();data['water'].append('6,5');data['blocked'].append('6,5')
        code,result=self.store.save(data);self.assertEqual(code,200)
        self.assertEqual({r['cell'] for r in result['plan']['issues']},{'8,8'})
        self.assertEqual(result['plan']['placements']['5,5']['template'],22)
        self.assertEqual(result['plan']['placements']['8,8']['template'],10)
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_wall_outline_http_response_is_json_and_does_not_write_the_draft(self):
        image=self.root/'map.png';image.write_bytes(b'test');before=self.store.path.read_bytes()
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,image))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            data=json.dumps(self.payload()).encode()
            result=json.load(urlopen(Request('http://127.0.0.1:%d/outline-walls'%server.server_port,data=data,headers={'Content-Type':'application/json'})))
            self.assertTrue(result['additions']);self.assertIn('placements',result['plan'])
            self.assertFalse(any(k.startswith('_') for k in result['plan']))
            self.assertEqual(self.store.path.read_bytes(),before);self.assertEqual(self.source.read_bytes(),self.raw)
        finally:server.shutdown();server.server_close();thread.join()

    def test_art_for_packed_cell_renders_its_source_file_instead_of_its_id(self):
        import world
        image=self.root/'map.png';image.write_bytes(b'test');commands=[]
        def render(argv,**kwargs):
            commands.append(argv);Path(argv[argv.index('-o')+1]).write_bytes(b'PNG-draft')
            return type('Result',(),dict(returncode=0))()
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,image,art_python=Path(sys.executable)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            ident=world.location_at(5,5)
            with patch.object(editor.subprocess,'run',side_effect=render):
                self.assertEqual(urlopen('http://127.0.0.1:%d/art?id=%d'%(server.server_port,ident)).read(),b'PNG-draft')
            self.assertEqual(commands[0][commands[0].index('render')+1],str(Path(world.path_for(ident))))
            self.assertEqual(self.source.read_bytes(),self.raw)
        finally:server.shutdown();server.server_close();thread.join()

    def test_explicit_repair_http_returns_an_editable_draft_without_writing(self):
        from test_boundary_outline import kit
        self.store.catalog=kit();image=self.root/'map.png';image.write_bytes(b'test');before=self.store.path.read_bytes()
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,image))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            data=json.dumps(self.payload()).encode()
            result=json.load(urlopen(Request('http://127.0.0.1:%d/repair-boundaries'%server.server_port,data=data,headers={'Content-Type':'application/json'})))
            self.assertTrue(result['draft']['physical_boundary_audit']);self.assertIn('changes',result['report'])
            self.assertFalse(any(k.startswith('_') for k in result['plan']))
            self.assertEqual(self.store.path.read_bytes(),before);self.assertEqual(self.source.read_bytes(),self.raw)
        finally:server.shutdown();server.server_close();thread.join()


    def test_cancelled_browser_download_does_not_send_another_response(self):
        Handler=editor.handler(self.store,self.source)
        for failure in (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            request=object.__new__(Handler)
            request.send_response=Mock();request.send_header=Mock();request.end_headers=Mock()
            request.wfile=Mock();request.wfile.write.side_effect=failure()
            request.send(dict(ok=True))
            request.send_response.assert_called_once_with(200)
            request.wfile.write.assert_called_once()

    def test_get_errors_before_art_import_return_valid_http_responses(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,self.source))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            for failure,status in ((OSError('unavailable'),500),(editor.subprocess.TimeoutExpired('render',60),503)):
                with patch.object(self.store,'state',side_effect=failure):
                    with self.assertRaises(HTTPError) as error:urlopen('http://127.0.0.1:%d/state'%server.server_port)
                    self.assertEqual(error.exception.code,status)
                    self.assertIn('error',json.load(error.exception))
        finally:server.shutdown();server.server_close();thread.join()


    def test_painted_coast_is_saved_as_a_separate_nonblocking_manual_type(self):
        data=self.payload();data['coast']=['4,5'];before=self.store.state()['geometry']
        self.assertEqual(self.store.save(data)[0],200)
        state=self.store.state();self.assertEqual(state['coast'],['4,5'])
        self.assertNotIn('4,5',state['blocked']);self.assertNotEqual(state['geometry'],before)
        self.assertEqual(self.source.read_bytes(),self.raw)


    def test_inspection_reuses_parsed_draft_and_detects_external_saves(self):
        with patch.object(self.store,'read',wraps=self.store.read) as read:
            first=self.store.inspection_context();second=self.store.inspection_context()
            self.assertIs(first[0],second[0]);self.assertEqual(read.call_count,1)
            self.assertIsInstance(first[2]['_blocked'],frozenset);self.assertIs(first[2]['_blocked'],second[2]['_blocked'])
            first[2]['_blocked']=frozenset({(9,9)})
            self.assertNotIn((9,9),self.store.inspection_context()[2]['_blocked'])
            changed=dict(self.original,water=['6,6','6,7'],blocked=['6,6','6,7','1,1'])
            self.store.path.write_text(json.dumps(changed),encoding='utf-8')
            third=self.store.inspection_context()
            self.assertEqual(read.call_count,2);self.assertEqual(third[1]['water'],{(6,6),(6,7)})
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_save_invalidates_inspection_and_preserves_erased_walls(self):
        self.store.inspection_context();data=self.payload()
        data['blocked'].remove('1,1');data['overrides']['1,1']=None
        self.assertEqual(self.store.save(data)[0],200)
        doc,layers,plan=self.store.inspection_context()
        self.assertEqual(doc['overrides']['1,1'],None);self.assertNotIn((1,1),layers['walls'])
        self.assertNotIn('1,1',plan['generated_walls']);self.assertTrue(planner.passable(layers,plan,(1,1)))
        self.assertEqual(self.source.read_bytes(),self.raw)

    def test_versioned_art_is_cacheable_and_supports_conditional_requests(self):
        art=self.root/'art';art.mkdir();(art/'template-17.png').write_bytes(b'PNG-cached')
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,self.source,art))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:%d/art?id=17&v=source-hash'%server.server_port
            with urlopen(url) as response:
                self.assertEqual(response.read(),b'PNG-cached');etag=response.headers['ETag']
                self.assertIn('max-age=',response.headers['Cache-Control'])
            with self.assertRaises(HTTPError) as error:urlopen(Request(url,headers={'If-None-Match':etag}))
            self.assertEqual(error.exception.code,304);self.assertEqual(error.exception.read(),b'')
        finally:server.shutdown();server.server_close();thread.join()

    def test_cached_picture_does_not_wait_for_an_unrelated_slow_renderer(self):
        import world
        cold=world.pack(5,5);warm=world.pack(6,5)
        digest=hashlib.sha256(Path(world.path_for(warm)).read_bytes()).hexdigest()
        (self.store.workspace/('art-'+digest+'.png')).write_bytes(b'PNG-warm')
        entered=threading.Event();release=threading.Event();errors=[]
        def render(argv,**kwargs):
            entered.set();release.wait(3);Path(argv[argv.index('-o')+1]).write_bytes(b'PNG-cold')
            return type('Result',(),dict(returncode=0))()
        server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(self.store,self.source,art_python=Path(sys.executable)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:%d'%server.server_port
        def load_cold():
            try:urlopen(url+'/art?id='+str(cold),timeout=5).read()
            except Exception as error:errors.append(error)
        worker=threading.Thread(target=load_cold)
        try:
            with patch.object(editor.subprocess,'run',side_effect=render):
                worker.start();self.assertTrue(entered.wait(2))
                try:self.assertEqual(urlopen(url+'/art?id='+str(warm),timeout=1).read(),b'PNG-warm')
                finally:release.set();worker.join(5)
            self.assertFalse(errors);self.assertEqual(self.source.read_bytes(),self.raw)
        finally:release.set();server.shutdown();server.server_close();thread.join()


if __name__=='__main__':run_cases(PreviewEditor)
