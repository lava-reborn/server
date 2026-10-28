"""Report isolation and incomplete/failing runs must never become a green gate."""
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import local_checks as checks


class LocalChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.phase = dict(name='native', code=0, timed_out=False, seconds=1,
                          metrics={'sampled_tree_peak_rss_bytes': None})

    def result(self, **kwargs):
        values = dict(out=self.out, phases=[self.phase], gaps=[], findings=[],
                      before='same', after='same', mode='all', interrupted=False)
        values.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            code = checks.report(**values)
        return code, json.loads((self.out / 'report.json').read_text(encoding='utf-8'))

    def test_regression_names_exist_and_include_current_release_cases(self):
        names = {Path(p).stem for p in checks.suite.suites()}
        self.assertEqual(len(checks.REGRESSION), len(set(checks.REGRESSION)))
        self.assertFalse(set(checks.REGRESSION) - names)
        self.assertTrue({'test_weapon_tooltips', 'test_equipment_release_cap',
                         'test_set_upgrade_transactions', 'test_weapon_requirements',
                         'test_equipment_level_wear', 'test_tester_launcher'}
                        <= set(checks.REGRESSION))

    def test_xml_and_deploy_filter_edits_invalidate_run_fingerprint(self):
        root = self.out / 'source'
        (root / 'client/files').mkdir(parents=True)
        (root / 'deploy').mkdir()
        xml = root / 'client/files/spec.xml'
        policy = root / 'deploy/rsync.filter'
        xml.write_text('<data/>', encoding='utf-8')
        policy.write_text('- logs/\n', encoding='utf-8')
        with patch.object(checks, 'ROOT', root):
            before = checks.fingerprint()
            xml.write_text('<data changed="1"/>', encoding='utf-8')
            after_xml = checks.fingerprint()
            policy.write_text('- logs/\n- dist/\n', encoding='utf-8')
            after_filter = checks.fingerprint()
        self.assertNotEqual(before, after_xml)
        self.assertNotEqual(after_xml, after_filter)

    def test_working_db_and_clock_are_not_inherited(self):
        with patch.dict(os.environ, {'LAVA_DB_URL': 'postgresql://remote/production',
                                     'LAVA_SCHEDULE': 'other.json', 'LAVA_BOSS_CLOCK': 'old'}):
            env = checks.clean_env(self.out, self.out / 'missing', self.out / 'missing.swf')
        self.assertNotIn('LAVA_DB_URL', env)
        self.assertNotIn('LAVA_SCHEDULE', env)
        self.assertNotIn('LAVA_BOSS_CLOCK', env)
        self.assertIn('ResourceWarning', env['PYTHONWARNINGS'])

    def test_installed_map_assets_are_reported_without_replacing_them(self):
        repo = self.out / 'repo'
        (repo / 'client').mkdir(parents=True)
        res = self.out / 'res'
        (res / 'globalmap' / 'full').mkdir(parents=True)
        tile = res / 'globalmap' / 'full' / '1.jpg'
        tile.write_bytes(b'painted')
        digest = hashlib.sha256(b'original').hexdigest()
        (repo / 'client' / 'base.txt').write_bytes(
            ('lava-base 1\r\n%s\t8\tglobalmap/full/1.jpg\r\n' % digest).encode())
        with patch.object(checks, 'ROOT', repo):
            problems = checks.asset_inputs(res)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]['reason'], 'differs from client/base.txt')
        self.assertEqual(tile.read_bytes(), b'painted')

    def test_known_failure_is_preserved_even_if_ci_stage_succeeds(self):
        shard = self.out / 'ci' / 'shards' / '1'
        shard.mkdir(parents=True)
        (shard / 'summary.txt').write_text('1 3s test_example\nDONE\n', encoding='utf-8')
        code, report = self.result()
        self.assertEqual(code, 1)
        self.assertTrue(report['failed'])
        self.assertFalse(report['ready_for_review'])

    def test_skip_with_exit_zero_is_incomplete(self):
        (self.out / 'test_example.out').write_text('SKIP: missing fixture\n', encoding='utf-8')
        code, report = self.result()
        self.assertEqual(code, 2)
        self.assertFalse(report['ready_for_review'])

    def test_linux_flash_skip_requires_actual_native_success(self):
        (self.out / 'native').mkdir()
        (self.out / 'native' / 'summary.txt').write_text('0 5s test_flash\nDONE\n', encoding='utf-8')
        (self.out / 'ci').mkdir()
        (self.out / 'ci' / 'test_flash.out').write_text('SKIP: Flash needs Windows\n', encoding='utf-8')
        code, report = self.result()
        self.assertEqual(code, 0)
        self.assertEqual(report['skipped'][0]['covered_by'], 'native/test_flash')

    def test_warning_and_source_change_require_review(self):
        (self.out / 'native.err').write_text('ResourceWarning: unclosed database\n', encoding='utf-8')
        code, report = self.result(after='changed')
        self.assertEqual(code, 2)
        self.assertFalse(report['ready_for_review'])
        self.assertTrue(report['warnings'])

    def test_every_security_finding_is_retained(self):
        findings = [dict(scanner='bandit', id='B101', text='review'),
                    dict(scanner='pip_audit', id='EXAMPLE-1', text='review')]
        code, report = self.result(findings=findings)
        self.assertEqual(code, 1)
        self.assertEqual(report['security_findings'], findings)

    def test_partial_mode_cannot_satisfy_pre_push_gate(self):
        code, report = self.result(mode='regression')
        self.assertEqual(code, 2)
        self.assertFalse(report['ready_for_review'])


if __name__ == '__main__':
    unittest.main()
