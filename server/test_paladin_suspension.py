"""Temporary Paladin quest gate, including already accepted quests, in memory."""
import logging
import os
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import accounts
import inventory
import items
import progression
import quests
import server
import world
from test_quest_state import session


class PaladinSuspension(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, 'STORE', previous)
        aid, _ = self.store.register('paladin-test', 'local-only')
        self.cid, _ = self.store.create_character(aid, 'PaladinTest', 0, '1')
        self.s = session(self.store, level=17, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        for row in self.s.char.skill:
            row[0] = 17
        self.s.char.afro, self.s.char.gold = 123456, 5000
        self.s.char.save(self.store)
        self.s.closed, self.s.transport, self.s.residence_timer = False, None, None
        self.s.close = lambda force=False: setattr(self.s, 'closed', True)
        self.npc = 1726
        self.s.loc = NS(id=446, width=64, height=128, spawns=[])
        self.s.room = NS(npc=lambda n: (0, self.npc, world.COMMONER))
        self.s.pos = 0
        self.s.active = self.store.character(self.cid)
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames, self.messages = [], []
        self.s.send = lambda cmd, **p: self.frames.append((cmd, p))
        self.s.send_player_info = lambda: None
        self.s.say = self.s.answer = self.messages.append

    def snapshot(self):
        return (self.store.character(self.cid), self.s.inv.rows(),
                [dict(r) for r in self.store.db.execute(
                    'SELECT * FROM char_quests_done WHERE char_id=? ORDER BY id', (self.cid,))],
                self.s.char.afro, self.s.char.gold)

    def accepted(self, q):
        self.npc = q.take[0]
        for t, n, _ in q.objs:
            self.s.inv.give_pieces(t, n)
        return self.store.take_quest(self.cid, q.type,
                                     q.bag_progress(self.s.inv.bag_pieces()), True)

    def test_all_component_and_assembly_reward_paths_are_suspended(self):
        expected = set(range(943, 948)) | set(range(960, 965))
        self.assertEqual(quests.TEMPORARILY_DISABLED_QUESTS, expected)
        parts = set(range(5546, 5576)) | set(range(11559, 11564))
        found = set()
        for q in quests.QUESTS.values():
            rewards = set(q.rew_obj) | {t for t, n in q.rew_also} | {t for t, n, w in q.rew_random}
            if rewards & parts:
                found.add(q.type)
                self.assertTrue(quests.acquisition_blocked(q))
        self.assertEqual(found, expected)
        with patch.object(items, 'acquisition_blocked', return_value=False):
            for qid in expected:
                self.assertTrue(quests.acquisition_blocked(quests.get(qid)))

    def test_unavailable_to_new_and_existing_characters_without_reindexing_npc_list(self):
        for qid in quests.TEMPORARILY_DISABLED_QUESTS:
            q = quests.get(qid)
            self.npc = q.give[0]
            offered = quests.given_by(self.npc)
            self.assertIn(qid, offered)
            self.assertFalse(self.s.quest_available(q))
            self.frames.clear()
            before = self.snapshot()
            self.s.cmd_q_st(dict(mob=1, q_idx=offered.index(qid)))
            self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.frames)
            self.assertFalse(self.store.has_quest(self.cid, qid))
            self.assertEqual(self.snapshot(), before)
            active = self.accepted(q)
            self.assertFalse(self.s.quest_available(q))
            self.store.drop_quest(active)

    def test_already_complete_hand_in_and_replay_preserve_every_resource(self):
        for qid in sorted(quests.TEMPORARILY_DISABLED_QUESTS):
            with self.subTest(quest=qid):
                q = quests.get(qid)
                active = self.accepted(q)
                before = self.snapshot()
                quest_before = dict(self.store.quest(active))
                for _ in range(2):
                    self.frames.clear()
                    self.s.cmd_q_co(dict(q_id=active, mob=1, obj_idx=0))
                    self.assertIn(('cmdAck', dict(res=server.RES_NOT_AVAILABLE)), self.frames)
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(dict(self.store.quest(active)), quest_before)
                    self.assertFalse(any(cmd.startswith('ss_obj') for cmd, p in self.frames))
                self.store.drop_quest(active)
        self.assertFalse(self.s.closed)

    def test_cancel_stays_available_without_consuming_collected_parts(self):
        q = quests.get(960)
        active = self.accepted(q)
        before = self.snapshot()
        self.frames.clear()
        self.s.cmd_q_ca(dict(q_id=active))
        self.assertIn(('cmdAck', dict(res=0)), self.frames)
        self.assertIsNone(self.store.quest(active))
        self.assertEqual(self.snapshot(), before)

    def test_owned_paladin_piece_and_unrelated_services_remain_intact(self):
        fields = inventory.new_fields(11559)
        root = fields.pop('root')
        owned = self.store.create_item(self.cid, 11559, root, **fields)
        for qid in (942, 923, 8800, 8801, 8802, 8803):
            self.assertNotIn(qid, quests.TEMPORARILY_DISABLED_QUESTS)
            self.assertFalse(quests.acquisition_blocked(quests.get(qid)))
        active = self.accepted(quests.get(960))
        self.s.cmd_q_co(dict(q_id=active, mob=1, obj_idx=0))
        self.assertEqual(self.store.item(owned['uniq']), owned)


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(PaladinSuspension)
