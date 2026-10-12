"""What the real Flash Player 32 did with the location, against what it
should have done (README.md beside this file). Reads what host.as POSTed to
the stand and what the stand served, writes report.txt and the pictures
(scene_quarter.png, inst_<n>_<id>.png, crop_<n>_<id>.png) into OUTDIR, and
exits 1 if anything is off. Standard library only.

    python3 check.py OUTDIR LOCATION.xml OBJDIR TOOLS
"""
import glob
import os
import re
import struct
import sys
import zlib

OUT, XML, OBJDIR, TOOLS = sys.argv[1:5]
RUN = os.path.join(OUT, "run")
sys.path.insert(0, TOOLS)
import custom_objects as co  # noqa: E402
import swfgen  # noqa: E402

lines, failed = [], [0]
WATCH = 50          # host.as: game frames each object is watched
MAX_OURS = 8        # host.as: objects of ours dumped


def say(ok, text):
    lines.append("%s %s" % ("ok  " if ok else "FAIL", text))
    if not ok:
        failed[0] += 1


def note(text):
    lines.append("  -- " + text)


def png_write(path, w, h, rgba):
    def chunk(typ, body):
        return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def load_dump(path):
    """(w, h, straight RGBA bytes) of a getPixel32 dump: 'WxH|row;row',
    a row is ARGB hex values joined by commas. AVM1 prints a pixel whose
    alpha is 128 or more as a negative number ('-37000001' is c8ffffff)."""
    with open(path, encoding="utf-8") as fh:
        dims, rows = fh.read().split("|", 1)
    w, h = map(int, dims.split("x"))
    out = bytearray()
    for row in rows.split(";")[:h]:
        for v in row.split(",")[:w]:
            v = int(v, 16) & 0xFFFFFFFF
            out += bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255, v >> 24))
    return w, h, bytes(out)


def posted(name):
    """The file the stand kept for a POST of this name, or None."""
    hits = sorted(glob.glob(os.path.join(RUN, "*_%s.txt" % name)))
    return hits[-1] if hits else None


