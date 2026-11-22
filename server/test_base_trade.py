"""Paid clan-base prices: native frames and actual atomic buy/sell/repair."""
import math
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_gold_commerce as fixtures
import gold_trade
import holdings
import inventory
import items
import mortimer
import progression
import protocol
import world
from testkit import run_cases


class BaseTrade(unittest.TestCase):
    give = fixtures.GoldCommerce.give
    sell = fixtures.GoldCommerce.sell
    quote = fixtures.GoldCommerce.quote
    confirmed = fixtures.GoldCommerce.confirmed

    def setUp(self):
        fixtures.GoldCommerce.setUp(self)
        self.site = holdings.site_at(609)
        self.assertIsNotNone(self.site)
        self.clan = self.store.clan_create(self.cid, 'BaseTrade', 'basetrade', '', None)
        self.store.holding_set(self.site.key, self.clan, 'admin', slot=1000, when=1000)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                              (1000 + 7 * 86400, self.site.key))
        self.store.db.commit()
        clock = patch.object(holdings.bosses, 'clock', return_value=2000)
        clock.start()
        self.addCleanup(clock.stop)
        self.s.loc = NS(id=609, width=20, height=20, spawns=[])
        self.s.room.loc = self.s.loc
        self.s.combat = NS(mob_info=lambda n: {}, after_npc_info=lambda n: None)
        self.store.set_money(self.cid, 50000000, 100000)
        self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
        self.open(714)

    def open(self, trader):
        self.s.room.npc = lambda n: (0, trader, world.TRADER) if n == 1 else None
        self.frames.clear()
        self.inv.open_trade(dict(target=1))
        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])

    def buy(self, type_id, n=1, gold=True):
        stock = items.stock_for(self.inv.trade.trader_type, self.inv.trade.loc_id)
        self.frames.clear()
        self.inv.buy(dict(obj=format(stock.index(type_id), 'x'), param=n),
                     inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def test_advertised_native_rates_and_real_purchase_match_every_quantity(self):
        info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
        self.assertEqual((info['pmod'], info['smod'], info['rmod']), (0.9, 0.85, inventory.RMOD * 0.5))
        self.assertLess(len(protocol.frame('userInfo_Trader', **info)), 4096)
        for trader, gold in ((714, True), (714, False), (1013, True), (1013, False)):
            self.open(trader)
            stock = items.stock_for(trader, 609)
            available = [t for t in stock if bool(items.params_of(t).get('g_cost')) == gold]
            t = available[0]
            for n in ((1, 20, 5000) if items.root_of(t) == items.AMMO else (1,)):
                before = self.store.money(self.cid)
                cost = inventory.buy_price(items.params_of(t), items.root_of(t), n, gold, 0.9)
                self.assertEqual(self.buy(t, n, gold), [0])
                after = self.store.money(self.cid)
                self.assertEqual(before[int(gold)] - after[int(gold)], cost)
                for row in self.inv.rows():
                    self.store.delete_item(row['uniq'])

    def test_only_paid_local_owner_and_explicit_trader_receive_benefits(self):
        self.assertEqual(inventory.trade_rates(self.store, 609, 714, self.cid)['smod'], 0.85)
        self.assertEqual(inventory.trade_rates(self.store, 609, 123, self.cid)['smod'], inventory.SMOD)
        self.assertEqual(inventory.trade_rates(self.store, 36, 714, self.cid)['smod'], inventory.SMOD)
        self.assertEqual(inventory.trade_rates(self.store, 609, 714, None)['smod'], inventory.SMOD)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=1500 WHERE site=?', (self.site.key,))
        self.store.db.commit()
        self.assertEqual(inventory.trade_rates(self.store, 609, 714, self.cid)['smod'], inventory.SMOD)

    def test_stimulants_and_scanner_use_gold_discount_and_gear_has_no_purchase_discount(self):
        self.open(1013)
        stock = items.stock_for(1013, 609)
        self.assertIn(3826, stock)
        self.assertIn(3561, stock)
        for t in (3826, 3561):
            before = self.store.money(self.cid)
            expected = math.ceil(items.params_of(t)['g_cost'] * 0.9)
            self.assertEqual(self.buy(t), [0])
            self.assertEqual(before[1] - self.store.money(self.cid)[1], expected)
            self.assertEqual(before[0], self.store.money(self.cid)[0])
        self.assertEqual(inventory.purchase_pmod(26075, self.inv.trade.rates), inventory.PMOD)
        self.assertEqual(inventory.repair_rmod(self.site.loc, self.site.flag), inventory.RMOD)

    def test_changed_membership_or_expired_rent_refuses_stale_window_without_payment(self):
        ammo = next(t for t in items.stock_for(714, 609) if items.root_of(t) == items.AMMO and items.params_of(t).get('g_cost'))
        before = self.store.money(self.cid)
        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
        self.store.db.commit()
        self.assertEqual(self.buy(ammo, 20), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(self.inv.rows())
        # A new ordinary window can be used at ordinary prices.
        self.open(714)
        self.assertEqual(self.inv.trade.rates['pmod'], inventory.PMOD)
        self.assertEqual(self.buy(ammo, 20), [0])

    def test_membership_change_cannot_keep_high_quoted_buyback(self):
        row = self.give(26075)
        p, q = self.quote(row)
        self.assertEqual(q['res'], 0)
        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
        self.store.db.commit()
        before = self.store.money(self.cid)
        self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertIsNotNone(self.store.item(row['uniq']))

    def test_rent_expiry_refuses_buy_repair_and_confirmed_sale(self):
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=100)
        row = self.store.item(row['uniq'])
        p, q = self.quote(row)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=1500 WHERE site=?', (self.site.key,))
        self.store.db.commit()
        before = self.store.money(self.cid)
        self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        self.frames.clear()
        self.inv.repair(dict(obj=inventory.oid_of(row)), inventory.UPD_REPAIR)
        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.item(row['uniq']), row)

    def test_repair_halves_only_ordinary_price_and_retains_ceiling_loss(self):
        for code, money_index in ((inventory.UPD_REPAIR, 0), (inventory.UPD_REPAIR_GOLD, 1)):
            row = self.give(25636)
            self.store.update_item(row['uniq'], brk=0)
            row = self.store.item(row['uniq'])
            p = items.params_of(row['type_id'])
            price = inventory.repair_prices(p, row['brk'], row['max_break_cur'], inventory.RMOD * 0.5)[money_index]
            before = self.store.money(self.cid)
            self.frames.clear()
            self.inv.repair(dict(obj=inventory.oid_of(row)), code)
            self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
            self.assertEqual(before[money_index] - self.store.money(self.cid)[money_index], price)
            repaired = self.store.item(row['uniq'])
            self.assertEqual(repaired['max_break_cur'], math.floor(row['max_break_cur'] * inventory.REPAIR_KEEPS))
            self.assertEqual(repaired['brk'], repaired['max_break_cur'])

    def test_resale_uses_factory_wear_and_remaining_doses_with_old_blueprint_caps(self):
        for t in (25586, 26075, 37679, 37645):
            row = self.give(t)
            p = items.params_of(t)
            if row['root'] in items.BREAKABLE_ROOTS:
                self.store.update_item(row['uniq'], brk=row['max_break_cur'] // 2)
                row = self.store.item(row['uniq'])
            before = self.store.money(self.cid)
            quality = gold_trade.sale_quality(row, p)
            if gold_trade.gold_priced(t, p):
                unit = gold_trade.sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
                request, quote = self.quote(row)
                self.assertEqual(quote['price'], max(1, math.floor(unit * quality)))
                self.assertEqual(self.confirmed(request, quote), 0)
            else:
                unit = gold_trade.afro_sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
                if not unit:
                    unit = p['cost'] * 0.85 * p.get('sell_mod', 1) / (p.get('sell_num') or 1)
                cap = gold_trade.afro_sale_cap(t, p)
                if cap:
                    unit = min(unit, cap)
                self.assertEqual(self.sell(row, 1), 0)
            self.assertEqual(self.store.money(self.cid)[0] - before[0], max(1, math.floor(unit * quality)))
        heal = next(t for t in items.stock_for(1013, 609)
                    if items.root_of(t) == items.HEAL and items.params_of(t).get('use_count', 0) > 1)
        row = self.give(heal)
        self.store.update_item(row['uniq'], use_count=1)
        request, quote = self.quote(self.store.item(row['uniq']))
        expected = math.floor(gold_trade.sale_unit(heal, items.params_of(heal), gold_trade.BASE_SALE_SHARE)
                              / items.params_of(heal)['use_count'])
        self.assertEqual(quote['price'], max(1, expected))
        self.assertEqual(self.confirmed(request, quote), 0)

    def test_forged_index_serial_and_absent_npc_cannot_buy_or_keep_base_tariff(self):
        before = self.store.money(self.cid)
        for obj in ('ffff', 'ffffffff', 'not-a-number'):
            self.frames.clear()
            self.inv.buy(dict(obj=obj, param=20), inventory.UPD_BUY_GOLD)
            self.assertEqual(len([p for cmd, p in self.frames if cmd == 'cmdAck']), 1)
            self.assertNotEqual(self.frames[0][1]['res'], 0)
        self.s.room.npc = lambda n: None
        t = next(t for t in items.stock_for(714, 609) if items.root_of(t) == items.AMMO)
        self.assertEqual(self.buy(t, 20), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(self.inv.rows())

    def test_base_stock_is_city_consumables_only_without_duplicates_or_client_overflow(self):
        for loc, traders in ((609, (714, 1013)), (1443, (1013, 5240))):
            stocks = [items.stock_for(t, loc) for t in traders]
            self.assertFalse(set(stocks[0]) & set(stocks[1]))
            for trader, stock in zip(traders, stocks):
                self.assertTrue(stock)
                self.assertLessEqual(len(stock), 64)
                self.assertEqual(len(stock), len(set(stock)))
                for t in stock:
                    self.assertIn(items.root_of(t), (items.AMMO, items.HEAL))
                    self.assertFalse(gold_trade.protected(t, items.params_of(t)))
                    self.assertNotIn(t, items.DISCOUNT_AMMO_COUPONS)

    def test_all_base_stock_buy_resale_and_repair_sale_routes_are_unprofitable(self):
        rate = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE
        checked = 0
        for loc, traders in ((609, (714, 1013)), (1443, (1013, 5240))):
            for trader in traders:
                for t in items.stock_for(trader, loc):
                    p, root = items.params_of(t), items.root_of(t)
                    ns = (1, 2, 20, 100, 999, 5000) if root == items.AMMO else (1,)
                    if gold_trade.gold_priced(t, p):
                        unit = gold_trade.sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
                    else:
                        unit = p['cost'] * 0.85 * p.get('sell_mod', 1) / (p.get('sell_num') or 1)
                    for n in ns:
                        for gold, key in ((False, 'cost'), (True, 'g_cost')):
                            if p.get(key, 0) <= 0:
                                continue
                            cost = inventory.buy_price(p, root, n, gold, 0.9)
                            value = cost * (rate if gold else 1)
                            self.assertLessEqual(max(1, math.floor(unit * n)), value, (t, n, key))
                            self.assertLessEqual(n * max(1, math.floor(unit)), value, (t, n, key, 'split'))
                            checked += 1
        self.assertGreater(checked, 500)
        # A repair can make damaged loot worth more. It cannot turn a
        # purchase/wear/repair/resale cycle into a profit or restore the ceiling.
        for t in (25586, 25636, 26075):
            p = items.params_of(t)
            unit = (gold_trade.sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
                    if gold_trade.gold_priced(t, p) else gold_trade.afro_sale_unit(t, p, gold_trade.BASE_SALE_SHARE))
            factory = p['max_break_abs']
            for wear in (0.1, 0.5, 0.9):
                brk = int(factory * wear)
                top = max(math.floor(factory * inventory.REPAIR_KEEPS), brk)
                repair = inventory.repair_prices(p, brk, factory, inventory.RMOD * 0.5)[0]
                resale = math.floor(unit * top / factory)
                buying_gold = not p.get('cost')
                bought = inventory.buy_price(p, items.root_of(t), 1, buying_gold)
                bought *= rate if buying_gold else 1
                self.assertLessEqual(resale - repair, bought, (t, wear, resale, repair, bought))
                self.assertLess(top, factory)

    def test_repeated_real_bulk_purchase_and_single_piece_sales_do_not_create_money(self):
        rate = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE
        for trader, gold in ((714, False), (714, True)):
            self.open(trader)
            t = next(t for t in items.stock_for(trader, 609) if items.root_of(t) == items.AMMO and bool(items.params_of(t).get('g_cost')) == gold)
            for _ in range(3):
                before = self.store.money(self.cid)
                self.assertEqual(self.buy(t, 20, gold), [0])
                row = next(row for row in self.inv.rows() if row['type_id'] == t)
                for _ in range(20):
                    if gold:
                        p, q = self.quote(self.store.item(row['uniq']), 1)
                        self.assertEqual(self.confirmed(p, q), 0)
                    else:
                        self.assertEqual(self.sell(row, 1), 0)
                after = self.store.money(self.cid)
                self.assertLessEqual(after[0] + after[1] * rate, before[0] + before[1] * rate)
                self.assertIsNone(self.store.item(row['uniq']))

    def test_five_gold_valuables_pay_gold_once_and_keep_remaining_stack(self):
        prices = {6950: 4, 6951: 5, 6952: 5, 6953: 5, 6959: 7}
        self.assertEqual({t: gold_trade.base_loot_gold(t) for t in mortimer.VALUABLES}, prices)
        self.assertTrue(next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')['base_gold_buyer'])
        for t, unit in prices.items():
            row = self.give(t, 5)
            before = self.store.money(self.cid)
            p, q = self.quote(row, 2)
            self.assertEqual((q['res'], q['price'], q['currency']), (0, unit * 2, 1))
            self.assertNotIn('eden_sale', q)
            self.s.char.gold = 999999999
            self.assertEqual(self.confirmed(p, q), 0)
            self.assertEqual(self.store.money(self.cid), (before[0], before[1] + unit * 2))
            self.assertEqual(self.store.item(row['uniq'])['count'], 3)
            self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
            p, q = self.quote(self.store.item(row['uniq']), 3)
            self.assertEqual(self.confirmed(p, q), 0)
            self.assertEqual(self.store.money(self.cid), (before[0], before[1] + unit * 5))
            self.assertIsNone(self.store.item(row['uniq']))

    def test_gold_valuable_quote_loses_rights_when_membership_or_lease_changes(self):
        row = self.give(6951, 5)
        p, q = self.quote(row, 2)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=1500 WHERE site=?', (self.site.key,))
        self.store.db.commit()
        before = self.store.money(self.cid)
        self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.item(row['uniq'])['count'], 5)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                              (1000 + 7 * 86400, self.site.key))
        self.store.db.commit()
        p, q = self.quote(row, 2)
        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
        self.store.db.commit()
        self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.item(row['uniq'])['count'], 5)

    def test_gold_valuable_quotes_refuse_wrong_trader_and_failed_payment_rolls_back(self):
        row = self.give(6950, 5)
        self.open(1013)
        _, q = self.quote(row, 2)
        self.assertNotEqual(q['res'], 0)
        self.open(714)
        p, q = self.quote(row, 2)
        before = self.store.money(self.cid)
        with patch.object(self.store, 'set_money', side_effect=RuntimeError('injected')):
            self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.item(row['uniq'])['count'], 5)
        self.assertEqual(self.confirmed(p, q), inventory.RES_REFUSED)
        p, q = self.quote(row, 2)
        self.assertEqual(self.confirmed(p, q), 0)
        self.assertEqual(self.store.money(self.cid)[1], before[1] + 8)

    def test_gold_loot_excludes_sand_ingots_and_quest_bags_and_has_no_retail_source(self):
        from test_shop_prices import stock_types
        self.assertFalse(mortimer.VALUABLES & stock_types())
        for t in (2258, 7620, 4796, 4797, 1305, 1306):
            self.assertEqual(gold_trade.base_loot_gold(t), 0)
            row = self.give(t)
            _, q = self.quote(row)
            self.assertNotEqual(q.get('currency'), 1)

    def test_dongola_gold_supplier_uses_its_actual_paid_base_and_same_gold_buyback(self):
        self.store.holding_clear(self.site.key, 'admin')
        site = holdings.site_at(1443)
        self.store.holding_set(site.key, self.clan, 'admin', slot=1000, when=1000)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                              (1000 + 7 * 86400, site.key))
        self.store.db.commit()
        self.s.loc = NS(id=1443, width=20, height=20, spawns=[])
        self.s.room.loc = self.s.loc
        self.open(5240)
        row = self.give(6950)
        before = self.store.money(self.cid)
        p, q = self.quote(row)
        self.assertEqual((q['price'], q['currency']), (4, 1))
        self.assertEqual(self.confirmed(p, q), 0)
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 4))


if __name__ == '__main__':
    run_cases(BaseTrade)
