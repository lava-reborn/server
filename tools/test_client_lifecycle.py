"""Execute cleanup AVM1: repeated transitions retain no retired timers/listeners."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Arr, Function
from client_lifecycle import patches
from testkit import run_cases
import widescreen as w


class Publisher(dict):
    def __init__(self):
        super().__init__(publisher=True)
        self.listeners = []
        self.update(addEventListener=self.addEventListener,
                    removeEventListener=self.removeEventListener)

    def addEventListener(self, event, owner, handler=None):
        handler = handler if handler is not None else owner.get(event)
        self.removeEventListener(event, owner, handler)
        self.listeners.append((event, owner, handler))

    def removeEventListener(self, event, owner, handler=None):
        handler = handler if handler is not None else owner.get(event)
        self.listeners[:] = [(e, o, h) for e, o, h in self.listeners
                             if not (e == event and o is owner and h is handler)]

    def dispatch(self, event):
        for e, _owner, handler in list(self.listeners):
            if e == event and handler is not None:
                handler()


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.timers, self.cleared = {}, []
        self.next_timer = 0
        self.state, self.master, self.gamer = Publisher(), Publisher(), Publisher()
        self.attrs, self.equipment, self.chat = Publisher(), Publisher(), Publisher()
        self.gamer.update(attributes=self.attrs, equipment=self.equipment)
        self.master.update(gamer=self.gamer, chat=self.chat)
        self.shifter = dict(_ref=self.state)
        self.global_ = dict(untouched='chat, input and asset cache')
        self.env = dict(_global=self.global_, clearInterval=self.clear,
                        lol=dict(core=dict(SceneShifter=self.shifter),
                                 events=dict(PlayerEvent=dict(UPDATE_STATE='userUpdate', UPDATE_PARAMS='rp_info'))))
        self.functions = {}
        for name, args, body in patches(w.Asm, w.UNDEF)['globals']:
            fn = Function(args, body.assemble(), self.env)
            self.global_[name] = self.functions[name] = fn

    def timer(self, owner):
        value = self.next_timer
        self.next_timer += 1
        self.timers[value] = owner
        return value

    def clear(self, handle):
        self.cleared.append(handle)
        self.timers.pop(handle, None)

    def call(self, name, owner=None, *args):
        return self.functions[name].invoke(owner, args)

    def scene(self):
        scene = dict(master=self.master, currentLocation=Publisher(), native_kills=0, updates=0)
        def update():
            scene['updates'] += 1
        for name in ('sceneEnabled', 'userStateUpdate', 'gamerUpdate', 'chatRefreshed',
                     'changePrimary', 'addPlayer', 'removePlayer', 'position', 'finishPart',
                     'finishMove', 'aim', 'fireAck', 'dead', 'enemy', 'addBag', 'removeBag'):
            scene[name] = update
        self.state.addEventListener('sceneEnabled', scene)
        def init():
            scene['areaInterval'] = self.timer(scene)
            self.master.addEventListener('userUpdate', scene, scene['userStateUpdate'])
            self.gamer.addEventListener('userUpdate', scene, scene['gamerUpdate'])
            self.attrs.addEventListener('rp_info', scene, scene['gamerUpdate'])
            self.equipment.addEventListener('changePrimary', scene)
            self.chat.addEventListener('refresh', scene, scene['chatRefreshed'])
            for event in ('addPlayer', 'removePlayer', 'position', 'finishPart', 'finishMove',
                          'aim', 'fireAck', 'dead', 'enemy', 'addBag', 'removeBag'):
                scene['currentLocation'].addEventListener(event, scene)
        def kill():
            # Original DisplayLocScene.kill removes chat, but not the interval
            # or subscriptions above. Manager disposal has no fixture effect.
            self.chat.removeEventListener('refresh', scene, scene['chatRefreshed'])
            scene['native_kills'] += 1
        scene.update(__lcSceneInitOrig=init, __lcSceneKillOrig=kill)
        return scene

    def buses(self):
        return (self.state, self.master, self.gamer, self.attrs, self.equipment, self.chat)

    def test_original_cleanup_leaves_retired_timer_and_long_lived_subscriptions(self):
        scene = self.scene()
        scene['__lcSceneInitOrig']()
        scene['__lcSceneKillOrig']()
        self.assertEqual(len(self.timers), 1)
        self.assertTrue(all(bus.listeners for bus in self.buses()[:-1]))

    def test_hundred_transitions_keep_only_the_live_scene(self):
        active = self.scene()
        self.call('__lcSceneInit', active)
        for _ in range(100):
            retired = self.scene()
            self.call('__lcSceneInit', retired)
            self.call('__lcSceneKill', retired)
            self.assertEqual(retired['native_kills'], 1)
            self.assertEqual(retired['currentLocation'].listeners, [])
        self.assertEqual(list(self.timers.values()), [active])
        for bus in self.buses():
            self.assertEqual(len(bus.listeners), 1)
            self.assertIs(bus.listeners[0][1], active)
        self.master.dispatch('userUpdate')
        self.assertEqual(active['updates'], 1)
        self.call('__lcSceneKill', active)
        self.assertEqual(self.timers, {})
        self.assertTrue(all(not bus.listeners for bus in self.buses()))
        self.assertEqual(self.global_['untouched'], 'chat, input and asset cache')

    def test_reinitialization_does_not_orphan_an_interval_including_handle_zero(self):
        scene = self.scene()
        self.call('__lcSceneInit', scene)
        self.assertEqual(scene['areaInterval'], 0)
        self.call('__lcSceneInit', scene)
        self.assertEqual(self.cleared, [0])
        self.assertEqual(len(self.timers), 1)
        self.call('__lcSceneKill', scene)
        self.assertEqual(self.timers, {})

    def test_disposal_twice_calls_native_kill_once(self):
        scene = self.scene()
        self.call('__lcSceneInit', scene)
        scene['spt_int'] = self.timer(scene)
        self.call('__lcSceneKill', scene)
        self.call('__lcSceneKill', scene)
        self.assertEqual(scene['native_kills'], 1)
        self.assertEqual(len(self.cleared), 2)

    def test_old_scene_cleanup_uses_its_original_publishers(self):
        scene = self.scene()
        self.call('__lcSceneInit', scene)
        new_state, new_gamer = Publisher(), Publisher()
        new_state.addEventListener('sceneEnabled', scene)
        new_gamer.addEventListener('userUpdate', scene, scene['gamerUpdate'])
        self.shifter['_ref'] = new_state
        self.master['gamer'] = new_gamer
        self.call('__lcSceneKill', scene)
        self.assertTrue(all(not bus.listeners for bus in self.buses()))
        self.assertEqual(len(new_state.listeners), 1)
        self.assertEqual(len(new_gamer.listeners), 1)

    def test_equipment_and_attributes_replacement_keeps_new_subscribers(self):
        scene = self.scene()
        self.call('__lcSceneInit', scene)
        attrs, equipment = Publisher(), Publisher()
        attrs.addEventListener('rp_info', scene, scene['gamerUpdate'])
        equipment.addEventListener('changePrimary', scene)
        self.gamer.update(attributes=attrs, equipment=equipment)
        self.call('__lcSceneKill', scene)
        self.assertEqual(self.attrs.listeners, [])
        self.assertEqual(self.equipment.listeners, [])
        self.assertEqual(len(attrs.listeners), 1)
        self.assertEqual(len(equipment.listeners), 1)

    def test_global_map_removes_add_player_from_original_model_only(self):
        model, replacement = Publisher(), Publisher()
        scene = dict(globalMap=model, addPlayer=lambda: None, killed=0)
        scene['__lcMapInitOrig'] = lambda: model.addEventListener('addPlayer', scene)
        def kill():
            scene['killed'] += 1
        scene['__lcMapKillOrig'] = kill
        self.call('__lcMapInit', scene)
        scene['globalMap'] = replacement
        replacement.addEventListener('addPlayer', scene)
        self.call('__lcMapKill', scene)
        self.call('__lcMapKill', scene)
        self.assertEqual(model.listeners, [])
        self.assertEqual(len(replacement.listeners), 1)
        self.assertEqual(scene['killed'], 1)

    def test_cancelled_loader_detaches_its_error_callback_without_unloading_shared_asset(self):
        resource = Publisher()
        resource.update(status='loading', sourceURL='unchanged', frame_arr=Arr([1, 2]))
        loader = dict(sourceList=Arr([resource, None]), onLoadSource=lambda: None,
                      onLoadProgress=lambda: None, onLoadError=lambda: None)
        other = dict(onLoadError=lambda: None)
        for event in ('onLoadSource', 'onLoadProgress', 'onLoadError'):
            resource.addEventListener(event, loader)
        resource.addEventListener('onLoadError', other)
        def clear():
            for event in ('onLoadSource', 'onLoadProgress'):
                resource.removeEventListener(event, loader)
            loader['sourceList'] = Arr()
        loader['__lcLoaderClearOrig'] = clear
        self.call('__lcLoaderClear', loader)
        self.assertEqual(len(resource.listeners), 1)
        self.assertIs(resource.listeners[0][1], other)
        self.assertEqual((resource['status'], resource['sourceURL'], resource['frame_arr']),
                         ('loading', 'unchanged', [1, 2]))
        self.call('__lcLoaderClear', loader)
        self.assertEqual(len(resource.listeners), 1)

    def test_trader_ad_disabled_without_service_message_or_subscription(self):
        calls = []
        interface = dict(traderMessage_bool=True,
                         __lcTraderOrig=lambda: calls.append('subscribe'),
                         __lcTraderLoadedOrig=lambda: calls.append('advertise'),
                         newServiceMessage='existing quest notice')
        self.call('__lcDisableTraderNotice', interface)
        self.call('__lcDisableTraderNotice', interface)
        self.assertFalse(interface['traderMessage_bool'])
        self.assertEqual(calls, [])
        self.assertEqual(interface['newServiceMessage'], 'existing quest notice')
        wrapped = {(p, m) for p, m, *_ in patches(w.Asm, w.UNDEF)['wraps']}
        path = ('gpui', 'LocationInterface')
        self.assertIn((path, 'checkTrader'), wrapped)
        self.assertIn((path, 'checkPlayerAfterLoading'), wrapped)
        self.assertNotIn((path, 'showGoldMessage'), wrapped)
        self.assertNotIn((path, 'checkBagOverload'), wrapped)

    def test_loader_before_any_requests_still_runs_native_clear(self):
        calls = []
        loader = dict(__lcLoaderClearOrig=lambda: calls.append('cleared'))
        self.call('__lcLoaderClear', loader)
        self.assertEqual(calls, ['cleared'])

    def test_timeout_constructor_preserves_bootstrap_registry(self):
        old = dict(_intervals=Arr([17]))
        self.env['lol']['utils'] = dict(Timeout=old)
        replacement = self.functions['__lcTimeout']
        replacement.prototype = {}
        self.call('__lcInstallTimeout')
        self.assertIs(self.env['lol']['utils']['Timeout'], replacement)
        self.assertIs(replacement._intervals, old['_intervals'])
        self.assertIs(replacement.prototype['Clear'], self.functions['__lcTimeoutClear'])
        self.call('__lcInstallTimeout')
        self.assertIs(self.env['lol']['utils']['Timeout'], replacement)

    def test_effect_panel_releases_original_source_and_timer(self):
        source, replacement = Publisher(), Publisher()
        self.gamer['effects'] = source
        self.env['lol']['events']['PlayerEvent'].update(UPDATE_EFFECTS='effects', UPDATE_ONE_EFFECT='oneEffect')
        calls = []
        panel = dict(master=self.master, effectsUpdate=lambda: None, oneEffectUpdate=lambda: None,
                     __lcEffectsKillOrig=lambda: calls.append('killed'))
        def init():
            panel['effectsTimer'] = self.timer(panel)
            source.addEventListener('effects', panel, panel['effectsUpdate'])
            source.addEventListener('oneEffect', panel, panel['oneEffectUpdate'])
        panel['__lcEffectsInitOrig'] = init
        self.call('__lcEffectsInit', panel)
        self.gamer['effects'] = replacement
        replacement.addEventListener('effects', panel, panel['effectsUpdate'])
        self.call('__lcEffectsKill', panel)
        self.call('__lcEffectsKill', panel)
        self.assertFalse(self.timers)
        self.assertFalse(source.listeners)
        self.assertEqual(len(replacement.listeners), 1)
        self.assertEqual(calls, ['killed'])

    def info_panel(self, party, player):
        events = dict(JOIN_TO_PARTY='join', DISBAND_PARTY='disband',
                      KICKED_FROM_PARTY='kick', LEAVE_PARTY='leave',
                      PARTY_LIST_REFRESH='refresh')
        self.env['lol']['core']['party'] = dict(
            PartyManager=dict(getInstance=lambda: party), PartyEvent=events)
        self.env['lol']['events']['PlayerEvent']['UPDATE_INFO'] = 'info'
        panel = dict(player=player, native_kills=0,
                     partyColorUpdate=lambda: None, partyColorUpdate_pause=lambda: None,
                     userInfoUpdate=lambda: None)

        def init(entity_id):
            panel['entity_id'] = entity_id
            for event in events.values():
                party.addEventListener(event, panel, panel['partyColorUpdate'])
            player.addEventListener('info', panel, panel['userInfoUpdate'])
            panel['timer'] = self.timer(panel)
            panel['removePhraseInterval'] = self.timer(panel)

        def native_kill():
            # Exact native mismatch: these are not the subscribed functions.
            for event in events.values():
                party.removeEventListener(event, panel, panel['partyColorUpdate_pause'])
            panel['native_kills'] += 1

        panel.update(__lcInfoNickOrig=init, __lcInfoKillOrig=native_kill)
        panel['kill'] = lambda: self.call('__lcInfoKill', panel)
        return panel

    def test_native_name_panel_retains_party_info_and_timers_after_kill(self):
        party, player = Publisher(), Publisher()
        panel = self.info_panel(party, player)
        panel['__lcInfoNickOrig'](800001)
        panel['__lcInfoKillOrig']()
        self.assertEqual(len(party.listeners), 5)
        self.assertEqual(len(player.listeners), 1)
        self.assertEqual(len(self.timers), 2)

    def test_name_panel_cleanup_keeps_other_live_panel_and_original_publishers(self):
        party, player = Publisher(), Publisher()
        retired = self.info_panel(party, player)
        live = self.info_panel(party, player)
        self.call('__lcInfoNick', retired, 800001)
        self.call('__lcInfoNick', live, 0)
        replacement = Publisher()
        retired['player'] = replacement
        replacement.addEventListener('info', retired, retired['userInfoUpdate'])
        self.call('__lcInfoKill', retired)
        self.call('__lcInfoKill', retired)
        self.assertEqual(retired['native_kills'], 1)
        self.assertEqual(len(self.timers), 2)
        self.assertEqual(len(party.listeners), 5)
        self.assertTrue(all(owner is live for _event, owner, _handler in party.listeners))
        self.assertEqual(len(player.listeners), 1)
        self.assertIs(player.listeners[0][1], live)
        self.assertEqual(len(replacement.listeners), 1)
        self.assertIsNone(retired['__lcInfoParty'])
        self.assertIsNone(retired['__lcInfoPlayer'])

    def test_hundred_ten_player_scenes_release_sparse_name_panels(self):
        party, player = Publisher(), Publisher()
        for _ in range(100):
            scene = self.scene()
            self.call('__lcSceneInit', scene)
            panels = [self.info_panel(party, player) for _ in range(10)]
            for index, panel in enumerate(panels):
                self.call('__lcInfoNick', panel, 800001 + index)
            # Native helperObjects is sparse, keyed by possibly huge entity IDs.
            scene['helperObjects'] = {str(800000001 + i): panel for i, panel in enumerate(panels)}
            scene['helperObjects']['0'] = None
            self.call('__lcSceneKill', scene)
            self.call('__lcSceneKill', scene)
            self.assertEqual([p['native_kills'] for p in panels], [1] * 10)
            self.assertFalse(party.listeners)
            self.assertFalse(player.listeners)
            self.assertFalse(self.timers)

    def test_preparation_display_expires_after_delayed_frame_without_early_release(self):
        clock, calls = [1000], []
        self.functions['__lcPrepareTimer'].closure['getTimer'] = lambda: clock[0]
        panel = dict(startTimer=1000, timerFlag=True, prepare_txt=dict(text='15'),
                     __lcPrepareTimerOrig=lambda seconds: calls.append(seconds))
        panel['timer'] = self.timer(panel)
        clock[0] = 15999
        self.call('__lcPrepareTimer', panel, 15)
        self.assertEqual(calls, [15])
        self.assertTrue(panel['timerFlag'])
        self.assertEqual(len(self.timers), 1)
        # Native count == seconds misses this second after a pause/slow frame.
        clock[0] = 18000
        self.call('__lcPrepareTimer', panel, 15)
        self.assertEqual(calls, [15])
        self.assertFalse(panel['timerFlag'])
        self.assertIsNone(panel['timer'])
        self.assertFalse(self.timers)
        self.assertEqual(panel['prepare_txt']['text'], '')
        panel['timerFlag'] = True
        panel['timer'] = self.timer(panel)
        clock[0] = 16000
        self.call('__lcPrepareTimer', panel, 15)
        self.assertFalse(self.timers)
        self.assertFalse(panel['timerFlag'])

    def test_ten_shooters_thirty_thousand_timeouts_release_every_reference(self):
        pending, delivered = {}, []
        counter = 0
        def schedule(callback, delay, owner):
            nonlocal counter
            counter += 1
            pending[counter] = (callback, owner)
            return counter
        self.functions['__lcTimeout'].closure['setInterval'] = schedule
        self.functions['__lcStopTimer'].closure['clearInterval'] = lambda key: pending.pop(key, None)
        peak = 0
        for volley in range(500):
            batch = []
            for player in range(10):
                for pellet in range(6):
                    timer = {}
                    self.call('__lcTimeout', timer, dict(player=player),
                              lambda value: delivered.append(value), 50, (volley, player, pellet))
                    batch.append(timer)
            peak = max(peak, len(pending))
            for timer in batch:
                self.call('__lcTimeoutFire', None, timer)
                self.assertIsNone(timer['id'])
                self.assertIsNone(timer['target'])
                self.assertIsNone(timer['callback'])
                self.assertIsNone(timer['args'])
            self.assertEqual(len(pending), 0)
        self.assertEqual(peak, 60)
        self.assertEqual(len(delivered), 30000)
        self.assertEqual(len(set(delivered)), 30000)

    def test_timeout_clears_before_callback_and_clear_is_idempotent(self):
        pending = {}
        def schedule(callback, delay, owner):
            pending[0] = owner
            return 0
        self.functions['__lcTimeout'].closure['setInterval'] = schedule
        self.functions['__lcStopTimer'].closure['clearInterval'] = lambda key: pending.pop(key, None)
        def failure():
            self.assertFalse(pending)
            raise ValueError('callback failed')
        timer = {}
        self.call('__lcTimeout', timer, {}, failure, 50)
        with self.assertRaisesRegex(ValueError, 'callback failed'):
            self.call('__lcTimeoutFire', None, timer)
        self.call('__lcTimeoutClear', timer)
        self.assertFalse(pending)
        self.call('__lcTimeoutFire', None, timer)


if __name__ == '__main__':
    run_cases(Lifecycle)
