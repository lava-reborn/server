"""Execute loot shortcut AVM1, including modal and in-flight request guards."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Arr, Function
from testkit import run_cases
import widescreen as w
from loot_controls_client import patches


class LootControls(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.keys = dict(enabled=True, checkFilter=lambda name: name == 'loot',
                         addEventListener=lambda *a: self.calls.append(('add', a)),
                         removeEventListener=lambda *a: self.calls.append(('remove', a)))
        self.env = dict(_global={}, lol=dict(
            core=dict(SceneShifter=dict(hotKeyManager=self.keys), player=dict(Loot=dict(UPD_GET_ALL=3))),
            data=dict(BigUINT=lambda v: v, BigUINTCluster=lambda v: v),
            server=dict(mess=dict(CSM_SSUpdate=lambda code, obj: (code, obj)),
                        XMLCCallStack=dict(addCall=lambda *a: self.calls.append(('ack', a))))))
        self.functions = {}
        for name, params, body in patches(w.Asm, w.UNDEF)['globals']:
            fn = Function(params, body.assemble(), self.env)
            self.functions[name] = self.env['_global'][name] = fn

    def call(self, name, owner, *args):
        return self.functions[name].invoke(owner, args)

    def test_default_is_a_native_configurable_setting(self):
        owner = dict(hotKeyArr={}, __lootDefaultsOrig=lambda: self.calls.append('native'))
        self.call('__lootDefaults', owner)
        self.assertEqual(owner['hotKeyArr']['LOOT_TAKE_ALL']['keyCode'], [69])
        self.assertEqual(owner['hotKeyArr']['LOOT_TAKE_ALL']['about'], 'Взять всё из мешка')
        self.assertEqual(self.calls, ['native'])

    def test_only_loot_filter_gets_the_new_action(self):
        owner = dict(lootArr=Arr(), locationArr=Arr(), __lootFiltersOrig=lambda: None)
        self.call('__lootFilters', owner)
        self.assertEqual(owner['lootArr'], ['LOOT_TAKE_ALL'])
        self.assertEqual(owner['locationArr'], [])

    def test_input_and_other_modal_windows_block_take_all(self):
        panel = dict(loot=dict(status=True), transferAll=lambda: self.calls.append('take'))
        self.call('__lootTakeKey', panel)
        self.keys['enabled'] = False
        self.call('__lootTakeKey', panel)
        self.keys.update(enabled=True, checkFilter=lambda name: False)
        self.call('__lootTakeKey', panel)
        self.keys['checkFilter'] = lambda name: True
        panel['loot']['status'] = False
        self.call('__lootTakeKey', panel)
        self.assertEqual(self.calls, ['take'])

    def test_repeat_request_waits_for_ack_and_failure_allows_retry(self):
        owner = dict(status=True, XMC=dict(Send=lambda msg: self.calls.append(msg) or True),
                     allTranferAck=lambda obj: None, __lootTransferAckOrig=lambda obj: None)
        self.call('__lootTransferAll', owner)
        self.call('__lootTransferAll', owner)
        self.assertEqual(len(self.calls), 2)  # one message, one registered ack
        self.call('__lootTransferAck', owner, dict(param=dict(res=1)))
        self.call('__lootTransferAll', owner)
        self.assertEqual(len(self.calls), 4)

    def test_failed_send_does_not_leave_pending_command(self):
        owner = dict(status=True, XMC=dict(Send=lambda msg: False))
        self.call('__lootTransferAll', owner)
        self.assertFalse(owner.get('__lootTakePending'))
        self.assertEqual(self.calls, [])

    def test_close_removes_keyboard_and_transfer_listeners(self):
        panel = dict(loot=dict(removeEventListener=lambda *a: self.calls.append(('loot', a))),
                     transferAllOk=lambda: None, __lootKillOrig=lambda: self.calls.append('kill'))
        self.call('__lootKill', panel)
        self.assertEqual([c[0] if isinstance(c, tuple) else c for c in self.calls],
                         ['remove', 'loot', 'kill'])


if __name__ == '__main__':
    run_cases(LootControls)
