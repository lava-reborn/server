import sys
sys.path.insert(0, "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server")
import re, world
L = world.Location(102)
import io
raw = open("/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/102.xml","rb").read()
try: txt = raw.decode("utf-8")
except UnicodeDecodeError: txt = raw.decode("cp1251","replace")
def chunks(tag, step):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), txt, re.S)
    if not m or not m.group(1).strip(): return []
    s = "".join(m.group(1).split())
    return [s[i:i+step] for i in range(0, len(s)-step+1, step)]
cell = lambda c: int(c[2:4],16)*L.width + int(c[0:2],16)
zones = {cell(c) for c in chunks("zones", 4)}
spawn = L.entry_cell()
print("  точка появления:", spawn)
print("  клеток выхода:", len(zones))
print("  появление на клетке выхода:", spawn in zones)
free = [c for c in L.entries if c not in L.obstacles and c not in zones]
print("  входов, не являющихся выходами:", len(free))
if free:
    cx = sum(c % L.width for c,_ in L.spawns)/len(L.spawns)
    cy = sum(c // L.width for c,_ in L.spawns)/len(L.spawns)
    best = min(free, key=lambda c: (c%L.width-cx)**2 + (c//L.width-cy)**2)
    print("  лучший безопасный вход:", best)
