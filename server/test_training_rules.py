"""Fast arithmetic and isolation checks for experimental range rules."""
import unittest
import combat
from training.rules import Rules


class TrainingRules(unittest.TestCase):
    def weapon(self):
        return combat.Weapon(1, 100, 120, 3, 10, 20, 5, 0.1, 7, 1, 2, sdmin=20, sdmax=40)

    def test_normal_room_and_baseline_keep_exact_weapon(self):
        weapon = self.weapon()
        self.assertIs(combat.Fighter.prepare_weapon(None, weapon, {'dam_mod': 2}, None), weapon)
        self.assertIs(Rules().weapon(weapon, {'dam_mod': 2}), weapon)

    def test_ammunition_damage_stamina_range_and_spread_are_independent(self):
        weapon = self.weapon()
        candidate = Rules(ammo_modifiers=True, spread=0.5).weapon(
            weapon, dict(dam_mod=1.1, st_mod=0.9, range_mod=1.2))
        self.assertEqual((candidate.dmin, candidate.dmax), (110, 132))
        self.assertEqual((candidate.sdmin, candidate.sdmax), (18, 36))
        self.assertAlmostEqual(candidate.opt_lo, 3.6)
        self.assertEqual((candidate.opt_hi, candidate.max_range), (12, 24))
        self.assertAlmostEqual(candidate.cone, 0.1 * 0.5 / 1.2)
        self.assertEqual(candidate.num_shots, weapon.num_shots)
        self.assertEqual(candidate.piercing, weapon.piercing)
        self.assertEqual(weapon.dmin, 100)

    def test_rules_round_trip_and_reject_invalid_values(self):
        rules = Rules(ammo_modifiers=True, effect_armour=25, health=2)
        self.assertEqual(Rules.parse(rules.as_dict()), rules)
        self.assertEqual(Rules.from_values(rules.values()).values(), rules.values())
        for raw in ({'effect_armour': float('inf')}, {'effect_armour': -1},
                    {'ammo_modifiers': 1}, {'broken_armour': 'yes'}, {'attributes': [1] * 4}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                Rules.parse(raw)

    def test_description_uses_the_same_percentages_and_labels_as_the_panel(self):
        rules = Rules(revision='user-0123456789abcdef', attributes=(1, .5, 1.5, 1, 2),
                      health=1.5, stamina=2, armour=.8, spread=.5, effect_armour=20,
                      ammo_modifiers=True, broken_armour=False)
        before = rules.values()
        text = rules.description()
        for label in ('ловкость 50%', 'телосложение 150%', 'интеллект 200%',
                      'Запас HP: 150%', 'выносливости: 200%', 'Броня: 80%',
                      'доп. броня: 20 ед.', 'разброс: 50%',
                      'Параметры патронов: учитывать', 'защита сломанной брони: не учитывать'):
            self.assertIn(label, text)
        self.assertNotIn(rules.revision, text)
        self.assertEqual(rules.values(), before)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingRules)
