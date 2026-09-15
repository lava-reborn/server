"""Checks the HTTP bootstrap against what lol/core/Session.as actually does."""
import os, subprocess, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 18080
BASE = "http://127.0.0.1:%d" % PORT
env = dict(os.environ, LAVA_HTTP_PORT=str(PORT),
           LAVA_GAME_HOST="127.0.0.1", LAVA_GAME_PORT="9775")
srv = subprocess.Popen([sys.executable, "bootstrap_http.py"], cwd=HERE, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

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
    check("parsed hash", h, "devhash")

    # 3. real client assets must come through
    swf = get("/res/main.swf")
    check("main.swf served", swf[:3], b"CWS")
    check("main.swf size", len(swf), 1749720)
    check("crossdomain", b"allow-access-from" in get("/res/crossdomain.xml"), True)
    # directory traversal must not escape the res root
    traversal_code = None
    try:
        urllib.request.urlopen(BASE + "/res/%2e%2e/%2e%2e/settings.db", timeout=5)
        traversal_code = 200
    except urllib.error.HTTPError as e:
        traversal_code = e.code
    check("traversal blocked", traversal_code, 404)
    check("index has ruffle", b"RufflePlayer" in get("/"), True)
    check("index passes logged=1", b'logged: "1"' in get("/"), True)
finally:
    srv.terminate()
    try: srv.communicate(timeout=5)
    except Exception: srv.kill()

print()
if fails:
    print("FAILED %d:" % len(fails))
    for f in fails: print(" -", f)
    sys.exit(1)
print("bootstrap OK")
