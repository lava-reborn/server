"""Execute Mortimer trade price/currency patches, without a Flash window."""
import math
import unittest
import widescreen as w
from avm_test import Function
from mortimer_trade_client import patches


class MortimerTradeUI(unittest.TestCase):
    def setUp(self):
        self.panel=dict(trader=dict(playerInfo=dict(resID=1188)))
        self.env=dict(_global={},String=str,Math=dict(floor=math.floor),
                      lol=dict(core=dict(SceneShifter=dict(_ref=dict(UIPanels=dict(
                          trade=dict(instance=dict(content=self.panel))))))))
        spec=patches(w.Asm,w.UNDEF)
        for name,params,body in spec['globals']:
            self.env['_global'][name]=Function(params,body.assemble(),self.env)
        self.methods={name:Function(params,body.assemble(),self.env)
                      for _,name,_,params,body in spec['wraps']}

    def item(self,type_id=6951,cost=2040,n=50):
        return dict(typeID=type_id,rootID=4,getProp=lambda key:dict(cost=cost,size=n).get(key))

    def test_mortimer_card_and_quantity_dialog_show_same_gold_payment(self):
        values=[];frames=[]
        card=dict(showItemSellMod=True,showHeapCount=True,attachIconEnabled=True,
                  __moShowCostOrig=lambda *args:None,
                  price_mc=dict(gotoAndStop=frames.append,fontContainer=dict(showValue=values.append)))
        item=self.item()
        self.methods['showCost'].invoke(card,[item,'left'])
        self.assertEqual(values,[2])
        self.assertEqual(frames,[2])
        self.assertEqual(card['costType'],'Золото')
        dialog={}
        ui=dict(__moExchangeOrig=lambda *args:dialog)
        result=self.methods['createExchangePan'].invoke(ui,[item,'sell',.7,False,True])
        self.assertEqual(result['cost_num'],4)
        self.assertEqual(result['cost_mod'],1)
        self.assertTrue(result['showCostInGold'])

    def test_only_allowlisted_gold_valuables_can_be_sold(self):
        ui=dict(__moCheckSellOrig=lambda item:None)
        for t in (6950,6951,6952,6953,6959):
            self.assertIsNone(self.methods['checkSellItem'].invoke(ui,[self.item(t)]))
        for t in (6946,2258,7620,566,25566):
            self.assertIn('только золотые ценности',self.methods['checkSellItem'].invoke(ui,[self.item(t)]))

    def test_other_traders_and_purchase_dialog_are_unchanged(self):
        self.panel['trader']['playerInfo']['resID']=123
        events=[]
        card=dict(showItemSellMod=True,price_mc={},__moShowCostOrig=lambda *args:events.append('native'))
        self.methods['showCost'].invoke(card,[self.item(),'left'])
        self.assertEqual(events,['native'])
        self.assertFalse(card['price_mc']['_visible'])
        self.assertIn('только Мортимеру',self.methods['checkSellItem'].invoke(
            dict(__moCheckSellOrig=lambda item:None),[self.item()]))
        ui=dict(__moCheckSellOrig=lambda item:'native rule',__moExchangeOrig=lambda *args:dict(original=True))
        self.assertEqual(self.methods['checkSellItem'].invoke(ui,[self.item(6946)]),'native rule')
        self.panel['trader']['playerInfo']['resID']=1188
        self.assertEqual(self.methods['createExchangePan'].invoke(ui,[self.item(),'buy',1,True,False]),dict(original=True))


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from testkit import run_cases
    run_cases(MortimerTradeUI)
