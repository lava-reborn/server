#!/usr/bin/env python3
"""The owner's own location objects (client/objects/README.md): his pictures
and client/objects/manifest.json in, the release's sprite files out
(client/build.py, step gen_custom_objects), and the XML a location places an
object with. Standard library only, like the rest of the release build.

client/objects/manifest.json maps each object's id to its entry:

  {"c_test_flag": {
     "title": "Тестовый флажок",     what the editor shows; any text
     "frames": ["0.png", "1.png"],    pictures in client/objects/<id>/, in order;
                                      several make an animation, a name may repeat
     "fps": 4,                        pictures a second, 1..25; needed for an animation
     "anchor": [9, 79],               the picture's pixel that stands on the cell's centre
     "front": [[0, 0]],               the depth line: cells relative to the anchor cell
     "footprint": [[0, 0]],           cells that block walking, relative to the anchor cell
     "kind": "sprite",                "sprite" (default) or "background"
     "note": "..."}}                  optional, for people; nothing reads it

Ids are "c_" and then 1..40 of a-z 0-9 _: ASCII, so the release path rules
(client/FORMAT.md) always hold, and no file of the original game starts so.
The Russian name is the title.

What a release gets: locations/libs/sprite/<id>.swf for kind "sprite",
locations/libs/background/<id>.swf for kind "background" (tools/swfgen.py).
A build refuses an id whose file, or whose library name, the original game
has in any case (client/base.txt) or extra.txt lists: a file of ours there
would silently replace the original's, and the client keeps one loaded
source per name (SourceLibrary), so a library of the same name would too.

How a location uses an object (place() below writes it):

  kind sprite, standing on cell GX:GY (an object):
    <sprite id="<id>" dx="-ax" dy="-ay" front="<front>" type="ext">GXGY</sprite>
    and GXGY + "f" in <obstacles> for every footprint cell
  kind sprite, flat on the ground at pixel X,Y (a decal, frame 1 only):
    <bgdecoration id="<id>" dx="X" dy="Y" type="ext" />
  kind background (tiled from 0,0, frame 1 only):
    <background type="ext" id="<id>" fx="" />

Cells relative to the anchor follow the client's own rule (LDParser
getHexCoord): the offsets are those of an anchor on an even row, and on an
odd anchor row a cell on an odd relative row moves one to the right. front
is written that way, 0x80 + offset per coordinate; footprint cells are
turned into map cells by the same rule. A footprint cell is an obstacle with
code "f", a wall: the server reads code "1" as a counter one can shoot over
in the shooting ranges (server/world.py SHOOT_OVER).

For an editor: load() gives the checked entries, load_raw() the manifest as
written, manifest_text() writes it back the one way it is written;
check_entry() checks one entry, build() everything (pictures too), place()
what a placement writes. Every refusal is a Refused with the reason.

    python3 tools/custom_objects.py check [OBJDIR] [--base client/base.txt]
    python3 tools/custom_objects.py build OUTDIR [OBJDIR] [--base client/base.txt]
    python3 tools/custom_objects.py place ID GX GY [OBJDIR]
"""
import hashlib
import json
import os
import re
import sys

try:
    import swfgen
except ImportError:
    # Loaded by its file path with tools/ off the path. client/build.py
    # puts tools/ on the path itself and takes it off after the import, so
    # it never comes here and leaves sys.path as it found it.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import swfgen
from swfgen import Refused  # noqa: E402,F401  (callers catch it from here)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJDIR = os.path.join(ROOT, "client", "objects")
MANIFEST = "manifest.json"
README = "README.md"

