"""Project global/local positions and choose declared, escapable entries.

This policy is only for entering a map cell. Quest, door, resurrection and
administrator arrivals keep their own rules. Geometry is cached on the
immutable Location; live occupancy is checked for every arrival.
"""
from collections import deque
from dataclasses import dataclass
import math

import progression
import travel


class NoSafeEntry(ValueError):
    """No declared entry currently has a free path to a real edge exit."""


@dataclass(frozen=True)
class _Geometry:
    candidates: frozenset
    exits: frozenset
    triggers: frozenset


def _valid(loc, cell):
    return isinstance(cell, int) and 0 <= cell < loc.width * loc.height


def _central(loc, cell):
    x, y = cell % loc.width, cell // loc.width
    return ((loc.width - 1) / 4 <= x <= 3 * (loc.width - 1) / 4
            and (loc.height - 1) / 4 <= y <= 3 * (loc.height - 1) / 4)


def _allowed_side(loc, cell, available_sides, declared):
    if _central(loc, cell):
        return cell in declared
    distances = {side: travel._edge_distance(loc, cell, side) for side in travel.SIDES}
    nearest = min(distances.values())
    return all(side in available_sides for side, depth in distances.items() if depth == nearest)


def _reachable(loc, exits, blocked, stop=None):
    """Flood only from actual exits, stopping once all candidates are found."""
    found = set(exits) - blocked
    pending = deque(found)
    wanted = set(stop) - found if stop is not None else None
    while pending and (wanted is None or wanted):
        cell = pending.popleft()
        for neighbour in progression.hex_neighbours(cell, loc.width, loc.height):
            if neighbour not in blocked and neighbour not in found:
                found.add(neighbour)
                pending.append(neighbour)
                if wanted is not None:
                    wanted.discard(neighbour)
    return found


def _geometry(loc):
    cached = getattr(loc, '_global_entry_geometry', None)
    if cached is not None:
        return cached
    if loc.width < 1 or loc.height < 1:
        raise NoSafeEntry('The location has no valid grid')
    all_exits = {cell: side for cell, side in travel.exit_sides(loc).items()
                 if _valid(loc, cell)}
    triggers = frozenset(cell for cells, _record in travel.walk_ins(loc)
                         for cell in cells if _valid(loc, cell))
    blocked = set(loc.obstacles) | triggers
    exits = {cell: side for cell, side in all_exits.items()
             if side in travel.SIDES and cell not in blocked}
    available_sides = set(exits.values())
    declared = set(loc.entries)
    if loc.war:
        declared.update(travel.war_entries(loc))
    pool = set(declared)
    # A file may omit its inzones along an edge. Only the immediate hex
    # inside a real outzone is an allowed substitute, never an arbitrary
    # walkable point in an enclosed yard or behind a building.
    for cell, side in exits.items():
        depth = travel._edge_distance(loc, cell, side)
        pool.update(neighbour for neighbour in progression.hex_neighbours(
            cell, loc.width, loc.height)
            if travel._edge_distance(loc, neighbour, side) > depth)
    candidates = {cell for cell in pool if _valid(loc, cell)
                  and cell not in blocked and cell not in all_exits
                  and _allowed_side(loc, cell, available_sides, declared)}
    reachable = _reachable(loc, exits, blocked, candidates)
    cached = _Geometry(frozenset(candidates & reachable), frozenset(exits), triggers)
    loc._global_entry_geometry = cached
    return cached


def _fraction(value):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise NoSafeEntry('Invalid global-map position') from exc
    if not math.isfinite(number) or number < 0:
        raise NoSafeEntry('Invalid global-map position')
    # DisplayGlobalMap chooses a cell by floor, not by rounding its centre.
    return number - math.floor(number)


def map_position(loc, cell, gx, gy):
    """The local hex's position inside its existing global square.

    choose() uses the same axes and width/height minus one. Map coordinates
    have four integer digits and the wire formats floats with six significant
    digits, so keep hundredths and stay below the next cell even at an edge.
    """
    if not _valid(loc, cell):
        raise NoSafeEntry('Invalid local position')
    _fraction(gx)
    _fraction(gy)
    fx = (cell % loc.width) / (loc.width - 1) if loc.width > 1 else .5
    fy = (cell // loc.width) / (loc.height - 1) if loc.height > 1 else .5
    return (round(math.floor(float(gx)) + min(.99, fx), 2),
            round(math.floor(float(gy)) + min(.99, fy), 2))


def choose(loc, gx, gy, occupied=frozenset()):
    """Return a free entry near the fractional position inside this map cell.

    Every candidate belongs to a component with a real exit and therefore
    has at least one free neighbour. Live NPC/player occupancy may invalidate
    both a candidate and its route; no unsafe cell-zero fallback is used.
    """
    fx, fy = _fraction(gx), _fraction(gy)
    geometry = _geometry(loc)
    occupied = frozenset(cell for cell in occupied if _valid(loc, cell))
    candidates = geometry.candidates - occupied
    if occupied and candidates:
        reachable = _reachable(loc, geometry.exits,
                               set(loc.obstacles) | geometry.triggers | occupied,
                               candidates)
        candidates &= reachable
    if not candidates:
        raise NoSafeEntry('No free entry has a path to an exit')
    width, height = max(1, loc.width - 1), max(1, loc.height - 1)
    return min(candidates, key=lambda cell: (
        (cell % loc.width / width - fx) ** 2 + (cell // loc.width / height - fy) ** 2,
        cell))
