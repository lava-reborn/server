#!/usr/bin/env python3
"""Location art for the location editor: the original's SWFs as pictures, a
location drawn the way the client draws it, mob icons, and the index CI
checks a location's references against.

    python3 tools/location_art.py index [-o data/location_art.json] [--check]
    python3 tools/location_art.py warm [--jobs 8] [--only libs,sprites,backgrounds,mobs]
    python3 tools/location_art.py render ID|PATH -o OUT.png [--layers art,obstacles]
                                   [--scale 0.5] [--order reverse|file] [--extra-row]
    python3 tools/location_art.py lint [ID|PATH ...]
    python3 tools/location_art.py stats

WHERE THE BYTES COME FROM (Art.read). The release's list of files, as
client/build.py layers it: client/base.txt less client/remove.txt, then
client/extra.txt, then client/files/**, then the owner's own objects
(client/objects/manifest.json, ext sprites c_*). A path's bytes are taken
from client/files/ (in git), else from a store laid out <aa>/<sha256> like
the release store (LAVA_ART_STORE, folders separated by os.pathsep), else
from a client's res folder (LAVA_ART_RES; by default the launcher-installed
client on the Desktop) -- and only if their sha256 is the one the release
lists. Pictures need Pillow and numpy (WSL ~/venvs/lavagd); index, lint and
the release list are standard library, as CI is.

THE CACHE (LAVA_ART_CACHE, default ~/.cache/lava-location-editor) is keyed
by the sha256 of the SWF, so it never goes stale and two editors can share
it. <sha>/manifest.json:

    {"v": 1, "sha": ..., "path": the release path first asked for,
     "bytes": n, "frames": root frames (nested animation counted),
     "stage": picture of the root's first frame, or null,
     "symbols": {exported name: picture, or {"empty": true}},
     "errors": [...]}
    picture = {"file", "w", "h", "ox", "oy", "opaque", "thumb", "tw", "th"}

file is JPEG (q88) when the picture is opaque, else WebP (q90, alpha);
thumb a WebP (q80) at most 128 px. (ox, oy) is where the picture's top-left
sits from the SWF's origin. A symbol is SpriteSource.getFromLib's bitmap and
the stage getBitmap's, both cut to the shapes' bounds (tools/swfx.py, fix 2).
A mob's stand frame is <sha>/mob-s<seq>-d<direction>.json with
stand-<frame>.webp (full size, trimmed to its pixels, ox/oy from the
registration point) and icon-<frame>.webp (at most 64 px).

HOW THE CLIENT DRAWS A LOCATION (recon/as-src/lol/core/location):

  background   the library symbol bg (type lib; a painted library that
               exports nothing serves its own picture) or
               locations/libs/background/<id>.swf (ext), tiled from (0, 0)
               over W*40 x H*15 (DisplayLocBackground.fillBackground)
  decals       <bgdecoration>: the picture's top-left at (dx, dy), painted
               into the background (drawBGDecor), the last one in the file
               first: LDParser walks the children with for..in, which in
               AVM1 runs from the end (order="file" is kept for comparison)
  zones        a zoneHex at every exit cell, at positions rounded to 5 px
               (drawn here as a pale hex)
  sprites      lib: the symbol's top-left at cell_px(anchor) + (dx, dy);
               ext: the SWF's origin there (a live clip, animating at 25 fps;
               drawn here at its first frame); in LDepthManager's order
               (tools/lavaloc.py depth_sort, ties as AVM1's own sort)
  mobs         a walker's stand frame on its cell, put among the sprites as
               listZSort puts it (lavaloc.walker_index)

Checked against the real Flash Player 32 (the launcher's), headless under
Wine in docker, driving the client's own LDParser, LDepthManager,
SourceLibrary, DisplaySprite and AnimationSprite copied out of main.swf
(2026-10-12): for locations 1, 35, 266, 270 and 522 the parse order of
sprites and decals and the zSort order are the same as here, and 1:1 crops
of the composed scene differ by the cache's JPEG/WebP only (mean 1.7-2.6 of
255, 99th percentile at most 19). tools/test_lavaloc.py pins the player's
orders.

An anchor off the client's grid -- the extra row y == H, which 199 of the
original's files use -- has no cell there (LocationGrid.getCellFromGrid is
undefined), so the client sets no position and the picture lands at dx, dy
from the location's top-left corner, in its place in the depth order (seen
in the real Flash Player 32, 2026-10-12); render draws it so, or at the
cell beyond the grid with extra_row=True.
"""
import argparse
import collections
import hashlib
import importlib.util
import io
import json
import os
import re
import struct
import sys
import threading
import time
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lavaloc as L  # noqa: E402

