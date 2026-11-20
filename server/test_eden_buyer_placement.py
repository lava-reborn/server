"""The Eden buyer reuses auctioneer art at a reachable, unoccupied town cell."""
from collections import deque
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(__file__))

import names
import npcs
import eden_shop
import progression
import rooms
import travel
import world
from testkit import run_cases


BUYER, APPEARANCE, TOWN = 60020, 883, 267


class EdenBuyerPlacementTests(unittest.TestCase):
    def test_separate_buyer_reuses_original_auctioneer_without_modifying_it(self):
        original = next(row for row in ET.parse(os.path.join(
            world.RES, 'database', 'mobs.xml')).getroot().iter('mob')
                        if row.get('type_id') == str(APPEARANCE))
        types = world.mob_types()
        self.assertEqual(types[APPEARANCE], (int(original.get('root_type_id')),
                                            original.get('name'), original.get('resource')))
        self.assertEqual(types[APPEARANCE][0], world.AUCTIONER)
        self.assertEqual(types[BUYER][0], world.TRADER)
        self.assertEqual(types[BUYER][2], types[APPEARANCE][2])
        self.assertNotEqual(types[BUYER][1], types[APPEARANCE][1])
        self.assertEqual(names.text(BUYER), 'Скупщик')
        self.assertTrue(names.known(BUYER))
        self.assertEqual(npcs.stock(BUYER), [])
        self.assertFalse(npcs.home(BUYER))
        # Server/CI resources contain catalogues, not the client's mob art.
        # Its published native appearance ID must resolve to the original
        # auctioneer above; the player's client owns that existing animation.
        self.assertEqual(eden_shop.ART_TYPE, APPEARANCE)

    def test_buyer_is_only_in_town_beside_house_refuse_and_has_six_clear_approaches(self):
        placements = [(loc, row) for loc, rows in world.placements().items()
                      for row in rows if row['type'] == BUYER]
        self.assertEqual(len(placements), 1)
        loc_id, row = placements[0]
        self.assertEqual((loc_id, row['cell']), (TOWN, [20, 110]))
        loc = world.location(TOWN)
        cell = row['cell'][1] * loc.width + row['cell'][0]
        staff = {pos for pos, _type in loc.spawns}
        self.assertNotIn(cell, staff | loc.obstacles | set(loc.entries))
        self.assertNotIn(cell, travel.exit_sides(loc))
        neighbours = set(progression.hex_neighbours(cell, loc.width, loc.height))
        self.assertEqual(len(neighbours), 6)
        self.assertTrue(neighbours.isdisjoint(staff | loc.obstacles))
        reachable, pending = {loc.entry_cell()}, deque([loc.entry_cell()])
        while pending:
            at = pending.popleft()
            for neighbour in progression.hex_neighbours(at, loc.width, loc.height):
                if neighbour not in reachable and neighbour not in staff | loc.obstacles:
                    reachable.add(neighbour)
                    pending.append(neighbour)
        self.assertIn(cell, reachable)
        self.assertTrue(neighbours <= reachable)
        for route_cells, _record in travel.quest_ways(loc):
            self.assertNotIn(cell, route_cells)
            self.assertTrue(route_cells <= reachable)
        room = rooms.Rooms(world.mob_types()).get(TOWN)
        spawned = [npc for npc in room.npcs.values() if npc.type_id == BUYER]
        self.assertEqual(len(spawned), 1)
        self.assertEqual((spawned[0].cell, spawned[0].root), (cell, world.TRADER))
        self.assertEqual(rooms.placement_problems(world.mob_types(), {TOWN: [row]}), [])


if __name__ == '__main__':
    run_cases(EdenBuyerPlacementTests)
