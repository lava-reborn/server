"""One deferred input after committed firing, before native action side effects."""
from avm_codegen import Compiler

SOURCE = '''
def __bfClearInput():
    if _global.__bfInputTimer:
        clearInterval(_global.__bfInputTimer)
    _global.__bfInputTimer = None
    _global.__bfPendingInput = None
    _global.__bfRecoveryUntil = 0
    _global.__bfOwnerFigure = None
    _global.__bfMoveIntent = None
    _global.__bfObservedFigure = None

def __bfWaiting():
    if _global.__bfRecoveryUntil and getTimer() < _global.__bfRecoveryUntil:
        return True
    figure = _global.__bfOwnerFigure
    if figure and figure.behavior == "fire" and figure.onEnterFrame and figure.animationEnabled != False and figure.isActive != False and figure.is_default != True:
        if figure.__bfBursts and len(figure.__bfBursts) > 0 and figure.__bfBursts[0].got > 0:
            return True
    return False

def __bfDefer(owner, method, args):
    if not _global.__bfWaiting():
        figure = _global.__bfOwnerFigure
        if figure and figure.__bfScene:
            if figure.__bfBursts and len(figure.__bfBursts) > 0 and figure.__bfBursts[0].got > 0:
                _global.__bfVisualFlush(figure.__bfScene, figure, False)
        _global.__bfPendingInput = None
        if _global.__bfInputTimer:
            clearInterval(_global.__bfInputTimer)
        _global.__bfInputTimer = None
        return False
    master = lol.core.Master.getInstance()
    if method != "__bfRequestFireOrig" and method != "__bfRequestStrikeOrig":
        if master.gamer.acManager:
            master.gamer.acManager.autoFireTargetDead()
    _global.__bfPendingInput = {"owner":owner, "method":method, "args":args, "location":master.currentLocation}
    if not _global.__bfInputTimer:
        _global.__bfInputTimer = setInterval(_global.__bfDrainInput, 10)
    return True

def __bfDrainInput():
    pending = _global.__bfPendingInput
    if not pending:
        if _global.__bfInputTimer:
            clearInterval(_global.__bfInputTimer)
        _global.__bfInputTimer = None
        return
    master = lol.core.Master.getInstance()
    if master.currentLocation != pending.location:
        _global.__bfClearInput()
        return
    if _global.__bfWaiting():
        return
    _global.__bfPendingInput = None
    clearInterval(_global.__bfInputTimer)
    _global.__bfInputTimer = None
    figure = _global.__bfOwnerFigure
    if figure and figure.__bfBursts and len(figure.__bfBursts) > 0:
        _global.__bfVisualFlush(figure.__bfScene, figure, False)
    pending.owner[pending.method].apply(pending.owner, pending.args)

def __bfRecovery(obj):
    p = obj.param
    if not p.id and p.recovery_ms and p.recovery_ms > 0:
        until = getTimer() + p.recovery_ms
        _global.__bfRecoveryUntil = Math.max(_global.__bfRecoveryUntil or 0, until)
        _global.__bfObservedFigure = None

def __bfRecoveryNotify(cmd):
    _global.__bfQuietHit = (cmd.messID == "faHit" or cmd.messID == "caHit") and cmd.params.no_war
    if cmd.messID == "faShot" or cmd.messID == "caHit" or cmd.messID == "caMiss" or cmd.messID == "breakMv":
        _global.__bfRecovery({"param":cmd.params})
    this.__bfRecoveryNotifyOrig(cmd)
    _global.__bfQuietHit = False

def __bfExitTimer():
    if not _global.__bfQuietHit:
        this.__bfExitTimerOrig()

def __bfRetryMove(obj):
    # Native refusal consumes the original movement callback before any retry.
    this.__bfRetryMoveOrig(obj)
    p = obj.param
    intent = _global.__bfMoveIntent
    master = lol.core.Master.getInstance()
    if p.id or not p.recovery_ms or not (p.recovery_ms > 0) or not intent or intent.retried or intent.location != master.currentLocation:
        return
    pending = _global.__bfPendingInput
    if pending and pending.method != "__bfRequestMoveOrig":
        return
    intent.retried = True
    _global.__bfRecovery(obj)
    _global.__bfDefer(intent.owner, "__bfRequestMoveOrig", intent.args)

def __bfLocationShot(obj):
    _global.__bfRecovery(obj)
    this.__bfLocationShotOrig(obj)

def __bfNextSequence():
    this.__bfNextSequenceOrig()
    if this.__bfAdvanceReady:
        this.__bfAdvanceReady = False
        if this.__bfBursts and len(this.__bfBursts) > 0:
            _global.__bfVisualStart(this.__bfScene, this, this.__bfBursts[0])
    if not this.id:
        _global.__bfDrainInput()

def __bfHitTarget(event):
    figure = this.getWalker(event.targetID)
    if not figure and event.__bfPoint:
        return event.__bfPoint
    if figure and figure.behavior == "die":
        return event.__bfPoint or {"x":figure._x, "y":figure._y - 50}
    if figure and figure.__bfBursts and len(figure.__bfBursts) > 0:
        if figure.__bfBursts[0].got > 0 and (figure.behavior == "fire" or figure.behavior == "fire_out"):
            return event.__bfPoint or {"x":figure._x, "y":figure._y - 50}
    point = this.__bfHitTargetOrig(event)
    return event.__bfPoint or point

def __bfProtectedVisual(figure):
    return figure and figure.__bfBursts and len(figure.__bfBursts) > 0 and figure.__bfBursts[0].got > 0 and (figure.behavior == "fire" or figure.behavior == "fire_out")

def __bfChangingWeapon(figure):
    return figure and (figure.behavior == "arm_in" or figure.behavior == "arm_out")

def __bfBreakMove(pos):
    # A late authoritative stop must correct position, not overwrite a swap.
    this.__bfStoppingMove = True
    this.__bfStopMoveOrig(pos)
    this.__bfStoppingMove = False

def __bfFinishMove(obj):
    figure = this.getWalker(obj.walker.id)
    if not _global.__bfProtectedVisual(figure) and not _global.__bfChangingWeapon(figure):
        this.__bfFinishMoveOrig(obj)

def __bfPosition(obj):
    walker = obj.walker
    figure = this.getWalker(walker.id)
    if walker.__bfStoppingMove and (_global.__bfProtectedVisual(figure) or _global.__bfChangingWeapon(figure)):
        this.placeWalker(figure, walker.x, walker.y)
        return
    if _global.__bfProtectedVisual(figure):
        # A real new step supersedes delayed cosmetic firing on observers.
        # An authoritative stop above only corrects the position.
        _global.__bfVisualFlush(this, figure, False)
    this.__bfPositionOrig(obj)

def __bfPanelSwap():
    # Native WeaponPan locks changeFlag before calling PersEquip. Queue before
    # that lock; a replaced input must not leave the weapon button disabled.
    equip = this.equipment
    if not equip or (equip.transferStack and len(equip.transferStack) > 0):
        return
    master = lol.core.Master.getInstance()
    if master.gamer.acManager:
        master.gamer.acManager.autoFireTargetDead()
    _global.__bfMoveIntent = None
    if _global.__bfDefer(this, "changeWeapon", []):
        return
    # No transfer is in flight: a flag left by a refusal is not a real lock.
    this.changeFlag = True
    return this.__bfPanelSwapOrig()

def __bfLocationKill():
    _global.__bfClearInput()
    this.__bfLocationKillOrig()
'''

