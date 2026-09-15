import io
t = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(t, encoding="utf-8").read()
old = '''    # Coming back onto the settlement's own cell drops the player into it.
    c.send("moveTo;dy=0;dx=100;")
    c.frames()
    got = c.frames(wait=6)
    names = [f.split(";")[0] for f in got]
    check("returning enters the location", names, ["userMove", "lcall"])'''
new = '''    # Coming back onto the settlement must NOT pull the player in: a cell is
    # wide enough that any short hop near one would land inside it, and the
    # map would be impossible to stay on.
    c.send("moveTo;dy=0;dx=100;")
    c.frames()
    got = c.frames(wait=6)
    names = [f.split(";")[0] for f in got]
    check("returning does not enter by itself", names, ["userMove"])

    # The button does it, and only while standing on the settlement.
    c.send("chWorld;")
    got = c.frames()
    check("button enters from the settlement",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])'''
assert old in s
io.open(t, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
