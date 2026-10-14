"""Build data/questgen_weaponcraft.json: the weapon craft of a city, row by row.

    MSYS_NO_PATHCONV=1 wsl.exe -e bash -lc "cd /mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server && LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/build_weaponcraft.py"
    ... python3 data/build_weaponcraft.py --stock     the blueprint stalls' lists

The original's weapon craft was a quest of a master's, written by the
thousand from a template -- the plan's «шаблонные семейства ... генераторами
по политике владельца» -- and this is the one generator of it. It reads the
original's own lines out of texts.xml (LAVA_ORIG_TEXTS, default
/mnt/c/Users/gmkrt/Downloads/texts.xml), ties every gun, blueprint and part
they name to its objects.xml type, and writes the rows a CITY asks for by
its level band. A city is data (CITIES): its band, its masters by class and
line, its camps, whetstones, gunsmiths, decoder and blueprint stalls. The
next city adds an entry and gets its rows from the same code; the rows of
the cities before it keep their types (number: each row's key -- family,
city, the original's line -- keeps the type the table's "types" gave it,
and a new key takes the next type of its family's blocks, FAMILIES).

The families, each a repeatable service (quests.py: service -- neither
counted nor refused by the daily limit, no place in the server's journal),
open to the city's band (level = its low end, max_level = its high end: the
plan's «видны только в своём поясе»):

  upgrade   «<gun> [(G)]: <effect>» -- bring the gun and the blueprint, get
            the gun's modification. The newest edition's pairs of name and
            start (texts.xml 51681-51934, 58935-59370 for Вади-Хальфа's band),
            A and G lines; and the older numbered ones («Задание
            №B000000NN», 24620-24945) for the [Q] guns of «Веселый праздник»,
            at the city's q_masters. Only a gun with the wiki's table («real
            stats»; a gun without one would be the designed stand-in) and a
            non-premium one; the modification is objects.xml's
            <base>_mod_<effect>[_gold], the blueprint bpg_<effect>_lvl<N> of
            the recipe's level (the two-effect «Урон и размер обоймы» the
            _afro_ one for the A line and the _gold_ one for the G line, the
            numbered ones' two-effect blueprints bpb_*: DESIGNED readings of
            the internal names). Each blueprint slot also drops from the
            chiefs of the city's camps of that level («Сражение за чертежи»,
            «главари ... чертежи и схемы для модернизации», 47395), for a
            player with the recipe open (quests.py: a slot's "drop"): DESIGNED
            chance BLUEPRINT_DROP, one blueprint a corpse at most whatever
            rows are open (the slot's "one_of").
  knife     «Заточка / Эргономика / Заточка и Эргономика <ножа>» at a
            whetstone (50915-50974): the knife (G), its blueprint -> the
            knife's modification (knife_lvl<N>_G_damage / _actionpoint /
            _damage_actionpoints).
  salvage   «Разобрать сломаный <оружие> Nкл.» (25400-25456) at a gunsmith:
            a broken gun of the class (server/craft.py: ready, hand_in, the
            cheapest; the start says which, a DESIGNED line), the text's fee,
            one part of the class's tier drawn (rew_random), the text's
            «Переработка» experience (rew_spec_xp: nothing unless learned, as
            the text says). A class is a band of gun levels read off its
            parts' own level (class_levels, DESIGNED), and its row goes to
            the city whose band holds that level, where a real gun of the
            class falls in its band.
  assembly  «<gun>(A)» (46153-46315) at the gunsmith of its class: its parts
            -> the gun, and the text's «Переработка» experience. The «детали
            от пистолета / дробовика ...» of the start pick the class where
            one name is two guns. Only where a salvage row of the city or of
            one before it gives every part.
  decode    «Чертежи N-го уровня» (47998-48037) at the decoder (Техногик):
            the «Зашифрованный чертеж (Nу)» -> one blueprint of that level
            drawn, for a fee (DECODE_FEE of what the draw is worth, the
            prizes' mean afro price, DESIGNED: a decoded blueprint sold back
            to a stall nets no more than a tenth of its price). The
            encrypted blueprint drops in the camps of its level, from
            anybody there, for a player with the row open
            (DESIGNED chance CODIFIED_DROP, one a corpse at most); nothing
            else gives it, so a level no camp of the city holds has no row.

Beside the rows, "items": names for what the original names only in words
-- the gunsmith's parts (7924-8139, the quality and the part: «Кустарный
пистолетный ствол»), a blueprint only a recipe's start names, a
modification with no name of its own (its base gun's) -- laid under the
original's names (server/craft.py item_names), never over them; "stock":
what the craft adds to a stall the owner wrote no list for (EXTRA_STALLS,
server/craft.py stock_extra); "types": every key ever given a type.

Output is deterministic: sort_keys, indent=1, ensure_ascii=False, no dates.
"""
import collections
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
sys.path.insert(0, HERE)

import bosses          # noqa: E402
import build_orig_misc  # noqa: E402  (load_texts: the file as the other builders read it)
import craft           # noqa: E402
import items           # noqa: E402
import mobs            # noqa: E402
import names           # noqa: E402
import orig_texts      # noqa: E402
import rooms           # noqa: E402
import world           # noqa: E402

DEFAULT_SOURCE = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "questgen_weaponcraft.json")

# Each family's blocks of types, in order. A row keeps the type its key was
# given (the table's "types", number); a new key takes the next free type
# after the highest its family ever gave, and a family that runs out of
# blocks stops the build: the plan's registry (generators 10000-29999) then
# grants it another block here. 10000-10999 is this builder's. The upgrade
# recipes of the whole game's newest edition are some 490 A/G lines (123 of
# 0-8) and 12 numbered ones a [Q] gun: 600 types hold them; the older
# editions (the SMG series, the silver ones) would need another block.
FAMILIES = {"upgrade": [(10000, 10399), (10800, 10999)], "knife": [(10400, 10499)],
            "salvage": [(10500, 10599)], "assembly": [(10600, 10699)],
            "decode": [(10700, 10799)]}

# DESIGNED chances of a slot's drop (quests.py "drop"): a stat blueprint off
# a camp's chief, an encrypted one off anybody in a camp of its level --
# each group one thing a corpse at most, rolled once whatever rows the
# killers hold open (the slot's "one_of", mobs.quest_roll).
BLUEPRINT_DROP = 0.1
CODIFIED_DROP = 0.02
ONE_OF_BLUEPRINT, ONE_OF_CODIFIED = "craft_blueprint", "craft_codified"
# DESIGNED: the decoder's fee, a share of what the draw is worth -- the mean
# afro price of the row's prizes, which are drawn alike: a decoded blueprint
# sold back (inventory.SMOD 0.7) nets a tenth of its price, so an encrypted
# one is worth using, not farming. The fee was a share of the level's price
# (craft.LADDER) until the review of 2026-10-14: it is the articles' price
# for 0-12, but Донгола's 13-16 blueprints are priced 40 000 / 50 000 /
# 69 000 / 80 000 by their articles over the ladder's 35 000-50 000, and a
# decode there left 17-33 % of the prize after the sale, with no limit.
DECODE_FEE = 0.6

