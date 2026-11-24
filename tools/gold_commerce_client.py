"""G commerce confirmation; purchase and repair prices stay native."""
from avm_codegen import Compiler

SOURCE = '''
def __esActive():
    panel = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    return not not (panel and panel.trader and panel.trader.eden_shop)

def __esNominal(item):
    return _global.__esActive() and item and (item.rootID == 0 or item.rootID == 1 or item.rootID == 5)

def __esTraderInfo(obj):
    this.__esTraderInfoOrig(obj)
    this.eden_shop = obj.param.eden_shop == 1
    this.base_gold_buyer = obj.param.base_gold_buyer == 1

def __gcBaseLoot(item):
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    return not not (pan and pan.trader and pan.trader.base_gold_buyer and item and item.getProp("base_loot_gold") > 0)

def __gcInitialize(obj):
    this.__gcInitializeOrig(obj)
    this.g_restore_base = obj.g_restore_base
    this.a_sale_unit = obj.a_sale_unit
    this.g_sale_unit = obj.g_sale_unit
    this.a_base_sale_unit = obj.a_base_sale_unit
    this.g_base_sale_unit = obj.g_base_sale_unit
    this.base_loot_gold = obj.base_loot_gold
    this.bp_sell = obj.bp_sell
    this.a_sale_cap = obj.a_sale_cap
    this.g_transfer = obj.g_transfer
    this.g_auction_base = obj.g_auction_base
    this.eden_sale_unit = obj.eden_sale_unit
    this.eden_sale_gold = obj.eden_sale_gold

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

def __gcSaleUnit(item):
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if pan and pan.trader and pan.trader.smod == 85 / 100:
        unit = item.getProp("g_base_sale_unit")
        if not unit:
            unit = item.getProp("a_base_sale_unit")
    else:
        unit = item.getProp("g_sale_unit")
        if not unit:
            unit = item.getProp("a_sale_unit")
    cap = item.getProp("a_sale_cap")
    if cap and unit:
        return Math.min(cap, unit)
    if not unit:
        unit = cap
    return unit

def __gcBuyTotal(price, count, modifier, root, gold):
    if modifier > 0 and modifier < 1 and (root == 2 or root == 3):
        unit = Math.max(1, Math.min(Math.ceil(price * modifier), Math.ceil(price) - 1))
        return unit * count
    return Math.ceil(price * count * modifier)

def __gcBaseBuyPrice(item, count):
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if lol.gpui.StaffInterface.ssType != "trade" or not pan or not pan.trader:
        return
    if not item or item.tradeID == None or pan.trader.type_list[item.tradeID] != item.typeID:
        return
    if not (item.rootID == 2 or item.rootID == 3) or item.getProp("bg_p_cost"):
        return
    modifier = pan.trader.pmod
    if not (modifier > 0 and modifier < 1):
        return
    gold = item.getProp("g_cost") > 0
    price = item.getProp("cost")
    if gold:
        price = item.getProp("g_cost")
    if not (price > 0 and count > 0):
        return
    total = _global.__gcBuyTotal(price, count, modifier, item.rootID, gold)
    if gold:
        return String(total / 100) + " G"
    return String(total) + " Афро"

def __gcAddCost(rows):
    this.__gcAddCostOrig(rows)
    price = _global.__gcBaseBuyPrice(this.item, 1)
    if price == None:
        return
    rows.push(["Цена на клан базе:", price])

def __gcShowCost(item, align):
    this.__gcShowCostOrig(item, align)
    if lol.gpui.StaffInterface.ssType != "trade":
        return
    # Native gold cards ignore pmod, while A cards floor a purchase that
    # the server ceils. Quote the same whole purchase in both currencies.
    if not this.showItemSellMod and (item.rootID == 2 or item.rootID == 3) and this.cost_mod > 0 and this.cost_mod < 1:
        gold = this.showPriseInGold and item.getProp("g_cost") > 0
        price = item.getProp("cost")
        if gold:
            price = item.getProp("g_cost")
        if price > 0:
            n = 1
            if this.showHeapCount and item.getProp("size"):
                n = item.getProp("size")
            value = _global.__gcBuyTotal(price, n, this.cost_mod, item.rootID, gold)
            frame = 1
            prefix = "a"
            this.costType = "Афро"
            if gold:
                value = value / 100
                frame = 2
                prefix = "g"
                this.costType = "Золото"
            this.price_mc._visible = value > 0
            this.price_mc.gotoAndStop(frame)
            this.mainCost = value
            if not this.attachIconEnabled:
                value = prefix + String(value)
            this.price_mc.fontContainer.showValue(value)
            return
    if _global.__gcBaseLoot(item) and this.showItemSellMod:
        n = 1
        if this.showHeapCount and item.getProp("size"):
            n = item.getProp("size")
        value = item.getProp("base_loot_gold") * n / 100
        this.price_mc._visible = True
        this.price_mc.gotoAndStop(2)
        this.mainCost = value
        this.costType = "Золото"
        if not this.attachIconEnabled:
            value = "g" + String(value)
        this.price_mc.fontContainer.showValue(value)
        return
    if _global.__esNominal(item) and this.showItemSellMod:
        n = 1
        if this.showHeapCount and item.getProp("size"):
            n = item.getProp("size")
        value = Math.floor(item.getProp("eden_sale_unit") * n * _global.__gcSaleQuality(item))
        this.price_mc._visible = value > 0
        if value <= 0:
            return
        gold = item.getProp("eden_sale_gold")
        frame = 1
        this.costType = "Афро"
        prefix = "a"
        if gold:
            frame = 2
            value = value / 100
            this.costType = "Золото"
            prefix = "g"
        this.price_mc.gotoAndStop(frame)
        this.mainCost = value
        if not this.attachIconEnabled:
            value = prefix + String(value)
        this.price_mc.fontContainer.showValue(value)
        return
    base = _global.__gcSaleUnit(item)
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
    if _global.__gcBaseLoot(item):
        return
    if _global.__esNominal(item):
        if not item.getProp("eden_sale_unit") or _global.__gcSaleQuality(item) <= 0:
            return "Скупщик не принимает этот предмет"
        return
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
    if not selling and (item.rootID == 2 or item.rootID == 3) and mode > 0 and mode < 1:
        pan.__gcBuyRoot = item.rootID
        pan.__gcBuyGold = showGold and item.getProp("g_cost") > 0
        pan.countMoney()
        return pan
    if selling and _global.__gcBaseLoot(item):
        pan.cost_num = item.getProp("base_loot_gold")
        pan.cost_mod = 1
        pan.showCostInGold = True
        return pan
    if selling and _global.__esNominal(item):
        pan.cost_num = item.getProp("eden_sale_unit")
        pan.cost_mod = _global.__gcSaleQuality(item)
        pan.showCostInGold = not not item.getProp("eden_sale_gold")
        return pan
    unit = _global.__gcSaleUnit(item)
    if selling and not _global.__moActive() and unit > 0:
        pan.cost_num = unit
        pan.cost_mod = _global.__gcSaleQuality(item)
        pan.showCostInGold = False
    return pan

def __gcCountMoney():
    this.__gcCountMoneyOrig()
    if this.__gcBuyRoot == None or this.sell_bool:
        return
    n = this[this.mainSize]
    if not (n > 0):
        return
    total = _global.__gcBuyTotal(this.cost_num, n, this.cost_mod, this.__gcBuyRoot, this.__gcBuyGold)
    if this.showCostInGold:
        total = total / 100
    this.money_mc.info_txt.text = String(total)

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

def __gcAskSale():
    operation = this.currDDOperation
    if not operation or _global.__moActive() or operation.fromSlot != this.bag_mc or operation.toSlot != this.visavisBag_mc:
        return this.__gcAskSaleOrig()
    group = operation.fromItemMc_arr
    if not group or len(group) == 0:
        group = [{"item":operation.fromItem}]
    quoted = False
    i = 0
    while i < len(group):
        item = group[i].item
        if not item:
            return this.__gcAskSaleOrig()
        if _global.__esNominal(item) or item.getProp("g_sale_unit") or _global.__gcBaseLoot(item):
            quoted = True
        elif item.getProp("g_cost") > 0:
            # Retain the native protection for sales outside the quote flow.
            return this.__gcAskSaleOrig()
        i = i + 1
    if quoted:
        # Validation and the transfer queue still run; each G sale asks once
        # after its authoritative price quote arrives from the server.
        return this.tryToSendTransferToServer()
    return this.__gcAskSaleOrig()

def __gcSell(item, quantity):
    if (not item.getProp("g_sale_unit") and not _global.__esNominal(item) and not _global.__gcBaseLoot(item)) or _global.__moActive():
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
    price = obj.param.price
    currency = " афро"
    if obj.param.currency == 1:
        price = price / 100
        currency = " G"
    pending.edenAfro = obj.param.eden_sale == 1 and obj.param.currency == 0
    dialog.label = "Продать «" + pending.item.getProp("name") + "» за " + String(price) + currency + "? Количество: " + String(obj.param.count) + "."
    if not pending.edenAfro:
        dialog.label = dialog.label + " Введите ПРОДАТЬ для подтверждения."
        _global.__gcConfirmInput(dialog, 7)
    dialog.addEventListener("click", this, this.__gcAnswer)

def __gcAnswer(event):
    pending = this.__gcPending
    dialog = this.__gcDialog
    if not dialog or event.target != dialog:
        return
    dialog.removeEventListener("click", this, this.__gcAnswer)
    text = "ПРОДАТЬ"
    if not pending.edenAfro:
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


def __gcConfirmInput(dialog, length):
    # HTML whitespace is not reliable padding. Reserve real layout space
    # below the rendered text, then let the native frame tile itself again.
    contentHeight = Math.max(dialog.alert_txt._height, Math.ceil(dialog.alert_txt.textHeight) + 4)
    dialog.alert_txt.autoSize = False
    dialog.alert_txt._height = contentHeight + 44
    dialog.resize()
    y = dialog.alert_txt._y + contentHeight + 8
    dialog.createTextField("__gcInput", dialog.getNextHighestDepth(), dialog.alert_txt._x, y, dialog.alert_txt._width, 22)
    field = dialog.__gcInput
    field.type = "input"
    field.border = True
    field.borderColor = 7368298
    field.background = True
    field.backgroundColor = 2236962
    field.textColor = 13616814
    field.maxChars = length
    field.embedFonts = False
    format = new(TextFormat, "Tahoma", 12)
    field.setNewTextFormat(format)
    field.text = ""
    # Native query frames reserve a large empty footer. Keep the original
    # bottom artwork, but bring its buttons to 12px below the input.
    buttonsY = y + 22 + 12
    back = dialog.back_mc
    bottomY = back.bottom_mc._y + buttonsY - dialog.apply_btn._y
    bottomY = Math.max(bottomY, back.middle_mc._y + back.middle_mc._height)
    shift = bottomY - back.bottom_mc._y
    back.bottom_mc._y = bottomY
    dialog.apply_btn._y = dialog.apply_btn._y + shift
    dialog.cancel_btn._y = dialog.apply_btn._y
    i = 0
    while back["m" + String(i)]:
        tile = back["m" + String(i)]
        if tile._y >= bottomY:
            tile.removeMovieClip()
        elif tile._y + tile._height > bottomY:
            tile._height = bottomY - tile._y
        i = i + 1
    Selection.setFocus(field)

def __gcBuy(item, count):
    price = item.getProp("g_cost")
    points = item.getProp("bg_p_cost")
    if not price or price <= 0 or isNaN(price) or (points != None and not isNaN(points)):
        return this.__gcBuyOrig(item, count)
    if this.__gcBuyDialog or this.__gcBuyPending:
        return
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if this.__gcDead or not pan or pan.trade != this or lol.core.SceneShifter._ref.UIPanels.query.instance:
        this.applyTransfer(False)
        return
    if pan.trader.type_list[item.tradeID] != item.typeID or not item.getProp("name"):
        this.applyTransfer(False)
        return
    n = 1
    if item.rootID == 3 or (item.rootID == 2 and (item.getProp("max_count") or 1) > 1):
        n = count
        if n == None:
            n = item.getProp("size")
    if not n or n <= 0 or isNaN(n) or n != Math.floor(n):
        this.applyTransfer(False)
        return
    total = _global.__gcBuyTotal(price, n, pan.trader.pmod, item.rootID, True)
    if not total or total <= 0 or isNaN(total):
        this.applyTransfer(False)
        return
    # Ammo.g_cost is already rounded to the native price of one cartridge.
    # Freeze the exact item, quantity and shown price, not the selection.
    this.__gcBuyPending = {"item":item, "type":item.typeID, "index":item.tradeID, "price":price, "npc":this.visavisID, "n":n, "pmod":pan.trader.pmod}
    dialog = lol.core.SceneShifter.openNewWindow("query").content
    this.__gcBuyDialog = dialog
    dialog.label = "Купить «" + item.getProp("name") + "» за " + String(total / 100) + " G? Количество: " + String(n) + ". Введите КУПИТЬ для подтверждения."
    _global.__gcConfirmInput(dialog, 6)
    dialog.addEventListener("click", this, this.__gcBuyAnswer)

def __gcBuyAnswer(event):
    dialog = this.__gcBuyDialog
    if not dialog or event.target != dialog:
        return
    pending = this.__gcBuyPending
    dialog.removeEventListener("click", this, this.__gcBuyAnswer)
    text = dialog.__gcInput.text
    this.__gcBuyDialog = None
    this.__gcBuyPending = None
    lol.core.SceneShifter.closeWindow("query")
    if not pending or this.__gcDead:
        return
    pan = lol.core.SceneShifter._ref.UIPanels.trade.instance.content
    if not event.success or text != "КУПИТЬ" or not pan or pan.trade != this or this.visavisID != pending.npc or pan.trader.pmod != pending.pmod:
        this.applyTransfer(False)
        return
    item = pending.item
    if item.typeID != pending.type or item.tradeID != pending.index or item.getProp("g_cost") != pending.price or pan.trader.type_list[pending.index] != pending.type:
        this.applyTransfer(False)
        return
    # Native purchase preserves money, weight and stock rules and the ACK queue.
    return this.__gcBuyOrig(item, pending.n)

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
    if this.__gcBuyDialog:
        this.__gcBuyDialog.removeEventListener("click", this, this.__gcBuyAnswer)
        lol.core.SceneShifter.closeWindow("query")
    this.__gcBuyDialog = None
    this.__gcBuyPending = None
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
        (('core', 'player', 'Trader'), 'userInfo', '__esTraderInfoOrig', '__esTraderInfo'),
        (('core', 'objects', 'Item'), 'initialize', '__gcInitializeOrig', '__gcInitialize'),
        (('core', 'objects', 'Item'), 'getProp', '__gcGetPropOrig', '__gcGetProp'),
        (('gpui', 'Annotation'), 'addSell', '__gcAddSellOrig', '__gcAddSell'),
        (('gpui', 'Annotation'), 'addCost', '__gcAddCostOrig', '__gcAddCost'),
        (('gpui', 'ItemContainer'), 'showCost', '__gcShowCostOrig', '__gcShowCost'),
        (('gpui', 'TradeInterface'), 'askTradeItem', '__gcAskSaleOrig', '__gcAskSale'),
        (('gpui', 'TradeInterface'), 'checkSellItem', '__gcCheckSellOrig', '__gcCheckSell'),
        (('gpui', 'TradeInterface'), 'createExchangePan', '__gcExchangeOrig', '__gcExchange'),
        (('gpui', 'ExchangePan'), 'countMoney', '__gcCountMoneyOrig', '__gcCountMoney'),
        (('gpui', 'AuctionMyLotsInterface'), 'checkDragItem', '__gcAuctionCheckOrig', '__gcAuctionCheck'),
        (('gpui', 'AuctionMyLotsInterface'), 'checkComission', '__gcCommissionOrig', '__gcCommission'),
        (('core', 'player', 'Trade'), 'buy', '__gcBuyOrig', '__gcBuy'),
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
    for name in ('__gcQuote', '__gcAnswer', '__gcBuyAnswer'):
        params, body = bodies[name]
        wraps.append((('core', 'player', 'Trade'), name, name + 'Orig', params, body))
    return dict(globals=[(name, params, body) for name, params, body in functions
                         if name in ('__gcQuality', '__gcSaleQuality', '__gcSaleUnit', '__gcConfirmInput',
                                     '__esActive', '__esNominal', '__gcBaseLoot', '__gcBuyTotal',
                                     '__gcBaseBuyPrice')], wraps=tuple(wraps))
