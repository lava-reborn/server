"""The location editor's server half (tools/location_editor.py), without a
browser, on a copy of data/ and of client/objects:

  * tools/jsonrows.py: a member taken out, a row added and taken out, and the
    table's bytes come back as they were;
  * the model: the original's files read and written back byte for byte;
  * a new place from a copy: the first free id from 1381, its title and fn,
    the copy's creatures as inhabitants (those that could not stand there
    named in dropped), nothing written;
  * the checks: an inhabitant on a wall, a walk-in on a wall or an exit, a
    door to nowhere, no free entry, an exit walled off, a map cell taken,
    on the rim, cut off by the valley's wall or under an interior;
  * edits: a picture of the library put down as the original puts it most
    often, moved, nudged, taken out; an object put down with its anchor and
    its footprint stamped as walls f on even and odd rows, as
    custom_objects.place writes it; exits by their edge;
  * the owner's objects: an upload into client/objects and its manifest,
    the refusals (interlaced, too big, sizes that differ, no fps, not
    base64), an update, a delete refused while a location places it;
  * a save over HTTP: exactly the files expected, every other byte of data/
    kept; the server reads the place (world.Location), walks in from the
    original (travel.plan_walk_in) and out through the door back
    (travel.plan_exit); the map: settlements.json changed by this cell
    alone, the verified row, the name and the square; a recount that would
    move another place is refused;
  * a save that changes nothing writes nothing; a wall alone writes the
    file alone; the rows taken out again give the tables back byte for byte;
  * 409 when this location's rows changed on disk, 422 on an error, 403
    under another host name, 415 for anything but JSON;
  * the list, the palette, the creatures, the map, the CLI, and a render
    (with Pillow);
  * the page (tools/location_editor_ui/static) and the files it loads.

    python3 tools/test_location_editor.py
"""
import base64
import json
import re
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

W = tempfile.mkdtemp(prefix="test-location-editor-")
DATA = os.path.join(W, "data")
OBJ = os.path.join(W, "objects")
os.makedirs(DATA)
TABLES = ("placements.json", "passages.json", "map_labels.json", "map_cells.json",
          "settlements_verified.json", "settlements.json", "settlements_report.md",
          "exits_sides.json", "exits.json", "retired.json")
for _n in TABLES:
    shutil.copy(os.path.join(ROOT, "data", _n), os.path.join(DATA, _n))
shutil.copytree(os.path.join(ROOT, "data", "locations"), os.path.join(DATA, "locations"))
shutil.copytree(os.path.join(ROOT, "client", "objects"), OBJ)
# This process reads what the editor writes: set before anything asks.
os.environ.update(LAVA_LOCATION_EDITOR_GIT="0", LAVA_LOCATION_EDITOR_CACHE=os.path.join(W, "cache"),
                  LAVA_LOC_OVERLAY=os.path.join(DATA, "locations"),
                  LAVA_PASSAGES=os.path.join(DATA, "passages.json"),
                  LAVA_PLACEMENTS=os.path.join(DATA, "placements.json"))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import custom_objects as CO  # noqa: E402
import jsonrows  # noqa: E402
import lavaloc as L  # noqa: E402
import location_editor as E  # noqa: E402
import map_cells  # noqa: E402
import map_labels  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "the location editor"
E.configure(DATA, OBJ)
E._MEMO["ext_warm_done"] = True        # no extraction of every ext sprite in the background here


def snapshot():
    out = {}
    for d in (DATA, OBJ):
        for base, _dirs, names in os.walk(d):
            if "__pycache__" in base:
                continue
            for n in names:
                p = os.path.join(base, n)
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, W).replace(os.sep, "/")] = fh.read()
    return out


