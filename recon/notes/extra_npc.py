import io, json, re, time, urllib.parse, urllib.request
API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1"}
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/extra_npc.txt"

def api(**kw):
    kw.setdefault("format", "json")
    r = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))

CAND = ["Нильсон", "Иви",
        "Винс", "Зоричев",
        "Ольсен", "Банкир",
        "Бартоломью",
        "Джексон Кертис",
        "Генри ст",
        "Берт Гаммер",
        "Лотерейщик"]
out = []
for n in CAND:
    try:
        w = api(action="parse", page=n, prop="wikitext")["parse"]["wikitext"]["*"]
    except Exception as e:
        out.append("%-20s ОШИБКА" % n); continue
    desc = re.search(r"==\s*Описание\s*==\s*(.{0,150})", w, re.S)
    serv = re.search(r"==\s*Услуги\s*==(.{0,260})", w, re.S)
    clean = lambda t: re.sub(r"\s+", " ", re.sub(r"[\[\]|=*'\n]+", " ", t or "")).strip()
    out.append("%-20s ОПИС: %s" % (n, clean(desc.group(1) if desc else "")[:95]))
    out.append("%-20s УСЛУГИ: %s" % ("", clean(serv.group(1) if serv else "нет")[:150]))
    out.append("")
    time.sleep(0.15)
io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("готово")
