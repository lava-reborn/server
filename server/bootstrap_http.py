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
import sys
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

    def do_POST(self):
        path = urlparse(self.path).path
        if path.rstrip("/") == "/exe/lavaclient/loaduser":
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            # Session.getHashHostPort() splits on ":" then " "
            self._send("data=%s:%s devhash\n" % (GAME_HOST, GAME_PORT))
            return
        self._send("not found", code=404)

    def do_GET(self):
        path = posixpath.normpath(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            self._send(INDEX.format(host=GAME_HOST, port=GAME_PORT),
                       "text/html; charset=utf-8")
            return
        if path.endswith("/crossdomain.xml"):
            self._send(CROSSDOMAIN, "text/x-cross-domain-policy")
            return
        if path == "/res/xmldocs/csettings_v1.xml":
            self._send(CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,
                                        http_port=HTTP_PORT), "text/xml")
            return
        if path.startswith("/res/"):
            rel = path[len("/res/"):].replace("/", os.sep)
            full = os.path.normpath(os.path.join(RES_ROOT, rel))
            if not full.startswith(os.path.normpath(RES_ROOT)):
                self._send("forbidden", code=403)
                return
            if not os.path.isfile(full):
                self._send("not found", code=404)
                return
            ctype = ("application/x-shockwave-flash" if full.endswith(".swf")
                     else "text/xml" if full.endswith(".xml")
                     else "image/jpeg" if full.endswith((".jpg", ".jpeg"))
                     else "image/png" if full.endswith(".png")
                     else "application/octet-stream")
            with open(full, "rb") as fh:
                self._send(fh.read(), ctype)
            return
        self._send("not found", code=404)


if __name__ == "__main__":
    print("res root : %s" % RES_ROOT)
    print("game srv : %s:%s" % (GAME_HOST, GAME_PORT))
    print("http     : http://127.0.0.1:%d/" % HTTP_PORT)
    ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), Handler).serve_forever()
