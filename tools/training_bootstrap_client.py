"""Capability handshake and reversible, lazy AVM1 hooks for the private range.

Only Send/sendNotification are bootstrapped. The remaining hooks exist only
from an accepted types packet until the ordinary equipment/stat snapshots
have returned, or until the transport is closed. Restore the exact chain we
found; a later owner of a method must never be overwritten by teardown.
"""

SOURCE = '''
def __tgHandshakeSend(mess):
    # Existing characters enter from selPers; only newborns use actPlayer.
    # Negotiate before either command can restore a saved training session.
    if mess.name == "selPers" or mess.name == "actPlayer":
        this.__tgCompatible = False
        hello = new(lol.server.mess.CSMessage)
        hello._name = "tg"
        hello.addProp("op", "@hello@")
        hello.addProp("version", 1)
        if _global.__tgTypeCache and _global.__tgTypeCache.version:
            hello.addProp("types_version", "@" + _global.__tgTypeCache.version + "@")
        _global.__tgTransmit(hello)
    return this.__tgHandshakeOrig(mess)

def __tgBootstrapNotify(cmd):
    if cmd.messID != "tg":
        return this.__tgNotifyOrig(cmd)
    value = cmd.params
    if value.op == "hello":
        this.__tgCompatible = Number(value.version) == 1 and Boolean(value.available)
        return
    if value.op == "types_cached":
        cache = _global.__tgTypeCache
        if not cache or cache.version != value.version:
            request = new(lol.server.mess.CSMessage)
            request._name = "tg"
            request.addProp("op", "@types_request@")
            _global.__tgTransmit(request)
            return
        value = cache
        cmd = {"messID":"tg", "params":cache}
    if not _global.__tgHooksActive:
        if value.op != "types" or not this.__tgCompatible:
            return
        _global.__tgLoadFeature()
    result = _global.__tgNotifyWrapper.apply(this, [cmd])
    if value.op == "types" and value.version:
        # Only immutable display metadata survives the reversible hook teardown.
        # Keep one version, never any private item instances or character state.
        _global.__tgTypeCache = value
        ack = new(lol.server.mess.CSMessage)
        ack._name = "tg"
        ack.addProp("op", "@types_ack@")
        ack.addProp("version", "@" + value.version + "@")
        _global.__tgTransmit(ack)
    return result

def __tgMaybeDetach():
    if not _global.__tgHooksActive or _global.__tgActive or _global.__tgReturnEquipment or _global.__tgSnapshotPending or _global.__tgReturnBagPending:
        return
    _global.__tgForgetItems(True)
    equipment = lol.core.Master.getInstance().gamer.equipment
    equipment.__tgManaged = False
    equipment.__tgReplaceNextBag = False
    _global.__tgCopies = {}
    _global.__tgIcons = {}
    _global.__tgLines = {}
    _global.__tgLabels = {}
    _global.__tgPrices = {}
    _global.__tgUnbindSocket()
    _global.__tgUnbindEvents()
    _global.__tgDetachHooks()

def __tgBindEvents():
    # LEventDispatcher captures handler functions at subscription time.
    # Updating a prototype alone does not update these existing listeners.
    _global.__tgUnbindEvents()
    _global.__tgEventBindings = []
    master = lol.core.Master.getInstance()
    _global.__tgBindEvent("lenter", master, master.__tgEnterOrig, master.lenter)
    attrs = master.gamer.attributes
    _global.__tgBindEvent("rp_info", attrs, attrs.__tgStatsOrig, attrs.rp_info)

def __tgBindEvent(event, target, previous, bound):
    queue = lol.server.XMLConnection.getInstance()["__q_" + event]
    if not queue or not previous or not bound:
        return
    i = 0
    while i < len(queue):
        row = queue[i]
        if row[0] == target and row[1] == previous:
            _global.__tgEventBindings.push({"row":row, "previous":previous, "bound":bound})
            row[1] = bound
        i = i + 1

def __tgUnbindEvents():
    bindings = _global.__tgEventBindings
    if not bindings:
        return
    i = 0
    while i < len(bindings):
        binding = bindings[i]
        if binding.row[1] == binding.bound:
            binding.row[1] = binding.previous
        i = i + 1
    _global.__tgEventBindings = []

def __tgBindSocket():
    connection = lol.server.XMLConnection.getInstance()
    socket = connection.connector
    if not socket or not socket.onClose:
        return
    _global.__tgSocketTarget = socket
    _global.__tgSocketPrevious = socket.onClose
    # XMLConnection.init captured the old method before the lazy hooks existed.
    # Rebind only this socket's delegate, preserving its exact original on exit.
    _global.__tgSocketBound = mx.utils.Delegate.create(connection, connection.onClose)
    socket.onClose = _global.__tgSocketBound

def __tgUnbindSocket():
    socket = _global.__tgSocketTarget
    if socket and socket.onClose == _global.__tgSocketBound:
        socket.onClose = _global.__tgSocketPrevious
    _global.__tgSocketTarget = None
    _global.__tgSocketPrevious = None
    _global.__tgSocketBound = None
'''


