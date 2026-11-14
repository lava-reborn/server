"""Consent uses real sessions and the normal atomic clone-entry coordinator."""
import unittest
from unittest.mock import patch

from protocol import decode
from training import api, entry, runtime, session
import test_training_ground as fixtures


class EntryConsent(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    party_members = fixtures.TrainingGround.party_members

    def invite(self, count=3):
        members, parties, group = self.party_members(count)
        for member in members:
            member.training_entry_confirmation = True
        self.addCleanup(lambda: api.cancel_entry(self.s))
        session.enter_from_quest(self.s)
        return members, parties, group, self.s.training_entry

    def answer(self, member, pending, accept=1, token=None):
        return api.handle(member, 'tg', dict(op='entry_reply', accept=accept,
                          confirmation=token if token is not None else pending.token))

    def unchanged(self, members):
        self.assertEqual(list(self.store.db._db.iterdump()), self.before)
        self.assertFalse(runtime.ACTIVE)
        self.assertTrue(all(member.training_ground is None for member in members))

    async def test_nobody_moves_until_every_guest_accepts_and_duplicates_do_not_reenter(self):
        members, _, _, pending = self.invite()
        self.unchanged(members)
        packets = [decode(frame[:-1]) for frame in members[1].writer.frames]
        self.assertTrue(any(name == 'tg' and p.get('op') == 'entry_invite' for name, p in packets))
        self.answer(members[1], pending)
        self.answer(members[1], pending)
        self.unchanged(members)
        self.answer(members[2], pending)
        grounds = [member.training_ground for member in members]
        self.assertTrue(all(ground.room is grounds[0].room for ground in grounds))
        self.assertTrue(all(getattr(member, 'training_entry', None) is None for member in members))
        with patch.object(session, 'enter', side_effect=AssertionError('replay')):
            self.answer(members[2], pending)

    async def test_cancel_and_timeout_preserve_main_characters_without_clones_or_presence(self):
        members, _, _, pending = self.invite()
        self.answer(members[1], pending)
        self.answer(members[2], pending, accept=0)
        self.unchanged(members)
        self.assertIsNone(pending.timer)
        session.enter_from_quest(self.s)
        pending = self.s.training_entry
        pending.expire()
        self.unchanged(members)
        self.assertTrue(all(member.training_entry is None for member in members))

    async def test_unrelated_or_forged_replies_and_expired_acceptance_never_enter(self):
        members, _, _, pending = self.invite()
        self.answer(self.s, pending)
        self.answer(members[1], pending, token='forged')
        self.answer(members[1], pending, accept='1')
        self.assertEqual(pending.accepted, {self.s})
        with patch.object(entry.time, 'monotonic', return_value=pending.deadline + 1):
            self.answer(members[1], pending)
        self.unchanged(members)
        self.assertIsNone(self.s.training_entry)

    async def test_repeated_quest_handin_does_not_replace_or_extend_pending_consent(self):
        members, _, _, pending = self.invite()
        deadline = pending.deadline
        with self.assertRaises(ValueError):
            session.enter_from_quest(self.s)
        self.assertIs(self.s.training_entry, pending)
        self.assertEqual(pending.deadline, deadline)
        self.unchanged(members)

    async def test_departure_party_change_and_new_leader_invalidate_all_consents(self):
        members, parties, group, pending = self.invite()
        room = members[1].room
        for change in ('room', 'party', 'leader', 'closed'):
            with self.subTest(change=change):
                if self.s.training_entry is None:
                    session.enter_from_quest(self.s)
                    pending = self.s.training_entry
                self.answer(members[1], pending)
                if change == 'room':
                    members[1].room = None
                elif change == 'party':
                    parties.by_char.pop(members[1].char_id)
                elif change == 'leader':
                    group.members[0], group.members[1] = group.members[1], group.members[0]
                else:
                    members[1].closed = True
                self.answer(members[2], pending)
                self.unchanged(members)
                self.assertIsNone(self.s.training_entry)
                members[1].room = room
                members[1].closed = False
                parties.by_char[members[1].char_id] = group
                group.members[:] = [member.char_id for member in members]

    async def test_new_travel_or_barter_blocks_entry_after_acceptance(self):
        members, _, _, pending = self.invite()
        for field in ('way', 'passage', 'arrival', 'barter'):
            with self.subTest(field=field):
                if self.s.training_entry is None:
                    session.enter_from_quest(self.s)
                    pending = self.s.training_entry
                self.answer(members[1], pending)
                target, attribute = (members[1].barter, 'deal') if field == 'barter' else (members[1], field)
                setattr(target, attribute, object())
                try:
                    self.answer(members[2], pending)
                    self.unchanged(members)
                    self.assertIsNone(self.s.training_entry)
                finally:
                    setattr(target, attribute, None)

    async def test_activation_failure_after_consent_clears_pending_and_rolls_back_presence(self):
        members, _, _, pending = self.invite(2)
        with patch.object(session, 'activate', side_effect=ValueError('activation failed')):
            self.answer(members[1], pending)
        self.assertFalse(runtime.ACTIVE)
        for member in members:
            self.assertIsNone(member.training_entry)
            self.assertIsNone(member.training_ground)
            self.assertFalse(self.store.training_profile(member.char_id)['inside'])

    async def test_confirmation_capability_is_explicit_and_invalid_hello_clears_it(self):
        api.handle(self.s, 'tg', dict(op='hello', version=1))
        self.assertFalse(self.s.training_entry_confirmation)
        api.handle(self.s, 'tg', dict(op='hello', version=1, entry_confirmation=1))
        self.assertTrue(self.s.training_entry_confirmation)
        api.handle(self.s, 'tg', dict(op='hello', version=2, entry_confirmation=1))
        self.assertFalse(self.s.training_entry_confirmation)

    async def test_disconnect_cancels_timer_and_closes_invitations(self):
        members, _, _, pending = self.invite()
        members[1].close(force=True)
        self.assertIsNone(pending.timer)
        self.assertTrue(all(member.training_entry is None for member in members))
        self.assertFalse(runtime.ACTIVE)

    async def test_old_client_cannot_be_moved_without_a_confirmation_ui(self):
        members, _, _ = self.party_members(2)
        with self.assertRaisesRegex(ValueError, 'обновить клиент'):
            session.enter_from_quest(self.s)
        self.unchanged(members)

    async def test_single_player_keeps_quest_entry_without_an_invitation(self):
        session.enter_from_quest(self.s)
        self.assertIsNotNone(self.s.training_ground)
        self.assertIsNone(getattr(self.s, 'training_entry', None))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(EntryConsent)
