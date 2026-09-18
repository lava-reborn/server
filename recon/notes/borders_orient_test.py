"""Decide the location-grid -> compass mapping from data, not from names.

A location's outzones carry a side code per exit cell: 1 = the x-min edge of
the location grid, 2 = y-min, 3 = x-max, 4 = y-max (that is what the numbers
mean geometrically -- see recon/notes/borders_loc_geom.py output).  Whether code 1 is
WEST or EAST is the open question.

Test: for every settlement cell (gx, gy) whose location is known, look at the
ground the client's own global-map artwork shows in the four neighbouring
cells.  A location that has no exit with code 1 should be the one whose
blocked neighbour sits on whichever side code 1 really is.  Run both
hypotheses and see which one the data prefers.

  hypothesis A (no inversion): 1=W(gx-1) 2=N(gy-1) 3=E(gx+1) 4=S(gy+1)
  hypothesis B (both axes flipped): 1=E 2=S 3=W 4=N

Ground is read from res/globalmap/full exactly as data/build_terrain.py does:
one 256x256 JPEG per 32x32 cells, file ty*256+tx, 8x8 pixels a cell.
"""
import json
import os
import re
from collections import Counter, defaultdict

from PIL import Image

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
STATIC = RES + 'locations/static/'
TILES = RES + 'globalmap/full/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')

GX0, GX1 = 5833, 6305
GY0, GY1 = 1600, 2110

_tile_cache = {}


def tile(tx, ty):
    key = (tx, ty)
    if key not in _tile_cache:
        p = TILES + '%d.jpg' % (ty * 256 + tx)
        if not os.path.exists(p):
            _tile_cache[key] = None
        else:
            _tile_cache[key] = Image.open(p).convert('RGB').load()
    return _tile_cache[key]


def cell_stats(gx, gy):
    """(mean-abs-deviation of luminance, mean r, mean g, mean b) or None."""
    px = tile(gx // 32, gy // 32)
    if px is None:
        return None
    ox, oy = (gx % 32) * 8, (gy % 32) * 8
    lum = []
    rs = gs = bs = 0
    for dy in range(8):
        for dx in range(8):
            r, g, b = px[ox + dx, oy + dy]
            rs += r
            gs += g
            bs += b
            lum.append(0.299 * r + 0.587 * g + 0.114 * b)
    m = sum(lum) / len(lum)
    mad = sum(abs(v - m) for v in lum) / len(lum)
    return mad, rs / 64.0, gs / 64.0, bs / 64.0


_stat_cache = {}


def stats(gx, gy):
    if (gx, gy) not in _stat_cache:
        _stat_cache[(gx, gy)] = cell_stats(gx, gy)
    return _stat_cache[(gx, gy)]


def rough(gx, gy):
    """Roughness smoothed over the 3x3 block, like build_terrain."""
    vals = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            s = stats(gx + dx, gy + dy)
            if s:
                vals.append(s[0])
    return sum(vals) / len(vals) if vals else None


def is_water(gx, gy):
    s = stats(gx, gy)
    return bool(s and s[3] > s[1] + 2.0)


def side_codes(lid):
    p = STATIC + '%d.xml' % lid
    if not os.path.exists(p):
        return None
    s = open(p, encoding='utf-8').read()
    m = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
    if not m:
        return set()
    txt = re.sub(r'\s+', '', m.group(1))
    if len(txt) % 5:
        return None
    return set(txt[i + 4] for i in range(0, len(txt), 5))


HYP = {
    'A no-inversion  1=W 2=N 3=E 4=S': {'1': (-1, 0), '2': (0, -1),
                                        '3': (1, 0), '4': (0, 1)},
    'B both flipped  1=E 2=S 3=W 4=N': {'1': (1, 0), '2': (0, 1),
                                        '3': (-1, 0), '4': (0, -1)},
    'C x flipped     1=E 2=N 3=W 4=S': {'1': (1, 0), '2': (0, -1),
                                        '3': (-1, 0), '4': (0, 1)},
    'D y flipped     1=W 2=S 3=E 4=N': {'1': (-1, 0), '2': (0, 1),
                                        '3': (1, 0), '4': (0, -1)},
}


def main():
    cells = json.load(open(os.path.join(DATA, 'settlements.json')))['cells']
    ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
    cells = dict(cells)
    for k, v in ver.items():
        if v is None:
            cells.pop(k, None)
        else:
            cells[k] = v

    known = []
    for k, lid in sorted(cells.items()):
        gx, gy = (int(v) for v in k.split(','))
        cs = side_codes(lid)
        if cs is None:
            continue
        sides = set(c for c in cs if c in '1234')
        known.append((gx, gy, lid, sides))

    print('settlement cells with a readable location: %d' % len(known))
    part = [t for t in known if len(t[3]) < 4]
    print('of those, locations missing at least one map-edge exit: %d'
          % len(part))
    print()

    # roughness distribution to pick a sane rock threshold
    allr = []
    for gx, gy, lid, sides in known:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                r = rough(gx + dx, gy + dy)
                if r is not None:
                    allr.append(r)
    allr.sort()
    print('roughness quantiles around settlements: '
          'p10=%.1f p50=%.1f p75=%.1f p90=%.1f p95=%.1f' %
          tuple(allr[int(len(allr) * q)] for q in
                (0.10, 0.50, 0.75, 0.90, 0.95)))
    print()

    for name, step in sorted(HYP.items()):
        # For each hypothesis: mean roughness of the neighbour on a side that
        # is CLOSED vs a side that is OPEN, over the partial locations.
        closed, openn = [], []
        closed_water = openn_water = 0
        for gx, gy, lid, sides in part:
            for code, (dx, dy) in step.items():
                nx, ny = gx + dx, gy + dy
                r = rough(nx, ny)
                if r is None:
                    continue
                if code in sides:
                    openn.append(r)
                    openn_water += is_water(nx, ny)
                else:
                    closed.append(r)
                    closed_water += is_water(nx, ny)
        mc = sum(closed) / len(closed) if closed else float('nan')
        mo = sum(openn) / len(openn) if openn else float('nan')
        print('%-34s closed-side neighbour roughness %.2f (n=%d, water %d) | '
              'open-side %.2f (n=%d, water %d) | delta %+.2f'
              % (name, mc, len(closed), closed_water, mo, len(openn),
                 openn_water, mc - mo))
    print()
    print('(a positive delta means: the side with no exit really does face '
          'rougher ground -- the hypothesis fits)')


main()
