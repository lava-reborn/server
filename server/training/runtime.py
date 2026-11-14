"""Training range: runtime."""
import itertools
from training.settings import SERIAL_BASE
from training.config import PLAYER_ID_BASE


ACTIVE = set()
SERIALS = itertools.count(SERIAL_BASE, 1 << 20)
PLAYER_IDS = itertools.count(PLAYER_ID_BASE)
