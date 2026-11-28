"""Validate the shipped world through real XML, room and travel code."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from testkit import run_cases


class ShippedBoundarySnapshot(unittest.TestCase):
    def test_all_instances_keep_native_collision_and_reciprocal_reachable_exits(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'runtime.json'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/audit_boundary_runtime.py'),
                '--manifest',str(ROOT/'data/boundary_world.json'),'--out',str(out)],
                cwd=ROOT,env=dict(os.environ),capture_output=True,text=True,timeout=600)
            self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-8000:])
            report=json.loads(out.read_bytes())
            self.assertGreater(report['instances'],10000)
            self.assertGreater(report['counts']['transitions'],40000)
            self.assertEqual(report['errors'],[])

    def test_every_original_inhabitant_keeps_its_type_and_hex(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'population.json';draft=ROOT/'data/boundary_editor_draft.json'
            result=subprocess.run([sys.executable,'-B',str(ROOT/'tools/audit_boundary_population.py'),
                '--manifest',str(ROOT/'data/boundary_world.json'),'--draft',str(draft),
                '--previous-draft',str(draft),'--out',str(out)],
                cwd=ROOT,env=dict(os.environ),capture_output=True,text=True,timeout=600)
            self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-8000:])
            report=json.loads(out.read_bytes())
            self.assertGreater(report['original_identities_checked'],10000)
            # The approved single 3x3 camp footprints remove old peripheral
            # populated cells. The exact roster is checked by the audit below;
            # this floor only detects an absent/incomplete native fixture.
            self.assertGreater(report['original_inhabited_identities'],1100)
            self.assertEqual(set(map(int,report['new_combat_actors'])),{98,130,2418,2419,2420})
            self.assertEqual(report['errors'],[])


if __name__=='__main__':run_cases(ShippedBoundarySnapshot)
