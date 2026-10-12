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

PUBLISH MODE, for the admin panel (lava-admin runs this in a container of
its own, service `locations`, and shows the page at /admin/locations):

    python3 DIR/tools/location_editor.py --repo DIR [--branch main]
            --host 0.0.0.0 [--port 8096] [--work /work] [--store /store]
            [--cache /cache]

DIR is a git clone whose origin is the source of truth (lvrbrn/server); the
editor runs from it and reads its data/, and never writes it. What the page
saves is a draft, WORK/drafts/<uuid>.json (the page saves after 3 s of quiet
and keeps a copy in the browser); the owner's objects go into WORK/objects
(the clone's client/objects with the uploads laid over it, kept until they
are published). A new place has the temporary id "new:<uuid>" (its draft's
uuid) until it is published; the checks see it under the first free number.
«Опубликовать» (POST /api/publish) runs in the background, one at a time,
and the draft says how far it got:

  1. fetch origin/<branch>; when origin's engine (ENGINE: the server, data/
     but the tables this editor merges, this editor and the tools it
     imports) is not the checkout's, the editor restarts on it first (503
     restarting, RESTART_CODE: the entrypoint checks the new commit out);
  2. a git worktree of origin/<branch>; the pending objects laid into its
     client/objects (an object main changed meanwhile is a 409); the draft
     saved into its data/ by main's own code (`publish-save`, the save above:
     L1, L2, L3 and the map's recount): a new place gets the first free id
     there, and every "new:<uuid>" of the draft becomes it (fn ED_NEW too);
     a place whose rows main changed since the draft began is a 409 (a
     stale draft), an error a 422;
  3. the changed files of data/ and client/objects committed onto
     origin/<branch> in an index of its own (tools/publisher.py), author
     «<login> (админка)» from X-Lava-Admin;
  4. L4: the location suites (L4_SUITES, LAVA_LOCATIONS_L4) run on that
     commit's tree with LAVA_RES (LAVA_LOCATIONS_L4_RES: several folders
     separated by ":" are laid one over the other); a red one, its known
     failure (tools/known_failures.txt) aside, and nothing is pushed;
  5. push <commit>:refs/heads/<branch>, PUSH_TRIES times while the branch
     moves meanwhile; then the editor restarts on the new commit.

