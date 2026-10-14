"""Build data/sets.json from the owner's wardrobe layout, and Локсли's list.

    LAVA_RES=.../lava/res python3 data/build_sets.py LAYOUT.json [--npcs]

The owner laid his sets out on a page, the wardrobe: for each set a name, the
rung of the ladder it stands on (its level), the five pieces he chose by their
icons -- the A piece of a series, or the quest (Q) piece where a family has
nothing else -- and, optionally, the figure a full set draws its wearer as.
Its data is one JSON file:

    {"sets": [{"name", "level", "slots": {helm, shirt, armor, pants, boots:
               type id}, "res"?: "113" | "0"}]}

This turns that page into the file server/sets.py reads, by the rules below,
which the file's own _meta repeats for whoever edits it by hand. It is
re-runnable on purpose: the owner may move a piece, rename a set or pick
another figure, and the same page must give the same file. Which sets a
trader sells is no longer this file's: since the owner's «по уровню городов»
(2026-10-10) every set seller -- Локсли among them -- sells the A and G sets
of his city's band (data/shop_bands.json, server/shop_bands.py), so a moved
rung is on the right stalls by itself. --npcs takes the ladder's pieces off
Локсли's own list in data/npcs.json (stock "5213"), should an older run have
put them there; the rest of it (the silk) stays. Without it the valley's
rungs are only printed.

WHICH ROWS BECOME SETS

A row with all five slots filled and a real name (three letters or more) is
a set; any other row is skipped and named in the output, never guessed at --
the page keeps the owner's half-finished rows ("Се") as well as his sets. So
is a set whose name SOURCES has no words for: its pieces' names, wiki pages
and descriptions are a decision, and the output says what to add.

WHAT COMES FROM WHERE

  pieces   the layout's A piece; the G variant is the G of that piece's own
           series and level, the same icon in gold (helm_Set_M_LVL_11_A_mod00
           -> helm_Set_M_LVL_11_G_mod00). A quest piece has no G: a set made
           of quest pieces is its one variant, Q -- unless its series has a
           G of our own for every piece (data/own_items.json): then it is
           sold, the quest pieces its A and ours its G (Чёрный Ловелас,
           2026-10-13; Тёмное Эхо, 2026-10-14); a quest piece among A ones
           (Красное Эхо's boots) is matched in the G variant by the G of the
           series the rest of the set is. No P anywhere: the owner took
           premium out of the game (items.premium).
  set_type the texts.xml row of the name of the set these very types formed
           in the original (SET_ROWS, the block 10938-11289): stable, unique,
           and a trail back to the original. The owner's names are his own
           ("Странник" on the types the original called Колонист[11]).
  figure   the layout's res, else the one suggested to the owner (SUGGESTED),
           the same on every variant; "0" leaves the wearer's own body.
  numbers  the wiki's (data/wiki_items.json, parsed from data/wiki/pages.json):
           each piece's page, column by column -- the A column for A, the G
           column for G; a lone column is the variant its price says and the
           other variant copies its numbers with the price converted at the
           wiki's own 4000 afro = 1 G; a quest piece takes its page's first
           column, priced in afro as the wiki prices the quest sets. Стрельба
           asked is the set's level; every other requirement is the page's.
           Where the wiki has no numbers the set is DESIGNED between the
           nearest rungs that have them (interpolate(); the rule is written
           out in the file's _meta), and says so.
  bonuses  the wiki's set page, the variant's column (a lone column serves
           both); where the page's table is not one wiki_items.json parses,
           transcribed from its wikitext (TRANSCRIBED); none where the page
           says none; designed like the numbers where there is no page, and
           for Чёрный Ловелас, whose page gives Штурм-М[15]'s column to a set
           sold at 12. A designed G lies between the neighbours' G pieces and
           G columns where both have a G.
  words    each set's piece names and descriptions (SOURCES): the wiki's or
           the original's, never a line about a dead former owner.

A number the wiki gives but the file cannot carry -- a piece's own attribute
bonus, which sets.ITEM_FIELDS has no field for -- is kept under the piece's
_bonus_attribs, where the server does not read it, for the day it can.
"""
import argparse
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import items  # noqa: E402  (reads LAVA_RES for the client's catalogue)
import orig_texts  # noqa: E402
import own_items  # noqa: E402
import sets  # noqa: E402

OUT = os.path.join(HERE, "sets.json")
NPCS = os.path.join(HERE, "npcs.json")
WIKI_ITEMS = os.path.join(HERE, "wiki_items.json")
PAGES = os.path.join(HERE, "wiki", "pages.json")

LOXLEY = 5213          # Локсли, "Одежда и Броня": the valley's band (shop_bands.py)
AFRO_PER_G = 4000      # every wiki set page's rate: Вещи Колонистов 4000 afro / 1 G
SLOTS = sets.SLOTS     # helm, shirt, armor, pants, boots
MIN_NAME = 3

# The client's clothing series: <slot>_<family>_<M|U>_LVL_<level>_<variant>_modNN.
SERIES = re.compile(r"^(helm|shirt|armor|pants|boots)_((?:Bs|Set|Exzo)_[MU])_LVL_(\d+)_([APGQ])_mod00$")

# (family, level) -> {variant: texts.xml row of that set's name}, from the set
# block of the original texts.xml (10938-11289); P rows left out. Колонист is
# Set_M, Беженец Bs_M; Exzo_M is Легионер 0-6, Красное ЭXO 7-10, Темное ЭXO
# 11-14, Штурм-М 15-16, Дредноут 17-18, Паладин 19, Апокалипсис 20; the quest
# family Bs_U has only [Q] rows. A quest set that is sold (pieces_of: its
# series has a G of our own, data/own_items.json) keeps its [Q] row for the
# A, the row its types answered to; its G no row of the original names, and
# it is keyed by its first piece, our type (Чёрный Ловелас[12]: 60000;
# Тёмное Эхо[17]: 60005, since Абу-Хамед, 2026-10-14).
SET_ROWS = {
    ("Bs_M", 0): {"A": 11218, "G": 11221}, ("Bs_M", 2): {"A": 11222, "G": 11224},
    ("Bs_M", 3): {"A": 11225, "G": 11227}, ("Bs_M", 4): {"A": 11228, "G": 11230},
    ("Bs_M", 5): {"A": 11231, "G": 11233}, ("Bs_M", 6): {"A": 11234, "G": 11236},
    ("Bs_M", 7): {"A": 11237, "G": 11239}, ("Bs_M", 8): {"A": 11240, "G": 11242},
    ("Bs_M", 10): {"A": 11243, "G": 11245}, ("Bs_M", 11): {"A": 11246, "G": 11248},
    ("Bs_M", 12): {"A": 11249, "G": 11251}, ("Bs_M", 14): {"A": 11252, "G": 11254},
    ("Bs_M", 15): {"A": 11255, "G": 11257}, ("Bs_M", 16): {"A": 11258, "G": 11260},
    ("Bs_M", 17): {"A": 11261, "G": 11263}, ("Bs_M", 18): {"A": 11264, "G": 11266},
    ("Bs_M", 19): {"A": 11267, "G": 11269}, ("Bs_M", 20): {"A": 11270, "G": 11272},
    ("Set_M", 0): {"A": 11163, "G": 11166}, ("Set_M", 2): {"A": 11167, "G": 11169},
    ("Set_M", 3): {"A": 11170, "G": 11172}, ("Set_M", 4): {"A": 11173, "G": 11175},
    ("Set_M", 5): {"A": 11176, "G": 11178}, ("Set_M", 6): {"A": 11179, "G": 11181},
    ("Set_M", 7): {"A": 11182, "G": 11184}, ("Set_M", 8): {"A": 11185, "G": 11187},
    ("Set_M", 10): {"A": 11188, "G": 11190}, ("Set_M", 11): {"A": 11191, "G": 11193},
    ("Set_M", 12): {"A": 11194, "G": 11196}, ("Set_M", 14): {"A": 11197, "G": 11199},
    ("Set_M", 15): {"A": 11200, "G": 11202}, ("Set_M", 16): {"A": 11203, "G": 11205},
    ("Set_M", 17): {"A": 11206, "G": 11208}, ("Set_M", 18): {"A": 11209, "G": 11211},
    ("Set_M", 19): {"A": 11212, "G": 11214}, ("Set_M", 20): {"A": 11215, "G": 11217},
    ("Exzo_M", 0): {"A": 10938, "G": 10941}, ("Exzo_M", 2): {"A": 10942, "G": 10944},
    ("Exzo_M", 3): {"A": 10945, "G": 10947}, ("Exzo_M", 4): {"A": 10948, "G": 10950},
    ("Exzo_M", 5): {"A": 10951, "G": 10953}, ("Exzo_M", 6): {"A": 10954, "G": 10956},
    ("Exzo_M", 7): {"A": 10957, "G": 10960}, ("Exzo_M", 8): {"A": 10961, "G": 10965},
    ("Exzo_M", 10): {"A": 10966, "G": 10968}, ("Exzo_M", 11): {"A": 10971, "G": 10974},
    ("Exzo_M", 12): {"A": 10975, "G": 10977}, ("Exzo_M", 14): {"A": 10979, "G": 10981},
    ("Exzo_M", 15): {"A": 10987, "G": 10990}, ("Exzo_M", 16): {"A": 11002, "G": 11004},
    ("Exzo_M", 17): {"A": 11010, "G": 11013}, ("Exzo_M", 18): {"A": 11016, "G": 11018},
    ("Exzo_M", 19): {"A": 11030, "G": 11033}, ("Exzo_M", 20): {"A": 11043, "G": 11046},
    ("Bs_U", 10): {"Q": 11116}, ("Bs_U", 11): {"Q": 11118},
    ("Bs_U", 12): {"Q": 11120, "A": 11120, "G": 60000},
    ("Bs_U", 14): {"Q": 11122}, ("Bs_U", 15): {"Q": 11123},
    ("Bs_U", 16): {"Q": 11125, "A": 11125, "G": 60005},
    ("Bs_U", 17): {"Q": 11126}, ("Bs_U", 18): {"Q": 11127}, ("Bs_U", 19): {"Q": 11128},
    ("Bs_U", 20): {"Q": 11129},
}

