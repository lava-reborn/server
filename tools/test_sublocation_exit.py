"""Client patch: no way to the global map out of a sublocation.

A mine or a cellar (Location.isSubLocation: geoID with z != 0) is left
through its door. LocationInterface.battleMode keeps the exit button off
there, but init() calls battleMode and then, as its last line, lights the
button again from gamer.prepare alone; it stays lit until the next lch;ws.
toGlobal(), behind both the button and the CHANGE_WORLD hot key, checks
only enabledExitLoc and toGMEnabled, so either sent chWorld from a mine
and the server refused it.

In process: the real bytecode of both wrappers (LocationInterface.init and
toGlobal) runs against a model of the original's init, battleMode and
toGlobal, from recon/as-src/lol/gpui/LocationInterface.as.

Real Flash (LAVA_FLASH_PLAYER and LAVA_RES, Windows): the client logs in to
a server of its own in a town (102), goes with /goto to the first
interior data/passages.json 'no_map' lists (the server tells the client
it is a sublocation, travel.geo_id), tries the exit there, comes back and
leaves for the map. Twice: the
original's init and toGlobal, and the patch as built.
"""
import ast
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import zlib

HERE = Path(__file__).resolve().parent
SERVER = HERE.parent / "server"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SERVER))
import widescreen as w  # noqa: E402
from testkit import check, fails  # noqa: E402


# --- a small AVM1 executor ---------------------------------------------------

def get(target, key):
    if target is None:
        return None
    return getattr(target, key, None)


def execute(code, env):
    """The opcodes these two wrappers use; undefined is None here."""
    stack, at = [], 0
    while at < len(code):
        op = code[at]
        at += 1
        payload = b""
        if op >= 0x80:
            size, = struct.unpack_from("<H", code, at)
            at += 2
            payload = code[at:at + size]
            at += size
        if op == 0x96:
            p = 0
            while p < len(payload):
                kind = payload[p]
                p += 1
                if kind == 0:
                    end = payload.index(b"\0", p)
                    stack.append(payload[p:end].decode())
                    p = end + 1
                elif kind == 5:
                    stack.append(bool(payload[p]))
                    p += 1
                elif kind == 7:
                    stack.append(struct.unpack_from("<i", payload, p)[0])
                    p += 4
                else:
                    raise AssertionError("unexpected push type: %s" % kind)
        elif op == 0x1C:
            stack.append(env.get(stack.pop()))
        elif op == 0x4E:
            key, target = stack.pop(), stack.pop()
            stack.append(get(target, key))
        elif op == 0x4F:
            value, key, target = stack.pop(), stack.pop(), stack.pop()
            setattr(target, key, value)
        elif op == 0x52:
            method, target, count = stack.pop(), stack.pop(), stack.pop()
            args = [stack.pop() for _ in range(count)]
            stack.append(get(target, method)(*args))
        elif op == 0x12:
            stack.append(not stack.pop())
        elif op == 0x17:
            stack.pop()
        elif op == 0x9D:
            if stack.pop():
                at += struct.unpack("<h", payload)[0]
        else:
            raise AssertionError("unexpected opcode: %02x" % op)
    if stack:
        raise AssertionError("wrapper leaked stack values: %r" % stack)


# --- the original LocationInterface, from recon/as-src/lol/gpui -------------

class Button:
    def __init__(self):
        self.enabled = True


class Location:
    def __init__(self, sub, war=0):
        self.sub, self.warStatus = sub, war

    @property
    def isSubLocation(self):            # Location.as get isSubLocation
        return self.sub


class Interface:
    def __init__(self, location, prepare, patched):
        self.currentLocation, self.exitLoc_btn = location, Button()
        self.prepare, self.enabledExitLoc, self.toGMEnabled = prepare, True, True
        self.sent = []
        setattr(self, "__subInitOrig", self.original_init)
        setattr(self, "__subGlobalOrig", self.original_toGlobal)
        if patched:
            self.init = lambda: execute(w.fn_sublocation_init().assemble(), dict(this=self))
            self.toGlobal = lambda: execute(w.fn_sublocation_global().assemble(), dict(this=self))
        else:
            self.init, self.toGlobal = self.original_init, self.original_toGlobal

    def original_init(self):            # LocationInterface.as init, the exit parts
        self.battleMode(self.currentLocation.warStatus)
        self.exitLoc_btn.enabled = not self.prepare

    def battleMode(self, ws):           # LocationInterface.as battleMode
        if ws:
            self.enabledExitLoc = False
            self.exitLoc_btn.enabled = False
        else:
            self.enabledExitLoc = True
            self.exitLoc_btn.enabled = not self.currentLocation.isSubLocation

    def original_toGlobal(self):        # LocationInterface.as toGlobal
        if self.enabledExitLoc and self.toGMEnabled:
            self.toGMEnabled = False
            self.sent.append("chWorld")


