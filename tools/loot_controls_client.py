"""Configurable loot shortcut using the native settings and modal filters."""
from avm_codegen import Compiler

SOURCE = '''
def __lootDefaults():
    this.__lootDefaultsOrig()
    this.hotKeyArr["LOOT_TAKE_ALL"] = {"keyCode":[69], "keyCode1":[69], "focus":True, "title":"Добыча", "about":"Взять всё из мешка"}

def __lootFilters():
    this.__lootFiltersOrig()
    this.lootArr.push("LOOT_TAKE_ALL")

def __lootInit():
    this.__lootInitOrig()
    lol.core.SceneShifter.hotKeyManager.addEventListener("LOOT_TAKE_ALL", this, _global.__lootTakeKey)

def __lootTakeKey():
    keys = lol.core.SceneShifter.hotKeyManager
    if keys.enabled and keys.checkFilter("loot") and this.loot and this.loot.status:
        this.transferAll()

def __lootKill():
    lol.core.SceneShifter.hotKeyManager.removeEventListener("LOOT_TAKE_ALL", this, _global.__lootTakeKey)
    if this.loot:
        this.loot.removeEventListener("transferAll", this, this.transferAllOk)
    this.__lootKillOrig()

def __lootTransferAll():
    if this.__lootTakePending or not this.status:
        return
    message = new(lol.server.mess.CSM_SSUpdate, lol.core.player.Loot.UPD_GET_ALL, new(lol.data.BigUINT, new(lol.data.BigUINTCluster, 0)))
    if this.XMC.Send(message):
        this.__lootTakePending = True
        lol.server.XMLCCallStack.addCall("cmdAck", this, this.allTranferAck)

def __lootTransferAck(obj):
    this.__lootTakePending = False
    this.__lootTransferAckOrig(obj)
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('services', 'HotKeyManager'), 'createDefaultArr', '__lootDefaultsOrig', '__lootDefaults'),
        (('services', 'HotKeyFilter'), 'createFilterArr', '__lootFiltersOrig', '__lootFilters'),
        (('gpui', 'LootInterface'), 'init', '__lootInitOrig', '__lootInit'),
        (('gpui', 'LootInterface'), 'kill', '__lootKillOrig', '__lootKill'),
        (('core', 'player', 'Loot'), 'transferAll', '__lootTransferAllOrig', '__lootTransferAll'),
        (('core', 'player', 'Loot'), 'allTranferAck', '__lootTransferAckOrig', '__lootTransferAck'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
