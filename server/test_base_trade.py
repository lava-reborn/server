"""Paid clan-base prices: native frames and actual atomic buy/sell/repair."""
import math
import time
import unittest
from datetime import datetime
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
import effects
import world
from testkit import run_cases


class BaseTrade(unittest.TestCase):
    give = fixtures.GoldCommerce.give
    sell = fixtures.GoldCommerce.sell
    quote = fixtures.GoldCommerce.quote
    confirmed = fixtures.GoldCommerce.confirmed

    def foreign_clan(self):
        aid, _ = self.store.register('base-outsider', 'local-only')
        head, _ = self.store.create_character(aid, 'BaseOutsider', 0, '1')
        return self.store.clan_create(head, 'Other base clan', 'other-base-clan', '', None)

    def test_service_access_matrix_for_every_base_npc_and_lease_boundaries(self):
        other = self.foreign_clan()
        slot = datetime(2026, 11, 21, 20, tzinfo=holdings.bosses.ZONE).timestamp()
        week = 7 * 86400
        # State, holding slot, paid-until, current time, services, benefits.
        states = (
            ('paid', slot, slot + week - 300, slot + 1800, True, True),
            ('reservation', slot, 0, slot + 1800, False, False),
            ('neutral', None, 0, slot + 1800, False, False),
            ('expired', slot, slot + 1799, slot + 1800, False, False),
            ('expiry-boundary', slot, slot + 1800, slot + 1800, False, False),
            ('payment-deadline', slot, 0, slot + 4500, False, False),
            ('old-reservation', slot - week, 0, slot + 1800, False, False),
            ('future-lease', slot + week, slot + 2 * week - 300, slot + 1800, False, False),
            ('invalid-lease', slot, slot + week + 1, slot + 1800, False, False),
            ('weekly-reset', slot, slot + week, slot + week - 300, False, False),
        )
        for loc in (609, 1443):
            self.base_room(loc)
            for state, held_slot, until, now, services, benefits in states:
                self.store.holding_clear(self.site.key, 'admin')
                if held_slot is not None:
                    self.store.holding_set(self.site.key, self.clan, 'admin', slot=held_slot, when=slot)
                    self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                                          (until, self.site.key))
                    self.store.db.commit()
                for member in ('owner', 'foreign', 'none'):
                    self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                    self.store.db.commit()
                    if member != 'none':
                        self.store.clan_member_add(self.cid, self.clan if member == 'owner' else other, 0, '')
                    for trader in self.site.traders:
                        with self.subTest(location=loc, state=state, member=member, trader=trader), \
                                patch.object(holdings.bosses, 'clock', return_value=now):
                            allowed = services and member == 'owner'
                            self.s.room.npc = lambda n, t=trader: (0, t, world.TRADER) if n == 1 else None
                            self.frames.clear()
                            self.s.send_npc_info(1)
                            info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
                            self.assertEqual(info['can_trade'], int(allowed))
                            self.assertEqual(info['can_repair'], int(allowed and trader == 989))
                            if not allowed:
                                self.assertEqual(info['type_list'], [])
                            self.frames.clear()
                            self.inv.open_trade(dict(target=1))
                            self.assertEqual(self.frames[-1], ('cmdAck', dict(
                                res=0 if allowed else inventory.RES_REFUSED)))
                            if allowed:
                                rates = self.inv.current_trade_rates()
                                self.assertIsNotNone(rates)
                                self.assertEqual(rates['pmod'], .9 if benefits else inventory.PMOD)
                            else:
                                self.assertIsNone(self.inv.trade)
                            self.assertFalse(holdings.may_serve(self.store, loc, trader, None))

    def test_all_mutations_refuse_lost_rights_with_no_money_or_item_changes(self):
        other = self.foreign_clan()
        self.inv.carry_limit = lambda: 1_000_000
        for loc in (609, 1443):
            for change in ('leave', 'other-clan', 'new-owner', 'neutral', 'expiry'):
                self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                self.store.db.commit()
                self.store.clan_member_add(self.cid, self.clan, 0, '')
                self.base_room(loc)
                for trader in self.site.traders:
                    # Restore rights before opening each real NPC, then revoke
                    # them after its sale quote, as with an already open client.
                    self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                    self.store.db.commit()
                    self.store.clan_member_add(self.cid, self.clan, 0, '')
                    self.base_room(loc)
                    self.open(trader)
                    gear, ammo, worn = self.give(26075), self.give(6164, 5), self.give(25636)
                    self.store.update_item(worn['uniq'], brk=0, max_break_cur=worn['max_break_cur'] // 2)
                    request, quote = self.quote(gear)
                    self.assertEqual(quote['res'], 0)
                    if change in ('leave', 'other-clan'):
                        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                        self.store.db.commit()
                        if change == 'other-clan':
                            self.store.clan_member_add(self.cid, other, 0, '')
                    elif change == 'new-owner':
                        self.store.holding_set(self.site.key, other, 'admin', slot=1000, when=1000)
                        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                                              (1000 + 7 * 86400, self.site.key))
                        self.store.db.commit()
                    elif change == 'neutral':
                        self.store.holding_clear(self.site.key, 'admin')
                    else:
                        self.store.db.execute('UPDATE clan_holdings SET paid_until=1500 WHERE site=?', (self.site.key,))
                        self.store.db.commit()
                    before = (self.store.money(self.cid), list(self.inv.rows()))
                    operations = [
                        ('confirmed-sale', lambda: self.confirmed(request, quote)),
                        ('new-quote', lambda: self.quote(gear)),
                        ('afro-sale', lambda: self.sell(ammo, 1)),
                        ('repair-afro', lambda: self.inv.repair(dict(obj=inventory.oid_of(worn)), inventory.UPD_REPAIR)),
                        ('repair-gold', lambda: self.inv.repair(dict(obj=inventory.oid_of(worn)), inventory.UPD_REPAIR_GOLD)),
                        ('restore', lambda: self.inv.restore(dict(obj=inventory.oid_of(worn)))),
                    ]
                    stock = items.stock_for(trader, loc)
                    for gold in (False, True):
                        kind = next((t for t in stock if bool(items.params_of(t).get('g_cost')) == gold), None)
                        if kind is not None:
                            operations.append(('buy-gold' if gold else 'buy-afro',
                                               lambda t=kind, g=gold: self.buy(t, 1, g)))
                    for operation, call in operations:
                        with self.subTest(location=loc, trader=trader, change=change, operation=operation):
                            self.frames.clear()
                            call()
                            acks = [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']
                            self.assertEqual(acks, [inventory.RES_REFUSED])
                            self.assertEqual((self.store.money(self.cid), list(self.inv.rows())), before)

    def test_all_bunker_services_reject_nonmembers_and_stale_windows_in_both_bases(self):
        for loc in (609, 1443):
            self.base_room(loc)
            for trader in self.site.traders:
                with self.subTest(location=loc, trader=trader):
                    self.open(trader)
                    self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
                    self.store.db.commit()
                    before = (self.store.money(self.cid), list(self.inv.rows()))
                    self.assertIsNone(self.inv.current_trade_rates())
                    self.frames.clear()
                    self.s.send_npc_info(1)
                    info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
                    self.assertEqual((info['can_trade'], info['can_repair'], info['type_list']), (0, 0, []))
                    self.frames.clear()
                    self.inv.open_trade(dict(target=1))
                    self.assertEqual(self.frames[-1], ('cmdAck', dict(res=inventory.RES_REFUSED)))
                    self.assertIsNone(self.inv.trade)
                    self.assertEqual((self.store.money(self.cid), list(self.inv.rows())), before)
                    self.store.clan_member_add(self.cid, self.clan, 0x8000, '')
                    self.open(trader)

    def test_minimum_purchase_cut_is_one_afro_or_cent_and_never_free(self):
        for gold in (False, True):
            for root in (items.AMMO, items.HEAL):
                for unit, expected in ((1, 1), (2, 1), (4, 3), (9, 8), (10, 9), (13, 12), (100, 90)):
                    si = dict(cost=unit, g_cost=unit, sell_num=1)
                    for count in (1, 2, 10, 5000):
                        self.assertEqual(inventory.buy_price(si, root, count, gold, .9), expected * count)
                        self.assertEqual(inventory.buy_price(si, root, count, gold), unit * count)

    def test_minimum_unit_discounts_cannot_fund_resale_at_any_buyer(self):
        rate = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE
        for tid, gold in ((6116, False), (6164, True), (6055, False), (7100, True)):
            params = dict(items.params_of(tid), cost=0 if gold else 2,
                          g_cost=2 if gold else 0, sell_num=1, sell_mod=1)
            prices = []
            for share in (gold_trade.NPC_SALE_SHARE, gold_trade.BASE_SALE_SHARE):
                unit = (gold_trade.sale_unit(tid, params, share) if gold else
                        gold_trade.afro_sale_unit(tid, params, share))
                prices.append(unit)
                for count in (1, 2, 10, 5000):
                    paid = inventory.buy_price(params, items.root_of(tid), count, gold, .9)
                    paid *= rate if gold else 1
                    self.assertLessEqual(max(1, math.floor(unit * count)), paid)
                    self.assertLessEqual(count * max(1, math.floor(unit)), paid)
            self.assertGreaterEqual(prices[1], prices[0])

    def test_safe_resale_below_the_discounted_purchase_price_is_unchanged(self):
        params = dict(items.params_of(6116), cost=6, g_cost=0, sell_num=1, sell_mod=1)
        self.assertEqual(gold_trade.afro_sale_unit(6116, params), 4.2)
        self.assertEqual(gold_trade.afro_sale_unit(6116, params, gold_trade.BASE_SALE_SHARE), 5)

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
        for trader, gold in ((714, True), (714, False), (1013, True), (2018, False)):
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

    def test_two_hour_scanner_costs_135_cents_per_piece_at_both_paid_bases(self):
        for location in (609, 1443):
            self.base_room(location)
            self.open(1013)
            for quantity in (1, 2):
                with self.subTest(location=location, quantity=quantity):
                    before = self.store.money(self.cid)
                    serials = {row['uniq'] for row in self.inv.rows()}
                    self.assertEqual(self.buy(3826, quantity), [inventory.RES_OK])
                    self.assertEqual(self.store.money(self.cid),
                                     (before[0], before[1] - 135 * quantity))
                    bought = [row for row in self.inv.rows() if row['uniq'] not in serials]
                    self.assertEqual(len(bought), quantity)
                    self.assertTrue(all(row['type_id'] == 3826 and row['count'] == 1
                                        for row in bought))

    def test_changed_membership_or_expired_rent_refuses_stale_window_without_payment(self):
        ammo = next(t for t in items.stock_for(714, 609) if items.root_of(t) == items.AMMO and items.params_of(t).get('g_cost'))
        before = self.store.money(self.cid)
        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
        self.store.db.commit()
        self.assertEqual(self.buy(ammo, 20), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(self.inv.rows())
        # Reopening must not bypass the owner-only service gate.
        self.frames.clear()
        self.inv.open_trade(dict(target=1))
        self.assertEqual(self.frames[-1], ('cmdAck', dict(res=inventory.RES_REFUSED)))
        self.assertIsNone(self.inv.trade)
        self.assertEqual(self.store.money(self.cid), before)

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
        self.open(989)
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
        self.open(989)
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

    def base_room(self, loc):
        for key in holdings.base_keys():
            self.store.holding_clear(key, 'admin')
        self.site = holdings.site_at(loc)
        self.store.holding_set(self.site.key, self.clan, 'admin', slot=1000, when=1000)
        self.store.db.execute('UPDATE clan_holdings SET paid_until=? WHERE site=?',
                              (1000 + 7 * 86400, self.site.key))
        self.store.db.commit()
        self.s.loc = NS(id=loc, width=20, height=20, spawns=[])
        self.s.room.loc = self.s.loc

    def test_every_a_g_base_consumable_wire_purchase_uses_advertised_discount(self):
        self.inv.carry_limit = lambda: 1_000_000
        checked = 0
        categories = set()
        for loc, supplier in ((609, 714), (1443, 5240)):
            self.base_room(loc)
            self.store.set_money(self.cid, 1_000_000_000, 1_000_000)
            self.s.char.afro, self.s.char.gold = self.store.money(self.cid)
            for trader in (supplier, 1013, 2018):
                self.open(trader)
                info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
                stock = items.stock_for(trader, loc)
                name, sent = protocol.decode(protocol.encode('userInfo_Trader', **info))
                self.assertEqual(name, 'userInfo_Trader')
                self.assertEqual(sent['type_list'], stock)
                self.assertEqual((sent['pmod'], sent['smod']), (.9, .85))
                for index, type_id in enumerate(stock):
                    params = items.params_of(type_id)
                    gold = bool(params.get('g_cost'))
                    root = items.root_of(type_id)
                    category = ('ammo' if root == items.AMMO else
                                'buff' if effects.definition(type_id) else 'medicine')
                    categories.add((loc, category, gold))
                    counts = (1, 7, 100, 5000) if root == items.AMMO else (
                        (1, 10) if items.heapable(type_id) else (1,))
                    for n in counts:
                        unit = params['g_cost'] if gold else params['cost']
                        unit /= params.get('sell_num', 1) or 1
                        if root == items.AMMO:
                            precision = 1 if gold else 1000
                            unit = math.floor(unit * precision + .5) / precision
                        expected = max(1, min(math.ceil(unit * .9), math.ceil(unit) - 1)) * n
                        before = self.store.money(self.cid)
                        self.frames.clear()
                        command, request = protocol.decode(protocol.encode('ss_upd',
                            s_status=inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY,
                            obj=protocol.BigUInt(format(index, 'x')), param=n))
                        self.assertEqual(command, 'ss_upd')
                        self.assertTrue(self.inv.ss_upd(request))
                        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0],
                                         (loc, trader, type_id, n))
                        after = self.store.money(self.cid)
                        self.assertEqual(before[int(gold)] - after[int(gold)], expected)
                        self.assertEqual(before[int(not gold)], after[int(not gold)])
                        if gold:
                            self.assertGreater(expected, 0)
                            if root != items.AMMO and unit > 1:
                                self.assertLessEqual(expected, math.ceil(unit * n) - 1)
                        for row in self.inv.rows():
                            self.store.delete_item(row['uniq'])
                        checked += 1
        self.assertEqual(categories, {(loc, kind, gold) for loc in (609, 1443)
                                     for kind in ('ammo', 'medicine', 'buff') for gold in (False, True)})
        self.assertGreater(checked, 500)

    def test_only_dedicated_base_repairer_advertises_and_accepts_repairs(self):
        for loc, supplier in ((609, 714), (1443, 5240)):
            self.base_room(loc)
            row = self.give(25636)
            self.store.update_item(row['uniq'], brk=0)
            row = self.store.item(row['uniq'])
            before = self.store.money(self.cid)
            for trader in (supplier, 1013, 2018):
                self.open(trader)
                info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
                self.assertEqual(info['can_repair'], 0)
                for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE):
                    self.frames.clear()
                    self.inv.repair(dict(obj=inventory.oid_of(row)), code)
                    self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'],
                                     [inventory.RES_REFUSED])
                    self.assertEqual(self.store.item(row['uniq']), row)
                    self.assertEqual(self.store.money(self.cid), before)
            self.open(989)
            info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
            self.assertEqual((info['can_repair'], info['rmod']), (1, inventory.RMOD * .5))
            for code, currency in ((inventory.UPD_REPAIR, 0), (inventory.UPD_REPAIR_GOLD, 1)):
                self.store.update_item(row['uniq'], brk=0, max_break_cur=row['max_break_cur'])
                before = self.store.money(self.cid)
                expected = inventory.repair_prices(items.params_of(row['type_id']), 0,
                                                   row['max_break_cur'], inventory.RMOD * .5)[currency]
                self.frames.clear()
                self.inv.repair(dict(obj=inventory.oid_of(row)), code)
                self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [0])
                self.assertEqual(before[currency] - self.store.money(self.cid)[currency], expected)

    def test_nonowner_base_repair_window_cannot_use_an_absent_or_different_npc(self):
        self.open(989)
        self.store.db.execute('DELETE FROM clan_members WHERE char_id=?', (self.cid,))
        self.store.db.commit()
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=0, max_break_cur=row['max_break_cur'] // 2)
        before = (self.store.money(self.cid), self.store.item(row['uniq']))
        self.s.room.npc = lambda _npc: None
        for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE):
            self.frames.clear()
            self.inv.repair(dict(obj=inventory.oid_of(row)), code)
            self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [inventory.RES_REFUSED])
            self.assertEqual((self.store.money(self.cid), self.store.item(row['uniq'])), before)
        self.frames.clear()
        self.inv.restore(dict(obj=inventory.oid_of(row)))
        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [inventory.RES_REFUSED])
        self.assertEqual((self.store.money(self.cid), self.store.item(row['uniq'])), before)

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

    def test_base_medics_split_all_released_buffs_and_every_battle_medicine_tier(self):
        import shop_bands
        expected_buffs = set().union(*(shop_bands.stimulants(top) for top in shop_bands.BUFF_RANKS))
        expected_meds = {t for t, ware in shop_bands.wares().items() if ware[0] == 'combat_meds'}
        self.assertEqual(len(expected_buffs), 78)
        for loc in (609, 1443):
            stocks = {trader: set(items.stock_for(trader, loc)) for trader in (1013, 2018)}
            self.assertFalse(stocks[1013] & stocks[2018])
            combined = stocks[1013] | stocks[2018]
            self.assertEqual({t for t in combined if effects.definition(t)}, expected_buffs)
            self.assertEqual({t for t in combined if t in expected_meds}, expected_meds)
            for trader, gold in ((1013, True), (2018, False)):
                self.assertTrue(all(bool(items.params_of(t).get('g_cost')) == gold
                                    for t in stocks[trader]))
            self.assertNotIn(3914, combined)  # Event food is not a released retail stimulant.

    def test_both_base_medics_stock_all_requested_grades_and_exact_discounted_prices(self):
        expected = set(range(4917, 4957)) | {3789, 3826, 3897, 4181, 4182, 4183, 4184, 4185}
        for loc in (609, 1443):
            with self.subTest(location=loc):
                stock = items.stock_for(1013, loc) + items.stock_for(2018, loc)
                self.assertTrue(expected <= set(stock), sorted(expected - set(stock)))
                self.assertEqual(len(stock), len(set(stock)))
                self.assertLess(len(stock), 256)
                for tid, gold, cost in ((3789, True, 45), (3826, True, 135),
                                        (4181, False, 2250),
                                        (4917, False, 450), (4937, False, 450),
                                        (4919, True, 7), (4939, True, 7),
                                        (4936, True, 198), (4956, True, 198)):
                    self.assertEqual(inventory.buy_price(items.params_of(tid), items.HEAL, 1, gold, .9), cost)
                self.assertNotIn(4917, items.stock_for(1013, 127))
                self.assertNotIn(4956, items.stock_for(1013, 36))

    def test_base_stock_is_consumables_only_without_duplicates_or_client_overflow(self):
        for loc, traders in ((609, (714, 1013, 2018)), (1443, (1013, 2018, 5240))):
            stocks = [items.stock_for(t, loc) for t in traders]
            self.assertEqual(sum(map(len, stocks)), len(set().union(*map(set, stocks))))
            for trader, stock in zip(traders, stocks):
                self.assertTrue(stock)
                self.assertLess(len(stock), 256)  # Native trader index is one byte.
                self.assertEqual(len(stock), len(set(stock)))
                for t in stock:
                    self.assertIn(items.root_of(t), (items.AMMO, items.HEAL))
                    self.assertFalse(gold_trade.protected(t, items.params_of(t)))
                    self.assertNotIn(t, items.DISCOUNT_AMMO_COUPONS)

    def test_all_base_stock_buy_resale_and_repair_sale_routes_are_unprofitable(self):
        rate = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE
        checked = 0
        for loc, traders in ((609, (714, 1013, 2018)), (1443, (1013, 2018, 5240))):
            for trader in traders:
                for t in items.stock_for(trader, loc):
                    p, root = items.params_of(t), items.root_of(t)
                    ns = (1, 2, 20, 100, 999, 5000) if root == items.AMMO else (1,)
                    if gold_trade.gold_priced(t, p):
                        unit = gold_trade.sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
                    else:
                        unit = gold_trade.afro_sale_unit(t, p, gold_trade.BASE_SALE_SHARE)
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
            candidates = [t for t in items.stock_for(trader, 609) if items.root_of(t) == items.AMMO
                          and bool(items.params_of(t).get('g_cost')) == gold]
            t = max(candidates, key=lambda t: inventory.buy_price(items.params_of(t), items.AMMO, 1, gold)
                    / inventory.buy_price(items.params_of(t), items.AMMO, 1, gold, .9))
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

    def test_gold_valuables_are_refused_by_every_trader_on_both_paid_bases(self):
        for loc_id in (609, 1443):
            self.base_room(loc_id)
            for trader in self.site.traders:
                self.open(trader)
                info = next(p for cmd, p in self.frames if cmd == 'userInfo_Trader')
                self.assertFalse(info.get('base_gold_buyer'))
                for type_id in mortimer.VALUABLES:
                    row = self.give(type_id, 5)
                    before = self.store.money(self.cid), list(self.inv.rows())
                    request, quote = self.quote(row, 2)
                    self.assertEqual(quote['res'], inventory.RES_REFUSED)
                    self.assertEqual(self.confirmed(request, quote), inventory.RES_REFUSED)
                    self.assertEqual((self.store.money(self.cid), list(self.inv.rows())), before)

    def test_old_gold_quote_cannot_be_confirmed_after_exchange_is_removed(self):
        row = self.give(6950, 5)
        before = self.store.money(self.cid), list(self.inv.rows())
        self.inv.trade.sale_quote = dict(token='old-quote', expires=time.monotonic() + 60,
                                        row=row, n=2, price=8, gold=True)
        request = dict(obj=inventory.oid_of(row), param=2)
        for _ in range(2):
            self.assertEqual(self.confirmed(request, dict(token='old-quote')), inventory.RES_REFUSED)
            self.assertEqual((self.store.money(self.cid), list(self.inv.rows())), before)

    def test_valuables_remain_sellable_only_to_mortimer_at_original_price(self):
        self.s.loc = NS(id=36, width=20, height=20, spawns=[])
        self.s.room.loc = self.s.loc
        self.open(1188)
        for type_id in mortimer.VALUABLES:
            row = self.give(type_id, 5)
            before = self.store.money(self.cid)
            self.assertEqual(self.sell(row, 2), inventory.RES_OK)
            self.assertEqual(self.store.money(self.cid),
                             (before[0], before[1] + 2 * mortimer.unit_gold(type_id)))
            self.assertEqual(self.store.item(row['uniq'])['count'], 3)
            self.assertEqual(gold_trade.client_fields(type_id)['mortimer_only'], 1)
        for type_id in (2258, 7620, 4796, 4797, 1305, 1306):
            self.assertEqual(gold_trade.client_fields(type_id)['mortimer_only'], 0)


if __name__ == '__main__':
    run_cases(BaseTrade)
