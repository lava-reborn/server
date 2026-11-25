"""Persist only the local tester clock, including recovery and failed writes."""
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import bosses
from testkit import run_cases


class TestClock(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.database = Path(self.tmp) / 'tester.sqlite'
        self.database.write_bytes(b'untouched game state')
        self.saved = Path(str(self.database) + '.test-clock.json')
        self.enterContext(patch.dict(os.environ, {'LAVA_BOSS_CLOCK': ''}))
        self.enterContext(patch.object(bosses, '_OFFSET', 0))
        self.enterContext(patch.object(bosses.time, 'time', return_value=1800000000))

    def test_restart_restores_saved_offset_without_touching_database(self):
        bosses.save_test_offset(self.database, 86400.25)
        self.assertEqual(bosses.restore_test_offset(self.database), 86400.25)
        self.assertEqual(self.database.read_bytes(), b'untouched game state')
        self.assertEqual(list(Path(self.tmp).glob('*.tmp')), [])
        bosses.save_test_offset(self.database, 0)
        self.assertEqual(bosses.restore_test_offset(self.database, [1801000000]), 0)

    def test_explicit_clock_and_nonfile_databases_never_read_or_write_sidecars(self):
        with patch.object(bosses, '_OFFSET', 37), patch.dict(os.environ, {'LAVA_BOSS_CLOCK': '2027-01-01'}):
            self.assertEqual(bosses.restore_test_offset(self.database), 37)
        for database in (None, '', ':memory:', 'file:test?mode=memory', 'postgresql://localhost/game'):
            with self.subTest(database=database):
                bosses.save_test_offset(database, 27)
                self.assertEqual(bosses.restore_test_offset(database, [1801000000]), 0)
        self.assertFalse(self.saved.exists())

    def test_recovers_future_capture_once_and_ignores_malformed_slots(self):
        slots = [None, 'broken', float('nan'), float('inf'), 1799999999, 1800000020, 1800000010]
        self.assertEqual(bosses.restore_test_offset(self.database, slots), 21)
        self.assertEqual(bosses.restore_test_offset(self.database, [1800010000]), 21)
        self.assertEqual(self.database.read_bytes(), b'untouched game state')

    def test_corrupt_sidecar_can_recover_but_never_applies_invalid_offsets(self):
        for data in ('broken', '[]', '{"version":2,"offset":1}', '{"version":1}',
                     '{"version":1,"offset":null}', '{"version":1,"offset":"NaN"}'):
            with self.subTest(data=data):
                self.saved.write_text(data, encoding='utf-8')
                self.assertEqual(bosses.restore_test_offset(self.database), 0)
                self.assertEqual(bosses.restore_test_offset(self.database, [1800000040]), 41)

    def test_failed_replace_preserves_previous_clock_and_removes_temporary(self):
        bosses.save_test_offset(self.database, 10)
        old = self.saved.read_bytes()
        with patch.object(bosses.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                bosses.save_test_offset(self.database, 20)
        self.assertEqual(self.saved.read_bytes(), old)
        self.assertEqual(list(Path(self.tmp).glob('*.tmp')), [])
        for invalid in (float('nan'), float('inf'), -float('inf'), 1e100):
            with self.subTest(offset=invalid):
                with self.assertRaises((ValueError, OverflowError, OSError)):
                    bosses.save_test_offset(self.database, invalid)
                self.assertEqual(self.saved.read_bytes(), old)

    def test_server_startup_restores_only_cheats_sqlite_clock(self):
        database = Path(self.tmp) / 'startup.sqlite'
        bosses.save_test_offset(database, 123.25)
        env = {k: v for k, v in os.environ.items()
               if k not in ('LAVA_DB_URL', 'LAVA_BOSS_CLOCK')}
        env.update(LAVA_DB=str(database), PYTHONDONTWRITEBYTECODE='1')
        script = ('import json, bosses, server; '
                  'print("CLOCK=" + json.dumps(bosses._OFFSET)); server.STORE.close()')
        for enabled, expected in (('0', 0), ('1', 123.25), ('0', 0)):
            with self.subTest(cheats=enabled):
                result = subprocess.run([sys.executable, '-B', '-c', script],
                    cwd=Path(__file__).resolve().parent,
                    env=dict(env, LAVA_CHEATS=enabled), capture_output=True,
                    text=True, encoding='utf-8', timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                clock = next(line[6:] for line in result.stdout.splitlines() if line.startswith('CLOCK='))
                self.assertEqual(json.loads(clock), expected)
        self.assertEqual(json.loads(Path(str(database) + '.test-clock.json').read_text())['offset'], 123.25)

    def test_failed_recovery_does_not_advance_unsaved_clock(self):
        with patch.object(bosses, 'save_test_offset', side_effect=OSError('disk full')):
            self.assertEqual(bosses.restore_test_offset(self.database, [1800000040]), 0)
        self.assertEqual(bosses._OFFSET, 0)


if __name__ == '__main__':
    run_cases(TestClock)
