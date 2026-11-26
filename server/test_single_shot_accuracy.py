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
import mobs
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

    def test_all_classes_and_modes_keep_identity_with_small_rifle_and_native_single_bonuses(self):
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
                    if kind == items.RIFLE:
                        bonus *= .95
                    self.assertAlmostEqual(result.cone, original.cone * bonus)
                    self.assertEqual(result.hit_cap, .95)
                    self.assertEqual(result.base_crit, original.crit)
                    for field in original._fields:
                        if field not in ('cone', 'hit_cap', 'base_crit'):
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

    def test_rifle_followup_is_small_smooth_and_keeps_every_probability_cap(self):
        params = dict(weapon_type=items.RIFLE, fire_mods=[1, 3, 6])
        for mode, shots in enumerate(params['fire_mods']):
            for spec in (0, 3, 5):
                ch = self.character(spec=spec)
                for missing in range(4):
                    original = self.weapon(shots=shots,
                        cone=combat.cone_of(combat.spread_factor(13, spec), .7, 1, 100))
                    row = dict(type_id=1, cur_mode=mode)
                    with patch.object(inventory, 'item_level', return_value=13 + missing), \
                            patch.object(items, 'params_of', return_value=params):
                        with patch.object(battle_balance, 'RIFLE_SPREAD', 1):
                            before = battle_balance.weapon(original, ch, row, {})
                        after = battle_balance.weapon(original, ch, row, {})
                    self.assertAlmostEqual(after.cone, before.cone * .95)
                    self.assertEqual(after.hit_cap, before.hit_cap)
                    for fraction in (.25, .5, .9, 1):
                        distance = original.max_range * fraction
                        old = combat.hit_probability(before.cone, distance, before.hit_cap)
                        new = combat.hit_probability(after.cone, distance, after.hit_cap)
                        self.assertGreaterEqual(new, old)
                        self.assertLessEqual(new, after.hit_cap)
                        self.assertLessEqual(new - old, .0475 + 1e-12)
                        self.assertLessEqual(new, old / .95 + 1e-12)

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
                        self.assertAlmostEqual(result.cone, cone * .8 * .95 / ratio)
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
                            own = combat.hit_probability(cone * .8 * .95, distance, .95)
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

    def test_free_aim_before_on_and_behind_body_matches_target_accuracy(self):
        # Fixed quantiles exercise the actual flight geometry, not model battles.
        samples = 400
        for row in (6, 7):
            for distance in (1, 5, 10):
                for cone in (0, .04, .2):
                    for cap in (.95, .8075):
                        with self.subTest(row=row, distance=distance, cone=cone, cap=cap):
                            rc = combat.RoomCombat.__new__(combat.RoomCombat)
                            rc.room = NS(loc=NS(width=64, height=20, obstacles=set()))
                            shooter = NS(cell=row * 64 + 5, is_player=True)
                            body = Mock(cell=shooter.cell + distance, is_player=False, sp_now=lambda: 100)
                            rc.bodies = lambda *_: {body.cell: body}
                            rc.ranged_critical = lambda *_: False
                            rc.bullet_damage = lambda *_: (10, 0)
                            weapon = self.weapon(cone=cone)._replace(max_range=40, hit_cap=cap)
                            counts = []
                            for target, aim in ((body, body.cell), (None, shooter.cell + 1),
                                                (None, body.cell), (None, shooter.cell + 30)):
                                draws = iter((i + .5) / samples - .5 for i in range(samples))
                                def offset(cone, dist):
                                    return next(draws) * cone * dist
                                with patch.object(combat, 'bullet_offset', side_effect=offset) as scatter, \
                                        patch.object(holdings, 'defender_friendly', return_value=False):
                                    counts.append(sum(body in rc.resolve(shooter, target, aim, weapon, 1)[1]
                                                      for _ in range(samples)))
                                self.assertEqual(scatter.call_count, samples)
                            expected = combat.hit_probability(cone, distance, cap)
                            for hits in counts:
                                self.assertLessEqual(hits, math.ceil(samples * cap))
                                self.assertAlmostEqual(hits / samples, expected, delta=.005)
                            for hits in counts[1:]:
                                self.assertLessEqual(abs(counts[0] - hits), 2)

    def test_target_and_free_aim_accuracy_match_in_eight_directions(self):
        samples = 200
        start = 24 * 64 + 20
        for step in (1, -1, 128, -128, 129, 127, -127, -129):
            for cone in (.04, .2):
                for cap in (.95, .8075):
                    with self.subTest(step=step, cone=cone, cap=cap):
                        rc = combat.RoomCombat.__new__(combat.RoomCombat)
                        rc.room = NS(loc=NS(width=64, height=48, obstacles=set()))
                        shooter = NS(cell=start, is_player=True)
                        body = Mock(cell=start + step * 3, is_player=False, sp_now=lambda: 100)
                        rc.bodies = lambda *_: {body.cell: body}
                        rc.ranged_critical = lambda *_: False
                        rc.bullet_damage = lambda *_: (10, 0)
                        weapon = self.weapon(cone=cone)._replace(max_range=50, hit_cap=cap)
                        counts = []
                        for target, aim in ((body, body.cell), (None, start + step),
                                            (None, body.cell), (None, start + step * 9)):
                            draws = iter((i + .5) / samples - .5 for i in range(samples))
                            with patch.object(combat, 'bullet_offset',
                                              side_effect=lambda cone, dist: next(draws) * cone * dist), \
                                    patch.object(holdings, 'defender_friendly', return_value=False):
                                counts.append(sum(body in rc.resolve(shooter, target, aim, weapon, 1)[1]
                                                  for _ in range(samples)))
                        expected = combat.hit_probability(cone, mobs.hex_distance(start, body.cell, 64), cap)
                        for hits in counts:
                            self.assertAlmostEqual(hits / samples, expected, delta=.01)
                        self.assertLessEqual(max(counts) - min(counts), 2)

    def test_capped_free_aim_uses_body_width_and_retains_walls_range_and_penetration(self):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        loc = NS(width=64, height=20, obstacles=set())
        rc.room = NS(loc=loc)
        shooter = NS(cell=389, is_player=True)
        bodies = [Mock(cell=shooter.cell + d, is_player=False, sp_now=lambda: 100) for d in (5, 10, 15)]
        rc.bodies = lambda *_: {body.cell: body for body in bodies}
        rc.ranged_critical = lambda *_: False
        rc.bullet_damage = lambda *_: (10, 0)
        weapon = self.weapon(cone=.1)._replace(max_range=20, hit_cap=.95, through=True)
        aim = shooter.cell + 30
        # At the first body this ray misses the 0.3m body but crosses its hex.
        with patch.object(combat, 'bullet_offset', return_value=1.2):
            self.assertEqual(rc.resolve(shooter, None, aim, weapon, 1)[1], {})
        with patch.object(combat, 'bullet_offset', return_value=0):
            self.assertEqual(set(rc.resolve(shooter, None, aim, weapon, 1)[1]), set(bodies[:2]))
            loc.obstacles.add(shooter.cell + 3)
            self.assertEqual(rc.resolve(shooter, None, aim, weapon, 1)[1], {})
            loc.obstacles.clear()
            self.assertEqual(rc.resolve(shooter, None, aim, weapon._replace(max_range=4), 1)[1], {})
            self.assertEqual(rc.resolve(shooter, None, aim, weapon, 0)[1], {})
            # A hex can overlap the last flight step while its body is out of range.
            diagonal = Mock(cell=12 * 64 + 5, is_player=False, sp_now=lambda: 100)
            rc.bodies = lambda *_: {diagonal.cell: diagonal}
            self.assertEqual(rc.resolve(shooter, None, diagonal.cell,
                                        weapon._replace(max_range=5), 1)[1], {})

    def test_valid_capped_stray_still_carries_health_and_stamina_damage(self):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        rc.room = NS(loc=NS(width=64, height=20, obstacles=set()))
        shooter = NS(cell=6 * 64 + 5, is_player=True)
        mark = Mock(cell=6 * 64 + 8, is_player=False, sp_now=lambda: 100)
        stray = Mock(cell=7 * 64 + 10, is_player=False, sp_now=lambda: 100)
        rc.bodies = lambda *_: {stray.cell: stray}
        rc.ranged_critical = lambda *_: False
        rc.bullet_damage = lambda *_: (15, 9)
        weapon = self.weapon(cone=.4)._replace(hit_cap=.95)
        # A ray outside the intended body crosses the actual body on the next row.
        with patch.object(combat, 'bullet_offset', return_value=.52) as scatter, \
                patch.object(holdings, 'defender_friendly', return_value=False):
            pairs, struck = rc.resolve(shooter, mark, mark.cell, weapon, 1)
        self.assertNotIn(mark, struck)
        self.assertEqual(struck[stray][:3], [15, 9, 1])
        self.assertEqual(pairs, [(None, [(stray, 15, 9, False)])])
        scatter.assert_called_once()

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
