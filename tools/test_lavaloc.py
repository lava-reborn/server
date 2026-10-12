"""Location files: tools/lavaloc.py reads and writes them as the game does.

Every location file in LAVA_RES goes through the raw layer, the cell codec
and the semantic encoder and comes back byte for byte; what it decodes is
what server/world.py reads and what data/exits_sides.json says; the front
templates, the grid maths and the depth order follow the client's classes
(recon/as-src/lol/core/location); a file the writer makes is one line in
the static style that world.Location reads the same.
"""
import copy
import glob
import hashlib
import json
import os
import random
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import lavaloc as L  # noqa: E402
import world  # noqa: E402
from testkit import check, fails  # noqa: E402

RES = world.RES
LOC = os.path.join(RES, "locations")


def files():
    out = []
    for sub in ("static", "desert", "deadloc"):
        out += sorted(glob.glob(os.path.join(LOC, sub, "*.xml")))
    return out


FILES = files()
STATIC = {int(os.path.basename(f)[:-4]): f for f in FILES
          if os.path.basename(os.path.dirname(f)) == "static"}
t0 = time.time()

# --- the files are there ---------------------------------------------------------
check("LAVA_RES holds the 1381 static files 0..1380, 11 desert, 4 deadloc",
      (sorted(STATIC)[:1] + sorted(STATIC)[-1:], len(STATIC),
       len([f for f in FILES if "/desert/" in f.replace(os.sep, "/")]),
       len([f for f in FILES if "/deadloc/" in f.replace(os.sep, "/")])),
      ([0, 1380], 1381, 11, 4))

with open(os.path.join(ROOT, "data", "exits_sides.json"), encoding="utf-8") as fh:
    SIDES_TABLE = json.load(fh)["locations"]

# One pass over the files makes every check of a single file, each section's
# below, and keeps of a file's bytes, raw doc and model only what a later
# section reads again by name (KEEP_DOCS, KEEP_MODELS): all 1396 files' docs
# and models held at once took 624 MB, and with a dozen suites at once that
# was more than CI's runners have (2026-10-12). Each file goes through the
# checks in the order of the sections, so it meets them as it did when
# every section made its own pass.
F35 = STATIC[35]
FD = os.path.join(LOC, "desert", "0001.xml")
PINNED = (1, 35, 266, 270, 522)      # the locations FLASH_ZSORT pins to the player
rng = random.Random(7)
RT_SAMPLE = rng.sample(sorted(STATIC.values()), 40)   # "random edits survive a round trip"
KEEP_DOCS = {F35} | set(RT_SAMPLE)
KEEP_MODELS = {FD} | {STATIC[lid] for lid in PINNED}
DOCS, MODELS, RAW35 = {}, {}, None

bad_raw, bad_sem, bad_enc, bad_et = [], [], [], []
bad_world, bad_exits, bad_zones = [], [], []
bad_front, n_front = [], 0
same_bytes, bad_new = 0, []
bad_depth, inst, depth_s = [], 0, 0.0
tmpdir = tempfile.mkdtemp(prefix="lavaloc_")
tmp = os.path.join(tmpdir, "x.xml")
# The server's own reader on a file of our choosing: whichever of these
# world resolves an id through, it is pointed at that file for one read.
SERVER_PATHS = {n: getattr(world, n) for n in ("path_for", "static_path") if hasattr(world, n)}


def server_reads(lid, path):
    for n in SERVER_PATHS:
        setattr(world, n, lambda _lid: path)
    try:
        return world.Location(lid)
    finally:
        for n, fn in SERVER_PATHS.items():
            setattr(world, n, fn)


