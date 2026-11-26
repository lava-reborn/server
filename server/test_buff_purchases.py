"""Paid medicine quantity must equal delivered pieces, including individual buffs."""
import unittest
from unittest.mock import patch

import effects
import inventory
import items
from test_mortimer_sales import MortimerSales
from testkit import run_cases


class BuffPurchases(unittest.TestCase):
    def setUp(self):
        MortimerSales.setUp(self)
        self.store.set_money(self.cid, 100_000_000, 100_000)
        self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
        self.stock = [3561]
        stock = patch.object(items, 'stock_for', side_effect=lambda *args: self.stock)
        stock.start()
        self.addCleanup(stock.stop)
        self.rates = dict(pmod=1, smod=.7, rmod=1)
        rates = patch.object(self.inv, 'current_trade_rates', side_effect=lambda: self.rates)
        rates.start()
        self.addCleanup(rates.stop)

    def buy(self, type_id, n, gold=True):
        self.stock[:] = [type_id]
        self.frames.clear()
        self.inv.buy(dict(obj='0', param=n), inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def test_two_experience_buffs_deliver_two_distinct_items_for_two_unit_prices(self):
        for type_id in effects.EXPERIENCE_UP:
            for modifier in (1, .9):
                with self.subTest(type_id=type_id, modifier=modifier):
                    self.rates['pmod'] = modifier
                    before = self.store.money(self.cid)
                    ids = {r['uniq'] for r in self.inv.rows()}
                    self.assertEqual(self.buy(type_id, 2), [inventory.RES_OK])
                    new = [r for r in self.inv.rows() if r['uniq'] not in ids]
                    self.assertEqual(len(new), 2)
                    self.assertEqual([r['count'] for r in new], [1, 1])
                    self.assertEqual(len({inventory.oid_of(r) for r in new}), 2)
                    self.assertTrue(all(r['type_id'] == type_id for r in new))
                    si = items.params_of(type_id)
                    price = inventory.buy_price(si, items.HEAL, 2, True, modifier)
                    self.assertEqual(self.store.money(self.cid), (before[0], before[1] - price))
                    self.assertEqual(self.s.char.gold, before[1] - price)
                    self.assertEqual(sum(cmd == 'ss_obj_status' for cmd, _ in self.frames), 2)
                    self.assertEqual(sum(cmd == 'ss_di_heal' for cmd, _ in self.frames), 2)
                    self.assertEqual(sum(cmd == 'money' for cmd, _ in self.frames), 1)

    def test_two_hour_scanner_charges_exact_retail_and_base_prices_without_item_loss(self):
        for modifier, unit_price in ((1, 150), (.9, 135)):
            self.rates['pmod'] = modifier
            for quantity in (1, 2):
                with self.subTest(modifier=modifier, quantity=quantity):
                    before = self.store.money(self.cid)
                    serials = {row['uniq'] for row in self.inv.rows()}
                    self.assertEqual(self.buy(3826, quantity), [inventory.RES_OK])
                    self.assertEqual(self.store.money(self.cid),
                                     (before[0], before[1] - unit_price * quantity))
                    bought = [row for row in self.inv.rows() if row['uniq'] not in serials]
                    self.assertEqual(len(bought), quantity)
                    self.assertTrue(all(row['type_id'] == 3826 and row['count'] == 1
                                        for row in bought))

    def test_every_supported_buff_preserves_quantity_charges_and_payment(self):
        checked = 0
        for type_id in effects.definitions():
            si = items.params_of(type_id)
            if items.root_of(type_id) != items.HEAL or not si:
                continue
            for gold in (False, True):
                if not si['g_cost' if gold else 'cost']:
                    continue
                checked += 1
                with self.subTest(type_id=type_id, gold=gold):
                    ids = {r['uniq'] for r in self.inv.rows()}
                    before = self.store.money(self.cid)
                    self.assertEqual(self.buy(type_id, 2, gold), [inventory.RES_OK])
                    new = [r for r in self.inv.rows() if r['uniq'] not in ids]
                    self.assertEqual(sum(r['count'] for r in new), 2)
                    self.assertTrue(all(r['use_count'] == si.get('use_count', 1) for r in new))
                    price = inventory.buy_price(si, items.HEAL, 2, gold, 1)
                    expected = list(before); expected[int(gold)] -= price
                    self.assertEqual(self.store.money(self.cid), tuple(expected))
        self.assertGreater(checked, 20)

    def test_two_sequential_single_gold_purchases_keep_both_buffs_separate(self):
        for type_id in effects.definitions():
            si = items.params_of(type_id)
            if items.root_of(type_id) != items.HEAL or not si or not si.get('g_cost'):
                continue
            with self.subTest(type_id=type_id):
                self.assertEqual(si['max_count'], 1)
                self.assertFalse(items.heapable(type_id))
                before_money = self.store.money(self.cid)
                before_ids = {row['uniq'] for row in self.inv.rows()}
                for expected in (1, 2):
                    self.assertEqual(self.buy(type_id, 1), [inventory.RES_OK])
                    rows = [row for row in self.inv.rows() if row['uniq'] not in before_ids]
                    self.assertEqual(len(rows), expected)
                    self.assertTrue(all(row['slot'] == inventory.BAG and row['count'] == 1 for row in rows))
                    self.assertEqual(self.store.money(self.cid)[1], before_money[1] - expected * si['g_cost'])
                    self.assertEqual(self.s.char.gold, self.store.money(self.cid)[1])


    def test_second_item_failure_rolls_back_first_item_money_and_ledger(self):
        afro_buff = next(t for t in effects.definitions() if items.params_of(t).get('cost'))
        for type_id, gold in ((3561, True), (3826, True), (afro_buff, False)):
            with self.subTest(type_id=type_id):
                before = self.store.money(self.cid)
                ledger = self.store.db.execute('SELECT COUNT(*) FROM money_ledger').fetchone()[0]
                create = self.store.create_item
                calls = []
                def fail_second(*args, **kwargs):
                    calls.append(1)
                    if len(calls) == 2:
                        raise RuntimeError('injected second buff failure')
                    return create(*args, **kwargs)
                with patch.object(self.store, 'create_item', side_effect=fail_second), \
                        patch.object(inventory.log, 'exception') as failure:
                    self.assertEqual(self.buy(type_id, 2, gold), [inventory.RES_REFUSED])
                failure.assert_called_once()
                self.assertEqual(len(calls), 2)
                self.assertEqual(self.store.money(self.cid), before)
                self.assertEqual((self.s.char.afro, self.s.char.gold), before)
                self.assertEqual(self.inv.rows(), [])
                self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM money_ledger').fetchone()[0], ledger)
                self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])

    def test_invalid_quantities_and_insufficient_funds_never_charge_or_deliver(self):
        before = self.store.money(self.cid)
        for n in (0, -1, 11, 1.5, True, None, '', 'bad'):
            self.assertEqual(self.buy(3561, n), [inventory.RES_REFUSED])
            self.assertEqual(self.store.money(self.cid), before)
            self.assertEqual(self.inv.rows(), [])
        for type_id in (3561, 3826):
            unit_price = items.params_of(type_id)['g_cost']
            self.store.set_money(self.cid, before[0], unit_price)
            self.assertEqual(self.buy(type_id, 2), [inventory.RES_NO_MONEY])
            self.assertEqual(self.inv.rows(), [])
            self.assertEqual(self.store.money(self.cid)[1], unit_price)

    def test_bulk_weight_is_checked_and_repeated_purchases_deliver_all_pieces(self):
        before = self.store.money(self.cid)
        with patch.object(self.inv, 'carry_limit', return_value=items.params_of(3561)['weight']):
            self.assertEqual(self.buy(3561, 2), [inventory.RES_OVERLOAD])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.inv.rows(), [])
        for _ in range(2):
            self.assertEqual(self.buy(3561, 2), [inventory.RES_OK])
        self.assertEqual(len(self.inv.rows()), 4)
        self.assertEqual(self.store.money(self.cid)[1], before[1] - 4 * items.params_of(3561)['g_cost'])


if __name__ == '__main__':
    run_cases(BuffPurchases)
