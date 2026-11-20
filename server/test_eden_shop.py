"""The Eden counter uses real shop handlers and isolated SQLite money rows."""
from fractions import Fraction
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import patch
import unittest

import test_mortimer_sales as fixtures
import eden
import eden_shop
import gold_trade
import inventory
import items
import server
import storage
import world
from testkit import run_cases


class EdenShopTests(unittest.TestCase):
    give = fixtures.MortimerSales.give

    def setUp(self):
        fixtures.MortimerSales.setUp(self)
        self.s.loc = world.location(eden.CENTER)
        self.s.pos = 7060
        self.s.live_cell = lambda: self.s.pos
        self.s.on_map = False
        self.s.room = NS(loc=self.s.loc, npc=lambda n: (7060, eden_shop.NPC_TYPE, world.TRADER))
        self.s.combat = NS(mob_info=lambda n: {}, after_npc_info=lambda n: None)
        self.s.eden_sentence = eden.assign(self.store, self.cid, 'test', 'Counter regression')
        self.inv.trade = inventory.TradeSession(1, eden_shop.NPC_TYPE, eden.CENTER)

    def quote(self, row, n=1, obj=None):
        p = dict(obj=obj or inventory.oid_of(row), param=n)
        self.frames.clear()
        self.inv.ss_upd(dict(p, s_status=2, sale_stage='quote'))
        acks = [p for cmd, p in self.frames if cmd == 'cmdAck']
        self.assertEqual(len(acks), 1)
        return p, acks[0]

    def confirm(self, p, quote):
        self.frames.clear()
        self.inv.ss_upd(dict(p, s_status=2, sale_token=quote.get('token'), confirmation='ПРОДАТЬ'))
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def state(self):
        return self.store.money(self.cid), self.inv.rows()

    def test_nominal_gear_uses_native_currency_factory_wear_and_single_payment(self):
        for type_id, gold in ((25636, False), (26075, True)):
            row = self.give(type_id)
            factory = items.params_of(type_id)['max_break_abs']
            self.store.update_item(row['uniq'], brk=factory // 4, max_break_cur=factory // 2)
            row = self.store.item(row['uniq'])
            before = self.store.money(self.cid)
            p, q = self.quote(row)
            nominal = items.params_of(type_id)['g_cost' if gold else 'cost']
            expected = int(Fraction(nominal * row['brk'], factory))
            self.assertEqual((q['res'], q['price'], q['currency'], q['eden_sale']),
                             (0, expected, int(gold), 1))
            self.s.char.afro, self.s.char.gold = 999999, 999999
            self.assertEqual(self.confirm(p, q), [0])
            after = (before[0] + (0 if gold else expected), before[1] + (expected if gold else 0))
            self.assertEqual(self.store.money(self.cid), after)
            self.assertEqual((self.s.char.afro, self.s.char.gold), after)
            self.assertIsNone(self.store.item(row['uniq']))
            self.assertNotEqual(self.confirm(p, q), [0])
            self.assertEqual(self.store.money(self.cid), after)

    def test_zero_quality_or_sub_currency_nominal_never_mints_a_minimum_payout(self):
        row = self.give(25637)
        for brk, ceiling in ((0, 500), (1, 500), (1, 0)):
            self.store.update_item(row['uniq'], brk=brk, max_break_cur=ceiling)
            before = self.state()
            _, q = self.quote(self.store.item(row['uniq']))
            self.assertNotEqual(q['res'], 0)
            self.assertEqual(self.state(), before)

    def test_local_items_and_forged_stock_are_refused_without_any_mutation(self):
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.give(type_id)
            before = self.state()
            _, q = self.quote(row)
            self.assertNotEqual(q['res'], 0, type_id)
            self.frames.clear()
            self.inv.ss_upd(dict(s_status=2, obj=inventory.oid_of(row), param=1))
            self.assertNotEqual(self.frames[0][1]['res'], 0, type_id)
            self.assertEqual(self.state(), before)
        before = self.state()
        with patch.object(items, 'stock_for', return_value=[25636]):
            for code in (inventory.UPD_BUY, inventory.UPD_BUY_GOLD, inventory.UPD_BGPOINTS_BUY):
                self.frames.clear()
                self.inv.ss_upd(dict(s_status=code, obj='0', param=1))
                self.assertNotEqual(self.frames[0][1]['res'], 0)
        self.assertEqual(self.state(), before)

    def test_locked_banked_and_forged_item_identity_cannot_be_quoted(self):
        row = self.give(26075)
        for mode in ('locked', 'bank', 'wrong_type', 'wrong_root'):
            self.store.update_item(row['uniq'], slot=inventory.BAG)
            self.inv.locked.clear()
            obj = inventory.oid_of(row)
            if mode == 'locked':
                self.inv.locked.add(row['uniq'])
            elif mode == 'bank':
                self.store.update_item(row['uniq'], slot=inventory.BANK)
            elif mode == 'wrong_type':
                obj = inventory.oid(row['uniq'], 25636, row['root'])
            else:
                obj = inventory.oid(row['uniq'], row['type_id'], items.TRASH)
            before = self.state()
            _, q = self.quote(row, obj=obj)
            self.assertNotEqual(q['res'], 0, mode)
            self.assertEqual(self.state(), before)

    def test_changed_counter_distance_sentence_and_wear_invalidate_confirmation(self):
        for mode in ('npc', 'map', 'distance', 'sentence', 'wear'):
            row = self.give(26075)
            p, q = self.quote(row)
            self.assertEqual(q['res'], 0)
            before = self.state()
            if mode == 'npc':
                context = patch.object(self.s.room, 'npc', return_value=None)
            elif mode == 'map':
                context = patch.object(self.s, 'on_map', True)
            elif mode == 'distance':
                context = patch.object(self.s, 'live_cell', return_value=0)
            elif mode == 'sentence':
                context = patch.object(eden, 'assigned', return_value=None)
            else:
                self.store.update_item(row['uniq'], brk=1)
                before = self.state()
                context = patch.object(self.s, 'on_map', False)
            with context:
                self.assertNotEqual(self.confirm(p, q), [0], mode)
            self.assertEqual(self.state(), before, mode)

    def test_non_gear_blueprints_consumables_and_ammo_keep_current_sale_rules(self):
        for type_id, n in ((37679, 1), (37638, 1), (6946, 1), (3159, 3)):
            baseline = self.give(type_id, n)
            local = self.give(type_id, n)
            self.s.loc = NS(id=36, width=20, height=20)
            self.s.room = NS(loc=self.s.loc, npc=lambda n: (0, 123, world.TRADER))
            self.inv.trade = inventory.TradeSession(1, 123, 36)
            before = self.store.money(self.cid)
            si = items.params_of(type_id)
            if gold_trade.gold_priced(type_id, si):
                p, q = self.quote(baseline, n)
                self.assertNotIn('eden_sale', q)
                self.assertEqual(self.confirm(p, q), [0])
            else:
                self.frames.clear()
                self.inv.ss_upd(dict(s_status=2, obj=inventory.oid_of(baseline), param=n))
                self.assertEqual(self.frames[0], ('cmdAck', dict(res=0)))
            after = self.store.money(self.cid)
            expected = (after[0] - before[0], after[1] - before[1])
            self.s.loc = world.location(eden.CENTER)
            self.s.pos = 7060
            self.s.room = NS(loc=self.s.loc, npc=lambda n: (7060, eden_shop.NPC_TYPE, world.TRADER))
            self.inv.trade = inventory.TradeSession(1, eden_shop.NPC_TYPE, eden.CENTER)
            if gold_trade.gold_priced(type_id, si):
                p, q = self.quote(local, n)
                self.assertEqual(q['price'], expected[0])
                self.assertNotIn('eden_sale', q)
                self.assertEqual(self.confirm(p, q), [0])
            else:
                self.frames.clear()
                self.inv.ss_upd(dict(s_status=2, obj=inventory.oid_of(local), param=n))
                self.assertEqual(self.frames[0], ('cmdAck', dict(res=0)))
            actual = self.store.money(self.cid)
            self.assertEqual((actual[0] - after[0], actual[1] - after[1]), expected, type_id)

    def test_sale_write_failure_rolls_back_item_money_and_live_character(self):
        row = self.give(26075)
        p, q = self.quote(row)
        before = self.state()
        with patch.object(self.store, 'set_money', side_effect=RuntimeError('rollback sale')):
            self.assertNotEqual(self.confirm(p, q), [0])
        self.assertEqual(self.state(), before)
        self.assertEqual((self.s.char.afro, self.s.char.gold), before[0])
        self.assertFalse(any(cmd == 'money' or cmd == 'ss_obj_status' for cmd, _ in self.frames))

    def test_uncertain_sale_commit_closes_with_one_native_payment_and_no_success_frames(self):
        for type_id in (25636, 26075):
            row = self.give(type_id)
            p, q = self.quote(row)
            before = self.store.money(self.cid)
            original = storage.atomic

            @contextmanager
            def lost_reply(db):
                with original(db):
                    yield db
                raise storage.CommitError('committed, reply lost')

            self.s.closed = False
            with patch.object(storage, 'atomic', lost_reply):
                self.assertEqual(self.confirm(p, q), [])
            expected = (before[0] + (0 if q['currency'] else q['price']),
                        before[1] + (q['price'] if q['currency'] else 0))
            self.assertTrue(self.s.closed)
            self.assertEqual(self.store.money(self.cid), expected)
            self.assertIsNone(self.store.item(row['uniq']))
            self.assertEqual(self.frames, [])
            self.s.char.save(self.store)
            self.assertEqual(self.store.money(self.cid), expected)
            self.assertNotEqual(self.confirm(p, q), [0])
            self.assertEqual(self.store.money(self.cid), expected)

    def test_insufficient_repair_money_and_gold_restore_preserve_core_rules(self):
        row = self.give(26075)
        si = items.params_of(row['type_id'])
        factory = si['max_break_abs']
        self.store.update_item(row['uniq'], brk=factory // 4, max_break_cur=factory // 2)
        self.store.set_money(self.cid, 0, 0)
        for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE):
            self.frames.clear()
            before = self.state()
            self.inv.ss_upd(dict(s_status=code, obj=inventory.oid_of(row)))
            self.assertEqual(self.frames[0], ('cmdAck', dict(res=inventory.RES_NO_MONEY)))
            self.assertEqual(self.state(), before)
        self.store.set_money(self.cid, 12345, 100000)
        expected = inventory.repair_prices(si, factory // 4, factory // 2)[2]
        self.frames.clear()
        self.inv.ss_upd(dict(s_status=inventory.UPD_RESTORE, obj=inventory.oid_of(row)))
        self.assertEqual(self.frames[0], ('cmdAck', dict(res=0)))
        self.assertEqual(self.store.money(self.cid), (12345, 100000 - expected))
        current = self.store.item(row['uniq'])
        self.assertEqual((current['brk'], current['max_break_cur']), (factory, factory))

    def test_repair_uses_existing_rates_in_each_currency_and_rejects_stale_context(self):
        for code, gold in ((inventory.UPD_REPAIR, False), (inventory.UPD_REPAIR_GOLD, True)):
            row = self.give(25636)
            si = items.params_of(row['type_id'])
            factory = si['max_break_abs']
            self.store.update_item(row['uniq'], brk=factory // 2)
            row = self.store.item(row['uniq'])
            price = inventory.repair_prices(si, row['brk'], row['max_break_cur'])[int(gold)]
            before = self.store.money(self.cid)
            self.frames.clear()
            self.inv.ss_upd(dict(s_status=code, obj=inventory.oid_of(row)))
            self.assertEqual(self.frames[0], ('cmdAck', dict(res=0)))
            self.assertEqual(self.store.money(self.cid),
                             (before[0] - (0 if gold else price), before[1] - (price if gold else 0)))
            repaired = self.store.item(row['uniq'])
            self.assertEqual((repaired['brk'], repaired['max_break_cur']), (int(factory * .9),) * 2)
        tool = self.give(eden.CLEAVER)
        self.store.update_item(tool['uniq'], brk=1)
        for context in (patch.object(self.s, 'on_map', True), patch.object(self.s.room, 'npc', return_value=None)):
            before = self.state()
            self.frames.clear()
            with context:
                self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(tool)))
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertEqual(self.state(), before)

    def test_only_local_tool_and_basket_can_use_core_repair_at_the_eden_counter(self):
        for type_id in (eden.CLEAVER, eden.BASKET):
            for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD):
                row = self.give(type_id)
                si = items.params_of(type_id)
                factory = si['max_break_abs']
                self.store.update_item(row['uniq'], brk=factory // 2)
                before = self.store.money(self.cid)
                expected = inventory.repair_prices(si, factory // 2, factory)[int(code == inventory.UPD_REPAIR_GOLD)]
                self.frames.clear()
                self.inv.ss_upd(dict(s_status=code, obj=inventory.oid_of(row)))
                self.assertEqual(self.frames[0], ('cmdAck', dict(res=0)))
                repaired = self.store.item(row['uniq'])
                self.assertEqual((repaired['brk'], repaired['max_break_cur']), (int(factory * .9),) * 2)
                delta = (expected, 0) if code == inventory.UPD_REPAIR else (0, expected)
                self.assertEqual(self.store.money(self.cid), (before[0] - delta[0], before[1] - delta[1]))
                # A local zero-price thing has no ordinary G restoration.
                self.frames.clear()
                state = self.state()
                self.inv.ss_upd(dict(s_status=inventory.UPD_RESTORE, obj=inventory.oid_of(row)))
                self.assertNotEqual(self.frames[0][1]['res'], 0)
                self.assertEqual(self.state(), state)
        for type_id in sorted(eden.LOCAL_ITEMS - eden_shop.REPAIRABLE_LOCAL):
            row = self.give(type_id)
            before = self.state()
            self.frames.clear()
            self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(row)))
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertEqual(self.state(), before)

    def test_local_repair_refuses_ordinary_trader_barter_lock_and_rollback_keeps_wear(self):
        for type_id in (eden.CLEAVER, eden.BASKET):
            row = self.give(type_id)
            self.store.update_item(row['uniq'], brk=100)
            before = self.state()
            trade = self.inv.trade
            self.inv.trade = inventory.TradeSession(1, 123, 36)
            self.frames.clear()
            self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(row)))
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertEqual(self.state(), before)
            self.inv.trade = trade
            self.inv.locked.add(row['uniq'])
            self.frames.clear()
            self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(row)))
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertEqual(self.state(), before)
            self.inv.locked.discard(row['uniq'])
            self.frames.clear()
            with patch.object(self.store, 'update_item', side_effect=RuntimeError('local repair rollback')):
                self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(row)))
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertEqual(self.state(), before)

    def test_repair_cash_failure_rolls_back_payment_wear_and_published_state(self):
        row = self.give(25636)
        self.store.update_item(row['uniq'], brk=100)
        before = self.state()
        self.frames.clear()
        with patch.object(self.store, 'update_item', side_effect=RuntimeError('rollback repair')):
            self.inv.ss_upd(dict(s_status=inventory.UPD_REPAIR, obj=inventory.oid_of(row)))
        self.assertNotEqual(self.frames[0][1]['res'], 0)
        self.assertEqual(self.state(), before)
        self.assertEqual((self.s.char.afro, self.s.char.gold), before[0])
        self.assertFalse(any(cmd in ('money', 'ss_di_firearm') for cmd, _ in self.frames))

    def test_alias_and_npc_frame_change_only_the_eden_counter(self):
        types = world.mob_types()
        self.assertEqual(types[eden_shop.NPC_TYPE], (world.TRADER, 'eden_buyback', types[883][2]))
        self.assertEqual(types[883][0], world.AUCTIONER)
        self.frames.clear()
        self.s.send_npc_info(1)
        command, p = self.frames[0]
        self.assertEqual(command, 'userInfo_Trader')
        self.assertEqual((p['name'], p['res'], p['type_list'], p['eden_shop'], p['smod']),
                         (eden_shop.NPC_TYPE, 883, [], 1, inventory.SMOD))


if __name__ == '__main__':
    run_cases(EdenShopTests)
