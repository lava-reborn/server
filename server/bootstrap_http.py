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

None of that is wanted when the player runs the client off their own disk.
Serving csettings_v1.xml is exactly what flips PATHTYPE to WEB, so the whole
/res/ tree -- assets, csettings, texts.xml, hints.xml -- sits behind
LAVA_HTTP_RES, which is off by default. With it off this process is the
registration page and the service replies, nothing else: the client stays in
LOCAL mode, reads its own res/ off the disk and only opens the game socket.
Turn it on (LAVA_HTTP_RES=1) for the WEB path, which is what run.sh and the
test suites use.
"""
import json
import os
import signal
import threading
from xml.sax.saxutils import escape
import posixpath
import re
import sys

import accounts
import names
import items
import world
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

# one source of truth for where the client's files are
RES_ROOT = world.RES
GAME_HOST = os.environ.get("LAVA_GAME_HOST", "127.0.0.1")
GAME_PORT = os.environ.get("LAVA_GAME_PORT", "9775")
HTTP_PORT = int(os.environ.get("LAVA_HTTP_PORT", "8080"))
# Inside a container 127.0.0.1 is the container's own loopback and no
# published port reaches it, so the address to listen on is configuration.
HTTP_HOST = os.environ.get("LAVA_HTTP_HOST", "127.0.0.1")


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() not in (
        "", "0", "no", "off", "false")


# Everything under /res/ -- the client's own files and the three documents
# this process synthesises for them -- is one switch, because they are one
# decision. Serving any of them means serving csettings_v1.xml, and that is
# what puts the client in WEB mode.
SERVE_RES = _flag("LAVA_HTTP_RES")

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

PAGE = """<!doctype html><html lang=ru><meta charset=utf-8>
<title>LAVA Online</title>
<style>
 body{{background:#15130f;color:#cfc6b0;font:15px/1.5 system-ui,sans-serif;
      margin:0;padding:40px 20px}}
 .w{{max-width:440px;margin:0 auto}}
 h1{{font-size:20px;letter-spacing:.14em;text-transform:uppercase;
     color:#b9a678;margin:0 0 4px}}
 p.sub{{margin:0 0 28px;color:#7d7566}}
 form{{background:#1e1b15;border:1px solid #332d22;padding:22px;border-radius:4px}}
 label{{display:block;margin:0 0 6px;color:#9c9280;font-size:13px}}
 input{{width:100%;box-sizing:border-box;background:#100e0a;color:#e8dfc8;
        border:1px solid #3d362a;border-radius:3px;padding:9px 10px;
        font-size:15px;margin:0 0 16px}}
 button{{width:100%;background:#6b5a34;color:#f2e9d2;border:0;border-radius:3px;
         padding:11px;font-size:15px;cursor:pointer}}
 button:hover{{background:#7d6a3e}}
 .msg{{padding:11px 13px;border-radius:3px;margin:0 0 20px;font-size:14px}}
 .ok{{background:#243a20;border:1px solid #3d5c33;color:#bfe0ae}}
 .err{{background:#3a2020;border:1px solid #5c3333;color:#e0aeae}}
 .note{{margin-top:26px;color:#7d7566;font-size:13px}}
 code{{background:#100e0a;padding:2px 6px;border-radius:3px;color:#c4b48a}}
</style>
<div class=w>
<h1>LAVA Online</h1>
<p class=sub>Регистрация в игре</p>
{message}
<form method=post action="/register">
 <label for=login>Логин</label>
 <input id=login name=login autocomplete=username autofocus>
 <label for=password>Пароль</label>
 <input id=password name=password type=password autocomplete=new-password>
 <button type=submit>Создать аккаунт</button>
</form>
<p class=note>Учётных записей: {count}. Вход выполняется из самой игры:
запустите клиент и введите те же логин и пароль. Сервер отвечает на
<code>{host}:{port}</code>.</p>
</div></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "lava-bootstrap"

    def _send(self, body, ctype="text/plain; charset=windows-1251", code=200):
        if isinstance(body, str):
            # Encode to whatever the header promises. The game replies
            # are cp1251, the web pages here are utf-8, and declaring
            # one while sending the other is how labels went blank once.
            enc = "utf-8" if "utf-8" in ctype else "cp1251"
            body = body.encode(enc, "replace")
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
        # Compare with a separator on the end, or a sibling directory whose
        # name merely starts with the root's would pass for being inside it.
        root = os.path.normpath(RES_ROOT) + os.sep
        if not (full + os.sep).startswith(root):
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
        recovered, answer with the names the client's own tables and the wiki
        can supply: an item whose name never arrives is never added to the
        inventory at all.

        The ?all=1 request must answer with every id the server will ever use,
        and an empty reply here is not a harmless stub. StringCollector is a
        singleton that keeps SBase subscribed to its "update" event for the
        life of the session, and SBase answers that event by reloading the
        location names and dispatching its own "onLoad" — which Session
        handles with SceneShifter.enterScene(), the login screen. So any batch
        of strings fetched after login throws the player back to the login
        window. Filling the cache up front is what stops a second batch from
        ever being asked for; that is also why logging in twice used to work.
        """
        if "all=1" in (query or ""):
            self._send_xml("<data>%s</data>" % names.document())
            return
        # Reaching this at all means an id escaped the preload, which is the
        # fault worth knowing about: answering keeps the client moving, but
        # the request itself has already brought the login screen back.
        ids = [int(m) for m in re.findall(b"[0-9]+", body or b"")]
        unknown = [i for i in ids if not names.known(i)]
        if unknown:
            print("  HTTP строки мимо предзагрузки: %s" % unknown[:10],
                  flush=True)
        rows = "".join("<s id='%d'>%s</s>" % (i, names.text(i)) for i in ids)
        self._send_xml("<data>%s</data>" % rows)

    def _page(self, message=""):
        store = accounts.Store()
        try:
            count = store.account_count()
        finally:
            store.close()
        self._send(PAGE.format(message=message, count=count,
                               host=GAME_HOST, port=GAME_PORT),
                   "text/html; charset=utf-8")

    def _status(self):
        """What a healthcheck can ask without a game client.

        Touching the account store is the point: the page cannot register
        anyone if the database is unreachable, and a process that answers
        while its only job is broken is worse than one that is down.
        """
        store = accounts.Store()
        try:
            count = store.account_count()
        finally:
            store.close()
        self._send(json.dumps({
            "ok": True,
            "accounts": count,
            "strings": len(names.ALL),
            "game": "%s:%s" % (GAME_HOST, GAME_PORT),
            "res": SERVE_RES,
        }), "application/json")

    def _register(self, body):
        form = parse_qs(body.decode("utf-8", "replace"))
        login = (form.get("login") or [""])[0]
        password = (form.get("password") or [""])[0]
        store = accounts.Store()
        try:
            _id, err = store.register(login, password)
        finally:
            store.close()
        if err:
            self._page('<p class="msg err">%s</p>' % err)
        else:
            self._page('<p class="msg ok">Аккаунт <b>%s</b> создан. '
                       'Запустите клиент и войдите этим логином.</p>'
                       % login.replace("<", "&lt;"))

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
        # Percent-decode before touching the filesystem. Fifteen files under
        # res/ have a space in the name -- "Vadihalfa port.swf" is the art
        # library of the Wadi Halfa docks -- and the client asks for them
        # correctly escaped. Without this the location loads with no artwork
        # at all and shows as a black field, with only a 404 in the log to
        # say so.
        path = posixpath.normpath(unquote(parts.path))
        if path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Fills the host and port fields on the client's own login screen,
            # which parses the reply with getHashHostPort. No digest belongs
            # here any more: the client computes its own from the password.
            # Real Flash asks with GET, since LoadVars.sendAndLoad downgrades
            # to one when the outgoing object carries no variables, while
            # Ruffle issues the POST that was actually requested.
            self._send("data=%s:%s" % (GAME_HOST, GAME_PORT))
            return
        if path == "/register":
            self._register(body)
            return
        if path in ("/", "/index.html"):
            self._page()
        elif path == "/status":
            self._status()
        elif path.endswith("/crossdomain.xml"):
            self._send(CROSSDOMAIN, "text/x-cross-domain-policy")
        elif path.startswith("/res/") and not SERVE_RES:
            # Assets are the player's own copy of the game; we never hand them
            # out. Answering 404 rather than 403 is also the answer the client
            # needs: a csettings_v1.xml that is not there is what leaves it in
            # LOCAL mode, reading its own res/ off the disk.
            self._send("not found", code=404)
        elif path == "/res/xmldocs/csettings_v1.xml":
            self._send(CSETTINGS.format(host=GAME_HOST, port=GAME_PORT,
                                        http_port=HTTP_PORT), "text/xml")
        elif path == "/res/database/texts.xml":
            self._texts(parts.query, body)
        elif path == "/res/hints/hints.xml":
            # The other of the two files missing from the shipped client
            # (texts.xml is the first). An empty document satisfies it, but
            # written the way the client's own XML is, UTF-8 with a byte
            # order mark, which is what _send_xml does; the cp1251 that
            # _send produces is the same silent failure texts.xml had.
            self._send_xml("<data/>")
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
    print("http     : http://%s:%d/" % (HTTP_HOST, HTTP_PORT))
    print("res serve: %s" % ("on" if SERVE_RES else "off (registration only)"))
    # Build the 1.9 MB string table before the client can ask for it.
    names.document()
    httpd = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    # docker stop sends SIGTERM, whose default action kills the process where
    # it stands. Nothing here is worth saving, but the listener should close
    # and the log should say so rather than the container reporting 143.
    for _sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(_sig, lambda *_a: threading.Thread(
            target=httpd.shutdown, daemon=True).start())
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        print("http stopped", flush=True)