REQUESTS = (
    (('core','location','Location'), 'movePlayer', '__bfRequestMoveOrig', ('cell','spliceNum')),
    (('core','objects','ItemActivator'), 'fire', '__bfRequestFireOrig', ('targetType','target')),
    (('core','objects','ItemActivator'), 'strike', '__bfRequestStrikeOrig', ('targetType','target')),
    (('core','objects','ItemActivator'), 'loadObject', '__bfRequestLoadOrig', ('fireArm','ammo')),
    (('core','objects','ItemActivator'), 'useObjectIdle', '__bfRequestHealOrig', ('item',)),
    (('core','objects','ItemActivator'), 'useObjectToTarget', '__bfRequestTargetHealOrig', ('item','target')),
    (('core','objects','ItemActivator'), 'unloadObject', '__bfRequestUnloadOrig', ('fireArm',)),
    (('core','objects','ItemActivator'), 'changeUseMode', '__bfRequestModeOrig', ('fireArm','mode')),
    (('core','player','PersEquip'), 'changePrimary', '__bfRequestSwapOrig', ()),
    # These methods install useAck listeners or start UI effects. Defer them
    # before those side effects, not just ItemActivator's eventual request.
    (('core','player','PersEquip'), 'loadFireArm', '__bfEquipLoadOrig', ('fireArm','ammo')),
    (('core','player','PersEquip'), 'unloadFireArm', '__bfEquipUnloadOrig', ('fireArm',)),
    (('core','player','PersEquip'), 'changeFireMode', '__bfEquipModeOrig', ('mode',)),
    (('core','player','PersEquip'), 'useHealItem', '__bfEquipHealOrig', ()),
    (('core','player','PersEquip'), 'useEatItem', '__bfEquipEatOrig', ()),
)


