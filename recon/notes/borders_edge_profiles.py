"""Do the rock templates tile seamlessly into a wall?

Each border template opens onto the map through a strip of outzone cells on
one or more of its four edges.  If two templates were meant to stand next to
each other in a wall, the gap in one's edge has to line up with the gap in
the other's facing edge: what is rock at the bottom of the tile above must be
rock at the top of the tile below, or the range would have a seam you could
walk through.

For every template this prints the open run on each of its four outermost
lines, then scores every ordered pair for how well they join.
"""
import re
import sys
from collections import defaultdict

BASE = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/'
CODE_EDGE = {'1': 'W', '2': 'N', '3': 'E', '4': 'S'}


def parse(lid):
    s = open(BASE + '%d.xml' % lid, encoding='utf-8').read()
    m = re.search(r'<location[^>]*>', s)
    hdr = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
    out = defaultdict(list)
    mm = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
    txt = re.sub(r'\s+', '', mm.group(1)) if mm else ''
    for i in range(0, len(txt), 5):
        r = txt[i:i + 5]
        out[r[4]].append((int(r[0:2], 16), int(r[2:4], 16)))
    ob = set()
    mo = re.search(r'<obstacles\b[^>]*>(.*?)</obstacles>', s, re.S)
    t2 = re.sub(r'\s+', '', mo.group(1)) if mo else ''
    for i in range(0, len(t2), 5):
        ob.add((int(t2[i:i + 2], 16), int(t2[i + 2:i + 4], 16)))
    return hdr, out, ob


def runs(vals):
    vals = sorted(set(vals))
    if not vals:
        return []
    out = [[vals[0], vals[0]]]
    for v in vals[1:]:
        if v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return [tuple(r) for r in out]


def profile(lid):
    """{'N': set of open x on the topmost line, 'S': ..., 'W': set of open y,
        'E': ...}  Empty set = that edge is walled."""
    hdr, out, ob = parse(lid)
    p = {}
    w = int(hdr.get('width', 64))
    h = int(hdr.get('height', 128))
    # N: the topmost row that carries code-2 cells
    c = out.get('2', [])
    p['N'] = set(x for x, y in c if y == min((yy for _, yy in c), default=-1))
    c = out.get('4', [])
    p['S'] = set(x for x, y in c if y == max((yy for _, yy in c), default=-1))
    c = out.get('1', [])
    p['W'] = set(y for x, y in c if x == min((xx for xx, _ in c), default=-1))
    c = out.get('3', [])
    p['E'] = set(y for x, y in c if x == max((xx for xx, _ in c), default=-1))
    p['_fn'] = hdr.get('fn', '')
    p['_w'], p['_h'] = w, h
    return p


def jaccard(a, b):
    if not a and not b:
        return None
    return len(a & b) / float(len(a | b))


IDS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 40, 51, 218,
       428, 1298]

if __name__ == '__main__':
    profs = {}
    print('open runs on each outermost line (empty = walled):')
    for lid in IDS:
        p = profile(lid)
        profs[lid] = p
        print('%5d %-24s N=%-22s S=%-22s W=%-22s E=%s'
              % (lid, p['_fn'] or '<no fn>',
                 runs(p['N']), runs(p['S']), runs(p['W']), runs(p['E'])))
    print()
    print('vertical joins  (tile A on top, tile B below): S-edge of A vs '
          'N-edge of B, Jaccard over x')
    for a in IDS:
        row = []
        for b in IDS:
            j = jaccard(profs[a]['S'], profs[b]['N'])
            row.append('  --' if j is None else '%4.2f' % j)
        print('%5d %s' % (a, ' '.join(row)))
    print('      ' + ' '.join('%4d' % b for b in IDS))
    print()
    print('horizontal joins (tile A left, tile B right): E-edge of A vs '
          'W-edge of B, Jaccard over y')
    for a in IDS:
        row = []
        for b in IDS:
            j = jaccard(profs[a]['E'], profs[b]['W'])
            row.append('  --' if j is None else '%4.2f' % j)
        print('%5d %s' % (a, ' '.join(row)))
    print('      ' + ' '.join('%4d' % b for b in IDS))
