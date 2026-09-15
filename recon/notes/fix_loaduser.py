import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

old = '''    def _dispatch(self, body=b""):
        parts = urlparse(self.path)
        path = posixpath.normpath(parts.path)
        if path in ("/", "/index.html"):'''
new = '''    def _dispatch(self, body=b""):
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
        if path in ("/", "/index.html"):'''
assert old in s
s = s.replace(old, new)

# the POST handler's own copy is now redundant
old_post = '''        if urlparse(self.path).path.rstrip("/") == "/exe/lavaclient/loaduser":
            # Session.getHashHostPort() splits on ":" then " "
            self._send("data=%s:%s devhash" % (GAME_HOST, GAME_PORT))
            return
        self._dispatch(body)'''
assert old_post in s
s = s.replace(old_post, "        self._dispatch(body)")
io.open(p, "w", encoding="utf-8").write(s)
import ast
ast.parse(io.open(p, encoding="utf-8").read())
print("patched, syntax ok")