ID = re.compile(r"c_[a-z0-9_]{1,40}")
FRAME = re.compile(r"[a-z0-9_-]{1,40}\.(png|jpg|jpeg)")
DIRS = {"sprite": "locations/libs/sprite/", "background": "locations/libs/background/"}
# An entry's fields, in the order manifest_text() writes them.
KEY_ORDER = ("title", "frames", "fps", "anchor", "front", "footprint", "kind", "note")
KEYS = set(KEY_ORDER)
MAX_FRAMES = 120
MAX_TITLE = 80
# client/objects/ goes up with every deploy (the gate takes at most 64 MB
# packed, deploy/remote/lava-gate.sh): bigger art belongs in the server's
# store and client/extra.txt (client/README.md).
MAX_PICTURE_BYTES = 8 << 20
MAX_TOTAL_BYTES = 32 << 20
# What a build may decode. tools/swfgen.py inflates every PNG picture into
# RGBA in pure Python, about a second and 4 MB for each million pixels (a
# picture at a time, read_pictures), and the release is built inside the
# deploy gate's container (deploy/remote/lava-gate.sh: 2 GB, 15 minutes for
# the whole build); a few megabytes of PNG can claim more pixels than that.
# The pixels of an object's distinct PNG pictures, and of all objects'; a
# JPEG goes in as its bytes and costs nothing here.
MAX_OBJECT_PIXELS = 24 * 1000 * 1000
MAX_TOTAL_PIXELS = 64 * 1000 * 1000
OBSTACLE = "f"


def release_path(oid, entry):
    return DIRS[entry.get("kind", "sprite")] + oid + ".swf"


def _cells(oid, key, cells):
    if not isinstance(cells, list):
        raise Refused("%s: %s is a list of [dx, dy] cells" % (oid, key))
    seen = set()
    for c in cells:
        if not (isinstance(c, list) and len(c) == 2 and all(type(v) is int and -128 <= v <= 127 for v in c)):
            raise Refused("%s: %s cell %r: [dx, dy], each -128..127" % (oid, key, c))
        if tuple(c) in seen:
            raise Refused("%s: %s names cell %r twice" % (oid, key, c))
        seen.add(tuple(c))
    return [tuple(c) for c in cells]


def check_entry(oid, entry):
    """The entry as it will be used (defaults filled in), or Refused. Looks
    at the manifest alone; build() also reads the pictures."""
    if not ID.fullmatch(oid):
        raise Refused("%s: an id is c_ and then 1..40 of a-z 0-9 _" % oid)
    if not isinstance(entry, dict):
        raise Refused("%s: an entry is an object" % oid)
    unknown = sorted(set(entry) - KEYS)
    if unknown:
        raise Refused("%s: unknown field%s %s (known: %s)" % (
            oid, "" if len(unknown) == 1 else "s", ", ".join(unknown), ", ".join(sorted(KEYS))))
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE \
            or any(ord(ch) < 32 for ch in title):
        raise Refused("%s: title is text of 1..%d characters on one line" % (oid, MAX_TITLE))
    if not isinstance(entry.get("note", ""), str):
        raise Refused("%s: note is text" % oid)
    kind = entry.get("kind", "sprite")
    if kind not in DIRS:
        raise Refused("%s: kind is %s" % (oid, " or ".join(sorted(DIRS))))
    frames = entry.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise Refused("%s: frames lists 1..%d pictures" % (oid, MAX_FRAMES))
    for f in frames:
        if not isinstance(f, str) or not FRAME.fullmatch(f):
            raise Refused("%s: frame %r: a file name in client/objects/%s/, a-z 0-9 _ -, "
                          "ending .png, .jpg or .jpeg" % (oid, f, oid))
    fps = entry.get("fps")
    if len(frames) > 1 and fps is None:
        raise Refused("%s: an animation of %d pictures needs fps, 1..%d" % (oid, len(frames), swfgen.HOST_FPS))
    if fps is not None:
        try:
            swfgen.hold_for(fps)
        except Refused as e:
            raise Refused("%s: %s" % (oid, e))
    out = {"title": title, "frames": list(frames), "fps": fps, "kind": kind, "note": entry.get("note")}
    if kind == "background":
        if len(frames) > 1:
            raise Refused("%s: a background is one picture (the client draws frame 1 only)" % oid)
        for k in ("anchor", "front", "footprint"):
            if entry.get(k):
                raise Refused("%s: a background has no %s: it is tiled from the corner" % (oid, k))
        out.update(anchor=None, front=[], footprint=[])
        return out
    anchor = entry.get("anchor")
    if not (isinstance(anchor, list) and len(anchor) == 2 and all(type(v) is int for v in anchor)):
        raise Refused("%s: anchor is [x, y], the picture's pixel that stands on the cell" % oid)
    front = _cells(oid, "front", entry.get("front", [[0, 0]]))
    if not front:
        raise Refused("%s: front needs at least one cell; [[0, 0]] is the anchor cell" % oid)
    out.update(anchor=tuple(anchor), front=front, footprint=_cells(oid, "footprint", entry.get("footprint", [])))
    return out


