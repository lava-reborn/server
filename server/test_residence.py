"""Real SQLite quest/status/fee transactions and rental rules; no live player DB."""
import os
import logging
import time
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop("LAVA_DB_URL",None)
os.environ["LAVA_DB"] = ":memory:"
logging.disable(logging.CRITICAL)
import accounts
import progression
import residence
import quests
import server
import transport
import world
from test_quest_state import session
from testkit import run_cases


class Residence(unittest.TestCase):
    def setUp(self):
        self.store = accounts.Store(":memory:")
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr,server,"STORE",previous)
        self.addCleanup(self.store.close)
        account,_ = self.store.register("resident","test-only")
        self.cid,_ = self.store.create_character(account,"Resident",0,"1")
        self.s = session(self.store,char_id=self.cid)
        self.ch = self.s.char = progression.Character.load(self.store,self.cid)
        self.ch.afro,self.ch.gold = 1000000,10000
        self.ch.save(self.store)
        self.s.active = self.store.character(self.cid)
        self.s.closed,self.s.transport,self.s.residence_timer = False,None,None
        self.s.close = lambda force=False:setattr(self.s,"closed",True)
        self.s.account = None
        self.s.pos = 0
        self.s.loc = NS(id=36,width=20,height=20,spawns=[])
        self.s.room = NS(npc=lambda n: {100:(0,44,world.COMMONER),200:(0,653,world.LESSOR)}.get(n))
        self.s.fee_shown,self.s.skill_shown = {},{}
        self.frames = []
        self.s.send = lambda cmd,**p:self.frames.append((cmd,p))
        self.s.answer = self.s.say = lambda msg:self.frames.append(("notice",dict(text=msg)))

    def status(self,level,remaining=86400*3):
        self.ch.premium = level
        self.ch.premium_until = time.time()+remaining if level else None
        self.ch.save(self.store)

    def ready(self,t):
        return self.store.take_quest(self.cid,t,{},True)

    def finish(self,qid,**params):
        self.frames.clear()
        self.s.cmd_q_co(dict(q_id=qid,mob=100,obj_idx=0,**params))
        return [p["res"] for cmd,p in self.frames if cmd=="cmdAck"]

    def rent(self,vehicle,days=1):
        self.frames.clear()
        self.s.rent_transport(dict(mob=200,p1=vehicle,p2=days))
        return [p["res"] for cmd,p in self.frames if cmd=="cmdAck"]

    def test_status_text_has_no_experience_statement(self):
        for level in (1,2):
            self.status(level)
            text=residence.frame(self.ch)['residence_text'].lower()
            self.assertNotIn('опыт',text)
            self.assertIn(str(residence.WEIGHT[level]//1000),text)
        self.assertEqual(self.ch.premium_level(),2)

    def test_registration_cost_weight_expiry_and_duplicate_hand_in(self):
        now = time.time()
        qid = self.ready(2129)
        self.assertEqual(self.finish(qid),[0])
        saved = self.store.character(self.cid)
        self.assertEqual((self.ch.gold,saved["gold"],saved["premium"],self.ch.max_weight()),(9000,9000,1,65000))
        self.assertTrue(now+residence.SECONDS-1 <= saved["premium_until"] <= time.time()+residence.SECONDS)
        self.assertNotEqual(self.finish(qid),[0])
        self.assertEqual(self.ch.gold,9000)
        self.assertFalse(self.s.quest_available(quests.get(2129)))
        self.assertTrue(self.s.quest_available(quests.get(2130)))
        self.assertEqual([p["max_weight"] for cmd,p in self.frames if cmd=="rp_info"],[])

    def test_vnj_replaces_p_only_after_confirmation_of_current_deadline(self):
        self.assertEqual(self.finish(self.ready(2129)),[0])
        old_until = self.ch.premium_until
        qid = self.ready(2130)
        for params in ({},{"residence_from":old_until-1},{"residence_from":"invalid"}):
            self.assertNotEqual(self.finish(qid,**params),[0])
            self.assertEqual((self.ch.gold,self.ch.premium_until),(9000,old_until))
        self.assertEqual(self.finish(qid,residence_from=old_until),[0])
        self.assertEqual((self.ch.gold,self.ch.premium,self.ch.max_weight()),(6000,2,90000))
        for t in (2129,2130):
            self.assertFalse(self.s.quest_available(quests.get(t)))
            self.assertNotEqual(self.finish(self.ready(t)),[0])
        self.assertEqual(self.ch.gold,6000)

    def test_direct_vnj_no_p_and_no_xp_bonus(self):
        self.assertEqual(self.finish(self.ready(2130)),[0])
        self.assertEqual((self.ch.gold,self.ch.premium),(7000,2))
        for level in (0,1,2):
            ch = progression.Character()
            ch.premium = level
            ch.gain_xp(progression.MELEE,100)
            self.assertEqual(ch.skill[0],[1,0,200])

    def test_no_money_or_distant_npc_cannot_grant_status(self):
        self.ch.gold = 999
        self.ch.save(self.store)
        qid = self.ready(2129)
        self.assertNotEqual(self.finish(qid),[0])
        self.assertEqual((self.ch.gold,self.ch.premium),(999,0))
        self.ch.gold = 10000
        self.ch.save(self.store)
        self.s.pos = 399
        self.assertNotEqual(self.finish(qid),[0])
        self.assertEqual((self.ch.gold,self.ch.premium),(10000,0))

    def test_failure_after_status_write_rolls_back_status_money_history_and_instance(self):
        qid = self.ready(2129)
        with patch.object(self.ch,"save",side_effect=RuntimeError("fault after status CAS")):
            self.assertNotEqual(self.finish(qid),[0])
        saved = self.store.character(self.cid)
        self.assertEqual((saved["premium"],saved["premium_until"],saved["gold"]),(0,None,10000))
        self.assertEqual((self.ch.premium,self.ch.gold),(0,10000))
        self.assertIsNotNone(self.store.quest(qid))
        self.assertFalse(self.store.quest_done(self.cid,2129))
        self.assertFalse(any(cmd=="rp_info" for cmd,p in self.frames))

    def test_external_status_change_is_not_overwritten(self):
        qid = self.ready(2129)
        self.store.save_character_state(self.cid,premium=2,premium_until=int(time.time())+1000)
        self.assertNotEqual(self.finish(qid),[0])
        self.assertEqual(self.store.character(self.cid)["premium"],2)
        self.assertEqual(self.store.character(self.cid)["gold"],10000)

    def test_expiry_without_relogin_refreshes_weight_and_allows_both_quests(self):
        self.status(2,-1)
        self.s.expire_residence()
        self.assertEqual((self.ch.premium,self.ch.max_weight()),(0,40000))
        self.assertEqual(self.store.character(self.cid)["premium"],0)
        self.assertTrue(all(self.s.quest_available(quests.get(t)) for t in (2129,2130)))
        self.assertTrue(any(cmd=="rp_info" and p["max_weight"]==40000 for cmd,p in self.frames))
        self.assertEqual(self.finish(self.ready(2129)),[0])

    def test_live_deadline_timer_expires_once_and_closed_session_cancels(self):
        async def flow():
            self.status(1,.02)
            self.s.schedule_residence()
            self.assertIsNotNone(self.s.residence_timer)
            await asyncio.sleep(.07)
            self.assertEqual(self.ch.premium,0)
            self.assertIsNone(self.s.residence_timer)
            self.status(1,100)
            self.s.schedule_residence()
            timer = self.s.residence_timer
            self.s.closed = True
            self.s.schedule_residence()
            self.assertTrue(timer.cancelled())
        asyncio.run(flow())

    def test_expiry_database_failure_retries_with_backoff_and_recovers(self):
        async def flow():
            self.status(1,-1)
            loop = asyncio.get_running_loop()
            with patch.object(server.storage,"atomic",side_effect=OSError("temporary DB outage")):
                for failures,delay in enumerate((5,10,20,40,60,60),1):
                    self.s.expire_residence()
                    timer=self.s.residence_timer
                    self.assertIsNotNone(timer)
                    self.assertAlmostEqual(timer.when()-loop.time(),delay,delta=.1)
                    self.assertEqual(self.s.residence_retries,failures)
                    timer.cancel()  # emulate firing it; never leave test timers behind
            self.s.expire_residence()
            self.assertIsNone(self.s.residence_timer)
            self.assertEqual(self.s.residence_retries,0)
            self.assertEqual((self.ch.premium,self.store.character(self.cid)["premium"]),(0,0))
            self.assertTrue(any(cmd=="rp_info" and p["max_weight"]==40000 for cmd,p in self.frames))
        asyncio.run(flow())

    def test_expiry_successful_write_then_publish_failure_retries_snapshot(self):
        async def flow():
            self.status(1,-1)
            with patch.object(self.s,"push_money",side_effect=OSError("temporary snapshot failure")):
                for delay in (5,10,20):
                    self.s.expire_residence()
                    self.assertAlmostEqual(self.s.residence_timer.when()-asyncio.get_running_loop().time(),delay,delta=.1)
                    self.s.residence_timer.cancel()
            self.assertEqual(self.ch.premium,0)
            self.assertEqual(self.store.character(self.cid)["premium"],0)
            self.assertIsNotNone(self.s.residence_timer)
            self.s.residence_timer.cancel()
            self.s.expire_residence()
            self.assertIsNone(self.s.residence_timer)
            self.assertEqual(self.s.residence_retries,0)
            self.assertTrue(any(cmd=="rp_info" and p["max_weight"]==40000 for cmd,p in self.frames))
        asyncio.run(flow())

    def test_expiry_lost_commit_reply_retry_preserves_external_newer_status(self):
        async def flow():
            self.status(1,-1)
            raw=self.store.db.raw
            def commit():
                raw.commit()
                raise ConnectionError("lost expiry commit reply")
            proxy=NS(commit=commit,rollback=raw.rollback)
            with patch.object(type(self.store.db),"raw",property(lambda _db:proxy)):
                self.s.expire_residence()
            self.assertEqual(self.store.character(self.cid)["premium"],0)
            self.assertIsNotNone(self.s.residence_timer)
            self.s.residence_timer.cancel()
            deadline=int(time.time())+1000
            self.store.save_character_state(self.cid,premium=2,premium_until=deadline)
            self.s.expire_residence()
            self.assertEqual((self.ch.premium,self.ch.premium_until),(2,deadline))
            self.assertIsNotNone(self.s.residence_timer)
            self.s.residence_timer.cancel()
            self.assertFalse(any(cmd=="notice" for cmd,p in self.frames))
        asyncio.run(flow())

    def test_expiry_retry_replaces_timer_and_refreshes_new_status_after_publish_failure(self):
        async def flow():
            self.status(1,-1)
            deadline=int(time.time())+1000
            self.store.save_character_state(self.cid,premium=2,premium_until=deadline)
            loop=asyncio.get_running_loop();created=[];original=loop.call_later
            def later(*args):
                timer=original(*args);created.append(timer);return timer
            with patch.object(loop,"call_later",side_effect=later),patch.object(self.s,"push_stats",side_effect=OSError("snapshot failure")):
                self.s.expire_residence()
            self.assertEqual(sum(not timer.cancelled() for timer in created),1)
            self.assertTrue(created[0].cancelled())
            self.s.residence_timer.cancel()
            self.s.expire_residence()
            self.assertEqual((self.ch.premium,self.ch.premium_until),(2,deadline))
            self.assertTrue(any(cmd=="rp_info" and p["max_weight"]==90000 for cmd,p in self.frames))
            self.assertEqual(self.s.residence_retries,0)
            self.s.residence_timer.cancel()
            self.s.closed=True
            self.s.expire_residence()
            self.assertIsNone(self.s.residence_timer)
        asyncio.run(flow())

    def test_expiry_callback_preserves_newer_external_status(self):
        self.status(1,-1)
        self.store.save_character_state(self.cid,premium=2,premium_until=time.time()+1000)
        self.s.expire_residence()
        self.assertEqual((self.ch.premium,self.store.character(self.cid)["premium"]),(2,2))

    def test_transport_status_gates_prices_and_minimum_one_day_exception(self):
        for status,vehicle,accepted in ((0,17,False),(0,18,False),(1,17,True),(1,18,False),(2,17,True),(2,18,True)):
            self.s.transport = None
            self.store.save_character_state(self.cid,transport_type=None,transport_until=None)
            self.status(status,3600)  # less than 24 h: a full day remains rentable
            before = self.ch.gold
            afro = self.ch.afro
            result = self.rent(vehicle)
            self.assertEqual(result==[0],accepted,(status,vehicle,result))
            self.assertEqual(self.ch.gold,before)
            self.assertEqual(self.ch.afro,afro-({17:35000,18:45000}[vehicle] if accepted else 0))
            if accepted:
                self.assertEqual(self.s.transport[0],vehicle)
                self.assertGreater(self.s.transport[1],self.ch.premium_until)
                self.assertNotEqual(self.rent(vehicle,2),[0])
        self.assertEqual(self.ch.gold,10000)
        self.assertEqual(self.ch.afro,885000)
        self.s.transport = None
        self.store.save_character_state(self.cid,transport_type=None,transport_until=None)
        self.status(2,86400*2+100)
        self.assertNotEqual(self.rent(18,4),[0])
        self.assertEqual(self.rent(18,3),[0])
        self.status(2,-1)
        self.assertNotEqual(self.rent(18),[0])

    def test_rental_requires_gold_even_with_enough_afro(self):
        self.status(0)
        for vehicle,price in ((4,70),(5,90)):
            self.ch.gold = price-1
            self.ch.save(self.store)
            self.assertNotEqual(self.rent(vehicle),[0])
            self.assertEqual(self.ch.gold,price-1)
            self.assertEqual(self.ch.afro,1000000)
            self.assertIsNone(self.s.transport)
            self.ch.gold,self.ch.afro = price,0
            self.ch.save(self.store)
            self.assertEqual(self.rent(vehicle),[0])
            self.assertEqual((self.ch.gold,self.ch.afro),(0,0))
            self.s.transport = None
            self.store.save_character_state(self.cid,transport_type=None,transport_until=None)
            self.ch.afro = 1000000

    def test_same_vehicle_extends_remaining_hour_and_other_replaces(self):
        now = int(time.time())
        self.s.transport = (7,now+3600)
        self.store.save_character_state(self.cid,transport_type=7,transport_until=now+3600)
        with patch.object(transport.time,"time",return_value=now):
            self.assertEqual(self.rent(7,1),[0])
            self.assertEqual(self.s.transport,(7,now+3600+86400))
            self.assertEqual(self.rent(3,1),[0])
            self.assertEqual(self.s.transport,(3,now+86400))

    def test_repeated_extension_cannot_bypass_status_total_deadline(self):
        now = int(time.time())
        self.status(1)
        self.ch.premium_until = now+3600
        self.ch.save(self.store)
        with patch.object(transport.time,"time",return_value=now):
            self.assertEqual(self.rent(17,1),[0])
            paid = self.ch.afro
            until = self.s.transport[1]
            self.assertNotEqual(self.rent(17,1),[0])
            self.assertEqual((self.ch.afro,self.s.transport[1]),(paid,until))
            self.assertLessEqual(until-self.ch.premium_until,86400)

    def commit_fault(self, committed, vehicle=5):
        self.status(2)
        raw = self.store.db.raw
        before = self.ch.gold
        afro = self.ch.afro
        def commit():
            if committed: raw.commit()
            raise ConnectionError("commit reply failed")
        proxy = NS(commit=commit,rollback=raw.rollback)
        def close(force):
            self.assertTrue(force)
            if self.s.char is not None:self.s.char.save(self.store)
        with patch.object(type(self.store.db),"raw",property(lambda _db:proxy)), patch.object(self.s,"close",side_effect=close) as closed:
            self.rent(vehicle)
        closed.assert_called_once_with(force=True)
        saved = self.store.character(self.cid)
        self.assertEqual(saved["gold"],before-(transport.price(vehicle,1)[1] if committed else 0))
        self.assertEqual(saved["afro"],afro-(transport.price(vehicle,1)[0] if committed else 0))
        self.assertEqual(saved["transport_type"],vehicle if committed else None)
        self.assertEqual(self.s.char.gold,saved["gold"])

    def test_afro_rental_failed_commit_reloads_rolled_back_state(self):
        self.commit_fault(False, 17)

    def test_afro_rental_lost_commit_reply_cannot_restore_old_purse(self):
        self.commit_fault(True, 18)

    def test_afro_rental_cannot_spend_gold_instead(self):
        self.status(2)
        for vehicle, cost in ((17, 35000), (18, 45000)):
            self.ch.afro = cost - 1
            self.ch.save(self.store)
            gold = self.ch.gold
            self.assertNotEqual(self.rent(vehicle), [0])
            self.assertEqual((self.ch.afro, self.ch.gold), (cost - 1, gold))
            self.assertIsNone(self.s.transport)
            self.ch.afro = cost
            self.ch.save(self.store)
            self.assertEqual(self.rent(vehicle), [0])
            self.assertEqual((self.ch.afro, self.ch.gold), (0, gold))
            self.s.transport = None
            self.store.save_character_state(self.cid, transport_type=None, transport_until=None)

    def test_gold_rental_cannot_overwrite_a_newer_external_status(self):
        self.status(0)
        until = int(time.time()) + 86400
        self.store.save_character_state(self.cid, premium=2, premium_until=until)
        before = self.store.money(self.cid)
        self.rent(4)
        row = self.store.character(self.cid)
        self.assertEqual((row["premium"], row["premium_until"]), (2, until))
        self.assertEqual(self.store.money(self.cid), before)
        self.assertIsNone(row["transport_type"])
        self.assertEqual((self.s.char.premium, self.s.char.premium_until), (2, until))
        self.assertTrue(self.s.closed)

    def test_gold_rental_without_status_and_cross_currency_extension(self):
        now = int(time.time())
        self.status(0)
        with patch.object(transport.time, "time", return_value=now):
            self.assertEqual(self.rent(4, 1), [0])
            self.assertEqual(self.s.transport, (4, now + 86400))
            self.status(1, 3 * 86400)
            self.assertEqual(self.rent(17, 1), [0])
            self.assertEqual(self.s.transport, (17, now + 2 * 86400))
            self.assertEqual(self.rent(4, 2), [0])
            self.assertEqual(self.s.transport, (4, now + 4 * 86400))
            before = self.ch.afro, self.ch.gold, self.s.transport
            self.assertNotEqual(self.rent(17, 1), [0])
            self.assertEqual((self.ch.afro, self.ch.gold, self.s.transport), before)
            self.assertEqual(self.ch.gold, 10000 - 3 * 70)
            self.assertEqual(self.ch.afro, 1000000 - 35000)

    def test_rental_failed_commit_reloads_rolled_back_state(self):
        self.commit_fault(False)

    def test_rental_lost_commit_reply_cannot_restore_old_purse(self):
        self.commit_fault(True)

    def test_rental_payment_and_vehicle_roll_back_together(self):
        self.status(2)
        before = self.ch.gold
        with patch.object(self.store,"save_character_state",side_effect=RuntimeError("rental write failed")):
            self.assertNotEqual(self.rent(5),[0])
        self.assertEqual((self.ch.gold,self.store.character(self.cid)["gold"]),(before,before))
        self.assertIsNone(self.s.transport)
        self.assertIsNone(self.store.character(self.cid)["transport_type"])


if __name__ == "__main__":
    try:
        run_cases(Residence)
    finally:
        server.STORE.close()
