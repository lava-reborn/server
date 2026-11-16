"""Keep passive quest status separate from an explicit NPC interaction."""
from avm_codegen import Compiler

SOURCE = '''
def __qwInit():
    if this.__qwDisposed:
        return
    this.__qwAlive = True
    this.__qwInitial = True
    this.__qwInitOrig()
    if this.currentStatus == "description":
        this.__qwInitial = False

def __qwKill():
    if this.__qwDisposed:
        return
    this.__qwDisposed = True
    this.__qwAlive = False
    this.__qwInitial = False
    this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE, this, this.getAck)
    this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE, this, this.takeAck)
    this.__qwKillOrig()

def __qwStatus(obj):
    if not this.__qwAlive:
        return
    if this.__qwInitial:
        this.__qwInitial = False
        return this.__qwStatusOrig(obj)
    if len(obj.quests) == 0:
        return this.__qwStatusOrig(obj)
    # The native singleton branch opens a fresh acceptance form after a
    # repeatable hand-in. Availability is a list update, not a user action.
    this.rebuildQuestList()

def __qwEdenNPC(obj):
    # Native checkedQuests survives location changes and even relogin.
    # After a release its status=0 can otherwise hide every subsequent
    # quest except the first one of an Eden NPC. Revalidate only this
    # NPC's Eden offers; keep the read FIFO and pending actions intact.
    res = obj.param.res
    if res and res >= 1784 and res <= 1789:
        inspector = lol.core.quests.QuestInspector.getInstance()
        i = 0
        while i < len(obj.param.give_quests):
            inspector.checkedQuests[obj.param.give_quests[i]] = None
            i = i + 1
        i = 0
        while i < len(obj.param.take_quests):
            inspector.checkedQuests[obj.param.take_quests[i]] = None
            i = i + 1
    return this.__qwEdenNPCOrig(obj)
'''


def patches(Asm, undef):
    source = SOURCE
    specs = [('init', '__qwInit'), ('kill', '__qwKill'),
             ('questsStatusUpdate', '__qwStatus')]
    for method in ('getQuest', 'takeQuest', 'back', 'selectQuest', 'getAck', 'takeAck', 'questsUpdate'):
        helper = '__qw' + method[0].upper() + method[1:]
        source += f'''
def {helper}(obj):
    if not this.__qwAlive:
        return
    this.__qwInitial = False
    return this.{helper}Orig(obj)
'''
        specs.append((method, helper))
    functions = Compiler(Asm, undef).functions(source)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = tuple(
        (('gpui', 'QuestInterface'), method, helper + 'Orig', *bodies[helper])
        for method, helper in specs)
    wraps += ((('core', 'player', 'NPC'), 'userInfo', '__qwEdenNPCOrig',
               *bodies['__qwEdenNPC']),)
    return dict(globals=[], wraps=wraps)
