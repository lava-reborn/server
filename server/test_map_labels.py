"""data/map_labels.json against the client's own res/database/locations.xml,
and the rule server/map_labels.py and launcher/MapLabels.cs both follow."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map_labels as M  # noqa: E402

from testkit import check, fails  # noqa: E402


RES = os.environ.get("LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res")
raw = open(os.path.join(RES, "database", "locations.xml"), "rb").read()
edits = M.load()


def rows_at(doc, x, y, was):
    out = []
    for m in M.ROW.finditer(doc):
        a = {k.decode(): v for k, v in M.ATTR.findall(m.group(0))}
        if (a.get("x"), a.get("y")) == (str(x).encode(), str(y).encode()):
            import html
            if html.unescape(a["text"].decode("utf-8")) == was:
                out.append(m.group(0))
    return out


print("every edit names one row the client really has")
for x, y, was, new in edits:
    if was is None:
        # An added row (a place of ours put on the map) names a cell that
        # has no row of its text yet.
        check("(%d, %d) adds %r: the cell has no row of that text" % (x, y, new),
              rows_at(raw, x, y, new), [])
        continue
    check("(%d, %d) %r: exactly one row" % (x, y, was), len(rows_at(raw, x, y, was)), 1)

print("the real file")
out, changed = M.apply(raw)
check("every edit applied", changed, len(edits))
tree = rows_at(raw, 6266, 1822, "Новогодняя Елка")
check("the farm's New Year label is gone", rows_at(out, 6266, 1822, "Новогодняя Елка"), [])
check("the farm's own name is still there, and is now the cell's only one",
      len(rows_at(out, 6266, 1822, "Ферма Говарда Хаксли <BR>Здесь можно найти задания.")), 1)
want = raw
for x, y, was, new in edits:
    if was is None:
        end = want.rfind(b"</data>")
        want = want[:end] + b'<location x="%d" y="%d" text="%s" />\n' % (
            x, y, M.escape(new).encode("utf-8")) + want[end:]
        continue
    row = rows_at(raw, x, y, was)[0]
    if new is None:
        want = want.replace(row, b"", 1)
    else:
        old = dict((k.decode(), v) for k, v in M.ATTR.findall(row))["text"]
        want = want.replace(row, row.replace(b'text="' + old + b'"',
                                             b'text="' + M.escape(new).encode("utf-8") + b'"', 1), 1)
check("nothing else moved: the file less the hidden rows, the retexted ones retexted in place",
      out, want)
# And the slums of Абри lose theirs, a line of their name (the owner's Абри,
# 2026-10-12: a name of the map knows no season; server/test_abri_cut.py),
# Донгола's pier its own (the owner's Донгола, 2026-10-13;
# server/test_dongola_cut.py), and Абу-Хамед's pier its own (the owner's
# Абу-Хамед, 2026-10-14; server/test_abuhamed_cut.py).
check("the other New Year trees, inside other places' names, stay",
      out.count("Новогодняя Елка".encode()), raw.count("Новогодняя Елка".encode()) - 4)

# The owner's cut of (P) (2026-09-30): the premium masters' camps 124, 125 and
# 130 are off the map (data/retired.json), and no name over a cell promises a
# premium thing or place any more -- the camps', the factories' calibres, the
# bar of Донгола's quarter, the machine guns of its masters' camp 96.
print("the cut of (P)")
CAMPS = {(5968, 1726): 124, (5876, 2012): 125, (6182, 1975): 130}


def texts_at(doc, x, y):
    import html
    out_ = []
    for m in M.ROW.finditer(doc):
        a = {k.decode(): v for k, v in M.ATTR.findall(m.group(0))}
        if (a.get("x"), a.get("y")) == (str(x).encode(), str(y).encode()):
            out_.append(html.unescape(a["text"].decode("utf-8")))
    return out_


PREMIUM_WORD = re.compile(r"\((?:P|Р)\)|\[(?:P|Р)\]|\bA,P\b")
check("the three premium masters' camps have no name over their cells any more",
      {c: texts_at(out, *c) for c in CAMPS}, {c: [] for c in CAMPS})
check("  ..where each had «Лагерь мастеров: улучшение оружия (Р)», with a Cyrillic Р",
      {c: texts_at(raw, *c) for c in CAMPS},
      {c: ["Лагерь мастеров: улучшение оружия (Р)"] for c in CAMPS})
check("no name left on the map promises (P), in Latin or Cyrillic",
      [m.group(0).decode("utf-8") for m in M.ROW.finditer(out)
       if PREMIUM_WORD.search(M.html.unescape(m.group(0).decode("utf-8")))], [])
check("  ..while the file had ten",
      len([m for m in M.ROW.finditer(raw)
           if PREMIUM_WORD.search(M.html.unescape(m.group(0).decode("utf-8")))]), 10)
check("  ..the factories keep their calibres, Вади-Хальфа's as its plant makes them",
      texts_at(out, 6017, 1726), ["Производство боеприпасов Вади Хальфы:<br>12-й калибр<br>СП-10"])
check("  ..Донгола's quarter its quests, not the premium bar (nor the ingots' exchange since the owner's"
      " Донгола of 2026-10-13: Мортимер exchanges them in the new market)",
      texts_at(out, 5877, 2011), ["Жилой квартал Донголы:<BR>Задания."])

# The owner's cut of Вади-Хальфа (2026-10-09, «убери из хальфы следующие
# локации: торговцы одеждой, улучшение сетов 6-8, ремесленники по одежде 6, 7
# и 8, а также кланбазу KKND»): the four places are off the map and the
# KKND base's files out of the game (data/retired.json), the set upgrade's
# windows empty (setcraft.SLICES off) -- no name over a cell of the town
# offers any of them, while the other towns keep their own.
print("the cut of Вади-Хальфа")
HALFA_CUT = {(5969, 1729): "Торговцы одеждой",
             (5969, 1730): "Улучшение сетов 6-8[G]<BR>Казначеи ремесленников",
             (5969, 1731): "Ремесленники по одежде 6 уровень",
             (5969, 1732): "Ремесленники по одежде 7 уровень",
             (5970, 1732): "Ремесленники по одежде 8 уровень",
             (5984, 1759): "Собственность клана KKND:<br>ПОСТОРОННИМ СМЕРТЬ! "}
check("the clothing market, the set upgrade, the three clothing craftsmen's quarters and the"
      " KKND base have no name over their cells any more",
      {c: texts_at(out, *c) for c in HALFA_CUT}, {c: [] for c in HALFA_CUT})
check("  ..where each had its own (KKND's with the original's trailing space)",
      {c: texts_at(raw, *c) for c in HALFA_CUT}, {c: [t] for c, t in HALFA_CUT.items()})
OLD_MARKET = "Старый рынок Вади-Хальфы:<BR>Банк<br>Торговец сувенирами.<br>Лотерейщик (А)<br>" \
             "Обучение специализациям<br>%sЗадания"
check("the old market keeps its label but «Обмен G комплектов», Генри ст's exchange",
      (texts_at(raw, 5968, 1727), texts_at(out, 5968, 1727)),
      ([OLD_MARKET % "Обмен G комплектов<br>"], [OLD_MARKET % ""]))
HALFA_BOX = (5955, 5995, 1710, 1770)
GONE = re.compile(r"Торговцы одеждой|Ремесленники по одежде|Улучшение сетов|Обмен G комплектов|"
                  r"KKND")


def rows_in(doc, box, pattern):
    import html
    x0, x1, y0, y1 = box
    got = []
    for m in M.ROW.finditer(doc):
        a = {k.decode(): v for k, v in M.ATTR.findall(m.group(0))}
        if x0 <= int(a["x"]) <= x1 and y0 <= int(a["y"]) <= y1 \
                and pattern.search(html.unescape(a["text"].decode("utf-8"))):
            got.append((int(a["x"]), int(a["y"])))
    return sorted(got)


check("  ..so no name around Вади-Хальфа offers any of it, where the file had seven",
      (rows_in(out, HALFA_BOX, GONE), len(rows_in(raw, HALFA_BOX, GONE))), ([], 7))
# Абри's craftsmen's names went with the cut of Абри (2026-10-12,
# server/test_abri_cut.py), its clothing market's with the owner's «и ещё
# убери локацию торговцы одеждой в Абри» the same day
# (server/test_river_camps_cut.py), Донгола's with the cut of Донгола
# (2026-10-13, server/test_dongola_cut.py) and Абу-Хамед's with the cut of
# Абу-Хамед (2026-10-14, server/test_abuhamed_cut.py).
check("  ..nor do the other towns' clothing markets and craftsmen any more (Донгола's went with its cut"
      " of 2026-10-13, Абу-Хамед's with its own of 2026-10-14)",
      [texts_at(out, *c) for c in ((5878, 2013), (6183, 1974), (5876, 2013), (6184, 1973))],
      [[], [], [], []])
with open(os.path.join(os.path.dirname(HERE), "data", "map_labels.json"), encoding="utf-8") as _fh:
    LABELS = json.load(_fh)["labels"]
OLD_MARKET_CELL, PREMIUM_CAMP_CELL = (5968, 1727), (5968, 1726)
check("the cut's own edits are its seven cells and no other: the six names hidden and the old"
      " market's retext",
      sorted((e["x"], e["y"]) for e in LABELS
             if e.get("why", "").startswith("The owner's cut of Вади-Хальфа, 2026-10-09")),
      sorted(list(HALFA_CUT) + [OLD_MARKET_CELL]))


def rows_of(doc, box):
    import html
    x0, x1, y0, y1 = box
    got = []
    for m in M.ROW.finditer(doc):
        a = {k.decode(): v for k, v in M.ATTR.findall(m.group(0))}
        if x0 <= int(a["x"]) <= x1 and y0 <= int(a["y"]) <= y1:
            got.append((int(a["x"]), int(a["y"]), html.unescape(a["text"].decode("utf-8"))))
    return got


FSC_AIRFIELD_CELL = (5970, 1727)                 # the cut of the ФСЦ, below
# The boss clock's retexts (2026-10-11, below): the camps' and their chiefs'
# places' hours, each row's text for another. The warehouses' were retexted
# too, and are the original's again since 2026-10-12 (below).
CLOCK_WHY = "The owner's boss clock, 2026-10-11"
CLOCK = {(e["x"], e["y"], e["was"]): e["text"] for e in LABELS
         if e.get("why", "").startswith(CLOCK_WHY)}
# The names of the places of ours (data/locations), each added over its own
# cell by the location editor: the owner's, not the file's, and not part of
# any cut (the editor refuses a cell a cut took off the map).
_DATA = os.path.join(os.path.dirname(HERE), "data")
try:
    _OURS = {int(n[:-4]) for n in os.listdir(os.path.join(_DATA, "locations", "static"))
             if n.endswith(".xml") and n[:-4].isdigit() and int(n[:-4]) >= 1381}
except OSError:
    _OURS = set()
with open(os.path.join(_DATA, "settlements.json"), encoding="utf-8") as _fh:
    _SETTLED = {tuple(int(v) for v in k.split(",")): lid for k, lid in json.load(_fh)["cells"].items()}
OURS_ADDED = {(x, y, new) for x, y, was, new in edits if was is None and _SETTLED.get((x, y)) in _OURS}
kept, clocked = [], 0
for x, y, text in rows_of(raw, HALFA_BOX):
    if (x, y) in HALFA_CUT or (x, y) in (PREMIUM_CAMP_CELL, FSC_AIRFIELD_CELL):
        continue
    if (x, y) == OLD_MARKET_CELL and text == OLD_MARKET % "Обмен G комплектов<br>":
        text = OLD_MARKET % ""
    if (x, y, text) in CLOCK:
        text, clocked = CLOCK[(x, y, text)], clocked + 1
    kept.append((x, y, text))
check("  ..and every other name around Вади-Хальфа is the file's own, row for row (the (P) camp"
      " 124's hidden since 2026-09-30, the ФСЦ airfield's since 2026-10-10, the boss clock's"
      " hours retexted since 2026-10-11; the names of places of ours aside)",
      [r for r in rows_of(out, HALFA_BOX) if r not in OURS_ADDED], kept)
check("  ..of which there are dozens", len(kept) > 30, True)
check("  ..eight of them retexted to the boss clock: the four camps and their chiefs' places (the"
      " southern warehouse's is the original's)", clocked, 8)

# The owner's cut of Вади-Хальфа's ФСЦ (2026-10-10, «убери фсц тоже»): the
# FSC airfield 528 (the blue square with «!» beside the old market) and the
# FSC base «НИЛ-1» 522 across the river are off the map (data/retired.json);
# every other name of the ФСЦ -- the airfields of the other towns, the two
# over wasteland, the bases НИЛ-2..4 -- stays. Абри's air base «Авиабаза ЦСЦ»
# (5866,1836) and its airfield beside it (5865,1835) stayed too, until the
# cut of Абри took them (2026-10-12, server/test_abri_cut.py), and so did the
# bases НИЛ-2..4 across the river, until the cut of everything across it
# (2026-10-13, server/test_river_all_cut.py), Донгола's airfield (5879,2011),
# until the cut of Донгола the same day (server/test_dongola_cut.py), and
# Абу-Хамед's (6185,1977), until the cut of Абу-Хамед (2026-10-14,
# server/test_abuhamed_cut.py).
print("the cut of Вади-Хальфа's ФСЦ")
FSC_CUT = {FSC_AIRFIELD_CELL: "Аэроплощадка ФСЦ", (5942, 1723): 'База ФСЦ "НИЛ-1"'}
FSC_KEPT = {(5863, 1946): "Аэроплощадка ФСЦ", (6032, 1951): "Аэроплощадка ФСЦ",
            (6017, 2086): "Аэроплощадка ФСЦ"}
FSC_FAR = {(5849, 1851): 'База ФСЦ "НИЛ-2"', (5863, 2002): 'База ФСЦ "НИЛ-3"',
           (6167, 1989): 'База ФСЦ "НИЛ-4"'}
check("Вади-Хальфа's FSC airfield and the base НИЛ-1 have no name over their cells any more",
      {c: texts_at(out, *c) for c in FSC_CUT}, {c: [] for c in FSC_CUT})
check("  ..where each had its own", {c: texts_at(raw, *c) for c in FSC_CUT},
      {c: [t] for c, t in FSC_CUT.items()})
check("  ..while the other airfields keep theirs",
      {c: texts_at(out, *c) for c in FSC_KEPT}, {c: [t] for c, t in FSC_KEPT.items()})
check("  ..and the bases НИЛ-2..4 across the river, which kept theirs, are hidden since 2026-10-13",
      ({c: texts_at(raw, *c) for c in FSC_FAR}, {c: texts_at(out, *c) for c in FSC_FAR}),
      ({c: [t] for c, t in FSC_FAR.items()}, {c: [] for c in FSC_FAR}))
FSC_WORD = re.compile(r"ФСЦ|ЦСЦ")
check("  ..so of the file's twelve names of the ФСЦ the map shows three (Абри's air base and"
      " airfield gone since 2026-10-12, the bases НИЛ-2..4 and Донгола's airfield since 2026-10-13,"
      " Абу-Хамед's airfield since 2026-10-14)",
      (len(rows_in(raw, (0, 99999, 0, 99999), FSC_WORD)),
       len(rows_in(out, (0, 99999, 0, 99999), FSC_WORD))), (12, 3))
check("the ФСЦ cut's own edits are its two cells and no other",
      sorted((e["x"], e["y"]) for e in LABELS
             if e.get("why", "").startswith("The owner's cut of Вади-Хальфа's ФСЦ, 2026-10-10")),
      sorted(FSC_CUT))

# The owner's cut of the camps across the river (2026-10-12, «убери во всех
# городах лагеря за рекой»; server/test_river_camps_cut.py): «Лагерь за
# рекой» is hidden on its three cells, and Донгола's pier no longer offers
# «Отправка на фронт», the boat of its two men of the Армия ЦСЦ to the camp
# 431 across the river. The pier keeps every other word.
print("the cut of the camps across the river")
RIVER_WHY = "The owner's cut of the camps across the river, 2026-10-12"
RIVER_HIDDEN = [(5943, 1723), (5864, 2002), (6168, 1989)]
PIER_DN = (5873, 2012)
check("«Лагерь за рекой» has no cell of the map any more, where the file had three",
      ({c: texts_at(out, *c) for c in RIVER_HIDDEN}, {c: texts_at(raw, *c) for c in RIVER_HIDDEN}),
      ({c: [] for c in RIVER_HIDDEN}, {c: ["Лагерь за рекой"] for c in RIVER_HIDDEN}))
check("Донгола's pier drops «Отправка на фронт» and keeps its quests (its New Year tree went too, with"
      " the owner's Донгола of 2026-10-13: the row's one edit carries both)",
      (texts_at(raw, *PIER_DN), texts_at(out, *PIER_DN)),
      (["Причал Донголы:<BR>Задания.<br>Отправка на фронт.<br>Новогодняя Елка"],
       ["Причал Донголы:<BR>Задания."]))
check("  ..the only name of the file that offered the front",
      (rows_in(raw, (0, 99999, 0, 99999), re.compile("фронт", re.I)),
       rows_in(out, (0, 99999, 0, 99999), re.compile("фронт", re.I))),
      ([PIER_DN], []))
check("the river cut's own edits are those four cells and no other (Абри's clothing market's is"
      " its own cut's)",
      sorted((e["x"], e["y"]) for e in LABELS if e.get("why", "").startswith(RIVER_WHY)),
      sorted(RIVER_HIDDEN + [PIER_DN]))

# The owner's boss clock (2026-10-11: «давай 14 18 22», «и в описании ко всем
# локациям измени это», «и там написано что выпадает чертеж хотя надо чтобы
# было написано выпадает голд»). The client's only description of a place is
# its name over the map, so every name that tells when a boss of the clock
# comes says the owner's hours, written out for bosses.DEFAULT_HOURS; the
# camps whose bosses leave gold (data/loot_manual.json) say so -- Абри's two
# since the owner's «Там голду дают 6 (работорговцы) и 8 (живодеры)»
# (2026-10-12), Донгола's two since the owner's Донгола (2026-10-13, 10 and 12
# ounces), Абу-Хамед's pirates, the Северный Альянс's outpost and its base
# since the owner's Абу-Хамед (2026-10-14, 14 and 16 ounces); the base, whose
# bosses left none until then, named the fight with the chief. A name with no boss
# of the clock behind it stays the original's, and is listed here; the staffs
# and the dig 433 promised what nothing on the server keeps, and lose those
# lines (below). The warehouses' «Хозяин склада» keeps his own hour since
# 2026-10-12, the original's 20:00, and their names are the original's again
# (below).
print("the boss clock (2026-10-11)")
import bosses  # noqa: E402

check("the labels below were written for these hours: change them together",
      (bosses.parse_hours(bosses.DEFAULT_HOURS), bosses.DEFAULT_STAY), ([840, 1080, 1320], 60.0))
GOLD_CAMPS = [(5970, 1724), (5978, 1727), (5974, 1739), (5993, 1721),           # 80, 81, 84, 85
              (5880, 1844), (5868, 1854),                                       # Абри: 88, 92
              (5883, 2035), (5921, 2011),                                       # Донгола: 93, 98
              (6160, 1975), (6210, 1986), (6273, 1953)]                         # Абу-Хамед: 132, 168, 263
GOLD_CHIEFS = [(5971, 1723), (5979, 1728), (5975, 1738), (5992, 1720),          # 82, 83, 86, 87
               (5881, 1843), (5869, 1855),                                      # Абри: 89, 90
               (5882, 2036), (5920, 2010),                                      # Донгола: 91, 99
               (6161, 1973), (6274, 1952)]                                      # Абу-Хамед: 133, 274
VALLEY_CAMP = (6272, 1840)                                     # Лагерь бандитов 34, Лидер 2103
# The far camp, the Северный Альянс's base 263 (6273,1953), and its chief's
# cell (6274,1952) named the fight with the chief and the hours without gold,
# and the pirates' and the outpost's names were the original's, until the
# owner's Абу-Хамед (2026-10-14): every camp of the clock names gold since.
FAR_CAMPS, FAR_CHIEFS = [], []
HALFA_WAREHOUSES = [(5998, 1697), (6002, 1738), (5957, 1743)]                   # 111, 110, 109
WAREHOUSES = HALFA_WAREHOUSES + [(5913, 1976), (5931, 2031), (5883, 2060), (6183, 1976)]
MKS_BASE = (6036, 2019)                                        # База МКС 257, 2251
VILLAGES = [(6017, 2036), (6023, 2045), (6031, 2041), (6030, 2051), (6019, 2057), (6026, 2063),
            (5977, 2084), (5992, 2084), (5972, 2094), (5987, 2092), (5979, 2101), (6002, 2086),
            (5990, 2042), (6002, 2045), (6004, 2038), (6009, 2052), (5999, 2053), (6009, 2063),
            (5980, 2055), (5981, 2065), (5991, 2063), (5976, 2071), (5988, 2072), (6001, 2071)]
CLOCK_CELLS = (GOLD_CAMPS + GOLD_CHIEFS + [VALLEY_CAMP] + FAR_CAMPS + FAR_CHIEFS
               + [MKS_BASE] + VILLAGES)
check("the clock's own edits are its 47 cells and no other: the camps, their chiefs' places, the"
      " МКС base and the 24 villages",
      (sorted((x, y) for x, y, _ in CLOCK), len(set(CLOCK_CELLS))), (sorted(CLOCK_CELLS), 47))


def say(cells, words):
    """Per cell, whether each of its names on the map says the words."""
    return {c: [words in t for t in texts_at(out, *c)] for c in cells}


def one_each(cells):
    return {c: [True] for c in cells}


check("the four camps of Вади-Хальфа, Абри's two, Донгола's two, Абу-Хамед's three and the valley's"
      " Лагерь бандитов, whose bosses leave gold, name the gold and the owner's hours",
      say(GOLD_CAMPS + [VALLEY_CAMP], "Сражение за золото в 14:00, 18:00 и 22:00"),
      one_each(GOLD_CAMPS + [VALLEY_CAMP]))
check("  ..and their chiefs' places say who comes with it",
      say(GOLD_CHIEFS, "В 14:00, 18:00 и 22:00 часто кто-то приезжает с золотом."),
      one_each(GOLD_CHIEFS))
check("no camp of the clock is a far one, whose bosses leave no gold, any more: the Северный Альянс's base"
      " names the gold since the owner's Абу-Хамед, and no name says «Сражение с главарем» now",
      (FAR_CAMPS, FAR_CHIEFS, sorted({(x, y) for x, y, t in rows_of(out, (0, 99999, 0, 99999))
                                      if "Сражение с главарем" in t})), ([], [], []))
check("the 24 villages' headmen and the МКС base's stock chief come at the owner's hours",
      (say(VILLAGES, "Староста присутствует в 14:00, 18:00 и 22:00"),
       say([MKS_BASE], "Начальник склада приходит в 14:00, 18:00 и 22:00")),
      (one_each(VILLAGES), one_each([MKS_BASE])))
STALE = re.compile(r"чертеж|01\.00|05\.00|с 20:00 до 21:00|12:00 и 21:00|21:30")
check("  ..and none of the 47 names blueprints or an hour no boss keeps",
      [(c, t) for c in CLOCK_CELLS for t in texts_at(out, *c) if STALE.search(t)], [])
with open(os.path.join(os.path.dirname(HERE), "data", "schedule.json"), encoding="utf-8") as _fh:
    WINDOWS = json.load(_fh)["windows"]

# The warehouses' «Хозяин склада» comes once a day (the owner's «на складах
# хозяин должен прриходить один раз!!!», 2026-10-12), at
# bosses.DEFAULT_WAREHOUSE_HOURS for the bosses' stay: 20:00 to 21:00, the
# original's own «Хозяин присутствует с 20:00 до 21:00». The seven names
# over the warehouses are the file's, untouched, and say his window as the
# default makes it: another hour there and no new labels fails here.
print("the warehouses' master (2026-10-12)")


def windows_said(hours, stay):
    """«с 20:00 до 21:00», or «с 14:00 до 15:00, с 18:00 до 19:00 и с 22:00
    до 23:00»: the windows as the warehouses' names would say them."""
    parts = ["с %d:%02d до %d:%02d" % (m // 60, m % 60, (m + int(stay)) // 60 % 24,
                                       (m + int(stay)) % 60) for m in hours]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " и " + parts[-1]


