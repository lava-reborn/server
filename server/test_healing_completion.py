"""Healing completion guards; isolated characters, no database connections."""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace as NS
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
import combat, inventory, items, progression

class HealingCompletion(unittest.IsolatedAsyncioTestCase):
    def fixture(self, type_id=6043):
        row = dict(uniq=1, char_id=1, root=items.HEAL, type_id=type_id, use_count=1)
        ch = progression.Character()
        ch.hp = 30
        events, consumed = [], []
        room = NS(ws=False, broadcast=events.append)
        sess = NS(char_id=1, room=room, inv=NS(find=lambda _:row,
            push_status=lambda *a:None, wear_worn=lambda *a:None), answer=events.append,
            push_stats=lambda **k:None, push_vitals=lambda:None)
        f = NS(sess=sess, rc=NS(room=room), ap=100, healing=None, dead=False,
            eid=1, damage_revision=0, character=lambda:ch, ack=events.append,
            store=NS(item=lambda _:row, delete_item=consumed.append))
        f.heal_now = lambda *args:combat.Fighter.heal_now(f, *args)
        return f, ch, room, consumed

    def start(self, f):
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertIsNotNone(f.healing)
        timer = f.healing
        args = timer._args
        timer.cancel()
        return args

    async def test_peace_can_finish_after_combat_starts_without_damage(self):
        f,ch,room,used = self.fixture()
        args = self.start(f)
        room.ws = True
        f.heal_now(*args)
        self.assertGreater(ch.hp,30)
        self.assertEqual(used,[1])

    async def test_hp_or_stamina_damage_interrupts_without_consumption(self):
        for damage in ((1,0),(0,1)):
            f,ch,room,used = self.fixture()
            args = self.start(f)
            room.ws = True
            combat.Fighter.apply_damage(f,*damage)
            hp,sp = ch.hp,ch.sp
            f.heal_now(*args)
            self.assertEqual((ch.hp,ch.sp),(hp,sp))
            self.assertEqual(used,[])

    async def test_dead_patient_preserves_item(self):
        f,ch,room,used = self.fixture(6055)
        args = self.start(f)
        ch.hp = 0
        f.dead = True
        f.heal_now(*args)
        self.assertEqual(ch.hp,0)
        self.assertEqual(used,[])

    async def test_other_patient_dies_or_has_zero_hp(self):
        for dead in (False,True):
            f,ch,room,used = self.fixture(6055)
            patient = progression.Character()
            patient.hp = 0
            target = NS(dead=dead,character=lambda:patient,eid=2)
            f.heal_now(1,target)
            self.assertEqual(patient.hp,0)
            self.assertEqual(used,[])

    async def test_other_patient_damage_interrupts_peace_healing(self):
        f,ch,room,used = self.fixture()
        patient = progression.Character()
        patient.hp = 25
        target = NS(dead=False, damage_revision=1, character=lambda:patient, eid=2)
        f.heal_now(1,target,(0,0))
        self.assertEqual(patient.hp,25)
        self.assertEqual(used,[])

    async def test_combat_medicine_survives_damage(self):
        f,ch,room,used = self.fixture(6055)
        room.ws = True
        args = self.start(f)
        combat.Fighter.apply_damage(f,1,0)
        f.heal_now(*args)
        self.assertGreater(ch.hp,29)
        self.assertEqual(used,[1])

    async def test_dead_target_cannot_start(self):
        f,ch,room,used = self.fixture()
        f.dead = True
        combat.Fighter.use_heal(f,dict(obj='1'),inventory.USE_IDLE)
        self.assertIsNone(f.healing)
        self.assertEqual(used,[])

if __name__ == '__main__':
    unittest.main()
