"""Refresh owned equipment and retire local quests after committed Eden moves.

The native gamer asks for its first equipment list once per connection.
Subsequent location loads retain that cache. Request the ordinary masked
list after lenter; never push an unsolicited ss_ack or move client items.
"""
import ast

from avm_codegen import Compiler


SOURCE = '''
def __edInventoryNotification(cmd):
    if cmd.messID == "eden_inv" and cmd.params.refresh == 1:
        lol.core.Master.getInstance().__edEquipmentPending = True
        if cmd.params.clear_eden == 1:
            inspector = lol.core.quests.QuestInspector.getInstance()
            local_types = {}
            i = 0
            while i < len(cmd.params.q_types):
                quest_type = cmd.params.q_types[i]
                local_types[quest_type] = True
                del inspector.cqList[quest_type]
                del inspector.checkedQuests[quest_type]
                i = i + 1
            changed = False
            # currentQuests is sparse and keyed by global instance IDs.
            # Enumerate its actual properties, never scan up to its length.
            for qid in keys(inspector.currentQuests):
                task = inspector.currentQuests[qid]
                if task and local_types[task.typeID]:
                    del inspector.currentQuests[qid]
                    if inspector.closedQuest == qid:
                        inspector.closedQuest = None
                    changed = True
            if local_types[inspector.closedQuest]:
                inspector.closedQuest = None
            if changed:
                # Native journal listeners rebuild from currentQuests.
                # No cancel packet/ACK or unrelated NPC status reset.
                inspector.questUpdate()
    return this.__edInventoryNotifyOrig(cmd)

def __edInventoryEnter(obj):
    equipment = this.gamer.equipment
    loaded = equipment and equipment.first
    this.__edInventoryEnterOrig(obj)
    if not this.__edEquipmentPending:
        return
    this.__edEquipmentPending = False
    # Native firstRequest already queued the same mask on a fresh gamer.
    # A retained gamer needs its own FIFO request after LOCAL_STATE begins.
    if loaded:
        this.gamer.equipment.getStuff(11, 0)

def __edInventoryClose():
    this.__edEquipmentPending = False
    return this.__edInventoryCloseOrig()
'''


class _EdenCompiler(Compiler):
    """Two local AS2 operations for the sparse, native quest dictionary."""

    def statements(self, a, body):
        for node in body:
            if isinstance(node, ast.Delete):
                target, = node.targets
                assert isinstance(target, ast.Subscript)
                self.expression(a, target.value)
                self.expression(a, target.slice)
                a.op('delete').op('pop')
            elif (isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                  and isinstance(node.iter, ast.Call)
                  and isinstance(node.iter.func, ast.Name)
                  and node.iter.func.id == 'keys' and not node.orelse):
                # Enumerate2 pushes a null sentinel followed by property keys;
                # StackSwap puts each key in DefineLocal's value position.
                start, end = self.label(), self.label()
                self.expression(a, node.iter.args[0])
                a.op('enumerate2').label(start).push(node.target.id).op('stackswap')
                a.op('definelocal').var(node.target.id).push(None).op('equals2').iftrue(end)
                self.statements(a, node.body)
                a.push(True).iftrue(start).label(end)
            else:
                super().statements(a, [node])
        return a


def patches(Asm, undef):
    functions = _EdenCompiler(Asm, undef).functions(SOURCE)
    bodies = {name: (params, body) for name, params, body in functions}
    wraps = []
    for path, method, keep, helper in (
        (('server', 'XMLConnection'), 'sendNotification', '__edInventoryNotifyOrig',
         '__edInventoryNotification'),
        (('core', 'Master'), 'lenter', '__edInventoryEnterOrig', '__edInventoryEnter'),
        (('core', 'Master'), 'onClose', '__edInventoryCloseOrig', '__edInventoryClose'),
    ):
        wraps.append((path, method, keep, *bodies[helper]))
    return dict(globals=[], wraps=tuple(wraps))
