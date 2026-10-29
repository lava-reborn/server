"""Bulk availability matches live checks, including cache invalidation.

The q_status contract is PROTOCOL.md; taking/handing in must keep live checks.
Compare all real quest definitions against that uncached path and exercise
history ordering, dependencies and snapshot invalidation in memory.
"""
import os
import random
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
import accounts  # noqa: E402
import inventory  # noqa: E402
import progression  # noqa: E402
import quest_state  # noqa: E402
import quests  # noqa: E402
import server  # noqa: E402
import world  # noqa: E402
from testkit import run_cases  # noqa: E402

def session(store, level=10, char_id=1):
    s = server.Session.__new__(server.Session)
    s.char_id = char_id
    s.account = None
    s.char = progression.Character()
    for skill in s.char.skill:
        skill[0] = level
    for spec in s.char.spec:
        spec[0] = 2
    s.inv = inventory.Inventory(s, store)
    s.send = lambda *a, **kw: None
    return s

class QuestStateTests(unittest.TestCase):

    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, 'STORE', self.previous)
        self.addCleanup(self.store.db.close)
        self.s = session(self.store)
        self.day = self.s.day_start()

    def history(self, rows):
        self.store.db.executemany('INSERT INTO char_quests_done (char_id,type,done_at) VALUES (?,?,?)', rows)
        self.store.db.commit()

    def test_summary_and_first_event_tie_break(self):
        self.history([(1, 10, self.day - 5), (1, 11, self.day - 5), (1, 10, self.day + 5), (1, 10, self.day + 6), (2, 12, self.day + 7)])
        self.store.take_quest(1, 15, {}, False)
        self.store.note_lent(1, 19, self.day + 1)
        state = self.s.quest_status_state()
        self.assertEqual(state.active, {15})
        self.assertEqual(state.today(10), 2)
        self.assertEqual(state.last(10), self.day + 6)
        self.assertEqual(state.first_done([11, 10]), 10)
        self.assertFalse(state.done(12))
        self.assertEqual(state.loans, {19: self.day + 1})
        self.assertIsNone(state.first_done([]))

    def test_first_event_uses_time_before_id_and_scopes_other_characters(self):
        self.history([(1, 10, self.day + 10), (1, 11, self.day - 20),
                      (1, 10, self.day - 20), (2, 10, self.day - 100)])
        state = quest_state.QuestState(self.store.db, 1, self.day, {10, 11})
        self.assertEqual(state.first_done([10, 11]), 11)
        self.assertEqual(state.history[10][0], self.day - 20)
        self.assertEqual(state.last(10), self.day + 10)
        self.assertEqual(state.today(10), 1)
        empty = quest_state.QuestState(self.store.db, 1, self.day, set())
        self.assertEqual(empty.history, {})

    def test_one_query_for_status_burst(self):
        seen = []
        original = self.store.db.execute

        def execute(sql, args=()):
            seen.append(sql)
            return original(sql, args)
        with patch.object(self.store.db, 'execute', execute):
            for _ in range(200):
                self.s.quest_status_state()
        self.assertEqual(len(seen), 1)

    def test_every_quest_write_invalidates_snapshot(self):
        old = self.s.quest_status_state()
        q_id = self.store.take_quest(1, 10, {}, False)
        new = self.s.quest_status_state()
        self.assertIsNot(new, old)
        self.assertIn(10, new.active)
        self.store.drop_quest(q_id)
        self.assertNotIn(10, self.s.quest_status_state().active)
        q_id = self.store.take_quest(1, 10, {}, False)
        self.store.finish_quest(q_id, 1, 10, self.day + 1)
        self.assertTrue(self.s.quest_status_state().done(10))
        self.store.note_lent(1, 19, self.day + 1)
        self.assertIn(19, self.s.quest_status_state().loans)
        self.store.forget_lent(1, 19)
        self.assertNotIn(19, self.s.quest_status_state().loans)

    def test_other_characters_do_not_invalidate_this_snapshot(self):
        state = self.s.quest_status_state()
        q_id = self.store.take_quest(2, 10, {}, False)
        self.store.finish_quest(q_id, 2, 10)
        self.store.note_lent(2, 19)
        self.assertIs(state, self.s.quest_status_state())

    def test_expiry_day_reset_and_character_switch(self):
        with patch.object(server.time, 'monotonic', return_value=10):
            first = self.s.quest_status_state()
        with patch.object(server.time, 'monotonic', return_value=13):
            second = self.s.quest_status_state()
        self.assertIsNot(first, second)
        with patch.object(self.s, 'day_start', return_value=self.day + 86400):
            self.assertIsNot(second, self.s.quest_status_state())
        old = self.s.quest_status_state()
        self.s.char_id = 2
        self.assertIsNot(old, self.s.quest_status_state())

    def test_q_list_invalidates_on_location_reload(self):
        self.s.quest_status_state()
        self.s.cmd_q_list({})
        self.assertIsNone(self.s._quest_status_snapshot)

    def test_all_real_quests_match_uncached_availability(self):
        rng = random.Random(427)
        types = list(quests.QUESTS)
        self.history([(1, rng.choice(types), self.day + rng.randrange(-172800, 7200)) for _ in range(700)])
        for t in rng.sample(types, min(15, len(types))):
            self.store.take_quest(1, t, {}, False)
        for level in (0, 5, 10, 20):
            for skill in self.s.char.skill:
                skill[0] = level
            state = quest_state.QuestState(self.store.db, 1, self.day)
            for q in quests.QUESTS.values():
                with self.subTest(level=level, quest=q.type):
                    self.assertEqual(self.s.quest_available(q), self.s.quest_available(q, state))

    def test_action_validation_does_not_use_status_cache(self):
        q = quests.Quest(dict(type=900001, kind='kill_mobs', name='test', give=[1], take=[1], repeatable=False))
        state = self.s.quest_status_state()
        self.assertTrue(self.s.quest_available(q))
        # Simulate another process writing after the display snapshot.
        self.history([(1, q.type, self.day + 1)])
        self.assertTrue(self.s.quest_available(q, state))
        self.assertFalse(self.s.quest_available(q))

    def test_location_scope_includes_dependencies_and_unknown_requests(self):
        self.s.loc = world.location(49)
        self.s.room = None
        types = {t for _, npc in self.s.loc.spawns for t in quests.given_by(npc) + quests.taken_by(npc)}
        state = self.s.quest_status_state(next(iter(types)))
        for t in types:
            q = quests.get(t)
            self.assertTrue(set(q.need_all + q.need_any + q.branch + q.excludes) <= state.types)
            self.assertEqual(self.s.quest_available(q), self.s.quest_available(q, state))
        extra = next((t for t in quests.QUESTS if t not in state.types))
        expanded = self.s.quest_status_state(extra)
        self.assertIn(extra, expanded.types)
        self.assertTrue(state.types <= expanded.types)
        self.assertIsNot(state, expanded)

    def test_scoped_history_keeps_all_active_quests_for_feed_exceptions(self):
        self.history([(1, 10, self.day), (1, 11, self.day)])
        self.store.take_quest(1, 99, {}, False)
        state = quest_state.QuestState(self.store.db, 1, self.day, {10})
        self.assertTrue(state.done(10))
        self.assertFalse(state.done(11))
        self.assertIn(99, state.active)

    def test_cooldown_expires_without_rebuilding_snapshot(self):
        q = quests.Quest(dict(type=900002, kind='kill_mobs', name='cooldown', repeatable=True, cooldown=30))
        self.history([(1, q.type, self.day + 100)])
        state = self.s.quest_status_state()
        for now, available in ((self.day + 110, False), (self.day + 131, True)):
            with patch.object(server.time, 'time', return_value=now):
                self.assertEqual(self.s.quest_available(q, state), available)
                self.assertEqual(self.s.quest_available(q), available)

    def test_request_for_a_dependency_loads_its_own_prerequisites(self):
        first = quests.Quest(dict(type=900010, kind='kill_mobs', name='first', need_quest=900011))
        dependency = quests.Quest(dict(type=900011, kind='kill_mobs', name='next', need_quest=900012))
        self.s.loc = NS(id=99999, spawns=[])
        self.s.room = None
        self.history([(1, 900012, self.day)])
        with patch.dict(quests.QUESTS, {first.type: first, dependency.type: dependency}):
            state = self.s.quest_status_state(first.type)
            self.assertIn(dependency.type, state.types)
            self.assertNotIn(900012, state.types)
            expanded = self.s.quest_status_state(dependency.type)
            self.assertTrue(self.s.quest_available(dependency, expanded))
            self.assertEqual(self.s.quest_available(dependency), self.s.quest_available(dependency, expanded))
if __name__ == '__main__':
    try:
        run_cases(QuestStateTests)
    finally:
        server.STORE.close()