LID_OF = {f: lid for lid, f in STATIC.items()}
try:
    for f in FILES:
        with open(f, "rb") as fh:
            raw = fh.read()
        lid = LID_OF.get(f)
        # raw layer: byte for byte
        d = L.parse_raw(raw)
        if L.write_raw(d) != raw:
            bad_raw.append(f)
        m = L.decode(d)
        if L.write_raw(L.encode_into(copy.deepcopy(d), m)) != raw:
            bad_sem.append(f)
        if L.write_raw(L.encode(m, d)) != raw:
            bad_enc.append(f)
        root = ET.fromstring(raw[3:] if raw.startswith(L.BOM) else raw)
        kids = [(c.tag, dict(c.attrib)) for c in root]
        mine = [(c["tag"], {k: L.unescape(v) for k, v in c["attrs"]}) for c in d.children]
        if kids != mine or dict(root.attrib) != m["attrs"]:
            bad_et.append(f)
        # what the server reads (an overlay, data/locations, wins over RES for its id)
        if lid is not None and world.path_for(lid) == f:
            loc = world.Location(lid)
            W = m["width"]
            got = (loc.title, loc.fn, loc.width, loc.height, loc.war, loc.pvp,
                   loc.obstacles, loc.entries, loc.spawns)
            want = (m["attrs"].get("title", ""), m["attrs"].get("fn", ""), W, m["height"],
                    int(m["attrs"].get("war", 0)), int(m["attrs"].get("pvp") != "0"),
                    {L.cell_num(x, y, W) for x, y, _ in m["lists"]["obstacles"]},
                    [L.cell_num(x, y, W) for x, y, _ in m["lists"]["inzones"]],
                    [(L.cell_num(x, y, W), t) for x, y, t in L.mob_slots(m)])
            if got != want:
                bad_world.append(lid)
        if lid is not None and str(lid) in SIDES_TABLE and SIDES_TABLE[str(lid)] != L.exits_row(m):
            bad_exits.append(lid)
        if [c[:2] for c in m["lists"]["zones"]] != [c[:2] for c in m["lists"]["outzones"]]:
            bad_zones.append(f)
        # fronts
        for sp in m["sprites"]:
            fr = sp["front"] or ""
            if len(fr) % 4:
                continue
            for ax, ay in sp["anchors"]:
                n_front += 1
                if L.front_hex(L.front_cells(fr, ax, ay), ax, ay) != fr:
                    bad_front.append((f, sp["id"], ax, ay))
        # the writer
        if lid is not None:
            out = L.write_static(m)
            same_bytes += out == raw
            problems = []
            if not out.startswith(L.DECL.encode()) or out.startswith(L.BOM):
                problems.append("declaration")
            if out.count(b"\n") != 1 or not out.endswith(b"<serverdata>\r\n</serverdata></location>"):
                problems.append("not one line ending in <serverdata>\r\n</serverdata>")
            ET.fromstring(out)
            m2 = L.load(out)
            for k in ("pvp", "fn"):
                if k not in m2["attrs"]:
                    problems.append("no " + k)
            if m2["lists"] != {k: [tuple(c) for c in v] for k, v in m["lists"].items()}:
                problems.append("lists")
            if [(s["id"], s["anchors"], s["front"] or "") for s in m2["sprites"]] != \
                    [(s["id"], s["anchors"], s["front"] or "") for s in m["sprites"]]:
                problems.append("sprites")
            with open(tmp, "wb") as fh:
                fh.write(out)
            a, b = server_reads(lid, tmp), server_reads(lid, f)
            if (a.title, a.fn, a.width, a.height, a.war, a.pvp, a.obstacles, a.entries, a.spawns) != \
                    (b.title, b.fn, b.width, b.height, b.war, b.pvp, b.obstacles, b.entries, b.spawns):
                problems.append("world.Location reads it differently")
            if problems:
                bad_new.append((lid, problems))
        # depth: LDepthManager
        ts = time.time()
        o = L.depth_order(m)
        want = sorted((si, ai) for si, sp in enumerate(m["sprites"]) for ai in range(len(sp["anchors"])))
        inst += len(want)
        if sorted(o) != want:
            bad_depth.append(f)
        depth_s += time.time() - ts
        if f in KEEP_DOCS:
            DOCS[f] = d
        if f in KEEP_MODELS:
            MODELS[f] = m
        if f == F35:
            RAW35 = raw
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# --- raw layer: byte for byte ---------------------------------------------------------
check("raw parse -> write is byte-identical for every file", bad_raw, [])
check("decode -> re-encode of the cell lists is byte-identical for every file", bad_sem, [])
check("encode(decode(d), base=d) is byte-identical for every file", bad_enc, [])
check("the raw layer reads the same elements and attributes as ElementTree", bad_et, [])

