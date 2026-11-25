"""Online buff checkpoints and migration on the configured SQL dialect."""
import logging
logging.disable(logging.CRITICAL)
import unittest
import uuid
from unittest.mock import patch

import accounts
import storage
from testkit import run_cases


class EffectClockStorage(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        aid, _ = self.store.register('clock-' + uuid.uuid4().hex[:12], 'test-only')
        self.cid, _ = self.store.create_character(aid, 'Clock' + uuid.uuid4().hex[:8], 0, '1')
        self.other, _ = self.store.create_character(aid, 'Other' + uuid.uuid4().hex[:8], 0, '1')

    def put(self, cid=None, family='critical_probability', source=3115, end=1600):
        self.store.put_effect(cid or self.cid, family, source, 1000, end, checkpoint_at=1000)

    def test_checkpoint_batch_preserves_offline_character_and_expires_online_rows(self):
        self.put()
        self.put(self.other)
        self.put(family='critical_evade', source=3208, end=1100)
        self.store.checkpoint_effects([self.cid, self.cid], 1125)
        self.assertEqual(self.store.effects_for(self.cid), [dict(family='critical_probability',
                         source=3115, started=1000, deadline=1600, checkpoint_at=1125)])
        self.assertEqual(self.store.effects_for(self.other)[0]['checkpoint_at'], 1000)

    def test_checkpoint_rollback_restores_expired_rows_and_old_anchor(self):
        self.put()
        self.put(family='critical_evade', source=3208, end=1100)
        before = self.store.effects_for(self.cid)
        with self.assertRaises(RuntimeError):
            with storage.atomic(self.store.db):
                self.store.checkpoint_effects([self.cid], 1125)
                raise RuntimeError('rollback')
        self.assertEqual(self.store.effects_for(self.cid), before)

    def test_replacement_commits_interval_and_checkpoint_together(self):
        self.put()
        with storage.atomic(self.store.db):
            self.store.put_effect(self.cid, 'critical_probability', 4183, 1200, 4800,
                                  checkpoint_at=1200)
        rows = self.store.effects_for(self.cid)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['source'], rows[0]['deadline'], rows[0]['checkpoint_at']),
                         (4183, 4800, 1200))

    def test_legacy_schema_migration_keeps_original_interval(self):
        self.put()
        self.store.db.execute('ALTER TABLE char_effects DROP COLUMN checkpoint_at')
        self.store.db.commit()
        with patch.object(accounts.time, 'time', return_value=1200):
            accounts.migrate(self.store.db)
        row = self.store.effects_for(self.cid)[0]
        self.assertEqual(row['checkpoint_at'], 1200)
        self.assertEqual((row['source'], row['started'], row['deadline']), (3115, 1000, 1600))
        with patch.object(accounts.time, 'time', return_value=1300):
            accounts.migrate(self.store.db)
        self.assertEqual(self.store.effects_for(self.cid)[0], row)


if __name__ == '__main__':
    run_cases(EffectClockStorage)
