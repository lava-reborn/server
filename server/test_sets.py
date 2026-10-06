"""Clothing sets: the slot every piece goes in, the owner's ladder, Локсли's
stall, and the ss_get_s_si / ss_si_set exchange.

In process first: items.static_info is what ss_get_si sends and sets.frame
what ss_get_s_si does, so every piece of every set is checked -- served,
named as the owner's page and the wiki name it, described, priced in one
currency, numbered as the wiki numbers it (or, where the wiki has nothing,
as the written rule designs it), in its own slot, in its set -- and every
set's frame: its figure, and its bonuses against the wiki's set page. Then
one server over the socket, for the window: whatever type is asked about,
one ss_si_set comes back with that type, and never a cmdAck.

    LAVA_RES=.../lava/res python3 server/test_sets.py
"""
import json
import logging
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = "utf-8"

# A database of its own before anything opens one: the exception path below
# imports server.py, which opens its Store at import.
DB = os.path.join(tempfile.mkdtemp(), "sets.db")
os.environ["LAVA_DB"] = DB

sys.path.insert(0, HERE)
import accounts  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import npcs  # noqa: E402
import orig_texts  # noqa: E402
import quests  # noqa: E402
import sets  # noqa: E402
import world  # noqa: E402
from protocol import decode  # noqa: E402

import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


cat = items.catalogue()
by_name = {n: t for t, (_r, n) in cat.items()}
SLOT = {"helm": 0, "shirt": 1, "armor": 2, "belt": 3, "pants": 4, "boots": 5}

# --- every piece in its own slot ---------------------------------------------
print("slots")
check("LVL names: the first word is the slot",
      [items.slot_of(n) for n in ("helm_Set_M_LVL_0_A_mod00", "shirt_Bs_M_LVL_2_P_mod03",
                                  "armor_Exzo_M_LVL_7_G_mod00", "pants_Mob_M_LVL_8_M_mod00",
                                  "boots_Bs_U_LVL_20_A_mod10")],
      [0, 1, 2, 4, 5])
check("a belt goes on the belt", items.slot_of("belt_assault_rifles"), 3)
check("a war hat on the head", items.slot_of("warhat_Lab"), 0)
check("a numbered series still reads its stem", items.slot_of("helm_3"), 0)
check("and a name that says nothing is a shirt, as before", items.slot_of("pumpkin"), 1)
lvl = [(t, n) for t, (r, n) in cat.items() if r == items.WEAR and "_LVL_" in n
       and n.split("_")[0] in SLOT]
check("the client has over fifteen thousand LVL pieces named for a slot", len(lvl) >= 15000, True)
check("each of them designed into the slot its first word names",
      [(t, n) for t, n in lvl
       if items.designed_info(t)[1]["slot_type"] != SLOT[n.split("_")[0]]][:5], [])
check("a mob's outfit (mob_Exzo_M_LVL_...) names no slot and stays where it was",
      items.designed_info(by_name["mob_Exzo_M_LVL_0_G_mod10"])[1]["slot_type"], 1)
belts = [t for t, (r, n) in cat.items() if r == items.WEAR and n.startswith("belt_")
         and not items._SERIES.match(n)]
check("and every belt_ into the belt slot",
      [t for t in belts if items.designed_info(t)[1]["slot_type"] != 3], [])

# --- the ladder ------------------------------------------------------------------
# The owner's wardrobe page as data/build_sets.py turned it into
# data/sets.json, written out here rather than read from the file, so the two
# are checked against each other. Per rung: its level, his name for it, the
# figure a full set draws (res/personages/<res>, 0 for none), the client's
# series the pieces are (chosen by their icons), set_type per variant -- the
# texts.xml row of the set those types formed in the original -- the pieces'
# names, the wiki pages their numbers come from (None: none on the wiki, so
# designed), and where the set's bonuses come from.
PIECES = ("helm", "shirt", "armor", "pants", "boots")


def rung(level, word, res, series, keys, words, pages=(), bonus=None):
    """pages: the wiki page per slot where it is not the piece's own name;
    None for a rung the wiki has no numbers for."""
    if pages is not None:
        pages = tuple(dict(pages).get(s, w) for s, w in zip(PIECES, words))
    return dict(level=level, word=word, res=res, series=series, keys=keys, words=words,
                pages=pages, bonus=bonus)


LADDER = (
    rung(1, "Беженец", 0, "Bs_M_LVL_0", {"A": 11218, "G": 11221},
         ("Панама", "Пончо", "Самодельная Броня", "Шорты", "Самодельные тапки"),
         dict(armor="Самодельная броня"), ("none", "Вещи Беженца")),
    rung(2, "Колонист", 102, "Set_M_LVL_2", {"A": 11167, "G": 11169},
         ("Гоглы с фильтром", "Рубашка", "Кусковая броня", "Джинсы", "Старые ботинки"),
         dict(helm="Каска строителя"), ("table", "Вещи Колонистов")),
    rung(4, "Странник", 114, "Set_M_LVL_11", {"A": 11191, "G": 11193},
         ("Шапка странника", "Плащ странника", "Броня странника", "Штаны странника",
          "Ботинки странника"), (), ("table", "Сет Странник")),
    rung(6, "Магриб", 101, "Bs_M_LVL_16", {"A": 11258, "G": 11260},
         ("Армейский шлем", "Армейская рубашка", "Общевойсковой бронежилет", "Армейские штаны",
          "Армейские ботинки"), (), ("table", "Армейские вещи")),
    rung(8, "Налетчик", 107, "Set_M_LVL_8", {"A": 11185, "G": 11187},
         ("Очки налетчика", "Куртка налетчика", "Бронежилет налетчика",
          "Кожаные штаны налетчика", "Ботинки налетчика"), (), ("table", "Налетчик")),
    rung(10, "Пустынник", 103, "Set_M_LVL_7", {"A": 11182, "G": 11184},
         ("Шлем пустынника", "Накидка пустынника", "Броня пустынника", "Штаны пустынника",
          "Сапоги пустынника"), (), ("table", "Пустынник")),
    rung(12, "Чёрный Ловелас", 111, "Bs_U_LVL_12", {"Q": 11120},
         ("Шлем Чёрного Ловеласа", "Жилет Чёрного Ловеласа", "Броня Чёрного Ловеласа",
          "Штанишки Чёрного Ловеласа", "Ботинки Чёрного Ловеласа"), None,
         ("text", "Снаряжение Чёрного Ловеласа")),
    rung(13, "Спецназ", 10, "Set_M_LVL_17", {"A": 11206, "G": 11208},
         ("Шлем спецназа", "Куртка спецназа", "Броня спецназа", "Штаны спецназа",
          "Ботинки спецназа"), (), ("table", "Спецназ")),
    rung(14, "Легионер", 1401, "Exzo_M_LVL_6", {"A": 10954, "G": 10956},
         ("Шлем легионера", "Плащ легионера", "Броня легионера", "Штаны легионера",
          "Ботинки легионера"), (), ("table", "Легионер")),
    rung(15, "Штурм-М", 80, "Exzo_M_LVL_16", {"A": 11002, "G": 11004},
         ("Шлем Штурм-М", "Жилет Штурм-М", "Броня Штурм-М", "Моторика Штурм-М", "Боты Штурм-М"),
         (), ("table", "Штурм-М")),
    rung(16, "Красное Эхо", 1601, "Exzo_M_LVL_8", {"A": 10961, "G": 10965},
         ("Шлем Красного Эхо", "Поддоспешник Красного Эхо", "Корпус Красного Эхо",
          "Моторика Красного Эхо", "Боты Красного Эхо"), (), ("table", "Красное Эхо")),
    rung(17, "Тёмное Эхо", 119, "Bs_U_LVL_16", {"Q": 11125},
         ("Шлем Тёмного Эха", "Жилет Тёмного Эха", "Броня Тёмного Эха", "Моторика Тёмного Эха",
          "Ступни Тёмного Эха"),
         dict(helm="Шлем Темного Эха", shirt="Жилет Темного Эха", armor="Броня Темного Эха",
              pants="Моторика Темного Эха", boots="Ступни Темного Эха"), ("text", "Темное Эхо")),
    rung(18, "Дредноут", 77, "Exzo_M_LVL_18", {"A": 11016, "G": 11018},
         ("Шлем Дредноута", "Жилет Дредноута", "Броня Дредноута", "Моторика Дредноута",
          "Ступни Дредноута"), None, ("design", None)),
    rung(19, "Паладин", 76, "Exzo_M_LVL_19", {"A": 11030, "G": 11033},
         ("Шлем Паладина", "Жилет Паладина", "Броня Паладина", "Моторика Паладина",
          "Боты Паладина"), None, ("design", None)),
    rung(20, "Апокалипсис", 84, "Exzo_M_LVL_20", {"A": 11043, "G": 11046},
         ("Шлем Апокалипсиса", "Жилет Апокалипсиса", "Броня Апокалипсиса",
          "Моторика Апокалипсиса", "Боты Апокалипсиса"), (), ("table", "Модификация паладин")),
)
SOLD_UP_TO = 8          # Локсли sells the rungs up to this level; the rest is data only
SUFFIX = {"A": "", "G": " (G)", "Q": " (Q)"}
GROUPS = []             # one per set: the rung, its variant and set_type, its five types
for r in LADDER:
    for v, key in r["keys"].items():
        group = [by_name["%s_%s_%s_mod00" % (p, r["series"], v)] for p in PIECES]
        GROUPS.append(dict(r, v=v, key=key, types=group))