# --- what the server reads -----------------------------------------------------------------
# (the pass's files come in the order of their names; the ids are reported in theirs)
check("world.Location reads every static file as the model does", sorted(bad_world), [])
check("data/exits_sides.json is every static file's outzones (exits_row)", sorted(bad_exits), [])
check("data/exits_sides.json has a row for every static file",
      [lid for lid in STATIC if str(lid) not in SIDES_TABLE], [])
# The locations of ours (data/locations, server/world.py OVERLAY): read and
# written byte for byte too, the server reads them as the model does, and
# their exits_sides rows are their exits_row.
bad_ours = []
for lid in world.overlay_ids():
    f = world.overlay_path(lid)
    with open(f, "rb") as fh:
        raw = fh.read()
    d = L.parse_raw(raw)
    m = L.decode(d)
    loc = world.Location(lid)
    W = m["width"]
    if L.write_raw(L.encode(m, d)) != raw:
        bad_ours.append((lid, "bytes"))
    if (loc.width, loc.height, loc.obstacles, loc.entries) != (
            W, m["height"], {L.cell_num(x, y, W) for x, y, _ in m["lists"]["obstacles"]},
            [L.cell_num(x, y, W) for x, y, _ in m["lists"]["inzones"]]):
        bad_ours.append((lid, "world.Location"))
    if SIDES_TABLE.get(str(lid)) != L.exits_row(m):
        bad_ours.append((lid, "exits_sides"))
check("the locations of ours (%d in data/locations): bytes, the server's reading and their "
      "exits_sides rows agree with the model" % len(world.overlay_ids()), bad_ours, [])
check("zones are the outzones cells, in their order, in every file", bad_zones, [])

# --- fronts ---------------------------------------------------------------------------------
check("front_hex(front_cells(f, anchor)) == f for every sprite instance (%d)" % n_front,
      bad_front[:5], [])
check("front: an odd anchor row moves odd relative rows one cell right (LDParser.getHexCoord)",
      (L.front_cells("7f7f80818180", 10, 20), L.front_cells("7f7f80818180", 10, 21)),
      ([(9, 19), (10, 21), (11, 20)], [(10, 20), (11, 22), (11, 21)]))
check("front: offsets in the even-row convention give the same cells",
      [L.offsets_cells(L.front_offsets(fr), ax, ay) == L.front_cells(fr, ax, ay)
       for fr in ("7f7f80818180", "8080", "7e807f80808081808280") for ax, ay in ((5, 6), (5, 7))],
      [True] * 6)
check("front: offsets_front is front_offsets' inverse",
      L.offsets_front(L.front_offsets("7e807f80808081808280")), "7e807f80808081808280")

# The owner's objects (tools/custom_objects.py place) are written in the
# same convention: what place() puts into a location is what lavaloc reads.
import custom_objects  # noqa: E402
OBJ = {"kind": "sprite", "anchor": (3, 5), "front": [(-1, 0), (0, 0), (1, 1)],
       "footprint": [(0, 0), (1, 1), (0, -1), (-1, 1)]}
bad_obj = []
for gx, gy in ((10, 20), (10, 21), (0, 1)):
    pl = custom_objects.place("c_probe", OBJ, gx, gy)
    m = L.load(('<location width="32" height="64">%s<obstacles>%s</obstacles></location>'
                % (pl["sprite"], pl["obstacles"])).encode())
    sp = m["sprites"][0]
    got = ((sp["id"], sp["type"], sp["dx"], sp["dy"], sp["anchors"]),
           sp["front"], L.front_cells(sp["front"], gx, gy), L.offsets_cells(OBJ["footprint"], gx, gy),
           m["lists"]["obstacles"])
    want = (("c_probe", "ext", -3, -5, [(gx, gy)]),
            L.offsets_front(OBJ["front"]), pl["front"], pl["footprint"],
            [(x, y, "f") for x, y in pl["footprint"]])
    if got != want:
        bad_obj.append((gx, gy, got, want))
