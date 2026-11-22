"""Build-time AVM1 cleanup for retired scenes and interrupted asset loads.

No per-frame hooks, new timers, network requests or shared texture eviction.
Only the departing object's own subscriptions and timer handles are removed.
"""
from avm_codegen import Compiler

SOURCE = '''
def __lcTimeout(target, callback, delay):
    this.target = target
    this.callback = callback
    this.args = []
    i = 3
    while i < len(arguments):
        this.args.push(arguments[i])
        i = i + 1
    this.id = setInterval(_global.__lcTimeoutFire, delay, this)

def __lcTimeoutClear():
    _global.__lcStopTimer(this, "id")
    this.target = None
    this.callback = None
    this.args = None

def __lcTimeoutFire(timer):
    callback = timer.callback
    target = timer.target
    args = timer.args
    _global.__lcTimeoutClear.apply(timer, [])
    if callback:
        callback.apply(target, args)

def __lcInstallTimeout():
    old = lol.utils.Timeout
    if not old or old.__lcPatched:
        return
    replacement = _global.__lcTimeout
    replacement.prototype.Clear = _global.__lcTimeoutClear
    # Bootstrap timers still reference their original registry until they fire.
    replacement._intervals = old._intervals
    replacement.__lcPatched = True
    lol.utils.Timeout = replacement

def __lcEffectsInit():
    this.__lcEffectsSource = this.master.gamer.effects
    this.__lcEffectsDisposed = False
    this.__lcEffectsInitOrig()

def __lcEffectsKill():
    if this.__lcEffectsDisposed:
        return
    this.__lcEffectsDisposed = True
    _global.__lcStopTimer(this, "effectsTimer")
    source = this.__lcEffectsSource
    if source:
        source.removeEventListener(lol.events.PlayerEvent.UPDATE_EFFECTS, this, this.effectsUpdate)
        source.removeEventListener(lol.events.PlayerEvent.UPDATE_ONE_EFFECT, this, this.oneEffectUpdate)
    this.__lcEffectsSource = None
    this.__lcEffectsKillOrig()

def __lcInfoNick(id):
    this.__lcInfoDisposed = False
    this.__lcInfoNickOrig(id)
    this.__lcInfoPlayer = this.player
    this.__lcInfoParty = lol.core.party.PartyManager.getInstance()

def __lcInfoKill():
    if this.__lcInfoDisposed:
        return
    this.__lcInfoDisposed = True
    _global.__lcStopTimer(this, "timer")
    _global.__lcStopTimer(this, "removePhraseInterval")
    party = this.__lcInfoParty
    events = lol.core.party.PartyEvent
    if party:
        # Native kill removes partyColorUpdate_pause, but setNick registered
        # partyColorUpdate. The dispatcher requires the same function object.
        types = [events.JOIN_TO_PARTY, events.DISBAND_PARTY, events.KICKED_FROM_PARTY, events.LEAVE_PARTY, events.PARTY_LIST_REFRESH]
        i = 0
        while i < len(types):
            party.removeEventListener(types[i], this, this.partyColorUpdate)
            i = i + 1
    player = this.__lcInfoPlayer
    if player:
        player.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO, this, this.userInfoUpdate)
    this.__lcInfoKillOrig()
    this.__lcInfoParty = None
    this.__lcInfoPlayer = None

def __lcPrepareTimer(seconds):
    # A delayed Flash frame can skip the exact second native code waits for.
    # Retire the display timer once its deadline has passed as well.
    if getTimer() - this.startTimer >= seconds * 1000:
        this.timerFlag = False
        _global.__lcStopTimer(this, "timer")
        this.prepare_txt.text = ""
        return
    return this.__lcPrepareTimerOrig(seconds)

def __lcDisableTraderNotice():
    this.traderMessage_bool = False

def __lcFilter(name):
    if name == "persInfo":
        # The preceding window patch constructs this filter dynamically;
        # it has no persInfoArr field. Preserve that wrapper in the chain.
        return this.__lcFilterOrig(name)
    base = this[name + "Arr"]
    if not base:
        base = []
    return base.concat([lol.services.HotKeyEvent.CTRL, lol.services.HotKeyEvent.SHIFT])

def __lcStopTimer(owner, key):
    if owner[key] != None:
        clearInterval(owner[key])
        owner[key] = None

def __lcUnlisten(source, events, target):
    if not source:
        return
    i = 0
    while i < len(events):
        source.removeEventListener(events[i], target)
        i = i + 1

def __lcSceneInit():
    _global.__lcStopTimer(this, "areaInterval")
    this.__lcDisposed = False
    this.__lcState = lol.core.SceneShifter._ref
    this.__lcMaster = this.master
    this.__lcGamer = this.master.gamer
    this.__lcChat = this.master.chat
    this.__lcAttributes = this.master.gamer.attributes
    this.__lcEquipment = this.master.gamer.equipment
    this.__lcSceneInitOrig()

def __lcSceneKill():
    if this.__lcDisposed:
        return
    this.__lcDisposed = True
    _global.__lcStopTimer(this, "areaInterval")
    _global.__lcStopTimer(this, "spt_int")
    # Native scene kill never calls kill on the surviving name/health panels.
    _global.__lcKillHelpers(this.helperObjects)
    _global.__lcUnlisten(this.currentLocation, ["addPlayer", "removePlayer", "position", "finishPart", "finishMove", "aim", "fireAck", "dead", "enemy", "addBag", "removeBag"], this)
    state = this.__lcState
    if state:
        state.removeEventListener("sceneEnabled", this)
    master = this.__lcMaster
    if master:
        master.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE, this, this.userStateUpdate)
    gamer = this.__lcGamer
    if gamer:
        gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE, this, this.gamerUpdate)
    if this.__lcAttributes:
        this.__lcAttributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS, this, this.gamerUpdate)
    if this.__lcEquipment:
        this.__lcEquipment.removeEventListener("changePrimary", this)
    if this.__lcChat:
        this.__lcChat.removeEventListener("refresh", this, this.chatRefreshed)
    this.__lcSceneKillOrig()
    this.__lcState = None
    this.__lcMaster = None
    this.__lcGamer = None
    this.__lcChat = None
    this.__lcAttributes = None
    this.__lcEquipment = None

def __lcMapInit():
    this.__lcMapDisposed = False
    this.__lcMapModel = this.globalMap
    this.__lcMapInitOrig()

def __lcMapKill():
    if this.__lcMapDisposed:
        return
    this.__lcMapDisposed = True
    _global.__lcStopTimer(this, "spt_int")
    if this.__lcMapModel:
        this.__lcMapModel.removeEventListener("addPlayer", this)
    this.__lcMapKillOrig()
    this.__lcMapModel = None

def __lcLoaderClear():
    sources = this.sourceList
    i = 0
    while sources and i < len(sources):
        if sources[i]:
            sources[i].removeEventListener("onLoadError", this)
        i = i + 1
    this.__lcLoaderClearOrig()
'''


