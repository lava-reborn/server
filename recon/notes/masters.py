import io, json, re, time, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/masters.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

NAMES = ["Мастер Аммар",
         "Мастер Самир",
         "Шульц", "Хасани",
         "Симона"]
out = []
for n in NAMES:
    try:
        w = api(action="parse", page=n, prop="wikitext")["parse"]["wikitext"]["*"]
    except Exception:
        out.append("%-16s НЕТ СТРАНИЦЫ" % n); continue
    clean = lambda t: re.sub(r"\s+", " ", re.sub(r"[\[\]|=*'\n]+", " ", t or "")).strip()
    body = clean(w)
    at_market = "5968" in w
    out.append("%-16s на Чёрном рынке ВХ: %s" % (n, "ДА" if at_market else "нет"))
    out.append("   " + body[:230])
    out.append("")
    time.sleep(0.15)
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
