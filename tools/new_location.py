#!/usr/bin/env python3
"""Make a location of ours from a copy of an existing one, with its ways in and out.

    python3 tools/new_location.py --from 673 --title "Убежище" \\
        --walk-in "102:30,40;31,40" --door a --why "слово владельца" \\
        [--id 1381] [--fn ED_ubezhishche] [--author owner] [--keep-mobs] \\
        [--data DIR]

The copy is the file the server reads for --from (world.static_path), byte
for byte but for its title, its fn and its inhabitants: <mobs> is emptied,
since the inhabitants of a place of ours stand in data/placements.json
(--keep-mobs keeps the copy's). The art, the walls, the exits and the
entries are the original's. It takes --id, or the first free id from 1381
(world.FIRST_NEW_ID), below 8192.

Its way in is a walk-in (data/passages.json 'walk_in'): cells x,y of an
existing location where a walk that ends there takes the player into the
new place (server.py, Session.arm_passage) -- the original location's file
is not touched, and the client opens no window there. Its way out is one of
the copy's own doors, a or b (passages.json 'doors', confidence high): back
to where the walk-in is, or to --door a=<id>.

What it writes, under DIR (the repository's data/ unless given):

    locations/static/<id>.xml   the copy (server/world.py reads it first;
                                client/build.py ships it with its row in
                                xml/loc_defs.xml)
    locations/index.json        its row: title, from, author, created, why
    exits_sides.json            its rows, when DIR has the table
                                (data/build_exits_sides.py rows_for)
    passages.json               the walk-in's row and the door's, when asked

Every other row of those tables stays byte for byte as it was
(tools/jsonrows.py). It never opens a window and touches no original file.
A place on the map (data/settlements_verified.json, a label in
data/map_labels.json, a square in data/map_cells.json) is the location
editor's.
"""
import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "data"))
sys.path.insert(0, os.path.join(ROOT, "server"))
import jsonrows  # noqa: E402
import world  # noqa: E402


class Refused(Exception):
    pass


def next_id(taken):
    """The first id from world.FIRST_NEW_ID that no file has."""
    i = world.FIRST_NEW_ID
    taken = set(taken)
    while i in taken:
        i += 1
    if i >= world.NEW_ID_LIMIT:
        raise Refused("no free id below %d" % world.NEW_ID_LIMIT)
    return i


def _attr(value):
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def copy_xml(raw, title, fn, keep_mobs=False):
    """The bytes of a location file with its title and fn set and, unless
    keep_mobs, its <mobs> emptied; every other byte as it was."""
    m = re.search(rb"<location\b[^>]*>", raw)
    if not m:
        raise Refused("not a location file: no <location> tag")
    tag = m.group(0)
    for name, value in ((b"title", title), (b"fn", fn)):
        enc = _attr(value).encode("utf-8")
        if re.search(rb'\b' + name + rb'="[^"]*"', tag):
            tag = re.sub(rb'\b' + name + rb'="[^"]*"', lambda _m: name + b'="' + enc + b'"', tag, count=1)
        else:
            tag = tag[:-1] + b" " + name + b'="' + enc + b'">'
    out = raw[:m.start()] + tag + raw[m.end():]
    if not keep_mobs:
        out = re.sub(rb"<mobs>.*?</mobs>", b"<mobs></mobs>", out, count=1, flags=re.S)
    return out


def parse_walk_in(spec):
    """'102:30,40;31,40' -> (102, [[30, 40], [31, 40]])."""
    try:
        loc, cells = spec.split(":", 1)
        out = []
        for part in cells.split(";"):
            x, y = part.split(",")
            out.append([int(x), int(y)])
        return int(loc), out
    except ValueError:
        raise Refused("--walk-in is written LOC:X,Y[;X,Y...]; given %r" % spec)


def check_walk_in(loc_id, cells):
    """Why these cells of loc_id cannot be a walk-in, or None."""
    import travel
    try:
        loc = world.location(loc_id)
    except (KeyError, OSError) as exc:
        return "location %d: %s" % (loc_id, exc)
    sides = travel.exit_sides(loc)
    for x, y in cells:
        if not (0 <= x < loc.width and 0 <= y < loc.height):
            return "%d,%d is off the grid of %d (%dx%d)" % (x, y, loc_id, loc.width, loc.height)
        c = y * loc.width + x
        if c in loc.obstacles:
            return "%d,%d of %d is a wall" % (x, y, loc_id)
        if c in sides:
            return "%d,%d of %d is an exit already (%s)" % (x, y, loc_id, sides[c])
    return None