MASTER_SAYS = "Хозяин присутствует " + windows_said(
    bosses.parse_hours(bosses.DEFAULT_WAREHOUSE_HOURS), bosses.DEFAULT_STAY) + "<br>"
check("the warehouses' names were left for this hour: change them together",
      (bosses.parse_hours(bosses.DEFAULT_WAREHOUSE_HOURS), bosses.DEFAULT_STAY, MASTER_SAYS),
      ([20 * 60], 60.0, "Хозяин присутствует с 20:00 до 21:00<br>"))
check("  ..(the helper says the old three windows as they were written)",
      windows_said([840, 1080, 1320], 60), "с 14:00 до 15:00, с 18:00 до 19:00 и с 22:00 до 23:00")
check("the seven warehouses' names say the master's one window, the default's",
      say(WAREHOUSES, MASTER_SAYS), one_each(WAREHOUSES))
check("  ..as the original's own words, each the file's one row over its cell, unedited",
      ({c: texts_at(out, *c) for c in WAREHOUSES},
       sorted((e["x"], e["y"]) for e in LABELS if (e["x"], e["y"]) in WAREHOUSES)),
      ({c: texts_at(raw, *c) for c in WAREHOUSES}, []))
check("  ..and none of them names the bosses' hours any more",
      [(c, t) for c in WAREHOUSES for t in texts_at(out, *c) if "14:00" in t or "22:00" in t], [])
