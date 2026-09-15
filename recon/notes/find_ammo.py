import sys
sys.path.insert(0, "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server")
import items
cat = items.catalogue()
ammo = [(t, n) for t, (r, n) in cat.items() if r == items.AMMO]
print("патронов всего:", len(ammo))
for t, n in sorted(ammo)[:14]:
    print("   %-7d %s" % (t, n))
