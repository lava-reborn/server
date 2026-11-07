"""Execute server slot quotes in AVM1 without a running Flash client."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Function
from testkit import run_cases
import widescreen as w
from spec_access_client import patches


class SpecAccessClient(unittest.TestCase):
    def setUp(self):
        self.env = dict(_global={}, Number=float)
        self.functions = {}
        for name, args, body in patches(w.Asm, w.UNDEF)['globals']:
            self.functions[name] = Function(args, body.assemble(), self.env)

    def call(self, name, obj, *args):
        return self.functions[name].invoke(obj, args)

    def test_any_choice_uses_same_vacant_slot_quote(self):
        attrs = dict(__saSlots=3, __saAfro=0, __saGold=0)
        training = dict(master=dict(gamer=dict(attributes=attrs)))
        for idx in range(12):
            training['__saSelected'] = idx
            self.assertEqual(self.call('__saCost', training), dict(cost=0, type='afro'))
        attrs['__saGold'] = 3000
        self.assertEqual(self.call('__saCost', training), dict(cost=30, type='gold'))

    def test_free_slot_quote_replaces_previous_price_before_redraw(self):
        seen = []
        attrs = dict(__saSlots=3, __saAfro=0, __saGold=5500)
        attrs['__saAttributesOrig'] = lambda obj: seen.append((attrs['__saSlots'], attrs['__saAfro'], attrs['__saGold']))
        self.call('__saAttributes', attrs, dict(param=dict(spec_slots=3, spec_next_afro=0, spec_next_gold=0)))
        self.assertEqual(seen, [(3, 0, 0)])
        training = dict(master=dict(gamer=dict(attributes=attrs)))
        self.assertEqual(self.call('__saCost', training), dict(cost=0, type='afro'))

    def test_afro_capacity_expansion_quote_uses_afro(self):
        training = dict(master=dict(gamer=dict(attributes=dict(__saSlots=1, __saAfro=1000, __saGold=0))))
        self.assertEqual(self.call('__saCost', training), dict(cost=1000, type='afro'))

    def test_server_without_new_fields_keeps_original_price_method(self):
        training = dict(master=dict(gamer=dict(attributes={})), __saCostOrig=lambda: dict(cost=55, type='gold'))
        self.assertEqual(self.call('__saCost', training), dict(cost=55, type='gold'))


if __name__ == '__main__':
    run_cases(SpecAccessClient)
