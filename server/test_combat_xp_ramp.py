"""Combat XP ramp endpoints, fractional shares and actual kill settlement."""
import unittest

import progression as p
import test_combat_xp_cap as cap_tests


class CombatXpRamp(unittest.TestCase):
    def test_gap_rewards_increase_and_stop_at_four(self):
        for skill in range(17):
            base = p.mob_price(skill + 1) * p.COMBAT_XP_LEVEL_MULTIPLIERS[skill]
            values = [p.combat_mob_xp(skill + gap, skill) for gap in range(5)]
            self.assertAlmostEqual(values[0], base * .70)
            for gap, factor in enumerate((.85, 1, 1.1, 1.2), 1):
                self.assertAlmostEqual(values[gap], base * factor)
                self.assertGreater(values[gap], values[gap - 1])
            self.assertAlmostEqual(p.combat_mob_xp(skill + 50, skill), base * 1.2)

    def test_level_reduction_matches_variant_b_at_every_base_skill_level(self):
        expected = [1] + [.95] * 10 + [.90, .80, .70, .60, .50, .45, .45]
        for skill, factor in enumerate(expected):
            with self.subTest(skill=skill):
                self.assertAlmostEqual(p.combat_mob_xp(skill + 2, skill),
                                       p.mob_price(min(skill, 16) + 1) * factor)

    def test_mob_multipliers_and_shares_apply_once(self):
        for skill in (0, 5, 12, 16):
            for gap in range(-2, 7):
                base = p.combat_mob_xp(max(0, skill + gap), skill)
                for mult in (.7, 1, 3):
                    for share in (0, .125, .5, 1):
                        self.assertAlmostEqual(p.combat_mob_xp(max(0, skill + gap), skill, share, mult), base * mult * share)

    def test_equal_and_lower_targets_follow_the_agreed_ladder(self):
        for skill in range(17):
            for mob in range(skill + 1):
                for mult in (.7, 1, 3):
                    ratio = {0:.70, -1:.50, -2:.30, -3:.15}.get(mob - skill, 0)
                    expected = p.mob_price(skill + 1) * ratio * mult * p.COMBAT_XP_LEVEL_MULTIPLIERS[skill]
                    self.assertAlmostEqual(p.combat_mob_xp(mob, skill, xp_mult=mult), expected)

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
                    before = (ch.skill[skill][1], ch.spec[spec][:], dict(ch.xp_carry))
                    for _ in range(13):
                        f.award_xp(skill, spec, 7, mob)
                        self.assertEqual((ch.skill[skill][1], ch.spec[spec], ch.xp_carry), before)
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
        self.assertEqual((a.skill[p.SHOOTING][1], b.skill[p.SHOOTING][1]), (0, 0))
        fixture.settle(mob, first, second)
        awarded = sum(ch.skill[p.SHOOTING][1] + ch.xp_carry[p.SHOOTING] for ch in (a, b))
        self.assertAlmostEqual(awarded, p.combat_mob_xp(14, 12))
        for character in (a, b):
            self.assertAlmostEqual(character.skill[p.SHOOTING][1] + character.xp_carry[p.SHOOTING],
                                   p.combat_mob_xp(14, 12) / 2)


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(CombatXpRamp)
