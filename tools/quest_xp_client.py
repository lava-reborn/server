"""Raw quest XP notifications; ordinary combat bonus messages stay native."""
from avm_codegen import Compiler


SOURCE = """
def __questXPInfo(obj):
    previous = _global.__questXPPlain
    _global.__questXPPlain = obj.param.quest_xp == 1
    this.__questXPInfoOrig(obj)
    _global.__questXPPlain = previous

def __questXPBonus(value):
    if _global.__questXPPlain:
        return [value, 0]
    return this.__questXPBonusOrig(value)

def __questXPWarState():
    if _global.__questXPPlain:
        # Pay the quest message now, outside a mixed combat XP queue.
        return False
    return this.__questXPWarStateOrig()
"""


def patches(Asm, undef):
    bodies = {name: (params, body) for name, params, body in Compiler(Asm, undef).functions(SOURCE)}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'player', 'PersAttributes'), 'rp_info', '__questXPInfoOrig', '__questXPInfo'),
        (('services', 'SpecSkillMessages'), 'getRealAndBonus', '__questXPBonusOrig', '__questXPBonus'),
        (('services', 'SpecSkillMessages'), 'warState', '__questXPWarStateOrig', '__questXPWarState'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(wraps=tuple(wraps))
