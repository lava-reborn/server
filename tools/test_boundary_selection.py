"""Joint native map selection, preservation of pins and compatible exits."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_planner as p
from boundary_selection import fit
from boundary_manual import generate
from test_boundary_planner import catalogue,layer
from testkit import run_cases


class Selection(unittest.TestCase):
    def pair_catalog(self):
        return {10:p.Profile(10,'rock',frozenset('NS'),{'E':1,'W':1}),
                11:p.Profile(11,'rock',frozenset('N'),{'E':2,'W':2,'S':3})}

    def test_three_maps_switch_together_without_breaking_a_previously_valid_seam(self):
        cat=self.pair_catalog();rows={f'{x},5':dict(kind='rock',template=10) for x in range(4,7)}
        data=layer();updates=fit(rows,data,cat,set(),{},lambda kind,cell:(frozenset('N'),[]))
        self.assertEqual(len(updates),3)
        self.assertEqual({r['template'] for r in rows.values()},{11})
        for x in (4,5):self.assertIsNotNone(p.seam(cat[rows[f'{x},5']['template']],cat[rows[f'{x+1},5']['template']],'E'))

    def test_a_pin_cannot_be_changed_to_force_a_joint_solution(self):
        cat=self.pair_catalog();rows={f'{x},5':dict(kind='rock',template=10) for x in range(4,7)}
        data=layer(overrides={'5,5':10})
        self.assertEqual(fit(rows,data,cat,set(),{},lambda kind,cell:(frozenset('N'),[])),[])
        self.assertEqual({r['template'] for r in rows.values()},{10})

    def test_a_closed_cycle_is_fitted_as_a_whole_without_opening_a_bad_join(self):
        cat={i:p.Profile(i,'rock',frozenset(),{s:mask for s in p.STEP}) for i,mask in ((10,1),(11,2))}
        keys=['4,4','5,4','5,5','4,5']
        rows={k:dict(kind='rock',template=10+i%2) for i,k in enumerate(keys)}
        updates=fit(rows,layer(),cat,set(),{},lambda kind,cell:(frozenset(),[]))
        self.assertEqual(len(updates),2);self.assertEqual(len({r['template'] for r in rows.values()}),1)

    def test_existing_location_exit_is_a_hard_constraint(self):
        cat=self.pair_catalog();rows={'5,5':dict(kind='rock',template=10)}
        entrance=p.Profile(99,'existing',frozenset(),{'W':1})
        updates=fit(rows,layer(),cat,set(),{(6,5):99},lambda kind,cell:(frozenset('N'),[('E',entrance)]))
        self.assertEqual(updates,[]);self.assertEqual(rows['5,5']['template'],10)

    def test_rocks_in_a_narrow_pass_use_native_two_sided_geometry(self):
        data=layer(rocks=['5,5','6,5'],walls=['5,4','5,6','6,4','6,6'])
        before=copy.deepcopy(data)
        plan=generate(data,catalogue(),{},p.document(data),'test',{'5,5':'rocks','6,5':'rocks'})
        self.assertEqual({r['template'] for r in plan['placements'].values()},{5})
        self.assertTrue(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(5,5),(5,4),catalogue()))
        self.assertEqual(data,before);self.assertFalse(plan['issues'])

    def test_variety_is_deterministic_and_does_not_change_cells_or_directions(self):
        cat=catalogue();data=layer(rocks=[f'{x},5' for x in range(1,10)],walls=[f'{x},4' for x in range(1,10)])
        base=p.document(data);edits={k:'rocks' for k in base['rocks']};before=copy.deepcopy(base)
        first=generate(data,cat,{},base,'test',edits)
        self.assertEqual({r['template'] for r in first['placements'].values()},{10,11})
        saved=copy.deepcopy(base);saved['boundary_preview']=first;saved['scene_edits']=edits
        again=generate(data,cat,{},saved,'test',edits)
        self.assertEqual({k:r['template'] for k,r in first['placements'].items()},
                         {k:r['template'] for k,r in again['placements'].items()})
        self.assertEqual(again['template_updates'],[]);self.assertEqual(base,before)
        self.assertFalse(first['issues'])

    def test_unsatisfiable_join_does_not_hide_the_scene_or_repaint_a_wall(self):
        data=layer(water=['5,4','6,5','5,6']);data['coast']={(5,5)}
        before=p.document(data);plan=generate(data,catalogue(),{},before,'test',{'5,5':'coast'})
        self.assertIn('5,5',plan['placements']);self.assertEqual(p.document(data),before)
        self.assertIn('manual_direction_conflict',{r['code'] for r in plan['issues']})


if __name__=='__main__':run_cases(Selection)
