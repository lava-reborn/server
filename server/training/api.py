"""Cheap main-game facade. Disabled sessions import no range implementation."""
from protocol import Str
from training.config import CLIENT_PROTOCOL, ENTRY_QUEST, EXIT_QUEST, SERIAL_BASE, enabled


def compatible(owner):
    return getattr(owner, 'training_protocol', None) == CLIENT_PROTOCOL


def preload():
    if enabled():
        from training import session
        session.preload()


def preload_strings():
    if enabled():
        from training.items import register_sets_and_strings
        register_sets_and_strings()


def entry_available(owner):
    if not enabled() or not compatible(owner):
        return False
    from training.party import entry_available as available
    return available(owner)


def check_entry(owner, params):
    if not enabled() or not compatible(owner):
        raise ValueError('Для полигона требуется совместимая версия клиента')
    from training.session import check_entry as check
    return check(owner, params)


def enter_from_quest(owner):
    from training.session import enter_from_quest as enter
    return enter(owner)


def resume(owner):
    if not enabled() or not compatible(owner):
        return False  # Preserve the checkpoint until a compatible client returns.
    from training.session import resume as restore
    return restore(owner)


def handle(owner, command, params):
    ground = getattr(owner, 'training_ground', None)
    if command == 'tg' and params.get('op') == 'hello' and ground is None:
        version = str(params.get('version', ''))
        owner.training_protocol = CLIENT_PROTOCOL if version == str(CLIENT_PROTOCOL) else None
        owner.send('tg', op='hello', version=CLIENT_PROTOCOL,
                   available=int(enabled() and compatible(owner)))
        return True
    if command != 'tg' and ground is None:
        return False
    if ground is None:
        owner.send('tg', op='error', message=Str('Нет активной тренировки'))
        return True
    if getattr(ground.clone, 'range_disconnecting', False):
        return True
    from training.commands import handle as dispatch
    return dispatch(owner, command, params)


_LIVE = frozenset(('userMsg', 'online', 'tg', 'shutdown', 'kickban', 'p_op', 'p_m',
                   'gg_struct', 'fellow', 'lsml', 'svml'))
_REFRESH = frozenset(('gg_list',))
_AVATAR = frozenset(('userInfo', 'userInfo_Player', 'hp', 'sp', 'c_ap', 'rp_info', 'money',
                     'lcall', 'lenter', 'lch', 'userMove', 'breakMv', 'actionCancel',
                     'ss_obj_move', 'ss_ack', 'ss_upd', 'ss_obj_status', 'medCooldown'))


def outgoing(owner, command, params):
    ground = getattr(owner, 'training_ground', None)
    if ground is None:
        return params
    if command in ('p_op', 'p_m'):
        from training.party import frame
        return frame(ground, command, params)
    if command in _LIVE:
        return params
    permitted_reply = (getattr(owner, 'training_chat', False)
                       or getattr(owner, 'training_party_control', False)
                       or getattr(owner, 'training_clan_read', False)
                       or getattr(owner, 'training_mail_read', False))
    if permitted_reply and command in ('cmdAck', 'gg_list'):
        return params
    if command in _REFRESH:
        ground.deferred_refresh.add(command)
    elif command not in _AVATAR and not command.startswith(('q_di_', 'ss_di_', 'ss_si_')):
        # Bounded diagnostics, not an unbounded queue of stale frames.
        if command not in ground.deferred_events and len(ground.deferred_events) < 32:
            ground.deferred_events.add(command)
            import logging
            logging.getLogger('lava').warning('Deferred main-avatar event during range: %s', command)
    return None


def suspend(owner):
    ground = getattr(owner, 'training_ground', None)
    if ground is not None:
        ground.exit(notify=False, suspend=True)
