"""Startup-only extra templates; no feature imports or resource loading.

Registration cannot replace an ordinary type or a previously registered id.
The caller owns the lifetime and authorisation of items made from these
templates. Ordinary Inventory refuses their creation.
"""
import copy

_FRAMES = {}
_SOURCES = {}
_EFFECTS = frozenset()


def register(frames, sources, *, catalogue, commands, effects=()):
    """Validate a whole batch before publishing it to the process catalogue."""
    global _EFFECTS
    frames, sources, effects = copy.deepcopy(frames), dict(sources), frozenset(effects)
    if frames.keys() != sources.keys() or not effects <= frames.keys():
        raise ValueError("Additional template metadata does not match its frames")
    if frames.keys() & (catalogue.keys() | _FRAMES.keys()):
        raise ValueError("Additional templates overlap existing types")
    for type_id, source in sources.items():
        if type(type_id) is not int or not 0 < type_id <= 65535:
            raise ValueError("Additional template id is outside the wire range")
        if type(source) is not int or source not in catalogue:
            raise ValueError("Additional template needs an ordinary source type")
        frame = frames[type_id]
        if (not isinstance(frame, (tuple, list)) or len(frame) != 2
                or not isinstance(frame[1], dict)
                or frame[0] != commands[catalogue[source][0]]
                or type(frame[1].get('type')) is not int or frame[1]['type'] != type_id):
            raise ValueError("Additional template frame does not match its type")
    _FRAMES.update(frames)
    _SOURCES.update(sources)
    _EFFECTS |= effects


def contains(type_id):
    return type_id in _SOURCES


def source_type(type_id):
    return _SOURCES.get(type_id, type_id)


def supports_effects(type_id):
    return type_id in _EFFECTS


def static_info(type_id):
    command, params = _FRAMES[type_id]
    return command, copy.deepcopy(params)
