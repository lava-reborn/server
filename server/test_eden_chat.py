"""Eden chat isolation through the real Session wire and command handlers."""
import unittest
from unittest.mock import patch

import test_release_battle as fixtures
import clans
import eden
import eden_map
import inventory
import party
import rooms
import server
import world
from protocol import decode, encode
from testkit import run_cases


class EdenChat(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.store = self.case.store
        self.a, self.b, self.c = self.case.players
        self.directory = rooms.Directory()
        self.map = rooms.GlobalMapRoom(10)
        self.parties = party.Parties(self.directory)
        self.clans = clans.Clans(self.store, self.directory, self.map)
        for name, value in (('ONLINE', self.directory), ('GMAP', self.map),
                            ('PARTIES', self.parties), ('CLANS', self.clans)):
            self.enterContext(patch.object(server, name, value))
        for seat in self.case.players:
            self.directory.add(seat)
        group = party.Party(self.a.char_id)
        group.members = [seat.char_id for seat in self.case.players]
        group.present = set(group.members)
        for cid in group.members:
            self.parties.by_char[cid] = group
        clan_id = self.store.clan_create(self.a.char_id, 'Chat', 'chat', '',
                                          (self.a.char_id, 1000000, 0))
        for seat in (self.b, self.c):
            self.assertTrue(self.store.clan_member_add(seat.char_id, clan_id,
                                                       clans.R_CHAT, ''))
        self.clear()

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def clear(self):
        for seat in self.case.players:
            seat.writer.frames.clear()

    def confine(self, seat, reason='sentence'):
        # Each independent signal must protect even a stale ordinary position
        # or a missing sentence cache. The sentence is an actual saved row.
        eden.release(self.store, seat.char_id)
        seat.eden_sentence = None
        seat.loc = self.case.loc
        seat.gx, seat.gy, seat.on_map = 6270, 1832, False
        if reason == 'sentence':
            seat.eden_sentence = eden.assign(self.store, seat.char_id,
                                             'test', 'Chat isolation')
        elif reason == 'location':
            seat.loc = world.location(eden.CENTER)
        elif reason == 'cell':
            seat.gx, seat.gy = eden_map.CENTER_CELL
            seat.on_map = True
        else:
            raise AssertionError(reason)
        self.assertTrue(eden.confined(seat))
        self.clear()

    def send_chat(self, seat, group=None, to=None, text='test ^0^ message'):
        params = dict(entry=text)
        if group is not None:
            params['group'] = group
        if to is not None:
            params['to'] = to
        # Exercise the same decoding and dispatch as a client command. Session
        # send is never replaced, so every assertion reads the encoded reply.
        seat.handle(*decode(encode('userMsg', **params)))

    def acks(self, seat):
        return [p['res'] for cmd, p in seat.writer.frames if cmd == 'cmdAck']

    def messages(self, seat):
        return [p for cmd, p in seat.writer.frames if cmd == 'userMsg']

    def assert_refused(self, seat):
        self.assertEqual(self.acks(seat), [inventory.RES_REFUSED])
        self.assertEqual(len(self.messages(seat)), 1)
        self.assertEqual(self.messages(seat)[0]['from'], 0)
        self.assertIn('Эдем', self.messages(seat)[0]['entry'])

    async def test_each_confinement_signal_blocks_outgoing_world_trade_and_party(self):
        for signal in ('sentence', 'location', 'cell'):
            self.confine(self.a, signal)
            for channel in (1, 4, 6):
                with self.subTest(signal=signal, channel=channel):
                    self.clear()
                    self.send_chat(self.a, channel)
                    self.assert_refused(self.a)
                    self.assertEqual(self.b.writer.frames, [])
                    self.assertEqual(self.c.writer.frames, [])

    async def test_each_confinement_signal_blocks_incoming_world_trade_and_party(self):
        for signal in ('sentence', 'location', 'cell'):
            self.confine(self.b, signal)
            for channel in (1, 4, 6):
                with self.subTest(signal=signal, channel=channel):
                    self.clear()
                    self.send_chat(self.a, channel)
                    self.assertEqual(self.acks(self.a), [0])
                    self.assertEqual(self.messages(self.a), [])
                    self.assertEqual(self.b.writer.frames, [])
                    self.assertEqual(self.messages(self.c), [dict(
                        group=channel, nick=self.a.nick,
                        entry='test ^0^ message', **{'from': self.a.pid})])

    async def test_private_messages_are_refused_in_both_directions_for_each_signal(self):
        for signal in ('sentence', 'location', 'cell'):
            self.confine(self.b, signal)
            for sender, target in ((self.a, self.b), (self.b, self.a)):
                with self.subTest(signal=signal, sender=sender.nick):
                    self.clear()
                    self.send_chat(sender, to=target.nick.swapcase())
                    self.assert_refused(sender)
                    self.assertEqual(target.writer.frames, [])
                    self.assertEqual(self.c.writer.frames, [])

    async def test_direct_incoming_private_frames_do_not_bypass_recipient_guard(self):
        self.confine(self.b)
        self.b.send('userMsg', nick=self.a.nick, entry='private',
                    **{'from': self.a.pid})
        self.assertEqual(self.b.writer.frames, [])

    async def test_private_offline_target_is_still_refused_inside_but_keeps_normal_code_outside(self):
        self.confine(self.b)
        self.send_chat(self.b, to='offline')
        self.assert_refused(self.b)
        self.clear()
        self.send_chat(self.a, to='offline')
        self.assertEqual(self.acks(self.a), [9])
        self.assertEqual(self.messages(self.a), [])

    async def test_clan_chat_crosses_boundary_both_ways_and_preserves_chat_rights(self):
        self.confine(self.b)
        for sender, target in ((self.a, self.b), (self.b, self.a)):
            self.clear()
            self.send_chat(sender, 2, text='clan')
            self.assertEqual(self.acks(sender), [0])
            self.assertEqual(self.messages(sender), [])
            self.assertEqual(self.messages(target), [dict(
                group=2, player=sender.char_id, nick=sender.nick, entry='clan')])
        clan_id = self.store.clan_member(self.b.char_id)['clan_id']
        self.assertTrue(self.store.clan_member_update(self.b.char_id, clan_id, perm=0))
        self.clear()
        self.send_chat(self.a, 2)
        self.assertEqual(self.acks(self.a), [0])
        self.assertEqual(self.b.writer.frames, [])
        self.clear()
        self.send_chat(self.b, 2)
        self.assertEqual(self.acks(self.b), [0])
        self.assertEqual(self.a.writer.frames, [])
        self.assertEqual(self.c.writer.frames, [])

    async def test_local_room_chat_reaches_same_side_only_without_sender_echo(self):
        self.confine(self.a)
        self.confine(self.b)
        for sender, target in ((self.a, self.b), (self.b, self.a)):
            self.clear()
            self.send_chat(sender, 0, text='local')
            self.assertEqual(self.acks(sender), [0])
            self.assertEqual(self.messages(sender), [])
            self.assertEqual(self.messages(target), [dict(
                group=0, nick=sender.nick, entry='local', **{'from': sender.pid})])
            self.assertEqual(self.c.writer.frames, [])
        self.clear()
        self.send_chat(self.c, 0)
        self.assertEqual(self.acks(self.c), [0])
        self.assertEqual(self.a.writer.frames, [])
        self.assertEqual(self.b.writer.frames, [])

    async def test_global_map_local_chat_does_not_leak_across_nearby_boundary(self):
        # Both sides fall inside the ordinary chat radius. Only coordinates
        # establish confinement here, not a sentence or the old local scene.
        for seat, cell in zip(self.case.players, ((5853, 1929), (5854, 1929), (5852, 1929))):
            seat.eden_sentence = None
            seat.gx, seat.gy = cell
            seat.on_map = True
            self.map.seen[seat] = set()
        self.assertTrue(eden.confined(self.a))
        self.assertTrue(eden.confined(self.b))
        self.assertFalse(eden.confined(self.c))
        self.assertTrue(self.map._within(self.a, self.c))
        self.send_chat(self.a, 0, text='island')
        self.assertEqual(self.acks(self.a), [0])
        self.assertEqual(self.messages(self.b)[0]['entry'], 'island')
        self.assertEqual(self.c.writer.frames, [])
        self.clear()
        self.send_chat(self.c, 0)
        self.assertEqual(self.acks(self.c), [0])
        self.assertEqual(self.a.writer.frames, [])
        self.assertEqual(self.b.writer.frames, [])

    async def test_system_messages_and_other_protocol_frames_pass_unchanged(self):
        self.confine(self.b)
        for channel in (None, 0, 1, 2, 4, 6):
            params = dict(entry='system', nick='Сервер', **{'from': 0})
            if channel is not None:
                params['group'] = channel
            self.b.send('userMsg', **params)
            self.assertEqual(self.messages(self.b)[-1], params)
        self.b.send('usrUp', id=self.a.pid, hp=100, sp=50)
        self.b.send('cmdAck', res=0)
        self.assertEqual(self.b.writer.frames[-2:], [
            ('usrUp', dict(id=self.a.pid, hp=100, sp=50)), ('cmdAck', dict(res=0))])

    async def test_release_restores_ordinary_channels_and_whispers(self):
        self.confine(self.b)
        released = eden.release(self.store, self.b.char_id)
        self.assertIsNotNone(released)
        self.b.eden_sentence = None
        self.assertFalse(eden.confined(self.b))
        for channel in (0, 1, 4, 6):
            self.clear()
            self.send_chat(self.b, channel)
            self.assertEqual(self.acks(self.b), [0])
            self.assertEqual(self.messages(self.a)[0]['from'], self.b.pid)
        for sender, target in ((self.a, self.b), (self.b, self.a)):
            self.clear()
            self.send_chat(sender, to=target.nick)
            self.assertEqual(self.acks(sender), [0])
            self.assertEqual(self.messages(target)[0]['from'], sender.pid)
            self.assertNotIn('group', self.messages(target)[0])

    async def test_refusal_keeps_fifo_and_does_not_change_character_or_social_state(self):
        self.confine(self.a)
        before = (dict(self.store.character(self.a.char_id)),
                  self.store.items_of(self.a.char_id), self.store.quests(self.a.char_id),
                  self.store.clan_member(self.a.char_id),
                  list(self.parties.party_of(self.a).members),
                  self.a.loc, self.a.pos, self.a.gx, self.a.gy, self.a.combat.ap)
        self.send_chat(self.a, 4)
        self.assert_refused(self.a)
        self.send_chat(self.a, 2, text='still in step')
        self.assertEqual(self.acks(self.a), [inventory.RES_REFUSED, 0])
        self.assertEqual(self.messages(self.b)[0]['entry'], 'still in step')
        after = (dict(self.store.character(self.a.char_id)),
                 self.store.items_of(self.a.char_id), self.store.quests(self.a.char_id),
                 self.store.clan_member(self.a.char_id),
                 list(self.parties.party_of(self.a).members),
                 self.a.loc, self.a.pos, self.a.gx, self.a.gy, self.a.combat.ap)
        self.assertEqual(after, before)
        self.assertFalse(self.a.closed)


if __name__ == '__main__':
    run_cases(EdenChat)
