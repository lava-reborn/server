"""Prison income follows real hand-ins and sales, never unlimited coupon rates."""
from datetime import datetime
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS

import bosses
import events
import inventory
import quests
import server
import world
from test_gold_commerce import GoldCommerce
from testkit import run_cases


class PrisonFarmEconomy(unittest.TestCase):
    quote = GoldCommerce.quote
    confirmed = GoldCommerce.confirmed

    def setUp(self):
        GoldCommerce.setUp(self)
        self.medic_time = datetime(2026, 11, 23, 13, 25,
                                  tzinfo=bosses.ZONE).timestamp()
        self.clock = patch.object(bosses, 'clock', return_value=self.medic_time)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.place(646, 879)

    def place(self, loc, npc):
        self.s.loc = world.location(loc)
        self.s.room = NS(loc=self.s.loc, npc=lambda _eid: (0, npc, world.TRADER))
        self.s.npc_type = lambda _eid: npc
        self.s.gx, self.s.gy = world.cell_of(loc) or world.unpack(quests.get(167).loc)

    def acks(self):
        return [p['res'] for cmd, p in self.frames if cmd == 'cmdAck']

    def take(self, kind, npc):
        self.s.npc_type = lambda _eid: npc
        self.frames.clear()
        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(npc).index(kind)))
        self.assertEqual(self.acks(), [0])
        return next(r['q_id'] for r in self.store.quests(self.cid) if r['type'] == kind)

    def finish(self, qid, reward=0):
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=reward))
        self.assertEqual(self.acks(), [0])

    def test_seventy_five_bands_pay_one_talon_once_per_day_across_towns(self):
        self.inv.give_pieces(2476, 150)
        before = self.store.money(self.cid)
        qid = self.take(167, 879)
        self.finish(qid)
        bag = self.inv.bag_pieces()
        self.assertEqual(bag.get(2476), 75)
        self.assertEqual(bag.get(3570), 1)
        self.assertEqual(self.store.money(self.cid), before)
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
        self.assertNotIn(0, self.acks())
        self.assertEqual(self.inv.bag_pieces().get(3570), 1)
        for loc in (622, 651):
            self.place(loc, 879)
            self.frames.clear()
            self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(879).index(167)))
            self.assertNotIn(0, self.acks())
            self.assertEqual(self.inv.bag_pieces().get(3570), 1)
        self.assertEqual(self.s.daily_available(), server.DAILY_MAX - 1)

    def test_cash_rewards_use_one_talon_resale_and_pay_once(self):
        for kind, npc, bands, amount in ((164, 877, 10, 23500),
                                         (165, 877, 25, 58500),
                                         (166, 878, 50, 116500),
                                         (168, 879, 100, 233500)):
            with self.subTest(quest=kind):
                self.place(646, npc)
                self.inv.give_pieces(2476, bands + 1)
                held = self.inv.bag_pieces()[2476]
                before = self.store.money(self.cid)
                qid = self.take(kind, npc)
                self.finish(qid)
                after = (before[0] + amount, before[1])
                self.assertEqual(self.store.money(self.cid), after)
                self.assertEqual(self.inv.bag_pieces()[2476], held - bands)
                self.assertEqual(amount % 500, 0)
                self.assertLessEqual(abs(amount - 175000 * bands / 75), 250)
                self.frames.clear()
                self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
                self.assertNotIn(0, self.acks())
                self.assertEqual(self.store.money(self.cid), after)
                self.assertEqual(self.inv.bag_pieces()[2476], held - bands)
                if kind != 164:
                    for loc in (622, 651):
                        self.place(loc, npc)
                        self.frames.clear()
                        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(npc).index(kind)))
                        self.assertNotIn(0, self.acks())
                        self.assertEqual(self.store.money(self.cid), after)

    def test_reward_descriptions_survive_original_text_overlay(self):
        self.assertIn('1 талон', quests.get(167).texts[1])
        self.assertNotIn('2 талона', quests.get(167).texts[1])
        self.assertIn('233 500 афро', quests.get(168).texts[1])
        self.assertNotIn('15000', quests.get(168).texts[1])

    def test_every_talon_reward_is_five_hundred_rounds_and_sells_once(self):
        q = quests.get(169)
        for index, ammo_type in enumerate(q.rew_obj):
            with self.subTest(ammo=ammo_type):
                self.inv.give_pieces(3570, 1)
                self.place(36, 893)
                self.s.gx, self.s.gy = world.unpack(q.loc)
                self.finish(self.take(169, 893), index)
                ammo = next(r for r in self.inv.rows() if r['type_id'] == ammo_type)
                self.assertEqual(ammo['count'], 500)
                self.place(36, 123)
                self.inv.trade = inventory.TradeSession(1, 123, 36)
                request, quote = self.quote(ammo, 500)
                self.assertEqual(quote['price'], 175000)
                before = self.store.money(self.cid)
                self.assertEqual(self.confirmed(request, quote), 0)
                self.assertEqual(self.store.money(self.cid), (before[0] + 175000, before[1]))
                self.assertNotEqual(self.confirmed(request, quote), 0)
        self.assertEqual(self.s.daily_available(), server.DAILY_MAX)
        self.assertNotIn(3570, self.inv.bag_pieces())
        self.assertFalse(any(r['type_id'] in q.rew_obj for r in self.inv.rows()))

    def test_medic_window_and_daily_limit_prevent_continuous_reward_income(self):
        q = quests.get(167)
        self.assertEqual((q.per_day, q.service), (1, False))
        # These rows are gated by the NPC's presence, not a quest clock.
        for town in ('wh', 'dn', 'ah'):
            window = events.table().window('prison_' + town + '_medics')
            self.assertFalse(window.is_open(self.medic_time - 1))
            self.assertTrue(window.is_open(self.medic_time))
            self.assertFalse(window.is_open(self.medic_time + 300))
        self.assertEqual(quests.get(169).service, True)
        for _ in range(server.DAILY_MAX):
            self.inv.give_pieces(2476, 10)
            self.place(646, 877)
            self.finish(self.take(164, 877))
        self.assertEqual(self.s.daily_available(), 0)
        self.inv.give_pieces(2476, 75)
        self.place(646, 879)
        qid = self.take(167, 879)
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=0))
        self.assertNotIn(0, self.acks())
        self.assertNotIn(3570, self.inv.bag_pieces())


if __name__ == '__main__':
    run_cases(PrisonFarmEconomy)
