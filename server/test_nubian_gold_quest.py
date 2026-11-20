"""The Nubian gold quest pays 0.8 G once per character, including old history.

Runs real transactional handlers against isolated SQLite stores. No sockets,
test-client accounts or production data are used.
"""
import json
import logging
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)
import accounts
import inventory
import progression
import quests
import server
from test_quest_state import session
from testkit import run_cases


class NubianGoldQuest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = os.path.join(directory.name, "quest.sqlite")
        self.store = accounts.Store(self.path)
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        self.aid, _ = self.store.register("prospector", "local-password")
        self.cid, _ = self.store.create_character(self.aid, "prospector", 0, "1")
        self.q = quests.get(9)
        self.frames = []
        self.s = self.make_session(self.cid)

    def make_session(self, cid):
        s = session(self.store, char_id=cid)
        s.char = progression.Character.load(self.store, cid)
        s.char.set_skill(progression.SHOOTING, 3)
        s.active = self.store.character(cid)
        s.closed, s.transport, s.room = False, None, None
        s.loc = NS(id=612, spawns=[])
        s.fee_shown, s.skill_shown = {}, {}
        s.npc_type = lambda _id: 1134
        s.over_weight = lambda *_args: False
        s.send = lambda command, **p: self.frames.append((command, p))
        return s

    def give_sand(self, number=10):
        fields = inventory.new_fields(2258, number)
        root = fields.pop("root")
        fields["slot"] = inventory.BAG
        return self.store.create_item(self.cid, 2258, root, **fields)

    def active(self):
        progress = self.q.bag_progress(self.s.inv.bag_pieces())
        return self.store.take_quest(self.cid, self.q.type, progress,
                                     self.q.is_complete(progress))

    def hand_in(self, qid):
        self.frames.clear()
        self.s.cmd_q_co(dict(q_id=qid, mob=1, obj_idx=0))
        return [p["res"] for name, p in self.frames if name == "cmdAck"]

    def old_completion(self, when=1):
        self.store.finish_quest(0, self.cid, self.q.type, when=when)

    def test_definition_and_player_texts_keep_the_new_reward_and_rule(self):
        self.assertEqual((self.q.repeatable, self.q.per_day, self.q.rew_gold), (0, 0, 80))
        self.assertEqual(self.q.wants(), [(2258, 10)])
        self.assertEqual(self.q.give, [1134])
        self.assertNotIn(9, quests.repeatable_types())
        rows = json.loads(Path(quests.PATH).read_text(encoding="utf-8"))["quests"]
        row = next(r for r in rows if r["type"] == 9)
        old_texts = {9: {"start": "Плати раз в сутки", "finish": "Держи унцию золота"}}
        served = quests.player_texts(row, originals=old_texts)
        self.assertIn("один раз на персонажа", served["start"])
        self.assertIn("0,8 G", served["start"])
        self.assertIn("0,8 унции", served["finish"])
        self.assertNotIn("сутки", served["start"])

    def test_first_completion_consumes_ten_sacks_pays_80_and_ignores_daily_limit(self):
        self.give_sand(11)
        qid = self.active()
        before = self.store.money(self.cid)
        with patch.object(self.s, "daily_available", return_value=0):
            self.assertEqual(self.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 80))
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 1)
        self.assertEqual(self.store.quests_done_since(self.cid, 0, [9]), 1)
        self.assertFalse(any(name == "q_sys" for name, _ in self.frames))
        self.assertFalse(self.s.quest_available(self.q))
        self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 80))

    def test_historical_daily_completion_blocks_new_take_in_any_day(self):
        self.old_completion()
        before = self.store.money(self.cid)
        for offset in (0, 86400, 365 * 86400):
            with self.subTest(offset=offset), patch.object(self.s, "day_start", return_value=offset):
                self.assertFalse(self.s.quest_available(self.q))
                self.assertFalse(self.s.quest_available(self.q, self.s.quest_status_state(9)))
                self.frames.clear()
                self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(1134).index(9)))
                self.assertEqual([p["res"] for name, p in self.frames if name == "cmdAck"],
                                 [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.store.quests(self.cid), [])
        self.assertEqual(self.store.money(self.cid), before)

    def test_old_active_repeat_is_refused_and_can_be_cancelled_without_losing_sand(self):
        self.give_sand()
        qid = self.active()
        self.old_completion()
        before = self.store.money(self.cid)
        self.assertFalse(self.s.quest_available(self.q))
        self.assertFalse(self.s.quest_available(self.q, self.s.quest_status_state(9)))
        self.assertEqual(self.hand_in(qid), [server.RES_NOT_AVAILABLE])
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 10)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.store.quests_done_since(self.cid, 0, [9]), 1)
        self.frames.clear()
        self.s.cmd_q_ca(dict(q_id=qid))
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 10)
        self.assertEqual(self.store.money(self.cid), before)

    def test_two_active_copies_cannot_pay_twice(self):
        self.give_sand(20)
        first, duplicate = self.active(), self.active()
        before = self.store.money(self.cid)
        self.assertEqual(self.hand_in(first), [0])
        self.assertEqual(self.hand_in(duplicate), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 10)
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 80))
        self.assertEqual(self.store.quests_done_since(self.cid, 0, [9]), 1)

    def test_history_survives_new_store_and_session(self):
        self.old_completion()
        reopened = accounts.Store(self.path)
        self.addCleanup(reopened.close)
        fresh = session(reopened, char_id=self.cid)
        fresh.char = progression.Character.load(reopened, self.cid)
        with patch.object(server, "STORE", reopened):
            self.assertTrue(reopened.quest_done(self.cid, 9))
            self.assertFalse(fresh.quest_available(self.q))
            self.assertFalse(fresh.quest_available(self.q, fresh.quest_status_state(9)))

    def test_other_character_of_same_account_keeps_an_independent_attempt(self):
        self.old_completion()
        self.cid, _ = self.store.create_character(self.aid, "secondminer", 0, "1")
        self.s = self.make_session(self.cid)
        self.assertTrue(self.s.quest_available(self.q))
        self.give_sand()
        before = self.store.money(self.cid)
        self.assertEqual(self.hand_in(self.active()), [0])
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 80))

    def test_reward_failure_rolls_back_sand_history_and_money_then_retry_pays_once(self):
        self.give_sand()
        qid = self.active()
        before = self.store.money(self.cid)
        with patch.object(self.s.char, "save", side_effect=RuntimeError("test write failure")):
            self.assertEqual(self.hand_in(qid), [1])
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 10)
        self.assertEqual(self.store.money(self.cid), before)
        self.assertFalse(self.store.quest_done(self.cid, 9))
        self.assertEqual(self.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid), (before[0], before[1] + 80))

    def test_hand_in_reads_live_history_under_character_lock_not_display_cache(self):
        self.give_sand()
        qid = self.active()
        state = self.s.quest_status_state(9)
        self.assertTrue(self.s.quest_available(self.q, state))
        self.old_completion()
        locked = []
        original_lock = self.store.lock_quest_character
        original_done = self.store.quest_done

        def lock(cid):
            self.assertGreater(self.store.db._atomic_depth, 0)
            locked.append(cid)
            return original_lock(cid)

        def done(cid, qtype):
            self.assertEqual(locked, [self.cid])
            self.assertGreater(self.store.db._atomic_depth, 0)
            return original_done(cid, qtype)

        with patch.object(self.store, "lock_quest_character", side_effect=lock), \
                patch.object(self.store, "quest_done", side_effect=done):
            self.assertEqual(self.hand_in(qid), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.s.inv.bag_pieces().get(2258), 10)


if __name__ == "__main__":
    try:
        run_cases(NubianGoldQuest)
    finally:
        server.STORE.close()
