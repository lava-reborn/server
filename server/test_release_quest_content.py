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


if __name__ == '__main__':
    run_cases(ReleaseQuests)
