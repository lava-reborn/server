"""Locations of ours (data/locations): the server reads them first, one push
brings the same bytes to the client.

A location file reaches the game through two places kept apart on purpose:
the client draws from its own copy, which a release changes; the server
reads the original's slice (/opt/lava/res), which no deploy changes. A new
place, or an original one changed, therefore lives in the repository --
data/locations/static/<id>.xml -- and both sides take it from there:

  * server/world.py: static_path reads ours before the original's, path_for
    and is_wilderness go through it -- a new id 1381 is no packed map cell
    and never a desert template -- and static_ids is the two together;
  * client/build.py ships the same bytes as locations/static/<id>.xml, with
    a row for each in xml/loc_defs.xml (world.loc_defs), without which the
    client draws a desert where the server opens the file; and refuses an
    id client/files also has (262 «Тотем» is the client's alone);
  * data/build_exits_sides.py rewrites the rows of ours alone (rows_for),
    and travel's own reading of the file agrees with them;
  * bootstrap_http serves them, and the list with their rows, on a local run.

All of it on a made overlay (LAVA_LOC_OVERLAY, world.OVERLAY), so that the
repository's own data/locations is left as it is; its files are held to the
same rules here and in server/test_locations.py.

    python3 server/test_location_overrides.py
"""
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "data"))
sys.path.insert(0, os.path.join(ROOT, "client"))
sys.path.insert(0, HERE)
import world  # noqa: E402
import travel  # noqa: E402
import build_exits_sides as B  # noqa: E402
import new_location  # noqa: E402
import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "locations of ours (data/locations)"

W = tempfile.mkdtemp(prefix="test-loc-overrides-")
REPO_OVERLAY = world.OVERLAY
# The original's ids: the files of the slice the server reads.
ORIGINAL_IDS = sorted(i for i in map(world._static_name,
                                     os.listdir(os.path.join(world.RES, "locations", "static")))
                      if i is not None)
srv = None


def parts(raw):
    """(the <location> tag's attributes, the file without that tag and with
    its <mobs> taken out, the <mobs> body)."""
    m = re.search(rb"<location\b[^>]*>", raw)
    mobs = re.search(rb"<mobs>(.*?)</mobs>", raw, re.S)
    rest = raw[:m.start()] + raw[m.end():mobs.start()] + raw[mobs.end():]
    return dict(re.findall(rb'(\w+)="([^"]*)"', m.group(0))), rest, mobs.group(1)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


