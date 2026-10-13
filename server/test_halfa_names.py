"""Вади-Хальфа's people, mobs and quest things by the original's names (the
owner's «займись фулл восстановлением Вади-Хальфы», 2026-09-28), held to
before the town is opened:

  * nobody who stands in a place the restoration opens -- the town and its
    markets, quarters, arenas and airfield, the camps and warehouses, the
    quest places around it, the mountain paths and the recycling plant,
    Берт's range, the quarry, the ore mines and the VH mine with their
    tiers, the oases, the prison yard, the craftsmen's quarter 447 (behind
    the owner's wall; its way in went with the cut of (P)) and Заречье --
    shows his mobs.xml name. Read straight from the client's location
    files, whether or not a room stands them yet (a type the client has
    no record of stands only as world.substitute's kin, and that one is
    checked), and from data/placements.json. The one exception is the remainder
    data/orig_names_manual.json lists under "none", each with its reason,
    and it is small;
  * those places are all there is: every settlement of data/settlements.json
    in their own box on the map, and every place a door or a quest way leads
    to from them, is one of them or set aside below with its reason (the
    first list missed the ambush site, the airfield, the warehouses, the
    mountain paths and the recycling plant);
  * the four factions' ranks -- the camps' fighters, their treasurers and
    ammunition boxes, their bosses -- carry their own faction and nobody
    else's (Джанджавиды were once shown as ДСР and Beja Congress, Магриб's
    sentry as a laboratory's);
  * Эддай is Npc_Commoner000799 (6763) under his row 10351, standing in the
    quarter (36) by its own file, and «Королевский Элексир» (56) is handed
    in to him; the stand-in 421 is put down nowhere;
  * the givers and takers the Halfa quests rely on, the rest of the town by
    its families' own runs, the creatures the quests send the player to kill
    or rob (each by its name alone, no level in front: the owner's
    2026-10-12), and the things they hand out and ask for, by the names below;
    every thing with a description; 260 still the valley's antelope meat,
    which its quests hand out;
  * every one of those ids in names.ALL, and the exported table with no id
    missing (tools/export_texts.py).

    LAVA_RES=.../lava/res python3 server/test_halfa_names.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _knob in ("LAVA_PLACEMENTS", "LAVA_QUESTS"):
    os.environ.pop(_knob, None)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import export_texts  # noqa: E402
import items  # noqa: E402
import names  # noqa: E402
import quests  # noqa: E402
import rooms  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

from testkit import check, fails  # noqa: E402


MT = world.mob_types()
with open(os.path.join(ROOT, "data", "orig_names_manual.json"), encoding="utf-8") as _fh:
    MANUAL = json.load(_fh)
# Named by nobody, each with its reason in the file: the whole remainder.
REMAINDER = {int(k) for k in MANUAL["none"]}
MAX_REMAINDER = 8

# The places the restoration opens. Not the premium masters' camp 124, off the
# map since the owner's cut of (P) (2026-09-30, data/retired.json), nor the
# clothing market 468 and the craftsmen's quarters 452, 456 and 457, off it
# since the owner's cut of Вади-Хальфа (2026-10-09, server/test_halfa_cut.py),
# nor the FSC airfield 528, off it since the cut of the town's ФСЦ
# (2026-10-10; its upgraders 8213/8214 stand in the other towns' airfields).
TOWN = [41, 52, 37, 104, 35, 94, 36, 95, 102, 100, 70, 164, 60,
        176, 107, 59, 78]
QUEST_PLACES = [43, 48, 65, 119, 120, 140, 62, 61, 47, 64, 63, 117, 137, 138, 139, 141, 142,
                122, 108, 45, 46, 44, 116, 121, 250]
CAMPS = list(range(80, 88))
# The warehouses, the building site, the factory and the recycling plant, the
# mountain paths with their masters. (The paths' inner ends 162 and 53 are
# files the map puts down by Донгола and Абу-Хамед as well: another region's.)
OUTSKIRTS = [109, 110, 111, 165, 198, 199, 598, 599, 623]
RANGE = [732, 1048, 1233, 1260, 1276, 1280, 1282]              # TIR_00..06
QUARRY = list(range(626, 631))
ORE_MINES = [200, 201, 202, 657, 658, 659, 1025, 1218, 1255, 1027, 1220, 1257,
             1026, 1219, 1256]
VH_MINE = [154, 158, 160, 613, 617, 1012, 1016, 1024, 1215, 1017, 1018, 1019]
# Not the FSC base «НИЛ-1» 522, off the map since the cut of the ФСЦ
# (2026-10-10); nobody ever stood in it. Nor the resistance camp 429, off the
# map since the cut of the camps across the river (2026-10-12).
ZARECHYE = [433, 508]
PRISON = [644, 645, 646, 647, 648]      # the blocks under the yard 176 (events package)
# The craftsmen's quarter, inside the owner's wall on the map. The weapon craft's
# way «Квартал ремесленников» (414) led in from the premium masters' camp 124
# until the owner's cut of (P) (2026-09-30) took both away; its people keep
# their names all the same: its trader 5770 is named since the integration of
# 2026-09-28.
QUARTER_447 = [447]
PLACES = (TOWN + QUEST_PLACES + CAMPS + OUTSKIRTS + RANGE + QUARRY + ORE_MINES + VH_MINE
          + ZARECHYE + PRISON + QUARTER_447)
# On the town's map, and not opened.
SET_ASIDE = {
    283: "Apoc_Oasis on 5972,1738, whose cell the Halfa plan gives the hermit's 61 "
         "(the owner's default 2)",
}
MARGIN = 5                  # cells around the places' own box that are the town's too

# The factions' own words, and the words of the others a rank must not carry.
FACTION = {"nc_": "Новые колонисты", "lu_": "Люшер", "ja_": "Джанджавиды",
           "mg_": "Союз арабского Магриба"}
BOSSES = {269: "nc_", 270: "nc_", 283: "lu_", 284: "lu_", 299: "ja_", 300: "ja_",
          313: "mg_", 314: "mg_"}
STRANGERS = ("ДСР", "Beja", "Лаборатори", "Работорговцы", "Миротворцы")
# Of the same prefixes but not Halfa's: the level-12 sect of Донгола's sewers (608).
ELSEWHERE = {671, 672}

EDDAI, QUARTER, ELIXIR, STAND_IN = 6763, 36, 56, 421

# The givers and takers of the town's quests, by the names the quest
# packages build on (display form: <br>, a mob's own level).
PEOPLE = {
    30: "Демир", 44: "Саид", 46: "Генри мл.", 47: "Кшиштоф", 48: "Назир", 49: "Каспар",
    67: "Рахат", 68: "жена Рахата", 86: "Инсар", 93: "Генри", 101: "Иви",
    103: "Послушник Джо", 104: "Спящий верблюд", 105: "Хассир<br>водитель",
    106: "Послушник Натти", 112: "Странник", 666: "Водитель Тиля", 668: "Винс",
    694: "Нильсон", 697: "Мария", 698: "Фрэнк", 718: "Прапорщик Касим<br>Магриб",
    719: "Механик Сейид<br>Магриб", 816: "Останки Горбика", 834: "агроном Климов",
    858: "Медик Умар<br>Магриб", 859: "Офицер Раис<br>Магриб", 860: "Лейла",
    978: "Равшан<br>Владелец каменоломни", 979: "Большой Сэм<br>Прораб",
    1657: "Старикашка", 1685: "Старая женщина", 1691: "Вивек", 1692: "Алхимический столик",
    6520: "Бари", 6522: "«Саморез» Мауризио", 4043: "Племяш Бари<br>Астронавигатор в отставке",
    6763: "Эддай<br>Местный житель", 6764: "Бюльбюль-Оглы<br>Пилигрим",
    6765: "Чарльз МакКалок<br>Сумасшедший паталогоанатом", 1188: "Мортимер<br>Обменник",
    1196: "Бернар<br>старший помощник", 2015: "Младший<br>помощник Доктора",
    1013: "Доктор Гофус", 72: "Часовой<br>Магриб", 75: "я не бомба нет", 650: "Рияд<br>Магриб",
    1077: "Капитан Калиюга<br>Встречающий<br>МКС", 2259: "Энди Уорхол<br>Старый коллекционер",
    4689: "Бензоколонка", 2011: "Мун Сон Мён<br>Колдунья", 2391: "Хан Сэлл<br>Контрабанда",
    1959: "Марк Клаус<br>Подарки", 2000: "Борн<br>сын Марка<br>упаковка подарков",
    2001: "Лана<br>дочь Марка<br>распаковка подарков", 1014: "Ребенок", 423: "Ребенок",
    425: "Ребенок", 1977: "Добрый беженец", 431: "Ольсен<br>Амулеты и сувениры",
    662: "Лотерейщик", 711: "Золотая лотерея", 5: "Мастер Тиль", 5104: "Генри ст",
    2088: "Берт Гаммер", 893: "Самуэль<br>патроны по талонам",
    652: "Техногик<br>расшифровка чертежей", 653: "Шихаб<br>Аренда транспорта",
    4: "Зоричев<br>Обучение специализациям", 883: "Хафиз<br>Аукционер", 74: "Отшельник",
    5685: "Лейтенант О’Нилл<br>Армия ЦСЦ", 5686: "Рядовой Беккет<br>Армия ЦСЦ",
    5693: "Др. Генри<br>Археолог", 5694: "Рядовой Дуэйн Доберман<br>Армия ЦСЦ",
    5695: "Техник Джеймс Хэтфилд<br>Армия ЦСЦ", 5705: "Джон док Нильсон<br>Лекарства и еда",
    5706: "Иван змей Сидоркин<br>Торговец патронами",
    5707: "Раф профессор Лю<br>Специальное снаряжение", 100: "Деда Джоф<br>Лекарь",
    2111: "Ланд Байрон<br>Лекарь", 1387: "Водитель автобуса<br>до завода",
    2180: "Снабженец Хальфы<br>Патроны и лекарства", 1791: "Охранник<br>Западная сторона",
    1794: "Охранник<br>Южная сторона", 202: "Снитке<br>Аптекарь",
    660: "Нуман<br>Аренда верблюдов и ослов", 2298: "Тьерри Сабин<br>",
    1753: "Осколок скалы (ВХ)", 1224: "Оружие", 1227: "Торговец патронами", 1234: "Лекарь",
    1320: "Вход в шахту<br>Добыча свинца", 1324: "Вход на карьер<br>Добыча селитры",
    1328: "Вход в шахту<br>Добыча меди", 1332: "Выход из шахты", 1336: "Выход из карьера",
    1340: "Выход из шахты", 1078: "Таможенник Магриба", 107: "Расул",
    81: "Бартоломью<br>Продукты",
    2276: "Джексон Кёртис<br>Волонтер Фонд спасения цивилизаци",
}
PEOPLE.update({t: "Берт Гаммер" for t in range(2089, 2096)})     # one in each lesson
# The rest of the town, each by his family's own run of rows: the woman at the
# pier Мауризио waits for, the resistance camp's spy and exchanger, the oasis'
# gunsmith, the masters of the mountain paths and the recycling plant's
# workshops; the warehouses' flag by its own caption, the original's 46362
# (the holding clan's name goes under it, server/holdings.py).
NEIGHBOURS = {
    6891: "Лаура Принсипе", 6960: "Лазутчик<br>Северный Альянс",
    7548: "Жозеф де Гобино<br>Оружейный механик<br>С Веселого Праздника",
    7021: "Корщунд<br>Аццкий обмен", 238: "Оружейник<br>Винтовки",
    239: "Оружейник<br>Дробовики", 242: "Оружейник<br>Пистолеты",
    243: "Оружейник<br>Пистолет-пулеметы", 1371: "Производство пуль",
    1375: "Производство пороха", 1379: "Производство гильз", 1011: "Складом владеют:",
    # The craftsmen's quarter 447 the weapon craft's way 414 led into: its
    # trader by the first [Q] master's row (medium, the manual file says why),
    # and the exchanger the craft makes its [Q] upgrader by his own.
    5770: "Мастер Гуго Борхардт<br>улучшение пистолетов [Q]<br>чертежи [0у], [2у] и [15у]",
    5771: "Аббас ибн Заглюль<br>Обмен экзоодежды [6-8]",
}
# The creatures the quests send the player to kill or rob, by the name alone:
# no level in front of it (orig_texts.person_name; the owner, 2026-10-12).
# The level each fights at belongs to data/mob_types.json; of it the client
# shows only a shield beside the name with the difference from the player's
# own level, -4 .. +4 (combat.mob_info).
MOBS = {
    696: "Главарь бандитов", 110: "Послушник Люшера", 111: "Мастер Люшера",
    854: "Послушник Люшера", 722: "Грабитель", 833: "Трусливый грабитель",
    814: "Погонщик верблюдов<br>Джанджавиды", 723: "Озверевшая собака",
    83: "Дикая собака", 717: "Механик<br>ДСР", 855: "Скотовод Халид",
    856: "Пастух", 665: "Шахтер", 852: "Курьер", 851: "Бандит",
    853: "Лидер бандитов", 664: "Бандит", 266: "Бригадир<br>Новые колонисты",
    261: "Каратель<br>Новые колонисты", 312: "Ефрейтор<br>Союз арабского Магриба",
    838: "Шахтер<br>Союз арабского Магриба", 839: "Шахтер<br>Союз арабского Магриба",
    41: "Ящик с деньгами", 50: "Ящик<br>Новые колонисты", 102: "Ящик спирту",
    832: "Огневая установка", 411: "Бомж",
    7448: "Хозяин склада<br>Северный склад", 7449: "Хозяин склада<br>Восточный склад",
    7450: "Хозяин склада<br>Южный склад", 977: "Порода",
    1714: "Злой шахтёр<br>Стахановцы", 60: "Бандит",
    # The ДСР stand-ins «Механик ДСР» (122) stands in its empty slots
    # (data/camp_fill.json), by the ДСР block's ranks (integration, 2026-09-28).
    62: "Ополченец<br>ДСР", 87: "Диверсант<br>ДСР", 90: "Боевик<br>ДСР",
    1040: "Старший офицер<br>ДСР", 51: "Новобранец <br>ДСР",
}
MOBS.update({1397 + k: "Цель №%d" % (k + 1) for k in range(6)})   # Берт's targets
# The things the town's quests hand out and ask for.
ITEMS = {
    216: "Мясо животного", 253: "Учетные записи", 254: "Мешок с деньгами",
    255: "Ценный груз", 256: "Посылка", 257: "Отчеты", 258: "Мешочек с деньгами", 259: "Ухо",
    260: "Мясо антилопы", 261: "Трубка", 262: "Фильтр от противогаза", 263: "Канистра",
    264: "Жетон", 266: "Бомба", 286: "Жетон Магриба", 287: "Спирт",
    291: "Священные тесты Психоса", 334: "Фуль", 416: "Первая часть журнала",
    417: "Вторая часть журнала", 418: "Третья часть журнала", 419: "Четвертая часть журнала",
    716: "Планы Магриба", 1305: "Мешочек с золотом", 1306: "Мешок с породой",
    1316: "Научная книга", 1317: "Керосиновая лампа", 1321: "Мешок зерна",
    1322: "Голова бандита", 1543: "Набор инструментов", 1544: "Пропуск на базу",
    1562: "Голова «Горбика»", 2195: "Корм для верблюда", 2196: "Передатчик", 2197: "Семена",
    2943: "Кайло каменотеса", 2944: "Каменный блок", 3186: "Бронзовый Анкх", 3189: "Шаурма",
    3190: "Бутылка самогона", 3727: "Тренировочные патроны",
    3728: "Тренировочный пистолет", 3729: "Тренировочный дробовик",
    3730: "Тренировочный Пистолет Пулемет", 3731: "Тренировочный Автомат",
    3732: "Тренировочный Пулемёт", 3733: "Тренировочная винтовка", 3742: "Сертификат",
    3939: "Алое кольцо", 3940: "Мыло с гравировкой", 3957: "Склянка",
    1307: "Лотерейный билет", 1333: "Золотой лотерейный билет",
    6544: "Билет в Абри из Вади Хальфы",
    # The Магриб base's and Мария's (147, 153, 155, 188), named at the
    # integration of 2026-09-28.
    1535: "Старый спальный мешок", 356: "Проволока", 1537: "Скрепки", 1538: "Болты",
    1539: "Гайки", 1541: "Кусок Древесины", 36: "Кусок резины", 1319: "Линейка",
}
ITEMS.update({420 + k: "Страница %d журнала" % (k + 1) for k in range(16)})
# The self-teachers' parts Тиль's trainings pay and the assemblies ask, in
# objects.xml's order (5041-5106): «<Skill> N часть» of the original.
ITEMS.update({5041 + 6 * s + k: "%s %d часть" % (word, k + 1)
              for s, word in enumerate(("Рукопашный бой", "Пистолеты", "Первая Помощь",
                                        "Хирургия", "Дробовики", "Винтовки", "Автоматы",
                                        "Пулеметы", "Ножевой бой", "Пистолет-Пулемёты",
                                        "Горное Дело"))
              for k in range(6)})
NOT_AN_ITEM = 265               # between qToken 264 and qBomb 266: objects.xml has none


def internal(t):
    return names.ALL.get(t, MT[t][1]) == MT[t][1]


def seasonal(t):
    """Left out of every room by the tokens of its name (world.EVENT_TOKENS:
    the holidays' and the developers' entries, such as the airfield's
    ADMIN_Q_*), unless the world lets it stand: nobody sees it."""
    name = MT[t][1]
    return (bool(world._name_tokens(name) & world.EVENT_TOKENS)
            and not world.belongs_here(t, name, MT[t][0], True))


# --- nobody by his mobs.xml name ----------------------------------------------------------
try:
    stands = {}                                      # type -> places
    for lid in PLACES:
        loc = world.location(lid)
        for _cell, t in loc.spawns:
            if t == 0:
                continue                             # a camp's slot: a rank, checked below
            if t not in MT:
                t = world.substitute(t) if loc.war else None
                if t is None or t not in MT:
                    continue                         # no record: never stands
            if seasonal(t):
                continue
            stands.setdefault(t, set()).add(lid)
        for rec in world.placed_in(lid):
            stands.setdefault(int(rec["type"]), set()).add(lid)
    shown = {t: sorted(where) for t, where in stands.items() if internal(t)}
    check("every place the restoration opens has a file, and is listed once",
          len(PLACES), len(set(PLACES)))
    check("nobody in them stands by his mobs.xml name but the remainder the manual file lists",
          sorted(shown), sorted(REMAINDER & set(stands)))
    # What the rooms stand there, too: a file's empty slots filled from
    # data/camp_fill.json are no rank of the four factions in «Механик ДСР»
    # (122), whose stand-ins showed their mobs.xml names until 2026-09-28.
    stood = {}
    for lid in PLACES:
        for npc in rooms.Room(world.location(lid), rooms.IdAllocator(), MT).npcs.values():
            stood.setdefault(npc[1], set()).add(lid)
    check("  ..nor anybody a room stands in them, the filled camp slots included",
          {t: sorted(where) for t, where in stood.items() if internal(t) and t not in REMAINDER},
          {})
    check("  ..and the remainder is small, each a creature with its reason",
          (len(REMAINDER) <= MAX_REMAINDER, all(v for v in MANUAL["none"].values()),
           sorted(REMAINDER - set(MT))), (True, True, []))
except Exception:
    import traceback
    fails.append("the places in process broke:\n" + traceback.format_exc())

# --- those places are all there is -------------------------------------------------------
try:
    with open(os.path.join(ROOT, "data", "settlements.json"), encoding="utf-8") as _fh:
        CELLS = {tuple(int(v) for v in k.split(",")): int(lid)
                 for k, lid in json.load(_fh)["cells"].items()}
    own = [c for c, lid in CELLS.items() if lid in PLACES]
    x0, x1 = min(x for x, _y in own) - MARGIN, max(x for x, _y in own) + MARGIN
    y0, y1 = min(y for _x, y in own) - MARGIN, max(y for _x, y in own) + MARGIN
    inside = {}                                      # lid -> whether a cell of it is in the box
    for (x, y), lid in CELLS.items():
        inside[lid] = inside.get(lid, False) or (x0 <= x <= x1 and y0 <= y <= y1)
    reached, todo = {lid for lid, v in inside.items() if v}, list(PLACES)
    # A door or a quest way leads into an interior, or to a place on the map;
    # one outside the box (the valley's Караван, where «В Хальфу!» starts) is
    # another region's, with its own names.
    while todo:
        lid = todo.pop()
        loc = world.location(lid)
        targets = [int(r["target_loc_id"]) for _c, r in travel.quest_ways(loc)
                   if r.get("target_loc_id")]
        for side in "ab":
            rec = travel.door(lid, side)
            if (rec and rec.get("target_loc_id")
                    and rec.get("confidence") in travel.DOOR_CONFIDENCE):
                targets.append(int(rec["target_loc_id"]))
        for t in targets:
            if t in reached or inside.get(t, True) is False:
                continue
            reached.add(t)
            if t not in SET_ASIDE:
                todo.append(t)
    # The places of ours (data/locations, the location editor's) are the
    # owner's, their inhabitants put there by him: not the original's town.
    OURS = {i for i in world.overlay_ids() if i >= world.FIRST_NEW_ID}
    check("every place on the town's map and every one its doors and quest ways lead to "
          "is listed above or set aside with its reason (the places of ours aside)",
          (sorted(reached - set(PLACES) - set(SET_ASIDE) - OURS), all(SET_ASIDE.values())), ([], True))
except Exception:
    import traceback
    fails.append("the town's map in process broke:\n" + traceback.format_exc())

# --- the factions' ranks ------------------------------------------------------------------------
try:
    wrong = {}
    for t, (_root, name, _art) in sorted(MT.items()):
        prefix = BOSSES.get(t) or next((p for p in FACTION if name.startswith(p)), None)
        if prefix is None or t in ELSEWHERE:
            continue
        text = names.ALL.get(t, name)
        others = [w for p, w in FACTION.items() if p != prefix] + list(STRANGERS)
        if (internal(t) or FACTION[prefix].split()[-1] not in text
                or any(w in text for w in others)):
            wrong[t] = text
    check("every rank of the four factions named, under its own faction and nobody else's",
          wrong, {})
except Exception:
    import traceback
    fails.append("the ranks in process broke:\n" + traceback.format_exc())

# --- Эддай ----------------------------------------------------------------------------------------
try:
    room = rooms.Room(world.location(QUARTER), rooms.IdAllocator(), MT)
    check("Эддай is 6763 under the original's row 10351",
          names.ALL.get(EDDAI), "Эддай<br>Местный житель")
    check("  ..who stands in the quarter by its own file, as a resident the client opens quests for",
          ([t for _c, t in world.location(QUARTER).spawns if t == EDDAI],
           [n.root for n in room.npcs.values() if n.type_id == EDDAI]), ([EDDAI], [world.COMMONER]))
    check("  ..and takes «Королевский Элексир»", quests.get(ELIXIR).take, [EDDAI])
    check("the stand-in wh_ny_Local_Man is put down nowhere, and has no hand-given row",
          ([lid for lid, rows in world.placements().items()
            for r in rows if int(r["type"]) == STAND_IN], str(STAND_IN) in MANUAL["types"]),
          ([], False))
except Exception:
    import traceback
    fails.append("Эддай in process broke:\n" + traceback.format_exc())

# --- the names the quests build on ------------------------------------------------------------
try:
    check("the givers and takers by their names", {t: names.ALL.get(t) for t in PEOPLE}, PEOPLE)
    check("the rest of the town by its families' own runs",
          {t: names.ALL.get(t) for t in NEIGHBOURS}, NEIGHBOURS)
    check("the creatures they send the player after, by their names alone",
          {t: names.ALL.get(t) for t in MOBS}, MOBS)
    check("the things they hand out and ask for by the original's names",
          {t: names.ALL.get(items.STRING_ID_OFFSET + t) for t in ITEMS}, ITEMS)
    check("  ..each with a description", [t for t in ITEMS
                                          if not names.ALL.get(items.DESC_ID_OFFSET + t)], [])
    check("  ..and a simple object's frame points at it",
          [t for t in ITEMS if items.root_of(t) == items.TRASH
           and (items.static_info(t) or ("", {}))[1].get("desc") != items.DESC_ID_OFFSET + t], [])
    check("no thing 265 to name", NOT_AN_ITEM in items.catalogue(), False)
except Exception:
    import traceback
    fails.append("the names in process broke:\n" + traceback.format_exc())

# --- the launcher's table -------------------------------------------------------------------
try:
    ids = sorted(set(PEOPLE) | set(NEIGHBOURS) | set(MOBS) | set(stands)
                 | {items.STRING_ID_OFFSET + t for t in ITEMS}
                 | {items.DESC_ID_OFFSET + t for t in ITEMS})
    check("every one of those ids in names.ALL", [i for i in ids if not names.known(i)], [])
    blob = export_texts.document_bytes()
    check("the exported table: no id missing, none stray", export_texts.verify(blob), ([], []))
    check("  ..and those ids in it",
          [i for i in ids if ("<s id='%d'>" % i).encode() not in blob], [])
except Exception:
    import traceback
    fails.append("the table in process broke:\n" + traceback.format_exc())

if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" - " + f)
    sys.exit(1)
print("halfa names OK")
