"""Reachable loot approach uses existing bounded grid search, no network polling."""
import sys,math,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from avm_test import Arr,Function
from testkit import run_cases
import widescreen as w
from combat_client import patches


class Choices(Arr):
    def concat(self,other):
        return Choices(list(self)+list(other))


class LootRoute(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.now=100
        self.timers=[]
        self.here=dict(gx=0,gy=0,num=0)
        self.bag=dict(gx=5,gy=0,num=5)
        self.blocked=dict(gx=4,gy=0,num=4)
        self.free=dict(gx=5,gy=1,num=105)
        def search(*args):
            self.calls.append(('search',args))
            return Arr([[5,1]]) if args[3] == 1 else Arr()
        grid=dict(getHexDistance=lambda a,b: abs(a['gx']-b['gx'])+abs(a['gy']-b['gy']),
                  getSiblings=lambda _:Choices([self.free,self.blocked]),searchWay=search)
        self.loc=dict(locationGrid=grid,locInfo=dict(width=100,height=100),
                      getCellFromNumber=lambda n:self.here if n==0 else self.bag,
                      movePlayer=lambda cell:self.calls.append(('move',cell)))
        self.env=dict(_global={},Number=float,
                      getTimer=lambda:self.now,
                      setInterval=lambda fn,ms:self.timers.append((fn,ms)) or len(self.timers),
                      clearInterval=lambda timer:None,
                      Math=dict(max=max,floor=math.floor,abs=abs),
                      lol=dict(core=dict(Master=dict(getInstance=lambda:dict(currentLocation=self.loc))),
                               gpui=dict(UserSettings=dict(PATH_FINDING='path',getSetting=lambda _:False))))
        self.functions={}
        for name,args,body in patches(w.Asm,w.UNDEF)['globals']:
            fn=Function(args,body.assemble(),self.env)
            self.functions[name]=self.env['_global'][name]=fn

    def test_unreachable_nearest_neighbour_tries_next_without_opening_early(self):
        gamer=dict(walker=dict(numPos=0,removeEventListener=lambda *a:None,
                               addEventListener=lambda *a:None),createLoot=lambda _:self.calls.append('open'))
        self.functions['__bfLootGo'].invoke(gamer,[5])
        self.assertEqual(self.calls[-1],('move',self.free))
        self.assertEqual(len([c for c in self.calls if c[0]=='search']),2)
        self.assertNotIn('open',self.calls)
        self.assertEqual(gamer['stuff_param'],5)

    def test_nearby_bag_opens_without_search(self):
        self.bag.update(gx=1)
        gamer=dict(walker=dict(numPos=0),createLoot=lambda _:self.calls.append('open'))
        self.functions['__bfLootGo'].invoke(gamer,[5])
        self.assertEqual(self.calls,['open'])

    def test_far_outside_configured_search_window_does_not_allocate_path(self):
        self.assertFalse(self.functions['__bfLootReachable'].invoke(None,[self.loc,self.here,dict(gx=100,gy=0)]))
        self.assertEqual(self.calls,[])

    def test_loot_click_waits_for_recovery_then_opens_once(self):
        self.bag.update(gx=1)
        gamer=dict(walker=dict(numPos=0),createLoot=lambda _:self.calls.append('open'))
        gamer['gotoLoot']=lambda pos:self.functions['__bfLootGo'].invoke(gamer,[pos])
        self.env['_global']['__bfRecoveryUntil']=200
        self.functions['__bfLootGo'].invoke(gamer,[5])
        self.assertNotIn('open',self.calls)
        self.assertEqual(len(self.timers),1)
        self.now=199
        self.functions['__bfDrainInput'].invoke(None,[])
        self.assertNotIn('open',self.calls)
        self.now=200
        self.functions['__bfDrainInput'].invoke(None,[])
        self.functions['__bfDrainInput'].invoke(None,[])
        self.assertEqual(self.calls.count('open'),1)
        self.assertIsNone(self.env['_global']['__bfPendingInput'])
        self.assertIsNone(self.env['_global']['__bfInputTimer'])


if __name__=='__main__':
    run_cases(LootRoute)
