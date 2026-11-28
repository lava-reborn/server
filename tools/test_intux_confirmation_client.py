"""Execute the shipped INTUX bytecode with real native-style query callbacks."""
import unittest
from avm_test import Function
import widescreen as w
from intux_confirmation_client import MARK, action, patches


class IntuxClient(unittest.TestCase):
    def setUp(self):
        self.sent,self.calls,self.acks=[],[],[]
        self.location=dict(id='before');self.item=dict(typeID=3561)
        self.query=dict(instance=None)
        self.dialog=dict(apply_btn={},cancel_btn={},addEventListener=lambda *args:None,
                         removeEventListener=lambda *args:None)
        self.gamer=dict(attributes=dict(__ixSupported=True),dispatchAck=self.acks.append)
        self.master=dict(gamer=self.gamer,currentLocation=self.location)
        def message(kind,obj,target):
            value=dict(type=kind,obj=obj,target=target)
            value['addProp']=lambda k,v:value.update({k:v})
            return value
        def open_window(name):
            self.query['instance']=dict(content=self.dialog)
            return self.query['instance']
        def close_window(name):self.query['instance']=None
        self.env=dict(_global={},Number=float,clearInterval=lambda *args:None,
                      setInterval=lambda *args:4,
                      lol=dict(data=dict(BigUINT=lambda value:value,BigUINTCluster=lambda value:value),
                          core=dict(Master=dict(getInstance=lambda:self.master),
                              objects=dict(ItemFactory=dict(getItem=lambda obj:self.item)),
                              SceneShifter=dict(_ref=dict(UIPanels=dict(query=self.query)),
                                  openNewWindow=open_window,closeWindow=close_window)),
                          server=dict(mess=dict(CSM_SSUse=message),
                              XMLCCallStack=dict(addCall=lambda *args:self.calls.append(args)))))
        spec=patches(w.Asm,w.UNDEF)
        self.methods={method:Function(params,body.assemble(),self.env) for _,method,_,params,body in spec['wraps']}
        for name,params,body in spec['globals']:self.env['_global'][name]=Function(params,body.assemble(),self.env)
        self.original=[]
        self.actor=dict(gamer=self.gamer,XMC=dict(Send=lambda packet:self.sent.append(packet) or True),
                        canUse=lambda:True,coolDownBlock=False,useType=2,
                        __ixUseOrig=lambda *args:self.original.append(args),
                        useAck=lambda packet:self.acks.append(packet['param']['res']))
        for method,fn in self.methods.items():
            self.actor[method]=lambda *args, fn=fn:fn.invoke(self.actor,list(args))

    def request(self):self.actor['useItem'](2,123,None)
    def quote(self,warning=1,res=0):
        self.actor['__ixQuote'](dict(param=dict(res=res,xp_warning=warning,xp_token='token',
                                              xp_message='Суммарно +150%; максимум +100%. Применить?')))
    def answer(self,success=True,target=None):
        self.actor['__ixAnswer'](dict(target=self.dialog if target is None else target,success=success))

    def test_quote_has_no_native_action_cost_and_cancel_sends_no_application(self):
        self.request();self.assertEqual(self.sent[0]['xp_stage'],'@quote@')
        self.assertFalse(self.actor['coolDownBlock'])
        self.quote();self.assertIn('+100%',self.dialog['label'])
        self.assertEqual(self.dialog['apply_btn']['label'],'ОК')
        self.answer(False);self.assertEqual(len(self.sent),1)
        self.assertIsNone(self.actor['__ixPending'])

    def test_ok_sends_one_token_bound_application_and_retains_the_native_ack(self):
        self.request();self.request();self.assertEqual(len(self.sent),1)
        self.quote();self.answer();self.answer();self.assertEqual(len(self.sent),2)
        self.assertEqual(self.sent[1]['xp_token'],'@token@')
        self.assertNotIn('xp_stage',self.sent[1])
        self.assertTrue(self.actor['coolDownBlock'])
        self.actor['__ixApplied'](dict(param=dict(res=0)))
        self.assertEqual(self.acks,[0]);self.assertIsNone(self.actor['__ixPending'])

    def test_exact_cap_needs_no_window_and_other_consumables_keep_native_use(self):
        self.request();self.quote(0)
        self.assertIsNone(self.query['instance']);self.assertEqual(len(self.sent),2)
        self.actor['__ixPending']=None;self.item['typeID']=3473
        self.request();self.assertEqual(len(self.original),1)

    def test_rejected_or_late_quote_does_not_apply_and_does_not_replace_another_dialog(self):
        self.request();self.query['instance']=dict(content={});other=self.query['instance']
        self.quote();self.assertIs(self.query['instance'],other)
        self.assertEqual(len(self.sent),1)
        self.request();self.quote(res=7);self.assertEqual(self.acks,[7])
        self.assertEqual(len(self.sent),2)

    def test_other_dialog_click_location_change_and_unload_cannot_apply(self):
        self.request();self.quote();self.answer(target={})
        self.assertEqual(len(self.sent),1)
        self.master['currentLocation']=dict(id='after');self.answer()
        self.assertEqual(len(self.sent),1)
        self.location=self.master['currentLocation'];self.request();self.quote()
        self.env['_global']['__ixUnloaded'].invoke(self.dialog,[])
        self.assertIsNone(self.actor['__ixPending']);self.assertEqual(len(self.sent),2)

    def test_older_server_without_handshake_never_receives_a_quote_as_an_item_use(self):
        self.gamer['attributes']['__ixSupported']=False;self.request()
        self.assertFalse(self.sent);self.assertEqual(len(self.original),1)

    def test_capability_comes_from_the_native_rp_info_handler_and_preserves_stats(self):
        frames=[]
        attrs=dict(__ixAttributesOrig=frames.append)
        callback=self.methods['rp_info']
        frame=dict(param=dict(intux_confirmation=1, lvl=8))
        callback.invoke(attrs,[frame])
        self.assertTrue(attrs['__ixSupported']);self.assertEqual(frames,[frame])
        callback.invoke(attrs,[dict(param={})])
        self.assertTrue(attrs['__ixSupported'])

    def test_full_build_contains_the_dialog_and_replaces_incremental_updates(self):
        incremental=action(w.Asm,w.UNDEF)
        tags=[(12,incremental,True),(1,b'',False),(0,b'',False)]
        rebuilt=w.inject(tags,training=False)
        self.assertFalse(any(code==12 and MARK.encode() in data for code,data,*_ in rebuilt))
        full=next(data for code,data,*_ in rebuilt if code==12 and w.MARK.encode() in data)
        self.assertIn(b'__ixAttributesOrig',full)
        self.assertIn(b'xp_token',full)
        self.assertIn('ОТМЕНА'.encode(),full)
        self.assertEqual(w.inject(rebuilt,training=False),rebuilt)


if __name__=='__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
    from testkit import run_cases
    run_cases(IntuxClient)
