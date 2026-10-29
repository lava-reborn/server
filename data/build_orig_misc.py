"""Build data/orig_misc.json: the original texts of our vehicles and quests.

The owner found the game's own string table, texts.xml (62 795 entries of
<item id="N">text</item>). Its ids do not go on the wire: a vehicle's name
travels as transport.NAME_ID_OFFSET + type and its description as
transport.DESC_ID_OFFSET + type; quest text k of type T as
quests.STRING_BASE + 4 * T + k (k: 0 name, 1 start, 2 notfinish, 3 finish).
What this file carries across is only the text, under our own type ids:

    {"_meta":     {"source", "source_md5", "source_size", "source_rows",
                   "rule", "counts"},
     "transport": {"<type>": {"name", "desc", "name_id", "desc_id"}},
     "quests":    {"<type>": {"name", "start", "notfinish", "finish",
                              "ids": [name, start, notfinish, finish],
                              "confidence": "high"}}}

The *_id / ids fields are the original's string ids, kept only so a reader can
find the line in texts.xml; any text or id may be null where the original has
nothing we could tie to it.

The text is the original one with the XML entities decoded (html.unescape:
&lt;Br&gt; -> <Br>) and nothing else: variant marks "(P)", "<Br>" in upper
case, <hint> numbers, %имя% / %sex?...% macros and typos all stay. Every
change to a text happens in one place, server/orig_texts.py.

Transport
---------
Our table (data/transport.json) is the wiki's, with ids of our own, so a
vehicle is found by its text. Both the name and the description are looked up
only inside the vehicles' part of the file, TRANSPORT_BLOCK = 10679..10930:

  10679-10688  "Имя", then the lessor desks' names, which are the vehicles'
               plain names ("Ослик Панург", "Верблюд" ... "Хаммер"); the file
               stores a text once, so a rental of "Ослик Панург" can only have
               used this string -- the TransObject block has no plain copy
  10689-10743  NPC and map-object names, mostly "Имя<Br>Роль"; none of them
               equals a vehicle's name or description
  10744-10930  the TransObject records: names with variant marks and
               descriptions

Three levels, the first that finds anything wins, the lowest id within it:

  exact   the decoded text equals ours
  folded  equal after folding: letters and digits only, lower case, ё = е
          (a trailing full stop, "Крылатый ламантин")
  marker  names only: the original ends in one variant mark and the rest
          folds equal to ours, and the mark agrees with our record --
          P/P1/P2 with premium, G with a gold price, A with an afro one
          ("Газ 67 Б (P)" for our premium "Газ 67 Б")

A string starting with "Тест" is never written ("Тест Кобыла -").

Quests
------
Of our quests, those written for this server (OWN_QUESTS) have no original
and are never looked up -- the black market's five (1, 2, 3, 5, 6) were, until
they left the table on 2026-09-28 (the plan's gold taps) -- and neither is
Джеррах's «Обмен слитка»
(10), whose texts are ours and match nothing. The seventeen of the Nubian
valley's tutorial (11-27) were written into data/quests.json from the
original's own lines, the newest edition of each (see start below), and are
matched like any other; where the original has no line -- the name of
«Провиант» (the wiki's), of the squad's report (ours) -- the slot stays ours.
So were the eighteen of its story (28-45: Наби's line, Демир's rides out and
back, Саид in Вади-Хальфа); «Назад, в долину» has no finish in the file, and
the one it is given is the original's line for the same ride in another
quest. And the twenty-two of its market, farm and mine (46-67: Муад's,
Сорванец's, Доктор Гофус's, the rat-catcher's and the farmer's, Шульц's,
Камал's «Изумруды», Сабир's antelopes and the four map flags); two of them,
«Точильный камень» and «Крысиный король», have no name line of their own,
and the matcher finds the thing's, the same words.
Eight come from the wiki, and the way into
the Nubian mine (7) was written into data/quests.json from the original's own
lines, which the matcher then finds like any other; the way out (8) was too,
but its start is cut to what the server does (nothing is taken on the way
out) and it is not in VERIFIED.
Камал's «Золотоискатель» (9) was written from them too, but with the count
the owner set (10 bags where the original says 5): its start and notfinish
no longer fold equal to the original's, the matcher finds nothing, and the
texts stay ours -- which is the point; it is not in VERIFIED. In
the original a quest is laid out as name, start, "not finished", finish, but
a text is stored once, so the four are rarely consecutive and every text is
looked up on its own. Texts are compared folded, as above, after dropping
from both sides the <hint>…</hint> quest number, %sex?…% / %имя% macros and
the "<b>Задача:</b> …" task line later quests end their start with; from ours
also three wiki artefacts: a "Квест: " prefix and a " (часть N)" suffix on
the name (page title conventions) and the quest's title glued in front of the
start ("Муж<br>Можно попробовать…").

  name       every string folding equal to the name as it stands; where
             the file has none, the name with the wiki's " (часть N)" cut
             off («Похищенный груз (часть 2)» is a line of its own, 25191,
             beside «Похищенный груз»; "Муж (часть 2)" is not, and is "Муж")
  start      folding equal to the start. A text the file keeps in several
             editions -- the Nubian valley's tutorial is written twice, the
             2012 lines of 24333-25210, many of them labelled with the
             quest's number (<hint><B>№0000158</B></hint>), and the newest
             ones of 59767-59946 without it -- is the newest unlabelled one,
             the highest id; its name is the nearest name candidate before
             it, however far (the new edition wrote no name line where the
             old one's still served, so «Мертвые беззащитны» is 25176 and
             its start 59813), or none where the file has no such name (a
             title the wiki gave, «Провиант»). Where every copy carries the
             label (Мастер Тиль's six trainings share one start, each with
             its own number), the start is the one nearest after a name
             candidate, at most MAX_GAP ids on, which fixes the name too
  notfinish  folding equal -- the unlabelled copies, if there are any, and
             of those the valley's newest edition's (59767-59946), if it
             wrote one: «Разведчик» keeps its 2012 start and takes that
             edition's finish, 59861, not "кто—то" of 24425 --
             the nearest after the start, else the nearest before it (a
             shared line stored once, earlier)
  finish     the same, counted from the later of the start and the
             notfinish (a notfinish the new edition shares with the old
             sits far before its start, and the finish follows the start)

Where copies that fold equal differ in their task lines -- «Еда»'s start
and notfinish say the same words with another task each -- the ones whose
task line is ours are taken, in each of the three (QuestIndex.same_task).

A slot we leave empty is not looked up: the original's text for it, if any,
is not ours to guess. VERIFIED holds the result of each quest as checked by
hand, with the reason. The matcher has to reproduce every entry on its own or
the build stops; a match for a quest not in VERIFIED is reported and not
written.

Output is deterministic: sort_keys, indent=1, ensure_ascii=False, no dates;
the digest of the final string table is compared by every player's launcher.

    MSYS_NO_PATHCONV=1 wsl.exe -e bash -lc "cd /mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server && LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/build_orig_misc.py"

The source is LAVA_ORIG_TEXTS (default /mnt/c/Users/gmkrt/Downloads/texts.xml).
Nothing here reads LAVA_RES; the command above carries it only to be the same
for every data/build_orig_*.py.
"""
import hashlib
import html
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCE = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "orig_misc.json")

TRANSPORT_BLOCK = range(10679, 10931)
TEST_PREFIX = "тест"            # compared lower-case

# Written for this server, not in the original. The black market's 1, 2, 3, 5
# and 6 were, until they left data/quests.json (2026-09-28).
OWN_QUESTS = ()
MAX_GAP = 20                    # start at most this many ids after the name
QUEST_KEYS = ("name", "start", "notfinish", "finish")   # = k 0..3 in quests.py

