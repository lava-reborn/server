"""Every decoded blueprint can be sold for afro, preserving caps and replay safety."""
import unittest

import gold_trade
import items
import test_gold_commerce as commerce
from testkit import run_cases


class DecodedBlueprintSales(unittest.TestCase):
    def setUp(self):
        self.case=commerce.GoldCommerce()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def test_all_decoded_blueprints_sell_for_afro_once(self):
        count=0
        for type_id,(root,name) in items.catalogue().items():
            if not gold_trade.decoded_blueprint(type_id) or items.out_of_game(type_id):
                continue
            with self.subTest(type_id=type_id,name=name):
                params=items.params_of(type_id)
                self.assertEqual(gold_trade.client_fields(type_id)['bp_sell'],1)
                row=self.case.give(type_id)
                before=self.case.store.money(self.case.cid)
                if gold_trade.gold_priced(type_id,params):
                    request,quote=self.case.quote(row)
                    self.assertEqual(self.case.confirmed(request,quote),0)
                    self.assertNotEqual(self.case.confirmed(request,quote),0)
                else:
                    self.assertEqual(self.case.sell(row,1),0)
                    self.assertNotEqual(self.case.sell(row,1),0)
                after=self.case.store.money(self.case.cid)
                self.assertGreater(after[0],before[0])
                self.assertEqual(after[1],before[1])
                self.assertIsNone(self.case.store.item(row['uniq']))
                if params.get('cost',0)>0:
                    self.assertLessEqual(after[0]-before[0],params['cost'])
                if params.get('g_cost',0)>0:
                    self.assertLessEqual(after[0]-before[0],params['g_cost']*500)
                count+=1
        self.assertGreaterEqual(count,365)


if __name__=='__main__':
    run_cases(DecodedBlueprintSales)
