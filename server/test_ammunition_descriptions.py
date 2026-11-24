"""Original ammunition prose and complete preloads, without combat/stat changes."""
import unittest

import items
import names
import orig_texts
from testkit import run_cases


class AmmunitionDescriptions(unittest.TestCase):
    def test_every_catalogued_round_has_a_nonempty_preloaded_native_description(self):
        checked = 0
        for tid, (root, _) in items.catalogue().items():
            if root != items.AMMO:
                continue
            with self.subTest(type=tid):
                command, params = items.static_info(tid)
                self.assertEqual(command, 'ss_si_ammo')
                self.assertEqual(params['desc'], items.DESC_ID_OFFSET + tid)
                self.assertTrue(names.known(params['desc']))
                text = names.text(params['desc'])
                self.assertTrue(text.strip())
                self.assertTrue(orig_texts.launcher_ok(text))
                self.assertNotIn('Точность без изменений', text)
                checked += 1
        self.assertGreaterEqual(checked, 338)

    def test_all_shock_calibres_share_the_original_shock_description(self):
        expected = 'Шоковые. Сводят выносливость противника на нет'
        self.assertEqual(orig_texts.item_descs()[6189], expected)
        for tid in items.SHOCK_ROUNDS.values():
            with self.subTest(type=tid):
                self.assertEqual(names.text(items.params_of(tid)['desc']), expected)

    def test_original_and_special_ammunition_prose_is_preserved(self):
        count = 0
        for tid, text in orig_texts.item_descs().items():
            if items.root_of(tid) == items.AMMO:
                self.assertEqual(names.text(items.params_of(tid)['desc']), text, tid)
                count += 1
        self.assertGreaterEqual(count, 158)
        self.assertIn('Стрела', names.text(items.params_of(4780)['desc']))
        self.assertIn('по животным', names.text(items.params_of(6202)['desc']))
        self.assertNotIn('Шоковые', names.text(items.params_of(6190)['desc']))


if __name__ == '__main__':
    run_cases(AmmunitionDescriptions)
