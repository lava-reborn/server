"""Released buffs retain a clear potency/price ladder in each currency."""
from collections import defaultdict
from fractions import Fraction
import math
import unittest

import effects
import inventory
import items
from testkit import run_cases


def potency(effect):
    bonus = effect['bonuses']
    values = [bonus[k] for k in effects.SCALARS]
    values += [n for k in effects.ARRAYS for n in bonus[k]]
    modifiers = effect.get('modifiers', {})
    direction = -1 if effect.get('family') == 'experience_down' else 1
    values += [round(direction * (modifiers.get(k, 1) - 1), 8)
               for k in ('mob_exp', 'pl_exp', 'mob_drop')]
    return values


class BuffProgression(unittest.TestCase):
    def test_stronger_released_buffs_never_cost_less_within_their_family_and_currency(self):
        groups = defaultdict(list)
        for tid, effect in effects.definitions().items():
            if items.acquisition_blocked(tid):
                continue
            params = items.params_of(tid)
            currency = 'g_cost' if params.get('g_cost') else 'cost'
            if params.get(currency, 0) > 0:
                groups[effect['family'], currency].append((tid, effect, params[currency]))
        comparisons = 0
        for rows in groups.values():
            for low, old_effect, old_cost in rows:
                for high, new_effect, new_cost in rows:
                    a, b = potency(old_effect), potency(new_effect)
                    stronger = all(y >= x for x, y in zip(a, b)) and any(y > x for x, y in zip(a, b))
                    longer = a == b and new_effect['duration'] > old_effect['duration']
                    if stronger:
                        self.assertGreater(new_cost, old_cost, (low, high))
                        comparisons += 1
                    elif longer:
                        self.assertGreaterEqual(new_cost, old_cost, (low, high))
                        comparisons += 1
        self.assertGreater(comparisons, 100)

    def test_plus_prices_scale_from_mk_nine_without_changing_effects(self):
        for previous, plus, stat, price, bonus in (
                (4935, 4936, 'hp', 220, 300), (4955, 4956, 'sp', 220, 600)):
            old, current = effects.definition(previous), effects.definition(plus)
            scaled = Fraction(items.params_of(previous)['g_cost'] * bonus, old['bonuses'][stat])
            self.assertEqual(math.ceil(scaled / 5) * 5, price)
            params = items.params_of(plus)
            self.assertEqual((params['cost'], params['g_cost']), (0, price))
            self.assertEqual((current['bonuses'][stat], current['duration']), (bonus, 1800))
            self.assertEqual(inventory.buy_price(params, items.HEAL, 1, True), price)
            self.assertEqual(inventory.buy_price(params, items.HEAL, 1, True, .9), math.ceil(price * .9))

    def test_salus_eight_is_a_real_intermediate_tier_and_nine_costs_more(self):
        for tier in range(1, 10):
            afro = effects.definition(4916 + tier * 2)
            gold = effects.definition(4917 + tier * 2)
            self.assertEqual(afro['bonuses']['hp'], 25 * (tier + 1))
            self.assertEqual(gold['bonuses']['hp'], 25 * (tier + 2))
            self.assertEqual((afro['duration'], gold['duration']), (600 * tier, 600 * (tier + 1)))
        self.assertEqual(items.params_of(4934)['cost'], 84000)
        self.assertEqual(items.params_of(4935)['g_cost'], 200)


if __name__ == '__main__':
    run_cases(BuffProgression)
