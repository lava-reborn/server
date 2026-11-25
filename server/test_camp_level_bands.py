"""Camp interiors, side locations, patrols and encounters keep their bands."""
import json
from pathlib import Path
import unittest

import encounters
import mobs
import rooms
import world
from testkit import run_cases

ROOT = Path(__file__).resolve().parents[1]
# The advertised bands, plus the Nubian bandit camp's existing 2-4 roster.
BANDS = {34:(2,4),80:(0,2),81:(2,4),84:(4,6),85:(6,8),88:(8,10),
         92:(10,12),93:(12,14),98:(14,16),132:(16,18),168:(16,18),263:(19,20)}
SIDES = {80:82,81:83,84:86,85:87,88:89,92:90,93:91,98:99,132:133,263:274}
QUEST_PEOPLE = frozenset({1749,1750,1751,2170})


class CampBands(unittest.TestCase):
    def test_centres_sides_and_actual_patrol_npcs_stay_in_the_camp_band(self):
        manager = rooms.Rooms(world.mob_types())
        locations = {camp:camp for camp in BANDS}
        locations.update({side:camp for camp,side in SIDES.items()})
        table = json.loads((ROOT/'data/placements.json').read_text(encoding='utf-8'))['locations']
        for lid, records in table.items():
            for record in records:
                if record.get('patrol') in BANDS:
                    locations[int(lid)] = record['patrol']
        for lid,camp in locations.items():
            low,high = BANDS[camp]
            for npc in manager.get(lid).npcs.values():
                if npc.root != world.MOB or npc.type_id in QUEST_PEOPLE:
                    continue
                stats = mobs.stats(npc.type_id)
                if not stats.can_attack or stats.role not in ('mob','animal','turret'):
                    continue
                with self.subTest(location=lid, type=npc.type_id):
                    self.assertLessEqual(low, stats.level)
                    self.assertLessEqual(stats.level, high)

    def test_random_encounters_use_the_same_advertised_band(self):
        for band,_reach in encounters.bands():
            self.assertEqual((band.lo,band.hi),BANDS[band.camp])
            for tid in band.types:
                with self.subTest(camp=band.camp,type=tid):
                    self.assertEqual(mobs.stats(tid).role,'mob')
                    self.assertLessEqual(band.lo,mobs.stats(tid).level)
                    self.assertLessEqual(mobs.stats(tid).level,band.hi)


if __name__ == '__main__':
    run_cases(CampBands)
