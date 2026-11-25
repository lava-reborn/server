"""Committed attack animation, including the final lowering sequence."""
from functools import lru_cache
import json
import math
from pathlib import Path

import items

@lru_cache(maxsize=1)
def sequences():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/action_animation.json').read_text(encoding='utf-8'))


def duration_ms(session, params=None, shots=1, *, aimed_for=0):
    """Wait through every shot and fire_out; do not recount an elapsed fire_in.

    Raising a firearm starts at faAim, before its packets. Melee has no
    faAim, so its whole attack sequence starts with caHit/caMiss.
    """
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
    raise_ms = max(0, sequence['fire_in'] * 1000 / data['frame_rate'] - max(0, aimed_for) * 1000)
    frames = sequence['fire'] * cycles + sequence['fire_out']
    # Round once, upwards; a partial frame must not release an attack early.
    return math.ceil(raise_ms + frames * 1000 / data['frame_rate'])
