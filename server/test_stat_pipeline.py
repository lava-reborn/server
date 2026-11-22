"""Inventory/effect numbers must reach combat and rp_info without drift.

Uses the ordinary character and inventory on an isolated in-memory store.
No balancing constants or live account state are modified.
"""
import copy
import unittest
from unittest.mock import patch

import combat
import effects
import inventory
import items
import progression
import sets
from testkit import attack_fixture
from protocol import decode
import test_training_ground as fixtures


class StatPipeline(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown

    async def test_every_retail_ammo_calibre_reaches_actual_aim_with_all_its_bonuses(self):
        import shop_bands
        combinations = {}
        for gun in shop_bands.wares():
            if items.root_of(gun) != items.FIRE_ARM or items.acquisition_blocked(gun):
                continue
            for ammo in items.params_of(gun)['comp_array']:
                if shop_bands.ammunition_order(ammo)[1] < 6:
                    combinations.setdefault(ammo, gun)
        self.assertGreaterEqual(len(combinations), 60)
        for ammo_id, gun in combinations.items():
            with self.subTest(ammo=ammo_id, gun=gun):
                f, ch, _, _, _, row = attack_fixture(gun)
                for spec in ch.spec:
                    spec[0] = 5
                row.update(ammo_type=ammo_id, ammo_count=100)
                si, ammo = items.params_of(gun), items.params_of(ammo_id)
                row['cur_mode'] = mode = items.first_mode(si['fire_mods'])
                combat.Fighter.use_fire(f, dict(obj='weapon', target='000000005'))
                try:
                    self.assertIsNotNone(f.aim)
                    shot = f.aim._args[-1][3]
                    spec = combat.SPEC_OF_WEAPON[si['weapon_type']]
                    self.assertAlmostEqual(shot.cone, combat.cone_of(
                        combat.spread_factor(ch.skill_level(progression.SHOOTING), ch.spec_level(spec)),
                        si['target_size'][mode], ammo['acc_mod'], si['max_range'][mode]))
                    power = 1 + .03 * max(0, ch.attr(progression.INTELLECT) - 5)
                    self.assertEqual(shot.dmin, max(1, round(si['h_damage_min'][mode] * power * ammo['dam_mod'])))
                    self.assertEqual(shot.sdmin, round(si.get('st_damage_min', [0] * 3)[mode] * power * ammo['st_mod']))
                    self.assertEqual(shot.max_range, int(si['max_range'][mode] * ammo['range_mod'] + 1e-9))
                    self.assertEqual(shot.piercing, ammo['piercing'])
                finally:
                    if f.aim:
                        f.aim.cancel()

    def test_overlevel_gun_keeps_damage_and_loses_no_more_than_fifteen_percent_accuracy(self):
        weapon = combat.Weapon(1, 1000, 2000, 2, 5, 20, 1, .1, 0, None, None,
                               sdmin=500, sdmax=1000)
        ch = self.s.char
        ch.attrib[progression.INTELLECT] = 5
        for skill in ch.skill:
            skill[0] = 13
        ammo = dict(acc_mod=.8, dam_mod=1.1, st_mod=1.1, range_mod=1)
        for missing, ratio in ((0, 1), (1, .95), (2, .9), (3, .85)):
            with patch.object(inventory, 'item_level', return_value=13 + missing):
                shot = self.s.combat.prepare_weapon(weapon, ammo, dict(type_id=25201))
                self.assertEqual((shot.dmin, shot.dmax, shot.sdmin, shot.sdmax), (1100, 2200, 550, 1100))
                self.assertEqual(self.s.combat.prepare_melee((100, 200), dict(type_id=6240)), (100, 200))
                for distance in (1, 5, 10, 20):
                    base = combat.hit_probability(weapon.cone, distance)
                    actual = combat.hit_probability(shot.cone, distance)
                    self.assertGreaterEqual(actual + 1e-9, base * ratio)
                self.assertAlmostEqual(shot.cone, weapon.cone / ratio)
        self.assertEqual((weapon.dmin, weapon.dmax, weapon.cone), (1000, 2000, .1))

    def manager(self):
        self.s.on_map = False
        self.s.room.players[self.s] = True
        self.s.room.combat = combat.RoomCombat(self.s.room, self.store)
        self.s.effects = effects.Effects(self.s)
        self.s.effects.load()
        self.addCleanup(self.s.effects.close)
        return self.s.effects

    def verify_wire(self):
        ch = self.s.character()
        packet = ch.rp_info()
        self.assertEqual(packet['f_attribs'], [ch.attr(i) for i in range(progression.ATTRIBS)])
        self.assertEqual(packet['f_skills'], [ch.skill_level(i) for i in range(progression.SKILLS)])
        self.assertEqual(packet['f_specs'], [max(0, ch.spec_level(i)) for i in range(progression.SPECS)])
        self.assertEqual(packet['ap_max'], 50 + 5 * ch.level)
        self.assertEqual(packet['max_weight'], self.s.inv.carry_limit())
        self.assertEqual(self.s.combat.hp_max, ch.hp_max)
        self.assertEqual(self.s.combat.vitals(), ch.vitals())
        self.assertEqual(self.s.combat.sp_now(), ch.vitals()['scur'])
        self.assertEqual(self.s.combat.ap_max, ch.ap_ceiling)

    async def test_each_available_effect_reaches_combat_and_wire_once_and_expires(self):
        manager = self.manager()
        ch = self.s.character()
        base_attrs = [ch.attr(i) for i in range(progression.ATTRIBS)]
        base_hp, base_sp, base_ap = ch.hp_max, ch.sp_max, ch.ap_ceiling
        base_cp, base_ce = progression.crit_chance(ch, progression.PISTOL)
        base_armour = self.s.combat.armor()
        base_dodge = self.s.combat.dodge_melee()
        base_melee_cp, base_melee_ce = combat.melee_crit(ch, combat.SPEC_FIST), self.s.combat.crit_evade_melee()
        for source, definition in effects.definitions().items():
            with self.subTest(source=source):
                clock = 10000
                with patch.object(manager, 'clock', return_value=clock):
                    manager.add(source)
                    if definition['interval']:
                        clock += definition['interval']
                        with patch.object(manager, 'clock', return_value=clock):
                            manager.refresh()
                    bonus = definition['bonuses']
                    attrs = [a + b for a, b in zip(base_attrs, bonus['attribs'])]
                    self.assertEqual([ch.attr(i) for i in range(progression.ATTRIBS)], attrs)
                    self.assertEqual(ch.hp_max, base_hp + 4 * bonus['attribs'][0] + 20 * bonus['attribs'][2] + bonus['hp'])
                    self.assertEqual(ch.sp_max, base_sp + 4 * bonus['attribs'][1] + 20 * bonus['attribs'][2] + bonus['sp'])
                    self.assertEqual(ch.ap_ceiling, base_ap + bonus['od'])
                    cp, ce = progression.crit_chance(ch, progression.PISTOL)
                    self.assertEqual(cp - base_cp, 2 * bonus['attribs'][1] + bonus['attribs'][3] + bonus['cp'])
                    self.assertEqual(ce - base_ce, (bonus['attribs'][1] + bonus['attribs'][3]) / 2 + bonus['ce'])
                    self.assertEqual(self.s.combat.armor() - base_armour,
                                     (3 * bonus['attribs'][1] + bonus['attribs'][3]) / 4 + bonus['armor'])
                    self.assertEqual(self.s.combat.dodge_melee() - base_dodge,
                                     bonus['attribs'][1] + bonus['attribs'][3])
                    self.assertEqual(combat.melee_crit(ch, combat.SPEC_FIST) - base_melee_cp,
                                     bonus['attribs'][1] + bonus['cp'])
                    self.assertEqual(self.s.combat.crit_evade_melee() - base_melee_ce,
                                     (bonus['attribs'][1] + bonus['attribs'][3]) / 2 + bonus['ce'])
                    self.verify_wire()
                    self.s.writer.frames.clear()
                    manager.static(effects.FIRST + source)
                    name, static = decode(self.s.writer.frames[-1][:-1])
                    self.assertEqual(name, 'e_si')
                    self.assertEqual(static['critical_probability'], bonus['cp'])
                    self.assertEqual(static['critical_evade'], bonus['ce'])
                    self.assertEqual(static['max_hp'], bonus['hp'])
                    self.assertEqual(static['max_sp'], bonus['sp'])
                with patch.object(manager, 'clock', return_value=10000 + definition['duration'] + 1):
                    manager.refresh()
                    self.assertFalse(manager.active)
                    self.assertEqual([ch.attr(i) for i in range(progression.ATTRIBS)], base_attrs)
                    self.assertEqual((ch.hp_max, ch.sp_max, ch.ap_ceiling), (base_hp, base_sp, base_ap))
                    self.assertEqual(progression.crit_chance(ch, progression.PISTOL), (base_cp, base_ce))

    async def test_combined_families_repeat_refresh_and_gear_refresh_do_not_stack(self):
        manager = self.manager()
        ch = self.s.character()
        base = (ch.hp_max, ch.sp_max, progression.crit_chance(ch, progression.PISTOL),
                [ch.attr(i) for i in range(progression.ATTRIBS)])
        for source in (4917, 4937, 3115, 3208, 3468, 3471):
            manager.add(source)
        expected = (base[0] + 35, base[1] + 65 + 4,
                    (base[2][0] + 10 + 2, base[2][1] + 10 + .5),
                    [base[3][0], base[3][1] + 1, base[3][2], base[3][3], base[3][4] + 1])
        for _ in range(10):
            self.s.inv.refresh_gear(push=False)
            manager.refresh()
            self.assertEqual((ch.hp_max, ch.sp_max, progression.crit_chance(ch, progression.PISTOL),
                              [ch.attr(i) for i in range(progression.ATTRIBS)]), expected)
            self.verify_wire()
        self.assertEqual(ch.attrib, base[3])

    async def test_effects_round_trip_relog_without_persisting_temporary_base_stats(self):
        manager = self.manager()
        self.s.char.set_rep(100)
        before = copy.deepcopy(self.s.char.rows())
        for source in (4917, 4937, 3115, 3208, 3468, 3471):
            row = self.s.inv.create(source)
            effects.activate(self.s.combat, row['uniq'], self.s.combat, 0)
            self.assertIsNone(self.store.item(row['uniq']))
        before_relog = (self.s.char.rp_info(), self.s.char.vitals(), self.s.combat.armor(),
                        progression.crit_chance(self.s.char, progression.PISTOL))
        self.s.char.save(self.store)
        manager.close()
        self.s.char = progression.Character.load(self.store, self.s.char_id)
        manager.load()
        after_relog = (self.s.char.rp_info(), self.s.char.vitals(), self.s.combat.armor(),
                       progression.crit_chance(self.s.char, progression.PISTOL))
        self.assertEqual(before_relog, after_relog)
        self.assertEqual(self.s.char.rows(), before)
        self.assertEqual(len(manager.active), 6)

    async def test_intellect_buff_changes_actual_heal_completion(self):
        manager = self.manager()
        ch = self.s.char
        ch.hp = ch.sp = 1
        manager.add(3470)
        row = self.s.inv.create(7100)
        params = items.params_of(row['type_id'])
        expected_hp = min(ch.hp_max, 1 + int(params['min_h_rest'] * 1.2))
        expected_sp = min(ch.sp_max, 1 + int(params['min_st_rest'] * 1.2))
        with patch.object(combat.RNG, 'uniform', side_effect=lambda lo, hi: lo):
            self.s.combat.heal_now(row['uniq'], self.s.combat)
        self.assertEqual((ch.hp, ch.sp), (expected_hp, expected_sp))

    async def test_attribute_changes_reach_derived_stats_and_intellect_damage_healing(self):
        ch = self.s.char
        ch.effects = effects.zero()
        start = [ch.attr(i) for i in range(progression.ATTRIBS)]
        hp, sp, armour, weight = ch.hp_max, ch.sp_max, self.s.combat.armor(), self.s.inv.carry_limit()
        ch.effects['attribs'] = [2, 3, 4, 5, 6]
        self.s.inv.refresh_gear(push=False)
        self.assertEqual(ch.hp_max - hp, 2 * 4 + 4 * 20)
        self.assertEqual(ch.sp_max - sp, 3 * 4 + 4 * 20)
        self.assertEqual(self.s.combat.armor() - armour, (3 * 3 + 5) / 4)
        self.assertEqual(self.s.inv.carry_limit() - weight, 4000)
        self.assertAlmostEqual(self.s.combat.healing_multiplier(ch), 1 + .04 * max(0, start[4] + 6 - 5))
        weapon = combat.Weapon(1, 100, 200, 2, 5, 10, 1, .1, 0, None, None, sdmin=50, sdmax=100)
        prepared = self.s.combat.prepare_weapon(weapon, {}, None)
        self.assertEqual((prepared.dmin, prepared.dmax), (118, 236))
        self.assertEqual((prepared.sdmin, prepared.sdmax), (59, 118))
        self.verify_wire()

    async def test_all_catalogue_ammunition_modifiers_reach_prepared_weapon(self):
        ch = self.s.char
        ch.attrib[progression.INTELLECT] = 5
        weapon = combat.Weapon(1, 1000, 2000, 2, 5, 10, 1, .1, 0, None, None, sdmin=500, sdmax=1000)
        for type_id, (root, _name) in items.catalogue().items():
            if root != items.AMMO:
                continue
            with self.subTest(type_id=type_id):
                ammo = items.params_of(type_id)
                shot = self.s.combat.prepare_weapon(weapon, ammo, None)
                self.assertEqual((shot.dmin, shot.dmax),
                                 (max(1, round(1000 * ammo['dam_mod'])), max(1, round(2000 * ammo['dam_mod']))))
                self.assertEqual((shot.sdmin, shot.sdmax),
                                 (round(500 * ammo['st_mod']), round(1000 * ammo['st_mod'])))
                self.assertEqual(shot.max_range, int(10 * ammo['range_mod'] + 1e-9))

    async def test_compatible_ammo_accuracy_piercing_and_damage_reach_actual_fire_timer(self):
        self.manager()
        ch = self.s.char
        ch.skill[progression.SHOOTING][0] = 20
        ch.spec = [[5, 0, progression.spec_xp_max(5)] for _ in range(progression.SPECS)]
        ch.recalc()
        gun = self.real_item
        params = items.params_of(gun['type_id'])
        mode = items.first_mode(params['fire_mods'])
        self.s.inv.store.update_item(gun['uniq'], slot=inventory.PRIMARY, cur_mode=mode, ammo_count=100)
        self.s.inv.refresh_gear(push=False)
        for ammo_type in params['comp_array']:
            with self.subTest(ammo_type=ammo_type), patch.object(self.s.loc, 'war', 1):
                self.store.update_item(gun['uniq'], ammo_type=ammo_type)
                self.s.combat.use_fire(dict(obj=inventory.oid_of(gun), target='000000001'))
                try:
                    self.assertIsNotNone(self.s.combat.aim)
                    shot = self.s.combat.aim._args[-1][3]
                    ammo = items.params_of(ammo_type)
                    self.assertEqual(shot.piercing, ammo['piercing'])
                    spec = combat.SPEC_OF_WEAPON[params['weapon_type']]
                    expected_cone = combat.cone_of(combat.spread_factor(ch.skill_level(progression.SHOOTING),
                        ch.spec_level(spec)), params['target_size'][mode], ammo['acc_mod'], params['max_range'][mode])
                    self.assertAlmostEqual(shot.cone, expected_cone)
                    intellect = 1 + .03 * max(0, ch.attr(progression.INTELLECT) - 5)
                    self.assertEqual(shot.dmin, max(1, round(params['h_damage_min'][mode] * intellect * ammo['dam_mod'])))
                    self.assertEqual(shot.dmax, max(1, round(params['h_damage_max'][mode] * intellect * ammo['dam_mod'])))
                finally:
                    self.s.combat.cancel_timers()

    async def test_all_declared_sets_count_each_part_and_each_threshold_once(self):
        slots = dict(helm=inventory.HEAD, shirt=inventory.CAMO, armor=inventory.ARMOR,
                     pants=inventory.LEGS, boots=inventory.BOOTS)
        for set_id, definition in sets.SETS.items():
            rows = []
            for index, (slot, type_id) in enumerate(definition['members'].items()):
                rows.append(dict(uniq=index + 1, type_id=type_id, root=items.WEAR,
                                 slot=slots[slot], brk=100))
                with self.subTest(set_id=set_id, count=len(rows)):
                    expected = sets.zero()
                    for row in rows:
                        bonus = inventory.item_bonus(items.params_of(row['type_id']))
                        for key in sets.SCALARS:
                            expected[key] += bonus[key]
                        for key, _ in sets.LISTS:
                            expected[key] = [a + b for a, b in zip(expected[key], bonus[key])]
                    for count, bonus in definition['bonus'].items():
                        if count <= len(rows):
                            for key in sets.SCALARS:
                                expected[key] += bonus[key]
                            for key, _ in sets.LISTS:
                                expected[key] = [a + b for a, b in zip(expected[key], bonus[key])]
                    self.assertEqual(inventory.gear_bonus(rows, self.s.char), expected)

    async def test_every_gear_type_applies_its_attributes_and_scalar_bonuses_once(self):
        ch = self.s.char
        ch.spec = [[0, 0, progression.spec_xp_max(0)] for _ in range(progression.SPECS)]
        base = copy.deepcopy(ch.rows())
        for type_id, (root, _name) in items.catalogue().items():
            if root not in inventory.GEAR_ROOTS:
                continue
            with self.subTest(type_id=type_id):
                params = items.params_of(type_id)
                slot = inventory.HEAD + params['slot_type'] if root == items.WEAR else inventory.PRIMARY
                row = dict(type_id=type_id, root=root, slot=slot, brk=100)
                expected = inventory.item_bonus(params)
                if slot == inventory.BELT:
                    for spec, amount in enumerate(expected['specs']):
                        attrib = progression.SPEC_ATTRIB[spec]
                        if attrib is not None:
                            expected['attribs'][attrib] += amount
                ch.set_gear(inventory.gear_bonus([row], ch))
                packet = ch.rp_info()
                self.assertEqual(packet['f_attribs'], [a + b for a, b in zip(ch.attrib, expected['attribs'])])
                self.assertEqual(packet['f_skills'], [a[0] + b for a, b in zip(ch.skill, expected['skills'])])
                self.assertEqual(packet['f_specs'], expected['specs'])
                self.assertEqual(ch.hp_max, 4 * (ch.attrib[0] + expected['attribs'][0])
                                 + 20 * (ch.attrib[2] + expected['attribs'][2]) + expected['hp'])
                self.assertEqual(ch.sp_max, 4 * (ch.attrib[1] + expected['attribs'][1])
                                 + 20 * (ch.attrib[2] + expected['attribs'][2]) + expected['st'])
                self.assertEqual(ch.ap_ceiling, ch.ap_max + expected['od'])
                self.assertEqual((ch.bonus_cp, ch.bonus_ce), (expected['cp'], expected['ce']))
                self.assertEqual(ch.rows(), base)

    async def test_bag_bank_and_held_consumables_do_not_lend_passive_stats(self):
        rows = []
        for slot in (inventory.BAG, inventory.BANK):
            rows.extend(dict(type_id=type_id, root=items.WEAR, slot=slot, brk=100)
                        for type_id in sets.SETS[11185]['members'].values())
        rows.extend(dict(type_id=type_id, root=items.HEAL, slot=slot, brk=100)
                    for type_id, slot in ((4917, inventory.PRIMARY), (3115, inventory.SECONDARY)))
        self.assertEqual(inventory.gear_bonus(rows, self.s.char), sets.zero())


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(StatPipeline)
