"""Reviewed ordinary weapon roles, independent of combat numbers and sites.

The explicit type policy is loaded once. Mob preparation consults it; an
attack never scans camp rooms, the world or item tables to choose a class.
"""
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType


PATH = Path(__file__).resolve().parents[1] / 'data' / 'mob_loadouts.json'


@lru_cache(maxsize=1)
def policy():
    raw = json.loads(PATH.read_text(encoding='utf-8'))
    camps = {}
    rifles = set(raw['non_camp_rifle_types'])
    if (raw.get('version') != 1
            or any(type(t) is not int or t <= 0 for t in rifles)):
        raise ValueError('Invalid ordinary mob weapon policy')
    membership = {}
    for key, row in raw['camps'].items():
        camp = int(key)
        members = frozenset(row['types'])
        sniper = row['rifle_type']
        if (camp <= 0 or not members
                or any(type(t) is not int or t <= 0 for t in members)
                or (sniper is not None and (type(sniper) is not int or sniper not in members))):
            raise ValueError('Invalid ordinary camp weapon policy: ' + key)
        for type_id in members:
            membership.setdefault(type_id, set()).add(sniper == type_id)
        camps[camp] = (members, sniper)
        if sniper is not None:
            rifles.add(sniper)
    # A type used by two camps cannot be a sniper in only one of them.
    if any(len(roles) > 1 for roles in membership.values()):
        raise ValueError('Conflicting shared camp sniper type')
    camp_members = set(membership)
    if any(t in camp_members and not all(membership[t])
           for t in raw['non_camp_rifle_types']):
        raise ValueError('Non-camp sniper overlaps a camp ordinary fighter')
    return MappingProxyType(camps), frozenset(rifles)


def weapon_class(type_id, original):
    """Keep native roles, reserving rifles for the reviewed sniper types."""
    rifles = policy()[1]
    if type_id in rifles:
        return 'rifle'
    return 'assault_rifle' if original == 'rifle' else original