def changed(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def rel(paths):
    """Editor paths (data/..., client/objects/...) as this copy names them."""
    return sorted(p.replace("client/objects", "objects") for p in paths)


ORIGINAL = snapshot()

# --- jsonrows: one row in, one row out, the rest as it was ----------------------------------------
pas_text = ORIGINAL["data/passages.json"].decode("utf-8")
rows = [{"cells": [[3, 4]], "target_loc_id": 1381, "why": "t"}]
t1 = jsonrows.set_key(pas_text, ["walk_in", "102"], rows)
check("jsonrows: a walk-in added to the empty table reads back", json.loads(t1)["walk_in"], {"102": rows})
check("jsonrows: delete_key gives the bytes back, the empty object written {} again",
      jsonrows.delete_key(t1, ["walk_in", "102"]) == pas_text, True)
check("jsonrows: delete_key of a missing path changes nothing",
      jsonrows.delete_key(pas_text, ["doors", "999999", "a"]) == pas_text, True)
one = '{"a": 1, "b": {"x": 1, "y": 2}, "c": 3}'
check("jsonrows: delete_key on one line, first, middle and last",
      [jsonrows.delete_key(one, ["a"]), jsonrows.delete_key(one, ["b", "y"]), jsonrows.delete_key(one, ["c"])],
      ['{"b": {"x": 1, "y": 2}, "c": 3}', '{"a": 1, "b": {"x": 1}, "c": 3}', '{"a": 1, "b": {"x": 1, "y": 2}}'])
lab_text = ORIGINAL["data/map_labels.json"].decode("utf-8")
n_rows = len(jsonrows.items(lab_text, ["labels"]))
row_text = E.label_row({"x": 6000, "y": 1800, "text": "Проба", "add": True, "why": "t"})
t2 = jsonrows.append_item(lab_text, ["labels"], row_text)
check("jsonrows: a label row appended is the last row, in the file's two-line layout",
      (len(jsonrows.items(t2, ["labels"])), jsonrows.items(t2, ["labels"])[-1][0],
       t2.count("\n") - lab_text.count("\n")),
      (n_rows + 1, {"x": 6000, "y": 1800, "text": "Проба", "add": True, "why": "t"}, 2))
check("jsonrows: remove_item takes it out again, byte for byte",
      jsonrows.remove_item(t2, ["labels"], n_rows) == lab_text, True)
check("jsonrows: rows into an empty array and out of it",
      [jsonrows.append_item('{"l": []}', ["l"], "1"), jsonrows.remove_item('{"l": [\n 1\n]}', ["l"], 0)],
      ['{"l": [\n 1\n]}', '{"l": []}'])
ver_text = ORIGINAL["data/settlements_verified.json"].decode("utf-8")
v2 = E.set_rows(ver_text, ["cells", "6000,1800"], 1381)
check("set_rows: a table written as json.dumps(indent=1) gets its row the same way, and loses it again",
      (json.loads(v2)["cells"]["6000,1800"], E.set_rows(v2, ["cells", "6000,1800"], None) == ver_text,
       E.set_rows(ver_text, ["cells", "5970,1730"], 102) == ver_text),
      (1381, True, True))

# --- the model: the original's files, read and written back -------------------------------------
same = []
for i in (0, 1, 35, 102, 266, 522, 673, 1380):
    m = E.load_model(i)
    same.append((i, m["state"], E.model_bytes(m) == open(E.original_path(i), "rb").read()))
check("the model of an original file writes it back byte for byte", same,
      [(i, "original", True) for i in (0, 1, 35, 102, 266, 522, 673, 1380)])
m102 = E.load_model(102)
loc102 = world.location(102)
check("the model agrees with the server's reading: walls, entries, spawns",
      ({c[1] * m102["width"] + c[0] for c in m102["walls"]} == loc102.obstacles,
       [c[1] * m102["width"] + c[0] for c in m102["entries"]] == loc102.entries,
       [(c[1] * m102["width"] + c[0], c[2]) for c in m102["spawns"]] == loc102.spawns),
      (True, True, True))
try:
    E.load_model(99999)
    check("no location 99999", "found", "NotFound")
except E.NotFound:
    check("no location 99999", "NotFound", "NotFound")

# --- a new place from a copy ------------------------------------------------------------------------
FIRST = E.next_free_id()
check("the first free id is 1381 or the first after the overlay's", FIRST,
      next(i for i in range(world.FIRST_NEW_ID, world.NEW_ID_LIMIT) if i not in world.static_ids()))
got = E.new_model("Звездолёт Квакша", src=102, why="tools/test_location_editor.py")
M = got["model"]
check("a copy: the first free id, state new, the title, fn ED_<slug>, the copy's file underneath",
      (M["id"], M["state"], M["from"], M["attrs"]["title"], M["attrs"]["fn"], M["attrs"]["library"]),
      (FIRST, "new", 102, "Звездолёт Квакша", "ED_Zvezdolet_Kvaksha", "goldtraders"))
kept = sorted((r["type"], tuple(r["cell"])) for r in M["inhabitants"])
lost = sorted((r["type"], tuple(r["cell"])) for r in got["dropped"])
check("its <mobs> are empty, every typed slot an inhabitant or dropped with the reason",
      (M["raw"]["mobs"], M["spawns"], sorted(kept + lost) == sorted((t, (x, y)) for x, y, t in
                                                                   L.mob_slots(L.load(E.original_path(102))) if t)),
      ([], [], True))
check("  ..the black market's armour upgrader 639 is out of the game: dropped",
      [d["why"] for d in got["dropped"] if d["type"] == 639], ["существо выведено из игры (data/retired.json)"])
check("  ..each kept one says where it comes from", all(r["why"].startswith("DESIGNED (") for r in M["inhabitants"]),
      True)
check("nothing is written by making a model", changed(ORIGINAL, snapshot()), [])
orig102 = open(E.original_path(102), "rb").read()
mobs102 = b"<mobs>" + orig102.split(b"<mobs>")[1].split(b"</mobs>")[0] + b"</mobs>"
want102 = (orig102.replace(b'title="' + L.escape(m102["attrs"]["title"]).encode() + b'"',
                           b'title="' + L.escape("Звездолёт Квакша").encode() + b'"')
           .replace(b'fn="WH_Gold_Traders_old"', b'fn="ED_Zvezdolet_Kvaksha"')
           .replace(mobs102, b"<mobs></mobs>"))
check("the model writes the copy's bytes but for its title, fn and <mobs>", E.model_bytes(M) == want102, True)
empty = E.new_model("Пустошь редактора", empty={"w": 32, "h": 64}, why="t")["model"]
check("an empty place: 32x64 of the Desert library, a ring of edge exits and entries",
      (empty["width"], empty["height"], empty["attrs"]["library"],
       sorted({s for _x, _y, s in empty["exits"]}), len(empty["entries"]) > 10),
      (32, 64, "Desert", ["E", "N", "S", "W"], True))
check("  ..its file is the static style, read back by the server's parser",
      (E.model_bytes(empty).startswith(L.DECL.encode()), E.model_bytes(empty).endswith(
          b"<serverdata>\r\n</serverdata></location>")), (True, True))
for bad, why in (({"src": 262}, "262"), ({"empty": {"w": 40, "h": 40}}, "64x128"), ({"src": 99999}, "99999")):
    try:
        E.new_model("x", **bad)
        check("new refuses %r" % bad, None, why)
    except E.Refused as exc:
        check("new refuses %r" % bad, why in str(exc), True)


def errors(problems, what=None):
    return [p for p in problems if p["level"] == "error" and (what is None or p["what"] == what)]


# --- the checks -----------------------------------------------------------------------------------------
print("the checks")
check("the copy has no error but its missing why", [p["what"] for p in errors(E.lint(dict(M, index={})))], ["why"])
check("  ..and none with it", errors(E.lint(M)), [])
walls = sorted((r[0], r[1]) for r in M["walls"])
bad = dict(M, inhabitants=M["inhabitants"] + [{"type": M["inhabitants"][0]["type"], "cell": list(walls[0])}])
check("an inhabitant on a wall is an error at its cell",
      [(p["text"].endswith("на препятствии"), p["cells"]) for p in errors(E.lint(bad), "inhabitants")],
      [(True, [list(walls[0])])])
ex102 = E.exits_of(102)
wall102 = sorted(E.location_grid(102)[2])[0]
exit102 = sorted(ex102)[0]
bad = dict(M, walk_ins=[{"from": 102, "cells": [list(wall102)]}, {"from": 102, "cells": [list(exit102)]}])
check("a walk-in on a wall or an exit of the original is an error there",
      sorted((p["loc"], p["cells"][0] == list(wall102), p["cells"][0] == list(exit102))
             for p in errors(E.lint(bad), "walk_in")),
      [(102, False, True), (102, True, False)])
bad = dict(M, doors={"b": {"target": 999999}})
check("a door the place has not, to a place that is not: errors",
      sorted(p["text"][:12] for p in errors(E.lint(bad), "doors")), ["двери b нет ", "дверь b ведё"])
bad = dict(M, entries=[])
check("no entry: an error", [p["what"] for p in errors(E.lint(bad))], ["entries"])
north = [r for r in M["exits"] if r[2] == "N"]
bad = dict(M, walls=M["walls"] + [[r[0], r[1], "f"] for r in north])
check("the northern exits walled off: the walk does not reach them",
      [p["text"] for p in errors(E.lint(bad), "walk")], ["до выхода N не дойти от входов"])
m673 = E.new_model("Тайник Квакши", src=673, why="t")["model"]
check("a copy of an interior with no door leading anywhere: no way out",
      [p["what"] for p in errors(E.lint(m673))], ["ways"])

inside, outside = E.walks()
settled = E.settlements_table()


def map_errors(model, cell):
    mm = dict(model, map={"cell": list(cell), "label": "", "square": None})
    return [p["text"] for p in errors(E.map_problems(mm))]


check("a map cell another place stands on is refused",
      [t for t in map_errors(M, (5970, 1730)) if "занята" in t], ["клетка карты 5970,1730 занята: там 102"])
check("  ..one on the world's rim", any("кромке" in t for t in map_errors(M, (world.MAP_X[0], 1700))), True)
check("  ..an interior is never put on the map", any("выходами по краям" in t for t in map_errors(m673, (5990, 1740))),
      True)
stranded = None
for c in sorted(settled):
    if c in inside or c in outside:
        continue
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            n = (c[0] + dx, c[1] + dy)
            if n not in settled and world.passable(*n) and n not in inside and n not in outside \
                    and n not in E.retired_cells() and n not in E.patrol_cells():
                stranded = n
                break
        if stranded:
            break
    if stranded:
        break
if stranded:
    check("  ..a cell the valley's wall cuts off (data/test_borders.py pins how many places are)",
          any("отрезана стеной" in t for t in map_errors(M, stranded)), True)
else:
    print("  --  no cut-off cell found near the stranded places: that check is skipped")

# a free cell near the start for the place
CELL = None
for r in range(2, 30):
    for dx in range(-r, r + 1):
        for dy in (-r, r):
            c = (5990 + dx, 1745 + dy)
            if c in settled or c in E._tooltips():
                continue
            if not map_errors(M, c):
                CELL = c
                break
        if CELL:
            break
    if CELL:
        break
check("a free cell is found for the place on the map", CELL is not None, True)

# --- edits ------------------------------------------------------------------------------------------------
print("edits")
E.usage(wait=True)
lib = "goldtraders"
u = E.usage()
pic = next(n for n in sorted(E.art_index()["libraries"][lib]["exports"]) if E.usage().get("lib:" + n))
most = u["lib:" + pic][0]
free_cells = sorted(set((x, y) for x in range(10, 50) for y in range(30, 90)) - set(walls)
                    - {(r[0], r[1]) for r in M["exits"]})
fx, fy = free_cells[0]
m1, inf = E.edit(M, {"op": "place", "kind": "lib", "id": pic, "cell": [fx, fy]})
sp = m1["sprites"][-1]
check("a picture of the library goes down as the original puts it most often",
      (sp["id"], sp["type"], sp["dx"], sp["dy"], sp["front"], sp["anchors"]),
      (pic, "lib", most["dx"], most["dy"], most["front"], [[fx, fy]]))
check("  ..the model it came from is untouched", len(M["sprites"]) == len(m102["sprites"]), True)
si = len(m1["sprites"]) - 1
m2, _ = E.edit(m1, {"op": "move", "sprite": si, "anchor": 0, "cell": [fx + 1, fy]})
m3, _ = E.edit(m2, {"op": "nudge", "sprite": si, "anchor": 0, "dx": 5, "dy": -7})
m4, _ = E.edit(m3, {"op": "delete", "sprite": si, "anchor": 0})
check("  ..moved, nudged, taken out",
      (m2["sprites"][si]["anchors"], (m3["sprites"][si]["dx"], m3["sprites"][si]["dy"]), len(m4["sprites"])),
      ([[fx + 1, fy]], (5, -7), len(M["sprites"])))
withfoot = next((n for n in sorted(E.art_index()["libraries"][lib]["exports"])
                 if (u.get("lib:" + n) or [{}])[0].get("footprint")), None)
taken_cells = set(walls) | {(r[0], r[1]) for r in M["exits"]}
if withfoot:
    v = u["lib:" + withfoot][0]
    # where every cell of its footprint is open ground
    gx, gy = next(c for c in free_cells if all(
        0 <= p[0] < 64 and 0 <= p[1] < 128 and p not in taken_cells
        for p in L.offsets_cells([(d[0], d[1]) for d in v["footprint"]], c[0], c[1])))
    m5, inf = E.edit(M, {"op": "place", "kind": "lib", "id": withfoot, "cell": [gx, gy], "stamp": True})
    want = [list(c) for c in L.offsets_cells([(d[0], d[1]) for d in v["footprint"]], gx, gy)]
    check("  ..with its footprint: the walls its placings in the original have in common",
          sorted(inf["cells"]), sorted(want))
    m6, inf6 = E.edit(m5, {"op": "delete", "sprite": len(m5["sprites"]) - 1, "anchor": 0, "stamp": True})
    check("  ..and taken out with it", (sorted(map(tuple, m6["walls"])) == sorted(map(tuple, M["walls"])),
                                       sorted(inf6["cells"])), (True, sorted(want)))
mx, _ = E.edit(M, {"op": "exits", "cells": [[0, 40], [63, 41], [30, 1], [31, 127]], "side": "auto"})
check("exits by their edge", {(r[0], r[1]): r[2] for r in mx["exits"] if (r[0], r[1]) in
                              {(0, 40), (63, 41), (30, 1), (31, 127)}},
      {(0, 40): "W", (63, 41): "E", (30, 1): "N", (31, 127): "S"})
try:
    E.edit(M, {"op": "exits", "cells": [[30, 60]], "side": "auto"})
    check("a cell off the edges is no edge exit", "taken", "refused")
except E.Refused:
    check("a cell off the edges is no edge exit", "refused", "refused")

# --- HTTP ---------------------------------------------------------------------------------------------------
srv = E.serve(0)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()


def call(path, body=None, headers=None, raw=None, ctype="application/json"):
    """(status, parsed JSON or bytes)."""
    h = {"Host": "127.0.0.1:%d" % PORT}
    data = None
    if body is not None or raw is not None:
        data = raw if raw is not None else json.dumps(body).encode("utf-8")
        h["Content-Type"] = ctype
    h.update(headers or {})
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path), data=data, headers=h,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            out, code, ct = resp.read(), resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        out, code, ct = exc.read(), exc.code, exc.headers.get("Content-Type", "")
    return code, (json.loads(out) if ct.startswith("application/json") else out)