def load_raw(objdir=OBJDIR):
    """The manifest as written, {id: entry} with nothing filled in or
    checked but its JSON; {} when there is none. What an editor changes
    and gives back to manifest_text()."""
    path = os.path.join(objdir, MANIFEST)
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as fh:
        raw = fh.read()
    def pairs(kv):
        keys = [k for k, _ in kv]
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:
            raise Refused("%s: %s is there twice" % (MANIFEST, twice[0]))
        return dict(kv)
    try:
        m = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except ValueError as e:
        if isinstance(e, Refused):
            raise
        raise Refused("%s: not JSON (%s)" % (MANIFEST, e))
    if not isinstance(m, dict):
        raise Refused("%s: an object of id -> entry" % MANIFEST)
    return m


def load(objdir=OBJDIR):
    """{id: checked entry, defaults filled in} of the manifest, by id; {}
    when there is no manifest. The pictures are not read."""
    m = load_raw(objdir)
    return {oid: check_entry(oid, m[oid]) for oid in sorted(m)}



def manifest_text(raw):
    """The one way manifest.json is written: ids sorted, an entry's fields in
    KEY_ORDER, each value on its line as compact JSON, UTF-8 as it is, LF,
    a newline at the end. load_raw() of the file and back gives the same
    bytes, so a save that changes nothing changes no byte."""
    out = []
    for oid in sorted(raw):
        entry = raw[oid]
        unknown = sorted(set(entry) - KEYS)
        if unknown:
            raise Refused("%s: unknown field %s" % (oid, unknown[0]))
        fields = ["    %s: %s" % (json.dumps(k), json.dumps(entry[k], ensure_ascii=False))
                  for k in KEY_ORDER if k in entry]
        out.append("  %s: {\n%s\n  }" % (json.dumps(oid), ",\n".join(fields)))
    return "{\n" + ",\n".join(out) + "\n}\n" if out else "{}\n"


def _clash_names(oid):
    """The release paths that, in any case, would clash with this id: its
    own sprite and background files and a location library of its name."""
    return {d + oid + ".swf" for d in DIRS.values()} | {"locations/libs/" + oid + ".swf"}


def png_pixels(path):
    """Width times height of a PNG file from its header, 0 for anything
    else (a JPEG is not decoded by the build)."""
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != swfgen.PNG_SIG:
        return 0
    try:
        w, h = swfgen.png_header(head)[:2]
    except Refused:
        return 0
    return w * h


def check_tree(objdir, objs):
    """Every folder is an object of the manifest and holds its pictures and
    nothing else; the sizes fit what a deploy may carry, the pixels what a
    build may decode (MAX_OBJECT_PIXELS, MAX_TOTAL_PIXELS)."""
    total = 0
    pixels = 0
    # Dot files are a desktop's own (.DS_Store); git and the release never
    # see them.
    names = {n for n in os.listdir(objdir) if not n.startswith(".")} - {MANIFEST, README}
    stray = sorted(n for n in names if n not in objs)
    if stray:
        raise Refused("client/objects/%s: not an object of %s; add it there or take it out"
                      % (stray[0], MANIFEST))
    for oid, entry in objs.items():
        d = os.path.join(objdir, oid)
        if not os.path.isdir(d):
            raise Refused("%s: no folder client/objects/%s/" % (oid, oid))
        listed = set(entry["frames"])
        for n in sorted(os.listdir(d)):
            if n.startswith("."):
                continue
            full = os.path.join(d, n)
            if n not in listed or not os.path.isfile(full) or os.path.islink(full):
                raise Refused("client/objects/%s/%s: not a picture of %s's frames; "
                              "list it or take it out" % (oid, n, oid))
            size = os.path.getsize(full)
            if size > MAX_PICTURE_BYTES:
                raise Refused("client/objects/%s/%s: %d bytes, more than %d; big art goes into "
                              "the store and client/extra.txt" % (oid, n, size, MAX_PICTURE_BYTES))
            total += size
        for f in listed:
            if not os.path.isfile(os.path.join(d, f)):
                raise Refused("%s: frame %s is not in client/objects/%s/" % (oid, f, oid))
        px = sum(png_pixels(os.path.join(d, f)) for f in sorted(listed))
        if px > MAX_OBJECT_PIXELS:
            raise Refused("%s: %d pixels of PNG pictures, more than %d: the release build decodes every one "
                          "(tools/swfgen.py, about a second a million); smaller pictures, fewer of them, or the "
                          "opaque ones as JPEG" % (oid, px, MAX_OBJECT_PIXELS))
        pixels += px
    if total > MAX_TOTAL_BYTES:
        raise Refused("client/objects: %d bytes of pictures, more than %d; big art goes into "
                      "the store and client/extra.txt" % (total, MAX_TOTAL_BYTES))
    if pixels > MAX_TOTAL_PIXELS:
        raise Refused("client/objects: %d pixels of PNG pictures, more than %d: the release build decodes every "
                      "one (tools/swfgen.py, about a second a million); smaller pictures, fewer of them, or the "
                      "opaque ones as JPEG" % (pixels, MAX_TOTAL_PIXELS))
    return total


