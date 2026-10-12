#!/usr/bin/env python3
"""The location editor's server: places of ours (data/locations) made from a
copy of a location or from nothing, laid out cell by cell and piece by
piece, checked the way the server and CI check them, and written into data/
row by row.

    python3 tools/location_editor.py [serve] [--port 8096] [--host 127.0.0.1]
    python3 tools/location_editor.py new (--from ID | --empty 64x128 [--library L])
            --title T --why W [--id N] [--author A]
            [--walk-in LOC:X,Y[;X,Y...]] [--door a|b[=ID]]
    python3 tools/location_editor.py show ID           the model, as GET /api/location/ID
    python3 tools/location_editor.py check ID|MODEL.json [--quick]
    python3 tools/location_editor.py render ID|MODEL.json -o OUT.png [--layers art] [--scale 0.5]
    python3 tools/location_editor.py save MODEL.json [--etag E]

Every command takes --data DIR (default: the repository's data/) and
--objects DIR (default: client/objects). Run it in WSL:
PYTHONUTF8=1 ~/venvs/lavagd/bin/python tools/location_editor.py -- Pillow and
numpy draw the pictures, everything else is the standard library. It prints
its address and never opens a window: the owner opens http://127.0.0.1:8096/
(LAVA_LOCATION_EDITOR_PORT) in his own browser, which WSL's mirrored network
reaches. The page is tools/location_editor_ui (Vite, React, TypeScript; the
canvas a plain TS module), built into its static/ by `bash
tools/location_editor_ui/build.sh` and committed built; without static/ the
address answers with a page that lists this API.

WHAT IT READS. LAVA_RES, the original's slice the server reads: by default
CI's (~/lava-cicd2/ci-assets2/res), else the Desktop client. A launcher's
res holds the release's own 262.xml «Тотем», which would skew the map's
recount; /api/info says whether RES is the original (res_original). The
pictures come through tools/location_art.py (LAVA_ART_RES, LAVA_ART_STORE,
its cache under ~/.cache/lava-location-editor).

THE MODEL. A location as JSON, what GET /api/location/<id> gives, POST
/api/check and /api/save take back, and `show` / `save` print and read:

  id, state       the id; "new" (not written yet), "ours" (data/locations)
                  or "original" (the original's file: read only)
  from            the location it was copied from (null: made empty)
  attrs           every attribute of <location> as written: title, pvp
                  ("0"/"1"), war ("0"/"1"), bgsound (a track of
                  /api/info tracks, "" for the default), fn (ED_<slug> for
                  a new place), library, bg, bgExt, dir, preloader, version
  width, height   64x128 or 32x64, fixed when the place is made
  background      {type: lib|ext, id, fx} (fx "water" animates it)
  sprites         [{id, type: lib|ext, dx, dy, front, anchors: [[x, y]]}]:
                  one picture at each anchor cell, its top-left (lib) or
                  its SWF's origin (ext, the owner's objects among them) at
                  the cell's centre plus (dx, dy); front, the depth line,
                  as written (tools/lavaloc.py front_cells)
  decals          [{id, type, dx, dy}]: <bgdecoration>, at absolute pixels
  walls           [[x, y, code]]: <obstacles>; code "f" a wall (the
                  default), "1" a counter shot over in the ranges, others
                  kept as the original has them
  exits           [[x, y, side]]: <outzones>; side W N E S by the edge,
                  a or b a door (the client's zones are written from these)
  entries         [[x, y]]: <inzones>, where a player arrives
  war_entries     [[x, y]]: <warinzones>
  spawns          [[x, y, type]]: the file's own <mobs>, read only (a new
                  place has none: a copy's become inhabitants)
  raw             what the file carries that is not edited: {mobs, tails,
                  serverdata}; give it back as it came
  inhabitants     [{type, cell: [x, y], why, escort?}]: the location's rows
                  of data/placements.json (why filled in when left empty)
  doors           {a|b: {target, why}}: data/passages.json 'doors' for the
                  location's own doors a and b (confidence high, source
                  editor)
  walk_ins        [{from, cells: [[x, y]], why}]: data/passages.json
                  'walk_in' rows of another location that lead here (its
                  file is not touched; the client opens no window there)
  no_map          {why} or null: data/passages.json 'no_map'
  map             {cell: [x, y], label, square, why} or null: the map cell
                  (data/settlements_verified.json, then data/settlements.json
                  and settlements_report.md by data/place_settlements.py),
                  the name over it (data/map_labels.json, an add) and the
                  square painted on it (data/map_cells.json 'paint', one
                  of server/map_cells.py PALETTE, or null)
  index           {title, from, author, created, why}: the row of
                  data/locations/index.json; why, the owner's word, is a must
  etag            what the tables held for this location when it was read

A problem (POST /api/check, a 422) is {level: error|warning, what, text,
cells: [[x, y]], loc}: an error blocks a save, cells say where (in loc,
when it is another location's -- a walk-in's), text is for the owner.

THE API. Under 127.0.0.1 and localhost only, POST bodies JSON only, as
tools/quest_editor.py (a page of another site can neither post a form here
nor rebind its own name to this port).

  GET  /api/info                 RES, art, sizes, tracks, obstacle codes,
                                 sides, map colours, layers, id range
  GET  /api/locations            {locations: [{id, title, fn, size: [w, h],
                                 library, war, pvp, state, cell, from,
                                 inhabitants, doors}]}
  GET  /api/location/<id>        the model
  GET  /api/render/<id>.png      the location drawn; ?layers=art,obstacles,...
                                 (tools/location_art.py LAYERS; art = background,
                                 decals, sprites), &scale=0.5, &order=reverse|file
  POST /api/render               {model, layers, scale}: an unsaved model drawn
  GET  /api/palette/<id>         {library, items: [{name, type: lib|ext,
                                 origin (object: the owner's), title, w, h,
                                 thumb (URL, once extracted), frames,
                                 default: {dx, dy, front, footprint}}],
                                 warming}: what the location can place
  GET  /art/<sha>/<file>         a picture of the art cache
  GET  /api/mobs?q=&limit=       [{type, name, sub, level, root, role, known,
                                 retired, icon}]
  GET  /api/mobicon/<type>.webp  a creature's icon (its stand frame)
  GET  /api/map                  {bounds, cell, tile, tiles: [{n, x, y, url}],
                                 settlements: {"x,y": id}, titles, ours,
                                 retired, cut: {"x,y": why} (the owner's
                                 cuts: no new place there), patrols,
                                 labels: [[x, y, text]],
                                 starts, blocked, reachable}: blocked and
                                 reachable are bitsets over the bounds, row
                                 by row, base64
  GET  /api/map/tile/<n>.jpg     a tile of the global map, as the release has it
  GET  /api/objects              {objects: {id: entry + pictures, used_in}}
  GET  /api/object/<id>/<file>   one of an object's pictures
  POST /api/new                  {from: id | empty: {w, h, library, background,
                                 ring}, title, why, id?} -> {model, dropped}:
                                 a new model, nothing written; its id the
                                 first free from 1381 against the overlay and
                                 origin/main
  POST /api/edit                 {model, op} -> {model, cells}: one edit the
                                 server works out (ops below)
  POST /api/check                {model, quick?} -> {problems, seconds}
  POST /api/save                 {model, etag} -> {id, written, model,
                                 problems}; 409 when this location's rows or
                                 file changed on disk since it was read, 422
                                 on an error
  POST /api/object               {title, frames: [base64 PNG or JPEG], fps,
                                 anchor: [x, y], front, footprint, id?, kind?,
                                 note?} -> {id, entry}: client/objects/<id>/
                                 and its manifest row
  POST /api/object/update        {id, title?, fps?, anchor?, front?,
                                 footprint?, note?, frames?}
  POST /api/object/delete        {id}; 409 while a location places it

  edit ops:
    {op: place, kind: lib|ext|object, id, cell, stamp?, dx?, dy?, front?}
        a new sprite on the cell. dx, dy and front default to what the
        original places that picture with most often (an object: -anchor
        and its front); stamp also writes its footprint as walls (an
        object's footprint as "f", a picture's the walls its original
        placings have in common)
    {op: move, sprite, anchor, cell, stamp?}   moves one placing (the
        footprint's walls with it when stamp)
    {op: delete, sprite, anchor, stamp?}       takes one placing out
        (stamp takes off only the placing's own walls: a wall of the
        copy -- base_walls -- or a cell another placing's footprint
        stands on stays)
    {op: nudge, sprite, anchor, dx, dy}        one placing's pixel offset
    {op: exits, cells, side: auto|W|N|E|S|a|b} exit cells (auto: the edge's)
    {op: ring}                                 edge exits and a ring of
                                               entries, as the templates

WHAT A SAVE WRITES, and only where a byte changes (a save that changes
nothing writes nothing):

  data/locations/static/<id>.xml   the location in the static style
                                   (tools/lavaloc.py): what the edit did not
                                   touch keeps the bytes it was copied with
  data/locations/index.json        its row
  data/exits_sides.json            its rows (data/build_exits_sides.py row)
  data/placements.json             its rows
  data/passages.json               its doors, walk-ins and no_map rows
                                   (tools/jsonrows.py: every other byte kept)
  data/settlements_verified.json   its map cell, with the why
  data/settlements.json,           data/place_settlements.py rerun, when the
  data/settlements_report.md       map or a place's title, name, sides or
                                   war changed and the recount moved anything
  data/map_labels.json             the name over its cell, a row added
  data/map_cells.json              its square

Never data/terrain_verified.json, data/map_terrain.json, client/files or
res/. The owner's objects (client/objects) are written by the object calls
alone. A door into a place on the map is written with own_cell (the
player arrives on that place's cell). A list of another location's rows
(102's walk-ins) is rewritten in place: this location's rows where they
stood, the others' untouched.

One save at a time over a data/ folder, between processes too (SaveLock:
the page, a second editor, the command line); before it writes, every
table the plan was made from is read again, and one another writer
changed meanwhile is a 409 that names it, nothing written.

THE CHECKS. Every check and save runs, on the model:

  L1  references (data/location_art.json, client/objects), anchors and
      cells on the grid, zones = outzones (the encoder writes zones from
      the exits), exit sides by their edge, a free entry, inhabitants as
      rooms.placement_problems has them, doors and walk-ins that lead
      somewhere real, a way in and a way out, and for a map cell: in the
      world and off its rim, walkable, nobody's (no place, retired cell or
      camp patrol), not one of the owner's cuts (cut_cells: a square
      data/map_cells.json erases or keeps, a name data/map_labels.json
      hides), side exits onto walkable ground, and on the walk from
      the start or from the Nubian valley (data/test_borders.py pins the
      settlements stranded by the valley's wall);
  L2  a walk from the free entries to every exit side, door, war entry and
      inhabitant (the cell or one beside it), and on the location a walk-in
      leaves from, from its entries to the walk-in;
  L3  in a subprocess on the candidate data/ (a folder of links, the
      candidate files written into it; LAVA_LOC_OVERLAY, LAVA_PASSAGES,
      LAVA_PLACEMENTS point there): world.Location, rooms.placement_problems,
      events' and holdings' checks, travel.plan_exit for each side and door,
      travel.plan_walk_in for each walk-in, the start places; and, when a
      place's map-relevant attributes or the verified cells change,
      data/place_settlements.py on that state: it may change this
      location's cells and nothing else, and the settlements stranded by
      the valley's wall stay as many (tools/known_failures.txt). The
      recount takes about a minute; its result is kept by its inputs.

A new id is the first free from 1381 (world.FIRST_NEW_ID) below 8192,
against the files of the overlay and RES, data/locations/index.json and
origin/main's data/locations/static (git fetch first; LAVA_LOCATION_EDITOR_GIT=0
skips git, LAVA_LOCATION_EDITOR_FETCH=0 the fetch). 262 «Тотем» is closed
to the editor; the original's files are read and copied, never written.
"""
import argparse
import ast
import base64
import collections
import copy
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _default_res():
    for c in (os.path.join(os.path.expanduser("~"), "lava-cicd2", "ci-assets2", "res"),
              "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        if os.path.isdir(os.path.join(c, "locations", "static")):
            return c
    return ""


if not os.environ.get("LAVA_RES"):
    os.environ["LAVA_RES"] = _default_res()
if not os.environ.get("LAVA_ORIG_TEXTS"):
    _res = os.environ["LAVA_RES"]
    for _candidate in (os.path.join(os.path.dirname(_res), "texts.xml"),
                       os.path.join(_res, "xml", "texts.xml"),
                       "/mnt/c/Users/gmkrt/Downloads/texts.xml"):
        if _res and os.path.isfile(_candidate):
            os.environ["LAVA_ORIG_TEXTS"] = _candidate
            break

for _p in (HERE, os.path.join(ROOT, "data"), os.path.join(ROOT, "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import custom_objects as CO  # noqa: E402
import jsonrows  # noqa: E402
import lavaloc as L  # noqa: E402
import location_art as A  # noqa: E402
import swfgen  # noqa: E402
import travel  # noqa: E402
import world  # noqa: E402

PORT = int(os.environ.get("LAVA_LOCATION_EDITOR_PORT", "8096"))
UI = os.path.join(HERE, "location_editor_ui", "static")
CACHE = os.environ.get("LAVA_LOCATION_EDITOR_CACHE") or os.path.join(
    os.path.expanduser("~"), ".cache", "lava-location-editor")

# outzones side code <-> the side data/exits_sides.json and travel name
CODE = {"W": "1", "N": "2", "E": "3", "S": "4", "a": "a", "b": "b"}
EDGE_SIDES = ("W", "N", "E", "S")
DOOR_SIDES = ("a", "b")
# How deep from its edge an exit cell is still on it: the original's side
# exits lie at x <= 1, y <= 2 (three rows), x >= W-2 and y >= H-3 (and on
# the extra row y == H) but for a few hundred cells of funnels further in,
# which a warning names.
EDGE_BAND = {"W": 1, "N": 2, "E": 1, "S": 2}
WARN_BAND = {"W": 1, "N": 3, "E": 1, "S": 3}
OBSTACLE_CODES = {
    "f": "стена",
    "1": "стойка: в тирах через неё стреляют (world.SHOOT_OVER)",
    "3": "край, обрыв (код 3 оригинала)",
    "7": "дерево, машина (код 7 оригинала)",
}
MAX_TITLE = 80
FOOT_WINDOW = (range(-6, 7), range(-12, 4))     # (dx, dy) looked at around an anchor
FOOT_SHARE, FOOT_MIN = 0.8, 3                   # a footprint cell: in 80% of 3 placings or more
TODAY = None                                    # a test fixes the date


class Refused(Exception):
    """A request the editor will not carry out; the text says why (400)."""


class Conflict(Exception):
    """What was read has changed on disk since, or is in use (409)."""

    def __init__(self, text, extra=None):
        Exception.__init__(self, text)
        self.extra = extra or {}


class NotFound(Exception):
    """No such location (404)."""


def today():
    return TODAY or datetime.date.today().isoformat()


# --- the refusals of the build, in the owner's words ----------------------------------------
# tools/swfgen.py and tools/custom_objects.py say why in English (the
# release build's log); the page shows the owner the same reasons in
# Russian. A reason with no row here goes through as it is.
_RU = [
    (r"not a PNG", "это не PNG"),
    (r"not a JPEG", "это не JPEG"),
    (r"neither a PNG nor a JPEG", "это не PNG и не JPEG"),
    (r"(PNG|JPEG|picture) (\d+)x(\d+): each side must be 1\.\.(\d+) pixels",
     r"\1 \2x\3: каждая сторона — от 1 до \4 точек"),
    (r"PNG: interlaced; save it without interlacing",
     "PNG с чересстрочностью (interlaced): сохраните его без неё"),
    (r"PNG: colour type (\d+) with bit depth (\d+)", r"PNG: такого цвета игра не знает (тип \1, глубина \2)"),
    (r"PNG: (?:cut short before IEND|chunk .* cut short|image data cut short)", "PNG: файл обрезан"),
    (r"PNG: no IHDR first", "PNG: файл испорчен (нет IHDR в начале)"),
    (r"PNG: bad CRC in chunk (.*)", r"PNG: файл испорчен (не сходится контрольная сумма блока \1)"),
    (r"PNG: image data does not inflate.*", "PNG: данные картинки не распаковываются, файл испорчен"),
    (r"PNG: unknown row filter (\d+)", r"PNG: файл испорчен (фильтр строки \1)"),
    (r"PNG: palette picture without a palette", "PNG: у картинки с палитрой нет палитры"),
    (r"PNG: palette index (\d+) past the palette", r"PNG: цвет \1 за краем палитры"),
    (r"JPEG: no marker at byte (\d+)", r"JPEG: файл испорчен (байт \1)"),
    (r"JPEG: no frame header", "JPEG: файл испорчен (нет заголовка кадра)"),
    (r"JPEG: (\d+) colour components \(CMYK\?\); save it as RGB", r"JPEG в CMYK (\1 канала): сохраните его в RGB"),
    (r"JPEG: not baseline .*",
     "JPEG прогрессивный (progressive) или другой необычный: сохраните его как обычный (baseline) JPEG или как PNG"),
    (r"JPEG: EXIF Orientation (\d+) .*",
     r"JPEG повёрнут записью в EXIF (Orientation \1): браузер его поворачивает, игра показывает так, как он "
     r"записан. Поверните картинку и сохраните без поворота в EXIF"),
    (r"every picture of an animation must be the same size: (.*)",
     r"все картинки анимации должны быть одного размера; здесь размеры \1"),
    (r"fps (.*): a whole number 1\.\.(\d+) .*", r"кадров в секунду — целое число от 1 до \2"),
    (r"an animation of (\d+) pictures needs fps, 1\.\.(\d+)", r"анимации из \1 картинок нужна скорость: 1..\2 в секунду"),
    (r"anchor (-?\d+),(-?\d+) is outside the (\d+)x(\d+) picture", r"ноги \1,\2 за краем картинки \3x\4"),
    (r"(\d+) bytes, more than (\d+); big art goes into the store and client/extra\.txt",
     r"\1 байт, больше \2: крупное — в хранилище и client/extra.txt"),
    (r"(\d+) bytes of pictures, more than (\d+); big art goes into the store and client/extra\.txt",
     r"\1 байт картинок, больше \2: крупное — в хранилище и client/extra.txt"),
    (r"(\d+) pixels of PNG pictures, more than (\d+): .*",
     r"\1 точек в картинках PNG, больше \2: сборка релиза распаковывает каждую точку, и столько она "
     r"не потянет. Уменьшите картинки, сократите кадры или сохраните непрозрачные в JPEG"),
    (r"title is text of 1\.\.(\d+) characters on one line", r"название — от 1 до \1 знаков в одну строку"),
    (r"front needs at least one cell.*", "линии глубины нужна хотя бы одна клетка"),
    (r"anchor is \[x, y\].*", "ноги — точка картинки [x, y]"),
    (r"(front|footprint) names cell (.*) twice", r"клетка \2 дважды"),
    (r"(front|footprint) cell (.*): \[dx, dy\], each -128\.\.127", r"клетка \2: [dx, dy], каждое от -128 до 127"),
    (r"a background is one picture.*", "фон — одна картинка: клиент рисует только первый кадр"),
    (r"a background has no (\w+): it is tiled from the corner", r"у фона нет \1: он кладётся плиткой от угла"),
    (r"the game already has (.*); pick another id", r"в игре уже есть \1: нужен другой id"),
]
_RU = [(re.compile(p), r) for p, r in _RU]


def ru_refusal(text):
    """A refusal of swfgen or custom_objects in Russian: its prefix (the
    object, the file) kept, the reason after it translated."""
    text = str(text)
    head, rest = "", text
    m = re.match(r"((?:client/objects/[^:]+|c_[a-z0-9_]+|client/objects|картинка \d+): )(.*)\Z", text, re.S)
    if m:
        head, rest = m.group(1), m.group(2)
    for rx, ru in _RU:
        m = rx.fullmatch(rest)
        if m:
            return head + m.expand(ru)
    return text


def art_why_ru(why):
    """location_art.art_problems' why in Russian."""
    for rx, ru in ((r"no (\S+) in the release", r"в релизе нет \1"),
                   (r"not exported by (\S+): the client draws the library's whole picture there",
                    r"такой картинки в библиотеке \1 нет: клиент рисует там всю картинку библиотеки"),
                   (r"not exported by (\S+): nothing is drawn", r"такой картинки в библиотеке \1 нет: ничего не рисуется"),
                   (r"no (\S+): nothing is drawn", r"нет файла \1: ничего не рисуется"),
                   (r"no (\S+): no music", r"нет файла \1: музыки не будет"),
                   (r"no (\S+)", r"нет файла \1")):
        m = re.fullmatch(rx, str(why))
        if m:
            return m.expand(ru)
    return why


# --- where things are ---------------------------------------------------------------------

class Paths:
    """The data/ folder and the objects folder the editor reads and writes."""

    def __init__(self, data=None, objects=None):
        self.data = os.path.abspath(data or os.path.join(ROOT, "data"))
        self.objects = os.path.abspath(objects or os.path.join(ROOT, "client", "objects"))

    def d(self, *parts):
        return os.path.join(self.data, *parts)

    @property
    def overlay(self):
        return self.d("locations")

    def xml(self, loc_id):
        return self.d("locations", "static", "%d.xml" % int(loc_id))

    index = property(lambda s: s.d("locations", "index.json"))
    placements = property(lambda s: s.d("placements.json"))
    passages = property(lambda s: s.d("passages.json"))
    labels = property(lambda s: s.d("map_labels.json"))
    cells = property(lambda s: s.d("map_cells.json"))
    verified = property(lambda s: s.d("settlements_verified.json"))
    settlements = property(lambda s: s.d("settlements.json"))
    report = property(lambda s: s.d("settlements_report.md"))
    exits = property(lambda s: s.d("exits_sides.json"))
    retired = property(lambda s: s.d("retired.json"))

    def rel(self, path):
        """A path as the repository names it (data/..., client/objects/...)."""
        for base, name in ((self.data, "data"), (self.objects, "client/objects")):
            if path == base or path.startswith(base + os.sep):
                return name + path[len(base):].replace(os.sep, "/")
        return path


P = Paths()
_LOCK = threading.RLock()          # one save or object write at a time
_MEMO = {}
_MEMO_LOCK = threading.Lock()


def configure(data=None, objects=None):
    """Point the editor at a data/ folder and an objects folder (a suite's
    copy; the repository's by default). The server modules read our
    locations from the same folder (world.OVERLAY)."""
    global P
    P = Paths(data, objects)
    world.OVERLAY = P.overlay
    world._CACHE.clear()
    # what is read from data/ itself; the original's files, the names and
    # the map's walks stay
    forget("locations", "exits_json")
    # the pictures: the objects of this folder (Art reads them, not the
    # repository's client/objects)
    _ART[0] = None


def memo(name, fn):
    with _MEMO_LOCK:
        if name in _MEMO:
            return _MEMO[name]
    value = fn()
    with _MEMO_LOCK:
        _MEMO.setdefault(name, value)
        return _MEMO[name]


def forget(*names):
    with _MEMO_LOCK:
        for n in names:
            _MEMO.pop(n, None)


# --- files ------------------------------------------------------------------------------------

def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except (FileNotFoundError, NotADirectoryError):
        return None


def read_text(path):
    b = read_bytes(path)
    return None if b is None else b.decode("utf-8")


def sha(b):
    return None if b is None else hashlib.sha256(b).hexdigest()


def write_atomic(path, data):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, ".%s.%d.%d.tmp" % (os.path.basename(path), os.getpid(), threading.get_ident()))
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def load_json(path, default=None):
    t = read_text(path)
    if t is None:
        return default
    return json.loads(t)


def dumps1(doc):
    """The form data/placements.json, settlements_verified.json and
    locations/index.json are written in: json.dumps(indent=1), UTF-8 as it
    is, a newline at the end."""
    return json.dumps(doc, ensure_ascii=False, indent=1) + "\n"


def set_rows(text, path, value):
    """text with the member at path set to value (None: taken out), every
    other byte kept. A file written as dumps1 writes it is written so again;
    any other goes through tools/jsonrows.py."""
    doc = json.loads(text)
    if jsonrows.get_key(doc, path, _MISSING) == (_MISSING if value is None else value):
        return text
    if dumps1(doc) == text:
        node = doc
        for k in path[:-1]:
            node = node.setdefault(k, {})
        if value is None:
            node.pop(path[-1], None)
        else:
            node[path[-1]] = value
        return dumps1(doc)
    if value is None:
        return jsonrows.delete_key(text, path)
    return jsonrows.set_key(text, path, value)


_MISSING = object()


# --- the reference data --------------------------------------------------------------------

def art_index():
    return memo("art_index", A.load_index)


def tracks():
    return list(art_index().get("tracks") or [])


def libraries():
    return {k.lower(): k for k in art_index()["libraries"]}


def base_ids():
    """The original's static ids, as client/base.txt lists them."""
    def read():
        try:
            with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
                return frozenset(int(m.group(1)) for m in re.finditer(
                    r"\tlocations/static/(\d+)\.xml\r?$", fh.read(), re.M))
        except OSError:
            return frozenset(range(world.FIRST_NEW_ID))
    return memo("base_ids", read)


def res_original():
    """Whether RES is the original's slice: its 262.xml is the one
    client/base.txt lists (a launcher's res has the release's «Тотем»)."""
    def read():
        try:
            with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
                m = re.search(r"^([0-9a-f]{64})\t\d+\tlocations/static/262\.xml\r?$", fh.read(), re.M)
            raw = read_bytes(os.path.join(world.RES, "locations", "static", "262.xml"))
            return bool(m and raw is not None and sha(raw) == m.group(1))
        except OSError:
            return False
    return memo("res_original", read)


def mob_types():
    return memo("mob_types", world.mob_types)


def _names():
    """server/names.py (it loads half the server: the first call takes some
    seconds; the server starts it in the background)."""
    def load():
        import names
        return names
    return memo("names", load)


def creatures():
    """[{type, name, sub, level, root, role, known, retired, internal}] of
    every creature the client has a record of."""
    def build():
        names = _names()
        import mobs
        out = []
        for t, (root, internal, _art) in sorted(mob_types().items()):
            n, _, sub = names.text(t).replace("<BR>", "<br>").replace("<Br>", "<br>").partition("<br>")
            info = mobs.TYPES.get(str(t)) or {}
            out.append({"type": t, "name": n.strip(), "sub": sub.replace("<br>", " ").strip(),
                        "level": int(info.get("level") or 0), "root": int(root),
                        "role": world.creature_role(t) or "", "known": names.known(t),
                        "retired": world.retired_creature(t), "internal": internal})
        return out
    return memo("creatures", build)


def creature_name(t):
    try:
        n = _names().text(int(t))
    except Exception:          # noqa: BLE001 -- a name is a nicety here
        return "#%s" % t
    return re.split(r"<[Bb][Rr]\s*/?>", n)[0].strip()


# --- the tables -------------------------------------------------------------------------------

def index_doc():
    return load_json(P.index, {"locations": {}}) or {"locations": {}}


def placements_doc():
    return load_json(P.placements, {"locations": {}}) or {"locations": {}}


def passages_doc():
    return load_json(P.passages, {}) or {}


def labels_doc():
    return load_json(P.labels, {"labels": []}) or {"labels": []}


def cells_doc():
    return load_json(P.cells, {}) or {}


def verified_doc():
    return load_json(P.verified, {"cells": {}, "why": {}}) or {"cells": {}, "why": {}}


def settlements_table():
    """{(x, y): id} of data/settlements.json."""
    doc = load_json(P.settlements, {}) or {}
    return {_xy(k): int(v) for k, v in (doc.get("cells") or {}).items()}


def retired_cells():
    doc = load_json(P.retired, {}) or {}
    return {_xy(k): int(v) for k, v in (doc.get("cells") or {}).items() if not str(k).startswith("_")}


def _ids(section):
    """The location keys of a passages-like section, numbers only (a
    section may carry a "_" note)."""
    return [k for k in (section or {}) if str(k).isdigit()]


def patrol_cells():
    """{(x, y): camp} of the open-desert cells a camp's patrol stands on
    (data/placements.json rows with 'patrol', keyed by the packed cell)."""
    out = {}
    for k, rows in (placements_doc().get("locations") or {}).items():
        try:
            key = int(k)
        except ValueError:
            continue
        if key < world.NEW_ID_LIMIT:
            continue
        for r in rows or ():
            if isinstance(r, dict) and r.get("patrol") is not None:
                out[world.unpack(key)] = int(r["patrol"])
    return out


def _xy(key):
    x, y = str(key).split(",")
    return int(x), int(y)


def _key(x, y):
    return "%d,%d" % (int(x), int(y))


def ours_ids():
    return world.overlay_ids(P.overlay)


def is_ours(loc_id):
    return os.path.isfile(P.xml(loc_id))


def original_path(loc_id):
    p = os.path.join(world.RES, "locations", "static", "%d.xml" % int(loc_id))
    return p if os.path.isfile(p) else None


def file_of(loc_id):
    """The file the server reads for a static id (ours first), or None."""
    return P.xml(loc_id) if is_ours(loc_id) else original_path(loc_id)


def exits_of(loc_id):
    """{(x, y): side} of a location's exits, read from its file."""
    path = file_of(loc_id)
    if path is None:
        return {}
    m = L.load(path)
    return {(x, y): L.SIDES.get(e, e) for x, y, e in m["lists"]["outzones"]}


def location_grid(loc_id):
    """(width, height, walls {(x, y)}, entries [(x, y)], exits {(x, y): side})
    of a location's file, or None."""
    path = file_of(loc_id)
    if path is None:
        return None
    m = L.load(path)
    return (m["width"], m["height"], L.cells(m, "obstacles"),
            [(x, y) for x, y, _e in m["lists"]["inzones"]],
            {(x, y): L.SIDES.get(e, e) for x, y, e in m["lists"]["outzones"]})


# --- the model ---------------------------------------------------------------------------------

def to_model(m):
    """A tools/lavaloc.py model as the editor's JSON (no rows of the tables)."""
    lists = m["lists"]

    def typ(e):
        try:
            return int(e, 16)
        except ValueError:
            return 0
    return {
        "attrs": dict(m["attrs"]),
        "width": int(m["width"]), "height": int(m["height"]),
        "background": dict(m["background"]) if m.get("background") is not None else None,
        "sprites": [{"id": s["id"], "type": s.get("type"), "dx": s.get("dx", 0), "dy": s.get("dy", 0),
                     "front": s.get("front"), "anchors": [[int(a[0]), int(a[1])] for a in s["anchors"]]}
                    for s in m["sprites"]],
        "decals": [{"id": d["id"], "type": d.get("type"), "dx": d.get("dx", 0), "dy": d.get("dy", 0)}
                   for d in m["bgdecorations"]],
        "walls": [[x, y, e] for x, y, e in lists["obstacles"]],
        "exits": [[x, y, L.SIDES.get(e, e)] for x, y, e in lists["outzones"]],
        "entries": [[x, y] for x, y, _e in lists["inzones"]],
        "war_entries": [[x, y] for x, y, _e in lists["warinzones"]],
        "spawns": [[x, y, typ(e)] for x, y, e in lists["mobs"]],
        "raw": {"mobs": [[x, y, e] for x, y, e in lists["mobs"]],
                "tails": dict(m.get("tails") or {}), "serverdata": m.get("serverdata")},
    }


def to_lavaloc(model):
    """The editor's model as a tools/lavaloc.py model; zones are left for
    the encoder to write from the exits."""
    def cells(rows, extra=None):
        out = []
        for r in rows or ():
            x, y = int(r[0]), int(r[1])
            out.append((x, y, extra(r) if extra else ""))
        return out
    raw = model.get("raw") or {}
    bg = model.get("background")
    return {
        "attrs": {k: "" if v is None else str(v) for k, v in (model.get("attrs") or {}).items()},
        "width": int(model["width"]), "height": int(model["height"]),
        "background": {k: "" if v is None else str(v) for k, v in bg.items()} if bg is not None else None,
        "sprites": [{"id": str(s["id"]), "type": s.get("type"), "dx": L.num(s.get("dx")),
                     "dy": L.num(s.get("dy")), "front": s.get("front"),
                     "anchors": [(int(a[0]), int(a[1])) for a in s.get("anchors") or ()]}
                    for s in model.get("sprites") or ()],
        "bgdecorations": [{"id": str(d["id"]), "type": d.get("type"), "dx": L.num(d.get("dx")),
                           "dy": L.num(d.get("dy"))} for d in model.get("decals") or ()],
        "lists": {
            "obstacles": cells(model.get("walls"), lambda r: str(r[2]) if len(r) > 2 else "f"),
            "zones": [],
            "warinzones": cells(model.get("war_entries")),
            "inzones": cells(model.get("entries")),
            "outzones": cells(model.get("exits"), lambda r: CODE.get(r[2], str(r[2]))),
            "mobs": [(int(x), int(y), str(e)) for x, y, e in raw.get("mobs") or ()],
        },
        "tails": dict(raw.get("tails") or {}),
        # a model that came back without its raw part still ends the static way
        "serverdata": raw.get("serverdata", "\r\n"),
    }


def base_bytes(model):
    """The file a model's bytes are written against: its own (ours), the
    original it is (read only), or the one it was copied from; None for a
    place made empty."""
    loc_id = int(model["id"])
    st = model.get("state")
    if st in ("ours", "original"):
        p = file_of(loc_id)
        if p is not None:
            return read_bytes(p)
    src = model.get("from")
    if src is not None:
        p = world.static_path(int(src))
        if p is not None:
            return read_bytes(p)
    return None


def model_bytes(model):
    """The location file of a model in the static style: no BOM, the
    declaration, one line; what did not change keeps its base's bytes."""
    lm = to_lavaloc(model)
    raw = base_bytes(model)
    if raw is None:
        return L.write_static(lm)
    base = L.parse_raw(raw)
    doc = L.encode(lm, base=base, derive_zones=True)
    doc.bom = False
    if not doc.decl:
        doc.decl = L.DECL
    return L.write_raw(doc)


def location_state(loc_id):
    """Everything of the tables that belongs to one location, as on disk
    now: what a save compares against what the page read (etag)."""
    loc_id = int(loc_id)
    key = str(loc_id)
    pas = passages_doc()
    walk = []
    section = pas.get("walk_in") or {}
    for src in sorted(_ids(section), key=int):
        # by content, not by place in the list: another location's rows
        # moving round this one's leave its etag as it was
        for r in section[src] or ():
            if isinstance(r, dict) and r.get("target_loc_id") == loc_id:
                walk.append([src, r])
    ver = verified_doc()
    mine = sorted(k for k, v in (ver.get("cells") or {}).items() if v == loc_id)
    labels = [r for r in labels_doc().get("labels", ())
              if isinstance(r, dict) and r.get("add") and _key(r.get("x", -1), r.get("y", -1)) in mine]
    paint = {k: v for k, v in (cells_doc().get("paint") or {}).items() if k in mine}
    return {"xml": sha(read_bytes(P.xml(loc_id))),
            "index": (index_doc().get("locations") or {}).get(key),
            "placements": (placements_doc().get("locations") or {}).get(key),
            "doors": (pas.get("doors") or {}).get(key),
            "walk_in": walk,
            "no_map": (pas.get("no_map") or {}).get(key),
            "verified": [mine, {k: (ver.get("why") or {}).get(k) for k in mine}],
            "labels": labels, "paint": paint}


def etag_of(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


def rows_of(loc_id):
    """The table rows of a location in the model's shape."""
    loc_id = int(loc_id)
    key = str(loc_id)
    out = {}
    out["inhabitants"] = [dict(r) for r in (placements_doc().get("locations") or {}).get(key) or ()
                          if isinstance(r, dict)]
    pas = passages_doc()
    doors = {}
    for side, rec in ((pas.get("doors") or {}).get(key) or {}).items():
        if side in DOOR_SIDES and isinstance(rec, dict) and rec.get("target_loc_id") is not None:
            d = {"target": rec.get("target_loc_id"), "why": rec.get("why", "")}
            for k in ("confidence", "source", "own_cell"):
                if k in rec:
                    d[k] = rec[k]
            doors[side] = d
    out["doors"] = doors
    walk = []
    section = pas.get("walk_in") or {}
    for src in sorted(_ids(section), key=int):
        for r in section[src] or ():
            if isinstance(r, dict) and r.get("target_loc_id") == loc_id:
                walk.append({"from": int(src), "cells": [list(c) for c in r.get("cells") or ()],
                             "why": r.get("why", "")})
    out["walk_ins"] = walk
    nm = (pas.get("no_map") or {}).get(key)
    out["no_map"] = dict(nm) if isinstance(nm, dict) else None
    ver = verified_doc()
    mine = sorted(k for k, v in (ver.get("cells") or {}).items() if v == loc_id)
    if mine:
        k = mine[0]
        x, y = _xy(k)
        label = next((r.get("text") for r in labels_doc().get("labels", ())
                      if isinstance(r, dict) and r.get("add") and (r.get("x"), r.get("y")) == (x, y)), "")
        paint = (cells_doc().get("paint") or {}).get(k) or {}
        out["map"] = {"cell": [x, y], "label": label or "", "square": paint.get("colour"),
                      "why": (ver.get("why") or {}).get(k, "")}
    else:
        out["map"] = None
    idx = (index_doc().get("locations") or {}).get(key)
    out["index"] = dict(idx) if isinstance(idx, dict) else None
    return out


def load_model(loc_id):
    """GET /api/location/<id>: the model of a location as on disk."""
    loc_id = int(loc_id)
    if is_ours(loc_id):
        state, path = "ours", P.xml(loc_id)
    else:
        path = original_path(loc_id)
        state = "original"
        if path is None:
            raise NotFound("нет локации %d" % loc_id)
    model = {"id": loc_id, "state": state}
    model.update(to_model(L.load(path)))
    model.update(rows_of(loc_id))
    idx = model.get("index") or {}
    model["from"] = idx.get("from") if state == "ours" else None
    model["etag"] = etag_of(location_state(loc_id))
    model["closed"] = loc_id == 262
    return model


# --- names ------------------------------------------------------------------------------------

_TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                     ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "i", "k", "l", "m", "n", "o",
                      "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e",
                      "yu", "ya"]))


