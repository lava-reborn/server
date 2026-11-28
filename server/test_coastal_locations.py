"""Native coast profiles remain intact while global placement awaits review."""
from collections import Counter, deque
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

import location_entry
import map_labels
import xml.etree.ElementTree as ET
import coasts
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
            'Абу-Хамед': ({38, 39, 54}, 2420, 17)}
STEPS = {'W': (-1, 0), 'N': (0, -1), 'E': (1, 0), 'S': (0, 1)}


class CoastalLocations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = build_coastal_locations.document()

    def test_native_profiles_remain_but_withdrawn_coordinates_are_not_bound(self):
        found = {city: {int(i) for i, row in self.doc['locations'].items() if row['city'] == city}
                 for city in self.doc['cities']}
        self.assertEqual(found, {city: values[0] for city, values in EXPECTED.items()})
        self.assertIs(self.doc['global_bindings_enabled'],False)
        self.assertEqual(build_coastal_locations.placement_rows(self.doc),{})
        for key,row in self.doc['locations'].items():
            loc_id=int(key)
            with self.subTest(location=key):
                self.assertIsNone(world.cell_of(loc_id))
                self.assertNotEqual(world.location_at(*row['cell']),loc_id)
                self.assertNotIn(loc_id,world.settlements().values())
                self.assertIsNone(world.overlay_path(loc_id))
                self.assertEqual(world.location(loc_id).title,'Побережье')
        self.assertEqual(world.location_at(5972,1738),61)

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
                self.assertEqual(coasts.profiles()[loc.id, mob], level)
                self.assertEqual(mobs.stats(mob).role, 'animal')
                self.assertEqual(world.mob_types()[mob][2], 'crocodile')
                self.assertTrue(names.known(mob))
                self.assertEqual(names.ALL[mob], "Крокодил<br>Дикое животное")
                self.assertEqual(mobs.stats(mob).weapon_type_id, None)
                total += len(room.npcs)
        self.assertEqual(total, 109)

    def test_placement_requires_explicit_approval_and_does_not_activate_by_missing_flag(self):
        draft=dict(self.doc)
        draft.pop('global_bindings_enabled')
        self.assertEqual(build_coastal_locations.placement_rows(draft),{})
        for value in (False,None,1,'true'):
            draft['global_bindings_enabled']=value
            self.assertEqual(build_coastal_locations.placement_rows(draft),{})
        draft['global_bindings_enabled']=True
        self.assertEqual(build_coastal_locations.placement_rows(draft),self.doc['locations'])

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

    def test_preliminary_coast_labels_are_absent_while_quest_oasis_is_retained(self):
        labels = json.loads((ROOT/'data/map_labels.json').read_text(encoding='utf-8'))['labels']
        self.assertFalse([row for row in labels if 'coastal_location' in row])
        self.assertTrue(any(row.get('hide') and (row['x'],row['y'])==(5972,1738) for row in labels))
        self.assertEqual(world.cell_of(61),(5972,1738))

    def test_population_rebuild_preserves_profiles_without_global_bindings(self):
        meta = {int(k): v for k, v in json.loads((ROOT/'data/mob_types.json').read_text(encoding='utf-8'))['types'].items()}
        rebuilt = build_spawn_substitutes.camp_fill(world.mob_types(), meta)['fill']
        current = json.loads((ROOT/'data/camp_fill.json').read_text(encoding='utf-8'))['fill']
        fixed = json.loads((ROOT/'data/settlements_verified.json').read_text(encoding='utf-8'))['cells']
        for key, row in self.doc['locations'].items():
            self.assertEqual(rebuilt[key], current[key])
            self.assertNotIn(int(key),fixed.values())


    def test_rebuild_does_not_resurrect_withdrawn_global_points(self):
        files=('coastal_locations.json','mob_types.json','settlements.json',
               'settlements_verified.json','camp_fill.json','map_labels.json')
        with tempfile.TemporaryDirectory(prefix='coast-rebuild-') as directory:
            target=Path(directory)
            for name in files:
                (target/name).write_bytes((ROOT/'data'/name).read_bytes())
            before={name:json.loads((target/name).read_text(encoding='utf-8')) for name in files}
            with patch.object(build_coastal_locations,'HERE',target):
                build_coastal_locations.main()
                build_coastal_locations.main()
            after={name:json.loads((target/name).read_text(encoding='utf-8')) for name in files}
            self.assertEqual(after,before)


    def test_withdrawal_removes_old_embedded_labels_without_hiding_other_names(self):
        labels=json.loads((ROOT/'data/map_labels.json').read_text(encoding='utf-8'))['labels']
        withdrawals=[r for r in labels if 'withdrawn_coastal_location' in r]
        self.assertEqual({r['withdrawn_coastal_location'] for r in withdrawals},{int(k) for k in self.doc['locations']})
        tree=ET.Element('data')
        for row in withdrawals:
            ET.SubElement(tree,'location',x=str(row['x']),y=str(row['y']),text=row['was'])
        ET.SubElement(tree,'location',x='5972',y='1738',text='Оазис')
        ET.SubElement(tree,'location',x='5987',y='1699',text='Северный Оазис')
        raw=ET.tostring(tree,encoding='utf-8')
        rules=[(r['x'],r['y'],r['was'],None) for r in withdrawals]+[(5972,1738,'Оазис',None)]
        edited,count=map_labels.apply(raw,rules)
        self.assertEqual(count,15)
        remaining=ET.fromstring(edited).findall('location')
        self.assertEqual([(r.get('x'),r.get('y'),r.get('text')) for r in remaining],
                         [('5987','1699','Северный Оазис')])
        self.assertEqual(map_labels.apply(edited,rules),(edited,0))


if __name__ == '__main__':
    run_cases(CoastalLocations)
