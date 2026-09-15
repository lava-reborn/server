import io, re
LOC = 36
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/%d.xml" % LOC
txt = io.open(p, encoding="cp1251", errors="replace").read()
attrs = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<location([^>]*)>", txt).group(1)))
w, h = int(attrs["width"]), int(attrs["height"])
print("локация %d: %s  %dx%d  war=%s pvp=%s" % (LOC, attrs["title"], w, h,
                                                attrs.get("war"), attrs.get("pvp")))

def cells(tag, step):
    m = re.search(r"<%s>(.*?)</%s>" % (tag, tag), txt, re.S)
    if not m or not m.group(1).strip():
        return []
    s = m.group(1).strip()
    out = []
    for i in range(0, len(s) - 3, step):
        gx, gy = int(s[i:i+2], 16), int(s[i+2:i+4], 16)
        out.append((gx, gy))
    return out

inz = cells("inzones", 4)
war = cells("warinzones", 4)
obs = cells("obstacles", 5)
mobs_raw = re.search(r"<mobs>(.*?)</mobs>", txt, re.S)
print("  inzones     : %d точек входа" % len(inz))
print("  warinzones  : %d" % len(war))
print("  obstacles   : %d непроходимых" % len(obs))
if inz:
    blocked = set(obs)
    free = [c for c in inz if c not in blocked]
    print("  свободных точек входа: %d" % len(free))
    for gx, gy in free[:5]:
        print("    gx=%-3d gy=%-3d  pos = %d*%d + %d = %d" % (gx, gy, gy, w, gx, gy * w + gx))
