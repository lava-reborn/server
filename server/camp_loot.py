"""One ordinary A-armour roll for a camp creature, using released native sets.

This slot replaces ordinary legacy A-set drops. Personal quest items and
native G drops are handled separately by the caller. Imports of the world
and mob catalogues are delayed because mobs imports this module at startup.
"""
from functools import lru_cache
import math


BASE_CHANCE = .01
MAX_MULTIPLIER = 3.75
MAX_SET_LEVEL = 16
NORTHERN_BASE = 263
ECHO_LEVEL = 16
CENTRES = frozenset((34, 80, 81, 84, 85, 88, 92, 93, 98, 132, 168, 263))
SIDES = {80: 82, 81: 83, 84: 86, 85: 87, 88: 89, 92: 90,
         93: 91, 98: 99, 132: 133, 263: 274}
# Native non-composite human models omit <body type="man"> in their XML.
# In particular, every DSR patriot would otherwise miss the new loot slot.
LEGACY_HUMAN_MODELS = frozenset(('patriot', 'm7', 'bich', 'm8_broken', 'band_leader',
                                 'q1-2', '120', '136', '82', 'berber'))


@lru_cache(maxsize=1)
def _camp_locations():
    import world
    locations = {camp: camp for camp in CENTRES}
    locations.update({side: camp for camp, side in SIDES.items()})
    for loc_id, rows in world.placements().items():
        camps = {row['patrol'] for row in rows if row.get('patrol') in CENTRES}
        # Do not guess which camp owns an ambiguous patrol location.
        if len(camps) == 1:
            locations.setdefault(loc_id, next(iter(camps)))
    return locations


def camp_for(loc_id, ambush_camp=None):
    """Recognise centres, sides, marked patrols and actual global encounters.

    An encounter's room.ambush carries the camp ID. It is accepted only for
    packed global locations, so a static warehouse or private room cannot
    become a camp merely by carrying that optional attribute.
    """
    import world
    camp = _camp_locations().get(loc_id)
    if camp is not None:
        return camp
    if (loc_id is not None and loc_id >= world.NEW_ID_LIMIT
            and ambush_camp in CENTRES):
        return ambush_camp
    return None


@lru_cache(maxsize=1)
def _active_sets():
    import item_templates
    import items
    import sets
    records = []
    for record in sets.records():
        if record['variant'] != 'A' or not 0 < record['level'] <= MAX_SET_LEVEL:
            continue
        members = record['members']
        if set(members) != set(sets.SLOTS):
            continue
        if all(not item_templates.contains(t) and not items.own(t)
               and items.root_of(t) == items.WEAR
               and not items.out_of_game(t) and not items.acquisition_blocked(t)
               for t in members.values()):
            records.append(record)
    return tuple(sorted(records, key=lambda record: record['level']))


def is_humanoid(stats):
    """Native human models, including old records without a body attribute."""
    import mobs
    source = mobs.TYPES.get(str(stats.type_id), {})
    body = source.get('body')
    return body == 'man' or (body is None and source.get('resource') in LEGACY_HUMAN_MODELS)


def eligible_set(stats, loc_id, ambush_camp=None):
    """Nearest released A set at or below this humanoid camp mob's level."""
    camp = camp_for(loc_id, ambush_camp)
    if camp is None or getattr(stats, 'role', None) not in ('mob', 'boss'):
        return None
    if not getattr(stats, 'can_attack', False) or not is_humanoid(stats):
        return None
    eligible = (record for record in _active_sets()
                if record['level'] <= stats.level
                and (record['level'] != ECHO_LEVEL or camp == NORTHERN_BASE))
    return max(eligible, key=lambda record: record['level'], default=None)


def piece_types(stats, loc_id, ambush_camp=None):
    """Five equip slots, in native set order; also used by exact loot reports."""
    import sets
    record = eligible_set(stats, loc_id, ambush_camp)
    return tuple(record['members'][slot] for slot in sets.SLOTS) if record else ()


def is_afro_set_piece(type_id):
    """Include unreleased/upper tiers when suppressing legacy ordinary drops."""
    import item_templates
    import sets
    return sets.variant_of(item_templates.source_type(type_id)) == 'A'


def without_armour(drops):
    """Remove ordinary A-set parts; leave G, belts and non-set items intact."""
    return [(type_id, count) for type_id, count in drops
            if not is_afro_set_piece(type_id)]


def drop_chance(multiplier=1):
    """Apply the existing gap/scanner factor once, within its current ceiling."""
    if not math.isfinite(multiplier):
        return 0
    return BASE_CHANCE * min(MAX_MULTIPLIER, max(0, multiplier))


def roll(stats, rng, *, loc_id=None, ambush_camp=None, multiplier=1, protected=()):
    """At most one part per corpse; an existing personal quest part wins."""
    if any(count > 0 and is_afro_set_piece(type_id) for type_id, count in protected):
        return []
    chance = drop_chance(multiplier)
    if chance <= 0:
        return []
    parts = piece_types(stats, loc_id, ambush_camp)
    if not parts or rng.random() >= chance:
        return []
    return [(rng.choice(parts), 1)]
