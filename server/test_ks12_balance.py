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
EXPECTED = {4: (7072, 29), 5: (7073, 30), 6: (7074, 31), 7: (7075, 34),
            8: (7076, 23), 9: (7077, 26), 10: (7078, 36), 11: (7079, 36),
            12: (7080, 44), 14: (7070, 44), 15: (7081, 44)}


class Ks12Numbers(unittest.TestCase):
    def test_specialisation_ladder_and_named_copies(self):
        required = {4: None, 5: None, 6: None, 7: 1, 8: 2, 9: 2,
                    10: 3, 11: 3, 12: 3, 14: 3, 15: 4}
        for t, (root, name) in items.catalogue().items():
            if root != items.FIRE_ARM or not name.startswith('lamantin_shotgun_'):
                continue
            row = dict(type_id=t, root=root)
            params = items.params_of(t)
            level = inventory.item_level(t)
            if level not in required:
                continue
            need = required[level]
            with self.subTest(type=t, level=level):
                ch = progression.Character()
                ch.skill[progression.SHOOTING][0] = level
                ch.recalc()
                if need is None:
                    self.assertFalse(params.get('need_specs_m', 0) & (1 << 3))
                    continue
                ch.spec[3][0] = need - 1
                self.assertIsNotNone(inventory.weapon_requirement_error(row, ch))
                ch.spec[3][0] = need
                self.assertIsNone(inventory.weapon_requirement_error(row, ch))

    def test_all_base_versions_change_only_the_active_shot_cost(self):
        for level, (t, cost) in EXPECTED.items():
            with self.subTest(level=level, type=t):
                with patch.dict(items.KS12_FIRE_COSTS, {}, clear=True), \
                        patch.object(items, "KS12_FIRE_COST_PERCENT", 100):
                    before = items.params_of(t)
                after = items.params_of(t)
                self.assertEqual(max(after['need_skills']), level)
                self.assertEqual(after['fire_costs'], [0, 0, cost])
                self.assertEqual(items.static_info(t)[1]['fire_costs'], [0, 0, cost])
                self.assertEqual({k: v for k, v in before.items() if k != 'fire_costs'},
                                 {k: v for k, v in after.items() if k != 'fire_costs'})
                # Pellets do not become cartridges after changing AP.
                self.assertEqual(combat.pull(after, 2, after['clip_size']),
                                 (6 if level == 14 else 10, 1))

    def test_burst_limit_covers_named_and_clan_copies_without_changing_damage(self):
        for t, (root, name) in items.catalogue().items():
            if root != items.FIRE_ARM or not name.startswith('lamantin_shotgun_'):
                continue
            with self.subTest(type=t):
                params = items.params_of(t)
                original = items.wiki()[t]
                self.assertEqual(params['fire_mods'], [min(v, 10) for v in original['fire_mods']])
                self.assertEqual(combat.pull(params, 2, params['clip_size']),
                                 (6 if '_14' in name else 10, 1))
                for field in ('h_damage_min', 'h_damage_max', 'st_damage_min', 'st_damage_max'):
                    self.assertEqual(params[field], original[field])

    def test_original_two_shot_budget_is_not_rebalanced_by_new_medicine_cost(self):
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
                # KS-12's approved costs predate the independent medicine AP change.
                heal = {6056: 8, 6057: 10, 6058: 12}[bandage]
                with patch.dict(items.KS12_FIRE_COSTS, {}, clear=True), \
                        patch.object(items, "KS12_FIRE_COST_PERCENT", 100):
                    original = items.params_of(weapon)['fire_costs'][2]
                previous = 32 if level == 5 else 27 if level == 9 else original * 2
                limit = (ch.ap_ceiling - heal - 5) // 2
                self.assertEqual(cost, (min(previous, limit) * 95 + 50) // 100)
                self.assertGreaterEqual(ch.ap_ceiling - cost * 2 - heal - 5, 0)
                if previous <= limit:
                    self.assertEqual(cost, (previous * 95 + 50) // 100)

    def test_all_copies_reduce_cost_and_description_matches(self):
        for t, (root, name) in items.catalogue().items():
            if root != items.FIRE_ARM or not name.startswith('lamantin_shotgun_'):
                continue
            with self.subTest(type=t):
                with patch.object(items, 'KS12_FIRE_COST_PERCENT', 100):
                    before = items.params_of(t)
                after = items.params_of(t)
                expected = [max(1, (v * 95 + 50) // 100) if v else 0
                            for v in before['fire_costs']]
                self.assertEqual(after['fire_costs'], expected)
                self.assertEqual(items.static_info(t)[1]['fire_costs'], expected)
                self.assertEqual({k: v for k, v in after.items() if k != 'fire_costs'},
                                 {k: v for k, v in before.items() if k != 'fire_costs'})
        for t in (25996, 25997):  # Striker is not a KS-12.
            self.assertEqual(items.params_of(t)['fire_costs'][0], 15)


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
                    _uniq, _target, _cell, _weapon, paid, rounds, palm_cycle, mode = resolved[0]
                    self.assertEqual(paid, cost)
                    self.assertEqual(rounds, 1)
                    self.assertIsNone(palm_cycle)
                    self.assertEqual(mode, 2)
                finally:
                    combat.Fighter.cancel_timers(f)


if __name__ == '__main__':
    try:
        run_cases(Ks12Numbers, Ks12AttackCosts)
    finally:
        server.STORE.close()
