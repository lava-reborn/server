"""What does the client's own small-scale world map actually show?

SSEmulator.getGMTURL: the small map is globalmap/client/<y*32+x>.jpg, and
DisplayLandscape.setScale gives it mapScale=1, cellSize=256 -- one pixel per
map cell, 32x32 tiles of 256x256, i.e. the whole 8192x8192 cell world that
the 13-bit x/y fields of a geo id can address (LocIdToCoordinate).

So the picture of the entire world is on disk.  Find where the drawn world
ends: which tiles hold anything at all, and inside them, the bounding box of
non-blank pixels.
"""
import os

from PIL import Image, ImageStat

DIR = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/globalmap/client/'

present = {}
for name in os.listdir(DIR):
    if not name.endswith('.jpg'):
        continue
    n = int(name[:-4])
    tx, ty = n % 32, n // 32
    present[(tx, ty)] = DIR + name

print('client tiles on disk: %d' % len(present))
xs = [t[0] for t in present]
ys = [t[1] for t in present]
print('tile grid: tx %d..%d, ty %d..%d' % (min(xs), max(xs), min(ys), max(ys)))
print('=> cells %d..%d by %d..%d' % (min(xs) * 256, max(xs) * 256 + 255,
                                     min(ys) * 256, max(ys) * 256 + 255))
print()

# Which tiles carry a real picture?  A blank tile is a flat fill.
rows = []
sizes = {}
for (tx, ty), p in sorted(present.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    sizes[(tx, ty)] = os.path.getsize(p)
print('file sizes: min %d, max %d, median %d'
      % (min(sizes.values()), max(sizes.values()),
         sorted(sizes.values())[len(sizes) // 2]))
big = sorted(sizes.items(), key=lambda kv: -kv[1])[:20]
print('largest tiles (tx,ty,bytes):')
for (tx, ty), s in big:
    print('   tx=%2d ty=%2d  %7d  cells x %d..%d y %d..%d'
          % (tx, ty, s, tx * 256, tx * 256 + 255, ty * 256, ty * 256 + 255))
print()

# grid of "has content" by file size
THRESH = 2 * min(sizes.values())
print('map of tiles whose jpeg is bigger than %d bytes (. = flat fill):'
      % THRESH)
print('      ' + ''.join(str(tx % 10) for tx in range(32)))
for ty in range(32):
    line = ''
    for tx in range(32):
        s = sizes.get((tx, ty))
        line += ('#' if s and s > THRESH else ('.' if s else ' '))
    print('ty=%2d %s' % (ty, line))
print()

# bounding box of drawn content inside the interesting tiles
interesting = [k for k, s in sizes.items() if s > THRESH]
print('non-flat tiles: %d' % len(interesting))
gx0 = gy0 = 10 ** 9
gx1 = gy1 = -1
for (tx, ty) in interesting:
    im = Image.open(present[(tx, ty)]).convert('L')
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            if px[x, y] > 24:
                cx, cy = tx * 256 + x, ty * 256 + y
                gx0 = min(gx0, cx)
                gx1 = max(gx1, cx)
                gy0 = min(gy0, cy)
                gy1 = max(gy1, cy)
print('bounding box of pixels brighter than 24: gx %d..%d (%d), gy %d..%d (%d)'
      % (gx0, gx1, gx1 - gx0 + 1, gy0, gy1, gy1 - gy0 + 1))