# The quest series sold for afro and for gold (a G of our own for every
# piece, data/own_items.json), each with the words of the decision that sold
# it, which its sets' _designed repeat. Тёмное Эхо[17], the ladder's 17th
# rung, was a quest set no stall sold; the plan gave it to its stage 6 (the
# [Q] reward of «Странные осадки», 1132) and called the rung's want of a set
# a known hole. Абу-Хамед's band 16-20 sells it now, as Чёрный Ловелас (the
# owner's decision 32 of Абу-Хамед's plan, against that line of the plan):
# its pieces stay the same types, so 1132 may still hand them out.
SOLD_SINCE = {
    ("Bs_U", 12): "the owner's 'за афро и за голд' (2026-10-13)",
    ("Bs_U", 16): "Абу-Хамед, the owner's 'сделай потом абу хамед в таком же формате' "
                  "(2026-10-14): the 17th rung had no set on sale",
}

# The figure offered to the owner for each set (res/personages/<res>), taken
# where his page gives none.
SUGGESTED = {"Беженец": 113, "Колонист": 118, "Странник": 86, "Налетчик": 107,
             "Пустынник": 103, "Чёрный Ловелас": 111, "Спецназ": 79, "Легионер": 1401,
             "Штурм-М": 80, "Красное Эхо": 1601, "Тёмное Эхо": 119, "Дредноут": 77,
             "Паладин": 76, "Апокалипсис": 84, "Магриб": 101}
# Folders of res/personages that are no person in clothes: the tutorial
# dummy and the animals. (armor, default, 119_, 132_ are no number at all.)
NOT_A_FIGURE = {1502, 96, 97, 98, 99, 125, 127, 143, 144, 1444}

WIKI = "wiki"          # a description: the wiki page's own


def lit(source, text):
    """A description taken from elsewhere than the piece's wiki page."""
    return (source, text)


