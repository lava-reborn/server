"""Location art: the editor's pictures, renders and reference checks.

Standard library, as CI runs it: data/location_art.json agrees with
client/base.txt, every location file's art references resolve but for the
original's own known misses (an editor's file has none), the release list
layers as client/build.py does and a file's bytes count only with the sha256
the release lists. With Pillow and the original's SWFs (WSL ~/venvs/lavagd,
the Desktop client): the cache keeps what it extracted, painted libraries
serve their picture, a sprite, an ext sprite and a decal land where the
client puts them, three reference renders keep their look, and mobs get an
icon or a placeholder.

    python3 tools/test_location_art.py [--print-signatures]
"""
import collections
import copy
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import lavaloc as L  # noqa: E402
import location_art as A  # noqa: E402
import world  # noqa: E402
from swf_fixture import export, matrix, place, shape, sprite, swf  # noqa: E402
from testkit import check, fails  # noqa: E402

TMP = tempfile.mkdtemp(prefix="location_art_")

# --- the index agrees with the release ---------------------------------------------------------
ix = A.load_index()
with open(A.INDEX, encoding="utf-8") as fh:
    INDEX_TEXT = fh.read()
rel = A.read_release(ROOT)
ours = {p: e for p, e in rel.items() if e.origin != "object"}
libs = {p[len(A.LIBS):-4]: e for p, e in ours.items()
        if p.startswith(A.LIBS) and p.endswith(".swf") and "/" not in p[len(A.LIBS):]}
check("index: one entry per library SWF of the release, with its sha256",
      sorted((n, e.sha[:16]) for n, e in libs.items()),
      sorted((n, v["sha"]) for n, v in ix["libraries"].items()))
check("index: the ext sprites, backgrounds and music tracks of the release",
      (sorted(ix["sprites"]), sorted(ix["backgrounds"]), sorted(ix["tracks"])),
      (sorted(p[len(A.SPRITES):-4] for p in ours if p.startswith(A.SPRITES) and p.endswith(".swf")),
       sorted(p[len(A.BACKGROUNDS):-4] for p in ours if p.startswith(A.BACKGROUNDS) and p.endswith(".swf")),
       sorted(p[len(A.TRACKS):-4] for p in ours if p.startswith(A.TRACKS) and p.endswith(".swf"))))
check("index: 3109 exports, 33 painted libraries, the animated ext sprites",
      (sum(len(v["exports"]) for v in ix["libraries"].values()),
       sum(v["stage"] for v in ix["libraries"].values()),
       ix["animated"].get("a_campfire.png"), ix["animated"].get("a_computer.png")),
      (3109, 33, 12, 306))
check("index: written as dump_index writes it (python3 tools/location_art.py index)",
      A.dump_index(ix) == INDEX_TEXT, True)
check("index: small enough to keep in git", len(INDEX_TEXT.encode()) < 120_000, True)

# --- every location's art resolves ---------------------------------------------------------------
# The original's own misses (research of 2026-10-12): symbols its libraries do
# not export, ext sprites never shipped, music names with a typo or ".swf".
KNOWN = {
    ("bgsound", "Desert.swf"): 12, ("bgsound", "Nil.swf"): 5, ("bgsound", "Underground "): 2,
    ("bgsound", "Undrground"): 1, ("bgsound", "Village.swf"): 8,
    ("decal", "miit.png"): 1, ("decal", "plant20.png"): 7, ("sprite", "sdkfz01.png"): 4,
    ("sprite", "tent1.png"): 1, ("sprite", "tent2.png"): 7, ("sprite", "wall1.png"): 2,
}
extra = A.local_ext(ROOT)
found = collections.Counter()
for f in sorted(glob.glob(os.path.join(world.RES, "locations", "*", "*.xml"))):
    for p in A.art_problems(L.load(f), ix, extra):
        found[(p["what"], p["id"])] += p["count"]
check("lint: every original location's art resolves but for the original's own misses",
      dict(found), KNOWN)
