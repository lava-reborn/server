"""Paid specialization capacity, free replacements and atomic currency writes."""
import copy
import logging
import unittest
from unittest.mock import patch

import accounts
import progression as p
import spec_access_service as service
from testkit import run_cases

logging.disable(logging.CRITICAL)


class SpecAccess(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        aid, _ = self.store.register('spec-access', 'test-only')
        self.cid, _ = self.store.create_character(aid, 'SpecAccess', 0, '1')
        self.store.set_money(self.cid, 10000, 100000)
        self.ch = p.Character.load(self.store, self.cid)

    def action(self, idx, learn=True):
        status = p.UPD_LEARN if learn else p.UPD_FORGET
        return service.apply(self.store, self.ch, status, idx)

    def test_paid_slot_accepts_any_other_spec_after_reset_and_relogin(self):
        self.assertEqual(self.action(0), (0, (0, 0)))
        self.assertEqual(self.action(1), (0, (1000, 0)))
        self.assertEqual(self.action(2), (0, (0, 1000)))
        self.assertEqual(self.action(2, False)[0], 0)
        self.ch = p.Character.load(self.store, self.cid)
        money = self.store.money(self.cid)
        self.assertEqual(self.ch.spec_cost(), (0, 0))
        self.assertEqual(self.action(7), (0, (0, 0)))
        self.assertEqual(self.store.money(self.cid), money)
        self.assertEqual(self.ch.spec[7], [0, 0, p.SPEC_XP_START])
        self.assertEqual(self.ch.spec_capacity(), 3)
        self.assertEqual(self.ch.spec_cost(), (0, 3000))

    def test_repeated_replacements_do_not_increase_capacity_or_restore_xp(self):
        self.action(0)
        self.action(1)
        self.ch.set_spec(1, 3)
        self.ch.save(self.store)
        before = self.store.money(self.cid)
        for idx in range(1, 12):
            old = idx - 1 if idx > 1 else 1
            self.assertEqual(self.action(old, False)[0], 0)
            self.assertEqual(self.action(idx), (0, (0, 0)))
            self.assertEqual(self.ch.spec[idx], [0, 0, p.SPEC_XP_START])
            self.assertEqual(self.ch.specs_learned(), 2)
            self.assertEqual(self.ch.spec_capacity(), 2)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.action(1), (0, (0, 1000)))
        self.assertEqual(self.ch.spec_capacity(), 3)

    def test_reset_all_keeps_paid_capacity_and_next_expansion_price(self):
        for idx in (0, 1, 2):
            self.assertEqual(self.action(idx)[0], 0)
        for idx in (0, 1, 2):
            self.assertEqual(self.action(idx, False)[0], 0)
        before = self.store.money(self.cid)
        for idx in (9, 10, 11):
            self.assertEqual(self.action(idx), (0, (0, 0)))
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.action(3), (0, (0, 3000)))
        self.assertEqual(self.ch.spec_capacity(), 4)

    def test_first_free_slot_can_be_reassigned_without_unlocking_a_second(self):
        before = self.store.money(self.cid)
        for idx in range(12):
            self.assertEqual(self.action(idx), (0, (0, 0)))
            self.assertEqual(self.ch.spec_capacity(), 1)
            self.assertEqual(self.ch.spec_cost(), (1000, 0))
            self.assertEqual(self.action(idx, False)[0], 0)
        self.assertEqual(self.store.money(self.cid), before)

    def test_full_twelve_slot_price_ladder_and_reuse(self):
        costs = [(0, 0), (1000, 0), (0, 1000), (0, 3000), (0, 5500)]
        costs += [(0, 7500)] * 7
        for idx, cost in enumerate(costs):
            self.assertEqual(self.action(idx), (0, cost))
        self.assertEqual(self.ch.spec_capacity(), 12)
        for idx in range(12):
            self.assertEqual(self.action(idx, False)[0], 0)
        money = self.store.money(self.cid)
        for idx in reversed(range(12)):
            self.assertEqual(self.action(idx), (0, (0, 0)))
        self.assertEqual(self.store.money(self.cid), money)
        self.assertEqual(self.ch.specs_learned(), 12)
        self.assertEqual(self.action(12)[0], p.ERR_STATE)

    def test_repeated_learning_cannot_charge_or_expand_twice(self):
        self.action(0)
        self.action(1)
        before = self.store.money(self.cid)
        self.assertEqual(self.action(1)[0], p.ERR_STATE)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.spec_slots(self.cid), 2)

    def test_stale_second_copy_cannot_fill_the_same_vacancy_twice(self):
        self.action(0)
        self.action(1)
        self.action(1, False)
        other = p.Character.load(self.store, self.cid)
        self.action(2)
        result = service.apply(self.store, other, p.UPD_LEARN, 3)
        self.assertEqual(result[0], p.ERR_STATE)
        self.assertEqual(self.ch.specs_learned(), 2)
        self.assertEqual(p.Character.load(self.store, self.cid).spec, self.ch.spec)

    def test_insufficient_money_does_not_expand_capacity(self):
        self.action(0)
        self.store.set_money(self.cid, 0, 0)
        self.ch.afro = self.ch.gold = 0
        self.assertEqual(self.action(1)[0], p.ERR_MONEY)
        self.assertEqual(self.ch.spec_capacity(), 1)
        self.assertEqual(self.ch.spec[1][0], -1)

    def test_failed_purchase_rolls_back_money_capacity_and_live_state(self):
        self.action(0)
        before = copy.deepcopy(self.ch.__dict__)
        money = self.store.money(self.cid)
        stats = [dict(r) for r in self.store.load_stats(self.cid)]
        slots = self.store.spec_slots(self.cid)
        with patch.object(self.store, 'save_spec_slots', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.action(1)
        self.assertEqual(self.ch.__dict__, before)
        self.assertEqual(self.store.money(self.cid), money)
        self.assertEqual([dict(r) for r in self.store.load_stats(self.cid)], stats)
        self.assertEqual(self.store.spec_slots(self.cid), slots)

    def test_admin_grant_is_not_a_paid_slot(self):
        self.ch.set_spec(2, 3)
        self.ch.save(self.store)
        self.assertEqual(self.store.spec_slots(self.cid), 0)
        self.assertEqual(self.action(2, False)[0], 0)
        self.action(0)
        self.assertEqual(self.ch.spec_cost(), (1000, 0))

    def test_legacy_migration_recovers_paid_capacity_without_distinct_choice_abuse(self):
        self.ch.spec[1] = [2, 7, p.spec_xp_max(2)]
        self.ch.save(self.store)
        with self.store.db:
            for idx in range(2, 10):
                self.store.db.execute("INSERT INTO money_ledger (at,char_id,level,source,ref,afro,gold)"
                                      " VALUES (1,?,1,'spec',?,-1000,0)", (self.cid, idx))
            self.store.db.execute('DELETE FROM char_spec_access WHERE char_id=?', (self.cid,))
            accounts.restore_spec_access(self.store.db)
        self.ch = p.Character.load(self.store, self.cid)
        self.assertEqual(self.ch.spec_capacity(), 2)
        self.assertEqual(self.ch.spec_cost(), (0, 0))
        self.assertEqual(self.action(11), (0, (0, 0)))
        self.assertEqual(self.ch.spec_cost(), (0, 1000))

    def test_legacy_gold_purchase_recovers_third_slot_after_all_resets(self):
        with self.store.db:
            self.store.db.execute("INSERT INTO money_ledger (at,char_id,level,source,ref,afro,gold)"
                                  " VALUES (1,?,1,'spec',2,0,-1000)", (self.cid,))
            self.store.db.execute('DELETE FROM char_spec_access WHERE char_id=?', (self.cid,))
            accounts.restore_spec_access(self.store.db)
        self.ch = p.Character.load(self.store, self.cid)
        for idx in (9, 10, 11):
            self.assertEqual(self.action(idx), (0, (0, 0)))
        self.assertEqual(self.ch.spec_cost(), (0, 3000))

    def test_free_replacement_failure_keeps_vacancy_and_currency(self):
        self.action(0)
        self.action(1)
        self.action(1, False)
        before = copy.deepcopy(self.ch.__dict__)
        money = self.store.money(self.cid)
        with patch.object(self.store, 'save_character_state', side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.action(11)
        self.assertEqual(self.ch.__dict__, before)
        self.assertEqual(self.store.money(self.cid), money)
        restored = p.Character.load(self.store, self.cid)
        self.assertEqual(restored.specs_learned(), 1)
        self.assertEqual(restored.spec_capacity(), 2)

    def test_existing_local_tester_capacity_survives_without_identity_mask(self):
        with self.store.db:
            self.store.db.execute('UPDATE char_spec_access SET unlocked_mask=7, opened_count=3'
                                  ' WHERE char_id=?', (self.cid,))
        self.ch = p.Character.load(self.store, self.cid)
        for idx in (9, 10, 11):
            self.assertEqual(self.action(idx), (0, (0, 0)))
        self.assertEqual(self.ch.spec_capacity(), 3)

    def test_capacity_is_character_specific_and_invalid_indices_are_rejected(self):
        self.action(0)
        self.action(1)
        aid, _ = self.store.register('other-spec', 'test-only')
        other, _ = self.store.create_character(aid, 'OtherSpec', 0, '1')
        self.assertEqual(self.store.spec_slots(other), 0)
        for idx in (-1, 12, 15, 1000):
            self.assertEqual(self.action(idx)[0], p.ERR_STATE)


if __name__ == '__main__':
    run_cases(SpecAccess)
