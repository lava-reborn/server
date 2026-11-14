"""Opt-in native Flash Shift routes; uses an isolated local server/account.

Production handlers and native DDOperation/selection run against minimal UI
stand-ins; equipment submission is recorded instead of sending commands.
This is not a physical keyboard, raster QA or FPS measurement.
"""
import os
import json

import test_location_transition as host
import widescreen as w
from avm_codegen import Compiler
from testkit import check, fails


SOURCE = '''
def __inventoryProbe(url):
    _root.tick = _root.tick + 1
    report = new(LoadVars)
    report.tick = _root.tick
    if _root.tick == 6:
        _root.nativeHits = 0
        _root.destination = "missing"
        _root.weapon = {"__proto__":lol.core.objects.FireArm.prototype, "rootID":0, "inited":True, "getProp":_global.__probeProp}
        bag = {"id":"bag", "clearSelectList":_global.__probeNoop}
        primary = {"id":"primary", "item_mc":{}}
        owner = {"__proto__":lol.gpui.EquipInterface.prototype, "bag_mc":bag, "outfitInterface":{"prim_mc":primary}, "ddOperation_arr":[], "sendTransferToServer":_global.__probeSubmit}
        owner.__proto__ = lol.gpui.EquipInterface.prototype
        _root.weapon.__proto__ = lol.core.objects.FireArm.prototype
        bag.__icOwner = owner
        # Native compiled methods call the explicit AS2 accessor, whereas
        # generated wrappers read .item. The stand-in must expose both.
        card = {"item":_root.weapon, "__get__item":_global.__probeGetItem, "__icBag":bag, "blockItem":_global.__probeNoop}
        card.clickFlag = True
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.hits = _root.nativeHits
        report.destination = _root.destination
        report.shift_cleared_click = not card.clickFlag
        # Exercise the native type constants and original clothing/medicine
        # branches, not just a stand-in handler with copied numeric roots.
        card.unblockItem = _global.__probeNoop
        owner.currDDOperation = None
        owner.outfitInterface.head_mc = {"id":"head", "item_mc":{"item":{}, "blockItem":_global.__probeNoop}}
        card.item = new(lol.core.objects.Wear, "0", 0, lol.core.objects.Item.WEAR)
        card.item.inited = True
        card.item.getProp = _global.__probeProp
        report.armour_class = card.item.__className
        report.armour_root = card.item.rootID
        _root.destination = "missing"
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.armour_destination = _root.destination
        owner.currDDOperation = None
        _root.healUses = 0
        owner.equipment = {"onDoubleClick":_global.__probeUseMedicine}
        card.item = new(lol.core.objects.HealItem, "0", 0, lol.core.objects.Item.HEAL_ITEM)
        card.item.inited = True
        card.item.getProp = _global.__probeProp
        report.medicine_class = card.item.__className
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.medicine_uses = _root.healUses
        report.medicine_pending = Boolean(owner.currDDOperation)
        owner.currDDOperation = None
        card.item = new(lol.core.objects.MeleeWeapon, "0", 0, lol.core.objects.Item.COLD_ARM)
        card.item.inited = True
        card.item.getProp = _global.__probeProp
        _root.destination = "missing"
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.knife_destination = _root.destination
        owner.currDDOperation = None
        card.item = new(lol.core.objects.Ammo, "0", 0, lol.core.objects.Item.AMMO)
        card.item.inited = True
        card.item.getProp = _global.__probeProp
        _root.destination = "missing"
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.ammo_destination = _root.destination
        # Exercise the real SlotPan.addItem -> ItemContainer release ->
        # EquipInterface -> DDOperation chain, including repeat clicks while
        # awaiting the server and detachment when the slot card is removed.
        savedKey = Key.isDown
        # Key.isDown is read-only in the projector. Replace it only in this
        # isolated probe, restoring the real function before other checks.
        ASSetPropFlags(Key, "isDown", 0, 7)
        Key.isDown = _global.__probeShiftDown
        report.unequip_slots = 0
        report.unequip_single = True
        report.unequip_detached = True
        names = ["prim_mc", "sec_mc", "head_mc", "armor_mc", "cam_mc", "legs_mc", "boots_mc", "belt_mc"]
        ids = ["primary", "secondary", "head", "armor", "camouflage", "legs", "boots", "belt"]
        i = 0
        while i < len(names):
            owner.currDDOperation = None
            slot = {"__proto__":lol.gpui.SlotPan.prototype, "id":ids[i], "typeOfList":"icon", "cont_mc":{"attachMovie":_global.__probeAttachSlot}, "dispatchEvent":_global.__probeNoop}
            slot.__proto__ = lol.gpui.SlotPan.prototype
            owner.outfitInterface[names[i]] = slot
            _global.__icBindEquipSlots(owner, True)
            _root.slotCard = {"__get__item":_global.__probeSlotGetItem, "__set__item":_global.__probeSetItem, "blockItem":_global.__probeBlock, "unblockItem":_global.__probeUnblock, "attachIcon":_global.__probeNoop, "kill":_global.__probeNoop, "removeMovieClip":_global.__probeNoop, "reload_btn":{}, "price_mc":{}}
            _root.slotCard.__proto__ = lol.gpui.ItemContainer.prototype
            lol.events.LEventDispatcher.initialize(_root.slotCard)
            if i == 0:
                item = new(lol.core.objects.FireArm, "0", 0, lol.core.objects.Item.FIRE_ARM)
            elif i == 1:
                item = new(lol.core.objects.MeleeWeapon, "0", 0, lol.core.objects.Item.COLD_ARM)
            else:
                item = new(lol.core.objects.Wear, "0", 0, lol.core.objects.Item.WEAR)
            item.inited = True
            item.getProp = _global.__probePremium
            slot.addItem(item)
            hits = _root.nativeHits
            if i == 0:
                report.unequip_binding = slot.__icEquipOwner == owner and _root.slotCard.__icSlot == slot
                report.unequip_card = slot.item_mc == _root.slotCard
                report.unequip_shift = Key.isDown(16)
                report.unequip_item = _root.slotCard.item == item
            lol.gpui.ItemContainer.prototype.onPressBg.apply(_root.slotCard, [])
            lol.gpui.ItemContainer.prototype.onReleaseBg.apply(_root.slotCard, [])
            if i == 0:
                report.unequip_hits = _root.nativeHits
                report.unequip_target = _root.destination
                report.unequip_blocked = Boolean(_root.slotCard.blockFlag)
            if _root.nativeHits == hits + 1 and _root.destination == "bag" and owner.currDDOperation.fromSlot == slot and owner.currDDOperation.fromItem == item and not _root.slotCard.clickFlag and not _root.slotCard.onMouseMove:
                report.unequip_slots = Number(report.unequip_slots) + 1
            lol.gpui.ItemContainer.prototype.onReleaseBg.apply(_root.slotCard, [])
            if _root.nativeHits != hits + 1:
                report.unequip_single = False
            slot.removeItem()
            if _root.slotCard.__icSlot:
                report.unequip_detached = False
            i = i + 1
        _global.__icBindEquipSlots(owner, False)
        report.unequip_released = not slot.__icEquipOwner
        Key.isDown = savedKey
        # Exercise the actual native getNumFromSortList/selection path when
        # the old anchor was removed or hidden by a filter.
        stale = {"currSelectItem":{"item":{"id":"gone"}}, "sortList":[card], "selectItem_arr":[], "clearSelectList":_global.__probeNoop, "getNumFromSortList":lol.gpui.BagInterface.prototype.getNumFromSortList, "select":lol.gpui.BagInterface.prototype.select}
        lol.gpui.BagInterface.prototype.itemPressShift.apply(stale, [card])
        report.selected_current = stale.currSelectItem == card
        keys = {"__proto__":lol.services.HotKeyManager.prototype, "hotKeyFilters":new(lol.services.HotKeyFilter), "__icEscape":{"filter":"inventoryTrade", "event":lol.services.HotKeyEvent.CANCEL, "handled":False}}
        lol.events.LEventDispatcher.initialize(keys)
        _root.tradeEscapes = 0
        _root.otherEscapes = 0
        keys.addEventListener("__icTradeEscape", _root, _global.__probeTradeEscape)
        keys.addEventListener(lol.services.HotKeyEvent.CANCEL, _root, _global.__probeOtherEscape)
        keys.checkAndDispatch(lol.services.HotKeyEvent.CANCEL)
        keys.checkAndDispatch(lol.services.HotKeyEvent.ESC)
        report.trade_escape = _root.tradeEscapes
        report.other_escape = _root.otherEscapes
        stats = keys.hotKeyFilters.getFilter("persInfo")
        report.stats_cancel = _global.__probeContains(stats, lol.services.HotKeyEvent.CANCEL)
        report.stats_toggle = _global.__probeContains(stats, lol.services.HotKeyEvent.PERS_INFO)
    report.sendAndLoad(url, report, "POST")

def __probeProp(name):
    return 0

def __probeNoop():
    return

def __probeGetItem():
    return this.item

def __probeSetItem(item):
    this.__item = item

def __probeSlotGetItem():
    return this.__item

def __probeAttachSlot(linkage, name, depth):
    return _root.slotCard

def __probeShiftDown(code):
    return code == 16

def __probeBlock():
    this.blockFlag = True

def __probeUnblock():
    this.blockFlag = False

def __probePremium(name):
    if name == "premium":
        return 2
    return 0

def __probeUseMedicine(item, slot):
    _root.healUses = _root.healUses + 1

def __probeSubmit():
    _root.nativeHits = _root.nativeHits + 1
    _root.destination = this.currDDOperation.toSlot.id

def __probeTradeEscape(event):
    _root.tradeEscapes = _root.tradeEscapes + 1

def __probeOtherEscape(event):
    _root.otherEscapes = _root.otherEscapes + 1

def __probeContains(values, item):
    i = 0
    while i < len(values):
        if values[i] == item:
            return True
        i = i + 1
    return False
'''


