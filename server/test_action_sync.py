"""Movement AP, confirmed healing bars, observer cancellation and melee spam.

See PROTOCOL.md action synchronization, Location.movePlayer and
DisplayLocScene's aiming events. Session's position setter is real; frames
are captured without a socket. test_combat covers the matching wire flow.
"""
import asyncio
import logging
import os
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import server  # noqa: E402
import test_action_order as fixtures  # noqa: E402
from testkit import run_cases  # noqa: E402

class ActionSync(unittest.IsolatedAsyncioTestCase):

    def fixture(self, weapon=25566):
        f, ch, room, used, events, row = fixtures.ActionOrder().attack_fixture(weapon)
        source = f.sess
        s = server.Session.__new__(server.Session)
        s.char_id = 1
        s.char = ch
        s.combat = f
        s.room = room
        s.loc = source.loc
        s.inv = source.inv
        s.send = source.send
        s.answer = source.answer
        s.cancel_passage = lambda: None
        s.on_map = False
        s.pos = 0
        f.sess = s
        f.ap_max = 100
        room.ws = True

        async def cleanup():
            combat.Fighter.cancel_timers(f)
        self.addAsyncCleanup(cleanup)
        return (f, s, room, events, row)

    def clock(self, seconds):
        return patch.object(asyncio.get_running_loop(), 'time', return_value=seconds)

    def start_walk(self, f, s, cells):
        s.pos = cells[-1]
        s.walk = (cells, 100.0)
        combat.Fighter.moved(f, cells)

    async def test_stopping_at_second_step_charges_two_not_whole_route(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
            self.assertEqual(f.ap, 100)
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual((s.pos, f.ap), (2, 98))
        self.assertIsNone(s.walk)
        self.assertIsNone(f.walk_ap)
        self.assertIn(('c_ap', dict(ap=98)), events)

    async def test_attack_ap_check_does_not_charge_unwalked_tail(self):
        f, s, room, events, row = self.fixture()
        cost = items.params_of(row['type_id'])['fire_costs'][row['cur_mode']]
        f.ap = cost + 2
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        self.assertIsNotNone(f.aim)
        self.assertEqual((s.pos, f.ap), (2, cost))

    async def test_finished_walk_is_charged_exactly_once(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 10.1 * combat.mobs.HEX_MS / 1000):
            self.assertEqual(s.live_cell(), 10)
            combat.Fighter.settle_walk(f)
            combat.Fighter.begin_action(f)
        self.assertEqual(f.ap, 90)

    async def test_reroute_does_not_charge_old_tail(self):
        f, s, room, events, row = self.fixture()
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        second = 100.0 + 2.1 * combat.mobs.HEX_MS / 1000
        with self.clock(second):
            s.pos = 6
            s.walk = ([2, 3, 4, 5, 6], second)
            combat.Fighter.moved(f, [2, 3, 4, 5, 6])
        with self.clock(second + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual((s.pos, f.ap), (4, 96))

    async def test_peace_steps_not_charged_when_war_starts(self):
        f, s, room, events, row = self.fixture()
        room.ws = False
        rc = NS(room=room, fighters=lambda: [f], mobs={})
        with self.clock(100.0):
            self.start_walk(f, s, list(range(11)))
        with self.clock(100.0 + 2.1 * combat.mobs.HEX_MS / 1000):
            combat.RoomCombat.set_ws(rc, True)
        with self.clock(100.0 + 4.1 * combat.mobs.HEX_MS / 1000):
            combat.Fighter.begin_action(f)
        self.assertEqual(f.ap, 98)

    async def test_replacing_aim_notifies_owner_and_observers(self):
        f, s, room, events, row = self.fixture()
        own = []
        observers = []
        s.send = lambda cmd, **p: own.append((cmd, p))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        saved = (f.aim._callback, f.aim._args)
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        saved[0](*saved[1])
        self.assertIn(('actionCancel', dict(release=0, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)
        self.assertIsNone(f.aim)
        self.assertFalse(any((e[0] == 'resolved_fire' for e in events)))
        self.assertEqual(own[-1][0], 'actionStart')

    def movable_inventory(self, f, s, row):
        store = NS(update_item=lambda uniq, **fields: row.update(fields))
        inv = inventory.Inventory(s, store)
        inv.find = lambda obj: row
        inv.in_slot = lambda slot: None
        s.character = f.character
        f.primary_changed = lambda: combat.Fighter.primary_changed(f)
        return inv

    async def test_switch_away_and_back_cancels_aim_and_saved_callback(self):
        f, s, room, events, row = self.fixture()
        inv = self.movable_inventory(f, s, row)
        own = []
        observers = []
        s.send = lambda cmd, **p: own.append((cmd, p))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        saved = (timer._callback, timer._args)
        before = (f.ap, row['ammo_count'], row['brk'])
        for src, dst in ((inventory.PRIMARY, inventory.SECONDARY), (inventory.SECONDARY, inventory.PRIMARY)):
            inv.ss_move(dict(obj='weapon', **{'from': src, 'to': dst}))
        saved[0](*saved[1])
        self.assertTrue(timer.cancelled())
        self.assertIsNone(f.aim)
        self.assertEqual((f.ap, row['ammo_count'], row['brk']), before)
        self.assertFalse(any((e[0] == 'resolved_fire' for e in events)))
        self.assertIn(('actionCancel', dict(release=1, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)

    async def test_refused_weapon_move_preserves_aim(self):
        f, s, room, events, row = self.fixture()
        inv = self.movable_inventory(f, s, row)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        revision = f.action_revision
        inv.ss_move(dict(obj='weapon', **{'from': inventory.BAG, 'to': inventory.PRIMARY}))
        self.assertIs(f.aim, timer)
        self.assertFalse(timer.cancelled())
        self.assertEqual(f.action_revision, revision)

    async def test_unrelated_inventory_move_preserves_aim(self):
        f, s, room, events, row = self.fixture()
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.aim
        revision = f.action_revision
        spare = dict(row, uniq=3, slot=inventory.BAG)
        inv = self.movable_inventory(f, s, spare)
        inv.ss_move(dict(obj='spare', **{'from': inventory.BAG, 'to': inventory.SECONDARY}))
        self.assertIs(f.aim, timer)
        self.assertFalse(timer.cancelled())
        self.assertEqual(f.action_revision, revision)

    async def test_primary_change_without_aim_preserves_melee_or_heal(self):
        for kind in ('strike', 'healing'):
            f, s, room, events, row = self.fixture()
            revision = combat.Fighter.begin_action(f)
            combat.Fighter.schedule_action(f, revision, kind, 100, lambda: None)
            pending = getattr(f, kind)
            combat.Fighter.primary_changed(f)
            self.assertIs(getattr(f, kind), pending)
            self.assertFalse(pending.cancelled())
            self.assertEqual(f.action_revision, revision)

    async def test_repeated_heal_confirms_bar_after_cancelling_old_timer(self):
        f, s, room, events, row = self.fixture()
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        old = f.healing
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertTrue(old.cancelled())
        commands = [cmd for cmd, p in events if isinstance(cmd, str)]
        self.assertEqual(commands[-3:], ['actionCancel', 'c_ap', 'actionStart'])

    async def test_ap_loss_before_shot_cancels_aim_for_owner_and_observers(self):
        f, s, room, events, row = self.fixture()
        own, observers = ([], [])
        s.send = lambda command, **params: own.append((command, params))
        room.broadcast = lambda frame, **kw: observers.append((frame, kw))
        f.ap = 0
        before = (row['ammo_count'], row['brk'])
        combat.Fighter.fire_now(f, row['uniq'], None, None, NS(num_shots=1), 11, 1)
        self.assertIn(('actionCancel', dict(release=1, stop_aim=1)), own)
        self.assertIn((('actionCancel', dict(id=f.eid, stop_aim=1)), dict(exclude=s)), observers)
        self.assertIn(('c_ap', dict(ap=0)), events)
        self.assertEqual((row['ammo_count'], row['brk']), before)

    async def test_thousand_melee_presses_keep_one_timer_and_one_impact(self):
        f, s, room, events, row = self.fixture(6241)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.strike
        saved = (timer._callback, timer._args)
        deadline = timer.when()
        for _ in range(1000):
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000002'))
            self.assertIs(f.strike, timer)
            self.assertEqual(f.strike.when(), deadline)
        saved[0](*saved[1])
        saved[0](*saved[1])
        timer.cancel()
        hits = [e for e in events if e[0] == 'resolved_strike']
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1][1], 1)
if __name__ == '__main__':
    try:
        run_cases(ActionSync)
    finally:
        server.STORE.close()
