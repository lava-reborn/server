"""Training range: settings."""
from training import config, content
from training import layout as training_layout


BERT = 2088
ENTRY_QUEST = config.ENTRY_QUEST
EXIT_QUEST = config.EXIT_QUEST
MARKET = 35
RANGE = 108
ARENA_WIDTH, ARENA_HEIGHT = content.location(RANGE)['width'], content.location(RANGE)['height']
COMPUTER_CELL = content.location(RANGE)['computer']
CONTROL_CELL = content.location(RANGE)['control']
LOCATIONS = {int(key): (row['computer'], row['name'], row['control'])
             for key, row in content.data()['locations'].items()}
LEGACY_LOCATIONS = frozenset(content.data()['legacy_locations'])
FIGHT_START = content.location(RANGE)['fight_start']
ENEMY_SPAWNS = {key: tuple(content.location(key)['enemy_spawns']) for key in LOCATIONS}

SPAWN_LABELS = ('Ближняя - выше справа от компьютера', 'Средняя', 'Дальняя - справа сверху')
DEFAULT_SPAWN = 0
TERMINAL = 1263
TERMINAL_CELL = LOCATIONS[RANGE][0]
MAX_SESSIONS = config.limit('LAVA_TRAINING_MAX_SESSIONS', 16, 1, 128)
MAX_ITEMS = 32
CARRY_LIMIT_GRAMS = 150_000
MAX_LEVEL = 20
PAGE_SIZE = 10
IDLE_SECONDS = config.limit('LAVA_TRAINING_IDLE_SECONDS', 1800, 30, 86400)
SERIAL_BASE = config.SERIAL_BASE
ENABLED = config.enabled()
READ_COMMANDS = frozenset(('getInfo', 'rp_get_info', 'ss_get_si', 'ss_get_di',
                           'ss_get', 'ss_get_s_si', 'e_get_si', 'e_get_di', 'q_si', 'q_di', 'q_status', 'ah_search'))
PLAY_COMMANDS = frozenset(('moveTo', 'ss_move', 'ss_use', 'ss_heap_c'))
CONTRABAND_TRADER = 2391