overlay = sorted(glob.glob(os.path.join(world.OVERLAY, "**", "*.xml"), recursive=True))
OV_INDEX = world.overlay_index()


def new_misses(f):
    """What a location of ours misses that the location it was copied from
    (index.json 'from') does not: the copy keeps the original's own misses,
    as the location editor does (a warning there, «так в оригинале»)."""
    got = A.art_problems(L.load(f), ix, extra)
    stem = os.path.basename(f)[:-4]
    src = (OV_INDEX.get(int(stem)) or {}).get("from") if stem.isdigit() else None
    path = world.static_path(int(src)) if src is not None else None
    had = {(p["what"], p["id"], p["type"]) for p in A.art_problems(L.load(path), ix, extra)} if path else set()
    return [p for p in got if (p["what"], p["id"], p["type"]) not in had]


check("lint: every location of data/locations (%d) draws all it names, but for what its copy's original misses"
      % len(overlay), [(os.path.relpath(f, ROOT), new_misses(f)) for f in overlay if new_misses(f)], [])
model = {"attrs": {"library": "Mountains", "bgsound": "underground", "bg": "bg_desert2.jpg",
                   "bgExt": "lib"},
         "background": None,
         "sprites": [{"id": "dune01.png", "type": "lib", "anchors": [(1, 1)]},
                     {"id": "nope.png", "type": None, "anchors": [(1, 1), (2, 2)]},
                     {"id": "A_CAMPFIRE.PNG", "type": "ext", "anchors": [(3, 3)]},
                     {"id": "c_house", "type": "ext", "anchors": [(4, 4)]},
                     {"id": "c_gone", "type": "ext", "anchors": [(4, 4)]}],
         "bgdecorations": [{"id": "edge01.png", "type": "undefined"}]}
check("lint: names it cannot find, counted per instance; file names in any case "
      "(the launcher's Release.Find); the owner's objects resolve",
      [(p["what"], p["id"], p["count"]) for p in A.art_problems(model, ix, ({"c_house"}, set()))],
      [("sprite", "c_gone", 1), ("sprite", "nope.png", 2)])
model["attrs"]["library"] = "Tephnuty"
model["attrs"]["bg"] = "Tephnuty_nosh.jpg"
check("lint: a painted library's picture is its background under any name; a sprite "
      "it does not export would be the whole picture",
      [(p["what"], p["id"]) for p in A.art_problems(model, ix, ({"c_house"}, set()))
       if p["type"] == "lib"],
      [("decal", "edge01.png"), ("sprite", "dune01.png"), ("sprite", "nope.png")])
model["attrs"]["library"] = "NoSuchLib"
check("lint: a library the release does not have",
      [p["what"] for p in A.art_problems(model, ix, (set(), set())) if p["what"] == "library"],
      ["library"])

# --- the release's files, and whose bytes count ------------------------------------------------------
repo = os.path.join(TMP, "repo")
res = os.path.join(TMP, "res")
store = os.path.join(TMP, "store")
os.makedirs(os.path.join(repo, "client", "files", "locations", "libs", "sprite"))
os.makedirs(os.path.join(repo, "client", "objects", "c_box"))
os.makedirs(os.path.join(res, "locations", "libs"))
lib_bytes = swf([shape(1, (0, 400, 0, 300)), sprite(2, [[place(1, 1)]]), export([(2, "a.png")])])
bad_bytes = bytes(len(lib_bytes))
gone = b"x" * 10


def sha(b):
    return hashlib.sha256(b).hexdigest()


