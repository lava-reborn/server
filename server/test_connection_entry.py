"""Real entry handlers and TCP policy fragments; isolated SQLite and writers."""
import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ['LAVA_DB'] = os.path.join(tempfile.mkdtemp(prefix='lava_entry_'), 'entry.sqlite')
os.environ['LAVA_DB_URL'] = ''
os.environ['LAVA_POLICY_PORT'] = '0'
import accounts
import clans
import party
import rooms
import server
from protocol import decode
from testkit import run_cases


class Writer:
    def __init__(self):
        self.frames = []
        self.closed = False
        self.fail_online = False
        self.fail_command = None

    def write(self, data):
        command, params = decode(data[:-1].decode())
        if (self.fail_online and command == 'online') or command == self.fail_command:
            raise BrokenPipeError('injected stale recipient')
        self.frames.append((command, params))

    def close(self):
        self.closed = True


class EntryFailures(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = accounts.Store(':memory:')
        self.online = rooms.Directory()
        self.gmap = rooms.GlobalMapRoom(server.VIEW_RADIUS)
        self.patches = [patch.object(server, name, value) for name, value in (
            ('STORE', self.store), ('ONLINE', self.online),
            ('GMAP', self.gmap), ('ROOMS', rooms.Rooms(server.MOB_TYPES)),
            ('PARTIES', party.Parties(self.online)),
            ('CLANS', clans.Clans(self.store, self.online, self.gmap)),
        )]
        for item in self.patches:
            item.start()
        self.sessions = []

    async def asyncTearDown(self):
        for sess in self.sessions:
            sess.writer.fail_online = False
            sess.writer.fail_command = None
        for sess in self.sessions:
            sess.close(force=True)
        for item in reversed(self.patches):
            item.stop()
        self.store.close()

    def player(self, name):
        self.store.register(name, 'test-secret')
        sess = server.Session(Writer(), ('127.0.0.1', len(self.sessions)))
        self.sessions.append(sess)
        sess.handle('hello', dict(online=2))
        sess.handle('login', dict(hash=accounts.credential(name, 'test-secret')))
        sess.handle('newPers', dict(res=1, sex=0, name=name))
        sess.writer.frames.clear()
        return sess

    async def test_stale_online_recipient_cannot_abort_a_new_players_activation(self):
        first, stale, newcomer = (self.player(name) for name in ('Alpha', 'Bravo', 'Charlie'))
        first.handle('actPlayer', {})
        stale.handle('actPlayer', {})
        stale.writer.fail_online = True
        first.writer.frames.clear()
        newcomer.handle('actPlayer', {})
        commands = [name for name, _ in newcomer.writer.frames]
        self.assertEqual(commands.count('cmdAck'), 1)
        self.assertEqual(commands.count('lcall'), 1)
        self.assertTrue(any(name == 'online' for name, _ in first.writer.frames))
        self.assertTrue(stale.writer.closed)
        self.assertFalse(newcomer.closed)

    async def test_entry_exception_after_success_ack_disconnects_without_a_second_ack(self):
        sess = self.player('Delta')
        with patch.object(sess, 'enter_location', side_effect=RuntimeError('entry failed')):
            sess.handle('actPlayer', {})
        self.assertTrue(sess.closed)
        self.assertTrue(sess.writer.closed)
        self.assertEqual([name for name, _ in sess.writer.frames].count('cmdAck'), 1)

    async def test_stale_party_member_cannot_abort_a_returning_members_entry(self):
        stale,newcomer=(self.player(n) for n in ('PartyOld','PartyNew'))
        stale.handle('actPlayer',{})
        group=party.Party(stale.char_id)
        group.members.append(newcomer.char_id)
        server.PARTIES.by_char.update({stale.char_id:group,newcomer.char_id:group})
        stale.writer.fail_command='p_op'
        newcomer.handle('actPlayer',{})
        self.assertEqual([c for c,p in newcomer.writer.frames].count('lcall'),1)
        self.assertFalse(newcomer.closed)
        self.assertTrue(stale.writer.closed)

    async def test_stale_clan_roster_holder_cannot_abort_a_members_entry(self):
        stale,newcomer=(self.player(n) for n in ('ClanOld','ClanNew'))
        stale.handle('actPlayer',{})
        clan_id=self.store.clan_create(stale.char_id,'EntryClan','entryclan','',None)
        self.store.clan_member_add(newcomer.char_id,clan_id,clans.R_CHAT,'',0)
        clans.view(stale).roster=clan_id
        stale.writer.fail_command='gg_struct'
        newcomer.handle('actPlayer',{})
        self.assertEqual([c for c,p in newcomer.writer.frames].count('lcall'),1)
        self.assertFalse(newcomer.closed)
        self.assertTrue(stale.writer.closed)

    async def test_failed_character_load_does_not_overwrite_durable_position_or_purse(self):
        sess = self.player('Echo')
        char_id = sess.char_id
        sess.char_id, sess.char, sess.active = None, None, None
        self.store.save_position(char_id, 49, 100, 1000, 1000, False)
        before = dict(self.store.character(char_id))
        sess.characters = [before]
        with patch.object(sess, 'load_character', side_effect=RuntimeError('load failed')):
            sess.handle('selPers', dict(num=before['slot']))
        after = dict(self.store.character(char_id))
        self.assertTrue(sess.closed)
        self.assertEqual(after, before)
        self.assertEqual(sess.writer.frames, [])  # selPers never owns a cmdAck

    async def test_fragmented_policy_and_coalesced_hello_use_the_game_port(self):
        tasks = set()
        async def serve(reader, writer):
            task = asyncio.current_task()
            tasks.add(task)
            try:
                await server.handle_client(reader, writer)
            finally:
                tasks.discard(task)
        listener = await asyncio.start_server(serve, '127.0.0.1', 0)
        port = listener.sockets[0].getsockname()[1]
        request = b'<policy-file-request/>\0'
        try:
            for split in (1, 8, len(request) - 2, len(request)):
                with self.subTest(split=split):
                    reader, writer = await asyncio.open_connection('127.0.0.1', port)
                    try:
                        writer.write(request[:split])
                        await writer.drain()
                        await asyncio.sleep(.01)
                        writer.write(request[split:] + b'hello;minor=2;major=0;\0')
                        await writer.drain()
                        policy = await asyncio.wait_for(reader.readuntil(b'\0'), .5)
                        self.assertIn(b'<cross-domain-policy>', policy)
                        hello = await asyncio.wait_for(reader.readuntil(b'\0'), .5)
                        self.assertEqual(decode(hello[:-1].decode())[0], 'hello')
                    finally:
                        writer.close()
                        await writer.wait_closed()
        finally:
            listener.close()
            await listener.wait_closed()
            if tasks:
                await asyncio.wait_for(asyncio.gather(*tasks), 2)


if __name__ == '__main__':
    run_cases(EntryFailures)
