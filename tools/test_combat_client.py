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


if __name__ == '__main__':
    run_cases(CombatClient)