def probe(url):
    a = w.Asm()
    functions = Compiler(w.Asm, w.UNDEF).functions(SOURCE)
    for name, args, body in functions:
        a.var('_global').push(name).function(args, body).op('setmember')
    a.push(url, 1, '__inventoryProbe').op('callfunc').op('pop')
    return a


def main():
    if not host.PLAYER or os.name != 'nt':
        print('SKIP: set LAVA_FLASH_PLAYER and LAVA_RES on Windows')
        return
    host.probe = probe
    host.resize = lambda *args: None
    host.RESIZE_AT, host.LAST = 999, 9
    rows = host.run(True)
    row = next((r for r in rows if r.get('tick') == '6'), {})
    check('native Shift selection submits one equipment operation', row.get('hits'), '1')
    check('native weapon equip selects the primary slot', row.get('destination'), 'primary')
    check('native Shift consumes the double-click flag', row.get('shift_cleared_click'), 'true')
    check('native Shift armour selects its clothing slot', row.get('armour_destination'), 'head')
    check('native Shift medicine uses once and leaves no pending equipment operation',
          (row.get('medicine_uses'), row.get('medicine_pending')), ('1', 'false'))
    check('native Shift knife selects the primary slot', row.get('knife_destination'), 'primary')
    check('native Shift ammunition selects the weapon target', row.get('ammo_destination'), 'primary')
    check('native Shift unequips all eight slots through normal transfer, even without premium',
          row.get('unequip_slots'), '8')
    check('native Shift repeat cannot submit an extra unequip before ACK', row.get('unequip_single'), 'true')
    check('native slot removal detaches the retired card', row.get('unequip_detached'), 'true')
    check('native equipment cleanup releases slot ownership', row.get('unequip_released'), 'true')
    check('native filtered-out range anchor selects the current card safely', row.get('selected_current'), 'true')
    check('native trade Escape reaches only its own recipient',
          (row.get('trade_escape'), row.get('other_escape')), ('1', '0'))
    check('native complete filter chain preserves stats cancellation and toggle',
          (row.get('stats_cancel'), row.get('stats_toggle')), ('true', 'true'))
    if fails:
        print(json.dumps(row,sort_keys=True))
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
