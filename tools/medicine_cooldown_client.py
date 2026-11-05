"""A short medicine debuff rendered with the native FX shortcut and timer."""
from avm_codegen import Compiler

SOURCE = '''
def __bfMedHover():
    _global.__bfMedHintIcon = this
    lol.gpui.HintManager.showHint(_global.__bfMedDescription, 0, this._width)

def __bfMedOut():
    if _global.__bfMedHintIcon == this:
        _global.__bfMedHintIcon = None
        lol.gpui.HintManager.closeHint()

def __bfMedRemove(view):
    icon = view.__bfMedIcon
    if icon:
        if _global.__bfMedHintIcon == icon:
            _global.__bfMedHintIcon = None
            lol.gpui.HintManager.closeHint()
        icon.removeMovieClip()
        view.__bfMedIcon = None

def __bfMedDraw(icon):
    # Draw above the native shortcut chrome, not inside its placeholder.
    # The placeholder can contain its own mask/display object lifecycle.
    drawing = icon.createEmptyMovieClip("__bfBrokenCross", icon.getNextHighestDepth())
    drawing._x = 4
    drawing._y = 3
    drawing.lineStyle(1, 5196098, 100)
    drawing.beginFill(10691121, 100)
    points = [[8,1],[16,1],[16,8],[23,8],[23,16],[16,16],[16,23],[8,23],[8,16],[1,16],[1,8],[8,8],[8,1]]
    drawing.moveTo(8, 1)
    i = 1
    while i < len(points):
        drawing.lineTo(points[i][0], points[i][1])
        i = i + 1
    drawing.endFill()
    drawing.lineStyle(2, 1907480, 100)
    drawing.moveTo(2, 18)
    drawing.lineTo(10, 13)
    drawing.lineTo(8, 10)
    drawing.lineTo(15, 12)
    drawing.lineTo(22, 6)

def __bfMedFindView():
    shifter = lol.core.SceneShifter
    if shifter and shifter._ref and shifter._ref.currentScene:
        panel = shifter._ref.currentScene.effectsPan
        if panel:
            content = panel.content
            if content and content.core_mc:
                return content
            return None
    return _global.__bfMedView

def __bfMedTick():
    view = _global.__bfMedFindView()
    old = _global.__bfMedView
    if old and old != view:
        _global.__bfMedRemove(old)
    _global.__bfMedView = view
    left = (_global.__bfMedUntil or 0) - getTimer()
    if not (left > 0):
        if view:
            _global.__bfMedRemove(view)
        if _global.__bfMedTimer:
            clearInterval(_global.__bfMedTimer)
        _global.__bfMedTimer = None
        return
    # Stay alive only for these four seconds, including a collapsed panel.
    # This also handles a canvas whose native constructor predates our hooks.
    if not _global.__bfMedTimer:
        _global.__bfMedTimer = setInterval(_global.__bfMedTick, 100)
    if not view:
        return
    icon = view.__bfMedIcon
    if not icon:
        icon = view.core_mc.attachMovie("FX_Shortcut", "__bfMedicineCooldown", view.core_mc.getNextHighestDepth())
        if not icon:
            return
        view.__bfMedIcon = icon
        icon._visible = False
    # Timeline children may not exist until the next Flash frame. Never scale
    # an empty clip or mark its initial caption as painted before it is ready.
    if not icon.EstimateTime or not (icon._height > 0):
        return
    if not icon.__bfMedReady:
        _global.__bfMedDraw(icon)
        if icon.EffectIcon:
            icon.EffectIcon._visible = False
        icon.EstimateTime.autoSize = False
        icon.EstimateTime._x = 0
        icon.EstimateTime._width = 32
        icon.onRollOver = _global.__bfMedHover
        icon.onRollOut = _global.__bfMedOut
        icon.__bfMedReady = True
    icon._x = 35
    icon._y = icon._height * (view.debuff_length or 0)
    icon._alpha = 100
    icon._visible = True
    seconds = Math.ceil(left / 1000)
    if icon.__bfSeconds != seconds:
        icon.__bfSeconds = seconds
        icon.EstimateTime.text = "00:0" + String(seconds)

def __bfMedNotify(cmd):
    this.__bfMedNotifyOrig(cmd)
    if cmd.messID == "medCooldown":
        _global.__bfMedUntil = getTimer() + Math.min(4000, Math.max(0, cmd.params.time_ms * 1))
        _global.__bfMedDescription = cmd.params.description
        _global.__bfMedTick()

def __bfMedInit():
    this.__bfMedInitOrig()
    _global.__bfMedView = this
    this.onUnload = _global.__bfMedDetach
    _global.__bfMedTick()

def __bfMedEffects(obj):
    this.__bfMedEffectsOrig(obj)
    if _global.__bfMedView == this:
        _global.__bfMedTick()

def __bfMedDetach():
    _global.__bfMedRemove(this)
    if _global.__bfMedView == this:
        _global.__bfMedView = None
        if not ((_global.__bfMedUntil or 0) > getTimer()):
            if _global.__bfMedTimer:
                clearInterval(_global.__bfMedTimer)
            _global.__bfMedTimer = None

def __bfMedKill():
    _global.__bfMedDetach.apply(this, [])
    this.__bfMedKillOrig()
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name:(params,body) for name,params,body in functions}
    wraps=[]
    for path,method,keep,helper in (
        (('server','XMLConnection'),'sendNotification','__bfMedNotifyOrig','__bfMedNotify'),
        (('core','effects','DisplayFX'),'init','__bfMedInitOrig','__bfMedInit'),
        (('core','effects','DisplayFX'),'effectsUpdate','__bfMedEffectsOrig','__bfMedEffects'),
        (('core','effects','DisplayFX'),'kill','__bfMedKillOrig','__bfMedKill'),
    ):
        params,body=bodies[helper]
        wraps.append((path,method,keep,params,body))
    return dict(globals=functions,wraps=tuple(wraps))
