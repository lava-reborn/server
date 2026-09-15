import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
old = '''    check("inhabitants placed", names.count("lch") > 0, True)
    # registered without a figure first, so their details can land before
    # anything is drawn
    check("registration precedes description",
          "refl=" in " ".join(f for f in got if f.startswith("lch")), True)'''
new = '''    check("inhabitants placed", names.count("lch") > 0, True)
    # each placement is followed immediately by that inhabitant's details
    check("described alongside placement",
          names.count("lch") == len([n for n in names if n.startswith("userInfo")]),
          True)'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
