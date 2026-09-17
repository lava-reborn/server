"""How far the recovered terrain map is from what the client's own files say.

Two facts from the client:
  * every cell the server does not name a static file for resolves to
    locations/desert/000N.xml, and all eleven desert templates carry all four
    outzone side codes -- open desert can be left in any direction;
  * a settlement cell's file lists exactly the sides it can be left by.

So a cell the recovered terrain calls rock is a cell that, when entered,
shows open desert with four ways out.  Count how big that disagreement is.
"""
import json
import os
import re

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
STATIC = RES + 'locations/static/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')

t = json.load(open(os.path.join(DATA, 'map_terrain.json')))
b = t['bounds']
GX0, GX1, GY0, GY1 = b['gx0'], b['gx1'], b['gy0'], b['gy1']
rows = t['rows'] if 'rows' in t else t.get('ground') or t.get('map')
if rows is None:
    for k, v in t.items():
        if isinstance(v, list) and v and isinstance(v[0], str):
            rows = v
            break
BLOCKED = '#~'
W = GX1 - GX0 + 1
H = GY1 - GY0 + 1
tot = W * H
rock = sum(1 for r in rows for c in r if c in BLOCKED)
print('terrain rectangle %dx%d = %d cells' % (W, H, tot))
print('cells the recovered terrain blocks: %d (%.2f%%)' % (rock, 100.0 * rock / tot))
from collections import Counter
print('character histogram: %s' % Counter(c for r in rows for c in r).most_common())


def blocked(gx, gy):
    if not (GX0 <= gx <= GX1 and GY0 <= gy <= GY1):
        return None
    return rows[gy - GY0][gx - GX0] in BLOCKED


cells = dict(json.load(open(os.path.join(DATA, 'settlements.json')))['cells'])
ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
for k, v in ver.items():
    if v is None:
        cells.pop(k, None)
    else:
        cells[k] = v

_c = {}


def codes(lid):
    if lid not in _c:
        p = STATIC + '%d.xml' % lid
        s = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
        m = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
        cs = set()
        if m:
            t2 = re.sub(r'\s+', '', m.group(1))
            if len(t2) % 5 == 0:
                cs = set(t2[i + 4] for i in range(0, len(t2), 5))
        _c[lid] = cs
    return _c[lid]


STEP = {'1': (-1, 0), '2': (0, -1), '3': (1, 0), '4': (0, 1)}
NAME = {'1': 'W', '2': 'N', '3': 'E', '4': 'S'}
conflict = []
ok = 0
for k, lid in sorted(cells.items()):
    gx, gy = (int(p) for p in k.split(','))
    for c in sorted(codes(lid) & set('1234')):
        dx, dy = STEP[c]
        bl = blocked(gx + dx, gy + dy)
        if bl is None:
            continue
        if bl:
            conflict.append((gx, gy, lid, NAME[c]))
        else:
            ok += 1
print()
print('settlement exits onto a neighbouring cell: %d open as the file says, '
      '%d contradicted by the terrain map' % (ok, len(conflict)))
for gx, gy, lid, d in conflict:
    print('   %d,%d loc %-5d says you may leave %s -- terrain calls that cell rock'
          % (gx, gy, lid, d))
