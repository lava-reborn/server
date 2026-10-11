"""Item stats off the wiki mirror, typed and mapped onto the ss_si_* schema.

    wsl.exe -e python3 data/wiki_extract.py

Reads data/wiki/pages.json (see wiki_dump.py) and data/wiki_links.json
(wiki_links.py) and writes two files:

    data/wiki_items.json   every item article, parsed: description, all stat
                           tables typed (numbers, ranges, prices, booleans,
                           "Стрельба 4" -> {"Стрельба": 4}), bullet facts of
                           loot pages, and the link lists (quests, traders,
                           guardian mobs, modifications, ammunition, set)
    data/items_wiki.json   type_id -> ss_si_* fields for every type_id the
                           linker tied to a page with confidence >= 0.5;
                           the column is chosen by the variant (A/P/G) or
                           the required shooting level (I..VI), _wiki says
                           which page and column the numbers came from

The wiki tables are transcriptions of the client's tooltip (Annotation.as),
so every row maps onto one field; the conversions follow
recon/analysis/items.md section 7.2.

Table columns, as used on the wiki:

  Оружие(A) / Одежда (A) / Стимулятор (А)   ordinary item, sold for afro
  (P)                                        premium copy, _pm / _P in names
  (G)                                        gold copy, _gold / _G / _g
  I, II, III (... VI)                        grades of one named model: each
                                             is its own type_id with a higher
                                             required "Стрельба N" (N, N+1,
                                             N+2 or the levels of the family,
                                             lamantin_shotgun_4..8 for
                                             "КС-12" I..V), more damage,
                                             wear and price. For reward
                                             weapons (9А-91, ГШ-18, ТП-82)
                                             only the requirement differs.
  КС, КС(Р), СТ, ОТ, ОТ(PS), ЭК, ББ, СБ, ШК  ammunition qualities, see
                                             AMMO_COLUMN in wiki_links.py

Content is CC BY-SA (data/wiki/README.md).
"""
import collections
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_common import (HERE, FIREARM_CLASS, ROMAN, FIRE_ARM, WEAR, HEAL, AMMO, TRASH,
                         COLD_ARM, TROPHY, load_pages, load_objects, load_json, categories,
                         parse_tables, value, clean_cell, dump_json, parse_name)

LINKS = os.path.join(HERE, "wiki_links.json")
OUT_ITEMS = os.path.join(HERE, "wiki_items.json")
OUT_SI = os.path.join(HERE, "items_wiki.json")

# PersAttributes.as / Annotation.as:37-41 - the dense lists need_* and
# bonus_* are indexed in this order.
ATTRIBS = ["Сила", "Ловкость", "Телосложение", "Восприятие", "Интеллект"]
SKILLS = ["Ближний бой", "Стрельба", "Медицина", "Промышленность", "Производство"]
SPECS = ["Рукопашный бой", "Режущее оружие", "Пистолеты", "Дробовики", "Автоматы",
         "Винтовки", "Ручные пулеметы", "Пистолет-пулеметы", "Хирургия",
         "Первая помощь", "Добыча", "Переработка", "Мастер свинца",
         "Мастер селитры", "Мастер меди"]
# Annotation.as:735-755, same numbering as server/items.py SLOT_*.
SLOT = {"Головной убор": 0, "Верхняя одежда": 1, "Броня": 2, "Пояс": 3,
        "Штаны": 4, "Ботинки": 5}
# FireArm.as:38-43.
WEAPON_TYPE = {"pistols": 0, "shotgun": 1, "assault_rifle": 2, "rifle": 3,
               "machine_gun": 4, "sub_machine_guns": 5}

MODE_SECTIONS = {"первый режим стрельбы": 0, "первий режим стрельбы": 0,
                 "второй режим стрельбы": 1, "третий режим стрельбы": 2,
                 "режим 1": 0, "режим 2": 1, "режим 3": 2}

