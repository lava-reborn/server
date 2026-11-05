"""Small build-time contracts for native training-window hooks."""
import re
from pathlib import Path
import unittest

import training_ground_client as client
import widescreen


class TrainingClient(unittest.TestCase):
    def test_all_prototype_hooks_match_existing_game_methods(self):
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        root = Path(__file__).resolve().parents[1] / 'recon/as-src/lol'
        for path, method, _, params, body in package['wraps']:
            with self.subTest(path=path, method=method):
                source = (root.joinpath(*path).with_suffix('.as')).read_text(encoding='utf-8')
                match = re.search(r'function\s+' + re.escape(method) + r'\(([^)]*)\)', source)
                self.assertIsNotNone(match)
                native = [part for part in match[1].split(',') if part.strip()]
                self.assertEqual(len(params), len(native))
                self.assertTrue(body.assemble())

    def test_profile_and_button_objects_use_literal_field_names(self):
        import ast
        tree = ast.parse(client.SOURCE)
        count = 0
        for obj in ast.walk(tree):
            if isinstance(obj, ast.Dict):
                for key in obj.keys:
                    self.assertIsInstance(key, ast.Constant)
                    self.assertIsInstance(key.value, str)
                    count += 1
        self.assertGreater(count, 15)

    def helpers(self, env):
        from avm_test import Function
        functions = {}
        for name, args, body in client.patches(widescreen.Asm, widescreen.UNDEF)['globals']:
            fn = Function(args, body.assemble(), env)
            env['_global'][name] = functions[name] = fn
        return functions

    def test_center_and_clamp_use_original_movie_origin(self):
        env = dict(_global={}, Stage=dict(width=1920, height=1080),
                   Math=dict(round=round, max=max, min=min),
                   lol=dict(core=dict(SceneShifter=dict(_ref=dict(minW=950, minH=650)))))
        funcs = self.helpers(env)
        panel = dict(__w=1040, __h=640, _x=0, _y=0)
        funcs['__tgLayout'].invoke(None, [panel, True])
        self.assertEqual((panel['_x'], panel['_y']), (-45, 5))
        panel.update(_x=9999, _y=-9999)
        funcs['__tgLayout'].invoke(None, [panel, False])
        self.assertEqual((panel['_x'], panel['_y']), (387, -207))

    def test_training_and_restore_snapshots_do_not_emit_xp_but_real_gains_do(self):
        env = dict(_global=dict(__tgActive=True))
        funcs = self.helpers(env)
        messages, values = [], []
        attrs = dict(__progressLoaded=True)
        def native(obj):
            values.append(obj['xp'])
            if attrs['__progressLoaded']:
                messages.append(obj['xp'])
            attrs['__progressLoaded'] = True
        attrs['__tgStatsOrig'] = native
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=0)])
        env['_global'].update(__tgActive=False, __tgSnapshotPending=True)
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=10398)])
        funcs['__tgStatsWrapper'].invoke(attrs, [dict(xp=10418)])
        self.assertEqual(values, [0, 10398, 10418])
        self.assertEqual(messages, [10418])
        self.assertFalse(env['_global']['__tgSnapshotPending'])

    def test_equipment_is_refreshed_once_per_clone_revision_after_loading(self):
        from avm_test import Arr
        class IDs(Arr):
            def join(self, sep):
                return sep.join(self)
        calls = []
        gamer = dict(equipment=dict(getStuff=lambda *args: calls.append(args)),
                     apManager=dict(setAP=lambda *args: None))
        env = dict(_global={}, lol=dict(core=dict(Master=dict(getInstance=lambda: dict(gamer=gamer)))))
        funcs = self.helpers(env)
        v = dict(loaded=0, live_oids=IDs(['copy-1']), regen=2.5, ap=136)
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [])
        v['loaded'] = 1
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [(11, 0)])
        v['live_oids'] = IDs(['copy-2'])
        funcs['__tgRefreshEquipment'].invoke(None, [v, False])
        self.assertEqual(calls, [(11, 0), (11, 0)])

    def test_exit_zones_removed_only_from_private_training_descriptions(self):
        info = dict(zones=[dict(x=1, y=2)], pvpEnabled=False)
        env = dict(_global={})
        funcs = self.helpers(env)
        parser = dict(__tgParseOrig=lambda doc: dict(info))
        ordinary = funcs['__tgParse'].invoke(parser, [None])
        self.assertEqual(ordinary, info)
        env['_global']['__tgActive'] = True
        private = funcs['__tgParse'].invoke(parser, [None])
        self.assertEqual(private['zones'], [])
        self.assertTrue(private['pvpEnabled'])
        self.assertEqual(info['zones'], [dict(x=1, y=2)])

    def test_return_refreshes_real_equipment_after_native_location_entry(self):
        calls = []
        env = dict(_global=dict(__tgReturnEquipment=True, __rfRepairKeys=lambda: True))
        funcs = self.helpers(env)
        owner = dict(__tgEnterOrig=lambda obj: calls.append('entered'),
                     gamer=dict(equipment=dict(getStuff=lambda *args: calls.append(args))))
        funcs['__tgEnterWrapper'].invoke(owner, [None])
        funcs['__tgEnterWrapper'].invoke(owner, [None])
        self.assertEqual(calls, ['entered', (11, 0), 'entered'])
        self.assertFalse(env['_global']['__tgReturnEquipment'])

    def test_managed_full_bag_snapshot_replaces_old_rows_with_native_removal_events(self):
        import math
        from avm_test import Arr
        removed, detached = [], []
        old = [dict(id='real-old'), dict(id='training-old')]
        for item in old:
            item['removeEventListener'] = lambda *args: detached.append(args)
        bag = dict(itemList=Arr(old))
        fresh = dict(id='real-current')
        eq = dict(isGamer=True, __tgManaged=True, __tgReplaceBag=True, bag=bag, slots_arr=Arr(), action_arr=Arr())
        def remove(slot, item):
            self.assertIs(slot, bag)
            self.assertEqual(bag['itemList'], [])
            removed.append(item['id'])
        def native(obj):
            bag['itemList'].append(fresh)
        eq.update(removeItem=remove, __tgEquipOrig=native)
        env = dict(_global=dict(__tgActive=False), Number=float, Math=dict(floor=math.floor))
        funcs = self.helpers(env)
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=11)])
        self.assertEqual(removed, ['real-old', 'training-old'])
        self.assertEqual(len(detached), 2)
        self.assertEqual(bag['itemList'], [fresh])
        self.assertEqual([i['id'] for i in old], ['real-old', 'training-old'])

    def test_late_snapshot_cannot_replace_bag_after_training_boundary(self):
        received = []
        env = dict(_global=dict(__tgEpoch=3), Boolean=bool)
        funcs = self.helpers(env)
        eq = dict(ss_ack=received.append)
        funcs['__tgSnapshotAck'].invoke(eq, [dict(data=dict(mask=11, epoch=2), param=dict(o_list=['copy']))])
        self.assertEqual(received, [])
        funcs['__tgSnapshotAck'].invoke(eq, [dict(data=dict(mask=11, epoch=3), param=dict(o_list=['real']))])
        self.assertEqual(received, [dict(data=11, param=dict(o_list=['real']))])

    def test_late_item_initialization_cannot_reinsert_retired_training_copy(self):
        calls, detached = [], []
        item = dict(id='copy-old', typeID=54000, removeEventListener=lambda *args: detached.append(args))
        eq = dict(isGamer=True, __tgManaged=True, __tgBagUpdateOrig=calls.append)
        env = dict(_global=dict(__tgActive=False, __tgCopies={54000:26075}, __tgLive={}), Boolean=bool)
        funcs = self.helpers(env)
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [])
        self.assertEqual(len(detached), 1)
        env['_global']['__tgActive'] = True
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [])
        env['_global']['__tgLive']['copy-old'] = True
        funcs['__tgBagItemUpdate'].invoke(eq, [dict(target=item)])
        self.assertEqual(calls, [dict(target=item)])

    def test_ordinary_snapshot_after_training_does_not_rebuild_bag(self):
        from avm_test import Arr
        bag = dict(itemList=Arr([dict(id='real-item')]))
        called = []
        eq = dict(isGamer=True, __tgManaged=True, bag=bag, __tgEquipOrig=lambda obj: called.append(obj))
        funcs = self.helpers(dict(_global={}))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=11)])
        self.assertEqual(bag['itemList'], [dict(id='real-item')])
        self.assertEqual(len(called), 1)

    def test_partial_equipment_snapshot_keeps_bag(self):
        import math
        from avm_test import Arr
        bag = dict(itemList=Arr([dict(id='kept')]))
        eq = dict(isGamer=True, __tgManaged=True, __tgReplaceBag=True, bag=bag, slots_arr=Arr(), action_arr=Arr(), __tgEquipOrig=lambda obj: None)
        funcs = self.helpers(dict(_global={}, Number=float, Math=dict(floor=math.floor)))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=3)])
        self.assertEqual(bag['itemList'], [dict(id='kept')])

    def test_replacement_clears_empty_wear_and_hand_slots_before_native_snapshot(self):
        import math
        from avm_test import Arr
        removed = []
        primary = dict(item=dict(id='old-primary'))
        secondary = dict(item=dict(id='old-secondary'))
        helmet = dict(item=dict(id='old-helmet'))
        eq = dict(isGamer=True, __tgReplaceBag=True,
                  slots_arr=Arr([helmet]), action_arr=Arr([primary, secondary]))
        def remove(slot, item):
            removed.append(item['id'])
            slot['item'] = None
        def native(obj):
            self.assertIsNone(primary['item'])
            self.assertIsNone(secondary['item'])
            self.assertIsNone(helmet['item'])
        eq.update(removeItem=remove, __tgEquipOrig=native)
        funcs = self.helpers(dict(_global={}, Number=float, Math=dict(floor=math.floor)))
        funcs['__tgEquipWrapper'].invoke(eq, [dict(data=3)])
        self.assertEqual(removed, ['old-helmet', 'old-primary', 'old-secondary'])

    def test_closing_terminal_releases_only_its_filter_and_repairs_keys(self):
        events = []
        panel = dict(stopDrag=lambda: events.append('stop'), removeMovieClip=lambda: events.append('remove'))
        env = dict(_global=dict(__tgPanel=panel, __rfRepairKeys=lambda: events.append('keys')),
                   Stage=dict(removeListener=lambda p: events.append('stage')),
                   lol=dict(core=dict(SceneShifter=dict(hotKeyManager=dict(removeFilter=lambda key: events.append(key)))),
                            gpui=dict(HintManager=dict(closeHint=lambda: events.append('hint')))))
        funcs = self.helpers(env)
        funcs['__tgClose'].invoke(None, [])
        self.assertEqual(events, ['stop', 'stage', 'remove', 'tg', 'keys', 'hint'])
        self.assertIsNone(env['_global']['__tgPanel'])

    def test_whole_client_injection_builds_with_new_helpers(self):
        payload = widescreen.injected()
        self.assertIn(b'__tgInstall', payload)
        self.assertIn(b'__tgForgetItems', payload)
        self.assertIn('Учебный центр'.encode('utf-8'), payload)
        # A native DoAction is used; no browser or command-line UI dependency.
        self.assertNotIn(b'ExternalInterface', client.SOURCE.encode('utf-8'))


    def test_compiled_copy_guard_never_labels_normal_items_or_prototypes(self):
        from avm_test import execute
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        _, _, body = next(row for row in package['globals'] if row[0] == '__tgIsCopy')
        for item, expected in ((None, False), ({'id': 0, 'typeID': 54000}, False),
                               ({'id': 'abcd65db00', 'uID': float('nan'), 'typeID': 26075}, False),
                               ({'id': '10000000000d2f000', 'typeID': 54000}, True)):
            env = dict(item=item, Boolean=bool, _global={'__tgCopies': {54000: 26075}})
            self.assertEqual(execute(body.assemble(), env), expected)


if __name__ == '__main__':
    unittest.main()
