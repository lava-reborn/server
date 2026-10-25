"""Reload replacement, atomic ammunition and AP, and stale callback rejection.

PROTOCOL.md action ordering applies to reloads too. Use real Inventory and
Session transactions with SQLite in memory; execute saved timer callbacks,
without sockets, AI, sleeps or a game simulation.
"""
import asyncio
import logging
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
logging.disable(logging.CRITICAL)

import accounts
import combat
import inventory
import items
import progression
import server
from test_quest_state import session
from testkit import run_cases


class ReloadSync(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = accounts.Store(':memory:')
        previous = server.STORE
        server.STORE = self.store
        self.addCleanup(setattr, server, 'STORE', previous)
        self.addCleanup(self.store.close)
        account, _ = self.store.register('reload-unit', 'local-password')
        cid, _ = self.store.create_character(account, 'reload-unit', 0, '1')
        self.s = session(self.store, char_id=cid)
        self.s.char = progression.Character.load(self.store, cid)
        for skill in self.s.char.skill:
            skill[0] = 20
        for spec in self.s.char.spec:
            spec[0] = 5
        self.s.char.recalc()
        self.s.char.save(self.store)
        self.s.active = self.store.character(cid)
        self.s.room = None
        self.s.loc = NS(id=49, spawns=[], war=True, width=64, height=64)
        self.s.on_map = False
        self.s.walk = None
        self.s.fee_shown, self.s.skill_shown = {}, {}
        self.s.count_bag = lambda: None
        self.s.answer = lambda message: self.frames.append(('message', message))
        self.frames = []
        self.s.send = lambda cmd, **p: self.frames.append((cmd, p))
        room = NS(ws=True, broadcast=lambda frame, **kw: self.frames.append(frame))
        target = NS(is_player=False, cell=1)
        rc = NS(room=room, actor=lambda _: target, set_ws=lambda _: None)
        self.f = NS(sess=self.s, rc=rc, ap=100, dead=False, cell=0, eid=0,
                    aim=None, strike=None, healing=None, reloading=None,
                    action_revision=0, walk_ap=None, preparing=lambda: False,
                    character=lambda: self.s.char,
                    ack=lambda res: self.s.send('cmdAck', res=res))
        self.s.combat = self.f
        self.f.c_ap = lambda: combat.Fighter.c_ap(self.f)
        self.f.primary_changed = lambda: combat.Fighter.primary_changed(self.f)
        self.f.refuse_no_ap = lambda: combat.Fighter.refuse_no_ap(self.f)
        self.f.fire_now = lambda *args: None
        self.f.heal_now = lambda *args: None
        self.gun = self.give(25636, slot=inventory.PRIMARY)
        self.ammo_type = items.params_of(25636)['comp_array'][0]
        self.ammo = self.give(self.ammo_type, count=50)

    async def asyncTearDown(self):
        combat.Fighter.cancel_timers(self.f)

    def give(self, t, **changes):
        fields = inventory.new_fields(t)
        root = fields.pop('root')
        fields.update(slot=inventory.BAG)
        fields.update(changes)
        return self.store.create_item(self.s.char_id, t, root, **fields)

    def start(self):
        self.frames.clear()
        with patch.object(inventory.pace, 'paced', return_value=3600):
            self.s.inv.use_load(dict(obj=inventory.oid_of(self.gun), target=inventory.oid_of(self.ammo)))
        self.assertIsNotNone(self.f.reloading)
        timer = self.f.reloading
        return timer._callback, timer._args

    def invoke(self, saved):
        saved[0](*saved[1])

    def resources(self):
        gun, ammo = self.store.item(self.gun['uniq']), self.store.item(self.ammo['uniq'])
        return gun['ammo_count'], ammo['count'] if ammo else 0, self.f.ap

    async def test_completion_consumes_ammo_and_ap_once_after_the_deadline(self):
        saved = self.start()
        self.assertEqual(self.resources(), (0, 50, 100))
        self.invoke(saved)
        clip = items.params_of(25636)['clip_size']
        cost = items.params_of(25636)['reload_cost']
        self.assertEqual(self.resources(), (clip, 50 - clip, 100 - cost))
        self.assertEqual([p['res'] for n, p in self.frames if n == 'cmdAck'], [0])
        self.invoke(saved)
        self.assertEqual(self.resources(), (clip, 50 - clip, 100 - cost))

    async def test_switch_and_movement_cancel_without_ammo_or_ap_consumption(self):
        for action in ('switch', 'move'):
            with self.subTest(action=action):
                saved = self.start()
                if action == 'switch':
                    combat.Fighter.primary_changed(self.f)
                else:
                    self.s.walk = ([0, 1], asyncio.get_running_loop().time())
                    combat.Fighter.moved(self.f, [0, 1])
                    self.s.walk = None
                self.invoke(saved)
                self.assertEqual(self.resources(), (0, 50, 100))
                self.assertIsNone(self.f.reloading)
                self.assertFalse(self.s.inv.reloads)
                self.assertTrue(any(n == 'actionCancel' for n, _ in self.frames))

    async def test_accepted_healing_replaces_reload_and_rejected_medicine_preserves_it(self):
        saved = self.start()
        combat.Fighter.use_heal(self.f, dict(obj='invalid'), inventory.USE_IDLE)
        self.assertIsNotNone(self.f.reloading)
        medicine = self.give(6055)
        combat.Fighter.use_heal(self.f, dict(obj=inventory.oid_of(medicine)), inventory.USE_IDLE)
        self.assertIsNone(self.f.reloading)
        self.assertIsNotNone(self.f.healing)
        self.invoke(saved)
        self.assertEqual(self.resources(), (0, 50, 100))

    async def test_accepted_shot_replaces_reload_using_only_previously_loaded_rounds(self):
        self.store.update_item(self.gun['uniq'], ammo_count=1, ammo_type=self.ammo_type)
        saved = self.start()
        combat.Fighter.use_fire(self.f, dict(obj=inventory.oid_of(self.gun), target='100000001'))
        self.assertIsNone(self.f.reloading)
        self.assertIsNotNone(self.f.aim)
        self.invoke(saved)
        self.assertEqual(self.resources(), (1, 50, 100))

    async def test_rejected_reload_and_empty_shot_do_not_cancel_existing_reload(self):
        saved = self.start()
        timer = self.f.reloading
        self.s.inv.use_load(dict(obj=inventory.oid_of(self.gun), target='invalid'))
        combat.Fighter.use_fire(self.f, dict(obj=inventory.oid_of(self.gun), target='100000001'))
        self.assertIs(self.f.reloading, timer)
        self.assertFalse(timer.cancelled())
        self.invoke(saved)
        self.assertGreater(self.resources()[0], 0)

    async def test_failed_completion_rolls_back_inputs_without_a_second_ack(self):
        saved = self.start()
        original = self.store.update_item
        def fail(uniq, **fields):
            original(uniq, **fields)
            if uniq == self.gun['uniq']:
                raise RuntimeError('failed after ammunition was changed')
        with patch.object(self.store, 'update_item', side_effect=fail):
            self.invoke(saved)
        self.assertEqual(self.resources(), (0, 50, 100))
        self.assertEqual([p['res'] for n, p in self.frames if n == 'cmdAck'], [0])
        self.assertFalse(any(n.startswith('ss_') for n, _ in self.frames))

    async def test_changed_ammunition_owner_cannot_be_consumed(self):
        saved = self.start()
        self.store.update_item(self.ammo['uniq'], slot=inventory.BANK)
        self.invoke(saved)
        self.assertEqual(self.resources(), (0, 50, 100))

    async def test_insufficient_ap_refuses_reload_without_replacing_aim(self):
        timer = asyncio.get_running_loop().call_later(3600, lambda: None)
        self.f.aim = timer
        self.f.ap = 0
        self.s.inv.use_load(dict(obj=inventory.oid_of(self.gun), target=inventory.oid_of(self.ammo)))
        self.assertIs(self.f.aim, timer)
        self.assertFalse(timer.cancelled())
        self.assertIsNone(self.f.reloading)
        self.assertEqual(self.resources(), (0, 50, 0))
        self.assertEqual(self.frames[0], ('cmdAck', dict(res=inventory.RES_NO_AP)))

    async def test_old_callback_cannot_finish_a_new_reload(self):
        old = self.start()
        combat.Fighter.primary_changed(self.f)
        current = self.start()
        timer = self.f.reloading
        self.invoke(old)
        self.assertIs(self.f.reloading, timer)
        self.assertEqual(self.resources(), (0, 50, 100))
        self.invoke(current)
        clip = items.params_of(25636)['clip_size']
        self.assertEqual(self.resources()[:2], (clip, 50 - clip))


if __name__ == '__main__':
    run_cases(ReloadSync)