LIST_SECTIONS = {
    "Квесты": "quests", "Участвует в квестах": "quests", "Участвует в квест": "quests",
    "Учавствует в квестах": "quests",
    "Продажа": "traders", "Модификации": "modifications", "Боеприпасы": "ammo",
    "Мобы-хранители": "mobs", "Моб-хранитель": "mobs", "Моб-Хранитель": "mobs",
    "НПС-хранители": "npcs", "Комплект": "set", "Комплектация": "set_items",
    "Награжденные": "awarded", "Награжденые": "awarded",
}

# Row labels, by field, with the spellings met on the wiki.
LABELS = {
    "dmg": ["Урон по здоровью", "Урон здоровью"],
    "st_dmg": ["Урон по выносливости"],
    "spread": ["Разброс на 100 метров"],
    "range": ["Максимальная дистанция"],
    "opt": ["Оптимальная"],
    "burst": ["Длина очереди"],
    "aim": ["Время на изготовку"],
    "ap": ["Очки действия", "Очки действия на выстрел"],
    "pierce": ["Бронебойность"],
    "clip": ["Емкость магазина/обоймы", "Количество патронов"],
    "ammo_type": ["Тип патронов"],
    "reload_time": ["Время перезарядки"],
    "reload_cost": ["Очки действия перезарядки"],
    "wear": ["Износ"],
    "exchange": ["Допустимость обмена"],
    "sell": ["Допустимость продажи"],
    "weight": ["Вес", "Вес 1 шт.", "Вес 1 шт"],
    "cost": ["Базовая цена", "Базовая цена:"],
    "premium": ["Премиумность", "Премеумность"],
    "need_skills": ["Необходимые навыки", "Необхидимые навыки"],
    "need_attribs": ["Необходимые атрибуты", "Необходимые аттрибуты"],
    "need_specs": ["Необходимые специализации"],
    "pvp": ["Необходимый навык бойца", "Необходимы навык бойца", "Навык бойца"],
    "bonus_attribs": ["Бонусы к атрибутам", "Бонусы к аттрибутам", "Бонус к атрибутам"],
    "bonus_skills": ["Бонусы к навыкам"],
    "bonus_specs": ["Бонусы к специализациям", "Бонусы к специализации"],
    "hp": ["Здоровье", "Бонус к здоровью", "Бонусы к здоровью"],
    "st": ["Выносливость", "Бонус к выносливости"],
    "od": ["Очки действия", "Бонус к очкам действия"],
    "cp": ["Крит. попадание", "Крит. попадания", "Шанс крита", "Бонус к критическому попаданию"],
    "ce": ["Избег. крит. попадания", "Избег. крит. попадание"],
    "armor": ["Уровень брони"],
    "slot": ["Тип"],
    "h_rest": ["Восстанавливаемое здоровье"],
    "st_rest": ["Восстанавливаемое стамина"],
    "portions": ["Кол-во порций", "Кол-во доз", "Количество использований"],
    "duration": ["Время действия", "Время действия (минут)"],
    "prob": ["Вероятность срабатывания"],
    "a_range": ["Дальнобойность"],
    "a_acc": ["Точность"],
    "exp_mobs": ["Бонус к опыту с мобов"],
    "exp_players": ["Бонус к опыту с игроков"],
    "loot": ["Бонус к луту с мобов"],
    "speed": ["Скорость"],
    "intercept": ["Шанс перехвата"],
}


def key_norm(s):
    return re.sub(r"[^а-яa-z0-9]", "", s.lower().replace("ё", "е"))


MODE_SECTIONS = {key_norm(k): v for k, v in MODE_SECTIONS.items()}
MODE_FIELDS = {"dmg", "st_dmg", "spread", "range", "opt", "burst", "aim", "ap", "pierce"}
LABEL_INDEX = {}
for _field, _names in LABELS.items():
    for _n in _names:
        LABEL_INDEX.setdefault(key_norm(_n), []).append(_field)
