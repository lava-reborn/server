"""Inventory/effect numbers must reach combat and rp_info without drift.

Uses the ordinary character and inventory on an isolated in-memory store.
No balancing constants or live account state are modified.
"""
import copy
import asyncio
import unittest
from unittest.mock import patch

import combat
import battle_balance
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

    async def test_learning_and_forgetting_with_pouch_refresh_temporary_attributes_immediately(self):
        ch = self.s.char
        ch.set_skill(progression.SHOOTING, 16)
        self.s.inv.create(5615, slot=inventory.BELT)
        self.s.inv.refresh_gear(push=False)
        base = ch.attrib[progression.AGILITY]
        direct = ch.bonus_attribs[progression.AGILITY]
        self.assertEqual(ch.spec_level(1), -1)
        for status, expected in ((progression.UPD_LEARN, direct + 4),
                                 (progression.UPD_FORGET, direct),
                                 (progression.UPD_LEARN, direct + 4)):
            self.s.writer.frames.clear()
            self.s.training_upd(dict(s_status=status, obj='1'))
            frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
            self.assertEqual([f['res'] for cmd, f in frames if cmd == 'cmdAck'], [0])
            self.assertEqual(ch.bonus_attribs[progression.AGILITY], expected)
            self.assertEqual(ch.attrib[progression.AGILITY], base)
            self.assertEqual(ch.level, 16)
            persisted = progression.Character.load(self.store, self.s.char_id)
            self.assertEqual(persisted.attrib, ch.attrib)
            self.assertEqual(persisted.bonus_attribs, [0] * progression.ATTRIBS)

    async def test_login_keeps_weapon_supported_by_a_pouch_without_saving_bonus_levels(self):
        ch = self.s.char
        ch.set_skill(progression.SHOOTING, 2)
        ch.set_skill(progression.MELEE, 2)
        ch.set_spec(1, 1)
        self.s.inv.create(5614, slot=inventory.BELT)  # Original pouch: melee +1.
        weapon = self.s.inv.create(6240, slot=inventory.PRIMARY)  # Tesak, tier 6.
        self.s.inv.refresh_gear(push=False)
        self.assertEqual(ch.skill_level(progression.MELEE), 3)
        self.assertTrue(inventory.wearable(weapon, ch.level, ch))
        ch.save(self.store)
        before = ch.rows()
        self.s.load_character(self.s.char_id)
        self.assertEqual(self.s.char.rows(), before)
        self.assertEqual(self.s.char.level, 2)
        self.assertEqual(self.store.item(weapon['uniq'])['slot'], inventory.PRIMARY)

    async def test_pouch_ap_ceiling_updates_live_without_refilling_or_changing_progress(self):
        ch, fighter = self.s.char, self.s.combat
        ch.set_skill(progression.MELEE, 17)
        ch.set_skill(progression.SHOOTING, 17)
        fighter.amax_sent, fighter.ap = ch.ap_ceiling, 23
        row = self.s.inv.create(5615, slot=inventory.BAG)
        before = ch.rows()
        for _ in range(3):
            for slot, maximum in ((inventory.BELT, 155), (inventory.BAG, 135)):
                self.store.update_item(row['uniq'], slot=slot)
                self.s.writer.frames.clear()
                self.s.inv.refresh_gear()
                frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
                self.assertEqual([p for name, p in frames if name == 'c_ap'],
                                 [dict(ap=23, amax=maximum)])
                self.assertEqual((fighter.ap_max, fighter.ap), (maximum, 23))
                self.assertEqual(ch.rows(), before)
                self.s.writer.frames.clear()
                self.s.inv.refresh_gear()
                self.assertFalse(self.s.writer.frames)  # Recount is idempotent.
        self.store.update_item(row['uniq'], slot=inventory.BELT)
        self.s.inv.refresh_gear()
        ch.set_skill(progression.SHOOTING, 18)
        self.s.push_stats()
        self.assertEqual((ch.skill_ap_bonus, fighter.ap_max, fighter.ap), (15, 155, 23))
        fighter.ap = 153
        self.store.update_item(row['uniq'], slot=inventory.BAG)
        self.s.writer.frames.clear()
        self.s.inv.refresh_gear()
        frames = [decode(frame[:-1]) for frame in self.s.writer.frames]
        self.assertIn(('c_ap', dict(ap=140, amax=140)), frames)
        self.store.update_item(row['uniq'], slot=inventory.BELT)
        self.s.inv.refresh_gear()
        self.assertEqual((fighter.ap_max, fighter.ap), (155, 140))
        fighter.ap = 30
        fighter.walk_ap = ([0, 1, 2, 3], 0, 0)
        self.s.room.ws = True
        with patch.object(combat, 'now', return_value=1.5 * combat.mobs.HEX_MS / 1000):
            self.store.update_item(row['uniq'], slot=inventory.BAG)
            self.s.inv.refresh_gear()
            self.assertEqual(fighter.ap, 29)
            self.assertEqual(fighter.walk_ap[2], 1)
            self.assertFalse(fighter.sync_ap_ceiling())
            self.assertEqual(fighter.ap, 29)

    async def test_every_released_rifle_mode_aim_uses_small_uniform_followup_without_other_changes(self):
        import shop_bands
        guns = []
        for gun in set(shop_bands.wares()) | set(range(7065, 7070)):
            if (items.root_of(gun) == items.FIRE_ARM and not items.out_of_game(gun)
                    and not items.acquisition_blocked(gun)
                    and 6 <= inventory.item_level(gun) <= 17
                    and items.params_of(gun)['weapon_type'] == items.RIFLE):
                guns.append(gun)
        self.assertGreaterEqual(len(guns), 20)
        for gun in guns:
            frozen = copy.deepcopy(items.params_of(gun))
            for mode, shots in enumerate(frozen['fire_mods']):
                if not shots:
                    continue
                with self.subTest(gun=gun, mode=mode):
                    prepared = []
                    for multiplier in (1, .95):
                        fighter, character, _, _, events, row = attack_fixture(gun)
                        for spec in character.spec:
                            spec[0] = 5
                        row.update(cur_mode=mode, ammo_type=frozen['comp_array'][0], ammo_count=100)
                        with patch.object(battle_balance, 'RIFLE_SPREAD', multiplier), \
                                patch.object(combat.pace, 'paced', side_effect=lambda seconds: seconds):
                            combat.Fighter.use_fire(fighter, dict(obj='weapon', target='000000005'))
                        try:
                            self.assertIsNotNone(fighter.aim)
                            args = fighter.aim._args[-1]
                            prepared.append(args[3])
                            delay = fighter.aim.when() - asyncio.get_running_loop().time()
                            self.assertAlmostEqual(delay, frozen['fire_times'][mode] / 1000, delta=.02)
                            self.assertEqual(args[4], frozen['fire_costs'][mode])
                            self.assertEqual(row['ammo_count'], 100)
                            self.assertEqual(next(p['num_shots'] for n, p in events if n == 'faAim'), shots)
                        finally:
                            combat.Fighter.cancel_timers(fighter)
                    before, after = prepared
                    self.assertAlmostEqual(after.cone, before.cone * .95)
                    for field in before._fields:
                        if field != 'cone':
                            self.assertEqual(getattr(after, field), getattr(before, field), field)
            self.assertEqual(items.params_of(gun), frozen)

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
                    factor = max(.1, 1 + (.7 - .65 / 20 * ch.skill_level(progression.SHOOTING))
                                 + (.8 - .75 / 5 * max(0, ch.spec_level(spec))))
                    expected_cone = combat.cone_of(factor, si['target_size'][mode],
                                                  ammo['acc_mod'], si['max_range'][mode])
                    if si['weapon_type'] in (items.ASSAULT, items.RIFLE) and si['fire_mods'][mode] == 1:
                        expected_cone *= .8
                    if si['weapon_type'] == items.RIFLE:
                        expected_cone *= .95
                    self.assertAlmostEqual(shot.cone, expected_cone)
                    self.assertEqual(shot.hit_cap, battle_balance.weapon_hit_caps().get(gun, .95))
                    power = 1 + .03 * max(0, ch.attr(progression.INTELLECT) - 5)
                    self.assertEqual(shot.dmin, max(1, round(si['h_damage_min'][mode] * power * (1 if items.gold_round(ammo) else ammo['dam_mod']))))
                    self.assertEqual(shot.sdmin, round(si.get('st_damage_min', [0] * 3)[mode] * power * (1 if items.gold_round(ammo) else ammo['st_mod'])))
                    self.assertEqual(shot.max_range, int(si['max_range'][mode] * ammo['range_mod'] + 1e-9))
                    self.assertEqual(shot.piercing, ammo['piercing'])
                finally:
                    if f.aim:
                        f.aim.cancel()

    async def test_all_collectible_svd_modes_use_the_reviewed_damage_in_native_aim(self):
        for gun in (7065, 7066, 7067, 7068, 7069):
            si = items.params_of(gun)
            for mode, enabled in enumerate(si['fire_mods']):
                if not enabled:
                    continue
                with self.subTest(gun=gun, mode=mode):
                    f, ch, _, _, _, row = attack_fixture(gun)
                    for spec in ch.spec:
                        spec[0] = 5
                    row.update(cur_mode=mode, ammo_type=si['comp_array'][1], ammo_count=20)
                    ammo = items.params_of(row['ammo_type'])
                    try:
                        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000005'))
                        self.assertIsNotNone(f.aim)
                        shot = f.aim._args[-1][3]
                        power = 1 + .03 * max(0, ch.attr(progression.INTELLECT) - 5)
                        self.assertEqual((shot.dmin, shot.dmax), tuple(
                            max(1, round(si[field][mode] * power * (1 if items.gold_round(ammo) else ammo['dam_mod'])))
                            for field in ('h_damage_min', 'h_damage_max')))
                        self.assertEqual(shot.num_shots, si['fire_mods'][mode])
                    finally:
                        combat.Fighter.cancel_timers(f)

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
                    base = combat.hit_probability(weapon.cone * .8, distance, .95)
                    actual = combat.hit_probability(shot.cone, distance, shot.hit_cap)
                    self.assertAlmostEqual(actual, base * ratio)
                self.assertAlmostEqual(shot.cone, weapon.cone * .8 / ratio)
                self.assertAlmostEqual(shot.hit_cap, .95 * ratio)
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
        expected = (base[0] + 3, base[1] + 6 + 4,
                    (base[2][0] + 6 + 2, base[2][1] + 4 + .5),
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
        self.s.char.set_skill(progression.SHOOTING, 17)
        self.s.char.set_skill(progression.MELEE, 9)
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
        expected_hp = min(ch.hp_max, 1 + int(params['min_h_rest'] * 1.03))
        expected_sp = min(ch.sp_max, 1 + int(params['min_st_rest'] * 1.03))
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
        self.assertAlmostEqual(self.s.combat.healing_multiplier(ch), (1 + .04 * max(0, start[4] - 5)) * 1.03)
        weapon = combat.Weapon(1, 100, 200, 2, 5, 10, 1, .1, 0, None, None, sdmin=50, sdmax=100)
        prepared = self.s.combat.prepare_weapon(weapon, {}, None)
        self.assertEqual((prepared.dmin, prepared.dmax), (103, 206))
        self.assertEqual((prepared.sdmin, prepared.sdmax), (52, 103))
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
                                 (max(1, round(1000 * (1 if items.gold_round(ammo) else ammo['dam_mod']))), max(1, round(2000 * (1 if items.gold_round(ammo) else ammo['dam_mod'])))))
                self.assertEqual((shot.sdmin, shot.sdmax),
                                 (round(500 * (1 if items.gold_round(ammo) else ammo['st_mod'])), round(1000 * (1 if items.gold_round(ammo) else ammo['st_mod']))))
                self.assertEqual(shot.max_range, int(10 * ammo['range_mod'] + 1e-9))
                self.assertEqual(shot.hp_multiplier, ammo['dam_mod'] if items.gold_round(ammo) else 1)
                self.assertEqual(shot.sp_multiplier, ammo['st_mod'] if items.gold_round(ammo) else 1)
                self.assertEqual(shot.crit, weapon.crit)

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
                    factor = max(.1, 1 + (.7 - .65 / 20 * ch.skill_level(progression.SHOOTING))
                                 + (.8 - .75 / 5 * max(0, ch.spec_level(spec))))
                    expected_cone = combat.cone_of(factor, params['target_size'][mode],
                                                  ammo['acc_mod'], params['max_range'][mode])
                    if params['weapon_type'] in (items.ASSAULT, items.RIFLE) and params['fire_mods'][mode] == 1:
                        expected_cone *= .8
                    if params['weapon_type'] == items.RIFLE:
                        expected_cone *= .95
                    self.assertAlmostEqual(shot.cone, expected_cone)
                    intellect = 1 + .03 * max(0, ch.attr(progression.INTELLECT) - 5)
                    self.assertEqual(shot.dmin, max(1, round(params['h_damage_min'][mode] * intellect * (1 if items.gold_round(ammo) else ammo['dam_mod']))))
                    self.assertEqual(shot.dmax, max(1, round(params['h_damage_max'][mode] * intellect * (1 if items.gold_round(ammo) else ammo['dam_mod']))))
                finally:
                    self.s.combat.cancel_timers()

    async def test_real_fire_crit_separates_permanent_and_temporary_ratings_for_every_class_and_ammo(self):
        from types import SimpleNamespace as NS
        guns = (25566, 25943, 25201, 25803, 24990, 26177)
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        for gun in guns:
            params = items.params_of(gun)
            for ammo_id in params['comp_array']:
                f, ch, _, _, _, row = attack_fixture(gun)
                for spec in ch.spec:
                    spec[0] = 5
                ch.effects = effects.zero()
                ch.effects['cp'], ch.effects['ce'] = 12, 17
                gear = sets.zero()
                gear['cp'], gear['ce'] = 32, 10
                ch.set_gear(gear, repeat=(2, 3))
                row.update(ammo_type=ammo_id, ammo_count=100,
                           cur_mode=items.first_mode(params['fire_mods']))
                combat.Fighter.use_fire(f, dict(obj='weapon', target='000000005'))
                try:
                    self.assertIsNotNone(f.aim)
                    weapon = f.aim._args[-1][3]
                    self.assertEqual(weapon.crit, progression.crit_chance(ch, params['weapon_type'])[0])
                    for enemy_gun in guns:
                        defender = progression.Character()
                        defender.set_skill(progression.SHOOTING, 16)
                        for spec in defender.spec:
                            spec[0] = 3
                        for anti_bonus in (0, 20, 200):
                            defender.effects = effects.zero()
                            defender.effects['ce'] = 17
                            defence = sets.zero()
                            defence['ce'] = anti_bonus
                            defender.set_gear(defence, repeat=(0, 3))
                            target = NS(is_player=True, level=16, character=lambda: defender,
                                primary=lambda: dict(root=items.FIRE_ARM, type_id=enemy_gun), armor=lambda: 148)
                            target.crit_evade_ranged = lambda: combat.Fighter.crit_evade_ranged(target)
                            expected_anti = progression.crit_chance(defender,
                                items.params_of(enemy_gun)['weapon_type'])[1]
                            self.assertEqual(target.crit_evade_ranged(), expected_anti)
                            for optimal in (False, True):
                                with patch.object(combat, 'roll', return_value=True) as roll:
                                    self.assertTrue(rc.ranged_critical(f, target, weapon, optimal))
                                expected = battle_balance.pvp_critical_chance(weapon.base_crit,
                                    expected_anti - 17, weapon.crit - weapon.base_crit, 17)
                                roll.assert_called_once_with(expected if optimal else expected*.5)
                            hp, sp = rc.bullet_damage(f, target, weapon, weapon.dmax,
                                                     weapon.sdmax, True, 100)
                            self.assertEqual((hp, sp), (weapon.dmax, min(100, weapon.dmax)))
                finally:
                    combat.Fighter.cancel_timers(f)

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
                highest = max(0, *(s[0] + b for s, b in zip(ch.skill, expected['skills'])))
                self.assertEqual(ch.ap_ceiling, 50 + 5 * highest + expected['od'])
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
