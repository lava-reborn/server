"""Native named private-chat tabs, built with the client's existing AVM1 UI.

No server/history store. Keep the original renderer, channel overflow, input
focus filter and cmdAck FIFO; attach each delivery's immutable send context.
"""


def patches(Asm, UNDEF):
    def original(a, name, params):
        for param in reversed(params):
            a.var(param)
        a.push(len(params)).var('this').push(name).op('callmethod')

    def find(a, chat='chat', peer='peer'):
        a.var(peer).var(chat).push(2).var('_global').push('__pmFind').op('callmethod')

    def finder():
        a = Asm()
        a.var('peer').op('not').iftrue('missing')
        a.push('i', 0).op('definelocal')
        a.label('loop')
        a.var('i').var('chat').member('channelList', 'length').op('less2').op('not').iftrue('missing')
        a.push('rec').var('chat').member('channelList').var('i').op('getmember').op('definelocal')
        a.var('rec').member('group').push(-1).op('equals2').op('not').iftrue('next')
        a.push(0).var('rec').member('withID').push('toLowerCase').op('callmethod')
        a.push(0).var('peer').push('toLowerCase').op('callmethod').op('equals2').op('not').iftrue('next')
        a.var('i').op('return')
        a.label('next').push('i').var('i').push(1).op('add2').op('definelocal')
        a.push(True).iftrue('loop')
        a.label('missing').push(UNDEF).op('return')
        return a

    def ensure():
        a = Asm()
        a.push('index'); find(a); a.op('definelocal')
        a.var('index').push(UNDEF).op('equals2').iftrue('new')
        a.var('chat').member('channelList').var('index').op('getmember').op('return')
        a.label('new')
        a.push('rec', 'group', -1, 'withID').var('peer').push('name').var('peer')
        a.push('logArr', 0).op('initarray').push(4).op('initobject').op('definelocal')
        a.var('rec').push(1).var('chat').member('channelList').push('push').op('callmethod').op('pop')
        a.var('rec').op('return')
        return a

    def is_chat():
        a = Asm()
        a.var('isChat_group').push(-1).op('equals2').iftrue('private')
        original(a, '__pmIsChatOrig', ('isChat_group', 'isChat_id')); a.op('return')
        a.label('private').push('chat').var('this').op('definelocal')
        a.push('peer').var('this').member('__pmPeer').op('definelocal')
        a.var('peer').iftrue('find')
        a.push('peer').var('isChat_id').op('definelocal')
        a.label('find'); find(a); a.op('return')
        return a

    def get_channel():
        a = Asm()
        a.var('get_group').push(-1).op('equals2').iftrue('private')
        original(a, '__pmGetChannelOrig', ('get_group', 'get_withID')); a.op('return')
        a.label('private').push('chat').var('this').op('definelocal')
        a.push('peer').var('get_withID').op('definelocal')
        a.push('index'); find(a); a.op('definelocal')
        a.var('this').member('channelList').var('index').op('getmember').op('return')
        return a

    def context(incoming):
        a = Asm()
        a.push('previous').var('this').member('__pmPeer').op('definelocal')
        if incoming:
            a.var('obj').member('param', 'group').push(-1).op('equals2').iftrue('private')
            a.var('obj').member('param', 'group').push(UNDEF).op('equals2').op('not').iftrue('call')
            a.var('obj').member('param', 'from').push(UNDEF).op('equals2').iftrue('call')
            a.label('private').push('peer').var('obj').member('param', 'nick').op('definelocal')
            a.var('peer').iftrue('set')
            a.push('peer').var('obj').member('param', 'from').push(1).var('this').push('getName').op('callmethod').op('definelocal')
        else:
            a.var('new_group').push(-1).op('equals2').iftrue('private')
            a.var('new_group').push(UNDEF).op('equals2').op('not').iftrue('call')
            a.label('private').push('peer').var('new_withName').op('definelocal')
        a.label('set').var('this').push('__pmPeer').var('peer').op('setmember')
        # Original multipart assembly keys outgoing fragments by our own ID.
        # Give each peer its own buffer, including interleaved delivery acks.
        a.push('bufferBefore').var('this').member('msgBuffer').op('definelocal')
        a.push('record').var('peer').var('this').push(2).var('_global').push('__pmEnsure').op('callmethod').op('definelocal')
        a.var('this').push('__pmPeer').var('record').member('withID').op('setmember')
        if incoming:
            a.var('record').member('__pmClosed').op('not').iftrue('open_checked')
            a.push('fragment').var('obj').member('param', 'entry').push(1)
            a.var('this').push('findTerminators').op('callmethod').op('definelocal')
            a.var('fragment').member('index').push(UNDEF).op('equals2').iftrue('reopen')
            a.var('fragment').member('last_str').op('not').iftrue('open_checked')
            a.label('reopen').var('record').push('__pmClosed', False).op('setmember')
            a.label('open_checked')
        a.var('record').member('__pmBuffer').iftrue('buffer')
        a.var('record').push('__pmBuffer', 0).op('initarray').op('setmember')
        a.label('buffer').var('this').push('msgBuffer').var('record').member('__pmBuffer').op('setmember')
        a.label('call')
        original(a, '__pmIncomingOrig' if incoming else '__pmOutgoingOrig',
                 ('obj',) if incoming else ('new_group', 'new_fromID', 'new_withName', 'new_mess'))
        a.op('pop')
        a.var('record').op('not').iftrue('restore')
        a.var('this').push('msgBuffer').var('bufferBefore').op('setmember')
        a.label('restore')
        a.var('this').push('__pmPeer').var('previous').op('setmember')
        return a

    def dispatch():
        a = Asm()
        a.var('disObj').member('group').push(-1).op('equals2').op('not').iftrue('call')
        a.push('peer').var('this').member('__pmPeer').op('definelocal')
        a.var('peer').op('not').iftrue('limit')
        for field in ('name', 'withID'):
            a.var('disObj').push(field).var('peer').op('setmember')
        a.label('limit')
        a.push('limit').var('lol').member('gpui', 'UserSettings', 'NUMBER_OF_MESSAGE').push(1)
        a.var('lol').member('gpui', 'UserSettings').push('getSetting').op('callmethod').op('definelocal')
        a.push(0).var('limit').op('less2').iftrue('clamp')
        a.push('limit', 200).op('definelocal')
        a.label('clamp').push(1000).var('limit').op('less2').op('not').iftrue('trim')
        a.push('limit', 1000).op('definelocal')
        a.label('trim').push('log').var('disObj').member('logArr').op('definelocal')
        a.var('limit').var('log').member('length').op('less2').op('not').iftrue('call')
        a.var('log').member('length').var('limit').op('subtract').push(0, 2)
        a.var('log').push('splice').op('callmethod').op('pop')
        a.label('call'); original(a, '__pmDispatchOrig', ('disObj',)); a.op('pop')
        return a

    def send():
        # Keep the original wire protocol, but store immutable routing data
        # in this command's own existing FIFO callback (no extra callbacks).
        a = Asm()
        a.var('obj').member('group').push(-1).op('equals2').op('not').iftrue('snapshot')
        a.var('obj').push('to').var('obj').member('toID').op('setmember')
        a.var('obj').push('group', UNDEF).op('setmember')
        a.label('snapshot')
        a.push('sent', 'group').var('obj').member('group').push('to').var('obj').member('to')
        a.push('mess').var('obj').member('mess').push(3).op('initobject').op('definelocal')
        a.push('to', UNDEF).op('definelocal')
        a.var('sent').member('to').push(UNDEF).op('equals2').iftrue('message')
        a.push('to').var('sent').member('to').push(1).var('lol').member('data').push('GDString').op('newmethod').op('definelocal')
        a.label('message')
        a.push('mess').var('sent').member('mess').push(1).var('lol').member('data').push('GDString').op('newmethod').op('definelocal')
        a.push('wire').var('mess').var('sent').member('group').var('to').push(3)
        a.var('lol').member('server', 'mess').push('CSM_ChatMessage').op('newmethod').op('definelocal')
        a.var('wire').push(1).var('this').member('XMC').push('Send').op('callmethod').op('not').iftrue('out')
        a.var('sent').var('this').member('delivery').var('this').push('cmdAck', 4)
        a.var('lol').member('server', 'XMLCCallStack').push('addCall').op('callmethod').op('pop')
        a.label('out')
        return a

    def delivery():
        a = Asm()
        a.var('obj').member('data').op('not').iftrue('call')
        for field, source in (('sendGroup','group'), ('sendWithName','to'),
                              ('sendMess','mess'), ('sendMessUnescape','mess')):
            a.var('this').push(field).var('obj').member('data',source).op('setmember')
        a.label('call'); original(a, '__pmDeliveryOrig', ('obj',)); a.op('pop')
        return a

    def no_placeholder():
        a = Asm()
        # Party context menus still use the legacy (undefined, entity ID).
        a.var('group').push(UNDEF).op('equals2').op('not').iftrue('check')
        a.var('withID').push(UNDEF).op('equals2').iftrue('call')
        a.push('withID').var('withID').push(1).var('this').member('master').push('getPlayer').op('callmethod').member('playerInfo', 'name').op('definelocal')
        a.push('group', -1).op('definelocal')
        a.label('check').var('group').push(-1).op('equals2').op('not').iftrue('call')
        a.var('withID').op('not').iftrue('out')
        a.push('withID').var('withID').var('this').member('master', 'chat').push(2).var('_global').push('__pmEnsure').op('callmethod').member('withID').op('definelocal')
        a.label('call'); original(a, '__pmNewChannelOrig', ('group', 'withID')); a.op('pop')
        a.label('out')
        return a

    def linkage():
        a = Asm()
        a.var('str').push(-1).op('equals2').op('not').iftrue('call')
        # Separate artwork: clan button chrome without its baked-in caption.
        a.var('lol').member('gpui', 'controls', 'ChannelButton').push('__pm_channel_btn', 2)
        a.var('Object').push('registerClass').op('callmethod').op('pop')
        a.push('__pm_channel_btn').op('return')
        a.label('call'); original(a, '__pmLinkageOrig', ('str',)); a.op('return')
        return a

    def caption(stacked):
        a = Asm()
        a.push('mc')
        original(a, '__pmStackOrig' if stacked else '__pmCreateOrig', ('group','withID','pos','insert'))
        a.op('definelocal')
        a.var('group').push(-1).op('equals2').op('not').iftrue('out')
        a.var('mc').op('not').iftrue('out')
        # This is the sole text field; never add a second GPUIButton label.
        # Fixed-size overlay: text alignment must not be changed by autoSize.
        for key, value in (('autoSize', 'none'), ('antiAliasType', 'advanced'),
                           ('gridFitType', 'pixel'), ('selectable', False)):
            a.var('mc').member('pmNickname').push(key, value).op('setmember')
        a.push('display').var('withID').op('definelocal')
        a.push(14).var('display').member('length').op('less2').op('not').iftrue('text')
        a.push('display', 11, 0, 2).var('withID').push('substring').op('callmethod')
        a.push('…').op('add2').op('definelocal')
        a.label('text').var('mc').member('pmNickname').push('text').var('display').op('setmember')
        a.var('mc').member('backButton').push('hintTitle_str').var('withID').op('setmember')
        a.var('mc').member('backButton').push('__pmNick').var('withID').op('setmember')
        a.var('mc').member('backButton').push('onUnload').var('_global').member('__pmTipUnload').op('setmember')
        # A one-pixel soft shadow on the text overlay only, never the artwork.
        a.var('mc').member('pmNickname').push('filters')
        a.push(False, False, False, 1, 1, 1, 1, 40, 100).op('divide')
        a.push(0, 45, 1, 11).var('flash').member('filters').push('DropShadowFilter').op('newmethod')
        a.push(1).op('initarray').op('setmember')
        a.label('out').var('mc').op('return')
        return a

    def open_peer():
        a = Asm()
        a.var('name_str').op('not').iftrue('out')
        a.push('name_str').var('name_str').var('this').member('chat').push(2).var('_global').push('__pmEnsure').op('callmethod').member('withID').op('definelocal')
        a.var('name_str').push(-1, 2).var('this').member('chatChannelPan').push('newChannel').op('callmethod').op('pop')
        a.push(0).var('this').push('gotoLastSymbol').op('callmethod').op('pop')
        a.label('out')
        return a

    def open_id():
        a = Asm()
        a.var('withID').push(1).var('this').push('getName').op('callmethod')
        a.push(1).var('this').push('selectPrivateUserNick').op('callmethod').op('pop')
        return a

    def start_chat():
        a = Asm()
        a.push('nick').var('obj').member('target','data','id').push(1).var('this').member('master').push('getPlayer').op('callmethod').member('playerInfo','name').op('definelocal')
        a.var('nick').push(1).var('this').push('selectPrivateUserNick').op('callmethod').op('pop')
        return a

    def show():
        a = Asm()
        a.push('peer', UNDEF).op('definelocal')
        a.var('obj').member('group').push(-1).op('equals2').op('not').iftrue('check')
        a.push('peer').var('obj').member('withID').op('definelocal')
        a.label('check')
        a.var('peer').var('this').member('__pmCurrent').op('equals2').iftrue('same')
        a.push('chat').var('this').member('chat').op('definelocal')
        a.push('previous').var('this').member('__pmCurrent').op('definelocal')
        a.var('previous').op('not').iftrue('public')
        a.push('peerSave').var('peer').op('definelocal')
        a.push('peer').var('previous').op('definelocal')
        a.push('idx'); find(a); a.op('definelocal')
        a.var('idx').push(UNDEF).op('equals2').iftrue('restore_peer')
        a.var('chat').member('channelList').var('idx').op('getmember').push('draft')
        a.var('this').member('chatInput','text').op('setmember')
        a.label('restore_peer').push('peer').var('peerSave').op('definelocal')
        a.push(True).iftrue('load')
        a.label('public').var('this').push('__pmPublicDraft').var('this').member('chatInput','text').op('setmember')
        a.label('load')
        original(a, '__pmShowOrig', ('obj',)); a.op('pop')
        a.push('text').var('this').member('__pmPublicDraft').op('definelocal')
        a.var('peer').op('not').iftrue('write')
        a.push('idx'); find(a); a.op('definelocal')
        a.push('text').var('chat').member('channelList').var('idx').op('getmember').member('draft').op('definelocal')
        a.label('write').var('text').iftrue('set')
        a.push('text','').op('definelocal')
        a.label('set').var('this').member('chatInput').push('text').var('text').op('setmember')
        a.var('this').push('__pmCurrent').var('peer').op('setmember')
        a.push(True).iftrue('out')
        a.label('same'); original(a, '__pmShowOrig', ('obj',)); a.op('pop')
        a.label('out')
        return a

    def send_input():
        a = Asm()
        a.var('_messStr').push(UNDEF).op('equals2').op('not').iftrue('call')
        a.var('this').member('stackArr').op('not').iftrue('call')
        a.push(0).var('this').member('stackArr', 'length').op('less2').iftrue('out')
        a.label('call'); original(a, '__pmInputOrig', ('obj', '_messStr')); a.op('pop')
        a.label('out')
        return a

    def stack():
        a = Asm()
        a.var('this').member('chatChannelPan','currentChannel','group').push(-1).op('equals2').op('not').iftrue('call')
        a.push('private ', 1).var('str').push('indexOf').op('callmethod').push(0).op('equals2').iftrue('call')
        a.push('str','private ').var('this').member('chatChannelPan','currentChannel','withID').op('add2')
        a.push(': ').op('add2').var('str').op('add2').op('definelocal')
        a.label('call'); original(a, '__pmSplitOrig', ('str',)); a.op('pop')
        return a

    chat=('core','Chat')
    ui=('services','ChatPan')
    tabs=('gpui','ChatChannelPan')
    wraps=(
        (chat,'isChat','__pmIsChatOrig',('isChat_group','isChat_id'),is_chat()),
        (chat,'getChannel','__pmGetChannelOrig',('get_group','get_withID'),get_channel()),
        (chat,'userMsg','__pmIncomingOrig',('obj',),context(True)),
        (chat,'newMessage','__pmOutgoingOrig',('new_group','new_fromID','new_withName','new_mess'),context(False)),
        (chat,'dispatchChannel','__pmDispatchOrig',('disObj',),dispatch()),
        (chat,'sendMessage','__pmSendOrig',('obj',),send()),
        (chat,'delivery','__pmDeliveryOrig',('obj',),delivery()),
        (tabs,'newChannel','__pmNewChannelOrig',('group','withID'),no_placeholder()),
        (tabs,'getLinkage','__pmLinkageOrig',('str',),linkage()),
        (tabs,'createChannel','__pmCreateOrig',('group','withID','pos','insert'),caption(False)),
        (tabs,'addToStack','__pmStackOrig',('group','withID','pos','insert'),caption(True)),
        (ui,'selectPrivateUserNick','__pmOpenOrig',('name_str',),open_peer()),
        (ui,'startChat','__pmStartOrig',('obj',),start_chat()),
        (ui,'setPrivateToInputStr','__pmOpenIdOrig',('withID',),open_id()),
        (ui,'showChannel','__pmShowOrig',('obj',),show()),
        (ui,'sendInStack','__pmSplitOrig',('str',),stack()),
        (ui,'sendMessage','__pmInputOrig',('obj','_messStr'),send_input()),
    )
    return dict(globals=(('__pmFind',('chat','peer'),finder()),
                         ('__pmEnsure',('chat','peer'),ensure())),wraps=wraps)


