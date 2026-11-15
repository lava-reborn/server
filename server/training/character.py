"""Training range: character."""
import inventory
import items
import progression
from training import items as training_items, rules as training_rules
from training.catalog import item_catalogue
from training.settings import CARRY_LIMIT_GRAMS, MAX_ITEMS, MAX_LEVEL
from training.validation import integer


def preset(level=12):
    return dict(skills=[level, level, level, 0, 0], specs=[-1] * progression.SPECS,
                gear={})


def profile_slots(profile):
    hand = iter(inventory.HAND_SLOTS)
    slots = {}
    for type_id in profile['gear']:
        root = items.root_of(type_id)
        if root in (items.FIRE_ARM, items.COLD_ARM):
            slots[type_id] = next(hand, inventory.BAG)
        elif root == items.WEAR:
            slots[type_id] = inventory.HEAD + items.params_of(type_id)['slot_type']
        else:
            slots[type_id] = inventory.BAG
    return slots


def validate_profile(raw, rules=None):
    skills = [integer(x, 0, MAX_LEVEL) for x in raw['skills']]
    specs = [integer(x, -1, progression.SPEC_MAX) for x in raw['specs']]
    if len(specs) == progression.SPECS:
        specs[12:] = [-1] * 3
    if len(skills) != progression.SKILLS or len(specs) != progression.SPECS or max(skills) < 1:
        raise ValueError('Проверьте навыки персонажа')
    gear = {}
    if len(raw['gear']) > MAX_ITEMS:
        raise ValueError('Слишком много предметов')
    worn = set()
    for raw_id, count in raw['gear'].items():
        t = integer(raw_id, 1, 65535)
        if t not in item_catalogue():
            raise ValueError('Предмет недоступен на полигоне')
        if not training_items.available(t, bool(rules and rules.simulator_formulas)):
            raise ValueError('Этот предмет исключён из нового профиля симулятора. Сдайте его или выберите старые правила.')
        root = items.root_of(t)
        n = integer(count, 1, 5000 if root == items.AMMO else 50 if root == items.HEAL else 1)
        slot = inventory.BAG
        if root == items.WEAR:
            slot = inventory.HEAD + items.params_of(t)['slot_type']
        if slot != inventory.BAG:
            if slot in worn:
                raise ValueError('На один слот выбрано несколько вещей')
            worn.add(slot)
        gear[t] = n
    if sum(n if items.root_of(t) == items.HEAL else 1 for t, n in gear.items()) > 256:
        raise ValueError('Слишком много отдельных предметов')
    training_items.prepare(item_catalogue())
    result = dict(skills=skills, specs=specs, gear=gear)
    ch = character(result, rules)
    fields = []
    slots = profile_slots(result)
    for source, n in gear.items():
        t = training_items.copy_type(source, simulator=ch.training_rules.simulator_formulas)
        f = inventory.new_fields(t, n)
        f['type_id'] = t
        f['slot'] = slots[source]
        fields.append(f)
    ch.set_gear(inventory.gear_bonus(fields, ch), inventory.card_repeat(fields))
    if sum(items.params_of(training_items.copy_type(t, simulator=ch.training_rules.simulator_formulas)).get('weight', 0) * n for t, n in gear.items()) > ch.max_weight():
        raise ValueError('Пресет превышает допустимый вес персонажа')
    for row in fields:
        if row['slot'] != inventory.BAG:
            error = inventory.weapon_requirement_error(row, ch)
            if error:
                raise ValueError(error)
    return result


class TrainingCharacter(progression.Character):
    def max_weight(self):
        """Fixed range capacity, shared by UI, movement and inventory checks."""
        return CARRY_LIMIT_GRAMS

    def __init__(self, rules=None):
        super().__init__()
        self.training_rules = rules if rules is not None else training_rules.current()
    def save(self, store):
        if store is not getattr(self, '_training_store', None):
            raise ValueError('Тренировочный персонаж сохраняется только внутри своей сессии')
        return super().save(store)

    def attr(self, i):
        effects = getattr(self, 'training_effects', None)
        extra = effects.bonus['attribs'][i] if effects else 0
        return max(0, round((super().attr(i) + extra) * self.training_rules.attributes[i]))

    @property
    def hp_max(self):
        return max(1, round(super().hp_max * self.training_rules.health))

    @property
    def sp_max(self):
        return max(1, round(super().sp_max * self.training_rules.stamina))

    def set_gear(self, bonus, repeat=(0, 0)):
        # The simulator intentionally retains the source card's set repeat.
        changed = super().set_gear(bonus, (0, 0) if self.training_rules.combat_v2
                                   and not self.training_rules.simulator_formulas else repeat)
        effects = getattr(self, 'training_effects', None)
        if effects:
            for key in ('hp', 'st', 'od', 'cp', 'ce'):
                setattr(self, 'bonus_' + key, getattr(self, 'bonus_' + key) + effects.bonus['sp' if key == 'st' else key])
        return changed

    def gain_xp(self, *args, **kwargs):
        return {'skills': set(), 'specs': set(), 'attribs': set()}


def character(profile, rules=None):
    ch = TrainingCharacter(rules)
    for i, level in enumerate(profile['skills']):
        ch.set_skill(i, level)
    ch.recalc()
    for i, level in enumerate(profile['specs']):
        ch.set_spec(i, level)
    return ch