# Checked by hand: type -> (name, start, notfinish, finish) original ids.
VERIFIED = {
    # 41453-41456, all four in a row: "Пистолетчик", <hint>№B81000024 start
    # "Решил%sex?:а% начать учиться...", its notfinish, and the finish.
    4: (41453, 41454, 41455, 41456),
    # Мастер Тиль's four trainings each have their own name, start and
    # notfinish (hint numbers B81000025, -29, -26, -28), and all share the
    # finish of quest 4, stored once at 41456 -- the wiki gives the same text.
    1829: (41457, 41458, 41459, 41456),
    1895: (41469, 41470, 41471, 41456),
    1971: (41460, 41461, 41462, 41456),
    2128: (41466, 41467, 41468, 41456),
    # The wild and the leftovers (250-286), each read in texts.xml by hand.
    # Treasures: Камал's «Карты сокровищ» (sold by Бари in Вади-Хальфа, no
    # notfinish in the file) and the first dig of Зубери's five, whose
    # finish 25963 is stored once; the other four digs repeat its start and
    # notfinish under their own labels (25964-25971), which the matcher
    # cannot tell apart, so they are not pinned. «Сокровища Зубери» itself;
    # the B81 web's «Сокровища» of Хоу Сян, «Лопатка» of his wife and
    # Чакки's copy (the name 41523 stored once); the seven «Зарытые
    # сокровища» share one line under twelve labels and are not pinned.
    250: (25957, 25958, None, 25959),
    251: (25960, 25961, 25962, 25963),
    256: (25953, 25954, 25955, 25956),
    257: (41523, 41524, 41525, 41526),
    258: (41527, 41528, 41529, 41530),
    259: (41523, 41531, 41532, 41533),
    # Мясники: the names of the old block, the lines of the newest copy
    # (60512-60520, unlabelled, just before the butchers' own names).
    267: (26277, 60512, 60513, 60514),
    268: (26281, 60515, 60516, 60517),
    269: (26285, 60518, 60519, 60520),
    # Уорхол's two drivers' collections (the Ламантин one is the wiki's).
    271: (47950, 47951, 47952, 47953),
    272: (47954, 47955, 47956, 47957),
    # The rides: «Поездка в Донголу» is one name for two (46965); the ride
    # from Абри shares «Поездка в Абри»'s notfinish and finish, stored once.
    # The passes: their names 46744-46748 and 47243, their starts, the
    # shared notfinish 47226 and «Ну, поехали!» (59830). Мероэ's pass has no
    # start of its own (the ticket's description) and is not pinned.
    273: (46957, 46958, 46959, 46960),
    274: (46961, 46962, 46963, 46964),
    275: (46965, 46966, 46959, 46960),
    276: (47239, 47240, 47241, 47242),
    277: (46965, 47222, 47223, 47224),
    278: (47228, 47229, 47230, 47231),
    279: (46745, 61303, 47226, 59830),
    280: (46744, 61304, 47226, 59830),
    281: (46746, 61305, 47226, 59830),
    282: (46745, 61303, 47226, 59830),
    283: (47243, 47244, 47226, 59830),
    284: (46746, 61306, 47226, 59830),
    285: (46748, 47227, 47226, 59830),
    # "Тир Берта Гаммера": the name line 41446, and the newest edition's
    # start and finish, 59767/59768 -- the course free, «рассчитан на
    # игроков 0-5 Уровня», no letter; the old paid one of 41447-41449 is
    # not ours. No notfinish in the newest edition, none looked up.
    1682: (41446, 59767, None, 59768),
    # The "Муж" chain, 47315-47329, one name string for every stage. The
    # wiki's 761 is Кшиштоф's stage: its start is 47318 without the task line,
    # notfinish and finish follow at 47319-47320.
    1761: (47315, 47318, 47319, 47320),
    # The wiki's 762 ("Муж (часть 2)", a page title) is Назир's stage; its
    # start on the wiki begins "Муж<br>", the title as the game showed it.
    # 47325-47327 are start, notfinish and finish in a row.
    1762: (47315, 47325, 47326, 47327),
    # Берт Гаммер's course (351-365), each text read in texts.xml by hand.
    # The lessons' names are the old edition's lines (41450, 41360-41380, in
    # fours), the only copies; their starts the newest edition's, 59769-59778
    # (the old ones write «?–1» for «№1»); a notfinish or a finish the newest
    # edition wrote again (59772, 59775, 59777, 59779) is its copy, the rest
    # the old edition's only lines. «Урок 1» has no notfinish in either.
    351: (41450, 59769, None, 41452),
    352: (41360, 59770, 41362, 41363),
    353: (41364, 59771, 59772, 41367),
    354: (41368, 59773, 41370, 41371),
    355: (41372, 59774, 41374, 59775),
    356: (41376, 59776, 41378, 59777),
    357: (41380, 59778, 41382, 59779),
    # «Прервать обучение», one row per range: the newest name and start
    # («второго шанса не будет»); «Удачи.» is the old edition's finish,
    # 41389, nearer than the other «Удачи» (25214).
    358: (59780, 59781, None, 41389),
    359: (59780, 59781, None, 41389),
    360: (59780, 59781, None, 41389),
    361: (59780, 59781, None, 41389),
    362: (59780, 59781, None, 41389),
    363: (59780, 59781, None, 41389),
    364: (59780, 59781, None, 41389),
    # «Получить боеприпасы», the newest edition's free rounds: name, start,
    # finish in a row; no notfinish.
    365: (59782, 59783, None, 59784),
    # «Автоматчик», Мастер Тиль's sixth training, as his five above.
    366: (41463, 41464, 41465, 41456),
    # «Самоучители» (the wiki's «ч.2», Часовой): the one name line 49536;
    # 49540 start and 49541 finish. 49537-49539 are Мунир's part 1.
    367: (49536, 49540, None, 49541),
    # The eleven assemblies of Бюльбюль-Оглы: name, labelled start and
    # notfinish in threes from 26302; the finish «С этим самоучителем...» is
    # stored twice, 26305 and 47570 (a space before the dash), and the one
    # nearest after each notfinish is taken.
    368: (26302, 26303, 26304, 26305),
    369: (26306, 26307, 26308, 47570),
    370: (26309, 26310, 26311, 47570),
    371: (26312, 26313, 26314, 47570),
    372: (26315, 26316, 26317, 47570),
    373: (26318, 26319, 26320, 47570),
    374: (26321, 26322, 26323, 47570),
    375: (26324, 26325, 26326, 47570),
    376: (26327, 26328, 26329, 47570),
    377: (26330, 26331, 26332, 47570),
    378: (26333, 26334, 26335, 47570),
    # The exams of the base of Magrib, for afro (379-389) and for gold
    # (390-400): name and start in twos from 49544; «Возми книжку, почитай.»
    # 49543 and «Молодец, хорошо подготовился...» 49542 are shared, stored
    # once before them (60662 is another copy, «еденицу», not the same).
    379: (49544, 49545, 49543, 49542),
    380: (49546, 49547, 49543, 49542),
    381: (49548, 49549, 49543, 49542),
    382: (49550, 49551, 49543, 49542),
    383: (49552, 49553, 49543, 49542),
    384: (49554, 49555, 49543, 49542),
    385: (49556, 49557, 49543, 49542),
    386: (49558, 49559, 49543, 49542),
    387: (49560, 49561, 49543, 49542),
    388: (49562, 49563, 49543, 49542),
    389: (49564, 49565, 49543, 49542),
    390: (49566, 49567, 49543, 49542),
    391: (49568, 49569, 49543, 49542),
    392: (49570, 49571, 49543, 49542),
    393: (49572, 49573, 49543, 49542),
    394: (49574, 49575, 49543, 49542),
    395: (49576, 49577, 49543, 49542),
    396: (49578, 49579, 49543, 49542),
    397: (49580, 49581, 49543, 49542),
    398: (49582, 49583, 49543, 49542),
    399: (49584, 49585, 49543, 49542),
    400: (49586, 49587, 49543, 49542),
    # The quarry of Вади-Хальфа, 61428-61444. Равшан's contract: name,
    # start, finish; no notfinish. «Покинуть каменоломню.»: name and start;
    # its finish, the wiki's «Возвращайся. Работа есть всегда.», is the
    # file's line of those words for another quarry, 25838, stored once.
    # Большой Сэм's blocks (10 and 30) share the notfinish 61435 and the
    # finish 61436, as the wiki gives them; the Анкх four in a row.
    401: (61428, 61429, None, 61430),
    402: (61431, 61432, None, 25838),
    403: (61433, 61434, 61435, 61436),
    404: (61437, 61438, 61435, 61436),
    405: (61441, 61442, 61443, 61444),
    # The boat to Заречье and back (switched off in the table): 24440-24443
    # and 24444-24446, in a row; «Вернуться в город» has no notfinish.
    412: (24440, 24441, 24442, 24443),
    413: (24444, 24445, None, 24446),
    # The Nubian mine's quests, 59924-59943: "Старые штольни" (Шульц sends
    # the player to the mine; our 57, below), then Рудо's
    # "Отправка в шахту" at 59928-59931, Камал's two work quests, and his
    # "Выведи меня отсюда" at 59940-59943 -- each name, start, notfinish and
    # finish in a row. Every one of the eight texts occurs once in the file.
    # The first of Камал's work quests, «Золотоискатель» 59932-59935, is our
    # 9 with the count changed (see the docstring) and is left out on purpose.
    # Камал's "Выведи меня отсюда", 59940-59943, is our 8 with the start cut
    # to what the server does (nothing is taken on the way out, the owner's
    # call of 2026-09-25) and is left out on purpose, like 9.
    7: (59928, 59929, 59930, 59931),
    # The Nubian valley's tutorial, 11-27, each text read in texts.xml by
    # hand. The newest edition (59785-59826, 59923) writes a quest's start,
    # notfinish and finish in a row and no name, where the 2012 one's name
    # still served; the 2012 lines (24337-24411, 25168-25190) that the new
    # edition did not write again are its own. Where both carry a text, the
    # 2012 copy differs by its «№0000156..161» label or its em dashes
    # ("задания— за них"), and the newest is taken.
    # North: «Добро пожаловать» -- 25168 the one name line, then Думисани's
    # start (the tutorial's first, WASD hint), notfinish, Зула's finish.
    11: (25168, 59785, 59786, 59787),
    # «Друзья», Зула -> Салех: 24401 is the only «Друзья» of the file (the
    # wiki's name for this edition; the 2012 numbered one is «Помощь»,
    # 25172); start and notfinish without №0000157; 25175 Салех's finish.
    12: (24401, 59788, 59789, 25175),
    # «Подоить корову»: the newest of seven copies of the start (24410 and
    # the event's 46630-46634 are the others); no notfinish; 24411.
    13: (24409, 59923, None, 24411),
    # «Финансовая система», Салех's parcel: four in a row.
    14: (59790, 59791, 59792, 59793),
    # West: «Добро пожаловать» again -- 25168; Джеррах's start ("Очнулся?
    # При тебе документы...", the 2012 copy 25169 labelled №0000156),
    # notfinish, Ибрахим's finish.
    15: (25168, 59794, 59795, 59796),
    # «Друзья» (the wiki's «Друзья I»), Ибрахим's tools: no name line of its
    # own, 24401 as for 12; start, notfinish, finish in a row.
    16: (24401, 59797, 59798, 59799),
    # «Забрать инструменты», the box: name, start, finish; no notfinish.
    17: (59800, 59801, None, 59802),
    # «Финансовая система» (the wiki's «... I»), Ибрахим's parcel: the one
    # name line 59790, then its own three.
    18: (59790, 59803, 59804, 59805),
    # «Немного мудрости», Гарард: 24390; the start's 2012 copy 24391 has
    # em dashes, 59806 not; "Давай уже." is stored once, 24392; the finish
    # 59807 (24393 the 2012 copy).
    19: (24390, 59806, 24392, 59807),
    # «Стреляем», Гарард's rats: the 2012 four, the only copies (45365 is a
    # later copy of the finish elsewhere; the one after the notfinish wins).
    20: (24337, 24338, 24339, 24340),
    # «Снабжение», Ибрахим -> Амина: 24394; start and notfinish of the newest
    # edition (24395/24396 the 2012 copies); Амина's 24397, stored once.
    21: (24394, 59808, 59809, 24397),
    # «Провиант», Амина -> Ибрахим: the file has no name line (the name is
    # the wiki's); start, notfinish, finish of the newest edition.
    22: (None, 59810, 59811, 59812),
    # «Мертвые беззащитны», the dog skins: 25176; the three without №0000158.
    23: (25176, 59813, 59814, 59815),
    # «Шелковый путь», the silk: the newest edition's own name 59816 (25180
    # is «Шёлковый путь»); start, notfinish without №0000159; 25183.
    24: (59816, 59817, 59818, 25183),
    # «Доверие», Джеррах -> the squad: 25184; start and notfinish without
    # №0000160; 25187, the squad's words.
    25: (25184, 59819, 59820, 25187),
    # The squad's report (№0000161 in 2012, no name line): back to Джеррах
    # in the newest edition (59821; 25188 sent the player to Рихтер);
    # "Отправляйся как можно скорее!" 59822; Джеррах's 25190.
    26: (None, 59821, 59822, 25190),
    # «Слава или смерть», the arena's ear: four in a row.
    27: (59823, 59824, 59825, 59826),
    # Мортимер's services in Вади-Хальфа (301-307), each read in texts.xml
    # by hand: a name and a start, no notfinish or finish in the file. The
    # cashing takes the start of the copy for one with neither residence
    # nor citizenship («комиссия ... 0,05 унции золота», 49802, 49807,
    # 49812: 0.95, 4.95 and 9.95 ounces paid); the name lines 49800, 49796,
    # 49798 are the plain ones, the «с видом на жительство» and «с
    # гражданством» lines being names of their own. Our rows' starts are
    # their own since the cut of (P) (2026-10-02): the opening «Как для лица
    # не имеющего гражданства или вида на жительство» is out, everybody
    # pays the commission here (build_quests, one_passage_out). The change of ingots,
    # 49817-49824, name and start in a row. The lotteries (308, 309) are not
    # here: their starts are cut of the (P) guns, and ours.
    301: (49800, 49802, None, None),
    302: (49796, 49807, None, None),
    303: (49798, 49812, None, None),
    304: (49817, 49818, None, None),
    305: (49819, 49820, None, None),
    306: (49821, 49822, None, None),
    307: (49823, 49824, None, None),
    # The money boxes of Вади-Хальфа's three склады (765-767, server/
    # holdings.py), read in texts.xml by hand: the series' one name line,
    # 26363 «Патроны и афро владельцам склада (Бж.)», and each box's start,
    # №0000765-767 (26364-26366: 8000, 8000 and 24000 afro); the file has no
    # notfinish or finish for the series. Name and start are the rows' own
    # (own_texts): the tier «(Бж.)» and the hint of residence and
    # citizenship are out, one passage each (build_quests, one_passage_out).
    765: (26363, 26364, None, None),
    766: (26363, 26365, None, None),
    767: (26363, 26366, None, None),
    # The quarry's leftovers (320-323), each text read in texts.xml by hand.
    # Большой Сэм's «Полированные камни.» (61439/61440) ends as his blocks do,
    # 61435/61436, the words the wiki gives it; «Создать Полировочную смесь»
    # is name, start and finish in a row, no notfinish. Варон's «Камни для
    # фундамента» is four in a row, and «Полированные Камни» (61466/61467 --
    # a name folding equal to Сэм's, the nearest before its start taken)
    # shares its notfinish and finish, stored once.
    320: (61439, 61440, 61435, 61436),
    321: (61459, 61460, None, 61461),
    322: (61462, 61463, 61464, 61465),
    323: (61466, 61467, 61464, 61465),
    # The valley's story, 28-45, each text read in texts.xml by hand. The
    # newest edition wrote Наби's line at 59834-59871 again, and where it did
    # not (the name lines, «Разведчик»'s start, «Хвост», «Важные персоны»,
    # «В Хальфу!»), the 2012 lines of 24345-24436 and 25191-25210 are its
    # own; the 2012 copies of the lines it did write carry «№0000162..166» or
    # em dashes, and the newest is taken.
    # «Нет больше покоя»: name, start, finish in a row; no notfinish.
    28: (59834, 59835, None, 59836),
    # «Предки без защиты», Наби's dogs: four in a row.
    29: (59837, 59838, 59839, 59840),
    # «Главное - это здоровье», to Гарард: name, start, finish; no notfinish.
    30: (59841, 59842, None, 59843),
    # «Похищенный груз»: the newest edition's name (24416 is «... (часть
    # 1)»), start and finish; the notfinish is the 2012 line 24418, the only
    # one ("к западу отсюда"), before the start.
    31: (59851, 59852, 24418, 59853),
    # «Похищенный груз (часть 2)»: its own name line 25191 (the name is
    # looked up as it stands before the part is cut off); start and
    # notfinish without №0000162; 25194, stored once.
    32: (25191, 59854, 59855, 25194),
    # «Похищенный груз (часть 3)»: 25195; the two without №0000163; 25198.
    33: (25195, 59856, 59857, 25198),
    # «Дальнейшая борьба»: 24420; the newest start, to Сейфул (24421 sends
    # the player to Рихтер); no notfinish; 24422.
    34: (24420, 59858, None, 24422),
    # «Пути информации», the courier: 25199; the two without №0000164; 25202.
    35: (25199, 59859, 59860, 25202),
    # «Разведчик»: 24423 and 24424, the only start; no notfinish; the finish
    # of the newest edition, 59861 (24425 is the same words with "кто—то":
    # QuestIndex.newest).
    36: (24423, 24424, None, 59861),
    # «Хвост», Корбен's pursuers: the 2012 four, the only copies.
    37: (24345, 24346, 24347, 24348),
    # «Одолжить аптечку»: 25203; the two without №0000165; 25206.
    38: (25203, 59862, 59863, 25206),
    # «Важные персоны», Аюб's commissar: the name 24349 and the notfinish
    # 24351, the only copies; the start and finish of the later copy
    # 45368/45369 (a pass that also rewrote «Стреляем»'s finish, 45365),
    # which writes "-" where 24350/24352 write "–".
    39: (24349, 45368, 24351, 45369),
    # «Последний удар», the leader: 25207; the newest three (25208/25209
    # carry №0000166, 25210 is the 2012 finish).
    40: (25207, 59864, 59865, 59866),
    # «Новые вопросы», the notes: 24426; the newest start and notfinish (to
    # ал-Асад; 24427/24428 send them to Хаксли); 24429.
    41: (24426, 59867, 59868, 24429),
    # «Назад, в большой мир»: 24430; the newest start 59869 (24431 has em
    # dashes); 24432 and 24433, the only copies.
    42: (24430, 59869, 24432, 24433),
    # «В Хальфу!», Демир's ride out: name, start, finish; no notfinish.
    43: (24434, 24435, None, 24436),
    # «Назад, в долину», the ride back: name and start; the file has no
    # finish for it, and ours -- DESIGNED -- is the original's own words for
    # the same ride into the valley, «Ну, поехали!» of «Полиция: отправка в
    # нубийскую долину» (59828-59830), stored once.
    44: (59870, 59871, None, 59830),
    # «Добро пожаловать в Хальфу», Демир -> Саид: name, start, finish.
    45: (62650, 62651, None, 62652),
    # Вади-Хальфа's story (101-155), each text read in texts.xml by hand.
    # «Обучение», Шульц -> Зоричев: four in a row.
    101: (47375, 47376, 47377, 47378),
    # The newest edition's act straight on from 45, 62653-62694: name,
    # start, notfinish, finish in a row, or name, start, finish where it
    # wrote no notfinish.
    102: (62653, 62654, 62655, 62656),
    103: (62657, 62658, 62659, 62660),
    104: (62661, 62662, None, 62663),
    105: (62664, 62665, None, 62666),
    106: (62667, 62668, 62669, 62670),
    107: (62671, 62672, None, 62673),
    108: (62674, 62675, None, 62676),
    109: (62677, 62678, None, 62679),
    110: (62680, 62681, None, 62682),
    111: (62683, 62684, None, 62685),
    112: (62686, 62687, None, 62688),
    113: (62689, 62690, None, 62691),
    114: (62692, 62693, None, 62694),
    # The dailies of the older block. «Раббин аль-Гуд»'s notfinish is the
    # lavabook's, «Сопутствует ли тебе удача?», stored once at 47267 (the
    # notfinish of «Отомстить похитителям», 126, too); «Местные
    # предпочтения» has none.
    115: (47275, 47276, 47267, 47277),
    116: (47278, 47279, 47280, 47281),
    117: (47282, 47283, 47284, 47285),
    118: (47286, 47287, None, 47288),
    119: (47289, 47290, 47291, 47292),
    # «Муж», the four stages beside the wiki's 1761/1762, all under the one
    # name line 47315: Иви's start and Кшиштоф's answer, the sentry's news
    # and Иви's tears, Иви's plea and Назир's answer, Назир's refusal and
    # Иви's silence.
    120: (47315, 47316, None, 47317),
    121: (47315, 47321, None, 47322),
    122: (47315, 47323, None, 47324),
    123: (47315, 47328, None, 47329),
    # Рахат: his wife's two steps under 47260; «Отомстить похитителям»
    # four in a row; its parts 2 and 3 by their own name lines.
    124: (47260, 47261, None, 47262),
    125: (47260, 47263, None, 47264),
    126: (47265, 47266, 47267, 47268),
    127: (47269, 47270, None, 47271),
    128: (47272, 47273, None, 47274),
    # «Порядок» and its part 2; part 3 and «Чертежи» (131, 132) are not
    # here: their starts name the owner's boss hours, 14, 18 and 22, where the
    # original says 18 and 22, and are ours.
    129: (47383, 47384, None, 47385),
    130: (47386, 47387, 47388, 47389),
    # «Пропавший товарищ», each part by its own name line.
    133: (47293, 47294, None, 47295),
    134: (47296, 47297, None, 47298),
    135: (47299, 47300, 47301, 47302),
    # «Слухи», «Гарантии безопасности»: four in a row, or three.
    136: (47303, 47304, None, 47305),
    137: (47306, 47307, 47308, 47309),
    # «Бомба»: no name line of the quest's own; the one of that word is
    # the bomb's, 6200 (its description 6201 follows), nearest before the
    # starts. Назир's start, notfinish and the box's finish; the box's
    # start and Назир's finish.
    138: (6200, 47310, 47311, 47312),
    139: (6200, 47313, None, 47314),
    # The gold rush, 62695-62710, under its one name line: Винс's debt;
    # his word to find Тиль (no finish in the file); Тиль's step;
    # the driver's ride back, «В Вади-Хальфу», which the file ends with
    # nothing and ours with the original's «Ну, поехали!» (59830, as 44);
    # the driver's ore; Винс's reward; Тиль's «К шахте», ended with his own
    # «Собирайся и езжай.» (62701). The later edition's 62711-62714 are 156
    # and 157, below.
    140: (62695, 62696, 62697, 62698),
    141: (62695, 62699, None, None),
    142: (62695, 62700, None, 62701),
    143: (62705, 62706, None, 59830),
    144: (62695, 62702, 62703, 62704),
    145: (62695, 62709, None, 62710),
    146: (62707, 62708, None, 62701),
    # The Магриб base, 62715-62747: four in a row each, but the pass,
    # which has no name line of its own -- the one of that word is the
    # pass's, 6230 --, and «Вернутся к Сейиду», which has no notfinish.
    147: (62715, 62716, 62717, 62718),
    148: (62719, 62720, 62721, 62722),
    149: (62723, 62724, 62725, 62726),
    150: (62727, 62728, 62729, 62730),
    151: (6230, 62731, None, 62732),
    152: (62733, 62734, None, 62735),
    153: (62736, 62737, 62738, 62739),
    154: (62740, 62741, 62742, 62743),
    155: (62744, 62745, 62746, 62747),
    # The gold rush's later edition (62711, 62712) under its one name line:
    # Винс's word to ask Тиль, Тиль's greeting. Its paid step (157, 62713/
    # 62714) has a start of ours -- the original sold gold for real money
    # there -- and is not here.
    156: (62695, 62711, None, 62712),
    # Вади-Хальфа's prison, 62257-62292: the invitation (its three in a
    # row); the rides «Поехали!» (the town's copy of three, 62263) and back,
    # which the file ends with nothing and ours with «Ну, поехали!» (59830,
    # as 143); the two gates, whose names follow the one call to the
    # uprising they share (62272/62273), so the matcher finds no name before
    # it and our name stands; Томас's «Выход»; the medics' five, «75
    # двухсотых» with the start that names its two talons (62292, beside
    # 62289), it and the hundred with no finish in the file; and Самуэль's
    # talon (61934/61935).
    158: (62257, 62258, None, 62259),
    159: (62262, 62263, None, 59830),
    160: (62266, 62267, None, 59830),
    161: (None, 62272, 62273, None),
    162: (None, 62272, 62273, None),
    163: (62276, 62277, None, 62278),
    164: (62279, 62280, None, 62281),
    165: (62282, 62283, None, 62284),
    166: (62285, 62286, None, 62287),
    167: (62288, 62292, None, None),
    168: (62290, 62291, None, None),
    169: (61934, 61935, None, None),
    # The valley's market, farm and mine, 46-67, each text read in texts.xml
    # by hand. The newest edition wrote them at 59741-59744 and 59844-59939,
    # name, start, notfinish and finish in a row; where it did not (the
    # rat-catcher's and the farmer's names and finishes, Шульц's boss), the
    # 2012 lines of 24341-24344, 24613-24616 and 26266-26276 are its own,
    # and their copies of the lines it did write carry «№0000720..722» or
    # dashes.
    # Муад: «Лучшее снаряжение» (to Сет) and «Попутный ветер» (to Фая):
    # name, start, finish; no notfinish.
    46: (59899, 59900, None, 59901),
    47: (59902, 59903, None, 59904),
    # «Точильный камень»: the file has no name line of the quest's own; the
    # one of those words is the grindstone's, 6342 (the file stores a text
    # once), nearest before the start. Start, notfinish, finish in a row.
    48: (6342, 59905, 59906, 59907),
    # «Клык за Клык» and «Раненый сын»: four in a row each.
    49: (59908, 59909, 59910, 59911),
    50: (59912, 59913, 59914, 59915),
    # Сорванец's «Спички детям»: four in a row.
    51: (59895, 59896, 59897, 59898),
    # Доктор Гофус's «Сгоревшая микросхема»: four in a row, just before the
    # newest edition's own block.
    52: (59741, 59742, 59743, 59744),
    # Крысолов's «Крысиный переполох»: 24613, the one name line; the newest
    # start 59916 (24614 has other hours, 24615 em dashes); no notfinish;
    # the newest finish 59917 (24616 the 2012 copy).
    53: (24613, 59916, None, 59917),
    # «Крысиные хвосты»: 26273; start and notfinish without №0000722;
    # 26276, stored once.
    54: (26273, 59921, 59922, 26276),
    # Хрущ's «Крысиный король»: no name line of the quest's own; the rat
    # king's, 6344, nearest before the start; start and notfinish without
    # №0000720; 26268, stored once.
    55: (6344, 59918, 59919, 26268),
    # «Королевский Элексир»: 26269; the start without №0000721; its
    # notfinish is the words of 55's, whose newest copy is 59919; 26272.
    56: (26269, 59920, 59919, 26272),
    # Шульц's «Старые штольни»: four in a row (Рудо's «Отправка в шахту», 7,
    # follows on).
    57: (59924, 59925, 59926, 59927),
    # «Экипировка к пистолету», Большой Мвамба: 24341; the newest start and
    # notfinish 59832/59833 (24342/24343 have en dashes, 45366/45367 are a
    # later copy); 24344, the only finish. Its introduction is type 68.
    58: (24341, 59832, 59833, 24344),
    # Schulz's preparation: the original has no finish; ours completes the talk.
    68: (59944, 59945, 59946, None),
    # Камал's «Изумруды»: four in a row.
    59: (59936, 59937, 59938, 59939),
    # Сабир's «Любимая антилопа»: four in a row; part 2 by its own name
    # line, start, finish; no notfinish.
    60: (59844, 59845, 59846, 59847),
    61: (59848, 59849, None, 59850),
    # «Еда»: name and start; the notfinish is 59877, which says what 59875
    # says before the task line and another task ('отнести найденное мясо
    # Сабиру'), told apart by it (QuestIndex.same_task); the finish 59878
    # («Спасибо, странник.»); 59876 is left out.
    62: (59874, 59875, 59877, 59878),
    # «Охота на антилоп»: four in a row.
    63: (59891, 59892, 59893, 59894),
    # The four «Где ...?» map flags: name, start, finish each; no notfinish.
    64: (59879, 59880, None, 59881),
    65: (59882, 59883, None, 59884),
    66: (59885, 59886, None, 59887),
    67: (59888, 59889, None, 59890),
    # Вади-Хальфа's town chains of the old edition (180-237), each text read
    # in texts.xml by hand. They have no newest copy: each is stored once, in
    # the quest's own run (47330-47524, 41384-41399); where a step has no
    # name line of its own, its row carries the chain's name and the nearest
    # such line before the start is the one (197 and 199 «Верблюдное дело:
    # корм / молодняк», 201, 202, 205-207, 221).
    # Бари's B81 web, the Вади-Хальфа steps: «Билли Джей» name, start,
    # finish; «Курьер» and «Медик Умар», whose every line carries its №B81
    # label (Умар's is the Вади-Хальфа copy B81000002: 41398, his "Часовой!!!",
    # folds as Абри's 41401 does and is the nearest after the start).
    180: (41384, 41385, None, 41386),
    181: (41393, 41394, None, 41395),
    182: (41396, 41397, 41398, 41399),
    # «Выборы» (47398-47478). «Мауризио» (184) has no name line after 47400:
    # the file stores «Мауризио» once, 26568, the name of another quest of
    # his (№0000879), and that line is the nearest before the start.
    183: (47398, 47399, None, 47400),
    184: (26568, 47401, None, 47402),
    185: (47403, 47404, 47405, 47406),
    186: (47407, 47408, 47409, 47410),
    187: (47411, 47412, 47413, 47414),
    188: (47415, 47416, 47417, 47418),
    189: (47419, 47420, None, 47421),
    190: (47422, 47423, 47424, 47425),
    191: (47426, 47427, None, 47428),
    192: (47429, 47430, None, 47431),
    193: (47432, 47433, 47434, 47435),
    194: (47436, 47437, 47438, 47439),
    195: (47440, 47441, None, 47442),
    196: (47443, 47444, 47445, 47446),
    197: (47443, 47456, 47457, 47458),
    198: (47447, 47448, None, 47449),
    199: (47447, 47450, None, 47451),
    200: (47452, 47453, 47454, 47455),
    201: (47440, 47459, None, 47460),
    202: (47429, 47461, None, 47462),
    203: (47463, 47464, 47465, 47466),
    204: (47467, 47468, 47469, 47470),
    205: (47467, 47471, 47472, 47473),
    206: (47463, 47474, 47475, 47476),
    207: (47398, 47477, None, 47478),
    # «Индийское кино» (47489-47524): the two rows of «Быть или не быть»
    # (212, 213) are one text, the drop chosen at the table.
    208: (47489, 47490, 47491, 47492),
    209: (47493, 47494, None, 47495),
    210: (47496, 47497, None, 47498),
    211: (47499, 47500, None, 47501),
    212: (47502, 47503, None, 47504),
    213: (47502, 47503, None, 47504),
    214: (47505, 47506, None, 47507),
    215: (47508, 47509, None, 47510),
    216: (47515, 47516, None, 47517),
    217: (47518, 47519, 47520, 47521),
    218: (47522, 47523, None, 47524),
    # «Шутка висельника»; «Просьба о помощи» and the son's raid.
    219: (47485, 47486, 47487, 47488),
    220: (47479, 47480, None, 47481),
    221: (47479, 47482, 47483, 47484),
    # Натти and Джо (47330-47382): the seven guns of «Веселый праздник»
    # share the notfinish and finish stored once, 47338-47339.
    222: (47330, 47331, None, 47332),
    223: (47333, 47334, None, 47335),
    224: (47336, 47337, 47338, 47339),
    225: (47340, 47341, 47338, 47339),
    226: (47342, 47343, 47338, 47339),
    227: (47344, 47345, 47338, 47339),
    228: (47346, 47347, 47338, 47339),
    229: (47348, 47349, 47338, 47339),
    230: (47350, 47351, 47338, 47339),
    231: (47352, 47353, None, 47354),
    232: (47355, 47356, 47357, 47358),
    233: (47359, 47360, 47361, 47362),
    234: (47363, 47364, 47365, 47366),
    235: (47367, 47368, 47369, 47370),
    236: (47371, 47372, 47373, 47374),
    237: (47379, 47380, 47381, 47382),
    # Генри's window (server/setcraft.py): «Как менять старые комплекты»,
    # 24572-24574 in a row; «Обмен б/у снаряжения», 24376/24377, which the
    # file ends with nothing, ends in the same help line.
    238: (24572, 24573, None, 24574),
    239: (24376, 24377, None, 24574),
    # Абри (2026-10-12, the owner's «Делаем Абри»): the rows 450-599, each text read
    # in texts.xml by hand; a slot None is one the file has no line for, and a
    # name None is a DESIGNED one (data/quests.json says which, row by row).
    450: (46871, 46872, 46873, 46874),
    451: (46875, 46876, None, 46877),
    452: (46878, 46879, 46880, 46881),
    453: (46882, 46883, None, 46884),
    454: (46885, 46886, None, 46887),
    455: (46888, 46889, 46890, 46891),
    456: (46892, 46893, None, 46894),
    457: (46895, 46896, None, 46897),
    458: (46898, 46899, None, 46900),
    459: (46901, 46902, None, 46903),
    460: (46904, 46905, 46906, 46907),
    461: (46908, 46909, 46910, 46911),
    462: (46912, 46913, 46914, 46915),
    463: (46916, 46917, 46918, 46919),
    464: (46920, 46921, None, 46922),
    465: (46923, 46924, None, 46925),
    466: (46926, 46927, None, 46928),
    467: (46929, 46930, 46931, 46932),
    470: (46967, 46968, 46969, 46970),
    471: (46971, 46972, None, 46973),
    472: (46974, 46975, 46976, 46977),
    473: (46978, 46979, None, 46980),
    474: (46981, 46982, None, 46983),
    475: (46984, 46985, None, 46986),
    477: (None, 46990, 46991, 46992),
    478: (46999, 47000, None, 47001),
    479: (46993, 46994, None, 46995),
    480: (46996, 46997, None, 46998),
    481: (47002, 47003, 47004, 47005),
    482: (47006, 47007, 47008, 47009),
    485: (47010, 47011, None, 47012),
    486: (47013, 47014, 47015, 47016),
    487: (47017, 47018, None, 47019),
    488: (47020, 47021, 47022, 47023),
    489: (47024, 47025, 47026, 47027),
    491: (61902, 61903, None, None),
    492: (61904, 61905, None, None),
    493: (61906, 61907, None, None),
    494: (61908, 61909, None, None),
    495: (61910, 61911, None, None),
    496: (61912, 61913, None, None),
    497: (61914, 61915, None, None),
    498: (61916, 61917, None, None),
    499: (61918, 61919, None, None),
    500: (61920, 61921, None, None),
    501: (61922, 61923, None, None),
    502: (61924, 61925, None, None),
    507: (47028, 47029, None, 47030),
    513: (47163, 47164, None, 47165),
    514: (47166, 47167, 47168, 47169),
    515: (47170, 47171, None, 47172),
    516: (47173, 47174, None, 47175),
    522: (49721, 49722, 49723, 49724),
    523: (49725, 49726, 49727, 49724),
    524: (49728, 49729, 49730, 49724),
    525: (49731, 49732, 49733, 49724),
    526: (49734, 49735, 49733, 49724),
    527: (49736, 49737, 49738, 49724),
    528: (49739, 49740, 49733, 49724),
    529: (49741, 49742, 49743, 49724),
    532: (49760, 49761, 49762, 49763),
    533: (49764, 49765, 49766, 49763),
    534: (49767, 49768, 49769, 49763),
    535: (49770, 49771, 49772, 49763),
    536: (49773, 49774, 49775, 49763),
    537: (49776, 49777, 49778, 49763),
    538: (49779, 49780, 49781, 49763),
    564: (None, 49114, None, 49115),
    565: (49148, 49149, None, 49150),
    566: (49151, 49152, 49154, 49155),
    567: (49156, 49157, None, 49158),
    568: (49159, 49160, None, None),
    569: (49162, 49163, None, 49164),
    570: (49165, 49166, None, 49167),
    571: (49168, 49169, None, 49170),
    572: (49171, 49172, None, 49173),
    573: (49174, 49175, None, 49176),
    574: (None, 49177, None, 49178),
    575: (49179, 49180, None, 49181),
    576: (49182, 49183, None, 49184),
    577: (49185, 49187, None, 49188),
    578: (49189, 49190, None, 49191),
    # Донгола (2026-10-13, the owner's «и потом сделай донголу тоже»): the rows
    # 630-799, each text read in texts.xml by hand; a slot None is one the file has
    # no line for, or a name the row writes itself (data/quests.json says which, row
    # by row). The rows not here are DESIGNED (the mines' gates 715-720, the
    # lotteries' names and starts 721/722, the ways 706/707/748/749/762, the fees
    # of the ways into Zone 49 733/744, the boss hours of 653).
    630: (46965, 48539, 48540, 48541),
    631: (46961, 48542, 48543, 48544),
    632: (62262, 62264, None, 59830),
    633: (62268, 62269, None, 59830),
    634: (None, 62272, 62273, None),
    635: (None, 62272, 62273, None),
    636: (62257, 62258, None, 62259),
    638: (48545, 48546, None, 48547),
    639: (48548, 48549, None, 48550),
    640: (48551, 48552, None, 48553),
    641: (48554, 48555, 48556, 48557),
    642: (48558, 48559, None, 48560),
    643: (48561, 48562, None, 48563),
    644: (48564, 48565, None, 48566),
    645: (48567, 48568, None, 48569),
    646: (48570, 48571, None, 48572),
    647: (48573, 48574, None, 48575),
    648: (48576, 48577, None, 48578),
    649: (48579, 48580, None, 48581),
    650: (48582, 48583, None, 48584),
    651: (48585, 48586, None, 48587),
    652: (48588, 48589, None, 48590),
    654: (48594, 48595, 48596, 48597),
    655: (48598, 48599, 48600, 48601),
    656: (48602, 48603, None, 48604),
    657: (48605, 48606, None, 48607),
    658: (48608, 48609, 48610, 48611),
    659: (48612, 48613, None, 48614),
    660: (48615, 48616, None, 48617),
    661: (48618, 48619, None, 48620),
    662: (48621, 48622, None, 48623),
    663: (48624, 48625, None, 48626),
    664: (48627, 48628, None, 48629),
    666: (48630, 48631, None, 48632),
    667: (48633, 48634, 48635, 48636),
    668: (48637, 48638, None, 48639),
    669: (48640, 48641, None, 48642),
    670: (48643, 48644, 48645, 48646),
    671: (48647, 48648, None, 48649),
    672: (48650, 48651, None, None),
    673: (48652, 48653, None, 48654),
    674: (48655, 48656, None, 48657),
    675: (48658, 48659, 48660, 48661),
    676: (48662, 48663, None, 48664),
    677: (48665, 48666, 48667, 48668),
    678: (48669, 48670, None, 48671),
    679: (48672, 48673, None, 48674),
    680: (48675, 48676, None, 48677),
    681: (48678, 48679, None, 48680),
    682: (48681, 48682, 48683, 48684),
    683: (48685, 48686, 48687, 48688),
    684: (48689, 48690, 48691, 48692),
    685: (48693, 48694, None, 48695),
    686: (48708, 48709, None, 48710),
    687: (48711, 48712, 48713, 48714),
    689: (48715, 48716, 48717, 48718),
    690: (48719, 48720, None, 48721),
    691: (48722, 48723, None, 48724),
    692: (48725, 48726, None, 48727),
    693: (48728, 48729, None, 48730),
    694: (48731, 48732, 48733, 48734),
    695: (60007, 60008, None, 60009),
    696: (60010, 60011, None, 60012),
    697: (60013, 60014, 60015, 60016),
    698: (60017, 60018, 60020, 60019),
    699: (60023, 60024, None, 60025),
    700: (60026, 60027, 60028, 60029),
    701: (60030, 60031, None, 60032),
    702: (None, 60021, None, 60022),
    703: (60033, 60034, 60035, 60036),
    704: (60037, 60038, 60039, 60040),
    705: (60041, 60042, None, 60043),
    708: (61428, 61445, None, 61430),
    709: (61431, 61432, None, 25838),
    710: (61446, 61447, 61435, 61436),
    711: (61448, 61449, 61435, 61436),
    712: (61450, 61451, 61435, 61436),
    713: (61459, 61460, None, 61461),
    714: (61441, 61442, 61443, 61444),
    725: (47031, 47032, None, 47033),
    726: (47034, 47035, None, 47036),
    727: (47037, 47038, 47039, 47040),
    728: (47041, 47042, None, 47043),
    729: (47044, 47045, None, 47046),
    730: (47047, 47048, None, 47049),
    731: (47050, 47051, None, 47052),
    732: (47053, 47054, None, 47055),
    734: (47117, 47118, None, 47119),
    735: (47120, 47121, None, 47122),
    738: (47063, 47064, None, 47065),
    739: (47059, 47060, 47061, 47062),
    740: (47069, 47070, None, 47071),
    741: (47066, 47067, None, 47068),
    742: (47072, 47073, 47074, None),
    743: (47075, 47076, None, 47077),
    745: (47081, 47082, None, 47083),
    746: (47084, 47085, None, 47086),
    747: (47087, 47088, None, 47089),
    750: (47090, 47091, 47092, 47093),
    751: (47094, 47095, 47096, 47097),
    752: (47098, 47099, 47100, 47101),
    753: (47102, 47103, 47104, 47105),
    754: (47106, 47107, 47108, 47109),
    755: (47110, 47111, None, 47112),
    756: (47113, 47114, 47115, 47116),
    757: (47525, 47526, None, 47527),
    758: (49536, 49537, 49538, 49539),
    768: (26363, 26367, None, None),
    769: (26363, 26368, None, None),
    770: (26363, 26369, None, None),
    # Абу-Хамед (2026-10-14, the owner's «сделай потом абу хамед в таком же формате»):
    # the rows 880-999 and 771, each text read in texts.xml by hand; a slot None is
    # one the file has no line for, or a name the row writes itself (data/quests.json
    # says which, row by row). The rows not here are DESIGNED (the mines' gates
    # 910-915, the lotteries' names and starts 916-921, «Письмо Президента Крюгера
    # ч.2» 888 with its start sent to the Тёмная шахта, the archives' reward lists
    # 893-896 and 899).
    771: (26363, 26370, None, None),
    880: (62262, 62265, None, 59830),
    881: (62270, 62271, None, 59830),
    882: (None, 62272, 62273, None),
    883: (None, 62272, 62273, None),
    884: (62257, 62258, None, 62259),
    886: (50040, 50041, None, 50042),
    887: (50043, 50044, 50045, 50046),
    889: (50051, 50052, 50053, 50054),
    890: (None, 50052, 50053, 50054),
    891: (None, 50052, 50053, 50054),
    892: (None, 50052, 50053, 50054),
    893: (50058, 50059, 50060, 50061),
    894: (50062, 50063, 50060, 50064),
    895: (50065, 50066, 50060, 50067),
    896: (50068, 50069, 50060, 50070),
    897: (50071, 50072, 50073, 50074),
    898: (50075, 50076, 50077, 50078),
    899: (50079, 50080, 50060, 50081),
    903: (61428, 61452, None, 61430),
    904: (61431, 61432, None, 25838),
    905: (61453, 61454, 61435, 61436),
    906: (61455, 61456, 61435, 61436),
    907: (61457, 61458, 61435, 61436),
    908: (61459, 61460, None, 61461),
    909: (61441, 61442, 61443, 61444),
    922: (47245, 47246, 47247, 47248),
    923: (50093, 50094, 50095, 50096),
    925: (47176, 47177, 47178, 47179),
    926: (47180, 47181, None, 47182),
    927: (47183, 47184, None, 47185),
    928: (47186, 47187, None, 47188),
    929: (47189, 47190, None, 47191),
    930: (47192, 47193, None, 47194),
    931: (47195, 47196, None, 47197),
    932: (47198, 47199, 47200, 47201),
    933: (47202, 47203, None, 47204),
    934: (47205, 47206, 47207, 47208),
    935: (47210, 47211, None, 47212),
    942: (60527, 60528, None, 60529),
    943: (60530, 60531, 60532, 60533),
    944: (60534, 60535, 60536, 60537),
    945: (60538, 60539, 60540, 60541),
    946: (60542, 60543, 60544, 60545),
    947: (60546, 60547, 60548, 60549),
    948: (60550, 60551, None, 60552),
    949: (60573, 60574, 60572, 60575),
    950: (60576, 60577, 60572, 60578),
    951: (60579, 60580, 60572, 60581),
    952: (60582, 60583, 60572, 60584),
    953: (60585, 60586, 60572, 60587),
    954: (60588, 60589, None, None),
    955: (None, 60553, None, 60554),
    956: (None, 60553, None, 60554),
    957: (None, 60553, None, 60554),
    958: (None, 60553, None, 60554),
    959: (None, 60553, None, 60554),
    960: (60562, 60563, 60560, 60561),
    961: (60564, 60565, 60560, 60561),
    962: (60566, 60567, 60560, 60561),
    963: (60568, 60569, 60560, 60561),
    964: (60570, 60571, 60560, 60561),
    965: (49526, 49527, None, 49528),
    966: (49529, 49530, None, None),
    967: (50086, 50087, 50088, 50089),
}

