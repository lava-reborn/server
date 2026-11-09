"""Versioned experimental rules used by range clones only."""
from dataclasses import asdict, dataclass
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
    effect_armour: float = 0
    ammo_modifiers: bool = False
    broken_armour: bool = False
    combat_v2: bool = True

    @classmethod
    def parse(cls, raw):
        if set(raw) - {'revision', 'attributes', 'health', 'stamina', 'armour', 'spread',
                       'effect_armour', 'ammo_modifiers', 'broken_armour', 'combat_v2'}:
            raise ValueError('Unknown training rule')
        attrs = tuple(raw.get('attributes', (1, 1, 1, 1, 1)))
        if len(attrs) != 5:
            raise ValueError('Five attribute scales required')
        values = attrs + tuple(raw.get(k, 1) for k in ('health', 'stamina', 'armour', 'spread'))
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0.01 <= x <= 10 for x in values):
            raise ValueError('Training scales must be finite in 0.01..10')
        revision = raw.get('revision', 'candidate-v2')
        if not isinstance(revision, str) or not 1 <= len(revision) <= 64:
            raise ValueError('Invalid training revision')
        effect = raw.get('effect_armour', 0)
        if isinstance(effect, bool) or not isinstance(effect, (int, float)) or not math.isfinite(effect) or not 0 <= effect <= 200:
            raise ValueError('Training effect armour must be finite in 0..200')
        ammo, broken = raw.get('ammo_modifiers', False), raw.get('broken_armour', False)
        if not isinstance(ammo, bool) or not isinstance(broken, bool):
            raise ValueError('Training flags must be boolean')
        model = raw.get('combat_v2', True)
        if not isinstance(model, bool):
            raise ValueError('Training model flag must be boolean')
        return cls(revision, attrs, *values[5:], effect, ammo, broken, model)

    def as_dict(self):
        return asdict(self)

    def values(self):
        return ','.join(format(v, '.15g') for v in self.attributes +
                        (self.health, self.stamina, self.armour, self.spread,
                         self.effect_armour, int(self.ammo_modifiers), int(self.broken_armour), int(self.combat_v2)))

    @classmethod
    def from_values(cls, text):
        if not isinstance(text, str) or len(text) > 256:
            raise ValueError('Invalid training rules payload')
        values = text.split(',')
        if len(values) not in (12, 13) or any(v not in ('0', '1') for v in values[10:]):
            raise ValueError('Twelve training values required')
        numbers = [float(v) for v in values[:10]]
        return cls.parse(dict(revision='session-v1', attributes=numbers[:5],
                              **dict(zip(('health', 'stamina', 'armour', 'spread', 'effect_armour'), numbers[5:])),
                              ammo_modifiers=values[10] == '1', broken_armour=values[11] == '1',
                              combat_v2=len(values) == 13 and values[12] == '1'))

    def weapon(self, weapon, ammo):
        if not self.ammo_modifiers and self.spread == 1:
            return weapon
        damage = ammo.get('dam_mod', 1) if self.ammo_modifiers else 1
        stamina = ammo.get('st_mod', 1) if self.ammo_modifiers else 1
        reach = ammo.get('range_mod', 1) if self.ammo_modifiers else 1
        # Static item data are trusted only after finite/range validation.
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 < v <= 10
               for v in (damage, stamina, reach)):
            raise ValueError('Invalid experimental ammunition modifiers')
        return weapon._replace(dmin=round(weapon.dmin * damage), dmax=round(weapon.dmax * damage),
                               sdmin=round(weapon.sdmin * stamina), sdmax=round(weapon.sdmax * stamina),
                               opt_lo=weapon.opt_lo * reach, opt_hi=weapon.opt_hi * reach,
                               max_range=weapon.max_range * reach, cone=weapon.cone * self.spread / reach)

    def description(self):
        return ('Версия правил: %s. Множители: характеристики %s; HP %g; выносливость %g; '
                'броня %g; разброс %g; добавка брони эффекта %g. '
                'Множители патронов: %s; броня поломанных частей: %s. '
                'Исправленная модель: %s. Изменения действуют только на полигоне. '
                'Множитель 1 не меняет выбранную модель. Предметы имеют отдельные типы и таблицу параметров.') % (
                    self.revision, '/'.join('%g' % v for v in self.attributes),
                    self.health, self.stamina, self.armour, self.spread, self.effect_armour,
                    'включены' if self.ammo_modifiers else 'текущая игра',
                    'учитывается' if self.broken_armour else 'не учитывается',
                    'включена' if self.combat_v2 else 'выключена')

@lru_cache(maxsize=1)
def current():
    return Rules.parse(json.loads(PATH.read_text(encoding='utf-8-sig')))
