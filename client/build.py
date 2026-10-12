#!/usr/bin/env python3
"""Build the list of files a client release is made of (client/FORMAT.md).

    python3 client/build.py base --zip LAVA.zip --prefix LAVA/res/ [--exclude PATH ...] -o client/base.txt
    python3 client/build.py base --dir /path/to/res [--exclude PATH ...] -o client/base.txt
    python3 client/build.py release --tree . --store STORE --res RES --out OUT

A release is four layers, later ones over earlier ones:

  1. client/base.txt     the original game, file by file: the hashes of the
                         client as it was shipped. Its bytes live in the
                         server's store, put there once by publish.py
                         import-base; they are never in git.
     client/remove.txt   paths of the original that players do not get.
  2. client/extra.txt    big files of ours that live only in the store
                         (uploaded with publish.py add), listed here by hash.
  3. generated           what the repository computes from the original:
                         main.swf through tools/widescreen.py, the string
                         table through tools/export_texts.py, the global
                         map's names through server/map_labels.py, hints.xml,
                         the map's tiles that lose the squares of retired
                         places through server/map_cells.py, the owner's
                         own location objects, client/objects/ made into
                         sprite files by tools/custom_objects.py, and the
                         locations of ours (data/locations/static, the same
                         bytes the server reads) with their rows in
                         xml/loc_defs.xml.
  4. client/files/**     small files of ours, kept in git as they are.

A path that two layers both claim is fine going down (a generated main.swf
replaces the original one), but a file in client/files/ that is also
generated is an error: one of the two would be silently thrown away.

`release` writes into OUT:

  files.tsv          the manifest's file lines, sorted: sha256 TAB size TAB path
  blobs/<sha256>     the bytes of every generated and in-git file
  report.txt         what each layer contributed, for the deploy report

and touches nothing else. The gate runs it inside the game's own image,
network off, the deployed tree and the store read-only, so what the
repository can do here is compute files and nothing more; publish.py, which
the gate runs as itself, checks what came out before anything is signed.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

HINTS = b"\xef\xbb\xbf<?xml version='1.0'?><data/>"


# --- paths ---------------------------------------------------------------------

# The path rules of FORMAT.md, kept identical in publish.py and in the
# launcher (Release.cs, Manifest.PathOk). A whitelist rather than a list of
# what Windows refuses: with ASCII only, Python and C# cannot disagree about
# case or length, and every name the original game uses fits it.
PART = re.compile(r"[A-Za-z0-9 ._()-]+")
# Device names: "con.swf" is the console, not a file, on Windows.
DEVICE = re.compile(r"(con|prn|aux|nul|com[0-9]|lpt[0-9]|conin\$|conout\$)(\..*)?", re.I)
MAX_PATH_LEN = 150


def check_path(p):
    """A reason the path is refused, or None if it is fine."""
    if not p or len(p) > MAX_PATH_LEN:
        return "empty or longer than %d" % MAX_PATH_LEN
    parts = p.split("/")
    for s in parts:
        if s in ("", ".", ".."):
            return "an empty, '.' or '..' part"
        if not PART.fullmatch(s):
            return "a character outside A-Z a-z 0-9 space . _ ( ) -"
        if s.endswith((".", " ")):
            # Windows trims these off a name, and two paths become one file.
            return "a part ending in a dot or a space"
        if DEVICE.fullmatch(s):
            return "a Windows device name (con, nul, com1...)"
    if parts[0].lower() == ".lava":
        return "under .lava, which is the launcher's own"
    return None


def check_tree(paths):
    """A reason a set of paths cannot be one folder on Windows, or None: two
    that differ only in case, or a file that is also a folder of another."""
    files = {}
    for p in paths:
        other = files.setdefault(p.lower(), p)
        if other != p:
            return "%s and %s differ only in case" % (p, other)
    for p in paths:
        parts = p.lower().split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            if d in files:
                return "%s is a file and also a folder of %s" % (files[d], p)
    return None


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# --- the lists in client/ --------------------------------------------------------

ENTRY = re.compile(r"([0-9a-f]{64})\t([0-9]+)\t(.+)")


def read_entries(path, header):
    """{path: (sha, size)} from a list of sha TAB size TAB path lines under a
    `header` first line; '#' lines are comments. A missing file is empty."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8", newline="\n") as fh:
        lines = fh.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or lines[0] != header:
        raise SystemExit("%s: the first line must be %r" % (path, header))
    seen = {}
    for no, line in enumerate(lines[1:], 2):
        if not line or line.startswith("#"):
            continue
        m = ENTRY.fullmatch(line)
        if not m:
            raise SystemExit("%s:%d: not 'sha256 TAB size TAB path'" % (path, no))
        sha, size, p = m.group(1), int(m.group(2)), m.group(3)
        why = check_path(p)
        if why:
            raise SystemExit("%s:%d: %s: %s" % (path, no, p, why))
        low = p.lower()
        if low in seen:
            raise SystemExit("%s:%d: %s is listed twice (as %s)" % (path, no, p, seen[low]))
        seen[low] = p
        out[p] = (sha, size)
    return out