# A salvage class takes the broken guns from its parts' level (objects.xml
# craft_<cls>_<part>_<level>: the pistol's 2кл кустарный at 2, 3кл старый at
# 3; the rifle's 1кл at 7, 2кл at 10) up to the next class's, the lowest
# class reaching down to 0 and the highest up to TOP_LEVEL (class_levels,
# DESIGNED: the original says no more than the class).
TOP_LEVEL = 20

# The gunsmith's parts: objects.xml craft_<cls>_<part>_<level>, by class
# (the word of craft.WEAPONS), their levels by quality (кустарный, старый,
# обычный, заводской, идеальный -- pistols and shotguns have no обычный),
# and the parts, in the order texts.xml 7924-8139 lists them.
PARTS = {
    "pistol": ("pistol", (0, 1, 3, 4), (2, 3, 4, 5), ("stvol", "korpys", "usm")),
    "rifle": ("rifle", (0, 1, 2, 3, 4), (7, 10, 12, 16, 19),
              ("stvol", "lozha", "zatvor", "kazennik")),
    "shotgun": ("shotgun", (0, 1, 3, 4), (5, 6, 7, 8), ("stvol", "priklad", "cevye", "stkorobka")),
    "assault": ("assrifle", (0, 1, 2, 3, 4), (12, 13, 14, 15, 16),
                ("stvol", "priklad", "gazootvod", "stvolkorobka")),
    "smg": ("submachgun", (0, 1, 2, 3, 4), (8, 9, 10, 11, 12), ("stvol", "korpys", "usm", "zatvor")),
    "mg": ("machgun", (0, 1, 2, 3, 4), (16, 17, 18, 19, 20), ("stvol", "stkorobka", "zatrama", "priklad")),
}
# The original's words for a part, first word of its name line (7924: «Ствол
# пистолета $0M»), and of its class.
PART_WORDS = {"ствол": "stvol", "cтвол": "stvol", "корпус": "korpys", "усм": "usm",
              "ложа": "lozha", "затвор": "zatvor", "казенник": "kazennik",
              "приклад": "priklad", "цевье": "cevye", "газоотвод": "gazootvod",
              "затворная": "zatrama", "стк": None, "ствольная": None}
CLASS_WORDS = (("пистолета", "pistol"), ("винтовки", "rifle"), ("дробовика", "shotgun"),
               ("автомата", "assault"), ("пп", "smg"), ("пулемета", "mg"))
TIER_WORDS = (("кустарн", 0), ("стар", 1), ("обычн", 2), ("заводск", 3), ("идеальн", 4))
# «Разобрать сломаный <это> Nкл.» and «детали от <этого>» -- longest first.
KIND_WORDS = (("пистолет—пулемет", "smg"), ("пистолет-пулемет", "smg"), ("пулемет", "mg"),
              ("пистолет", "pistol"), ("винтовк", "rifle"), ("винтовок", "rifle"), ("дробовик", "shotgun"),
              ("автомат", "assault"))

# The original's words for a blueprint's effect -> the effect (craft.EFFECTS)
# and the stem of its blueprint's internal name.
EFFECT_WORDS = {
    "урон": "damage", "точность": "precision", "дистанция стрельбы": "shotrange",
    "время прицеливания": "aimtime", "скорость перезарядки": "reloadspeed",
    "перезарядка": "reloadspeed", "скорострельность": "shotspeed",
    "размер обоймы": "clipsize", "прочность": "attrition_x2", "ловкость": "agility",
    "восприятие": "perception", "вес": "weight",
    "урон и размер обоймы": "damage_clipsize",
    "точность и дистанция стрельбы": "precision_shotrange",
}
STEMS = {"damage": "damage", "precision": "precision", "shotrange": "shot_range",
         "aimtime": "aim_time", "reloadspeed": "reload_speed", "shotspeed": "shot_speed",
         "clipsize": "clip_size", "attrition_x2": "durability", "agility": "agility",
         "perception": "perception", "weight": "weight"}
EFFECT_TITLE = {"damage": "Урон", "precision": "Точность", "shotrange": "Дистанция стрельбы",
                "aimtime": "Время прицеливания", "reloadspeed": "Перезарядка",
                "shotspeed": "Скорострельность", "clipsize": "Размер обоймы",
                "attrition_x2": "Прочность", "agility": "Ловкость", "perception": "Восприятие",
                "weight": "Вес", "damage_clipsize": "Урон и размер обоймы",
                "precision_shotrange": "Точность и дистанция стрельбы"}
KNIFE_KINDS = (("Заточка и Эргономика", "Damage_Actionpoint", "damage_actionpoints"),
               ("Заточка", "Damage", "damage"), ("Эргономика", "Actionpoint", "actionpoint"))
# Names the original spells two ways (texts.xml 46204 «Lee-Enfield», 51833
# «Li-Enfield» and the item rows).
ALIASES = {"lee-enfield": "li-enfield", "mp-40": "mp 40"}

# The generic lines the newest edition's recipes share and write no copy of:
# «Само собой ничего не сделается.» and «Готово, пользуйся.», the notfinish
# and finish of every recipe in the older edition and on the wiki.
NOTFINISH, FINISH = 47221, 25011
SALVAGE_FINISH = 25402              # «Хм, вот что получилось тут наковырять.»
DECODE_NOTFINISH, DECODE_FINISH = 46151, 46152

