#!/usr/bin/env python3
"""Releases for launcher/test/TestSync.cs, signed by client/publish.py itself.

    python3 launcher/test/make_fixture.py WORK

Writes WORK/keys/{resource,launcher,stranger}.keys and WORK/served/<name>/,
each a ROOT as client/FORMAT.md lays it out:

  r1        release 1
  r2        release 2 (one file changed, one added, one dropped) and launcher 2
  stranger  r2 with its pointer signed by a key the launcher does not know
  badblob   r2 with the added file's bytes in the store swapped
  badexe    r2 with launcher 2's statement signed by a stranger
  r1again   r1's own pointer: older than r2, which a launcher has seen

The launcher test is then run against these by the C# side; nothing here
starts a server.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "client"))
import lavasig  # noqa: E402
import publish  # noqa: E402

W = os.path.abspath(sys.argv[1])
shutil.rmtree(W, ignore_errors=True)
os.makedirs(os.path.join(W, "keys"))


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


keys = {}
for name in ("resource", "launcher", "stranger"):
    k = lavasig.generate(2048)
    keys[name] = k
    write(os.path.join(W, "keys", name + ".pem"), lavasig.pem_private(k).encode())
    write(os.path.join(W, "keys", name + ".keys"), (k.keys_line() + "\n").encode())


def texts(version):
    """A string table TextsCheck.Sane accepts: BOM, the client's prologue,
    more than a thousand rows, only whitelisted tags."""
    rows = "".join("<s id='%d'>name %d v%d&lt;br&gt;</s>" % (i, i, version) for i in range(1200))
    return ("﻿<?xml version='1.0'?><data>" + rows + "</data>").encode("utf-8")


v1 = {
    "main.swf": b"CWS\x09main v1" + b"\x00" * 3000,
    "database/texts.xml": texts(1),
    "database/locations.xml": b"<locations/>",
    "locations/libs/Abu Hamad.swf": b"a name with a space",
    "mobs/a.swf": b"same bytes" * 50,
    "mobs/b.swf": b"same bytes" * 50,
    "mobs/old.swf": b"dropped in release 2",
    "hints/hints.xml": b"\xef\xbb\xbf<?xml version='1.0'?><data/>",
}
v2 = dict(v1)
v2["main.swf"] = b"CWS\x09main v2" + b"\x00" * 3001
v2["database/texts.xml"] = texts(2)
v2["sounds/new.swf"] = b"added in release 2" * 10
del v2["mobs/old.swf"]


def out_dir(name, files):
    d = os.path.join(W, "build", name)
    os.makedirs(os.path.join(d, "blobs"))
    lines = []
    for p in sorted(files, key=lambda s: s.encode("utf-8")):
        data = files[p]
        sha = publish.hashlib.sha256(data).hexdigest()
        write(os.path.join(d, "blobs", sha), data)
        lines.append("%s\t%d\t%s\n" % (sha, len(data), p))
    write(os.path.join(d, "files.tsv"), "".join(lines).encode("utf-8"))
    return d


def run(*args):
    rc = publish.main(list(args))
    if rc:
        raise SystemExit("publish %s failed: %s" % (args[0], rc))


served = os.path.join(W, "served")
r1 = os.path.join(served, "r1")
rk = os.path.join(W, "keys", "resource.pem")
state = os.path.join(W, "state")
run("publish", "--state", state, "--out", out_dir("v1", v1), "--root", r1, "--key", rk, "--source", "1" * 40)

r2 = os.path.join(served, "r2")
shutil.copytree(r1, r2)
run("publish", "--state", state, "--out", out_dir("v2", v2), "--root", r2, "--key", rk, "--source", "2" * 40)
exe = os.path.join(W, "build", "LavaReborn-2.exe")
write(exe, b"MZ launcher build 2")
body = "lava-launcher 1\nversion 2\nsha256 %s\nsize %d\ncreated 2026-10-06T00:00:00Z\n" % (
    publish.hashlib.sha256(b"MZ launcher build 2").hexdigest(), len(b"MZ launcher build 2"))
st = os.path.join(W, "build", "2.txt")
write(st, lavasig.sign_doc(keys["launcher"], body.encode()))
run("launcher", "--state", state, "--root", r2, "--key", rk, "--launcher-keys", os.path.join(W, "keys", "launcher.keys"),
    "--exe", exe, "--statement", st)

# A pointer signed by someone else.
stranger = os.path.join(served, "stranger")
shutil.copytree(r2, stranger)
with open(os.path.join(r2, "current.txt"), "rb") as fh:
    body2, _, _ = lavasig.split_doc(fh.read())
write(os.path.join(stranger, "current.txt"), lavasig.sign_doc(keys["stranger"], body2))

# The store's copy of the added file swapped for other bytes.
badblob = os.path.join(served, "badblob")
shutil.copytree(r2, badblob)
sha_new = publish.hashlib.sha256(v2["sounds/new.swf"]).hexdigest()
write(publish.blob_path(badblob, sha_new), b"not what the manifest says" * 7)

# Launcher 2's statement signed by someone else (the pointer is still good).
badexe = os.path.join(served, "badexe")
shutil.copytree(r2, badexe)
write(os.path.join(badexe, "launcher", "2.txt"), lavasig.sign_doc(keys["stranger"], body.encode()))

# Release 1's pointer again, after release 2 was seen.
shutil.copytree(r1, os.path.join(served, "r1again"))

# What the C# side compares the installed files with.
for name, files in (("v1", v1), ("v2", v2)):
    for p, data in files.items():
        write(os.path.join(W, "expect", name, *p.split("/")), data)
print("fixture: %s" % W)