KNOWN_LABELS = set(LABEL_INDEX)
ATTR_INDEX = {key_norm(a): i for i, a in enumerate(ATTRIBS)}
ATTR_INDEX[key_norm("Интелект")] = 4
SKILL_INDEX = {key_norm(s): i for i, s in enumerate(SKILLS)}
# "Медецина 6" on the "Аптечка «Стандарт»" page: the one misspelling of the
# skill in the dump, and it hides the requirement that proves the kits follow
# the same Медицина 0/2/4/6/8/10 ladder as bandages and food.
SKILL_INDEX[key_norm("Медецина")] = 2
SPEC_INDEX = {key_norm(s): i for i, s in enumerate(SPECS)}
SPEC_INDEX[key_norm("Режущие оружие")] = 1
SPEC_INDEX[key_norm("Ручные пулемёты")] = 6


# --- article structure -----------------------------------------------------

SECTION = re.compile(r"^(=+)\s*(.+?)\s*\1\s*$", re.M)
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
BULLET = re.compile(r"^\*\s*(.+?)\s*'''\s*\"?([^\"']*?)\"?\s*\.?\s*'''", re.M)
PRICE = re.compile(r"Цена в\s+(?:\[\[[^\]]*\]\]|афро|унциях золота)\s*'''\s*\"?([^\"']*?)\"?\s*\.?'''", re.M)
BP_DESC = re.compile(r"'''Описание'''\s*\n(.+?)(?:\n\s*\n|\n\*)", re.S)


def sections_of(wikitext):
    """[(title, body)] for level-2 sections; deeper ones fold into the parent."""
    out, cur, buf = [], "", []
    for line in wikitext.split("\n"):
        m = SECTION.match(line)
        if m and len(m.group(1)) <= 2:
            out.append((cur, "\n".join(buf)))
            cur, buf = clean_cell(m.group(2)), []
        elif m:
            buf.append(line)
        else:
            buf.append(line)
    out.append((cur, "\n".join(buf)))
    return out


def description_of(wikitext):
    for title, body in sections_of(wikitext):
        if title.startswith("Описание"):
            text = re.sub(r"\[\[Файл:[^\]]*\]\]", "", body)
            text = re.sub(r"^\{\|.*?^\|\}", "", text, flags=re.S | re.M)
            text = re.sub(r"^=+.*$", "", text, flags=re.M)
            text = re.sub(r"^\*.*$", "", text, flags=re.M)
            text = clean_cell(text)
            return re.sub(r"\n{2,}", "\n", text).strip()
    m = BP_DESC.search(wikitext)
    if m:
        return clean_cell(m.group(1)).strip()
    return ""


def lists_of(wikitext):
    out = collections.defaultdict(list)
    for title, body in sections_of(wikitext):
        key = LIST_SECTIONS.get(clean_cell(re.sub(r"\[\[[^\]]*\|", "[[", title)))
        if not key:
            continue
        for target in LINK.findall(body):
            target = target.strip()
            if target.startswith(("Файл:", "Категория:", "http")) or not target:
                continue
            if target not in out[key]:
                out[key].append(target)
    return dict(out)


def bullets_of(wikitext):
    """Loot pages state their facts as bullets: key '''"value".'''"""
    facts = {}
    for key, val in BULLET.findall(wikitext):
        key = clean_cell(key).rstrip(":").strip()
        facts[key] = value(val.replace("гр", "г"))
    prices = PRICE.findall(wikitext)
    price = {}
    if prices:
        price["afro"] = value(prices[0])
    if len(prices) > 1:
        price["g"] = value(prices[1])
    return facts, price


# --- tables ----------------------------------------------------------------

def column_tier(col):
    c = col.replace("Р", "P").replace("А", "A").strip()
    if c in ROMAN:
        return c
    if re.search(r"\(P\)|^P$", c):
        return "P"
    if re.search(r"\(G\)|^G$", c):
        return "G"
    if re.search(r"\(У\)", c):
        return "U"
    return "A"