# The cities. Band: the levels a row serves (its gun's, knife's, blueprint's
# level must be inside). masters: (class, line) -> who gives and takes the
# recipes; q_masters: the [Q] line's; camps: ((lo, hi), locations) of the
# faction camps whose level band drops a blueprint of that level;
# whetstones: type -> the knife levels it sharpens; gunsmiths: class ->
# type; decoder: the Техногик; stalls: class -> the blueprint stalls that
# sell the blueprints of that class's recipes of this city and of no other
# (data/npcs.json 'stock', the owner's file: --stock prints them).
CITIES = [
    dict(name="valley", band=(0, 4),
         # «Точильный камень<Br>Нубийской долины» (5192, «Караван» 186): the
         # wiki's «Заточка Самодельного ножа», «... Кухонного ножа».
         whetstones={5192: (2, 4)}),
    dict(name="halfa", band=(0, 8),
         # Вади-Хальфа's masters by their original names (texts.xml
         # 51649-51666, the wiki's quest pages): Ремесленники I (94) Ицхак
         # Уорнер A / Клара G pistols; Ремесленники II (95) Хаким A / Сэм G
         # shotguns, Шон A / Азам G rifles. The sub-machine guns' Подмастерье
         # Джерри (342) and Мастер Ракин (381) stand in no file: Ракин's
         # blueprint stall 7311 in the market (104) gives both lines,
         # DESIGNED. The (Q) Маузер of the newest edition is its A
         # apprentice's, as the text and the wiki («Маузер С96: повышение
         # урона», Подмастерье Ицхак Уорнер) have it.
         masters={("pistol", "A"): [338], ("pistol", "G"): [377], ("pistol", "Q"): [338],
                  ("shotgun", "A"): [339], ("shotgun", "G"): [378],
                  ("rifle", "A"): [341], ("rifle", "G"): [380],
                  ("smg", "A"): [7311], ("smg", "G"): [7311]},
         # The [Q] masters: the Квартал ремесленников (447, «Мастера
         # улучшения: -Оружия [Q] "Веселый праздник"», map label 5968,1719),
         # whose one upgrader of weapons is DESIGNED 5771, and Жозеф де
         # Гобино «Оружейный механик С Веселого Праздника» (7548, oasis 62).
         q_masters=[5771, 7548],
         camps=[((0, 2), (80, 82)), ((3, 4), (81, 83)), ((5, 6), (84, 86)), ((7, 8), (85, 87))],
         whetstones={2279: (6, 8)},
         # «Горные тропы: Мастера» (599): the gunsmiths «Оружейник<Br>
         # Винтовки / Дробовики / Пистолеты / Пистолет-пулеметы».
         gunsmiths={"rifle": 238, "shotgun": 239, "pistol": 242, "smg": 243},
         decoder=652,
         # The blueprint stalls, by the class their master upgrades. Not the
         # premium masters 702, 704 and 705 of the camp 124, whose stalls
         # repeated these one for one: they stand nowhere since the owner's
         # cut of (P) (2026-09-30, data/retired.json), and their lists left
         # data/npcs.json.
         stalls={"shotgun": (576, 7309), "rifle": (578, 7310), "smg": (7311,)}),
    # Абри (2026-10-12): its whetstone, «Точильный камень<Br>Абри» (2280,
    # Портовый рынок 187, texts.xml 51646), sharpens the knives of the town's
    # band its knife trader sells, Нож кастет (10у) and Штык нож (12у): the
    # wiki's «Заточка и Эргономика Нож кастета (10у)» and «... Штык ножа
    # (12у)» are on Одноухий's list. Охотничий нож (8у) is Вади-Хальфа's
    # whetstone's. No masters, camps' blueprints, gunsmiths or decoder: the
    # client has no upgrader of Абри's, and the guns of 8-12 were upgraded
    # in Вади-Хальфа and Донгола (the owner's decision 28, DESIGNED).
    dict(name="abri", band=(8, 12),
         whetstones={2280: (10, 12)}),
    # Донгола (2026-10-13, the owner's «и потом сделай донголу тоже»). Its
    # masters by their original names (texts.xml 51653-51664) in the two
    # masters' camps the map labels name: «Лагерь мастеров ... автоматов,
    # пулемётов» (96, L124) -- Подмастерье Сафи A and Мастер Самир G assault
    # rifles (dn_modif_assrifle 335, _g 382), Подмастерье Али A and Мастер
    # Гази G machine guns (345, 385) -- and «... винтовок, пистолет-
    # пулеметов» (97, L128) -- Подмастерье Санчес A and Мастер Умар G rifles
    # (346, 386), Подмастерье Басам A and Мастер Фахад G sub-machine guns
    # (347, 387). The band 9-16, DESIGNED (the owner's decision 27): the
    # masters' blueprint stalls of the original start at 9у (Фахад's), and
    # 9-12, which Абри has no master for, is served here. No shotgun master:
    # the shotguns of 9-12 (Вепрь-12, Remington ...) have nobody to upgrade
    # them. The camps whose chiefs drop the blueprints: Лагерь ДСР (93) and
    # its chiefs' second cell (91) 12-14, Лагерь Миротворцев (98, 99) 15-16,
    # by their labels' «12-14» and «14-16» without the overlap. The
    # whetstone «Точильный камень<Br>Донголы» (2281, the black market 103)
    # sharpens Боевой нож (14у) and Такоуба (16у), the knives of the town's
    # band Одноногий sells beside it (his article: «Заточка и Эргономика
    # Боевого ножа (14у)», «... Такоубы (16у)»). The gunsmiths «Оружейник<Br>
    # Винтовки / Пулеметы / Автоматы / Пистолет-пулеметы» of «Горные тропы»
    # (625; 244, 246, 247, 249), the decoder Техногик (651, the black
    # market). The blueprint stalls of the markets 50 and 197 by their
    # internal names: dn_trmodif_assrifle_g (580, «Мастер Самир»),
    # _machingun_g (583, «Мастер Гафур»), _rifle_g (584, «Мастер Умар»),
    # _submachgun_g (585, «Мастер Фахад»).
    dict(name="dongola", band=(9, 16),
         masters={("assault", "A"): [335], ("assault", "G"): [382],
                  ("mg", "A"): [345], ("mg", "G"): [385],
                  ("rifle", "A"): [346], ("rifle", "G"): [386],
                  ("smg", "A"): [347], ("smg", "G"): [387]},
         camps=[((12, 14), (93, 91)), ((15, 16), (98, 99))],
         whetstones={2281: (14, 16)},
         gunsmiths={"rifle": 244, "mg": 246, "assault": 247, "smg": 249},
         decoder=651,
         stalls={"assault": (580,), "mg": (583,), "rifle": (584,), "smg": (585,)}),
    # Абу-Хамед (2026-10-14, the owner's «сделай потом абу хамед в таком же
    # формате»), the band 17-20, DESIGNED (the owner's decision 34): 16 is
    # Донгола's. Its masters by their original names (texts.xml 51671-51680)
    # in «Лагерь мастеров: улучшение оружия (A)» (131, L161) and the living
    # quarter's «Мастера (G)» (127, L156): Подмастерье Имран A
    # (ah_modif_assrifle 755) and Мастер Гияс G (ah_trmodif_assrifle_g 748)
    # assault rifles; Подмастерье Камаль A (ah_modif_machingun 758) and
    # Мастер Заки G (751) machine guns; Подмастерье Катада A (ah_modif_rifle
    # 759) and Мастер Зияд G (752) rifles; Подмастерье Гринефилд A
    # (ah_trmodif_submachgun 4583) and Мастер Корлу G (753) sub-machine guns;
    # Подмастерье Вася A (ah_trmodif_pistol 4584) and Мастер Аншан G (749)
    # pistols. The client has no ah_modif_*_g: the (G) types are traders
    # (ah_trmodif_*_g, root 1), what Донгола's blueprint stalls 580/583-585
    # are, while Донгола's (G) masters are others (382, 385-387). So here
    # the trader (G) of a class both upgrades and sells its blueprints,
    # DESIGNED. No pistol or sub-machine gun of 17-20 has the wiki's table
    # (Thompson M1928 is 15у), so those four keys make no row. The camps
    # whose chiefs drop the blueprints: Лагерь Пиратов Сомали (132) and its
    # chief's cell (133) with the Аванпост Северного Альянса (168) 17-18, by
    # their labels' «16+» and «16-18» less Донгола's 16; the База Северного
    # Альянса (263) and its chief's cell (274) 19-20, its label's «19-20».
    # «Точильный камень<Br>Абу-Хамеда» (2282, the station 126, texts.xml
    # 51648) sharpens Кукри (18у) and Мачете (20у), the knives of the town's
    # band Шрам sells beside it (his article: «Заточка и Эргономика Кукри
    # (18у)», «... Мачете (20у)»); Такоуба (16у) is Донгола's whetstone's.
    # The gunsmiths «Оружейник<Br>Винтовки / Пулеметы / Автоматы» of «Горные
    # тропы: Мастера» (624; 730, 732, 733), the decoder Техногик (796, the
    # living quarter, 46942 «Техногик<Br>расшифровка чертежей»).
    dict(name="abu_hamed", band=(17, 20),
         masters={("assault", "A"): [755], ("assault", "G"): [748],
                  ("mg", "A"): [758], ("mg", "G"): [751],
                  ("rifle", "A"): [759], ("rifle", "G"): [752],
                  ("smg", "A"): [4583], ("smg", "G"): [753],
                  ("pistol", "A"): [4584], ("pistol", "G"): [749]},
         camps=[((17, 18), (132, 133, 168)), ((19, 20), (263, 274))],
         whetstones={2282: (18, 20)},
         gunsmiths={"rifle": 730, "mg": 732, "assault": 733},
         decoder=796,
         stalls={"assault": (748,), "mg": (751,), "rifle": (752,)}),
]

