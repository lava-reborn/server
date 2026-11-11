"""Paged, read-only catalogue and bounded private-range item operations."""
from dataclasses import dataclass
from functools import lru_cache
import re

import inventory
import items
import names
import storage
from training import display as display
from training import items as copies
from protocol import Str

PAGE_SIZE = 10
# Archive-only entries: keep the registry and copy ids stable across updates.
# They remain inspectable/obtainable, but never mix with functional equipment.
ARCHIVE_SOURCES = frozenset((*range(4329, 4353), 1081, 1535, 1073, 1074))
STATIONS = {
    'weapons': ('weapon',),
    'armoury': ('armour',),
    'supplies': ('ammo', 'pouch'),
    'medical': ('medicine', 'event_medicine'),
    'boosts': ('buff',),
    'specialist': ('special_weapon', 'experimental_weapon'),
    'archive': ('souvenir', 'unsupported', 'legacy'),
}


@dataclass(frozen=True)
class Entry:
    source: int
    category: str
    level: int
    line: str
    name: str
    model: str
    upgrade: str
    weapon_class: int
    search: str


def search_key(text):
    return re.sub(r'[^\w]+', '', text.casefold().replace('ё', 'е'))


@lru_cache(maxsize=2)
def index(simulator=False):
    from training import catalog as ground
    copies.prepare(ground.item_catalogue())
    out = {}
    for source, (category, level, name) in ground.item_catalogue().items():
        root = items.root_of(copies.copy_type(source, simulator=simulator))
        if simulator:
            level = inventory.item_level(copies.copy_type(source, simulator=True))
        # Real zero-level melee collectibles have damage/bonuses and belong
        # with special weapons, not with the discarded souvenir placeholders.
        if source in ARCHIVE_SOURCES:
            category = 'unsupported' if source in (1073, 1074) else 'legacy' if source == 1535 else 'souvenir'
            name += ' · ' + ('Эффект не подключён' if category == 'unsupported' else 'Архив')
        elif category == 'accessory' and root == items.COLD_ARM:
            category = 'special_weapon'
        weapon = root in (items.FIRE_ARM, items.COLD_ARM)
        if root == items.AMMO:
            modifier = names.text(items.STRING_ID_OFFSET + source).partition('$')[2].strip()
            aliases = {'BB': 'ББ', 'EK': 'ЭК', 'SB': 'СБ', 'SHK': 'ШК',
                       'OT': 'ОТ', 'ST': 'СТ', 'KS': 'КС', 'KE': 'КЭ'}
            modifier = aliases.get(modifier, modifier)
            if modifier in aliases.values():
                name = name.rstrip() + ' · ' + modifier
        model = str(source)
        if weapon and source not in copies.PROTOTYPES:
            model = re.sub(r'_(?:gold|pm)$', '', items.catalogue()[source][1].partition('_mod_')[0])
        # Source-only prototypes must not collapse into their artwork donor.
        if source in copies.PROTOTYPES:
            model = str(source)
            category = 'experimental_weapon'
        out[source] = Entry(source, category, level, ground.item_line(source), name,
                            model, display.upgrade(source) if weapon else '',
                            (6 if root == items.COLD_ARM else display.weapon_class(source)) if weapon else -1, search_key(name))
    return out


@lru_cache(maxsize=None)
def sources(station):
    allowed = STATIONS[station]
    return frozenset(t for t, entry in index().items() if entry.category in allowed)


