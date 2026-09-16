"""Bind the wiki's NPC pages to the client's type ids: names, roles, stock.

The client names its townsfolk in Latin shorthand (wh_trd_Hasseer, nz_Zula,
Simple_Upgrader) and looked the Russian names up in texts.xml, which did
not survive. The fan wiki has a page for each of 317 NPCs with a portrait,
a description, coordinates ("[[Вади-Хальфа]] [[Черный рынок Вади-Хальфы|
Черный рынок]] 5968х1727"), the services offered and, for traders, the
list of goods. This script walks from each page to the type id standing in
that location:

  page -> named location (wiki link) and map cell
       -> static location file(s) by title, or by cell through settlements
       -> the spawn points there with root_type_id != 0
       -> filtered by the role the services imply (Торговля -> Trader,
          Улучшения -> Upgrader, Лечение -> Medic, Аренда -> Lessor, ...)
       -> ranked by a transliteration of the name against the internal name
          (Хамис ~ wh_set_trd? no; Аарон ~ wh_Aaron_bank: yes) and by the
          goods category (Пистолеты и патроны ~ wh_Pistols).

Every candidate is kept with its score, so a wrong pick can be traced.
Bindings rated high or medium go into data/npc_names.json (the file
server/names.py reads; its 16 hand-made entries are kept as they are);
everything, including the low ones, goes into data/npc_wiki.json, and the
traders' goods lists into data/trader_stock_wiki.json by type id.

Wiki text is CC-BY-SA (https://lava-online.fandom.com/ru).

    wsl.exe -e python3 data/build_npc_wiki.py
"""
import collections
import html
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

WIKI = "https://lava-online.fandom.com/ru/wiki/"
ROLE_NAME = {0: "Mob", 1: "Trader", 2: "Teacher", 3: "Upgrader",
             4: "Commoner", 5: "Medic", 6: "Lessor", 7: "Auctioneer"}

# Which client class an offered service implies (quests.md §3).
SERVICE_ROLES = {
    "Торговля": {1}, "Ремонт": {1}, "Трофеи": {1},
    "Улучшения": {3}, "Улучшение": {3}, "Варианты улучшения": {3},
    "Лечение": {5}, "Прописка": {4, 5}, "Хранилище": {4},
    "Аренда транспорта": {6}, "Аукцион": {7}, "Обучение": {2},
}
CITIES = {"Вади-Хальфа", "Донгола", "Абри", "Абу-Хамед", "Мероэ",
          "Нубийская долина", "Тефнут", "Окрестности Мероэ", "Нубия",
          "Нубийская пустыня"}
# Every city ships its own copy of the market, the station, the masters'
# camp, and the client names the copies by region: WH_Gold_Traders_old
# against DN_Gold_Traders_old, wh_Pistols against dn_Rifles. The region is
# what tells six "Лагерь Мастеров" files apart, so it is read three ways:
# off the wiki link, off the file name, off the map cell.
CITY_ALIAS = {"Окрестности Мероэ": "Мероэ", "Нубия": "Нубийская долина",
              "Нубийская пустыня": "Нубийская долина", "Тефнут": "Мероэ"}
CITY_TOKENS = {
    "Вади-Хальфа": {"wh", "vh", "vadihalfa", "wadihalfa", "vadi", "wadi", "night"},
    "Донгола": {"dn", "dongola", "dangola"},
    "Абри": {"ab", "abri"},
    "Абу-Хамед": {"ah", "abuhamed", "abu"},
    "Мероэ": {"mr", "meroe", "tefnut", "me"},
    "Нубийская долина": {"nz", "noob", "noobia", "nubia", "noobzone"},
}
CITY_WORDS = {
    "Вади-Хальфа": ("вади", "хальф"), "Донгола": ("донгол",),
    "Абри": ("абри",), "Абу-Хамед": ("хамед",),
    "Мероэ": ("мероэ", "тефнут"), "Нубийская долина": ("нуби",),
}
# Where each city sits on the global map, from the cells already pinned in
# settlements.json (the two black markets are confirmed by playing).
CITY_CENTER = {"Вади-Хальфа": (5968, 1727), "Донгола": (5878, 2011),
               "Абри": (5861, 1835), "Абу-Хамед": (6182, 1976),
               "Мероэ": (6025, 1990), "Нубийская долина": (6268, 1825)}


