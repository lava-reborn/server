"""PvE calendar/INTUX alternatives, additive residence and damage-time awards."""
from datetime import datetime, timedelta
import math
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import effects
import progression as p
from test_combat_xp_cap import CombatXpCap
from testkit import run_cases

FRIDAY = datetime(2026, 11, 27, 12, tzinfo=p.COMBAT_XP_ZONE).timestamp()
SATURDAY = datetime(2026, 11, 28, 12, tzinfo=p.COMBAT_XP_ZONE).timestamp()


def session(source=None, reduction=None):
    active = {key: NS(source=key, deadline=10) for key in (source, reduction) if key is not None}
    return NS(effects=NS(active=active, clock=lambda: 0))


class WeekendExperience(unittest.TestCase):
    def test_moscow_midnight_boundaries_ignore_the_host_timezone(self):
        saturday = datetime(2026, 11, 28, tzinfo=p.COMBAT_XP_ZONE).timestamp()
        monday = datetime(2026, 11, 30, tzinfo=p.COMBAT_XP_ZONE).timestamp()
        for stamp, expected in ((saturday - 1, 1), (saturday, 1.5),
                                (monday - 1, 1.5), (monday, 1)):
            self.assertEqual(p.combat_calendar_multiplier(stamp), expected)
        self.assertEqual(datetime.fromtimestamp(saturday, p.COMBAT_XP_ZONE).hour, 0)
        self.assertEqual(p.COMBAT_XP_ZONE.utcoffset(None), timedelta(hours=3))

    def test_calendar_and_intux_choose_the_greater_then_add_residence_and_reduce(self):
        for stamp, calendar in ((FRIDAY, 1), (SATURDAY, 1.5)):
            for residence in (0, .15, .30):
                for source, boost in ((None, 1), (3112, 1.1), (3113, 1.3), (3114, 1.5), (3561, 1.7)):
                    for reduction, factor in ((None, 1), (3205, .5), (3206, .2), (3207, .01)):
                        s = session(source, reduction)
                        got = effects.multiplier(s, 'mob_exp', bonus=residence,
                                                 minimum=p.combat_calendar_multiplier(stamp))
                        self.assertAlmostEqual(got, (max(calendar, boost) + residence) * factor)
                        # PvP and other callers retain their previous, non-calendar rule.
                        self.assertAlmostEqual(effects.multiplier(s, 'pl_exp', bonus=residence),
                                               (boost + residence) * factor)
        s = session(3561)
        s.effects.active['duplicate'] = NS(source=3561, deadline=10)
        self.assertEqual(effects.multiplier(s, 'mob_exp', bonus=.3, minimum=1.5), 2)

    def test_no_extra_weekday_reduction_and_early_levels_keep_variant_b(self):
        for level in range(18):
            base = p.mob_price(min(level, 16) + 1) * p.COMBAT_XP_LEVEL_MULTIPLIERS[level]
            self.assertAlmostEqual(p.combat_mob_xp(level + 2, level), base)
            for stamp in (FRIDAY, SATURDAY):
                f, ch, spec = CombatXpCap().fighter(level)
                with patch.object(p.time, 'time', return_value=stamp):
                    got = f.xp_reward(p.SHOOTING, 1, CombatXpCap().mob(level + 2))
                self.assertAlmostEqual(got, base * (1.5 if stamp == SATURDAY else 1))
        self.assertEqual(p.COMBAT_XP_LEVEL_MULTIPLIERS[1:5], (.95,) * 4)
        self.assertEqual(p.mob_xp(10, 9), 267)  # noncombat legacy path unchanged

    def test_weekend_fully_boosted_ceiling_matches_b_instead_of_multiplying_again(self):
        fixture = CombatXpCap()
        for stamp in (FRIDAY, SATURDAY):
            for level in range(1, 18):
                for gap in range(-4, 7):
                    for role in (.7, 1, 3):
                        f, ch, spec = fixture.fighter(level, 2)
                        f.sess.effects = session(3561).effects
                        target = fixture.mob(level + gap, role)
                        with patch.object(p.time, 'time', return_value=stamp):
                            reward = f.xp_reward(p.SHOOTING, 1, target)
                        self.assertAlmostEqual(reward, p.combat_mob_xp(level + gap, level, xp_mult=role) * 2)
        f, ch, spec = fixture.fighter(15, 2)
        f.sess.effects = session(3561).effects
        with patch.object(p.time, 'time', return_value=SATURDAY):
            self.assertAlmostEqual(f.xp_reward(p.SHOOTING, 1, fixture.mob(19)), 1796.4)

    def test_all_combinations_credit_once_before_fractional_carry_and_keep_cap(self):
        fixture = CombatXpCap()
        for stamp, calendar in ((FRIDAY, 1), (SATURDAY, 1.5)):
            for level in (1, 4, 5, 10, 11, 15, 17):
                for premium, residence in ((0, 0), (1, .15), (2, .30)):
                    for source, boost in ((None, 1), (3112, 1.1), (3113, 1.3), (3114, 1.5), (3561, 1.7)):
                        f, ch, spec = fixture.fighter(level, premium)
                        f.sess.effects = session(source).effects
                        with patch.object(p.time, 'time', return_value=stamp):
                            for _ in range(100):
                                f.credit_xp(p.SHOOTING, spec, .01, fixture.mob(level + 4))
                        reward = p.combat_mob_xp(level + 4, level) * (max(calendar, boost) + residence)
                        self.assertEqual(fixture.spec_total(ch, spec), int(reward + 1e-9))
                        self.assertAlmostEqual(ch.xp_carry['spec', spec], reward % 1)
                        self.assertEqual(ch.skill[p.SHOOTING][1], 0 if level == 17 else int(reward + 1e-9))

    def test_expired_intux_falls_back_to_calendar_and_reductions_still_apply(self):
        f, ch, spec = CombatXpCap().fighter(15, 2)
        f.sess.effects = session(3561, 3206).effects
        f.sess.effects.active[3561].deadline = 0
        with patch.object(p.time, 'time', return_value=SATURDAY):
            reward = f.xp_reward(p.SHOOTING, 1, CombatXpCap().mob(19))
        self.assertAlmostEqual(reward, p.combat_mob_xp(19, 15) * 1.8 * .2)
        self.assertEqual(effects.multiplier(NS(), 'mob_exp', minimum=1.5), 1.5)

    def test_crossing_midnight_pays_damage_time_price_without_repricing_or_double_settlement(self):
        fixture = CombatXpCap()
        saturday = datetime(2026, 11, 28, tzinfo=p.COMBAT_XP_ZONE).timestamp()
        for source, boost in ((None, 1), (3113, 1.3), (3561, 1.7)):
            f, ch, spec = fixture.fighter(15, 2)
            f.sess.effects = session(source).effects
            target = fixture.mob(19)
            with patch.object(p.time, 'time', return_value=saturday - 1):
                f.award_xp(p.SHOOTING, spec, 99, target)
            with patch.object(p.time, 'time', return_value=saturday):
                f.award_xp(p.SHOOTING, spec, 1, target)
                fixture.settle(target, f)
                before = (ch.skill[p.SHOOTING][:], ch.spec[spec][:], dict(ch.xp_carry))
                fixture.settle(target, f)
            expected = p.combat_mob_xp(19, 15) * ((boost + .3) * .99 + (max(1.5, boost) + .3) * .01)
            self.assertAlmostEqual(ch.skill[p.SHOOTING][1] + ch.xp_carry[p.SHOOTING], expected)
            self.assertEqual((ch.skill[p.SHOOTING], ch.spec[spec], ch.xp_carry), before)

    def test_rewards_rise_and_adjacent_level_kill_counts_grow_by_at_most_two_point_five(self):
        for calendar in (1, 1.5):
            for gap in range(-3, 5):
                for role in (.7, 1, 3):
                    for residence in (0, .15, .30):
                        for boost in (1, 1.1, 1.3, 1.5, 1.7):
                            previous_reward, previous_kills = 0, 0
                            for level in range(max(1, 1 - gap), 17):
                                reward = p.combat_mob_xp(level + gap, level, xp_mult=role) * (max(calendar, boost) + residence)
                                kills = math.ceil(p.skill_xp_max(level) / reward)
                                self.assertGreater(reward, previous_reward)
                                self.assertGreaterEqual(kills, previous_kills)
                                if previous_kills:
                                    self.assertLessEqual(kills, previous_kills * 2.5,
                                        (calendar, gap, role, residence, boost, level, previous_kills, kills))
                                previous_reward, previous_kills = reward, kills
        self.assertEqual(p.combat_mob_xp(11, 15), 0)


if __name__ == '__main__':
    run_cases(WeekendExperience)
