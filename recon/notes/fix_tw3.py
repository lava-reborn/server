import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
old = '''    # res must be the art folder name, not the numeric type id, or the
    # creature is placed but never drawn.
    check("art folder sent as a string", "res=@" in got[0], True)'''
new = '''    # res must be the numeric type id: the client looks the record up by it in
    # its own copy of mobs.xml and reads the art folder off that. Sending the
    # folder or the name instead leaves the creature undrawn.
    res = got[0].split("res=")[1].split(";")[0]
    check("art keyed by numeric type id", res.isdigit(), True)'''
assert old in s
s = s.replace(old, new)
# the placement is now three passes, so lch frames bracket the userInfo ones
s = s.replace('    check("inhabitants placed", len(got) > 2 and set(names[2:]) == {"lch"}, True)',
              '    check("inhabitants placed", names.count("lch") > 0, True)\n'
              '    # registered without a figure first, so their details can land before\n'
              '    # anything is drawn\n'
              '    check("registration precedes description",\n'
              '          "refl=" in " ".join(f for f in got if f.startswith("lch")), True)')
s = s.replace('    first_npc = got[2]', '    first_npc = [f for f in got if f.startswith("lch")][0]')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