print("http")
code, out = call("/api/info")
check("GET /api/info: sizes, tracks, the id range", (code, out["sizes"], "Village" in out["tracks"], out["first_new_id"]),
      (200, [[64, 128], [32, 64]], True, 1381))
code, out = call("/api/locations")
row = next(r for r in out["locations"] if r["id"] == 102)
check("GET /api/locations: 102 with its title, size, library, cell, inhabitants",
      (code, row["state"], row["size"], row["library"], row["cell"], row["inhabitants"] > 0),
      (200, "original", [64, 128], "goldtraders", [5970, 1730], True))
code, out = call("/api/location/102")
check("GET /api/location/102: the model", (code, out["id"], out["state"], out["etag"] == m102["etag"]),
      (200, 102, "original", True))
check("GET /api/location/99999: 404", call("/api/location/99999")[0], 404)
code, out = call("/api/new", {"from": 673, "title": "Тайник", "why": "t"})
check("POST /api/new: a model, nothing written", (code, out["model"]["id"], changed(ORIGINAL, snapshot())),
      (200, FIRST, []))
code, out = call("/api/check", {"model": dict(M, inhabitants=[{"type": 1263, "cell": list(walls[0])}]),
                                "quick": True})
check("POST /api/check: the inhabitant on a wall, at its cell",
      (code, [(p["what"], p["cells"]) for p in errors(out["problems"])]),
      (200, [("inhabitants", [list(walls[0])])]))
