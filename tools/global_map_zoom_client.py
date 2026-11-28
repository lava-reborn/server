"""Extra global-map zoom with matching selection and native saved preferences."""
from avm_codegen import Compiler


SOURCE = '''
def __gzLandscapeScale(kind):
    result = this.__gzLandscapeScaleOrig(kind)
    # Native overview/full calls also leave a previous enlarged grid behind.
    this.locationSize = 8
    return result

def __gzScaleUp():
    land = this.landscape
    if not land or land.mapScaleType != "full":
        return this.__gzScaleUpOrig()
    if land.mapScale >= 12:
        return
    # Keep the full tile folder and the same 32 world cells per tile.
    land.setScale("full")
    land.mapScale = 12
    land.cellSize = 384
    land.locationSize = 12
    # Native build centring otherwise compares only the unchanged folder.
    this.curScaleType = None
    return this.redrawMap()

def __gzScaleDown():
    land = this.landscape
    if land and land.mapScaleType == "full" and land.mapScale > 8:
        this.curScaleType = None
        return this.setScale("full")
    return this.__gzScaleDownOrig()

def __gzFitLocBorder(border, scale):
    if not border:
        return
    factor = 1
    if scale > 8:
        factor = scale / 8
    border._xscale = 100 * factor
    border._yscale = 100 * factor
    title = border.name_txt
    if not title:
        return
    if border.__gzTitleX == None:
        border.__gzTitleX = title._x
        border.__gzTitleY = title._y
        border.__gzTitleScaleX = title._xscale
        border.__gzTitleScaleY = title._yscale
    # Enlarge the square, keeping the native text size and gap after it.
    title._xscale = border.__gzTitleScaleX / factor
    title._yscale = border.__gzTitleScaleY / factor
    title._x = (border.__gzTitleX + 8 * (factor - 1)) / factor
    title._y = border.__gzTitleY / factor

def __gzDrawLocBorder(name, x, y):
    result = this.__gzLocBorderOrig(name, x, y)
    _global.__gzFitLocBorder(this.locBorder_mc, this.displayMap.mapScale)
    return result

def __gzRedrawMap():
    # An old hover belongs to the previous screen position after zooming.
    scale = this.landscape.mapScale
    if this.__gzBorderScale != scale:
        if this.locBorder:
            this.locBorder._visible = False
        this.__gzBorderScale = scale
    return this.__gzRedrawOrig()

def __gzMoveToLabel(obj):
    index = this.displayMap.markManager.getMarkNum(obj.target.markObj)
    mark = this.displayMap.markManager.markList[index]
    if mark._x != None and mark._y != None:
        half = this.displayMap.mapScale / 2
        this.displayMap.playerMoveToCoords(mark._x + half, mark._y + half)

def __gzUiScaleUp():
    this.displayMap.scaleUp()
    value = "up"
    if this.displayMap.mapScale > 8:
        value = "zoom"
    lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.GLOBAL_SCALE, value)

def __gzUiScaleDown():
    this.displayMap.scaleDown()
    value = "down"
    if this.displayMap.mapScale >= 8:
        value = "up"
    lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.GLOBAL_SCALE, value)

def __gzUiInit():
    saved = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.GLOBAL_SCALE)
    result = this.__gzUiInitOrig()
    if saved == "zoom" and this.displayMap and this.displayMap.landscape:
        # Native init understands up/down; restore the third step afterwards.
        # Set the folder without drawing an intermediate full-size map.
        this.displayMap.landscape.setScale("full")
        this.displayMap.scaleUp()
    return result
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (args, body) for name, args, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'globmap', 'DisplayLandscape'), 'setScale', '__gzLandscapeScaleOrig', '__gzLandscapeScale'),
        (('core', 'globmap', 'DisplayGlobalMap'), 'scaleUp', '__gzScaleUpOrig', '__gzScaleUp'),
        (('core', 'globmap', 'DisplayGlobalMap'), 'scaleDown', '__gzScaleDownOrig', '__gzScaleDown'),
        (('core', 'globmap', 'DisplayGlobalMap'), 'redrawMap', '__gzRedrawOrig', '__gzRedrawMap'),
        (('gpui', 'GlobalMapInterface'), 'drawLocBorder', '__gzLocBorderOrig', '__gzDrawLocBorder'),
        (('gpui', 'GlobalMapInterface'), '_moveToLabel', '__gzMoveToLabelOrig', '__gzMoveToLabel'),
        (('gpui', 'GlobalMapInterface'), 'scaleUp', '__gzUiScaleUpOrig', '__gzUiScaleUp'),
        (('gpui', 'GlobalMapInterface'), 'scaleDown', '__gzUiScaleDownOrig', '__gzUiScaleDown'),
        (('gpui', 'GlobalMapInterface'), 'init', '__gzUiInitOrig', '__gzUiInit'),
    ):
        wraps.append((path, method, keep, *bodies[helper]))
    return dict(globals=[(name, args, body) for name, args, body in functions
                         if name == '__gzFitLocBorder'], wraps=tuple(wraps))
