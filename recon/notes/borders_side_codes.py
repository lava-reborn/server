"""Which outzone side codes each static location carries, and how many cells.

outzones records are 5 hex chars (LDParser.as:46 uses d=5 for obstacles; the
same stride divides every outzones body exactly): xx yy c, where c is the
side code.  Prints one line per location:  id <tab> fn <tab> codes <tab> counts
"""
import os
import re
import sys
from collections import Counter

BASE = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/'


def codes(path):
    s = open(path, encoding='utf-8').read()
    m = re.search(r'<location[^>]*>', s)
    hdr = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0))) if m else {}
    out = {}
    for tag in ('outzones',):
        mm = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), s, re.S)
        if not mm:
            out[tag] = None
            continue
        txt = re.sub(r'\s+', '', mm.group(1))
        if len(txt) % 5:
            out[tag] = 'BADLEN:%d' % len(txt)
            continue
        c = Counter()
        for i in range(0, len(txt), 5):
            c[txt[i + 4]] += 1
        out[tag] = c
    return hdr, out['outzones']


def main():
    rows = []
    for name in sorted(os.listdir(BASE), key=lambda n: int(n[:-4])):
        lid = int(name[:-4])
        hdr, c = codes(BASE + name)
        rows.append((lid, hdr.get('fn', ''), hdr.get('title', ''), c))
    if len(sys.argv) > 1 and sys.argv[1] == '--codehist':
        h = Counter()
        for lid, fn, t, c in rows:
            if isinstance(c, Counter):
                h.update(c.keys())
        print('distinct side codes across all', len(rows), 'files:',
              h.most_common())
        setsh = Counter()
        for lid, fn, t, c in rows:
            if isinstance(c, Counter):
                setsh[''.join(sorted(c.keys()))] += 1
        print('code-set frequency:')
        for k, v in setsh.most_common():
            print('   %-8s %4d' % (k or '<empty>', v))
        return
    for lid, fn, t, c in rows:
        if isinstance(c, Counter):
            cs = ''.join(sorted(c.keys()))
            det = ' '.join('%s:%d' % (k, c[k]) for k in sorted(c))
        else:
            cs, det = str(c), ''
        print('%d\t%s\t%s\t%s\t%s' % (lid, fn, t, cs, det))


main()
