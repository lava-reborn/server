"""Execute catalogue UI bytecode for stale responses and one-shot issuance."""
import unittest
import test_training_ground_client as base


class SupplyClient(unittest.TestCase):
    helpers = base.TrainingClient.helpers

    def test_stale_pages_and_previews_do_not_touch_a_new_or_closed_window(self):
        panel = dict(__supply=True)
        env = dict(_global=dict(__tgPanel=panel, __tgContext='medical', __tgCatalogueRequest=8))
        f = self.helpers(env)
        for packet in (dict(op='supply_list',context='weapons',request_id=8),
                       dict(op='supply_list',context='medical',request_id=7),
                       dict(op='supply_variants',context='medical',request_id=7)):
            f['__tgSupplyReceive'].invoke(None,[packet])
        self.assertEqual(panel,dict(__supply=True))
        env['_global']['__tgPanel']=None
        f['__tgSupplyReceive'].invoke(None,[dict(op='supply_variants',context='medical',request_id=8)])

    def test_pending_give_does_not_submit_twice_or_clear_on_another_ack(self):
        panel=dict(__supply=True,__supplySource=26075)
        env=dict(_global=dict(__tgPanel=panel,__tgSupplyPending=12))
        f=self.helpers(env)
        f['__tgSupplyClick'].invoke(dict(__op='give'),[])
        f['__tgSupplyReceive'].invoke(None,[dict(op='supply_done',sequence=11)])
        self.assertEqual(env['_global']['__tgSupplyPending'],12)
        panel['status']={}
        f['__tgSupplyReceive'].invoke(None,[dict(op='supply_done',sequence=12,message='OK')])
        self.assertEqual(env['_global']['__tgSupplyPending'],0)
        self.assertEqual(panel['status']['text'],'OK')

    def test_detach_preview_removes_async_listeners_and_card(self):
        calls=[]
        item=dict(typeID=54000,removeEventListener=lambda *args:calls.append('item'))
        proto=dict(removeEventListener=lambda *args:calls.append('proto'))
        icon=dict(src=dict(removeEventListener=lambda *args:calls.append('icon')),
                  mcl_list=dict(onLoadInit='callback'))
        card=dict(icon_mc=icon,kill=lambda:calls.append('kill'),removeMovieClip=lambda:calls.append('remove'))
        panel=dict(__supplyItem=item,supplyCard=card,__supplySource=42)
        env=dict(_global={},lol=dict(core=dict(objects=dict(ItemFactory=dict(getProtoItem=lambda _:proto))),
                 utils=dict(StringCollector=dict(getInstance=lambda:dict(removeEventListener=lambda *args:None)))))
        f=self.helpers(env)
        f['__tgSupplyClear'].invoke(None,[panel])
        self.assertEqual(calls,['item','item','proto','icon','kill','remove'])
        self.assertIsNone(panel['__supplySource'])
        self.assertIsNone(icon['mcl_list']['onLoadInit'])
        self.assertIsNone(panel['__supplyItem'])

    def test_late_item_loading_cannot_attach_preview_to_another_window(self):
        old=dict(__supply=True,__supplyProto=dict(typeID=54000))
        current=dict(__supply=True,__supplyProto=dict(typeID=54001))
        env=dict(_global=dict(__tgPanel=current))
        f=self.helpers(env)
        f['__tgSupplyReady'].invoke(old,[dict(target=old['__supplyProto'])])
        f['__tgSupplyReady'].invoke(current,[dict(target=old['__supplyProto'])])
        self.assertNotIn('supplyCard',current)

    def test_native_window_coordinates_center_and_clamp_without_hiding_description_layer(self):
        panel = dict(__nativeLayer=True, __w=980, __h=640, _x=0, _y=0)
        env = dict(Math=dict(round=round,max=max,min=min), Stage=dict(width=1280,height=800),
                   lol=dict(core=dict(SceneShifter=dict(_ref=dict(minW=1280,minH=800)))), _global={})
        f = self.helpers(env)
        f['__tgLayout'].invoke(None,[panel,True])
        self.assertEqual((panel['_x'],panel['_y']),(-490,-320))
        panel['_x'],panel['_y'] = 10000,10000
        f['__tgLayout'].invoke(None,[panel,False])
        self.assertEqual((panel['_x'],panel['_y']),(-348,-248))
        import training_ground_client
        self.assertIn('layer = lol.core.SceneShifter.linkWindow', training_ground_client.SOURCE)

    def test_pick_complete_set_sends_bundle_marker_and_exact_set_id(self):
        sent = {}
        panel = dict(__supply=True,__supplyRows=dict(bundle=1))
        env = dict(Number=float,Boolean=bool,_global=dict(__tgPanel=panel,__tgCatalogueRequest=1))
        f = self.helpers(env)
        env['_global']['__tgSupplyClear'] = lambda p:None
        env['_global']['__tgSend'] = lambda op:dict(addProp=lambda k,v:sent.update({k:v}))
        env['_global']['__tgTransmit'] = lambda p:None
        f['__tgSupplyClick'].invoke(dict(__op='pick',__value=80001),[])
        self.assertEqual(sent['source'],80001)
        self.assertEqual(sent['bundle'],1)
        self.assertEqual(sent['request_id'],2)


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
    from testkit import run_cases
    run_cases(SupplyClient)
