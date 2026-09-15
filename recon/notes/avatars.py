import io, os, re
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/avatars/list.xml"
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/avatars.txt"
raw = open(P, "rb").read()
try:
    txt = raw.decode("utf-8")
except UnicodeDecodeError:
    txt = raw.decode("cp1251", "replace")
AV = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/avatars"
PERS = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/personages"
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("--- начало list.xml ---\n")
    f.write(txt[:600] + "\n\n")
    rows = re.findall(r"<(\w+)\s+([^>]*?)/?>", txt)
    f.write("узлы с атрибутами id/sex/buy:\n")
    n = 0
    for tag, at in rows:
        a = dict(re.findall(r'(\w+)="([^"]*)"', at))
        if "id" not in a:
            continue
        n += 1
        ident = a["id"]
        has_png0 = os.path.isfile(os.path.join(AV, ident + "_0.png"))
        has_png1 = os.path.isfile(os.path.join(AV, ident + "_1.png"))
        has_swf = os.path.isfile(os.path.join(AV, ident + "_0.swf"))
        has_pers = os.path.isdir(os.path.join(PERS, ident))
        f.write("  id=%-8s sex=%-5s buy=%-6s png0=%-5s png1=%-5s swf=%-5s personages/%s=%s\n"
                % (ident, a.get("sex"), a.get("buy"), has_png0, has_png1,
                   has_swf, ident, has_pers))
    f.write("\nвсего записей: %d\n" % n)
print("готово")
