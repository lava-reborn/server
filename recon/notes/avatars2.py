import io, os, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/avatars/list.xml"
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/avatars.txt"
txt = open(P, "rb").read().decode("utf-8", "replace")
AV = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/avatars"
PERS = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/personages"
rows = re.findall(r"<a\s+id='([^']*)'\s+sex='([^']*)'\s+buy='([^']*)'", txt)
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("записей в list.xml: %d\n\n" % len(rows))
    f.write("%-9s %-4s %-6s %-6s %-6s %-6s %s\n" %
            ("id", "sex", "buy", "png_0", "png_1", "swf_0", "personages/<id>"))
    for ident, sex, buy in rows:
        f.write("%-9s %-4s %-6s %-6s %-6s %-6s %s\n" % (
            ident, sex, buy,
            os.path.isfile(os.path.join(AV, ident + "_0.png")),
            os.path.isfile(os.path.join(AV, ident + "_1.png")),
            os.path.isfile(os.path.join(AV, ident + "_0.swf")),
            os.path.isdir(os.path.join(PERS, ident))))
print("готово")
