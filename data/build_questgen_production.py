"""A town's plant as quest rows: data/questgen_production.json.

The original ran its mines' sorting, its processing base and its ammunition
factory as quests of one family, numbered CrBQ№1010001-1010178 in texts.xml
(40301-40718): each a row whose start says what the line takes -- «Запустить
первую очередь обработки? ... Требуется 120 частей сортированной свинцовой
руды» -- and whose finish closes the cycle -- «Цикл закончен. Повторное
использование возможно через 20 минут». Every run of the family lists the
five cities in one order, (ВХ), (Аб), (Дн), (АХ), (Мр) -- the gold of the
third line rising 0.02, 0.03, 0.04, 0.05 and Мероэ's 0.04 back, the sorting's
pieces 10, 11, 12, 13, 14 -- and each run of fifteen the three ores in one
order, lead, saltpetre, copper (the start names its ore). The ammunition runs
are one row a calibre, twelve (12мм ... 8.6x70), each factory making those its
map label names.

This builder writes the rows of the cities in OPEN from those texts: the
name, start and notfinish of each (the finish where the file has one) and
what it asks -- the pieces, parts and sacks and the gold, read out of the
start itself, not copied by hand -- and adds what the file does not say,
DESIGNED and said in each row's why: what a run makes, the experience, the
band, the cooldown, the giver of each (the city's own terminal and lines).
A city is added by adding its entry to CITIES (its terminals, lines,
factory, calibres, band and type range) and its name to OPEN; the code does
not know which city it builds.

Types: CITIES[..]["base"] on, a block of 100 a city; Вади-Хальфа's is
13000-13099, Абри's 13100-13199, Донгола's 13200-13299, Абу-Хамед's
13300-13399 (the registry's generators, 10000-29999; 10000-12999 are the
weapon and set crafts').

    LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/build_questgen_production.py

The source is LAVA_ORIG_TEXTS (default /mnt/c/Users/gmkrt/Downloads/texts.xml).
"""
import html
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEXTS = "/mnt/c/Users/gmkrt/Downloads/texts.xml"
OUT = os.path.join(HERE, "questgen_production.json")
RES = os.environ.get("LAVA_RES", "")

# The ores, in the order of every run of fifteen; what each line makes of one.
ORES = ("plumbum", "nitre", "copper")
SACK_OF = {"plumbum": "bullet", "nitre": "powder", "copper": "shell"}
ORE_WORD = {"plumbum": "свинцов", "nitre": "селитр", "copper": "медн"}
# The ammunition runs, one row a calibre (CrBQ№1010061 + index).
CALIBRES = ("12мм", "9мм", "5.56х45", "7.62х54", "7.62х51", "0.45", "7.62х25", "7.62х39",
            "СП-10", "5.7x28", "ПАБ-9", "8.6x70")
# objects.xml's word for a calibre, where a factory makes it: the (P) round its
# label names is Ammo_<word>_KS_P, and what it makes here the same without the
# (P) -- the owner's decision 12 (the original factories made only (P) rounds).
# Абри's «9ММ НАТО» and «5.7x28 (SS190)» are Ammo_9mmNato_KS and
# Ammo_SS190_KS, the rounds «9мм НАТО $КС» and «5.7x28 $КС»; Донгола's
# «5.56x45ММ НАТО» and «ПАБ-9» Ammo_556x45_KS and Ammo_SP_5_6_KS, «5.56х45мм
# НАТО $КС» and «ПАБ–9 $КС» (CALIBRES writes the first with a Cyrillic «х»,
# as the texts do); Абу-Хамед's «7.62x54R», «7.62x51ММ НАТО» and «8.6x70
# (.338 Lapua Magnum)» Ammo_762x54R_KS, Ammo_762x51_KS and Ammo_86x70_KS,
# «7.62х54R $КС», «7.62х51мм НАТО $КС» and «8.6x70 $КС» (the first two with
# the Cyrillic «х» of CALIBRES).
CALIBRE_WORD = {"12мм": "12mm", "СП-10": "SP_10_12", "9мм": "9mmNato", "5.7x28": "SS190",
                "5.56х45": "556x45", "ПАБ-9": "SP_5_6",
                "7.62х54": "762x54R", "7.62х51": "762x51", "8.6x70": "86x70"}

