"""Explicit ordinary loot release, with a live NPC retail witness per type.

This is not a use/ownership gate. Personal quests, collectibles, event items
and emitters are outside this ordinary equipment slot. No database reads.
"""
from functools import lru_cache
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'data/mob_equipment_release.json'


@lru_cache(maxsize=1)
def catalogue():
    doc = json.loads(PATH.read_text(encoding='utf-8'))
    if doc.get('version') != 1 or not isinstance(doc.get('items'), dict):
        raise ValueError('Invalid ordinary equipment release catalogue')
    rows = {}
    for key, row in doc['items'].items():
        ident = int(key)
        sellers = row.get('sellers')
        if (ident <= 0 or not row.get('name') or not isinstance(sellers, list) or not sellers
                or any(not isinstance(pair, list) or len(pair) != 2
                       or any(type(value) is not int or value <= 0 for value in pair)
                       for pair in sellers)):
            raise ValueError('Invalid retail witness for equipment ' + key)
        rows[ident] = row
    return rows


@lru_cache(maxsize=1)
def available_types():
    import items
    return frozenset(t for t, row in catalogue().items()
                     if not items.out_of_game(t) and not items.acquisition_blocked(t)
                     and any(trader in sellers_at(location) and t in items.stock_for(trader, location)
                             for trader, location in row['sellers']))


@lru_cache(maxsize=128)
def sellers_at(location):
    """Current native/hand spawns, read once per market; no player database."""
    import world
    loc = world.location(location)
    return frozenset(t for _cell, t in loc.spawns if t) | frozenset(
        int(row['type']) for row in world.placed_in(location))


def available(type_id):
    return type_id in available_types()
