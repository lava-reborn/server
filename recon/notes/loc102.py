import io, re, os
LOC = 102
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/%d.xml" % LOC
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/loc102.txt"
raw = open(P, "rb").read()
try:
    txt = raw.decode("utf-8")
except UnicodeDecodeError:
    txt = raw.decode("cp1251", "replace")
attrs = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<location([^>]*)>", txt).group(1)))
W, H = int(attrs["width"]), int(attrs["height"])

def cells(tag, step):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), txt, re.S)
    if not m or not m.group(1).strip():
        return []
    s = "".join(m.group(1).split())
    return [s[i:i + step] for i in range(0, len(s) - step + 1, step)]

obstacles = {(int(c[0:2], 16), int(c[2:4], 16)) for c in cells("obstacles", 5)}
inz = [(int(c[0:2], 16), int(c[2:4], 16)) for c in cells("inzones", 4)]
mobs_raw = cells("mobs", 8)
mobs = [(int(c[0:2], 16), int(c[2:4], 16), int(c[4:8], 16)) for c in mobs_raw]

# mob type_id -> internal name
names = {}
mp = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/mobs.xml"
mraw = open(mp, "rb").read()
try:
    mtxt = mraw.decode("utf-8")
except UnicodeDecodeError:
    mtxt = mraw.decode("cp1251", "replace")
for m in re.finditer(r'<mob type_id="(\d+)"\s+root_type_id=\s*"(\d+)"\s+name="([^"]*)"(?:\s+resource="([^"]*)")?', mtxt):
    names[int(m.group(1))] = (int(m.group(2)), m.group(3), m.group(4) or "")

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("локация %d: %s  %dx%d  war=%s pvp=%s\n" %
            (LOC, attrs["title"], W, H, attrs.get("war"), attrs.get("pvp")))
    f.write("препятствий: %d, точек входа: %d, спавнов мобов: %d\n\n" %
            (len(obstacles), len(inz), len(mobs)))
    free = [c for c in inz if c not in obstacles]
    f.write("первые свободные точки входа игрока:\n")
    for gx, gy in free[:4]:
        f.write("   gx=%-3d gy=%-3d  pos=%d\n" % (gx, gy, gy * W + gx))
    f.write("\nспавны мобов (тип -> роль, имя ресурса):\n")
    for gx, gy, t in mobs:
        root, nm, res = names.get(t, (-1, "?", ""))
        f.write("   pos=%-6d gx=%-3d gy=%-3d  type=%-6d root=%-2d %-28s res=%s\n"
                % (gy * W + gx, gx, gy, t, root, nm, res))
print("готово")
