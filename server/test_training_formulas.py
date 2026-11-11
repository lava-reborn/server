"""Deterministic simulator equations, real range actions and ordinary defaults."""
from types import SimpleNamespace as NS
import math
import unittest
from unittest.mock import patch

import battle_medicine
import combat
import inventory
import items
import mobs
import progression
import training_balance
import training_formulas as formulas
import training_ground as training
import training_items
from training_rules import Rules
import test_training_ground as fixtures


class SimulatorEquations(unittest.TestCase):
    def actor(self, level=12, armour=148, player=True, enabled=True):
        rules = Rules(simulator_formulas=enabled)
        return NS(is_player=player, character=lambda: NS(level=level), stats=NS(level=level),
                  armor=lambda: armour, crit_evade_ranged=lambda: 0,
                  sess=NS(ground=NS(rules=rules)) if player else None,
                  training_ground=None if player else NS(rules=rules))

    def test_current_and_old_payloads_remain_opt_in(self):
        profile = Rules(simulator_formulas=True, ammo_modifiers=True)
        self.assertEqual(Rules.parse(profile.as_dict()), profile)
        self.assertEqual(Rules.from_values(profile.values()).values(), profile.values())
        for values in ('1,1,1,1,1,1,1,1,1,0,0,1', '1,1,1,1,1,1,1,1,1,0,1,0,1'):
            self.assertFalse(Rules.from_values(values).simulator_formulas)
        self.assertFalse(Rules.parse({'combat_v2': True}).simulator_formulas)
        for values in ({'simulator_formulas': 'yes'}, {'simulator_formulas': 1},
                       {'simulator_formulas': True, 'combat_v2': False}):
            with self.assertRaises(ValueError):
                Rules.parse(values)

    def test_reference_is_exact_by_level_including_non_monotone_sets(self):
        self.assertEqual([formulas.reference_armour(level) for level in (0, 4, 5, 6, 7, 12, 17, 20, 35)],
                         [13, 44, 44, 55, 55, 148, 624, 1650, 1650])

    def test_armour_ratio_piercing_cap_and_overflow(self):
        shooter, target = self.actor(), self.actor()
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 200, rifle=True), (50, 50))
        self.assertEqual(formulas.split(shooter, target, 100, 2, False, 200, rifle=True), (67, 33))
        self.assertEqual(formulas.split(shooter, target, 100, 0, False, 200, rifle=True), (34, 66))
        target.armor = lambda: 1_000_000
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 200, rifle=True), (10, 90))
        target.armor = lambda: 148
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 20, 10, rifle=True), (90, 20))
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 0, rifle=True), (100, 0))
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 200, melee=True), (0, 100))

    def test_non_rifle_armour_uses_shooter_level_and_weak_armour_leaks(self):
        shooter = self.actor()
        target = self.actor(armour=formulas.reference_armour(11))
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 200), (0, 100))
        target.armor = lambda: formulas.reference_armour(11) / 2
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 200), (50, 50))
        self.assertEqual(formulas.split(shooter, target, 100, 1, False, 20), (80, 20))

    def test_crit_bypasses_armour_but_uses_remaining_stamina_for_bullets(self):
        shooter, target = self.actor(), self.actor()
        self.assertEqual(formulas.split(shooter, target, 100, 1, True, 20, 300), (100, 20))
        self.assertEqual(formulas.split(shooter, target, 100, 1, True, 20, melee=True), (100, 0))

    def test_gap_rule_uses_exact_level_table_and_only_player_against_mob(self):
        shooter = self.actor()
        for gap, expected in ((0, 100), (1, 83), (2, 20), (3, 5), (4, 5), (5, 5)):
            target = self.actor(level=12 + gap, armour=0, player=False)
            self.assertEqual(formulas.split(shooter, target, 100, 1, True, 0)[0], expected)
        self.assertEqual(formulas.split(shooter, self.actor(level=20), 100, 1, True, 0)[0], 100)
        self.assertEqual(formulas.split(self.actor(player=False), self.actor(level=20), 100, 1, True, 0)[0], 100)

    def test_crit_requires_player_optimal_band_and_mob_floor_is_separate(self):
        player, mob = self.actor(), self.actor(player=False)
        with patch.object(combat, 'roll', side_effect=lambda chance: chance):
            self.assertEqual(formulas.critical(player, mob, 160, False), 0)
            self.assertEqual(formulas.critical(player, mob, -5), 0)
            self.assertEqual(formulas.critical(mob, player, -5, False), 5)
            self.assertEqual(formulas.critical(player, player, -5), 0)
            self.assertEqual(formulas.critical(mob, player, 30, False), 30)

    def test_intellect_and_overlevel_weapon_scale_once_with_ammunition(self):
        char = NS(level=12, attr=lambda _: 15)
        gun = combat.Weapon(3, 100, 200, 5, 10, 20, 1, .1, 30, 1, 4, sdmin=10, sdmax=20)
        rules = Rules(simulator_formulas=True, ammo_modifiers=True)
        ammo = dict(dam_mod=1.1, st_mod=.9, range_mod=1.2)
        result = formulas.weapon(gun, char, None, ammo, rules)
        self.assertEqual((result.dmin, result.dmax, result.sdmin, result.sdmax), (143, 286, 12, 23))
        self.assertEqual((result.opt_lo, result.opt_hi, result.max_range, result.cone), (5, 10, 24, .1))
        with patch.object(inventory, 'item_level', return_value=14), patch.object(formulas, 'weapon_reference', return_value=(1, 'fist')):
            short = formulas.weapon(gun, char, dict(type_id=25055), ammo, rules)
        self.assertAlmostEqual(short.cone, .22)
        self.assertEqual(short.dmax, round(200 * 1.3 * .76 * 1.1))
        self.assertEqual(gun.dmax, 200)
        self.assertEqual(formulas.melee((100, 200), char, None), (130, 260))
        self.assertAlmostEqual(formulas.healing_multiplier(char), 1.4)
        self.assertEqual(formulas.cooldown_seconds(char), 3)
        self.assertEqual(formulas.cooldown_seconds(NS(attr=lambda _: 100)), 2)
        self.assertEqual(formulas.cooldown_seconds(NS(attr=lambda _: 1)), 4)
        with self.assertRaises(ValueError):
            formulas.weapon(gun, char, None, dict(dam_mod=float('nan')), rules)

    def test_shared_room_uses_attacker_profile_and_never_enables_normal_actors(self):
        current, simulator = self.actor(enabled=False), self.actor()
        rc = object.__new__(training.TrainingCombat)
        gun = combat.Weapon(1, 100, 100, 1, 10, 20, 1, .1, 0, 1, 4)
        self.assertEqual(rc.bullet_damage(current, simulator, gun, 100, 0, False, 200),
                         combat.split_damage(100, 148, 1, False, 200))
        self.assertEqual(rc.bullet_damage(simulator, current, gun, 100, 0, False, 200), (0, 100))
        self.assertEqual(rc.melee_damage(current, simulator, 100, False, 200), combat.melee_split(100, False, 200))
        self.assertEqual(rc.melee_damage(simulator, current, 100, False, 200), (0, 100))
        self.assertFalse(formulas.enabled(NS(is_player=True)))
        self.assertFalse(formulas.enabled(NS(is_player=False)))

    def test_A_and_G_use_distinct_source_coefficients(self):
        self.assertEqual(formulas.weapon_reference(25055), (1, 'machinegun'))
        self.assertEqual(formulas.weapon_reference(25056), (1, 'machinegun'))
        self.assertEqual(formulas.weapon_reference(26075)[0], 1)

    def test_source_A_G_damage_undoes_old_normalization_and_uses_candidate_mode(self):
        # Frozen directly from LavaFixed 6b7b28d at shooting 20, Intellect 5.
        fixtures = ((25055, 0, 24, 89), (25055, 1, 20, 85), (25055, 2, 20, 94),
                    (25056, 0, 29, 107), (25056, 1, 24, 102), (25056, 2, 24, 112))
        character = NS(level=20, attr=lambda _: 5)
        gun = combat.Weapon(3, 999, 999, 1, 20, 40, 1, .1, 0, 1, 6)
        rules = Rules(simulator_formulas=True, ammo_modifiers=True)
        ammo = dict(dam_mod=.9, st_mod=.9, range_mod=1.2)
        for source, mode, minimum, maximum in fixtures:
            with self.subTest(source=source, mode=mode):
                # AI may evaluate a mode different from the currently selected one.
                row = dict(type_id=source, cur_mode=0)
                result = formulas.weapon(gun, character, row, ammo, rules, mode=mode)
                self.assertEqual((result.dmin, result.dmax), (minimum, maximum))
        self.assertEqual(gun.dmin, 999)

    def test_source_gold_blade_uses_own_base_and_strength_before_scaling(self):
        character = NS(level=20, attr=lambda _: 5)
        self.assertEqual(formulas.melee((999, 999), character, dict(type_id=6231)), (36, 44))
        self.assertEqual(formulas.melee((999, 999), character, dict(type_id=6241)), (49, 67))


