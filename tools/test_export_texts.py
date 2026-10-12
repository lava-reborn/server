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
# is held to it. Of the level the client shows only a shield beside the
# name, the difference from the player's own, -4 .. +4 (combat.mob_info).
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

# --- nobody a player meets goes by a level ----------------------------------
# Who the rooms stand, as well as what the table holds. A creature with no
# row of the original, the wiki or the NPC editor goes by its mobs.xml name,
# and that carries the level as well: «m510_zhivoder_lvl8» and
# «mrare_chief_lvl30» stood so in 73 and 98 until 2026-10-12
# (data/orig_names_manual.json names them now). The places: every one on the
# map's cells and every room a door, a side of data/passages.json or a quest
# way leads into from them, the camps' patrol cells (data/placements.json),
# and the camps' encounters in the wasteland (encounters.bands).
import json                                           # noqa: E402
import encounters                                     # noqa: E402
import mobs                                           # noqa: E402
import quests                                         # noqa: E402
import rooms                                          # noqa: E402
import travel                                         # noqa: E402
import world                                          # noqa: E402


def reached_from(start):
    """Every place a player gets to from start, start among them."""
    with open(travel.passages_path(), encoding="utf-8") as fh:
        sides = json.load(fh).get("sides") or {}
    seen, todo = set(start), list(start)
    while todo:
        lid = todo.pop()
        targets = [r.get("target_loc_id") for _c, r in travel.quest_ways(world.location(lid))]
        for side in "ab":
            rec = travel.door(lid, side)
            if rec and rec.get("confidence") in travel.DOOR_CONFIDENCE:
                targets.append(rec.get("target_loc_id"))
        targets += [r.get("target_loc_id") for r in (sides.get(str(lid)) or {}).values()
                    if isinstance(r, dict)]
        for t in targets:
            if t and int(t) not in seen:
                seen.add(int(t))
                todo.append(int(t))
    return seen


_MT = world.mob_types()
_places = reached_from(sorted(set(world.settlements().values())
                              | {int(k) for k in world.placements()}))
_stands = {}
for _lid in sorted(_places):
    _stands[str(_lid)] = {n.type_id for n in
                          rooms.Room(world.location(_lid), rooms.IdAllocator(), _MT).npcs.values()}
for _band, _reach in encounters.bands():
    _stands["band %d" % _band.camp] = set(_band.types)
_met = set().union(*_stands.values())
_LEVEL_IN = re.compile(r"lvl_?\d|^\s*\[\s*\d+\s*\]", re.I)
print("  places a player gets to: %d, creature types standing in them or met on the way: %d"
      % (len(_places), len(_met)))
check("the walk reaches the camps of 2026-10-12's three: «Тайная Сделка» 68, «Донгола: Живодеры»"
      " 73, «Лагерь Миротворцев» 98", {68, 73, 98} <= _places, True)
check("nobody a player meets goes by a level in his name, a mobs.xml one included",
      sorted((t, _rows.get(t)) for t in _met if _LEVEL_IN.search(_rows.get(t, ""))), [])

# A kill quest's target and a mob it does not count, in one place under one
# name at another level: with no level in the name the player cannot tell
# which to kill (the shield shows a difference clamped to -4 .. +4, the same
# for both from level 9 on). «Бандитская активность» (117) had its level-5
# Диверсант among level-4 ones; kill_also counts both since 2026-10-12.
_lv = {t: mobs.stats(t).level for t in _met}
_mixed = sorted({(q.type, aim, other, place)
                 for q in quests.QUESTS.values() if q.kind == quests.KILL_MOBS
                 for aim in q.mobs_kill
                 for place, there in _stands.items() if aim in there
                 for other in there
                 if other != aim and other not in q.mobs_kill and other not in q.kill_also
                 and names.ALL.get(other) == names.ALL.get(aim)
                 and _lv[other] != _lv[aim]})
check("no kill quest's target stands under its name beside a mob of another level it does"
      " not count", _mixed[:10], [])
check("  ..117's two Диверсанты: one name, one camp, two levels, both counted",
      (names.ALL.get(290) == names.ALL.get(291), any({290, 291} <= s for s in _stands.values()),
       (_lv[290], _lv[291]), quests.get(117).kill_also),
      (True, True, (4, 5), {290: 291}))

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