The art comes from the release store by sha (--store, LAVA_ART_STORE: the
site's download/client/store, <aa>/<sha256>) through client/base.txt and
extra.txt, cached under --cache (LAVA_ART_CACHE); at most two pictures are
extracted at once, and the ten libraries the original uses most are
extracted in the background at start. Requests come from the panel alone
(no port outside); a write names its admin in X-Lava-Admin (the panel sends
the login as its UTF-8 bytes), and the panel itself checks its form token
(X-Lava-Token) before it lets a write through. More of the API in publish
mode:

  GET  /api/entry                the built page's script and styles, for the panel
  GET  /api/drafts               {drafts: [{uuid, id, title, state, from, base, rev,
                                 created, created_by, updated, login, stale,
                                 publish}]}
  GET  /api/draft/<uuid>         the draft whole: {uuid, rev, base, id, model,
                                 publish: {state: running|done|failed, step,
                                 code, result, ...} or null}
  GET  /api/diff/<uuid>          what publishing it would change, against the
                                 checkout: {summary, files, objects, problems,
                                 stale, assign, ...}
  POST /api/new                  as above, and the draft made at once: {model
                                 (id "new:<uuid>"), dropped, notes, draft: {uuid, rev}}
  POST /api/draft, /api/save     {uuid?, rev?, base?, model} -> {uuid, rev, updated,
                                 id}; 409 when the draft was saved meanwhile
                                 (another tab: its rev differs) or is published
  POST /api/draftdel             {uuid}
  POST /api/publish              {uuid, rev?, message?} -> 202 {uuid, publish};
                                 then GET /api/draft/<uuid> until publish.state
                                 is done (result: {commit, url, id, summary,
                                 files, suites, objects}) or failed (code
                                 409/422/502 and result {error, problems?,
                                 suites?, git?})
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
import uuid as uuidlib
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
import publisher  # noqa: E402
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
        # publish mode: at most EXTRACT_AT_ONCE pictures extracted at once
        _ART[0] = (_LimitedArt if PUB is not None else A.Art)(objects=P.objects)
    return _ART[0]


def res_bytes(rel):
    """A file of the client the server's slice (RES) may not hold -- the
    original's database/locations.xml is no part of /opt/lava/res -- from
    RES, else from the release (client/base.txt, the store, by its sha)."""
    raw = read_bytes(os.path.join(world.RES, *rel.split("/")))
    if raw is None:
        try:
            raw = art().read(rel)
        except (OSError, ValueError):
            raw = None
    return raw


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
    and /api/info and /api/new tell the owner. In publish mode: origin's as
    the clone last fetched it."""
    if PUB is not None:
        GIT.update(ok=True, why="")
        names = PUB.ls(PUB.remote_ref, "data/locations/static")
        return {i for i in (world._static_name(os.path.basename(n)) for n in names) if i is not None}
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
    square erased or kept under a hidden name (data/map_cells.json 'cells',
    'keep') and a name hidden (data/map_labels.json 'hide'). A place of ours
    there would put a name and a place back over what was cut
    (server/test_map_cells.py, test_halfa_cut and the other cuts' suites
    hold those cells empty)."""
    out = {}
    cd = cells_doc()
    for part, why in (("cells", "квадрат стёрт (data/map_cells.json)"),
                      ("keep", "имя снято, квадрат оставлен (data/map_cells.json)")):
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
        raw = res_bytes("database/locations.xml") or b""
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
    raw = res_bytes("database/locations.xml")
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


# --- what a save changes, in words --------------------------------------------------------------

SIDE_WORDS = {"W": "запад", "N": "север", "E": "восток", "S": "юг", "a": "дверь a", "b": "дверь b"}
ATTR_WORDS = (("title", "название"), ("pvp", "pvp"), ("war", "война"), ("bgsound", "музыка"), ("fn", "fn"),
              ("library", "библиотека"), ("bg", "фон"), ("bgExt", "вид фона"))


def _cellset(rows):
    return {(int(r[0]), int(r[1])) for r in rows or () if _ok_cell(r)}


def _plus_minus(word, now, was):
    add, gone = len(now - was), len(was - now)
    if not add and not gone:
        return None
    return "%s: %s" % (word, ", ".join(p for p in ("+%d" % add if add else "", "−%d" % gone if gone else "") if p))


def cells_word(n):
    """«1 клетка», «3 клетки», «5 клеток»."""
    tail = n % 100
    word = "клеток" if 11 <= tail <= 14 else {1: "клетка", 2: "клетки", 3: "клетки", 4: "клетки"}.get(n % 10, "клеток")
    return "%d %s" % (n, word)


def _names_of(types, limit=4):
    c = collections.Counter(types)
    parts = ["%s%s" % (creature_name(t), " ×%d" % n if n > 1 else "") for t, n in sorted(c.items())]
    return ", ".join(parts[:limit]) + (" и ещё %d" % (len(parts) - limit) if len(parts) > limit else "")


def describe(before, after):
    """What saving the model `after` changes against `before` (the place as
    it is; for a new place, the location it is copied from, or None for one
    made empty): one line in Russian per kind of change -- the publish
    dialog's semantic diff and the commit message's summary."""
    out = []
    title = str((after.get("attrs") or {}).get("title") or "")
    new = after.get("state") == "new" or bool(temp_uuid(after.get("id")))
    if new:
        src = after.get("from")
        out.append("новое место%s «%s», %s" % ("" if temp_uuid(after.get("id")) else " #%s" % after.get("id"), title,
                                               "копия #%s" % src if src is not None else
                                               "пустое %sx%s" % (after.get("width"), after.get("height"))))
    if before is None:
        before = {}
    elif new:
        # the location copied: its file is the new place's start, its rows are its own
        before = dict(before, inhabitants=[], spawns=[], doors={}, walk_ins=[], no_map=None, map=None, index=None)
    a0, a1 = before.get("attrs") or {}, after.get("attrs") or {}
    for k, word in ATTR_WORDS:
        if new and k in ("title", "fn"):
            continue
        if before and str(a0.get(k, "")) != str(a1.get(k, "")):
            out.append("%s: «%s» → «%s»" % (word, a0.get(k, ""), a1.get(k, "")))
    for key, word in (("walls", "стены"), ("entries", "входы"), ("war_entries", "военные входы")):
        line = _plus_minus(word, _cellset(after.get(key)), _cellset(before.get(key)))
        if line:
            out.append(line)
    e0 = {(int(r[0]), int(r[1])): str(r[2]) for r in before.get("exits") or () if _ok_cell(r) and len(r) > 2}
    e1 = {(int(r[0]), int(r[1])): str(r[2]) for r in after.get("exits") or () if _ok_cell(r) and len(r) > 2}
    for side in sorted(set(e0.values()) | set(e1.values()), key=lambda s: "WNESab".find(s)):
        line = _plus_minus("выходы (%s)" % SIDE_WORDS.get(side, side),
                           {c for c, s in e1.items() if s == side}, {c for c, s in e0.items() if s == side})
        if line:
            out.append(line)

    def placings(m):
        return collections.Counter((str(s.get("id")), s.get("type"), L.num(s.get("dx")), L.num(s.get("dy")),
                                    str(s.get("front") or ""), int(a[0]), int(a[1]))
                                   for s in m.get("sprites") or () for a in s.get("anchors") or () if _ok_cell(a))
    p0, p1 = placings(before), placings(after)
    if p0 != p1:
        add, gone = sum((p1 - p0).values()), sum((p0 - p1).values())
        out.append("объекты на клетках: %s" % ", ".join(p for p in ("+%d" % add if add else "",
                                                                    "−%d" % gone if gone else "") if p))
    if before and (before.get("decals") or []) != (after.get("decals") or []):
        out.append("наклейки: было %d, стало %d" % (len(before.get("decals") or []), len(after.get("decals") or [])))
    if before and (before.get("background") or None) != (after.get("background") or None):
        out.append("фон: %s → %s" % ((before.get("background") or {}).get("id", ""),
                                     (after.get("background") or {}).get("id", "")))

    def people(m):
        return collections.Counter((int(r["type"]), int(r["cell"][0]), int(r["cell"][1]))
                                   for r in m.get("inhabitants") or ()
                                   if isinstance(r, dict) and "type" in r and _ok_cell(r.get("cell") or ()))
    h0, h1 = people(before), people(after)
    if h0 != h1:
        add = [t for (t, _x, _y), n in (h1 - h0).items() for _ in range(n)]
        gone = [t for (t, _x, _y), n in (h0 - h1).items() for _ in range(n)]
        parts = []
        if add:
            parts.append("+%d (%s)" % (len(add), _names_of(add)))
        if gone:
            parts.append("−%d (%s)" % (len(gone), _names_of(gone)))
        out.append("жители: " + ", ".join(parts))
    d0, d1 = before.get("doors") or {}, after.get("doors") or {}
    for side in DOOR_SIDES:
        t0, t1 = (d0.get(side) or {}).get("target"), (d1.get(side) or {}).get("target")
        if t0 != t1:
            out.append("дверь %s: %s → %s" % (side, "#%s" % t0 if t0 is not None else "никуда",
                                              "#%s" % t1 if t1 is not None else "никуда"))

    def walks_in(m):
        return {(int(w.get("from")), tuple(sorted(_cellset(w.get("cells"))))) for w in m.get("walk_ins") or ()
                if isinstance(w, dict) and str(w.get("from", "")).lstrip("-").isdigit()}
    w0, w1 = walks_in(before), walks_in(after)
    for src, cells in sorted(w1 - w0):
        out.append("проход сюда из #%d (%s)" % (src, cells_word(len(cells))))
    for src, cells in sorted(w0 - w1):
        if src not in {s for s, _c in w1}:
            out.append("убран проход из #%d" % src)
    if bool(before.get("no_map")) != bool(after.get("no_map")):
        out.append("не выходит на карту" if after.get("no_map") else "снова выходит на карту")
    m0, m1 = before.get("map") or {}, after.get("map") or {}
    c0 = tuple(m0["cell"]) if m0.get("cell") is not None else None
    c1 = tuple(m1["cell"]) if m1.get("cell") is not None else None
    if c0 != c1:
        out.append("клетка на карте: %s → %s" % ("%d,%d" % c0 if c0 else "нет", "%d,%d" % c1 if c1 else "нет"))
    if c1 and (m0.get("label") or "") != (m1.get("label") or ""):
        out.append("подпись на карте: «%s»" % (m1.get("label") or ""))
    if c1 and (m0.get("square") or None) != (m1.get("square") or None):
        out.append("квадрат на карте: %s" % (m1.get("square") or "без квадрата"))
    i0, i1 = before.get("index") or {}, after.get("index") or {}
    if before and not new and str(i0.get("why") or "") != str(i1.get("why") or ""):
        out.append("«почему» места переписано")
    return out


def describe_against(model):
    """describe() of a model against what the editor's data/ has: the place
    itself (ours), or the location a new place is copied from."""
    try:
        lid = int(model["id"])
    except (TypeError, ValueError, KeyError):
        lid = None
    before = None
    if lid is not None and model.get("state") != "new" and is_ours(lid):
        before = load_model(lid)
    elif model.get("from") is not None:
        try:
            before = load_model(int(model["from"]))
        except (NotFound, TypeError, ValueError):
            before = None
    return describe(before, model)


# --- publish mode (the admin panel) ------------------------------------------------------------

PUB = None                  # the LocationPublisher in publish mode, None locally
WORK = None                 # its folder: drafts/, objects/, publish/
DRAFTS = None
PENDING = None
TEMP = re.compile(r"new:([0-9a-f]{32})\Z")
UUID = re.compile(r"[0-9a-f]{32}\Z")
TEMP_FN = "ED_NEW"          # a new place's fn while it has no number and its title no latin word
# What the checks and the merge read: the server, its tables, the editor and
# the tools it imports. When origin's differ from the checkout's, the editor
# restarts on them before it publishes. The tables a save of a place writes
# (MERGED) are merged by that save itself, on origin's own: never a reason.
ENGINE = ("server", "data", "client/build.py", "tools/location_editor.py", "tools/lavaloc.py",
          "tools/swfx.py", "tools/location_art.py", "tools/publisher.py", "tools/custom_objects.py",
          "tools/jsonrows.py", "tools/swfgen.py")
MERGED = ("data/locations/", "data/placements.json", "data/passages.json", "data/map_labels.json",
          "data/map_cells.json", "data/settlements_verified.json", "data/settlements.json",
          "data/settlements_report.md", "data/exits_sides.json", "client/objects/")
PUBLISHED_PATHS = ("data", "client/objects")
# L4: the suites that read locations and the tables a place writes, run on
# the commit before it is pushed. The long ones that play whole sessions
# (test_walk_in, test_travel, test_world) are CI's after the push.
L4_SUITES = ("server/test_locations.py", "server/test_location_overrides.py", "server/test_new_location.py",
             "server/test_map_labels.py", "server/test_map_cells.py", "server/test_camp_patrols.py",
             "data/test_borders.py", "tools/test_lavaloc.py")
# a suite that needs a file of the client beyond the server's slice runs only
# where the res given has it (CI's extras, /opt/lava-ci/res-extra)
L4_NEEDS = {"server/test_map_labels.py": "database/locations.xml"}
L4_JOBS = int(os.environ.get("LAVA_LOCATIONS_L4_JOBS") or "2")
L4_TIMEOUT = 900
EXTRACT_AT_ONCE = int(os.environ.get("LAVA_LOCATION_EDITOR_EXTRACT") or "2")
WARM_LIBRARIES = 10
KEEP_PUBLISHED = 3 * 86400  # a published draft is kept this long, for the page that asks how it went
RESTARTS_AFTER = 20         # minutes, about: CI, the deploy and the warning to players
WARN_SECONDS = 180

# the publish steps, in the page's words
STEPS = {"start": "начинаю", "fetch": "беру свежий main", "tree": "раскладываю main",
         "objects": "кладу объекты", "save": "сохраняю место и проверяю его, как сервер",
         "commit": "собираю коммит", "suites": "гоняю наборы проверок (L4)", "push": "отправляю в main",
         "done": "готово"}


class _LimitedArt(A.Art):
    """Art that extracts at most EXTRACT_AT_ONCE pictures at once (a big
    library takes about 500 MB while it is extracted; the container has 2 GB)."""

    _slots = threading.BoundedSemaphore(EXTRACT_AT_ONCE)

    def ensure(self, path):
        e = self.entry(path)
        if e is None or self._cached(e.sha) is not None:
            return A.Art.ensure(self, path)
        with self._slots:
            return A.Art.ensure(self, path)

    def mob(self, type_id, direction=1):
        if (int(type_id), direction) in self._mob_memo:
            return A.Art.mob(self, type_id, direction)
        with self._slots:
            return A.Art.mob(self, type_id, direction)


def _warm_libraries():
    """The libraries the original's locations use most, extracted ahead."""
    counts = collections.Counter(r.get("library") for r in _originals().values() if r.get("library"))
    for name, _n in counts.most_common(WARM_LIBRARIES):
        try:
            art().library(libraries().get(name.lower(), name))
        except Exception:                  # noqa: BLE001 -- a library missing is a thumbnail missing
            traceback.print_exc()


class LocationPublisher(publisher.Publisher):
    """The clone publish mode works on, the location editor's way."""

    def __init__(self, repo, branch="main", web=""):
        publisher.Publisher.__init__(
            self, repo, branch, web, engine=ENGINE, merged=MERGED, section="Локации",
            ident={"author_email": ("LAVA_LOCATIONS_AUTHOR_EMAIL", "locations@lava-reborn.ru"),
                   "committer_name": ("LAVA_LOCATIONS_COMMITTER_NAME", "Редактор локаций админки"),
                   "committer_email": ("LAVA_LOCATIONS_COMMITTER_EMAIL", "locations@lava-reborn.ru")},
            tmp_prefix="loc-publish-")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def temp_uuid(v):
    """The uuid of a temporary id "new:<uuid>", else None."""
    m = TEMP.match(v) if isinstance(v, str) else None
    return m.group(1) if m else None


def numbered(model):
    """(model, temp, n): a model whose id is "new:<uuid>" under the first free
    number n, for the checks, the edits and the pictures; temp None for one
    that has its number."""
    if not isinstance(model, dict) or not temp_uuid(model.get("id")):
        return model, None, None
    n = next_free_id()
    return dict(model, id=n, state="new"), model["id"], n


def lettered(model, temp, n):
    """A model numbered() gave, back under its temporary id."""
    if temp is not None and isinstance(model, dict) and model.get("id") == n:
        return dict(model, id=temp)
    return model


def problems_back(problems, temp, n):
    if temp is not None:
        for p in problems:
            if p.get("loc") == n:
                p["loc"] = temp
    return problems


def assign_id(model, temp, real):
    """A new place's model under its number: every "new:<uuid>" in it (the
    id, a why that names it) becomes the number, and fn ED_NEW its ED_<id>."""
    def walk(v):
        if isinstance(v, str):
            return v.replace(temp, str(real))
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v
    m = walk(model)
    m["id"] = int(real)
    m["state"] = "new"
    attrs = m.setdefault("attrs", {})
    if str(attrs.get("fn") or "") == TEMP_FN:
        attrs["fn"] = "ED_%d" % int(real)
    elif not attrs.get("fn"):
        attrs["fn"] = fn_for(attrs.get("title"), int(real))
    return m


class Drafts:
    """The drafts of publish mode: WORK/drafts/<uuid>.json each."""

    def __init__(self, folder):
        self.dir = folder
        os.makedirs(folder, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, uuid):
        if not UUID.fullmatch(str(uuid or "")):
            raise NotFound("нет черновика %s" % uuid)
        return os.path.join(self.dir, "%s.json" % uuid)

    def read(self, uuid):
        try:
            with open(self.path(uuid), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def get(self, uuid):
        d = self.read(uuid)
        if d is None:
            raise NotFound("нет черновика %s" % uuid)
        return d

    def write(self, doc):
        write_atomic(self.path(doc["uuid"]), (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))

    def delete(self, uuid):
        try:
            os.unlink(self.path(uuid))
        except FileNotFoundError:
            pass

    def all(self):
        out = []
        for f in sorted(os.listdir(self.dir)):
            if f.endswith(".json") and UUID.fullmatch(f[:-5]):
                d = self.read(f[:-5])
                if d:
                    out.append(d)
        return out

    def settle(self):
        """At start: a publish a restart cut short is said to have failed (its
        thread is gone); a published draft past KEEP_PUBLISHED goes."""
        cut = time.time() - KEEP_PUBLISHED
        for d in self.all():
            pub = d.get("publish") or {}
            if pub.get("state") == "running":
                d["publish"] = dict(pub, state="failed", code=503, finished=now_iso(), result={
                    "error": "Публикацию прервал перезапуск редактора. Если коммит успел уйти, он виден в истории "
                             "main; иначе опубликуйте ещё раз"})
                self.write(d)
            elif pub.get("state") == "done":
                try:
                    if os.path.getmtime(self.path(d["uuid"])) < cut:
                        self.delete(d["uuid"])
                except OSError:
                    pass


def draft_stale(d):
    """Why a draft would be a 409 now (its place's rows changed in the
    checkout since it began), or None."""
    m = d.get("model") or {}
    if temp_uuid(m.get("id")) or m.get("state") != "ours":
        return None
    try:
        if etag_of(location_state(int(m["id"]))) != m.get("etag"):
            return ("локацию %s тем временем изменили в %s: этот черновик начат с прежней" % (m["id"], PUB.branch))
    except (TypeError, ValueError, KeyError):
        return None
    return None


def draft_row(d):
    m = d.get("model") or {}
    pub = d.get("publish") or None
    return {"uuid": d["uuid"], "id": d.get("id"), "title": str((m.get("attrs") or {}).get("title") or ""),
            "state": m.get("state"), "from": m.get("from"), "base": d.get("base"), "rev": d.get("rev"),
            "created": d.get("created"), "created_by": d.get("created_by"), "updated": d.get("updated"),
            "login": d.get("login"), "stale": draft_stale(d),
            "publish": {k: pub.get(k) for k in ("state", "step", "code", "started", "finished", "login")}
            if pub else None}


def drafts_list():
    rows = [draft_row(d) for d in DRAFTS.all() if (d.get("publish") or {}).get("state") != "done"]
    return sorted(rows, key=lambda r: r.get("updated") or "", reverse=True)


def checkout_head():
    try:
        return PUB.rev("HEAD")
    except publisher.GitError:
        return ""


def draft_save(body, login):
    """POST /api/draft (and /api/save in publish mode)."""
    model = body.get("model")
    if not isinstance(model, dict):
        raise Refused("model: объект")
    temp = temp_uuid(model.get("id"))
    _clean(numbered(model)[0])
    uuid = str(body.get("uuid") or temp or uuidlib.uuid4().hex)
    if not UUID.fullmatch(uuid):
        raise Refused("uuid черновика: 32 шестнадцатеричных знака")
    if temp and temp != uuid:
        raise Refused("черновик нового места живёт под его же номером new:<uuid>")
    if not temp:
        if model.get("state") != "ours" or not is_ours(int(model["id"])):
            raise Refused("черновик — нового места или нашей локации; локация оригинала правится копией")
        if int(model["id"]) == 262:
            raise Refused("262 «Тотем» закрыт для редактора")
    with DRAFTS.lock:
        d = DRAFTS.read(uuid)
        if d is None:
            d = {"v": 1, "uuid": uuid, "rev": 0, "created": now_iso(), "created_by": login,
                 "base": str(body.get("base") or "") or checkout_head(), "publish": None}
        else:
            pub = d.get("publish") or {}
            if pub.get("state") == "running":
                raise Conflict("черновик сейчас публикуется: дождитесь конца", {"rev": d["rev"], "publish": pub})
            if pub.get("state") == "done":
                raise Conflict("черновик уже опубликован: дальнейшие правки — в локации из списка",
                               {"rev": d["rev"], "publish": pub})
            if body.get("rev") is not None and str(body.get("rev")) != str(d.get("rev")):
                raise Conflict("черновик тем временем сохранили в другой вкладке (%s): откройте его заново"
                               % (d.get("login") or "?"), {"rev": d.get("rev"), "login": d.get("login"),
                                                           "updated": d.get("updated")})
            if (d.get("model") or {}).get("id") != model.get("id"):
                raise Conflict("у черновика другая локация: %s" % (d.get("model") or {}).get("id"))
            if pub.get("state") == "failed":
                d["publish"] = None
        d.update(rev=int(d.get("rev") or 0) + 1, model=model, id=model.get("id"), updated=now_iso(), login=login,
                 title=str((model.get("attrs") or {}).get("title") or ""))
        DRAFTS.write(d)
        return {"uuid": uuid, "rev": d["rev"], "updated": d["updated"], "id": d["id"], "base": d.get("base")}


def draft_new(body, login):
    """POST /api/new in publish mode: the model under "new:<uuid>" and its
    draft at once."""
    uuid = uuidlib.uuid4().hex
    temp = "new:" + uuid
    n = next_free_id()
    got = new_model(body.get("title"), body.get("from"), body.get("empty"), body.get("why") or "",
                    author=login, new_id=n)
    m = got["model"]
    if m["attrs"].get("fn") == "ED_%d" % n:
        m["attrs"]["fn"] = TEMP_FN
    m["id"] = temp
    m["etag"] = ""
    notes = [x for x in got["notes"] if "origin/main" not in x]
    notes.append("Номер новое место получит при публикации: первый свободный в %s (сейчас это %d)."
                 % (PUB.branch, n))
    with DRAFTS.lock:
        d = {"v": 1, "uuid": uuid, "rev": 1, "created": now_iso(), "created_by": login, "updated": now_iso(),
             "login": login, "base": str(body.get("base") or "") or checkout_head(), "id": temp,
             "title": m["attrs"]["title"], "model": m, "publish": None}
        DRAFTS.write(d)
    return {"model": m, "dropped": got["dropped"], "notes": notes, "draft": {"uuid": uuid, "rev": 1}}


def draft_delete(body):
    uuid = str(body.get("uuid") or "")
    with DRAFTS.lock:
        d = DRAFTS.get(uuid)
        if (d.get("publish") or {}).get("state") == "running":
            raise Conflict("черновик сейчас публикуется")
        DRAFTS.delete(uuid)
    return {"uuid": uuid, "deleted": True}


def draft_users(oid):
    """The drafts whose place shows an object (any case)."""
    low = oid.lower()
    out = []
    for d in DRAFTS.all() if DRAFTS else ():
        if (d.get("publish") or {}).get("state") == "done":
            continue
        m = d.get("model") or {}
        ids = [s.get("id") for s in m.get("sprites") or ()] + [x.get("id") for x in m.get("decals") or ()]
        ids.append((m.get("background") or {}).get("id"))
        if any(str(x or "").lower() == low for x in ids):
            out.append("«%s»" % ((m.get("attrs") or {}).get("title") or d["uuid"][:8]))
    return out


def draft_diff(uuid):
    """GET /api/diff/<uuid>: what publishing the draft would change, worked
    out against the checkout (the publish works it out again on origin's)."""
    d = DRAFTS.get(uuid)
    m0 = d.get("model")
    out = {"uuid": uuid, "rev": d.get("rev"), "base": d.get("base"), "head": PUB._about("HEAD"),
           "objects": PENDING.listing(), "restart_minutes": RESTARTS_AFTER, "warn_seconds": WARN_SECONDS,
           "branch": PUB.branch}
    if not m0:
        out.update(summary=[], files=[], problems=[], stale=None, id=None, assign=None)
        return out
    model, temp, n = numbered(m0)
    model = _clean(model)
    out["id"] = m0.get("id")
    out["assign"] = n
    out["stale"] = draft_stale(d)
    summary = describe_against(dict(model, id=m0.get("id")) if temp else model)
    problems = lint(model)
    try:
        plan = plan_writes(model, d.get("login") or "admin")
        files = [P.rel(p) for p in sorted(plan)]
    except Exception as exc:               # noqa: BLE001 -- a plan that does not come out is a problem shown
        files = []
        problems.append(problem("error", "model", "файлы из черновика не пишутся: %s" % exc))
    if temp:
        files = [f.replace("/%d.xml" % n, "/%s.xml" % "N") for f in files]
    out.update(summary=summary, files=files, problems=problems_back(problems, temp, n))
    out["occupancy_id"] = None if temp else model["id"]
    return out


class PendingObjects:
    """The owner's objects of publish mode, not yet in main: WORK/objects/view
    is the clone's client/objects with them laid over it (what the editor
    reads and the object calls write), pending.json and pending/<id>/ what
    each changed into, against what the clone had (base) when it changed."""

    def __init__(self, folder, checkout):
        self.dir = folder
        self.view = os.path.join(folder, "view")
        self.files = os.path.join(folder, "pending")
        self.journal = os.path.join(folder, "pending.json")
        self.checkout = checkout
        self.lock = threading.RLock()
        os.makedirs(self.files, exist_ok=True)

    def load(self):
        return load_json(self.journal, {}) or {}

    def save(self, j):
        write_atomic(self.journal, (json.dumps(j, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8"))

    @staticmethod
    def shas(folder):
        if not os.path.isdir(folder):
            return {}
        return {n: sha(read_bytes(os.path.join(folder, n))) for n in sorted(os.listdir(folder))
                if os.path.isfile(os.path.join(folder, n))}

    @staticmethod
    def raw(folder):
        try:
            return CO.load_raw(folder)
        except CO.Refused:
            return {}

    def rebuild(self):
        """The view, anew: the clone's objects and the pending ones over them."""
        with self.lock:
            shutil.rmtree(self.view, ignore_errors=True)
            if os.path.isdir(self.checkout):
                shutil.copytree(self.checkout, self.view)
            else:
                os.makedirs(self.view)
            j = self.load()
            if not j:
                return
            raw = self.raw(self.view)
            for oid, rec in sorted(j.items()):
                shutil.rmtree(os.path.join(self.view, oid), ignore_errors=True)
                if rec.get("entry") is None:
                    raw.pop(oid, None)
                    continue
                shutil.copytree(os.path.join(self.files, oid), os.path.join(self.view, oid))
                raw[oid] = rec["entry"]
            write_atomic(os.path.join(self.view, CO.MANIFEST), CO.manifest_text(raw).encode("utf-8"))

    def record(self, oid):
        """After an object call wrote the view: what the object is now."""
        with self.lock:
            j = self.load()
            entry = self.raw(self.view).get(oid)
            files = self.shas(os.path.join(self.view, oid)) if entry is not None else {}
            was = {"entry": self.raw(self.checkout).get(oid), "files": self.shas(os.path.join(self.checkout, oid))}
            base = (j.get(oid) or {}).get("base") or was
            shutil.rmtree(os.path.join(self.files, oid), ignore_errors=True)
            if entry == was["entry"] and files == (was["files"] if was["entry"] is not None else {}):
                j.pop(oid, None)           # back to what main has: nothing to publish
            else:
                if entry is not None:
                    shutil.copytree(os.path.join(self.view, oid), os.path.join(self.files, oid))
                kind = "delete" if entry is None else ("new" if base.get("entry") is None else "update")
                j[oid] = {"entry": entry, "files": files, "base": base, "kind": kind, "at": now_iso()}
            self.save(j)

    def listing(self):
        return [{"id": oid, "kind": rec.get("kind"), "title": (rec.get("entry") or (rec.get("base") or {}).get("entry")
                                                                 or {}).get("title", ""), "at": rec.get("at")}
                for oid, rec in sorted(self.load().items())]

    def apply_to(self, objdir):
        """The pending objects into a tree's client/objects (origin's); Conflict
        when origin changed one of them since it was taken. [{id, kind,
        title, at}]."""
        with self.lock:
            j = self.load()
            if not j:
                return []
            raw = self.raw(objdir)
            for oid, rec in sorted(j.items()):
                now = {"entry": raw.get(oid), "files": self.shas(os.path.join(objdir, oid))}
                mine = {"entry": rec.get("entry"), "files": rec.get("files") or {}}
                if now["entry"] is None:
                    now["files"] = {}
                base = rec.get("base") or {}
                if base.get("entry") is None:
                    base = {"entry": None, "files": {}}
                if now != base and now != mine:
                    raise Conflict("объект %s тем временем изменили в %s: откройте «Мои объекты» после перезапуска "
                                   "редактора и сделайте правку заново" % (oid, PUB.branch if PUB else "main"))
                shutil.rmtree(os.path.join(objdir, oid), ignore_errors=True)
                if rec.get("entry") is None:
                    raw.pop(oid, None)
                else:
                    shutil.copytree(os.path.join(self.files, oid), os.path.join(objdir, oid))
                    raw[oid] = rec["entry"]
            write_atomic(os.path.join(objdir, CO.MANIFEST), CO.manifest_text(raw).encode("utf-8"))
            return self.listing()

    def published(self, done):
        """The objects a push took to main: no longer pending (unless changed
        again since)."""
        with self.lock:
            j = self.load()
            for o in done:
                rec = j.get(o["id"])
                if rec is not None and rec.get("at") == o.get("at"):
                    j.pop(o["id"])
                    shutil.rmtree(os.path.join(self.files, o["id"]), ignore_errors=True)
            self.save(j)


def configure_repo(repo, branch="main", web="", work=None, store=None, cache=None):
    """Publish mode on the clone repo: its data/ read and never written, the
    drafts and the pending objects in work."""
    global PUB, WORK, DRAFTS, PENDING, CACHE
    PUB = LocationPublisher(repo, branch, web)
    WORK = os.path.abspath(work or os.path.join(os.path.dirname(PUB.repo), "locations-work"))
    if store:
        os.environ["LAVA_ART_STORE"] = store
    if cache:
        # the pictures, the original's placings, the list and the map's
        # recount, shared with the publish's own save (a subprocess)
        os.environ["LAVA_ART_CACHE"] = cache
        os.environ["LAVA_LOCATION_EDITOR_CACHE"] = cache
        CACHE = cache
    os.environ.setdefault("LAVA_ART_IMAGE_PIXELS", "40000000")
    for sub in ("drafts", "objects", "publish"):
        os.makedirs(os.path.join(WORK, sub), exist_ok=True)
    DRAFTS = Drafts(os.path.join(WORK, "drafts"))
    DRAFTS.settle()
    PENDING = PendingObjects(os.path.join(WORK, "objects"), os.path.join(PUB.repo, "client", "objects"))
    PENDING.rebuild()
    configure(os.path.join(PUB.repo, "data"), PENDING.view)
    res = fill_res(os.path.join(WORK, "res"))
    if res != world.RES:
        # what this process, the checks it starts and the suites read from now on
        world.RES = os.environ["LAVA_RES"] = res
        world._CACHE.clear()
        forget("tooltips", "res_original")
    # what the last publish left behind in the clone, a killed one included
    try:
        PUB.git("worktree", "prune")
    except publisher.GitError:
        pass
    shutil.rmtree(os.path.join(WORK, "publish"), ignore_errors=True)
    os.makedirs(os.path.join(WORK, "publish"), exist_ok=True)
    return PUB


# What the checks read of the client beyond the server's slice (/opt/lava/res):
# data/place_settlements.py, the map's recount, reads the original's list of
# places on the map. Publish mode lays it in from the release by its sha.
RES_FILLS = ("database/locations.xml",)


def fill_res(into):
    """RES as the checks need it: RES itself when it has every file of
    RES_FILLS, else a folder of links to it with the missing ones taken from
    the release (client/base.txt, the store) laid in."""
    if not world.RES:
        return world.RES
    missing = [rel for rel in RES_FILLS if not os.path.isfile(os.path.join(world.RES, *rel.split("/")))]
    if not missing:
        return world.RES
    extra = into + "-fill"
    shutil.rmtree(extra, ignore_errors=True)
    found = 0
    for rel in missing:
        try:
            data = art().read(rel)
        except (OSError, ValueError):
            data = None
        if data is None:
            print("location editor: %s is in neither RES (%s) nor the release store; the map's recount "
                  "will not run" % (rel, world.RES), flush=True)
            continue
        write_atomic(os.path.join(extra, *rel.split("/")), data)
        found += 1
    if not found:
        return world.RES
    return merged_res([os.path.realpath(world.RES), extra], into)


def merged_res(dirs, into):
    """One folder of links that has the files of every one of dirs, a later
    one's file over an earlier one's: the server's slice and CI's extras as
    the suites see them in CI."""
    shutil.rmtree(into, ignore_errors=True)
    os.makedirs(into)

    def merge(srcs, dst):
        names = collections.OrderedDict()
        for s in srcs:
            for n in sorted(os.listdir(s)):
                names.setdefault(n, []).append(os.path.join(s, n))
        for n, paths in names.items():
            subdirs = [p for p in paths if os.path.isdir(p)]
            if len(subdirs) > 1:
                os.makedirs(os.path.join(dst, n))
                merge(subdirs, os.path.join(dst, n))
            else:
                os.symlink(subdirs[0] if subdirs else paths[-1], os.path.join(dst, n))
    merge([d for d in dirs if os.path.isdir(d)], into)
    return into


def l4_res():
    dirs = [d for d in (os.environ.get("LAVA_LOCATIONS_L4_RES") or "").split(os.pathsep) if d] or [world.RES]
    if len(dirs) == 1:
        return dirs[0]
    return merged_res(dirs, os.path.join(WORK, "l4-res"))


def l4_suites(tree, res):
    """(suites to run, notes): LAVA_LOCATIONS_L4 or L4_SUITES, less those the
    tree has not and those whose file the res has not."""
    names = [s.strip() for s in (os.environ.get("LAVA_LOCATIONS_L4") or "").split(",") if s.strip()] or list(L4_SUITES)
    run, notes = [], []
    for s in names:
        if not os.path.isfile(os.path.join(tree, *s.split("/"))):
            notes.append("%s: такого набора в main нет" % s)
        elif s in L4_NEEDS and not os.path.exists(os.path.join(res, *L4_NEEDS[s].split("/"))):
            notes.append("%s пропущен: в ресурсах нет %s" % (s, L4_NEEDS[s]))
        else:
            run.append(s)
    return run, notes


def location_message(summary, objects, note, login):
    """The commit message: "Локации: …" within 72 characters, the summary,
    the objects, the admin's words, who published."""
    lines = [publisher.one_line(s) for s in summary]
    lines += ["объект %s «%s»: %s" % (o["id"], publisher.one_line(o.get("title") or ""),
                                      {"new": "новый", "update": "правка", "delete": "удалён"}.get(o["kind"], o["kind"]))
              for o in objects]
    first = "Локации: " + (lines[0] if lines else "правка")
    if len(lines) > 1 and lines[0].startswith("новое место") is False:
        first = "Локации: " + "; ".join(lines[:2])
    if len(first) > 72:
        first = first[:71] + "…"
    parts = [first, "", "\n".join(lines) or "без изменений в словах"]
    if note:
        parts += ["", note]
    parts += ["", "Опубликовано из админки: %s" % login]
    return "\n".join(parts) + "\n"


def publish_start(body, login):
    """POST /api/publish: (code, body). The work goes on in a thread of its
    own; the draft says how it goes (GET /api/draft/<uuid>)."""
    uuid = str(body.get("uuid") or "")
    if not uuid:
        # the owner's objects alone, with no place: a draft of nothing
        if not PENDING.load():
            return 400, {"error": "нечего публиковать: ни черновика (uuid), ни новых объектов"}
        uuid = uuidlib.uuid4().hex
        with DRAFTS.lock:
            DRAFTS.write({"v": 1, "uuid": uuid, "rev": 1, "created": now_iso(), "created_by": login,
                          "updated": now_iso(), "login": login, "base": checkout_head(), "id": None,
                          "title": "мои объекты", "model": None, "publish": None})
    d = DRAFTS.get(uuid)
    if body.get("rev") is not None and str(body.get("rev")) != str(d.get("rev")):
        return 409, {"error": "черновик тем временем сохранили ещё раз (другая вкладка?): откройте его заново",
                     "rev": d.get("rev")}
    pub = d.get("publish") or {}
    if pub.get("state") == "running":
        return 202, {"uuid": uuid, "publish": pub}
    if pub.get("state") == "done":
        return 409, {"error": "черновик уже опубликован", "publish": pub}
    if PUB.restarting:
        return 503, {"restarting": True, "error": publisher.RESTARTING % PUB.branch}
    try:
        PUB.fetch()
        head = PUB.rev(PUB.remote_ref)
        moved = PUB.engine_moved(head)
    except publisher.FetchError as exc:
        return 502, PUB.failed(publisher.FETCH_FAILED, exc)
    except publisher.GitError as exc:
        return 502, PUB.failed(publisher.GIT_FAILED, exc)
    if moved:
        PUB.restart()
        return 503, {"restarting": True, "error": publisher.ENGINE_MOVED % PUB.branch}
    if not PUB.lock.acquire(blocking=False):
        return 503, {"error": "Идёт другая публикация, повторите через минуту"}
    try:
        note = publisher.clean_note(body.get("message"))
        with DRAFTS.lock:
            d = DRAFTS.get(uuid)
            d["publish"] = {"state": "running", "step": "start", "step_text": STEPS["start"], "started": now_iso(),
                            "login": login, "note": note, "rev": d.get("rev")}
            DRAFTS.write(d)
        t = threading.Thread(target=_publish_job, args=(uuid, note, login), daemon=True,
                             name="loc-publish-" + uuid[:8])
        t.start()
    except BaseException:
        PUB.lock.release()
        raise
    print("publish by %s: draft %s started" % (login, uuid), flush=True)
    return 202, {"uuid": uuid, "publish": d["publish"]}


def _step(uuid, step):
    with DRAFTS.lock:
        d = DRAFTS.read(uuid)
        if d and d.get("publish"):
            d["publish"].update(step=step, step_text=STEPS.get(step, step))
            DRAFTS.write(d)


def _publish_job(uuid, note, login):
    """The publish of a draft, the lock held (publish_start took it)."""
    try:
        try:
            code, out = _publish_attempts(uuid, note, login)
        except Conflict as exc:
            code, out = 409, dict(exc.extra, error=str(exc))
        except Exception as exc:           # noqa: BLE001 -- the page gets the reason, the log the trace
            traceback.print_exc()
            code, out = 500, {"error": "%s: %s" % (type(exc).__name__, exc)}
        with DRAFTS.lock:
            d = DRAFTS.read(uuid)
            if d is not None:
                d["publish"] = dict(d.get("publish") or {}, state="done" if code == 200 else "failed", code=code,
                                    result=out, finished=now_iso(), step="done" if code == 200 else
                                    (d.get("publish") or {}).get("step"))
                DRAFTS.write(d)
        print("publish by %s: draft %s: %d %s" % (login, uuid, code, out.get("commit") or str(out.get("error", ""))[:200]),
              flush=True)
        if code == 200 and out.get("objects"):
            PENDING.published(out["objects"])
        if code == 200 and not out.get("nothing"):
            PUB.restart()                  # once the lock is let go: on the commit just pushed
    finally:
        PUB.lock.release()


def _publish_attempts(uuid, note, login):
    d = DRAFTS.get(uuid)
    model = d.get("model")
    for attempt in range(publisher.PUSH_TRIES):
        _step(uuid, "fetch")
        try:
            PUB.fetch()
            head = PUB.rev(PUB.remote_ref)
            moved = PUB.engine_moved(head)
        except publisher.FetchError as exc:
            return 502, PUB.failed(publisher.FETCH_FAILED, exc)
        except publisher.GitError as exc:
            return 502, PUB.failed(publisher.GIT_FAILED, exc)
        if moved:
            PUB.restart()
            return 503, {"restarting": True, "error": publisher.ENGINE_MOVED % PUB.branch}
        _step(uuid, "tree")
        try:
            with PUB.worktree(head, under=os.path.join(WORK, "publish")) as tree:
                got = _publish_on(uuid, tree, head, model, note, login, attempt)
        except publisher.GitError as exc:
            return 502, PUB.failed(publisher.GIT_FAILED, exc)
        if got is not None:
            return got
    return 502, {"error": "%s уходил вперёд во время публикации %d раза подряд: повторите"
                          % (PUB.branch, publisher.PUSH_TRIES)}


def _publish_on(uuid, tree, head, model, note, login, attempt):
    """One attempt on a worktree of head: (code, body), or None when the
    branch moved before the push (the caller tries again)."""
    _step(uuid, "objects")
    objects = PENDING.apply_to(os.path.join(tree, "client", "objects"))
    saved = {"summary": [], "id": None, "renumbered": {}}
    if model:
        _step(uuid, "save")
        mfile = os.path.join(os.path.dirname(tree), "%s-model.json" % uuid)
        rfile = os.path.join(os.path.dirname(tree), "%s-result.json" % uuid)
        with open(mfile, "w", encoding="utf-8") as fh:
            json.dump(model, fh, ensure_ascii=False)
        env = dict(os.environ, LAVA_LOCATION_EDITOR_GIT="0", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
        for k in ("LAVA_LOC_OVERLAY", "LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_SCHEDULE"):
            env.pop(k, None)
        try:
            p = subprocess.run([sys.executable, os.path.join(tree, "tools", "location_editor.py"),
                                "--data", os.path.join(tree, "data"), "--objects", os.path.join(tree, "client", "objects"),
                                "publish-save", mfile, "--author", login, "--out", rfile],
                               cwd=tree, env=env, capture_output=True, timeout=1800)
        except subprocess.TimeoutExpired:
            return 502, {"error": "сохранение места в main не уложилось в 30 минут"}
        res = load_json(rfile, None) if os.path.isfile(rfile) else None
        for f in (mfile, rfile):
            try:
                os.unlink(f)
            except OSError:
                pass
        if not isinstance(res, dict):
            tail = (p.stderr or p.stdout or b"").decode("utf-8", "replace")[-1500:]
            return 502, {"error": "сохранение места в main упало (код %d): %s" % (p.returncode, tail)}
        if res["code"] == 409:
            return 409, {"error": "Черновик устарел: %s" % res["body"].get("error", ""), "stale": True}
        if res["code"] != 200:
            body = res["body"]
            return res["code"], {"error": "Место в таком виде сервер не примет: %s" % body.get("error", ""),
                                 "problems": body.get("problems") or []}
        saved = res
    _step(uuid, "commit")
    files = PUB.changed_in(tree, PUBLISHED_PATHS)
    if not files:
        return 200, {"nothing": True, "commit": head, "head": PUB._about(head), "id": saved.get("id"),
                     "summary": [], "objects": objects}
    summary = list(saved.get("summary") or [])
    sha_ = PUB.commit(head, files, location_message(summary, objects, note, login), login)
    _step(uuid, "suites")
    PUB.git("checkout", "--quiet", "--force", "--detach", sha_, cwd=tree, timeout=publisher.PUSH_TIMEOUT)
    res_dir = l4_res()
    run, notes = l4_suites(tree, res_dir)
    env = {"LAVA_RES": res_dir, "LAVA_LOCATION_EDITOR_GIT": "0"}
    results = publisher.run_suites(tree, run, env=env, jobs=L4_JOBS, timeout=L4_TIMEOUT,
                                   drop=("LAVA_LOC_OVERLAY", "LAVA_PASSAGES", "LAVA_PLACEMENTS", "LAVA_SCHEDULE",
                                         "LAVA_ART_STORE", "LAVA_ART_RES", "LAVA_ART_CACHE",
                                         "LAVA_LOCATION_EDITOR_CACHE", "LAVA_ART_IMAGE_PIXELS"),
                                   scratch=os.path.join(WORK, "publish", "suites-" + uuid[:8]))
    shutil.rmtree(os.path.join(WORK, "publish", "suites-" + uuid[:8]), ignore_errors=True)
    red = [r for r in results if not r["ok"]]
    if red:
        return 422, {"error": "Наборы проверок на этом коммите красные (%s): в %s ничего не ушло"
                              % (", ".join(r["suite"] for r in red), PUB.branch),
                     "suites": results, "suite_notes": notes, "problems": []}
    _step(uuid, "push")
    try:
        if PUB.before_push:
            PUB.before_push(attempt)
        pushed = PUB.push(sha_)
    except publisher.GitError as exc:
        return 502, PUB.failed(publisher.PUSH_FAILED, exc)
    if not pushed:
        return None
    return 200, {"commit": sha_, "head": PUB._about(sha_), "summary": summary, "id": saved.get("id"),
                 "renumbered": saved.get("renumbered") or {}, "files": sorted(files),
                 "objects": objects, "suites": results, "suite_notes": notes,
                 "url": ("%s/commit/%s" % (PUB.web, sha_)) if PUB.web else ""}


def publish_save(model, author):
    """`publish-save`: the save a publish makes in a worktree of origin's
    main (this editor configured on its data/): a new place takes the first
    free number there. {code, body, id, renumbered, summary}."""
    if not isinstance(model, dict):
        return {"code": 400, "body": {"error": "model: объект"}}
    temp = model.get("id") if temp_uuid(model.get("id")) else None
    renumbered = {}
    if temp:
        real = next_free_id()
        model = assign_id(model, temp, real)
        renumbered[temp] = real
        etag = etag_of(location_state(real))
    else:
        etag = str(model.get("etag") or "")
    try:
        model = _clean(model)
    except Refused as exc:
        return {"code": 400, "body": {"error": str(exc)}}
    summary = describe_against(model)
    code, out = save(model, etag, author)
    out = {k: v for k, v in out.items() if k != "model"}
    return {"code": code, "body": out, "id": int(model["id"]), "renumbered": renumbered, "summary": summary}


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


def entry():
    """The built page's script and stylesheets, for a page that embeds it
    (the admin panel's /admin/locations)."""
    with open(os.path.join(UI, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    js = re.search(r'<script[^>]*\ssrc="(?:\./|/)?(assets/[^"]+\.js)"', html)
    css = re.findall(r'<link[^>]*\shref="(?:\./|/)?(assets/[^"]+\.css)"', html)
    return {"js": js.group(1) if js else None, "css": css}


# What a write in publish mode is: an admin's, named by X-Lava-Admin.
WRITES = ("/api/new", "/api/save", "/api/draft", "/api/draftdel", "/api/publish", "/api/object",
          "/api/object/update", "/api/object/delete")


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
        Publish mode sits behind the panel, under the container's name.
        True when the request was refused."""
        if PUB is not None:
            return False
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
        if url == "/api/entry":
            try:
                return self._send(entry())
            except OSError:
                return self._send({"error": "страница редактора не собрана (tools/location_editor_ui/build.sh)"},
                                  code=500)
        if url == "/api/info":
            return self._info()
        if PUB is not None:
            if url == "/api/drafts":
                return self._send({"drafts": drafts_list(), "objects": PENDING.listing()})
            m = re.fullmatch(r"/api/draft/([0-9a-f]{32})", url)
            if m:
                d = DRAFTS.get(m.group(1))
                return self._send(dict(d, stale=draft_stale(d)))
            m = re.fullmatch(r"/api/diff/([0-9a-f]{32})", url)
            if m:
                return self._send(draft_diff(m.group(1)))
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
            out = objects_info()
            if PUB is not None:
                out["pending"] = {o["id"]: o["kind"] for o in PENDING.listing()}
            return self._send(out)
        m = re.fullmatch(r"/api/object/(c_[a-z0-9_]{1,40})/([a-z0-9_-]{1,40}\.(?:png|jpg|jpeg))", url)
        if m:
            return self._file(os.path.join(P.objects, m.group(1)), m.group(2))
        return self._send({"error": "not found"}, code=404)

    def _info(self):
        out = info()
        if PUB is None:
            return self._send(out)
        # A page load fetches: main moved on, and the editor restarts on it
        # (the entrypoint checks it out), so that what the page shows and
        # checks against is main as it is.
        stale = None if PUB.restarting else PUB.fetch_now_and_then()
        try:
            moved = not stale and PUB.rev(PUB.remote_ref) != PUB.rev("HEAD")
        except publisher.GitError as exc:
            stale, moved = str(exc), False
        if PUB.restarting or moved:
            self._send({"restarting": True, "error": publisher.RESTARTING % PUB.branch}, code=503)
            return PUB.restart()
        head = PUB._about("HEAD")
        out.update(mode="publish", commit=head["sha"], branch=PUB.branch, web=PUB.web, head=head,
                   pending_objects=PENDING.listing(), restart_minutes=RESTARTS_AFTER, warn_seconds=WARN_SECONDS)
        if stale:
            out["stale"] = publisher.reason(stale)
        return self._send(out)

    def _login(self):
        return publisher.clean_login(publisher.header_text(self.headers.get("X-Lava-Admin") or ""))

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
        login = "owner"
        if PUB is not None:
            if PUB.restarting and url in WRITES:
                return self._send({"restarting": True, "error": publisher.RESTARTING % PUB.branch}, code=503)
            login = self._login()
            if url in WRITES and not login:
                return self._send({"error": "нет X-Lava-Admin: кто правит?"}, code=400)
        if url == "/api/new":
            if PUB is not None:
                return self._send(draft_new(body, login))
            return self._send(new_model(body.get("title"), body.get("from"), body.get("empty"),
                                        body.get("why") or "", new_id=body.get("id")))
        if url == "/api/edit":
            # a new place of publish mode ("new:<uuid>") is edited under a number
            model, temp, n = numbered(body.get("model"))
            model, inf = edit(_clean(model), body.get("op") or {})
            return self._send(dict(inf, model=lettered(model, temp, n)))
        if url == "/api/check":
            model, temp, n = numbered(body.get("model"))
            got = check(model, bool(body.get("quick")), author=login)
            problems_back(got["problems"], temp, n)
            return self._send(got)
        if url == "/api/save" and PUB is None:
            code, out = save(body.get("model"), str(body.get("etag") or ""))
            return self._send(out, code=code)
        if url == "/api/render":
            model, _temp, _n = numbered(body.get("model"))
            png, _rep = render_png(_clean(model), body.get("layers") or "art",
                                   _scale(body.get("scale")), body.get("order") or "reverse")
            return self._send(png, "image/png")
        if url == "/api/object":
            got = object_upload(body)
            if PUB is not None:
                PENDING.record(got["id"])
            return self._send(got)
        if url == "/api/object/update":
            got = object_update(body)
            if PUB is not None:
                PENDING.record(got["id"])
            return self._send(got)
        if url == "/api/object/delete":
            if PUB is not None:
                users = draft_users(str(body.get("id") or ""))
                if users:
                    raise Conflict("объект стоит в черновиках %s: сначала уберите его оттуда" % ", ".join(users),
                                   {"drafts": users})
            got = object_delete(body)
            if PUB is not None:
                PENDING.record(got["id"])
            return self._send(got)
        if PUB is not None:
            # publish mode: what the page saves is a draft, and «Опубликовать» a commit to main
            if url in ("/api/save", "/api/draft"):
                return self._send(draft_save(body, login))
            if url == "/api/draftdel":
                return self._send(draft_delete(body))
            if url == "/api/publish":
                code, out = publish_start(body, login)
                return self._send(out, code=code)
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
    """What the page asks for first, read in the background; in publish
    mode also the libraries the original uses most."""
    _background("names", creatures)
    _background("list", locations)
    _background("usage", lambda: usage(True))
    if PUB is not None and have_pictures():
        _background("libraries", _warm_libraries)


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
    ap.add_argument("--repo", help="publish mode: a git clone whose origin is the source of truth")
    ap.add_argument("--branch", default=os.environ.get("LAVA_LOCATIONS_BRANCH") or "main",
                    help="the branch publish mode pushes to (LAVA_LOCATIONS_BRANCH, main)")
    ap.add_argument("--work", default=os.environ.get("LAVA_LOCATIONS_WORK"),
                    help="publish mode: the folder of the drafts and the pending objects (LAVA_LOCATIONS_WORK)")
    ap.add_argument("--store", default=os.environ.get("LAVA_ART_STORE"),
                    help="the release store, <aa>/<sha256> (LAVA_ART_STORE)")
    ap.add_argument("--cache", default=os.environ.get("LAVA_ART_CACHE"),
                    help="the art cache (LAVA_ART_CACHE)")
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
    p = sub.add_parser("publish-save", help="publish mode's save on a worktree of origin's main (a model file)")
    p.add_argument("file")
    p.add_argument("--author", default="owner")
    p.add_argument("--out", required=True, help="where the result goes, as JSON")
    a = ap.parse_args(argv)
    configure(a.data, a.objects)
    cmd = a.cmd or "serve"
    if a.repo:
        if cmd != "serve":
            print("--repo is for serving the page", file=sys.stderr)
            return 2
        configure_repo(a.repo, a.branch, os.environ.get("LAVA_LOCATIONS_WEB", ""), a.work, a.store, a.cache)
    try:
        if cmd == "serve":
            srv = serve(a.port, a.host)
            url = "http://%s:%d/" % (srv.bound_host, srv.server_address[1])
            if PUB is not None:
                print("location editor, publish mode: %s -> origin/%s, on %s (work: %s, RES: %s)"
                      % (PUB.repo, PUB.branch, url, WORK, world.RES), flush=True)
            else:
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
        if cmd == "publish-save":
            with open(a.file, encoding="utf-8") as fh:
                model = json.load(fh)
            got = publish_save(model, a.author)
            write_atomic(os.path.abspath(a.out), json.dumps(got, ensure_ascii=False).encode("utf-8"))
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