check("objects: custom_objects.place() writes a sprite, front and footprint walls that lavaloc "
      "reads back as the same cells, on even and odd rows", bad_obj, [])

# --- the grid ----------------------------------------------------------------------------------
mism = 0
for gy in range(0, 129):
    for gx in range(0, 64):
        x, y = L.cell_px(gx, gy)
        for ddx, ddy in ((0, 0), (10, 0), (-10, 0), (0, 4), (0, -4), (15, 2), (-15, -2)):
            if L.px_cell(x + ddx, y + ddy) != (gx, gy):
                mism += 1
check("px_cell(cell_px(c)) == c, and 6 points inside each hex, over 64 x 129 cells", mism, 0)
check("cell_px: odd rows half a cell right, 15 px per row",
      [L.cell_px(0, 0), L.cell_px(0, 1), L.cell_px(3, 2), L.cell_px(63, 127)],
      [(0, 0), (20, 15), (120, 30), (2540, 1905)])
asym = [(a, b) for a in ((7, 8), (7, 9)) for b in L.neighbours(*a) if a not in L.neighbours(*b)]
check("neighbours are mutual and six", (asym, len(set(L.neighbours(7, 8))), len(set(L.neighbours(7, 9)))),
      ([], 6, 6))
check("neighbours' centres are one hex away (40 px across, 25 px diagonally)",
      sorted({round(((L.cell_px(*n)[0] - L.cell_px(7, 9)[0]) ** 2
                     + (L.cell_px(*n)[1] - L.cell_px(7, 9)[1]) ** 2) ** 0.5)
              for n in L.neighbours(7, 9)}), [25, 40])
check("cell_num / num_cell", (L.cell_num(5, 3, 64), L.num_cell(197, 64)), (197, (5, 3)))

# --- the writer -----------------------------------------------------------------------------------
check("write_static: every static file rewritten in the static style reads the same "
      "(declaration, one line, pvp and fn, lists, sprites, world.Location)", sorted(bad_new)[:5], [])
print("  ..  write_static reproduces %d of %d static files byte for byte" % (same_bytes, len(STATIC)))
check("write_static reproduces most static files byte for byte (the static style)",
      same_bytes >= 1300, True)

# --- edits change only what they edit -----------------------------------------------------------------
d35, raw35 = DOCS[F35], RAW35
m = L.decode(d35)
m["lists"]["obstacles"].append((1, 1, "f"))
once = L.write_raw(L.encode(m, d35))
m["lists"]["obstacles"].pop()
twice = L.write_raw(L.encode(m, d35))
changed = [c["tag"] for c, c0 in zip(L.parse_raw(once).children, d35.children) if c != c0]
check("an obstacle added changes only <obstacles>; taken away, the bytes are the original's",
      (changed, twice == raw35), (["obstacles"], True))
m = L.decode(d35)
a0 = m["sprites"][3]["anchors"][0]
m["sprites"][3]["anchors"][0] = (a0[0] + 1, a0[1])
moved = L.parse_raw(L.write_raw(L.encode(m, d35)))
m["sprites"][3]["anchors"][0] = a0
check("a sprite moved changes only that <sprite>; moved back, the bytes are the original's",
      ([i for i, (c, c0) in enumerate(zip(moved.children, d35.children)) if c != c0],
       L.write_raw(L.encode(m, d35)) == raw35),
      ([[c["tag"] for c in d35.children].index("sprite") + 3], True))
m = L.decode(d35)
m["attrs"]["title"] = 'Рынок "Б" & <ко>'
d2 = L.encode(m, d35)
check("a new title is escaped, the other attributes and children keep their bytes",
      ([k for (k, v), (k0, v0) in zip(d2.root_attrs, d35.root_attrs) if v != v0],
       dict(d2.root_attrs)["title"], d2.children == d35.children,
       L.load(L.write_raw(d2))["attrs"]["title"]),
      (["title"], "Рынок &quot;Б&quot; &amp; &lt;ко&gt;", True, 'Рынок "Б" & <ко>'))