RULE = {
    "transport": (
        "our type -> original text found by text inside ids 10679-10930 (lessor desks' plain "
        "vehicle names 10680-10688 and the TransObject block 10744-10930). Levels, first hit wins, "
        "lowest id within a level: exact decoded text; folded (letters and digits, lower case, "
        "ё=е); names only, one trailing variant mark stripped when it agrees with our record "
        "(P/P1/P2 premium, G gold price, A afro price). Strings starting with 'Тест' never written."),
    "quests": (
        "the quests written for this server (OWN_QUESTS; none since the black market's "
        "1,2,3,5,6 left the table on 2026-09-28) are not looked up. For the others "
        "(the wiki's, the mine's 7-8 and the valley's tutorial 11-27, story 28-45 and market, "
        "farm and mine 46-67 written from the original's lines) each text is looked up on its "
        "own, folded, with <hint> "
        "numbers, %sex?..%/%имя% macros and the '<b>Задача:</b>' task line dropped and the "
        "wiki's 'Квест: ' prefix and title-before-start removed from ours; the name as it "
        "stands, and only where the file has no such line with the wiki's ' (часть N)' suffix "
        "cut: start = the newest copy without a '№' label, its name the nearest before it "
        "however far (or none), and where every copy is labelled the one nearest after a name "
        "(<= 20 ids); notfinish = of the unlabelled copies, the valley's newest edition's "
        "(59767-59946) where it wrote one, the nearest after the start, else before; "
        "finish = the same from the later of start and notfinish; of copies that differ only "
        "in their task line, the ones with ours. An empty slot of ours is not "
        "looked up. Every written quest was checked by hand and is pinned in VERIFIED; ids = "
        "[name, start, notfinish, finish] original string ids."),
    "text": "html.unescape of the original, nothing else",
}