def compare(got, want):
    """(alpha max diff, premultiplied colour max diff) of two RGBA images."""
    da = dc = 0
    for i in range(0, len(want), 4):
        ga, wa = got[i + 3], want[i + 3]
        da = max(da, abs(ga - wa))
        for c in range(3):
            dc = max(dc, abs(got[i + c] * ga // 255 - want[i + c] * wa // 255))
    return da, dc


# --- what should happen: the location's own objects ------------------------------------
with open(XML, encoding="utf-8") as fh:
    xml = fh.read()
expect = []          # (id, gx, gy, dx, dy)
counts = {"lib": 0, "ext": 0}
for m in re.finditer(r"<sprite\b([^>]*)>([^<]*)</sprite>", xml):
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    kind = attrs.get("type") or "lib"
    cells = "".join(m.group(2).split())
    for i in range(0, len(cells) - 3, 4):
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "ext" and attrs.get("id", "").startswith("c_"):
            expect.append((attrs["id"], int(cells[i:i + 2], 16), int(cells[i + 2:i + 4], 16),
                           int(attrs.get("dx") or 0), int(attrs.get("dy") or 0)))
objs = co.load(OBJDIR)

with open(os.path.join(RUN, "log.txt"), encoding="utf-8") if os.path.exists(os.path.join(RUN, "log.txt")) else open(os.devnull) as fh:
    log = fh.read().splitlines()
with open(os.path.join(RUN, "requests.log"), encoding="utf-8") if os.path.exists(os.path.join(RUN, "requests.log")) else open(os.devnull) as fh:
    requests = fh.read().splitlines()

# --- the film ran and the client's classes were in it -----------------------------------
start = next((l for l in log if " start: " in l), "")
say("LDParser=function" in start and "AnimationSprite=function" in start,
    "the client's own classes are in the film (%s)" % (start.split(" start: ")[-1] or "the film never started"))
say(any(l.endswith("DONE") or " DONE " in l for l in log), "the film finished within the time given")
parse = next((l for l in log if " parse: " in l), "")
m = re.search(r"lib=(\d+) ext=(\d+)", parse)
say(bool(m) and (int(m.group(1)), int(m.group(2))) == (counts["lib"], counts["ext"]),
    "LDParser read the location: %s (the XML has lib=%d ext=%d)" % (parse.split(" parse: ")[-1] or "nothing", counts["lib"], counts["ext"]))
for l in log:
    if " NO " in l:
        note(l.split(" ", 1)[1])

# --- every object of ours was fetched, built and stands where it should --------------------
ids = sorted({e[0] for e in expect})
for oid in ids:
    path = "/res/locations/libs/sprite/%s.swf" % oid
    ok = any(r.startswith("GET %s 200 " % path) for r in requests)
    say(ok and not any(r == "GET %s 404" % path for r in requests), "%s.swf was served to the client" % oid)
    say(oid in objs, "%s is an object of client/objects" % oid)
missing = sorted({r.split()[1] for r in requests if r.endswith(" 404")})
if missing:
    note("404 (the original game references a few files it never shipped): %s" % ", ".join(missing))
built = {}
for l in log:
    m = re.search(r" built (\S+) cell (\d+):(\d+) at ([-\d.]+),([-\d.]+)", l)
    if m:
        built.setdefault((m.group(1), int(m.group(2)), int(m.group(3))), []).append((float(m.group(4)), float(m.group(5))))
say(sum(len(v) for v in built.values()) == len(expect),
    "the client built every instance of ours: %d of %d" % (sum(len(v) for v in built.values()), len(expect)))
for oid, gx, gy, dx, dy in expect:
    want = (40 * gx + 20 * (gy % 2) + dx, 15 * gy + dy)
    got = built.get((oid, gx, gy), [None])[0]
    say(got is not None and abs(got[0] - want[0]) <= 0.5 and abs(got[1] - want[1]) <= 0.5,
        "%s on %d:%d stands at %s, the cell's centre + (dx, dy) = %d,%d" % (
            oid, gx, gy, "%.2f,%.2f" % got if got else "nowhere", want[0], want[1]))

# --- what each watched instance shows ------------------------------------------------------
for k in range(min(MAX_OURS, len(expect))):
    tp = posted("trace_%d" % k)
    if not tp:
        say(False, "instance %d: no report from the film" % k)
        continue
    with open(tp, encoding="utf-8") as fh:
        oid, cell, trace = fh.read().split("|")
    frames_seen = [int(v) for v in trace.split(",") if v not in ("", "undefined")]
    entry = objs.get(oid)
    if entry is None:
        continue
    n = len(entry["frames"])
    hold = swfgen.hold_for(entry["fps"]) if n > 1 else 1
    total = n * hold
    if n > 1:
        steps = all(b == a % total + 1 for a, b in zip(frames_seen, frames_seen[1:]))
        pics = sorted({(f - 1) // hold for f in frames_seen})
        # The clip loads on its own after the scene is built (a second
        # loadClip), so the first frames may find it not there yet.
        say(len(frames_seen) >= WATCH // 2 and steps and (pics == list(range(n)) or len(frames_seen) < total),
            "instance %d %s at %s: its own timeline steps one frame a game frame through %d frames "
            "and loops, showing pictures %s over %d frames" % (k, oid, cell, total, pics, len(frames_seen)))
    dp = sorted(glob.glob(os.path.join(RUN, "*_bmp_inst_%d_f*.txt" % k)))
    if not dp:
        say(False, "instance %d %s: no pixels from the film" % (k, oid))
        continue
    frame = int(re.search(r"_f(\d+)\.txt$", dp[-1]).group(1))
    w, h, got = load_dump(dp[-1])
    png_write(os.path.join(OUT, "inst_%d_%s.png" % (k, oid)), w, h, got)
    name = entry["frames"][(frame - 1) // hold]
    with open(os.path.join(OBJDIR, oid, name), "rb") as fh:
        pic = swfgen.picture(fh.read())
    if (w, h) != (pic.w, pic.h):
        say(False, "instance %d %s: drawn %dx%d, its picture %s is %dx%d" % (k, oid, w, h, name, pic.w, pic.h))
    elif pic.kind == "png":
        da, dc = compare(got, pic.rgba)
        say(da <= 1 and dc <= 2, "instance %d %s, frame %d: drawn as %s, alpha within %d, premultiplied colour within %d"
            % (k, oid, frame, name, da, dc))
    else:
        say(all(got[i + 3] == 255 for i in range(0, len(got), 4)),
            "instance %d %s, frame %d: the JPEG %s drawn %dx%d and opaque" % (k, oid, frame, name, w, h))
    cp = posted("bmp_crop_%d" % k)
    if cp:
        cw, ch, crop = load_dump(cp)
        png_write(os.path.join(OUT, "crop_%d_%s.png" % (k, oid)), cw, ch, crop)
qp = posted("bmp_scene_quarter")
if qp:
    qw, qh, quarter = load_dump(qp)
    png_write(os.path.join(OUT, "scene_quarter.png"), qw, qh, quarter)
    note("scene_quarter.png: the whole location at a quarter, %dx%d" % (qw, qh))
if len(expect) > MAX_OURS:
    note("%d instances of ours; the first %d were watched" % (len(expect), MAX_OURS))
if not expect:
    note("the location places no object of ours (no ext sprite whose id starts with c_)")

lines.append("%s: %d checks failed" % ("FAILED" if failed[0] else "OK", failed[0]))
with open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
sys.exit(1 if failed[0] else 0)
