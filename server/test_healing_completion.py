"""Healing completion guards; isolated characters, no database connections.

The owner's ordinary/battle medicine rule is recorded in PROTOCOL.md.
Verify delayed application, cancelled doses, death and AP at completion;
client bars require the separate Flash check.
"""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
from testkit import run_cases  # noqa: E402

class HealingCompletion(unittest.IsolatedAsyncioTestCase):

    def fixture(self, type_id=6043):
        row = dict(uniq=1, char_id=1, root=items.HEAL, type_id=type_id, use_count=1)
        ch = progression.Character()
        ch.hp = 30
        events, consumed = ([], [])
        room = NS(ws=False, broadcast=lambda frame, **kw: events.append(frame))
        frames = []
        sess = NS(char_id=1, room=room, inv=NS(find=lambda _: row, push_status=lambda *a: None, wear_worn=lambda *a: None), answer=events.append, push_stats=lambda **k: None, push_vitals=lambda: None, send=lambda name, **p: frames.append((name, p)))
        f = NS(sess=sess, rc=NS(room=room), ap=100, healing=None, dead=False, eid=1, damage_revision=0, character=lambda: ch, ack=events.append, store=NS(item=lambda _: row, delete_item=consumed.append))
        f.heal_now = lambda *args: combat.Fighter.heal_now(f, *args)
        f.c_ap = lambda: None
        f.frames = frames
        return (f, ch, room, consumed)

    def start(self, f):
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertIsNotNone(f.healing)
        timer = f.healing
        args = timer._args[-1]
        timer.cancel()
        return args

    async def test_failed_completion_releases_client_item_without_spending(self):
        for reason in ('ap', 'dead', 'zero_hp', 'missing'):
            with self.subTest(reason=reason):
                f, ch, room, used = self.fixture(6055)
                room.ws = True
                frames = []
                f.sess.send = lambda name, **p: frames.append((name, p))
                args = self.start(f)
                before = ch.hp
                if reason == 'ap':
                    f.ap = 0
                elif reason == 'dead':
                    f.dead = True
                elif reason == 'zero_hp':
                    ch.hp = before = 0
                else:
                    f.store.item = lambda _: None
                frames.clear()
                f.heal_now(*args)
                self.assertIn(('actionCancel', dict(release=1)), frames)
                self.assertEqual((ch.hp, used), (before, []))

    async def test_peace_cannot_finish_after_combat_starts_without_damage(self):
        f, ch, room, used = self.fixture()
        args = self.start(f)
        room.ws = True
        f.heal_now(*args)
        self.assertEqual(ch.hp, 30)
        self.assertEqual(used, [])

    async def test_hp_or_stamina_damage_interrupts_without_consumption(self):
        for damage in ((1, 0), (0, 1)):
            f, ch, room, used = self.fixture()
            args = self.start(f)
            room.ws = True
            combat.Fighter.apply_damage(f, *damage)
            hp, sp = (ch.hp, ch.sp)
            f.heal_now(*args)
            self.assertEqual((ch.hp, ch.sp), (hp, sp))
            self.assertEqual(used, [])

    async def test_dead_patient_preserves_item(self):
        f, ch, room, used = self.fixture(6055)
        args = self.start(f)
        ch.hp = 0
        f.dead = True
        f.heal_now(*args)
        self.assertEqual(ch.hp, 0)
        self.assertEqual(used, [])
        self.assertIn(('actionCancel', dict(release=1)), f.frames)

    async def test_other_patient_dies_or_has_zero_hp(self):
        for dead in (False, True):
            f, ch, room, used = self.fixture(6055)
            patient = progression.Character()
            patient.hp = 0
            target = NS(dead=dead, character=lambda: patient, eid=2)
            f.heal_now(1, target)
            self.assertEqual(patient.hp, 0)
            self.assertEqual(used, [])
            self.assertEqual(f.frames, [('actionCancel', dict(release=1))])

    async def test_other_patient_damage_interrupts_peace_healing(self):
        f, ch, room, used = self.fixture()
        patient = progression.Character()
        patient.hp = 25
        target = NS(dead=False, damage_revision=1, character=lambda: patient, eid=2)
        f.heal_now(1, target, (0, 0))
        self.assertEqual(patient.hp, 25)
        self.assertEqual(used, [])

    async def test_combat_medicine_completes_after_damage(self):
        f, ch, room, used = self.fixture(6055)
        room.ws = True
        args = self.start(f)
        combat.Fighter.apply_damage(f, 1, 0)
        f.heal_now(*args)
        self.assertGreater(ch.hp, 29)
        self.assertEqual(used, [1])

    async def test_dead_target_cannot_start(self):
        f, ch, room, used = self.fixture()
        f.dead = True
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertIsNone(f.healing)
        self.assertEqual(used, [])

    async def test_room_war_without_personal_timer_allows_only_battle_medicine(self):
        for type_id in (6043, 6055):
            f, ch, room, used = self.fixture(type_id)
            room.ws = True
            with patch.object(combat, 'now', return_value=100):
                if type_id == 6043:
                    combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
                    self.assertIsNone(f.healing)
                    self.assertEqual((ch.hp, used), (30, []))
                else:
                    args = self.start(f)
                    f.heal_now(*args)
                    self.assertGreater(ch.hp, 30)
                    self.assertEqual(used, [1])

    async def test_medicine_category_follows_room_war_not_recent_hits(self):
        for war in (False, True):
            for type_id in (6043, 6055):
                f, ch, room, used = self.fixture(type_id)
                room.ws = war
                f.last_hit = 99
                acks = []
                f.ack = acks.append
                with patch.object(combat, 'now', return_value=100):
                    allowed = type_id == 6055 or not war
                    if allowed:
                        args = self.start(f)
                        f.heal_now(*args)
                        self.assertEqual(acks, [inventory.RES_OK])
                        self.assertEqual(used, [1])
                    else:
                        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
                        self.assertEqual(acks, [inventory.RES_NOT_READY])
                        self.assertIsNone(f.healing)
                        self.assertEqual((ch.hp, f.ap, used), (30, 100, []))

    async def test_room_peace_immediately_allows_ordinary_medicine(self):
        f, ch, room, used = self.fixture(6043)
        room.ws = True
        f.ap_max = 100
        f.sess.on_map = False
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        rc.room, rc.mobs = room, {}
        rc.fighters = lambda: [f]
        f.rc = rc
        with patch.object(combat, 'now', return_value=100):
            combat.Fighter.hit_exchanged(f)
            rc.set_ws(False)
            self.assertEqual(combat.Fighter.exit_timer_left(f), 0)
            args = self.start(f)
            f.heal_now(*args)
        self.assertEqual(used, [1])

    async def test_room_peace_keeps_pending_battle_heal(self):
        f, ch, room, used = self.fixture(6055)
        room.ws = True
        args = self.start(f)
        room.ws = False
        f.heal_now(*args)
        self.assertGreater(ch.hp, 30)
        self.assertEqual(used, [1])
        self.assertEqual(f.ap, 100 - items.params_of(6055)['heal_cost'])
        self.assertNotIn(('actionCancel', dict(release=1)), f.frames)

    async def test_hit_given_or_taken_cancels_pending_heal_immediately(self):
        for type_id in (6043,):
            f, ch, room, used = self.fixture(type_id)
            with patch.object(combat, 'now', return_value=100):
                args = self.start(f)
                timer = f.healing
                combat.Fighter.hit_exchanged(f)
                self.assertIsNone(f.healing)
                self.assertTrue(timer.cancelled())
                f.heal_now(*args)
            self.assertEqual((ch.hp, f.ap, used), (30, 100, []))

    async def test_patient_recent_hit_does_not_block_ordinary_healing_in_peace(self):
        f, ch, room, used = self.fixture(6043)
        patient = progression.Character()
        patient.hp = 25
        target = NS(is_player=True, dead=False, last_hit=99, cell=1,
                    character=lambda: patient, eid=2)
        f.cell = 0
        f.sess.loc = NS(width=20, height=20)
        f.rc.actor = lambda _: target
        with patch.object(combat, 'now', return_value=100):
            combat.Fighter.use_heal(f, dict(obj='1', target='100000002'), inventory.USE_TARGET)
            self.assertIsNotNone(f.healing)
            timer = f.healing
            args = timer._args[-1]
            timer.cancel()
            f.heal_now(*args)
        self.assertEqual(used, [1])
        self.assertGreater(patient.hp, 25)

    async def test_hit_does_not_cancel_pending_battle_medicine(self):
        f, ch, room, used = self.fixture(6055)
        room.ws = True
        with patch.object(combat, 'now', return_value=100):
            combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
            timer = f.healing
            args = timer._args[-1]
            combat.Fighter.hit_exchanged(f)
            self.assertIs(f.healing, timer)
            self.assertFalse(timer.cancelled())
            timer.cancel()
            f.heal_now(*args)
        self.assertGreater(ch.hp, 30)
        self.assertEqual(used, [1])

    async def test_battle_medicine_heals_patient_during_room_war(self):
        f, ch, room, used = self.fixture(6055)
        patient = progression.Character()
        patient.hp = 25
        target = NS(dead=False, last_hit=99, character=lambda: patient, eid=2)
        room.ws = True
        with patch.object(combat, 'now', return_value=100):
            f.heal_now(1, target, None, 8)
        self.assertGreater(patient.hp, 25)
        self.assertEqual(used, [1])
if __name__ == '__main__':
    run_cases(HealingCompletion)