def filtered(station, params, ground=None):
    from training.validation import integer
    level = integer(params.get('level', 0), 0, 20)
    wclass = integer(params.get('wclass', -1), -1, 6)
    line = str(params.get('line', 'all'))
    category = str(params.get('category', 'all'))
    if line not in ('all', 'A', 'P', 'G', 'C'):
        raise ValueError('Неизвестная версия')
    if category != 'all' and category not in STATIONS[station]:
        raise ValueError('Неизвестная категория')
    query = search_key(str(params.get('query', ''))[:48])
    detail = str(params.get('detail', 'all'))
    allowed = detail_sources(station, detail, ground)
    from training import catalog as training
    entries = index(bool(ground and ground.rules.simulator_formulas))
    return [entry for source in sources(station) if (entry := entries[source])
            and (not level or entry.level == level)
            and (wclass < 0 or entry.weapon_class == wclass)
            and (category == 'all' or category == entry.category)
            and (line == 'all' or (source in training.contraband() if line == 'C' else entry.line == line))
            and (allowed is None or source in allowed)
            and query in entry.search]


@lru_cache(maxsize=1)
def ammunition_classes():
    groups = {i: set() for i in range(6)}
    for source, entry in index().items():
        if items.root_of(copies.copy_type(source)) == items.FIRE_ARM:
            params = items.params_of(copies.copy_type(source))
            groups[entry.weapon_class].update(copies.profile_source(t) for t in params.get('comp_array', ()))
    return {key: frozenset(value) for key, value in groups.items()}


def detail_sources(station, detail, ground):
    if detail == 'all':
        return None
    if station == 'supplies' and detail == 'held':
        if ground is None:
            return frozenset()
        row = ground.clone.inv.in_slot(inventory.PRIMARY)
        if row is None or row['root'] != items.FIRE_ARM:
            return frozenset()
        return frozenset(copies.profile_source(t) for t in items.params_of(row['type_id']).get('comp_array', ()))
    return static_detail(station, detail)


@lru_cache(maxsize=48)
def static_detail(station, detail):
    valid = {'weapons': ('base', 'modified'), 'specialist': ('base', 'modified'),
             'armoury': ('head', 'camo', 'body', 'legs', 'feet'),
             'medical': ('battle', 'peace', 'health', 'stamina'),
             'supplies': tuple('w' + str(i) for i in range(6))}
    if detail not in valid.get(station, ()):
        raise ValueError('Неизвестный фильтр')
    if station == 'supplies':
        return ammunition_classes()[int(detail[1:])]
    slots = dict(zip(('head', 'camo', 'body', 'legs', 'feet'), inventory.SET_SLOTS))
    result = set()
    for source in sources(station):
        entry = index()[source]
        params = items.params_of(copies.copy_type(source))
        if station in ('weapons', 'specialist'):
            selected = bool(entry.upgrade) == (detail == 'modified')
        elif station == 'armoury':
            selected = entry.category == 'armour' and params.get('slot_type', -1) + inventory.HEAD == slots[detail]
        else:
            if detail in ('battle', 'peace'):
                selected = items.battle_medicine(source) == (detail == 'battle')
            else:
                hp, sp = params.get('max_h_rest', 0), params.get('max_st_rest', 0)
                selected = hp >= sp if detail == 'health' else sp >= hp
        if selected:
            result.add(source)
    return frozenset(result)


@lru_cache(maxsize=1)
def set_catalogue():
    from training import sets as training_sets
    return {key: row for key, row in training_sets.records().items()
            if not row.get('simulator') and all(t in sources('armoury') for t in row['members'].values())}


def selected_set(ground, source):
    record = set_catalogue().get(source)
    if ground.context != 'armoury' or record is None or not all(
            copies.available(t, ground.rules.simulator_formulas) for t in record['members'].values()):
        raise ValueError('Комплект недоступен у этой стойки')
    return record