def typed_table(tab):
    """Parsed wikitable -> {"columns", "tiers", "sections": {sec: {label: [v]}}}.

    Mode headers ("Первый режим стрельбы", or a "Режим 1" packed with its
    sub-rows into one <br>-separated cell) open a section keyed "0".."2";
    everything else lands in "общие". Tables with fewer than two known
    labels (player rankings, image grids) are dropped.
    """
    columns = tab["columns"][1:] or [""]
    ncol = max(1, len(columns))
    sections = collections.OrderedDict()
    cur = "общие"
    known = 0
    for label, cells in tab["rows"]:
        if not label:
            continue
        head, *subs = [x for x in label.split("\n") if x.strip()]
        head_key = key_norm(head)
        if head_key in MODE_SECTIONS:
            cur = str(MODE_SECTIONS[head_key])
            sections.setdefault(cur, collections.OrderedDict())
            if not subs:
                continue
            subs = [s.lstrip("-").strip() for s in subs]
            for ci, cell in enumerate(cells[:ncol]):
                vals = [v for v in cell.split("\n") if v.strip()]
                if len(vals) == len(subs) + 1 and key_norm(vals[0]) in MODE_SECTIONS:
                    vals = vals[1:]
                if len(vals) != len(subs):
                    continue
                for s, v in zip(subs, vals):
                    row = sections[cur].setdefault(s, [None] * ncol)
                    row[ci] = value(v)
                    if key_norm(s) in KNOWN_LABELS:
                        known += 1
            continue
        if subs and not any(c.strip() for c in cells):
            continue
        if not any(c.strip() for c in cells) and key_norm(head) not in KNOWN_LABELS:
            cur = head
            sections.setdefault(cur, collections.OrderedDict())
            continue
        vals = [value(c) for c in cells[:ncol]] + [None] * (ncol - len(cells))
        # General rows (wear, weight, price...) follow the last fire mode in
        # the table; only per-shot figures belong to the mode itself.
        dest = cur
        if cur in ("0", "1", "2") and not (set(LABEL_INDEX.get(key_norm(head), [])) & MODE_FIELDS):
            dest = "общие"
        sections.setdefault(dest, collections.OrderedDict())[head.rstrip(":").strip()] = vals
        if key_norm(head) in KNOWN_LABELS:
            known += 1
    if known < 2:
        return None
    return {"columns": columns, "tiers": [column_tier(c) for c in columns],
            "sections": sections}


def field_rows(table, field, section=None):
    """Values (per column) of the first row that means `field`."""
    secs = [section] if section else [s for s in table["sections"] if s not in "012"]
    for sec in secs:
        for label, vals in table["sections"].get(sec, {}).items():
            if field in LABEL_INDEX.get(key_norm(label), []):
                return vals
    return None


# --- ss_si_* fields --------------------------------------------------------

def as_range(v):
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return v[0], v[1]
    if isinstance(v, (int, float)):
        return v, v
    return None


def as_num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, dict) and "pct" in v:
        return v["pct"]
    if isinstance(v, dict) and "sec" in v:
        return v["sec"]
    if isinstance(v, list):
        for x in v:
            n = as_num(x)
            if n is not None:
                return n
    return None


def named(v):
    """{"Стрельба": 4, "Ловкость": 2} from a cell (or list of cells)."""
    out = {}
    if isinstance(v, dict):
        for k, n in v.items():
            if k not in ("afro", "g", "pvp", "pct", "sec"):
                out[k] = n
    elif isinstance(v, list):
        for x in v:
            out.update(named(x))
    elif isinstance(v, str):
        for m in re.finditer(r"([А-Яа-яЁё][А-Яа-яЁё .-]*?)\s*([-+]?\d+)", v):
            out[m.group(1).strip()] = int(m.group(2))
    return out


def dense(mapping, index, size):
    """(mask, values) the way Item.parseNeedBonus expects them."""
    mask, vals = 0, []
    slots = {}
    for name, n in mapping.items():
        i = index.get(key_norm(name))
        if i is None:
            for k, idx in index.items():
                if key_norm(name).startswith(k[:6]):
                    i = idx
                    break
        if i is not None:
            slots[i] = n
    for i in range(size):
        if i in slots:
            mask |= 1 << i
            vals.append(slots[i])
    return mask, vals


def money(si, v):
    if isinstance(v, dict):
        if "afro" in v:
            si["cost"] = v["afro"]
        if "g" in v:
            si["g_cost"] = int(round(v["g"] * 100))
        if "pvp" in v:
            si["bg_p_cost"] = v["pvp"]
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        si["cost"] = v