def city_of_words(text):
    """The city a Russian title names, if any."""
    low = (text or "").lower().replace("ё", "е")
    for city, words in CITY_WORDS.items():
        if any(w in low for w in words):
            return city
    return None


def city_of_xy(xy):
    if not xy:
        return None
    best = min(CITY_CENTER.items(),
               key=lambda kv: abs(kv[1][0] - xy[0]) + abs(kv[1][1] - xy[1]))
    dist = abs(best[1][0] - xy[0]) + abs(best[1][1] - xy[1])
    return best[0] if dist <= 45 else None


def city_of_internal(internal):
    """The region prefix of an internal name: wh_Pistols -> Вади-Хальфа."""
    toks = re.split(r"[^A-Za-z]+", internal)
    head = [t.lower() for t in toks[:2] if t]
    for city, words in CITY_TOKENS.items():
        if head and head[0] in words:
            return city
    return None


# The client files the Tefnut temple and the Meroe oasis under AH_ with the
# rest of the east, so for the purpose of matching internal names those two
# cities are one region.
REGION = {"Абу-Хамед": "восток", "Мероэ": "восток"}


def same_region(a, b):
    return REGION.get(a, a) == REGION.get(b, b)
# A word in the page title that the internal name spells in English.
KEYWORDS = [
    ("пистолет-пулемет", ("submach",)), ("пистолет", ("pistol",)),
    ("дробовик", ("shotgun",)), ("винтовк", ("rifle",)),
    ("автомат", ("assrifle", "assaultrifle", "assault")),
    ("пулемет", ("machgun", "machinegun")), ("лотере", ("lotery",)),
    ("техногик", ("technogeek",)), ("техномастер", ("techmaster",)),
    ("патрон", ("ammo",)), ("аптек", ("med",)), ("лекар", ("med", "healer")),
    ("одежд", ("wear",)), ("точильн", ("modif_knifes", "knifes")),
    ("нож", ("knife",)), ("банк", ("bank",)),
    ("подмастерь", ("modif",)), ("мастер", ("master",)),
    ("торгов", ("trd", "trader")),
    ("транспорт", ("lessor", "travel")), ("аукцион", ("auction",)),
    ("охранник", ("guard", "secur")), ("билет", ("travel", "ticket")),
    ("контейнер", ("box", "container")), ("сейф", ("safe",)),
    ("шкафчик", ("locker", "box")), ("сундук", ("chest", "box")),
    ("ящик", ("box",)), ("вход", ("enter",)), ("выход", ("exit",)),
    ("сортиров", ("sorting",)), ("камень", ("stone", "rock")),
    ("руд", ("stone", "source")), ("верстак", ("table", "creator")),
    ("терминал", ("terminal",)), ("врач", ("healer", "doc")),
    ("доктор", ("doc", "dr")), ("тренер", ("trainer",)),
    ("инструктор", ("trainer", "teacher")), ("ремесленник", ("craft",)),
    ("шахтёр", ("miner",)), ("шахтер", ("miner",)),
]

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ы": "i", "ь": "", "э": "e", "ю": "u", "я": "a",
}


def skel(word):
    """Consonant skeleton of a name in either alphabet, for fuzzy equality.

    Spelling differs between the wiki and the files in every way a Russian
    name can be romanised -- Хасир against Hasseer, Кшиштоф against
    Kshishtoff, Однопальцый against Odnopalciy -- so vowels, doubled
    letters and the usual digraph choices are all thrown away first.
    """
    w = word.lower().replace("ё", "е")
    w = "".join(TRANSLIT.get(ch, ch) for ch in w)
    for a, b in (("kh", "h"), ("ch", "c"), ("sh", "s"), ("zh", "z"),
                 ("ts", "c"), ("ck", "k"), ("ph", "f"), ("th", "t"),
                 ("w", "v"), ("q", "k"), ("x", "ks"), ("y", "i"), ("j", "i")):
        w = w.replace(a, b)
    w = re.sub(r"[^a-z]", "", w)
    w = re.sub(r"[aeiou]", "", w)
    w = re.sub(r"(.)\1+", r"\1", w)
    return w.replace("c", "k")


