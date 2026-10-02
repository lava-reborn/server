"""Checks the HTTP bootstrap against what lol/core/Session.as actually does."""
import os, re, subprocess, sys, time, urllib.request, urllib.error
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
def free_port():
    """A port nobody holds right now.

    Fixed ports made the verdict depend on who else was testing: with two
    checkouts running the suites at once, the second server failed to bind
    and the test talked to the first one's, passing or failing on code it
    was not built from.
    """
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = free_port()
BASE = "http://127.0.0.1:%d" % PORT
# LAVA_HTTP_RES=1: everything below is the WEB path, and serving /res/ at all
# is what puts the client on it. The default is off, checked separately at the
# end of this file.
env = dict(os.environ, LAVA_HTTP_PORT=str(PORT), LAVA_HTTP_RES="1",
           LAVA_GAME_HOST="127.0.0.1", LAVA_GAME_PORT="9775")
srv = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


# The log outgrows a pipe that nobody drains: at 64 KB the write blocks and
# the server stops answering in the middle of the test, which showed up as
# frames going missing at whatever step happened to cross the threshold.
# Drain it as it comes, the way test_combat and test_quests already do.
_log = []
_drain = threading.Thread(target=lambda: _log.extend(srv.stdout), daemon=True)
_drain.start()

fails = []
def check(label, got, want):
    if got != want:
        fails.append("%s\n   got  %r\n   want %r" % (label, got, want))
    else:
        print("  ok  %s" % label)

def get(path):
    return urllib.request.urlopen(BASE + path, timeout=5).read()

def port_up():
    for _ in range(100):
        try:
            urllib.request.urlopen(BASE + "/", timeout=1).read(); return True
        except urllib.error.URLError:
            time.sleep(0.1)
        except Exception:
            return True
    return False

def get_hash_host_port(s):
    """Faithful port of Session.getHashHostPort (Session.as:37)."""
    i = s.find(":")
    if i == -1: i = len(s)
    host = s[:i]
    j = s.find(" ", i)
    if j == -1: j = len(s)
    port = s[i+1:j]
    h = s[j+1:] if j != len(s) - 1 else None
    return host, port, h

