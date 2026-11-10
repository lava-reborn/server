"""Cached range presentation: exact model icons and catalogue classification."""
from functools import lru_cache
from pathlib import Path
import re

UPGRADES = {'precision': 'Точность', 'damage': 'Урон', 'shotrange': 'Дальность',
    'aimtime': 'Время прицеливания', 'reloadspeed': 'Перезарядка',
    'shotspeed': 'Скорость стрельбы', 'clipsize': 'Размер обоймы',
    'agility': 'Ловкость', 'perception': 'Восприятие',
    'damage_clipsize': 'Урон и размер обоймы',
    'precision_shotrange': 'Точность и дальность'}


@lru_cache(maxsize=1)
def index():
    import items
    return {raw: source for source, (_root, raw) in items.catalogue().items()}


def model(source):
    import items
    import own_items
    import training_items
    if source in training_items.PROTOTYPES:
        source = training_items.PROTOTYPES[source]['base']
    own = own_items.load().get(source)
    if own is not None:
        source = own['like']
    raw = items.catalogue()[source][1].partition('_mod_')[0]
    return re.sub(r'_(?:gold|pm)$', '', raw)


def upgrade(source):
    import items
    import training_items
    if source in training_items.PROTOTYPES:
        return ''
    raw = items.catalogue()[source][1]
    suffix = raw.partition('_mod_')[2]
    return UPGRADES.get(re.sub(r'_(?:gold|pm)$', '', suffix), '')


def weapon_class(source):
    import items
    import training_items
    if source in training_items.PROTOTYPES:
        source = training_items.PROTOTYPES[source]['base']
    raw = items.catalogue()[source][1]
    for prefix, value in (('machine_gun_', items.MACHINEGUN), ('assault_rifle_', items.ASSAULT),
        ('rifle_', items.RIFLE), ('smg_', items.SMG), ('shotgun_', items.SHOTGUN),
        ('pistols_', items.PISTOL)):
        if raw.startswith(prefix):
            return value
    return items.params_of(source).get('weapon_type', -1)


@lru_cache(maxsize=None)
def icon_source(source):
    import items
    import own_items
    import training_balance
    import world
    import training_items
    if source in training_items.PROTOTYPES:
        return icon_source(training_items.PROTOTYPES[source]['base'])
    root, raw = items.catalogue()[source]
    def exists(candidate):
        return (candidate is not None and items.root_of(candidate) == root
                and (Path(world.RES) / own_items.icon_path(*items.catalogue()[candidate])).is_file())
    if exists(source):
        return source
    own = own_items.load().get(source)
    if own is not None and exists(own['like']):
        return own['like']
    # A modification changes properties, not the identity of the pictured gun.
    stem = model(source)
    line = training_balance.line(source)
    variants = {'A': '', 'P': '_pm', 'G': '_gold'}
    for raw in (stem + variants[line], stem):
        candidate = index().get(raw)
        if exists(candidate):
            return candidate
    raise ValueError('No matching model icon for training item: %s' % source)