check("  ..and Вади-Хальфа's three still share the box from 19:00 to 20:00, the window wh_box of"
      " data/schedule.json",
      (say(HALFA_WAREHOUSES, "Дележ добычи с 19:00 до 20:00"),
       WINDOWS["wh_box"]["daily"], WINDOWS["wh_box"]["minutes"]),
      (one_each(HALFA_WAREHOUSES), ["19:00"], 60))

# Left as the original's (UNDONE «подписи-без-механики»): the prisons keep
# their own window (data/schedule.json prison_wh); the МКС helicopter has no
# boss of the clock behind it; the black market sells blueprints. The jungle
# hangar and the three far digs were left so too, until the cut of everything
# across the river hid them (2026-10-13), and the pirates' two names and the
# abandoned clan base's, until the owner's Абу-Хамед (2026-10-14) gave the
# pirates their camp, their gold and the clock, and cut the clan base.
ORIGINAL = {(5985, 1744): "Тюрьма Вади-Хальфы", (5903, 1996): "Тюрьма Донголы",
            (6193, 1966): "Тюрьма Абу-Хамеда",
            (6045, 2017): "Третий Склад МКС", (5970, 1730): "Чёрный рынок"}
MWAMBA = (6274, 1833)                                    # «Лагерь Большого Мвамбы», no hours
TIMED = re.compile(r"\d\d:\d\d|\b\d\d\.\d\d\b|\d+ час|чертеж")
EVERYWHERE = (0, 99999, 0, 99999)