# Each set's words by the owner's name: its wiki set page (bonuses, and its
# description where `desc` is WIKI), and per slot the piece's name, the wiki
# page its numbers come from (None: designed) and its description.
#
#   bonus  "table"  the set page's table as wiki_items.json has it
#          "text"   TRANSCRIBED from the page's wikitext
#          "none"   the page says there is none
#          "design" no page: interpolated like the numbers
SOURCES = {
    "Беженец": dict(
        page="Вещи Беженца", bonus="none",
        desc=lit("texts.xml 11219", "Добротная одежда беженца. Еще не успела истрепаться."),
        pieces=dict(
            helm=("Панама", "Панама", lit(
                "texts.xml 22946, its Latin e made Cyrillic and its <br/> a space (the wiki's "
                "copy writes 'Не плохо')",
                "Легкая шляпа с упругими полями, выполненная в стиле милитари. "
                "Неплохо защищает от солнца.")),
            shirt=("Пончо", "Пончо", WIKI),
            # The original's own capital Б (texts.xml 22945-22952); the page is lower case.
            armor=("Самодельная Броня", "Самодельная броня", WIKI),
            pants=("Шорты", "Шорты", WIKI),
            boots=("Самодельные тапки", "Самодельные тапки", WIKI))),
    "Колонист": dict(
        page="Вещи Колонистов", bonus="table",
        desc=lit("texts.xml 11164", "Добротная одежда колониста. Еще не успела истрепаться."),
        pieces=dict(
            # The wiki's set has a builder's helmet; the icon is goggles. Its
            # numbers, the original's words for the goggles.
            helm=("Гоглы с фильтром", "Каска строителя", lit(
                "texts.xml 16576", "Очки-консервы интегрированные с противопыльным респиратором.")),
            shirt=("Рубашка", "Рубашка", WIKI),
            armor=("Кусковая броня", "Кусковая броня", WIKI),
            pants=("Джинсы", "Джинсы", lit(
                "texts.xml 16747, the wiki's very sentence as the original spells it (the "
                "wiki's hand copy splits 'про клепанными')",
                "Брюки из плотной хлопчатобумажной ткани, с проклёпанными стыками швов на "
                "карманах. Старые и грязные, но всё еще прочные.")),
            boots=("Старые ботинки", "Старые ботинки", WIKI))),
    # Set_M_LVL_11: a cloth wrap on the icon, the wiki's Шапка странника to
    # the letter ("a thick head wrap") -- not the cowboy hat of Set_M_LVL_6.
    "Странник": dict(
        page="Сет Странник", bonus="table", desc=WIKI,
        pieces=dict(
            helm=("Шапка странника", "Шапка странника", WIKI),
            shirt=("Плащ странника", "Плащ странника", WIKI),
            armor=("Броня странника", "Броня странника", WIKI),
            pants=("Штаны странника", "Штаны странника", WIKI),
            boots=("Ботинки странника", "Ботинки странника", WIKI))),
    # The owner's name for Bs_M_LVL_16 (Беженец[16] in the original): a steel
    # helmet, a field shirt, a plate vest, army trousers and boots on the
    # icons -- the wiki's Армейские вещи, "used everywhere, the military of
    # Магриб among them", whose pieces ask Стрельба 6, the rung he put it on.
    "Магриб": dict(
        page="Армейские вещи", bonus="table", desc=WIKI,
        pieces=dict(
            helm=("Армейский шлем", "Армейский шлем", WIKI),
            shirt=("Армейская рубашка", "Армейская рубашка", WIKI),
            armor=("Общевойсковой бронежилет", "Общевойсковой бронежилет", WIKI),
            pants=("Армейские штаны", "Армейские штаны", lit(
                "texts.xml 23243, the trousers' own line (the wiki's page repeats the shirt's)",
                "Классическая армейская одежда. Военные стали частью нового стиля "
                "постапокалиптической моды - прочный материал, различные расцветки ткани, "
                "дешево и сердито.")),
            boots=("Армейские ботинки", "Армейские ботинки", WIKI))),
    "Налетчик": dict(
        page="Налетчик", bonus="table", desc=WIKI,
        pieces=dict(
            helm=("Очки налетчика", "Очки налетчика", WIKI),
            shirt=("Куртка налетчика", "Куртка налетчика", WIKI),
            armor=("Бронежилет налетчика", "Бронежилет налетчика", WIKI),
            pants=("Кожаные штаны налетчика", "Кожаные штаны налетчика", WIKI),
            boots=("Ботинки налетчика", "Ботинки налетчика", WIKI))),
    "Пустынник": dict(
        page="Пустынник", bonus="table", desc=WIKI,
        pieces=dict(
            helm=("Шлем пустынника", "Шлем пустынника", WIKI),
            shirt=("Накидка пустынника", "Накидка пустынника", WIKI),
            armor=("Броня пустынника", "Броня пустынника", WIKI),
            pants=("Штаны пустынника", "Штаны пустынника", WIKI),
            boots=("Сапоги пустынника", "Сапоги пустынника", WIKI))),
    # No piece pages on the wiki: numbers designed. Words the original's
    # (texts.xml 15108-15117), the set's name row 11120 its own. The set
    # page's bonuses (TRANSCRIBED) are Штурм-М[15]'s A column word for word,
    # an event set's that was never sold -- its Цена комплекта is blank, its
    # pieces ask Стрельба 7. Sold on the ladder at 12 since 2026-10-13, with
    # its pieces designed between Пустынник and Спецназ, it gets its bonuses
    # the same way (designed_bonuses), so that its power is its rung's.
    "Чёрный Ловелас": dict(
        page="Снаряжение Чёрного Ловеласа", bonus="design",
        bonus_why="the wiki's Снаряжение Чёрного Ловеласа gives Штурм-М[15]'s A column word for "
                  "word (an event set, never sold: its Цена комплекта is blank); sold at 12 since "
                  "2026-10-13, the set takes its rung's power instead",
        desc=lit("texts.xml 11121",
                 "Комплекс снаряжения легендарной антитеррористической группы «ЛОВЕЛАС»."),
        pieces=dict(
            helm=("Шлем Чёрного Ловеласа", None, lit(
                "texts.xml 15109", "Встроен рентген сканер обнажающий натуру противника. Без смсок!")),
            shirt=("Жилет Чёрного Ловеласа", None, lit(
                "texts.xml 15111", "Плотный и облегающий жилет - лучше для мужчины нет.")),
            armor=("Броня Чёрного Ловеласа", None, lit(
                "texts.xml 15113", "Лучшая защита на свете от нежелательной Бременской Музыкантки.")),
            pants=("Штанишки Чёрного Ловеласа", None, lit(
                "texts.xml 15115", "Немного жмут в паховой области, тем самым подчеркивая "
                "достоинства… Если таковые имеются. Придётся потерпеть.")),
            boots=("Ботинки Чёрного Ловеласа", None, lit(
                "texts.xml 15117", "Они просто клёвые, для настоящих метросексуалов.")))),
    "Спецназ": dict(
        page="Спецназ", bonus="table", desc=WIKI,
        pieces=dict(
            helm=("Шлем спецназа", "Шлем спецназа", WIKI),
            shirt=("Куртка спецназа", "Куртка спецназа", WIKI),
            armor=("Броня спецназа", "Броня спецназа", WIKI),
            pants=("Штаны спецназа", "Штаны спецназа", WIKI),
            boots=("Ботинки спецназа", "Ботинки спецназа", WIKI))),
    "Легионер": dict(
        page="Легионер", bonus="table", desc=lit(
            "texts.xml 10939",
            "Тяжесть и мощь. Доблесть и честь. Пришел, увидел, схватил... а вот убежать в нем "
            "будет сложно, хотя за медведем гонятся себе дороже."),
        pieces=dict(
            helm=("Шлем легионера", "Шлем легионера", WIKI),
            shirt=("Плащ легионера", "Плащ легионера", WIKI),
            armor=("Броня легионера", "Броня легионера", WIKI),
            pants=("Штаны легионера", "Штаны легионера", WIKI),
            boots=("Ботинки легионера", "Ботинки легионера", WIKI))),
    "Штурм-М": dict(
        page="Штурм-М", bonus="table", desc=lit(
            "texts.xml 10988",
            "Современные наработки в области Экзоскелета, только успевшие поступить в "
            "гвардейские части для тестирования."),
        pieces=dict(
            helm=("Шлем Штурм-М", "Шлем Штурм-М", lit(
                "wiki Шлем Штурм-М, its doubled first letter ('ИИногда') dropped",
                "Иногда кажется, что этот шлем самостоятельнее его обладателя.")),
            shirt=("Жилет Штурм-М", "Жилет Штурм-М", WIKI),
            armor=("Броня Штурм-М", "Броня Штурм-М", WIKI),
            pants=("Моторика Штурм-М", "Моторика Штурм-М", WIKI),
            boots=("Боты Штурм-М", "Боты Штурм-М", WIKI))),
    # The wiki's names: the original writes "Красное ЭXO" with a Latin X and O.
    "Красное Эхо": dict(
        page="Красное Эхо", bonus="table", desc=lit(
            "texts.xml 10958",
            "Экзоскелет — устройство, предназначенное для увеличения силы человека за счёт "
            "внешнего каркаса. Он повторяет биомеханику человека и пропорционально "
            "увеличивает усилия при движениях. Первые образцы были разработаны в 60-х годах."),
        pieces=dict(
            # The wiki's helmet line ends "хозяин труп и в шлеме дырка".
            helm=("Шлем Красного Эхо", "Шлем Красного Эхо", lit(
                "texts.xml 12336 (the wiki's line is about the dead man who wore it)",
                "Вес шлема должен лежать на экзоскелете так что владельцу не о чем беспокоится, "
                "если конечно у него он есть. Встроен кондиционер, тактический анализатор, "
                "детектор движения и ПНВ.")),
            shirt=("Поддоспешник Красного Эхо", "Поддоспешник Красного Эхо", WIKI),
            armor=("Корпус Красного Эхо", "Корпус Красного Эхо", WIKI),
            pants=("Моторика Красного Эхо", "Моторика Красного Эхо", WIKI),
            # The wiki's boots page repeats the undersuit's line word for word.
            boots=("Боты Красного Эхо", "Боты Красного Эхо", lit(
                "texts.xml 12344 (the wiki's page repeats the undersuit's line)",
                "Механизированные боты являются частью опорно-двигательного аппарата.")))),
    # ё as the owner writes the set; the wiki writes Темного.
    "Тёмное Эхо": dict(
        page="Темное Эхо", bonus="text", desc=lit(
            "texts.xml 10972",
            "Модификация известного сета, переработанного учеными МКС с использованием "
            "редкоземельных элементов."),
        pieces=dict(
            helm=("Шлем Тёмного Эха", "Шлем Темного Эха", WIKI),
            shirt=("Жилет Тёмного Эха", "Жилет Темного Эха", WIKI),
            armor=("Броня Тёмного Эха", "Броня Темного Эха", WIKI),
            pants=("Моторика Тёмного Эха", "Моторика Темного Эха", WIKI),
            boots=("Ступни Тёмного Эха", "Ступни Темного Эха", WIKI))),
    # No page at all: numbers and bonuses designed. The original's piece
    # names (texts.xml 14175-14179) and its level-17 descriptions (13966-13974).
    "Дредноут": dict(
        page=None, bonus="design",
        desc=lit("texts.xml 11011", "Новый комплект брони для выполнения самых сложных боевых операций."),
        pieces=dict(
            helm=("Шлем Дредноута", None, lit(
                "texts.xml 13966", "Уникальная многокомпонентная защитная структура бронешлема "
                "практически полностью поглощает ударный импульс пули.")),
            shirt=("Жилет Дредноута", None, lit(
                "texts.xml 13968", "Система гашения ударного импульса в этом бронекомбинезоне "
                "основана на технологии жидкой брони – при ударе формирующей твердые кластеры.")),
            armor=("Броня Дредноута", None, lit(
                "texts.xml 13970", "Корпус из углепластика покрыт титано-керамикой. Внутри, под "
                "многослойным кевларом, находятся полости для специальной останавливающей "
                "жидкости с наночастицами. Самая высокотехнологичная защита тела из всех возможных!")),
            pants=("Моторика Дредноута", None, lit(
                "texts.xml 13972", "Композитные материалы, армированная ткань, тонкий слой жидкой "
                "брони в сочетании с надёжной системой охлаждения обеспечивают лучшую защиту "
                "нижних конечностей от пуль и осколков, а также спасают от перегрева в условиях "
                "пустыни.")),
            boots=("Ступни Дредноута", None, lit(
                "texts.xml 13974", "Композитный материал с высочайшей степенью бронирования - "
                "кевлар-арамид, дополнительно армированный титановыми нитями, остановит "
                "большинство известных калибров стрелкового оружия.")))),
    # No pages of its own (see Апокалипсис for the page named after it).
    # The original has lines for two of its pieces; the other three borrow
    # Дредноут's, the armour Паладин improves on (texts.xml 11031).
    "Паладин": dict(
        page=None, bonus="design",
        desc=lit("texts.xml 11031",
                 "Паладин - попытка дальнейшего улучшения тактической брони Дредноут. Благодаря "
                 "нанесению оксида титана броня приобрела желто-золотой оттенок, что является "
                 "дополнительной маскировкой в условиях пустыни."),
        pieces=dict(
            helm=("Шлем Паладина", None, lit(
                "texts.xml 13966, Шлем Дредноута's (the original has none for this helmet)",
                "Уникальная многокомпонентная защитная структура бронешлема практически полностью "
                "поглощает ударный импульс пули.")),
            shirt=("Жилет Паладина", None, lit("texts.xml 14377", "Внутренний жилет армирован кевларом.")),
            armor=("Броня Паладина", None, lit(
                "texts.xml 13970, Броня Дредноута's (the original has none for this armour)",
                "Корпус из углепластика покрыт титано-керамикой. Внутри, под многослойным кевларом, "
                "находятся полости для специальной останавливающей жидкости с наночастицами. Самая "
                "высокотехнологичная защита тела из всех возможных!")),
            pants=("Моторика Паладина", None, lit(
                "texts.xml 14380", "Современная электроника в сочетании с кинетическими "
                "стабилизаторами обеспечивают наилучшую устойчивость при стрельбе.")),
            boots=("Боты Паладина", None, lit(
                "texts.xml 13974, Ступни Дредноута's (the original has none for these boots)",
                "Композитный материал с высочайшей степенью бронирования - кевлар-арамид, "
                "дополнительно армированный титановыми нитями, остановит большинство известных "
                "калибров стрелкового оружия.")))),
    # The wiki's "Модификация паладин" carries Паладин's title and blurb, but
    # its set is these five pieces -- it lists them, and its 300 G is their
    # prices' sum (75 + 45 + 90 + 60 + 30) -- and Апокалипсис "combines the
    # advantages of the Paladin's modifications" (texts.xml 11044). Its table
    # is theirs.
    "Апокалипсис": dict(
        page="Модификация паладин", bonus="table",
        desc=lit("texts.xml 11044", "Апокалипсис сочетает в себе все преимущества различных "
                                    "модификаций Паладина."),
        pieces=dict(
            helm=("Шлем Апокалипсиса", "Шлем Апокалипсиса", WIKI),
            shirt=("Жилет Апокалипсиса", "Жилет Апокалипсиса", WIKI),
            armor=("Броня Апокалипсиса", "Броня Апокалипсиса", lit(
                "texts.xml 14583 (the wiki's page says 'Эти Боты')",
                "Эта Броня сочетает в себе все преимущества различных модификаций Паладина.")),
            pants=("Моторика Апокалипсиса", "Моторика Апокалипсиса", WIKI),
            boots=("Боты Апокалипсиса", "Боты Апокалипсиса", WIKI))),
}