def set_list(ground, params):
    from training.validation import integer
    level = integer(params.get('level', 0), 0, 20)
    line = str(params.get('line', 'all'))
    if line not in ('all', 'A', 'P', 'G', 'C'):
        raise ValueError('Неизвестная версия')
    query = search_key(str(params.get('query', ''))[:48])
    rows = [(key, row) for key, row in set_catalogue().items()
            if (line == 'all' or row['variant'] == line)
            and query in search_key(row['name']) and all(copies.available(t, ground.rules.simulator_formulas)
                                                       for t in row['members'].values())]
    available_levels = sorted({row['level'] for _, row in rows if row['level'] > 0})
    if level and level not in available_levels:
        level = 0
    rows = [(key, row) for key, row in rows if not level or row['level'] == level]
    rows.sort(key=lambda r: (r[1]['level'], r[1]['name'], r[0]))
    page = min(integer(params.get('page', 0), 0, 10000), max(0, (len(rows)-1)//PAGE_SIZE))
    selected = rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    ground.clone.send('tg', op='supply_list', context=Str(ground.context), bundle=1,
                      request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                      page=page, total=len(rows), ids=[key for key, _ in selected],
                      available_levels=available_levels, selected_level=level,
                      labels=[Str('%s · %d ур. [%s]' % (row['name'], row['level'], row['variant'])) for _, row in selected])


def model_key(entry):
    return entry.category, entry.model, entry.level, entry.line


def catalogue(ground, params):
    from training.validation import integer
    if params.get('category') == 'set':
        if ground.context != 'armoury':
            raise ValueError('Комплекты доступны у стойки брони')
        return set_list(ground, params)
    level = integer(params.get('level', 0), 0, 20)
    candidates = [e for e in filtered(ground.context, dict(params, level=0), ground)
                  if copies.available(e.source, ground.rules.simulator_formulas)]
    available_levels = sorted({e.level for e in candidates if e.level > 0})
    if level and level not in available_levels:
        level = 0
    rows = (e for e in candidates if not level or e.level == level)
    groups = {}
    for entry in rows:
        key = model_key(entry)
        previous = groups.get(key)
        if previous is None or (bool(entry.upgrade), entry.source) < (bool(previous.upgrade), previous.source):
            groups[key] = entry
    rows = sorted(groups.values(), key=lambda e: (e.level, e.name, e.source))
    page = min(integer(params.get('page', 0), 0, 10000), max(0, (len(rows) - 1) // PAGE_SIZE))
    selected = rows[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    ground.clone.send('tg', op='supply_list', context=Str(ground.context),
                      request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                      page=page, total=len(rows), ids=[e.source for e in selected],
                      available_levels=available_levels, selected_level=level,
                      labels=[Str(e.name + ' [' + e.line + ']') for e in selected])


def variants(ground, params):
    from training.validation import integer
    if integer(params.get('bundle', 0), 0, 1):
        source = integer(params.get('source'), 1, 100000)
        record = selected_set(ground, source)
        members = list(record['members'].values())
        ground.clone.send('tg', op='supply_variants', context=Str(ground.context), bundle=1,
                          request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                          ids=[source] * len(members),
                          types=[copies.copy_type(t, simulator=ground.rules.simulator_formulas) for t in members],
                          labels=[Str(record['name'] + ' · ' + index()[t].name) for t in members],
                          variants=[Str('Часть комплекта %d / %d' % (i + 1, len(members))) for i in range(len(members))],
                          maximum=[1] * len(members))
        return
    source = integer(params.get('source'), 1, 65535)
    if source not in sources(ground.context) or not copies.available(source, ground.rules.simulator_formulas):
        raise ValueError('Предмет недоступен у этой стойки')
    entries = index(ground.rules.simulator_formulas)
    entry = entries[source]
    rows = sorted((entries[t] for t in sources(ground.context)
                   if model_key(entries[t]) == model_key(entry)
                   and copies.available(t, ground.rules.simulator_formulas)),
                  key=lambda e: (bool(e.upgrade), e.upgrade, e.source))
    ground.clone.send('tg', op='supply_variants', context=Str(ground.context),
                      request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                      ids=[e.source for e in rows],
                      types=[copies.copy_type(e.source, simulator=ground.rules.simulator_formulas) for e in rows],
                      labels=[Str(e.name) for e in rows],
                      variants=[Str(e.upgrade or 'Без улучшения') for e in rows],
                      maximum=[maximum(e.source) for e in rows])


def maximum(source):
    target = copies.copy_type(source)
    return min(5000, items.params_of(target).get('max_count', 1)) if items.root_of(target) in items.HEAPABLE_ROOTS else (
        50 if items.root_of(target) == items.HEAL else 1)


def bag(ground, params):
    from training.validation import integer
    rows = [row for row in ground.clone.inv.rows() if row['slot'] == inventory.BAG and copies.is_copy(row['type_id'])]
    page = min(integer(params.get('page', 0), 0, 10000), max(0, (len(rows)-1)//PAGE_SIZE))
    selected = rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    ground.clone.send('tg', op='supply_bag', context=Str(ground.context), page=page, total=len(rows),
                      request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                      ids=[Str(inventory.oid_of(row)) for row in selected],
                      labels=[Str(index()[copies.profile_source(row['type_id'])].name) for row in selected],
                      types=[row['type_id'] for row in selected],
                      maximum=[row['count'] if row['root'] in items.HEAPABLE_ROOTS else 1 for row in selected])


def change(ground, params, returning=False):
    from training.validation import integer
    inv = ground.clone.inv
    seq = integer(params.get('sequence'), 1, 2**31-1)
    if seq <= ground.supply_sequence:
        ground.clone.send('tg', op='supply_done', sequence=seq, message=Str('Запрос уже обработан'))
        return
    count = integer(params.get('count', 1), 1, 5000)
    updates = []
    if returning:
        row = inv.find(params.get('source'))
        if row is None or row['slot'] != inventory.BAG or not copies.is_copy(row['type_id']):
            raise ValueError('Можно сдать только тестовый предмет из своего рюкзака')
        heapable = row['root'] in items.HEAPABLE_ROOTS
        if count > (row['count'] if heapable else 1):
            raise ValueError('Неверное количество')
        left = row['count'] - count if heapable else 0
        with storage.atomic(ground.store.db):
            if left:
                ground.store.update_item(row['uniq'], count=left)
            else:
                ground.store.delete_item(row['uniq'])
        ground.supply_sequence = seq
        if left:
            updates.append((inv.push_di, (ground.store.item(row['uniq']),)))
        else:
            updates.append((inv.push_status, (row, 0)))
    else:
        bundle = integer(params.get('bundle', 0), 0, 1)
        if bundle:
            source = integer(params.get('source'), 1, 100000)
            record = selected_set(ground, source)
            if count != 1:
                raise ValueError('Выберите один комплект')
            # Nested issue operations commit together; never publish a partial set.
            created = []
            with storage.atomic(ground.store.db):
                for member in record['members'].values():
                    created.extend(inv.issue(copies.copy_type(member, simulator=ground.rules.simulator_formulas), 1))
        else:
            source = integer(params.get('source'), 1, 65535)
            if source not in sources(ground.context) or count > maximum(source):
                raise ValueError('Предмет или количество недоступны')
            created = inv.issue(copies.copy_type(source, simulator=ground.rules.simulator_formulas), count)
        ground.supply_sequence = seq
        for row in created:
            updates.append((inv.push_status, (row, 1)))
            updates.append((inv.push_di, (row,)))
    ground.remember_outfit()
    # Announce committed live identities before native item callbacks can run.
    ground.inventory_state()
    for publish, args in updates:
        publish(*args)
    ground.clone.send('tg', op='supply_done', sequence=seq,
                      message=Str('Предмет сдан' if returning else 'Снаряжение получено'))


def handle(ground, op, params):
    if ground.context not in STATIONS:
        raise ValueError('Откройте окно снабжения')
    # Caller verifies token, phase and range; never accept a client-selected store.
    ground.clone.inv.check_post(ground.post_ids[ground.context])
    if op == 'supply_list':
        catalogue(ground, params)
    elif op == 'supply_variants':
        variants(ground, params)
    elif op == 'supply_bag':
        bag(ground, params)
    elif op in ('supply_get', 'supply_return'):
        change(ground, params, returning=op == 'supply_return')
    else:
        raise ValueError('Неизвестное действие снабжения')
