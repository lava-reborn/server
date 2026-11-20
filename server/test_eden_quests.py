"""Exercise real Eden quest transactions on isolated stores, without sockets."""
import logging
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.pop("LAVA_DB_URL", None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)

import accounts  # noqa: E402
import eden  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import server  # noqa: E402
import storage  # noqa: E402
import world  # noqa: E402
from test_quest_state import session  # noqa: E402
from testkit import run_cases  # noqa: E402


class EdenQuestTests(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store.temporary()
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, "STORE", self.store))
        aid, _ = self.store.register("eden_quest_test", "local-password")
        self.cid, _ = self.store.create_character(aid, "EdenQuestTester", 0, "1")
        self.frames, self.departures = [], []
        self.ids = rooms.IdAllocator()
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.active = self.store.character(self.cid)
        self.s.closed, self.s.transport = False, None
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.s.combat = NS(ap=0, ap_max=100, dead=False)
        self.s.send = lambda command, **params: self.frames.append((command, params))
        self.s.live_cell = lambda: self.s.pos
        self.s.push_stats = lambda **_changes: None
        self.s.push_vitals = lambda: None
        self.s.restore = self.restore_place
        self.s.enter_location = lambda: self.departures.append(self.s.loc.id)
        self.new_sentence()

    def restore_place(self, row):
        # Loading/graphics are the I/O boundary. The real departure helper,
        # inventory mutations, character money, quest handlers and SQL all run.
        self.s.active = row
        self.s.loc = world.location(row["loc"])
        self.s.pos = row["pos"] or self.s.loc.entry_cell()
        self.s.gx, self.s.gy = row["gx"], row["gy"]
        self.s.on_map = bool(row["on_map"])

    def new_sentence(self):
        if eden.assigned(self.store, self.cid) is not None:
            eden.release(self.store, self.cid)
        self.s.eden_sentence = eden.assign(
            self.store, self.cid, "local-test", "Isolated quest regression",
            return_state=dict(loc=41, pos=100, gx=5970, gy=1730, on_map=0))
        self.contact(1789)

    def contact(self, npc_type):
        loc_id = {1784: 267, 1785: 267, 1789: 267,
                  1786: 1383, 1787: 1385, 1788: 1384, 1790: 264}[npc_type]
        self.s.loc = world.location(loc_id)
        self.s.gx, self.s.gy = eden.target_cell(loc_id)
        self.s.on_map = False
        self.s.room = rooms.Room(self.s.loc, self.ids, world.mob_types())
        matches = [(eid, entry) for eid, entry in self.s.room.npcs.items()
                   if entry[1] == npc_type]
        self.assertTrue(matches, "requested NPC must exist in the real Eden location")
        eid, entry = matches[0]
        self.s.pos = entry[0]
        self.npc = eid
        return eid

    def give(self, type_id, count=1, slot=inventory.BAG):
        first = None
        remaining = count
        while remaining:
            fields = inventory.new_fields(type_id, remaining)
            root = fields.pop("root")
            fields["slot"] = slot
            row = self.store.create_item(self.cid, type_id, root, **fields)
            if first is None:
                first = row
            remaining -= row["count"] if root in items.HEAPABLE_ROOTS else 1
        return first

    def fund(self, afro=0, gold=0):
        current = self.s.character()
        before = self.store.money(self.cid)
        current.add_money(afro - before[0], gold - before[1])
        current.save(self.store)

    def acknowledgements(self):
        return [p["res"] for command, p in self.frames if command == "cmdAck"]

    def take(self, quest_type, npc_type=None):
        quest = quests.get(quest_type)
        npc_type = quest.give[0] if npc_type is None else npc_type
        self.contact(npc_type)
        self.frames.clear()
        self.s.cmd_q_st(dict(mob=self.npc, q_idx=quests.given_by(npc_type).index(quest_type)))
        return self.acknowledgements()

    def active(self, quest_type):
        quest = quests.get(quest_type)
        progress = quest.fresh_progress()
        if quest.counts_bag:
            progress.update(quest.bag_progress(self.s.inv.bag_pieces()))
        return self.store.take_quest(self.cid, quest_type, progress, quest.is_complete(progress))

    def hand_in(self, qid, npc=None):
        self.frames.clear()
        self.s.cmd_q_co(dict(q_id=qid, mob=self.npc if npc is None else npc, obj_idx=0))
        return self.acknowledgements()

    def taken_id(self, quest_type):
        return next(row["q_id"] for row in self.store.quests(self.cid)
                    if row["type"] == quest_type)

    def finish_intro(self):
        self.assertEqual(self.take(18127), [0])
        self.assertEqual(self.hand_in(self.taken_id(18127)), [0])

    def test_norm_opens_only_after_completing_lukes_introduction(self):
        norm = quests.get(18114)
        self.contact(1785)
        before_money, before_items = self.store.money(self.cid), self.store.items_of(self.cid)
        self.assertFalse(self.s.quest_available(norm))
        self.assertEqual(self.take(18114), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.take(18127), [0])
        self.assertFalse(self.s.quest_available(norm))
        self.assertEqual(self.hand_in(self.taken_id(18127)), [0])
        self.assertEqual(self.store.money(self.cid), before_money)
        self.assertEqual(self.store.items_of(self.cid), before_items)
        self.contact(1785)
        self.assertTrue(self.s.quest_available(norm))
        self.assertEqual(self.take(18114), [0])
        old_norm = self.taken_id(18114)
        self.s.cmd_q_ca(dict(q_id=old_norm))
        self.assertIsNone(self.store.quest(old_norm))
        eden.release(self.store, self.cid)
        self.new_sentence()
        self.contact(1785)
        self.assertTrue(self.s.quest_available(norm))

    def test_three_real_exchanges_feed_the_full_quota_and_exit(self):
        self.fund(afro=0, gold=0)
        with storage.atomic(self.store.db):
            eden.grant_tools(self.store, self.cid)
        self.assertFalse(any(r['type_id'] == eden.BASKET for r in self.store.items_of(self.cid)))
        self.give(eden.PALM_LEAF, 20)
        self.assertEqual(self.take(18116), [0])
        self.assertEqual(self.hand_in(self.taken_id(18116)), [0])
        self.assertEqual(sum(r['type_id'] == eden.BASKET
                             for r in self.store.items_of(self.cid)), 1)
        self.assertFalse(self.store.quest_done(self.cid, 18128))
        self.finish_intro()
        for qtype, banana, ticket, needed in (
                (18111, eden.GREEN_BANANA, eden.GREEN_TICKET, 100),
                (18112, eden.GOOD_BANANA, eden.GOOD_TICKET, 1000),
                (18113, eden.BAD_BANANA, eden.BAD_TICKET, 75)):
            self.give(banana)
            self.assertEqual(self.take(qtype), [0])
            self.assertEqual(self.hand_in(self.taken_id(qtype)), [0])
            self.assertEqual(self.s.inv.bag_pieces().get(ticket), 1)
            self.give(ticket, needed - 1)
        self.assertEqual(self.take(18114), [0])
        self.assertEqual(self.hand_in(self.taken_id(18114)), [0])
        self.assertEqual(self.s.inv.bag_pieces().get(eden.EXIT_PASS), 1)
        for ticket in eden.TICKET_QUOTA:
            self.assertNotIn(ticket, self.s.inv.bag_pieces())
        self.assertEqual(self.take(18115), [0])
        self.assertEqual(self.hand_in(self.taken_id(18115)), [0])
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertFalse(eden.inside(self.s.loc))
        self.assertFalse(any(r['type_id'] in eden.LOCAL_ITEMS
                             for r in self.store.items_of(self.cid)))
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertEqual(len(self.departures), 1)

    def test_each_sorter_exchanges_only_its_banana_kind_once_per_real_submission(self):
        exchanges = ((1788, 18111, eden.GREEN_BANANA, eden.GREEN_TICKET),
                     (1787, 18112, eden.GOOD_BANANA, eden.GOOD_TICKET),
                     (1786, 18113, eden.BAD_BANANA, eden.BAD_TICKET))
        self.fund(afro=0, gold=0)
        for npc_type, qtype, banana, ticket in exchanges:
            with self.subTest(npc=npc_type, quest=qtype):
                quest = quests.get(qtype)
                self.assertEqual(quest.give, [npc_type])
                self.assertEqual(quest.take, [npc_type])
                self.assertEqual(quest.objs[0][:2], (banana, 1))
                self.assertEqual(quest.reward_item(0), (ticket, 1))
                self.give(banana)
                before = self.s.inv.bag_pieces().copy()
                self.assertEqual(self.take(qtype, npc_type), [0])
                qid = self.taken_id(qtype)
                self.assertEqual(self.hand_in(qid), [0])
                after = self.s.inv.bag_pieces().copy()
                self.assertEqual(after.get(banana, 0), before.get(banana, 0) - 1)
                self.assertEqual(after.get(ticket, 0), before.get(ticket, 0) + 1)
                for other in eden.LOCAL_ITEMS - {banana, ticket}:
                    self.assertEqual(after.get(other, 0), before.get(other, 0))
                self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])
                self.assertEqual(self.s.inv.bag_pieces(), after)
                self.assertIsNotNone(eden.assigned(self.store, self.cid))
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertEqual({ticket: self.s.inv.bag_pieces().get(ticket)
                          for _npc, _qtype, _banana, ticket in exchanges},
                         {eden.GREEN_TICKET: 1, eden.GOOD_TICKET: 1, eden.BAD_TICKET: 1})

    def test_all_six_wrong_sorter_hand_ins_preserve_bananas_tickets_and_active_quest(self):
        for qtype, npc_type, banana, ticket in (
                (18111, 1788, eden.GREEN_BANANA, eden.GREEN_TICKET),
                (18112, 1787, eden.GOOD_BANANA, eden.GOOD_TICKET),
                (18113, 1786, eden.BAD_BANANA, eden.BAD_TICKET)):
            self.give(banana)
            self.assertEqual(self.take(qtype, npc_type), [0])
            qid = self.taken_id(qtype)
            before = self.s.inv.bag_pieces().copy()
            for wrong in {1786, 1787, 1788} - {npc_type}:
                with self.subTest(quest=qtype, wrong_sorter=wrong):
                    self.assertNotIn(qtype, quests.given_by(wrong))
                    self.assertNotIn(qtype, quests.taken_by(wrong))
                    self.contact(wrong)
                    self.assertEqual(self.hand_in(qid), [server.RES_WRONG_NPC])
                    self.assertIsNotNone(self.store.quest(qid))
                    self.assertEqual(self.s.inv.bag_pieces(), before)
            self.contact(npc_type)
            self.assertEqual(self.hand_in(qid), [0])
            self.assertNotIn(banana, self.s.inv.bag_pieces())
            self.assertEqual(self.s.inv.bag_pieces().get(ticket), 1)

    def test_paid_gold_charge_is_exact_for_first_and_second_lifetime_visit(self):
        for visit, cost in enumerate((5000, 10000), 1):
            with self.subTest(visit=visit):
                if visit > 1:
                    self.new_sentence()
                self.fund(afro=123, gold=20000)
                global_quest = quests.get(eden.GOLD_EXIT)
                self.assertEqual(global_quest.cost_gold, 5000)
                self.assertEqual(eden.priced(global_quest, self.s.eden_sentence).cost_gold,
                                 cost)
                self.assertEqual(self.s.eden_sentence['visit'], visit)
                self.assertTrue(self.s.fee_ready(global_quest))
                self.assertEqual(self.take(eden.GOLD_EXIT), [0])
                qid = self.taken_id(eden.GOLD_EXIT)
                self.assertEqual(self.hand_in(qid), [0])
                self.assertEqual(self.store.money(self.cid), (123, 20000 - cost))
                self.assertEqual(global_quest.cost_gold, 5000)
                self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])
                self.assertEqual(self.store.money(self.cid), (123, 20000 - cost))
                self.assertEqual(self.store.db.execute(
                    'SELECT visits FROM char_eden_visits WHERE char_id=?',
                    (self.cid,)).fetchone()['visits'], visit)

    def test_paid_afro_charge_is_exact_for_first_and_second_lifetime_visit(self):
        for visit, cost in enumerate((5_000_000, 10_000_000), 1):
            with self.subTest(visit=visit):
                if visit > 1:
                    self.new_sentence()
                self.fund(afro=20_000_000, gold=7)
                quest = quests.get(eden.AFRO_EXIT)
                self.assertEqual(quest.cost_afro, 5_000_000)
                self.assertEqual(eden.priced(quest, self.s.eden_sentence).cost_afro,
                                 cost)
                self.assertEqual(self.s.eden_sentence['visit'], visit)
                self.assertTrue(self.s.fee_ready(quest))
                self.assertEqual(self.take(eden.AFRO_EXIT), [0])
                qid = self.taken_id(eden.AFRO_EXIT)
                self.assertEqual(self.hand_in(qid), [0])
                self.assertEqual(self.store.money(self.cid),
                                 (20_000_000 - cost, 7))
                self.assertEqual(self.store.db.execute(
                    'SELECT visits FROM char_eden_visits WHERE char_id=?',
                    (self.cid,)).fetchone()['visits'], visit)

    def test_changing_payment_currency_does_not_reset_the_visit_price(self):
        self.fund(gold=5000)
        self.assertEqual(self.take(eden.GOLD_EXIT), [0])
        self.assertEqual(self.hand_in(self.taken_id(eden.GOLD_EXIT)), [0])
        self.new_sentence()
        self.fund(afro=10_000_000)
        self.assertEqual(self.s.eden_sentence["visit"], 2)
        self.assertEqual(self.take(eden.AFRO_EXIT), [0])
        self.assertEqual(self.hand_in(self.taken_id(eden.AFRO_EXIT)), [0])
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.new_sentence()
        self.fund(afro=100_000_000, gold=100_000)
        self.assertEqual(self.s.eden_sentence["visit"], 3)
        for qtype in (eden.GOLD_EXIT, eden.AFRO_EXIT):
            with self.subTest(third_visit_currency=qtype):
                quest = quests.get(qtype)
                self.assertFalse(self.s.quest_available(quest))
                self.assertEqual(self.take(qtype), [server.RES_NOT_AVAILABLE])
                forged = self.active(qtype)
                self.assertEqual(self.hand_in(forged), [server.RES_NOT_AVAILABLE])
                self.assertIsNotNone(self.store.quest(forged))
                self.assertEqual(self.store.money(self.cid), (100_000_000, 100_000))
                self.assertIsNotNone(eden.assigned(self.store, self.cid))

    def test_later_visits_refuse_old_paid_quests_even_with_stale_cache_and_advertised_fee(self):
        self.fund(afro=100_000_000, gold=100_000)
        old_sentence = dict(self.s.eden_sentence)
        paid = []
        for qtype in (eden.GOLD_EXIT, eden.AFRO_EXIT):
            self.assertEqual(self.take(qtype), [0])
            paid.append((qtype, self.taken_id(qtype)))
        self.new_sentence()
        for visit in range(3, 11):
            self.new_sentence()
            self.assertEqual(self.s.eden_sentence['visit'], visit)
            live_sentence = dict(self.s.eden_sentence)
            # Simulate a first-visit cache and a genuine old active quest.
            # The locked hand-in must still use the current persisted visit.
            for qtype, qid in paid:
                with self.subTest(visit=visit, currency=qtype):
                    self.s.eden_sentence = old_sentence
                    self.contact(1789)
                    before = (self.store.money(self.cid), self.store.items_of(self.cid),
                              self.store.quests(self.cid))
                    self.assertEqual(self.hand_in(qid), [server.RES_NOT_AVAILABLE])
                    self.assertEqual((self.store.money(self.cid), self.store.items_of(self.cid),
                                      self.store.quests(self.cid)), before)
                    self.assertEqual(eden.assigned(self.store, self.cid), live_sentence)
                    self.assertEqual(self.departures, [])
                    self.s.eden_sentence = live_sentence
                    quest = quests.get(qtype)
                    self.assertIs(eden.priced(quest, live_sentence), quest)
                    self.assertFalse(eden.allowed(self.s, quest))

    def test_third_visit_still_allows_complete_work_quota_and_unpaid_release(self):
        self.new_sentence()
        self.new_sentence()
        self.assertEqual(self.s.eden_sentence['visit'], 3)
        self.fund(afro=0, gold=0)
        self.finish_intro()
        for qtype, banana, ticket, needed in (
                (18111, eden.GREEN_BANANA, eden.GREEN_TICKET, 100),
                (18112, eden.GOOD_BANANA, eden.GOOD_TICKET, 1000),
                (18113, eden.BAD_BANANA, eden.BAD_TICKET, 75)):
            self.give(banana)
            self.assertEqual(self.take(qtype), [0])
            self.assertEqual(self.hand_in(self.taken_id(qtype)), [0])
            self.give(ticket, needed - 1)
        self.assertEqual(self.take(18114), [0])
        self.assertEqual(self.hand_in(self.taken_id(18114)), [0])
        self.assertEqual(self.s.inv.bag_pieces().get(eden.EXIT_PASS), 1)
        self.assertEqual(self.take(18115), [0])
        self.assertEqual(self.hand_in(self.taken_id(18115)), [0])
        self.assertIsNone(eden.assigned(self.store, self.cid))
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertFalse(any(row['type_id'] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.cid)))
        self.assertEqual(self.store.db.execute(
            'SELECT visits FROM char_eden_visits WHERE char_id=?',
            (self.cid,)).fetchone()['visits'], 3)

    def test_local_work_does_not_require_remaining_daily_quest_allowance(self):
        self.give(eden.GREEN_BANANA)
        with patch.object(self.s, "daily_available", return_value=0):
            self.assertEqual(self.take(18111), [0])
            self.assertEqual(self.hand_in(self.taken_id(18111)), [0])
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GREEN_TICKET), 1)
        self.assertFalse(any(command == "q_sys" for command, _params in self.frames))

    def test_insufficient_currency_neither_releases_nor_spends(self):
        for qtype, afro, gold in ((eden.GOLD_EXIT, 10_000_000, 4999),
                                  (eden.AFRO_EXIT, 4_999_999, 50000)):
            with self.subTest(quest=qtype):
                self.fund(afro, gold)
                self.assertFalse(self.s.fee_ready(quests.get(qtype)))
                self.assertEqual(self.take(qtype), [0])
                qid = self.taken_id(qtype)
                self.assertEqual(self.hand_in(qid), [server.RES_NO_MONEY])
                self.assertEqual(self.store.money(self.cid), (afro, gold))
                self.assertIsNotNone(eden.assigned(self.store, self.cid))
                self.assertIsNotNone(self.store.quest(qid))
                self.assertFalse(self.store.quest_done(self.cid, qtype))

    def test_release_failure_rolls_back_payment_items_history_and_sentence(self):
        self.fund(gold=5000)
        banana = self.give(eden.GOOD_BANANA)
        self.assertEqual(self.take(eden.GOLD_EXIT), [0])
        qid = self.taken_id(eden.GOLD_EXIT)
        before = self.store.money(self.cid)
        original = eden.complete_release

        def fail_after_cleanup(*args):
            original(*args)
            raise RuntimeError("injected departure write failure")

        with patch.object(eden, "complete_release", side_effect=fail_after_cleanup):
            self.assertEqual(self.hand_in(qid), [1])
        self.assertEqual(self.store.money(self.cid), before)
        self.assertEqual(self.s.character().gold, before[1])
        self.assertIsNotNone(self.store.item(banana["uniq"]))
        self.assertIsNotNone(eden.assigned(self.store, self.cid))
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, eden.GOLD_EXIT))
        self.assertEqual(self.departures, [])
        self.assertEqual(self.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid)[1], 0)

    def test_failed_release_does_not_publish_temporary_loss_of_basket_stats(self):
        self.fund(gold=5000)
        self.give(eden.BASKET, slot=inventory.BELT)
        self.assertEqual(self.take(eden.GOLD_EXIT), [0])
        qid = self.taken_id(eden.GOLD_EXIT)
        self.s.inv.refresh_gear()
        before = self.s.character().vitals()
        broadcasts = []
        self.s.room.broadcast = lambda frame, **_kw: broadcasts.append(frame)
        original = eden.complete_release

        def fail_after_cleanup(*args):
            original(*args)
            raise RuntimeError("failure after removing worn local basket")

        with patch.object(eden, "complete_release", side_effect=fail_after_cleanup):
            self.assertEqual(self.hand_in(qid), [1])
        self.assertEqual(self.s.character().vitals(), before)
        self.assertEqual(broadcasts, [])

    def test_npc_id_from_a_previous_room_cannot_authorize_exit(self):
        self.fund(gold=5000)
        self.assertEqual(self.take(eden.GOLD_EXIT), [0])
        qid, previous_npc = self.taken_id(eden.GOLD_EXIT), self.npc
        self.contact(1787)
        self.assertIsNone(self.s.room.npc(previous_npc))
        self.assertEqual(self.hand_in(qid, previous_npc), [server.RES_WRONG_NPC])
        self.assertEqual(self.store.money(self.cid)[1], 5000)
        self.assertIsNotNone(eden.assigned(self.store, self.cid))

    def test_release_reclaims_local_bag_body_bank_but_preserves_ordinary_items(self):
        own = self.give(inventory.STARTER_PISTOL, slot=inventory.PRIMARY)
        own_ammo = self.give(inventory.STARTER_AMMO, 20)
        local = [self.give(eden.BASKET, slot=inventory.BELT),
                 self.give(eden.PALM_LEAF, 10, slot=inventory.BANK),
                 self.give(eden.GOOD_BANANA), self.give(eden.GREEN_TICKET)]
        self.give(eden.EXIT_PASS)
        self.assertEqual(self.take(18115), [0])
        self.assertEqual(self.hand_in(self.taken_id(18115)), [0])
        for row in local:
            self.assertIsNone(self.store.item(row["uniq"]))
        for row in (own, own_ammo):
            self.assertEqual(self.store.item(row["uniq"]), row)
        self.assertFalse(any(row["type_id"] in eden.LOCAL_ITEMS
                             for row in self.store.items_of(self.cid)))
        self.assertFalse(any(row["type"] in eden.QUESTS
                             for row in self.store.quests(self.cid)))

    def test_far_or_wrong_npc_does_not_allow_paid_exit(self):
        self.fund(gold=5000)
        self.assertEqual(self.take(eden.GOLD_EXIT), [0])
        qid = self.taken_id(eden.GOLD_EXIT)
        self.s.pos = next(c for c in self.s.loc.entries
                          if not progression.within_reach(c, self.s.room.npc(self.npc)[0],
                                                          self.s.loc.width, self.s.loc.height))
        self.assertEqual(self.hand_in(qid), [progression.ERR_TOO_FAR])
        self.assertEqual(self.store.money(self.cid)[1], 5000)
        wrong = self.contact(1784)
        self.assertEqual(self.hand_in(qid, wrong), [server.RES_WRONG_NPC])
        self.assertIsNotNone(eden.assigned(self.store, self.cid))

    def test_forged_active_exit_outside_or_after_release_cannot_charge(self):
        self.fund(gold=5000)
        qid = self.active(eden.GOLD_EXIT)
        self.s.loc = world.location(41)
        self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid)[1], 5000)
        self.contact(1789)
        eden.release(self.store, self.cid)
        # Deliberately retain the stale cached sentence. The actual hand-in
        # must consult the database while holding the quest character lock.
        self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid)[1], 5000)
        self.assertIsNotNone(self.store.quest(qid))

    def test_no_assignment_means_no_quest_availability_or_forged_hand_in(self):
        eden.release(self.store, self.cid)
        self.s.eden_sentence = None
        for qtype in (18111, 18114, 18115, 18117, 18119, 18127):
            self.assertFalse(self.s.quest_available(quests.get(qtype)))
        self.assertEqual(self.take(eden.GOLD_EXIT), [server.RES_NOT_AVAILABLE])
        qid = self.active(eden.GOLD_EXIT)
        self.assertEqual(self.hand_in(qid), [server.RES_NO_SUCH])

if __name__ == "__main__":
    try:
        run_cases(EdenQuestTests)
    finally:
        server.STORE.close()
