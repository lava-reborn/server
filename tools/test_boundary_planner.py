"""Boundary proposal invariants and native geometry, without game mutations."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_planner as p
from testkit import run_cases


def catalogue():
    all_bits=(1<<p.BINS)-1
    return {i:p.Profile(i,'coast' if i in p.COAST else 'rock',frozenset(side),
             {s:0 if s in side else all_bits for s in p.STEP}) for i,side in {**p.ROCK,**p.COAST}.items()}


def layer(water=(),rocks=(),walls=(),opened=(),overrides=None):
    return p.normalise(dict(water=list(water),rocks=list(rocks),blocked=list(walls)+list(water)+list(rocks),
               passable=list(opened),overrides=overrides or {}),(0,0,10,10))


class BoundaryPlanner(unittest.TestCase):
    def test_both_banks_face_river_without_shared_instance_keys(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)])
        plan=p.generate(data,catalogue())
        for y in range(1,10):
            self.assertEqual(plan['placements']['4,%d'%y]['template'],22)
            self.assertEqual(plan['placements']['6,%d'%y]['template'],19)
        keys=[r['instance_key'] for r in plan['placements'].values()]
        self.assertEqual(len(keys),len(set(keys)))

    def test_no_inland_or_diagonal_tails_after_river_ends(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(5)])
        plan=p.generate(data,catalogue())
        for key in plan['placements']:
            point=p.point(key)
            self.assertIn(point,data['water'])
            self.assertTrue(any(p.neighbour(point,s) in set(map(p.point,plan['retained_river'])) for s in p.STEP))
        self.assertNotIn('4,5',plan['placements']);self.assertNotIn('6,5',plan['placements'])
        self.assertNotIn('5,6',plan['placements'])

    def test_water_and_outer_bounds_cannot_be_crossed_by_global_route(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)])
        catalog=catalogue();plan=p.generate(data,catalog)
        self.assertFalse(p.route(data,plan,(4,5),(6,5),catalog)['reachable'])
        self.assertTrue(p.route(data,plan,(4,1),(4,9),catalog)['reachable'])
        self.assertFalse(p.can_step(data,plan,(4,5),(5,5),catalog))
        self.assertFalse(p.can_step(data,plan,(0,0),(-1,0),catalog))

    def test_manual_walls_preserved_and_never_receive_locations(self):
        data=layer(water=['5,5'],walls=['4,5','0,0','1,0'])
        before=copy.deepcopy(data);plan=p.generate(data,catalogue())
        self.assertEqual(data,before)
        self.assertTrue(set(map(p.cell_key,data['walls'])).isdisjoint(plan['placements']))
        self.assertIn('5,5',plan['review_walls'])
        self.assertEqual(plan['summary']['preserved_manual_walls'],3)

    def test_explicit_thin_rock_orientation_gains_wall_behind_scene(self):
        data=layer(rocks=['5,%d'%y for y in range(2,9)],overrides={'5,4':1,'5,5':1,'5,6':1})
        catalog=catalogue();plan=p.generate(data,catalog)
        self.assertEqual(plan['placements']['5,5']['template'],1)
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalog))
        self.assertFalse(p.can_step(data,plan,(6,5),(5,5),catalog))
        self.assertTrue(p.can_step(data,plan,(5,5),(4,5),catalog))
        self.assertIn('6,5',plan['backing_walls'])
        self.assertIn('6,5',plan['generated_walls'])
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertEqual(data['walls'],set())

    def test_thin_rock_band_with_unknown_back_is_not_guessed(self):
        data=layer(rocks=['5,%d'%y for y in range(2,9)])
        plan=p.generate(data,catalogue())
        self.assertNotIn('5,5',plan['placements'])
        self.assertTrue(any(r['cell']=='5,5' and r['code']=='ambiguous_rock_direction' for r in plan['issues']))
        self.assertFalse(p.passable(data,plan,(5,5)))

    def test_rock_interior_becomes_generated_walls_without_changing_manual_layer(self):
        rocks=['%d,%d'%(x,y) for x in range(3,8) for y in range(3,8)]
        data=layer(rocks=rocks);plan=p.generate(data,catalogue())
        self.assertIn('5,5',plan['interior_rocks']);self.assertFalse(p.passable(data,plan,(5,5)))
        self.assertEqual(data['walls'],set());self.assertIn('5,5',plan['generated_walls'])
        self.assertGreater(plan['summary']['added_walls'],0)

    def test_only_one_rock_row_then_wall_and_no_route_through_boundary(self):
        data=layer(rocks=['%d,%d'%(x,y) for x in range(5,11) for y in range(11)])
        before=copy.deepcopy(data);catalog=catalogue();plan=p.generate(data,catalog)
        self.assertEqual(data,before)
        rock_rows={p.point(k) for k,r in plan['placements'].items() if r['kind']=='rock'}
        self.assertEqual(rock_rows,{(5,y) for y in range(11)})
        walls=set(map(p.point,plan['generated_walls']))
        self.assertTrue({(x,y) for x in range(6,11) for y in range(11)}<=walls)
        self.assertTrue(walls.isdisjoint(rock_rows))
        self.assertTrue(p.route(data,plan,(4,5),(5,5),catalog)['reachable'])
        self.assertFalse(p.route(data,plan,(4,5),(7,5),catalog)['reachable'])
        for a in rock_rows:
            for side in plan['placements'][p.cell_key(a)]['closed']:
                back=p.neighbour(a,side)
                self.assertTrue(not p.inside(back,data['bounds']) or back in walls|data['walls']|data['water'])

    def test_rock_backing_wall_never_consumes_protected_point_or_coast(self):
        for extra in ({},):
            with self.subTest(extra=extra):
                data=layer(rocks=['5,%d'%y for y in range(2,9)],overrides={'5,5':1},**extra)
                special={(6,5):61} if not extra else {}
                plan=p.generate(data,catalogue(),special)
                self.assertNotIn('5,5',plan['placements'])
                self.assertNotIn('6,5',plan['generated_walls'])
                self.assertFalse(p.passable(data,plan,(5,5)))
                self.assertTrue(any(r['code'] in ('backing_wall_conflict','isolated_boundary') for r in plan['issues']))

    def test_no_generated_wall_or_template_on_protected_marked_rock(self):
        data=layer(rocks=['%d,%d'%(x,y) for x in range(3,8) for y in range(3,8)])
        plan=p.generate(data,catalogue(),{(5,5):61})
        self.assertNotIn('5,5',plan['generated_walls'])
        self.assertNotIn('5,5',plan['placements'])
        self.assertTrue(any(r['cell']=='5,5' and r['code']=='protected_mark_conflict' for r in plan['issues']))

    def test_rocks_may_be_backed_by_existing_water_without_creating_wall_there(self):
        data=layer(rocks=['4,%d'%y for y in range(11)],water=['%d,%d'%(x,y) for x in range(5,9) for y in range(11)])
        catalog=catalogue();plan=p.generate(data,catalog)
        self.assertEqual(plan['placements']['4,5']['closed'],['E'])
        self.assertNotIn('5,5',plan['generated_walls'])
        self.assertFalse(p.can_step(data,plan,(4,5),(5,5),catalog))

    def test_legacy_green_marks_are_plain_land_and_not_required_for_movement(self):
        data=layer(opened=['1,1','2,1']);ordinary=layer()
        self.assertEqual(data['passable'],set())
        self.assertEqual(p.fingerprint(data),p.fingerprint(ordinary))
        plan=p.generate(data,catalogue())
        self.assertTrue(p.route(data,plan,(1,1),(9,9),catalogue())['reachable'])
        self.assertEqual(p.document(data)['passable'],[])

    def test_protected_quest_point_is_not_overwritten(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)]);plan=p.generate(data,catalogue(),{(4,5):61})
        self.assertNotIn('4,5',plan['placements'])
        self.assertTrue(any(r['cell']=='4,5' and r['existing']==61 for r in plan['issues']))

    def test_joint_selection_chooses_compatible_variant_instead_of_lowest_id(self):
        catalog={10:p.Profile(10,'rock',frozenset('N'),{'E':3,'W':12,'S':15}),
                 11:p.Profile(11,'rock',frozenset('N'),{'E':12,'W':3,'S':15})}
        chosen,approx=p._component_assignment({(1,1),(2,1)},{(1,1):{10,11},(2,1):{10}},catalog)
        self.assertEqual(chosen,{(1,1):11,(2,1):10});self.assertFalse(approx)
        self.assertIsNotNone(p.seam(catalog[chosen[1,1]],catalog[chosen[2,1]],'E'))

    def test_wrong_orientation_override_is_reported_not_silently_applied(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)],overrides={'4,5':19})
        plan=p.generate(data,catalogue());self.assertNotIn('4,5',plan['placements'])
        self.assertTrue(any(r['code']=='override_conflict' for r in plan['issues']))

    def test_suppression_survives_recalculation_without_modifying_water(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(4,7) for y in range(11)],overrides={'4,5':None})
        plan=p.generate(data,catalogue());self.assertNotIn('4,5',plan['placements'])
        self.assertFalse(p.passable(data,plan,(4,5)))
        self.assertEqual(data['water'],{(x,y) for x in range(4,7) for y in range(11)})
        self.assertEqual(p.generate(data,catalogue()),{k:v for k,v in plan.items() if not k.startswith('_')})

    def test_geometry_revision_ignores_opacity_but_tracks_overrides_and_terrain(self):
        data=layer(water=['5,5']);first=p.fingerprint(data)
        data['opacity']=20;self.assertEqual(first,p.fingerprint(data))
        data['overrides']['4,5']=None;self.assertNotEqual(first,p.fingerprint(data))

    def test_rejects_conflicts_bad_types_and_outside_cells(self):
        for doc in ({'water':['5,5'],'rocks':['5,5']},{'water':['11,5']},
                    {'passable':['bad']},{'overrides':{'1,1':True}}, {'opacity':101}):
            with self.subTest(doc=doc),self.assertRaises(ValueError):p.normalise(doc,(0,0,10,10))

    def test_inset_coast_replaces_edge_water_without_mutating_manual_draft(self):
        data=layer(water=['%d,%d'%(x,y) for x in range(3,8) for y in range(11)])
        before=copy.deepcopy(data);catalog=catalogue();plan=p.generate(data,catalog)
        shore={p.point(k) for k in plan['replaced_water']}
        self.assertTrue(shore);self.assertTrue(shore<=data['water']);self.assertEqual(data,before)
        self.assertEqual(shore,{p.point(k) for k,r in plan['placements'].items() if r['kind']=='coast'})
        self.assertFalse(shore&set(map(p.point,plan['effective_water'])))
        self.assertFalse(shore&set(map(p.point,plan['generated_walls'])))
        self.assertTrue(p.route(data,plan,(2,5),(3,5),catalog)['reachable'])
        self.assertFalse(p.route(data,plan,(3,5),(7,5),catalog)['reachable'])
        self.assertNotIn('2,5',plan['placements']);self.assertNotIn('8,5',plan['placements'])

    def test_thin_channels_are_never_consumed_or_turned_into_a_crossing(self):
        for width in (1,2):
            with self.subTest(width=width):
                data=layer(water=['%d,%d'%(x,y) for x in range(5,5+width) for y in range(11)])
                catalog=catalogue();plan=p.generate(data,catalog)
                self.assertEqual(plan['replaced_water'],[])
                self.assertEqual(set(map(p.point,plan['retained_river'])),data['water'])
                self.assertFalse(p.route(data,plan,(4,5),(5+width,5),catalog)['reachable'])

    def test_river_neck_and_water_connectivity_survive_inset(self):
        water={(x,y) for x in range(2,9) for y in (*range(4),*range(7,11))}|{(5,y) for y in range(4,7)}
        data=layer(water=list(map(p.cell_key,water)));catalog=catalogue();plan=p.generate(data,catalog)
        retained=set(map(p.point,plan['retained_river']));seen={min(retained)};queue=list(seen)
        while queue:
            cell=queue.pop()
            for side in p.STEP:
                n=p.neighbour(cell,side)
                if n in retained and n not in seen:seen.add(n);queue.append(n)
        self.assertEqual(seen,retained);self.assertTrue({(5,4),(5,5),(5,6)}<=retained)
        self.assertFalse(p.route(data,plan,(0,5),(10,5),catalog)['reachable'])
        for key,row in plan['placements'].items():
            if row['kind']=='coast':
                cell=p.point(key)
                self.assertEqual(set(row['closed']),{s for s in p.STEP if p.neighbour(cell,s) in retained})

    def test_review_walls_never_replace_protected_locations_or_overlap_scenes(self):
        data=layer(water=['5,5'],rocks=['7,%d'%y for y in range(2,9)])
        plan=p.generate(data,catalogue(),{(7,5):61})
        review=set(map(p.point,plan['review_walls']))
        self.assertTrue(review);self.assertNotIn((7,5),review)
        self.assertFalse(review&set(map(p.point,plan['placements'])))
        for cell in review:self.assertFalse(p.passable(data,plan,cell))

    def test_native_profiles_have_no_exit_through_closed_side(self):
        catalog,version=p.native_catalog()
        self.assertEqual(set(catalog),set(p.COAST)|set(p.ROCK)|set(p.CONNECTORS));self.assertTrue(version)
        self.assertEqual(catalog[5].closed,frozenset('NS'))
        self.assertEqual(catalog[6].closed,frozenset('EW'))
        for profile in catalog.values():
            self.assertFalse(profile.closed & profile.exits)
        self.assertNotIn('N',catalog[24].exits) # source has an invalid north record outside the map

    def test_existing_location_closed_side_is_not_bypassed_by_global_walk(self):
        data=layer();data['_special']={(5,5):1}
        plan=p.generate(data,catalogue())
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(6,5),(5,5),catalogue()))
        self.assertTrue(p.can_step(data,plan,(5,5),(4,5),catalogue()))

    def test_native_obstacle_cannot_be_used_as_local_destination(self):
        geometry=p.geometry(24);loc=geometry['loc']
        free=next(c for c,n in geometry['components'].items() if n==geometry['main'])
        blocked=next(c for c in loc.obstacles if 0<=c<loc.width*loc.height)
        self.assertTrue(p.local_probe(24,free,free)['reachable'])
        self.assertFalse(p.local_probe(24,free,blocked)['reachable'])
        self.assertFalse(p.local_probe(24,free,loc.width*loc.height)['reachable'])


if __name__=='__main__':run_cases(BoundaryPlanner)
