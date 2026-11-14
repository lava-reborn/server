"""Exercise reported quest chains against real tables and transactional handlers."""
import os
import random
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

os.environ['LAVA_DB'] = ':memory:'
os.environ.pop('LAVA_DB_URL', None)
import accounts
import inventory
import mobs
import progression
import quests
import rooms
import server
import travel
import world
from test_quest_state import session
from testkit import run_cases


class ReleaseQuests(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        self.enterContext(patch.object(server, 'STORE', self.store))
        self.addCleanup(self.store.close)
        aid, _ = self.store.register('releasequest', 'local-secret')
        self.cid, _ = self.store.create_character(aid, 'releasequest', 0, '1')
        self.s = session(self.store, level=20, char_id=self.cid)
        self.s.char = progression.Character.load(self.store, self.cid)
        for skill in self.s.char.skill:
            skill[0] = 20
        self.s.char.afro = 100000
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.transport, self.s.closed, self.s.room = None, False, None
        self.s.gx, self.s.gy = 0, 0
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.frames, self.moves = [], []
        self.s.send = lambda cmd, **p:self.frames.append((cmd,p))
        self.s.over_weight = lambda *_args:False
        self.s.hand_in_way = lambda *args:self.moves.append(args)

    def at(self, loc, npc):
        self.s.loc = world.location(loc)
        self.s.npc_type = lambda _eid:npc

    def give(self, type_id, count=1, slot=inventory.BAG):
        fields = inventory.new_fields(type_id, count)
        root = fields.pop('root')
        fields['slot'] = slot
        return self.store.create_item(self.cid, type_id, root, **fields)

    def done(self, type_id):
        self.store.db.execute('INSERT INTO char_quests_done (char_id,type,done_at) VALUES (?,?,?)',
                              (self.cid,type_id,1))
        self.store.db.commit()
        self.s._quest_status_snapshot = None

    def take(self, type_id, npc):
        self.frames.clear()
        self.s.cmd_q_st(dict(mob=1,q_idx=quests.given_by(npc).index(type_id)))
        self.assertEqual([p['res'] for c,p in self.frames if c=='cmdAck'],[0])
        return next(r['q_id'] for r in self.store.quests(self.cid) if r['type']==type_id)

    def hand_in(self, qid):
        self.frames.clear()
        self.s.cmd_q_co(dict(mob=1,q_id=qid,obj_idx=0))
        return [p['res'] for c,p in self.frames if c=='cmdAck']

    def test_shovel_requires_note_in_bag_and_rewards_once(self):
        self.at(107,2011)
        self.give(5512,slot=inventory.BANK)
        qid=self.take(258,2011)
        self.assertEqual(self.hand_in(qid),[server.RES_NOT_READY])
        self.assertNotIn(3191,self.s.inv.bag_pieces())
        self.give(5512)
        self.assertEqual(self.hand_in(qid),[0])
        self.assertEqual(self.s.inv.bag_pieces().get(3191),1)
        self.assertNotIn(5512,self.s.inv.bag_pieces())
        self.assertEqual(self.hand_in(qid),[server.RES_NO_SUCH])
        self.assertEqual(self.s.inv.bag_pieces().get(3191),1)

    def test_door_requires_prior_quest_and_lockpick_and_commits_before_way(self):
        self.at(188,1394)
        self.assertFalse(self.s.quest_available(quests.get(452)))
        self.done(451)
        qid=self.take(452,1394)
        self.assertEqual(self.hand_in(qid),[server.RES_NOT_READY])
        self.assertEqual(self.moves,[])
        self.give(3770)
        self.assertEqual(self.hand_in(qid),[0])
        self.assertIsNone(self.store.quest(qid))
        self.assertNotIn(3770,self.s.inv.bag_pieces())
        self.assertEqual(len(self.moves),1)
        self.assertEqual(self.hand_in(qid),[server.RES_NO_SUCH])

    def test_door_chain_obtains_lockpick_from_an_actual_manticore_spawn(self):
        self.at(188,1415)
        self.give(25485)
        first=self.take(450,1415)
        self.assertEqual(self.hand_in(first),[0])
        second=self.take(451,1415)
        self.at(188,1394)
        self.assertEqual(self.hand_in(second),[0])
        third=self.take(452,1394)
        base=rooms.Room(world.location(220), rooms.IdAllocator(), server.MOB_TYPES)
        self.assertTrue(any(npc.type_id==1411 and npc.root==world.MOB for npc in base.npcs.values()))
        rng=random.Random(7)
        for _ in range(20):
            wanted=quests.wanted_things(self.store,self.cid,self.s.inv.bag_pieces())
            for t,n in mobs.loot_for(mobs.stats(1411),rng,wanted,loc_id=220,killer_level=20):
                if t==3770:
                    self.s.inv.give_pieces(t,n)
            if self.s.inv.bag_pieces().get(3770):
                break
        self.assertEqual(self.s.inv.bag_pieces().get(3770),1)
        self.assertNotIn(3770,quests.wanted_things(self.store,self.cid,self.s.inv.bag_pieces()))
        self.assertEqual(self.hand_in(third),[0])
        self.assertEqual(len(self.moves),1)
        self.assertEqual(travel.quest_way(self.s.loc,452)['target_loc_id'],671)
        self.assertEqual(self.hand_in(third),[server.RES_NO_SUCH])
        self.assertEqual(len(self.moves),1)

    def test_sorcerer_note_really_opens_the_wifes_shovel_exchange(self):
        self.at(105,2010)
        qid=self.take(257,2010)
        self.assertEqual(self.hand_in(qid),[server.RES_NOT_READY])
        self.give(46652,15)  # exchange input; acquisition of 15 coins is a separate audit
        self.assertEqual(self.hand_in(qid),[0])
        self.assertEqual(self.s.inv.bag_pieces().get(5512),1)
        self.at(107,2011)
        shovel=self.take(258,2011)
        self.assertEqual(self.hand_in(shovel),[0])
        self.assertEqual(self.s.inv.bag_pieces().get(3191),1)
        self.assertNotIn(5512,self.s.inv.bag_pieces())

    def test_journal_assembly_is_available_after_231_and_consumes_four_parts_once(self):
        self.at(35,106)
        self.done(231)
        self.assertTrue(self.s.quest_available(quests.get(232)))
        qid=self.take(232,106)
        for part in (416,417,418):
            self.give(part)
        self.assertEqual(self.hand_in(qid),[server.RES_NOT_READY])
        self.give(419)
        self.assertEqual(self.hand_in(qid),[0])
        self.assertTrue(all(t not in self.s.inv.bag_pieces() for t in (416,417,418,419)))
        self.assertEqual(self.hand_in(qid),[server.RES_NO_SUCH])
        self.assertFalse(self.s.quest_available(quests.get(232)))

    def test_paid_dongola_abri_ride_preserves_pass_and_charges_once_per_trip(self):
        self.at(49,156)
        self.s.char.afro,self.s.char.gold=200,7
        self.s.char.save(self.store)
        self.give(6547)
        before=self.s.inv.bag_pieces()
        q=quests.get(18100)
        self.assertTrue(q.service)
        self.assertEqual(q.loc,quests.get(282).loc)
        self.assertEqual(q.wants(),[])
        self.assertEqual((q.cost_afro,q.cost_gold,q.pays),(100,0,False))
        self.assertEqual(quests.get(282).wants(),[(6547,1)])
        self.assertEqual(travel.quest_way(self.s.loc,18100)['target_loc_id'],187)
        for remaining in (100,0):
            qid=self.take(18100,156)
            self.assertEqual(self.store.money(self.cid),(remaining+100,7))
            self.assertEqual(self.hand_in(qid),[0])
            self.assertEqual(self.store.money(self.cid),(remaining,7))
            self.assertEqual(self.hand_in(qid),[server.RES_NO_SUCH])
            self.assertEqual(self.store.money(self.cid),(remaining,7))
        self.assertEqual(len(self.moves),2)
        self.assertEqual(self.s.inv.bag_pieces(),before)
        exported=quests.strings()
        self.assertTrue(all(exported.get(key) for key in q.string_ids()))
        self.assertIn('100 афро',exported[q.string_id(quests.START)])

    def test_paid_trip_refuses_insufficient_afro_even_with_a_pass(self):
        self.at(49,156)
        self.s.char.afro,self.s.char.gold=99,100
        self.s.char.save(self.store)
        self.give(6547)
        before=self.s.inv.bag_pieces()
        qid=self.take(18100,156)
        self.assertEqual(self.hand_in(qid),[server.RES_NO_MONEY])
        self.assertEqual(self.store.money(self.cid),(99,100))
        self.assertEqual(self.s.inv.bag_pieces(),before)
        self.assertIsNotNone(self.store.quest(qid))
        self.assertEqual(self.moves,[])

    def test_existing_pass_routes_still_take_only_the_requested_pass(self):
        for loc,npc,qtype,ticket,target in ((49,156,282,6547,187),(187,1179,281,6546,49)):
            with self.subTest(quest=qtype):
                self.at(loc,npc)
                self.s.char.afro,self.s.char.gold=0,0
                self.s.char.save(self.store)
                self.give(ticket)
                qid=self.take(qtype,npc)
                self.assertEqual(self.hand_in(qid),[0])
                self.assertEqual(self.store.money(self.cid),(0,0))
                self.assertNotIn(ticket,self.s.inv.bag_pieces())
                self.assertEqual(travel.quest_way(self.s.loc,qtype)['target_loc_id'],target)

    def test_abri_dongola_cash_route_still_charges_100_without_consuming_pass(self):
        self.at(187,1179)
        self.s.char.afro,self.s.char.gold=100,3
        self.s.char.save(self.store)
        self.give(6546)
        q=quests.get(275)
        self.assertEqual((q.cost_afro,q.cost_gold,q.wants()),(100,0,[]))
        qid=self.take(275,1179)
        self.assertEqual(self.hand_in(qid),[0])
        self.assertEqual(self.store.money(self.cid),(0,3))
        self.assertEqual(self.s.inv.bag_pieces().get(6546),1)
        self.assertEqual(travel.quest_way(self.s.loc,275)['target_loc_id'],49)

    def test_unfulfilled_paid_trip_returns_fare_once(self):
        self.at(49,156)
        self.s.char.afro,self.s.char.gold=100,3
        self.s.char.save(self.store)
        qid=self.take(18100,156)
        self.s.way,self.s.way_quest=None,None
        self.s.on_map=False
        self.s.combat=NS(dead=False)
        self.s.hold_line=lambda _verb:None
        self.s.say=lambda _text:None
        self.s.hand_in_way=server.Session.hand_in_way.__get__(self.s)
        plan=travel.plan_quest_way(self.s.loc,18100,0,0)
        # Precheck succeeds, but the destination becomes unavailable after commit.
        with patch.object(travel,'plan_quest_way',side_effect=[plan,travel.Refused('unavailable')]):
            self.assertEqual(self.hand_in(qid),[0])
        self.assertEqual(self.store.money(self.cid),(100,3))
        self.assertIsNone(self.store.quest(qid))
        self.assertEqual(self.hand_in(qid),[server.RES_NO_SUCH])
        self.assertEqual(self.store.money(self.cid),(100,3))

    def test_paid_ride_cannot_be_taken_at_another_location_or_npc(self):
        self.at(187,156)
        self.s.cmd_q_st(dict(mob=1,q_idx=quests.given_by(156).index(18100)))
        self.assertEqual([p['res'] for c,p in self.frames if c=='cmdAck'],[server.RES_NOT_AVAILABLE])
        self.assertFalse(self.store.quests(self.cid))


if __name__ == '__main__':
    run_cases(ReleaseQuests)
