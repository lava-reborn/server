"""Link wiki item articles to type_ids of the client's objects.xml.

    wsl.exe -e python3 data/wiki_links.py      -> data/wiki_links.json

The wiki never mentions a type_id, so every link is inferred and carries a
`method` and a `confidence`. Methods, best first:

  icon_exact      the article's image file is named after the internal item
                  name (the wiki uploaded icons straight from the client:
                  "Knife lvl14 A.png" == knife_lvl14_A); ~100 % precise
  icon_prefix     the image name is a prefix of a family of internal names
                  ("Codified bp" -> codified_bp_1..20); the family is linked
                  and the caller narrows it down
  icon_revprefix  an internal name is a prefix of the image name
                  ("Knife lvl14 G1" -> knife_lvl14_G*), used by knife mods
  title           the article title is the internal name (MG-3, MEG-23)
  blueprint       "<effect> (<N>у)" -> bpg_<effect>_lvl<N>, "Зашифрованный
                  чертеж (<N>у)" -> codified_bp_<N>, knife sharpening ->
                  bpg_knife_lvl<N>_<Damage|Actionpoint|...>
  calibre         ammunition: the calibre of the page and the quality column
                  (КС, СТ, ОТ, ...) give Ammo_<calibre>_<KS|ST|OT|...>
  manual          hand-made tables for buffs and a few drinks whose names
                  are transliterations (Анестетик МК I -> Anesthetic_MK_1),
                  and for food and first-aid kits, whose pages carry no icon
                  or the icon of another type (WRONG_ICONS, which the icon
                  methods skip)
  firearm_class_level
                  mass-produced firearms are named <class>_<index>_lvl_<N>
                  and the wiki names real guns, so the only key is the class
                  (category) plus "Стрельба N" (= N); that leaves up to four
                  candidate families per page, listed for data/firearm_families.json

Each link lists all matched type_ids and splits them by variant: "A"
(ordinary), "P" (premium, _pm), "G" (gold), with ":<mod>" appended for
_mod_* modifications. Coverage per category is printed and stored in _meta.
"""
import collections
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import (HERE, ITEM_CATEGORIES, FIREARM_CLASS, ROMAN, MASS_FIREARM,
                         load_pages, load_objects, norm, categories, image_names,
                         parse_name, parse_tables, dump_json)

OUT = os.path.join(HERE, "wiki_links.json")
# The hand-made half of the firearm pairing: which line each article names,
# for the articles where class and level alone leave two lines fitting and
# data/firearm_families.py reports "ambiguous". See that file's _meta.
LINES_MANUAL = os.path.join(HERE, "firearm_lines_manual.json")
MOD_TAIL = re.compile(r"\s+Mod\s*[IVX]+\s*$")


