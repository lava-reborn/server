"""Contextual Shift actions and one Escape recipient per key press.

Reuse the windows' transfer/confirmation pipelines, without sending packets or
changing item data here. Card bindings are installed at creation, not per frame.
"""
from avm_codegen import Compiler

SOURCE = '''
def __icModal():
    panels = lol.core.SceneShifter._ref.UIPanels
    return panels.exchange.instance or panels.query.instance or panels.queryTradeItem.instance or panels.queryDeleteItem.instance or panels.queryWithCheckBox.instance or panels.alert.instance

def __icCanStart(owner, card):
    if not owner or owner.__icDead or not card or not card.item or card.blockFlag or card.item.inited == False:
        return False
    if owner.ddFlag or owner.currDDOperation or (owner.ddOperation_arr and len(owner.ddOperation_arr) > 0) or _global.__icModal():
        return False
    if (owner.equipment.transferStack and len(owner.equipment.transferStack) > 0) or (owner.bank.transferStack and len(owner.bank.transferStack) > 0) or (owner.trade.transferStack and len(owner.trade.transferStack) > 0):
        return False
    return True

def __icAddItem(item, pos):
    this.__icAddItemOrig(item, pos)
    this.bagPan.content["item" + String(item.id)].__icBag = this

def __icRemoveItem(index):
    this.itemList[index].item_mc.__icBag = None
    return this.__icRemoveItemOrig(index)

def __icBagKill():
    this.__icDead = True
    this.__icOwner = None
    this.__bkOwner = None
    return this.__icBagKillOrig()

def __icRelease():
    bag = this.__icBag
    slot = this.__icSlot
    owner = slot.__icEquipOwner
    if Key.isDown(16) and (bag.__icOwner or bag.__bkOwner or bag.__icPassiveShift or (owner and slot.item_mc == this)):
        # The native release sends DOUBLE_CLICK before SHIFT_SELECT. A fast
        # Shift click must have exactly one route, including after a plain click.
        this.clickFlag = False
        if this.clickTimer:
            this.clickTimer.Clear()
        this.clickTimer = None
        this.onMouseMove = None
        this.price_mc.onMouseMove = None
        if owner and slot.item_mc == this:
            owner.doubleClick({"target":slot, "item_mc":this})
        else:
            this.dispatch({"type":lol.gpui.ItemContainer.SHIFT_SELECT})
        lol.gpui.AnnotationManager.clear()
        return
    return this.__icReleaseOrig()

def __icPress():
    bag = this.__icBag
    slot = this.__icSlot
    if Key.isDown(16) and (bag.__icOwner or bag.__bkOwner or bag.__icPassiveShift or (slot.__icEquipOwner and slot.item_mc == this)):
        this.onMouseMove = None
        return
    return this.__icPressOrig()

def __icShift(obj):
    if this.__icDead:
        return
    card = obj.target
    if this.__icOwner:
        card.clickFlag = False
        if card.__icBag == this and _global.__icCanStart(this.__icOwner, card):
            this.clearSelectList()
            this.__icOwner.doubleClick({"target":this, "item_mc":card})
        return
    if not this.__bkOwner and (not this.currSelectItem or not this.selectGroupAvailable):
        if card and card.item and not card.blockFlag:
            this.select(obj)
        return
    return this.__icShiftOrig(obj)

def __icRange(card):
    anchor = this.currSelectItem
    if not card or not card.item:
        return
    if not anchor or not anchor.item:
        this.select({"target":card})
        return
    start = this.getNumFromSortList(anchor.item.id)
    end = this.getNumFromSortList(card.item.id)
    if start == None or end == None:
        this.select({"target":card})
        return
    return this.__icRangeOrig(card)

def __icEquipInit():
    if this.__icDead:
        return
    this.__icDead = False
    this.__icEquipInitOrig()
    this.bag_mc.__icOwner = this
    _global.__icBindEquipSlots(this, True)

def __icEquipKill():
    this.__icDead = True
    this.bag_mc.__icOwner = None
    _global.__icBindEquipSlots(this, False)
    return this.__icEquipKillOrig()

def __icBindEquipSlots(owner, active):
    outfit = owner.outfitInterface
    slots = [outfit.prim_mc, outfit.sec_mc, outfit.head_mc, outfit.armor_mc, outfit.cam_mc, outfit.legs_mc, outfit.boots_mc, outfit.belt_mc]
    i = 0
    while i < len(slots):
        slot = slots[i]
        if slot:
            if active:
                slot.__icEquipOwner = owner
                slot.item_mc.__icSlot = slot
            else:
                slot.item_mc.__icSlot = None
                slot.__icEquipOwner = None
        i = i + 1

def __icSlotAdd(item):
    this.__icSlotAddOrig(item)
    if this.__icEquipOwner:
        this.item_mc.__icSlot = this

def __icSlotRemove():
    this.item_mc.__icSlot = None
    return this.__icSlotRemoveOrig()

def __icEquipSend():
    operation = this.currDDOperation
    this.__icEquipSendOrig()
    if operation and this.currDDOperation == operation and not lol.core.SceneShifter._ref.UIPanels.queryWithCheckBox.instance:
        # Native premium rejection unblocks the card but keeps this pointer.
        this.currDDOperation = None

def __icWarningAnswer(obj):
    operation = this.currDDOperation
    this.__icWarningAnswerOrig(obj)
    if not obj.success and this.currDDOperation == operation:
        this.currDDOperation = None

def __icEquipDouble(obj):
    card = obj.item_mc
    if not _global.__icCanStart(this, card):
        return
    root = card.item.rootID
    slot = None
    if obj.target.__icEquipOwner == this and obj.target.item_mc == card:
        # Removing equipment follows the same server-validated transfer as
        # dragging to the bag, including after a premium entitlement expires.
        slot = this.bag_mc
    elif obj.target == this.bag_mc and (root == 0 or root == 5 or root == 3):
        # The old double-click branch can leave hand items without a target.
        # Item.as: firearm=0, cold arm=5, ammo=3. Wear=1 keeps its
        # native clothing slot; medicine=2 keeps native use-on-double-click.
        # Use the same DDOperation and validation/confirmation path as a drop
        # on the primary hand; do not send a command or move the card here.
        slot = this.outfitInterface.prim_mc
    else:
        return this.__icEquipDoubleOrig(obj)
    if not slot:
        return
    if not this.ddOperation_arr:
        this.ddOperation_arr = []
    op = new(lol.gpui.DDOperation)
    op.setFrom(card.item, obj.target, card)
    if slot == this.bag_mc:
        op.setTo(None, slot)
    else:
        op.setTo(slot.item_mc.item, slot, slot.item_mc)
        if slot.item_mc:
            slot.item_mc.blockItem()
    this.currDDOperation = op
    this.sendTransferToServer()

def __icTradeInit():
    if this.__icDead:
        return
    this.__icDead = False
    this.__icTradeInitOrig()
    this.bag_mc.__icOwner = this
    this.visavisBag_mc.__icPassiveShift = True
    this.__icTradeKeys = True
    keys = lol.core.SceneShifter.hotKeyManager
    keys.addFilter("inventoryTrade")
    keys.addEventListener("__icTradeEscape", this, this.__icTradeEsc)

def __icTradeKill():
    this.__icDead = True
    this.bag_mc.__icOwner = None
    this.visavisBag_mc.__icPassiveShift = False
    this.methodTable = []
    this.__methodTable = []
    this.onEnterFrame = None
    if this.__icTradeKeys:
        keys = lol.core.SceneShifter.hotKeyManager
        keys.removeEventListener("__icTradeEscape", this, this.__icTradeEsc)
        keys.removeFilter("inventoryTrade")
        this.__icTradeKeys = False
    return this.__icTradeKillOrig()

def __icBankInit():
    if not this.__icDead:
        return this.__icBankInitOrig()

def __icBankKill():
    this.__icDead = True
    this.bag_mc.__bkOwner = None
    this.visavisBag_mc.__bkOwner = None
    this.methodTable = []
    this.__methodTable = []
    this.onEnterFrame = None
    return this.__icBankKillOrig()

def __icCancelDrag(owner):
    if not owner.ddFlag:
        return False
    owner.ddFlag = False
    owner.onMouseMove = None
    owner.dragItemMc.kill()
    owner.dragItemMc.removeMovieClip()
    owner.currDDOperation.failedOperation()
    owner.currDDOperation = None
    return True

def __icEscapeFor(name):
    keys = lol.core.SceneShifter.hotKeyManager
    if keys.__icEscape:
        return keys.__icEscape.filter == name
    return keys.checkFilter(name)

def __icEquipEsc():
    if not _global.__icEscapeFor("equipment") or _global.__icModal():
        return
    if not _global.__icCancelDrag(this):
        return this.__icEquipEscOrig()

def __icTradeEsc():
    if this.__icDead or not _global.__icEscapeFor("inventoryTrade") or _global.__icModal():
        return
    if this.trade.__gcBusy or (this.ddOperation_arr and len(this.ddOperation_arr) > 0):
        return
    if not _global.__icCancelDrag(this):
        this.close()

def __icFilter(name):
    if name == "inventoryTrade":
        return [lol.services.HotKeyEvent.CANCEL, lol.services.HotKeyEvent.CTRL, lol.services.HotKeyEvent.SHIFT]
    return this.__icFilterOrig(name)

def __icCheckKeys(suffix):
    if len(this.keyStack) != 1 or this.keyStack[0] != 27:
        return this.__icCheckKeysOrig(suffix)
    previous = this.__icEscape
    top = this.hotKeyFilter_arr[len(this.hotKeyFilter_arr) - 1]
    event = lol.services.HotKeyEvent.CANCEL
    if top == "equipment" or top == "location" or top == "chat" or top == "transport" or top == "auction":
        event = lol.services.HotKeyEvent.ESC
    this.__icEscape = {"filter":top, "event":event, "handled":False}
    this.__icCheckKeysOrig(suffix)
    this.__icEscape = previous

def __icDispatch(title):
    context = this.__icEscape
    if context and (title == lol.services.HotKeyEvent.CANCEL or title == lol.services.HotKeyEvent.ESC):
        if title != context.event or context.handled:
            return
        allowed = this.hotKeyFilters.getFilter(context.filter)
        i = 0
        while i < len(allowed):
            if allowed[i] == title:
                context.handled = True
                # Esc cancels even while a quantity/confirmation text field
                # has focus. It never dispatches APPLY or restores game focus.
                if context.filter == "inventoryTrade":
                    return this.dispatchEvent({"type":"__icTradeEscape"})
                return this.dispatchEvent({"type":title})
            i = i + 1
        return
    return this.__icDispatchOrig(title)
'''


