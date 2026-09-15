import io, json, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/wiki_npc.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

lines = []
for label, q in [("Черный рынок", "Черный рынок"),
                 ("торговец", "торговец"),
                 ("wh_Pistols", "wh_Pistols"),
                 ("Вади Хальфа", "Вади Хальфа")]:
    try:
        r = api(action="query", list="search", srsearch=q, srlimit=8)
        hits = r.get("query", {}).get("search", [])
        lines.append("поиск %s: %d" % (label, len(hits)))
        for h in hits:
            lines.append("   " + h["title"])
    except Exception as e:
        lines.append("поиск %s: ошибка %s" % (label, e))
    lines.append("")

r = api(action="query", list="allcategories", aclimit=500, acprop="size")
cats = [(c["size"], c["*"]) for c in r["query"]["allcategories"]]
lines.append("категорий: %d, крупнейшие:" % len(cats))
for n, c in sorted(cats, reverse=True)[:22]:
    lines.append("   %4d  %s" % (n, c))
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("готово")
