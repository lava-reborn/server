"""Training range: settings."""
import os
from training import layout as training_layout


BERT = 2088
ENTRY_QUEST = 9301
EXIT_QUEST = 9302
MARKET = 35
RANGE = 108
ARENA_WIDTH, ARENA_HEIGHT = 72, 144
COMPUTER_CELL = training_layout.BY_KEY['computer'].cell(ARENA_WIDTH)
CONTROL_CELL = COMPUTER_CELL + 1
LOCATIONS = {108: (COMPUTER_CELL, 'Пустынный полигон', CONTROL_CELL),
             59: (96 * 64 + 32, 'Арена №1 Вади-Хальфы', 96 * 64 + 33)}
LEGACY_LOCATIONS = frozenset((78,))
FIGHT_START = 78 * ARENA_WIDTH + 36
ENEMY_SPAWNS = {location: (98 * ARENA_WIDTH + 44, 65 * ARENA_WIDTH + 44, 8 * ARENA_WIDTH + 65) for location in LOCATIONS}
ENEMY_SPAWNS[59] = (68 * 64 + 40, 52 * 64 + 44, 35 * 64 + 46)
SPAWN_LABELS = ('Ближняя — выше справа от компьютера', 'Средняя', 'Дальняя — справа сверху')
DEFAULT_SPAWN = 0
TERMINAL = 1263
TERMINAL_CELL = LOCATIONS[RANGE][0]
MAX_SESSIONS = 16
MAX_ITEMS = 32
CARRY_LIMIT_GRAMS = 150_000
MAX_LEVEL = 20
PAGE_SIZE = 10
IDLE_SECONDS = 1800
SERIAL_BASE = 1 << 40
ENABLED = os.environ.get('LAVA_TRAINING_GROUND', '0') == '1'
READ_COMMANDS = frozenset(('getInfo', 'rp_get_info', 'ss_get_si', 'ss_get_di',
                           'ss_get', 'ss_get_s_si', 'e_get_si', 'e_get_di', 'q_si', 'q_di', 'q_status', 'ah_search'))
PLAY_COMMANDS = frozenset(('moveTo', 'ss_move', 'ss_use', 'ss_heap_c'))
CONTRABAND_TRADER = 2391
