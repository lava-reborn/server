import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

s = s.replace("import re\nimport sys",
              "import re\nimport sys\n\nimport world")

s = s.replace('CTYPES = {',
'''# The server hands out a creature's type id where a string id belongs, so the
# stub below can answer with its internal name instead of a bare placeholder.
try:
    MOB_NAMES = {t: n for t, (_root, n) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}

CTYPES = {''')

old = '''        ids = [m.decode() for m in re.findall(rb"\d+", body or b"")]
        rows = "".join('<s id="%s">#%s</s>' % (i, i) for i in ids)
        self._send("<data>%s</data>" % rows, "text/xml")'''
new = '''        ids = [m.decode() for m in re.findall(rb"\d+", body or b"")]
        rows = "".join('<s id="%s">%s</s>' % (i, MOB_NAMES.get(int(i), "#" + i))
                       for i in ids)
        self._send("<data>%s</data>" % rows, "text/xml")'''
assert old in s, "anchor missing"
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