try:
    # --- the repository's own -----------------------------------------------------------------
    print("the repository's locations of ours")
    with io.open(os.path.join(ROOT, "data", "exits_sides.json"), encoding="utf-8") as fh:
        ES = json.load(fh)
    check("every one has its rows in data/exits_sides.json, read off its own outzones",
          [i for i in world.overlay_ids()
           if (ES["locations"].get(str(i)), ES["summary"].get(str(i))) != B.row(i, world.static_path(i))[:2]],
          [])
    check("262 «Тотем» is not one of them: its copy in client/files is the client's alone",
          262 in world.overlay_ids(), False)
    check("the overlay is the repository's data/locations unless LAVA_LOC_OVERLAY says otherwise",
          os.path.normpath(REPO_OVERLAY) == os.path.join(ROOT, "data", "locations")
          or bool(os.environ.get("LAVA_LOC_OVERLAY")), True)

    # --- a made overlay: a new place and a changed original -------------------------------------
    print("a made overlay")
    NEW = new_location.next_id(world.static_ids())
    check("a new place takes the first free id from 1381", NEW >= world.FIRST_NEW_ID, True)
    check("  ..which, with no file of its own, is a packed map cell to the server -- a desert",
          (world.is_wilderness(NEW), world.path_for(NEW).replace(os.sep, "/").split("/")[-2]),
          (True, "desert"))
    OV = os.path.join(W, "locations")
    os.makedirs(os.path.join(OV, "static"))
    PLACE = new_location.copy_xml(read(world.static_path(673)), "Проверочная", "ED_check")
    CHANGED = new_location.copy_xml(read(world.static_path(102)), "Черный рынок (наш)", "WH_Gold_Traders_old",
                                    keep_mobs=True)
    for i, data in ((NEW, PLACE), (102, CHANGED)):
        with open(os.path.join(OV, "static", "%d.xml" % i), "wb") as fh:
            fh.write(data)
    for junk in ("0%d.xml" % NEW, "notes.txt", "x.xml"):
        with open(os.path.join(OV, "static", junk), "w") as fh:
            fh.write("not a location")
    world.OVERLAY = OV
    world._CACHE.clear()
    a_new, rest_new, mobs_new = parts(PLACE)
    a_old, rest_old, mobs_old = parts(read(os.path.join(world.RES, "locations", "static", "673.xml")))
    check("the copy is the original's bytes but for its title, its fn and its <mobs>, emptied",
          (rest_new == rest_old, {k for k in a_old if a_old[k] != a_new.get(k)}, set(a_new) - set(a_old),
           mobs_new, len(mobs_old) > 0, a_new[b"title"].decode("utf-8")),
          (True, {b"title", b"fn"}, set(), b"", True, "Проверочная"))
    check("path_for: ours for the new id", world.path_for(NEW), os.path.join(OV, "static", "%d.xml" % NEW))
    check("  ..and ours before the original's for an id both have",
          world.path_for(102), os.path.join(OV, "static", "102.xml"))
    check("  ..and the original's where ours has none", world.path_for(5),
          os.path.join(world.RES, "locations", "static", "5.xml"))
    check("is_wilderness: the new id is a location now", world.is_wilderness(NEW), False)
    check("  ..and a packed cell is still one", world.is_wilderness(world.pack(6100, 1900)), True)
    loc = world.location(NEW)
    check("the new place is read as the client reads it: static/<id>.xml, its title, the copy's grid",
          (loc.file, loc.title, loc.width, loc.height, loc.spawns),
          ("static/%d.xml" % NEW, "Проверочная", 32, 64, []))
    check("  ..never one of the four desert templates", world.location(NEW).file.startswith("desert/"), False)
    check("the changed original is read from ours", world.location(102).title, "Черный рынок (наш)")
    check("static_ids: the original's and ours, each once; a stray name in the folder is no id",
          world.static_ids(), sorted(set(ORIGINAL_IDS) | {NEW}))
    check("overlay_ids: ours alone", world.overlay_ids(), [102, NEW])
    env = dict(os.environ, LAVA_LOC_OVERLAY=OV)
    got = subprocess.run([sys.executable, "-c", "import world; print(world.OVERLAY)"], cwd=HERE, env=env,
                         stdout=subprocess.PIPE, text=True).stdout.strip()
    check("LAVA_LOC_OVERLAY names the folder", got, OV)

    # --- data/exits_sides.json: the rows of ours alone ------------------------------------------
    print("exits_sides rows")
    es_copy = os.path.join(W, "exits_sides.json")
    shutil.copy(os.path.join(ROOT, "data", "exits_sides.json"), es_copy)
    before = read(es_copy)
    check("rows_for([]) writes the table back byte for byte", (B.rows_for([], out=es_copy), read(es_copy) == before),
          ([], True))
    check("rows_for the new place", B.rows_for([NEW], out=es_copy), [(NEW, "written")])
    with io.open(es_copy, encoding="utf-8") as fh:
        es = json.load(fh)
    cells, summary, _odd = B.row(NEW, world.static_path(NEW))
    check("  ..its row is its outzones, the door a of the copy",
          (es["locations"][str(NEW)], es["summary"][str(NEW)]["sides"], es["summary"][str(NEW)]["title"]),
          (cells, ["a"], "Проверочная"))
    check("  ..as travel reads them off the file itself (the server's own table has no row for it)",
          travel.exit_sides(world.location(NEW)), {int(c): s for c, s in cells.items()})
    after = set(read(es_copy).decode("utf-8").split("\n"))
    removed = [ln for ln in before.decode("utf-8").split("\n") if ln not in after]
    check("  ..every line of the table is still there, but the row before it, which gains its comma",
          [(ln + ",") in after for ln in removed], [True])
    keep = {k: v for k, v in es["locations"].items() if k != str(NEW)}
    with io.open(os.path.join(ROOT, "data", "exits_sides.json"), encoding="utf-8") as fh:
        check("  ..every other row as it was", keep == {k: v for k, v in json.load(fh)["locations"].items()
                                                         if k != str(NEW)}, True)
    os.unlink(os.path.join(OV, "static", "%d.xml" % NEW))
    check("a place whose file is gone loses its rows", B.rows_for([NEW], out=es_copy), [(NEW, "dropped")])
    check("  ..and the table is the one it started as", read(es_copy) == before, True)
    with open(os.path.join(OV, "static", "%d.xml" % NEW), "wb") as fh:
        fh.write(PLACE)

    # --- xml/loc_defs.xml: the client opens a static file only for an id it lists --------------
    print("xml/loc_defs.xml")
    toy = (b"<?xml version='1.0'?>\n<data>\n"
           b'<file href="locations/deadloc/0.xml" hash="%s" time="1" size="9" />\n'
           b'<file href="locations/static/102.xml" hash="%s" time="7" size="5" />\n'
           b'<file href="locations/static/1020.xml" hash="%s" time="7" size="5" />\n'
           b"</data>") % (b"a" * 32, b"b" * 32, b"c" * 32)
    md5 = lambda b: hashlib.md5(b).hexdigest().encode()  # noqa: E731
    check("a new id gets a row of its own before </data>, the original's rows keep every byte but"
          " the changed one's hash and size",
          world.loc_defs(toy, {NEW: b"new place", 102: b"changed"}),
          (b"<?xml version='1.0'?>\n<data>\n"
           b'<file href="locations/deadloc/0.xml" hash="%s" time="1" size="9" />\n'
           b'<file href="locations/static/102.xml" hash="%s" time="7" size="7" />\n'
           b'<file href="locations/static/1020.xml" hash="%s" time="7" size="5" />\n'
           b'<file href="locations/static/%d.xml" hash="%s" time="%d" size="9" />\n'
           b"</data>") % (b"a" * 32, md5(b"changed"), b"c" * 32, NEW, md5(b"new place"), world.LOC_DEFS_TIME))
    check("  ..and nothing of ours is the list as it was", world.loc_defs(toy, {}), toy)
    real = None
    for res_dir in (world.RES, "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"):
        p = os.path.join(res_dir, "xml", "loc_defs.xml")
        if os.path.isfile(p):
            real = read(p)
            break
    if real is None:
        print("  -- no xml/loc_defs.xml in LAVA_RES: the real list is not checked here (CI's slice has none)")
    else:
        out = world.loc_defs(real, {NEW: PLACE})
        check("the client's own list: one row more, every row it had as it was",
              (out.count(b"<file "), out.replace(b'<file href="locations/static/%d.xml" hash="%s" time="%d" size="%d" />\n'
                                                 % (NEW, md5(PLACE), world.LOC_DEFS_TIME, len(PLACE)), b"")),
              (real.count(b"<file ") + 1, real))
        check("  ..and the hash it gives a file is the one its rows use, the file's md5",
              b'href="locations/static/0.xml" hash="%s"' % md5(read(os.path.join(world.RES, "locations", "static",
                                                                               "0.xml"))) in real
              if os.path.isfile(os.path.join(world.RES, "locations", "static", "0.xml")) else True, True)

    # --- client/build.py: the same bytes into the release ---------------------------------------
    print("client/build.py")
    import build
    tree = os.path.join(W, "tree")
    store = os.path.join(W, "store")
    os.makedirs(os.path.join(tree, "client", "files", "locations", "static"))
    os.makedirs(os.path.join(tree, "data", "locations", "static"))
    with open(os.path.join(tree, "client", "files", "locations", "static", "262.xml"), "wb") as fh:
        fh.write(b"the client's own")
    sha = hashlib.sha256(toy).hexdigest()
    os.makedirs(os.path.join(store, sha[:2]))
    with open(os.path.join(store, sha[:2], sha), "wb") as fh:
        fh.write(toy)

    def gen(names):
        d = os.path.join(tree, "data", "locations", "static")
        for f in os.listdir(d):
            os.unlink(os.path.join(d, f))
        for name, data in names.items():
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(data)
        b = build.Build(tree, store, None, os.path.join(W, "out"))
        b.base = {"xml/loc_defs.xml": (sha, len(toy))}
        try:
            return b.gen_overlay_locations()
        except SystemExit as exc:
            return "refused: %s" % exc

    got = gen({"%d.xml" % NEW: PLACE, "102.xml": CHANGED})
    check("the release gets our files at locations/static/<id>.xml, the bytes the server reads, and the list",
          sorted(got) if isinstance(got, dict) else got,
          sorted(["locations/static/%d.xml" % NEW, "locations/static/102.xml", "xml/loc_defs.xml"]))
    check("  ..the very bytes", (got["locations/static/%d.xml" % NEW] == PLACE,
                                 got["locations/static/102.xml"] == CHANGED), (True, True))
    check("  ..and the list with their rows (world.loc_defs over the original's)",
          got["xml/loc_defs.xml"], world.loc_defs(toy, {NEW: PLACE, 102: CHANGED}))
    check("an id client/files has too is refused: 262 «Тотем» is the client's alone",
          str(gen({"262.xml": b"ours"})).startswith("refused: data/locations/static/262.xml: client/files has"),
          True)
    os.rename(os.path.join(tree, "client", "files", "locations"), os.path.join(tree, "client", "files", "Locations"))
    check("  ..whatever case client/files spells the path in",
          str(gen({"262.xml": b"x"})).count("client/files has"), 1)
    os.rename(os.path.join(tree, "client", "files", "Locations"), os.path.join(tree, "client", "files", "locations"))
    check("a name that is not <id>.xml is refused", str(gen({"0%d.xml" % NEW: PLACE})).startswith("refused"), True)
    check("no files of ours: nothing generated, the list stays the original's", gen({}), {})

    # --- bootstrap_http: a local run serves ours ---------------------------------------------------
    print("bootstrap_http")
    res = os.path.join(W, "res")
    os.makedirs(res)
    for name in os.listdir(world.RES):
        if name != "xml":
            os.symlink(os.path.join(world.RES, name), os.path.join(res, name))
    os.makedirs(os.path.join(res, "xml"))
    with open(os.path.join(res, "xml", "loc_defs.xml"), "wb") as fh:
        fh.write(real or toy)
    port = free_port()
    env = dict(os.environ, LAVA_HTTP_PORT=str(port), LAVA_HTTP_RES="1", LAVA_RES=res, LAVA_LOC_OVERLAY=OV,
               LAVA_DB=os.path.join(W, "http.db"), LAVA_GAME_HOST="127.0.0.1", LAVA_GAME_PORT="9775")
    srv = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _log = []
    threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True).start()

    def get(path):
        end = time.time() + testkit.START_WAIT
        while True:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d%s" % (port, path), timeout=5) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, b""
            except urllib.error.URLError:
                if time.time() > end or srv.poll() is not None:
                    raise SystemExit("bootstrap_http did not start:\n" + "".join(_log[-20:]))
                time.sleep(0.1)

    check("a local run serves the new place from data/locations", get("/res/locations/static/%d.xml" % NEW),
          (200, PLACE))
    check("  ..ours for an original we changed", get("/res/locations/static/102.xml"), (200, CHANGED))
    check("  ..and the original's file for the rest", get("/res/locations/static/5.xml"),
          (200, read(os.path.join(world.RES, "locations", "static", "5.xml"))))
    check("  ..an id nobody has is not found", get("/res/locations/static/%d.xml" % (NEW + 977))[0], 404)
    check("the list it serves has their rows", get("/res/xml/loc_defs.xml"),
          (200, world.loc_defs(real or toy, {NEW: PLACE, 102: CHANGED})))
except Exception:
    import traceback
    fails.append("crashed:\n" + traceback.format_exc())
finally:
    if srv is not None:
        srv.terminate()
        try:
            srv.wait(10)
        except subprocess.TimeoutExpired:
            srv.kill()
    world.OVERLAY = REPO_OVERLAY
    shutil.rmtree(W, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("location overrides OK")