# What the craft adds to a stall with no list of the owner's (the table's
# "stock", server/craft.py stock_extra, after the wiki's list): the
# quarter's trader (5770) the [Q] line's blueprints; Однопальцый (1152, the
# black market) the blueprints of the whetstones named and the (G) knives
# of those whose knives no stall of their town sells -- Вади-Хальфа's Тесак
# and Охотничий нож (G) were the valley's Одноглазый's alone (5222, behind
# the valley's way back, max_level 2). Одноглазый keeps his knife line
# (server/test_shops.py holds his list): the valley's 2у/4у blueprints are
# the owner's to add there.
Q_STALL = 5770
EXTRA_STALLS = {1152: dict(blueprints=(5192, 2279), knives=(2279,))}
# The knife stalls whose list is the owner's file's (data/npcs.json 'stock',
# --stock prints it), by the whetstones whose blueprints they sell:
# Одноухий (1164, Абри's port market) Абри's whetstone's (2280). His list
# in the file is these and after them the gypsum, wire and bandages of
# Марис Дамбис's chain («торговец ножами ... знатным костоправом», texts.xml
# 49186), which are no craft's -- so a list of his own, which the table's
# "stock" (EXTRA_STALLS) would not reach. His knives are Абри's band's
# (data/shop_bands.json). Одноногий (1153, Донгола's black market) Донгола's
# whetstone's (2281), his whole list in the file; his knives are Донгола's
# band's. Шрам (2274, Абу-Хамед's station) Абу-Хамед's whetstone's (2282),
# his whole list in the file (his article named two of the six); his
# knives are Абу-Хамед's band's.
KNIFE_STALLS = {1164: (2280,), 1153: (2281,), 2274: (2282,)}


# --- the tables of the game -------------------------------------------------------------
CAT = items.catalogue()
BY_NAME = {}
for _t, (_r, _n) in sorted(CAT.items()):
    BY_NAME.setdefault(_n, _t)
RAW = {int(k): v for k, v in orig_texts._ITEMS.items()}
WIKI = items.wiki()
_ITEM_NAME = re.compile(r"^(.*?)\s*\[([A-Z]+)\]\s*\[(\d+)\]\s*\$(.*)$")

GUNS = collections.defaultdict(list)
for _t, (_r, _n) in CAT.items():
    if _r != items.FIRE_ARM or "_mod_" in _n:
        continue
    _m = _ITEM_NAME.match((RAW.get(_t) or {}).get("name") or "")
    if _m:
        GUNS[(_m.group(1).strip().lower(), _m.group(2), int(_m.group(3)))].append(_t)
# (class, level) -> the guns a bench may take (craft.salvageable).
BENCH = collections.defaultdict(list)
for _t, (_r, _n) in sorted(CAT.items()):
    _s = craft.salvageable(_t) if _r == items.FIRE_ARM else None
    if _s:
        BENCH[_s].append(_t)

report = collections.defaultdict(list)


def clean(text):
    """A line as the client gets it (orig_texts.text), cut to its Russian:
    the older edition follows it with «—————» and an English and a Ukrainian
    copy."""
    text = re.split(r"(?:<Br>|<hint>)*—{5,}", text)[0]
    return orig_texts.text(text).strip()


def servable(t):
    """A thing a row may name: the game has it, and it is not premium."""
    return t is not None and items.params_of(t) is not None and not items.premium(t)


def line_of(t):
    name = CAT[t][1]
    if name.endswith("_gold"):
        return "G"
    m = _ITEM_NAME.match((RAW.get(t) or {}).get("name") or "")
    return m.group(2) if m else "A"


def resolve_gun(name, line, level, weapon=None):
    """(type, line) of a gun the original names, or (None, why)."""
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    if name.strip() in BY_NAME and items.root_of(BY_NAME[name.strip()]) == items.FIRE_ARM:
        t = BY_NAME[name.strip()]
        return t, line_of(t)
    cands, got_line = GUNS.get((key, line, level), []), line
    if not cands and line == "A":
        cands, got_line = GUNS.get((key, "Q", level), []), "Q"
    if weapon:
        cands = [t for t in cands if craft.weapon_of(t) == weapon]
    real = [t for t in cands if t in WIKI]
    if len(real) != 1:
        return None, "%s [%s][%s]: %s" % (name, line, level, "no gun with the wiki's table"
                                           if not real else "two guns with tables %s" % real)
    return real[0], got_line


def mod_type(gun, effect):
    stem = CAT[gun][1]
    gold = stem.endswith("_gold")
    if gold:
        stem = stem[:-len("_gold")]
    return BY_NAME.get("%s_mod_%s%s" % (stem, effect, "_gold" if gold else ""))


def blueprint(effect, level, line, numbered=False):
    if effect == "damage_clipsize":
        name = ("bpb_damage_clipsize_lvl%d" % level if numbered else
                "bpg_damage_25_%s_lvl%d" % ("gold" if line == "G" else "afro", level))
    elif effect == "precision_shotrange":
        name = "bpb_precision_shotrange_lvl%d" % level
    else:
        name = "bpg_%s_lvl%d" % (STEMS[effect], level)
    return BY_NAME.get(name)


def effect_of(words):
    return EFFECT_WORDS.get(re.sub(r"\s+", " ", words.strip().lower().rstrip(".")))


# --- the camps ---------------------------------------------------------------------------------
_STANDING = {}


def standing(loc_id):
    """The types standing in a location, as the server puts them down."""
    if loc_id not in _STANDING:
        room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), world.mob_types())
        _STANDING[loc_id] = sorted({npc[1] for npc in room.npcs.values()})
    return _STANDING[loc_id]


def camp_mobs(city, level, chiefs_only):
    """The hostiles of the city's camps whose band holds level: their chiefs
    (a boss that keeps the hours, not a treasurer standing all day), or all
    who fight there."""
    out = set()
    for (lo, hi), locs in city.get("camps", ()):
        if not lo <= level <= hi:
            continue
        for loc in locs:
            for t in standing(loc):
                role = mobs.stats(t).role
                if role == "boss" and t not in bosses.ALL_DAY:
                    out.add(t)
                elif role == "mob" and not chiefs_only:
                    out.add(t)
    return sorted(out)


