"""Execute emitted range hooks without Flash, networking or battle simulations."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import Arr, Function
from testkit import run_cases
from weapon_range_client import patches


class WeaponRangeClient(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.values = dict(cur_mode=2, max_range=Arr([8, 0, 42]),
                           opt_range=Arr([3, 0, 28]), end_opt_range=Arr([6, 0, 38]),
                           ammo_type=6107)
        self.item = dict(rootID=0, getProp=self.values.get)
        self.distance = 40.0
        self.own, self.mark = dict(rx=0, ry=0), dict(rx=40, ry=0)
        self.walker = dict(numPos=2)
        self.location = dict(
            getCellFromNumber=lambda number: self.own if number == 1 else self.mark,
            getCellFromReal=lambda x, y: self.mark,
            getWalker=lambda identifier: self.walker if identifier == 9 else None,
            locationGrid=dict(getHexDistance=lambda a, b: self.distance))
        self.master = dict(gamer=dict(walker=dict(numPos=1), equipment=dict(primaryItem=self.item)),
                           currentLocation=self.location)
        self.prototypes = {6107: dict(item=dict(getProp=lambda key: 1 if key == 'range_mod' else None))}

        def number(value):
            return float('nan') if value is None else float(value)

        self.env = dict(_global={}, Number=number, isNaN=math.isnan, Math=dict(floor=math.floor),
                        lol=dict(core=dict(Master=dict(getInstance=lambda: self.master),
                                           objects=dict(Item=dict(FIRE_ARM=0),
                                                        ItemFactory=dict(itemTypeStore=self.prototypes)))))
        self.functions = {}
        spec = patches(w.Asm, w.UNDEF)
        for name, args, body in spec['globals']:
            function = Function(args, body.assemble(), self.env)
            self.env['_global'][name] = self.functions[name] = function
        self.auto = dict(autoFireTargetID=9, __wrAutoDistanceOrig=lambda: self.calls.append('native-auto') or True)

    def call(self, name, target, *args):
        return self.functions[name].invoke(target, args)

    def cursor(self, *, flared=True):
        colors = []
        text = dict(text='', setTextFormat=lambda style: colors.append(style['color']))
        panel = dict(target=dict(master=self.master), currentCursor=dict(_x=3, _y=4),
                     sfManager=dict(flared=dict(target=dict(id=9)) if flared else None),
                     tf=dict(color=123), distance_txt=text)

        def native():
            self.calls.append('native-cursor')
            text['text'] = format(math.floor(self.distance * 10) / 10, '.1f')
            panel['tf']['color'] = 123

        panel['__wrCursorDistanceOrig'] = native
        return panel, text, colors

    def test_exact_outside_range_is_red_even_when_native_text_rounds_down(self):
        self.distance = math.sqrt(1767)  # 42.035699: valid hex offset (42, 2).
        panel, text, colors = self.cursor()
        self.call('__wrCursorDistance', panel)
        self.assertEqual(text['text'], '42.0')
        self.assertEqual(colors, [16711680])
        self.assertFalse(self.call('__wrAutoDistance', self.auto))
        self.assertEqual(self.calls, ['native-cursor'])

    def test_exact_maximum_remains_in_range_and_optimal_band_uses_unrounded_distance(self):
        for distance, expected in ((42, 16777215), (38, 65280), (38.0357, 16777215), (27.99, 16777215)):
            with self.subTest(distance=distance):
                self.distance = distance
                panel, text, colors = self.cursor()
                self.call('__wrCursorDistance', panel)
                self.assertEqual(colors, [expected])
                self.assertTrue(self.call('__wrAutoDistance', self.auto))

    def test_auto_fire_checks_current_mode_instead_of_always_using_short_mode(self):
        self.distance = 40
        self.assertTrue(self.call('__wrAutoDistance', self.auto))
        self.values['cur_mode'] = 0
        self.assertFalse(self.call('__wrAutoDistance', self.auto))
        self.values['cur_mode'] = 2
        self.assertTrue(self.call('__wrAutoDistance', self.auto))
        self.assertEqual(self.calls, [])

    def test_loaded_ammo_range_is_floored_once_without_changing_optimal_band(self):
        self.values['ammo_type'] = 6167
        self.prototypes[6167] = dict(item=dict(getProp=lambda key: 1.1))
        self.assertEqual(self.call('__wrWeaponRange', None, self.item), dict(maximum=46, mode=2))
        for distance, expected in ((46, True), (46.01, False)):
            self.distance = distance
            self.assertEqual(self.call('__wrAutoDistance', self.auto), expected)
        self.distance = 40
        panel, _, colors = self.cursor(flared=False)
        self.call('__wrCursorDistance', panel)
        self.assertEqual(colors, [16777215])  # 38 stays the optimal end.
        self.values['cur_mode'] = 0
        self.assertEqual(self.call('__wrWeaponRange', None, self.item), dict(maximum=8, mode=0))

    def test_missing_ammo_metadata_uses_base_range_without_creating_or_requesting_items(self):
        for cached in (None, dict(item=None), dict(item=dict(getProp=lambda key: None)),
                       dict(item=dict(getProp=lambda key: 0))):
            with self.subTest(cached=cached):
                self.prototypes[6107] = cached
                self.assertEqual(self.call('__wrWeaponRange', None, self.item), dict(maximum=42, mode=2))
        self.assertEqual(self.values['ammo_type'], 6107)
        self.assertEqual(self.calls, [])

    def test_missing_target_is_not_in_range_and_non_firearms_keep_native_gate(self):
        self.auto['autoFireTargetID'] = 999
        self.assertFalse(self.call('__wrAutoDistance', self.auto))
        self.item['rootID'] = 5
        self.assertTrue(self.call('__wrAutoDistance', self.auto))
        panel, _, colors = self.cursor()
        self.call('__wrCursorDistance', panel)
        self.assertEqual(colors, [])
        self.assertEqual(self.calls, ['native-auto', 'native-cursor'])

    def test_private_range_profiles_keep_original_distance_methods_and_ammo_equations(self):
        self.env['_global']['__tgActive'] = True
        self.distance = 100
        self.assertTrue(self.call('__wrAutoDistance', self.auto))
        panel, _, colors = self.cursor()
        self.call('__wrCursorDistance', panel)
        self.assertEqual(colors, [])
        self.assertEqual(self.calls, ['native-auto', 'native-cursor'])

    def test_only_two_native_range_methods_are_wrapped(self):
        spec = patches(w.Asm, w.UNDEF)
        self.assertEqual([(path, method) for path, method, *_ in spec['wraps']], [
            (('core', 'location', 'CursorManager'), 'calcDistance'),
            (('services', 'AutoCommandManager'), 'checkDistance')])


if __name__ == '__main__':
    run_cases(WeaponRangeClient)
