"""Weapon-paced firearm presentation and native melee recovery."""
from functools import lru_cache
import json
import math
from pathlib import Path

import items

@lru_cache(maxsize=1)
def sequences():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/action_animation.json').read_text(encoding='utf-8'))


FIREARM_ANIMATION_RATIO = 0.35


def duration_ms(session, params=None, shots=1, *, aimed_for=0, mode=0):
    """Firearms add 35% of their selected native aiming time after the shot.

    Burst length and character graphics must not flatten weapon cadence.
    The client fits all fire/fire_out frames into this authoritative budget.
    Bare animation descriptors and melee retain their native frame timing.
    """
    params = params or {}
    times = params.get('fire_times', ())
    if params.get('weapon_type') is not None and 0 <= mode < len(times) and times[mode] > 0:
        return max(1, math.ceil(times[mode] * FIREARM_ANIMATION_RATIO))
    return native_duration_ms(session, params, shots, aimed_for=aimed_for)


def frame_counts(session, params=None, shots=1):
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
    return sequence['fire_in'], sequence['fire'] * cycles + sequence['fire_out']


def native_duration_ms(session, params=None, shots=1, *, aimed_for=0):
    raising, frames = frame_counts(session, params, shots)
    rate = sequences()['frame_rate']
    raise_ms = max(0, raising * 1000 / rate - max(0, aimed_for) * 1000)
    # Round once, upwards; a partial frame must not release an attack early.
    return math.ceil(raise_ms + frames * 1000 / rate)