def in_band(city, level):
    lo, hi = city["band"]
    return level is not None and lo <= level <= hi


def service(city, row):
    """The keys every craft row has."""
    lo, hi = city["band"]
    row.update(repeatable=1, service=True, level=lo, max_level=hi)
    return row


def row_key(fam, city, line):
    """A row's key (number): its family, its city and the texts.xml line of
    its name -- what a rebuild finds the row by, wherever it now falls in
    the original's order."""
    return "%s:%s:%d" % (fam, city["name"], line)


# --- the families ----------------------------------------------------------------------------
_START = re.compile(r"^Хочешь улучшить свое оружие\? Мне нужен соответствующий чертеж и, "
                    r"собственно, само оружие\.<Br><b>Задача:</b> принести (?P<gun>.+?) и "
                    r"Чертеж: (?P<bp>[^<(]+?) \((?P<lvl>\d+)у\)<Br>")
_NAME = re.compile(r"^(?P<gun>.+?)\s*: (?P<eff>[^:<>]+?)\s*$")
_VARIANT = re.compile(r"^(?P<base>.+?)\s*\((?P<v>G|P)\)$")
_NUMBERED = re.compile(r"№B\d+.*?принести (?P<gun>[^<\[]+?)\[(?P<v>[A-Z]+)\]\[(?P<lvl>\d+)\] и "
                       r"Чертеж: (?P<bp>[^<\[]+?) \[(?P<blvl>\d+)у\]", re.S)


def upgrade_rows(city, texts):
    """The recipes of a city's band: the newest edition's pairs, then the
    numbered [Q] ones for its q_masters."""
    out = []
    for i in sorted(texts) if city.get("masters") else ():
        m = _START.match(texts[i])
        n = _NAME.match(texts.get(i - 1, ""))
        if not m or not n:
            continue
        level, gun_words = int(m.group("lvl")), n.group("gun").strip()
        if "[" in gun_words:
            continue                            # a clan's gun («HK121 [19](G)Blackwater»)
        v = _VARIANT.match(gun_words)
        line = v.group("v") if v else "A"
        if line == "P" or not in_band(city, level):
            continue
        base_name = v.group("base") if v else gun_words
        effect = effect_of(m.group("bp"))
        if effect is None:
            report["upgrade"].append("%d: blueprint words %r" % (i, m.group("bp")))
            continue
        gun, got_line = resolve_gun(base_name, line, level)
        if gun is None:
            report["upgrade"].append("%d %s: %s" % (i - 1, texts[i - 1], got_line))
            continue
        cls = craft.weapon_of(gun)
        givers = city.get("masters", {}).get((cls, got_line if got_line != "A" else line), [])
        row = recipe_row(city, gun, got_line, effect, level, givers,
                         (i - 1, i, NOTFINISH, FINISH), texts, numbered=False)
        if row:
            out.append(row)
    if city.get("q_masters"):
        for i in sorted(texts):
            if "Хочешь улучшить свое оружие" not in texts[i]:
                continue
            m = _NUMBERED.search(texts[i])
            if not m or m.group("v") != "Q" or not in_band(city, int(m.group("lvl"))):
                continue
            level = int(m.group("blvl"))
            gun, got_line = resolve_gun(m.group("gun"), "Q", int(m.group("lvl")))
            if gun is None:
                report["upgrade [Q]"].append("%d %s: %s" % (i - 1, texts[i - 1], got_line))
                continue
            effect = effect_of(m.group("bp"))
            row = recipe_row(city, gun, got_line, effect, level, city["q_masters"],
                             (i - 1, i, i + 1, FINISH), texts, numbered=True)
            if row:
                out.append(row)
    return out


def recipe_row(city, gun, line, effect, level, givers, ids, texts, numbered):
    """One recipe: the gun and its blueprint -> the modification."""
    mod = mod_type(gun, effect)
    bp = blueprint(effect, level, line, numbered)
    why = "%d %s" % (ids[0], texts[ids[0]])
    if not givers:
        report["upgrade"].append("%s: no master of %s [%s] in %s"
                                 % (why, craft.weapon_of(gun), line, city["name"]))
        return None
    if not servable(mod):
        report["upgrade"].append("%s: no modification %s" % (why, effect))
        return None
    if not servable(bp):
        report["upgrade"].append("%s: no blueprint %s (%dу)" % (why, effect, level))
        return None
    ceiling = (items.params_of(gun)["max_break_abs"], items.params_of(mod)["max_break_abs"])
    if ceiling[1] < ceiling[0]:
        # An upgrade keeps the gun's wear as a share of its ceiling
        # (setcraft.worn_as): a modification its article gives a lower
        # ceiling than its gun's would come out more worn, a gun worn by a
        # point broken. The article's slip -- AUG /Hbar Mod VIII's «повышение
        # прочности» at 550 against the gun's 2750 (its (G) copy's 5500) --
        # makes no row, DESIGNED.
        report["upgrade"].append("%s: the modification's wear ceiling %d under the gun's %d"
                                 % (why, ceiling[1], ceiling[0]))
        return None
    slot = {"obj": bp, "num": 1}
    chiefs = camp_mobs(city, level, chiefs_only=True)
    if chiefs:
        slot.update(mobs=chiefs, drop=BLUEPRINT_DROP, one_of=ONE_OF_BLUEPRINT)
    name, start = clean(texts[ids[0]]), clean(texts[ids[1]])
    internal = CAT[gun][1]
    if internal in name:
        # The file's own slip: a recipe that names its gun by the internal
        # name (58983-58990, «shotgun_1_lvl_8: время прицеливания»), read
        # as the gun's name, the wiki's «Jackhammer: ...». DESIGNED.
        shown = names.text(items.STRING_ID_OFFSET + gun).split("$")[0]
        name, start = name.replace(internal, shown), start.replace(internal, shown)
    return service(city, dict(
        kind="bring_l_obj", name=name, start=start,
        notfinish=clean(texts[ids[2]]), finish=clean(texts[ids[3]]),
        give=list(givers), take=list(givers),
        objs=[{"obj": gun, "num": 1}, slot], rew_obj=[mod], num_rew_obj=[1],
        craft={"family": "upgrade", "gun": gun, "mod": mod, "blueprint": bp,
               "effect": effect, "line": line, "level": level,
               "key": row_key("upgrade", city, ids[0])},
        why="RECOVERED: texts.xml %s (name, start, notfinish, finish), the gun %d, its "
            "modification %d, the blueprint %d (%dу). DESIGNED: the band %s-%s of %s, the "
            "blueprint's drop off the camps' chiefs of its level."
            % (list(ids), gun, mod, bp, level, city["band"][0], city["band"][1], city["name"])))


_KNIFE_START = re.compile(r"<b>Задача:</b>\s*Принести (?P<knife>.+?) и Чертеж: (?P<bp>.+?)\s*<Br>")