# Tokens of an internal name that say what a thing is, not who it is.
NOISE = {"wh", "dn", "nz", "ah", "ab", "mr", "vh", "trd", "upg", "craft",
         "modif", "npc", "commoner", "bank", "trader", "healer", "lessor",
         "simple", "g", "pm", "in", "out", "old", "new", "event", "ny",
         "market", "the", "of", "and", "gift", "romantik", "clan", "noob",
         "noobia", "sceen", "admin", "test", "quest", "env", "kb", "loc",
         "ownloc", "np", "master", "trainer", "upgrader", "auctioneer"}


def tokens(internal):
    parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", internal)
    parts = re.split(r"[^A-Za-z]+", parts)
    return [p.lower() for p in parts if p]


def name_hit(title, internal):
    """2 when a word of the wiki title is the internal name's word, 1 when
    one is a prefix of the other (Фрэнк against Franks), 0 otherwise."""
    words = [w for w in re.split(r"[^А-Яа-яЁёA-Za-z]+", title) if len(w) >= 3]
    skels = {skel(w) for w in words}
    skels = {s for s in skels if len(s) >= 2}
    best = 0
    for tok in tokens(internal):
        if tok in NOISE:
            continue
        t = skel(tok)
        if len(t) < 2:
            continue
        for s in skels:
            if s == t:
                return 2
            if len(s) >= 4 and len(t) >= 4 and (s.startswith(t) or t.startswith(s)):
                best = 1
    return best


def keyword_hit(title, internal):
    """1 when a word of the title is what the internal name says in English;
    -1 when the internal name is the gold-currency copy (_g) and the title
    does not say so, since every market has both copies side by side."""
    low = title.lower().replace("ё", "е")
    flat = internal.lower().replace("_", "")
    gold_internal = internal.lower().endswith("_g") or "gold" in flat
    if "золот" in low:
        return 1 if gold_internal else 0
    hit = 0
    for word, toks in KEYWORDS:
        if word in low:
            # "пистолет-пулемет" must not also count as "пулемет", and a
            # machine-gun dealer is not the sub-machine-gun one.
            low = low.replace(word, " ")
            if word == "пулемет" and "submach" in flat:
                continue
            if any(t.replace("_", "") in flat for t in toks):
                hit = 1
    return -1 if gold_internal and not hit else hit


# --- wiki markup ---------------------------------------------------------

LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
XY = re.compile(r"(\d{4})\s*[xхХX×]\s*(\d{4})")


def sections(txt):
    """[(level, name, body)] for every == heading == of the page."""
    out = []
    pos = [(m.start(), m.end(), len(m.group(1)), m.group(2).strip().strip("'"))
           for m in re.finditer(r"^(=+)\s*(.+?)\s*=+\s*$", txt, re.M)]
    for i, (s, e, lvl, name) in enumerate(pos):
        end = pos[i + 1][0] if i + 1 < len(pos) else len(txt)
        out.append((lvl, name, txt[e:end]))
    return out


def links(body):
    return [(t.strip(), (l or t).strip()) for t, l in LINK.findall(body)
            if not t.startswith(("Категория:", "Файл:", ":Категория"))]


def norm(s):
    s = html.unescape(s).lower().replace("ё", "е")
    s = re.sub(r"<[^>]*>", " ", s)
    return re.sub(r"[^а-яa-z0-9 ]+", " ", s).strip()


def stems(title):
    return frozenset(w[:5] for w in title.split() if len(w) > 2)


