"""Online-only buff time with real isolated persistence and lifecycle hooks."""
import copy
import logging
logging.disable(logging.CRITICAL)
import unittest
from unittest.mock import patch

import accounts
import combat
import effects
import progression
import server
from protocol import decode
import test_training_ground as fixtures
from testkit import run_cases


class OnlineEffects(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown

    def manager(self):
        self.now = 1000000.0
        self.enterContext(patch.object(effects.time, 'time', lambda: self.now))
        self.s.char.set_skill(progression.SHOOTING, 17)
        self.s.on_map = False
        self.s.room.players[self.s] = True
        self.s.room.combat = combat.RoomCombat(self.s.room, self.store)
        self.s.effects = effects.Effects(self.s)
        self.s.effects.load()
        self.addCleanup(self.s.effects.close)
        return self.s.effects

    def activate(self, source):
        row = self.s.inv.create(source)
        effects.activate(self.s.combat, row['uniq'], self.s.combat, 0)
        remaining = self.store.item(row['uniq'])
        self.assertEqual(remaining['use_count'] if remaining else 0, row['use_count'] - 1)
        return self.s.effects.active[effects.definition(source)['family']]

    async def test_every_family_keeps_exact_remaining_time_after_long_offline(self):
        manager = self.manager()
        for source in (4183, 4185, 3470, 3473, 3476, 4936, 4956, 3897, 3561, 3789):
            self.activate(source)
        self.now += 125
        before = {family: (row.deadline - self.now, self.now - row.started)
                  for family, row in manager.active.items()}
        manager.close()
        self.now += 7 * 86400
        manager.load()
        after = {family: (row.deadline - self.now, self.now - row.started)
                 for family, row in manager.active.items()}
        self.assertEqual(after, before)
        self.assertEqual(len(manager.active), 10)

    async def test_repeated_disconnect_resume_does_not_extend_online_duration(self):
        manager = self.manager()
        row = self.activate(3115)
        total = effects.definition(3115)['duration']
        for _ in range(10):
            self.now += 7
            manager.pause()
            self.assertIsNone(manager.timer)
            self.now += 86400
            manager.resume()
        row = manager.active['critical_probability']
        self.assertEqual(row.deadline - self.now, total - 70)
        self.assertEqual(self.now - row.started, 70)

    async def test_paused_lingering_body_keeps_bonus_without_consuming_time(self):
        manager = self.manager()
        self.activate(3473)
        before = copy.deepcopy(manager.bonus)
        self.now += 5
        manager.pause()
        elapsed = manager.clock()
        self.now += 100
        manager.refresh(notify=False)
        self.assertEqual(manager.clock(), elapsed)
        self.assertEqual(manager.bonus, before)
        self.assertIsNone(manager.timer)
        manager.resume()
        self.assertEqual(manager.active['Дофрамин'].deadline - self.now, 3595)

    async def test_periodic_effect_preserves_partial_pulse_and_does_not_catch_up(self):
        manager = self.manager()
        self.activate(3914)
        self.now += 650
        manager.refresh(notify=False)
        self.assertEqual(manager.bonus['attribs'][:2], [1, 1])
        manager.close()
        self.now += 8 * 86400
        manager.load()
        self.assertEqual(manager.bonus['attribs'][:2], [1, 1])
        self.now += 549
        manager.refresh(notify=False)
        self.assertEqual(manager.bonus['attribs'][:2], [1, 1])
        self.now += 1
        manager.refresh(notify=False)
        self.assertEqual(manager.bonus['attribs'][:2], [2, 2])

    async def test_heartbeat_recovers_after_process_loss_without_draining_offline(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 120
        self.store.checkpoint_effects([self.s.char_id], self.now)
        # Simulate abrupt process loss, without invoking close or pause.
        manager.timer.cancel()
        manager.timer = None
        self.now += 9 * 86400
        fresh = effects.Effects(self.s)
        fresh.load()
        self.addCleanup(fresh.close)
        self.assertEqual(fresh.active['critical_probability'].deadline - self.now, 480)
        self.assertEqual(self.now - fresh.active['critical_probability'].started, 120)
        manager.active.clear()

    async def test_expiration_is_committed_and_cannot_resurrect_after_restart(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 600
        manager.refresh(notify=False)
        self.assertFalse(manager.active)
        self.assertEqual(self.store.effects_for(self.s.char_id), [])
        self.now += 86400
        manager.load()
        self.assertFalse(manager.active)

    async def test_heartbeat_only_updates_online_characters(self):
        manager = self.manager()
        self.activate(3115)
        other = self.s.char_id + 999
        before = self.store.effects_for(self.s.char_id)
        self.now += 90
        self.store.checkpoint_effects([other], self.now)
        self.assertEqual(self.store.effects_for(self.s.char_id), before)
        self.store.checkpoint_effects([self.s.char_id], self.now)
        self.assertEqual(self.store.effects_for(self.s.char_id)[0]['checkpoint_at'], self.now)

    async def test_legacy_rows_preserve_remaining_time_and_do_not_restore_expired_buffs(self):
        manager = self.manager()
        self.store.put_effect(self.s.char_id, 'critical_probability', 3115, self.now - 200, self.now + 400)
        self.store.put_effect(self.s.char_id, 'critical_evade', 3208, self.now - 500, self.now - 1)
        manager.load()
        self.assertEqual(list(manager.active), ['critical_probability'])
        self.assertEqual(manager.active['critical_probability'].deadline - self.now, 400)
        self.assertEqual(len(self.store.effects_for(self.s.char_id)), 1)

    async def test_wire_elapsed_excludes_offline_time(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 45
        manager.close()
        self.now += 86400
        manager.load()
        self.s.writer.frames.clear()
        manager.dynamic(effects.FIRST + 3115)
        command, packet = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual((command, packet['time']), ('e_di', 45000))

    async def test_resume_failure_keeps_paused_intervals_for_retry(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 12
        manager.pause()
        before = copy.deepcopy(manager.active)
        self.now += 86400
        with patch.object(self.store, 'put_effect', side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):
                manager.resume()
        self.assertEqual(manager.active, before)
        self.assertIsNotNone(manager._paused_at)
        manager.resume()
        self.assertEqual(manager.active['critical_probability'].deadline - self.now, 588)

    async def test_online_directory_heartbeat_checkpoints_only_connected_players(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 12
        with patch.object(server, 'SESSIONS', {self.s}):
            server.publish_online()
            self.assertEqual(self.store.effects_for(self.s.char_id)[0]['checkpoint_at'], self.now)
            self.s.closed = True
            self.now += 20
            server.publish_online()
        self.assertEqual(self.store.effects_for(self.s.char_id)[0]['checkpoint_at'], self.now - 20)
        self.s.closed = False

    async def test_native_forced_logout_saves_the_exact_remaining_duration(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 45
        self.s.close(force=True)
        self.assertFalse(manager.active)
        self.assertEqual(self.store.effects_for(self.s.char_id)[0]['checkpoint_at'], self.now)
        self.now += 86400
        manager.load()
        self.assertEqual(manager.active['critical_probability'].deadline - self.now, 555)

    async def test_upgrade_freezes_existing_buff_before_first_new_login(self):
        manager = self.manager()
        self.store.put_effect(self.s.char_id, 'critical_probability', 3115,
                              self.now, self.now + 600)
        self.store.db.execute('ALTER TABLE char_effects DROP COLUMN checkpoint_at')
        self.store.db.commit()
        self.now += 120
        accounts.migrate(self.store.db)
        self.now += 7 * 86400
        manager.load()
        self.assertEqual(manager.active['critical_probability'].deadline - self.now, 480)

    async def test_failed_reconnect_keeps_old_socket_and_linger_until_retry(self):
        manager = self.manager()
        self.activate(3115)
        self.now += 15
        with patch.object(self.s, 'should_linger', return_value=True):
            self.s.close()
        old_writer, old_linger = self.s.writer, self.s.linger
        incoming = server.Session(fixtures.Writer(), 'reconnect')
        incoming.characters = [dict(self.store.character(self.s.char_id))]
        try:
            with patch.dict(server.ONLINE.by_char, {self.s.char_id: self.s}), \
                    patch.object(manager, 'resume', side_effect=RuntimeError('SQL failure')):
                with self.assertRaises(RuntimeError):
                    incoming.cmd_selPers(dict(num=incoming.characters[0]['slot']))
            self.assertIs(self.s.writer, old_writer)
            self.assertIs(self.s.linger, old_linger)
            self.assertFalse(old_linger.cancelled())
            self.assertTrue(self.s.closed)
            self.assertIsNone(incoming.resumed)
        finally:
            self.s.close(force=True)


if __name__ == '__main__':
    run_cases(OnlineEffects)