code, out = call("/api/save", {"model": dict(M, inhabitants=[{"type": 1263, "cell": list(walls[0])}]),
                               "etag": M["etag"]})
check("POST /api/save with an error: 422, nothing written",
      (code, bool(errors(out["problems"])), changed(ORIGINAL, snapshot())), (422, True, []))
code, out = call("/api/save", {"model": M, "etag": "0" * 32})
check("POST /api/save with a stale etag: 409", code, 409)
check("a request under another host name: 403", call("/api/locations", headers={"Host": "evil.example:%d" % PORT})[0],
      403)
check("a post that is not JSON: 415", call("/api/check", raw=b"model=1", ctype="text/plain")[0], 415)
check("a body that does not parse: 400", call("/api/check", raw=b"{", ctype="application/json")[0], 400)
code, out = call("/api/edit", {"model": M, "op": {"op": "fly"}})
check("an edit it does not know: 400", code, 400)
# the page itself: tools/location_editor_ui/static, built and committed
# (bash tools/location_editor_ui/build.sh); every file it loads is served
code, page = call("/")
assets = re.findall(rb'(?:src|href)="\./(assets/[^"]+)"', page) if code == 200 else []
check("GET /: the built page, its script and its styles, each served",
      (code, b'id="root"' in page, sorted(a.rsplit(b".", 1)[-1] for a in assets),
       sorted({call("/" + a.decode())[0] for a in assets})),
      (200, True, [b"css", b"js"], [200]))