def rows_bytes(doc, cell):
    """The rows over a cell as the file has them, byte for byte."""
    want = (str(cell[0]).encode(), str(cell[1]).encode())
    out_ = []
    for m in M.ROW.finditer(doc):
        a = dict(M.ATTR.findall(m.group(0)))
        if (a.get(b"x"), a.get(b"y")) == want:
            out_.append(m.group(0))
    return out_


check("every other name on the map that tells an hour or offers blueprints is one left as the"
      " original's: the warehouses (above), the prisons, the МКС helicopter and the black market",
      sorted({(x, y) for x, y, t in rows_of(out, EVERYWHERE) if TIMED.search(t)}
             - set(CLOCK_CELLS) - set(WAREHOUSES)),
      sorted(ORIGINAL))
check("  ..the warehouses' byte for byte as the file has them",
      [rows_bytes(out, c) for c in WAREHOUSES], [rows_bytes(raw, c) for c in WAREHOUSES])
check("  ..each byte for byte as the file has it, «Лагерь Большого Мвамбы» too, each under its name",
      [(rows_bytes(out, c), all(t.startswith(ORIGINAL.get(c, "Лагерь Большого Мвамбы"))
                                for t in texts_at(out, *c))) for c in sorted(ORIGINAL) + [MWAMBA]],
      [(rows_bytes(raw, c), True) for c in sorted(ORIGINAL) + [MWAMBA]])
