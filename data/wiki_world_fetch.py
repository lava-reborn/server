"""Fetch the world-side wiki pages (NPCs, locations, mobs, loot) into data/wiki_world/.

The fan wiki at lava-online.fandom.com/ru is the only surviving source for
who stands where, what the traders sell, which mob guards which item and how
the interiors of a settlement hang together. This pulls the raw wikitext of
every page in the categories the world data scripts read, one JSON file per
category, so everything downstream works offline and reproducibly.

Pages are fetched fifty at a time through prop=revisions, which is the API's
own batch form; category listings go through list=categorymembers. The pause
between requests is a courtesy to the wiki, not a requirement of the API.

Content is CC-BY-SA (https://www.fandom.com/licensing); keep attribution.

    wsl.exe -e python3 data/wiki_world_fetch.py            # everything missing
    wsl.exe -e python3 data/wiki_world_fetch.py НПС Мобы   # only these
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1 (server reimplementation)"}
PAUSE = 0.2
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wiki_world")

# category -> file stem. The item categories are here for the loot edges:
# their pages carry the "Мобы-хранители" lists that name who drops what.
CATEGORIES = {
    "НПС": "npc",
    "Персонажи": "personages",
    "Локации": "locations",
    "Мобы": "mobs",
    "Треш лут": "trash_loot",
    "Квестовые предметы": "quest_items",
    "Предметы": "items",
    "Транспорт": "transport",
    "Кланы": "clans",
    "Термины": "terms",
    # The quest pages carry what recon/analysis/wiki_quests_all.json left
    # out: level requirements, afro/gold amounts, the items involved.
    "Квесты": "quests",
}


def api(**kw):
    kw.setdefault("format", "json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw),
                                 headers=UA)
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as exc:  # network hiccup: back off and retry
            if attempt == 4:
                raise
            print("  retry %d: %s" % (attempt + 1, exc), file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    return None


def members(category):
    """Every page title in a category, and its subcategories, in wiki order."""
    pages, subcats, cont = [], [], None
    while True:
        kw = dict(action="query", list="categorymembers",
                  cmtitle="Категория:" + category, cmlimit=500,
                  cmprop="title|type")
        if cont:
            kw["cmcontinue"] = cont
        r = api(**kw)
        for m in r["query"]["categorymembers"]:
            (subcats if m["type"] == "subcat" else pages).append(m["title"])
        cont = r.get("continue", {}).get("cmcontinue")
        time.sleep(PAUSE)
        if not cont:
            return pages, subcats


def contents(titles):
    """title -> wikitext for up to fifty titles per request."""
    out = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        r = api(action="query", prop="revisions", rvprop="content",
                rvslots="main", titles="|".join(batch))
        for page in r["query"]["pages"].values():
            revs = page.get("revisions")
            if not revs:
                continue
            slot = revs[0].get("slots", {}).get("main", revs[0])
            out[page["title"]] = slot.get("*") or slot.get("content") or ""
        # Titles the API normalised (spaces, case) come back under the
        # normalised name; keep the requested one so lookups stay stable.
        for n in r["query"].get("normalized", []):
            if n["to"] in out:
                out[n["from"]] = out[n["to"]]
        print("  %d/%d" % (min(i + 50, len(titles)), len(titles)),
              file=sys.stderr)
        time.sleep(PAUSE)
    return out


def dump(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def main():
    os.makedirs(OUT, exist_ok=True)
    wanted = sys.argv[1:] or list(CATEGORIES)
    for cat in wanted:
        stem = CATEGORIES[cat]
        path = os.path.join(OUT, stem + ".json")
        if os.path.exists(path) and not sys.argv[1:]:
            print("skip %s (exists)" % path, file=sys.stderr)
            continue
        print("category %s" % cat, file=sys.stderr)
        pages, subcats = members(cat)
        print("  %d pages, %d subcategories" % (len(pages), len(subcats)),
              file=sys.stderr)
        texts = contents(pages)
        dump(path, {"_source": "https://lava-online.fandom.com/ru/wiki/"
                                "Категория:" + cat,
                    "_license": "CC-BY-SA 3.0",
                    "_fetched": time.strftime("%Y-%m-%d"),
                    "category": cat, "subcategories": subcats,
                    "pages": texts})
        print("  wrote %s (%d pages)" % (path, len(texts)), file=sys.stderr)


if __name__ == "__main__":
    main()
