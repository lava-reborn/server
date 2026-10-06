"""Real Flash and server: the map keeps its mask after location-to-location moves.

A quest way, a caravan or /goto takes the player from one location straight
into another, and SceneShifter.locationScene replaces the panel "lp" on the
same depth in one call. Flash then stops clipping the new map to its mask
and the map covers the chat; through the global map it does not happen.
The client runs against a server of its own with a fresh database and moves
102 -> 41 -> 102 -> 41 with /goto, the window resized on the way. After every
move the rendered location frame must stay empty outside its mask, and the
camera must still scroll. The control is the same widescreen client without
the SceneShifter.locationScene wrapper; the bare original does not lose
its mask on these moves.
Set LAVA_FLASH_PLAYER to a standalone Flash projector and LAVA_RES to the
client resources; without them, or off Windows, the suite skips. It never
touches a game server or account other than its own.
"""
import ast
import ctypes
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
sys.path.insert(0, str(SERVER))
from testkit import check, fails
import widescreen as w

PLAYER = os.environ.get("LAVA_FLASH_PLAYER", "")
RES = Path(os.environ.get("LAVA_RES", ""))
SRC = RES / "main.swf.orig" if (RES / "main.swf.orig").is_file() else RES / "main.swf"
# Report ticks (one a second) at which the probe sends a /goto; the window
# is resized between the first and the second move.
MOVES = {14: 41, 26: 102, 38: 41}
RESIZE_AT, SCROLL_AT, LAST = 22, 48, 50


def probe(url):
    """Once a second: report the location and three pixels of the frame."""
    a = w.Asm()
    a.var("_root").push("tick").var("_root").member("tick").push(1).op("add2").op("setmember")
    a.push("r")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    a.push("m", 0).var("lol").member("core", "Master").push("getInstance").op("callmethod").op("definelocal")
    a.push("frame").var("lol").member("core", "SceneShifter", "locationScreen", "locationFrame").op("definelocal")
    for tick, loc in MOVES.items():
        a.var("_root").member("tick").push(tick).op("equals2").op("not").iftrue("move%d" % tick)
        a.push("message")
        w.new(a, ["_global"], "Object", 0).op("definelocal")
        a.var("message").push("group", 0).op("setmember")
        a.var("message").push("mess", "/goto %d" % loc).op("setmember")
        a.var("message").push(1).var("m").member("chat").push("sendMessage").op("callmethod").op("pop")
        a.label("move%d" % tick)
    a.var("_root").member("tick").push(SCROLL_AT).op("equals2").op("not").iftrue("noscroll")
    a.var("r").push("before_scroll").var("frame").member("cont_mc", "_y").op("setmember")
    # One way may already be at the edge of the map; try both.
    a.push(-120)
    w.call_method(a, "frame", "scrollY", 1)
    a.var("r").push("up_scroll").var("frame").member("cont_mc", "_y").op("setmember")
    a.push(240)
    w.call_method(a, "frame", "scrollY", 1)
    a.var("r").push("down_scroll").var("frame").member("cont_mc", "_y").op("setmember")
    a.label("noscroll")
    a.var("r").push("tick").var("_root").member("tick").op("setmember")
    a.var("r").push("state").var("m").member("currentState").op("setmember")
    a.var("r").push("loc").var("m").member("currentLocation", "locInfo", "locID").op("setmember")
    a.var("r").push("stage_w").var("Stage").member("width").op("setmember")
    a.var("frame").op("not").iftrue("send")
    a.push("bitmap", 0, True, 1400, 2400)
    w.new(a, ["flash", "display"], "BitmapData", 4).op("definelocal")
    a.var("frame")
    w.call_method(a, "bitmap", "draw", 1)
    a.var("r").push("inside").push(100, 100, 2).var("bitmap").push("getPixel32").op("callmethod").op("setmember")
    a.var("r").push("below")
    a.var("frame").member("mask_mc", "_height").push(40).op("add2")
    a.push(100, 2).var("bitmap").push("getPixel32").op("callmethod").op("setmember")
    a.var("r").push("right").push(100)
    a.var("frame").member("mask_mc", "_width").push(40).op("add2")
    a.push(2).var("bitmap").push("getPixel32").op("callmethod").op("setmember")
    w.call_method(a, "bitmap", "dispose", 0)
    a.label("send")
    a.push("POST").var("r").push(url)
    w.call_method(a, "r", "sendAndLoad", 3)
    # The character is activated once, after its info arrives.
    a.var("_root").member("activated").iftrue("out")
    a.var("m").member("gamer", "playerInfo", "name").op("not").iftrue("out")
    a.var("m").member("persGen", "xmlInfoLoaded").op("not").iftrue("out")
    a.var("_root").push("activated", True).op("setmember")
    a.push(0).var("m").member("persGen").push("activatePlayer").op("callmethod").op("pop")
    a.label("out")
    return a


