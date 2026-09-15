import io, os, re, sys
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static"
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/found.txt"
# Cyrillic written as escapes so the shell heredoc cannot mangle it
NEEDLES = [
    "рын",          # рын
    "черн",    # черн
    "Черн",    # Черн
    "чёрн",    # чёрн
    "Чёрн",    # Чёрн
    "базар",  # базар
]
rows = []
for fn in os.listdir(R):
    txt = io.open(os.path.join(R, fn), encoding="cp1251", errors="replace").read(900)
    m = re.search(r"<location([^>]*)>", txt)
    if not m:
        continue
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    t = a.get("title", "")
    if any(n in t for n in NEEDLES):
        rows.append((int(fn.split(".")[0]), t, a.get("width"), a.get("height"),
                     a.get("war"), a.get("pvp")))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("найдено: %d\n" % len(rows))
    for loc, t, w, h, war, pvp in sorted(rows):
        f.write("%-6d %-38s %sx%s  war=%s pvp=%s\n" % (loc, t, w, h, war, pvp))
print("готово")
