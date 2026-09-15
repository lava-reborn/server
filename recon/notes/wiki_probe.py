import json, urllib.request, urllib.parse, io

API = "https://lava-online.fandom.com/ru/api.php"

def api(**kw):
    kw.setdefault("format", "json")
    url = API + "?" + urllib.parse.urlencode(kw)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 lava-preservation"})
    return json.load(urllib.request.urlopen(req, timeout=30))

d = api(action="parse", page="Самодельный автомат", prop="wikitext")
txt = d["parse"]["wikitext"]["*"]
print("=== WIKITEXT of 'Самодельный автомат' (%d chars) ===" % len(txt))
print(txt[:2600])
