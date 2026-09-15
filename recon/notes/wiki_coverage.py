import json, urllib.request, urllib.parse, time

API = "https://lava-online.fandom.com/ru/api.php"
def api(**kw):
    kw.setdefault("format","json")
    req = urllib.request.Request(API+"?"+urllib.parse.urlencode(kw),
          headers={"User-Agent":"Mozilla/5.0 lava-preservation"})
    return json.load(urllib.request.urlopen(req, timeout=30))

CATS = ["Автоматы","Винтовки","Пистолеты","Амуниция","Боеприпасы","Аксессуары",
        "БАФы","Холодное оружие","Броня","Монстры","Мобы","Квесты","Локации",
        "Шлемы","Ботинки","Пояса","Перчатки"]
print("%-22s %6s" % ("категория","страниц"))
found = {}
for c in CATS:
    try:
        r = api(action="query", list="categorymembers", cmtitle="Категория:"+c,
                cmlimit=500, cmtype="page")
        n = len(r["query"]["categorymembers"])
        if n:
            found[c] = [m["title"] for m in r["query"]["categorymembers"]]
            print("%-22s %6d" % (c, n))
    except Exception as e:
        pass
    time.sleep(0.2)

# how many of a sample actually carry a TTX table
import random
sample = []
for c in ("Автоматы","Винтовки","Амуниция","Боеприпасы"):
    sample += found.get(c, [])[:8]
sample = sample[:24]
hit = 0
print("\nпроверка таблиц ТТХ на выборке из %d статей:" % len(sample))
for title in sample:
    try:
        t = api(action="parse", page=title, prop="wikitext")["parse"]["wikitext"]["*"]
        has = "article-table" in t or "характеристики" in t.lower()
        hit += has
        print("  %s %s" % ("да " if has else "нет", title))
    except Exception as e:
        print("  err %s" % title)
    time.sleep(0.2)
print("\nсо структурой: %d / %d" % (hit, len(sample)))
