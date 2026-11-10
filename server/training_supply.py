"""Paged, read-only catalogue and bounded private-range item operations."""
from dataclasses import dataclass
from functools import lru_cache
import re

import inventory
import items
import names
import storage
import training_display as display
import training_items as copies
from protocol import Str

PAGE_SIZE = 10
STATIONS = {
    'weapons': ('weapon',),
    'armoury': ('armour',),
    'supplies': ('ammo', 'pouch'),
    'medical': ('medicine', 'event_medicine'),
    'boosts': ('buff',),
    'specialist': ('special_weapon', 'experimental_weapon'),
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


@lru_cache(maxsize=1)
def index():
    import training_ground as ground
    copies.prepare(ground.item_catalogue())
    out = {}
    for source, (category, level, name) in ground.item_catalogue().items():
        root = items.root_of(copies.copy_type(source))
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
                            (6 if root == items.COLD_ARM else display.weapon_class(source)) if weapon else -1)
    return out


@lru_cache(maxsize=None)
def sources(station):
    allowed = STATIONS[station]
    return frozenset(t for t, entry in index().items() if entry.category in allowed)


def filtered(station, params):
    from training_ground import integer
    level = integer(params.get('level', 0), 0, 20)
    wclass = integer(params.get('wclass', -1), -1, 6)
    line = str(params.get('line', 'all'))
    category = str(params.get('category', 'all'))
    if line not in ('all', 'A', 'P', 'G', 'C'):
        raise ValueError('Неизвестная версия')
    if category != 'all' and category not in STATIONS[station]:
        raise ValueError('Неизвестная категория')
    query = str(params.get('query', '')).strip().casefold()[:48]
    import training_ground as ground
    return [entry for source in sources(station) if (entry := index()[source])
            and (not level or entry.level == level)
            and (wclass < 0 or entry.weapon_class == wclass)
            and (category == 'all' or category == entry.category)
            and (line == 'all' or (source in ground.contraband() if line == 'C' else entry.line == line))
            and query in entry.name.casefold()]


def model_key(entry):
    return entry.category, entry.model, entry.level, entry.line


def catalogue(ground, params):
    from training_ground import integer
    rows = sorted(filtered(ground.context, params), key=lambda e: (e.level, e.name, e.source))
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
                      labels=[Str(e.name + ' [' + e.line + ']') for e in selected])


def variants(ground, params):
    from training_ground import integer
    source = integer(params.get('source'), 1, 65535)
    if source not in sources(ground.context):
        raise ValueError('Предмет недоступен у этой стойки')
    entry = index()[source]
    rows = sorted((index()[t] for t in sources(ground.context)
                   if model_key(index()[t]) == model_key(entry)),
                  key=lambda e: (bool(e.upgrade), e.upgrade, e.source))
    ground.clone.send('tg', op='supply_variants', context=Str(ground.context),
                      request_id=integer(params.get('request_id', 0), 1, 2**31-1),
                      ids=[e.source for e in rows], types=[copies.copy_type(e.source) for e in rows],
                      labels=[Str(e.name) for e in rows],
                      variants=[Str(e.upgrade or 'Без улучшения') for e in rows],
                      maximum=[maximum(e.source) for e in rows])


def maximum(source):
    target = copies.copy_type(source)
    return min(5000, items.params_of(target).get('max_count', 1)) if items.root_of(target) in items.HEAPABLE_ROOTS else (
        50 if items.root_of(target) == items.HEAL else 1)


def bag(ground, params):
    from training_ground import integer
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
    from training_ground import integer
    inv = ground.clone.inv
    seq = integer(params.get('sequence'), 1, 2**31-1)
    if seq <= ground.supply_sequence:
        ground.clone.send('tg', op='supply_done', sequence=seq, message=Str('Запрос уже обработан'))
        return
    count = integer(params.get('count', 1), 1, 5000)
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
            inv.push_di(ground.store.item(row['uniq']))
        else:
            inv.push_status(row, 0)
    else:
        source = integer(params.get('source'), 1, 65535)
        if source not in sources(ground.context) or count > maximum(source):
            raise ValueError('Предмет или количество недоступны')
        created = inv.issue(copies.copy_type(source), count)
        ground.supply_sequence = seq
        for row in created:
            inv.push_status(row, 1)
            inv.push_di(row)
    ground.remember_outfit()
    ground.inventory_state()
    ground.clone.send('tg', op='supply_done', sequence=seq,
                      message=Str('Предмет сдан' if returning else 'Предмет получен бесплатно'))


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