def make(src_id, title, why, data_dir=None, new_id=None, fn=None, author="owner",
         walk_in=None, door=None, keep_mobs=False, today=None):
    """Write the new location and its rows; a dict of what was written."""
    data_dir = os.path.abspath(data_dir or os.path.join(ROOT, "data"))
    world.OVERLAY = os.path.join(data_dir, "locations")
    world._CACHE.clear()
    today = today or datetime.date.today().isoformat()
    if not title or not why:
        raise Refused("a title and a why, both")
    src = world.static_path(src_id)
    if src is None:
        raise Refused("no location %d to copy" % src_id)
    taken = world.static_ids()
    if new_id is None:
        new_id = next_id(taken)
    elif not world.FIRST_NEW_ID <= new_id < world.NEW_ID_LIMIT:
        raise Refused("a new place's id is %d..%d" % (world.FIRST_NEW_ID, world.NEW_ID_LIMIT - 1))
    elif new_id in taken:
        raise Refused("%d is taken" % new_id)
    fn = fn or "ED_%d" % new_id
    if not re.fullmatch(r"[A-Za-z0-9_]+", fn):
        raise Refused("fn is letters, digits and _ only: %r" % fn)
    if walk_in:
        bad = check_walk_in(*walk_in)
        if bad:
            raise Refused("walk-in: " + bad)
    with open(src, "rb") as fh:
        body = copy_xml(fh.read(), title, fn, keep_mobs)

    sdir = os.path.join(world.OVERLAY, "static")
    os.makedirs(sdir, exist_ok=True)
    path = os.path.join(sdir, "%d.xml" % new_id)
    with open(path, "wb") as fh:
        fh.write(body)
    written = {"id": new_id, "files": [path]}
    try:
        loc = world.Location(new_id)
        free = [c for c in loc.entries if c not in loc.obstacles]
        if not free:
            raise Refused("the copy has no free entry cell")
        sides = {}
        for chunk in world._chunks(world._read(path), "outzones", 5):
            sides.setdefault(chunk[4], []).append(loc._cell(chunk))
        if door:
            side, target = door
            if side not in ("a", "b"):
                raise Refused("a door is a or b")
            if side not in sides:
                raise Refused("the copy of %d has no door %s (its exits: %s)"
                              % (src_id, side, "".join(sorted(sides)) or "none"))
            if target is None:
                if not walk_in:
                    raise Refused("--door %s leads where? --door %s=<id>, or a --walk-in" % (side, side))
                target = walk_in[0]
            if world.static_path(target) is None:
                raise Refused("the door leads to %d, which has no file" % target)
            door = (side, target)
    except Exception:
        os.unlink(path)
        raise

    # its row in the index
    ipath = os.path.join(world.OVERLAY, "index.json")
    if os.path.isfile(ipath):
        with io.open(ipath, encoding="utf-8", newline="") as fh:
            itext = fh.read()
    else:
        itext = '{\n "locations": {}\n}\n'
    row = {"title": title, "from": src_id, "author": author, "created": today, "why": why}
    itext = jsonrows.set_key(itext, ["locations", str(new_id)], row)
    with io.open(ipath, "w", encoding="utf-8", newline="") as fh:
        fh.write(itext)
    written["files"].append(ipath)

    # its exits
    epath = os.path.join(data_dir, "exits_sides.json")
    if os.path.isfile(epath):
        import build_exits_sides
        build_exits_sides.rows_for([new_id], out=epath)
        written["files"].append(epath)

    # its ways in and out
    if walk_in or door:
        ppath = os.path.join(data_dir, "passages.json")
        with io.open(ppath, encoding="utf-8", newline="") as fh:
            ptext = fh.read()
        doc = json.loads(ptext)
        if walk_in:
            from_id, cells = walk_in
            rows = list(jsonrows.get_key(doc, ["walk_in", str(from_id)], []) or [])
            rows.append({"cells": cells, "target_loc_id": new_id,
                         "why": "DESIGNED (%s, %s): the way into «%s» (%d), a location of ours copied from %d. %s"
                                % (today, author, title, new_id, src_id, why)})
            ptext = jsonrows.set_key(ptext, ["walk_in", str(from_id)], rows)
        if door:
            side, target = door
            ptext = jsonrows.set_key(ptext, ["doors", str(new_id), side], {
                "confidence": "high", "source": "editor", "target_loc_id": target,
                "why": "DESIGNED (%s, %s): door %s of «%s» (%d), a location of ours copied from %d, "
                       "leads to %d. %s" % (today, author, side, title, new_id, src_id, target, why)})
        with io.open(ppath, "w", encoding="utf-8", newline="") as fh:
            fh.write(ptext)
        written["files"].append(ppath)
        written["walk_in"] = walk_in
        written["door"] = door
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="src", type=int, required=True, help="the location to copy")
    ap.add_argument("--title", required=True, help="the title the client writes over its window")
    ap.add_argument("--why", required=True, help="the owner's word: why the place is there")
    ap.add_argument("--id", type=int, help="the new id (default: the first free from 1381)")
    ap.add_argument("--fn", help="its internal name (default ED_<id>)")
    ap.add_argument("--author", default="owner")
    ap.add_argument("--walk-in", help="LOC:X,Y[;X,Y...]: cells of LOC that lead into it")
    ap.add_argument("--door", help="a or b, back to the walk-in's LOC; or a=<id>")
    ap.add_argument("--keep-mobs", action="store_true", help="keep the copy's inhabitants")
    ap.add_argument("--data", help="the data/ folder to write into (default: the repository's)")
    a = ap.parse_args(argv)
    try:
        walk_in = parse_walk_in(a.walk_in) if a.walk_in else None
        door = None
        if a.door:
            side, _, target = a.door.partition("=")
            door = (side, int(target) if target else None)
        out = make(a.src, a.title, a.why, a.data, a.id, a.fn, a.author, walk_in, door, a.keep_mobs)
    except (Refused, ValueError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
