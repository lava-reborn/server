import io, os, re
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static"
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/found.txt"
NEEDLES = ["рын", "черн", "Черн",
           "чёрн", "Чёрн",
           "базар"]

def read(path):
    raw = open(path, "rb").read(1200)
    for enc in ("utf-8", "cp1251"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp1251", "replace")

rows, sample = [], None
for fn in os.listdir(R):
    txt = read(os.path.join(R, fn))
    m = re.search(r"<location([^>]*)>", txt)
    if not m:
        continue
    a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    t = a.get("title", "")
    if sample is None:
        sample = (fn, t)
    if any(n in t for n in NEEDLES):
        rows.append((int(fn.split(".")[0]), t, a.get("width"), a.get("height"),
                     a.get("war"), a.get("pvp")))
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("пример названия (%s): %s\n" % sample)
    f.write("найдено: %d\n" % len(rows))
    for loc, t, w, h, war, pvp in sorted(rows):
        f.write("%-6d %-38s %sx%s  war=%s pvp=%s\n" % (loc, t, w, h, war, pvp))
print("готово")
