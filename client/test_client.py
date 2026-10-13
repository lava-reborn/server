"""Client releases: signatures, the release builder and the publisher.

Runs on a toy client in a temporary directory with stand-ins for the four
generators (tools/widescreen.py, tools/export_texts.py, server/map_labels.py,
server/map_cells.py),
so it needs no game files and no network: what is tested is the layering,
the checks and the signed documents, not the patches -- those have their own
suites. The launcher reads the same documents in C#; launcher/test checks it
against vectors this suite's code writes.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import build  # noqa: E402
import lavasig  # noqa: E402
import publish  # noqa: E402
from testkit import check, fails  # noqa: E402

MECHANIC = "client releases: signing, building, publishing"

W = tempfile.mkdtemp(prefix="test-client-")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8", "newline": "\n"})) as fh:
        fh.write(data)


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def tiny_png(w, h, rgba):
    """An RGBA PNG of straight pixels, every row unfiltered."""
    def chunk(typ, body):
        return struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def quiet(fn, *args):
    """fn(*args) with its prints swallowed; (return value or exit code, output)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            rc = fn(*args)
        except SystemExit as e:
            rc = e.code if e.code is not None else 0
            if isinstance(rc, str):
                # SystemExit("why") prints why and exits 1; caught, it only
                # carries the text.
                out.write(rc + "\n")
                rc = 1
    return rc, out.getvalue()


