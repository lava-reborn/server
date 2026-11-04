"""Versioned experimental rules used by range clones only."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'data' / 'training_rules.json'

@dataclass(frozen=True)
class Rules:
    revision: str = 'baseline-v1'
    attributes: tuple = (1, 1, 1, 1, 1)
    health: float = 1
    stamina: float = 1
    armour: float = 1
    spread: float = 1

    @classmethod
    def parse(cls, raw):
        if set(raw) - {'revision', 'attributes', 'health', 'stamina', 'armour', 'spread'}:
            raise ValueError('Unknown training rule')
        attrs = tuple(raw.get('attributes', (1, 1, 1, 1, 1)))
        if len(attrs) != 5:
            raise ValueError('Five attribute scales required')
        values = attrs + tuple(raw.get(k, 1) for k in ('health', 'stamina', 'armour', 'spread'))
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0.01 <= x <= 10 for x in values):
            raise ValueError('Training scales must be finite in 0.01..10')
        revision = raw.get('revision', 'baseline-v1')
        if not isinstance(revision, str) or not 1 <= len(revision) <= 64:
            raise ValueError('Invalid training revision')
        return cls(revision, attrs, *values[5:])

    def description(self):
        return ('Версия правил: %s. Множители: характеристики %s; HP %g; выносливость %g; '
                'броня %g; разброс %g. Изменения действуют только на полигоне. '
                'Множитель 1 сохраняет текущие правила. Предметы имеют отдельные типы и таблицу параметров.') % (
                    self.revision, '/'.join('%g' % v for v in self.attributes),
                    self.health, self.stamina, self.armour, self.spread)

@lru_cache(maxsize=1)
def current():
    return Rules.parse(json.loads(PATH.read_text(encoding='utf-8-sig')))
