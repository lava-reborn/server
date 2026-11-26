"""Native PvP crit routing, permanent investment, buff grades and XP relief."""
import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import battle_balance as balance
import combat
import effects
import items
import progression as p
import sets
from testkit import run_cases


def character():
    ch = p.Character()
    ch.set_skill(p.SHOOTING, 17)
    ch.set_skill(p.MELEE, 17)
    for spec in range(2, 8):
        ch.set_spec(spec, 3)
    ch.set_gear(sets.zero())
    return ch


class PvPCriticalBalance(unittest.TestCase):
    def test_floor_ceiling_and_non_optimal_distance(self):
        for cp in (0, 5, 20, 100, 10000):
            for ce in (0, 5, 20, 100, 10000):
                for attack, defence in ((0, 0), (30, 0), (0, 30), (10000, 10000)):
                    chance = balance.pvp_critical_chance(cp, ce, attack, defence)
                    self.assertGreaterEqual(chance, 3)
                    self.assertLessEqual(chance, 90)
                    self.assertEqual(balance.pvp_critical_chance(cp, ce, attack, defence, False), chance / 2)

    def test_anticrit_never_removes_more_than_half_including_every_temporary_bonus(self):
        for cp in (0, 5, 20, 60, 100, 300, 10000):
            for temporary_cp in (0, 4, 30, 10000):
                unopposed = balance.pvp_critical_chance(cp, 0, temporary_cp)
                for ce in (0, 5, 40, 100, 1000, 10000):
                    for temporary_ce in (0, 4, 30, 10000):
                        for optimal in (True, False):
                            defended = balance.pvp_critical_chance(cp, ce, temporary_cp,
                                                                   temporary_ce, optimal)
                            reference = unopposed if optimal else unopposed / 2
                            self.assertGreaterEqual(defended, reference / 2)
                            self.assertLessEqual(defended, reference)
        self.assertEqual(balance.pvp_critical_chance(10000, 0), 90)
        self.assertEqual(balance.pvp_critical_chance(10000, 0, optimal=False), 45)

    def test_extra_permanent_ratings_and_ordinary_pills_still_help_high_rating_builds(self):
        for cp, ce in ((10, 10), (40, 40), (100, 100), (300, 300), (1000, 1000)):
            chance = balance.pvp_critical_chance(cp, ce)
            self.assertGreater(balance.pvp_critical_chance(cp + 1, ce), chance)
            self.assertLess(balance.pvp_critical_chance(cp, ce + 1), chance)
            self.assertGreater(balance.pvp_critical_chance(cp, ce, 4), chance)
            self.assertLess(balance.pvp_critical_chance(cp, ce, 0, 4), chance)

    def test_top_alpha_and_omega_each_have_a_measurable_effect_on_high_level_ratings(self):
        chance = balance.pvp_critical_chance(100, 80)
        alpha = balance.pvp_critical_chance(100, 80, 30)
        omega = balance.pvp_critical_chance(100, 80, 0, 30)
        self.assertGreater(alpha - chance, 1)
        self.assertGreater(chance - omega, 1)
        self.assertGreater(balance.pvp_critical_chance(100, 80, 4), chance)
        self.assertLess(balance.pvp_critical_chance(100, 80, 0, 4), chance)
        self.assertLess(alpha, balance.pvp_critical_chance(110, 80))
        self.assertGreater(omega, balance.pvp_critical_chance(100, 110))

    def test_permanent_growth_has_full_weight_and_temporary_power_tapers(self):
        base = balance.pvp_critical_chance(100, 80)
        trained = balance.pvp_critical_chance(110, 80)
        pill = balance.pvp_critical_chance(100, 80, 30)
        strongest = balance.pvp_critical_chance(100, 80, 100000)
        self.assertGreater(trained, base)
        self.assertGreater(pill, base)
        self.assertLess(pill - base, trained - base)
        self.assertLess(strongest, trained)
        self.assertLess(balance.pvp_critical_chance(100, 90), base)
        self.assertLess(balance.pvp_critical_chance(100, 80, 0, 30), base)

    def test_permanent_ratings_never_hurt_even_near_the_probability_bounds(self):
        for temporary_cp, temporary_ce in ((0,0),(30,0),(0,30),(30,30)):
            for opponent in (0,20,100,1000):
                values = [balance.pvp_critical_chance(cp,opponent,temporary_cp,temporary_ce)
                          for cp in range(0,2001,5)]
                self.assertTrue(all(a <= b for a,b in zip(values,values[1:])))
                values = [balance.pvp_critical_chance(opponent,ce,temporary_cp,temporary_ce)
                          for ce in range(0,2001,5)]
                self.assertTrue(all(a >= b for a,b in zip(values,values[1:])))

    def test_invalid_permanent_crit_snapshot_is_rejected_before_attack_acceptance(self):
        weapon = combat.Weapon(1,10,20,1,10,20,1,1,10,p.SHOOTING,2)
        for bad in (True,float('nan'),float('inf'),-1,11):
            with self.assertRaises(ValueError):
                combat.checked_weapon(weapon,weapon._replace(base_crit=bad))

    def test_all_ordinary_alpha_and_omega_grades_keep_distinct_benefits(self):
        for key, grades in (('cp', ((4181, 3116, 3118, 4182), (3115, 3117, 3119, 4183))),
                            ('ce', ((3208, 3210, 3212, 4184), (3209, 3211, 3213, 4185)))):
            for ids in grades:
                values = [effects.definition(i)['bonuses'][key] for i in ids]
                chances = [balance.pvp_critical_chance(100, 80, v if key == 'cp' else 0,
                           v if key == 'ce' else 0) for v in values]
                for first, second in zip(chances, chances[1:]):
                    self.assertGreater(second if key == 'cp' else first,
                                       first if key == 'cp' else second)

    def test_temporary_crit_removes_every_attribute_and_flat_rating_once(self):
        ch = character()
        ch.effects = effects.zero()
        ch.effects['attribs'] = [3, 3, 0, 2, 3]
        ch.effects['cp'], ch.effects['ce'] = 30, 30
        for kind in (items.PISTOL, items.SHOTGUN, items.ASSAULT, items.RIFLE, items.MACHINEGUN, items.SMG):
            permanent = copy.deepcopy(ch)
            permanent.effects = effects.zero()
            permanent.set_gear(sets.zero())
            ch.set_gear(sets.zero())
            full = p.crit_chance(ch, kind)
            base = p.crit_chance(permanent, kind)
            extra = p.temporary_crit(ch, kind)
            self.assertEqual(tuple(a-b for a,b in zip(full,base)), extra)

    def test_native_weapon_snapshots_permanent_crit_and_preserves_shot_after_buff_expiry(self):
        ch = character()
        base = p.crit_chance(ch, items.PISTOL)[0]
        ch.effects = effects.zero()
        ch.effects['cp'] = 30
        ch.effects['attribs'][p.AGILITY] = 3
        ch.set_gear(sets.zero())
        cp = p.crit_chance(ch, items.PISTOL)[0]
        raw = combat.Weapon(1, 10, 20, 1, 10, 20, 1, 1, cp, p.SHOOTING, 2)
        weapon = balance.weapon(raw, ch, dict(type_id=25637, cur_mode=0), {})
        self.assertEqual(weapon.base_crit, base)
        target_ch = character()
        target = NS(is_player=True, character=lambda: target_ch,
                    crit_evade_ranged=lambda: p.crit_chance(target_ch, items.PISTOL)[1])
        shooter = NS(is_player=True, character=lambda: ch)
        with patch.object(combat, 'roll', side_effect=lambda chance: chance):
            before = balance.ranged_critical(shooter, target, weapon, True, ordinary=True)
            ch.effects = effects.zero()
            ch.set_gear(sets.zero())
            after = balance.ranged_critical(shooter, target, weapon, True, ordinary=True)
            self.assertEqual(after, before)
            self.assertEqual(balance.ranged_critical(shooter, target, weapon, False, ordinary=True), before / 2)
            legacy = balance.ranged_critical(shooter, target, weapon, True)
            self.assertEqual(legacy, max(0, min(100, cp - target.crit_evade_ranged())))

    def test_native_melee_uses_the_same_curve_without_changing_private_rules(self):
        ch, victim = character(), character()
        a = NS(is_player=True, character=lambda: ch)
        b = NS(is_player=True, character=lambda: victim)
        raw = combat.melee_crit(ch, 1) - combat.melee_crit_evade(victim)
        with patch.object(combat, 'roll', side_effect=lambda chance: chance):
            current = balance.melee_critical(a, b, raw, ordinary=True)
            self.assertEqual(current, balance.pvp_critical_chance(combat.melee_crit(ch,1),
                                                               combat.melee_crit_evade(victim)))
            self.assertEqual(balance.melee_critical(a, b, raw), max(0, min(100, raw)))

    def test_temporary_intellect_keeps_a_positive_but_bounded_damage_and_healing_bonus(self):
        ch = character()
        for rate in (balance.DAMAGE_PER_INTELLECT, balance.HEAL_PER_INTELLECT):
            base = balance.attribute_multiplier(ch, rate)
            ch.effects = effects.zero()
            ch.effects['attribs'][p.INTELLECT] = 3
            boosted = balance.attribute_multiplier(ch, rate)
            self.assertGreater(boosted, base)
            self.assertLessEqual(boosted, base * 1.03)
            del ch.effects
            ch.attrib[p.INTELLECT] += 3
            self.assertGreater(balance.attribute_multiplier(ch, rate), boosted)
            ch.attrib[p.INTELLECT] -= 3

    def test_intellect_stimulant_grades_remain_distinct_after_limiting(self):
        ch = character()
        ch.effects = effects.zero()
        for rate in (balance.DAMAGE_PER_INTELLECT, balance.HEAL_PER_INTELLECT):
            values = []
            for extra in (1, 2, 3):
                ch.effects['attribs'][p.INTELLECT] = extra
                values.append(balance.attribute_multiplier(ch, rate))
            self.assertLess(values[0], values[1])
            self.assertLess(values[1], values[2])

    def test_approved_xp_relief_preserves_start_and_all_gap_rewards(self):
        self.assertEqual(p.COMBAT_XP_BASE[:11], (20,23.75,30.0751,38.2775,50.1567,66.1157,
                         86.8385,115.2115,153.11,203.2552,252.58061816))
        for level, base in ((11, 363.0088964189), (12, 512.1589986209), (13, 712.3213673975), (14, 885.1855761029), (15, 1100.0), (16, 1366.945003018)):
            for gap, factor in ((-4,0),(-3,.15),(-2,.30),(-1,.50),(0,890/1100),(1,980/1100),(2,1),(3,1.1),(4,1.2)):
                self.assertAlmostEqual(p.combat_mob_xp(level+gap,level),base*factor)
                self.assertAlmostEqual(p.combat_mob_xp(level+gap,level,.25),base*factor/4)
        self.assertTrue(all(a < b for a,b in zip(p.COMBAT_XP_BASE[:16],p.COMBAT_XP_BASE[1:17])))


if __name__ == '__main__':
    run_cases(PvPCriticalBalance)
