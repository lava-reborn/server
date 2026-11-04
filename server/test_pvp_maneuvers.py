"""Two bounded PvP maneuvers: actual server handlers, virtual time, no Flash."""
from pathlib import Path
import asyncio
import json
import math
import os
import statistics
import sys
import time
import unittest
from unittest.mock import patch

os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_release_battle as battle_fixtures
import battle_medicine
import combat
import inventory
import items
import mobs
import rooms
from protocol import decode
from testkit import run_cases

REPORT_DIR = os.environ.get('LAVA_PVP_REPORT_DIR')
OUT = Path(REPORT_DIR) if REPORT_DIR else None
if OUT is not None:
    OUT.mkdir(parents=True, exist_ok=True)



class Receiver:
    """Position projection of received commands; not a Flash renderer."""
    def __init__(self, owner):
        self.owner=owner
        self.routes={}
        self.health={}
        self.frames=[]

    def close(self):
        pass

    def write(self,data):
        name,p=decode(data[:-1])
        now=asyncio.get_running_loop().time()
        self.frames.append((name,p))
        eid=p.get('id') or self.owner.pid
        if name=='userMove' and 'path' in p:
            self.routes[eid]=(list(p['path']),now-p.get('step_ms',0)/1000)
        elif name in ('actionCancel','breakMv') and 'pos' in p:
            self.routes[eid]=([p['pos']],now)
        elif name=='lch' and 'newUser' in p:
            self.routes[p['newUser']]=([p['pos']],now)
        elif name=='usrUp' and 'hcur' in p:
            self.health[eid]=(p['hcur'],p['scur'])
        elif name=='heal':
            target=p.get('target') or self.owner.pid
            self.health[target]=(p['hp'],p['sp'])

    def cell(self,eid,now):
        cells,began=self.routes[eid]
        index=min(len(cells)-1,max(0,math.floor((now-began+1e-9)/.2)))
        return cells[index]


