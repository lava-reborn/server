"""Old valentine parcels/lots migrate atomically on SQLite and PostgreSQL."""
import json
import time
import unittest
import uuid
from unittest.mock import patch

import accounts
import inventory
import items
import mail
from testkit import run_cases


class HandGiftStorage(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        # PostgreSQL keeps this suite's database between test methods.
        self.store.db.execute('DELETE FROM migrations WHERE name=?',
                              (inventory.HAND_VALENTINE_SNAPSHOTS_FIX,))
        self.store.db.commit()
        aid, _ = self.store.register('gift-' + uuid.uuid4().hex[:12], 'test-only')
        self.cid, _ = self.store.create_character(aid, 'Gift' + uuid.uuid4().hex[:8], 0, '1')

    def snapshot(self, type_id=1069):
        row = self.store.create_item(self.cid, type_id, items.WEAR, slot=inventory.BAG,
                                     count=1, brk=123, max_break_cur=30000)
        snap = mail.snapshot(row)
        self.store.delete_item(row['uniq'])
        return snap

    def lot(self, type_id=1070):
        row = self.store.create_item(self.cid, type_id, items.WEAR, slot=inventory.BAG,
                                     count=1, brk=456, max_break_cur=30000)
        now = time.time()
        return self.store.auction_list(row['uniq'], self.cid, dict(
            type_id=type_id, root=items.WEAR, item_json=json.dumps(mail.snapshot(row)),
            seller=self.cid, seller_name='GiftSeller', currency=1, start_bid=100,
            buyout=200, fee=0, hours=24, created_at=int(now), ends_at=now + 86400))

    def migrate(self):
        return accounts.run_once(self.store.db, inventory.HAND_VALENTINE_SNAPSHOTS_FIX,
                                 inventory.repair_hand_valentine_snapshots)

    def test_all_gifts_mixed_parcels_and_auction_rows_keep_every_nonclass_field(self):
        snapshots = [self.snapshot(t) for t in items.HAND_VALENTINES]
        ordinary = dict(snapshots[0], type_id=3722)
        parcel = self.store.mail_send(self.cid, self.cid, mail.TRADE,
                                      'legacy', 'unchanged body', 321, 45,
                                      json.dumps(snapshots + [ordinary]))
        lot = self.lot()
        self.assertTrue(self.migrate())
        after_parcel = self.store.mail_letter(parcel['id'])
        expected = [dict(s, root=items.COLD_ARM) for s in snapshots] + [ordinary]
        self.assertEqual(json.loads(after_parcel['items_json']), expected)
        self.assertEqual({k: v for k, v in after_parcel.items() if k != 'items_json'},
                         {k: v for k, v in parcel.items() if k != 'items_json'})
        after_lot = self.store.auction_lot(lot['id'])
        self.assertEqual(json.loads(after_lot['item_json']),
                         dict(json.loads(lot['item_json']), root=items.COLD_ARM))
        self.assertEqual({k: v for k, v in after_lot.items() if k not in ('root', 'item_json')},
                         {k: v for k, v in lot.items() if k not in ('root', 'item_json')})
        self.assertEqual(after_lot['root'], items.COLD_ARM)
        self.assertFalse(self.migrate())
        self.assertEqual(self.store.mail_letter(parcel['id']), after_parcel)
        self.assertEqual(self.store.auction_lot(lot['id']), after_lot)
        # Re-running the repair itself is harmless too.
        with self.store.db:
            inventory.repair_hand_valentine_snapshots(self.store.db)
        self.assertEqual(self.store.mail_letter(parcel['id']), after_parcel)
        self.assertEqual(self.store.auction_lot(lot['id']), after_lot)

    def test_failure_after_parcel_write_rolls_back_the_lot_and_migration_marker(self):
        parcel = self.store.mail_send(self.cid, self.cid, mail.LETTER, 'old', 'old',
                                      0, 0, json.dumps([self.snapshot()]))
        lot = self.lot()
        execute = self.store.db.execute
        def fail_on_lot(sql, args=()):
            if sql.startswith('UPDATE auction_lots SET root='):
                raise RuntimeError('interrupted snapshot repair')
            return execute(sql, args)
        with patch.object(self.store.db, 'execute', side_effect=fail_on_lot):
            with self.assertRaisesRegex(RuntimeError, 'interrupted snapshot repair'):
                self.migrate()
        self.assertEqual(self.store.mail_letter(parcel['id']), parcel)
        self.assertEqual(self.store.auction_lot(lot['id']), lot)
        self.assertFalse(accounts.ran(self.store.db, inventory.HAND_VALENTINE_SNAPSHOTS_FIX))
        self.assertTrue(self.migrate())
        self.assertEqual(self.store.auction_lot(lot['id'])['root'], items.COLD_ARM)


if __name__ == '__main__':
    run_cases(HandGiftStorage)