def enter(sub, prepare=False, patched=True):
    """init, then the button (or the key): (lit after init, what was sent)."""
    ui = Interface(Location(sub), prepare, patched)
    ui.init()
    lit = ui.exitLoc_btn.enabled
    ui.toGlobal()
    return lit, ui.sent


# --- in process: the wrappers' own bytecode ---------------------------------
check("original: in a mine the button is lit after init and the exit sends chWorld",
      enter(True, patched=False), (True, ["chWorld"]))
check("patched: in a mine the button is off and neither button nor key sends chWorld",
      enter(True), (False, []))
check("patched: in a town the button is lit and the exit sends chWorld, as before",
      enter(False), (True, ["chWorld"]))
check("patched: in a town while preparing the button stays off, as before",
      enter(False, prepare=True)[0], False)
check("both wraps are in the injected code",
      [n for n in ("__subInitOrig", "__subGlobalOrig") if n.encode() not in w.injected()], [])


# --- real Flash: down the mine and back --------------------------------------
PLAYER = os.environ.get("LAVA_FLASH_PLAYER", "")
RES = Path(os.environ.get("LAVA_RES", ""))
SRC = RES / "main.swf.orig" if (RES / "main.swf.orig").is_file() else RES / "main.swf"
# Ticks (one a second) from the first one in a location.
DOWN, IN_MINE, UP, IN_TOWN, DONE = 4, 12, 16, 24, 30
SUB = next(k for k in json.loads((HERE.parent / "data" / "passages.json").read_text(
    encoding="utf-8"))["no_map"] if k.isdigit())


def probe(url):
    """Once a second: the location and the exit. From the first tick in a
    location: /goto SUB at DOWN, the exit tried at IN_MINE (phase "mine"),
    /goto 102 at UP, the exit tried at IN_TOWN (phase "town"), the state
    reported at DONE (phase "done"). `sent` is toGMEnabled gone false,
    which toGlobal does right before Master.changeWorld."""
    a = w.Asm()
    a.var("_root").push("tick").var("_root").member("tick").push(1).op("add2").op("setmember")
    a.push("r")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    a.push("m", 0).var("lol").member("core", "Master").push("getInstance").op("callmethod").op("definelocal")
    a.push("ui").var("lol").member("core", "SceneShifter", "locationScreen").op("definelocal")
    a.var("r").push("tick").var("_root").member("tick").op("setmember")
    a.var("r").push("state").var("m").member("currentState").op("setmember")
    a.var("r").push("loc").var("m").member("currentLocation", "locInfo", "locID").op("setmember")
    a.var("_root").member("start").iftrue("started")
    a.var("m").member("currentState").push("loc").op("equals2").op("not").iftrue("send")
    a.var("_root").push("start").var("_root").member("tick").op("setmember")
    a.label("started")
    a.push("t").var("_root").member("tick").var("_root").member("start").op("subtract").op("definelocal")
    for at, loc in ((DOWN, int(SUB)), (UP, 102)):
        a.var("t").push(at).op("equals2").op("not").iftrue("go%d" % at)
        a.push("message")
        w.new(a, ["_global"], "Object", 0).op("definelocal")
        a.var("message").push("group", 0).op("setmember")
        a.var("message").push("mess", "/goto %d" % loc).op("setmember")
        a.var("message").push(1).var("m").member("chat").push("sendMessage").op("callmethod").op("pop")
        a.label("go%d" % at)
    for at, phase in ((IN_MINE, "mine"), (IN_TOWN, "town")):
        a.var("t").push(at).op("equals2").op("not").iftrue("try%d" % at)
        a.var("r").push("phase", phase).op("setmember")
        a.var("r").push("sub").var("m").member("currentLocation", "isSubLocation").op("setmember")
        a.var("r").push("lit").var("ui").member("exitLoc_btn", "enabled").op("setmember")
        a.var("r").push("war").var("m").member("currentLocation", "warStatus").op("setmember")
        w.call_method(a, "ui", "toGlobal", 0)
        a.var("r").push("sent").var("ui").member("toGMEnabled").op("not").op("setmember")
        a.label("try%d" % at)
    a.var("t").push(DONE).op("equals2").op("not").iftrue("send")
    a.var("r").push("phase", "done").op("setmember")
    a.label("send")
    a.push("POST").var("r").push(url)
    w.call_method(a, "r", "sendAndLoad", 3)
    a.var("_root").member("activated").iftrue("out")
    a.var("m").member("gamer", "playerInfo", "name").op("not").iftrue("out")
    a.var("m").member("persGen", "xmlInfoLoaded").op("not").iftrue("out")
    a.var("_root").push("activated", True).op("setmember")
    a.push(0).var("m").member("persGen").push("activatePlayer").op("callmethod").op("pop")
    a.label("out")
    return a