def slug_words(text):
    """Latin words of a title: «Старый колодец» -> [stariy, kolodets]."""
    out = []
    for w in re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", text or ""):
        if not w:
            continue
        s = "".join(_TRANSLIT.get(ch, ch) for ch in w.lower())
        s = re.sub(r"[^a-z0-9]", "", s)
        if s:
            out.append(s)
    return out


def fn_for(title, loc_id):
    """ED_<Words> of a title, at most 40 characters; ED_<id> without one."""
    words = [w[:1].upper() + w[1:] for w in slug_words(title)]
    fn = "ED_" + "_".join(words)
    return fn[:40].rstrip("_") if words else "ED_%d" % loc_id


# --- the original's placings: what a picture is put down with -------------------------------

def _usage_key():
    """What the original's location files are: the shas client/base.txt
    lists for them (RES is meant to be that slice)."""
    try:
        with open(os.path.join(ROOT, "client", "base.txt"), encoding="utf-8") as fh:
            lines = [ln for ln in fh if "\tlocations/static/" in ln]
    except OSError:
        lines = []
    return hashlib.sha256(("u1" + world.RES + "".join(lines)).encode()).hexdigest()[:20]


def _foot_offsets(ax, ay, walls):
    """{(dx, dy): code} of the walls around an anchor, as offsets in the
    even-row convention (tools/lavaloc.py offsets_cells, inlined: it runs
    for every placing of the original)."""
    out = {}
    odd = ay % 2
    for dy in FOOT_WINDOW[1]:
        shift = 1 if odd and dy % 2 else 0
        y = ay + dy
        for dx in FOOT_WINDOW[0]:
            c = walls.get((ax + dx + shift, y))
            if c is not None:
                out[(dx, dy)] = c
    return out


