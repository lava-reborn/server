"""Bounded, per-server/per-character Flash SharedObject chat history.

The source is compiled to AVM1 at build time, never run by Python. Storage
failures are isolated from native delivery. No database or HTTP requests.
"""
from avm_codegen import Compiler, protected_call

SOURCE = '''
def __hcNow():
    return new("Date").getTime()

def __hcLimit():
    n = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_MESSAGE)
    if kind(n) == "string":
        n = Number(n)
    if kind(n) != "number" or n != n or n < 1 or n > 1000:
        n = 50
    return n

def __hcEncode(text):
    h1 = 0
    h2 = 7
    i = 0
    while i < len(text):
        code = text.charCodeAt(i)
        h1 = (h1 * 31 + code) % 2147483629
        h2 = (h2 * 37 + code) % 2147483587
        i = i + 1
    return String(h1) + "_" + String(h2)

def __hcPrune(rows, now, limit):
    out = []
    if not rows or kind(rows.length) != "number":
        return out
    i = len(rows) - limit
    if i < 0:
        i = 0
    while i < len(rows) and i < 2000:
        r = rows[i]
        i = i + 1
        if not r or kind(r.mess) != "string" or kind(r.name) != "string":
            continue
        if len(r.mess) > 2048 or len(r.name) > 128:
            continue
        if kind(r.__hcStamp) != "number" or r.__hcStamp < now - 43200000 or r.__hcStamp > now + 60000:
            continue
        out.push(r)
    return out

def __hcRecord(chat, rec):
    if chat.__hcRestoring:
        return
    now = _global.__hcNow()
    rows = rec.logArr
    if len(rows) > 0 and rows[len(rows) - 1].__hcStamp == None:
        rows[len(rows) - 1].__hcStamp = now
        chat.__hcDirty = True
    excess = len(rows) - _global.__hcLimit()
    if excess > 0:
        rows.splice(0, excess)
        chat.__hcDirty = True

def __hcFlush(chat):
    if not chat or not chat.__hcStore or not chat.__hcDirty:
        return
    now = _global.__hcNow()
    records = []
    limit = _global.__hcLimit()
    chars = 0
    budget = 0
    count = 0
    ci = len(chat.channelList) - 1
    while ci >= 0 and len(records) < 32 and chars < 12000 and count < 300:
        rec = chat.channelList[ci]
        ci = ci - 1
        source = _global.__hcPrune(rec.logArr, now, limit)
        saved = []
        j = len(source) - 1
        while j >= 0 and chars < 12000 and count < 300:
            r = source[j]
            j = j - 1
            if r.__hcMarker or r.fromID == "server":
                continue
            cost = 200 + 3 * (len(r.mess) + len(r.name) + len(String(r.time)) + len(String(r.to_name)))
            if chars + len(r.mess) + len(r.name) > 12000 or budget + cost > 60000:
                continue
            budget = budget + cost
            saved.unshift({"mess":r.mess, "name":r.name, "time":r.time,
                           "fromID":r.fromID, "group":r.group, "to_name":r.to_name,
                           "__hcStamp":r.__hcStamp})
            chars = chars + len(r.mess) + len(r.name)
            count = count + 1
        if len(saved) > 0:
            records.unshift({"group":rec.group,"peer":rec.withID,"closed":rec.__pmClosed,"scope":_global.__hcScope(chat.__hcUI, rec.group),"rows":saved})
    chat.__hcStore.data.identity = chat.__hcIdentity
    chat.__hcStore.data.version = 1
    chat.__hcStore.data.channels = records
    chat.__hcStore.data.closedAt = chat.__hcClosedAt
    chat.__hcStore.data.open = chat.__hcOpen
    chat.__hcDirty = False
    status = chat.__hcStore.flush()
    if status == "pending" or status == False:
        clearInterval(chat.__hcTimer)
        chat.__hcStore = None

def __hcTick(chat):
    _global.__hcSafeFlush(chat)

def __hcClose():
    chat = _global.__hcChat
    if not chat or not chat.__hcOpen:
        return
    chat.__hcOpen = False
    chat.__hcClosedAt = _global.__hcNow()
    chat.__hcDirty = True
    clearInterval(chat.__hcTimer)
    _global.__hcSafeFlush(chat)

def __hcMarker(stamp, open):
    text = "— Предыдущий сеанс завершён —"
    if not open and kind(stamp) == "number":
        d = new("Date", stamp)
        minutes = String(d.getMinutes())
        if len(minutes) == 1:
            minutes = "0" + minutes
        text = "— " + String(d.getDate()) + "." + String(d.getMonth() + 1) + ", " + String(d.getHours()) + ":" + minutes + " · Отключение от сервера —"
    return {"mess":text, "name":"events", "fromID":"events", "time":"",
            "__hcStamp":stamp, "__hcHistory":True, "__hcMarker":True}

def __hcScope(ui, group):
    if group == 2:
        return String(ui.master.playerRegister.gamer.clanMemberInfo.clanInfo.reg)
    if group == 1:
        return String(ui.partyManager.LeaderID)
    return "public"

def __hcAttach(ui):
    chat = ui.chat
    chat.__hcUI = ui
    nick = ui.master.gamer.playerInfo.name
    if not nick or len(nick) > 128 or not _global.__hcEndpoint:
        return
    identity = _global.__hcEndpoint + "|" + nick
    key = _global.__hcEncode(identity)
    if chat.__hcKey == key and chat.__hcOpen:
        return
    _global.__hcClose()
    if chat.__hcKey:
        ci = 0
        while ci < len(chat.channelList):
            rec = chat.channelList[ci]
            fresh = []
            j = 0
            while j < len(rec.logArr):
                row = rec.logArr[j]
                j = j + 1
                if row.__hcStamp > chat.__hcClosedAt:
                    fresh.push(row)
            rec.logArr = fresh
            ci = ci + 1
    store = SharedObject.getLocal("lavaChatV1" + key, "/")
    if store.data.identity and store.data.identity != identity:
        return
    chat.__hcIdentity = identity
    chat.__hcStore = store
    chat.__hcKey = key
    chat.__hcRestoring = True
    channels = store.data.channels
    now = _global.__hcNow()
    if store.data.version == 1 and channels and len(channels) <= 32:
        i = 0
        while i < len(channels):
            old = channels[i]
            i = i + 1
            if not old or kind(old.group) != "number" or old.group < 0 - 1 or old.group > 6:
                continue
            # Clan/party membership is session-bound; do not re-open obsolete channels.
            if (old.group == 1 or old.group == 2) and not ui.chatChannelPan.getChannel(old.group, None).mc:
                continue
            if old.scope != _global.__hcScope(ui, old.group):
                continue
            rows = _global.__hcPrune(old.rows, now, _global.__hcLimit() - 1)
            if len(rows) == 0:
                continue
            if old.group == 0 - 1:
                if kind(old.peer) != "string" or len(old.peer) < 1 or len(old.peer) > 128:
                    continue
                rec = _global.__pmEnsure(chat, old.peer)
            else:
                rec = chat.getChannel(old.group, None)
                if not rec:
                    rec = {"group":old.group, "logArr":[]}
                    chat.channelList.push(rec)
            j = 0
            while j < len(rows):
                rows[j].__hcHistory = True
                rows[j].withID = None
                j = j + 1
            rows.push(_global.__hcMarker(store.data.closedAt, store.data.open))
            j = 0
            while j < len(rec.logArr):
                rows.push(rec.logArr[j])
                j = j + 1
            excess = len(rows) - _global.__hcLimit()
            if excess > 0:
                rows.splice(0, excess)
            rec.logArr = rows
            rec.__pmClosed = old.closed == True
            # Create tabs directly; restoring must not dispatch new-message notifications.
            if not rec.__pmClosed and not ui.chatChannelPan.getChannel(rec.group, rec.withID).mc:
                ui.chatChannelPan.createChannel(rec.group, rec.withID)
    chat.__hcRestoring = False
    chat.__hcOpen = True
    chat.__hcDirty = True
    _global.__hcChat = chat
    chat.__hcTimer = setInterval(_global.__hcTick, 5000, chat)
    _global.__hcSafeFlush(chat)

def __hcRender(ui, rows, group):
    prefix = []
    i = 0
    while i < len(rows) and rows[i].__hcHistory:
        prefix.push(rows[i])
        i = i + 1
    if len(prefix) == 0:
        return False
    ui.__hcShowOrig(prefix, group)
    end = len(ui.chatOutput.text)
    ui.__hcShowOrig(rows, group)
    fmt = new("TextFormat")
    fmt.color = 10065534
    ui.chatOutput.setTextFormat(0, end, fmt)
    return True

def __hcInitWrapper():
    this.__hcInitOrig()
    _global.__hcSafeAttach(this)

def __hcInfoWrapper(obj):
    this.__hcInfoOrig(obj)
    ui = lol.core.SceneShifter.chat
    if ui:
        _global.__hcSafeAttach(ui)

def __hcDispatchWrapper(rec):
    _global.__hcSafeRecord(this, rec)
    this.__hcDispatchOrig(rec)

def __hcEraseWrapper(peer, group):
    this.__hcEraseOrig(peer, group)
    this.__hcDirty = True
    _global.__hcSafeFlush(this)

def __hcConnectWrapper(host, port):
    _global.__hcEndpoint = host + ":" + String(port)
    this.__hcConnectOrig(host, port)

def __hcCloseWrapper():
    _global.__hcSafeClose()
    this.__hcCloseOrig()

def __hcSocketCloseWrapper():
    _global.__hcSafeClose()
    this.__hcSocketCloseOrig()
'''


