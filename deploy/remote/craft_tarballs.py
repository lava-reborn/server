"""Bad tarballs for deploy/remote/test_gate.sh: each one is a good tree plus
one poison, so the gate refuses it for the poison and for nothing else.

    python3 deploy/remote/craft_tarballs.py GOOD_TREE_DIR OUT_DIR

GOOD_TREE_DIR is a tree as deploy/ci/pack.sh would pack it. Python's tarfile
writes no sparse members; the test builds those with GNU tar itself.
"""
import io
import os
import sys
import tarfile

good, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)


def base(tf):
    """The good tree, as pack.sh would pack it (names ./x)."""
    tf.add(good, arcname=".")


def add_bytes(tf, name, data, kind=tarfile.REGTYPE, link="", mode=0o644):
    ti = tarfile.TarInfo(name)
    ti.type = kind
    ti.linkname = link
    ti.size = len(data) if kind == tarfile.REGTYPE else 0
    ti.mode = mode
    tf.addfile(ti, io.BytesIO(data) if kind == tarfile.REGTYPE else None)


def make(label, poison, with_base=True):
    path = os.path.join(out, label + ".tgz")
    with tarfile.open(path, "w:gz") as tf:
        if with_base:
            base(tf)
        poison(tf)
    print(label, os.path.getsize(path))


make("traversal", lambda tf: add_bytes(tf, "../evil.txt", b"x"))
make("traversal_deep", lambda tf: add_bytes(tf, "./server/../../evil.txt", b"x"))
make("absolute", lambda tf: add_bytes(tf, "/tmp/cicdtest-evil.txt", b"x"))
make("symlink", lambda tf: add_bytes(tf, "./server/passwd", b"", tarfile.SYMTYPE, "/etc/passwd"))
make("hardlink", lambda tf: add_bytes(tf, "./server/hard", b"", tarfile.LNKTYPE, "./Dockerfile"))
make("fifo", lambda tf: add_bytes(tf, "./server/pipe", b"", tarfile.FIFOTYPE))
make("topdir", lambda tf: add_bytes(tf, "./evil/x.py", b"x"))
make("dotenv", lambda tf: add_bytes(tf, "./.env", b"LAVA_DB_URL=postgresql://evil\n"))
make("dotenv_deep", lambda tf: add_bytes(tf, "./deploy/.env", b"x\n"))
make("database", lambda tf: add_bytes(tf, "./data/lava.db", b"SQLite format 3\0"))
make("res", lambda tf: add_bytes(tf, "./res/database/mobs.xml", b"<x/>"))
make("newline_name", lambda tf: add_bytes(tf, "./server/a\nb.py", b"x"))
make("oversize", lambda tf: add_bytes(tf, "./data/noise.bin", os.urandom(9 * 1024 * 1024)))
make("bomb", lambda tf: add_bytes(tf, "./data/zeros.bin", b"\0" * (100 * 1024 * 1024)))
make("setuid", lambda tf: add_bytes(tf, "./server/su", b"#!/bin/sh\n", mode=0o4755))
make("sticky_dir", lambda tf: add_bytes(tf, "./data/tmp", b"", tarfile.DIRTYPE, mode=0o1777))
make("override", lambda tf: add_bytes(
    tf, "./docker-compose.override.yml",
    b"services:\n  game:\n    privileged: true\n"))
make("compose_yaml", lambda tf: add_bytes(
    tf, "./compose.yaml", b"services:\n  game:\n    image: busybox\n"))


def no_dockerfile(tf):
    for root, dirs, files in os.walk(good):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, good)
            if rel != "Dockerfile":
                tf.add(full, arcname="./" + rel)


make("no_dockerfile", no_dockerfile, with_base=False)
with open(os.path.join(out, "garbage.tgz"), "wb") as fh:
    fh.write(os.urandom(4096))
print("garbage 4096")
