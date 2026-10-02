"""The places the owner took out of the game, and nothing else, gone from the map.

The owner's cut of (P) (2026-09-30: «удали всё, что связано с (P), в том
числе и локации») takes the premium masters' camps 124 (Вади-Хальфа), 125
(Донгола) and 130 (Абу-Хамед) off the map: data/retired.json lists them,
data/settlements_verified.json nulls their cells, and data/place_settlements.py
leaves them out of the candidates. The trap this guards against was found
before the cut was made: a null alone lets the placer hand the file the next
cell that names it (125 moved to 5878,2012) and shifts neighbours whose
margins it touched (447, 429 and 432 left their cells, and with other nulls
the valley's Arena 167 -- Сет's stall and the one place for PvP -- left
6270,1831). So the placer is run twice here, as the table stands and with
the cut undone, and the two may differ in exactly the three intended cells;
and the table on disk is the placer's own output, so that difference is the
difference between the map before the cut and the map now.

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

# The cut, cell by cell: what stood there before, and nothing now.
INTENDED = {"5968,1726": 124, "5876,2012": 125, "6182,1975": 130}
fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def cells(table):
    return {"%d,%d" % k: v for k, v in table.items()}


on_disk = load("settlements.json")["cells"]
verified = load("settlements_verified.json")
retired = load("retired.json")

check("data/retired.json takes out the three premium masters' camps, each with its why",
      (sorted(int(k) for k in retired["places"]), all(retired["places"].values())),
      ([124, 125, 130], True))
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
check("the map before the cut had the three camps on their cells",
      {k: before.get(k) for k in INTENDED}, INTENDED)
diff = {k: (before.get(k), now.get(k)) for k in sorted(set(before) | set(now))
        if before.get(k) != now.get(k)}
check("and the cut changed exactly those three cells, nothing else on the map",
      diff, {k: (v, None) for k, v in INTENDED.items()})
check("  ..the valley's Arena 167 (Сет's stall, the PvP place) is where it was",
      now.get("6270,1831"), 167)

if fails:
    print("\nFAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("retired places OK")
