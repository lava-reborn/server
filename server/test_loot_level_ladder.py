"""Level-scaled random loot retains guarantees, quest drops and boss ingots."""
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')

import bosses
import combat
import effects
import items
import mobs
from testkit import run_cases


class Fighter:
    is_player = True

    def __init__(self, level=14):
        self.level = level
        self.sess = NS()


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class LootLevelLadder(unittest.TestCase):
    def mob(self, level, role='mob', fighter=None):
        fighter = fighter or Fighter()
        return NS(stats=NS(level=level, role=role, type_id=269),
                  xp_ledger={fighter: [100]}, loot_level=fighter.level, type_id=269)

    def test_every_level_boundary_with_and_without_a_scanner(self):
        fighter = Fighter()
        ladder = {-10: 0, -5: 0, -4: .25, -3: .5, -2: 1, -1: 1,
                  0: 1, 1: 1, 2: 1.05, 3: 1.15, 4: 1.25, 5: 1.25, 10: 1.25}
        for gap, expected in ladder.items():
            target = self.mob(fighter.level + gap, fighter=fighter)
            for scanner in (1, 3):
                with self.subTest(gap=gap, scanner=scanner), \
                        patch.object(effects, 'multiplier', return_value=scanner):
                    self.assertAlmostEqual(combat.RoomCombat.loot_multiplier(None, target, fighter),
                                           expected * scanner)
                    self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, fighter,
                                                                       include_scanner=False), expected)

    def test_departed_senior_contributor_prevents_lower_level_last_hit_boost(self):
        low = Fighter(10)
        target = self.mob(14, fighter=low)
        target.xp_ledger = {123: [100], low: [1]}
        target.loot_level = 14
        self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), 1)
        target.loot_level = 19
        with patch.object(effects, 'multiplier', return_value=3):
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, low), 0)

    def test_boss_ingot_modifier_is_neutral_at_every_gap_and_ignores_scanners(self):
        fighter = Fighter()
        for gap in (-10, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5):
            target = self.mob(fighter.level + gap, role='boss', fighter=fighter)
            with self.subTest(gap=gap), patch.object(effects, 'multiplier', return_value=3) as scanner:
                self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, fighter,
                                                                   include_scanner=False), 1)
                scanner.assert_not_called()

    def test_fractional_multipliers_reach_random_tables_without_being_raised_to_one(self):
        stats = NS(role='mob', level=14, type_id=411)
        for multiplier in (.25, .5, .75, .95, 1, 1.05, 1.15, 1.25, 3.75):
            with self.subTest(multiplier=multiplier), \
                    patch.object(mobs, 'carried', return_value=[]) as carried, \
                    patch.object(mobs, 'roll_table', return_value=[]) as table, \
                    patch.object(mobs, 'quest_roll', return_value=[]) as quest, \
                    patch.object(bosses, 'blueprint_for', return_value=None):
                rng = FixedRandom(.1)
                mobs.loot_for(stats, rng, {3770}, killer_level=14, multiplier=multiplier)
                carried.assert_called_once_with(stats, rng, multiplier)
                table.assert_called_once_with(411, rng, multiplier, gold_multiplier=1,
                                               guarantee_ingots=False)
                quest.assert_called_once_with(411, {3770}, rng)

    def test_guaranteed_carried_table_and_one_of_drops_and_quest_chances_stay_native(self):
        stats = NS(role='mob', level=14, type_id=411)
        for multiplier in (.25, .5, .75, .95, 1, 1.25, 3.75):
            with self.subTest(multiplier=multiplier), \
                    patch.object(mobs, 'carried', return_value=[(41, 1)]), \
                    patch.object(mobs, 'loot_table', return_value=[(333, .2, False), (334, 1, False)]), \
                    patch.object(mobs, 'independent_loot', return_value=set()), \
                    patch.object(mobs, 'count_of', return_value=1), \
                    patch.object(mobs, 'one_of_groups', return_value=[[(216, 1), (217, 1)]]), \
                    patch.object(mobs, 'quest_table', return_value=[(3770, .5)]), \
                    patch.object(bosses, 'blueprint_for', return_value=None):
                drops = mobs.loot_for(stats, FixedRandom(.1), {3770}, killer_level=14,
                                      multiplier=multiplier)
                expected = {(41, 1), (334, 1), (216, 1), (3770, 1)}
                if .1 < .2 * multiplier:
                    expected.add((333, 1))
                self.assertEqual(set(drops), expected)

    def test_boss_ingot_is_certain_through_cutoff_without_unlocking_other_rewards(self):
        fighter = Fighter(15)
        target = self.mob(10, role='boss', fighter=fighter)
        ingot = next(iter(items.GOLD_INGOTS))
        with patch.object(effects, 'multiplier', return_value=3), \
                patch.object(mobs, 'carried') as carried, \
                patch.object(mobs, 'loot_table', return_value=[(ingot, .2, True), (333, 1, False)]), \
                patch.object(mobs, 'independent_loot', return_value={ingot}), \
                patch.object(mobs, 'count_of', return_value=1), \
                patch.object(mobs, 'one_of_groups', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[(3770, .5), (2408, .5)]):
            ordinary = combat.RoomCombat.loot_multiplier(None, target, fighter)
            gold = combat.RoomCombat.loot_multiplier(None, target, fighter, include_scanner=False)
            self.assertEqual((ordinary, gold), (0, 1))
            for roll in (.19, .21, .99):
                drops = mobs.loot_for(target.stats, FixedRandom(roll), {3770, 2408},
                                      killer_level=15, multiplier=ordinary, gold_multiplier=gold)
                expected = {(ingot, 1)} | ({(3770, 1)} if roll < .5 else set())
                self.assertEqual(set(drops), expected)
            self.assertEqual(mobs.loot_for(target.stats, FixedRandom(.19), (), killer_level=15,
                                          multiplier=ordinary, gold_multiplier=gold), [(ingot, 1)])
            carried.assert_not_called()

    def test_scanner_changes_only_ordinary_random_drop_rolls(self):
        fighter = Fighter(14)
        target = self.mob(15, role='boss', fighter=fighter)
        ingot = next(iter(items.GOLD_INGOTS))
        with patch.object(mobs, 'loot_table', return_value=[(ingot, .2, True), (333, .2, False)]), \
                patch.object(mobs, 'independent_loot', return_value={ingot}), \
                patch.object(mobs, 'count_of', return_value=1), \
                patch.object(mobs, 'one_of_groups', return_value=[]):
            for scanner in (1, 3):
                with self.subTest(scanner=scanner), patch.object(effects, 'multiplier', return_value=scanner):
                    ordinary = combat.RoomCombat.loot_multiplier(None, target, fighter)
                    gold = combat.RoomCombat.loot_multiplier(None, target, fighter, include_scanner=False)
                    self.assertEqual(gold, 1)
                    drops = mobs.roll_table(269, FixedRandom(.21), ordinary, gold_multiplier=gold,
                                            guarantee_ingots=True)
                    self.assertEqual(drops, [(ingot, 1)] if scanner == 1 else [(ingot, 1), (333, 1)])

    def test_every_native_boss_ingot_kind_and_count_survives_at_any_killer_level(self):
        carriers = {int(type_id) for type_id, rows in mobs._loot_manual().items()
                    if any(row.get('type') in items.GOLD_INGOTS for row in rows)}
        self.assertTrue(carriers)
        for type_id in carriers:
            stats = mobs.stats(type_id)
            self.assertEqual(stats.role, 'boss')
            expected = [(t, mobs.count_of(type_id, t)) for t, _chance, _valuable
                        in mobs.loot_table(type_id) if t in items.GOLD_INGOTS]
            self.assertTrue(expected)
            for gap in (-10, -4, -3, 0, 1, 4, 10):
                with self.subTest(type_id=type_id, gap=gap), \
                        patch.object(mobs, 'carried', return_value=[]), \
                        patch.object(bosses, 'blueprint_for', return_value=None):
                    drops = mobs.loot_for(stats, FixedRandom(.999), killer_level=stats.level - gap,
                                          multiplier=0 if gap <= -4 else 3.75, gold_multiplier=0)
                    self.assertEqual([(t, n) for t, n in drops if t in items.GOLD_INGOTS], expected)

    def test_ingot_one_of_preserves_one_weighted_choice_and_never_all_alternatives(self):
        gold = tuple(items.GOLD_INGOTS)
        with patch.object(mobs, 'loot_table', return_value=[]), \
                patch.object(mobs, 'independent_loot', return_value=set()), \
                patch.object(mobs, 'one_of_groups', return_value=[[(gold[0], 1), (gold[1], 3)]]):
            for roll, chosen in ((0, gold[0]), (.249, gold[0]), (.25, gold[1]), (.999, gold[1])):
                with self.subTest(roll=roll):
                    self.assertEqual(mobs.roll_table(269, FixedRandom(roll), 0, gold_multiplier=0,
                                                     guarantee_ingots=True), [(chosen, 1)])

    def test_guarantee_does_not_add_gold_to_boss_without_an_ingot_entry(self):
        stats = NS(role='boss', level=14, type_id=411)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'loot_table', return_value=[(333, .2, False)]), \
                patch.object(mobs, 'independent_loot', return_value=set()), \
                patch.object(mobs, 'one_of_groups', return_value=[]), \
                patch.object(mobs, 'quest_table', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(.1), killer_level=14), [(333, 1)])
            self.assertEqual(mobs.loot_for(stats, FixedRandom(.1), killer_level=19), [])

    def test_nonboss_ingot_chance_stays_native_and_only_uses_explicit_gold_modifier(self):
        ingot = next(iter(items.GOLD_INGOTS))
        with patch.object(mobs, 'loot_table', return_value=[(ingot, .2, True)]), \
                patch.object(mobs, 'independent_loot', return_value=set()), \
                patch.object(mobs, 'count_of', return_value=4), \
                patch.object(mobs, 'one_of_groups', return_value=[]):
            self.assertEqual(mobs.roll_table(411, FixedRandom(.21), 3.75), [])
            self.assertEqual(mobs.roll_table(411, FixedRandom(.21), .25, gold_multiplier=1.25),
                             [(ingot, 4)])

    def test_harvest_objects_do_not_receive_level_or_scanner_modifiers(self):
        fighter = Fighter()
        for gap in (-10, 0, 10):
            target = self.mob(fighter.level + gap, role='object', fighter=fighter)
            with patch.object(effects, 'multiplier', return_value=3) as scanner:
                self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, fighter), 1)
                scanner.assert_not_called()


if __name__ == '__main__':
    run_cases(LootLevelLadder)
