"""Execute emitted ReFlash AVM1 without a renderer or server traffic."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))

from avm_test import Arr, Function, get
from reflash_client import patches
import widescreen as w
from testkit import run_cases


class ReFlash(unittest.TestCase):
    def setUp(self):
        self.now=100
        self.requests=[]
        self.timers=[]
        self.cleared=[]
        self.created=[]
        self.master={}
        self.global_={'__bfWaiting':lambda:False}
        self.env=dict(_global=self.global_,getTimer=lambda:self.now,String=str,
                      setInterval=lambda fn,delay:self.timers.append((fn,delay)) or len(self.timers),
                      clearInterval=self.cleared.append,
                      Math=dict(round=lambda x:int(x+.5)),
                      lol=dict(core=dict(Master=dict(getInstance=lambda:self.master))))
        self.released=[]
        self.key_listeners=[]
        self.focus=[]
        self.held=set()
        self.modal=False
        self.keys=dict(keyStack=Arr([16,82]),keyPressStack=Arr(),enabled=False,
                       hotKeyFilter_arr=Arr(['chat']),hotKeyArr={'custom':'unchanged'},
                       dispatchEvent=self.released.append)
        self.state=dict(flagSceneEnabled=False)
        self.state['sceneEnabled']=lambda:self.state.update(flagSceneEnabled=self.modal)
        self.shifter=dict(hotKeyManager=self.keys,_ref=self.state)
        self.env['lol']['core']['SceneShifter']=self.shifter
        self.env['lol']['services']=dict(HotKeyEvent=dict(KEY_RELEASE='KEY_RELEASE'))
        self.env['Key']=dict(isDown=lambda code:code in self.held,
                             removeListener=lambda keys:self.key_listeners.append(('remove',keys)),
                             addListener=lambda keys:self.key_listeners.append(('add',keys)))
        self.env['Selection']=dict(setFocus=self.focus.append)
        self.functions={}
        for name,params,body in patches(w.Asm,w.UNDEF)['globals']:
            fn=Function(params,body.assemble(),self.env)
            self.functions[name]=fn
            self.global_[name]=fn
        self.me=self.player(0)
        self.other=self.player(1000012)
        self.loc=dict(warStatus=False,__rfPlayers=Arr([0,1000012]),
                      playerList={0:self.me,1000012:self.other})
        self.master.update(gamer=self.me,currentLocation=self.loc)
        self.frames=[]
        self.button=dict(_width=83,_height=45,gotoAndStop=self.frames.append,
                         removeMovieClip=lambda:None)
        def attach(name,instance,depth):
            self.created.append((name,instance,depth))
            return self.button
        self.exit=dict(_x=1140,_y=20,_width=83,_height=45)
        self.ui=dict(exit_btn=self.exit,attachMovie=attach,getNextHighestDepth=lambda:55,
                     __rfResizeOrig=lambda obj:self.exit.update(_x=obj['w']-140),
                     __rfInitOrig=lambda:None,__rfKillOrig=lambda:None)

    def player(self,id):
        return dict(walker=dict(behavior='stand',__walkActive=False),
                    equipment=dict(getStuff=lambda mask,target:self.requests.append(('gear',mask,target))),
                    requestInfo=lambda:self.requests.append(('info',id)))

    def call(self,name,target=None,*args):
        return self.functions[name].invoke(target,args)

    def test_button_uses_exit_art_and_stays_left_without_exit_handler(self):
        self.call('__rfInit',self.ui)
        self.assertEqual(self.created,[('__rf_button_art','__rfButton',55)])
        self.assertNotIn('label',self.button)
        self.assertNotIn('__rfCaption',self.button)
        self.assertFalse(self.button['_focusrect'])
        self.assertFalse(self.button['tabEnabled'])
        self.assertEqual(self.button['_x'],1140-83-6)
        self.assertEqual(self.button['_y'],20)
        self.assertIs(self.button['onRelease'],self.global_['__rfRelease'])
        self.call('__rfPress',self.button)
        self.assertEqual(self.frames[-1],2)
        self.call('__rfReset',self.button)
        self.assertEqual(self.frames[-1],1)
        self.button['enabled']=False
        self.call('__rfPress',self.button)
        self.assertEqual(self.frames[-1],1)
        self.call('__rfResize',self.ui,dict(w=1920))
        self.assertEqual(len(self.created),1)
        self.assertEqual(self.button['_x'],1920-140-83-6)
        self.assertEqual(self.requests,[])
        self.assertEqual(self.timers,[])

    def test_one_read_only_actor_batch_per_tick_and_no_idle_timer_after_finish(self):
        self.call('__rfInit',self.ui)
        self.call('__rfRelease',self.button)
        self.assertEqual(len(self.timers),1)
        self.assertEqual(self.requests,[])
        self.call('__rfRelease',self.button)
        self.assertEqual(len(self.timers),1)
        self.call('__rfStep')
        self.assertEqual(self.requests,[('info',0),('gear',3,0)])
        self.call('__rfStep')
        self.assertEqual(self.requests,[('info',0),('gear',3,0),('info',1000012),('gear',3,1000012)])
        self.assertIsNone(self.global_['__rfTimer'])
        self.assertIsNone(self.global_['__rfQueue'])
        self.assertTrue(self.button['enabled'])
        self.call('__rfRelease',self.button)
        self.assertEqual(len(self.timers),1)

    def test_combat_movement_or_pending_action_prevents_refresh(self):
        self.call('__rfInit',self.ui)
        for mode in ('war','move','fire','queued'):
            self.loc['warStatus']=mode=='war'
            self.me['walker']['__walkActive']=mode=='move'
            self.me['walker']['behavior']='fire' if mode=='fire' else 'stand'
            self.global_['__bfPendingInput']={} if mode=='queued' else None
            if mode=='queued':
                self.global_['__bfPendingInput']={'method':'heal'}
            self.call('__rfBegin',None,self.ui)
            self.assertEqual(self.requests,[])
            self.assertEqual(self.timers,[])

    def test_native_healing_reload_or_inflight_use_also_blocks_refresh(self):
        self.call('__rfInit',self.ui)
        self.me['itemActivator']=dict(useFireArm=True,coolDownBlock=False)
        self.call('__rfBegin',None,self.ui)
        self.assertEqual(self.timers,[])
        self.me['itemActivator']=dict(useFireArm=False,coolDownBlock=True)
        self.call('__rfBegin',None,self.ui)
        self.assertEqual(self.timers,[])

    def test_war_state_allows_keyboard_repair_but_does_not_start_resource_work(self):
        self.call('__rfInit',self.ui)
        self.ui['__rfBattleModeOrig']=lambda ws:None
        self.call('__rfBattleMode',self.ui,True)
        self.assertTrue(self.button['enabled'])
        self.loc['warStatus']=True
        self.call('__rfRelease',self.button)
        self.assertTrue(self.keys['enabled'])
        self.assertEqual(self.timers,[])
        self.call('__rfBattleMode',self.ui,False)
        self.assertTrue(self.button['enabled'])

    def test_manual_key_repair_preserves_bindings_held_keys_and_action_queue(self):
        self.held={16}
        pending={'method':'heal'}
        self.global_['__bfPendingInput']=pending
        self.call('__rfRepairKeys')
        self.assertEqual(self.keys['keyStack'],[16])
        self.assertEqual(get(self.keys['keyPressStack'],'code16'),16)
        self.assertEqual(self.released,[dict(type='KEY_RELEASE',code=82)])
        self.assertEqual(self.keys['hotKeyFilter_arr'],['location'])
        self.assertEqual(self.keys['hotKeyArr'],{'custom':'unchanged'})
        self.assertTrue(self.keys['enabled'])
        self.assertEqual([event for event,_ in self.key_listeners],['remove','add'])
        self.assertEqual(self.focus,[None])
        self.assertIs(self.global_['__bfPendingInput'],pending)
        self.assertEqual(self.requests,[])

    def test_open_modal_preserves_input_restrictions_and_focus(self):
        self.modal=True
        self.keys['hotKeyFilter_arr']=Arr(['location','barter'])
        self.call('__rfRepairKeys')
        self.assertFalse(self.keys['enabled'])
        self.assertEqual(self.keys['hotKeyFilter_arr'],['location','barter'])
        self.assertEqual(self.focus,[])
        self.call('__rfInit',self.ui)
        self.call('__rfRelease',self.button)
        self.assertEqual(self.timers,[])
        self.assertEqual(self.requests,[])

    def test_keyboard_repair_still_runs_during_resource_cooldown(self):
        self.call('__rfInit',self.ui)
        self.global_['__rfNextAllowed']=10000
        self.call('__rfRelease',self.button)
        self.assertTrue(self.keys['enabled'])
        self.assertEqual(self.keys['hotKeyFilter_arr'],['location'])
        self.assertEqual(self.timers,[])

    def test_started_combat_or_changed_location_stops_unsent_refresh(self):
        for changed in (False,True):
            self.setUp()
            self.call('__rfInit',self.ui)
            self.call('__rfBegin',None,self.ui)
            self.call('__rfStep')
            if changed:
                self.master['currentLocation']={}
            else:
                self.loc['warStatus']=True
            self.call('__rfStep')
            self.assertEqual(len(self.requests),2)
            self.assertIsNone(self.global_['__rfTimer'])

    def test_registry_is_compact_and_ignores_npcs_or_repeated_placements(self):
        loc=dict(__rfAddOrig=lambda id,pos,root:{'id':id},__rfRemoveOrig=lambda id:None)
        for id in (0,1000012,1000012,25):
            self.assertEqual(self.call('__rfAdd',loc,id,1,-1),{'id':id})
        self.assertEqual(loc['__rfPlayers'],[0,1000012])
        self.call('__rfRemove',loc,1000012)
        self.assertEqual(loc['__rfPlayers'],[0])

    def test_departed_player_is_skipped_and_interface_kill_clears_batch(self):
        self.call('__rfInit',self.ui)
        self.call('__rfBegin',None,self.ui)
        self.loc['playerList'][1000012]=None
        self.call('__rfStep')
        self.call('__rfStep')
        self.assertEqual(self.requests,[('info',0),('gear',3,0)])
        self.now=11000
        self.call('__rfBegin',None,self.ui)
        self.call('__rfKill',self.ui)
        self.assertIsNone(self.global_['__rfTimer'])
        self.assertIsNone(self.ui['__rfButton'])


if __name__=='__main__':
    run_cases(ReFlash)
