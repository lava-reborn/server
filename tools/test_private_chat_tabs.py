"""Execute private-chat AVM1 bytecode; no Flash UI or network needed.

Native methods are small contract doubles. Rendering, drag/overflow layout and
focus still require a manual game check; these tests verify routing and state.
"""
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[1] / 'server')]
import widescreen as w
from avm_test import Arr, Function
from chat_tabs import patches
from testkit import run_cases


class PrivateChatTabs(unittest.TestCase):
    def setUp(self):
        self.sent, self.callbacks, self.events = [], [], []
        self.online = True
        self.limit = 200
        self.env = dict(flash=dict(filters=dict(DropShadowFilter=lambda *args: args)), _global={}, Object=dict(registerClass=lambda *args: None), lol=dict(
            data=dict(GDString=lambda text: text),
            server=dict(mess=dict(CSM_ChatMessage=lambda to, group, mess:
                                  dict(to=to, group=group, mess=mess)),
                        XMLCCallStack=dict(addCall=lambda *args: self.callbacks.append(args))),
            gpui=dict(controls=dict(ChannelButton=object()), UserSettings=dict(NUMBER_OF_MESSAGE='number',
                                        getSetting=lambda key: self.limit))))
        patch = patches(w.Asm, w.UNDEF)
        self.methods = {(path, name): Function(params, body.assemble(), self.env)
                        for path, name, _, params, body in patch['wraps']}
        for name, params, body in patch['globals']:
            self.env['_global'][name] = Function(params, body.assemble(), self.env)
        self.chat = dict(channelList=Arr(), msgBuffer=Arr(), getName=lambda id: 'fallback')
        for (path, name), fn in self.methods.items():
            if path == ('core', 'Chat'):
                self.chat[name] = fn
        self.chat.update(__pmIsChatOrig=lambda group, id: 99,
                         __pmGetChannelOrig=lambda group, id: dict(group=group),
                         __pmDispatchOrig=lambda rec: self.events.append((rec['group'], rec.get('withID'))),
                         __pmIncomingOrig=lambda obj: self.native_message(
                             obj['param'].get('group', -1), obj['param'].get('from'),
                             None, obj['param']['entry']),
                         __pmOutgoingOrig=self.native_message,
                         __pmDeliveryOrig=self.native_delivery,
                         XMC=dict(Send=self.send_wire))

    def call(self, path, name, target, *args):
        return self.methods[(path, name)].invoke(target, args)

    def model(self, name, *args):
        return self.call(('core', 'Chat'), name, self.chat, *args)

    def ensure(self, peer):
        return self.env['_global']['__pmEnsure'].invoke(self.env['_global'], [self.chat, peer])

    def send_wire(self, obj):
        self.sent.append(obj)
        return self.online

    def native_delivery(self, obj):
        self.model('newMessage', self.chat.get('sendGroup'),
                   'server' if obj['param']['res'] == 9 else 0,
                   self.chat.get('sendWithName'), self.chat.get('sendMess'))

    def ack(self, result=0):
        event, target, fn, snapshot = self.callbacks.pop(0)
        self.assertEqual(event, 'cmdAck')
        fn.invoke(target, [dict(param=dict(res=result), data=snapshot)])

    def native_message(self, group, from_id, peer, text):
        # Same essential native contracts: normalize private group, assemble
        # fragments by group/sender, then isChat -> append -> dispatchChannel.
        group = -1 if group is None else group
        if text.startswith('^'):
            mark, text = text[1:].split('^', 1)
            buf = self.chat['msgBuffer']
            if not mark.endswith('L'):
                buf.push(text)
                return
            text = ''.join(buf) + text
            buf.clear()
        index = self.model('isChat', group, peer if peer is not None else from_id)
        if index is None:
            rec = dict(group=group, logArr=Arr())
            self.chat['channelList'].push(rec)
        else:
            rec = self.chat['channelList'][index]
        rec['logArr'].push(dict(mess=text, fromID=from_id, to_name=peer))
        self.model('dispatchChannel', rec)

    def incoming(self, nick, text, id=21):
        self.model('userMsg', dict(param=dict(nick=nick, entry=text, **{'from': id})))

    def test_two_peers_have_separate_logs_incoming_and_outgoing(self):
        self.incoming('Лейкан', 'hello')
        self.incoming('STALKER', 'other', 22)
        self.model('sendMessage', dict(group=-1, toID='Лейкан', mess='reply'))
        self.ack()
        self.assertEqual([m['mess'] for m in self.ensure('Лейкан')['logArr']], ['hello', 'reply'])
        self.assertEqual([m['mess'] for m in self.ensure('STALKER')['logArr']], ['other'])
        self.assertEqual(self.events, [(-1, 'Лейкан'), (-1, 'STALKER'), (-1, 'Лейкан')])
        self.assertIsNone(self.chat['__pmPeer'])

    def test_same_nick_survives_location_id_change_and_special_names(self):
        for nick in ('constructor', '__proto__', 'Игрок с пробелом'):
            self.incoming(nick, 'first', 12)
            self.incoming(nick, 'second', 89)
            self.assertEqual(len(self.ensure(nick)['logArr']), 2)
        self.assertEqual(len(self.chat['channelList']), 3)

    def test_fast_sends_keep_each_acks_recipient_body_and_offline_result(self):
        obj = dict(to='A', mess='one')
        self.model('sendMessage', obj)
        obj.update(to='B', mess='two')
        self.model('sendMessage', obj)
        obj['mess'] = 'changed after send'
        self.assertEqual(len(self.callbacks), 2)
        self.ack()
        self.ack(9)
        self.assertEqual(self.ensure('A')['logArr'][0]['mess'], 'one')
        self.assertEqual(self.ensure('B')['logArr'][0], dict(mess='two', fromID='server', to_name='B'))
        self.assertEqual(self.sent, [dict(to='A', group=None, mess='one'),
                                     dict(to='B', group=None, mess='two')])

    def test_case_variants_of_same_recipient_reuse_tab_key(self):
        self.model('sendMessage', dict(to='лейкан', mess='one'))
        self.ack()
        self.incoming('Лейкан', 'two')
        self.assertEqual(len(self.chat['channelList']), 1)
        self.assertEqual(self.events, [(-1, 'лейкан'), (-1, 'лейкан')])
        self.assertIs(self.model('getChannel', -1, 'ЛЕЙКАН'), self.ensure('лейкан'))

    def test_failed_transport_send_does_not_add_ack_callback(self):
        self.online = False
        self.model('sendMessage', dict(to='A', mess='text'))
        self.assertEqual(self.callbacks, [])
        self.assertEqual(self.chat['channelList'], [])

    def test_public_channels_use_original_lookup_and_wire_group_zero(self):
        self.assertEqual(self.model('isChat', 0, None), 99)
        self.assertEqual(self.model('getChannel', 6, None), dict(group=6))
        self.model('sendMessage', dict(group=0, mess='location'))
        self.assertEqual(self.sent, [dict(to=None, group=0, mess='location')])
        # Native delivery remains unchanged; public ack never acquires a peer.
        self.chat['__pmDeliveryOrig'] = lambda obj: self.assertEqual(self.chat['sendGroup'], 0)
        self.ack()
        self.assertEqual(self.chat['channelList'], [])

    def test_interleaved_long_messages_keep_independent_buffers(self):
        public_buffer = self.chat['msgBuffer']
        self.model('newMessage', None, 0, 'A', '^0^A1')
        self.model('newMessage', None, 0, 'B', '^0^B1')
        self.incoming('C', '^0^C1')
        self.model('newMessage', None, 0, 'A', '^1L^A2')
        self.model('newMessage', None, 0, 'B', '^1L^B2')
        self.incoming('C', '^1L^C2', 99)
        for nick in 'ABC':
            self.assertEqual(self.ensure(nick)['logArr'][0]['mess'], nick + '1' + nick + '2')
        self.assertIs(self.chat['msgBuffer'], public_buffer)
        self.assertEqual(public_buffer, [])

    def test_private_history_bound_applies_without_opening_tab(self):
        self.limit = 2
        for text in ('one', 'two', 'three'):
            self.incoming('A', text)
        self.assertEqual([m['mess'] for m in self.ensure('A')['logArr']], ['two', 'three'])
        self.limit = -2
        self.incoming('A', 'four')
        self.assertEqual(len(self.ensure('A')['logArr']), 3)

    def test_no_shared_private_placeholder_and_native_public_tabs_unchanged(self):
        calls = []
        tabs = dict(master=dict(chat=self.chat, getPlayer=lambda id: dict(playerInfo=dict(name='B'))),
                    __pmNewChannelOrig=lambda *args: calls.append(args),
                    __pmLinkageOrig=lambda group: 'public')
        self.call(('gpui', 'ChatChannelPan'), 'newChannel', tabs, -1, None)
        self.call(('gpui', 'ChatChannelPan'), 'newChannel', tabs, -1, 'A')
        self.call(('gpui', 'ChatChannelPan'), 'newChannel', tabs, 0, None)
        self.call(('gpui', 'ChatChannelPan'), 'newChannel', tabs, None, 42)
        self.assertEqual(calls, [(-1, 'A'), (0, None), (-1, 'B')])
        self.assertEqual(self.ensure('B')['logArr'], [])
        self.assertEqual(self.call(('gpui', 'ChatChannelPan'), 'getLinkage', tabs, -1), '__pm_channel_btn')
        self.assertEqual(self.call(('gpui', 'ChatChannelPan'), 'getLinkage', tabs, 0), 'public')

    def test_main_and_overflow_private_tabs_get_nick_without_changing_public_caption(self):
        for method, original in (('createChannel', '__pmCreateOrig'), ('addToStack', '__pmStackOrig')):
            movie = dict(backButton={}, pmNickname={})
            tabs = {original: lambda *args: movie}
            self.call(('gpui', 'ChatChannelPan'), method, tabs, -1, 'Лейкан', None, None)
            self.assertEqual(movie['pmNickname']['text'], 'Лейкан')
            self.assertEqual(movie['pmNickname']['autoSize'], 'none')
            self.assertEqual(movie['backButton']['hintTitle_str'], 'Лейкан')
            self.assertEqual(movie['pmNickname']['filters'], [(1,45,0,.4,1,1,1,1,False,False,False)])
            movie.clear()
            self.call(('gpui', 'ChatChannelPan'), method, tabs, 0, None, None, None)
            self.assertEqual(movie, {})

    def test_long_nick_has_short_caption_and_full_tooltip(self):
        nick = 'TesttesttesttesttesTestTestTest'
        movie = dict(backButton={}, pmNickname={})
        tabs = dict(__pmCreateOrig=lambda *args: movie)
        self.call(('gpui', 'ChatChannelPan'), 'createChannel', tabs, -1, nick, None, None)
        self.assertEqual(movie['pmNickname']['text'], nick[:11] + '…')
        self.assertEqual(movie['backButton']['hintTitle_str'], nick)

    def test_open_peer_creates_empty_model_and_selects_native_tab(self):
        calls = []
        ui = dict(chat=self.chat, chatChannelPan=dict(newChannel=lambda *args: calls.append(args)),
                  gotoLastSymbol=lambda: calls.append('focus'))
        self.call(('services', 'ChatPan'), 'selectPrivateUserNick', ui, 'A')
        self.assertEqual(calls, [(-1, 'A'), 'focus'])
        self.assertEqual(self.ensure('A')['logArr'], [])

    def test_context_menu_by_id_opens_named_dialog(self):
        calls = []
        ui = dict(getName=lambda id: 'A', selectPrivateUserNick=lambda nick: calls.append(nick),
                  master=dict(getPlayer=lambda id: dict(playerInfo=dict(name='B'))))
        self.call(('services', 'ChatPan'), 'setPrivateToInputStr', ui, 42)
        self.call(('services', 'ChatPan'), 'startChat', ui, dict(target=dict(data=dict(id=43))))
        self.assertEqual(calls, ['A', 'B'])

    def test_drafts_are_separate_and_active_message_refresh_keeps_typing(self):
        for nick in 'AB':
            self.ensure(nick)
        calls = []
        ui = dict(chat=self.chat, chatInput=dict(text='public draft'),
                  __pmShowOrig=lambda obj: calls.append(obj))
        def show(group, peer=None):
            self.call(('services', 'ChatPan'), 'showChannel', ui, dict(group=group, withID=peer))
        show(-1, 'A')
        self.assertEqual(ui['chatInput']['text'], '')
        ui['chatInput']['text'] = 'draft A'
        show(-1, 'A')
        self.assertEqual(ui['chatInput']['text'], 'draft A')
        show(-1, 'B')
        self.assertEqual(ui['chatInput']['text'], '')
        ui['chatInput']['text'] = 'draft B'
        show(-1, 'A')
        self.assertEqual(ui['chatInput']['text'], 'draft A')
        show(0)
        self.assertEqual(ui['chatInput']['text'], 'public draft')
        self.assertEqual(self.ensure('B')['draft'], 'draft B')

    def test_long_send_freezes_private_peer_and_does_not_rewrite_explicit_address(self):
        calls = []
        ui = dict(chatChannelPan=dict(currentChannel=dict(group=-1, withID='A')),
                  __pmSplitOrig=lambda text: calls.append(text))
        for text in ('long text', 'private B: other text'):
            self.call(('services', 'ChatPan'), 'sendInStack', ui, text)
        self.assertEqual(calls, ['private A: long text', 'private B: other text'])
        ui['chatChannelPan']['currentChannel']['group'] = 0
        self.call(('services', 'ChatPan'), 'sendInStack', ui, 'public')
        self.assertEqual(calls[-1], 'public')

    def test_new_manual_message_cannot_overwrite_unsent_fragments(self):
        calls = []
        ui = dict(stackArr=Arr(['queued']), __pmInputOrig=lambda *args: calls.append(args))
        self.call(('services', 'ChatPan'), 'sendMessage', ui, None, None)
        self.assertEqual(calls, [])
        self.call(('services', 'ChatPan'), 'sendMessage', ui, None, '^1L^final fragment')
        self.assertEqual(len(calls), 1)
        ui['stackArr'].clear()
        self.call(('services', 'ChatPan'), 'sendMessage', ui, None, None)
        self.assertEqual(len(calls), 2)

    def test_incoming_reopens_closed_peer_but_outgoing_ack_does_not(self):
        rec=self.ensure('Peer')
        rec['__pmClosed']=True
        self.model('newMessage',None,0,'Peer','delayed own acknowledgement')
        self.assertTrue(rec['__pmClosed'])
        self.chat['findTerminators']=lambda text:dict(index=None)
        self.incoming('Peer','new incoming message')
        self.assertFalse(rec['__pmClosed'])

    def test_feature_is_present_in_final_injection(self):
        emitted = w.injected()
        for name in ('__pmFind', '__pmEnsure', '__pmIncomingOrig', '__pmInputOrig', '__pmDeliveryOrig'):
            self.assertIn(name.encode(), emitted)


if __name__ == '__main__':
    run_cases(PrivateChatTabs)
