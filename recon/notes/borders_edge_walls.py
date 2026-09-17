"""Do the locations on the rim of the rectangle refuse to let you off it?

If the world really stops at gx 5833..6305 by gy 1600..2110, then a location
standing on the rim must have no exit pointing outward.  Check every
settlement cell: how often is the outward side missing on the rim, compared
with the same side anywhere else.
"""
import json
import os
import re

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
STATIC = RES + 'locations/static/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')

GX0, GX1, GY0, GY1 = 5833, 6305, 1600, 2110
CODE = {'W': '1', 'N': '2', 'E': '3', 'S': '4'}

_c = {}


def info(lid):
    if lid in _c:
        return _c[lid]
    p = STATIC + '%d.xml' % lid
    if not os.path.exists(p):
        _c[lid] = None
        return None
    s = open(p, encoding='utf-8').read()
    h = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r'<location[^>]*>', s).group(0)))
    m = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
    codes = set()
    if m:
        b = re.sub(r'\s+', '', m.group(1))
        if len(b) % 5 == 0:
            codes = set(b[i + 4] for i in range(0, len(b), 5))
    _c[lid] = (h, codes)
    return _c[lid]


cells = dict(json.load(open(os.path.join(DATA, 'settlements.json')))['cells'])
ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
for k, v in ver.items():
    if v is None:
        cells.pop(k, None)
    else:
        cells[k] = v

print('--- every settlement cell on the rim of the rectangle ---')
rim = []
for k, lid in sorted(cells.items(), key=lambda kv: tuple(int(p) for p in kv[0].split(','))):
    gx, gy = (int(p) for p in k.split(','))
    out = []
    if gx == GX0:
        out.append('W')
    if gx == GX1:
        out.append('E')
    if gy == GY0:
        out.append('N')
    if gy == GY1:
        out.append('S')
    if not out:
        continue
    i = info(lid)
    if not i:
        continue
    h, codes = i
    rim.append((gx, gy, lid, out, codes, h))
    print('  %d,%d loc %-5d rim=%s codes=%s  title=%r fn=%r lib=%r pvp=%s war=%s'
          % (gx, gy, lid, ''.join(out), ''.join(sorted(codes)) or '-',
             h.get('title'), h.get('fn'), h.get('library'), h.get('pvp'),
             h.get('war')))
    for d in out:
        print('       outward %s (code %s): %s' %
              (d, CODE[d], 'BLOCKED' if CODE[d] not in codes else 'OPEN'))

print()
print('--- base rate: how often each side is missing over all 262 cells ---')
from collections import Counter
miss = Counter()
tot = 0
for k, lid in cells.items():
    i = info(lid)
    if not i:
        continue
    tot += 1
    for d, c in CODE.items():
        if c not in i[1]:
            miss[d] += 1
print('cells=%d  missing W %d  N %d  E %d  S %d'
      % (tot, miss['W'], miss['N'], miss['E'], miss['S']))

print()
print('--- cells within 2 of the rim, outward side blocked? ---')
for k, lid in sorted(cells.items(), key=lambda kv: tuple(int(p) for p in kv[0].split(','))):
    gx, gy = (int(p) for p in k.split(','))
    d = {'W': gx - GX0, 'E': GX1 - gx, 'N': gy - GY0, 'S': GY1 - gy}
    near = [s for s, v in d.items() if v <= 2]
    if not near:
        continue
    i = info(lid)
    if not i:
        continue
    h, codes = i
    print('  %d,%d loc %-5d  %s  codes=%s  %s'
          % (gx, gy, lid,
             ' '.join('%s=%d' % (s, d[s]) for s in sorted(near)),
             ''.join(sorted(codes)) or '-', h.get('title')))
