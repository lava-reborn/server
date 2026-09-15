"""Shared helpers for the wiki-derived data scripts (wiki_links, wiki_extract).

Everything reads the local mirror in data/wiki/ (see wiki_dump.py) and the
client's objects.xml; nothing here touches the network.
"""
import gzip
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
WIKI = os.path.join(HERE, "wiki")

RES = os.environ.get("LAVA_RES") or ""
if not os.path.isdir(RES):
    for _candidate in (r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res",
                       "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        if os.path.isdir(_candidate):
            RES = _candidate
            break

# Item root types (Item.as:39-45), same numbering as server/items.py.
FIRE_ARM, WEAR, HEAL, AMMO, TRASH, COLD_ARM, TROPHY = range(7)

# Wiki categories that describe items, and the root type they mostly hold.
ITEM_CATEGORIES = {
    "Огнестрельное оружие": FIRE_ARM, "Наградное оружие": FIRE_ARM,
    "Коллекционное оружие": FIRE_ARM,
    "Холодное оружие": COLD_ARM,
    "Одежда": WEAR, "Амуниция": WEAR, "Пояса": WEAR, "Аксесуары": WEAR,
    "Сеты": WEAR, "Наградные предметы": WEAR,
    "Боеприпасы": AMMO,
    "Лечащие предметы": HEAL, "БАФы": HEAL, "Провизия": HEAL, "Медикаменты": HEAL,
    "Чертежи": TRASH, "Треш лут": TRASH, "Квестовые предметы": TRASH,
    "Предметы": TRASH, "Коллекции": TRASH,
    "Трофеи": TROPHY,
    "Транспорт": None,
}

# The six firearm subcategories and the class token in objects.xml names
# (pistols_1_lvl_18 and so on; see recon/analysis/data.md section 2).
FIREARM_CLASS = {
    "Пистолеты": "pistols", "Дробовики": "shotgun",
    "Пистолет-пулеметы": "sub_machine_guns", "Автоматы": "assault_rifle",
    "Винтовки": "rifle", "Пулеметы": "machine_gun",
}

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
         "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19,
         "XX": 20}


def dump_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pages():
    """title -> page record from the mirror (pages.json or pages.json.gz)."""
    for name, opener in (("pages.json.gz", gzip.open), ("pages.json", open)):
        p = os.path.join(WIKI, name)
        if os.path.exists(p):
            with opener(p, "rt", encoding="utf-8") as f:
                return json.load(f)
    raise SystemExit("no data/wiki/pages.json: run data/wiki_dump.py first")


def load_objects():
    """type_id -> (root_type_id, internal name) from the client's objects.xml."""
    path = os.path.join(RES, "database", "objects.xml")
    with open(path, "rb") as f:
        txt = f.read().decode("utf-8", "replace")
    return {int(t): (int(r), n) for t, r, n in re.findall(
        r'<object type_id="(\d+)" root_type_id=\s*"(\d+)"\s+name="([^"]*)"', txt)}


