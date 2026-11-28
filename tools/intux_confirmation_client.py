"""INTUX uses the native query window and the existing item ACK pipeline."""
from avm_codegen import Compiler

MARK = '__intuxConfirmationV1'

SOURCE = '''
def __ixAttributes(obj):
    if obj.param.intux_confirmation != None:
        this.__ixSupported = Number(obj.param.intux_confirmation) == 1
    return this.__ixAttributesOrig(obj)

def __ixUse(type, obj, target):
    item = lol.core.objects.ItemFactory.getItem(obj)
    if not item or not this.gamer.attributes.__ixSupported or (type != 2 and type != 4):
        return this.__ixUseOrig(type, obj, target)
    source = item.typeID
    if source != 3112 and source != 3113 and source != 3114 and source != 3561:
        return this.__ixUseOrig(type, obj, target)
    if this.__ixPending:
        return
    this.__usedItem = item
    if this.coolDownBlock or not this.canUse():
        return this.__ixUseOrig(type, obj, target)
    this.__ixPending = {"type":type, "obj":obj, "target":target, "item":item,
                        "useType":this.useType, "location":lol.core.Master.getInstance().currentLocation,
                        "phase":"quote"}
    return this.__ixSend(False)

def __ixSend(apply):
    pending = this.__ixPending
    if not pending:
        return
    a = new(lol.data.BigUINT, new(lol.data.BigUINTCluster, pending.obj))
    b = None
    if pending.target != None:
        b = new(lol.data.BigUINT, new(lol.data.BigUINTCluster, pending.target))
    message = new(lol.server.mess.CSM_SSUse, pending.type, a, b)
    if not apply:
        message.addProp("xp_stage", "@quote@")
    else:
        message.addProp("xp_token", "@" + pending.token + "@")
    if not this.XMC.Send(message):
        this.__ixPending = None
        return
    if apply:
        this.coolDownBlock = True
        this.useFireArm = True
        clearInterval(this.breakInterval)
        this.breakInterval = setInterval(this, "breakAction", 3000)
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.__ixApplied)
    else:
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.__ixQuote)

def __ixQuote(obj):
    pending = this.__ixPending
    if not pending or pending.phase != "quote":
        return
    if obj.param.res != 0 or not obj.param.xp_token:
        this.__ixPending = None
        this.gamer.dispatchAck(obj.param.res)
        return
    pending.token = obj.param.xp_token
    if not obj.param.xp_warning:
        return this.__ixApply()
    # Do not replace another trade, quest or purchase confirmation.
    if lol.core.SceneShifter._ref.UIPanels.query.instance:
        this.__ixPending = None
        return
    if pending.location != lol.core.Master.getInstance().currentLocation:
        this.__ixPending = None
        return
    dialog = lol.core.SceneShifter.openNewWindow("query").content
    this.__ixDialog = dialog
    dialog.__ixOwner = this
    dialog.label = obj.param.xp_message
    dialog.apply_btn.label = "ОК"
    dialog.cancel_btn.label = "ОТМЕНА"
    dialog.addEventListener("click", this, this.__ixAnswer)
    dialog.onUnload = _global.__ixUnloaded

def __ixAnswer(event):
    dialog = this.__ixDialog
    if not dialog or event.target != dialog:
        return
    dialog.removeEventListener("click", this, this.__ixAnswer)
    this.__ixDialog = None
    lol.core.SceneShifter.closeWindow("query")
    if not event.success:
        this.__ixPending = None
        return
    return this.__ixApply()

def __ixUnloaded():
    owner = this.__ixOwner
    if owner and owner.__ixDialog == this:
        owner.__ixDialog = None
        owner.__ixPending = None

def __ixApply():
    pending = this.__ixPending
    if not pending or pending.phase != "quote":
        return
    master = lol.core.Master.getInstance()
    if pending.location != master.currentLocation or master.gamer != this.gamer:
        this.__ixPending = None
        return
    this.__usedItem = pending.item
    this.useType = pending.useType
    if this.coolDownBlock or not this.canUse():
        this.__ixPending = None
        return
    pending.phase = "apply"
    return this.__ixSend(True)

def __ixApplied(obj):
    this.__ixPending = None
    return this.useAck(obj)
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    by_name = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, name in (
        (('core', 'player', 'PersAttributes'), 'rp_info', '__ixAttributesOrig', '__ixAttributes'),
        (('core', 'objects', 'ItemActivator'), 'useItem', '__ixUseOrig', '__ixUse'),
        *[(('core', 'objects', 'ItemActivator'), name, name + 'Orig', name)
          for name in ('__ixSend', '__ixQuote', '__ixAnswer', '__ixApply', '__ixApplied')],
    ):
        params, body = by_name[name]
        wraps.append((path, method, keep, params, body))
    return dict(globals=[row for row in functions if row[0] == '__ixUnloaded'], wraps=tuple(wraps))


def action(Asm, undef):
    """Incremental update for an already patched local client, without other changes."""
    a = Asm().push(MARK).op('pop')
    feature = patches(Asm, undef)
    for name, params, body in feature['globals']:
        a.var('_global').push(name).function(params, body).op('setmember')
    for path, method, keep, params, body in feature['wraps']:
        skip = 'skip_' + method
        pvar = '__ixPrototype'
        a.push(pvar).var('lol').member(*path).member('prototype').op('definelocal')
        a.var(pvar).push(undef).op('equals2').iftrue(skip)
        a.var(pvar).push(keep).op('getmember').push(undef).op('equals2').op('not').iftrue(skip)
        a.var(pvar).push(keep).var(pvar).push(method).op('getmember').op('setmember')
        a.var(pvar).push(method).function(params, body).op('setmember')
        a.label(skip)
    return a.op('end').assemble()