CACHE_V = 1
INDEX = os.path.join(ROOT, "data", "location_art.json")
DEFAULT_RES = ("/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res",
               r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res")
LIBS = "locations/libs/"
SPRITES = "locations/libs/sprite/"
BACKGROUNDS = "locations/libs/background/"
TRACKS = "sounds/tracks/"
THUMB, ICON = 128, 64
JPEG_Q, WEBP_Q, THUMB_Q, ICON_Q = 88, 90, 80, 85
ART_LAYERS = ("background", "decals", "sprites")
# The largest canvas render() draws, in pixels, before and after the scale
# (64x128 cells are 2560 x 1920, about 4.9 M): anything bigger is refused
# before Image.new takes the memory.
MAX_CANVAS = 40_000_000
LAYERS = ("background", "decals", "zones", "sprites", "mobs",
          "obstacles", "exits", "entries", "warentries", "spawns", "grid", "extrarow")
OVERLAYS = ("obstacles", "exits", "entries", "warentries", "spawns", "grid", "extrarow")
SHA = re.compile(r"[0-9a-f]{64}")
CACHE_NAME = re.compile(r"[A-Za-z0-9_.-]{1,80}")


def lib_path(name):
    return LIBS + name + ".swf"


def sprite_path(sid):
    return SPRITES + sid + ".swf"


def background_path(bid):
    return BACKGROUNDS + bid + ".swf"


def track_path(name):
    return TRACKS + name + ".swf"


def _pil():
    from PIL import Image, ImageDraw
    return Image, ImageDraw


def _client_build():
    spec = importlib.util.spec_from_file_location(
        "lava_client_build", os.path.join(ROOT, "client", "build.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _world():
    """server/world.py: RES, the folder the server reads locations from."""
    sdir = os.path.join(ROOT, "server")
    if sdir not in sys.path:
        sys.path.insert(1, sdir)
    import world
    return world


def _env_dirs(name, default):
    v = os.environ.get(name)
    if v:
        return [d for d in v.split(os.pathsep) if d]
    return [d for d in default if os.path.isdir(d)]


# --- the release's files ---------------------------------------------------------------

Entry = collections.namedtuple("Entry", "path sha size origin")


def read_release(repo=ROOT, objects=None):
    """{path: Entry} of a release built from repo (client/build.py's layers
    less what it generates), plus the owner's objects (those of `objects`,
    by default repo's client/objects) as origin "object" (sha: of their
    frames' bytes). A list client/build.py refuses (it stops the build with
    SystemExit) is a ValueError here, with the reason."""
    build = _client_build()
    cdir = os.path.join(repo, "client")
    out = {}
    try:
        base = build.read_entries(os.path.join(cdir, "base.txt"), "lava-base 1")
        removed = build.read_paths(os.path.join(cdir, "remove.txt"))
        extra = build.read_entries(os.path.join(cdir, "extra.txt"), "lava-extra 1")
    except SystemExit as exc:
        raise ValueError("client/build.py: %s" % (exc.code if exc.code is not None else "refused"))
    for p, (sha, size) in base.items():
        out[p] = Entry(p, sha, size, "base")
    for p in removed:
        out.pop(p, None)
    for p, (sha, size) in extra.items():
        out[p] = Entry(p, sha, size, "extra")
    fdir = os.path.join(cdir, "files")
    for d, _dirs, names in os.walk(fdir):
        for f in names:
            full = os.path.join(d, f)
            p = os.path.relpath(full, fdir).replace(os.sep, "/")
            if p in (".gitkeep", "README.md"):
                continue
            with open(full, "rb") as fh:
                data = fh.read()
            out[p] = Entry(p, hashlib.sha256(data).hexdigest(), len(data), "files")
    for oid, obj in read_objects(repo, objects).items():
        p = object_path(oid, obj)
        if p in out:
            continue        # a SWF committed under client/files wins
        # The picture's sha: of the frames' bytes and how they play, which
        # is all swfgen makes the SWF from (the anchor and the cells are
        # the XML's, never the picture's).
        h = hashlib.sha256(b"lava-object 2\n")
        h.update(json.dumps([obj.get("frames"), obj.get("fps")]).encode())
        size = 0
        for fr in _frames(obj):
            try:
                with open(object_file(repo, oid, fr, objects), "rb") as fh:
                    data = fh.read()
            except OSError:
                data = b""
            h.update(hashlib.sha256(data).digest())
            size += len(data)
        out[p] = Entry(p, h.hexdigest(), size, "object")
    return out


def _custom_objects():
    import custom_objects
    return custom_objects


def objects_dir(repo=ROOT, objects=None):
    """The owner's objects folder: `objects`, else repo's client/objects."""
    return objects or os.path.join(repo, "client", "objects")


def read_objects(repo=ROOT, objects=None):
    """The owner's objects as client/objects/manifest.json has them
    (tools/custom_objects.py load_raw): {id: entry}, an entry's frames
    being file names in client/objects/<id>/ (or in the `objects` folder).
    Entries whose id is not an object id are left out; {} without a
    manifest or when it does not read (custom_objects.py check says why)."""
    co = _custom_objects()
    try:
        raw = co.load_raw(objects_dir(repo, objects))
    except co.Refused:
        return {}
    return {oid: e for oid, e in raw.items() if co.ID.fullmatch(oid) and isinstance(e, dict)}


def _frames(obj):
    fr = obj.get("frames")
    return [f for f in fr if isinstance(f, str)] if isinstance(fr, list) else []


def object_path(oid, obj):
    """The release path of an object: its sprite or background file."""
    return (BACKGROUNDS if obj.get("kind") == "background" else SPRITES) + oid + ".swf"


def object_file(repo, oid, frame, objects=None):
    """A picture of an object: client/objects/<id>/<frame>."""
    return os.path.join(objects_dir(repo, objects), oid, frame)


def object_frames(obj):
    """Game frames (25 a second) the object's SWF plays: each picture held
    round(25 / fps) of them, as tools/swfgen.py writes it; 1 for a still."""
    n = len(_frames(obj))
    if n <= 1:
        return 1
    try:
        return n * _custom_objects().swfgen.hold_for(obj.get("fps"))
    except Exception:
        return n


# --- a light look at a SWF, standard library only --------------------------------------------

def swf_body(raw):
    """(version, body after the 8-byte header) of a CWS/FWS/ZWS file."""
    sig = raw[:3]
    if sig == b"FWS":
        return raw[3], raw[8:]
    if sig == b"CWS":
        return raw[3], zlib.decompress(raw[8:])
    if sig == b"ZWS":
        import lzma
        props = raw[12:17]
        filt = lzma._decode_filter_properties(lzma.FILTER_LZMA1, props)
        return raw[3], lzma.decompress(raw[17:], format=lzma.FORMAT_RAW, filters=[filt])
    raise ValueError("not a swf: %r" % sig)


def swf_summary(raw):
    """What the index needs of a SWF, without decoding a picture:
    {"exports": [names], "stage": the root's first frame places something,
     "frames": root frames, or the frames of a clip placed there if more}."""
    import swfx
    _v, body = swf_body(raw)
    _rect, p = swfx.read_rect(body, 0)
    p += 4
    exports, sprites = [], {}       # sprites: cid -> (frames, cids placed in its frame 1)

    def placed_cid(code, t):
        if code == 4:
            return struct.unpack_from("<H", t, 0)[0]
        fl = t[0]
        q = 2 if code == 70 else 1
        fl2 = t[1] if code == 70 else 0
        q += 2
        if code == 70 and (fl2 & 0x08 or (fl2 & 0x10 and fl & 0x02)):
            q = t.index(b"\0", q) + 1
        return struct.unpack_from("<H", t, q)[0] if fl & 0x02 else None

    def first_frame(data, pos, end):
        out = set()
        for code, t in swfx.iter_tags(data, pos, end):
            if code == 1:
                break
            if code in (4, 26, 70):
                c = placed_cid(code, t)
                if c is not None:
                    out.add(c)
        return out

    root_frames, placed, first = 0, set(), True
    for code, t in swfx.iter_tags(body, p, len(body)):
        if code == 1:
            root_frames += 1
            first = False
        elif code in (56, 76):
            n, = struct.unpack_from("<H", t, 0)
            q = 2
            for _ in range(n):
                q += 2
                e = t.index(b"\0", q)
                exports.append(t[q:e].decode("utf-8", "replace"))
                q = e + 1
        elif code == 39:
            cid, nf = struct.unpack_from("<HH", t, 0)
            sprites[cid] = (nf, first_frame(t, 4, len(t)))
        elif code in (4, 26, 70) and first:
            c = placed_cid(code, t)
            if c is not None:
                placed.add(c)
    # an animation nested in clips placed on the first frame counts too
    frames, seen, todo = root_frames, set(), list(placed)
    while todo:
        c = todo.pop()
        if c in seen or c not in sprites:
            continue
        seen.add(c)
        frames = max(frames, sprites[c][0])
        todo.extend(sprites[c][1])
    return {"exports": sorted(set(exports)), "stage": bool(placed), "frames": max(1, frames)}


# --- the index -------------------------------------------------------------------------------------

def build_index(art):
    """data/location_art.json from the release and its SWFs."""
    rel = art.release
    libs, sprites, animated, backgrounds, tracks, missing = {}, [], {}, [], [], []
    for p in sorted(rel):
        if p.startswith(LIBS) and p.endswith(".swf") and "/" not in p[len(LIBS):]:
            name = p[len(LIBS):-4]
            raw = art.read(p)
            if raw is None:
                missing.append(p)
                continue
            try:
                s = swf_summary(raw)
            except Exception:       # the 36-byte stub
                s = {"exports": [], "stage": False, "frames": 1}
            libs[name] = {"sha": rel[p].sha[:16], "stage": s["stage"], "exports": s["exports"]}
        elif p.startswith(SPRITES) and p.endswith(".swf") and rel[p].origin != "object":
            sid = p[len(SPRITES):-4]
            sprites.append(sid)
            raw = art.read(p)
            if raw is None:
                missing.append(p)
                continue
            try:
                s = swf_summary(raw)
            except Exception:
                continue
            if s["frames"] > 1:
                animated[sid] = s["frames"]
        elif p.startswith(BACKGROUNDS) and p.endswith(".swf") and rel[p].origin != "object":
            backgrounds.append(p[len(BACKGROUNDS):-4])
        elif p.startswith(TRACKS) and p.endswith(".swf"):
            tracks.append(p[len(TRACKS):-4])
    if missing:
        raise SystemExit("index: no bytes for %d SWFs (LAVA_ART_RES / LAVA_ART_STORE), e.g. %s"
                         % (len(missing), missing[:3]))
    return {"_": ("What location art the release has, read from its SWFs, so that a "
                  "location's references can be checked without them (tools/location_art.py "
                  "lint, tools/test_location_art.py). libraries: name -> sha (16 hex of "
                  "client/base.txt's), stage (the root draws a picture: a painted library, "
                  "whose picture also stands in for any name it does not export), exports "
                  "(the names <sprite type=lib>, <bgdecoration> and <background> may use). "
                  "sprites: ext ids (locations/libs/sprite/<id>.swf), animated: their frame "
                  "counts above 1, backgrounds: ext backgrounds, tracks: bgsound names. Made by "
                  "python3 tools/location_art.py index; do not edit."),
            "format": 1, "libraries": libs, "sprites": sprites, "animated": animated,
            "backgrounds": backgrounds, "tracks": tracks}


def dump_index(ix):
    """One library per line, names wrapped: diffable, about 80 KB."""
    def wrap(names, indent):
        lines, cur = [], ""
        for n in names:
            s = json.dumps(n, ensure_ascii=False)
            if cur and len(cur) + len(s) + 2 > 100:
                lines.append(cur + ",")
                cur = ""
            cur = cur + ", " + s if cur else s
        if cur:
            lines.append(cur)
        if not lines:
            return "[]"
        return "[\n" + "\n".join(indent + "  " + ln for ln in lines) + "\n" + indent + "]"
    out = ["{"]
    out.append(' "_": %s,' % json.dumps(ix["_"], ensure_ascii=False))
    out.append(' "format": %d,' % ix["format"])
    out.append(' "libraries": {')
    names = sorted(ix["libraries"])
    for i, n in enumerate(names):
        e = ix["libraries"][n]
        out.append('  %s: {"sha": %s, "stage": %s, "exports": %s}%s' % (
            json.dumps(n, ensure_ascii=False), json.dumps(e["sha"]), json.dumps(e["stage"]),
            json.dumps(e["exports"], ensure_ascii=False), "," if i < len(names) - 1 else ""))
    out.append(" },")
    out.append(' "sprites": %s,' % wrap(ix["sprites"], " "))
    out.append(' "animated": %s,' % json.dumps(ix["animated"], ensure_ascii=False, sort_keys=True))
    out.append(' "backgrounds": %s,' % json.dumps(ix["backgrounds"], ensure_ascii=False))
    out.append(' "tracks": %s' % json.dumps(ix["tracks"], ensure_ascii=False))
    out.append("}")
    return "\n".join(out) + "\n"


def load_index(path=INDEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def local_ext(repo=ROOT, objects=None):
    """Ext sprite and background ids a release of repo has beyond the
    original: client/files and the owner's objects. ({sprites}, {backgrounds})"""
    sprites, backgrounds = set(), set()
    fdir = os.path.join(repo, "client", "files")
    for sub, bag in ((SPRITES, sprites), (BACKGROUNDS, backgrounds)):
        d = os.path.join(fdir, *sub.rstrip("/").split("/"))
        if os.path.isdir(d):
            bag.update(f[:-4] for f in os.listdir(d) if f.endswith(".swf"))
    for oid, obj in read_objects(repo, objects).items():
        (backgrounds if obj.get("kind") == "background" else sprites).add(oid)
    return sprites, backgrounds


def art_problems(m, index=None, extra=None):
    """What of a location (lavaloc model) the client cannot draw as meant,
    by the index alone: [{what, id, type, count, why}], what in library,
    background, sprite, decal, bgsound. extra = local_ext() of the repo.
    File names are matched as the launcher serves them, regardless of case
    (Release.Find); symbol names exactly."""
    ix = index if index is not None else load_index()
    ext_sprites, ext_bgs = extra if extra is not None else local_ext()
    sprites = {s.lower() for s in ix["sprites"]} | {s.lower() for s in ext_sprites}
    backgrounds = {s.lower() for s in ix["backgrounds"]} | {s.lower() for s in ext_bgs}
    tracks = {s.lower() for s in ix["tracks"]}
    libs = {k.lower(): v for k, v in ix["libraries"].items()}
    attrs = m["attrs"]
    library = attrs.get("library", "")
    lib = libs.get(library.lower())
    exports = set(lib["exports"]) if lib else set()
    stage = bool(lib and lib["stage"])
    found = collections.Counter()

    if lib is None:
        found[("library", library, "", "no %s%s.swf in the release" % (LIBS, library))] += 1

    def check_lib(what, rid):
        if rid in exports:
            return
        if lib is None:
            return
        if stage:
            if what != "background":
                found[(what, rid, "lib", "not exported by %s: the client draws the library's "
                       "whole picture there" % library)] += 1
            return
        found[(what, rid, "lib", "not exported by %s: nothing is drawn" % library)] += 1

    bg = m.get("background") or {"type": attrs.get("bgExt"), "id": attrs.get("bg", "")}
    if bg.get("type") == "ext":
        if (bg.get("id") or "").lower() not in backgrounds:
            found[("background", bg.get("id"), "ext", "no %s%s.swf" % (BACKGROUNDS, bg.get("id")))] += 1
    else:
        check_lib("background", bg.get("id"))
    for what, items in (("sprite", m["sprites"]), ("decal", m["bgdecorations"])):
        for it in items:
            n = len(it["anchors"]) if what == "sprite" else 1
            if it.get("type") == "ext":
                if it["id"].lower() not in sprites:
                    found[(what, it["id"], "ext", "no %s%s.swf: nothing is drawn" % (SPRITES, it["id"]))] += n
            else:
                for _ in range(n):
                    check_lib(what, it["id"])
    snd = attrs.get("bgsound", "")
    if snd and snd.lower() not in tracks:
        found[("bgsound", snd, "", "no %s%s.swf: no music" % (TRACKS, snd))] += 1
    return [{"what": w, "id": i, "type": t, "count": c, "why": y}
            for (w, i, t, y), c in sorted(found.items())]


# --- extraction ---------------------------------------------------------------------------------------

def _encode(img, thumb=THUMB):
    """(file bytes, ext, opaque, thumb bytes, (tw, th))."""
    Image, _ = _pil()
    opaque = img.mode != "RGBA" or img.getextrema()[3][0] == 255
    buf = io.BytesIO()
    if opaque:
        img.convert("RGB").save(buf, "JPEG", quality=JPEG_Q)
        ext = ".jpg"
    else:
        img.save(buf, "WEBP", quality=WEBP_Q, method=4)
        ext = ".webp"
    th = img.copy()
    th.thumbnail((thumb, thumb), Image.LANCZOS)
    tb = io.BytesIO()
    th.save(tb, "WEBP", quality=THUMB_Q, method=4)
    return buf.getvalue(), ext, opaque, tb.getvalue(), th.size


def _picture(files, stem, img, off):
    data, ext, opaque, tdata, tsize = _encode(img)
    files[stem + ext] = data
    files["t" + stem + ".webp"] = tdata
    return {"file": stem + ext, "w": img.size[0], "h": img.size[1],
            "ox": off[0], "oy": off[1], "opaque": opaque,
            "thumb": "t" + stem + ".webp", "tw": tsize[0], "th": tsize[1]}


def extract_swf(data, sha, path):
    """({file name: bytes}, manifest) of one SWF: every export as
    getFromLib draws it, and the root's first frame as getBitmap does."""
    import swfx
    files = {}
    man = {"v": CACHE_V, "sha": sha, "path": path, "bytes": len(data), "frames": 1,
           "stage": None, "symbols": {}, "errors": []}
    try:
        s = swfx.Swf(data)
    except Exception as e:      # the 36-byte stub
        man["errors"].append("unreadable: %s" % e)
        return files, man
    try:
        man["frames"] = swf_summary(data)["frames"]
    except Exception:
        pass
    for i, name in enumerate(sorted(s.exports)):
        try:
            img, off = s.library_bitmap(name)
        except Exception as e:
            man["errors"].append("%s: %s" % (name, e))
            img = None
        if img is None:
            man["symbols"][name] = {"empty": True}
            continue
        man["symbols"][name] = _picture(files, "s%03d" % i, img, off)
    try:
        img, off = s.root_bitmap()
    except Exception as e:
        man["errors"].append("stage: %s" % e)
        img = None
    if img is not None and img.getbbox():
        man["stage"] = _picture(files, "stage", img, off)
    return files, man


def extract_object(repo, oid, obj, sha, path, objects=None):
    """The owner's object: its first picture, the origin at its top-left
    (client/objects -> swfgen puts the picture at the SWF's (0, 0); checked
    in the real Flash Player 32 by tools/flash_headless)."""
    Image, _ = _pil()
    files = {}
    frames = _frames(obj)
    man = {"v": CACHE_V, "sha": sha, "path": path, "bytes": 0, "frames": object_frames(obj),
           "stage": None, "symbols": {}, "errors": [], "object": oid}
    try:
        img = Image.open(object_file(repo, oid, frames[0], objects)).convert("RGBA")
        man["stage"] = _picture(files, "stage", img, (0, 0))
    except Exception as e:
        man["errors"].append("picture: %s" % e)
    return files, man


def extract_mob(data, sha, path, frame):
    """A mob's stand frame (0-based timeline index): full size trimmed to
    its pixels, offset from the registration point, and a 64 px icon."""
    import swfx
    Image, _ = _pil()
    s = swfx.Swf(data)
    if frame >= len(s.timeline):
        raise ValueError("frame %d of %d" % (frame, len(s.timeline)))
    img, off = s.render(s.timeline[frame], frame, crop="alpha")
    if img is None:
        raise ValueError("empty frame %d" % frame)
    files = {}
    b = io.BytesIO()
    img.save(b, "WEBP", quality=WEBP_Q, method=4)
    files["stand-%d.webp" % frame] = b.getvalue()
    ic = img.copy()
    ic.thumbnail((ICON, ICON), Image.LANCZOS)
    b = io.BytesIO()
    ic.save(b, "WEBP", quality=ICON_Q, method=4)
    files["icon-%d.webp" % frame] = b.getvalue()
    man = {"v": CACHE_V, "sha": sha, "path": path, "frame": frame,
           "stand": {"file": "stand-%d.webp" % frame, "w": img.size[0], "h": img.size[1],
                     "ox": off[0], "oy": off[1]},
           "icon": {"file": "icon-%d.webp" % frame, "w": ic.size[0], "h": ic.size[1]}}
    return files, man


# --- the art store ---------------------------------------------------------------------------------------

class Art:
    """Pictures of a release's location art, cached by SWF sha256."""

    def __init__(self, repo=ROOT, res=None, store=None, cache=None, objects=None):
        self.repo = repo
        # the owner's objects: repo's client/objects, or the folder an
        # editor works in (tools/location_editor.py --objects)
        self.objects = objects_dir(repo, objects)
        self.res_dirs = list(res) if res is not None else _env_dirs("LAVA_ART_RES", DEFAULT_RES)
        self.store_dirs = list(store) if store is not None else _env_dirs("LAVA_ART_STORE", ())
        self.cache = cache or os.environ.get("LAVA_ART_CACHE") or \
            os.path.join(os.path.expanduser("~"), ".cache", "lava-location-editor")
        self._release = None
        self._lower = None
        self._manifests = {}
        self._images = collections.OrderedDict()
        self._lock = threading.Lock()
        self._mobs = None
        self._mob_memo = {}

    # -- the release ---------------------------------------------------------------
    @property
    def release(self):
        if self._release is None:
            self._release = read_release(self.repo, self.objects)
            self._lower = {p.lower(): p for p in self._release}
        return self._release

    def entry(self, path):
        """The release's Entry for a path (its own spelling if it differs
        in case only), or None."""
        rel = self.release
        e = rel.get(path)
        if e is None:
            p = self._lower.get(path.lower())
            e = rel.get(p) if p else None
        return e

    def read(self, path):
        """The bytes of a release file, checked against its sha256; None
        when no source has them."""
        e = self.entry(path)
        if e is None or e.origin == "object":
            return None
        if e.origin == "files":
            with open(os.path.join(self.repo, "client", "files", *e.path.split("/")), "rb") as fh:
                return fh.read()
        for d in self.store_dirs:
            f = os.path.join(d, e.sha[:2], e.sha)
            if os.path.isfile(f):
                with open(f, "rb") as fh:
                    data = fh.read()
                if hashlib.sha256(data).hexdigest() == e.sha:
                    return data
        for d in self.res_dirs:
            f = os.path.join(d, *e.path.split("/"))
            if os.path.isfile(f) and os.path.getsize(f) == e.size:
                with open(f, "rb") as fh:
                    data = fh.read()
                if hashlib.sha256(data).hexdigest() == e.sha:
                    return data
        return None

    # -- the cache -----------------------------------------------------------------
    def cache_file(self, sha, name):
        """The absolute path of a cached file, for serving it; None for a
        name that is not one (no traversal) or a file that is not there."""
        if not SHA.fullmatch(sha or "") or not CACHE_NAME.fullmatch(name or "") or name.startswith("."):
            return None
        f = os.path.join(self.cache, sha, name)
        return f if os.path.isfile(f) else None

    def _publish(self, sha, files, mname, man):
        d = os.path.join(self.cache, sha)
        os.makedirs(d, exist_ok=True)
        tag = ".%d.%d.tmp" % (os.getpid(), threading.get_ident())
        for name, data in files.items():
            with open(os.path.join(d, name + tag), "wb") as fh:
                fh.write(data)
            os.replace(os.path.join(d, name + tag), os.path.join(d, name))
        with open(os.path.join(d, mname + tag), "w", encoding="utf-8") as fh:
            json.dump(man, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(os.path.join(d, mname + tag), os.path.join(d, mname))

    def _cached(self, sha, mname="manifest.json"):
        key = (sha, mname)
        man = self._manifests.get(key)
        if man is not None:
            return man
        try:
            with open(os.path.join(self.cache, sha, mname), encoding="utf-8") as fh:
                man = json.load(fh)
        except (OSError, ValueError):
            return None
        if man.get("v") != CACHE_V:
            return None
        self._manifests[key] = man
        return man

    def ensure(self, path):
        """The manifest of a release SWF (or object), extracting it into the
        cache the first time; None when the release has no such file or no
        source has its bytes."""
        e = self.entry(path)
        if e is None:
            return None
        man = self._cached(e.sha)
        if man is not None:
            return man
        if e.origin == "object":
            sub = BACKGROUNDS if e.path.startswith(BACKGROUNDS) else SPRITES
            oid = e.path[len(sub):-4]
            files, man = extract_object(self.repo, oid, read_objects(self.repo, self.objects).get(oid, {}),
                                        e.sha, e.path, self.objects)
        else:
            data = self.read(e.path)
            if data is None:
                return None
            files, man = extract_swf(data, e.sha, e.path)
        self._publish(e.sha, files, "manifest.json", man)
        self._manifests[(e.sha, "manifest.json")] = man
        return man

    def library(self, name):
        return self.ensure(lib_path(name))

    def sprite(self, sid):
        return self.ensure(sprite_path(sid))

    def background(self, bid):
        return self.ensure(background_path(bid))

    def image(self, man, pic):
        """A cached picture (an entry of a manifest) as an RGBA Image."""
        Image, _ = _pil()
        key = (man["sha"], pic["file"])
        with self._lock:
            img = self._images.get(key)
            if img is not None:
                self._images.move_to_end(key)
                return img
        img = Image.open(os.path.join(self.cache, man["sha"], pic["file"])).convert("RGBA")
        with self._lock:
            self._images[key] = img
            px = 0
            for k in reversed(self._images):
                px += self._images[k].size[0] * self._images[k].size[1]
            # LAVA_ART_IMAGE_PIXELS: how many decoded pixels are kept (4
            # bytes each); the admin panel's container keeps fewer
            while len(self._images) > 1 and px > int(os.environ.get("LAVA_ART_IMAGE_PIXELS") or 120_000_000):
                _k, old = self._images.popitem(last=False)
                px -= old.size[0] * old.size[1]
        return img

    # -- what the client draws ----------------------------------------------------------
    def lib_picture(self, library, name):
        """getFromLib(name) of a location's library: (Image, (ox, oy)), the
        top-left goes where the client puts the bitmap; (None, None) when
        nothing is drawn. A name not exported draws the root's picture."""
        man = self.library(library)
        if man is None:
            return None, None
        pic = man["symbols"].get(name)
        if pic is None:
            pic = man["stage"]
        if not pic or pic.get("empty"):
            return None, None
        return self.image(man, pic), (pic["ox"], pic["oy"])

    def ext_picture(self, sid, kind="sprite"):
        """An ext sprite (or kind="background") SWF's first frame: (Image,
        (ox, oy) from the SWF's origin) or (None, None)."""
        man = self.background(sid) if kind == "background" else self.sprite(sid)
        if man is None or not man["stage"]:
            return None, None
        return self.image(man, man["stage"]), (man["stage"]["ox"], man["stage"]["oy"])

    def palette(self, library, ext=True):
        """What a location of this library can place: its exports, then
        (ext=True) every ext sprite of the release. [{name, type, sha, path,
        and, once cached, file, thumb, w, h, ox, oy, frames}]. Ext sprites
        are listed without extracting them; ensure(path) does that. The
        owner's objects (origin "object") also carry their manifest's
        title, anchor, front and footprint: what custom_objects.place()
        writes when one is put on a cell."""
        out = []
        man = self.library(library)
        if man:
            for name in sorted(man["symbols"]):
                pic = man["symbols"][name]
                if pic.get("empty"):
                    continue
                out.append(dict(pic, name=name, type="lib", sha=man["sha"], path=lib_path(library)))
        if ext:
            objs = read_objects(self.repo, self.objects)
            for p in sorted(self.release):
                if not (p.startswith(SPRITES) and p.endswith(".swf")):
                    continue
                e = self.release[p]
                item = {"name": p[len(SPRITES):-4], "type": "ext", "sha": e.sha, "path": p}
                if e.origin == "object":
                    obj = objs.get(item["name"], {})
                    item.update(origin="object", title=obj.get("title"), anchor=obj.get("anchor"),
                                front=obj.get("front", [[0, 0]]), footprint=obj.get("footprint", []),
                                frames=object_frames(obj))
                sm = self._cached(e.sha)
                if sm and sm["stage"]:
                    item.update(sm["stage"], frames=sm["frames"])
                out.append(item)
        return out

    # -- mobs -------------------------------------------------------------------------
    def mob_types(self):
        """{type_id: resource} of database/mobs.xml."""
        if self._mobs is None:
            raw = self.read("database/mobs.xml")
            if raw is None:
                world = _world()
                with open(os.path.join(world.RES, "database", "mobs.xml"), "rb") as fh:
                    raw = fh.read()
            root = _xml(raw)
            self._mobs = {int(m.get("type_id")): m.get("resource") for m in root.iter("mob")
                          if m.get("type_id", "").isdigit() and m.get("resource")}
        return self._mobs

    def stand(self, resource, direction=1):
        """(release path of the stand SWF, 0-based frame) of a mob resource,
        as AnimationFactory picks it: frame 2 + N*(dir-1) + seq[0], N the
        frames per direction; (None, why) when it has none."""
        raw = self.read("mobs/%s.xml" % resource)
        if raw is None:
            return None, "no mobs/%s.xml" % resource
        act = None
        for beh in _xml(raw):
            if beh.tag == "body":
                continue
            a = beh.find("action[@id='stand']")
            if a is not None:
                act = a
                break
        if act is None:
            return None, "no stand action"
        seq = [int(v) for v in re.findall(r"\d+", act.text or "")] or [1]
        path = "mobs/%s/%s_%s.swf" % (resource, resource, act.get("action"))
        e = self.entry(path)
        if e is None:
            return None, "no %s" % path
        return (e.path, seq[0], direction), None

    def mob(self, type_id, direction=1):
        """The cached stand frame of a mob type: {sha, path, frame, seq,
        dir, stand: {file, w, h, ox, oy}, icon: {file, w, h}}, or None (no
        resource, no stand animation, no bytes, an empty frame)."""
        key = (int(type_id), direction)
        if key in self._mob_memo:
            return self._mob_memo[key] or None
        man = None
        res = self.mob_types().get(int(type_id))
        st = self.stand(res, direction)[0] if res else None
        if st is not None:
            path, seq, d = st
            e = self.entry(path)
            mname = "mob-s%d-d%d.json" % (seq, d)
            man = self._cached(e.sha, mname)
            if man is None:
                data = self.read(path)
                if data is not None:
                    import swfx
                    try:
                        n = (len(swfx.Swf(data).timeline) - 2) // 8
                        files, man = extract_mob(data, e.sha, path, 1 + n * (d - 1) + seq)
                        man["seq"], man["dir"] = seq, d
                        self._publish(e.sha, files, mname, man)
                        self._manifests[(e.sha, mname)] = man
                    except Exception:
                        man = None
        self._mob_memo[key] = man or False
        return man

    def mob_icon(self, type_id):
        """(absolute path of a 64 px WebP, placeholder?) for a mob type."""
        man = self.mob(type_id)
        if man:
            return os.path.join(self.cache, man["sha"], man["icon"]["file"]), False
        return self.placeholder(), True

    def mob_picture(self, type_id):
        """(Image, (ox, oy) from the cell centre) of a mob's stand frame, or
        (None, None)."""
        man = self.mob(type_id)
        if not man:
            return None, None
        return self.image(man, man["stand"]), (man["stand"]["ox"], man["stand"]["oy"])

    def placeholder(self):
        f = os.path.join(self.cache, "placeholder64.webp")
        if not os.path.isfile(f):
            Image, ImageDraw = _pil()
            img = Image.new("RGBA", (ICON, ICON), (0, 0, 0, 0))
            dr = ImageDraw.Draw(img)
            dr.ellipse((14, 4, 50, 40), fill=(120, 120, 120, 200))
            dr.polygon([(32, 30), (12, 62), (52, 62)], fill=(120, 120, 120, 200))
            dr.text((27, 12), "?", fill=(255, 255, 255, 255))
            os.makedirs(self.cache, exist_ok=True)
            tmp = f + ".%d.tmp" % os.getpid()
            img.save(tmp, "WEBP", quality=ICON_Q)
            os.replace(tmp, f)
        return f

    # -- locations --------------------------------------------------------------------
    def location_path(self, ref):
        """A location file by id ("35", 35), by "desert/0001", or by path:
        the locations of ours first (server/world.py OVERLAY, which
        LAVA_LOC_OVERLAY moves, for this repository; another repo's
        data/locations), then LAVA_RES, then the art res folders -- the
        order the server reads them in (world.static_path)."""
        ref = str(ref)
        if os.path.isfile(ref):
            return ref
        rel = ref if "/" in ref else "static/%s" % ref
        if not rel.endswith(".xml"):
            rel += ".xml"
        world = _world()
        overlay = getattr(world, "OVERLAY", None) if os.path.abspath(self.repo) == ROOT else None
        overlay = overlay or os.path.join(self.repo, "data", "locations")
        cands = [os.path.join(overlay, *rel.split("/")),
                 os.path.join(world.RES, "locations", *rel.split("/"))]
        cands += [os.path.join(d, "locations", *rel.split("/")) for d in self.res_dirs]
        for c in cands:
            if os.path.isfile(c):
                return c
        return None


def _xml(raw):
    if raw.startswith(L.BOM):
        raw = raw[len(L.BOM):]
    txt = raw.decode("utf-8", "replace")
    txt = re.sub(r"<\?xml[^>]*\?>", "", txt, count=1)
    return ET.fromstring(txt)


# --- the render -----------------------------------------------------------------------------------------

def _round(v):
    return int(v + 0.5) if v >= 0 else -int(-v + 0.5)


def render(m, art=None, layers=ART_LAYERS, scale=1.0, order="reverse", extra_row=False,
           mobs=None):
    """A location (lavaloc model) drawn as the client draws it: (RGBA Image
    of W*40 x H*15 times scale, report). layers: any of LAYERS, "art" for
    ART_LAYERS; without "background" the canvas is transparent, so one
    layer at a time gives the layers apart. mobs: [(gx, gy, type)] drawn
    besides the file's own non-empty <mobs> slots (placements.json rows).
    order: "reverse" (the for..in walk) or "file", for decals and sprites."""
    Image, ImageDraw = _pil()
    import swfx
    art = art or Art()
    layers = _layers(layers)
    t0 = time.time()
    W, H = m["width"], m["height"]
    cw, ch = W * L.CELL_W, H * L.ROW_H
    if not (cw > 0 and ch > 0 and cw * ch <= MAX_CANVAS and cw * ch * scale * scale <= MAX_CANVAS):
        raise ValueError("холст %dx%d клеток (%d x %d точек, масштаб %g) больше предела в %d точек"
                         % (W, H, cw, ch, scale, MAX_CANVAS))
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    attrs = m["attrs"]
    library = attrs.get("library", "")
    rep = {"size": [cw, ch], "library": library, "layers": list(layers), "order": order,
           "background": None, "decals": {"drawn": 0, "missing": collections.Counter()},
           "sprites": {"drawn": 0, "missing": collections.Counter(), "extra_row": 0},
           "mobs": {"drawn": 0, "missing": collections.Counter()}, "notes": []}

    if "background" in layers:
        bg = m.get("background") or {"type": "ext" if attrs.get("bgExt") == "ext" else "lib",
                                     "id": attrs.get("bg", "")}
        if bg.get("type") == "ext":
            img, _off = art.ext_picture(bg.get("id"), "background")
        else:
            img, _off = art.lib_picture(library, bg.get("id"))
        rep["background"] = {"id": bg.get("id"), "type": bg.get("type"), "fx": bg.get("fx", ""),
                             "tile": list(img.size) if img else None}
        if img is not None:
            tw, th = img.size
            for x in range(0, cw, tw):
                for y in range(0, ch, th):
                    canvas.paste(img, (x, y))
        if bg.get("fx") == "water":
            rep["notes"].append("fx water: the client animates the background (lol.fx.Water0); "
                                "drawn here as the plain tile")

    if "decals" in layers:
        decals = list(m["bgdecorations"])
        if order == "reverse":
            decals.reverse()
        for dc in decals:
            if dc.get("type") == "ext":
                img, _off = art.ext_picture(dc["id"])
            else:
                img, _off = art.lib_picture(library, dc["id"])
            if img is None:
                rep["decals"]["missing"][dc["id"]] += 1
                continue
            swfx.blit(canvas, img, _round(L.num(dc["dx"])), _round(L.num(dc["dy"])))
            rep["decals"]["drawn"] += 1

    if "zones" in layers:
        dr = ImageDraw.Draw(canvas, "RGBA")
        for x, y, _e in m["lists"]["zones"]:
            if y >= H:
                continue
            cx, cy = L.cell_px(x, y)
            cx, cy = 5 * _round(cx / 5.0), 5 * _round(cy / 5.0)
            dr.polygon([(cx + dx, cy + dy) for dx, dy in L.HEX], fill=(255, 255, 210, 60),
                       outline=(255, 255, 210, 140))

    objs = L.depth_sort(L.scene_objects(m, order)) if ("sprites" in layers or "mobs" in layers) else []
    drawn = list(objs)
    walkers = []
    if "mobs" in layers:
        slots = [(x, y, t) for x, y, t in L.mob_slots(m) if t] + [tuple(r) for r in (mobs or [])]
        for x, y, t in slots:
            w = L.SceneObject(None, None, (x, y), [(x, y)])
            w.minD = 0
            drawn.insert(L.walker_index(drawn, x, y), w)
            walkers.append((w, t))
    types = {id(w): t for w, t in walkers}
    for o in drawn:
        if o.sprite is None:
            t = types[id(o)]
            img, off = art.mob_picture(t)
            if img is None:
                rep["mobs"]["missing"][t] += 1
                continue
            px, py = L.cell_px(*o.point)
            swfx.blit(canvas, img, _round(px + off[0]), _round(py + off[1]))
            rep["mobs"]["drawn"] += 1
            continue
        if "sprites" not in layers:
            continue
        sp = m["sprites"][o.sprite]
        ax, ay = o.point
        if 0 <= ax < W and 0 <= ay < H:
            px, py = L.cell_px(ax, ay)
        else:
            # No such cell in the client's grid (the extra row y == H):
            # LocationGrid.getCellFromGrid gives undefined, placeObject's
            # NaN position is ignored, and dx, dy are added to the clip's
            # 0, 0 -- the picture lands at the location's top-left corner,
            # in its place in the depth order.
            rep["sprites"]["extra_row"] += 1
            px, py = L.cell_px(ax, ay) if extra_row else (0, 0)
        x, y = px + L.num(sp.get("dx")), py + L.num(sp.get("dy"))
        if sp.get("type") == "ext":
            img, off = art.ext_picture(sp["id"])
            if img is not None:
                x, y = x + off[0], y + off[1]
        else:
            img, _off = art.lib_picture(library, sp["id"])
        if img is None:
            rep["sprites"]["missing"][sp["id"]] += 1
            continue
        swfx.blit(canvas, img, _round(x), _round(y))
        rep["sprites"]["drawn"] += 1

    if scale != 1.0:
        canvas = canvas.resize((max(1, _round(cw * scale)), max(1, _round(ch * scale))), Image.LANCZOS)
    _overlays(canvas, m, layers, scale)
    for k in ("decals", "sprites", "mobs"):
        rep[k]["missing"] = dict(rep[k]["missing"])
    rep["seconds"] = round(time.time() - t0, 2)
    return canvas, rep


def _layers(layers):
    if isinstance(layers, str):
        layers = [s for s in layers.split(",") if s]
    out = []
    for s in layers:
        for x in (ART_LAYERS if s == "art" else (s,)):
            if x not in LAYERS:
                raise ValueError("unknown layer %r (one of %s, art)" % (x, ", ".join(LAYERS)))
            if x not in out:
                out.append(x)
    return out


OBSTACLE_COLOURS = {"f": (255, 40, 40, 110), "1": (255, 230, 0, 110), "3": (255, 140, 0, 110),
                    "7": (170, 60, 255, 120)}
EXIT_COLOURS = {"a": (0, 230, 255, 150), "b": (255, 0, 200, 150)}


def _overlays(canvas, m, layers, scale):
    """The cell layers, drawn over the scaled picture as hexes."""
    if not any(x in layers for x in OVERLAYS):
        return
    _Image, ImageDraw = _pil()
    dr = ImageDraw.Draw(canvas, "RGBA")
    W, H = m["width"], m["height"]

    def hexes(cells, fill, outline=None):
        for c in cells:
            dr.polygon(L.hex_points(c[0], c[1], scale), fill=fill, outline=outline)

    if "grid" in layers:
        for gy in range(H):
            for gx in range(W):
                dr.polygon(L.hex_points(gx, gy, scale), outline=(255, 255, 255, 40))
    if "extrarow" in layers:
        hexes([(gx, H) for gx in range(W)], (0, 0, 0, 90), (255, 255, 255, 60))
    if "obstacles" in layers:
        for x, y, e in m["lists"]["obstacles"]:
            dr.polygon(L.hex_points(x, y, scale), fill=OBSTACLE_COLOURS.get(e, (150, 150, 150, 110)))
    if "exits" in layers:
        for x, y, e in m["lists"]["outzones"]:
            dr.polygon(L.hex_points(x, y, scale), fill=EXIT_COLOURS.get(e, (0, 120, 255, 140)))
    if "entries" in layers:
        hexes(m["lists"]["inzones"], (0, 255, 80, 140))
    if "warentries" in layers:
        hexes(m["lists"]["warinzones"], (0, 120, 40, 160))
    if "spawns" in layers:
        for x, y, _t in L.mob_slots(m):
            dr.polygon(L.hex_points(x, y, scale), outline=(255, 0, 255, 255))


def render_layers(m, art=None, names=LAYERS, **kw):
    """{layer: Image} -- each layer alone on a transparent canvas."""
    art = art or Art()
    return {n: render(m, art, [n], **kw)[0] for n in names}


def png_bytes(img, optimize=False):
    b = io.BytesIO()
    img.save(b, "PNG", optimize=optimize, compress_level=6)
    return b.getvalue()


# --- warming the cache -------------------------------------------------------------------------------------

_WORKER = {}


def _worker_init(repo, res, store, cache):
    _WORKER["art"] = Art(repo, res, store, cache)


def _warm_one(job):
    kind, key = job
    art = _WORKER["art"]
    t = time.time()
    try:
        if kind == "mob":
            ok = art.mob(key) is not None
        else:
            ok = art.ensure(key) is not None
        return job, ok, time.time() - t, None
    except Exception as e:
        return job, False, time.time() - t, "%s: %s" % (type(e).__name__, e)


def warm(art, jobs=8, only=("libs", "sprites", "backgrounds", "mobs")):
    """Extract everything into the cache, `jobs` processes at once. Returns
    {count, failed, seconds, bytes, files} of the cache afterwards."""
    from concurrent.futures import ProcessPoolExecutor
    rel = art.release
    todo = []
    if "libs" in only:
        todo += [("swf", p) for p in rel if p.startswith(LIBS) and p.endswith(".swf")
                 and "/" not in p[len(LIBS):]]
    if "sprites" in only:
        todo += [("swf", p) for p in rel if p.startswith(SPRITES) and p.endswith(".swf")]
    if "backgrounds" in only:
        todo += [("swf", p) for p in rel if p.startswith(BACKGROUNDS) and p.endswith(".swf")]
    # one job per sha, the biggest first
    seen, jobs_list = set(), []
    for kind, p in sorted(todo, key=lambda j: -rel[j[1]].size):
        if rel[p].sha in seen:
            continue
        seen.add(rel[p].sha)
        jobs_list.append((kind, p))
    if "mobs" in only:
        res_seen = set()
        for t, r in sorted(art.mob_types().items()):
            if r not in res_seen:
                res_seen.add(r)
                jobs_list.append(("mob", t))
    t0 = time.time()
    failed = []
    with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init,
                             initargs=(art.repo, art.res_dirs, art.store_dirs, art.cache)) as ex:
        for job, ok, _sec, err in ex.map(_warm_one, jobs_list, chunksize=1):
            if not ok:
                failed.append((job, err))
    out = cache_stats(art.cache)
    out.update(count=len(jobs_list), failed=failed, seconds=round(time.time() - t0, 1))
    return out


def cache_stats(cache):
    files = size = 0
    by = collections.Counter()
    for d, _dirs, names in os.walk(cache):
        for f in names:
            n = os.path.getsize(os.path.join(d, f))
            files += 1
            size += n
            by[os.path.splitext(f)[1]] += n
    return {"files": files, "bytes": size, "by_ext": dict(by)}


# --- command line ----------------------------------------------------------------------------------------

def _short(path):
    """A location file's path as locations/<dir>/<file> when it has one."""
    parts = os.path.normpath(path).split(os.sep)
    return "/".join(parts[-3:]) if len(parts) >= 3 and parts[-3] == "locations" else path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index", help="write data/location_art.json from the SWFs")
    p.add_argument("-o", "--out", default=INDEX)
    p.add_argument("--check", action="store_true", help="exit 1 if the file differs")
    p = sub.add_parser("warm", help="extract every picture into the cache")
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--only", default="libs,sprites,backgrounds,mobs")
    p = sub.add_parser("render", help="a location as a PNG")
    p.add_argument("ref")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--layers", default="art")
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--order", choices=("reverse", "file"), default="reverse")
    p.add_argument("--extra-row", action="store_true")
    p = sub.add_parser("lint", help="art references the client cannot draw")
    p.add_argument("refs", nargs="*")
    sub.add_parser("stats", help="what the cache holds")
    a = ap.parse_args(argv)
    art = Art()
    if a.cmd == "index":
        text = dump_index(build_index(art))
        if a.check:
            with open(a.out, encoding="utf-8") as fh:
                same = fh.read() == text
            print("%s is %s" % (a.out, "up to date" if same else "STALE"))
            return 0 if same else 1
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("%s: %d bytes" % (a.out, len(text.encode("utf-8"))))
        return 0
    if a.cmd == "warm":
        st = warm(art, a.jobs, tuple(a.only.split(",")))
        print(json.dumps({k: v for k, v in st.items() if k != "failed"}, indent=1))
        for job, err in st["failed"][:20]:
            print("failed:", job, err or "")
        print("%d failed" % len(st["failed"]))
        return 0
    if a.cmd == "render":
        path = art.location_path(a.ref)
        if not path:
            print("no location %s" % a.ref)
            return 2
        img, rep = render(L.load(path), art, a.layers, a.scale, a.order, a.extra_row)
        img.save(a.out)
        print(json.dumps(rep, ensure_ascii=False))
        return 0
    if a.cmd == "lint":
        import glob
        world = _world()
        refs = a.refs or sorted(glob.glob(os.path.join(world.RES, "locations", "*", "*.xml")))
        ix, extra = load_index(), local_ext(art.repo, art.objects)
        n = 0
        for r in refs:
            path = art.location_path(r)
            for pr in art_problems(L.load(path), ix, extra):
                n += 1
                print("%s: %s %s (%s) x%d: %s" % (_short(path), pr["what"], pr["id"],
                                                  pr["type"], pr["count"], pr["why"]))
        print("%d problems" % n)
        return 0
    if a.cmd == "stats":
        print(json.dumps(cache_stats(art.cache), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
