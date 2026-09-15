import io, re, collections
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/objects.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
rows = [(int(m.group(1)), int(m.group(2)), m.group(3))
        for m in re.finditer(r'<object type_id="(\d+)" root_type_id=\s*"(\d+)" name="([^"]*)"', txt)]
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/series.txt"
SER = re.compile(r"^([a-z_]+?)_(\d+)$")
groups = collections.defaultdict(list)
for t, root, name in rows:
    m = SER.match(name)
    if m:
        groups[(m.group(1), root)].append((int(m.group(2)), t, name))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("пронумерованных серий: %d\n\n" % len(groups))
    for (base, root), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 3 or len(items) > 40:
            continue
        items.sort()
        f.write("%-22s root=%d  %2d шт  type_id: %s\n"
                % (base, root, len(items),
                   ", ".join(str(t) for _n, t, _x in items[:10])))
print("готово")
