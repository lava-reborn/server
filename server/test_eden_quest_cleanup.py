"""Committed release -> real wire -> emitted AVM1 journal reconciliation."""
import contextlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from test_eden_quests import EdenQuestTests
import eden
import protocol
import quests
import storage
from avm_test import Function
from eden_inventory_client import patches
import widescreen as w
from testkit import run_cases


class EdenQuestCleanupTests(unittest.TestCase):
    def setUp(self):
        self.t = EdenQuestTests()
        self.t.setUp()
        self.addCleanup(self.t.doCleanups)
        self.t.fund(20_000_000, 20_000)
        self.t.finish_intro()
        self.assertEqual(self.t.take(eden.GIFT), [0])
        self.assertEqual(self.t.hand_in(self.t.taken_id(eden.GIFT)), [0])
        self.ordinary = self.t.active(9)
        self.updates, self.forwarded = [], []
        self.inspector = dict(currentQuests={}, cqList={}, checkedQuests={},
                              questUpdate=lambda: self.updates.append('update'))
        self.master = {}
        env = dict(lol=dict(core=dict(Master=dict(getInstance=lambda: self.master),
            quests=dict(QuestInspector=dict(getInstance=lambda: self.inspector)))))
        spec = next(row for row in patches(w.Asm, w.UNDEF)['wraps']
                    if row[1] == 'sendNotification')
        self.notify = Function(spec[3], spec[4].assemble(), env)
        self.connection = dict(__edInventoryNotifyOrig=lambda cmd: self.forwarded.append(cmd))
        self.published_depths = []

        def capture(command, **params):
            if command == 'eden_inv' and params.get('clear_eden'):
                self.published_depths.append(self.t.store.db._atomic_depth)
            self.t.frames.append((command, params))
        self.t.s.send = capture

    def seed_local_journal(self, except_type=None):
        # Include the obsolete gather task and several unrelated Eden services,
        # not merely the release task which native takeAck removes itself.
        active_types = {row['type'] for row in self.t.store.quests(self.t.cid)}
        for quest_type in eden.LOCAL_QUESTS - {eden.GIFT, except_type} - active_types:
            self.t.store.take_quest(self.t.cid, quest_type, {}, False)
        for row in self.t.store.quests(self.t.cid):
            self.inspector['currentQuests'][row['q_id']] = dict(typeID=row['type'])
            self.inspector['cqList'][row['type']] = row['q_id']
            self.inspector['checkedQuests'][row['type']] = True
        self.ordinary_task = self.inspector['currentQuests'][self.ordinary]

    def replay_committed_wire(self):
        markers = 0
        for command, params in self.t.frames:
            if command == 'eden_inv':
                # Encode/decode the same typed list the Flash parser receives.
                command, params = protocol.decode(protocol.frame(command, **params)[:-1])
                self.notify.invoke(self.connection, [dict(messID=command, params=params)])
                markers += int(params.get('clear_eden', 0))
        self.assertEqual(markers, 1)
        self.assertEqual(self.published_depths, [0])

    def assert_released_journal_and_history(self):
        self.assertEqual([row['q_id'] for row in self.t.store.quests(self.t.cid)], [self.ordinary])
        self.assertEqual(self.inspector['currentQuests'], {self.ordinary: self.ordinary_task})
        self.assertIs(self.inspector['currentQuests'][self.ordinary], self.ordinary_task)
        self.assertEqual(self.inspector['cqList'], {9: self.ordinary})
        self.assertEqual(self.inspector['checkedQuests'], {9: True})
        self.assertEqual(self.updates, ['update'])
        self.assertTrue(self.t.store.quest_done(self.t.cid, eden.GIFT))
        self.assertTrue(self.t.store.quest_done(self.t.cid, 18127))
        self.assertIsNone(eden.assigned(self.t.store, self.t.cid))
        self.assertEqual(self.t.store.db.execute(
            'SELECT visits FROM char_eden_visits WHERE char_id=?', (self.t.cid,)
        ).fetchone()['visits'], 1)

    def release_by_quest(self, quest_type):
        if quest_type == 18115:
            self.t.give(eden.EXIT_PASS)
        self.assertEqual(self.t.take(quest_type), [0])
        qid = self.t.taken_id(quest_type)
        self.seed_local_journal(except_type=quest_type)
        self.assertEqual(self.t.hand_in(qid), [0])
        self.replay_committed_wire()
        self.assert_released_journal_and_history()
        self.assertTrue(self.t.store.quest_done(self.t.cid, quest_type))

    def test_quota_release_retires_all_local_tasks_in_the_live_journal(self):
        self.release_by_quest(18115)

    def test_gold_release_retires_only_local_tasks_after_commit(self):
        self.release_by_quest(eden.GOLD_EXIT)
        self.assertEqual(self.t.store.money(self.t.cid), (19_985_000, 15_000))

    def test_afro_release_retires_only_local_tasks_after_commit(self):
        self.release_by_quest(eden.AFRO_EXIT)
        self.assertEqual(self.t.store.money(self.t.cid), (14_985_000, 20_000))

    def admin_release(self, online=True):
        self.t.frames.clear()
        return eden.admin_apply(self.t.store, dict(kind='eden_release', char_id=self.t.cid,
            admin='regression', args_json=json.dumps(dict(reason='Journal cleanup'))),
            self.t.s if online else None, (41, 5970, 1730))

    def test_admin_release_and_second_assignment_preserve_history_and_new_work(self):
        self.seed_local_journal()
        self.admin_release()
        self.replay_committed_wire()
        self.assert_released_journal_and_history()
        self.t.new_sentence()
        self.assertEqual(self.t.s.eden_sentence['visit'], 2)
        self.assertFalse(self.t.s.quest_available(quests.get(eden.GIFT)))
        # Both African Punishment steps are available again. A completion is
        # preserved as a prerequisite, while the old active instances are gone.
        for qtype in (18127, 18114):
            self.assertEqual(self.t.take(qtype), [0])
            row = self.t.store.quest(self.t.taken_id(qtype))
            self.assertEqual(row['type'], qtype)
        self.assertEqual(len(self.t.store.quests(self.t.cid)), 3)

    def test_offline_admin_release_cleans_legacy_quests_without_a_client_frame(self):
        self.seed_local_journal()
        self.admin_release(online=False)
        self.assertFalse(any(command == 'eden_inv' for command, _ in self.t.frames))
        self.assertEqual([row['q_id'] for row in self.t.store.quests(self.t.cid)], [self.ordinary])
        self.assertTrue(self.t.store.quest_done(self.t.cid, eden.GIFT))
        self.assertTrue(self.t.store.quest_done(self.t.cid, 18127))

    def test_quest_rollback_publishes_no_removal_and_retains_all_active_tasks(self):
        self.assertEqual(self.t.take(eden.GOLD_EXIT), [0])
        qid = self.t.taken_id(eden.GOLD_EXIT)
        self.seed_local_journal(except_type=eden.GOLD_EXIT)
        before_rows = self.t.store.quests(self.t.cid)
        before_money = self.t.store.money(self.t.cid)
        before_tasks = self.inspector['currentQuests'].copy()
        with patch.object(self.t.store, 'save_position', side_effect=RuntimeError('rollback')):
            self.assertEqual(self.t.hand_in(qid), [1])
        self.assertEqual(self.t.store.quests(self.t.cid), before_rows)
        self.assertEqual(self.t.store.money(self.t.cid), before_money)
        self.assertIsNotNone(eden.assigned(self.t.store, self.t.cid))
        self.assertFalse(any(command == 'eden_inv' for command, _ in self.t.frames))
        self.assertEqual(self.inspector['currentQuests'], before_tasks)
        self.assertEqual(self.published_depths, [])


if __name__ == '__main__':
    run_cases(EdenQuestCleanupTests)
