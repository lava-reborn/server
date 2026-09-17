"""The procedural tiles: what do the desert and deadloc templates allow?

SSEmulator.getLocDescription resolves any cell the server does not name a
static file for: locations/desert/000N.xml with N = ((gx+gy)&3)+1, and
locations/deadloc/K.xml for ids with id>>28 == 4.  Print their header, their
outzone side codes and their obstacle count.
"""
import os
import re

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/'


def report(path):
    s = open(path, encoding='utf-8').read()
    h = dict(re.findall(r'(\w+)="([^"]*)"',
                        re.search(r'<location[^>]*>', s).group(0)))
    out = {}
    for tag, d in (('outzones', 5), ('zones', 4), ('obstacles', 5),
                   ('inzones', 4)):
        m = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), s, re.S)
        b = re.sub(r'\s+', '', m.group(1)) if m else ''
        out[tag] = (len(b) // d if b and len(b) % d == 0 else 0, b)
    codes = {}
    b = out['outzones'][1]
    if b and len(b) % 5 == 0:
        for i in range(0, len(b), 5):
            codes.setdefault(b[i + 4], []).append(
                (int(b[i:i + 2], 16), int(b[i + 2:i + 4], 16)))
    ranges = {}
    for c, pts in sorted(codes.items()):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ranges[c] = (len(pts), min(xs), max(xs), min(ys), max(ys))
    print('%-28s title=%-22r %sx%s war=%s pvp=%s lib=%-10r obstacles=%d '
          'inzones=%d'
          % (os.path.relpath(path, RES), h.get('title'), h.get('width'),
             h.get('height'), h.get('war'), h.get('pvp'), h.get('library'),
             out['obstacles'][0], out['inzones'][0]))
    for c, v in sorted(ranges.items()):
        print('        code %s: n=%-4d x %d..%d  y %d..%d' % (c, v[0], v[1],
                                                              v[2], v[3], v[4]))
    if not ranges:
        print('        no outzones at all')


for sub in ('desert', 'deadloc'):
    d = RES + sub
    print('=== %s ===' % sub)
    for n in sorted(os.listdir(d)):
        if n.endswith('.xml'):
            report(os.path.join(d, n))
    print()