m = L.decode(d35)
m["lists"]["outzones"].append((30, 40, "a"))
d3 = L.encode(m, d35)
m3 = L.decode(d3)
check("a door added to outzones is added to zones too (derive_zones)",
      (m3["lists"]["zones"][-1], m3["lists"]["outzones"][-1]), ((30, 40, ""), (30, 40, "a")))
m = L.decode(d35)
m["sprites"].append({"id": "c_house", "type": "ext", "dx": -90.5, "dy": -136,
                     "front": L.offsets_front([(-1, 0), (0, 0), (1, 0)]), "anchors": [(30, 65)]})
m["bgdecorations"].append({"id": "ground05.png", "type": None, "dx": 12.346, "dy": -3})
d4 = L.parse_raw(L.write_raw(L.encode(m, d35)))
tags = [c["tag"] for c in d4.children]
check("a new sprite goes after the others, a new decal after the decals, in the static style",
      (d4.children[tags.index("bgdecoration") - 1]["attrs"],
       d4.children[len(tags) - 1 - tags[::-1].index("bgdecoration")]["attrs"]),
      ([("id", "c_house"), ("dx", "-90.5"), ("dy", "-136"), ("front", "7f8080808180"),
        ("type", "ext")],
       [("id", "ground05.png"), ("dx", "12.35"), ("dy", "-3"), ("type", "lib")]))
check("fmt_num: at most two places, no trailing zeros",
      [L.fmt_num(v) for v in (-115, 12.5, 7.25, 0.004, -0.0, 3.0, "1.50")],
      ["-115", "12.5", "7.25", "0", "0", "3", "1.5"])

# --- a copy of a template, normalised ---------------------------------------------------------------------
fd = FD
n = L.normalized(MODELS[fd])
out = L.write_static(n)
nm = L.load(out)
check("normalized(desert template): no BOM, the declaration, <background> from bg, pvp and fn "
      "written, types spelled out",
      (out[:5], nm["background"], "pvp" in nm["attrs"], "fn" in nm["attrs"],
       {s["type"] for s in nm["sprites"]} <= {"lib", "ext"},
       {s["type"] for s in nm["bgdecorations"]} <= {"lib", "ext"}),
      (b"<?xml", {"type": "lib", "id": MODELS[fd]["attrs"]["bg"], "fx": ""}, True, True, True, True))
check("normalized keeps the pvp the client reads (absent = open)",
      (MODELS[fd]["attrs"].get("pvp"), nm["attrs"]["pvp"]), (None, "1"))
check("normalized keeps every cell list", nm["lists"] == MODELS[fd]["lists"], True)

# --- depth: LDepthManager -----------------------------------------------------------------------------------
synthetic = {"sprites": [
    {"id": "back", "front": L.front_hex([(4, 10), (5, 10), (6, 10)], 5, 10), "anchors": [(5, 10)]},
    {"id": "front", "front": L.front_hex([(5, 12), (6, 12)], 5, 12), "anchors": [(5, 12)]},
    {"id": "aside", "front": "8080", "anchors": [(20, 30)]},
    {"id": "nofront", "front": "", "anchors": [(5, 11)]}]}
order = [synthetic["sprites"][s]["id"] for s, _ in L.depth_order(synthetic)]
check("depth: an object whose front is lower in a shared column is drawn over the other",
      order.index("front") > order.index("back"), True)
check("depth: every instance is drawn once", sorted(order), ["aside", "back", "front", "nofront"])
objs = L.depth_sort(L.scene_objects(synthetic))
check("depth: a walker in front of a front line goes over it, behind it under it",
      (L.walker_index(objs, 5, 13) > [o.sprite for o in objs].index(1),
       L.walker_index(objs, 5, 9) <= [o.sprite for o in objs].index(0)), (True, True))
