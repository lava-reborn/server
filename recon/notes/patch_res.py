import io
w = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/world.py"
s = io.open(w, encoding="utf-8").read()
old = '''def mob_types():
    """type_id -> (root_type_id, internal name) from the client's own table."""
    txt = _read(os.path.join(RES, "database", "mobs.xml"))
    out = {}
    for m in re.finditer(r'<mob type_id="(\d+)"\s+root_type_id=\s*"(\d+)"'
                         r'\s+name="([^"]*)"', txt):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3))
    return out'''
new = '''def mob_types():
    """type_id -> (root_type_id, internal name, art folder).

    The art folder is the "resource" attribute, and it is what the client wants
    in the res field: it builds paths as mobs/<resource>/..., with names like
    1f_npc9 or q4-1 rather than anything numeric. Sending the type id there
    leaves the creature invisible.
    """
    txt = _read(os.path.join(RES, "database", "mobs.xml"))
    out = {}
    for m in re.finditer(r'<mob type_id="(\d+)"\s+root_type_id=\s*"(\d+)"'
                         r'\s+name="([^"]*)"(?:\s+resource="([^"]*)")?', txt):
        out[int(m.group(1))] = (int(m.group(2)), m.group(3), m.group(4) or "")
    return out'''
assert old in s, "world anchor missing"
io.open(w, "w", encoding="utf-8").write(s.replace(old, new))

p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('            root, _name = MOB_TYPES.get(type_id, (world.MOB, ""))',
              '            root = MOB_TYPES.get(type_id, (world.MOB, "", ""))[0]')
s = s.replace('        params = dict(id=npc_id, name=type_id, sex=0, res=type_id, ail=0,',
              '        art = MOB_TYPES.get(type_id, (world.MOB, "", ""))[2]\n'
              '        params = dict(id=npc_id, name=type_id, sex=0, res=Str(art),\n'
              '                      ail=0,')
io.open(p, "w", encoding="utf-8").write(s)

b = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/bootstrap_http.py"
s = io.open(b, encoding="utf-8").read()
s = s.replace("MOB_NAMES = {t: n for t, (_root, n) in world.mob_types().items()}",
              "MOB_NAMES = {t: n for t, (_r, n, _a) in world.mob_types().items()}")
io.open(b, "w", encoding="utf-8").write(s)

import ast
for f in (w, p, b):
    ast.parse(io.open(f, encoding="utf-8").read())
print("ok")
