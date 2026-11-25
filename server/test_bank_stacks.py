"""Short real-database bank transactions: quantities, state, rollback and weight."""
import unittest
import uuid
import logging
logging.disable(logging.CRITICAL)
from types import SimpleNamespace as NS
from unittest.mock import patch

import accounts
import bank_storage
import combat
import inventory
import items
from testkit import run_cases


class BankStacks(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        aid, _ = self.store.register('bank-' + uuid.uuid4().hex[:12], 'test-only')
        self.cid, _ = self.store.create_character(aid, 'Bank' + uuid.uuid4().hex[:10], 0, '1')
        self.frames = []
        self.sess = NS(char_id=self.cid, send=lambda c, **p: self.frames.append((c,p)),
                       say=lambda text: None, character=lambda: NS(max_weight=lambda: 1_000_000))
        self.inv = inventory.Inventory(self.sess, self.store)
        self.inv.bank_max = lambda: 1_000_000

    def make(self, count, slot=inventory.BAG, type_id=2258, **state):
        fields = inventory.new_fields(type_id)
        root = fields.pop('root')
        fields.update(slot=slot, count=count, **state)
        return self.store.create_item(self.cid, type_id, root, **fields)

    def move(self, row, n, putting=True):
        return bank_storage.transfer(self.inv, inventory.oid_of(row), n, row['count'], putting)

    def test_put_merges_and_get_splits_to_bag_limit_without_loss(self):
        a = self.make(100, inventory.BANK)
        b = self.make(50)
        self.move(b, 50)
        rows = self.store.items_of(self.cid)
        self.assertEqual([(r['slot'],r['count']) for r in rows], [(inventory.BANK,150)])
        self.move(rows[0], 150, False)
        self.assertEqual(sorted(r['count'] for r in self.store.items_of(self.cid)), [50,100])

    def test_every_timed_buff_consolidates_in_bank_and_returns_as_individual_bag_items(self):
        import effects
        for type_id in effects.definitions():
            if items.root_of(type_id) != items.HEAL:
                continue
            with self.subTest(type_id=type_id):
                self.assertFalse(items.heapable(type_id))
                first = self.make(1, type_id=type_id)
                second = self.make(1, type_id=type_id)
                before_money = self.store.money(self.cid)
                self.move(first, 1)
                self.move(second, 1)
                bank = [row for row in self.store.items_of(self.cid) if row['type_id'] == type_id]
                self.assertEqual([(row['slot'], row['count']) for row in bank], [(inventory.BANK, 2)])
                self.assertEqual(inventory.weight_of(bank[0]), items.params_of(type_id)['weight'] * 2)
                self.move(bank[0], 1, False)
                bank = next(row for row in self.store.items_of(self.cid) if row['type_id'] == type_id and row['slot'] == inventory.BANK)
                self.move(bank, 1, False)
                rows = [row for row in self.store.items_of(self.cid) if row['type_id'] == type_id]
                self.assertEqual([(row['slot'], row['count']) for row in rows], [(inventory.BAG, 1)] * 2)
                self.assertEqual({row['use_count'] for row in rows}, {first['use_count']})
                self.assertEqual(self.store.money(self.cid), before_money)
                for row in rows:
                    self.store.delete_item(row['uniq'])

    def test_buff_withdrawal_rollback_preserves_doses_character_and_request_retry(self):
        row = self.make(4, inventory.BANK, 3561)
        before = self.store.items_of(self.cid)
        character = self.store.character(self.cid)
        create = self.store.create_item
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('second individual buff write failed')
            return create(*args, **kwargs)
        request = dict(obj=inventory.oid_of(row), bank_count=4, bank_expected=4, bank_request=1)
        with patch.object(self.store, 'create_item', side_effect=fail_second), patch.object(inventory.log, 'exception'):
            self.inv.bank_get(request)
        self.assertEqual(self.store.items_of(self.cid), before)
        self.assertEqual(self.store.character(self.cid), character)
        self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])
        # A rolled-back request has no committed token: the same request may succeed once.
        self.inv.bank_get(request)
        self.inv.bank_get(request)
        self.assertEqual([(r['slot'], r['count']) for r in self.store.items_of(self.cid)], [(inventory.BAG, 1)] * 4)
        self.assertEqual(self.store.character(self.cid), character)

    def test_legacy_withdrawal_cannot_put_a_bank_buff_heap_in_the_bag(self):
        row = self.make(3, inventory.BANK, 3561)
        self.inv.bank_legacy_transfer(dict(obj=inventory.oid_of(row)), False)
        self.assertEqual(self.store.item(row['uniq']), row)
        self.assertEqual(self.frames[-1], ('cmdAck', dict(res=inventory.RES_REFUSED)))


    def test_buff_payment_and_instances_commit_or_roll_back_together_on_both_databases(self):
        type_id = 3561
        self.store.set_money(self.cid, 12345, 1_000_000)
        ch = NS(afro=12345, gold=1_000_000, max_weight=lambda: 1_000_000)
        self.sess.character = lambda: ch
        self.sess.send_player_info = lambda: None
        self.inv.trade = inventory.TradeSession(1, 1188, 36)
        with patch.object(items, 'stock_for', return_value=[type_id]), \
                patch.object(self.inv, 'current_trade_rates', return_value=dict(pmod=1, smod=.7, rmod=1)):
            for _ in range(2):
                self.inv.buy(dict(obj='0', param=1), inventory.UPD_BUY_GOLD)
                self.assertEqual([p['res'] for c, p in self.frames if c == 'cmdAck'][-1], inventory.RES_OK)
            rows = self.store.items_of(self.cid)
            self.assertEqual([(row['slot'], row['count']) for row in rows], [(inventory.BAG, 1)] * 2)
            self.assertEqual(self.store.money(self.cid), (12345, 1_000_000-2*items.params_of(type_id)['g_cost']))
            before = self.store.money(self.cid)
            create = self.store.create_item
            writes = 0
            def fail_second(*args, **kwargs):
                nonlocal writes
                writes += 1
                if writes == 2:
                    raise RuntimeError('second purchased buff failed')
                return create(*args, **kwargs)
            self.frames.clear()
            with patch.object(self.store, 'create_item', side_effect=fail_second), \
                    patch.object(inventory.log, 'exception'):
                self.inv.buy(dict(obj='0', param=2), inventory.UPD_BUY_GOLD)
            self.assertEqual(self.frames, [('cmdAck', dict(res=inventory.RES_REFUSED))])
            self.assertEqual(self.store.money(self.cid), before)
            self.assertEqual(self.store.items_of(self.cid), rows)
            self.assertEqual((ch.afro, ch.gold), before)

    def test_partial_transfer_preserves_remaining_source_and_all_state(self):
        row = self.make(70, use_count=5)
        self.move(row, 20)
        self.assertEqual(self.store.item(row['uniq'])['count'], 50)
        self.assertEqual({r['use_count'] for r in self.store.items_of(self.cid)}, {5})
        self.assertEqual(sum(r['count'] for r in self.store.items_of(self.cid)),70)

    def test_changed_charges_and_equipment_never_consolidate(self):
        self.make(10, inventory.BANK, use_count=1)
        self.make(10, inventory.BANK, use_count=2)
        self.make(1, inventory.BANK, 25562)
        self.make(1, inventory.BANK, 25562)
        bank_storage.consolidate(self.store, self.cid, inventory.BANK)
        self.assertEqual(len(self.store.items_of(self.cid)),4)

    def test_overweight_refuses_both_directions_without_mutations(self):
        row = self.make(20)
        original = self.store.items_of(self.cid)
        self.inv.bank_max = lambda: 0
        with self.assertRaises(bank_storage.Refused):
            self.move(row, 10)
        self.assertEqual(self.store.items_of(self.cid),original)
        self.store.update_item(row['uniq'],slot=inventory.BANK)
        row = self.store.item(row['uniq'])
        self.inv.carry_limit = lambda: 0
        with self.assertRaises(bank_storage.Refused):
            self.move(row, 10, False)
        self.assertEqual(self.store.item(row['uniq']), row)

    def test_failure_after_destination_update_rolls_everything_back(self):
        self.make(20, inventory.BANK)
        row = self.make(20)
        before = self.store.items_of(self.cid)
        with patch.object(self.store, 'delete_item', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.move(row, 20)
        self.assertEqual(self.store.items_of(self.cid),before)

    def test_repeated_and_stale_quantity_requests_cannot_duplicate(self):
        row = self.make(50)
        p = dict(obj=inventory.oid_of(row),bank_count=10,bank_expected=50,bank_request=1)
        self.inv.bank_put(p)
        self.inv.bank_put(p)
        p['bank_request'] = 2
        self.inv.bank_put(p)
        self.assertEqual(sorted((r['slot'],r['count']) for r in self.store.items_of(self.cid)),
                         [(inventory.BAG,40),(inventory.BANK,10)])
        self.assertEqual([p['res'] for c,p in self.frames if c=='cmdAck'], [0,0,inventory.RES_REFUSED])

    def assert_committed_result(self, before, result):
        after={r['uniq']:r for r in self.store.items_of(self.cid)}
        expected=[(before.get(u),after.get(u)) for u in sorted(before.keys() | after.keys())
                  if before.get(u)!=after.get(u)]
        self.assertEqual(result.changes,expected)
        self.assertEqual(result.bank_weight,
                         sum(inventory.weight_of(r) for r in after.values() if r['slot']==inventory.BANK))

    def test_committed_delta_and_weight_match_actual_rows_through_partial_and_full_moves(self):
        self.make(80, inventory.BANK)
        source=self.make(70)
        for putting,n in ((True,30),(False,15),(True,25),(False,140)):
            rows=self.store.items_of(self.cid)
            slot=inventory.BAG if putting else inventory.BANK
            row=next(r for r in rows if r['slot']==slot)
            n=min(n,row['count'])
            before={r['uniq']:r for r in rows}
            result=self.move(row,n,putting)
            self.assert_committed_result(before,result)
            self.assertEqual(sum(r['count'] for r in self.store.items_of(self.cid)),150)
        gear=self.make(1,type_id=25562)
        before={r['uniq']:r for r in self.store.items_of(self.cid)}
        self.assert_committed_result(before,self.move(gear,1))

    def test_consolidation_error_rolls_back_every_stack(self):
        self.make(10,inventory.BANK)
        self.make(20,inventory.BANK)
        self.make(30,inventory.BANK)
        before=self.store.items_of(self.cid)
        real=self.store.delete_item
        deleted=[]
        def fail_second(uniq):
            deleted.append(uniq)
            if len(deleted)==2:
                raise RuntimeError('injected after first delete')
            real(uniq)
        with patch.object(self.store,'delete_item',side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                bank_storage.consolidate(self.store,self.cid,inventory.BANK)
        self.assertEqual(self.store.items_of(self.cid),before)

    def test_consolidation_preserves_integer_boundaries_and_row_identity(self):
        first=self.make(bank_storage.MAX_COUNT-5,inventory.BANK)
        self.make(3,inventory.BANK)
        overflow=self.make(10,inventory.BANK)
        self.make(20,inventory.BANK)
        bank_storage.consolidate(self.store,self.cid,inventory.BANK)
        rows=self.store.items_of(self.cid)
        self.assertEqual([(r['uniq'],r['count']) for r in rows],
                         [(first['uniq'],bank_storage.MAX_COUNT-2),(overflow['uniq'],30)])

    def test_bank_never_enters_death_losses_and_100_stack_does_not_increase_loss(self):
        row = self.make(100,inventory.BANK)
        self.assertEqual(combat.death_losses([row]),[])
        two_old = sum(combat.bag_share(dict(row,slot=inventory.BAG,count=50)) for _ in range(2))
        one_new = combat.bag_share(dict(row,slot=inventory.BAG))
        self.assertEqual((two_old,one_new),(34,33))


    def test_scanner_and_intux_variants_remain_distinct_after_reopen_and_round_trip(self):
        import effects
        types = effects.SCANNERS + effects.EXPERIENCE_UP
        for type_id in types:
            self.make(2, inventory.BANK, type_id)
            self.move(self.make(1, type_id=type_id), 1)
        # Reopening is idempotent, including the serials advertised to the client.
        before = self.store.items_of(self.cid)
        for _ in range(3):
            bank_storage.consolidate(self.store, self.cid, inventory.BANK)
            self.assertEqual(self.store.items_of(self.cid), before)
        self.assertEqual({r['type_id']: r['count'] for r in before}, dict.fromkeys(types, 3))
        for row in before:
            self.move(row, 3, False)
        rows = self.store.items_of(self.cid)
        for type_id in types:
            group = [r for r in rows if r['type_id'] == type_id]
            self.assertEqual([(r['slot'], r['count']) for r in group], [(inventory.BAG, 1)] * 3)
        self.assertEqual(len({r['uniq'] for r in rows}), len(types) * 3)

    def test_bank_buffs_have_no_catalogue_stack_cap_and_preserve_overflow(self):
        import effects
        self.inv.bank_max = lambda: 10**18
        for type_id in effects.SCANNERS + effects.EXPERIENCE_UP:
            with self.subTest(type_id=type_id):
                first = self.make(bank_storage.MAX_COUNT - 1, inventory.BANK, type_id)
                for _ in range(3):
                    self.move(self.make(1, type_id=type_id), 1)
                bank_storage.consolidate(self.store, self.cid, inventory.BANK)
                rows = [r for r in self.store.items_of(self.cid) if r['type_id'] == type_id]
                self.assertEqual([r['count'] for r in rows], [bank_storage.MAX_COUNT, 2])
                self.assertEqual(rows[0]['uniq'], first['uniq'])
                self.assertEqual(sum(r['count'] for r in rows), bank_storage.MAX_COUNT + 2)

    def test_no_buff_state_field_is_lost_or_merged_with_a_different_state(self):
        original = self.make(1, inventory.BANK, 3561)
        for field in bank_storage.STATE:
            row = self.make(1, type_id=3561)
            self.store.update_item(row['uniq'], **{field: row[field] + 1})
            row = self.store.item(row['uniq'])
            self.move(row, 1)
            self.assertEqual(self.store.item(row['uniq']), dict(row, slot=inventory.BANK))
        bank_storage.consolidate(self.store, self.cid, inventory.BANK)
        self.assertEqual(self.store.item(original['uniq']), original)
        self.assertEqual(len(self.store.items_of(self.cid)), len(bank_storage.STATE) + 1)

    def test_buying_every_buff_leaves_bank_untouched_and_charges_exact_delivered_quantity(self):
        import effects
        self.sess.send_player_info = lambda: None
        self.inv.trade = inventory.TradeSession(1, 1188, 36)
        ch = NS(afro=0, gold=0, max_weight=lambda: 1_000_000)
        self.sess.character = lambda: ch
        for type_id in effects.definitions():
            si = items.params_of(type_id)
            if items.root_of(type_id) != items.HEAL or not si:
                continue
            for gold in (False, True):
                if not si.get('g_cost' if gold else 'cost'):
                    continue
                with self.subTest(type_id=type_id, gold=gold):
                    self.store.set_money(self.cid, 100_000_000, 1_000_000)
                    before_money = self.store.money(self.cid)
                    ch.afro, ch.gold = before_money
                    bank = self.make(5, inventory.BANK, type_id)
                    before_ids = {r['uniq'] for r in self.store.items_of(self.cid)}
                    with patch.object(items, 'stock_for', return_value=[type_id]), \
                            patch.object(self.inv, 'current_trade_rates', return_value=dict(pmod=.9, smod=.7, rmod=1)):
                        self.frames.clear()
                        self.inv.buy(dict(obj='0', param=2), inventory.UPD_BUY_GOLD if gold else inventory.UPD_BUY)
                    self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'], [inventory.RES_OK])
                    bought = [r for r in self.store.items_of(self.cid) if r['uniq'] not in before_ids]
                    self.assertEqual([(r['type_id'], r['slot'], r['count']) for r in bought],
                                     [(type_id, inventory.BAG, 1)] * 2)
                    self.assertEqual(self.store.item(bank['uniq']), bank)
                    expected_money = list(before_money)
                    expected_money[int(gold)] -= inventory.buy_price(si, items.HEAL, 2, gold, .9)
                    self.assertEqual(self.store.money(self.cid), tuple(expected_money))
                    self.assertEqual((ch.afro, ch.gold), tuple(expected_money))
                    for row in bought:
                        self.move(row, 1)
                    bank = self.store.item(bank['uniq'])
                    self.assertEqual(bank['count'], 7)
                    self.move(bank, 2, False)
                    rows = [r for r in self.store.items_of(self.cid) if r['type_id'] == type_id]
                    self.assertEqual(sorted((r['slot'], r['count']) for r in rows),
                                     sorted([(inventory.BANK, 5)] + [(inventory.BAG, 1)] * 2))
                    self.assertEqual(self.store.money(self.cid), tuple(expected_money))
                    for row in rows:
                        self.store.delete_item(row['uniq'])

    def test_forged_wrong_slot_locked_and_stale_buff_transfers_change_nothing(self):
        row = self.make(5, inventory.BANK, 3561)
        aid, _ = self.store.register('other-' + uuid.uuid4().hex[:12], 'test-only')
        other, _ = self.store.create_character(aid, 'Other' + uuid.uuid4().hex[:10], 0, '1')
        foreign = self.store.create_item(other, 3561, items.HEAL, slot=inventory.BANK, count=5)
        forged = inventory.oid_of(dict(row, type_id=3789))
        before = self.store.items_of(self.cid)
        for obj, n, expected, putting in ((inventory.oid_of(foreign), 1, 5, False),
                (forged, 1, 5, False), (inventory.oid_of(row), 1, 5, True),
                (inventory.oid_of(row), 1, 4, False), (inventory.oid_of(row), 0, 5, False),
                (inventory.oid_of(row), 6, 5, False)):
            with self.subTest(obj=obj, n=n, expected=expected, putting=putting):
                with self.assertRaises(bank_storage.Refused):
                    bank_storage.transfer(self.inv, obj, n, expected, putting)
                self.assertEqual(self.store.items_of(self.cid), before)
        self.inv.locked.add(row['uniq'])
        with self.assertRaises(bank_storage.Refused):
            self.move(row, 1, False)
        self.assertEqual(self.store.items_of(self.cid), before)
        self.assertEqual(self.store.item(foreign['uniq']), foreign)

    def test_same_token_cannot_be_reused_for_another_buff_or_direction(self):
        first = self.make(1, type_id=3561)
        second = self.make(1, type_id=3789)
        request = dict(obj=inventory.oid_of(first), bank_count=1, bank_expected=1, bank_request=1)
        self.inv.bank_put(request)
        before = self.store.items_of(self.cid)
        self.inv.bank_put(dict(request, obj=inventory.oid_of(second)))
        self.inv.bank_get(request)
        self.inv.bank_put(request)
        self.assertEqual(self.store.items_of(self.cid), before)
        self.assertEqual([p['res'] for cmd, p in self.frames if cmd == 'cmdAck'],
                         [inventory.RES_OK, inventory.RES_REFUSED, inventory.RES_REFUSED, inventory.RES_OK])

    def test_concurrent_withdrawals_of_one_buff_stack_commit_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        import tempfile
        import threading
        # Two independent connections to the same database, also on SQLite.
        with tempfile.TemporaryDirectory(prefix='lava-bank-race-') as temporary:
            path = str(Path(temporary) / 'race.sqlite')
            store = accounts.Store(path)
            try:
                aid, _ = store.register('race-' + uuid.uuid4().hex[:12], 'test-only')
                cid, _ = store.create_character(aid, 'Race' + uuid.uuid4().hex[:10], 0, '1')
                row = store.create_item(cid, 3561, items.HEAL, slot=inventory.BANK, count=5, use_count=1)
                money = store.money(cid)
                ready = threading.Barrier(2)
                def withdraw():
                    connection = accounts.Store(path)
                    try:
                        inv = inventory.Inventory(NS(char_id=cid, character=lambda: NS(max_weight=lambda: 1_000_000)), connection)
                        ready.wait(timeout=15)
                        try:
                            bank_storage.transfer(inv, inventory.oid_of(row), 3, 5, False)
                            return True
                        except bank_storage.Refused:
                            return False
                    finally:
                        connection.close()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(withdraw) for _ in range(2)]
                    self.assertEqual(sorted(f.result(timeout=30) for f in futures), [False, True])
                rows = store.items_of(cid)
                self.assertEqual(sorted((r['slot'], r['count']) for r in rows),
                                 sorted([(inventory.BANK, 2)] + [(inventory.BAG, 1)] * 3))
                self.assertEqual(store.money(cid), money)
            finally:
                store.close()


if __name__ == '__main__':
    run_cases(BankStacks)
