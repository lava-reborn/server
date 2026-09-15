import io, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/locations.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/market_cell.txt"
NEEDLE = "Черный рынок"  # Черный рынок
alt = "черный рынок"
rows = []
for m in re.finditer(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt):
    t = m.group(3)
    if NEEDLE in t or alt in t:
        rows.append((int(m.group(1)), int(m.group(2)), t))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("клеток с упоминанием чёрного рынка: %d\n\n" % len(rows))
    for x, y, t in rows:
        clean = re.sub(r"&lt;[Bb][Rr]&gt;|&lt;br&gt;", " | ", t)
        f.write("  %5d %5d  %s\n\n" % (x, y, clean[:260]))
print("готово")