ALL_TYPES = [t for g in GROUPS for t in g["types"]]
LOXLEY = [t for g in GROUPS if g["level"] <= SOLD_UP_TO for t in g["types"]]
print()
print("the ladder")
check("15 rungs, 28 sets, 140 pieces", (len(LADDER), len(GROUPS), len(ALL_TYPES)), (15, 28, 140))
check("data/sets.json holds these sets and nothing else",
      sorted(sets.SETS), sorted(g["key"] for g in GROUPS))
check("..and these pieces", sorted(sets.ITEMS), sorted(ALL_TYPES))
with open(sets.PATH, encoding="utf-8") as fh:
    RAW = json.load(fh)["sets"]
check("the file says each set's rung, variant and series as the page has it",
      [(g["key"], RAW[str(g["key"])].get("level"), RAW[str(g["key"])].get("variant"),
        RAW[str(g["key"])].get("family")) for g in GROUPS
       if (RAW[str(g["key"])].get("level"), RAW[str(g["key"])].get("variant"),
           RAW[str(g["key"])].get("family")) != (g["level"], g["v"], g["series"].split("_LVL_")[0])],
      [])
wrong = []
for g in GROUPS:
    if {sets.set_of(t) for t in g["types"]} != {g["key"]}:
        wrong.append((g["word"], g["v"], "pieces in sets %r" % {sets.set_of(t) for t in g["types"]}))
    elif sets.SETS[g["key"]]["members"] != dict(zip(PIECES, g["types"])):
        wrong.append((g["word"], g["v"], "set lists %r" % sets.SETS[g["key"]]["members"]))
check("each group of five is one set, keyed by its texts.xml row, and that set is those five",
      wrong, [])
check("no P anywhere: the A and G of the series, and the quest family's one Q",
      [cat[t][1] for g in GROUPS for t in g["types"]
       if cat[t][1].split("_")[-2] != g["v"] or items.premium(t)], [])
check("the quest family (Bs_U) is Q alone, every other series A and G",
      {r["word"]: sorted(r["keys"]) for r in LADDER if r["series"].startswith("Bs_U")},
      {"Чёрный Ловелас": ["Q"], "Тёмное Эхо": ["Q"]})
check("the P copies of the ladder belong to no set and stand on no stall",
      [t for r in LADDER if "A" in r["keys"] for p in PIECES
       for t in [by_name["%s_%s_P_mod00" % (p, r["series"])]]
       if sets.set_of(t) or t in items.stock_for(5213)], [])
check("the sets are named as the owner names them, gold and quest ones the way every such thing is",
      [names.text(sets.NAME_ID_OFFSET + g["key"]) for g in GROUPS],
      [g["word"] + SUFFIX[g["v"]] for g in GROUPS])

# The figure: the page's res on every variant, a folder of res/personages
# with its .xml, and what a full set of each draws its wearer as.
check("every set's ss_si_set carries the rung's figure, the same on every variant",
      {g["key"]: sets.frame(g["key"])["res"] for g in GROUPS},
      {g["key"]: g["res"] for g in GROUPS})
check("..which is a figure for all but Беженец, the owner's '0': the wearer's own body",
      [r["word"] for r in LADDER if not r["res"]], ["Беженец"])
PERSONAGES = os.path.join(world.RES, "personages")
check("..and every figure is a folder of res/personages with its .xml",
      [r["res"] for r in LADDER if r["res"] and not (
          os.path.isdir(os.path.join(PERSONAGES, str(r["res"])))
          and os.path.isfile(os.path.join(PERSONAGES, "%d.xml" % r["res"])))], [])
check("..none of them the tutorial dummy or an animal",
      [r["res"] for r in LADDER if r["res"] in (1502, 96, 97, 98, 99, 125, 127, 143, 144, 1444)], [])
check("five pieces of a set, in either variant, draw that set's figure",
      {g["key"]: sets.look(g["types"]) for g in GROUPS}, {g["key"]: g["res"] for g in GROUPS})

# --- Локсли -------------------------------------------------------------------------
print()
print("Локсли")
check("the rungs up to level 8 are for sale: Беженец, Колонист, Странник, Магриб, Налетчик",
      [r["word"] for r in LADDER if r["level"] <= SOLD_UP_TO],
      ["Беженец", "Колонист", "Странник", "Магриб", "Налетчик"])
# and, last of all, the silk «Шелковый путь» sends a player to him for
# («Шелк находится в самом низу списка товаров», texts.xml 59817).
SILK = 3482
check("data/npcs.json sells exactly them, in order: level, A before G, helm to boots,"
      " then the quest's silk", npcs.stock(5213), LOXLEY + [SILK])
check("  ..50 types", len(LOXLEY), 50)
check("and the stall shows every one of them: nothing premium to filter out",
      items.stock_for(5213), LOXLEY + [SILK])
check("  ..nothing above level 8 on it",
      [t for t in items.stock_for(5213) if t not in LOXLEY + [SILK]], [])

# --- names and descriptions ----------------------------------------------------------
print()
print("words")
shown = {}
for g in GROUPS:
    for t, w in zip(g["types"], g["words"]):
        shown[t] = (names.text(items.STRING_ID_OFFSET + t), w + SUFFIX[g["v"]])
check("every piece is shown by its set's name for it, the gold one with (G), the quest one with (Q)",
      {t: got for t, (got, want) in shown.items() if got != want}, {})
