"""Focused failure/retry checks; never fetch assets or render Flash."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from avm_test import Arr,Function
from reflash_resources import patches
import widescreen as w
from testkit import run_cases


class ReFlashResources(unittest.TestCase):
    def setUp(self):
        self.now=20000
        self.calls=[]
        self.global_=dict(__rfGeneration=1,__rfNonce='20000-1',__rfResources=0)
        self.store={}
        self.factories={}
        def http():
            return dict(addEventListener=lambda *a:self.calls.append(('listen',a[0])),
                        Send=lambda body,url:self.calls.append(('xml',url)))
        self.env=dict(_global=self.global_,String=str,getTimer=lambda:self.now,
            lol=dict(display=dict(AnimationFactory=dict(persList=self.factories),
                                  SourceLibrary=dict(_lib=dict(store_arr=self.store))),
                     server=dict(HTTPRequest=http),
                     services=dict(SSEmulator=dict(getPersInfoURL=lambda model:'http://game/personages/'+str(model)+'.xml')),
                     utils=dict(ParseString=dict(replaceAll=lambda text,a,b:text.replace(a,b)))))
        self.functions={}
        for name,args,body in patches(w.Asm,w.UNDEF)['globals']:
            fn=Function(args,body.assemble(),self.env)
            self.functions[name]=fn
            self.global_[name]=fn

    def call(self,name,target=None,*args):
        return self.functions[name].invoke(target,args)

    def source(self,status='loading',failed=True,started=0):
        source=dict(status=status,loaded=status=='loaded',__rfFailed=failed,__rfStarted=started,
                    sourceURL='http://game/model.swf?v=1',cont_mc={},mcl_list={},
                    mcl=dict(removeListener=lambda obj:self.calls.append('detach'),
                             unloadClip=lambda obj:self.calls.append('unload')))
        source['loadSource']=lambda url:self.calls.append(('sprite',url))
        return source

    def test_failed_sprite_is_retried_once_without_replacing_shared_object(self):
        src=self.source()
        self.store['model']=src
        self.call('__rfRetrySource',None,src)
        self.call('__rfRetrySource',None,src)
        self.assertIs(self.store['model'],src)
        self.assertEqual(self.calls,['detach','unload',('sprite','http://game/model.swf?v=1&reflash=20000-1')])
        self.assertEqual(self.global_['__rfResources'],1)
        self.assertEqual(src['frame_arr'],[])
        self.assertEqual(src['__rfBaseURL'],'http://game/model.swf?v=1')

    def test_healthy_recent_and_never_requested_sources_are_not_reloaded(self):
        for src in (self.source('loaded'),self.source(failed=False,started=19000),
                    dict(status=None,loaded=False)):
            self.call('__rfRetrySource',None,src)
        self.assertEqual(self.calls,[])

    def test_loading_stuck_over_15_seconds_is_retried(self):
        self.call('__rfRetrySource',None,self.source(failed=False,started=4999))
        self.assertEqual(self.global_['__rfResources'],1)

    def test_slow_download_with_recent_progress_is_not_restarted(self):
        src=self.source(failed=False,started=0)
        src['__rfSourceProgressOrig']=lambda *args:None
        self.now=19000
        self.call('__rfSourceProgress',src,{},100,1000)
        self.now=20000
        self.call('__rfRetrySource',None,src)
        self.assertEqual(self.calls,[])
        self.assertEqual(src['__rfProgressAt'],19000)
        self.now=34001
        self.call('__rfRetrySource',None,src)
        self.assertEqual(self.global_['__rfResources'],1)

    def test_resource_retry_has_per_click_cap(self):
        for _ in range(20):
            self.call('__rfRetrySource',None,self.source())
        self.assertEqual(self.global_['__rfResources'],8)
        self.assertEqual(sum(isinstance(x,tuple) and x[0]=='sprite' for x in self.calls),8)

    def test_new_attempt_uses_original_url_without_growing_query_strings(self):
        src=self.source()
        self.call('__rfRetrySource',None,src)
        src.update(__rfFailed=True,status='loading',sourceURL=self.calls[-1][1])
        self.global_.update(__rfGeneration=2,__rfNonce='30000-2')
        self.call('__rfRetrySource',None,src)
        self.assertEqual(self.calls[-1],('sprite','http://game/model.swf?v=1&reflash=30000-2'))
        self.assertEqual(self.call('__rfFreshURL',None,'file:///game/model.swf'),'file:///game/model.swf')

    def test_model_xml_failure_is_retried_without_disposing_good_assets(self):
        af=dict(infoLoaded=False,__rfXmlFailed=True,persName=10,
                killHR=lambda:self.calls.append('kill-old-http'),AnimationList={'old':'partial'})
        self.call('__rfRetryXML',None,af)
        self.call('__rfRetryXML',None,af)
        self.assertEqual(self.calls,['kill-old-http',('listen','onXML'),('listen','failed'),
                                     ('xml','http://game/personages/10.xml?reflash=20000-1')])
        self.assertEqual(self.global_['__rfResources'],1)
        self.assertEqual(af['AnimationList'],[])

    def test_loaded_and_recent_model_xml_are_left_alone(self):
        for af in (dict(infoLoaded=True),dict(infoLoaded=False,__rfXmlStarted=19000)):
            self.call('__rfRetryXML',None,af)
        self.assertEqual(self.calls,[])

    def test_only_visible_models_and_equipped_weapon_overlay_are_considered(self):
        base=self.source()
        overlay=self.source()
        untouched=self.source()
        self.store.update(player10idle=base,player10gunidle=overlay,player99idle=untouched)
        self.factories['player10']=dict(infoLoaded=True,aName='player10',composite=True,
                                      AnimationList=dict(rifle=dict(stand=dict(action='idle'))))
        player=dict(walker=dict(persType=10),primaryItem=dict(itemName='g/un'))
        self.call('__rfRetryPlayerResources',None,player)
        self.assertEqual(self.global_['__rfResources'],2)
        self.assertNotIn('__rfAttempt',untouched)

    def test_error_hook_marks_failure_and_loading_keeps_original_url(self):
        src=dict(status=None,__rfSourceLoadOrig=lambda url:self.calls.append(('load',url)),
                 __rfSourceErrorOrig=lambda *a:self.calls.append('native-error'))
        self.call('__rfSourceLoad',src,'http://game/model.swf')
        self.assertEqual(src['__rfBaseURL'],'http://game/model.swf')
        self.assertFalse(src['__rfFailed'])
        self.call('__rfSourceError',src,{},'LoadNeverCompleted',404)
        self.assertTrue(src['__rfFailed'])
        self.assertEqual(self.calls[-1],'native-error')


if __name__=='__main__':
    run_cases(ReFlashResources)
