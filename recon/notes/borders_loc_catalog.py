"""Catalogue all static location XMLs: id, title, fn, size, war/pvp, library.

Prints a TSV of every location whose fn starts with B_ or whose title is
"Skaly" (Cyrillic), plus a summary of how many locations exist overall.
Read-only; touches only the client resource tree.
"""
import os
import re
import sys

BASE = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/'

ATTRS = ('title', 'fn', 'width', 'height', 'war', 'pvp', 'library', 'dir', 'bg')


def head(path):
    with open(path, 'rb') as f:
        raw = f.read(4096)
    txt = raw.decode('utf-8', 'replace')
    m = re.search(r'<location[^>]*>', txt)
    if not m:
        return None
    tag = m.group(0)
    out = {}
    for a in ATTRS:
        mm = re.search(r'\b%s="([^"]*)"' % a, tag)
        out[a] = mm.group(1) if mm else ''
    return out


rows = []
for name in os.listdir(BASE):
    if not name.endswith('.xml'):
        continue
    lid = int(name[:-4])
    h = head(BASE + name)
    if h is None:
        rows.append((lid, {'title': '<no location tag>', 'fn': '', 'width': '',
                           'height': '', 'war': '', 'pvp': '', 'library': '',
                           'dir': '', 'bg': ''}))
        continue
    rows.append((lid, h))

rows.sort()
print('total static locations:', len(rows))

want = sys.argv[1] if len(sys.argv) > 1 else 'B'
print()
print('id\tfn\ttitle\tw\th\twar\tpvp\tlibrary\tdir\tbg\tbytes')
for lid, h in rows:
    isb = h['fn'].startswith('B_')
    isrock = h['title'] == 'Скалы'
    if want == 'B' and not (isb or isrock):
        continue
    size = os.path.getsize(BASE + '%d.xml' % lid)
    print('\t'.join([str(lid), h['fn'], h['title'], h['width'], h['height'],
                     h['war'], h['pvp'], h['library'], h['dir'], h['bg'],
                     str(size)]))

# how many distinct fn prefixes exist overall
from collections import Counter
pref = Counter()
for lid, h in rows:
    fn = h['fn']
    pref[fn.split('_')[0] if fn else '<none>'] += 1
print()
print('fn prefixes:', pref.most_common(25))
