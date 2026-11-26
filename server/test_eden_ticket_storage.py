"""Plantation coupon consolidation and delivery on SQLite and PostgreSQL."""
import unittest
import uuid
from types import SimpleNamespace as NS
from unittest.mock import patch

import accounts
import inventory
import items
import storage
from testkit import run_cases


class EdenTicketStorage(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        aid, _ = self.store.register('ticket-' + uuid.uuid4().hex[:12], 'test-only')
        self.cid, _ = self.store.create_character(aid, 'Ticket' + uuid.uuid4().hex[:8], 0, '1')
        self.other, _ = self.store.create_character(aid, 'Other' + uuid.uuid4().hex[:8], 0, '1')
        self.frames = []
        self.s = NS(char_id=self.cid, send=lambda cmd, **p: self.frames.append((cmd, p)))
        self.inv = inventory.Inventory(self.s, self.store)

    def tickets(self, type_id=4232):
        return [r for r in self.inv.rows() if r['type_id'] == type_id and r['slot'] == inventory.BAG]

    def test_repeated_rewards_merge_all_three_colours_and_send_the_new_count(self):
        for type_id in items.EDEN_TICKETS:
            self.assertTrue(items.heapable(type_id))
            self.assertEqual(items.params_of(type_id)['max_count'], items.EDEN_TICKET_STACK)
            first = self.inv.give_pieces(type_id, 1)[0]
            self.inv.give_pieces(type_id, 1000)
            self.inv.give_pieces(type_id, 1)
            rows = self.tickets(type_id)
            self.assertEqual([(row['uniq'], row['count']) for row in rows], [(first['uniq'], 1002)])
            self.assertEqual(self.frames[-1][1]['size'], 1002)
            self.assertEqual(self.inv.take_pieces(type_id, 1000), 1000)
            self.assertEqual(self.store.item(first['uniq'])['count'], 2)
            self.assertEqual(self.inv.take_pieces(type_id, 2), 2)
            self.assertIsNone(self.store.item(first['uniq']))

    def test_login_consolidates_more_than_a_thousand_legacy_rows_without_loss(self):
        with storage.atomic(self.store.db):
            legacy = [self.inv.create(4232) for _ in range(1001)]
        other_colour = self.inv.create(4231, 75)
        bank = self.inv.create(4232, 30, slot=inventory.BANK)
        foreign = self.inv.create(4232, 15, char_id=self.other)
        locked = self.inv.create(4232, 5)
        self.inv.locked.add(locked['uniq'])
        unusual = self.inv.create(4232, 3)
        self.store.update_item(unusual['uniq'], use_count=1)
        self.inv.normalize_eden_tickets()
        normal = [row for row in self.tickets() if row['uniq'] not in (locked['uniq'], unusual['uniq'])]
        self.assertEqual([(row['uniq'], row['count']) for row in normal], [(legacy[0]['uniq'], 1001)])
        for saved in (other_colour, bank, foreign, locked):
            self.assertEqual(self.store.item(saved['uniq']), saved)
        self.assertEqual(self.store.item(unusual['uniq'])['count'], 3)
        before = list(self.inv.rows())
        self.assertEqual(self.inv.normalize_eden_tickets(), [])
        self.assertEqual(list(self.inv.rows()), before)
        self.assertFalse(self.frames)  # login has not exposed any old item IDs

    def test_compaction_failure_rolls_back_counts_and_deleted_rows(self):
        for _ in range(3):
            self.inv.create(4232)
        before = list(self.inv.rows())
        execute = self.store.db.execute
        def fail_after_delete(query, params=()):
            result = execute(query, params)
            if query.startswith('DELETE FROM items'):
                raise RuntimeError('SQL failure')
            return result
        with patch.object(self.store.db, 'execute', side_effect=fail_after_delete):
            with self.assertRaises(RuntimeError):
                self.inv.normalize_eden_tickets()
        self.assertEqual(list(self.inv.rows()), before)
        self.assertFalse(self.frames)

    def test_delivery_failure_rolls_back_a_partially_filled_heap_and_sends_nothing(self):
        self.inv.create(4232, items.EDEN_TICKET_STACK - 1)
        before = list(self.inv.rows())
        with patch.object(self.inv, 'create', side_effect=RuntimeError('SQL failure')):
            with self.assertRaises(RuntimeError):
                self.inv.give_pieces(4232, 3)
        self.assertEqual(list(self.inv.rows()), before)
        self.assertFalse(self.frames)

    def test_storage_bound_creates_a_second_heap_instead_of_overflowing(self):
        first = self.inv.create(4232, items.EDEN_TICKET_STACK - 1)
        self.inv.give_pieces(4232, 3)
        self.assertEqual([r['count'] for r in self.tickets()], [items.EDEN_TICKET_STACK, 2])
        self.assertEqual(self.store.item(first['uniq'])['count'], items.EDEN_TICKET_STACK)


if __name__ == '__main__':
    run_cases(EdenTicketStorage)
