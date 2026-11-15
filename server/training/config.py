"""Resource-free deployment configuration shared with the integration facade."""
import os

ENTRY_QUEST = 9301
EXIT_QUEST = 9302
SERIAL_BASE = 1 << 40
CLIENT_PROTOCOL = 1
# Shared visits are reserved for a separately tested future release. Do not
# expose an environment/client override in the current solo-only deployment.
SHARED_ROOMS = False

# Private protocol namespaces. Assigned item ids are frozen in
# data/training_item_ids.json and checked against the ordinary catalogue.
# 60000..60999 stays with ordinary designed equipment, never range copies.
ITEM_FIRST, ITEM_LAST = 54000, 65535
BASELINE_LAST = 56999
SIMULATOR_FIRST, SIMULATOR_LAST = 57000, 59999
PROTOTYPE_FIRST, PROTOTYPE_LAST = 61000, 61999
SET_FIRST, SET_SIMULATOR_OFFSET = 80000, 1000
EFFECT_FIRST = 90000
PLAYER_ID_BASE = 100_000_000


def enabled():
    return os.environ.get('LAVA_TRAINING_GROUND', '0') == '1'


def limit(name, default, low, high):
    value = int(os.environ.get(name, default))
    if not low <= value <= high:
        raise ValueError('%s must be in %d..%d' % (name, low, high))
    return value
