"""Atomic bank transfers and lossless consolidation of heapable items only."""
from collections import namedtuple

import items
import storage

# SQL count is INTEGER on both backends; this is a storage bound, not a stack rule.
MAX_COUNT = 2_147_483_647
MAX_NEW_STACKS = 512
STATE = ('brk', 'max_break_cur', 'ammo_count', 'ammo_type', 'cur_mode', 'use_count')
TransferResult = namedtuple('TransferResult', 'changes bank_weight')


class Refused(ValueError):
    pass


def key(row):
    if row['root'] not in items.HEAPABLE_ROOTS:
        return None
    return (row['type_id'], row['root']) + tuple(row[f] for f in STATE)


def _locked_rows(store, char_id, slot=None):
    """Reserve existing item rows as well as their owner on PostgreSQL.

    SQLite already reserves its writer in storage.atomic. The fixed id
    order also keeps concurrent bank operations' row-lock order consistent.
    """
    sql = 'SELECT * FROM items WHERE char_id = ?'
    args = [char_id]
    if slot is not None:
        sql += ' AND slot = ?'
        args.append(slot)
    sql += ' ORDER BY uniq'
    if storage.using_postgres(store.db):
        sql += ' FOR UPDATE'
    return [dict(row) for row in store.db.execute(sql, args).fetchall()]


def consolidate(store, char_id, bank_slot):
    """Called before the initial bank list; never modifies worn/charged items."""
    with storage.atomic(store.db):
        if not store.lock_quest_character(char_id):
            raise Refused('Персонаж не найден')
        groups, totals, donors = {}, {}, []
        for row in _locked_rows(store, char_id, bank_slot):
            group = key(row)
            if group is None:
                continue
            previous = groups.get(group)
            if previous is not None and previous['count'] + row['count'] <= MAX_COUNT:
                previous['count'] += row['count']
                totals[previous['uniq']] = previous['count']
                donors.append(row['uniq'])
            else:
                groups[group] = row
        # Write each surviving stack once, rather than once for every donor.
        for uniq, count in totals.items():
            store.update_item(uniq, count=count)
        for uniq in donors:
            store.delete_item(uniq)


def _update(store, changes, row, **fields):
    store.update_item(row['uniq'], **fields)
    old = changes.get(row['uniq'], (row, None))[0]
    changes[row['uniq']] = (old, dict(row, **fields))


def transfer(inv, text, count, expected, putting):
    """Return committed changes and bank grams from one locked item snapshot.

    Only touched rows are copied. No second full read or persistent weight
    cache is needed: a transfer changes bank weight by its checked weight.
    """
    import inventory
    source_slot, dest_slot = ((inventory.BAG, inventory.BANK) if putting
                              else (inventory.BANK, inventory.BAG))
    store = inv.store
    with storage.atomic(store.db):
        if not store.lock_quest_character(inv.char_id):
            raise Refused('Персонаж не найден')
        parsed = inventory.parse_oid(text)
        if parsed is None:
            raise Refused('Предмет уже перемещён или недоступен')
        rows = _locked_rows(store, inv.char_id)
        row = None
        bank_weight, carry_weight = 0, 0
        for candidate in rows:
            if candidate['uniq'] == parsed[0]:
                row = candidate
            grams = inventory.weight_of(candidate)
            if candidate['slot'] == inventory.BANK:
                bank_weight += grams
            else:
                carry_weight += grams
        if (row is None or (row['type_id'], row['root']) != parsed[1:]
                or row['slot'] != source_slot or row['uniq'] in inv.locked):
            raise Refused('Предмет уже перемещён или недоступен')
        if row['count'] != expected or not 1 <= count <= expected:
            raise Refused('Количество изменилось; откройте выбор заново')
        group = key(row)
        if group is None and count != 1:
            raise Refused('Этот предмет нельзя разделить')
        weight = inventory.weight_of(dict(row, count=count))
        if putting:
            if bank_weight + weight > inv.bank_max():
                raise Refused('Недостаточно места в хранилище')
        elif carry_weight + weight > inv.carry_limit():
            raise Refused('Превышен переносимый вес')
        changes = {}
        if group is None:
            _update(store, changes, row, slot=dest_slot)
        else:
            limit = MAX_COUNT if putting else int(items.params_of(row['type_id'])['max_count'])
            remaining = count
            for dest in rows:
                if dest['slot'] == dest_slot and key(dest) == group and dest['count'] < limit:
                    n = min(remaining, limit - dest['count'])
                    _update(store, changes, dest, count=dest['count'] + n)
                    remaining -= n
                    if not remaining:
                        break
            fields = {f: row[f] for f in STATE}
            if (remaining + limit - 1) // limit > MAX_NEW_STACKS:
                raise Refused('Выберите меньшую часть стопки')
            reused = False
            while remaining:
                n = min(remaining, limit)
                if count == row['count'] and not reused:
                    _update(store, changes, row, slot=dest_slot, count=n)
                    reused = True
                else:
                    created = store.create_item(inv.char_id, row['type_id'], row['root'],
                                                slot=dest_slot, count=n, **fields)
                    changes[created['uniq']] = (None, created)
                remaining -= n
            if count == row['count']:
                if not reused:
                    store.delete_item(row['uniq'])
                    changes[row['uniq']] = (row, None)
            else:
                _update(store, changes, row, count=row['count'] - count)
        result = TransferResult([changes[u] for u in sorted(changes)],
                                bank_weight + weight if putting else bank_weight - weight)
    return result