# --- the owner's objects ---------------------------------------------------------------------------------------
print("objects")


def png(w, h, rgba, interlace=0):
    raw = b"".join(b"\0" + bytes(rgba) * w for _ in range(h))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, interlace))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def b64(b):
    return base64.b64encode(b).decode()


f0, f1 = png(16, 24, (200, 40, 40, 255)), png(16, 24, (40, 200, 40, 128))
man_before = open(os.path.join(OBJ, "manifest.json"), "rb").read()
for body, said in (({"title": "x", "frames": [b64(png(4, 4, (1, 2, 3, 4), interlace=1))]}, "interlaced"),
                   ({"title": "x", "frames": [b64(png(3000, 1, (1, 2, 3, 4)))]}, "2880"),
                   ({"title": "x", "frames": [b64(f0), b64(png(8, 8, (1, 2, 3, 4)))], "fps": 5}, "одного размера"),
                   ({"title": "x", "frames": [b64(f0), b64(f1)]}, "fps"),
                   ({"title": "x", "frames": ["@@not base64@@"]}, "base64"),
                   ({"title": "", "frames": [b64(f0)]}, "title")):
    code, out = call("/api/object", body)
    check("an object refused (%s): 400 and why" % said, (code, said in out.get("error", "")), (400, True))
check("  ..and nothing written by any of them", changed(ORIGINAL, snapshot()), [])
code, out = call("/api/object", {"title": "Тестовая бочка", "frames": [b64(f0), b64(f1), b64(f0)], "fps": 5,
                                 "anchor": [8, 23], "front": [[0, 0], [1, 0]], "footprint": [[0, 0], [1, 0]]})
OID = out.get("id")
check("POST /api/object: an id from the title, its pictures (a repeated one stored once), its row",
      (code, OID, sorted(os.listdir(os.path.join(OBJ, OID))), out["entry"]["frames"], out["entry"]["anchor"]),
      (200, "c_testovaya_bochka", ["0.png", "1.png"], ["0.png", "1.png", "0.png"], [8, 23]))
built, report = CO.build(OBJ, CO.base_paths(os.path.join(ROOT, "client", "base.txt")))
check("  ..which the release build makes into its sprite file",
      "locations/libs/sprite/c_testovaya_bochka.swf" in built, True)
check("  ..and the manifest is written the one way it is written",
      open(os.path.join(OBJ, "manifest.json"), encoding="utf-8").read() == CO.manifest_text(CO.load_raw(OBJ)), True)
code, out = call("/api/objects")
check("GET /api/objects: the object, its pictures, used nowhere",
      (code, out["objects"][OID]["pictures"][0], out["objects"][OID]["used_in"]),
      (200, "/api/object/%s/0.png" % OID, []))
code, data = call("/api/object/%s/1.png" % OID)
check("GET /api/object/<id>/<file>: the picture", (code, data == f1), (200, True))
entry = CO.check_entry(OID, CO.load_raw(OBJ)[OID])
open_m = E._components(64, 128, {(r[0], r[1]) for r in M["walls"]}, [(r[0], r[1]) for r in M["entries"]])
busy = {(r[0], r[1]) for r in M["exits"] + M["entries"]} | {tuple(r["cell"]) for r in M["inhabitants"]}


def spot(parity, rows=range(40, 100)):
    """A cell on an even or odd row where the object's anchor and footprint
    stand on open ground of the place, nobody's."""
    for y in rows:
        if y % 2 != parity:
            continue
        for x in range(10, 54):
            cells = [(x, y)] + CO.absolute(entry["footprint"], x, y)
            if all(c in open_m and c not in busy for c in cells) and \
                    all(n in open_m for c in cells for n in L.neighbours(*c)):
                return x, y
    raise SystemExit("no open ground for the object")


