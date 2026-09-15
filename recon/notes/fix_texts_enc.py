import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

old = '''        if "all=1" in (query or ""):
            self._send("<data></data>", "text/xml")
            return'''
new = '''        if "all=1" in (query or ""):
            self._send_xml("<data></data>")
            return'''
assert old in s
s = s.replace(old, new)

old2 = '''        rows = "".join(
            '<s id="%s">%s</s>'
            % (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i), "#" + i))
            for i in ids)
        self._send("<data>%s</data>" % rows, "text/xml")'''
new2 = '''        rows = "".join(
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
        payload = ("\ufeff<?xml version='1.0'?>" + body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)'''
assert old2 in s
io.open(p, "w", encoding="utf-8").write(s.replace(old2, new2))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
