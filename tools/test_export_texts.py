"""The exported texts.xml must be what the HTTP stub answers ?all=1 with.

In LOCAL mode nothing stands between the client and the file: it reads
localPath + "database/texts.xml" off the disk. So the only way to know the
export is right is to compare it with the document the WEB path serves, byte
for byte, and to check the PROTOCOL.md 9 invariant on the bytes themselves --
every id in names.ALL present, nothing else.
"""
import io
import os
import re
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
SERVER = os.path.join(ROOT, "server")
sys.path.insert(0, HERE)
sys.path.insert(0, SERVER)

import export_texts  # noqa: E402
import names  # noqa: E402

from testkit import check, fails  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


blob = export_texts.document_bytes()

check("starts with a byte order mark", blob[:3], bytes([0xEF, 0xBB, 0xBF]))
check("then the client's own declaration",
      blob[3:].startswith(b"<?xml version='1.0'?><data>"), True)
check("closed document", blob.endswith(b"</data>"), True)
missing, stray = export_texts.verify(blob)
check("every id the server may send is in the file", missing, [])
check("and nothing the server cannot send", stray, [])
check("row count matches the table",
      len(re.findall(rb"<s id='\d+'>", blob)), len(names.ALL))
# Cyrillic has to survive as UTF-8; cp1251 here is the silent failure the
# HTTP stub already had once, and the client ends up with no strings at all.
check("decodes as utf-8", isinstance(blob.decode("utf-8"), str), True)

# --- a mob by its name alone ------------------------------------------------
# The owner's word of 2026-10-12: «у мобов надо в начале убрать подписи
# уровня». Read off the bytes the player gets, for every creature type, so a
# name from any source -- mobs.xml, the wiki, the NPC editor, the original --
# is held to it. The client shows a mob's level by itself (combat.mob_info).
import orig_texts                                     # noqa: E402
_LEAD = re.compile(r"^\s*\[\s*\d+\s*\]")
_rows = {int(i): t for i, t in re.findall(r"<s id='(\d+)'>([^<]*)</s>", blob.decode("utf-8"))}
_creatures = set(names.MOB_NAMES) | set(orig_texts.person_names())
_raw = {int(t): r["name"] for t, r in orig_texts._NPCS.items()
        if r.get("kind") == "mob" and int(t) in _rows}
_in_file = sorted(t for t in _creatures if _LEAD.match(_rows.get(t, "")))
print("  creature rows in the file: %d; mobs the original names with a level in front: %d;"
      " rows in the file that start with one: %d"
      % (len(_creatures & set(_rows)), sum(1 for n in _raw.values() if _LEAD.match(n)),
         len(_in_file)))
check("no creature's name in the file starts with a level", _in_file[:10], [])
check("  ..including every mob the original wrote one for",
      sorted(t for t, n in _raw.items() if _LEAD.match(n) and _LEAD.match(_rows[t])), [])

# --- what the launcher will say -------------------------------------------
# TextsCheck.Sane refuses a whole table for a single tag it does not know, and a
# refused table leaves the player on the one he had -- whose missing ids are a
# trip back to the login screen. So every row goes through a port of its check.
import re as _re                                      # noqa: E402
refused = [i for i, v in names.ALL.items() if v and not orig_texts.launcher_ok(v)]
check("the launcher would accept every row", refused[:10], [])

# The port is only worth anything while it checks against the launcher's own
# list. Read the C# array and compare, so the two cannot drift apart unseen.
_cs = io.open(os.path.join(ROOT, "launcher", "TextsCheck.cs"), encoding="utf-8").read()
_arr = _re.search(r"ALLOWED_TAGS\s*=\s*\{(.*?)\};", _cs, _re.S).group(1)
_cs_tags = set(_re.findall(r'"([^"]*)"', _arr))
check("the Python whitelist is the launcher's", sorted(orig_texts.ALLOWED_TAGS),
      sorted(_cs_tags))

# --- the file on disk, written where the player will copy it from ----------
tmp = tempfile.mkdtemp(prefix="lava-texts-")
out = os.path.join(tmp, "sub", "texts.xml")
check("exporter exits clean", export_texts.main(["-o", out]), 0)
with open(out, "rb") as fh:
    on_disk = fh.read()
check("file on disk is the same document", on_disk, blob)

# --- and the same bytes the WEB path serves --------------------------------
port = free_port()
env = dict(os.environ, LAVA_HTTP_PORT=str(port), LAVA_HTTP_RES="1",
           LAVA_GAME_HOST="127.0.0.1", LAVA_GAME_PORT="9775")
srv = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=SERVER,
                       env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
# The log outgrows a pipe nobody drains: at 64 KB the write blocks and the
# server stops answering mid-test.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()
base = "http://127.0.0.1:%d" % port
try:
    up = False
    # As long as a suite waits for its server (server/testkit.py START_WAIT).
    end = time.time() + float(os.environ.get("LAVA_START_WAIT") or 120)
    while time.time() < end:
        try:
            urllib.request.urlopen(base + "/", timeout=1).read()
            up = True
            break
        except urllib.error.URLError:
            time.sleep(0.1)
        except Exception:
            up = True
            break
    if not up:
        raise SystemExit("bootstrap http did not start")
    served = urllib.request.urlopen(
        base + "/res/database/texts.xml?all=1", timeout=60).read()
    check("export matches what ?all=1 serves", served, blob)
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except Exception:
        srv.kill()
    _drain.join(timeout=2)

for name in (out,):
    try:
        os.remove(name)
    except OSError:
        pass

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("export_texts OK")
