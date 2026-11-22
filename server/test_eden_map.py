"""The foreman's map preview is one cell, never a route out of Eden."""
import json
import math
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import test_release_battle as fixtures
import eden
import eden_map
import inventory
import location_entry
import rooms
import server
import travel
import world
from testkit import run_cases


class EdenMapTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.store = self.case.store
        self.s, self.other, _ = self.case.players
        self.directory = rooms.Directory()
        self.manager = rooms.Rooms(world.mob_types())
        self.map = NS(enter=Mock(), leave=Mock(), moved=Mock())
        self.enterContext(patch.object(server, 'ROOMS', self.manager))
        self.enterContext(patch.object(server, 'ONLINE', self.directory))
        self.enterContext(patch.object(server, 'GMAP', self.map))
        self.enterContext(patch.object(server, 'PARTIES', NS(
            online=lambda _s: None, party_of=lambda _s: None)))
        self.enterContext(patch.object(server, 'CLANS', NS(
            online=lambda _s: None, entered=lambda _s: None)))
        self.enterContext(patch.object(server, 'broadcast_online_count'))
        self.s.eden_sentence = eden.assign(self.store, self.s.char_id, 'test', 'Map regression')
        self.store.save_character_state(self.s.char_id, home_loc=41, home_gx=5970, home_gy=1730)
        self.place(eden.CENTER)

    async def asyncTearDown(self):
        for room in self.manager.rooms.values():
            if room.combat and room.combat.timer:
                room.combat.timer.cancel()
        self.s.cancel_travel()
        self.other.cancel_travel()
        await self.case.asyncTearDown()

    def place(self, loc_id):
        self.s.combat.left()
        if self.s.room is not None:
            self.s.room.players.pop(self.s, None)
        self.s.loc = world.location(loc_id)
        self.s.room = self.manager.get(loc_id)
        self.s.room.players[self.s] = True
        self.s.pos = self.s.loc.entry_cell()
        self.s.gx, self.s.gy = eden_map.cell_of(loc_id)
        self.s.on_map = False
        self.s.writer.frames.clear()

    def answers(self):
        return [p['res'] for cmd, p in self.s.writer.frames if cmd == 'cmdAck']

    def open_map(self):
        self.s.cmd_chWorld({})
        self.assertEqual(self.answers(), [0])
        self.assertTrue(self.s.on_map)
        self.assertIsNone(self.s.room)

    async def test_historical_mapping_is_non_pvp_and_closed_to_ordinary_global_travel(self):
        self.assertEqual(len(eden_map.CELL_TO_LOC), 62)
        self.assertEqual(len(set(eden_map.CELL_TO_LOC.values())), 62)
        for cell, loc_id in eden_map.CELL_TO_LOC.items():
            self.assertEqual(world.location_at(*cell), loc_id)
            self.assertEqual(world.cell_of(loc_id), cell)
            self.assertFalse(world.location(loc_id).pvp)
            with patch.object(world, 'terrain_overrides', return_value={cell: True}):
                self.assertFalse(world.passable(*cell))
        for loc_id in eden.LOCATIONS:
            self.assertFalse(travel.no_map(loc_id))

    async def test_every_scene_opens_global_map_and_can_return_without_moving(self):
        for loc_id in eden.LOCATIONS:
            self.place(loc_id)
            cell = eden_map.cell_of(loc_id)
            point = location_entry.map_position(self.s.loc, self.s.pos, *cell)
            self.open_map()
            self.assertEqual((self.s.gx, self.s.gy), point)
            self.assertEqual((math.floor(self.s.gx), math.floor(self.s.gy)), cell)
            self.s.writer.frames.clear()
            self.s.step_on_map(0, 0)
            self.assertEqual((self.s.gx, self.s.gy), point)
            self.assertIsNone(self.s.leg)
            self.assertIsNone(self.s.arrival)
            self.s.writer.frames.clear()
            self.s.cmd_chWorld({})
            self.assertFalse(self.s.on_map)
            self.assertEqual(self.s.loc.id, loc_id)
        self.place(eden.CENTER)
        self.open_map()
        self.s.writer.frames.clear()
        self.s.cmd_lenter({'accept': 1})
        self.assertEqual(self.answers(), [server.RES_NO_WAY])
        self.assertIsNone(self.s.room)
        self.assertTrue(self.s.on_map)
        self.assertFalse(eden.allowed(self.s, server.quests.get(eden.GIFT)))

    async def test_local_corner_projection_stays_in_its_eden_square_on_wire_and_return(self):
        for fx, fy in ((0, 0), (.5, .5), (1, 0), (0, 1), (1, 1)):
            self.place(eden.CENTER)
            loc = self.s.loc
            free = set(range(loc.width * loc.height)) - loc.obstacles
            self.s.pos = min(free, key=lambda c: (
                (c % loc.width / (loc.width - 1) - fx) ** 2
                + (c // loc.width / (loc.height - 1) - fy) ** 2, c))
            self.open_map()
            packet = next(p for cmd, p in self.s.writer.frames if cmd == 'gmap')
            self.assertEqual((packet['x'], packet['y']), (self.s.gx, self.s.gy))
            self.assertEqual((math.floor(packet['x']), math.floor(packet['y'])),
                             eden_map.CENTER_CELL)
            self.assertTrue(eden_map.inside_map(self.s.gx, self.s.gy))
            self.s.writer.frames.clear()
            self.s.cmd_chWorld({})
            self.assertEqual(self.answers(), [0])
            self.assertFalse(self.s.on_map)
            self.assertEqual(self.s.loc.id, eden.CENTER)
            self.assertIsNotNone(self.s.eden_sentence)

    async def test_local_exit_request_from_non_exit_cell_is_refused(self):
        self.place(eden.CENTER)
        self.s.cmd_chWorld({'to': 1})
        self.assertEqual(self.answers(), [server.RES_NOT_AVAILABLE])
        self.assertFalse(self.s.on_map)

    async def test_boundaries_finite_inputs_and_ordinary_rock_exception_cannot_cross_island(self):
        x, y = eden_map.CENTER_CELL
        for dx, dy in ((100, 0), (-100, 0), (0, 100), (0, -100),
                       (100, 100), (-100, -100), (1e300, -1e300),
                       (float('nan'), 1), (float('inf'), 1), (0, -float('inf'))):
            end = eden_map.walk(x + .5, y + .5, dx, dy)
            self.assertTrue(eden_map.inside_map(*end), (dx, dy, end))
            self.assertTrue(all(math.isfinite(v) for v in end))
        self.assertTrue(eden_map.inside_map(x + .999, y + .999))
        self.assertFalse(eden_map.inside_map(5970, 1730))
        self.assertFalse(eden_map.inside_cell(float('nan'), y))
        edge_x = min(cell[0] for cell in eden_map.CELL_TO_LOC)
        for passable in (True, False):
            with patch.object(world, 'passable', return_value=passable):
                end = travel.walk(edge_x - 1.5, y + .5, 4, 0)
                self.assertLess(end[0], edge_x)
                self.assertFalse(eden_map.inside_cell(*end))
        with patch.object(world, 'passable', return_value=True):
            self.assertEqual(travel.walk(5970.2, 1730.3, 2, 1), (5972.2, 1731.3))

    async def test_global_walk_cannot_cross_a_closed_gap_or_diagonal_wall(self):
        # The destination is open, but the straight path crosses a closed
        # cell: validating only the endpoint must not allow this shortcut.
        mask = {(0, 0): 1, (1, 0): 2, (1, 1): 3, (2, 1): 4, (3, 1): 5, (3, 0): 6}
        with patch.object(eden_map, 'CELL_TO_LOC', mask):
            end = eden_map.walk(.5, .5, 3, 0)
            self.assertLess(end[0], 2)
            self.assertGreater(end[0], 1)
        with patch.object(eden_map, 'CELL_TO_LOC', {(0, 0): 1, (1, 1): 2}):
            end = eden_map.walk(.5, .5, 1, 1)
            self.assertLess(end[0], 1)
            self.assertLess(end[1], 1)

    async def test_global_walk_stays_inside_the_mask_along_every_segment(self):
        for x, y in eden_map.CELL_TO_LOC:
            for dx, dy in ((100, 0), (-100, 0), (0, 100), (0, -100),
                           (100, 100), (-100, 100), (100, -100), (-100, -100),
                           (1e300, 1e300), (float('inf'), 0)):
                end = eden_map.walk(x + .5, y + .5, dx, dy)
                self.assertTrue(eden_map.inside_cell(*end), ((x, y), dx, dy, end))
                self.assertTrue(all(math.isfinite(v) for v in end))
                for index in range(41):
                    ratio = index / 40
                    point = (x + .5 + (end[0] - x - .5) * ratio,
                             y + .5 + (end[1] - y - .5) * ratio)
                    self.assertTrue(eden_map.inside_cell(*point), (point, end))

    async def test_global_travel_enters_another_work_area_and_survives_reconnect(self):
        self.open_map()
        x, y = eden_map.CENTER_CELL
        with self.case.at(100):
            self.s.step_on_map(-.5, .5)
        self.assertIsNotNone(self.s.arrival)
        self.s.arrival.cancel()
        self.s.arrive(x - .5, y + .5)
        self.s.save_place()
        expected = eden_map.location_at(x - .5, y + .5)
        saved = self.store.character(self.s.char_id)
        self.assertEqual(saved['loc'], expected)
        self.s.restore(saved)
        self.assertEqual(self.s.loc.id, expected)
        self.assertIsNotNone(self.s.eden_sentence)

    async def test_all_internal_edges_use_canonical_cells_and_ordinary_exit_gate(self):
        transitions = 0
        for lid, cell in eden_map.LOC_TO_CELL.items():
            loc = world.location(lid)
            for side in travel.SIDES:
                nx, ny = travel.neighbour(*cell, side)
                target = eden_map.location_at(nx, ny)
                if target is None:
                    # A forged client/exit table may claim an outer side;
                    # the planner still cannot leave the district.
                    with patch.object(travel, 'side_at', return_value=side):
                        with self.assertRaises(travel.Refused):
                            travel.plan_exit(loc, loc.entry_cell(), 5970, 1730)
                    continue
                pos = next(p for p, s in travel.exit_sides(loc).items() if s == side)
                self.place(lid)
                self.s.pos = pos
                # Stale ordinary-world coordinates do not select the far side.
                self.s.gx, self.s.gy = 5970, 1730
                self.s.cmd_chWorld({'to': 1})
                self.assertEqual(self.answers(), [0], (lid, side))
                self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy),
                                 (target, nx, ny), (lid, side))
                self.assertFalse(self.s.on_map)
                self.assertIsNotNone(self.s.eden_sentence)
                transitions += 1
        expected = sum(eden_map.location_at(*travel.neighbour(*cell, side)) is not None
                       for cell in eden_map.CELL_TO_LOC for side in travel.SIDES)
        self.assertEqual(transitions, expected)
        self.assertGreater(transitions, 24)

    async def test_actual_global_vectors_and_late_arrival_save_only_district_cells(self):
        self.open_map()
        x, y = eden_map.CENTER_CELL
        for dx, dy in ((100, 100), (-100, -100), (1e300, 1), (float('nan'), 0)):
            self.s.cancel_travel()
            self.s.gx, self.s.gy = x + .5, y + .5
            with self.case.at(100):
                self.s.step_on_map(dx, dy)
            if self.s.arrival is not None:
                self.assertTrue(eden_map.inside_map(*self.s.arrival._args))
            with self.case.at(100000):
                self.assertTrue(eden_map.inside_map(*self.s.current_pos()))
                self.s.save_place()
            row = self.store.character(self.s.char_id)
            self.assertTrue(eden.inside(row['loc']))
            self.assertTrue(eden_map.inside_map(row['gx'], row['gy']))
            self.s.arrive(5970, 1730)
            self.assertTrue(eden_map.inside_map(self.s.gx, self.s.gy))

    async def test_enter_cell_and_reconnect_use_floor_in_bottom_right_corner(self):
        self.open_map()
        self.s.gx, self.s.gy = 5858.999, 1929.999
        self.s.cmd_chWorld({})
        self.assertFalse(self.s.on_map)
        self.assertEqual(self.s.loc.id, eden.CENTER)
        self.assertTrue(any(cmd == 'lcall' and p['id'] == eden.CENTER
                            for cmd, p in self.s.writer.frames))
        for point in ((5858.999, 1929.999), (5859.1, 1930.1), (5970, 1730)):
            self.store.save_position(self.s.char_id, 264, None, *point, True)
            self.s.restore(self.store.character(self.s.char_id))
            self.assertFalse(self.s.on_map)
            expected = eden_map.location_at(*point) or 264
            self.assertEqual(self.s.loc.id, expected)
            self.assertEqual((self.s.gx, self.s.gy), eden_map.cell_of(expected))
            self.assertIsNotNone(self.s.eden_sentence)

    async def test_interception_and_random_encounters_cannot_leave_the_preview(self):
        self.open_map()
        self.other.on_map = True
        self.directory.add(self.s)
        self.directory.add(self.other)
        self.s.intercept(self.other.pid)
        self.assertIsNone(self.s.chase)
        self.other.intercept(self.s.pid)
        self.assertIsNone(self.other.chase)
        with patch.object(self.s, 'enter_cell') as enter:
            self.s.caught(self.other, 5858.5, 1929.5)
            enter.assert_not_called()
        self.assertFalse(server.ENCOUNTERS.allowed(self.s))
        server.ENCOUNTERS.arm(self.s, 5858.1, 1929.1, 5858.9, 1929.9, 1)
        self.assertNotIn(self.s, server.ENCOUNTERS.armed)

    async def test_ordinary_handlers_send_forged_island_positions_home(self):
        self.store.save_character_state(self.other.char_id, home_loc=41,
                                        home_gx=5970, home_gy=1730)
        for cell in eden_map.CELL_TO_LOC:
            for action in ('enter', 'walk', 'arrive'):
                self.other.on_map = True
                self.other.gx, self.other.gy = cell
                self.other.loc = world.location(eden.CENTER)
                if action == 'enter':
                    self.other.enter_cell()
                elif action == 'walk':
                    self.other.step_on_map(1, 0)
                else:
                    self.other.arrive(*cell)
                self.assertFalse(self.other.on_map, (cell, action))
                self.assertEqual((self.other.loc.id, self.other.gx, self.other.gy),
                                 (41, 5970, 1730), (cell, action))
                self.assertIsNone(getattr(self.other, 'eden_sentence', None))

    async def test_late_global_position_stops_at_planned_end_and_enters_the_actual_target(self):
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1929.5
        with self.case.at(100):
            self.s.step_on_map(100, 0)
        end = self.s.arrival._args
        self.assertEqual(end, (5866.98, 1929.5))
        self.assertEqual(self.s._eden_leg_end, end)
        started, sx, sy, vx, vy = self.s.leg
        duration = math.hypot(end[0] - sx, end[1] - sy) / math.hypot(vx, vy)
        with self.case.at(started + duration / 2):
            self.assertAlmostEqual(self.s.current_pos()[0], (sx + end[0]) / 2)
        with self.case.at(started + duration + 1):
            self.assertEqual(self.s.current_pos(), end)
            self.s.save_place()
            saved = self.store.character(self.s.char_id)
            self.assertEqual((saved['loc'], saved['gx'], saved['gy']),
                             (eden_map.location_at(*end), *end))
            self.s.enter_cell()
        self.assertFalse(self.s.on_map)
        self.assertEqual(self.s.loc.id, eden_map.location_at(*end))
        self.assertEqual((self.s.gx, self.s.gy), (5866, 1929))
        self.assertIsNone(self.s.leg)
        self.assertIsNone(self.s.arrival)
        self.assertIsNone(self.s._eden_leg_end)

    async def test_late_global_position_cannot_jump_across_the_concave_notch(self):
        source = eden_map.location_at(5858.5, 1927.5)
        self.place(source)
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1927.5
        with self.case.at(100):
            self.s.step_on_map(100, 0)
        end = self.s.arrival._args
        self.assertEqual(end, (5858.98, 1927.5))
        self.assertNotIn((5859, 1927), eden_map.CELL_TO_LOC)
        self.assertIn((5860, 1927), eden_map.CELL_TO_LOC)
        with self.case.at(100000):
            self.assertEqual(self.s.current_pos(), end)
            self.s.save_place()
            self.assertEqual(self.store.character(self.s.char_id)['loc'], source)
            self.s.enter_cell()
        self.assertEqual(self.s.loc.id, source)
        self.assertEqual((self.s.gx, self.s.gy), (5858, 1927))

    async def test_legacy_global_leg_stops_at_first_closed_edge_before_save_and_entry(self):
        source = eden_map.location_at(5858.5, 1927.5)
        self.place(source)
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1927.5
        self.s.leg = (100, self.s.gx, self.s.gy, 1, 0)
        self.s._eden_leg_end = None
        with self.case.at(102):
            self.assertEqual(self.s.current_pos(), (5858.98, 1927.5))
            self.s.save_place()
            self.assertEqual(self.store.character(self.s.char_id)['loc'], source)
            self.s.enter_cell()
        self.assertEqual(self.s.loc.id, source)

    async def test_arrival_and_cancellation_clear_the_eden_endpoint_without_capping_ordinary_walks(self):
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1929.5
        with self.case.at(100):
            self.s.step_on_map(.2, .1)
        end = self.s.arrival._args
        self.s.arrival.cancel()
        self.s.arrive(*end)
        self.assertIsNone(self.s._eden_leg_end)
        with self.case.at(101):
            self.s.step_on_map(.2, .1)
        self.assertIsNotNone(self.s._eden_leg_end)
        self.s.cancel_travel()
        self.assertIsNone(self.s._eden_leg_end)
        self.other.on_map = True
        self.other.gx, self.other.gy = 5970.5, 1730.5
        self.other.leg = (100, self.other.gx, self.other.gy, 1, 0)
        self.other._eden_leg_end = (5971, 1730.5)
        with self.case.at(102):
            self.assertEqual(self.other.current_pos(), (5972.5, 1730.5))

    async def test_real_close_preserves_the_mid_leg_eden_cell_for_reconnect(self):
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1929.5
        with self.case.at(100):
            self.s.step_on_map(100, 0)
        arrival = self.s.arrival
        end = arrival._args
        started, sx, sy, vx, vy = self.s.leg
        duration = math.hypot(end[0] - sx, end[1] - sy) / math.hypot(vx, vy)
        with self.case.at(started + duration / 2), \
                patch.object(server.PARTIES, 'disconnected', lambda _s: None, create=True), \
                patch.object(server.CLANS, 'offline', lambda _s: None, create=True):
            expected = self.s.current_pos()
            self.s.close(force=True)
        saved = self.store.character(self.s.char_id)
        expected_loc = eden_map.location_at(*expected)
        self.assertNotEqual(expected_loc, eden.CENTER)
        self.assertTrue(self.s.closed)
        self.assertTrue(arrival.cancelled())
        self.assertEqual((saved['loc'], saved['gx'], saved['gy'], saved['on_map']),
                         (expected_loc, *expected, 1))
        self.assertIsNone(self.s.leg)
        self.assertIsNone(self.s._eden_leg_end)
        self.s.restore(saved)
        self.assertFalse(self.s.on_map)
        self.assertEqual(self.s.loc.id, expected_loc)
        self.assertEqual((self.s.gx, self.s.gy), eden_map.cell_of(expected_loc))

    async def test_late_cancel_preserves_the_planned_endpoint_before_saving(self):
        self.open_map()
        self.s.gx, self.s.gy = 5858.5, 1929.5
        with self.case.at(100):
            self.s.step_on_map(100, 0)
        arrival, end = self.s.arrival, self.s.arrival._args
        with self.case.at(100000):
            self.s.cancel_travel()
            self.s.save_place()
        saved = self.store.character(self.s.char_id)
        self.assertEqual((self.s.gx, self.s.gy), end)
        self.assertEqual((saved['loc'], saved['gx'], saved['gy']),
                         (eden_map.location_at(*end), *end))
        self.assertTrue(arrival.cancelled())
        self.assertIsNone(self.s._eden_leg_end)

    async def test_ordinary_cancel_keeps_its_existing_coordinate_behavior(self):
        self.other.on_map = True
        self.other.gx, self.other.gy = 5970.5, 1730.5
        self.other.leg = (100, self.other.gx, self.other.gy, 1, 0)
        with self.case.at(102):
            self.assertEqual(self.other.current_pos(), (5972.5, 1730.5))
            self.other.cancel_travel()
        self.assertEqual((self.other.gx, self.other.gy), (5970.5, 1730.5))
        self.assertIsNone(self.other.leg)

    def ordinary_map_departure(self):
        eden.release(self.store, self.s.char_id)
        self.s.eden_sentence = None
        self.s.leave_room()
        self.s.loc, self.s.on_map = world.location(41), True
        self.s.gx, self.s.gy = 5970.5, 1730.5
        self.store.save_position(self.s.char_id, 41, None, self.s.gx, self.s.gy, True)
        with self.case.at(100):
            self.s.step_on_map(2, 0)
        self.assertIsNotNone(self.s.arrival)
        return dict(kind='eden', char_id=self.s.char_id,
                    account_id=self.s.active['account_id'], admin='test',
                    args_json=json.dumps({'reason': 'Assignment from a moving map'}))

    async def test_real_assignment_cancels_ordinary_map_leg_before_confined_restore(self):
        action = self.ordinary_map_departure()
        arrival = self.s.arrival
        before_money = self.store.money(self.s.char_id)
        with patch.object(server, 'session_for', return_value=self.s):
            server.apply_admin_action(action)
        self.assertTrue(arrival.cancelled())
        self.assertIsNone(self.s.arrival)
        self.assertIsNone(self.s.leg)
        self.assertIsNone(self.s._eden_leg_end)
        self.map.leave.assert_called_with(self.s)
        self.assertFalse(self.s.on_map)
        self.assertEqual(self.s.loc.id, eden.CENTER)
        self.assertIsNotNone(self.s.eden_sentence)
        self.assertEqual(self.store.character(self.s.char_id)['loc'], eden.CENTER)
        self.assertEqual(self.store.money(self.s.char_id), before_money)

    async def test_assignment_map_departure_failure_keeps_the_committed_sentence_and_destination(self):
        action = self.ordinary_map_departure()
        arrival = self.s.arrival
        with patch.object(server, 'session_for', return_value=self.s), \
                patch.object(self.map, 'leave', side_effect=RuntimeError('map departure failed')):
            with self.assertRaisesRegex(RuntimeError, 'map departure failed'):
                server.apply_admin_action(action)
        self.assertTrue(arrival.cancelled())
        self.assertTrue(self.s.closed)
        self.assertTrue(self.s._failed_location_entry)
        self.assertEqual(self.s.eden_sentence, eden.assigned(self.store, self.s.char_id))
        saved = self.store.character(self.s.char_id)
        self.assertEqual((saved['loc'], saved['on_map']), (eden.CENTER, 0))

    async def test_admin_release_cancels_a_legacy_map_leg_and_stale_arrival_is_inert(self):
        own = self.s.inv.create(inventory.STARTER_PISTOL)
        self.open_map()
        self.s.gx, self.s.gy = 5858.2, 1929.2
        # A leg saved by the preceding build must also be cancelled, even
        # though this build refuses to start new global-map movement.
        loop = asyncio.get_running_loop()
        self.s.leg = (loop.time(), self.s.gx, self.s.gy, .1, .1)
        self.s.arrival = loop.call_later(600, self.s.arrive, 5858.7, 1929.7)
        arrival = self.s.arrival
        self.assertIsNotNone(arrival)
        callback, args = arrival._callback, arrival._args
        action = dict(kind='eden_release', char_id=self.s.char_id,
                      account_id=self.s.active['account_id'], admin='test',
                      args_json=json.dumps({'reason': 'Map release regression'}))
        with patch.object(server, 'session_for', return_value=self.s):
            server.apply_admin_action(action)
        self.assertTrue(arrival.cancelled())
        self.assertIsNone(self.s.arrival)
        self.assertIsNone(self.s.leg)
        self.assertIsNone(self.s.eden_sentence)
        self.assertFalse(self.s.on_map)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy), (41, 5970, 1730))
        self.map.leave.assert_called_with(self.s)
        callback(*args)
        self.assertEqual((self.s.loc.id, self.s.gx, self.s.gy), (41, 5970, 1730))
        self.assertEqual(self.store.item(own['uniq']), own)


if __name__ == '__main__':
    run_cases(EdenMapTests)
