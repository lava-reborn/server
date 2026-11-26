"""Combat XP ramp endpoints, fractional shares and actual kill settlement."""
import unittest
from unittest.mock import patch

import progression as p
import test_combat_xp_cap as cap_tests


class CombatXpRamp(unittest.TestCase):
    def setUp(self):
        calendar = patch.object(p, 'combat_calendar_multiplier', return_value=1)
        calendar.start()
        self.addCleanup(calendar.stop)

    def test_gap_rewards_increase_and_stop_at_four(self):
        for skill in range(17):
            base = p.COMBAT_XP_BASE[skill]
            values = [p.combat_mob_xp(skill + gap, skill) for gap in range(5)]
            self.assertAlmostEqual(values[0], base * (890/1100))
            for gap, factor in enumerate((980/1100, 1, 1.1, 1.2), 1):
                self.assertAlmostEqual(values[gap], base * factor)
                self.assertGreater(values[gap], values[gap - 1])
            self.assertAlmostEqual(p.combat_mob_xp(skill + 50, skill), base * 1.2)

    def test_full_rewards_match_approved_moderate_curve_at_every_base_skill_level(self):
        expected = (20, 23.75, 30.0751, 38.2775, 50.1567, 66.1157, 86.8385, 115.2115, 153.11, 203.2552, 252.58061816, 363.0088964189, 512.1589986209, 712.3213673975, 885.1855761029, 1100.0, 1366.945003018, 1366.945003018)
        for skill, reward in enumerate(expected):
            with self.subTest(skill=skill):
                self.assertAlmostEqual(p.combat_mob_xp(skill + 2, skill), reward)

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
                    ratio = {0:890/1100, -1:.70, -2:.30, -3:.15}.get(mob - skill, 0)
                    expected = p.COMBAT_XP_BASE[skill] * ratio * mult
                    self.assertAlmostEqual(p.combat_mob_xp(mob, skill, xp_mult=mult), expected)

    def test_minus_one_gains_forty_percent_while_lower_rewards_fall_to_zero(self):
        for level in range(1, 18):
            base = p.COMBAT_XP_BASE[level]
            for share in (.125, .5, 1):
                previous = base * .5 * share
                self.assertAlmostEqual(p.combat_mob_xp(level - 1, level, share), previous * 1.4)
            self.assertLess(p.combat_mob_xp(level - 1, level), p.combat_mob_xp(level, level))
        for level in range(4, 18):
            rewards = [p.combat_mob_xp(level + gap, level) for gap in range(-4, 1)]
            self.assertEqual(rewards[0], 0)
            self.assertTrue(all(a < b for a, b in zip(rewards, rewards[1:])))

    def test_legacy_noncombat_price_does_not_gain_a_ramp(self):
        self.assertEqual(p.mob_xp(1, 0), 20)
        self.assertEqual(p.mob_xp(10, 9), 267)
        self.assertEqual(p.mob_xp(20, 9), 267)

    def test_split_hits_settlement_and_repeat_do_not_lose_or_duplicate_xp(self):
        fixture = cap_tests.CombatXpCap()
        for skill in (p.SHOOTING, p.MELEE):
            for gap in range(-3, 5):
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