def knife_rows(city, texts):
    """The whetstones' sharpening: the knife (G) and its blueprint -> its
    modification."""
    out = []
    knives = {}
    for t, (r, n) in CAT.items():
        m = re.match(r"^knife_lvl(\d+)_G$", n)
        if r == items.COLD_ARM and m:
            knives[int(m.group(1))] = t
    shown = {re.sub(r"\s+\(", " (", names.text(items.STRING_ID_OFFSET + t).split("$")[0]).lower(): lvl
             for lvl, t in knives.items()}
    for i in sorted(texts):
        m = _KNIFE_START.search(texts[i])
        if not m or "Точильный круг" not in texts[i] and "рукоят" not in texts[i]:
            continue
        level = shown.get(re.sub(r"\s*\(", " (", m.group("knife").strip()).lower())
        if level is None:
            continue
        kind = [k for k in KNIFE_KINDS if m.group("bp").startswith(k[0])][0]
        givers = [w for w, lvls in city.get("whetstones", {}).items() if level in lvls]
        if not givers or not in_band(city, level):
            continue
        knife = knives[level]
        bp = BY_NAME.get("bpg_knife_lvl%d_%s" % (level, kind[1]))
        mod = BY_NAME.get("knife_lvl%d_G_%s" % (level, kind[2]))
        if not (servable(bp) and servable(mod)):
            report["knife"].append("%d: %s" % (i, texts[i - 1]))
            continue
        out.append(service(city, dict(
            kind="bring_l_obj", name=clean(texts[i - 1]), start=clean(texts[i]),
            notfinish=clean(texts[NOTFINISH]), finish=clean(texts[FINISH]),
            give=givers, take=givers,
            objs=[{"obj": knife, "num": 1}, {"obj": bp, "num": 1}], rew_obj=[mod],
            num_rew_obj=[1],
            craft={"family": "knife", "gun": knife, "mod": mod, "blueprint": bp,
                   "level": level, "key": row_key("knife", city, i - 1)},
            why="RECOVERED: texts.xml %d-%d, the wiki's «%s» at the whetstone; the "
                "generic notfinish %d and finish %d the wiki gives every recipe."
                % (i - 1, i, texts[i - 1], NOTFINISH, FINISH))))
    return out


def part_table(texts):
    """(class, part, level) -> (type, the original's words for it), off
    texts.xml 7924-8139: the name line («Ствол пистолета $0M»: the part, the
    class, the quality) and its words («Кустарный пистолетный ствол»)."""
    out = {}
    for i in range(7924, 8140, 2):
        head, words = texts[i], texts[i + 1]
        m = re.match(r"^(.+?)\s*\$(\d)", head)
        if not m:
            continue
        first = m.group(1).split()[0].lower()
        part = PART_WORDS.get(first)
        cls = [c for w, c in CLASS_WORDS if w in m.group(1).lower().split()]
        if not cls:
            continue
        cls = cls[0]
        if first == "стк":
            part = "stvolkorobka" if cls == "assault" else "stkorobka"
        stem, tiers, levels, parts = PARTS[cls]
        tier = int(m.group(2))
        if part not in parts or tier not in tiers:
            continue
        level = levels[tiers.index(tier)]
        t = BY_NAME.get("craft_%s_%s_%d" % (stem, part, level))
        if t is not None:
            out[(cls, part, level)] = (t, orig_texts.text(words).replace("—", "-"), i)
    return out


def tier_of(word):
    for stem, tier in TIER_WORDS:
        if word.lower().startswith(stem):
            return tier
    return None


def kind_of(text):
    low = text.lower()
    for word, cls in KIND_WORDS:
        if word in low:
            return cls
    return None


def class_levels(cls, k, classes):
    """(its parts' level, lo, hi) of a weapon's salvage class k, classes
    the weapon's classes: it takes the guns from its parts' level up to the
    next class's, the lowest class down to 0 and the highest up to
    TOP_LEVEL (DESIGNED)."""
    levels, ks = PARTS[cls][2], sorted(classes)
    j = ks.index(k)
    lo = 0 if j == 0 else levels[j]
    hi = levels[j + 1] - 1 if j + 1 < len(ks) else TOP_LEVEL
    return levels[j], lo, hi


# What the bench takes, said where the player reads the row (DESIGNED
# words, server/craft.py _broken).
SALVAGE_NOTE = ("<Br><Br><b>Внимание:</b> на верстак пойдёт самое дешёвое сломанное оружие "
                "этого класса %d-%d уровня из рюкзака. Золотое, улучшенное и выданное по "
                "заданию оружие не разбирается.")


def salvage_rows(city, texts, parts, placed):
    """The gunsmiths' salvage of broken guns, by class: each class once, at
    the first city with gunsmiths whose band holds its parts' level (placed:
    the lines a city before took), and only where a gun a bench may take
    (craft.salvageable) falls in its levels."""
    out = []
    classes = collections.defaultdict(list)
    heads = {}
    for i in range(25400, 25457):
        m = re.match(r"^Разобрать сломан\w+ (.+?) (\d)кл\.?$", texts[i])
        if m:
            cls = kind_of(m.group(1))
            classes[cls].append(int(m.group(2)))
            heads[(cls, int(m.group(2)))] = i
    for (cls, k), i in sorted(heads.items(), key=lambda kv: kv[1]):
        level, lo, hi = class_levels(cls, k, classes[cls])
        if i in placed or not city.get("gunsmiths") or not in_band(city, level):
            continue
        smith = city["gunsmiths"].get(cls)
        if smith is None:
            report["salvage"].append("%d %s: no gunsmith of that class in %s"
                                     % (i, texts[i], city["name"]))
            continue
        if not any(BENCH.get((cls, n)) for n in range(lo, hi + 1)):
            report["salvage"].append("%d %s: no gun a bench may take in levels %d-%d"
                                     % (i, texts[i], lo, hi))
            continue
        placed.add(i)
        kinds = PARTS[cls][3]
        drawn = [parts[(cls, p, level)][0] for p in kinds if (cls, p, level) in parts]
        start = texts[i + 1]
        fee = int(re.search(r"сбор в размере (\d+) афро", start).group(1))
        xp = int(re.search(r"опыта (\d+) единиц", start).group(1))
        out.append(service(city, dict(
            kind="del_obj", obj=0, name=clean(texts[i]),
            start=clean(start) + SALVAGE_NOTE % (lo, hi),
            notfinish="", finish=clean(texts[SALVAGE_FINISH]),
            give=[smith], take=[smith], cost_afro=fee,
            rew_random=[{"obj": t, "num": 1, "w": 1} for t in drawn],
            rew_spec_xp={"recycling": xp},
            craft={"family": "salvage", "weapon": cls, "class": k, "levels": [lo, hi],
                   "key": row_key("salvage", city, i)},
            why="RECOVERED: texts.xml %d-%d and the finish %d; the fee %d afro and %d "
                "«Переработка» the text's; one part of the class drawn, those the text lists "
                "(7924-8139, level %d). DESIGNED: the gunsmith of the class stands for the "
                "bench («На этом верстаке»); class %d takes a broken gun of levels %d-%d, "
                "from its parts' level up to the next class's, the cheapest in the bag and "
                "never a gold, modified or lent one, as the start's last line says."
                % (i, i + 1, SALVAGE_FINISH, fee, xp, level, k, lo, hi))))
    return out


