"""Approved lottery pools, weighted boundaries and real atomic hand-ins.

These are finite deterministic checks, not a statistical win-rate claim.
All writes use isolated SQLite; no live account or user-supplied code runs.
"""
import math
import os
import random
import unittest
from collections import Counter
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ['LAVA_DB'] = ':memory:'
os.environ.pop('LAVA_DB_URL', None)
import accounts
import inventory
import items
import progression
import quests
import rooms
import server
import world
from test_quest_state import session
from testkit import run_cases


# Independent, explicit acceptance table from the supplied workbook, with
# the approved 15/20 G jackpots resolving contradictory text labels.
EXPECTED = {
    308: [(6116,120),(6117,120),(6118,120),(6120,60),(6119,60),
          (6122,50),(6123,50),(6055,5),(6061,5),(6056,5),(6062,5),
          (6057,5),(6063,5),(6911,1),(1307,1)],
    309: [(6073,1),(6904,1),(6074,1),(6905,1),(6906,1),(7100,1),
          (6152,50),(6156,50),(6155,50),(6158,50),(6159,50),(1333,1),(1134,1)],
    518: [(6116,200),(6117,200),(6118,200),(6120,100),(6119,100),
          (6122,75),(6123,75),(6125,75),(6056,5),(6062,5),(6057,5),
          (6063,5),(6058,5),(6064,5),(6911,1),(2646,1)],
    519: [(6116,300),(6117,300),(6118,300),(6120,150),(6119,150),
          (6122,120),(6123,120),(6125,120),(6056,10),(6062,10),(6057,10),
          (6063,10),(6058,10),(6064,10),(6911,1),(2647,1)],
    520: [(6905,1),(7101,1),(6906,1),(7102,1),(6907,1),(7103,1),
          (6152,210),(6156,210),(6155,210),(6158,210),(6159,210),(2649,1),(4796,1)],
    521: [(6905,1),(7101,1),(6906,1),(7102,1),(6907,1),(7103,1),
          (6152,260),(6156,260),(6155,260),(6158,260),(6159,260),(2650,1),(4796,1)],
    721: [(6116,500),(6117,500),(6118,500),(6119,250),(6124,250),
          (6122,200),(6123,200),(6125,200),(6121,200),(6126,200),
          (6057,15),(6063,15),(6058,10),(6064,10),(6059,5),(6065,5),(6911,1),(2648,1)],
    722: [(6906,1),(7102,1),(6907,1),(7103,1),(6908,1),(7104,1),
          (6155,310),(6158,310),(6159,310),(6157,310),(6162,310),(2651,1),(4797,1)],
    916: [(6119,300),(6124,300),(6122,250),(6123,250),(6121,250),(6126,250),
          (6058,15),(6064,15),(6059,10),(6065,10),(6060,5),(6066,5),(6911,1),(2652,1)],
    917: [(6119,350),(6124,350),(6122,300),(6123,300),(6121,300),(6126,300),
          (6059,15),(6065,15),(6060,10),(6066,10),(6902,1),(6053,1),(6911,1),(2653,1)],
    918: [(6119,400),(6124,400),(6122,350),(6123,350),(6121,350),(6126,350),
          (6059,20),(6065,20),(6060,10),(6066,10),(6903,1),(6054,1),(6911,1),(3574,1)],
    919: [(6907,1),(7103,1),(6908,1),(7104,1),(6909,1),(7105,1),
          (6155,310),(6158,310),(6159,310),(6157,310),(6162,310),(2654,1),(4797,1)],
    920: [(6907,1),(7103,1),(6908,1),(7104,1),(6909,1),(7105,1),
          (6155,360),(6158,360),(6159,360),(6157,360),(6162,360),(2655,1),(4796,3)],
    921: [(6907,1),(7103,1),(6908,1),(7104,1),(6909,1),(7105,1),
          (6155,460),(6158,460),(6159,460),(6157,460),(6162,460),(3575,1),(4797,2)],
}
RULES = {  # ticket, price (hundredths for G), G-only, min/max level, location
    308:(1307,500,False,0,20,35), 309:(1333,50,True,0,20,102),
    518:(2646,1000,False,9,20,187), 519:(2647,1700,False,11,20,187),
    520:(2649,200,True,9,20,187), 521:(2650,250,True,11,20,187),
    721:(2648,2400,False,12,20,197), 722:(2651,300,True,12,20,103),
    916:(2652,3000,False,16,20,446), 917:(2653,3700,False,17,20,446),
    918:(3574,4730,False,17,20,446), 919:(2654,300,True,16,20,446),
    920:(2655,350,True,17,20,446), 921:(3575,450,True,17,20,446),
}


