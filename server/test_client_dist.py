"""Раздача клиента лаунчеру: манифест, файлы, докачка (issue #50).

Лаунчер ставит игру, обновляет изменившиеся файлы и проверяет свои по
манифесту под /exe/lavaclient/client/ (server/client_dist.py). Проверяется:
манифест перечисляет ровно то, что лежит в эталонной копии, и его размеры и
хеши сходятся с тем, что приходит; Range с If-Range докачивает тот же файл,
а не склеивает две версии; два загрузчика разом получают каждый своё;
изменённый файл не отдаётся по старой строке, а манифест пересобирается;
паки (файлы подряд, без архива) режутся по размерам из манифеста в те же
файлы, и докачка внутри пака проходит через границу файлов; старый манифест
texts.xml остаётся каким был. Без LAVA_CLIENT_DIST оба адреса
отвечают 404. Клиент не нужен: эталонная копия собирается во временной папке.

    python3 server/test_client_dist.py
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["LAVA_DB"] = os.path.join(TMP, "dist.db")

sys.path.insert(0, HERE)
import client_dist  # noqa: E402
import testkit  # noqa: E402
from testkit import check, fails  # noqa: E402


def make_tree(root, files):
    for rel, data in files.items():
        full = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(data)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# --- ranges, in process -------------------------------------------------------
pr = client_dist.parse_range
check("range: open end runs to the last byte", pr("bytes=100-", 1000), (100, 999))
check("range: closed range as asked", pr("bytes=0-99", 1000), (0, 99))
check("range: an end past the file is cut to it", pr("bytes=900-5000", 1000),
      (900, 999))
check("range: suffix form takes the tail", pr("bytes=-10", 1000), (990, 999))
check("range: start at the size is unsatisfiable", pr("bytes=1000-", 1000), "bad")
check("range: several ranges get the whole file", pr("bytes=0-1,5-6", 1000), None)
check("range: another unit gets the whole file", pr("items=0-1", 1000), None)

# --- scan and its cache, in process -------------------------------------------
src = os.path.join(TMP, "scan")
make_tree(src, {"main.swf": b"swf", "a/b c.xml": b"xml", ".git/x": b"no",
                "main.swf.orig": b"no", "a/Thumbs.db": b"no"})
cache = os.path.join(TMP, "scan.cache.json")
first = client_dist.scan(src, cache)
check("scan: listed what a player needs, and nothing else",
      list(first), ["a/b c.xml", "main.swf"])
check("scan: digests are of the contents", first["main.swf"][2], sha(b"swf"))
# A cached row that matches size and mtime is taken as it is: that is what
# saves rehashing 2 GB on every start. Prove it by planting a wrong digest.
with open(cache, encoding="utf-8") as fh:
    rows = json.load(fh)
rows["main.swf"][2] = "planted"
with open(cache, "w", encoding="utf-8") as fh:
    json.dump(rows, fh)
check("scan: an unchanged file is not hashed again",
      client_dist.scan(src, cache)["main.swf"][2], "planted")
make_tree(src, {"main.swf": b"swf2"})
again = client_dist.scan(src, cache)
check("scan: a changed file is hashed again", again["main.swf"][2], sha(b"swf2"))
v1 = json.loads(client_dist.document(first)[0])["version"]
v2 = json.loads(client_dist.document(again)[0])["version"]
check("version follows the files", v1 != v2, True)
check("a version given is the version", json.loads(
    client_dist.document(again, "2026.10")[0])["version"], "2026.10")
rows3 = {"a": (40, 0, "x"), "b": (40, 0, "y"), "c": (100, 0, "z"),
         "d": (10, 0, "w")}
check("packs: consecutive rows up to the limit, a big file on its own",
      [(r, n) for _id, r, n in client_dist.packs(rows3, 90)],
      [(["a", "b"], 80), (["c"], 100), (["d"], 10)])

# --- the server ---------------------------------------------------------------
def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(extra):
    port = free_port()
    env = dict(os.environ, LAVA_HTTP_PORT=str(port),
               LAVA_DB=os.path.join(TMP, "dist.db"), **extra)
    env.pop("LAVA_HTTP_RES", None)
    if "LAVA_CLIENT_DIST" not in extra:
        env.pop("LAVA_CLIENT_DIST", None)
    p = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                         env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    log = []
    threading.Thread(target=lambda: log.extend(p.stdout), daemon=True).start()
    base = "http://127.0.0.1:%d" % port
    end = time.time() + testkit.START_WAIT
    while time.time() < end:
        try:
            urllib.request.urlopen(base + "/", timeout=1).read()
            return p, base, log
        except urllib.error.URLError:
            time.sleep(0.1)
    raise SystemExit("bootstrap http did not start")


def req(url, method="GET", headers=None):
    """(status, headers, body) without raising on 4xx/5xx."""
    rq = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        r = urllib.request.urlopen(rq, timeout=30)
        return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


ref = os.path.join(TMP, "ref")
big = os.urandom(3 * (1 << 20) + 12345)
files = {"main.swf": big,
         "locations/libs/Arena.swf": os.urandom(50000),
         "locations/libs/Vadihalfa port.swf": os.urandom(70000),
         "xml/texts.xml": "строки".encode("utf-8"),
         "empty.swf": b""}
make_tree(ref, dict(files, **{".hidden": b"x", "main.swf.orig": b"x"}))

servers = []
try:
    # One megabyte packs: main.swf is a pack of its own, the rest share one.
    srv, base, log = start({"LAVA_CLIENT_DIST": ref,
                            "LAVA_CLIENT_PACK_MB": "1",
                            "LAVA_CLIENT_CACHE": os.path.join(TMP, "c.json")})
    servers.append(srv)
    url_m = base + client_dist.MANIFEST_URL
    end = time.time() + 30
    while True:
        code, _h, body = req(url_m)
        if code != 503 or time.time() > end:
            break
        time.sleep(0.1)
    check("manifest: answers, res serving off", code, 200)
    man = json.loads(body)
    rows = {f["path"]: f for f in man["files"]}
    check("manifest: exactly the reference copy", sorted(rows), sorted(files))
    check("manifest: total size", man["size"], sum(map(len, files.values())))

    code, h, gz = req(url_m, headers={"Accept-Encoding": "gzip"})
    import gzip
    check("manifest: gzipped on request, the same document",
          (h.get("Content-Encoding"), gzip.decompress(gz)), ("gzip", body))

    def file_url(rel):
        return base + man["base"] + quote(rel)

    # --- every file as the manifest promises it ---------------------------
    for rel, data in files.items():
        code, h, got = req(file_url(rel))
        check("file %s: arrives" % rel, code, 200)
        check("file %s: size as listed" % rel, len(got), rows[rel]["size"])
        check("file %s: digest as listed" % rel, sha(got), rows[rel]["sha256"])
        check("file %s: header digest" % rel, h.get("X-Lava-Sha256"),
              rows[rel]["sha256"])
    code, h, got = req(file_url("main.swf"), "HEAD")
    check("HEAD: length without the body",
          (code, h.get("Content-Length"), got), (200, str(len(big)), b""))

    # --- resume -----------------------------------------------------------
    etag = '"%s"' % rows["main.swf"]["sha256"]
    cut = 1 << 20
    _c, _h, head = req(file_url("main.swf"), headers={"Range": "bytes=0-%d" % (cut - 1)})
    code, h, tail = req(file_url("main.swf"),
                        headers={"Range": "bytes=%d-" % cut, "If-Range": etag})
    check("resume: partial content", code, 206)
    check("resume: says which bytes", h.get("Content-Range"),
          "bytes %d-%d/%d" % (cut, len(big) - 1, len(big)))
    check("resume: head and tail make the file", sha(head + tail),
          rows["main.swf"]["sha256"])
    code, _h, whole = req(file_url("main.swf"),
                          headers={"Range": "bytes=%d-" % cut,
                                   "If-Range": '"another version"'})
    check("resume: a different version gets the whole file, not a tail",
          (code, len(whole)), (200, len(big)))
    code, h, _b = req(file_url("main.swf"),
                      headers={"Range": "bytes=%d-" % len(big)})
    check("resume: past the end is 416 with the size",
          (code, h.get("Content-Range")), (416, "bytes */%d" % len(big)))

    # --- packs: the files back to back -----------------------------------
    order = [f["path"] for f in man["files"]]
    check("packs: cover every file once, in order",
          [i for p in man["packs"] for i in range(p["first"], p["first"] + p["count"])],
          list(range(len(order))))
    pieces = {}
    for p in man["packs"]:
        url = base + man["pack_base"] + p["id"]
        code, _h, blob = req(url)
        check("pack %s: arrives whole" % p["id"], (code, len(blob)), (200, p["size"]))
        if p["count"] > 1:
            # Resume from inside the first file, across into the next ones.
            cut = rows[order[p["first"]]]["size"] // 2
            code, _h, tail = req(url, headers={"Range": "bytes=%d-" % cut,
                                               "If-Range": '"%s"' % p["id"]})
            check("pack %s: resumes across a file boundary" % p["id"],
                  (code, blob[:cut] + tail == blob), (206, True))
        pos = 0
        for rel in order[p["first"]:p["first"] + p["count"]]:
            n = rows[rel]["size"]
            pieces[rel] = sha(blob[pos:pos + n])
            pos += n
    check("packs: cut by the manifest sizes they are the files",
          pieces, {rel: rows[rel]["sha256"] for rel in order})
    check("packs: more than one, so the cutting was tested",
          len(man["packs"]) > 1, True)

    # --- two launchers at once --------------------------------------------
    got = {}

    def fetch(name, step):
        parts, pos = [], 0
        while pos < len(big):
            _c, _h, b = req(file_url("main.swf"), headers={
                "Range": "bytes=%d-%d" % (pos, pos + step - 1)})
            parts.append(b)
            pos += step
        got[name] = sha(b"".join(parts))
    ts = [threading.Thread(target=fetch, args=(n, s))
          for n, s in (("a", 200000), ("b", 333333))]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=60)
    check("two launchers at once: each gets the file",
          got, {"a": rows["main.swf"]["sha256"], "b": rows["main.swf"]["sha256"]})

    # --- nothing else is in reach -----------------------------------------
    for rel in (".hidden", "main.swf.orig", "../dist.db", "xml/../../dist.db",
                "missing.swf"):
        check("not listed, not served: %s" % rel, req(file_url(rel))[0], 404)

    # --- the old launcher's manifest --------------------------------------
    code, _h, old = req(base + "/exe/lavaclient/manifest")
    first_sha = re.search(r'"sha256"\s*:\s*"([0-9a-f]+)"', old.decode())
    _c, _h, table = req(base + "/exe/lavaclient/texts.xml")
    check("old manifest: still the string table first",
          (code, first_sha and first_sha.group(1)), (200, sha(table)))

    # --- a file changed under the server ----------------------------------
    new = b"patched main.swf"
    make_tree(ref, {"main.swf": new})
    code, _h, _b = req(file_url("main.swf"))
    check("changed file: not served by the old row", code, 503)
    end = time.time() + 30
    while time.time() < end:
        m2 = json.loads(req(url_m)[2])
        if m2["version"] != man["version"]:
            break
        time.sleep(0.1)
    row2 = {f["path"]: f for f in m2["files"]}["main.swf"]
    check("changed file: the manifest moves to it",
          (m2["version"] != man["version"], row2["sha256"]), (True, sha(new)))
    check("changed file: and it is served", sha(req(file_url("main.swf"))[2]),
          sha(new))
    old_pack = [p["id"] for p in man["packs"] if p["first"] == order.index("main.swf")][0]
    check("changed file: the pack that held it is gone",
          req(base + man["pack_base"] + old_pack)[0], 404)

    # --- off by default ---------------------------------------------------
    srv2, base2, _log2 = start({})
    servers.append(srv2)
    check("off: no manifest", req(base2 + client_dist.MANIFEST_URL)[0], 404)
    check("off: no files",
          req(base2 + client_dist.FILES_URL + "main.swf")[0], 404)
except Exception:
    import traceback
    fails.append("test crashed:\n" + traceback.format_exc())
finally:
    for p in servers:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    if servers and (fails or any("Traceback" in x for x in log)):
        fails.append("server log tail:\n" + "".join(log[-30:]))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("client dist OK")