def registry(Asm, undef, hooks):
    """Emit method changes from one declarative table, including static hooks."""
    attach, detach = Asm(), Asm()
    for index, (path, method, keep, helper, static) in enumerate(hooks):
        for code, uninstall in ((attach, False), (detach, True)):
            done = 'hook_%d_done' % index
            code.push('target').var('lol').member(*path)
            if not static:
                code.member('prototype')
            code.op('definelocal')
            code.var('target').push(undef).op('equals2').iftrue(done)
            if uninstall:
                code.var('target').member(method).var('_global').member(helper).op('equals2').op('not').iftrue(done)
                code.var('target').push(method).var('target').member(keep).op('setmember')
                code.var('target').push(keep).op('delete').op('pop')
            else:
                code.var('target').member(keep).push(undef).op('equals2').op('not').iftrue(done)
                code.var('target').push(keep).var('target').member(method).op('setmember')
                code.var('target').push(method).var('_global').member(helper).op('setmember')
            code.label(done)
    attach.var('_global').push('__tgHooksActive', True).op('setmember')
    detach.var('_global').push('__tgHooksActive', False).op('setmember')
    return [('__tgAttachHooks', (), attach), ('__tgDetachHooks', (), detach)]


def loader(Asm, functions):
    """Defer allocation of the feature's UI helpers until its first entry."""
    parts, part, size = [], Asm(), 0
    for name, params, body in functions:
        define = Asm().var('_global').push(name).function(params, body).op('setmember')
        length = len(define.assemble())
        # AVM1 function bodies have a uint16 size and branches use int16.
        # Keep each lazy declaration chunk comfortably inside these bounds.
        if size and size + length > 24_000:
            parts.append(('__tgLoadPart%d' % len(parts), (), part))
            part, size = Asm(), 0
        part.parts.extend(define.parts)
        size += length
    if size:
        parts.append(('__tgLoadPart%d' % len(parts), (), part))
    code = Asm()
    code.var('_global').member('__tgFeatureLoaded').iftrue('loaded')
    for name, _, _ in parts:
        code.push(0).var('_global').push(name).op('callmethod').op('pop')
    code.var('_global').push('__tgFeatureLoaded', True).op('setmember')
    code.label('loaded')
    code.push(0).var('_global').push('__tgInstall').op('callmethod').op('pop')
    return parts + [('__tgLoadFeature', (), code)]


def transmit(Asm):
    """Restore the command-filter flag even if the socket Send throws."""
    import struct
    code = Asm()
    code.push('manager').push(0).var('lol').member('server', 'filters', 'FilterManager').push('getInstance').op('callmethod').member('currentFilter').op('definelocal')
    code.push('previous').push('tg', 1).var('manager').push('getFlag').op('callmethod').op('definelocal')
    code.push(True, 'tg', 2).var('manager').push('setFlag').op('callmethod').op('pop')
    body = Asm()
    body.var('m').push(1, 0).var('lol').member('server', 'XMLConnection').push('getInstance').op('callmethod').push('Send').op('callmethod').op('pop')
    final = Asm()
    final.var('previous').push('tg', 2).var('manager').push('setFlag').op('callmethod').op('pop')
    before, after = body.assemble(), final.assemble()
    # ActionTry: no catch, finally always restores the original filter flag.
    header = bytes((2,)) + struct.pack('<HHH', len(before), 0, len(after)) + b'unused\0'
    code.parts.append(b'\x8f' + struct.pack('<H', len(header)) + header + before + after)
    return code