try:
    # --- lavasig: keys and signed documents ------------------------------------------
    key = lavasig.generate(2048)
    other = lavasig.generate(2048)
    keys = lavasig.parse_keys(key.keys_line() + "\n")
    body = b"lava-pointer 1\nserial 7\n"
    doc = lavasig.sign_doc(key, body)
    check("a signed document verifies and gives its body back", lavasig.verify_doc(keys, doc), body)
    check("the sig line names the key", doc.split(b"\n")[-2].split(b" ")[1].decode(), key.id)

    def refused(fn, *args):
        try:
            fn(*args)
        except ValueError:
            return True
        return False

    check("a changed body is refused", refused(lavasig.verify_doc, keys, doc.replace(b"serial 7", b"serial 8")), True)
    check("another key is refused", refused(lavasig.verify_doc, lavasig.parse_keys(other.keys_line()), doc), True)
    check("anything after the sig line is refused", refused(lavasig.verify_doc, keys, doc + b"extra\n"), True)
    check("a document with no sig line is refused", refused(lavasig.verify_doc, keys, body), True)
    check("a body without its last newline is not signed", refused(lavasig.sign_doc, key, b"x"), True)
    k2 = lavasig.load_private(lavasig.pem_private(key))
    check("PKCS#1 PEM reads back to the same key", (k2.n, k2.d), (key.n, key.d))
    bad_line = "%s %d %x" % ("0" * 16, key.e, key.n)
    check("a .keys line whose id is not its modulus is refused", refused(lavasig.parse_keys, bad_line), True)
    check("a signature is deterministic", lavasig.sign_doc(key, body), doc)

    # --- paths: the rules FORMAT.md gives, the same in build.py and publish.py -------------
    for p, ok in (("locations/libs/Abu Hamad.swf", True), ("a/../b", False), ("/abs", False),
                  ("a\\b", False), ("a/b:c", False), ("a/b*c", False), ('a/"q"', False),
                  ("mobs/con.swf", False), ("NUL", False), ("lpt1.txt", False), ("console.swf", True),
                  ("a./b", False), ("a /b", False), (".LAVA/x", False), ("a//b", False)):
        check("path %r: build says %s" % (p, ok), build.check_path(p) is None, ok)
        check("path %r: publish says %s" % (p, ok), publish.check_path(p), ok)

    # --- build: the base list -------------------------------------------------------------
    res = os.path.join(W, "res")
    originals = {
        "main.swf": b"CWS\x09original main",
        "database/locations.xml": b"<locations/>",
        "database/texts.xml": b"<old texts>",
        "locations/static/a b.swf": b"a file with a space",
        "junk/teaser.swf": b"not for players",
        "Mobs/Big.swf": b"m" * 5000,
        "mobs/copy.swf": b"m" * 5000,
        "globalmap/full/1.jpg": b"a tile with a square",
        "globalmap/full/2.jpg": b"a tile with nothing to paint over",
        "locations/libs/sprite/C_Old.swf": b"an original sprite whose name an object of ours wants",
        "xml/loc_defs.xml": (b"<?xml version='1.0'?>\n<data>\n<file href=\"locations/static/0.xml\" "
                             b"hash=\"00000000000000000000000000000000\" time=\"1\" size=\"3\" />\n</data>"),
        "database/objects.xml": (b"<?xml version='1.0'?>\n<data>\n"
                                 b"<object type_id=\"7\" root_type_id= \"0\" name=\"gun\" />\n"
                                 b"<object type_id=\"11721\" root_type_id= \"1\" name=\"helm_Bs_U_LVL_12_Q_mod00\" />\n"
                                 b"</data>"),
        "classes/WearItem/helm_Bs_U_LVL_12_Q_mod00/ico.swf": b"CWS\x09the quest helmet's picture",
        "classes/WearItem/helm_Taken_mod00/ico.swf": b"CWS\x09a folder no row names",
    }
    for p, data in originals.items():
        write(os.path.join(res, *p.split("/")), data)

    tree = os.path.join(W, "tree")
    cdir = os.path.join(tree, "client")
    os.makedirs(cdir)
    base_txt = os.path.join(cdir, "base.txt")
    rc, out = quiet(build.main, ["base", "--dir", res, "--exclude", "database/texts.xml", "-o", base_txt])
    check("base: written", rc, 0)
    base = build.read_entries(base_txt, "lava-base 1")
    check("base: every original but the excluded one", sorted(base),
          sorted(p for p in originals if p != "database/texts.xml"))
    check("base: hash and size of a file", base["main.swf"], (sha(originals["main.swf"]), len(originals["main.swf"])))

    # --- publish: the original into the store ------------------------------------------------
    sroot = os.path.join(W, "served")
    state = os.path.join(W, "state")
    rc, out = quiet(publish.main, ["import-base", "--state", state, "--root", sroot, "--base", base_txt, "--dir", res])
    check("import-base: all stored", rc, 0)
    check("import-base: one blob for two identical files",
          sum(len(f) for _, _, f in os.walk(os.path.join(sroot, "store"))), len(set(sha(v) for p, v in originals.items() if p != "database/texts.xml")))
    rc, out = quiet(publish.main, ["import-base", "--state", state, "--root", sroot, "--base", base_txt, "--dir", res])
    check("import-base: a second run finds everything there", "0 stored" in out and rc == 0, True)

    big = os.path.join(W, "music.swf")
    write(big, b"big asset of ours" * 100)
    rc, out = quiet(publish.main, ["add", "--state", state, "--root", sroot, big])
    check("add: the file is stored and its line printed", sha(read(big)) in out and rc == 0, True)

    # --- build: a release ---------------------------------------------------------------------
    # Stand-ins for the generators, with the real ones' command lines.
    write(os.path.join(tree, "tools", "widescreen.py"),
          "import sys\nd = open(sys.argv[1], 'rb').read()\nopen(sys.argv[2], 'wb').write(d + b'+wide')\n")
    write(os.path.join(tree, "tools", "export_texts.py"),
          "import os, sys\nassert os.environ['LAVA_RES']\nopen(sys.argv[2], 'wb').write(b'\\xef\\xbb\\xbf<data>texts</data>')\n")
    write(os.path.join(tree, "server", "map_labels.py"),
          "def apply(raw, edits=None):\n    return raw + b'<!--labels-->', 1\n")
    # map_cells.apply(read): the tiles that changed and its report; it asks for
    # the tiles a cut can touch, and one of them this client has not.
    write(os.path.join(tree, "server", "map_cells.py"),
          "def apply(read, plan=None):\n"
          "    asked = [p for p in ('globalmap/full/1.jpg', 'globalmap/full/3.jpg') if read(p) is not None]\n"
          "    out = {p: read(p) + b'+painted' for p in asked}\n"
          "    return out, ['1,1: green square at +0,+0, 81 pixels', '  81 pixels painted',\n"
          "                 '9,9: no tile globalmap/full/3.jpg in this client, left alone']\n")
    write(os.path.join(cdir, "remove.txt"), "# not for players\njunk/teaser.swf\n")
    write(os.path.join(cdir, "extra.txt"),
          "lava-extra 1\n%s\t%d\tsounds/music.swf\n" % (sha(read(big)), len(read(big))))
    write(os.path.join(cdir, "files", "xmldocs", "ours.xml"), b"<ours/>")

    def release(out_dir):
        b = build.Build(tree, os.path.join(sroot, "store"), res, out_dir)
        return quiet(b.run)

    out1 = os.path.join(W, "out1")
    rc, out = release(out1)
    check("release: built", rc, None)
    lines = read(os.path.join(out1, "files.tsv")).decode().splitlines()
    got = {l.split("\t")[2]: l.split("\t")[0] for l in lines}
    check("release: the paths, sorted by bytes", [l.split("\t")[2] for l in lines], sorted(got, key=lambda s: s.encode()))
    check("release: main.swf is the patched original", got.get("main.swf"), sha(originals["main.swf"] + b"+wide"))
    check("release: locations.xml carries the map labels", got.get("database/locations.xml"),
          sha(originals["database/locations.xml"] + b"<!--labels-->"))
    check("release: texts.xml is the generated table", got.get("database/texts.xml"),
          sha(b"\xef\xbb\xbf<data>texts</data>"))
    check("release: hints.xml is there", got.get("hints/hints.xml"), sha(build.HINTS))
    check("release: remove.txt took the teaser out", "junk/teaser.swf" in got, False)
    check("release: extra.txt brought the stored asset", got.get("sounds/music.swf"), sha(read(big)))
    check("release: client/files brought ours", got.get("xmldocs/ours.xml"), sha(b"<ours/>"))
    check("release: the map tile with a square is the painted original",
          got.get("globalmap/full/1.jpg"), sha(originals["globalmap/full/1.jpg"] + b"+painted"))
    check("  ..and the generated bytes are in blobs/",
          os.path.exists(os.path.join(out1, "blobs", got["globalmap/full/1.jpg"])), True)
    check("  ..a tile map_cells did not change is the original's",
          got.get("globalmap/full/2.jpg"), sha(originals["globalmap/full/2.jpg"]))
    check("  ..a tile this client has not is not invented", "globalmap/full/3.jpg" in got, False)
    report1 = read(os.path.join(out1, "report.txt")).decode()
    check("  ..the report names the tile and counts what was painted over, and what was not",
          ("generated: %s globalmap/full/1.jpg" % got["globalmap/full/1.jpg"][:16] in report1,
           "map:       1 squares and 0 caption boxes painted over in 1 tiles; "
           "9,9: no tile globalmap/full/3.jpg in this client, left alone" in report1),
          (True, True))
    check("release: generated bytes are in blobs/",
          os.path.exists(os.path.join(out1, "blobs", got["main.swf"])), True)
    out1b = os.path.join(W, "out1b")
    release(out1b)
    check("release: the same tree builds the same list", read(os.path.join(out1b, "files.tsv")),
          read(os.path.join(out1, "files.tsv")))

    def fails_with(text, out_dir):
        rc, out = release(out_dir)
        return rc not in (None, 0) and text in out

    write(os.path.join(cdir, "files", "main.swf"), b"hand made")
    check("release: a file both generated and in client/files is refused",
          fails_with("also generated", os.path.join(W, "o2")), True)
    os.unlink(os.path.join(cdir, "files", "main.swf"))
    write(os.path.join(cdir, "files", "globalmap", "full", "1.jpg"), b"painted by hand")
    check("release: a map tile both painted over and in client/files is refused",
          fails_with("also generated", os.path.join(W, "o2b")), True)
    shutil.rmtree(os.path.join(cdir, "files", "globalmap"))
    write(os.path.join(cdir, "files", "mobs", "big.swf"), b"lower case")
    check("release: two paths differing only in case are refused",
          fails_with("differ only in case", os.path.join(W, "o3")), True)
    os.unlink(os.path.join(cdir, "files", "mobs", "big.swf"))
    blob = publish.blob_path(sroot, base["database/locations.xml"][0])
    good = read(blob)
    write(blob, b"rotten")
    check("release: a store copy that does not match base.txt stops the build",
          fails_with("does not match", os.path.join(W, "o4")), True)
    write(blob, good)

    # --- build: the owner's own location objects (client/objects/) ------------------------------------
    # The real writer (tools/swfgen.py, tools/custom_objects.py; their own
    # suite is tools/test_swfgen.py), in the toy tree where the gate's tree
    # has it.
    for name in ("swfgen.py", "custom_objects.py"):
        shutil.copy(os.path.join(ROOT, "tools", name), os.path.join(tree, "tools", name))
    check("objects: a release without client/objects has none",
          "objects:   0 from client/objects/" in read(os.path.join(out1, "report.txt")).decode(), True)
    odir = os.path.join(cdir, "objects")
    write(os.path.join(odir, "manifest.json"), json.dumps({"c_flag": {
        "title": "Флажок", "frames": ["0.png", "1.png"], "fps": 5, "anchor": [1, 2],
        "footprint": [[0, 0]]}}, ensure_ascii=False))
    write(os.path.join(odir, "c_flag", "0.png"), tiny_png(2, 3, bytes(range(24))))
    write(os.path.join(odir, "c_flag", "1.png"), tiny_png(2, 3, bytes(range(100, 124))))
    out5 = os.path.join(W, "out5")
    rc, out = release(out5)
    check("objects: built", rc, None)
    got5 = {l.split("\t")[2]: l.split("\t")[0] for l in read(os.path.join(out5, "files.tsv")).decode().splitlines()}
    import custom_objects  # noqa: E402  (the copy build.py just loaded from the toy tree)
    want5, _ = custom_objects.build(odir)
    swf = want5["locations/libs/sprite/c_flag.swf"]
    check("objects: the sprite file is in the release, the writer's bytes",
          got5.get("locations/libs/sprite/c_flag.swf"), sha(swf))
    check("  ..its bytes are in blobs/", read(os.path.join(out5, "blobs", sha(swf))), swf)
    check("  ..it is an animated sprite file (SWF 9, ten frames: two pictures at 5 fps)",
          (swf[:4], struct.unpack("<H", zlib.decompress(swf[8:])[11:13])[0]), (b"CWS\x09", 10))
    report5 = read(os.path.join(out5, "report.txt")).decode()
    check("  ..the report names it and counts it",
          ("object:    %s locations/libs/sprite/c_flag.swf (2x3, 2 pictures at 5 fps," % sha(swf)[:16] in report5,
           "objects:   1 from client/objects/" in report5), (True, True))
    check("objects: nothing else in the release changed",
          {p: s for p, s in got5.items() if p != "locations/libs/sprite/c_flag.swf"}, got)
    check("objects: the same tree builds the same list", (release(os.path.join(W, "out5b"))[0],
          read(os.path.join(W, "out5b", "files.tsv"))), (None, read(os.path.join(out5, "files.tsv"))))
    write(os.path.join(cdir, "files", "locations", "libs", "sprite", "c_flag.swf"), b"by hand")
    check("objects: an object's file also in client/files is refused",
          fails_with("also generated", os.path.join(W, "o5")), True)
    shutil.rmtree(os.path.join(cdir, "files", "locations"))
    os.rename(os.path.join(odir, "c_flag"), os.path.join(odir, "c_old"))
    write(os.path.join(odir, "manifest.json"), read(os.path.join(odir, "manifest.json")).replace(b"c_flag", b"c_old"))
    check("objects: an id whose file the original has, in another case, is refused",
          fails_with("the game already has locations/libs/sprite/C_Old.swf", os.path.join(W, "o6")), True)
    write(os.path.join(odir, "manifest.json"), b'{"c_old": {"title": "x"}}')
    check("objects: a broken manifest stops the build, naming client/objects",
          fails_with("client/objects: c_old: frames", os.path.join(W, "o7")), True)
    shutil.rmtree(odir)

    # The locations of ours (data/locations/static/<id>.xml, server/world.py):
    # the release ships the bytes the server reads, and the client's list of
    # location files with a row for each -- without one it draws a desert.
    check("release: no location of ours, the list of location files is the original's",
          got.get("xml/loc_defs.xml"), sha(originals["xml/loc_defs.xml"]))
    place = b'<location title="ours" width="32" height="64"><mobs></mobs></location>'
    write(os.path.join(tree, "data", "locations", "static", "1381.xml"), place)
    out6 = os.path.join(W, "out6")
    rc, out = release(out6)
    got6 = {l.split("\t")[2]: l.split("\t")[0] for l in read(os.path.join(out6, "files.tsv")).decode().splitlines()}
    check("release: a location of ours is in it, at locations/static/<id>.xml, byte for byte",
          (rc, got6.get("locations/static/1381.xml")), (None, sha(place)))
    check("  ..and the list of location files has its row, the original's rows as they were",
          read(os.path.join(out6, "blobs", got6["xml/loc_defs.xml"])),
          originals["xml/loc_defs.xml"].replace(
              b"</data>", b'<file href="locations/static/1381.xml" hash="%s" time="1616508972" size="%d" />\n</data>'
              % (hashlib.md5(place).hexdigest().encode(), len(place))))
    check("  ..and the report says so", "locations: 1 of ours (data/locations)" in read(
        os.path.join(out6, "report.txt")).decode(), True)
    write(os.path.join(cdir, "files", "locations", "static", "1381.xml"), place)
    check("release: an id that client/files has too is refused (the client's alone, like 262)",
          fails_with("client/files has locations/static/1381.xml", os.path.join(W, "o8")), True)
    shutil.rmtree(os.path.join(cdir, "files", "locations"))
    # Both steps in one release: a location of ours that stands an object of
    # ours on a cell (custom_objects.place), its sprite file beside it.
    write(os.path.join(odir, "manifest.json"), json.dumps({"c_flag": {
        "title": "Флажок", "frames": ["0.png"], "anchor": [1, 2], "footprint": [[0, 0]]}}, ensure_ascii=False))
    write(os.path.join(odir, "c_flag", "0.png"), tiny_png(2, 3, bytes(range(24))))
    put = custom_objects.place("c_flag", custom_objects.load(odir)["c_flag"], 5, 7)
    with_obj = place.replace(b"<mobs>", put["sprite"].encode() + b"<obstacles>" + put["obstacles"].encode()
                             + b"</obstacles><mobs>")
    write(os.path.join(tree, "data", "locations", "static", "1381.xml"), with_obj)
    out7 = os.path.join(W, "out7")
    rc, out = release(out7)
    got7 = {l.split("\t")[2]: l.split("\t")[0] for l in read(os.path.join(out7, "files.tsv")).decode().splitlines()}
    report7 = read(os.path.join(out7, "report.txt")).decode()
    check("release: a location of ours with an object of ours: both files, and both steps report",
          (rc, got7.get("locations/static/1381.xml"), "locations/libs/sprite/c_flag.swf" in got7,
           "objects:   1 from client/objects/" in report7, "locations: 1 of ours (data/locations)" in report7),
          (None, sha(with_obj), True, True, True))
    shutil.rmtree(odir)
    shutil.rmtree(os.path.join(tree, "data"))

    # Item types of our own (data/own_items.json, server/own_items.py, the
    # real one in the toy tree): the client draws a type by its row of
    # objects.xml, classes/<folder>/<name>/ico.swf (SSEmulator.getIcon), so
    # the release adds a row for each and a byte copy of the picture of the
    # original type it is like. Чёрный Ловелас's gold helmet is the model.
    shutil.copy(os.path.join(ROOT, "server", "own_items.py"), os.path.join(tree, "server", "own_items.py"))
    check("own items: none, objects.xml is the original's and the report counts none",
          (got.get("database/objects.xml"),
           "own items: 0 types (data/own_items.json)" in read(os.path.join(out1, "report.txt")).decode()),
          (sha(originals["database/objects.xml"]), True))
    own_json = os.path.join(tree, "data", "own_items.json")

    def own(items_):
        write(own_json, json.dumps({"_meta": {"what": "x"}, "items": items_}))

    gold_helm = {"60000": {"name": "helm_Bs_U_LVL_12_G_mod00", "like": 11721}}
    own(gold_helm)
    out9 = os.path.join(W, "out9")
    rc, out = release(out9)
    got9 = {l.split("\t")[2]: l.split("\t")[0] for l in read(os.path.join(out9, "files.tsv")).decode().splitlines()}
    icon = "classes/WearItem/helm_Bs_U_LVL_12_G_mod00/ico.swf"
    rows9 = originals["database/objects.xml"].replace(
        b"</data>", b'<object type_id="60000" root_type_id= "1" name="helm_Bs_U_LVL_12_G_mod00" />\n</data>')
    check("own items: built; objects.xml is the original with our row before its end, in its"
          " own format", (rc, read(os.path.join(out9, "blobs", got9["database/objects.xml"]))), (None, rows9))
    check("  ..which the server's reader reads as the type, its root and its name",
          [(int(m.group(1)), int(m.group(2)), m.group(3)) for m in build.OBJECT_ROW.finditer(rows9)][-1],
          (60000, 1, b"helm_Bs_U_LVL_12_G_mod00"))
    check("  ..and the type's icon is the picture of the type it is like, byte for byte",
          read(os.path.join(out9, "blobs", got9[icon])),
          originals["classes/WearItem/helm_Bs_U_LVL_12_Q_mod00/ico.swf"])
    check("  ..nothing else in the release changed",
          {p: s for p, s in got9.items() if p not in (icon, "database/objects.xml")},
          {p: s for p, s in got.items() if p != "database/objects.xml"})
    report9 = read(os.path.join(out9, "report.txt")).decode()
    check("  ..the report names the type, the picture it copies and the count",
          ("own item:  60000 helm_Bs_U_LVL_12_G_mod00, the picture of 11721 helm_Bs_U_LVL_12_Q_mod00"
           in report9, "own items: 1 types (data/own_items.json)" in report9,
           "an icon of our own item type, new" in report9), (True, True, True))
    check("  ..the same tree builds the same list",
          (release(os.path.join(W, "out9b"))[0], read(os.path.join(W, "out9b", "files.tsv"))),
          (None, read(os.path.join(out9, "files.tsv"))))
    write(os.path.join(cdir, "files", *icon.split("/")), b"by hand")
    check("own items: an icon also in client/files is refused",
          fails_with("also generated", os.path.join(W, "o9")), True)
    shutil.rmtree(os.path.join(cdir, "files", "classes"))
    for why, items_, text in (
            ("a name whose icon folder the original has, in another case",
             {"60000": {"name": "HELM_Taken_mod00", "like": 11721}}, "is a file of the original"),
            ("a like that is no type of the original",
             {"60000": {"name": "helm_x_G_mod00", "like": 4242}}, "like 4242 is no type of the original"),
            ("a type id of the original's range",
             {"11722": {"name": "helm_x_G_mod00", "like": 11721}}, "a type of ours is 50036..65535"),
            ("a name of the original's",
             {"60000": {"name": "gun", "like": 11721}}, "the original's 7 is named gun")):
        own(items_)
        check("own items: %s is refused, naming data/own_items.json" % why,
              fails_with("data/own_items.json: ", os.path.join(W, "o10")) and fails_with(text, os.path.join(W, "o10")),
              True)
    shutil.rmtree(os.path.join(tree, "data"))

    # --- publish: check and publish ---------------------------------------------------------------
    keyfile = os.path.join(W, "resource.pem")
    write(keyfile, lavasig.pem_private(key))
    rc, out = quiet(publish.main, ["check", "--out", out1, "--root", sroot])
    check("check: a good build passes", rc, 0)

    def bad_build(name, mutate):
        d = os.path.join(W, name)
        shutil.copytree(out1, d)
        mutate(d)
        rc, out = quiet(publish.main, ["check", "--out", d, "--root", sroot])
        return rc

    def unsort(d):
        p = os.path.join(d, "files.tsv")
        ls = read(p).decode().splitlines()
        write(p, "\n".join(reversed(ls)) + "\n")

    def dotdot(d):
        p = os.path.join(d, "files.tsv")
        write(p, read(p).decode().replace("\txmldocs/ours.xml", "\txmldocs/../../ours.xml"))

    def rot(d):
        write(os.path.join(d, "blobs", got["main.swf"]), b"swapped on the way")

    def lose(d):
        os.unlink(os.path.join(d, "blobs", got["xmldocs/ours.xml"]))

    def list_link(d):
        p = os.path.join(d, "files.tsv")
        os.rename(p, p + ".real")
        os.symlink(p + ".real", p)

    def blob_link(d):
        b = os.path.join(d, "blobs", got["xmldocs/ours.xml"])
        os.rename(b, b + ".real")
        os.symlink(b + ".real", b)

    def file_and_folder(d):
        p = os.path.join(d, "files.tsv")
        ls = read(p).decode().splitlines()
        ls.append("%s\t%d\tzz/main.swf/x" % (got["main.swf"], len(read(os.path.join(d, "blobs", got["main.swf"])))))
        ls.append("%s\t%d\tzz/main.swf" % (got["main.swf"], len(read(os.path.join(d, "blobs", got["main.swf"])))))
        write(p, "\n".join(sorted(ls)) + "\n")

    check("check: unsorted lines are refused", bad_build("b1", unsort), 2)
    check("check: a '..' path is refused", bad_build("b2", dotdot), 2)
    check("check: a blob that is not what the list says is refused", bad_build("b3", rot), 2)
    check("check: a file in neither store nor build is refused", bad_build("b4", lose), 2)
    check("check: files.tsv as a link is refused", bad_build("b5", list_link), 2)
    check("check: a blob as a link is refused", bad_build("b6", blob_link), 2)
    check("check: a file that is also a folder is refused", bad_build("b7", file_and_folder), 2)
    check("tree: a file that is also a folder, in another case", build.check_tree(["a/b", "A"]) is not None, True)
    check("tree: a file that is also a folder of another", build.check_tree(["a", "A/b"]) is not None, True)
    check("tree: a folder and a file beside it", build.check_tree(["a/b", "ab", "a.b"]), None)

    rc, out = quiet(publish.main, ["publish", "--state", state, "--out", out1, "--root", sroot, "--key", keyfile,
                                   "--source", "a" * 40, "--keep", "2"])
    check("publish: done", rc, 0)
    cur = read(os.path.join(sroot, "current.txt"))
    pbody = lavasig.verify_doc(keys, cur).decode()
    p1 = publish.read_pointer(state)
    check("publish: the pointer is signed and names the manifest", pbody.startswith("lava-pointer 1\nserial %d\n" % p1["serial"]), True)
    mdata = read(os.path.join(sroot, p1["manifest"][2]))
    check("publish: the pointer carries the manifest's hash", p1["manifest"][0], sha(mdata))
    check("publish: the manifest lists the build", mdata.decode().split("\n", 4)[4], read(os.path.join(out1, "files.tsv")).decode())
    check("publish: generated blobs are in the store",
          os.path.exists(publish.blob_path(sroot, got["main.swf"])), True)
    check("publish: no launcher line before a launcher is published", p1["launcher"], None)

    rc, out = quiet(publish.main, ["publish", "--state", state, "--out", out1, "--root", sroot, "--key", keyfile, "--source", "b" * 40])
    p2 = publish.read_pointer(state)
    check("publish: the serial grows even within one second", p2["serial"] > p1["serial"], True)

    # --- publish: the launcher ---------------------------------------------------------------------
    lkey = lavasig.generate(2048)
    lkeys = os.path.join(W, "launcher.keys")
    write(lkeys, "# test\n" + lkey.keys_line() + "\n")
    exe = os.path.join(W, "LavaReborn.exe")
    write(exe, b"MZ launcher 3")

    def statement(version, data, signer):
        st = os.path.join(W, "st%d.txt" % version)
        b = "lava-launcher 1\nversion %d\nsha256 %s\nsize %d\ncreated 2026-10-06T00:00:00Z\n" % (
            version, sha(data), len(data))
        write(st, lavasig.sign_doc(signer, b.encode()))
        return st

    dl = os.path.join(W, "download")
    os.makedirs(dl)
    write(os.path.join(dl, "LavaReborn.exe"), b"MZ the old launcher")

    def publish_launcher(st, *extra):
        return quiet(publish.main, ["launcher", "--state", state, "--root", sroot, "--key", keyfile, "--launcher-keys", lkeys,
                                    "--exe", exe, "--statement", st, "--download", dl] + list(extra))[0]

    check("launcher: a statement signed by another key is refused",
          publish_launcher(statement(3, read(exe), other)), 2)
    check("launcher: published", publish_launcher(statement(3, read(exe), lkey)), 0)
    p3 = publish.read_pointer(state)
    check("launcher: the pointer names it", p3["launcher"], (3, sha(read(exe)), len(read(exe)), "launcher/3.exe"))
    check("launcher: the pointer keeps the release", p3["manifest"], p2["manifest"])
    check("launcher: the site's download is the new exe", read(os.path.join(dl, "LavaReborn.exe")), read(exe))
    check("launcher: the old exe is kept as .prev", read(os.path.join(dl, "LavaReborn.exe.prev")), b"MZ the old launcher")
    check("launcher: the same version again is refused", publish_launcher(statement(3, read(exe), lkey)), 2)
    check("launcher: an exe the statement does not describe is refused",
          publish_launcher(statement(4, b"MZ something else", lkey)), 2)

    # --- publish: what the web root holds is never a source of truth -------------------------------
    # Whoever can write the served folder edits its pointer and drops a
    # manifest of their own: the next launcher publish still re-signs the
    # release STATE says was published.
    evil_m = b"lava-manifest 1\nserial 1\nsource x\nfiles 1 1\n" + ("%s\t1\tmain.swf\n" % ("0" * 64)).encode()
    write(os.path.join(sroot, "manifests", "1.txt"), evil_m)
    served = read(os.path.join(sroot, "current.txt"))
    write(os.path.join(sroot, "current.txt"), served.replace(
        p3["manifest"][0].encode(), sha(evil_m).encode()).replace(p3["manifest"][2].encode(), b"manifests/1.txt"))
    write(exe, b"MZ launcher 5")
    check("web root tampered: a launcher publish goes on", publish_launcher(statement(5, read(exe), lkey)), 0)
    p3b = publish.read_pointer(state)
    check("web root tampered: the release signed is the one STATE kept", p3b["manifest"], p3["manifest"])
    check("web root tampered: the served pointer is ours again",
          lavasig.verify_doc(keys, read(os.path.join(sroot, "current.txt"))).decode().count(p3["manifest"][0]), 1)
    os.unlink(os.path.join(sroot, "manifests", "1.txt"))
    p3 = p3b

    # Whoever can write the site's folder leaves a link where .prev goes: the
    # previous exe replaces the link, the file it pointed to stays as it was.
    outside = os.path.join(W, "outside.txt")
    write(outside, b"not the publisher's")
    os.unlink(os.path.join(dl, "LavaReborn.exe.prev"))
    os.symlink(outside, os.path.join(dl, "LavaReborn.exe.prev"))
    write(exe, b"MZ launcher 6")
    check("download: a link at .prev -> the launcher still goes out", publish_launcher(statement(6, read(exe), lkey)), 0)
    check("download: the file the link named is untouched", read(outside), b"not the publisher's")
    check("download: .prev is a plain file now", os.path.islink(os.path.join(dl, "LavaReborn.exe.prev")), False)
    check("download: and holds the exe before", read(os.path.join(dl, "LavaReborn.exe.prev")), b"MZ launcher 5")
    check("download: the link is the new exe", read(os.path.join(dl, "LavaReborn.exe")), b"MZ launcher 6")
    p3 = publish.read_pointer(state)
    check("launcher-version: what the gate counts on from",
          quiet(publish.main, ["launcher-version", "--state", state])[1].strip(), "6")
    check("launcher-version: 0 before any launcher",
          quiet(publish.main, ["launcher-version", "--state", os.path.join(W, "no-state")])[1].strip(), "0")

    # A served folder replaced by a link is not written into.
    mdir = os.path.join(sroot, "manifests")
    os.rename(mdir, mdir + ".real")
    os.symlink(mdir + ".real", mdir)
    rc, out = quiet(publish.main, ["publish", "--state", state, "--out", out1, "--root", sroot, "--key", keyfile,
                                   "--source", "e" * 40])
    check("a served folder that is a link: refused", rc, 2)
    check("a served folder that is a link: the pointer did not move", publish.read_pointer(state)["serial"], p3["serial"])
    os.unlink(mdir)
    os.rename(mdir + ".real", mdir)

    rc, out = quiet(publish.main, ["publish", "--state", state, "--out", out1, "--root", sroot, "--key", keyfile, "--source", "c" * 40,
                                   "--keep", "2"])
    p4 = publish.read_pointer(state)
    check("publish: a release keeps the launcher line", p4["launcher"], p3["launcher"])
    check("publish: --keep 2 leaves two manifests", len(publish.manifests(state)), 2)

    # --- publish: rollback, status, gc ---------------------------------------------------------------
    write(os.path.join(cdir, "files", "xmldocs", "ours.xml"), b"<ours v2/>")
    out2 = os.path.join(W, "out2")
    release(out2)
    quiet(publish.main, ["publish", "--state", state, "--out", out2, "--root", sroot, "--key", keyfile, "--source", "d" * 40, "--keep", "3"])
    p5 = publish.read_pointer(state)
    rc, out = quiet(publish.main, ["rollback", "--state", state, "--root", sroot, "--key", keyfile])
    p6 = publish.read_pointer(state)
    check("rollback: done", rc, 0)
    check("rollback: the pointer names the release before", p6["manifest"][2], p4["manifest"][2])
    check("rollback: with a new serial", p6["serial"] > p5["serial"], True)
    check("status: answers", quiet(publish.main, ["status", "--state", state, "--root", sroot])[0], 0)

    stray = publish.store_bytes(sroot, b"nobody lists me")
    rc, out = quiet(publish.main, ["gc", "--state", state, "--root", sroot, "--base", base_txt, "--extra", os.path.join(cdir, "extra.txt")])
    check("gc: an unlisted blob goes", os.path.exists(publish.blob_path(sroot, stray)), False)
    check("gc: the original stays", os.path.exists(publish.blob_path(sroot, base["main.swf"][0])), True)
    check("gc: what a kept release needs stays", os.path.exists(publish.blob_path(sroot, got["main.swf"])), True)

    # --- vectors for the launcher's own test (launcher/test) ---------------------------------------
    vec = os.environ.get("LAVA_CLIENT_VECTORS")
    if vec:
        os.makedirs(vec, exist_ok=True)
        write(os.path.join(vec, "resource.keys"), key.keys_line() + "\n")
        write(os.path.join(vec, "launcher.keys"), lkey.keys_line() + "\n")
        write(os.path.join(vec, "pointer.txt"), cur)
        write(os.path.join(vec, "statement.txt"), read(os.path.join(sroot, "launcher", "3.txt")))
        print("  --  vectors written to %s" % vec)
except Exception:
    import traceback
    fails.append("crashed:\n" + traceback.format_exc())
finally:
    shutil.rmtree(W, ignore_errors=True)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("client OK")