def artwork(tags):
    """Clone clan chrome, replacing its baked caption with one native-font field.

    Never change the original clan symbol. Rebuild our two definitions from
    the source on every invocation so patching an already patched SWF is safe.
    """
    import struct
    import widescreen as w
    from swfgen import rect

    def exports(payload):
        at = 2
        for _ in range(struct.unpack_from('<H', payload)[0]):
            cid = struct.unpack_from('<H', payload, at)[0]
            at += 2
            end = payload.index(b'\0', at)
            yield payload[at:end].decode('utf-8'), cid
            at = end + 1

    owned = {'__pm_channel_btn', '__pm_nickname_text'}
    old_ids = {cid for code, payload, _ in tags if code == 56
               for name, cid in exports(payload) if name in owned}
    clean = []
    for code, payload, long_header in tags:
        if code in (37, 39) and struct.unpack_from('<H', payload)[0] in old_ids:
            continue
        if code == 56:
            rows = [(name, cid) for name, cid in exports(payload) if name not in owned]
            if not rows:
                continue
            payload = struct.pack('<H', len(rows)) + b''.join(
                struct.pack('<H', cid) + name.encode() + b'\0' for name, cid in rows)
        clean.append((code, payload, long_header))
    linkage = {name: cid for code, payload, _ in clean if code == 56
               for name, cid in exports(payload)}
    source = next(payload for code, payload, _ in clean if code == 39
                  and struct.unpack_from('<H', payload)[0] == linkage['channel_clan_btn'])
    definitions = {2, 6, 7, 10, 11, 14, 20, 21, 22, 32, 33, 34, 35, 36,
                   37, 39, 46, 48, 60, 75, 83, 84, 87, 90, 91}
    used = {struct.unpack_from('<H', payload)[0] for code, payload, _ in clean
            if code in definitions}
    symbol, text_id = sorted(set(range(1, 65536)) - used)[:2]
    # Regular embedded Arial from the native UI, with Latin/Cyrillic coverage.
    font = next(struct.unpack_from('<H', payload)[0] for code, payload, _ in clean
                if code == 75 and not payload[2] & 1
                and payload[5:5 + payload[4]].rstrip(b'\0') == b'Arial')
    # Reserve the left 18 px for the native unread indicator.
    text = (struct.pack('<H', text_id) + rect(360, 1560, 20, 360)
            + bytes((0x8D, 0x31)) + struct.pack('<HH', font, 220)
            + bytes((170, 166, 138, 255)) + bytes((2,))
            + struct.pack('<HHHh', 0, 0, 0, 0) + b'\0\0')
    children = w.split_tags(b'\x08\0\0\0\0\0' + source[4:])
    replaced = 0
    for i, (code, payload, long_header) in enumerate(children):
        if code == 26 and struct.unpack_from('<H', payload, 1)[0] == 4:
            # The source caption is an unnamed shape at depth 4.
            assert payload[0] == 6, 'clan caption artwork changed'
            children[i] = (26, bytes((0x26,)) + struct.pack('<HH', 4, text_id)
                           + b'\0pmNickname\0', True)
            replaced += 1
    assert replaced == 1, 'expected exactly one baked clan caption'
    # Borrow the shipped close control, not the generic tab's extra caption.
    generic = next(payload for code, payload, _ in clean if code == 39
                   and struct.unpack_from('<H', payload)[0] == linkage['channel_btn'])
    close = next(t for t in w.split_tags(b'\x08\0\0\0\0\0' + generic[4:])
                 if t[0] == 26 and b'close_btn\0' in t[1])
    at_frame = next(i for i, t in enumerate(children) if t[0] == 1)
    children.insert(at_frame, close)
    sprite = struct.pack('<H', symbol) + source[2:4] + w.join_tags(b'', children)
    exports_tag = struct.pack('<HH', 2, symbol) + b'__pm_channel_btn\0'
    exports_tag += struct.pack('<H', text_id) + b'__pm_nickname_text\0'
    at = next(i for i, t in enumerate(clean) if t[0] == 1)
    clean[at:at] = [(37, text, True), (39, sprite, True), (56, exports_tag, False)]
    return clean
