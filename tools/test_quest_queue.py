"""Execute emitted quest-read queue recovery; never reset the cmdAck FIFO."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parent.parent / 'server')]
import widescreen as w
from avm_test import Arr, execute
from testkit import run_cases


class Queue(Arr):
    def shift(self):
        return self.pop(0) if self else None


class QuestQueue(unittest.TestCase):
    def setup_queue(self, names=('q_status', 'q_si', 'q_di')):
        queue = Queue(NS(name=name) for name in names)
        cls = NS(callStack=queue, callCount=0, packageLength=1, sInstance=None)
        sent = []
        conn = NS(allowed=False)
        def send(message):
            if not conn.allowed:
                return False
            sent.append(message.name)
            return True
        conn.Send = send
        inspector = NS(XMC=conn)
        env = dict(this=inspector, lol=NS(core=NS(quests=NS(QuestInspector=cls))))
        inspector.sendCall = lambda: execute(w.fn_quest_send_call().assemble(), env)
        cls.sInstance = inspector
        return cls, inspector, conn, sent, env

    def test_filtered_reads_stay_queued_without_a_phantom_inflight_request(self):
        cls, inspector, conn, sent, _env = self.setup_queue()
        head = cls.callStack[0]
        for _ in range(5):
            inspector.sendCall()
        self.assertEqual(cls.callCount, 0)
        self.assertIs(cls.callStack[0], head)
        self.assertEqual(len(cls.callStack), 3)
        self.assertEqual(sent, [])

    def test_read_fifo_resumes_and_never_duplicates_an_inflight_request(self):
        cls, inspector, conn, sent, _env = self.setup_queue()
        inspector.sendCall()
        conn.allowed = True
        for name in ('q_status', 'q_si', 'q_di'):
            inspector.sendCall()
            self.assertEqual(sent[-1], name)
            self.assertEqual(cls.callCount, 1)
            inspector.sendCall()
            self.assertEqual(sent.count(name), 1)
            cls.callCount -= 1  # original updateCall on the matching response
        inspector.sendCall()
        self.assertEqual((cls.callCount, list(cls.callStack)), (0, []))

    def test_state_change_resumes_only_after_the_original_filter_update(self):
        cls, inspector, conn, sent, env = self.setup_queue()
        inspector.sendCall()
        filters = NS()
        setattr(filters, '__questFilterOrig', lambda: setattr(conn, 'allowed', True))
        execute(w.fn_quest_filter_resume().assemble(), dict(this=filters, lol=env['lol']))
        self.assertEqual((sent, cls.callCount), (['q_status'], 1))

    def test_reentrant_send_observer_cannot_send_the_head_twice(self):
        cls, inspector, conn, sent, _env = self.setup_queue(('q_status',))
        def send(message):
            self.assertEqual(cls.callCount, 1)
            inspector.sendCall()
            sent.append(message.name)
            return True
        conn.Send = send
        inspector.sendCall()
        self.assertEqual((sent, cls.callCount, len(cls.callStack)), (['q_status'], 1, 0))

    def test_repeated_npc_refresh_replaces_timer_without_touching_inflight_reads(self):
        cls, inspector, _conn, sent, env = self.setup_queue()
        cls.callCount = 1
        head = cls.callStack[0]
        timers, events = {}, []

        def cancel(timer):
            events.append(("cancel", timer))
            timers.pop(timer, None)

        def original():
            timer = len(events)
            events.append(("start", timer))
            timers[timer] = "requestNPC"
            inspector.updateTimerID = timer

        setattr(inspector, '__questRefreshNPCOrig', original)
        env['clearInterval'] = cancel
        for _ in range(3):
            execute(w.fn_quest_refresh_npcs().assemble(), env)
            self.assertEqual(len(timers), 1)
            self.assertIn(inspector.updateTimerID, timers)
            self.assertEqual(cls.callCount, 1)
            self.assertIs(cls.callStack[0], head)
            self.assertEqual(len(cls.callStack), 3)
            self.assertEqual(sent, [])
        self.assertEqual(events, [("start", 0), ("cancel", 0),
                                  ("start", 2), ("cancel", 2), ("start", 4)])

    def test_filter_change_does_not_construct_a_quest_singleton(self):
        cls, _inspector, _conn, sent, env = self.setup_queue()
        cls.sInstance = None
        calls = []
        filters = NS()
        setattr(filters, '__questFilterOrig', lambda: calls.append('original'))
        execute(w.fn_quest_filter_resume().assemble(), dict(this=filters, lol=env['lol']))
        self.assertEqual(calls, ['original'])
        self.assertEqual(sent, [])


if __name__ == '__main__':
    run_cases(QuestQueue)
