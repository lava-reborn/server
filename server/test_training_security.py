"""Private inventory fault injection and sandbox disconnect boundaries."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

import combat
import inventory
import storage
from training import items as training_items
from training import shop as training_shop
from training import character as range_character
from training import session as tg
import test_training_ground as fixtures
from protocol import decode


class TrainingSecurity(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    party_members = fixtures.TrainingGround.party_members

    def rows(self, g):
        return [dict(row) for row in g.clone.inv.rows()]

    def packets(self):
        return [decode(frame[:-1]) for frame in self.s.writer.frames]

    async def test_negative_fractional_boolean_and_foreign_stack_commands_are_rejected(self):
        g = self.enter()
        inv = g.clone.inv
        a = inv.create(training_items.copy_type(6108), 30)
        b = inv.create(training_items.copy_type(6108), 20)
        before = self.rows(g)
        for count in (-1, -100, 1.5, True, 'bad', None):
            self.s.writer.frames.clear()
            inv.ss_heap_c(dict(obj=inventory.oid_of(a), trg=inventory.oid_of(b), num=count))
            self.assertEqual(self.rows(g), before)
            self.assertEqual(self.packets(), [('cmdAck', dict(res=inventory.RES_REFUSED))])
        inv.ss_heap_c(dict(obj=inventory.oid_of(a), trg=inventory.oid_of(self.real_item), num=1))
        self.assertEqual(self.rows(g), before)
        self.unchanged()

    async def test_split_and_merge_preserve_total_and_publish_after_commit(self):
        g = self.enter()
        inv = g.clone.inv
        a = inv.create(training_items.copy_type(6108), 30)
        inv.ss_heap_c(dict(obj=inventory.oid_of(a), num=10))
        rows = self.rows(g)
        b = next(row for row in rows if row['uniq'] != a['uniq'])
        self.assertEqual(sorted(row['count'] for row in rows), [10, 20])
        inv.ss_heap_c(dict(obj=inventory.oid_of(a), trg=inventory.oid_of(b), num=0))
        self.assertEqual([row['count'] for row in self.rows(g)], [30])
        self.unchanged()

    async def test_failed_split_and_merge_roll_back_without_success_packets(self):
        g = self.enter()
        inv = g.clone.inv
        a = inv.create(training_items.copy_type(6108), 30)
        b = inv.create(training_items.copy_type(6108), 20)
        before = self.rows(g)
        for method, params in (
            ('create_item', dict(obj=inventory.oid_of(a), num=10)),
            ('delete_item', dict(obj=inventory.oid_of(a), trg=inventory.oid_of(b), num=20)),
        ):
            self.s.writer.frames.clear()
            with patch.object(g.store, method, side_effect=RuntimeError('injected storage failure')):
                inv.ss_heap_c(params)
            self.assertEqual(self.rows(g), before)
            self.assertEqual(self.packets(), [('cmdAck', dict(res=inventory.RES_REFUSED))])
        self.unchanged()

    async def test_split_and_unload_cannot_bypass_private_row_limit(self):
        g = self.enter()
        inv = g.clone.inv
        a = inv.create(training_items.copy_type(6108), 30)
        gun = inv.create(training_items.copy_type(26022))
        g.store.update_item(gun['uniq'], ammo_type=a['type_id'], ammo_count=3)
        before = self.rows(g)
        with patch.object(training_shop, 'MAX_ROWS', len(before)):
            inv.ss_heap_c(dict(obj=inventory.oid_of(a), num=10))
            self.assertEqual(self.rows(g), before)
            self.s.writer.frames.clear()
            inv.use_unload(dict(obj=inventory.oid_of(gun)))
            self.assertEqual(self.rows(g), before)
            self.assertEqual(self.packets(), [('cmdAck', dict(res=inventory.RES_REFUSED))])
        self.unchanged()

    async def test_unload_update_failure_retains_loaded_rounds_and_no_new_stack(self):
        g = self.enter()
        inv = g.clone.inv
        gun = inv.create(training_items.copy_type(26022))
        g.store.update_item(gun['uniq'], ammo_type=training_items.copy_type(6108), ammo_count=3)
        before = self.rows(g)
        self.s.writer.frames.clear()
        with patch.object(g.store, 'update_item', side_effect=RuntimeError('injected update failure')):
            inv.use_unload(dict(obj=inventory.oid_of(gun)))
        self.assertEqual(self.rows(g), before)
        self.assertEqual(self.packets(), [('cmdAck', dict(res=inventory.RES_REFUSED))])
        inv.use_unload(dict(obj=inventory.oid_of(gun)))
        self.assertEqual(g.store.item(gun['uniq'])['ammo_count'], 0)
        self.assertEqual(sum(row['count'] for row in self.rows(g) if row['root'] == inventory.items.AMMO), 3)
        self.unchanged()

    async def test_serial_block_exhaustion_cannot_alias_another_session(self):
        g = self.enter()
        g.store.db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='items'",
                           (g.serial_base + (1 << 20) - 1,))
        g.store.db.commit()
        with self.assertRaises(ValueError):
            g.clone.inv.create(training_items.copy_type(6108), 1)
        self.unchanged()

    async def test_uncertain_reload_commit_closes_owner_not_private_character(self):
        g = self.enter()
        inv = g.clone.inv
        gun = inv.create(training_items.copy_type(26022), slot=inventory.PRIMARY)
        stack = inv.create(training_items.copy_type(6108), 20)
        with patch.object(combat.Fighter, 'schedule_action'):
            inv.use_load(dict(obj=inventory.oid_of(gun), target=inventory.oid_of(stack)))
        with patch.object(inv, 'finish_reload', side_effect=storage.CommitError('injected')), \
                patch.object(self.s, 'close') as close, \
                patch.object(self.store, 'save_position') as position:
            inv.reloaded(gun['uniq'])
        close.assert_called_once_with(force=True)
        position.assert_not_called()
        self.unchanged()

    async def test_actor_close_cannot_persist_private_position_in_main_database(self):
        g = self.enter()
        expected = (self.s.char_id, self.s.loc.id, self.s.pos, self.s.gx, self.s.gy, self.s.on_map)
        with patch.object(self.store, 'save_position', wraps=self.store.save_position) as save:
            g.clone.close(force=True)
        save.assert_called_once_with(*expected)
        self.assertTrue(g.closed)
        self.assertTrue(self.s.closed)
        self.assertIsNone(self.s.training_ground)

    async def test_settings_write_failure_closes_clone_and_preserves_main_record(self):
        g = self.enter()
        g.clone.inv.create(training_items.copy_type(26022), slot=inventory.PRIMARY)
        g.remember_outfit()
        g.save_settings()
        saved = self.store.training_profile(self.s.char_id)
        real_items = [dict(r) for r in self.s.inv.rows()]
        with patch.object(self.store, 'save_training_profile', side_effect=RuntimeError('injected')) as write:
            with self.assertRaises(ValueError):
                g.configure_player(range_character.preset(12))
        self.assertEqual(write.call_count, 1)
        self.assertTrue(g.closed)
        self.assertIsNone(self.s.training_ground)
        self.assertEqual(saved, self.store.training_profile(self.s.char_id))
        self.assertEqual(real_items, [dict(r) for r in self.s.inv.rows()])

    async def test_legacy_full_preset_failure_cannot_publish_or_touch_main_items(self):
        g = self.enter()
        saved = self.store.training_profile(self.s.char_id)
        real_items = [dict(r) for r in self.s.inv.rows()]
        self.s.writer.frames.clear()
        with patch.object(self.store, 'save_training_profile', side_effect=RuntimeError('injected')):
            with self.assertRaises(ValueError):
                g.request(dict(op='apply', token=g.token, who='player',
                               skills='0,12,0,0,0', specs=','.join(['-1'] * 15), gear=''))
        self.assertTrue(g.closed)
        self.assertEqual(saved, self.store.training_profile(self.s.char_id))
        self.assertEqual(real_items, [dict(r) for r in self.s.inv.rows()])
        self.assertFalse(any(name == 'ss_obj_move' for name, fields in self.packets()))

    async def test_shared_map_failed_second_save_keeps_both_rooms_and_profiles(self):
        members, _, _ = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        grounds = [member.training_ground for member in members]
        for g in grounds:
            g.clone.cmd_lenter({})
        before = [(g.room, g.location, g.clone.pos, self.store.training_profile(g.owner.char_id))
                  for g in grounds]
        saved = self.store.save_training_profile
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            saved(*args, **kwargs)
            if calls == 2:
                raise RuntimeError('injected second write failure')
        for member in members:
            member.writer.frames.clear()
        with patch.object(self.store, 'save_training_profile', side_effect=fail_second):
            with self.assertRaises(ValueError):
                grounds[0].change_location(59)
        self.assertEqual(before, [(g.room, g.location, g.clone.pos,
                                  self.store.training_profile(g.owner.char_id)) for g in grounds])
        self.assertTrue(all(not member.writer.frames for member in members))
        grounds[0].change_location(59)
        self.assertIs(grounds[0].room, grounds[1].room)
        self.assertNotEqual(grounds[0].clone.pos, grounds[1].clone.pos)
        self.unchanged()

    async def test_shared_map_during_duel_is_refused_and_exit_clears_alias(self):
        members, _, _ = self.party_members(2)
        tg.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        old = first.room
        with patch.object(second.clone.combat, 'duels', {first.clone.pid}):
            with self.assertRaises(ValueError):
                first.change_location(59)
        self.assertIs(first.room, old)
        second.exit(notify=False)
        self.assertNotIn(second.owner.pid, old.owner_ids)
        self.assertEqual(old.owner_ids[first.owner.pid], first.clone.pid)
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingSecurity)
