"""Eden's reviewed 62-cell administrative region.

Four original positions are recovered; all other cells reuse existing
map artwork inside the approved screenshot outline. Global travel
stays within this mask; local exits join only adjacent region cells.
"""
import math


CENTER = 267
CELL_TO_LOC = {
    (5858, 1927): 1386,
    (5860, 1927): 1387,
    (5861, 1927): 1388,
    (5862, 1927): 1389,
    (5856, 1928): 1390,
    (5857, 1928): 264,
    (5858, 1928): 1381,
    (5859, 1928): 1382,
    (5860, 1928): 1391,
    (5861, 1928): 1392,
    (5862, 1928): 1393,
    (5863, 1928): 1394,
    (5864, 1928): 1395,
    (5853, 1929): 1396,
    (5854, 1929): 1397,
    (5855, 1929): 1398,
    (5856, 1929): 1399,
    (5857, 1929): 1383,
    (5858, 1929): 267,
    (5859, 1929): 1384,
    (5860, 1929): 1400,
    (5861, 1929): 1401,
    (5862, 1929): 1402,
    (5863, 1929): 1403,
    (5864, 1929): 1404,
    (5865, 1929): 1405,
    (5866, 1929): 1406,
    (5854, 1930): 1407,
    (5855, 1930): 1408,
    (5856, 1930): 1409,
    (5857, 1930): 265,
    (5858, 1930): 1385,
    (5859, 1930): 266,
    (5860, 1930): 1410,
    (5861, 1930): 1411,
    (5862, 1930): 1412,
    (5863, 1930): 1413,
    (5864, 1930): 1414,
    (5865, 1930): 1415,
    (5854, 1931): 1416,
    (5855, 1931): 1417,
    (5856, 1931): 1418,
    (5857, 1931): 1419,
    (5858, 1931): 1420,
    (5859, 1931): 1421,
    (5860, 1931): 1422,
    (5861, 1931): 1423,
    (5862, 1931): 1424,
    (5863, 1931): 1425,
    (5864, 1931): 1426,
    (5854, 1932): 1427,
    (5855, 1932): 1428,
    (5856, 1932): 1429,
    (5857, 1932): 1430,
    (5858, 1932): 1431,
    (5859, 1932): 1432,
    (5860, 1932): 1433,
    (5861, 1932): 1434,
    (5862, 1932): 1435,
    (5863, 1932): 1436,
    (5861, 1933): 1437,
    (5862, 1933): 1438,
}
LOC_TO_CELL = {loc: cell for cell, loc in CELL_TO_LOC.items()}
CENTER_CELL = LOC_TO_CELL[CENTER]
CLEARANCE = 0.02


def _cell(gx, gy):
    try:
        gx, gy = float(gx), float(gy)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(gx) and math.isfinite(gy)):
        return None
    return math.floor(gx), math.floor(gy)


def location_at(gx, gy):
    return CELL_TO_LOC.get(_cell(gx, gy))


def cell_of(loc_id):
    return LOC_TO_CELL.get(loc_id)


def inside_cell(gx, gy):
    return _cell(gx, gy) in CELL_TO_LOC


def inside_map(gx, gy, loc_id=CENTER):
    return inside_cell(gx, gy)


def clamp(gx, gy, loc_id=CENTER):
    """Keep valid district positions; recover invalid points at a local cell."""
    anchor = LOC_TO_CELL.get(loc_id, CENTER_CELL)
    if inside_cell(gx, gy):
        return float(gx), float(gy)
    if _cell(gx, gy) is None:
        return anchor[0] + 0.5, anchor[1] + 0.5
    gx, gy = float(gx), float(gy)
    x, y = anchor
    return (min(max(gx, x), x + 1 - CLEARANCE),
            min(max(gy, y), y + 1 - CLEARANCE))


def walk(gx, gy, dx, dy, loc_id=CENTER):
    """Clip a ray at its first closed grid edge, including concave borders.

    Checking only the destination would allow a long click to cross the
    outside of the district and return inside. Visit every crossed cell;
    diagonal corners require both cardinal neighbours to be open as well.
    """
    gx, gy = clamp(gx, gy, loc_id)
    try:
        dx, dy = float(dx), float(dy)
    except (TypeError, ValueError, OverflowError):
        return gx, gy
    if not (math.isfinite(dx) and math.isfinite(dy)) or not (dx or dy):
        return gx, gy
    x, y = math.floor(gx), math.floor(gy)
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    tx = ((x + 1 - gx) if dx > 0 else (gx - x)) / abs(dx) if dx else math.inf
    ty = ((y + 1 - gy) if dy > 0 else (gy - y)) / abs(dy) if dy else math.inf
    stepx, stepy = (1 / abs(dx) if dx else math.inf), (1 / abs(dy) if dy else math.inf)
    for _ in range(2 * len(CELL_TO_LOC) + 4):
        edge = min(tx, ty)
        if edge > 1:
            return gx + dx, gy + dy
        crossx = tx <= ty or math.isclose(tx, ty, rel_tol=1e-12, abs_tol=0)
        crossy = ty <= tx or math.isclose(tx, ty, rel_tol=1e-12, abs_tol=0)
        nx, ny = x + (sx if crossx else 0), y + (sy if crossy else 0)
        opened = ((nx, ny) in CELL_TO_LOC
                  and (not crossx or not crossy
                       or ((nx, y) in CELL_TO_LOC and (x, ny) in CELL_TO_LOC)))
        if not opened:
            stop = max(0, edge - CLEARANCE / max(abs(dx), abs(dy)))
            return clamp(gx + dx * stop, gy + dy * stop, loc_id)
        x, y = nx, ny
        if crossx:
            tx += stepx
        if crossy:
            ty += stepy
    # A straight ray cannot cross more distinct rows/columns than this
    # finite district contains. Refuse safely if numeric precision fails.
    return gx, gy
