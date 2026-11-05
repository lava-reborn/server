"""G commerce quotes/confirmation; purchase and repair prices stay native."""
from avm_codegen import Compiler

SOURCE = '''
def __gcInitialize(obj):
    this.__gcInitializeOrig(obj)
    this.g_restore_base = obj.g_restore_base
    this.a_sale_unit = obj.a_sale_unit
    this.g_sale_unit = obj.g_sale_unit
    this.bp_sell = obj.bp_sell
    this.a_sale_cap = obj.a_sale_cap
    this.g_transfer = obj.g_transfer
    this.g_auction_base = obj.g_auction_base

def __gcGetProp(prop):
    value = this.__gcGetPropOrig(prop)
    if prop == "exchang":
        transfer = this.__gcGetPropOrig("g_transfer")
        if transfer != None:
            return transfer
    return value

def __gcQuality(item):
    top = item.getProp("max_break_cur")
    if top > 0:
        return Math.min(1, item.getProp("__break") / top)
    top = item.getProp("max_use_count")
    if item.rootID == 2 and top > 0:
        return Math.min(1, item.getProp("use_count") / top)
    return 1

def __gcSaleQuality(item):
    if item.rootID == 0 or item.rootID == 1 or item.rootID == 5:
        factory = item.getProp("max_break_abs")
        ceiling = item.getProp("max_break_cur")
        if not factory or factory <= 0 or not ceiling or ceiling <= 0:
            return 0
        return Math.max(0, Math.min(1, Math.min(item.getProp("__break"), ceiling) / factory))
    return _global.__gcQuality(item)

def __gcShowCost(item, align):
    this.__gcShowCostOrig(item, align)
    if lol.gpui.StaffInterface.ssType != "trade":
        return
    base = item.getProp("g_sale_unit")
    if not base:
        base = item.getProp("a_sale_unit")
    if not base:
        base = item.getProp("a_sale_cap")
    if not base or not this.showItemSellMod or _global.__moActive():
        return
    n = 1
    if this.showHeapCount and item.getProp("size"):
        n = item.getProp("size")
    value = Math.max(1, Math.floor(base * n * _global.__gcSaleQuality(item)))
    this.price_mc._visible = True
    this.price_mc.gotoAndStop(1)
    this.mainCost = value
    this.costType = "Афро"
    if not this.attachIconEnabled:
        value = "a" + String(value)
    this.price_mc.fontContainer.showValue(value)

def __gcAddSell(annotationArr):
    if this.item.getProp("bp_sell") or this.item.getProp("g_sale_unit") > 0:
        annotationArr.push(["Допустимость продажи", "Да"])
        return
    this.__gcAddSellOrig(annotationArr)

def __gcCheckSell(item):
    if not _global.__moActive() and item.getProp("bp_sell"):
        return
    if not _global.__moActive() and item.getProp("g_sale_unit") > 0:
        if (item.rootID == 0 or item.rootID == 1 or item.rootID == 5) and item.getProp("__break") == 0:
            return "Вы не можете продать полностью сломанный предмет"
        if item.rootID == 6:
            return "Вы не можете продать трофеи"
        return
    return this.__gcCheckSellOrig(item)

def __gcExchange(item, title, mode, showGold, selling):
    pan = this.__gcExchangeOrig(item, title, mode, showGold, selling)
    unit = item.getProp("g_sale_unit")
    if not unit:
        unit = item.getProp("a_sale_unit")
    if not unit:
        unit = item.getProp("a_sale_cap")
    if selling and not _global.__moActive() and unit > 0:
        pan.cost_num = unit
        pan.cost_mod = _global.__gcSaleQuality(item)
        pan.showCostInGold = False
    return pan

def __gcAuctionCheck():
    item = this.currDDOperation.fromItem
    transfer = item.getProp("g_transfer")
    if transfer == None:
        return this.__gcAuctionCheckOrig()
    if not transfer:
        this.createAlert("Этот предмет нельзя передавать")
        return False
    if item.getProp("max_break_cur") > 0 and _global.__gcQuality(item) < 15 / 100:
        this.createAlert("Нельзя выложить предмет поломанный более чем на 85%")
        return False
    if not item.getProp("g_auction_base"):
        this.createAlert("У предмета нет цены для комиссии аукциона")
        return False
    return True

def __gcCommission():
    item = this.lotSlot.item
    if not item or not item.getProp("g_sale_unit") or not (this.rateA_txt.text or this.buyoutA_txt.text):
        return this.__gcCommissionOrig()
    n = item.getProp("size")
    if not n:
        n = 1
    rate = 5 / 100
    if this.curTime_btn == this.time24_btn:
        rate = 7 / 100
    if this.curTime_btn == this.time48_btn:
        rate = 9 / 100
    fee = Math.ceil(item.getProp("g_auction_base") * rate * n)
    this.info_txt.htmlText = "\\rКомиссия: " + String(fee) + " А"
    this.info_txt.setTextFormat(this.tf)

def __gcSell(item, quantity):
    if not item.getProp("g_sale_unit") or _global.__moActive():
        return this.__gcSellOrig(item, quantity)
    if this.__gcPending:
        this.applyTransfer(False)
        return
    n = quantity
    if not n:
        n = item.getProp("size")
    if not n:
        n = 1
    this.__gcPending = {"item": item, "n": n}
    message = new(lol.server.mess.CSM_SSUpdate, 2, new(lol.data.BigUINT, new(lol.data.BigUINTCluster, item.id)), n)
    message.addProp("sale_stage", "@quote@")
    if this.XMC.Send(message):
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.__gcQuote)
    else:
        this.__gcPending = None
        this.applyTransfer(False)

def __gcQuote(obj):
    pending = this.__gcPending
    if not pending:
        return
    if obj.param.res != 0 or lol.core.SceneShifter._ref.UIPanels.query.instance:
        this.__gcPending = None
        this.applyTransfer(False)
        return
    pending.token = obj.param.token
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if not pan or pan.trade != this:
        this.__gcPending = None
        this.applyTransfer(False)
        return
    dialog = lol.core.SceneShifter.openNewWindow("query").content
    this.__gcDialog = dialog
    dialog.label = "Продать «" + pending.item.itemName + "» за " + String(obj.param.price) + " афро? Количество: " + String(obj.param.count) + ". Введите ПРОДАТЬ для подтверждения.\\r\\r\\r"
    y = dialog.alert_txt._y + dialog.alert_txt._height - 34
    dialog.createTextField("__gcInput", dialog.getNextHighestDepth(), dialog.alert_txt._x, y, dialog.alert_txt._width, 22)
    field = dialog.__gcInput
    field.type = "input"
    field.border = True
    field.borderColor = 7368298
    field.background = True
    field.backgroundColor = 2236962
    field.textColor = 13616814
    field.maxChars = 7
    field.embedFonts = False
    format = new(TextFormat, "Tahoma", 12)
    field.setNewTextFormat(format)
    field.text = ""
    Selection.setFocus(field)
    dialog.addEventListener("click", this, this.__gcAnswer)

def __gcAnswer(event):
    pending = this.__gcPending
    dialog = this.__gcDialog
    if not dialog or event.target != dialog:
        return
    dialog.removeEventListener("click", this, this.__gcAnswer)
    text = dialog.__gcInput.text
    this.__gcDialog = None
    this.__gcPending = None
    lol.core.SceneShifter.closeWindow("query")
    if not pending:
        return
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if not event.success or text != "ПРОДАТЬ" or not pan or pan.trade != this:
        this.applyTransfer(False)
        return
    message = new(lol.server.mess.CSM_SSUpdate, 2, new(lol.data.BigUINT, new(lol.data.BigUINTCluster, pending.item.id)), pending.n)
    message.addProp("sale_token", "@" + pending.token + "@")
    message.addProp("confirmation", "@ПРОДАТЬ@")
    if this.XMC.Send(message):
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.transferAck)
    else:
        this.applyTransfer(False)

def __gcRequestTransfer(transfer):
    if this.__gcBusy:
        return
    this.__gcBusy = True
    return this.__gcRequestOrig(transfer)

def __gcApplyTransfer(success):
    this.__gcApplyOrig(success)
    this.__gcBusy = False
    if not this.__gcDead and len(this.transferStack) > 0:
        this.requestTranfer(this.transferStack[0])

def __gcKill():
    this.__gcDead = True
    if this.__gcDialog:
        this.__gcDialog.removeEventListener("click", this, this.__gcAnswer)
        lol.core.SceneShifter.closeWindow("query")
    this.__gcDialog = None
    this.__gcPending = None
    return this.__gcKillOrig()

def __gcMoveError():
    if this.currDDOperation:
        return this.__gcMoveErrorOrig()
    operation = this.ddOperation_arr.shift()
    if operation:
        operation.failedOperation()
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'objects', 'Item'), 'initialize', '__gcInitializeOrig', '__gcInitialize'),
        (('core', 'objects', 'Item'), 'getProp', '__gcGetPropOrig', '__gcGetProp'),
        (('gpui', 'Annotation'), 'addSell', '__gcAddSellOrig', '__gcAddSell'),
        (('gpui', 'ItemContainer'), 'showCost', '__gcShowCostOrig', '__gcShowCost'),
        (('gpui', 'TradeInterface'), 'checkSellItem', '__gcCheckSellOrig', '__gcCheckSell'),
        (('gpui', 'TradeInterface'), 'createExchangePan', '__gcExchangeOrig', '__gcExchange'),
        (('gpui', 'AuctionMyLotsInterface'), 'checkDragItem', '__gcAuctionCheckOrig', '__gcAuctionCheck'),
        (('gpui', 'AuctionMyLotsInterface'), 'checkComission', '__gcCommissionOrig', '__gcCommission'),
        (('core', 'player', 'Trade'), 'sell', '__gcSellOrig', '__gcSell'),
        (('core', 'player', 'Trade'), 'requestTranfer', '__gcRequestOrig', '__gcRequestTransfer'),
        (('core', 'player', 'Trade'), 'applyTransfer', '__gcApplyOrig', '__gcApplyTransfer'),
        (('core', 'player', 'Trade'), 'kill', '__gcKillOrig', '__gcKill'),
        (('gpui', 'TradeInterface'), 'moveItemError', '__gcMoveErrorOrig', '__gcMoveError'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    # Quote and dialog callbacks are new prototype methods, installed via
    # the normal wrapper mechanism (their original methods are unused).
    for name in ('__gcQuote', '__gcAnswer'):
        params, body = bodies[name]
        wraps.append((('core', 'player', 'Trade'), name, name + 'Orig', params, body))
    return dict(globals=[(name, params, body) for name, params, body in functions
                         if name in ('__gcQuality', '__gcSaleQuality')], wraps=tuple(wraps))
