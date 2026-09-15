import io, json, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/market_page.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

out = []
title = "\u0427\u0435\u0440\u043d\u044b\u0439 \u0440\u044b\u043d\u043e\u043a \u0412\u0430\u0434\u0438-\u0425\u0430\u043b\u044c\u0444\u044b"
txt = api(action="parse", page=title, prop="wikitext")["parse"]["wikitext"]["*"]
out.append("=== страница: %s (%d символов) ===" % (title, len(txt)))
out.append(txt[:2500])
out.append("")
# what does the НПС category hold
cat = "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f:\u041d\u041f\u0421"
r = api(action="query", list="categorymembers", cmtitle=cat, cmlimit=40, cmtype="page")
out.append("=== первые страницы категории НПС ===")
for m in r["query"]["categorymembers"]:
    out.append("   " + m["title"])
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
