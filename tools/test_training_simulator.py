"""CI contract for the pinned simulator port; no network, battles or account DB."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'server')]
from export_training_simulator import encode_snapshot


class SnapshotContract(unittest.TestCase):
    def test_exported_reference_cases_match_the_runtime_port(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/check_training_simulator.py')],
                                env=dict(os.environ, LAVA_DB=':memory:', LAVA_DB_URL=''),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = json.loads(result.stdout)
        self.assertEqual(result['engine'], 'simulator-v1')
        self.assertEqual(result['golden_cases'], 108)
        self.assertGreater(result['equipment'], 1000)
        for key, minimum in dict(ranged=100, melee=18, critical=24, calibrated=2, mobs=200).items():
            self.assertGreaterEqual(result['equations'][key], minimum)

    def test_snapshot_is_canonical_and_records_its_source_inputs(self):
        path = ROOT / 'data/training_simulator_formulas.json'
        text = path.read_text(encoding='utf-8')
        raw = json.loads(text)
        self.assertEqual(encode_snapshot(raw), text)
        self.assertEqual(raw['engine'], 'simulator-v1')
        self.assertRegex(raw['source_commit'], r'^[0-9a-f]{40}$')
        self.assertNotIn('commit', raw)
        self.assertEqual(set(raw['source_hashes']), {'rulesets/lava.py', 'rulesets/lava_fixed.py',
                                                    'data/lava/snapshot.json', 'data/lava/fixed_rules.json'})
        self.assertTrue(all(len(digest) == 64 for digest in raw['source_hashes'].values()))

    def test_equation_cases_are_separate_canonical_and_pinned_to_runtime_snapshot(self):
        path = ROOT / 'data/training_simulator_cases.json'
        text = path.read_text(encoding='utf-8')
        cases = json.loads(text)
        snapshot = json.loads((ROOT / 'data/training_simulator_formulas.json').read_text(encoding='utf-8'))
        self.assertEqual(encode_snapshot(cases), text)
        self.assertEqual(cases['source_commit'], snapshot['source_commit'])
        self.assertTrue(cases['calibrated'])
        self.assertTrue(all(row['calibration']['weapon_scale'] and row['calibration']['class_scale']
                            for row in cases['calibrated']))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(SnapshotContract)
