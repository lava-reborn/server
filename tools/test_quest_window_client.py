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
    def test_repeated_handins_keep_one_native_scan_and_preserve_the_queue(self):
        timers, cleared = set(), []
        queue = Arr([dict(q_type=7)])
        env = dict(clearInterval=lambda timer: (timers.discard(timer), cleared.append(timer)))
        spec = next(row for row in patches(w.Asm, w.UNDEF)['wraps']
                    if row[1] == 'requestAllNPC')
        callback = Function(spec[3], spec[4].assemble(), env)
        inspector = dict(updateTimerID=None, callStack=queue, callCount=1)
        def native():
            timer = len(cleared)
            timers.add(timer)
            inspector['updateTimerID'] = timer
        inspector['__qwRefreshNPCsOrig'] = native
        for _ in range(100):
            callback.invoke(inspector, [])
            self.assertEqual(timers, {inspector['updateTimerID']})
            self.assertIs(inspector['callStack'], queue)
            self.assertEqual(inspector['callCount'], 1)

    def test_location_departure_stops_only_its_scan_and_late_status_is_safe(self):
        inspector = dict(updateTimerID=42, updateNPCList=Arr([1, 2]), quester=dict(id=1),
                         callStack=Arr([dict(q_type=18201)]), callCount=1, currentQuests={3: 18202})
        queue = inspector['callStack']
        cleared, native = [], []
        env = dict(clearInterval=cleared.append, lol=dict(core=dict(quests=dict(QuestInspector=dict(
            getInstance=lambda: inspector)))))
        callbacks = {keep: Function(params, body.assemble(), env)
                     for path, method, keep, params, body in patches(w.Asm, w.UNDEF)['wraps']}
        callbacks['__qwLocationKillOrig'].invoke(dict(__qwLocationKillOrig=lambda: native.append('kill')), [])
        inspector['__qwStatusChangedOrig'] = lambda: native.append('status')
        callbacks['__qwStatusChangedOrig'].invoke(inspector, [])
        inspector['quester'] = dict(id=2)
        callbacks['__qwStatusChangedOrig'].invoke(inspector, [])
        self.assertEqual(cleared, [42])
        self.assertEqual(native, ['kill', 'status'])
        self.assertIs(inspector['callStack'], queue)
        self.assertEqual(inspector['callCount'], 1)
        self.assertEqual(inspector['currentQuests'], {3: 18202})
        self.assertEqual(list(inspector['updateNPCList']), [])

    def test_removing_contact_closes_quest_window_before_native_npc_destruction(self):
        for npc_id in (800001, 73, 1407):
            with self.subTest(npc=npc_id):
                contact = dict(id=npc_id, playerInfo=dict(ally=True))
                queue = Arr([dict(q_type=18211)])
                current = {142: dict(typeID=18211)}
                inspector = dict(quester=contact, questStatusList=Arr([18211]),
                                 callStack=queue, callCount=1, currentQuests=current)
                events = []
                env = dict(lol=dict(core=dict(quests=dict(QuestInspector=dict(
                    getInstance=lambda: inspector)), SceneShifter=dict(
                        closeWindow=lambda *args: events.append(('close', args))))))
                row = next(r for r in patches(w.Asm, w.UNDEF)['wraps'] if r[1] == 'removePlayer')
                def remove(entity_id):
                    self.assertIsNone(inspector['quester'])
                    self.assertEqual(list(inspector['questStatusList']), [])
                    events.append(('remove', entity_id))
                    contact.clear()
                    return 'native-result'
                callback = Function(row[3], row[4].assemble(), env)
                self.assertEqual(callback.invoke(dict(__qwNPCRemovedOrig=remove), [npc_id]),
                                 'native-result')
                self.assertEqual(events, [('close', ('quests', 'all')), ('remove', npc_id)])
                self.assertIs(inspector['callStack'], queue)
                self.assertEqual(inspector['callCount'], 1)
                self.assertIs(inspector['currentQuests'], current)

    def test_other_entity_removal_keeps_live_contact_and_pending_quest_replies(self):
        for contact in (None, dict(id=74)):
            with self.subTest(contact=contact):
                inspector = dict(quester=contact, questStatusList=Arr([18211]))
                events = []
                env = dict(lol=dict(core=dict(quests=dict(QuestInspector=dict(
                    getInstance=lambda: inspector)), SceneShifter=dict(
                        closeWindow=lambda *args: events.append('close')))))
                row = next(r for r in patches(w.Asm, w.UNDEF)['wraps'] if r[1] == 'removePlayer')
                callback = Function(row[3], row[4].assemble(), env)
                callback.invoke(dict(__qwNPCRemovedOrig=lambda eid: events.append(eid)), [73])
                self.assertEqual(events, [73])
                self.assertIs(inspector['quester'], contact)
                self.assertEqual(list(inspector['questStatusList']), [18211])

    def setUp(self):
        self.events = []
        self.env = dict(lol=dict(core=dict(quests=dict(QuestEvent=dict(UPDATE='update')))))
        self.functions = {method: Function(params, body.assemble(), self.env)
                          for path, method, keep, params, body in patches(w.Asm, w.UNDEF)['wraps']
                          if path == ('gpui', 'QuestInterface')}
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

    def test_late_quest_description_cannot_reopen_a_closed_npc_window(self):
        detached = []
        reopen = object()
        self.panel.update(currentQuest=dict(removeEventListener=lambda *args: detached.append(args)),
                          ReopenDescription=reopen,
                          __qwReopenDescriptionOrig=lambda obj: self.events.append('description'))
        self.call('init')
        self.call('ReopenDescription', dict(quest=1))
        self.assertIn('description', self.events)
        self.call('kill')
        self.assertEqual(detached, [('questLoaded', self.panel, reopen)])
        before = list(self.events)
        self.call('ReopenDescription', dict(quest=1))
        self.assertEqual(self.events, before)

    def test_empty_status_keeps_native_close_or_service_window_behavior(self):
        self.call('init')
        self.panel['__qwInitial']=False
        self.call('questsStatusUpdate', dict(quests=Arr()))
        self.assertEqual(self.events,['init',('native-status',0)])


if __name__ == '__main__':
    run_cases(QuestWindow)
