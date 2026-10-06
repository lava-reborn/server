#!/usr/bin/env python3
"""Put client releases where the launcher finds them (client/FORMAT.md).

Runs on the server as root, out of the gate's own directory (install.sh
copies it with lavasig.py and build.py to /opt/lava-ci/client/): this is the
code that holds the resource key, so it is the installed copy that runs,
never the one a deploy brings.

    publish.py check     --out OUT --root ROOT
    publish.py publish   --out OUT --root ROOT --key KEY --source COMMIT [--keep 8]
    publish.py import-base --root ROOT --base base.txt (--zip Z --prefix P | --dir D)
    publish.py add       --root ROOT FILE...                  big files for client/extra.txt
    publish.py launcher  --root ROOT --key KEY --launcher-keys KEYS --exe EXE --statement TXT
                         [--download DIR] [--force]
    publish.py rollback  --root ROOT --key KEY [--to SERIAL]
    publish.py status    --root ROOT
    publish.py gc        --root ROOT --base base.txt [--extra extra.txt] [--dry-run]
    publish.py launcher-version                                the published launcher's, or 0

Every command that reads or writes what is published also takes --state
(default: state/ beside this script, /opt/lava-ci/client/state, root's
only).

OUT is what client/build.py release wrote. ROOT is the served directory,
/opt/lava-site/download/client on production.

WHAT IS TRUSTED. Nothing in OUT: every path is checked against the format,
every file is opened without following links and must be a regular file,
every blob that is not already in the store is hashed before it goes in, and
a file the store does not have stops the publish. Nothing in ROOT either, as
a source of truth: it is what the web serves, and whatever can write there
must not be able to make this script sign something. The pointer and the
manifests this script signed are kept again in STATE, and only STATE is read
back -- the previous serial, the manifest a launcher publish re-signs, the
manifest a rollback returns to, what gc keeps. ROOT and its folders must be
real folders, root's and writable by root alone, or nothing is written into
them; files go in through temporary files nobody else could have made.
"""
import argparse
import hashlib
import os
import re
import stat
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402  (the path rules and list readers, one copy)
import lavasig  # noqa: E402

MAX_FILES = 200000
MAX_FILE = 512 * 1024 * 1024
MAX_LIST = 64 * 1024 * 1024
ENTRY = re.compile(r"([0-9a-f]{64})\t([0-9]+)\t(.+)")


class Refused(Exception):
    pass


# --- the file system, carefully ------------------------------------------------------

def check_path(p):
    return build.check_path(p) is None


def now_iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))


def safe_dir(path, mode=0o755):
    """path as a real folder: made if missing; refused if it is a link, or,
    when this runs as root, if it is not root's or others may write in it."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        parent = os.path.dirname(path)
        if parent and parent != path:
            safe_dir(parent, mode) if not os.path.isdir(parent) else None
        os.mkdir(path, mode)
        os.chmod(path, mode)
        st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        raise Refused("%s is not a plain folder" % path)
    if os.geteuid() == 0 and (st.st_uid != 0 or st.st_mode & 0o022):
        raise Refused("%s must be root's and writable by root alone" % path)
    return path


def blob_path(root, sha):
    return os.path.join(root, "store", sha[:2], sha)


def write_atomic(path, data, mode=0o644):
    """data at path, through a temporary file in the same folder that
    mkstemp made (O_EXCL: no link someone left there is followed)."""
    d = safe_dir(os.path.dirname(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix="." + os.path.basename(path) + ".")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    try:
        dfd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


def open_regular(path, limit):
    """A regular file opened without following a link, and no bigger than limit."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as e:
        raise Refused("%s cannot be opened as a plain file (%s)" % (path, e.strerror))
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
        os.close(fd)
        raise Refused("%s is not a plain file of at most %d bytes" % (path, limit))
    return os.fdopen(fd, "rb")


def store_bytes(root, data, sha=None):
    """Put data into the store under its own hash; returns the hash."""
    got = hashlib.sha256(data).hexdigest()
    if sha is not None and got != sha:
        raise Refused("content does not match its hash %s" % sha[:16])
    dest = blob_path(root, got)
    if not os.path.isfile(dest):
        safe_dir(os.path.join(root, "store"))
        write_atomic(dest, data)
    return got


