"""Complete-complex projection preserves source portals, services and native geometry."""
import copy,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'server')]
import boundary_planner as p
import boundary_complexes as c
from testkit import run_cases

class Complexes(unittest.TestCase):
    def test_projection_preserves_native_points_without_synthesizing_more_service_rooms(self):
        raw={(6015,1747):598,(6017,1747):623,(6016,1742):599,(6008,1742):117}
        original=copy.deepcopy(raw);layers=p.normalise({'mountain_complexes':{'halfa':[6015,1747]}},(5833,1600,6335,2143))
        layers['_preserved_land']=set(raw);special=c.project(layers,raw)
        self.assertEqual(raw,original)
        for cell,ident in raw.items():self.assertEqual(special[cell],ident)
        self.assertEqual(special,raw)
        self.assertEqual(layers['_retired_complex_sources'],set())
        self.assertEqual(layers['_complex_bindings'],{})

    def test_manifest_roundtrip_and_validation(self):
        bounds=(5833,1600,6335,2143);doc={'mountain_complexes':{'halfa':[6016,1747],'abu':[6211,1948]}}
        layers=p.normalise(doc,bounds);self.assertEqual(p.document(layers)['mountain_complexes'],doc['mountain_complexes'])
        for value in ([],{'unknown':[6000,1800]},{'halfa':[True,1700]},{'abu':[5833,1600]}):
            with self.assertRaises(ValueError):p.normalise({'mountain_complexes':value},bounds)

    def test_portal_designs_use_free_native_cells_and_preserve_original_targets(self):
        import travel
        layers=p.normalise({'mountain_complexes':{'halfa':[6016,1747]}},(5833,1600,6335,2143));layers['_preserved_land']=set()
        c.project(layers,{(6015,1747):598,(6017,1747):623})
        rows={'6015,1747':{'template':6},'6017,1747':{'template':13}}
        c.annotate(rows,layers)
        for row in rows.values():
            self.assertEqual(row['portal_sides'],['N']);g=p.geometry(row['template'])
            self.assertEqual(row['source_doors']['a'],travel.door(row['source_location'],'a'))
            for door in row['door_designs']:
                self.assertTrue(door['cells']);self.assertTrue(all(g['components'].get(n)==g['main'] and g['exits'][n]=='N' for n in door['cells']))

    def test_portal_pairs_arrive_on_native_free_connected_hexes_and_unknown_door_stays_disabled(self):
        import travel
        layers=p.normalise({'mountain_complexes':{'halfa':[6016,1747],'abu':[6211,1948]}},(5833,1600,6335,2143))
        layers['_preserved_land']=set()
        c.project(layers,{(5908,2001):162,(6015,1747):598,(6017,1747):623,(6210,1948):163,(6212,1948):53})
        rows={p.cell_key(cell):{'template':6 if ident in (598,163) else 13} for cell,ident in layers['_special'].items() if ident in (598,623,163,53)}
        g=p.geometry(6);rows['5908,2001']=dict(template=6,mountain_trail=True,source_location=162,source_doors={'b':travel.door(162,'b')},door_designs=[dict(source_side='b',target_loc_id=598,side='N',cells=[n for n,side in g['exits'].items() if side=='N'])])
        c.annotate(rows,layers);links=c.links(layers,{'placements':rows})
        self.assertEqual(sum(row['enabled'] for row in links),4)
        self.assertEqual([row['source_location'] for row in links if not row['enabled']],[163])
        for row in links:
            if row['enabled']:
                target=p.geometry(row['target_template']);n=row['arrival_hex']
                self.assertNotIn(n,target['loc'].obstacles);self.assertEqual(target['components'][n],target['main'])
                self.assertNotIn(n,target['exits'])

    def test_reserved_portal_side_cannot_step_into_an_unrelated_global_neighbour(self):
        layers=p.normalise({},(0,0,10,10));catalog,_=p.native_catalog()
        plan=dict(placements={'5,5':dict(template=15,portal_sides=['N'])},issues=[],generated_walls=[],effective_water=[])
        self.assertFalse(p.can_step(layers,plan,(5,5),(5,4),catalog))
        self.assertFalse(p.can_step(layers,plan,(5,4),(5,5),catalog))
        self.assertTrue(p.can_step(layers,plan,(5,5),(6,5),catalog))
        self.assertTrue(p.can_step(layers,plan,(6,5),(5,5),catalog))

if __name__=='__main__':run_cases(Complexes)
