"""Combat presentation, nearby loot and specialization-window lifecycle fixes."""
from avm_codegen import Compiler

SOURCE = '''
def __bfRemotePrimary(obj):
    # Native ss_obj_move constructs a type-0 firearm for an empty hand.
    # Empty snapshots must use PersEquip's existing bare-fist fallback.
    if not this.isGamer and obj.param.to == 512 and obj.param.obj == "0":
        this.primaryItem = None
        return
    return this.__bfRemotePrimaryOrig(obj)

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

def __bfLootReachable(loc, here, cell):
    width = 30
    height = 40
    if lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.PATH_FINDING):
        width = loc.locInfo.width
        height = loc.locInfo.height
    x = Math.max(0, Math.floor((cell.gx + here.gx - width) / 2))
    y = Math.max(0, Math.floor((cell.gy + here.gy - height) / 2))
    if Math.abs(cell.gx - here.gx) > width or Math.abs(cell.gy - here.gy) > height:
        return False
    path = loc.locationGrid.searchWay(here.gx - x, here.gy - y, cell.gx - x, cell.gy - y, x, y, width, height)
    size = len(path)
    return size > 0 and path[size - 1][0] == cell.gx and path[size - 1][1] == cell.gy

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
    choices = loc.locationGrid.getSiblings(bag).concat([])
    best = None
    while len(choices) > 0 and not best:
        distance = 1000000
        index = 0
        i = 0
        while i < len(choices):
            d = loc.locationGrid.getHexDistance(here, choices[i])
            if d < distance:
                index = i
                distance = d
            i = i + 1
        cell = choices[index]
        choices.splice(index, 1)
        if not cell.busy and not cell.alwaysBusy and not cell.unreachable:
            if _global.__bfLootReachable(loc, here, cell):
                best = cell
    if best:
        this.walker.removeEventListener("finishMove", this)
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

def __bfAimSound(scene, aim):
    # Snapshot the aiming weapon intentionally: a fallback for that confirmed
    # volley must not take the sound of a newly switched weapon.
    if scene.master:
        player = scene.master.getPlayer(aim)
        if player and player.equipment:
            item = player.equipment.primaryItem
            if item and item.getProp:
                weapon = item.getProp("weapon_type")
                if weapon == lol.core.objects.FireArm.PISTOL:
                    return lol.sound.SoundEvent.PISTOL_FIRE
                if weapon == lol.core.objects.FireArm.SHOTGUN:
                    return lol.sound.SoundEvent.SHOTGUN_FIRE
                if weapon == lol.core.objects.FireArm.ASSAULT:
                    return lol.sound.SoundEvent.ASSAULT_FIRE
                if weapon == lol.core.objects.FireArm.RIFLE:
                    return lol.sound.SoundEvent.RIFLE_FIRE
                if weapon == lol.core.objects.FireArm.MACHINEGUN:
                    return lol.sound.SoundEvent.MACHINEGUN_FIRE
                if weapon == lol.core.objects.FireArm.SMG:
                    return lol.sound.SoundEvent.SMG_FIRE
    return None

def __bfPresentInterrupted(scene, figure, event):
    # A confirmed volley must not become completely invisible when the next
    # authoritative action interrupts its first visual frame. Show at most
    # one captured trace per unplayed volley, not its entire remaining burst.
    bundle = event.__bfBundle
    if not bundle or bundle.shown or event.__bfPresented or not event.shot or not event.access:
        return
    if figure.animationEnabled == False or figure.isActive == False or not event.hits or len(event.hits) == 0:
        return
    bundle.shown = True
    scene.applyFireAck(event)
    event.__bfPresented = True
    if lol.sound and lol.sound.SoundManager:
        sound = bundle.sound or lol.sound.SoundEvent.FIREARM_FIRE
        lol.sound.SoundManager.getInstance().playEventSound(sound)

def __bfVisualFlush(scene, figure, draw):
    bursts = figure.__bfBursts or []
    bullets = figure.burstArr or []
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
        else:
            _global.__bfPresentInterrupted(scene, figure, bullets[i])
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
                else:
                    _global.__bfPresentInterrupted(scene, figure, event)
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
    i = 0
    while i < len(bullets):
        _global.__bfPresentInterrupted(this, figure, bullets[i])
        i = i + 1
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
    bundle = {"aim":obj, "expected":Math.max(1, obj.num_shots), "got":0, "events":[], "active":False, "shown":False, "sound":_global.__bfAimSound(this, obj.aim)}
    figure.__bfIncoming = bundle
    figure.__bfBursts.push(bundle)
    figure.addEventListener("finalFrame", this, _global.__bfVisualFinal)
    if len(figure.__bfBursts) == 1:
        _global.__bfVisualStart(this, figure, bundle)

def __bfFire(event):
    figure = this.getWalker(event.gunnerID)
    if figure and event.shot and event.access:
        # Delayed cosmetic playback must not follow figures to new cells.
        event.__bfOrigin = {"x":figure._x, "y":figure._y - 50}
        i = 0
        while event.hits and i < len(event.hits):
            hit = event.hits[i]
            if hit.type == "target":
                target = this.getWalker(hit.targetID)
                if target:
                    hit.__bfPoint = {"x":target._x, "y":target._y - 50}
            i = i + 1
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
    event.__bfBundle = bundle
    bundle.got = bundle.got + 1
    if bundle.active:
        this.__bfFireOrig(event)
    else:
        bundle.events.push(event)

def __bfApplyFire(event):
    if event.shot:
        if event.__bfPresented:
            return
        event.__bfPresented = True
        if event.__bfBundle:
            event.__bfBundle.shown = True
    if not event.__bfOrigin:
        return this.__bfApplyFireOrig(event)
    point = None
    while len(event.hits) > 0:
        hit = event.hits.shift()
        if hit.type == "point":
            point = this.hitPoint(hit)
        elif hit.type == "wall":
            point = this.hitWall(hit)
        elif hit.type == "target":
            point = this.hitTarget(hit)
    if event.shot and point:
        this.traceShot(event.gunnerID, point, event.__bfOrigin)

def __bfTraceShot(gunnerID, point, origin):
    if not origin:
        return this.__bfTraceShotOrig(gunnerID, point)
    if not point:
        return
    trace = new(lol.fx.ShotTrace)
    trace.traceShot(this.helpers_mc, origin, {"x":point.x + Math.random() * 20 - 10, "y":point.y + Math.random() * 20 - 10})

def __bfBurstFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        _global.__bfVisualFlush(this, obj.target, False)
    this.__bfBurstFinalOrig(obj)

def __bfShotgunFinal(obj):
    if obj.data != "fire" and obj.target.burstArr:
        _global.__bfVisualFlush(this, obj.target, False)
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
        (('core','player','PersEquip'), 'ss_obj_move', '__bfRemotePrimaryOrig', '__bfRemotePrimary'),
        (('core','player','Training'), 'close', '__bfTrainingCloseOrig', '__bfTrainingClose'),
        (('core','player','Gamer'), 'gotoLoot', '__bfLootGoOrig', '__bfLootGo'),
        (('core','player','Gamer'), 'createLoot', '__bfLootOpenOrig', '__bfLootOpen'),
        (('core','location','CharInfo'), 'showHealth', '__bfHealthOrig', '__bfHealth'),
        (('core','location','CharInfo'), 'showStamina', '__bfStaminaOrig', '__bfStamina'),
        (('core','location','DisplayLocScene'), 'aim', '__bfAimOrig', '__bfAim'),
        (('core','location','DisplayLocScene'), 'fireAck', '__bfFireOrig', '__bfFire'),
        (('core','location','DisplayLocScene'), 'applyFireAck', '__bfApplyFireOrig', '__bfApplyFire'),
        (('core','location','DisplayLocScene'), 'traceShot', '__bfTraceShotOrig', '__bfTraceShot'),
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
    from respawn_client import patches as respawn_patches
    respawn = respawn_patches(Asm, undef)
    return dict(globals=functions + recovery['globals'] + medicine['globals'] + respawn['globals'],
                wraps=tuple(wraps) + recovery['wraps'] + medicine['wraps'] + respawn['wraps'])
