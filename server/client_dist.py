"""The game client as a download: manifest and files for the launcher.

The launcher installs the game, updates only the files that changed and
checks the files it has against the digests here (issue #50). This module is
the server half: a manifest of every file under one directory and the files
themselves, with Range, so a download cut off halfway goes on from where it
stopped instead of starting over.

Off unless LAVA_CLIENT_DIST names a directory: the client is the original
game's files, and handing them out is the owner's decision, not this code's.
With it unset, or pointing at nothing, both addresses answer 404, the same as
any path that is not ours.

The directory is a reference copy, not the player's own res/: whatever is in
it goes out, under its path relative to it. In the container the only mount is
LAVA_RES_DIR on /res (the deploy gate refuses any other), so the reference
copy is either that whole directory or a directory inside it.

Hashing 2.2 GB takes a while, so the manifest is built in a background thread
at start and answers 503 with Retry-After until it is ready; the digests are
kept in a cache file keyed by size and mtime, and a restart rehashes only what
changed. A file that no longer matches its manifest row is not served: the
request answers 503 and the manifest is rebuilt, because a launcher that
resumed into a different file would glue two versions together.
"""
import fnmatch
import gzip
import hashlib
import json
import os
import threading
import time

ROOT = os.environ.get("LAVA_CLIENT_DIST", "").strip()
# Version the launcher compares with what it installed. Empty: derived from
# the file list itself, so it changes exactly when a file does.
VERSION = os.environ.get("LAVA_CLIENT_VERSION", "").strip()
# Next to the database by default: the one place the http container may write.
CACHE = os.environ.get("LAVA_CLIENT_CACHE", "").strip() or os.path.join(
    os.path.dirname(os.path.abspath(os.environ.get("LAVA_DB") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "lava.db"))),
    "client_manifest.cache.json")
# Leftovers a working copy collects and no player needs: backups of main.swf
# from patching it, and what Explorer drops into every folder it shows.
EXCLUDE = [p.strip() for p in os.environ.get(
    "LAVA_CLIENT_EXCLUDE", "*.orig,Thumbs.db,desktop.ini").split(",")
    if p.strip()]

BASE = "/exe/lavaclient/client/"
MANIFEST_URL = BASE + "manifest"
FILES_URL = BASE + "files/"
PACKS_URL = BASE + "pack/"
CHUNK = 1 << 20
# How big a pack grows before the next one starts. A file larger than this
# is a pack of its own.
PACK_BYTES = int(float(os.environ.get("LAVA_CLIENT_PACK_MB", "64")) * (1 << 20))


def _skip(name):
    return name.startswith(".") or any(
        fnmatch.fnmatch(name.lower(), p.lower()) for p in EXCLUDE)


