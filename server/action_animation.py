"""Firearm recovery from native firing frames; legacy blade cadence."""
from functools import lru_cache
import json
import math
from pathlib import Path

import items

@lru_cache(maxsize=1)
def sequences():
    return json.loads((Path(__file__).resolve().parents[1] / 'data/action_animation.json').read_text(encoding='utf-8'))


FIREARM_ANIMATION_RATIO = 0.25
FIREARM_MIN_RECOVERY_MS = 150


def duration_ms(session, params=None, shots=1, *, aimed_for=0, mode=0):
    """Firearms reserve 25% of native firing time, with a 150 ms floor.

    Aim and lowering are not part of that reference. The ordinary model
    prevents costume-dependent cadence; shotgun pellets share one firing
    cycle. Blades keep their old swing-only recovery; bare fists
    retain the complete native sequence. Client presentation fits the budget.
    """
    params = params or {}
    if params:
        firearm = params.get('weapon_type') is not None
        _, frames = frame_counts(session, params, shots, include_lowering=False,
                                 model_look=0 if firearm else None)
        ratio = FIREARM_ANIMATION_RATIO if firearm else 1
        minimum = FIREARM_MIN_RECOVERY_MS if firearm else 1
        return max(minimum, math.ceil(frames * 1000 / sequences()['frame_rate'] * ratio))
    return native_duration_ms(session, params, shots, aimed_for=aimed_for)


def frame_counts(session, params=None, shots=1, *, include_lowering=True, model_look=None):
    params = params or {}
    if params.get('weapon_type') is not None:
        kind = 'pistol' if params['weapon_type'] == items.PISTOL else 'rifle'
        cycles = 1 if params['weapon_type'] == items.SHOTGUN else max(1, shots)
    else:
        kind = 'knife' if params else 'fist'
        cycles = 1
    look = model_look
    if look is None:
        look = getattr(session.inv, 'look', 0) or (getattr(session, 'active', None) or {}).get('sex', 0)
    data = sequences()
    fallback = data['models']['0']
    model = data['models'].get(str(look), fallback)
    sequence = model.get(kind, fallback[kind])
    frames = sequence['fire'] * cycles
    if include_lowering:
        frames += sequence['fire_out']
    return sequence['fire_in'], frames


def native_duration_ms(session, params=None, shots=1, *, aimed_for=0):
    raising, frames = frame_counts(session, params, shots)
    rate = sequences()['frame_rate']
    raise_ms = max(0, raising * 1000 / rate - max(0, aimed_for) * 1000)
    # Round once, upwards; a partial frame must not release an attack early.
    return math.ceil(raise_ms + frames * 1000 / rate)
