"""Mortimer valuables and sand services on an isolated in-memory SQLite store."""
import os
import logging
logging.disable(logging.CRITICAL)
os.environ.pop('LAVA_DB_URL',None)
os.environ['LAVA_DB']=':memory:'
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import accounts
import inventory
import items
import mortimer
import progression
import quests
import server
import world
from test_quest_state import session


class MortimerSales(unittest.TestCase):
    def setUp(self):
        self.store=accounts.Store(':memory:')
        self.addCleanup(self.store.close)
        previous=server.STORE;server.STORE=self.store
        self.addCleanup(setattr,server,'STORE',previous)
        aid,_=self.store.register('gold-test','test-only')
        self.cid,_=self.store.create_character(aid,'GoldTester',0,'1')
        self.s=session(self.store,char_id=self.cid)
        self.s.char=progression.Character.load(self.store,self.cid)
        self.s.char.afro,self.s.char.gold=12345,100
        self.s.char.save(self.store)
        self.s.closed,self.s.transport,self.s.residence_timer=False,None,None
        self.s.close=lambda force=False:setattr(self.s,'closed',True)
        self.s.loc=NS(id=36,width=20,height=20,spawns=[])
        self.s.room=NS(npc=lambda n:(0,1188,world.TRADER))
        self.s.pos=0;self.s.active=self.store.character(self.cid)
        self.s.fee_shown,self.s.skill_shown={},{}
        self.frames=[]
        self.s.send=lambda cmd,**p:self.frames.append((cmd,p))
        self.s.send_player_info=lambda:self.frames.append(('money',dict(gold=self.s.char.gold)))
        self.s.say=self.s.answer=lambda text:None
        self.inv=self.s.inv
        self.inv.trade=inventory.TradeSession(1,1188,36)

    def give(self,t,n=1):
        rows=self.inv.give_pieces(t,n);self.frames.clear();return rows[0]

    def sell(self,row,n):
        self.frames.clear();self.inv.sell(dict(obj=inventory.oid_of(row),param=n))
        return next(p['res'] for cmd,p in self.frames if cmd=='cmdAck')

    def test_prices_are_base_price_rounded_down_per_piece(self):
        self.assertEqual({t:mortimer.unit_gold(t) for t in mortimer.VALUABLES},
                         {6950:3,6951:4,6952:4,6953:4,6959:6})
        self.assertEqual(mortimer.unit_gold(2258),0)
        self.assertEqual(mortimer.unit_gold(7620),0)

    def test_partial_and_full_sale_pay_gold_only_and_update_live_purse(self):
        row=self.give(6951,50)
        self.assertEqual(self.sell(row,7),0)
        self.assertEqual(self.store.item(row['uniq'])['count'],43)
        self.assertEqual((self.s.char.afro,self.s.char.gold),(12345,128))
        self.assertEqual(self.sell(row,43),0)
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual((self.s.char.afro,self.s.char.gold),(12345,300))
        self.assertNotEqual(self.sell(row,43),0)
        self.assertEqual(self.store.character(self.cid)['gold'],300)

    def test_non_valuables_ingots_sand_and_quest_items_are_refused(self):
        for t in (25566,6946,2258,7620,333,3941):
            row=self.give(t)
            before=self.inv.rows()
            with self.subTest(t=t):
                self.assertNotEqual(self.sell(row,1),0)
                self.assertEqual(self.inv.rows(),before)
                self.assertEqual((self.s.char.afro,self.s.char.gold),(12345,100))

    def test_invalid_quantities_do_not_consume_a_stack(self):
        row=self.give(6951,5)
        for n in (-1,6,'bad'):
            self.assertNotEqual(self.sell(row,n),0)
            self.assertEqual(self.store.item(row['uniq'])['count'],5)
        self.assertEqual(self.s.char.gold,100)

    def test_bank_items_and_stale_npc_session_are_refused(self):
        row=self.give(6951,5)
        self.store.update_item(row['uniq'],slot=inventory.BANK)
        self.assertNotEqual(self.sell(row,5),0)
        self.store.update_item(row['uniq'],slot=inventory.BAG)
        self.s.room.npc=lambda n:None
        self.assertNotEqual(self.sell(row,5),0)
        self.assertEqual(self.store.item(row['uniq'])['count'],5)

    def test_money_write_failure_rolls_back_items_and_purse(self):
        row=self.give(6951,10)
        for n in (3,10):
            with patch.object(self.store,'set_money',side_effect=RuntimeError('injected write failure')):
                self.assertNotEqual(self.sell(row,n),0)
            self.assertEqual(self.store.item(row['uniq'])['count'],10)
            self.assertEqual(self.s.char.gold,100)
            self.assertEqual(self.store.character(self.cid)['gold'],100)

    def test_authoritative_purse_is_read_after_lock_and_ledger_records_gold(self):
        row=self.give(6951,2);self.s.char.gold=999999
        self.assertEqual(self.sell(row,2),0)
        self.assertEqual(self.s.char.gold,108)
        ledger=self.store.db.execute("SELECT gold FROM money_ledger WHERE char_id=? AND source='shop_sell'",(self.cid,)).fetchall()
        self.assertEqual(sum(r['gold'] for r in ledger),8)

    def test_other_traders_still_pay_afro(self):
        row=self.give(6946,2)
        self.inv.trade=inventory.TradeSession(1,123,36)
        self.assertEqual(self.sell(row,2),0)
        self.assertGreater(self.s.char.afro,12345)
        self.assertEqual(self.s.char.gold,100)

    def test_gold_valuables_are_refused_by_other_merchants_without_loss(self):
        self.inv.trade=inventory.TradeSession(1,123,36)
        for type_id in mortimer.VALUABLES:
            row=self.give(type_id,2)
            self.assertNotEqual(self.sell(row,2),0)
            self.assertEqual(self.store.item(row['uniq'])['count'],2)
        self.assertEqual((self.s.char.afro,self.s.char.gold),(12345,100))

    def test_every_mortimer_type_uses_the_same_restriction(self):
        for npc in mortimer.NPC_TYPES:
            self.inv.trade=inventory.TradeSession(1,npc,36)
            self.s.room.npc=lambda n,npc=npc:(0,npc,world.TRADER)
            self.assertEqual(self.sell(self.give(6950),1),0)
            self.assertNotEqual(self.sell(self.give(6946),1),0)
        self.assertEqual(self.s.char.gold,100+3*len(mortimer.NPC_TYPES))

    def test_each_sand_quest_consumes_exact_batch_and_rewards_once(self):
        for qid,n,gold in ((8800,5,1),(8801,50,20),(8802,100,50),(8803,175,100)):
            for row in self.inv.rows():self.store.delete_item(row['uniq'])
            self.give(2258,n+1)
            q=quests.get(qid)
            self.assertTrue(q.service)
            self.assertTrue(q.repeatable)
            self.assertEqual(set(q.give),set(mortimer.NPC_TYPES))
            before=self.s.char.gold
            active=self.store.take_quest(self.cid,qid,q.bag_progress(self.inv.bag_pieces()),True)
            self.s.cmd_q_co(dict(q_id=active,mob=1,obj_idx=0))
            self.assertEqual(self.inv.bag_pieces(),{2258:1})
            self.assertEqual(self.s.char.gold,before+gold)
            self.s.cmd_q_co(dict(q_id=active,mob=1,obj_idx=0))
            self.assertEqual(self.s.char.gold,before+gold)
        self.assertEqual(self.s.char.afro,12345)


if __name__ == "__main__":
    from testkit import run_cases
    run_cases(MortimerSales)