# --------------------------------------------------------------- original texts
_ITEM = re.compile(r'<item id="(\d+)">(.*?)</item>', re.S)


def load_texts(path):
    """id -> text with the XML entities decoded, plus md5 and size of the file.

    Stops on anything but one <item> per id, 0..N-1 without a gap: a file of
    another shape is not the one these rules were checked against.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    body = raw.decode("utf-8")
    texts = {}
    for m in _ITEM.finditer(body):
        i = int(m.group(1))
        if i in texts:
            raise SystemExit("%s: id %d twice" % (path, i))
        texts[i] = html.unescape(m.group(2))
    if body.count("<item ") != len(texts) or set(texts) != set(range(len(texts))):
        raise SystemExit("%s: not one <item> per id 0..N-1" % path)
    return texts, hashlib.md5(raw).hexdigest(), len(raw)


# --------------------------------------------------------------- folding
_HINT = re.compile(r"<hint>.*?</hint>", re.S | re.I)
_TASK = re.compile(r"<b>\s*Задача\s*:?\s*</b>.*\Z", re.S | re.I)
_MACRO = re.compile(r"%sex\?[^%]*%|%имя%", re.I)
_TAG = re.compile(r"<[^<>]*>")
_NOT_WORD = re.compile(r"[^0-9a-zа-я]+")
_MARK = re.compile(r"^(.*?)\s*[(\[]\s*([A-Za-z0-9]+)\s*[)\]]\s*$", re.S)
_WIKI_PREFIX = re.compile(r"^\s*Квест\s*:\s*")
_WIKI_PART = re.compile(r"\s*\(\s*часть\s*\d+\s*\)\s*$", re.I)


def fold(text):
    """Letters and digits only, lower case, ё as е: what two copies of a text share."""
    text = _TAG.sub(" ", _MACRO.sub("", text))
    return _NOT_WORD.sub("", text.lower().replace("ё", "е"))


def fold_quest(text):
    """fold() without the quest number label and the trailing task line."""
    return fold(_TASK.sub("", _HINT.sub("", text)))


def is_test(text):
    return text.strip().lower().startswith(TEST_PREFIX)


# --------------------------------------------------------------- transport
def mark_fits(mark, rec):
    """Whether a variant mark says the same as our record about the vehicle."""
    mark = mark.upper()
    if mark == "P":
        return int(rec.get("premium", 0)) >= 1
    if mark in ("P1", "P2"):
        return int(rec.get("premium", 0)) == int(mark[1])
    if mark == "G":
        return int(rec.get("g_cost", 0)) > 0
    if mark == "A":
        return int(rec.get("cost", 0)) > 0
    return False


def find_vehicle_text(texts, ours, rec, is_name):
    """(original id, level) of our name or description, or (None, None)."""
    if not ours:
        return None, None
    block = [i for i in TRANSPORT_BLOCK if not is_test(texts[i])]
    want = fold(ours)
    levels = [
        ("exact", lambda t: t == ours),
        ("folded", lambda t: fold(t) == want),
    ]
    if is_name:
        def marked(t):
            m = _MARK.match(t)
            return bool(m) and fold(m.group(1)) == want and mark_fits(m.group(2), rec)
        levels.append(("marker", marked))
    for level, test in levels:
        hits = [i for i in block if test(texts[i])]
        if hits:
            return min(hits), level
    return None, None


def build_transport(texts, table):
    out, levels = {}, {}
    for key in sorted(table, key=int):
        rec = table[key]
        name_id, nlev = find_vehicle_text(texts, rec.get("name"), rec, True)
        desc_id, dlev = find_vehicle_text(texts, rec.get("desc"), rec, False)
        out[str(int(key))] = {
            "name": texts[name_id] if name_id is not None else None,
            "desc": texts[desc_id] if desc_id is not None else None,
            "name_id": name_id,
            "desc_id": desc_id,
        }
        for part, lev in (("name", nlev), ("desc", dlev)):
            key_ = "%s_%s" % (part, lev or "none")
            levels[key_] = levels.get(key_, 0) + 1
    return out, levels


# --------------------------------------------------------------- quests
def wiki_name(name):
    return _WIKI_PART.sub("", _WIKI_PREFIX.sub("", name)).strip()


def wiki_start(start, title):
    """Our start without the quest's title the wiki glued in front of it."""
    m = re.match(r"^\s*" + re.escape(title) + r"\s*<\s*br\s*/?\s*>", start, re.I)
    return start[m.end():] if m else start


