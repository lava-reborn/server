"""KS-12 AP rebalance: A-set budget, shared wire and attack costs.

Isolated handler fixtures; no sockets, running game or farm simulation.
"""
import os
import unittest
from unittest.mock import patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

import combat
import inventory
import items
import progression
import server
import setcraft
from test_action_order import ActionOrder
from testkit import run_cases


# Explicit owner-approved targets, independent of the runtime mapping.
EXPECTED = {4: (7072, 31), 5: (7073, 32), 6: (7074, 33), 7: (7075, 36),
            8: (7076, 24), 9: (7077, 27), 10: (7078, 38), 11: (7079, 38),
            12: (7080, 46), 14: (7070, 46), 15: (7081, 46)}


class Ks12Numbers(unittest.TestCase):
    def test_all_base_versions_change_only_the_active_shot_cost(self):
        for level, (t, cost) in EXPECTED.items():
            with self.subTest(level=level, type=t):
                with patch.dict(items.KS12_FIRE_COSTS, {}, clear=True):
                    before = items.params_of(t)
                after = items.params_of(t)
                self.assertEqual(max(after['need_skills']), level)
                self.assertEqual(after['fire_costs'], [0, 0, cost])
                self.assertEqual(items.static_info(t)[1]['fire_costs'], [0, 0, cost])
                self.assertEqual({k: v for k, v in before.items() if k != 'fire_costs'},
                                 {k: v for k, v in after.items() if k != 'fire_costs'})
                # Pellets do not become cartridges after changing AP.
                self.assertEqual(combat.pull(after, 2, after['clip_size']),
                                 (6 if level == 14 else 12, 1))

    def test_two_shots_bandage_and_five_steps_fit_the_actual_a_set(self):
        slots = dict(helm=inventory.HEAD, shirt=inventory.CAMO,
                     armor=inventory.ARMOR, pants=inventory.LEGS, boots=inventory.BOOTS)
        for level, (weapon, cost) in EXPECTED.items():
            with self.subTest(level=level):
                rung = max((r for r in setcraft.LADDER
                            if r['variant'] == 'A' and r['level'] <= level),
                           key=lambda r: r['level'])
                worn = [dict(root=items.WEAR, type_id=t, slot=slots[slot], brk=1)
                        for slot, t in rung['members'].items()]
                ch = progression.Character()
                ch.skill[progression.SHOOTING][0] = level
                ch.recalc()
                ch.set_gear(inventory.gear_bonus(worn))
                bandage = 6056 if level < 8 else 6057 if level < 12 else 6058
                heal = items.params_of(bandage)['heal_cost']
                with patch.dict(items.KS12_FIRE_COSTS, {}, clear=True):
                    original = items.params_of(weapon)['fire_costs'][2]
                previous = 32 if level == 5 else 27 if level == 9 else original * 2
                limit = (ch.ap_ceiling - heal - 5) // 2
                self.assertEqual(cost, min(previous, limit))
                self.assertGreaterEqual(ch.ap_ceiling - cost * 2 - heal - 5, 0)
                if previous <= limit:
                    self.assertEqual(cost, previous)  # a minimum must not become an extra nerf

    def test_striker_and_named_copies_are_unchanged(self):
        for t in (25996, 25997, 34565, 35032, 35033, 35037, 36860):
            with self.subTest(type=t):
                with patch.dict(items.KS12_FIRE_COSTS, {}, clear=True):
                    before = items.params_of(t)
                self.assertEqual(items.params_of(t), before)
        self.assertEqual(items.params_of(25996)['fire_costs'][0], 15)
        self.assertEqual(items.params_of(25997)['fire_costs'][0], 15)


class Ks12AttackCosts(unittest.IsolatedAsyncioTestCase):
    async def test_handler_refuses_below_new_cost_and_schedules_exact_cost(self):
        for level, (t, cost) in EXPECTED.items():
            with self.subTest(level=level, type=t):
                f, ch, room, _used, events, row = ActionOrder().attack_fixture(t)
                # Capture the real acknowledgement on the fixture's current wire.
                f.ack = lambda res: combat.Fighter.ack(f, res)
                try:
                    for spec in ch.spec:
                        spec[0] = 5
                    row['cur_mode'] = 2
                    row['ammo_type'] = items.params_of(t)['comp_array'][0]
                    room.ws = True
                    f.ap = cost - 1
                    f.refuse_no_ap = lambda: events.append(('insufficient_ap', None))
                    before = dict(row)
                    combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
                    self.assertIsNone(f.aim)
                    self.assertEqual(row, before)
                    self.assertIn(('insufficient_ap', None), events)
                    events.clear()
                    f.ap = cost
                    combat.Fighter.use_fire(f, dict(obj='weapon', target='000000001'))
                    self.assertIsNotNone(f.aim)
                    self.assertEqual(row, before)  # no early ammo or wear consumption
                    self.assertEqual([p['res'] for n, p in events if n == 'cmdAck'],
                                     [inventory.RES_OK])
                    f.aim._callback(*f.aim._args)
                    resolved = [args for name, args in events if name == 'resolved_fire']
                    self.assertEqual(len(resolved), 1)
                    self.assertEqual(resolved[0][-2], cost)
                    self.assertEqual(resolved[0][-1], 1)
                finally:
                    combat.Fighter.cancel_timers(f)


if __name__ == '__main__':
    try:
        run_cases(Ks12Numbers, Ks12AttackCosts)
    finally:
        server.STORE.close()
