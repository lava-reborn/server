"""Rare loot rates, exclusivity, native exceptions and remaining durability."""
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')

import camp_loot
import inventory
import items
import mob_equipment_loot as equipment
import mob_weapon_loot
import mobs
import sets
from testkit import run_cases


class FixedRandom:
    def __init__(self, value=0, upper=False):
        self.value, self.upper, self.calls = value, upper, []

    def random(self):
        self.calls.append('random')
        return self.value

    def choice(self, values):
        return values[0]

    def randint(self, low, high):
        self.calls.append((low, high))
        return high if self.upper else low


class EquipmentLoot(unittest.TestCase):
    def test_single_draw_uses_absolute_rates_with_one_result_only(self):
        options = (('armour', (10,), .01), ('weapon', (20,), .005), ('pouch', (30,), .005))
        with patch.object(equipment, 'categories', return_value=options), \
                patch.object(equipment, 'random_drop_allowed', return_value=True):
            for multiplier in (.25, .95, 1, 1.25, 1.3, 3.75, 3.9, 100):
                factor = min(3.9, multiplier)
                for point, expected in ((0, 10), (.009999, 10), (.01, 20),
                                        (.014999, 20), (.015, 30), (.019999, 30), (.02, None)):
                    rng = FixedRandom(point * factor)
                    got = equipment.roll(NS(), rng, multiplier=multiplier)
                    self.assertEqual(got, [(expected, 1)] if expected else [])
                    self.assertEqual(rng.calls, ['random'])

    def test_unavailable_categories_do_not_transfer_their_chance(self):
        options = (('armour', (), .01), ('weapon', (), .005), ('pouch', (30,), .005))
        with patch.object(equipment, 'categories', return_value=options), \
                patch.object(equipment, 'random_drop_allowed', return_value=True):
            for point, expected in ((0, []), (.01, []), (.015, [(30, 1)]), (.02, [])):
                self.assertEqual(equipment.roll(NS(), FixedRandom(point)), expected)
        for multiplier in (0, -1, float('nan'), float('inf')):
            rng = FixedRandom()
            self.assertEqual(equipment.roll(NS(), rng, multiplier=multiplier), [])
            self.assertEqual(rng.calls, [])

    def test_native_candidates_are_clean_a_level_17_or_lower_and_class_matched(self):
        import battle_balance
        for kind, weapon in equipment.POUCHES.items():
            stats = NS(**vars(mobs.stats(365)))
            stats.level, stats.weapon_class, stats.ranged = 23, kind, kind != 'knife'
            categories = equipment.categories(stats, 263)
            self.assertEqual(categories[2], ('pouch', (weapon,), .005))
            selected = categories[1][1][0]
            self.assertTrue(any(row[2] == selected and row[0] <= 17
                                for row in battle_balance.mob_weapons()[kind]))
            self.assertFalse(items.premium(selected))
            self.assertEqual((items.params_of(selected) or {}).get('g_cost', 0), 0)
        for site in (109, 110, 111, 118, 609, 128, 1442, 1443):
            self.assertFalse(equipment.categories(mobs.stats(365), site)[1][1])

    def test_personal_a_reward_wins_and_guaranteed_g_does_not_suppress(self):
        stats = mobs.stats(365)
        a = camp_loot.piece_types(stats, 93)[0]
        g = next(r['members']['armor'] for r in sets.records() if r['variant'] == 'G')
        for type_id in (a, 3577, mob_weapon_loot.weapon_type(stats, 93)):
            rng = FixedRandom()
            self.assertEqual(equipment.roll(stats, rng, loc_id=93, protected=[(type_id, 1)]), [])
            self.assertEqual(rng.calls, [])
        self.assertEqual(len(equipment.roll(stats, FixedRandom(), loc_id=93, protected=[(g, 1)])), 1)
        self.assertEqual(equipment.without_equipment([(a, 5), (3577, 2), (g, 1), (41, 3)]),
                         [(g, 1), (41, 3)])

    def test_remaining_ceiling_and_current_durability_endpoints(self):
        stats = mobs.stats(365)
        types = (camp_loot.piece_types(stats, 93)[0],
                 mob_weapon_loot.weapon_type(stats, 93), 3577)
        for type_id in types:
            factory = items.params_of(type_id)['max_break_abs']
            low, high = equipment.CONDITION[equipment.kind_of(type_id)]
            bounds = equipment.condition_bounds(type_id)
            self.assertEqual(bounds, ((factory * low + 99) // 100, factory * high // 100))
            for upper in (False, True):
                rng = FixedRandom(upper=upper)
                fields = equipment.worn_fields(type_id, rng)
                ceiling = bounds[int(upper)]
                self.assertEqual(fields['max_break_cur'], ceiling)
                self.assertEqual(fields['brk'], ceiling if upper else (ceiling + 1) // 2)
                self.assertLess(ceiling, factory)
                self.assertGreaterEqual(2 * fields['brk'], ceiling)
                self.assertLessEqual(fields['brk'], ceiling)
                self.assertNotIn('upgrade', fields)
                self.assertEqual(inventory.new_fields(type_id)['max_break_cur'], factory)
        g = next(r['members']['armor'] for r in sets.records() if r['variant'] == 'G')
        rng = FixedRandom()
        self.assertEqual(equipment.worn_fields(g, rng), {})
        self.assertEqual(equipment.worn_fields(41, rng), {})
        self.assertEqual(rng.calls, [])


if __name__ == '__main__':
    run_cases(EquipmentLoot)
