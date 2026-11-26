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

    def stalled_shot(self):
        scene,figure=self.fx.scene()
        figure.update(id=0,behavior='fire',currentFrameNumber=0,
                      animationEnabled=True,isActive=True,onEnterFrame=True,
                      __bfScene=scene)
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,shot=True,seq=1))
        self.call('__bfRecovery',None,dict(param=dict(id=0,recovery_ms=120)))
        return scene,figure

    def test_stalled_firing_releases_last_deferred_input_once_after_server_floor(self):
        _,figure=self.stalled_shot()
        owner=dict(__bfRequestHealOrig=lambda cell:self.executed.append(cell))
        self.call('__bfRequest4',owner,'old')
        self.now=800
        self.call('__bfRequest4',owner,'last')
        self.now=1099
        self.call('__bfDrainInput',None)
        self.assertNotIn('last',self.executed)
        self.now=1100
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('last'),1)
        self.assertNotIn('old',self.executed)
        self.assertEqual(figure['__bfBursts'],[])
        self.assertEqual(self.fx.reported,[1])
        self.assertIsNone(self.global_['__bfInputTimer'])

    def test_watchdog_does_not_cut_slow_but_progressing_firing(self):
        _,figure=self.stalled_shot()
        owner=dict(__bfRequestHealOrig=lambda *args:self.executed.append('move'))
        self.call('__bfRequest4',owner,'cell')
        for now,frame in ((900,1),(1700,2),(2500,0),(3300,1)):
            self.now=now
            figure['currentFrameNumber']=frame
            self.call('__bfDrainInput',None)
            self.assertNotIn('move',self.executed)
        figure['__bfNextSequenceOrig']=lambda:figure.update(behavior='stand')
        self.call('__bfNextSequence',figure)
        self.assertEqual(self.executed.count('move'),1)

    def test_stall_timeout_never_bypasses_authoritative_recovery(self):
        self.stalled_shot()
        self.call('__bfRecovery',None,dict(param=dict(id=0,recovery_ms=3000)))
        owner=dict(__bfRequestHealOrig=lambda med:self.executed.append('heal'))
        self.call('__bfRequest4',owner,'med')
        for now in (1100,3099):
            self.now=now
            self.call('__bfDrainInput',None)
            self.assertNotIn('heal',self.executed)
        self.now=3100
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('heal'),1)

    def test_received_bullets_restart_stall_observation(self):
        scene,figure=self.stalled_shot()
        self.call('__bfRequest4',dict(__bfRequestHealOrig=lambda med:self.executed.append('heal')),'med')
        self.now=900
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=2))
        self.call('__bfDrainInput',None)
        self.now=1100
        self.call('__bfDrainInput',None)
        self.assertNotIn('heal',self.executed)
        self.now=1900
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('heal'),1)

    def test_death_and_location_change_discard_stalled_command(self):
        for cleanup in ('death','location'):
            with self.subTest(cleanup=cleanup):
                self.call('__bfClearInput',None)
                self.now=100
                scene,_=self.stalled_shot()
                before=len(self.executed)
                self.call('__bfRequest4',dict(__bfRequestHealOrig=lambda med:self.executed.append('heal')),'med')
                if cleanup=='death':
                    self.call('__bfDead',scene,dict(dead=0))
                else:
                    self.master['currentLocation']={'other':True}
                self.now=5000
                self.call('__bfDrainInput',None)
                self.assertNotIn('heal',self.executed[before:])
                self.assertIsNone(self.global_['__bfPendingInput'])
                self.assertIsNone(self.global_['__bfObservedFigure'])

    def test_new_firing_bundle_gets_its_own_progress_deadline(self):
        scene,figure=self.stalled_shot()
        owner=dict(__bfRequestHealOrig=lambda *args:self.executed.append('move'))
        self.call('__bfRequest4',owner,'cell')
        self.now=1000
        self.call('__bfVisualFlush',None,scene,figure,False)
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=2))
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=2))
        self.call('__bfDrainInput',None)
        self.now=1100
        self.call('__bfDrainInput',None)
        self.assertNotIn('move',self.executed)
        self.now=2000
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('move'),1)
        self.assertIsNone(self.global_['__bfObservedFigure'])

    def test_stall_recovery_keeps_weapon_panel_inflight_guard(self):
        self.stalled_shot()
        panel,equip=self.panel()
        self.call('__bfPanelSwap',panel)
        self.now=1100
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        self.call('__bfPanelSwap',panel)
        self.assertEqual(self.executed.count('swap-sent'),1)
        self.assertEqual(equip['transferStack'],['pending'])
        equip['transferStack'].shift()
        panel['changeFlag']=True
        self.call('__bfPanelSwap',panel)
        self.assertEqual(self.executed.count('swap-sent'),2)

    def test_stall_recovery_does_not_replay_nine_bullets_at_once(self):
        _,figure,sounds,traces,_=self.fx.confirmed_volley(count=9)
        figure.update(id=0,behavior='fire',currentFrameNumber=0,onEnterFrame=True)
        self.global_['__bfOwnerFigure']=figure
        owner=dict(__bfRequestHealOrig=lambda *args:self.executed.append('move'))
        self.call('__bfRequest4',owner,'cell')
        self.now=1100
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('move'),1)
        self.assertEqual(len(traces),1)
        self.assertEqual(len(sounds),1)
        self.assertEqual(len(self.fx.reported),9)
        self.assertEqual(figure['__bfBursts'],[])

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

    def test_weapon_switch_replaces_only_the_queued_next_shot(self):
        self.global_['__bfRecoveryUntil']=500
        fire=dict(__bfRequestFireOrig=lambda a,b:self.executed.append('fire'))
        swap=dict(__bfRequestSwapOrig=lambda:self.executed.append('swap'))
        self.call('__bfRequest1',fire,1,42)
        self.call('__bfRequest8',swap)
        self.assertNotIn('swap',self.executed)
        self.now=500
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed.count('fire'), 0)
        self.assertEqual(self.executed.count('swap'),1)

    def test_deferred_medicine_runs_after_the_complete_attack_sequence(self):
        scene,figure=self.fx.scene()
        figure.update(id=0,behavior='fire',animationEnabled=True,isActive=True,
                      onEnterFrame=True,__bfScene=scene)
        self.call('__bfAim',scene,dict(aim=0,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=0,access=True,seq=1))
        self.call('__bfRecovery',None,dict(param=dict(id=0,recovery_ms=120)))
        owner=dict(__bfRequestHealOrig=lambda c:self.executed.append(c))
        self.call('__bfRequest4',owner,'first')
        self.call('__bfRequest4',owner,'last')
        self.assertEqual(len(self.timers),1)
        self.now=219
        self.call('__bfDrainInput',None)
        self.assertNotIn('last',self.executed)
        self.now=220
        self.call('__bfDrainInput',None)
        self.assertNotIn('last',self.executed)
        # Actual rendering can be slower than the server floor. Finish both
        # firing and lowering before releasing a queued action.
        self.now=240
        figure['__bfNextSequenceOrig']=lambda:figure.update(behavior='stand')
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

    def test_move_after_shot_is_sent_once_immediately_without_timer_or_replay(self):
        state=dict(cell=10)
        owner=dict(__bfRequestMoveOrig=lambda cell,splice:
                   self.executed.append((state['cell'],cell,splice)))
        self.global_['__bfRecoveryUntil']=500
        self.call('__bfRequest0',owner,20,False)
        self.assertEqual([x for x in self.executed if isinstance(x,tuple)], [(10,20,False)])
        self.assertFalse(self.timers)
        state['cell']=11
        self.now=500
        self.call('__bfDrainInput',None)
        self.call('__bfDrainInput',None)
        moves=[x for x in self.executed if isinstance(x,tuple)]
        self.assertEqual(moves,[(10,20,False)])
        self.assertIsNone(self.global_['__bfInputTimer'])
        self.call('__bfRequest0',owner,50,True)
        self.assertEqual(self.executed[-1],(11,50,True))
        self.assertFalse(self.timers)

    def test_auto_fire_waits_for_the_complete_previous_sequence(self):
        activator=dict(__bfRequestFireOrig=lambda a,b:self.executed.append('fire'))
        connection=dict(__bfRecoveryNotifyOrig=lambda cmd:self.call('__bfRequest1',activator,1,42))
        self.call('__bfRecoveryNotify',connection,dict(messID='faShot',params=dict(id=0,status=0,recovery_ms=440)))
        self.assertEqual(self.executed, [])
        self.assertEqual(self.global_['__bfRecoveryUntil'],540)
        self.now=540
        self.call('__bfDrainInput',None)
        self.assertEqual(self.executed,['fire'])

    def test_repeated_attack_keeps_native_ack_latch_during_aim_and_recovery(self):
        for index, method in ((1, '__bfRequestFireOrig'), (2, '__bfRequestStrikeOrig')):
            for recovering in (False, True):
                with self.subTest(index=index, recovering=recovering):
                    self.call('__bfClearInput', None)
                    self.executed.clear()
                    self.timers.clear()
                    self.now = 100
                    self.global_['__bfRecoveryUntil'] = 500 if recovering else 0
                    activator = dict(coolDownBlock=True, useType=16)
                    activator[method] = lambda *args: self.executed.append(args)
                    for target in range(1000):
                        self.call('__bfRequest' + str(index), activator, 1, target)
                    # No native aim/swing bar restart, retarget, queue or timer.
                    self.assertFalse(self.executed)
                    self.assertFalse(self.timers)
                    self.assertIsNone(self.global_.get('__bfPendingInput'))
                    activator['coolDownBlock'] = False
                    self.call('__bfRequest' + str(index), activator, 1, 42)
                    if recovering:
                        self.assertFalse(self.executed)
                        self.assertIsNotNone(self.global_['__bfPendingInput'])
                        self.assertEqual(len(self.timers), 1)
                        self.now = 500
                        self.call('__bfDrainInput', None)
                        self.call('__bfDrainInput', None)
                    self.assertEqual(self.executed, [(1, 42)])

    def test_space_spam_waits_through_fire_out_and_sends_one_new_aim(self):
        scene, figure = self.stalled_shot()
        owner = dict(__bfRequestFireOrig=lambda *args: self.executed.append(args))
        for target in range(100):
            self.call('__bfRequest1', owner, 1, target)
        self.assertEqual(len(self.timers), 1)
        self.assertEqual(figure['__bfBursts'][0]['got'], 1)
        self.now = 250
        figure['behavior'] = 'fire_out'
        self.call('__bfDrainInput', None)
        self.assertFalse(self.executed)
        figure['__bfNextSequenceOrig'] = lambda: figure.update(behavior='stand')
        self.call('__bfNextSequence', figure)
        self.call('__bfDrainInput', None)
        self.assertEqual(self.executed, [(1, 99)])
        self.assertEqual(self.fx.reported, [1])
        self.assertIsNone(self.global_['__bfInputTimer'])

    def test_melee_lowering_allows_one_next_strike_only_after_the_committed_swing(self):
        for command in ('caHit', 'caMiss'):
            with self.subTest(command=command):
                self.call('__bfClearInput', None)
                self.executed.clear()
                self.now = 100
                scene, figure = self.fx.scene()
                figure.update(id=0, behavior='fire', currentFrameNumber=0,
                              animationEnabled=True, isActive=True, onEnterFrame=True)
                self.call('__bfAim', scene, dict(aim=0, num_shots=1, seq=1))
                self.call('__bfRecoveryNotify', dict(__bfRecoveryNotifyOrig=lambda cmd:None),
                          dict(messID=command, params=dict(id=0, recovery_ms=240)))
                self.call('__bfFire', scene, dict(gunnerID=0, access=True, shot=False, seq=1))
                self.assertTrue(figure['__bfBursts'][0]['melee'])
                owner = dict(__bfRequestStrikeOrig=lambda *args:self.executed.append(args))
                self.call('__bfRequest2', owner, 1, 41)
                self.call('__bfRequest2', owner, 1, 42)
                figure['behavior'] = 'fire_out'
                self.now = 339
                self.call('__bfDrainInput', None)
                self.assertFalse(self.executed)
                self.now = 340
                self.call('__bfDrainInput', None)
                self.call('__bfDrainInput', None)
                self.assertEqual(self.executed, [(1, 42)])
                self.assertIsNone(self.global_['__bfInputTimer'])
                self.assertEqual(figure['__bfBursts'], [])

    def test_first_shot_packet_arms_guard_before_native_ack_releases_repeat_attack(self):
        activator = dict(coolDownBlock=False,
                         __bfRequestFireOrig=lambda *args:self.executed.append('fire'))
        connection = dict(__bfRecoveryNotifyOrig=lambda cmd:
                          self.call('__bfRequest1', activator, 1, 42))
        self.call('__bfRecoveryNotify', connection,
                  dict(messID='faShot', params=dict(id=0, status=1, recovery_ms=150)))
        self.assertFalse(self.executed)
        self.assertEqual(len(self.timers), 1)
        self.now = 249
        self.call('__bfDrainInput', None)
        self.assertFalse(self.executed)
        self.now = 250
        self.call('__bfDrainInput', None)
        self.call('__bfDrainInput', None)
        self.assertEqual(self.executed, ['fire'])

    def test_native_shot_event_transfers_timing_to_visual_then_clears_packet_context(self):
        scene, figure = self.fx.scene()
        self.call('__bfAim', scene, dict(aim=0, num_shots=1, seq=1))
        location = dict(__bfLocationShotOrig=lambda event:
                        self.call('__bfFire', scene, dict(gunnerID=0, access=True, shot=True, seq=1)))
        self.call('__bfLocationShot', location,
                  dict(param=dict(id=0, status=0, recovery_ms=150, animation_frames=9)))
        self.assertIsNone(self.global_['__bfShotTiming'])
        self.assertEqual(figure['__bfPlayback'],
                         dict(start=100, duration=150, frames=9, painted=0))
        self.assertEqual(self.fx.reported, [1])

    def test_retimed_burst_plays_every_native_frame_and_only_then_releases_one_input(self):
        scene, figure = self.fx.scene()
        figure.update(id=0, behavior='fire', animationEnabled=True, isActive=True,
                      onEnterFrame=True, currentFrameNumber=0)
        self.call('__bfAim', scene, dict(aim=0, num_shots=5, seq=1))
        for index in range(5):
            if index == 4:
                self.global_['__bfShotTiming'] = dict(recovery_ms=150, animation_frames=21)
            self.call('__bfFire', scene, dict(gunnerID=0, access=True, shot=True, seq=index))
            self.global_['__bfShotTiming'] = None
        # Native Char.playAnimation paints a frame, emits finalFrame and runs
        # nextSequence. Exercise its firing/lowering callbacks, not a shortcut
        # that just clears the waiting flag at a deadline.
        rendered = []
        def native_frame():
            rendered.append(figure['behavior'])
            if len(rendered) == 15:
                figure['behavior'] = 'fire_out'
            if len(rendered) == 21:
                self.call('__bfVisualFinal', scene, dict(target=figure, data='fire_out'))
                figure['__bfNextSequenceOrig'] = lambda:figure.update(behavior='stand')
                self.call('__bfNextSequence', figure)
        figure['__bfPlayAnimationOrig'] = native_frame
        self.global_['__bfRecoveryUntil'] = 250
        owner = dict(__bfRequestFireOrig=lambda *args:self.executed.append(args))
        self.call('__bfRequest1', owner, 1, 41)
        self.call('__bfRequest1', owner, 1, 42)
        self.now = 249
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 20)
        self.assertFalse(self.executed)
        self.now = 252  # a slow render catches up without adding a native-length tail
        self.call('__bfPlayAnimation', figure)
        self.call('__bfDrainInput', None)
        self.assertEqual(rendered, ['fire'] * 15 + ['fire_out'] * 6)
        self.assertEqual(self.executed, [(1, 42)])
        self.assertIsNone(figure['__bfPlayback'])
        self.assertEqual(self.fx.reported, list(range(5)))

    def test_playback_work_is_bounded_and_does_not_speed_up_movement_or_legacy_animations(self):
        rendered = []
        clock = dict(start=100, duration=100, frames=200, painted=0)
        figure = dict(behavior='fire', __bfPlayback=clock,
                      __bfPlayAnimationOrig=lambda:rendered.append('frame'))
        self.now = 200
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 64)
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 128)
        figure['behavior'] = 'run'
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 129)
        self.assertEqual(clock['painted'], 128)
        figure.update(behavior='fire', __bfPlayback=None)
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 130)

    def test_model_frame_count_override_finishes_real_animation_at_deadline(self):
        rendered = []
        clock = dict(start=100, duration=150, frames=9, painted=0)
        figure = dict(behavior='fire', __bfPlayback=clock)
        def native_frame():
            rendered.append('frame')
            if len(rendered) == 12:
                figure.update(behavior='stand', __bfPlayback=None)
        figure['__bfPlayAnimationOrig'] = native_frame
        self.now = 249
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 8)
        self.now = 252
        self.call('__bfPlayAnimation', figure)
        self.assertEqual(len(rendered), 12)
        self.assertEqual(figure['behavior'], 'stand')

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
        owner=dict(__bfRequestHealOrig=lambda a:self.executed.append('move'))
        self.call('__bfRequest4',owner,'cell')
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

    def test_firing_and_lowering_hold_the_next_attack_but_stand_and_disabled_rendering_do_not(self):
        _,figure=self.fx.scene()
        figure.update(animationEnabled=True,isActive=True,onEnterFrame=True,
                      behavior='fire',__bfBursts=Arr([dict(got=1)]))
        self.global_['__bfOwnerFigure']=figure
        self.global_['__bfRecoveryUntil']=100
        self.assertTrue(self.call('__bfWaiting',None))
        figure['behavior'] = 'fire_out'
        self.assertTrue(self.call('__bfWaiting', None))
        for behavior in ('stand','run'):
            figure['behavior']=behavior
            self.assertFalse(self.call('__bfWaiting',None))
        figure['behavior']='fire'
        figure['animationEnabled']=False
        self.assertFalse(self.call('__bfWaiting',None))

    def test_heal_and_swap_run_once_on_firing_completion_without_reclick(self):
        for wrapper,method,args,label in (
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
                figure['__bfNextSequenceOrig']=lambda:figure.update(behavior='stand')
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
        event=dict(walker=dict(id=0,x=40,y=50,__bfStoppingMove=True))
        self.call('__bfPosition',scene,event)
        self.call('__bfFinishMove',scene,event)
        self.assertEqual(figure['behavior'],'fire')
        self.assertEqual((figure['_x'],figure['_y']),(40,50))
        figure['__bfBursts']=Arr()
        self.call('__bfPosition',scene,event)
        self.assertEqual(figure['behavior'],'run')
        self.call('__bfFinishMove',scene,event)
        self.assertEqual(figure['behavior'],'stand')

    def test_authoritative_new_movement_drops_stale_observer_firing_pose(self):
        scene,figure=self.fx.scene()
        self.call('__bfAim',scene,dict(aim=17,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=17,access=True,seq=1))
        figure['behavior']='fire'
        scene['__bfPositionOrig']=lambda e:figure.update(behavior='run')
        self.call('__bfPosition',scene,dict(walker=dict(id=17,x=40,y=50)))
        self.assertEqual(figure['behavior'],'run')
        self.assertEqual(figure['__bfBursts'],[])
        self.assertEqual(self.fx.reported,[1])
        self.assertEqual(self.fx.applied,[])

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