def nearest(cands, anchor):
    """The candidate nearest after the anchor, else the nearest before it."""
    if not cands:
        return None
    return min(cands, key=lambda c: (c <= anchor, abs(c - anchor), c))


class QuestIndex:
    """folded text -> original ids, built once over the whole file.

    ... and which of several copies of one text to take: the unlabelled
    ones (plain), and of those the newest edition's where it has one
    (newest)."""

    def __init__(self, texts):
        self.texts = texts
        self.by_fold = {}
        for i in sorted(texts):
            f = fold_quest(texts[i])
            if f:
                self.by_fold.setdefault(f, []).append(i)

    def ids(self, text):
        f = fold_quest(text) if text else ""
        return list(self.by_fold.get(f, [])) if f else []

    def numbered(self, i):
        """Whether a line carries its quest's number label (<hint><B>№...)."""
        return bool(_NUMBER_LABEL.search(self.texts[i]))

    def plain(self, ids):
        """The copies without the number label, or all of them if none is."""
        out = [i for i in ids if not self.numbered(i)]
        return out or list(ids)

    def newest(self, ids):
        """plain(), and of those the ones the newest edition of the valley
        wrote (NEWEST_EDITION) when it wrote one: «Разведчик»'s finish is
        59861, not the 2012 edition's 24425, which says "кто—то" with an em
        dash, though its start is the 2012 line (the new edition did not
        write that one again)."""
        out = self.plain(ids)
        return [i for i in out if i in NEWEST_EDITION] or out

    def same_task(self, ids, text):
        """Of copies that fold equal once their task lines are dropped, the
        ones whose task line is ours too, if any is: «Еда» writes 'Прошу,
        найди еще мяса для деревни!' twice, its start with the task 'найти
        еще мяса для Сабира' (59875) and its notfinish with 'отнести
        найденное мясо Сабиру' (59877), and without the task line the one is
        the other. Only the quest number label is dropped here."""
        want = fold(_HINT.sub("", text or ""))
        out = [i for i in ids if fold(_HINT.sub("", self.texts[i])) == want]
        return out or list(ids)


