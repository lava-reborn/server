"""Purchase discount for blueprints explicitly restricted to A weapons."""
import re

CHEAP_GOLD_STEP = 50       # hundredths: 0.5 G
GOLD_STEP = 250            # hundredths: 2.5 G
CHEAP_LIMIT = 500          # Below 5 G the coarse step would swallow the discount.


def apply(name, params):
    if not re.fullmatch(r'bpg_damage_25_afro_lvl\d+', name):
        return
    gold = params.get('g_cost', 0)
    if gold:
        step = CHEAP_GOLD_STEP if gold < CHEAP_LIMIT else GOLD_STEP
        # Divide by 1.5 and round to the nearest price step using integers.
        params['g_cost'] = min(gold, max(step, step * ((4 * gold + 3 * step) // (6 * step))))
    if params.get('cost', 0):
        params['cost'] = max(1, params['cost'] * 2 // 3)