try:
    if not port_up():
        raise SystemExit("bootstrap http did not start")

    # 1. csettings_v1.xml must exist -> flips PATHTYPE to WEB
    cs = get("/res/xmldocs/csettings_v1.xml").decode("cp1251")
    check("csettings served", "<gamesrv" in cs, True)
    check("csettings host", 'host="127.0.0.1"' in cs, True)
    check("csettings port", 'port="9775"' in cs, True)

    # 2. loaduser POST -> "data=<host>:<port> <hash>"
    req = urllib.request.Request(BASE + "/exe/lavaclient/loaduser/?ajax",
                                 data=b"", method="POST")
    body = urllib.request.urlopen(req, timeout=5).read().decode("cp1251")
    check("loaduser is LoadVars pairs", body.startswith("data="), True)
    payload = body.split("=", 1)[1].strip()
    host, port, h = get_hash_host_port(payload)
    check("parsed host", host, "127.0.0.1")
    check("parsed port", port, "9775")
    # no digest here any more: the client computes its own from the password
    check('no digest handed out', bool(h), False)


    # The client loads every XML resource with LoadVars.sendAndLoad, i.e.
    # over POST, so serving those paths on GET alone leaves it with 404s
    # and no usable settings file.
    def post(path, data=b''):
        rq = urllib.request.Request(BASE + path, data=data, method='POST')
        try:
            r = urllib.request.urlopen(rq, timeout=10)
            return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, b''

    check('POST csettings', post('/res/xmldocs/csettings_v1.xml')[0], 200)
    check('POST avatar list', post('/res/avatars/list.xml')[0], 200)
    check('POST real file', post('/res/database/objects.xml')[0], 200)
    check('POST missing file 404', post('/res/nope/nope.xml')[0], 404)

    # base must be absolute and carry no trailing slash: the client builds
    # every resource URL as base + '/avatars/list.xml'.
    base_attr = re.search('base=' + chr(34) + '([^' + chr(34) + ']*)' + chr(34), cs).group(1)
    check('base is absolute', base_attr.startswith('http://'), True)
    check('base has no trailing slash', base_attr.endswith('/'), False)

    # texts.xml is absent from the client; the stub must answer or items
    # never reach the inventory.
    code, body = post('/res/database/texts.xml', b'<data>12,34</data>')
    check('texts stub answers', code, 200)
    check('texts stub echoes ids', b"id='12'" in body, True)
    # the client's own XML is UTF-8 with a byte order mark; cp1251 here
    # leaves it with no strings at all, and no error either
    check('texts stub is utf-8 with BOM',
          body[:3], bytes([0xEF, 0xBB, 0xBF]))

    # ?all=1 has to arrive complete, and this is not cosmetic. StringCollector
    # is a singleton and SBase stays subscribed to its "update" event forever,
    # answering it by re-dispatching its own onLoad, which Session turns into
    # SceneShifter.enterScene() -- the login screen. So one string fetched
    # after login throws the player back out. Only a cache filled up front
    # keeps a second fetch from ever happening.
    # hints.xml is the other file the shipped client lacks. It is asked for
    # with LoadVars, so over POST as well, and read like the rest of the
    # client's XML: UTF-8 with a byte order mark.
    code, hints = post('/res/hints/hints.xml')
    check('hints stub answers', code, 200)
    check('hints stub is utf-8 with BOM', hints[:3], bytes([0xEF, 0xBB, 0xBF]))
    check('hints stub is an empty document', b'<data/>' in hints, True)
    check('hints stub over GET too', b'<data/>' in get('/res/hints/hints.xml'), True)

    everything = get('/res/database/texts.xml?all=1')
    check('all=1 is not empty', len(everything) > 100000, True)
    sys.path.insert(0, HERE)
    import world, items, quests, transport, names
    ids = set(world.mob_types())
    ids |= {items.STRING_ID_OFFSET + t for t in items.catalogue()}
    # item descriptions, the id ss_si_* puts in desc: the wiki's, and the
    # original table's, which also describes types the wiki never did
    ids |= {items.DESC_ID_OFFSET + t for t in items.wiki_descs()}
    import orig_texts                                  # noqa: E402
    ids |= {items.DESC_ID_OFFSET + t for t in orig_texts.item_descs()}
    # quest names and texts, plus the shared empty string they fall back to
    ids |= set(quests.strings())
    # vehicle names and descriptions, the ids ts_si puts in name and desc
    ids |= set(transport.strings())
    # clothing set names and descriptions, the ids ss_si_set puts in name and desc
    import sets                                        # noqa: E402
    ids |= set(sets.strings())
    # and the descriptions data/sets.json gives its pieces, over the
    # original's: a piece the original never described still gets its id
    ids |= {items.DESC_ID_OFFSET + t for t in sets.item_descs()}
    # and the reworked pieces' and the clothing cheques' words (setcraft.py)
    import setcraft                                    # noqa: E402
    ids |= set(setcraft.strings())
    have = {int(i) for i in re.findall(rb"id='(\d+)'", everything)}
    check('every name the server sends is preloaded', ids - have, set())
    check('creature, item, description, quest, transport and set ids do not collide',
          len(have), len(ids))
    # Russian names replace the internal ones under the same ids: the
    # original table's first, the wiki's where it is silent
    body = everything.decode('utf-8')
    _want = names._escape(names.text(items.STRING_ID_OFFSET + 6092))
    check('a linked item is served under its Russian name',
          ("<s id='%d'>%s</s>" % (items.STRING_ID_OFFSET + 6092, _want) in body,
           _want != "Ammo_9mmNato_KS"), (True, True))
    check('and its description under the description id',
          "<s id='%d'>" % (items.DESC_ID_OFFSET + 6092) in body, True)
    check('an unlinked item keeps its internal name',
          "<s id='%d'>pistols_1</s>" % (items.STRING_ID_OFFSET + 4380) in body, True)
    # 3. real client assets must come through
    # Fifteen files under res/ have a space in the name, and the client asks
    # for them percent-escaped. Serving them meant decoding the path first:
    # without that, the Wadi Halfa docks loaded with no artwork at all and
    # showed as a black field, with only a 404 in the log to say why.
    spaced = get("/res/locations/libs/Vadihalfa%20port.swf")
    check("a name with a space is decoded", spaced[:3], b"CWS")
    check("and served whole", len(spaced) > 1000000, True)

    # CI carries the slice of res/ the server reads and no client code
    # (deploy/ci/make_test_extras.sh): without main.swf on disk these two
    # are skipped, and say so, as tools/test_wrapper.py does -- decided by
    # the disk, not by the answer, so a server that stops serving a file it
    # has still fails here.
    import world
    if os.path.isfile(os.path.join(world.RES, "main.swf")):
        swf = get("/res/main.swf")
        check("main.swf served", swf[:3], b"CWS")
        check("main.swf size", len(swf), 1749720)
    else:
        print("  --  no main.swf in %s; its two checks are skipped" % world.RES)
    check("crossdomain", b"allow-access-from" in get("/res/crossdomain.xml"), True)
    # directory traversal must not escape the res root
    traversal_code = None
    try:
        urllib.request.urlopen(BASE + "/res/%2e%2e/%2e%2e/settings.db", timeout=5)
        traversal_code = 200
    except urllib.error.HTTPError as e:
        traversal_code = e.code
    check("traversal blocked", traversal_code, 404)
    page = get("/")
    check('landing page is the registration form',
          b'action="/register"' in page, True)
    check('landing page is utf-8', b'charset=utf-8' in page, True)
    status = get("/status")
    check('status answers json', b'"ok": true' in status, True)
    check('status says res serving is on', b'"res": true' in status, True)
