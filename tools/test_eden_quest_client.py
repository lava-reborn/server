"""Replay native status caching for Eden, lifts and warehouse gold rewards."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import quests
import widescreen as w
from avm_test import Arr, Function
from quest_window_client import patches
from testkit import run_cases


# Actual checkQStatus body from main.swf DoInitAction sprite3487 (161 bytes).
# Kept as a fixture so this regression needs neither Flash nor local assets.
# Only its existing constant-pool entries and implicit registers are supplied.
NATIVE_STATUS = bytes.fromhex(
    '960400040108204e96020004044e124c9d02001d0017960400040108214e'
    '96020004024e124c129d02000600179602000402129d0200690096040004'
    '0108204e960400040405014f9602000402129d0200100096040004010821'
    '4e960400040205014f9606000401082405014f9609000404070100000008'
    '011c96020008104e96020008304e9602000831538701000317960b000403'
    '0701000000040108255217')
POOL = {1: 'lol', 16: 'server', 32: 'checkedQuests', 33: 'checkedNPC',
        36: 'lockUpdate', 37: 'addCall', 48: 'mess', 49: 'CSM_QStatus'}


def native_status(inspector, quest_type, npc_id):
    """Execute this native function's instructions, including its real branches."""
    registers = {1: inspector, 2: npc_id, 4: quest_type}
    env = {'lol': {'server': {'mess': {'CSM_QStatus': lambda t: {'q_type': t}}}}}
    stack, at, steps = [], 0, 0
    while at < len(NATIVE_STATUS):
        steps += 1
        assert steps < 100, 'native read exceeded its instruction budget'
        op = NATIVE_STATUS[at]
        at += 1
        payload = b''
        if op >= 128:
            size, = struct.unpack_from('<H', NATIVE_STATUS, at)
            at += 2
            payload = NATIVE_STATUS[at:at + size]
            at += size
        if op == 0x96:
            i = 0
            while i < len(payload):
                kind = payload[i]
                i += 1
                if kind in (4, 8):
                    stack.append((registers if kind == 4 else POOL).get(payload[i]))
                    i += 1
                elif kind == 5:
                    stack.append(bool(payload[i]))
                    i += 1
                elif kind == 7:
                    stack.append(struct.unpack_from('<i', payload, i)[0])
                    i += 4
                else:
                    raise AssertionError(('unsupported native push', kind))
        elif op == 0x4E:
            key, obj = stack.pop(), stack.pop()
            stack.append(obj.get(key))
        elif op == 0x4F:
            value, key, obj = stack.pop(), stack.pop(), stack.pop()
            obj[key] = value
        elif op == 0x12:
            stack.append(not stack.pop())
        elif op == 0x4C:
            stack.append(stack[-1])
        elif op == 0x9D:
            if stack.pop():
                at += struct.unpack_from('<h', payload)[0]
        elif op == 0x17:
            stack.pop()
        elif op == 0x1C:
            stack.append(env[stack.pop()])
        elif op in (0x52, 0x53):
            method, obj, count = stack.pop(), stack.pop(), stack.pop()
            args = [stack.pop() for _ in range(count)]
            stack.append(obj[method](*args))
        elif op == 0x87:
            registers[payload[0]] = stack[-1]
        else:
            raise AssertionError(('unsupported native opcode', hex(op)))
    assert not stack, stack


