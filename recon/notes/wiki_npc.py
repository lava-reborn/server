import io, json, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/wiki_npc.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

lines = []
# does the wiki know the market itself?
for q in ["Черный рынок",   # Черный рынок
          "торговец",                      # торговец
          "NPC"]:
    r = api(action="query", list="search", srsearch=q, srlimit=8)
    lines.append("поиск %r: %d совпадений" % (q, r["query"]["searchinfo"]["totalhits"]))
    for hit in r["query"]["search"]:
        lines.append("   " + hit["title"])
    lines.append("")

# all categories, to see whether NPCs are catalogued at all
r = api(action="query", list="allcategories", aclimit=500, acprop="size")
cats = [(c["size"], c["*"]) for c in r["query"]["allcategories"]]
lines.append("категорий всего: %d" % len(cats))
lines.append("самые крупные:")
for n, c in sorted(cats, reverse=True)[:25]:
    lines.append("   %4d  %s" % (n, c))
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("готово")
