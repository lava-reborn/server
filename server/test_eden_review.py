"""Eden integration regressions: committed exits, rollback and admission boundaries."""
import contextlib
from itertools import product
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_mortimer_sales as fixtures
import eden
import inventory
import items
import quests
import server
import storage
import world
from testkit import run_cases


class EdenReviewTests(unittest.TestCase):
    give = fixtures.MortimerSales.give

    def setUp(self):
        fixtures.MortimerSales.setUp(self)
        self.s.char.gold = 20000
        self.s.char.afro = 10000000
        self.s.char.save(self.store)
        self.s.loc = NS(id=eden.CENTER, width=20, height=20, file='Eden')
        self.s.pos = 0
        self.s.live_cell = lambda: self.s.pos
        self.s.combat = NS(ap=0, ap_max=100)
        self.s.room = NS(npc=lambda n: (0, 1789, world.COMMONER),
                         players=[], broadcast=lambda *a, **kw: None)
        self.s.send_player_info = lambda: self.s.send('money', gold=self.s.char.gold)
        self.s.eden_sentence = eden.assign(self.store, self.cid, 'review', 'review')

    def exit_quest(self, type_id):
        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(1789).index(type_id)))
        rows = [r for r in self.store.quests(self.cid) if r['type'] == type_id]
        self.assertEqual(len(rows), 1)
        self.frames.clear()
        return rows[0]['q_id']

    @contextlib.contextmanager
    def lost_outer_commit_reply(self):
        original = storage.atomic
        lost = [False]

        @contextlib.contextmanager
        def lost_reply(db):
            outer = getattr(db, '_atomic_depth', 0) == 0
            with original(db):
                yield db
            if outer and not lost[0]:
                lost[0] = True
                raise storage.CommitError('committed but reply lost')

        with patch.object(storage, 'atomic', lost_reply):
            yield

    def assert_committed_exit(self, exit_type, expected_money):
        q_id = self.exit_quest(exit_type)
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.give(type_id)
            if type_id == eden.BAD_BANANA:
                # Also reclaim any legacy local property left in storage.
                self.store.update_item(row['uniq'], slot=inventory.BANK)
        self.give(6946, 3)
        banked = self.give(3159, 2)
        self.store.update_item(banked['uniq'], slot=inventory.BANK)
        self.frames.clear()
        with self.lost_outer_commit_reply():
            self.s.cmd_q_co(dict(q_id=q_id, mob=1))
        self.assertTrue(self.s.closed)
        self.assertEqual(self.store.money(self.cid), expected_money)
        self.assertEqual((self.s.char.afro, self.s.char.gold), expected_money)
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertIsNone(self.store.quest(q_id))
        self.assertFalse(any(eden.restricted_item(r['type_id'])
                             for r in self.store.items_of(self.cid)))
        self.assertEqual(sorted((r['type_id'], r['slot'], r['count'])
                                for r in self.store.items_of(self.cid)),
                         [(3159, inventory.BANK, 2), (6946, inventory.BAG, 3)])
        self.assertEqual(self.frames, [])
        self.assertFalse(eden.inside(self.store.character(self.cid)['loc']))

    def test_committed_gold_exit_does_not_refund_when_commit_reply_is_lost(self):
        self.assert_committed_exit(eden.GOLD_EXIT, (10000000, 15000))

    def test_committed_afro_exit_does_not_refund_when_commit_reply_is_lost(self):
        self.assert_committed_exit(eden.AFRO_EXIT, (5000000, 20000))

    def test_third_visit_rejects_forged_payment_before_release_or_money_mutation(self):
        old_sentence = self.s.eden_sentence
        for _ in range(2):
            eden.release(self.store, self.cid)
            current = eden.assign(self.store, self.cid, 'review', 'repeat visit')
        self.assertEqual(current['visit'], 3)
        # The UI cache can be old; admission must use the row read under
        # quest_write's character lock, before charging or removing items.
        self.s.eden_sentence = old_sentence
        for qtype in (eden.GOLD_EXIT, eden.AFRO_EXIT):
            quest = quests.get(qtype)
            q_id = self.store.take_quest(self.cid, qtype, quest.fresh_progress(), True)
            self.frames.clear()
            before = (self.store.money(self.cid), self.inv.rows(),
                      self.store.quests(self.cid), eden.assigned(self.store, self.cid))
            with patch.object(eden, 'complete_release') as release:
                self.s.cmd_q_co(dict(q_id=q_id, mob=1))
                release.assert_not_called()
            self.assertEqual(self.frames, [('cmdAck', {'res': server.RES_NOT_AVAILABLE})])
            self.assertEqual((self.store.money(self.cid), self.inv.rows(),
                              self.store.quests(self.cid), eden.assigned(self.store, self.cid)), before)

    def test_release_failure_rolls_back_fee_sentence_items_and_quest(self):
        q_id = self.exit_quest(eden.GOLD_EXIT)
        self.give(eden.GOOD_BANANA, 2)
        self.give(6946, 3)
        before_items = self.inv.rows()
        before_sentence = eden.assigned(self.store, self.cid)
        self.frames.clear()
        with patch.object(self.store, 'save_position', side_effect=RuntimeError('write failed')):
            self.s.cmd_q_co(dict(q_id=q_id, mob=1))
        self.assertEqual(self.store.money(self.cid), (10000000, 20000))
        self.assertEqual((self.s.char.afro, self.s.char.gold), (10000000, 20000))
        self.assertEqual(self.inv.rows(), before_items)
        self.assertEqual(eden.assigned(self.store, self.cid), before_sentence)
        self.assertIsNotNone(self.store.quest(q_id))
        self.assertFalse(self.s.closed)
        self.assertFalse(any(cmd == 'money' or (cmd == 'cmdAck' and p['res'] == 0)
                             for cmd, p in self.frames))

    def test_enforcement_returns_a_sentenced_character_from_any_destination(self):
        self.s.loc = NS(id=41)
        self.s.on_map = True
        self.s._accepted_place = (41, 5, 5970, 1730, False)
        cancelled = []
        self.s.cancel_travel = lambda: cancelled.append(True)
        eden.enforce(self.s, self.store, (41, 5970, 1730))
        self.assertEqual(self.s.loc.id, eden.CENTER)
        self.assertFalse(self.s.on_map)
        self.assertIsNone(self.s._accepted_place)
        self.assertEqual(cancelled, [True])
        self.assertEqual((self.s.gx, self.s.gy), eden.CELLS[eden.CENTER])

    def test_ordinary_character_cannot_enter_or_take_eden_quests(self):
        eden.release(self.store, self.cid)
        self.s.eden_sentence = None
        home_loc = NS(id=41, entry_cell=lambda: 10)
        self.s.cancel_travel = lambda: None
        with patch.object(world, 'location', return_value=home_loc):
            eden.enforce(self.s, self.store, (41, 5970, 1730))
        self.assertEqual((self.s.loc.id, self.s.pos, self.s.on_map), (41, 10, False))
        for quest_type in sorted(eden.QUESTS):
            self.assertFalse(eden.allowed(self.s, quests.get(quest_type)))
        ordinary = quests.get(51)
        self.assertNotIn(ordinary.type, eden.QUESTS)
        self.assertTrue(eden.allowed(self.s, ordinary))

    def test_ordinary_quest_cannot_be_handed_to_an_eden_npc(self):
        ordinary = quests.get(51)
        q_id = self.store.take_quest(self.cid, ordinary.type, {}, True)
        before = (self.store.money(self.cid), self.inv.rows(),
                  eden.assigned(self.store, self.cid))
        self.frames.clear()
        self.s.cmd_q_co(dict(q_id=q_id, mob=1))
        self.assertEqual(self.frames, [('cmdAck', {'res': server.RES_WRONG_NPC})])
        self.assertIsNotNone(self.store.quest(q_id))
        self.assertEqual((self.store.money(self.cid), self.inv.rows(),
                          eden.assigned(self.store, self.cid)), before)

    def test_quests_require_a_local_npc_even_when_global_map_is_available(self):
        # Real map/edge commands for every filled scene are covered by
        # test_eden_map. A stale NPC quest window on global must still fail.
        for loc_id in eden.LOCATIONS:
            self.s.loc = world.location(loc_id)
            self.s.on_map = True
            for qtype in eden.QUESTS:
                self.assertFalse(eden.allowed(self.s, quests.get(qtype)), (loc_id, qtype))

    def test_local_property_is_bound_and_does_not_become_a_transfer_route(self):
        import barter
        import mail
        for type_id in sorted(eden.LOCAL_ITEMS):
            with self.subTest(type_id=type_id):
                info = items.params_of(type_id)
                self.assertTrue(info['quest'])
                self.assertFalse(info['exchang'])
                self.assertFalse(info['cost'] or info['g_cost'])
                self.assertFalse(barter.tradable(type_id))
                self.assertFalse(mail.postable(type_id))

    def test_delete_cannot_destroy_any_local_work_item(self):
        sentence = self.s.eden_sentence
        self.s.answer = lambda text: self.frames.append(('answer', text))
        states = [(loc, None) for loc in sorted(eden.LOCATIONS)]
        states.append((41, sentence))
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.give(type_id)
            for (loc_id, active_sentence), slot in product(states, (inventory.BAG, inventory.PRIMARY)):
                with self.subTest(type_id=type_id, loc=loc_id, sentenced=bool(active_sentence), slot=slot):
                    self.s.loc = NS(id=loc_id)
                    self.s.eden_sentence = active_sentence
                    self.store.update_item(row['uniq'], slot=slot)
                    before = (self.inv.rows(), self.store.money(self.cid),
                              eden.assigned(self.store, self.cid))
                    self.frames.clear()
                    with patch.object(self.inv, 'forget_reload') as forget:
                        self.s.cmd_ss_use(dict(type=inventory.USE_DELETE,
                                               obj=inventory.oid_of(row)))
                        forget.assert_not_called()
                    self.assertEqual((self.inv.rows(), self.store.money(self.cid),
                                      eden.assigned(self.store, self.cid)), before)
                    self.assertEqual(self.frames[0],
                                     ('cmdAck', {'res': inventory.RES_UNWORDED}))
                    self.assertEqual(len(self.frames), 2)
                    self.assertEqual(self.frames[1][0], 'answer')
                    self.assertIn('нельзя удалить', self.frames[1][1])

    def test_ordinary_deletion_is_unchanged_inside_and_outside_eden(self):
        for loc_id, active_sentence in ((eden.CENTER, self.s.eden_sentence), (41, None)):
            with self.subTest(loc=loc_id):
                self.s.loc = NS(id=loc_id)
                self.s.eden_sentence = active_sentence
                row = self.give(6946, 3)
                self.s.cmd_ss_use(dict(type=inventory.USE_DELETE,
                                       obj=inventory.oid_of(row)))
                self.assertIsNone(self.store.item(row['uniq']))
                self.assertEqual(self.frames[0], ('cmdAck', {'res': inventory.RES_OK}))
                self.assertEqual([p['status'] for cmd, p in self.frames
                                  if cmd == 'ss_obj_status'], [0])

    def test_local_items_remain_bound_outside_without_any_active_sentence(self):
        eden.release(self.store, self.cid)
        self.s.loc = NS(id=41)
        self.s.eden_sentence = None
        self.s.answer = lambda text: self.frames.append(('answer', text))
        for type_id in sorted(eden.LOCAL_ITEMS):
            row = self.give(type_id)
            self.frames.clear()
            self.s.cmd_ss_use(dict(type=inventory.USE_DELETE, obj=inventory.oid_of(row)))
            self.assertEqual(self.store.item(row['uniq']), row)
            self.assertEqual(self.frames[0], ('cmdAck', {'res': inventory.RES_UNWORDED}))
            self.assertFalse(any(cmd == 'ss_obj_status' for cmd, _ in self.frames))


if __name__ == '__main__':
    run_cases(EdenReviewTests)