check("  ..the prisons' «12:00, 16:00 и 23:00» being their own window (data/schedule.json prison_wh)",
      WINDOWS["prison_wh"]["daily"], ["12:00", "16:00", "23:00"])

# The names that promised what nothing on the server keeps (the owner's
# «поправь чтобы на карте тоже были корректные надписи», 2026-10-11): the four
# staffs' «Сражение за чертежи в 20:00» -- open desert with nobody on it, no
# boss at 20:00 and no window then -- and, at the dig 433 beside Вади-Хальфа,
# the tomb raider of 18:00, where the one inhabitant is the archaeologist. Each
# kept its name and lost the promise; all five stand across the river and are
# hidden whole since the owner's cut of everything across it (2026-10-13,
# «все локации за рекой не нужны»; server/test_river_all_cut.py): their
# edits are hides of the same rows now.
LABELS_WHY = "The owner's map labels, 2026-10-11"
STAFFS = {(5935, 1711): "Штаб Север", (5850, 1999): "Штаб Центр", (6158, 2000): "Штаб Юг",
          (5840, 1839): "Штаб Северо-Запад"}
STAFFS_WAS = {c: [t + "<br>Сражение за чертежи в 20:00"] for c, t in STAFFS.items()}
STAFFS_WAS[(5840, 1839)] = [STAFFS_WAS[(5840, 1839)][0]
                            + "<br>Внимание!!! Необходимо прибывать за 15 минут до встречи с главарем."]
