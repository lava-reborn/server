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

    wsl.exe -e python3 data/build_exits_sides.py
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


def read(path):
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", "replace")


def main():
    static = os.path.join(world.RES, "locations", "static")
    locations, summary, odd = {}, {}, {}
    for fn in sorted(os.listdir(static), key=lambda f: int(f[:-4])):
        if not fn.endswith(".xml"):
            continue
        loc_id = int(fn[:-4])
        txt = read(os.path.join(static, fn))
        attrs = dict(re.findall(r'(\w+)="([^"]*)"',
                                re.search(r"<location([^>]*)>", txt).group(1)))
        width = int(attrs["width"])
        cells = {}
        for chunk in world._chunks(txt, "outzones", 5):
            gx, gy = int(chunk[0:2], 16), int(chunk[2:4], 16)
            side = SIDE.get(chunk[4])
            if side is None:
                odd.setdefault(chunk[4], []).append(loc_id)
                continue
            cells[str(gy * width + gx)] = side
        sides = sorted({s for s in cells.values()},
                       key=lambda s: "WNESab".index(s))
        locations[str(loc_id)] = cells
        summary[str(loc_id)] = {
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
    out = os.path.join(HERE, "exits_sides.json")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"_": "loc_id -> {cell: side}; side W/N/E/S = map edge, "
                        "a/b = door into an interior; cell = gy*width+gx as "
                        "in server/world.py. Built by data/build_exits_sides.py "
                        "from outzones of res/locations/static.",
                   "locations": locations, "summary": summary},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    with_sides = sum(1 for c in locations.values() if c)
    print("locations: %d, with outzones: %d" % (len(locations), with_sides))
    counts = {}
    for c in locations.values():
        for s in set(c.values()):
            counts[s] = counts.get(s, 0) + 1
    print("files per side:", counts)
    if odd:
        print("unknown side codes:", {k: len(v) for k, v in odd.items()})
    print("written", out)


if __name__ == "__main__":
    main()
