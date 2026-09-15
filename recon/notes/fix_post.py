import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("import os\nimport posixpath\nimport sys",
              "import os\nimport posixpath\nimport re\nimport sys")

s = s.replace('CROSSDOMAIN = (',
'''CTYPES = {
    ".swf": "application/x-shockwave-flash",
    ".xml": "text/xml",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".mp3": "audio/mpeg", ".txt": "text/plain",
}

CROSSDOMAIN = (''')

start = s.index("    def do_POST(self):")
end = s.index('if __name__ == "__main__":')
new = '''    # --- routing ---------------------------------------------------------
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
            self._send("<data></data>", "text/xml")
            return
        ids = [m.decode() for m in re.findall(rb"\d+", body or b"")]
        rows = "".join('<s id="%s">#%s</s>' % (i, i) for i in ids)
        self._send("<data>%s</data>" % rows, "text/xml")

    def _dispatch(self, body=b""):
        parts = urlparse(self.path)
        path = posixpath.normpath(parts.path)
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
        if urlparse(self.path).path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Session.getHashHostPort() splits on ":" then " "
            self._send("data=%s:%s devhash\n" % (GAME_HOST, GAME_PORT))
            return
        self._dispatch(body)


'''
io.open(p, "w", encoding="utf-8").write(s[:start] + new + s[end:])
print("patched")
