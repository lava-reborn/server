"""Place the map's named cells onto location files by weighing every clue.

The client draws 414 tooltips on the global map (res/database/locations.xml)
and opens, on any cell, whatever location id the server names in lcall. The
table behind that -- cell -> file in res/locations/static -- lived on the
server and is gone. data/build_settlements.py rebuilt part of it by matching
tooltip names to file titles; names alone put several cells on the wrong
copy of a place, and every correction had to be typed into
data/settlements_verified.json by hand.

This script scores EVERY usable file against EVERY named cell on independent
clues, adds them up, and takes the leader only when it leads the runner-up
by a margin. Where nothing leads, the cell stays open desert, which the
client resolves by itself. The clues, each written out per cell in
data/settlements_report.md so a player who remembers the game can check
them:

  name      tooltip's first line against the file title, compared as word
            stems (four letters, five for long words, prefix-matched) with
            the city words removed and word order ignored; a match on
            kind-words alone (лагерь, оазис, рынок, мастера) is worth
            little, numbers never match on their own, and a title naming
            the same city as the tooltip earns a little more. A qualifier
            the tooltip adds (старый/новый/северный/южный/верхний/нижний)
            has to be confirmed by the file's own name, or by the name of
            its twin drawn from the same art -- Vadihalfa0 is the old market
            because Night_WH_OldMarket draws the same background -- and is
            punished when the file name says the opposite. A title that is
            a part of a place (a mine tier, a prison block) yields to the
            whole.
  wiki      a location article on the fan wiki standing within 3 cells whose
            title is the tooltip's name; weaker when only the coordinates
            agree and the article names something else on the same cell.
  npc       an NPC article within 3 cells whose type id is known at medium
            confidence or better (data/npc_names.json), counted for every
            file whose spawn list holds that type id or its look-alike (the
            same internal name up to a _pm/_g suffix: the wiki cannot tell
            the premium master from the plain one). This is what tells the
            black market (file 102) from the old market (35): the wiki
            writes all the stalls on one cell, but their type ids stand in
            102. The wiki's city coordinates are coarse, so this counts in
            full only for a file the tooltip's name also fits; otherwise a
            quarter.
  resident  a word of the tooltip that is the name of an inhabitant, by
            consonant skeleton: Бензоколонка ~ nz_Benzokolonka, Генри Мл.
            ~ wh_HenryJr.
  services  what the tooltip promises against who lives in the file: Банк
            against a commoner named *bank*, Аренда транспорта against a
            LESSOR, Лекарь against a HEALER, Обучение against a TEACHER,
            Аукцион against an AUCTIONEER, Торговцы оружием against
            wh_Pistols/dn_Rifles/..., Добыча меди against a Copper mine, the
            (A)/(G)/(P) variants against plain, _g and _pm inhabitants, and
            so on (SERVICES below, read off the spawn names the files use).
  region    the city the cell lies in (the tooltip's own words, or the
            nearest city core found from the tooltips that name one)
            against the city the file was built for (fn prefix WH_/DN_/AH_/
            Abri_/kr_..., title, or the prefixes of its inhabitants).
  calm      the peaceful (war=0) copy of a place is where the map leads.
  event     quest, seasonal, clan-base, border-tile and test files are not
            settlements; test files are dropped outright.
  family    identically titled files numbered within one city (WH_district1/
            4/7) against identically named cells numbered within that city
            (Ремесленники по одежде 6/7/8 уровень): paired in rank order.
  interior  a file with no map-edge exit (only doors a/b) cannot stand on a
            map cell at all. This is what settles the fourteen "Лагерь
            Джанджавидов": thirteen Up_Camp_*LVL boss rooms have only door a,
            the base camp Bandit_Camp3 has all four edges.
  clones    files identical in title, name, art, war and exits (109 and 982
            are both stok_WH_ug) are one candidate, the lowest id.

Placement is greedy from the highest score down, one file to one place: a
file already standing somewhere may take another cell only within 3 steps
of a cell it already holds, only under the same name, and at a discount (a
settlement may be wide, or a strip like the five cells of Ущелье Смерти,
but three adjacent "Лагерь мастеров" are three camps). Nothing is placed on
a name-less clue alone. data/settlements_verified.json overrides everything
and must be reproduced; the report says whether the clues would have found
each verified cell on their own.

    wsl.exe -e python3 data/place_settlements.py
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
sys.path.insert(0, HERE)
import world  # noqa: E402
from build_npc_wiki import NOISE, XY, links, sections, skel, tokens  # noqa: E402

ADJACENT = 3      # Manhattan steps a settlement may span cell to cell
NEAR = 3          # Chebyshev tolerance of the wiki's coordinates
CITY_RADIUS = 40  # how far from a city core a cell still counts as its
CORE = 6          # how close tooltips naming a city have to be to form its core
RARE = 20         # a file-name word in at most this many files names a place
KIN = 3           # Chebyshev reach of a placed neighbour sharing such a word

# --- weights ---------------------------------------------------------------
W = dict(
    name_exact=6.0, name_super=4.0, name_sub=3.0, name_partial=1.5,
    name_generic=3.0, name_kind=2.0,
    qual_ok=2.0, qual_bad=-4.0, qual_unknown=-0.5,
    city_ok=1.5, number_bad=-3.0, number_only=-1.0, part=-1.5,
    full_match=1.5, qual_same=1.0,
    wiki_loc=(5.0, 4.0, 3.0),   # by distance 0, 1, 2..3
    wiki_cell=3.0,              # article on this very cell, other name
    npc=(3.0, 2.5), npc_cap=6.0, npc_unnamed=0.25,
    resident=3.0, resident_cap=4.0,
    service=1.0, service_specific=2.0, service_cap=6.0, service_miss=-0.5,
    variant_ok=1.0, premium_ok=2.0, premium_missing=-1.0, premium_only=-3.0,
    region_ok=3.0, region_near=1.5, region_bad=-4.0,
    calm=2.0, event=-2.0,
    family=4.0, family_other=-2.0,
    extra_cell=-2.0, neighbour=1.5, neighbour_cap=3.0,
)
# Verdicts
CONFIDENT_SCORE, CONFIDENT_MARGIN = 9.0, 3.0
WEAK_SCORE, WEAK_MARGIN = 4.0, 1.5

# --- words -----------------------------------------------------------------
GENERIC_TITLES = {"пустошь", "скалы", "пустыня", "побережье", ""}
CITY_WORDS = {"Вади-Хальфа": ("вади", "халь"), "Донгола": ("донг",),
              "Абри": ("абри",), "Абу-Хамед": ("хаме", "абух"),
              "Мероэ": ("меро", "тефн"), "Нубийская долина": ("нуби",),
              "Керма": ("керм",)}
CITY_TOKENS = {
    "Вади-Хальфа": {"wh", "vh", "vadihalfa", "wadihalfa", "vadi", "wadi", "night"},
    "Донгола": {"dn", "dongola", "dangola"},
    "Абри": {"ab", "abri"},
    "Абу-Хамед": {"ah", "abuhamed", "abu"},
    "Мероэ": {"mr", "meroe", "tefnut", "tf", "me"},
    "Нубийская долина": {"nz", "noob", "noobia", "nubia", "noobzone"},
    "Керма": {"kr", "kerma"},
}
# The client files the east as one region: Tefnut's temple and the Meroe
# oasis are AH_ files.
REGION = {"Абу-Хамед": "восток", "Мероэ": "восток"}

# fn tokens of files that were never a settlement on the map: quests,
# seasons, clan bases, border tiles.
EVENT_TOKENS = {"q", "test", "9may", "ny", "hw", "hws", "vdv", "apoc", "apoc1",
                "apoc2", "apoc3", "admin", "event", "valentines", "fevral23",
                "il", "usm", "invaider", "invaiders", "invaders", "hq", "b",
                "nopvp", "mw", "e", "vov", "vbg", "ves", "kb", "tir"}


def stem(w):
    """Four letters, five of a long word, a three-letter word whole."""
    if w.isdigit():
        return w
    if len(w) >= 7:
        return w[:5]
    if len(w) >= 4:
        return w[:4]
    return w


# Spelled one way on the map and another in the files.
SYNONYMS = {stem("порт"): stem("причал"), stem("аванпост"): stem("лагерь"),
            stem("вещевой"): stem("торговцы"), stem("тюремный"): stem("тюрьма"),
            stem("гараж"): stem("автохозяйство")}
# Kinds of place and of people; sharing one of these is no evidence of the
# same place: every city has its лагерь мастеров and its ремесленники.
GENERIC = {stem(w) for w in (
    "лагерь база поселок деревня оазис рынок лавка ферма пещера дорога пост "
    "шахта склад дом место точка станция стоянка завод центр площадка хижина "
    "бункер штаб зона город квартал вход выход уровень часть камера блок двор "
    "ремесленники торговцы мастера").split()}
CITY_STEMS = {stem(w) for w in (
    "вади хальфа хальфы донгола донголы абри абу хамед хамеда абухамед мероэ "
    "тефнут нубии нубийская нубийской нубия керма кермы керме").split()}
QUAL = [("стар", "old"), ("нов", "new"), ("север", "north"), ("южн", "south"),
        ("восто", "east"), ("запад", "west"), ("верхн", "up"), ("нижн", "down"),
        ("дальн", "far")]
FN_QUAL = {"old": {"old"}, "new": {"new"},
           "north": {"north", "sever", "nord", "n"},
           "south": {"south", "ug", "yug", "s"},
           "east": {"east", "vostok", "e"}, "west": {"west", "zapad", "w"},
           "up": {"up", "top", "upper"}, "down": {"down", "dwn", "bottom", "lower"},
           "far": {"far", "d"}}
OPPOSITE = {"old": "new", "new": "old", "north": "south", "south": "north",
            "east": "west", "west": "east", "up": "down", "down": "up"}
# Words that make a title a part of a place: mine tiers, prison cells.
PART = {stem(w) for w in ("ярус", "ярусы", "этаж", "камеры", "тунели", "туннели",
                          "тоннель", "тоннели")}


def qualifier(s):
    if s.startswith("новог"):
        return None
    for pre, q in QUAL:
        if s.startswith(pre):
            return q
    return None


def is_generic(s):
    return any(s.startswith(g) or g.startswith(s) for g in GENERIC) and not s.isdigit()


def same_stem(a, b):
    if a.isdigit() or b.isdigit():
        return a == b
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


# What a tooltip promises -> the flag a file's inhabitants must carry.
# hard: a class the client builds (bank, lessor, ...); its absence counts.
SERVICES = [
    (r"банк", "bank", True), (r"аренд", "lessor", True),
    (r"лекар", "healer", True), (r"обучени", "teacher", True),
    (r"аукцион", "auction", True),
    (r"улучшени|мастера|мастеров|ремесленник", "upgrader", False),
    (r"оружи", "guns", False), (r"патрон", "ammo", False),
    (r"одежд|снаряж|брон|сетов|сеты", "wear", False),
    (r"медикамент|стимулятор|аптек", "med", False),
    (r"чертеж", "blueprint", False), (r"трофе", "trophy", False),
    (r"лотере", "lottery", False), (r"гофус", "gofus", False),
    (r"золотых слитков|обмен золот", "goldexchange", False),
    (r"каменоломн", "quarry", False),
    (r"водител|перевозчик|транспортировк|поездк|отправк", "travel", False),
    (r"казначе", "treasurer", False),
    (r"автомат", "assault", False), (r"(?<!пистолет-)пулемет", "machinegun", False),
    (r"винтов", "rifle", False), (r"пистолет-пулемет|\bпп\b", "submach", False),
    (r"пистолет(?!-)", "pistol", False), (r"дробовик", "shotgun", False),
    (r"свинц", "lead", False), (r"\bмеди\b|медь", "copper", False),
    (r"селитр", "nitre", False), (r"переработ", "recycling", False),
    (r"боеприпас", "ammo", False), (r"алмаз", "diamond", False),
]
# Promises that name one thing rather than a class of shop: the weapon a
# master improves, the ore a mine yields. Worth twice a generic match.
SPECIFIC = {"assault", "machinegun", "rifle", "submach", "pistol", "shotgun",
            "lead", "copper", "nitre", "diamond", "trophy", "quarry", "gofus",
            "treasurer", "goldexchange", "blueprint"}
# Flags a file carries in its own name rather than its inhabitants.
FN_FLAGS = {"plumbum": "lead", "copper": "copper", "nitre": "nitre",
            "bullet": "ammo", "bulletworkshop": "ammo", "refactoring": "recycling",
            "orerefinery": "recycling", "diamond": "diamond", "arenda": "lessor",
            "upgraders": "upgrader", "butchers": "trophy", "sets": "wear"}


def flags_of(name, root):
    """The service flags one inhabitant carries, from its internal name."""
    n = name.lower()
    out = set()
    if root == world.COMMONER and ("bank" in n or "bankir" in n):
        out.add("bank")
    if root == world.LESSOR or "lessor" in n:
        out.add("lessor")
    if root == world.HEALER or "healer" in n or "medic" in n:
        out.add("healer")
    if root == world.TEACHER or "trainer" in n:
        out.add("teacher")
    if root == world.AUCTIONER or "auction" in n:
        out.add("auction")
    if root == world.UPGRADER or "modif" in n or "_upg" in n or "upgrader" in n:
        out.add("upgrader")
    if root == world.TRADER and re.search(
            r"pistol|rifle|shotgun|submach|assault|machgun|machingun|machinegun|_w_trd|guns", n):
        out.update(("guns", "ammo"))
    if "ammo" in n or "bullet" in n:
        out.add("ammo")
    if "assrifle" in n or "assault" in n:
        out.add("assault")
    elif "rifle" in n:
        out.add("rifle")
    if "shotgun" in n:
        out.add("shotgun")
    if "submach" in n or "sub_machine" in n:
        out.add("submach")
    elif re.search(r"machingun|machgun|machine_gun|machinegun", n):
        out.add("machinegun")
    if re.search(r"(^|_)pistol", n):
        out.add("pistol")
    if re.search(r"wear|set_trd|_set|sets|armor", n):
        out.add("wear")
    if re.search(r"(^|_)med(_|$)|med_|gofus|healtrader", n):
        out.add("med")
    if "gofus" in n:
        out.add("gofus")
    if re.search(r"technogeek|convert|_bp|blueprint", n):
        out.add("blueprint")
    if "butcher" in n or "troph" in n:
        out.add("trophy")
    if "lotery" in n or "lottery" in n:
        out.add("lottery")
    if "goldexchange" in n or "gold_exchange" in n:
        out.add("goldexchange")
    if "stone_owner" in n:
        out.add("quarry")
    if re.search(r"travel|bus_driver|driver|taxi", n):
        out.add("travel")
    if "kaznachei" in n or "craft_bank" in n:
        out.add("treasurer")
    if "plumbum" in n:
        out.add("lead")
    if "copper" in n:
        out.add("copper")
    if "nitre" in n:
        out.add("nitre")
    if "sorting" in n or "refactor" in n or "refinery" in n:
        out.add("recycling")
    if "diamond" in n:
        out.add("diamond")
    return out


def variant_of(name):
    """'pm', 'g' or 'plain' for a shop inhabitant, None for anyone else."""
    n = name.lower()
    if not re.search(r"modif|upg|trd|trader|pistol|rifle|shotgun|submach|machgun|machingun", n):
        return None
    if n.endswith("_pm") or "_pm_" in n:
        return "pm"
    if n.endswith("_g"):
        return "g"
    return "plain"


def family_of(name):
    """The internal name up to the variant suffix, trmodif folded into
    modif: the wiki's Мастер Самир is dn_trmodif_assrifle_pm to one editor
    and dn_modif_assrifle to the next."""
    n = re.sub(r"_(pm|g|p)$", "", name.lower())
    return n.replace("trmodif", "modif")


# --- text ------------------------------------------------------------------
LOOKALIKE = str.maketrans("abcekmopxyth", "авсекморхутн")


def norm(s):
    """Lower case, ё folded, tags and punctuation out, Latin look-alikes in
    Cyrillic words folded (the client spells one camp "Лагерь Cеверного
    Альянаса" with a Latin C)."""
    s = html.unescape(s).lower().replace("ё", "е")
    s = re.sub(r"<[^>]*>", " ", s)
    s = s.replace("абухамед", "абу хамед")
    words = []
    for w in re.sub(r"[^а-яa-z0-9 ]+", " ", s).split():
        if re.search(r"[а-я]", w) and re.search(r"[a-z]", w):
            w = w.translate(LOOKALIKE)
        words.append(w)
    return " ".join(words)


def split_words(text):
    """(stems, city stems) of a normalised text."""
    out, cities = set(), set()
    for w in text.split():
        if len(w) < 3 and not w.isdigit():
            continue
        st = stem(w)
        st = SYNONYMS.get(st, st)
        if st in CITY_STEMS:
            cities.add(st)
        else:
            out.add(st)
    return frozenset(out), frozenset(cities)


def numbers(text):
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


def fn_tokens(fn):
    """Words of a file name, camel case split: Night_WH_OldMarket ->
    night, wh, old, market -- the old is what confirms Старый рынок."""
    fn = re.sub(r"([a-z])([A-Z])", r"\1 \2", fn)
    return [t.lower() for t in re.split(r"[^A-Za-z0-9]+", fn) if t]


def fn_number(fn):
    m = re.search(r"(\d+)[A-Za-z_]*$", fn)
    return int(m.group(1)) if m else None


def city_of_text(text):
    for city, words in CITY_WORDS.items():
        if any(w in text for w in words):
            return city
    return None


def city_of_internal(name):
    head = [t.lower() for t in re.split(r"[^A-Za-z]+", name)[:2] if t]
    for city, toks in CITY_TOKENS.items():
        if head and head[0] in toks:
            return city
    return None


def same_region(a, b):
    return REGION.get(a, a) == REGION.get(b, b)


def skeletons(text):
    """Consonant skeletons of the words of a tooltip that could be a
    person's name: four letters or more, not a kind-word, not a city."""
    out = set()
    for w in text.split():
        if len(w) < 4 or w.isdigit():
            continue
        st = stem(w)
        if is_generic(st) or st in CITY_STEMS or qualifier(st):
            continue
        s = skel(w)
        if len(s) >= 3:
            out.add(s)
    return out


# --- name score ------------------------------------------------------------
def matched(A, B):
    """Stems of A that some stem of B matches (prefix-wise)."""
    return {a for a in A if any(same_stem(a, b) for b in B)}


def name_score(head, title, fn_toks):
    """(score, note) for a tooltip name against a file title.

    fn_toks are the tokens of the file's own name and of its twins', which
    is where a qualifier the map adds may be confirmed or contradicted.
    """
    H, hc = split_words(head)
    T, tc = split_words(title)
    if (not H and not T) or (not H and not hc) or (not T and not tc):
        return 0.0, ""
    qh = {qualifier(s) for s in H if qualifier(s) and not matched({s}, T)}
    qt = {qualifier(s) for s in T if qualifier(s) and not matched({s}, H)}
    Hp = frozenset(s for s in H if not (qualifier(s) and not matched({s}, T)))
    Tp = frozenset(s for s in T if not (qualifier(s) and not matched({s}, H)))
    # Numbers tell copies apart (Боевая Арена 1 / 2) but never make a match
    # on their own: "Блок-пост №6" is not "Улучшение сетов 6-8".
    dh, dt = {s for s in Hp if s.isdigit()}, {s for s in Tp if s.isdigit()}
    Hp, Tp = Hp - dh, Tp - dt
    # Qualifiers both sides share (Северный склад / Северный блок) agree
    # without naming anything: they are kept out of the real words.
    rh = {s for s in Hp if not is_generic(s) and not qualifier(s)}
    rt = {s for s in Tp if not is_generic(s) and not qualifier(s)}
    score, note = 0.0, ""
    if rh and rt:
        mh, mt = matched(rh, rt), matched(rt, rh)
        if mh == rh and mt == rt:
            score, note = W["name_exact"], "="
        elif mt == rt:
            score, note = W["name_super"], "⊃"
        elif mh == rh:
            score, note = W["name_sub"], "⊂"
        elif mh:
            score, note = W["name_partial"], "~"
        else:
            return 0.0, ""
    elif rh and not rt:
        # A file titled by its kind alone ("Лагерь", "лагерь Мастеров")
        # under a fuller map name sharing that kind.
        if Tp and matched(Tp, Hp) == Tp:
            score, note = W["name_kind"], "⊃kind"
        elif Tp and matched(Tp, Hp):
            score, note = W["name_kind"] / 2, "~kind"
        else:
            return 0.0, ""
    elif rt and not rh:
        if Hp and matched(Hp, Tp) == Hp:
            score, note = W["name_partial"], "⊂kind"
        else:
            return 0.0, ""
    else:
        # Both are kind-words only ("Оазис" / "Оазис"), or a bare city name
        # against a file titled by that city and a kind ("Мероэ" / "Мероэ:
        # рынок").
        if Hp and Tp and matched(Hp, Tp) == Hp and matched(Tp, Hp) == Tp:
            score, note = W["name_generic"], "=kind"
        elif Hp and Tp and matched(Hp, Tp) == Hp:
            # "Центр Абу-Хамеда" under "Абу-Хамед: Центр города".
            score, note = W["name_partial"], "⊂kind"
        elif not Hp and hc and hc & tc:
            score, note = W["name_generic"], "=город"
        else:
            return 0.0, ""
    if hc and tc and not (hc & tc):
        return 0.0, ""
    if hc and tc:
        score += W["city_ok"]
        note += "+город"
    if dh and dt:
        if dh == dt:
            note += "+№"
        else:
            score += W["number_bad"]
            note += "-№"
    elif dt:
        # "Боевая Арена 1" under a map name with no number is one of several.
        score += W["number_only"]
        note += "файл:№"
    if H == T:
        # Every word agrees, kind-words and qualifiers included: "Выход с
        # карьера" over a bare "Карьер", "Северный склад" over "Восточный".
        score += W["full_match"]
        note += "+полное"
    shared_q = {qualifier(s) for s in Hp if qualifier(s)} & {qualifier(s) for s in Tp if qualifier(s)}
    if shared_q:
        score += W["qual_same"]
        note += "+" + "/".join(sorted(shared_q))
    # A tier or a cell block is a part of the place the map names whole.
    if (Tp & PART) and not (Hp & PART):
        score += W["part"]
        note += "файл:часть"
    for q in qh:
        if q in qt:
            continue
        if fn_toks & FN_QUAL[q]:
            score += W["qual_ok"]
            note += "+%s" % q
        elif OPPOSITE.get(q) and (fn_toks & (FN_QUAL[OPPOSITE[q]] - {"n", "s", "e", "w", "d"})):
            score += W["qual_bad"]
            note += "-%s" % q
        else:
            score += W["qual_unknown"]
            note += "?%s" % q
    for q in qh & {OPPOSITE.get(t) for t in qt}:
        score += W["qual_bad"]
        note += "-%s/%s" % (q, OPPOSITE[q])
    # A qualifier only the file carries makes it a part of the place the
    # map names whole: "Тюрьма: Северный блок" under "Тюрьма Вади-Хальфы".
    for q in qt - qh - {OPPOSITE.get(t) for t in qh}:
        score += W["qual_unknown"]
        note += "файл:%s" % q
    return score, note


# --- inputs ----------------------------------------------------------------
def read(path):
    with io.open(path, encoding="utf-8-sig", errors="replace") as fh:
        return fh.read()


def load_json(name, default=None):
    try:
        with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def tooltips():
    """cell -> [raw tooltip texts] (two cells carry two tooltips each)."""
    txt = read(os.path.join(world.RES, "database", "locations.xml"))
    out = collections.defaultdict(list)
    for x, y, t in re.findall(r'<location x="(\d+)" y="(\d+)" text="([^"]*)"', txt):
        out[(int(x), int(y))].append(html.unescape(t))
    return out


SPLIT = re.compile(r"<[Bb][Rr]\s*/?>|\n|:| - |\|")


def parse_tooltip(raws):
    heads, texts = [], []
    for raw in raws:
        parts = SPLIT.split(raw)
        heads.append(norm(parts[0]))
        texts.append(norm(raw))
    text = " ".join(texts)
    low = " ".join(raws).lower().replace("р", "p").replace("а", "a")
    wants = set()
    if re.search(r"\(\s*p\s*\)|\(a,\s*p\b|,\s*p и g\)", low):
        wants.add("pm")
    if re.search(r"\(\s*a\b", low):
        wants.add("plain")
    if re.search(r"\bg\s*\)|\[g\]", low):
        wants.add("g")
    return heads, text, wants


def static_files():
    """id -> everything the placer knows about a file."""
    sides = load_json("exits_sides.json", {}).get("summary", {})
    mt = world.mob_types()
    d = os.path.join(world.RES, "locations", "static")
    out = {}
    for fn in sorted(os.listdir(d), key=lambda s: int(s[:-4])):
        if not fn.endswith(".xml"):
            continue
        i = int(fn[:-4])
        loc = world.location(i)
        txt = read(os.path.join(d, fn))
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        toks = fn_tokens(loc.fn)
        spawns = collections.Counter()
        families = set()
        flags = set()
        variants = collections.Counter()
        skels = set()
        votes = collections.Counter()
        for _cell, tid in loc.spawns:
            if tid in mt:
                root, name, _a = mt[tid]
                spawns[tid] += 1
                if root != world.MOB:
                    families.add(family_of(name))
                    flags |= flags_of(name, root)
                    v = variant_of(name)
                    if v:
                        variants[v] += 1
                    for t in tokens(name):
                        if t not in NOISE and len(t) >= 4:
                            s = skel(t)
                            if len(s) >= 3:
                                skels.add(s)
                    c = city_of_internal(name)
                    if c:
                        votes[c] += 1
        for t in toks:
            if t in FN_FLAGS:
                flags.add(FN_FLAGS[t])
        city, how = None, ""
        for t in toks:
            for c, words in CITY_TOKENS.items():
                if t in words:
                    city, how = c, "fn"
                    break
            if city:
                break
        if city is None:
            city = city_of_text(norm(loc.title))
            how = "title" if city else ""
        if votes:
            c, n = votes.most_common(1)[0]
            if city is None and n >= 2 and n > sum(votes.values()) / 2:
                city, how = c, "spawns"
            elif city and c != city and n >= 3 and n > sum(votes.values()) * 2 / 3:
                # Oasis_VH-D is staffed by Abri_oasis_ammo, Abri_oasis_healer
                # and Abri_oasis_w_trd: the inhabitants outvote a two-letter
                # hint in the file name.
                city, how = c, "spawns over fn"
        out[i] = dict(
            id=i, title=loc.title, ntitle=norm(loc.title), fn=loc.fn, toks=toks,
            war=loc.war, dir=attrs.get("dir", ""),
            place=(attrs.get("bg", ""), attrs.get("library", "")),
            sides=sides.get(str(i), {}).get("sides", []),
            spawns=spawns, families=families, flags=flags, skels=skels,
            city=city, city_how=how,
            variants=variants,
            # A premium shop: named so, or staffed by _pm copies only.
            premium_only=("pm" in toks or "p" in toks or
                          (variants["pm"] >= 2 and not variants["plain"] and not variants["g"])),
            test=any("test" in t for t in toks),
            event=bool(set(toks) & EVENT_TOKENS),
            quest="q" in toks,
            number=fn_number(loc.fn),
        )
    return out


def wiki_locations():
    """[(xy, title, city)] of the wiki's location articles with coordinates."""
    pages = load_json(os.path.join("wiki_world", "locations.json"), {}).get("pages", {})
    out = []
    for title, txt in pages.items():
        xy, city = None, None
        for _lvl, name, body in sections(txt):
            key = name.strip("'").replace(":", "").strip()
            if key.startswith("Координ"):
                m = XY.search(body)
                if m:
                    xy = (int(m.group(1)), int(m.group(2)))
                for t, _l in links(body):
                    c = city_of_text(norm(t))
                    if c:
                        city = city or c
        if xy is None:
            m = XY.search(txt)
            if m:
                xy = (int(m.group(1)), int(m.group(2)))
        if xy:
            out.append((xy, title, city or city_of_text(norm(title))))
    return out


def wiki_npcs(mt):
    """[(xy, npc title, name family)] for NPC articles bound at medium or
    better; the family is the internal name up to its variant suffix."""
    npcs = load_json("npc_wiki.json", {}).get("npcs", {})
    names = load_json("npc_names.json", {})
    conf = names.get("confidence", {})
    bound = names.get("names", {})
    out = []
    for title, rec in npcs.items():
        for p in rec.get("places", []):
            tid, xy = p.get("type_id"), p.get("xy")
            if not tid or not xy or int(tid) not in mt:
                continue
            c = conf.get(str(tid)) or (p.get("confidence") if str(tid) in bound else None)
            if c in ("verified", "high", "medium"):
                out.append((tuple(xy), title, family_of(mt[int(tid)][1])))
    return out


def verified():
    return (load_json("settlements_verified.json", {}) or {}).get("cells", {})


# --- the placer --------------------------------------------------------------
def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


EVIDENCE = ("name", "wiki", "npc", "resident", "services", "region", "calm",
            "event", "family")


class Placer:
    def __init__(self):
        self.files = static_files()
        usable = {i: f for i, f in self.files.items()
                  if not f["test"] and f["ntitle"] not in GENERIC_TITLES
                  and any(s in "WNES" for s in f["sides"])}
        # Clones: the same file shipped twice under two ids.
        self.clones = collections.defaultdict(list)
        seen = {}
        for i in sorted(usable):
            f = usable[i]
            key = (f["ntitle"], f["fn"], f["place"], f["war"], tuple(f["sides"]))
            if key in seen:
                self.clones[seen[key]].append(i)
            else:
                seen[key] = i
        dropped = {j for js in self.clones.values() for j in js}
        self.usable = {i: f for i, f in usable.items() if i not in dropped}
        # Twins: one place drawn twice (peaceful and war, day and night),
        # recognised by background and library. Only hand-drawn files
        # (dir=Static): the templates share a handful of backgrounds.
        by_place = collections.defaultdict(list)
        for i, f in self.files.items():
            if f["dir"] == "Static" and not f["test"]:
                by_place[f["place"]].append(i)

        def twin_titles(a, b):
            # The same place under the very same name: the three Dongola
            # warehouses share one background and are not twins, nor are
            # "Поселок" and "Нубийское поселение" drawn from one camp.
            return self.files[a]["ntitle"] == self.files[b]["ntitle"]

        self.twins = {i: [j for j in by_place[f["place"]] if j != i and twin_titles(i, j)]
                      for i, f in self.files.items()}
        self.fn_toks = {i: set(f["toks"]) | {t for j in self.twins.get(i, ())
                                             for t in self.files[j]["toks"]}
                        for i, f in self.files.items()}
        self.by_family = collections.defaultdict(set)
        for i, f in self.usable.items():
            for fam in f["families"]:
                self.by_family[fam].add(i)
        # Rare words of file names: Evan_00, Evan_07, Evan_14 are one
        # village, and a file placed next to its kin is where it belongs.
        freq = collections.Counter()
        for f in self.usable.values():
            freq.update(set(f["toks"]))
        skip = {t for ts in CITY_TOKENS.values() for t in ts} | EVENT_TOKENS
        self.rare = {i: {t for t in f["toks"] if freq[t] <= RARE and not t.isdigit()
                         and t not in skip and len(t) >= 3}
                     for i, f in self.usable.items()}
        self.cells = {}
        for cell, raws in tooltips().items():
            heads, text, wants = parse_tooltip(raws)
            self.cells[cell] = dict(raws=raws, heads=heads, text=text, wants=wants,
                                    head=max(heads, key=len),
                                    stems=[split_words(h)[0] for h in heads],
                                    skels=skeletons(text))
        self.centres = self.city_centres()
        self.wloc = wiki_locations()
        self.wnpc = wiki_npcs(world.mob_types())
        self.fixed = {tuple(int(v) for v in k.split(",")): v2
                      for k, v2 in verified().items()}

    def city_centres(self):
        """Where each city's cores are: among the tooltips naming the city,
        every cell with two or more such neighbours within CORE cells, the
        best (most neighbours, then the longest menu of services) first.
        A city may have two cores: the Nubian valley is drawn twice, in the
        far east and in the north-west corner."""
        pts = collections.defaultdict(list)
        for cell, c in self.cells.items():
            city = city_of_text(c["head"])
            if city:
                pts[city].append(cell)
        out = {}
        for city, cells in pts.items():
            def rank(cell):
                near = sum(1 for o in cells if o != cell and cheb(o, cell) <= CORE)
                lines = len(SPLIT.split(" ".join(self.cells[cell]["raws"])))
                return (near, lines, -cell[0], -cell[1])
            ranked = sorted(cells, key=rank, reverse=True)
            cores = [ranked[0]]
            for cell in ranked[1:]:
                if rank(cell)[0] >= 2 and all(cheb(cell, k) > CITY_RADIUS for k in cores):
                    cores.append(cell)
            out[city] = cores
        return out

    def cell_city(self, cell):
        head = self.cells[cell]["head"]
        c = city_of_text(head)
        if c:
            return c, "название"
        best = min(((cheb(k, cell), city) for city, cores in self.centres.items()
                    for k in cores), default=(None, None))
        if best[0] is not None and best[0] <= CITY_RADIUS:
            return best[1], "ближайший город"
        return None, ""

    # -- evidence per (cell, file) --
    def score(self, cell, i, family_bonus):
        f = self.usable[i]
        c = self.cells[cell]
        ev = {}
        notes = []
        best = (0.0, "")
        for head in c["heads"]:
            s = name_score(head, f["ntitle"], self.fn_toks[i])
            if s[0] > best[0]:
                best = s
        ev["name"] = best[0]
        if best[1]:
            notes.append("имя %s" % best[1])

        # wiki location articles
        wl = 0.0
        for xy, title, wcity in self.wloc:
            d = cheb(xy, cell)
            if d > NEAR:
                continue
            if wcity and f["city"] and not same_region(wcity, f["city"]):
                continue
            eq = max(name_score(h, norm(title), set())[0] for h in c["heads"])
            fs = name_score(norm(title), f["ntitle"], self.fn_toks[i])[0]
            if eq >= W["name_super"] and fs >= W["name_sub"]:
                wl = max(wl, W["wiki_loc"][min(d, 2)])
                notes.append("вики «%s» %d" % (title, d))
            elif d == 0 and fs >= W["name_super"]:
                wl = max(wl, W["wiki_cell"])
                notes.append("вики-клетка «%s»" % title)
        ev["wiki"] = wl

        # a tooltip word that is an inhabitant's name
        hits = sorted(c["skels"] & f["skels"])
        ev["resident"] = min(W["resident"] * len(hits), W["resident_cap"])
        if hits:
            notes.append("житель %s" % ",".join(hits))

        # wiki NPC articles
        npc = 0.0
        hits = []
        for xy, title, fam in self.wnpc:
            d = cheb(xy, cell)
            if d <= NEAR and i in self.by_family.get(fam, ()):
                npc += W["npc"][0 if d == 0 else 1]
                hits.append(title)
        npc = min(npc, W["npc_cap"])
        if npc and ev["name"] <= 0 and wl <= 0 and ev["resident"] <= 0:
            npc *= W["npc_unnamed"]
        ev["npc"] = npc
        if hits:
            notes.append("НПС %s" % ", ".join(sorted(set(hits))[:4]))

        # services
        sv, miss = 0.0, 0.0
        got, lost = [], []
        for pat, flag, hard in SERVICES:
            if not re.search(pat, c["text"]):
                continue
            if flag in f["flags"]:
                if flag not in got:
                    sv += W["service_specific"] if flag in SPECIFIC else W["service"]
                    got.append(flag)
            elif hard and f["spawns"]:
                miss += W["service_miss"]
                lost.append(flag)
        ev["services"] = min(sv, W["service_cap"]) + miss
        if got:
            notes.append("услуги %s" % ",".join(got))
        if lost:
            notes.append("нет %s" % ",".join(lost))
        # (A) / (G) / (P) variants against plain, _g and _pm shopkeepers
        v = f["variants"]
        if "pm" in c["wants"]:
            if v["pm"]:
                ev["services"] += W["premium_ok"]
                notes.append("премиум")
            elif v["plain"] or v["g"]:
                ev["services"] += W["premium_missing"]
                notes.append("нет премиум")
        if "plain" in c["wants"] and v["plain"]:
            ev["services"] += W["variant_ok"]
            notes.append("вариант A")
        if "g" in c["wants"] and v["g"]:
            ev["services"] += W["variant_ok"]
            notes.append("вариант G")
        if f["premium_only"] and ("plain" in c["wants"] or "g" in c["wants"]):
            ev["services"] += W["premium_only"]
            notes.append("только премиум")

        # region
        ccity, _how = self.cell_city(cell)
        if ccity and f["city"]:
            if ccity == f["city"]:
                ev["region"] = W["region_ok"]
                notes.append("регион %s" % f["city"])
            elif same_region(ccity, f["city"]):
                ev["region"] = W["region_near"]
                notes.append("регион %s~%s" % (f["city"], ccity))
            else:
                ev["region"] = W["region_bad"]
                notes.append("регион %s≠%s" % (f["city"], ccity))
        else:
            ev["region"] = 0.0

        ev["calm"] = W["calm"] if not f["war"] else 0.0
        # A quest file named exactly as the map names the cell is that
        # quest's place; the penalty is for quest files competing on less,
        # and for seasonal, clan and border files always.
        waived = f["quest"] and ev["name"] >= W["name_exact"]
        ev["event"] = W["event"] if f["event"] and not waived else 0.0
        if ev["event"]:
            notes.append("ивент/квест fn")
        ev["family"] = family_bonus
        if family_bonus:
            notes.append("семейство %+g" % family_bonus)
        total = sum(ev.values())
        return total, ev, "; ".join(notes)

    def family_bonuses(self):
        """(cell, file) -> bonus for numbered families paired in rank order."""
        cell_groups = collections.defaultdict(list)
        for cell, c in self.cells.items():
            n = numbers(c["head"])
            if n is None:
                continue
            key = (self.cell_city(cell)[0], split_words(re.sub(r"\d+", " ", c["head"]))[0])
            cell_groups[key].append((n, cell))
        file_groups = collections.defaultdict(list)
        for i, f in self.usable.items():
            if f["number"] is None:
                continue
            file_groups[(f["city"], f["ntitle"])].append((f["number"], i))
        bonus = {}
        for (city, hstems), cells in cell_groups.items():
            if len(cells) < 2 or city is None:
                continue
            for (fcity, ntitle), files in file_groups.items():
                if len(files) < 2 or fcity != city:
                    continue
                if name_score(" ".join(sorted(hstems)), ntitle, set())[0] < W["name_kind"]:
                    continue
                cells.sort()
                files.sort()
                for (_n, cell), (_m, i) in zip(cells, files):
                    bonus[(cell, i)] = W["family"]
                for _n, cell in cells:
                    for _m, i in files:
                        bonus.setdefault((cell, i), W["family_other"])
        return bonus

    def series_pick(self, cell, free, placed):
        """The representative of a series tied at the top of a cell, or None.

        A series: files with one title, one city and one name up to a
        number or a roman numeral (DethPass_1_VR..DethPass_5_VR, SILVER_1..
        10, MP_Enter1..3), all within a weak margin of the leader, the map
        naming the place in full (name evidence at least exact). The
        unnumbered member represents it, else the lowest number. A file
        already standing next door does not join the tie: it has its cell,
        the series members are what is left for this one.
        """
        top = free[0][0]
        tied = [i for s, i in free if top - s < WEAK_MARGIN and not placed[i]]
        if len(tied) < 2:
            return None
        name_ev = {r[1]: r[2]["name"] for r in self.scored[cell]}
        if name_ev.get(tied[0], 0.0) < W["name_exact"]:
            return None

        def series_key(i):
            f = self.usable[i]
            stemmed = re.sub(r"(\d+|_[IVX]+)(?=_|$)", "", f["fn"]).rstrip("_")
            return (f["ntitle"], f["city"], f["war"], stemmed)

        if len({series_key(i) for i in tied}) != 1:
            return None
        return min(tied, key=lambda i: (self.usable[i]["number"] is not None,
                                        self.usable[i]["number"] or 0, i))

    def candidates(self, cell):
        c = self.cells[cell]
        out = set()
        for i, f in self.usable.items():
            if any(name_score(h, f["ntitle"], self.fn_toks[i])[0] > 0 for h in c["heads"]):
                out.add(i)
            elif c["skels"] & f["skels"]:
                out.add(i)
        for xy, title, _wcity in self.wloc:
            if cheb(xy, cell) <= NEAR:
                for i, f in self.usable.items():
                    if name_score(norm(title), f["ntitle"], self.fn_toks[i])[0] >= W["name_sub"]:
                        out.add(i)
        for xy, _title, fam in self.wnpc:
            if cheb(xy, cell) <= NEAR:
                out |= self.by_family.get(fam, set())
        return out

    def run(self):
        family = self.family_bonuses()
        scored = {}   # cell -> [(total, i, ev, notes)] sorted desc
        for cell, c in self.cells.items():
            if all(h in GENERIC_TITLES for h in c["heads"]):
                scored[cell] = []
                continue
            rows = []
            for i in self.candidates(cell):
                total, ev, notes = self.score(cell, i, family.get((cell, i), 0.0))
                rows.append((total, i, ev, notes))
            rows.sort(key=lambda r: (-r[0], r[1]))
            scored[cell] = rows
        self.scored = scored
        named = {(cell, r[1]): (r[2]["name"] > 0 or r[2]["wiki"] >= W["wiki_cell"]
                                or r[2]["resident"] > 0)
                 for cell, rows in scored.items() for r in rows}

        placed = collections.defaultdict(list)   # file -> cells
        table = {}
        verdict = {}
        # Verified cells first: they are the truth and anchor their files.
        for cell, i in self.fixed.items():
            if i is not None:
                table[cell] = i
                placed[i].append(cell)
                verdict[cell] = "проверено"
            else:
                verdict[cell] = "снято проверкой"

        real = {cell: {s for st in c["stems"] for s in st
                       if not is_generic(s) and not s.isdigit()}
                for cell, c in self.cells.items()}

        def may_take(i, cell):
            if not named.get((cell, i)):
                return False
            if not placed[i]:
                return True
            return any(manhattan(cell, c) <= ADJACENT and real[cell] == real[c]
                       for c in placed[i])

        kin_bonus = {}

        def kin(cell, i):
            """Placed files within KIN cells sharing a rare file-name word."""
            n = 0
            for j, cells in placed.items():
                if j != i and self.rare[i] & self.rare[j] \
                        and any(cheb(cell, c) <= KIN for c in cells):
                    n += 1
            return min(W["neighbour"] * n, W["neighbour_cap"])

        def free_at(cell):
            """(effective score, file) of every file still able to take the
            cell, best first; a file already standing next door is
            discounted, one with placed kin nearby is credited."""
            out = []
            for r in scored[cell]:
                if not may_take(r[1], cell):
                    continue
                k = kin(cell, r[1])
                kin_bonus[(cell, r[1])] = k
                out.append((r[0] + k + (W["extra_cell"] if placed[r[1]] else 0.0), r[1]))
            return sorted(out, key=lambda t: (-t[0], t[1]))

        # Greedy by rounds: the strongest (cell, file) pair anywhere is
        # decided first, then the next, each time against whoever is still
        # free to take that cell. Who those were is kept for the report.
        contenders = {}
        undecided = {cell for cell, rows in scored.items() if rows and cell not in verdict}
        while undecided:
            best = None
            for cell in undecided:
                free = free_at(cell)
                if free and (best is None or (free[0][0], -cell[0], -cell[1]) > best[0]):
                    best = ((free[0][0], -cell[0], -cell[1]), cell, free)
            if best is None:
                break
            _key, cell, free = best
            undecided.discard(cell)
            contenders[cell] = free
            score, i = free[0]
            runner = free[1][0] if len(free) > 1 else 0.0
            margin = score - runner
            if score >= CONFIDENT_SCORE and margin >= CONFIDENT_MARGIN:
                verdict[cell] = "уверенно"
            elif score >= WEAK_SCORE and margin >= WEAK_MARGIN:
                verdict[cell] = "слабо"
            elif score >= WEAK_SCORE and self.series_pick(cell, free, placed) is not None:
                # A tie among numbered copies of one place whose name the
                # map gives in full: the representative is the unnumbered
                # member, else the lowest number. Documented, not divined.
                i = self.series_pick(cell, free, placed)
                verdict[cell] = "слабо: представитель серии"
            else:
                verdict[cell] = "пустошь: нет отрыва" if score >= WEAK_SCORE else "пустошь: мало улик"
                continue
            table[cell] = i
            placed[i].append(cell)
        for cell in scored:
            if cell in verdict:
                continue
            if all(h in GENERIC_TITLES for h in self.cells[cell]["heads"]):
                verdict[cell] = "пустошь: общий заголовок"
            elif not scored[cell]:
                verdict[cell] = "пустошь: нет кандидатов"
            elif any(named.get((cell, r[1])) for r in scored[cell]):
                verdict[cell] = "пустошь: кандидаты стоят в другом месте"
            else:
                verdict[cell] = "пустошь: мало улик"
            contenders.setdefault(cell, [])
        self.table, self.verdict, self.placed = table, verdict, placed
        self.contenders, self.kin = contenders, kin_bonus
        return table

    # -- output --
    def write_table(self, path):
        cells = {"%d,%d" % k: v for k, v in sorted(self.table.items())}
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"cells": cells}, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")

    def write_report(self, path, previous):
        f = self.files
        counts = collections.Counter(v.split(":")[0] for v in self.verdict.values())
        reasons = collections.Counter(v for v in self.verdict.values() if v.startswith("пустошь"))
        lines = []
        lines.append("# Привязка клеток карты к файлам локаций\n")
        lines.append("Построено `data/place_settlements.py` по сумме улик (см. докстринг). "
                     "Каждая строка — одна клетка с подсказкой на глобальной карте. "
                     "Проверять игроку: колонка «выбрано» — что откроется на клетке; "
                     "«альтернативы» — кто был вторым и третьим († — файл сильнее, но уже "
                     "стоит в другом месте); «улики» — за что взят файл. "
                     "Исправленную клетку заносить в `data/settlements_verified.json` "
                     "(значение null — клетка становится пустошью).\n")
        lines.append("Итог: клеток с подсказкой %d; проверено игрой %d; уверенно %d; слабо %d; "
                     "пустошь %d (%s).\n" % (
                         len(self.cells), counts["проверено"], counts["уверенно"], counts["слабо"],
                         counts["пустошь"],
                         ", ".join("%s %d" % (k.split(": ")[1], n) for k, n in reasons.most_common())))
        lines.append("Ядра городов по подсказкам: " + "; ".join(
            "%s %s" % (c, ", ".join("%d×%d" % k for k in cores))
            for c, cores in sorted(self.centres.items())) + ".\n")
        if self.clones:
            lines.append("Файлы-клоны (одинаковые заголовок, fn, фон, war и выходы), представлены "
                         "младшим id: " + "; ".join("%d = %s" % (i, ", ".join(map(str, js)))
                                                   for i, js in sorted(self.clones.items())) + ".\n")
        changed = [(c, previous.get("%d,%d" % c), self.table.get(c))
                   for c in sorted(set(self.cells) | {tuple(int(v) for v in k.split(","))
                                                      for k in previous})
                   if previous.get("%d,%d" % c) != self.table.get(c)]
        lines.append("Отличий от предыдущей таблицы: %d (колонка «было»).\n" % len(changed))
        # Self-check on the verified cells.
        for cell, want in sorted(self.fixed.items()):
            rows = self.scored.get(cell, [])
            top = rows[0][1] if rows else None
            lines.append("- проверенная клетка %d,%d → %s: улики сами дают %s%s" % (
                cell[0], cell[1], want, top,
                " (совпадает)" if top == want else " (НЕ совпадает, перекрыто проверкой)"))
        lines.append("")
        lines.append("Очки: имя / вики / НПС / житель / услуги / регион / мир / ивент / семейство "
                     "/ соседи по имени файла = всего. Пометки имени: = совпадение, ⊃ файл назван короче, ⊂ файл назван "
                     "длиннее, ~ общее слово, kind — только слово-род, +город — назван тот же "
                     "город, +old/+new квалификатор подтверждён именем файла, ?old не "
                     "подтверждён, -old противоречит, файл:часть — файл назван как часть "
                     "(ярус, камеры).\n")
        lines.append("| клетка | подсказка | выбрано | было | очки | улики | альтернативы | вердикт |")
        lines.append("|---|---|---|---|---|---|---|---|")

        def show(i):
            if i is None:
                return "—"
            m = f[i]
            return "%d «%s» %s war=%d" % (i, m["title"].strip(), m["fn"], m["war"])

        for cell in sorted(self.cells):
            c = self.cells[cell]
            rows = self.scored.get(cell, [])
            chosen = self.table.get(cell)
            head = " / ".join(h for h in c["heads"])
            ev_txt, notes = "", ""
            if chosen is not None:
                row = next((r for r in rows if r[1] == chosen), None)
                if row:
                    ev = row[2]
                    k = self.kin.get((cell, chosen), 0.0)
                    ev_txt = "/".join("%g" % ev[x] for x in EVIDENCE) + "/%g = %g" % (k, row[0] + k)
                    notes = row[3] + ("; соседи по имени файла %+g" % k if k else "")
            # Runners-up among the files still free when the cell was
            # decided; a stronger file already standing elsewhere is shown
            # after them with a dagger.
            free = [(s, i) for s, i in self.contenders.get(cell, []) if i != chosen][:2]
            taken = [(r[0], r[1]) for r in rows if r[1] != chosen
                     and r[1] not in {i for _s, i in free}
                     and (not free or r[0] > free[-1][0])][:2]
            alts = "; ".join("%s (%g)" % (show(i), s) for s, i in free)
            if taken:
                alts += ("; " if alts else "") + "; ".join(
                    "†%s (%g)" % (show(i), s) for s, i in taken)
            alts = alts or "—"
            was = previous.get("%d,%d" % cell)
            lines.append("| %d,%d | %s | %s | %s | %s | %s | %s | %s |" % (
                cell[0], cell[1], head.replace("|", "/"), show(chosen),
                "" if was == chosen else show(was),
                ev_txt, notes.replace("|", "/"), alts.replace("|", "/"),
                self.verdict.get(cell, "")))
        with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
        return counts, changed


def main():
    out = os.path.join(HERE, "settlements.json")
    previous = (load_json("settlements.json", {}) or {}).get("cells", {})
    placer = Placer()
    table = placer.run()
    placer.write_table(out)
    counts, changed = placer.write_report(os.path.join(HERE, "settlements_report.md"), previous)
    print("клеток с подсказкой: %d, файлов-кандидатов: %d (клонов убрано %d)" % (
        len(placer.cells), len(placer.usable), sum(len(v) for v in placer.clones.values())))
    print("ядра городов:", {c: v for c, v in sorted(placer.centres.items())})
    for k, v in counts.most_common():
        print("  %-12s %d" % (k, v))
    print("привязано клеток: %d, отличий от прежней таблицы: %d" % (len(table), len(changed)))
    print("записано в %s и settlements_report.md" % out)


if __name__ == "__main__":
    main()
