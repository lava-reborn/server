"""Committed firing time; aiming and lowering the weapon are excluded."""
from functools import lru_cache
import json
from pathlib import Path

import items

@lru_cache(maxsize=1)
def sequences():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/action_animation.json').read_text(encoding='utf-8'))


def duration_ms(session, params=None, shots=1):
    """Exclude aiming; count shotgun pellets as one cycle and bursts as shots."""
    params = params or {}
    if params.get('weapon_type') is not None:
        kind = 'pistol' if params['weapon_type'] == items.PISTOL else 'rifle'
        cycles = 1 if params['weapon_type'] == items.SHOTGUN else max(1, shots)
    else:
        kind = 'knife' if params else 'fist'
        cycles = 1
    look = getattr(session.inv, 'look', 0) or (getattr(session, 'active', None) or {}).get('sex', 0)
    data = sequences()
    fallback = data['models']['0']
    model = data['models'].get(str(look), fallback)
    sequence = model.get(kind, fallback[kind])
    frames = sequence['fire'] * cycles
    return (frames * 1000 + data['frame_rate'] - 1) // data['frame_rate']
