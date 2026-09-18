"""What actually stands on the edge of the rectangle the server calls the world.

Lists the client's own map tooltips (res/database/locations.xml) and the
recovered settlement cells that sit on or near the four extreme rows and
columns, so one can see whether a ring of rocks could ever have stood there.
"""
import html
import json
import os
import re

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')

txt = open(RES + 'database/locations.xml', encoding='utf-8', errors='replace').read()
tips = []
for m in re.finditer(r'<location\s+x="(\d+)"\s+y="(\d+)"\s+text="([^"]*)"', txt):
    t = html.unescape(html.unescape(m.group(3)))
    t = re.sub(r'<[^>]*>', ' | ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    tips.append((int(m.group(1)), int(m.group(2)), t))
print('tooltips: %d' % len(tips))
xs = [t[0] for t in tips]
ys = [t[1] for t in tips]
print('tooltip extent: gx %d..%d, gy %d..%d' % (min(xs), max(xs), min(ys), max(ys)))

cells = dict(json.load(open(os.path.join(DATA, 'settlements.json')))['cells'])
ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
for k, v in ver.items():
    if v is None:
        cells.pop(k, None)
    else:
        cells[k] = v
sc = [tuple(int(p) for p in k.split(',')) + (v,) for k, v in cells.items()]
print('settlement cells: %d, extent gx %d..%d, gy %d..%d'
      % (len(sc), min(c[0] for c in sc), max(c[0] for c in sc),
         min(c[1] for c in sc), max(c[1] for c in sc)))
print()

GX0, GX1, GY0, GY1 = min(xs), max(xs), min(ys), max(ys)
for label, sel in (
        ('gx == %d (west edge)' % GX0, lambda t: t[0] == GX0),
        ('gx == %d (east edge)' % GX1, lambda t: t[0] == GX1),
        ('gy == %d (north edge)' % GY0, lambda t: t[1] == GY0),
        ('gy == %d (south edge)' % GY1, lambda t: t[1] == GY1)):
    print('--- tooltips on %s ---' % label)
    for t in sorted(filter(sel, tips)):
        print('   %d,%d  %s' % (t[0], t[1], t[2][:110]))
    print()

print('--- how thick is the labelled band at each edge ---')
for name, vals, lo, hi in (('gx', xs, GX0, GX1), ('gy', ys, GY0, GY1)):
    from collections import Counter
    c = Counter(vals)
    near_lo = [(v, c[v]) for v in range(lo, lo + 12) if c.get(v)]
    near_hi = [(v, c[v]) for v in range(hi - 11, hi + 1) if c.get(v)]
    print('%s low  %s' % (name, near_lo))
    print('%s high %s' % (name, near_hi))
print()
print('--- settlement cells within 3 of an edge ---')
for gx, gy, lid in sorted(sc):
    d = min(gx - GX0, GX1 - gx, gy - GY0, GY1 - gy)
    if d <= 3:
        print('   %d,%d  loc %d  (distance to edge %d)' % (gx, gy, lid, d))