def build_usage():
    """{"lib:<id>" | "ext:<id>": [{dx, dy, front, n, footprint}]} over the
    original's files, the most used variant first: how each picture is put
    down, and the walls its placings have in common (in FOOT_SHARE of them,
    FOOT_MIN placings or more), as [dx, dy, code]."""
    variants = collections.defaultdict(collections.Counter)
    feet = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for loc_id in sorted(base_ids()):
        path = original_path(loc_id)
        if path is None:
            continue
        try:
            m = L.load(path)
        except (ValueError, UnicodeDecodeError):
            continue
        walls = {(x, y): e for x, y, e in m["lists"]["obstacles"]}
        for s in m["sprites"]:
            kind = "ext" if s.get("type") == "ext" else "lib"
            var = (L.num(s.get("dx")), L.num(s.get("dy")), s.get("front") or "")
            key = "%s:%s" % (kind, s["id"])
            for ax, ay in s["anchors"]:
                if ay >= m["height"]:
                    continue
                variants[key][var] += 1
                for off, code in _foot_offsets(ax, ay, walls).items():
                    feet[(key, var)][off][code] += 1
    out = {}
    for key, counter in variants.items():
        rows = []
        for var, n in counter.most_common():
            foot = []
            if n >= FOOT_MIN:
                for off, codes in sorted(feet[(key, var)].items()):
                    if sum(codes.values()) >= FOOT_SHARE * n:
                        foot.append([off[0], off[1], codes.most_common(1)[0][0]])
            rows.append({"dx": var[0], "dy": var[1], "front": var[2], "n": n, "footprint": foot})
        out[key] = rows
    return out


