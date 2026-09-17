"""Where the client's own map labels put mountains.

res/database/locations.xml is the only surviving per-cell data the client
carries: 414 captions the global map shows on hover.  Some of them name rock:
"Предгорья", "Скалы", "Горы", "Ущелье", "Перевал", "Хребет", "Каньон".
Print every such caption with its cell, then a picture of where they fall
inside the rectangle.
"""
import html
import json
import os
import re

RES = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/'
HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(HERE, 'data')
STATIC = RES + 'locations/static/'

WORDS = ('предгор', 'скал', 'гор', 'ущел', 'перевал', 'хреб', 'каньон',
         'утес', 'утёс', 'кряж', 'массив', 'плато', 'обрыв')

txt = open(RES + 'database/locations.xml', encoding='utf-8', errors='replace').read()
tips = []
for m in re.finditer(r'<location\s+x="(\d+)"\s+y="(\d+)"\s+text="([^"]*)"', txt):
    t = html.unescape(html.unescape(m.group(3)))
    t = re.sub(r'<[^>]*>', ' | ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    tips.append((int(m.group(1)), int(m.group(2)), t))

cells = dict(json.load(open(os.path.join(DATA, 'settlements.json')))['cells'])
ver = json.load(open(os.path.join(DATA, 'settlements_verified.json')))['cells']
for k, v in ver.items():
    if v is None:
        cells.pop(k, None)
    else:
        cells[k] = v


def loc_info(lid):
    p = STATIC + '%d.xml' % lid
    if not os.path.exists(p):
        return ''
    s = open(p, encoding='utf-8').read()
    m = re.search(r'<location[^>]*>', s)
    h = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
    mm = re.search(r'<outzones\b[^>]*>(.*?)</outzones>', s, re.S)
    codes = ''
    if mm:
        b = re.sub(r'\s+', '', mm.group(1))
        if len(b) % 5 == 0:
            codes = ''.join(sorted(set(b[i + 4] for i in range(0, len(b), 5))))
    return 'title=%r fn=%r lib=%r war=%s codes=%s' % (
        h.get('title'), h.get('fn'), h.get('library'), h.get('war'), codes)


hits = []
for gx, gy, t in sorted(tips):
    low = t.lower().replace('ё', 'е')
    if any(w.replace('ё', 'е') in low for w in WORDS):
        hits.append((gx, gy, t))

print('captions naming rock: %d of %d' % (len(hits), len(tips)))
for gx, gy, t in hits:
    lid = cells.get('%d,%d' % (gx, gy))
    print('  %d,%d  %-60s' % (gx, gy, t[:60]))
    if lid is not None:
        print('        -> settlement guess loc %d  %s' % (lid, loc_info(lid)))
print()

GX0, GX1, GY0, GY1 = 5833, 6305, 1600, 2110
B = 8
print('rock captions (R) and all other captions (.) over the rectangle, '
      'one char per %dx%d cells:' % (B, B))
grid = {}
for gx, gy, t in tips:
    key = ((gx - GX0) // B, (gy - GY0) // B)
    grid.setdefault(key, set()).add('.')
for gx, gy, t in hits:
    grid.setdefault(((gx - GX0) // B, (gy - GY0) // B), set()).add('R')
W = (GX1 - GX0) // B + 1
H = (GY1 - GY0) // B + 1
for r in range(H):
    line = ''
    for c in range(W):
        s = grid.get((c, r), set())
        line += 'R' if 'R' in s else ('.' if s else ' ')
    print('%5d %s' % (GY0 + r * B, line))