# "<hint><B>№0000158</B></hint>", "<hint><B>Задание №B81000024</B>...".
_NUMBER_LABEL = re.compile(r"<hint>\s*<b>[^<]*№", re.I)
# The Nubian valley's newest edition (the docstring's 59767-59946): where it
# and an older line carry the same text, its copy is the one taken.
NEWEST_EDITION = range(59767, 59947)


def match_quest(index, row):
    """[name, start, notfinish, finish] original ids for one of our rows, or None."""
    title = wiki_name(row["name"])
    # The name as it stands first -- the file has «Похищенный груз (часть
    # 2)» as a line of its own, beside «Похищенный груз» -- and only where
    # it has no such line, the wiki's page title cut to the game's name
    # ("Муж (часть 2)" is "Муж").
    names = index.ids(_WIKI_PREFIX.sub("", row["name"]).strip()) or index.ids(title)
    start = wiki_start(row.get("start") or "", title)
    starts = index.ids(start)
    if int(row["type"]) in (159, 632, 880):
        # The rides share their greeting; only the trailing task names the
        # destination. Compare the whole text with the reviewed new hours,
        # rather than falling back to the last city's copy after a mismatch.
        wanted = fold(_HINT.sub("", start))
        matching = []
        for candidate in starts:
            original_start = (index.texts[candidate].replace("12:00", "13:00")
                              .replace("16:00", "17:00").replace("23:00", "21:00"))
            if fold(_HINT.sub("", original_start)) == wanted:
                matching.append(candidate)
        starts = matching
    unlabelled = [s for s in starts if not index.numbered(s)]
    if unlabelled:
        # The newest edition, and the name nearest before it, however far
        # -- of the copies with our task line, where they differ in it.
        start_id = max(index.same_task(unlabelled, start))
        before = [n for n in names if n < start_id]
        name_id = max(before) if before else None
    else:
        pairs = [(s - n, n, s) for n in names for s in starts if 0 < s - n <= MAX_GAP]
        if not pairs:
            return None
        _, name_id, start_id = min(pairs)
    notfinish_id = nearest(index.newest(index.same_task(
        index.ids(row.get("notfinish")), row.get("notfinish"))), start_id)
    anchor = max(i for i in (start_id, notfinish_id) if i is not None)
    finish_id = nearest(index.newest(index.same_task(
        index.ids(row.get("finish")), row.get("finish"))), anchor)
    return [name_id, start_id, notfinish_id, finish_id]


