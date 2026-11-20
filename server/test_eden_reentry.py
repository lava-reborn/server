"""A previous gift, paid release and journeys do not hide repeatable Eden services."""
import unittest

from test_eden_quests import EdenQuestTests
import eden
import quests
from testkit import run_cases


class EdenReentryTests(unittest.TestCase):
    def test_second_assignment_keeps_paid_exits_and_all_six_journeys_after_gift(self):
        t = EdenQuestTests()
        t.setUp()
        self.addCleanup(t.doCleanups)
        t.fund(20_000_000, 20_000)
        t.finish_intro()
        self.assertEqual(t.take(eden.GIFT), [0])
        self.assertEqual(t.hand_in(t.taken_id(eden.GIFT)), [0])
        for qtype in (18120, 18123):
            qid = t.active(qtype)
            t.store.finish_quest(qid, t.cid, qtype, require_active=True)
        self.assertEqual(t.take(eden.GOLD_EXIT), [0])
        self.assertEqual(t.hand_in(t.taken_id(eden.GOLD_EXIT)), [0])
        self.assertIsNone(eden.assigned(t.store, t.cid))
        t.new_sentence()
        self.assertEqual(t.s.eden_sentence['visit'], 2)
        for qtype in (eden.GOLD_EXIT, eden.AFRO_EXIT, 18120, 18121, 18122, 18123, 18124, 18125):
            quest = quests.get(qtype)
            t.contact(quest.give[0])
            self.assertTrue(quest.repeatable)
            self.assertEqual((quest.per_day, quest.cooldown), (0, 0))
            self.assertTrue(t.s.quest_available(quest), qtype)
            t.frames.clear()
            t.s.cmd_q_status(dict(q_type=qtype))
            self.assertEqual([(cmd, p['type'], p['status']) for cmd, p in t.frames],
                             [('q_status', qtype, 1)], qtype)
        self.assertFalse(t.s.quest_available(quests.get(eden.GIFT)))


if __name__ == '__main__':
    run_cases(EdenReentryTests)
