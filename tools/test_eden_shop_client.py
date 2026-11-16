"""Execute the emitted AVM1 for Eden-only prices and confirmation currency."""
import unittest

from test_gold_commerce_client import GoldCommerceClient
from testkit import run_cases


class EdenShopClient(unittest.TestCase):
    setUp = GoldCommerceClient.setUp
    item = GoldCommerceClient.item
    trade = GoldCommerceClient.trade
    message = GoldCommerceClient.message

    def test_trader_flag_is_scoped_to_the_current_counter_and_clears_on_other_info(self):
        trader = dict(__esTraderInfoOrig=lambda obj: None)
        self.methods['userInfo'].invoke(trader, [dict(param=dict(eden_shop=1))])
        self.pan['trader'] = trader
        active = self.env['_global']['__esActive']
        self.assertTrue(active.invoke({}, []))
        self.methods['userInfo'].invoke(trader, [dict(param={})])
        self.assertFalse(active.invoke({}, []))
        trader['eden_shop'] = True
        self.windows['trade']['instance'] = None
        self.assertFalse(active.invoke({}, []))

    def test_nominal_card_uses_native_currency_and_factory_wear(self):
        self.pan['trader'] = dict(eden_shop=True)
        for gold, unit, expected, frame in ((1, 1000, 2.5, 2), (0, 4000, 1000, 1)):
            item = self.item(eden_sale_unit=unit, eden_sale_gold=gold,
                             max_break_abs=1000, max_break_cur=500, __break=250)
            values, frames = [], []
            card = dict(showItemSellMod=True, showHeapCount=True, attachIconEnabled=True,
                        __gcShowCostOrig=lambda *args: None,
                        price_mc=dict(gotoAndStop=frames.append, fontContainer=dict(showValue=values.append)))
            self.methods['showCost'].invoke(card, [item, 'left'])
            self.assertEqual(values, [expected])
            self.assertEqual(frames, [frame])
            self.assertEqual(card['costType'], 'Золото' if gold else 'Афро')

    def test_non_gear_keeps_ordinary_quote_valuation_even_at_the_counter(self):
        self.pan['trader'] = dict(eden_shop=True)
        item = self.item(g_sale_unit=180000, eden_sale_unit=0, eden_sale_gold=0,
                         max_break_abs=0, max_break_cur=0, __break=0)
        item['rootID'] = 4
        values = []
        card = dict(showItemSellMod=True, showHeapCount=True, attachIconEnabled=True,
                    __gcShowCostOrig=lambda *args: None,
                    price_mc=dict(gotoAndStop=lambda frame: None, fontContainer=dict(showValue=values.append)))
        self.methods['showCost'].invoke(card, [item, 'left'])
        self.assertEqual(values, [180000])
        self.assertEqual(card['costType'], 'Афро')

    def test_local_nominal_item_is_rejected_without_offering_a_price(self):
        self.pan['trader'] = dict(eden_shop=True)
        item = self.item(eden_sale_unit=0, eden_sale_gold=0)
        panel = dict(__gcCheckSellOrig=lambda item: self.fail('native eligibility bypass'))
        self.assertIn('не принимает', self.methods['checkSellItem'].invoke(panel, [item]))

    def test_gold_quote_names_gold_and_afro_quote_uses_regular_yes_cancel(self):
        for gold, expected in ((1, '10.37 G'), (0, '1037 афро')):
            trade = self.trade()
            trade.update(__gcPending=dict(item=self.item(), n=1), __gcAnswer=lambda event: None)
            dialog = dict(addEventListener=lambda *args: None, removeEventListener=lambda *args: None)
            self.env['lol']['core']['SceneShifter']['openNewWindow'] = lambda name: dict(content=dialog)
            self.env['_global']['__gcConfirmInput'] = lambda target, length: target.update(input_requested=length)
            self.methods['__gcQuote'].invoke(trade, [dict(param=dict(res=0, token='abc', price=1037,
                                                                    count=1, eden_sale=1, currency=gold))])
            self.assertIn(expected, dialog['label'])
            self.assertEqual(dialog.get('input_requested'), 7 if gold else None)
            if not gold:
                self.methods['__gcAnswer'].invoke(trade, [dict(target=dialog, success=True)])
                self.assertEqual(self.sent[-1]['sale_token'], '@abc@')
                self.assertEqual(self.sent[-1]['confirmation'], '@ПРОДАТЬ@')


if __name__ == '__main__':
    run_cases(EdenShopClient)
