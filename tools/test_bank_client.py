"""Execute bank AVM1 helpers; no real player, database or load simulation."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Arr, Function
from testkit import run_cases
import widescreen as w
from bank_client import patches
from client_lifecycle import patches as lifecycle


class BankClient(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.keys = dict(checkFilter=lambda s: s == 'dialogue',
                         removeEventListener=lambda *a: self.calls.append('unsubscribe'))
        self.env = dict(_global={}, Number=float, String=str, Math=dict(ceil=lambda n: n),
                        lol=dict(core=dict(SceneShifter=dict(hotKeyManager=self.keys)),
                                 services=dict(HotKeyEvent=dict(KEY_PRESS='press', CTRL='ctrl', SHIFT='shift')),
                                 gpui=dict(DDEvents=dict(TRANSFER_SUCCESS='success', TRANSFER_ERROR='error'))))
        self.functions = {}
        for name, args, body in patches(w.Asm,w.UNDEF)['globals'] + lifecycle(w.Asm,w.UNDEF)['globals']:
            fn = Function(args,body.assemble(),self.env)
            self.functions[name] = self.env['_global'][name] = fn

    def call(self,name,obj,*args):
        return self.functions[name].invoke(obj,args)

    def test_f_selects_all_without_submitting_or_using_medicine(self):
        pan = dict(__bkQuantity=True,maxValue=1234,right_txt=dict(text='1'),changedRight=lambda: self.calls.append('changed'))
        self.call('__bkSelectAll',pan,dict(code=70))
        self.assertEqual(pan['right_txt']['text'],1234)
        self.assertEqual(self.calls,['changed'])
        self.call('__bkSelectAll',pan,dict(code=70))
        self.assertEqual(self.calls,['changed'])
        self.keys['checkFilter'] = lambda _: False
        self.call('__bkSelectAll',pan,dict(code=70))
        self.assertEqual(self.calls,['changed'])
        pan['__bkQuantity'] = False
        self.keys['checkFilter'] = lambda _: True
        self.call('__bkSelectAll',pan,dict(code=70))
        self.assertEqual(self.calls,['changed'])

    def test_e_confirms_quantity_once_and_only_in_bank_dialogue(self):
        pan = dict(__bkQuantity=True, right_txt=dict(text='12'),
                   sendObj=lambda: self.calls.append('submit'))
        self.keys['checkFilter'] = lambda _: False
        self.call('__bkSelectAll', pan, dict(code=69))
        self.assertEqual(self.calls, [])
        self.keys['checkFilter'] = lambda _: True
        pan['__bkQuantity'] = False
        self.call('__bkSelectAll', pan, dict(code=69))
        self.assertEqual(self.calls, [])
        pan['__bkQuantity'] = True
        self.call('__bkSelectAll', pan, dict(code=69))
        self.call('__bkSelectAll', pan, dict(code=69))
        self.assertEqual(self.calls, ['submit'])
        self.assertEqual(pan['right_txt']['text'], '12')

    def test_caption_uses_heading_font_and_native_text_rendering(self):
        import copy
        field = dict(setNewTextFormat=lambda f: None,
                     setTextFormat=lambda f: self.calls.append(copy.copy(f)))
        heading_format = dict(font='Arial', size=11, bold=True,
                              color=0xAAA68A, align='left')
        heading = dict(_width=170, _height=18, _x=20, embedFonts=True,
                       antiAliasType='advanced', gridFitType='pixel',
                       sharpness=0, thickness=0, textColor=0xAAA68A,
                       filters=['native shadow'],
                       getTextFormat=lambda: copy.copy(heading_format))
        hint = dict(caption=field,
                    createTextField=lambda *a: self.calls.append(a))
        pan = dict(__bkQuantity=True, label_txt=heading, apply_btn=dict(_y=120),
                   __bkQuantityInitOrig=lambda: None,
                   getNextHighestDepth=lambda: 10,
                   createEmptyMovieClip=lambda *a: hint)
        self.keys['addEventListener'] = lambda *a: None
        self.call('__bkQuantityInit', pan)
        self.assertEqual(field['text'], 'Выбрать всё [F]')
        self.assertEqual(self.calls[-1], dict(heading_format, align='center'))
        for key in ('embedFonts', 'antiAliasType', 'gridFitType', 'sharpness',
                    'thickness', 'textColor', 'filters'):
            self.assertEqual(field[key], heading[key])
        self.assertFalse(field['selectable'])
        self.assertEqual(hint['_y'], 97)

    def test_closed_quantity_panel_removes_caption_and_listener(self):
        pan = dict(__bkQuantity=True,
                   __bkHint=dict(removeMovieClip=lambda: self.calls.append('clip')),
                   __bkQuantityKillOrig=lambda: self.calls.append('native'))
        self.call('__bkQuantityKill', pan)
        self.assertEqual(self.calls, ['unsubscribe', 'clip', 'native'])
        self.assertFalse(pan['__bkQuantity'])
        self.call('__bkSelectAll', pan, dict(code=69))
        self.assertEqual(self.calls, ['unsubscribe', 'clip', 'native'])

    def test_transfer_ack_never_predicts_item_or_stack_mutation(self):
        panel=dict(__bkPending=True,transferStack=Arr([dict(item='old')]),
                   dispatchEvent=lambda e: self.calls.append(e['type']))
        self.call('__bkApply',panel,True)
        self.assertEqual(panel['transferStack'],[])
        self.assertEqual(self.calls,['success'])
        self.assertFalse(panel['__bkPending'])

    def test_shift_outside_bank_keeps_original_selection(self):
        self.call('__bkShift',dict(__bkShiftOrig=lambda e: self.calls.append(e)),dict(target=1))
        self.assertEqual(self.calls,[dict(target=1)])

    def test_duplicate_bank_size_does_not_refresh_item_twice(self):
        item=dict(rootID=4, heapSize=120)
        def update(props):
            self.calls.append(props['size'])
            item['heapSize']=props['size']
        item['updateProperties']=update
        bank=dict(visavisBag=dict(getItem=lambda oid:item),
                  __bkDeltaOrig=lambda obj:self.calls.append('native'))
        event=dict(param=dict(s_status=7,bank_delta='abc:120'))
        self.call('__bkDelta',bank,event)
        self.assertEqual(self.calls,[])
        event['param']['bank_delta']='abc:125'
        self.call('__bkDelta',bank,event)
        self.call('__bkDelta',bank,event)
        self.assertEqual(self.calls,[125])

    def test_filter_lookup_does_not_accumulate_modifier_entries(self):
        class Filter(Arr):
            def concat(self,other):
                return Arr(list(self)+list(other))
        base=Filter(['eat'])
        for _ in range(100):
            self.assertEqual(self.call('__lcFilter',dict(locationArr=base),'location'),['eat','ctrl','shift'])
        self.assertEqual(base,['eat'])


if __name__ == '__main__':
    run_cases(BankClient)
