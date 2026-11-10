"""Run emitted purchase-confirmation bytecode, including late UI callbacks."""
import math
import unittest

import widescreen as w
from avm_test import Function, Arr
from gold_commerce_client import patches


class GoldPurchaseClient(unittest.TestCase):
    def setUp(self):
        self.bought, self.failed, self.windows_opened = [], [], []
        self.frames = []
        self.pan = dict(trader=dict(pmod=1, type_list={8: 25217, 9: 25218}))
        self.windows = dict(trade=dict(instance=dict(content=self.pan)), query=dict(instance=None))
        self.env = dict(_global={}, String=str, Math=dict(ceil=math.ceil, floor=math.floor, max=max), isNaN=lambda n: n is None or math.isnan(float(n)),
                        TextFormat=lambda font, size: dict(font=font, size=size),
                        Selection=dict(setFocus=lambda field: None),
                        lol=dict(core=dict(SceneShifter=dict(_ref=dict(UIPanels=self.windows),
                            closeWindow=self.close, openNewWindow=self.open))))
        spec = patches(w.Asm, w.UNDEF)
        for name, params, body in spec['globals']:
            self.env['_global'][name] = Function(params, body.assemble(), self.env)
        self.methods = {name: Function(params, body.assemble(), self.env)
                        for _, name, _, params, body in spec['wraps']}
        self.trade = dict(visavisID=123, __gcBuyOrig=lambda item, n: self.bought.append((item['typeID'], n)),
                          applyTransfer=self.failed.append, __gcKillOrig=lambda: None)
        self.trade['__gcBuyAnswer'] = lambda event: self.methods['__gcBuyAnswer'].invoke(self.trade, [event])
        self.pan['trade'] = self.trade

    def open(self, name):
        dialog = dict(alert_txt=dict(_y=10, _height=100, textHeight=96, _x=20, _width=250),
                      getNextHighestDepth=lambda: 20,
                      addEventListener=lambda *args: None, removeEventListener=lambda *args: None)
        def resize():
            dialog['reservedHeight'] = dialog['alert_txt']['_height']
            footer = 10 + dialog['reservedHeight'] + 70
            dialog['apply_btn'] = dict(_y=footer)
            dialog['cancel_btn'] = dict(_y=footer)
            dialog['back_mc'] = dict(bottom_mc=dict(_y=footer-5), middle_mc=dict(_y=15, _height=20))
            for i in range(math.ceil((footer-20)/20)):
                name = 'm'+str(i)
                dialog['back_mc'][name] = dict(_y=35+i*20, _height=20,
                    removeMovieClip=lambda key=name: dialog['back_mc'].pop(key, None))
        def create_field(name, depth, x, y, width, height):
            dialog[name] = dict(setNewTextFormat=self.frames.append, _x=x, _y=y, _width=width, _height=height)
        dialog['resize'] = resize
        dialog['createTextField'] = create_field
        self.windows[name]['instance'] = dict(content=dialog)
        self.windows_opened.append(dialog)
        return dict(content=dialog)

    def close(self, name):
        self.windows[name]['instance'] = None

    def item(self, root=0, gold=1921, type_id=25218, index=9):
        props = dict(g_cost=gold, name='G3 (G)')
        return dict(rootID=root, typeID=type_id, tradeID=index,
                    getProp=lambda name: props.get(name), props=props)

    def buy(self, item=None):
        self.methods['buy'].invoke(self.trade, [item if item is not None else self.item(), 99])

    def answer(self, word='КУПИТЬ', success=True, dialog=None):
        dialog = dialog if dialog is not None else self.trade['__gcBuyDialog']
        dialog['__gcInput']['text'] = word
        self.trade['__gcBuyAnswer'](dict(target=dialog, success=success))

    def test_all_gold_categories_wait_for_exact_word(self):
        # Armour and pouches share the game's WEAR root.
        for root in (0, 5, 1, 2, 4, 6):
            with self.subTest(root=root):
                self.setUp()
                self.buy(self.item(root=root))
                self.assertEqual(self.bought, [])
                dialog = self.trade['__gcBuyDialog']
                self.assertIn('G3 (G)', dialog['label'])
                self.assertIn('19.21 G', dialog['label'])
                self.assertIn('КУПИТЬ', dialog['label'])
                self.assertEqual(dialog['__gcInput']['maxChars'], 6)
                self.assertEqual(self.frames, [dict(font='Tahoma', size=12)])
                self.answer()
                self.assertEqual(self.bought, [(25218, 1)])
                self.assertIsNone(self.trade['__gcBuyPending'])

    def test_real_trade_wrapper_uses_name_property_and_not_itemname(self):
        item = self.item(gold=13)
        self.assertNotIn('itemName', item)
        item['props']['name'] = 'Самопальный дробовик (G)'
        self.buy(item)
        self.assertIn('Самопальный дробовик (G)', self.trade['__gcBuyDialog']['label'])
        self.assertIn('0.13 G', self.trade['__gcBuyDialog']['label'])
        self.assertNotIn('undefined', self.trade['__gcBuyDialog']['label'])

    def test_input_is_below_short_and_wrapped_text_with_reserved_frame_space(self):
        for height in (18, 64, 110, 190):
            dialog = self.open('query')['content']
            dialog['alert_txt'].update(_height=height+4, textHeight=height)
            self.env['_global']['__gcConfirmInput'].invoke(None, [dialog, 6])
            field = dialog['__gcInput']
            self.assertGreaterEqual(field['_y'], 10 + height + 4 + 8)
            self.assertLessEqual(field['_y'] + field['_height'], 10 + dialog['reservedHeight'])
            self.assertEqual(dialog['alert_txt']['autoSize'], False)
            self.assertEqual(dialog['apply_btn']['_y'] - field['_y'] - field['_height'], 12)
            self.assertEqual(dialog['cancel_btn']['_y'], dialog['apply_btn']['_y'])
            back = dialog['back_mc']
            self.assertTrue(all(tile['_y']+tile['_height'] <= back['bottom_mc']['_y']
                                for name,tile in back.items() if name.startswith('m') and name != 'middle_mc'))

    def test_missing_name_does_not_offer_an_ambiguous_gold_purchase(self):
        item = self.item()
        item['props']['name'] = None
        self.buy(item)
        self.assertEqual(self.windows_opened, [])
        self.assertEqual(self.bought, [])
        self.assertEqual(self.failed, [False])

    def test_afro_items_and_pvp_points_keep_native_flow(self):
        for root in (0, 1, 2, 3, 4, 5, 6):
            self.buy(self.item(root=root, gold=0))
        points = self.item()
        points['props']['bg_p_cost'] = 150
        self.buy(points)
        self.assertEqual(len(self.bought), 8)
        self.assertEqual(self.windows_opened, [])

    def test_gold_ammunition_confirms_selected_count_and_total(self):
        item = self.item(root=3, gold=2)
        self.methods['buy'].invoke(self.trade, [item, 175])
        self.assertIn('3.5 G', self.trade['__gcBuyDialog']['label'])
        self.assertIn('Количество: 175', self.trade['__gcBuyDialog']['label'])
        self.answer()
        self.assertEqual(self.bought, [(25218, 175)])

    def test_default_ammo_quantity_and_price_multiplier(self):
        item = self.item(root=3, gold=2)
        item['props']['size'] = 500
        self.pan['trader']['pmod'] = 1.25
        self.methods['buy'].invoke(self.trade, [item, None])
        self.assertIn('12.5 G', self.trade['__gcBuyDialog']['label'])
        self.answer()
        self.assertEqual(self.bought, [(25218, 500)])

    def test_invalid_ammo_count_cannot_open_purchase_dialog(self):
        for n in (0, -1, 1.5, None):
            self.methods['buy'].invoke(self.trade, [self.item(root=3), n])
        self.assertEqual(self.windows_opened, [])
        self.assertEqual(self.bought, [])
        self.assertEqual(self.failed, [False] * 4)

    def test_cancel_empty_lowercase_and_wrong_word_never_buy(self):
        for word, success in (('КУПИТЬ', False), ('', True), ('купить', True), ('ПРОДАТЬ', True)):
            self.buy()
            self.answer(word, success)
        self.assertEqual(self.bought, [])
        self.assertEqual(self.failed, [False] * 4)
        self.buy()
        self.answer()
        self.assertEqual(self.bought, [(25218, 1)])

    def test_duplicate_click_and_callback_buy_once(self):
        self.buy()
        old = self.trade['__gcBuyDialog']
        self.buy()
        self.assertEqual(len(self.windows_opened), 1)
        self.answer()
        self.answer(dialog=old)
        self.assertEqual(self.bought, [(25218, 1)])

    def test_stale_callback_does_not_consume_another_purchase(self):
        self.buy()
        old = self.trade['__gcBuyDialog']
        self.answer(success=False)
        self.buy()
        current = self.trade['__gcBuyDialog']
        self.answer(dialog=old)
        self.assertIs(self.trade['__gcBuyDialog'], current)
        self.assertEqual(self.bought, [])
        self.answer()
        self.assertEqual(self.bought, [(25218, 1)])

    def test_changed_npc_stock_price_or_item_invalidates_confirmation(self):
        for changed in ('npc', 'window', 'stock', 'price', 'type', 'index', 'pmod'):
            with self.subTest(changed=changed):
                self.setUp()
                item = self.item()
                self.buy(item)
                if changed == 'npc': self.trade['visavisID'] = 999
                elif changed == 'window': self.pan['trade'] = {}
                elif changed == 'stock': self.pan['trader']['type_list'][9] = 25217
                elif changed == 'price': item['props']['g_cost'] += 100
                elif changed == 'type': item['typeID'] = 25217
                elif changed == 'pmod': self.pan['trader']['pmod'] = 2
                else: item['tradeID'] = 8
                self.answer()
                self.assertEqual(self.bought, [])
                self.assertEqual(self.failed, [False])

    def test_closed_trade_removes_pending_dialog_and_ignores_late_confirmation(self):
        self.buy()
        old = self.trade['__gcBuyDialog']
        self.methods['kill'].invoke(self.trade, [])
        self.answer(dialog=old)
        self.assertIsNone(self.trade['__gcBuyDialog'])
        self.assertIsNone(self.trade['__gcBuyPending'])
        self.assertEqual(self.bought, [])

    def test_existing_modal_or_wrong_stock_does_not_get_replaced(self):
        self.windows['query']['instance'] = dict(other=True)
        self.buy()
        self.assertEqual(self.windows_opened, [])
        self.assertEqual(self.windows['query']['instance'], dict(other=True))
        self.windows['query']['instance'] = None
        self.buy(self.item(index=8))
        self.assertEqual(self.windows_opened, [])
        self.assertEqual(self.bought, [])

    def test_new_selection_does_not_change_pending_item(self):
        self.buy()
        self.pan['selectedItem'] = self.item(gold=0, type_id=25217, index=8)
        self.answer()
        self.assertEqual(self.bought, [(25218, 1)])


if __name__ == '__main__':
    unittest.main()