check("depth: the client's for..in walk takes <sprite> elements last to first",
      [o.sprite for o in L.scene_objects(synthetic)], [3, 2, 1, 0])
check("depth_order: every sprite instance of every file, once (%d instances)" % inst, bad_depth, [])
print("  ..  depth_order over all files: %.1f s" % depth_s)

# --- what the real player does ---------------------------------------------------------------------
# Flash Player 32 (the launcher's flashplayer.exe), headless under Wine and
# Xvfb in a --network none container, running the client's own LDParser,
# SceneObject and LDepthManager copied byte for byte out of main.swf
# (2026-10-12). Pinned as it came out: Array.sortOn of crafted arrays, the
# zSort order and the order decals are painted in, for five locations.
FLASH_SORTS = [
    ([2, 1, 2, 1, 2], [3, 1, 0, 2, 4]),
    ([2, 2, 2, 0, 1], [3, 4, 0, 2, 1]),
    ([0, 2, 0, 0, 0], [0, 4, 2, 3, 1]),
    ([1, 1, 0, 1, 2, 0, 2, 0], [5, 7, 2, 0, 1, 3, 4, 6]),
    ([2, 0, 2, 2, 2, 1, 0, 1, 1, 1, 1, 2], [6, 1, 7, 9, 8, 5, 10, 0, 4, 3, 2, 11]),
    ([0] * 24, list(range(24))),
]
check("avm1_sort: Array.sortOn's own order of equal keys, as the player gave it",
      [L.avm1_sort(range(len(k)), k.__getitem__) for k, _ in FLASH_SORTS],
      [o for _, o in FLASH_SORTS])


def digest(items):
    return hashlib.sha256("|".join(items).encode()).hexdigest()[:24]


def flash_num(v):
    v = float(v)
    return str(int(v)) if v.is_integer() else repr(v)


FLASH_ZSORT = {1: "99f5f312760f4d970d4366be", 35: "1723162005e3841d264075e5",
               266: "03539e9f4e6eda4acd8f3c56", 270: "41a356665a0613b87fedf889",
               522: "dfe940d1e3ffa88d58ec507f"}
FLASH_DECALS = {1: "208488cd260321d5f6679e2e", 266: "171125e195c3c37ddd0cee11",
                270: "8d74dc790cfe6fe5d18f6c46"}
got_z, got_d = {}, {}
for lid in FLASH_ZSORT:
    # the pass keeps PINNED's models; a location pinned here later and not
    # there is read again
    m = MODELS.get(STATIC[lid]) or L.load(STATIC[lid])
    got_z[lid] = digest("%s@%d,%d" % ((m["sprites"][s]["id"],) + tuple(m["sprites"][s]["anchors"][a]))
                        for s, a in L.depth_order(m))
    if lid in FLASH_DECALS:
        got_d[lid] = digest("%s@%s,%s" % (d["id"], flash_num(d["dx"]), flash_num(d["dy"]))
                            for d in reversed(m["bgdecorations"]))
check("depth_order is the player's zSort order (locations 1, 35, 266, 270, 522; 24..624 objects)",
      got_z, FLASH_ZSORT)
check("decals are painted last to first in the file, as the player's LDParser gave them",
      got_d, FLASH_DECALS)

# --- random edits survive a round trip ------------------------------------------------------------
# (the 40 files are rng's first draw, taken before the pass: RT_SAMPLE)
bad_rt = []
for f in RT_SAMPLE:
    m = L.decode(DOCS[f])
    for _ in range(5):
        x, y = rng.randrange(m["width"]), rng.randrange(m["height"])
        m["lists"]["obstacles"].append((x, y, rng.choice("f13")))
    out = L.write_raw(L.encode(m, DOCS[f]))
    back = L.load(out)
    if back["lists"]["obstacles"] != [tuple(c) for c in m["lists"]["obstacles"]]:
        bad_rt.append(f)
check("obstacles added at random come back as written (40 files)", bad_rt, [])

print("  ..  %d files, %.1f s" % (len(FILES), time.time() - t0))
print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("lavaloc OK")
