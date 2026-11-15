"""Explicit host dependencies; providers resolve the live manager at call time."""
_parties = _clans = _expects_ack = None


def install(*, parties, clans, expects_ack):
    if not all(callable(value) for value in (parties, clans, expects_ack)):
        raise TypeError('Training host services must be callable')
    global _parties, _clans, _expects_ack
    _parties, _clans, _expects_ack = parties, clans, expects_ack


def parties():
    if _parties is None:
        raise RuntimeError('Training host services were not installed')
    return _parties()


def clans():
    if _clans is None:
        raise RuntimeError('Training host services were not installed')
    return _clans()


def expects_ack(command, params):
    if _expects_ack is None:
        raise RuntimeError('Training host services were not installed')
    return _expects_ack(command, params)
