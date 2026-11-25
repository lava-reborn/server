"""Global-map entry follows click position without spawning into walls or traps."""
from collections import deque
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import location_entry as E
import progression
import travel
import world
from protocol import decode, encode
from testkit import run_cases


class Scene:
    def __init__(self, entries=(), exits=None, obstacles=(), *, war=0, war_entries=(), triggers=()):
        self.id, self.width, self.height, self.war = -100, 21, 21, war
        self.entries, self.obstacles = list(entries), set(obstacles)
        self.exits = dict(exits if exits is not None else {
            10 * 21: travel.W, 10: travel.N, 10 * 21 + 20: travel.E, 20 * 21 + 10: travel.S})
        self.war_entries, self.triggers = list(war_entries), frozenset(triggers)


def cell(x, y):
    return y * 21 + x


class GlobalEntryTests(unittest.TestCase):
    def setUp(self):
        native_exits, native_war, native_walk = travel.exit_sides, travel.war_entries, travel.walk_ins
        for name, callback in (
            ('exit_sides', lambda loc: loc.exits if isinstance(loc, Scene) else native_exits(loc)),
            ('war_entries', lambda loc: loc.war_entries if isinstance(loc, Scene) else native_war(loc)),
            ('walk_ins', lambda loc: [(loc.triggers, {})] if isinstance(loc, Scene) else native_walk(loc)),
        ):
            active = patch.object(travel, name, side_effect=callback)
            active.start()
            self.addCleanup(active.stop)

    def assert_escape(self, loc, start, occupied=frozenset()):
        blocked = loc.obstacles | set(occupied)
        blocked |= {c for cells, _row in travel.walk_ins(loc) for c in cells}
        exits = {c for c, side in travel.exit_sides(loc).items()
                 if side in travel.SIDES and c not in blocked}
        self.assertNotIn(start, blocked)
        self.assertNotIn(start, travel.exit_sides(loc))
        self.assertTrue(0 <= start < loc.width * loc.height)
        found, pending = {start}, deque([start])
        while pending:
            current = pending.popleft()
            if current in exits:
                self.assertGreater(len(found), 1)
                return
            for neighbour in progression.hex_neighbours(current, loc.width, loc.height):
                if neighbour not in blocked and neighbour not in found:
                    found.add(neighbour)
                    pending.append(neighbour)
        self.fail('Chosen entry has no free path to a real exit')

    def real_location(self, loc_id):
        path = world.path_for(loc_id)
        if path is None or not Path(path).is_file():
            self.skipTest('Original location resources are unavailable')
        return world.location(loc_id)

    def test_nine_corners_edges_and_center_follow_fractional_floor_position(self):
        entries = [cell(x, y) for y in (2, 10, 18) for x in (2, 10, 18)]
        loc = Scene(entries)
        for y in (2, 10, 18):
            for x in (2, 10, 18):
                with self.subTest(x=x, y=y):
                    chosen = E.choose(loc, 6000 + x / 20, 1900 + y / 20)
                    self.assertEqual(chosen, cell(x, y))
                    self.assert_escape(loc, chosen)

    def test_local_projection_maps_center_edges_and_corners_without_changing_map_square(self):
        loc = Scene()
        for x, fx in ((0, 0), (10, .5), (20, .99)):
            for y, fy in ((0, 0), (10, .5), (20, .99)):
                with self.subTest(x=x, y=y):
                    point = E.map_position(loc, cell(x, y), 6000.8, 1900.2)
                    self.assertEqual(point, (6000 + fx, 1900 + fy))
                    self.assertEqual(tuple(map(math.floor, point)), (6000, 1900))
                    _command, wire = decode(encode('gmap', x=point[0], y=point[1]))
                    self.assertEqual((wire['x'], wire['y']), point)

    def test_projection_and_safe_entry_choose_the_same_declared_position(self):
        entries = [cell(x, y) for y in (2, 10, 18) for x in (2, 10, 18)]
        loc = Scene(entries)
        for original in entries:
            point = E.map_position(loc, original, 6000, 1900)
            self.assertEqual(E.choose(loc, *point), original)
            self.assert_escape(loc, original)

    def test_projection_handles_single_hex_and_rejects_invalid_local_or_global_inputs(self):
        loc = Scene()
        for bad_cell in (-1, loc.width * loc.height, None):
            with self.assertRaises(E.NoSafeEntry):
                E.map_position(loc, bad_cell, 6000, 1900)
        for bad_point in ((None, 1900), (-1, 1900), (6000, float('inf')),
                          (float('nan'), 1900)):
            with self.assertRaises(E.NoSafeEntry):
                E.map_position(loc, 0, *bad_point)
        loc.width = loc.height = 1
        self.assertEqual(E.map_position(loc, 0, 6000, 1900), (6000.5, 1900.5))

    def test_real_black_market_declared_center_remains_allowed_and_escapable(self):
        loc = self.real_location(103)
        chosen = E.choose(loc, 5879.5, 2012.5)
        self.assertIn(chosen, loc.entries)
        self.assertTrue(all(travel._edge_distance(loc, chosen, side) > travel.EDGE_BAND
                            for side in travel.SIDES))
        self.assert_escape(loc, chosen)

    def test_real_port_never_uses_edges_without_outzones_but_keeps_open_center(self):
        loc = self.real_location(41)
        self.assertEqual(set(travel.exit_sides(loc).values()), {travel.E})
        for fx in (.05, .5, .95):
            for fy in (.05, .5, .95):
                with self.subTest(fx=fx, fy=fy):
                    chosen = E.choose(loc, 5965 + fx, 1728 + fy)
                    for side in (travel.W, travel.N, travel.S):
                        self.assertGreater(travel._edge_distance(loc, chosen, side), travel.EDGE_BAND)
                    self.assert_escape(loc, chosen)

    def test_real_port_west_and_southwest_do_not_bypass_closed_side_beyond_four_hexes(self):
        loc = self.real_location(41)
        geometry = E._geometry(loc)
        rejected = {84 * loc.width + 5, 92 * loc.width + 5}
        self.assertTrue(rejected.issubset(loc.entries))
        self.assertTrue(rejected.isdisjoint(geometry.candidates))
        for fy in (.5, .95):
            chosen = E.choose(loc, 5965.05, 1728 + fy)
            self.assertNotIn(chosen, rejected)
            if not E._central(loc, chosen):
                distances = {side: travel._edge_distance(loc, chosen, side) for side in travel.SIDES}
                nearest = min(distances.values())
                self.assertEqual({side for side, depth in distances.items() if depth == nearest}, {travel.E})
            else:
                self.assertIn(chosen, loc.entries)
            self.assert_escape(loc, chosen)

    def test_outside_center_a_tied_closed_corner_is_rejected(self):
        corner = cell(19, 1)
        loc = Scene([corner], exits={cell(20, 10): travel.E})
        self.assertNotIn(corner, E._geometry(loc).candidates)
        chosen = E.choose(loc, 6000.95, 1900.05)
        self.assertNotEqual(chosen, corner)
        self.assert_escape(loc, chosen)

    def test_central_exception_requires_a_declared_entry_not_an_inward_fallback(self):
        # These deliberately interior outzones exercise the fallback policy:
        # their immediate neighbours cannot invent a central spawn point.
        loc = Scene([], exits={cell(8, 10): travel.W})
        with self.assertRaises(E.NoSafeEntry):
            E.choose(loc, 6000.5, 1900.5)
        declared = Scene([cell(9, 10)], exits={cell(8, 10): travel.W})
        self.assertEqual(E.choose(declared, 6000.45, 1900.5), cell(9, 10))
        self.assert_escape(declared, cell(9, 10))

    def test_an_isolated_declared_cell_inside_a_closed_chamber_is_never_used(self):
        center = cell(10, 10)
        walls = progression.hex_neighbours(center, 21, 21)
        loc = Scene([center, cell(10, 3)], obstacles=walls)
        chosen = E.choose(loc, 6000.5, 1900.5)
        self.assertNotEqual(chosen, center)
        self.assert_escape(loc, chosen)

    def test_live_npc_ring_invalidates_cached_center_and_rechecks_escape_route(self):
        center = cell(10, 10)
        loc = Scene([center, cell(13, 13)], exits={cell(20, 10): travel.E})
        self.assertEqual(E.choose(loc, 6000.5, 1900.5), center)
        occupied = frozenset(progression.hex_neighbours(center, 21, 21))
        chosen = E.choose(loc, 6000.5, 1900.5, occupied)
        self.assertNotEqual(chosen, center)
        self.assert_escape(loc, chosen, occupied)

    def test_occupied_exit_or_fully_occupied_candidates_refuse_without_unsafe_fallback(self):
        loc = Scene([cell(10, 10)])
        for occupied in (frozenset(loc.exits), frozenset(range(21 * 21))):
            with self.subTest(occupied_count=len(occupied)):
                with self.assertRaises(E.NoSafeEntry):
                    E.choose(loc, 6000.5, 1900.5, occupied)

    def test_invalid_declared_points_are_ignored_and_only_real_inward_hex_is_fallback(self):
        loc = Scene([-1, 21 * 21, 21 * 21 + 7], exits={cell(20, 10): travel.E, 99999: travel.W})
        chosen = E.choose(loc, 6000.5, 1900.5)
        self.assertEqual(chosen, cell(19, 10))
        self.assertIn(chosen, progression.hex_neighbours(cell(20, 10), 21, 21))
        self.assert_escape(loc, chosen)
        with self.assertRaises(E.NoSafeEntry):
            E.choose(Scene([cell(10, 10)], exits={99999: travel.E}), 6000.5, 1900.5)

    def test_war_entries_are_used_only_for_war_locations(self):
        center = cell(10, 10)
        for war in (0, 1):
            loc = Scene([], war=war, war_entries=[center])
            chosen = E.choose(loc, 6000.5, 1900.5)
            self.assertEqual(chosen == center, bool(war))
            self.assert_escape(loc, chosen)

    def test_walk_in_cells_are_neither_spawn_points_nor_passages_through_a_trap(self):
        corridor = {cell(10, y) for y in range(11)}
        loc = Scene([cell(10, 10)], exits={cell(10, 0): travel.N},
                    obstacles=set(range(21 * 21)) - corridor, triggers={cell(10, 5)})
        chosen = E.choose(loc, 6000.5, 1900.5)
        self.assertLess(chosen // 21, 5)
        self.assertNotIn(chosen, loc.triggers)
        self.assert_escape(loc, chosen)

    def test_no_exit_or_door_only_scene_cannot_fall_back_to_cell_zero(self):
        for exits in ({}, {cell(10, 0): 'a'}):
            with self.subTest(exits=exits):
                with self.assertRaises(E.NoSafeEntry):
                    E.choose(Scene([cell(10, 10)], exits=exits), 6000.5, 1900.5)

    def test_invalid_coordinates_are_refused_before_any_geometry_work(self):
        for bad in (-1, float('nan'), float('inf'), -float('inf'), None, 'invalid'):
            for point in ((bad, 1900.5), (6000.5, bad)):
                with self.subTest(point=point):
                    with patch.object(E, '_geometry', side_effect=AssertionError('Invalid coordinates must stop first')):
                        with self.assertRaises(E.NoSafeEntry):
                            E.choose(Scene(), *point)

    def test_static_geometry_is_cached_without_repeating_pathfinding_for_empty_occupancy(self):
        loc = Scene([cell(10, 10)])
        expected = E.choose(loc, 6000.5, 1900.5)
        geometry = loc._global_entry_geometry
        with patch.object(E, '_reachable', side_effect=AssertionError('Static geometry must be reused')):
            self.assertEqual(E.choose(loc, 6000.5, 1900.5), expected)
        self.assertIs(loc._global_entry_geometry, geometry)


if __name__ == '__main__':
    run_cases(GlobalEntryTests)