# The blocks of the family: the first CrBQ number of each, its name row (None:
# the file has none), its finish row (None: none either; FINISH_BORROWED is
# taken, DESIGNED).
SORT_1 = dict(first=1010109, name=None, finish=40573)
SORT_PREP = dict(first=1010124, name=40602, finish=40605)
SORT_2 = dict(first=1010139, name=40634, finish=None)
SORT_3 = dict(first=1010154, name=40665, finish=None)
LINE_1 = dict(first=1010001, name=40301, finish=40304)
LINE_PREP = dict(first=1010016, name=40333, finish=None)
LINE_2 = dict(first=1010031, name=40364, finish=40367)
LINE_3 = dict(first=1010046, name=40396, finish=None)
AMMO_1 = dict(first=1010061, name="before", finish=None)
AMMO_PREP = dict(first=1010073, name="before", finish=None)
AMMO_2 = dict(first=1010085, name="before", finish=None)
AMMO_3 = dict(first=1010097, name="before", finish=None)
NAMES = {40602: "Запуск второго конвейера", 40634: "Сортировка. На двух конвейерах.",
         40665: "Сортировка. На трёх конвейерах.", 40301: "Запуск одной линии обработки.",
         40333: "Подготовка второй линии.", 40364: "Запуск двух линий обработки.",
         40396: "Запуск третьей линий обработки. G.", 40573: "Так, вот это сгодится!",
         40605: "Теперь можешь работать на двух конвейерах!", 40304: "Цикл закончен.",
         40367: "Цикл закончен."}
# Where the file has no finish: the sorting's is its first line's, a line's or
# the factory's «Цикл закончен.» (40367) -- the words of the family, DESIGNED.
SORT_FINISH, LINE_FINISH = 40573, 40367
# The first sorting line has no name row: the terminal's own, «Сортировка»
# (10526), DESIGNED.
SORT_NAME = "Сортировка"

# What the file does not say, DESIGNED (2026-09-28):
#   one run of a terminal feeds one line of the base -- its parts are the
#   first line's need (ВХ: 10 pieces of lead, 120 parts);
#   a line makes three sacks, so a factory's first line (ВХ: 3 bullets, 12
#   powder, 9 cases) is eight runs of the base, eighty pieces of ore;
#   the factory's first line makes 600 rounds;
#   the gold line gives a quarter more («повышенную норму») and five times
#   the experience of the same run without the gold («в 5 раз больше опыта»);
#   experience: 2 a piece sorted into Промышленность and «Добыча», 10 a sack
#   and one a tenth of a round into Промышленность and «Переработка»;
#   the base's and the factory's lines rest 20 minutes after a cycle, the
#   finish's own words; the sorting does not (its texts say nothing).
SACKS_PER_LINE = 3
ROUNDS_PER_LINE = 600
GOLD_BONUS = 1.25
GOLD_XP = 5
COOLDOWN = 20 * 60

