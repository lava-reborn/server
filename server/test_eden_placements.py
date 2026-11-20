"""Reachable shared Eden groves, clear routes and existing map artwork."""
from collections import Counter, deque
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))

import eden
import eden_map
import events
import progression
import rooms
import travel
import world
from testkit import run_cases
from test_eden_region import EXPECTED_CELLS


EXTRA_FROM = {loc_id: world.overlay_index()[loc_id]['from']
              for loc_id in eden.LOCATIONS if loc_id not in (264, 265, 266, 267)}
SORTERS = {1383: 1786, 1385: 1787, 1384: 1788}
LOCATIONS = frozenset(eden.LOCATIONS)
WORK = LOCATIONS - {eden.CENTER}


def distances(adjacent, seeds, blocked=frozenset()):
    found = {cell: 0 for cell in seeds if cell in adjacent and cell not in blocked}
    pending = deque(found)
    while pending:
        cell = pending.popleft()
        for neighbour in adjacent[cell]:
            if neighbour not in found and neighbour not in blocked:
                found[neighbour] = found[cell] + 1
                pending.append(neighbour)
    return found


class EdenPlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = rooms.Rooms(world.mob_types())
        cls.geometry = {}

    def layout(self, loc_id):
        loc, room = world.location(loc_id), self.table.get(loc_id)
        palms = sorted(npc.cell for npc in room.npcs.values() if npc.type_id in eden.PALMS)
        staff = {npc.cell for npc in room.npcs.values() if npc.type_id not in eden.PALMS}
        key = (loc.width, loc.height, frozenset(loc.obstacles),
               frozenset(loc.entries), tuple(palms), frozenset(staff), loc.entry_cell())
        if key not in self.geometry:
            free = set(range(loc.width * loc.height)) - loc.obstacles - staff
            adjacent = {cell: [n for n in progression.hex_neighbours(
                cell, loc.width, loc.height) if n in free] for cell in free}
            reachable = set(distances(adjacent, [loc.entry_cell()]))
            self.geometry[key] = adjacent, reachable
        adjacent, reachable = self.geometry[key]
        return loc, palms, staff, adjacent, reachable

    def test_each_work_map_has_exactly_twelve_palms_and_town_has_none(self):
        actual = set()
        for loc_id in sorted(LOCATIONS):
            with self.subTest(location=loc_id):
                loc, palms, _staff, _adjacent, _reachable = self.layout(loc_id)
                self.assertEqual(len(palms), len(set(palms)))
                self.assertEqual(loc.pvp, 0)
                self.assertEqual(loc.war, int(loc_id != eden.CENTER))
                if loc_id == eden.CENTER:
                    self.assertEqual(palms, [])
                else:
                    self.assertEqual(len(palms), 12)
                    actual.add(loc_id)
        self.assertEqual(actual, WORK)
        self.assertEqual(len(WORK), len(EXPECTED_CELLS) - 1)
        subset = {loc_id: world.placements()[loc_id] for loc_id in LOCATIONS
                  if loc_id in world.placements()}
        self.assertEqual(rooms.placement_problems(world.mob_types(), subset), [])

    def test_palms_are_reachable_and_never_sever_staff_or_edge_routes(self):
        for loc_id in sorted(WORK):
            with self.subTest(location=loc_id):
                loc, palms, staff, adjacent, reachable = self.layout(loc_id)
                self.assertEqual(set(distances(adjacent, [loc.entry_cell()], set(palms))),
                                 reachable - set(palms))
                protected = set(loc.entries)
                for route_cells, _record in travel.quest_ways(loc):
                    protected.update(route_cells)
                protected_distance = distances(adjacent, protected)
                staff_distance = distances(adjacent, {
                    n for cell in staff for n in progression.hex_neighbours(
                        cell, loc.width, loc.height) if n in adjacent})
                exits = travel.exit_sides(loc)
                self.assertTrue(exits)
                for cell in palms:
                    self.assertIn(cell, reachable)
                    self.assertNotIn(cell, exits)
                    self.assertGreaterEqual(protected_distance[cell], 8)
                    if staff_distance:
                        self.assertGreaterEqual(staff_distance[cell], 8)
                    ring = {cell} | set(adjacent[cell])
                    ring.update(n for c in tuple(ring) for n in adjacent[c])
                    # All nineteen cells within two hex steps must be free:
                    # a palm cannot stand against a wall or occupy a choke.
                    self.assertEqual(len(ring), 19, (loc_id, cell))

    def test_groves_cover_whole_work_maps_instead_of_clustering_at_sorters(self):
        metrics = {}
        for loc_id in sorted(WORK):
            with self.subTest(location=loc_id):
                loc, palms, staff, adjacent, reachable = self.layout(loc_id)
                key = (loc.width, loc.height, frozenset(loc.obstacles),
                       frozenset(loc.entries), tuple(palms), frozenset(staff))
                if key not in metrics:
                    measured = [distances(adjacent, [cell]) for cell in palms]
                    pair = min(measured[i][cell] for j, cell in enumerate(palms) for i in range(j))
                    coverage = max(min(d[cell] for d in measured) for cell in reachable)
                    territories = Counter(min(range(len(palms)), key=lambda i: measured[i][cell])
                                          for cell in reachable)
                    metrics[key] = (pair, coverage, len(territories), min(territories.values()),
                                    max(territories.values()), len(reachable))
                # Each map's geometry/entries/palms/staff must match this full
                # key before sharing path metrics; every ID is still checked.
                pair, coverage, count, least, most, reached = metrics[key]
                self.assertEqual(reached, len(reachable))
                self.assertGreaterEqual(pair, 20)
                # Full recovered entry zones need an eight-hex safety margin.
                # Reviewed layouts preserve that margin and a harvest site
                # within26hexes; each serves a useful, bounded map area.
                self.assertLessEqual(coverage, 26)
                self.assertEqual(count, len(palms))
                self.assertGreaterEqual(least, len(reachable) // 25)
                self.assertLessEqual(most, len(reachable) * 3 // 20)

    def test_original_work_maps_preserve_art_and_all_maps_allow_global_map(self):
        index = world.overlay_index()
        for loc_id in (264, 265, 266, 267):
            with self.subTest(location=loc_id):
                root = ET.parse(world.path_for(loc_id)).getroot()
                original = ET.parse(os.path.join(world.RES, 'locations', 'static',
                                                str(loc_id) + '.xml')).getroot()
                self.assertEqual(index[loc_id]['from'], loc_id)
                self.assertIn('DESIGNED', index[loc_id]['why'])
                for key in ('bgExt', 'bg', 'height', 'width', 'dir', 'library'):
                    self.assertEqual(root.attrib[key], original.attrib[key])
                self.assertEqual(root.attrib['fn'], original.attrib['fn'])
                mutable = {'outzones', 'inzones', 'zones', 'mobs'}
                self.assertEqual([(n.tag, n.attrib, n.text) for n in root if n.tag not in mutable],
                                 [(n.tag, n.attrib, n.text) for n in original if n.tag not in mutable])
                self.assertTrue((root.findtext('outzones') or '').strip())
                if loc_id != eden.CENTER:
                    self.assertEqual(world.location(loc_id).spawns, [])
                self.assertFalse(travel.walk_ins(world.location(loc_id)))
                self.assertFalse(travel.no_map(loc_id))
        keep = [(types, locations) for types, locations in events.table().keep_in
                if eden.CLEAVER in types]
        self.assertEqual(len(keep), 1)
        self.assertEqual(set(keep[0][0]), set(eden.LOCAL_ITEMS))
        self.assertEqual(set(keep[0][1]), set(LOCATIONS))

    def test_added_work_maps_reuse_original_art_and_sorters_are_only_beside_the_town(self):
        index = world.overlay_index()
        for loc_id, source in EXTRA_FROM.items():
            with self.subTest(location=loc_id):
                root = ET.parse(world.path_for(loc_id)).getroot()
                original = ET.parse(world.path_for(source)).getroot()
                self.assertEqual(index[loc_id]['from'], source)
                self.assertIn('DESIGNED', index[loc_id]['why'])
                self.assertNotEqual(root.attrib['fn'], original.attrib['fn'])
                for key in ('bgExt', 'bg', 'height', 'width', 'dir', 'library'):
                    self.assertEqual(root.attrib[key], original.attrib[key])
                mutable = {'mobs', 'zones', 'outzones'}
                self.assertEqual([(n.tag, n.attrib, n.text) for n in root if n.tag not in mutable],
                                 [(n.tag, n.attrib, n.text) for n in original if n.tag not in mutable])
                self.assertEqual(world.location(loc_id).spawns, [])
                expected = {1790} | ({SORTERS[loc_id]} if loc_id in SORTERS else set())
                self.assertEqual({npc.type_id for npc in self.table.get(loc_id).npcs.values()}, expected)
                self.assertFalse(travel.no_map(loc_id))
        self.assertEqual({loc_id: eden.target_cell(loc_id) for loc_id in SORTERS},
                         {1383: (5857, 1929), 1385: (5858, 1930), 1384: (5859, 1929)})
        for loc_id in WORK - set(SORTERS):
            self.assertEqual({npc.type_id for npc in self.table.get(loc_id).npcs.values()}, {1790})

    def test_all_internal_sides_are_reachable_reciprocal_and_never_point_outside(self):
        self.assertEqual(set(eden.LOCATIONS), set(LOCATIONS))
        self.assertEqual(set(eden_map.CELL_TO_LOC), EXPECTED_CELLS)
        directions = {'W': (-1, 0), 'N': (0, -1), 'E': (1, 0), 'S': (0, 1)}
        opposite = {'W': 'E', 'N': 'S', 'E': 'W', 'S': 'N'}
        graph, edge_count = {}, 0
        for loc_id in sorted(LOCATIONS):
            with self.subTest(location=loc_id):
                loc, palms, staff, adjacent, _reachable = self.layout(loc_id)
                gx, gy = eden.target_cell(loc_id)
                expected = {side: eden_map.CELL_TO_LOC[(gx + delta[0], gy + delta[1])]
                            for side, delta in directions.items()
                            if (gx + delta[0], gy + delta[1]) in eden_map.CELL_TO_LOC}
                exits = travel.exit_sides(loc)
                self.assertEqual(set(exits.values()), set(expected))
                reachable = set(distances(adjacent, [loc.entry_cell()], set(palms)))
                self.assertTrue(set(exits) <= reachable)
                raw = world._read(world.path_for(loc_id))
                self.assertEqual(set(world._chunks(raw, 'zones', 4)),
                                 {r[:4] for r in world._chunks(raw, 'outzones', 5)})
                graph[loc_id] = set(expected.values())
                for side, dest_id in expected.items():
                    edge_count += 1
                    source_cell = next(c for c, s in exits.items() if s == side)
                    rec = travel.side_way(loc_id, side)
                    self.assertEqual(rec['target_loc_id'], dest_id)
                    self.assertEqual(travel.side_way(dest_id, opposite[side])['target_loc_id'], loc_id)
                    target = travel.plan_exit(loc, source_cell, gx, gy)
                    self.assertEqual(target.loc_id, dest_id)
                    self.assertEqual((target.gx, target.gy), eden.target_cell(dest_id))
                    dest, dest_palms, _staff, dest_adjacent, _seen = self.layout(dest_id)
                    self.assertIn(target.pos, distances(dest_adjacent, [dest.entry_cell()], set(dest_palms)))
                    # Arrival is just inside the opposite edge, deliberately
                    # off the exit hex so opening the new room cannot bounce.
                    self.assertLessEqual(travel._edge_distance(dest, target.pos, opposite[side]), 4)
        self.assertEqual(edge_count, sum((x + dx, y + dy) in EXPECTED_CELLS
                                        for x, y in EXPECTED_CELLS
                                        for dx, dy in directions.values()))
        reached, pending = {eden.CENTER}, [eden.CENTER]
        while pending:
            for neighbour in graph[pending.pop()] - reached:
                reached.add(neighbour)
                pending.append(neighbour)
        self.assertEqual(reached, set(LOCATIONS))


if __name__ == '__main__':
    run_cases(EdenPlacementTests)
