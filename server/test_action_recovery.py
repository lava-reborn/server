"""Cancellation before completion; committed attack recovery after completion."""
from types import SimpleNamespace as NS
import unittest
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

    async def test_committed_shot_blocks_actions_until_end_of_firing_sequence(self):
        callback,args,when=self.complete_shot()
        expected=action_animation.duration_ms(self.a,items.params_of(25566),1)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)
        ends=self.a.combat.recovery_until
        self.assertAlmostEqual(ends,when+expected/1000)
        medicine=self.a.inv.create(6055)
        with self.case.at(when+.01):
            self.a.writer.frames.clear()
            self.a.move_in_location(dict(path=[0,1]))
            self.assertIsNone(self.a.walk)
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun),target='1%08x'%self.b.pid))
            self.a.combat.use_heal(dict(obj=inventory.oid_of(medicine)),inventory.USE_IDLE)
            self.assertIsNone(self.a.combat.aim)
            self.assertIsNone(self.a.combat.healing)
            self.assertEqual(self.a.writer.frames[0][0],'breakMv')
            retry=self.a.writer.frames[0][1]['recovery_ms']
            self.assertGreater(retry,0)
            self.assertLessEqual(retry,expected)
            acknowledgements=[p for n,p in self.a.writer.frames if n=='cmdAck']
            self.assertEqual([p['res'] for p in acknowledgements],[inventory.RES_NOT_READY]*2)
            callback(*args)  # Replayed completion is inert, including its recovery.
            self.assertEqual(self.a.combat.recovery_until,ends)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)
        self.assertIsNotNone(self.case.store.item(medicine['uniq']))
        with self.case.at(ends+1e-6):
            self.a.move_in_location(dict(path=[0,1]))
        self.assertIsNotNone(self.a.walk)

    async def test_next_aim_is_available_at_animation_threshold_and_not_before(self):
        _,_,when=self.complete_shot()
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)
        delay=action_animation.duration_ms(self.a,items.params_of(25566),1)/1000
        with self.case.at(when+delay-.001):
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun),target='1%08x'%self.b.pid))
            self.assertIsNone(self.a.combat.aim)
        with self.case.at(when+delay):
            self.a.combat.use_fire(dict(obj=inventory.oid_of(self.gun),target='1%08x'%self.b.pid))
            self.assertIsNotNone(self.a.combat.aim)
        self.assertEqual(self.case.store.item(self.gun['uniq'])['ammo_count'],7)

    async def test_melee_completion_has_one_committed_visual_stage(self):
        self.b.pos=1
        with self.case.at(100):
            self.a.combat.use_fire(dict(obj='0',target='1%08x'%self.b.pid))
            self.assertTrue(combat.Fighter.recovering(self.a.combat))
            self.a.move_in_location(dict(path=[0,20]))
        self.assertIsNone(self.a.walk)
        result=[p for n,p in self.a.writer.frames if n in ('caHit','caMiss')]
        self.assertEqual(len(result),1)
        self.assertGreater(result[0]['recovery_ms'],0)
        self.assertEqual(self.a.combat.ap,195)

    async def test_recovery_is_piggybacked_on_final_shot_only_for_both_viewers(self):
        self.complete_shot()
        for seat in (self.a,self.b):
            packets=[p for n,p in seat.writer.frames if n=='faShot']
            marked=[p for p in packets if p.get('recovery_ms')]
            self.assertEqual(len(marked),1)
            self.assertEqual(marked[0]['status'],0)
            self.assertEqual(marked[0]['id'],0 if seat is self.a else self.a.pid)

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

    async def test_model_recovery_counts_firing_frames_only_without_repeated_io_or_sql(self):
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
                        full=seq['fire']*cycles*1000/data['frame_rate']
                        delay=action_animation.duration_ms(seat,params,count)
                        self.assertGreaterEqual(delay,full-1e-9)
                        self.assertLess(delay,full+1)
            one=action_animation.duration_ms(self.a,{'weapon_type':items.SHOTGUN},1)
            self.assertEqual(action_animation.duration_ms(self.a,{'weapon_type':items.SHOTGUN},12),one)
            fallback=NS(inv=NS(look='unknown'),active={'sex':0})
            normal=NS(inv=NS(look=0),active={'sex':0})
            self.assertEqual(action_animation.duration_ms(fallback),action_animation.duration_ms(normal))


if __name__=='__main__':
    run_cases(ActionRecovery)
