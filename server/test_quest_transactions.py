"""Quest resources, history and notifications commit as one operation.

PROTOCOL.md q_st/q_co/q_ca defines one acknowledgement per request. Faults
are injected into real handlers and an isolated SQLite store: no reward may
be lost between commits, and a repeated or disconnected hand-in cannot pay
twice. This suite does not exercise concurrent sockets or PostgreSQL.
"""
import copy
import logging
import os
import random
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)
import accounts  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import mobs  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import server  # noqa: E402
import storage  # noqa: E402
from test_quest_state import session  # noqa: E402
from testkit import run_cases  # noqa: E402


class QuestTransactions(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        self.previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, "STORE", self.previous)
        self.addCleanup(self.store.close)
        account, _ = self.store.register("questtxn", "local-password")
        self.cid, _ = self.store.create_character(account, "questtxn", 0, "1")
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        for skill in self.s.char.skill:
            skill[0] = 20
        self.s.char.afro = 10000
        self.s.char.gold = 10000
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.transport = None
        self.s.closed = False
        self.s.room = None
        self.s.loc = NS(id=49, spawns=[])
        self.s.npc_type = lambda _id: 1
        self.s.over_weight = lambda *_args: False
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames = []
        self.s.send = lambda command, **p: self.frames.append((command, p))
        self.q = quests.Quest(dict(
            type=900099, kind="bring_l_obj", name="transaction probe", repeatable=True,
            give=[1], take=[1], objs=[{"obj": 6043, "num": 1}],
            rew_obj=[6106], num_rew_obj=[1]))
        self.enterContext(patch.dict(quests.QUESTS, {self.q.type: self.q}))
        self.enterContext(patch.object(quests, "given_by", return_value=[self.q.type]))

    def give(self, type_id):
        fields = inventory.new_fields(type_id)
        root = fields.pop("root")
        fields["slot"] = inventory.BAG
        return self.store.create_item(self.cid, type_id, root, **fields)

    def take_ready(self):
        self.give(6043)
        progress = self.q.bag_progress(self.s.inv.bag_pieces())
        return self.store.take_quest(self.cid, self.q.type, progress, True)

    def hand_in(self, qid):
        self.s.cmd_q_co(dict(q_id=qid, mob=1, obj_idx=0))

    def history(self):
        return self.store.db.execute(
            "SELECT COUNT(*) AS n FROM char_quests_done WHERE char_id=? AND type=?",
            (self.cid, self.q.type)).fetchone()["n"]

    def test_error_after_history_write_restores_quest_and_input(self):
        qid = self.take_ready()
        snapshot = self.s.quest_status_state(self.q.type)
        with patch.object(self.s.inv, "give_pieces", side_effect=RuntimeError("reward failed")):
            self.hand_in(qid)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.history(), 0)
        self.assertEqual(self.s.inv.bag_pieces().get(6043), 1)
        self.assertNotIn(6106, self.s.inv.bag_pieces())
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [1])
        self.assertFalse(any(n.startswith("ss_") for n, _p in self.frames))
        self.assertIsNot(self.s.quest_status_state(self.q.type), snapshot)
        self.frames.clear()
        self.hand_in(qid)
        self.assertEqual(self.history(), 1)
        self.assertEqual(self.s.inv.bag_pieces().get(6106), 1)

    def test_same_instance_hand_in_twice_pays_once(self):
        qid = self.take_ready()
        self.hand_in(qid)
        self.hand_in(qid)
        self.assertEqual(self.history(), 1)
        self.assertEqual(self.s.inv.bag_pieces().get(6106), 1)
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"],
                         [0, server.RES_NO_SUCH])

    def test_halfa_provisions_consumes_abu_bakr_quest_ful_and_rewards_once(self):
        self.q = quests.QUESTS[148]
        self.assertIn(334, items.stock_for(155, 50))
        self.assertIn(333, items.stock_for(155, 50))
        self.assertEqual(self.q.drops, [(t, 333, 0.3) for t in range(287, 299)])
        self.assertEqual(items.params_of(333)['weight'], 10000)
        self.assertEqual(items.params_of(334)['weight'], 2000)
        self.assertEqual(inventory.Inventory.pieces_weight(333, 1), 10000)
        self.assertEqual(inventory.Inventory.pieces_weight(334, 1), 2000)
        self.assertIn('Абу-бакра', self.q.texts[1])
        self.s.npc_type = lambda _id: 718
        self.give(333)
        wrong_ful = self.give(6899)
        self.assertEqual(self.q.bag_progress(self.s.inv.bag_pieces())['obj_num'], [1, 0])
        ful = self.give(334)
        progress = self.q.bag_progress(self.s.inv.bag_pieces())
        self.assertEqual(progress['obj_num'], [1, 1])
        qid = self.store.take_quest(self.cid, self.q.type, progress, True)
        before = self.s.char.afro
        self.hand_in(qid)
        self.assertIsNone(self.store.quest(qid))
        self.assertIsNone(self.store.item(ful['uniq']))
        self.assertIsNotNone(self.store.item(wrong_ful['uniq']))
        self.assertNotIn(333, self.s.inv.bag_pieces())
        self.assertEqual(self.s.char.afro - before, self.q.rew_afro)
        self.assertEqual(self.history(), 1)
        self.hand_in(qid)
        self.assertEqual(self.s.char.afro - before, self.q.rew_afro)
        self.assertEqual(self.history(), 1)

    def test_halfa_provisions_quest_loot_supplies_beans_not_ful(self):
        q = quests.QUESTS[148]
        rng = random.Random(148)
        drops = [t for _ in range(200)
                 for t, _n in mobs.loot_for(mobs.stats(287), rng, {333})]
        self.assertIn(333, drops)
        self.assertNotIn(334, drops)
        self.assertEqual(q.bag_progress({333: 1, 334: 1})['obj_num'], [1, 1])
        plain = [t for _ in range(200)
                 for t, _n in mobs.loot_for(mobs.stats(287), rng)]
        self.assertNotIn(333, plain)

    def test_failed_take_rolls_back_start_item_and_instance(self):
        self.q.start_obj = [(6043, 1)]
        original = self.store.take_quest
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("take failed after insert")
        with patch.object(self.store, "take_quest", fail):
            self.s.cmd_q_st(dict(mob=1, q_idx=0))
        self.assertEqual(self.store.quests(self.cid), [])
        self.assertNotIn(6043, self.s.inv.bag_pieces())
        self.assertFalse(any(n.startswith("ss_") or n.startswith("q_di") for n, _p in self.frames))

    def test_failed_cancel_preserves_instance_and_lent_items(self):
        qid = self.take_ready()
        self.q.start_obj = [(6043, 1)]
        original = self.s.inv.reclaim_pieces
        def fail(*args):
            original(*args)
            raise RuntimeError("cancel failed after reclaim")
        with patch.object(self.s.inv, "reclaim_pieces", fail):
            self.s.cmd_q_ca(dict(q_id=qid))
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.s.inv.bag_pieces().get(6043), 1)
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [1])

    def test_commit_failure_restores_character_and_all_database_writes(self):
        qid = self.take_ready()
        self.q.rew_afro = 100
        before = copy.deepcopy(self.s.char.__dict__)
        raw = self.store.db.raw
        proxy = NS(commit=lambda: (_ for _ in ()).throw(RuntimeError("commit failed")),
                   rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)), \
                patch.object(self.s, "close") as close:
            self.hand_in(qid)
        close.assert_called_once_with(force=True)
        self.assertEqual(self.s.char.__dict__, before)
        self.assertEqual(self.store.character(self.cid)["afro"], 10000)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.history(), 0)
        self.assertNotIn(6106, self.s.inv.bag_pieces())

    def test_lost_database_commit_reply_cannot_overwrite_committed_reward(self):
        qid = self.take_ready()
        self.q.rew_afro = 100
        raw = self.store.db.raw

        def commit():
            raw.commit()
            raise ConnectionError("database committed but its reply was lost")

        def close(force):
            self.assertTrue(force)
            self.s.char.save(self.store)

        proxy = NS(commit=commit, rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)), \
                patch.object(self.s, "close", side_effect=close) as closed:
            self.hand_in(qid)
        closed.assert_called_once_with(force=True)
        self.assertEqual(self.store.character(self.cid)["afro"], 10100)
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.history(), 1)
        self.assertEqual(self.s.inv.bag_pieces().get(6106), 1)
        self.assertFalse(any(command == "cmdAck" for command, _params in self.frames))

    def test_unreadable_commit_result_does_not_save_stale_character(self):
        qid = self.take_ready()
        raw = self.store.db.raw
        proxy = NS(commit=lambda: (_ for _ in ()).throw(ConnectionError("lost database")),
                   rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)), \
                patch.object(progression.Character, "load", side_effect=ConnectionError("offline")), \
                patch.object(self.s, "close") as closed:
            self.hand_in(qid)
        closed.assert_called_once_with(force=True)
        self.assertIsNone(self.s.char)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.history(), 0)

    def test_lost_database_reply_refunds_committed_unfulfilled_trip(self):
        qid = self.take_ready()
        self.q.cost_afro = 200
        self.q.rew_obj = []
        self.s.gx, self.s.gy = 0, 0
        raw = self.store.db.raw

        def commit():
            raw.commit()
            raise ConnectionError("database committed but its reply was lost")

        proxy = NS(commit=commit, rollback=raw.rollback)
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)), \
                patch.object(server.travel, "is_quest_way", return_value=True), \
                patch.object(server.travel, "plan_quest_way"), \
                patch.object(self.s, "close") as closed:
            self.hand_in(qid)
        closed.assert_called_once_with(force=True)
        self.assertEqual(self.store.character(self.cid)["afro"], 10000)
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.history(), 1)

    def test_success_frames_are_published_after_commit(self):
        qid = self.take_ready()
        raw = self.store.db.raw
        committed = []
        def commit():
            raw.commit()
            committed.append(True)
        proxy = NS(commit=commit, rollback=raw.rollback)
        def send(command, **p):
            self.assertTrue(committed, command)
            self.frames.append((command, p))
        self.s.send = send
        with patch.object(type(self.store.db), "raw", property(lambda _db: proxy)):
            self.hand_in(qid)
        self.assertEqual([p["res"] for n, p in self.frames if n == "cmdAck"], [0])

    def test_lost_success_reply_does_not_rollback_or_duplicate_reward(self):
        qid = self.take_ready()
        def disconnect(command, **_params):
            if command == "cmdAck":
                raise ConnectionError("client lost success acknowledgement")
        self.s.send = disconnect
        with self.assertRaises(ConnectionError):
            self.hand_in(qid)
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.history(), 1)
        self.s.send = lambda command, **p: self.frames.append((command, p))
        self.hand_in(qid)
        self.assertEqual(self.s.inv.bag_pieces().get(6106), 1)
        self.assertEqual(self.history(), 1)

    def test_lost_way_reply_does_not_skip_committed_travel(self):
        qid = self.take_ready()
        self.s.gx, self.s.gy = 0, 0

        def disconnect(command, **_params):
            if command == "cmdAck":
                raise ConnectionError("client lost travel acknowledgement")

        self.s.send = disconnect
        with patch.object(server.travel, "is_quest_way", return_value=True), \
                patch.object(server.travel, "plan_quest_way"), \
                patch.object(self.s, "hand_in_way") as follow:
            with self.assertRaises(ConnectionError):
                self.hand_in(qid)
        follow.assert_called_once_with(qid, self.q)
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.history(), 1)
        self.assertEqual(self.s.inv.bag_pieces().get(6106), 1)

    def test_caught_nested_database_failure_cannot_commit_partial_work(self):
        db = self.store.db
        db.execute("CREATE TABLE atomic_probe (n INTEGER)")
        db.commit()
        with self.assertRaises(RuntimeError):
            with storage.atomic(db):
                db.execute("INSERT INTO atomic_probe VALUES (1)")
                db.commit()
                try:
                    with db:
                        db.execute("INSERT INTO atomic_probe VALUES (2)")
                        raise ValueError("inner operation failed")
                except ValueError:
                    pass
                db.execute("INSERT INTO atomic_probe VALUES (3)")
        self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM atomic_probe").fetchone()["n"], 0)


if __name__ == "__main__":
    try:
        run_cases(QuestTransactions)
    finally:
        server.STORE.close()
