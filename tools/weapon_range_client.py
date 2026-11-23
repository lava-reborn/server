"""Use exact ordinary firing distances in the native cursor and auto-fire gate."""
from avm_codegen import Compiler


SOURCE = '''
def __wrWeaponRange(item):
    if not item or item.rootID != lol.core.objects.Item.FIRE_ARM:
        return None
    mode = Number(item.getProp("cur_mode"))
    if isNaN(mode):
        mode = 0
    if mode < 0 or mode > 2 or mode != Math.floor(mode):
        return None
    ranges = item.getProp("max_range")
    if not ranges:
        return None
    reach = Number(ranges[mode])
    if isNaN(reach) or reach <= 0:
        return None
    multiplier = 1
    ammoType = item.getProp("ammo_type")
    # Only inspect prototypes the existing inventory loader already cached.
    # A mouse movement must never create items or send static-info requests.
    cached = lol.core.objects.ItemFactory.itemTypeStore[ammoType]
    if cached and cached.item:
        value = Number(cached.item.getProp("range_mod"))
        if not isNaN(value) and value > 0:
            multiplier = value
    return {"maximum":Math.floor(reach * multiplier + Number("0.000000001")), "mode":mode}

def __wrCursorDistance():
    this.__wrCursorDistanceOrig()
    # Private range profiles use their own ammunition and reach equations.
    if _global.__tgActive:
        return
    master = this.target.master
    location = master.currentLocation
    item = master.gamer.equipment.primaryItem
    limits = _global.__wrWeaponRange(item)
    if not limits:
        return
    own = location.getCellFromNumber(master.gamer.walker.numPos)
    if this.sfManager.flared:
        figure = location.getWalker(this.sfManager.flared.target.id)
        if not figure:
            return
        cell = location.getCellFromNumber(figure.numPos)
    else:
        cell = location.getCellFromReal(this.currentCursor._x, this.currentCursor._y)
    if not own or not cell:
        return
    distance = location.locationGrid.getHexDistance(own, cell)
    if isNaN(distance):
        return
    # Keep the native one-decimal text, but never round before comparing.
    this.tf.color = 16711680
    if distance <= limits.maximum:
        this.tf.color = 16777215
        low = item.getProp("opt_range")[limits.mode]
        high = item.getProp("end_opt_range")[limits.mode]
        if distance >= low and distance <= high:
            this.tf.color = 65280
    this.distance_txt.setTextFormat(this.tf)

def __wrAutoDistance():
    if _global.__tgActive:
        return this.__wrAutoDistanceOrig()
    master = lol.core.Master.getInstance()
    item = master.gamer.equipment.primaryItem
    limits = _global.__wrWeaponRange(item)
    if not limits:
        return this.__wrAutoDistanceOrig()
    location = master.currentLocation
    figure = location.getWalker(this.autoFireTargetID)
    if not figure:
        return False
    own = location.getCellFromNumber(master.gamer.walker.numPos)
    cell = location.getCellFromNumber(figure.numPos)
    if not own or not cell:
        return False
    distance = location.locationGrid.getHexDistance(own, cell)
    return not isNaN(distance) and distance <= limits.maximum
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'location', 'CursorManager'), 'calcDistance', '__wrCursorDistanceOrig', '__wrCursorDistance'),
        (('services', 'AutoCommandManager'), 'checkDistance', '__wrAutoDistanceOrig', '__wrAutoDistance'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