_ASSEMBLY = re.compile(r"принести \d+ детал\w*: (?P<parts>[^<]+?)\s*<Br>")


def assembly_rows(city, texts, parts, given):
    """The gunsmiths' assembly of a gun out of its parts: only where every
    part is one a salvage row of the city or of one before it draws (given)."""
    out = []
    for i in range(46153, 46316):
        head = texts[i]
        m = re.match(r"^(?P<gun>[^<>]+?)\s*\((?P<v>[AGP])\)$", head)
        start = texts.get(i + 1, "")
        a = _ASSEMBLY.search(start)
        if not m or not a:
            continue
        if m.group("v") != "A":
            continue
        cls = kind_of(re.search(r"детали от ([^,.<]+)", start).group(1)) \
            if re.search(r"детали от ([^,.<]+)", start) else None
        cands = [t for (k, line, _lvl), ts in GUNS.items()
                 if k == ALIASES.get(m.group("gun").strip().lower(), m.group("gun").strip().lower())
                 and line == "A" for t in ts if t in WIKI and craft.weapon_of(t) == cls]
        if not city.get("gunsmiths"):
            continue
        if len(cands) != 1:
            report["assembly"].append("%d %s: %s" % (i, head, "no A gun of the class with the "
                                                     "wiki's table" if not cands else cands))
            continue
        gun = cands[0]
        level = craft.gun_level(gun)
        if not in_band(city, level):
            continue
        smith = city["gunsmiths"].get(cls)
        if smith is None:
            report["assembly"].append("%d %s: no gunsmith of that class in %s"
                                      % (i, head, city["name"]))
            continue
        stem, tiers, levels, _kinds = PARTS[cls]
        wanted, bad = collections.Counter(), []
        for words in a.group("parts").split(","):
            w = words.split()
            tier = tier_of(w[0]) if w else None
            part = PART_WORDS.get(w[1].lower()) if len(w) > 1 else None
            if len(w) > 1 and w[1].lower() in ("стк", "ствольная"):
                part = "stvolkorobka" if cls == "assault" else "stkorobka"
            if tier is not None and tier not in tiers:
                # A quality the class has no part of (a pistol's or a
                # shotgun's «Обычный»): the part of the level nearest the
                # gun's own. DESIGNED.
                tier = min(tiers, key=lambda k: (abs(levels[tiers.index(k)] - level), k))
            if tier is None or part is None \
                    or (cls, part, levels[tiers.index(tier)]) not in parts:
                bad.append(words.strip())
                continue
            wanted[parts[(cls, part, levels[tiers.index(tier)])][0]] += 1
        if bad:
            report["assembly"].append("%d %s: parts %s" % (i, head, bad))
            continue
        missing = sorted(t for t in wanted if t not in given)
        if missing:
            report["assembly"].append("%d %s: parts no salvage row gives %s"
                                      % (i, head, ["%d %s" % (t, CAT[t][1]) for t in missing]))
            continue
        xp = re.search(r"опыта (\d+) единиц", start)
        finish = texts.get(i + 2, "")
        row = dict(
            kind="bring_l_obj", name=clean(head),
            # The file's own slip, «Задачадвоеточие» (the colon's name
            # written out), read as what it stands for.
            start=clean(start.replace("Задачадвоеточие", "Задача:")),
            notfinish=clean(texts[NOTFINISH]),
            finish=clean(finish) if finish.startswith("Отлично") else "",
            give=[smith], take=[smith],
            objs=[{"obj": t, "num": n} for t, n in sorted(wanted.items())],
            rew_obj=[gun], num_rew_obj=[1],
            craft={"family": "assembly", "gun": gun, "weapon": cls,
                   "key": row_key("assembly", city, i)},
            why="RECOVERED: texts.xml %d-%d, the parts the start names (7924-8139), the gun %d. "
                "DESIGNED: the gunsmith of the class, the generic notfinish %d."
                % (i, i + 2, gun, NOTFINISH))
        if xp:
            row["rew_spec_xp"] = {"recycling": int(xp.group(1))}
        out.append(service(city, row))
    return out


def decode_rows(city, texts, upgrades):
    """The decoder's «Чертежи N-го уровня»."""
    out = []
    if not city.get("decoder"):
        return out
    used = collections.defaultdict(set)
    for r in upgrades:
        if r["craft"]["effect"] in STEMS:
            used[r["craft"]["level"]].add(r["craft"]["blueprint"])
    for i in range(47998, 48038, 2):
        m = re.match(r"^Чертежи (\d+)-го уровня$", texts[i])
        if not m:
            continue
        level = int(m.group(1))
        if not in_band(city, level):
            continue
        codified = BY_NAME.get("codified_bp_%d" % level)
        named = {BY_NAME[n] for n in ("bpg_%s_lvl%d" % (s, level) for s in STEMS.values())
                 if n in BY_NAME and items.STRING_ID_OFFSET + BY_NAME[n]
                 in names.ORIG_ITEM_NAMES}
        prizes = sorted(t for t in used[level] | named if servable(t))
        if not servable(codified) or not prizes:
            report["decode"].append("%d %s: nothing to draw" % (i, texts[i]))
            continue
        dropping = camp_mobs(city, level, chiefs_only=False)
        if not dropping:
            # Nothing else gives the encrypted blueprint (no loot table,
            # no stall): a row for it could never be done. Донгола's
            # 9-11, whose levels no camp of the town holds.
            report["decode"].append("%d %s: no camp of %s drops it"
                                    % (i, texts[i], city["name"]))
            continue
        slot = {"obj": codified, "num": 1,
                "mobs": dropping, "drop": CODIFIED_DROP, "one_of": ONE_OF_CODIFIED}
        # What the draw is worth: the prizes' mean afro price (drawn alike,
        # w 1 each, below). Rounded up, so the sale never nets past a tenth.
        worth = sum(items.params_of(t)["cost"] for t in prizes) / float(len(prizes))
        fee = int(math.ceil(round(worth * DECODE_FEE, 6)))
        out.append(service(city, dict(
            kind="bring_l_obj", name=clean(texts[i]),
            # The fee said the way the original says its own («Внимание: с
            # вашего счёта будет списано ...», 25399): DESIGNED words.
            start=clean(texts[i + 1]) + "<Br><Br><b>Внимание:</b> с вашего счёта будет "
                                        "списано %d афро." % fee,
            notfinish=clean(texts[DECODE_NOTFINISH]), finish=clean(texts[DECODE_FINISH]),
            give=[city["decoder"]], take=[city["decoder"]],
            cost_afro=fee,
            objs=[slot],
            rew_random=[{"obj": t, "num": 1, "w": 1} for t in prizes],
            craft={"family": "decode", "level": level, "key": row_key("decode", city, i)},
            why="RECOVERED: texts.xml %d-%d, the notfinish %d and finish %d (the Техногик's "
                "lines). DESIGNED: one blueprint of the level drawn (the ones the city's "
                "recipes ask for and the ones the original names), the fee %d%% of the "
                "prizes' mean price and its line in the start, the drop off the camps of the "
                "level."
                % (i, i + 1, DECODE_NOTFINISH, DECODE_FINISH, int(DECODE_FEE * 100)))))
    return out


