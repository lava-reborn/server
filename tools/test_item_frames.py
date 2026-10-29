"""Execute the emitted item-style refresh without changing item prices."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parent.parent / 'server')]
import widescreen as w
from avm_test import execute
from testkit import run_cases


class ItemFrames(unittest.TestCase):
    def panel(self, props, base='info_btn', frame=1, selected=False):
        calls = []
        panel = NS(item=NS(rootID=0, getProp=props.get), bg_mc=NS(bg=NS(_currentframe=frame)),
                   attachBackEnabled=True, toggled=selected, btnLinkID=base)
        panel.item.id = 17
        live = set()

        def attach():
            suffix = ('_premium' if props.get('premium') in (1, 2) else
                      '_gold' if props.get('g_cost') else '')
            panel.btnLinkID += suffix  # original appends to the current id
            name = panel.btnLinkID
            live.add(name)
            panel.info_btn = NS(_name=name, _currentframe=1,
                                removeMovieClip=lambda: live.discard(name),
                                onRelease=lambda: calls.append(('info', panel.item.id)))

        def highlight(value):
            panel.bg_mc.bg._currentframe = 2 if value else 1
            if getattr(panel, 'info_btn', None):
                panel.info_btn._currentframe = 2 if value else 1

        def repaint(root):
            calls.append(('paint', root))
            panel.bg_mc.bg = NS(_currentframe=1)

        setattr(panel, '__itemInfoAttachOrig', attach)
        setattr(panel, '__itemFrameUpdateOrig', lambda obj: None)
        setattr(panel, '__set__toggled_frame', highlight)
        panel.attachBack = repaint
        panel.attachBtn = lambda: execute(w.fn_item_info_refresh().assemble(), dict(this=panel))
        return panel, calls, live

    def update(self, panel):
        execute(w.fn_item_frame_refresh().assemble(), dict(
            this=panel, obj=None, lol=NS(core=NS(objects=NS(Item=NS(QUEST=-2))))))

    def test_gold_refresh_keeps_background_hover_and_info_button_click(self):
        props = dict(g_cost=0, premium=0, quest=0)
        panel, calls, live = self.panel(props, base='list_info_btn', frame=2)
        panel.attachBtn()
        self.assertEqual(panel.bg_mc.bg._currentframe, 2)
        props['g_cost'] = 2500
        self.update(panel)
        self.assertEqual(live, {'list_info_btn_gold'})
        self.assertEqual(panel.bg_mc.bg._currentframe, 2)
        self.assertEqual(panel.info_btn._currentframe, 2)
        panel.info_btn.onRelease()
        self.assertIn(('info', 17), calls)

    def test_selection_survives_repaint_and_unselected_stays_normal(self):
        for frame, selected, want in ((1, True, 2), (2, False, 2), (1, False, 1)):
            panel, _calls, _live = self.panel(dict(g_cost=2500, premium=0, quest=0),
                                            frame=frame, selected=selected)
            self.update(panel)
            self.assertEqual(panel.bg_mc.bg._currentframe, want)

    def test_button_transitions_do_not_stack_suffixes_or_leave_old_clips(self):
        for base in ('info_btn', 'list_info_btn'):
            props = dict(g_cost=0, premium=0, quest=0)
            panel, _calls, live = self.panel(props, base)
            for gold, premium, suffix in ((0, 0, ''), (100, 0, '_gold'),
                                          (100, 0, '_gold'), (100, 1, '_premium'),
                                          (100, 2, '_premium'), (0, 0, '')):
                props.update(g_cost=gold, premium=premium)
                panel.attachBtn()
                self.assertEqual(panel.btnLinkID, base + suffix)
                self.assertEqual(live, {base + suffix})

    def test_repeated_updates_do_not_recreate_unchanged_button(self):
        panel, calls, live = self.panel(dict(g_cost=2500, premium=0, quest=0))
        panel.attachBtn()
        self.update(panel)
        button = panel.info_btn
        calls.clear()
        for _ in range(10):
            self.update(panel)
        self.assertIs(panel.info_btn, button)
        self.assertEqual(calls, [])
        self.assertEqual(live, {'info_btn_gold'})

    def test_static_info_arrival_repaints_gold_once(self):
        props = dict(g_cost=0, premium=0, quest=0)
        calls = []
        item = NS(rootID=0, getProp=props.get)
        panel = NS(item=item, attachBackEnabled=True, bg_mc=NS(),
                   attachBack=lambda root: calls.append((root, props.copy())))
        setattr(panel, '__itemFrameUpdateOrig', lambda obj: None)
        env = dict(this=panel, obj=None, lol=NS(core=NS(objects=NS(Item=NS(QUEST=-2)))))
        setattr(panel, '__set__toggled_frame', lambda value: None)
        code = w.fn_item_frame_refresh().assemble()
        execute(code, env)
        props['g_cost'] = 2500
        execute(code, env)
        execute(code, env)  # ammunition/durability update: no style change
        props['g_cost'] = 3000
        execute(code, env)  # another positive price is the same visual style
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1][1]['g_cost'], 2500)
        self.assertEqual(props['g_cost'], 3000)
        props['quest'] = 1
        execute(code, env)
        self.assertEqual(calls[-1][0], -2)
        props['premium'] = 1
        execute(code, env)
        self.assertEqual(calls[-1][1]['premium'], 1)

    def test_disabled_background_still_updates_original_content(self):
        calls = []
        panel = NS(attachBackEnabled=False)
        setattr(panel, '__itemFrameUpdateOrig', calls.append)
        execute(w.fn_item_frame_refresh().assemble(), dict(this=panel, obj='update'))
        self.assertEqual(calls, ['update'])


if __name__ == '__main__':
    run_cases(ItemFrames)
