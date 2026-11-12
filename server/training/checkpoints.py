"""One durable checkpoint, with a recoverable private staging database.

Private SQLite is a disposable working copy. It commits before the main
checkpoint is attempted. No cross-database atomicity or compensating main
writes are assumed. An uncertain checkpoint closes the private session;
the next login reads the durable record instead of overwriting it.
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
def mutation(ground):
    """Stage rare configuration/issue operations, never movement or combat ticks."""
    if getattr(ground, '_checkpoint_staging', False):
        yield
        return
    snapshot = snapshot_database(ground)
    before = {key: copy.deepcopy(getattr(ground, key)) for key in FIELDS}
    old_character = ground.clone.char
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
        if durable_attempted:
            # The server may have committed even if its reply was lost.
            # Never write an old checkpoint back as a 'compensation'.
            ground.emergency('Не удалось подтвердить сохранение полигона. Перезайдите; основной персонаж сохранён.')
            raise ValueError('Не удалось подтвердить сохранение полигона') from exc
        else:
            try:
                if ground.enemy is not None and ground.enemy is not actors[0]:
                    ground.enemy.combat.cancel_timers()
                    ground.enemy.training_effects.close()
                restore_database(ground, snapshot)
                ground.clone.char = old_character
                ground.enemy, ground.enemy_cache, ground.mob_eid = actors
                ground.phase = old_phase
                for target, saved in zip((ground.room.npcs, ground.room.combat.mobs, ground.room.players), room_state):
                    target.clear()
                    target.update(saved)
                for key, value in before.items():
                    setattr(ground, key, value)
                ground.room.combat.sync_ws()
            except Exception:
                log.exception('Could not recover private staging state for %s', ground.owner.char_id)
                ground.emergency('Не удалось восстановить тренировку. Основной персонаж сохранён.')
        raise
    finally:
        ground._checkpoint_staging = False
        ground._checkpoint_payload = None
        restore_senders()
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