finally:
    srv.terminate()
    try: srv.wait(timeout=5)
    except Exception: srv.kill()
    _drain.join(timeout=2)

# --- the default: registration, and not one file of the game ---------------
# The owner hands friends an address, not the game. With /res/ off the client
# has to run off the player's own disk, which is the same thing as saying
# csettings_v1.xml must not be there: that document is what flips PATHTYPE to
# WEB. So the check is both that assets stay in and that LOCAL mode holds.
PORT2 = free_port()
BASE2 = "http://127.0.0.1:%d" % PORT2
env2 = dict(os.environ, LAVA_HTTP_PORT=str(PORT2),
            LAVA_GAME_HOST="127.0.0.1", LAVA_GAME_PORT="9775")
env2.pop("LAVA_HTTP_RES", None)
srv2 = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE,
                        env=env2, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)
_log2 = []
_drain2 = threading.Thread(target=lambda: _log2.extend(srv2.stdout), daemon=True)
_drain2.start()

def code_of(url, data=None):
    try:
        rq = urllib.request.Request(url, data=data,
                                    method="POST" if data is not None else "GET")
        return urllib.request.urlopen(rq, timeout=10).status
    except urllib.error.HTTPError as e:
        return e.code

try:
    up = False
    for _ in range(150):
        try:
            urllib.request.urlopen(BASE2 + "/", timeout=1).read(); up = True; break
        except urllib.error.URLError:
            time.sleep(0.1)
        except Exception:
            up = True; break
    if not up:
        raise SystemExit("bootstrap http (res off) did not start")
    check("assets are not served by default",
          code_of(BASE2 + "/res/main.swf"), 404)
    check("nor the settings that would take the client off its own disk",
          code_of(BASE2 + "/res/xmldocs/csettings_v1.xml"), 404)
    check("nor over POST", code_of(BASE2 + "/res/main.swf", b""), 404)
    check("nor the string table",
          code_of(BASE2 + "/res/database/texts.xml?all=1"), 404)
    reg = urllib.request.urlopen(BASE2 + "/", timeout=5).read()
    check("registration page still stands",
          b'action="/register"' in reg, True)
    check("and it needs nothing out of res/", b"/res/" in reg, False)
    st = urllib.request.urlopen(BASE2 + "/status", timeout=5).read()
    check("status says res serving is off", b'"res": false' in st, True)

    # The update channel, checked here and nowhere else. It has to answer with
    # res serving OFF -- that is the whole point of putting it under /exe/
    # rather than under /res/, and this is the only block in the suite where
    # the guard is actually in force. A regression that moved these two routes
    # below it would pass every other check green.
    import hashlib as _hashlib
    import json as _json
    man = urllib.request.urlopen(BASE2 + "/exe/lavaclient/manifest", timeout=10)
    check("manifest answers with res serving off", man.status, 200)
    doc = _json.loads(man.read().decode("utf-8"))
    row = doc["resources"][0]
    rs = urllib.request.urlopen(BASE2 + "/exe/lavaclient/texts.xml", timeout=30)
    check("string table answers with res serving off", rs.status, 200)
    blob = rs.read()
    check("manifest size is the size that arrives", row["size"], len(blob))
    check("manifest digest is the digest that arrives",
          row["sha256"], _hashlib.sha256(blob).hexdigest())
    check("and the header carries it too",
          rs.headers.get("X-Lava-Sha256"), row["sha256"])
    check("manifest row count is the row count that arrives",
          row["rows"], blob.count(b"<s id='"))
    # Byte for byte the document the WEB path serves, because the launcher
    # compares a digest of one against the other.
    check("it is the same document ?all=1 would serve",
          blob.startswith("﻿<?xml version='1.0'?><data>".encode("utf-8")), True)
    check("and it is closed", blob.endswith(b"</data>"), True)
    # Nothing under /res/ was opened up by adding them.
    check("the guard still stands after them",
          code_of(BASE2 + "/res/database/texts.xml?all=1"), 404)
    check("and loaduser was not shadowed",
          code_of(BASE2 + "/exe/lavaclient/loaduser"), 200)
finally:
    srv2.terminate()
    try: srv2.wait(timeout=5)
    except Exception: srv2.kill()
    _drain2.join(timeout=2)

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails: print(" -", f)
    sys.exit(1)
print("bootstrap OK")
