"""Cancellation before completion; committed attack recovery after completion."""
from types import SimpleNamespace as NS
import unittest
import math
from unittest.mock import patch

import action_animation
import combat
import inventory
import items
import test_release_battle as battle_fixtures
from testkit import run_cases


class ActionRecovery(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case=battle_fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.a,self.b,_=self.case.players
        self.b.pos=5
        self.gun=self.a.inv.create(25566,slot=inventory.PRIMARY)
        self.a.inv.look = 0
        self.ammo=items.params_of(25566)['comp_array'][0]
        self.case.store.update_item(self.gun['uniq'],ammo_count=8,ammo_type=self.ammo)

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def start_shot(self):
        with self.case.at(100):
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun),target='1%08x'%self.b.pid))
        timer=self.a.combat.aim
        self.assertIsNotNone(timer)
        callback,args,when=timer._callback,timer._args,timer.when()
        return timer,callback,args,when

    def complete_shot(self):
        timer,callback,args,when=self.start_shot()
        timer.cancel()
        with self.case.at(when):
            callback(*args)
        return callback,args,when

    async def test_aim_can_be_cancelled_by_movement_without_spending_rounds(self):
        timer,callback,args,when=self.start_shot()
        with self.case.at(100.1):
            self.a.move_in_location(dict(path=[0,1]))
            self.assertTrue(timer.cancelled())
            callback(*args)
            self.assertFalse(combat.Fighter.recovering(self.a.combat))
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],8)
        self.assertIsNotNone(self.a.walk)

    async def test_accepted_weapon_swap_cancels_aim_even_after_switching_back(self):
        other=self.a.inv.create(25566,slot=inventory.SECONDARY)
        timer,callback,args,when=self.start_shot()
        before_ap=self.a.combat.ap
        before_hp=self.b.character().hp
        with self.case.at(100.1):
            self.a.inv.ss_move(dict(obj=inventory.oid_of(self.gun),
                                   **{'from':inventory.PRIMARY,'to':inventory.SECONDARY}))
            self.assertTrue(timer.cancelled())
            self.assertIsNone(self.a.combat.aim)
            self.a.inv.ss_move(dict(obj=inventory.oid_of(self.gun),
                                   **{'from':inventory.SECONDARY,'to':inventory.PRIMARY}))
        with self.case.at(when):
            callback(*args)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],8)
        self.assertEqual(self.a.combat.ap,before_ap)
        self.assertEqual(self.b.character().hp,before_hp)
        self.assertFalse(any(n=='faShot' for n,p in self.a.writer.frames))
        for seat in (self.a,self.b):
            self.assertTrue(any(n=='actionCancel' and p.get('stop_aim')
                                for n,p in seat.writer.frames))

    async def test_committed_shot_rejects_next_attack_without_refunding_or_repeating_it(self):
        callback,args,when=self.complete_shot()
        expected=action_animation.duration_ms(self.a,items.params_of(25566),1,
                                              aimed_for=items.params_of(25566)["fire_times"][0]/1000)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)
        ends=self.a.combat.recovery_until
        self.assertAlmostEqual(ends,when+expected/1000)
        medicine=self.a.inv.create(6055)
        with self.case.at(when+.01):
            self.a.writer.frames.clear()
            self.a.handle('moveTo', dict(path=[0,1]))
            self.assertIsNotNone(self.a.walk)
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun),target='1%08x'%self.b.pid))
            self.a.combat.use_heal(dict(obj=inventory.oid_of(medicine)),inventory.USE_IDLE)
            self.assertIsNone(self.a.combat.aim)
            self.assertIsNone(self.a.combat.healing)
            self.assertFalse(any(name == 'breakMv' for name, _p in self.a.writer.frames))
            acknowledgements=[p for n,p in self.a.writer.frames if n=='cmdAck']
            self.assertEqual([p['res'] for p in acknowledgements],
                             [inventory.RES_OK, inventory.RES_NOT_READY, inventory.RES_NOT_READY])
            callback(*args)  # Replayed completion is inert, including its recovery.
            self.assertEqual(self.a.combat.recovery_until,ends)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)
        self.assertIsNotNone(self.case.store.item(medicine['uniq']))
        with self.case.at(ends+1e-6):
            here = self.a.live_cell()
            self.a.move_in_location(dict(path=[here, here+1]))
            self.assertIsNotNone(self.a.walk)

    async def test_next_aim_waits_for_animation_then_starts_its_full_aim_time(self):
        _, _, when = self.complete_shot()
        ends = self.a.combat.recovery_until
        request = dict(type=inventory.USE_FIRE, obj=inventory.oid_of(self.gun),
                       target='1%08x' % self.b.pid)
        before = self.case.store.item(self.gun['uniq'])
        for stamp in (when, ends - .001):
            with self.case.at(stamp):
                self.a.handle('ss_use', request)
                self.assertIsNone(self.a.combat.aim)
                self.assertEqual(self.case.store.item(self.gun['uniq']), before)
        with self.case.at(ends):
            self.a.handle('ss_use', request)
            timer = self.a.combat.aim
            self.assertIsNotNone(timer)
            self.assertAlmostEqual(timer.when() - ends, items.params_of(25566)['fire_times'][0] / 1000)
        with self.case.at(ends + .001):
            self.a.handle('ss_use', dict(request, target='000000006'))
            self.assertIs(self.a.combat.aim, timer)
            self.assertFalse(timer.cancelled())
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'], 7)

    async def test_smg_single_shots_serialize_full_animation_and_new_aim_without_duplicate_costs(self):
        self.case.store.update_item(self.gun['uniq'], slot=inventory.BAG)
        gun = self.a.inv.create(25485, slot=inventory.PRIMARY)
        params = items.params_of(25485)
        self.case.store.update_item(gun['uniq'], ammo_count=10, ammo_type=params['comp_array'][0])
        for spec in self.a.char.spec:
            spec[0] = 5
        request = dict(obj=inventory.oid_of(gun), target='1%08x' % self.b.pid)
        clock = 100.0
        for count in range(3):
            with self.case.at(clock):
                self.a.combat.use_fire(request)
                timer = self.a.combat.aim
                self.assertIsNotNone(timer)
                deadline = timer.when()
                self.assertAlmostEqual(deadline - clock, params['fire_times'][0] / 1000)
                for _ in range(50):
                    self.a.combat.use_fire(request)
                    self.assertIs(self.a.combat.aim, timer)
            callback, args = timer._callback, timer._args
            timer.cancel()
            with self.case.at(deadline):
                callback(*args)
                callback(*args)
                self.assertEqual(self.case.store.item(gun['uniq'])['ammo_count'], 9 - count)
                before = self.case.store.item(gun['uniq'])
                self.a.combat.use_fire(request)
                self.assertIsNone(self.a.combat.aim)
                self.assertEqual(self.case.store.item(gun['uniq']), before)
            clock = self.a.combat.recovery_until
        for viewer in (self.a, self.b):
            shots = [p for name, p in viewer.writer.frames if name == 'faShot']
            self.assertEqual([p['status'] for p in shots], [1, 0] * 3)

    async def test_every_firearm_class_and_mode_waits_without_cancelling_the_current_burst(self):
        self.case.store.update_item(self.gun['uniq'], slot=inventory.BAG)
        self.a.char.set_skill(combat.progression.SHOOTING, 17)
        for spec in self.a.char.spec:
            spec[0] = 5
        # Pistol, shotgun, assault rifle, rifle, machine gun, SMG.
        types = (25566, 25943, 25201, 25803, 24990, 25485)
        self.assertEqual({items.params_of(t)['weapon_type'] for t in types}, set(range(6)))
        clock = 100.0
        for type_id in types:
            gun = self.a.inv.create(type_id, slot=inventory.PRIMARY)
            params = items.params_of(type_id)
            for mode, shots in enumerate(params['fire_mods']):
                if not shots:
                    continue
                for rounds in (1, max(1, shots)):
                    self.case.store.update_item(gun['uniq'], cur_mode=mode, ammo_count=rounds,
                                               ammo_type=params['comp_array'][0])
                    request = dict(obj=inventory.oid_of(gun), target='00000018f')
                    with self.case.at(clock):
                        self.a.combat.ap = 200
                        self.a.combat.use_fire(request)
                        timer = self.a.combat.aim
                        self.assertIsNotNone(timer, (type_id, mode, rounds))
                        for _ in range(5):
                            self.a.combat.use_fire(dict(request, target='00000018e'))
                            self.assertIs(self.a.combat.aim, timer)
                        callback, args, deadline = timer._callback, timer._args, timer.when()
                        timer.cancel()
                    with self.case.at(deadline):
                        callback(*args)
                        before = dict(self.case.store.item(gun['uniq']))
                        previous_end = self.a.combat.recovery_until
                        cycles = 1 if params['weapon_type'] == items.SHOTGUN else args[3].num_shots
                        self.assertAlmostEqual(previous_end - deadline, max(.150, cycles * .030))
                        self.a.combat.use_fire(request)
                        callback(*args)
                        self.assertIsNone(self.a.combat.aim)
                        self.assertEqual(self.a.combat.recovery_until, previous_end)
                        self.assertEqual(self.case.store.item(gun['uniq']), before)
                    clock = previous_end
            self.case.store.update_item(gun['uniq'], slot=inventory.BAG)

    async def test_fist_waits_for_its_complete_animation_without_charging_a_second_hit(self):
        self.b.pos = 1
        request = dict(obj='0', target='1%08x' % self.b.pid)
        with self.case.at(100):
            self.a.combat.use_fire(request)
            self.assertTrue(combat.Fighter.recovering(self.a.combat))
            self.a.combat.use_fire(request)
            self.a.move_in_location(dict(path=[0, 20]))
        self.assertIsNotNone(self.a.walk)
        result = [p for n, p in self.a.writer.frames if n in ('caHit', 'caMiss')]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['recovery_ms'], action_animation.duration_ms(self.a))
        self.assertEqual(self.a.combat.ap, 195)

    async def test_blade_restores_840ms_cycle_without_replaying_damage_or_costs(self):
        self.case.store.update_item(self.gun['uniq'], slot=inventory.BAG)
        self.a.char.set_skill(combat.progression.MELEE, 17)
        self.a.char.set_spec(1, 3)
        blade = self.a.inv.create(6241, slot=inventory.PRIMARY)
        self.b.pos = 1
        request = dict(obj=inventory.oid_of(blade), target='1%08x' % self.b.pid)
        clock = 100.0
        for _ in range(2):
            with self.case.at(clock):
                self.a.combat.use_fire(request)
                timer = self.a.combat.strike
                self.assertIsNotNone(timer)
                self.assertAlmostEqual(timer.when() - clock, .600)
                callback, args, deadline = timer._callback, timer._args, timer.when()
                before = self.a.combat.ap
                worn = self.case.store.item(blade['uniq'])['brk']
                for _press in range(50):
                    self.a.combat.use_fire(request)
                    self.assertIs(self.a.combat.strike, timer)
                    self.assertEqual(timer.when(), deadline)
            timer.cancel()
            with self.case.at(deadline), patch.object(combat, 'roll', return_value=True):
                callback(*args)
                callback(*args)  # a duplicate callback must not double-charge
                self.assertIsNone(self.a.combat.strike)
                self.assertTrue(combat.Fighter.recovering(self.a.combat))
                self.a.combat.use_fire(request)
                self.assertIsNone(self.a.combat.strike)
            self.assertEqual(self.a.combat.ap, before - 8)
            self.assertEqual(self.case.store.item(blade['uniq'])['brk'], worn - 1)
            clock = self.a.combat.recovery_until
            self.assertAlmostEqual(clock - deadline, .240)
            with self.case.at(clock - .001):
                self.a.combat.use_fire(request)
                self.assertIsNone(self.a.combat.strike)
        impacts = [p for n, p in self.a.writer.frames if n == 'caHit' and p['id'] == 0]
        self.assertEqual(len(impacts), 2)

    async def test_recovery_guards_first_packet_and_final_packet_carries_playback_budget(self):
        self.complete_shot()
        for seat in (self.a,self.b):
            packets=[p for n,p in seat.writer.frames if n=='faShot']
            marked=[p for p in packets if p.get('recovery_ms')]
            self.assertEqual(marked, [packets[0], packets[-1]])
            self.assertEqual([p['status'] for p in marked], [1, 0])
            self.assertEqual([p['recovery_ms'] for p in marked], [150, 150])
            self.assertEqual([p['id'] for p in marked], [0 if seat is self.a else self.a.pid] * 2)
            self.assertNotIn('animation_frames', packets[0])
            self.assertEqual(packets[-1]['animation_frames'],
                             action_animation.frame_counts(self.a, items.params_of(25566), 1)[1])

    async def test_mode_change_during_aim_only_changes_the_next_shot(self):
        params = items.params_of(25566)
        self.case.store.update_item(self.gun['uniq'], cur_mode=2)
        timer, callback, args, when = self.start_shot()
        self.assertAlmostEqual(when - 100, params['fire_times'][2] / 1000)
        self.case.store.update_item(self.gun['uniq'], cur_mode=0)
        self.assertFalse(timer.cancelled())
        timer.cancel()
        with self.case.at(when):
            callback(*args)
        expected = 150
        self.assertAlmostEqual(self.a.combat.recovery_until, when + expected / 1000)
        packets = [p for n,p in self.a.writer.frames if n == 'faShot' and p.get('recovery_ms')]
        self.assertEqual([p['recovery_ms'] for p in packets], [expected, expected])
        ends = self.a.combat.recovery_until
        with self.case.at(ends):
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun), target='00000018f'))
            self.assertIsNotNone(self.a.combat.aim)
            self.assertAlmostEqual(self.a.combat.aim.when() - ends,
                                   params['fire_times'][0] / 1000)

    async def test_healing_and_reload_remain_cancellable_before_timer(self):
        for kind in ('heal','reload'):
            with self.subTest(kind=kind):
                self.a.pos=0
                medicine=self.a.inv.create(6055)
                stack=self.a.inv.create(self.ammo,30)
                self.case.store.update_item(self.gun['uniq'],ammo_count=0)
                with self.case.at(100):
                    if kind=='heal':
                        self.a.combat.use_heal(dict(obj=inventory.oid_of(medicine)),inventory.USE_IDLE)
                        timer=self.a.combat.healing
                    else:
                        self.a.inv.use_load(dict(obj=inventory.oid_of(self.gun),target=inventory.oid_of(stack)))
                        timer=self.a.combat.reloading
                    self.assertIsNotNone(timer)
                    callback,args=timer._callback,timer._args
                old_med=dict(self.case.store.item(medicine['uniq']))
                old_ammo=dict(self.case.store.item(stack['uniq']))
                with self.case.at(100.1):
                    self.a.move_in_location(dict(path=[0,1]))
                    self.assertTrue(timer.cancelled())
                    callback(*args)
                    self.assertFalse(combat.Fighter.recovering(self.a.combat))
                self.assertEqual(dict(self.case.store.item(medicine['uniq'])),old_med)
                self.assertEqual(dict(self.case.store.item(stack['uniq'])),old_ammo)
                self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],0)

    async def test_death_or_location_departure_clears_committed_stage(self):
        self.complete_shot()
        with self.case.at(100.51):
            self.a.combat.left()
            self.assertFalse(combat.Fighter.recovering(self.a.combat))
            self.a.combat.recovery_until=200
            self.a.combat.die(self.b.combat)
            self.assertEqual(self.a.combat.recovery_until,0)

    async def test_firearm_pause_uses_a_quarter_of_firing_frames_for_all_models_and_modes(self):
        data = action_animation.sequences()
        for type_id in (25566, 25943, 25218, 25772, 24990, 26177):
            params = items.params_of(type_id)
            kind = 'pistol' if params['weapon_type'] == items.PISTOL else 'rifle'
            for mode, shots in enumerate(params['fire_mods']):
                if not shots:
                    continue
                for look, model in data['models'].items():
                    seat = NS(inv=NS(look=look), active={'sex':0})
                    # Outfits change presentation, never the timing reference.
                    sequence = data['models']['0'][kind]
                    for count in (1, shots):
                        cycles = 1 if params['weapon_type'] == items.SHOTGUN else count
                        expected = max(150, math.ceil(sequence['fire'] * cycles * 1000 / data['frame_rate'] * .25))
                        for elapsed in (0, .01, 10):
                            self.assertEqual(action_animation.duration_ms(seat, params, count,
                                             mode=mode, aimed_for=elapsed), expected,
                                             (type_id, mode, look, count, elapsed))
        self.assertEqual(action_animation.duration_ms(self.a, items.params_of(26177), 5, mode=1), 150)
        self.assertEqual(action_animation.duration_ms(self.a, items.params_of(25218), 3, mode=1), 150)

    async def test_every_catalogue_firearm_uses_native_shot_duration_in_each_enabled_mode(self):
        classes = set()
        # The ordinary human model has three fire frames at 25 fps: a quarter
        # is 30 ms per round before the 150 ms floor. Aim/lowering are separate.
        for type_id, (root, _name) in items.catalogue().items():
            if root != items.FIRE_ARM:
                continue
            params = items.params_of(type_id)
            classes.add(params['weapon_type'])
            for mode, shots in enumerate(params['fire_mods']):
                if shots:
                    cycles = 1 if params['weapon_type'] == items.SHOTGUN else shots
                    self.assertEqual(action_animation.duration_ms(
                        self.a, params, shots, mode=mode), max(150, 30 * cycles), (type_id, mode))
        self.assertTrue(set(range(6)) <= classes)
        for kind in range(6):
            cycles = 1 if kind == items.SHOTGUN else 12
            self.assertEqual(action_animation.duration_ms(
                self.a, {'weapon_type':kind}, 12), max(150, 30 * cycles))

    async def test_blades_keep_the_legacy_swing_without_raising_or_lowering(self):
        data = action_animation.sequences()
        blade = items.params_of(6241)
        for look, model in data['models'].items():
            seat = NS(inv=NS(look=look), active={'sex':0})
            sequence = model.get('knife', data['models']['0']['knife'])
            expected = math.ceil(sequence['fire'] * 1000 / data['frame_rate'])
            self.assertEqual(action_animation.duration_ms(seat, blade), expected)
        self.assertEqual(action_animation.duration_ms(self.a, blade), 240)
        self.assertEqual(action_animation.native_duration_ms(self.a, blade), 320)
        self.assertEqual(action_animation.duration_ms(self.a),
                         action_animation.native_duration_ms(self.a))

    async def test_model_recovery_counts_complete_sequences_without_repeated_io_or_sql(self):
        data=action_animation.sequences()
        with patch.object(self.case.store.db,'execute',side_effect=AssertionError('unexpected SQL')), \
                patch.object(action_animation.Path,'read_text',side_effect=AssertionError('repeated IO')):
            for look,model in data['models'].items():
                seat=NS(inv=NS(look=look),active={'sex':0})
                for kind,params in (('fist',None),('knife',{'blade':True}),
                                    ('pistol',{'weapon_type':items.PISTOL}),
                                    ('rifle',{'weapon_type':items.RIFLE})):
                    for count in (1,3,12):
                        cycles=count if kind in ('pistol','rifle') else 1
                        seq=model.get(kind,data['models']['0'][kind])
                        full=(seq['fire_in']+seq['fire']*cycles+seq['fire_out'])*1000/data['frame_rate']
                        delay=action_animation.native_duration_ms(seat,params,count)
                        self.assertGreaterEqual(delay,full-1e-9)
                        self.assertLess(delay,full+1)
            one=action_animation.native_duration_ms(self.a,{'weapon_type':items.SHOTGUN},1)
            self.assertEqual(action_animation.native_duration_ms(self.a,{'weapon_type':items.SHOTGUN},12),one)
            fallback=NS(inv=NS(look='unknown'),active={'sex':0})
            normal=NS(inv=NS(look=0),active={'sex':0})
            self.assertEqual(action_animation.duration_ms(fallback),action_animation.duration_ms(normal))


if __name__=='__main__':
    run_cases(ActionRecovery)