orig = orig_texts.item_names()
check("  ..over the original's words for these types, which are another set's",
      (orig[by_name["helm_Set_M_LVL_8_A_mod00"]], orig[by_name["helm_Bs_M_LVL_0_G_mod00"]],
       names.text(items.STRING_ID_OFFSET + by_name["helm_Set_M_LVL_8_A_mod00"]),
       names.text(items.STRING_ID_OFFSET + by_name["helm_Bs_M_LVL_0_G_mod00"])),
      ("Гоглы с фильтром", "Очки-консервы (G)", "Очки налетчика", "Панама (G)"))
check("  ..and the pieces' names are all names.py adds for them: sets.item_names() under the item ids",
      {items.STRING_ID_OFFSET + t: n for t, n in sets.item_names().items()},
      {items.STRING_ID_OFFSET + t: n for t, (n, _w) in shown.items()})

descs = sets.item_descs()
check("every piece has a description of its own in the file", sorted(descs), sorted(ALL_TYPES))
check("  ..and that is the text under its description id",
      [t for t in ALL_TYPES if names.text(items.DESC_ID_OFFSET + t) != descs[t]], [])
check("  ..the wiki's, where the wiki has a page for the thing on the icon",
      [names.text(items.DESC_ID_OFFSET + by_name[n]) for n in (
          "shirt_Bs_M_LVL_0_A_mod00", "helm_Set_M_LVL_11_A_mod00", "helm_Bs_M_LVL_16_A_mod00")],
      ["Этот древнейший предмет одежды, пришедший к нам из Южной Америки. Хорошо защищает от "
       "солнца, ветра, песка и пыли.",
       "Плотная повязка на голову, защищающая от солнца и песка.",
       "Стальной армейский шлем времен первой мировой войны, сколько этого добра еще в песке лежит."])
check("  ..the original's row where it carries the wiki's very sentence: Панама, 22946, its "
      "Latin e made Cyrillic and its <br/> a space",
      [names.text(items.DESC_ID_OFFSET + by_name["helm_Bs_M_LVL_0_%s_mod00" % v]) for v in "AG"],
      ["Легкая шляпа с упругими полями, выполненная в стиле милитари. Неплохо защищает от солнца."] * 2)
check("  ..and the original's where the wiki's page repeats another piece's line: Боты Красного "
      "Эхо, Армейские штаны, Броня Апокалипсиса",
      [names.text(items.DESC_ID_OFFSET + by_name[n]) for n in (
          "boots_Exzo_M_LVL_8_A_mod00", "pants_Bs_M_LVL_16_A_mod00", "armor_Exzo_M_LVL_20_A_mod00")],
      ["Механизированные боты являются частью опорно-двигательного аппарата.",
       "Классическая армейская одежда. Военные стали частью нового стиля постапокалиптической "
       "моды - прочный материал, различные расцветки ткани, дешево и сердито.",
       "Эта Броня сочетает в себе все преимущества различных модификаций Паладина."])
check("  ..the wiki's slip mended where it is one letter: 'ИИногда'",
      names.text(items.DESC_ID_OFFSET + by_name["helm_Exzo_M_LVL_16_A_mod00"]),
      "Иногда кажется, что этот шлем самостоятельнее его обладателя.")
check("  ..never one about the dead man who wore it before (Шлем Красного Эхо's wiki line, "
      "the original's Налетчик boots)",
      [t for t in ALL_TYPES if re.search(r"труп|смерти|не спасли|дырка", descs[t])], [])
check("  ..and no name or description mixes a Latin letter into its Cyrillic words",
      [t for t in ALL_TYPES for text in (descs[t], shown[t][0])
       if re.search(r"[А-Яа-яЁё][A-Za-z]|[A-Za-z][А-Яа-яЁё]", text)], [])
strings = [names.text(sets.NAME_ID_OFFSET + g["key"]) for g in GROUPS]
strings += [names.text(sets.DESC_ID_OFFSET + g["key"]) for g in GROUPS]
strings += [names.text(items.STRING_ID_OFFSET + t) for t in ALL_TYPES]
strings += [names.text(items.DESC_ID_OFFSET + t) for t in ALL_TYPES]
check("every set string and every piece's name and description is one the launcher takes",
      [s for s in strings if not orig_texts.launcher_ok(s) or s.startswith("#")], [])
check("the sets' descriptions: the original's row where it has one, the wiki set page's otherwise",
      [names.text(sets.DESC_ID_OFFSET + g["key"]).split(".")[0].split(",")[0].split(" -")[0]
       for g in GROUPS if g["v"] != "G"],
      ["Добротная одежда беженца", "Добротная одежда колониста", "Добротная экипировка",
       "Добротная армейская экипировка", "Комплект", "В него можно аккуратно закутаться и укрыться "
       "от песка", "Комплекс снаряжения легендарной антитеррористической группы «ЛОВЕЛАС»",
       "Легкий удобный и надежный комплект Спецподразделений обеспечит вам непревзойденную "
       "маневренность и комфорт в боевой обстановке", "Тяжесть и мощь",
       "Современные наработки в области Экзоскелета", "Экзоскелет — устройство",
       "Модификация известного сета", "Новый комплект брони для выполнения самых сложных боевых "
       "операций", "Паладин", "Апокалипсис сочетает в себе все преимущества различных "
       "модификаций Паладина"])

# --- numbers: the wiki's ---------------------------------------------------------------
# Where the numbers come from: the wiki's own tables, data/wiki_items.json,
# column by column -- a piece's own variant's column where the page has A/P/G,
# the page's first column otherwise, which is the variant its price is in
# (the other variant copies it, its price converted at 4000 afro = 1 G); a
# quest piece is priced in afro. Стрельба asked is the rung's level.
#
# Every number the frame carries is held to it, and a key the wiki's table
# does not have is held to 0: a price, a bonus or a requirement changed in
# data/sets.json fails here. The places the file departs from the page on
# purpose are the four prices below, each written down in its set's _designed.
with open(os.path.join(HERE, "..", "data", "wiki_items.json"), encoding="utf-8") as fh:
    WIKI = json.load(fh)
NUMBERS = (("Уровень брони", "armor_class"), ("Износ", "max_break_abs"), ("Вес", "weight"),
           ("Выносливость", "bonus_st"), ("Здоровье", "bonus_hp"), ("Очки действия", "bonus_od"),
           ("Крит. попадание", "bonus_cp"),
           (("Избег. крит. попадание", "Избег. крит. попадания"), "bonus_ce"))
# The page's price that its own set page and its other column refute.
DESIGNED_PRICE = {
    by_name["helm_Set_M_LVL_8_G_mod00"]: (0, 250),         # Очки налетчика: 1.25 G on its page
    by_name["boots_Exzo_M_LVL_6_G_mod00"]: (0, 750),       # Ботинки легионера: 5 G on its page
    by_name["armor_Exzo_M_LVL_16_A_mod00"]: (210000, 0),   # Броня Штурм-М: 2 100 000 afro
    by_name["pants_Exzo_M_LVL_16_A_mod00"]: (140000, 0),   # Моторика Штурм-М: 120 000 afro
}


def half_up(x):
    return int(math.floor(x + 0.5 + 1e-9))


def price_of(cell):
    """('afro', n) or ('g', x) from a Базовая цена cell ("200 000 Афро" too)."""
    if isinstance(cell, dict):
        return ("afro", cell["afro"]) if "afro" in cell else ("g", cell["g"])
    return "afro", int(re.sub(r"\D", "", cell))


