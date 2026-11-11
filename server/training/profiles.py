"""Catalogue of selectable range profiles. UI receives data, not hard-coded branches.

A new engine revision must have a distinct key and Rules selector, a pinned data
snapshot and parity tests. Never repurpose a published key for different equations.
Legacy flag payloads remain readable; the runtime Rules adapter owns dispatch.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import re
import secrets
from protocol import Str, RawList, escape
from training.rules import Rules, simulator_notes


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    rules: Rules
    notes: tuple

@lru_cache(maxsize=1)
def catalogue():
    from training import formulas as training_formulas
    commit = training_formulas.data()['source_commit']
    result = (
        Profile('baseline-v1', 'Исходный профиль', Rules(combat_v2=False, broken_armour=True), (
            'Исходный профиль полигона\n\nПрежний расчёт попаданий, брони и лечения. Дополнительные множители патронов выключены. '
            'Это контрольная модель для сравнения с исправлениями. Предметы остаются отдельными копиями полигона с его таблицами: '
            'профиль не возвращает цены или характеристики предметов основной игры.',)),
        Profile('simulator-' + commit[:7], 'Симулятор: после правок', Rules(ammo_modifiers=True, simulator_formulas=True),
                simulator_notes() + ('Особые предметы\n\nВ снимке симулятора классические излучатели, арбалет и ракетница имеют неполные исходные записи. '
                'Для них сохранены восстановленные параметры полигона. P-варианты без данных симулятора также не заменяются вымышленными A/G-значениями.',)),
    )
    if len({p.key for p in result}) != len(result) or len({selector(p.rules) for p in result}) != len(result):
        raise ValueError('Range profile identifiers and selectors must be unique')
    return result

def selector(rules):
    # Numeric/ammunition overrides do not choose a different equation engine.
    return rules.combat_v2, rules.simulator_formulas

def restore(rules):
    """Retire the intermediate engine without changing gear or numeric tuning."""
    if rules.combat_v2 and not rules.simulator_formulas:
        return replace(rules, combat_v2=False, ammo_modifiers=False,
                       broken_armour=True, revision='baseline-v1')
    return rules


def selected(rules):
    return next(p for p in catalogue() if selector(p.rules) == selector(rules))

def _texts(values):
    # SCDataParser walks through string lists looking for ; and = and does not
    # unescape their entries. Encode these delimiters as well, and decode only
    # these versioned display fields in the range client. Do not change the
    # shared game codec or the stored descriptions/formula identifiers.
    return RawList(escape(v).replace(';', '%3B').replace('=', '%3D').replace('|', '%7C')
                   for v in values)


def payload(rules, personal=(), selected_key=None):
    records = catalogue() + tuple(personal)
    chosen = selected(rules)
    if selected_key:
        chosen = next((p for p in records if p.key == selected_key), chosen)
    elif rules.revision.startswith('user-'):
        chosen = next((p for p in personal if p.key == rules.revision and selector(p.rules) == selector(rules)), chosen)
    notes, offsets, counts = [], [], []
    for profile in records:
        offsets.append(len(notes))
        counts.append(len(profile.notes))
        notes.extend(Str(note) for note in profile.notes)
    return dict(profile_keys=[Str(p.key) for p in records], profile_titles=_texts(p.title for p in records),
                profile_values=[Str(p.rules.values()) for p in records], profile_notes=_texts(notes), profile_text_codec=1,
                profile_offsets=offsets, profile_counts=counts, profile_selected=records.index(chosen),
                profile_personal=[int(p.key.startswith("user-")) for p in records],
                profile_bases=[Str(selected(p.rules).key) for p in records])


def resolve(values, key=None, personal=()):
    rules = restore(Rules.from_values(values))
    profile = selected(rules)
    if key and key.startswith('user-'):
        owned = next((p for p in personal if p.key == key), None)
        if owned is None or selector(owned.rules) != selector(rules):
            raise ValueError('Личный профиль недоступен или его основа изменилась')
        return replace(rules, revision=key)
    if key is not None and key != profile.key:
        raise ValueError('Профиль изменился; заново откройте компьютер и выберите версию.')
    return replace(rules, revision=profile.key)


MAX_PERSONAL = 8


def personal_record(key, title, rules):
    if not isinstance(title, str) or not re.fullmatch(r'[\w .()\-]{1,32}', title.strip()) or not title.strip():
        raise ValueError('Название: 1–32 символа, буквы, цифры, пробел, точка, скобки или дефис')
    if not isinstance(key, str) or not re.fullmatch(r'user-[0-9a-f]{16}', key):
        raise ValueError('Неверный идентификатор личного профиля')
    base = selected(rules)
    return Profile(key, title.strip(), replace(rules, revision=key),
                   ('Личный профиль «%s». Основа: %s.\n%s' % (title.strip(), base.title, rules.description()),))


def dump_personal(records):
    return [dict(key=p.key, title=p.title, base=selected(p.rules).key, values=p.rules.values()) for p in records]


def load_personal(raw):
    if not isinstance(raw, list):
        return ()
    records = []
    for row in raw[:MAX_PERSONAL]:
        try:
            rules = resolve(row['values'], row['base'])
            record = personal_record(row['key'], row['title'], rules)
            if all(p.key != record.key and p.title.casefold() != record.title.casefold() for p in records):
                records.append(record)
        except (ValueError, TypeError, KeyError):
            continue  # A retired engine revision must not silently become a different model.
    return tuple(records)


def manage(ground, operation, params):
    ground.require_player_reset()  # Computer, idle clone, private inventory, no fight.
    old = ground.personal_profiles
    key = str(params.get('key', ''))
    owned = next((p for p in old if p.key == key), None)
    rules_before = ground.rules
    if operation == 'profile_delete':
        if owned is None:
            raise ValueError('Удалять можно только свои сохранённые профили')
        records = tuple(p for p in old if p.key != key)
        if ground.rules.revision == key:
            ground.rules = replace(ground.rules, revision=selected(ground.rules).key)
        chosen = selected(rules_before).key
        message = 'Личный профиль удалён. Уже применённые параметры боя не изменены.'
    elif operation == 'profile_save':
        if key and owned is None:
            raise ValueError('Редактировать можно только свои сохранённые профили')
        if not key and len(old) >= MAX_PERSONAL:
            raise ValueError('Можно сохранить до 8 личных профилей; удалите ненужный')
        rules = resolve(str(params.get('values', '')), params.get('base'))
        record = personal_record(key or 'user-' + secrets.token_hex(8), params.get('name'), rules)
        if any(p.key != record.key and p.title.casefold() == record.title.casefold() for p in old):
            raise ValueError('Профиль с таким названием уже есть')
        records = tuple(record if p.key == key else p for p in old)
        if not key:
            records += (record,)
        chosen = record.key
        message = 'Личный профиль сохранён. Для изменения боя нажмите «Применить правила».'
    else:
        raise ValueError('Неизвестное действие профиля')
    ground.personal_profiles = records
    try:
        ground.save_settings()
    except Exception as exc:
        ground.personal_profiles, ground.rules = old, rules_before
        raise ValueError('Не удалось сохранить личные профили. Прежние данные сохранены; повторите попытку.') from exc
    ground.clone.send('tg', op='profiles', **payload(ground.rules, records, chosen), message=Str(message))