def _sha256(full):
    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _load_cache(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_cache(path, cache):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
        os.replace(tmp, path)
    except OSError:
        pass  # a cache that cannot be written only costs the next start time


def scan(root, cache_path=None):
    """Every file under root as {path: (size, mtime_ns, sha256)}.

    Paths are relative to root with forward slashes, sorted, the way the
    launcher lays them under its own res/.
    """
    cache = _load_cache(cache_path) if cache_path else {}
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not _skip(x))
        for name in sorted(files):
            if _skip(name):
                continue
            full = os.path.join(d, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            hit = cache.get(rel)
            if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
                out[rel] = tuple(hit)
            else:
                out[rel] = (st.st_size, st.st_mtime_ns, _sha256(full))
    if cache_path:
        _save_cache(cache_path, {k: list(v) for k, v in out.items()})
    return dict(sorted(out.items()))


def _digest(rows):
    h = hashlib.sha256()
    for rel, size, sha in rows:
        h.update(("%s\0%d\0%s\n" % (rel, size, sha)).encode("utf-8"))
    return h.hexdigest()


def packs(files, limit=None):
    """The files cut into runs of consecutive manifest rows, about limit
    bytes each: [(id, [path, ...], size)].

    Why packs at all: the client is 30 thousand files, three quarters of them
    under 16 KB, and one request per file spends the install on round trips
    rather than on bytes. Why not an archive: the SWFs, 95 % of the volume,
    are compressed already (zlib over a sample of them saves 1 %), so a zip
    would buy nothing but a second copy of 2 GB on the player's disk and an
    unpacking pass after the download. A pack is the files themselves, back
    to back, in manifest order, with nothing in between: the launcher cuts
    the stream by the sizes it already has, checks each piece against its
    digest and writes it straight to its place. It is never stored here
    either; the server reads it out of the files as it goes.

    The id is a digest of the rows it carries, so a pack is the same bytes
    for as long as its address works: when any of its files changes the old
    id answers 404 and the launcher asks for the manifest again.
    """
    limit = limit or PACK_BYTES
    out, run, size = [], [], 0
    for rel, (fsize, _m, sha) in files.items():
        if run and size + fsize > limit:
            out.append(run)
            run, size = [], 0
        run.append((rel, fsize, sha))
        size += fsize
    if run:
        out.append(run)
    return [(_digest(r)[:16], [x[0] for x in r], sum(x[1] for x in r))
            for r in out]


def document(files, version="", limit=None):
    """The manifest as the launcher reads it, encoded once, and its packs."""
    if not version:
        version = _digest((rel, size, sha) for rel, (size, _m, sha)
                          in files.items())[:16]
    index = {rel: i for i, rel in enumerate(files)}
    cut = packs(files, limit)
    doc = {
        "version": version,
        "size": sum(v[0] for v in files.values()),
        "count": len(files),
        # Each file is base + its path, percent-encoded: fifteen of them
        # have a space in the name.
        "base": FILES_URL,
        "files": [{"path": rel, "size": size, "sha256": sha}
                  for rel, (size, _m, sha) in files.items()],
        # Pack i is files[first : first + count] back to back, at
        # pack_base + id. Range works on it as on a file.
        "pack_base": PACKS_URL,
        "packs": [{"id": pid, "first": index[rels[0]], "count": len(rels),
                   "size": size} for pid, rels, size in cut],
    }
    blob = json.dumps(doc, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return blob, {pid: rels for pid, rels, _s in cut}


class Dist:
    """One reference copy: its manifest, built in the background."""

    def __init__(self, root, cache_path=None, version=""):
        self.root = os.path.abspath(root) if root else ""
        self.cache_path = cache_path
        self.version = version
        self.files = None
        self.blob = None
        self.blob_gz = None
        self.packs = {}
        self._lock = threading.Lock()
        self._building = False

    def enabled(self):
        return bool(self.root) and os.path.isdir(self.root)

    def start(self):
        """Build the manifest unless a build is already running."""
        if not self.enabled():
            return
        with self._lock:
            if self._building:
                return
            self._building = True
        threading.Thread(target=self._build, daemon=True,
                         name="client-manifest").start()

    def _build(self):
        t0 = time.time()
        try:
            files = scan(self.root, self.cache_path)
            blob, cut = document(files, self.version)
            # Swapped together: a reader sees the old set or the new one.
            # The manifest is 4 MB of JSON for the real client and a
            # quarter of that gzipped; the launcher asks for it every start.
            self.blob_gz = gzip.compress(blob, 6, mtime=0)
            self.files, self.blob, self.packs = files, blob, cut
            print("client dist: %d files, %.1f GB, %.0f s" % (
                len(files), sum(v[0] for v in files.values()) / 1e9,
                time.time() - t0), flush=True)
        except Exception as exc:  # noqa: BLE001
            print("client dist: manifest failed: %r" % exc, flush=True)
        finally:
            with self._lock:
                self._building = False

    def wait(self, timeout=None):
        """Until the first manifest is in (tests, and nothing else)."""
        end = None if timeout is None else time.time() + timeout
        while self.blob is None or self._building:
            if end is not None and time.time() > end:
                return False
            time.sleep(0.05)
        return True

    def _check(self, files, rel):
        size, mtime, _sha = files[rel]
        full = os.path.join(self.root, *rel.split("/"))
        try:
            st = os.stat(full)
        except OSError:
            return None
        if st.st_size != size or st.st_mtime_ns != mtime:
            return None
        return full, size

    def row(self, rel):
        """([(full path, size)], size, etag) of a listed file that still
        matches its row, "stale" when it does not, None when it is not
        listed at all."""
        files = self.files
        if files is None or rel not in files:
            return None
        seg = self._check(files, rel)
        if seg is None:
            self.start()
            return "stale"
        return [seg], seg[1], files[rel][2]

    def pack(self, pid):
        """The same as row(), for a pack: its files in order."""
        files, cut = self.files, self.packs
        if files is None or pid not in cut:
            return None
        segs = [self._check(files, rel) for rel in cut[pid]]
        if None in segs:
            self.start()
            return "stale"
        return segs, sum(x[1] for x in segs), pid


def parse_range(header, size):
    """A Range header against a file of size bytes.

    None: no range, or one this does not honour (several ranges, another
    unit), so the whole file goes out with 200 as RFC 9110 allows.
    "bad": a range that starts past the end, answered with 416.
    (start, end) inclusive otherwise.
    """
    if not header:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, dash, last = spec.strip().partition("-")
    if not dash:
        return None
    try:
        if first == "":
            n = int(last)
            if n <= 0:
                return "bad"
            return max(0, size - n), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start >= size:
        return "bad"
    if start < 0 or end < start:
        return None
    return start, min(end, size - 1)


DIST = Dist(ROOT, CACHE, VERSION)
