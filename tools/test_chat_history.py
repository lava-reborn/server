"""Execute emitted local-history AVM1 against an isolated SharedObject double."""
import copy
from types import SimpleNamespace as NS
import unittest
import widescreen as w
from avm_test import Arr, Function
from chat_tabs import patches as tab_patches
from chat_history import patches


class History(unittest.TestCase):
    def setUp(self):
        self.now=100000000
        self.limit=50
        self.disk={}
        self.writes=0
        self.timers=[]
        self.env=dict(Number=float,_global={},String=lambda v: str(v),
                      Date=lambda *args:self.date(args[0] if args else self.now),
                      TextFormat=lambda:{}, clearInterval=lambda timer:None,
                      setInterval=lambda *args:self.timers.append(args) or len(self.timers),
                      SharedObject=dict(getLocal=self.local),
                      lol=dict(gpui=dict(UserSettings=dict(NUMBER_OF_MESSAGE='limit',
                          getSetting=lambda key:self.limit))))
        self.methods={}
        for spec in (tab_patches(w.Asm,w.UNDEF),patches(w.Asm,w.UNDEF)):
            for name,params,body in spec['globals']:
                self.env['_global'][name]=Function(params,body.assemble(),self.env)
            for path,name,keep,params,body in spec['wraps']:
                if keep.startswith('__hc'):
                    self.methods[(path,name)]=Function(params,body.assemble(),self.env)
        self.env['_global']['__hcEndpoint']='127.0.0.1:19775'
        self.ui=self.make_ui('Tester12')

    def date(self,stamp):
        return dict(getTime=lambda:stamp,getDate=lambda:2,getMonth=lambda:10,
                    getHours=lambda:19,getMinutes=lambda:4)

    def local(self,key,path):
        data=copy.deepcopy(self.disk.get(key,{}))
        def flush():
            self.writes+=1
            self.disk[key]=copy.deepcopy(data)
            return True
        return dict(data=data,flush=flush)

    def make_ui(self,nick):
        channels=Arr()
        def channel(group,peer):
            return next((r for r in channels if r['group']==group and
                         (group!=-1 or r.get('withID')==peer)),None)
        tabs=[]
        chat=dict(channelList=channels,getChannel=channel)
        return dict(chat=chat,master=dict(gamer=dict(playerInfo=dict(name=nick))),
                    chatChannelPan=dict(getChannel=lambda *args:dict(mc=None),
                        createChannel=lambda *args:tabs.append(args)),tabs=tabs)

    def call(self,name,*args):
        return self.env['_global'][name].invoke(self.env['_global'],args)

    def attach(self,ui=None):self.call('__hcSafeAttach',ui or self.ui)

    def rec(self,ui=None,group=0,peer=None):
        ui=ui or self.ui
        r=dict(group=group,withID=peer,logArr=Arr())
        ui['chat']['channelList'].push(r)
        return r

    def add(self,rec,text='hello',stamp=None):
        r=dict(mess=text,name='Sender',time='19:04',fromID=12,group=rec['group'])
        if stamp is not None:r['__hcStamp']=stamp
        rec['logArr'].push(r)
        self.call('__hcSafeRecord',self.ui['chat'],rec)
        return r

    def test_private_public_ttl_original_names_times_and_no_delivery_events(self):
        self.attach()
        rec=self.rec(group=-1,peer='Лейкан')
        self.add(rec,'too old',self.now-43200001)
        self.add(rec,'private')
        self.add(self.rec(group=6),'world')
        self.call('__hcSafeClose')
        second=self.make_ui('Tester12')
        self.attach(second)
        rows=second['chat']['channelList']
        self.assertEqual(len(rows),2)
        texts=[r['mess'] for c in rows for r in c['logArr'] if not r.get('__hcMarker')]
        self.assertCountEqual(texts,['private','world'])
        for c in rows:
            self.assertTrue(c['logArr'][0]['__hcHistory'])
            self.assertEqual(c['logArr'][0]['name'],'Sender')
            self.assertEqual(c['logArr'][0]['time'],'19:04')
            self.assertIn('Отключение от сервера',c['logArr'][-1]['mess'])
        self.assertCountEqual(second['tabs'],[(-1,'Лейкан'),(6,None)])

    def test_character_and_server_isolation(self):
        self.attach();self.add(self.rec(),'secret');self.call('__hcSafeClose')
        other=self.make_ui('Other');self.attach(other)
        self.assertEqual(other['chat']['channelList'],[])
        self.env['_global']['__hcEndpoint']='different:19775'
        other_server=self.make_ui('Tester12');self.attach(other_server)
        self.assertEqual(other_server['chat']['channelList'],[])
        self.assertEqual(len(self.disk),3)

    def test_limit_is_enforced_live_cached_and_after_restore(self):
        self.limit=5;self.attach();rec=self.rec()
        for i in range(20):self.add(rec,str(i))
        self.assertEqual(len(rec['logArr']),5)
        self.call('__hcSafeFlush',self.ui['chat'])
        self.assertEqual(len(next(iter(self.disk.values()))['channels'][0]['rows']),5)
        self.call('__hcSafeClose');second=self.make_ui('Tester12');self.attach(second)
        rows=second['chat']['channelList'][0]['logArr']
        self.assertEqual(len(rows),5)
        self.assertEqual([r['mess'] for r in rows[:-1]],['16','17','18','19'])

    def test_flush_is_batched_and_noop_without_dirty_data(self):
        self.attach();initial=self.writes;rec=self.rec()
        for i in range(10):self.add(rec)
        self.assertEqual(self.writes,initial)
        self.call('__hcTick',self.ui['chat']);self.assertEqual(self.writes,initial+1)
        self.call('__hcTick',self.ui['chat']);self.assertEqual(self.writes,initial+1)
        self.assertEqual(len(self.timers),1)
        self.attach();self.assertEqual(len(self.timers),1)

    def test_global_cache_budget_and_long_text_are_bounded(self):
        self.limit=1000;self.attach();rec=self.rec()
        for i in range(250):self.add(rec,'x'*80)
        self.add(rec,'x'*2049)
        self.call('__hcSafeFlush',self.ui['chat'])
        rows=next(iter(self.disk.values()))['channels'][0]['rows']
        self.assertLessEqual(len(rows),300)
        self.assertLessEqual(sum(200+3*(len(r['mess'])+len(r['name'])) for r in rows),60000)
        self.assertTrue(all(len(r['mess'])<=2048 for r in rows))

    def test_crash_marker_does_not_invent_disconnect_time(self):
        self.attach();self.add(self.rec());self.call('__hcSafeFlush',self.ui['chat'])
        self.env['_global']['__hcChat']=None
        second=self.make_ui('Tester12');self.attach(second)
        self.assertEqual(second['chat']['channelList'][0]['logArr'][-1]['mess'],
                         '— Предыдущий сеанс завершён —')

    def test_storage_error_does_not_block_native_dispatch(self):
        self.env['SharedObject']['getLocal']=lambda *args:(_ for _ in ()).throw(OSError('denied'))
        self.attach()
        events=[]
        self.ui['chat']['__hcDispatchOrig']=lambda rec:events.append(rec)
        rec=self.rec();self.add(rec)
        self.methods[(('core','Chat'),'dispatchChannel')].invoke(self.ui['chat'],[rec])
        self.assertEqual(events,[rec])

    def test_clear_channel_removes_persisted_messages(self):
        self.attach();rec=self.rec();self.add(rec)
        self.call('__hcSafeFlush',self.ui['chat'])
        self.ui['chat']['__hcEraseOrig']=lambda peer,group:rec.update(logArr=Arr())
        self.methods[(('core','Chat'),'eraseChannel')].invoke(self.ui['chat'],[None,0])
        self.assertEqual(next(iter(self.disk.values()))['channels'],[])

    def test_renderer_mutes_only_history_prefix(self):
        calls=[]
        output=dict(text='')
        def native(rows,group):output['text']=''.join(r['mess']+'\n' for r in rows)
        output['setTextFormat']=lambda start,end,fmt:calls.append((start,end,fmt))
        ui=dict(chatOutput=output,__hcShowOrig=native)
        rows=Arr([dict(mess='old',__hcHistory=True),dict(mess='new')])
        self.methods[(('services','ChatPan'),'showMessage')].invoke(ui,[rows,0])
        self.assertEqual(output['text'],'old\nnew\n')
        self.assertEqual(calls,[(0,4,dict(color=10065534))])

    def test_failed_private_delivery_is_not_saved_as_sent_text(self):
        self.attach();rec=self.rec(group=-1,peer='Offline')
        row=self.add(rec,'not delivered');row['fromID']='server'
        self.call('__hcSafeFlush',self.ui['chat'])
        self.assertEqual(next(iter(self.disk.values()))['channels'],[])

    def test_quota_denial_disables_cache_without_affecting_chat(self):
        self.attach();rec=self.rec();self.add(rec)
        self.ui['chat']['__hcStore']['flush']=lambda:False
        self.call('__hcSafeFlush',self.ui['chat'])
        self.assertIsNone(self.ui['chat']['__hcStore'])
        self.assertEqual(rec['logArr'][0]['mess'],'hello')

    def test_corrupt_storage_does_not_change_delivery(self):
        key='lavaChatV1'+self.call('__hcEncode','127.0.0.1:19775|Tester12')
        self.disk[key]=dict(version=1,channels=Arr([None,dict(group=99),
                            dict(group=-1,peer='bad',scope='public',rows=Arr([dict(mess=3)]))]))
        self.attach()
        self.assertEqual(self.ui['chat']['channelList'],[])
        self.add(self.rec(),'new message')
        self.call('__hcSafeFlush',self.ui['chat'])
        self.assertEqual(self.disk[key]['channels'][0]['rows'][0]['mess'],'new message')

    def test_same_chat_object_can_relog_without_duplicates_or_stopped_cache(self):
        self.attach();self.add(self.rec(),'before relog')
        self.call('__hcSafeClose')
        self.attach()
        rows=self.ui['chat']['channelList'][0]['logArr']
        self.assertEqual(sum(r['mess']=='before relog' for r in rows),1)
        self.assertTrue(self.ui['chat']['__hcOpen'])
        self.assertEqual(len(self.timers),2)

    def test_saved_string_message_limit_is_respected(self):
        self.limit='5'
        self.assertEqual(self.call('__hcLimit'),5)

    def test_closed_private_history_restores_without_reopening_tab(self):
        self.attach();rec=self.rec(group=-1,peer='Peer');self.add(rec)
        rec['__pmClosed']=True
        self.call('__hcSafeClose')
        other=self.make_ui('Tester12');self.attach(other)
        restored=other['chat']['channelList'][0]
        self.assertTrue(restored['__pmClosed'])
        self.assertEqual(restored['logArr'][0]['mess'],'hello')
        self.assertEqual(other['tabs'],[])

    def test_protected_bytecode_has_header_only_action_length(self):
        from avm_codegen import protected_call
        import struct
        data=protected_call(w.Asm,'__hcFlush',('chat',),w.UNDEF).assemble()
        self.assertEqual(data[:4], b'\x8f\x12\x00\x01')
        size=struct.unpack_from('<H',data,4)[0]
        self.assertEqual(len(data),3+18+size)

    def test_late_character_info_attaches_cache_after_initial_empty_name(self):
        self.ui['master']['gamer']['playerInfo']['name']=''
        self.attach();self.assertEqual(self.disk,{})
        self.env['lol']['core']=dict(SceneShifter=dict(chat=self.ui))
        actor=dict(__hcInfoOrig=lambda obj:self.ui['master']['gamer']['playerInfo'].update(name='Tester12'))
        self.methods[(('core','player','Gamer'),'userInfo')].invoke(actor,[{}])
        self.assertEqual(len(self.disk),1)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from testkit import run_cases
    run_cases(History)
