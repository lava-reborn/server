"""Teacher prices follow the authoritative vacant-slot quote."""
from avm_codegen import Compiler

SOURCE = '''
def __saAttributes(obj):
    if obj.param.spec_slots != None:
        this.__saSlots = Number(obj.param.spec_slots)
        this.__saAfro = Number(obj.param.spec_next_afro)
        this.__saGold = Number(obj.param.spec_next_gold)
    this.__saAttributesOrig(obj)

def __saCost():
    attrs = this.master.gamer.attributes
    if attrs.__saSlots == None:
        return this.__saCostOrig()
    if attrs.__saGold > 0:
        return {"cost":attrs.__saGold / 100, "type":"gold"}
    return {"cost":attrs.__saAfro, "type":"afro"}
'''


def patches(Asm, undef):
    functions = Compiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('core', 'player', 'PersAttributes'), 'rp_info', '__saAttributesOrig', '__saAttributes'),
        (('core', 'player', 'Training'), 'getCost', '__saCostOrig', '__saCost'),
    ):
        params, body = bodies[helper]
        wraps.append((path, method, keep, params, body))
    return dict(globals=functions, wraps=tuple(wraps))
