"""Mortimer's explicit gold-valuables buyback, separate from ingot services."""

from progression import GOLD_OUNCE, GOLD_TO_AFRO_RATE


NPC_TYPES = frozenset({1188, 1990, 2479, 2480, 4017})
VALUABLES = frozenset({6950, 6951, 6952, 6953, 6959})
SAND = 2258
AFRO_PER_GOLD = GOLD_TO_AFRO_RATE
GOLD_CENTS = GOLD_OUNCE


def unit_gold(type_id):
    """Hundredths per piece, rounded down before multiplying by quantity."""
    if type_id not in VALUABLES:
        return 0
    import items
    info = items.params_of(type_id) or {}
    if info.get('quest') or items.root_of(type_id) != items.TRASH:
        return 0
    return max(0, int(info.get('cost', 0)) * GOLD_CENTS // AFRO_PER_GOLD)
