"""Main-game integration facade; range internals stay behind this boundary."""
from training import session, commands, party, settings
from training.settings import ENTRY_QUEST, EXIT_QUEST, SERIAL_BASE


def enabled():
    return settings.ENABLED


def preload():
    return session.preload()


def check_entry(owner, params):
    return session.check_entry(owner, params)


def enter_from_quest(owner):
    return session.enter_from_quest(owner)


def resume(owner):
    return session.resume(owner)


def handle(owner, command, params):
    return commands.handle(owner, command, params)


def entry_available(owner):
    return party.entry_available(owner)


_BACKGROUND_EVENTS = frozenset(('userMsg', 'online', 'tg', 'shutdown', 'kickban', 'p_op', 'p_m'))


def outgoing(owner, command, params):
    """Filter real-avatar updates while a private avatar owns the connection.

    Ordinary sessions reuse params unchanged; no allocation or store access.
    """
    ground = getattr(owner, 'training_ground', None)
    if ground is None:
        return params
    chat_or_party_ack = command == 'cmdAck' and (
        getattr(owner, 'training_chat', False) or getattr(owner, 'training_party_control', False))
    clan_reply = command in ('gg_list', 'cmdAck') and getattr(owner, 'training_clan_read', False)
    if command not in _BACKGROUND_EVENTS and not chat_or_party_ack and not clan_reply:
        return None
    if command in ('p_op', 'p_m'):
        return party.frame(ground, command, params)
    return params


def suspend(owner):
    """Checkpoint the private avatar before closing the main connection."""
    ground = getattr(owner, 'training_ground', None)
    if ground is not None:
        ground.exit(notify=False, suspend=True)
