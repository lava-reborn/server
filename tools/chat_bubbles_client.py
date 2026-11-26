"""Location phrases must not confuse persistent clan IDs with local entities."""
from avm_codegen import Compiler

SOURCE = """
def __cbChatRefreshed(obj):
    # Only location chat addresses a local sprite. Clan/party/private/world
    # senders use other ID namespaces or may stand in another location.
    if not obj or obj.group != 0 or not obj.logArr or obj.logArr.length == 0:
        return
    row = obj.logArr[obj.logArr.length - 1]
    if not row or (row.group != undefined and row.group != 0):
        return
    if not this.helperObjects:
        return
    sprite = this.helperObjects[row.fromID]
    # Player.userInfo marks real players; NPCs inherit Entity, not Player.
    if not sprite or not sprite.driver or sprite.driver.__rcPlayer != True:
        return
    # Reject stale/reused local IDs even when another player owns that ID.
    name = sprite.driver.playerInfo.name
    if not row.name or not name or row.name != name:
        return
    return this.__cbChatOrig(obj)
"""


def patches(Asm, undef):
    name, args, body = Compiler(Asm, undef).functions(SOURCE)[0]
    return dict(globals=(), wraps=((('core', 'location', 'DisplayLocScene'),
                                   'chatRefreshed', '__cbChatOrig', args, body),))
