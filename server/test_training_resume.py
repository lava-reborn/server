"""Private range membership survives transport loss, not an explicit exit."""
import copy
import unittest
from unittest.mock import patch

from protocol import decode
import progression
import quests
import rooms
import server
import training_ground as training
import training_party
import test_training_ground as fixtures


class TrainingResume(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    party_members = fixtures.TrainingGround.party_members

    async def asyncTearDown(self):
        # Shared visitors must close before their common real store does.
        for ground in tuple(training.ACTIVE):
            if ground.owner.inv.store is self.store:
                ground.exit(notify=False)
        await fixtures.TrainingGround.asyncTearDown(self)

    def next_session(self):
        session = server.Session(fixtures.Writer(), 'reconnected')
        session.char_id = self.s.char_id
        session.active = dict(self.store.character(session.char_id))
        session.char = progression.Character.load(self.store, session.char_id)
        session.loc, session.pos = self.s.loc, self.s.pos
        session.gx, session.gy = self.s.gx, self.s.gy
        self.s = session
        return session

    def take_exit(self, ground):
        ground.clone.cmd_q_st(dict(mob=ground.terminal_id,
            q_idx=quests.given_by(training.TERMINAL).index(training.EXIT_QUEST)))
        return next(row for row in ground.store.quests(ground.clone.char_id)
                    if row['type'] == training.EXIT_QUEST)

    def suspend(self, ground):
        ground.exit(notify=False, suspend=True)
        self.assertTrue(self.store.training_profile(self.s.char_id)['inside'])
        self.assertNotIn(ground, training.ACTIVE)
        self.assertIsNone(self.s.training_ground)

    async def test_entry_records_presence_immediately_and_explicit_exit_clears_it(self):
        ground = self.enter()
        self.assertTrue(self.store.training_profile(self.s.char_id)['inside'])
        ground.exit(notify=False)
        self.assertFalse(self.store.training_profile(self.s.char_id)['inside'])
        self.assertFalse(training.resume(self.next_session()))
        self.unchanged()

    async def test_reconnect_restores_private_clone_at_computer_and_return_quest(self):
        ground = self.enter()
        old_quest = self.take_exit(ground)
        old_token = ground.token
        self.suspend(ground)
        session = self.next_session()
        self.assertTrue(training.resume(session))
        restored = session.training_ground
        self.assertNotEqual(restored.token, old_token)
        self.assertIsNot(restored.store, self.store)
        self.assertEqual(restored.phase, 'ready')
        self.assertEqual(restored.clone.pos, training.control_cell(restored.location))
        restored.clone.cmd_lenter({})
        row = next(row for row in restored.store.quests(restored.clone.char_id)
                   if row['type'] == training.EXIT_QUEST)
        self.assertNotEqual(row['q_id'], old_quest['q_id'])
        self.assertFalse(self.store.quests(session.char_id))
        with patch.object(session, 'enter_location') as returned:
            restored.clone.cmd_q_co(dict(mob=restored.terminal_id, q_id=row['q_id']))
        returned.assert_called_once_with()
        self.assertFalse(self.store.training_profile(session.char_id)['inside'])
        self.unchanged()

    async def test_untaken_or_cancelled_exit_quest_is_available_after_reconnect(self):
        ground = self.enter()
        row = self.take_exit(ground)
        ground.clone.cmd_q_ca(dict(q_id=row['q_id']))
        self.suspend(ground)
        self.assertTrue(training.resume(self.next_session()))
        restored = self.s.training_ground
        restored.clone.cmd_q_status(dict(q_type=training.EXIT_QUEST))
        command, params = decode(self.s.writer.frames[-1][:-1])
        self.assertEqual((command, params['status']), ('q_status', 1))
        self.take_exit(restored)
        self.unchanged()

    async def test_logout_and_repeated_transport_close_suspend_instead_of_exit(self):
        ground = self.enter()
        with patch.object(self.s, 'should_linger', return_value=False):
            self.assertTrue(training.handle(self.s, 'logout', {}))
            self.s.close(force=True)
        self.assertTrue(ground.closed)
        self.assertTrue(self.store.training_profile(self.s.char_id)['inside'])
        self.assertTrue(self.s.closed)
        self.assertTrue(training.resume(self.next_session()))
        self.assertEqual(len([g for g in training.ACTIVE if g.owner is self.s]), 1)
        # Ordinary close writes the real position/stats, never the range clone.
        self.assertEqual(self.store.character(self.s.char_id)['loc'], training.MARKET)
        self.assertEqual(self.store.item(self.real_item['uniq'])['type_id'], self.real_item['type_id'])

    async def test_disconnect_during_fight_stops_only_own_target_and_restores_ready(self):
        ground = self.enter()
        ground.start('mob')
        ground.clone.cmd_lenter({})
        self.suspend(ground)
        self.assertFalse(ground.room.combat.mobs)
        self.assertTrue(training.resume(self.next_session()))
        restored = self.s.training_ground
        self.assertEqual(restored.phase, 'ready')
        self.assertFalse(restored.room.combat.mobs)
        self.assertFalse(restored.clone.combat.dead)
        self.unchanged()

    async def test_shared_visit_restores_even_after_party_dissolves_and_relocates(self):
        members, parties, group = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        self.suspend(first)
        parties.dissolve(group)
        training_party.relocate(second, 106)
        self.assertTrue(training.resume(self.next_session()))
        restored = self.s.training_ground
        self.assertIs(restored.room, second.room)
        self.assertEqual(restored.location, 106)
        self.assertNotEqual(restored.clone.pos, second.clone.pos)
        self.assertEqual(len(restored.room.grounds), 2)
        self.unchanged()

    async def test_all_offline_participants_recreate_one_shared_visit_without_live_rooms(self):
        members, _parties, _group = self.party_members(2)
        training.enter(self.s, dict(npc=self.npc))
        first, second = [member.training_ground for member in members]
        visit = first.room.key[1]
        self.suspend(first)
        second.exit(notify=False, suspend=True)
        self.assertTrue(training.resume(self.next_session()))
        self.assertTrue(training.resume(members[1]))
        self.assertIs(self.s.training_ground.room, members[1].training_ground.room)
        self.assertEqual(self.s.training_ground.room.key[1], visit)
        self.unchanged()

    async def test_failed_explicit_exit_keeps_active_clone_and_saved_membership(self):
        ground = self.enter()
        with patch.object(self.store, 'save_training_profile', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                ground.exit()
        self.assertFalse(ground.closed)
        self.assertIs(self.s.training_ground, ground)
        self.assertTrue(self.store.training_profile(self.s.char_id)['inside'])
        self.unchanged()

    async def test_failed_entry_checkpoint_disposes_unpublished_clone(self):
        before = set(training.ACTIVE)
        room = self.s.room
        with patch.object(self.store, 'save_training_profile', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                training.enter(self.s, dict(npc=self.npc))
        self.assertIsNone(self.s.training_ground)
        self.assertEqual(training.ACTIVE, before)
        self.assertIs(self.s.room, room)
        self.unchanged()

    async def test_repeated_resume_does_not_create_a_second_clone(self):
        ground = self.enter()
        with patch.object(training, 'Ground', side_effect=AssertionError('duplicate')):
            self.assertTrue(training.resume(self.s))
        self.assertIs(self.s.training_ground, ground)

    async def test_unavailable_range_retains_presence_for_a_later_retry(self):
        ground = self.enter()
        self.suspend(ground)
        session = self.next_session()
        with patch.object(training, 'MAX_SESSIONS', 0):
            self.assertFalse(training.resume(session))
        self.assertTrue(self.store.training_profile(session.char_id)['inside'])
        self.assertIsNone(session.training_ground)
        self.assertTrue(training.resume(session))

    async def test_second_socket_resumes_after_closing_first_socket(self):
        self.store.save_position(self.s.char_id, self.s.loc.id, self.s.pos,
                                 self.s.gx, self.s.gy, False)
        old = self.s
        ground = self.enter()
        selected = dict(self.store.character(old.char_id))
        session = self.next_session()
        session.characters = [selected]
        directory = rooms.Directory()
        directory.add(old)
        with patch.object(server, 'ONLINE', directory), \
                patch.object(server, 'broadcast_online_count'), \
                patch.object(server.PARTIES, 'online'), patch.object(server.CLANS, 'online'):
            session.cmd_selPers(dict(num=selected['slot']))
        self.assertTrue(old.closed)
        self.assertTrue(ground.closed)
        self.assertIsNotNone(session.training_ground)
        self.assertEqual(session.loc.id, training.MARKET)
        self.assertEqual(len([g for g in training.ACTIVE if g.owner.char_id == session.char_id]), 1)

    async def test_old_profiles_do_not_teleport_and_ordinary_login_checks_only_once(self):
        profile = copy.deepcopy(self.store.training_profile(self.s.char_id))
        self.assertIsNone(profile)
        with patch.object(server, 'ONLINE', rooms.Directory()), \
                patch.object(server, 'broadcast_online_count'), \
                patch.object(server.PARTIES, 'online'), patch.object(server.CLANS, 'online'), \
                patch.object(self.s, 'keep_lent'), patch.object(server.events, 'take_back'), \
                patch.object(training, 'resume', return_value=False) as resume:
            self.s.enter_location()
            self.s.enter_location()
        self.assertEqual(resume.call_count, 1)

    async def test_actual_login_sends_range_lcall_without_public_location_or_character_changes(self):
        ground = self.enter()
        self.suspend(ground)
        session = self.next_session()
        with patch.object(server, 'ONLINE', rooms.Directory()), \
                patch.object(server, 'broadcast_online_count'), \
                patch.object(server.PARTIES, 'online'), patch.object(server.CLANS, 'online'), \
                patch.object(session, 'keep_lent') as keep:
            session.enter_location()
        self.assertIsNotNone(session.training_ground)
        calls = [params for command, params in (decode(f[:-1]) for f in session.writer.frames)
                 if command == 'lcall']
        self.assertEqual([call['id'] for call in calls], [training.RANGE])
        keep.assert_not_called()
        session.handle('lenter', {})
        self.assertIn(session.training_ground.clone, session.training_ground.room.players)
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingResume)