CITIES = {
    # Вади-Хальфа: the mines' terminals WH_plumbum/nitre/copper_sorting in the
    # control rooms 658/659/657, the base 199's WH_bullet/powder/shell_creator,
    # the factory 198's WH_ammo_creator, whose label reads «Производство
    # боеприпасов Вади Хальфы: 12-й калибр (P), СП-10 (P)»; the band of the
    # mines' gates, «Вход разрешен персонажам 4-8 ур.».
    "ВХ": dict(index=0, band=(4, 8), base=13000,
               sorters={"plumbum": 1359, "nitre": 1363, "copper": 1367},
               lines={"plumbum": 1371, "nitre": 1375, "copper": 1379},
               assembler=1383, calibres=("12мм", "СП-10")),
    # Абри (2026-10-12): the terminals AB_plumbum/nitre/copper_sorting in the
    # control rooms 662/661/660 of its lead, saltpetre and copper mines
    # («Шахта Абри: Добыча свинца / селитры / меди, Вход разрешен персонажам
    # 8-12 ур.»), the base 207's AB_bullet/powder/shell_creator, the factory
    # 206's AB_ammo_creator, whose label reads «Производство боеприпасов
    # Абри: 9ММ НАТО, 5.7x28 (SS190)»; the band of the mines' gates.
    "АБ": dict(index=1, band=(8, 12), base=13100,
               sorters={"plumbum": 1360, "nitre": 1364, "copper": 1368},
               lines={"plumbum": 1372, "nitre": 1376, "copper": 1380},
               assembler=1384, calibres=("9мм", "5.7x28")),
    # Донгола (2026-10-13): the terminals DN_plumbum/nitre/copper_sorting in
    # the control rooms 665/664/663 of its lead, saltpetre and copper mines
    # («Шахта Донголы: Добыча свинца / селитры / меди, Вход разрешен
    # персонажам 12-15 ур.»), the processing centre 212's DN_bullet/powder/
    # shell_creator («Центр Переработки Донголы»), the factory 211's
    # DN_ammo_creator, whose label reads «Производство боеприпасов Донголы:
    # 5.56x45ММ НАТО (P), ПАБ-9 (P)»; the band of the mines' gates, as
    # Вади-Хальфа's and Абри's are theirs -- one short of the town's 12-16: a
    # character of the 16th enters no mine of Донгола.
    "ДН": dict(index=2, band=(12, 15), base=13200,
               sorters={"plumbum": 1361, "nitre": 1365, "copper": 1369},
               lines={"plumbum": 1373, "nitre": 1377, "copper": 1381},
               assembler=1385, calibres=("5.56х45", "ПАБ-9")),
    # Абу-Хамед (2026-10-14, the owner's «сделай потом абу хамед в таком же
    # формате»): the terminals AH_plumbum/nitre/copper_sorting in the control
    # rooms 668/667/666 of its lead, saltpetre and copper mines («Шахта
    # Абу-Хамеда: Добыча свинца / селитры / меди<br>Вход разрешен персонажам
    # 15-20 ур.», L317-L319), the processing centre 217's AH_bullet/powder/
    # shell_creator («Центр Переработки Абу-Хамеда», L316), the factory 216's
    # AH_ammo_creator, whose label reads «Производство боеприпасов
    # Абу-Хамеда: 7.62x54R (P), 7.62x51ММ НАТО (P), 8.6x70 (.338 Lapua
    # Magnum) (P)» (L315); the band of the mines' gates, 15-20: a character
    # of the 15th enters Донгола's mines and Абу-Хамед's both.
    "АХ": dict(index=3, band=(15, 20), base=13300,
               sorters={"plumbum": 1362, "nitre": 1366, "copper": 1370},
               lines={"plumbum": 1374, "nitre": 1378, "copper": 1382},
               assembler=1386, calibres=("7.62х54", "7.62х51", "8.6x70")),
}
OPEN = ("ВХ", "АБ", "ДН", "АХ")

_ITEM = re.compile(r'<item id="(\d+)">(.*?)</item>', re.S)
_START = re.compile(r"^<hint><B>CrBQ№(\d+)</B></hint>")
_NOTFINISH = re.compile(r"^<hint>CrBQ<B>№(\d+)</B></hint>")


def load_texts(path):
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    return {int(m.group(1)): html.unescape(m.group(2)) for m in _ITEM.finditer(body)}


def load_objects():
    path = os.path.join(RES, "database", "objects.xml")
    if not os.path.isfile(path):
        raise SystemExit("set LAVA_RES to the client's res directory (database/objects.xml)")
    with open(path, encoding="utf-8", errors="replace") as fh:
        txt = fh.read()
    return {m.group(3): int(m.group(1)) for m in re.finditer(
        r'<object type_id="(\d+)" root_type_id=\s*"(\d+)" name="([^"]*)"', txt)}


def crbq(T):
    """CrBQ number -> (start row, notfinish row)."""
    starts, notfin = {}, {}
    for i, t in T.items():
        m = _START.match(t)
        if m:
            starts[int(m.group(1))] = i
        m = _NOTFINISH.match(t)
        if m:
            notfin[int(m.group(1))] = i
    return {n: (s, notfin.get(n)) for n, s in starts.items()}


def gold(text):
    """The gold a start asks, in hundredths («и 0.02 G»), or 0."""
    m = re.search(r"и\s*([0-9.]+)\s*G", text)
    return int(round(float(m.group(1)) * 100)) if m else 0


