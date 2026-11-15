"""Main-avatar resynchronisation; private identities are never replayed."""
def inventory_snapshot(owner, *, full=False):
    import inventory
    return [dict(row) for row in owner.inv.store.db.execute(
        'SELECT %s FROM items WHERE char_id=? AND slot<>?' % ('*' if full else 'uniq,type_id,root,slot'),
        (owner.char_id, inventory.BANK)).fetchall()]


def returned(owner):
    """Refresh authoritative main items after lenter, without unsolicited ss_ack.

    Old bag entries may have been removed by mail/auction while their frames
    were suppressed. Per-item status/DI frames use the native push protocol;
    the normal ss_get request remains responsible for equipment/FIFO replies.
    """
    import inventory
    from protocol import BigUInt
    previous = owner.__dict__.pop('training_inventory_before', ())
    for row in previous:
        owner.send('ss_obj_status', obj=BigUInt(inventory.oid_of(row)), status=0)
    for row in inventory_snapshot(owner, full=True):
        if row['slot'] == inventory.BAG:
            owner.send('ss_obj_status', obj=BigUInt(inventory.oid_of(row)), status=1)
        owner.send(inventory.DI_COMMAND.get(row['root'], 'ss_di_heap'),
                   **inventory.di_params(row, owner.inv.store))
    owner.inv.refresh_gear()
    owner.count_bag()
