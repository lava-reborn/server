"""Light sandbox model, equipment, effect lifecycle and isolation regressions."""
import asyncio
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

import combat
import inventory
import items
import progression
import sets
import training_balance as balance
import training_effects as effects
import training_ground as tg
import training_items
import training_layout as layout
import training_sets
import test_training_ground as fixtures


class TrainingV2(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.TrainingGround.asyncSetUp
    asyncTearDown = fixtures.TrainingGround.asyncTearDown
    enter = fixtures.TrainingGround.enter
    unchanged = fixtures.TrainingGround.unchanged
    approach_shop = fixtures.TrainingGround.approach_shop
    supply = fixtures.TrainingGround.supply

    async def test_reference_price_packet_matches_sources_but_copies_stay_free(self):
        from protocol import decode
        self.enter()
        packet=next(params for name,params in (decode(frame[:-1]) for frame in self.s.writer.frames)
                    if name=='tg' and params.get('op')=='types')
        self.assertEqual(len(packet['costs']),len(packet['copies']))
        self.assertEqual(len(packet['gold_costs']),len(packet['copies']))
        self.assertTrue(any(packet['gold_costs']))
        self.assertTrue(any(packet['costs']))
        for copied,source,afro,gold in zip(packet['copies'],packet['sources'],packet['costs'],packet['gold_costs']):
            import training_legacy, training_ammo
            if source in training_items.PROTOTYPES:
                base = training_items.PROTOTYPES[source]['data']
            else:
                base=training_ammo.parameters(source,training_legacy.apply(source,copy.deepcopy(items.params_of(source))))
            self.assertEqual(afro,base.get('cost',0) or 0)
            self.assertEqual(gold,base.get('g_cost',0) or 0)
            self.assertEqual((items.params_of(copied)['cost'],items.params_of(copied)['g_cost']),(0,0))
        self.unchanged()

    async def test_special_and_event_sources_have_exactly_one_shop(self):
        self.enter()
        for source, (category, _level, label) in tg.item_catalogue().items():
            matching = [post for post in layout.POSTS if post.line and
                        training_items.copy_type(source) in tg.training_shop.stock(post)]
            self.assertEqual(len(matching), 1, (source, label))
            self.assertIn(category, tg.training_supply.STATIONS[matching[0].key])
        self.assertEqual(tg.item_catalogue()[1572][0], 'event_medicine')
        self.assertEqual(tg.item_catalogue()[5844][0], 'special_weapon')
        self.assertNotIn('set', {p.category for p in layout.POSTS})
        self.assertTrue(all('тестовая версия' not in row[2].casefold() for row in tg.item_catalogue().values()))
        self.unchanged()

    async def test_contraband_and_collectors_share_one_dedicated_vendor_without_normal_duplicates(self):
        self.enter()
        vendors=[p for p in layout.POSTS if p.category=='special_weapon']
        self.assertEqual(len(vendors),1)
        post=vendors[0]
        self.assertEqual((post.key,post.line,post.resource),('specialist','all',2391))
        rare=set(tg.training_shop.stock(post))
        expected={training_items.copy_type(source) for source,row in tg.item_catalogue().items() if row[0] in ('special_weapon','experimental_weapon')}
        self.assertEqual(rare,expected)
        self.assertTrue(all(training_items.copy_type(source) in rare for source in tg.contraband() if source in tg.item_catalogue()))
        for ordinary in layout.POSTS:
            if ordinary.category=='weapon':
                self.assertTrue(rare.isdisjoint(tg.training_shop.stock(ordinary)))
        self.unchanged()

    async def test_dedicated_vendor_can_issue_contraband_PKM_for_free(self):
        g = self.enter()
        self.approach_shop(g, 'specialist')
        self.supply(g, 7051)
        copied = training_items.copy_type(7051)
        self.assertTrue(any(row['type_id'] == copied for row in g.clone.inv.rows()))
        self.unchanged()

    async def test_p_g_damage_normalized_without_changing_other_source_fields(self):
        self.enter()
        for source in (26061, 26062, 26063):
            original = copy.deepcopy(items.params_of(source))
            actual = items.params_of(training_items.copy_type(source))
            base = items.params_of(balance.afro_of(source))
            for field in ('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max'):
                self.assertEqual(actual[field], balance.scaled(base[field], balance.RATIOS[balance.line(source)]))
            for field in ('clip_size', 'weight', 'max_break_abs', 'fire_times', 'fire_costs'):
                self.assertEqual(actual[field], original[field])
            self.assertEqual(items.params_of(source), original)
            self.assertEqual((actual['cost'],actual['g_cost'],actual['premium']), (0,0,0))
        self.unchanged()

    async def test_private_sets_scale_only_from_A_and_do_not_mutate_original_records(self):
        original = copy.deepcopy(sets.SETS)
        self.enter()
        grouped = {}
        for key, record in training_sets.records().items():
            if record.get('simulator'):
                continue  # Exact source bonuses are covered by the profile tests.
            grouped.setdefault((record['family'],record['level']),{})[record['variant']] = record
            for source in record['members'].values():
                self.assertEqual(sets.set_of(training_items.copy_type(source)),key)
        for variants in grouped.values():
            for line, record in variants.items():
                for count, bonus in record['bonus'].items():
                    for field,value in bonus.items():
                        self.assertEqual(value,balance.scaled(variants['A']['bonus'][count][field],balance.RATIOS[line]))
        self.assertEqual(sets.SETS,original)

    async def test_twenty_levels_only_in_clone_profiles_and_copy_acquisition(self):
        g=self.enter()
        profile=tg.preset(20)
        profile['specs']=[5]*15
        checked=tg.validate_profile(profile)
        self.assertEqual(checked['specs'][12:],[-1]*3)
        g.configure_player(checked)
        self.assertEqual(g.clone.char.level,20)
        source=next(t for t, row in tg.item_catalogue().items() if row[0]=='weapon' and row[1]==20 and items.acquisition_blocked(t))
        self.assertIsNotNone(g.clone.inv.create(training_items.copy_type(source)))
        self.assertTrue(items.acquisition_blocked(source))
        self.unchanged()

    async def test_buff_refresh_does_not_stack_and_expiry_removes_attribute_bonus(self):
        g=self.enter()
        source=next(t for t,d in effects.definitions().items() if any(d['bonuses']['attribs']) and not d['interval'])
        manager=g.clone.training_effects
        before=[g.clone.char.attr(i) for i in range(5)]
        manager.add(source)
        after=[g.clone.char.attr(i) for i in range(5)]
        self.assertNotEqual(before,after)
        timer=manager.timer
        manager.add(source)
        self.assertTrue(timer.cancelled())
        self.assertEqual([g.clone.char.attr(i) for i in range(5)],after)
        self.assertEqual(len(manager.active),1)
        next(iter(manager.active.values())).deadline=asyncio.get_running_loop().time()-1
        manager.refresh()
        self.assertEqual([g.clone.char.attr(i) for i in range(5)],before)
        self.assertIsNone(manager.timer)
        self.unchanged()

    async def test_periodic_buff_does_not_grant_all_pulses_on_first_use(self):
        g=self.enter()
        source=next(t for t,d in effects.definitions().items() if d['interval'])
        manager=g.clone.training_effects
        manager.add(source)
        self.assertFalse(any(manager.bonus['attribs']))
        active=next(iter(manager.active.values()))
        active.started-=effects.definitions()[source]['interval']+0.01
        manager.refresh()
        self.assertEqual(manager.bonus['attribs'],effects.definitions()[source]['bonuses']['attribs'])
        self.unchanged()

    async def test_weaker_effect_refused_without_changing_active_effect(self):
        g=self.enter()
        family={}
        for source,d in effects.definitions().items():
            if d['bonuses']['hp']:
                family.setdefault(d['family'],[]).append(source)
        values=next(v for v in family.values() if len(v)>1)
        values.sort(key=lambda source:effects.definitions()[source]['bonuses']['hp'])
        manager=g.clone.training_effects
        manager.add(values[-1])
        with self.assertRaises(ValueError): manager.add(values[0])
        self.assertEqual(next(iter(manager.active.values())).source,values[-1])
        self.unchanged()

    async def test_successful_buff_consumes_only_one_private_dose_and_exit_cancels_timer(self):
        g=self.enter()
        source=next(t for t,d in effects.definitions().items() if d['bonuses']['hp'])
        row=g.clone.inv.create(training_items.copy_type(source))
        g.clone.combat.ap=30
        effects.activate(g.clone.combat,row['uniq'],g.clone.combat,3)
        self.assertEqual(g.clone.combat.ap,27)
        self.assertTrue(g.clone.training_effects.active)
        left=g.store.item(row['uniq'])
        self.assertTrue(left is None or left['use_count']==row['use_count']-1)
        timer=g.clone.training_effects.timer
        g.exit(notify=False)
        self.assertTrue(timer.cancelled())
        self.assertFalse(g.clone.training_effects.active)
        self.unchanged()

    async def test_medical_specializations_intellect_and_stamina_model(self):
        g=self.enter()
        fighter=g.clone.combat
        self.assertEqual(fighter.healing_spec(dict(hcur=20,hmax=100)),8)
        self.assertEqual(fighter.healing_spec(dict(hcur=80,hmax=100)),9)
        weapon=combat.Weapon(1,100,100,1,10,20,1,.1,10,1,2)
        with patch.object(g.clone.char,'attr',return_value=10):
            self.assertEqual(fighter.prepare_weapon(weapon,{}).dmin,105)
        g.clone.char.hp=g.clone.char.hp_max
        g.clone.char.sp=0
        with patch.object(g.clone.char,'attr',return_value=20): fighter.regen()
        self.assertEqual(g.clone.char.sp,4)
        g.rules=replace(g.rules,combat_v2=False,ammo_modifiers=False)
        self.assertIs(fighter.prepare_weapon(weapon,{}),weapon)
        self.unchanged()

    async def test_buff_works_through_normal_use_timer_and_cancel_does_not_consume(self):
        g=self.enter()
        source=next(t for t,d in effects.definitions().items() if d['bonuses']['hp'])
        row=g.clone.inv.create(training_items.copy_type(source))
        with patch.object(combat.Fighter,'schedule_action') as schedule:
            g.clone.combat.use_heal(dict(obj=inventory.oid_of(row)),inventory.USE_IDLE)
            self.assertTrue(schedule.called)
            args=schedule.call_args.args
        self.assertFalse(g.clone.training_effects.active)
        self.assertEqual(g.store.item(row['uniq'])['use_count'],row['use_count'])
        args[4](*args[5:])
        self.assertTrue(g.clone.training_effects.active)
        self.unchanged()

    async def test_buff_refused_after_target_moves_out_of_reach_without_losing_dose(self):
        g=self.enter()
        source=next(t for t,d in effects.definitions().items() if d['bonuses']['hp'])
        row=g.clone.inv.create(training_items.copy_type(source))
        g.start('fighter')
        target=g.enemy.combat
        before=dict(g.store.item(row['uniq']))
        effects.activate(g.clone.combat,row['uniq'],target,0)
        self.assertEqual(dict(g.store.item(row['uniq'])),before)
        self.assertFalse(target.sess.training_effects.active)
        self.unchanged()

    async def test_humanoid_uses_A_weapon_of_own_level_and_animals_keep_natural_attack(self):
        g=self.enter()
        source=next(int(t) for t,info in tg.mobs.TYPES.items() if 12<=info.get('level',0)<=17 and info.get('role')=='mob' and info.get('weapon_class') in ('rifle','assault_rifle','pistol') and int(t) in tg.mob_catalogue())
        g.mob_type=source
        original=copy.deepcopy(tg.mobs.stats(source).__dict__)
        g.start('mob')
        mob=g.room.combat.mobs[g.mob_eid]
        self.assertTrue(hasattr(mob,'training_weapon'))
        gun_source=training_items.source_type(mob.stats.weapon_type_id)
        self.assertEqual(balance.line(gun_source),'A')
        self.assertLessEqual(inventory.item_level(gun_source),mob.level)
        self.assertGreater(inventory.item_level(gun_source),1)
        self.assertEqual(mob.stats.attack_ap,items.params_of(mob.stats.weapon_type_id)['fire_costs'][0])
        self.assertEqual(tg.mobs.stats(source).__dict__,original)
        self.unchanged()


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingV2)
