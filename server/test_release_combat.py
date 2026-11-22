"""Release boundaries: timed items, fractional XP, loot and purchase prices."""
import copy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import battle_medicine
import combat
import effects
import holdings
import inventory
import items
import mobs
import progression
import test_combat_xp_cap as xp_fixture
import test_training_ground as fixtures


class TimedItems(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown

    def manager(self):
        self.s.on_map = False
        self.s.room.players[self.s] = True
        self.s.room.combat = combat.RoomCombat(self.s.room, self.store)
        self.s.effects = effects.Effects(self.s)
        self.s.effects.load()
        self.addCleanup(self.s.effects.close)
        return self.s.effects

    async def test_use_relog_expiry_and_quest_snapshot(self):
        manager = self.manager()
        row = self.s.inv.create(3206)
        f = self.s.combat
        f.ap = f.ap_max
        effects.activate(f, row['uniq'], f, 0)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertAlmostEqual(effects.multiplier(self.s, 'mob_exp'), .2)
        self.assertEqual(len(self.store.effects_for(self.s.char_id)), 1)
        # Quest rollback copies only character values, never the socket or DB.
        self.assertEqual(copy.deepcopy(self.s.char).__dict__, self.s.char.__dict__)
        deadline = manager.active['experience_down'].deadline
        manager.close()
        manager.load()
        self.assertEqual(manager.active['experience_down'].deadline, deadline)
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
            self.assertEqual(effects.multiplier(self.s, 'mob_exp'), 1)
            self.assertFalse(manager.active)
            self.assertIsNone(manager.timer)

    async def test_weaker_dose_and_foreign_target_are_not_consumed(self):
        manager = self.manager()
        manager.add(3206)
        row = self.s.inv.create(3205)
        effects.activate(self.s.combat, row['uniq'], self.s.combat, 0)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.assertAlmostEqual(effects.multiplier(self.s, 'mob_exp'), .2)
        self.assertIsNotNone(effects.use_error(self.s.combat, object(), 3201))
        self.assertIsNotNone(effects.use_error(self.s.combat, self.s.combat, 3203))
        self.s.char.skill[progression.SHOOTING][0] = 18
        self.s.char.skill[progression.MELEE][0] = 9
        self.assertIsNone(effects.use_error(self.s.combat, self.s.combat, 3203))

    async def test_bonuses_do_not_stack_and_downward_effect_keeps_fraction(self):
        manager = self.manager()
        manager.add(3206)
        manager.add(3206)
        manager.add(3207)
        self.assertAlmostEqual(effects.multiplier(self.s, 'mob_exp'), .01)
        f, character, spec = xp_fixture.CombatXpCap().fighter(level=12)
        f.sess.effects = manager
        fixture = xp_fixture.CombatXpCap()
        target = fixture.mob(level=14)
        before = (character.skill[progression.SHOOTING][1], character.spec[spec][:], dict(character.xp_carry))
        for _ in range(100):
            f.award_xp(progression.SHOOTING, spec, 2, target)
            self.assertEqual((character.skill[progression.SHOOTING][1], character.spec[spec], character.xp_carry), before)
        fixture.settle(target, f)
        expected = progression.combat_mob_xp(14, 12) * .01
        self.assertAlmostEqual(character.skill[progression.SHOOTING][1] + character.xp_carry[progression.SHOOTING], expected)

    async def test_fixed_six_second_shared_medicine_cooldown(self):
        self.assertEqual(self.s.combat.medicine_cooldown_seconds(), 6)
        self.s.char.attrib[progression.INTELLECT] = 20
        self.assertEqual(self.s.combat.medicine_cooldown_seconds(), 6)
        self.assertEqual(battle_medicine.start(self.store, self.s.char_id, 100), 6000)
        self.assertEqual(battle_medicine.remaining_ms(self.store, self.s.char_id, 105), 1000)
        self.assertEqual(battle_medicine.remaining_ms(self.store, self.s.char_id, 106), 0)

    async def test_effect_and_dose_roll_back_together_on_storage_failure(self):
        manager = self.manager()
        row = self.s.inv.create(3206)
        fighter = self.s.combat
        fighter.ap = fighter.ap_max
        before_ap = fighter.ap
        with patch.object(self.store, 'delete_item', side_effect=RuntimeError('storage unavailable')):
            with self.assertRaises(RuntimeError):
                effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertEqual(self.store.item(row['uniq'])['use_count'], row['use_count'])
        self.assertFalse(self.store.effects_for(self.s.char_id))
        self.assertFalse(manager.active)
        self.assertEqual(fighter.ap, before_ap)

    async def test_expired_dead_or_moved_dose_callbacks_do_not_grant_effects(self):
        manager = self.manager()
        fighter = self.s.combat
        row = self.s.inv.create(3206)
        fighter.ap = fighter.ap_max
        with patch.object(fighter, 'present', return_value=False):
            effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertFalse(manager.active)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.store.update_item(row['uniq'], slot=inventory.BANK)
        effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertFalse(manager.active)
        self.assertIsNotNone(self.store.item(row['uniq']))
        self.store.update_item(row['uniq'], slot=inventory.BAG)
        effects.activate(fighter, row['uniq'], fighter, 1)
        deadline = manager.active['experience_down'].deadline
        ap = fighter.ap
        effects.activate(fighter, row['uniq'], fighter, 1)
        self.assertEqual(manager.active['experience_down'].deadline, deadline)
        self.assertEqual(fighter.ap, ap)

    async def test_refresh_replaces_the_timer_and_expired_relogin_is_clean(self):
        manager = self.manager()
        manager.add(3206)
        handles = []
        for _ in range(100):
            handles.append(manager.timer)
            manager.refresh(notify=False)
        self.assertTrue(all(handle.cancelled() for handle in handles))
        self.assertFalse(manager.timer.cancelled())
        self.store.put_effect(self.s.char_id, 'experience_down', 3206, 10, 11)
        manager.close()
        manager.load()
        self.assertFalse(manager.active)
        self.assertIsNone(manager.timer)

    async def test_syringe_twenty_attempts_hit_or_miss_then_disappears(self):
        self.manager()
        f, rc = self.s.combat, self.s.room.combat
        self.addCleanup(combat.Fighter.cancel_timers, f)
        row = self.s.inv.create(items.POISON_SYRINGE, slot=inventory.PRIMARY)
        target = NS(is_player=True, eid=999, cell=self.s.pos + 1, present=lambda _rc: True,
                    dodge_melee=lambda: 0, crit_evade_melee=lambda: 0,
                    sp_now=lambda: 7000, apply_damage=lambda _h, _s: False)
        self.enterContext(patch.object(combat.Fighter, 'allied', return_value=False))
        self.enterContext(patch.object(combat.Fighter, 'same_clan', return_value=False))
        self.enterContext(patch.object(combat.mobs, 'adjacent', return_value=True))
        self.enterContext(patch.object(rc, 'melee_critical', return_value=False))
        damage = self.enterContext(patch.object(rc, 'melee_damage', return_value=(7000, 7000)))
        self.enterContext(patch.object(rc, 'after_hostile'))
        self.enterContext(patch.object(rc, 'hit_landed'))
        self.enterContext(patch.object(rc, 'push_vitals'))
        self.enterContext(patch.object(holdings, 'defender_friendly', return_value=False))
        for attempt in range(20):
            with patch.object(combat, 'roll', return_value=bool(attempt % 2)):
                f.strike_now(target, None, (7000, 7000), combat.SPEC_BLADE, 0, row['uniq'])
            current = self.store.item(row['uniq'])
            if attempt < 19:
                self.assertEqual((current['brk'], current['max_break_cur']), (19 - attempt, 20))
            else:
                self.assertIsNone(current)
        self.assertEqual(damage.call_count, 10)
        f.strike_now(target, None, (7000, 7000), combat.SPEC_BLADE, 0, row['uniq'])
        self.assertEqual(damage.call_count, 10)
        self.assertFalse(any(r['type_id'] == items.POISON_SYRINGE for r in self.s.inv.rows()))

    async def test_syringe_rejects_mobs_and_ground_without_spending_a_dose(self):
        self.manager()
        f, rc = self.s.combat, self.s.room.combat
        row = self.s.inv.create(items.POISON_SYRINGE, slot=inventory.PRIMARY)
        self.enterContext(patch.object(self.s.loc, 'war', True))
        self.enterContext(patch.object(rc, 'actor', return_value=NS(is_player=False, cell=self.s.pos + 1)))
        self.enterContext(patch.object(f, 'preparing', return_value=False))
        start = self.enterContext(patch.object(f, 'strike_with'))
        for target in ('000000001', '000000000'):
            f.use_fire(dict(obj=inventory.oid_of(row), target=target))
        self.assertFalse(start.called)
        f.strike_now(NS(is_player=False, cell=1), None, (7000, 7000), combat.SPEC_BLADE, 0, row['uniq'])
        self.assertEqual(self.store.item(row['uniq'])['brk'], 20)

    async def test_syringe_cannot_be_repaired_or_restored_with_either_currency(self):
        self.manager()
        self.s.char.afro, self.s.char.gold = 1_000_000, 10_000
        self.s.char.save(self.store)
        self.s.inv.trade = inventory.TradeSession(1, 1200)
        row = self.s.inv.create(items.POISON_SYRINGE)
        self.store.update_item(row['uniq'], brk=7, max_break_cur=20)
        before = dict(self.store.item(row['uniq']))
        money = self.store.money(self.s.char_id)
        for code in (inventory.UPD_REPAIR, inventory.UPD_REPAIR_GOLD, inventory.UPD_RESTORE):
            self.s.inv.repair(dict(obj=inventory.oid_of(row)), code)
            self.assertEqual(dict(self.store.item(row['uniq'])), before)
            self.assertEqual(self.store.money(self.s.char_id), money)
        self.s.inv.restore(dict(obj=inventory.oid_of(row)))
        self.assertEqual(dict(self.store.item(row['uniq'])), before)

    async def test_requirement_check_reuses_one_frame_without_changing_masks(self):
        row = self.s.inv.create(26062)
        expected = inventory.weapon_requirement_error(row, self.s.char)
        with patch.object(items, 'params_of', wraps=items.params_of) as params:
            self.assertEqual(inventory.weapon_requirement_error(row, self.s.char), expected)
        self.assertEqual(params.call_count, 1)

    async def test_experience_boosters_apply_gain_keep_skill_cap_and_downward_effect(self):
        manager = self.manager()
        fixture = xp_fixture.CombatXpCap()
        for type_id, multiplier in ((3112, 1.1), (3113, 1.3), (3114, 1.5), (3561, 1.7)):
            with self.subTest(type_id=type_id):
                manager.add(type_id)
                self.assertEqual(len(manager.active), 1)
                self.assertAlmostEqual(effects.multiplier(self.s, 'mob_exp'), multiplier)
                self.assertAlmostEqual(effects.multiplier(self.s, 'pl_exp'), multiplier)
                for level in (12, progression.COMBAT_SKILL_CAP):
                    f, character, spec = fixture.fighter(level)
                    f.sess.effects = manager
                    target = fixture.mob(level + 2)
                    f.award_xp(progression.SHOOTING, spec, 25, target)
                    self.assertEqual(character.skill[progression.SHOOTING][1], 0)
                    self.assertEqual(fixture.spec_total(character, spec), 0)
                    # The active-at-hit reward survives expiry before death.
                    deadline = manager.active['experience_up'].deadline
                    with patch.object(manager, 'clock', return_value=deadline + 1):
                        fixture.settle(target, f)
                        fixture.settle(target, f)
                    expected = progression.combat_mob_xp(level + 2, level) * multiplier
                    skill_xp = character.skill[progression.SHOOTING][1]
                    if level == progression.COMBAT_SKILL_CAP:
                        self.assertEqual(skill_xp, 0)
                        self.assertAlmostEqual(fixture.spec_total(character, spec)
                                               + character.xp_carry.get(('spec', spec), 0), expected)
                    else:
                        self.assertEqual(fixture.spec_total(character, spec), int(expected))
                        self.assertAlmostEqual(skill_xp + character.xp_carry[progression.SHOOTING], expected)
        # Repeated or stale duplicate positive effects cannot exceed +70%.
        manager.add(3561)
        manager.active['stale_duplicate'] = manager.active['experience_up']
        self.assertEqual(effects.multiplier(self.s, 'mob_exp'), 1.7)
        self.assertEqual(effects.multiplier(self.s, 'mob_exp', bonus=.3), 2)
        manager.active.pop('stale_duplicate')
        manager.add(3206)
        self.assertAlmostEqual(effects.multiplier(self.s, 'mob_exp'), .34)
        f, character, spec = fixture.fighter(12)
        f.sess.effects = manager
        target = fixture.mob(14)
        f.award_xp(progression.SHOOTING, spec, 25, target)
        self.assertEqual(character.skill[progression.SHOOTING][1], 0)
        fixture.settle(target, f)
        expected = progression.combat_mob_xp(14, 12) * .34
        self.assertAlmostEqual(character.skill[progression.SHOOTING][1]
                               + character.xp_carry[progression.SHOOTING], expected)

    async def test_experience_dose_relog_expiry_and_weaker_rejection(self):
        manager = self.manager()
        manager.add(3114)
        row = self.s.inv.create(3561)
        effects.activate(self.s.combat, row['uniq'], self.s.combat, 0)
        self.assertIsNone(self.store.item(row['uniq']))
        deadline = manager.active['experience_up'].deadline
        for type_id in (3112, 3113, 3114):
            weaker = self.s.inv.create(type_id)
            effects.activate(self.s.combat, weaker['uniq'], self.s.combat, 0)
            self.assertIsNotNone(self.store.item(weaker['uniq']))
        self.assertEqual(manager.active['experience_up'].deadline, deadline)
        repeated = self.s.inv.create(3561)
        with patch.object(manager, 'clock', return_value=deadline - 1200):
            effects.activate(self.s.combat, repeated['uniq'], self.s.combat, 0)
        self.assertIsNone(self.store.item(repeated['uniq']))
        self.assertEqual(manager.active['experience_up'].deadline, deadline + 600)
        self.assertEqual(len(manager.active), 1)
        self.assertEqual(len(self.store.effects_for(self.s.char_id)), 1)
        deadline += 600
        manager.close()
        manager.load()
        self.assertEqual(manager.active['experience_up'].deadline, deadline)
        self.assertEqual(effects.multiplier(self.s, 'mob_exp'), 1.7)
        with patch.object(manager, 'clock', return_value=deadline + 1):
            manager.refresh()
            self.assertEqual(effects.multiplier(self.s, 'mob_exp'), 1)
            self.assertFalse(manager.active)


class ReleaseCatalogue(unittest.TestCase):
    def test_plus_one_mob_critical_chance_is_halved_without_changing_bosses_or_range(self):
        import battle_balance
        player = NS(is_player=True, character=lambda: NS(level=12))
        mob = NS(is_player=False, stats=NS(level=13, role='mob'))
        with patch.object(combat, 'roll', return_value=False) as roll:
            battle_balance.critical(mob, player, 20, ordinary=True)
            roll.assert_called_with(10)
            battle_balance.critical(mob, player, 0, ordinary=True)
            roll.assert_called_with(2.5)
            battle_balance.critical(mob, player, 20)
            roll.assert_called_with(20)
            mob._holding_prepared = True
            battle_balance.critical(mob, player, 20, ordinary=True)
            roll.assert_called_with(20)
            mob._holding_prepared = False
            mob.stats.level = 14
            battle_balance.critical(mob, player, 20, ordinary=True)
            roll.assert_called_with(10)
            for role, level in (('boss', 13), ('mob', 12), ('mob', 15)):
                mob.stats.role, mob.stats.level = role, level
                battle_balance.critical(mob, player, 20, ordinary=True)
                roll.assert_called_with(20)

    def test_outside_optimal_critical_chance_is_half_for_ordinary_fire(self):
        import battle_balance
        shooter = NS(is_player=True)
        target = NS(is_player=True)
        with patch.object(combat, 'roll', return_value=True) as roll:
            self.assertTrue(battle_balance.critical(shooter, target, 40, ordinary=True))
            roll.assert_called_with(40)
            self.assertTrue(battle_balance.critical(shooter, target, 40, optimal=False, ordinary=True))
            roll.assert_called_with(20)
            self.assertFalse(battle_balance.critical(shooter, target, 40, optimal=False))

    def test_four_level_loot_cutoff_has_no_last_hit_or_scanner_bypass(self):
        fighter = NS(is_player=True, level=14, sess=NS())
        # Object keys in older transient ledgers are also supported.
        class Contributor:
            is_player, level, sess = True, 14, NS()
        senior = Contributor()
        mob = NS(stats=NS(level=10, role='mob'), xp_ledger={senior: [100]}, loot_level=14)
        with patch.object(effects, 'multiplier', return_value=3):
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, mob, fighter), 0)
            mob.stats.level = 11
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, mob, fighter), 3)
            mob.stats.role = 'object'
            self.assertEqual(combat.RoomCombat.loot_multiplier(None, mob, fighter), 1)
        st = NS(role='mob', level=10)
        with patch.object(mobs, 'carried') as carried:
            self.assertEqual(mobs.loot_for(st, None, killer_level=14, multiplier=3), [])
            carried.assert_not_called()

    def test_four_level_cutoff_preserves_only_wanted_personal_quest_loot(self):
        st = NS(role='mob', level=10, type_id=1411)
        class Rng:
            def random(self):
                return 0
        with patch.object(mobs, 'quest_table', return_value=[(3770, 1), (2408, 1)]):
            self.assertEqual(mobs.loot_for(st, Rng(), {3770, 2408}, killer_level=14), [(3770, 1)])
            self.assertEqual(mobs.loot_for(st, Rng(), (), killer_level=14), [])

    def test_scanner_never_multiplies_gold_ingot_chance(self):
        ingot = next(iter(items.GOLD_INGOTS))
        class Rng:
            def random(self):
                return .25
        with patch.object(mobs, 'loot_table', return_value=[(ingot, .1, False), (333, .1, False)]), \
                patch.object(mobs, 'independent_loot', return_value={ingot, 333}), \
                patch.object(mobs, 'one_of_groups', return_value=[]):
            self.assertEqual(mobs.roll_table(82, Rng(), 3), [(333, 1)])

    def test_ordinary_mob_pools_are_reduced_with_original_values_as_floor(self):
        import battle_balance
        frozen = copy.deepcopy(battle_balance.data()['mob_records'])
        tested = 0
        for key, index in battle_balance.data()['mobs'].items():
            original = mobs.MobStats(int(key), balanced=False)
            current = mobs.stats(int(key))
            source = battle_balance.ordinary_mob_reference()[0].get(current.level, frozen[index])
            if original.role != 'mob':
                continue
            tested += 1
            for field in ('hp_max', 'sp_max'):
                self.assertEqual(getattr(current, field),
                                 max(getattr(original, field), round(source[field] / 1.5)))
                self.assertGreaterEqual(getattr(current, field), getattr(original, field))
            # Fresh instances cannot compound the reduction or edit the simulator.
            self.assertEqual(mobs.MobStats(int(key)).hp_max, current.hp_max)
            self.assertEqual(mobs.MobStats(int(key)).sp_max, current.sp_max)
        self.assertGreater(tested, 100)
        self.assertEqual(battle_balance.data()['mob_records'], frozen)

    def test_boss_adjustments_and_common_reduction_cannot_modify_pinned_modes(self):
        import battle_balance
        frozen = copy.deepcopy(battle_balance.data()['mob_records'])
        treasurers = {586, 590, 591, 592, 593, 764, 1024, 1736}
        for tid, adjustment in battle_balance.boss_adjustments().items():
            source = frozen[battle_balance.data()['mobs'][str(tid)]]
            current = mobs.stats(tid)
            original = mobs.MobStats(tid, balanced=False)
            expected = max(original.hp_max, round(source['hp_max'] * adjustment['hp_scale'] / 1.5))
            self.assertEqual(current.hp_max, expected)
            self.assertEqual(current.sp_max, max(original.sp_max, round(source['sp_max'] / 1.5)))
            if tid in treasurers:
                ordinary = [mobs.stats(int(key)).hp_max for key in battle_balance.data()['mobs']
                            if mobs.stats(int(key)).role == 'mob' and mobs.stats(int(key)).level == current.level]
                if ordinary:
                    self.assertGreater(current.hp_max, max(ordinary))
            for mode, before in zip(current.balanced_modes, source['modes']):
                self.assertEqual(mode['dmax'], max(1, round(before['dmax'] * adjustment['damage_scale'] / 1.5)))
        self.assertEqual(battle_balance.data()['mob_records'], frozen)

    def test_contributor_level_survives_character_selection_and_resets_on_respawn(self):
        fixture = xp_fixture.CombatXpCap()
        fighter, character, spec = fixture.fighter(14)
        target = fixture.mob(14)
        target.stats.level = 14
        fighter.award_xp(progression.SHOOTING, spec, 1, target)
        character.set_skill(progression.SHOOTING, 10)
        self.assertEqual(combat.RoomCombat.loot_multiplier(None, target, fighter), 1)
        mob = mobs.Mob(1, 258, 100)
        mob.loot_level = 14
        mob.reset()
        self.assertEqual(mob.loot_level, 0)

    def test_level_loot_bonus_cannot_be_obtained_by_a_low_level_last_hit(self):
        class Fighter:
            is_player = True
            def __init__(self, level):
                self.level = level
                self.sess = NS()
        low, senior = Fighter(10), Fighter(14)
        mob = NS(stats=NS(level=13, role='mob'), xp_ledger={low: [100]})
        multiplier = lambda: combat.RoomCombat.loot_multiplier(None, mob, low)
        self.assertEqual(multiplier(), 1.5)
        mob.stats.level = 14
        self.assertEqual(multiplier(), 1.75)
        for gap, reward in ((1, 1.15), (2, 1.3)):
            mob.stats.level = low.level + gap
            self.assertEqual(multiplier(), reward)
        mob.stats.level = 14
        with patch.object(effects, 'multiplier', return_value=3):
            self.assertEqual(multiplier(), 5.25)
        mob.xp_ledger[senior] = [1]
        self.assertEqual(multiplier(), 1)
        mob.stats.role = 'object'
        with patch.object(effects, 'multiplier', return_value=3):
            self.assertEqual(multiplier(), 1)

    def test_live_sets_match_pinned_simulator_health_stamina_and_armour(self):
        import battle_balance
        import sets
        frozen = battle_balance.data()
        for key, fields in frozen['equipment'].items():
            t = int(key)
            if items.root_of(t) != items.WEAR or not sets.set_of(t):
                continue
            params = items.params_of(t)
            for name in ('armor_class', 'bonus_hp', 'bonus_st'):
                if name in fields:
                    self.assertEqual(params[name], fields[name], (t, name))
        for key, bonuses in frozen['sets'].items():
            set_id = int(key)
            if set_id not in sets.SETS:
                continue
            frame = sets.frame(set_id)
            for count, row in bonuses.items():
                for name in ('hp', 'st'):
                    self.assertEqual(frame.get('bonus_%s_%s' % (count, name), 0), row[name], (set_id, count, name))

    def test_boss_plus_four_uses_mob_plus_two_gap_factor(self):
        import battle_balance
        for level in range(1, 17):
            shooter = NS(is_player=True, character=lambda: NS(level=level))
            mob = NS(is_player=False, stats=NS(level=level + 2, role='mob'), armor=lambda: 0)
            boss = NS(is_player=False, stats=NS(level=level + 4, role='boss'), armor=lambda: 0)
            for critical in (False, True):
                self.assertEqual(battle_balance.split(shooter, boss, 100, 1, critical, 500, ordinary=True),
                                 battle_balance.split(shooter, mob, 100, 1, critical, 500, ordinary=True))

    def test_difficulty_steps_keep_plus_five_as_the_previous_plus_four(self):
        import battle_balance
        shooter = NS(is_player=True, character=lambda: NS(level=16))
        for gap, expected in ((0, 10000), (1, 10000), (2, 8590), (3, 7775), (4, 5636), (5, 500), (6, 500)):
            target = NS(is_player=False, stats=NS(level=16 + gap, role='mob'), armor=lambda: 0)
            self.assertEqual(battle_balance.split(shooter, target, 10000, 1, False, 0, ordinary=True),
                             (expected, 0))
        player = NS(is_player=True, character=lambda: NS(level=21), armor=lambda: 0)
        self.assertEqual(battle_balance.split(shooter, player, 10000, 1, False, 0, ordinary=True),
                         battle_balance.split(shooter, player, 10000, 1, False, 0))

    def test_ordinary_difficulty_moves_up_one_level_without_changing_private_profile(self):
        import battle_balance
        for level in range(1, 21):
            shooter = NS(is_player=True, character=lambda: NS(level=level))
            for gap in (-1, 0, 1, 2, 3, 4, 5, 8):
                target = NS(is_player=False, stats=NS(level=level + gap, role='mob'), armor=lambda: 0)
                before = battle_balance.split(shooter, target, 10000, 1, False, 0)
                after = battle_balance.split(shooter, target, 10000, 1, False, 0, ordinary=True)
                if gap in (1, 2, 3, 4):
                    self.assertGreaterEqual(after[0], before[0])
                else:
                    self.assertEqual(after, before, (level, gap))

    def test_plus_four_curve_affects_only_ordinary_encounter_and_not_bosses_or_pvp(self):
        import battle_balance
        for level in range(1, 18):
            player = NS(is_player=True, character=lambda: NS(level=level), armor=lambda: 0)
            for role in ('mob', 'animal', 'turret', 'boss', 'object'):
                mob = NS(is_player=False, stats=NS(level=level + 4, role=role), armor=lambda: 0)
                native = battle_balance.split(mob, player, 1000, 1, False, 10000, 200)
                ordinary = battle_balance.split(mob, player, 1000, 1, False, 10000, 200, ordinary=True)
                if role in ('mob', 'animal', 'turret'):
                    self.assertEqual(ordinary, (875, 175))
                else:
                    self.assertEqual(ordinary, native)
                # Other gaps retain their previous incoming damage.
                for gap in (0, 1, 2, 3, 5):
                    mob.stats.level = level + gap
                    self.assertEqual(battle_balance.split(mob, player, 1000, 1, False, 10000, 200, ordinary=True),
                                     battle_balance.split(mob, player, 1000, 1, False, 10000, 200))
            other = NS(is_player=True, character=lambda: NS(level=level + 3), armor=lambda: 0)
            self.assertEqual(battle_balance.split(other, player, 1000, 1, False, 10000, 200, ordinary=True),
                             battle_balance.split(other, player, 1000, 1, False, 10000, 200))

    def test_boss_gap_equivalence_preserves_armour_and_ranged_melee_critical_rules(self):
        import battle_balance
        for level in range(1, 17):
            shooter = NS(is_player=True, character=lambda: NS(level=level))
            for armour in (0, 100, 1000):
                mob = NS(is_player=False, stats=NS(level=level + 2, role='mob'), armor=lambda: armour)
                boss = NS(is_player=False, stats=NS(level=level + 4, role='boss'), armor=lambda: armour)
                for critical in (False, True):
                    for melee in (False, True):
                        args = dict(ordinary=True, melee=melee)
                        self.assertEqual(battle_balance.split(shooter, boss, 1000, 1.5, critical, 500, 70, **args),
                                         battle_balance.split(shooter, mob, 1000, 1.5, critical, 500, 70, **args))
                self.assertEqual(boss.stats.level, level + 4)
                self.assertEqual(boss.armor(), armour)

    def test_stamina_damage_waits_for_death_and_solo_kill_settles_only_once(self):
        fixture = xp_fixture.CombatXpCap()
        f, ch, spec = fixture.fighter(12)
        mob = fixture.mob(14)
        f.award_xp(progression.SHOOTING, spec, 25, mob)
        reward = progression.combat_mob_xp(14, 12)
        self.assertEqual(ch.skill[progression.SHOOTING][1], 0)
        self.assertEqual(fixture.spec_total(ch, spec), 0)
        self.assertEqual(ch.xp_carry.get(progression.SHOOTING, 0), 0)
        fixture.settle(mob, f)
        fixture.settle(mob, f)
        self.assertAlmostEqual(ch.skill[progression.SHOOTING][1] + ch.xp_carry[progression.SHOOTING], reward)

    def test_only_documented_ordinary_utility_items(self):
        self.assertEqual(effects.definition(3789)['duration'], 1800)
        self.assertEqual(effects.definition(3826)['duration'], 7200)
        self.assertEqual(items.params_of(3826)['g_cost'], 100)
        for t in (3093, 3823, 31594, 26275, 26607, 6490):
            self.assertIsNone(effects.definition(t))

    def test_experience_boosters_follow_city_ladder_and_original_prices(self):
        import shop_bands
        boosters = {3112, 3113, 3114, 3561}
        for top, expected in ((4, set()), (8, {3112}), (12, {3113}), (16, {3114}), (20, {3561})):
            self.assertEqual(boosters.intersection(shop_bands.stimulants(top)), expected)
            self.assertFalse(boosters.intersection(shop_bands.stimulants(top, 'afro')))
            self.assertEqual(boosters.intersection(shop_bands.stimulants(top, 'gold')), expected)
        for type_id, percent, price in ((3112, 10, 28), (3113, 30, 105), (3114, 50, 210), (3561, 70, 630)):
            self.assertFalse(items.stimulant_unavailable(type_id))
            self.assertEqual(effects.definition(type_id)['modifiers']['mob_exp'], 1 + percent / 100)
            self.assertEqual(effects.definition(type_id)['duration'], 1800)
            self.assertEqual(items.params_of(type_id)['g_cost'], price)
        self.assertNotIn(3561, items.stock_for(2015, 36))
        self.assertNotIn(3561, items.stock_for(2015))
        self.assertIn(3561, items.stock_for(1013, 127))
        from training import effects as private_effects
        self.assertFalse(boosters.intersection(private_effects.definitions()))
        from training import catalog as private_catalog
        self.assertFalse(boosters.intersection(private_catalog.item_catalogue()))

    def test_scanner_changes_probability_not_quantity_or_guaranteed_drop(self):
        rows = [(333, .1, True), (334, 1, False)]
        with patch.object(mobs, 'loot_table', return_value=rows), \
                patch.object(mobs, 'independent_loot', return_value=set()), \
                patch.object(mobs, 'count_of', return_value=1), \
                patch.object(mobs, 'one_of_groups', return_value=[]):
            rng = NS(random=lambda: .2)
            self.assertEqual(mobs.roll_table(82, rng), [(334, 1)])
            self.assertEqual(mobs.roll_table(82, rng, 3), [(333, 1), (334, 1)])
            rng.random = lambda: .31
            self.assertEqual(mobs.roll_table(82, rng, 3), [(334, 1)])

    def test_gold_rounds_price_is_two_hundredths_and_only_selected_types_added(self):
        import shop_bands
        added = shop_bands.gold_ammunition(items.stock_for(1200))
        self.assertTrue(added)
        for t in added:
            self.assertTrue(items.catalogue()[t][1].endswith(('_BB_G', '_EK_G')))
            self.assertEqual(inventory.buy_price(items.params_of(t), items.AMMO, 100, True), 200)

    def test_every_present_city_gun_seller_keeps_compatible_rounds_in_calibre_groups(self):
        import shop_bands
        import world
        checked = 0
        for loc in shop_bands.CITY_OF:
            traders = {t for _, t in world.location(loc).spawns if t in shop_bands.SELLERS}
            traders.update(int(row['type']) for row in world.placed_in(loc)
                           if int(row['type']) in shop_bands.SELLERS)
            for trader in traders:
                stock = items.stock_for(trader, loc)
                guns = [t for t in stock if items.root_of(t) == items.FIRE_ARM]
                if not guns:
                    continue
                checked += 1
                self.assertEqual(len(stock), len(set(stock)), (loc, trader))
                self.assertLess(len(stock), 256, (loc, trader))
                rounds = [t for t in stock if items.root_of(t) == items.AMMO]
                self.assertLess(max(stock.index(t) for t in guns), min(stock.index(t) for t in rounds))
                groups = []
                for type_id in rounds:
                    calibre, rank = shop_bands.ammunition_order(type_id)
                    if not groups or groups[-1][0] != calibre:
                        self.assertNotIn(calibre, [c for c, _ in groups])
                        groups.append((calibre, []))
                    groups[-1][1].append(rank)
                for _, ranks in groups:
                    self.assertEqual(ranks, sorted(ranks))
                for gun in guns:
                    compatible = set(items.params_of(gun)['comp_array'])
                    self.assertTrue(compatible.intersection(rounds), (loc, trader, gun))
                    standard = {t for t in compatible if items.params_of(t).get('cost')
                                and not items.params_of(t).get('g_cost')
                                and not items.out_of_game(t) and not items.acquisition_blocked(t)}
                    self.assertTrue(standard.issubset(stock), (loc, trader, gun, standard - set(stock)))
        self.assertGreater(checked, 20)

    def test_round_order_has_gold_selected_then_ap_then_expansive_and_keeps_sp5_alias(self):
        import shop_bands
        stock = shop_bands.with_weapon_ammunition([25636])
        self.assertEqual(stock[:7], [25636, 6092, 6104, 6116, 6140, 6164, 6152])
        self.assertNotIn(6128, stock)  # Premium handcrafted rounds were not requested.
        self.assertEqual(shop_bands.ammunition_order(6124), ('SP_5_6', 2))
        self.assertEqual(shop_bands.ammunition_order(6160), ('SP_5_6', 5))

    def test_gear_boundary_all_existing_armour_and_weapons(self):
        for t, (root, _) in items.catalogue().items():
            if root not in items.BREAKABLE_ROOTS or items.out_of_game(t):
                continue
            level = inventory.item_level(t)
            if not 4 <= level <= 20:
                continue
            row = dict(type_id=t, root=root)
            with self.subTest(type=t):
                self.assertTrue(inventory.wearable(row, level - 3))
                self.assertFalse(inventory.wearable(row, level - 4))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TimedItems, ReleaseCatalogue)
