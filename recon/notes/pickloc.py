import io, os, re
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static"
peaceful = []
for fn in sorted(os.listdir(R), key=lambda x: int(x.split(".")[0])):
    txt = io.open(os.path.join(R, fn), encoding="cp1251", errors="replace").read(1200)
    m = re.search(r"<location([^>]*)>", txt)
    if not m:
        continue
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    if a.get("war") == "0":
        peaceful.append((fn, a.get("title", "?"), a.get("width"), a.get("height"), a.get("pvp")))
print("мирных локаций (war=0):", len(peaceful))
for row in peaceful[:15]:
    print("  %-10s %-28s w=%s h=%s pvp=%s" % row)