SPOTS = {0: spot(0), 1: spot(1)}
for parity, (ox, oy) in sorted(SPOTS.items()):
    mo, inf = E.edit(M, {"op": "place", "kind": "object", "id": OID, "cell": [ox, oy], "stamp": True})
    sp = mo["sprites"][-1]
    want = CO.place(OID, entry, ox, oy)
    check("the object on an %s row: <sprite> as custom_objects.place writes it, its footprint as walls f"
          % ("even", "odd")[parity],
          ([("id", sp["id"]), ("dx", str(sp["dx"])), ("dy", str(sp["dy"])), ("front", sp["front"]),
            ("type", sp["type"])], sp["anchors"], "".join("%02x%02x%s" % (x, y, c) for x, y, c in mo["walls"]
                                                          if [x, y] in inf["cells"])),
          (want["attrs"], [[ox, oy]], want["obstacles"]))
OX, OY = SPOTS[1]

# --- a save -------------------------------------------------------------------------------------------------------
print("a save")
model, _ = E.edit(M, {"op": "place", "kind": "object", "id": OID, "cell": [OX, OY], "stamp": True})
g102 = E.location_grid(102)
reach102 = E._components(64, 128, g102[2], [c for c in g102[3] if c not in g102[2]])
people102 = {(r[0], r[1]) for r in m102["spawns"]}
# the walk-in: two cells of the black market a walker reaches, off its exits, entries and people
WALK = [c for c in sorted(reach102) if c not in ex102 and c not in set(g102[3]) and c not in people102
        and 20 <= c[1] <= 60 and 15 <= c[0] <= 45][:2]
mreach = E._components(64, 128, {(r[0], r[1]) for r in model["walls"]},
                       [(r[0], r[1]) for r in model["entries"]])
# the door back: three open cells of the place, nobody's
DOOR = [c for c in sorted(mreach) if c not in busy and 30 <= c[1] <= 50 and 25 <= c[0] <= 40
        and c not in {tuple(p) for p in CO.absolute(entry["footprint"], OX, OY)} and c != (OX, OY)][:3]
model, _ = E.edit(model, {"op": "exits", "cells": [list(c) for c in DOOR], "side": "a"})
model["doors"] = {"a": {"target": 102, "why": ""}}
model["walk_ins"] = [{"from": 102, "cells": [list(c) for c in WALK], "why": ""}]
LABEL = "Звездолёт Квакша<br>Проба редактора"
model["map"] = {"cell": list(CELL), "label": LABEL, "square": "tan", "why": ""}
check("the place with its door, walk-in, object and map cell has no error", errors(E.lint(model)), [])

# a recount that would move another place: the copy's settlements.json lacks a row the placer makes
BEFORE_SAVE = snapshot()
key_ = next(k for k in sorted(json.loads(ORIGINAL["data/settlements.json"])["cells"])
            if k not in json.loads(ORIGINAL["data/settlements_verified.json"])["cells"])
tampered = json.loads(ORIGINAL["data/settlements.json"])
gone = tampered["cells"].pop(key_)
with open(os.path.join(DATA, "settlements.json"), "w", encoding="utf-8", newline="\n") as fh:
    json.dump(tampered, fh, ensure_ascii=False, indent=1, sort_keys=True)
    fh.write("\n")
t0 = time.time()
code, out = call("/api/save", {"model": model, "etag": model["etag"]})
check("a save whose map recount would move another place is refused there (%.0f s)" % (time.time() - t0),
      (code, [p["cells"] for p in errors(out.get("problems") or [], "placer")]),
      (422, [[[int(v) for v in key_.split(",")]]]))
with open(os.path.join(DATA, "settlements.json"), "wb") as fh:
    fh.write(ORIGINAL["data/settlements.json"])
check("  ..and nothing written", changed(BEFORE_SAVE, snapshot()), [])

t0 = time.time()
code, out = call("/api/save", {"model": model, "etag": model["etag"]})
after = snapshot()
check("POST /api/save: 200 (%.0f s)" % (time.time() - t0), (code, out.get("error"), out.get("id")), (200, None, FIRST))
check("  ..exactly these files, and every other byte of data/ as it was",
      changed(ORIGINAL, after),
      sorted(["data/exits_sides.json", "data/locations/index.json", "data/locations/static/%d.xml" % FIRST,
              "data/map_cells.json", "data/map_labels.json", "data/passages.json", "data/placements.json",
              "data/settlements.json", "data/settlements_report.md", "data/settlements_verified.json",
              "objects/c_testovaya_bochka/0.png", "objects/c_testovaya_bochka/1.png", "objects/manifest.json"]))
check("  ..as the answer says", rel(out["written"]), sorted(p for p in changed(ORIGINAL, after) if
                                                          not p.startswith("objects/")))
saved = out["model"]
xml = after["data/locations/static/%d.xml" % FIRST]
check("the file: the static style, no BOM, one line", (xml[:5], b"\n" in xml.replace(b"\r\n</serverdata>", b"")),
      (b"<?xml", False))
