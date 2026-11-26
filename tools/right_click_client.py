"""Use the launcher's scoped F24 bridge to open the native player menu."""
from avm_codegen import Compiler

SOURCE = '''
def __rcPlayerInfo(obj):
    this.__rcPlayer = True
    return this.__rcPlayerInfoOrig(obj)

def __rcKeyDown():
    if Key.getCode() != 135:
        return this.__rcKeyDownOrig()
    manager = this.sfManager
    if not manager or not manager.activated or not manager.flared or not manager.flared.target:
        return
    player = manager.flared.target.driver
    if not player or not player.__rcPlayer or player.id == None or player.id == lol.core.player.Gamer.ID:
        return
    manager.contextMenuPlayer = player
    manager.createContextMenu()

def __rcKeyUp():
    if Key.getCode() != 135:
        return this.__rcKeyUpOrig()

def __rcHotDown():
    if Key.getCode() != 135:
        return this.__rcHotDownOrig()

def __rcHotUp():
    if Key.getCode() != 135:
        return this.__rcHotUpOrig()
'''


def patches(Asm, undef):
    bodies = {name: (args, body) for name, args, body in Compiler(Asm, undef).functions(SOURCE)}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'player', 'Player'), 'userInfo', '__rcPlayerInfoOrig', '__rcPlayerInfo'),
        (('core', 'location', 'CursorManager'), 'onKeyDown', '__rcKeyDownOrig', '__rcKeyDown'),
        (('core', 'location', 'CursorManager'), 'onKeyUp', '__rcKeyUpOrig', '__rcKeyUp'),
        (('services', 'HotKeyManager'), 'onKeyDown', '__rcHotDownOrig', '__rcHotDown'),
        (('services', 'HotKeyManager'), 'onKeyUp', '__rcHotUpOrig', '__rcHotUp'),
    ):
        args, body = bodies[helper]
        wraps.append((path, method, keep, args, body))
    return dict(globals=(), wraps=tuple(wraps))