class PointRandom(random.Random):
    def __init__(self, point):
        super().__init__(0)
        self.point = point

    def random(self):
        return self.point


class LotteryRelease(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        self.enterContext(patch.object(server, 'STORE', self.store))
        aid, _ = self.store.register('lotterytest', 'temporary-local-secret')
        self.cid, _ = self.store.create_character(aid, 'lotterytest', 0, '1')
        self.s = session(self.store, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        self.s.active = self.store.character(self.cid)
        self.s.transport, self.s.closed, self.s.room = None, False, None
        self.s.gx, self.s.gy = 0, 0
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames = []
        self.s.send = lambda cmd, **p:self.frames.append((cmd,p))

    def prepare(self, qtype, tickets=1, player_level=None):
        self.q = quests.get(qtype)
        ticket, _price, _gold, level, _max, loc = RULES[qtype]
        if player_level is not None:
            level = player_level
        for skill in self.s.char.skill:
            skill[0] = level
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.s.loc = world.location(loc)
        self.s.npc_type = lambda _id:self.q.give[0]
        if tickets:
            fields = inventory.new_fields(ticket, tickets)
            root = fields.pop('root')
            fields['slot'] = inventory.BAG
            self.store.create_item(self.cid, ticket, root, **fields)
        self.frames.clear()
        self.s.cmd_q_st(dict(mob=1, q_idx=quests.given_by(self.q.give[0]).index(qtype)))
        self.assertEqual(self.acks(), [0])
        return next(row['q_id'] for row in self.store.quests(self.cid) if row['type']==qtype)

    def acks(self):
        return [p['res'] for c,p in self.frames if c=='cmdAck']

    def complete(self, qid, point=0, obj_idx=0):
        self.frames.clear()
        with patch.object(quests, 'RNG', PointRandom(point)):
            self.s.cmd_q_co(dict(mob=1, q_id=qid, obj_idx=obj_idx))

    def choose(self, obj):
        index = next(i for i,(t,_n,_w) in enumerate(self.q.rew_random) if t==obj)
        return (index + .5) / len(self.q.rew_random)

    def test_exact_approved_pools_and_uniform_unique_weights(self):
        for qtype, expected in EXPECTED.items():
            with self.subTest(quest=qtype):
                q = quests.get(qtype)
                self.assertEqual(Counter(q.rew_random),Counter((t,n,1) for t,n in expected))
                self.assertEqual(len({t for t,_n,_w in q.rew_random}),len(expected))
                self.assertTrue(q.repeatable and q.service)
                self.assertFalse(q.rew_gold or q.rew_afro or q.rew_also or q.rew_obj)

    def test_every_lottery_giver_is_present_in_its_actual_location(self):
        for qtype, (_ticket,_price,_gold,_lo,_hi,loc) in RULES.items():
            with self.subTest(quest=qtype, location=loc):
                room = rooms.Room(world.location(loc), rooms.IdAllocator(), world.mob_types())
                giver = quests.get(qtype).give[0]
                self.assertIn(giver, [npc.type_id for npc in room.npcs.values()])
                self.assertIn(qtype, quests.given_by(giver))

    def test_ticket_currency_price_levels_and_no_afro_to_gold_prize(self):
        for qtype,(ticket,price,gold,lo,hi,_loc) in RULES.items():
            with self.subTest(quest=qtype):
                q = quests.get(qtype)
                si = items.params_of(ticket)
                self.assertEqual(q.wants(),[(ticket,1)])
                self.assertEqual((q.level,q.max_level),(lo,hi))
                self.assertIn(f"{lo}\u201320", q.texts[1])
                self.assertIn(f"{lo} \u0443\u0440.", q.texts[0])
                self.assertEqual(inventory.buy_price(si,items.root_of(ticket),1,gold),price)
                self.assertEqual(bool(si.get('g_cost')),gold)
                if gold:
                    self.assertEqual(si.get('cost',0),0)
                else:
                    self.assertTrue(all(not items.params_of(t).get('g_cost') and t not in items.GOLD_INGOTS
                                        for t,_n,_w in q.rew_random))

    def test_availability_preserves_minimum_and_extends_to_level_twenty(self):
        for qtype,(_ticket,_price,_gold,lo,hi,_loc) in RULES.items():
            q = quests.get(qtype)
            for level in {0, 8, 9, 16, 17, 18, 19, lo, hi, hi+1} | ({lo-1} if lo else set()):
                with self.subTest(quest=qtype,level=level):
                    for skill in self.s.char.skill:
                        skill[0] = level
                    self.assertEqual(self.s.quest_available(q),lo<=level<=hi)

    def test_gold_tickets_cannot_be_bought_with_forged_afro_purchase_code(self):
        for qtype,(ticket,_price,gold,_lo,_hi,loc) in RULES.items():
            if not gold:
                continue
            with self.subTest(quest=qtype):
                npc = quests.get(qtype).give[0]
                stock = items.stock_for(npc,loc)
                self.assertIn(ticket,stock)
                self.s.inv.trade = inventory.TradeSession(1,npc,loc)
                self.frames.clear()
                before = self.store.character(self.cid)
                self.s.inv.buy(dict(obj=format(stock.index(ticket),'x'),param=1),inventory.UPD_BUY)
                self.assertEqual(self.acks(),[inventory.RES_REFUSED])
                self.assertEqual(self.store.items_of(self.cid),[])
                self.assertEqual(self.store.character(self.cid),before)

    def test_all_weighted_intervals_and_endpoints(self):
        for qtype in EXPECTED:
            q = quests.get(qtype)
            n = len(q.rew_random)
            for i,(obj,count,_w) in enumerate(q.rew_random):
                self.assertEqual(q.draw(PointRandom((i+.5)/n)),(obj,count))
            self.assertEqual(q.draw(PointRandom(0)),q.rew_random[0][:2])
            self.assertEqual(q.draw(PointRandom(math.nextafter(1,0))),q.rew_random[-1][:2])

    def test_expected_retail_budget_below_ticket_not_each_individual_prize(self):
        for qtype,(_ticket,price,gold,_lo,_hi,_loc) in RULES.items():
            q = quests.get(qtype)
            values = []
            for obj,n,w in q.rew_random:
                # The workbook values the encrypted blueprint at 2.5 G.
                # This is a budget assumption, not its NPC selling price.
                value = 250*n if obj==1134 else inventory.buy_price(items.params_of(obj),items.root_of(obj),n,gold)
                values.append(value*w)
            self.assertLess(sum(values),price*sum(w for _t,_n,w in q.rew_random),qtype)

    def test_real_hand_in_of_all_pools_and_replay(self):
        for qtype in EXPECTED:
            with self.subTest(quest=qtype):
                # Reuse the account, clearing only its isolated test inventory.
                for row in self.store.items_of(self.cid):
                    self.store.delete_item(row['uniq'])
                qid = self.prepare(qtype)
                expected = self.q.draw(random.Random(qtype))
                self.frames.clear()
                with patch.object(quests,'RNG',random.Random(qtype)):
                    self.s.cmd_q_co(dict(mob=1,q_id=qid,obj_idx=0))
                self.assertEqual(self.acks(),[0])
                self.assertEqual(self.s.inv.bag_pieces(),{expected[0]:expected[1]})
                snapshot = self.store.items_of(self.cid)
                self.complete(qid)
                self.assertEqual(self.acks(),[server.RES_NO_SUCH])
                self.assertEqual(self.store.items_of(self.cid),snapshot)

    def test_halfa_lottery_is_offered_and_completed_at_level_sixteen(self):
        for qtype in (308, 309):
            with self.subTest(quest=qtype):
                for row in self.store.items_of(self.cid):
                    self.store.delete_item(row['uniq'])
                qid = self.prepare(qtype, player_level=16)
                self.s.cmd_q_status(dict(q_type=qtype))
                status = [p for c,p in self.frames if c=='q_status'][-1]
                self.assertEqual(status['status'], 1)
                self.assertIn(qtype, quests.given_by(self.q.give[0]))
                self.assertEqual(self.s.loc.id, RULES[qtype][-1])
                expected = self.q.draw(PointRandom(0))
                self.complete(qid)
                self.assertEqual(self.acks(), [0])
                self.assertEqual(self.s.inv.bag_pieces(), {expected[0]:expected[1]})

    def test_abu_upper_tier_lotteries_accept_level_seventeen_and_eighteen(self):
        for qtype in (918, 921):
            for level in (17, 18):
                with self.subTest(quest=qtype, level=level):
                    for row in self.store.items_of(self.cid):
                        self.store.delete_item(row['uniq'])
                    qid = self.prepare(qtype, player_level=level)
                    self.assertIn('от 17 ур.', self.q.texts[0])
                    self.assertIn('17\u201320', self.q.texts[1])
                    self.s.cmd_q_status(dict(q_type=qtype))
                    status = [p for c,p in self.frames if c=='q_status'][-1]
                    self.assertEqual(status['status'], 1)
                    expected = self.q.draw(PointRandom(0))
                    self.complete(qid)
                    self.assertEqual(self.acks(), [0])
                    self.assertEqual(self.s.inv.bag_pieces(), {expected[0]:expected[1]})

    def test_all_pools_can_be_completed_at_level_twenty(self):
        for qtype in RULES:
            with self.subTest(quest=qtype):
                for row in self.store.items_of(self.cid):
                    self.store.delete_item(row['uniq'])
                qid = self.prepare(qtype, player_level=20)
                expected = self.q.draw(PointRandom(0))
                self.complete(qid)
                self.assertEqual(self.acks(), [0])
                self.assertEqual(self.s.inv.bag_pieces(), {expected[0]:expected[1]})

    def test_without_ticket_cannot_roll(self):
        qid = self.prepare(520,tickets=0)
        with patch.object(quests.Quest,'draw',side_effect=AssertionError('must not draw')):
            self.complete(qid)
        self.assertEqual(self.acks(),[server.RES_NOT_READY])
        self.assertEqual(self.s.inv.bag_pieces(),{})
        self.assertIsNotNone(self.store.quest(qid))

    def test_ticket_prize_funds_exactly_one_next_game(self):
        qid = self.prepare(520)
        self.complete(qid,self.choose(2649))
        self.assertEqual(self.s.inv.bag_pieces(),{2649:1})
        qid = self.prepare(520,tickets=0)
        self.complete(qid,self.choose(6152))
        self.assertEqual(self.s.inv.bag_pieces(),{6152:210})
        qid = self.prepare(520,tickets=0)
        self.complete(qid)
        self.assertEqual(self.acks(),[server.RES_NOT_READY])

    def test_jackpot_and_blueprint_counts_are_not_client_selected(self):
        qid = self.prepare(920)
        self.complete(qid,self.choose(4796),obj_idx=999999)
        self.assertEqual(self.s.inv.bag_pieces(),{4796:3})
        for row in self.store.items_of(self.cid):
            self.store.delete_item(row['uniq'])
        qid = self.prepare(309)
        self.complete(qid,self.choose(1134))
        self.assertEqual(self.s.inv.bag_pieces(),{1134:1})

    def test_failure_after_actual_jackpot_creation_rolls_back_ticket_and_reward(self):
        qid = self.prepare(920)
        before = self.store.items_of(self.cid)
        original = self.s.inv.give_pieces
        def fail(obj,num):
            original(obj,num)
            raise RuntimeError('failure after creating real ingots')
        with patch.object(self.s.inv,'give_pieces',fail):
            self.complete(qid,self.choose(4796))
        self.assertEqual(self.acks(),[1])
        self.assertEqual(self.store.items_of(self.cid),before)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(any(c.startswith('ss_') for c,_p in self.frames))

    def test_lost_reply_after_jackpot_commit_does_not_pay_again(self):
        qid = self.prepare(920)
        original_send = self.s.send
        self.s.send = lambda *_a,**_k:(_ for _ in ()).throw(BrokenPipeError('lost client reply'))
        with self.assertRaises(BrokenPipeError):
            self.complete(qid,self.choose(4796))
        self.s.send = original_send
        self.assertEqual(self.s.inv.bag_pieces(),{4796:3})
        self.complete(qid,self.choose(4796))
        self.assertEqual(self.acks(),[server.RES_NO_SUCH])
        self.assertEqual(self.s.inv.bag_pieces(),{4796:3})

    def test_uncertain_commit_reloads_and_keeps_actual_jackpot_once(self):
        qid = self.prepare(920)
        raw = self.store.db.raw
        def commit():
            raw.commit()
            raise ConnectionError('lost database reply after actual commit')
        proxy = NS(commit=commit,rollback=raw.rollback)
        with patch.object(type(self.store.db),'raw',property(lambda _db:proxy)), \
                patch.object(self.s,'close') as closed:
            self.complete(qid,self.choose(4796))
        closed.assert_called_once_with(force=True)
        self.assertEqual(self.s.inv.bag_pieces(),{4796:3})
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.acks(),[])
        self.complete(qid,self.choose(4796))
        self.assertEqual(self.acks(),[server.RES_NO_SUCH])
        self.assertEqual(self.s.inv.bag_pieces(),{4796:3})


if __name__=='__main__':
    run_cases(LotteryRelease)