DIG_433 = (5943, 1722)
DIG = ("Археологические раскопки:<BR> Часть сохранившегося надземного комплекса.<BR> Вход в "
       "гробницу Фараонов.<BR>Ходят слухи, что там есть чем поживиться.%s<br>Внимание!!! "
       "Необходимо прибывать за 15 минут до встречи с археологами.")
RIVER_ALL_WHY = "The owner's cut of everything across the river, 2026-10-13"
check("the four staffs, open desert with nobody on them, and the dig 433 have no name on the map",
      {c: texts_at(out, *c) for c in list(STAFFS) + [DIG_433]}, {c: [] for c in list(STAFFS) + [DIG_433]})
check("  ..where each staff promised «Сражение за чертежи в 20:00» (Северо-Запад a chief as well) and the dig"
      " the tomb raider of 18:00",
      ({c: texts_at(raw, *c) for c in STAFFS}, texts_at(raw, *DIG_433)),
      (STAFFS_WAS, [DIG % "<BR>Расхитительница гробниц появляется в 18 часов."]))
check("  ..each edit a hide of that row now, the cut of everything across the river's, telling what 2026-10-11"
      " took off; no edit of the owner's map labels is left",
      ({(e["x"], e["y"]): (e["was"], bool(e.get("hide")), e["why"].startswith(RIVER_ALL_WHY), "2026-10-11" in e["why"])
        for e in LABELS if (e["x"], e["y"]) in set(STAFFS) | {DIG_433}},
       sorted((e["x"], e["y"]) for e in LABELS if e.get("why", "").startswith(LABELS_WHY))),
      ({c: (w[0], True, True, True) for c, w in list(STAFFS_WAS.items())
        + [(DIG_433, [DIG % "<BR>Расхитительница гробниц появляется в 18 часов."])]}, []))
