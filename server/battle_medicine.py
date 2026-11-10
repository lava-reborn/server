"""Short, process-local medicine cooldown shared by a character's sessions.

No per-tick writes or database queries. One expiry callback removes each
active entry; room transitions and reconnects share the Store's deadline.
"""
import asyncio
import math

COOLDOWN_SECONDS = 4.0
DESCRIPTION = 'Усталость после использования боевой медицины'


def remaining_ms(store, char_id, now):
    deadlines = getattr(store, '_battle_medicine_deadlines', None)
    if not deadlines:
        return 0
    deadline = deadlines.get(char_id, 0)
    remaining = deadline - now
    if remaining <= 0:
        deadlines.pop(char_id, None)
        return 0
    return min(int(COOLDOWN_SECONDS * 1000), max(1, math.ceil(remaining * 1000 - 1e-6)))


def start(store, char_id, now, duration=COOLDOWN_SECONDS):
    deadlines = getattr(store, '_battle_medicine_deadlines', None)
    if deadlines is None:
        deadlines = {}
        store._battle_medicine_deadlines = deadlines
    duration = max(2.0, min(COOLDOWN_SECONDS, float(duration)))
    deadline = now + duration
    deadlines[char_id] = deadline

    def expire():
        if deadlines.get(char_id) == deadline:
            deadlines.pop(char_id, None)

    asyncio.get_running_loop().call_later(duration, expire)
    return math.ceil(duration * 1000)