lm = L.load(xml)
check("  ..the object's <sprite> and its walls f, read back by lavaloc",
      ([s for s in lm["sprites"] if s["id"] == OID][0]["anchors"],
       set(CO.place(OID, entry, OX, OY)["footprint"]) <= {(x, y) for x, y, e in lm["lists"]["obstacles"] if e == "f"}),
      ([(OX, OY)], True))
world._CACHE.clear()
loc = world.Location(FIRST)
check("the server reads the place: title, entries, no <mobs>, the door's cells",
      (loc.title, bool([c for c in loc.entries if c not in loc.obstacles]), loc.spawns),
      ("Звездолёт Квакша", True, []))
idx = json.loads(after["data/locations/index.json"])["locations"][str(FIRST)]
check("  ..its row in the index", (idx["title"], idx["from"], idx["why"]),
      ("Звездолёт Квакша", 102, "tools/test_location_editor.py"))
es = json.loads(after["data/exits_sides.json"])
check("  ..its exits_sides rows are its outzones (lavaloc.exits_row)",
      (es["locations"][str(FIRST)] == L.exits_row(lm), es["summary"][str(FIRST)]["sides"]),
      (True, ["W", "N", "E", "S", "a"]))
pl = json.loads(after["data/placements.json"])["locations"][str(FIRST)]
check("  ..its inhabitants in data/placements.json, each with its why",
      ([(r["type"], r["cell"]) for r in pl] == [(r["type"], r["cell"]) for r in M["inhabitants"]],
       all(r["why"] for r in pl)), (True, True))
travel._PASSAGES = None
travel._WAYS.clear()
travel._SIDES.clear()
src = world.location(102)
pos = WALK[0][1] * src.width + WALK[0][0]
ex = travel.plan_walk_in(src, pos, 5970, 1730)
check("travel: the walk-in from 102 leads into the place, beside its door back",
      (ex.loc_id, (ex.pos % loc.width, ex.pos // loc.width) in {tuple(c) for c in
                                                                 [[e[0], e[1]] for e in lm["lists"]["inzones"]]}),
      (FIRST, True))
dpos = DOOR[0][1] * loc.width + DOOR[0][0]
ex = travel.plan_exit(loc, dpos, CELL[0], CELL[1])
check("travel: its door a leads back to 102", ex.loc_id, 102)
settle = json.loads(after["data/settlements.json"])["cells"]
before_settle = json.loads(ORIGINAL["data/settlements.json"])["cells"]
check("the map: settlements.json gains this cell alone (data/place_settlements.py rerun)",
      {k: (before_settle.get(k), settle.get(k)) for k in set(settle) | set(before_settle)
       if settle.get(k) != before_settle.get(k)}, {E._key(*CELL): (None, FIRST)})
ver = json.loads(after["data/settlements_verified.json"])
check("  ..its verified row, with a why", (ver["cells"].get(E._key(*CELL)), bool(ver["why"].get(E._key(*CELL)))),
      (FIRST, True))
check("  ..its name added over the cell (server/map_labels.py)",
      (CELL[0], CELL[1], None, LABEL) in map_labels.load(os.path.join(DATA, "map_labels.json")), True)
plan_ = map_cells.load(os.path.join(DATA, "map_cells.json"), os.path.join(DATA, "retired.json"))
check("  ..and its square (server/map_cells.py)", plan_.paint.get(CELL, ("?",))[0], "tan")
report = after["data/settlements_report.md"].decode("utf-8")
verified_count = [int(re.search(r"проверено игрой (\d+)", r).group(1))
                  for r in (ORIGINAL["data/settlements_report.md"].decode("utf-8"), report)]
check("  ..and the report counts one verified cell more", verified_count[1] - verified_count[0], 1)
code, out = call("/api/locations")
row = next(r for r in out["locations"] if r["id"] == FIRST)
check("the list has the place: ours, its cell, its inhabitants",
      (row["state"], row["cell"], row["inhabitants"], row["from"]), ("ours", list(CELL), len(pl), 102))

# --- what a save writes, and what it does not ---------------------------------------------------------------
code, out = call("/api/save", {"model": saved, "etag": saved["etag"]})
check("a save that changes nothing writes nothing", (code, out["written"], changed(after, snapshot())),
      (200, [], []))
m2 = json.loads(json.dumps(saved))
free = next(c for c in sorted(mreach) if c not in {(r[0], r[1]) for r in m2["walls"] + m2["exits"]}
            and c not in {(r[0], r[1]) for r in m2["entries"]} and 40 <= c[1] <= 80
            and c not in {tuple(r["cell"]) for r in m2["inhabitants"]})
m2["walls"].append([free[0], free[1], "f"])
t0 = time.time()
code, out = call("/api/save", {"model": m2, "etag": m2["etag"]})
check("a wall alone: the file alone, no recount (%.1f s)" % (time.time() - t0), (code, out["written"]),
      (200, ["data/locations/static/%d.xml" % FIRST]))
m3 = out["model"]
with open(os.path.join(DATA, "placements.json"), "rb") as fh:
    pl_raw = fh.read()
pdoc = json.loads(pl_raw)
pdoc["locations"][str(FIRST)].pop()
with open(os.path.join(DATA, "placements.json"), "w", encoding="utf-8") as fh:
    fh.write(E.dumps1(pdoc))
