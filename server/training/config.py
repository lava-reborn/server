"""Resource-free deployment configuration shared with the integration facade."""
import os

ENTRY_QUEST = 9301
EXIT_QUEST = 9302
SERIAL_BASE = 1 << 40
CLIENT_PROTOCOL = 1


def enabled():
    return os.environ.get('LAVA_TRAINING_GROUND', '0') == '1'


def limit(name, default, low, high):
    value = int(os.environ.get(name, default))
    if not low <= value <= high:
        raise ValueError('%s must be in %d..%d' % (name, low, high))
    return value