check("«чертеж» is left on the map in one name: the black market's «Покупка чертежей» (its shop sells"
      " them); the pirates' camp by Абу-Хамед, which promised blueprints, names gold since the owner's"
      " Абу-Хамед (2026-10-14)",
      sorted({(x, y) for x, y, t in rows_of(out, EVERYWHERE) if "чертеж" in t}),
      [(5970, 1730)])

print("the rule itself")
doc = ('\ufeff<?xml version=\'1.0\'?>\n<data>\n'
       '<location x="1" y="2" text="A &lt;BR&gt;B" />\n'
       '<location x="3" y="4" text="C" />\n</data>\n').encode("utf-8")
got, n = M.apply(doc, [(1, 2, "A <BR>B", "D \"&\" E's"), (3, 4, "C", None)])
check("retext and hide on a file with a byte order mark", (got, n),
      (('\ufeff<?xml version=\'1.0\'?>\n<data>\n'
        '<location x="1" y="2" text="D &quot;&amp;&quot; E&apos;s" />\n'
        '</data>\n').encode("utf-8"), 2))
check("a row whose text differs is left alone", M.apply(doc, [(3, 4, "not C", None)]), (doc, 0))
check("the same text on another cell is left alone", M.apply(doc, [(3, 5, "C", None)]), (doc, 0))
check("the launcher's form of the edits",
      M.export_rules([(1, 2, "A", None), (3, 4, "B", "C")]).splitlines()[1:],
      ["1\t2\tA\thide\t", "3\t4\tB\ttext\tC"])

