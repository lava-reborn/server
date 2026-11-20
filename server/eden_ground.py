"""Durable, visit-bound plantation resources; ordinary ground is unchanged."""
import time
import logging

import eden
import inventory
import items
import storage


RESOURCES = frozenset((eden.GOOD_BANANA, eden.GREEN_BANANA,
                       eden.BAD_BANANA, eden.PALM_LEAF))
LOOT_OWNER = 0
log = logging.getLogger('lava')


def create(store, type_id, char_id, visit, place, cell, expires_at):
    """Called only by a final harvest strike, inside its locked transaction."""
    if type_id not in RESOURCES or place[0] not in eden.LOCATIONS:
        raise ValueError("not a plantation harvest resource/place")
    fields = inventory.new_fields(type_id, 1)
    root = fields.pop('root')
    fields['slot'] = inventory.BAG
    row = store.create_item(LOOT_OWNER, type_id, root, **fields)
    store.lay_down({row['uniq']: expires_at}, place, cell)
    store.db.execute('INSERT INTO eden_ground (uniq, owner_char, visit) VALUES (?, ?, ?)',
                     (row['uniq'], int(char_id), int(visit)))
    return row


def claimable(fighter, row, cell):
    """A manual/legacy drop never becomes valid merely by lying in Eden."""
    sess, store, rc = fighter.sess, fighter.store, fighter.rc
    if (fighter.dead or getattr(sess, 'closed', False)
            or row['type_id'] not in RESOURCES or row['char_id'] != LOOT_OWNER
            or row['root'] != items.root_of(row['type_id']) or row['count'] != 1
            or row['slot'] != inventory.BAG or rc is None
            or sess.room is not rc.room or sess.on_map or not eden.inside(sess.loc)):
        return False
    current = store.db.execute(
        'SELECT g.loc, g.gx, g.gy, g.cell, g.expires_at FROM eden_ground e'
        ' JOIN ground g ON g.uniq=e.uniq JOIN char_eden s ON s.char_id=e.owner_char'
        ' WHERE e.uniq=? AND e.owner_char=? AND e.visit=s.visit',
        (row['uniq'], sess.char_id)).fetchone()
    return bool(current is not None and tuple(current[k] for k in ('loc', 'gx', 'gy')) == rc.place
                and current['cell'] == cell and current['expires_at'] > time.time())


def remember(rc, bag, rows):
    if not eden.inside(rc.room.loc):
        return
    cached = getattr(bag, '_eden_rows', None)
    if cached is None:
        cached = bag._eden_rows = {}
    for row in rows:
        full = rc.store.item(row['uniq'])
        if full is not None and full['type_id'] in RESOURCES:
            cached[full['uniq']] = full


def stage(rc, cell, row, expires):
    """Install committed bag memory before sending any fallible frame."""
    from combat import LootBag
    bag = rc.loot.get(cell)
    fresh = bag is None
    if fresh:
        bag = rc.loot[cell] = LootBag(cell, [])
    if row['uniq'] not in bag.uniqs:
        bag.uniqs.append(row['uniq'])
    bag.until[row['uniq']] = expires
    remember(rc, bag, [row])
    rc.arm_bag(bag)
    return fresh


def visible(fighter, row, cell):
    # Keep unbound legacy rows visible but unclaimable, as before. Hide only
    # genuine harvests assigned to a different worker/visit.
    if row['type_id'] not in RESOURCES:
        return True
    bound = fighter.store.db.execute('SELECT owner_char, visit FROM eden_ground WHERE uniq=?',
                                     (row['uniq'],)).fetchone()
    if bound is None:
        return True
    sentence = eden.assigned(fighter.store, fighter.sess.char_id)
    # Expiry does not change the displayed list before the ordinary expiry
    # callback. Otherwise a stale take-all could move the client's old item
    # on a successful empty transfer while the server rejects its ownership.
    return bool(sentence and bound['owner_char'] == fighter.sess.char_id
                and bound['visit'] == sentence['visit'])