def read_paths(path):
    """A plain list of paths, one per line, '#' comments."""
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for no, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            why = check_path(line)
            if why:
                raise SystemExit("%s:%d: %s: %s" % (path, no, line, why))
            out.append(line)
    return out


def write_entries(path, header, comment, entries):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n")
        for line in comment:
            fh.write("# " + line + "\n" if line else "#\n")
        for p in sorted(entries, key=lambda s: s.encode("utf-8")):
            sha, size = entries[p]
            fh.write("%s\t%d\t%s\n" % (sha, size, p))


# --- base ------------------------------------------------------------------------

def cmd_base(a):
    entries = {}
    excluded = set(a.exclude or [])
    if a.zip:
        z = zipfile.ZipFile(a.zip)
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(a.prefix):
                continue
            p = unicodedata.normalize("NFC", info.filename[len(a.prefix):])
            if p in excluded:
                continue
            data = z.read(info)
            entries[p] = (sha256(data), len(data))
    else:
        root = os.path.abspath(a.dir)
        for d, _dirs, files in os.walk(root):
            for f in files:
                full = os.path.join(d, f)
                p = unicodedata.normalize("NFC", os.path.relpath(full, root).replace(os.sep, "/"))
                if p in excluded:
                    continue
                with open(full, "rb") as fh:
                    data = fh.read()
                entries[p] = (sha256(data), len(data))
    bad = [(p, check_path(p)) for p in entries if check_path(p)]
    if bad:
        raise SystemExit("paths the format does not allow: %s" % bad[:5])
    why = check_tree(entries)
    if why:
        raise SystemExit(why)
    src = a.zip and ("%s, %s" % (os.path.basename(a.zip), a.prefix)) or os.path.basename(a.dir)
    write_entries(a.out, "lava-base 1", [
        "The original client, file by file: what players get when nothing of",
        "ours replaces it. Written by client/build.py base from " + src + ".",
        "Excluded: " + (", ".join(sorted(excluded)) or "nothing") + ".",
        "Do not edit by hand: the bytes behind these hashes are in the store,",
        "and a line that does not match them stops every release.",
    ], entries)
    total = sum(s for _, s in entries.values())
    print("%s: %d files, %d bytes" % (a.out, len(entries), total))


# --- release ------------------------------------------------------------------------

