"""Bank quantities, modal select-all and authoritative compact stack updates."""
from avm_codegen import Compiler

SOURCE = '''
def __bkPersReady(obj):
    obj.target.removeEventListener("itemUpdate", this)
    this.__bkPersReadyOrig(obj)

def __bkPersStatus(obj):
    if obj.param.status == 0:
        item = lol.core.objects.ItemFactory.getItem(obj.param.obj)
        if item:
            item.removeEventListener("itemUpdate", this)
    this.__bkPersStatusOrig(obj)

def __bkInit():
    this.__bkInitOrig()
    this.bag_mc.__bkOwner = this
    this.visavisBag_mc.__bkOwner = this

def __bkShift(obj):
    if this.__bkOwner:
        obj.target.clickFlag = False
        this.__bkOwner.doubleClick({"target":this, "item_mc":obj.target})
        return
    this.__bkShiftOrig(obj)

def __bkDouble(obj):
    if this.currDDOperation or len(this.ddOperation_arr) > 0 or this.bank.__bkPending:
        return
    if not this.ddOperation_arr:
        this.ddOperation_arr = []
    mc = obj.item_mc
    if not mc or not mc.item:
        return
    op = new(lol.gpui.DDOperation)
    op.setFrom(mc.item, obj.target, mc)
    if obj.target == this.bag_mc:
        op.setTo(0, this.visavisBag_mc)
    else:
        op.setTo(0, this.bag_mc)
    this.currDDOperation = op
    if mc.item.heapSize > 1:
        title = "Сколько штук взять?"
        if obj.target == this.bag_mc:
            title = "Сколько штук положить?"
        pan = this.createExchangePan(mc.item, title)
        pan.addEventListener("exchange", this, this.exchangeDropAck)
        pan.addEventListener("close", this, this.exchangeCancel)
    else:
        this.sendTransferToServer()

def __bkExchange(item, title):
    pan = this.__bkExchangeOrig(item, title)
    pan.__bkQuantity = True
    return pan

def __bkExchangeAck(obj):
    obj.target.removeEventListener("close", this, this.exchangeCancel)
    obj.target.removeEventListener("exchange", this, this.exchangeDropAck)
    this.currDDOperation.__bkCount = Number(obj.right)
    lol.core.SceneShifter.closeWindow("exchange")
    this.sendTransferToServer()

def __bkCancel(obj):
    obj.target.removeEventListener("close", this, this.exchangeCancel)
    obj.target.removeEventListener("exchange", this, this.exchangeDropAck)
    lol.core.SceneShifter.closeWindow("exchange")
    if this.currDDOperation:
        this.currDDOperation.failedOperation()
    this.currDDOperation = None
    this.dropEnabled = True

def __bkSendTransfer():
    op = this.currDDOperation
    if not op:
        return
    group = op.fromItemMc_arr
    if len(group) > 1:
        i = 0
        while i < len(group):
            part = new(lol.gpui.DDOperation)
            part.setFrom(group[i].item, op.fromSlot, group[i])
            part.setTo(0, op.toSlot)
            this.ddOperation_arr.push(part)
            this.bank.transferItem(part.fromItem, part.fromSlot.id, part.toSlot.id)
            i = i + 1
    else:
        count = op.__bkCount
        if not count:
            count = op.fromItem.heapSize
        if not count:
            count = 1
        this.ddOperation_arr.push(op)
        this.bank.transferItem(op.fromItem, op.fromSlot.id, op.toSlot.id, op.toItem, count)
    this.currDDOperation = None
    this.dropEnabled = True

def __bkMouseUp():
    if not this.ddFlag:
        return
    this.ddFlag = False
    this.dragItemMc.kill()
    this.dragItemMc.removeMovieClip()
    op = this.currDDOperation
    if not op.toSlot or op.toSlot == op.fromSlot:
        op.failedOperation()
        this.currDDOperation = None
    else:
        if not op.group and op.fromItem.heapSize > 1:
            title = "Сколько штук взять?"
            if op.fromSlot == this.bag_mc:
                title = "Сколько штук положить?"
            pan = this.createExchangePan(op.fromItem, title)
            pan.addEventListener("exchange", this, this.exchangeDropAck)
            pan.addEventListener("close", this, this.exchangeCancel)
        else:
            this.sendTransferToServer()
    this.onMouseMove = None

def __bkRequest(op):
    if this.__bkPending:
        return
    if op["from"] == op.to or not op.to:
        this.applyTransfer(False)
        return
    code = 1
    if op.to == this.bag:
        code = 2
    count = op.heapNum
    expected = op.item.heapSize
    if not expected:
        expected = 1
    if not count:
        count = expected
    if not _global.__bkRequestID:
        _global.__bkRequestID = 0
    _global.__bkRequestID = _global.__bkRequestID + 1
    message = new(lol.server.mess.CSM_SSUpdate, code, new(lol.data.BigUINT, new(lol.data.BigUINTCluster, op.item.id)))
    message.addProp("bank_count", count)
    message.addProp("bank_expected", expected)
    message.addProp("bank_request", _global.__bkRequestID)
    if this.XMC.Send(message):
        this.__bkPending = True
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.transferAck)
    else:
        this.applyTransfer(False)

def __bkApply(success):
    this.__bkPending = False
    this.transferStack.shift()
    event = lol.gpui.DDEvents.TRANSFER_ERROR
    if success:
        event = lol.gpui.DDEvents.TRANSFER_SUCCESS
    this.dispatchEvent({"type":event})
    if len(this.transferStack) > 0:
        this.requestTranfer(this.transferStack[0])

def __bkDelta(obj):
    if obj.param.s_status != 7:
        this.__bkDeltaOrig(obj)
        return
    entries = String(obj.param.bank_delta).split(",")
    i = 0
    while i < len(entries):
        parts = entries[i].split(":")
        if len(parts) == 2:
            item = this.visavisBag.getItem(parts[0])
            if Number(parts[1]) == 0:
                if item:
                    this.removeItem(this.visavisBag, item)
            else:
                if not item:
                    item = this.createItem(parts[0])
                    this.addItem(this.visavisBag, item)
                if item and (item.rootID == 3 or item.rootID == 4) and item.heapSize != Number(parts[1]):
                    item.updateProperties({"size":Number(parts[1])})
        i = i + 1

def __bkQuantityInit():
    this.__bkQuantityInitOrig()
    if not this.__bkQuantity:
        return
    this.__bkSubmitted = False
    lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.KEY_PRESS, this, _global.__bkSelectAll)
    # Use native text rendering, like the heading: rasterizing the caption
    # through BitmapData loses its text anti-aliasing and looks pixelated.
    width = Math.ceil(this.label_txt._width)
    height = Math.ceil(this.label_txt._height)
    hint = this.createEmptyMovieClip("__bkHint", this.getNextHighestDepth())
    hint._x = this.label_txt._x
    hint._y = this.apply_btn._y - 23
    hint.createTextField("caption", 0, 0, 0, width, height)
    field = hint.caption
    field.selectable = False
    field.autoSize = "none"
    field.multiline = False
    field.wordWrap = False
    field.embedFonts = this.label_txt.embedFonts
    field.antiAliasType = this.label_txt.antiAliasType
    field.gridFitType = this.label_txt.gridFitType
    field.sharpness = this.label_txt.sharpness
    field.thickness = this.label_txt.thickness
    field.filters = this.label_txt.filters
    format = this.label_txt.getTextFormat()
    format.align = "center"
    field.setNewTextFormat(format)
    field.text = "Выбрать всё [F]"
    field.setTextFormat(format)
    field.textColor = this.label_txt.textColor

def __bkSelectAll(obj):
    if not this.__bkQuantity or this.__bkSubmitted or not lol.core.SceneShifter.hotKeyManager.checkFilter("dialogue"):
        return
    if obj.code == 70:
        if Number(this.right_txt.text) != this.maxValue:
            this.right_txt.text = this.maxValue
            this.changedRight()
    elif obj.code == 69:
        this.__bkSubmitted = True
        this.sendObj()

def __bkQuantityKill():
    if this.__bkQuantity:
        lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.KEY_PRESS, this, _global.__bkSelectAll)
        if this.__bkHint:
            this.__bkHint.removeMovieClip()
        this.__bkQuantity = False
    this.__bkQuantityKillOrig()
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'player', 'PersEquip'), 'itemUpdate', '__bkPersReadyOrig', '__bkPersReady'),
        (('core', 'player', 'PersEquip'), 'ss_obj_status', '__bkPersStatusOrig', '__bkPersStatus'),
        (('gpui', 'BankInterface'), 'init', '__bkInitOrig', '__bkInit'),
        (('gpui', 'BagInterface'), 'shiftSelect', '__bkShiftOrig', '__bkShift'),
        (('gpui', 'BankInterface'), 'onMouseUp', '__bkMouseUpOrig', '__bkMouseUp'),
        (('gpui', 'BankInterface'), 'doubleClick', '__bkDoubleOrig', '__bkDouble'),
        (('gpui', 'BankInterface'), 'createExchangePan', '__bkExchangeOrig', '__bkExchange'),
        (('gpui', 'BankInterface'), 'exchangeDropAck', '__bkExchangeAckOrig', '__bkExchangeAck'),
        (('gpui', 'BankInterface'), 'exchangeCancel', '__bkCancelOrig', '__bkCancel'),
        (('gpui', 'BankInterface'), 'sendTransferToServer', '__bkSendTransferOrig', '__bkSendTransfer'),
        (('core', 'player', 'Bank'), 'requestTranfer', '__bkRequestOrig', '__bkRequest'),
        (('core', 'player', 'Bank'), 'checkUse', '__bkCheckUseOrig', '__bkNoMerge'),
        (('core', 'player', 'Bank'), 'applyTransfer', '__bkApplyOrig', '__bkApply'),
        (('core', 'player', 'Bank'), 'ss_upd', '__bkDeltaOrig', '__bkDelta'),
        (('gpui', 'ExchangePan'), 'init', '__bkQuantityInitOrig', '__bkQuantityInit'),
        (('gpui', 'ExchangePan'), 'kill', '__bkQuantityKillOrig', '__bkQuantityKill'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))


# Merging happens only on the server, never by drag-and-drop prediction.
SOURCE += '''
def __bkNoMerge(op):
    return False
'''
