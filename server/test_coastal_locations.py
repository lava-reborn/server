"""Recovered coasts: regional population, dry routes and safe player arrivals."""
from collections import Counter, deque
import json
from pathlib import Path
import sys
import unittest

import location_entry
import mobs
import names
import progression
import rooms
import travel
import world
from testkit import run_cases

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'data'))
import build_coastal_locations
import build_spawn_substitutes

EXPECTED = {'Вади-Хальфа': ({17, 18, 19, 22}, 2418, 4),
            'Абри': ({21, 55, 56, 57}, 2419, 11),
            'Донгола': ({20, 23, 24}, 130, 12),
            'Абу-Хамед': ({38, 39, 54}, 2420, 20)}
STEPS = {'W': (-1, 0), 'N': (0, -1), 'E': (1, 0), 'S': (0, 1)}


class CoastalLocations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build_coastal_locations.document()

    def test_all_fourteen_original_maps_are_bound_once_to_their_regions(self):
        found = {city: {int(i) for i, row in self.doc['locations'].items() if row['city'] == city}
                 for city in self.doc['cities']}
        self.assertEqual(found, {city: values[0] for city, values in EXPECTED.items()})
        cells = [tuple(row['cell']) for row in self.doc['locations'].values()]
        self.assertEqual(len(set(cells)), 14)
        for key, row in self.doc['locations'].items():
            with self.subTest(location=key):
                loc_id = int(key)
                self.assertEqual(world.location_at(*row['cell']), loc_id)
                self.assertEqual(world.cell_of(loc_id), tuple(row['cell']))
                self.assertIsNone(world.overlay_path(loc_id))
                self.assertEqual(world.location(loc_id).title, 'Побережье')
                self.assertTrue(world.passable(*row['cell']))
                self.assertEqual([c for c, i in world.settlements().items() if i == loc_id],
                                 [tuple(row['cell'])])

    def test_every_native_empty_nest_gets_one_drawable_crocodile(self):
        total = 0
        for key, row in self.doc['locations'].items():
            with self.subTest(location=key):
                loc = world.location(int(key))
                mob, level = EXPECTED[row['city']][1:]
                room = rooms.Room(loc, rooms.IdAllocator(), world.mob_types())
                self.assertTrue(loc.war)
                self.assertTrue(all(t == 0 for _, t in loc.spawns))
                self.assertEqual(Counter(n.type_id for n in room.npcs.values()),
                                 {mob: len(loc.spawns)})
                self.assertEqual(mobs.stats(mob).level, level)
                self.assertEqual(mobs.stats(mob).role, 'animal')
                self.assertEqual(world.mob_types()[mob][2], 'crocodile')
                self.assertTrue(names.known(mob))
                self.assertEqual(names.ALL[mob], "Крокодил<br>Дикое животное")
                self.assertEqual(mobs.stats(mob).weapon_type_id, None)
                total += len(room.npcs)
        self.assertEqual(total, 109)

    def test_exit_directions_match_dry_neighbours_and_cannot_cross_the_river(self):
        for key, row in self.doc['locations'].items():
            loc = world.location(int(key))
            x, y = row['cell']
            opened = {side for side, (dx, dy) in STEPS.items() if world.passable(x+dx, y+dy)}
            native = set(travel.exit_sides(loc).values()) & set(STEPS)
            self.assertEqual(native, opened, key)
            self.assertTrue(any(world.water(x+dx, y+dy) for dx in (-1, 0, 1)
                                for dy in (-1, 0, 1) if dx or dy), key)
            # A natural-respawn coast is a fixed location, never an ambush room.
            self.assertFalse(world.is_wilderness(loc.id))
            self.assertEqual(world.placed_in(world.pack(x, y)), [])

    def test_each_coast_is_reachable_from_its_town_on_the_existing_land(self):
        for city, city_row in self.doc['cities'].items():
            targets = {tuple(row['cell']) for row in self.doc['locations'].values() if row['city'] == city}
            start = tuple(city_row['origin'])
            reached = {start}
            pending = deque([(start, 0)])
            while pending and not targets <= reached:
                (x, y), depth = pending.popleft()
                if depth >= 100:
                    continue
                for dx, dy in STEPS.values():
                    cell = x+dx, y+dy
                    if cell not in reached and world.passable(*cell):
                        reached.add(cell)
                        pending.append((cell, depth+1))
            self.assertFalse(targets - reached, (city, targets - reached))

    def test_arrivals_avoid_crocodiles_and_can_reach_every_nest_and_an_exit(self):
        for key, row in self.doc['locations'].items():
            loc = world.location(int(key))
            occupied = {cell for cell, _ in loc.spawns}
            exits = {c for c in travel.exit_sides(loc) if 0 <= c < loc.width*loc.height}
            for fx, fy in ((.01,.01),(.5,.5),(.99,.99)):
                start = location_entry.choose(loc, row['cell'][0]+fx, row['cell'][1]+fy,
                                              occupied, near_exits=True)
                self.assertNotIn(start, occupied | loc.obstacles | exits)
                self.assertTrue(set(progression.hex_neighbours(start,loc.width,loc.height)) & exits)
            # Check the original geometry once per map, independently of occupancy.
            reached = {start}
            pending = deque([start])
            while pending:
                current = pending.popleft()
                for cell in progression.hex_neighbours(current, loc.width, loc.height):
                    if cell not in reached and cell not in loc.obstacles:
                        reached.add(cell)
                        pending.append(cell)
            self.assertFalse(occupied - reached, key)

    def test_spawn_and_settlement_rebuilds_preserve_the_approved_rows(self):
        meta = {int(k): v for k, v in json.loads((ROOT/'data/mob_types.json').read_text(encoding='utf-8'))['types'].items()}
        rebuilt = build_spawn_substitutes.camp_fill(world.mob_types(), meta)['fill']
        current = json.loads((ROOT/'data/camp_fill.json').read_text(encoding='utf-8'))['fill']
        fixed = json.loads((ROOT/'data/settlements_verified.json').read_text(encoding='utf-8'))['cells']
        for key, row in self.doc['locations'].items():
            self.assertEqual(rebuilt[key], current[key])
            self.assertEqual(fixed['%d,%d' % tuple(row['cell'])], int(key))


if __name__ == '__main__':
    run_cases(CoastalLocations)
