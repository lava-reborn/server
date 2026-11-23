"""Ordinary single-shot accuracy, bounded scatter and private-profile isolation."""
import copy
import math
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import battle_balance
import combat
import holdings
import inventory
import items
import progression
from testkit import run_cases
from training.arena import TrainingFighter
from training import bot
from training.rules import Rules


class SingleShotAccuracy(unittest.TestCase):
    def character(self, level=13, spec=4):
        ch = progression.Character()
        ch.skill[progression.SHOOTING][0] = level
        for index in combat.SPEC_OF_WEAPON.values():
            ch.spec[index][0] = spec
        return ch

    def weapon(self, shots=1, cone=.1):
        return combat.Weapon(shots, 100, 200, 2, 5, 100, 1, cone, 10,
                             progression.SHOOTING, 5, sdmin=30, sdmax=50)

    def test_all_classes_and_modes_keep_identity_and_boost_only_native_single_rifle_or_assault(self):
        ch = self.character()
        for kind in combat.SPEC_OF_WEAPON:
            params = dict(weapon_type=kind, fire_mods=[1, 3, 6])
            for mode, shots in enumerate(params['fire_mods']):
                with self.subTest(weapon_type=kind, mode=mode):
                    original = self.weapon(shots)
                    with patch.object(inventory, 'item_level', return_value=13), \
                            patch.object(items, 'params_of', return_value=params):
                        result = battle_balance.weapon(original, ch, dict(type_id=1, cur_mode=mode), {})
                    bonus = .8 if shots == 1 and kind in (items.ASSAULT, items.RIFLE) else 1
                    self.assertAlmostEqual(result.cone, original.cone * bonus)
                    self.assertEqual(result.hit_cap, .95)
                    for field in original._fields:
                        if field not in ('cone', 'hit_cap'):
                            self.assertEqual(getattr(result, field), getattr(original, field), field)
                    self.assertEqual(combat.checked_weapon(original, result), result)

    def test_last_round_of_a_burst_does_not_gain_single_shot_accuracy(self):
        params = dict(weapon_type=items.ASSAULT, fire_mods=[1, 3, 6])
        for mode in (1, 2):
            original = self.weapon(1)
            with patch.object(inventory, 'item_level', return_value=13), \
                    patch.object(items, 'params_of', return_value=params):
                result = battle_balance.weapon(original, self.character(), dict(type_id=1, cur_mode=mode), {})
            self.assertEqual(result.cone, original.cone)
            self.assertEqual(result.hit_cap, .95)

    def test_spec_ammo_and_senior_gear_are_preserved_at_near_and_maximum_distances(self):
        params = items.params_of(25803)
        frozen = copy.deepcopy(params)
        for spec in (2, 4, 5):
            ch = self.character(spec=spec)
            for precision in (.8, 1, 1.1):
                ammo = dict(acc_mod=precision, dam_mod=1.1, st_mod=1.3, range_mod=1.2)
                cone = combat.cone_of(combat.spread_factor(13, spec), params['target_size'][2],
                                      precision, params['max_range'][2])
                original = self.weapon(cone=cone)._replace(max_range=params['max_range'][2])
                for missing in range(4):
                    with self.subTest(spec=spec, ammo=precision, gap=missing):
                        ratio = 1 - missing * .05
                        with patch.object(inventory, 'item_level', return_value=13 + missing):
                            result = battle_balance.weapon(original, ch, dict(type_id=25803, cur_mode=2), ammo)
                        self.assertAlmostEqual(result.cone, cone * .8 / ratio)
                        self.assertAlmostEqual(result.hit_cap, .95 * ratio)
                        self.assertEqual((result.dmin, result.dmax, result.sdmin, result.sdmax),
                                         (110, 220, 39, 65))
                        self.assertEqual(result.max_range, math.floor(params['max_range'][2] * 1.2 + 1e-9))
                        self.assertEqual((result.opt_lo, result.opt_hi, result.crit, result.piercing),
                                         (original.opt_lo, original.opt_hi, original.crit, original.piercing))
                        distances = (0, 1, 5, result.max_range * .9, result.max_range * .95,
                                     result.max_range * .99, result.max_range)
                        for distance in distances:
                            chance = combat.hit_probability(result.cone, distance, result.hit_cap)
                            own = combat.hit_probability(cone * .8, distance, .95)
                            self.assertGreater(chance, 0)
                            self.assertLessEqual(chance, .95 * ratio)
                            self.assertAlmostEqual(chance, own * ratio)
        self.assertEqual(items.params_of(25803), frozen)

    def test_effective_skill_and_pouch_bonuses_above_training_limits_improve_scatter(self):
        ch = self.character(level=17, spec=5)
        before = copy.deepcopy(ch.rows())
        params = items.params_of(25803)
        row = dict(type_id=25803, cur_mode=2)

        def prepared():
            cone = combat.cone_of(combat.spread_factor(ch.skill_level(progression.SHOOTING),
                                                      combat.spec_or_zero(ch, 5)),
                                  params['target_size'][2], 1, params['max_range'][2])
            return battle_balance.weapon(self.weapon(cone=cone), ch, row, {})

        base = prepared()
        ch.bonus_specs[5] = 1
        pouch = prepared()
        self.assertLess(pouch.cone, base.cone)
        ch.bonus_skills[progression.SHOOTING] = 2
        enhanced = prepared()
        self.assertLess(enhanced.cone, pouch.cone)
        ch.bonus_specs[5] = 1000
        floor = prepared()
        self.assertGreater(floor.cone, 0)
        self.assertTrue(math.isfinite(floor.cone))
        self.assertEqual(floor.hit_cap, .95)
        self.assertEqual(ch.rows(), before)
        self.assertEqual(combat.spread_factor(1000, 1000),
                         combat.spread_factor(progression.SKILL_MAX, progression.SPEC_MAX))

    def test_zero_ammunition_scatter_keeps_the_cap_and_senior_gear_penalty(self):
        original = self.weapon()
        ch = self.character()
        for missing in range(4):
            with self.subTest(gap=missing), \
                    patch.object(inventory, 'item_level', return_value=13 + missing):
                zero = battle_balance.weapon(original, ch, dict(type_id=25803, cur_mode=2), {'acc_mod': 0})
                default = battle_balance.weapon(original, ch, dict(type_id=25803, cur_mode=2), {})
            self.assertEqual(zero.cone, 0)
            self.assertGreater(default.cone, 0)
            for distance in (0, 1, 5, 90, 95, 99, 100):
                chance = combat.hit_probability(zero.cone, distance, zero.hit_cap)
                self.assertAlmostEqual(chance, .95 * (1 - missing * .05))

    def resolve(self, weapon, distance, offset=0, covers=()):
        room = combat.RoomCombat.__new__(combat.RoomCombat)
        room.room = NS(loc=NS(width=128, height=2, obstacles=set()))
        room.bodies = lambda *_args: {}
        room.ranged_critical = lambda *_args: False
        room.bullet_damage = lambda *_args: (10, 0)
        shooter = NS(cell=0, is_player=True)
        target = Mock(cell=distance, sp_now=lambda: 100)
        with patch.object(combat, 'bullet_offset', return_value=offset) as scatter, \
                patch.object(combat, 'shot_wall', return_value=None), \
                patch.object(combat, 'bodies_between', return_value=list(covers)), \
                patch.object(combat, 'flight', return_value=([], ('faMiss', {}))) as flight, \
                patch.object(holdings, 'defender_friendly', return_value=False), \
                patch.object(combat, 'roll', side_effect=AssertionError('No second accuracy roll')):
            pairs, struck = room.resolve(shooter, target, target.cell, weapon, weapon.num_shots)
        return target, pairs, struck, scatter, flight

    def test_resolver_samples_one_capped_scatter_per_bullet_and_keeps_real_flight_distance(self):
        for distance in (0, 1, 5, 90, 95, 99, 100):
            for cap in (.95, .95 * .85):
                with self.subTest(distance=distance, cap=cap):
                    weapon = self.weapon(shots=3, cone=.0001)._replace(hit_cap=cap)
                    target, _, struck, scatter, flight = self.resolve(weapon, distance)
                    self.assertEqual(scatter.call_count, 3)
                    effective_cone, sampled_distance = scatter.call_args.args
                    self.assertAlmostEqual(effective_cone * sampled_distance, combat.TARGET_SIZE / cap)
                    self.assertEqual(sampled_distance, distance if distance else 1)
                    self.assertEqual(struck[target][2], 3)
                    self.assertEqual(flight.call_args.kwargs['past'], distance)
                    self.assertEqual(flight.call_args.args[4], weapon.max_range)

    def test_capped_scatter_keeps_misses_range_and_cover_effective(self):
        weapon = self.weapon(cone=.001)._replace(hit_cap=.95)
        target, _, struck, _, _ = self.resolve(weapon, 1, offset=.151)
        self.assertNotIn(target, struck)
        target, _, struck, _, _ = self.resolve(weapon, 101)
        self.assertNotIn(target, struck)
        cover = Mock(cell=2, sp_now=lambda: 100)
        target, _, struck, _, _ = self.resolve(weapon, 5, offset=.12, covers=(cover,))
        self.assertNotIn(target, struck)
        self.assertEqual(struck[cover][2], 1)

    def test_default_private_and_npc_scatter_remain_unchanged(self):
        original = self.weapon(cone=.0001)
        self.assertEqual(original.hit_cap, 1)
        for distance in (0, 1, 5, 100):
            _, _, _, scatter, _ = self.resolve(original, distance)
            scatter.assert_called_once_with(original.cone, distance)
            self.assertEqual(combat.hit_probability(original.cone, distance), 1)
        for combat_v2 in (False, True):
            ch = self.character(level=17, spec=5)
            ch.bonus_specs[5] = 1
            fighter = NS(sess=NS(ground=NS(rules=Rules(combat_v2=combat_v2))), character=lambda: ch)
            result = TrainingFighter.prepare_weapon(fighter, original, {}, dict(type_id=25803, cur_mode=2))
            self.assertEqual(result, original)

    def test_local_bot_scores_each_mode_with_its_own_snapshot_without_changing_the_held_mode(self):
        ch = self.character()
        gun = dict(type_id=25201, ammo_type=6107, ammo_count=100, cur_mode=2)
        original = dict(gun)
        seen = []

        def prepare(weapon, ammo, row, mode):
            seen.append((dict(row), mode))
            return battle_balance.weapon(weapon, ch, row, ammo)

        enemy = NS(character=lambda: ch, combat=NS(ap=100, prepare_weapon=prepare))
        with patch.object(combat.action_animation, 'duration_ms', return_value=100):
            bot.modes(NS(enemy=enemy), gun, 5)
        self.assertEqual({mode for _, mode in seen}, {0, 1, 2})
        self.assertTrue(all(row['cur_mode'] == mode for row, mode in seen))
        self.assertEqual(gun, original)

    def test_invalid_caps_are_refused_even_when_the_original_object_is_returned(self):
        original = self.weapon()
        for invalid in (0, -1, 1.01, math.inf, math.nan, True, False, None, '0.95'):
            bad = original._replace(hit_cap=invalid)
            with self.subTest(cap=invalid):
                with self.assertRaises(ValueError):
                    combat.checked_weapon(original, bad)
                with self.assertRaises(ValueError):
                    combat.checked_weapon(bad, bad)
        for valid in (.01, .8075, .95, 1):
            candidate = original._replace(hit_cap=valid)
            self.assertEqual(combat.checked_weapon(original, candidate), candidate)


if __name__ == '__main__':
    run_cases(SingleShotAccuracy)
