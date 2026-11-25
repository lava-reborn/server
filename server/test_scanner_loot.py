"""Scanner quantity/probability boundaries and durable, lossless corpse creation."""
from collections import Counter
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import accounts
import bosses
import combat
import inventory
import items
import mob_equipment_loot
import mortimer
import mobs
import names
from testkit import run_cases


class FixedRandom:
    def __init__(self, draw=0):
        self.draw = draw

    def random(self):
        return self.draw

    def choice(self, values):
        return values[0]

    def randint(self, low, high):
        return low


class ScannerLoot(unittest.TestCase):
    def test_only_common_afro_loot_can_have_quantity_increased(self):
        for type_id in (41, 333, 334, 6092):
            self.assertTrue(items.scanner_quantity_item(type_id), type_id)
        for type_id in (2258, 6950, 6951, 6952, 6953, 6959, 3577, 26177, 1069, 3770, 3789, 3826,
                        *items.GOLD_INGOTS):
            self.assertFalse(items.scanner_quantity_item(type_id), type_id)
        for type_id, (root, _name) in items.catalogue().items():
            if root in (items.FIRE_ARM, items.WEAR, items.COLD_ARM):
                self.assertFalse(items.scanner_quantity_item(type_id), type_id)

    def test_common_quantity_gold_and_quest_count_are_separate(self):
        stats = NS(role='mob', type_id=82, level=11)
        ingot = next(iter(items.GOLD_INGOTS))
        rows = [(333, .1, False), (6950, .1, True), (ingot, .1, True), (334, mobs.SURE, False)]
        with patch.object(mobs, 'carried', return_value=[(41, 2)]), \
                patch.object(mobs, 'loot_table', return_value=rows), \
                patch.object(mobs, 'independent_loot', return_value={333, 6950, ingot}), \
                patch.object(mobs, 'count_of', return_value=2), \
                patch.object(mobs, 'one_of_groups', return_value=[]), \
                patch.object(mobs, 'quest_roll', return_value=[(3770, 1)]), \
                patch.object(bosses, 'blueprint_for', return_value=None), \
                patch.object(mob_equipment_loot, 'roll', return_value=[]):
            def loot(scanner, draw):
                return dict(mobs.loot_for(stats, FixedRandom(draw), (3770,), multiplier=scanner,
                                         scanner_multiplier=scanner))
            self.assertEqual(loot(1, .05), {41: 2, 333: 2, 334: 2, 6950: 2, ingot: 2, 3770: 1})
            self.assertEqual(loot(3, .05), {41: 6, 333: 6, 334: 6, 6950: 2, ingot: 2, 3770: 1})
            self.assertEqual(loot(1, .15), {41: 2, 334: 2, 3770: 1})
            self.assertEqual(loot(3, .15), {41: 6, 334: 6, 3770: 1})
            self.assertEqual(loot(3, .31), {41: 6, 334: 6, 3770: 1})
            stats.role = 'object'
            self.assertEqual(loot(3, .05), loot(1, .05))
            stats.role = 'boss'
            self.assertEqual(loot(3, .99)[ingot], 2)

    def test_scanner_never_changes_any_gold_valuable_or_ingot_roll(self):
        stats = NS(role='mob', type_id=82, level=11)
        types = mortimer.VALUABLES | items.GOLD_INGOTS.keys() | {mortimer.SAND}
        rows = [(type_id, .1, True) for type_id in sorted(types)]
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'loot_table', return_value=rows), \
                patch.object(mobs, 'independent_loot', return_value=types), \
                patch.object(mobs, 'one_of_groups', return_value=[]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None), \
                patch.object(mob_equipment_loot, 'roll', return_value=[]):
            for gap_factor in (.75, 1, 1.3):
                for scanner in (1, 3):
                    for draw, expected in ((.1 * gap_factor - 1e-9, types),
                                           (.1 * gap_factor + 1e-9, set())):
                        with self.subTest(gap_factor=gap_factor, scanner=scanner, draw=draw):
                            drops = mobs.loot_for(stats, FixedRandom(draw),
                                multiplier=gap_factor * scanner, gold_multiplier=gap_factor,
                                scanner_multiplier=scanner)
                            self.assertEqual(dict(drops), dict.fromkeys(expected, 1))

    def test_each_equipment_category_gets_triple_probability_but_only_one_item(self):
        stats = mobs.stats(291)
        categories = mob_equipment_loot.categories(stats, 84)
        self.assertTrue(all(types for _kind, types, _chance in categories))
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            threshold = 0
            for _kind, types, chance in categories:
                threshold += chance
                drops = mobs.loot_for(stats, FixedRandom(threshold*3-1e-9), loc_id=84,
                                      multiplier=3, scanner_multiplier=3)
                self.assertEqual(drops, [(types[0], 1)])
            self.assertEqual(mobs.loot_for(stats, FixedRandom(threshold*3), loc_id=84,
                                          multiplier=3, scanner_multiplier=3), [])

    def test_sure_gold_equipment_is_not_copied(self):
        stats = NS(role='mob', type_id=82, level=11)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'loot_table', return_value=[]), \
                patch.object(mobs, 'one_of_groups', return_value=[[(26177, 1)]]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None), \
                patch.object(mob_equipment_loot, 'roll', return_value=[]):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(), multiplier=3,
                                          scanner_multiplier=3), [(26177, 1)])

    def test_both_descriptions_explain_quantity_and_equipment_exceptions(self):
        for type_id in (3789, 3826):
            text = names.ALL[items.DESC_ID_OFFSET + type_id]
            for fragment in ('количество обычного лута за афро на 200%', 'шанс выпадения на 200%',
                             'Количество снаряжения не меняется', 'На дроп золотых ценностей не влияет'):
                self.assertIn(fragment, text)