class SimulatorSession(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged

    def enable(self, ground):
        ground.request(dict(op='rules', token=ground.token,
                            values=Rules(simulator_formulas=True, ammo_modifiers=True).values()))

    async def test_rules_survive_exit_and_never_change_main_character(self):
        ground = self.enter()
        self.enable(ground)
        self.assertTrue(ground.clone.character().training_rules.simulator_formulas)
        self.assertTrue(self.store.training_profile(self.s.char_id)['rules']['simulator_formulas'])
        self.assertFalse(hasattr(self.s.character(), 'training_rules'))
        self.unchanged()
        ground.exit(notify=False)
        restored = training.Ground(self.s)
        try:
            self.assertTrue(restored.rules.simulator_formulas)
            self.unchanged()
        finally:
            restored.exit(notify=False)

    async def test_applied_profile_changes_real_fighter_weapon_without_mutating_templates(self):
        ground = self.enter()
        source = 26075
        before = dict(items.params_of(source))
        self.enable(ground)
        char = ground.clone.character()
        gun = combat.Weapon(1, 100, 200, 1, 10, 20, 1, .1, 30, 1, 4)
        expected = formulas.weapon(gun, char, ground.clone.inv.in_slot(inventory.PRIMARY), {}, ground.rules)
        self.assertEqual(ground.clone.combat.prepare_weapon(gun, {}), expected)
        self.assertEqual(items.params_of(source), before)
        self.assertEqual(training_balance.RATIOS, dict(A=1, P=1.06, G=1.12))
        self.unchanged()

    async def test_profile_mob_crit_changes_only_spawned_copy(self):
        ground = self.enter()
        self.enable(ground)
        ground.mob_type = 1733
        original = mobs.stats(ground.mob_type)
        before = dict(vars(original))
        ground.start('mob')
        mob = ground.room.combat.mobs[ground.mob_eid]
        expected = 3 * (5 + mob.stats.spec) + mob.stats.level / 4 + mob.stats.spec
        self.assertEqual(mob.stats.crit, expected)
        if hasattr(mob, 'training_weapon'):
            self.assertEqual(mob.training_weapon.crit, expected)
        self.assertEqual(vars(original), before)
        self.unchanged()

    async def test_new_mob_has_frozen_source_health_and_distance_modes(self):
        ground = self.enter()
        self.enable(ground)
        ground.mob_type = 1733
        ground.start('mob')
        mob = ground.room.combat.mobs[ground.mob_eid]
        record = formulas.data()['mob_records'][formulas.data()['mobs'][str(mob.type_id)]]
        self.assertEqual(mob.hp_max, record['hp_max'])
        self.assertEqual(mob.sp_max, record['sp_max'])
        self.assertEqual(mob.stats.armor, record['armor'])
        self.assertTrue(mob.training_modes)
        for distance in (1, max(weapon.max_range for weapon, _cost, _delay in mob.training_modes)):
            selected = formulas.mob_mode(mob, distance)
            self.assertIsNotNone(selected)
            self.assertGreaterEqual(selected[0].max_range, distance)
        self.assertIsNone(formulas.mob_mode(mob, 1000))
        self.unchanged()

    async def test_real_battle_heal_commits_once_and_uses_profile_cooldown(self):
        ground = self.enter()
        self.enable(ground)
        clone = ground.clone
        clone.char.set_skill(progression.MEDICINE, 20)
        clone.char.set_spec(8, 5)
        clone.char.hp = 1
        clone.char.sp = 1
        ground.room.combat.set_ws(True)
        row = clone.inv.create(training_items.copy_type(6055))
        fighter = clone.combat
        fighter.ap = fighter.ap_max
        cost = items.params_of(row['type_id'])['heal_cost']
        before = fighter.ap
        maximum = clone.char.vitals()['hmax']
        self.assertEqual(fighter.healing_multiplier(clone.char), 1.2)
        with patch.object(combat, 'now', return_value=100), patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: hi):
            fighter.heal_now(row['uniq'], fighter, ap_cost=cost)
        self.assertIsNone(ground.store.item(row['uniq']))
        self.assertEqual(fighter.ap, before - cost)
        self.assertEqual(clone.char.hp, min(maximum, 1 + int(items.params_of(row['type_id'])['max_h_rest'] * 2 * 1.2)))
        self.assertEqual(battle_medicine.remaining_ms(ground.store, clone.char_id, 100), 3500)
        self.assertEqual(battle_medicine.remaining_ms(self.store, self.s.char_id, 100), 0)
        hp = clone.char.hp
        fighter.heal_now(row['uniq'], fighter, ap_cost=cost)
        self.assertEqual(clone.char.hp, hp)
        self.assertEqual(fighter.ap, before - cost)
        self.unchanged()

    async def test_known_weapon_row_avoids_another_inventory_read(self):
        ground = self.enter()
        self.enable(ground)
        weapon = combat.Weapon(1, 100, 200, 1, 10, 20, 1, .1, 30, 1, 4)
        row = dict(type_id=training_items.copy_type(26075))
        with patch.object(ground.clone.inv, 'in_slot', side_effect=AssertionError('duplicate inventory query')):
            result = ground.clone.combat.prepare_weapon(weapon, {}, row)
        self.assertGreater(result.dmax, 0)
        self.unchanged()

    async def test_real_shot_factory_uses_profile_once_and_actual_ammo(self):
        ground = self.enter()
        self.enable(ground)
        profile = training.preset(12)
        profile['specs'][3] = 3
        profile['gear'] = {26075: 1}
        ground.profile = training.validate_profile(profile)
        ground.spawn_point = 0
        ground.start('mob')
        ground.clone.cmd_lenter({})
        gun = ground.clone.inv.in_slot(inventory.PRIMARY)
        si = items.params_of(gun['type_id'])
        ammo = si['comp_array'][0]
        ground.store.update_item(gun['uniq'], ammo_count=3, ammo_type=ammo)
        target = next(iter(ground.room.combat.mobs.values()))
        with patch.object(combat.Fighter, 'schedule_action') as schedule:
            ground.clone.combat.use_fire(dict(obj=inventory.oid_of(gun), target='1%08x' % target.eid))
        weapon = schedule.call_args.args[8]
        multiplier, spread = formulas.damage_multiplier(ground.clone.character(), gun)
        mode = gun['cur_mode']
        source = training_items.profile_source(gun['type_id'])
        base = formulas.data()['weapon_bases'][str(source)]
        self.assertEqual(weapon.dmin, max(1, round(base['h_damage_min'][mode] * multiplier * items.params_of(ammo)['dam_mod'])))
        self.assertEqual(weapon.max_range, math.floor(si['max_range'][mode] * items.params_of(ammo)['range_mod'] + 1e-9))
        self.assertEqual(weapon.opt_lo, si['opt_range'][mode])
        self.assertGreater(spread, 0)
        self.unchanged()

    async def test_all_thirteen_prototypes_have_own_identity_ammo_and_only_private_items(self):
        ground = self.enter()
        self.enable(ground)
        self.assertEqual(len(training_items.PROTOTYPES), 13)
        for source, record in training_items.PROTOTYPES.items():
            self.assertEqual(training_items.copy_type(source), source)
            self.assertEqual(training_items.profile_source(source), source)
            self.assertEqual(training_items.source_type(source), record['base'])
            self.assertTrue(training_items.is_copy(source))
            self.assertNotIn(source, items.catalogue())
            self.assertEqual(inventory.item_level(source), record['level'])
            si = items.params_of(source)
            self.assertTrue(si['comp_array'])
            self.assertTrue(all(training_items.is_copy(ammo) and items.root_of(ammo) == items.AMMO for ammo in si['comp_array']))
            row = ground.clone.inv.create(source)
            self.assertEqual(row['type_id'], source)
            ground.store.update_item(row['uniq'], slot=inventory.PRIMARY)
            ground.remember_outfit()
            self.assertIn(source, ground.profile['gear'])
            ground.store.delete_item(row['uniq'])
        ground.exit(notify=False)
        self.assertFalse(any(training_items.is_copy(row['type_id']) for row in self.s.inv.rows()))
        self.unchanged()

    async def test_prototype_is_bought_free_from_special_stall_and_cannot_leave(self):
        ground = self.enter()
        self.enable(ground)
        source = next(iter(training_items.PROTOTYPES))
        fixtures.TrainingGround.approach_shop(self, ground, 'specialist')
        stock = training.training_shop.stock(training.training_layout.BY_KEY['specialist'])
        self.assertIn(source, stock)
        before = len(ground.clone.inv.rows())
        fixtures.TrainingGround.supply(self, ground, source)
        self.assertEqual(len(ground.clone.inv.rows()), before + 1)
        self.assertTrue(any(row['type_id'] == source for row in ground.clone.inv.rows()))
        ground.exit(notify=False)
        self.assertFalse(any(training_items.is_copy(row['type_id']) for row in self.s.inv.rows()))
        self.unchanged()

    async def test_party_visitors_keep_independent_rules(self):
        members, _parties, _party = fixtures.TrainingGround.party_members(self, 2)
        ground = self.enter()
        other = members[1].training_ground
        self.assertIs(other.room, ground.room)
        self.enable(ground)
        self.assertTrue(ground.rules.simulator_formulas)
        self.assertFalse(other.rules.simulator_formulas)
        self.assertFalse(other.clone.character().training_rules.simulator_formulas)
        self.assertFalse(self.store.training_profile(members[1].char_id)['rules']['simulator_formulas'])
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(SimulatorEquations, SimulatorSession)