def number(text, pattern):
    m = re.search(pattern, text)
    if not m:
        raise SystemExit("texts.xml: %r not in %r" % (pattern, text))
    return [int(g) for g in m.groups()]


def half_up(x):
    return int(math.floor(x + 0.5))


class City:
    def __init__(self, key, T, rows, objects):
        self.key, self.T, self.rows, self.objects = key, T, rows, objects
        self.c = CITIES[key]
        self.k = self.c["index"]
        self.next_type = self.c["base"]
        self.out = []

    def thing(self, name):
        if name not in self.objects:
            raise SystemExit("objects.xml has no %s" % name)
        return self.objects[name]

    def ore(self, o):
        return self.thing("%s_ore_%d" % (o, self.k + 1))

    def sorted_(self, o):
        return self.thing("%s_ore_sorting_%d" % (o, self.k + 1))

    def sack(self, o):
        return self.thing("%s_sack_%d" % (SACK_OF[o], self.k + 1))

    def texts(self, block, number_, ore_word=None):
        """(name, start, notfinish, finish, ids) of one row of the family."""
        start_id, nf_id = self.rows[number_]
        T = self.T
        if ore_word and ore_word not in T[start_id]:
            raise SystemExit("CrBQ№%d does not name its ore (%s)" % (number_, ore_word))
        if block["name"] == "before":
            name_id = start_id - 1
            if not T[name_id].startswith(("Производство патронов", "Подготовить вторую линию")):
                raise SystemExit("texts.xml %d is no name of CrBQ№%d" % (name_id, number_))
        else:
            name_id = block["name"]
            if name_id is not None and T[name_id] != NAMES[name_id]:
                raise SystemExit("texts.xml %d is not %r" % (name_id, NAMES[name_id]))
        fin_id = block["finish"]
        if fin_id is not None and T[fin_id].split("<")[0] != NAMES[fin_id]:
            raise SystemExit("texts.xml %d is not %r" % (fin_id, NAMES[fin_id]))
        name = T[name_id] if name_id is not None else SORT_NAME
        ids = [name_id, start_id, nf_id, fin_id]
        return name, T[start_id], T[nf_id] if nf_id else "", fin_id, ids

    def add(self, row):
        row["type"] = self.next_type
        self.next_type += 1
        self.out.append(row)
        return row["type"]

    def row(self, giver, name, start, notfinish, finish_id, borrowed, objs, made, xp, spec,
            fee, repeatable, need, cooldown, why):
        lo, hi = self.c["band"]
        r = dict(type=0, kind="bring_l_obj", name=name, start=start, notfinish=notfinish,
                 finish=self.T[finish_id if finish_id is not None else borrowed],
                 give=[giver], take=[giver],
                 objs=[dict(obj=o, num=n) for o, n in objs],
                 rew_obj=[made[0]], num_rew_obj=[made[1]], rew_afro=0, rew_gold=0)
        if fee:
            r["cost_gold"] = fee
        r["rew_xp"] = {"industry": xp}
        r["rew_spec_xp"] = {spec: xp}
        r["repeatable"] = 1 if repeatable else 0
        r["service"] = True
        if cooldown:
            r["cooldown"] = cooldown
        r["level"], r["max_level"], r["q_type"] = lo, hi, 0
        if need:
            r["need_quest"] = need
        r["why"] = why
        return r

    def why(self, number_, ids, borrowed, asks, makes, xp, extra):
        name_id, start_id, nf_id, fin_id = ids
        return ("GENERATED by data/build_questgen_production.py for %s from the original's "
                "CrBQ№%d: RECOVERED %s (texts.xml %s) and what it asks, read out of its start "
                "(%s); DESIGNED %s, %d experience into Промышленность and the specialisation, "
                "the band %d-%d (the town's mines' gates, «Вход разрешен персонажам %d-%d ур.»)%s. "
                "A service: repeatable or once, outside the daily limit and the journal's count."
                % (self.key, number_,
                   "name, start and notfinish" if name_id is not None else
                   "start and notfinish (no name row: «%s», the terminal's own, DESIGNED)" % SORT_NAME,
                   ", ".join(str(i) for i in (name_id, start_id, nf_id) if i is not None)
                   + (", finish %d" % fin_id if fin_id is not None else
                      "; no finish of its own: %d's, DESIGNED" % borrowed),
                   asks, makes, xp, self.c["band"][0], self.c["band"][1], self.c["band"][0],
                   self.c["band"][1], extra))

    # --- the three stages --------------------------------------------------------------
    def sorting(self):
        for oi, o in enumerate(ORES):
            giver, ore, parts = self.c["sorters"][o], self.ore(o), self.sorted_(o)
            n1 = self.rows[SORT_1["first"] + 5 * oi + self.k]
            need1 = number(self.T[n1[0]], r"при наличии (\d+)")[0]
            line1 = number(self.T[self.rows[LINE_1["first"] + 5 * oi + self.k][0]],
                           r"Требуется (\d+) частей")[0]
            per_piece = line1 / float(need1)
            prep_type = None
            for block, pattern, again in ((SORT_1, r"при наличии (\d+)", True),
                                          (SORT_PREP, r"Принести (\d+)", False),
                                          (SORT_2, r"при наличии (\d+)", True),
                                          (SORT_3, r"при наличии (\d+)", True)):
                num = block["first"] + 5 * oi + self.k
                name, start, nf, fin, ids = self.texts(block, num, ORE_WORD[o])
                pieces = number(start, pattern)[0]
                fee = gold(start)
                plain = half_up(pieces * per_piece)
                made = half_up(plain * GOLD_BONUS) if fee else plain
                xp = 2 * pieces * (GOLD_XP if fee else 1)
                extra = ""
                if block is SORT_1:
                    extra = ("; what a run makes, %d parts, is the first line's need at the base "
                             "(%d a piece)" % (made, round(per_piece)))
                elif block is SORT_PREP:
                    extra = ("; once (the start's «его достаточно выполнить один раз» is the "
                             "second conveyor's), the double norm sorted all the same")
                else:
                    extra = "; after «Запуск второго конвейера»"
                    if fee:
                        extra += ", a quarter more for the gold and five times the experience"
                t = self.add(self.row(
                    giver, name, start, nf, fin, SORT_FINISH, [(ore, pieces)], (parts, made), xp,
                    "mining", fee, again, prep_type if block in (SORT_2, SORT_3) else None, 0,
                    self.why(num, ids, SORT_FINISH, "%d pieces of %d" % (pieces, ore)
                             + (", %s G" % (fee / 100.0) if fee else ""),
                             "what it makes (%d parts, %d)" % (made, parts), xp, extra)))
                if block is SORT_PREP:
                    prep_type = t

    def lines(self):
        for oi, o in enumerate(ORES):
            giver, parts, sack = self.c["lines"][o], self.sorted_(o), self.sack(o)
            line1 = number(self.T[self.rows[LINE_1["first"] + 5 * oi + self.k][0]],
                           r"Требуется (\d+) частей")[0]
            prep_type = None
            for block, again in ((LINE_1, True), (LINE_PREP, False), (LINE_2, True),
                                 (LINE_3, True)):
                num = block["first"] + 5 * oi + self.k
                name, start, nf, fin, ids = self.texts(block, num, ORE_WORD[o])
                need = number(start, r"Требуется (\d+) частей")[0]
                fee = gold(start)
                plain = half_up(SACKS_PER_LINE * need / float(line1))
                made = half_up(plain * GOLD_BONUS) if fee else plain
                xp = 10 * plain * (GOLD_XP if fee else 1)
                extra = "; the line rests %d minutes after its cycle (cooldown, the finish's «через 20 минут»)" \
                    % (COOLDOWN // 60) if again else "; once, «его достаточно выполнить один раз»"
                if block in (LINE_2, LINE_3):
                    extra += "; after «Подготовка второй линии.»"
                if fee:
                    extra += "; a quarter more for the gold and five times the experience"
                t = self.add(self.row(
                    giver, name, start, nf, fin, LINE_FINISH, [(parts, need)], (sack, made), xp,
                    "recycling", fee, again, prep_type if block in (LINE_2, LINE_3) else None,
                    COOLDOWN if again else 0,
                    self.why(num, ids, LINE_FINISH, "%d parts of %d" % (need, parts)
                             + (", %s G" % (fee / 100.0) if fee else ""),
                             "what it makes (%d of %d; a first line three)" % (made, sack), xp,
                             extra)))
                if block is LINE_PREP:
                    prep_type = t

    def factory(self):
        for cal in self.c["calibres"]:
            ci = CALIBRES.index(cal)
            word = CALIBRE_WORD[cal]
            self.thing("Ammo_%s_KS_P" % word)           # the (P) round the label names
            rounds = self.thing("Ammo_%s_KS" % word)     # and its twin without it
            first = number(self.T[self.rows[AMMO_1["first"] + ci][0]],
                           r"принести (\d+) ящик\w* пуль, (\d+) меш\w* пороха, (\d+) короб\w* гильз")
            prep_type = None
            for block, again in ((AMMO_1, True), (AMMO_PREP, False), (AMMO_2, True),
                                 (AMMO_3, True)):
                num = block["first"] + ci
                name, start, nf, fin, ids = self.texts(block, num)
                if cal not in name:
                    raise SystemExit("CrBQ№%d is not %s's: %r" % (num, cal, name))
                asks = number(start, r"принести (\d+) ящик\w* пуль, (\d+) меш\w* пороха, "
                                     r"(\d+) короб\w* гильз")
                fee = gold(start)
                plain = half_up(ROUNDS_PER_LINE * asks[0] / float(first[0]))
                made = half_up(plain * GOLD_BONUS) if fee else plain
                xp = plain // 10 * (GOLD_XP if fee else 1)
                sacks = [self.sack(o) for o in ORES]
                extra = ("; %s is what the factory's label names, «(P)», made as the same round "
                         "without it (the owner's decision 12: %s of objects.xml, not its _P twin)"
                         % (cal, "Ammo_%s_KS" % word))
                extra += "; the line rests %d minutes after its cycle (cooldown, as the base's)" \
                    % (COOLDOWN // 60) if again else "; once, «его достаточно выполнить один раз»"
                if block in (AMMO_2, AMMO_3):
                    extra += "; after «Подготовить вторую линию сборки»"
                if fee:
                    extra += "; a quarter more for the gold and five times the experience"
                t = self.add(self.row(
                    self.c["assembler"], name, start, nf, fin, LINE_FINISH,
                    list(zip(sacks, asks)), (rounds, made), xp, "recycling", fee, again,
                    prep_type if block in (AMMO_2, AMMO_3) else None, COOLDOWN if again else 0,
                    self.why(num, ids, LINE_FINISH, "%d, %d and %d of %s" % (
                        asks[0], asks[1], asks[2], ", ".join(str(s) for s in sacks))
                        + (", %s G" % (fee / 100.0) if fee else ""),
                        "what it makes (%d rounds of %d)" % (made, rounds), xp, extra)))
                if block is AMMO_PREP:
                    prep_type = t

    def build(self):
        self.sorting()
        self.lines()
        self.factory()
        if self.next_type > self.c["base"] + 100:
            raise SystemExit("%s: more rows than its block of 100" % self.key)
        return self.out


NOTE = ("The plant's quest rows (sorting, processing, ammunition) of the open cities, written by "
        "data/build_questgen_production.py from the original's CrBQ family (texts.xml 40301-40718); "
        "loaded with data/quests.json (server/quests.py companion_paths). Do not edit by hand: "
        "change the builder and run it again.")


def build(texts_path):
    T = load_texts(texts_path)
    rows = crbq(T)
    objects = load_objects()
    out = []
    for key in OPEN:
        out += City(key, T, rows, objects).build()
    return {"_": NOTE, "quests": out}


def main():
    path = os.environ.get("LAVA_ORIG_TEXTS") or DEFAULT_TEXTS
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    doc = build(path)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print("%d rows (%s) -> %s" % (len(doc["quests"]),
                                   ", ".join("%d-%d" % (doc["quests"][0]["type"],
                                                        doc["quests"][-1]["type"])
                                             for _ in (0,) if doc["quests"]), out))


if __name__ == "__main__":
    main()