def kill_helpers(Asm):
    """Enumerate native sparse entity IDs, never scan an array's length."""
    a = Asm()
    a.var('helpers').op('not').iftrue('done')
    a.var('helpers').op('enumerate2').label('next')
    a.push('key').op('stackswap').op('definelocal')
    a.var('key').push(None).op('equals2').iftrue('done')
    a.push('panel').var('helpers').var('key').op('getmember').op('definelocal')
    a.var('panel').op('not').iftrue('skip')
    a.var('panel').member('kill').op('not').iftrue('skip')
    a.push(0).var('panel').push('kill').op('callmethod').op('pop')
    a.label('skip').push(True).iftrue('next')
    a.label('done').push(None).op('return')
    return a


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    functions.append(('__lcKillHelpers', ('helpers',), kill_helpers(Asm)))
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        # Disable only the obsolete top-up advertisement. Do not suppress
        # generic service messages, quest notices or inventory warnings.
        (('gpui', 'LocationInterface'), 'checkTrader', '__lcTraderOrig', '__lcDisableTraderNotice'),
        (('gpui', 'LocationInterface'), 'checkPlayerAfterLoading', '__lcTraderLoadedOrig', '__lcDisableTraderNotice'),
        (('services', 'HotKeyFilter'), 'getFilter', '__lcFilterOrig', '__lcFilter'),
        (('core', 'location', 'DisplayLocScene'), 'init', '__lcSceneInitOrig', '__lcSceneInit'),
        (('core', 'location', 'DisplayLocScene'), 'kill', '__lcSceneKillOrig', '__lcSceneKill'),
        (('core', 'globmap', 'DisplayGlobalMap'), 'init', '__lcMapInitOrig', '__lcMapInit'),
        (('core', 'globmap', 'DisplayGlobalMap'), 'kill', '__lcMapKillOrig', '__lcMapKill'),
        (('core', 'location', 'LocSourceLoader'), 'clearList', '__lcLoaderClearOrig', '__lcLoaderClear'),
        (('core', 'effects', 'DisplayFX'), 'init', '__lcEffectsInitOrig', '__lcEffectsInit'),
        (('core', 'effects', 'DisplayFX'), 'kill', '__lcEffectsKillOrig', '__lcEffectsKill'),
        (('core', 'location', 'CharInfo'), 'setNick', '__lcInfoNickOrig', '__lcInfoNick'),
        (('core', 'location', 'CharInfo'), 'kill', '__lcInfoKillOrig', '__lcInfoKill'),
        (('core', 'location', 'CharInfo'), 'prepareTimer', '__lcPrepareTimerOrig', '__lcPrepareTimer'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
