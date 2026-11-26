"""Analytic MG gain limits, original damage bounds and single ammo scaling."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import action_animation
import battle_balance as balance
import combat
import items
import progression as p
from testkit import run_cases


class MachinegunBalance(unittest.TestCase):
    def setUp(self):
        self.ch = p.Character()
        self.ch.set_skill(p.SHOOTING, 17)
        for spec in (6, 7):
            self.ch.set_spec(spec, 3)
        self.seat = NS(inv=NS(look=0), active={'sex': 0})
        self.shooter = NS(is_player=True, level=17, character=lambda: self.ch)
        self.target = NS(is_player=True, level=17, character=lambda: self.ch, armor=lambda: 148,
                         crit_evade_ranged=lambda: p.crit_chance(self.ch, items.MACHINEGUN)[1])

    def weapon(self, type_id, mode, ammo):
        si = items.params_of(type_id)
        kind = si['weapon_type']
        spec = combat.SPEC_OF_WEAPON[kind]
        cone = combat.cone_of(combat.spread_factor(self.ch.skill_level(p.SHOOTING), self.ch.spec_level(spec)),
                              si['target_size'][mode], ammo.get('acc_mod', 1), si['max_range'][mode])
        original = combat.Weapon(si['fire_mods'][mode], si['h_damage_min'][mode], si['h_damage_max'][mode],
            si['opt_range'][mode], si['end_opt_range'][mode], si['max_range'][mode],
            ammo.get('piercing', 1), cone, p.crit_chance(self.ch, kind)[0], p.SHOOTING, spec,
            sdmin=si.get('st_damage_min', [0]*3)[mode], sdmax=si.get('st_damage_max', [0]*3)[mode])
        return balance.weapon(original, self.ch, dict(type_id=type_id, cur_mode=mode), ammo)

    def scores(self, type_id, distance=None, stamina=0):
        si = items.params_of(type_id)
        ammo_id = next(t for t in si['comp_array'] if items.catalogue()[t][1].endswith('_EK_G'))
        ammo = items.params_of(ammo_id)
        scores = []
        for mode, shots in enumerate(si['fire_mods']):
            if not shots:
                continue
            weapon = self.weapon(type_id, mode, ammo)
            sample = max(weapon.opt_lo, min(7, weapon.opt_hi)) if distance is None else distance
            optimal = weapon.opt_lo <= sample <= weapon.opt_hi
            hit = combat.hit_probability(weapon.cone, sample, weapon.hit_cap) if sample <= weapon.max_range else 0
            crit = balance.ranged_critical_chance(self.shooter, self.target, weapon, optimal, ordinary=True) / 100
            low = (weapon.dmax - weapon.dmin) // 2 + weapon.dmin if optimal else weapon.dmin
            slow = (weapon.sdmax - weapon.sdmin) // 2 + weapon.sdmin if optimal else weapon.sdmin
            def mean(critical):
                total = 0
                for hp in range(low, weapon.dmax + 1):
                    for sp in range(slow, weapon.sdmax + 1):
                        h, spent = balance.split(self.shooter, self.target, hp, weapon.piercing,
                                                  critical, stamina, sp, ordinary=True)
                        total += combat.ammunition_damage(weapon, h, spent, stamina)[0]
                return total / ((weapon.dmax - low + 1) * (weapon.sdmax - slow + 1))
            damage = hit * ((1 - crit) * mean(False) + crit * mean(True)) * shots
            aim = si['fire_times'][mode] / 1000
            seconds = aim + action_animation.duration_ms(self.seat, si, shots, aimed_for=aim, mode=mode) / 1000
            reload = si['reload_time'] / 1000 * shots / si['clip_size']
            scores.append((damage / (seconds + reload),
                           damage / max(seconds + reload, si['fire_costs'][mode] / (p.AP_REGEN / .6))))
        return tuple(max(score[index] for score in scores) for index in (0, 1))

    def test_reviewed_dps_ladder_uses_native_animation_recovery_and_reload(self):
        # A quarter of native firing frames, selected mode and amortized reload.
        # Each mode uses its optimal band; fixed distances are checked below.
        for variants, targets in (((24989, 25006, 25022), (241.7, 241.8, 320.7)),
                                  ((24990, 25007, 7051, 25023, 7052),
                                   (288.6, 290.1, 312.6, 387.2, 409.5))):
            scores = [self.scores(type_id)[0] for type_id in variants]
            self.assertEqual(scores, sorted(scores))
            for type_id, score, target in zip(variants, scores, targets):
                with self.subTest(type_id=type_id):
                    self.assertAlmostEqual(score, target, delta=.5)
        self.assertAlmostEqual(self.scores(7052, distance=7)[0], 409.5, delta=.5)

    def test_bizon_comparison_preserves_distance_roles_instead_of_forcing_a_class_winner(self):
        for bizon, rpd, aug in ((25540, 24989, 25006), (26177, 24990, 25007)):
            with self.subTest(bizon=bizon):
                self.assertGreater(self.scores(bizon, distance=4)[0], self.scores(aug, distance=4)[0])
                self.assertGreater(self.scores(rpd, distance=12)[0], self.scores(bizon, distance=12)[0])
                self.assertGreater(self.scores(aug, distance=18)[0], self.scores(rpd, distance=18)[0])
                self.assertEqual(self.scores(bizon, distance=18)[0], 0)

    def test_pkm16_reference_uses_native_animation_and_full_reload_cycle(self):
        # Native damage/accuracy are unchanged. Volley animation changes mode
        # efficiency; compare the complete new cycle including reload.
        for pkm, reference in ((7051, 24990),):
            with self.subTest(pkm=pkm):
                ratio = self.scores(pkm)[0] / self.scores(reference)[0]
                self.assertAlmostEqual(ratio, 1.083, delta=.002)

    def test_afro_and_gold_m249_beat_matching_rpd_on_medium_and_long_ranges(self):
        # Use the same fixed distance for all modes, with real non-optimal
        # critical chance, damage and range.
        for m249, rpd in ((25022, 24989), (25023, 24990)):
            for distance in (7, 12, 18, 24):
                with self.subTest(m249=m249, distance=distance):
                    self.assertGreater(self.scores(m249, distance)[0], self.scores(rpd, distance)[0])

    def test_m249_beats_matching_rpd_at_close_range_with_and_without_blueprints(self):
        for m249, rpd in ((25022, 24989), (25023, 24990),
                          (25025, 24992), (25026, 24993),
                          (40086, 24995), (40088, 24996),
                          (25025, 25001), (25026, 25002)):
            for distance in (1, 2, 3, 4):
                with self.subTest(m249=m249, rpd=rpd, distance=distance):
                    self.assertGreater(self.scores(m249, distance)[0], self.scores(rpd, distance)[0])

    def test_gold_m249_damage_blueprint_exceeds_pkm17_by_at_most_five_percent(self):
        # Keep both the agreed optimal-band reference and actual close fights.
        for stamina in (0, 10000):
            for distance in (None, *range(1, 34)):
                with self.subTest(distance=distance, stamina=stamina):
                    ratio = self.scores(25026, distance, stamina)[0] / self.scores(7052, distance, stamina)[0]
                    self.assertGreater(ratio, 1)
                    self.assertLessEqual(ratio, 1.05)
        self.assertGreater(self.scores(25026, 4)[0], self.scores(40088, 4)[0])

    def test_dps_respects_the_live_targets_anticrit_when_stamina_absorbs_damage(self):
        with patch.object(self.target, 'crit_evade_ranged', return_value=0):
            unopposed = self.scores(25026, 4, stamina=10000)[0]
            empty = self.scores(25026, 4)[0]
        with patch.object(self.target, 'crit_evade_ranged', return_value=100):
            defended = self.scores(25026, 4, stamina=10000)[0]
            self.assertAlmostEqual(self.scores(25026, 4)[0], empty)
        self.assertGreater(unopposed, defended)
        self.assertGreater(empty, unopposed)
        self.assertAlmostEqual(self.scores(25026, 4, stamina=10000)[0], 386.5, delta=.2)
        self.assertAlmostEqual(self.scores(7052, 4, stamina=10000)[0], 372.7, delta=.2)

    def test_accuracy_ceilings_cover_all_rpd_blueprints_without_changing_other_weapons(self):
        expected = {type_id for type_id, (_root, name) in items.catalogue().items()
                    if name.startswith('machine_gun_1_lvl_16')
                    and '_mob' not in name and not items.premium(type_id)}
        caps = balance.weapon_hit_caps()
        self.assertEqual(set(caps), expected)
        for type_id in expected:
            self.assertEqual(caps[type_id], .83)
        for type_id, cap in ((24990, .83), (7052, .95), (25026, .95), (26177, .95)):
            with self.subTest(type_id=type_id):
                self.assertEqual(self.weapon(type_id, 2, {}).hit_cap, cap)
        # An older weapon still receives the existing over-level penalty.
        self.ch.set_skill(p.SHOOTING, 15)
        self.assertAlmostEqual(self.weapon(24990, 2, {}).hit_cap, .83 * .95)

    def test_all_m249_afro_and_gold_blueprints_receive_the_same_mode_corrections(self):
        from training.balance import before_release
        prior_ordinary = {25034: [.924, 1.123, 1.289], 25035: [.924, 1.123, 1.289]}
        count = 0
        for type_id, (_root, name) in items.catalogue().items():
            if (not name.startswith('machine_gun_1_lvl_17') or items.premium(type_id)
                    or items.root_of(type_id) != items.FIRE_ARM):
                continue
            si = items.params_of(type_id)
            if si['weapon_type'] != items.MACHINEGUN:
                continue
            # These range blueprints deliberately retain an older private
            # profile; the ordinary game already had a newer spread table.
            original = prior_ordinary.get(type_id, before_release(type_id, dict(si))['target_size'])
            expected = [round(x*f, 5) for x, f in zip(original, (.7, .69, .935))]
            if type_id in (25025, 25026, 40107, 40109):
                expected = {25025: [.7573, .89112, 1.38959],
                            25026: [.7573, .89112, 1.38959],
                            40107: [0.7573, 0.89112, 1.38959],
                            40109: [0.7573, 0.89112, 1.38959]}[type_id]
            self.assertEqual(si['target_size'], expected)
            count += 1
        self.assertEqual(count, 24)

    def test_m249_and_pkm_keep_the_original_aim_times_and_ap_costs(self):
        for type_id, times, costs in ((25022, [800, 800, 1000], [25, 32, 39]),
                                      (25023, [800, 800, 1000], [25, 32, 39]),
                                      (7051, [800, 800, 1200], [25, 30, 40]),
                                      (7052, [800, 800, 1000], [25, 32, 39])):
            with self.subTest(type_id=type_id):
                si = items.params_of(type_id)
                self.assertEqual(si['fire_times'], times)
                self.assertEqual(si['fire_costs'], costs)

    def test_reviewed_machinegun_variants_keep_their_original_table_damage(self):
        count = 0
        for type_id, record in balance.equipment_changes().items():
            si = items.params_of(type_id)
            if items.root_of(type_id) != items.FIRE_ARM or si['weapon_type'] != items.MACHINEGUN:
                continue
            for field in ('h_damage_min', 'h_damage_max'):
                if field in record:
                    self.assertEqual(si[field], record[field], (type_id, field))
                    count += 1
        self.assertGreaterEqual(count, 100)

    def test_only_pkm17_receives_the_reviewed_small_damage_reduction(self):
        fixtures = {7051: ([24, 24, 18], [72, 60, 90]),
                    7052: ([28, 31, 36], [78, 81, 99]),
                    7082: ([36, 30, 30], [132, 126, 138]),
                    7053: ([46, 42, 54], [118, 114, 102]),
                    7054: ([78, 66, 60], [138, 114, 108])}
        for type_id, (minimum, maximum) in fixtures.items():
            with self.subTest(type_id=type_id):
                si = items.params_of(type_id)
                self.assertEqual(si['h_damage_min'], minimum)
                self.assertEqual(si['h_damage_max'], maximum)

    def test_pkm17_damage_is_lower_in_every_mode_with_no_large_nominal_gap(self):
        fn = items.params_of(25026)
        pkm = items.params_of(7052)
        for field in ('h_damage_min', 'h_damage_max'):
            for higher, lower in zip(fn[field], pkm[field]):
                self.assertGreater(higher, lower)
                self.assertLessEqual(higher / lower, 1.05)
        # Cone size is proportional to maximum range. Equal close-range
        # accuracy avoids multiplying a damage reduction by another hit penalty.
        for mode in range(3):
            fn_weapon = self.weapon(25026, mode, {})
            pkm_weapon = self.weapon(7052, mode, {})
            self.assertAlmostEqual(fn_weapon.cone, pkm_weapon.cone, delta=.00001)
            self.assertEqual(fn_weapon.hit_cap, pkm_weapon.hit_cap)
        self.assertEqual(pkm['max_range'], [33, 25, 22])
        self.assertEqual(pkm['end_opt_range'], [24, 19, 15])
        self.assertEqual(pkm['fire_mods'], fn['fire_mods'])
        self.assertEqual(pkm['fire_times'], fn['fire_times'])
        self.assertEqual(pkm['fire_costs'], fn['fire_costs'])

    def test_pkm17_private_range_keeps_its_frozen_damage(self):
        from training.balance import before_release
        ordinary = items.params_of(7052)
        private = before_release(7052, dict(ordinary))
        self.assertEqual(private['h_damage_min'], [29, 32, 37])
        self.assertEqual(private['h_damage_max'], [81, 84, 103])
        self.assertEqual(ordinary['h_damage_min'], [28, 31, 36])

    def test_gold_ammo_changes_final_damage_without_changing_bounds_or_crit(self):
        for type_id in (25566, 25943, 25201, 25803, 24990, 26177):
            si = items.params_of(type_id)
            for mode, shots in enumerate(si['fire_mods']):
                if not shots:
                    continue
                original = self.weapon(type_id, mode, dict(dam_mod=1, st_mod=1))
                explosive = self.weapon(type_id, mode, dict(cost=0, g_cost=2, dam_mod=1.3, st_mod=1.3))
                for field in original._fields:
                    if field not in ('hp_multiplier', 'sp_multiplier'):
                        self.assertEqual(getattr(explosive, field), getattr(original, field), field)
                for critical in (False, True):
                    for stamina in (0, 1000):
                        hp, sp = balance.split(self.shooter, self.target, original.dmax,
                            original.piercing, critical, stamina, original.sdmax, ordinary=True)
                        self.assertEqual(combat.ammunition_damage(explosive, hp, sp, stamina),
                                         (int(hp*13//10), min(stamina, int(sp*13//10))))
                self.assertEqual(combat.ammunition_damage(explosive, 0, 10, 5), (0, 5))

    def test_preparation_strips_gold_modifiers_once_and_keeps_ordinary_ammo(self):
        weapon = combat.Weapon(3, 100, 200, 1, 5, 20, 1, .1, 20, p.SHOOTING, 7)
        ammo = dict(cost=0, g_cost=2, dam_mod=1.3, st_mod=.8, acc_mod=.8, range_mod=1.1)
        prepared, stripped = combat.prepare_ammunition(weapon, ammo)
        self.assertEqual(combat.prepare_ammunition(prepared, stripped), (prepared, stripped))
        self.assertEqual((prepared.hp_multiplier, prepared.sp_multiplier), (1.3, .8))
        self.assertEqual((ammo['dam_mod'], ammo['st_mod']), (1.3, .8))
        self.assertEqual((stripped['acc_mod'], stripped['range_mod']), (.8, 1.1))
        ordinary = dict(ammo, cost=10, g_cost=0)
        self.assertEqual(combat.prepare_ammunition(weapon, ordinary), (weapon, ordinary))

    def test_range_can_still_disable_ammo_bonuses_explicitly(self):
        from training.arena import TrainingFighter
        from training.rules import Rules
        weapon = combat.Weapon(1, 100, 200, 1, 5, 20, 1, .1, 20, p.SHOOTING, 7)
        ammo = dict(cost=0, g_cost=2, dam_mod=1.3, st_mod=1.3)
        for enabled in (False, True):
            actor = NS(sess=NS(ground=NS(rules=Rules(ammo_modifiers=enabled, combat_v2=False))))
            result = TrainingFighter.prepare_weapon(actor, weapon, ammo)
            self.assertEqual((result.dmin, result.dmax, result.crit), (100, 200, 20))
            self.assertEqual(result.hp_multiplier, 1.3 if enabled else 1)

    def test_post_ammo_fields_are_validated_before_accepting_an_attack(self):
        weapon = combat.Weapon(1, 100, 100, 1, 5, 20, 1, .1, 20, p.SHOOTING, 7)
        for field in ('hp_multiplier', 'sp_multiplier'):
            for value in (-1, float('inf'), float('nan'), True, None, '1.3'):
                with self.subTest(field=field, value=value):
                    bad = weapon._replace(**{field: value})
                    with self.assertRaises(ValueError):
                        combat.checked_weapon(weapon, bad)
                    with self.assertRaises(ValueError):
                        combat.checked_weapon(bad, bad)


if __name__ == '__main__':
    run_cases(MachinegunBalance)