def common_fields(table, col, tier):
    si = {}
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    v = g("weight")
    if as_num(v) is not None:
        si["weight"] = as_num(v)
    money(si, g("cost"))
    v = g("exchange")
    if isinstance(v, bool):
        si["exchang"] = int(v)
    v = g("sell")
    if isinstance(v, bool):
        si["sellable"] = int(v)
    v = g("premium")
    if isinstance(v, bool) or tier == "P":
        si["premium"] = 1 if (v is True or tier == "P") else 0
    v = g("wear")
    if as_num(v) is not None:
        si["max_break_abs"] = as_num(v)
    v = g("pvp")
    if as_num(v) is not None:
        si["need_pvp_rep"] = as_num(v)
    for field, index, size, key in (("need_attribs", ATTR_INDEX, 5, "need_attribs"),
                                    ("need_skills", SKILL_INDEX, 5, "need_skills"),
                                    ("need_specs", SPEC_INDEX, 15, "need_specs"),
                                    ("bonus_attribs", ATTR_INDEX, 5, "bonus_attribs"),
                                    ("bonus_skills", SKILL_INDEX, 5, "bonus_skills"),
                                    ("bonus_specs", SPEC_INDEX, 15, "bonus_specs")):
        v = g(field)
        if v is None:
            continue
        mask, vals = dense(named(v), index, size)
        if mask:
            si[key + "_m"] = mask
            si[key] = vals
    for field, key in (("hp", "bonus_hp"), ("st", "bonus_st"), ("cp", "bonus_cp"),
                       ("ce", "bonus_ce")):
        v = g(field)
        if as_num(v) is not None:
            si[key] = as_num(v)
    return si


def mode_fields(table, col):
    """The three fire modes of a firearm as parallel lists."""
    modes = {}
    secs = table["sections"]
    for i in range(3):
        sec = str(i)
        if sec not in secs and i == 0 and field_rows(table, "dmg"):
            sec = None   # single-mode table without a mode header
        elif sec not in secs:
            continue
        rows = lambda f: (field_rows(table, f, sec) or [None] * (col + 1))[col] \
            if field_rows(table, f, sec) else None
        dmg = as_range(rows("dmg"))
        if not dmg:
            continue
        m = dict(h_damage_min=dmg[0], h_damage_max=dmg[1])
        st = as_range(rows("st_dmg"))
        m["st_damage_min"], m["st_damage_max"] = st if st else (0, 0)
        m["max_range"] = as_num(rows("range")) or 0
        opt = as_range(rows("opt"))
        m["opt_range"], m["end_opt_range"] = opt if opt else (0, m["max_range"])
        spread = as_num(rows("spread"))
        # FireArm.as:84 shows accuracy = 100 * target_size / max_range.
        m["target_size"] = round(spread * m["max_range"] / 100, 3) if spread and m["max_range"] else 0
        m["piercing"] = as_num(rows("pierce")) or 0
        m["fire_mods"] = as_num(rows("burst")) or 1
        aim = as_num(rows("aim"))
        m["fire_times"] = int(round(aim * 1000)) if aim else 0
        m["fire_costs"] = as_num(rows("ap")) or 0
        modes[i] = m
    if not modes:
        return None
    out = {}
    for key in ("h_damage_min", "h_damage_max", "st_damage_min", "st_damage_max",
                "max_range", "opt_range", "end_opt_range", "target_size", "piercing",
                "fire_mods", "fire_times", "fire_costs"):
        out[key] = [modes[i][key] if i in modes else 0 for i in range(3)]
    return out


def firearm_fields(table, col, tier, cls):
    si = common_fields(table, col, tier)
    modes = mode_fields(table, col)
    if not modes:
        return None
    si.update(modes)
    if cls in WEAPON_TYPE:
        si["weapon_type"] = WEAPON_TYPE[cls]
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    v = as_num(g("clip"))
    if v:
        si["clip_size"] = v
    v = as_num(g("reload_time"))
    if v:
        si["reload_time"] = int(v * 1000) if v < 100 else int(v)
    v = as_num(g("reload_cost"))
    if v:
        si["reload_cost"] = v
    v = g("ammo_type")
    if isinstance(v, str):
        si["ammo_calibre"] = v
    elif isinstance(v, list):
        si["ammo_calibre"] = [x for x in v if isinstance(x, str)]
    return si


