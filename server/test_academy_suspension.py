"""All academy XP lessons closed; knives and safe journal cancellation remain."""
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import accounts
import progression
import quests
import server
import world
from test_quest_state import session
from testkit import run_cases


class AcademySuspension(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, 'STORE', previous)
        aid, _ = self.store.register('academy-test', 'local-only')
        self.cid, _ = self.store.create_character(aid, 'AcademyTest', 0, '1')
        self.s = session(self.store, level=17, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        for skill in self.s.char.skill:
            skill[:] = [17, 0, progression.skill_xp_max(17)]
        for idx in progression.LEARNABLE:
            self.s.char.spec[idx] = [0, 0, progression.spec_xp_max(0)]
        self.s.char.afro, self.s.char.gold = 123456, 100000
        self.s.char.save(self.store)
        self.s.closed, self.s.transport, self.s.residence_timer = False, None, None
        self.s.close = lambda force=False: setattr(self.s, 'closed', True)
        self.npc = 1425
        self.s.loc = NS(id=1295, width=64, height=128, spawns=[])
        self.s.room = NS(npc=lambda _: (0, self.npc, world.COMMONER))
        self.s.pos = 0
        self.s.active = self.store.character(self.cid)
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames, self.messages = [], []
        self.s.send = lambda cmd, **p: self.frames.append((cmd, p))
        self.s.send_player_info = lambda: None
        self.s.say = self.s.answer = self.messages.append

    def snapshot(self):
        return (self.store.character(self.cid), self.s.inv.rows(),
                [dict(r) for r in self.store.load_stats(self.cid)],
                [dict(r) for r in self.store.db.execute(
                    'SELECT * FROM char_quests_done WHERE char_id=? ORDER BY id', (self.cid,))],
                [dict(r) for r in self.store.db.execute(
                    'SELECT * FROM money_ledger WHERE char_id=? ORDER BY id', (self.cid,))],
                self.s.char.rows(), self.s.char.afro, self.s.char.gold)

    def test_gate_matches_all_generated_lessons_and_only_knives_pay_academy_xp(self):
        data = Path(__file__).resolve().parents[1] / 'data/questgen_academy.json'
        lessons = {q['type'] for q in json.loads(data.read_text(encoding='utf-8'))['quests']}
        self.assertEqual(len(lessons), 75)
        self.assertEqual(quests.DISABLED_ACADEMY_LESSONS, lessons)
        self.assertTrue(all(quests.acquisition_blocked(quests.get(t)) for t in lessons))
        available = {q.type for q in quests.QUESTS.values()
                     if set(q.give) & {1425, 1426, 1427, 1428}
                     and (q.rew_xp or q.rew_spec_xp) and not quests.acquisition_blocked(q)}
        self.assertEqual(available, {967})

    def test_all_75_forged_take_requests_refuse_without_any_writes(self):
        before = self.snapshot()
        for kind in sorted(quests.DISABLED_ACADEMY_LESSONS):
            with self.subTest(quest=kind):
                q = quests.get(kind)
                self.npc = q.give[0]
                offered = quests.given_by(self.npc)
                self.assertIn(kind, offered)  # Stable NPC and journal indices.
                self.assertFalse(self.s.quest_available(q))
                self.frames.clear()
                self.s.cmd_q_st(dict(mob=1, q_idx=offered.index(kind)))
                self.assertEqual(self.frames, [('cmdAck', dict(res=server.RES_NOT_AVAILABLE))])
                self.assertFalse(self.store.has_quest(self.cid, kind))
                self.assertEqual(self.snapshot(), before)

    def test_old_complete_lessons_cannot_charge_or_grant_xp_even_on_replay(self):
        for kind in sorted(quests.DISABLED_ACADEMY_LESSONS):
            with self.subTest(quest=kind):
                self.npc = quests.get(kind).take[0]
                active = self.store.take_quest(self.cid, kind, {'obj': 1}, True)
                before = self.snapshot()
                record = dict(self.store.quest(active))
                for _ in range(2):
                    self.frames.clear()
                    self.s.cmd_q_co(dict(q_id=active, mob=1, obj_idx=0))
                    self.assertEqual(self.frames, [('cmdAck', dict(res=server.RES_NOT_AVAILABLE))])
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(dict(self.store.quest(active)), record)
                    self.assertEqual(self.s.char.level, 17)
                    self.assertIn('отключены', self.messages[-1])
                self.store.drop_quest(active)

    def test_every_old_lesson_can_be_cancelled_without_charging_or_rewarding(self):
        for kind in sorted(quests.DISABLED_ACADEMY_LESSONS):
            with self.subTest(quest=kind):
                active = self.store.take_quest(self.cid, kind, {'obj': 1}, True)
                before = self.snapshot()
                self.frames.clear()
                self.s.cmd_q_ca(dict(q_id=active))
                self.assertIn(('cmdAck', dict(res=0)), self.frames)
                self.assertIsNone(self.store.quest(active))
                self.assertEqual(self.snapshot(), before)

    def test_entry_exit_and_knives_remain_available_and_rewards_unchanged(self):
        for kind in (965, 966, 967):
            self.assertFalse(quests.acquisition_blocked(quests.get(kind)))
        q = quests.get(967)
        self.assertEqual((q.rew_xp, q.rew_spec_xp, q.rew_afro, q.per_day),
                         ([], [(quests.SPEC_KEYS['unarmed'], 200000)], 25000, 1))
        self.npc = 1425
        self.assertTrue(self.s.quest_available(q))
        self.s.inv.give_pieces(4203, 50)
        active = self.store.take_quest(self.cid, 967, q.bag_progress(self.s.inv.bag_pieces()), True)
        before = self.s.char.afro
        skills = [list(skill) for skill in self.s.char.skill]
        self.frames.clear()
        self.s.cmd_q_co(dict(q_id=active, mob=1, obj_idx=0))
        self.assertIn(('cmdAck', dict(res=0)), self.frames)
        self.assertIsNone(self.store.quest(active))
        self.assertEqual(self.s.char.afro, before + 25000)
        self.assertEqual(self.s.char.skill, skills)
        self.assertEqual(self.s.char.spec[0], [3, 108750, 640000])


if __name__ == '__main__':
    run_cases(AcademySuspension)