def patches(Asm, undef):
    source = SOURCE
    for i, (path, method, keep, params) in enumerate(REQUESTS):
        args = ', '.join(params)
        stop_auto = ''
        if method in ('changePrimary', 'movePlayer'):
            # Stop repeat fire even before recovery starts, while still aiming.
            stop_auto = '''    master = lol.core.Master.getInstance()
    if master.gamer.acManager:
        master.gamer.acManager.autoFireTargetDead()
'''
        remember = '    _global.__bfMoveIntent = None\n'
        if method == 'movePlayer':
            remember = '''    master = lol.core.Master.getInstance()
    _global.__bfMoveIntent = {"owner":this, "args":[cell, spliceNum], "location":master.currentLocation, "retried":False}
'''
        source += f'''
def __bfRequest{i}({args}):
{stop_auto}{remember}    if _global.__bfDefer(this, "{keep}", [{args}]):
        return
    return this.{keep}({args})
'''
    functions = Compiler(Asm, undef).functions(source)
    bodies = {name:(params,body) for name,params,body in functions}
    wraps=[]
    for path,method,keep,helper in (
        (('server','XMLConnection'),'sendNotification','__bfRecoveryNotifyOrig','__bfRecoveryNotify'),
        (('core','location','Location'),'faShot','__bfLocationShotOrig','__bfLocationShot'),
        (('core','location','Location'),'breakMv','__bfRetryMoveOrig','__bfRetryMove'),
        (('gpui','LocationInterface'),'startExitTimer','__bfExitTimerOrig','__bfExitTimer'),
        (('core','location','LocWalker'),'breakMove','__bfStopMoveOrig','__bfBreakMove'),
        (('core','location','Char'),'nextSequence','__bfNextSequenceOrig','__bfNextSequence'),
        (('core','location','DisplayLocScene'),'hitTarget','__bfHitTargetOrig','__bfHitTarget'),
        (('core','location','DisplayLocScene'),'finishMove','__bfFinishMoveOrig','__bfFinishMove'),
        (('core','location','DisplayLocScene'),'position','__bfPositionOrig','__bfPosition'),
        (('gpui','WeaponPan'),'changeWeapon','__bfPanelSwapOrig','__bfPanelSwap'),
        (('core','location','Location'),'kill','__bfLocationKillOrig','__bfLocationKill'),
    ):
        params,body=bodies[helper]
        wraps.append((path,method,keep,params,body))
    for i,(path,method,keep,_) in enumerate(REQUESTS):
        params,body=bodies[f'__bfRequest{i}']
        wraps.append((path,method,keep,params,body))
    return dict(globals=functions,wraps=tuple(wraps))
