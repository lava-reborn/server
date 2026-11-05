"""Execute committed-animation input guards and cleanup as emitted AVM1."""
import unittest

import test_combat_client as fixture
from avm_test import Arr
from testkit import run_cases


class ActionRecoveryClient(unittest.TestCase):
    def setUp(self):
        self.fx=fixture.CombatClient()
        self.fx.setUp()
        self.now=100
        self.timers=[]
        self.cleared=[]
        self.executed=[]
        self.location={}
        self.master=dict(currentLocation=self.location,gamer=dict(acManager=dict(
            autoFireTargetDead=lambda: self.executed.append('stop-auto'))))
        self.fx.env['getTimer']=lambda:self.now
        self.fx.env['setInterval']=lambda callback,delay:self.timers.append((callback,delay)) or len(self.timers)
        self.fx.env['clearInterval']=self.cleared.append
        self.fx.env['lol']['core']['Master']=dict(getInstance=lambda:self.master)
        self.global_=self.fx.env['_global']
        for function in self.fx.functions.values():
            function.closure.update(self.fx.env)

    def call(self,name,target,*args):
        return self.fx.call(name,target,*args)

    def test_stale_burst_in_standing_animation_does_not_block_weapon_switch(self):
        scene,figure=self.fx.scene()
        figure.update(id=0,animationEnabled=True,isActive=True,onEnterFrame=True,
                      behavior='stand',currentFrameNumber=0,
                      __bfBursts=Arr([dict(got=1,events=Arr())]),__bfScene=scene)
        self.global_['__bfOwnerFigure']=figure
        self.global_['__bfRecoveryUntil']=99
        owner=dict(__bfRequestSwapOrig=lambda:self.executed.append('swap'))
        self.call('__bfRequest8',owner)
        self.assertEqual(self.executed,['stop-auto','swap'])
        self.assertEqual(self.timers,[])
        self.assertEqual(figure['__bfBursts'],[])
        # Next attack must start its own visual, rather than queue behind a ghost.
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=2))
        self.assertEqual(self.fx.calls[-1],('aim',2))

    def test_gameplay_receiver_arms_recovery_before_auto_fire_even_without_outer_hook(self):
        owner=dict(__bfRequestSwapOrig=lambda:self.executed.append('swap'))
        location=dict(__bfLocationShotOrig=lambda event:self.call('__bfRequest8',owner))
        self.call('__bfLocationShot',location,dict(param=dict(id=0,status=0,recovery_ms=360)))
        self.assertNotIn('swap',self.executed)
        self.assertEqual(self.global_['__bfRecoveryUntil'],460)
        self.now=460
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('swap'),1)

    def test_weapon_switch_stops_repeat_fire_before_native_swap(self):
        owner=dict(__bfRequestSwapOrig=lambda:self.executed.append('swap'))
        self.call('__bfRequest8',owner)
        self.assertEqual(self.executed,['stop-auto','swap'])
        self.assertEqual(self.timers,[])

    def test_weapon_switch_during_committed_shot_waits_and_replaces_queued_fire(self):
        self.global_['__bfRecoveryUntil']=500
        fire=dict(__bfRequestFireOrig=lambda a,b:self.executed.append('fire'))
        swap=dict(__bfRequestSwapOrig=lambda:self.executed.append('swap'))
        self.call('__bfRequest1',fire,1,42)
        self.call('__bfRequest8',swap)
        self.assertNotIn('swap',self.executed)
        self.now=500
        self.call('__bfDrainInput',None)
        self.assertNotIn('fire',self.executed)
        self.assertEqual(self.executed.count('swap'),1)

    def test_last_move_runs_on_final_firing_frame_without_waiting_for_fire_out(self):
        scene,figure=self.fx.scene()
        figure.update(id=0,behavior='fire',animationEnabled=True,isActive=True,
                      onEnterFrame=True,__bfScene=scene)
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=1))
        self.call('__bfRecovery',None,dict(param=dict(id=0,recovery_ms=120)))
        owner=dict(__bfRequestMoveOrig=lambda c,splice:self.executed.append(c))
        self.call('__bfRequest0',owner,'first',None)
        self.call('__bfRequest0',owner,'last',None)
        self.assertEqual(len(self.timers),1)
        self.now=219
        self.call('__bfDrainInput',None)
        self.assertNotIn('last',self.executed)
        self.now=220
        self.call('__bfDrainInput',None)
        self.assertNotIn('last',self.executed)
        # Actual firing is slower than the nominal server floor. Only its
        # final frame releases the command; lowering does not add a wait.
        self.now=240
        figure['__bfNextSequenceOrig']=lambda:figure.update(behavior='fire_out')
        self.call('__bfNextSequence',figure)
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('last'),1)
        self.assertNotIn('first',self.executed)
        self.assertEqual(self.fx.applied,[])
        self.assertEqual(self.fx.reported,[1])
        self.assertEqual(figure['__bfBursts'],[])
        self.assertIsNone(self.global_['__bfInputTimer'])

    def test_move_sent_before_shot_notice_is_retried_once_after_native_refusal(self):
        owner=self.location
        owner['__bfRequestMoveOrig']=lambda cell,splice:self.executed.append(('request',cell))
        owner['__bfRetryMoveOrig']=lambda event:self.executed.append('consume-old-callback')
        self.call('__bfRequest0',owner,10,None)
        self.call('__bfRequest0',owner,20,None)
        conn=dict(__bfRecoveryNotifyOrig=lambda cmd:
                  self.call('__bfRetryMove',owner,dict(param=cmd['params'])))
        packet=dict(messID='breakMv',params=dict(id=0,pos=5,recovery_ms=120))
        self.call('__bfRecoveryNotify',conn,packet)
        self.call('__bfRecoveryNotify',conn,packet)
        self.assertEqual(len(self.timers),1)
        self.now=219
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count(('request',20)),1)
        self.now=220
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count(('request',10)),1)
        self.assertEqual(self.executed.count(('request',20)),2)
        self.assertLess(self.executed.index('consume-old-callback'),
                        len(self.executed)-1)

    def test_shot_boundary_retry_does_not_restore_a_move_replaced_by_heal(self):
        owner=self.location
        owner['__bfRequestMoveOrig']=lambda cell,splice:self.executed.append('move')
        owner['__bfRetryMoveOrig']=lambda event:None
        self.call('__bfRequest0',owner,10,None)
        self.global_['__bfRecoveryUntil']=220
        heal=dict(__bfRequestHealOrig=lambda med:self.executed.append('heal'))
        self.call('__bfRequest4',heal,'med')
        self.call('__bfRetryMove',owner,dict(param=dict(id=0,recovery_ms=120)))
        self.now=220
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('move'),1)
        self.assertEqual(self.executed.count('heal'),1)

    def test_wall_refusal_never_retries_and_location_cleanup_discards_intent(self):
        owner=self.location
        owner['__bfRequestMoveOrig']=lambda cell,splice:self.executed.append('move')
        owner['__bfRetryMoveOrig']=lambda event:None
        self.call('__bfRequest0',owner,10,None)
        self.call('__bfRetryMove',owner,dict(param=dict(id=0,pos=5)))
        self.assertEqual(self.timers,[])
        self.call('__bfClearInput',None)
        self.assertIsNone(self.global_['__bfMoveIntent'])

    def test_clicks_during_shot_keep_latest_destination_and_rebuild_at_execution(self):
        state=dict(cell=10)
        owner=dict(__bfRequestMoveOrig=lambda cell,splice:
                   self.executed.append((state['cell'],cell,splice)))
        self.global_['__bfRecoveryUntil']=500
        for target in range(20,40):
            self.call('__bfRequest0',owner,target,False)
        self.assertEqual(len(self.timers),1)
        self.assertFalse(any(isinstance(x,tuple) for x in self.executed))
        # Authoritative state may update while the committed animation finishes.
        state['cell']=11
        self.now=500
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        moves=[x for x in self.executed if isinstance(x,tuple)]
        self.assertEqual(moves,[(11,39,False)])
        self.assertIsNone(self.global_['__bfInputTimer'])
        # Subsequent rerouting uses the unchanged native entry point immediately.
        self.call('__bfRequest0',owner,50,True)
        self.assertEqual(self.executed[-1],(11,50,True))
        self.assertEqual(len(self.timers),1)

    def test_recovery_is_seen_before_native_auto_fire_listener(self):
        activator=dict(__bfRequestFireOrig=lambda a,b:self.executed.append('fire'))
        connection=dict(__bfRecoveryNotifyOrig=lambda cmd:self.call('__bfRequest1',activator,1,42))
        self.call('__bfRecoveryNotify',connection,dict(messID='faShot',params=dict(id=0,status=0,recovery_ms=440)))
        self.assertNotIn('fire',self.executed)
        self.assertEqual(self.global_['__bfRecoveryUntil'],540)
        self.now=540
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed,['fire'])

    def test_enemy_recovery_does_not_block_own_commands(self):
        connection=dict(__bfRecoveryNotifyOrig=lambda cmd:None)
        self.call('__bfRecoveryNotify',connection,dict(messID='caHit',params=dict(id=123,recovery_ms=440)))
        owner=dict(__bfRequestMoveOrig=lambda a,b:self.executed.append('move'))
        self.call('__bfRequest0',owner,'cell',None)
        self.assertEqual(self.executed,['stop-auto','move'])
        self.assertEqual(self.timers,[])

    def test_clan_hit_keeps_native_damage_but_does_not_start_or_refresh_exit_timer(self):
        panel=dict(__bfExitTimerOrig=lambda:self.executed.append('timer'))
        def hit(cmd):
            self.executed.append('native-hit')
            self.call('__bfExitTimer',panel)
        connection=dict(__bfRecoveryNotifyOrig=hit)
        for kind in ('faHit','caHit'):
            self.call('__bfRecoveryNotify',connection,dict(messID=kind,params=dict(no_war=1)))
        self.assertEqual(self.executed,['native-hit','native-hit'])
        self.call('__bfRecoveryNotify',connection,dict(messID='faHit',params={}))
        self.assertEqual(self.executed[-2:],['native-hit','timer'])
        self.call('__bfExitTimer',panel)
        self.assertEqual(self.executed[-1],'timer')

    def test_location_change_discards_pending_input_and_timer(self):
        self.global_['__bfRecoveryUntil']=500
        owner=dict(__bfRequestMoveOrig=lambda a,b:self.executed.append('move'))
        self.call('__bfRequest0',owner,'cell',None)
        self.master['currentLocation']={"new":True}
        self.now=600
        self.call('__bfDrainInput',None)
        self.assertNotIn('move',self.executed)
        self.assertIsNone(self.global_['__bfPendingInput'])
        self.assertIsNone(self.global_['__bfInputTimer'])

    def test_native_transition_cannot_remove_next_attack_animation(self):
        scene,figure=self.fx.scene()
        def native_aim(obj):
            figure.update(next=None,onEnterFrame='play',behavior='fire_in')
        scene['__bfAimOrig']=native_aim
        figure['__bfNextSequenceOrig']=lambda:figure.update(onEnterFrame=None,behavior='stand')
        for i in (1,2):
            self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=i))
            self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=i))
        figure['burstArr'].shift()
        figure['next']='stand'
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertTrue(figure['__bfAdvanceReady'])
        self.call('__bfNextSequence',figure)
        self.assertEqual(figure['onEnterFrame'],'play')
        self.assertEqual(figure['behavior'],'fire_in')
        self.assertFalse(figure['__bfAdvanceReady'])

    def test_disabled_model_animation_does_not_wait_for_missing_final_frame(self):
        scene,figure=self.fx.scene()
        figure.update(animationEnabled=False,isActive=True)
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=1))
        self.assertEqual(self.fx.applied,[1])
        self.assertFalse(figure.get('__bfBursts'))
        self.assertFalse(self.call('__bfWaiting',None))

    def test_fire_out_stand_and_disabled_rendering_do_not_hold_finished_attack(self):
        _,figure=self.fx.scene()
        figure.update(animationEnabled=True,isActive=True,onEnterFrame=True,
                      behavior='fire',__bfBursts=Arr([dict(got=1)]))
        self.global_['__bfOwnerFigure']=figure
        self.global_['__bfRecoveryUntil']=100
        self.assertTrue(self.call('__bfWaiting',None))
        for behavior in ('fire_out','stand','run'):
            figure['behavior']=behavior
            self.assertFalse(self.call('__bfWaiting',None))
        figure['behavior']='fire'
        figure['animationEnabled']=False
        self.assertFalse(self.call('__bfWaiting',None))

    def test_fire_heal_and_swap_run_once_on_firing_completion_without_reclick(self):
        for wrapper,method,args,label in (
            ('__bfRequest1','__bfRequestFireOrig',(1,42),'fire-next'),
            ('__bfRequest4','__bfRequestHealOrig',('med',),'heal'),
            ('__bfRequest8','__bfRequestSwapOrig',(),'swap')):
            with self.subTest(action=label):
                self.call('__bfClearInput',None)
                scene,figure=self.fx.scene()
                figure.update(id=0,behavior='fire',animationEnabled=True,isActive=True,
                              onEnterFrame=True,__bfScene=scene,
                              __bfBursts=Arr([dict(got=1,events=Arr())]))
                self.global_['__bfOwnerFigure']=figure
                self.global_['__bfRecoveryUntil']=200
                owner={method:lambda *a:self.executed.append(label)}
                self.now=100
                self.call(wrapper,owner,*args)
                self.now=200
                self.call('__bfDrainInput',None)
                self.assertNotIn(label,self.executed)
                figure['__bfNextSequenceOrig']=lambda:figure.update(behavior='fire_out')
                self.call('__bfNextSequence',figure)
                self.call('__bfDrainInput',None)
                self.assertEqual(self.executed.count(label),1)
                self.assertIsNone(self.global_['__bfPendingInput'])
                self.assertIsNone(self.global_['__bfInputTimer'])

    def test_authoritative_stop_keeps_actual_position_without_cutting_shot(self):
        scene,figure=self.fx.scene()
        figure.update(__bfBursts=Arr([dict(got=1)]),behavior='fire')
        scene['__bfFinishMoveOrig']=lambda e:figure.update(behavior='stand')
        scene['__bfPositionOrig']=lambda e:figure.update(behavior='run')
        scene['placeWalker']=lambda f,x,y:f.update(_x=x,_y=y)
        event=dict(walker=dict(id=0,x=40,y=50))
        self.call('__bfPosition',scene,event)
        self.call('__bfFinishMove',scene,event)
        self.assertEqual(figure['behavior'],'fire')
        self.assertEqual((figure['_x'],figure['_y']),(40,50))
        figure['__bfBursts']=Arr()
        self.call('__bfPosition',scene,event)
        self.assertEqual(figure['behavior'],'run')
        self.call('__bfFinishMove',scene,event)
        self.assertEqual(figure['behavior'],'stand')

    def test_stop_after_swap_preserves_holster_and_draw_without_blocking_new_walk(self):
        for phase in ('arm_out','arm_in'):
            with self.subTest(phase=phase):
                scene,figure=self.fx.scene()
                figure.update(behavior=phase)
                scene['__bfFinishMoveOrig']=lambda e:figure.update(behavior='stand')
                scene['__bfPositionOrig']=lambda e:figure.update(behavior='run')
                scene['placeWalker']=lambda f,x,y:f.update(_x=x,_y=y)
                walker=dict(id=0,x=40,y=50)
                event=dict(walker=walker)
                def stop(pos):
                    walker.update(x=pos,y=50)
                    self.call('__bfPosition',scene,event)
                    self.call('__bfFinishMove',scene,event)
                walker['__bfStopMoveOrig']=stop
                self.call('__bfBreakMove',walker,60)
                self.assertEqual(figure['behavior'],phase)
                self.assertEqual((figure['_x'],figure['_y']),(60,50))
                self.assertFalse(walker['__bfStoppingMove'])
                # A real new step is allowed to replace the weapon animation.
                self.call('__bfPosition',scene,event)
                self.assertEqual(figure['behavior'],'run')
                self.call('__bfFinishMove',scene,event)
                self.assertEqual(figure['behavior'],'stand')

    def panel(self):
        equip=dict(transferStack=Arr())
        panel=dict(equipment=equip,changeFlag=True)
        def native():
            if panel['changeFlag']:
                panel['changeFlag']=False
                equip['transferStack'].push('pending')
                self.executed.append('swap-sent')
        panel['__bfPanelSwapOrig']=native
        panel['changeWeapon']=lambda:self.call('__bfPanelSwap',panel)
        return panel,equip

    def test_panel_swap_queues_before_lock_then_allows_later_swaps_and_refusal_retry(self):
        panel,equip=self.panel()
        self.global_['__bfRecoveryUntil']=200
        self.call('__bfPanelSwap',panel)
        self.assertTrue(panel['changeFlag'])
        self.assertEqual(equip['transferStack'],[])
        self.now=200
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('swap-sent'),1)
        self.call('__bfPanelSwap',panel)
        self.assertEqual(self.executed.count('swap-sent'),1) # in-flight guard
        for success in (True,False,True):
            equip['transferStack'].shift()
            if success:
                panel['changeFlag']=True # native changePrimary event
            self.call('__bfPanelSwap',panel)
        self.assertEqual(self.executed.count('swap-sent'),4)

    def test_replaced_swap_never_leaves_native_panel_locked(self):
        panel,equip=self.panel()
        self.global_['__bfRecoveryUntil']=200
        self.call('__bfPanelSwap',panel)
        owner=dict(__bfRequestMoveOrig=lambda *args:self.executed.append('move'))
        self.call('__bfRequest0',owner,'hex',None)
        self.now=200
        self.call('__bfDrainInput',None)
        self.assertNotIn('swap-sent',self.executed)
        self.assertTrue(panel['changeFlag'])
        self.call('__bfPanelSwap',panel)
        self.assertEqual(self.executed.count('swap-sent'),1)

    def test_equipment_actions_defer_before_registering_ack_or_ui_side_effects(self):
        for index,method,args in (
                (9,'__bfEquipLoadOrig',('gun','ammo')),
                (10,'__bfEquipUnloadOrig',('gun',)),
                (11,'__bfEquipModeOrig',(1,)),
                (12,'__bfEquipHealOrig',()),
                (13,'__bfEquipEatOrig',())):
            with self.subTest(action=method):
                self.call('__bfClearInput',None)
                self.now=100
                self.global_['__bfRecoveryUntil']=200
                effects=[]
                owner={method:lambda *a:effects.append(('ack/UI',a))}
                self.call('__bfRequest'+str(index),owner,*args)
                self.assertEqual(effects,[])
                self.now=200
                self.call('__bfDrainInput',None)
                self.call('__bfDrainInput',None)
                self.assertEqual(effects,[('ack/UI',args)])
                self.call('__bfRequest'+str(index),owner,*args)
                self.assertEqual(len(effects),2)

    def test_replaced_reload_unload_or_mode_cannot_consume_healing_ack(self):
        for index,method,args in (
                (9,'__bfEquipLoadOrig',('gun','ammo')),
                (10,'__bfEquipUnloadOrig',('gun',)),
                (11,'__bfEquipModeOrig',(1,))):
            self.call('__bfClearInput',None)
            self.now=100
            self.global_['__bfRecoveryUntil']=200
            listeners=[]
            owner={method:lambda *a:listeners.append(method)}
            self.call('__bfRequest'+str(index),owner,*args)
            healer=dict(__bfEquipHealOrig=lambda:listeners.append('heal'))
            self.call('__bfRequest12',healer)
            self.now=200
            self.call('__bfDrainInput',None)
            self.assertEqual(listeners,['heal'])
            self.assertIsNone(self.global_['__bfPendingInput'])
            self.assertIsNone(self.global_['__bfInputTimer'])

    def test_taking_damage_preserves_committed_shot_but_not_death(self):
        scene,figure=self.fx.scene()
        figure.update(__bfBursts=Arr([dict(got=1)]),behavior='fire',_x=20,_y=100)
        scene['__bfHitTargetOrig']=lambda event:self.executed.append('damage-animation')
        result=self.call('__bfHitTarget',scene,dict(targetID=0))
        self.assertEqual(result,dict(x=20,y=50))
        self.assertNotIn('damage-animation',self.executed)
        self.global_['__bfRecoveryUntil']=500
        self.global_['__bfPendingInput']=dict(owner={},method='unused')
        figure['__bfBursts']=Arr()
        self.call('__bfDead',scene,dict(dead=0))
        self.assertEqual(self.global_['__bfRecoveryUntil'],0)
        self.assertIsNone(self.global_['__bfPendingInput'])


if __name__=='__main__':
    run_cases(ActionRecoveryClient)
