"""Action replacement invariants with real callbacks and isolated inventories.

PROTOCOL.md's action sequence and ItemActivator/Location.as define ordering.
Replaying a saved callback catches effects after cancellation or replacement;
this does not exercise Flash rendering or operating-system focus.
"""
import asyncio
import os
import sys
import unittest
from types import SimpleNamespace as NS
os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'
sys.path.insert(0, os.path.dirname(__file__))
import combat  # noqa: E402
import inventory  # noqa: E402
import items  # noqa: E402
import progression  # noqa: E402
from test_healing_completion import HealingCompletion  # noqa: E402
from testkit import run_cases  # noqa: E402

class ActionOrder(unittest.IsolatedAsyncioTestCase):

    def fixture(self, type_id=6055):
        f, ch, room, used = HealingCompletion().fixture(type_id)
        events = []
        f.sess.send = lambda cmd, **p: events.append((cmd, p))
        f.c_ap = lambda: events.append(('c_ap', dict(ap=f.ap)))
        f.aim = f.strike = None
        f.sess.walk = None
        return (f, ch, room, used, events)

    def start(self, f):
        combat.Fighter.use_heal(f, dict(obj='1'), inventory.USE_IDLE)
        self.assertIsNotNone(f.healing)
        return (f.healing._callback, f.healing._args)

    def invoke(self, saved):
        saved[0](*saved[1])

    def attack_fixture(self, type_id=25566):
        f, ch, room, used, events = self.fixture()
        for skill in ch.skill:
            skill[0] = 20
        ch.spec[1][0] = 4
        row = dict(inventory.new_fields(type_id), type_id=type_id, uniq=2, root=items.COLD_ARM if type_id == 6241 else items.FIRE_ARM, slot=inventory.PRIMARY, char_id=1, ammo_count=10, ammo_type=6101, brk=100, cur_mode=0)
        f.sess.on_map = False
        f.sess.loc = NS(war=True, width=20, height=20)
        f.sess.inv.find = lambda obj: row if obj == 'weapon' else dict(uniq=1, char_id=1, root=items.HEAL, type_id=6055, use_count=1)
        f.cell = 0
        f.preparing = lambda: False
        room.broadcast = lambda frame, **kw: events.append(frame)
        f.rc.set_ws = lambda ws: setattr(room, 'ws', ws)
        f.fire_now = lambda *args: events.append(('resolved_fire', args))
        f.strike_now = lambda *args: events.append(('resolved_strike', args))
        f.strike_with = lambda *args: combat.Fighter.strike_with(f, *args)
        return (f, ch, room, used, events, row)

    async def test_valid_attack_replaces_heal(self):
        for type_id, kind in ((25566, 'aim'), (6241, 'strike')):
            f, ch, room, used, events, row = self.attack_fixture(type_id)
            old = self.start(f)
            combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
            self.assertIsNone(f.healing)
            self.assertIsNotNone(getattr(f, kind))
            self.invoke(old)
            self.assertEqual(used, [])
            self.assertEqual((row['ammo_count'], row['brk'], f.ap), (10, 100, 100))
            combat.Fighter.cancel_pending(f)

    async def test_target_change_only_resolves_last_attack(self):
        f, ch, room, used, events, row = self.attack_fixture()
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        old = (f.aim._callback, f.aim._args)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000002'))
        new = (f.aim._callback, f.aim._args)
        self.invoke(old)
        self.invoke(new)
        self.invoke(new)
        hits = [e for e in events if e[0] == 'resolved_fire']
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1][2], 2)

    async def test_rejected_attack_keeps_heal(self):
        f, ch, room, used, events, row = self.attack_fixture()
        old = self.start(f)
        row['ammo_count'] = 0
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        self.assertIsNotNone(f.healing)
        self.invoke(old)
        self.assertEqual(used, [1])

    async def test_melee_spam_preserves_original_swing(self):
        f, ch, room, used, events, row = self.attack_fixture(6241)
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
        timer = f.strike
        revision = f.action_revision
        saved = (timer._callback, timer._args)
        for i in range(20):
            # Even a different target or bare fist must not replace this swing.
            combat.Fighter.use_fire(f, dict(obj='weapon' if i % 2 else '0', target='000000002'))
            self.assertIs(f.strike, timer)
            self.assertEqual(f.action_revision, revision)
            self.assertFalse(timer.cancelled())
        self.assertNotIn('actionCancel', [e[0] for e in events if isinstance(e, tuple)])
        self.assertEqual((row['brk'], f.ap), (100, 100))
        self.invoke(saved)
        self.invoke(saved)
        hits = [e for e in events if isinstance(e, tuple) and e[0] == 'resolved_strike']
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][1][1], 1)
        # Subsequent presses start the next swing after the previous one landed.
        combat.Fighter.use_fire(f, dict(obj='weapon', target='000000002'))
        self.assertIsNotNone(f.strike)
        self.assertIsNot(f.strike, timer)
        self.invoke((f.strike._callback, f.strike._args))
        hits = [e for e in events if isinstance(e, tuple) and e[0] == 'resolved_strike']
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[1][1][1], 2)
        timer.cancel()

    async def test_move_cancels_heal_and_stale_callback(self):
        f, ch, room, used, events = self.fixture()
        saved = self.start(f)
        combat.Fighter.moved(f, [0, 1])
        self.invoke(saved)
        self.assertEqual((ch.hp, used, f.ap), (30, [], 100))
        self.assertIsNone(f.healing)
        self.assertEqual(sum((e[0] == 'actionCancel' for e in events)), 1)

    async def test_heal_replaces_heal_only_last_applies(self):
        f, ch, room, used, events = self.fixture()
        old = self.start(f)
        new = self.start(f)
        self.invoke(old)
        self.assertEqual((ch.hp, used), (30, []))
        self.invoke(new)
        self.invoke(new)
        self.assertEqual(used, [1])
        self.assertGreater(ch.hp, 30)
        if f.healing:
            f.healing.cancel()

    async def test_rejected_replacement_keeps_previous(self):
        f, ch, room, used, events = self.fixture()
        saved = self.start(f)
        f.sess.inv.find = lambda _: None
        combat.Fighter.use_heal(f, dict(obj='bad'), inventory.USE_IDLE)
        self.assertIsNotNone(f.healing)
        self.invoke(saved)
        self.assertEqual(used, [1])

    async def test_combat_ap_paid_once_at_completion(self):
        f, ch, room, used, events = self.fixture()
        room.ws = True
        old_ap = f.ap
        cost = items.params_of(6055)['heal_cost']
        saved = self.start(f)
        self.assertEqual(f.ap, old_ap)
        self.invoke(saved)
        self.invoke(saved)
        self.assertEqual(f.ap, old_ap - cost)
        self.assertEqual(used, [1])

    async def test_death_before_heal_preserves_ap(self):
        f, ch, room, used, events = self.fixture()
        room.ws = True
        saved = self.start(f)
        f.dead = True
        ch.hp = 0
        self.invoke(saved)
        self.assertEqual((f.ap, ch.hp, used), (100, 0, []))

    async def test_ap_lost_before_completion_preserves_items(self):
        f, ch, room, used, events = self.fixture()
        room.ws = True
        saved = self.start(f)
        f.ap = 0
        self.invoke(saved)
        self.assertEqual((ch.hp, used, f.ap), (30, [], 0))
        combat.Fighter.fire_now(f, 2, None, 1, NS(num_shots=1), 8)
        combat.Fighter.strike_now(f, None, 1, (10, 20), 1, 8, 2)
        self.assertEqual((ch.hp, used, f.ap), (30, [], 0))

    async def test_pending_attack_replaced_by_healing(self):
        for kind in ('aim', 'strike'):
            f, ch, room, used, events = self.fixture()
            effects = []
            rev = combat.Fighter.begin_action(f)
            combat.Fighter.schedule_action(f, rev, kind, 60, lambda: effects.append('hit'))
            old = getattr(f, kind)
            saved = (old._callback, old._args)
            self.start(f)
            self.invoke(saved)
            self.assertEqual(effects, [])
            self.assertTrue(old.cancelled())
            combat.Fighter.cancel_pending(f)

    async def test_chat_inventory_reads_leave_timer_alone(self):
        f, ch, room, used, events = self.fixture()
        saved = self.start(f)
        # These operations do not call begin_action or cancel_pending.
        f.sess.send('userMsg', entry='hello')
        f.sess.inv.find('1')
        self.invoke(saved)
        self.assertEqual(used, [1])

    async def test_new_action_stops_walk_at_live_cell(self):
        f, ch, room, used, events = self.fixture()
        f.sess.walk = ([1, 2, 3], 0)
        f.sess.live_cell = lambda: 2
        f.sess.cancel_passage = lambda: events.append(('passage', {}))
        room.broadcast = lambda frame, **kw: None
        combat.Fighter.begin_action(f)
        self.assertEqual(f.sess.pos, 2)
        self.assertIn(('actionCancel', dict(pos=2)), events)

    async def test_cancel_timers_prevents_all_old_callbacks(self):
        for kind in ('aim', 'strike', 'healing'):
            f, ch, room, used, events = self.fixture()
            effects = []
            rev = combat.Fighter.begin_action(f)
            combat.Fighter.schedule_action(f, rev, kind, 60, lambda: effects.append(1))
            old = getattr(f, kind)
            saved = (old._callback, old._args)
            combat.Fighter.cancel_timers(f)
            self.invoke(saved)
            self.assertEqual(effects, [])
if __name__ == '__main__':
    run_cases(ActionOrder)
