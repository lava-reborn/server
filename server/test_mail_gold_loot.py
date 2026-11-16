"""Gold-loot mail policy: forged sends are atomic, old parcels remain claimable."""
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_mortimer_sales as mortimer_tests
import auction
import barter
import eden
import inventory
import items
import mail
import mortimer
from protocol import Repeated, decode
from testkit import run_cases


class MailGoldLootTests(unittest.TestCase):
    give = mortimer_tests.MortimerSales.give

    def setUp(self):
        mortimer_tests.MortimerSales.setUp(self)
        aid, _ = self.store.register('recipient', 'test-only')
        self.recipient, _ = self.store.create_character(aid, 'Recipient', 0, '1')
        self.directory = NS(by_pid=lambda pid: None)
        self.box = mail.Mail(self.s, self.store, self.directory)
        self.s.mail = self.box
        self.answers = []
        self.s.answer = self.answers.append

    def state(self):
        ledger = self.store.db.execute(
            'SELECT COUNT(*) AS n FROM money_ledger WHERE char_id=?',
            (self.cid,)).fetchone()['n']
        return (self.inv.rows(), self.store.money(self.cid),
                (self.s.char.afro, self.s.char.gold), ledger,
                self.store.mail_outbox(self.cid),
                self.store.mail_inbox(self.recipient),
                self.store.mail_inbox(self.cid),
                self.store.mail_outbox(self.recipient),
                self.store.money(self.recipient))

    def test_policy_uses_gold_loot_not_all_gold_purchases(self):
        expected = {2258, 4796, 4797, 6950, 6951, 6952, 6953, 6959, 7620}
        self.assertEqual(mail.GOLD_LOOT_NOT_POSTABLE, expected)
        self.assertEqual(expected,
                         set(items.GOLD_INGOTS) | mortimer.VALUABLES | {mortimer.SAND})
        for type_id in expected:
            with self.subTest(type_id=type_id):
                self.assertFalse(mail.postable(type_id))
                self.assertTrue(barter.tradable(type_id))
        for type_id in (25567, 26075, 4363, 7006, 37679, 6946, 3159):
            with self.subTest(type_id=type_id):
                self.assertTrue(mail.postable(type_id))

    def test_forged_send_is_refused_before_items_postage_or_money_leave(self):
        # These are all supported player parcel types, including express
        # postage and payment-on-delivery. The same server handler receives
        # both the real client and a command sent without its UI checks.
        for type_id in sorted(mail.GOLD_LOOT_NOT_POSTABLE):
            row = self.give(type_id, 3)
            for kind in (mail.LETTER, mail.LETTER_EXPRESS,
                         mail.TRADE, mail.TRADE_EXPRESS):
                with self.subTest(type_id=type_id, kind=kind):
                    before = self.state()
                    self.frames.clear()
                    cmd, params = decode(
                        'sndml;to=@Recipient@;subj=@test@;body=@test@;'
                        'type=%d;afro=100;gold=0;item=x%s;' %
                        (kind, inventory.oid_of(row)))
                    getattr(self.s, 'cmd_' + cmd)(params)
                    self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_PARCEL_REFUSED})])
                    self.assertEqual(self.state(), before)
                    self.assertIn('нельзя пересылать почтой', self.answers[-1])

    def test_mixed_parcel_is_refused_whole_even_with_allowed_item_first(self):
        allowed = self.give(26075)
        forbidden = self.give(mortimer.SAND, 10)
        for rows in ((allowed, forbidden), (forbidden, allowed)):
            with self.subTest(first=rows[0]['type_id']):
                before = self.state()
                self.frames.clear()
                self.box.sndml(dict(to='Recipient', type=mail.LETTER,
                                    item=Repeated([inventory.oid_of(r) for r in rows])))
                self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_PARCEL_REFUSED})])
                self.assertEqual(self.state(), before)

    def test_clan_letters_and_unsupported_orders_cannot_bypass_policy(self):
        row = self.give(7620)
        with patch.object(self.store, 'clan_member', return_value={'clan_id': 1}):
            for kind in (mail.CLAN, mail.CLAN_EXPRESS, mail.ORDER, mail.ORDER_EXPRESS):
                with self.subTest(kind=kind):
                    before = self.state()
                    self.frames.clear()
                    self.box.sndml(dict(to='Recipient', type=kind,
                                        item=inventory.oid_of(row)))
                    code = (mail.RES_NOT_IN_CLAN if kind in (mail.CLAN, mail.CLAN_EXPRESS)
                            else mail.RES_REFUSED)
                    self.assertEqual(self.frames, [('cmdAck', {'res': code})])
                    self.assertEqual(self.state(), before)

    def test_gold_equipment_and_ordinary_loot_still_send_with_each_parcel_type(self):
        self.s.char.gold = 10000
        self.s.char.save(self.store)
        for type_id in (26075, 6946):
            for kind in (mail.LETTER, mail.LETTER_EXPRESS,
                         mail.TRADE, mail.TRADE_EXPRESS):
                with self.subTest(type_id=type_id, kind=kind):
                    row = self.give(type_id)
                    old_money = self.store.money(self.cid)
                    fees = mail.tariff(kind, inventory.weight_of(row))
                    before = len(self.store.mail_inbox(self.recipient))
                    self.box.sndml(dict(to='Recipient', type=kind,
                                        item=inventory.oid_of(row)))
                    self.assertEqual(self.frames[0], ('cmdAck', {'res': mail.RES_OK}))
                    self.assertIsNone(self.store.item(row['uniq']))
                    self.assertEqual(len(self.store.mail_inbox(self.recipient)), before + 1)
                    self.assertEqual(self.store.money(self.cid),
                                     tuple(a - b for a, b in zip(old_money, fees)))

    def test_legacy_parcels_and_cod_gold_loot_can_be_claimed_once(self):
        for type_id in sorted(mail.GOLD_LOOT_NOT_POSTABLE):
            for kind in (mail.LETTER, mail.LETTER_EXPRESS,
                         mail.TRADE, mail.TRADE_EXPRESS):
                with self.subTest(type_id=type_id, kind=kind):
                    row = self.give(type_id, 3)
                    snap = mail.snapshot(row)
                    self.store.delete_item(row['uniq'])
                    offer = kind in (mail.TRADE, mail.TRADE_EXPRESS)
                    letter = self.store.mail_send(
                        self.cid, self.recipient, kind, 'old parcel', 'old parcel',
                        25 if offer else 0, 0, json.dumps([snap]))
                    before = self.store.money(self.cid)
                    self.frames.clear()
                    self.box.uldml({'id': str(letter['id'])})
                    self.assertEqual(self.frames[0], ('cmdAck', {'res': mail.RES_OK}))
                    self.assertEqual(self.store.money(self.cid),
                                     (before[0] - (25 if offer else 0), before[1]))
                    received = self.inv.rows()
                    self.assertEqual(received[-1]['type_id'], type_id)
                    self.assertEqual(received[-1]['count'], snap['count'])
                    self.assertEqual(self.store.mail_letter(letter['id'])['items_json'], '[]')
                    money = self.store.money(self.cid)
                    self.frames.clear()
                    self.box.uldml({'id': str(letter['id'])})
                    self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_NOTHING_TO_TAKE})])
                    self.assertEqual(self.inv.rows(), received)
                    self.assertEqual(self.store.money(self.cid), money)

    def test_legacy_gold_loot_return_is_not_lost(self):
        row = self.give(7620, 3)
        snap = mail.snapshot(row)
        self.store.delete_item(row['uniq'])
        letter = self.store.mail_send(self.recipient, self.cid, mail.TRADE,
                                      'old offer', 'old offer', 500, 0, json.dumps([snap]))
        recipient = NS(char_id=self.recipient, send=lambda *a, **kw: None)
        mail.Mail(recipient, self.store, self.directory).rmvml({'id': str(letter['id'])})
        returned = self.store.mail_letter(letter['id'])
        self.assertEqual((returned['to_char'], returned['returned'], returned['afro']),
                         (self.cid, 1, 0))
        before = self.store.money(self.cid)
        self.box.uldml({'id': str(letter['id'])})
        self.assertEqual(self.inv.rows()[-1]['type_id'], 7620)
        self.assertEqual(self.inv.rows()[-1]['count'], 3)
        self.assertEqual(self.store.money(self.cid), before)

    def test_auction_ingot_refund_remains_claimable(self):
        row = self.give(7620)
        house = auction.Auction(self.s, self.store, self.directory)
        house.at_auctioneer = lambda p: True
        result, _ = house._create(dict(obj=inventory.oid_of(row), time=24, a_bid=1000))
        self.assertEqual(result, 0)
        lot = self.store.auction_active(0)[0]
        letters = self.store.auction_close(lot['id'], auction.give_back(lot, 'test', 'test'))
        self.box.uldml({'id': str(letters[0]['id'])})
        self.assertEqual([(r['type_id'], r['count']) for r in self.inv.rows()], [(7620, 1)])


