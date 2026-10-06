"""Real Flash: the old site's links are gone or point to the new forum.

The shipped location and global map panels and the help menu, with their
own methods: «Пополнить счет» is hidden after a resize, the session's one
hint at it gives way to the help hint, and both «Форум» buttons open the
new forum. getURL is replaced on the instances, so no browser opens.
The unpatched client is the control.
Set LAVA_FLASH_PLAYER to a standalone Flash projector and LAVA_RES to the
client resources; without either the suite skips.
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
SRC = Path(os.environ.get("LAVA_RES", "")) / "main.swf.orig"
if not SRC.is_file():
    SRC = Path(os.environ.get("LAVA_RES", "")) / "main.swf"


def field(a, key, *path):
    a.var("report").push(key).var(path[0]).member(*path[1:]).op("setmember")


def probe(url):
    a = w.Asm()
    a.push("report")
    w.new(a, ["_global"], "LoadVars", 0).op("definelocal")
    # getURL stand-in: remember the address on the report.
    record = w.Asm()
    record.var("_global").member("__siteReport").var("this").member("__key").var("url")
    record.op("setmember")
    a.var("_global").push("__siteReport").var("report").op("setmember")
    for depth, (key, link) in enumerate((("loc", "locationPanel"), ("map", "globalMapPanel"),
                                         ("help", "helpDropList")), 3):
        a.push(key, depth, key, link, 3).var("_root").push("attachMovie").op("callmethod")
        a.op("definelocal")
        a.var(key).push("__key", "url_" + key).op("setmember")
        a.var(key).push("getURL").function(("url", "window"), record).op("setmember")
    for key in ("loc", "map"):
        a.push("size")
        w.new(a, ["_global"], "Object", 0).op("definelocal")
        a.var("size").push("w", 1920).op("setmember")
        a.var("size").push("h", 1080).op("setmember")
        a.var("size")
        w.call_method(a, key, "resizeStage", 1)
        field(a, key + "_gold_visible", key, "frame_top", "gold_btn", "_visible")
        w.call_method(a, key, "goToForum", 0)
        # The hint at the button, once a session: the help hint instead.
        a.var(key).push("showHelpTooltip").function((), _help_hint(key)).op("setmember")
        a.var("lol").member("core", "SceneShifter", "_ref").push("addGoldTooltip_bool", True).op("setmember")
        w.call_method(a, key, "showTooltip", 0)
        field(a, key + "_flag_after", "lol", "core", "SceneShifter", "_ref", "addGoldTooltip_bool")
    w.call_method(a, "help", "forum", 0)
    a.push("POST").var("report").push(url)
    w.call_method(a, "report", "sendAndLoad", 3)
    a.op("end")
    return a.assemble()


def _help_hint(key):
    body = w.Asm()
    body.var("_global").member("__siteReport").push(key + "_help_hint", "shown").op("setmember")
    return body


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
    process = worker = None
    try:
        url = "http://127.0.0.1:%d" % server.server_port
        version, body = w.read_swf(SRC)
        tags = w.split_tags(body)
        if SRC.name == "main.swf":
            tags = [t for t in tags if t[0] not in (12, 26)]
        if patched:
            tags = w.inject(tags)
        at = next(i for i, t in enumerate(tags) if t[0] == 1)
        tags.insert(at, (12, probe(url + "/report"), True))
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
            raise RuntimeError("Flash did not return the site links probe")
        return {k: v[0] for k, v in reports[0].items()}
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=5)
        if worker is not None:
            server.shutdown()
            worker.join(timeout=5)
        server.server_close()


# --- the shipped panels, before and after the patch ------------------------
try:
    if PLAYER and SRC.is_file():
        before = run_flash(False)
        check("unpatched: the bottom bar's forum is the old site",
              before.get("url_loc"), "http://www.lava-online.ru/forum/")
        after = run_flash(True)
        for key, where in (("loc", "location"), ("map", "global map")):
            check("%s: «Пополнить счет» is hidden" % where, after.get(key + "_gold_visible"), "false")
            check("%s: «Форум» opens the new forum" % where, after.get("url_" + key), w.FORUM_URL)
            check("%s: the help hint comes instead of the top-up hint, once" % where,
                  (after.get(key + "_help_hint"), after.get(key + "_flag_after")), ("shown", "false"))
        check("the help menu's «Форум» opens the new forum", after.get("url_help"), w.FORUM_URL)
    else:
        print("  --  set LAVA_FLASH_PLAYER and LAVA_RES for real Flash checks")
except Exception:
    import traceback
    fails.append("Flash site links probe failed:\n" + traceback.format_exc())

if fails:
    for failure in fails:
        print("FAILED: " + failure)
    sys.exit(1)
print("site links OK")
