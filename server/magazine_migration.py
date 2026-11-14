"""Lazy, atomic conservation of legacy Bizon magazine overflow.

Only entry and inventory reads invoke this; no shot/tick hook or global scan.
Items outside the owner's inventory (auction/mail snapshots) are untouched
until claimed. The excess stays with that owner and in the same storage.
"""
import logging

import inventory
import items
import storage

BIZON_DAMAGE_CLIP_A = 26185
CAPACITY = 100
log = logging.getLogger('lava')


def legacy(row):
    return row['type_id'] == BIZON_DAMAGE_CLIP_A and row['ammo_count'] > CAPACITY


def normalize(store, char_id, rows, locked=()):
    candidates = [r for r in rows if legacy(r) and r['uniq'] not in locked]
    if not candidates:
        return {}, []
    changed, added = {}, []
    with storage.atomic(store.db):
        if not store.lock_quest_character(char_id):
            raise ValueError('Magazine owner disappeared')
        for candidate in candidates:
            row = store.item(candidate['uniq'])
            if row is None or row['char_id'] != char_id or not legacy(row):
                continue
            si = items.params_of(row['type_id']) or {}
            ammo = row['ammo_type']
            if (row['root'] != items.FIRE_ARM or ammo not in si.get('comp_array', [])
                    or items.root_of(ammo) != items.AMMO or row['ammo_count'] > 128):
                # Preserve suspicious data for investigation, without locking
                # the owner out of their character or blocking valid rows.
                log.error('Invalid legacy Bizon magazine uniq=%s char_id=%s; unchanged',
                          row['uniq'], char_id)
                continue
            fields = inventory.new_fields(ammo, row['ammo_count'] - CAPACITY)
            root = fields.pop('root')
            # As with unloading, keep every round even when capacity is
            # exhausted. Ordinary weight/transfer checks still apply; never
            # drop ammunition to make an older inventory fit a new rule.
            fields['slot'] = inventory.BANK if row['slot'] == inventory.BANK else inventory.BAG
            added.append(store.create_item(char_id, ammo, root, **fields))
            store.update_item(row['uniq'], ammo_count=CAPACITY)
            changed[row['uniq']] = dict(row, ammo_count=CAPACITY)
    return changed, added
