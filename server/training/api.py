"""Cheap main-game facade. Disabled sessions import no range implementation."""
from protocol import Str
from training import config
from training.config import CLIENT_PROTOCOL, ENTRY_QUEST, EXIT_QUEST, SERIAL_BASE, enabled
from training.services import install


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
        owner.training_entry_confirmation = compatible(owner) and params.get('entry_confirmation') == 1
        owner.training_types_version = params.get('types_version')
        owner.send('tg', op='hello', version=CLIENT_PROTOCOL,
                   available=int(enabled() and compatible(owner)))
        return True
    if command == 'tg' and params.get('op') == 'entry_reply':
        if config.SHARED_ROOMS and enabled() and compatible(owner) and ground is None:
            from training.entry import reply
            reply(owner, params)
        return True
    if command == 'tg' and params.get('op') in ('types_ack', 'types_request'):
        if ground is not None and compatible(owner):
            from training import type_metadata
            if params['op'] == 'types_ack':
                if params.get('version') == type_metadata.payload()['version']:
                    owner.training_types_version = params['version']
            else:
                import time
                now = time.monotonic()
                if now - getattr(owner, 'training_types_request', -float('inf')) >= 10:
                    owner.training_types_request = now
                    type_metadata.announce(owner, full=True)
                    ground.state()
                    if ground.phase == 'ready':
                        ground.clone.enter_location()
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
    # Avatar frames are never replayed against private identities. Exit reloads
    # the real inventory, wallet and social state from their authoritative stores.
    return None


def suspend(owner):
    ground = getattr(owner, 'training_ground', None)
    if ground is not None:
        ground.exit(notify=False, suspend=True)


def cancel_entry(owner):
    if getattr(owner, 'training_entry', None) is not None:
        from training.entry import cancel
        cancel(owner)



def returned(owner):
    from training.events import returned as refresh
    refresh(owner)