class EdenMailTests(unittest.TestCase):
    give = MailGoldLootTests.give
    setUp = MailGoldLootTests.setUp
    state = MailGoldLootTests.state

    def old_parcel(self, kind=mail.LETTER, sender=None, afro=0, gold=0, item=True):
        snaps = []
        if item:
            row = self.give(6946, 2)
            snaps = [mail.snapshot(row)]
            self.store.delete_item(row['uniq'])
        return self.store.mail_send(
            self.cid, self.recipient if sender is None else sender, kind,
            'old parcel', 'old parcel', afro, gold, json.dumps(snaps))

    def test_all_eden_rooms_block_old_parcels_cod_and_auction_payments_without_loss(self):
        cases = ((mail.LETTER, self.recipient, 100, 20, True),
                 (mail.LETTER_EXPRESS, self.recipient, 100, 20, False),
                 (mail.TRADE, self.recipient, 100, 0, True),
                 (mail.TRADE_EXPRESS, self.recipient, 0, 20, True),
                 (mail.LETTER, mail.SYSTEM_SENDER, 0, 0, True),
                 (mail.LETTER, mail.SYSTEM_SENDER, 200, 50, False))
        for location in sorted(eden.LOCATIONS):
            self.s.loc.id = location
            for kind, sender, afro, gold, item in cases:
                with self.subTest(location=location, kind=kind, sender=sender, item=item):
                    letter = self.old_parcel(kind, sender, afro, gold, item)
                    before = self.state()
                    self.frames.clear()
                    # Forged packet location does not overrule the session.
                    self.s.cmd_uldml(dict(id=str(letter['id']), loc=36))
                    self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_PARCEL_REFUSED})])
                    self.assertEqual(self.state(), before)
                    self.assertIn('Вложения сохранены', self.answers[-1])

    def test_all_eden_rooms_block_outgoing_parcels_and_money_without_postage(self):
        row = self.give(6946, 3)
        for location in sorted(eden.LOCATIONS):
            self.s.loc.id = location
            for kind in range(8):
                for attachment in (dict(item=inventory.oid_of(row)),
                                   dict(afro=10), dict(gold=10)):
                    with self.subTest(location=location, kind=kind, attachment=attachment):
                        before = self.state()
                        self.frames.clear()
                        self.s.cmd_sndml(dict(to='Recipient', type=kind, **attachment))
                        self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_PARCEL_REFUSED})])
                        self.assertEqual(self.state(), before)

    def test_mail_can_be_read_and_text_can_be_sent_on_eden(self):
        for location in sorted(eden.LOCATIONS):
            self.s.loc.id = location
            for item in (False, True):
                letter = self.old_parcel(item=item)
                before_items = self.inv.rows()
                before_money = self.store.money(self.cid)
                self.frames.clear()
                self.box.getml(dict(id=str(letter['id'])))
                self.assertEqual([cmd for cmd, _ in self.frames], ['cmdAck', 'rcml'])
                self.assertEqual(self.frames[0][1]['res'], mail.RES_OK)
                self.assertEqual(self.inv.rows(), before_items)
                self.assertEqual(self.store.money(self.cid), before_money)
                self.assertEqual(self.store.mail_letter(letter['id'])['items_json'],
                                 letter['items_json'])
            self.frames.clear()
            self.box.sndml(dict(to='Recipient', type=mail.LETTER,
                                subj='text only', body='text only'))
            self.assertEqual(self.frames[0], ('cmdAck', {'res': mail.RES_OK}))
            self.assertEqual(self.store.money(self.cid), (before_money[0] - mail.PRICES[0],
                                                         before_money[1]))

    def test_refusal_or_deletion_cannot_send_a_parcel_back_from_eden(self):
        for location in sorted(eden.LOCATIONS):
            self.s.loc.id = location
            text = self.old_parcel(item=False)
            parcel = self.old_parcel(afro=100)
            before = self.state()
            self.frames.clear()
            self.box.rmvml(dict(id=Repeated([str(text['id']), str(parcel['id'])])))
            self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_PARCEL_REFUSED})])
            self.assertEqual(self.state(), before)
            self.assertIn('Письмо сохранено', self.answers[-1])

    def test_waiting_parcel_is_still_claimable_once_after_leaving_eden(self):
        letter = self.old_parcel(afro=100, gold=20)
        self.s.loc.id = eden.CENTER
        before = self.state()
        self.box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.state(), before)
        self.s.loc.id = 36
        self.frames.clear()
        self.box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.frames[0], ('cmdAck', {'res': mail.RES_OK}))
        self.assertEqual(self.store.money(self.cid), (12445, 120))
        self.assertEqual([(r['type_id'], r['count']) for r in self.inv.rows()], [(6946, 2)])
        self.frames.clear()
        self.box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.frames, [('cmdAck', {'res': mail.RES_NOTHING_TO_TAKE})])
        self.assertEqual(self.store.money(self.cid), (12445, 120))


if __name__ == '__main__':
    run_cases(MailGoldLootTests, EdenMailTests)
