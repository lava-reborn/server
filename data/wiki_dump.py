"""Mirror the fan wiki (lava-online.fandom.com/ru) into data/wiki/.

The wiki is the only surviving copy of the game's balance tables, quest texts
and NPC names, so everything downstream (linker, extractor) works off this
local mirror instead of hitting the site. Run from WSL:

    wsl.exe -e python3 data/wiki_dump.py            # incremental
    wsl.exe -e python3 data/wiki_dump.py --force    # refetch everything

What it writes (all sorted, indent=1, so diffs stay readable):

    data/wiki/site.json      siteinfo statistics + namespaces, dump timestamp
    data/wiki/pages.json     title -> {pageid, ns, revid, timestamp, images,
                             categories, wikitext}; becomes pages.json.gz
                             when the wikitext alone passes 30 MB
    data/wiki/images.json    file name -> {url, size, width, height, mime,
                             sha1, timestamp} for every uploaded file
                             (the pictures themselves are not downloaded)

Idempotent: it lists every page with its last revision id first and only
fetches content for pages that are new or changed since the previous run.
Content is CC-BY-SA (see data/wiki/README.md); keep the attribution.
"""
import argparse
import datetime
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://lava-online.fandom.com/ru/api.php"
UA = "lava-preservation/0.2 (server reimplementation for a dead game; github.com/polestvr)"
PAUSE = 0.2
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wiki")
GZ_THRESHOLD = 30 * 1024 * 1024

# Namespaces worth mirroring. Talk pages, user pages and message walls are
# left out: they hold no game data and the statistics count of 6721 "pages"
# includes them.
NAMESPACES = [0, 4, 6, 10, 12, 14, 110, 500, 502, 828, 2900]


def api(retries=6, **kw):
    kw.setdefault("format", "json")
    kw.setdefault("formatversion", "2")
    kw.setdefault("maxlag", "5")
    url = API + "?" + urllib.parse.urlencode(kw)
    delay = 2.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            if "error" in data:
                if data["error"].get("code") == "maxlag":
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise RuntimeError(data["error"])
            time.sleep(PAUSE)
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ConnectionError, json.JSONDecodeError) as exc:
            if attempt == retries - 1:
                raise
            print("  retry %d after %s" % (attempt + 1, exc), file=sys.stderr)
            time.sleep(delay)
            delay *= 2


def query_all(**kw):
    """Yield every result page of a query, following `continue`."""
    cont = {}
    while True:
        r = api(action="query", **kw, **cont)
        yield r
        if "continue" not in r:
            return
        cont = r["continue"]


def dump_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def load_pages():
    for name, opener in (("pages.json.gz", gzip.open), ("pages.json", open)):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            with opener(p, "rt", encoding="utf-8") as f:
                return json.load(f)
    return {}


def save_pages(pages):
    size = sum(len(p.get("wikitext", "")) for p in pages.values())
    plain, packed = os.path.join(OUT, "pages.json"), os.path.join(OUT, "pages.json.gz")
    if size > GZ_THRESHOLD:
        tmp = packed + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as f:
            json.dump(pages, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, packed)
        if os.path.exists(plain):
            os.remove(plain)
    else:
        dump_json(plain, pages)
        if os.path.exists(packed):
            os.remove(packed)
    return size


def list_pages(namespaces):
    """title -> {pageid, ns, lastrevid, length, touched} across namespaces."""
    index = {}
    for ns in namespaces:
        n = 0
        for r in query_all(generator="allpages", gapnamespace=ns, gaplimit=500,
                           prop="info"):
            for p in r.get("query", {}).get("pages", []):
                index[p["title"]] = dict(pageid=p["pageid"], ns=p["ns"],
                                         lastrevid=p.get("lastrevid", 0),
                                         length=p.get("length", 0),
                                         touched=p.get("touched", ""))
                n += 1
        print("ns %d: %d pages" % (ns, n), file=sys.stderr)
    return index


def fetch_batch(pageids):
    """Wikitext + images + categories for up to 50 pages, following continue."""
    got = {}
    cont = {}
    while True:
        r = api(action="query", pageids="|".join(str(i) for i in pageids),
                prop="revisions|images|categories",
                rvprop="ids|timestamp|content", rvslots="main",
                imlimit="max", cllimit="max", **cont)
        for p in r.get("query", {}).get("pages", []):
            rec = got.setdefault(p["pageid"], dict(
                pageid=p["pageid"], ns=p["ns"], title=p["title"],
                images=[], categories=[]))
            if "revisions" in p and "wikitext" not in rec:
                rev = p["revisions"][0]
                rec["revid"] = rev["revid"]
                rec["timestamp"] = rev["timestamp"]
                rec["wikitext"] = rev["slots"]["main"]["content"]
            for im in p.get("images", []):
                if im["title"] not in rec["images"]:
                    rec["images"].append(im["title"])
            for c in p.get("categories", []):
                if c["title"] not in rec["categories"]:
                    rec["categories"].append(c["title"])
        if "continue" not in r:
            return got
        cont = r["continue"]


