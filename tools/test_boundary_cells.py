"""Inspect any live map binding and validate draft-only per-cell spawn moves."""
import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import boundary_cells as c
from testkit import run_cases

class BoundaryCells(unittest.TestCase):
    def setUp(self):
        self.base=({'cell':11,'type':123,'root':1,'name':'Моб'}, {'cell':22,'type':124,'root':1,'name':'Второй'})
        self.geometry=dict(loc=SimpleNamespace(entries=[1]),components={i:0 for i in range(100) if i!=33},exits={2:'N'})
        self.a=patch.object(c,'inhabitants',return_value=self.base);self.a.start()
        self.b=patch('world.location_at',return_value=99);self.b.start()
        self.g=patch.object(c.p,'geometry',return_value=self.geometry);self.g.start()
        self.row={'5,5':dict(location_id=99,spawn_signature=c.signature(99),positions=[12,22])}
    def tearDown(self):self.g.stop();self.b.stop();self.a.stop()
    def test_accepts_valid_move_without_changing_type_or_source(self):
        before=copy.deepcopy(self.row);self.assertEqual(c.validate_overrides(self.row,(0,0,10,10)),before)
        self.assertEqual(self.row,before);self.assertEqual(self.base[0]['cell'],11)
    def test_rejects_obstacles_outside_entries_exits_and_occupied_cells(self):
        for target in (33,100,-1,True,1,2,22):
            with self.subTest(target=target):
                row=copy.deepcopy(self.row);row['5,5']['positions'][0]=target
                with self.assertRaises(ValueError):c.validate_overrides(row,(0,0,10,10))
    def test_rejects_isolated_destination(self):
        self.geometry['components'][44]=1;self.row['5,5']['positions'][0]=44
        with self.assertRaises(ValueError):c.validate_overrides(self.row,(0,0,10,10))
    def test_rejects_stale_sources_and_spawn_changes(self):
        for change in ({'location_id':98},{'spawn_signature':'stale'},{'positions':[12]}):
            row=copy.deepcopy(self.row);row['5,5'].update(change)
            with self.assertRaises(ValueError):c.validate_overrides(row,(0,0,10,10))
    def test_rejects_outside_map_and_malformed_documents(self):
        for data in ([],{'bad':{}},{'11,5':self.row['5,5']}):
            with self.assertRaises(ValueError):c.validate_overrides(data,(0,0,10,10))
    def test_each_coordinate_keeps_its_own_positions(self):
        self.row['6,5']=dict(self.row['5,5'],positions=[13,22]);result=c.validate_overrides(self.row,(0,0,10,10))
        self.assertEqual(result['5,5']['positions'][0],12);self.assertEqual(result['6,5']['positions'][0],13)

if __name__=='__main__':run_cases(BoundaryCells)
