"""Random loot falls only from gap -3; XP/PvP retain their own ladders."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import bosses
import combat
import effects
import items
import mob_equipment_loot
import mobs
import progression
from testkit import run_cases


class FixedRandom:
    def __init__(self, value=0):
        self.value = value

    def random(self):
        return self.value

    def choice(self, values):
        return values[0]

    def randint(self, low, high):
        return low


class MobLootFollowup(unittest.TestCase):
    def test_explicit_loot_boundaries_do_not_reuse_the_xp_ladder(self):
        ladder = {-10: 0, -5: 0, -4: .25, -3: .5, -2: 1, -1: 1,
                  0: 1, 1: 1, 2: 1.05, 3: 1.15, 4: 1.25, 10: 1.25}
        xp = {-5: 0, -4: 0, -3: .25, -2: .5, -1: .75, 0: .95,
              1: 1, 2: 1.05, 3: 1.15, 4: 1.25}
        for gap, expected in ladder.items():
            self.assertEqual(mobs.loot_level_factor(gap), expected)
        for gap, ratio in xp.items():
            self.assertAlmostEqual(progression.combat_mob_xp(10 + gap, 10),
                                   progression.mob_price(11) * ratio)

    def test_departed_senior_and_scanner_use_the_same_native_loot_factor(self):
        class Fighter:
            is_player = True
            def __init__(self, level):
                self.level, self.sess = level, NS()
        low, senior = Fighter(10), Fighter(14)
        target = NS(stats=NS(role='mob', level=10), xp_ledger={123: [100], low: [1]}, loot_level=14)
        with patch.object(effects, 'multiplier', return_value=3):
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), .75)
            target.loot_level = 13
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), 1.5)
            target.loot_level = 12
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), 3)
            target.loot_level = 15
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), 0)
        target.xp_ledger = {senior: [100], low: [1]}
        target.loot_level = 0
        self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), .25)

    def test_minus_four_corpse_keeps_native_ammo_and_scales_each_rare_category_once(self):
        stats = mobs.stats(291)
        categories = mob_equipment_loot.categories(stats, 84)
        self.assertTrue(all(types for _kind, types, _chance in categories))
        ammo = next(iter(mobs.standard_ammunition_types().values()))
        cumulative = 0
        with patch.object(mobs, 'carried', return_value=[(ammo, 7)]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            for kind, types, chance in categories:
                cumulative += chance
                factor = mobs.loot_level_factor(-4)
                drops = mobs.loot_for(stats, FixedRandom(cumulative * factor - 1e-8),
                                      loc_id=84, killer_level=stats.level + 4, multiplier=factor)
                self.assertIn((ammo, 7), drops)
                self.assertEqual([(t, n) for t, n in drops if mob_equipment_loot.kind_of(t)], [(types[0], 1)])
            self.assertEqual(mobs.loot_for(stats, FixedRandom(cumulative * factor),
                                          loc_id=84, killer_level=stats.level + 4, multiplier=factor), [(ammo, 7)])

    def test_minus_five_blocks_carried_ammo_and_equipment_even_with_a_scanner(self):
        stats = mobs.stats(258)
        with patch.object(mobs, 'carried') as carried, \
                patch.object(mob_equipment_loot, 'roll') as equipment, \
                patch.object(mobs, 'quest_table', return_value=[(3770, 1), (2408, 1)]):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(), (3770, 2408), loc_id=80,
                                          killer_level=stats.level + 5, multiplier=3.75), [(3770, 1)])
        carried.assert_not_called()
        equipment.assert_not_called()

    def test_minus_four_preserves_active_quest_chances_without_scaling_them(self):
        stats = NS(role='mob', level=10, type_id=411)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[(3770, .5), (5545, .5)]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(.49), (3770, 5545),
                                          killer_level=14, multiplier=.25), [(3770, 1), (5545, 1)])
            self.assertEqual(mobs.loot_for(stats, FixedRandom(.5), (3770, 5545),
                                          killer_level=14, multiplier=.25), [])

    def test_boss_ingot_is_certain_both_before_and_beyond_the_new_cutoff(self):
        stats = mobs.stats(269)
        ingots = [(t, mobs.count_of(stats.type_id, t)) for t, _chance, _value
                  in mobs.loot_table(stats.type_id) if t in items.GOLD_INGOTS]
        self.assertTrue(ingots)
        for gap in (-10, -5, -4, -3, -2, 0, 4):
            with patch.object(mobs, 'carried', return_value=[]), \
                    patch.object(bosses, 'blueprint_for', return_value=None):
                drops = mobs.loot_for(stats, FixedRandom(.999), killer_level=stats.level - gap,
                                      multiplier=mobs.loot_level_factor(gap) * 3, gold_multiplier=0)
                self.assertEqual([(t, n) for t, n in drops if t in items.GOLD_INGOTS], ingots)


if __name__ == '__main__':
    run_cases(MobLootFollowup)
