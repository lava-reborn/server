"""Three-player movement, death, loot, membership and decoding regressions."""
import asyncio
import logging
import os
from pathlib import Path
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
import mobs
import movement
import progression
import quests
import rooms
import server
import world
from protocol import decode


class Writer:
    def __init__(self):
        self.frames = []
    def write(self, value):
        self.frames.append(decode(value[:-1]))
    def close(self):
        pass


class BattleFixes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = accounts.Store(':memory:')
        self.patch = patch.object(server, 'STORE', self.store)
        self.patch.start()
        self.loc = NS(id=100, title='Test field', file='test.xml', width=20, height=20,
                      obstacles=set(), pvp=True, war=True, ours=False)
        self.room = rooms.Room.__new__(rooms.Room)
        self.room.loc, self.room.key = self.loc, 100
        self.room.npcs, self.room.players = {}, {}
        self.room.ws, self.room.escorts = True, []
        self.rc = self.room.combat = combat.RoomCombat(self.room, self.store)
        self.rc.keep_hours = lambda: None
        self.clock = movement.get(self.room)
        self.clock.schedule = lambda: None
        self.players = []
        for i, cell in enumerate((0, 40, 80)):
            aid, _ = self.store.register('fix-%d' % i, 'local-test')
            cid, _ = self.store.create_character(aid, 'Tester%d' % i, 0, '1')
            seat = server.Session(Writer(), 'local')
            seat.char_id = cid
            seat.active = dict(self.store.character(cid))
            seat.char = progression.Character.load(self.store, cid)
            seat.char.set_skill(progression.SHOOTING, 17)
            seat.char.set_spec(3, 3)
            seat.char.afro = 1000000
            seat.char.save(self.store)
            seat.loc, seat.room, seat.pos = self.loc, self.room, cell
            seat.gx, seat.gy, seat.on_map = 6270, 1832, False
            seat.arm_passage = lambda n: None
            seat.combat.amax_sent = 200
            seat.combat.ap = 200
            self.room.players[seat] = True
            self.players.append(seat)

    async def asyncTearDown(self):
        for seat in self.players:
            seat.combat.cancel_timers()
        if self.clock.timer:
            self.clock.timer.cancel()
        self.patch.stop()
        self.store.close()

    def at(self, value):
        return patch.object(asyncio.get_running_loop(), 'time', return_value=value)

    def move(self, seat, path, t=100):
        with self.at(t):
            seat.move_in_location(dict(path=path))

    def enter_loaded_player(self, seat, cell):
        self.room.leave(seat)
        seat.pos = cell
        seat.resume_loading = False
        seat.enter_room = lambda: self.room.enter(seat)
        seat.save_place = lambda: None
        seat.writer.frames.clear()
        with patch.object(server.ROOMS, 'get', return_value=self.room), \
                patch.object(self.room, 'snapshot_for'), \
                patch.object(server.CLANS, 'entered'):
            seat.cmd_lenter(dict(accept=1))
        own = next(p for n, p in seat.writer.frames if n == 'lenter')
        self.assertEqual(own['pos'], seat.pos)
        return seat.pos

    async def test_loaded_entry_avoids_player_and_publishes_same_cell(self):
        a, b, viewer = self.players
        viewer.writer.frames.clear()
        cell = self.enter_loaded_player(b, a.pos)
        self.assertNotEqual(cell, a.pos)
        placed = next(p for n, p in viewer.writer.frames
                      if n == 'lch' and p.get('newUser') == b.pid)
        self.assertEqual(placed['pos'], cell)

    async def test_loaded_entry_avoids_live_mob_and_reserved_next_hex(self):
        a, b, _ = self.players
        mob = mobs.Mob(150, 1, 100)
        self.rc.mobs[mob.eid] = mob
        self.room.npcs[mob.eid] = rooms.NPC(100, mob.type_id, 2)
        with self.at(100):
            self.clock.accept(mob, [100, 101, 102], 100)
            first = self.enter_loaded_player(a, 100)
            second = self.enter_loaded_player(b, 101)
        self.assertNotIn(first, (100, 101))
        self.assertNotIn(second, (100, 101, first))

    async def test_loaded_entry_can_spawn_when_entry_and_all_neighbours_are_taken(self):
        a, b, c = self.players
        entry = 200
        taken = {entry, *progression.hex_neighbours(entry, self.loc.width, self.loc.height)}
        for i, cell in enumerate(taken):
            self.room.npcs[500+i] = rooms.NPC(cell, 1, world.TEACHER)
        chosen = self.enter_loaded_player(a, entry)
        self.assertNotIn(chosen, taken)
        self.assertNotIn(chosen, (b.pos, c.pos))
        self.assertIn(a, self.room.players)

    async def test_concurrent_loaded_entries_reserve_distinct_cells(self):
        for seat in self.players:
            self.room.leave(seat)
        # Commands are synchronous on the room event loop: each arrival is
        # registered before the next loaded client can choose its own cell.
        results = await asyncio.gather(*(self.loaded_entry(seat, 200)
                                        for seat in self.players))
        self.assertEqual(len(set(results)), len(self.players))
        self.assertEqual(results[0], 200)

    async def loaded_entry(self, seat, cell):
        return self.enter_loaded_player(seat, cell)

    async def test_three_players_cross_without_overlapping_or_extra_step_packets(self):
        a, b, c = self.players
        self.move(a, list(range(10)), 100)
        self.move(b, [40, 41, 21, 1, 2, 3], 100)
        self.move(c, [80, 60, 40, 20, 0], 100)
        before = sum(len(s.writer.frames) for s in self.players)
        for i in range(1, 61):
            with self.at(100 + i / 20):
                cells = [s.live_cell() for s in self.players]
                self.assertEqual(len(set(cells)), 3, (i, cells))
        after = sum(len(s.writer.frames) for s in self.players)
        self.assertLessEqual(after - before, 18)  # Stops only, no stream of per-step frames.

    async def test_delayed_collision_tick_charges_only_completed_steps(self):
        a,b,_=self.players
        self.move(a,[0,1,2,22,42])
        self.move(b,[40,41,21,22,23])
        with self.at(100.95):
            self.clock.advance()
        self.assertEqual(b.pos,21)
        self.assertIsNone(b.walk)
        self.assertEqual(b.combat.ap,198)

    async def test_head_on_swap_and_forged_single_hex_never_teleport(self):
        a, b, _ = self.players
        b.pos = 1
        self.move(a, [0, 1])
        self.move(b, [1, 0])
        self.assertEqual((a.pos, b.pos), (0, 1))
        self.move(a, [300])
        self.assertEqual(a.pos, 0)
        self.move(a, [100, 101, 102])
        self.assertEqual(a.pos, 0)

    async def test_invalid_route_stops_at_current_hex_for_all_viewers(self):
        a = self.players[0]
        self.move(a, list(range(10)))
        with self.at(100.45):
            a.move_in_location(dict(path=[2, 390]))
        self.assertEqual(a.pos, 2)
        self.assertIsNone(a.walk)
        own = [p for n,p in a.writer.frames if n == 'breakMv']
        self.assertEqual(own[-1]['pos'], 2)
        for viewer in self.players[1:]:
            stops = [p for n,p in viewer.writer.frames if n == 'actionCancel']
            self.assertEqual(stops[-1]['pos'], 2)

    async def test_joining_observer_gets_current_hex_and_remaining_route(self):
        a, observer, _ = self.players
        self.move(a, list(range(10)))
        observer.writer.frames.clear()
        with self.at(100.45):
            self.room.snapshot_for(observer)
        frames = observer.writer.frames
        placement = next(p for n,p in frames if n == 'lch' and p.get('newUser') == a.pid)
        route = next(p for n,p in frames if n == 'userMove' and p.get('id') == a.pid)
        self.assertEqual(placement['pos'], 2)
        self.assertEqual(route['path'], list(range(2,10)))
        self.assertEqual(route['step_ms'], 50)
        self.assertTrue(any(n == 'usrUp' and p.get('id') == a.pid and p['hcur'] == p['hmax'] for n,p in frames))

    async def test_joining_observer_gets_live_mob_position_and_route(self):
        mob = mobs.Mob(150, 1, 100)
        mob.walk = (list(range(100, 110)), 100)
        mob.cell = 109
        mob._motion = self.clock
        self.rc.mobs[mob.eid] = mob
        self.room.npcs[mob.eid] = rooms.NPC(109, mob.type_id, 2)
        with self.at(100):
            self.clock.accept(mob, mob.walk[0], 100)
        viewer = self.players[1]
        viewer.send_npc_info = lambda eid: None
        viewer.writer.frames.clear()
        with self.at(100.45):
            self.room.snapshot_for(viewer)
        frames = viewer.writer.frames
        placement = next(p for n,p in frames if n == 'lch' and p.get('newUser') == mob.eid)
        route = next(p for n,p in frames if n == 'userMove' and p.get('id') == mob.eid)
        self.assertEqual(placement['pos'],102)
        self.assertEqual(route['path'],list(range(102,110)))
        self.assertEqual(route['step_ms'],50)
        viewer.writer.frames.clear()
        with self.at(100.6):
            self.room.snapshot_for(viewer)
        frames = viewer.writer.frames
        placement = next(p for n,p in frames if n == 'lch' and p.get('newUser') == mob.eid)
        route = next(p for n,p in frames if n == 'userMove' and p.get('id') == mob.eid)
        self.assertEqual(placement['pos'],103)
        self.assertEqual(route['path'][0],placement['pos'])

    async def test_mob_death_at_edge_boundary_keeps_current_cell(self):
        mob = mobs.Mob(150, 1, 100)
        mob.walk = (list(range(100,110)),100)
        mob.cell = 109
        mob._motion = self.clock
        self.rc.mobs[mob.eid] = mob
        self.room.npcs[mob.eid] = rooms.NPC(109,mob.type_id,2)
        with self.at(100):
            self.clock.accept(mob,mob.walk[0],100)
        self.rc.quest_wants = lambda *args: frozenset()
        self.rc.settle_xp = lambda *args: None
        with self.at(100.6), patch.object(combat.holdings,'snapshot',return_value=None):
            self.rc.kill(mob,None)
        self.assertEqual(mob.cell,103)
        self.assertFalse(mob.alive)
        self.assertIsNone(mob.walk)
        for seat in self.players:
            stops=[p for n,p in seat.writer.frames if n=='actionCancel' and p.get('id')==mob.eid]
            self.assertEqual(stops[-1]['pos'],103)

    async def test_death_stops_every_observer_before_corpse_and_loot(self):
        a, b, c = self.players
        row = a.inv.create(2258, 10)
        dropped = []
        self.rc.add_to_bag = lambda cell, rows, **kw: dropped.append((cell, rows))
        self.move(a, list(range(10)))
        for s in self.players:
            s.writer.frames.clear()
        with self.at(100.45), patch.object(combat, 'death_losses', return_value=[(row, 10)]):
            a.combat.die(b.combat)
        self.assertEqual(a.pos, 2)
        self.assertIsNone(a.walk)
        self.assertEqual(dropped[0][0], 2)
        for s in self.players:
            frames = s.writer.frames
            stop = next(i for i,(n,p) in enumerate(frames) if n == 'actionCancel' and p.get('pos') == 2)
            dead = next(i for i,(n,p) in enumerate(frames) if n == 'lch' and 'dead' in p)
            self.assertLess(stop, dead)
        with self.at(110):
            self.assertEqual(a.live_cell(), 2)

    async def test_completed_route_is_stopped_before_death_for_delayed_viewer(self):
        a,b,_=self.players
        self.move(a,[0,1,2])
        with self.at(100.5):
            self.assertEqual(a.live_cell(),2)
            self.assertIsNone(a.walk)
            a.combat.die(b.combat)
        for viewer in self.players:
            frames=viewer.writer.frames
            stop=next(i for i,(n,p) in enumerate(frames) if n=='actionCancel' and p.get('pos')==2)
            death=next(i for i,(n,p) in enumerate(frames) if n=='lch' and 'dead' in p)
            self.assertLess(stop,death)

    async def test_loot_open_stops_running_and_transfer_rechecks_reach(self):
        a = self.players[0]
        self.rc.loot[3] = NS(uniqs=[])
        self.move(a, list(range(10)))
        with self.at(100.45):
            a.combat.open_loot(dict(target=3))
        self.assertIsNone(a.walk)
        self.assertEqual(a.pos, 2)
        a.pos = 30
        a.writer.frames.clear()
        self.assertTrue(a.combat.ss_upd(dict(s_status=3)))
        self.assertNotEqual(a.writer.frames[-1][1]['res'], 0)
        self.assertIsNone(a.combat.loot)

    async def test_room_uses_one_step_timer_and_departure_releases_claim(self):
        a,b,_=self.players
        with self.at(100):
            self.move(a,list(range(10)))
            movement.Motion.schedule(self.clock)
            first=self.clock.timer
            self.move(b,list(range(40,50)))
            movement.Motion.schedule(self.clock)
            self.assertFalse(first.cancelled())
            self.assertIs(self.clock.timer,first)
            self.assertAlmostEqual(self.clock.timer.when(),100.2)
            self.room.leave(a)
            self.assertNotIn(id(a),self.clock.walks)
            self.assertNotIn(1,self.clock.occupied())

    async def test_motion_timer_reschedules_earlier_deadline_and_cancels_when_empty(self):
        a=self.players[0]
        with self.at(100):
            self.clock.schedule=movement.Motion.schedule.__get__(self.clock)
            self.move(a,list(range(10)))
            first=self.clock.timer
            self.clock.forget(object())
            self.assertIs(self.clock.timer,first)
            self.clock.walks[id(a)].began=99.95
            self.clock.schedule()
            self.assertTrue(first.cancelled())
            self.assertAlmostEqual(self.clock.timer.when(),100.15)
            replacement=self.clock.timer
            self.clock.forget(a)
            self.assertTrue(replacement.cancelled())
            self.assertIsNone(self.clock.timer)

    async def test_weapon_switch_stops_route_without_charging_future_steps(self):
        a = self.players[0]
        self.move(a, list(range(10)))
        with self.at(100.45):
            a.combat.primary_changed()
        self.assertEqual(a.pos, 2)
        self.assertIsNone(a.walk)
        self.assertEqual(a.combat.ap, 198)

    def clan_pair(self):
        a,b,c=self.players
        clan=self.store.clan_create(a.char_id,'Same','same','',(a.char_id,1000000,0))
        self.store.clan_member_add(b.char_id,clan,0,'')
        b.pos=1
        self.room.ws=False
        return a,b,c,clan

    def loaded_gun(self,a):
        gun=a.inv.create(25566,slot=inventory.PRIMARY)
        ammo=items.params_of(25566)['comp_array'][0]
        self.store.update_item(gun['uniq'],ammo_count=8,ammo_type=ammo)
        return gun

    def finish_aim(self,a):
        timer=a.combat.aim
        callback,args,when=timer._callback,timer._args,timer.when()
        timer.cancel()
        with self.at(when):
            callback(*args)

    async def test_clan_fire_deals_damage_without_war_or_trophies_and_caches_membership(self):
        a,b,c,clan=self.clan_pair()
        self.assertTrue(a.combat.same_clan(b.combat))
        self.assertFalse(a.combat.allied(b.combat))
        with patch.object(self.store,'clan_member',wraps=self.store.clan_member) as read:
            for _ in range(200):
                self.assertTrue(a.combat.same_clan(b.combat))
            self.assertEqual(read.call_count,0)
        gun=self.loaded_gun(a)
        before=b.combat.vitals()['hcur']
        a.writer.frames.clear()
        with self.at(100):
            a.combat.use_fire(dict(obj=inventory.oid_of(gun),target='1%08x'%b.pid))
            self.assertIsNotNone(a.combat.aim)
            self.assertFalse(self.room.ws)
            self.assertFalse(self.rc.hostilities(100))
        result=([(None,[(b.combat,5,0,False)])],{b.combat:[5,0,1,b.combat.sp_now()]})
        with patch.object(self.rc,'resolve',return_value=result):
            self.finish_aim(a)
        self.assertEqual(b.combat.vitals()['hcur'],before-5)
        self.assertEqual(self.store.item(gun['uniq'])['ammo_count'],7)
        self.assertFalse(self.room.ws)
        self.assertFalse(a.combat.duels or b.combat.duels)
        self.assertEqual((a.combat.last_hit,b.combat.last_hit),(-1e9,-1e9))
        hits=[p for n,p in a.writer.frames if n=='faHit']
        self.assertEqual(hits[-1]['no_war'],1)
        import trophies
        self.assertIsNone(trophies.drop(a.combat,b.combat,combat.LOOT_OWNER,inventory.BAG))
        self.store.clan_member_remove(b.char_id,clan)
        self.assertFalse(a.combat.same_clan(b.combat))

    async def test_clan_melee_deals_damage_without_starting_room_war(self):
        a,b,_,_=self.clan_pair()
        before=b.combat.vitals()['hcur']
        with self.at(100),patch.object(combat,'roll',return_value=True):
            a.combat.use_fire(dict(obj='0',target='1%08x'%b.pid))
        self.assertLess(b.combat.vitals()['hcur'],before)
        self.assertFalse(self.room.ws)
        self.assertFalse(a.combat.duels)
        self.assertEqual(next(p for n,p in a.writer.frames if n=='caHit')['no_war'],1)

    async def test_party_prevents_direct_and_collateral_damage_even_between_clanmates(self):
        a,b,_,_=self.clan_pair()
        group=NS(members={a.char_id,b.char_id})
        a.party=lambda:group
        b.party=lambda:group
        gun=self.loaded_gun(a)
        for obj in (inventory.oid_of(gun),'0'):
            a.writer.frames.clear()
            with self.at(100):
                a.combat.use_fire(dict(obj=obj,target='1%08x'%b.pid))
            self.assertEqual(next(p['res'] for n,p in a.writer.frames if n=='cmdAck'),combat.RES_NO_PVP)
        self.assertEqual(self.store.item(gun['uniq'])['ammo_count'],8)
        weapon=NS(at_players=True)
        self.assertNotIn(b.pos,self.rc.bodies(a.combat,None,weapon))
        self.assertFalse(self.room.ws)

    async def test_party_joined_during_aim_cancels_shot_without_resources(self):
        a,b,_,_=self.clan_pair()
        gun=self.loaded_gun(a)
        with self.at(100):
            a.combat.use_fire(dict(obj=inventory.oid_of(gun),target='1%08x'%b.pid))
        a.party=lambda:NS(members={a.char_id,b.char_id})
        self.finish_aim(a)
        self.assertEqual(self.store.item(gun['uniq'])['ammo_count'],8)
        self.assertFalse(any(n=='faShot' for n,p in a.writer.frames))

    async def test_clan_hits_preserve_existing_war_and_do_not_refresh_exit_timer(self):
        a,b,c,_=self.clan_pair()
        with self.at(100):
            self.rc.after_hostile(a.combat,c.combat)
        self.assertTrue(self.room.ws)
        a.combat.last_hit=99
        with self.at(110):
            self.rc.hit_landed(a.combat,b.combat)
            self.rc.after_hostile(a.combat,b.combat)
        self.assertTrue(self.room.ws)
        self.assertEqual(a.combat.last_hit,99)
        self.assertIn(c.combat,a.combat.duels)
        self.assertNotIn(b.combat,a.combat.duels)

    async def test_clan_collateral_is_allowed_but_outsider_hit_starts_real_combat(self):
        a,b,c,_=self.clan_pair()
        self.assertIn(b.pos,self.rc.bodies(a.combat,None,NS(at_players=True)))
        with self.at(100):
            self.rc.hit_landed(a.combat,c.combat)
            self.rc.after_hostile(a.combat,c.combat)
        self.assertTrue(self.room.ws)
        self.assertIn(c.combat,a.combat.duels)

    async def test_decode_17_available_at_16_and_commits_one_reward(self):
        a = self.players[0]
        npc = 104
        self.room.npcs[npc] = rooms.NPC(a.pos, 796, server.world.COMMONER)
        a.char.set_skill(progression.SHOOTING,16)
        q = quests.get(10713)
        self.assertTrue(a.quest_available(q))
        a.char.set_skill(progression.SHOOTING,15)
        self.assertFalse(a.quest_available(q))
        a.char.set_skill(progression.SHOOTING,16)
        row = a.inv.create(2416)
        a.char.save(self.store)
        before = a.char.afro
        a.cmd_q_st(dict(mob=npc,q_idx=quests.given_by(796).index(10713)))
        held = next(x for x in self.store.quests(a.char_id) if x['type']==10713)
        a.cmd_q_co(dict(mob=npc,q_id=held['q_id'],obj_idx=0))
        self.assertIsNone(self.store.item(row['uniq']))
        self.assertEqual(a.char.afro, before-q.cost_afro)
        rewards = [r for r in a.inv.rows() if r['type_id'] in {x[0] for x in q.rew_random}]
        self.assertEqual(len(rewards),1)
        a.cmd_q_co(dict(mob=npc,q_id=held['q_id'],obj_idx=0))
        self.assertEqual(a.char.afro, before-q.cost_afro)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(BattleFixes)