def run(patched):
    """patched: the whole patch, or with patch 12's wrappers passing through."""
    import accounts
    work = Path(tempfile.mkdtemp(prefix="lava_sublocation_"))
    store = accounts.Store(str(work / "lava.db"))
    aid, _ = store.register("probe", "probe-password")
    store.create_character(aid, "Probe", 0, 1, home=(102, 5965, 1728))
    store.close()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    tree = ast.parse((SERVER / "bootstrap_http.py").read_text(encoding="utf-8"))
    settings = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", None) == "CSETTINGS" for t in n.targets))
    reports = []

    class Handler(BaseHTTPRequestHandler):
        def serve(self):
            path = unquote(urlsplit(self.path).path)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            status = 200
            if path == "/report":
                reports.append({k: v[0] for k, v in parse_qs(body.decode()).items()})
                data = b"ok=1"
            elif path.endswith("/loaduser/"):
                data = ("data=127.0.0.1:%d %s" % (port, accounts.credential("probe", "probe-password"))).encode()
            elif path.endswith("crossdomain.xml"):
                data = b'<cross-domain-policy><allow-access-from domain="*" to-ports="*"/></cross-domain-policy>'
            elif path == "/res/main.swf":
                data = movie
            elif path.endswith("csettings_v1.xml"):
                data = settings.format(host="127.0.0.1", port=port, http_port=http.server_port).encode()
            elif path.endswith("/hints/hints.xml"):
                data = b"\xef\xbb\xbf<?xml version='1.0'?><data/>"
            elif path.startswith("/res/") and (RES / path[5:]).is_file():
                data = (RES / path[5:]).read_bytes()
            else:
                status, data = 404, b""
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        do_GET = do_POST = serve

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = "http://127.0.0.1:%d" % http.server_port
    version, body = w.read_swf(SRC)
    tags = [t for t in w.split_tags(body) if t[0] not in (12, 26)] if SRC.name == "main.swf" else w.split_tags(body)
    w.patch_ceiling(tags, 3840, 2160)
    keep = w.fn_sublocation_init, w.fn_sublocation_global

    def passthrough(orig):
        def body():
            a = w.Asm()
            a.push(0).var("this").push(orig).op("callmethod").op("pop")
            return a
        return body
    if not patched:
        w.fn_sublocation_init = passthrough("__subInitOrig")
        w.fn_sublocation_global = passthrough("__subGlobalOrig")
    try:
        tags = w.inject(tags)
    finally:
        w.fn_sublocation_init, w.fn_sublocation_global = keep
    code = w.Asm()
    code.var("_root").push("tick", 0).op("setmember")
    code.var("_global").push("__sublocationProbe").function((), probe(url + "/report")).op("setmember")
    code.push(1000, "__sublocationProbe").var("_global").push(3, "setInterval").op("callfunc").op("pop").op("end")
    at = next(i for i, t in enumerate(tags) if t[0] == 1)
    tags.insert(at, (12, code.assemble(), True))
    payload = w.join_tags(body[:w.header_len(body)], tags)
    movie = b"CWS" + bytes([version]) + struct.pack("<I", len(payload) + 8) + zlib.compress(payload)
    log = open(work / "server.log", "w", encoding="utf-8")
    env = dict(os.environ, LAVA_DB=str(work / "lava.db"), LAVA_PORT=str(port),
               LAVA_POLICY_PORT="0", LAVA_CHEATS="1", PYTHONIOENCODING="utf-8")
    server = subprocess.Popen([sys.executable, "server.py"], cwd=SERVER,
                              env=env, stdout=log, stderr=log)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    player = subprocess.Popen([PLAYER, url + "/res/main.swf?logged=1&vversion=1"], startupinfo=startup)
    try:
        deadline = time.time() + 150
        while time.time() < deadline:
            time.sleep(.2)
            if any(r.get("phase") == "done" for r in reports):
                break
        return {r["phase"]: r for r in reports if "phase" in r}
    finally:
        player.terminate()
        player.wait(timeout=5)
        server.terminate()
        server.wait(timeout=5)
        http.shutdown()
        http.server_close()
        log.close()


def walk(patched):
    phases = run(patched)
    missing = [p for p in ("mine", "town", "done") if p not in phases]
    if missing:
        raise AssertionError("patched=%s: the probe never reported %s" % (patched, missing))
    return phases["mine"], phases["town"], phases["done"]


try:
    if PLAYER and SRC.is_file() and os.name == "nt":
        mine, town, done = walk(False)
        check("Flash, original: /goto %s lands in a sublocation at peace" % SUB,
              (mine["loc"], mine["sub"], mine["war"]), (SUB, "true", "false"))
        check("Flash, original: the button is lit in the sublocation and the exit sends chWorld",
              (mine["lit"], mine["sent"]), ("true", "true"))
        mine, town, done = walk(True)
        check("Flash, patched: the button is off in the sublocation and the exit sends nothing",
              (mine["loc"], mine["sub"], mine["lit"], mine["sent"]), (SUB, "true", "false", "false"))
        check("Flash, patched: back in town the button is lit and the exit leaves for the map",
              (town["loc"], town["sub"], town["lit"], town["sent"], done["state"]),
              ("102", "false", "true", "true", "gm"))
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES on Windows for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash sublocation probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("sublocation exit OK")