def coldarm_fields(table, col, tier):
    si = common_fields(table, col, tier)
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    dmg = as_range(g("dmg"))
    if not dmg:
        return None
    si["h_damage_min"], si["h_damage_max"] = dmg
    st = as_range(g("st_dmg"))
    si["st_damage_min"], si["st_damage_max"] = st if st else (0, 0)
    si["max_range"] = as_num(g("range")) or 1
    si["strike_cost"] = as_num(g("ap")) or 0
    return si


def wear_fields(table, col, tier):
    si = common_fields(table, col, tier)
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    v = as_num(g("armor"))
    if v is None:
        return None
    si["armor_class"] = v
    slot = g("slot")
    if isinstance(slot, str) and slot in SLOT:
        si["slot_type"] = SLOT[slot]
    v = as_num(g("od"))
    if v is not None:
        si["bonus_od"] = v
    return si


def ammo_fields(table, col, tier):
    si = common_fields(table, col, tier)
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    pct = lambda f: (as_num(g(f)) or 0) / 100.0
    if g("dmg") is None and g("a_range") is None:
        return None
    # Annotation.as:1036-1040: the tooltip prints (mod - 1) * 100 %, and
    # accuracy the other way round, (1 - acc_mod) * 100 %.
    si["dam_mod"] = round(1 + pct("dmg"), 3)
    si["st_mod"] = round(1 + pct("st_dmg"), 3)
    si["range_mod"] = round(1 + pct("a_range"), 3)
    si["acc_mod"] = round(1 - pct("a_acc"), 3)
    si["piercing"] = round(1 + pct("pierce"), 3)
    return si


def heal_fields(table, col, tier):
    si = common_fields(table, col, tier)
    g = lambda f: (field_rows(table, f) or [None] * (col + 1))[col] if field_rows(table, f) else None
    h = as_range(g("h_rest"))
    s = as_range(g("st_rest"))
    if not h and not s and as_num(g("duration")) is None and g("bonus_attribs") is None:
        return None
    si["min_h_rest"], si["max_h_rest"] = h if h else (0, 0)
    si["min_st_rest"], si["max_st_rest"] = s if s else (0, 0)
    v = as_num(g("ap"))
    if v is not None:
        si["heal_cost"] = v
    v = as_num(g("portions"))
    if v:
        si["use_count"] = v
    v = as_num(g("duration"))
    if v:
        si["bonus_act_time"] = v
    v = as_num(g("prob"))
    if v is not None:
        si["bonus_prob"] = v
    bonus = named(g("bonus_attribs"))
    for name, key in zip(ATTRIBS, ("str_bonus", "dex_bonus", "sta_bonus", "per_bonus", "int_bonus")):
        for k, n in bonus.items():
            if key_norm(k).startswith(key_norm(name)[:5]):
                si[key] = n
    for field, key in (("exp_mobs", "exp_mobs_pct"), ("exp_players", "exp_players_pct"),
                       ("loot", "loot_pct")):
        v = as_num(g(field))
        if v is not None:
            si[key] = v
    return si


def simple_fields(facts, price):
    si = {}
    for k, v in facts.items():
        kn = key_norm(k)
        if kn.startswith(key_norm("Допустимость обмена")) and isinstance(v, bool):
            si["exchang"] = int(v)
        elif kn.startswith(key_norm("Допустимость продажи")) and isinstance(v, bool):
            si["sellable"] = int(v)
        elif kn.startswith(key_norm("Продажа через аукцион")) and isinstance(v, bool):
            si["auction"] = int(v)
        elif kn.startswith(key_norm("Шанс выпадения при смерти")) and isinstance(v, bool):
            si["drop_on_death"] = int(v)
        elif kn.startswith(key_norm("Квестовый предмет")) and isinstance(v, bool):
            si["quest"] = int(v)
        elif kn.startswith(key_norm("Количество предметов в стеке")) and as_num(v):
            si["max_count"] = as_num(v)
        elif kn.startswith(key_norm("Вес")) and as_num(v) is not None:
            si["weight"] = as_num(v)
    if "afro" in price and as_num(price["afro"]) is not None:
        si["cost"] = as_num(price["afro"])
    if "g" in price and as_num(price["g"]) is not None:
        si["g_cost"] = int(round(as_num(price["g"]) * 100))
    return si or None


