"""Execute nickname tooltip timing/cancellation bytecode without a Flash window."""
import unittest
import widescreen as w
from avm_test import Function
from private_chat_tooltips import patches


class NicknameTooltip(unittest.TestCase):
    def setUp(self):
        self.timers,self.cleared,self.shown=[],[],[]
        self.hints=dict(closeHint=lambda:None)
        self.hints['_showHint']=self.show
        self.env=dict(_global={},lol=dict(gpui=dict(HintManager=self.hints)),
                      TextFormat=lambda:{},clearInterval=self.cleared.append,
                      setInterval=self.schedule)
        spec=patches(w.Asm,w.UNDEF)
        for name,params,body in spec['globals']:
            self.env['_global'][name]=Function(params,body.assemble(),self.env)
        self.methods={name:Function(params,body.assemble(),self.env)
                      for _,name,_,params,body in spec['wraps']}

    def show(self,*args):
        self.shown.append(args)
        self.hints['hint_mc']={}

    def schedule(self,*args):
        self.timers.append(args)
        return len(self.timers)

    def button(self,nick='Тест Птав Тест'):
        return dict(__pmNick=nick,hintTitle_str=nick,_parent=dict(_visible=True),
                    _ymouse=5,_width=96,__pmTipOverOrig=lambda:None,
                    __pmTipOutOrig=lambda:None,__pmTipPressOrig=lambda:None,
                    __pmTipOutsideOrig=lambda:None)

    def test_waits_500ms_and_shows_full_nick(self):
        button=self.button()
        self.methods['onRollOver'].invoke(button,[])
        self.assertEqual(self.shown,[])
        fn,delay,target=self.timers[0]
        self.assertEqual(delay,500)
        fn.invoke(self.env['_global'],[target])
        self.assertEqual(self.shown,[('Тест Птав Тест',5,91)])
        self.assertTrue(self.hints['hint_mc']['__pmNicknameTip'])
        self.assertEqual(self.cleared,[1])

    def test_leaving_or_pressing_cancels_pending_hint(self):
        for method in ('onRollOut','onPress','onReleaseOutside'):
            button=self.button()
            self.methods['onRollOver'].invoke(button,[])
            fn,_,target=self.timers[-1]
            self.methods[method].invoke(button,[])
            fn.invoke(self.env['_global'],[target])
            self.assertEqual(self.shown,[])

    def test_other_buttons_keep_their_native_tooltip(self):
        called=[]
        button=dict(__pmTipOverOrig=lambda:called.append('native'))
        self.methods['onRollOver'].invoke(button,[])
        self.assertEqual(called,['native'])
        self.assertEqual(self.timers,[])

    def test_only_private_nickname_hints_use_tab_font_size(self):
        formats=[]
        tip=dict(__pmNicknameTip=True,title_str='А <B>',title_txt=dict(
            setTextFormat=lambda fmt:formats.append(fmt)),hintSize=lambda:None)
        self.methods['init'].invoke(tip,[])
        self.assertEqual(tip['title_txt']['text'],'А <B>')
        self.assertEqual(formats,[dict(font='Arial',size=11,bold=False)])
        called=[]
        self.methods['init'].invoke(dict(__pmTipInitOrig=lambda:called.append(1)),[])
        self.assertEqual(called,[1])


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from testkit import run_cases
    run_cases(NicknameTooltip)
