"""Combat skill ceiling and continued specialisation XP; no sockets or AI."""
import copy
import logging
import os
from types import SimpleNamespace as NS
import unittest

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import combat
import effects
import progression as p
from testkit import run_cases


class CombatXpCap(unittest.TestCase):
    def fighter(self, level=17, premium=0, skill=p.SHOOTING, carry=0):
        ch = p.Character()
        ch.set_skill(skill, level)
        ch.premium = premium
        ch.xp_carry[skill] = carry
        spec = 2 if skill == p.SHOOTING else 0
        ch.spec[spec] = [0, 0, p.spec_xp_max(0)]
        f = combat.Fighter.__new__(combat.Fighter)
        f.sess = NS(loc=NS(id=100), character=lambda: ch, push_vitals=lambda: None)
        f.stats_changed = lambda changed: None
        return f, ch, spec

    def mob(self, level=18, mult=1):
        return NS(level=level, stats=NS(hp_max=100, sp_max=100, role='mob', xp_mult=mult), xp_ledger={})

    def settle(self, mob, *fighters):
        rc = NS(room=NS(players=[f.sess for f in fighters]))
        combat.RoomCombat.settle_xp(rc, mob)

    def spec_total(self, ch, spec):
        level, xp, ceiling = ch.spec[spec]
        return sum(p.spec_xp_max(i) for i in range(level)) + xp

    def test_equal_and_lower_rewards_use_the_plus_one_base_and_four_level_cutoff(self):
        for level in range(17):
            for mob in range(level + 1):
                for share in (0, .125, .5, 1):
                    for mult in (.7, 1, 3):
                        ratio = {0:.8, -1:.7, -2:.6, -3:.5}.get(mob - level, 0)
                        expected = p.mob_price(level + 1) * ratio * mult * share
                        self.assertAlmostEqual(p.combat_mob_xp(mob, level, share, mult), expected)

    def test_spec_reward_rises_to_level_16_maximum_at_gap_four(self):
        ceiling = 1996 * 1.3
        self.assertAlmostEqual(ceiling, 2594.8)
        expected = [1996 * .8, 1996, 1996 * 1.1, 1996 * 1.2, 1996 * 1.3]
        for level in (17, 18, 19, 20):
            self.assertEqual([p.combat_mob_xp(17 + gap, level) for gap in range(5)], expected)
            for mob in (17, 18, 21, 30):
                for mult in (.7, 1, 3, 10):
                    full = min(ceiling, expected[min(mob - 17, 4)] * mult)
                    self.assertEqual(p.combat_mob_xp(mob, level, 1, mult), full)
                    self.assertEqual(p.combat_mob_xp(mob, level, .25, mult), full / 4)
            self.assertEqual(p.combat_mob_xp(13, level), 0)
            self.assertEqual(p.combat_mob_xp(15, level), 1996 * .6)
        self.assertEqual(p.combat_mob_xp(16, 17), 1996 * .7)
        for gap in range(-3, 9):
            self.assertEqual(p.combat_mob_xp(17 + gap, 17),
                             p.combat_mob_xp(16 + gap, 16))

    def test_many_hits_settlement_only_train_spec_and_pay_once(self):
        for skill in (p.SHOOTING, p.MELEE):
            for level in (17, 18, 19, 20):
                for premium in (0, 1, 2):
                    f, ch, spec = self.fighter(level, premium, skill)
                    before = ch.skill[skill][:]
                    mob = self.mob(21, mult=3)
                    for _ in range(100):
                        f.award_xp(skill, spec, 1, mob)
                    self.settle(mob, f)
                    self.settle(mob, f)
                    self.assertEqual(ch.skill[skill], before)
                    self.assertEqual(self.spec_total(ch, spec),
                                     int(2594.8 * (1 + p.PREMIUM_XP_BONUS[premium]) + 1e-9))

    def test_premium_is_applied_once_before_fractional_combat_carry(self):
        for level in (12, 17):
            for premium in (0, 1, 2):
                with self.subTest(level=level, premium=premium):
                    split, ch, spec = self.fighter(level, premium)
                    whole, reference, reference_spec = self.fighter(level, premium)
                    mob = self.mob(level + 1)
                    reward = p.combat_mob_xp(mob.level, level) * (1 + p.PREMIUM_XP_BONUS[premium])
                    for _ in range(100):
                        split.credit_xp(p.SHOOTING, spec, .01, mob)
                    whole.credit_xp(p.SHOOTING, reference_spec, 1, mob)
                    self.assertEqual(ch.skill, reference.skill)
                    self.assertEqual(ch.spec, reference.spec)
                    self.assertEqual(self.spec_total(ch, spec), int(reward + 1e-9))
                    carry = ('spec', spec) if level == 17 else p.SHOOTING
                    self.assertAlmostEqual(ch.xp_carry[carry], reward % 1)

    def test_intux_residence_percentages_add_before_experience_reduction(self):
        for type_id, multipliers in ((3112, (1.1, 1.25, 1.4)), (3113, (1.3, 1.45, 1.6)),
                                     (3114, (1.5, 1.65, 1.8)), (3561, (1.7, 1.85, 2.0))):
            for premium, multiplier in enumerate(multipliers):
                for reduction, factor in ((None, 1), (3205, .5), (3206, .2), (3207, .01)):
                    for level in (12, p.COMBAT_SKILL_CAP):
                        with self.subTest(type_id=type_id, premium=premium, reduction=reduction, level=level):
                            f, ch, spec = self.fighter(level, premium)
                            active = {type_id: NS(source=type_id, deadline=10)}
                            if reduction:
                                active[reduction] = NS(source=reduction, deadline=10)
                            f.sess.effects = NS(active=active, clock=lambda: 0)
                            expected_multiplier = multiplier * factor
                            self.assertAlmostEqual(effects.multiplier(f.sess, 'mob_exp',
                                bonus=p.PREMIUM_XP_BONUS[premium]), expected_multiplier)
                            mob = self.mob(level + 1)
                            f.credit_xp(p.SHOOTING, spec, 1, mob)
                            reward = p.combat_mob_xp(level + 1, level) * expected_multiplier
                            carry = ('spec', spec) if level == 17 else p.SHOOTING
                            self.assertEqual(self.spec_total(ch, spec), int(reward + 1e-9))
                            self.assertAlmostEqual(ch.xp_carry[carry], reward % 1)

    def test_no_active_intux_preserves_residence_with_or_without_effect_manager(self):
        for premium, expected in ((0, 1), (1, 1.15), (2, 1.3)):
            for manager in (None, NS(active={}, clock=lambda: 0),
                            NS(active={3561: NS(source=3561, deadline=0)}, clock=lambda: 1)):
                f, ch, spec = self.fighter(12, premium)
                f.sess.effects = manager
                self.assertAlmostEqual(effects.multiplier(f.sess, 'mob_exp',
                    bonus=p.PREMIUM_XP_BONUS[premium]), expected)
                mob = self.mob(13)
                f.credit_xp(p.SHOOTING, spec, 1, mob)
                reward = p.combat_mob_xp(13, 12) * expected
                self.assertEqual(self.spec_total(ch, spec), int(reward + 1e-9))
                self.assertAlmostEqual(ch.xp_carry[p.SHOOTING], reward % 1)

    def test_expiry_stops_new_bonus_without_reapplying_it_to_old_fraction(self):
        f, ch, spec = self.fighter(12, 1)
        mob = self.mob(13)
        share = .5 / p.combat_mob_xp(13, 12)
        f.credit_xp(p.SHOOTING, spec, share, mob)
        self.assertAlmostEqual(ch.xp_carry[p.SHOOTING], .575)
        ch.premium_until = 1
        f.credit_xp(p.SHOOTING, spec, share, mob)
        self.assertEqual(self.spec_total(ch, spec), 1)
        self.assertAlmostEqual(ch.xp_carry[p.SHOOTING], .075)

    def test_overkill_callbacks_do_not_multiply_spec_reward(self):
        f, ch, spec = self.fighter()
        mob = self.mob()
        for _ in range(10):
            f.award_xp(p.SHOOTING, spec, 99999, mob)
        self.settle(mob, f)
        self.assertEqual(ch.skill[p.SHOOTING][1], 0)
        self.assertEqual(self.spec_total(ch, spec), int(p.combat_mob_xp(mob.level, ch.level)))

    def test_lower_base_skill_still_trains_when_character_is_17(self):
        f, ch, spec = self.fighter(10, skill=p.MELEE)
        ch.set_skill(p.SHOOTING, 17)
        ch.bonus_skills[p.MELEE] = 10
        f.credit_xp(p.MELEE, spec, 1, self.mob(11))
        self.assertEqual(ch.skill[p.MELEE][1], int(p.combat_mob_xp(11, 10)))
        f, ch, spec = self.fighter(16)
        ch.bonus_skills[p.SHOOTING] = 5
        f.credit_xp(p.SHOOTING, spec, 1, self.mob(17))
        self.assertEqual(ch.skill[p.SHOOTING][1], int(p.combat_mob_xp(17, 16)))

    def test_group_shares_and_fractional_carry_are_preserved(self):
        first, a, spec_a = self.fighter()
        second, b, spec_b = self.fighter()
        mob = self.mob()
        first.award_xp(p.SHOOTING, spec_a, 50, mob)
        second.award_xp(p.SHOOTING, spec_b, 50, mob)
        self.settle(mob, first, second)
        for ch, spec in ((a, spec_a), (b, spec_b)):
            self.assertEqual(ch.skill[p.SHOOTING][1], 0)
            reward = p.combat_mob_xp(mob.level, ch.level) / 2
            self.assertEqual(self.spec_total(ch, spec), int(reward))
            self.assertAlmostEqual(ch.xp_carry['spec', spec], reward - int(reward))
        f, ch, spec = self.fighter()
        for _ in range(10):
            mob = self.mob(16)
            f.award_xp(p.SHOOTING, spec, 1, mob)
            self.settle(mob, f)
        self.assertEqual(self.spec_total(ch, spec), int(10 * p.mob_xp(15, 16)))
        self.assertAlmostEqual(ch.xp_carry['spec', spec], .5)

    def test_unlearned_or_missing_spec_gets_no_reward_or_carry(self):
        f, ch, spec = self.fighter()
        ch.spec[spec][0] = -1
        before = copy.deepcopy(ch.spec)
        for idx in (None, spec, -1, p.SPECS):
            f.credit_xp(p.SHOOTING, idx, 1, self.mob())
        self.assertEqual(ch.spec, before)
        self.assertEqual(ch.skill[p.SHOOTING][1], 0)
        self.assertNotIn(('spec', spec), ch.xp_carry)

    def test_fractional_carry_does_not_leak_between_specs(self):
        f, ch, first = self.fighter()
        second = first + 1
        ch.spec[second] = [0, 0, p.spec_xp_max(0)]
        share = .5 / p.combat_mob_xp(18, 17)
        for spec in (first, second):
            f.credit_xp(p.SHOOTING, spec, share, self.mob())
            self.assertEqual(self.spec_total(ch, spec), 0)
        for spec in (first, second):
            f.credit_xp(p.SHOOTING, spec, share, self.mob())
            self.assertEqual(self.spec_total(ch, spec), 1)

    def test_level_16_to_17_discards_skill_overflow_but_keeps_spec_reward(self):
        for skill in (p.SHOOTING, p.MELEE):
            f, ch, spec = self.fighter(16, skill=skill)
            ch.skill[skill][1] = ch.skill[skill][2] - 1
            first_reward = p.combat_mob_xp(17, 16)
            f.credit_xp(skill, spec, 1, self.mob(17))
            self.assertEqual(ch.skill[skill], [17, 0, p.skill_xp_max(17)])
            self.assertEqual(self.spec_total(ch, spec), int(first_reward))
            f.credit_xp(skill, spec, 1, self.mob(18))
            self.assertEqual(ch.skill[skill], [17, 0, p.skill_xp_max(17)])
            second_reward = p.combat_mob_xp(18, 17)
            self.assertEqual(self.spec_total(ch, spec), int(first_reward + second_reward))
            self.assertAlmostEqual(ch.xp_carry['spec', spec], (first_reward + second_reward) % 1)

    def test_existing_skill_progress_is_not_erased(self):
        f, ch, spec = self.fighter()
        ch.skill[p.SHOOTING][1] = 123
        f.credit_xp(p.SHOOTING, spec, 1, self.mob())
        self.assertEqual(ch.skill[p.SHOOTING][1], 123)

    def test_spec_level_up_gives_its_attribute_without_skill_xp(self):
        f, ch, spec = self.fighter()
        ch.spec[spec][1] = ch.spec[spec][2] - 1
        attribute = p.SPEC_ATTRIB[spec]
        before = ch.attrib[attribute]
        f.credit_xp(p.SHOOTING, spec, 1, self.mob())
        self.assertEqual(ch.spec[spec][0], 1)
        self.assertEqual(ch.attrib[attribute], before + 1)
        self.assertEqual(ch.skill[p.SHOOTING][1], 0)

    def test_noncombat_and_administrative_sources_are_unchanged(self):
        self.assertEqual(p.mob_xp(18, 17), p.mob_price(18))
        for skill in (p.MEDICINE, p.INDUSTRY, p.SHOOTING):
            ch = p.Character()
            ch.set_skill(skill, 17)
            ch.gain_xp(skill, 100)
            self.assertEqual(ch.skill[skill][1], 100)


if __name__ == '__main__':
    run_cases(CombatXpCap)