# --- driving it ------------------------------------------------------------

def pick_column(tables, tier, level=None):
    """(table, column index) for a variant tier or a required level."""
    best = None
    for tab in tables:
        tiers = tab["tiers"]
        if level is not None:
            skills = field_rows(tab, "need_skills")
            if skills:
                for ci, v in enumerate(skills):
                    n = named(v).get("Стрельба")
                    if n == level:
                        return tab, ci
        if tier in tiers:
            return tab, tiers.index(tier)
        if best is None:
            best = (tab, 0)
    if best and tier == "P" and "A" in best[0]["tiers"]:
        return best[0], best[0]["tiers"].index("A")
    return best


def build_si(root, tables, facts, price, col_choice, tier, cls):
    if col_choice and tables:
        tab, col = col_choice
        if root == FIRE_ARM:
            si = firearm_fields(tab, col, tier, cls)
        elif root == COLD_ARM:
            si = coldarm_fields(tab, col, tier)
        elif root == WEAR:
            si = wear_fields(tab, col, tier)
        elif root == AMMO:
            si = ammo_fields(tab, col, tier)
        elif root == HEAL:
            si = heal_fields(tab, col, tier)
        else:
            si = common_fields(tab, col, tier) or None
        if si:
            return si, "%s[%d]" % (tab["columns"][col] or "-", col)
    if facts or price:
        si = simple_fields(facts, price)
        if si:
            return si, "bullets"
    return None, None


# Cells the wiki mistyped. A table rather than a cleverer parser: the whole
# dump holds four cells shaped "N/M", three of them this one page's spread
# column across its (A)/(P)/(G) copies, and a fraction means nothing there.
# The modification's own text says precision is up 20 %, and the base Desert
# Eagle's spread is 7.3, so 7.3 * 0.8 = 5.84 -- the cell is "5.8" with the
# dot mistyped. Left unfixed it reaches target_size as a zero, which the
# client divides by (see the head of server/items.py).
CELL_FIXES = {
    ("Desert Eagle Mod XI", "Разброс на 100 метров", "5/8"): 5.8,
    # A price typed as text instead of the template the other cells use: the
    # number is the one written, in the currency written. Left as text, the
    # (A) gun had no price at all and kept the designed 120 afro.
    ("FN F2000", "Базовая цена", "78 900 Афро"): {"afro": 78900},
    ("СВД-С", "Базовая цена", "120 900 Афро"): {"afro": 120900},
}

# Rows a page leaves out that the original states. РПД's table has no
# «Необходимые навыки» row, and the level is what a gun's wearer needs
# (server/inventory.item_level): without it the gun asks for nothing and
# reads as a level-0 one. The original's own name for the line says 16 --
# texts.xml 3534 «РПД[A][16]» (data/orig_items.json) -- as does its price,
# 67 400 afro, every level-16 gun's.
ROW_FIXES = {
    ("РПД", "общие", "Необходимые навыки"): [{"Стрельба": 16}] * 3,
}


def repair_cells(title, tables):
    """Put the known mistyped cells of this page right, in place, and add
    the rows it leaves out (ROW_FIXES) to its first table."""
    for (page, section, label), value in ROW_FIXES.items():
        if page == title and tables:
            rows = tables[0].setdefault("sections", {}).setdefault(section, {})
            rows.setdefault(label, list(value))
    for table in tables:
        for section in (table.get("sections") or {}).values():
            for label, value in (section or {}).items():
                if not isinstance(value, list):
                    continue
                for i, cell in enumerate(value):
                    fix = CELL_FIXES.get((title, label, cell)) if isinstance(cell, str) else None
                    if fix is not None:
                        value[i] = fix