def resize(pid, width, height):
    user32 = ctypes.windll.user32
    found = []
    visit = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @visit
    def each(hwnd, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            found.append(hwnd)
        return True
    user32.EnumWindows(each, 0)
    for hwnd in found:
        outer, inner = (ctypes.c_long * 4)(), (ctypes.c_long * 4)()
        user32.GetWindowRect(ctypes.c_void_p(hwnd), outer)
        user32.GetClientRect(ctypes.c_void_p(hwnd), inner)
        if outer[2] - outer[0] > 500:
            user32.SetWindowPos(ctypes.c_void_p(hwnd), 0, 0, 0,
                                width + outer[2] - outer[0] - inner[2],
                                height + outer[3] - outer[1] - inner[3], 0x16)


def run(patched):
    import accounts
    work = Path(tempfile.mkdtemp(prefix="lava_transition_"))
    store = accounts.Store(str(work / "lava.db"))
    aid, _ = store.register("probe", "probe-password")
    store.create_character(aid, "Probe", 0, 1, home=(102, 5965, 1728))
    store.close()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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
    remask = w.fn_location_scene
    if not patched:
        # The rest of the widescreen client: without it the original keeps
        # its mask through the same moves, so it cannot be the control.
        def passthrough():
            a = w.Asm()
            w.call_method(a, "this", "__wideSceneOrig", 0)
            return a
        w.fn_location_scene = passthrough
    try:
        tags = w.inject(tags)
    finally:
        w.fn_location_scene = remask
    code = w.Asm()
    code.var("_root").push("tick", 0).op("setmember")
    code.var("_global").push("__transitionProbe").function((), probe(url + "/report")).op("setmember")
    code.push(1000, "__transitionProbe").var("_global").push(3, "setInterval").op("callfunc").op("pop").op("end")
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
        resized = [False, False]
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(.2)
            tick = int(reports[-1].get("tick", 0)) if reports else 0
            if not resized[0] and reports:
                resize(player.pid, 1920, 1080)
                resized[0] = True
            if not resized[1] and tick >= RESIZE_AT:
                resize(player.pid, 1600, 900)
                resized[1] = True
            if tick >= LAST:
                break
        return reports
    finally:
        player.terminate()
        player.wait(timeout=5)
        server.terminate()
        server.wait(timeout=5)
        http.shutdown()
        http.server_close()
        log.close()


def settled(reports):
    """For each location visited in turn, its report from just before the next move."""
    starts = sorted(MOVES) + [LAST + 1]
    out = []
    for begin, end in zip([0] + starts[:-1], starts):
        rows = [r for r in reports if begin < int(r.get("tick", 0)) < end and "below" in r]
        if rows:
            out.append(rows[-1])
    return out


# --- moves between locations, without the global map ---------------------
try:
    if PLAYER and SRC.is_file() and os.name == "nt":
        before = settled(run(False))
        check("without the wrapper a direct move leaves the map unclipped (regression reproduced)",
              any(int(r["below"]) != 0 for r in before[1:]), True)
        after = run(True)
        rows = settled(after)
        check("the moves arrive in turn", [r.get("loc") for r in rows], ["102", "41", "102", "41"])
        for i, r in enumerate(rows):
            check("stop %d (location %s): the map is drawn inside the mask" % (i, r.get("loc")),
                  int(r["inside"]) & 0xFF000000 != 0, True)
            check("stop %d (location %s): nothing is drawn below or right of the mask" % (i, r.get("loc")),
                  (int(r["below"]), int(r["right"])), (0, 0))
        check("the second size reached the client", rows[-1].get("stage_w"), "1600")
        scroll = next((r for r in after if "down_scroll" in r), {})
        check("the camera still scrolls after the moves",
              len({scroll.get(k) for k in ("before_scroll", "up_scroll", "down_scroll")}) > 1, True)
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES on Windows for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash transition probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("location transition OK")
