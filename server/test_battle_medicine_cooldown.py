"""Four-second battle medicine cooldown: virtual time, no sleeps or load."""
import asyncio
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import battle_medicine
import combat
import inventory
import items
import protocol
from test_healing_completion import HealingCompletion
from testkit import run_cases


class BattleMedicineCooldown(unittest.IsolatedAsyncioTestCase):
    def fixture(self, type_id=7100):
        return HealingCompletion().fixture(type_id)

    def use(self, f):
        return HealingCompletion().start(f)

    async def test_success_starts_only_after_dose_commits_and_expires_at_four_seconds(self):
        f,ch,room,used=self.fixture()
        room.ws=True
        with patch.object(combat,'now',return_value=100):
            args=self.use(f)
            self.assertEqual(battle_medicine.remaining_ms(f.store,1,100),0)
            f.heal_now(*args)
        self.assertEqual(used,[1])
        self.assertEqual(battle_medicine.remaining_ms(f.store,1,100),4000)
        self.assertEqual(battle_medicine.remaining_ms(f.store,1,103.999),1)
        self.assertEqual(battle_medicine.remaining_ms(f.store,1,104),0)
        self.assertEqual(f.frames[-1],('medCooldown',dict(time_ms=4000,description=battle_medicine.DESCRIPTION)))

    async def test_shared_by_all_battle_items_and_rejection_keeps_aim_ap_and_dose(self):
        f,ch,room,used=self.fixture()
        room.ws=True
        with patch.object(combat,'now',return_value=100):
            f.heal_now(*self.use(f))
        row=f.store.item(1)
        for type_id in (t for t in items.catalogue() if items.battle_medicine(t)):
            row['type_id']=type_id
            f.ap=100
            aim=object()
            f.aim=aim
            revision=f.action_revision
            ordered=[]
            f.ack=lambda res:ordered.append(('ack',res))
            f.sess.send=lambda name,**p:ordered.append((name,p))
            with patch.object(combat,'now',return_value=101):
                combat.Fighter.use_heal(f,dict(obj='1'),inventory.USE_IDLE)
            self.assertEqual(ordered[0],('ack',inventory.RES_NOT_READY))
            self.assertEqual(ordered[1][0],'medCooldown')
            self.assertEqual((f.ap,used),(100,[1]))
            self.assertIs(f.aim,aim)
            self.assertEqual(f.action_revision,revision)
            f.aim=None

    async def test_no_cooldown_for_peace_use_or_cancelled_or_failed_heal(self):
        for mode in ('peace','cancelled','dead','no_ap'):
            f,ch,room,used=self.fixture()
            room.ws=mode!='peace'
            with patch.object(combat,'now',return_value=100):
                args=self.use(f)
                if mode=='cancelled':
                    combat.Fighter.cancel_pending(f)
                else:
                    if mode=='dead':
                        f.dead=True
                    if mode=='no_ap':
                        f.ap=0
                    f.heal_now(*args)
            self.assertEqual(battle_medicine.remaining_ms(f.store,1,100),0,mode)
            self.assertEqual(used,[1] if mode=='peace' else [],mode)

    async def test_reconnect_room_change_and_reflash_snapshot_keep_deadline(self):
        f,ch,room,used=self.fixture()
        with patch.object(combat,'now',return_value=100):
            battle_medicine.start(f.store,1,100)
        replacement,_,_,_=self.fixture()
        replacement.store=f.store
        replacement.rc=None
        with patch.object(combat,'now',return_value=101):
            combat.Fighter.resend_room(replacement,resumed=True)
            self.assertEqual(combat.Fighter.medicine_cooldown_blocked(replacement,7101),3000)
        self.assertEqual(replacement.frames[-1][1]['time_ms'],3000)
        self.assertEqual(battle_medicine.remaining_ms(f.store,2,101),0)
        self.assertEqual(combat.Fighter.medicine_cooldown_blocked(replacement,6043),False)

    async def test_expiry_callback_cannot_remove_a_newer_deadline(self):
        store=NS()
        callbacks=[]
        loop=NS(call_later=lambda delay,fn:callbacks.append((delay,fn)))
        with patch.object(battle_medicine.asyncio,'get_running_loop',return_value=loop):
            battle_medicine.start(store,1,100)
            battle_medicine.start(store,1,104)
        self.assertEqual([delay for delay,_ in callbacks],[4,4])
        callbacks[0][1]()
        self.assertEqual(battle_medicine.remaining_ms(store,1,104),4000)
        callbacks[1][1]()
        self.assertEqual(store._battle_medicine_deadlines,{})

    async def test_new_frame_keeps_russian_hint_and_millisecond_precision(self):
        source=protocol.encode('medCooldown',time_ms=2100,description=battle_medicine.DESCRIPTION)
        command=protocol.decode(source)
        self.assertEqual(command[0],'medCooldown')
        self.assertEqual(command[1]['time_ms'],2100)
        self.assertEqual(command[1]['description'],battle_medicine.DESCRIPTION)


if __name__=='__main__':
    run_cases(BattleMedicineCooldown)