def refresh_bag(rc, bag):
    cached = getattr(bag, '_eden_rows', {})
    gone = [uniq for uniq in tuple(bag.uniqs) if uniq in cached
            and (rc.store.item(uniq) or {}).get('char_id') != LOOT_OWNER]
    if not gone:
        return
    for fighter in rc.fighters():
        if fighter.loot == bag.cell:
            fighter.ran_out += [cached[uniq] for uniq in gone]
    for uniq in gone:
        bag.uniqs.remove(uniq)
        bag.until.pop(uniq, None)
        cached.pop(uniq, None)
    if not bag.uniqs:
        rc.close_bag(bag.cell)


def refresh_rooms(manager):
    """Only after COMMIT: stale windows may never resurrect reclaimed rows."""
    for room in tuple(manager.rooms.values()):
        rc = room.combat
        if rc is not None and eden.inside(room.loc):
            for bag in tuple(rc.loot.values()):
                refresh_bag(rc, bag)


def take(fighter, bag, requested):
    """Commit ownership before the transfer ack; revalidate every local row."""
    sess, store, inv = fighter.sess, fighter.store, fighter.sess.inv
    rows = []
    failure = inventory.RES_REFUSED
    try:
        with storage.atomic(store.db):
            if not store.lock_quest_character(sess.char_id):
                fighter.ack(failure)
                return
            for old in requested:
                row = store.item(old['uniq'])
                if (row is None or row != old or row['uniq'] not in bag.uniqs
                        or row['char_id'] != LOOT_OWNER):
                    fighter.ack(failure)
                    return
                if eden.restricted_item(row['type_id']) and not claimable(fighter, row, bag.cell):
                    fighter.ack(failure)
                    return
                if items.acquisition_blocked(row['type_id']):
                    fighter.ack(failure)
                    return
                rows.append(row)
            if inv.total_weight() + sum(inventory.weight_of(row) for row in rows) > inv.carry_limit():
                fighter.ack(inventory.RES_OVERLOAD)
                return
            store.pick_up([row['uniq'] for row in rows], sess.char_id, inventory.BAG)
            for row in rows:
                store.db.execute('DELETE FROM eden_ground WHERE uniq=?', (row['uniq'],))
    except storage.CommitError:
        inv.close_after_uncertain_commit()
        return
    except Exception:
        log.exception('Eden ground pickup failed for character %s', sess.char_id)
        fighter.ack(failure)
        return
    # Update memory before publication so a failed socket cannot reuse a row.
    for row in rows:
        if row['uniq'] in bag.uniqs:
            bag.uniqs.remove(row['uniq'])
        bag.until.pop(row['uniq'], None)
        getattr(bag, '_eden_rows', {}).pop(row['uniq'], None)
    fighter.ack(inventory.RES_OK)
    for row in fighter.ran_out:
        inv.push_status(row, 0)
    fighter.ran_out = []
    if not bag.uniqs:
        fighter.rc.close_bag(bag.cell)


def withdraw_owned_ground(store, char_id):
    """Withdraw only this worker's unclaimed resources; caller owns the tx."""
    marks = ','.join('?' for _ in RESOURCES)
    rows = store.db.execute(
        'SELECT i.uniq FROM eden_ground e JOIN items i ON i.uniq=e.uniq'
        ' WHERE e.owner_char=? AND i.char_id=? AND i.type_id IN (%s)' % marks,
        (int(char_id), LOOT_OWNER, *sorted(RESOURCES))).fetchall()
    uniqs = [r['uniq'] for r in rows]
    for uniq in uniqs:
        store.db.execute('DELETE FROM ground WHERE uniq=?', (uniq,))
        store.db.execute('DELETE FROM items WHERE uniq=?', (uniq,))
    store.db.execute('DELETE FROM eden_ground WHERE owner_char=?', (int(char_id),))
    return uniqs


def sweep_metadata(store):
    """Explicit orphan cleanup for SQLite and PostgreSQL's FK-free schema."""
    store.db.execute('DELETE FROM eden_ground WHERE uniq NOT IN (SELECT uniq FROM ground)'
                     ' OR uniq NOT IN (SELECT uniq FROM items WHERE char_id=?)', (LOOT_OWNER,))
    store.db.commit()
