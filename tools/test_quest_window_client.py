"""Execute the compiled quest-window lifecycle without replacing its queue."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import Arr, Function
from quest_window_client import patches
from testkit import run_cases


class QuestWindow(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.env = dict(lol=dict(core=dict(quests=dict(QuestEvent=dict(UPDATE='update')))))
        self.functions = {method: Function(params, body.assemble(), self.env)
                          for path, method, keep, params, body in patches(w.Asm, w.UNDEF)['wraps']}
        self.panel = dict(currentStatus='list',
                          questInspector=dict(removeEventListener=lambda *a:self.events.append(('remove', a))),
                          getAck='get-listener', takeAck='take-listener',
                          __qwInitOrig=lambda:self.events.append('init'),
                          __qwKillOrig=lambda:self.events.append('kill'),
                          __qwStatusOrig=lambda e:self.events.append(('native-status', len(e['quests']))),
                          rebuildQuestList=lambda:self.events.append('list'))

    def call(self, method, *args):
        return self.functions[method].invoke(self.panel, args)

    def test_initial_singleton_may_open_but_later_status_only_refreshes_list(self):
        self.call('init')
        for _ in range(3):
            self.call('questsStatusUpdate', dict(quests=Arr([dict(quest=1,type='get')])))
        self.assertEqual(self.events, ['init', ('native-status', 1), 'list', 'list'])

    def test_explicit_initial_description_is_not_opened_again_by_status(self):
        self.panel['__qwInitOrig']=lambda:self.panel.update(currentStatus='description')
        self.call('init')
        self.call('questsStatusUpdate', dict(quests=Arr([dict(quest=1)])))
        self.assertEqual(self.events, ['list'])

    def test_actions_and_acks_do_not_reenable_passive_auto_open(self):
        for method in ('getQuest','takeQuest','back','selectQuest','getAck','takeAck','questsUpdate'):
            self.events.clear()
            self.call('init')
            keep='__qw' + method[0].upper() + method[1:] + 'Orig'
            self.panel[keep]=lambda obj:self.events.append('native-action')
            self.call(method, {})
            self.call('questsStatusUpdate', dict(quests=Arr([dict(quest=1)])))
            self.assertEqual(self.events,['init','native-action','list'])

    def test_kill_removes_write_listeners_and_late_updates_cannot_revive_window(self):
        self.call('init')
        self.call('kill')
        self.call('kill')
        self.call('init')  # delayed doLater must not resurrect the clip
        self.call('getAck', {})
        self.call('takeAck', {})
        self.call('questsStatusUpdate', dict(quests=Arr([dict(quest=1)])))
        self.assertEqual(self.events[0], 'init')
        self.assertEqual([item[0] for item in self.events if isinstance(item,tuple)], ['remove','remove'])
        self.assertEqual(self.events[-1], 'kill')
        self.assertEqual(self.events.count('kill'), 1)

    def test_empty_status_keeps_native_close_or_service_window_behavior(self):
        self.call('init')
        self.panel['__qwInitial']=False
        self.call('questsStatusUpdate', dict(quests=Arr()))
        self.assertEqual(self.events,['init',('native-status',0)])


if __name__ == '__main__':
    run_cases(QuestWindow)
