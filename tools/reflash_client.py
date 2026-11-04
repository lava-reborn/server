"""Manual, bounded appearance refresh using existing read-only requests."""
from avm_codegen import Compiler

SOURCE = '''
def __rfAdd(id, pos, rtype):
    player = this.__rfAddOrig(id, pos, rtype)
    if id == 0 or id >= 1000000:
        if not this.__rfPlayers:
            this.__rfPlayers = []
        i = 0
        while i < len(this.__rfPlayers):
            if this.__rfPlayers[i] == id:
                return player
            i = i + 1
        this.__rfPlayers.push(id)
    return player

def __rfRemove(id):
    this.__rfRemoveOrig(id)
    if this.__rfPlayers:
        i = 0
        while i < len(this.__rfPlayers):
            if this.__rfPlayers[i] == id:
                this.__rfPlayers.splice(i, 1)
                return
            i = i + 1

def __rfIdle(player):
    if player.equipment and player.equipment.transferStack and len(player.equipment.transferStack) > 0:
        return False
    if player.itemActivator and (player.itemActivator.coolDownBlock or player.itemActivator.useFireArm):
        return False
    walker = player.walker
    if not walker:
        return False
    if walker.__walkActive or walker.behavior == "fire_in" or walker.behavior == "fire" or walker.behavior == "arm_in" or walker.behavior == "arm_out" or walker.behavior == "die":
        return False
    return True

def __rfFinish():
    if _global.__rfTimer:
        clearInterval(_global.__rfTimer)
    _global.__rfTimer = None
    ui = _global.__rfUI
    if ui and ui.__rfButton:
        ui.__rfButton.enabled = True
    _global.__rfUI = None
    _global.__rfQueue = None
    _global.__rfLocation = None

def __rfRepairKeys():
    shifter = lol.core.SceneShifter
    if not shifter or not shifter.hotKeyManager:
        return False
    keys = shifter.hotKeyManager
    old = keys.keyStack or []
    keys.keyStack = []
    keys.keyPressStack = []
    i = 0
    while i < len(old):
        code = old[i]
        key = "code" + String(code)
        if Key.isDown(code):
            if not keys.keyPressStack[key]:
                keys.keyStack.push(code)
                keys.keyPressStack[key] = code
        else:
            keys.dispatchEvent({"type":lol.services.HotKeyEvent.KEY_RELEASE, "code":code})
        i = i + 1
    # Reattach only the existing manager: bindings and subscribers stay intact.
    Key.removeListener(keys)
    Key.addListener(keys)
    state = shifter._ref
    if not state or not state.sceneEnabled:
        return False
    state.sceneEnabled()
    if state.flagSceneEnabled:
        # Never enable combat keys through an open modal or transaction UI.
        return False
    Selection.setFocus(None)
    keys.hotKeyFilter_arr = ["location"]
    keys.enabled = True
    return True

def __rfBegin(ui):
    master = lol.core.Master.getInstance()
    loc = master.currentLocation
    if not ui or not ui.__rfButton:
        return
    if not _global.__rfRepairKeys():
        return
    if _global.__rfTimer or (_global.__rfNextAllowed and getTimer() < _global.__rfNextAllowed):
        return
    if not loc or loc.warStatus or not loc.__rfPlayers or not _global.__rfIdle(master.gamer):
        return
    if _global.__bfPendingInput or _global.__bfWaiting():
        return
    queue = []
    i = 0
    while i < len(loc.__rfPlayers):
        id = loc.__rfPlayers[i]
        player = loc.playerList[id]
        if player and player.equipment and _global.__rfIdle(player):
            queue.push(id)
        i = i + 1
    if len(queue) == 0:
        return
    _global.__rfGeneration = (_global.__rfGeneration or 0) + 1
    _global.__rfNonce = String(getTimer()) + "-" + String(_global.__rfGeneration)
    _global.__rfResources = 0
    _global.__rfUI = ui
    _global.__rfQueue = queue
    _global.__rfLocation = loc
    _global.__rfNextAllowed = getTimer() + 10000
    _global.__rfTimer = setInterval(_global.__rfStep, 250)

def __rfStep():
    master = lol.core.Master.getInstance()
    loc = _global.__rfLocation
    if not loc or loc != master.currentLocation or loc.warStatus or not _global.__rfIdle(master.gamer) or _global.__bfPendingInput or _global.__bfWaiting():
        _global.__rfFinish()
        return
    if not _global.__rfQueue or len(_global.__rfQueue) == 0:
        _global.__rfFinish()
        return
    id = _global.__rfQueue.shift()
    player = loc.playerList[id]
    if player and player.equipment and _global.__rfIdle(player):
        _global.__rfRetryPlayerResources(player)
        player.requestInfo()
        player.equipment.getStuff(3, id)
    if len(_global.__rfQueue) == 0:
        _global.__rfFinish()

def __rfPress():
    if this.enabled != False:
        this.gotoAndStop(2)

def __rfReset():
    this.gotoAndStop(1)

def __rfRelease():
    this.gotoAndStop(1)
    if this.enabled != False:
        _global.__rfBegin(this.__rfUI)

def __rfButton(ui):
    exit = ui.exit_btn
    if not exit:
        return
    button = ui.__rfButton
    if not button:
        # This unique symbol has native chrome and exactly one fixed caption.
        # It has no GPUIButton class, default labels or localization callbacks.
        button = ui.attachMovie("__rf_button_art", "__rfButton", ui.getNextHighestDepth())
        if not button:
            return
        ui.__rfButton = button
        button.__rfUI = ui
        button.onPress = _global.__rfPress
        button.onRelease = _global.__rfRelease
        button.onReleaseOutside = _global.__rfReset
        button.onRollOut = _global.__rfReset
        button._focusrect = False
        button.tabEnabled = False
        button.gotoAndStop(1)
    button._x = exit._x - button._width - 6
    button._y = exit._y
    button.enabled = True

def __rfInit():
    this.__rfInitOrig()
    _global.__rfButton(this)

def __rfResize(obj):
    this.__rfResizeOrig(obj)
    _global.__rfButton(this)

def __rfBattleMode(ws):
    this.__rfBattleModeOrig(ws)
    if this.__rfButton:
        this.__rfButton.enabled = True

def __rfKill():
    if _global.__rfUI == this:
        _global.__rfFinish()
    if this.__rfButton:
        this.__rfButton.removeMovieClip()
        this.__rfButton = None
    this.__rfKillOrig()
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'location', 'Location'), 'addPlayer', '__rfAddOrig', '__rfAdd'),
        (('core', 'location', 'Location'), 'removePlayer', '__rfRemoveOrig', '__rfRemove'),
        (('gpui', 'LocationInterface'), 'init', '__rfInitOrig', '__rfInit'),
        (('gpui', 'LocationInterface'), 'resizeStage', '__rfResizeOrig', '__rfResize'),
        (('gpui', 'LocationInterface'), 'kill', '__rfKillOrig', '__rfKill'),
        (('gpui', 'LocationInterface'), 'battleMode', '__rfBattleModeOrig', '__rfBattleMode'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    from reflash_resources import patches as resource_patches
    resources = resource_patches(Asm, undef)
    return dict(globals=functions + resources['globals'], wraps=tuple(wraps) + resources['wraps'])
