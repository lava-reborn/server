"""Marked Magrib cells intercept without creating extra actors or rooms."""
import asyncio, unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import boundary_world as bw
import encounters as e
import rooms, world, combat
from testkit import run_cases


class Walker:
    def __init__(self, vehicle=None):
        self.char_id=70; self.closed=False; self.on_map=True; self.loc=None
        self.gx=5990; self.gy=1750; self.leg=object(); self.vehicle=vehicle
        self.nick='patrol-test'; self.meetings=[]
    def skill_level(self): return 19
    def transport_now(self): return self.vehicle
    def meet(self, loc, pos, x, y):
        self.loc=NS(id=loc); self.on_map=False; self.gx=x; self.gy=y
        self.meetings.append((loc,pos,x,y))


class BoundaryEncounters(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.key='5990,1750'
        self.record=dict(id=world.pack(5990,1750),template=6,spawns=[(1300,98)],allowed_exits=['N','S'],boundary=True)
        self.doc=dict(version=1,cells={self.key:self.record},blocked=[],regions={})
        self.patcher=patch.object(bw,'manifest',return_value=self.doc);self.patcher.start()
        for f in (bw.by_id,bw.blocked_cells,bw.regions):f.cache_clear()
    def tearDown(self):
        self.patcher.stop()
        for f in (bw.by_id,bw.blocked_cells,bw.regions):f.cache_clear()
    async def test_only_the_marked_cell_adds_level19_interception(self):
        with patch.object(e,'bands',return_value=[]),patch.object(e,'near_town',return_value=False):
            self.assertEqual(e.band_at(5990.5,1750.5).types,(98,))
            for x,y in ((5989,1750),(5991,1750),(5990,1749),(5990,1751)):
                self.assertIsNone(e.band_at(x+.5,y+.5))
            self.record['spawns']=[(1300,130)]
            self.assertIsNone(e.band_at(5990.5,1750.5))
    async def test_isolated_regions_and_blocked_cells_do_not_intercept(self):
        with patch.object(e,'bands',return_value=[]),patch.object(world,'in_noob_valley',return_value=True):
            self.assertIsNone(e.band_at(5990,1750))
        with patch.object(e,'bands',return_value=[]),patch.object(e.eden_map,'inside_cell',return_value=True):
            self.assertIsNone(e.band_at(5990,1750))
        self.doc['blocked']=[self.key];bw.blocked_cells.cache_clear()
        self.assertIsNone(e.band_at(5990,1750))
    async def test_vehicle_bonus_changes_the_roll_and_a_cell_is_rolled_once(self):
        band=e.Band(self.record['id'],(5990,1750),19,19,(98,))
        manager=e.Encounters(NS()); foot=Walker(); rider=Walker(7)
        with patch.object(e,'CHANCE',.03),patch.object(e,'GRACE',0),patch.object(e,'band_at',return_value=band), \
             patch.object(e,'crossings',return_value=[(100,(5990,1750))]), \
             patch.object(e.transport,'get',return_value={'aggro_mod':.5}), \
             patch.object(e.RNG,'random',return_value=.02) as roll:
            manager.arm(foot,5989.5,1750.5,5991.5,1750.5,1)
            self.assertIn(foot,manager.armed)
            manager.arm(rider,5989.5,1750.5,5991.5,1750.5,1)
            self.assertNotIn(rider,manager.armed)
            manager.arm(rider,5989.5,1750.5,5991.5,1750.5,1)
            self.assertEqual(roll.call_count,2)
            manager.disarm(foot)
    async def test_existing_patrol_is_reused_and_survives_leaving(self):
        loc=NS(id=self.record['id']);npc=rooms.NPC(1300,98,world.MOB)
        room=NS(loc=loc,npcs={100:npc},combat=None,players={})
        manager=e.Encounters(NS(get=lambda key:room,rooms={loc.id:room}))
        sess=Walker();band=e.Band(loc.id,(5990,1750),19,19,(98,))
        with patch.object(world,'location',return_value=loc),patch.object(e,'arrival_cell',return_value=20):
            self.assertIs(manager.start(sess,(5990,1750),band),room)
        self.assertEqual(room.npcs,{100:npc});self.assertFalse(hasattr(room,'ambush'))
        self.assertEqual(manager.room_key(sess),loc.id)
        self.assertEqual(room.patrol_interceptions,{sess.char_id})
        sess.on_map=True;manager.left(sess)
        self.assertEqual(room.npcs,{100:npc});self.assertIn(loc.id,manager.rooms.rooms)
        self.assertEqual(room.patrol_interceptions,set());self.assertNotIn(sess,manager.stationary)
    async def test_defeated_patrol_cannot_intercept_or_respawn_by_interception(self):
        loc=NS(id=self.record['id']);dead=NS(type_id=98,alive=False,cell=1300)
        room=NS(loc=loc,npcs={100:rooms.NPC(1300,98,0)},combat=NS(mobs={100:dead}))
        manager=e.Encounters(NS(get=lambda key:room,rooms={loc.id:room}));sess=Walker()
        with patch.object(world,'location',return_value=loc):
            self.assertIsNone(manager.start_patrol(sess,(5990,1750),self.record))
        self.assertFalse(sess.meetings);self.assertNotIn(sess,manager.met)
    async def test_only_magrib_attacks_the_intercepted_player(self):
        sess=Walker();fighter=NS(sess=sess,eid=1,dead=False,interception=None,preparing=lambda:False)
        guard=NS(type_id=98,alive=True,target=None,stats=NS(can_attack=True))
        animal=NS(type_id=130,alive=True,target=None,stats=NS(can_attack=True))
        rc=NS(room=NS(patrol_interceptions={70}),timer=object(),fighters=lambda:[],mobs={2:guard,3:animal},aggro=lambda m,f:attacks.append(m))
        attacks=[];combat.RoomCombat.player_entered(rc,fighter)
        self.assertEqual(attacks,[guard])


if __name__=='__main__':run_cases(BoundaryEncounters)
