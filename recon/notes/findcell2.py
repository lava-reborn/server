import io, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/locations.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/cells.txt"
TRANS = "транспорт"      # транспорт
ARMS  = "оружи"                              # оружи
VH    = "Вади"                                    # Вади
rows = []
for m in re.finditer(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt):
    x, y, t = int(m.group(1)), int(m.group(2)), m.group(3)
    if VH in t:
        rows.append((x, y, t, (TRANS in t, ARMS in t)))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("клеток с упоминанием Вади: %d\n\n" % len(rows))
    for x, y, t, flags in rows:
        clean = re.sub(r"&lt;[Bb][Rr]&gt;", " | ", t)
        mark = ("транспорт " if flags[0] else "") + ("оружие" if flags[1] else "")
        f.write("  %5d %5d  [%s]\n     %s\n\n" % (x, y, mark, clean[:250]))
print("готово")
