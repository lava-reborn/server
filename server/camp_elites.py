"""Existing fighters reserved for camp interiors; no new client mob resources."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def locations():
    path = Path(__file__).resolve().parents[1] / 'data/camp_elites.json'
    with path.open(encoding='utf-8') as stream:
        return {int(k): (frozenset(row['sources']), tuple(row['types']))
                for k, row in json.load(stream)['locations'].items()}


# Exact kill targets and carriers at the locations marked by existing quests.
QUEST_TARGETS = {80: frozenset({258, 261}), 84: frozenset({291}),
                 85: frozenset({303, 307, 311}), 93: frozenset({362, 365, 366}),
                 98: frozenset({399}), 168: frozenset({1027})}


def applies(loc_id, type_id):
    record = locations().get(loc_id)
    return (record is not None and type_id in record[0]
            and type_id not in QUEST_TARGETS.get(loc_id, ()))


def replacement(loc_id, type_id, index):
    record = locations().get(loc_id)
    if not applies(loc_id, type_id):
        return type_id
    return record[1][index % len(record[1])]