class ScannerLootStorage(unittest.IsolatedAsyncioTestCase):
    async def test_overflow_nonheap_items_and_ground_are_atomic_and_idempotent(self):
        store = accounts.Store(':memory:')
        self.addCleanup(store.close)
        mob = NS(type_id=82, stats=NS(role='mob'), cell=42, quest_wants=frozenset(),
                 loot_multiplier=3, gold_loot_multiplier=1, scanner_multiplier=3)
        published = []
        rc = NS(store=store, room=NS(loc=NS(id=100)), place=(100, 0, 0),
                add_to_bag=lambda *args: published.append(args))
        rc.drop_loot = lambda target: combat.RoomCombat.drop_loot(rc, target)
        limit = items.params_of(6092)['max_count']
        expected = {6092: limit+7, 3789: 2, 333: 301}
        create = store.create_item
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('injected storage failure')
            return create(*args, **kwargs)
        with patch.object(mobs, 'loot_for', return_value=list(expected.items())) as generator, \
                patch.object(combat.events, 'loot', return_value=[]), \
                patch.object(combat.production, 'yield_of', return_value=[]):
            with patch.object(store, 'create_item', side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, 'injected'):
                    combat.RoomCombat.materialize_loot(rc, mob)
            self.assertFalse(getattr(mob, '_loot_materialized', False))
            self.assertEqual(store.items_of(combat.LOOT_OWNER), [])
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM ground').fetchone()[0], 0)
            self.assertEqual(published, [])
            combat.RoomCombat.materialize_loot(rc, mob)
            rows = store.items_of(combat.LOOT_OWNER)
            actual = Counter()
            for row in rows:
                actual[row['type_id']] += row['count']
                self.assertLessEqual(row['count'], items.params_of(row['type_id']).get('max_count', 1))
            self.assertEqual(dict(actual), expected)
            self.assertEqual(len([row for row in rows if row['type_id'] == 3789]), 2)
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM ground').fetchone()[0], len(rows))
            generator.assert_called_with(mob.stats, combat.RNG, mob.quest_wants, loc_id=100,
                ambush_camp=None, killer_level=None, multiplier=3, gold_multiplier=1,
                scanner_multiplier=3, box_player_kill=False, box_weapon_type=None)
            combat.RoomCombat.materialize_loot(rc, mob)
            self.assertEqual(len(store.items_of(combat.LOOT_OWNER)), len(rows))
            self.assertEqual(len(published), 1)


if __name__ == '__main__':
    run_cases(ScannerLoot, ScannerLootStorage)
