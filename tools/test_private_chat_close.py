"""Closing a private tab hides UI without deleting its bounded history."""
import unittest
from types import SimpleNamespace
import widescreen as w
from avm_test import Arr, Function
from chat_tabs import patches as private_patches
from private_chat_close import patches


class PrivateClose(unittest.TestCase):
    def setUp(self):
        self.saved=[]
        self.env=dict(_global=dict(__hcSafeFlush=lambda chat:self.saved.append(chat)))
        for name,params,body in private_patches(w.Asm,w.UNDEF)['globals']:
            self.env['_global'][name]=Function(params,body.assemble(),self.env)
        spec=patches(w.Asm,w.UNDEF)
        for name,params,body in spec['globals']:
            self.env['_global'][name]=Function(params,body.assemble(),self.env)
        self.methods={name:Function(params,body.assemble(),self.env)
                      for _,name,_,params,body in spec['wraps']}

    def test_close_active_tab_without_overflow_preserves_log_and_selects_remaining(self):
        rec=dict(group=-1,withID='Peer',logArr=Arr([dict(mess='keep me')]))
        chat=dict(channelList=Arr([rec]),getChannel=lambda *args:rec)
        mc=dict(group=-1,withID='Peer',where='main')
        selections=[];removed=[]
        tabs=dict(master=dict(chat=chat),currentChannel=mc,
                  mainList=Arr([dict(group=0,withID=None)]),stackList=Arr(),
                  removeChannel=lambda *args:removed.append(args),
                  setSizeStackMc=lambda:None,resizeStage=lambda:None,
                  initChannel=lambda *args:selections.append(args))
        self.methods['closeChannel'].invoke(tabs,[dict(target=mc)])
        self.assertTrue(rec['__pmClosed'])
        self.assertEqual(rec['logArr'][0]['mess'],'keep me')
        self.assertEqual(removed,[(-1,'Peer','main')])
        self.assertEqual(selections,[(0,None)])
        self.assertEqual(self.saved,[chat])

    def test_refresh_does_not_reopen_closed_private_but_manual_open_does(self):
        rec=dict(group=-1,withID='Peer',__pmClosed=True,logArr=Arr())
        events=[];ui=dict(__pmClosedRefreshOrig=lambda obj:events.append(obj))
        self.methods['refresh'].invoke(ui,[rec]);self.assertEqual(events,[])
        chat=dict(channelList=Arr([rec]))
        calls=[];tabs=dict(master=dict(chat=chat),__pmManualChannelOrig=lambda *args:calls.append(args))
        self.methods['newChannel'].invoke(tabs,[-1,'Peer'])
        self.assertFalse(rec['__pmClosed'])
        self.methods['refresh'].invoke(ui,[rec]);self.assertEqual(events,[rec])
        self.assertEqual(calls,[(-1,'Peer')])

    def test_close_public_tab_delegates_to_original(self):
        called=[];obj=dict(target=dict(group=0))
        self.methods['closeChannel'].invoke(dict(__pmCloseTabOrig=lambda obj:called.append(obj)),[obj])
        self.assertEqual(called,[obj])

    def test_cross_fits_actual_frame_and_repeated_layout_does_not_drift(self):
        for width in (100, 140):
            close = SimpleNamespace(_x=120)
            close.getBounds = lambda parent: dict(xMax=close._x + 5)
            frame = dict(getBounds=lambda parent: dict(xMax=width))
            field = SimpleNamespace(text='', _width=60, textWidth=20)
            mc = dict(close_btn=close, backButton=frame, pmNickname=field)
            for _ in range(2):
                self.env['_global']['__pmFitNickname'].invoke(self.env['_global'], [mc, 'Peer'])
                self.assertEqual(close.getBounds(mc)['xMax'], width - 5)
            self.assertEqual(field.text, 'Peer')

    def test_text_fits_available_space_before_cross_and_full_peer_is_unchanged(self):
        class Field:
            text=''
            _width=60
            @property
            def textWidth(self):return len(self.text)*7
        field=Field();peer='TesttesttesttesttesTestTestTest'
        self.env['_global']['__pmFitNickname'].invoke(self.env['_global'],[dict(pmNickname=field),peer])
        self.assertLessEqual(field.textWidth,field._width-4)
        self.assertTrue(field.text.endswith('…'))
        self.assertEqual(peer,'TesttesttesttesttesTestTestTest')


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from testkit import run_cases
    run_cases(PrivateClose)
