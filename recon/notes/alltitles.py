import io, os, re, collections
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static"
out = io.open("/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/titles.txt",
              "w", encoding="utf-8")
rows = []
for fn in os.listdir(R):
    txt = io.open(os.path.join(R, fn), encoding="cp1251", errors="replace").read(900)
    m = re.search(r"<location([^>]*)>", txt)
    if not m:
        continue
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    rows.append((int(fn.split(".")[0]), a.get("title", ""), a.get("width"),
                 a.get("height"), a.get("war"), a.get("pvp")))
out.write("всего локаций: %d\n" % len(rows))
names = collections.Counter(r[1] for r in rows)
out.write("уникальных названий: %d\n\n" % len(names))
for t, n in names.most_common():
    out.write("%4d  %s\n" % (n, t))
out.close()
print("ok")
