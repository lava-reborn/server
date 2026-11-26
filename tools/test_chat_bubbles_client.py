"""Emitted AVM: remote chat IDs never attach speech to NPCs or other players."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from avm_test import Arr, Function
from chat_bubbles_client import patches
from testkit import run_cases
import widescreen as w


class ChatBubblesClient(unittest.TestCase):
    def setUp(self):
        path, method, saved, args, body = patches(w.Asm, w.UNDEF)['wraps'][0]
        self.function = Function(args, body.assemble(), {})
        self.calls = []
        self.sprite = dict(driver=dict(__rcPlayer=True, playerInfo=dict(name='VIKING')))
        self.scene = dict(helperObjects={17: self.sprite}, __cbChatOrig=self.calls.append)

    def event(self, group=0, row_group=0, name='VIKING'):
        return dict(group=group, logArr=Arr([dict(fromID=17, name=name, group=row_group, mess='hello')]))

    def test_only_local_chat_from_the_correct_player_keeps_native_bubble(self):
        event = self.event()
        self.function.invoke(self.scene, (event,))
        self.assertEqual(self.calls, [event])
        self.assertEqual(event['logArr'][0]['mess'], 'hello')

    def test_own_location_line_at_id_zero_also_keeps_the_native_bubble(self):
        self.scene['helperObjects'] = {0: self.sprite}
        event = self.event()
        event['logArr'][0]['fromID'] = 0
        self.function.invoke(self.scene, (event,))
        self.assertEqual(self.calls, [event])

    def test_clan_party_private_world_trade_and_system_chat_do_not_use_local_ids(self):
        for group in (1, 2, -1, 3, 4, 5, 6, None):
            self.function.invoke(self.scene, (self.event(group, group),))
        self.assertEqual(self.calls, [])

    def test_same_id_npc_mob_or_another_player_never_gets_the_phrase(self):
        for driver in (None, dict(playerInfo=dict(name='VIKING')),
                       dict(__rcPlayer=False, playerInfo=dict(name='VIKING')),
                       dict(__rcPlayer=True, playerInfo=dict(name='Other player'))):
            self.sprite['driver'] = driver
            self.function.invoke(self.scene, (self.event(),))
        self.assertEqual(self.calls, [])

    def test_mismatched_channel_empty_and_missing_entities_are_ignored(self):
        for event in (None, dict(group=0), dict(group=0, logArr=Arr([])), self.event(0, 2), self.event(name=None)):
            self.function.invoke(self.scene, (event,))
        self.scene['helperObjects'] = {}
        self.function.invoke(self.scene, (self.event(),))
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    run_cases(ChatBubblesClient)
