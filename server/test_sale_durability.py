"""Factory durability in A/G resale and purchase/upgrade currency invariants."""
from fractions import Fraction
import unittest

import test_gold_commerce as fixtures
import craft
import gold_trade
import inventory
import items
import progression
import setcraft
import shop_bands
from testkit import run_cases


class SaleDurability(unittest.TestCase):
    give = fixtures.GoldCommerce.give
    quote = fixtures.GoldCommerce.quote
    confirmed = fixtures.GoldCommerce.confirmed
    sell = fixtures.GoldCommerce.sell

    def setUp(self):
        fixtures.GoldCommerce.setUp(self)
        self.s.room.loc = self.s.loc

    def test_quality_combines_ceiling_loss_and_current_damage(self):
        params = dict(max_break_abs=1000)
        for brk, ceiling, expected in ((1000, 1000, 1), (500, 500, .5),
                                        (250, 500, .25), (0, 500, 0),
                                        (500, 0, 0), (2000, 2000, 1),
                                        (1000, 500, .5)):
            with self.subTest(brk=brk, ceiling=ceiling):
                self.assertEqual(gold_trade.sale_quality(
                    dict(root=items.FIRE_ARM, brk=brk, max_break_cur=ceiling), params), expected)

    def test_g_resale_pays_half_for_half_factory_ceiling_and_quarter_with_damage(self):
        for brk, expected in ((750, 181475), (375, 90737)):
            row = self.give(26075)
            self.store.update_item(row['uniq'], brk=brk, max_break_cur=750)
            row = self.store.item(row['uniq'])
            before = self.store.money(self.cid)
            request, quote = self.quote(row)
            self.assertEqual(quote['price'], expected)
            self.assertEqual(self.confirmed(request, quote), 0)
            self.assertEqual(self.store.money(self.cid), (before[0] + expected, before[1]))
            self.assertNotEqual(self.confirmed(request, quote), 0)
            self.assertEqual(self.store.money(self.cid), (before[0] + expected, before[1]))

    def test_a_resale_uses_factory_ceiling_too(self):
        for brk, expected in ((750, 11375), (375, 5687)):
            row = self.give(26061)
            self.store.update_item(row['uniq'], brk=brk, max_break_cur=750)
            before = self.store.money(self.cid)
            self.assertEqual(self.sell(row, 1), 0)
            self.assertEqual(self.store.money(self.cid), (before[0] + expected, before[1]))

    def test_ordinary_repair_cannot_restore_full_npc_value(self):
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=1, max_break_cur=750)
        self.frames.clear()
        self.inv.repair(dict(obj=inventory.oid_of(row)), inventory.UPD_REPAIR_GOLD)
        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
        row = self.store.item(row['uniq'])
        self.assertEqual((row['brk'], row['max_break_cur']), (675, 675))
        _, quote = self.quote(row)
        self.assertEqual(quote['price'], 163327)

    def test_ceiling_change_invalidates_existing_g_quote(self):
        row = self.give(26075)
        request, quote = self.quote(row)
        self.store.update_item(row['uniq'], brk=750, max_break_cur=750)
        self.assertNotEqual(self.confirmed(request, quote), 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.money(self.cid), (12345, 100))


RATE = Fraction(progression.GOLD_TO_AFRO_RATE, progression.GOLD_OUNCE)


def purchase(type_id):
    params = items.params_of(type_id) or {}
    options = []
    if params.get('cost', 0) > 0:
        options.append(Fraction(str(params['cost'])))
    if params.get('g_cost', 0) > 0:
        options.append(Fraction(str(params['g_cost'])) * RATE)
    return min(options) if options else None


class ResalePaths(unittest.TestCase):
    def test_shop_purchase_resale_does_not_print_currency(self):
        checked = 0
        for t in shop_bands.wares():
            p = items.params_of(t) or {}
            if p.get('quest') or gold_trade.protected(t, p):
                continue
            paid = purchase(t)
            if paid is None:
                continue
            per = Fraction(str(p.get('sell_num') or 1))
            paid /= per
            if gold_trade.gold_priced(t, p):
                sale = Fraction(str(gold_trade.sale_unit(t, p)))
            elif items.root_of(t) in items.BREAKABLE_ROOTS:
                sale = Fraction(str(gold_trade.afro_sale_unit(t, p)))
            else:
                sale = (Fraction(str(p.get('cost', 0))) * gold_trade.NPC_SALE_SHARE
                        * Fraction(str(p.get('sell_mod', 1))) / per)
            self.assertLessEqual(sale, paid, t)
            checked += 1
        self.assertGreater(checked, 200)

    def test_g_weapon_upgrade_resale_is_below_cheapest_compatible_inputs(self):
        checked = 0
        for r in craft.rows().values():
            if r.get('family') != 'upgrade':
                continue
            p = items.params_of(r['mod']) or {}
            if not gold_trade.gold_priced(r['mod'], p) or items.acquisition_blocked(r['mod']):
                continue
            gun = purchase(r['gun'])
            blueprints = [purchase(t) for t in craft.blueprint_variants(r['blueprint'])]
            blueprints = [v for v in blueprints if v is not None]
            if gun is None or not blueprints:
                continue
            self.assertLessEqual(Fraction(str(gold_trade.sale_unit(r['mod'], p))),
                                 gun + min(blueprints), r['mod'])
            checked += 1
        self.assertGreater(checked, 100)

    def test_g_set_upgrade_resale_is_below_input_and_service_cost(self):
        paths = set()
        for loc, npc in setcraft.OASIS_UPGRADERS.items():
            paths.update(setcraft.entries(npc, loc))
        for slice_ in setcraft.SLICES.values():
            for npc in slice_['upgraders']:
                paths.update(setcraft.entries(npc))
        checked = 0
        for src, dst, cents in paths:
            if items.acquisition_blocked(dst):
                continue
            paid = purchase(src)
            if paid is None:
                continue
            self.assertLessEqual(Fraction(str(gold_trade.sale_unit(dst, items.params_of(dst)))),
                                 paid + cents * RATE, (src, dst))
            checked += 1
        self.assertGreaterEqual(checked, 50)


if __name__ == '__main__':
    run_cases(SaleDurability, ResalePaths)
