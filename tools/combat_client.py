"""Combat presentation, nearby loot and specialization-window lifecycle fixes."""
from avm_codegen import Compiler

SOURCE = '''
def __bfTrainingClose(obj):
    if obj:
        if obj.target:
            obj.target.removeEventListener("close", this)
    else:
        cluster = new(lol.data.BigUINTCluster, 0)
        number = new(lol.data.BigUINT, cluster)
        message = new(lol.server.mess.CSM_SSUpdate, lol.core.player.Training.UPD_CLOSE, number)
        this.XMC.Send(message)
    this.dispatchEvent({"type":"close"})
    avatar = lol.core.SceneShifter.linkGame.visavisAvatar
    if avatar:
        avatar.removeMovieClip()
    this.kill()

def __bfLootOpen(pos):
    this.walker.removeEventListener("finishMove", this)
    loc = lol.core.Master.getInstance().currentLocation
    here = loc.getCellFromNumber(this.walker.numPos)
    bag = loc.getCellFromNumber(pos)
    if here and bag and loc.locationGrid.getHexDistance(here, bag) <= Number("1.01"):
        this.loot = new(lol.core.player.Loot)
        this.loot.createSession(pos)

def __bfLootGo(pos):
    if _global.__bfDefer(this, "gotoLoot", [pos]):
        return
    loc = lol.core.Master.getInstance().currentLocation
    here = loc.getCellFromNumber(this.walker.numPos)
    bag = loc.getCellFromNumber(pos)
    if not here or not bag:
        return
    if loc.locationGrid.getHexDistance(here, bag) <= Number("1.01"):
        this.createLoot(pos)
        return
    choices = loc.locationGrid.getSiblings(bag)
    best = None
    distance = 1000000
    i = 0
    while i < len(choices):
        cell = choices[i]
        if not cell.busy and not cell.alwaysBusy and not cell.unreachable:
            d = loc.locationGrid.getHexDistance(here, cell)
            if d < distance:
                best = cell
                distance = d
        i = i + 1
    if best:
        this.stuff_param = pos
        this.stuff_func = this.createLoot
        this.walker.addEventListener("finishMove", this)
        loc.movePlayer(best)

def __bfHealth(percent, value):
    p = Number(percent)
    if isNaN(p):
        p = 0
    this.__bfHealthOrig(Math.max(0, Math.min(100, p)), value)

def __bfStamina(percent, value):
    p = Number(percent)
    if isNaN(p):
        p = 0
    this.__bfStaminaOrig(Math.max(0, Math.min(100, p)), value)

def __bfVisualStart(scene, figure, bundle):
    bundle.active = True
    figure.__fireCount = 0
    scene.__bfAimOrig(bundle.aim)
    i = 0
    while i < len(bundle.events):
        scene.__bfFireOrig(bundle.events[i])
        i = i + 1
    bundle.events = []

def __bfVisualFlush(scene, figure, draw):
    bursts = figure.__bfBursts
    bullets = figure.burstArr
    figure.__bfBursts = []
    figure.burstArr = []
    figure.__bfIncoming = None
    figure.__bfAdvanceReady = False
    figure.removeEventListener("finalFrame", scene, scene.shotgunFireAck)
    figure.removeEventListener("finalFrame", scene, scene.busrtFireAck)
    i = 0
    while i < len(bullets):
        if draw != False:
            scene.applyFireAck(bullets[i])
        i = i + 1
    i = 0
    while i < len(bursts):
        bundle = bursts[i]
        j = 0
        while j < len(bundle.events):
            event = bundle.events[j]
            if event.access:
                scene.addFireAckReport(event)
                if draw != False:
                    scene.applyFireAck(event)
            j = j + 1
        i = i + 1
    scene.showFireAckReport()
    figure.removeEventListener("finalFrame", scene, _global.__bfVisualFinal)

def __bfVisualFinal(obj):
    figure = obj.target
    if not figure.__bfBursts or len(figure.__bfBursts) == 0:
        return
    if obj.data == "die" or obj.data == "run":
        _global.__bfVisualFlush(this, figure, False)
        return
    current = figure.__bfBursts[0]
    if current.got < current.expected:
        return
    if obj.data != "fire_out" and obj.data != "stand":
        return
    # This listener can run before the native burst cleanup on the same
    # finalFrame. Drop unplayed cosmetic traces without another visual cycle.
    bullets = figure.burstArr
    figure.burstArr = []
    if len(bullets) > 0:
        this.showFireAckReport()
    figure.__bfBursts.shift()
    if len(figure.__bfBursts) > 0:
        figure.__bfAdvanceReady = True
    else:
        figure.__bfIncoming = None
        figure.removeEventListener("finalFrame", this, _global.__bfVisualFinal)

def __bfAim(obj):
    figure = this.getWalker(obj.aim)
    if not figure:
        this.__bfAimOrig(obj)
        return
    figure.__bfScene = this
    if not obj.aim:
        _global.__bfOwnerFigure = figure
    figure.__bfSkipVisual = figure.animationEnabled == False or figure.isActive == False
    if figure.__bfSkipVisual:
        if figure.__bfBursts and len(figure.__bfBursts) > 0:
            _global.__bfVisualFlush(this, figure)
        this.__bfAimOrig(obj)
        return
    if not figure.__bfBursts:
        figure.__bfBursts = []
    if len(figure.__bfBursts) > 0 and figure.__bfBursts[0].got == 0:
        figure.__bfBursts.shift()
    if len(figure.__bfBursts) >= 8:
        _global.__bfVisualFlush(this, figure, False)
    bundle = {"aim":obj, "expected":Math.max(1, obj.num_shots), "got":0, "events":[], "active":False}
    figure.__bfIncoming = bundle
    figure.__bfBursts.push(bundle)
    figure.addEventListener("finalFrame", this, _global.__bfVisualFinal)
    if len(figure.__bfBursts) == 1:
        _global.__bfVisualStart(this, figure, bundle)

def __bfFire(event):
    figure = this.getWalker(event.gunnerID)
    if figure and figure.__bfSkipVisual:
        if event.access:
            this.addFireAckReport(event)
            this.applyFireAck(event)
            this.showFireAckReport()
        return
    if not figure or not figure.__bfIncoming:
        this.__bfFireOrig(event)
        return
    bundle = figure.__bfIncoming
    bundle.got = bundle.got + 1
    if bundle.active:
        this.__bfFireOrig(event)
    else:
        bundle.events.push(event)

def __bfBurstFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        obj.target.burstArr = []
        this.showFireAckReport()
    this.__bfBurstFinalOrig(obj)

def __bfShotgunFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        obj.target.burstArr = []
        this.showFireAckReport()
    this.__bfShotgunFinalOrig(obj)

def __bfDead(obj):
    if not obj.dead:
        _global.__bfClearInput()
    figure = this.getWalker(obj.dead)
    if figure and figure.__bfBursts:
        _global.__bfVisualFlush(this, figure, False)
    this.__bfDeadOrig(obj)
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core','player','Training'), 'close', '__bfTrainingCloseOrig', '__bfTrainingClose'),
        (('core','player','Gamer'), 'gotoLoot', '__bfLootGoOrig', '__bfLootGo'),
        (('core','player','Gamer'), 'createLoot', '__bfLootOpenOrig', '__bfLootOpen'),
        (('core','location','CharInfo'), 'showHealth', '__bfHealthOrig', '__bfHealth'),
        (('core','location','CharInfo'), 'showStamina', '__bfStaminaOrig', '__bfStamina'),
        (('core','location','DisplayLocScene'), 'aim', '__bfAimOrig', '__bfAim'),
        (('core','location','DisplayLocScene'), 'fireAck', '__bfFireOrig', '__bfFire'),
        (('core','location','DisplayLocScene'), 'busrtFireAck', '__bfBurstFinalOrig', '__bfBurstFinal'),
        (('core','location','DisplayLocScene'), 'shotgunFireAck', '__bfShotgunFinalOrig', '__bfShotgunFinal'),
        (('core','location','DisplayLocScene'), 'dead', '__bfDeadOrig', '__bfDead'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    from action_recovery_client import patches as recovery_patches
    recovery = recovery_patches(Asm, undef)
    from medicine_cooldown_client import patches as medicine_patches
    medicine = medicine_patches(Asm, undef)
    return dict(globals=functions + recovery['globals'] + medicine['globals'],
                wraps=tuple(wraps) + recovery['wraps'] + medicine['wraps'])
