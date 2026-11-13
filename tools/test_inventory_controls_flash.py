"""Opt-in native Flash Shift routes; uses an isolated local server/account.

Production handlers and native DDOperation/selection run against minimal UI
stand-ins; equipment submission is recorded instead of sending commands.
This is not a physical keyboard, raster QA or FPS measurement.
"""
import os

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
        card = {"item":_root.weapon, "__icBag":bag, "blockItem":_global.__probeNoop}
        card.clickFlag = True
        lol.gpui.BagInterface.prototype.shiftSelect.apply(bag, [{"target":card}])
        report.hits = _root.nativeHits
        report.destination = _root.destination
        report.shift_cleared_click = not card.clickFlag
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
    check('native filtered-out range anchor selects the current card safely', row.get('selected_current'), 'true')
    check('native trade Escape reaches only its own recipient',
          (row.get('trade_escape'), row.get('other_escape')), ('1', '0'))
    check('native complete filter chain preserves stats cancellation and toggle',
          (row.get('stats_cancel'), row.get('stats_toggle')), ('true', 'true'))
    if fails:
        print('\n'.join(fails))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
