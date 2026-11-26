"""Execute the player-menu bridge: no left clicks, NPC menus or combat actions."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Function
from right_click_client import patches
from testkit import run_cases
import widescreen as w


class RightClickClient(unittest.TestCase):
    def setUp(self):
        self.key = 135
        self.env = dict(Key=dict(getCode=lambda: self.key),
                        lol=dict(core=dict(player=dict(Gamer=dict(ID=0)))))
        self.functions = {(path[-1], method): Function(args, body.assemble(), self.env)
                          for path, method, keep, args, body in patches(w.Asm, w.UNDEF)['wraps']}

    def call(self, cls, method, obj, *args):
        return self.functions[(cls, method)].invoke(obj, args)

    def test_player_identity_is_marked_without_changing_native_info(self):
        event = dict(param=dict(id=7))
        received = []
        player = dict(__rcPlayerInfoOrig=received.append)
        self.call('Player', 'userInfo', player, event)
        self.assertTrue(player['__rcPlayer'])
        self.assertEqual(received, [event])

    def test_right_click_opens_the_native_menu_for_the_hovered_player_only(self):
        received = []
        player = dict(id=7, __rcPlayer=True)
        manager = dict(activated=True, flared=dict(target=dict(driver=player)))
        manager['createContextMenu'] = lambda: received.append(manager['contextMenuPlayer'])
        cursor = dict(sfManager=manager, __rcKeyDownOrig=lambda: received.append('unexpected action'))
        self.call('CursorManager', 'onKeyDown', cursor)
        self.assertEqual(received, [player])

    def test_self_npc_missing_target_and_disabled_focus_do_nothing(self):
        for target in (None, dict(driver=None), dict(driver=dict(id=0, __rcPlayer=True)),
                       dict(driver=dict(id=7)), dict(driver=dict(id=7, __rcPlayer=False))):
            events = []
            manager = dict(activated=True, flared=dict(target=target), createContextMenu=lambda: events.append('menu'))
            cursor = dict(sfManager=manager, __rcKeyDownOrig=lambda: events.append('action'))
            self.call('CursorManager', 'onKeyDown', cursor)
            self.assertEqual(events, [])
        for manager in (None, dict(activated=False), dict(activated=True, flared=None)):
            self.call('CursorManager', 'onKeyDown', dict(sfManager=manager))

    def test_bridge_does_not_trigger_hotkeys_or_keyup_cursor_changes(self):
        for cls, method, saved in (('CursorManager','onKeyUp','__rcKeyUpOrig'),
                                   ('HotKeyManager','onKeyDown','__rcHotDownOrig'),
                                   ('HotKeyManager','onKeyUp','__rcHotUpOrig')):
            events = []
            obj = {saved: lambda: events.append('native')}
            self.call(cls, method, obj)
            self.assertEqual(events, [])
            self.key = 65
            self.call(cls, method, obj)
            self.assertEqual(events, ['native'])
            self.key = 135
        events = []
        self.key = 16
        self.call('CursorManager', 'onKeyDown', dict(__rcKeyDownOrig=lambda: events.append('shift')))
        self.assertEqual(events, ['shift'])


if __name__ == '__main__':
    run_cases(RightClickClient)