def one_passage_out(original, own):
    """Whether our text is the original's with one passage taken out and
    nothing written in, compared folded (letters and digits, any case).

    What a row's own_texts (server/quests.py) may do to the original's line:
    cut what this server cannot stand behind -- 158's «Если вы хотите быстро
    добраться до тюрьмы, у вас должен быть вид на жительство или
    гражданство», Мортимер's cashing's «Как для лица не имеющего гражданства
    или вида на жительство» (301-303), the owner's cut of (P) -- and not
    rewrite it. Case is not a rewrite: 301's «будет» opens the sentence now.
    """
    a, b = fold(original), fold(own)
    if len(b) > len(a):
        return False
    head = 0
    while head < len(b) and a[head] == b[head]:
        head += 1
    tail = 0
    while tail < len(b) - head and a[len(a) - 1 - tail] == b[len(b) - 1 - tail]:
        tail += 1
    return head + tail == len(b)


def build_quests(texts, rows):
    index = QuestIndex(texts)
    out, unverified = {}, {}
    seen = set()
    for row in rows:
        qtype = int(row["type"])
        seen.add(qtype)
        if qtype in OWN_QUESTS:
            if row.get("wiki_type") or row.get("source"):
                raise SystemExit("quest %d is listed as our own but carries a wiki source" % qtype)
            continue
        own = frozenset(row.get("own_texts") or ())
        ids = match_quest(index, row)
        if ids is None and "start" in own and qtype in VERIFIED:
            # The matcher finds a row by its start, and a start of the row's
            # own is not the original's on purpose: 301-303 lost their
            # opening words to the cut of (P) (2026-10-02), and no line of
            # the file folds to what is left (158's cut sentence came after
            # its task line, which the fold drops anyway). The ids checked by
            # hand stand, held to what the row still shares with the file:
            # its name, word for word -- or, where the name is the row's own
            # too (the warehouses' boxes, 765-767, without the tier «(Бж.)»),
            # the original's but for one passage -- and its own start, the
            # original's but for one passage (below).
            ids = list(VERIFIED[qtype])
            name_id = ids[0]
            if "name" in own:
                name_ok = name_id is not None and one_passage_out(texts[name_id], row["name"])
            else:
                name_ok = name_id is not None and fold(texts[name_id]) == fold(row["name"])
            if not name_ok:
                raise SystemExit("quest %d: own start, and the name is not the original's %r"
                                 % (qtype, name_id))
        if qtype not in VERIFIED:
            if ids is not None:
                unverified[qtype] = ids
            continue
        if ids is None or tuple(ids) != VERIFIED[qtype]:
            raise SystemExit("quest %d: verified %r, matcher found %r"
                             % (qtype, VERIFIED[qtype], ids))
        for key, i in zip(QUEST_KEYS, ids):
            original = texts[i] if i is not None else ""
            if qtype in (158, 636, 884) and key == "start":
                original = original.replace("12:00", "13:00").replace("16:00", "17:00").replace("23:00", "21:00")
            if key in own and i is not None and not one_passage_out(original, row.get(key) or ""):
                raise SystemExit("quest %d: its own %s is not the original's %d with one"
                                 " passage taken out" % (qtype, key, i))
        rec = {k: (texts[i] if i is not None else None) for k, i in zip(QUEST_KEYS, ids)}
        rec["ids"] = ids
        rec["confidence"] = "high"
        out[str(qtype)] = rec
    missing = sorted(set(VERIFIED) - seen)
    if missing:
        raise SystemExit("verified quests not in data/quests.json: %r" % missing)
    return out, unverified


