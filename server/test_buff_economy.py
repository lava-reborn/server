"""Discount ammunition coupons cannot become an unlimited NPC cash source.

Existing coupons still redeem through real quest handlers and sell normally;
the unrestricted cheap shop source is what must be unavailable.
"""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import inventory
import items
import progression
import quests
import world
from test_gold_commerce import GoldCommerce
from testkit import run_cases


class BuffEconomy(unittest.TestCase):
    quote = GoldCommerce.quote
    confirmed = GoldCommerce.confirmed

    def setUp(self):
        GoldCommerce.setUp(self)
        self.s.loc = world.location(261)
        self.s.room = NS(loc=self.s.loc, npc=lambda _eid: (0, self.inv.trade.trader_type, world.TRADER))
        self.s.npc_type = lambda _eid: 5766
        self.s.gx, self.s.gy = world.unpack(quests.get(500).loc)
        for skill in self.s.char.skill:
            skill[0] = 12
        self.s.char.recalc()
        self.store.set_money(self.cid, 0, 10000)
        self.s.char.afro, self.s.char.gold = 0, 10000
        self.s.char.save(self.store)
        self.inv.trade = inventory.TradeSession(1, 5766, 261)

    def acks(self):
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def redeem(self, coupon):
        qtype = {6294: 492, 6295: 496, 6296: 500}[coupon]
        self.frames.clear()
        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(5766).index(qtype)))
        self.assertEqual(self.acks(), [0])
        qid = next(r['q_id'] for r in self.store.quests(self.cid) if r['type'] == qtype)
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
        self.assertEqual(self.acks(), [0])
        return qid

    def test_discount_coupons_cannot_be_bought_from_actual_huxley_stall(self):
        # Before the fix these buys succeed for 0.1/1/10 G; a 10 G coupon
        # redeems into 5000 EK rounds with a real 3,500,000 afro resale quote.
        stock = items.stock_for(5766, 261)
        before = self.store.money(self.cid)
        for coupon, old_index in ((6294, 0), (6295, 1), (6296, 2)):
            index = stock.index(coupon) if coupon in stock else old_index
            self.frames.clear()
            self.inv.buy(dict(obj=format(index, 'x'), param=1), inventory.UPD_BUY_GOLD)
            self.assertNotIn(0, self.acks(), coupon)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(self.inv.rows())

    def test_forged_type_or_owned_serial_does_not_buy_another_coupon(self):
        owned = self.inv.create(6296)
        before = self.store.money(self.cid)
        for obj in (format(6296, 'x'), inventory.oid_of(owned), '0', '1', '2'):
            self.frames.clear()
            self.inv.buy(dict(obj=obj, param=100), inventory.UPD_BUY_GOLD)
            self.assertNotIn(0, self.acks())
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual([r['uniq'] for r in self.inv.rows()], [owned['uniq']])

    def test_owner_and_fallback_stock_sources_cannot_restore_discount_coupon_sales(self):
        coupons = [6294, 6295, 6296]
        with patch.object(items.npcs, 'stock', return_value=coupons):
            self.assertTrue(set(coupons).isdisjoint(items.stock_for(5766)))
        with patch.object(items.npcs, 'stock', return_value=None), \
                patch.object(items, 'stock_table', return_value={5766: coupons}):
            self.assertTrue(set(coupons).isdisjoint(items.stock_for(5766)))
        # Hiding the sale never inflates a historical coupon's nominal value.
        self.assertEqual([items.params_of(t)['g_cost'] for t in coupons], [10, 100, 1000])

    def test_existing_coupon_redeems_once_and_sale_cannot_be_replayed(self):
        row = self.inv.create(6296)
        qid = self.redeem(6296)
        self.assertIsNone(self.store.item(row['uniq']))
        ammo = next(r for r in self.inv.rows() if r['type_id'] == 6152)
        self.assertEqual(ammo['count'], 5000)
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
        self.assertNotIn(0, self.acks())
        self.s.loc = NS(id=36, width=20, height=20)
        self.s.room.loc = self.s.loc
        self.inv.trade = inventory.TradeSession(1, 123, 36)
        request, quote = self.quote(ammo, 5000)
        self.assertEqual(quote['price'], 3500000)
        self.assertEqual(self.confirmed(request, quote), 0)
        self.assertNotEqual(self.confirmed(request, quote), 0)
        self.assertEqual(self.store.money(self.cid), (3500000, 10000))

    def test_small_existing_coupons_keep_their_exact_redemption_quantities(self):
        for coupon, count in ((6294, 20), (6295, 300)):
            with self.subTest(coupon=coupon):
                self.inv.trade = inventory.TradeSession(1, 5766, 261)
                self.inv.create(coupon)
                self.redeem(coupon)
                self.assertFalse(any(r['type_id'] == coupon for r in self.inv.rows()))
                ammo = [r for r in self.inv.rows() if r['type_id'] == 6152]
                self.assertIn(count, [r['count'] for r in ammo])


if __name__ == '__main__':
    run_cases(BuffEconomy)