def fetch_images():
    images = {}
    for r in query_all(list="allimages", ailimit=500,
                       aiprop="url|size|mime|sha1|timestamp|user"):
        for im in r.get("query", {}).get("allimages", []):
            url = im["url"].split("/revision/")[0]
            images[im["name"]] = dict(
                url=url, size=im["size"], width=im["width"],
                height=im["height"], mime=im["mime"], sha1=im["sha1"],
                timestamp=im["timestamp"], user=im.get("user", ""))
    return images


def write_readme(stats, index, pages, images, when):
    ns_counts = {}
    for p in pages.values():
        ns_counts[p["ns"]] = ns_counts.get(p["ns"], 0) + 1
    lines = [
        "# Зеркало вики lava-online.fandom.com/ru",
        "",
        "Снято скриптом `data/wiki_dump.py` через MediaWiki API, %s." % when,
        "",
        "Содержимое вики распространяется по лицензии "
        "[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/); "
        "авторы — участники вики «Энциклопедия lava-online.ru» "
        "(<https://lava-online.fandom.com/ru>). Всё, что выведено из этих "
        "файлов (`wiki_items.json`, `items_wiki.json`, `mods_wiki.json`, "
        "`wiki_links.json`), наследует ту же лицензию и должно ссылаться на "
        "источник.",
        "",
        "Статистика вики на момент снятия: страниц %s, статей %s, файлов %s, "
        "правок %s." % (stats.get("pages"), stats.get("articles"),
                        stats.get("images"), stats.get("edits")),
        "",
        "| Файл | Что внутри |",
        "|---|---|",
        "| `site.json` | siteinfo: статистика, пространства имён, время снятия |",
        "| `pages.json[.gz]` | %d страниц: заголовок → pageid, ns, revid, "
        "timestamp, список изображений и категорий, wikitext |" % len(pages),
        "| `images.json` | %d файлов: имя → URL, размер, mime, sha1 "
        "(сами картинки не скачаны) |" % len(images),
        "",
        "Страниц по пространствам имён: " + ", ".join(
            "ns %d — %d" % (ns, n) for ns, n in sorted(ns_counts.items())) + ".",
        "",
        "Не зеркалируются обсуждения, страницы участников и стены обсуждений: "
        "игровых данных там нет.",
        "",
        "Повторный запуск докачивает только новые и изменённые страницы "
        "(сравнение `lastrevid`); `--force` перекачивает всё.",
        "",
    ]
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="refetch every page")
    ap.add_argument("--ns", default=",".join(map(str, NAMESPACES)),
                    help="comma-separated namespace ids")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    namespaces = [int(x) for x in args.ns.split(",") if x.strip()]
    os.makedirs(OUT, exist_ok=True)

    when = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    si = api(action="query", meta="siteinfo", siprop="statistics|namespaces|general")
    stats = si["query"]["statistics"]
    dump_json(os.path.join(OUT, "site.json"), dict(
        dumped=when, statistics=stats, general=si["query"]["general"],
        namespaces={k: v.get("name", "") for k, v in si["query"]["namespaces"].items()}))
    print("wiki: %s" % json.dumps(stats), file=sys.stderr)

    index = list_pages(namespaces)
    pages = load_pages()
    by_id = {p["pageid"]: t for t, p in pages.items()}

    # Drop pages that were deleted or renamed on the wiki.
    live_ids = {p["pageid"] for p in index.values()}
    for pid, title in list(by_id.items()):
        if pid not in live_ids or pages[title]["ns"] not in namespaces:
            del pages[title]
    todo = []
    for title, meta in index.items():
        old = pages.get(title)
        if args.force or not old or old.get("revid") != meta["lastrevid"] \
                or "wikitext" not in old:
            todo.append(meta["pageid"])
    print("pages: %d listed, %d cached, %d to fetch"
          % (len(index), len(pages), len(todo)), file=sys.stderr)

    fetched = 0
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        for pid, rec in fetch_batch(batch).items():
            if "wikitext" not in rec:
                print("  no content for %s" % rec["title"], file=sys.stderr)
                continue
            rec["images"].sort()
            rec["categories"].sort()
            pages[rec.pop("title")] = rec
            fetched += 1
        if (i // 50) % 10 == 0 or i + 50 >= len(todo):
            print("  %d/%d" % (min(i + 50, len(todo)), len(todo)), file=sys.stderr)
            save_pages(pages)
    size = save_pages(pages)
    print("saved %d pages, %.1f MB of wikitext%s" % (
        len(pages), size / 1048576, " (gzipped)" if size > GZ_THRESHOLD else ""),
        file=sys.stderr)

    images_path = os.path.join(OUT, "images.json")
    if args.no_images and os.path.exists(images_path):
        with open(images_path, encoding="utf-8") as f:
            images = json.load(f)
    else:
        images = fetch_images()
        dump_json(images_path, images)
        print("images: %d" % len(images), file=sys.stderr)

    write_readme(stats, index, pages, images, when)
    print("fetched %d pages this run" % fetched, file=sys.stderr)


if __name__ == "__main__":
    main()