# --- the table ------------------------------------------------------------------------------
def build(texts, types=None):
    """{"quests": rows, "items": names, "stock": additions, "types": every
    key's type} for every city, and the report. types: the keys given a type
    so far, the table's on disk unless said."""
    if types is None:
        types = load_types()
    parts = part_table(texts)
    fams = collections.OrderedDict((f, []) for f in FAMILIES)
    placed, given = set(), set()
    for city in CITIES:
        ups = upgrade_rows(city, texts)
        fams["upgrade"] += ups
        fams["knife"] += knife_rows(city, texts)
        salvage = salvage_rows(city, texts, parts, placed)
        fams["salvage"] += salvage
        given |= {o["obj"] for r in salvage for o in r["rew_random"]}
        fams["assembly"] += assembly_rows(city, texts, parts, given)
        fams["decode"] += decode_rows(city, texts, ups)
    rows, types = number(fams, types)
    return {"_": __doc__.split("\n\n")[0], "quests": rows,
            "items": item_table(rows, parts), "stock": extra_stock(rows),
            "types": types}


def load_types():
    """The table's "types" on disk: every key ever given a type."""
    try:
        with open(OUT, encoding="utf-8") as fh:
            return {k: int(v) for k, v in (json.load(fh).get("types") or {}).items()}
    except FileNotFoundError:
        return {}


def number(fams, types):
    """(the rows with their types, sorted; every key's type): a row keeps
    the type its key had, and a new key takes the next type after the
    highest its family ever gave, inside the family's blocks (FAMILIES). A
    line the original's order puts between two old ones moves nobody, and a
    row gone leaves its type unused, never given again."""
    types = dict(types)
    rows, seen = [], set()
    for fam, got in fams.items():
        blocks = FAMILIES[fam]
        mine = [t for k, t in types.items() if k.split(":", 1)[0] == fam]
        for row in got:
            k = row["craft"]["key"]
            if k in seen:
                raise SystemExit("two rows of one key %s" % k)
            seen.add(k)
            if k not in types:
                t = max(mine) + 1 if mine else blocks[0][0]
                for lo, hi in blocks:
                    if t <= hi:
                        t = max(t, lo)
                        break
                else:
                    raise SystemExit("family %s is out of types %s: the plan's registry must "
                                     "grant it another block (FAMILIES)" % (fam, blocks))
                types[k] = t
                mine.append(t)
            rows.append(dict(type=types[k], **row))
    return sorted(rows, key=lambda r: r["type"]), types


def item_table(rows, parts):
    """Names for the things the rows name that the original names only in
    words, never over its own names."""
    out = {}
    orig = set(orig_texts.item_names())
    for (_cls, _part, _lvl), (t, words, i) in sorted(parts.items(), key=lambda kv: kv[1][0]):
        if t not in orig:
            out[str(t)] = {"name": words,
                           "why": "RECOVERED: texts.xml %d-%d; the words line (quality and part) "
                                  "for the name, DESIGNED." % (i, i + 1)}
    for r in rows:
        rec = r["craft"]
        bp = rec.get("blueprint")
        if bp and bp not in orig and not items.wiki().get(bp) and rec.get("effect"):
            out[str(bp)] = {"name": "%s (%dу)$BP" % (EFFECT_TITLE[rec["effect"]], rec["level"]),
                            "why": "DESIGNED: the recipe's own words for its blueprint, as the "
                                   "original names the blueprints it does name."}
        mod = rec.get("mod")
        if mod and mod not in orig and not items.wiki().get(mod):
            out[str(mod)] = {"name": names.text(items.STRING_ID_OFFSET + rec["gun"]),
                             "why": "DESIGNED: the base gun's name; the original names a "
                                    "modification as its gun."}
    return out


def city_of(row):
    """The name of the city a row was written for, off its key (row_key)."""
    return row["craft"]["key"].split(":")[1]


def stock(doc):
    """The blueprint stalls' lists for data/npcs.json (--stock): each city's
    stalls (CITIES' stalls) the blueprints of its own masters' recipes of
    their class, by level -- never another city's, whose levels are another
    band; a knife stall's (KNIFE_STALLS) its whetstones' blueprints, the
    head of its list there."""
    out = {}
    rows = doc["quests"]
    for city in CITIES:
        for cls, stalls in city.get("stalls", {}).items():
            got = []
            for r in rows:
                c = r["craft"]
                if c["family"] == "upgrade" and c["line"] in ("A", "G") \
                        and city_of(r) == city["name"] \
                        and craft.weapon_of(c["gun"]) == cls and c["blueprint"] not in got:
                    got.append(c["blueprint"])
            got.sort(key=lambda t: (int(re.search(r"lvl(\d+)$", CAT[t][1]).group(1)), t))
            for s in stalls:
                out[s] = got
    for s, stones in KNIFE_STALLS.items():
        out[s] = sorted({r["craft"]["blueprint"] for r in rows
                         if r["craft"]["family"] == "knife" and set(stones) & set(r["give"])})
    return out


def extra_stock(rows):
    """The table's "stock": trader -> what the craft adds to his stall (the
    wiki's list, where the owner wrote none): the [Q] line's blueprints at
    Q_STALL, in the order of the rows; at EXTRA_STALLS the (G) knives and
    then the blueprints of the whetstones named."""
    q = []
    for r in rows:
        c = r["craft"]
        if c["family"] == "upgrade" and c["line"] == "Q" and c["blueprint"] not in q:
            q.append(c["blueprint"])
    out = {str(Q_STALL): q} if q else {}
    knife = [r for r in rows if r["craft"]["family"] == "knife"]
    for trader, spec in EXTRA_STALLS.items():
        knives = {r["craft"]["gun"] for r in knife if set(spec["knives"]) & set(r["give"])}
        prints = {r["craft"]["blueprint"] for r in knife
                  if set(spec["blueprints"]) & set(r["give"])}
        out[str(trader)] = sorted(knives) + sorted(prints)
    return out


def main():
    source = os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_SOURCE
    texts, _md5, _size = build_orig_misc.load_texts(source)
    doc = build(texts)
    if "--stock" in sys.argv:
        print(json.dumps({str(k): v for k, v in stock(doc).items()}, indent=1))
        return
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    fams = collections.Counter(r["craft"]["family"] for r in doc["quests"])
    print("%d rows -> %s: %s" % (len(doc["quests"]), OUT, dict(fams)), file=sys.stderr)
    for fam, lines in sorted(report.items()):
        print("left out, %s: %d" % (fam, len(lines)), file=sys.stderr)
        for line in lines:
            print("   " + line, file=sys.stderr)


if __name__ == "__main__":
    main()
