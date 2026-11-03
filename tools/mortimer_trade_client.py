"""Gold-only Mortimer sell quotes without changing global item prices."""
from avm_codegen import Compiler

SOURCE = '''
def __moActive():
    panel = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if not panel or not panel.trader:
        return False
    t = panel.trader.playerInfo.resID
    return __NPC_TEST__

def __moUnit(item):
    if not item or item.rootID != 4:
        return 0
    t = item.typeID
    if not (__ITEM_TEST__):
        return 0
    return Math.floor(item.getProp("cost") / 500)

def __moShowCost(item, align):
    this.__moShowCostOrig(item, align)
    if not this.showItemSellMod:
        return
    if not _global.__moActive():
        if _global.__moUnit(item) > 0:
            this.price_mc._visible = False
        return
    unit = _global.__moUnit(item)
    if unit <= 0:
        this.price_mc._visible = False
        return
    this.price_mc._visible = True
    n = 1
    if this.showHeapCount and item.getProp("size"):
        n = item.getProp("size")
    amount = unit * n / 100
    this.price_mc.gotoAndStop(2)
    this.mainCost = amount
    this.costType = "Золото"
    value = amount
    if not this.attachIconEnabled:
        value = "g" + String(amount)
    this.price_mc.fontContainer.showValue(value)

def __moCheckSell(item):
    if not _global.__moActive() and _global.__moUnit(item) > 0:
        return "Золотые ценности можно продать за золото только Мортимеру."
    if _global.__moActive() and _global.__moUnit(item) <= 0:
        return "Мортимер принимает только золотые ценности. Золотой песок можно обменять через задания."
    return this.__moCheckSellOrig(item)

def __moExchange(item, title, mode, showGold, selling):
    pan = this.__moExchangeOrig(item, title, mode, showGold, selling)
    if selling and _global.__moActive() and _global.__moUnit(item) > 0:
        pan.cost_num = _global.__moUnit(item)
        pan.cost_mod = 1
        pan.showCostInGold = True
        pan.label = "Сколько штук продать за золото?"
    return pan
'''


def patches(Asm, undef):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
    import mortimer
    source=SOURCE.replace('__NPC_TEST__',' or '.join('t == %d'%n for n in sorted(mortimer.NPC_TYPES)))
    source=source.replace('__ITEM_TEST__',' or '.join('t == %d'%n for n in sorted(mortimer.VALUABLES)))
    functions=Compiler(Asm,undef).functions(source)
    bodies={name:(params,body) for name,params,body in functions}
    wraps=[]
    for path,method,keep,helper in (
        (('gpui','ItemContainer'),'showCost','__moShowCostOrig','__moShowCost'),
        (('gpui','TradeInterface'),'checkSellItem','__moCheckSellOrig','__moCheckSell'),
        (('gpui','TradeInterface'),'createExchangePan','__moExchangeOrig','__moExchange')):
        params,body=bodies[helper];wraps.append((path,method,keep,params,body))
    return dict(globals=functions[:2],wraps=tuple(wraps))
