import io, json, re, time, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/npc_pages.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

market = "Черный рынок Вади-Хальфы"
txt = api(action="parse", page=market, prop="wikitext")["parse"]["wikitext"]["*"]
links = re.findall(r"\*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", txt)
out = ["жителей на странице рынка: %d" % len(links), ""]
for name in links:
    try:
        w = api(action="parse", page=name, prop="wikitext")["parse"]["wikitext"]["*"]
    except Exception as e:
        out.append("%-34s ОШИБКА %s" % (name, e))
        continue
    body = re.sub(r"\[\[([^\]|]*\|)?", "", w).replace("]]", "")
    body = re.sub(r"\{\|.*?\|\}", " ", body, flags=re.S)
    body = re.sub(r"[=*'\n]+", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    out.append("%-34s %s" % (name, body[:170]))
    time.sleep(0.15)
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
