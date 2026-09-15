import io, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/locations.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
pts = [(int(m.group(1)), int(m.group(2)), m.group(3))
       for m in re.finditer(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt)]
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/glob.txt"
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("точек на глобальной карте: %d\n" % len(pts))
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    f.write("диапазон x: %d..%d   y: %d..%d\n\n" % (min(xs), max(xs), min(ys), max(ys)))
    f.write("ближайшие к 5968x1727 (координаты рынка по вики):\n")
    near = sorted(pts, key=lambda p: (p[0] - 5968) ** 2 + (p[1] - 1727) ** 2)[:6]
    for x, y, t in near:
        f.write("  %5d %5d  %s\n" % (x, y, re.sub(r"\s+", " ", t)[:90]))
print("готово")
