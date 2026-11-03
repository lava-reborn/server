"""Update the existing restore button after each native repair-slot path."""
from avm_codegen import Compiler


SOURCE = '''
def __restorePrice(panel):
    item = panel.repair_slot.item_mc.item
    panel.restoreGold_btn.enabled = False
    panel.restoreGoldCost_txt.text = ""
    if not item:
        panel.restoreGoldCost_txt.text = "0"
        return
    base = item.getProp("g_restore_base")
    factory = item.getProp("max_break_abs")
    ceiling = item.getProp("max_break_cur")
    if not base or not factory or ceiling < 0 or ceiling >= factory:
        return
    price = Math.max(1, Math.round(base * lol.core.GConstatns.gold_restore_price_mod * (factory - ceiling) / factory))
    panel.restoreGoldCost_txt.text = String(price / 100)
    panel.restoreGold_btn.enabled = True

def __restoreCount():
    this.__restoreCountOrig()
    _global.__restorePrice(this)

def __restoreDoubleClick():
    this.__restoreDoubleClickOrig()
    _global.__restorePrice(this)

def __restoreDrop():
    this.__restoreDropOrig()
    _global.__restorePrice(this)
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for method, keep, helper in (
        ('repairCostCount', '__restoreCountOrig', '__restoreCount'),
        ('onDoubleClick', '__restoreDoubleClickOrig', '__restoreDoubleClick'),
        ('drop', '__restoreDropOrig', '__restoreDrop'),
    ):
        params, body = bodies[helper]
        wraps.append((('gpui', 'RepairInterface'), method, keep, params, body))
    return dict(globals=[(name, params, body) for name, params, body in functions
                         if name == '__restorePrice'], wraps=tuple(wraps))
