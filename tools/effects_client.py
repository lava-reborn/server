"""Keep cached effect prototypes attached to the current player's scene."""
from avm_codegen import Compiler

SOURCE = '''
def __effectSceneList(obj):
    # EffectsFactory survives scene changes; its prototypes retain the first
    # manager. Rebind before cloning so late e_si/e_di reach the live scene.
    if this.isGamer and obj.param.mobi_id == this.mobID:
        types = obj.param.effects
        i = 0
        while types and i < len(types):
            proto = lol.core.effects.EffectsFactory.fxStore[types[i]]
            if proto:
                proto._em = this
            i = i + 1
    return this.__effectSceneListOrig(obj)
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    _name, params, body = functions[0]
    return dict(globals=(), wraps=((('core', 'effects', 'EffectManager'),
        'e_list', '__effectSceneListOrig', params, body),))
