"""Training range: geometry."""
import copy
import mobs
import world
from functools import lru_cache
from training.settings import ARENA_HEIGHT, ARENA_WIDTH, FIGHT_START, LOCATIONS, RANGE


def control_cell(location=RANGE):
    return LOCATIONS[location][2]


@lru_cache(maxsize=len(LOCATIONS))
def arena_location(location=RANGE):
    loc = copy.copy(world.location(location))
    if location != 59:
        loc.width, loc.height = ARENA_WIDTH, ARENA_HEIGHT
        loc.obstacles, loc.shoot_over = set(), frozenset()
    else:
        loc.obstacles = set(loc.obstacles)
    loc.entries, loc.spawns = [], []
    loc.war, loc.pvp, loc.newbies = 1, 1, False
    return loc


@lru_cache(maxsize=len(LOCATIONS))
def geometry(location=RANGE):
    loc = arena_location(location)
    free = set(range(loc.width * loc.height)) - loc.obstacles
    boundary = 82 if location == 59 else 100
    arena = {cell for cell in free if cell // loc.width < boundary
             and mobs.hex_distance(cell, LOCATIONS[location][0], loc.width) > 4}
    return frozenset(free - arena), frozenset(arena), 78 * 64 + 32 if location == 59 else FIGHT_START
