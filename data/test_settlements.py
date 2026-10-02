"""The map table, its report, and the designed spawn stand-ins.

data/settlements.json is built by data/place_settlements.py from the
client's tooltips and every clue the wiki and the files give; this checks
what the placer promised rather than what it happened to choose: the cells
confirmed by playing are reproduced exactly, one file stands in one place,
no scratch or interior file is on the map, the report agrees with the
table, and the stand-ins in data/spawn_substitutes.json point at creatures
the client can draw. Runs under WSL with the client resources present:

    wsl.exe -e python3 data/test_settlements.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

ADJACENT = 3


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def cell_of(key):
    x, y = key.split(",")
    return int(x), int(y)


def connected(cells):
    """Whether the cells form one settlement: every cell within ADJACENT
    Manhattan steps of another, as a chain (a five-cell pass is one place,
    the same file at two ends of the map is not)."""
    cells = list(cells)
    seen = {cells[0]}
    frontier = [cells[0]]
    while frontier:
        a = frontier.pop()
        for b in cells:
            if b not in seen and abs(a[0] - b[0]) + abs(a[1] - b[1]) <= ADJACENT:
                seen.add(b)
                frontier.append(b)
    return len(seen) == len(cells)


def main():
    table = load("settlements.json")["cells"]
    fixed = load("settlements_verified.json")["cells"]
    subs = load("spawn_substitutes.json")
    sides = load("exits_sides.json")["summary"]
    mt = world.mob_types()
    types = {int(k): v for k, v in load("mob_types.json")["types"].items()}

    # --- the truth is reproduced, exactly ---------------------------------
    for key, loc_id in fixed.items():
        if loc_id is None:
            assert key not in table, "settlements: verified-empty cell %s is bound" % key
        else:
            assert table.get(key) == loc_id, "settlements: verified %s -> %s, table says %s" % (
                key, loc_id, table.get(key))
    print("verified cells reproduced: %d" % len(fixed))

    # --- a place out of the game opens on no cell (data/retired.json) -------
    # The exact difference the cut made is data/test_retired_places.py's,
    # which runs the placer; this is only that none of them is on the map.
    retired = {int(k) for k in load("retired.json").get("places", {})}
    on_map = sorted((k, v) for k, v in table.items() if v in retired)
    assert not on_map, "settlements: places out of the game are on the map: %s" % on_map
    print("places out of the game on no cell: %s" % sorted(retired))

    # --- every binding is a real map cell leading to a real file ------------
    tooltips = set()
    txt = open(os.path.join(world.RES, "database", "locations.xml"), "rb").read().decode("utf-8", "replace")
    for x, y in re.findall(r'<location x="(\d+)" y="(\d+)"', txt):
        tooltips.add((int(x), int(y)))
    for key, loc_id in table.items():
        assert re.match(r"^\d{4},\d{4}$", key), key
        # A verified cell may be a quest place with no tooltip, which the
        # wiki's quest gives instead (45 «Курьер» on 5967,1737); nothing
        # else is placed off the tooltips.
        assert cell_of(key) in tooltips or fixed.get(key) == loc_id, \
            "settlements: %s has no tooltip on the map" % key
        assert world.path_for(loc_id) is not None, "settlements: %s -> %s has no file" % (key, loc_id)
        meta = sides[str(loc_id)]
        # A cell the verified table puts a file on is the truth, whatever the
        # file is called: the valley's courier place 28 is Q_IV_test_gonec,
        # and the map's own tooltip on 6272,1833 is «Гонец».
        assert "test" not in meta["fn"].lower() or fixed.get(key) == loc_id, \
            "settlements: scratch file %s on %s" % (loc_id, key)
        assert any(s in "WNES" for s in meta["sides"]), \
            "settlements: interior %s (%s) on %s" % (loc_id, meta["fn"], key)
    assert len(table) >= 200, "settlements: only %d cells bound" % len(table)
    print("settlements: %d cells, all on tooltips, none scratch or interior" % len(table))

    # --- one file, one place ------------------------------------------------
    by_loc = collections.defaultdict(list)
    for key, loc_id in table.items():
        by_loc[loc_id].append(cell_of(key))
    scattered = {i: cs for i, cs in by_loc.items() if not connected(cs)}
    assert not scattered, "settlements: files at two ends of the map: %s" % scattered
    print("one file one place: %d files, widest %d cells" % (
        len(by_loc), max(len(cs) for cs in by_loc.values())))

    # --- the report agrees with the table -----------------------------------
    with io.open(os.path.join(HERE, "settlements_report.md"), encoding="utf-8") as fh:
        report = fh.read()
    rows = {}
    for line in report.splitlines():
        m = re.match(r"^\| (\d{4},\d{4}) \| [^|]* \| (—|(\d+) «)", line)
        if m:
            rows[m.group(1)] = int(m.group(3)) if m.group(3) else None
    assert len(rows) == len(tooltips), "report: %d rows for %d tooltip cells" % (len(rows), len(tooltips))
    for key, loc_id in table.items():
        if cell_of(key) not in tooltips:
            continue        # a verified quest place: the report rows are the tooltips
        assert rows.get(key) == loc_id, "report: %s shows %s, table says %s" % (key, rows.get(key), loc_id)
    for key, loc_id in rows.items():
        if loc_id is not None:
            assert table.get(key) == loc_id, "report: %s chosen %s but not in the table" % (key, loc_id)
    m = re.search(r"уверенно (\d+); слабо (\d+); пустошь (\d+)", report)
    assert m, "report: no summary line"
    # A verified null binds nothing: it takes a cell off the map.
    bound = int(m.group(1)) + int(m.group(2)) + sum(1 for v in fixed.values() if v is not None)
    assert bound == len(table), "report: summary says %d bound, table has %d" % (bound, len(table))
    print("report: %d rows, summary and table agree" % len(rows))

    # --- the stand-ins ----------------------------------------------------
    assert subs.get("designed") is True, "substitutes: not marked as designed"
    n = 0
    for k, rec in subs["substitutes"].items():
        unknown, known = int(k), int(rec["type_id"])
        assert unknown not in mt, "substitutes: %s is known to the client, needs no stand-in" % k
        assert known in mt, "substitutes: stand-in %d for %s not in mobs.xml" % (known, k)
        assert mt[known][0] == world.MOB, "substitutes: stand-in %d for %s is not a hostile" % (known, k)
        assert types[known]["role"] == "mob", "substitutes: stand-in %d for %s is a %s" % (
            known, k, types[known]["role"])
        assert mt[known][1].lower().startswith(rec["faction"] + "_"), \
            "substitutes: %s -> %s is not of faction %s" % (k, mt[known][1], rec["faction"])
        assert rec["files"], k
        n += 1
    for k, rec in subs["unresolved"].items():
        assert int(k) not in mt and rec["reason"], k
    assert n >= 400, "substitutes: only %d stand-ins" % n
    # A stand-in reaches the room only where fighting happens.
    assert world.substitute(int(next(iter(subs["substitutes"])))) is not None
    print("substitutes: %d unknown types stood in, %d left unresolved" % (n, len(subs["unresolved"])))
    print("ok")


if __name__ == "__main__":
    main()