def main():
    pages = load_pages()
    objects = load_objects()
    links = load_json(LINKS)["pages"]
    items = {}
    for title, rec in links.items():
        page = pages[title]
        txt = page["wikitext"]
        tables = [t for t in (typed_table(x) for x in parse_tables(txt)) if t]
        repair_cells(title, tables)
        facts, price = bullets_of(txt)
        items[title] = dict(
            kind=rec["kind"], categories=rec["categories"],
            description=description_of(txt), tables=tables,
            bullets=facts, price=price, lists=lists_of(txt))

    si_out, conflicts = {}, 0
    for title, rec in links.items():
        it = items[title]
        classes = [FIREARM_CLASS[c] for c in rec["categories"] if c in FIREARM_CLASS]
        cls = classes[0] if len(classes) == 1 else None
        for link in rec["links"]:
            if link["confidence"] < 0.5:
                continue
            by_col = link.get("by_column") or {}
            col_of_id = {i: c for c, ids in by_col.items() for i in ids}
            for vkey, ids in link["variants"].items():
                tier = vkey.split(":")[0].split("+")[0]
                vmod = vkey.split("+")[0].split(":")[1] if ":" in vkey.split("+")[0] else None
                if vmod != rec["mod"] and link["method"] != "manual":
                    continue   # a Mod page describes its own variants
                for tid in ids:
                    root, name = objects[tid]
                    # Families like lamantin_shotgun_4..15 number their
                    # members by required level; that picks the I..VI column.
                    level = None
                    m = re.search(r"_(\d+)$", parse_name(name)[0])
                    if m and link["method"] in ("icon_prefix", "icon_exact"):
                        level = int(m.group(1))
                    if tid in col_of_id:
                        choice = None
                        for tab in it["tables"]:
                            if col_of_id[tid] in tab["columns"]:
                                choice = (tab, tab["columns"].index(col_of_id[tid]))
                                break
                    else:
                        choice = pick_column(it["tables"], tier, level)
                    si, where = build_si(root, it["tables"], it["bullets"], it["price"],
                                         choice, tier, cls)
                    if not si:
                        continue
                    si["name_ru"] = re.sub(r"\s*\((R|Rw|RW|Q)\)\s*$", "", title)
                    if it["description"]:
                        si["desc_ru"] = it["description"]
                    si["_wiki"] = dict(page=title, column=where, method=link["method"],
                                       confidence=link["confidence"], variant=vkey)
                    key = str(tid)
                    if key in si_out:
                        old = si_out[key]["_wiki"]
                        conflicts += 1
                        if (old["confidence"], old["method"] == "icon_exact") >= \
                                (link["confidence"], link["method"] == "icon_exact"):
                            continue
                    si_out[key] = si

    by_root = collections.Counter(objects[int(k)][0] for k in si_out)
    meta = dict(
        generated=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        source="data/wiki (CC BY-SA, lava-online.fandom.com/ru) via data/wiki_links.json",
        items=len(si_out), conflicts=conflicts,
        by_root={["firearm", "wear", "heal", "ammo", "simple", "coldarm", "trophy"][r]: n
                 for r, n in sorted(by_root.items())},
        fields="ss_si_* names as in server/items.py; sellable/auction/drop_on_death/"
               "ammo_calibre/*_pct/name_ru/desc_ru are wiki extras the server may ignore")
    dump_json(OUT_ITEMS, items)
    dump_json(OUT_SI, dict(_meta=meta, items=si_out))
    with_tables = sum(1 for i in items.values() if i["tables"])
    with_bullets = sum(1 for i in items.values() if i["bullets"])
    print("wiki_items: %d pages, %d with stat tables, %d with bullet facts" % (
        len(items), with_tables, with_bullets), file=sys.stderr)
    print("items_wiki: %d type_ids (%s), %d conflicts" % (
        len(si_out), meta["by_root"], conflicts), file=sys.stderr)


if __name__ == "__main__":
    main()
