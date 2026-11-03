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
        f.sess = NS(character=lambda: ch, push_vitals=lambda: None)
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

    def test_equal_lower_and_ceiling_rewards_below_17_retain_the_existing_formula(self):
        for level in range(17):
            for mob in (max(0, level - 2), level, level + 4, level + 5):
                for share in (0, .125, .5, 1):
                    for mult in (.7, 1, 3):
                        self.assertEqual(p.combat_mob_xp(mob, level, share, mult), p.mob_xp(mob, level, share, mult))

    def test_spec_reward_rises_to_level_16_maximum_at_gap_four(self):
        ceiling = p.mob_xp(17, 16)
        self.assertEqual(ceiling, 1996)
        expected = [748.5, 1060.375, 1372.25, 1684.125, 1996]
        for level in (17, 18, 19, 20):
            self.assertEqual([p.combat_mob_xp(17 + gap, level) for gap in range(5)], expected)
            for mob in (17, 18, 21, 30):
                for mult in (.7, 1, 3, 10):
                    full = min(ceiling, expected[min(mob - 17, 4)] * mult)
                    self.assertEqual(p.combat_mob_xp(mob, level, 1, mult), full)
                    self.assertEqual(p.combat_mob_xp(mob, level, .25, mult), full / 4)
            self.assertEqual(p.combat_mob_xp(15, level), 0)
        self.assertEqual(p.combat_mob_xp(16, 17), p.mob_xp(15, 16))
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
                    self.assertEqual(self.spec_total(ch, spec), 1996)

    def test_overkill_callbacks_do_not_multiply_spec_reward(self):
        f, ch, spec = self.fighter()
        mob = self.mob()
        for _ in range(10):
            f.award_xp(p.SHOOTING, spec, 99999, mob)
        self.settle(mob, f)
        self.assertEqual(ch.skill[p.SHOOTING][1], 0)
        self.assertEqual(self.spec_total(ch, spec), 1060)

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
            self.assertEqual(self.spec_total(ch, spec), 530)
            self.assertAlmostEqual(ch.xp_carry['spec', spec], .1875)
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
