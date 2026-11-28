import copy,hashlib,json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import boundary_world as b

class BoundaryWorld(unittest.TestCase):
    def setUp(self):
        self.doc={'version':1,'cells':{'4,4':dict(id=32772,template=6,spawns=[(5,98)],allowed_exits=['S'],boundary=True,no_map=True,portals={})},'blocked':['3,4'],'regions':{'eden':['4,5']}}
        self.patcher=patch.object(b,'manifest',return_value=self.doc);self.patcher.start()
        for fn in (b.by_id,b.blocked_cells,b.regions,b.overlay_path):fn.cache_clear()
    def tearDown(self):
        self.patcher.stop()
        for fn in (b.by_id,b.blocked_cells,b.regions,b.overlay_path):fn.cache_clear()
    def test_two_faces_depth_and_administrative_isolation(self):
        self.assertFalse(b.crossing((4,4),(3,4)))
        self.assertFalse(b.crossing((4,4),(5,4)))
        self.assertFalse(b.crossing((4,4),(4,5)))
        self.doc['regions']={};b.regions.cache_clear()
        self.assertTrue(b.crossing((4,4),(4,5)))
        self.assertTrue(b.crossing((4,5),(4,4)))
        self.assertFalse(b.crossing((4,4),(5,5)))
    def test_xml_keeps_art_and_collision_but_no_exits_into_depth(self):
        raw=b'<location width="4" height="4" library="Mountains"><obstacles>00001</obstacles><outzones>01002010340102a</outzones><mobs>02020000</mobs></location>'
        record=copy.deepcopy(self.doc['cells']['4,4']);record['portals']={'N':dict(side='b')}
        xml=b.xml_bytes(record,raw)
        self.assertIn(b'library="Mountains"',xml);self.assertIn(b'<obstacles>00001</obstacles>',xml)
        self.assertIn(b'<outzones>0100b01034</outzones>',xml)
        self.assertIn(b'<mobs>01010062</mobs>',xml)
    def test_client_definitions_replace_native_and_add_packed_unique_instance(self):
        record=self.doc['cells']['4,4'];record.update(md5='a'*32,size=123)
        raw=b'<data><file href="locations/static/6.xml" hash="native" size="10" /></data>'
        xml=b.loc_defs(raw)
        self.assertIn(b'href="locations/static/32772.xml"',xml)
        self.assertIn(b'hash="native"',xml)
        twice=b.loc_defs(xml);self.assertEqual(twice.count(b'static/32772.xml'),1)

    def test_exit_zone_formatting_does_not_change_native_exit_meaning(self):
        raw=b'<location width="4"><outzones>\n 01002\n 01034\n</outzones><mobs></mobs></location>'
        result=b.xml_bytes(self.doc['cells']['4,4'],raw)
        self.assertIn(b'<outzones>01034</outzones>',result)
        with self.assertRaisesRegex(ValueError,'exit zones'):
            b.xml_bytes(self.doc['cells']['4,4'],raw.replace(b'01034',b'0103'))
    def test_subcell_collision_stops_before_native_rock(self):
        self.doc['cells']={};self.doc['blocked']=[];self.doc['regions']={}
        with patch.object(b,'point_open',side_effect=lambda x,y:x<4.75):
            x,y=b.clip_walk(4.5,4.5,4.95,4.5)
        self.assertLess(x,4.75);self.assertGreater(x,4.74);self.assertEqual(y,4.5)
    def test_diagonal_cannot_squeeze_past_a_blocked_corner(self):
        self.doc['cells']={};self.doc['regions']={};self.doc['blocked']=['5,4'];b.blocked_cells.cache_clear()
        with patch.object(b,'point_open',return_value=True):
            x,y=b.clip_walk(4.5,4.5,5.5,5.5)
        self.assertLess(x,5);self.assertLess(y,5)
    def test_map_disabled_for_tunnel_and_unique_coordinate_identity(self):
        self.assertTrue(b.no_map(32772));self.assertEqual(b.coordinate(32772),(4,4))
        self.assertFalse(b.no_map(6));self.assertIsNone(b.coordinate(6))

    def test_scheduled_declarations_survive_without_changing_visible_roster(self):
        record=copy.deepcopy(self.doc['cells']['4,4']);record['scheduled_spawns']=[(10,6521)]
        raw=b'<location width="4" height="4"><outzones>01034</outzones><mobs></mobs></location>'
        result=b.xml_bytes(record,raw)
        self.assertIn(b'<mobs>0101006202021979</mobs>',result)
        self.assertEqual(record['spawns'],[(5,98)])

    def test_compiled_spawns_are_validated_per_coordinate_against_native_collision(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'native.xml';path.write_text('<location width="4" height="4"><obstacles>00001</obstacles></location>')
            with patch('world.source_path_for',return_value=str(path)):
                self.assertEqual(b.validation_problems({98:(0,98,'guard')}),[])
                self.doc['cells']['4,4']['spawns']=[(0,98)]
                self.assertTrue(any('obstacle' in s for s in b.validation_problems({98:(0,98,'guard')})))

if __name__=='__main__':unittest.main()
