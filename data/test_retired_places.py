"""The places the owner took out of the game, and nothing else, gone from the map.

The owner's cut of (P) (2026-09-30: «удали всё, что связано с (P), в том
числе и локации») takes the premium masters' camps 124 (Вади-Хальфа), 125
(Донгола) and 130 (Абу-Хамед) off the map; the cut of Вади-Хальфа
(2026-10-09: «убери из хальфы следующие локации: торговцы одеждой, улучшение
сетов 6-8, ремесленники по одежде 6, 7 и 8, а также кланбазу KKND») the
clothing market 468 and the craftsmen's quarters 452, 456 and 457, with the
KKND clan base's six files, which never had a cell. data/retired.json lists
them, data/settlements_verified.json nulls their cells, and
data/place_settlements.py leaves them out of the candidates. The trap this
guards against was found before the first cut was made: a null alone lets
the placer hand the file the next cell that names it (125 moved to
5878,2012) and shifts neighbours whose margins it touched (447, 429 and 432
left their cells, and with other nulls the valley's Arena 167 -- Сет's
stall and the one place for PvP -- left 6270,1831; the four nulls of
Halfa's cut alone took 447 off 5968,1719). So the placer is run twice here,
as the table stands and with both cuts undone, and the two may differ in
exactly the seven intended cells; and the table on disk is the placer's own
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
INTENDED = dict(PREMIUM, **HALFA)
# The KKND clan base: six files, none of them ever on a cell -- listed so the
# placer can never give 297 or 383 the wasteland cell under its label.
KKND = [297, 383, 384, 938, 961, 1189]


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def cells(table):
    return {"%d,%d" % k: v for k, v in table.items()}


on_disk = load("settlements.json")["cells"]
verified = load("settlements_verified.json")
retired = load("retired.json")

check("data/retired.json takes out the three premium masters' camps, Halfa's clothing market"
      " and craftsmen's quarters and the KKND base, each with its why",
      (sorted(int(k) for k in retired["places"]), all(retired["places"].values())),
      (sorted(list(INTENDED.values()) + KKND), True))
check("  ..and settlements_verified.json nulls each one's old cell, with its why",
      [(k, verified["cells"].get(k, "absent"), bool(verified["why"].get(k)))
       for k in sorted(INTENDED)],
      [(k, None, True) for k in sorted(INTENDED)])
check("  ..so none of them opens on any cell of the table",
      sorted(k for k, v in on_disk.items() if v in INTENDED.values()), [])

now = cells(place_settlements.Placer().run())
check("the table on disk is the placer's own output", now == on_disk, True)

before_fixed = {k: v for k, v in verified["cells"].items() if k not in INTENDED}
before = cells(place_settlements.Placer(fixed=before_fixed, retired=()).run())
check("the map before the cuts had the three camps, the market and the three quarters on"
      " their cells", {k: before.get(k) for k in INTENDED}, INTENDED)
diff = {k: (before.get(k), now.get(k)) for k in sorted(set(before) | set(now))
        if before.get(k) != now.get(k)}
check("and the cuts changed exactly those seven cells, nothing else on the map",
      diff, {k: (v, None) for k, v in INTENDED.items()})
check("  ..the valley's Arena 167 (Сет's stall, the PvP place) is where it was",
      now.get("6270,1831"), 167)
check("  ..and so are Halfa's neighbours of the cut: Причал 41, the masters' camp 95, the"
      " arena 78, the black market 102, the quest places 43 and 108, the walled quarter 447",
      {k: now.get(k) for k in ("5965,1728", "5969,1728", "5970,1729", "5970,1730", "5969,1733",
                               "5971,1731", "5968,1719")},
      {"5965,1728": 41, "5969,1728": 95, "5970,1729": 78, "5970,1730": 102, "5969,1733": 43,
       "5971,1731": 108, "5968,1719": 447})
check("  ..the KKND base on no cell, before the cut or after it",
      sorted(k for k, v in list(before.items()) + list(now.items()) if v in KKND), [])

if fails:
    print("\nFAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("retired places OK")