# An added row: the name of a place of ours (data/locations) on a cell of the
# map, {x, y, text, add: true, why}. It goes before </data>, in the file's
# own line ending, escaped as a retext is; every other byte stays.
got, n = M.apply(doc, [(3, 4, "C", None), (7, 8, None, "Новое <BR>место")])
check("an added row goes before </data>, after a hide in the same file", (got, n),
      (('﻿<?xml version=\'1.0\'?>\n<data>\n'
        '<location x="1" y="2" text="A &lt;BR&gt;B" />\n'
        '<location x="7" y="8" text="Новое &lt;BR&gt;место" />\n'
        '</data>\n').encode("utf-8"), 2))
check("  ..and alone, it is the only change",
      M.apply(doc, [(7, 8, None, "X")]),
      (doc.replace(b"</data>", b'<location x="7" y="8" text="X" />\n</data>'), 1))
check("an add whose cell has a row of that text already adds nothing", M.apply(doc, [(3, 4, None, "C")]),
      (doc, 0))
crlf = doc.replace(b"\n", b"\r\n")
check("a file with CRLF lines gets its added row with CRLF",
      M.apply(crlf, [(5, 6, None, "D")])[0].endswith(b'<location x="5" y="6" text="D" />\r\n</data>\r\n'), True)
check("the launcher's rules leave an add out: they can only hide or retext",
      M.export_rules([(1, 2, "A", None), (5, 6, None, "D")]).splitlines()[1:], ["1\t2\tA\thide\t"])
def load_one(entry):
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"labels": [entry]}, fh, ensure_ascii=False)
    try:
        return M.load(tmp)
    except ValueError as exc:
        return "refused: %s" % str(exc)[:40]
    finally:
        os.unlink(tmp)


check("load: {x, y, text, add: true} is (x, y, None, text)",
      load_one({"x": 5, "y": 6, "text": "D", "add": True, "why": "a place of ours"}), [(5, 6, None, "D")])
check("load: an add with a 'was', with hide, or without a text is refused",
      [str(load_one(e)).startswith("refused") for e in (
          {"x": 5, "y": 6, "was": "C", "text": "D", "add": True},
          {"x": 5, "y": 6, "hide": True, "text": "D", "add": True},
          {"x": 5, "y": 6, "add": True})], [True, True, True])

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("map_labels OK")
