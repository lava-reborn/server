"""Real Flash and server: the list of players under the online counter.

The widescreen client logs in to a server of its own beside a few bot
players, opens the list from the counter and drives it the way a player
would: an envelope prepares a private in the chat without losing the draft,
the own row's envelope is off, the cross and a click outside close it, a
player leaving updates an open list, and nothing it registers outlives it.
First in the narrowest window the client allows, then wide, then on the
global map. Pictures of the
popup go next to the report when LAVA_ONLINE_LIST_OUT names a folder.
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
OUT = os.environ.get("LAVA_ONLINE_LIST_OUT", "")
BOTS = ["Archivist", "bandit", "Ccc", "Delta", "echo", "Foxtrot", "Golf",
        "hotel", "India", "Juliet", "kilo"]
LEAVES = "Delta"
SNAP = 300, 420        # the picture's size: the counter and any popup under it
TOP = 50               # where the popup's top goes in a picture, below the counter


def asm_report(a, key, *path):
    a.var("r").push(key).var(path[0]).member(*path[1:]).op("setmember")


def probe(url):
    """Once a second; each tick number has its own step."""
    a = w.Asm()
    a.var("_root").push("tick").var("_root").member("tick").push(1).op("add2").op("setmember")
    a.push("r")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    a.push("m", 0).var("lol").member("core", "Master").push("getInstance").op("callmethod").op("definelocal")
    a.push("ui").var("lol").member("core", "SceneShifter", "_ref", "currentScene").op("definelocal")
    a.push("chat").var("lol").member("core", "SceneShifter", "chat").op("definelocal")
    a.push("p").var("ui").member("__onlineOpen").op("definelocal")
    asm_report(a, "tick", "_root", "tick")
    asm_report(a, "state", "m", "currentState")
    asm_report(a, "count", "_global", "__onlineCount")
    asm_report(a, "open", "p", "_name")
    asm_report(a, "mouse", "Mouse", "_listeners", "length")
    asm_report(a, "keys", "Key", "_listeners", "length")
    asm_report(a, "dclicks", "lol", "utils", "EMouse", "refDispatcher", "__q_onDoubleClick", "length")
    asm_report(a, "input", "chat", "chatInput", "text")
    a.var("r").push("focus").push(0).var("Selection").push("getFocus").op("callmethod").op("setmember")
    asm_report(a, "chat_y", "chat", "_y")
    asm_report(a, "stage_w", "Stage", "width")

    def at(tick, label):
        a.var("_root").member("tick").push(tick).op("equals2").op("not").iftrue(label)

    def toggle():
        a.var("ui").push(1, "__onlineToggle").op("callfunc").op("pop")
        a.push("p").var("ui").member("__onlineOpen").op("definelocal")

    def describe(prefix):
        for key, path in (("x", ("p", "_x")), ("y", ("p", "_y")), ("w", ("p", "frame", "_width")),
                          ("h", ("p", "frame", "_height")), ("bar", ("p", "pan", "vBar", "_visible")),
                          ("panel_x", ("ui", "__onlinePanel", "_x")),
                          ("panel_w", ("ui", "__onlinePanel", "_width"))):
            asm_report(a, prefix + key, *path)
        for i in range(3):
            asm_report(a, "%srow%d" % (prefix, i), "p", "pan", "_content", "r%d" % i, "t", "text")
            asm_report(a, "%senabled%d" % (prefix, i), "p", "pan", "_content", "r%d" % i, "m", "enabled")
        a.push("k", 0).op("definelocal")
        a.label(prefix + "count")
        a.var("p").member("pan", "_content").push("r").var("k").op("add2").op("getmember")
        a.push(UNDEF).op("equals2").iftrue(prefix + "counted")
        a.push("k").var("k").push(1).op("add2").op("definelocal")
        a.push(True).iftrue(prefix + "count")
        a.label(prefix + "counted")
        a.var("r").push(prefix + "rows").var("k").op("setmember")

    def snapshot(name, clip="p", top=TOP):
        # The clip at (10, top) and what surrounds it, as the stage shows it.
        a.push("bm", 0, False, SNAP[1], SNAP[0])
        w.new(a, ["flash", "display"], "BitmapData", 4).op("definelocal")
        a.push("pt", 0, 0)
        w.new(a, ["flash", "geom"], "Point", 2).op("definelocal")
        a.var("pt")
        w.call_method(a, clip, "localToGlobal", 1)
        a.push("mx").push(top).var("pt").member("y").op("subtract").push(10).var("pt").member("x")
        a.op("subtract").push(1, 0, 0, 1)
        w.new(a, ["flash", "geom"], "Matrix", 6).op("definelocal")
        a.var("mx").var("_root")
        w.call_method(a, "bm", "draw", 2)
        a.push("px", "").op("definelocal")
        a.push("yy", 0).op("definelocal")
        a.label(name + "row")
        a.push("xx", 0).op("definelocal")
        a.label(name + "pix")
        a.push("px").var("px").var("yy").var("xx").push(2).var("bm").push("getPixel").op("callmethod")
        a.op("add2").push(",").op("add2").op("definelocal")
        a.push("xx").var("xx").push(1).op("add2").op("definelocal")
        a.var("xx").push(SNAP[0]).op("less2").iftrue(name + "pix")
        a.push("yy").var("yy").push(1).op("add2").op("definelocal")
        a.var("yy").push(SNAP[1]).op("less2").iftrue(name + "row")
        a.var("r").push("picture_" + name).var("px").op("setmember")
        w.call_method(a, "bm", "dispose", 0)

    # 16: a short list (two names) fills its rows to the right edge; the
    # frame takes clicks; the location's cursor goes off and comes back.
    at(16, "s16short")
    a.push("saved").var("_global").member("__onlineNames").op("definelocal")
    a.var("_global").push("__onlineNames").push("Archivist", "Probe", 2).op("initarray").op("setmember")
    toggle()
    for key, path in (("short_row_w", ("p", "pan", "_content", "r0", "bg", "_width")),
                      ("short_mail_x", ("p", "pan", "_content", "r0", "m", "_x")),
                      ("short_bar", ("p", "pan", "vBar", "_visible")),
                      ("short_guard", ("p", "frame", "onPress"))):
        asm_report(a, key, *path)
    a.push(True).var("ui").push(2, "__onlineCursor").op("callfunc").op("pop")
    asm_report(a, "cursor_hidden", "ui", "displayLoc", "cursorManager", "sfManager", "activated")
    a.push(False).var("ui").push(2, "__onlineCursor").op("callfunc").op("pop")
    asm_report(a, "cursor_back", "ui", "displayLoc", "cursorManager", "sfManager", "activated")
    toggle()
    a.var("_global").push("__onlineNames").var("saved").op("setmember")
    a.label("s16short")
    # 18: wide by now (the runner resizes from 13 on): the counter opens the list.
    at(18, "s12")
    a.var("r").push("before_mouse").var("Mouse").member("_listeners", "length").op("setmember")
    a.var("r").push("before_keys").var("Key").member("_listeners", "length").op("setmember")
    a.var("r").push("before_dclicks").var("lol").member("utils", "EMouse", "refDispatcher",
                                                         "__q_onDoubleClick", "length").op("setmember")
    a.push("cp").var("ui").member("__onlinePanel").op("definelocal")
    asm_report(a, "panel_h", "cp", "_height")
    snapshot("closed", "cp", 10)
    a.push(0).var("ui").member("__onlinePanel").push("onRelease").op("callmethod").op("pop")
    a.push("p").var("ui").member("__onlineOpen").op("definelocal")
    describe("a_")
    a.label("s12")
    # Pictures a frame after opening, once the pane has laid itself out.
    at(19, "shot19")
    snapshot("location")
    a.label("shot19")
    # 19: a draft, then the second row's envelope.
    at(19, "s13")
    a.var("chat").member("chatInput").push("text", "hello there").op("setmember")
    a.push(0).var("p").member("pan", "_content", "r1", "m").push("onRelease").op("callmethod").op("pop")
    a.label("s13")
    # 20: the same envelope again on a private to that nick only focuses.
    at(20, "s14")
    a.var("r").push("after_first").var("chat").member("chatInput", "text").op("setmember")
    toggle()
    a.push(0).var("p").member("pan", "_content", "r1", "m").push("onRelease").op("callmethod").op("pop")
    a.label("s14")
    # 21: the own row's envelope does nothing; the cross closes.
    at(21, "s15")
    toggle()
    a.push(0).var("p").member("pan", "_content", "r0", "m").push("onRelease").op("callmethod").op("pop")
    a.var("r").push("own_kept_open").var("ui").member("__onlineOpen", "_name").op("setmember")
    a.push(0).var("p").member("x").push("onRelease").op("callmethod").op("pop")
    a.label("s15")
    # 22: a click outside (the mouse rests at the stage's corner) closes.
    at(22, "s16")
    toggle()
    a.var("r").push("watch_open").var("ui").member("__onlineOpen", "_name").op("setmember")
    a.push(0).var("p").member("__watch").push("onMouseDown").op("callmethod").op("pop")
    a.label("s16")
    # 23: open, and stay open while a bot leaves (the runner does it at 24).
    at(23, "s17")
    toggle()
    a.label("s17")
    at(27, "s21")
    describe("u_")
    toggle()
    # The chat line holds a Key listener while it has the focus (ChatPan).
    a.push(None, 1).var("Selection").push("setFocus").op("callmethod").op("pop")
    a.label("s21")
    # 28: off to the global map.
    at(28, "s22")
    w.call_method(a, "m", "changeWorld", 0)
    a.label("s22")
    at(36, "s30")
    toggle()
    describe("g_")
    a.label("s30")
    at(37, "shot37")
    snapshot("map")
    toggle()
    a.label("shot37")
    # 12: the narrowest window the client allows, as it starts (950 x 650).
    at(12, "s34")
    toggle()
    describe("n_")
    a.label("s34")
    at(13, "shot13")
    snapshot("narrow")
    toggle()
    a.label("shot13")
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


UNDEF = w.UNDEF


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


class Bot:
    """A player on a socket of its own: hello, login, a character, in."""

    def __init__(self, port, accounts, name):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        for text in ("hello;minor=2;major=0;",
                     "login;hash=@%s@;" % accounts.credential(name.lower(), "secret"),
                     "newPers;res=1;sex=0;name=@%s@;" % name, "actPlayer;", "lenter;accept=1;"):
            self.sock.sendall(text.encode("utf-8") + b"\0")
            time.sleep(.15)

    def close(self):
        self.sock.close()


def run():
    import accounts
    work = Path(tempfile.mkdtemp(prefix="lava_online_list_"))
    store = accounts.Store(str(work / "lava.db"))
    aid, _ = store.register("probe", "probe-password")
    store.create_character(aid, "Probe", 0, 1, home=(41, 5965, 1728))
    for name in BOTS:
        store.register(name.lower(), "secret")
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
    tags = w.inject(tags)
    code = w.Asm()
    code.var("_root").push("tick", 0).op("setmember")
    code.var("_global").push("__listProbe").function((), probe(url + "/report")).op("setmember")
    code.push(1000, "__listProbe").var("_global").push(3, "setInterval").op("callfunc").op("pop").op("end")
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
    bots = {}
    player = None
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(.3)
        for name in BOTS:
            bots[name] = Bot(port, accounts, name)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        player = subprocess.Popen([PLAYER, url + "/res/main.swf?logged=1&vversion=1"], startupinfo=startup)
        steps = {24: lambda: bots.pop(LEAVES).close()}
        deadline = time.time() + 120
        while time.time() < deadline:
            time.sleep(.2)
            tick = int(reports[-1].get("tick", 0)) if reports else -1
            for when in sorted(steps):
                if tick >= when:
                    steps.pop(when)()
            # A hidden projector now and then ignores a resize: ask again.
            if 13 <= tick < 18 and reports[-1].get("stage_w") != "1920":
                resize(player.pid, 1920, 1080)
            if tick >= 39:
                break
        return reports
    finally:
        if player is not None:
            player.terminate()
            player.wait(timeout=5)
        for bot in bots.values():
            bot.close()
        server.terminate()
        server.wait(timeout=5)
        http.shutdown()
        http.server_close()
        log.close()


def save(report, name):
    if not OUT or "picture_" + name not in report:
        return
    from PIL import Image
    image = Image.new("RGB", SNAP)
    image.putdata([((v >> 16) & 255, (v >> 8) & 255, v & 255)
                   for v in (int(x) for x in report["picture_" + name].split(",") if x)])
    image.save(Path(OUT) / ("online-list-%s.png" % name))


# --- the list, driven like a player --------------------------------------
try:
    if PLAYER and SRC.is_file() and os.name == "nt":
        reports = run()
        by = {int(r["tick"]): r for r in reports if r.get("tick", "").isdigit()}
        # A report reads the state at the start of its tick, before that
        # tick's step: the outcome of a step shows in the next one.
        first, second, third = by[18], by[20], by[21]
        everyone = 1 + len(BOTS)
        ordered = ["Probe (вы)"] + sorted(BOTS, key=str.casefold)[:2]
        check("the counter opens a list of everyone, own name first",
              (first["count"], first["a_rows"], [first["a_row%d" % i] for i in range(3)]),
              (str(everyone), str(everyone), ordered))
        check("the own envelope is off, the others on",
              [first["a_enabled%d" % i] for i in range(3)], ["false", "true", "true"])
        check("a long list scrolls inside a bounded popup",
              (first["a_bar"], int(float(first["a_h"])) <= 2 * 22 + 8 + 8 * 27), ("true", True))
        check("the popup hangs under the counter, plate edges aligned",
              abs(float(first["a_x"]) + float(first["a_w"]) - 8
                  - float(first["a_panel_x"]) - float(first["a_panel_w"])) <= 1, True)
        short = by[16]
        check("a short list runs its rows to the edge, envelope flush, no bar",
              (short["short_row_w"], short["short_mail_x"], short["short_bar"]),
              (str(w.LIST_ROW_W + w.LIST_BAR), str(w.LIST_ROW_W + w.LIST_BAR - 25), "false"))
        check("the popup's frame takes the clicks that miss its rows",
              short["short_guard"].startswith("[type Function]"), True)
        check("the location's cursor goes off over the popup and comes back",
              (short["cursor_hidden"], short["cursor_back"]), ("false", "true"))
        nick = sorted(BOTS, key=str.casefold)[0]
        check("an envelope closes the list and prepares a private, keeping the draft",
              (second["open"], second["input"]), ("undefined", "private %s: hello there" % nick))
        check("the chat line takes the focus",
              second["focus"].endswith("chatInput"), True)
        check("the same envelope again does not turn the private into a reply",
              third["input"], "private %s: hello there" % nick)
        check("the own envelope does nothing; the cross closes",
              (by[21]["own_kept_open"].startswith("__onlinePopup"), by[22]["open"]), (True, "undefined"))
        check("a click outside closes the list",
              (by[22]["watch_open"].startswith("__onlinePopup"), by[23]["open"]), (True, "undefined"))
        check("a player leaving updates the open list",
              (by[27]["u_rows"], LEAVES not in [by[27]["u_row%d" % i] for i in range(3)]),
              (str(everyone - 1), True))
        base = (first["before_mouse"], first["before_keys"], first["before_dclicks"])
        check("closing leaves no listener behind (Mouse, Key, double click)",
              (by[28]["mouse"], by[28]["keys"], by[28]["dclicks"]), base)
        check("the list opens on the global map",
              (by[36]["state"], by[36]["g_rows"]), ("gm", str(everyone - 1)))
        narrow = by[12]
        check("a narrow window keeps the popup on the stage and above the chat",
              (narrow["stage_w"], float(narrow["n_x"]) >= 0,
               float(narrow["n_y"]) + float(narrow["n_h"]) <= float(narrow["chat_y"])),
              ("950", True, True))
        def pixel(report, x, y, name="location"):
            v = int(report["picture_" + name].split(",")[y * SNAP[0] + x])
            return (v >> 16) & 255, (v >> 8) & 255, v & 255

        def lit(rgb):
            return min(rgb) > 140

        # The counter: the popup's plate without its shadow, 22 high, the
        # icon, a two-digit count and the arrow 33 + 20 + 3 = 56 in. The
        # arrow is five pixel rows, 10 to 2 wide, rows 9 to 13; up is the
        # same rows reversed.
        ax = 56
        width = ax + 10 + 16
        closed = lambda x, y: pixel(by[18], 10 + x, 10 + y, "closed")
        opened = lambda x, y: pixel(by[19], 10 + w.LIST_W - 8 - width + x,
                                    TOP - (w.ONLINE_H + 3 - 5) + y)
        check("the counter is the popup's dark plate, no light inset",
              [max(closed(x, 17)) < 90 for x in (5, 32, width - 5)], [True, True, True])
        check("no shadow hangs under the counter: it is exactly the plate",
              by[18]["panel_h"], str(w.ONLINE_H))
        check("the counter keeps the original people icon",
              any(lit(closed(x, y)) for x in range(14, 33) for y in range(3, 21)), True)
        check("the arrow points down while the list is closed",
              (lit(closed(ax + 2, 9)), lit(closed(ax + 2, 12))), (True, False))
        check("the arrow points up while the list is open, the same arrow mirrored",
              (lit(opened(ax + 2, 9)), lit(opened(ax + 2, 12))), (False, True))
        check("both arrows have the same pixels, mirrored",
              [lit(closed(ax + x, 11 - d)) for x in range(10) for d in range(-2, 3)],
              [lit(opened(ax + x, 11 + d)) for x in range(10) for d in range(-2, 3)])

        # The popup sits at 10,10 in the picture. The frame's left plate,
        # then the first row's face, which must be the settings rows' grey.
        plate = pixel(by[19], 10 + 14, TOP + 60)
        face = pixel(by[19], 10 + 22 + 4 + 60, TOP + 22 + 4 + 4)
        check("the frame is drawn from the settings window's dark plate",
              max(plate) < 90 and max(plate) - min(plate) < 10, True)
        check("rows have the settings rows' face", face, (0x6D, 0x6B, 0x65))
        for name in ("closed", "location", "map", "narrow"):
            save(by[{"closed": 18, "location": 19, "map": 37, "narrow": 13}[name]], name)
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES on Windows for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash online list probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("online list OK")
