"""Agreed A-blueprint rounding, cheap-price floor and unchanged G/common lines."""
import unittest
import blueprint_prices
from testkit import run_cases


class BlueprintPrices(unittest.TestCase):
    def test_independent_approved_gold_examples(self):
        for before, after in ((100, 50), (200, 150), (300, 200), (500, 250),
                              (750, 500), (1000, 750), (1500, 1000), (2000, 1250)):
            with self.subTest(before=before):
                params = dict(g_cost=before, cost=6000)
                blueprint_prices.apply('bpg_damage_25_afro_lvl12', params)
                self.assertEqual(params, dict(g_cost=after, cost=4000))

    def test_cheapest_price_never_increases_or_becomes_free(self):
        for before in (1, 25, 49, 50):
            params = dict(g_cost=before)
            blueprint_prices.apply('bpg_damage_25_afro_lvl1', params)
            self.assertGreater(params['g_cost'], 0)
            self.assertLessEqual(params['g_cost'], before)

    def test_gold_and_common_blueprints_keep_their_purchase_prices(self):
        for name in ('bpg_damage_25_gold_lvl12', 'bp_damage_10_lvl12', 'other'):
            params = dict(g_cost=1500, cost=10000)
            blueprint_prices.apply(name, params)
            self.assertEqual(params, dict(g_cost=1500, cost=10000))


if __name__ == '__main__':
    run_cases(BlueprintPrices)
