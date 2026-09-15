import io, json, re, time, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/mods.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

QUERIES = [
    ("модификация брони", "модификация брони"),
    ("конверсия", "конверсия"),
    ("переделка автомата", "переделка автомат"),
    ("эргономика", "эргономика"),
    ("модификатор", "модификатор"),
]
out = []
for label, q in QUERIES:
    try:
        r = api(action="query", list="search", srsearch=q, srlimit=10)
        hits = r.get("query", {}).get("search", [])
        out.append("%s: %d" % (label, len(hits)))
        for h in hits:
            out.append("   " + h["title"])
    except Exception as e:
        out.append("%s: ошибка %s" % (label, e))
    out.append("")
    time.sleep(0.2)
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
