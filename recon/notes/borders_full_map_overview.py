"""An ASCII overview of the detailed global map the client ships.

res/globalmap/full/<gy//32*256 + gx//32>.jpg, 256x256 px per tile, 8x8 px per
map cell (SSEmulator.getGMTURL + DisplayLandscape mapScale=8, cellSize=256).

Prints, over the whole artwork, one character per BLOCK x BLOCK cells:
  ' ' nothing drawn (no tile, or flat black)
  '.' smooth ground
  ':' medium
  '#' rough ground (shaded relief -- mountains)
  '~' water (blue over red)
and marks the rectangle the server currently calls the world
(5833..6305 x 1600..2110) with '|' and '-' along its edges.
"""
import os
import sys

from PIL import Image

DIR = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/globalmap/full/'
BLOCK = int(sys.argv[1]) if len(sys.argv) > 1 else 8

RX0, RX1 = 5833, 6305
RY0, RY1 = 1600, 2110

tiles = {}
for name in os.listdir(DIR):
    if name.endswith('.jpg'):
        n = int(name[:-4])
        tiles[(n % 256, n // 256)] = DIR + name

txs = sorted(set(t[0] for t in tiles))
tys = sorted(set(t[1] for t in tiles))
print('full tiles: %d, tx %d..%d, ty %d..%d' % (len(tiles), min(txs), max(txs),
                                                min(tys), max(tys)))
print('artwork covers cells gx %d..%d, gy %d..%d'
      % (min(txs) * 32, max(txs) * 32 + 31, min(tys) * 32, max(tys) * 32 + 31))
missing = [(tx, ty) for ty in range(min(tys), max(tys) + 1)
           for tx in range(min(txs), max(txs) + 1) if (tx, ty) not in tiles]
extra = [t for t in tiles if not (min(txs) <= t[0] <= max(txs)
                                  and min(tys) <= t[1] <= max(tys))]
print('missing tiles inside that block: %s' % (missing or 'none'))
print('tiles outside it: %s' % (extra or 'none'))
print()

_cache = {}


def px_of(tx, ty):
    if (tx, ty) not in _cache:
        p = tiles.get((tx, ty))
        _cache[(tx, ty)] = Image.open(p).convert('RGB').load() if p else None
        if len(_cache) > 40:
            for k in list(_cache)[:20]:
                if k != (tx, ty):
                    del _cache[k]
    return _cache[(tx, ty)]


def cell(gx, gy):
    px = px_of(gx // 32, gy // 32)
    if px is None:
        return None
    ox, oy = (gx % 32) * 8, (gy % 32) * 8
    lum = []
    r = g = b = 0
    for dy in range(8):
        for dx in range(8):
            pr, pg, pb = px[ox + dx, oy + dy]
            r += pr
            g += pg
            b += pb
            lum.append(0.299 * pr + 0.587 * pg + 0.114 * pb)
    m = sum(lum) / 64.0
    mad = sum(abs(v - m) for v in lum) / 64.0
    return m, mad, r / 64.0, g / 64.0, b / 64.0


GX0, GX1 = min(txs) * 32, max(txs) * 32 + 31
GY0, GY1 = min(tys) * 32, max(tys) * 32 + 31

print('one char per %dx%d cells; left/top label = gx/gy of the block' % (BLOCK, BLOCK))
hdr = '      '
for i, gx in enumerate(range(GX0, GX1 + 1, BLOCK)):
    hdr += str((gx // BLOCK) % 10)
print(hdr)
for gy in range(GY0, GY1 + 1, BLOCK):
    line = ''
    for gx in range(GX0, GX1 + 1, BLOCK):
        vals = []
        for dy in range(BLOCK):
            for dx in range(BLOCK):
                c = cell(gx + dx, gy + dy)
                if c:
                    vals.append(c)
        if not vals:
            line += ' '
            continue
        mad = sum(v[1] for v in vals) / len(vals)
        lum = sum(v[0] for v in vals) / len(vals)
        blue = sum(v[4] for v in vals) / len(vals)
        red = sum(v[2] for v in vals) / len(vals)
        if lum < 8:
            ch = ' '
        elif blue > red + 2:
            ch = '~'
        elif mad >= 26:
            ch = '#'
        elif mad >= 18:
            ch = ':'
        else:
            ch = '.'
        # mark the rectangle edges
        if gx <= RX0 < gx + BLOCK or gx <= RX1 < gx + BLOCK:
            if RY0 - BLOCK < gy <= RY1:
                ch = '|' if ch in '.:' else ch
        if gy <= RY0 < gy + BLOCK or gy <= RY1 < gy + BLOCK:
            if RX0 - BLOCK < gx <= RX1:
                ch = '-' if ch in '.:' else ch
        line += ch
    print('%5d %s' % (gy, line))
