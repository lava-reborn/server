"""Scheduled outpost subboss: one four-G bag per window, including restarts."""
import asyncio
from datetime import datetime
import unittest
from unittest.mock import patch

import accounts
import bosses
import combat
import items
import mobs
import rooms
import world
from testkit import run_cases

CAPTAIN, OUTPOST, INGOT = 1035, 168, 7620


class OutpostCaptain(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = accounts.Store(':memory:')
        self.now = datetime(2026, 11, 27, 17, 59, 59, tzinfo=bosses.ZONE).timestamp()
        self.active = []
        for active in (patch.object(bosses,'HOURS',[18*60,20*60]),
                       patch.object(bosses,'clock',side_effect=lambda:self.now),
                       patch.object(combat,'CORPSE_DELAY',.01),
                       patch.object(combat,'RESPAWN_DELAY',.01)):
            active.start()
            self.addCleanup(active.stop)

    async def asyncTearDown(self):
        for rc in self.active:
            for mob in rc.mobs.values():
                for timer in (mob.aim, getattr(mob,'respawn_timer',None)):
                    if timer is not None:
                        timer.cancel()
            for bag in rc.loot.values():
                if bag.expiry is not None:
                    bag.expiry.cancel()
        self.store.close()

    def room(self):
        room = rooms.Room(world.location(OUTPOST),rooms.IdAllocator(),world.mob_types())
        rc = combat.RoomCombat(room,self.store)
        self.active.append(rc)
        rc.keep_hours()
        captain = next(m for m in rc.mobs.values() if m.type_id==CAPTAIN)
        return room,rc,captain

    def gold(self):
        return self.store.db.execute('SELECT COALESCE(SUM(count),0) FROM items WHERE type_id=?',(INGOT,)).fetchone()[0]

    async def test_captain_arrives_with_bosses_and_leaves_when_the_window_closes(self):
        room,rc,captain = self.room()
        self.assertTrue(captain.away)
        self.assertNotIn(captain.eid,room.npcs)
        self.now += 1
        rc.keep_hours()
        self.assertFalse(captain.away)
        self.assertTrue(captain.alive)
        self.assertIn(captain.eid,room.npcs)
        sherhan=next(m for m in rc.bosses if m.type_id==8620)
        self.assertEqual(captain.slot,sherhan.slot)
        self.assertEqual(captain.stats.level,18)
        self.assertEqual(len([m for m in rc.bosses if m.type_id==CAPTAIN]),1)
        self.assertNotIn(1024,{m.type_id for m in rc.bosses})
        self.now += 3600
        rc.keep_hours()
        self.assertTrue(captain.away)
        self.assertNotIn(captain.eid,room.npcs)

    async def test_kill_and_room_restart_cannot_repeat_the_four_gold_reward(self):
        self.now += 1
        room,rc,captain = self.room()
        rc.kill(captain,None)
        await asyncio.sleep(.04)
        self.assertEqual(self.gold(),4)
        self.assertTrue(captain.away)
        rc.keep_hours()
        self.assertNotIn(captain.eid,room.npcs)
        restarted,rc2,again = self.room()
        self.assertTrue(again.away)
        self.assertNotIn(again.eid,restarted.npcs)
        self.assertEqual(self.gold(),4)
        self.now += 7200
        rc2.keep_hours()
        self.assertTrue(again.alive)
        self.assertFalse(again.away)
        rc2.kill(again,None)
        await asyncio.sleep(.04)
        self.assertEqual(self.gold(),8)

    async def test_disabled_boss_hours_and_scanner_cannot_multiply_gold(self):
        _room,rc,captain = self.room()
        for multiplier in (1,3,20):
            captain.loot_multiplier=multiplier
            captain.gold_loot_multiplier=multiplier
            captain.scanner_multiplier=multiplier
            self.assertEqual(sum(row['count'] for row in rc.drop_loot(captain)
                                 if row['type_id']==INGOT),4)
        with patch.object(bosses,'HOURS',[]):
            self.assertFalse(any(row['type_id'] in items.GOLD_INGOTS for row in rc.drop_loot(captain)))
        self.assertIsNone(bosses.blueprint_for(OUTPOST,CAPTAIN))
        self.assertTrue(bosses.uses_camp_recovery(OUTPOST,CAPTAIN))

    async def test_subboss_is_only_at_outpost_and_clear_of_existing_spawns(self):
        locations = [(loc,row) for loc,rows in world.placements().items()
                     for row in rows if row['type']==CAPTAIN]
        self.assertEqual(len(locations),1)
        self.assertEqual(locations[0][0],OUTPOST)
        loc = world.location(OUTPOST)
        x,y = locations[0][1]['cell']
        self.assertNotIn(y*loc.width+x,loc.obstacles | {c for c,_ in loc.spawns})
        self.assertEqual(rooms.placement_problems(world.mob_types(), {OUTPOST:[locations[0][1]]}),[])


if __name__ == '__main__':
    run_cases(OutpostCaptain)