def wiki_price(cell, v):
    """(cost, g_cost) of a variant, converted at 4000 afro = 1 G when the
    column is priced in the other currency; a quest piece in afro."""
    cur, x = price_of(cell)
    if v in ("A", "Q"):
        return (x if cur == "afro" else half_up(x * 4000)), 0
    return 0, half_up((x if cur == "g" else x / 4000.0) * 100)


def flat(cell):
    """{name: value} out of a requirement cell: a dict, a list of them, or
    lists of lists."""
    out = {}
    if isinstance(cell, dict):
        out.update(cell)
    elif isinstance(cell, list):
        for x in cell:
            out.update(flat(x))
    return out


def need_of(p):
    """A frame's need_* masks and lists as {name: value}."""
    out = {}
    for kind, titles in sets.LISTS:
        vals = [0] * len(titles)
        dense = list(p.get("need_%s" % kind, []))
        for i in range(len(titles)):
            if p.get("need_%s_m" % kind, 0) >> i & 1:
                vals[i] = dense.pop(0) if dense else 0
        out.update({titles[i]: x for i, x in enumerate(vals) if x})
    return out


def served(t):
    """The numbers of a served frame this test holds to a rule."""
    p = items.static_info(t)[1]
    got = {key: p.get(key, 0) for _w, key in NUMBERS}
    got.update(cost=p.get("cost", 0), g_cost=p.get("g_cost", 0), need=need_of(p))
    return got


off = {}
for g in GROUPS:
    if g["pages"] is None:
        continue
    for t, page in zip(g["types"], g["pages"]):
        table = WIKI[page]["tables"][0]
        sec = table["sections"]["общие"]
        i = {"A": 0, "G": 2}[g["v"]] if table["tiers"] == ["A", "P", "G"] else 0
        want = {}
        for wkeys, key in NUMBERS:
            wkeys = (wkeys,) if isinstance(wkeys, str) else wkeys
            cells = [sec[k][i] for k in wkeys if k in sec]
            want[key] = (cells[0] or 0) if cells else 0
        want["cost"], want["g_cost"] = DESIGNED_PRICE.get(t) or wiki_price(sec["Базовая цена"][i], g["v"])
        need = {}
        for wkey in ("Необходимые атрибуты", "Необходимые навыки", "Необходимые специализации"):
            need.update(flat((sec.get(wkey) or [{}] * 3)[i]))
        need["Стрельба"] = g["level"]
        want["need"] = need
        got = served(t)
        for k in want:
            if want[k] != got[k]:
                off[(t, page, g["v"], k)] = (got[k], want[k])
check("every number of every piece with a wiki page is the wiki's: armour, durability, weight, "
      "stamina, health, action points, crit, anti-crit, price and requirements, 0 where the page "
      "has none", off, {})
check("  ..and the frame carries no bonus the check above did not look at",
      [(t, k) for t in ALL_TYPES for k, x in items.static_info(t)[1].items()
       if k.startswith("bonus_") and x and k not in {key_ for _w, key_ in NUMBERS}], [])
check("  ..Кусковая броня 20 (A) / 23 (G), Бронежилет налетчика 47 / 54, Корпус Красного Эхо "
      "274 / 345, Броня Тёмного Эха 638 (the page's first column), Броня Апокалипсиса 1143",
      [items.params_of(by_name[n])["armor_class"] for n in (
          "armor_Set_M_LVL_2_A_mod00", "armor_Set_M_LVL_2_G_mod00", "armor_Set_M_LVL_8_A_mod00",
          "armor_Set_M_LVL_8_G_mod00", "armor_Exzo_M_LVL_8_A_mod00", "armor_Exzo_M_LVL_8_G_mod00",
          "armor_Bs_U_LVL_16_Q_mod00", "armor_Exzo_M_LVL_20_G_mod00")],
      [20, 23, 47, 54, 274, 345, 638, 1143])
check("prices too: the wiki's afro, its gold in hundredths (0.25 G is 25), a quest piece's afro",
      [(items.params_of(by_name[n])["cost"], items.params_of(by_name[n])["g_cost"]) for n in (
          "helm_Set_M_LVL_2_A_mod00", "helm_Set_M_LVL_2_G_mod00", "armor_Set_M_LVL_8_A_mod00",
          "armor_Set_M_LVL_8_G_mod00", "helm_Set_M_LVL_11_G_mod00", "helm_Bs_U_LVL_16_Q_mod00")],
      [(1000, 0), (0, 25), (12000, 0), (0, 300), (0, 125), (200000, 0)])
check("  ..and where a variant has no column, its price at the wiki's 4000 afro = 1 G",
      [(items.params_of(by_name[n])["cost"], items.params_of(by_name[n])["g_cost"]) for n in (
          "helm_Set_M_LVL_11_A_mod00", "helm_Bs_M_LVL_0_G_mod00", "armor_Exzo_M_LVL_20_A_mod00")],
      [(5000, 0), (0, 13), (360000, 0)])
check("  ..the four the pages get wrong, as their set pages' totals say: Очки налетчика (G) 2.5 G, "
      "Ботинки легионера (G) 7.5 G, Броня Штурм-М 210 000, Моторика Штурм-М 140 000",
      {t: (items.params_of(t)["cost"], items.params_of(t)["g_cost"]) for t in DESIGNED_PRICE},
      DESIGNED_PRICE)
totals = {}
for g in GROUPS:
    if g["pages"] is None or g["bonus"][0] != "table":
        continue
    table = WIKI[g["bonus"][1]]["tables"][0]
    for sec in table["sections"].values():
        if "Цена комплекта" in sec:
            cells = sec["Цена комплекта"]
            cur, x = price_of(cells[{"A": 0, "G": 2}[g["v"]] if len(cells) == 3 else 0])
            if (cur == "g") == (g["v"] == "G"):
                key = "g_cost" if g["v"] == "G" else "cost"
                totals[(g["word"], g["v"])] = (sum(items.params_of(t)[key] for t in g["types"]),
                                               half_up(x * 100) if cur == "g" else x)
check("every set's pieces add up to its wiki page's price for the set",
      {k: v for k, v in totals.items() if v[0] != v[1]}, {})
check("  ..eighteen totals to hold them to", len(totals), 18)

# --- numbers: the designed ones ---------------------------------------------------------
# Three rungs have no numbers on the wiki. Each number of each piece is linear
# between the nearest rungs below and above that have them, by level, from
# their A (or quest) piece in the same slot, half up; afro prices to whole
# thousands; Телосложение likewise, a requirement only one neighbour has is
# not carried; Стрельба is the level. The G copies the A, priced at 4000 : 1.
WIKI_RUNGS = [r for r in LADDER if r["pages"] is not None]


def between(level, rungs):
    lo = [r for r in rungs if r["level"] <= level][-1]
    hi = [r for r in rungs if r["level"] > level][0]
    return lo, hi, (level - lo["level"]) / float(hi["level"] - lo["level"])


def base_types(r):
    v = "A" if "A" in r["keys"] else "Q"
    return [by_name["%s_%s_%s_mod00" % (p, r["series"], v)] for p in PIECES]


