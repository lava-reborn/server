"""Execute the short debuff's emitted AVM1; no renderer/network/load."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from avm_test import Function
from medicine_cooldown_client import patches
import widescreen as w
from testkit import run_cases


class MedicineCooldownClient(unittest.TestCase):
    def test_quantity_purchase_emits_one_native_request_and_one_ack_registration(self):
        sent, ack, rejected = [], [], []
        self.env['lol']['core']['objects'] = dict(Item=dict(HEAL_ITEM=2))
        self.env['lol']['core']['player'] = dict(Trade=dict(UPD_BUY=1, UPD_BUY_GOLD=4))
        self.env['lol']['server'] = dict(mess=dict(CSM_SSUpdate=lambda *args: args),
                                        XMLCCallStack=dict(addCall=lambda *args:ack.append(args)))
        self.env['lol']['data'] = dict(BigUINT=lambda value:value, BigUINTCluster=lambda value:value)
        self.env['Math']['floor'] = math.floor
        gold = [0]
        item = dict(rootID=2, tradeID=dict(toString=lambda radix:'a'),
                    getProp=lambda key:dict(max_count=10,g_cost=gold[0]).get(key))
        trade = dict(XMC=dict(Send=lambda message:sent.append(message) or True), transferAck='ack',
                     applyTransfer=rejected.append)
        self.call('__bfMedBuy',trade,item,10)
        gold[0]=5
        self.call('__bfMedBuy',trade,item,3)
        self.assertEqual(sent,[(1,'a',10),(4,'a',3)])
        self.assertEqual(len(ack),2)
        for n in (0,-1,11,1.5):
            self.call('__bfMedBuy',trade,item,n)
        self.assertEqual(len(sent),2)
        self.assertEqual(rejected,[False]*4)

    def test_heal_initialization_reuses_native_heap_without_changing_charged_packs(self):
        objects = self.env['lol']['core']['objects'] = dict(HealItem=dict(prototype={}),
                        Heapable=dict(prototype={'nativeHeap': True}), Item=dict(HEAL_ITEM=2))
        seen = []
        item = dict(__bfMedItemInitOrig=seen.append)
        self.call('__bfMedItemInit', item, dict(max_count=10, use_count=1))
        self.assertIs(objects['HealItem']['prototype']['__proto__'], objects['Heapable']['prototype'])
        self.assertEqual((item['max_count'], item['size']), (10, 1))
        pack = dict(__bfMedItemInitOrig=seen.append)
        self.call('__bfMedItemInit', pack, dict(max_count=1, use_count=20))
        self.assertEqual(pack['max_count'], 1)
        self.assertEqual(seen[-1]['use_count'], 20)

    def test_single_dose_trade_quantity_uses_existing_dialogue_once(self):
        self.env['lol']['core']['objects'] = dict(Item=dict(HEAL_ITEM=2))
        events, calls = [], []
        pan = dict(addEventListener=lambda *args: events.append(args))
        item = dict(rootID=2, getProp=lambda key: 10 if key=='max_count' else 0)
        op = dict(fromSlot='stock', toSlot='bag', fromItem=item)
        view = dict(currDDOperation=op, visavisBag_mc='stock', bag_mc='bag', trader=dict(pmod=1),
                    createExchangePan=lambda *args: pan, exchangeAck='ack', exchangeCancel='cancel',
                    __bfMedQuantityOrig=lambda: calls.append('native'))
        self.call('__bfMedQuantity', view)
        self.assertEqual(pan['maxValue'], 10)
        self.assertEqual([event[0] for event in events], ['exchange','close'])
        self.assertFalse(calls)
        op['heapNum'] = 10
        self.call('__bfMedQuantity', view)
        self.assertEqual(calls, ['native'])

    def test_single_dose_counter_uses_only_native_numeric_glyphs_and_keeps_charged_uses(self):
        self.env['lol']['core']['objects'] = dict(Item=dict(HEAL_ITEM=2))
        drawn = []
        card = dict(item=dict(rootID=2, getProp=lambda key: dict(size=7,max_count=10).get(key)),
                    __bfMedAmountOrig=drawn.append)
        for count in (1, 3, 7, 10):
            card['item']['getProp'] = lambda key, n=count: dict(size=n,max_count=10).get(key)
            self.call('__bfMedAmount', card, '1/1')
            self.assertEqual(drawn[-1], str(count))
            # TextCharCreate's numChar atlas supports digits but no suffix
            # " шт.": unknown characters leave the zero frame visible.
            self.assertTrue(all(symbol in '0123456789' for symbol in drawn[-1]))
        card['item']['getProp'] = lambda key: 1 if key=='max_count' else None
        self.call('__bfMedAmount', card, '19/20')
        self.assertEqual(drawn[-1], '19/20')

    def setUp(self):
        self.now=1000
        self.timers=[]
        self.cleared=[]
        self.draw=[]
        self.created=[]
        self.removed=[]
        self.hints=[]
        self.global_={}
        self.env=dict(_global=self.global_,getTimer=lambda:self.now,String=str,
                      Math=dict(ceil=math.ceil,min=min,max=max),
                      setInterval=lambda fn,ms:self.timers.append((fn,ms)) or len(self.timers),
                      clearInterval=self.cleared.append,
                      lol=dict(core=dict(effects=dict(DisplayFX=dict(BUFF_WIDTH=44))),
                               gpui=dict(HintManager=dict(showHint=lambda *a:self.hints.append(a),
                                                          closeHint=lambda:self.hints.append('closed')))))
        self.functions={}
        for name,params,body in patches(w.Asm,w.UNDEF)['globals']:
            fn=Function(params,body.assemble(),self.env)
            self.functions[name]=fn
            self.global_[name]=fn
        self.view=self.new_view()
        self.connection=dict(__bfMedNotifyOrig=lambda command:None)

    def call(self,name,target=None,*args):
        return self.functions[name].invoke(target,args)

    def new_view(self):
        drawing={name:lambda *a,n=name:self.draw.append((n,a)) for name in
                 ('lineStyle','beginFill','moveTo','lineTo','endFill')}
        def attach(*args):
            icon=dict(EffectIcon=dict(_visible=True),createEmptyMovieClip=lambda *a:drawing,
                      getNextHighestDepth=lambda:10,
                      EstimateTime={'text':''},_height=40,_width=44)
            icon['removeMovieClip']=lambda:self.removed.append(icon)
            self.created.append(icon)
            return icon
        return dict(core_mc=dict(attachMovie=attach,getNextHighestDepth=lambda:10),
                    debuff_length=2,__bfMedInitOrig=lambda:None,
                    __bfMedEffectsOrig=lambda event:None,__bfMedKillOrig=lambda:None)

    def notify(self,remaining=4000):
        self.call('__bfMedNotify',self.connection,dict(messID='medCooldown',
                  params=dict(time_ms=remaining,description='Усталость после использования боевой медицины')))

    def test_single_native_shortcut_counts_down_and_removes_itself_without_polling(self):
        self.call('__bfMedInit',self.view)
        self.notify()
        self.assertEqual(len(self.created),1)
        icon=self.created[0]
        self.assertEqual((icon['_x'],icon['_y']),(35,80))
        self.assertEqual(icon['EstimateTime']['text'],'00:04')
        self.assertEqual([ms for _,ms in self.timers],[100])
        for stamp,text in ((2000,'00:03'),(3000,'00:02'),(4000,'00:01')):
            self.now=stamp
            self.call('__bfMedTick')
            self.assertEqual(icon['EstimateTime']['text'],text)
        self.now=5000
        self.call('__bfMedTick')
        self.assertEqual(self.removed,[icon])
        self.assertIsNone(self.global_['__bfMedTimer'])
        self.assertIsNone(self.view['__bfMedIcon'])

    def test_repeated_server_snapshot_does_not_duplicate_icon_or_timer(self):
        self.call('__bfMedInit',self.view)
        self.notify()
        self.now=1500
        self.notify(3500)
        self.assertEqual(self.global_['__bfMedUntil'],5000)
        self.assertEqual(len(self.created),1)
        self.assertEqual(len(self.timers),1)
        self.assertTrue(self.draw) # cross drawn only on creation

    def test_full_server_cooldown_remains_visible_until_medicine_is_ready(self):
        import battle_medicine
        remaining = int(battle_medicine.COOLDOWN_SECONDS * 1000)
        self.assertEqual(remaining, 6000)
        self.call('__bfMedInit',self.view)
        self.notify(remaining)
        icon=self.created[0]
        self.assertEqual(icon['EstimateTime']['text'],'00:06')
        for stamp,text in ((3000,'00:04'),(5000,'00:02'),(6999,'00:01')):
            self.now=stamp
            self.call('__bfMedTick')
            self.assertEqual(icon['EstimateTime']['text'],text)
            self.assertEqual(self.removed,[])
        self.now=7000
        self.call('__bfMedTick')
        self.assertEqual(self.removed,[icon])
        self.assertIsNone(self.global_['__bfMedTimer'])

    def test_collapse_reopen_and_old_unload_preserve_deadline_and_new_view(self):
        self.call('__bfMedInit',self.view)
        self.notify()
        self.call('__bfMedDetach',self.view)
        self.assertIsNotNone(self.global_['__bfMedTimer'])
        self.assertEqual(self.global_['__bfMedUntil'],5000)
        self.now=2000
        newer=self.new_view()
        self.call('__bfMedInit',newer)
        self.assertEqual(self.created[-1]['EstimateTime']['text'],'00:03')
        timer=self.global_['__bfMedTimer']
        self.call('__bfMedDetach',self.view)
        self.assertIs(self.global_['__bfMedView'],newer)
        self.assertEqual(self.global_['__bfMedTimer'],timer)
        self.call('__bfMedKill',newer)
        self.assertIsNone(self.global_['__bfMedView'])

    def test_minimised_window_catches_up_from_deadline_and_other_effects_keep_position(self):
        self.call('__bfMedInit',self.view)
        self.notify()
        self.view['debuff_length']=3
        self.call('__bfMedEffects',self.view,{})
        self.assertEqual(self.created[0]['_y'],120)
        self.assertEqual(self.view['debuff_length'],3)
        self.now=50000
        self.call('__bfMedTick')
        self.assertEqual(len(self.removed),1)
        self.assertIsNone(self.global_['__bfMedTimer'])

    def test_zero_or_unrelated_notification_preserves_native_dispatch(self):
        seen=[]
        self.connection['__bfMedNotifyOrig']=seen.append
        command=dict(messID='heal',params={})
        self.call('__bfMedNotify',self.connection,command)
        self.assertEqual(seen,[command])
        self.assertEqual(self.timers,[])
        self.call('__bfMedInit',self.view)
        self.notify()
        self.notify(0)
        self.assertEqual(len(self.removed),1)
        self.assertIsNone(self.global_['__bfMedTimer'])

    def test_existing_native_canvas_is_found_without_init_hook(self):
        self.env['lol']['core']['SceneShifter']=dict(_ref=dict(currentScene=dict(
            effectsPan=dict(content=self.view))))
        # Actual canvas already exists; the constructor hook never ran.
        self.notify()
        self.assertIs(self.global_['__bfMedView'],self.view)
        self.assertEqual(len(self.created),1)
        self.assertTrue(self.created[0]['_visible'])
        self.assertEqual(self.created[0]['EstimateTime']['text'],'00:04')

    def test_delayed_timeline_fields_are_drawn_on_next_tick_without_invisible_scaling(self):
        self.call('__bfMedInit',self.view)
        icon=dict(_height=0,_width=0,removeMovieClip=lambda:None)
        self.view['core_mc']['attachMovie']=lambda *a:icon
        self.notify()
        self.assertFalse(icon['_visible'])
        self.assertNotIn('__bfSeconds',icon)
        self.assertIsNotNone(self.global_['__bfMedTimer'])
        drawing={name:lambda *a:None for name in
                 ('lineStyle','beginFill','moveTo','lineTo','endFill')}
        icon.update(_height=40,_width=32,EstimateTime={'text':''},EffectIcon={'_visible':True},
                    createEmptyMovieClip=lambda *a:drawing,getNextHighestDepth=lambda:10)
        self.now=1100
        self.call('__bfMedTick')
        self.assertTrue(icon['_visible'])
        self.assertEqual(icon['_width'],32)
        self.assertEqual(icon['EstimateTime']['text'],'00:04')
        self.assertTrue(icon['__bfMedReady'])

    def test_closed_panel_opened_after_notification_restores_unexpired_icon(self):
        panel=dict(content=None)
        self.env['lol']['core']['SceneShifter']=dict(_ref=dict(currentScene=dict(effectsPan=panel)))
        self.notify()
        self.assertEqual(self.created,[])
        self.assertIsNotNone(self.global_['__bfMedTimer'])
        panel['content']=self.view
        self.now=2000
        self.call('__bfMedTick')
        self.assertEqual(self.created[0]['EstimateTime']['text'],'00:03')

    def test_clock_is_native_gettime_instruction_not_undefined_global_call(self):
        from avm_codegen import Compiler
        compiled=Compiler(w.Asm,w.UNDEF).functions("def clock():\n    return getTimer()\n")
        code=compiled[0][2].assemble()
        self.assertEqual(code[0],0x34)
        self.assertNotIn(b'getTimer\0',code)
        for name,params,body in patches(w.Asm,w.UNDEF)['globals']:
            self.assertNotIn(b'getTimer\0',body.assemble(),name)

    def test_hover_shows_requested_description_and_no_game_action(self):
        self.call('__bfMedInit',self.view)
        self.notify()
        self.call('__bfMedHover',self.created[0])
        self.assertEqual(self.hints[0][0],'Усталость после использования боевой медицины')
        self.call('__bfMedOut',self.created[0])
        self.assertEqual(self.hints[-1],'closed')


if __name__=='__main__':
    run_cases(MedicineCooldownClient)
