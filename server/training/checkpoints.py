"""One durable checkpoint, with a recoverable private staging database.

Private SQLite is a disposable working copy. It commits before the main
checkpoint is attempted. No cross-database atomicity or compensating main
writes are assumed. An uncertain checkpoint closes the private session;
the next login reads the durable record instead of overwriting it. Only a
CommitError or a lost connection during the durable write is uncertain.
Validation/integrity failures roll back the private staging copy and keep the
visitor connected. No branch writes an old checkpoint as compensation.
"""
from contextlib import contextmanager
import copy
import logging

import storage

log = logging.getLogger('lava')
FIELDS = ('profile', 'opponent', 'rules', 'applied_profile', 'outfit_revision',
          'personal_profiles', 'spawn_point', 'stationary', 'mode', 'mob_type',
          'mob_health', 'mob_damage', 'enemy_healing', 'heal_below', 'heal_count',
          'unavailable_rules', 'unavailable_presets', 'supply_sequence')


def uncertain(exc, db):
    if isinstance(exc, (storage.CommitError, ConnectionError, TimeoutError)):
        return True
    driver = getattr(db, '_psycopg', None)
    return bool(driver and isinstance(exc, (driver.OperationalError, driver.InterfaceError))
                and (db.raw.closed or db.raw.broken))


def snapshot_database(ground):
    snapshot = storage.SqliteDB(':memory:')
    try:
        ground.store.db.raw.backup(snapshot.raw)
        return snapshot
    except BaseException:
        snapshot.close()
        raise


def restore_database(ground, snapshot):
    ground.store.db.raw.rollback()
    snapshot.raw.backup(ground.store.db.raw)


@contextmanager
def mutation(ground, *, database=True):
    """Stage rare configuration/issue operations, never movement or combat ticks."""
    if getattr(ground, '_checkpoint_staging', False):
        yield
        return
    snapshot = snapshot_database(ground) if database else None
    before = {key: copy.deepcopy(getattr(ground, key)) for key in FIELDS}
    old_character = ground.clone.char
    old_effects = ground.clone.training_effects
    active_effects = copy.deepcopy(old_effects.active)
    ap, amax = ground.clone.combat.ap, ground.clone.combat.amax_sent
    deadlines = getattr(ground.store, '_battle_medicine_deadlines', None)
    saved_deadlines = dict(deadlines or {})
    appearance = {key: dict(getattr(ground.clone.inv, key)) for key in ('shown', 'acked')}
    actors = ground.enemy, ground.enemy_cache, ground.mob_eid
    room_state = dict(ground.room.npcs), dict(ground.room.combat.mobs), dict(ground.room.players)
    old_phase = ground.phase
    frames, senders = [], []
    for peer in ground.room.grounds.values():
        clone = peer.clone
        original = clone.send
        own = 'send' in clone.__dict__
        senders.append((clone, original, own))
        clone.send = lambda command, _send=original, _clone=clone, **fields: frames.append((_clone, _send, command, fields))
    ground._checkpoint_staging = True
    ground._checkpoint_payload = None
    durable_attempted = False

    def restore_senders():
        for clone, original, own in senders:
            if own:
                clone.send = original
            else:
                clone.__dict__.pop('send', None)

    try:
        yield
        # All nested private transactions have completed at this point.
        payload = ground._checkpoint_payload
        if payload is not None:
            durable_attempted = True
            ground.owner.inv.store.save_training_profile(ground.owner.char_id, payload)
    except BaseException as exc:
        restore_senders()
        if durable_attempted and uncertain(exc, ground.owner.inv.store.db):
            # The server may have committed even if its reply was lost.
            # Never write an old checkpoint back as a 'compensation'.
            ground.emergency('Не удалось подтвердить сохранение полигона. Перезайдите; основной персонаж сохранён.')
            raise ValueError('Не удалось подтвердить сохранение полигона') from exc
        else:
            try:
                if ground.enemy is not None and ground.enemy is not actors[0]:
                    ground.enemy.combat.cancel_timers()
                    ground.enemy.training_effects.close()
                if snapshot is not None:
                    restore_database(ground, snapshot)
                ground.clone.char = old_character
                effects_changed = (ground.clone.training_effects is not old_effects
                                   or old_effects.active != active_effects)
                if ground.clone.training_effects is not old_effects:
                    ground.clone.training_effects.close()
                if effects_changed:
                    old_effects.close()
                    old_effects.active = active_effects
                ground.clone.training_effects = old_effects
                ground.clone.combat.ap, ground.clone.combat.amax_sent = ap, amax
                current_deadlines = getattr(ground.store, '_battle_medicine_deadlines', None)
                if current_deadlines is not None:
                    current_deadlines.clear()
                    current_deadlines.update(saved_deadlines)
                for key, value in appearance.items():
                    setattr(ground.clone.inv, key, value)
                ground.enemy, ground.enemy_cache, ground.mob_eid = actors
                ground.phase = old_phase
                for target, saved in zip((ground.room.npcs, ground.room.combat.mobs, ground.room.players), room_state):
                    target.clear()
                    target.update(saved)
                for key, value in before.items():
                    setattr(ground, key, value)
                if effects_changed:
                    old_effects.refresh()
                ground.room.combat.sync_ws()
            except Exception:
                log.exception('Could not recover private staging state for %s', ground.owner.char_id)
                ground.emergency('Не удалось восстановить тренировку. Основной персонаж сохранён.')
        if durable_attempted:
            log.exception('Training checkpoint rejected for %s; private state rolled back', ground.owner.char_id)
            raise ValueError('Не удалось сохранить настройки; прежнее состояние сохранено. Повторите попытку.') from exc
        raise
    finally:
        ground._checkpoint_staging = False
        ground._checkpoint_payload = None
        restore_senders()
        if snapshot is not None:
            snapshot.close()
    for clone, send, command, fields in frames:
        if clone.ground.closed:
            continue
        try:
            send(command, **fields)
        except Exception:
            if clone is ground.clone:
                raise
            clone.ground.emergency('Соединение с полигоном прервано. Настройки сохранены.')
