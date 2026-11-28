"""Per-projectile burst bounds, level progression and blueprint inheritance."""
import copy
import re
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import battle_balance
import combat
import craft
import inventory
import items
import mobs
import progression
from testkit import run_cases
from training.balance import before_release


class WeaponModeBalance(unittest.TestCase):
    def test_longer_third_burst_never_has_less_total_damage_than_second(self):
        checked = 0
        for source, (root, name) in items.catalogue().items():
            if (root != items.FIRE_ARM or items.out_of_game(source)
                    or items.acquisition_blocked(source)):
                continue
            params = items.params_of(source)
            shots = params['fire_mods']
            # A third aimed single shot is a different role, not a longer burst.
            if len(shots) < 3 or not 0 < shots[1] < shots[2]:
                continue
            for field in ('h_damage_min', 'h_damage_max'):
                with self.subTest(source=source, field=field):
                    self.assertGreaterEqual(params[field][2] * shots[2],
                                            params[field][1] * shots[1])
            checked += 1
        self.assertGreater(checked, 100)

    def test_player_weapon_improvements_do_not_increase_existing_npc_pressure(self):
        # Frozen current-main outputs, covering ordinary mobs, a capped boss,
        # a senior boss and the separate site pipeline. No damage is restored
        # for the erroneous G3/MP5 bursts corrected by this release.
        expected = {
            (False, 1027): [(31, 44)],
            (False, 1029): [(25, 40)],
            (False, 374): [(6, 8)],
            (False, 5641): [(25, 40)],
            (True, 1027): [(35, 49)],
            (True, 1029): [(28, 45)],
            (True, 374): [(59, 88)],
            (True, 5641): [(28, 45)],
        }
        player_before = {source: copy.deepcopy(items.params_of(source))
                         for source in (25287, 25288, 25319, 25320)}
        for (site, source), bounds in expected.items():
            stats = mobs.MobStats(source, balanced=not site)
            if site:
                battle_balance.configure_mob(stats, site=True)
            with self.subTest(site=site, source=source):
                self.assertEqual([(row['dmin'], row['dmax'])
                                  for row in stats.balanced_modes], bounds)
                if stats.weapon_type_id in (25287, 25319):
                    self.assertEqual([row['shots'] for row in stats.balanced_modes], [3])
                    self.assertIsNone(battle_balance.mob_mode(stats, stats.range + 1))
        self.assertEqual(set(battle_balance.mob_weapon_damage_overrides()), {25217, 25287, 25319})
        for source, params in player_before.items():
            self.assertEqual(items.params_of(source), params)
        self.assertEqual(items.params_of(25287)['h_damage_max'], [170, 80, 52])
        self.assertEqual(items.params_of(25319)['h_damage_max'], [218, 100, 64])

    def test_npc_bullets_have_independent_scatter_and_can_miss_at_close_range(self):
        stats = mobs.MobStats(1029)
        weapon, cost, delay = battle_balance.mob_mode(stats, 1)
        self.assertEqual((weapon.num_shots, cost, delay), (3, 24, .7))
        self.assertEqual(weapon.hit_cap, .95)
        self.assertEqual(combat.hit_probability(0, 1, weapon.hit_cap), .95)
        room = combat.RoomCombat.__new__(combat.RoomCombat)
        room.room = NS(loc=NS(width=128, height=2, obstacles=set()))
        room.bodies = lambda *_args: {}
        room.ranged_critical = lambda *_args: False
        room.bullet_damage = lambda *_args: (10, 0)
        shooter = NS(cell=0, is_player=False, stats=stats)
        target = Mock(cell=1, is_player=True, sp_now=lambda: 100)
        with patch.object(combat, 'bullet_offset', side_effect=(0, .151, 0)) as scatter, \
                patch.object(combat, 'shot_wall', return_value=None), \
                patch.object(combat, 'bodies_between', return_value=[]), \
                patch.object(combat, 'flight', return_value=([], ('faMiss', {}))), \
                patch.object(combat.holdings, 'defender_friendly', return_value=False):
            pairs, struck = room.resolve(shooter, target, target.cell, weapon, 3)
        self.assertEqual(scatter.call_count, 3)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(struck[target][:3], [20, 0, 2])

    def test_reviewed_second_modes_are_between_single_and_long_burst(self):
        for source in (25166, 25167, 25217, 25218, 25265, 25266,
                       25287, 25288, 25319, 25320):
            params = items.params_of(source)
            for field in ('h_damage_min', 'h_damage_max'):
                first, second, third = [v*n for v,n in zip(params[field], params['fire_mods'])]
                with self.subTest(source=source, field=field):
                    self.assertLess(first, second)
                    self.assertLess(second, third)
                    self.assertLessEqual(abs(second - (first + third)/2), 3)

    def test_galil_and_g3_keep_reviewed_per_projectile_bounds(self):
        for source, minimum, maximum in ((25201, 26, 44), (25202, 31, 53),
                                         (25217, 32, 52), (25218, 38, 62)):
            with self.subTest(source=source):
                params = items.params_of(source)
                self.assertEqual(params['fire_mods'], [1, 3, 6])
                self.assertEqual((params['h_damage_min'][2], params['h_damage_max'][2]),
                                 (minimum, maximum))
                self.assertLess(params['h_damage_max'][2], params['h_damage_max'][0])
                self.assertGreater(maximum * 6, params['h_damage_max'][0])

    def test_released_bursts_never_outdamage_the_strongest_single_projectile(self):
        checked = 0
        for source, (root, name) in items.catalogue().items():
            if (root != items.FIRE_ARM or items.out_of_game(source)
                    or items.acquisition_blocked(source)):
                continue
            params = items.params_of(source)
            if params['weapon_type'] == items.SHOTGUN:
                continue  # Pellets are simultaneous; their budget is not an automatic burst.
            shots = params['fire_mods']
            singles = [mode for mode, count in enumerate(shots) if count == 1]
            if not singles:
                continue  # Machine guns have no aimed single-shot reference.
            lo, hi = params['h_damage_min'], params['h_damage_max']
            ceiling = max(hi[mode] for mode in singles)
            mean = max(lo[mode] + hi[mode] for mode in singles)
            for mode, count in enumerate(shots):
                if count <= 1:
                    continue
                with self.subTest(source=source, mode=mode):
                    self.assertLessEqual(hi[mode], ceiling)
                    self.assertLessEqual(lo[mode] + hi[mode], mean)
                checked += 1
        self.assertGreater(checked, 600)

    def test_assault_level_ladder_has_no_backwards_step_in_each_mode(self):
        # Alternatives retain different roles/ranges. Compare the best nominal
        # projectile budget of each level at the same tier and blueprint.
        by_name = craft._by_name()
        for gold in (False, True):
            for effect in (None, 'damage', 'damage_clipsize', 'precision_shotrange'):
                levels = {}
                for source, (root, name) in items.catalogue().items():
                    if root != items.FIRE_ARM or not re.fullmatch(r'assault_rifle_\d+_lvl_\d+' + ('_gold' if gold else ''), name):
                        continue
                    level = inventory.item_level(source)
                    if not 12 <= level <= 17:
                        continue
                    selected = source
                    if effect:
                        stem = name.removesuffix('_gold')
                        selected = by_name.get(stem + '_mod_' + effect + ('_gold' if gold else ''))
                        if selected is None:
                            continue
                    params = items.params_of(selected)
                    budget = [lo + hi for lo, hi in zip(params['h_damage_min'], params['h_damage_max'])]
                    levels[level] = [max(a, b) for a, b in zip(levels.get(level, [0]*3), budget)]
                self.assertEqual(set(levels), set(range(12, 18)))
                for mode in range(3):
                    values = [levels[level][mode] for level in sorted(levels)]
                    with self.subTest(gold=gold, effect=effect, mode=mode):
                        self.assertEqual(values, sorted(values))

    def test_affected_blueprints_keep_their_declared_damage_bonus(self):
        bases = {25166, 25167, 25201, 25202, 25217, 25218,
                 25265, 25266, 25469, 25470, 25636, 25637,
                 25287, 25288, 25319, 25320,
                 24989, 24990, 25006, 25007, 25341, 25342, 25357, 25358,
                 25373, 25374, 25389, 25390, 25421, 25422, 25437, 25438,
                 25453, 25454, 25514, 25515, 25540, 26177}
        checked = 0
        for source, (root, name) in items.catalogue().items():
            mod = craft.mod_of(source) if root == items.FIRE_ARM else None
            if not mod or mod[0] not in bases:
                continue
            base, effect = mod
            expected = copy.deepcopy(items.params_of(base))
            craft._apply(expected, effect)
            actual = items.params_of(source)
            for field in ('h_damage_min', 'h_damage_max'):
                with self.subTest(source=source, field=field):
                    self.assertEqual(actual[field], expected[field])
            checked += 1
        self.assertGreater(checked, 100)

    def test_frozen_range_profiles_are_preserved(self):
        frozen = battle_balance.data()['equipment']
        for source in (25201, 25202, 25217, 25218, 25265, 25266,
                       25287, 25288, 25319, 25320):
            ordinary = items.params_of(source)
            fixed = frozen.get(str(source), {})
            original = before_release(source, copy.deepcopy(ordinary))
            for field in ('h_damage_min', 'h_damage_max'):
                if field in fixed:
                    self.assertNotEqual(ordinary[field], fixed[field])
                self.assertEqual(original[field], items.wiki()[source][field])

    def test_real_resolver_matches_card_bounds_per_projectile_without_double_counting(self):
        character = progression.Character()
        character.skill[progression.SHOOTING][0] = 20
        shooter = NS(cell=0, level=20, is_player=True, character=lambda: character)
        target = Mock(cell=1, level=20, is_player=True, character=lambda: character,
                      armor=lambda: 0, sp_now=lambda: 0,
                      vitals=lambda: {'hcur': 50, 'hmax': 100})
        room = combat.RoomCombat.__new__(combat.RoomCombat)
        room.room = NS(loc=NS(width=128, height=2, obstacles=set()))
        room.bodies = lambda *_args: {}
        room.ranged_critical = lambda *_args: False
        checked = 0
        with patch.object(combat, 'bullet_offset', return_value=0), \
                patch.object(combat, 'shot_wall', return_value=None), \
                patch.object(combat, 'bodies_between', return_value=[]), \
                patch.object(combat, 'flight', return_value=([], ('faMiss', {}))), \
                patch.object(combat.holdings, 'defender_friendly', return_value=False):
            for source, (root, name) in items.catalogue().items():
                if (root != items.FIRE_ARM or items.out_of_game(source)
                        or items.acquisition_blocked(source)):
                    continue
                params = items.params_of(source)
                for mode, shots in enumerate(params['fire_mods']):
                    if not shots:
                        continue
                    weapon = combat.Weapon(shots, params['h_damage_min'][mode],
                        params['h_damage_max'][mode], params['opt_range'][mode],
                        params['end_opt_range'][mode], params['max_range'][mode],
                        1, .001, 0, progression.SHOOTING,
                        combat.SPEC_OF_WEAPON[params['weapon_type']])
                    prepared = battle_balance.weapon(weapon, character,
                        dict(type_id=source, cur_mode=mode), {})
                    self.assertEqual((prepared.dmin, prepared.dmax),
                        (max(1, weapon.dmin), max(1, weapon.dmax)), (source, mode))
                    low = prepared.dmin
                    if prepared.opt_lo <= 1 <= prepared.opt_hi:
                        low += (prepared.dmax - low) // 2
                    for upper, expected in ((False, low), (True, prepared.dmax)):
                        choose = (lambda lo, hi: hi) if upper else (lambda lo, hi: lo)
                        with patch.object(combat.RNG, 'randint', side_effect=choose):
                            pairs, struck = room.resolve(shooter, target, target.cell, prepared, shots)
                        with self.subTest(source=source, mode=mode, upper=upper):
                            self.assertEqual(struck[target][:3], [expected * shots, 0, shots])
                            self.assertEqual(len(pairs), shots)
                            self.assertEqual([fate[1] for _, fates in pairs for fate in fates],
                                             [expected] * shots)
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_fire_modes_costs_and_timing_are_unchanged(self):
        fixtures = ((25166, [16, 21, 26], [800, 700, 800]),
                    (25201, [18, 18, 24], [800, 700, 800]),
                    (25217, [19, 21, 24], [800, 700, 800]),
                    (25469, [14, 20, 0], [450, 450, 0]),
                    (25636, [12, 20, 0], [400, 500, 0]),
                    (25287, [22, 23, 30], [800, 700, 800]),
                    (25319, [23, 24, 31], [800, 700, 800]))
        for source, costs, times in fixtures:
            for selected in (source, craft._by_name()[items.catalogue()[source][1] + '_gold']):
                with self.subTest(source=selected):
                    params = items.params_of(selected)
                    self.assertEqual(params['fire_costs'], costs)
                    self.assertEqual(params['fire_times'], times)


if __name__ == '__main__':
    run_cases(WeaponModeBalance)
