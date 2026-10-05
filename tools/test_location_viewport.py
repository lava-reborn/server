"""Real Flash: small maps stay centered, large maps stay inside their bounds.

Uses the shipped locationFrame symbol and its actual ViewFrame methods,
including mask rendering. The unpatched client is a regression control.
Set LAVA_FLASH_PLAYER to a standalone Flash projector and LAVA_RES to the
client resources. Without either asset this optional runtime suite skips;
test_widescreen still validates generated code and SWF containers in CI.
The projector runs hidden, serves only a synthetic scene on localhost and
never connects to the game or accesses accounts.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "server"))
from testkit import check, fails
import widescreen as w

PLAYER = os.environ.get("LAVA_FLASH_PLAYER", "")
SRC = Path(os.environ.get("LAVA_RES", "")) / "main.swf"


def rectangle(a, clip, width, height):
    a.push(100, 0x00FF00)
    w.call_method(a, clip, "beginFill", 2)
    for x, y in ((0, 0), (width, 0), (width, height), (0, height), (0, 0)):
        a.push(y, x)
        w.call_method(a, clip, "lineTo", 2)
    w.call_method(a, clip, "endFill", 0)


def field(a, key, var, *members):
    a.var("report").push(key).var(var).member(*members).op("setmember")


def pixel(a, key, x, y):
    a.var("report").push(key).push(y, x, 2).var("bitmap")
    a.push("getPixel32").op("callmethod").op("setmember")


def probe(url):
    a = w.Asm()
    a.push("report")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    a.push("frame", 1, "locationFrame", "locationFrame", 3).var("_root")
    a.push("attachMovie").op("callmethod").op("definelocal")
    a.push("content", 0, "content", 2).var("frame").member("cont_mc")
    a.push("createEmptyMovieClip").op("callmethod").op("definelocal")
    a.var("frame").push("_content").var("content").op("setmember")
    # 528: 32x64 cells, 41: 64x128 cells; cells are 40x15 pixels.
    cases = ((1280, 960, 1856, 843), (2560, 1920, 1856, 843),
             (1280, 960, 3776, 1923), (1280, 960, 1280, 960),
             (1280, 960, 960, 500), (2560, 1920, 2496, 1163))
    for i, (mw, mh, vw, vh) in enumerate(cases):
        w.call_method(a, "content", "clear", 0)
        rectangle(a, "content", mw, mh)
        a.push(mh, mw, 0, 0)
        w.call_method(a, "frame", "setScrollArea", 4)
        a.push(vh, vw)
        w.call_method(a, "frame", "setSize", 2)
        for j, (x, y) in enumerate(((0, 0), (mw, mh), (mw / 2, mh / 2))):
            a.push(int(y), int(x))
            w.call_method(a, "frame", "_centerPoint", 2)
            for key, members in (("x", ("cont_mc", "_x")), ("y", ("cont_mc", "_y")),
                                 ("w", ("mask_mc", "_width")), ("h", ("mask_mc", "_height"))):
                field(a, "%d_%d_%s" % (i, j, key), "frame", *members)
        # Direct drag or edge scroll must apply the same constraints.
        a.push(-99999)
        w.call_method(a, "frame", "scrollX", 1)
        a.push(99999)
        w.call_method(a, "frame", "scrollY", 1)
        field(a, "%d_scroll_x" % i, "frame", "cont_mc", "_x")
        field(a, "%d_scroll_y" % i, "frame", "cont_mc", "_y")
    # Opaque margins, with the real clip mask stopping scene pixels.
    w.call_method(a, "content", "clear", 0)
    rectangle(a, "content", 1280, 960)
    a.push(960, 1280, 0, 0)
    w.call_method(a, "frame", "setScrollArea", 4)
    a.push(843, 1856)
    w.call_method(a, "frame", "setSize", 2)
    a.push(480, 640)
    w.call_method(a, "frame", "_centerPoint", 2)
    a.push(1080, 1920).var("_root").push(3, "__wideLocationBack").op("callfunc").op("pop")
    a.push("bitmap", 0, True, 1200, 2400)
    w.new(a, ["flash", "display"], "BitmapData", 4).op("definelocal")
    a.var("_root")
    w.call_method(a, "bitmap", "draw", 1)
    pixel(a, "margin", 50, 500)
    pixel(a, "inside", 500, 500)
    pixel(a, "below", 500, 850)
    pixel(a, "outside", 1950, 500)
    w.call_method(a, "bitmap", "dispose", 0)
    # Exercise the real SpriteSource.drawBitmap under the hidden library.
    a.push("library").var("lol").member("display", "SourceLibrary").op("definelocal")
    w.call_method(a, "library", "create", 0)
    field(a, "library_visible", "library", "_lib", "_visible")
    a.push("source", "probe", 1).var("library").push("getSource").op("callmethod").op("definelocal")
    a.push("source_clip").var("source").member("cont_mc").op("definelocal")
    rectangle(a, "source_clip", 20, 20)
    a.push("bitmap", 0).var("source").push("drawBitmap").op("callmethod").op("definelocal")
    pixel(a, "hidden_source_pixel", 10, 10)
    w.call_method(a, "bitmap", "dispose", 0)
    # The chat is a sibling BELOW LocationInterface in SceneShifter.
    # Exercise the actual panel artwork and resize handler, then scroll its
    # map all the way down. Backing or resource clips must not cover chat.
    w.call_method(a, "frame", "removeMovieClip", 0)
    a.push(0).var('_root').member('__wideLocationBack').push('removeMovieClip').op('callmethod').op('pop')
    a.push('chat', 0, 'chat', 2).var('_root').push('createEmptyMovieClip').op('callmethod').op('definelocal')
    rectangle(a, 'chat', 1920, 144)
    a.var('chat').push('_y', 936).op('setmember')
    a.push('ui', 3, 'ui', 'locationPanel', 3).var('_root').push('attachMovie').op('callmethod').op('definelocal')
    a.push('size'); w.new(a, ['_global'], 'Object', 0).op('definelocal')
    a.var('size').push('w', 1920).op('setmember')
    a.var('size').push('h', 1080).op('setmember')
    a.var('size'); w.call_method(a, 'ui', 'resizeStage', 1)
    a.push('frame').var('ui').member('locationFrame').op('definelocal')
    a.push('content', 0, 'content', 2).var('frame').member('cont_mc').push('createEmptyMovieClip').op('callmethod').op('definelocal')
    a.var('frame').push('_content').var('content').op('setmember')
    rectangle(a, 'content', 2560, 1920)
    a.push(1920, 2560, 0, 0); w.call_method(a, 'frame', 'setScrollArea', 4)
    a.push(-99999); w.call_method(a, 'frame', 'scrollY', 1)
    field(a, 'chat_y_after_scroll', 'chat', '_y')
    field(a, 'ui_y_after_scroll', 'ui', '_y')
    a.push('bitmap', 0, True, 1200, 2400)
    w.new(a, ['flash', 'display'], 'BitmapData', 4).op('definelocal')
    a.var('_root'); w.call_method(a, 'bitmap', 'draw', 1)
    pixel(a, 'chat_pixel_after_scroll', 1000, 1000)
    a.push("POST").var("report").push(url)
    w.call_method(a, "report", "sendAndLoad", 3)
    a.op("end")
    return a.assemble(), cases


def run_flash(patched):
    received, reports = threading.Event(), []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(movie if self.path == "/probe.swf" else b"")

        def do_POST(self):
            reports.append(parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode()))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok=1")
            received.set()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    process = None
    worker = None
    try:
        url = "http://127.0.0.1:%d" % server.server_port
        code, cases = probe(url + "/report")
        version, body = w.read_swf(SRC)
        tags = [t for t in w.split_tags(body) if t[0] not in (12, 26)]
        if patched:
            tags = w.inject(tags)
        at = next(i for i, t in enumerate(tags) if t[0] == 1)
        tags.insert(at, (12, code, True))
        payload = w.join_tags(body[:w.header_len(body)], tags)
        movie = b"CWS" + bytes([version]) + struct.pack("<I", len(payload) + 8) + zlib.compress(payload)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        options = {}
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
            options["startupinfo"] = startup
        process = subprocess.Popen([PLAYER, url + "/probe.swf"], **options)
        if not received.wait(20):
            raise RuntimeError("Flash did not return the viewport probe")
        return {k: v[0] for k, v in reports[0].items()}, cases
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=5)
        if worker is not None:
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()


# --- actual AVM1, geometry and rendered pixels -----------------------------
try:
    if PLAYER and SRC.is_file():
        before, _ = run_flash(False)
        check("unpatched airport camera exposes empty space at the map's right edge",
              float(before["0_1_x"]) < 0, True)
        after, cases = run_flash(True)
        for i, (mw, mh, _, _) in enumerate(cases):
            for j, (x, y) in enumerate(((0, 0), (mw, mh), (mw / 2, mh / 2))):
                vw, vh = (float(after["%d_%d_%s" % (i, j, k)]) for k in ("w", "h"))
                want_x = (vw - mw) / 2 if vw >= mw else max(vw - mw, min(0, vw / 2 - x))
                want_y = (vh - mh) / 2 if vh >= mh else max(vh - mh, min(0, vh / 2 - y))
                check("scene %dx%d, view %.0fx%.0f, target %d: bounded camera" % (mw, mh, vw, vh, j),
                      abs(float(after["%d_%d_x" % (i, j)]) - want_x) < .06
                      and abs(float(after["%d_%d_y" % (i, j)]) - want_y) < .06, True)
            want_x = (vw - mw) / 2 if vw >= mw else vw - mw
            want_y = (vh - mh) / 2 if vh >= mh else 0
            check("scene %d: edge scrolling cannot leave the map" % i,
                  abs(float(after["%d_scroll_x" % i]) - want_x) < .06
                  and abs(float(after["%d_scroll_y" % i]) - want_y) < .06, True)
        check("unused space hides the loader, scene pixels stop at the viewport mask",
              [int(after[k]) & 0xFFFFFFFF for k in ("margin", "inside", "below", "outside")],
              [0xFF10151B, 0xFF00FF00, 0xFF10151B, 0])
        check("the resource library is explicitly hidden", after["library_visible"], "false")
        check("SpriteSource still draws artwork from the hidden library",
              int(after["hidden_source_pixel"]) & 0xFFFFFFFF, 0xFF00FF00)
        check("scrolling the dock keeps the chat and interface anchored",
              (after['chat_y_after_scroll'], after['ui_y_after_scroll']), ('936', '0'))
        check("the actual location panel cannot cover the lower-depth chat",
              int(after['chat_pixel_after_scroll']) & 0xFFFFFFFF, 0xFF00FF00)
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash viewport probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("location viewport OK")
