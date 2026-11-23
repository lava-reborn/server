"""Ordinary pouch accuracy above trained V; private preparation stays pinned."""
from types import SimpleNamespace as NS
import unittest

import battle_balance
import combat
import items
import progression
from testkit import run_cases
from training.arena import TrainingFighter
from training.rules import Rules


class EffectiveAccuracyBonuses(unittest.TestCase):
    def character(self, level=17, spec=5, bonus=0):
        ch = progression.Character()
        ch.set_skill(progression.SHOOTING, level)
        ch.set_spec(5, spec)
        ch.bonus_specs[5] = bonus
        return ch

    def weapon(self, ch, ammo):
        return combat.Weapon(1, 100, 200, 28, 38, 42, ammo.get('piercing', 1),
            combat.cone_of(combat.spread_factor(ch.skill_level(progression.SHOOTING),
                                               combat.spec_or_zero(ch, 5)),
                           .462, ammo.get('acc_mod', 1), 42),
            0, progression.SHOOTING, 5)

    def test_mod_above_trained_five_keeps_its_accuracy_bonus_with_ammo_and_senior_gear(self):
        for level, ammo in ((17, {}), (13, dict(acc_mod=.8, dam_mod=1.1, st_mod=1.3, range_mod=1.1))):
            with self.subTest(level=level, ammo=ammo):
                ch = self.character(level)
                row = dict(type_id=25803, root=items.FIRE_ARM, cur_mode=2)
                plain = battle_balance.weapon(self.weapon(ch, ammo), ch, row, ammo)
                ch.bonus_specs[5] = 1
                enhanced = battle_balance.weapon(self.weapon(ch, ammo), ch, row, ammo)
                # Trained V is retained; the existing +1 pouch supplies effective VI.
                self.assertEqual((ch.spec[5][0], ch.spec_level(5)), (5, 6))
                self.assertLess(enhanced.cone, plain.cone)
                capped = 1 + (.7 - .65 / 20 * level) + (.8 - .75 / 5 * 5)
                effective = capped - .15
                self.assertAlmostEqual(enhanced.cone / plain.cone, effective / capped)
                self.assertEqual((enhanced.dmin, enhanced.dmax, enhanced.max_range),
                                 (plain.dmin, plain.dmax, plain.max_range))

    def test_unlearned_specialisation_is_not_unlocked_by_a_pouch(self):
        ch = self.character(spec=-1)
        row = dict(type_id=25803, root=items.FIRE_ARM, cur_mode=2)
        plain = battle_balance.weapon(self.weapon(ch, {}), ch, row, {})
        ch.bonus_specs[5] = 1
        enhanced = battle_balance.weapon(self.weapon(ch, {}), ch, row, {})
        self.assertEqual((ch.spec_level(5), combat.spec_or_zero(ch, 5)), (-1, 0))
        self.assertEqual(enhanced.cone, plain.cone)

    def test_zero_ammunition_scatter_is_not_replaced_with_neutral_precision(self):
        ch = self.character()
        # use_fire's legacy ``acc_mod or 1`` supplies this nonzero initial cone.
        shot = self.weapon(ch, {})
        self.assertGreater(shot.cone, 0)
        prepared = battle_balance.weapon(shot, ch,
            dict(type_id=25803, root=items.FIRE_ARM, cur_mode=2), dict(acc_mod=0))
        self.assertEqual(prepared.cone, 0)
        self.assertLessEqual(prepared.hit_cap, .95)

    def test_original_private_range_preparation_does_not_inherit_ordinary_effective_stat_adjustment(self):
        ch = self.character(bonus=1)
        shot = self.weapon(ch, {})
        fighter = NS(sess=NS(ground=NS(rules=Rules(combat_v2=False))))
        private = TrainingFighter.prepare_weapon(fighter, shot, {},
            dict(type_id=25803, root=items.FIRE_ARM, cur_mode=2))
        self.assertEqual(private, shot)


if __name__ == '__main__':
    run_cases(EffectiveAccuracyBonuses)
