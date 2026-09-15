import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/server.py"
s = io.open(p, encoding="utf-8").read()
old = '''        # res must be the creature's NAME from mobs.xml, not its art folder.
        # SSEmulator.getMobInfoURL looks the name up in the client's own copy
        # of that table and reads the resource field off the record itself, so
        # handing it the folder makes the lookup miss and the path come out as
        # mobs/undefined.xml.
        kind = MOB_TYPES.get(type_id, (world.MOB, "", ""))[1]
        params = dict(id=npc_id, name=type_id, sex=0, res=Str(kind),
                      ail=0,'''
new = '''        # res is the creature's numeric type id. The client keeps its own copy
        # of mobs.xml and looks the record up by that id, then reads the art
        # folder off it, so neither the folder name nor the creature name works
        # here: both make the lookup miss and the path resolve to
        # mobs/undefined.xml.
        params = dict(id=npc_id, name=type_id, sex=0, res=type_id,
                      ail=0,'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
import ast; ast.parse(io.open(p, encoding="utf-8").read())
print("ok")
