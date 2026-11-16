"""Real session/map acknowledgements and safe placement across the load gap."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import combat
import location_entry
import movement
import rooms
import server
import travel
import world
import test_release_battle as fixtures
from testkit import run_cases


class GlobalEntrySessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.s, self.other, _ = self.case.players
        self.store = self.case.store
        self.directory = rooms.Directory()
        self.manager = rooms.Rooms(world.mob_types())
        self.map = NS(enter=Mock(), leave=Mock(), moved=Mock())
        for name, value in (
            ('ROOMS', self.manager), ('ONLINE', self.directory), ('GMAP', self.map),
            ('PARTIES', NS(online=Mock(), party_of=lambda s: None, disconnected=Mock())),
            ('CLANS', NS(online=Mock(), entered=Mock(), offline=Mock())),
            ('broadcast_online_count', Mock()),
        ):
            self.enterContext(patch.object(server, name, value))
        self.s.training_resume_char = self.s.char_id
        loc = world.location(103)
        self.accepted = (loc.id, loc.entry_cell(), 5879, 2012, False)
        self.s._accepted_place = self.accepted
        self.store.save_position(self.s.char_id, *self.accepted)
        self.on_map()

    async def asyncTearDown(self):
        for room in self.manager.rooms.values():
            if room.combat and room.combat.timer:
                room.combat.timer.cancel()
            clock = getattr(room, 'motion', None)
            if clock and clock.timer:
                clock.timer.cancel()
        self.s.cancel_travel()
        await self.case.asyncTearDown()

    def on_map(self, fx=.5, fy=.5):
        self.s.combat.left()
        if self.s.room is not None:
            self.s.room.players.pop(self.s, None)
        self.s.loc = world.location(103)
        self.s.room = None
        self.s.pos = self.s.loc.entry_cell()
        self.s.gx, self.s.gy = 5879 + fx, 2012 + fy
        self.s.on_map = True
        self.s.eden_sentence = None
        self.s.writer.frames.clear()
        self.map.leave.reset_mock()

    def acks(self):
        return [p['res'] for cmd, p in self.s.writer.frames if cmd == 'cmdAck']

    def room(self):
        result = self.manager.get(103)
        combat.room_combat(result, self.store).keep_hours()
        return result

    def expected(self, x, y):
        room = self.room()
        return location_entry.choose(room.loc, x, y,
            occupied=movement.get(room).occupied(exclude=self.s))

    async def test_real_global_toggle_uses_fraction_and_publishes_same_safe_cell(self):
        positions = set()
        for fx in (.05, .5, .95):
            for fy in (.05, .5, .95):
                with self.subTest(fx=fx, fy=fy):
                    self.on_map(fx, fy)
                    chosen = self.expected(self.s.gx, self.s.gy)
                    self.s.handle('chWorld', {})
                    self.assertFalse(self.s.closed)
                    self.assertFalse(self.s.on_map)
                    self.assertEqual(self.acks(), [0])
                    self.assertEqual(self.s.pos, chosen)
                    self.assertEqual((self.s.gx, self.s.gy), (5879, 2012))
                    self.s.handle('lenter', {'accept': 1})
                    self.assertFalse(self.s.closed)
                    frame = next(p for cmd, p in self.s.writer.frames if cmd == 'lenter')
                    self.assertEqual(frame['pos'], chosen)
                    self.assertEqual(self.s.pos, chosen)
                    self.assertIsNone(self.s._global_entry)
                    self.assertIn(self.s, self.room().players)
                    positions.add(chosen)
        self.assertGreater(len(positions), 3)

    async def test_loading_rechecks_occupied_entry_and_escape_route(self):
        self.s.handle('chWorld', {})
        first = self.s.pos
        room = self.room()
        # Leave the selected hex empty, but surround it: free_cell alone
        # would keep it and strand the loading player inside this NPC ring.
        import progression
        for i, cell in enumerate(progression.hex_neighbours(first, room.loc.width, room.loc.height)):
            room.npcs[8000 + i] = rooms.NPC(cell, 1, world.TEACHER)
        expected = self.expected(5879.5, 2012.5)
        self.assertNotEqual(first, expected)
        self.s.handle('lenter', {'accept': 1})
        self.assertFalse(self.s.closed)
        self.assertEqual(self.s.pos, expected)
        self.assertEqual(self.acks(), [0])

    async def test_all_safe_entries_taken_refuses_before_success_and_stays_on_map(self):
        room = self.room()
        before = (self.s.loc, self.s.pos, self.s.gx, self.s.gy)
        with patch.object(movement.get(room), 'occupied', return_value=range(room.loc.width * room.loc.height)):
            self.s.handle('chWorld', {})
        self.assertEqual(self.acks(), [server.RES_NO_WAY])
        self.assertTrue(self.s.on_map)
        self.assertFalse(self.s.closed)
        self.assertEqual((self.s.loc, self.s.pos, self.s.gx, self.s.gy), before)
        self.assertFalse(any(cmd == 'lcall' for cmd, _ in self.s.writer.frames))
        self.map.leave.assert_not_called()

    async def test_all_entries_blocked_during_load_refuses_and_preserves_last_accepted_place(self):
        self.s.handle('chWorld', {})
        room = self.room()
        self.s.writer.frames.clear()
        with patch.object(movement.get(room), 'occupied', return_value=range(room.loc.width * room.loc.height)):
            self.s.handle('lenter', {'accept': 1})
        self.assertEqual(self.acks(), [server.RES_NO_WAY])
        self.assertTrue(self.s.closed)
        self.assertFalse(any(cmd == 'lenter' for cmd, _ in self.s.writer.frames))
        saved = self.store.character(self.s.char_id)
        self.assertEqual(tuple(saved[k] for k in ('loc', 'pos', 'gx', 'gy', 'on_map')), self.accepted)

    async def test_unexpected_preflight_or_lcall_failure_closes_without_duplicate_ack(self):
        # A broken occupancy/load path must never leave the ACK FIFO waiting.
        for after_ack in (False, True):
            with self.subTest(after_ack=after_ack):
                self.s.closed = False
                self.on_map()
                target = (patch.object(self.s, 'enter_location', side_effect=RuntimeError('failed lcall'))
                          if after_ack else patch.object(self.manager, 'get', side_effect=RuntimeError('failed room')))
                with target:
                    self.s.handle('chWorld', {})
                self.assertTrue(self.s.closed)
                self.assertEqual(self.acks(), [0] if after_ack else [])
                saved = self.store.character(self.s.char_id)
                self.assertEqual(tuple(saved[k] for k in ('loc', 'pos', 'gx', 'gy', 'on_map')), self.accepted)

    async def test_non_map_arrival_clears_fractional_entry_and_keeps_its_own_position(self):
        self.s.handle('chWorld', {})
        self.assertIsNotNone(self.s._global_entry)
        self.s.loc = world.location(41)
        self.s.pos = self.s.loc.entry_cell()
        self.s.gx, self.s.gy = 5965, 1728
        original = self.s.pos
        self.s.enter_location()
        self.assertIsNone(self.s._global_entry)
        with patch.object(location_entry, 'choose', side_effect=AssertionError('Not a map arrival')):
            self.s.handle('lenter', {'accept': 1})
        self.assertFalse(self.s.closed)
        self.assertEqual(self.s.pos, original)

    async def test_reconnect_from_map_uses_floor_and_preserves_fraction_through_loading(self):
        self.on_map(.95, .95)
        self.s.save_place()
        saved = self.store.character(self.s.char_id)
        expected = self.expected(5879.95, 2012.95)
        pending = self.s.restore(saved)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy), (103, 5879, 2012))
        self.s.enter_location(global_entry=pending)
        self.assertEqual(self.s.pos, expected)
        self.s.handle('lenter', {'accept': 1})
        self.assertFalse(self.s.closed)
        self.assertEqual(self.s.pos, expected)

    async def test_reconnect_in_eden_preserves_confinement_and_fractional_entry(self):
        import eden
        import eden_map
        self.s.eden_sentence = eden.assign(self.store, self.s.char_id, 'test', 'Map entry')
        x, y = eden_map.CENTER_CELL
        point = (x + .95, y + .95)
        self.store.save_position(self.s.char_id, eden.CENTER, None, *point, True)
        saved = self.store.character(self.s.char_id)
        pending = self.s.restore(saved)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy), (eden.CENTER, x, y))
        self.assertEqual(pending[3:], point)
        self.s.enter_location(global_entry=pending)
        room = self.manager.get(eden.CENTER)
        combat.room_combat(room, self.store).keep_hours()
        expected = location_entry.choose(room.loc, *point,
            occupied=movement.get(room).occupied(exclude=self.s))
        self.s.handle('lenter', {'accept': 1})
        self.assertFalse(self.s.closed)
        self.assertEqual(self.s.pos, expected)
        self.assertTrue(eden.inside(self.s.loc))

    async def test_corrupt_saved_map_coordinates_fall_back_without_login_loop_or_eden_escape(self):
        import eden
        for confined in (False, True):
            if confined:
                eden.assign(self.store, self.s.char_id, 'test', 'Invalid map position')
            for x, y in ((None, None), (float('inf'), 2012), (-1, 2012), (5879, float('nan'))):
                with self.subTest(confined=confined, x=x, y=y):
                    self.store.save_position(self.s.char_id, 103, None, x, y, True)
                    saved = self.store.character(self.s.char_id)
                    pending = self.s.restore(saved)
                    self.assertIsNone(pending)
                    self.assertFalse(self.s.on_map)
                    if confined:
                        self.assertTrue(eden.inside(self.s.loc))
                    else:
                        expected = travel.home(dict(saved), (server.START_LOC, server.GLOBAL_X, server.GLOBAL_Y))
                        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy), expected)
                    self.assertNotIn(self.s.pos, self.s.loc.obstacles)


if __name__ == '__main__':
    run_cases(GlobalEntrySessionTests)
