"""Manual assignments are authoritative, warnings never erase scenes or bypass geometry."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_manual as manual
import boundary_planner as p
from test_boundary_planner import catalogue,layer
from testkit import run_cases

class ManualBoundary(unittest.TestCase):
    def make(self,layers,edits=None,base=None,special=None):
        return manual.generate(layers,catalogue(),special or {},base or p.document(layers),'test',edits or {})
    def test_rock_on_a_former_depth_wall_is_installed_instead_of_rejected(self):
        data=layer(rocks=['5,5','6,5'],walls=['5,4','5,6','4,5'])
        base=p.document(data);base['boundary_preview']={'generated_walls':['5,5','6,5'],'placements':{}}
        before=copy.deepcopy(base);plan=self.make(data,{'5,5':'rocks'},base)
        self.assertIn('5,5',plan['placements']);self.assertNotIn('5,5',plan['generated_walls'])
        self.assertIn('6,5',plan['generated_walls']);self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertEqual(base,before)
    def test_isolated_or_incompatible_manual_scene_is_kept_with_warnings(self):
        data=layer(rocks=['5,5'],walls=['5,4','6,5','5,6','4,5'],overrides={'5,5':10})
        plan=self.make(data,{'5,5':'rocks'})
        self.assertEqual(plan['placements']['5,5']['template'],10)
        self.assertEqual(plan['placements']['5,5']['allowed_exits'],[])
        self.assertIn('no_safe_return',{r['code'] for r in plan['issues']})
        self.assertTrue(p.passable(data,plan,(5,5)))
    def test_unrelated_locations_and_depth_are_not_rebuilt(self):
        data=layer(rocks=['2,2','8,8'],walls=['9,8'])
        base=p.document(data);base['boundary_preview']={'placements':{'2,2':{'template':10,'kind':'rock'}},'generated_walls':['8,8']}
        plan=self.make(data,{'5,5':'wall'},base)
        self.assertEqual(plan['placements']['2,2']['template'],10)
        self.assertEqual(plan['generated_walls'],['8,8'])
        self.assertNotIn('5,4',plan['placements']);self.assertNotIn('5,6',plan['placements'])
    def test_later_neighbour_edits_do_not_rechoose_an_explicitly_pinned_map(self):
        old=layer(rocks=['5,5'],overrides={'5,5':10});base=p.document(old);base['scene_edits']={'5,5':'rocks'}
        base['boundary_preview']={'placements':{'5,5':{'kind':'rock','template':10,'manual':True}},'generated_walls':[]}
        current=layer(rocks=['5,5'],walls=['4,5'],overrides={'5,5':10});plan=self.make(current,{'5,5':'rocks','4,5':'wall'},base)
        self.assertEqual(plan['placements']['5,5']['template'],10)
        self.assertIn('manual_direction_conflict',{r['code'] for r in plan['issues']})

    def test_changed_water_refits_a_straight_shore_to_a_corner_without_repainting(self):
        old=layer(water=['5,6']);old['coast']={(5,5)}
        base=p.document(old);base['scene_edits']={'5,5':'coast'}
        base['boundary_preview']={'placements':{'5,5':{'kind':'coast','template':18,'manual':True}}}
        current=layer(water=['5,6','6,5']);current['coast']={(5,5)}
        before=p.document(current);plan=self.make(current,{'5,5':'coast','6,5':'water'},base)
        self.assertEqual(plan['placements']['5,5']['template'],21)
        self.assertEqual(plan['placements']['5,5']['closed'],['E','S'])
        self.assertEqual(plan['template_updates'],[dict(cell='5,5',previous=18,template=21)])
        self.assertEqual(p.document(current),before)
        self.assertFalse(any(r['cell']=='5,5' for r in plan['issues']))
        self.assertFalse(p.can_step(current,plan,(5,5),(6,5),catalogue()))
        self.assertFalse(p.can_step(current,plan,(5,5),(5,6),catalogue()))

    def test_saved_stale_auto_choice_is_refitted_once_and_then_stays_stable(self):
        data=layer(water=['5,6','6,5']);data['coast']={(5,5)}
        base=p.document(data);base['scene_edits']={'5,5':'coast'}
        base['boundary_preview']={'placements':{'5,5':{'kind':'coast','template':18,'manual':True}}}
        before=copy.deepcopy(base);plan=self.make(data,{'5,5':'coast'},base)
        self.assertEqual(plan['placements']['5,5']['template'],21)
        self.assertEqual(base,before)
        saved=copy.deepcopy(base);saved['boundary_preview']=plan
        again=self.make(data,{'5,5':'coast'},saved)
        self.assertEqual(again['placements']['5,5']['template'],21)
        self.assertEqual(again['template_updates'],[])

    def test_auto_refit_keeps_a_conflict_when_no_exact_compatible_map_exists(self):
        data=layer(water=['5,6','6,5']);data['coast']={(5,5)}
        base=p.document(data);base['scene_edits']={'5,5':'coast'}
        base['boundary_preview']={'placements':{'5,5':{'kind':'coast','template':18}}}
        plan=manual.generate(data,{18:catalogue()[18]}, {},base,'test',{'5,5':'coast'})
        self.assertEqual(plan['placements']['5,5']['template'],18)
        self.assertEqual(plan['template_updates'],[])
        self.assertIn('manual_direction_conflict',{r['code'] for r in plan['issues']})

    def test_new_cell_chooses_matching_native_exit_without_changing_its_neighbour(self):
        catalog={10:p.Profile(10,'rock',frozenset('N'),{'E':3,'W':12,'S':15}),
                 11:p.Profile(11,'rock',frozenset('N'),{'E':12,'W':3,'S':15})}
        data=layer(rocks=['5,5','6,5'],walls=['5,4','6,4'],overrides={'6,5':10})
        base=p.document(data);base['boundary_preview']={'placements':{'6,5':{'kind':'rock','template':10}}}
        before=copy.deepcopy(base)
        plan=manual.generate(data,catalog,{},base,'test',{'5,5':'rocks'})
        self.assertEqual(plan['placements']['5,5']['template'],11)
        self.assertEqual(plan['placements']['6,5']['template'],10)
        self.assertIn('E',plan['placements']['5,5']['allowed_exits'])
        self.assertIn('W',plan['placements']['6,5']['allowed_exits'])
        self.assertFalse(any(r['code']=='incompatible_neighbour' for r in plan['issues']))
        self.assertEqual(base,before)

    def test_wrong_direction_is_reported_without_changing_the_exact_template(self):
        data=layer(water=['4,5'],overrides={'5,5':17})
        plan=self.make(data)
        self.assertEqual(plan['placements']['5,5']['template'],17)
        self.assertIn('manual_direction_conflict',{r['code'] for r in plan['issues']})
    def test_two_layers_keep_river_and_native_closed_face_impassable(self):
        data=layer(water=['6,5'],overrides={'5,5':22})
        plan=self.make(data)
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(6,5),(5,5),catalogue()))
        self.assertTrue(p.can_step(data,plan,(5,5),(4,5),catalogue()))
        # Without a painted wall the native closed face still marks its backing as depth.
        data=layer(overrides={'5,5':22});plan=self.make(data)
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(6,5),(5,5),catalogue()))
    def test_warning_does_not_block_valid_sides_and_incompatible_seam_never_opens(self):
        data=layer(overrides={'5,5':10});plan=self.make(data)
        self.assertTrue(p.can_step(data,plan,(5,5),(5,6),catalogue()))
        data=layer(overrides={'5,5':10,'6,5':12});plan=self.make(data)
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertIn('incompatible_neighbour',{r['code'] for r in plan['issues']})
    def test_existing_place_overlap_is_allowed_but_visible(self):
        data=layer(overrides={'5,5':10});data['_preserved_land']={(5,5)}
        plan=self.make(data,special={(5,5):999})
        self.assertIn('5,5',plan['placements']);self.assertNotIn('5,5',plan['preserved_land'])
        self.assertIn('existing_location_overlap',{r['code'] for r in plan['issues']})
    def test_eden_does_not_gain_a_world_exit_or_crocodiles(self):
        data=layer(overrides={'5,5':10});data['_regions']={(5,5):'eden',(5,6):'eden'};data['_mask_regions']={'eden'}
        plan=self.make(data)
        self.assertEqual(plan['placements']['5,5']['spawn_policy'],'none')
        self.assertFalse(p.can_step(data,plan,(5,5),(4,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(5,5),(5,4),catalogue()))
        self.assertTrue(p.can_step(data,plan,(5,5),(5,6),catalogue()))
    def test_cleared_wall_and_shore_do_not_return(self):
        data=layer(overrides={'5,5':None});base=p.document(data)
        base['boundary_preview']={'generated_walls':['5,5'],'placements':{'5,5':{'kind':'rock','template':10}}}
        plan=self.make(data,{'5,5':'erase'},base)
        self.assertNotIn('5,5',plan['placements']);self.assertNotIn('5,5',plan['generated_walls'])
        self.assertTrue(p.passable(data,plan,(5,5)))
    def test_erased_depth_mark_is_kept_and_warned_without_opening_native_backing(self):
        data=layer(overrides={'5,5':22,'6,5':None});base=p.document(data)
        base['scene_edits']={'6,5':'erase'}
        before=copy.deepcopy(base)
        plan=self.make(data,{'6,5':'erase'},base)
        self.assertIn('6,5',plan['depth_cells'])
        self.assertNotIn('6,5',plan['placements'])
        self.assertTrue(any(r['cell']=='6,5' and r['code']=='manual_depth_conflict' for r in plan['issues']))
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(5,5),(6,5),catalogue()))
        self.assertEqual(base,before)

    def test_three_rock_cells_connect_along_the_front_but_second_row_is_closed(self):
        data=layer(rocks=['4,4','5,4','6,4','5,5'],overrides={'4,4':15,'5,4':15,'6,4':15,'5,5':15})
        plan=self.make(data)
        self.assertTrue(p.can_step(data,plan,(4,4),(5,4),catalogue()))
        self.assertTrue(p.can_step(data,plan,(5,4),(6,4),catalogue()))
        self.assertFalse(p.passable(data,plan,(5,5)))
        self.assertFalse(p.can_step(data,plan,(5,4),(5,5),catalogue()))
        self.assertIn('5,5',plan['placements'])
        self.assertTrue(any(r['cell']=='5,5' and r['code']=='scene_inside_depth' for r in plan['issues']))
    def test_explicit_wall_outline_preserves_source_marks_and_existing_places(self):
        data=layer(water=['6,5'],walls=['5,5']);base=p.document(data)
        result=manual.outline_walls(data,catalogue(),{(4,5):999},base,edits={'5,4':'erase'})
        self.assertNotIn('4,5',result['additions']);self.assertNotIn('5,4',result['additions'])
        self.assertNotIn('5,5',result['additions']);self.assertNotIn('6,5',result['additions'])
        self.assertTrue(any(r['kind']=='rock' for r in result['additions'].values()))
        self.assertTrue(any(r['kind']=='coast' for r in result['additions'].values()))
        self.assertEqual(p.document(data),base)
        for key,row in result['additions'].items():
            self.assertEqual(result['plan']['placements'][key]['template'],row['template'])
    def test_native_dry_corners_connect_a_wall_rim_without_opening_its_depth(self):
        cat=catalogue();edges={s:(1<<p.BINS)-1 for s in p.STEP}
        cat[51]=p.Profile(51,'rock',frozenset(),edges)
        cat[30]=p.Profile(30,'coast',frozenset(),edges)
        data=layer(walls=['5,5']);result=manual.outline_walls(data,cat,{},p.document(data))
        plan=result['plan'];traversal=layer(rocks=list(result['additions']),walls=['5,5'])
        self.assertEqual(plan['placements']['4,4']['template'],51)
        self.assertTrue(p.can_step(traversal,plan,(4,4),(5,4),cat))
        self.assertTrue(p.can_step(traversal,plan,(4,4),(4,5),cat))
        self.assertFalse(p.passable(traversal,plan,(5,5)))
        self.assertFalse(any(k in plan['depth_cells'] for k in result['additions']))

    def test_eden_one_cell_inset_is_a_single_ring_and_keeps_isolation(self):
        cells={(x,y) for x in range(3,8) for y in range(3,8)}
        ring=manual.eden_outer_ring(cells)
        self.assertEqual(len(ring),16);self.assertEqual(cells-ring,{(x,y) for x in range(4,7) for y in range(4,7)})
        data=layer();data['_retired_existing']=ring;data['_preserved_land']=cells-ring
        data['_regions']={c:'eden' for c in cells};data['_mask_regions']={'eden'}
        plan=self.make(data)
        self.assertFalse(p.passable(data,plan,(3,5)));self.assertTrue(p.passable(data,plan,(4,5)))
        self.assertFalse(p.can_step(data,plan,(4,5),(3,5),catalogue()))
        self.assertFalse(p.can_step(data,plan,(3,5),(2,5),catalogue()))

    def test_retired_eden_palms_can_be_replaced_by_shore_without_false_conflicts(self):
        data=layer(water=['6,5'],overrides={'5,5':22})
        data['_retired_existing']={(5,5),(5,6)};data['_preserved_land']={(4,5)}
        data['_regions']={(4,5):'eden',(5,5):'eden',(5,6):'eden'};data['_mask_regions']={'eden'}
        plan=self.make(data,{'5,5':'coast'},special={(5,5):999})
        codes={r['code'] for r in plan['issues'] if r['cell']=='5,5'}
        self.assertNotIn('existing_location_overlap',codes)
        self.assertNotIn('scene_inside_depth',codes);self.assertNotIn('no_safe_return',codes)
        self.assertTrue(p.passable(data,plan,(5,5)))
        self.assertTrue(p.can_step(data,plan,(5,5),(4,5),catalogue()))
        self.assertTrue(p.can_step(data,plan,(4,5),(5,5),catalogue()))
        self.assertFalse(p.passable(data,plan,(5,6)))
        self.assertFalse(p.passable(data,plan,(6,5)))
        self.assertFalse(p.can_step(data,plan,(5,5),(5,4),catalogue()))
        self.assertEqual(plan['placements']['5,5']['spawn_policy'],'none')

    def test_eden_replacement_still_reports_real_native_depth_and_npc_conflicts(self):
        data=layer(overrides={'4,4':22,'5,4':22,'4,5':22})
        data['_retired_existing']={(4,4),(5,4)}
        data['_regions']={(4,4):'eden',(5,4):'eden',(4,5):'eden'};data['_mask_regions']={'eden'}
        plan=self.make(data,special={(4,4):999,(5,4):998,(4,5):997})
        self.assertTrue(any(r['cell']=='5,4' and r['code']=='scene_inside_depth' for r in plan['issues']))
        self.assertFalse(p.passable(data,plan,(5,4)))
        self.assertFalse(any(r['cell']=='5,4' and r['code']=='existing_location_overlap' for r in plan['issues']))
        self.assertTrue(any(r['cell']=='4,5' and r['code']=='existing_location_overlap' for r in plan['issues']))
        self.assertTrue(all(r['spawn_policy']=='none' for r in plan['placements'].values()))

    def test_manual_layer_is_a_format_check_not_a_geometric_gate(self):
        self.assertEqual(manual.scene_edits({'scene_edits':{'5,5':'rocks'}},(0,0,10,10)),{'5,5':'rocks'})
        for value in ({'11,5':'rocks'},{'5,5':'unknown'},[]):
            with self.assertRaises(ValueError):manual.scene_edits({'scene_edits':value},(0,0,10,10))

if __name__=='__main__':run_cases(ManualBoundary)
