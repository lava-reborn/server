import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(p, encoding="utf-8").read()

old = '''# The server hands out a creature's type id where a string id belongs, so the
# stub below can answer with its internal name instead of a bare placeholder.
try:
    MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}
except Exception:
    MOB_NAMES = {}'''
new = '''# The server hands out a creature's type id where a string id belongs, so the
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
    REAL_NAMES = {}'''
assert old in s
s = s.replace(old, new)

old2 = '''        rows = "".join('<s id="%s">%s</s>' % (i, MOB_NAMES.get(int(i), "#" + i))
                       for i in ids)'''
new2 = '''        rows = "".join(
            '<s id="%s">%s</s>'
            % (i, REAL_NAMES.get(int(i)) or MOB_NAMES.get(int(i), "#" + i))
            for i in ids)'''
assert old2 in s
io.open(p, "w", encoding="utf-8").write(s.replace(old2, new2))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
