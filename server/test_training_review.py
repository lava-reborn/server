"""Regression cases from server-module review: failures, refresh and budgets."""
import copy
import time
import unittest
from unittest.mock import patch

import inventory
import item_type_ids
import items
import own_items
import progression
import storage
from protocol import decode
from training import api, avatar, checkpoints, commands, runtime, session, type_metadata
import test_training_ground as fixtures


class Review(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    party_members = fixtures.TrainingGround.party_members

    async def test_second_of_three_activation_failures_clear_all_durable_memberships(self):
        members, _, _ = self.party_members(3)
        activate = session.activate
        def fail_second(ground, **kw):
            if ground.owner is members[1]:
                ground.owner.leave_room()
                raise ValueError('after leaving main room')
            return activate(ground, **kw)
        with patch.object(session, 'activate', side_effect=fail_second):
            with self.assertRaises(ValueError):
                session.enter(self.s, dict(npc=self.npc))
        for member in members:
            self.assertFalse(self.store.training_profile(member.char_id)['inside'])
            self.assertIsNone(member.training_ground)
            self.assertFalse(member.closed)
        self.assertFalse(runtime.ACTIVE)
        for member in members[:2]:
            member.cmd_lenter({})
            self.assertIsNotNone(member.room)
            self.assertIn(member, member.room.players)

    async def test_corrupt_checkpoint_fields_archive_and_allow_reentry(self):
        for invalid in ([], dict(player=dict(gear=None)), dict(player=dict(gear={'bad': 1})),
                        dict(personal_rules=None), dict(unavailable_presets=None)):
            saved = dict(version=1, player=session.preset(1), opponent=session.preset(1))
            if isinstance(invalid, dict):
                saved.update(invalid)
            else:
                saved = invalid
            with self.subTest(saved=saved), patch.object(self.store, 'training_profile', return_value=saved):
                ground = session.Ground(self.s)
                try:
                    self.assertEqual(ground.clone.char.level, 1)
                    self.assertIn('checkpoint', ground.unavailable_presets)
                    ground.save_settings()
                finally:
                    ground.dispose()
        ground = self.enter()
        self.assertEqual(ground.clone.char.level, 1)

    async def test_known_durable_rejections_roll_back_without_disconnect(self):
        ground = self.enter()
        before = copy.deepcopy(ground.profile)
        old_items = [dict(row) for row in ground.clone.inv.rows()]
        for failure in (ValueError('too large'), storage.IntegrityError('rejected')):
            with patch.object(self.store, 'save_training_profile', side_effect=failure):
                with self.assertRaises(ValueError):
                    ground.configure_player(session.preset(12))
            self.assertFalse(ground.closed)
            self.assertFalse(self.s.closed)
            self.assertEqual(ground.profile, before)
            self.assertEqual([dict(row) for row in ground.clone.inv.rows()], old_items)

    async def test_resume_failure_after_leaving_room_falls_back_once_to_normal_location(self):
        ground = self.enter()
        ground.exit(notify=False, suspend=True)
        self.s.training_resume_char = None
        def fail_activation(restored, **kw):
            restored.owner.leave_room()
            raise ValueError('after leaving room')
        with patch.object(session, 'activate', side_effect=fail_activation):
            self.s.enter_location()
        self.assertIsNone(self.s.training_ground)
        self.s.cmd_lenter({})
        self.assertIn(self.s, self.s.room.players)
        self.assertEqual(self.s.training_resume_char, self.s.char_id)
        with patch.object(api, 'resume', side_effect=AssertionError('repeated resume')):
            self.s.enter_location()

    async def test_connection_loss_is_uncertain_but_integrity_rejection_is_not(self):
        self.assertTrue(checkpoints.uncertain(storage.CommitError(), self.store.db))
        self.assertTrue(checkpoints.uncertain(ConnectionError(), self.store.db))
        self.assertFalse(checkpoints.uncertain(storage.IntegrityError(), self.store.db))
        ground = self.enter()
        with patch.object(self.store, 'save_training_profile', side_effect=ConnectionError()):
            with self.assertRaises(ValueError):
                ground.configure_player(session.preset(12))
        self.assertTrue(ground.closed)

    async def test_durable_rate_limit_precedes_snapshot_and_metadata_needs_no_database_backup(self):
        ground = self.enter()
        with patch.object(checkpoints, 'snapshot_database', side_effect=AssertionError('metadata backup')), \
                patch.object(self.store, 'save_training_profile', wraps=self.store.save_training_profile) as save:
            ground.request(dict(op='spawn', token=ground.token, spawn_point=1))
            with self.assertRaises(ValueError):
                ground.request(dict(op='spawn', token=ground.token, spawn_point=2))
            self.assertEqual(save.call_count, 1)
            self.assertEqual(ground.spawn_point, 1)
            ground.last_request = time.monotonic() - 1.01
            ground.request(dict(op='spawn', token=ground.token, spawn_point=2))
            self.assertEqual(save.call_count, 2)

    async def test_local_chat_reaches_only_shared_training_room(self):
        members, _, _ = self.party_members(2)
        session.enter(self.s, dict(npc=self.npc))
        for member in members:
            member.training_ground.clone.cmd_lenter({})
            member.writer.frames.clear()
        first, second = [member.training_ground for member in members]
        self.assertIsNone(first.owner.room)
        first.clone.handle_training('userMsg', dict(group=0, entry='hello range'))
        messages = [p for name, p in (decode(f[:-1]) for f in second.owner.writer.frames) if name == 'userMsg']
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['entry'], 'hello range')
        self.assertEqual(messages[0]['from'], first.clone.pid)

    async def test_return_refreshes_main_items_changed_while_training(self):
        ground = self.enter()
        original = self.store.item(self.real_item['uniq'])
        self.store.delete_item(original['uniq'])
        new = self.s.inv.create(6108, 10)
        self.s.writer.frames.clear()
        ground.exit()
        self.s.cmd_lenter({})
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        statuses = [(p['obj'], p['status']) for name, p in frames if name == 'ss_obj_status']
        self.assertIn((inventory.oid_of(original), 0), statuses)
        self.assertIn((inventory.oid_of(new), 1), statuses)
        self.assertTrue(any(name == 'userInfo_Player' for name, _ in frames))
        self.assertFalse(hasattr(self.s, 'training_inventory_before'))

    async def test_participant_with_pending_paid_way_is_not_interrupted(self):
        members, _, _ = self.party_members(2)
        pending = members[1].way = object()
        before = list(self.store.db.raw.iterdump())
        with self.assertRaises(ValueError):
            session.enter(self.s, dict(npc=self.npc))
        self.assertIs(members[1].way, pending)
        self.assertTrue(all(member.training_ground is None for member in members))
        self.assertEqual(list(self.store.db.raw.iterdump()), before)
        members[1].way = None

    async def test_internal_key_error_is_logged_and_never_sent_as_user_text(self):
        ground = self.enter()
        self.s.writer.frames.clear()
        with patch.object(ground, 'request', side_effect=KeyError('internal_gear')), \
                patch.object(commands.log, 'exception') as logged:
            commands.handle(self.s, 'tg', {})
            logged.assert_called()
        messages = [p.get('message', '') for name, p in (decode(f[:-1]) for f in self.s.writer.frames) if name == 'tg']
        self.assertTrue(messages)
        self.assertFalse(any('internal_gear' in message for message in messages))

    async def test_dynamic_class_reuse_and_armour_never_materialises_backpack(self):
        ground = self.enter()
        self.assertIs(avatar.clone_class(type(self.s)), avatar.clone_class(type(self.s)))
        with patch.object(ground.clone.inv, 'rows', side_effect=AssertionError('full backpack')):
            self.assertGreaterEqual(ground.clone.combat.armor(), 0)

    async def test_persistent_types_cannot_allocate_private_bands_even_without_mode_flag(self):
        for first, last in item_type_ids.PRIVATE_BANDS:
            for type_id in (first, last):
                with self.assertRaises(own_items.Refused):
                    own_items.parse({'items': {str(type_id): dict(name='private_collision', like=6108)}})
        self.assertIn(60000, own_items.parse({'items': {'60000': dict(name='public_test', like=6108)}}))

    async def test_type_metadata_cache_requires_matching_ack_and_limits_resend(self):
        ground = self.enter()
        data = type_metadata.payload()
        self.assertIs(data, type_metadata.payload())
        self.s.writer.frames.clear()
        api.handle(self.s, 'tg', dict(op='types_ack', version=data['version']))
        type_metadata.announce(self.s)
        self.assertEqual(decode(self.s.writer.frames[-1][:-1])[1]['op'], 'types_cached')
        self.s.writer.frames.clear()
        for _ in range(3):
            api.handle(self.s, 'tg', dict(op='types_request'))
        frames = [decode(f[:-1]) for f in self.s.writer.frames]
        self.assertEqual(len([1 for name, p in frames if p.get('op') == 'types']), 1)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(Review)