def norm(s):
    """Case-, space- and punctuation-insensitive key for name matching."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def categories(page):
    return [c.replace("Категория:", "") for c in page.get("categories", [])]


def image_names(page):
    """Image file names of a page without the namespace and extension."""
    out = []
    for i in page.get("images", []):
        i = re.sub(r"^Файл:", "", i)
        i = re.sub(r"\.(png|jpe?g|gif|svg)$", "", i, flags=re.I)
        out.append(i)
    return out


# --- internal name anatomy -------------------------------------------------

# Trailing tokens that mark a clan/event/private copy rather than a variant.
EXTRA_TOKENS = {"LeMon", "mob", "Blackwater", "Delta", "Force", "x10", "Pack",
                "Pack1000", "Jons", "demo", "afro", "long", "super", "Event",
                "NY", "xenos", "9may", "briket"}
TIER_TOKENS = {"pm": "P", "P": "P", "p": "P",
               "gold": "G", "Gold": "G", "G": "G", "g": "G",
               "A": "A", "a": "A"}
KNIFE = re.compile(r"^(knife_lvl\d+)_(A|G)(?:_(damage_actionpoints|actionpoint|damage))?$")
WEAR_RE = re.compile(r"^(helm|shirt|armor|pants|boots|belt)_(.+?)_(M|W)_LVL_(\d+)_"
                     r"(A|P|G|U|Q)_mod(\d\d)(.*)$")
MASS_FIREARM = re.compile(r"^(pistols|shotgun|sub_machine_guns|assault_rifle|rifle|machine_gun)"
                          r"_(\d+)_lvl_(\d+)(.*)$")


def parse_name(name):
    """Split an internal name into (base, tier, mod, extra).

    tier is "A" (ordinary, sold for afro), "P" (premium) or "G" (gold);
    mod is the modification key after `_mod_` (damage, clipsize, ...),
    knife mods map onto the same idea; extra lists clan/event tokens.
    """
    m = KNIFE.match(name)
    if m:
        return m.group(1), m.group(2), m.group(3), []
    m = WEAR_RE.match(name)
    if m:
        mod = None if m.group(6) == "00" else "mod" + m.group(6)
        extra = [m.group(7)] if m.group(7) else []
        return "%s_%s_%s_LVL_%s" % m.groups()[:4], m.group(5), mod, extra
    toks = name.split("_")
    tier, extra = "A", []
    while len(toks) > 1:
        t = toks[-1]
        if t in TIER_TOKENS:
            tier = TIER_TOKENS[t]
            toks.pop()
        elif t in EXTRA_TOKENS or re.match(r"^(ID|CL)\d+$|^base$", t):
            extra.insert(0, t)
            toks.pop()
        else:
            break
    mod = None
    if "mod" in toks[1:]:
        i = len(toks) - 1 - toks[::-1].index("mod")
        mod = "_".join(toks[i + 1:]) or None
        toks = toks[:i]
        while len(toks) > 1 and toks[-1] in TIER_TOKENS:
            tier = TIER_TOKENS[toks.pop()]
    return "_".join(toks), tier, mod, extra


# --- wikitable parsing -----------------------------------------------------

TABLE = re.compile(r"^\{\|.*?^\|\}", re.S | re.M)
BOLD = "'''"
WIKILINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
EXTLINK = re.compile(r"\[https?://\S+\s+([^\]]*)\]")
TAG = re.compile(r"<[^>]+>")
ATTRS = re.compile(r'^\s*(?:(?:[a-zA-Z-]+\s*=\s*(?:"[^"]*"|\S+)\s*)+)\|')


def clean_cell(text):
    """Wikitext cell -> plain text; <br> becomes a newline, links their label."""
    t = ATTRS.sub("", text)
    t = re.sub(r"<\s*br\s*/?\s*>", "\n", t, flags=re.I)
    t = WIKILINK.sub(r"\1", t)
    t = EXTLINK.sub(r"\1", t)
    t = TAG.sub("", t)
    t = t.replace("&nbsp;", " ").replace("\u00a0", " ").replace("\u200e", "")
    t = t.replace(BOLD, "").replace("''", "")
    return "\n".join(x.strip() for x in t.split("\n")).strip()


def parse_table(block):
    """One {| ... |} block -> {"columns": [...], "rows": [(label, [cells])]}.

    Header cells (!) that form a whole row are the column names; a header
    cell at the start of a data row (scope="row") is that row's label, which
    is how a few articles lay their tables out sideways. Bold labels are
    kept as-is: the caller decides whether they are section headers.
    """
    lines = block.split("\n")[1:]
    rows, cur = [], []
    for ln in lines:
        s = ln.strip()
        if s.startswith("|}"):
            break
        if s.startswith("|-"):
            rows.append(cur)
            cur = []
        elif s.startswith("|+"):
            continue
        elif s.startswith("!"):
            for c in s[1:].split("!!"):
                cur.append([True, c])
        elif s.startswith("|"):
            for c in s[1:].split("||"):
                cur.append([False, c])
        elif cur:
            cur[-1][1] += "\n" + ln
    rows.append(cur)
    columns, data = [], []
    for row in rows:
        if not row:
            continue
        cells = [(h, clean_cell(c)) for h, c in row]
        if all(h for h, _ in cells):
            columns = [c for _, c in cells]
            continue
        label = cells[0][1]
        data.append((label, [c for _, c in cells[1:]]))
    return {"columns": columns, "rows": data}


def parse_tables(wikitext):
    return [parse_table(b) for b in TABLE.findall(wikitext)]


# --- cell values -----------------------------------------------------------

NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
RANGE_RE = re.compile(r"^(%s)\s*[-–—]\s*(%s)$" % (NUMBER, NUMBER))
NUM_RE = re.compile(r"^(%s)\s*(с|c|сек|г|гр|кг|м|шт|%%)?\.?$" % NUMBER)
MONEY_RE = re.compile(r"^(%s)\s*(Афро|афро|G|ПвП-баллов)$" % NUMBER)
DURATION_RE = re.compile(r"^(?:(\d+)\s*ч\.?\s*)?(?:(\d+)\s*м\.?\s*)?(?:(\d+)\s*[сc]\.?\s*)?$")
NAMED_RE = re.compile(r"^([А-Яа-яЁё][А-Яа-яЁё .-]*?)\s+(%s)$" % NUMBER)


def _num(s):
    v = float(s.replace(",", "."))
    return int(v) if v == int(v) else v


def value(cell):
    """Typed cell value: number, [lo, hi], {"afro"/"g": n}, bool, or text.

    Multi-line cells (from <br>) become lists; "Стрельба 4" style requirement
    lines become {"Стрельба": 4}.
    """
    s = cell.strip()
    if not s:
        return None
    if "\n" in s:
        parts = [value(p) for p in s.split("\n") if p.strip()]
        return parts if len(parts) != 1 else parts[0]
    if s in ("Да", "да", "Да.", "Есть"):
        return True
    if s in ("Нет", "нет", "Нет.", "-", "—", "–"):
        return False
    m = RANGE_RE.match(s)
    if m:
        return [_num(m.group(1)), _num(m.group(2))]
    m = MONEY_RE.match(s)
    if m:
        unit = m.group(2)
        if unit == "G":
            return {"g": _num(m.group(1))}
        if unit.startswith("ПвП"):
            return {"pvp": _num(m.group(1))}
        return {"afro": _num(m.group(1))}
    m = NUM_RE.match(s)
    if m:
        v = _num(m.group(1))
        unit = m.group(2) or ""
        if unit == "кг":
            v = v * 1000
        if unit == "%":
            return {"pct": v}
        return v
    m = DURATION_RE.match(s)
    if m and any(m.groups()):
        h, mi, se = (int(x) if x else 0 for x in m.groups())
        return {"sec": h * 3600 + mi * 60 + se}
    m = NAMED_RE.match(s)
    if m:
        return {m.group(1).strip(): _num(m.group(2))}
    return s
