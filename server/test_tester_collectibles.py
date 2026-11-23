"""Additive exact-level collectible supplies, with native requirements and rollback."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import accounts
import inventory
import items
import progression
import storage
import tester_firearms as supplies
from testkit import run_cases


class CollectibleSupplies(unittest.TestCase):
    def test_verified_exact_tiers_exclude_placeholders_and_named_clan_copies(self):
        expected = {1: (), 2: (7055,), 3: (), 4: (7056, 7072), 5: (7057, 7073),
                    6: (7074,), 7: (7075,), 8: (7076,), 9: (7077,), 10: (7078,),
                    11: (7079,), 12: (7059, 7080), 13: (7065,), 14: (7070,),
                    15: (7066, 7081), 16: (7051, 7067), 17: (7052,)}
        for level, types in expected.items():
            self.assertEqual(supplies.collectible_arsenal(level), types)
            for type_id in types:
                self.assertEqual(inventory.item_level(type_id), level)
                self.assertFalse(items.acquisition_blocked(type_id))
        self.assertNotIn(7058, supplies.collectible_arsenal(2))  # nominal17/actual2 mismatch
        self.assertEqual(supplies.collectible_arsenal(18), ())  # release cap

    def profile(self, level):
        store = accounts.Store(':memory:')
        self.addCleanup(store.close)
        aid, _ = store.register('collectible-fixture', 'local-test')
        cid, _ = store.create_character(aid, 'CollectibleFixture', 0, '1')
        ch = progression.Character.load(store, cid)
        ch.set_skill(progression.SHOOTING, level)
        ch.save(store)
        return store, cid

    def test_addition_is_idempotent_preserves_old_items_money_and_position(self):
        store, cid = self.profile(15)
        old = store.create_item(cid, 41, items.root_of(41), **{
            key: value for key, value in inventory.new_fields(41).items() if key != 'root'})
        before = dict(store.character(cid))
        profile = supplies.plan_character(store, cid, collectibles_only=True)
        self.assertEqual([gun['type'] for gun in profile['weapons']], [7066, 7081])
        with storage.atomic(store.db):
            supplies.apply_character(store, profile)
        self.assertEqual(store.item(old['uniq']), old)
        self.assertEqual(dict(store.character(cid)), before)
        followup = supplies.plan_character(store, cid, collectibles_only=True)
        self.assertEqual(followup['item_additions'], [])
        self.assertEqual(followup['stat_updates'], [])
        for gun in followup['weapons']:
            row = store.item(gun['existing'])
            self.assertEqual(row['brk'], items.params_of(gun['type'])['max_break_abs'])
        self.assertTrue(all(row['after'] >= 400 for row in followup['ammunition']))

    def test_transaction_failure_rolls_back_whole_grant(self):
        store, cid = self.profile(12)
        profile = supplies.plan_character(store, cid, collectibles_only=True)
        before = [dict(r) for r in store.items_of(cid)]
        with self.assertRaises(RuntimeError):
            with storage.atomic(store.db):
                supplies.apply_character(store, profile)
                raise RuntimeError('after grant, before commit')
        self.assertEqual(store.items_of(cid), before)

    def test_collection_overflow_uses_bank_without_regranting_or_changing_capacity(self):
        store, cid = self.profile(16)
        with patch.object(progression.Character, 'max_weight', return_value=1):
            profile = supplies.plan_character(store, cid, collectibles_only=True)
            self.assertFalse(profile['overweight'])
            self.assertTrue(all(row['slot'] == inventory.BANK for row in profile['item_additions']))
            with storage.atomic(store.db):
                supplies.apply_character(store, profile)
            again = supplies.plan_character(store, cid, collectibles_only=True)
            self.assertEqual(again['item_additions'], [])
            self.assertEqual(again['capacity'], 1)

    def test_full_bank_uses_paid_native_expansion_without_combat_stat_changes(self):
        store, cid = self.profile(16)
        store.set_money(cid, 5000, 1000)
        before = dict(store.character(cid))
        stats = [row for row in progression.Character.load(store, cid).rows() if row[0] != 'spec']
        with patch.object(progression.Character, 'max_weight', return_value=1), \
             patch.object(inventory.Inventory, 'bank_weight', return_value=50000):
            profile = supplies.plan_character(store, cid, collectibles_only=True)
            self.assertEqual(profile['bank_steps_added'], 1)
            with storage.atomic(store.db):
                supplies.apply_character(store, profile)
            after = dict(store.character(cid))
            self.assertEqual(after['bank_steps'], before['bank_steps'] + 1)
            self.assertEqual(after['gold'], before['gold'] - inventory.BANK_STEP_GOLD)
            for key in before.keys() - {'bank_steps', 'gold'}:
                self.assertEqual(after[key], before[key], key)
            self.assertEqual([row for row in progression.Character.load(store, cid).rows() if row[0] != 'spec'], stats)

    def test_paid_expansion_and_items_roll_back_together(self):
        store, cid = self.profile(16)
        store.set_money(cid, 5000, 1000)
        before = dict(store.character(cid))
        with patch.object(progression.Character, 'max_weight', return_value=1), \
             patch.object(inventory.Inventory, 'bank_weight', return_value=50000):
            profile = supplies.plan_character(store, cid, collectibles_only=True)
        with self.assertRaises(RuntimeError):
            with storage.atomic(store.db):
                supplies.apply_character(store, profile)
                raise RuntimeError('after native expansion')
        self.assertEqual(dict(store.character(cid)), before)
        self.assertEqual(store.items_of(cid), [])


if __name__ == '__main__':
    run_cases(CollectibleSupplies)
