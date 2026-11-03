"""Closable private tabs: preserve logs and reopen only on incoming/manual open."""
from avm_codegen import Compiler

SOURCE = '''
def __pmFitNickname(mc, peer):
    # The borrowed close control belongs to a wider native tab. Position it
    # against this tab's actual frame, accounting for the symbol's own origin.
    if mc.close_btn and mc.backButton:
        frame = mc.backButton.getBounds(mc)
        close = mc.close_btn.getBounds(mc)
        mc.close_btn._x = mc.close_btn._x + frame.xMax - close.xMax - 5
    field = mc.pmNickname
    field.text = peer
    length = len(peer)
    while field.textWidth > field._width - 4 and length > 1:
        length = length - 1
        field.text = peer.substring(0, length) + "…"

def __pmCloseTab(obj):
    mc = obj.target
    if mc.group != 0 - 1:
        this.__pmCloseTabOrig(obj)
        return
    chat = this.master.chat
    rec = chat.getChannel(mc.group, mc.withID)
    if rec:
        rec.__pmClosed = True
        chat.__hcDirty = True
    wasCurrent = this.currentChannel == mc
    where = mc.where
    this.removeChannel(mc.group, mc.withID, where)
    if where == "main" and len(this.stackList) > 0:
        first = this.stackList[0]
        light = first.mc.light
        this.removeChannel(first.group, first.withID, "stack")
        replacement = this.createChannel(first.group, first.withID)
        replacement.light = light
    this.setSizeStackMc()
    this.resizeStage()
    if wasCurrent and len(this.mainList) > 0:
        next = this.mainList[0]
        this.initChannel(next.group, next.withID)
    if rec:
        _global.__hcSafeFlush(chat)

def __pmClosedRefresh(disObj):
    if disObj.group == 0 - 1 and disObj.__pmClosed:
        return
    this.__pmClosedRefreshOrig(disObj)

def __pmManualChannel(group, peer):
    if group == 0 - 1 and peer:
        rec = _global.__pmEnsure(this.master.chat, peer)
        rec.__pmClosed = False
        this.master.chat.__hcDirty = True
    this.__pmManualChannelOrig(group, peer)

def __pmClosableCreate(group, withID, pos, insert):
    mc = this.__pmClosableCreateOrig(group, withID, pos, insert)
    if mc and group == 0 - 1:
        _global.__pmFitNickname(mc, withID)
    return mc

def __pmClosableStack(group, withID, pos, insert):
    mc = this.__pmClosableStackOrig(group, withID, pos, insert)
    if mc and group == 0 - 1:
        _global.__pmFitNickname(mc, withID)
    return mc
'''


def patches(Asm, undef):
    functions=Compiler(Asm,undef).functions(SOURCE)
    bodies={name:(params,body) for name,params,body in functions}
    wraps=[]
    for path,method,keep,helper in (
        (('gpui','ChatChannelPan'),'closeChannel','__pmCloseTabOrig','__pmCloseTab'),
        (('gpui','ChatChannelPan'),'newChannel','__pmManualChannelOrig','__pmManualChannel'),
        (('gpui','ChatChannelPan'),'createChannel','__pmClosableCreateOrig','__pmClosableCreate'),
        (('gpui','ChatChannelPan'),'addToStack','__pmClosableStackOrig','__pmClosableStack'),
        (('services','ChatPan'),'refresh','__pmClosedRefreshOrig','__pmClosedRefresh')):
        params,body=bodies[helper];wraps.append((path,method,keep,params,body))
    return dict(globals=functions[:1],wraps=tuple(wraps))
