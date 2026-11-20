"""Shared plantation rooms retain the actual non-PvP combat boundaries."""
import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import test_release_battle as fixtures
import combat
import eden
import inventory
import items
import mobs
import movement
import progression
import rooms
import world
from testkit import run_cases


class EdenPvPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.store = self.case.store
        self.a, self.b, third = self.case.players
        self.case.room.players.pop(third)
        self.players = (self.a, self.b)
        self.created_rooms = []
        for seat in self.players:
            seat.eden_sentence = eden.assign(self.store, seat.char_id, 'test', 'Shared PvP boundary')
        self.tools = {}
        helmet = next(t for t, (_root, name) in items.catalogue().items()
                      if name == 'helm_Set_M_LVL_8_A_mod00')
        for seat in self.players:
            seat.inv.create(helmet, slot=inventory.HEAD)
            gun = self.case.loaded_gun(seat)
            tool = seat.inv.create(eden.CLEAVER)
            blade = seat.inv.create(6228)
            self.tools[seat] = (None, tool, blade, gun)

    async def asyncTearDown(self):
        for room in self.created_rooms:
            if room.combat and room.combat.timer:
                room.combat.timer.cancel()
            clock = movement.get(room)
            if clock.timer:
                clock.timer.cancel()
        await self.case.asyncTearDown()

    def place(self, loc_id):
        loc = world.location(loc_id)
        room = rooms.Room(loc, rooms.IdAllocator(), world.mob_types(), key=loc.id)
        room.combat = combat.RoomCombat(room, self.store)
        self.created_rooms.append(room)
        occupied = {entry.cell for entry in room.npcs.values()}
        pair = next((cell, other) for cell in range(loc.width * loc.height)
                    if cell not in loc.obstacles and cell not in occupied
                    for other in progression.hex_neighbours(cell, loc.width, loc.height)
                    if other not in loc.obstacles and other not in occupied
                    and combat.shot_wall(loc, cell, other) is None)
        for seat, cell in zip(self.players, pair):
            seat.combat.left()
            seat.loc, seat.room, seat.pos = loc, room, cell
            seat.gx, seat.gy = eden.target_cell(loc_id)
            seat.walk = None
            room.players[seat] = True
        self.room, self.rc = room, room.combat
        return room

    def equip(self, seat, row):
        for current in seat.inv.rows():
            if current['slot'] == inventory.PRIMARY:
                self.store.update_item(current['uniq'], slot=inventory.BAG)
        if row is not None:
            self.store.update_item(row['uniq'], slot=inventory.PRIMARY)

    def state(self):
        return [(s.combat.vitals(), s.combat.ap, s.inv.rows(),
                 dict(s.combat.duels), s.combat.last_hit) for s in self.players]

    def frames(self, seat):
        return seat.writer.frames

    def finish(self, timer):
        callback, args, when = timer._callback, timer._args, timer.when()
        timer.cancel()
        with self.case.at(when):
            callback(*args)

    async def test_direct_fist_tool_blade_and_firearm_never_change_player_resources(self):
        group = None
        clan = None
        for relation in ('outsider', 'same_clan', 'party'):
            if relation == 'same_clan':
                clan = self.store.clan_create(self.a.char_id, 'Eden', 'eden', '',
                                              (self.a.char_id, 1000000, 0))
                self.store.clan_member_add(self.b.char_id, clan, 0, '')
                self.assertTrue(self.a.combat.same_clan(self.b.combat))
            elif relation == 'party':
                group = NS(members={self.a.char_id, self.b.char_id})
            with patch.object(self.a, 'party', return_value=group), \
                    patch.object(self.b, 'party', return_value=group):
                for loc_id in sorted(eden.LOCATIONS):
                    self.place(loc_id)
                    self.assertFalse(self.a.combat.pvp_allowed())
                    for attacker, victim in (self.players, self.players[::-1]):
                        for row in self.tools[attacker]:
                            with self.subTest(relation=relation, loc=loc_id,
                                              attacker=attacker.char_id,
                                              item=None if row is None else row['type_id']):
                                self.equip(attacker, row)
                                before = self.state()
                                for seat in self.players:
                                    self.frames(seat).clear()
                                with self.case.at(100):
                                    attacker.cmd_ss_use(dict(type=inventory.USE_FIRE,
                                        obj='0' if row is None else inventory.oid_of(row),
                                        target='1%08x' % victim.pid))
                                answers = [p['res'] for cmd, p in self.frames(attacker)
                                           if cmd == 'cmdAck']
                                self.assertEqual(len(answers), 1)
                                self.assertNotEqual(answers[0], 0)
                                self.assertEqual(self.state(), before)
                                self.assertIsNone(attacker.combat.aim)
                                self.assertIsNone(attacker.combat.strike)
                                self.assertFalse(any(cmd in ('faAim', 'faShot', 'faHit', 'caHit')
                                                     for s in self.players for cmd, _ in self.frames(s)))

    async def test_hex_fire_cannot_hit_players_even_on_their_own_hex(self):
        for loc_id in sorted(eden.LOCATIONS):
            self.place(loc_id)
            gun = self.tools[self.a][-1]
            self.equip(self.a, gun)
            self.store.update_item(gun['uniq'], ammo_count=8)
            before = (self.b.combat.vitals(), self.b.inv.rows())
            for seat in self.players:
                self.frames(seat).clear()
            with self.case.at(100), patch.object(combat, 'bullet_offset', return_value=0):
                self.a.cmd_ss_use(dict(type=inventory.USE_FIRE, obj=inventory.oid_of(gun),
                                       target='0%08x' % self.b.pos))
            if self.a.combat.aim is not None:
                with patch.object(combat, 'bullet_offset', return_value=0):
                    self.finish(self.a.combat.aim)
                self.assertLess(self.store.item(gun['uniq'])['ammo_count'], 8)
                self.assertTrue(any(cmd == 'faShot' for cmd, _ in self.frames(self.b)))
            else:
                # The foreman's center is entirely peaceful, including ground shots.
                self.assertFalse(self.room.loc.war)
                self.assertEqual(self.store.item(gun['uniq'])['ammo_count'], 8)
            self.assertEqual((self.b.combat.vitals(), self.b.inv.rows()), before)
            self.assertFalse(self.a.combat.duels or self.b.combat.duels)
            self.assertFalse(any(cmd == 'faHit' for s in self.players for cmd, _ in self.frames(s)))

    async def test_old_firearm_and_blade_callbacks_are_inert_after_room_departure(self):
        for kind in ('gun', 'blade'):
            # Accept a real attack in a PvP room, then admit both players to Eden.
            self.place(264)
            old_loc = copy.copy(self.room.loc)
            old_loc.pvp = True
            self.room.loc = self.a.loc = self.b.loc = old_loc
            row = self.tools[self.a][-1 if kind == 'gun' else 2]
            self.equip(self.a, row)
            with self.case.at(100):
                self.a.cmd_ss_use(dict(type=inventory.USE_FIRE, obj=inventory.oid_of(row),
                                       target='1%08x' % self.b.pid))
            timer = self.a.combat.aim if kind == 'gun' else self.a.combat.strike
            self.assertIsNotNone(timer)
            callback, args = timer._callback, timer._args
            self.a.leave_room()
            self.b.leave_room()
            self.assertTrue(timer.cancelled())
            self.place(264)
            before = self.state()
            for seat in self.players:
                self.frames(seat).clear()
            with self.case.at(110):
                callback(*args)
            self.assertEqual(self.state(), before)
            self.assertFalse(any(cmd in ('faShot', 'faHit', 'caHit')
                                 for s in self.players for cmd, _ in self.frames(s)))

    async def test_palm_work_does_not_provoke_retaliation_against_either_player(self):
        for loc_id in (264, 265, 266):
            self.place(loc_id)
            palm = next(m for m in self.rc.mobs.values() if m.type_id in eden.PALMS)
            self.a.pos = next(c for c in progression.hex_neighbours(
                palm.cell, self.room.loc.width, self.room.loc.height)
                              if c not in self.room.loc.obstacles and c != self.b.pos)
            tool = self.tools[self.a][1]
            self.equip(self.a, tool)
            before = [s.combat.vitals() for s in self.players]
            with self.case.at(100):
                self.a.cmd_ss_use(dict(type=inventory.USE_FIRE, obj=inventory.oid_of(tool),
                                       target='1%08x' % palm.eid))
            self.assertIsNotNone(self.a.combat.strike)
            self.finish(self.a.combat.strike)
            with self.case.at(110):
                self.rc.after_hostile(self.a.combat, palm)
                for mob in self.rc.mobs.values():
                    mob.think(self.rc, 110)
                    self.assertFalse(mob.stats.can_attack)
                    self.assertIsNone(mob.target)
            self.assertEqual([s.combat.vitals() for s in self.players], before)


if __name__ == '__main__':
    run_cases(EdenPvPTests)