class EdenQuestClient(unittest.TestCase):
    def setUp(self):
        self.reads, self.original_calls = [], []
        self.catalogue = {npc: (quests.given_by(npc), quests.taken_by(npc))
                          for npc in range(1784, 1790)}
        known = {q for give, take in self.catalogue.values() for q in give + take}
        self.pending = Arr([{'q_type': 777}])
        self.active = {22: {'type': 44}}
        self.inspector = dict(checkedQuests=dict.fromkeys(known | {777}, True),
                              checkedNPC={100: True}, currentQuests=self.active,
                              callStack=self.pending, callCount=1, closedQuest=18117)

        def enqueue(message):
            self.reads.append(message['q_type'])
            self.pending.append(message)
        self.inspector['addCall'] = enqueue
        self.env = dict(lol=dict(core=dict(quests=dict(QuestInspector=dict(
            getInstance=lambda: self.inspector)))))
        spec = next(entry for entry in patches(w.Asm, w.UNDEF)['wraps']
                    if entry[0] == ('core', 'player', 'NPC'))
        self.wrapper = Function(spec[3], spec[4].assemble(), self.env)

    def npc(self, npc_type, entity_id=100):
        give, take = self.catalogue.get(npc_type, ([777], [777]))
        frame = dict(param=dict(res=npc_type, give_quests=Arr(give), take_quests=Arr(take)))

        def original(obj):
            self.original_calls.append(obj)
            for quest_type in obj['param']['give_quests'] + obj['param']['take_quests']:
                native_status(self.inspector, quest_type, entity_id)
        return dict(__qwEdenNPCOrig=original), frame

    def test_native_cache_reproduces_hidden_paid_exits_and_journeys(self):
        for npc_type in (1785, 1789):
            target, frame = self.npc(npc_type)
            target['__qwEdenNPCOrig'](frame)
        self.assertEqual(self.reads, [])
        # A new entity ID refreshes only the first previously checked quest.
        for npc_type, entity_id in ((1785, 200), (1789, 201)):
            target, frame = self.npc(npc_type, entity_id)
            target['__qwEdenNPCOrig'](frame)
        self.assertEqual(self.reads, [18114, 18116])
        self.assertTrue({18117, 18119, 18120, 18121, 18122}.isdisjoint(self.reads))

    def test_refresh_requests_every_current_eden_offer_once_for_each_npc(self):
        for npc_type in self.catalogue:
            self.reads.clear()
            target, frame = self.npc(npc_type)
            self.wrapper.invoke(target, [frame])
            give, take = self.catalogue[npc_type]
            self.assertEqual(self.reads, list(dict.fromkeys(give + take)), npc_type)
            self.assertIs(self.original_calls[-1], frame)

    def test_refresh_preserves_pending_reads_actions_and_other_quest_state(self):
        head = self.pending[0]
        checked_npcs = self.inspector['checkedNPC']
        target, frame = self.npc(1785)
        self.wrapper.invoke(target, [frame])
        self.assertIs(self.pending[0], head)
        self.assertEqual(self.inspector['callCount'], 1)
        self.assertIs(self.inspector['currentQuests'], self.active)
        self.assertIs(self.inspector['checkedNPC'], checked_npcs)
        self.assertEqual(self.inspector['closedQuest'], 18117)
        self.assertTrue(self.inspector['checkedQuests'][777])
        self.assertEqual(self.reads, [18114, 18120, 18121, 18122])

    def test_ordinary_npcs_keep_the_original_cache_and_requests(self):
        for npc_type in (883, 1783, 1790, 6823, 6831, 60020, None):
            target, frame = self.npc(npc_type)
            self.wrapper.invoke(target, [frame])
        self.assertEqual(self.reads, [])
        self.assertEqual(len(self.original_calls), 7)

    def warehouse(self, npc_type, entity_id):
        self.catalogue[npc_type] = (quests.given_by(npc_type), quests.taken_by(npc_type))
        give, take = self.catalogue[npc_type]
        self.inspector['checkedQuests'].update(dict.fromkeys(give + take, True))
        return self.npc(npc_type, entity_id)

    def test_native_cache_reproduces_hidden_warehouse_gold_after_box_refresh(self):
        for npc_type in range(6824, 6831):
            with self.subTest(npc=npc_type):
                self.reads.clear()
                target, frame = self.warehouse(npc_type, 800000 + npc_type)
                target['__qwEdenNPCOrig'](frame)
                # Native checkQStatus marks the new NPC checked after the
                # retired personal quest, then skips its cached gold offer.
                self.assertEqual(self.reads, [765 + npc_type - 6824])
                self.assertNotIn(18220 + npc_type - 6824, self.reads)

    def test_all_warehouse_boxes_revalidate_gold_after_window_capture_and_relog(self):
        for npc_type in range(6824, 6831):
            for entity_id in (800001, 800002, 800001):
                with self.subTest(npc=npc_type, entity=entity_id):
                    self.reads.clear()
                    target, frame = self.warehouse(npc_type, entity_id)
                    offered = list(frame['param']['give_quests'])
                    self.wrapper.invoke(target, [frame])
                    self.assertEqual(self.reads, [765 + npc_type - 6824,
                                                 18220 + npc_type - 6824])
                    self.assertEqual(list(frame['param']['give_quests']), offered)
                    self.assertEqual(list(frame['param']['take_quests']), offered)

    def test_warehouse_refresh_preserves_inflight_requests_and_other_npc_cache(self):
        pending_head = self.pending[0]
        checked_npcs = self.inspector['checkedNPC']
        target, frame = self.warehouse(6830, 800030)
        self.wrapper.invoke(target, [frame])
        self.assertEqual(self.reads, [771, 18226])
        self.assertIs(self.pending[0], pending_head)
        self.assertEqual(self.inspector['callCount'], 1)
        self.assertIs(self.inspector['currentQuests'], self.active)
        self.assertIs(self.inspector['checkedNPC'], checked_npcs)
        self.assertTrue(self.inspector['checkedQuests'][777])
        self.assertEqual(self.inspector['closedQuest'], 18117)

    def test_bunker_lifts_revalidate_both_locations_without_reindexing_quests(self):
        self.catalogue[689] = (quests.given_by(689), quests.taken_by(689))
        self.inspector['checkedQuests'].update({18202: True, 18204: True})
        for entity in (50, 60, 50):
            self.reads.clear()
            target, frame = self.npc(689, entity)
            self.wrapper.invoke(target, [frame])
            self.assertEqual(self.reads, [18202, 18204])
            self.assertEqual(list(frame['param']['give_quests']), [18202, 18204])
            self.assertEqual(self.inspector['callCount'], 1)

    def test_subsequent_eden_contact_revalidates_but_does_not_duplicate_take_list(self):
        target, frame = self.npc(1789)
        self.wrapper.invoke(target, [frame])
        self.wrapper.invoke(target, [frame])
        self.assertEqual(self.reads, [18116, 18117, 18119, 18128] * 2)


if __name__ == '__main__':
    run_cases(EdenQuestClient)
