"""Build-time AVM1 cleanup for retired scenes and interrupted asset loads.

No per-frame hooks, new timers, network requests or shared texture eviction.
Only the departing object's own subscriptions and timer handles are removed.
"""
from avm_codegen import Compiler

SOURCE = '''
def __lcDisableTraderNotice():
    this.traderMessage_bool = False

def __lcFilter(name):
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


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
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
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
