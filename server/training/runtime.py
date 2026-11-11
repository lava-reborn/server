"""Training range: runtime."""
import itertools
from training.settings import SERIAL_BASE


ACTIVE = set()
SERIALS = itertools.count(SERIAL_BASE, 1 << 20)
PLAYER_IDS = itertools.count(100_000_000)
