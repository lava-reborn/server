"""Run emitted legacy-link guards without opening a browser or touching auth."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import widescreen as w
from avm_test import execute
from testkit import run_cases


class LegacyLinks(unittest.TestCase):
    def test_profile_context_is_inert_and_detaches_only_its_own_listener(self):
        calls = []
        callback = object()
        target = dict(removeEventListener=lambda *args: calls.append(args))
        owner = dict(clickContext=callback,
                     __siteContextOrig=lambda event: self.fail('old profile route used'))
        execute(w.fn_site_context().assemble(), dict(this=owner, obj=dict(
            target=target, data=dict(function_str='actionProfile', param='Tester12'))))
        self.assertEqual(calls, [('selectItem', owner, callback)])

    def test_other_player_context_actions_keep_the_original_handler(self):
        calls = []
        owner = dict(__siteContextOrig=calls.append)
        for action in ('actionInspect', 'actionBarter', 'actionPrivat', 'actionInvite'):
            event = dict(data=dict(function_str=action))
            execute(w.fn_site_context().assemble(), dict(this=owner, obj=event))
            self.assertIs(calls[-1], event)

    def test_quest_markers_become_plain_text_without_altering_other_substitutions(self):
        calls = []
        text = '%startPutGold%Пополнить%endPutGold% %startProfile%Профиль%endProfile% %имя% <b>Прочее</b>'
        env = dict(this=dict(__siteQuestTextOrig=lambda value: calls.append(value) or value), strIn=text,
                   lol=dict(utils=dict(ParseString=dict(replaceAll=lambda value, old, new: value.replace(old, new)))))
        result = execute(w.fn_site_quest_text().assemble(), env)
        self.assertEqual(result, 'Пополнить Профиль %имя% <b>Прочее</b>')
        self.assertEqual(calls, [result])

    def test_existing_forum_link_still_uses_the_current_reborn_forum(self):
        calls = []
        owner = dict(getURL=lambda *args: calls.append(args), openClose=lambda: calls.append('close-menu'))
        execute(w.fn_open_forum(close_menu=True).assemble(), dict(this=owner))
        self.assertEqual(calls, ['close-menu', (w.FORUM_URL, '_blank')])
        self.assertNotIn('lava-online.ru', w.FORUM_URL)

    def test_hidden_links_preserve_native_init_and_leave_login_controls_unchanged(self):
        calls = []
        fields = ('lostPassw_btn', 'registration_btn', 'support_btn', 'i_have_problem_btn')
        owner = {name: dict(_visible=True) for name in (*fields, 'login_btn')}
        owner['__siteLoginInitOrig'] = lambda: calls.append('native-init')
        execute(w.fn_site_hide('__siteLoginInitOrig', (), fields).assemble(), dict(this=owner))
        self.assertEqual(calls, ['native-init'])
        self.assertTrue(owner['login_btn']['_visible'])
        self.assertTrue(all(not owner[name]['_visible'] for name in fields))


if __name__ == '__main__':
    run_cases(LegacyLinks)
