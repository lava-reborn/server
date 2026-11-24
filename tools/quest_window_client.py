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
    if this.currentQuest:
        this.currentQuest.removeEventListener("questLoaded", this, this.ReopenDescription)
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
    # NPC's Eden/lift offers; keep the read FIFO and pending actions intact.
    res = obj.param.res
    if res and ((res >= 1784 and res <= 1789) or res == 689):
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

def __qwRefreshNPCs():
    # Keep one native status scan across overlapping repeatable hand-ins.
    # The request/ack FIFO is deliberately untouched.
    clearInterval(this.updateTimerID)
    this.updateTimerID = None
    return this.__qwRefreshNPCsOrig()

def __qwLocationKill():
    inspector = lol.core.quests.QuestInspector.getInstance()
    clearInterval(inspector.updateTimerID)
    inspector.updateTimerID = None
    inspector.updateNPCList = []
    inspector.quester = None
    return this.__qwLocationKillOrig()

def __qwStatusChanged():
    # Replies already in flight still retire normally; their old NPC/window
    # no longer belongs to a live location and must not be dereferenced.
    if not this.quester:
        return
    return this.__qwStatusChangedOrig()

def __qwNPCRemoved(id):
    # Timed NPC refreshes also happen without leaving the location (rent,
    # warehouse rewards, the lab). Drop the open contact before native
    # removal destroys its playerInfo/walker. Pending replies still retire
    # through the existing queues; another NPC's window is left alone.
    inspector = lol.core.quests.QuestInspector.getInstance()
    if inspector.quester and inspector.quester.id == id:
        inspector.quester = None
        inspector.questStatusList = []
        lol.core.SceneShifter.closeWindow("quests", "all")
    return this.__qwNPCRemovedOrig(id)
'''


def patches(Asm, undef):
    source = SOURCE
    specs = [('init', '__qwInit'), ('kill', '__qwKill'),
             ('questsStatusUpdate', '__qwStatus')]
    for method in ('getQuest', 'takeQuest', 'back', 'selectQuest', 'getAck', 'takeAck', 'questsUpdate', 'ReopenDescription'):
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
    wraps += ((('core', 'quests', 'QuestInspector'), 'requestAllNPC', '__qwRefreshNPCsOrig',
               *bodies['__qwRefreshNPCs']),)
    wraps += ((('core', 'quests', 'QuestInspector'), 'checkStatusChanged', '__qwStatusChangedOrig',
               *bodies['__qwStatusChanged']),)
    wraps += ((('core', 'location', 'Location'), 'kill', '__qwLocationKillOrig',
               *bodies['__qwLocationKill']),)
    wraps += ((('core', 'location', 'Location'), 'removePlayer', '__qwNPCRemovedOrig',
               *bodies['__qwNPCRemoved']),)
    return dict(globals=[], wraps=wraps)
