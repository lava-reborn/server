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


def applies(loc_id, type_id):
    record = locations().get(loc_id)
    return record is not None and type_id in record[0]


def replacement(loc_id, type_id, index):
    record = locations().get(loc_id)
    if record is None or type_id not in record[0]:
        return type_id
    return record[1][index % len(record[1])]
