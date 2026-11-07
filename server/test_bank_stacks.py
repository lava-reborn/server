"""Short real-database bank transactions: quantities, state, rollback and weight."""
import unittest
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
        aid, _ = self.store.register('bank-stacks', 'test-only')
        self.cid, _ = self.store.create_character(aid, 'BankStacks', 0, '1')
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


if __name__ == '__main__':
    run_cases(BankStacks)