def store_file(root, src, sha=None, size=None):
    """Like store_bytes, streamed from a plain file: hashed on the way into
    a temporary file beside its destination."""
    h = hashlib.sha256()
    inc = safe_dir(os.path.join(safe_dir(os.path.join(root, "store")), ".incoming"))
    fd, tmp = tempfile.mkstemp(dir=inc)
    n = 0
    try:
        with open_regular(src, MAX_FILE) as fi, os.fdopen(fd, "wb") as fo:
            while True:
                chunk = fi.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
                fo.write(chunk)
                n += len(chunk)
            fo.flush()
            os.fsync(fo.fileno())
        got = h.hexdigest()
        if (sha is not None and got != sha) or (size is not None and n != size):
            raise Refused("%s does not hold what it should (%s)" % (src, (sha or got)[:16]))
        dest = blob_path(root, got)
        if not os.path.isfile(dest):
            safe_dir(os.path.dirname(dest))
            os.chmod(tmp, 0o644)
            os.replace(tmp, dest)
        return got, n
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Lock:
    """One writer of ROOT and STATE at a time: a deploy, a launcher publish,
    a rollback and a gc must not interleave."""

    def __init__(self, state):
        self.dir = state

    def __enter__(self):
        safe_dir(self.dir, 0o700)
        self.fd = os.open(os.path.join(self.dir, ".lock"),
                          os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except ImportError:
            pass
        return self

    def __exit__(self, *exc):
        os.close(self.fd)


# --- what this script published, kept in STATE ---------------------------------------

POINTER = re.compile(
    r"lava-pointer 1\n"
    r"serial ([0-9]{1,15})\n"
    r"created (\S+)\n"
    r"manifest ([0-9a-f]{64}) ([0-9]+) (manifests/[0-9]+\.txt)\n"
    r"(?:launcher ([0-9]{1,9}) ([0-9a-f]{64}) ([0-9]+) (launcher/[0-9]+\.exe)\n)?\Z")


def read_pointer(state, key=None):
    """The last pointer this script published, or None. With key, its
    signature is checked against the key's own public half."""
    path = os.path.join(state, "current.txt")
    if not os.path.exists(path):
        return None
    with open_regular(path, 64 * 1024) as fh:
        doc = fh.read()
    if key is not None:
        try:
            body = lavasig.verify_doc({key.id: (key.e, key.n)}, doc)
        except ValueError as e:
            raise Refused("the kept pointer does not verify with this key: %s" % e)
    else:
        body, _kid, _sig = lavasig.split_doc(doc)
    m = POINTER.match(body.decode("utf-8"))
    if not m:
        raise Refused("the kept pointer is not one this script wrote")
    p = {"serial": int(m.group(1)), "created": m.group(2),
         "manifest": (m.group(3), int(m.group(4)), m.group(5)), "launcher": None}
    if m.group(6):
        p["launcher"] = (int(m.group(6)), m.group(7), int(m.group(8)), m.group(9))
    return p


def kept_manifest(state, rel, sha=None):
    """The bytes of a manifest this script published, from STATE; checked
    against sha when one is given."""
    path = os.path.join(state, rel)
    with open_regular(path, MAX_LIST) as fh:
        data = fh.read()
    if sha is not None and hashlib.sha256(data).hexdigest() != sha:
        raise Refused("the kept %s is not the one the pointer names" % rel)
    return data


def entries_of(data):
    out = {}
    for line in data.decode("utf-8").split("\n"):
        m = ENTRY.fullmatch(line)
        if m:
            out[m.group(3)] = (m.group(1), int(m.group(2)))
    return out


def manifests(state):
    d = os.path.join(state, "manifests")
    if not os.path.isdir(d):
        return []
    return sorted(int(f[:-4]) for f in os.listdir(d) if re.fullmatch(r"[0-9]+\.txt", f))


# --- check ------------------------------------------------------------------------------

def check(out, root):
    """(entries [(sha, size, path)], new blobs {sha: path in OUT}) or Refused."""
    with open_regular(os.path.join(out, "files.tsv"), MAX_LIST) as fh:
        raw = fh.read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Refused("files.tsv is not ASCII, and every allowed path is")
    if not text.endswith("\n"):
        raise Refused("files.tsv does not end with a newline")
    entries, prev = [], None
    for no, line in enumerate(text[:-1].split("\n"), 1):
        m = ENTRY.fullmatch(line)
        if not m:
            raise Refused("files.tsv:%d: not 'sha256 TAB size TAB path'" % no)
        sha, size, p = m.group(1), int(m.group(2)), m.group(3)
        why = build.check_path(p)
        if why:
            raise Refused("files.tsv:%d: %r: %s" % (no, p[:80], why))
        if prev is not None and p <= prev:
            raise Refused("files.tsv:%d: not sorted, or %s twice" % (no, p))
        prev = p
        if size > MAX_FILE:
            raise Refused("files.tsv:%d: %s is %d bytes" % (no, p, size))
        entries.append((sha, size, p))
        if len(entries) > MAX_FILES:
            raise Refused("files.tsv lists more than %d files" % MAX_FILES)
    if not entries:
        raise Refused("files.tsv lists no files")
    why = build.check_tree([p for _, _, p in entries])
    if why:
        raise Refused("files.tsv: %s" % why)
    if not any(p == "main.swf" for _, _, p in entries):
        raise Refused("files.tsv has no main.swf: that is not a release of this game")

    new, missing = {}, []
    bdir = os.path.join(out, "blobs")
    for sha, size, p in entries:
        if sha in new:
            continue
        stored = blob_path(root, sha)
        if os.path.isfile(stored) and not os.path.islink(stored) and os.path.getsize(stored) == size:
            continue
        cand = os.path.join(bdir, sha)
        try:
            st = os.lstat(cand)
        except FileNotFoundError:
            missing.append((sha, p))
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_size != size:
            raise Refused("blobs/%s is not a plain file of %d bytes (%s)" % (sha[:16], size, p))
        h = hashlib.sha256()
        with open_regular(cand, MAX_FILE) as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != sha:
            raise Refused("blobs/%s does not hold what files.tsv says (%s)" % (sha[:16], p))
        new[sha] = (cand, size)
    if missing:
        sample = ", ".join("%s (%s)" % (p, s[:12]) for s, p in missing[:5])
        raise Refused("%d file(s) are in neither the store nor the build: %s" % (len(missing), sample))
    return entries, new


def cmd_check(a):
    entries, new = check(a.out, a.root)
    print("check: %d files, %d bytes, %d new blob(s)" % (
        len(entries), sum(s for _, s, _ in entries), len(new)))


# --- publish ----------------------------------------------------------------------------

def make_pointer(key, serial, manifest, launcher):
    body = "lava-pointer 1\nserial %d\ncreated %s\nmanifest %s %d %s\n" % (
        serial, now_iso(), manifest[0], manifest[1], manifest[2])
    if launcher:
        body += "launcher %d %s %d %s\n" % launcher
    return lavasig.sign_doc(key, body.encode("utf-8"))


def next_serial(prev):
    return max(int(time.time()), (prev["serial"] + 1) if prev else 0)


def put_pointer(a, doc):
    """STATE first, then ROOT: a crash between the two leaves STATE ahead,
    and the next serial is counted from STATE."""
    write_atomic(os.path.join(safe_dir(a.state, 0o700), "current.txt"), doc, 0o600)
    write_atomic(os.path.join(safe_dir(a.root), "current.txt"), doc)


def diff(old, new):
    """(added, changed, removed) path lists between two {path: (sha, size)}."""
    added = sorted(p for p in new if p not in old)
    removed = sorted(p for p in old if p not in new)
    changed = sorted(p for p in new if p in old and old[p][0] != new[p][0])
    return added, changed, removed


def prune(a, keep, current):
    for s in (manifests(a.state)[:-keep] if keep > 0 else []):
        if s == current:
            continue
        for base in (a.state, a.root):
            path = os.path.join(base, "manifests", "%d.txt" % s)
            if os.path.isfile(path):
                os.unlink(path)


def prepare_root(root, *subs):
    """ROOT and the folders a command writes into, checked before the first
    byte goes anywhere."""
    safe_dir(root)
    for s in subs:
        safe_dir(os.path.join(root, s))


def cmd_publish(a):
    key = lavasig.read_private(a.key)
    prepare_root(a.root, "store", "manifests")
    with Lock(a.state):
        entries, new = check(a.out, a.root)
        for sha, (src, size) in sorted(new.items()):
            store_file(a.root, src, sha, size)
        prev = read_pointer(a.state, key)
        serial = next_serial(prev)
        total = sum(s for _, s, _ in entries)
        body = "lava-manifest 1\nserial %d\nsource %s\nfiles %d %d\n" % (
            serial, a.source, len(entries), total)
        body += "".join("%s\t%d\t%s\n" % e for e in entries)
        data = body.encode("ascii")
        rel = "manifests/%d.txt" % serial
        write_atomic(os.path.join(safe_dir(a.state, 0o700), rel), data, 0o600)
        write_atomic(os.path.join(a.root, rel), data)
        manifest = (hashlib.sha256(data).hexdigest(), len(data), rel)
        launcher = prev["launcher"] if prev else None

        # Everything that could fail is done before the pointer: once it is
        # out, the gate must not roll the server back under a release that
        # players' launchers already see.
        old = {}
        if prev:
            try:
                old = entries_of(kept_manifest(a.state, prev["manifest"][2], prev["manifest"][0]))
            except (Refused, OSError):
                old = {}
        added, changed, removed = diff(old, {p: (s, n) for s, n, p in entries})
        doc = make_pointer(key, serial, manifest, launcher)
        put_pointer(a, doc)
        try:
            prune(a, a.keep, serial)
        except OSError as e:
            print("warning: old manifests not pruned: %s" % e)

    print("release %d: %d files, %d bytes, %d new blob(s) stored" % (serial, len(entries), total, len(new)))
    if prev:
        print("since %d: %d added, %d changed, %d removed" % (
            prev["serial"], len(added), len(changed), len(removed)))
        for p in (changed + added)[:8]:
            print("  %s" % p)
    for s, n, p in entries:
        if p == "database/texts.xml":
            print("texts %s" % s)
    print("launcher %d" % launcher[0] if launcher else "launcher none published yet")


# --- the original game, once --------------------------------------------------------------

def cmd_import_base(a):
    base = build.read_entries(a.base, "lava-base 1")
    if not base:
        raise Refused("%s is empty" % a.base)
    z = zipfile.ZipFile(a.zip) if a.zip else None
    stored = present = 0
    bad, missing = [], []
    safe_dir(a.root)
    with Lock(a.state):
        for p, (sha, size) in sorted(base.items()):
            if os.path.isfile(blob_path(a.root, sha)):
                present += 1
                continue
            try:
                if z:
                    data = z.read(a.prefix + p)
                else:
                    with open_regular(os.path.join(a.dir, *p.split("/")), MAX_FILE) as fh:
                        data = fh.read()
            except (KeyError, OSError, Refused):
                missing.append(p)
                continue
            if hashlib.sha256(data).hexdigest() != sha or len(data) != size:
                bad.append(p)
                continue
            store_bytes(a.root, data, sha)
            stored += 1
    print("import-base: %d stored, %d already there, %d missing, %d not matching base.txt" % (
        stored, present, len(missing), len(bad)))
    for p in (missing + bad)[:10]:
        print("  %s" % p)
    return 1 if (missing or bad) else 0


def cmd_add(a):
    safe_dir(a.root)
    with Lock(a.state):
        for f in a.files:
            sha, size = store_file(a.root, f)
            print("%s\t%d\t%s" % (sha, size, os.path.basename(f)))
    print("# add these lines to client/extra.txt with the path each file takes under res/")


# --- the launcher -----------------------------------------------------------------------------

STATEMENT = re.compile(
    r"lava-launcher 1\nversion ([0-9]{1,9})\nsha256 ([0-9a-f]{64})\nsize ([0-9]+)\ncreated (\S+)\n\Z")


def cmd_launcher(a):
    key = lavasig.read_private(a.key)
    lkeys = lavasig.read_keys(a.launcher_keys)
    with open_regular(a.statement, 64 * 1024) as fh:
        doc = fh.read()
    try:
        body = lavasig.verify_doc(lkeys, doc)
    except ValueError as e:
        raise Refused("statement: %s" % e)
    m = STATEMENT.match(body.decode("utf-8"))
    if not m:
        raise Refused("statement is not a launcher statement")
    version, sha, size = int(m.group(1)), m.group(2), int(m.group(3))
    with open_regular(a.exe, MAX_FILE) as fh:
        exe = fh.read()
    if hashlib.sha256(exe).hexdigest() != sha or len(exe) != size:
        raise Refused("the exe is not the one the statement describes")
    prepare_root(a.root, "launcher", "manifests")
    with Lock(a.state):
        prev = read_pointer(a.state, key)
        if not prev:
            raise Refused("no release is published yet; a deploy publishes the first one")
        if prev["launcher"] and prev["launcher"][0] >= version and not a.force:
            raise Refused("launcher %d is published already; this one is %d" % (prev["launcher"][0], version))
        # The release stays the one STATE says was published, checked again,
        # and the served copy of its manifest is put back from STATE.
        mdata = kept_manifest(a.state, prev["manifest"][2], prev["manifest"][0])
        write_atomic(os.path.join(a.root, prev["manifest"][2]), mdata)
        write_atomic(os.path.join(a.root, "launcher", "%d.exe" % version), exe)
        write_atomic(os.path.join(a.root, "launcher", "%d.txt" % version), doc)
        launcher = (version, sha, size, "launcher/%d.exe" % version)
        serial = next_serial(prev)
        put_pointer(a, make_pointer(key, serial, prev["manifest"], launcher))
    print("launcher %d published in pointer %d" % (version, serial))
    if a.download:
        # The site's own link and /api/client, which every launcher before the
        # self-updating one compares itself with. Both files go in through
        # write_atomic: a folder that is not root's is refused, and a link left
        # at either name is replaced, never written through.
        dest = os.path.join(a.download, "LavaReborn.exe")
        try:
            if os.path.isfile(dest) and not os.path.islink(dest):
                with open_regular(dest, MAX_FILE) as fh:
                    old = fh.read()
                if hashlib.sha256(old).hexdigest() != sha:
                    write_atomic(dest + ".prev", old)
            write_atomic(dest, exe)
            print("%s replaced (previous kept as LavaReborn.exe.prev)" % dest)
        except (OSError, Refused) as e:
            print("warning: %s not replaced: %s -- the self-updating launcher is out anyway" % (dest, e))


def cmd_rollback(a):
    key = lavasig.read_private(a.key)
    prepare_root(a.root, "store", "manifests")
    with Lock(a.state):
        prev = read_pointer(a.state, key)
        if not prev:
            raise Refused("nothing is published")
        cur = int(re.search(r"([0-9]+)\.txt$", prev["manifest"][2]).group(1))
        have = manifests(a.state)
        if a.to is not None:
            if a.to not in have:
                raise Refused("manifests/%d.txt is not kept" % a.to)
            target = a.to
        else:
            older = [s for s in have if s < cur]
            if not older:
                raise Refused("no release older than %d is kept" % cur)
            target = older[-1]
        rel = "manifests/%d.txt" % target
        data = kept_manifest(a.state, rel)
        for sha, _size in entries_of(data).values():
            if not os.path.isfile(blob_path(a.root, sha)):
                raise Refused("%s needs %s, which the store no longer has" % (rel, sha[:16]))
        write_atomic(os.path.join(a.root, rel), data)
        manifest = (hashlib.sha256(data).hexdigest(), len(data), rel)
        serial = next_serial(prev)
        put_pointer(a, make_pointer(key, serial, manifest, prev["launcher"]))
    print("pointer %d now names release %d (was %d)" % (serial, target, cur))


def cmd_launcher_version(a):
    """The published launcher's version, 0 if none: the gate builds the next."""
    p = read_pointer(a.state)
    print(p["launcher"][0] if p and p["launcher"] else 0)
    return 0


def cmd_status(a):
    p = read_pointer(a.state)
    if not p:
        print("nothing published (no %s)" % os.path.join(a.state, "current.txt"))
        return 0
    print("pointer:  serial %d, %s" % (p["serial"], p["created"]))
    print("release:  %s (%d bytes)" % (p["manifest"][2], p["manifest"][1]))
    print("launcher: %s" % ("version %d, %s" % (p["launcher"][0], p["launcher"][1][:16]) if p["launcher"] else "none"))
    print("kept:     %s" % " ".join(str(s) for s in manifests(a.state)))
    served = os.path.join(a.root, "current.txt")
    if os.path.isfile(served):
        with open(os.path.join(a.state, "current.txt"), "rb") as f1, open(served, "rb") as f2:
            print("served:   %s" % ("the same pointer" if f1.read() == f2.read() else "DIFFERS from the kept one"))
    n = size = 0
    for d, _dirs, files in os.walk(os.path.join(a.root, "store")):
        if os.path.basename(d) == ".incoming":
            continue
        for f in files:
            n += 1
            size += os.path.getsize(os.path.join(d, f))
    print("store:    %d files, %.1f MB" % (n, size / 1048576.0))
    return 0


def cmd_gc(a):
    gone = size = 0
    with Lock(a.state):
        # Inside the lock: a release published meanwhile would otherwise lose
        # the files it just stored.
        keep = set()
        for s in manifests(a.state):
            for sha, _ in entries_of(kept_manifest(a.state, "manifests/%d.txt" % s)).values():
                keep.add(sha)
        for lst, head in ((a.base, "lava-base 1"), (a.extra, "lava-extra 1")):
            if lst:
                for sha, _ in build.read_entries(lst, head).values():
                    keep.add(sha)
        for d, _dirs, files in os.walk(os.path.join(a.root, "store")):
            for f in files:
                if re.fullmatch(r"[0-9a-f]{64}", f) and f not in keep:
                    full = os.path.join(d, f)
                    size += os.path.getsize(full)
                    gone += 1
                    if not a.dry_run:
                        os.unlink(full)
    print("gc: %s %d blob(s), %.1f MB" % ("would remove" if a.dry_run else "removed", gone, size / 1048576.0))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_state = os.path.join(HERE, "state")

    def with_state(p):
        p.add_argument("--state", default=default_state,
                       help="where what was published is kept (default %(default)s)")
        return p

    c = sub.add_parser("check")
    c.add_argument("--out", required=True)
    c.add_argument("--root", required=True)

    p = with_state(sub.add_parser("publish"))
    p.add_argument("--out", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--keep", type=int, default=8)

    i = with_state(sub.add_parser("import-base"))
    i.add_argument("--root", required=True)
    i.add_argument("--base", required=True)
    g = i.add_mutually_exclusive_group(required=True)
    g.add_argument("--zip")
    g.add_argument("--dir")
    i.add_argument("--prefix", default="")

    d = with_state(sub.add_parser("add"))
    d.add_argument("--root", required=True)
    d.add_argument("files", nargs="+")

    l = with_state(sub.add_parser("launcher"))
    l.add_argument("--root", required=True)
    l.add_argument("--key", required=True)
    l.add_argument("--launcher-keys", required=True)
    l.add_argument("--exe", required=True)
    l.add_argument("--statement", required=True)
    l.add_argument("--download")
    l.add_argument("--force", action="store_true")

    r = with_state(sub.add_parser("rollback"))
    r.add_argument("--root", required=True)
    r.add_argument("--key", required=True)
    r.add_argument("--to", type=int)

    s = with_state(sub.add_parser("status"))
    s.add_argument("--root", required=True)

    with_state(sub.add_parser("launcher-version"))

    gc = with_state(sub.add_parser("gc"))
    gc.add_argument("--root", required=True)
    gc.add_argument("--base")
    gc.add_argument("--extra")
    gc.add_argument("--dry-run", action="store_true")

    a = ap.parse_args(argv)
    os.umask(0o022)
    try:
        rc = {
            "check": cmd_check, "publish": cmd_publish, "import-base": cmd_import_base,
            "add": cmd_add, "launcher": cmd_launcher, "rollback": cmd_rollback,
            "status": cmd_status, "gc": cmd_gc, "launcher-version": cmd_launcher_version,
        }[a.cmd](a)
    except Refused as e:
        print("publish: refused: %s" % e, file=sys.stderr)
        return 2
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