def patches(Asm, undef):
    # Keep wrapper names distinct so the bank and G-confirmation wrappers
    # remain in the call chain, irrespective of their implementation details.
    source = SOURCE
    specs = [
        ('BagInterface', '__addItem', '__icAddItem'),
        ('BagInterface', '__removeItem', '__icRemoveItem'),
        ('BagInterface', 'kill', '__icBagKill'),
        ('ItemContainer', 'onReleaseBg', '__icRelease'),
        ('ItemContainer', 'onPressBg', '__icPress'),
        ('BagInterface', 'shiftSelect', '__icShift'),
        ('BagInterface', 'itemPressShift', '__icRange'),
        ('EquipInterface', 'init', '__icEquipInit'),
        ('EquipInterface', 'kill', '__icEquipKill'),
        ('EquipInterface', 'pressEscKey', '__icEquipEsc'),
        ('EquipInterface', 'doubleClick', '__icEquipDouble'),
        ('EquipInterface', 'sendTransferToServer', '__icEquipSend'),
        ('EquipInterface', 'warningAnswer', '__icWarningAnswer'),
        ('SlotPan', 'addItem', '__icSlotAdd'),
        ('SlotPan', 'removeItem', '__icSlotRemove'),
        ('TradeInterface', 'init', '__icTradeInit'),
        ('TradeInterface', 'kill', '__icTradeKill'),
        ('TradeInterface', '__icTradeEsc', '__icTradeEsc'),
        ('BankInterface', 'init', '__icBankInit'),
        ('BankInterface', 'kill', '__icBankKill'),
    ]
    for cls in ('EquipInterface', 'TradeInterface', 'BankInterface'):
        for method, card in (('doubleClick', 'obj.item_mc'),
                             ('startDragNDrop', 'obj.item_mc')):
            if cls == 'EquipInterface' and method == 'doubleClick':
                continue
            helper = '__ic' + cls + method
            source += f'''
def {helper}(obj):
    if _global.__icCanStart(this, {card}):
        return this.{helper}Orig(obj)
'''
            specs.append((cls, method, helper))
    for cls, method, filter_name in (
        ('CharInterface', 'cancel', 'persInfo'),
        ('QuestInterface', 'close', 'quest'),
        ('BankInterface', 'close', 'cancel'),
        ('SettingsInterface', 'close', 'settings'),
    ):
        helper = '__ic' + cls + 'Close'
        source += f'''
def {helper}():
    keys = lol.core.SceneShifter.hotKeyManager
    if keys.__icEscape and not _global.__icEscapeFor("{filter_name}"):
        return
'''
        if cls == 'BankInterface':
            source += '''    if keys.__icEscape and _global.__icCancelDrag(this):
        return
'''
        source += f'    return this.{helper}Orig()\n'
        specs.append((cls, method, helper))
    functions = Compiler(Asm, undef).functions(source)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = [(('gpui', cls), method, helper + 'Orig', *bodies[helper])
             for cls, method, helper in specs]
    for method, helper in (('checkHotKey', '__icCheckKeys'),
                           ('checkAndDispatch', '__icDispatch')):
        wraps.append((('services', 'HotKeyManager'), method, helper + 'Orig', *bodies[helper]))
    wraps.append((('services', 'HotKeyFilter'), 'getFilter', '__icFilterOrig', *bodies['__icFilter']))
    shared = {'__icModal', '__icCanStart', '__icCancelDrag', '__icEscapeFor', '__icBindEquipSlots'}
    return dict(globals=[entry for entry in functions if entry[0] in shared], wraps=tuple(wraps))
