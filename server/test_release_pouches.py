"""Approved MOD A1 pouches keep raw level gates and temporary learned-spec bonuses."""
import unittest

import inventory
import items
import progression as p
from testkit import run_cases


class ReleasePouches(unittest.TestCase):
    # Ready-made pouches cost more than their accepted laboratory recipes.
    PRICES = {3735: 6000, 3736: 5500, 3737: 6000, 3738: 7000,
              3739: 5000, 3740: 5000, 5615: 6000}
    BONUSES = {3735: {0: 3, 1: 3, 4: 1}, 3736: {0: 3, 1: 3, 5: 1},
               3737: {0: 3, 1: 3, 7: 1}, 3738: {0: 3, 1: 3, 6: 1},
               3739: {0: 3, 1: 3, 3: 1}, 3740: {0: 3, 1: 3, 2: 1},
               5615: {0: 4, 1: 4}}

    def row(self, type_id):
        return dict(type_id=type_id, root=items.WEAR, slot=inventory.BELT, brk=1000)

    def test_all_seven_laboratory_mods_are_sold_at_their_rounded_prices(self):
        stock = items.stock_for(1219, 126)
        self.assertEqual(set(stock) & set(self.PRICES), set(self.PRICES))
        self.assertEqual(len(stock), len(set(stock)))
        for tid, gold in self.PRICES.items():
            self.assertEqual((items.params_of(tid)['cost'], items.params_of(tid)['g_cost']), (0, gold))
            self.assertEqual(inventory.item_level(tid), 16)

    def test_four_golden_valentines_are_sold_by_gift_merchants_only(self):
        gifts = {1069, 1070, 1071, 1072}
        for trader, location in ((1959, 41), (1797, 445)):
            stock = items.stock_for(trader, location)
            self.assertEqual(set(stock) & gifts, gifts)
            self.assertEqual(len(stock), len(set(stock)))
            self.assertFalse(set(stock) & {1073, 1074})
            for t in gifts:
                self.assertEqual((items.params_of(t)['cost'], items.params_of(t)['g_cost']), (0, 2500))
        self.assertFalse(set(items.stock_for(1219, 126)) & gifts)
        self.assertFalse(set(items.stock_for(1965, 445)) & gifts)

    def test_level_allowance_uses_base_level_despite_bonus_skills(self):
        for tid in self.PRICES:
            ch = p.Character()
            ch.set_skill(p.SHOOTING, 12)
            ch.bonus_skills = [100] * p.SKILLS
            self.assertFalse(inventory.wearable(self.row(tid), ch.level, ch))
            ch.set_skill(p.SHOOTING, 13)
            self.assertTrue(inventory.wearable(self.row(tid), ch.level, ch))
            ch.set_skill(p.SHOOTING, 16)
            self.assertTrue(inventory.wearable(self.row(tid), ch.level, ch))

    def test_actual_gear_bonus_extends_only_learned_specialisations(self):
        for tid, declared in self.BONUSES.items():
            with self.subTest(item=tid):
                ch = p.Character()
                original = [sp[:] for sp in ch.spec]
                ch.set_gear(inventory.gear_bonus([self.row(tid)], ch))
                self.assertEqual([ch.spec_level(i) for i in declared], [-1] * len(declared))
                self.assertEqual(ch.spec, original)
                ch.set_gear(inventory.gear_bonus([], ch))
                for index in declared:
                    ch.set_spec(index, 5)
                saved = [sp[:] for sp in ch.spec]
                bonus = inventory.gear_bonus([self.row(tid)], ch)
                ch.set_gear(bonus)
                for index, amount in declared.items():
                    self.assertEqual(ch.spec_level(index), 5 + amount)
                    self.assertEqual(ch.spec[index][0], 5)
                self.assertEqual(ch.spec, saved)
                expected = [0] * p.ATTRIBS
                expected[{3735: p.AGILITY, 3736: p.PERCEPTION, 3737: p.AGILITY,
                          3738: p.STRENGTH, 3739: p.STRENGTH, 3740: p.AGILITY,
                          5615: p.AGILITY}[tid]] = 1
                for index, amount in declared.items():
                    expected[p.SPEC_ATTRIB[index]] += amount
                self.assertEqual(bonus['attribs'], expected)
                ch.set_gear(inventory.gear_bonus([], ch))
                self.assertEqual(ch.spec, saved)
                self.assertEqual([ch.spec_level(i) for i in declared], [5] * len(declared))

    def test_mod_bonus_does_not_increase_trained_specialisation_cap(self):
        for tid, declared in self.BONUSES.items():
            ch = p.Character()
            for index in declared:
                ch.set_spec(index, 5)
            ch.set_gear(inventory.gear_bonus([self.row(tid)], ch))
            for index in declared:
                ch.gain_spec_xp(index, 100000000)
                self.assertEqual(ch.spec[index][0], 5)
                self.assertLessEqual(ch.spec[index][1], ch.spec[index][2])
                self.assertEqual(ch.spec_level(index), 5 + declared[index])


if __name__ == '__main__':
    run_cases(ReleasePouches)