designed_off = {}
anchors = {}
for g in GROUPS:
    if g["pages"] is not None:
        continue
    lo, hi, t = between(g["level"], WIKI_RUNGS)
    anchors[g["word"]] = (lo["word"], hi["word"], round(t, 3))
    for slot, tt, a, b in zip(PIECES, g["types"], base_types(lo), base_types(hi)):
        a, b = served(a), served(b)
        want = {key: half_up(a[key] + (b[key] - a[key]) * t) for _w, key in NUMBERS}
        afro = half_up((a["cost"] + (b["cost"] - a["cost"]) * t) / 1000.0) * 1000
        want["cost"], want["g_cost"] = (0, afro // 40) if g["v"] == "G" else (afro, 0)
        want["need"] = {k: half_up(a["need"][k] + (b["need"][k] - a["need"][k]) * t)
                        for k in a["need"] if k in b["need"] and k != "Стрельба"}
        want["need"]["Стрельба"] = g["level"]
        got = served(tt)
        for k in want:
            if want[k] != got[k]:
                designed_off[(tt, g["word"], g["v"], k)] = (got[k], want[k])
check("the three rungs the wiki has no numbers for sit between their neighbours",
      anchors, {"Чёрный Ловелас": ("Пустынник", "Спецназ", 0.667),
                "Дредноут": ("Тёмное Эхо", "Апокалипсис", 0.333),
                "Паладин": ("Тёмное Эхо", "Апокалипсис", 0.667)})
check("  ..and every number of their pieces is the rule's", designed_off, {})
check("  ..Броня Дредноута 806 armour for 280 000 afro, Броня Паладина (G) 975 for 80 G, "
      "Броня Чёрного Ловеласа 109 for 50 000",
      [(items.params_of(by_name[n])["armor_class"], items.params_of(by_name[n])["cost"],
        items.params_of(by_name[n])["g_cost"]) for n in (
          "armor_Exzo_M_LVL_18_A_mod00", "armor_Exzo_M_LVL_19_G_mod00", "armor_Bs_U_LVL_12_Q_mod00")],
      [(806, 280000, 0), (975, 0, 8000), (109, 50000, 0)])

bad = {}
for g in GROUPS:
    for t in g["types"]:
        info = items.static_info(t)
        if not info:
            bad[t] = ["no static info: ss_get_si would go unanswered"]
            continue
        cmd, p = info
        why = []
        if cmd != "ss_si_wear":
            why.append("command %s" % cmd)
        if p["slot_type"] != SLOT.get(cat[t][1].split("_")[0]):
            why.append("slot_type %r" % p["slot_type"])
        if p["set_type"] != g["key"]:
            why.append("set_type %r" % p["set_type"])
        if not names.known(p["name"]):
            why.append("name id %r not preloaded" % p["name"])
        if p["desc"] != items.DESC_ID_OFFSET + t or not names.known(p["desc"]):
            why.append("desc %r" % p["desc"])
        for sid in (sets.NAME_ID_OFFSET + g["key"], sets.DESC_ID_OFFSET + g["key"]):
            if not names.known(sid):
                why.append("set string %d not preloaded" % sid)
        if "bg_p_cost" in p:
            why.append("bg_p_cost turns the purchase into one for battleground points")
        money = (p["cost"] > 0, p["g_cost"] > 0, p["premium"], p["exchang"])
        want = {"A": (True, False, 0, 1), "G": (False, True, 0, 0), "Q": (True, False, 0, 0)}[g["v"]]
        if money != want:
            why.append("cost/g_cost/premium/exchang %r for %s" % (
                (p["cost"], p["g_cost"], p["premium"], p["exchang"]), g["v"]))
        if p["armor_class"] < 1 or p["max_break_abs"] < 1 or p["weight"] < 1:
            why.append("armour/durability/weight %r" % ((p["armor_class"], p["max_break_abs"], p["weight"]),))
        for kind, n in (("attribs", 5), ("skills", 5), ("specs", 15)):
            m, vals = p.get("need_%s_m" % kind, 0), p.get("need_%s" % kind, [])
            if m >= 1 << n or bin(m).count("1") != len(vals):
                why.append("need_%s mask %r vs %r" % (kind, m, vals))
        # Стрельба is skill bit 1: the rung's level.
        shoot = (p.get("need_skills_m", 0), p.get("need_skills", []))
        if shoot != (2, [g["level"]]):
            why.append("Стрельба %r at level %d" % (shoot, g["level"]))
        if not p.get("need_attribs_m", 0) & 4:
            why.append("no Телосложение asked")
        if why:
            bad[t] = why
check("every piece: served, in its slot and set, described, priced once, Стрельба = its level",
      bad, {})
check("the one requirement beyond Телосложение and Стрельба: Апокалипсис asks 5 in every firearm "
      "specialisation, as its wiki pages do",
      sorted({(g["word"], k) for g in GROUPS for t in g["types"] for k in served(t)["need"]
              if k not in ("Телосложение", "Стрельба")}),
      sorted({("Апокалипсис", k) for k in ("Пистолеты", "Дробовики", "Автоматы", "Винтовки",
                                           "Ручные пулеметы", "Пистолет-пулеметы")}))


# The ladder: nothing gets weaker, cheaper or less durable as the level rises
# -- except where the wiki's own numbers say so and the owner placed the set
# there: Магриб (the wiki's Армейские вещи, 4 G) above Странник (5 G), and
# Красное Эхо (500 000 afro) above Штурм-М (700 000). Named, so a third one
# is news. A gold piece is never weaker than the afro one of its rung.
def total(group, key):
    return sum(items.params_of(t).get(key, 0) for t in group)


worse = []
for side in (("A", "Q"), ("G",)):
    prev = None
    for g in GROUPS:
        if g["v"] not in side:
            continue
        price = "g_cost" if g["v"] == "G" else "cost"
        now = (total(g["types"], "armor_class"), total(g["types"], price),
               total(g["types"], "max_break_abs"))
        if prev and any(a < b for a, b in zip(now, prev[1])):
            worse.append((side[0], prev[0], g["word"]))
        prev = (g["word"], now)
check("a higher rung is never weaker, cheaper or less durable but for the wiki's own two",
      worse, [("A", "Странник", "Магриб"), ("A", "Штурм-М", "Красное Эхо"),
              ("G", "Странник", "Магриб"), ("G", "Штурм-М", "Красное Эхо")])
pairs = [(ga, gg) for ga in GROUPS for gg in GROUPS
         if ga["word"] == gg["word"] and ga["v"] == "A" and gg["v"] == "G"]
check("a G piece is never weaker than its A: armour and stamina",
      [(a, g) for ga, gg in pairs for a, g in zip(ga["types"], gg["types"])
       if any(items.params_of(g).get(k, 0) < items.params_of(a).get(k, 0)
              for k in ("armor_class", "bonus_st"))], [])

# --- the frames ----------------------------------------------------------------
print()
print("ss_si_set")
READ = {"type", "res", "name", "desc"}
for k in sets.PIECES:
    READ |= {"bonus_%d_%s%s" % (k, kind, m) for kind in ("attribs", "skills", "specs")
             for m in ("", "_m")}
    READ |= {"bonus_%d_%s" % (k, key) for key in sets.SCALARS}
bad = {}
for st, s in sets.SETS.items():
    p = sets.frame(st)
    why = []
    if p["type"] != st:
        why.append("type %r" % p["type"])
    if p["name"] != sets.NAME_ID_OFFSET + st or not names.known(p["name"]):
        why.append("name %r" % p["name"])
    if p["desc"] != "" and not names.known(p["desc"]):
        why.append("desc %r" % p["desc"])
    if set(p) - READ:
        why.append("keys SetObject never reads: %s" % sorted(set(p) - READ))
    for k in sets.PIECES:
        for kind, n in (("attribs", 5), ("skills", 5), ("specs", 15)):
            m = p.get("bonus_%d_%s_m" % (k, kind))
            vals = p.get("bonus_%d_%s" % (k, kind))
            if (m is None) != (vals is None):
                why.append("K=%d %s: mask and list travel together" % (k, kind))
            elif m is not None and (not 0 < m < 1 << n or bin(m).count("1") != len(vals)
                                    or not all(vals)):
                why.append("K=%d %s: mask %r vs %r" % (k, kind, m, vals))
    for key, value in p.items():
        if key.startswith("bonus_") and not (isinstance(value, int) or
                                             all(isinstance(x, int) for x in value)):
            why.append("%s=%r" % (key, value))
    if why:
        bad[st] = why
check("every set's frame: its type, known strings, only keys SetObject reads, masks that fit",
      bad, {})

# Each set's bonuses from its wiki set page, read here on their own: the
# table wiki_items.json parses, the variant's column (a lone one serves every
# variant); for the two pages whose layout it does not parse, the page's
# wikitext itself; none for Вещи Беженца, which says so.
with open(os.path.join(HERE, "..", "data", "wiki", "pages.json"), encoding="utf-8") as fh:
    PAGES = json.load(fh)
BONUS = {"Здоровье": "hp", "Выносливость": "st", "Очки действия": "od", "Крит. попадание": "cp",
         "Избег. крит. попадание": "ce", "Избег. крит. попадания": "ce", "Интелект": "Интеллект"}


def table_bonus(page, v):
    table = WIKI[page]["tables"][0]
    i = {"A": 0, "G": 2}[v] if table["tiers"] == ["A", "P", "G"] else 0
    out = {}
    for section, rows in table["sections"].items():
        m = re.match(r"Комплект из (\d) предметов", section)
        if m:
            line = {BONUS.get(w.strip(), w.strip()): x[i] for w, x in rows.items()
                    if w != "Цена комплекта" and x[i] is not None}
            if line:
                out[int(m.group(1))] = line
    return out


def text_bonus(page):
    """The two free-form layouts: "Имя +N" lines under each '''Комплект из K
    предметов''' (Темное Эхо), and a row of "-Имя<br />" beside a row of
    "+N<br />" (Снаряжение Чёрного Ловеласа)."""
    wt = PAGES[page]["wikitext"]
    out = {}
    for row in wt.split("|-"):
        m = re.search(r"Комплект из (\d) предметов<br />", row)
        if m:
            words = re.findall(r"^-(.+?)<br />", row, re.M)
            values = re.findall(r"^\+(\d+)<br />", row, re.M)
            out[int(m.group(1))] = {BONUS.get(w.strip(), w.strip()): int(x)
                                    for w, x in zip(words, values)}
    if out:
        return out
    k = None
    for line in wt.splitlines():
        m = re.search(r"Комплект из (\d) предметов", line)
        if m:
            k = int(m.group(1))
            continue
        m = re.match(r"^\s*([А-Яа-яЁё. ]+?)\s+\+(\d+)\s*$", line)
        if m and k:
            out.setdefault(k, {})[BONUS.get(m.group(1).strip(), m.group(1).strip())] = int(m.group(2))
    return out


def frame_bonus(per_k):
    """{K: {bonus: value}} -> the ss_si_set keys SetObject.initSet reads."""
    out = {}
    for k, line in per_k.items():
        for key in sets.SCALARS:
            if line.get(key):
                out["bonus_%d_%s" % (k, key)] = line[key]
        for kind, titles in sets.LISTS:
            bits = [i for i, t in enumerate(titles) if line.get(t)]
            if bits:
                out["bonus_%d_%s_m" % (k, kind)] = sum(1 << i for i in bits)
                out["bonus_%d_%s" % (k, kind)] = [line[titles[i]] for i in bits]
    return out


def as_lines(frame):
    """A frame's bonus keys back to {K: {bonus: value}}."""
    out = {}
    for k in sets.PIECES:
        line = {key: frame["bonus_%d_%s" % (k, key)] for key in sets.SCALARS
                if "bonus_%d_%s" % (k, key) in frame}
        for kind, titles in sets.LISTS:
            m = frame.get("bonus_%d_%s_m" % (k, kind), 0)
            dense = list(frame.get("bonus_%d_%s" % (k, kind), []))
            for i, t in enumerate(titles):
                if m >> i & 1:
                    line[t] = dense.pop(0)
        if line:
            out[k] = line
    return out


def frame_of(g, per_k):
    return dict(type=g["key"], res=g["res"], name=sets.NAME_ID_OFFSET + g["key"],
                desc=sets.DESC_ID_OFFSET + g["key"], **frame_bonus(per_k))


want = {}
for g in GROUPS:
    kind, page = g["bonus"]
    if kind == "table":
        want[g["key"]] = frame_of(g, table_bonus(page, g["v"]))
    elif kind == "text":
        want[g["key"]] = frame_of(g, text_bonus(page))
    elif kind == "none":
        want[g["key"]] = frame_of(g, {})
check("every frame with a wiki set page is that page's column, whole: type, figure, strings, "
      "every K", {st: sets.frame(st) for st in want}, want)
check("  ..the two free-form pages read whole, as their wikitext lists them",
      [text_bonus(p) for p in ("Снаряжение Чёрного Ловеласа", "Темное Эхо")],
      [{2: {"hp": 50, "st": 20}, 3: {"st": 55, "od": 20, "Ловкость": 1},
        4: {"hp": 60, "st": 100, "ce": 17, "Интеллект": 1},
        5: {"st": 200, "cp": 17, "Сила": 2, "Телосложение": 3, "Восприятие": 2}},
       {2: {"st": 38, "ce": 6}, 3: {"st": 100, "Сила": 1, "Ловкость": 1},
        4: {"st": 150, "ce": 10, "Сила": 3, "Интеллект": 2},
        5: {"st": 250, "cp": 16, "Ловкость": 3, "Телосложение": 4, "Восприятие": 4}}])
check("  ..Модификация паладин is Апокалипсис's: it lists those five pieces, and its 300 G is "
      "their prices' sum",
      (sorted(WIKI["Модификация паладин"]["lists"]["set_items"]),
       sum(price_of(WIKI[p]["tables"][0]["sections"]["общие"]["Базовая цена"][0])[1]
           for p in WIKI["Модификация паладин"]["lists"]["set_items"])),
      (sorted(LADDER[-1]["pages"]), 300))
BONUS_RUNGS = [r for r in LADDER if r["bonus"][0] != "design"]
designed_want, designed_anchor = {}, {}
for g in GROUPS:
    if g["bonus"][0] != "design":
        continue
    lo, hi, t = between(g["level"], BONUS_RUNGS)
    designed_anchor[g["key"]] = (lo["word"], hi["word"])
    a = as_lines(sets.frame(list(lo["keys"].values())[0]))
    b = as_lines(sets.frame(list(hi["keys"].values())[0]))
    per_k = {}
    for k in sets.PIECES:
        line = {}
        for key in set(a.get(k, {})) | set(b.get(k, {})):
            x = half_up(a.get(k, {}).get(key, 0) + (b.get(k, {}).get(key, 0) - a.get(k, {}).get(key, 0)) * t)
            if x:
                line[key] = x
        if line:
            per_k[k] = line
    designed_want[g["key"]] = frame_of(g, per_k)
check("Дредноут and Паладин, with no set page, between Тёмное Эхо and Апокалипсис, K by K",
      set(designed_anchor.values()), {("Тёмное Эхо", "Апокалипсис")})
check("  ..every frame of theirs is the rule's",
      {st: sets.frame(st) for st in designed_want}, designed_want)
check("  ..Дредноут at five: +333 stamina, +17 crit, Ловкость 4, Телосложение 5, Восприятие 5",
      as_lines(sets.frame(11016))[5],
      {"st": 333, "cp": 17, "Ловкость": 4, "Телосложение": 5, "Восприятие": 5})
check("Беженец adds nothing, in either variant (Вещи Беженца has no bonus), and draws no figure",
      [sets.frame(st) for st in (11218, 11221)],
      [dict(type=st, res=0, name=sets.NAME_ID_OFFSET + st, desc=sets.DESC_ID_OFFSET + st)
       for st in (11218, 11221)])
check("Колонист[2] is the wiki's Вещи Колонистов: five pieces, +5 health, +1 crit, +1 anti-crit",
      sets.frame(11167), dict(type=11167, res=102, name=7011167, desc=7111167,
                              bonus_5_hp=5, bonus_5_cp=1, bonus_5_ce=1))
f = sets.frame(11185)
check("Налетчик (A): strength at 3 pieces is attribute bit 0",
      (f["bonus_3_attribs_m"], f["bonus_3_attribs"]), (1, [1]))
check("  ..strength and constitution at 5 are bits 0 and 2", (f["bonus_5_attribs_m"], f["bonus_5_attribs"]),
      (5, [1, 1]))
check("  ..and the rest of its column: 2, 3, 4 and 5 pieces as the wiki lists them",
      {k: v for k, v in f.items() if k.startswith("bonus_") and "attribs" not in k},
      dict(bonus_2_st=4, bonus_2_ce=2, bonus_3_st=10, bonus_3_od=6, bonus_4_hp=6,
           bonus_4_st=20, bonus_4_ce=3, bonus_5_st=35, bonus_5_cp=3))
check("Налетчик (G): its own column -- constitution +2 at five",
      (sets.frame(11187)["bonus_5_attribs"], sets.frame(11187)["bonus_3_od"]), ([1, 2], 10))
f = sets.frame(11191)
check("Странник: the wiki's one column in both variants, Интелект (sic) read as Интеллект",
      (f["bonus_5_attribs_m"], f["bonus_5_attribs"], sets.frame(11193)["bonus_5_attribs_m"]),
      (4 | 8 | 16, [1, 1, 1], 4 | 8 | 16))
f = sets.frame(10961)
check("Красное Эхо: a skill among the bonuses -- Ближний бой at three, Стрельба at five (skill bits 0, 1)",
      ((f["bonus_3_skills_m"], f["bonus_3_skills"]), (f["bonus_5_skills_m"], f["bonus_5_skills"])),
      ((1, [1]), (2, [1])))
check("an unknown set: its own type, the empty name, no description",
      sets.frame(424242), dict(type=424242, res=0, name=quests.EMPTY_STRING_ID, desc=""))
check("and the empty name is one the client has", names.known(quests.EMPTY_STRING_ID), True)

# --- what the gear asks: the bonuses of what is worn -----------------------------
print()
print("bonuses")
kol2 = list(sets.SETS[11167]["members"].values())
check("all five of Колонист: the set's five-piece bonus",
      {k: v for k, v in sets.bonuses(kol2).items() if v and k in sets.SCALARS},
      {"hp": 5, "cp": 1, "ce": 1})
check("four of them: nothing, the set has no four-piece line",
      sets.bonuses(kol2[:4]), sets.zero())
nal8 = list(sets.SETS[11185]["members"].values())
f = sets.frame(11185)
b = sets.bonuses(nal8[:3] + [kol2[0], 4380])
check("three of Налетчик and strangers: K=2 and K=3 together, strangers ignored",
      (b["st"], b["ce"], b["od"], b["attribs"]),
      (f["bonus_2_st"] + f["bonus_3_st"], f["bonus_2_ce"], f["bonus_3_od"], [1, 0, 0, 0, 0]))
check("pieces counts per set", sets.pieces(nal8[:3] + kol2[:2] + [4380]),
      {11185: 3, 11167: 2})

# --- mending a gold piece --------------------------------------------------------
# A G piece has cost 0: every repair used to be refused on that, and a set
# bought for gold wore out for good -- and with it the set's bonus, which
# counts only whole pieces. It is mended in either currency, priced from its
# gold price changed at the repair rate (inventory.repair_base_price, the
# owner's rule of 2026-10-05, PR #41; the patched window prints the same):
# the 3 G vest broken is 3 * 50 000 * rmod 0.3 = 45 000 afro or 0.90 G. It
# comes back to nine tenths of the ceiling it had (inventory.REPAIR_KEEPS),
# and is restored as new for its gold price.
print()
print("repair")
import inventory  # noqa: E402
import progression  # noqa: E402

rstore = accounts.Store(os.path.join(tempfile.mkdtemp(), "repair.db"))
racc, _ = rstore.register("mender", "secret")
rcid, _ = rstore.create_character(racc, "Починщик", 0, 1)


class Mender:
    """The parts of server.Session that Inventory.repair touches."""
    char_id = rcid

    def __init__(self):
        self.char = progression.Character.load(rstore, rcid)
        self.char.afro, self.char.gold = 44999, 1000
        self.frames = []

    def character(self):
        return self.char

    def send(self, *cmd, **params):
        self.frames.append((cmd[0], params))

    def send_player_info(self):
        self.send("userInfo_Player", afro=self.char.afro, gold=self.char.gold)

    def say(self, text, group=0):
        self.send("userMsg", entry=text, **{"from": 0})


mender = Mender()
minv = inventory.Inventory(mender, rstore)
vest = by_name["armor_Set_M_LVL_8_G_mod00"]           # Бронежилет налетчика (G), 3 G
vsi = items.params_of(vest)
row = minv.create(vest)
rstore.update_item(row["uniq"], brk=0)
obj = inventory.oid_of(rstore.item(row["uniq"]))


def mend(code):
    mender.frames = []
    minv.repair({"obj": obj}, code)
    r = rstore.item(row["uniq"])
    return ([p["res"] for n, p in mender.frames if n == "cmdAck"], r["brk"], r["max_break_cur"],
            mender.char.afro, mender.char.gold)


top = vsi["max_break_abs"]
once, twice = top * 9 // 10, top * 9 // 10 * 9 // 10
check("a G piece broken, one afro short of its 45 000: refused 21, nothing moves",
      mend(inventory.UPD_REPAIR), ([inventory.RES_NO_MONEY], 0, top, 44999, 1000))
mender.char.afro = 50000
check("  ..with 50 000 afro: mended for 45 000, three tenths of 3 G at the rate, to nine"
      " tenths of its ceiling",
      mend(inventory.UPD_REPAIR), ([0], once, once, 5000, 1000))
rstore.update_item(row["uniq"], brk=0)
check("  ..broken again, for gold: 0.90 G, a tenth off the ceiling it had",
      mend(inventory.UPD_REPAIR_GOLD), ([0], twice, twice, 5000, 910))
check("  ..restored for its gold price, as new",
      mend(inventory.UPD_RESTORE), ([0], top, top, 5000, 910 - vsi["g_cost"]))
# The window offers "Восстановить" for anything with a g_cost, so this is a
# press a player can make: a 3 would put up "Сервер не отвечает"
# (ErrorReport); a press with nothing to do is answered 0 and charged
# nothing (Inventory.repair).
check("  ..and as new, a restore has nothing to buy back: 0, nothing paid",
      mend(inventory.UPD_RESTORE), ([0], top, top, 5000, 910 - vsi["g_cost"]))
rstore.close()

# --- a table that is wrong stops the server ------------------------------------
print()
print("the table itself")


def refused(doc):
    try:
        sets.parse(doc)
    except ValueError as e:
        return str(e)
    return None


def one_set(**change):
    s = {"name": "Проба[0][A]", "desc": "", "res": 0,
         "members": {"helm": {"type": 10059, "cost": 1}}}
    s.update(change)
    return {"sets": {"500": s}}


check("a minimal set parses", refused(one_set()), None)
for label, doc in (
        ("a bonus the client cannot show", one_set(bonus={"5": {"удача": 1}})),
        ("a bonus for seven pieces", one_set(bonus={"7": {"hp": 1}})),
        ("a fraction", one_set(bonus={"5": {"hp": 1.5}})),
        ("a belt as a member", one_set(members={"belt": {"type": 3577}})),
        ("a field no frame carries", one_set(members={"helm": {"type": 10059, "damage": 3}})),
        ("a requirement nobody has", one_set(members={"helm": {"type": 10059, "need": {"Удача": 1}}})),
        ("a piece's name that is no text", one_set(members={"helm": {"type": 10059, "name": 5}})),
        ("a piece's name that is only tags", one_set(members={"helm": {"type": 10059, "name": "[0][A]"}})),
        ("a piece's description that is no text", one_set(members={"helm": {"type": 10059, "desc": ["x"]}})),
        ("no members", one_set(members={})),
        ("no name", one_set(name="")),
        ("set_type zero", {"sets": {"0": one_set()["sets"]["500"]}}),
        ("set_type into the description ids", {"sets": {"100000": one_set()["sets"]["500"]}}),
        ("one type in two sets", {"sets": {"500": one_set()["sets"]["500"],
                                           "501": one_set()["sets"]["500"]}})):
    check("refused: " + label, refused(doc) is not None, True)
check("a need by name becomes the client's mask and list",
      sets.parse(one_set(members={"helm": {"type": 10059, "need": {"Телосложение": 6, "Стрельба": 2}}}))[2][10059],
      {"need_attribs_m": 4, "need_attribs": [6], "need_skills_m": 2, "need_skills": [2]})
parsed = sets.parse(one_set(members={"helm": {"type": 10059, "name": "Проба [0][G]$ICO1",
                                              "desc": 'Проба \\"в кавычках\\"'}}))[0][500]
check("a piece's name is cleaned like the original's: the (G) before the $, no stray space",
      (parsed["names"], parsed["descs"]),
      ({10059: "Проба (G)$ICO1"}, {10059: 'Проба "в кавычках"'}))
check("  ..and a piece the file does not name keeps the original's",
      sets.parse(one_set())[0][500]["names"], {})

# --- the handler when frame() fails: still one answer, still the same type -----
print()
print("the handler")
import server  # noqa: E402  (after LAVA_DB: it opens a Store at import)


class Sent:
    def __init__(self):
        self.frames = []

    def send(self, *cmd, **params):
        self.frames.append((cmd[0], params))


def boom(_type):
    raise RuntimeError("a bug in sets.frame")


real, sets.frame = sets.frame, boom
logging.getLogger("lava").disabled = True
try:
    s = Sent()
    server.Session.cmd_ss_get_s_si(s, {"type": 11185})
finally:
    sets.frame = real
    logging.getLogger("lava").disabled = False
check("a failing frame still sends one ss_si_set for the type asked about",
      s.frames, [("ss_si_set", sets.fallback(11185))])
server.STORE.close()

# --- over the socket -------------------------------------------------------------
print()
print("the window")


def free_port():
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


PORT = free_port()
accounts.DB_PATH = DB
_store = accounts.Store(DB)
_store.register("tester", "secret")
_store.close()
CRED = accounts.credential("tester", "secret")
env = dict(os.environ, LAVA_PORT=str(PORT), LAVA_HOST="127.0.0.1", LAVA_DB=DB,
           LAVA_POLICY_PORT="0")
srv = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()


def connect(timeout=None):
    return testkit.connect(PORT, srv, _log, timeout)


class Client:
    def __init__(self, sock):
        self.s = sock
        self.buf = b""

    def send(self, text):
        self.s.sendall(text.encode(ENC) + b"\x00")

    def frames(self, wait=0.5):
        deadline = time.time() + wait
        while True:
            left = deadline - time.time()
            if left <= 0:
                break
            self.s.settimeout(left)
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        out, self.buf = self.buf.split(b"\x00"), b""
        return [decode(f.decode(ENC)) for f in out if f]

    def until(self, name, count=1, timeout=15):
        got = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            got += self.frames(0.3)
            if sum(1 for n, _p in got if n == name) >= count:
                return got + self.frames(0.5)
        return got


try:
    c = Client(connect())
    c.send("hello;minor=2;major=0;")
    c.send("login;hash=@%s@;" % CRED)
    c.frames()
    c.send("newPers;res=1;sex=0;name=@setstester@;")
    c.frames()
    c.send("actPlayer;")
    c.frames()
    c.send("lenter;accept=1;")
    c.until("lenter")

    c.send("ss_get_s_si;type=11185;")
    got = c.until("ss_si_set")
    check("a known set: one ss_si_set and nothing else", [n for n, _p in got], ["ss_si_set"])
    p = got[0][1]
    check("  ..its type, name and description", (p["type"], p["name"], p["desc"]),
          (11185, sets.NAME_ID_OFFSET + 11185, sets.DESC_ID_OFFSET + 11185))

    c.send("ss_get_s_si;type=424242;")
    got = c.until("ss_si_set")
    check("an unknown type: one ss_si_set, no cmdAck", [n for n, _p in got], ["ss_si_set"])
    check("  ..carrying the type asked about and the empty name",
          (got[0][1]["type"], got[0][1]["name"], got[0][1]["desc"]),
          (424242, quests.EMPTY_STRING_ID, ""))

    c.send("ss_get_s_si;type=@x@;")
    got = c.until("ss_si_set")
    check("a type that is no number: still one ss_si_set, no cmdAck",
          [n for n, _p in got], ["ss_si_set"])

    wanted = [11218, 11221, 11167, 11169, 11191, 424243, 11187]
    for st in wanted:
        c.send("ss_get_s_si;type=%d;" % st)
    got = c.until("ss_si_set", count=len(wanted))
    check("seven at once, more than the window holds: seven answers, in order, no cmdAck",
          [(n, q.get("type")) for n, q in got], [("ss_si_set", st) for st in wanted])

    c.send("ss_get_si;type=%d;" % LOXLEY[-3])
    got = c.until("ss_si_wear")
    si = got[0][1] if got and got[0][0] == "ss_si_wear" else {}
    check("a piece on the wire: its slot, its set, its name",
          (si.get("slot_type"), si.get("set_type"), names.text(si.get("name", 0))),
          (2, 11187, "Бронежилет налетчика (G)"))
    c.send("logout;")
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    srv.terminate()
    srv.wait(timeout=5)
    _drain.join(timeout=2)
    out = "".join(_log)
    if "Traceback" in out:
        fails.append("server logged a traceback:\n" + out[-2500:])
    if fails and os.environ.get("LAVA_TEST_LOG"):
        print(out[-6000:])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("sets OK")
