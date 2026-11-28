"""Explicit repairs must expose real native obstacles, never cosmetic exit masks."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_planner as p,boundary_manual as m
from boundary_repair import repair
from test_boundary_outline import kit
from test_boundary_planner import layer
from testkit import run_cases
from map_editor_preview import Store


class Repair(unittest.TestCase):
    def make(self,data,base=None,special=None):
        return repair(data,kit(),special or {},base or p.document(data),'test')

    def test_a_wall_has_physical_native_rock_faces_on_every_approach(self):
        data=layer(walls=['5,5']);before=copy.deepcopy(data);result=self.make(data);plan=result['plan']
        for side in p.STEP:
            cell=p.neighbour((5,5),side);row=plan['placements'][p.cell_key(cell)]
            self.assertEqual(row['kind'],'rock');self.assertIn(p.OPPOSITE[side],kit()[row['template']].closed)
            self.assertNotIn(row['template'],p.CONNECTORS)
        self.assertNotIn('5,5',plan['placements']);self.assertEqual(data,before);self.assertFalse(plan['issues'])

    def test_water_gets_shores_facing_its_core_without_a_second_river(self):
        data=layer(water=[f'5,{y}' for y in range(11)]);result=self.make(data);plan=result['plan']
        self.assertEqual(result['draft']['water'],p.document(data)['water'])
        for x,side in ((4,'E'),(6,'W')):
            row=plan['placements'][f'{x},5'];self.assertEqual(row['kind'],'coast');self.assertEqual(row['closed'],[side])
        self.assertTrue(all(row['template'] not in (38,39,54,55,56,57) for row in plan['placements'].values()))

    def test_explicit_repair_can_replace_a_conflicting_old_pin(self):
        data=layer(rocks=['5,5'],walls=['5,4'],overrides={'5,5':15});before=p.document(data)
        result=self.make(data)
        self.assertEqual(result['plan']['placements']['5,5']['closed'],['N'])
        self.assertIn(result['draft']['overrides']['5,5'],(10,11));self.assertEqual(p.document(data),before)
        self.assertTrue(any(r['action']=='release_conflicting_template' for r in result['report']['changes']))

    def test_inland_rock_uses_the_native_dry_resource_instead_of_a_false_back_wall(self):
        data=layer(rocks=['5,5']);base=p.document(data)
        base['boundary_preview']={'placements':{'5,5':dict(kind='rock',template=15,manual=True)}}
        result=self.make(data,base)
        self.assertEqual(result['plan']['placements']['5,5']['template'],51)
        self.assertEqual(result['draft']['blocked'],base['blocked']);self.assertFalse(result['plan']['issues'])

    def test_quest_location_and_other_authored_metadata_are_not_overwritten(self):
        data=layer(walls=['5,5']);data['_preserved_land']={(5,4)};base=p.document(data)
        base['mob_overrides']={'5,4':{'original':'positions'}};before=copy.deepcopy(base)
        result=self.make(data,base,{(5,4):105})
        self.assertNotIn('5,4',result['plan']['placements']);self.assertEqual(result['draft']['mob_overrides'],base['mob_overrides'])
        self.assertEqual(base,before)

    def test_closed_tunnel_sides_receive_actual_wall_depth_and_an_outer_rim(self):
        data=layer();data['tunnels']={(5,5)};result=self.make(data);plan=result['plan'];new=p.normalise(result['draft'],data['bounds'])
        for x in (4,6):
            self.assertIn(f'{x},5',result['draft']['blocked']);self.assertNotIn(f'{x},5',plan['placements'])
            self.assertFalse(p.can_step(new,plan,(5,5),(x,5),kit()))
        for y,side in ((4,'S'),(6,'N')):
            if f'5,{y}' in plan['placements']:self.assertIn(side,plan['placements'][f'5,{y}']['allowed_exits'])
        self.assertEqual(plan['placements']['5,5']['template'],6)

    def test_repaired_native_choices_survive_ordinary_save_and_reload(self):
        with tempfile.TemporaryDirectory(prefix='boundary-repair-') as folder:
            root=Path(folder);source=root/'source.json';data=layer(rocks=['5,5'],walls=['5,4'],overrides={'5,5':15})
            source.write_text(json.dumps(p.document(data)),encoding='utf-8');original=source.read_bytes()
            store=Store(source,root/'copy',data['bounds'],kit(),{},'test');state=store.state()
            result=repair(store.layers(state),kit(),{},json.loads(store.path.read_bytes()),'test',initial=state['plan'])
            payload={**result['draft'],'revision':state['revision']};code,saved=store.save(payload)
            self.assertEqual(code,200);again=store.state()
            self.assertEqual(again['plan']['placements']['5,5']['closed'],['N']);self.assertFalse(again['plan']['issues'])
            self.assertEqual(source.read_bytes(),original)

    def test_removing_one_rim_scene_reports_only_its_real_gap_without_repainting(self):
        data=layer(walls=['5,5']);result=self.make(data);doc=result['draft'];new=p.normalise(doc,data['bounds'])
        new['rocks'].discard((4,5));new['overrides']['4,5']=None;edits={**doc['scene_edits'],'4,5':'erase'}
        plan=m.generate(new,kit(),{},doc,'test',edits)
        self.assertIn('4,5',{r['cell'] for r in plan['issues'] if r['code']=='boundary_missing_scene'})
        self.assertNotIn('4,5',plan['placements']);self.assertNotIn((4,5),new['rocks'])

    def test_native_tunnel_landing_turns_to_existing_shops_without_replacing_them(self):
        cat,_=p.native_catalog();data=layer(rocks=['3,6','4,6','5,6','6,6','7,6','5,7'])
        data['tunnels']={(5,4),(5,5)};special={(4,7):625,(6,7):625};data['_special']=special
        result=repair(data,cat,special,p.document(data),'test');plan=result['plan'];new=p.normalise(result['draft'],data['bounds']);new['_special']=special
        for x in (4,6):
            row=plan['placements'][f'{x},6'];self.assertIn('S',row['allowed_exits']);self.assertIn('N',row['closed'])
            self.assertTrue(p.can_step(new,plan,(x,6),(x,7),cat));self.assertTrue(p.can_step(new,plan,(x,7),(x,6),cat))
            self.assertNotIn(f'{x},7',plan['placements'])
        self.assertEqual(set(plan['placements']['5,6']['allowed_exits']),{'N','E','W'})
        self.assertEqual(set(plan['placements']['5,5']['allowed_exits']),{'N','S'})

    def test_an_unchanged_dry_pin_survives_a_repair_of_its_bad_neighbour(self):
        with tempfile.TemporaryDirectory(prefix='boundary-dry-pin-') as folder:
            root=Path(folder);source=root/'source.json';data=layer(rocks=['5,5','6,5'],overrides={'5,5':51,'6,5':12})
            source.write_text(json.dumps(p.document(data)),encoding='utf-8');store=Store(source,root/'copy',data['bounds'],kit(),{},'test')
            state=store.state();doc,_=store.read();result=repair(store.layers(doc),kit(),{},doc,'test',initial=state['plan'])
            self.assertEqual(result['draft']['overrides']['5,5'],51)
            code,saved=store.save({**result['draft'],'revision':state['revision']});self.assertEqual(code,200)
            self.assertFalse(saved['plan']['issues']);self.assertEqual(saved['plan']['placements']['5,5']['template'],51)


if __name__=='__main__':run_cases(Repair)
