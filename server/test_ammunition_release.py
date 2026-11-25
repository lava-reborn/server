"""Retail/loot ammunition must fit a firearm released to players now."""
import unittest

import items
import shop_bands
import world
from testkit import run_cases


class AmmunitionRelease(unittest.TestCase):
    def test_unreleased_calibres_are_blocked_in_every_quality(self):
        unsupported = {'545x39', 'Metallbolt', '40mmRPG', '68x43', '16mm'}
        checked = set()
        for type_id, (root, _name) in items.catalogue().items():
            if root == items.AMMO and shop_bands.ammunition_order(type_id)[0] in unsupported:
                self.assertTrue(items.acquisition_blocked(type_id), type_id)
                checked.add(shop_bands.ammunition_order(type_id)[0])
        self.assertEqual(checked, unsupported)
        self.assertTrue(all(items.acquisition_blocked(t) for t in range(60022, 60027)))

    def test_every_round_for_released_player_firearms_remains_available(self):
        checked = 0
        for type_id, (root, _name) in items.catalogue().items():
            if (root != items.FIRE_ARM or type_id == items.ADMIN_GUN
                    or items.out_of_game(type_id) or items.acquisition_blocked(type_id)):
                continue
            for round_id in items.params_of(type_id)['comp_array']:
                self.assertFalse(items.acquisition_blocked(round_id), (type_id, round_id))
                checked += 1
        self.assertGreater(checked, 500)
        self.assertFalse(items.acquisition_blocked(items.STARTER_ROUNDS))

    def test_all_trader_stocks_exclude_ammunition_without_released_weapons(self):
        checked = 0
        for trader, (root, _name, _art) in world.mob_types().items():
            if root != world.TRADER:
                continue
            for type_id in items.stock_for(trader):
                if items.root_of(type_id) == items.AMMO:
                    self.assertFalse(items.acquisition_blocked(type_id), (trader, type_id))
                    checked += 1
        self.assertGreater(checked, 500)

    def test_oases_prisons_and_bases_keep_all_released_qualities_for_sold_calibres(self):
        counters = [(ammo, loc) for loc, (_weapon, ammo) in shop_bands.OASIS_MARKETS.items()]
        counters += [(2180, 176), (2181, 159), (880, 177), (714, 609), (5240, 1443)]
        for trader, location in counters:
            with self.subTest(trader=trader, location=location):
                rounds = {t for t in items.stock_for(trader, location) if items.root_of(t) == items.AMMO}
                self.assertTrue(rounds)
                self.assertFalse(rounds - items.player_ammunition())
                calibres = {shop_bands.ammunition_order(t)[0] for t in rounds}
                for calibre in calibres:
                    variants = shop_bands.retail_ammunition_by_calibre().get(calibre, ())
                    gold = {t for t in variants if items.gold_round(items.params_of(t))}
                    self.assertTrue(gold <= rounds, (trader, location, calibre, gold - rounds))


if __name__ == '__main__':
    run_cases(AmmunitionRelease)
