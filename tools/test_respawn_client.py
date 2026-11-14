"""Execute lifecycle cleanup as emitted AVM1; no live client or character edits."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))

from avm_test import Function
import widescreen as w
import respawn_client
from testkit import run_cases


def bus():
    entries = []
    def remove(event, owner, fn=None):
        fn = fn if fn is not None else owner.get(event)
        entries[:] = [v for v in entries if not
                      (v[0] == event and v[1] is owner and v[2] is fn)]
    return dict(entries=entries, removeEventListener=remove)


def subscribe(source, event, owner, fn=None):
    source['entries'].append((event, owner, fn if fn is not None else owner.get(event)))


class RespawnClient(unittest.TestCase):
    def setUp(self):
        self.cleared, self.keys, self.calls = [], [], []
        self.shifter, self.chat = bus(), bus()
        self.mouse = bus()
        self.mouse['DOUBLE_CLICK'] = 'doubleClick'
        self.env = dict(_global={}, clearInterval=self.cleared.append,
                        Key=dict(removeListener=self.keys.append),
                        lol=dict(core=dict(SceneShifter=dict(_ref=self.shifter, chat=self.chat)),
                                 utils=dict(EMouse=self.mouse),
                                 events=dict(PlayerEvent=dict(UPDATE_STATE='state', UPDATE_PARAMS='params'),
                                             TimeBarEvent=dict(HEAL='heal', UNLOAD='unload')),
                                 gpui=dict(controls=dict(GPUIButton=dict(RELEASE_EVENT='release')))))
        self.functions = {name: Function(params, body.assemble(), self.env)
                          for name, params, body in respawn_client.patches(w.Asm, w.UNDEF)['globals']}

    def call(self, name, target):
        return self.functions[name].invoke(target, ())

    def scene(self, master, number):
        loc = bus()
        scene = dict(master=master, currentLocation=loc, areaInterval=number,
                     onEnterFrame=lambda:None, userStateUpdate=lambda e:None,
                     gamerUpdate=lambda e:None, changePrimary=lambda e:None,
                     __lifeSceneKillOrig=lambda:self.calls.append('native scene kill'))
        for event in ('addPlayer','removePlayer','position','finishPart','finishMove',
                      'aim','fireAck','dead','enemy','addBag','removeBag'):
            subscribe(loc, event, scene)
        subscribe(master, 'state', scene, scene['userStateUpdate'])
        subscribe(master['gamer'], 'state', scene, scene['gamerUpdate'])
        subscribe(master['gamer']['attributes'], 'params', scene, scene['gamerUpdate'])
        subscribe(master['gamer']['equipment'], 'changePrimary', scene)
        subscribe(self.shifter, 'sceneEnabled', scene)
        return scene

    def master(self):
        master = bus()
        master['gamer'] = bus()
        master['gamer'].update(attributes=bus(), equipment=bus(), apManager=bus())
        return master

    def test_fifty_scene_replacements_keep_only_the_active_scene_subscribed(self):
        master = self.master()
        scene = self.scene(master, 1)
        for number in range(2, 52):
            newer = self.scene(master, number)
            self.call('__lifeSceneKill', scene)
            self.assertEqual(scene['currentLocation']['entries'], [])
            self.assertIsNone(scene['areaInterval'])
            self.assertIsNone(scene['onEnterFrame'])
            for source in (master, master['gamer'], master['gamer']['attributes'],
                           master['gamer']['equipment'], self.shifter):
                self.assertEqual(len(source['entries']), 1)
                self.assertIs(source['entries'][0][1], newer)
            scene = newer
        self.assertEqual(self.cleared, list(range(1, 51)))
        self.assertEqual(scene['areaInterval'], 51)

    def test_regeneration_close_removes_callback_and_timer_before_native_kill(self):
        resurrector, button = bus(), bus()
        native = []
        panel = dict(resurrector=resurrector, timer=7, addMoney_btn=button,
                     addMoney=lambda:None, resurrect=lambda e:None)
        panel['__lifeRegenKillOrig'] = lambda:native.append((len(resurrector['entries']), panel['timer']))
        subscribe(resurrector, 'resurrect', panel)
        subscribe(button, 'release', panel, panel['addMoney'])
        active = dict(resurrect=lambda e:None)
        subscribe(resurrector, 'resurrect', active)
        self.call('__lifeRegenKill', panel)
        self.assertEqual(native, [(1, None)])
        self.assertEqual(button['entries'], [])
        self.assertIs(resurrector['entries'][0][1], active)
        self.assertEqual(self.cleared, [7])

    def test_old_weapon_panel_cannot_receive_new_reload_or_item_updates(self):
        equipment, gamer, item = bus(), bus(), bus()
        old = dict(equipment=equipment, gamer=gamer, item=item, reloadItem=item,
                   healItem=item, timeBar_mc={}, msDamper={}, reloadAlert={},
                   changePrimary=lambda e:None, unload=lambda e:None,
                   healTimeBar=lambda e:None, itemUpdate=lambda e:None,
                   endTimeBar=lambda e:None, __lifeWeaponKillOrig=lambda:None)
        active = dict(changePrimary=lambda e:None, endTimeBar=lambda e:None)
        for target in (old, active):
            subscribe(equipment, 'changePrimary', target)
            subscribe(item, 'itemUpdate', target, target['endTimeBar'])
        subscribe(item, 'itemUpdate', old)
        subscribe(equipment, 'unload', old, old['unload'])
        subscribe(gamer, 'heal', old, old['healTimeBar'])
        subscribe(self.mouse, 'doubleClick', old)
        self.call('__lifeWeaponKill', old)
        self.assertEqual(len(equipment['entries']), 1)
        self.assertEqual(len(item['entries']), 1)
        self.assertIs(item['entries'][0][1], active)
        self.assertEqual(gamer['entries'], [])
        self.assertEqual(self.mouse['entries'], [])

    def test_removed_location_stops_global_ap_resize_chat_and_key_callbacks(self):
        master = self.master()
        old = dict(master=master, chWAck=lambda e:None, __lifeLocationKillOrig=lambda:None)
        current = dict(chWAck=lambda e:None)
        for target in (old, current):
            subscribe(master, 'changeWorld', target, target['chWAck'])
            subscribe(master['gamer']['apManager'], 'actionPoints', target)
            subscribe(self.shifter, 'resizeStage', target)
            subscribe(self.chat, 'chatRes', target)
        self.call('__lifeLocationKill', old)
        for source in (master, master['gamer']['apManager'], self.shifter, self.chat):
            self.assertEqual(len(source['entries']), 1)
            self.assertIs(source['entries'][0][1], current)
        self.assertEqual(self.keys, [old])


if __name__ == '__main__':
    run_cases(RespawnClient)
