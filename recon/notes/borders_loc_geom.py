"""Decode the cell-grid sections of a LAVA location XML.

Encoding (from recon/as-src/lol/core/location/LDParser.as:121 getHexCoord):
  records of `d` hex chars; x = int(s[i:i+2],16), y = int(s[i+2:i+4],16).
  obstacles are parsed with d=5 (LDParser.as:46) -> 5th nibble is extra data.
  zones with the default d=4 (LDParser.as:51).
  inzones / warinzones turn out to be d=4, outzones d=5 (verified by length).

Usage:  loc_geom.py <id> [<id> ...]        full dump + ASCII map
        loc_geom.py --summary <id> ...     one line per file
"""
import re
import sys

BASE = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/'
SECTIONS = ('obstacles', 'zones', 'warinzones', 'inzones', 'outzones')


def load(lid):
    return open(BASE + '%s.xml' % lid, encoding='utf-8').read()


def header(s):
    m = re.search(r'<location[^>]*>', s)
    tag = m.group(0)
    d = dict(re.findall(r'(\w+)="([^"]*)"', tag))
    return d


def body(s, tag):
    m = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), s, re.S)
    if not m:
        return None
    return re.sub(r'\s+', '', m.group(1))


def stride(txt):
    """Pick the record width that divides the string evenly (5 wins ties only
    when 4 does not divide)."""
    if len(txt) == 0:
        return 4, 0
    if len(txt) % 4 == 0 and len(txt) % 5 != 0:
        return 4, len(txt) // 4
    if len(txt) % 5 == 0 and len(txt) % 4 != 0:
        return 5, len(txt) // 5
    return None, None


def decode(txt, d):
    out = []
    for i in range(0, len(txt), d):
        rec = txt[i:i + d]
        x = int(rec[0:2], 16)
        y = int(rec[2:4], 16)
        extra = rec[4:] if d > 4 else ''
        out.append((x, y, extra))
    return out


def parse(lid):
    s = load(lid)
    h = header(s)
    w = int(h.get('width', 64))
    ht = int(h.get('height', 128))
    res = {'id': lid, 'hdr': h, 'w': w, 'h': ht}
    fixed = {'obstacles': 5, 'zones': 4, 'inzones': 4, 'warinzones': 4,
             'outzones': 5}
    for tag in SECTIONS:
        txt = body(s, tag)
        if txt is None:
            res[tag] = None
            continue
        d = fixed[tag]
        auto, n = stride(txt)
        res[tag + '_lenok'] = (len(txt) % d == 0)
        res[tag + '_auto'] = auto
        res[tag] = decode(txt, d)
    return res


def ascii_map(res, cols=None):
    """Render the grid.  One char per cell, rows top (y=0) to bottom."""
    w, h = res['w'], res['h']
    grid = [['.'] * w for _ in range(h)]
    def put(key, ch):
        if not res.get(key):
            return
        for x, y, _ in res[key]:
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = ch
    put('warinzones', 'w')
    put('zones', 'z')
    put('outzones', 'o')   # o overwrites z where both
    put('inzones', 'i')
    put('obstacles', '#')
    lines = []
    for y in range(h):
        lines.append('%3d %s' % (y, ''.join(grid[y])))
    return lines


def compress(res, bx=2, by=4):
    """Downsample for a compact schematic.  Priority per block:
       outzone nibble char (1/2/4/8) > 'I' inzone > '#' all rock >
       '+' some rock > '.' free."""
    w, h = res['w'], res['h']
    obst = set((x, y) for x, y, _ in (res['obstacles'] or []))
    inz = set((x, y) for x, y, _ in (res['inzones'] or []))
    outz = {}
    for x, y, e in (res['outzones'] or []):
        outz[(x, y)] = e
    zon = set((x, y) for x, y, _ in (res['zones'] or []))
    out = []
    for r in range((h + by - 1) // by):
        row = ''
        for c in range((w + bx - 1) // bx):
            cells = [(c * bx + dx, r * by + dy) for dx in range(bx)
                     for dy in range(by)]
            nib = [outz[p] for p in cells if p in outz]
            no = sum(1 for p in cells if p in obst)
            if nib:
                row += sorted(set(nib))[0]
            elif any(p in inz for p in cells):
                row += 'I'
            elif any(p in zon for p in cells):
                row += 'z'
            elif no == len(cells):
                row += '#'
            elif no:
                row += '+'
            else:
                row += '.'
        out.append(row)
    return out


def zone_out_match(res):
    z = set((x, y) for x, y, _ in (res['zones'] or []))
    o = set((x, y) for x, y, _ in (res['outzones'] or []))
    return z == o, len(z - o), len(o - z)


def nibble_regions(res):
    """For every distinct outzone nibble, report its bounding box."""
    from collections import defaultdict
    d = defaultdict(list)
    for x, y, e in (res['outzones'] or []):
        d[e].append((x, y, e))
    return {k: (len(v), bbox(v)) for k, v in sorted(d.items())}


def inzone_regions(res):
    """Group inzone cells into the edge they sit on."""
    from collections import defaultdict
    w, h = res['w'], res['h']
    d = defaultdict(list)
    for x, y, e in (res['inzones'] or []):
        if x <= 3:
            k = 'x-min(W?)'
        elif x >= w - 4:
            k = 'x-max(E?)'
        elif y <= 3:
            k = 'y-min(N?)'
        elif y >= h - 4:
            k = 'y-max(S?)'
        else:
            k = 'interior'
        d[k].append((x, y, e))
    return {k: (len(v), bbox(v)) for k, v in sorted(d.items())}


def bbox(pts):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def edges(pts, w, h, margin=3):
    """Which border(s) of the rectangle a point set touches."""
    e = set()
    for x, y, _ in pts:
        if x <= margin:
            e.add('x-min')
        if x >= w - 1 - margin:
            e.add('x-max')
        if y <= margin:
            e.add('y-min')
        if y >= h - 1 - margin:
            e.add('y-max')
    return sorted(e)


def summary(lid):
    r = parse(lid)
    h = r['hdr']
    parts = ['id=%s' % lid, 'fn=%s' % h.get('fn', '<none>'),
             '%sx%s' % (r['w'], r['h'])]
    for tag in SECTIONS:
        v = r[tag]
        if v is None:
            parts.append('%s=MISSING' % tag)
            continue
        parts.append('%s n=%d bbox=%s' % (tag, len(v), bbox(v)))
    # outzone direction nibbles
    if r['outzones']:
        from collections import Counter
        parts.append('outzone-nibbles=%s' %
                     Counter(e for _, _, e in r['outzones']).most_common())
    if r['obstacles']:
        from collections import Counter
        parts.append('obst-nibbles=%s' %
                     Counter(e for _, _, e in r['obstacles']).most_common(8))
    return '\n  '.join(parts)


if __name__ == '__main__':
    args = sys.argv[1:]
    mode = 'full'
    if args and args[0].startswith('--'):
        mode = args[0][2:]
        args = args[1:]
    for lid in args:
        if mode == 'summary':
            print(summary(lid))
            print()
        else:
            r = parse(lid)
            print('=' * 70)
            print(summary(lid))
            print('  zones==outzones? %s (z\\o=%d, o\\z=%d)' % zone_out_match(r))
            print('  outzone nibble regions: %s' % nibble_regions(r))
            print('  inzone edge groups:     %s' % inzone_regions(r))
            print()
            print('  map 32x32 (digit=outzone nibble, I=inzone, z=zone, '
                  '#=all rock, +=part rock, .=free):')
            for line in compress(r):
                print('   ' + line)
            print()