class LazyPicture:
    """A picture of an object as swfgen.sprite_swf takes it (kind, w, h,
    jpeg, rgba), read from its header; a PNG's pixels are decoded when the
    writer asks for rgba and dropped once it has wrapped them, so a build
    holds one decoded picture at a time, whatever the frames. A fault the
    decoding finds names the file."""

    def __init__(self, data, label):
        self.label = label
        if data[:8] == swfgen.PNG_SIG:
            w, h, _depth, _ctype, interlace = swfgen.png_header(data)
            swfgen._check_side(w, h, "PNG")
            if interlace:
                raise Refused("PNG: interlaced; save it without interlacing")
            self.kind, self.jpeg, self._png = "png", None, data
        elif data[:2] == b"\xff\xd8":
            w, h = swfgen.jpeg_size(data)
            self.kind, self.jpeg, self._png = "jpeg", bytes(data), None
        else:
            raise Refused("neither a PNG nor a JPEG")
        self.w, self.h = w, h

    @property
    def rgba(self):
        if self._png is None:
            return None
        try:
            return swfgen.png_decode(self._png)[2]
        except Refused as e:
            raise Refused("%s: %s" % (self.label, e))


def read_pictures(objdir, oid, entry):
    """The entry's pictures (LazyPicture), one per frame, with the anchor
    checked against their size. Nothing is decoded until a writer asks."""
    pics = {}
    for f in entry["frames"]:
        if f not in pics:
            label = "client/objects/%s/%s" % (oid, f)
            with open(os.path.join(objdir, oid, f), "rb") as fh:
                try:
                    pics[f] = LazyPicture(fh.read(), label)
                except Refused as e:
                    raise Refused("%s: %s" % (label, e))
    frames = [pics[f] for f in entry["frames"]]
    w, h = frames[0].w, frames[0].h
    if entry["anchor"] is not None:
        ax, ay = entry["anchor"]
        if not (0 <= ax <= w and 0 <= ay <= h):
            raise Refused("%s: anchor %d,%d is outside the %dx%d picture" % (oid, ax, ay, w, h))
    return frames


def build(objdir=OBJDIR, taken=()):
    """{release path: swf bytes} of every object, and the report lines.
    `taken`: the paths the release already has from elsewhere (client/base.txt
    and extra.txt); an object that would land on one of them, in any case,
    is refused. The same manifest and pictures give the same bytes."""
    objs = load(objdir)
    if not objs:
        return {}, []
    check_tree(objdir, objs)
    taken_lower = {p.lower(): p for p in taken}
    out, report = {}, []
    for oid, entry in objs.items():
        for p in sorted(_clash_names(oid)):
            if p.lower() in taken_lower:
                raise Refused("%s: the game already has %s; pick another id" % (oid, taken_lower[p.lower()]))
        pics = read_pictures(objdir, oid, entry)
        try:
            data = swfgen.sprite_swf(pics, fps=entry["fps"], keys=entry["frames"])
        except Refused as e:
            raise Refused("%s: %s" % (oid, e))
        p = release_path(oid, entry)
        out[p] = data
        n = len(entry["frames"])
        report.append("object:    %s %s (%dx%d, %d picture%s%s, %d bytes)" % (
            hashlib.sha256(data).hexdigest()[:16], p, pics[0].w, pics[0].h, n, "" if n == 1 else "s",
            "" if n == 1 else " at %d fps" % entry["fps"], len(data)))
    return out, report


