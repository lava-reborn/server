"""Execute the emitted quick-heal AVM1 against mixed inventories and battle states."""
import os
import sys
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
import widescreen as w
from testkit import check, fails
from avm_test import execute  # noqa: E402

class Item:

    def __init__(self, name, amount, cost, **extra):
        self.name = name
        self.props = dict(max_h_rest=amount, heal_cost=cost, use_count=1, _effects=[], **extra)

    def getProp(self, key):
        return self.props.get(key, 0)

def run(entries, bag, war, array='healArr', max_ap=100):
    gamer = NS(apManager=NS(maxAP=max_ap))
    master = NS(currentLocation=NS(warStatus=war), gamer=gamer)
    global_obj = NS(lol=NS(core=NS(Master=NS(getInstance=lambda: master))))
    equip = NS(bag=NS(chekExist=lambda item: item in bag))
    original_array = [dict(item=i, max_h_rest=i.props['max_h_rest']) for i in sorted(entries, key=lambda i: i.props['max_h_rest'])]
    setattr(equip, array, original_array)
    sent = []
    original = '__quickHealOrig' if array == 'healArr' else '__quickEatOrig'
    setattr(equip, original, lambda: sent.append(getattr(equip, array)[0]['item'].name))
    env = {'this': equip, '_global': global_obj}
    env['__quickMedPick'] = lambda equip, entries: execute(w.fn_quick_med_pick().assemble(), dict(equip=equip, entries=entries, _global=global_obj))
    execute(w.fn_quick_med_use(array, original).assemble(), env)
    assert getattr(equip, array) is original_array, 'original arrays must be restored'
    return sent
peace = Item('peace', 500, 0)
combat = Item('combat', 150, 6)
buff = Item('buff', 1000, 0, bonus_act_time=300)
check('room war selects battle medicine even before personal damage', run([peace, combat, buff], [peace, combat, buff], True), ['combat'])
check('peace prefers ordinary medicine in the bag', run([peace, combat, buff], [peace, combat, buff], False), ['peace'])
check('peace bag medicine beats stronger hand medicine', run([peace, Item('hand', 900, 0)], [peace], False), ['peace'])
check('peace falls back to combat medicine when no ordinary one exists', run([combat], [combat], False), ['combat'])
check('ordinary medicine is excluded in a room at war', run([peace], [peace], True), [])
check('buffs alone cause no automatic use', run([buff], [buff], False), [])
# HealItem stores effects in _effects, not the original wire field.
effect = Item('effect', 999, 4)
effect.props['_effects'] = [1]
check('client effect property excluded', run([effect, combat], [effect, combat], True), ['combat'])
check('too expensive battle item is skipped', run([combat], [combat], True, max_ap=5), [])
check('strongest eligible medicine is selected', run([combat, Item('strong', 200, 8)], [combat], True), ['strong'])
check('empty inventory is safe', run([], [], False), [])
check('stamina hotkey uses the same filtering', run([peace, combat, buff], [peace, combat, buff], True, array='eatArr'), ['combat'])
check('both wrappers included in client injection', all((n.encode() in w.injected() for n in ('__quickHealOrig', '__quickEatOrig', '__quickMedPick'))), True)
# Cross-check client filtering against the effective server catalogue.
if os.environ.get('LAVA_RES'):
    import items
    mismatch = []
    categories = []
    for t, (root, name) in items.catalogue().items():
        if root != items.HEAL:
            continue
        p = items.params_of(t)
        if name.startswith(('Med_Battle_', 'Med_Pacific_')):
            if bool(p.get('heal_cost')) != name.startswith('Med_Battle_'):
                categories.append(t)
        if not items.stimulant_unavailable(t):
            continue
        obj = Item.__new__(Item)
        obj.name = str(t)
        obj.props = dict(p, use_count=1, _effects=p.get('effects', []))
        for war in (False, True):
            if run([obj], [obj], war):
                mismatch.append((t, war))
    check('client skips every stimulant currently blocked by server', mismatch, [])
    check('battle/peace category agrees with all current medical item data', categories, [])
empty = Item('empty', 1000, 6)
empty.props['use_count'] = 0
check('empty doses never block the next eligible medicine', run([empty, combat], [empty, combat], True), ['combat'])
if fails:
    print('\n'.join(fails))
    sys.exit(1)
