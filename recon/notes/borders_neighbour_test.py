"""Is the location grid mirrored against the world grid?

Pairs of settlement cells that sit side by side on the global map must be
joined: the location on the left needs an exit toward the one on the right
and vice versa.  Each exit carries a side code 1..4 that names an EDGE of the
64x128 location grid (1 = x-min, 2 = y-min, 3 = x-max, 4 = y-max).  Which
compass direction each edge is, is the open question, so try all four
mappings and count how many adjacent settlement pairs each one leaves
unjoined.

A second, sharper statistic: along a shared edge the cells that may be
crossed should line up.  For a west-east pair the rows (y) that carry an exit
on one location's facing edge should overlap the rows on the other's.
"""
import json
import os
import re
from collections import defaultdict

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
STATIC = RES + 'locations/static/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')

_cache = {}


def outzones(lid):
    """{code: [(x, y), ...]} for a static location, or None."""
    if lid in _cache:
        return _cache[lid]
    p = STATIC + '%d.xml' % lid
    r = None
    if os.path.exists(p):
        s = open(p, encoding='utf-8').read()
        m = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
        if m:
            txt = re.sub(r'\s+', '', m.group(1))
            if len(txt) % 5 == 0:
                r = defaultdict(list)
                for i in range(0, len(txt), 5):
                    rec = txt[i:i + 5]
                    r[rec[4]].append((int(rec[0:2], 16), int(rec[2:4], 16)))
    _cache[lid] = r
    return r


def load_cells():
    cells = dict(json.load(open(os.path.join(DATA, 'settlements.json')))['cells'])
    ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
    for k, v in ver.items():
        if v is None:
            cells.pop(k, None)
        else:
            cells[k] = v
    out = {}
    for k, lid in cells.items():
        gx, gy = (int(v) for v in k.split(','))
        out[(gx, gy)] = lid
    return out


# code -> (dx, dy) it leads to on the world map
HYP = {
    'A  1=W 2=N 3=E 4=S (server today)': {'1': (-1, 0), '2': (0, -1),
                                          '3': (1, 0), '4': (0, 1)},
    'B  1=E 2=S 3=W 4=N (180 deg)':      {'1': (1, 0), '2': (0, 1),
                                          '3': (-1, 0), '4': (0, -1)},
    'C  1=E 2=N 3=W 4=S (x mirrored)':   {'1': (1, 0), '2': (0, -1),
                                          '3': (-1, 0), '4': (0, 1)},
    'D  1=W 2=S 3=E 4=N (y mirrored)':   {'1': (-1, 0), '2': (0, 1),
                                          '3': (1, 0), '4': (0, -1)},
}


def main():
    cells = load_cells()
    print('settlement cells: %d' % len(cells))

    pairs = []
    for (gx, gy), lid in sorted(cells.items()):
        for dx, dy in ((1, 0), (0, 1)):
            nb = cells.get((gx + dx, gy + dy))
            if nb is None or nb == lid:
                continue
            pairs.append(((gx, gy), lid, (gx + dx, gy + dy), nb, (dx, dy)))
    print('adjacent pairs of DIFFERENT settlement locations: %d' % len(pairs))

    usable = []
    for a, la, b, lb, step in pairs:
        oa, ob = outzones(la), outzones(lb)
        if oa is None or ob is None:
            continue
        usable.append((a, la, oa, b, lb, ob, step))
    print('pairs where both locations parse: %d' % len(usable))
    print()

    for name in sorted(HYP):
        step2code = {v: k for k, v in HYP[name].items()}
        joined = half = none = 0
        overlap = 0
        rows = 0
        for a, la, oa, b, lb, ob, step in usable:
            ca = step2code[step]                      # a -> b
            cb = step2code[(-step[0], -step[1])]      # b -> a
            ha = ca in oa and len(oa[ca]) > 0
            hb = cb in ob and len(ob[cb]) > 0
            if ha and hb:
                joined += 1
            elif ha or hb:
                half += 1
            else:
                none += 1
            if ha and hb:
                # do the crossing cells line up along the shared edge?
                if step[0]:                 # horizontal move: compare rows y
                    sa = set(y for _, y in oa[ca])
                    sb = set(y for _, y in ob[cb])
                else:                       # vertical move: compare columns x
                    sa = set(x for x, _ in oa[ca])
                    sb = set(x for x, _ in ob[cb])
                inter = len(sa & sb)
                union = len(sa | sb)
                if union:
                    overlap += inter / float(union)
                    rows += 1
        print('%-36s joined %3d | one-sided %3d | unjoined %3d | '
              'mean edge overlap %.3f (n=%d)'
              % (name, joined, half, none,
                 overlap / rows if rows else float('nan'), rows))

    print()
    print('--- the same test restricted to pairs where at least one location '
          'lacks a side ---')
    tight = [t for t in usable
             if len(set(t[2]) & set('1234')) < 4 or len(set(t[5]) & set('1234')) < 4]
    print('such pairs: %d' % len(tight))
    for name in sorted(HYP):
        step2code = {v: k for k, v in HYP[name].items()}
        joined = half = none = 0
        for a, la, oa, b, lb, ob, step in tight:
            ca = step2code[step]
            cb = step2code[(-step[0], -step[1])]
            ha = bool(oa.get(ca))
            hb = bool(ob.get(cb))
            joined += ha and hb
            half += (ha or hb) and not (ha and hb)
            none += not (ha or hb)
        print('%-36s joined %3d | one-sided %3d | unjoined %3d'
              % (name, joined, half, none))


main()
