"""Execute emitted AVM: recover missing key-up and cancel UI without FIFO edits.

HotKeyManager, LocationInterface.keyRelease_func and ViewFrame.setHandScroll
are the client contracts. The shared AVM executor runs the assembled patch;
physical Windows layout/focus and actual Flash rendering are manual checks.
"""
import os
import sys
import unittest
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server'))
import widescreen as w  # noqa: E402
from avm_test import Arr, execute, get  # noqa: E402
from testkit import run_cases  # noqa: E402

class ClientActions(unittest.TestCase):

    def reconcile(self, old, held, releasing=False, current=None, on_release=None):
        calls = []
        events = []
        obj = NS(keyStack=Arr(old), keyPressStack=Arr(), enabled=False, hotKeyFilter_arr=['chat'])

        def dispatch(event):
            events.append(event)
            if on_release:
                on_release(event, obj)
        obj.dispatchEvent = dispatch
        obj.releases = events
        obj.original = lambda: calls.append(1)
        execute(w.fn_hotkey_reconcile('original', releasing=releasing).assemble(), dict(this=obj, Key=NS(isDown=lambda code: code in held, getCode=lambda: current)))
        self.assertEqual(calls, [1])
        self.assertFalse(obj.enabled)
        self.assertEqual(obj.hotKeyFilter_arr, ['chat'])
        return obj

    def test_lost_modifier_keyup(self):
        for stale in ([16, 18], [17, 16], [91, 18]):
            obj = self.reconcile(stale, set())
            self.assertEqual(obj.keyStack, [])

    def test_held_modifiers_preserved(self):
        obj = self.reconcile([16, 17], {16})
        self.assertEqual(obj.keyStack, [16])
        self.assertEqual(get(obj.keyPressStack, 'code16'), 16)

    def test_duplicate_entries_removed(self):
        obj = self.reconcile([16, 16, 82], {16, 82})
        self.assertEqual(obj.keyStack, [16, 82])

    def test_physical_letter_codes_unchanged(self):
        for code in (70, 82, 32):
            self.assertEqual(self.reconcile([16, code], {code}).keyStack, [code])

    def test_lost_shift_release_exits_hand_scroll_before_next_hotkey(self):
        frame = NS(handDrag=True, clicks='camera')

        def release(event, obj):
            self.assertEqual(obj.keyStack, [81])
            if event == {'type': 'KEY_RELEASE', 'code': 16}:
                frame.handDrag = False
                frame.clicks = 'movement'
        obj = self.reconcile([16, 81], {81}, on_release=release)
        self.assertFalse(frame.handDrag)
        self.assertEqual(frame.clicks, 'movement')
        self.assertEqual(obj.releases, [{'type': 'KEY_RELEASE', 'code': 16}])

    def test_duplicate_stale_key_notifies_once(self):
        obj = self.reconcile([16, 16], set())
        self.assertEqual(obj.releases, [{'type': 'KEY_RELEASE', 'code': 16}])

    def test_held_shift_does_not_exit_hand_scroll(self):
        obj = self.reconcile([16, 81], {16, 81})
        self.assertEqual(obj.releases, [])
        self.assertEqual(obj.keyStack, [16, 81])

    def test_current_keyup_is_left_to_original_other_lost_keys_notified(self):
        obj = self.reconcile([16, 18], set(), releasing=True, current=18)
        self.assertEqual(obj.releases, [{'type': 'KEY_RELEASE', 'code': 16}])

    def test_cancel_bar_does_not_use_shot_or_ack(self):
        events = []
        loc = NS(dispatchEvent=events.append)
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={})))
        self.assertEqual(events, [dict(type='moveWalker', id=0)])

    def test_stop_walk_uses_no_fifo_skip(self):
        events = []
        cells = {1: NS(busy=True), 2: NS(busy=False)}
        walker = NS(prevNumPos=1, numPos=1)

        def stop(pos):
            events.append(('stop', pos))
            walker.numPos = pos
        walker.breakMove = stop
        loc = NS(getWalker=lambda _: walker, getCellFromNumber=cells.get, dispatchEvent=events.append)
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={'pos': 2})))
        self.assertFalse(cells[1].busy)
        self.assertTrue(cells[2].busy)
        self.assertEqual(events[0], ('stop', 2))

    def test_hooks_in_injection(self):
        blob = w.injected()
        for name in ('__keysDownOrig', '__keysUpOrig', '__actionInitOrig', '__actionKillOrig', '__actionCancel'):
            self.assertIn(name.encode(), blob)

    def test_remote_stop_does_not_clear_own_bar(self):
        events = []
        cells = {1: NS(busy=True), 2: NS(busy=False)}
        walker = NS(prevNumPos=1, numPos=1)
        walker.breakMove = lambda pos: setattr(walker, 'numPos', pos)
        loc = NS(getWalker=lambda ident: walker if ident == 42 else None, getCellFromNumber=cells.get, dispatchEvent=events.append)
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={'id': 42, 'pos': 2})))
        self.assertEqual(events, [])
        self.assertEqual(walker.numPos, 2)

    def test_movement_cancel_releases_old_item_latch(self):
        calls = []
        loc = NS(master=NS(gamer=NS(itemActivator=NS(breakAction=lambda: calls.append('release')))), dispatchEvent=lambda event: calls.append(event))
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={'release': 1})))
        self.assertEqual(calls, ['release', dict(type='moveWalker', id=0)])

    def test_replacement_ack_keeps_original_handler_and_opens_next_request(self):
        obj = NS(coolDownBlock=True)
        calls = []
        setattr(obj, '__actionAckOrig', lambda response: calls.append(response))
        response = NS(param={'res': 0})
        execute(w.fn_action_use_ack().assemble(), dict(this=obj, obj=response))
        self.assertEqual(calls, [response])
        self.assertFalse(obj.coolDownBlock)

    def test_cancel_listener_lifecycle(self):
        calls = []
        handler = lambda obj: None
        loc = NS(XMC=NS(addEventListener=lambda *args: calls.append(('add', args)), removeEventListener=lambda *args: calls.append(('remove', args))))
        loc.orig = lambda: calls.append(('original', ()))
        env = dict(this=loc, _global=NS(__actionCancel=handler, __actionStart=handler))
        execute(w.fn_action_listener('orig').assemble(), env)
        execute(w.fn_action_listener('orig', remove=True).assemble(), env)
        self.assertEqual([c[0] for c in calls], ['original', 'add', 'add', 'remove', 'remove', 'original'])
        self.assertEqual(calls[1][1], calls[3][1])
        self.assertEqual(calls[2][1], calls[4][1])

    def test_confirmed_heal_restores_bar_after_replacement_cancel(self):
        old = NS(name='old medicine')
        accepted = NS(name='accepted medicine')
        state = NS(active=True, item=old)

        def dispatch(event):
            if event['type'] == 'HEAL':
                state.active = True
                state.item = event['param']
        loc = NS(dispatchEvent=lambda event: setattr(state, 'active', False), master=NS(gamer=NS(dispatchEvent=dispatch)))
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={'release': 0})))
        self.assertFalse(state.active)
        factory = NS(getItem=lambda oid: accepted if oid == 'accepted-id' else None)
        glob = NS(lol=NS(core=NS(objects=NS(ItemFactory=factory))))
        execute(w.fn_action_start().assemble(), dict(this=loc, obj=NS(param={'heal_obj': 'accepted-id'}), _global=glob))
        self.assertTrue(state.active)
        self.assertIs(state.item, accepted)

    def test_unknown_heal_item_does_not_start_a_bar(self):
        events = []
        loc = NS(master=NS(gamer=NS(dispatchEvent=events.append)))
        glob = NS(lol=NS(core=NS(objects=NS(ItemFactory=NS(getItem=lambda _: None)))))
        execute(w.fn_action_start().assemble(), dict(this=loc, obj=NS(param={'heal_obj': 'gone'}), _global=glob))
        self.assertEqual(events, [])

    def test_local_heal_attempt_does_not_replace_confirmed_bar(self):
        calls = []
        bar = NS(startTimeBar=lambda value: calls.append(('duration', value)))
        setattr(bar, '__confirmedHealOrig', lambda obj: calls.append(('start', obj.param)))
        execute(w.fn_confirmed_heal_bar().assemble(), dict(this=bar, obj=NS(param='rejected medicine')))
        self.assertEqual(calls, [])
        execute(w.fn_confirmed_heal_bar().assemble(), dict(this=bar, obj=NS(param='accepted medicine', confirmed=True, duration=700)))
        self.assertEqual(calls, [('start', 'accepted medicine'), ('duration', 700)])

    def test_cancelled_aim_lowers_remote_gun_without_touching_own_bar(self):
        walker = NS(behavior='fire_in', burstArr=Arr(['stale']), fireCount=3, __fireCount=3)
        scene = NS(getWalker=lambda ident: walker if ident == 42 else None)
        own_bar = []

        def dispatch(event):
            if event['type'] == 'cancelAim':
                execute(w.fn_scene_cancel_aim().assemble(), dict(this=scene, obj=NS(**event)))
            else:
                own_bar.append(event)
        loc = NS(dispatchEvent=dispatch)
        execute(w.fn_action_cancel().assemble(), dict(this=loc, obj=NS(param={'id': 42, 'stop_aim': 1})))
        self.assertEqual(walker.behavior, 'fire_out')
        self.assertEqual(walker.burstArr, [])
        self.assertEqual(walker.fireCount, 0)
        self.assertEqual(own_bar, [])

    def test_cancelled_aim_does_not_override_running_or_dead_characters(self):
        for behavior in ('run', 'die', 'damage'):
            walker = NS(behavior=behavior)
            execute(w.fn_scene_cancel_aim().assemble(), dict(this=NS(getWalker=lambda _: walker), obj=NS(id=42)))
            self.assertEqual(walker.behavior, behavior)

    def test_scene_aim_listener_lifecycle(self):
        calls = []
        handler = lambda obj: None
        scene = NS(currentLocation=NS(addEventListener=lambda *a: calls.append(('add', a)), removeEventListener=lambda *a: calls.append(('remove', a))))
        scene.orig = lambda: calls.append(('original', ()))
        env = dict(this=scene, _global=NS(__sceneCancelAim=handler))
        execute(w.fn_scene_action_listener('orig').assemble(), env)
        execute(w.fn_scene_action_listener('orig', remove=True).assemble(), env)
        self.assertEqual([c[0] for c in calls], ['original', 'add', 'remove', 'original'])
        self.assertEqual(calls[1][1], calls[2][1])
if __name__ == '__main__':
    run_cases(ClientActions)
