"""G-only restoration: pay for the factory ceiling lost through repairs."""
import math


def base_price(type_id, params):
    """Gold hundredths; an A item's alternate G shop price is not eligibility."""
    import combat
    import items
    if items.root_of(type_id) not in items.BREAKABLE_ROOTS or not combat.gold_item(type_id):
        return 0
    return params.get("g_cost", 0) or 0


def price(params, ceiling, modifier=1):
    """Nearest hundredth, positive halves up; no free positive restoration."""
    factory = params.get("max_break_abs", 0) or 0
    cost = params.get("g_cost", 0) or 0
    if factory <= 0 or ceiling < 0 or ceiling > factory or cost <= 0:
        return None
    lost = factory - ceiling
    if not lost:
        return 0
    return max(1, math.floor(cost * modifier * lost / factory + 0.5))