with open(os.path.join(repo, "client", "base.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("lava-base 1\n# test\n")
    fh.write("%s\t%d\tlocations/libs/Lib.swf\n" % (sha(lib_bytes), len(lib_bytes)))
    fh.write("%s\t%d\tlocations/libs/Gone.swf\n" % (sha(gone), len(gone)))
    fh.write("%s\t%d\tlocations/libs/Store.swf\n" % (sha(gone + b"1"), 11))
with open(os.path.join(repo, "client", "remove.txt"), "w", encoding="utf-8") as fh:
    fh.write("locations/libs/Gone.swf\n")
with open(os.path.join(repo, "client", "extra.txt"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write("lava-extra 1\n%s\t%d\tlocations/libs/Extra.swf\n" % (sha(b"extra"), 5))
with open(os.path.join(repo, "client", "files", "locations", "libs", "sprite", "c_mine.swf"), "wb") as fh:
    fh.write(b"mine")
with open(os.path.join(repo, "client", "files", "README.md"), "w") as fh:
    fh.write("not a release file")
with open(os.path.join(repo, "client", "objects", "c_box", "0.png"), "wb") as fh:
    fh.write(b"png")
# client/objects/manifest.json as tools/custom_objects.py has it: {id: entry},
# frames in client/objects/<id>/.
with open(os.path.join(repo, "client", "objects", "manifest.json"), "w") as fh:
    json.dump({"c_box": {"title": "Ящик", "frames": ["0.png"], "anchor": [0, 0], "kind": "sprite"},
               "c_sky": {"title": "Небо", "frames": ["0.jpg"], "kind": "background"},
               "Not_an_id": {"title": "x", "frames": ["0.png"]}}, fh)
with open(os.path.join(res, "locations", "libs", "Lib.swf"), "wb") as fh:
    fh.write(bad_bytes)
os.makedirs(os.path.join(store, sha(gone + b"1")[:2]))
with open(os.path.join(store, sha(gone + b"1")[:2], sha(gone + b"1")), "wb") as fh:
    fh.write(gone + b"1")
r = A.read_release(repo)
check("release: base less remove.txt, extra.txt, client/files (not its README), the objects",
      sorted((p, e.origin) for p, e in r.items()),
      [("locations/libs/Extra.swf", "extra"), ("locations/libs/Lib.swf", "base"),
       ("locations/libs/Store.swf", "base"),
       ("locations/libs/background/c_sky.swf", "object"),
       ("locations/libs/sprite/c_box.swf", "object"),
       ("locations/libs/sprite/c_mine.swf", "files")])
art = A.Art(repo, res=[res], store=[store], cache=os.path.join(TMP, "cache1"))
check("read: bytes of the wrong sha256 do not count, the right ones do; the store by sha",
      (art.read("locations/libs/Lib.swf"), art.read("locations/libs/Store.swf"),
       art.read("locations/libs/sprite/c_mine.swf"), art.read("locations/libs/Nope.swf")),
      (None, gone + b"1", b"mine", None))
with open(os.path.join(res, "locations", "libs", "Lib.swf"), "wb") as fh:
    fh.write(lib_bytes)
check("read: a path in another case is the release's file (Release.Find)",
      (art.read("LOCATIONS/libs/lib.swf") == lib_bytes, art.entry("locations/LIBS/lib.SWF").path),
      (True, "locations/libs/Lib.swf"))
check("local_ext: the ext ids of client/files and of the objects",
      A.local_ext(repo), ({"c_mine", "c_box"}, {"c_sky"}))
# This repository's own objects (client/objects, tools/custom_objects.py):
# each is an ext sprite of the release to the editor and the lint, at the
# path the build writes it to.
import custom_objects  # noqa: E402
OBJS = custom_objects.load()
check("objects: every object of client/objects is in the release list where custom_objects "
      "builds it, and a sprite the lint accepts",
      sorted((custom_objects.release_path(o, e), rel.get(custom_objects.release_path(o, e)).origin
              if rel.get(custom_objects.release_path(o, e)) else None,
              o in (extra[1] if e["kind"] == "background" else extra[0])) for o, e in OBJS.items()),
      sorted((custom_objects.release_path(o, e), "object", True) for o, e in OBJS.items()))
check("cache_file: only a sha and a plain name, never a way out",
      [art.cache_file(*a) for a in (("../x", "manifest.json"), ("a" * 64, "../../etc/passwd"),
                                    ("a" * 64, ".hidden"), ("a" * 64, "nofile.webp"))],
      [None, None, None, None])

# --- swf_summary, standard library only -----------------------------------------------------------
lib2 = swf([shape(1, (0, 40, 0, 40)), sprite(2, [[place(1, 1)]] * 7), sprite(3, [[place(1, 2)]]),
            export([(2, "b.png"), (3, "a.png")])])
painted = swf([shape(1, (0, 40, 0, 40)), sprite(3, [[place(1, 1)]] * 5), place(1, 3, matrix(tx=20))])
check("swf_summary: exports sorted, no stage for a library of symbols",
      A.swf_summary(lib2), {"exports": ["a.png", "b.png"], "stage": False, "frames": 1})
check("swf_summary: a root that places a clip has a stage and its clip's frames",
      A.swf_summary(painted), {"exports": [], "stage": True, "frames": 5})

# --- pictures ---------------------------------------------------------------------------------------------
try:
    import numpy as np
    from PIL import Image
except ImportError:
    Image = np = None
real = A.Art(cache=os.path.join(TMP, "cache"))
MOUNTAINS = real.read(A.lib_path("Mountains")) if Image is not None else None


def signature(img):
    """16 x 12 blocks of mean colour, four bits a channel, as hex."""
    rgb = Image.new("RGB", img.size)
    rgb.paste(img, (0, 0), img)
    small = rgb.resize((16, 12), Image.BOX)
    px = (small.getpixel((x, y)) for y in range(12) for x in range(16))
    return "".join("%x%x%x" % (r // 16, g // 16, b // 16) for r, g, b in px)


def sig_diff(a, b):
    d = [abs(int(x, 16) - int(y, 16)) for x, y in zip(a, b)]
    return max(d), sum(1 for v in d if v) / len(d)


SIGS = {
    "static/35": (
        "666baa998986db8ca8886775998ccaba9887cbacbacba775ca8ba8ca8cb8ba8dc9ca8cb9aa9ba9998987a98998"
        "aa9997ba7ba7986a97aa8dcbcb9db9a98a97a98cb9cb9ba8ba7ba7ba7a96cb8b97ca8ba9cb9cb8db9ba8ba9ba8"
        "a97ba7a97876ba8ca7ca8a97a97a97ba7ba8a97ba8ba7b97a97a97877766ba7cb8ca8ba7997997998a99bbabba"
        "ba7dc9cb8cb8a97876ca7ba7a97a97a98bbadccaaa999766765cb8dc8cb8cb8cb8ba7a96aa8aa9875887665444"
        "665876ba7db8dc8dc8dc8dc8875986ba8ba8ca8ca8a97986aa7a97886a97ba7cb8dc8dc8db8dc8ba8a97986ba7"
        "ca8ba7a97a97a97ba8db8ca8986875cb8ba7db8db8ba7a97a86db8db8ba8ba8cb8b97ba8ba8765ba7a96ca7dc8"
        "cb8dc8dc8dc8dc9cb8a97986cb8ba7ca8ba8"),
    "static/1": (
        "ca9ca8ca8ba8ba8ba8ba8ba8ba8ba8a97a97a98887998a98cb9cb9ca8ba8ba7ca8ca8ca8ba8ba8b98ba8ba8987"
        "998988ca9ca8ca8ba8ba8ba8ca8ba8ba8ca8ba8886a98a98998a98cb9ca8ca9cb9ca9ba8ba8a97997ba9ba8b98"
        "a98987887997cb9ca8ca9ca9cb9cb9a98987876987ba9ba8ba8ba8a98a98ca8ba8a97ba8cb8ca8ba8ba8a97a98"
        "ca9cb9ba8ba8a98987ba7a98987ba9ca8ca9ca8ca8cb9cb8ca8ba8998a98988a98ca8ca9ca9ca9ba8ba8ca9ca9"
        "ba9aa8ba9a98a98998998998ba8ca8ba9ba8ca8ba8ca9ba9ba8987a98998a98998a98a98ba8ba8ba8ba8a98a97"
        "ca8cb9987998988998a98b98ba9aa8ba8ba8ca9ba8998a98ba8987887988998a98ba8ba8a98a98a98ba8ba8ba8"
        "cb8ba8988a98887998a98ba8ba9ba9a98a98"),
    "desert/0001": (
        "ba6b96b96b96a96a96ca6ca6b96ca6ca6ba6b96ba6ba6ca6a96b96a96ba6ca6ca6ca6ba6ba6ca6ca6ca6a96a96"
        "ba6ba6ca6ba6ca6ca6ca7ca7ca6ca6ca6ca6ca6ca6ca6ca6ca7b96ca6ca6ca6ba6ba6ba7ca7ca6ba6ba6ca6ca6"
        "ca6ca6ba6ba6ca7ca7ca7ca6ca6ca6ca6ba6ba6ca6ca6ca6ca6ca6ca6db8ba6a96ba7ca7ba6ca6ca6ba6ca6ca6"
        "ca6a96985b96ba6ca6ca6ca6ca6ca7ca7ca7ca6ca6ca6ba6a96a96874a96a96a96ca7ca6ca6ca6ca6ca6ca7ca6"
        "ca7cb8a97764a95ca6ba7ca7ca6ca6ca6ca6cb8874a96ca6ba6a95ba6ba6ca6ba6ba6ba6ca6ca6ca7ca7ca7ba7"
        "ba7ba6ca6ca6ba6ba6b96a96985985ca6ca7cb8cb8ca7ca6ca6ca6ca6ca6ca6ca6b96b96985a85ca6ca7ca7ca7"
        "ca6ca6ca7ba6b96ca6ca6ca6ca6ca7ba6ba6"),
}

if Image is None:
    print("  --  Pillow or numpy not installed: picture checks skipped (WSL ~/venvs/lavagd has them)")
elif MOUNTAINS is None:
    print("  --  the original's SWFs not found (LAVA_ART_RES / LAVA_ART_STORE): picture checks skipped")
else:
    import swfx
    import location_art

    # --- the cache ---
    man = real.library("Mountains")
    e01 = man["symbols"]["edge01.png"]
    check("cache: Mountains' 90 symbols; edge01 as the client draws it (424 px), WebP with its "
          "alpha; the tile bg_desert2.jpg opaque, JPEG",
          (len(man["symbols"]), e01["w"], e01["file"].endswith(".webp"), e01["opaque"],
           man["symbols"]["bg_desert2.jpg"]["file"].endswith(".jpg"), man["stage"]),
          (90, 424, True, False, True, None))
    check("cache: every picture has a thumbnail of at most 128 px, files in place",
          [n for n, p in man["symbols"].items()
           if max(p["tw"], p["th"]) > 128 or not real.cache_file(man["sha"], p["thumb"])
           or not real.cache_file(man["sha"], p["file"])], [])
    keep = location_art.extract_swf
    location_art.extract_swf = lambda *a: (_ for _ in ()).throw(AssertionError("extracted again"))
    try:
        again = A.Art(cache=real.cache).library("Mountains")
    finally:
        location_art.extract_swf = keep
    check("cache: a second editor reads the manifest, nothing is extracted again", again == man, True)
    teph = real.library("Tephnuty")
    img, off = real.lib_picture("Tephnuty", "Tephnuty_nosh.jpg")
    check("cache: a painted library exports nothing; its picture serves any name (2560 x 1920)",
          (teph["symbols"], teph["stage"]["opaque"], img.size, off), ({}, True, (2560, 1920), (0, 0)))
    camp = real.sprite("a_campfire.png")
    check("cache: an ext sprite's first frame and its frame count", (camp["frames"], bool(camp["stage"])),
          (12, True))
    check("cache: a missing ext sprite is None", real.sprite("tent2.png"), None)

    # --- where things land ---
    m35 = L.load(real.location_path(35))
    lib35 = swfx.Swf(real.read(A.lib_path(m35["attrs"]["library"])))
    one = copy.deepcopy(m35)
    sp = next(s for s in m35["sprites"] if s["type"] == "lib" and s["id"] in lib35.exports)
    one["sprites"] = [dict(sp, anchors=sp["anchors"][:1])]
    got = A.render(one, real, ["sprites"])[0].getbbox()
    pic, _o = lib35.library_bitmap(sp["id"])
    bx = pic.getbbox()
    px, py = L.cell_px(*sp["anchors"][0])
    x0, y0 = A._round(px + sp["dx"]), A._round(py + sp["dy"])
    check("render: a lib sprite's bounds top-left at cell_px(anchor) + (dx, dy) (%s)" % sp["id"],
          got, (max(0, x0 + bx[0]), max(0, y0 + bx[1]), x0 + bx[2], y0 + bx[3]))
    sp = next(s for s in m35["sprites"] if s["type"] == "ext" and real.sprite(s["id"]))
    one["sprites"] = [dict(sp, anchors=sp["anchors"][:1])]
    got = A.render(one, real, ["sprites"])[0].getbbox()
    pic, o = swfx.Swf(real.read(A.sprite_path(sp["id"]))).root_bitmap()
    bx = pic.getbbox()
    px, py = L.cell_px(*sp["anchors"][0])
    x0, y0 = A._round(px + sp["dx"] + o[0]), A._round(py + sp["dy"] + o[1])
    check("render: an ext sprite's origin at cell_px(anchor) + (dx, dy) (%s)" % sp["id"],
          got, (max(0, x0 + bx[0]), max(0, y0 + bx[1]), x0 + bx[2], y0 + bx[3]))
    # An object of ours, put on a cell the way custom_objects.place() writes
    # it into the XML: its anchor pixel stands on the cell's centre.
    for oid, ent in sorted(OBJS.items()):
        if ent["kind"] != "sprite":
            continue
        for gx, gy in ((10, 20), (10, 21)):
            pl = custom_objects.place(oid, ent, gx, gy)
            sp = L.load(('<location width="32" height="64">%s</location>' % pl["sprite"]).encode())["sprites"][0]
            one["sprites"] = [sp]
            got = A.render(one, real, ["sprites"])[0].getbbox()
            pic = Image.open(A.object_file(ROOT, oid, ent["frames"][0])).convert("RGBA")
            bx = pic.getbbox()
            px, py = L.cell_px(gx, gy)
            x0, y0 = px - ent["anchor"][0], py - ent["anchor"][1]
            check("render: object %s placed on %d:%d by custom_objects.place, its anchor on the "
                  "cell's centre" % (oid, gx, gy),
                  got, (x0 + bx[0], y0 + bx[1], x0 + bx[2], y0 + bx[3]))
        item = next((p for p in real.palette(m35["attrs"]["library"]) if p["name"] == oid), None)
        check("palette: object %s is there with its manifest's anchor, front and frames" % oid,
              (item or {}).get("origin"), "object")
        check("  ..anchor, front, game frames",
              ((item or {}).get("anchor"), (item or {}).get("front"), (item or {}).get("frames")),
              (list(ent["anchor"]), [list(c) for c in ent["front"]],
               A.object_frames(custom_objects.load_raw()[oid])))
    m1 = L.load(real.location_path(1))
    dc = next(d for d in m1["bgdecorations"] if d["dx"] > 100 and d["dy"] > 100 and d["type"] != "ext")
    one = copy.deepcopy(m1)
    one["bgdecorations"] = [dc]
    got = A.render(one, real, ["decals"])[0].getbbox()
    pic, _o = swfx.Swf(MOUNTAINS).library_bitmap(dc["id"])
    bx = pic.getbbox()
    x0, y0 = A._round(dc["dx"]), A._round(dc["dy"])
    check("render: a decal's top-left at (dx, dy) (%s)" % dc["id"],
          got, (x0 + bx[0], y0 + bx[1], x0 + bx[2], y0 + bx[3]))
    bg = np.asarray(A.render(m1, real, ["background"])[0])
    check("render: the background tile repeats every 800 x 582 px from (0, 0)",
          (bool((bg[:, :800] == bg[:, 800:1600]).all()), bool((bg[:582] == bg[582:1164]).all()),
           int(bg[..., 3].min())), (True, True, 255))
    lay = A.render_layers(m1, real, ["sprites"])["sprites"]
    full, rep = A.render(m1, real, ["sprites"])
    check("render_layers: one layer alone is that layer of render", np.array_equal(
        np.asarray(lay), np.asarray(full)), True)
    check("render: two anchors on the extra row y == H, drawn all the same",
          (rep["sprites"]["extra_row"], rep["sprites"]["drawn"],
           A.render(m1, real, ["sprites"], extra_row=True)[1]["sprites"]["drawn"]),
          (2, sum(len(s["anchors"]) for s in m1["sprites"]), sum(len(s["anchors"]) for s in m1["sprites"])))
    xs, xa = next((s, a) for s in m1["sprites"] for a in s["anchors"] if a[1] >= m1["height"]
                  and s.get("type") != "ext")
    one = copy.deepcopy(m1)
    one["sprites"] = [dict(xs, anchors=[xa])]
    pic, _o = real.lib_picture(m1["attrs"]["library"], xs["id"])
    cx, cy = L.cell_px(*xa)

    def clipped(x, y):
        """The box the picture covers on the canvas with its top-left at x, y."""
        canvas = Image.new("RGBA", (m1["width"] * L.CELL_W, m1["height"] * L.ROW_H), (0, 0, 0, 0))
        swfx.blit(canvas, pic, x, y)
        return canvas.getbbox()
    check("  ..from the location's top-left corner, as the client (no such cell: dx, dy from 0, 0), at the cell"
          " beyond only when asked (%s)" % xs["id"],
          (A.render(one, real, ["sprites"])[0].getbbox(),
           A.render(one, real, ["sprites"], extra_row=True)[0].getbbox()),
          (clipped(A._round(L.num(xs["dx"])), A._round(L.num(xs["dy"]))),
           clipped(A._round(cx + L.num(xs["dx"])), A._round(cy + L.num(xs["dy"])))))

    # --- reference renders ---
    print_sigs = "--print-signatures" in sys.argv
    for ref, want in SIGS.items():
        img, rep = A.render(L.load(real.location_path(ref)), real, "art", scale=0.125)
        s = signature(img)
        if print_sigs:
            print('    "%s": "%s",' % (ref, s))
            continue
        worst, share = sig_diff(s, want or "")
        check("reference render %s: 16 x 12 blocks within one step of four bits, most equal"
              % ref, (len(s), worst <= 1, share <= 0.15), (576, True, True))

    # --- mobs ---
    types = real.mob_types()
    good = next(t for t, r in sorted(types.items()) if r == "m2")
    path, ph = real.mob_icon(good)
    ic = Image.open(path)
    check("mobs: an icon of the stand frame, facing the camera, at most 64 px",
          (ph, max(ic.size) <= 64, ic.size[1] == 64 or ic.size[0] == 64), (False, True, True))
    lost = sorted(t for t, r in types.items() if r in ("f11_antelope22", "m8_broken", "q4_v2"))
    check("mobs: the three resources without a stand animation (m8_broken, q4_v2, f11_antelope22) "
          "get the placeholder",
          (lost, [real.mob_icon(t)[1] for t in lost]),
          ([1807, 4248, 4297, 5249, 5250, 5251], [True] * 6))
    img, rep = A.render(m35, real, ["mobs"])
    want_mobs = sum(1 for _x, _y, t in L.mob_slots(m35) if t and real.mob(t))
    check("render: the inhabitants of <mobs> stand on their cells (layer mobs)",
          (rep["mobs"]["drawn"], want_mobs > 0), (want_mobs, True))

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("location art OK")
