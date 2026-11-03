"""Real NPC buy/sell operations, stack rounding and catalogue currency loops."""
import contextlib
from functools import lru_cache
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import test_gold_commerce as fixtures
import gold_trade
import inventory
import items
import mortimer
import progression
import shop_bands
import storage
import world
from testkit import run_cases


ROOT = Path(__file__).resolve().parents[1]
RATE = progression.GOLD_TO_AFRO_RATE / progression.GOLD_OUNCE
QUANTITIES = (1, 2, 20, 100, 999, 5000)


@lru_cache(maxsize=1)
def stock_types():
    """Original/owner stalls plus every city band, not just weapon wares."""
    offered = set()
    for npc in world.mob_types():
        offered.update(items.stock_for(npc))
    doc = json.loads((ROOT / 'data/shop_bands.json').read_text(encoding='utf-8'))
    for npc in shop_bands.SELLERS:
        for city in doc['cities']:
            if city['places']:
                offered.update(items.stock_for(npc, city['places'][0]))
    return frozenset(offered)


def purchase_options(type_id, params, n):
    options = []
    for gold, key in ((False, 'cost'), (True, 'g_cost')):
        if params.get(key, 0) <= 0 or (not gold and type_id in items.GOLD_INGOTS):
            continue
        paid = inventory.buy_price(params, items.root_of(type_id), n, gold)
        options.append((paid * RATE if gold else paid, gold, paid))
    return options


def resale_unit(type_id, params):
    if type_id in mortimer.VALUABLES:
        return mortimer.unit_gold(type_id) * RATE
    if gold_trade.protected(type_id, params):
        return 0
    if gold_trade.gold_priced(type_id, params):
        return gold_trade.sale_unit(type_id, params)
    if items.root_of(type_id) in items.BREAKABLE_ROOTS:
        return gold_trade.afro_sale_unit(type_id, params)
    unit = (params.get('cost', 0) * inventory.SMOD * params.get('sell_mod', 1)
            / (params.get('sell_num') or 1))
    cap = gold_trade.afro_sale_cap(type_id, params)
    return min(unit, cap) if cap else unit


class ShopCatalogue(unittest.TestCase):
    def test_every_advertised_purchase_currency_has_a_positive_actual_price(self):
        self.assertGreater(len(stock_types()), 600)
        for t in stock_types():
            p = items.params_of(t) or {}
            ns = QUANTITIES if items.root_of(t) == items.AMMO else (1,)
            for n in ns:
                if n > p.get('max_count', 1):
                    continue
                for _, gold, paid in purchase_options(t, p, n):
                    self.assertGreater(paid, 0, (t, n, gold))

    def test_bulk_or_split_resale_never_exceeds_cheapest_allowed_purchase(self):
        checked = 0
        for t in stock_types():
            p = items.params_of(t) or {}
            if p.get('quest'):
                continue
            unit = resale_unit(t, p)
            if unit <= 0:
                continue
            ns = QUANTITIES if items.root_of(t) == items.AMMO else (1,)
            for n in ns:
                if n > p.get('max_count', 1):
                    continue
                options = purchase_options(t, p, n)
                if not options:
                    continue
                whole, split = max(1, math.floor(unit * n)), max(1, math.floor(unit)) * n
                self.assertLessEqual(max(whole, split), min(options)[0], (t, n))
                checked += 1
        self.assertGreater(checked, 600)

    def test_shop_ingots_and_sand_exchange_cannot_print_currency(self):
        for t in items.GOLD_INGOTS.keys() & stock_types():
            p = items.params_of(t)
            # The existing ingot service returns 95%, ordinary resale less.
            exchange = math.floor(items.GOLD_INGOTS[t] * .95) * RATE
            self.assertLess(exchange, min(purchase_options(t, p, 1))[0], t)
        if mortimer.SAND in stock_types():
            p = items.params_of(mortimer.SAND)
            paid = min(purchase_options(mortimer.SAND, p, 1))[0]
            for count, cents in ((5, 1), (50, 20), (100, 50), (175, 100)):
                self.assertLessEqual(cents * RATE, count * paid)


