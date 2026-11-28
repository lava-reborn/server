"""Connected draft outlines, native corner resources and immutable ordinary land."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_planner as p
from test_boundary_planner import catalogue,layer
from testkit import run_cases


def kit():
    result=catalogue();bits=(1<<p.BINS)-1
    for ident,kind in ((30,'coast'),(51,'rock')):
        result[ident]=p.Profile(ident,kind,frozenset(),{s:bits for s in p.STEP})
    return result


class BoundaryOutline(unittest.TestCase):
    def test_turning_river_gets_native_dry_connectors_without_consuming_core(self):
        water={(x,y) for y in range(11) for x in range(2+y//3,min(11,7+y//3))}
        data=layer(water=list(map(p.cell_key,water)));before=copy.deepcopy(data);cat=kit();plan=p.generate(data,cat)
        self.assertEqual(data,before);self.assertFalse(plan['issues']);self.assertFalse(plan['review_walls'])
        self.assertGreater(plan['summary']['coast'],0)
        self.assertTrue(all(row['template']!=30 for key,row in plan['placements'].items() if p.point(key) in data['water']))
        self.assertTrue(set(map(p.point,plan['retained_river'])))
        for key,row in plan['placements'].items():
            self.assertTrue(row['allowed_exits']);self.assertTrue(row['resource_only'])
            self.assertNotIn(key,plan['generated_walls']);self.assertNotIn(key,plan['effective_water'])
            for side in row['allowed_exits']:
                c=p.point(key);n=p.neighbour(c,side)
                self.assertTrue(p.can_step(data,plan,c,n,cat));self.assertTrue(p.can_step(data,plan,n,c,cat))

    def test_rock_uncertainty_becomes_red_wall_without_a_false_location(self):
        data=layer(rocks=['5,%d'%y for y in range(2,9)]);plan=p.generate(data,kit())
        self.assertIn('5,5',plan['generated_walls']);self.assertNotIn('5,5',plan['placements'])
        self.assertFalse(plan['issues']);self.assertTrue(plan['resolutions'])

    def test_thin_river_stays_blocked_and_gets_shores_on_land(self):
        data=layer(water=['5,%d'%y for y in range(11)]);cat=kit();plan=p.generate(data,cat)
        self.assertEqual(plan['replaced_water'],[])
        self.assertFalse(p.route(data,plan,(4,5),(6,5),cat)['reachable'])
        for x in (4,6):self.assertEqual(plan['placements']['%d,5'%x]['kind'],'coast')

    def test_unmarked_land_is_not_replaced_and_remains_connected(self):
        data=layer();cat=kit();plan=p.generate(data,cat)
        self.assertEqual(plan['placements'],{})
        self.assertTrue(p.route(data,plan,(0,0),(10,10),cat)['reachable'])

    def test_manual_wall_and_suppressed_shore_are_not_overridden(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(3,8) for y in range(11)],walls=['2,5'],overrides={'3,5':None})
        plan=p.generate(data,kit())
        for key in ('2,5','3,5'):self.assertNotIn(key,plan['placements'])
        self.assertIn('2,5',p.document(data)['blocked'])
        self.assertIn('3,5',plan['retained_river'])

    def test_instances_are_unique_and_eden_shores_have_no_spawns_or_outer_steps(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(3,8) for y in range(11)])
        data['_regions']={(x,y):'eden' for x in range(6) for y in range(11)};data['_mask_regions']={'eden'}
        cat=kit();plan=p.generate(data,cat);rows=plan['placements']
        self.assertEqual(len(rows),len({r['instance_key'] for r in rows.values()}))
        for key,row in rows.items():
            c=p.point(key)
            if data['_regions'].get(c)=='eden':self.assertEqual(row['spawn_policy'],'none')
        for y in range(11):
            self.assertFalse(p.can_step(data,plan,(5,y),(6,y),cat));self.assertFalse(p.can_step(data,plan,(6,y),(5,y),cat))

    def test_connector_override_cannot_crash_rock_selection_or_hide_an_invalid_choice(self):
        data=layer(rocks=['5,%d'%y for y in range(2,9)],overrides={'5,5':30})
        plan=p.generate(data,kit())
        self.assertNotIn('5,5',plan['placements'])
        self.assertTrue(any(r['cell']=='5,5' and r['code']=='override_conflict' for r in plan['issues']))

    def test_manual_wall_gets_one_connected_outer_rock_ring_and_keeps_its_cell_blocked(self):
        data=layer(walls=['5,5']);before=copy.deepcopy(data);cat=kit();plan=p.generate(data,cat)
        ring={(x,y) for x in range(4,7) for y in range(4,7)}-{(5,5)}
        self.assertEqual(data,before)
        self.assertEqual(set(map(p.point,plan['placements'])),ring)
        self.assertEqual(plan['summary']['wall_outline'],8)
        self.assertNotIn('5,5',plan['placements']);self.assertFalse(p.passable(data,plan,(5,5)))
        self.assertFalse(plan['generated_walls'])
        for key,row in plan['placements'].items():
            self.assertEqual(row['kind'],'rock');self.assertTrue(row['wall_outline'])
            self.assertTrue(row['allowed_exits'])
        self.assertEqual(plan['summary']['boundary_components'],1)
        self.assertEqual(plan['summary']['sealed_adjacent_faces'],0)
        again=p.generate(data,cat)
        self.assertEqual(plan['placements'],again['placements'])

    def test_wall_outline_does_not_replace_water_existing_places_or_suppressed_cells(self):
        data=layer(walls=['5,5'],water=['6,5'],overrides={'4,4':None})
        data['_preserved_land']={(5,4)};cat=kit();plan=p.generate(data,cat,{(5,4):123})
        for key in ('5,5','5,4','4,4','6,5'):self.assertNotIn(key,plan['placements'])
        self.assertIn('6,5',plan['retained_river'])
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(4,5),(5,5),cat))
        self.assertTrue(any(row['wall_outline'] and row['kind']=='rock' for row in plan['placements'].values()))


    def test_painted_coast_uses_water_side_and_prevents_a_second_automatic_bank_row(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)])
        data['coast']={(3,y) for y in range(11)};before=p.document(data);cat=kit();plan=p.generate(data,cat)
        self.assertEqual(p.document(data),before)
        for y in range(1,10):
            row=plan['placements']['3,%d'%y]
            self.assertEqual(row['template'],22);self.assertTrue(row['manual'])
            self.assertIn('4,%d'%y,plan['retained_river'])
            self.assertNotIn('4,%d'%y,plan['placements'])
            self.assertFalse(p.can_step(data,plan,(3,y),(4,y),cat))
        self.assertEqual(p.normalise(p.document(data),data['bounds'])['coast'],data['coast'])

    def test_painted_coast_without_matching_water_is_reported_without_inventing_a_river(self):
        data=layer();data['coast']={(5,5)};cat=kit();plan=p.generate(data,cat)
        self.assertNotIn('5,5',plan['placements'])
        self.assertTrue(any(r['cell']=='5,5' and r['code']=='manual_coast_no_template' for r in plan['issues']))
        self.assertFalse(plan['effective_water']);self.assertTrue(p.passable(data,plan,(5,5)))


    def test_erased_generated_shore_stays_suppressed_after_roundtrip_and_recalculation(self):
        data=layer(water=['5,%d'%y for y in range(11)],overrides={'4,5':None})
        cat=kit();data=p.normalise(p.document(data),data['bounds']);plan=p.generate(data,cat)
        self.assertNotIn('4,5',plan['placements'])
        self.assertFalse(any(r['cell']=='4,5' for r in plan['issues']))
        self.assertIn('5,5',plan['retained_river'])
        self.assertFalse(p.can_step(data,plan,(4,5),(5,5),cat))
        self.assertNotIn('4,5',p.generate(data,cat)['placements'])


    def test_erased_automatic_wall_stays_empty_and_does_not_receive_a_scene(self):
        for cat in (kit(),catalogue()):
            data=layer(rocks=['%d,%d'%(x,y) for x in range(4,9) for y in range(11)])
            self.assertIn('6,5',p.generate(data,cat)['generated_walls'])
            data['rocks'].remove((6,5));data['overrides']['6,5']=None
            before=copy.deepcopy(data);plan=p.generate(data,cat)
            self.assertEqual(data,before)
            self.assertNotIn('6,5',plan['generated_walls']);self.assertNotIn('6,5',plan['placements'])
            self.assertIn('6,5',plan['cleared_land']);self.assertTrue(p.passable(data,plan,(6,5)))
            saved=p.normalise(p.document(data),data['bounds'])
            self.assertNotIn('6,5',p.generate(saved,cat)['generated_walls'])

    def test_erased_manual_wall_is_not_replaced_by_a_neighbours_rock_outline(self):
        data=layer(walls=['6,5'],overrides={'5,5':None});cat=kit();plan=p.generate(data,cat)
        self.assertNotIn('5,5',plan['placements']);self.assertNotIn('5,5',plan['generated_walls'])
        self.assertTrue(p.route(data,plan,(4,5),(5,5),cat)['reachable'])
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(0,5),(-1,5),cat))


if __name__=='__main__':run_cases(BoundaryOutline)
