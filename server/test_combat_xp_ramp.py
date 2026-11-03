"""Combat XP ramp endpoints, fractional shares and actual kill settlement."""
import unittest

import progression as p
import test_combat_xp_cap as cap_tests


class CombatXpRamp(unittest.TestCase):
    def test_linear_steps_retain_equal_reward_and_old_ceiling(self):
        for skill in range(17):
            same = p.mob_price(skill) * .5
            ceiling = p.mob_price(skill + 1)
            values = [p.combat_mob_xp(skill + gap, skill) for gap in range(5)]
            self.assertEqual(values[0], same)
            self.assertEqual(values[4], ceiling)
            for gap in range(1, 5):
                with self.subTest(skill=skill, gap=gap):
                    self.assertAlmostEqual(values[gap] - values[gap - 1], (ceiling - same) / 4)
            self.assertEqual(p.combat_mob_xp(skill + 50, skill), ceiling)

    def test_mob_multipliers_and_shares_apply_once(self):
        for skill in (0, 5, 12, 16):
            for gap in range(-2, 7):
                base = p.combat_mob_xp(max(0, skill + gap), skill)
                for mult in (.7, 1, 3):
                    for share in (0, .125, .5, 1):
                        self.assertAlmostEqual(p.combat_mob_xp(max(0, skill + gap), skill, share, mult), base * mult * share)

    def test_equal_and_lower_targets_unchanged(self):
        for skill in range(17):
            for mob in range(skill + 1):
                for mult in (.7, 1, 3):
                    old = p.mob_xp(mob, skill, xp_mult=mult)
                    expected = old
                    self.assertEqual(p.combat_mob_xp(mob, skill, xp_mult=mult), expected)

    def test_legacy_noncombat_price_does_not_gain_a_ramp(self):
        self.assertEqual(p.mob_xp(1, 0), 20)
        self.assertEqual(p.mob_xp(10, 9), 267)
        self.assertEqual(p.mob_xp(20, 9), 267)

    def test_split_hits_settlement_and_repeat_do_not_lose_or_duplicate_xp(self):
        fixture = cap_tests.CombatXpCap()
        for skill in (p.SHOOTING, p.MELEE):
            for gap in range(1, 5):
                f, ch, spec = fixture.fighter(12, skill=skill)
                whole, expected_ch, expected_spec = fixture.fighter(12, skill=skill)
                reward = p.combat_mob_xp(12 + gap, 12)
                for kill in range(1, 4):
                    mob = fixture.mob(12 + gap)
                    for _ in range(13):
                        f.award_xp(skill, spec, 7, mob)
                    fixture.settle(mob, f)
                    fixture.settle(mob, f)
                    whole.credit_xp(skill, expected_spec, 1, fixture.mob(12 + gap))
                    self.assertEqual(ch.skill[skill][1], int(kill * reward))
                    self.assertEqual(ch.spec[spec], expected_ch.spec[expected_spec])
                    self.assertAlmostEqual(ch.xp_carry[skill], kill * reward % 1)

    def test_group_settlement_splits_one_kill_price(self):
        fixture = cap_tests.CombatXpCap()
        first, a, spec_a = fixture.fighter(12)
        second, b, spec_b = fixture.fighter(12)
        mob = fixture.mob(14)
        first.award_xp(p.SHOOTING, spec_a, 50, mob)
        second.award_xp(p.SHOOTING, spec_b, 50, mob)
        fixture.settle(mob, first, second)
        awarded = sum(ch.skill[p.SHOOTING][1] + ch.xp_carry[p.SHOOTING] for ch in (a, b))
        self.assertAlmostEqual(awarded, p.combat_mob_xp(14, 12))


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(CombatXpRamp)