class ShopOperations(unittest.TestCase):
    sell = fixtures.GoldCommerce.sell
    quote = fixtures.GoldCommerce.quote
    confirmed = fixtures.GoldCommerce.confirmed

    def setUp(self):
        fixtures.GoldCommerce.setUp(self)
        self.s.room.loc = self.s.loc
        self.store.set_money(self.cid, 50000000, 100000)
        self.s.char.afro, self.s.char.gold = 50000000, 100000

    def buy(self, type_id, gold=False, n=1):
        self.frames.clear()
        with patch.object(items, 'stock_for', return_value=[type_id]):
            self.inv.buy(dict(obj='0', param=n),
                         inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def test_real_buy_sell_round_trips_lose_money_for_a_g_and_blueprints(self):
        for t, gold in ((26061, False), (26075, True), (37638, False), (37672, True)):
            with self.subTest(type=t, gold=gold):
                before = self.store.money(self.cid)
                self.assertEqual(self.buy(t, gold), [0])
                row = next(r for r in self.inv.rows() if r['type_id'] == t)
                if gold_trade.gold_priced(t, items.params_of(t)):
                    request, quote = self.quote(row)
                    self.assertEqual(self.confirmed(request, quote), 0)
                else:
                    self.assertEqual(self.sell(row, 1), 0)
                after = self.store.money(self.cid)
                self.assertLess(after[0] + after[1] * RATE, before[0] + before[1] * RATE)
                self.assertFalse(any(r['type_id'] == t for r in self.inv.rows()))

    def test_buying_twenty_cheap_rounds_and_selling_singly_does_not_profit(self):
        before = self.store.money(self.cid)
        self.assertEqual(self.buy(6096, n=20), [0])
        row = next(r for r in self.inv.rows() if r['type_id'] == 6096)
        for _ in range(20):
            self.assertEqual(self.sell(row, 1), 0)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(any(r['type_id'] == 6096 for r in self.inv.rows()))

    def test_item_creation_failure_rolls_back_payment_and_ledger(self):
        before = self.store.money(self.cid)
        with patch.object(self.store, 'create_item', side_effect=RuntimeError('injected')):
            self.assertEqual(self.buy(26075, True), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual((self.s.char.afro, self.s.char.gold), before)
        self.assertFalse(any(r['type_id'] == 26075 for r in self.inv.rows()))
        self.assertEqual(self.store.db.execute(
            "SELECT gold FROM money_ledger WHERE char_id=? AND source='shop_buy'", (self.cid,)).fetchall(), [])

    def test_money_write_failure_does_not_create_item(self):
        before = self.store.money(self.cid)
        with patch.object(self.store, 'set_money', side_effect=RuntimeError('injected')):
            self.assertEqual(self.buy(26061), [inventory.RES_REFUSED])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(any(r['type_id'] == 26061 for r in self.inv.rows()))

    def test_buy_uses_saved_purse_not_stale_live_balance(self):
        self.s.char.afro, self.s.char.gold = 0, 0
        self.assertEqual(self.buy(26075, True), [0])
        self.assertEqual(self.store.money(self.cid), (50000000, 100000 - 1037))
        self.assertEqual((self.s.char.afro, self.s.char.gold), self.store.money(self.cid))

    def test_insufficient_saved_purse_refuses_without_creating_item(self):
        self.store.set_money(self.cid, 0, 1036)
        self.s.char.gold = 999999
        self.assertEqual(self.buy(26075, True), [inventory.RES_NO_MONEY])
        self.assertEqual(self.store.money(self.cid), (0, 1036))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (0, 1036))
        self.assertFalse(any(r['type_id'] == 26075 for r in self.inv.rows()))

    def test_overweight_refuses_without_payment_or_item(self):
        before = self.store.money(self.cid)
        with patch.object(self.inv, 'carry_limit', return_value=0):
            self.assertEqual(self.buy(26075, True), [inventory.RES_OVERLOAD])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(any(r['type_id'] == 26075 for r in self.inv.rows()))

    def test_uncertain_commit_reloads_money_and_keeps_one_committed_item(self):
        original = storage.atomic

        @contextlib.contextmanager
        def lost_reply(db):
            with original(db):
                yield db
            raise storage.CommitError('committed but reply lost')

        with patch.object(storage, 'atomic', lost_reply):
            self.assertEqual(self.buy(26075, True), [])
        self.assertTrue(self.s.closed)
        self.assertEqual(self.store.money(self.cid), (50000000, 100000 - 1037))
        self.assertEqual((self.s.char.afro, self.s.char.gold), self.store.money(self.cid))
        self.assertEqual(len([r for r in self.inv.rows() if r['type_id'] == 26075]), 1)

    def test_two_successful_purchases_charge_for_exactly_two_items(self):
        self.assertEqual(self.buy(26075, True), [0])
        self.assertEqual(self.buy(26075, True), [0])
        self.assertEqual(len([r for r in self.inv.rows() if r['type_id'] == 26075]), 2)
        self.assertEqual(self.store.money(self.cid), (50000000, 100000 - 2 * 1037))


if __name__ == '__main__':
    run_cases(ShopCatalogue, ShopOperations)
