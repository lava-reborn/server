"""G sales: real SQLite transactions, replay/quote protection and valuations."""
import contextlib
import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS

import test_mortimer_sales as mortimer_tests
import auction
import barter
import combat
import gold_trade
import inventory
import items
import mail
import storage
from testkit import run_cases


class GoldCommerce(unittest.TestCase):
    give = mortimer_tests.MortimerSales.give
    sell = mortimer_tests.MortimerSales.sell

    def setUp(self):
        mortimer_tests.MortimerSales.setUp(self)
        self.inv.trade = inventory.TradeSession(1, 123, 36)
        self.s.room.npc = lambda n: (0, 123, 1)
        # Use the actual role constant, never assume its protocol value.
        import world
        self.s.room.npc = lambda n: (0, 123, world.TRADER)

    def quote(self, row, n=1):
        self.frames.clear()
        p = dict(obj=inventory.oid_of(row), param=n)
        self.inv.ss_upd(dict(p, s_status=2, sale_stage='quote'))
        result = [p for cmd, p in self.frames if cmd == 'cmdAck'][-1]
        self.assertEqual(sum(cmd == 'cmdAck' for cmd, _ in self.frames), 1)
        return p, result

    def confirmed(self, p, result, **extra):
        self.frames.clear()
        self.inv.sell(dict(p, sale_token=result.get('token'), confirmation='ПРОДАТЬ', **extra))
        return next(p['res'] for cmd, p in self.frames if cmd == 'cmdAck')

    def test_sale_requires_confirmation_and_pays_once_from_authoritative_purse(self):
        row = self.give(26075)
        self.assertNotEqual(self.sell(row, 1), 0)
        p, q = self.quote(row)
        self.assertEqual(q['price'], 362950)
        self.s.char.afro = 99999999
        self.assertEqual(self.confirmed(p, q), 0)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (12345 + 362950, 100))
        self.assertNotEqual(self.confirmed(p, q), 0)
        self.assertEqual(self.store.character(self.cid)['afro'], 12345 + 362950)
        self.assertEqual(self.s.char.afro, 12345 + 362950)
        rows = self.store.db.execute("SELECT afro FROM money_ledger WHERE char_id=? AND source='shop_sell'", (self.cid,)).fetchall()
        self.assertEqual(sum(r['afro'] for r in rows), 362950)

    def test_cancel_bad_word_wrong_token_expiration_and_replay_do_not_consume(self):
        row = self.give(26075)
        for altered in ({'confirmation': ''}, {'confirmation': 'продать'}, {'sale_token': 'forged'}):
            p, q = self.quote(row)
            request = dict(p, sale_token=q['token'], confirmation='ПРОДАТЬ')
            request.update(altered)
            self.frames.clear()
            self.inv.sell(request)
            self.assertNotEqual(self.frames[0][1]['res'], 0)
            self.assertIsNotNone(self.store.item(row['uniq']))
        p, q = self.quote(row)
        self.inv.trade.sale_quote['expires'] = 0
        self.assertNotEqual(self.confirmed(p, q), 0)
        self.assertEqual(self.s.char.afro, 12345)

    def test_changed_item_quantity_npc_and_new_stall_invalidate_quote(self):
        row = self.give(37672, 3)
        for change in ('wear', 'quantity', 'npc', 'session', 'bank'):
            with self.subTest(change=change):
                self.store.update_item(row['uniq'], slot=inventory.BAG, count=3, brk=0)
                self.inv.trade = inventory.TradeSession(1, 123, 36)
                import world
                self.s.room.npc = lambda n: (0, 123, world.TRADER)
                p, q = self.quote(self.store.item(row['uniq']))
                if change == 'wear':
                    self.store.update_item(row['uniq'], count=2)
                elif change == 'quantity':
                    p['param'] = 2
                elif change == 'npc':
                    self.s.room.npc = lambda n: None
                elif change == 'session':
                    self.inv.trade = inventory.TradeSession(1, 123, 36)
                else:
                    self.store.update_item(row['uniq'], slot=inventory.BANK)
                self.assertNotEqual(self.confirmed(p, q), 0)
                self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.s.char.afro, 12345)

    def test_wear_and_partial_blueprint_sale_use_same_quote_and_atomic_payment(self):
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=100, max_break_cur=200)
        p, q = self.quote(self.store.item(row['uniq']))
        self.assertEqual(q['price'], 24196)
        self.assertEqual(self.confirmed(p, q), 0)
        row = self.give(37679, 3)
        self.store.update_item(row['uniq'], count=3)
        p, q = self.quote(self.store.item(row['uniq']), 2)
        self.assertEqual(q['price'], 360000)
        self.assertEqual(self.confirmed(p, q), 0)
        self.assertEqual(self.store.item(row['uniq'])['count'], 1)

    def test_money_failure_rolls_back_item_and_ledger(self):
        row = self.give(26075)
        p, q = self.quote(row)
        with patch.object(self.store, 'set_money', side_effect=RuntimeError('injected')):
            self.assertNotEqual(self.confirmed(p, q), 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.character(self.cid)['afro'], 12345)
        self.assertEqual(self.s.char.afro, 12345)

    def test_ordinary_sale_is_atomic_too_without_changing_its_price(self):
        row = self.give(25586)
        with patch.object(self.store, 'set_money', side_effect=RuntimeError('injected')):
            self.assertNotEqual(self.sell(row, 1), 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.character(self.cid)['afro'], 12345)
        self.assertEqual(self.sell(row, 1), 0)
        self.assertEqual(self.s.char.afro, 12345 + 560)
        self.assertIsNone(self.store.item(row['uniq']))

    def test_uncertain_commit_closes_connection_without_success_publication(self):
        row = self.give(26075)
        p, q = self.quote(row)
        original = storage.atomic

        @contextlib.contextmanager
        def lost_reply(db):
            with original(db):
                yield db
            raise storage.CommitError('committed but reply lost')

        self.frames.clear()
        def close(force=False):
            self.s.closed = True
            if self.s.char is not None:
                self.s.char.save(self.store)
        self.s.close = close
        with patch.object(storage, 'atomic', lost_reply):
            self.inv.sell(dict(p, sale_token=q['token'], confirmation='ПРОДАТЬ'))
        self.assertTrue(self.s.closed)
        self.assertFalse(any(cmd == 'cmdAck' and p['res'] == 0 for cmd, p in self.frames))
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.character(self.cid)['afro'], 12345 + 362950)
        self.assertEqual(self.s.char.afro, 12345 + 362950)

    def test_personal_quest_admin_broken_and_mortimer_are_protected(self):
        for t in (3941, items.ADMIN_GUN, 233):
            row = self.give(t)
            _, q = self.quote(row)
            self.assertNotEqual(q['res'], 0)
            self.assertFalse(barter.tradable(t))
            self.assertFalse(mail.postable(t))
        row = self.give(26075)
        self.store.update_item(row['uniq'], brk=0)
        _, q = self.quote(self.store.item(row['uniq']))
        self.assertNotEqual(q['res'], 0)
        self.inv.trade = inventory.TradeSession(1, 1188, 36)
        self.assertNotEqual(self.sell(row, 1), 0)

    def test_g_transfer_includes_mail_legacy_blueprints_not_new_acquisition(self):
        for t in (25567, 26075, 4363, 7006, 37679):
            self.assertTrue(barter.tradable(t), t)
            self.assertTrue(mail.postable(t), t)
        self.assertTrue(items.upgrade_blueprint_blocked(37679))
        self.assertFalse(items.acquisition_blocked(37679))
        self.assertTrue(combat.gold_item(26075))
        self.assertFalse(combat.drops_on_death(26075))

    def test_dual_priced_a_blueprint_keeps_afro_basis_and_no_sale_confirmation(self):
        params = items.params_of(37645)
        self.assertEqual((params['cost'], params['g_cost']), (180000, 4500))
        self.assertEqual(gold_trade.sale_unit(37645, params), 0)
        row = self.give(37645)
        self.assertEqual(self.sell(row, 1), 0)
        self.assertLessEqual(self.s.char.afro - 12345, 126000)
        self.assertEqual(self.s.char.afro - 12345, 77000)
        self.assertEqual(gold_trade.auction_base(37645), 180000)
        self.assertFalse(barter.tradable(37645))
        self.assertFalse(mail.postable(37645))

    def test_blueprint_prices_discount_cap_and_18_20_equal_17(self):
        import craft
        for t, (root, name) in items.catalogue().items():
            level = gold_trade.blueprint_level(t)
            if level is None or '_gold_' not in name:
                continue
            params = items.params_of(t)
            unit = gold_trade.sale_unit(t, params)
            self.assertLessEqual(unit, gold_trade.BLUEPRINT_SALE_CAPS[min(level, 17)])
            self.assertLessEqual(unit, params['g_cost'] * 350 // 3)
            if level > 17:
                import re
                twin = craft._by_name().get(re.sub(r'_lvl\d+', '_lvl17', name))
                self.assertIsNotNone(twin, name)
                self.assertEqual(unit, gold_trade.sale_unit(twin, items.params_of(twin)))
        # No level-17 knife sharpening exists: use the same effect at 16,
        # rather than make old knives' blueprints unsellable or invent data.
        for t in (6632, 6633, 6635, 6636):
            self.assertEqual(gold_trade.sale_unit(t, items.params_of(t)), 37333)
        for t in (6634, 6637):
            self.assertEqual(gold_trade.sale_unit(t, items.params_of(t)), 74666)

    def test_commission_uses_repair_reference_and_a_blueprint_twin(self):
        for t, base, fees in ((26075, 138125, (6907, 9669, 12432)),
                              (25804, 134800, (6740, 9436, 12132)),
                              (37679, 252000, (12600, 17640, 22680))):
            value = inventory.as_sent(gold_trade.auction_base(t))
            self.assertEqual(value, base)
            self.assertEqual(tuple(auction.afro_fee(value, 1, h) for h in (24, 72, 168)), fees)

    def test_blueprint_caps_do_not_exceed_actual_350_kill_source_income(self):
        import math
        from pathlib import Path
        import test_loot_rebalance as loot_tests
        doc = json.loads((Path(__file__).resolve().parents[1] / 'data/loot_rebalance.json').read_text(encoding='utf-8'))
        camps = (80, 81, 84, 85, 88, 92, 93, 98, 132)
        for level in range(1, 18):
            camp = camps[(level - 1) // 2]
            profile = next(p for p in doc['targets'] if p['id'] == 'camp-%d' % camp)
            counts = {int(k): n for k, n in profile['counts'].items()}
            income = sum(loot_tests.revenue(k)[0] * n for k, n in counts.items()) / sum(counts.values())
            self.assertLessEqual(gold_trade.BLUEPRINT_SALE_CAPS[level], math.floor(2 * income) + 2)

    def test_existing_afro_purchase_is_preserved_and_resale_cannot_profit(self):
        params = dict(items.params_of(26075), cost=80)
        with patch.object(items, 'stock_for', return_value=[26075]), \
                patch.object(items, 'params_of', return_value=params):
            self.inv.buy(dict(obj='0', param=1), inventory.UPD_BUY)
        self.assertTrue(any(cmd == 'cmdAck' and p['res'] == 0 for cmd, p in self.frames))
        self.assertEqual(self.s.char.afro, 12345 - inventory.buy_price(params, items.FIRE_ARM, 1, False))
        self.assertEqual(gold_trade.sale_unit(26075, params), 56)

    def mailbox(self):
        return mail.Mail(self.s, self.store, NS(by_pid=lambda pid: None))

    def test_mail_duplicate_attachment_refused_and_failed_send_rolls_back(self):
        aid, _ = self.store.register('recipient', 'test-only')
        recipient, _ = self.store.create_character(aid, 'Recipient', 0, '1')
        row = self.give(26075)
        box = self.mailbox()
        p = dict(to='Recipient', type=mail.LETTER, subj='test', body='test', item=inventory.oid_of(row))
        from protocol import Repeated
        box.sndml(dict(p, item=Repeated([p['item'], p['item']])))
        self.assertNotEqual(self.frames[-1][1]['res'], 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        with patch.object(self.store, 'mail_send', side_effect=RuntimeError('injected')):
            box.sndml(p)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.store.character(self.cid)['afro'], 12345)
        self.assertEqual(self.s.char.afro, 12345)
        self.assertEqual(len(self.store.mail_inbox(recipient)), 0)
        box.sndml(p)
        self.assertIsNone(self.store.item(row['uniq']))
        letters = self.store.mail_inbox(recipient)
        self.assertEqual(len(letters), 1)
        self.assertEqual(json.loads(letters[0]['items_json'])[0]['type_id'], 26075)
        postage = mail.tariff(mail.LETTER, inventory.weight_of(row))[0]
        self.assertEqual(self.s.char.afro, 12345 - postage)
        box.sndml(p)
        self.assertEqual(len(self.store.mail_inbox(recipient)), 1)

    def test_mail_claim_failure_rolls_back_and_success_cannot_be_replayed(self):
        row = self.give(37679)
        snap = mail.snapshot(row)
        self.store.delete_item(row['uniq'])
        letter = self.store.mail_send(self.cid, 0, mail.LETTER, 'test', 'test', 100, 0, json.dumps([snap]))
        box = self.mailbox()
        p = dict(id=str(letter['id']))
        before = self.inv.rows()
        with patch.object(self.store, 'mail_update', side_effect=RuntimeError('injected')):
            box.uldml(p)
        self.assertEqual(self.inv.rows(), before)
        self.assertEqual(self.store.mail_letter(letter['id'])['afro'], 100)
        self.assertEqual(self.s.char.afro, 12345)
        box.uldml(p)
        self.assertEqual(len([r for r in self.inv.rows() if r['type_id'] == 37679]), 1)
        self.assertEqual(self.s.char.afro, 12445)
        box.uldml(p)
        self.assertEqual(len([r for r in self.inv.rows() if r['type_id'] == 37679]), 1)
        self.assertEqual(self.s.char.afro, 12445)

    def test_g_lot_returns_by_mail_once_with_fee_and_snapshot_preserved(self):
        row = self.give(26075)
        self.store.update_item(row['uniq'], ammo_count=3, brk=100, max_break_cur=200)
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        res, then = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertEqual(res, 0)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(self.s.char.afro, 12345 - 6907)
        lot = self.store.auction_active(0)[0]
        letters = self.store.auction_close(lot['id'], auction.give_back(lot, 'test', 'test'))
        self.assertIsNone(self.store.auction_close(lot['id'], auction.give_back(lot, 'test', 'test')))
        self.mailbox().uldml(dict(id=str(letters[0]['id'])))
        returned = [r for r in self.inv.rows() if r['type_id'] == 26075]
        self.assertEqual(len(returned), 1)
        self.assertEqual((returned[0]['ammo_count'], returned[0]['brk'], returned[0]['max_break_cur']), (3, 100, 200))

    def test_afro_blueprint_cannot_be_listed_or_posted_without_losing_item(self):
        row = self.give(37638)
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        res, _ = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertNotEqual(res, 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertEqual(self.s.char.afro, 12345)

    def test_existing_afro_blueprint_lot_cannot_trade_and_returns_with_bid_refund(self):
        import time
        row = self.give(37638)
        aid, _ = self.store.register('bidder', 'test-only')
        bidder, _ = self.store.create_character(aid, 'Bidder', 0, '1')
        lot = self.store.auction_list(row['uniq'], self.cid, dict(
            type_id=row['type_id'], root=row['root'], item_json=json.dumps(mail.snapshot(row)),
            seller=self.cid, seller_name='GoldTester', currency=auction.AFRO,
            start_bid=100, buyout=200, fee=100, hours=24, created_at=int(time.time()),
            ends_at=time.time() + 3600), purse=(self.cid, 12245, 100))
        self.store.db.execute('UPDATE auction_lots SET bidder=?, bidder_name=?, bid=? WHERE id=?',
                              (bidder, 'Bidder', 100, lot['id']))
        self.store.db.commit()
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        res, _ = house._op(dict(obj=inventory.oid_of(row), type=auction.SELL))
        self.assertNotEqual(res, 0)
        rows, _, _ = house.find(dict(cat=auction.ANY))
        self.assertEqual(rows, [])
        auction.sweep(self.store, house.directory, now=time.time() + 7200)
        self.assertIsNone(self.store.auction_lot(lot['id']))
        self.assertEqual(sum(r['afro'] for r in self.store.mail_inbox(bidder)), 100)
        self.assertEqual(len(self.store.mail_inbox(self.cid)), 1)
        self.assertEqual(self.store.mail_inbox(self.cid)[0]['afro'], 100)

    def test_cod_payment_and_attachment_claim_are_atomic(self):
        aid, _ = self.store.register('seller', 'test-only')
        seller, _ = self.store.create_character(aid, 'Seller', 0, '1')
        row = self.give(37679)
        snap = mail.snapshot(row)
        self.store.delete_item(row['uniq'])
        letter = self.store.mail_send(self.cid, seller, mail.TRADE, 'test', 'test', 1000, 0, json.dumps([snap]))
        box = self.mailbox()
        p = dict(id=str(letter['id']))
        with patch.object(self.store, 'mail_send', side_effect=RuntimeError('payment insert failed')):
            box.uldml(p)
        self.assertEqual(self.s.char.afro, 12345)
        self.assertFalse(any(r['type_id'] == 37679 for r in self.inv.rows()))
        self.assertNotEqual(self.store.mail_letter(letter['id'])['items_json'], '[]')
        box.uldml(p)
        self.assertEqual(self.s.char.afro, 11345)
        self.assertEqual(sum(r['afro'] for r in self.store.mail_inbox(seller)), 1000)
        box.uldml(p)
        self.assertEqual(self.s.char.afro, 11345)
        self.assertEqual(sum(r['afro'] for r in self.store.mail_inbox(seller)), 1000)

    def test_legacy_afro_blueprint_cod_cannot_charge_the_recipient(self):
        row = self.give(37638)
        snap = mail.snapshot(row)
        self.store.delete_item(row['uniq'])
        letter = self.store.mail_send(self.cid, 123, mail.TRADE, 'test', 'test', 1000, 0, json.dumps([snap]))
        self.mailbox().uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.s.char.afro, 12345)
        self.assertFalse(any(r['type_id'] == 37638 for r in self.inv.rows()))
        self.assertNotEqual(self.store.mail_letter(letter['id'])['items_json'], '[]')


    def auction_offer(self, row):
        return dict(type_id=row['type_id'], root=row['root'],
                    item_json=json.dumps(mail.snapshot(row)), seller=self.cid,
                    seller_name='GoldTester', currency=auction.AFRO,
                    start_bid=1000, buyout=0, fee=100, hours=24,
                    created_at=1, ends_at=86401)

    def test_changed_auction_snapshot_preserves_item_money_and_no_lot(self):
        changes = dict(slot=inventory.BAG + 1, count=2, brk=1,
                       max_break_cur=1, ammo_count=1, ammo_type=1,
                       cur_mode=1, use_count=1)
        for field, value in changes.items():
            with self.subTest(field=field):
                row = self.give(26075)
                offer = self.auction_offer(row)
                # Ensure the mutation differs even for already-loaded weapons.
                value = value if row[field] != value else value + 1
                self.store.update_item(row['uniq'], **{field: value})
                with self.assertRaises(ValueError):
                    self.store.auction_list(row['uniq'], self.cid, offer,
                                            purse=(self.cid, 12245, 100))
                self.assertEqual(self.store.item(row['uniq'])[field], value)
                self.assertIsNone(self.store.auction_lot_by_item(row['uniq']))
                self.assertEqual(self.store.money(self.cid), (12345, 100))

    def test_lot_insert_failure_rolls_back_item_and_fee(self):
        row = self.give(26075)
        offer = self.auction_offer(row)
        original = self.store.db.insert

        def fail(sql, *args, **kwargs):
            if 'INSERT INTO auction_lots' in sql:
                raise RuntimeError('injected lot insert failure')
            return original(sql, *args, **kwargs)

        with patch.object(self.store.db, 'insert', side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.store.auction_list(row['uniq'], self.cid, offer,
                                        purse=(self.cid, 12245, 100))
        self.assertEqual(mail.snapshot(self.store.item(row['uniq'])), mail.snapshot(row))
        self.assertIsNone(self.store.auction_lot_by_item(row['uniq']))
        self.assertEqual(self.store.money(self.cid), (12345, 100))



    def test_auction_fee_uses_persisted_purse_not_stale_live_balance(self):
        row = self.give(26075)
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        self.s.char.afro, self.s.char.gold = 0, 999999
        res, _ = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertEqual(res, 0)
        self.assertEqual(self.store.money(self.cid), (12345 - 6907, 100))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (12345 - 6907, 100))

    def test_auction_does_not_accept_fee_from_stale_rich_live_balance(self):
        row = self.give(26075)
        self.store.set_money(self.cid, 100, 100)
        self.s.char.afro = 999999
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        res, _ = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertEqual(res, auction.RES_LOW)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertIsNone(self.store.auction_lot_by_item(row['uniq']))
        self.assertEqual(self.store.money(self.cid), (100, 100))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (100, 100))

    def test_uncertain_auction_commit_reloads_balance_before_closing(self):
        row = self.give(26075)
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        house.at_auctioneer = lambda p: True
        original = storage.atomic

        @contextlib.contextmanager
        def lost_reply(db):
            with original(db):
                yield db
            raise storage.CommitError('committed but reply lost')

        with patch.object(storage, 'atomic', lost_reply):
            res, then = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertNotEqual(res, 0)
        self.assertIsNone(then)
        self.assertTrue(self.s.closed)
        self.assertEqual(self.store.money(self.cid), (12345 - 6907, 100))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (12345 - 6907, 100))
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertIsNotNone(self.store.auction_lot_by_item(row['uniq']))



    def seller_lot(self):
        aid, _ = self.store.register('lot-seller', 'test-only')
        seller, _ = self.store.create_character(aid, 'Seller', 0, '1')
        row = self.give(26075)
        self.store.update_item(row['uniq'], char_id=seller)
        row = self.store.item(row['uniq'])
        offer = dict(self.auction_offer(row), seller=seller,
                     seller_name='Seller', buyout=1000, start_bid=100)
        return self.store.auction_list(row['uniq'], seller, offer)

    def test_bid_and_buyout_use_persisted_balance_and_cannot_pay_twice(self):
        lot = self.seller_lot()
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        self.s.char.afro = 0
        res, _ = house.bid(lot, 500)
        self.assertEqual(res, 0)
        self.assertEqual(self.store.money(self.cid), (11845, 100))
        self.s.char.afro = 0
        lot = self.store.auction_lot(lot['id'])
        res, _ = house.buyout(lot)
        self.assertEqual(res, 0)
        # The existing bid is refunded by mail, not silently counted twice.
        self.assertEqual(self.store.money(self.cid), (10845, 100))
        self.assertEqual(sum(r['afro'] for r in self.store.mail_inbox(self.cid)), 500)
        self.assertIsNone(self.store.auction_lot(lot['id']))
        self.assertNotEqual(house.buyout(lot)[0], 0)
        self.assertEqual(self.store.money(self.cid), (10845, 100))

    def test_buyout_letter_failure_rolls_back_lot_money_and_live_balance(self):
        lot = self.seller_lot()
        house = auction.Auction(self.s, self.store, NS(by_pid=lambda pid: None))
        with patch.object(self.store, '_mail_insert', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                house.buyout(lot)
        self.assertIsNotNone(self.store.auction_lot(lot['id']))
        self.assertEqual(self.store.money(self.cid), (12345, 100))
        self.assertEqual(self.s.char.afro, 12345)
        self.assertEqual(self.store.mail_inbox(self.cid), [])


if __name__ == '__main__':
    run_cases(GoldCommerce)