def plain(body):
    s = LINK.sub(lambda m: m.group(2) or m.group(1), body)
    s = re.sub(r"<[^>]*>", " ", s)
    s = re.sub(r"'{2,}", "", s)
    return re.sub(r"\s+", " ", s).strip()


# --- the world side ------------------------------------------------------

def static_index():
    """id -> title/fn/war from data/exits_sides.json (already read off the XML)."""
    with io.open(os.path.join(HERE, "exits_sides.json"), encoding="utf-8") as fh:
        summary = json.load(fh)["summary"]
    return {int(k): v for k, v in summary.items()}


def settlement_cells():
    with io.open(os.path.join(HERE, "settlements.json"), encoding="utf-8") as fh:
        cells = json.load(fh)["cells"]
    return {tuple(int(v) for v in k.split(",")): loc for k, loc in cells.items()}


# Words that name the region rather than the place. Stripped before titles
# are compared, because the wiki writes "Вокзал Абу-Хамеда" where the file
# says "Абухамед: Вокзал", and both mean the station.
CITY_STEMS = {"вади", "хальф", "донго", "абри", "абу", "хамед", "абуха",
              "мероэ", "тефну", "нубии", "нубий", "нубия", "керма", "кермы"}
# Pairs the words alone cannot settle, settled by the file name instead:
# Vadihalfa0 is the old market and Vadihalfa_new the new one, both titled
# just "рынок" in the client.
ALIASES = {
    "Старый рынок Вади-Хальфы": [35], "Новый рынок Вади-Хальфы": [104],
    "Старый рынок Донголы": [50], "Новый рынок Донголы": [197],
    "Рынок Нубии": [185],
}


def place_stems(title):
    """The stems of a title minus the region words and roman numerals."""
    t = norm(title).replace("абухамед", "абу хамед")
    out = frozenset(w[:5] for w in t.split()
                    if len(w) > 2 and w[:5] not in CITY_STEMS)
    return out


class Resolver:
    """Wiki place (link title, map cell) -> static location ids."""

    def __init__(self, static, cells, wiki_locations, spawn_city=None):
        self.static = static
        self.cells = cells
        self.by_loc = collections.defaultdict(list)
        for cell, loc in cells.items():
            self.by_loc[loc].append(cell)
        self.by_title = collections.defaultdict(list)
        self.by_stem = collections.defaultdict(list)
        self.usable = []
        for loc_id, m in static.items():
            if "test" in m["fn"].lower():
                continue
            t = norm(m["title"])
            if t:
                self.usable.append(loc_id)
                self.by_title[t].append(loc_id)
                self.by_stem[place_stems(t)].append(loc_id)
        # A wiki location page's own coordinates, for places named by link only.
        self.wiki_xy = {}
        for title, txt in wiki_locations.items():
            m = XY.search(txt)
            if m:
                self.wiki_xy[title] = (int(m.group(1)), int(m.group(2)))
        # Region of a file: its name, its title, or failing both the region
        # its NPC spawns carry in their names (wh_*, dn_*, ...).
        self.file_city = {}
        for i, m in static.items():
            city = self._city_of_file(m)
            if city is None and spawn_city:
                city = spawn_city.get(i)
            self.file_city[i] = city

    @staticmethod
    def _city_of_file(meta):
        toks = [t.lower() for t in re.split(r"[^A-Za-z]+", meta["fn"]) if t]
        for tok in toks[:3]:
            for city, words in CITY_TOKENS.items():
                if tok in words:
                    return city
        return city_of_words(meta["title"])

    def near(self, xy, tol=3):
        if not xy:
            return []
        x, y = xy
        return sorted({loc for (cx, cy), loc in self.cells.items()
                       if abs(cx - x) <= tol and abs(cy - y) <= tol})

    def by_name(self, title):
        """Files whose title says the same place, region words aside."""
        if title in ALIASES:
            return list(ALIASES[title])
        t = norm(title)
        if not t:
            return []
        hits = set(self.by_title.get(t, ()))
        want = place_stems(t)
        if not want:
            return sorted(hits)
        hits |= set(self.by_stem.get(want, ()))
        if hits:
            return sorted(hits)
        # "Старый рынок Донголы" against "Донгола: Рынок": the file says
        # less than the wiki, never more.
        for have, ids in self.by_stem.items():
            if have and have <= want:
                hits.update(ids)
        if not hits:
            for have, ids in self.by_stem.items():
                if len(want) >= 1 and want <= have and len(have) <= len(want) + 1:
                    hits.update(ids)
        return sorted(hits)

    def resolve(self, link, xy, city=None):
        """(loc_ids, how, city). Named first, the cell second, both is best;
        among files sharing a title the region decides."""
        if not xy and link in self.wiki_xy:
            xy = self.wiki_xy[link]
        city = CITY_ALIAS.get(city, city) or city_of_words(link) or city_of_xy(xy)
        named = self.by_name(link) if link else []
        if named and city:
            # Copies built for another region are not this place.
            named = [i for i in named if self.file_city[i] in (None, city)]
            same = [i for i in named if self.file_city[i] == city]
            if same:
                named = same
        near = self.near(xy)
        if named and near:
            both = [i for i in named if i in near]
            if both:
                return both, "title+cell", city
        if named:
            # Several files share a title (a night copy, a war copy): keep
            # the peaceful ones, which is where the map leads.
            calm = [i for i in named if not self.static[i]["war"]]
            return (calm or named), "title", city
        if near and not link:
            # A named place the files do not know is not turned into its
            # neighbour on the map; only a bare cell falls back to the cell.
            return near, "cell", city
        return [], "none", city


