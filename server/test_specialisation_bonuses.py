"""Specialisations affect actions, derived stats and progression independently.

Use real attack/healing entry points with deterministic rolls. Client visual
updates still need the Flash check; these assertions cover server outcomes.
"""
import os
import random
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

import battle_balance
import combat
import inventory
import items
import progression as p
from testkit import attack_fixture, healing_fixture, run_cases
from training.arena import TrainingFighter


class SpecialisationBonuses(unittest.IsolatedAsyncioTestCase):
    async def test_galil_at_level_thirteen_uses_fourth_spec_and_actual_ammo_in_every_fire_mode(self):
        params = items.params_of(25201)
        self.assertEqual(params['h_damage_min'], [62, 42, 26])
        self.assertEqual(params['h_damage_max'], [137, 61, 44])
        for mode in range(3):
            cones = []
            for ammo_type in (6107, 6119, 6143):
                f, ch, _, _, _, row = attack_fixture(25201)
                for skill in ch.skill:
                    skill[0] = 13
                ch.spec[combat.SPEC_OF_WEAPON[items.ASSAULT]][0] = 4
                row.update(ammo_type=ammo_type, cur_mode=mode, ammo_count=25)
                combat.Fighter.use_fire(f, dict(obj='weapon', target='000000005'))
                try:
                    self.assertIsNotNone(f.aim)
                    shot = f.aim._args[-1][3]
                    expected = combat.cone_of(combat.spread_factor(13, 4), params['target_size'][mode],
                                              items.params_of(ammo_type)['acc_mod'], params['max_range'][mode])
                    if params['fire_mods'][mode] == 1:
                        expected *= .8
                    self.assertAlmostEqual(shot.cone, expected)
                    self.assertEqual(shot.hit_cap, .95)
                    cones.append(shot.cone)
                    rng = random.Random(25201 + mode)
                    for distance in (2, 5, params['end_opt_range'][mode], shot.max_range):
                        hits = sum(combat.on_target(combat.bullet_offset(shot.cone, distance, rng))
                                   for _ in range(10000))
                        self.assertAlmostEqual(hits / 10000, combat.hit_probability(shot.cone, distance), delta=.02)
                finally:
                    if f.aim:
                        f.aim.cancel()
            self.assertGreater(cones[0], cones[1])
            self.assertGreater(cones[1], cones[2])

    def test_reset_above_attribute_cap_keeps_the_remaining_specialisation_bonus(self):
        ch = p.Character()
        for index in (1, 4, 7, 9):
            ch.set_spec(index, 5)
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        self.assertEqual(ch.set_spec(9, -1)['attribs'], set())
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        self.assertEqual(ch.set_spec(7, -1)['attribs'], {p.AGILITY})
        self.assertEqual(ch.attrib[p.AGILITY], 15)
        ch.set_spec(9, 5)
        self.assertEqual(ch.attrib[p.AGILITY], 20)

    def test_direct_spec_levels_cross_the_cap_in_both_directions(self):
        ch = p.Character()
        for index in (1, 4, 7):
            ch.set_spec(index, 5)
        ch.set_spec(9, 4)
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        self.assertEqual(ch.set_spec(9, 1)['attribs'], set())
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        ch.set_spec(7, 3)
        self.assertEqual(ch.attrib[p.AGILITY], 19)
        ch.set_spec(9, 5)
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        ch.set_spec(9, 0)
        self.assertEqual(ch.attrib[p.AGILITY], 18)

    def test_xp_gain_and_removal_are_reversible_when_other_specs_fill_the_cap(self):
        ch = p.Character()
        xp = sum(p.spec_xp_max(level) for level in range(5))
        for index in (1, 4, 7, 9):
            ch.set_spec(index, 0)
            ch.add_spec_xp(index, xp)
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        self.assertEqual(ch.add_spec_xp(9, -xp)['attribs'], set())
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        ch.add_spec_xp(7, -xp)
        self.assertEqual(ch.attrib[p.AGILITY], 15)
        ch.gain_spec_xp(7, xp)
        self.assertEqual(ch.attrib[p.AGILITY], 20)
        ch.gain_spec_xp(9, xp)
        self.assertEqual(ch.attrib[p.AGILITY], 20)

    def test_all_linked_attributes_restore_after_reset_with_gear_kept_separate(self):
        for attribute in (p.STRENGTH, p.AGILITY, p.PERCEPTION, p.INTELLECT):
            with self.subTest(attribute=attribute):
                ch = p.Character()
                ch.set_skill(p.SHOOTING, 10)
                ch.bonus_attribs = [7] * p.ATTRIBS
                baseline = ch.attrib[:]
                indices = [i for i, a in enumerate(p.SPEC_ATTRIB) if a == attribute]
                for index in indices:
                    ch.set_spec(index, 5)
                self.assertEqual(ch.attrib[attribute], min(20, 5 + 5 * len(indices)))
                for index in indices:
                    ch.forget_spec(index)
                self.assertEqual(ch.attrib, baseline)
                self.assertEqual(ch.bonus_attribs, [7] * p.ATTRIBS)
                self.assertEqual(ch.attr(attribute), baseline[attribute] + 7)

    def test_custom_admin_attributes_above_cap_are_not_normalized_by_spec_changes(self):
        ch = p.Character()
        ch.attrib[p.AGILITY] = 1000
        ch.set_spec(1, 5)
        self.assertEqual(ch.attrib[p.AGILITY], 1000)
        ch.add_spec_xp(1, -sum(p.spec_xp_max(level) for level in range(5)))
        self.assertEqual(ch.attrib[p.AGILITY], 1000)
        ch.set_spec(1, 5)
        ch.forget_spec(1)
        self.assertEqual(ch.attrib[p.AGILITY], 1000)

    def test_cap_contribution_survives_reload_without_rewriting_legacy_attributes(self):
        import accounts
        store = accounts.Store(':memory:')
        try:
            account, error = store.register('spec-cap-test', 'secret')
            self.assertIsNone(error)
            char_id, _ = store.create_character(account, 'SpecCapTest', 0, '45676')
            ch = p.Character.load(store, char_id)
            for index in (1, 4, 7, 9):
                ch.set_spec(index, 5)
            ch.save(store)
            ch = p.Character.load(store, char_id)
            ch.forget_spec(9)
            self.assertEqual(ch.attrib[p.AGILITY], 20)
            ch.save(store)
            ch = p.Character.load(store, char_id)
            ch.forget_spec(7)
            self.assertEqual(ch.attrib[p.AGILITY], 15)
            # An old inconsistent saved value has no recoverable audit trail.
            # Loading must not guess a replacement base attribute.
            ch.attrib[p.AGILITY] = 12
            ch.save(store)
            self.assertEqual(p.Character.load(store, char_id).attrib[p.AGILITY], 12)
        finally:
            store.close()

    def test_each_learnable_specialisation_raises_its_attribute_and_reverses(self):
        for index, attribute in enumerate(p.SPEC_ATTRIB[:12]):
            with self.subTest(index=index):
                ch = p.Character()
                before = (ch.attrib[:], ch.hp_max, ch.sp_max, ch.max_weight(), ch.armor)
                changed = ch.set_spec(index, 5)
                self.assertEqual(ch.attrib[attribute], before[0][attribute] + 5)
                self.assertEqual(ch.hp_max - before[1], 20 if attribute == p.STRENGTH else 0)
                self.assertEqual(ch.sp_max - before[2], 20 if attribute == p.AGILITY else 0)
                self.assertEqual(ch.max_weight() - before[3], 10000 if attribute == p.STRENGTH else 0)
                self.assertEqual(ch.armor - before[4], {p.AGILITY: 3.75, p.PERCEPTION: 1.25}.get(attribute, 0))
                self.assertEqual(changed['attribs'], {attribute})
                ch.forget_spec(index)
                self.assertEqual((ch.attrib, ch.hp_max, ch.sp_max, ch.max_weight(), ch.armor), before)

    async def test_residence_bonus_applies_to_completed_healing_skill_and_specialisation(self):
        awards = []
        for premium in (0, 1, 2):
            f, ch, _, _ = healing_fixture()
            ch.premium = premium
            ch.set_spec(9, 0)
            ch.hp = ch.hp_max // 2
            with patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: hi):
                f.heal_now(1, f)
            skill_level, skill_xp, _ = ch.skill[p.MEDICINE]
            skill_total = sum(p.skill_xp_max(i) for i in range(skill_level)) + skill_xp
            awards.append((skill_total, ch.spec[9][1]))
        base = sum(awards[0])
        self.assertEqual([sum(award) for award in awards],
                         [base, int(base + base * .15), int(base + base * .30)])
        self.assertTrue(all(skill - spec in (0, 1) for skill, spec in awards))

    def test_residence_bonus_applies_to_quest_spec_xp_but_not_admin_awards(self):
        for premium, expected in ((0, 100), (1, 115), (2, 130)):
            ch = p.Character()
            ch.premium = premium
            ch.set_spec(2, 0)
            ch.gain_spec_xp(2, 100)
            self.assertEqual(ch.spec[2][1], expected)
            ch.add_spec_xp(2, 100)
            self.assertEqual(ch.spec[2][1], expected + 100)
            ch.add_skill_xp(p.SHOOTING, 100)
            self.assertEqual(ch.skill[p.SHOOTING], [1, 0, p.skill_xp_max(1)])

    def test_each_learnable_specialisation_gains_levels_xp_and_reports_effective_values(self):
        for index in range(12):
            with self.subTest(index=index):
                ch = p.Character()
                ch.learn_spec(index)
                changed = ch.gain_spec_xp(index, p.SPEC_XP_START)
                self.assertEqual(ch.spec[index], [1, 0, p.spec_xp_max(1)])
                self.assertEqual(changed['specs'], {index})
                self.assertEqual(ch.rp_info(specs={index})['f_specs'], [1])
                self.assertEqual(ch.rp_info(specs={index})['a_specs'], [1])

    def test_gear_specialisation_bonus_does_not_unlock_unlearned_specialisation(self):
        ch = p.Character()
        ch.bonus_specs = [3] * p.SPECS
        self.assertEqual([ch.spec_level(i) for i in range(p.SPECS)], [-1] * p.SPECS)
        ch.set_spec(2, 1)
        self.assertEqual(ch.spec_level(2), 4)
        self.assertEqual(ch.rp_info(specs={2})['f_specs'], [4])

    def test_hidden_production_specialisations_cannot_be_bought(self):
        for index in range(12, 15):
            ch = p.Character()
            self.assertEqual(ch.learn_spec(index), p.ERR_STATE)
            self.assertEqual(ch.spec_level(index), -1)

    async def test_all_firearm_classes_use_matching_spec_for_live_aim_and_critical(self):
        for weapon_type, spec in combat.SPEC_OF_WEAPON.items():
            candidates = [type_id for type_id, (root, _) in sorted(items.catalogue().items())
                          if root == items.FIRE_ARM and items.params_of(type_id).get('weapon_type') == weapon_type
                          and items.params_of(type_id).get('fire_mods', [0])[0]]
            self.assertTrue(candidates, weapon_type)
            def required(type_id):
                si = items.params_of(type_id)
                return inventory.unpacked(si.get('need_specs_m', 0), si.get('need_specs'), p.SPECS)[spec]
            chosen = min(candidates, key=required)
            first_level = max(1, required(chosen))
            self.assertLess(first_level, 5, weapon_type)
            results = []
            for level in (first_level, 5):
                f, ch, room, _, _, row = attack_fixture(chosen)
                for sp in ch.spec:
                    sp[0] = 5
                ch.spec[spec][0] = level
                row['ammo_type'] = items.params_of(row['type_id'])['comp_array'][0]
                combat.Fighter.use_fire(f, dict(obj='weapon', target='000000005'))
                self.assertIsNotNone(f.aim, (weapon_type, level))
                args = f.aim._args[-1]
                f.aim.cancel()
                results.append(args[3])
            beginner, master = results
            self.assertEqual((beginner.spec, master.spec), (spec, spec))
            self.assertAlmostEqual(master.crit - beginner.crit, 5 - first_level)
            self.assertLess(master.cone, beginner.cone)
            self.assertEqual((master.dmin, master.dmax), (beginner.dmin, beginner.dmax))

    def test_melee_specs_have_separate_hit_critical_and_defence_effects(self):
        ch = p.Character()
        for spec in (combat.SPEC_FIST, combat.SPEC_BLADE):
            ch.spec[spec][0] = 0
            hit, crit = combat.melee_hit_chance(ch, spec), combat.melee_crit(ch, spec)
            ch.spec[spec][0] = 5
            self.assertEqual(combat.melee_hit_chance(ch, spec) - hit, 25)
            self.assertEqual(combat.melee_crit(ch, spec) - crit, 30)
        ch.spec[combat.SPEC_BLADE][0] = 0
        dodge = p.melee_evade(ch)
        ch.spec[combat.SPEC_BLADE][0] = 5
        self.assertEqual(p.melee_evade(ch) - dodge, 5)
        ch.spec[combat.SPEC_FIST][0] = 0
        evade = combat.melee_crit_evade(ch)
        ch.spec[combat.SPEC_FIST][0] = 5
        self.assertEqual(combat.melee_crit_evade(ch) - evade, 5)

    def test_medical_selection_matches_named_specs_in_world_and_training_profiles(self):
        for combat_v2 in (False, True):
            f = NS(sess=NS(ground=NS(rules=NS(combat_v2=combat_v2))))
            for hp, expected in ((29, 8), (30, 9), (31, 9)):
                v = dict(hcur=hp, hmax=100)
                self.assertEqual(combat.Fighter.healing_spec(f, v), expected)
                self.assertEqual(TrainingFighter.healing_spec(f, v), expected,
                                 (combat_v2, hp))

    async def test_completed_heal_uses_correct_medical_spec_and_awards_only_that_spec(self):
        for profile in ('world', 'training_legacy', 'training_v2'):
            for hp, selected in ((20, 8), (30, 9), (60, 9)):
                values = []
                for boosted in (None, selected, 17 - selected):
                    f, ch, room, used = healing_fixture()
                    if profile != 'world':
                        f.sess.ground = NS(rules=NS(combat_v2=profile == 'training_v2'))
                        f.healing_spec = lambda vitals: TrainingFighter.healing_spec(f, vitals)
                    ch.bonus_hp = 880
                    ch.hp, ch.sp = hp * 10, 0
                    ch.spec[8][0] = ch.spec[9][0] = 0
                    if boosted is not None:
                        ch.spec[boosted][0] = 5
                    before = ch.hp
                    with patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: hi):
                        f.heal_now(1, f)
                    self.assertEqual(used, [1])
                    self.assertGreater(ch.spec[selected][1], 0, (profile, hp))
                    self.assertEqual(ch.spec[17 - selected][1], 0, (profile, hp))
                    values.append(ch.hp - before)
                self.assertEqual(values[1], 2 * values[0], (profile, hp, values))
                self.assertEqual(values[2], values[0], (profile, hp, values))

    def test_surgery_intellect_increases_world_healing_and_weapon_damage_without_shorter_cooldown(self):
        ch = p.Character()
        weapon = combat.Weapon(1, 100, 100, 1, 5, 10, 1, .1, 5, 1, 2)
        baseline = battle_balance.weapon(weapon, ch, None, {})
        ch.set_spec(8, 5)
        result = battle_balance.weapon(weapon, ch, None, {})
        self.assertEqual((baseline.dmin, result.dmin), (100, 115))
        self.assertAlmostEqual(battle_balance.healing_multiplier(ch), 1.2)
        self.assertEqual(combat.Fighter.medicine_cooldown_seconds(None), 6)


if __name__ == '__main__':
    run_cases(SpecialisationBonuses)
