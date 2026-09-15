import io, os, re
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static"
hits = []
for fn in os.listdir(R):
    txt = io.open(os.path.join(R, fn), encoding="cp1251", errors="replace").read(900)
    m = re.search(r"<location([^>]*)>", txt)
    if not m:
        continue
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    t = a.get("title", "")
    if "ынок" in t or "ёрн" in t or "черн" in t.lower():
        hits.append((int(fn.split(".")[0]), t, a.get("width"), a.get("height"),
                     a.get("war"), a.get("pvp")))
for loc, t, w, h, war, pvp in sorted(hits):
    print("  %-6s %-34s %sx%s  war=%s pvp=%s" % (loc, t, w, h, war, pvp))