def npc_spawns(loc_id, mt):
    """[(type_id, root, internal)] of the non-mob spawns in a location."""
    try:
        loc = world.location(loc_id)
    except Exception:
        return []
    out, seen = [], set()
    for _cell, tid in loc.spawns:
        if tid in seen or tid not in mt:
            continue
        seen.add(tid)
        root, name, _res = mt[tid]
        if root != 0:
            out.append((tid, root, name))
    return out


# --- parsing an NPC page ---------------------------------------------------

def parse_npc(title, txt):
    secs = sections(txt)
    rec = {"description": "", "coords": [], "services": [], "quests": [],
           "trade": {}, "rent": [], "sublocations": []}
    trade_ctx = None
    for lvl, name, body in secs:
        key = name.replace(":", "").strip()
        if key.startswith("Описание"):
            rec["description"] = plain(body)[:600]
        elif key.startswith("Координат") or (lvl == 2 and key in CITIES):
            for line in body.splitlines():
                if not line.strip():
                    continue
                ls = links(line)
                m = XY.search(line)
                xy = (int(m.group(1)), int(m.group(2))) if m else None
                if not ls and not xy:
                    continue
                city = next((t for t, _l in ls if t in CITIES), None)
                place = next((t for t, _l in ls if t not in CITIES), None)
                if key in CITIES and not city:
                    city = key
                rec["coords"].append({"city": city, "location": place, "xy": xy})
        elif key == "Услуги":
            trade_ctx = None
        elif key in SERVICE_ROLES or key.startswith("Торгов"):
            rec["services"].append(key)
            if key.startswith("Торгов"):
                trade_ctx = "*"
                rec["trade"].setdefault("*", [])
                rec["trade"]["*"] += [t for t, _l in links(body)]
            elif key.startswith("Аренда"):
                rec["rent"] += [t for t, _l in links(body)]
        elif lvl >= 4 and trade_ctx and key not in SERVICE_ROLES:
            # ====Абри==== under Торговля: the stock of that city's copy.
            rec["trade"].setdefault(key, [])
            rec["trade"][key] += [t for t, _l in links(body)]
        elif key.startswith("Квест"):
            rec["quests"] += [t for t, _l in links(body)]
        elif key == "Локации":
            rec["sublocations"] += [t for t, _l in links(body)]
    if not rec["coords"]:
        # Coordinates written outside any section, or the page is a stub.
        m = XY.search(txt)
        if m:
            rec["coords"].append({"city": None, "location": None,
                                  "xy": (int(m.group(1)), int(m.group(2)))})
    if rec["trade"].get("*") == []:
        del rec["trade"]["*"]
    return rec


