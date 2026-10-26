"""Execute quick-heal AVM1 against mixed inventories and room war changes.

Owner update: medicine category depends only on room war, not a personal
hit deadline. Both resource wrappers use the same selector.
"""
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
        self.props = dict(max_h_rest=amount, max_st_rest=amount, heal_cost=cost, use_count=1, _effects=[])
        self.props.update(extra)

    def getProp(self, key):
        return self.props.get(key, 0)

def run(entries, bag, war, array='healArr', max_ap=100, location=None, now_ms=0,
        health=30, stamina=20):
    gamer = NS(apManager=NS(maxAP=max_ap), attributes=NS(
        health=health, maxHealth=100, stamina=stamina, maxStamina=100))
    master = NS(currentLocation=location or NS(warStatus=war), gamer=gamer)
    global_obj = NS(lol=NS(core=NS(Master=NS(getInstance=lambda: master))))
    equip = NS(bag=NS(chekExist=lambda item: item in bag))
    # Preserve incoming order: addHealItem can leave stamina entries in
    # lexical order, and selection must not depend on that client defect.
    original_array = [dict(item=i) for i in entries]
    setattr(equip, array, original_array)
    sent = []
    original = '__quickHealOrig' if array == 'healArr' else '__quickEatOrig'
    setattr(equip, original, lambda: sent.append(getattr(equip, array)[0]['item'].name))
    env = {'this': equip, '_global': global_obj}
    env['__quickMedPick'] = lambda equip, entries, resource: execute(w.fn_quick_med_pick().assemble(), dict(equip=equip, entries=entries, resource=resource, _global=global_obj, getTimer=lambda: now_ms))
    execute(w.fn_quick_med_use(array, original).assemble(), env)
    assert getattr(equip, array) is original_array, 'original arrays must be restored'
    return sent
peace = Item('peace', 500, 0)
combat = Item('combat', 150, 6)
buff = Item('buff', 1000, 0, bonus_act_time=300)
check('room war selects battle medicine even before personal damage', run([peace, combat, buff], [peace, combat, buff], True), ['combat'])
check('peace prefers ordinary medicine in the bag', run([peace, combat, buff], [peace, combat, buff], False), ['peace'])
check('peace bag medicine beats stronger hand medicine', run([peace, Item('hand', 900, 0)], [peace], False), ['peace'])
check('peace falls back to battle medicine when no ordinary one exists', run([combat], [combat], False), ['combat'])
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

hp_med = Item('hp', 500, 0, max_st_rest=9)
sp_med = Item('stamina', 20, 0, max_st_rest=100)
for entries in ([hp_med, sp_med], [sp_med, hp_med]):
    for hp in (30, 100):
        check('stamina selection uses numeric stamina restoration regardless of HP or item order',
              run(entries, entries, False, array='eatArr', health=hp), ['stamina'])
    check('health selection still uses health restoration from mixed medicines',
          run(entries, entries, False), ['hp'])
hp_only = Item('hp-only', 500, 0, max_st_rest=0)
check('stamina request never consumes a medicine that restores only HP',
      run([hp_only], [hp_only], False, array='eatArr'), [])

# A stale deadline from an older client patch must not affect either key.
location = NS(warStatus=True, __quickMedUntil=16000)
for array in ('healArr', 'eatArr'):
    check('room war selects battle medicine',
          run([peace, combat], [peace, combat], True, array=array, location=location, now_ms=1000), ['combat'])
    location.warStatus = False
    check('room peace immediately selects ordinary medicine while standing still',
          run([peace, combat], [peace, combat], False, array=array, location=location, now_ms=1001), ['peace'])
    check('battle medicine remains available in peace without ordinary medicine',
          run([combat], [combat], False, array=array, location=location, now_ms=1001), ['combat'])
    location.warStatus = True

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
