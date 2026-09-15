import io, json, re, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/three.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

names = ["Хамис", "Ваккас",
         "Самуэль",
         "Магдалена",
         "Савин"]
out = []
for n in names:
    w = api(action="parse", page=n, prop="wikitext")["parse"]["wikitext"]["*"]
    out.append("=== %s ===" % n)
    out.append(w[:900])
    out.append("")
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
