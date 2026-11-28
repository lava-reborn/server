"""Protected access repairs cannot join isolated regions or cut through rivers."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_planner as p
from boundary_policy import Policy,populated_places
from test_boundary_planner import catalogue,layer
from testkit import run_cases

class BoundaryPolicy(unittest.TestCase):
    def test_preserves_existing_place_without_changing_manual_marks(self):
        data=layer(water=['4,5'],rocks=['6,5']);before=p.document(data)
        policy=Policy({(4,5),(6,5)},{},lambda c:True,{},{})
        plan=policy.generate(data,catalogue(),{},'test')
        self.assertEqual(p.document(data),before)
        for c in ((4,5),(6,5)):
            self.assertTrue(p.passable(data,plan,c));self.assertNotIn(p.cell_key(c),plan['generated_walls'])
        self.assertEqual(len(plan['protected_repairs']),2)

    def test_restores_smallest_land_corridor_to_a_previously_accessible_place(self):
        data=layer(rocks=['5,%d'%y for y in range(11)])
        named={(4,5):101,(6,5):102};policy=Policy(set(named),{},lambda c:True,named,{})
        plan=policy.generate(data,catalogue(),{},'test')
        self.assertEqual(len(plan['access_corridors']),1)
        self.assertTrue(p.route(data,plan,(4,5),(6,5),catalogue())['reachable'])
        self.assertFalse(plan['unrepaired_access'])

    def test_does_not_create_a_corridor_through_the_river(self):
        data=layer(water=['5,%d'%y for y in range(11)])
        named={(4,5):101,(6,5):102};policy=Policy(set(named),{},lambda c:True,named,{})
        plan=policy.generate(data,catalogue(),{},'test')
        self.assertEqual(plan['access_corridors'],[])
        self.assertTrue(plan['unrepaired_access'])
        self.assertFalse(p.route(data,plan,(4,5),(6,5),catalogue())['reachable'])

    def test_eden_and_nubia_are_accessible_inside_but_cannot_be_crossed_from_outside(self):
        eden={(x,y) for x in (2,3) for y in (2,3)}
        nubia={(x,y) for x in (7,8) for y in (7,8)}
        data=layer(walls=['2,2','7,7']);policy=Policy(eden|nubia,{'eden':eden,'nubia':nubia},lambda c:True,{},{})
        plan=policy.generate(data,catalogue(),{},'test')
        self.assertTrue(p.route(data,plan,(2,2),(3,3),catalogue())['reachable'])
        self.assertTrue(p.route(data,plan,(7,7),(8,8),catalogue())['reachable'])
        for region in (eden,nubia):
            for c in region:
                for side in p.STEP:
                    n=p.neighbour(c,side)
                    if n not in region:
                        self.assertFalse(p.can_step(data,plan,c,n,catalogue()))
                        self.assertFalse(p.can_step(data,plan,n,c,catalogue()))
        self.assertFalse(p.route(data,plan,(2,2),(7,7),catalogue())['reachable'])

    def test_protected_access_can_withdraw_a_new_rock_scene_but_not_an_existing_closed_exit(self):
        data=layer();cat=catalogue()
        policy=Policy(set(),{},lambda c:c[1]==5,{},{})
        plan=dict(placements={'5,5':dict(template=12)},issues=[],effective_water=[],retained_river=[],generated_walls=[])
        path=policy._corridor(data,plan,cat,{(4,5)},{(6,5)})
        self.assertEqual(path,{(4,5),(5,5),(6,5)})
        policy.special={(5,5):123}
        with patch.object(p,'existing_profile',return_value=cat[12]):
            self.assertEqual(policy._corridor(data,plan,cat,{(4,5)},{(6,5)}),set())

    def test_population_protection_includes_unnamed_packed_cell_placements(self):
        import world,boundary_cells
        packed=world.pack(6000,1700)
        with patch.object(world,'borders',return_value={(6001,1700):0}), \
             patch.object(world,'settlements',return_value={(6002,1700):123}), \
             patch.object(world.eden_map,'CELL_TO_LOC',{}), \
             patch.object(world,'placements',return_value={packed:[dict(type=1025)]}), \
             patch.object(boundary_cells,'inhabitants',side_effect=lambda i:() if i==0 else (dict(type=1025),)):
            found=populated_places()
        self.assertEqual(found,{(6000,1700):packed,(6002,1700):123})


if __name__=='__main__':run_cases(BoundaryPolicy)
