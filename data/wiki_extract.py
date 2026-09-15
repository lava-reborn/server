"""Pull weapon/armour stat tables off the community wiki into JSON.

The official servers took the balance data with them: the shipped client holds
only type_id -> internal name plus icons. The fan wiki at lava-online.fandom.com
kept the tactical-technical tables, so it is the only surviving source for
damage, ranges, action-point costs and fire modes.

Content there is CC-BY-SA; keep attribution when redistributing.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://lava-online.fandom.com/ru/api.php"
UA = {"User-Agent": "lava-preservation/0.1 (server reimplementation)"}
BOLD = "'" * 3


def api(**kw):
    kw.setdefault("format", "json")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(kw), headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=30))


def category(name, limit=500):
    out, cont = [], None
    while True:
        kw = dict(action="query", list="categorymembers",
                  cmtitle="Категория:" + name, cmlimit=limit, cmtype="page")
        if cont:
            kw["cmcontinue"] = cont
        r = api(**kw)
        out += [m["title"] for m in r["query"]["categorymembers"]]
        cont = r.get("continue", {}).get("cmcontinue")
        if not cont:
            return out


def wikitext(title):
    return api(action="parse", page=title, prop="wikitext")["parse"]["wikitext"]["*"]


RANGE = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*-\s*(-?\d+(?:[.,]\d+)?)$")
NUM = re.compile(r"^(-?\d+(?:[.,]\d+)?)\s*(с|сек|кг|м|%)?$")
TABLE = re.compile(r"\{\|.*?\n\|\}", re.S)
HEAD = re.compile(r'^!\s*(?:scope="col"\s*\|)?(.+)$', re.M)
CELL = re.compile(r"^\|\s?(.*)$", re.M)
DESC = re.compile(r"==\s*Описание\s*==\s*\n(.+?)(?:\n==|\Z)", re.S)


def value(cell):
    """Turn a table cell into a number, a [lo, hi] range, or the raw string."""
    s = cell.strip().strip("'").strip().replace(" ", " ")
    if not s:
        return None
    m = RANGE.match(s)
    if m:
        return [float(m.group(1).replace(",", ".")),
                float(m.group(2).replace(",", "."))]
    m = NUM.match(s)
    if m:
        v = float(m.group(1).replace(",", "."))
        return int(v) if v == int(v) else v
    return s


def parse_tables(txt):
    """Parse every wikitable in the article, keeping each one separate.

    An article usually repeats a section name (weapons list "Первый режим
    стрельбы" once per variant table), so merging all tables into one dict
    would silently keep only the last occurrence.
    """
    tables = []
    for block in TABLE.findall(txt):
        columns, sections, cur = [], {}, "общие"
        for raw in re.split(r"\n\|-", block):
            heads = HEAD.findall(raw)
            if heads:
                columns = [h.strip() for h in heads]
                continue
            cells = [c for c in CELL.findall(raw)
                     if not c.startswith("}") and not c.startswith("-")]
            if not cells:
                continue
            key = cells[0].strip()
            if not key:
                continue
            # A bold first cell always marks a section header row (the other
            # cells on such rows are empty, but stray "|" fragments from the
            # markup would otherwise make them look like real values).
            if key.startswith(BOLD):
                cur = key.strip("'").strip()
                sections.setdefault(cur, {})
                continue
            vals = [value(c) for c in cells[1:]]
            sections.setdefault(cur, {})[key.strip("'").strip()] = vals
        if sections:
            tables.append({"columns": columns[1:] if columns else [],
                           "sections": sections})
    return tables


def extract(title):
    txt = wikitext(title)
    m = DESC.search(txt)
    return {"title": title,
            "description": m.group(1).strip() if m else "",
            "tables": parse_tables(txt)}


def main():
    titles = sys.argv[1:] or ["Самодельный автомат", "9А-91", "FN F2000"]
    out = []
    for t in titles:
        try:
            out.append(extract(t))
            print("  ok  %s" % t, file=sys.stderr)
        except Exception as exc:
            print("  err %s: %s" % (t, exc), file=sys.stderr)
        time.sleep(0.2)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
