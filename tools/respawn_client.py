"""Release native scene/UI subscriptions when resurrection replaces a location."""
from avm_codegen import Compiler

SOURCE = '''
def __lifeSceneKill():
    # Native init starts a repeating area scan; native kill never stops it.
    clearInterval(this.areaInterval)
    this.areaInterval = None
    this.onEnterFrame = None
    loc = this.currentLocation
    events = ["addPlayer", "removePlayer", "position", "finishPart", "finishMove", "aim", "fireAck", "dead", "enemy", "addBag", "removeBag"]
    i = 0
    while loc and i < len(events):
        loc.removeEventListener(events[i], this)
        i = i + 1
    master = this.master
    if master:
        master.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE, this, this.userStateUpdate)
        gamer = master.gamer
        if gamer:
            gamer.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE, this, this.gamerUpdate)
            if gamer.attributes:
                gamer.attributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS, this, this.gamerUpdate)
            if gamer.equipment:
                gamer.equipment.removeEventListener("changePrimary", this)
    lol.core.SceneShifter._ref.removeEventListener("sceneEnabled", this)
    return this.__lifeSceneKillOrig()

def __lifeWeaponKill():
    # These listeners are installed outside init or omitted by native kill.
    this.equipment.removeEventListener("changePrimary", this)
    this.equipment.removeEventListener(lol.events.TimeBarEvent.UNLOAD, this, this.unload)
    this.gamer.removeEventListener(lol.events.TimeBarEvent.HEAL, this, this.healTimeBar)
    lol.utils.EMouse.removeEventListener(lol.utils.EMouse.DOUBLE_CLICK, this)
    if this.item:
        this.item.removeEventListener("itemUpdate", this)
    if this.reloadItem:
        this.reloadItem.removeEventListener("itemUpdate", this, this.endTimeBar)
    if this.healItem:
        this.healItem.removeEventListener("itemUpdate", this, this.endTimeBar)
    this.onEnterFrame = None
    this.timeBar_mc.onEnterFrame = None
    this.msDamper.onEnterFrame = None
    this.reloadAlert.onEnterFrame = None
    return this.__lifeWeaponKillOrig()

def __lifeLocationKill():
    # All sources below outlive the removed location MovieClip.
    Key.removeListener(this)
    this.master.removeEventListener("changeWorld", this, this.chWAck)
    this.master.gamer.apManager.removeEventListener("actionPoints", this)
    lol.core.SceneShifter._ref.removeEventListener("resizeStage", this)
    lol.core.SceneShifter.chat.removeEventListener("chatRes", this)
    return this.__lifeLocationKillOrig()

def __lifeRegenKill():
    clearInterval(this.timer)
    this.timer = None
    this.resurrector.removeEventListener("resurrect", this)
    # The original removes this listener from addMoney_txt by mistake.
    this.addMoney_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT, this, this.addMoney)
    return this.__lifeRegenKillOrig()
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, keep, helper in (
        (('core', 'location', 'DisplayLocScene'), '__lifeSceneKillOrig', '__lifeSceneKill'),
        (('gpui', 'WeaponPan'), '__lifeWeaponKillOrig', '__lifeWeaponKill'),
        (('gpui', 'LocationInterface'), '__lifeLocationKillOrig', '__lifeLocationKill'),
        (('gpui', 'RegenerationInterface'), '__lifeRegenKillOrig', '__lifeRegenKill'),
    ):
        params, body = bodies[helper]
        wraps.append((path, 'kill', keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
