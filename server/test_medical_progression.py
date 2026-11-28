"""Completed treatment trains the patient's HP band, including after reload."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import accounts
import combat
import inventory
import items
import progression as p
import protocol
from testkit import healing_fixture, run_cases


class MedicalProgression(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        account, error = self.store.register('medical-progression', 'test-only')
        self.assertIsNone(error)
        self.cid, _ = self.store.create_character(account, 'MedicalProgression', 0, '1')
        self.ch = p.Character.load(self.store, self.cid)
        self.ch.set_skill(p.MEDICINE, 10)
        self.ch.set_spec(8, 0)
        self.ch.set_spec(9, 0)
        self.f, _, self.room, _ = healing_fixture(6043)
        self.f.character = lambda: self.ch
        self.f.store = self.store
        self.sess = self.f.sess
        self.sess.char_id = self.cid
        self.sess.character = lambda: self.ch
        self.sess.send_player_info = lambda: None
        self.sess.inv = inventory.Inventory(self.sess, self.store)
        self.sess.inv.carry_limit = lambda: 1_000_000
        self.updates = []
        self.sess.push_stats = lambda **changed: self.updates.append(
            self.ch.rp_info(**changed))

    def complete(self, target=None):
        row = self.sess.inv.create(6043, 1)
        with patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: hi):
            self.f.heal_now(row['uniq'], target or self.f)
        self.assertIsNone(self.store.item(row['uniq']))

    async def test_hp_threshold_awards_and_wire_values_survive_save_reload(self):
        for percent, selected in ((29, 8), (30, 9), (31, 9)):
            with self.subTest(percent=percent):
                self.ch.set_skill(p.MEDICINE, 10)
                self.ch.set_spec(8, 0)
                self.ch.set_spec(9, 0)
                self.ch.hp = int(self.ch.hp_max * percent / 100)
                # Make the exact 30% case representable by integer HP.
                self.ch.bonus_hp += (-self.ch.hp_max) % 100
                before = self.ch.hp = self.ch.hp_max * percent // 100
                maximum = self.ch.hp_max
                self.complete()
                healed = self.ch.hp - before
                ceiling = items.params_of(6043)['max_h_rest']
                total = int(healed * min(2, maximum / ceiling))
                self.assertGreater(total, 1)
                self.assertEqual(self.ch.spec[selected][1], total // 2)
                self.assertEqual(self.ch.spec[17 - selected][1], 0)
                self.assertEqual(self.ch.skill[p.MEDICINE][1], total - total // 2)
                frame = self.updates[-1]
                name, decoded = protocol.decode(protocol.encode('rp_info', **frame))
                self.assertEqual(name, 'rp_info')
                self.assertEqual(decoded['xp_specs_mask'], 1 << selected)
                self.assertEqual(decoded['xp_specs'], [total // 2])
                self.ch.save(self.store)
                restored = p.Character.load(self.store, self.cid)
                self.assertEqual(restored.spec, self.ch.spec)
                self.assertEqual(restored.skill, self.ch.skill)

    async def test_low_hp_patient_trains_doctor_surgery_even_when_doctor_is_healthy(self):
        patient = p.Character()
        patient.hp = 10
        target = NS(character=lambda: patient, dead=False, eid=2)
        self.ch.hp = self.ch.hp_max
        self.complete(target)
        self.assertGreater(self.ch.spec[8][1], 0)
        self.assertEqual(self.ch.spec[9][1], 0)
        self.assertEqual(patient.spec[8][1], 0)

    async def test_crossing_thirty_percent_during_treatment_keeps_surgery_award(self):
        self.ch.hp = self.ch.hp_max * 29 // 100
        self.complete()
        self.assertGreaterEqual(self.ch.hp, self.ch.hp_max * .3)
        self.assertGreater(self.ch.spec[8][1], 0)
        self.assertEqual(self.ch.spec[9][1], 0)

    async def test_unlearned_surgery_sends_full_award_to_medicine(self):
        self.ch.forget_spec(8)
        self.ch.hp = 10
        self.complete()
        self.assertEqual(self.ch.spec[8][:2], [-1, 0])
        self.assertGreater(self.ch.skill[p.MEDICINE][1], 0)
        self.assertEqual(self.ch.spec[9][1], 0)

    async def test_full_health_does_not_mint_medical_experience(self):
        self.ch.hp = self.ch.hp_max
        self.ch.sp = 0
        before = (self.ch.skill[p.MEDICINE][:], self.ch.spec[8][:], self.ch.spec[9][:])
        self.complete()
        self.assertEqual((self.ch.skill[p.MEDICINE], self.ch.spec[8], self.ch.spec[9]), before)
        self.assertEqual(self.updates, [])


if __name__ == '__main__':
    run_cases()
