"""Additive PvE calendar, INTUX and residence, with damage-time awards."""
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

    def test_calendar_intux_and_residence_add_then_reductions_apply(self):
        for stamp, calendar in ((FRIDAY, 1), (SATURDAY, 1.5)):
            for residence in (0, .15, .30):
                for source, boost in ((None, 1), (3112, 1.1), (3113, 1.3), (3114, 1.5), (3561, 1.7)):
                    for reduction, factor in ((None, 1), (3205, .5), (3206, .2), (3207, .01)):
                        s = session(source, reduction)
                        got = effects.multiplier(s, 'mob_exp',
                                                 bonus=residence + p.combat_calendar_multiplier(stamp) - 1)
                        self.assertAlmostEqual(got, min(2.25, calendar + boost - 1 + residence) * factor)
                        # PvP and other callers retain their previous, non-calendar rule.
                        self.assertAlmostEqual(effects.multiplier(s, 'pl_exp', bonus=residence),
                                               (boost + residence) * factor)
        s = session(3561)
        s.effects.active['duplicate'] = NS(source=3561, deadline=10)
        self.assertEqual(effects.multiplier(s, 'mob_exp', bonus=.3 + .5), 2.25)

    def test_total_server_cap_applies_before_reductions_and_leaves_other_rewards_unchanged(self):
        for name in ('mob_exp', 'pl_exp'):
            for bonus, expected in ((0, 1.7), (.3, 2), (.5, 2.2),
                                    (.55, 2.25), (.65, 2.25), (.8, 2.25), (10, 2.25)):
                with self.subTest(name=name, bonus=bonus):
                    self.assertAlmostEqual(effects.multiplier(session(3561), name, bonus=bonus), expected)
                    for source, factor in ((3205, .5), (3206, .2), (3207, .01)):
                        self.assertAlmostEqual(effects.multiplier(session(3561, source), name, bonus=bonus),
                                               expected * factor)
            self.assertEqual(effects.multiplier(session(), name, bonus=10), 2.25)
        self.assertEqual(effects.multiplier(session(3789), 'mob_drop', bonus=10), 3)

    def test_calendar_applies_to_the_approved_base_without_extra_weekday_reduction(self):
        for level in range(18):
            base = p.COMBAT_XP_BASE[level]
            self.assertAlmostEqual(p.combat_mob_xp(level + 2, level), base)
            for stamp in (FRIDAY, SATURDAY):
                f, ch, spec = CombatXpCap().fighter(level)
                with patch.object(p.time, 'time', return_value=stamp):
                    got = f.xp_reward(p.SHOOTING, 1, CombatXpCap().mob(level + 2))
                self.assertAlmostEqual(got, base * (1.5 if stamp == SATURDAY else 1))
        self.assertEqual(p.COMBAT_XP_BASE[1:5], (23.75, 30.0751, 38.2775, 50.1567))
        self.assertEqual(p.mob_xp(10, 9), 267)  # noncombat legacy path unchanged

    def test_weekend_stacks_with_intux_and_residence_without_multiplying_bonuses(self):
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
                        self.assertAlmostEqual(reward, p.combat_mob_xp(level + gap, level, xp_mult=role)
                                               * (2.25 if stamp == SATURDAY else 2.0))
        f, ch, spec = fixture.fighter(15, 2)
        f.sess.effects = session(3561).effects
        with patch.object(p.time, 'time', return_value=SATURDAY):
            self.assertAlmostEqual(f.xp_reward(p.SHOOTING, 1, fixture.mob(19)), 2970)

    def test_approved_kill_counts_for_every_transition_and_requested_bonus_combination(self):
        expected = (
            ((7, 6), (6, 6), (6, 5)),
            ((10, 9), (10, 9), (9, 8)),
            ((16, 14), (15, 13), (13, 12)),
            ((24, 22), (22, 20), (20, 18)),
            ((37, 33), (33, 30), (30, 27)),
            ((56, 50), (51, 45), (45, 40)),
            ((84, 75), (76, 68), (68, 61)),
            ((126, 112), (114, 102), (102, 91)),
            ((189, 168), (172, 153), (153, 137)),
            ((304, 271), (276, 246), (246, 220)),
            ((423, 377), (384, 342), (343, 305)),
            ((599, 534), (545, 485), (486, 433)),
            ((861, 767), (783, 697), (698, 622)),
            ((1386, 1234), (1260, 1122), (1124, 1001)),
            ((2230, 1986), (2027, 1806), (1808, 1611)),
            ((3087, 2750), (2806, 2500), (2503, 2230)),
        )
        for level, row in enumerate(expected, 1):
            for (premium, source), counts in zip(((0, 3114), (1, 3114), (1, 3561)), row):
                for skill in (p.MELEE, p.SHOOTING):
                    f, ch, spec = CombatXpCap().fighter(level, premium, skill=skill)
                    f.sess.effects = session(source).effects
                    with patch.object(p.time, 'time', return_value=FRIDAY):
                        rewards = [f.xp_reward(skill, 1, CombatXpCap().mob(level + gap)) for gap in (1, 2)]
                    self.assertEqual(tuple(math.ceil(p.skill_xp_max(level) / reward) for reward in rewards),
                                     counts, (level, premium, source, skill))
        # Calendar-only and calendar + INTUX have distinct, additive rewards.
        self.assertEqual(effects.multiplier(session(), 'mob_exp', bonus=.15 + .5), 1.65)

    def test_weekend_and_intux_have_explicit_additive_totals(self):
        expected = {3114: (2, 2.15, 2.25), 3561: (2.2, 2.25, 2.25)}
        for source, totals in expected.items():
            for premium, total in enumerate(totals):
                f, _ch, _spec = CombatXpCap().fighter(15, premium)
                f.sess.effects = session(source).effects
                with patch.object(p.time, 'time', return_value=SATURDAY):
                    self.assertAlmostEqual(f.xp_reward(p.SHOOTING, 1, CombatXpCap().mob(17)),
                                           1100 * total)

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
                        reward = p.combat_mob_xp(level + 4, level) * min(2.25, calendar + boost - 1 + residence)
                        self.assertEqual(fixture.spec_total(ch, spec), int(reward + 1e-9))
                        self.assertAlmostEqual(ch.xp_carry['spec', spec],
                                               max(0, reward - int(reward + 1e-9)))
                        self.assertEqual(ch.skill[p.SHOOTING][1], 0 if level == 17 else int(reward + 1e-9))

    def test_expired_intux_falls_back_to_calendar_and_reductions_still_apply(self):
        f, ch, spec = CombatXpCap().fighter(15, 2)
        f.sess.effects = session(3561, 3206).effects
        f.sess.effects.active[3561].deadline = 0
        with patch.object(p.time, 'time', return_value=SATURDAY):
            reward = f.xp_reward(p.SHOOTING, 1, CombatXpCap().mob(19))
        self.assertAlmostEqual(reward, p.combat_mob_xp(19, 15) * 1.8 * .2)
        self.assertEqual(effects.multiplier(NS(), 'mob_exp', bonus=.5), 1.5)

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
            expected = p.combat_mob_xp(19, 15) * (min(2.25, boost + .3) * .99 + min(2.25, boost + .5 + .3) * .01)
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
                                reward = p.combat_mob_xp(level + gap, level, xp_mult=role) * min(2.25, calendar + boost - 1 + residence)
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