# Set pages whose table wiki_items.json does not parse, transcribed from
# their wikitext in data/wiki/pages.json: K pieces -> {bonus: value}. Both
# are one column. Снаряжение Чёрного Ловеласа's serves no set since its set
# is sold (SOURCES: designed); it stays here, the page's word, should the
# owner want it back with a price to match.
TRANSCRIBED = {
    "Снаряжение Чёрного Ловеласа": {
        2: {"hp": 50, "st": 20},
        3: {"st": 55, "od": 20, "Ловкость": 1},
        4: {"hp": 60, "st": 100, "ce": 17, "Интеллект": 1},
        5: {"st": 200, "cp": 17, "Сила": 2, "Телосложение": 3, "Восприятие": 2}},
    "Темное Эхо": {
        2: {"st": 38, "ce": 6},
        3: {"st": 100, "Сила": 1, "Ловкость": 1},
        4: {"st": 150, "ce": 10, "Сила": 3, "Интеллект": 2},
        5: {"st": 250, "cp": 16, "Ловкость": 3, "Телосложение": 4, "Восприятие": 4}},
}

# Prices a piece page gives that its own set page and its other column refute,
# (page, variant) -> (price, why). The set page's total and the rate every
# other piece keeps (afro / 4000 = G) agree with each other and not with the
# page.
PRICE_FIXES = {
    ("Очки налетчика", "G"): (250, "the page's 1.25 G; the set page's 10 G and 10000 afro / 4000 "
                                   "say 2.5 G"),
    ("Ботинки легионера", "G"): (750, "the page's 5 G; the set page's 75 G and 30000 afro / 4000 "
                                      "say 7.5 G"),
    ("Броня Штурм-М", "A"): (210000, "the page's 2 100 000 afro, a zero too many; its 52.5 G x 4000 "
                                     "and the set page's 700 000 afro say 210 000"),
    ("Моторика Штурм-М", "A"): (140000, "the page's 120 000 afro; its 35 G x 4000 and the set "
                                        "page's 700 000 afro say 140 000"),
}

# A piece page's numbers -> the frame's fields.
STATS = (("Уровень брони", "armor_class"), ("Износ", "max_break_abs"), ("Вес", "weight"),
         ("Здоровье", "bonus_hp"), ("Выносливость", "bonus_st"), ("Очки действия", "bonus_od"),
         ("Крит. попадание", "bonus_cp"), ("Избег. крит. попадание", "bonus_ce"),
         ("Избег. крит. попадания", "bonus_ce"))
NUMBER_FIELDS = ("armor_class", "max_break_abs", "weight", "bonus_hp", "bonus_st", "bonus_od",
                 "bonus_cp", "bonus_ce")
# A set page's rows -> the file's bonus names (sets.SCALARS, or the client's
# tooltip name of an attribute, skill or specialisation).
BONUS_NAMES = {"Здоровье": "hp", "Выносливость": "st", "Очки действия": "od",
               "Крит. попадание": "cp", "Избег. крит. попадание": "ce",
               "Избег. крит. попадания": "ce", "Интелект": "Интеллект"}


def half_up(x):
    return int(math.floor(x + 0.5 + 1e-9))


def to_thousand(afro):
    """A designed afro price: whole thousands, so its G at 4000 : 1 is a whole
    number of hundredths (1000 afro = 25)."""
    return half_up(afro / 1000.0) * 1000


# --- the wiki ---------------------------------------------------------------

