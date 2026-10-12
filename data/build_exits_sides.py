"""Build data/exits_sides.json: which side of the world each exit cell leads to.

The client never says through which zone a player leaves a location -- it
sends chWorld;to=1 and nothing else -- so the server has to know it from the
player's cell. The location files still carry that: outzones is a list of
5-character records, xx yy s, where the fifth character is the side. Checked
over all 1381 files (recon/analysis/world.md §5): 1 west, 2 north, 3 east,
4 south, and a/b for doors that lead into an interior rather than onto the
map. The set of outzones cells equals the client's own zones set in every
file, so this is exactly the set of cells on which the exit window opens.

Output: {"locations": {loc_id: {cell: side}}, "summary": {loc_id: {...}}}
with cell = gy * width + gx, the same numbering world.py uses, and side one of
W N E S a b. The summary lists the sides each file has, its fn and title, so
data/build_exits.py can reason about doors without re-reading the XML.

The files are the ones the server reads: ours (data/locations/static) before
the original's (res/locations/static), world.static_path. A full rebuild
reads every one of them, so it is run over the original's res -- CI's slice,
LAVA_RES -- and never over an installed client, where the launcher has put
the release's own 262.xml («Тотем», client/files). A location of ours has its
rows rewritten alone (rows_for, --only), every other row left as it is.

    wsl.exe -e python3 data/build_exits_sides.py
    wsl.exe -e python3 data/build_exits_sides.py --only 1381 1382
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "server"))
import world  # noqa: E402

SIDE = {"1": "W", "2": "N", "3": "E", "4": "S", "a": "a", "b": "b"}
OUT = os.path.join(HERE, "exits_sides.json")


def read(path):
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", "replace")


def row(loc_id, path):
    """One file's rows: (cells {cell: side}, summary, odd {code: [loc_id]})."""
    txt = read(path)
    attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                            re.search(r"<location([^>]*)>", txt).group(1)))
    width = int(attrs["width"])
    cells, odd = {}, {}
    for chunk in world._chunks(txt, "outzones", 5):
        gx, gy = int(chunk[0:2], 16), int(chunk[2:4], 16)
        side = SIDE.get(chunk[4])
        if side is None:
            odd.setdefault(chunk[4], []).append(loc_id)
            continue
        cells[str(gy * width + gx)] = side
    sides = sorted({s for s in cells.values()},
                   key=lambda s: "WNESab".index(s))
    summary = {
        "fn": attrs.get("fn", ""),
        "title": attrs.get("title", ""),
        "width": width,
        "height": int(attrs["height"]),
        "war": int(attrs.get("war", 0) or 0),
        "pvp": int(attrs.get("pvp", 0) or 0),
        "sides": sides,
        "door_cells": {s: sorted(int(c) for c, v in cells.items() if v == s)
                       for s in sides if s in "ab"},
    }
    return cells, summary, odd


def write(out, locations, summary):
    # Half a million exit cells: one per line would run to ten megabytes, so
    # each location's cell map goes on a single line. Still plain JSON.
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{\n "_": %s,\n' % json.dumps(
            "loc_id -> {cell: side}; side W/N/E/S = map edge, a/b = door "
            "into an interior; cell = gy*width+gx as in server/world.py. "
            "Built by data/build_exits_sides.py from outzones of "
            "res/locations/static.", ensure_ascii=False))
        fh.write(' "locations": {\n')
        keys = sorted(locations, key=int)
        for n, k in enumerate(keys):
            cells = dict(sorted(locations[k].items(), key=lambda kv: int(kv[0])))
            fh.write('  "%s": %s%s\n' % (
                k, json.dumps(cells, separators=(",", ":")),
                "," if n < len(keys) - 1 else ""))
        fh.write(' },\n "summary": ')
        fh.write(json.dumps(summary, ensure_ascii=False, indent=1,
                            sort_keys=True).replace("\n", "\n "))
        fh.write("\n}\n")


def rows_for(ids, out=OUT):
    """Rewrite the rows of these ids alone, each from the file the server
    reads for it (world.static_path), and keep every other row as it is; an
    id with no file any more loses its rows. [(id, 'written' or
    'dropped')]. With nothing changed the table comes out byte for byte the
    same."""
    with io.open(out, encoding="utf-8") as fh:
        doc = json.load(fh)
    locations, summary = doc["locations"], doc["summary"]
    done = []
    for loc_id in sorted({int(i) for i in ids}):
        path = world.static_path(loc_id)
        if path is None:
            locations.pop(str(loc_id), None)
            summary.pop(str(loc_id), None)
            done.append((loc_id, "dropped"))
            continue
        cells, summ, odd = row(loc_id, path)
        if odd:
            raise SystemExit("%s: unknown side codes %s" % (path, sorted(odd)))
        locations[str(loc_id)] = cells
        summary[str(loc_id)] = summ
        done.append((loc_id, "written"))
    write(out, locations, summary)
    return done


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--only"]:
        for loc_id, what in rows_for(argv[1:]):
            print("%d: %s" % (loc_id, what))
        return
    if argv:
        raise SystemExit("usage: build_exits_sides.py [--only ID ...]")
    locations, summary, odd = {}, {}, {}
    for loc_id in world.static_ids():
        cells, summ, bad = row(loc_id, world.static_path(loc_id))
        for code, ids in bad.items():
            odd.setdefault(code, []).extend(ids)
        locations[str(loc_id)] = cells
        summary[str(loc_id)] = summ
    write(OUT, locations, summary)
    with_sides = sum(1 for c in locations.values() if c)
    print("locations: %d, with outzones: %d" % (len(locations), with_sides))
    counts = {}
    for c in locations.values():
        for s in set(c.values()):
            counts[s] = counts.get(s, 0) + 1
    print("files per side:", counts)
    if odd:
        print("unknown side codes:", {k: len(v) for k, v in odd.items()})
    print("written", OUT)


if __name__ == "__main__":
    main()
