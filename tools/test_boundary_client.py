"""Offline releases contain independent XML bindings and no editor graphics."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'client'),str(Path(__file__).resolve().parents[1]/'server')]
import build

class BoundaryClient(unittest.TestCase):
    def test_release_registers_packed_instance_and_shares_native_graphics(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir();record=dict(id=40965,template=6,spawns=[[5,98]],allowed_exits=['S'],portals={})
            (root/'data/boundary_world.json').write_text(json.dumps(dict(version=1,cells={'5,5':record})))
            raw=b'<location width="4" height="4" library="Mountains"><obstacles>00001</obstacles><outzones>0100201034</outzones><mobs></mobs></location>'
            originals={'locations/static/6.xml':raw,'xml/loc_defs.xml':b'<data></data>'}
            fixture=SimpleNamespace(tree=str(root),cdir=str(root/'client'),original=lambda path:originals[path])
            files=build.Build.gen_overlay_locations(fixture)
            self.assertEqual(set(files),{'locations/static/40965.xml','xml/loc_defs.xml'})
            xml=files['locations/static/40965.xml'];self.assertIn(b'library="Mountains"',xml)
            self.assertIn(b'<outzones>01034</outzones>',xml);self.assertIn(b'<mobs>01010062</mobs>',xml)
            self.assertIn(hashlib.md5(xml).hexdigest().encode(),files['xml/loc_defs.xml'])
            self.assertFalse(any('globalmap' in p or 'editor' in p for p in files))

if __name__=='__main__':unittest.main()