# --------------------------------------------------------------- output
def load_json(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def build(source=None):
    """Return (document, quests the matcher found but nobody has checked)."""
    source = source or os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_SOURCE
    texts, md5, size = load_texts(source)
    transport, levels = build_transport(texts, load_json("transport.json")["types"])
    # The hand-written table and its generated companions (data/questgen_*.json,
    # server/quests.py companion_paths): one string table for all of them.
    rows = load_json("quests.json")["quests"]
    for name in sorted(os.listdir(HERE)):
        if name.startswith("questgen_") and name.endswith(".json"):
            rows += load_json(name)["quests"]
    quests, unverified = build_quests(texts, rows)
    counts = {
        "transport_types": len(transport),
        "transport_names": sum(1 for r in transport.values() if r["name"] is not None),
        "transport_descs": sum(1 for r in transport.values() if r["desc"] is not None),
        "quests": len(quests),
        "quests_own_skipped": len(OWN_QUESTS),
    }
    counts.update(("transport_" + k, v) for k, v in levels.items())
    doc = {
        "_meta": {
            "source": os.path.basename(source),
            "source_md5": md5,
            "source_size": size,
            "source_rows": len(texts),
            "rule": RULE,
            "counts": counts,
        },
        "transport": transport,
        "quests": quests,
    }
    return doc, unverified


def dumps(doc):
    return json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True)


def dump(doc, path):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(doc))


def main():
    doc, unverified = build()
    dump(doc, OUT)
    with open(OUT, "rb") as fh:
        raw = fh.read()
    print("wrote %s: %d bytes, sha256 %s" % (OUT, len(raw), hashlib.sha256(raw).hexdigest()))
    print(json.dumps(doc["_meta"]["counts"], ensure_ascii=False, sort_keys=True))
    for qtype, ids in sorted(unverified.items()):
        print("quest %d matched %r but is not in VERIFIED: not written" % (qtype, ids))


if __name__ == "__main__":
    main()
