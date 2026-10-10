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
    row = rows_at(raw, x, y, was)[0]
    if new is None:
        want = want.replace(row, b"", 1)
    else:
        old = dict((k.decode(), v) for k, v in M.ATTR.findall(row))["text"]
        want = want.replace(row, row.replace(b'text="' + old + b'"',
                                             b'text="' + M.escape(new).encode("utf-8") + b'"', 1), 1)
check("nothing else moved: the file less the hidden rows, the retexted ones retexted in place",
      out, want)
check("the other New Year trees, inside other places' names, stay",
      out.count("Новогодняя Елка".encode()), raw.count("Новогодняя Елка".encode()) - 1)

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
check("  ..Донгола's quarter its quests and the ingots, not the premium bar",
      texts_at(out, 5877, 2011), ["Жилой квартал Донголы:<BR>Задания.<BR>Обмен золотых слитков"])

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
check("  ..while Абри, Донгола and Абу-Хамед keep their clothing markets' and craftsmen's names",
      [texts_at(out, *c) for c in ((5865, 1836), (5878, 2013), (6183, 1974), (5860, 1836))],
      [["Торговцы одеждой"]] * 3 + [["Ремесленники по одежде 10 уровень"]])
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
kept = []
for x, y, text in rows_of(raw, HALFA_BOX):
    if (x, y) in HALFA_CUT or (x, y) in (PREMIUM_CAMP_CELL, FSC_AIRFIELD_CELL):
        continue
    if (x, y) == OLD_MARKET_CELL and text == OLD_MARKET % "Обмен G комплектов<br>":
        text = OLD_MARKET % ""
    kept.append((x, y, text))
check("  ..and every other name around Вади-Хальфа is the file's own, row for row (the (P) camp"
      " 124's hidden since 2026-09-30, the ФСЦ airfield's since 2026-10-10)",
      rows_of(out, HALFA_BOX), kept)
check("  ..of which there are dozens", len(kept) > 30, True)

# The owner's cut of Вади-Хальфа's ФСЦ (2026-10-10, «убери фсц тоже»): the
# FSC airfield 528 (the blue square with «!» beside the old market) and the
# FSC base «НИЛ-1» 522 across the river are off the map (data/retired.json);
# every other name of the ФСЦ -- the airfields of the other towns, the two
# over wasteland, the bases НИЛ-2..4, Абри's air base -- stays.
print("the cut of Вади-Хальфа's ФСЦ")
FSC_CUT = {FSC_AIRFIELD_CELL: "Аэроплощадка ФСЦ", (5942, 1723): 'База ФСЦ "НИЛ-1"'}
FSC_KEPT = {(6185, 1977): "Аэроплощадка ФСЦ", (5865, 1835): "Аэроплощадка ФСЦ",
            (5879, 2011): "Аэроплощадка ФСЦ", (5863, 1946): "Аэроплощадка ФСЦ",
            (6032, 1951): "Аэроплощадка ФСЦ", (6017, 2086): "Аэроплощадка ФСЦ",
            (5849, 1851): 'База ФСЦ "НИЛ-2"', (5863, 2002): 'База ФСЦ "НИЛ-3"',
            (6167, 1989): 'База ФСЦ "НИЛ-4"', (5866, 1836): "Авиабаза ЦСЦ"}
check("Вади-Хальфа's FSC airfield and the base НИЛ-1 have no name over their cells any more",
      {c: texts_at(out, *c) for c in FSC_CUT}, {c: [] for c in FSC_CUT})
check("  ..where each had its own", {c: texts_at(raw, *c) for c in FSC_CUT},
      {c: [t] for c, t in FSC_CUT.items()})
check("  ..while the other airfields, the bases НИЛ-2..4 and Абри's air base keep theirs",
      {c: texts_at(out, *c) for c in FSC_KEPT}, {c: [t] for c, t in FSC_KEPT.items()})
FSC_WORD = re.compile(r"ФСЦ|ЦСЦ")
check("  ..so of the file's twelve names of the ФСЦ the map shows ten",
      (len(rows_in(raw, (0, 99999, 0, 99999), FSC_WORD)),
       len(rows_in(out, (0, 99999, 0, 99999), FSC_WORD))), (12, 10))
check("the ФСЦ cut's own edits are its two cells and no other",
      sorted((e["x"], e["y"]) for e in LABELS
             if e.get("why", "").startswith("The owner's cut of Вади-Хальфа's ФСЦ, 2026-10-10")),
      sorted(FSC_CUT))

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

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("map_labels OK")
