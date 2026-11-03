"""Cached economic overrides keyed only by mob type, never by location."""
import json
from functools import lru_cache
from pathlib import Path

import items

# Ordinary materials required by the existing provisions and rope quests.
QUEST_MATERIALS = frozenset({3179, 6915, 6942})


@lru_cache(maxsize=1)
def records():
    path = Path(__file__).resolve().parents[1] / 'data/loot_rebalance.json'
    with path.open(encoding='utf-8') as stream:
        return {int(k): rows for k, rows in json.load(stream)['by_type'].items()}


def economic(type_id):
    info = items.params_of(type_id) or {}
    return (items.root_of(type_id) == items.TRASH and info.get('cost', 0) > 0
            and not info.get('quest') and type_id not in items.GOLD_INGOTS
            and type_id not in QUEST_MATERIALS)
