"""Execute actual AVM1: residence icons, consent, expiry and total rental cap."""
import sys
import math
import unittest
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/"server")]
import widescreen as w
from avm_test import execute
from testkit import run_cases


class ResidenceClient(unittest.TestCase):
    def env(self,attrs=None):
        gamer = dict(attributes=attrs if attrs is not None else {},premium=0,playerInfo={})
        core = dict(Master=dict(getInstance=lambda:dict(gamer=gamer)))
        return dict(lol=dict(core=core),gamer=gamer,getTimer=lambda:1000,Math=dict(ceil=math.ceil))

    def test_free_home_service_is_distinguished_from_paid_status_quests(self):
        for service in (0,1,2):
            attendance=dict(__residenceHomeOrig=lambda n:None,_name="original")
            execute(w.fn_residence_home_label().assemble(),dict(this=attendance,id=service))
            self.assertEqual(attendance["_name"],"Место возрождения" if service==0 else "original")

    def test_fixed_weight_labels_and_existing_silver_gold_icon_frames(self):
        for level,bonus in ((0,0),(1,25000),(2,50000)):
            attrs=dict(max_weight=54000+bonus,__residenceStatus=level,__residenceBonus=bonus,
                       __residenceText="deadline notice")
            env=self.env(attrs)
            frames,hints=[],[]
            env["lol"]["gpui"]=dict(HintManager=dict(showHint=hints.append))
            pan=dict(maxWeight_txt={},bonusWeight_txt={},premium_mc=dict(gotoAndStop=frames.append),__weightLimitOrig=lambda:None)
            env["this"]=pan
            execute(w.fn_weight_limit().assemble(),env)
            self.assertEqual(pan["maxWeight"],54000+bonus)
            self.assertEqual(pan["maxWeight_txt"]["text"],"54.0 кг")
            self.assertEqual(pan["bonusWeight_txt"]["text"],"+%s кг"%(bonus/1000) if level else "")
            self.assertEqual(frames,[level+1])
            pan["premium_mc"]["onRollOver"].invoke(pan["premium_mc"],[])
            self.assertEqual(hints,["deadline notice"])

    def test_status_snapshot_updates_before_original_and_refreshes_quests_only_on_change(self):
        attrs={};env=self.env(attrs);calls=[]
        env["lol"]["core"]["quests"]=dict(QuestInspector=dict(getInstance=lambda:dict(requestAllNPC=lambda:calls.append("quests"))))
        attrs["__residenceInfoOrig"]=lambda obj:calls.append(("original",attrs["__residenceStatus"]))
        env["this"]=attrs
        for status in (0,1,1,0):
            env["obj"]=dict(param=dict(residence_level=status,residence_until=2000000000,
                 residence_bonus=status*25000,residence_text="status",residence_days=2,residence_now=1999900000))
            execute(w.fn_residence_snapshot().assemble(),env)
        self.assertEqual(calls,[("original",0),("original",1),"quests",("original",1),("original",0),"quests"])
        self.assertEqual(attrs["__residenceAt"],1000)
        self.assertEqual(env["gamer"]["premium"],0)

    def dialog(self):
        env=self.env(dict(__residenceStatus=1,__residenceUntil=1999999999,__residenceText="P until tomorrow"))
        task=dict(typeID=2130,qID=17)
        inspector=dict(quester=dict(id=100),currentQuests={17:task})
        env.update(this=inspector,questTask=task,objIdx=0)
        sent,queries,listeners=[],[],[]
        panel={}
        dialog=dict(addEventListener=lambda *args:listeners.append(args),removeEventListener=lambda *args:None)
        def open_window(name):
            queries.append(name);panel["instance"]=dict(content=dialog)
            return panel["instance"]
        def close_window(name):panel["instance"]=None
        env["lol"]["core"]["SceneShifter"]=dict(openNewWindow=open_window,closeWindow=close_window,_ref=dict(UIPanels=dict(query=panel)))
        env["lol"]["core"]["quests"]=dict(QuestInspector=dict(sInstance=inspector))
        connection=dict(__residenceSendOrig=lambda mess:sent.append(mess["propList"].copy()) or True)
        def original(task,index):
            mess=dict(name="q_co",propList=dict(q_id=task["qID"],mob=inspector["quester"]["id"]))
            mess["addProp"]=lambda key,value:mess["propList"].update({key:value})
            execute(w.fn_residence_send().assemble(),dict(env,this=connection,mess=mess))
        inspector["__residenceTakeOrig"]=original
        return env,task,inspector,sent,queries,listeners,dialog

    def test_upgrade_cancel_sends_nothing_and_repeated_click_opens_only_one_dialog(self):
        env,task,inspector,sent,queries,listeners,dialog=self.dialog()
        execute(w.fn_residence_take().assemble(),env)
        execute(w.fn_residence_take().assemble(),env)
        self.assertEqual(queries,["query"])
        self.assertFalse(sent)
        listeners[0][2].invoke(inspector,[dict(target=dialog,success=False)])
        self.assertFalse(sent)
        self.assertIsNone(inspector.get("__residencePending"))

    def test_confirmed_upgrade_sends_exact_deadline_once_and_does_not_leak_consent(self):
        env,task,inspector,sent,queries,listeners,dialog=self.dialog()
        execute(w.fn_residence_take().assemble(),env)
        listeners[0][2].invoke(inspector,[dict(target=dialog,success=True)])
        self.assertEqual(sent,[dict(q_id=17,mob=100,residence_from=1999999999)])
        self.assertIsNone(inspector.get("__residenceConfirmedQ"))
        inspector["__residenceTakeOrig"](task,0)
        self.assertEqual(sent[-1],dict(q_id=17,mob=100))

    def test_changing_npc_or_removing_quest_while_confirmation_is_open_does_not_send(self):
        for changed in ("npc","quest"):
            env,task,inspector,sent,queries,listeners,dialog=self.dialog()
            execute(w.fn_residence_take().assemble(),env)
            if changed=="npc":inspector["quester"]["id"]=200
            else:inspector["currentQuests"].clear()
            listeners[0][2].invoke(inspector,[dict(target=dialog,success=True)])
            self.assertFalse(sent)

    def test_double_click_rental_sends_once_until_ack_and_rejected_filter_unlocks(self):
        sent,queued=[],[]
        allowed=[True]
        rent=dict(lessorID=22,XMC=dict(Send=lambda mess:sent.append(mess) or allowed[0]),getTransportAck=lambda obj:None)
        env=dict(this=rent,typeID=7,day=1,lol=dict(server=dict(
            mess=dict(CSM_TS_on_conv=lambda npc,vehicle,days:dict(npc=npc,vehicle=vehicle,days=days)),
            XMLCCallStack=dict(addCall=lambda *args:queued.append(args)))))
        execute(w.fn_residence_rent_request().assemble(),env)
        execute(w.fn_residence_rent_request().assemble(),env)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0],dict(npc=22,vehicle=7,days=1))
        self.assertEqual(len(queued),1)
        rent["__residenceRentAckOrig"]=lambda obj:None
        execute(w.fn_residence_rent_ack().assemble(),dict(env,obj={}))
        allowed[0]=False
        execute(w.fn_residence_rent_request().assemble(),env)
        self.assertFalse(rent["__rentalPending"])
        self.assertEqual(len(queued),1)
        allowed[0]=True
        execute(w.fn_residence_rent_request().assemble(),env)
        self.assertEqual(len(queued),2)

    def test_rental_slider_uses_total_existing_rental_and_elapsed_time(self):
        now=1900000000
        attrs=dict(__residenceUntil=now+2*86400+3*3600,__residenceNow=now,__residenceAt=1000,
                   __rentalType=4,__rentalUntil=now+86400+5*3600)
        env=self.env(attrs)
        pan=dict(newSlot=dict(item_mc=dict(item=dict(typeID=4))),rightNum=10,__residencePrintOrig=lambda:None)
        env["this"]=pan
        execute(w.fn_residence_rent_print().assemble(),env)
        self.assertEqual((pan["maxValue"],pan["rightNum"]),(1,1))
        attrs["__rentalUntil"]=now+4*86400
        execute(w.fn_residence_rent_print().assemble(),env)
        self.assertEqual((pan["maxValue"],pan["rightNum"]),(1,0))
        attrs["__rentalType"]=7  # different transport: replacement starts now
        pan["rightNum"]=10
        execute(w.fn_residence_rent_print().assemble(),env)
        self.assertEqual((pan["maxValue"],pan["rightNum"]),(3,3))
        env["getTimer"]=lambda:1000+4*3600*1000
        execute(w.fn_residence_rent_print().assemble(),env)
        self.assertEqual((pan["maxValue"],pan["rightNum"]),(2,2))
        pan["newSlot"]["item_mc"]["item"]["typeID"]=7
        execute(w.fn_residence_rent_print().assemble(),env)
        self.assertEqual(pan["maxValue"],365)

    def test_rental_gate_uses_correct_status_names_and_same_transport_extends_directly(self):
        for need,status,accepted in ((1,0,False),(2,1,False),(1,1,True),(2,2,True)):
            env=self.env();env["gamer"]["premium"]=status
            item=dict(typeID=4 if need==1 else 5,getProp=lambda key:need)
            env["gamer"]["playerInfo"]=dict(transport=dict(typeID=item["typeID"]))
            calls=[]
            pan=dict(gamer=env["gamer"],newSlot=dict(item_mc=dict(item=item)),rightNum=1,
                     printTxt=lambda:None,newAlert=lambda text:calls.append(text),
                     _getTransport=lambda item:calls.append("extend"),__residenceRentOrig=lambda:calls.append("original"))
            execute(w.fn_residence_rent_get().assemble(),dict(env,this=pan))
            self.assertEqual(calls==["extend"],accepted)
            if not accepted:self.assertIn("прописка" if need==1 else "ВНЖ",calls[0])


if __name__ == "__main__":
    run_cases(ResidenceClient)