def hand_lines():
    """Base article title -> the family line chosen for it by hand.

    A missing file is not an error: without it every ambiguous firearm simply
    stays a list of candidates, which is where the linker was before.
    """
    try:
        with open(LINES_MANUAL, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return {}
    return {t: v["family"] for t, v in (doc.get("lines") or {}).items()}


def hand_levels():
    """Base article title -> the level supplied by hand, for the few articles
    that state none.

    The level is not decoration here: link_firearm can only look for candidate
    lines once it knows which level to look in, and it takes that from the
    "Необходимые навыки" row. A page without that row therefore produces no
    links at all, and no decision recorded in firearm_lines_manual.json can
    reach it -- the hand lookup happens inside the loop over the levels the
    page states.

    So an entry may carry a level of its own. It is a decision like the family
    beside it, and it is written down in the same place, with the same
    obligation to say why.
    """
    try:
        with open(LINES_MANUAL, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return {}
    return {t: int(v["level"]) for t, v in (doc.get("lines") or {}).items()
            if v.get("level") is not None}


HAND = hand_lines()
HAND_LEVEL = hand_levels()

# "Mod IX" in a firearm title -> the _mod_* suffix in objects.xml. Read off
# the effect descriptions of the 278 Mod pages (see data/mods_wiki.json).
MOD_SUFFIX = {
    "II": "weight", "III": "perception", "IV": "aimtime", "V": "shotrange",
    "VI": "agility", "VII": "reloadspeed", "VIII": "attrition_x2",
    "IX": "clipsize", "X": "shotspeed", "XI": "precision", "XII": "damage",
    "XIV": "precision_shotrange", "XV": "damage_clipsize",
}
# Knife pages count their own way: Mod I is both, Mod II action points,
# Mod III damage (checked on "Боевой нож Mod I..III" against knife_lvl14_G_*).
KNIFE_MOD = {"I": "damage_actionpoints", "II": "actionpoint", "III": "damage"}

# Ammunition quality columns -> name suffix.
AMMO_COLUMN = {"КС": "KS", "КС(Р)": "KS_P", "КС(P)": "KS_P", "КС(G)": "KSG",
               "СТ": "ST", "ОТ": "OT", "ОТ(PS)": "OT_PS", "ЭК": "EK_G",
               "ББ": "BB_G", "СБ": "SB_G", "CБ": "SB_G", "ШК": "shock"}
# Ammunition page -> calibre token(s) of Ammo_<calibre>_<quality>.
AMMO_CALIBRE = {
    "0.45 калибр": ["45"], "12-й калибр": ["12mm"], "5.56х45мм НАТО": ["556x45"],
    "5.7x28 (SS190)": ["SS190"], "7.62х25": ["762x25"], "7.62х39мм": ["762x39"],
    "7.62х51мм НАТО": ["762x51"], "7.62х54R": ["762x54R"],
    "8.6x70 (.338 Lapua Magnum)": ["86x70"], "9мм НАТО": ["9mmNato"],
    "ПАБ-9": ["SP_5_6"], "СП-5": ["SP_5", "SP_5_6"], "СП-6": ["SP_5_6"],
    "СП-10": ["SP_10_12"], "СП-12": ["SP_10_12"], "Монтажный": ["Metallbolt"],
}
# Ammunition pages outside the calibre scheme.
AMMO_NAMES = {
    "9мм даренные": (["Ammo_9mmNato_kal"], 0.5),
    "Ампула": (["Ammo_ampoule"], 0.8),
    "Балон азота - «Снежок»": (["snow_ammo", "snow_ammo2", "snow_ammo3", "snow_ammo4"], 0.5),
    "Батарейка «Крона» ШК": (["Ammo_battery_krona"], 0.8),
    "Блок питания ЭК": (["Ammo_battery"], 0.7),
    "Бьют прямо в сердце": (["Ammo_Love"], 0.7),
    "Останавливающие болты": (["Ammo_immobilize_bolt_5", "Ammo_immobilize_bolt_10",
                               "Ammo_immobilize_bolt_5_G", "Ammo_immobilize_bolt_10_G"], 0.7),
    "Парализующие болты": (["Ammo_stun_bolt_5", "Ammo_stun_bolt_10",
                            "Ammo_stun_bolt_5_G", "Ammo_stun_bolt_gold_10"], 0.7),
    "Парализующие пули": (["Ammo_stun", "Ammo_stun_G"], 0.7),
    "Слюна верблюда": (["Ammo_Camel"], 0.8),
    "Стрела": (["Ammo_strela_antiarmor"], 0.7),
    "Тренировочные патроны": (["noob_ammo"], 0.7),
    "Электроразряд": (["Ammo_elect_flash"], 0.6),
}

# Buffs and drinks: (title pattern, name templates, confidence). {n} is the
# arabic number of the roman numeral in the title, {r} the numeral itself.
PIKODIN = {1: "50", 2: "80", 3: "99"}
MANUAL = [
    (r"^Анестетик МК ([IVX]+)$", ["Anesthetic_MK_{n}", "Anesthetic_MK_{n}_Gold"], 0.85),
    (r"^Анестетик \+$", ["Anesthetic_Plus"], 0.85),
    (r"^Анестетик$", ["Anesthetic_noob"], 0.5),
    (r"^Салюс МК ([IVX]+)$", ["Salus_MK_{n}", "Salus_MK_{n}_Gold"], 0.85),
    (r"^Салюс \+$", ["Salus_Plus"], 0.85),
    (r"^Салюс$", ["Salus_noob"], 0.5),
    (r"^Дофрамин ([IVX]+)$", ["item_dex_up_{r}"], 0.7),
    (r"^Ментостимулятор ([IVX]+)$", ["item_int_up_{r}"], 0.7),
    (r"^Инъекция INTUX ([IVX]+)$", ["item_up_exp_all_{n}_gold"], 0.6),
    (r"^Альфа-Реагент ([IVX]+)$", ["item_up_critical_probability_{n}",
                                   "item_up_critical_probability_{n}_gold"], 0.6),
    (r"^Омега-Реагент ([IVX]+)$", ["item_up_critical_evade_{n}",
                                   "item_up_critical_evade_{n}_gold"], 0.6),
    (r"^Пикодин ([IVX]+)$", ["item_down_exp_all_{pik}", "item_down_exp_all_{pik}_gold"], 0.6),
    (r"^Сканер$", ["item_mob_drop_up", "item_mob_drop_up_long"], 0.6),
    (r"^Крыса - гриль$", ["item_Rat_grill"], 0.7),
    (r"^Кукурузный хлеб$", ["item_kukuruziniy_hlab_ay"], 0.6),
    (r"^Виски$", ["whisky"], 0.9), (r"^Водка$", ["vodka"], 0.9),
    (r"^Текила$", ["tequila"], 0.9), (r"^Пиво$", ["beer"], 0.9),
    (r"^Шаурма$", ["shaurma"], 0.9), (r"^Лава-Кола$", ["lava_cola"], 0.7),
    (r"^Лава-Кола \(стакан\)$", ["lava_cola2"], 0.6),
    # Trophies (root type 6) are named after the body part.
    (r"^Череп трофей$", ["tr_Skull"], 0.9), (r"^Скальп трофей$", ["tr_Scalp"], 0.9),
    (r"^Палец трофей$", ["tr_Finger"], 0.9), (r"^Ухо трофей$", ["tr_Ear"], 0.9),
    (r"^Кисть трофей$", ["tr_Hand"], 0.9), (r"^Сердце$", ["tr_Heart"], 0.8),
    (r"^Рога трофей$", ["tr_Horn"], 0.9), (r"^Жетон трофей$", ["tr_Token"], 0.9),
    # Food and first-aid kits. The food pages carry icons of their own
    # ("Food1.png") that name no type, so nothing linked them; the kit pages
    # carry icons named after the wrong type (WRONG_ICONS below). The right
    # type comes from two agreeing sources. The original texts.xml lists each
    # line as one block of six level bands, 0_3 .. 20 in order -- rows 320
    # (food), 332 (food, 10 portions), 356 (kits "(20) (G)"), 392 (kits
    # "(5) (P)") -- and every row states "Расход ОД", which equals the
    # page's "Очки действия". And the client's own icons show a root marked
    # "ЕДА" for Med_Pacific_Heal_0_3_A, a first-aid box for Med_Pacific_HR_*_G
    # and an army pouch for Med_Battle_HR_*_P.
    (r"^Корень Маниока$", ["Med_Pacific_Heal_0_3_A"], 0.9),
    (r"^Отварная Кукуруза$", ["Med_Pacific_Heal_4_7_A"], 0.9),
    (r"^Сушеная Рыба$", ["Med_Pacific_Heal_8_11_A"], 0.9),
    (r"^Вяленое Мясо$", ["Med_Pacific_Heal_12_15_A"], 0.9),
    (r"^Завтрак Туриста$", ["Med_Pacific_Heal_16_19_A"], 0.9),
    (r"^Консерва$", ["Med_Pacific_Heal_20_A"], 0.9),
    (r"^Корни Маниока$", ["Med_Pacific_Heal_0_3_Ax10"], 0.9),
    (r"^Фуль$", ["Med_Pacific_Heal_4_7_Ax10"], 0.9),
    (r"^Связка Сушеной Рыбы$", ["Med_Pacific_Heal_8_11_Ax10"], 0.9),
    (r"^Коробка Вяленого Мяса$", ["Med_Pacific_Heal_12_15_Ax10"], 0.9),
    (r"^Суточный Рацион$", ["Med_Pacific_Heal_16_19_Ax10"], 0.9),
    (r"^Продуктовый Набор$", ["Med_Pacific_Heal_20_Ax10"], 0.9),
    (r"^Аптечка «Эгоист»$", ["Med_Pacific_HR_0_3_G"], 0.9),
    (r"^Аптечка «Самоспас»$", ["Med_Pacific_HR_4_7_G"], 0.9),
    (r"^Аптечка «Резерв»$", ["Med_Pacific_HR_8_11_G"], 0.9),
    (r"^Аптечка «Медик»$", ["Med_Pacific_HR_12_15_G"], 0.9),
    (r"^Аптечка «Профи»$", ["Med_Pacific_HR_16_19_G"], 0.9),
    (r"^Аптечка «Спасатель»$", ["Med_Pacific_HR_20_G"], 0.9),
    (r"^Аптечка «Мини»$", ["Med_Battle_HR_0_3_P"], 0.9),
    (r"^Аптечка «Стандарт»$", ["Med_Battle_HR_12_15_P"], 0.9),
    # Belts. The pages carry no icon at all, and the client names the line
    # after the weapon class its pouches hold: "Удобные подсумки для
    # пистолетных магазинов" is belt_pistols, "... для 12 мм" belt_shotguns,
    # "... магазинов ПП" belt_sub_machineguns, "... магазинов винтовки"
    # belt_rifles, each with its gold copy (_g, the G column). Ваккас (1204)
    # sells the four (data/npcs.json stock). «Подсумки рукопашника» is left
    # out: belt_closecombat's own icon is on «Противогазная сумка(Q)».
    (r"^Подсумки пистолетные$", ["belt_pistols", "belt_pistols_g"], 0.9),
    (r"^Подсумки охотника$", ["belt_shotguns", "belt_shotguns_g"], 0.9),
    (r"^Подсумки спецназовца$", ["belt_sub_machineguns", "belt_sub_machineguns_g"], 0.9),
    (r"^Подсумки снайпера$", ["belt_rifles", "belt_rifles_g"], 0.9),
    # The gold lottery's ticket: its page carries an icon named after no
    # type, and the client's WhLoteryKey_g is the one gold key of Вади-Хальфа's
    # series (LoteryKey, WhLoteryKey_g, DnLoteryKey_*, AhLoteryKey_* -- the
    # order of texts.xml 6918-6925, «Лотерейный билет [8]», «Золотой
    # лотерейный билет [8]», [10] ...).
    (r"^Золотой лотерейный билет \(8\)$", ["WhLoteryKey_g"], 0.9),
]

# Icon files the wiki uploaded under another type's internal name, so an
# icon_exact link off them lands on the wrong type with the highest confidence
# the linker gives. Each is used by one page only: Med_Pacific_Heal_0_3_A.png
# shows the "Мини" kit (the client's own icon of that name is a manioc root),
# Med_Pacific_Heal_12_15_A.png the "Стандарт" kit (the client's is dried meat),
# and the six Med_Battle_HR_*_P.png sit on the "Эгоист" .. "Спасатель" pages,
# kits the original sells as "(20) (G)" and that the client draws as
# Med_Pacific_HR_*_G. The pages are linked by MANUAL above instead.
WRONG_ICONS = {norm(n) for n in (
    "Med_Pacific_Heal_0_3_A", "Med_Pacific_Heal_12_15_A",
    "Med_Battle_HR_0_3_P", "Med_Battle_HR_4_7_P", "Med_Battle_HR_8_11_P",
    "Med_Battle_HR_12_15_P", "Med_Battle_HR_16_19_P", "Med_Battle_HR_20_P")}
# And icons one page borrowed from another type, skipped on that page
# alone: qMultipass is «Билет в Донголу» (1124, texts.xml 6909), and the
# wiki put it on «Пропуск», a quest pass to the Maghreb base that costs
# 30 000 afro, and on «Лотерейный билет (8)», so Рияд's stall sold a
# ticket to Dongola and the lottery man one too.
WRONG_PAGE_ICONS = {"Пропуск": {norm("qMultipass")},
                    "Лотерейный билет (8)": {norm("qMultipass")}}

# Blueprint page title -> bpg_<key>_lvl<N>.
BLUEPRINT_EFFECT = {
    "Урон": "damage", "Размер обоймы": "clip_size", "Перезарядка": "reload_speed",
    "Скорострельность": "shot_speed", "Время прицеливания": "aim_time",
    "Дистанция стрельбы": "shot_range", "Точность": "precision",
    "Ловкость": "agility", "Восприятие": "perception", "Прочность": "durability",
    "Вес": "weight",
}
BLUEPRINT_COMBO = {"Урон и размер обоймы": "damage_25"}   # bpg_damage_25[_afro|_pm|_gold]_lvlN
KNIFE_BLUEPRINT = {"Заточка": "Damage", "Эргономика": "Actionpoint",
                   "Заточка и Эргономика": "Damage_Actionpoint"}
# Knife names in blueprint titles -> knife level (the title carries it too).
BLUEPRINT_TITLE = re.compile(r"^(.*?)\s*\((\d+)\s*у\)$")
KNIFE_BP_TITLE = re.compile(r"^(Заточка и Эргономика|Заточка|Эргономика)\s+(.+?)\s*\((\d+)у\)$")

KIND_ORDER = [
    ("ammo", {"Боеприпасы"}), ("blueprint", {"Чертежи"}),
    ("firearm", {"Огнестрельное оружие"} | set(FIREARM_CLASS)),
    ("coldarm", {"Холодное оружие"}), ("buff", {"БАФы"}),
    ("heal", {"Лечащие предметы", "Провизия", "Медикаменты"}),
    ("belt", {"Пояса"}), ("wear", {"Одежда", "Амуниция", "Аксесуары", "Наградные предметы"}),
    ("set", {"Сеты"}), ("trash", {"Треш лут", "Квестовые предметы", "Предметы", "Коллекции"}),
    ("trophy", {"Трофеи"}), ("transport", {"Транспорт"}),
    ("firearm", {"Наградное оружие", "Коллекционное оружие"}),
]

# Coverage groups for the report.
GROUPS = [
    ("Огнестрел", {"Огнестрельное оружие"}),
    ("Холодное", {"Холодное оружие"}),
    ("Броня/одежда", {"Одежда", "Амуниция", "Пояса", "Аксесуары"}),
    ("Боеприпасы", {"Боеприпасы"}),
    ("Лечилки/бафы", {"Лечащие предметы", "БАФы", "Провизия"}),
    ("Чертежи", {"Чертежи"}),
    ("Лут", {"Треш лут", "Квестовые предметы", "Предметы"}),
]


class Catalogue:
    def __init__(self, objects):
        self.objects = objects
        self.by_name = {n: t for t, (r, n) in objects.items()}
        self.by_norm = collections.defaultdict(list)
        for t, (r, n) in objects.items():
            self.by_norm[norm(n)].append(t)
        self.norms = sorted(self.by_norm)
        self.parsed = {t: parse_name(n) for t, (r, n) in objects.items()}
        self.mass = collections.defaultdict(list)   # (class, lvl) -> ids
        for t, (r, n) in objects.items():
            m = MASS_FIREARM.match(n)
            if m:
                self.mass[(m.group(1), int(m.group(3)))].append(t)

    def prefix(self, key):
        import bisect
        i = bisect.bisect_left(self.norms, key)
        out = []
        while i < len(self.norms) and self.norms[i].startswith(key):
            out += self.by_norm[self.norms[i]]
            i += 1
        return out

    def revprefix(self, key):
        for length in range(len(key) - 1, 5, -1):
            if key[:length] in self.by_norm:
                return self.prefix(key[:length])
        return []

    def variants(self, ids):
        out = collections.defaultdict(list)
        for t in ids:
            base, tier, mod, extra = self.parsed[t]
            key = tier + (":" + mod if mod else "")
            if extra:
                key += "+" + "_".join(extra)
            out[key].append(t)
        return {k: sorted(v) for k, v in sorted(out.items())}

    def link(self, method, confidence, key, ids, **more):
        ids = sorted(set(ids))
        rec = dict(method=method, confidence=confidence, key=key,
                   type_ids=ids, names=sorted(self.objects[t][1] for t in ids),
                   variants=self.variants(ids))
        rec.update(more)
        return rec


def page_kind(cats):
    for kind, names in KIND_ORDER:
        if names & set(cats):
            return kind
    return "other"


def title_mod(title, kind):
    m = re.search(r"\bMod\s*([IVX]+)\b", title)
    if not m:
        return None
    table = KNIFE_MOD if kind == "coldarm" else MOD_SUFFIX
    return table.get(m.group(1), "unknown:" + m.group(1))


def column_tier(col):
    c = col.replace("Р", "P").replace("А", "A")
    if re.search(r"\(P\)|^P$|\bP\b", c):
        return "P"
    if re.search(r"\(G\)|^G$|\bG\b", c):
        return "G"
    return "A"


def skill_levels(page):
    """[(column label, shooting skill level)] from the stats table."""
    out = []
    for tab in parse_tables(page["wikitext"]):
        for label, cells in tab["rows"]:
            if not re.match(r"Необх[ио]димые навыки", label):
                continue
            cols = tab["columns"][1:] or [""]
            for i, cell in enumerate(cells):
                m = re.search(r"Стрельба\s*(\d+)", cell)
                if m:
                    out.append((cols[i] if i < len(cols) else "", int(m.group(1))))
            if out:
                return out
    return out


def link_icons(cat, page, title=None):
    links = []
    seen = set()
    for img in image_names(page):
        key = norm(img)
        if not key or key in seen or key in WRONG_ICONS                 or key in WRONG_PAGE_ICONS.get(title, ()):
            continue
        seen.add(key)
        if key in cat.by_norm:
            links.append(cat.link("icon_exact", 0.95, img, cat.by_norm[key]))
            continue
        if len(key) >= 6:
            ids = cat.prefix(key)
            if ids and len(ids) <= 80:
                links.append(cat.link("icon_prefix", 0.8, img, ids))
                continue
            ids = cat.revprefix(key)
            if ids and len(ids) <= 80:
                links.append(cat.link("icon_revprefix", 0.7, img, ids))
    return links


def link_title(cat, title):
    key = norm(re.sub(r"\s*\((R|Rw|RW|G|Q|P|A)\)\s*$", "", title))
    if key in cat.by_norm:
        return [cat.link("title", 0.9, title, cat.by_norm[key])]
    return []


def link_blueprint(cat, title):
    m = KNIFE_BP_TITLE.match(title)
    if m:
        name = "bpg_knife_lvl%s_%s" % (m.group(3), KNIFE_BLUEPRINT[m.group(1)])
        if name in cat.by_name:
            return [cat.link("blueprint", 0.85, title, [cat.by_name[name]])]
        return []
    m = BLUEPRINT_TITLE.match(title)
    if not m:
        return []
    effect, lvl = m.group(1).strip(), m.group(2)
    if effect.startswith("Зашифрованный чертеж"):
        name = "codified_bp_" + lvl
        if name in cat.by_name:
            return [cat.link("blueprint", 0.9, title, [cat.by_name[name]])]
        return []
    if effect in BLUEPRINT_EFFECT:
        name = "bpg_%s_lvl%s" % (BLUEPRINT_EFFECT[effect], lvl)
        if name in cat.by_name:
            return [cat.link("blueprint", 0.9, title, [cat.by_name[name]])]
        return []
    if effect in BLUEPRINT_COMBO:
        stem = "bpg_%s" % BLUEPRINT_COMBO[effect]
        ids = [cat.by_name[n] for n in (stem + "_lvl" + lvl, stem + "_afro_lvl" + lvl,
                                        stem + "_pm_lvl" + lvl, stem + "_gold_lvl" + lvl)
               if n in cat.by_name]
        if ids:
            return [cat.link("blueprint", 0.5, title, ids)]
    return []


def link_ammo(cat, title, page):
    links = []
    if title in AMMO_NAMES:
        names, conf = AMMO_NAMES[title]
        ids = [cat.by_name[n] for n in names if n in cat.by_name]
        if ids:
            links.append(cat.link("manual", conf, title, ids))
    if title in AMMO_CALIBRE:
        columns = []
        for tab in parse_tables(page["wikitext"]):
            cols = [c for c in tab["columns"][1:] if c in AMMO_COLUMN]
            if cols:
                columns = cols
                break
        by_col = {}
        for col in columns:
            for calibre in AMMO_CALIBRE[title]:
                name = "Ammo_%s_%s" % (calibre, AMMO_COLUMN[col])
                if name in cat.by_name:
                    by_col[col] = cat.by_name[name]
                    break
        ids = list(by_col.values())
        if ids:
            links.append(cat.link("calibre", 0.9, "|".join(AMMO_CALIBRE[title]), ids,
                                  by_column={c: [i] for c, i in by_col.items()}))
    return links


def link_manual(cat, title):
    for pattern, templates, conf in MANUAL:
        m = re.match(pattern, title)
        if not m:
            continue
        n = ROMAN.get(m.group(1), 0) if m.groups() else 0
        names = [t.format(n=n, r=m.group(1) if m.groups() else "",
                          pik=PIKODIN.get(n, "")) for t in templates]
        ids = [cat.by_name[x] for x in names if x in cat.by_name]
        if ids:
            return [cat.link("manual", conf, title, ids)]
    return []


def link_firearm(cat, title, page, cats):
    classes = [FIREARM_CLASS[c] for c in cats if c in FIREARM_CLASS]
    if not classes:
        return []
    mod = title_mod(title, "firearm")
    if mod and mod.startswith("unknown"):
        return []
    links = []
    levels = skill_levels(page)
    if not levels:
        # No "Необходимые навыки" row, so the page states no level and there is
        # nothing to search. Unless the level was supplied by hand: then look in
        # that one, under each column label of the page's table -- an empty one,
        # which column_tier reads as the ordinary (A) variant, for a table with
        # no (P)/(G) columns (Самострел), and (A)/(P)/(G) for one with them
        # (РПД), so its gold copy is linked as every other line's is.
        manual = HAND_LEVEL.get(MOD_TAIL.sub("", title))
        if manual is None:
            return links
        cols = next((t["columns"][1:] for t in parse_tables(page["wikitext"])
                     if t["columns"][1:]), None) or [""]
        levels = [(c, manual) for c in cols]
    for col, lvl in levels:
        tier = column_tier(col)
        families = collections.defaultdict(list)
        for cls in classes:
            for t in cat.mass.get((cls, lvl), []):
                base, ptier, pmod, extra = cat.parsed[t]
                if ptier == tier and pmod == mod and not extra:
                    families[base].append(t)
        if not families:
            continue
        # A decision recorded by hand settles the line; the column and the
        # modification still pick the variant, so one entry covers the base
        # gun, its Mod pages and its (P)/(G) copies.
        chosen = HAND.get(MOD_TAIL.sub("", title))
        if chosen and chosen in families:
            families = {chosen: families[chosen]}
            method, conf = "hand", 1.0
        else:
            method, conf = "firearm_class_level", round(0.6 / len(families), 2)
        ids = [t for v in families.values() for t in v]
        links.append(cat.link(
            method, conf, "%s lvl %d %s%s" % (
                "/".join(classes), lvl, tier, " mod " + mod if mod else ""),
            ids, column=col, level=lvl,
            candidates=[dict(family=b, type_ids=sorted(v)) for b, v in sorted(families.items())]))
    return links


def narrow_by_mod(cat, links, mod, kind):
    """A "Mod IX" page shares its icon with the base weapon: keep the _mod_*
    variants only. Base pages keep everything, the caller reads variants."""
    if not mod:
        return links
    out = []
    for l in links:
        if l["method"].startswith("icon") or l["method"] == "title":
            ids = [t for t in l["type_ids"] if cat.parsed[t][2] == mod]
            if ids:
                out.append(cat.link(l["method"], l["confidence"], l["key"], ids, mod=mod))
            else:
                l = dict(l)
                l["confidence"] = round(l["confidence"] * 0.5, 2)
                l["note"] = "no _mod_%s variant in this family" % mod
                out.append(l)
        else:
            out.append(l)
    return out


def main():
    pages = load_pages()
    cat = Catalogue(load_objects())
    result = {}
    for title, page in sorted(pages.items()):
        if page["ns"] != 0:
            continue
        cats = categories(page)
        if not any(c in ITEM_CATEGORIES or c in FIREARM_CLASS for c in cats):
            continue
        kind = page_kind(cats)
        links = []
        if kind == "blueprint":
            links += link_blueprint(cat, title)
        if kind == "ammo":
            links += link_ammo(cat, title, page)
        links += link_manual(cat, title)
        icon_links = link_icons(cat, page, title) + link_title(cat, title)
        mod = title_mod(title, kind)
        links += narrow_by_mod(cat, icon_links, mod, kind)
        # A line recorded by hand is looked for even beside a firm link: two
        # articles' icons name something else -- MG-3's the standalone MG3
        # (192), СВД-С's its own precision Mod (26871) -- and without this the
        # line the original names after them (machine_gun_2_lvl_20,
        # rifle_1_lvl_20) kept the designed stand-in. Base pages only; a Mod
        # page still goes by its icon when it has one.
        if kind == "firearm" and (not any(l["confidence"] >= 0.5 for l in links)
                                  or (not mod and title in HAND)):
            links += link_firearm(cat, title, page, cats)
        # One record per (method, key). A firm link (blueprint title, exact
        # icon) makes the family-wide prefix links of the same page noise:
        # every blueprint page shares the "Codified bp" icon.
        uniq = {}
        for l in links:
            uniq.setdefault((l["method"], l["key"]), l)
        links = sorted(uniq.values(), key=lambda l: (-l["confidence"], l["method"], l["key"]))
        if links and links[0]["confidence"] >= 0.85:
            links = [l for l in links
                     if l["method"] not in ("icon_prefix", "icon_revprefix")]
        result[title] = dict(kind=kind, categories=sorted(cats), links=links,
                             mod=mod, confidence=max([l["confidence"] for l in links] or [0]))

    # Coverage.
    coverage = {}
    for name, group in GROUPS + [(c, {c}) for c in sorted(ITEM_CATEGORIES)]:
        members = [t for t, r in result.items() if group & set(r["categories"])]
        firm = [t for t in members if result[t]["confidence"] >= 0.5]
        weak = [t for t in members if 0 < result[t]["confidence"] < 0.5]
        methods = collections.Counter(
            l["method"] for t in members for l in result[t]["links"][:1])
        coverage[name] = dict(pages=len(members), linked=len(firm), candidates=len(weak),
                              methods=dict(methods))
    by_type = collections.defaultdict(list)
    for t, r in result.items():
        for l in r["links"]:
            if l["confidence"] >= 0.5:
                for i in l["type_ids"]:
                    by_type[i].append(t)
    meta = dict(
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        source="data/wiki/pages.json (CC BY-SA, lava-online.fandom.com/ru)",
        pages=len(result), linked_type_ids=len(by_type), coverage=coverage,
        mod_suffix=MOD_SUFFIX, knife_mod=KNIFE_MOD, ammo_column=AMMO_COLUMN)
    dump_json(OUT, dict(_meta=meta, pages=result,
                        by_type={str(k): sorted(set(v)) for k, v in by_type.items()}))
    print("%-24s %6s %7s %10s" % ("group", "pages", "linked", "candidates"), file=sys.stderr)
    for name, c in coverage.items():
        print("%-24s %6d %7d %10d   %s" % (name, c["pages"], c["linked"], c["candidates"],
                                          c["methods"]), file=sys.stderr)
    print("pages %d, type_ids linked %d -> %s" % (len(result), len(by_type), OUT),
          file=sys.stderr)


if __name__ == "__main__":
    main()