class Build:
    def __init__(self, tree, store, res, out, base=None):
        self.tree = os.path.abspath(tree)
        self.store = store and os.path.abspath(store)
        self.res = res and os.path.abspath(res)
        self.out = os.path.abspath(out)
        self.cdir = os.path.join(self.tree, "client")
        self.base_path = base or os.path.join(self.cdir, "base.txt")
        self.files = {}          # path -> (sha, size)
        self.origin = {}         # path -> layer name
        self.report = []
        self.tmp = tempfile.mkdtemp(prefix="lava-client-")

    def blob_path(self, sha):
        return os.path.join(self.store, sha[:2], sha)

    def original(self, path):
        """The original bytes of `path`, out of the store, checked."""
        base = self.base.get(path)
        if base is None:
            raise SystemExit("%s is not in client/base.txt; nothing to start from" % path)
        if not self.store:
            raise SystemExit("--store is needed to read the original %s" % path)
        with open(self.blob_path(base[0]), "rb") as fh:
            data = fh.read()
        if sha256(data) != base[0]:
            raise SystemExit("the store's copy of %s does not match client/base.txt" % path)
        return data

    def put(self, path, data, layer):
        sha = sha256(data)
        os.makedirs(os.path.join(self.out, "blobs"), exist_ok=True)
        dest = os.path.join(self.out, "blobs", sha)
        if not os.path.exists(dest):
            with open(dest + ".part", "wb") as fh:
                fh.write(data)
            os.replace(dest + ".part", dest)
        self.files[path] = (sha, len(data))
        self.origin[path] = layer

    def run_py(self, args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        e["PYTHONDONTWRITEBYTECODE"] = "1"
        e["PYTHONUTF8"] = "1"
        r = subprocess.run([sys.executable] + args, cwd=self.tree, env=e,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        text = r.stdout.decode("utf-8", "replace").strip()
        if r.returncode != 0:
            raise SystemExit("%s failed (%d):\n%s" % (" ".join(args[:1]), r.returncode, text[-2000:]))
        return text

    # The generated layer. Each returns the file's bytes.

    def gen_main_swf(self):
        src = os.path.join(self.tmp, "main.in.swf")
        dst = os.path.join(self.tmp, "main.out.swf")
        with open(src, "wb") as fh:
            fh.write(self.original("main.swf"))
        self.run_py([os.path.join("tools", "widescreen.py"), src, dst])
        with open(dst, "rb") as fh:
            return fh.read()

    def gen_texts(self):
        if not self.res:
            raise SystemExit("--res is needed for the string table")
        dst = os.path.join(self.tmp, "texts.xml")
        self.run_py([os.path.join("tools", "export_texts.py"), "-o", dst],
                    env={"LAVA_RES": self.res})
        with open(dst, "rb") as fh:
            return fh.read()

    def gen_locations(self):
        sys.path.insert(0, os.path.join(self.tree, "server"))
        try:
            import map_labels
            body, _changed = map_labels.apply(self.original("database/locations.xml"))
        finally:
            sys.path.pop(0)
        return body

    def gen_hints(self):
        return HINTS

    GENERATED = [
        ("main.swf", "gen_main_swf"),
        ("database/texts.xml", "gen_texts"),
        ("database/locations.xml", "gen_locations"),
        ("hints/hints.xml", "gen_hints"),
    ]

    def gen_map_tiles(self):
        """The global map's tiles with the squares of the places taken out of
        the game painted over (server/map_cells.py): {path: bytes} of the
        tiles that changed, and what was done. Read from the original in the
        store; a tile this client does not have is left alone."""
        def read(path):
            if self.origin.get(path) != "base":
                return None
            return self.original(path)
        sys.path.insert(0, os.path.join(self.tree, "server"))
        try:
            import map_cells
            return map_cells.apply(read)
        finally:
            sys.path.pop(0)

    def gen_custom_objects(self, taken):
        """The owner's own location objects (client/objects/README.md): {path:
        bytes} of their sprite files, locations/libs/sprite/<id>.swf and
        locations/libs/background/<id>.swf, and the report's lines. An
        object whose file would land on one of `taken` (the original's and
        extra.txt's paths), in any case, stops the build. No manifest, no
        objects."""
        objdir = os.path.join(self.cdir, "objects")
        if not os.path.exists(os.path.join(objdir, "manifest.json")):
            return {}, []
        sys.path.insert(0, os.path.join(self.tree, "tools"))
        try:
            import custom_objects
            try:
                return custom_objects.build(objdir, taken)
            except custom_objects.Refused as e:
                raise SystemExit("client/objects: %s" % e)
        finally:
            sys.path.pop(0)

    def gen_overlay_locations(self):
        """The locations of ours (data/locations/static/<id>.xml, the
        location editor's) as locations/static/<id>.xml, the bytes the
        server reads (world.static_path), and xml/loc_defs.xml with a row
        for each (world.loc_defs): the client opens a static file only for
        an id that list names. {path: bytes}; nothing at all while there
        are none, so a tree without the folder builds as it always has.

        An id client/files also has is refused: such a copy is the
        client's alone and the server keeps the original's (262 «Тотем»,
        client/files/README.md), so it cannot be ours as well."""
        src = os.path.join(self.tree, "data", "locations", "static")
        try:
            names = sorted(os.listdir(src))
        except FileNotFoundError:
            return {}
        theirs = set()
        fdir = os.path.join(self.cdir, "files")
        for d, _dirs, fs in os.walk(fdir):
            for f in fs:
                theirs.add(os.path.relpath(os.path.join(d, f), fdir).replace(os.sep, "/").lower())
        files = {}
        for name in names:
            stem = name[:-4]
            if not (name.endswith(".xml") and stem.isdigit() and str(int(stem)) == stem):
                raise SystemExit("data/locations/static/%s: a location of ours is <id>.xml" % name)
            path = "locations/static/%s" % name
            if path.lower() in theirs:
                raise SystemExit("data/locations/static/%s: client/files has %s, the client's alone "
                                 "and never the server's; an id is ours in one place only" % (name, path))
            with open(os.path.join(src, name), "rb") as fh:
                files[int(stem)] = fh.read()
        if not files:
            return {}
        sys.path.insert(0, os.path.join(self.tree, "server"))
        try:
            import world
            defs = world.loc_defs(self.original("xml/loc_defs.xml"), files)
        finally:
            sys.path.pop(0)
        out = {"locations/static/%d.xml" % i: data for i, data in files.items()}
        out["xml/loc_defs.xml"] = defs
        return out

    def run(self):
        os.makedirs(self.out, exist_ok=True)
        self.base = read_entries(self.base_path, "lava-base 1")
        if not self.base:
            raise SystemExit("%s is missing or empty" % self.base_path)

        # 1. the original, less what players do not get
        for p, v in self.base.items():
            self.files[p] = v
            self.origin[p] = "base"
        removed = 0
        for p in read_paths(os.path.join(self.cdir, "remove.txt")):
            if p not in self.files:
                raise SystemExit("client/remove.txt: %s is not in the original" % p)
            del self.files[p]
            removed += 1
        self.report.append("base:      %d files, %d removed by remove.txt" % (len(self.base), removed))

        # 2. ours, in the store only
        extra = read_entries(os.path.join(self.cdir, "extra.txt"), "lava-extra 1")
        for p, v in extra.items():
            self.files[p] = v
            self.origin[p] = "extra"
        self.report.append("extra:     %d files" % len(extra))

        # 3. computed from the original by the repository's own tools
        for p, fn in self.GENERATED:
            data = getattr(self, fn)()
            before = self.files.get(p)
            self.put(p, data, "generated")
            self.report.append("generated: %s %s (%d bytes%s)" % (
                self.files[p][0][:16], p, len(data),
                "" if before else ", new"))
        tiles, done = self.gen_map_tiles()
        for p in sorted(tiles):
            self.put(p, tiles[p], "generated")
            self.report.append("generated: %s %s (%d bytes, map squares painted over)" % (
                self.files[p][0][:16], p, len(tiles[p])))
        squares = sum(1 for line in done if " square at " in line)
        captions = sum(1 for line in done if line.startswith("caption ") and ": no " not in line)
        zones = sum(1 for line in done if line.startswith("zone ") and " the circle round " in line)
        missed = [line for line in done if ": no " in line]
        self.report.append("map:       %d squares and %d caption boxes painted over%s in %d tiles%s" % (
            squares, captions, " and %d war zones taken off" % zones if zones else "", len(tiles),
            "".join("; " + m for m in missed)))
        objects, lines = self.gen_custom_objects(set(self.base) | set(extra))
        for p in sorted(objects):
            self.put(p, objects[p], "generated")
        self.report.extend(lines)
        self.report.append("objects:   %d from client/objects/" % len(objects))
        ours = self.gen_overlay_locations()
        for p in sorted(ours):
            before = self.files.get(p)
            self.put(p, ours[p], "generated")
            self.report.append("generated: %s %s (%d bytes, %s)" % (
                self.files[p][0][:16], p, len(ours[p]),
                "the rows of our locations" if p == "xml/loc_defs.xml"
                else "a location of ours" + ("" if before else ", new")))
        self.report.append("locations: %d of ours (data/locations)" % (max(len(ours) - 1, 0)))

        # 4. ours, in git
        fdir = os.path.join(self.cdir, "files")
        n = 0
        for d, _dirs, names in os.walk(fdir):
            for f in sorted(names):
                full = os.path.join(d, f)
                p = unicodedata.normalize("NFC", os.path.relpath(full, fdir).replace(os.sep, "/"))
                if p in (".gitkeep", "README.md"):
                    continue
                why = check_path(p)
                if why:
                    raise SystemExit("client/files/%s: %s" % (p, why))
                if self.origin.get(p) == "generated":
                    raise SystemExit("client/files/%s is also generated; keep one of the two" % p)
                with open(full, "rb") as fh:
                    self.put(p, fh.read(), "files")
                n += 1
        self.report.append("files:     %d from client/files/" % n)

        # Windows puts two paths differing in case into one file, and a file
        # cannot be a folder of another.
        why = check_tree(self.files)
        if why:
            raise SystemExit(why)

        ordered = sorted(self.files, key=lambda s: s.encode("utf-8"))
        with open(os.path.join(self.out, "files.tsv"), "w", encoding="utf-8", newline="\n") as fh:
            for p in ordered:
                sha, size = self.files[p]
                fh.write("%s\t%d\t%s\n" % (sha, size, p))
        total = sum(s for _, s in self.files.values())
        self.report.append("total:     %d files, %d bytes" % (len(ordered), total))
        with open(os.path.join(self.out, "report.txt"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(self.report) + "\n")
        shutil.rmtree(self.tmp, ignore_errors=True)
        print("\n".join(self.report))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("base")
    src = b.add_mutually_exclusive_group(required=True)
    src.add_argument("--zip")
    src.add_argument("--dir")
    b.add_argument("--prefix", default="", help="the res/ folder inside the zip, with the slash")
    b.add_argument("--exclude", action="append", help="a path to leave out (repeatable)")
    b.add_argument("-o", "--out", default=os.path.join(HERE, "base.txt"))
    r = sub.add_parser("release")
    r.add_argument("--tree", default=os.path.dirname(HERE))
    r.add_argument("--store", required=True)
    r.add_argument("--res", required=True, help="the server's res/, for the string table")
    r.add_argument("--out", required=True)
    r.add_argument("--base", help="another base list (a developer stand made from their own client)")
    a = ap.parse_args(argv)
    if a.cmd == "base":
        cmd_base(a)
    else:
        Build(a.tree, a.store, a.res, a.out, a.base).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