code, out = call("/api/save", {"model": m3, "etag": m3["etag"]})
check("a save after this place's rows changed on disk: 409", code, 409)
with open(os.path.join(DATA, "placements.json"), "wb") as fh:
    fh.write(pl_raw)

# the rows taken out again: the tables as they were, byte for byte
m4 = json.loads(json.dumps(m3))
m4["inhabitants"], m4["walk_ins"], m4["doors"] = [], [], {}
m4["map"] = dict(m4["map"], label="", square=None)
code, out = call("/api/save", {"model": m4, "etag": m4["etag"]})
now = snapshot()
check("its inhabitants, ways, name and square taken out: those tables back byte for byte, the map cell kept",
      (code if code == 200 else (code, [p["text"] for p in errors(out.get("problems") or [])]), [n for n in ("data/placements.json", "data/passages.json", "data/map_labels.json", "data/map_cells.json")
              if now[n] != ORIGINAL[n]], now["data/settlements_verified.json"] == after["data/settlements_verified.json"]),
      (200, [], True))

# --- objects in use ---------------------------------------------------------------------------------------------
code, out = call("/api/object/delete", {"id": OID})
check("an object a location places is not deleted: 409 and where", (code, out.get("used_in")), (409, [FIRST]))
code, out = call("/api/object/update", {"id": OID, "anchor": [1, 1]})
check("  ..nor its anchor changed", code, 409)
code, out = call("/api/object/update", {"id": OID, "title": "Бочка"})
check("  ..its title is", (code, CO.load_raw(OBJ)[OID]["title"]), (200, "Бочка"))
m5 = out_model = call("/api/location/%d" % FIRST)[1]
si = next(i for i, s in enumerate(m5["sprites"]) if s["id"] == OID)
m5, inf = E.edit(m5, {"op": "delete", "sprite": si, "anchor": 0, "stamp": True})
check("taken out of the place with its footprint", sorted(inf["cells"]),
      sorted([list(c) for c in CO.place(OID, entry, OX, OY)["footprint"]]))
code, out = call("/api/save", {"model": m5, "etag": m5["etag"]})
check("  ..saved", (code, out.get("written")), (200, ["data/locations/static/%d.xml" % FIRST]))
code, out = call("/api/object/delete", {"id": OID})
check("then deleted: its folder gone, the manifest as it was before it",
      (code, os.path.isdir(os.path.join(OBJ, OID)), open(os.path.join(OBJ, "manifest.json"), "rb").read() == man_before),
      (200, False, True))

# --- the rest of the API ------------------------------------------------------------------------------------------
print("the rest")
code, out = call("/api/palette/%d" % FIRST)
names = {(i["name"], i["type"]) for i in out["items"]}
check("GET /api/palette: the library's pictures and the ext sprites", (code, out["library"],
      (pic, "lib") in names, ("a_campfire.png", "ext") in names), (200, "goldtraders", True, True))
code, out = call("/api/mobs?q=ow_Terminal&limit=50")
hit = [m for m in out["mobs"] if m["type"] == 1263]
check("GET /api/mobs: a creature by its internal name, with its name, level and icon",
      (code, len(hit), sorted(hit[0]) if hit else None, hit[0]["icon"] if hit else None),
      (200, 1, ["icon", "known", "level", "name", "retired", "role", "root", "sub", "type"],
       "/api/mobicon/1263.webp"))
code, out = call("/api/map")
X, Y = world.MAP_X, world.MAP_Y
bits = base64.b64decode(out["blocked"])
check("GET /api/map: the world's bounds, places, ours, a blocked bit per cell",
      (code, out["bounds"], out["settlements"]["5970,1730"], out["ours"].get(str(FIRST)),
       len(bits) == ((X[1] - X[0] + 1) * (Y[1] - Y[0] + 1) + 7) // 8),
      (200, {"x": list(X), "y": list(Y)}, 102, list(CELL), True))
cli = subprocess.run([sys.executable, os.path.join(HERE, "location_editor.py"), "--data", DATA, "--objects", OBJ,
                      "show", str(FIRST)], capture_output=True, text=True, timeout=300)
check("CLI show: the model", (cli.returncode, json.loads(cli.stdout)["attrs"]["title"] if cli.returncode == 0 else
                              cli.stderr[-300:]), (0, "Звездолёт Квакша"))
cli = subprocess.run([sys.executable, os.path.join(HERE, "location_editor.py"), "--data", DATA, "--objects", OBJ,
                      "check", str(FIRST), "--quick"], capture_output=True, text=True, timeout=300)
check("CLI check --quick: no error", (cli.returncode, cli.stdout.strip().splitlines()[-1][:9]), (0, "0 errors,"))
if E.have_pictures():
    code, data = call("/api/render/%d.png?scale=0.25&layers=art,obstacles" % FIRST)
    from PIL import Image
    import io
    check("GET /api/render: a PNG of the place at a quarter size", (code, Image.open(io.BytesIO(data)).size),
          (200, (640, 480)))
else:
    print("  --  Pillow or numpy not installed: the render is not checked here (WSL ~/venvs/lavagd has them)")

srv.shutdown()
shutil.rmtree(W, ignore_errors=True)
print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("location editor OK")
