"""Real ordinary attacks keep their costs; only palm death has Eden policy."""
import contextlib
import copy
import unittest
from unittest.mock import patch

import combat
import eden
import eden_harvest as harvest
import inventory
import items
import progression
import storage
import test_eden_harvest as harvest_fixtures
from testkit import run_cases


class EdenNativeWeaponTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.case = harvest_fixtures.EdenHarvestTests('runTest')
        self.case.setUp()
        self.addCleanup(self.case.dispose)
        for name in ('store', 's', 'f', 'rc', 'palm', 'frames'):
            setattr(self, name, getattr(self.case, name))
        self.s.active = dict(self.s.active)  # Session.select_character's shape.
        for row in self.s.char.skill:
            row[0] = 20
        for row in self.s.char.spec:
            row[0] = 20
        self.s.char.attrib = [30] * len(self.s.char.attrib)
        self.enterContext(patch.object(combat, 'now', side_effect=lambda: self.case.clock))
        self.enterContext(patch.object(combat, 'roll', return_value=True))
        self.enterContext(patch.object(combat.RNG, 'randint', side_effect=lambda lo, hi: lo))
        self.enterContext(patch.object(combat.WEAR_RNG, 'random', return_value=0))
        self.enterContext(patch.object(combat, 'bullet_offset', return_value=0))
        self.enterContext(patch.object(self.rc, 'melee_critical', return_value=False))
        self.enterContext(patch.object(self.rc, 'ranged_critical', return_value=False))
        # Native attacks call the class method; route its real callback and
        # exact delay into the same deterministic timer fixture as the tool.
        self.enterContext(patch.object(combat.Fighter, 'schedule_action',
            lambda fighter, *args: fighter.__dict__['schedule_action'](*args)))

    def weapon(self, kind, sess=None):
        sess = sess or self.s
        type_id = {'gun': 25636, 'shotgun': 25876}.get(kind, 6240)
        for row in sess.inv.rows():
            if row['slot'] == inventory.PRIMARY:
                self.store.update_item(row['uniq'], slot=inventory.BAG)
        fields = inventory.new_fields(type_id)
        root = fields.pop('root')
        row = self.store.create_item(sess.char_id, type_id, root,
                                     **dict(fields, slot=inventory.PRIMARY))
        if kind in ('gun', 'shotgun'):
            self.store.update_item(row['uniq'], ammo_count=8,
                                   ammo_type=items.params_of(type_id)['comp_array'][0])
        return self.store.item(row['uniq'])

    def attack(self, row, fighter=None):
        fighter = fighter or self.f
        fighter.use_fire(dict(obj='0' if row is None else inventory.oid_of(row),
                              target='1%08x' % self.palm.eid))

    def finish(self, saved=None):
        self.case.finish(saved)

    def skill_state(self):
        return copy.deepcopy((self.s.char.skill, self.s.char.spec, self.s.char.attrib,
                              self.s.char.xp_carry))

    def assert_one_ground(self, owner=None):
        rows = self.store.db.execute('SELECT i.*, e.owner_char, e.visit FROM items i'
            ' JOIN eden_ground e ON e.uniq=i.uniq').fetchall()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        owner = owner or self.s
        self.assertEqual((row['char_id'], row['owner_char'], row['visit'], row['count']),
                         (0, owner.char_id, owner.eden_sentence['visit'], 1))
        self.assertIn(row['type_id'], harvest.REWARDS)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM eden_palm_state').fetchone()[0], 1)
        return row

    async def test_blade_uses_native_timing_damage_ap_and_wear_without_xp(self):
        row = self.weapon('blade')
        si = items.params_of(row['type_id'])
        before = self.skill_state()
        with patch.object(harvest.RNG, 'random', side_effect=AssertionError('not a tool swing')):
            self.attack(row)
            self.assertEqual(self.palm.hp, 5000)
            self.assertEqual(self.case.pending[1], 'strike')
            self.assertEqual(self.case.pending[-1], si['strike_time'] / 1000)
            self.finish()
        strength = self.s.char.attr(progression.STRENGTH)
        # Ordinary blades receive the same intellect scaling on palms as elsewhere.
        expected = round((si['h_damage_min'] + strength) * (1 + .03 * max(0, self.s.char.attr(progression.INTELLECT) - 5)))
        self.assertEqual(self.palm.hp, 5000 - expected)
        self.assertEqual(self.store.item(row['uniq'])['brk'], row['brk'] - 1)
        self.assertEqual(self.f.ap, self.f.ap_max - si['strike_cost'])
        self.assertEqual(self.skill_state(), before)
        self.assertEqual(self.palm.xp_ledger, {})
        self.assertEqual(self.palm.capture_harm, {})
        self.assertEqual(self.case.resource_count(), 0)

    async def test_fist_and_native_miss_have_normal_costs(self):
        before = self.skill_state()
        self.attack(None)
        self.assertLess(self.palm.hp, 5000)
        self.assertEqual(self.f.ap, self.f.ap_max - combat.FIST_AP)
        self.case.clock = self.f.recovery_until
        row = self.weapon('blade')
        hp, ap = self.palm.hp, self.f.ap
        with patch.object(combat, 'roll', return_value=False):
            self.attack(row)
            self.finish()
        self.assertEqual(self.palm.hp, hp)
        self.assertEqual(self.f.ap, ap - items.params_of(row['type_id'])['strike_cost'])
        self.assertEqual(self.store.item(row['uniq'])['brk'], row['brk'] - 1)
        self.assertEqual(self.skill_state(), before)
        self.assertTrue(any(c == 'caMiss' for c, _p in self.frames))

    async def test_firearm_uses_native_aim_ammo_wear_ap_and_recovery(self):
        row = self.weapon('gun')
        si, mode = items.params_of(row['type_id']), row['cur_mode']
        before = self.skill_state()
        self.attack(row)
        self.assertEqual(self.case.pending[1], 'aim')
        self.assertEqual(self.case.pending[-1], si['fire_times'][mode] / 1000)
        self.assertEqual(self.store.item(row['uniq']), row)
        self.assertEqual(self.palm.hp, 5000)
        saved = self.case.pending
        self.finish()
        self.assertLess(self.palm.hp, 5000)
        _shots, rounds = combat.pull(si, mode, row['ammo_count'])
        live = self.store.item(row['uniq'])
        self.assertEqual(live['ammo_count'], row['ammo_count'] - rounds)
        expected_wear = combat.round_wear(rounds, combat.WEAR_PER_ROUND
            * inventory.wear_multiplier(row, self.s.char))
        self.assertEqual(live['brk'], row['brk'] - expected_wear)
        self.assertEqual(self.f.ap, self.f.ap_max - si['fire_costs'][mode])
        self.assertGreater(self.f.recovery_until, self.case.clock)
        hp = self.palm.hp
        self.attack(live)
        self.assertEqual([p['res'] for c, p in self.frames if c == 'cmdAck'][-1], inventory.RES_NOT_READY)
        self.assertEqual(self.store.item(row['uniq']), live)
        self.assertEqual(self.palm.hp, hp)
        self.case.clock = self.f.recovery_until
        self.attack(live)
        self.assertEqual([p['res'] for c, p in self.frames if c == 'cmdAck'][-1], inventory.RES_OK)
        next_shot = self.case.pending
        self.assertEqual(next_shot[1], 'aim')
        self.assertNotEqual(next_shot[0], saved[0])
        self.assertEqual(self.store.item(row['uniq']), live)
        self.assertEqual(self.palm.hp, hp)
        self.finish(saved)  # Consumed timer cannot pay or hit twice.
        self.assertEqual(self.store.item(row['uniq']), live)
        self.assertEqual(self.palm.hp, hp)
        self.finish(next_shot)
        self.assertEqual(self.store.item(row['uniq'])['ammo_count'], row['ammo_count'] - 2 * rounds)
        self.assertLess(self.palm.hp, hp)
        self.assertEqual(self.skill_state(), before)
        self.assertEqual(self.palm.xp_ledger, {})

    async def test_native_final_blow_owns_one_resource_and_skips_generic_kill(self):
        for kind in ('blade', 'gun'):
            with self.subTest(kind=kind):
                if not self.palm.alive:
                    self.case.reset_cycle()
                self.f.recovery_until = 0
                row = self.weapon(kind)
                self.palm.hp = 1
                before = self.case.resource_count()
                skills = self.skill_state()
                with patch.object(self.rc, 'drop_loot', side_effect=AssertionError('generic loot')), \
                     patch.object(self.f, 'count_kill', side_effect=AssertionError('generic kill')), \
                     patch.object(combat.production, 'mined_by', side_effect=AssertionError('mining XP')):
                    self.attack(row)
                    saved = self.case.pending
                    self.finish()
                    self.rc.kill(self.palm, self.f)  # Duplicate finalization is inert.
                self.assertEqual(self.palm.hp, 0)
                self.assertFalse(self.palm.alive)
                self.assertNotIn(self.palm.eid, self.rc.room.npcs)
                self.assertEqual(self.case.resource_count(), before + 1)
                self.assertEqual(self.skill_state(), skills)
                self.assertEqual(self.palm.xp_ledger, {})
                self.assertEqual(self.palm._eden_due - self.case.clock, harvest.respawn_seconds())
                self.finish(saved)
                self.assertEqual(self.case.resource_count(), before + 1)
        rows = self.store.db.execute('SELECT * FROM eden_ground').fetchall()
        self.assertEqual([(r['owner_char'], r['visit']) for r in rows],
                         [(self.s.char_id, self.s.eden_sentence['visit'])] * 2)

    async def test_shotgun_keeps_native_pellets_and_spends_one_cartridge(self):
        row = self.weapon('shotgun')
        si, mode = items.params_of(row['type_id']), row['cur_mode']
        shots, rounds = combat.pull(si, mode, row['ammo_count'])
        self.assertGreater(shots, 1)
        self.assertEqual(rounds, 1)
        self.attack(row)
        self.finish()
        self.assertEqual(self.store.item(row['uniq'])['ammo_count'], row['ammo_count'] - 1)
        self.assertEqual(sum(c == 'faShot' and p['status'] == 1 for c, p in self.frames), shots)
        self.assertEqual(self.f.ap, self.f.ap_max - si['fire_costs'][mode])
        self.assertLess(self.palm.hp, 5000)
        self.assertEqual(self.palm.xp_ledger, {})

    async def test_other_finisher_and_stale_native_swings_cannot_hit_the_next_cycle(self):
        for kind in ('blade', 'gun'):
            with self.subTest(kind=kind):
                if not self.palm.alive:
                    self.case.reset_cycle()
                self.f.recovery_until = 0
                row = self.weapon(kind)
                worker = self.case.other_worker(2 if kind == 'blade' else 3)
                self.palm.hp = 1
                self.attack(row)
                pending = self.case.pending
                worker.click()
                self.case.impact_at(self.case.clock + worker.pending[-1], worker.pending, worker.f)
                self.assertEqual(self.case.resource_count(worker.s), 1)
                self.assertEqual(self.case.resource_count(), 0)
                self.case.reset_cycle()
                before = (self.palm.hp, self.f.ap, self.store.item(row['uniq']))
                self.finish(pending)
                self.assertEqual((self.palm.hp, self.f.ap, self.store.item(row['uniq'])), before)
                self.assertTrue(any(c == 'actionCancel' for c, _p in self.frames))

    async def test_rollback_restores_preimpact_hp_and_preserves_hidden_resource_but_not_ammo(self):
        row = self.weapon('gun')
        self.palm.hp = 1
        self.attack(row)
        saved = self.case.pending
        original = harvest._create_ground
        def fail(*args):
            original(*args)
            raise RuntimeError('injected native palm rollback')
        with patch.object(harvest, '_create_ground', side_effect=fail):
            self.finish()
        chosen = self.palm._eden_reward
        self.assertIn(chosen, harvest.REWARDS)
        self.assertEqual(self.palm.hp, 1)
        self.assertTrue(self.palm.alive)
        self.assertEqual(self.case.resource_count(), 0)
        paid = self.store.item(row['uniq'])
        self.assertLess(paid['ammo_count'], row['ammo_count'])
        self.assertLess(paid['brk'], row['brk'])
        self.assertTrue(any(c == 'usrUp' and p.get('hcur') == 1 for c, p in self.frames))
        self.finish(saved)
        self.assertEqual(self.store.item(row['uniq']), paid)
        self.case.clock = self.f.recovery_until + 1
        with patch.object(harvest.RNG, 'choice', side_effect=AssertionError('hidden result reroll')):
            self.attack(paid)
            self.finish()
        self.assertEqual(self.assert_one_ground()['type_id'], chosen)

    async def test_uncertain_committed_native_reward_closes_and_cannot_be_replayed(self):
        row = self.weapon('gun')
        self.palm.hp = 1
        self.attack(row)
        saved = self.case.pending
        original = storage.atomic
        @contextlib.contextmanager
        def lost_reply(db):
            with original(db):
                yield db
            raise storage.CommitError('committed but confirmation lost')
        def close(force=False):
            self.assertTrue(force)
            self.s.closed = True
        with patch.object(storage, 'atomic', lost_reply), patch.object(self.s, 'close', side_effect=close):
            self.finish()
        self.assertTrue(self.s.closed)
        self.assertFalse(self.palm.alive)
        self.assertEqual(self.palm.hp, 0)
        self.assert_one_ground()
        paid = self.store.item(row['uniq'])
        self.finish(saved)
        self.rc.kill(self.palm, self.f)
        self.assertEqual(self.store.item(row['uniq']), paid)
        self.assert_one_ground()

    async def test_native_cost_failure_before_kill_cannot_leave_a_palm_unfinalizable(self):
        for kind in ('gun', 'blade'):
            with self.subTest(kind=kind):
                if not self.palm.alive:
                    self.case.reset_cycle()
                self.f.recovery_until = 0
                row = self.weapon(kind)
                self.palm.hp = 1
                before = self.case.resource_count()
                self.attack(row)
                original = self.store.update_item
                def fail_cost(uniq, **changes):
                    if uniq == row['uniq'] and 'brk' in changes:
                        raise RuntimeError('native cost before kill')
                    return original(uniq, **changes)
                with patch.object(self.store, 'update_item', side_effect=fail_cost):
                    with self.assertRaisesRegex(RuntimeError, 'native cost before kill'):
                        self.finish()
                self.assertEqual(self.palm.hp, 0)
                self.assertTrue(self.palm.alive)
                self.assertEqual(self.palm._eden_native_before_hit[0], 1)
                self.assertEqual(self.case.resource_count(), before)
                self.f.recovery_until = 0
                self.attack(self.store.item(row['uniq']))
                self.finish()
                self.assertFalse(self.palm.alive)
                self.assertEqual(self.case.resource_count(), before + 1)
                self.assertIsNone(self.palm._eden_native_before_hit)


if __name__ == '__main__':
    run_cases(EdenNativeWeaponTests)