# --- placing an object in a location ------------------------------------------------------

def encode_cells(cells):
    """A front attribute: 0x80 + dx, 0x80 + dy per cell, lowercase hex."""
    return "".join("%02x%02x" % (0x80 + dx, 0x80 + dy) for dx, dy in cells)


def absolute(cells, gx, gy):
    """Cells relative to the anchor -> the location's cells, by the client's
    rule (LDParser.getHexCoord)."""
    return [(gx + dx + (1 if gy % 2 and dy % 2 else 0), gy + dy) for dx, dy in cells]


def place(oid, entry, gx, gy):
    """What placing object `oid` (a checked entry, from load()) with its
    anchor on cell gx:gy writes into a location:

      sprite     the <sprite> element, in the originals' attribute order
      attrs      its attributes, [(name, value)]
      cells      its text, the anchor cell (several anchors: concatenate)
      obstacles  the chunks to add to <obstacles>, GXGY + "f" each
      footprint  the footprint's cells on the map, [(gx, gy)]
      front      the front's cells on the map, [(gx, gy)]
    """
    if entry["kind"] != "sprite":
        raise Refused("%s: a background is placed as <background type=\"ext\" id=\"%s\" />" % (oid, oid))
    if not (0 <= gx <= 255 and 0 <= gy <= 255):
        raise Refused("cell %d:%d: each coordinate 0..255" % (gx, gy))
    ax, ay = entry["anchor"]
    attrs = [("id", oid), ("dx", str(-ax)), ("dy", str(-ay)), ("front", encode_cells(entry["front"])),
             ("type", "ext")]
    cells = "%02x%02x" % (gx, gy)
    foot = absolute(entry["footprint"], gx, gy)
    bad = [c for c in foot if not (0 <= c[0] <= 255 and 0 <= c[1] <= 255)]
    if bad:
        raise Refused("%s at %d:%d: footprint cell %d:%d is off the grid" % ((oid, gx, gy) + bad[0]))
    return {
        "sprite": "<sprite%s>%s</sprite>" % ("".join(' %s="%s"' % kv for kv in attrs), cells),
        "attrs": attrs,
        "cells": cells,
        "obstacles": "".join("%02x%02x%s" % (x, y, OBSTACLE) for x, y in foot),
        "footprint": foot,
        "front": absolute(entry["front"], gx, gy),
    }


# --- command line ------------------------------------------------------------------------------

def base_paths(path):
    """The paths of a client/base.txt or extra.txt (sha TAB size TAB path)."""
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 3 and not line.startswith("#"):
                out.append(parts[2])
    return out


def main(argv):
    args = list(argv)
    taken = []
    while "--base" in args:
        i = args.index("--base")
        taken += base_paths(args[i + 1])
        del args[i:i + 2]
    try:
        if args[:1] == ["check"] and len(args) <= 2:
            objdir = args[1] if len(args) > 1 else OBJDIR
            objs = load(objdir)
            files, report = build(objdir, taken)
            print("\n".join(report) or "no objects")
            print("%d object%s fine" % (len(objs), "" if len(objs) == 1 else "s"))
            return 0
        if args[:1] == ["build"] and 2 <= len(args) <= 3:
            outdir = args[1]
            files, report = build(args[2] if len(args) > 2 else OBJDIR, taken)
            for p, data in sorted(files.items()):
                dest = os.path.join(outdir, *p.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as fh:
                    fh.write(data)
            print("\n".join(report) or "no objects")
            return 0
        if args[:1] == ["place"] and 4 <= len(args) <= 5:
            objs = load(args[4] if len(args) > 4 else OBJDIR)
            if args[1] not in objs:
                raise Refused("%s: no such object in the manifest" % args[1])
            r = place(args[1], objs[args[1]], int(args[2]), int(args[3]))
            print(r["sprite"])
            print("obstacles + %s" % (r["obstacles"] or "(none)"))
            return 0
    except Refused as e:
        print("refused: %s" % e, file=sys.stderr)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
