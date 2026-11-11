"""Reviewed range-only targets. No world scans, database work or main-game overrides."""
import json
import re
from pathlib import Path
from types import MappingProxyType

GROUPS = {'all': 'Все противники', 'camps': 'Бойцы лагерей', 'mines': 'Шахты',
          'bosses': 'Боссы лагерей', 'crocodiles': 'Крокодилы', 'animals': 'Животные',
          'patrols': 'Патрули Магриба', 'caravans': 'Караваны'}
NAME_BASE = 8_200_000
_raw = json.loads((Path(__file__).resolve().parents[1] / 'data/training_opponents.json').read_text(encoding='utf-8'))
_rows = _raw['opponents']
if (_raw['version'] != 1 or len({row['id'] for row in _rows}) != len(_rows)
        or any(not isinstance(row['id'], int) or not 0 < row['id'] < 100000
               or row['group'] not in GROUPS or row['group'] == 'all'
               or row['source'] not in ('spawn', 'additional')
               or not re.search('[А-Яа-яЁё]', row['name'])
               or any(mark in row['name'] for mark in ('_', '<', '>', '.swf')) for row in _rows)):
    raise ValueError('Invalid training opponent catalogue')
RECORDS = MappingProxyType({row['id']: MappingProxyType(row) for row in _rows})
NAMES = {NAME_BASE + type_id: row['name'].replace(' · ', '<br>', 1)
         for type_id, row in RECORDS.items()}