class PvPManeuvers(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case=battle_fixtures.BattleFixes()
        await self.case.asyncSetUp()
        self.a,self.b,self.third=self.case.players
        self.case.room.players.pop(self.third)
        self.players=[self.a,self.b]
        self.case.loc.obstacles={8+8*20,9+8*20,8+9*20,9+9*20}
        self.steps={s.pid:0 for s in self.players}
        self.command_us=[]
        self.tick_us=[]
        self.completed=[]
        original=self.case.clock.advance
        def advance(t=None):
            before=[(state,state.index) for state in self.case.clock.walks.values()]
            original(t)
            for state,index in before:
                for i in range(index+1,state.index+1):
                    first,second=state.cells[i-1:i+1]
                    self.assertTrue(mobs.adjacent(first,second,self.case.loc),
                                    ('non-adjacent completed step',first,second))
                    self.assertNotIn(second,self.case.loc.obstacles)
                    self.steps[state.actor.pid]+=1
                    self.completed.append((state.actor.pid,first,second))
        self.case.clock.advance=advance
        self.guns={}
        self.meds={}
        for s,cell in zip(self.players,[5+7*20,11+10*20]):
            s.pos=cell
            s.char.hp=s.char.hp_max-100
            s.char.sp=s.char.sp_max-40
            s.writer=Receiver(s)
            gun=s.inv.create(25566,slot=inventory.PRIMARY)
            self.case.store.update_item(gun['uniq'],ammo_count=8,
                                        ammo_type=items.params_of(25566)['comp_array'][0])
            self.guns[s.pid]=gun
            self.meds[s.pid]=[s.inv.create(6055) for _ in range(3)]
        self.shots={s.pid:0 for s in self.players}
        self.heals={s.pid:0 for s in self.players}
        self.goals={self.a.pid:[(5,5),(11,5),(12,10),(10,12),(5,11)],
                    self.b.pid:[(5,11),(10,12),(12,10),(11,5),(5,5)]}
        self.goal_index={s.pid:0 for s in self.players}
        with self.case.at(100):
            for s in self.players:
                self.case.room.broadcast(('lch',dict(newUser=s.pid,pos=s.pos,rtype=-1)))
                self.case.room.broadcast(('usrUp',rooms.player_health(s)))

    async def asyncTearDown(self):
        await self.case.asyncTearDown()

    def request(self,callback,*args):
        began=time.perf_counter_ns()
        result=callback(*args)
        self.command_us.append((time.perf_counter_ns()-began)/1000)
        return result

    def route(self,s):
        remaining=45-self.steps[s.pid]
        if remaining<=0:
            return
        here=s.live_cell()
        prefix=[here]
        state=self.case.clock.walks.get(id(s))
        if state and state.index+1<len(state.cells):
            prefix.append(state.cells[state.index+1])
        points=self.goals[s.pid]
        goal=points[self.goal_index[s.pid]%len(points)]
        goal=goal[0]+goal[1]*20
        if mobs.hex_distance(here,goal,20)<=1:
            self.goal_index[s.pid]+=1
            goal=points[self.goal_index[s.pid]%len(points)]
            goal=goal[0]+goal[1]*20
        blocked=self.case.clock.occupied(s)
        blocked.discard(prefix[-1])
        tail=mobs.find_path(self.case.loc,prefix[-1],lambda c:c==goal,blocked,toward=goal)
        if tail:
            path=(prefix+tail[1:])[:remaining+1]
            if len(path)>1:
                self.request(s.move_in_location,dict(path=path))

    def finish_actions(self,now):
        due=[]
        for s in self.players:
            for field in ('aim','healing','strike'):
                handle=getattr(s.combat,field,None)
                if handle is not None and handle.when()<=now+1e-9:
                    due.append((handle.when(),s,field,handle))
        for _,s,field,handle in sorted(due,key=lambda x:x[0]):
            callback,args=handle._callback,handle._args
            handle.cancel()
            self.request(callback,*args)

    async def simulate(self,variant):
        combat.RNG.seed(178+variant)
        checks=0
        tick=0
        next_reroute={s.pid:100 for s in self.players}
        shot_marks=(6,15,25,35,45)
        heal_marks=(10,22,38)
        now=100
        with patch.object(combat.pace,'SCALE',1), patch.object(combat.log,'exception',side_effect=AssertionError('Combat resolver error')):
            while now<170:
                # Second run includes bounded late simulation ticks and
                # mid-edge reroutes/duplicate requests, not lost packets.
                delta=.275 if variant==2 and tick and tick%67==0 else .025
                now=round(now+delta,6)
                started=time.perf_counter_ns()
                with self.case.at(now):
                    self.case.clock.advance()
                    self.finish_actions(now)
                    for s,other in ((self.a,self.b),(self.b,self.a)):
                        f=s.combat
                        if f.aim is not None or f.healing is not None or combat.Fighter.recovering(f):
                            continue
                        done=self.steps[s.pid]
                        if self.shots[s.pid]<len(shot_marks) and done>=shot_marks[self.shots[s.pid]]:
                            before=len(s.writer.frames)
                            self.request(f.use_fire,dict(obj=inventory.oid_of(self.guns[s.pid]),target='1%08x'%other.pid))
                            ack=next(p for n,p in s.writer.frames[before:] if n=='cmdAck')
                            self.assertEqual(ack['res'],0,('attack refused',s.pid,done,ack))
                            self.assertIsNotNone(f.aim)
                            self.shots[s.pid]+=1
                        elif (self.heals[s.pid]<len(heal_marks)
                              and done>=heal_marks[self.heals[s.pid]]
                              and not battle_medicine.remaining_ms(self.case.store,s.char_id,now)):
                            medicine=next(r for r in self.meds[s.pid] if self.case.store.item(r['uniq']) is not None)
                            self.request(f.use_heal,dict(obj=inventory.oid_of(medicine)),inventory.USE_IDLE)
                            self.assertIsNotNone(f.healing)
                            self.heals[s.pid]+=1
                        elif done<45 and (s.walk is None or variant==2 and now>=next_reroute[s.pid]):
                            self.route(s)
                            next_reroute[s.pid]=now+.125
                            if variant==2 and s.walk is not None:
                                self.request(s.move_in_location,dict(path=list(s.walk[0])))
                    cells=[s.live_cell() for s in self.players]
                    self.assertEqual(len(set(cells)),2,('overlap',now,cells))
                    for s in self.players:
                        self.assertFalse(s.combat.dead)
                        self.assertLessEqual(self.steps[s.pid],45)
                        self.assertGreaterEqual(s.combat.ap,0)
                        for viewer in self.players:
                            if viewer.writer.cell(s.pid,now)!=s.live_cell():
                                state=self.case.clock.walks.get(id(s))
                                print('DIAGNOSTIC',now,'viewer',viewer.pid,'server',s.pid,
                                      'received',viewer.writer.routes[s.pid],'server_walk',s.walk,
                                      'index',state.index if state else None,
                                      'recent_frames',viewer.writer.frames[-8:])
                            self.assertEqual(viewer.writer.cell(s.pid,now),s.live_cell(),
                                             ('wire projection mismatch',now,s.pid,viewer.pid))
                            self.assertEqual(viewer.writer.health[s.pid],
                                             (s.char.vitals()['hcur'],s.char.vitals()['scur']),
                                             ('health mismatch',now,s.pid,viewer.pid))
                            checks+=1
                    finished=all(self.steps[s.pid]==45 and self.shots[s.pid]==5 and self.heals[s.pid]==3
                                 and s.combat.aim is None and s.combat.healing is None and not combat.Fighter.recovering(s.combat) for s in self.players)
                self.tick_us.append((time.perf_counter_ns()-started)/1000)
                tick+=1
                if finished:
                    break
            self.assertTrue(finished,('scenario timed out',self.steps,self.shots,self.heals))
        observer=self.a.writer.frames
        for s in self.players:
            ended=sum(n=='faShot' and p.get('id',0)==(0 if s is self.a else s.pid)
                      and p.get('status')==0 for n,p in observer)
            self.assertEqual(ended,5)
            self.assertEqual(sum(n=='heal' and p.get('id',0)==(0 if s is self.a else s.pid)
                                 for n,p in observer),3)
            self.assertEqual(self.case.store.item(self.guns[s.pid]['uniq'])['ammo_count'],3)
        row=dict(scenario=variant,steps=list(self.steps.values()),shots_per_player=5,heals_per_player=3,
                 simulated_seconds=round(now-100,3),position_health_comparisons=checks,
                 position_mismatches=0,overlaps=0,command_median_us=round(statistics.median(self.command_us),2),
                 command_p95_us=round(sorted(self.command_us)[int(len(self.command_us)*.95)],2),
                 tick_max_us=round(max(self.tick_us),2),
                 hit_events=sum(n=='faHit' for n,p in observer),
                 wall_events=sum(n=='faWall' for n,p in observer),
                 miss_events=sum(n=='faMiss' for n,p in observer),
                 fps='not measured: Flash renderer is not running',
                 network='ordered local encoded frames; no real TCP or jitter measurement')
        if OUT is not None:
            (OUT/('scenario-%d.json'%variant)).write_text(json.dumps(row,indent=2),encoding='utf-8')
        print(json.dumps(row))

    async def test_1_two_players_circle_rocks_shoot_and_heal_45_steps_each(self):
        await self.simulate(1)

    async def test_2_reroutes_duplicate_clicks_and_late_ticks_45_steps_each(self):
        await self.simulate(2)


if __name__=='__main__':
    run_cases(PvPManeuvers)
