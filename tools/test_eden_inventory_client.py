"""Execute Eden refresh bytecode and preserve the native ss_ack FIFO."""
from collections import Counter
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import Arr, Function
from eden_inventory_client import patches
from testkit import run_cases


class EdenInventoryClientTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.fifo = Arr(['existing-bank-read', 'existing-inspect-read'])
        self.items = Arr([dict(id='own-gun'), dict(id='own-armour')])
        self.equipment = dict(first=True, bag=dict(itemList=self.items), getStuff=self.get_stuff)
        self.master = dict(gamer=dict(equipment=self.equipment),
                           __edInventoryEnterOrig=self.enter_native,
                           __edInventoryCloseOrig=lambda: self.calls.append('native-close'))
        self.updates = []
        self.inspector = dict(currentQuests={}, cqList={}, checkedQuests={},
                              closedQuest=None, questUpdate=lambda: self.updates.append('update'))
        self.env = dict(lol=dict(core=dict(Master=dict(getInstance=lambda: self.master),
            quests=dict(QuestInspector=dict(getInstance=lambda: self.inspector)))))
        self.methods = {method: Function(params, body.assemble(), self.env)
                        for _path, method, _keep, params, body in patches(w.Asm, w.UNDEF)['wraps']}
        self.connection = dict(__edInventoryNotifyOrig=lambda cmd: self.calls.append(('notification', cmd)))

    def get_stuff(self, mask, target):
        self.calls.append(('request', mask, target))
        self.fifo.push(('ss_ack', mask, target))

    def enter_native(self, obj):
        self.calls.append(('native-lenter', obj))
        if not self.equipment['first']:
            self.equipment['first'] = True
            self.get_stuff(11, 0)

    def notify(self, name='eden_inv', **params):
        self.methods['sendNotification'].invoke(self.connection, [dict(messID=name, params=params)])

    def enter(self):
        self.methods['lenter'].invoke(self.master, [dict(param=dict(pos=1))])

    def test_ordinary_notifications_and_location_entries_leave_the_native_cache_alone(self):
        for name, params in (('lch', dict(refresh=1)), ('eden_inv', dict(refresh=0)),
                             ('eden_inv', {})):
            self.notify(name, **params)
            self.enter()
        self.assertFalse(any(isinstance(c, tuple) and c[0] == 'request' for c in self.calls))
        self.assertEqual(self.fifo, ['existing-bank-read', 'existing-inspect-read'])
        self.assertIs(self.equipment['bag']['itemList'], self.items)
        self.assertEqual([item['id'] for item in self.items], ['own-gun', 'own-armour'])

    def test_committed_refresh_waits_for_lenter_and_queues_one_native_masked_read(self):
        self.notify(refresh=1)
        self.assertEqual(len(self.fifo), 2)
        self.enter()
        self.assertEqual(self.calls[-2][0], 'native-lenter')
        self.assertEqual(self.calls[-1], ('request', 11, 0))
        self.assertEqual(self.fifo, ['existing-bank-read', 'existing-inspect-read', ('ss_ack', 11, 0)])
        self.assertFalse(self.master['__edEquipmentPending'])
        self.enter()
        self.assertEqual(len(self.fifo), 3)

    def test_repeated_assignment_and_release_refresh_each_new_authoritative_inventory(self):
        for _ in range(4):
            self.notify(refresh=1)
            self.enter()
        self.assertEqual(self.fifo[2:], [('ss_ack', 11, 0)] * 4)
        self.assertEqual([item['id'] for item in self.items], ['own-gun', 'own-armour'])

    def test_fresh_gamer_uses_its_native_first_request_without_a_duplicate(self):
        self.equipment['first'] = False
        self.notify(refresh=1)
        self.enter()
        self.assertEqual(self.fifo[2:], [('ss_ack', 11, 0)])
        self.assertFalse(self.master['__edEquipmentPending'])

    def test_multiple_refresh_frames_before_entry_coalesce_without_extra_acks(self):
        for _ in range(5):
            self.notify(refresh=1)
        self.enter()
        self.assertEqual(self.fifo[2:], [('ss_ack', 11, 0)])

    def test_socket_close_cancels_pending_refresh_and_preserves_native_close(self):
        self.notify(refresh=1)
        self.methods['onClose'].invoke(self.master, [])
        self.assertEqual(self.calls[-1], 'native-close')
        self.assertFalse(self.master['__edEquipmentPending'])
        self.enter()
        self.assertEqual(len(self.fifo), 2)

    def test_release_removes_only_local_tasks_and_refreshes_the_open_journal(self):
        ordinary = dict(typeID=777, complete=True)
        self.inspector['currentQuests'] = {2_000_000_000: dict(typeID=18114),
                                           9: ordinary, 72: dict(typeID=18110), 73: None}
        self.inspector['cqList'] = {18114: 2_000_000_000, 18110: 72, 777: 9}
        self.inspector['checkedQuests'] = {18114: True, 18110: True, 777: True}
        self.inspector['closedQuest'] = 18114
        before_fifo = list(self.fifo)
        self.notify(refresh=1, clear_eden=1, q_types=Arr([18110, 18114]))
        self.assertEqual(self.inspector['currentQuests'], {9: ordinary, 73: None})
        self.assertIs(self.inspector['currentQuests'][9], ordinary)
        self.assertEqual(self.inspector['cqList'], {777: 9})
        self.assertEqual(self.inspector['checkedQuests'], {777: True})
        self.assertIsNone(self.inspector['closedQuest'])
        self.assertEqual(self.updates, ['update'])
        self.assertEqual(self.fifo, before_fifo)  # No q_ca or unsolicited cmdAck.
        self.notify(refresh=1, clear_eden=1, q_types=Arr([18110, 18114]))
        self.assertEqual(self.updates, ['update'])

    def test_assignment_refresh_keeps_an_existing_journal_untouched(self):
        task = dict(typeID=18114)
        self.inspector['currentQuests'][81] = task
        self.notify(refresh=1)
        self.enter()
        self.assertIs(self.inspector['currentQuests'][81], task)
        self.assertEqual(self.updates, [])

    def test_build_includes_the_hook_with_training_enabled_or_disabled(self):
        for enabled in (False, True):
            code = w.injected(training=enabled)
            self.assertIn(b'eden_inv\0', code)
            self.assertIn(b'__edInventoryEnterOrig\0', code)
            self.assertIn(b'__edInventoryNotifyOrig\0', code)

    def test_complete_doaction_opcode_counter_recognizes_the_sparse_iteration(self):
        self.assertEqual((w.OPS['enumerate2'], w.OPS['stackswap']), (0x55, 0x4D))
        for enabled in (False, True):
            # Use the complete assembled DoAction, not only our helper: this
            # is the same reader/whitelist that final SWF verify() runs.
            ops = Counter(w.disassemble(w.injected(training=enabled)))
            self.assertEqual(ops['enumerate2'], 1)
            self.assertEqual(ops['stackswap'], 1)
            self.assertFalse([op for op in ops if op.startswith('0x')])


if __name__ == '__main__':
    run_cases(EdenInventoryClientTests)
