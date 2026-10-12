"""The places the owner took out of the game, and nothing else, gone from the map.

The owner's cut of (P) (2026-09-30: «удали всё, что связано с (P), в том
числе и локации») takes the premium masters' camps 124 (Вади-Хальфа), 125
(Донгола) and 130 (Абу-Хамед) off the map; the cut of Вади-Хальфа
(2026-10-09: «убери из хальфы следующие локации: торговцы одеждой, улучшение
сетов 6-8, ремесленники по одежде 6, 7 и 8, а также кланбазу KKND») the
clothing market 468 and the craftsmen's quarters 452, 456 and 457, with the
KKND clan base's six files, which never had a cell; the cut of Вади-Хальфа's
ФСЦ (2026-10-10: «убери фсц тоже») the FSC airfield 528 and the FSC base
«НИЛ-1» 522; the cut of Абри (2026-10-12: «Убери локации: все ремесленники
по одежде; Авиабаза ЦСЦ; улучшение сетов 10-12; ...; убери кланбазу
Либерти») the craftsmen's quarters 453, 454, 458 and 459, the ЦСЦ's air
base 427 and the clan base Liberty's entrance 328 and block post 327, with
the quarter 450 behind «Улучшение сетов 10-12» and the base's nine other
files, which never had a cell -- and, by the decisions taken for him that
day («Все, что не сможешь восстановить, вырезай»), the ФСЦ airfield 529 and
the clan base Blackwater's block post 317, with the base's six other files.
data/retired.json lists them, data/settlements_verified.json
nulls their cells, and data/place_settlements.py leaves them out of the
candidates. The trap this
guards against was found before the first cut was made: a null alone lets
the placer hand the file the next cell that names it (125 moved to
5878,2012) and shifts neighbours whose margins it touched (447, 429 and 432
left their cells, and with other nulls the valley's Arena 167 -- Сет's
stall and the one place for PvP -- left 6270,1831; the four nulls of
Halfa's cut alone took 447 off 5968,1719). So the placer is run twice here,
as the table stands and with the cuts undone, and the two may differ in
exactly the eighteen intended cells; and the table on disk is the placer's own
output, so that difference is the difference between the map before the
cuts and the map now.

Slow by the placer's measure (a minute a run). Runs under WSL with the
client resources present:

    LAVA_RES=/mnt/c/Users/gmkrt/OneDrive/Desktop/lava/res python3 data/test_retired_places.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import place_settlements  # noqa: E402
from testkit import check, fails  # noqa: E402

# The cuts, cell by cell: what stood there before, and nothing now.
PREMIUM = {"5968,1726": 124, "5876,2012": 125, "6182,1975": 130}
HALFA = {"5969,1729": 468, "5969,1731": 452, "5969,1732": 456, "5970,1732": 457}
FSC = {"5970,1727": 528, "5942,1723": 522}
ABRI = {"5860,1836": 453, "5861,1836": 454, "5860,1837": 458, "5863,1837": 459,
        "5866,1836": 427, "5906,1888": 328, "5906,1889": 327, "5865,1835": 529,
        "5924,1838": 317}
INTENDED = dict(PREMIUM, **HALFA, **FSC, **ABRI)
# The KKND clan base: six files, none of them ever on a cell -- listed so the
# placer can never give 297 or 383 the wasteland cell under its label.
KKND = [297, 383, 384, 938, 961, 1189]
# The cut of Абри's off-cell files: the quarter 450 behind «Улучшение сетов
# 10-12» (5866,1837), and the clan base Liberty's own (the block post's other
# copy, the back door, the bunker, its garage and two workshops, the leader's
# room, and the older edition 148/610), and the clan base Blackwater's (the
# back door, the yard, the bunker, its garage, the workshop and the leader's
# room) -- the placer can never give one the wasteland under «Кланбаза
# Liberty» at Абу-Хамед (6248,1979), under Blackwater's «Блок-пост»
# (5923,1838) or anywhere.
ABRI_OFF_CELL = [450, 326, 329, 936, 937, 939, 940, 1190, 148, 610,
                 311, 312, 927, 931, 935, 1188]


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def cells(table):
    return {"%d,%d" % k: v for k, v in table.items()}


on_disk = load("settlements.json")["cells"]
verified = load("settlements_verified.json")
retired = load("retired.json")

check("data/retired.json takes out the three premium masters' camps, Halfa's clothing market"
      " and craftsmen's quarters, the KKND base, the ФСЦ's airfield and base НИЛ-1, and Абри's"
      " craftsmen's quarters, air base, set upgraders' quarter and clan base Liberty, each with"
      " its why",
      (sorted(int(k) for k in retired["places"]), all(retired["places"].values())),
      (sorted(list(INTENDED.values()) + KKND + ABRI_OFF_CELL), True))
check("  ..and settlements_verified.json nulls each one's old cell, with its why",
      [(k, verified["cells"].get(k, "absent"), bool(verified["why"].get(k)))
       for k in sorted(INTENDED)],
      [(k, None, True) for k in sorted(INTENDED)])
check("  ..so none of them opens on any cell of the table",
      sorted(k for k, v in on_disk.items() if v in INTENDED.values()), [])
check("  ..and retired.json's cells name exactly those eighteen, each with the place it held: the"
      " town's ground still for the encounters (world.retired_cells)",
      {k: v for k, v in retired["cells"].items() if not k.startswith("_")}, INTENDED)

now = cells(place_settlements.Placer().run())
check("the table on disk is the placer's own output", now == on_disk, True)

before_fixed = {k: v for k, v in verified["cells"].items() if k not in INTENDED}
before = cells(place_settlements.Placer(fixed=before_fixed, retired=()).run())
check("the map before the cuts had the three camps, the market, the three quarters, the"
      " airfield, the base НИЛ-1, Абри's four quarters, its air base, the clan base Liberty, the"
      " ФСЦ airfield 529 and Blackwater's block post on their cells",
      {k: before.get(k) for k in INTENDED}, INTENDED)
diff = {k: (before.get(k), now.get(k)) for k in sorted(set(before) | set(now))
        if before.get(k) != now.get(k)}
check("and the cuts changed exactly those eighteen cells, nothing else on the map",
      diff, {k: (v, None) for k, v in INTENDED.items()})
check("  ..the valley's Arena 167 (Сет's stall, the PvP place) is where it was",
      now.get("6270,1831"), 167)
check("  ..and so are Halfa's neighbours of the cut: Причал 41, the masters' camp 95, the"
      " arena 78, the black market 102, the quest places 43 and 108, the walled quarter 447",
      {k: now.get(k) for k in ("5965,1728", "5969,1728", "5970,1729", "5970,1730", "5969,1733",
                               "5971,1731", "5968,1719")},
      {"5965,1728": 41, "5969,1728": 95, "5970,1729": 78, "5970,1730": 102, "5969,1733": 43,
       "5971,1731": 108, "5968,1719": 447})
check("  ..and the ФСЦ's neighbours: the quarter 36, the arena 59 and the dump 100 around the"
      " airfield, the resistance camp 429 and the dig 433 beside the base",
      {k: now.get(k) for k in ("5969,1727", "5970,1728", "5971,1727", "5943,1723", "5943,1722")},
      {"5969,1727": 36, "5970,1728": 59, "5971,1727": 100, "5943,1723": 429, "5943,1722": 433})
check("  ..the KKND base on no cell, before the cut or after it",
      sorted(k for k, v in list(before.items()) + list(now.items()) if v in KKND), [])
check("  ..and Абри's neighbours of the cut: the port market 187, the quarter 188, the slums 255,"
      " Хаксли's fields 261, the dump 289, the abandoned factory 290, the graveyard 368, the"
      " clothing market 378 and the hippies 191; east of it the saltpetre pit's mouth 204",
      {k: now.get(k) for k in ("5860,1835", "5861,1835", "5862,1835", "5862,1836", "5863,1835",
                               "5864,1835", "5864,1836", "5865,1836", "5860,1838", "5914,1854")},
      {"5860,1835": 187, "5861,1835": 188, "5862,1835": 255, "5862,1836": 261, "5863,1835": 289,
       "5864,1835": 290, "5864,1836": 368, "5865,1836": 378, "5860,1838": 191, "5914,1854": 204})
check("  ..the quarter 450 and the clan bases' other files on no cell, before the cut or after it;"
      " the second «Кланбаза Liberty» at Абу-Хамед (6248,1979) and Blackwater's «Блок-пост»"
      " (5923,1838) wasteland both times",
      (sorted(k for k, v in list(before.items()) + list(now.items()) if v in ABRI_OFF_CELL),
       before.get("6248,1979"), now.get("6248,1979"), before.get("5923,1838"), now.get("5923,1838")),
      ([], None, None, None, None))

if fails:
    print("\nFAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("retired places OK")
