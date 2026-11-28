"""Independent patrol and tunnel marks: geometry, population and draft safety."""
import copy,json,sys,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'server')]
import boundary_planner as p,boundary_manual as m,boundary_patrols as patrol
from boundary_crocodiles import native_habitat,hex_steps,distances
from boundary_cells import inhabitants
from map_editor_preview import Store,handler
from test_boundary_planner import catalogue,layer
from testkit import run_cases
import world,progression,location_entry


class Marks(unittest.TestCase):
    def plan(self,data,base=None,special=None):
        return m.generate(data,catalogue(),special or {},base or p.document(data),'test')

    def test_overlay_marks_do_not_replace_the_terrain_or_each_other(self):
        data=layer(rocks=['5,5']);original=p.document(data)
        data['patrol']={(5,5)};data['tunnels']={(5,5)};doc=p.document(data)
        self.assertEqual(doc['rocks'],original['rocks']);self.assertEqual(doc['blocked'],original['blocked'])
        self.assertEqual(doc['patrol'],['5,5']);self.assertEqual(doc['tunnels'],['5,5'])
        self.assertEqual(p.document(p.normalise(doc,data['bounds'])),doc)
        before=p.fingerprint(data);data['patrol']=set();self.assertNotEqual(p.fingerprint(data),before)
        with self.assertRaises(ValueError):p.normalise({**doc,'tunnels':['11,5']},data['bounds'])

    def test_tunnel_chain_has_only_reciprocal_north_south_exits_and_closed_side_depth(self):
        data=layer();data['tunnels']={(5,4),(5,5),(5,6)};before=p.document(data);plan=self.plan(data)
        for y in (4,5,6):
            row=plan['placements'][f'5,{y}'];self.assertEqual(row['template'],6)
            self.assertEqual(row['allowed_exits'],['N','S']);self.assertFalse(row['global_map_exit']);self.assertFalse(row['global_map_entry'])
            for x in (4,6):
                self.assertFalse(p.passable(data,plan,(x,y)))
                self.assertFalse(p.can_step(data,plan,(5,y),(x,y),catalogue()))
                self.assertFalse(p.can_step(data,plan,(x,y),(5,y),catalogue()))
        self.assertTrue(p.route(data,plan,(5,3),(5,7),catalogue())['reachable'])
        self.assertEqual(p.document(data),before);self.assertFalse(plan['issues'])

    def test_erasing_tunnel_restores_pinned_rock_and_generated_wall_underlays(self):
        for pinned in (False,True):
            with self.subTest(pinned=pinned):
                data=layer(rocks=['5,5'] if pinned else [],overrides={'5,5':10} if pinned else {})
                base=p.document(data);base['boundary_preview']={'placements':{'5,5':dict(kind='rock',template=10)} if pinned else {},'generated_walls':[] if pinned else ['5,5']}
                data['tunnels']={(5,5)};plan=self.plan(data,base)
                saved=p.document(data);saved['boundary_preview']=plan
                again=self.plan(data,saved);self.assertEqual(again['placements']['5,5']['template'],6)
                data['tunnels']=set();restored=self.plan(data,saved)
                self.assertNotIn('5,5',restored['tunnels'])
                if pinned:
                    self.assertEqual(restored['placements']['5,5']['template'],10);self.assertEqual(data['overrides']['5,5'],10)
                else:self.assertIn('5,5',restored['generated_walls']);self.assertNotIn('5,5',restored['placements'])

    def test_native_rocks_at_both_tunnel_ends_refit_to_reciprocal_exits(self):
        cat,_=p.native_catalog()
        for backing in ('E','W','EW'):
            with self.subTest(backing=backing):
                data=layer(rocks=['5,4','5,6'],walls=[p.cell_key(p.neighbour((5,y),s)) for y in (4,6) for s in backing])
                data['tunnels']={(5,5)};before=p.document(data);base=copy.deepcopy(before)
                base['boundary_preview']={'placements':{f'5,{y}':dict(kind='rock',template=5) for y in (4,6)}}
                plan=m.generate(data,cat,{},base,'test')
                self.assertEqual(plan['placements']['5,5']['template'],6)
                for y,side in ((4,'S'),(6,'N')):
                    row=plan['placements'][f'5,{y}'];profile=cat[row['template']]
                    self.assertEqual(profile.closed,frozenset(backing))
                    self.assertIn(side,row['allowed_exits']);self.assertIsNotNone(p.seam(profile,cat[6],side))
                    self.assertTrue(p.can_step(data,plan,(5,y),(5,5),cat))
                    self.assertTrue(p.can_step(data,plan,(5,5),(5,y),cat))
                    g=p.geometry(row['template'])
                    self.assertTrue(any(g['components'].get(c)==g['main'] and s==side for c,s in g['exits'].items()))
                self.assertFalse(plan['issues']);self.assertEqual(p.document(data),before)

    def test_pinned_incompatible_tunnel_entrance_is_reported_and_not_opened(self):
        cat,_=p.native_catalog();data=layer(rocks=['5,4'],walls=['6,4'],overrides={'5,4':5});data['tunnels']={(5,5)}
        plan=m.generate(data,cat,{},p.document(data),'test')
        self.assertEqual(plan['placements']['5,4']['template'],5)
        self.assertFalse(p.can_step(data,plan,(5,4),(5,5),cat));self.assertFalse(p.can_step(data,plan,(5,5),(5,4),cat))
        self.assertTrue(any(r['code']=='incompatible_neighbour' for r in plan['issues']))

    def test_three_mountain_entrance_families_share_a_native_vertical_corridor(self):
        import boundary_tunnels as tunnels,travel
        cat,_=p.native_catalog();special={(3+i,5):ident for i,ident in enumerate(tunnels.MOUNTAIN_ENTRIES)}
        for cell,ident in special.items():
            data=layer();data['mountain_trails']=True;data['tunnels']={cell}
            before=copy.deepcopy(inhabitants(ident));plan=m.generate(data,cat,{cell:ident},p.document(data),'test')
            row=plan['placements'][p.cell_key(cell)];self.assertEqual(row['template'],6)
            self.assertEqual(row['closed'],['E','W']);self.assertEqual(row['native_exits'],['N','S'])
            self.assertEqual(row['source_location'],ident);self.assertTrue(row['preserve_source_binding'])
            self.assertEqual(row['source_doors'],{s:travel.door(ident,s) for s in 'ab' if travel.door(ident,s)})
            for door in row['door_designs']:
                self.assertTrue(door['cells']);self.assertIn(door['side'],'NS')
                self.assertEqual(door['target_loc_id'],row['source_doors'][door['source_side']].get('target_loc_id'))
                self.assertTrue(all(p.geometry(6)['exits'][c]==door['side'] for c in door['cells']))
            self.assertEqual(inhabitants(ident),before);self.assertFalse(plan['issues'])

    def test_mountain_entrance_can_be_saved_by_a_legacy_tab_and_overlay_erasure_restores_it(self):
        from boundary_repair import repair
        cat,_=p.native_catalog();data=layer();data['mountain_trails']=True;data['tunnels']={(5,5)};special={(5,5):162}
        with tempfile.TemporaryDirectory(prefix='mountain-entry-') as folder:
            root=Path(folder);source=root/'source.json';source.write_text(json.dumps(p.document(data)),encoding='utf-8')
            store=Store(source,root/'copy',data['bounds'],cat,special,'test');state=store.state();doc,_=store.read()
            result=repair(store.layers(doc),cat,special,doc,'test',initial=state['plan'])
            self.assertNotIn('5,5',result['draft']['overrides'])
            code,saved=store.save({**result['draft'],'revision':state['revision']});self.assertEqual(code,200)
            state=store.state();payload={k:state[k] for k in ('water','rocks','coast','blocked','passable','overrides','revision','tunnels')}
            self.assertEqual(store.save(payload)[0],200);self.assertTrue(store.state()['mountain_trails'])
            state=store.state();payload={**payload,'tunnels':[],'revision':state['revision']}
            self.assertEqual(store.save(payload)[0],200);self.assertNotIn('5,5',store.state()['plan']['placements'])

    def test_tunnel_does_not_overwrite_water_coasts_or_a_quest_location(self):
        for mark in ('water','walls','coast','special'):
            with self.subTest(mark=mark):
                data=layer();special={}
                if mark=='special':special={(5,5):105}
                else:data[mark]={(5,5)}
                data['tunnels']={(5,5)};before=p.document(data);plan=self.plan(data,special=special)
                self.assertNotIn('5,5',plan['tunnels']);self.assertEqual(p.document(data),before)
                self.assertTrue(any(r['code'] in ('tunnel_terrain_conflict','tunnel_existing_location') for r in plan['issues']))

    def test_patrol_types_are_only_the_requested_native_level_19(self):
        self.assertEqual(patrol.TYPES,((98,19),))
        types=json.loads((Path(__file__).resolve().parents[1]/'data/mob_types.json').read_text(encoding='utf-8'))['types']
        for ident,level in patrol.TYPES:
            self.assertEqual(types[str(ident)]['level'],level);self.assertIn('MagribPatrol',types[str(ident)]['name'])

    def test_patrol_spawns_are_on_connected_safe_hexes_away_from_entries_and_occupants(self):
        h=native_habitat(6);occupied=(h['candidates'][0],);row=patrol.population('5990,1700',6,occupied,'test')
        self.assertTrue(row);self.assertLessEqual(len(row['positions']),8)
        self.assertEqual(row['levels'],[19]*len(row['positions']));self.assertEqual(row['occupied'],list(occupied))
        self.assertEqual(row['type_ids'],[98]*len(row['positions']))
        for i,cell in enumerate(row['positions']):
            self.assertIn(cell,h['land']);steps=distances(h['width'],h['height'],[cell])
            self.assertGreaterEqual(min(steps[n] for n in h['doors']|location_entry._geometry(p.geometry(6)['loc']).candidates),10)
            for n in row['positions'][:i]+list(occupied):self.assertGreaterEqual(steps[n],12)
            ring=seen={cell}
            for _ in range(2):ring={n for c in ring for n in progression.hex_neighbours(c,h['width'],h['height'])}-seen;seen=seen|ring
            self.assertTrue(seen<=h['land'])

    def test_cached_patrol_layouts_are_independent_mutable_copies(self):
        a=patrol.population('5990,1700',6,(),'cache-test')
        b=patrol.population('5990,1700',6,(),'cache-test')
        self.assertEqual(a,b);self.assertIsNot(a,b)
        a['positions'][0]=-1
        self.assertNotEqual(a['positions'],b['positions'])
        self.assertEqual(patrol.population('5990,1700',6,(),'cache-test'),b)

    def test_wilderness_instances_share_geometry_but_not_population_identity(self):
        a,b=world.pack(5976,1700),world.pack(5980,1700)
        self.assertIs(patrol.habitat(a),patrol.habitat(b))
        for ident in (a,b):
            self.assertEqual(patrol.habitat(ident)['land'],native_habitat(ident)['land'])
        first=patrol.population('5976,1700',a,(),'test');second=patrol.population('5980,1700',b,(),'test')
        self.assertNotEqual(first['instance_key'],second['instance_key']);self.assertNotEqual(first['signature'],second['signature'])

    def test_patrol_and_tunnel_combine_and_native_entities_are_not_mutated(self):
        data=layer();data['bounds']=(5833,1600,6335,2143);data['patrol']={(5990,1700)};data['tunnels']={(5990,1700)}
        before=copy.deepcopy(inhabitants(6));plan=self.plan(data);result=patrol.build(data,plan,{})
        self.assertIn('5990,1700',result['cells']);self.assertEqual(result['cells']['5990,1700']['template'],6)
        self.assertEqual(result['cells']['5990,1700']['instance_key'],plan['placements']['5990,1700']['instance_key'])
        self.assertEqual(inhabitants(6),before)

    def test_incompatible_patrol_marks_remain_visible_without_spawns_or_repainting(self):
        data=layer(water=['1,1'],walls=['2,2']);data['coast']={(3,3)};data['patrol']={(1,1),(2,2),(3,3),(5,5)}
        data['_regions']={(5,5):'eden'};before=p.document(data);plan=self.plan(data)
        result=patrol.build(data,plan,{})
        self.assertEqual(len(result['excluded']),4);self.assertFalse(result['cells']);self.assertEqual(p.document(data),before)

    def test_patrol_moves_reject_obstacles_entries_and_existing_occupants(self):
        h=native_habitat(6);row=patrol.population('5990,1700',6,(h['candidates'][0],),'test');key='5990,1700'
        plan={'patrol_population':{'cells':{key:row}}};base=dict(template=6,signature=row['signature'],positions=row['positions'])
        self.assertEqual(patrol.validate_overrides({key:base},plan)[key],base)
        for target in (True,-1,next(iter(h['doors'])),row['occupied'][0],row['positions'][1]):
            bad=copy.deepcopy(base);bad['positions'][0]=target
            with self.subTest(target=target),self.assertRaises(ValueError):patrol.validate_overrides({key:bad},plan)
        stale={**base,'signature':'old'}
        self.assertEqual(patrol.validate_overrides({key:stale},plan,{key:stale})[key],stale)
        with self.assertRaises(ValueError):patrol.validate_overrides({key:stale},plan)

    def test_store_preserves_marks_for_legacy_tabs_and_never_writes_game_or_source_files(self):
        with tempfile.TemporaryDirectory(prefix='marks-store-') as folder:
            root=Path(folder);source=root/'source.json';data=layer();data['bounds']=(5833,1600,6335,2143)
            data['tunnels']={(5990,1700)};data['patrol']={(5990,1700)};source.write_text(json.dumps(p.document(data)))
            raw=source.read_bytes();store=Store(source,root/'copy',data['bounds'],catalogue(),{},'test')
            state=store.state();payload={k:state[k] for k in ('water','rocks','coast','blocked','passable','overrides','revision')}
            self.assertEqual(store.save(payload)[0],200)
            saved=store.state();self.assertEqual(saved['patrol'],['5990,1700']);self.assertEqual(saved['tunnels'],['5990,1700'])
            self.assertFalse(saved['plan']['placements']['5990,1700']['global_map_exit']);self.assertEqual(source.read_bytes(),raw)

    def test_http_patrol_preview_validation_is_draft_only(self):
        with tempfile.TemporaryDirectory(prefix='marks-http-') as folder:
            root=Path(folder);source=root/'source.json';source.write_text(json.dumps(p.document(layer())))
            bounds=(5833,1600,6335,2143);store=Store(source,root/'copy',bounds,catalogue(),{},'test')
            image=root/'map.png';image.write_bytes(b'PNG');server=ThreadingHTTPServer(('127.0.0.1',0),handler(store,image))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                data=p.document(p.normalise({'patrol':['5990,1700'],'tunnels':['5990,1700']},bounds))
                def post(path,body):
                    req=Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                    return json.load(urlopen(req))
                before=store.path.read_bytes();plan=post('/calculate',data);row=plan['patrol_population']['cells']['5990,1700']
                self.assertEqual(plan['patrol_population']['types'],[dict(type_id=98,level=19)])
                self.assertEqual(set(row['type_ids']),{98});self.assertEqual(set(row['levels']),{19})
                patch=dict(template=row['template'],signature=row['signature'],positions=row['positions'])
                result=post('/validate-patrol-mobs',{**data,'patrol_mob_overrides':{'5990,1700':patch}})
                self.assertEqual(result['5990,1700'],patch);self.assertEqual(store.path.read_bytes(),before)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':run_cases(Marks)
