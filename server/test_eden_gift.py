"""The optional Eden gift pays once, only during the character's first visit."""
import unittest
from unittest.mock import patch

from test_eden_quests import EdenQuestTests
import combat
import eden
import inventory
import items
import progression
import quests
import server
import world
from testkit import run_cases


GIFT, BASKET_QUEST = eden.GIFT, 18116


class EdenGiftTests(unittest.TestCase):
    def setUp(self):
        fixture = EdenQuestTests("test_three_real_exchanges_feed_the_full_quota_and_exit")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.store, self.s, self.cid = fixture, fixture.store, fixture.s, fixture.cid
        self.q = quests.get(GIFT)

    def test_definition_preserves_optional_gift_and_independent_basket_recipe(self):
        self.assertEqual((self.q.cost_afro, self.q.cost_gold), (15000, 0))
        self.assertEqual(self.q.reward_item(0), (eden.GOOD_TICKET, 500))
        self.assertEqual((self.q.repeatable, self.q.per_day, self.q.service), (0, 0, True))
        self.assertEqual((self.q.give, self.q.take), ([1789], [1789]))
        basket = quests.get(BASKET_QUEST)
        self.assertEqual((basket.need_all, basket.need_any), ([], []))
        self.assertEqual((basket.cost_afro, basket.cost_gold), (0, 0))
        self.assertEqual(items.params_of(eden.BASKET)['bonus_attribs_m'], 1)
        self.assertEqual(items.params_of(eden.BASKET)['bonus_attribs'], [20])
        self.assertIn(GIFT, eden.QUESTS)

    def buy(self):
        self.assertEqual(self.fixture.take(GIFT), [0])
        qid = self.fixture.taken_id(GIFT)
        self.assertEqual(self.fixture.hand_in(qid), [0])
        return qid

    def test_first_purchase_pays_exactly_15000_and_creates_five_valid_ticket_stacks(self):
        self.fixture.fund(afro=15000, gold=123)
        self.assertEqual(self.s.eden_sentence['visit'], 1)
        self.assertTrue(self.s.quest_available(self.q))
        before = self.store.money(self.cid)
        self.assertEqual(self.fixture.take(GIFT), [0])
        qid = self.fixture.taken_id(GIFT)
        self.assertEqual(self.store.money(self.cid), before)
        with patch.object(self.s, "daily_available", return_value=0):
            self.assertEqual(self.fixture.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid), (0, 123))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_TICKET), 500)
        rows = [r for r in self.store.items_of(self.cid) if r["type_id"] == eden.GOOD_TICKET]
        self.assertEqual(sorted(r["count"] for r in rows), [100] * 5)
        self.assertEqual(self.store.quests_done_since(self.cid, 0, [GIFT]), 1)
        self.assertFalse(any(command == "q_sys" for command, _params in self.fixture.frames))
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid), (0, 123))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_TICKET), 500)

    def test_missing_one_afro_preserves_the_quest_money_and_reward(self):
        self.fixture.fund(afro=14999, gold=50000)
        self.assertFalse(self.s.fee_ready(self.q))
        self.assertEqual(self.fixture.take(GIFT), [0])
        qid = self.fixture.taken_id(GIFT)
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NO_MONEY])
        self.assertEqual(self.store.money(self.cid), (14999, 50000))
        self.assertNotIn(eden.GOOD_TICKET, self.s.inv.bag_pieces())
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, GIFT))
        self.fixture.fund(afro=15000, gold=50000)
        self.assertEqual(self.fixture.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid), (0, 50000))

    def test_duplicate_active_copy_cannot_pay_or_grant_after_first_completion(self):
        self.fixture.fund(afro=30000)
        first = self.fixture.active(GIFT)
        duplicate = self.fixture.active(GIFT)
        self.assertEqual(self.fixture.hand_in(first), [0])
        self.assertEqual(self.fixture.hand_in(duplicate), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.store.money(self.cid), (15000, 0))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_TICKET), 500)
        self.assertEqual(self.store.quests_done_since(self.cid, 0, [GIFT]), 1)

    def test_new_assignment_does_not_reset_lifetime_gift_history(self):
        self.fixture.fund(afro=30000)
        self.buy()
        self.assertFalse(self.s.quest_available(self.q))
        self.fixture.new_sentence()
        self.assertEqual(self.s.eden_sentence["visit"], 2)
        self.assertFalse(self.s.quest_available(self.q))
        self.assertEqual(self.fixture.take(GIFT), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.store.money(self.cid), (15000, 0))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_TICKET), 500)

    def test_unclaimed_first_visit_offer_is_unavailable_on_later_visits_but_basket_is_not(self):
        self.fixture.fund(afro=15000)
        self.assertTrue(self.s.quest_available(self.q))
        for visit in range(2, 11):
            self.fixture.new_sentence()
            self.assertEqual(self.s.eden_sentence['visit'], visit)
            self.assertFalse(self.store.quest_done(self.cid, GIFT))
            self.assertFalse(self.s.quest_available(self.q))
            self.assertFalse(self.s.fee_ready(self.q))
            self.assertEqual(self.fixture.take(GIFT), [server.RES_NOT_AVAILABLE])
        self.fixture.fund(afro=0, gold=0)
        self.fixture.give(eden.PALM_LEAF, 20)
        self.assertEqual(self.fixture.take(BASKET_QUEST), [0])
        self.assertEqual(self.fixture.hand_in(self.fixture.taken_id(BASKET_QUEST)), [0])
        self.assertEqual(sum(r['type_id'] == eden.BASKET
                             for r in self.store.items_of(self.cid)), 1)
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertFalse(self.store.quest_done(self.cid, GIFT))

    def test_stale_first_visit_cache_and_old_active_gift_cannot_charge_on_second_visit(self):
        self.fixture.fund(afro=15000, gold=123)
        self.fixture.give(eden.PALM_LEAF, 7)
        self.assertEqual(self.fixture.take(GIFT), [0])
        qid = self.fixture.taken_id(GIFT)
        old_sentence = self.s.eden_sentence
        self.fixture.new_sentence()
        self.assertEqual(eden.assigned(self.store, self.cid)['visit'], 2)
        self.s.eden_sentence = old_sentence
        self.assertTrue(self.s.quest_available(self.q))  # Intentionally stale display.
        before_items, before_money = self.store.items_of(self.cid), self.store.money(self.cid)
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NOT_AVAILABLE])
        self.assertEqual(self.store.items_of(self.cid), before_items)
        self.assertEqual(self.store.money(self.cid), before_money)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, GIFT))
        self.assertNotIn(eden.GOOD_TICKET, self.s.inv.bag_pieces())

    def test_valid_ben_id_outside_eden_cannot_take_or_hand_in_the_gift(self):
        self.fixture.fund(afro=15000)
        self.fixture.contact(1789)
        self.s.loc = world.location(41)
        self.assertFalse(self.s.quest_available(self.q))
        self.fixture.frames.clear()
        self.s.cmd_q_st(dict(mob=self.fixture.npc, q_idx=quests.given_by(1789).index(GIFT)))
        self.assertEqual(self.fixture.acknowledgements(), [server.RES_NOT_AVAILABLE])
        qid = self.fixture.active(GIFT)
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid), (15000, 0))
        self.assertNotIn(eden.GOOD_TICKET, self.s.inv.bag_pieces())

    def test_basket_is_crafted_from_twenty_leaves_without_money_or_gift(self):
        basket = quests.get(BASKET_QUEST)
        self.fixture.fund(afro=0, gold=0)
        self.assertFalse(self.store.quest_done(self.cid, GIFT))
        self.assertTrue(self.s.quest_available(basket))
        self.fixture.give(eden.PALM_LEAF, 19)
        self.assertEqual(self.fixture.take(BASKET_QUEST), [0])
        qid = self.fixture.taken_id(BASKET_QUEST)
        self.assertEqual(self.fixture.hand_in(qid), [server.RES_NOT_READY])
        self.assertEqual(self.s.inv.bag_pieces().get(eden.PALM_LEAF), 19)
        self.assertFalse(any(row['type_id'] == eden.BASKET
                             for row in self.store.items_of(self.cid)))
        self.fixture.give(eden.PALM_LEAF)
        self.assertEqual(self.fixture.hand_in(qid), [0])
        self.assertNotIn(eden.PALM_LEAF, self.s.inv.bag_pieces())
        rows = [r for r in self.store.items_of(self.cid) if r['type_id'] == eden.BASKET]
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertFalse(self.store.quest_done(self.cid, GIFT))
        self.assertNotIn(eden.GOOD_TICKET, self.s.inv.bag_pieces())
        self.assertTrue(self.s.quest_available(self.q))
        self.s.combat = combat.Fighter(self.s)
        self.s.inv.refresh_gear()
        strength = self.s.character().attr(progression.STRENGTH)
        capacity = self.s.inv.carry_limit()
        self.fixture.frames.clear()
        self.s.inv.ss_move(dict(obj=str(inventory.oid_of(rows[0])),
                                **{'from': inventory.BAG, 'to': inventory.BELT}))
        self.assertEqual(self.fixture.acknowledgements(), [0])
        self.s.inv.refresh_gear()
        self.assertEqual(self.s.character().attr(progression.STRENGTH), strength + 20)
        self.assertEqual(self.s.inv.carry_limit(), capacity + 40000)

    def test_failure_partway_through_ticket_stacks_rolls_back_then_pays_once(self):
        self.fixture.fund(afro=15000)
        self.assertEqual(self.fixture.take(GIFT), [0])
        qid = self.fixture.taken_id(GIFT)
        original_create = self.store.create_item
        created = []

        def fail_third_stack(char_id, type_id, root, **fields):
            if type_id == eden.GOOD_TICKET:
                created.append(type_id)
                if len(created) == 3:
                    raise RuntimeError("injected failure creating the third ticket stack")
            return original_create(char_id, type_id, root, **fields)

        with patch.object(self.store, "create_item", side_effect=fail_third_stack):
            self.assertEqual(self.fixture.hand_in(qid), [1])
        self.assertEqual(len(created), 3)
        self.assertEqual(self.store.money(self.cid), (15000, 0))
        self.assertNotIn(eden.GOOD_TICKET, self.s.inv.bag_pieces())
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid, GIFT))
        self.assertEqual(self.fixture.hand_in(qid), [0])
        self.assertEqual(self.store.money(self.cid), (0, 0))
        self.assertEqual(self.s.inv.bag_pieces().get(eden.GOOD_TICKET), 500)


if __name__ == "__main__":
    try:
        run_cases(EdenGiftTests)
    finally:
        server.STORE.close()
