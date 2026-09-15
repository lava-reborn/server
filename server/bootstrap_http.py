"""HTTP side of the LAVA Online bootstrap.

The client needs three things over HTTP before it will open the game socket.
All of them are reproduced here, so neither the SWF nor the hosts file has to
be touched:

  GET  /res/...                        the client's own res/ tree
  GET  /res/xmldocs/csettings_v1.xml   absent from the shipped client; serving it
                                       flips SSEmulator.PATHTYPE to WEB
  POST /exe/lavaclient/loaduser/?ajax  returns "data=<host>:<port> <hash>",
                                       parsed by Session.getHashHostPort()

Entry path (lol/core/Session.as:88): when _root.logged == 1 and PATHTYPE == WEB,
the client POSTs to the relative loaduser URL and takes host, port and login hash
straight from the reply. That bypasses the hardcoded www.lava-online.ru domain
and the game_session.php endpoint entirely.
"""
import os
import posixpath
import re
import sys

import world
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

RES_ROOT = os.environ.get(
    "LAVA_RES", r"C:\Users\gmkrt\OneDrive\Desktop\LAVA\res")
GAME_HOST = os.environ.get("LAVA_GAME_HOST", "127.0.0.1")
GAME_PORT = os.environ.get("LAVA_GAME_PORT", "9775")
HTTP_PORT = int(os.environ.get("LAVA_HTTP_PORT", "8080"))

CSETTINGS = """<?xml version="1.0" encoding="windows-1251"?>
<settings>
  <gamesrv host="{host}" port="{port}"/>
  <debug value="1"/>
  <resource base="http://{host}:{http_port}/res">
    <item_icon format="swf">classes/</item_icon>
    <item_anim format="swf">classes/</item_anim>
    <avatar_list format="xml">avatars/list.xml</avatar_list>
    <avatar format="swf">avatars/</avatar>
    <sprite format="swf">locations/libs/</sprite>
    <globalmap format="swf">globalmap/</globalmap>
    <location_info format="xml">locations/</location_info>
    <location_lib format="swf">locations/libs/</location_lib>
    <mob_anim format="swf">mobs/</mob_anim>
    <mob_info format="xml">mobs/</mob_info>
    <char_anim format="swf">personages/</char_anim>
    <char_info format="xml">personages/</char_info>
    <text format="xml">xmldocs/</text>
    <sound format="swf">sounds/</sound>
  </resource>
</settings>
"""

# The server hands out a creature's type id where a string id belongs, so the
# stub below can answer with a real name. Preference order: the names recovered
# from the community wiki, then the internal name from the client's own table,
# then the bare id.
try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}

try:
    import json
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(_here, "data", "npc_names.json"), encoding="utf-8") as _f:
        REAL_NAMES = {int(k): v for k, v in json.load(_f)["names"].items()}
except Exception:
    REAL_NAMES = {}

CTYPES = {
    ".swf": "application/x-shockwave-flash",
    ".xml": "text/xml",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".mp3": "audio/mpeg", ".txt": "text/plain",
}

CROSSDOMAIN = (
    '<?xml version="1.0"?>'
    '<cross-domain-policy><allow-access-from domain="*" to-ports="*"/>'
    "</cross-domain-policy>"
)

