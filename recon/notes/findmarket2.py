import io, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/locations.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/market_cell.txt"
# "рынок" preceded by either spelling of чёрный
PAT = re.compile("[Чч][её]рны[йем]")
rows = []
for m in re.finditer(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt):
    x, y, t = int(m.group(1)), int(m.group(2)), m.group(3)
    if PAT.search(t):
        rows.append((x, y, t))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("клеток: %d\n\n" % len(rows))
    for x, y, t in rows:
        clean = re.sub(r"&lt;\s*[Bb][Rr]\s*&gt;", " | ", t)
        f.write("  %5d %5d  %s\n\n" % (x, y, clean[:230]))
print("готово")
