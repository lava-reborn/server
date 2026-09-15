import io, json, re, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/unmapped.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

out = []
# Everything the wiki places at the market's coordinates, not just what its
# own page happens to link.
r = api(action="query", list="search", srsearch="5968х1727", srlimit=50)
hits = [h["title"] for h in r.get("query", {}).get("search", [])]
out.append("страниц с координатами рынка 5968х1727: %d" % len(hits))
for t in hits:
    out.append("   " + t)
out.append("")

# Самуэль in full: he is the one wiki name left over.
w = api(action="parse", page="Самуэль",
        prop="wikitext")["parse"]["wikitext"]["*"]
out.append("=== Самуэль, полностью ===")
out.append(w[:1400])
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