def patches(Asm, undef):
    c = Compiler(Asm, undef)
    functions = c.functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    globals_ = [(name, params, body) for name, params, body in functions
                if not name.endswith('Wrapper')]
    for target, params in (('__hcAttach', ('ui',)), ('__hcRecord', ('chat','rec')),
                           ('__hcFlush', ('chat',)), ('__hcClose', ())):
        globals_.append((target.replace('__hc','__hcSafe'), params,
                         protected_call(Asm, target, params, undef)))
    wraps=[]
    for path, method, keep, helper in (
        (('services','ChatPan'),'init','__hcInitOrig','__hcInitWrapper'),
        (('core','player','Gamer'),'userInfo','__hcInfoOrig','__hcInfoWrapper'),
        (('core','Chat'),'dispatchChannel','__hcDispatchOrig','__hcDispatchWrapper'),
        (('core','Chat'),'eraseChannel','__hcEraseOrig','__hcEraseWrapper'),
        (('server','XMLConnection'),'connect','__hcConnectOrig','__hcConnectWrapper'),
        (('server','XMLConnection'),'close','__hcCloseOrig','__hcCloseWrapper'),
        (('server','XMLConnection'),'onClose','__hcSocketCloseOrig','__hcSocketCloseWrapper')):
        params,body=bodies[helper];wraps.append((path,method,keep,params,body))
    # Keep the native renderer outside a cache error boundary as a fallback.
    render = c.statements(Asm(), __import__('ast').parse(
        'ui.__hcRendered = _global.__hcRender(ui, rows, group)').body)
    from struct import pack
    code=render.assemble()
    data=bytes((1,))+pack('<HHH',len(code),0,0)+b'cacheError\0'+code
    renderer=Asm()
    renderer.var('this').push('__hcRendered',False).op('setmember')
    renderer.push('ui').var('this').op('definelocal')
    renderer.parts.append(b'\x8f'+pack('<H',len(data)-len(code))+data)
    renderer.var('this').member('__hcRendered').iftrue('out')
    renderer.var('group').var('rows').push(2).var('this').push('__hcShowOrig').op('callmethod').op('pop')
    renderer.label('out')
    wraps.append((('services','ChatPan'),'showMessage','__hcShowOrig',('rows','group'),renderer))
    return dict(globals=globals_, wraps=tuple(wraps))