def usage(wait=True):
    """build_usage, kept on disk by _usage_key; None while it is being built
    and wait is False."""
    with _MEMO_LOCK:
        if "usage" in _MEMO:
            return _MEMO["usage"]
    path = os.path.join(CACHE, "usage-%s.json" % _usage_key())
    try:
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
        with _MEMO_LOCK:
            _MEMO["usage"] = got
        return got
    except (OSError, ValueError):
        pass
    if not wait:
        _background("usage", lambda: usage(True))
        return None
    got = build_usage()
    try:
        os.makedirs(CACHE, exist_ok=True)
        tmp = path + ".%d.tmp" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(got, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError:
        pass
    with _MEMO_LOCK:
        _MEMO["usage"] = got
    return got


_BG = {}
_BG_LOCK = threading.Lock()


def _background(name, fn):
    """Run fn in a thread of its own, once at a time per name; whether it
    runs now."""
    with _BG_LOCK:
        t = _BG.get(name)
        if t is not None and t.is_alive():
            return True

        def run():
            try:
                fn()
            except Exception:              # noqa: BLE001 -- a background job only logs
                traceback.print_exc()
        t = _BG[name] = threading.Thread(target=run, daemon=True, name="loc-" + name)
        t.start()
        return True


# --- the art --------------------------------------------------------------------------------

_ART = [None]


def art():
    if _ART[0] is None:
        _ART[0] = A.Art(objects=P.objects)
    return _ART[0]


def _ART_RESET():
    """After an object changes: the release list (and its objects) is read anew."""
    a = _ART[0]
    if a is not None:
        a._release = None
        a._lower = None


def have_pictures():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def objects_raw():
    try:
        return CO.load_raw(P.objects)
    except CO.Refused:
        return {}


def objects_checked():
    """{id: checked entry} of the objects whose rows check."""
    out = {}
    for oid, e in objects_raw().items():
        try:
            out[oid] = CO.check_entry(oid, e)
        except CO.Refused:
            continue
    return out


def local_ext():
    """Ext sprite and background ids beyond the original: client/files and
    the owner's objects of this editor's objects folder."""
    sprites, bgs = A.local_ext(ROOT, objects=P.objects)
    for oid, e in objects_checked().items():
        (bgs if e["kind"] == "background" else sprites).add(oid)
    return sprites, bgs


def sprite_default(kind, sid, library=None):
    """{dx, dy, front, footprint: [[dx, dy, code]]} a picture is put down
    with: an object's from its row, a picture of the original's from its
    most used placing, else its bottom middle on the cell."""
    if kind == "object":
        e = objects_checked().get(sid)
        if e is None:
            raise Refused("нет объекта %s в client/objects/manifest.json" % sid)
        if e["kind"] != "sprite":
            raise Refused("%s — фон: он ставится как фон локации, не на клетку" % sid)
        ax, ay = e["anchor"]
        return {"dx": -ax, "dy": -ay, "front": CO.encode_cells(e["front"]),
                "footprint": [[dx, dy, CO.OBSTACLE] for dx, dy in e["footprint"]], "type": "ext"}
    u = usage(wait=False) or {}
    rows = u.get("%s:%s" % (kind, sid)) or []
    if rows:
        # the front as the original writes it (an empty one too), so that
        # sprite_footprint finds this placing's variant again
        r = rows[0]
        return {"dx": r["dx"], "dy": r["dy"], "front": r["front"],
                "footprint": r["footprint"], "type": kind}
    w = h = 0
    ox = oy = 0
    try:
        if have_pictures():
            if kind == "lib" and library:
                man = art().library(library)
                pic = (man or {}).get("symbols", {}).get(sid)
            else:
                man = art().sprite(sid)
                pic = (man or {}).get("stage")
            if pic and not pic.get("empty"):
                w, h, ox, oy = pic["w"], pic["h"], pic.get("ox", 0), pic.get("oy", 0)
    except Exception:                      # noqa: BLE001 -- a default is a guess anyway
        pass
    if kind == "lib":
        ox = oy = 0
    half = max(0, (w // L.CELL_W) // 2)
    front = L.offsets_front([(dx, 0) for dx in range(-half, half + 1)]) if w else "8080"
    return {"dx": -(ox + w // 2), "dy": -(oy + h) + 5 if h else 0, "front": front,
            "footprint": [], "type": kind}


def palette(library):
    """What a location of this library can place (GET /api/palette)."""
    ix = art_index()
    libs = libraries()
    name = libs.get((library or "").lower(), library)
    items = []
    warming = False
    if have_pictures():
        try:
            for it in art().palette(name, ext=True):
                if it.get("origin") == "object":
                    continue
                items.append(it)
            with _MEMO_LOCK:
                done = _MEMO.get("ext_warm_done")
            warming = False if done else _background("palette-ext", _warm_ext)
        except Exception:                  # noqa: BLE001 -- fall back on the index
            traceback.print_exc()
            items = []
    if not items:
        lib = ix["libraries"].get(name) or {}
        items = [{"name": n, "type": "lib"} for n in lib.get("exports") or ()]
        items += [{"name": s, "type": "ext"} for s in ix.get("sprites") or ()]
    out = []
    u = usage(wait=False) or {}
    for it in items:
        row = {"name": it["name"], "type": it["type"], "w": it.get("w"), "h": it.get("h"),
               "ox": it.get("ox"), "oy": it.get("oy"), "frames": it.get("frames", 1)}
        if it.get("thumb") and it.get("sha"):
            row["thumb"] = "/art/%s/%s" % (it["sha"], it["thumb"])
            row["picture"] = "/art/%s/%s" % (it["sha"], it["file"])
        v = (u.get("%s:%s" % (it["type"], it["name"])) or [None])[0]
        if v:
            row["default"] = {"dx": v["dx"], "dy": v["dy"], "front": v["front"],
                              "footprint": v["footprint"], "uses": v["n"]}
        out.append(row)
    for oid, e in sorted(objects_checked().items()):
        if e["kind"] != "sprite":
            continue
        row = {"name": oid, "type": "ext", "origin": "object", "title": e["title"],
               "frames": len(e["frames"]), "fps": e["fps"],
               "thumb": "/api/object/%s/%s" % (oid, e["frames"][0]),
               "picture": "/api/object/%s/%s" % (oid, e["frames"][0])}
        d = sprite_default("object", oid)
        row["default"] = {"dx": d["dx"], "dy": d["dy"], "front": d["front"], "footprint": d["footprint"]}
        out.append(row)
    return {"library": name, "items": out, "warming": warming}


def _warm_ext():
    """Every ext sprite of the release into the art cache, for the palette's
    thumbnails (about a minute the first time, then read from the cache)."""
    a = art()
    for p in sorted(a.release):
        if p.startswith(A.SPRITES) and p.endswith(".swf") and a.release[p].origin != "object":
            try:
                a.ensure(p)
            except Exception:              # noqa: BLE001 -- one bad file is one missing thumb
                continue
    with _MEMO_LOCK:
        _MEMO["ext_warm_done"] = True


def render_png(model, layers="art", scale=1.0, order="reverse"):
    """(PNG bytes, report) of a model drawn as the client draws it, its
    inhabitants among the sprites."""
    if not have_pictures():
        raise Refused("картинки рисует Pillow с numpy: запустите редактор из ~/venvs/lavagd")
    if not 0.05 <= float(scale) <= 2:
        raise Refused("scale: 0.05..2")
    lm = to_lavaloc(model)
    mobs = []
    for r in model.get("inhabitants") or ():
        try:
            mobs.append((int(r["cell"][0]), int(r["cell"][1]), int(r["type"])))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    try:
        img, rep = A.render(lm, art(), layers, scale=float(scale), order=order, mobs=mobs)
    except ValueError as exc:
        raise Refused(str(exc))
    return A.png_bytes(img), rep


# --- a new place -------------------------------------------------------------------------------

GIT = {"ok": None, "why": "ещё не спрашивали"}     # what origin_main_ids last found out


def wsl_path(path):
    """C:/Users/... (or C:\\Users\\...) as WSL reaches it, /mnt/c/Users/...;
    any other path as it is."""
    w = re.match(r"([A-Za-z]):[\\/](.*)\Z", path)
    if w and os.name != "nt":
        return "/mnt/%s/%s" % (w.group(1).lower(), w.group(2).replace("\\", "/"))
    return path


def git_env(root=ROOT):
    """The environment git runs in for a checkout. A worktree made by git
    for Windows names its git folder C:/...: WSL's git cannot open that and
    says "not a git repository", so GIT_DIR points at it through /mnt/c."""
    env = dict(os.environ)
    # the fetch asks nobody for anything: a key that wants a passphrase is a
    # fetch that fails at once, the ids then as origin/main last had them
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    dotgit = os.path.join(root, ".git")
    if os.path.isfile(dotgit):
        m = re.match(r"gitdir:\s*(.+?)\s*\Z", read_text(dotgit) or "")
        if m and wsl_path(m.group(1)) != m.group(1):
            g = wsl_path(m.group(1))
            if os.path.isdir(g):
                env.update(GIT_DIR=g, GIT_WORK_TREE=root)
    return env


def origin_main_ids():
    """The ids origin/main has under data/locations/static (after a fetch);
    empty when git cannot say (no git, no origin/main), which GIT keeps
    and /api/info and /api/new tell the owner."""
    if os.environ.get("LAVA_LOCATION_EDITOR_GIT", "1") == "0":
        GIT.update(ok=None, why="git выключен (LAVA_LOCATION_EDITOR_GIT=0)")
        return set()
    env = git_env()
    try:
        if os.environ.get("LAVA_LOCATION_EDITOR_FETCH", "1") != "0":
            subprocess.run(["git", "-C", ROOT, "fetch", "--quiet", "origin", "main"],
                           capture_output=True, timeout=30, env=env)
        p = subprocess.run(["git", "-C", ROOT, "ls-tree", "--name-only", "origin/main",
                            "data/locations/static/"], capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        GIT.update(ok=False, why="git не запустился: %s" % exc)
        return set()
    if p.returncode != 0:
        GIT.update(ok=False, why="git не прочёл origin/main: %s" % ((p.stderr or "").strip()[-300:] or p.returncode))
        return set()
    GIT.update(ok=True, why="")
    out = set()
    for line in p.stdout.splitlines():
        i = world._static_name(os.path.basename(line.strip()))
        if i is not None:
            out.add(i)
    return out


def taken_ids():
    ids = set(world.static_ids())
    ids |= {int(k) for k in (index_doc().get("locations") or {}) if str(k).isdigit()}
    ids |= origin_main_ids()
    return ids


def next_free_id(taken=None):
    taken = taken_ids() if taken is None else set(taken)
    i = world.FIRST_NEW_ID
    while i in taken:
        i += 1
    if i >= world.NEW_ID_LIMIT:
        raise Refused("свободных номеров ниже %d нет" % world.NEW_ID_LIMIT)
    return i


def _ring(model):
    """Edge exits and a ring of entries three cells in, as the templates."""
    W, H = int(model["width"]), int(model["height"])
    exits = []
    for y in range(3, H - 3):
        exits += [[0, y, "W"], [1, y, "W"], [W - 2, y, "E"], [W - 1, y, "E"]]
    for x in range(2, W - 2):
        exits += [[x, 0, "N"], [x, 1, "N"], [x, 2, "N"], [x, H - 2, "S"], [x, H - 1, "S"]]
    entries = []
    for y in range(5, H - 5, 2):
        entries += [[3, y], [W - 4, y]]
    for x in range(4, W - 4, 2):
        entries += [[x, 4], [x, H - 5]]
    return exits, entries


def placing_problem(t, x, y, model, taken):
    """Why a creature cannot stand on (x, y) of a model, as
    rooms.placement_problems would say it, or None."""
    mt = mob_types()
    W, H = int(model["width"]), int(model["height"])
    try:
        names = _names()
        known = names.known(t)
    except Exception:                      # noqa: BLE001 -- no names table: the server decides
        known = True
    if t not in mt or not known:
        return "у клиента нет записи или имени этого существа"
    if world.retired_creature(t):
        return "существо выведено из игры (data/retired.json)"
    if world.creature_role(t) == "object":
        return "ящик или куча руды, не житель"
    if mt[t][0] == world.MOB and str((model.get("attrs") or {}).get("war", "0")) != "1":
        return "враждебное существо в мирной локации (war=0)"
    if not (0 <= x < W and 0 <= y < H):
        return "за краем сетки %dx%d" % (W, H)
    if (x, y) in {(int(r[0]), int(r[1])) for r in model.get("walls") or ()}:
        return "на препятствии"
    if (x, y) in {(int(r[0]), int(r[1])) for r in model.get("exits") or ()}:
        return "на выходе"
    if (x, y) in taken:
        return "там уже кто-то стоит"
    return None


def new_model(title, src=None, empty=None, why="", author="owner", new_id=None):
    """POST /api/new: a model of a new place, nothing written. A copy keeps
    the original's file but for its title, fn and <mobs>, whose creatures
    become inhabitants (those that could not stand are named in dropped)."""
    title = (title or "").strip()
    if not title:
        raise Refused("нужно название")
    if new_id is None:
        new_id = next_free_id()
    else:
        new_id = int(new_id)
        if not world.FIRST_NEW_ID <= new_id < world.NEW_ID_LIMIT:
            raise Refused("номер нового места: %d..%d" % (world.FIRST_NEW_ID, world.NEW_ID_LIMIT - 1))
        if new_id in taken_ids():
            raise Refused("номер %d занят" % new_id)
    dropped = []
    if src is not None:
        src = int(src)
        if src == 262:
            raise Refused("262 «Тотем» закрыт для редактора: копия клиента и сервера у него разные")
        path = world.static_path(src)
        if path is None:
            raise Refused("нет локации %d" % src)
        m = L.normalized(L.load(read_bytes(path)))
        slots = [(x, y, t) for x, y, t in L.mob_slots(m) if t]
        m["lists"]["mobs"] = []
        m["tails"]["mobs"] = ""
    else:
        empty = empty or {}
        W, H = int(empty.get("w", 64)), int(empty.get("h", 128))
        if (W, H) not in L.SIZES:
            raise Refused("размер — 64x128 или 32x64")
        library = empty.get("library") or "Desert"
        if library.lower() not in libraries():
            raise Refused("нет библиотеки %s" % library)
        library = libraries()[library.lower()]
        bg = dict(empty.get("background") or {"type": "lib", "id": "bg_desert1.jpg" if library == "Desert" else "",
                                               "fx": ""})
        m = {"attrs": {"title": "", "preloader": "", "bgExt": bg.get("type", "lib"), "bg": bg.get("id", ""),
                       "bgsound": "", "height": str(H), "width": str(W), "dir": "Static",
                       "library": library, "pvp": "0", "war": "0", "fn": "", "version": "1"},
             "width": W, "height": H, "background": bg, "sprites": [], "bgdecorations": [],
             "lists": {t: [] for t in L.LISTS}, "tails": {t: "" for t in L.LISTS}, "serverdata": "\r\n"}
        slots = []
    model = {"id": new_id, "state": "new", "from": src}
    model.update(to_model(m))
    model["attrs"]["title"] = title
    model["attrs"]["fn"] = fn_for(title, new_id)
    if src is None and (empty or {}).get("ring", True):
        model["exits"], model["entries"] = _ring(model)
    rows, taken = [], set()
    for x, y, t in slots:
        bad = placing_problem(t, x, y, model, taken)
        if bad:
            dropped.append({"type": t, "cell": [x, y], "name": creature_name(t), "why": bad})
            continue
        taken.add((x, y))
        rows.append({"type": t, "cell": [x, y],
                     "why": "DESIGNED (%s, %s): %s из <mobs> локации %d, с которой скопировано место «%s»."
                            % (today(), author, creature_name(t), src, title)})
    model.update({"inhabitants": rows, "doors": {}, "walk_ins": [], "no_map": None, "map": None,
                  "index": {"title": title, "from": src, "author": author, "created": today(),
                            "why": why or ""},
                  "closed": False})
    model["etag"] = etag_of(location_state(new_id))
    notes = []
    if GIT.get("ok") is False:
        notes.append("Номер %d выбран без origin/main (%s): если в другой сессии уже сделано место под этим "
                     "номером, при слиянии будет конфликт." % (new_id, GIT["why"]))
    return {"model": model, "dropped": dropped, "notes": notes}


# --- edits the server works out ------------------------------------------------------------------

def _instance(model, op):
    try:
        si, ai = int(op["sprite"]), int(op["anchor"])
        sp = model["sprites"][si]
        anchor = sp["anchors"][ai]
    except (KeyError, IndexError, TypeError, ValueError):
        raise Refused("нет такого спрайта: sprite %r, anchor %r" % (op.get("sprite"), op.get("anchor")))
    return si, ai, sp, anchor


def sprite_footprint(sp, objs=None, used=None):
    """[(dx, dy, code)] a sprite's placing stamps: an object's footprint as
    walls "f", a picture's the walls its original placings share. objs and
    used: objects_checked() and usage(), when the caller has them."""
    sid = sp["id"]
    objs = objects_checked() if objs is None else objs
    if sid in objs:
        return [(dx, dy, CO.OBSTACLE) for dx, dy in objs[sid]["footprint"]]
    kind = "ext" if sp.get("type") == "ext" else "lib"
    var = (L.num(sp.get("dx")), L.num(sp.get("dy")), sp.get("front") or "")
    used = (usage(wait=False) or {}) if used is None else used
    for r in used.get("%s:%s" % (kind, sid)) or ():
        if (r["dx"], r["dy"], r["front"]) == var:
            return [tuple(c) for c in r["footprint"]]
    return []


def _stamp(model, foot, ax, ay):
    """Walls of a footprint put down on the grid; the cells changed."""
    W, H = int(model["width"]), int(model["height"])
    walls = model.setdefault("walls", [])
    have = {(int(r[0]), int(r[1])) for r in walls}
    out = []
    for dx, dy, code in foot:
        x, y = L.offsets_cells([(dx, dy)], ax, ay)[0]
        if 0 <= x < W and 0 <= y < H and (x, y) not in have:
            walls.append([x, y, code])
            have.add((x, y))
            out.append([x, y])
    return out


def _unstamp(model, foot, ax, ay, keep=frozenset()):
    """The footprint's walls taken off (those with its code), but for the
    cells in keep; the cells."""
    gone = {}
    for dx, dy, code in foot:
        x, y = L.offsets_cells([(dx, dy)], ax, ay)[0]
        if (x, y) not in keep:
            gone[(x, y)] = code
    stay, out = [], []
    for r in model.get("walls") or ():
        c = (int(r[0]), int(r[1]))
        if c in gone and str(r[2]) == gone[c]:
            out.append(list(c))
            continue
        stay.append(r)
    model["walls"] = stay
    return out


def base_walls(model):
    """{(x, y)} of the walls the place was made with: those of the location
    it was copied from (none for a place made empty, its own for an
    original). Taking a picture out never takes these away."""
    if model.get("state") == "original":
        return {(int(r[0]), int(r[1])) for r in model.get("walls") or ()}
    src = model.get("from")
    if src is None:
        return set()
    try:
        path = world.static_path(int(src))
    except (TypeError, ValueError):
        return set()
    if path is None:
        return set()
    return {(x, y) for x, y, _e in L.load(path)["lists"]["obstacles"]}


def kept_walls(model, si, ai):
    """The cells whose walls stay when placing (si, ai) is taken out or
    moved: the place's own walls from its copy, and every cell another
    placing's footprint stands on (two objects side by side share a wall;
    the second never stamped it)."""
    keep = base_walls(model)
    objs, used = objects_checked(), usage(wait=False) or {}
    for sj, sp in enumerate(model.get("sprites") or ()):
        foot = sprite_footprint(sp, objs, used)
        if not foot:
            continue
        offs = [(dx, dy) for dx, dy, _c in foot]
        for aj, a in enumerate(sp.get("anchors") or ()):
            if (sj, aj) == (si, ai):
                continue
            try:
                keep.update(L.offsets_cells(offs, int(a[0]), int(a[1])))
            except (TypeError, ValueError, IndexError):
                continue
    return keep


def _cell(op, model, key="cell"):
    try:
        x, y = int(op[key][0]), int(op[key][1])
    except (KeyError, IndexError, TypeError, ValueError):
        raise Refused("%s: [x, y]" % key)
    W, H = int(model["width"]), int(model["height"])
    if not (0 <= x < W and 0 <= y < H):
        raise Refused("клетка %d:%d за краем сетки %dx%d" % (x, y, W, H))
    return x, y


def edge_side(x, y, W, H, band=EDGE_BAND):
    """The edge a cell lies on (W N E S), the nearest in pixels when two, or
    None off the edges."""
    near = []
    if x <= band["W"]:
        near.append((x * L.CELL_W, "W"))
    if x >= W - 1 - band["E"]:
        near.append(((W - 1 - x) * L.CELL_W, "E"))
    if y <= band["N"]:
        near.append((y * L.ROW_H, "N"))
    if y >= H - 1 - band["S"]:
        near.append((max(0, H - 1 - y) * L.ROW_H, "S"))
    return min(near)[1] if near else None


def edit(model, op):
    """POST /api/edit: one edit of a model the server works out. Returns
    (model, info); the model given is not changed."""
    model = copy.deepcopy(model)
    kind = op.get("op")
    info = {"cells": []}
    if kind == "place":
        what = op.get("kind")
        sid = str(op.get("id") or "")
        if what not in ("lib", "ext", "object") or not sid:
            raise Refused("place: kind lib, ext или object и id")
        library = str((model.get("attrs") or {}).get("library") or "")
        if what == "ext" and sid in objects_checked():
            what = "object"
        if what == "lib":
            lib = art_index()["libraries"].get(libraries().get(library.lower(), library)) or {}
            if sid not in (lib.get("exports") or ()):
                raise Refused("в библиотеке %s нет картинки %s: у локации одна библиотека, картинки из других "
                              "ставятся как спрайты ext или свои объекты" % (library, sid))
        elif what == "ext":
            known = {s.lower() for s in art_index().get("sprites") or ()} | {s.lower() for s in local_ext()[0]}
            if sid.lower() not in known:
                raise Refused("нет спрайта %s (locations/libs/sprite/%s.swf)" % (sid, sid))
        x, y = _cell(op, model)
        d = sprite_default(what, sid, library)
        sp = {"id": sid, "type": d["type"],
              "dx": L.num(op["dx"]) if op.get("dx") is not None else d["dx"],
              "dy": L.num(op["dy"]) if op.get("dy") is not None else d["dy"],
              "front": op.get("front") if op.get("front") is not None else d["front"],
              "anchors": [[x, y]]}
        if not re.fullmatch(r"([0-9a-f]{4})*", sp["front"] or ""):
            raise Refused("front: клетки по 4 шестнадцатеричных знака")
        model.setdefault("sprites", []).append(sp)
        info["sprite"] = [len(model["sprites"]) - 1, 0]
        if op.get("stamp"):
            foot = d["footprint"] if what == "object" or op.get("dx") is None else sprite_footprint(sp)
            info["cells"] = _stamp(model, [tuple(c) for c in foot], x, y)
    elif kind == "move":
        si, ai, sp, (ax, ay) = _instance(model, op)
        x, y = _cell(op, model)
        if op.get("stamp"):
            foot = sprite_footprint(sp)
            info["cells"] = _unstamp(model, foot, ax, ay, kept_walls(model, si, ai)) + _stamp(model, foot, x, y)
        sp["anchors"][ai] = [x, y]
    elif kind == "delete":
        si, ai, sp, (ax, ay) = _instance(model, op)
        if op.get("stamp"):
            info["cells"] = _unstamp(model, sprite_footprint(sp), ax, ay, kept_walls(model, si, ai))
        del sp["anchors"][ai]
        if not sp["anchors"]:
            del model["sprites"][si]
    elif kind == "nudge":
        si, ai, sp, anchor = _instance(model, op)
        try:
            dx, dy = L.num(op["dx"]), L.num(op["dy"])
        except KeyError:
            raise Refused("nudge: dx и dy")
        if len(sp["anchors"]) == 1:
            sp["dx"], sp["dy"] = dx, dy
        else:
            del sp["anchors"][ai]
            one = dict(sp, dx=dx, dy=dy, anchors=[anchor])
            model["sprites"].insert(si + 1, one)
            info["sprite"] = [si + 1, 0]
    elif kind == "exits":
        side = op.get("side") or "auto"
        if side not in ("auto",) + EDGE_SIDES + DOOR_SIDES:
            raise Refused("side: auto, W, N, E, S, a или b")
        W, H = int(model["width"]), int(model["height"])
        exits = {(int(r[0]), int(r[1])): r for r in model.get("exits") or ()}
        order = [(int(r[0]), int(r[1])) for r in model.get("exits") or ()]
        for c in op.get("cells") or ():
            x, y = _cell({"cell": c}, model)
            s = edge_side(x, y, W, H) if side == "auto" else side
            if s is None:
                raise Refused("клетка %d:%d не у края: выход здесь — дверь a или b" % (x, y))
            if (x, y) not in exits:
                order.append((x, y))
            exits[(x, y)] = [x, y, s]
            info["cells"].append([x, y])
        model["exits"] = [exits[c] for c in order]
    elif kind == "ring":
        exits, entries = _ring(model)
        have = {(int(r[0]), int(r[1])) for r in model.get("exits") or ()}
        model["exits"] = list(model.get("exits") or []) + [e for e in exits if (e[0], e[1]) not in have]
        have = {(int(r[0]), int(r[1])) for r in model.get("entries") or ()}
        model["entries"] = list(model.get("entries") or []) + [e for e in entries if (e[0], e[1]) not in have]
    else:
        raise Refused("неизвестная правка %r (place, move, delete, nudge, exits, ring)" % kind)
    return model, info


# --- the checks ---------------------------------------------------------------------------------

def problem(level, what, text, cells=(), loc=None):
    return {"level": level, "what": what, "text": text,
            "cells": [[int(c[0]), int(c[1])] for c in cells][:200], "loc": loc}


def walks():
    """(inside, outside): the map cells walked to from the Nubian village
    and from the start, as data/test_borders.py walks them."""
    def build():
        import test_borders as B
        return B.walk_from(B.NUBIAN_VILLAGE), B.walk_from(B.START)
    return memo("walks", build)


def _components(W, H, walls, sources):
    """The cells a walk from the sources reaches, over free cells."""
    seen = set()
    todo = collections.deque()
    for s in sources:
        if s not in seen and s not in walls and 0 <= s[0] < W and 0 <= s[1] < H:
            seen.add(s)
            todo.append(s)
    while todo:
        x, y = todo.popleft()
        for n in L.neighbours(x, y):
            if n not in seen and n not in walls and 0 <= n[0] < W and 0 <= n[1] < H:
                seen.add(n)
                todo.append(n)
    return seen


def _art_problems(model, extra):
    try:
        return A.art_problems(to_lavaloc(model), art_index(), extra)
    except Exception as exc:               # noqa: BLE001
        return [{"what": "art", "id": "", "type": "", "count": 1, "why": str(exc)}]


def lint(model, for_save=True):
    """L1 and L2 on a model: [problem]. for_save=False looks at an original
    location as it is, without refusing it for being one."""
    out = []
    add = out.append
    try:
        loc_id = int(model["id"])
        W, H = int(model["width"]), int(model["height"])
    except (KeyError, TypeError, ValueError):
        return [problem("error", "model", "в модели нет id, width или height")]
    st = model.get("state")
    attrs = model.get("attrs") or {}
    war = str(attrs.get("war", "0")) == "1"

    # --- the id, the size, the attributes
    if loc_id == 262:
        add(problem("error" if for_save else "warning", "id", "262 «Тотем» закрыт для редактора"))
    if st == "original" or (st != "ours" and loc_id in base_ids()):
        add(problem("error" if for_save else "warning", "id",
                    "%d — локация оригинала: редактор её не пишет; сделайте копию" % loc_id))
    elif st == "new" and not world.FIRST_NEW_ID <= loc_id < world.NEW_ID_LIMIT:
        add(problem("error", "id", "номер нового места: %d..%d" % (world.FIRST_NEW_ID, world.NEW_ID_LIMIT - 1)))
    if (W, H) not in L.SIZES:
        add(problem("error" if st == "new" else "warning", "size", "размер %dx%d: у оригинала только 64x128 и 32x64"
                    % (W, H)))
    title = str(attrs.get("title") or "")
    if not title.strip():
        add(problem("error", "title", "нужно название"))
    elif len(title) > MAX_TITLE or any(ord(ch) < 32 for ch in title):
        add(problem("error", "title", "название — до %d знаков в одну строку" % MAX_TITLE))
    if not re.fullmatch(r"[A-Za-z0-9_]+", str(attrs.get("fn") or "")):
        add(problem("error", "fn", "fn — латиница, цифры и _ (ED_<имя> для нового места)"))
    for k in ("pvp", "war"):
        if str(attrs.get(k, "")) not in ("0", "1"):
            add(problem("error", k, "%s — 0 или 1" % k))
    snd = str(attrs.get("bgsound") or "")
    if snd and snd.lower() not in {t.lower() for t in tracks()}:
        add(problem("error", "bgsound", "нет музыки %s (есть: %s)" % (snd, ", ".join(tracks()))))
    if str(attrs.get("library") or "").lower() not in libraries():
        add(problem("error", "library", "нет библиотеки %s" % attrs.get("library")))
    idx = model.get("index") or {}
    if st != "original" and not str(idx.get("why") or "").strip():
        add(problem("error", "why", "нужно «почему»: слово владельца, зачем это место (data/locations/index.json)"))

    # --- the art: what the copy had missing already is a warning
    extra = local_ext()
    base_keys = set()
    src = model.get("from")
    if src is not None and world.static_path(int(src)):
        try:
            for pr in A.art_problems(L.load(world.static_path(int(src))), art_index(), extra):
                base_keys.add((pr["what"], pr["id"], pr["type"]))
        except Exception:                  # noqa: BLE001
            pass
    for pr in _art_problems(model, extra):
        inherited = (pr["what"], pr["id"], pr["type"]) in base_keys
        add(problem("warning" if inherited or st == "original" else "error", "art",
                    "%s %s%s: %s%s" % ({"library": "библиотека", "background": "фон", "sprite": "спрайт",
                                        "decal": "наклейка", "bgsound": "музыка"}.get(pr["what"], pr["what"]),
                                       pr["id"], " x%d" % pr["count"] if pr["count"] > 1 else "", art_why_ru(pr["why"]),
                                       " (так в оригинале)" if inherited else "")))

    # --- cells on the grid
    def grid(rows, what, label, allow_extra=True):
        """Cells of a list on the grid (the extra row y == H, which the
        original's exits and sprites use, where allowed)."""
        bad, extra_row, seen, twice = [], [], set(), []
        for r in rows or ():
            try:
                x, y = int(r[0]), int(r[1])
            except (TypeError, ValueError, IndexError):
                add(problem("error", what, "%s: клетка %r — не [x, y]" % (label, r)))
                continue
            if not (0 <= x < W and 0 <= y <= H) or (y == H and not allow_extra):
                bad.append((x, y))
            elif y == H:
                extra_row.append((x, y))
            if (x, y) in seen:
                twice.append((x, y))
            seen.add((x, y))
        if bad:
            add(problem("error", what, "%s: клетки за краем сетки %dx%d" % (label, W, H), bad))
        return extra_row, twice

    walls = {}
    for r in model.get("walls") or ():
        try:
            code = str(r[2]) if len(r) > 2 else "f"
        except TypeError:
            code = "?"
        if not re.fullmatch(r"[0-9a-f]", code):
            add(problem("error", "walls", "код препятствия — один знак 0-9 a-f, не %r" % code,
                        [r[:2]] if _ok_cell(r) else ()))
        try:
            walls[(int(r[0]), int(r[1]))] = code
        except (TypeError, ValueError, IndexError):
            pass
    grid(model.get("walls"), "walls", "стены")
    exits = {}
    grid(model.get("exits"), "exits", "выходы")
    for r in model.get("exits") or ():
        try:
            c, s = (int(r[0]), int(r[1])), str(r[2])
        except (TypeError, ValueError, IndexError):
            continue
        if s not in CODE:
            add(problem("warning", "exits", "выход с кодом стороны %r: такой код сервер не знает" % s, [c]))
        if c in exits and exits[c] != s:
            add(problem("error", "exits", "на клетке два выхода: %s и %s" % (exits[c], s), [c]))
        exits[c] = s
    entries = [(int(r[0]), int(r[1])) for r in model.get("entries") or () if _ok_cell(r)]
    wars = [(int(r[0]), int(r[1])) for r in model.get("war_entries") or () if _ok_cell(r)]
    grid(model.get("entries"), "entries", "входы", allow_extra=False)
    grid(model.get("war_entries"), "war_entries", "военные входы", allow_extra=False)
    for s in model.get("sprites") or ():
        an_extra, _ = grid(s.get("anchors"), "sprites", "спрайт %s" % s.get("id"))
        if an_extra:
            add(problem("warning", "sprites", "спрайт %s на лишнем ряду y=%d: такой клетки у клиента нет, и он "
                        "рисует спрайт от левого верхнего угла локации (сдвиг dx, dy от точки 0,0)"
                        % (s.get("id"), H), an_extra))
        if s.get("type") not in (None, "lib", "ext"):
            add(problem("error", "sprites", "тип спрайта %s — lib или ext" % s.get("id")))
        if not re.fullmatch(r"([0-9a-fA-F]{4})*", str(s.get("front") or "")):
            add(problem("error", "sprites", "front спрайта %s — клетки по 4 шестнадцатеричных знака" % s.get("id")))

    # --- exit sides by their edge
    off_edge = collections.defaultdict(list)
    for c, s in exits.items():
        if s in EDGE_SIDES and not _on_band(c, s, W, H):
            off_edge[s].append(c)
    for s, cs in sorted(off_edge.items()):
        add(problem("warning", "exits", "выход %s не у своего края: игрок выйдет на %s, хоть стоит не там"
                    % (s, {"W": "запад", "N": "север", "E": "восток", "S": "юг"}[s]), cs))
    on_walls = [c for c in exits if c in walls]
    if on_walls:
        add(problem("warning", "exits", "выход на препятствии: на эту клетку не встать", on_walls))

    # --- entries
    free = [c for c in entries if c not in walls and c not in exits]
    if not free:
        add(problem("error", "entries", "нет свободной клетки входа: игроку негде появиться", entries))
    bad_entries = [c for c in entries if c in walls]
    if bad_entries:
        add(problem("warning", "entries", "вход на препятствии", bad_entries))
    if war and wars and not [c for c in wars if c not in walls]:
        add(problem("warning", "war_entries", "все военные входы на препятствиях", wars))

    # --- the file's own <mobs>: read only
    raw_mobs = [list(r) for r in (model.get("raw") or {}).get("mobs") or ()]
    if st == "new" and raw_mobs:
        add(problem("error", "spawns", "у нового места <mobs> пуст: жители — строки data/placements.json"))
    if st == "ours":
        disk = read_bytes(P.xml(loc_id))
        if disk is not None:
            was = [[x, y, e] for x, y, e in L.load(disk)["lists"]["mobs"]]
            if was != raw_mobs:
                add(problem("error", "spawns", "<mobs> файла не правится: жители — строки data/placements.json"))

    # --- inhabitants (rooms.placement_problems, cell by cell)
    taken = {(int(r[0]), int(r[1])) for r in model.get("spawns") or () if _ok_cell(r) and len(r) > 2 and r[2]}
    spawn_types = [int(r[2]) for r in model.get("spawns") or () if len(r) > 2 and r[2]]
    for r in model.get("inhabitants") or ():
        try:
            t = int(r["type"])
            x, y = int(r["cell"][0]), int(r["cell"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            add(problem("error", "inhabitants", "житель без type и cell [x, y]: %r" % (r,)))
            continue
        bad = placing_problem(t, x, y, model, taken)
        if bad:
            add(problem("error", "inhabitants", "%s (%d) на %d:%d: %s" % (creature_name(t), t, x, y, bad), [(x, y)]))
        taken.add((x, y))
        if "escort" in r:
            if not isinstance(r["escort"], bool):
                add(problem("error", "inhabitants", "escort — true или false", [(x, y)]))
            elif r["escort"] and (mob_types().get(t, (None,))[0] != world.MOB
                                  or not any(world.creature_role(s) == "boss" for s in spawn_types)):
                add(problem("error", "inhabitants", "%s: свита без босса в <mobs> файла" % creature_name(t),
                            [(x, y)]))

    # --- doors, walk-ins, the ways in and out
    sides_here = set(exits.values())
    doors = model.get("doors") or {}
    for side, d in sorted(doors.items()):
        if side not in DOOR_SIDES:
            add(problem("error", "doors", "дверь %r: двери только a и b" % side))
            continue
        if not d:
            continue
        if side not in sides_here:
            add(problem("error", "doors", "двери %s нет на карте локации: нет выходов с кодом %s" % (side, side)))
        try:
            target = int(d.get("target"))
        except (TypeError, ValueError):
            add(problem("error", "doors", "дверь %s: куда? нужен номер локации" % side))
            continue
        if target == loc_id:
            add(problem("error", "doors", "дверь %s ведёт в саму себя" % side))
        elif world.static_path(target) is None:
            add(problem("error", "doors", "дверь %s ведёт в %d, а такой локации нет" % (side, target)))
    leads = {s for s in DOOR_SIDES if (doors.get(s) or {}).get("target") is not None
             or _exits_json_door(loc_id, s)}
    for side in DOOR_SIDES:
        if side in sides_here and side not in leads:
            cells = [c for c, s in exits.items() if s == side]
            add(problem("warning", "doors", "дверь %s никуда не ведёт: сервер ответит «Куда ведёт этот проход, "
                        "пока неизвестно»" % side, cells))
    edge_exits = sides_here & set(EDGE_SIDES)
    if not edge_exits and not (leads & sides_here) and not _quest_ways(loc_id):
        add(problem("error", "ways", "из места не выйти: нет выходов по краям и ни одна дверь никуда не ведёт"))
    for wi in model.get("walk_ins") or ():
        out.extend(_walk_in_problems(wi, loc_id))
    mp = model.get("map") or None
    if mp and mp.get("cell") is not None:
        out.extend(map_problems(model))
    has_in = (mp and mp.get("cell") is not None) or model.get("walk_ins") or _doors_into(loc_id)
    if not has_in:
        add(problem("warning", "ways", "в место не попасть: нет ни клетки на карте, ни прохода из другой локации, "
                    "ни двери, что вела бы сюда"))

    # --- the file as it will be written: the client's zones are its exits
    if not any(p["level"] == "error" and p["what"] in ("walls", "exits", "entries") for p in out):
        try:
            written = L.load(model_bytes(model))
            if [c[:2] for c in written["lists"]["zones"]] != [c[:2] for c in written["lists"]["outzones"]]:
                add(problem("error", "zones", "zones файла не совпали с outzones: клиент открыл бы окно выхода "
                            "не там, где выпускает сервер"))
        except (ValueError, KeyError, TypeError) as exc:
            add(problem("error", "model", "файл из модели не пишется: %s" % exc))

    # --- L2: the walk
    out.extend(walk_problems(model, walls, exits, entries, wars, war))
    return out


def _ok_cell(r):
    try:
        int(r[0]), int(r[1])
        return True
    except (TypeError, ValueError, IndexError):
        return False


def _on_band(c, s, W, H):
    x, y = c
    return {"W": x <= WARN_BAND["W"], "E": x >= W - 1 - WARN_BAND["E"],
            "N": y <= WARN_BAND["N"], "S": y >= H - 1 - WARN_BAND["S"]}[s]


def _doors_into(loc_id):
    """Locations whose doors (data/passages.json, data/exits.json) lead here."""
    out = []
    doors = passages_doc().get("doors") or {}
    for src in _ids(doors):
        for side, rec in (doors[src] or {}).items():
            if isinstance(rec, dict) and rec.get("target_loc_id") == loc_id:
                out.append((int(src), side))
    guessed = _exits_json()
    for src in _ids(guessed):
        for r in (guessed[src] or {}).get("doors") or ():
            if isinstance(r, dict) and r.get("target_loc_id") == loc_id \
                    and r.get("confidence") in travel.DOOR_CONFIDENCE:
                out.append((int(src), r.get("side")))
    return out


def _exits_json():
    """data/exits.json 'doors': the guessed doors of the original's files."""
    return memo("exits_json", lambda: (load_json(P.d("exits.json"), {}) or {}).get("doors") or {})


def _exits_json_door(loc_id, side):
    """Whether data/exits.json leads door `side` of a location somewhere
    the server follows (confidence high or medium)."""
    for r in (_exits_json().get(str(loc_id)) or {}).get("doors") or ():
        if r.get("side") == side and r.get("target_loc_id") is not None \
                and r.get("confidence") in travel.DOOR_CONFIDENCE:
            return True
    return False


def _quest_ways(loc_id):
    return (passages_doc().get("quest") or {}).get(str(loc_id)) or []


def _walk_in_problems(wi, loc_id):
    out = []
    try:
        src = int(wi.get("from"))
        cells = [(int(c[0]), int(c[1])) for c in wi.get("cells") or ()]
    except (TypeError, ValueError, IndexError, AttributeError):
        return [problem("error", "walk_in", "проход: нужны from (номер) и cells [[x, y]]")]
    if src == loc_id:
        return [problem("error", "walk_in", "проход из места в само себя")]
    if src == 262:
        return [problem("error", "walk_in", "262 «Тотем» закрыт для редактора")]
    g = location_grid(src)
    if g is None:
        return [problem("error", "walk_in", "проход из %d: такой локации нет" % src)]
    if not cells:
        return [problem("error", "walk_in", "проход из %d без клеток" % src, loc=src)]
    W, H, walls, entries, exits = g
    off = [c for c in cells if not (0 <= c[0] < W and 0 <= c[1] < H)]
    if off:
        out.append(problem("error", "walk_in", "проход: клетки за краем сетки %d (%dx%d)" % (src, W, H), off, src))
    on_wall = [c for c in cells if c in walls]
    if on_wall:
        out.append(problem("error", "walk_in", "проход на препятствии локации %d" % src, on_wall, src))
    on_exit = [c for c in cells if c in exits]
    if on_exit:
        out.append(problem("error", "walk_in", "проход на выходе локации %d (%s)" % (
            src, "".join(sorted({exits[c] for c in on_exit}))), on_exit, src))
    others = set()
    for r in (passages_doc().get("walk_in") or {}).get(str(src)) or ():
        if isinstance(r, dict) and r.get("target_loc_id") != loc_id:
            others |= {(int(c[0]), int(c[1])) for c in r.get("cells") or ()}
    clash = [c for c in cells if c in others]
    if clash:
        out.append(problem("error", "walk_in", "на этих клетках %d уже есть проход в другое место" % src, clash, src))
    on_entry = [c for c in cells if c in set(entries)]
    if on_entry:
        out.append(problem("warning", "walk_in", "проход на клетке входа %d: пришедший туда сразу уйдёт сюда"
                           % src, on_entry, src))
    free = [c for c in entries if c not in walls]
    reach = _components(W, H, walls, free)
    stuck = [c for c in cells if c not in reach and c not in walls]
    if stuck and len(stuck) == len([c for c in cells if c not in walls]):
        out.append(problem("error", "walk_in", "до прохода не дойти от входов локации %d" % src, stuck, src))
    return out


def map_problems(model):
    """What keeps a model's map cell from being its (the fast checks; the
    recount itself is L3's)."""
    out = []
    loc_id = int(model["id"])
    mp = model.get("map") or {}
    try:
        x, y = int(mp["cell"][0]), int(mp["cell"][1])
    except (KeyError, TypeError, ValueError, IndexError):
        return [problem("error", "map", "клетка карты — [x, y]")]
    c = (x, y)
    where = "клетка карты %d,%d" % c
    X, Y = world.MAP_X, world.MAP_Y
    if not (X[0] <= x <= X[1] and Y[0] <= y <= Y[1]):
        return [problem("error", "map", "%s за краем мира (%d..%d, %d..%d)" % (where, X[0], X[1], Y[0], Y[1]))]
    if x in X or y in Y:
        out.append(problem("error", "map", "%s на кромке мира: там кольцо скал (data/borders.json)" % where))
    if not world.passable(x, y):
        out.append(problem("error", "map", "%s непроходима: горы или вода" % where))
    other = settlements_table().get(c)
    if other is not None and other != loc_id:
        out.append(problem("error", "map", "%s занята: там %d" % (where, other)))
    ver = (verified_doc().get("cells") or {})
    if _key(*c) in ver and ver[_key(*c)] != loc_id:
        out.append(problem("error", "map", "%s решена в data/settlements_verified.json (%s): её не трогаем"
                           % (where, ver[_key(*c)])))
    if c in retired_cells():
        out.append(problem("error", "map", "%s — клетка выведенного места %d (data/retired.json)"
                           % (where, retired_cells()[c])))
    if c in patrol_cells():
        out.append(problem("error", "map", "%s — клетка патруля лагеря %d" % (where, patrol_cells()[c])))
    try:
        inside, outside = walks()
        if c not in inside and c not in outside:
            out.append(problem("error", "map", "%s отрезана стеной долины: ни от старта, ни из долины туда не "
                               "дойти (data/test_borders.py ждёт ровно столько отрезанных мест, сколько есть)"
                               % where))
    except Exception as exc:               # noqa: BLE001
        out.append(problem("warning", "map", "обход карты не удался: %s" % exc))
    sides = {str(r[2]) for r in model.get("exits") or () if len(r) > 2} & set(EDGE_SIDES)
    if not sides:
        out.append(problem("error", "map", "на карту ставится место с выходами по краям; у этого их нет"))
    for s in sorted(sides):
        nx, ny = travel.neighbour(x, y, s)
        if not world.in_map(nx, ny):
            out.append(problem("error", "map", "выход %s ведёт за край мира" % s))
        elif not world.passable(nx, ny):
            out.append(problem("error", "map", "выход %s ведёт в горы или воду (%d,%d)" % (s, nx, ny)))
    label = mp.get("label") or ""
    if not label and not _tooltips().get(c):
        out.append(problem("warning", "map", "без подписи игрок не увидит на карте, что здесь"))
    if label:
        if any(ch in label for ch in "\t\r\n"):
            out.append(problem("error", "map", "подпись — в одну строку (перенос — <br>)"))
        if label in _tooltips().get(c, ()):
            out.append(problem("error", "map", "у клетки уже есть подпись «%s»" % label))
    cut = cut_cells().get(c)
    if cut:
        out.append(problem("error", "map", "%s вырезана владельцем: %s. Новое место туда не ставится, "
                                           "выберите другую клетку" % (where, cut)))
    sq = mp.get("square")
    if sq:
        import map_cells
        if sq not in map_cells.PALETTE:
            out.append(problem("error", "map", "квадрат: цвет из %s" % ", ".join(sorted(map_cells.PALETTE))))
    if "test" in str((model.get("attrs") or {}).get("fn", "")).lower():
        out.append(problem("warning", "map", "fn со словом test: пересчёт карты считает такие файлы черновиками"))
    return out


def cut_cells():
    """{(x, y): why} of the map cells the owner's cuts took off the map: a
    square erased or kept under a hidden name, or a hidden name with no square
    (data/map_cells.json 'cells', 'keep', 'bare') and a name hidden
    (data/map_labels.json 'hide'). A place of ours
    there would put a name and a place back over what was cut
    (server/test_map_cells.py, test_halfa_cut and the other cuts' suites
    hold those cells empty)."""
    out = {}
    cd = cells_doc()
    for part, why in (("cells", "квадрат стёрт (data/map_cells.json)"),
                      ("keep", "имя снято, квадрат оставлен (data/map_cells.json)"),
                      ("bare", "имя снято, квадрата нет (data/map_cells.json)")):
        for k in cd.get(part) or {}:
            try:
                out.setdefault(_xy(k), why)
            except ValueError:
                continue
    for r in labels_doc().get("labels") or ():
        if isinstance(r, dict) and r.get("hide"):
            try:
                out.setdefault((int(r["x"]), int(r["y"])), "имя клетки снято (data/map_labels.json)")
            except (KeyError, TypeError, ValueError):
                continue
    return out


def _tooltips():
    """{(x, y): [texts]} of the original's map names (RES database/locations.xml)."""
    def read():
        import html
        out = collections.defaultdict(list)
        raw = read_bytes(os.path.join(world.RES, "database", "locations.xml")) or b""
        for x, y, t in re.findall(rb'<location x="(\d+)" y="(\d+)" text="([^"]*)"', raw):
            out[(int(x), int(y))].append(html.unescape(t.decode("utf-8", "replace")))
        return dict(out)
    return memo("tooltips", read)


def walk_problems(model, walls, exits, entries, wars, war):
    """L2: from the free entries to every exit side, door, war entry and
    inhabitant."""
    out = []
    W, H = int(model["width"]), int(model["height"])
    wset = set(walls)
    free = [c for c in entries if c not in wset]
    if not free:
        return out
    reach = _components(W, H, wset, free)
    by_side = collections.defaultdict(list)
    for c, s in exits.items():
        by_side[s].append(c)
    for s, cs in sorted(by_side.items()):
        if not any(c in reach for c in cs):
            out.append(problem("error", "walk", "до выхода %s не дойти от входов" % s, cs))
    if war:
        stuck = [c for c in wars if c not in wset and c not in reach]
        if stuck:
            out.append(problem("error", "walk", "до военных входов не дойти от обычных", stuck))
    for r in model.get("inhabitants") or ():
        try:
            c = (int(r["cell"][0]), int(r["cell"][1]))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if c in reach or any(n in reach for n in L.neighbours(*c)):
            continue
        out.append(problem("error", "walk", "к жителю %s не подойти от входов" % creature_name(r.get("type")), [c]))
    return out


# --- writing: the candidate files ---------------------------------------------------------------

def _why(text, default):
    text = str(text or "").strip()
    return text if text else default


def plan_writes(model, author="owner"):
    """{path: bytes} of every file a save of this model changes, the
    location's file and its rows; settlements.json and exits_sides.json
    are L3's and the candidate tree's."""
    loc_id = int(model["id"])
    key = str(loc_id)
    attrs = model.get("attrs") or {}
    title = str(attrs.get("title") or "").strip()
    out = {}

    def put(path, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        if data != read_bytes(path):
            out[path] = data

    # the file
    put(P.xml(loc_id), model_bytes(model))

    # its row in the index
    old_idx = (index_doc().get("locations") or {}).get(key) or {}
    idx = dict(model.get("index") or {})
    row = {"title": title, "from": idx.get("from", old_idx.get("from", model.get("from"))),
           "author": idx.get("author") or old_idx.get("author") or author,
           "created": idx.get("created") or old_idx.get("created") or today(),
           "why": str(idx.get("why") or "").strip()}
    for k, v in old_idx.items():
        row.setdefault(k, v)
    text = read_text(P.index) or '{\n "locations": {}\n}\n'
    put(P.index, set_rows(text, ["locations", key], row))

    # inhabitants
    rows = []
    for r in model.get("inhabitants") or ():
        t = int(r["type"])
        rec = {"type": t, "cell": [int(r["cell"][0]), int(r["cell"][1])]}
        if "escort" in r:
            rec["escort"] = bool(r["escort"])
        for k, v in r.items():
            if k not in ("type", "cell", "escort", "why"):
                rec[k] = v
        rec["why"] = _why(r.get("why"), "DESIGNED (%s, %s): %s в «%s» (%d), поставлен редактором локаций."
                          % (today(), author, creature_name(t), title, loc_id))
        rows.append(rec)
    text = read_text(P.placements)
    if text is not None:
        put(P.placements, set_rows(text, ["locations", key], rows or None))
    elif rows:
        put(P.placements, dumps1({"locations": {key: rows}}))

    # ways: doors, walk-ins, no_map
    text = read_text(P.passages)
    if text is None:
        text = "{}\n"
    doc = json.loads(text)
    doors = model.get("doors") or {}
    placed = set(settlements_table().values())
    for side in DOOR_SIDES:
        d = doors.get(side) or {}
        old = ((doc.get("doors") or {}).get(key) or {}).get(side)
        if d.get("target") is None:
            if old is not None:
                text = jsonrows.delete_key(text, ["doors", key, side])
            continue
        target = int(d["target"])
        rec = dict(old) if isinstance(old, dict) else {}
        rec.update({"confidence": d.get("confidence") or rec.get("confidence") or "high",
                    "source": d.get("source") or rec.get("source") or "editor",
                    "target_loc_id": target})
        # A door into a place that stands on the map arrives on that place's
        # cell (travel.plan_exit own_cell): without it the player keeps the
        # cell he had here -- this place's own, when it has one -- and the
        # map, and every edge exit of the far side, are a cell off.
        if d.get("own_cell") is False or target not in placed:
            rec.pop("own_cell", None)
        else:
            rec["own_cell"] = True
        rec["why"] = _why(d.get("why"), "DESIGNED (%s, %s): дверь %s места «%s» (%d) ведёт в %d."
                          % (today(), author, side, title, loc_id, target))
        rec = {k: rec[k] for k in ("confidence", "source", "target_loc_id", "own_cell", "why") if k in rec}
        if rec != old:
            text = jsonrows.set_key(text, ["doors", key, side], rec)
    doc = json.loads(text)
    if (doc.get("doors") or {}).get(key) == {}:
        text = jsonrows.delete_key(text, ["doors", key])
    # walk-ins: the rows of other locations that lead here, each from-location's list rewritten
    doc = json.loads(text)
    walk = doc.get("walk_in") or {}
    mine = collections.defaultdict(list)
    for wi in model.get("walk_ins") or ():
        src = int(wi["from"])
        mine[str(src)].append({"cells": [[int(c[0]), int(c[1])] for c in wi.get("cells") or ()],
                               "target_loc_id": loc_id,
                               "why": _why(wi.get("why"), "DESIGNED (%s, %s): проход из %d в «%s» (%d), место "
                                           "из редактора локаций; файл %d не тронут."
                                           % (today(), author, src, title, loc_id, src))})
    for src in sorted(set(_ids(walk)) | set(mine), key=int):
        old = list(walk.get(src) or [])
        # in place: this location's new rows where its old rows stood, in
        # their order, the rest of them after; another location's rows keep
        # their places, so a save that changes nothing changes no byte
        todo = list(mine.get(src, []))
        new = []
        for r in old:
            if isinstance(r, dict) and r.get("target_loc_id") == loc_id:
                if todo:
                    new.append(todo.pop(0))
                continue
            new.append(r)
        new += todo
        if new == old:
            continue
        text = jsonrows.set_key(text, ["walk_in", src], new) if new else \
            jsonrows.delete_key(text, ["walk_in", src])
        doc = json.loads(text)
    nm = model.get("no_map")
    old = (doc.get("no_map") or {}).get(key)
    if nm:
        rec = {"why": _why(nm.get("why"), "DESIGNED (%s, %s): «%s» (%d) покидают только своими проходами, "
                           "не на карту." % (today(), author, title, loc_id))}
        if rec != old:
            text = jsonrows.set_key(text, ["no_map", key], rec)
    elif old is not None:
        text = jsonrows.delete_key(text, ["no_map", key])
    put(P.passages, text)

    # the map: the verified cell, the label, the square
    mp = model.get("map") or {}
    cell = None
    if mp.get("cell") is not None:
        cell = _key(mp["cell"][0], mp["cell"][1])
    vtext = read_text(P.verified)
    if vtext is not None or cell:
        vtext = vtext or dumps1({"cells": {}, "why": {}})
        vdoc = json.loads(vtext)
        mine_cells = [k for k, v in (vdoc.get("cells") or {}).items() if v == loc_id]
        for k in mine_cells:
            if k != cell:
                vtext = set_rows(vtext, ["cells", k], None)
                vtext = set_rows(vtext, ["why", k], None)
        if cell:
            why = _why(mp.get("why"), "DESIGNED (%s, %s): «%s» (%d), место из редактора локаций "
                       "(data/locations), поставлено на эту клетку владельцем." % (today(), author, title, loc_id))
            vtext = set_rows(vtext, ["cells", cell], loc_id)
            vtext = set_rows(vtext, ["why", cell], why)
        put(P.verified, vtext)
    else:
        mine_cells = []
    old_cells = set(mine_cells)
    # the label: rows added over this location's cells, old and new
    ltext = read_text(P.labels)
    if ltext is not None or (cell and mp.get("label")):
        ltext = ltext or '{\n "labels": []\n}\n'
        wanted = None
        if cell and mp.get("label"):
            x, y = _xy(cell)
            wanted = {"x": x, "y": y, "text": mp["label"], "add": True,
                      "why": _why(mp.get("label_why"), "DESIGNED (%s, %s): подпись места «%s» (%d) на его клетке."
                                  % (today(), author, title, loc_id))}
        rows_ = jsonrows.items(ltext, ["labels"])
        ours_rows = [(i, v) for i, (v, _a, _e) in enumerate(rows_)
                     if isinstance(v, dict) and v.get("add") and _key(v.get("x", -1), v.get("y", -1))
                     in (old_cells | ({cell} if cell else set()))]
        keep = None
        for i, v in ours_rows:
            if wanted is not None and keep is None and v.get("text") == wanted["text"] and \
                    (v.get("x"), v.get("y")) == (wanted["x"], wanted["y"]):
                keep = i
        for i, v in reversed(ours_rows):
            if i != keep:
                ltext = jsonrows.remove_item(ltext, ["labels"], i)
        if wanted is not None and keep is None:
            ltext = jsonrows.append_item(ltext, ["labels"], label_row(wanted))
        put(P.labels, ltext)
    # the square
    ctext = read_text(P.cells)
    if ctext is not None or (cell and mp.get("square")):
        ctext = ctext or '{\n "paint": {}\n}\n'
        cdoc = json.loads(ctext)
        paint = cdoc.get("paint") or {}
        for k in list(paint):
            if k in old_cells and k != cell:
                ctext = jsonrows.delete_key(ctext, ["paint", k])
        if cell and mp.get("square"):
            rec = {"colour": mp["square"],
                   "why": _why(mp.get("square_why"), "DESIGNED (%s, %s): квадрат места «%s» (%d) на его клетке."
                               % (today(), author, title, loc_id))}
            old = (json.loads(ctext).get("paint") or {}).get(cell)
            if old is None or old.get("colour") != rec["colour"]:
                if "paint" not in json.loads(ctext):
                    ctext = jsonrows.set_key(ctext, ["paint"], {})
                ctext = jsonrows.set_key(ctext, ["paint", cell], rec)
        elif cell and (json.loads(ctext).get("paint") or {}).get(cell) is not None:
            ctext = jsonrows.delete_key(ctext, ["paint", cell])
        put(P.cells, ctext)
    return out


def label_row(row):
    """A data/map_labels.json row as the file lays its rows out: the cell,
    the text and add on the first line, why on the next."""
    head = json.dumps({k: row[k] for k in ("x", "y", "text", "add")}, ensure_ascii=False)
    return head[:-1] + ",\n   %s: %s}" % (json.dumps("why"), json.dumps(row["why"], ensure_ascii=False))


def placer_sig(xml):
    """What of a location file data/place_settlements.py weighs: its title,
    fn, war, dir, background and library, sides and the creatures of its
    <mobs>."""
    if xml is None:
        return None
    m = L.load(xml)
    a = m["attrs"]
    return [a.get("title", ""), a.get("fn", ""), a.get("war", ""), a.get("dir", ""), a.get("bg", ""),
            a.get("library", ""), sorted({L.SIDES.get(e, e) for _x, _y, e in m["lists"]["outzones"]}),
            sorted(t for _x, _y, t in L.mob_slots(m) if t)]


def needs_placer(loc_id, plan):
    """Whether a save changes what the map's recount weighs: this place's
    file in the ways placer_sig reads, or the verified cells."""
    path = P.xml(loc_id)
    if path in plan and placer_sig(plan[path]) != placer_sig(read_bytes(path)):
        return True
    return P.verified in plan


# --- L3: the server's own checks on the candidate data/ ------------------------------------------

L3_SCRIPT = r'''
import ast, json, os, re, sys, time, traceback
tree = sys.argv[1]
job = json.loads(sys.argv[2])
sys.path[:0] = [os.path.join(tree, "server"), os.path.join(tree, "data")]
OUT = {"problems": [], "notes": [], "placer": None, "seconds": {}}


def problem(text, cells=(), loc=None, what="server", level="error"):
    OUT["problems"].append({"level": level, "what": what, "text": text,
                            "cells": [[int(c[0]), int(c[1])] for c in cells], "loc": loc})


def step(name, fn):
    t = time.time()
    try:
        return fn()
    except Exception as exc:
        problem("%s: %s: %s" % (name, type(exc).__name__, exc), what=name)
        OUT["notes"].append(traceback.format_exc()[-3000:])
        return None
    finally:
        OUT["seconds"][name] = round(time.time() - t, 2)


import world
import travel
mt = world.mob_types()
LOC = int(job["id"])


def xy(loc, c):
    return [c % loc.width, c // loc.width]


def location():
    loc = world.Location(LOC)
    if not [c for c in loc.entries if c not in loc.obstacles]:
        problem("сервер: у места нет свободной клетки входа", what="entry")
    return loc


loc = step("location", location)


def placements():
    import rooms
    for line in rooms.placement_problems(mt):
        m = re.match(r"loc (\d+): (\d+) on (\d+),(\d+): ", line)
        problem("жители, data/placements.json: " + line,
                [(int(m.group(3)), int(m.group(4)))] if m else (),
                int(m.group(1)) if m else None, "placements")


step("placements", placements)


def events_():
    import events
    for line in events.table().problems(mt):
        problem("расписание, data/schedule.json: " + line, what="events")


step("events", events_)


def holdings_():
    import holdings
    for line in holdings.problems():
        problem("склады, data/holdings.json: " + line, what="holdings")


step("holdings", holdings_)


def ways():
    if loc is None:
        return
    gx, gy = world.cell_of(LOC) or tuple(job.get("cell_hint") or (5970, 1730))
    seen = set()
    for c, side in sorted(travel.exit_sides(loc).items()):
        if side in seen:
            continue
        seen.add(side)
        try:
            travel.plan_exit(loc, c, gx, gy)
        except travel.Refused as exc:
            # a door the model leads nowhere is the owner's to decide (L1
            # says so); one it leads somewhere must work
            level = "warning" if side in ("a", "b") and side not in job.get("doors", ()) else "error"
            problem("выход %s: сервер отвечает «%s»" % (side, exc), [xy(loc, c)], what="exit", level=level)
    for rec in job.get("walk_ins") or ():
        src = world.location(int(rec["from"]))
        x, y = rec["cell"]
        sx, sy = world.cell_of(src.id) or (gx, gy)
        try:
            ex = travel.plan_walk_in(src, y * src.width + x, sx, sy)
            if ex.loc_id != LOC:
                problem("проход из %d ведёт в %d, не сюда" % (src.id, ex.loc_id), [(x, y)], src.id, "walk_in")
        except travel.Refused as exc:
            problem("проход из %d: сервер отвечает «%s»" % (src.id, exc), [(x, y)], src.id, "walk_in")


step("ways", ways)


def starts():
    src = open(os.path.join(tree, "server", "server.py"), encoding="utf-8").read()
    m = re.search(r"^START_PLACES = (\([^=]*?\n\))", src, re.M)
    if not m:
        return
    for x, y, _w in ast.literal_eval(m.group(1)):
        i = world.location_at(x, y)
        if world.path_for(i) is None:
            problem("место старта %d,%d ведёт в %d, у которого нет файла" % (x, y, i), what="starts")


step("starts", starts)


def placer():
    import place_settlements as PS
    import test_borders as B
    data = os.path.join(tree, "data")
    previous = (PS.load_json("settlements.json", {}) or {}).get("cells", {})
    pl = PS.Placer()
    table = pl.run()
    now = {"%d,%d" % k: v for k, v in sorted(table.items())}
    want = {k: v for k, v in previous.items() if v != LOC}
    if job.get("cell"):
        want[job["cell"]] = LOC
    moved = {k: [previous.get(k), now.get(k)] for k in sorted(set(previous) | set(now))
             if previous.get(k) != now.get(k)}
    wrong = {k: v for k, v in moved.items() if want.get(k) != now.get(k)}
    missing = sorted(k for k in want if now.get(k) != want[k] and k not in wrong)
    OUT["placer"] = {"moved": moved}
    if wrong or missing:
        cells = [tuple(int(v) for v in k.split(",")) for k in list(wrong) + missing]
        problem("карта: пересчёт мест (data/place_settlements.py) сдвинул бы и другие места: %s" % "; ".join(
            "%s было %s, стало бы %s" % (k, a, b) for k, (a, b) in sorted(wrong.items())[:12]),
            cells, None, "placer")
        return
    inside, outside = B.walk_from(B.NUBIAN_VILLAGE), B.walk_from(B.START)

    def stranded(cells):
        return sorted(k for k in cells if tuple(int(v) for v in k.split(",")) not in inside
                      and tuple(int(v) for v in k.split(",")) not in outside)
    before, after = stranded(previous), stranded(now)
    if len(before) != len(after):
        problem("карта: мест, отрезанных стеной долины, стало бы %d вместо %d (data/test_borders.py и "
                "tools/known_failures.txt ждут ровно %d)" % (len(after), len(before), len(before)),
                [tuple(int(v) for v in k.split(",")) for k in sorted(set(after) ^ set(before))], None, "placer")
        return
    if moved:
        pl.write_table(os.path.join(data, "settlements.json"))
        pl.write_report(os.path.join(data, "settlements_report.md"), previous)
        OUT["placer"]["written"] = True


if job.get("placer"):
    step("placer", placer)

print("\n@@L3@@" + json.dumps(OUT, ensure_ascii=False))
'''


def _link(src, dst):
    try:
        os.symlink(src, dst)
    except OSError:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)


class Tree:
    """A data/ for the server to read, made of links to the editor's own and
    the candidate files written in: what L3 checks and the recount writes
    into. server/ is a link to the repository's, so the modules find this
    data/ by their own path."""

    WRITABLE = ("settlements.json", "settlements_report.md")

    def __init__(self, plan):
        self.dir = tempfile.mkdtemp(prefix="lava-loc-check-")
        _link(os.path.join(ROOT, "server"), os.path.join(self.dir, "server"))
        self.data = os.path.join(self.dir, "data")
        os.makedirs(self.data)
        # The editor's data/ first; what a suite's partial copy lacks, the
        # repository's.
        names = set(os.listdir(P.data)) | set(os.listdir(os.path.join(ROOT, "data")))
        for name in sorted(names):
            if name in ("locations", "__pycache__") or name in self.WRITABLE:
                continue
            src = P.d(name) if os.path.exists(P.d(name)) else os.path.join(ROOT, "data", name)
            _link(src, os.path.join(self.data, name))
        for name in self.WRITABLE:
            src = P.d(name)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(self.data, name))
        loc = os.path.join(self.data, "locations")
        static = os.path.join(loc, "static")
        os.makedirs(static)
        sdir = os.path.join(P.overlay, "static")
        for f in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else ():
            _link(os.path.join(sdir, f), os.path.join(static, f))
        if os.path.isfile(P.index):
            shutil.copyfile(P.index, os.path.join(loc, "index.json"))
        for path, data in plan.items():
            self.put(path, data)

    def path(self, path):
        """The tree's copy of one of the editor's data/ paths."""
        rel = os.path.relpath(path, P.data)
        if rel.startswith(".."):
            raise ValueError("%s is not under %s" % (path, P.data))
        return os.path.join(self.data, rel)

    def put(self, path, data):
        dst = self.path(path)
        if os.path.lexists(dst):
            os.unlink(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(data)

    def read(self, path):
        return read_bytes(self.path(path))

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def exits_sides_bytes(loc_id, xml_path):
    """data/exits_sides.json with this location's rows from its file
    (data/build_exits_sides.py row and write), or None when there is no
    table or nothing changes."""
    import build_exits_sides as B
    text = read_text(P.exits)
    if text is None:
        return None
    doc = json.loads(text)
    cells, summ, odd = B.row(loc_id, xml_path)
    if odd:
        raise Refused("коды сторон выходов, которых сервер не знает: %s" % ", ".join(sorted(odd)))
    k = str(loc_id)
    if doc["locations"].get(k) == cells and doc["summary"].get(k) == summ:
        return None
    doc["locations"][k] = cells
    doc["summary"][k] = summ
    fd, tmp = tempfile.mkstemp(prefix="exits-sides-", suffix=".json")
    os.close(fd)
    try:
        B.write(tmp, doc["locations"], doc["summary"])
        return read_bytes(tmp)
    finally:
        os.unlink(tmp)


_PLACER_MEMO = {}


def _placer_key(tree, loc_id, cell):
    h = hashlib.sha256(b"placer 1\n")
    h.update(world.RES.encode())
    h.update(read_bytes(os.path.join(ROOT, "data", "place_settlements.py")) or b"")
    for name in ("settlements_verified.json", "settlements.json", "retired.json"):
        h.update((name + "\n").encode())
        h.update(read_bytes(os.path.join(tree.data, name)) or b"")
    sdir = os.path.join(tree.data, "locations", "static")
    for f in sorted(os.listdir(sdir)):
        h.update(f.encode())
        h.update(json.dumps(placer_sig(read_bytes(os.path.join(sdir, f)))).encode())
    h.update(("%d %s" % (loc_id, cell)).encode())
    return h.hexdigest()


def run_l3(model, plan, placer=False):
    """L3 on a model's candidate files: (problems, {path: bytes} the recount
    adds to the save, seconds)."""
    loc_id = int(model["id"])
    t0 = time.time()
    tree = Tree(plan)
    try:
        xml_path = tree.path(P.xml(loc_id))
        extra = {}
        es = exits_sides_bytes(loc_id, xml_path) if os.path.exists(xml_path) else None
        if es is not None:
            extra[P.exits] = es
            tree.put(P.exits, es)
        mp = model.get("map") or {}
        cell = _key(*mp["cell"]) if mp.get("cell") is not None else None
        hint = None
        for wi in model.get("walk_ins") or ():
            try:
                hint = world.cell_of(int(wi["from"]))
            except Exception:              # noqa: BLE001
                hint = None
            if hint:
                break
        job = {"id": loc_id, "cell": cell, "cell_hint": list(hint) if hint else None,
               "doors": sorted(s for s, d in (model.get("doors") or {}).items()
                               if (d or {}).get("target") is not None),
               "walk_ins": [{"from": int(w["from"]), "cell": [int(w["cells"][0][0]), int(w["cells"][0][1])]}
                            for w in model.get("walk_ins") or () if w.get("cells")],
               "placer": False}
        cached = None
        if placer:
            pkey = _placer_key(tree, loc_id, cell)
            cached = _PLACER_MEMO.get(pkey) or _placer_from_disk(pkey)
            job["placer"] = cached is None
        env = dict(os.environ)
        env.update(LAVA_LOC_OVERLAY=os.path.join(tree.data, "locations"),
                   LAVA_PASSAGES=os.path.join(tree.data, "passages.json"),
                   LAVA_PLACEMENTS=os.path.join(tree.data, "placements.json"),
                   LAVA_SCHEDULE=os.path.join(tree.data, "schedule.json"),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        for k in ("LAVA_GX", "LAVA_GY", "LAVA_LOC", "LAVA_START"):
            env.pop(k, None)
        try:
            p = subprocess.run([sys.executable, "-c", L3_SCRIPT, tree.dir, json.dumps(job)], cwd=tree.dir,
                               env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=900)
        except subprocess.TimeoutExpired:
            return [problem("error", "server", "проверки сервера не уложились в 15 минут")], {}, time.time() - t0
        marker = p.stdout.rfind("@@L3@@")
        if marker < 0:
            tail = (p.stderr or p.stdout or "")[-1500:]
            return [problem("error", "server", "проверки сервера упали: %s" % tail)], {}, time.time() - t0
        got = json.loads(p.stdout[marker + len("@@L3@@"):].strip())
        problems = got["problems"]
        if placer:
            if cached is None:
                cached = {"problems": [x for x in problems if x["what"] == "placer"],
                          "moved": (got.get("placer") or {}).get("moved"),
                          "settlements": None, "report": None}
                if (got.get("placer") or {}).get("written"):
                    cached["settlements"] = (tree.read(P.settlements) or b"").decode("utf-8")
                    cached["report"] = (tree.read(P.report) or b"").decode("utf-8")
                _PLACER_MEMO[pkey] = cached
                _placer_to_disk(pkey, cached)
            else:
                problems = problems + cached["problems"]
            if cached.get("settlements") is not None and not cached["problems"]:
                extra[P.settlements] = cached["settlements"].encode("utf-8")
                extra[P.report] = cached["report"].encode("utf-8")
        return problems, extra, time.time() - t0
    finally:
        tree.close()


def _placer_from_disk(key):
    try:
        with open(os.path.join(CACHE, "placer", key + ".json"), encoding="utf-8") as fh:
            got = json.load(fh)
        _PLACER_MEMO[key] = got
        return got
    except (OSError, ValueError):
        return None


def _placer_to_disk(key, value):
    try:
        d = os.path.join(CACHE, "placer")
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, key + ".%d.tmp" % os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, key + ".json"))
    except OSError:
        pass


# --- check and save ------------------------------------------------------------------------------

def _clean(model):
    """A model as the page sent it, checked for its shape (400 otherwise)."""
    if not isinstance(model, dict):
        raise Refused("model: объект")
    for k in ("id", "width", "height", "attrs"):
        if k not in model:
            raise Refused("model: нет %s" % k)
    try:
        int(model["id"]), int(model["width"]), int(model["height"])
    except (TypeError, ValueError):
        raise Refused("model: id, width и height — числа")
    if not isinstance(model.get("attrs"), dict):
        raise Refused("model: attrs — объект")
    for k in ("sprites", "decals", "walls", "exits", "entries", "war_entries", "inhabitants", "walk_ins"):
        if not isinstance(model.get(k) or [], list):
            raise Refused("model: %s — список" % k)
    for k in ("doors",):
        if not isinstance(model.get(k) or {}, dict):
            raise Refused("model: %s — объект" % k)
    return model


def check(model, quick=False, author="owner"):
    """POST /api/check: L1 and L2, and L3 unless quick (or while L1 has an
    error). {problems, seconds}."""
    model = _clean(model)
    t0 = time.time()
    original = model.get("state") == "original"
    problems = lint(model, for_save=not original)
    if not quick:
        if any(p["level"] == "error" for p in problems):
            problems.append(problem("warning", "server", "проверки сервера ждут, пока не исправлены ошибки выше"))
        else:
            # an original is checked as the server has it: nothing to write
            plan = {} if original else plan_writes(model, author)
            got, _extra, _sec = run_l3(model, plan, placer=not original and needs_placer(int(model["id"]), plan))
            problems.extend(got)
    return {"problems": problems, "seconds": round(time.time() - t0, 2)}


def table_paths(loc_id):
    """Every file of data/ a save of this location reads to plan what it
    writes, or writes: whatever another writer changes in one of them
    between the plan and the write is lost unless a save looks again."""
    return [P.xml(loc_id), P.index, P.placements, P.passages, P.verified, P.labels, P.cells, P.exits,
            P.settlements, P.report]


def table_shas(loc_id):
    return {p: sha(read_bytes(p)) for p in table_paths(loc_id)}


class SaveLock:
    """One save at a time over one data/ folder, between processes too: the
    page's server, a second editor and the command line (`new`, `save`)
    each plan from the tables, check for up to a few minutes and write the
    tables whole. A lock file outside the repository (the system's temp
    folder, named by the folder's path); without fcntl (Windows) only the
    process's own lock holds."""

    def __init__(self, data):
        key = hashlib.sha256(os.path.abspath(data).encode("utf-8")).hexdigest()[:16]
        self.path = os.path.join(tempfile.gettempdir(), "lava-location-editor-%s.lock" % key)
        self.fh = None

    def __enter__(self):
        _LOCK.acquire()
        try:
            import fcntl
        except ImportError:
            return self
        try:
            self.fh = open(self.path, "a+b")
            fcntl.flock(self.fh, fcntl.LOCK_EX)
        except OSError:
            if self.fh is not None:
                self.fh.close()
            self.fh = None
        return self

    def __exit__(self, *exc):
        try:
            if self.fh is not None:
                import fcntl
                fcntl.flock(self.fh, fcntl.LOCK_UN)
                self.fh.close()
                self.fh = None
        finally:
            _LOCK.release()
        return False


def save(model, etag, author="owner"):
    """POST /api/save: (code, body)."""
    model = _clean(model)
    loc_id = int(model["id"])
    with SaveLock(P.data):
        if loc_id == 262:
            return 422, {"error": "262 «Тотем» закрыт для редактора", "problems": []}
        state = location_state(loc_id)
        if etag != etag_of(state) or (model.get("state") == "new" and loc_id in origin_main_ids()):
            body = {"error": "локация %d изменилась на диске после того, как её открыли: откройте её снова" % loc_id}
            if model.get("state") == "new":
                body["error"] = ("номер %d тем временем занят (здесь или в origin/main) или у него появились строки "
                                 "в таблицах: сделайте новое место ещё раз" % loc_id)
                try:
                    body["next_id"] = next_free_id()
                except Refused:
                    pass
            return 409, body
        if model.get("state") == "original" or (not is_ours(loc_id) and model.get("state") != "new"):
            return 422, {"error": "локация оригинала только читается: сделайте копию",
                         "problems": [problem("error", "id", "%d — оригинал" % loc_id)]}
        problems = lint(model)
        errors = [p for p in problems if p["level"] == "error"]
        if errors:
            return 422, {"error": "есть ошибки: %d" % len(errors), "problems": problems}
        # what the plan is made from: written over only if nobody (git,
        # another session without this lock) changed it meanwhile
        read = table_shas(loc_id)
        plan = plan_writes(model, author)
        if not plan:
            return 200, {"id": loc_id, "written": [], "model": load_model(loc_id), "problems": problems}
        got, extra, seconds = run_l3(model, plan, placer=needs_placer(loc_id, plan))
        problems.extend(got)
        errors = [p for p in got if p["level"] == "error"]
        if errors:
            return 422, {"error": "сервер не примет это место: %d" % len(errors), "problems": problems,
                         "seconds": round(seconds, 1)}
        plan.update(extra)
        moved = sorted(P.rel(p) for p, h in table_shas(loc_id).items() if read.get(p) != h)
        if moved or etag_of(location_state(loc_id)) != etag:
            return 409, {"error": "пока шла проверка, на диске поменялись %s: откройте локацию снова"
                         % (", ".join(moved) if moved else "строки локации %d" % loc_id),
                         "changed": moved}
        order = sorted(plan, key=lambda p: (p != P.xml(loc_id), p))
        for path in order:
            write_atomic(path, plan[path])
        world._CACHE.pop(loc_id, None)
        forget("locations")
        written = [P.rel(p) for p in sorted(plan)]
        return 200, {"id": loc_id, "written": written, "model": load_model(loc_id),
                     "problems": [p for p in problems if p["level"] != "error"], "seconds": round(seconds, 1)}


# --- the list -------------------------------------------------------------------------------------

_ATTR = re.compile(r'(\w+)="([^"]*)"')


def _scan_file(path):
    raw = read_bytes(path)
    if raw is None:
        return None
    txt = raw.decode("utf-8", "replace")
    m = re.search(r"<location([^>]*)>", txt)
    attrs = dict(_ATTR.findall(m.group(1))) if m else {}
    mobs = re.search(r"<mobs>([^<]*)</mobs>", txt)
    s = "".join((mobs.group(1) if mobs else "").split())
    typed = sum(1 for i in range(0, len(s) - 7, 8) if int(s[i + 4:i + 8] or "0", 16))
    oz = re.search(r"<outzones>([^<]*)</outzones>", txt)
    o = "".join((oz.group(1) if oz else "").split())
    sides = sorted({L.SIDES.get(o[i + 4], o[i + 4]) for i in range(0, len(o) - 4, 5)},
                   key=lambda s: "WNESab".index(s) if s in "WNESab" else 9)
    return {"title": L.unescape(attrs.get("title", "")), "fn": attrs.get("fn", ""),
            "size": [int(attrs.get("width") or 0), int(attrs.get("height") or 0)],
            "library": attrs.get("library", ""), "war": attrs.get("war", "0"), "pvp": attrs.get("pvp", "1"),
            "spawns": typed, "sides": sides}


def _originals():
    """The original's files, scanned once and kept on disk."""
    def build():
        key = hashlib.sha256(("list1" + world.RES + _usage_key()).encode()).hexdigest()[:20]
        path = os.path.join(CACHE, "list-%s.json" % key)
        try:
            with open(path, encoding="utf-8") as fh:
                return {int(k): v for k, v in json.load(fh).items()}
        except (OSError, ValueError):
            pass
        out = {}
        for i in sorted(base_ids()):
            p = original_path(i)
            if p:
                row = _scan_file(p)
                if row:
                    out[i] = row
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(out, fh, ensure_ascii=False)
            os.replace(path + ".tmp", path)
        except OSError:
            pass
        return out
    return memo("originals", build)


def locations():
    """GET /api/locations."""
    def build():
        rows = dict(_originals())
        idx = index_doc().get("locations") or {}
        ours = set(ours_ids())
        for i in ours:
            row = _scan_file(P.xml(i))
            if row:
                rows[i] = row
        cells = {}
        for c, i in sorted(settlements_table().items()):
            cells.setdefault(i, list(c))
        placed = collections.Counter({int(k): len(v or ()) for k, v in
                                      (placements_doc().get("locations") or {}).items()
                                      if str(k).isdigit() and int(k) < world.NEW_ID_LIMIT})
        out = []
        for i in sorted(rows):
            r = rows[i]
            out.append({"id": i, "title": r["title"], "fn": r["fn"], "size": r["size"], "library": r["library"],
                        "war": r["war"], "pvp": r["pvp"], "state": "ours" if i in ours else "original",
                        "cell": cells.get(i), "from": (idx.get(str(i)) or {}).get("from") if i in ours else None,
                        "inhabitants": r["spawns"] + placed.get(i, 0), "doors": [s for s in r["sides"] if s in "ab"],
                        "sides": r["sides"], "closed": i == 262})
        return out
    return memo("locations", build)


# --- creatures, the map ----------------------------------------------------------------------------

def mobs_search(q="", limit=50):
    q = (q or "").strip().lower()
    out = []
    for c in creatures():
        if q:
            hay = "%d %s %s %s" % (c["type"], c["name"].lower(), c["sub"].lower(), c["internal"].lower())
            if q not in hay:
                continue
        row = {k: c[k] for k in ("type", "name", "sub", "level", "root", "role", "known", "retired")}
        row["icon"] = "/api/mobicon/%d.webp" % c["type"]
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _bits(test):
    X, Y = world.MAP_X, world.MAP_Y
    w = X[1] - X[0] + 1
    bits = bytearray((w * (Y[1] - Y[0] + 1) + 7) // 8)
    n = 0
    for y in range(Y[0], Y[1] + 1):
        for x in range(X[0], X[1] + 1):
            if test(x, y):
                bits[n >> 3] |= 0x80 >> (n & 7)
            n += 1
    return base64.b64encode(bytes(bits)).decode()


def map_tile(n):
    """A tile of the global map: the release's bytes (client/files, the
    store, a client with the original's), else whatever a client's res
    has under that name -- a launcher-updated one holds the release's
    repainted tiles (server/map_cells.py), whose sha the original's list
    does not know. Only for looking at."""
    import map_cells
    path = map_cells.tile_path(int(n))
    data = art().read(path)
    if data is not None:
        return data
    for d in list(art().res_dirs) + [world.RES]:
        data = read_bytes(os.path.join(d, *path.split("/")))
        if data is not None:
            return data
    return None


def map_info():
    """GET /api/map."""
    X, Y = world.MAP_X, world.MAP_Y
    import map_cells
    import map_labels
    tiles = []
    for ty in range(Y[0] * 8 // 256, Y[1] * 8 // 256 + 1):
        for tx in range(X[0] * 8 // 256, X[1] * 8 // 256 + 1):
            n = ty * map_cells.ROW + tx
            if art().entry(map_cells.tile_path(n)) is not None:
                tiles.append({"n": n, "x": tx * 256, "y": ty * 256, "url": "/api/map/tile/%d.jpg" % n})
    table = settlements_table()
    titles = {}
    for r in locations():
        titles[r["id"]] = r["title"]
    labels = []
    raw = read_bytes(os.path.join(world.RES, "database", "locations.xml"))
    if raw is not None:
        try:
            edited, _n = map_labels.apply(raw, map_labels.load(P.labels))
        except (ValueError, KeyError):
            edited = raw
        import html
        for m in map_labels.ROW.finditer(edited):
            a = {k.decode(): v for k, v in map_labels.ATTR.findall(m.group(0))}
            try:
                labels.append([int(a["x"]), int(a["y"]), html.unescape(a["text"].decode("utf-8", "replace"))])
            except (KeyError, ValueError):
                continue
    blocked = memo("blocked", lambda: _bits(lambda x, y: not world.passable(x, y)))
    try:
        inside, outside = walks()
        reachable = memo("reachable", lambda: _bits(lambda x, y: (x, y) in inside or (x, y) in outside))
    except Exception:                      # noqa: BLE001
        reachable = None
    starts = []
    try:
        src = read_text(os.path.join(ROOT, "server", "server.py")) or ""
        m = re.search(r"^START_PLACES = (\([^=]*?\n\))", src, re.M)
        starts = [[x, y] for x, y, _w in ast.literal_eval(m.group(1))] if m else []
    except (ValueError, SyntaxError):
        pass
    return {"bounds": {"x": list(X), "y": list(Y)}, "cell": map_cells.CELL, "tile": map_cells.TILE,
            "tiles": tiles, "settlements": {_key(*c): i for c, i in sorted(table.items())},
            "titles": {str(i): titles.get(i, "") for i in sorted(set(table.values()))},
            "ours": {str(i): c for i, c in ((r["id"], r["cell"]) for r in locations() if r["state"] == "ours")},
            "retired": {_key(*c): i for c, i in sorted(retired_cells().items())},
            "cut": {_key(*c): why for c, why in sorted(cut_cells().items())},
            "patrols": {_key(*c): i for c, i in sorted(patrol_cells().items())},
            "labels": labels, "starts": starts, "blocked": blocked, "reachable": reachable,
            "colours": sorted(map_cells.PALETTE)}


# --- the owner's objects ----------------------------------------------------------------------------

def used_in(oid):
    """The locations of ours that place an object (any case), by id."""
    out = []
    low = oid.lower()
    for i in ours_ids():
        try:
            m = L.load(P.xml(i))
        except (ValueError, OSError):
            continue
        ids = [s["id"] for s in m["sprites"]] + [d["id"] for d in m["bgdecorations"]]
        if m.get("background"):
            ids.append(m["background"].get("id", ""))
        if any(str(x).lower() == low for x in ids):
            out.append(i)
    return out


def objects_info():
    """GET /api/objects."""
    out = {}
    for oid, e in sorted(objects_raw().items()):
        row = dict(e)
        try:
            CO.check_entry(oid, e)
            row["problem"] = None
        except CO.Refused as exc:
            row["problem"] = str(exc)
        frames = e.get("frames") if isinstance(e.get("frames"), list) else []
        row["pictures"] = ["/api/object/%s/%s" % (oid, f) for f in frames if isinstance(f, str)]
        row["used_in"] = used_in(oid)
        out[oid] = row
    return {"objects": out}


def _taken_paths():
    paths = []
    for name in ("base.txt", "extra.txt"):
        p = os.path.join(ROOT, "client", name)
        if os.path.isfile(p):
            paths += CO.base_paths(p)
    return {p.lower() for p in paths}


def _object_id(title, raw, wanted=None):
    taken = _taken_paths()

    def free(oid):
        return oid not in raw and CO.ID.fullmatch(oid) and \
            not any(p.lower() in taken for p in CO._clash_names(oid))
    if wanted:
        if not CO.ID.fullmatch(wanted):
            raise Refused("id объекта: c_ и дальше 1..40 знаков a-z 0-9 _")
        if wanted in raw:
            raise Refused("объект %s уже есть" % wanted)
        if not free(wanted):
            raise Refused("%s совпал бы с файлом оригинальной игры" % wanted)
        return wanted
    base = ("c_" + "_".join(slug_words(title)))[:40].rstrip("_")
    if base == "c":
        base = "c_obj"
    oid, n = base, 1
    while not free(oid):
        n += 1
        oid = "%s_%d" % (base[:40 - len(str(n)) - 1], n)
    return oid


Size = collections.namedtuple("Size", "w h")

# What a browser reads from a picture and Flash never does: the gamma, the
# colour profile and the rotation of a PNG. The browser draws such a picture
# colour-managed (a gAMA of 1.0 lightens (128, 64, 200) to (188, 137, 229)),
# while swfgen carries the samples as they are; taken out on upload, the
# editor shows what the game will.
PNG_COLOUR_CHUNKS = {b"gAMA", b"cHRM", b"iCCP", b"sRGB", b"eXIf"}


def plain_picture(data):
    """A PNG's bytes without PNG_COLOUR_CHUNKS, a JPEG's without its ICC
    profile (APP2 ICC_PROFILE); anything else, or a file that does not walk
    as one, as it came (swfgen says what is wrong with it)."""
    if data[:8] == swfgen.PNG_SIG:
        out, pos = [data[:8]], 8
        while pos + 12 <= len(data):
            ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
            end = pos + 12 + ln
            if end > len(data):
                return data
            if typ not in PNG_COLOUR_CHUNKS:
                out.append(data[pos:end])
            pos = end
            if typ == b"IEND":
                break
        out.append(data[pos:])
        return b"".join(out)
    if data[:2] == b"\xff\xd8":
        out, pos = [data[:2]], 2
        while pos + 4 <= len(data) and data[pos] == 0xFF:
            m = data[pos + 1]
            if m == 0xDA or not (0xE0 <= m <= 0xFE or m in (0xC4, 0xDB, 0xDD) or 0xC0 <= m <= 0xCF):
                break
            ln = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            end = pos + 2 + ln
            if end > len(data):
                return data
            if not (m == 0xE2 and data[pos + 4:pos + 16] == b"ICC_PROFILE\x00"):
                out.append(data[pos:end])
            pos = end
        out.append(data[pos:])
        return b"".join(out)
    return data


def _decode_frames(frames):
    """[(bytes, ext, Size)] of base64 pictures, checked from their headers
    as the release build checks them (swfgen: PNG not interlaced, baseline
    JPEG not rotated by EXIF, sides up to 2880, one size for all), their
    colour chunks taken out (plain_picture). Nothing is decoded here: the
    build in _write_object does that, a picture at a time, within
    custom_objects' pixel budget."""
    if not isinstance(frames, list) or not 1 <= len(frames) <= CO.MAX_FRAMES:
        raise Refused("frames: от 1 до %d картинок" % CO.MAX_FRAMES)
    out = []
    for i, f in enumerate(frames):
        if not isinstance(f, str):
            raise Refused("картинка %d: строка base64" % (i + 1))
        if f.startswith("data:"):
            f = f.split(",", 1)[-1]
        try:
            data = base64.b64decode(f, validate=True)
        except (ValueError, base64.binascii.Error):
            raise Refused("картинка %d: не base64" % (i + 1))
        if len(data) > CO.MAX_PICTURE_BYTES:
            raise Refused("картинка %d: %d байт, больше %d" % (i + 1, len(data), CO.MAX_PICTURE_BYTES))
        data = plain_picture(data)
        try:
            w, h = swfgen.picture_size(data)
            if data[:8] == swfgen.PNG_SIG and swfgen.png_header(data)[4]:
                raise swfgen.Refused("PNG: interlaced; save it without interlacing")
        except swfgen.Refused as exc:
            raise Refused("картинка %d: %s" % (i + 1, ru_refusal(str(exc))))
        out.append((data, ".png" if data[:8] == swfgen.PNG_SIG else ".jpg", Size(w, h)))
    sizes = sorted({(p.w, p.h) for _d, _e, p in out})
    if len(sizes) > 1:
        raise Refused("все картинки анимации одного размера: %s" % ", ".join("%dx%d" % s for s in sizes))
    return out


def _cells_arg(v, what):
    if v is None:
        return None
    if not isinstance(v, list) or not all(isinstance(c, list) and len(c) == 2 and
                                          all(type(n) is int for n in c) for c in v):
        raise Refused("%s: [[dx, dy], ...]" % what)
    return [list(c) for c in v]


def _write_object(oid, entry, pictures, raw):
    """Write an object's pictures and its manifest row, checked the way the
    build checks them; everything put back as it was on a refusal."""
    d = os.path.join(P.objects, oid)
    man = os.path.join(P.objects, CO.MANIFEST)
    old_man = read_bytes(man)
    old_files = {}
    if os.path.isdir(d):
        for n in os.listdir(d):
            old_files[n] = read_bytes(os.path.join(d, n))
    try:
        if pictures is not None:
            names = {}
            frames = []
            for data, ext, _pic in pictures:
                h = sha(data)
                if h not in names:
                    names[h] = "%d%s" % (len(names), ext)
                frames.append(names[h])
            entry["frames"] = frames
            os.makedirs(d, exist_ok=True)
            for n in os.listdir(d):
                os.unlink(os.path.join(d, n))
            for data, _ext, _pic in pictures:
                write_atomic(os.path.join(d, names[sha(data)]), data)
        raw = dict(raw)
        raw[oid] = {k: entry[k] for k in CO.KEY_ORDER if entry.get(k) is not None}
        checked = CO.check_entry(oid, raw[oid])
        write_atomic(man, CO.manifest_text(raw).encode("utf-8"))
        # the sizes and the pixel budget from the headers first, then the
        # build itself, as the release makes it (a picture at a time)
        CO.check_tree(P.objects, CO.load(P.objects))
        pics = CO.read_pictures(P.objects, oid, checked)
        swfgen.sprite_swf(pics, fps=checked["fps"], keys=checked["frames"])
    except (CO.Refused, swfgen.Refused, OSError) as exc:
        if old_man is None:
            if os.path.exists(man):
                os.unlink(man)
        else:
            write_atomic(man, old_man)
        if os.path.isdir(d):
            shutil.rmtree(d)
        if old_files:
            os.makedirs(d, exist_ok=True)
            for n, data in old_files.items():
                write_atomic(os.path.join(d, n), data)
        raise Refused(ru_refusal(str(exc)))
    _ART_RESET()
    forget("locations")
    return raw[oid]


def object_upload(body):
    """POST /api/object."""
    with _LOCK:
        raw = objects_raw()
        title = str(body.get("title") or "").strip()
        if not title:
            raise Refused("нужно название объекта (title)")
        oid = _object_id(title, raw, body.get("id"))
        pictures = _decode_frames(body.get("frames"))
        w, h = pictures[0][2].w, pictures[0][2].h
        kind = body.get("kind") or "sprite"
        entry = {"title": title, "fps": body.get("fps"), "kind": kind if kind != "sprite" else None,
                 "note": body.get("note")}
        if len(pictures) > 1 and entry["fps"] is None:
            raise Refused("анимации нужна скорость fps, 1..%d" % swfgen.HOST_FPS)
        if kind != "background":
            anchor = body.get("anchor")
            if anchor is None:
                anchor = [w // 2, h - 1]
            entry["anchor"] = anchor
            entry["front"] = _cells_arg(body.get("front"), "front") or [[0, 0]]
            entry["footprint"] = _cells_arg(body.get("footprint"), "footprint") or []
        total = sum(len(p[0]) for p in pictures)
        for o, e in raw.items():
            for f in (e.get("frames") or ()) if isinstance(e, dict) else ():
                p = os.path.join(P.objects, o, f)
                if os.path.isfile(p):
                    total += os.path.getsize(p)
        if total > CO.MAX_TOTAL_BYTES:
            raise Refused("в client/objects стало бы %d байт картинок, больше %d: крупное — в хранилище "
                          "и client/extra.txt" % (total, CO.MAX_TOTAL_BYTES))
        written = _write_object(oid, entry, pictures, raw)
        return {"id": oid, "entry": written}


def object_update(body):
    """POST /api/object/update."""
    with _LOCK:
        raw = objects_raw()
        oid = str(body.get("id") or "")
        if oid not in raw:
            raise Refused("нет объекта %s" % oid)
        entry = dict(raw[oid])
        users = used_in(oid)
        for k in ("anchor", "front", "footprint", "kind"):
            if k in body and body[k] != entry.get(k) and users:
                raise Conflict("объект стоит в локациях %s: якорь, линия глубины, след и вид меняются только у "
                               "объекта, который нигде не стоит" % ", ".join(map(str, users)), {"used_in": users})
        for k in ("title", "fps", "note"):
            if k in body:
                entry[k] = body[k]
        for k in ("front", "footprint"):
            if k in body:
                entry[k] = _cells_arg(body[k], k)
        if "anchor" in body:
            entry["anchor"] = body["anchor"]
        if "kind" in body:
            entry["kind"] = body["kind"]
        pictures = _decode_frames(body["frames"]) if body.get("frames") is not None else None
        written = _write_object(oid, entry, pictures, raw)
        return {"id": oid, "entry": written}


def object_delete(body):
    """POST /api/object/delete."""
    with _LOCK:
        raw = objects_raw()
        oid = str(body.get("id") or "")
        if oid not in raw:
            raise Refused("нет объекта %s" % oid)
        users = used_in(oid)
        if users:
            raise Conflict("объект стоит в локациях %s: сначала уберите его оттуда" % ", ".join(map(str, users)),
                           {"used_in": users})
        raw = dict(raw)
        del raw[oid]
        write_atomic(os.path.join(P.objects, CO.MANIFEST), CO.manifest_text(raw).encode("utf-8"))
        d = os.path.join(P.objects, oid)
        if os.path.isdir(d):
            shutil.rmtree(d)
        _ART_RESET()
        return {"id": oid, "deleted": True}


def info():
    """GET /api/info."""
    import map_cells
    return {"mode": "local", "data": P.data, "objects": P.objects, "res": world.RES,
            "res_original": res_original(), "pictures": have_pictures(), "origin_main": dict(GIT),
            "first_new_id": world.FIRST_NEW_ID, "id_limit": world.NEW_ID_LIMIT,
            "sizes": [list(s) for s in L.SIZES], "tracks": tracks(), "codes": OBSTACLE_CODES,
            "sides": {"W": "запад", "N": "север", "E": "восток", "S": "юг", "a": "дверь a", "b": "дверь b"},
            "edge_band": EDGE_BAND, "colours": sorted(map_cells.PALETTE), "layers": list(A.LAYERS),
            "cell": {"w": L.CELL_W, "h": L.ROW_H, "hex": [list(p) for p in L.HEX]},
            "today": today()}


# --- the page ---------------------------------------------------------------------------------------

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
         ".json": "application/json; charset=utf-8", ".woff2": "font/woff2", ".webp": "image/webp",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

FALLBACK = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Редактор локаций</title>
<style>body{font:15px/1.5 system-ui,sans-serif;margin:24px;max-width:860px;background:#15130f;color:#e8e1d3}
code,pre{font-family:ui-monospace,monospace;font-size:13px}a{color:#e0a85a}</style></head><body>
<h1>Редактор локаций</h1><p>Страница редактора ещё не собрана
(<code>tools/location_editor_ui/static</code>). Сервер и его API работают:
<a href="/api/info">/api/info</a>, <a href="/api/locations">/api/locations</a>,
<a href="/api/map">/api/map</a>, <a href="/api/objects">/api/objects</a>.
Описание API — в начале <code>tools/location_editor.py</code>.</p></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "LavaLocationEditor/1"

    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200, cache=False):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=31536000, immutable" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, base, rel, cache=False):
        path = os.path.normpath(os.path.join(base, rel))
        if not path.startswith(os.path.normpath(base) + os.sep) or not os.path.isfile(path):
            return self._send({"error": "not found"}, code=404)
        with open(path, "rb") as fh:
            data = fh.read()
        self._send(data, TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), cache=cache)

    def _local_only(self):
        """Only under a loopback name (or the --host it was given): a page of
        another site that rebinds its own name to 127.0.0.1 gets nothing.
        True when the request was refused."""
        port = self.server.server_address[1]
        names = {"127.0.0.1", "localhost", "[::1]"}
        bound = getattr(self.server, "bound_host", "")
        if bound and bound not in ("0.0.0.0", "::"):
            names.add(bound.lower())
        if (self.headers.get("Host") or "").strip().lower() in {"%s:%d" % (n, port) for n in names}:
            return False
        self._send({"error": "Редактор отвечает только по адресу http://127.0.0.1:%d/ "
                             "или http://localhost:%d/" % (port, port)}, code=403)
        return True

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64 << 20:
            raise ValueError("too big")
        raw = self.rfile.read(n) if n > 0 else b""
        return raw, (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()

    def _query(self):
        from urllib.parse import parse_qs
        q = self.path.split("?", 1)[1] if "?" in self.path else ""
        return {k: v[-1] for k, v in parse_qs(q).items()}

    def _guard(self, fn):
        try:
            return fn()
        except Refused as exc:
            return self._send({"error": str(exc)}, code=400)
        except Conflict as exc:
            return self._send(dict(exc.extra, error=str(exc)), code=409)
        except NotFound as exc:
            return self._send({"error": str(exc)}, code=404)
        except (BrokenPipeError, ConnectionResetError):
            # the page went away before its answer (it moved on while a
            # picture was drawn): there is nobody to tell
            return None
        except (Exception, SystemExit) as exc:  # noqa: BLE001 -- the page gets the reason, the log the trace
            # SystemExit too: client/build.py's readers stop a build with it
            # (a client/base.txt that does not read), and uncaught it would
            # end this request's thread with no answer and no line in the log
            traceback.print_exc()
            return self._send({"error": "%s: %s" % (type(exc).__name__, exc)}, code=500)

    def do_GET(self):
        if self._local_only():
            return
        self._guard(self._get)

    def _get(self):
        url = self.path.split("?", 1)[0]
        q = self._query()
        if url == "/health":
            return self._send(b"ok", "text/plain; charset=utf-8")
        if url in ("/", "/index.html"):
            if os.path.isfile(os.path.join(UI, "index.html")):
                return self._file(UI, "index.html")
            return self._send(FALLBACK.encode("utf-8"), "text/html; charset=utf-8")
        if url.startswith("/assets/"):
            return self._file(UI, url[1:])
        if url == "/api/info":
            return self._send(info())
        if url == "/api/locations":
            return self._send({"locations": locations()})
        m = re.fullmatch(r"/api/location/(\d+)", url)
        if m:
            return self._send(load_model(int(m.group(1))))
        m = re.fullmatch(r"/api/render/(\d+)\.png", url)
        if m:
            png, _rep = render_png(load_model(int(m.group(1))), q.get("layers") or "art",
                                   _scale(q.get("scale")), q.get("order") or "reverse")
            return self._send(png, "image/png")
        m = re.fullmatch(r"/api/palette/(\d+)", url)
        if m:
            return self._send(palette(load_model(int(m.group(1)))["attrs"].get("library", "")))
        if url == "/api/palette":
            return self._send(palette(q.get("library") or ""))
        m = re.fullmatch(r"/art/([0-9a-f]{64})/([A-Za-z0-9_.-]{1,80})", url)
        if m:
            f = art().cache_file(m.group(1), m.group(2))
            if f is None:
                return self._send({"error": "not found"}, code=404)
            return self._file(os.path.dirname(f), os.path.basename(f), cache=True)
        if url == "/api/mobs":
            try:
                limit = max(1, min(500, int(q.get("limit") or 50)))
            except ValueError:
                limit = 50
            return self._send({"mobs": mobs_search(q.get("q") or "", limit)})
        m = re.fullmatch(r"/api/mobicon/(\d+)\.webp", url)
        if m:
            if not have_pictures():
                return self._send({"error": "картинки рисует Pillow с numpy"}, code=404)
            f, _ph = art().mob_icon(int(m.group(1)))
            return self._file(os.path.dirname(f), os.path.basename(f))
        if url == "/api/map":
            return self._send(map_info())
        m = re.fullmatch(r"/api/map/tile/(\d+)\.jpg", url)
        if m:
            data = map_tile(int(m.group(1)))
            if data is None:
                return self._send({"error": "нет такой плитки"}, code=404)
            return self._send(data, "image/jpeg")
        if url == "/api/objects":
            return self._send(objects_info())
        m = re.fullmatch(r"/api/object/(c_[a-z0-9_]{1,40})/([a-z0-9_-]{1,40}\.(?:png|jpg|jpeg))", url)
        if m:
            return self._file(os.path.join(P.objects, m.group(1)), m.group(2))
        return self._send({"error": "not found"}, code=404)

    def do_POST(self):
        try:
            raw, ctype = self._body()
        except ValueError:
            return self._send({"error": "bad Content-Length"}, code=400)
        if self._local_only():
            return
        # JSON only: anything else is what another site may send here without
        # asking first (a CORS "simple" request); for JSON the browser asks
        # first (OPTIONS), and nothing here answers that.
        if ctype != "application/json":
            return self._send({"error": "a JSON body only (Content-Type: application/json)"}, code=415)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            return self._send({"error": "bad json"}, code=400)
        if not isinstance(body, dict):
            return self._send({"error": "bad json"}, code=400)
        self._guard(lambda: self._post(body))

    def _post(self, body):
        url = self.path.split("?", 1)[0]
        if url == "/api/new":
            return self._send(new_model(body.get("title"), body.get("from"), body.get("empty"),
                                        body.get("why") or "", new_id=body.get("id")))
        if url == "/api/edit":
            model, inf = edit(_clean(body.get("model")), body.get("op") or {})
            return self._send(dict(inf, model=model))
        if url == "/api/check":
            return self._send(check(body.get("model"), bool(body.get("quick"))))
        if url == "/api/save":
            code, out = save(body.get("model"), str(body.get("etag") or ""))
            return self._send(out, code=code)
        if url == "/api/render":
            png, _rep = render_png(_clean(body.get("model")), body.get("layers") or "art",
                                   _scale(body.get("scale")), body.get("order") or "reverse")
            return self._send(png, "image/png")
        if url == "/api/object":
            return self._send(object_upload(body))
        if url == "/api/object/update":
            return self._send(object_update(body))
        if url == "/api/object/delete":
            return self._send(object_delete(body))
        return self._send({"error": "not found"}, code=404)


def _scale(v):
    try:
        return float(v) if v not in (None, "") else 1.0
    except (TypeError, ValueError):
        raise Refused("scale: число 0.05..2")


def serve(port=PORT, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    srv.bound_host = host
    return srv


def warm():
    """What the page asks for first, read in the background."""
    _background("names", creatures)
    _background("list", locations)
    _background("usage", lambda: usage(True))


# --- command line --------------------------------------------------------------------------------------

def _model_arg(ref):
    """A model from an id or from a JSON file (`show`'s output)."""
    if os.path.isfile(ref):
        with open(ref, encoding="utf-8") as fh:
            got = json.load(fh)
        return got.get("model", got)
    return load_model(int(ref))


def _parse_walk_in(spec):
    try:
        loc, cells = spec.split(":", 1)
        return {"from": int(loc), "cells": [[int(v) for v in part.split(",")] for part in cells.split(";")]}
    except ValueError:
        raise Refused("--walk-in: LOC:X,Y[;X,Y...], не %r" % spec)


def _print_problems(problems):
    for p in problems:
        where = (" @ " + " ".join("%d:%d" % tuple(c) for c in p["cells"][:8])) if p["cells"] else ""
        loc = " [в %s]" % p["loc"] if p.get("loc") is not None else ""
        print("%-7s %-12s %s%s%s" % (p["level"], p["what"], p["text"], loc, where))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", help="the data/ folder (default: the repository's)")
    ap.add_argument("--objects", help="the objects folder (default: client/objects)")
    ap.add_argument("--port", type=int, default=PORT, help="serve: the port (LAVA_LOCATION_EDITOR_PORT, 8096)")
    ap.add_argument("--host", default="127.0.0.1", help="serve: the address to answer on")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("serve", help="the page and its API (the default)")
    p.add_argument("--port", type=int, default=argparse.SUPPRESS)
    p.add_argument("--host", default=argparse.SUPPRESS)
    p = sub.add_parser("new", help="make a place and save it")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from", dest="src", type=int, help="the location to copy")
    g.add_argument("--empty", help="WxH: 64x128 or 32x64")
    p.add_argument("--library", default="Desert")
    p.add_argument("--title", required=True)
    p.add_argument("--why", required=True, help="the owner's word: why the place is there")
    p.add_argument("--id", type=int)
    p.add_argument("--author", default="owner")
    p.add_argument("--walk-in", action="append", default=[], help="LOC:X,Y[;X,Y...]")
    p.add_argument("--door", action="append", default=[], help="a|b[=ID]: back to the walk-in's LOC, or to ID")
    p = sub.add_parser("show", help="print a location's model")
    p.add_argument("ref")
    p = sub.add_parser("check", help="the checks of a location or a model file")
    p.add_argument("ref")
    p.add_argument("--quick", action="store_true", help="L1 and L2 only")
    p = sub.add_parser("render", help="draw a location or a model file")
    p.add_argument("ref")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--layers", default="art")
    p.add_argument("--scale", type=float, default=1.0)
    p = sub.add_parser("save", help="save a model file")
    p.add_argument("file")
    p.add_argument("--etag", help="default: the model's own")
    p.add_argument("--author", default="owner")
    a = ap.parse_args(argv)
    configure(a.data, a.objects)
    cmd = a.cmd or "serve"
    try:
        if cmd == "serve":
            srv = serve(a.port, a.host)
            url = "http://%s:%d/" % (srv.bound_host, srv.server_address[1])
            print("location editor on %s (data: %s, RES: %s%s); Ctrl+C to stop"
                  % (url, P.data, world.RES, "" if res_original() else
                     "; its 262.xml differs from client/base.txt: the map's recount may move places"),
                  flush=True)
            warm()
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
            return 0
        if cmd == "new":
            empty = None
            if a.empty:
                w, _, h = a.empty.partition("x")
                empty = {"w": int(w), "h": int(h), "library": a.library}
            got = new_model(a.title, a.src, empty, a.why, a.author, a.id)
            model = got["model"]
            model["walk_ins"] = [_parse_walk_in(s) for s in a.walk_in]
            for spec in a.door:
                side, _, target = spec.partition("=")
                if target:
                    t = int(target)
                elif model["walk_ins"]:
                    t = model["walk_ins"][0]["from"]
                else:
                    raise Refused("--door %s: куда? %s=<id> или --walk-in" % (side, side))
                model["doors"][side] = {"target": t, "why": ""}
            code, out = save(model, model["etag"], a.author)
            if code != 200:
                _print_problems(out.get("problems") or [])
                print("refused (%d): %s" % (code, out.get("error")), file=sys.stderr)
                return 2
            print(json.dumps({"id": out["id"], "written": out["written"], "dropped": got["dropped"]},
                             ensure_ascii=False))
            return 0
        if cmd == "show":
            print(json.dumps(_model_arg(a.ref), ensure_ascii=False, indent=1))
            return 0
        if cmd == "check":
            got = check(_model_arg(a.ref), a.quick)
            _print_problems(got["problems"])
            errors = [p for p in got["problems"] if p["level"] == "error"]
            print("%d errors, %d warnings, %.1f s" % (len(errors), len(got["problems"]) - len(errors),
                                                      got["seconds"]))
            return 1 if errors else 0
        if cmd == "render":
            png, rep = render_png(_model_arg(a.ref), a.layers, a.scale)
            with open(a.out, "wb") as fh:
                fh.write(png)
            print(json.dumps(rep, ensure_ascii=False))
            return 0
        if cmd == "save":
            model = _model_arg(a.file)
            code, out = save(model, a.etag or model.get("etag") or "", a.author)
            _print_problems(out.get("problems") or [])
            if code != 200:
                print("refused (%d): %s" % (code, out.get("error")), file=sys.stderr)
                return 2
            print(json.dumps({"id": out["id"], "written": out["written"]}, ensure_ascii=False))
            return 0
    except (Refused, Conflict, KeyError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