def roles_for(services):
    roles = set()
    for s in services:
        roles |= SERVICE_ROLES.get(s, set())
    return roles


def display_name(title):
    """The name to show in the client: the page title minus disambiguators."""
    name = re.sub(r"\s*\((ВХ|ДН|АХ|АБ|МР|Абри|Донгола|Вади-Хальфа|Абу-Хамед|Мероэ)\)\s*$", "", title)
    name = re.sub(r"\s+(ВХ|ДН|АХ|АБ|МР)$", "", name)
    return name.strip()


def dump(path, obj):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def main():
    with io.open(os.path.join(HERE, "wiki_world", "npc.json"), encoding="utf-8") as fh:
        npc_pages = json.load(fh)["pages"]
    with io.open(os.path.join(HERE, "wiki_world", "locations.json"), encoding="utf-8") as fh:
        loc_pages = json.load(fh)["pages"]
    with io.open(os.path.join(HERE, "npc_names.json"), encoding="utf-8") as fh:
        existing = json.load(fh)
    # Only the hand-made entries are trusted over the wiki: those written
    # before this script existed (no confidence map) or marked verified.
    # Everything else in the file is this script's own earlier output and
    # is recomputed, so a rerun never grows more certain than the wiki is.
    trusted = {k: v for k, v in existing["names"].items()
               if existing.get("confidence", {}).get(k, "verified") == "verified"}

    mt = world.mob_types()
    static = static_index()

    # The region of a file that names none: the region its inhabitants
    # carry in their names, when two or more of them agree.
    spawn_cache = {}
    spawn_city = {}
    for loc_id in static:
        spawn_cache[loc_id] = npc_spawns(loc_id, mt)
        votes = collections.Counter(
            city_of_internal(name) for _t, _r, name in spawn_cache[loc_id])
        votes.pop(None, None)
        if votes:
            city, n = votes.most_common(1)[0]
            if n >= 2 and n > sum(votes.values()) / 2:
                spawn_city[loc_id] = city
    resolver = Resolver(static, settlement_cells(), loc_pages, spawn_city)

    # Wiki location pages list their NPCs; the reverse index places an NPC
    # whose own page names no location.
    npc_on_page = collections.defaultdict(set)
    for ltitle, txt in loc_pages.items():
        for lvl, name, body in sections(txt):
            if name.upper().startswith("NPC") or name.startswith("НПС"):
                for t, _l in links(body):
                    npc_on_page[t].add(ltitle)

    # "NPC дающий задание: [[Мастер Фахад]] улучшение пистолет-пулеметов" --
    # the quest pages say which weapon each master of a camp improves.
    specialty = {}
    quests_path = os.path.join(HERE, "wiki_world", "quests.json")
    if os.path.exists(quests_path):
        with io.open(quests_path, encoding="utf-8") as fh:
            for txt in json.load(fh)["pages"].values():
                for who, what in re.findall(
                        r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*улучшени[ея]\s+([а-яё\-]+)",
                        txt, re.I):
                    specialty.setdefault(who.strip(), what.lower())

    npcs = {}
    for title, txt in npc_pages.items():
        rec = parse_npc(title, txt)
        rec["specialty"] = specialty.get(title, "")
        if not rec["coords"]:
            for ltitle in sorted(npc_on_page.get(title, ())):
                rec["coords"].append({"city": None, "location": ltitle, "xy": None})
        rec["roles"] = sorted(roles_for(rec["services"]))
        npcs[title] = rec

    # Every (page, place, candidate type) with a score, then a greedy
    # assignment so that no type id is handed to two pages.
    proposals = []
    for title, rec in npcs.items():
        roles = set(rec["roles"])
        # The masters of the weapon camps are told apart by the weapon they
        # improve, which only the quest pages say; it is matched like a
        # word of the title (Мастер Фахад ~ dn_trmodif_submachgun_pm).
        match_title = title + " " + rec.get("specialty", "")
        places = []
        for c in rec["coords"]:
            loc_ids, how, city = resolver.resolve(c["location"], c["xy"], c["city"])
            place = dict(c, city=city, loc_ids=loc_ids, how=how, candidates=[])
            for loc_id in loc_ids:
                if loc_id not in spawn_cache:
                    spawn_cache[loc_id] = npc_spawns(loc_id, mt)
                for tid, root, internal in spawn_cache[loc_id]:
                    # A type named by hand belongs to the page that carries
                    # that name and to no other.
                    is_trusted = str(tid) in trusted
                    if is_trusted and trusted[str(tid)] not in title:
                        continue
                    score = 0.0
                    role_ok = (root in roles) if roles else (root == 4)
                    if roles and root not in roles:
                        score -= 3
                    score += 3 if role_ok else 0
                    hit = name_hit(match_title, internal)
                    kw = keyword_hit(match_title, internal)
                    score += {0: 0, 1: 4, 2: 5}[hit]
                    score += 2 * kw
                    if how == "title+cell":
                        score += 1
                    icity = city_of_internal(internal)
                    city_ok = None
                    if icity and city:
                        city_ok = same_region(icity, city)
                        score += 2 if city_ok else -2
                    # Among equals the plainer name: Dr_Gofus over
                    # Dr_Gofus_senior_assistent, wh_Frank over wh_Franks_Child.
                    score -= 0.1 * len(tokens(internal))
                    if is_trusted:
                        score += 10
                    place["candidates"].append({
                        "type_id": tid, "internal": internal, "loc_id": loc_id,
                        "root": ROLE_NAME[root], "score": round(score, 1),
                        "name_hit": hit, "keyword_hit": kw, "role_ok": role_ok,
                        "city_ok": city_ok, "trusted": is_trusted})
            place["candidates"].sort(key=lambda c: -c["score"])
            places.append(place)
        rec["places"] = places
        del rec["coords"]
        for pi, place in enumerate(places):
            for cand in place["candidates"]:
                proposals.append((cand["score"], title, pi, cand))

    proposals.sort(key=lambda p: (-p[0], p[1], p[2]))
    taken_types, taken_places = {}, {}
    for score, title, pi, cand in proposals:
        if cand["type_id"] in taken_types or (title, pi) in taken_places:
            continue
        if score < 0:
            continue
        taken_types[cand["type_id"]] = (title, pi)
        taken_places[(title, pi)] = cand

    # Confidence: a name or goods match with the right class is as good as
    # this gets; a lone spawn of the right class is nearly so; a pick among
    # several same-class spawns is a guess and stays out of the client.
    bound = 0
    for title, rec in npcs.items():
        for pi, place in enumerate(rec["places"]):
            cand = taken_places.get((title, pi))
            if not cand:
                place["type_id"] = None
                place["confidence"] = "none" if place["loc_ids"] else "unresolved"
                continue
            # Rivals: spawns of the right class in the same region. A pick
            # that had none is as safe as a name match; one that had rivals
            # is a guess.
            rivals = [c for c in place["candidates"]
                      if c["role_ok"] and c["city_ok"] is not False
                      and c["type_id"] != cand["type_id"]]
            sure = cand["role_ok"] and cand["city_ok"] is not False
            if cand["trusted"]:
                conf = "verified"
            elif sure and (cand["name_hit"] == 2 or cand["keyword_hit"] > 0):
                conf = "high"
            elif sure and cand["name_hit"] == 1:
                conf = "medium" if not rivals else "low"
            elif sure and not rivals and place["how"] != "cell":
                # A map cell alone is three cells wide and lands on the
                # neighbour as often as on the place; without a name it
                # proves nothing.
                conf = "medium"
            else:
                conf = "low"
            place["type_id"] = cand["type_id"]
            place["internal"] = cand["internal"]
            place["confidence"] = conf
            bound += 1

    # --- npc_names.json: keep the sixteen, add what is trusted ------------
    names = dict(trusted)
    internal = {k: v for k, v in existing.get("internal", {}).items() if k in trusted}
    confidence = {k: "verified" for k in names}
    source = {k: existing.get("source", {}).get(k, existing.get("_source", WIKI))
              for k in names}
    for title, rec in npcs.items():
        for place in rec["places"]:
            tid = place.get("type_id")
            if tid is None or place["confidence"] not in ("high", "medium", "verified"):
                continue
            key = str(tid)
            if key in trusted:
                continue
            names[key] = display_name(title)
            internal[key] = place["internal"]
            confidence[key] = place["confidence"]
            source[key] = WIKI + title.replace(" ", "_")
    dump(os.path.join(HERE, "npc_names.json"), {
        "_note": existing.get("_note", ""),
        "_source": existing.get("_source", WIKI),
        "_built": "The entries beyond the original sixteen come from "
                  "data/build_npc_wiki.py: wiki page -> location -> spawn of "
                  "the right class -> name. confidence: verified (played), "
                  "high (name or goods match), medium (only spawn of that "
                  "class there). Low picks stay in data/npc_wiki.json.",
        "names": dict(sorted(names.items(), key=lambda kv: int(kv[0]))),
        "internal": dict(sorted(internal.items(), key=lambda kv: int(kv[0]))),
        "confidence": dict(sorted(confidence.items(), key=lambda kv: int(kv[0]))),
        "source": dict(sorted(source.items(), key=lambda kv: int(kv[0]))),
    })

    # --- npc_wiki.json: everything, for the next pass -------------------
    dump(os.path.join(HERE, "npc_wiki.json"), {
        "_": "One record per wiki NPC page (CC-BY-SA, %s). places[]: each "
             "coordinate line of the page resolved to static location ids "
             "(how: title+cell / title / cell), the candidate spawns there "
             "with scores, and the chosen type_id with confidence. Built by "
             "data/build_npc_wiki.py." % WIKI,
        "npcs": npcs,
    })

    # --- trader_stock_wiki.json --------------------------------------------
    by_type, unbound = {}, {}
    for title, rec in npcs.items():
        if not rec["trade"]:
            continue
        placed = False
        for place in rec["places"]:
            tid = place.get("type_id")
            if tid is None:
                continue
            city = place.get("city")
            stock = rec["trade"].get(city) or rec["trade"].get("*")
            if not stock:
                # City sections named by the market, not the city.
                stock = next(iter(rec["trade"].values()))
            by_type[str(tid)] = {"npc": title, "city": city,
                                 "confidence": place["confidence"],
                                 "items": sorted(set(stock))}
            placed = True
        if not placed:
            unbound[title] = {k: sorted(set(v)) for k, v in rec["trade"].items()}
    dump(os.path.join(HERE, "trader_stock_wiki.json"), {
        "_": "Trader type_id -> the goods the wiki lists under Торговля for "
             "that NPC (item page titles; map them to type ids through "
             "data/wiki_links.json when it exists). unbound: pages whose NPC "
             "has no type id yet. Built by data/build_npc_wiki.py.",
        "by_type": by_type, "unbound": unbound,
    })

    # --- report -----------------------------------------------------------
    n_places = sum(len(r["places"]) for r in npcs.values())
    resolved = sum(1 for r in npcs.values() for p in r["places"] if p["loc_ids"])
    conf = collections.Counter(p["confidence"] for r in npcs.values() for p in r["places"])
    pages_bound = sum(1 for r in npcs.values()
                      if any(p.get("type_id") for p in r["places"]))
    print("NPC pages: %d, places: %d, places with a location: %d" %
          (len(npcs), n_places, resolved))
    print("places by confidence:", dict(conf))
    print("pages with at least one type_id: %d" % pages_bound)
    print("npc_names.json: %d names (was %d)" % (len(names), len(existing["names"])))
    print("trader stock: %d type ids, %d unbound pages" % (len(by_type), len(unbound)))


if __name__ == "__main__":
    main()
