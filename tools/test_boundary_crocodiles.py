"""Regional coast draft populations: native collision, distances and isolation."""
import copy,json,sys,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_crocodiles as c
import boundary_planner as p
import map_editor_preview as editor
import mobs,progression,travel,location_entry
from test_boundary_planner import catalogue
from testkit import run_cases

BOUNDS=(5833,1600,6335,2143)

class CrocodileDraft(unittest.TestCase):
    def test_all_native_layouts_are_reachable_clear_and_away_from_doors_and_other_mobs(self):
        for template in p.COAST:
            habitat=c.habitat(template);g=p.geometry(template);loc=g['loc']
            reached=c.distances(loc.width,loc.height,g['exits'].keys(),set(g['components']))
            for variant in range(c.VARIANTS):
                positions=c.layout(template,variant)
                with self.subTest(template=template,variant=variant):
                    self.assertGreaterEqual(len(positions),3)
                    self.assertEqual(len(positions),habitat['wanted'])
                    self.assertLessEqual(len(positions),c.MAX_MOBS)
                    self.assertEqual(len(positions),len(set(positions)))
                    for i,cell in enumerate(positions):
                        self.assertNotIn(cell,loc.obstacles)
                        self.assertIn(cell,reached)
                        steps=c.distances(loc.width,loc.height,[cell])
                        self.assertGreaterEqual(min(steps[door] for door in habitat['doors']),10)
                        self.assertGreaterEqual(min(steps[door] for door in location_entry._geometry(loc).candidates),10)
                        rings={cell};seen={cell}
                        for _ in range(2):
                            rings={n for a in rings for n in progression.hex_neighbours(a,loc.width,loc.height)}-seen;seen|=rings
                        self.assertTrue(seen<=habitat['land'])
                        for other in positions[:i]:self.assertGreaterEqual(steps[other],12)

    def test_hex_step_distance_matches_client_neighbours_and_breadth_first_paths(self):
        width,height=13,17
        for start in (0,12,13,55,110,220):
            paths=c.distances(width,height,[start])
            self.assertEqual(paths,{end:c.hex_steps(start,end,width) for end in paths})

    def test_city_types_and_levels_match_the_existing_regional_profiles(self):
        self.assertEqual({name:(r['mob'],r['level']) for name,r in c.REGIONS.items()},
                         {'Вади-Хальфа':(2418,4),'Абри':(2419,11),'Донгола':(130,12),'Абу-Хамед':(2420,17)})
        original=copy.deepcopy(mobs.stats(2420).__dict__)
        row=c.population('6182,1977',22,'test')
        self.assertEqual(row['level'],17);self.assertFalse(row['loot']);self.assertEqual(row['xp_multiplier'],1.0)
        self.assertEqual(mobs.stats(2420).__dict__,original)
        self.assertEqual(len({r['mob'] for r in c.REGIONS.values()}),4)

    def test_instances_are_independent_deterministic_and_not_bound_to_template_city(self):
        first=c.population('5960,1735',22,'test');again=c.population('5960,1735',22,'test')
        other=c.population('6182,1977',22,'test')
        self.assertEqual(first,again);self.assertNotEqual(first['instance_key'],other['instance_key'])
        self.assertEqual(first['type_id'],2418);self.assertEqual(other['type_id'],2420)
        first['positions'][0]=-1;self.assertNotEqual(first['positions'],again['positions'])

    def test_eden_nubia_existing_places_closed_cells_and_dry_connectors_remain_empty(self):
        points={'5960,1735':22,'5855,1840':19,'5875,2010':22,'6182,1977':18,
                '5858,1932':18,'5961,1735':30,'5962,1735':22,'5963,1735':22,'6330,2100':22}
        layers=p.normalise(dict(water=[],rocks=[],coast=list(points),blocked=[],passable=[],overrides={}),BOUNDS)
        layers['_regions']={(5858,1932):'eden',(5855,1840):'nubia'}
        plan=dict(catalog_version='test',placements={k:dict(template=t,kind='coast',allowed_exits=['W']) for k,t in points.items()},
                  issues=[],effective_water=[],generated_walls=[],depth_cells=['5963,1735'])
        result=c.build(layers,plan,protected={(5962,1735)})
        self.assertEqual(result['excluded']['5858,1932'],'isolated_eden')
        self.assertEqual(result['excluded']['5855,1840'],'isolated_nubia')
        self.assertEqual(result['excluded']['5961,1735'],'dry_connector')
        self.assertEqual(result['excluded']['5962,1735'],'existing_location')
        self.assertEqual(result['excluded']['5963,1735'],'closed_geometry')
        self.assertEqual(result['excluded']['6330,2100'],'outside_regions')
        self.assertEqual(set(result['cells']),{'5960,1735','5875,2010','6182,1977'})

    def test_invalid_moves_cannot_change_roster_enter_obstacles_or_approach_doors(self):
        key='5960,1735';row=c.population(key,22,'test');patch=dict(template=22,signature=row['signature'],positions=row['positions'])
        self.assertEqual(c.validate_overrides({key:patch},BOUNDS,'test')[key],patch)
        for target in (next(iter(p.geometry(22)['loc'].obstacles)),next(iter(c.habitat(22)['doors'])),row['positions'][1],True,-1):
            bad=copy.deepcopy(patch);bad['positions'][0]=target
            with self.subTest(target=target),self.assertRaises(ValueError):c.validate_overrides({key:bad},BOUNDS,'test')
        bad={**patch,'signature':'old'}
        with self.assertRaises(ValueError):c.validate_overrides({key:bad},BOUNDS,'test')
        bad={**patch,'positions':patch['positions'][:-1]}
        with self.assertRaises(ValueError):c.validate_overrides({key:bad},BOUNDS,'test')

    def test_density_depends_on_reachable_land_and_not_total_image_area(self):
        large=c.habitat(17);small=c.habitat(18)
        self.assertEqual((large['width'],large['height']),(small['width'],small['height']))
        self.assertGreater(len(large['land']),len(small['land']))
        self.assertGreater(large['wanted'],small['wanted'])
        for template in p.COAST:
            h=c.habitat(template);self.assertEqual(h['wanted'],min(10,max(1,len(h['land'])//450)))

    def test_unchanged_old_catalog_patch_does_not_block_unrelated_draft_saves(self):
        key='5960,1735';row=c.population(key,22,'old-catalog')
        old={key:dict(template=22,signature=row['signature'],positions=row['positions'])}
        self.assertEqual(c.saved_overrides(old,BOUNDS,'new-catalog',old),old)
        with self.assertRaises(ValueError):c.saved_overrides(old,BOUNDS,'new-catalog',{})
        changed=copy.deepcopy(old);changed[key]['positions'][0]=-1
        with self.assertRaises(ValueError):c.saved_overrides(changed,BOUNDS,'new-catalog',old)

    def test_editor_persistence_is_opt_in_and_source_bytes_are_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='coastal-preview-') as directory:
            root=Path(directory);source=root/'source.json'
            doc=dict(water=['5961,1735'],rocks=[],coast=['5960,1735'],blocked=['5961,1735'],passable=[],
                     overrides={'5960,1735':22},scene_edits={'5960,1735':'coast'})
            source.write_text(json.dumps(doc),encoding='utf-8');raw=source.read_bytes()
            disabled=editor.Store(source,root/'disabled',BOUNDS,catalogue(),{})
            self.assertNotIn('coastal_population',disabled.state()['plan'])
            store=editor.Store(source,root/'enabled',BOUNDS,catalogue(),{},'test',coastal_population=True)
            state=store.state();population=state['plan']['coastal_population']['cells']['5960,1735']
            patch=dict(template=22,signature=population['signature'],positions=population['positions'])
            payload={k:state[k] for k in ('water','rocks','coast','blocked','passable','overrides','scene_edits','revision')}
            payload['coastal_mob_overrides']={'5960,1735':patch}
            self.assertEqual(store.save(payload)[0],200)
            reread=store.state()
            self.assertEqual(reread['coastal_mob_overrides'],{'5960,1735':patch})
            self.assertEqual(reread['mob_overrides'],{})
            self.assertEqual(source.read_bytes(),raw)

    def test_coastal_validation_http_does_not_save_or_modify_native_mobs(self):
        with tempfile.TemporaryDirectory(prefix='coastal-http-') as directory:
            root=Path(directory);source=root/'source.json';source.write_text(json.dumps(dict(water=[],rocks=[],coast=[],blocked=[],passable=[],overrides={})))
            store=editor.Store(source,root/'copy',BOUNDS,catalogue(),{},'test',coastal_population=True)
            image=root/'map.png';image.write_bytes(b'PNG')
            row=c.population('5960,1735',22,'test');patch=dict(template=22,signature=row['signature'],positions=row['positions'])
            before=store.path.read_bytes();server=ThreadingHTTPServer(('127.0.0.1',0),editor.handler(store,image))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                req=Request('http://127.0.0.1:%d/validate-coastal-mobs'%server.server_port,
                            data=json.dumps(dict(coastal_mob_overrides={'5960,1735':patch})).encode(),headers={'Content-Type':'application/json'})
                self.assertEqual(json.load(urlopen(req))['5960,1735'],patch)
                self.assertEqual(store.path.read_bytes(),before)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':run_cases(CrocodileDraft)
