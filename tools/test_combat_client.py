"""Execute emitted battle hooks: no Flash, database, sockets or load run."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
import math
import unittest

import widescreen as w
from avm_test import Arr, Function
from combat_client import patches
from testkit import run_cases


class CombatClient(unittest.TestCase):
    def test_empty_remote_primary_uses_fist_without_type_zero_request(self):
        equip = dict(isGamer=False, primaryItem='old weapon',
                     __bfRemotePrimaryOrig=lambda event:self.fail('type-zero prototype requested'))
        self.call('__bfRemotePrimary', equip, dict(param=dict(to=512, obj='0')))
        self.assertIsNone(equip['primaryItem'])

    def test_remote_weapon_and_clothes_keep_native_item_processing(self):
        events = []
        equip = dict(isGamer=False, __bfRemotePrimaryOrig=events.append)
        for to, oid in ((512, '1642400'), (256, '0')):
            event = dict(param=dict(to=to, obj=oid))
            self.call('__bfRemotePrimary', equip, event)
            self.assertIs(events[-1], event)

    def test_own_primary_move_is_left_to_native_ack_processing(self):
        events = []
        equip = dict(isGamer=True, __bfRemotePrimaryOrig=events.append)
        event = dict(param=dict(to=512, obj='0'))
        self.call('__bfRemotePrimary', equip, event)
        self.assertEqual(events, [event])

    def setUp(self):
        self.sent, self.calls, self.applied = [], [], []
        self.reported = []
        self.env = dict(_global={}, Number=float, isNaN=math.isnan,
                        Math=dict(max=max, min=min),
                        lol=dict(core=dict(SceneShifter=dict(linkGame=dict(
                            visavisAvatar=dict(removeMovieClip=lambda: self.calls.append('avatar')))),
                            player=dict(Training=dict(UPD_CLOSE=0))),
                            data=dict(BigUINTCluster=lambda n: dict(value=n), BigUINT=lambda c: c),
                            server=dict(mess=dict(CSM_SSUpdate=lambda a,b: dict(kind=a, number=b)))))
        spec = patches(w.Asm, w.UNDEF)
        self.functions = {}
        for name, params, body in spec['globals']:
            fn = Function(params, body.assemble(), self.env)
            self.env['_global'][name] = fn
            self.functions[name] = fn

    def call(self, name, target, *args):
        return self.functions[name].invoke(target, args)

    def test_training_user_close_sends_one_close_and_finishes_cleanup(self):
        panel = dict(XMC=dict(Send=self.sent.append),
                     dispatchEvent=lambda e: self.calls.append(e['type']),
                     kill=lambda: self.calls.append('kill'))
        self.call('__bfTrainingClose', panel)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]['kind'], 0)
        self.assertEqual(self.calls, ['close', 'avatar', 'kill'])

    def test_server_training_close_does_not_echo_another_request(self):
        panel = dict(dispatchEvent=lambda e: self.calls.append(e['type']),
                     kill=lambda: self.calls.append('kill'))
        target = dict(removeEventListener=lambda *a: self.calls.append('unsubscribe'))
        self.call('__bfTrainingClose', panel, dict(target=target))
        self.assertEqual(self.sent, [])
        self.assertEqual(self.calls, ['unsubscribe', 'close', 'avatar', 'kill'])

    def test_bars_are_clamped_and_valid_full_health_is_preserved(self):
        for method in ('Health', 'Stamina'):
            seen=[]
            panel={'__bf'+method+'Orig': lambda p,v: seen.append((p,v))}
            for value in (-25, 0, 50, 100, 350, float('nan')):
                self.call('__bf'+method, panel, value, 500)
            self.assertEqual(seen, [(0,500),(0,500),(50,500),(100,500),(100,500),(0,500)])

    def scene(self):
        figure = dict(burstArr=Arr(), addEventListener=lambda *a: None,
                      removeEventListener=lambda *a: None)
        scene = dict(getWalker=lambda eid: figure,
                     __bfAimOrig=lambda e: self.calls.append(('aim',e['seq'])),
                     __bfFireOrig=lambda e: (figure['burstArr'].push(e), self.reported.append(e['seq'])),
                     applyFireAck=lambda e: self.applied.append(e['seq']),
                     addFireAckReport=lambda e: self.reported.append(e['seq']), showFireAckReport=lambda: None,
                     shotgunFireAck=lambda e: None, busrtFireAck=lambda e: None,
                     __bfDeadOrig=lambda e: self.calls.append(('dead',e['dead'])))
        return scene, figure

    def confirmed_volley(self, count=3, weapon=4):
        scene, figure = self.scene()
        figure.update(_x=100, _y=200, isActive=True, animationEnabled=True)
        sounds, traces = [], []
        names = ['PISTOL_FIRE', 'SHOTGUN_FIRE', 'ASSAULT_FIRE', 'RIFLE_FIRE',
                 'MACHINEGUN_FIRE', 'SMG_FIRE', 'FIREARM_FIRE']
        self.env['lol']['sound'] = dict(
            SoundEvent={name: name for name in names},
            SoundManager=dict(getInstance=lambda: dict(playEventSound=sounds.append)))
        scene['master'] = dict(getPlayer=lambda _id: dict(
            equipment=dict(primaryItem=dict(getProp=lambda _key: weapon))))
        scene['hitPoint'] = lambda hit: dict(x=hit['x'], y=hit['y'])
        scene['traceShot'] = lambda *args: traces.append(args)
        scene['applyFireAck'] = lambda event: self.call('__bfApplyFire', scene, event)
        scene['__bfApplyFireOrig'] = lambda event: self.fail('lost captured origin')
        self.call('__bfAim', scene, dict(aim=1, num_shots=count, seq=1))
        events = []
        for seq in range(count):
            event = dict(gunnerID=1, shot=True, access=True, seq=seq,
                         hits=Arr([dict(type='point', x=400, y=450)]))
            self.call('__bfFire', scene, event)
            events.append(event)
        return scene, figure, sounds, traces, events

    def test_confirmed_unplayed_shot_survives_movement_once_without_stalling_it(self):
        scene, figure, sounds, traces, events = self.confirmed_volley()
        figure.update(behavior='fire', onEnterFrame=lambda: None, _x=900, _y=900)
        walker = dict(id=1)
        scene['__bfPositionOrig'] = lambda obj: self.calls.append('movement')
        self.call('__bfPosition', scene, dict(walker=walker))
        self.assertEqual(traces, [(1, dict(x=400, y=450), dict(x=100, y=150))])
        self.assertEqual(sounds, ['MACHINEGUN_FIRE'])
        self.assertEqual(self.calls, [('aim', 1), 'movement'])
        self.assertEqual(self.reported, [0, 1, 2])
        self.assertEqual(figure['burstArr'], [])
        self.assertEqual(figure['__bfBursts'], [])
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual(len(traces), 1)
        self.assertEqual(len(sounds), 1)
        # A stale callback must not replay the same projectile.
        self.call('__bfApplyFire', scene, events[0])
        self.assertEqual(len(traces), 1)

    def test_other_action_and_final_frame_preserve_one_trace_not_entire_burst(self):
        for kind in ('Burst', 'Shotgun'):
            for transition in ('run', 'heal', 'change_weapon', 'fire_out'):
                with self.subTest(kind=kind, transition=transition):
                    self.reported.clear()
                    scene, figure, sounds, traces, _events = self.confirmed_volley(
                        count=9, weapon=1 if kind=='Shotgun' else 5)
                    scene['__bf'+kind+'FinalOrig'] = lambda obj: None
                    self.call('__bf'+kind+'Final', scene,
                              dict(target=figure, data=transition))
                    self.assertEqual(len(traces), 1)
                    self.assertEqual(sounds, ['SHOTGUN_FIRE' if kind=='Shotgun' else 'SMG_FIRE'])
                    self.assertEqual(self.reported, list(range(9)))
                    self.assertEqual(figure['__bfBursts'], [])

    def test_native_rendered_volley_is_not_replayed_or_given_a_second_sound(self):
        scene, figure, sounds, traces, events = self.confirmed_volley()
        # The native handler plays its sound after applyFireAck; leave that path alone.
        self.call('__bfApplyFire', scene, figure['burstArr'].shift())
        self.assertEqual(sounds, [])
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual(len(traces), 1)
        self.assertEqual(sounds, [])
        self.assertTrue(events[0]['__bfPresented'])

    def test_interruption_uses_weapon_sound_captured_at_aim_not_new_weapon(self):
        for weapon, expected in enumerate(('PISTOL_FIRE', 'SHOTGUN_FIRE', 'ASSAULT_FIRE',
                                           'RIFLE_FIRE', 'MACHINEGUN_FIRE', 'SMG_FIRE')):
            with self.subTest(weapon=weapon):
                scene, figure, sounds, _traces, _events = self.confirmed_volley(weapon=weapon)
                scene['master']['getPlayer'] = lambda _id: self.fail('late weapon lookup')
                self.call('__bfDead', scene, dict(dead=1))
                self.call('__bfDead', scene, dict(dead=1))
                self.assertEqual(sounds, [expected])

    def test_invisible_unconfirmed_melee_and_empty_shots_do_not_create_effects(self):
        for inactive in ('offscreen', 'animation_disabled', 'refused', 'melee', 'no_hits'):
            with self.subTest(case=inactive):
                scene, figure, sounds, traces, events = self.confirmed_volley(count=1)
                if inactive=='offscreen':
                    figure['isActive'] = False
                elif inactive=='animation_disabled':
                    figure['animationEnabled'] = False
                elif inactive=='refused':
                    events[0]['access'] = False
                elif inactive=='melee':
                    events[0]['shot'] = False
                else:
                    events[0]['hits'] = Arr()
                self.call('__bfVisualFlush', None, scene, figure, False)
                self.assertEqual((sounds, traces), ([], []))

    def test_cancelled_aim_never_creates_a_fallback_shot(self):
        scene, figure = self.scene()
        self.call('__bfAim', scene, dict(aim=1, num_shots=9, seq=1))
        self.call('__bfVisualFlush', None, scene, figure, False)
        self.assertEqual((self.reported, self.applied), ([], []))

    def test_repeat_aim_preserves_confirmed_previous_bullets(self):
        scene, figure = self.scene()
        self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=1))
        self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=1))
        self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=2))
        self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=2))
        self.assertEqual(self.calls,[('aim',1)])
        self.assertEqual([e['seq'] for e in figure['burstArr']],[1])
        # Native final-frame handler consumes the confirmed first burst.
        scene['applyFireAck'](figure['burstArr'].shift())
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.calls,[('aim',1)])
        figure['__bfNextSequenceOrig'] = lambda: self.calls.append('native-transition')
        self.call('__bfNextSequence',figure)
        self.assertEqual(self.calls,[('aim',1),'native-transition',('aim',2)])
        self.assertEqual([e['seq'] for e in figure['burstArr']],[2])
        scene['applyFireAck'](figure['burstArr'].shift())
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[1,2])
        self.assertEqual(figure['__bfBursts'],[])

    def test_final_fire_out_discards_remaining_traces_but_keeps_reports(self):
        scene,figure=self.scene()
        self.call('__bfAim',scene,dict(aim=1,num_shots=2,seq=1))
        for seq in (1,2):
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=seq))
        self.call('__bfVisualFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2])
        self.assertEqual(figure['__bfBursts'],[])
        self.assertEqual(figure['burstArr'],[])
        # Native cleanup observes the empty buffer; no duplicate damage/report.
        scene['__bfBurstFinalOrig']=lambda event:None
        self.call('__bfBurstFinal',scene,dict(target=figure,data='fire_out'))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2])

    def test_death_discards_unplayed_traces_and_keeps_each_report_once(self):
        scene, figure = self.scene()
        for i in (1,2,3):
            self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=i))
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=i))
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2,3])
        self.assertEqual(figure['__bfBursts'],[])
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,[1,2,3])

    def test_queued_visuals_are_bounded_without_catch_up_traces_or_lost_reports(self):
        scene, figure = self.scene()
        for i in range(30):
            self.call('__bfAim',scene,dict(aim=1,num_shots=1,seq=i))
            self.call('__bfFire',scene,dict(gunnerID=1,access=True,seq=i))
            self.assertLessEqual(len(figure['__bfBursts']),8)
        self.call('__bfDead',scene,dict(dead=1))
        self.assertEqual(self.applied,[])
        self.assertEqual(self.reported,list(range(30)))

    def test_interrupted_burst_and_shotgun_do_not_render_all_remaining_bullets(self):
        for kind in ('Burst','Shotgun'):
            scene, figure = self.scene()
            scene['__bf'+kind+'FinalOrig'] = lambda e: self.calls.append('native')
            figure['burstArr']=Arr([dict(seq=1),dict(seq=2)])
            self.call('__bf'+kind+'Final',scene,dict(target=figure,data='run'))
            self.assertEqual(figure['burstArr'],[])
        self.assertEqual(self.applied,[])

    def test_delayed_trace_keeps_the_shot_positions_instead_of_following_moving_figures(self):
        scene,figure=self.scene()
        figure.update(_x=100,_y=200)
        target=dict(_x=400,_y=500)
        scene['getWalker']=lambda eid:figure if eid==1 else target
        event=dict(gunnerID=1,access=True,shot=True,seq=1,
                   hits=Arr([dict(type='target',targetID=2)]))
        self.call('__bfFire',scene,event)
        self.assertEqual(event.get('__bfOrigin'),dict(x=100,y=150))
        self.assertEqual(event['hits'][0].get('__bfPoint'),dict(x=400,y=450))
        figure.update(_x=-20,_y=-20)
        target.update(_x=800,_y=900)
        traces=[]
        self.env['lol']['fx']=dict(ShotTrace=lambda:dict(traceShot=lambda *args:traces.append(args)))
        self.env['Math']['random']=lambda:.5
        scene['helpers_mc']='helpers'
        scene['__bfTraceShotOrig']=lambda *args:self.fail('late native coordinates')
        scene['__bfApplyFireOrig']=lambda e:self.fail('lost captured event')
        scene['hitTarget']=lambda hit:hit['__bfPoint']
        scene['traceShot']=lambda *args:self.call('__bfTraceShot',scene,*args)
        self.call('__bfApplyFire',scene,event)
        self.assertEqual(traces,[('helpers',dict(x=100,y=150),dict(x=400,y=450))])
        self.assertEqual(event['hits'],[])


if __name__ == '__main__':
    run_cases(CombatClient)
