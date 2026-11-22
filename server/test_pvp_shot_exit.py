"""Paid PvP shots engage in range; only actual hits start the exit timer."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_release_battle as fixtures
import combat
import eden
import inventory
import mobs
import progression
import rooms
from testkit import run_cases


class PvpShotExit(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.a, self.b, self.viewer = self.case.players
        self.store, self.room, self.rc = self.case.store, self.case.room, self.case.rc
        self.a.pos, self.b.pos, self.viewer.pos = 40, 50, 90
        self.gun = self.case.loaded_gun(self.a)
        self.weapon = combat.Weapon(1, 10, 10, 0, 10, 10, 1, 0, 0,
                                     progression.SHOOTING, 2)
        self.clear()

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def clear(self):
        for seat in self.case.players:
            seat.writer.frames.clear()

    def fire(self, t=100, *, weapon=None, offset=100, target=None):
        with self.case.at(t), patch.object(combat, 'bullet_offset', return_value=offset):
            self.a.combat.fire_now(self.gun['uniq'], target or self.b.combat, None,
                                   weapon or self.weapon, 5, 1)

    def flags(self, seat):
        return [p for name, p in seat.writer.frames if name == 'lch' and 'exit_lock' in p]

    def assert_no_intent_lock(self):
        for seat in (self.a, self.b):
            self.assertEqual(self.flags(seat), [])
            self.assertEqual(seat.combat.last_hit, -1e9)
            self.assertFalse(seat.combat.duels)

    async def test_paid_miss_engages_both_players_without_damage_or_exit_timer(self):
        before = [seat.char.vitals() for seat in self.case.players]
        self.fire()
        self.assertEqual([seat.char.vitals() for seat in self.case.players], before)
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 7)
        self.assertEqual(self.a.combat.ap, 195)
        for seat in (self.a, self.b):
            self.assertEqual(self.flags(seat), [])
            with self.case.at(100):
                self.assertEqual(seat.combat.exit_timer_left(), 0)
                self.assertFalse(seat.combat.in_combat())
                self.assertFalse(seat.combat.refuse_leave())
            self.assertEqual(seat.combat.last_hit, -1e9)
            self.assertFalse(any(name in ('faHit', 'caHit') for name, _ in seat.writer.frames))
        self.assertIn(self.b.combat, self.a.combat.duels)
        self.assertTrue(self.rc.hostilities(100))
        self.assertEqual(self.flags(self.viewer), [])
        self.assertEqual(self.viewer.combat.last_hit, -1e9)
        self.assertFalse(self.viewer.combat.duels)

    async def test_hard_cover_blocks_damage_but_not_in_range_pvp_intent(self):
        for cell in (43, 45, 47):
            with self.subTest(obstacle=cell):
                self.room.loc.obstacles = {cell}
                self.clear()
                before = self.b.char.vitals()
                self.fire(100 + cell)
                self.assertEqual(self.b.char.vitals(), before)
                self.assertTrue(any(name == 'faWall' for name, _ in self.a.writer.frames))
                self.assertFalse(any(name == 'faHit' for name, _ in self.a.writer.frames))
                self.assertEqual(self.a.combat.duels[self.b.combat], 100 + cell)
                self.assertEqual(self.b.combat.duels[self.a.combat], 100 + cell)
                self.assertEqual((self.a.combat.last_hit, self.b.combat.last_hit), (-1e9, -1e9))
                self.assertEqual(self.flags(self.a) + self.flags(self.b), [])
                self.assertEqual(self.flags(self.viewer), [])

    async def test_exact_range_is_included_and_epsilon_outside_does_not_engage(self):
        distance = mobs.hex_distance(self.a.pos, self.b.pos, self.room.loc.width)
        self.assertEqual(distance, 10)
        self.fire(weapon=self.weapon._replace(max_range=distance - 1e-6))
        self.assert_no_intent_lock()
        self.clear()
        self.fire(101, weapon=self.weapon._replace(max_range=distance))
        for seat in (self.a, self.b):
            self.assertEqual(self.flags(seat), [])
            self.assertEqual(seat.combat.last_hit, -1e9)
        self.assertEqual(self.a.combat.duels[self.b.combat], 101)

    async def test_only_actual_hit_starts_fifteen_seconds_and_misses_do_not_refresh_it(self):
        self.fire(offset=0)
        self.assertEqual((self.a.combat.last_hit, self.b.combat.last_hit), (100, 100))
        self.clear()
        self.fire(110)
        for seat in (self.a, self.b):
            self.assertEqual(self.flags(seat), [])
            self.assertEqual(seat.combat.last_hit, 100)
            with self.case.at(110):
                self.assertEqual(seat.combat.exit_timer_left(), 5)
            with self.case.at(114.999):
                self.assertTrue(seat.combat.refuse_leave())
            self.assertEqual([p['res'] for name, p in seat.writer.frames if name == 'cmdAck'], [39])
            with self.case.at(115):
                self.assertFalse(seat.combat.in_combat())
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 6)
        self.fire(116, offset=0)
        for seat in (self.a, self.b):
            self.assertEqual(seat.combat.last_hit, 116)
            with self.case.at(130.999):
                self.assertTrue(seat.combat.in_combat())
            with self.case.at(131):
                self.assertFalse(seat.combat.in_combat())

    async def test_invalid_or_empty_completion_cannot_refresh_an_existing_lock(self):
        self.fire(offset=0)
        original = self.store.item(self.gun['uniq'])
        for change in (dict(slot=inventory.BAG), dict(brk=0), dict(ammo_count=0)):
            self.store.update_item(self.gun['uniq'], slot=inventory.PRIMARY,
                                   brk=original['brk'], ammo_count=original['ammo_count'])
            self.store.update_item(self.gun['uniq'], **change)
            self.clear()
            self.fire(110)
            self.assertEqual((self.a.combat.last_hit, self.b.combat.last_hit), (100, 100))
            self.assertEqual(self.a.combat.duels[self.b.combat], 100)
            self.assertEqual(self.flags(self.a) + self.flags(self.b), [])
        self.store.update_item(self.gun['uniq'], ammo_count=7)
        self.a.combat.ap = 0
        self.clear()
        self.fire(111)
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 7)
        self.assertEqual((self.a.combat.last_hit, self.b.combat.last_hit), (100, 100))
        self.assertEqual(self.flags(self.a) + self.flags(self.b), [])

    async def test_rejected_request_and_cancelled_aim_never_create_lock_or_spend_round(self):
        params = dict(obj=inventory.oid_of(self.gun), target='1%08x' % self.b.pid)
        self.a.combat.ap = 0
        with self.case.at(100):
            self.a.combat.use_fire(params)
        self.assert_no_intent_lock()
        self.assertIsNone(self.a.combat.aim)
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 8)
        self.a.combat.ap = 200
        with self.case.at(101):
            self.a.combat.use_fire(params)
            timer = self.a.combat.aim
            callback, args = timer._callback, timer._args
            self.a.combat.cancel_pending()
            callback(*args)
        self.assert_no_intent_lock()
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 8)

    async def test_party_or_clan_practice_never_creates_intent_lock(self):
        self.a.party = lambda: NS(members={self.a.char_id, self.b.char_id})
        self.fire()
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 8)
        self.assert_no_intent_lock()
        self.a.party = lambda: None
        clan = self.store.clan_create(self.a.char_id, 'Practice', 'practice', '',
                                       (self.a.char_id, 1000000, 0))
        self.assertTrue(self.store.clan_member_add(self.b.char_id, clan, 0, ''))
        self.clear()
        self.fire(101)
        self.assertEqual(self.store.item(self.gun['uniq'])['ammo_count'], 7)
        self.assert_no_intent_lock()

    async def test_eden_peace_and_absent_target_do_not_create_intent_lock(self):
        self.room.loc.id, self.room.loc.pvp = eden.CENTER, False
        self.room.loc.obstacles = {45}
        self.fire()
        self.assert_no_intent_lock()
        self.room.loc.id, self.room.loc.pvp = 100, True
        self.room.players.pop(self.b)
        self.clear()
        self.fire(101)
        self.assert_no_intent_lock()

    async def test_native_war_frame_without_timer_and_first_shot_ap_policy_is_unchanged(self):
        self.room.ws = False
        self.fire()
        for seat in (self.a, self.b):
            frames = seat.writer.frames
            self.assertEqual([p['ws'] for name, p in frames if name == 'lch' and 'ws' in p], [1])
            self.assertEqual(seat.combat.last_hit, -1e9)
            self.assertEqual(self.flags(seat), [])
        self.assertTrue(self.room.ws)
        self.assertIn(self.b.combat, self.a.combat.duels)
        self.assertEqual(self.a.combat.ap, self.a.combat.ap_max)
        self.assertEqual(self.flags(self.viewer), [])

    async def test_actual_hit_uses_native_hit_countdown_and_death_cannot_reopen_duel(self):
        self.b.char.hp = 1
        self.b.combat.drop_on_death = lambda: None
        self.a.combat.pvp_kill = lambda _victim: None
        self.fire(weapon=self.weapon._replace(dmin=10000, dmax=10000), offset=0)
        self.assertTrue(self.b.combat.dead)
        self.assertFalse(self.a.combat.duels or self.b.combat.duels)
        self.assertEqual(self.flags(self.a) + self.flags(self.b), [])
        self.clear()
        self.fire(102)
        self.assertFalse(self.a.combat.duels or self.b.combat.duels)
        self.assertEqual(self.flags(self.a) + self.flags(self.b), [])
        with self.case.at(102):
            self.assertFalse(self.a.combat.in_combat())

    async def test_pve_wall_still_prevents_aggro_and_clear_miss_still_provokes(self):
        mob = mobs.Mob(150, 258, self.b.pos)
        self.rc.mobs[mob.eid] = mob
        self.room.npcs[mob.eid] = rooms.NPC(mob.cell, mob.type_id, 2)
        self.room.loc.obstacles = {45}
        self.fire(target=mob)
        self.assertIsNone(mob.target)
        self.assertEqual(self.flags(self.a), [])
        self.assertEqual(self.a.combat.last_hit, -1e9)
        self.room.loc.obstacles = set()
        self.clear()
        self.fire(102, target=mob)
        self.assertIs(mob.target, self.a.combat)
        self.assertEqual(self.flags(self.a), [])
        self.assertEqual(self.a.combat.last_hit, -1e9)


if __name__ == '__main__':
    run_cases(PvpShotExit)
