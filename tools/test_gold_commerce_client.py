"""Execute emitted AVM1: quote confirmation, price display and queue order."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import Function, Arr
from gold_commerce_client import patches
from protocol import decode
from testkit import run_cases


class GoldCommerceClient(unittest.TestCase):
    def setUp(self):
        self.calls, self.sent, self.transfers = [], [], []
        self.pan = {}
        self.windows = dict(trade=dict(instance=dict(content=self.pan)), query=dict(instance=None))
        self.env = dict(_global=dict(__moActive=lambda: False), String=str,
                        Math=dict(floor=math.floor, ceil=math.ceil, min=min, max=max),
                        lol=dict(gpui=dict(StaffInterface=dict(ssType='trade')),
                                 core=dict(SceneShifter=dict(_ref=dict(UIPanels=self.windows),
                            closeWindow=lambda name: self.calls.append(('close', name)))),
                                 server=dict(XMLCCallStack=dict(addCall=lambda *args: self.calls.append(args)),
                                             mess=dict(CSM_SSUpdate=self.message)),
                                 data=dict(BigUINT=lambda x: 'x' + str(x), BigUINTCluster=lambda x: x)))
        spec = patches(w.Asm, w.UNDEF)
        for name, params, body in spec['globals']:
            self.env['_global'][name] = Function(params, body.assemble(), self.env)
        self.methods = {name: Function(params, body.assemble(), self.env)
                        for _, name, _, params, body in spec['wraps']}

    def message(self, status, obj, n):
        data = dict(s_status=status, obj=obj, param=n)
        data['addProp'] = lambda key, value: data.update({key: value})
        return data

    def item(self, **overrides):
        props = dict(g_sale_unit=362950, max_break_cur=200, max_break_abs=200, __break=100,
                     size=1, g_transfer=1, g_auction_base=138125, max_use_count=0)
        props.update(overrides)
        return dict(id='165db00', rootID=0, itemName='Remington 11-87 (G)', getProp=lambda name: props.get(name))

    def trade(self):
        trade = dict(__gcSellOrig=lambda *args: self.calls.append(('native', args)),
                     XMC=dict(Send=lambda message: self.sent.append(message) or True),
                     __gcQuote=lambda obj: None,
                     applyTransfer=lambda success: self.transfers.append(success),
                     transferAck=lambda obj: None)
        self.pan['trade'] = trade
        return trade

    def test_prices_and_commissions_match_server_with_wear_and_quantity(self):
        values = []
        card = dict(showItemSellMod=True, showHeapCount=True, attachIconEnabled=True,
                    __gcShowCostOrig=lambda *a: None,
                    price_mc=dict(gotoAndStop=lambda frame: None,
                                  fontContainer=dict(showValue=values.append)))
        self.methods['showCost'].invoke(card, [self.item(), 'left'])
        self.assertEqual(values, [181475])
        ui = dict(lotSlot=dict(item=self.item(size=2)), rateA_txt=dict(text='100'),
                  buyoutA_txt=dict(text=''), curTime_btn=2, time24_btn=2, time48_btn=3,
                  info_txt=dict(setTextFormat=lambda fmt: None), tf={},
                  __gcCommissionOrig=lambda: self.fail('unexpected native commission'))
        self.methods['checkComission'].invoke(ui, [])
        self.assertEqual(ui['info_txt']['htmlText'], '\rКомиссия: 19338 А')

    def test_blueprint_without_durability_can_sell_and_tooltip_says_yes(self):
        for gold in (False,True):
            item=self.item(bp_sell=1,g_sale_unit=180000 if gold else 0,__break=0,cost=0 if gold else 4000)
            item['rootID']=3
            item['itemName']='Чертёж'
            ui=dict(__gcCheckSellOrig=lambda item:'native refusal')
            self.assertIsNone(self.methods['checkSellItem'].invoke(ui,[item]))
            lines=Arr()
            annotation=dict(item=item,__gcAddSellOrig=lambda arr:arr.push(['Допустимость продажи','Нет']))
            self.methods['addSell'].invoke(annotation,[lines])
            self.assertEqual(lines,[['Допустимость продажи','Да']])
        broken=self.item(__break=0)
        self.assertIsNotNone(self.methods['checkSellItem'].invoke(ui,[broken]))

    def test_sale_asks_for_quote_and_does_not_send_sale_confirmation_immediately(self):
        trade = self.trade()
        self.methods['sell'].invoke(trade, [self.item(), 1])
        self.assertEqual(self.sent[0]['sale_stage'], '@quote@')
        self.assertNotIn('confirmation', self.sent[0])
        self.assertEqual(self.calls[-1][0], 'cmdAck')
        # Strings must use the actual wire escaping expected by protocol.py.
        _, params = decode('ss_upd;s_status=2;obj=x165db00;param=1;sale_stage=@quote@;')
        self.assertEqual(params['sale_stage'], 'quote')

    def test_quote_opens_typed_confirmation_with_native_window_and_readable_input(self):
        trade = self.trade()
        trade.update(__gcPending=dict(item=self.item(), n=1), __gcAnswer=lambda event: None)
        fields = []
        dialog = dict(alert_txt=dict(_y=10, _height=100, _x=20, _width=250),
                      getNextHighestDepth=lambda: 42,
                      addEventListener=lambda *args: self.calls.append(args))
        def create_field(name, depth, x, y, width, height):
            dialog[name] = dict(setNewTextFormat=fields.append)
        dialog['createTextField'] = create_field
        self.env['lol']['core']['SceneShifter']['openNewWindow'] = lambda name: dict(content=dialog)
        self.env['TextFormat'] = lambda font, size: dict(font=font, size=size)
        self.env['Selection'] = dict(setFocus=lambda field: None)
        # Functions retain a snapshot of globals, just like other AVM tests.
        params, body = next((p, b) for _, n, _, p, b in patches(w.Asm, w.UNDEF)['wraps'] if n == '__gcQuote')
        Function(params, body.assemble(), self.env).invoke(trade, [dict(param=dict(res=0, token='abc', price=181475, count=1))])
        self.assertIn('Remington 11-87 (G)', dialog['label'])
        self.assertIn('181475', dialog['label'])
        self.assertEqual(dialog['__gcInput']['type'], 'input')
        self.assertEqual(dialog['__gcInput']['maxChars'], 7)
        self.assertEqual(fields, [dict(font='Tahoma', size=12)])

    def test_cancel_or_wrong_word_restores_transfer_without_a_sale_frame(self):
        for success, word in ((False, 'ПРОДАТЬ'), (True, ''), (True, 'продать')):
            trade = self.trade()
            dialog = dict(__gcInput=dict(text=word), removeEventListener=lambda *args: None)
            trade.update(__gcDialog=dialog, __gcPending=dict(item=self.item(), n=1, token='abc'),
                         __gcAnswer=lambda event: None)
            self.methods['__gcAnswer'].invoke(trade, [dict(target=dialog, success=success)])
            self.assertEqual(self.sent, [])
            self.assertEqual(self.transfers[-1], False)

    def test_correct_confirmation_sends_original_count_token_and_exact_word(self):
        trade = self.trade()
        dialog = dict(__gcInput=dict(text='ПРОДАТЬ'), removeEventListener=lambda *args: None)
        trade.update(__gcDialog=dialog, __gcPending=dict(item=self.item(), n=3, token='123abc'),
                     __gcAnswer=lambda event: None)
        self.methods['__gcAnswer'].invoke(trade, [dict(target=dialog, success=True)])
        self.assertEqual(self.sent[-1]['param'], 3)
        self.assertEqual(self.sent[-1]['sale_token'], '@123abc@')
        self.assertEqual(self.sent[-1]['confirmation'], '@ПРОДАТЬ@')
        self.assertEqual(self.calls[-1][0], 'cmdAck')

    def test_npc_window_change_cancels_confirmation(self):
        trade = self.trade()
        dialog = dict(__gcInput=dict(text='ПРОДАТЬ'), removeEventListener=lambda *args: None)
        trade.update(__gcDialog=dialog, __gcPending=dict(item=self.item(), n=1, token='abc'),
                     __gcAnswer=lambda event: None)
        self.pan['trade'] = {}
        self.methods['__gcAnswer'].invoke(trade, [dict(target=dialog, success=True)])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.transfers, [False])

    def test_bulk_transfers_are_serialized_without_shifting_another_sale(self):
        started = []
        trade = dict(__gcRequestOrig=started.append, transferStack=Arr(['one', 'two']),
                     __gcApplyOrig=lambda success: trade['transferStack'].pop(0))
        trade['requestTranfer'] = lambda obj: self.methods['requestTranfer'].invoke(trade, [obj])
        trade['requestTranfer']('one')
        trade['requestTranfer']('two')
        self.assertEqual(started, ['one'])
        self.methods['applyTransfer'].invoke(trade, [False])
        self.assertEqual(started, ['one', 'two'])

    def test_binding_fields_do_not_rewrite_purchase_or_repair_prices(self):
        item = dict(__gcGetPropOrig=lambda key: dict(cost=0, g_cost=1037, g_transfer=1, repair_cost=138125).get(key))
        for prop, expected in (('cost', 0), ('g_cost', 1037), ('repair_cost', 138125), ('exchang', 1)):
            self.assertEqual(self.methods['getProp'].invoke(item, [prop]), expected)



    def test_a_and_g_sale_display_include_lost_factory_ceiling(self):
        for item, expected in (
            (self.item(max_break_abs=1500, max_break_cur=750, __break=375), 90737),
            (self.item(g_sale_unit=0, a_sale_unit=22750, max_break_abs=1500,
                       max_break_cur=750, __break=375), 5687),
        ):
            values = []
            card = dict(showItemSellMod=True, showHeapCount=True, attachIconEnabled=True,
                        __gcShowCostOrig=lambda *args: None,
                        price_mc=dict(gotoAndStop=lambda frame: None,
                                      fontContainer=dict(showValue=values.append)))
            self.methods['showCost'].invoke(card, [item, 'left'])
            self.assertEqual(values, [expected])

    def test_auction_damage_gate_retains_current_ceiling_rule(self):
        for brk, expected in ((100, False), (120, True)):
            item = self.item(max_break_abs=1500, max_break_cur=750, __break=brk)
            panel = dict(currDDOperation=dict(fromItem=item),
                         createAlert=lambda message: None)
            self.assertEqual(self.methods['checkDragItem'].invoke(panel, []), expected)


if __name__ == '__main__':
    run_cases(GoldCommerceClient)