INDEX = """<!doctype html>
<meta charset="utf-8"><title>LAVA Online</title>
<style>html,body{{margin:0;background:#111;height:100%}}#c{{width:100%;height:100%}}</style>
<script src="ruffle/ruffle.js"></script>
<div id="c"></div>
<script>
window.RufflePlayer = window.RufflePlayer || {{}};
window.RufflePlayer.config = {{
  // Browsers cannot open raw TCP, so Ruffle tunnels the game socket through
  // websockify. On Ruffle desktop this whole block is unnecessary.
  socketProxy: [{{ host: "{host}", port: {port}, proxyUrl: "ws://127.0.0.1:9776" }}],
  autoplay: "on", unmuteOverlay: "hidden", contextMenu: "off",
}};
window.addEventListener("load", () => {{
  const player = window.RufflePlayer.newest().createPlayer();
  document.getElementById("c").appendChild(player);
  player.load({{
    url: "/res/main.swf",
    parameters: {{ logged: "1", session: "dev", vversion: "1",
                  var_host: "{host}", var_port: "{port}", var_login: "dev" }},
  }});
}});
</script>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "lava-bootstrap"

    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):
        if isinstance(body, str):
            body = body.encode("cp1251", "replace")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("  HTTP %s" % (fmt % args), flush=True)

    # --- routing ---------------------------------------------------------
    def _resource(self, path):
        """Serve a file straight out of the client's own res/ tree."""
        rel = path[len("/res/"):].replace("/", os.sep)
        full = os.path.normpath(os.path.join(RES_ROOT, rel))
        if not full.startswith(os.path.normpath(RES_ROOT)):
            self._send("forbidden", code=403)
            return
        if not os.path.isfile(full):
            self._send("not found", code=404)
            return
        ctype = CTYPES.get(os.path.splitext(full)[1].lower(),
                           "application/octet-stream")
        with open(full, "rb") as fh:
            self._send(fh.read(), ctype)

    def _texts(self, query, body):
        """Stand in for the missing res/database/texts.xml.

        Item names, quest text and NPC lines all travel as numeric string ids
        resolved through this endpoint, and the 20 MB file behind it is one of
        only two files absent from the shipped client. Until those strings are
        recovered, echo every requested id back as its own placeholder: an item
        whose name never arrives is never added to the inventory at all.
        """
        if "all=1" in (query or ""):
            self._send_xml("<data></data>")
            return
        ids = [m.decode() for m in re.findall(rb"\d+", body or b"")]
        rows = "".join(
            "<s id='%s'>%s</s>"
            % (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i), "#" + i))
            for i in ids)
        self._send_xml("<data>%s</data>" % rows)

    def _send_xml(self, body):
        """Answer the way the client's own XML files are written.

        Every file under res/ is UTF-8, most of them with a byte order mark,
        whatever their declaration claims. Sending cp1251 here, as the game
        socket uses, leaves the parser with bytes it cannot read, and the
        client quietly ends up with no strings at all rather than an error.
        """
        payload = ("﻿<?xml version='1.0'?>" + body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self, body=b""):
        parts = urlparse(self.path)
        path = posixpath.normpath(parts.path)
        if path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Session.getHashHostPort() splits the reply on ":" then " ".
            # Real Flash asks for this with GET, because LoadVars.sendAndLoad
            # downgrades to GET when the outgoing object carries no variables,
            # while Ruffle issues the POST the call actually requested. Accept
            # both.
            self._send("data=%s:%s devhash" % (GAME_HOST, GAME_PORT))
            return
        if path in ("/", "/index.html"):
            self._send(INDEX.format(host=GAME_HOST, port=GAME_PORT),
                       "text/html; charset=utf-8")
        elif path.endswith("/crossdomain.xml"):
            self._send(CROSSDOMAIN, "text/x-cross-domain-policy")
        elif path == "/res/xmldocs/csettings_v1.xml":
            self._send(CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,
                                        http_port=HTTP_PORT), "text/xml")
        elif path == "/res/database/texts.xml":
            self._texts(parts.query, body)
        elif path == "/res/hints/hints.xml":
            # never shipped with the client; an empty document satisfies it
            self._send("<data></data>", "text/xml")
        elif path.startswith("/res/"):
            self._resource(path)
        else:
            self._send("not found", code=404)

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        # The client fetches every XML resource with LoadVars.sendAndLoad,
        # which issues a POST. Only the login handshake is a POST by intent;
        # everything else must be served exactly as it would be over GET.
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self._dispatch(body)


if __name__ == "__main__":
    print("res root : %s" % RES_ROOT)
    print("game srv : %s:%s" % (GAME_HOST, GAME_PORT))
    print("http     : http://127.0.0.1:%d/" % HTTP_PORT)
    ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler).serve_forever()