def load_json(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


WIKI_DATA = load_json(WIKI_ITEMS)


def price_of(cell):
    """('afro', n) or ('g', x) out of a Базовая цена / Цена комплекта cell."""
    if isinstance(cell, dict):
        if "afro" in cell:
            return "afro", cell["afro"]
        if "g" in cell:
            return "g", cell["g"]
    if isinstance(cell, str):
        # Тёмное Эхо's pages write it out: "200 000 Афро".
        digits = re.sub(r"[^\d.,]", "", cell).replace(",", ".")
        if digits and "афро" in cell.lower():
            return "afro", int(float(digits))
        if digits and re.search(r"\bG\b", cell):
            return "g", float(digits)
    raise ValueError("no price in %r" % (cell,))


def piece_table(page):
    rec = WIKI_DATA.get(page)
    if not rec or not rec["tables"]:
        raise SystemExit("wiki page %r has no table of numbers" % page)
    table = rec["tables"][0]
    return table, table["sections"]["общие"]


def columns(page):
    """variant -> column of a piece page, and the variant a lone column is.

    A/P/G pages give A its column and G its own. A page of one column, or of
    several of one tier (Тёмное Эхо's three, by the attribute each favours),
    is read at its first column, which is the variant its price is in.
    """
    table, sec = piece_table(page)
    if table["tiers"] == ["A", "P", "G"]:
        return {"A": 0, "G": 2}, None, ""
    cur, _v = price_of(sec["Базовая цена"][0])
    lone = "A" if cur == "afro" else "G"
    if len(table["columns"]) > 1:
        return {lone: 0}, lone, " (the first of its %d columns, %s)" % (
            len(table["columns"]), table["columns"][0])
    return {lone: 0}, lone, " (its one column, %s)" % lone


def dicts(cell):
    """{name: value} out of a requirement or bonus cell: a dict, a list of
    them, a list of lists; strings ("Ловкость нет") say nothing."""
    out = {}
    if isinstance(cell, dict):
        for k, v in cell.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = int(v)
    elif isinstance(cell, list):
        for x in cell:
            out.update(dicts(x))
    return out


def page_numbers(page, i):
    """A piece page's column i: (fields, need, price, piece's own attributes)."""
    _table, sec = piece_table(page)
    fields = {}
    for wkey, key in STATS:
        if wkey in sec:
            v = sec[wkey][i]
            if v is not None:
                fields[key] = int(v)
    need = {}
    for wkey in ("Необходимые атрибуты", "Необходимые навыки", "Необходимые специализации"):
        if wkey in sec:
            need.update(dicts(sec[wkey][i]))
    own = {}
    for wkey in sec:
        if wkey.startswith("Бонусы к атрибутам"):
            own.update(dicts(sec[wkey][i]))
    return fields, need, price_of(sec["Базовая цена"][i]), own


def set_bonus_table(page):
    """variant -> {K: {bonus: value}} from a set page's table ("A"/"G", or
    "*" for a lone column that serves every variant)."""
    rec = WIKI_DATA[page]
    table = rec["tables"][0]
    cols = {"A": 0, "G": 2} if table["tiers"] == ["A", "P", "G"] else {"*": 0}
    out = {}
    for v, i in cols.items():
        per_k = {}
        for section, rows in table["sections"].items():
            m = re.match(r"Комплект из (\d) предметов", section)
            if not m:
                continue
            k = int(m.group(1))
            line = {}
            for wkey, values in rows.items():
                if wkey == "Цена комплекта":
                    continue
                value = values[i]
                if value is None:
                    continue
                name = BONUS_NAMES.get(wkey.strip(), wkey.strip())
                line[name] = int(value)
            if line:
                per_k[k] = line
        out[v] = per_k
    return out


def set_price(page, variant):
    """The set page's Цена комплекта for a variant, as afro or hundredths of G."""
    table = WIKI_DATA[page]["tables"][0]
    for section in table["sections"].values():
        if "Цена комплекта" in section:
            cells = section["Цена комплекта"]
            i = {"A": 0, "G": 2}.get(variant, 0) if len(cells) == 3 else 0
            cur, v = price_of(cells[i])
            return ("afro", v) if cur == "afro" else ("g", half_up(v * 100))
    return None


# --- the layout ----------------------------------------------------------------

def read_layout(path):
    """(rows that make sets, [(row, why skipped)])."""
    doc = load_json(path)
    good, skipped = [], []
    for row in doc.get("sets") or []:
        name = str(row.get("name") or "").strip()
        slots = row.get("slots") or {}
        missing = [s for s in SLOTS if not slots.get(s)]
        if len(name) < MIN_NAME:
            skipped.append((row, "no real name (%r)" % name))
        elif missing:
            skipped.append((row, "empty slots: %s" % ", ".join(missing)))
        elif not isinstance(row.get("level"), int):
            skipped.append((row, "no level"))
        else:
            good.append(row)
    return good, skipped


def figure(row, res_dir):
    """The res a full set draws its wearer as: the page's, else the one
    suggested, checked against the client's res/personages."""
    raw = row.get("res")
    if raw is None or str(raw).strip() == "":
        raw = SUGGESTED.get(row["name"].strip(), 0)
    try:
        res = int(str(raw).strip())
    except ValueError:
        raise SystemExit("%s: res %r is no number" % (row["name"], raw))
    if res == 0:
        return 0
    if res in NOT_A_FIGURE:
        raise SystemExit("%s: res %d is not a person in clothes" % (row["name"], res))
    base = os.path.join(res_dir, "personages")
    if not (os.path.isdir(os.path.join(base, str(res)))
            and os.path.isfile(os.path.join(base, "%d.xml" % res))):
        raise SystemExit("%s: res/personages has no figure %d (folder and .xml)" % (row["name"], res))
    return res


def pieces_of(row, cat, by_name):
    """variant -> {slot: type}, and the set's family and series level.

    The G of each piece is its own series' G. A quest piece has none in the
    original: five of them are the one variant Q, and one among A pieces is
    matched by the G of the series the rest of the set is (the same slot),
    and said so. Unless the quest series has a G of our own for every piece
    (data/own_items.json, a copy of that very piece's picture): then the set
    is sold, its quest pieces are its A, priced in afro, and our types its G
    (Чёрный Ловелас[12], the owner's «за афро и за голд», 2026-10-13;
    Тёмное Эхо[17] with Абу-Хамед, 2026-10-14: SOLD_SINCE)."""
    parsed = {}
    for slot in SLOTS:
        t = int(row["slots"][slot])
        name = cat.get(t, (None, ""))[1]
        m = SERIES.match(name)
        if not m or m.group(1) != slot:
            raise SystemExit("%s %s: type %d (%s) is no mod00 %s of a clothing series"
                             % (row["name"], slot, t, name or "unknown", slot))
        if m.group(4) not in ("A", "Q"):
            raise SystemExit("%s %s: type %d is %s; the page gives the A (or Q) piece"
                             % (row["name"], slot, t, name))
        parsed[slot] = (t, m.group(2), int(m.group(3)), m.group(4))
    variants = {v for _t, _f, _l, v in parsed.values()}
    notes = []
    if variants == {"Q"}:
        fams = {(f, lvl) for _t, f, lvl, _v in parsed.values()}
        family, level = sorted(fams)[0]
        quest = {s: p[0] for s, p in parsed.items()}
        own = own_items.load()
        gold = {s: by_name.get("%s_%s_LVL_%d_G_mod00" % (s, f, lvl))
                for s, (_t, f, lvl, _v) in parsed.items()}
        if not any(gold.values()):
            return {"Q": quest}, family, level, notes
        wrong = [s for s, g in gold.items() if g not in own or own[g]["like"] != quest[s]]
        if wrong:
            raise SystemExit("%s: a quest set is sold when every piece has a G of our own copying "
                             "its picture (data/own_items.json); not so for %s"
                             % (row["name"], ", ".join(wrong)))
        if (family, level) not in SOLD_SINCE:
            raise SystemExit("%s: a quest set sold for afro and gold says since when and why "
                             "(SOLD_SINCE)" % row["name"])
        notes.append("A: the quest series' own pieces (_Q_), sold for afro since %s; G: types of "
                     "our own, %s (data/own_items.json), each its A piece's picture: the "
                     "original has no G of this series"
                     % (SOLD_SINCE[(family, level)], ", ".join(str(gold[s]) for s in SLOTS)))
        return {"A": quest, "G": gold}, family, level, notes
    main = {}
    for _t, f, lvl, v in parsed.values():
        if v == "A":
            main[(f, lvl)] = main.get((f, lvl), 0) + 1
    family, level = max(main, key=lambda k: (main[k], -k[1]))
    out = {"A": {}, "G": {}}
    for slot, (t, f, lvl, v) in parsed.items():
        out["A"][slot] = t
        src_f, src_l = (f, lvl) if v == "A" else (family, level)
        g_name = "%s_%s_LVL_%d_G_mod00" % (slot, src_f, src_l)
        if g_name not in by_name:
            raise SystemExit("%s %s: the client has no %s" % (row["name"], slot, g_name))
        out["G"][slot] = by_name[g_name]
        if v == "Q":
            notes.append("%s: the page's A piece is the quest type %d (%s), which has no G; the G "
                         "variant takes %s, the G of the series the rest of the set is, in the "
                         "same slot" % (slot, t, cat[t][1], g_name))
    return out, family, level, notes


# --- one set ----------------------------------------------------------------

def label(word, level, variant):
    """A name the way texts.xml writes one; orig_texts.item_name drops [A] and
    the level and shows [G] as " (G)", [Q] as " (Q)"."""
    return "%s[%d][%s]" % (word, level, variant)


def wiki_piece(page, variant, level):
    """One piece of a set with a wiki page: the frame's fields, _designed
    notes, and the attributes the file cannot carry."""
    cols, lone, col_note = columns(page)
    notes = []
    if lone is None:
        i = cols[variant]
        col_note = " (%s column)" % variant
    else:
        i = cols[lone]
        if col_note.startswith(" (the first"):
            notes.append(("column", "the wiki's pieces have one column per favoured attribute; "
                                    "the first is taken, as the rule says"))
    fields, need, (cur, price), own = page_numbers(page, i)
    if variant in ("A", "Q"):
        cost, g_cost = (price if cur == "afro" else half_up(price * AFRO_PER_G)), 0
        if cur != "afro":
            notes.append(("convert", "the wiki's pieces have no afro column: the gold column's "
                                     "numbers, priced in afro at 4000 afro = 1 G"))
    else:
        cost, g_cost = 0, half_up((price if cur == "g" else price / float(AFRO_PER_G)) * 100)
        if cur != "g":
            notes.append(("convert", "the wiki's pieces have no G column: the afro column's "
                                     "numbers, priced in gold at 4000 afro = 1 G"))
    fix = PRICE_FIXES.get((page, variant))
    if fix:
        if variant == "G":
            g_cost = fix[0]
        else:
            cost = fix[0]
        notes.append(("fix", "%s %s: price %s -- %s" % (page, variant, fix[0], fix[1])))
    # In the order the file has always been written in.
    rec = {key: fields.get(key, 0) for key in ("armor_class", "max_break_abs", "weight")}
    rec.update(cost=cost, g_cost=g_cost, premium=0, exchang=1 if variant == "A" else 0)
    for key in NUMBER_FIELDS:
        if key.startswith("bonus_") and fields.get(key):
            rec[key] = fields[key]
    shoot = need.pop("Стрельба", None)
    if shoot != (level or None):
        notes.append(("shoot", shoot))
    if level:
        need["Стрельба"] = level
    rec["need"] = ordered_need(need)
    return rec, "%s%s" % (page, col_note), notes, own


def summarise(notes, level):
    """One line per kind of departure, not one per piece."""
    out = []
    shoot = sorted({n[1] for n in notes if n[0] == "shoot"}, key=lambda x: (x is not None, x))
    if shoot:
        asked = " / ".join("none" if s is None else str(s) for s in shoot)
        out.append("Стрельба %d on every piece, the set's level (the wiki's pieces ask %s)"
                   % (level, asked) if level else "no Стрельба at level 0")
    for kind in ("convert", "fix", "column"):
        for n in notes:
            if n[0] == kind and n[1] not in out:
                out.append(n[1])
    return out


def ordered_need(need):
    """Attributes, then skills, then specialisations, each in the client's order."""
    out = {}
    for _kind, titles in sets.LISTS:
        for t in titles:
            if need.get(t):
                out[t] = need[t]
    unknown = set(need) - set(out)
    if unknown:
        raise SystemExit("a requirement the client cannot show: %s" % sorted(unknown))
    return out


def interpolate(lo, hi, t):
    """A designed piece between two anchor pieces (both A or Q, afro)."""
    rec = {}
    for key in NUMBER_FIELDS:
        a, b = lo.get(key, 0), hi.get(key, 0)
        v = half_up(a + (b - a) * t)
        if v or not key.startswith("bonus_"):
            rec[key] = v
    rec["cost"] = to_thousand(lo["cost"] + (hi["cost"] - lo["cost"]) * t)
    need = {}
    for k in set(lo["need"]) & set(hi["need"]):
        if k != "Стрельба":
            need[k] = half_up(lo["need"][k] + (hi["need"][k] - lo["need"][k]) * t)
    return rec, need


def interpolate_bonus(lo, hi, t):
    out = {}
    for k in sets.PIECES:
        a, b = lo.get(k, {}), hi.get(k, {})
        line = {}
        for key in list(a) + [x for x in b if x not in a]:
            v = half_up(a.get(key, 0) + (b.get(key, 0) - a.get(key, 0)) * t)
            if v:
                line[key] = v
        if line:
            out[k] = line
    return out


# --- output ---------------------------------------------------------------------

def compact(x):
    return json.dumps(x, ensure_ascii=False)


def indent(text, n):
    pad = " " * n
    return text.replace("\n", "\n" + pad)


def dump(meta, table):
    """The file as the owner edits it: one line per piece and per bonus line."""
    out = ["{", ' "_meta": ' + indent(json.dumps(meta, ensure_ascii=False, indent=1), 1) + ",",
           ' "sets": {']
    keys = list(table)
    for n, key in enumerate(keys):
        s = table[key]
        out.append('  %s: {' % compact(str(key)))
        lines = []
        for field, value in s.items():
            if field == "bonus":
                if not value:
                    lines.append('   "bonus": {}')
                else:
                    inner = ",\n".join('    %s: %s' % (compact(str(k)), compact(v))
                                       for k, v in value.items())
                    lines.append('   "bonus": {\n%s\n   }' % inner)
            elif field == "members":
                inner = ",\n".join('    %s: %s' % (compact(slot), compact(p)) for slot, p in value.items())
                lines.append('   "members": {\n%s\n   }' % inner)
            else:
                lines.append('   %s: %s' % (compact(field), compact(value)))
        out.append(",\n".join(lines))
        out.append("  }" + ("," if n < len(keys) - 1 else ""))
    out += [" }", "}"]
    return "\n".join(out) + "\n"


META = {
    "about": "Clothing sets: which five pieces make one, what each piece is called and worth, "
             "what the set adds, what a full set draws its wearer as. Read by server/sets.py at "
             "start; a file that does not parse or does not validate stops the server (the set "
             "names are string ids the HTTP preload must carry). Keys starting with _ never "
             "reach the wire. Built by data/build_sets.py from the owner's wardrobe layout; edit "
             "the layout and rebuild, or edit here by hand and keep the rules.",
    "decided": None,     # filled in build()
    "real": "FROM THE WIKI wherever it has the number: the 2013 tables of these very sets and "
            "their pieces (data/wiki/pages.json, parsed into data/wiki_items.json), each "
            "member's _wiki naming the page and the column. Names and descriptions from the "
            "original texts.xml or the wiki, as each piece's _desc says (none: the wiki page's).",
    "designed": "DESIGNED only where the wiki is silent or contradicts itself, and each such "
                "place says so in its set's _designed: a variant column the wiki does not have, "
                "the ladder's Стрельба where a page asks another, four prices a page gives that "
                "its own set page refutes, three sets with no numbers on the wiki at all "
                "(Чёрный Ловелас's pieces, Дредноут, Паладин), interpolated between their "
                "neighbours on the ladder, and Чёрный Ловелас's bonus, which its page copies "
                "from Штурм-М[15], designed the same way since the set is sold.",
    "rules": [
        "Pieces: the layout's A piece for each slot (or quest piece, _Q_); the G variant is the "
        "G of the same series and level, the same icon in gold. A set of quest pieces is its "
        "one variant, Q -- unless its series has a G of our own for every piece "
        "(data/own_items.json, each a copy of its quest piece's picture): then the set is sold, "
        "the quest pieces its A and our types its G (Чёрный Ловелас, the owner's 'за афро и за "
        "голд', 2026-10-13; Тёмное Эхо with Абу-Хамед, the owner's 'сделай потом абу хамед в "
        "таком же формате', 2026-10-14). A quest piece among A ones is matched in G by the G of "
        "the series the rest of the set is. No P anywhere: the owner took premium out of the game "
        "(items.premium).",
        "set key = set_type = the texts.xml row of the name of the set these very types formed in "
        "the original (the block 10938-11289): Колонист[N] for Set_M_LVL_N, Беженец[N] for "
        "Bs_M_LVL_N, Легионер / Красное ЭXO / Темное ЭXO / Штурм-М / Дредноут / Паладин / "
        "Апокалипсис[N] for Exzo_M_LVL_N, the [Q] rows for the quest family Bs_U (a sold quest "
        "set's A keeps it). Stable, unique, below 100 000, and the row the types already "
        "answered to. A set of our own types, which no row of the original names, is keyed by "
        "its first piece: Чёрный Ловелас (G) 60000, Тёмное Эхо (G) 60005. The owner's names are "
        "his own: Странник sits on Колонист[11]'s row, Магриб on Беженец[16]'s, Пустынник on "
        "Колонист[7]'s, Спецназ on Колонист[17]'s.",
        "Магриб is the owner's name for Bs_M_LVL_16, whose icons are a steel helmet, a field "
        "shirt, a plate vest, army trousers and boots: the wiki's Армейские вещи ('used "
        "everywhere, the military of Магриб among them'), whose pieces ask Стрельба 6, the rung "
        "he put it on. Its numbers, names and bonus are that page's.",
        "name: written the way texts.xml writes one, [level][variant] and all, with the ladder's "
        "level, and cleaned by server/orig_texts.item_name: [A] and the level go, [G] shows as "
        "' (G)', [Q] as ' (Q)' like every quest thing in the game.",
        "res: the figure (res/personages/<res>, a folder with its .xml) the layout gives, else "
        "the one suggested to the owner; the same on every variant; 0 leaves the wearer's own.",
        "Numbers per piece from the wiki page in _wiki: Уровень брони -> armor_class, Износ -> "
        "max_break_abs, Вес -> weight (grams), Здоровье / Выносливость / Очки действия / Крит. "
        "попадание / Избег. крит. попадание -> bonus_hp / bonus_st / bonus_od / bonus_cp / "
        "bonus_ce, Базовая цена -> cost (afro) or g_cost (hundredths of G: 0.25 G is 25), "
        "Необходимые атрибуты / навыки / специализации -> need.",
        "Columns: the page's A column for A, its G column for G. A lone column is the variant its "
        "price says and the other copies its numbers with the price converted at 4000 afro = 1 G, "
        "the rate of every wiki set page; rounding half up. A quest piece takes its page's first "
        "column (Тёмное Эхо's pages have three, by the attribute each favours: Сила, Ловкость, "
        "Восприятие) and is priced in afro, as the wiki prices it.",
        "Variants: A priced in afro (cost), exchangeable; G priced in gold (g_cost), cost 0, not "
        "exchangeable; Q priced in afro and not exchangeable, as the wiki's quest pieces; premium "
        "0 throughout.",
        "Requirement Стрельба = the set's level on the ladder, on every piece; the other "
        "requirements are the page's. Where a page asks another Стрельба, its set's _designed "
        "says so.",
        "Set bonuses per K pieces worn, from the set page's column (a lone column serves every "
        "variant); cumulative, K=5 adds to what 2..4 gave, the way the client's tooltip lights "
        "its lines. Темное Эхо is transcribed from the page's wikitext, which wiki_items.json "
        "does not parse. Вещи Беженца has none ('Дополнительных бонусов и параметров не "
        "предусмотрено'). Снаряжение Чёрного Ловеласа's column is Штурм-М[15]'s A word for word "
        "(+20 action points at three pieces), an event set's that was never sold (its Цена "
        "комплекта is blank): since the set is sold at 12 (2026-10-13) its bonuses are "
        "designed, as below, and the page's stay in data/build_sets.py (TRANSCRIBED), served "
        "nowhere.",
        "Модификация паладин is Апокалипсис's table: the page lists the five Апокалипсис pieces "
        "and its 300 G is their sum; only its title and blurb are Паладин's.",
        "DESIGNED sets (no numbers on the wiki): each number of each piece linear between the "
        "nearest rungs below and above that have wiki numbers, by level -- value = low + (high - "
        "low) x (level - low level) / (high level - low level), half up -- from their A (or Q) "
        "pieces in the same slot; afro prices to whole thousands; Телосложение asked likewise, a "
        "requirement only one neighbour has is not carried; the G lies between the neighbours' "
        "G pieces where both have a G (else it copies the A's numbers), its price the A's at "
        "4000 afro = 1 G. A set with no wiki page gets its bonuses the same way, K by K and "
        "bonus by bonus (its G between the neighbours' G columns where its pieces are), 0 where "
        "a neighbour has none; so does Чёрный Ловелас. Its full set (pieces and bonuses) thus "
        "lies between its neighbours', as its price does.",
        "Not carried: a piece's own attribute bonus (the wiki's 'Бонусы к атрибутам') has no "
        "field in server/sets.py ITEM_FIELDS; it is kept under the piece's _bonus_attribs, "
        "unread, until it has one. Nor 'Допустимость продажи: Нет' of the quest pieces.",
        "Wiki numbers kept although odd, for the owner to judge: Пончо's Выносливость 45 at the "
        "first rung; on the owner's ladder Магриб (Армейские вещи, 4 G "
        "the set) stands above Странник (5 G) and Красное Эхо (500 000 afro) above Штурм-М "
        "(700 000), both weaker than the rung below; Броня пустынника (G) and Ботинки легионера "
        "(G) wear out sooner than their A, as their pages say; Апокалипсис asks 5 in every "
        "firearm specialisation.",
    ],
    "sets": None,        # filled in build(): the table of keys
    "fields": "sets.<set_type>: name, desc (cleaned by orig_texts as described), family (the "
              "client's series), level (the ladder's), variant, res, bonus, members; _layout, "
              "_source and _designed are the audit trail. bonus.<K> (K = 2..6 pieces worn): hp, "
              "st, od, cp, ce, and any attribute, skill or specialisation by the name the "
              "client's tooltip gives it (Сила, Стрельба, Ближний бой, ...). "
              "members.<helm|shirt|armor|pants|boots>: type, name and desc (the piece's own, over "
              "the original's), _wiki / _desc (where the numbers and the text come from), then "
              "ss_si_wear fields laid over the designed frame the way a wiki record is -- "
              "armor_class, max_break_abs, weight, cost (afro), g_cost (hundredths of G), "
              "premium, exchang, bonus_hp, bonus_st, bonus_od, bonus_cp, bonus_ce -- need: "
              "requirements by name, and _bonus_attribs (not read, see rules).",
}


def build(layout_path, res_dir):
    cat = items.catalogue()
    by_name = {n: t for t, (_r, n) in cat.items()}
    rows, skipped = read_layout(layout_path)
    rows.sort(key=lambda r: r["level"])

    plans = []
    for row in rows:
        name = row["name"].strip()
        src = SOURCES.get(name)
        if src is None:
            skipped.append((row, "no words for a set of this name in data/build_sets.py SOURCES "
                                 "(names, descriptions, wiki pages) -- add them, then rebuild"))
            continue
        variants, family, level_s, notes = pieces_of(row, cat, by_name)
        keys = SET_ROWS.get((family, level_s))
        if not keys or any(v not in keys for v in variants):
            raise SystemExit("%s: no texts.xml row for %s level %d %s"
                             % (name, family, level_s, "/".join(variants)))
        plans.append(dict(row=row, name=name, src=src, variants=variants, family=family,
                          series_level=level_s, level=row["level"], notes=notes,
                          res=figure(row, res_dir), keys=keys))

    # First the sets with wiki numbers: they are the anchors of the designed ones.
    built = {}
    anchors = []
    for plan in plans:
        if all(p[1] for p in plan["src"]["pieces"].values()):
            built[plan["name"]] = wiki_set(plan)
            anchors.append(plan)
    for plan in plans:
        if plan["name"] not in built:
            built[plan["name"]] = designed_set(plan, anchors, built)
    # Bonuses: pages first, then the designed ones between them.
    for plan in plans:
        if plan["src"]["bonus"] != "design":
            set_bonuses(plan, built[plan["name"]])
    bonus_anchors = [p for p in plans if p["src"]["bonus"] != "design"]
    for plan in plans:
        if plan["src"]["bonus"] == "design":
            designed_bonuses(plan, bonus_anchors, built)

    table = {}
    for plan in plans:
        for v, rec in built[plan["name"]]["variants"].items():
            key = plan["keys"][v]
            if key in table:
                raise SystemExit("set_type %d twice" % key)
            table[key] = rec
    check_prices(plans, built)
    return plans, built, table, skipped


def words(plan, slot):
    word, page, desc = plan["src"]["pieces"][slot]
    if desc == WIKI:
        text = WIKI_DATA[page]["description"]
        note = None
    else:
        note, text = desc
    return word, page, text, note


def set_desc(plan):
    d = plan["src"]["desc"]
    if d == WIKI:
        return WIKI_DATA[plan["src"]["page"]]["description"], "wiki %s" % plan["src"]["page"]
    return d[1], d[0]


def new_set(plan, v, source, designed):
    desc, desc_src = set_desc(plan)
    key = plan["keys"][v]
    if key >= own_items.FIRST:
        why = "key %d, its first piece, a type of our own: no row of the original names it" % key
    else:
        why = "key texts.xml %d, the row of the set these types formed in the original" % key
    return {
        "name": label(plan["name"], plan["level"], v),
        "desc": desc,
        "_layout": plan["row"].get("key"),
        "_source": "%s; desc %s; %s" % (why, desc_src, source),
        "_designed": designed,
        "family": plan["family"],
        "level": plan["level"],
        "variant": v,
        "res": plan["res"],
        "bonus": {},
        "members": {},
    }


def wiki_set(plan):
    out = {"variants": {}, "base": {}}
    for v in plan["variants"]:
        designed = list(plan["notes"])
        rec = new_set(plan, v, "numbers wiki, each piece's own page (its _wiki)", designed)
        notes = []
        for slot in SLOTS:
            word, page, text, note = words(plan, slot)
            fields, col, more, own = wiki_piece(page, v, plan["level"])
            notes += more
            piece = {"type": plan["variants"][v][slot], "name": label(word, plan["level"], v),
                     "desc": text, "_wiki": col}
            if note:
                piece["_desc"] = note
            piece.update(fields)
            if own:
                piece["_bonus_attribs"] = own
            rec["members"][slot] = piece
        designed += summarise(notes, plan["level"])
        if v == "A" and plan["name"] == "Беженец":
            designed.append("exchang 1 on every piece where the wiki says 'Допустимость обмена: "
                            "Нет': there they were a quest's gift, here they are bought, and an A "
                            "piece follows the A rule")
        out["variants"][v] = rec
    base_v = "A" if "A" in plan["variants"] else "Q"
    out["base"] = {s: dict(p, need=dict(p["need"])) for s, p in out["variants"][base_v]["members"].items()}
    return out


def neighbours(level, anchors):
    below = [a for a in anchors if a["level"] <= level]
    above = [a for a in anchors if a["level"] > level]
    return (below[-1] if below else None), (above[0] if above else None)


def designed_set(plan, anchors, built):
    lo, hi = neighbours(plan["level"], anchors)
    if lo is None and hi is None:
        raise SystemExit("%s: no rung with wiki numbers to design it from" % plan["name"])
    lo, hi = lo or hi, hi or lo
    t = 0.0 if hi["level"] == lo["level"] else (plan["level"] - lo["level"]) / float(hi["level"] - lo["level"])
    why = ("no numbers on the wiki: every piece designed between %s (%d) and %s (%d), "
           "t = %d/%d, by the rule in _meta" % (lo["name"], lo["level"], hi["name"], hi["level"],
                                                plan["level"] - lo["level"], hi["level"] - lo["level"]))
    out = {"variants": {}, "base": {}}
    base = {}
    for slot in SLOTS:
        rec, need = interpolate(built[lo["name"]]["base"][slot], built[hi["name"]]["base"][slot], t)
        if plan["level"]:
            need["Стрельба"] = plan["level"]
        base[slot] = (rec, ordered_need(need))
    # The G between the neighbours' G pieces (their pages' G columns) where
    # both have a G, priced as the A; else the A's numbers. A G column is
    # stronger than its A, so a G copied from the A would stand below the
    # rung under it (Чёрный Ловелас (G) against Пустынник (G)).
    gold = None
    if lo is not hi and all("G" in built[n["name"]]["variants"] for n in (lo, hi)):
        gold = {}
        for slot in SLOTS:
            rec, need = interpolate(built[lo["name"]]["variants"]["G"]["members"][slot],
                                    built[hi["name"]]["variants"]["G"]["members"][slot], t)
            rec["cost"] = base[slot][0]["cost"]
            if plan["level"]:
                need["Стрельба"] = plan["level"]
            gold[slot] = (rec, ordered_need(need))
    for v in plan["variants"]:
        designed = list(plan["notes"]) + [why]
        if v == "G":
            designed.append("G: between %s (G) and %s (G), their G pieces, priced as the A at "
                            "4000 afro = 1 G" % (lo["name"], hi["name"]) if gold else
                            "G: the A's numbers, priced at 4000 afro = 1 G")
        rec = new_set(plan, v, "numbers designed", designed)
        for slot in SLOTS:
            word, _page, text, note = words(plan, slot)
            fields, need = (gold or base)[slot] if v == "G" else base[slot]
            piece = {"type": plan["variants"][v][slot], "name": label(word, plan["level"], v),
                     "desc": text, "_wiki": None}
            if note:
                piece["_desc"] = note
            afro = fields["cost"]
            piece.update(armor_class=fields["armor_class"], max_break_abs=fields["max_break_abs"],
                         weight=fields["weight"],
                         cost=afro if v != "G" else 0,
                         g_cost=0 if v != "G" else afro // 40,
                         premium=0, exchang=1 if v == "A" else 0)
            for key in NUMBER_FIELDS:
                if key.startswith("bonus_") and fields.get(key):
                    piece[key] = fields[key]
            piece["need"] = dict(need)
            rec["members"][slot] = piece
        out["variants"][v] = rec
    base_v = "A" if "A" in plan["variants"] else "Q"
    out["base"] = {s: dict(p, need=dict(p["need"])) for s, p in out["variants"][base_v]["members"].items()}
    out["anchors"] = (lo["name"], hi["name"], t)
    out["gold"] = gold is not None
    return out


BONUS_ORDER = list(sets.SCALARS) + [t for _k, titles in sets.LISTS for t in titles]


def lines(per_k):
    """{K: line} as the file writes it: K ascending, each line in the client's
    order (the scalars, then attributes, skills, specialisations)."""
    return {str(k): {b: per_k[k][b] for b in sorted(per_k[k], key=BONUS_ORDER.index)}
            for k in sorted(per_k)}


def set_bonuses(plan, done):
    kind, page = plan["src"]["bonus"], plan["src"]["page"]
    if kind == "none":
        per = {"*": {}}
        note = "bonus none: the wiki's %s says there is none" % page
    elif kind == "text":
        per = {"*": TRANSCRIBED[page]}
        note = "bonus wiki %s, transcribed from its wikitext (one column)" % page
    else:
        per = set_bonus_table(page)
        note = "bonus wiki %s%s" % (page, " (one column)" if "*" in per else "")
    done["bonus"] = per.get("A", per.get("*"))
    done["bonus_of"] = {}
    for v, rec in done["variants"].items():
        b = per.get(v, per.get("*"))
        done["bonus_of"][v] = b
        rec["bonus"] = lines(b)
        rec["_source"] += "; " + note


def designed_bonuses(plan, anchors, built):
    """Each K and each bonus between the neighbours' columns: the A (or Q)
    ones, and for a G whose pieces were designed between the neighbours' G
    (designed_set) their G columns."""
    lo, hi = neighbours(plan["level"], anchors)
    lo, hi = lo or hi, hi or lo
    t = 0.0 if hi["level"] == lo["level"] else (plan["level"] - lo["level"]) / float(hi["level"] - lo["level"])
    b = interpolate_bonus(built[lo["name"]]["bonus"], built[hi["name"]]["bonus"], t)
    built[plan["name"]]["bonus"] = b
    gold = built[plan["name"]].get("gold") and all(
        "G" in built[n["name"]]["bonus_of"] for n in (lo, hi))
    why = plan["src"].get("bonus_why") or "no set page on the wiki"
    for v, rec in built[plan["name"]]["variants"].items():
        if v == "G" and gold:
            rec["bonus"] = lines(interpolate_bonus(built[lo["name"]]["bonus_of"]["G"],
                                                   built[hi["name"]]["bonus_of"]["G"], t))
            cols = " (their G columns)"
        else:
            rec["bonus"] = lines(b)
            cols = ""
        rec["_designed"].append("bonus: %s; each K and each bonus between %s (%d) and %s (%d)%s, "
                                "0 where one has none, half up"
                                % (why, lo["name"], lo["level"], hi["name"], hi["level"], cols))
        rec["_source"] += "; bonus designed"


def check_prices(plans, built):
    """Each wiki set's pieces add up to its page's Цена комплекта, as served
    (after PRICE_FIXES). A total that does not is printed, not fixed."""
    for plan in plans:
        page = plan["src"]["page"]
        if not page or plan["src"]["bonus"] not in ("table", "text"):
            continue
        if not all(p[1] for p in plan["src"]["pieces"].values()) or not WIKI_DATA[page]["tables"]:
            continue
        for v, rec in built[plan["name"]]["variants"].items():
            want = set_price(page, v)
            # Only a total in the variant's own currency says anything: a
            # lone gold column has no afro total to hold the A copy to.
            if not want or want[0] != ("g" if v == "G" else "afro"):
                continue
            key = "g_cost" if v == "G" else "cost"
            got = sum(p[key] for p in rec["members"].values())
            if got != want[1]:
                print("  note: %s %s pieces add up to %d %s, the set page says %d"
                      % (plan["name"], v, got, want[0], want[1]))


def finish(rec):
    """_designed as a list only when there is something in it."""
    d = rec.pop("_designed")
    out = {}
    for k, v in rec.items():
        out[k] = v
        if k == "_source" and d:
            out["_designed"] = d
    return out


def valley(plans):
    """The rungs of the valley's band, the first city of data/shop_bands.json
    (0-4 since 2026-10-10): what Локсли and Абдула sell of the ladder, A and
    G, helm to boots. For the printout; the server works it out itself."""
    import shop_bands
    low, top = shop_bands.CITIES[0][1:3] if shop_bands.CITIES else (0, 0)
    out = []
    for plan in plans:
        if not low <= plan["level"] <= top:
            continue
        for v in ("A", "G"):
            if v in plan["variants"]:
                out += [plan["variants"][v][s] for s in SLOTS]
    return out


def ladder_pieces(plans):
    """Every piece of every set of the layout, all variants."""
    return {plan["variants"][v][s] for plan in plans for v in plan["variants"] for s in SLOTS}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("layout")
    ap.add_argument("--npcs", action="store_true", help="also write the list into data/npcs.json")
    args = ap.parse_args()
    res_dir = os.environ.get("LAVA_RES")
    if not res_dir or not os.path.isdir(os.path.join(res_dir, "personages")):
        raise SystemExit("LAVA_RES must point at the client's res/")

    plans, built, table, skipped = build(args.layout, res_dir)
    meta = dict(META)
    meta["decided"] = (
        "Owner's wardrobe layout (%s): %d sets on the ladder, %s. Every set seller sells the A "
        "and G sets of his city's band, A then G, helm to boots, mod00 only (data/shop_bands.json, "
        "server/shop_bands.py; the owner's 'по уровню городов', 2026-10-10) -- Локсли (%d, "
        "'Одежда и Броня') the valley's; a quest (Q) set exists as data only, for quests and "
        "drops to come (none on the ladder since 2026-10-14). Чёрный Ловелас, the quest series "
        "Bs_U_LVL_12, is sold for afro and for gold (the owner's 'поставь ловеласа у Гали и за "
        "афро и за голд', 2026-10-13): its "
        "quest pieces are its A, five types of our own its G (data/own_items.json). So is "
        "Тёмное Эхо, the quest series Bs_U_LVL_16, the 17th rung, since Абу-Хамед (the owner's "
        "'сделай потом абу хамед в таком же формате', 2026-10-14): until then no stall sold a "
        "set of 17."
        % (os.path.basename(args.layout), len(plans),
                                ", ".join("%s %d" % (p["name"], p["level"]) for p in plans),
                                LOXLEY))
    meta["sets"] = ["%s (level %d): %s -- %s" % (
        p["name"], p["level"],
        ", ".join("%s %d" % (v, p["keys"][v]) for v in p["variants"]),
        "%s_LVL_%d" % (p["family"], p["series_level"])) for p in plans]
    doc_sets = {str(k): finish(dict(v)) for k, v in table.items()}
    # The server's own reader has the last word before anything is written.
    sets.parse({"sets": doc_sets})
    text = dump(meta, doc_sets)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)

    stock = valley(plans)
    print("data/sets.json: %d sets, %d pieces" % (len(table), sum(len(s["members"]) for s in table.values())))
    for p in plans:
        b = built[p["name"]]
        ids = "  ".join("%s %d: %s" % (v, p["keys"][v], ",".join(str(b["variants"][v]["members"][s]["type"])
                                                                   for s in SLOTS)) for v in p["variants"])
        print("  %2d %-15s res %-5d %s" % (p["level"], p["name"], p["res"], ids))
    for row, why in skipped:
        print("  skipped %r (level %s): %s" % (row.get("name"), row.get("level"), why))
    print("Локсли (%d) and Абдула sell the valley's band of it, %d types:" % (LOXLEY, len(stock)))
    print(json.dumps(stock))
    if args.npcs:
        with io.open(NPCS, encoding="utf-8") as fh:
            raw = fh.read()
        doc = json.loads(raw)
        own = doc.setdefault("stock", {}).get(str(LOXLEY))
        if own is not None:
            ladder = ladder_pieces(plans)
            doc["stock"][str(LOXLEY)] = [t for t in own if t not in ladder]
            with io.open(NPCS, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print("data/npcs.json: stock %d keeps its own goods, no set pieces" % LOXLEY)


if __name__ == "__main__":
    main()
