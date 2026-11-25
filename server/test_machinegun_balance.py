"""Analytic ordinary MG/SMG parity, catalogue bounds and single ammo scaling."""
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
        self.target = NS(is_player=True, level=17, character=lambda: self.ch, armor=lambda: 148)

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

    def scores(self, type_id):
        si = items.params_of(type_id)
        ammo_id = next(t for t in si['comp_array'] if items.catalogue()[t][1].endswith('_EK_G'))
        ammo = items.params_of(ammo_id)
        scores = []
        for mode, shots in enumerate(si['fire_mods']):
            if not shots:
                continue
            weapon = self.weapon(type_id, mode, ammo)
            distance = max(weapon.opt_lo, min(7, weapon.opt_hi))
            hit = combat.hit_probability(weapon.cone, distance, weapon.hit_cap)
            crit = balance.critical_chance(self.shooter, self.target, weapon.crit - 20, True, ordinary=True) / 100
            low = (weapon.dmax - weapon.dmin) // 2 + weapon.dmin
            slow = (weapon.sdmax - weapon.sdmin) // 2 + weapon.sdmin
            def mean(critical):
                total = 0
                for hp in range(low, weapon.dmax + 1):
                    for sp in range(slow, weapon.sdmax + 1):
                        h, stamina = balance.split(self.shooter, self.target, hp, weapon.piercing,
                                                  critical, 0, sp, ordinary=True)
                        total += combat.ammunition_damage(weapon, h, stamina, 0)[0]
                return total / ((weapon.dmax - low + 1) * (weapon.sdmax - slow + 1))
            damage = hit * ((1 - crit) * mean(False) + crit * mean(True)) * shots
            aim = si['fire_times'][mode] / 1000
            seconds = aim + action_animation.duration_ms(self.seat, si, shots, aimed_for=aim) / 1000
            reload = si['reload_time'] / 1000 * shots / si['clip_size']
            scores.append((damage / (seconds + reload),
                           damage / max(seconds + reload, si['fire_costs'][mode] / (p.AP_REGEN / .6))))
        return tuple(max(score[index] for score in scores) for index in (0, 1))

    def test_released_base_machineguns_keep_up_with_smg_without_excessive_sustained_damage(self):
        # Equal training; one already engaged unshielded target, EK G, no cover,
        # male model and each mode's optimal distance capped at seven hexes.
        for smg, machineguns in ((25540, (24989, 25006, 25022)), (26177, (24990, 25007, 25023))):
            baseline = self.scores(smg)
            for machinegun in machineguns:
                score = self.scores(machinegun)
                for current, previous in zip(score, baseline):
                    self.assertGreaterEqual(current, previous, machinegun)
                    self.assertLess(current, previous * 1.4, machinegun)

    def test_available_mg_modifications_stay_below_reviewed_smg_class_ceiling(self):
        pools = {}
        for type_id in balance.equipment_changes():
            si = items.params_of(type_id)
            if (items.root_of(type_id) != items.FIRE_ARM
                    or si['weapon_type'] not in (items.SMG, items.MACHINEGUN)
                    or items.premium(type_id) or items.acquisition_blocked(type_id)):
                continue
            pools.setdefault((si['weapon_type'], bool(si['g_cost'])), []).append(self.scores(type_id))
        self.assertGreaterEqual(sum(len(pools[items.MACHINEGUN, gold]) for gold in (False, True)), 30)
        for gold in (False, True):
            ceilings = [max(score[index] for score in pools[items.SMG, gold]) for index in (0, 1)]
            for score in pools[items.MACHINEGUN, gold]:
                for value, ceiling in zip(score, ceilings):
                    self.assertLess(value, ceiling * 1.4)

    def test_uniform_damage_correction_covers_all_catalogued_machinegun_variants(self):
        count = 0
        for type_id in balance.equipment_changes():
            si = items.params_of(type_id)
            if items.root_of(type_id) != items.FIRE_ARM or si['weapon_type'] != items.MACHINEGUN:
                continue
            # Disable the one shared policy to recover the exact same variant,
            # including its own blueprint and range. No hard-coded copies.
            with patch.object(items, 'MACHINEGUN_DAMAGE_PERCENT', 100):
                previous = items.params_of(type_id)
            for field in ('h_damage_min', 'h_damage_max'):
                self.assertEqual(si[field], [(value * 105 + 50) // 100 for value in previous[field]])
            self.assertEqual(si['fire_mods'], previous['fire_mods'])
            self.assertEqual(si['fire_costs'], previous['fire_costs'])
            count += 1
        self.assertGreaterEqual(count, 70)

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
