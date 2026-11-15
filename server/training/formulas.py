"""Optional equation engine boundary. No simulator data or formulas live here.

The server-only range offers the original engine. A separately installed
engine must register its implementation before catalogue preparation.
"""
_ENGINE = None


def register(engine):
    global _ENGINE
    if _ENGINE is not None:
        raise ValueError('An additional range engine is already registered')
    _ENGINE = engine


def available():
    return _ENGINE is not None


def engine():
    if _ENGINE is None:
        raise ValueError('Этот профиль правил пока недоступен')
    return _ENGINE


def data():
    return engine().data()


def enabled(actor):
    ground = (getattr(getattr(actor, 'sess', None), 'ground', None)
              or getattr(actor, 'training_ground', None))
    return bool(available() and ground and ground.rules.simulator_formulas)


def disabled_sources():
    return engine().disabled_sources()


def weapon(*args):
    return engine().weapon(*args)


def melee(*args):
    return engine().melee(*args)


def healing_multiplier(character):
    return engine().healing_multiplier(character)


def cooldown_seconds(character):
    return engine().cooldown_seconds(character)


def ranged_critical(*args):
    return engine().ranged_critical(*args)


def critical(*args):
    return engine().critical(*args)


def split(*args, **kwargs):
    return engine().split(*args, **kwargs)


def configure_mob(*args):
    return engine().configure_mob(*args)


def mob_mode(*args):
    return engine().mob_mode(*args)
