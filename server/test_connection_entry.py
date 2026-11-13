"""Real entry handlers and TCP policy fragments; isolated SQLite and writers."""
import asyncio
import os
import socket
import struct
import tempfile
import unittest
from unittest.mock import patch

os.environ['LAVA_DB'] = os.path.join(tempfile.mkdtemp(prefix='lava_entry_'), 'entry.sqlite')
os.environ['LAVA_DB_URL'] = ''
os.environ['LAVA_POLICY_PORT'] = '0'
import accounts
import clans
import combat
import inventory
import items
import party
import rooms
import server
import world
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

    async def test_reset_real_tcp_recipient_does_not_receive_fanout_or_block_entry(self):
        connected = asyncio.get_running_loop().create_future()
        def accept(reader, writer):
            connected.set_result((reader, writer))
        listener = await asyncio.start_server(accept, '127.0.0.1', 0)
        client = remote = None
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.setblocking(False)
            await asyncio.get_running_loop().sock_connect(
                client, ('127.0.0.1', listener.sockets[0].getsockname()[1]))
            reader, remote = await asyncio.wait_for(connected, 2)
            stale = self.player('ResetOld')
            stale.handle('actPlayer', {})
            stale.writer = remote
            client.setsockopt(
                socket.SOL_SOCKET, socket.SO_LINGER,
                struct.pack('hh' if os.name == 'nt' else 'ii', 1, 0))
            # A raw socket close preserves SO_LINGER's RST semantics on
            # Windows too; Proactor transport.abort first calls shutdown.
            client.close()
            try:
                await asyncio.wait_for(reader.read(), 2)
            except ConnectionResetError:
                pass
            await asyncio.sleep(0)
            self.assertTrue(remote.is_closing())
            with patch.object(stale, 'send', wraps=stale.send) as send:
                self.assertFalse(rooms.send_to(stale, 'online', dict(count=2)))
                send.assert_not_called()
                newcomer = self.player('ResetNew')
                newcomer.handle('actPlayer', {})
            self.assertFalse(newcomer.closed)
            self.assertEqual([c for c,p in newcomer.writer.frames].count('lcall'), 1)
        finally:
            listener.close()
            if client is not None:
                client.close()
            for writer in (remote,):
                if writer is not None:
                    writer.close()
                    try:
                        await asyncio.wait_for(writer.wait_closed(), 2)
                    except (ConnectionError, TimeoutError):
                        writer.transport.abort()
            await asyncio.wait_for(listener.wait_closed(), 2)

    async def test_failed_location_entry_keeps_last_accepted_location_on_reconnect(self):
        for late in (False, True):
            with self.subTest(after_position_save=late):
                name = 'LateEntry' if late else 'EarlyEntry'
                sess = self.player(name)
                sess.handle('actPlayer', {})
                sess.handle('lenter', dict(accept=1))
                before = dict(self.store.character(sess.char_id))
                sess.loc = world.location(49)
                sess.pos = sess.loc.entry_cell()
                sess.enter_location()
                sess.character().afro += 7
                if late:
                    failure = patch.object(server.CLANS, 'entered', side_effect=RuntimeError('bad destination after save'))
                else:
                    failure = patch.object(sess, 'enter_room', side_effect=RuntimeError('bad destination before save'))
                with failure:
                    sess.handle('lenter', dict(accept=1))
                self.assertTrue(sess.closed)
                after = dict(self.store.character(sess.char_id))
                self.assertEqual(tuple(after[k] for k in ('loc','pos','gx','gy','on_map')),
                                 tuple(before[k] for k in ('loc','pos','gx','gy','on_map')))
                self.assertEqual(after['afro'], before['afro'] + 7)
                returning = server.Session(Writer(), ('127.0.0.1', 99))
                self.sessions.append(returning)
                returning.handle('hello', {})
                returning.handle('login', dict(hash=accounts.credential(name, 'test-secret')))
                returning.handle('selPers', dict(num=before['slot']))
                returning.handle('lenter', dict(accept=1))
                self.assertFalse(returning.closed)
                self.assertEqual(returning.loc.id, before['loc'])

    async def test_first_entry_failure_uses_safe_start_without_changing_money(self):
        sess = self.player('FirstEntry')
        sess.loc = world.location(49)
        sess.pos = sess.loc.entry_cell()
        sess.handle('actPlayer', {})
        before = sess.character().afro
        with patch.object(sess, 'enter_room', side_effect=RuntimeError('initial destination failed')):
            sess.handle('lenter', dict(accept=1))
        row = self.store.character(sess.char_id)
        self.assertTrue(sess.closed)
        self.assertEqual((row['loc'], row['on_map'], row['afro']), (server.START_LOC, 0, before))

    async def test_corrupt_bizon_does_not_prevent_character_selection(self):
        sess = self.player('BadMagazine')
        fields = inventory.new_fields(26185)
        root = fields.pop('root')
        fields.update(ammo_count=129, ammo_type=6055, slot=inventory.BAG)
        gun = self.store.create_item(sess.char_id, 26185, root, **fields)
        slot = self.store.character(sess.char_id)['slot']
        sess.close(force=True)
        returning = server.Session(Writer(), ('127.0.0.1', 99))
        self.sessions.append(returning)
        returning.handle('hello', {})
        returning.handle('login', dict(hash=accounts.credential('BadMagazine', 'test-secret')))
        with patch('magazine_migration.log.error') as error:
            returning.handle('selPers', dict(num=slot))
        error.assert_called_once()
        self.assertFalse(returning.closed)
        returning.handle('lenter', dict(accept=1))
        self.assertFalse(returning.closed)
        self.assertEqual(self.store.item(gun['uniq']), gun)

    async def test_failed_resurrection_arrival_does_not_restore_the_battlefield(self):
        sess = self.player('HomeFailure')
        sess.loc = world.location(59)
        sess.pos = sess.loc.entry_cell()
        sess.handle('actPlayer', {})
        sess.handle('lenter', dict(accept=1))
        self.assertEqual(sess._accepted_place[0], 59)
        sess.combat.die(None)
        sess.handle('resurrect', dict(res_type=0))
        with patch.object(sess, 'enter_room', side_effect=RuntimeError('home entry failed')):
            sess.handle('lenter', dict(accept=1))
        row = self.store.character(sess.char_id)
        self.assertEqual((row['loc'], row['death']), (server.START_LOC, 0))

    async def test_repeated_death_during_reload_does_not_block_reload_after_resurrection(self):
        sess = self.player('ReloadLife')
        char = sess.character()
        for skill in char.skill:
            skill[0] = 20
        for spec in char.spec:
            spec[0] = 4
        char.recalc()
        char.save(self.store)
        # G equipment/ammunition stays with the owner on death, so this
        # scenario distinguishes a stuck action from simply dropped ammo.
        gun_type = 26186
        ammo_type = next(t for t in items.params_of(gun_type)['comp_array']
                         if items.params_of(t).get('g_cost'))
        def give(type_id, **changes):
            fields = inventory.new_fields(type_id)
            root = fields.pop('root')
            fields.update(changes)
            return self.store.create_item(sess.char_id, type_id, root, **fields)
        previous = sess.inv.in_slot(inventory.PRIMARY)
        if previous:
            self.store.update_item(previous['uniq'], slot=inventory.BAG)
        gun = give(gun_type, slot=inventory.PRIMARY)
        ammunition = [give(ammo_type, count=100, slot=inventory.BAG) for _ in range(5)]
        sess.handle('actPlayer', {})
        sess.handle('lenter', dict(accept=1))
        for ammo in ammunition:
            self.store.update_item(gun['uniq'], ammo_count=0, ammo_type=0)
            payload = dict(obj=inventory.oid_of(gun), target=inventory.oid_of(ammo))
            with patch.object(inventory.pace, 'paced', return_value=3600):
                sess.handle('ss_use', dict(type=inventory.USE_LOAD, **payload))
            timer = sess.combat.reloading
            self.assertIsNotNone(timer)
            callback, args = timer._callback, timer._args
            sess.combat.die(None)
            count = self.store.item(ammo['uniq'])['count']
            callback(*args)
            self.assertEqual(self.store.item(ammo['uniq'])['count'], count)
            sess.handle('resurrect', dict(res_type=0))
            sess.handle('lenter', dict(accept=1))
            self.assertFalse(sess.combat.dead)
            with patch.object(inventory.pace, 'paced', return_value=3600):
                sess.handle('ss_use', dict(type=inventory.USE_LOAD, **payload))
            timer = sess.combat.reloading
            self.assertIsNotNone(timer)
            timer._callback(*timer._args)
            clip = items.params_of(gun_type)['clip_size']
            self.assertEqual(self.store.item(gun['uniq'])['ammo_count'], clip)
            remainder = self.store.item(ammo['uniq'])
            self.assertEqual(remainder['count'] if remainder else 0, count - clip)
            self.assertIsNone(sess.combat.reloading)

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
