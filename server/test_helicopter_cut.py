"""Helicopter transport pilots leave the live world, without removing scenery."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import names
import quests
import rooms
import world
from testkit import run_cases


PILOTS = frozenset(range(4670, 4689)) | {4786}
BEFORE = {41: {4670}, 187: {4672}, 295: {4674}, 296: {4674}, 445: {4676},
          58: {4678}, 126: {4680}, 287: {4682}, 320: {4686}}


class HelicopterCutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = world.mob_types()
        xml = ET.parse(Path(world.RES) / 'database/mobs.xml').getroot()
        cls.drawn_pilots = {int(row.attrib['type_id']) for row in xml
                            if row.attrib.get('resource') == '1f_Pilot_Vert'}

    def test_only_the_twenty_transport_types_are_newly_retired(self):
        self.assertEqual(len(PILOTS), 20)
        self.assertTrue(PILOTS <= self.drawn_pilots)
        retired = {t for t, why in world.retired_creatures().items()
                   if why.startswith('The owner, 2026-11-22: remove all helicopter pilots.')}
        self.assertEqual(retired, PILOTS)
        self.assertTrue(all(names.known(t) for t in PILOTS))

    def test_all_native_helicopter_pilots_are_absent(self):
        self.assertEqual(len(self.drawn_pilots), 41)
        retired = {int(lid) for lid in json.loads(
            (Path(__file__).resolve().parents[1] / 'data/retired.json').read_text(encoding='utf-8'))['places']}
        locations = {lid for lid in world.static_ids()
                     if lid not in retired and
                     (any(t in self.drawn_pilots for _cell, t in world.location(lid).spawns)
                      or any(row['type'] in self.drawn_pilots for row in world.placed_in(lid)))}
        for lid in locations:
            with self.subTest(lid=lid):
                room = rooms.Room(world.location(lid), rooms.IdAllocator(), self.types)
                self.assertFalse({npc.type_id for npc in room.npcs.values()} & self.drawn_pilots)

    def test_the_exact_old_active_transport_pilots_are_removed(self):
        kept = world.retired_creatures()
        try:
            world._RETIRED_CREATURES = {t: why for t, why in kept.items() if t not in PILOTS}
            for lid, pilots in BEFORE.items():
                with self.subTest(lid=lid):
                    room = rooms.Room(world.location(lid), rooms.IdAllocator(), self.types)
                    self.assertEqual({npc.type_id for npc in room.npcs.values()} & PILOTS, pilots)
        finally:
            world._RETIRED_CREATURES = kept
        for lid in BEFORE:
            with self.subTest(lid=lid):
                room = rooms.Room(world.location(lid), rooms.IdAllocator(), self.types)
                self.assertFalse({npc.type_id for npc in room.npcs.values()} & PILOTS)

    def test_no_live_quest_can_be_started_or_handed_to_a_removed_pilot(self):
        for pilot in PILOTS:
            with self.subTest(pilot=pilot):
                self.assertFalse(quests.given_by(pilot))
                self.assertFalse(quests.taken_by(pilot))
                root, name, _attrs = self.types[pilot]
                for war, lid in ((0, 41), (1, 41), (0, None), (1, None)):
                    self.assertFalse(world.belongs_here(pilot, name, root, war, lid))


if __name__ == '__main__':
    run_cases(HelicopterCutTests)
