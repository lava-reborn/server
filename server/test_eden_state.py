"""Administrative Eden persistence and queue boundaries, with no live server."""
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import accounts  # noqa: E402
import eden  # noqa: E402
import eden_sentence  # noqa: E402
import storage  # noqa: E402


class EdenStateTests(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store.temporary()
        account, err = self.store.register("eden_test", "secret")
        self.assertFalse(err)
        self.cid, _ = self.store.create_character(account, "EdenTester", 0, "1")

    def tearDown(self):
        self.store.close()

    def sentence(self, **kwargs):
        return eden.assign(self.store, self.cid, "moderator", "Local test", **kwargs)

    def test_current_position_is_not_admission(self):
        self.store.save_character_state(self.cid, loc=267, on_map=0)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertIsNone(eden.entry(self.store, self.cid))
        for loc_id in range(264, 268):
            self.assertTrue(eden.inside(SimpleNamespace(id=loc_id)))
            self.assertIsNotNone(eden.target_cell(loc_id))
        self.assertFalse(eden.inside(263))
        self.assertIsNone(eden.target_cell(263))

    def test_assignment_preserves_inventory_stats_and_return_place(self):
        state = dict(loc=163, pos=20, gx=5970.5, gy=1730, on_map=1)
        before = dict(self.store.character(self.cid))
        item = self.store.create_item(self.cid, 4232, 4, count=4)
        rec = self.sentence(return_state=state)
        self.assertEqual(rec["admin"], "moderator")
        self.assertEqual(rec["reason"], "Local test")
        self.assertEqual(rec["visit"], 1)
        self.assertEqual({k: rec["return_" + k] for k in state}, state)
        self.assertEqual(dict(self.store.character(self.cid)), before)
        self.assertEqual(self.store.item(item["uniq"])["count"], 4)
        with self.assertRaisesRegex(ValueError, "already assigned"):
            eden.assign(self.store, self.cid, "other", "overwrite")
        self.assertEqual(eden.assigned(self.store, self.cid), rec)
        self.assertEqual(self.store.db.execute(
            "SELECT visits FROM char_eden_visits WHERE char_id = ?",
            (self.cid,)).fetchone()["visits"], 1)

    def test_outer_rollback_includes_assignment_and_training_presence(self):
        profile = {"inside": True, "room": "saved", "personal_profiles": ["keep"]}
        self.store.save_training_profile(self.cid, profile)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with storage.atomic(self.store.db):
                self.sentence()
                self.assertFalse(self.store.training_profile(self.cid)["inside"])
                raise RuntimeError("rollback")
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertEqual(self.store.training_profile(self.cid), profile)
        self.assertIsNone(self.store.db.execute(
            "SELECT visits FROM char_eden_visits WHERE char_id = ?",
            (self.cid,)).fetchone())

    def test_lifetime_visit_count_survives_release_and_repeat_attempts(self):
        self.assertEqual(self.sentence()["visit"], 1)
        eden.release(self.store, self.cid)
        self.assertEqual(self.sentence()["visit"], 2)
        with self.assertRaisesRegex(ValueError, "already assigned"):
            self.sentence()
        self.assertEqual(eden.assigned(self.store, self.cid)["visit"], 2)
        eden.release(self.store, self.cid)
        self.assertIsNone(eden.release(self.store, self.cid))
        self.assertEqual(self.sentence()["visit"], 3)

    def test_only_first_two_lifetime_visits_have_paid_exit_prices(self):
        for visit, expected in ((1, (5_000_000, 5000)), (2, (10_000_000, 10000))):
            with self.subTest(visit=visit):
                sentence = {"visit": visit}
                self.assertTrue(eden.paid_exit_available(sentence))
                self.assertEqual(eden.price(sentence), expected)
                self.assertEqual(sentence, {"visit": visit})
                text = eden.price_text(sentence)
                self.assertIn("№%d" % visit, text)
                self.assertIn(format(expected[0], ",").replace(",", " ") + " афро", text)
                self.assertIn("%d G" % (expected[1] // 100), text)
        for visit in (0, 3, 4, 100):
            with self.subTest(unavailable_visit=visit):
                sentence = {"visit": visit}
                self.assertFalse(eden.paid_exit_available(sentence))
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    eden.price(sentence)
                text = eden.price_text(sentence)
                self.assertIn("Платный выход недоступен", text)
                self.assertIn("выполните норму", text)
                self.assertNotIn("афро", text)
                self.assertNotIn(" G", text)

    def test_failed_reassignment_does_not_consume_next_visit(self):
        self.sentence()
        eden.release(self.store, self.cid)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with storage.atomic(self.store.db):
                self.assertEqual(self.sentence()["visit"], 2)
                raise RuntimeError("rollback")
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertEqual(self.sentence()["visit"], 2)

    def test_assignment_deactivates_only_training_presence(self):
        profile = {"inside": True, "room": "saved", "personal_profiles": ["keep"]}
        self.store.save_training_profile(self.cid, profile)
        self.sentence()
        self.assertEqual(self.store.training_profile(self.cid), dict(profile, inside=False))
        old = eden.release(self.store, self.cid)
        self.assertEqual(old["char_id"], self.cid)
        self.assertIsNone(eden.release(self.store, self.cid))
        self.assertFalse(self.store.training_profile(self.cid)["inside"])

    def test_release_rolls_back_with_its_caller(self):
        rec = self.sentence()
        with self.assertRaisesRegex(RuntimeError, "departure failed"):
            with storage.atomic(self.store.db):
                self.assertEqual(eden.release(self.store, self.cid), rec)
                raise RuntimeError("departure failed")
        self.assertEqual(eden.assigned(self.store, self.cid), rec)

    def test_invalid_assignment_is_not_persisted(self):
        for admin, reason in (("", "why"), ("admin", ""), ("a" * 101, "why")):
            with self.subTest(admin=admin[:10], reason=reason):
                with self.assertRaises(ValueError):
                    eden.assign(self.store, self.cid, admin, reason)
        for state in ({"gx": float("nan")}, {"loc": -1}, {"pos": True},
                      {"on_map": 2}, {"gy": "not a coordinate"}):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    self.sentence(return_state=state)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            eden.assign(self.store, self.cid + 1000, "admin", "why")
        self.assertIsNone(eden.assigned(self.store, self.cid))

    def test_entry_uses_walkable_deterministic_entrance(self):
        self.sentence()
        fake_world = SimpleNamespace(location=lambda _: SimpleNamespace(
            entries=[200, 100, 150], obstacles={100}))
        with patch.dict(sys.modules, world=fake_world):
            self.assertEqual(eden.entry(self.store, self.cid), (267, 150, 5858, 1929))
        fake_world = SimpleNamespace(location=lambda _: SimpleNamespace(
            entries=[100], obstacles={100}))
        with patch.dict(sys.modules, world=fake_world):
            with self.assertRaisesRegex(ValueError, "no walkable entrance"):
                eden.entry(self.store, self.cid)

    def test_cli_queues_but_cannot_directly_sentence_or_release(self):
        action_id = eden_sentence.queue(self.store.db, "EdenTester", "console", "test")
        row = self.store.db.execute("SELECT * FROM admin_actions WHERE id = ?",
                                    (action_id,)).fetchone()
        self.assertEqual((row["kind"], row["char_id"], row["admin"]),
                         ("eden", self.cid, "console"))
        self.assertEqual(json.loads(row["args_json"]), {"reason": "test"})
        self.assertIsNone(row["done_at"])
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.sentence()
        action_id = eden_sentence.queue(self.store.db, self.cid, "console", "release",
                                         release=True)
        row = self.store.db.execute("SELECT * FROM admin_actions WHERE id = ?",
                                    (action_id,)).fetchone()
        self.assertEqual(row["kind"], "eden_release")
        self.assertIsNotNone(eden.assigned(self.store, self.cid))

    def test_file_persistence_survives_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "eden.db")
            db = storage.SqliteDB(path)
            db.create_schema(accounts.SCHEMA)
            accounts.migrate(db)
            store = accounts.Store(db=db)
            account, _ = store.register("other", "secret")
            cid, _ = store.create_character(account, "Persisted", 0, "1")
            rec = eden.assign(store, cid, "moderator", "persists")
            store.close()
            db = storage.SqliteDB(path)
            store = accounts.Store(db=db)
            try:
                self.assertEqual(eden.assigned(store, cid), rec)
                self.assertEqual(eden.release(store, cid), rec)
            finally:
                store.close()
            db = storage.SqliteDB(path)
            store = accounts.Store(db=db)
            try:
                self.assertIsNone(eden.assigned(store, cid))
                self.assertEqual(eden.assign(store, cid, "moderator", "again")["visit"], 2)
                self.assertTrue(eden.paid_exit_available(eden.assigned(store, cid)))
                eden.release(store, cid)
                self.assertEqual(eden.assign(store, cid, "moderator", "third")["visit"], 3)
            finally:
                store.close()
            db = storage.SqliteDB(path)
            store = accounts.Store(db=db)
            try:
                current = eden.assigned(store, cid)
                self.assertEqual(current['visit'], 3)
                self.assertFalse(eden.paid_exit_available(current))
                with self.assertRaisesRegex(ValueError, 'unavailable'):
                    eden.price(current)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
