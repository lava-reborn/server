"""One XP per mob for trained combat skills 17+, without sockets or AI."""
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
        return NS(level=level, stats=NS(hp_max=100, sp_max=100, role='mob', xp_mult=mult),
                  xp_ledger={})

    def settle(self, mob, *fighters):
        rc = NS(room=NS(players=[f.sess for f in fighters]))
        combat.RoomCombat.settle_xp(rc, mob)

    def test_lower_skills_retain_the_existing_formula(self):
        for level in range(17):
            for mob in (max(0, level - 2), level, level + 1, level + 5):
                for share in (0, .125, .5, 1):
                    for mult in (.7, 1, 3):
                        self.assertEqual(p.combat_mob_xp(mob, level, share, mult),
                                         p.mob_xp(mob, level, share, mult))

    def test_all_high_levels_and_boss_multipliers_are_capped(self):
        for level in (17, 18, 19, 20):
            for mob in (level - 1, level, level + 1, 30):
                for mult in (.7, 1, 3, 10):
                    self.assertEqual(p.combat_mob_xp(mob, level, 1, mult), 1)
                    self.assertEqual(p.combat_mob_xp(mob, level, .25, mult), .25)
            self.assertEqual(p.combat_mob_xp(level - 2, level), 0)

    def test_many_hits_settlement_and_premium_pay_only_one(self):
        for level in (17, 18, 19, 20):
            for premium in (0, 1, 2):
                for carry in (0, .9):
                    f, ch, spec = self.fighter(level, premium, carry=carry)
                    mob = self.mob(level + 1, mult=3)
                    for _ in range(100):
                        f.award_xp(p.SHOOTING, spec, 1, mob)
                    self.settle(mob, f)
                    self.assertEqual(ch.skill[p.SHOOTING][1], 1)
                    self.assertEqual(ch.spec[spec][1], 1)
                    self.settle(mob, f)
                    self.assertEqual(ch.skill[p.SHOOTING][1], 1)

    def test_overkill_and_repeated_hit_callbacks_cannot_multiply_reward(self):
        f, ch, spec = self.fighter()
        mob = self.mob()
        for _ in range(10):
            f.award_xp(p.SHOOTING, spec, 99999, mob)
        self.settle(mob, f)
        self.assertEqual(ch.skill[p.SHOOTING][1], 1)

    def test_cap_depends_on_trained_base_skill_not_character_or_gear(self):
        f, ch, spec = self.fighter(10, skill=p.MELEE)
        ch.set_skill(p.SHOOTING, 17)
        ch.bonus_skills[p.MELEE] = 10
        f.credit_xp(p.MELEE, spec, 1, self.mob(11))
        self.assertEqual(ch.skill[p.MELEE][1], int(p.mob_xp(11, 10)))
        self.assertGreater(ch.skill[p.MELEE][1], 1)
        f, ch, spec = self.fighter(16)
        ch.bonus_skills[p.SHOOTING] = 5
        f.credit_xp(p.SHOOTING, spec, 1, self.mob(17))
        self.assertEqual(ch.skill[p.SHOOTING][1], int(p.mob_xp(17, 16)))

    def test_group_shares_keep_fractional_carry(self):
        first, a, spec_a = self.fighter()
        second, b, spec_b = self.fighter()
        for _ in range(2):
            mob = self.mob()
            first.award_xp(p.SHOOTING, spec_a, 50, mob)
            second.award_xp(p.SHOOTING, spec_b, 50, mob)
            self.settle(mob, first, second)
        self.assertEqual((a.skill[p.SHOOTING][1], b.skill[p.SHOOTING][1]), (1, 1))

    def test_mining_healing_and_direct_rewards_are_unchanged(self):
        self.assertGreater(p.mob_xp(18, 17), 1)
        for skill in (p.MEDICINE, p.INDUSTRY, p.SHOOTING):
            ch = p.Character()
            ch.set_skill(skill, 17)
            ch.gain_xp(skill, 100)
            self.assertEqual(ch.skill[skill][1], 100)

    def test_level_16_to_17_switches_the_next_award_to_the_cap(self):
        f, ch, spec = self.fighter(16)
        ch.skill[p.SHOOTING][1] = ch.skill[p.SHOOTING][2] - 1
        f.credit_xp(p.SHOOTING, spec, 1, self.mob(17))
        self.assertEqual(ch.skill[p.SHOOTING][0], 17)
        before = ch.skill[p.SHOOTING][1]
        f.credit_xp(p.SHOOTING, spec, 1, self.mob(18))
        self.assertEqual(ch.skill[p.SHOOTING][1] - before, 1)


if __name__ == '__main__':
    run_cases(CombatXpCap)
