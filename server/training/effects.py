"""Private effects use the shared timers without touching real accounts."""
import inventory
import items
import progression
import storage
import effects as ordinary_effects
from training import items as training_items
from effects import FIRST, MAX_EFFECTS, ARRAYS, SCALARS, Active, zero
from effects import Effects as BaseEffects


def definitions():
    return {t: value for t, value in ordinary_effects.definitions().items() if not value.get('self_only')}


def definition(type_id):
    return definitions().get(training_items.source_type(type_id))


class Effects(BaseEffects):
    persistent = False
    attribute = 'training_effects'


def activate(fighter, uniq, target, ap_cost, peace_damage=None):
    """Called only after the ordinary action timer completed successfully."""
    fighter.healing = None
    row = fighter.store.item(uniq)
    if (row is None or row['char_id'] != fighter.sess.char_id or row['use_count'] <= 0 or fighter.dead
            or target.dead or not target.present(fighter.rc) or not target.is_player
            or target.sess.room is not fighter.sess.room or fighter.ap < ap_cost
            or target is not fighter and not progression.within_reach(
                fighter.cell, target.cell, fighter.sess.loc.width, fighter.sess.loc.height)):
        fighter.sess.send('actionCancel', release=1)
        return
    source = training_items.source_type(row['type_id'])
    peace = items.no_combat(row['type_id'])
    if (combat_blocked(fighter, peace) or peace and peace_damage is not None and peace_damage != (
            getattr(fighter, 'damage_revision', 0) + getattr(fighter, 'hit_revision', 0),
            getattr(target, 'damage_revision', 0) + getattr(target, 'hit_revision', 0))):
        fighter.sess.send('actionCancel', release=1)
        return
    effect = definition(row['type_id'])
    if effect is None:
        fighter.sess.send('actionCancel', release=1)
        return
    receiver = target.sess.training_effects
    try:
        receiver.check(source)
    except ValueError as reason:
        fighter.sess.send('actionCancel', release=1)
        fighter.sess.answer(str(reason))
        return
    with storage.atomic(fighter.store.db):
        left = row['use_count'] - 1
        if left > 0:
            fighter.store.update_item(uniq, use_count=left)
        else:
            fighter.store.delete_item(uniq)
    fighter.ap -= ap_cost
    receiver.add(source)
    fighter.sess.ground.remember_outfit()
    fighter.sess.ground.inventory_state()
    if left > 0:
        fighter.sess.inv.push_di(fighter.store.item(uniq))
    else:
        fighter.sess.inv.push_status(row, 0)
    fighter.rc.room.broadcast(('heal', dict(id=fighter.eid, target=target.eid,
                                           hp=target.character().vitals()['hcur'],
                                           sp=target.character().vitals()['scur'])))
    fighter.c_ap()


def combat_blocked(fighter, peace):
    import combat
    return combat.Fighter.medicine_blocked(fighter, peace)
