"""Real single-dose stacks: counts, atomic transfers and delayed consumption."""
import json
import logging
import random
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import accounts
import bank_storage
import battle_medicine
import combat
import inventory
import items
import mail
import protocol
import progression
from testkit import healing_fixture, run_cases


logging.getLogger('lava').setLevel(logging.WARNING)


class MedicineStacks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        account, _ = self.store.register('medicine-stacks', 'test-only')
        self.cid, _ = self.store.create_character(account, 'MedicineStacks', 0, '1')
        self.other, _ = self.store.create_character(account, 'MedicineRecipient', 0, '1')
        self.fighter, self.character, self.room, _ = healing_fixture(6055)
        self.sess = self.fighter.sess
        self.sess.char_id = self.cid
        self.sess.character = lambda: self.character
        self.sess.send_player_info = lambda: None
        self.sess.say = self.sess.answer = lambda text: None
        self.inv = inventory.Inventory(self.sess, self.store)
        self.sess.inv = self.inv
        self.inv.carry_limit = self.inv.bank_max = lambda: 1_000_000
        self.fighter.store = self.store
        self.fighter.ack = self.inv.ack
        self.frames = self.fighter.frames
        self.character.hp = 10

    def give(self, count=1, type_id=6055, **state):
        row = self.inv.create(type_id, count)
        if state:
            self.store.update_item(row['uniq'], **state)
            row = self.store.item(row['uniq'])
        return row

    def quantities(self):
        return [(r['uniq'], r['count'], r['use_count'], r['slot']) for r in self.inv.rows()]

    def ack(self):
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck'][-1]

    def complete(self, row, timestamp=100):
        with patch.object(combat, 'now', return_value=timestamp):
            self.fighter.heal_now(row['uniq'], self.fighter)

    async def test_only_native_single_doses_stack_and_wire_weight_are_exact(self):
        found = 0
        for type_id, (root, name) in items.catalogue().items():
            if root != items.HEAL:
                continue
            params = items.params_of(type_id)
            expected = name.startswith(('Med_Battle_', 'Med_Pacific_')) and params['use_count'] == 1
            self.assertEqual(items.heapable(type_id), expected, type_id)
            if expected:
                found += 1
                self.assertEqual(params['max_count'], 10)
        self.assertGreater(found, 20)
        row = self.give(10)
        fields = inventory.di_params(row)
        name, decoded = protocol.decode(protocol.encode('ss_di_heal', **fields))
        self.assertEqual((name, decoded['size'], decoded['use_count']), ('ss_di_heal', 10, 1))
        self.assertEqual(inventory.weight_of(row), 10 * items.params_of(6055)['weight'])
        self.assertEqual(self.inv.total_weight(), inventory.weight_of(row))
        charged = self.give(10, 7100)
        self.assertEqual((charged['count'], charged['use_count']), (1, 20))

    async def test_split_merge_and_repeated_merge_conserve_doses_and_weight(self):
        row = self.give(10)
        weight = self.inv.total_weight()
        self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), num=3))
        self.assertEqual(self.ack(), inventory.RES_OK)
        self.assertEqual(sorted(r['count'] for r in self.inv.rows()), [3, 7])
        donor = next(r for r in self.inv.rows() if r['uniq'] != row['uniq'])
        command = dict(obj=inventory.oid_of(row), trg=inventory.oid_of(donor), num=3)
        self.inv.ss_heap_c(command)
        self.assertEqual(self.ack(), inventory.RES_OK)
        self.inv.ss_heap_c(command)
        self.assertNotEqual(self.ack(), inventory.RES_OK)
        self.assertEqual(self.quantities(), [(row['uniq'], 10, 1, inventory.BAG)])
        self.assertEqual(self.inv.total_weight(), weight)

    async def test_bad_counts_foreign_locked_and_bank_stacks_do_not_mutate(self):
        row, donor = self.give(4), self.give(6)
        for count in (-1, 1.5, True, False, None, '', 'bad', '1.5'):
            before = self.quantities()
            self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), trg=inventory.oid_of(donor), num=count))
            self.assertNotEqual(self.ack(), inventory.RES_OK)
            self.assertEqual(self.quantities(), before)
        for state in ('foreign', 'locked', 'bank', 'used'):
            self.store.update_item(donor['uniq'], char_id=self.cid, slot=inventory.BAG, use_count=1)
            self.inv.locked.clear()
            if state == 'locked':
                self.inv.locked.add(donor['uniq'])
            else:
                fields = {'foreign': dict(char_id=self.other), 'bank': dict(slot=inventory.BANK),
                          'used': dict(use_count=0)}[state]
                self.store.update_item(donor['uniq'], **fields)
            before = self.store.items_of(self.cid) + self.store.items_of(self.other)
            self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), trg=inventory.oid_of(donor), num=2))
            self.assertNotEqual(self.ack(), inventory.RES_OK)
            self.assertEqual(self.store.items_of(self.cid) + self.store.items_of(self.other), before)

    async def test_split_creation_failure_rolls_back_and_emits_only_failure(self):
        row = self.give(10)
        before = self.quantities()
        with patch.object(self.store, 'create_item', side_effect=RuntimeError('injected')), \
                self.assertLogs('lava', level=logging.ERROR):
            self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), num=3))
        self.assertEqual(self.quantities(), before)
        self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])

    async def test_merge_delete_failure_rolls_back_recipient_increase(self):
        row, donor = self.give(4), self.give(6)
        before = self.quantities()
        with patch.object(self.store, 'delete_item', side_effect=RuntimeError('injected')), \
                self.assertLogs('lava', level=logging.ERROR):
            self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), trg=inventory.oid_of(donor), num=6))
        self.assertEqual(self.quantities(), before)
        self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])

    async def test_partial_merge_second_update_failure_rolls_back_both_rows(self):
        row, donor = self.give(4), self.give(6)
        before = self.quantities()
        real = self.store.update_item
        def update(uniq, **fields):
            if uniq == donor['uniq']:
                raise RuntimeError('injected after recipient write')
            real(uniq, **fields)
        with patch.object(self.store, 'update_item', side_effect=update), \
                self.assertLogs('lava', level=logging.ERROR):
            self.inv.ss_heap_c(dict(obj=inventory.oid_of(row), trg=inventory.oid_of(donor), num=3))
        self.assertEqual(self.quantities(), before)
        self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])

    async def test_bank_combines_and_withdraws_as_valid_stacks_without_changing_charges(self):
        rows = [self.give(10) for _ in range(3)]
        for row in rows:
            bank_storage.transfer(self.inv, inventory.oid_of(row), 10, 10, True)
        banked = self.inv.banked()
        self.assertEqual([(r['count'], r['use_count']) for r in banked], [(30, 1)])
        self.assertEqual(self.inv.total_weight(), 0)
        bank_storage.transfer(self.inv, inventory.oid_of(banked[0]), 25, 30, False)
        self.assertEqual(sorted(r['count'] for r in self.inv.rows() if r['slot'] == inventory.BAG), [5, 10, 10])
        self.assertTrue(all(r['use_count'] == 1 for r in self.inv.rows()))
        self.assertEqual(sum(r['count'] for r in self.inv.rows()), 30)
        self.assertEqual(self.inv.total_weight(), 25 * items.params_of(6055)['weight'])

    async def test_each_completion_spends_one_dose_and_final_dose_removes_the_id(self):
        row = self.give(3)
        for remaining in (2, 1, 0):
            self.character.hp = 10
            self.complete(row)
            self.assertGreater(self.character.hp, 10)
            current = self.store.item(row['uniq'])
            self.assertEqual(current['count'] if current else 0, remaining)
            if current:
                self.assertEqual(current['use_count'], 1)
        self.frames.clear()
        self.character.hp = 10
        self.complete(row)
        self.assertEqual(self.character.hp, 10)
        self.assertEqual(self.frames, [('actionCancel', dict(release=1))])

    async def test_battle_repeated_completion_cannot_bypass_shared_cooldown(self):
        row = self.give(3)
        self.room.ws = True
        self.complete(row)
        self.assertEqual(self.store.item(row['uniq'])['count'], 2)
        self.character.hp = 10
        self.complete(row, 101)
        self.assertEqual((self.character.hp, self.store.item(row['uniq'])['count']), (10, 2))
        self.assertEqual(battle_medicine.remaining_ms(self.store, self.cid, 101), 2000)

    async def test_completion_rejects_banked_offered_spent_or_foreign_medicine(self):
        for state in ('bank', 'locked', 'spent', 'empty', 'foreign'):
            row = self.give(3)
            if state == 'locked':
                self.inv.locked.add(row['uniq'])
            else:
                fields = {'bank': dict(slot=inventory.BANK), 'spent': dict(use_count=0),
                          'empty': dict(count=0), 'foreign': dict(char_id=self.other)}[state]
                self.store.update_item(row['uniq'], **fields)
            before = self.store.item(row['uniq'])
            self.frames.clear()
            self.complete(row)
            self.assertEqual(self.character.hp, 10, state)
            self.assertEqual(self.store.item(row['uniq']), before, state)
            self.assertEqual(self.frames, [('actionCancel', dict(release=1))], state)

    async def test_failed_dose_write_grants_no_health_ap_or_cooldown(self):
        for count, method in ((1, 'delete_item'), (3, 'update_item')):
            row = self.give(count)
            before = self.store.item(row['uniq'])
            self.room.ws = True
            self.frames.clear()
            with patch.object(self.store, method, side_effect=RuntimeError('injected')), \
                    self.assertLogs('lava', level=logging.ERROR):
                with patch.object(combat, 'now', return_value=100):
                    self.fighter.heal_now(row['uniq'], self.fighter, None, 5)
            self.assertEqual((self.character.hp, self.fighter.ap), (10, 100))
            self.assertEqual(self.store.item(row['uniq']), before)
            self.assertEqual(battle_medicine.remaining_ms(self.store, self.cid, 100), 0)
            self.assertEqual(self.frames, [('actionCancel', dict(release=1))])

    async def test_death_loss_is_identical_to_individual_doses_and_ground_preserves_state(self):
        row = self.give(10)
        for seed in range(100):
            separate = random.Random(seed)
            self.assertEqual(combat.bag_share(row, random.Random(seed)),
                             sum(combat.bag_share(dict(row, count=1), separate) for _ in range(10)))
        dropped = self.store.drop_items(self.cid, [(row, 3)], combat.LOOT_OWNER, inventory.BAG)
        self.assertEqual((self.store.item(row['uniq'])['count'], dropped[0]['count'], dropped[0]['use_count']), (7, 3, 1))
        self.store.pick_up([dropped[0]['uniq']], self.cid, inventory.BAG)
        self.assertEqual(sum(r['count'] for r in self.inv.rows()), 10)
        self.assertTrue(all(r['use_count'] == 1 for r in self.inv.rows()))

    async def test_mail_snapshot_and_barter_transfer_preserve_count_and_dose_state(self):
        row = self.give(7)
        snapshot = json.loads(json.dumps(mail.snapshot(row)))
        self.assertEqual((snapshot['count'], snapshot['use_count']), (7, 1))
        self.assertEqual(mail.describe(snapshot), '=?HS:7?=')
        self.assertIsNone(self.store.barter_swap([(row, self.other)], []))
        moved = self.store.item(row['uniq'])
        self.assertEqual((moved['char_id'], moved['count'], moved['use_count']), (self.other, 7, 1))
        self.assertIsNotNone(self.store.barter_swap([(row, self.other)], []))
        self.assertEqual(self.store.item(row['uniq']), moved)

    async def test_purchase_quantity_one_to_ten_is_validated_before_payment(self):
        self.inv.trade = inventory.TradeSession(1, 202, 185)
        self.store.set_money(self.cid, 1_000_000, 10000)
        self.character.afro, self.character.gold = 1_000_000, 10000
        index = format(items.stock_for(202, 185).index(6055), 'x')
        rates = dict(pmod=1, smod=.7, rmod=1)
        with patch.object(self.inv, 'current_trade_rates', return_value=rates):
            before = (self.quantities(), self.store.money(self.cid))
            for n in (0, -1, 11, 1.5, True, None, 'bad'):
                self.inv.buy(dict(obj=index, param=n), inventory.UPD_BUY)
                self.assertNotEqual(self.ack(), inventory.RES_OK, n)
                self.assertEqual((self.quantities(), self.store.money(self.cid)), before, n)
            for n in (1, 10):
                self.inv.buy(dict(obj=index, param=n), inventory.UPD_BUY)
                self.assertEqual(self.ack(), inventory.RES_OK)
        self.assertEqual(sorted(r['count'] for r in self.inv.rows()), [1, 10])
        self.assertEqual(self.store.money(self.cid)[0], 1_000_000 - 11 * items.params_of(6055)['cost'])

    async def test_overweight_and_failed_purchase_leave_money_and_doses_unchanged(self):
        self.inv.trade = inventory.TradeSession(1, 202, 185)
        self.store.set_money(self.cid, 1_000_000, 10000)
        self.character.afro, self.character.gold = 1_000_000, 10000
        command = dict(obj=format(items.stock_for(202, 185).index(6055), 'x'), param=10)
        before = (self.quantities(), self.store.money(self.cid))
        with patch.object(self.inv, 'current_trade_rates', return_value=dict(pmod=1, smod=.7, rmod=1)):
            with patch.object(self.inv, 'carry_limit', return_value=9 * items.params_of(6055)['weight']):
                self.inv.buy(command, inventory.UPD_BUY)
                self.assertEqual(self.ack(), inventory.RES_OVERLOAD)
                self.assertEqual((self.quantities(), self.store.money(self.cid)), before)
            self.frames.clear()
            with patch.object(self.store, 'create_item', side_effect=RuntimeError('injected')), \
                    self.assertLogs('lava', level=logging.ERROR):
                self.inv.buy(command, inventory.UPD_BUY)
        self.assertEqual((self.quantities(), self.store.money(self.cid)), before)
        self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])

    def send_parcel(self, row):
        self.store.set_money(self.cid, 10000, 100)
        self.character.afro, self.character.gold = 10000, 100
        self.sess.nick = 'MedicineStacks'
        self.sess.push_money = lambda: None
        box = mail.Mail(self.sess, self.store, NS(by_pid=lambda pid: None))
        box.sndml(dict(to='MedicineRecipient', type=mail.LETTER, item=inventory.oid_of(row)))
        self.assertEqual(self.ack(), mail.RES_OK)
        self.assertIsNone(self.store.item(row['uniq']))
        return box, self.store.mail_inbox(self.other)[0]

    def receive_as_other(self):
        self.sess.char_id = self.other
        other = progression.Character.load(self.store, self.other)
        self.sess.character = lambda: other

    async def test_real_mail_send_unpack_and_repeated_requests_preserve_exact_doses(self):
        row = self.give(7)
        box, letter = self.send_parcel(row)
        box.sndml(dict(to='MedicineRecipient', type=mail.LETTER, item=inventory.oid_of(row)))
        self.assertEqual(len(self.store.mail_inbox(self.other)), 1)
        self.receive_as_other()
        box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.ack(), mail.RES_OK)
        rows = self.store.items_of(self.other)
        self.assertEqual([(r['count'], r['use_count']) for r in rows], [(7, 1)])
        box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.store.items_of(self.other), rows)
        self.assertFalse(mail.attached(self.store.mail_letter(letter['id'])))

    async def test_mail_failure_after_recreating_stack_rolls_back_and_remains_claimable(self):
        box, letter = self.send_parcel(self.give(7))
        self.receive_as_other()
        self.frames.clear()
        with patch.object(self.store, 'mail_update', side_effect=RuntimeError('injected after create')), \
                self.assertLogs('lava', level=logging.ERROR):
            box.uldml(dict(id=str(letter['id'])))
        self.assertEqual(self.store.items_of(self.other), [])
        self.assertTrue(mail.attached(self.store.mail_letter(letter['id'])))
        self.assertEqual(self.frames, [('cmdAck', dict(res=mail.RES_REFUSED))])
        box.uldml(dict(id=str(letter['id'])))
        self.assertEqual([(r['count'], r['use_count']) for r in self.store.items_of(self.other)], [(7, 1)])


if __name__ == '__main__':
    run_cases(MedicineStacks)
