import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    check("map position sent", "x=5968;y=1727;" in got[1], True)''',
'''    check("map position sent", "x=5968;y=1727;" in got[1], True)

    # The same command goes both ways: the client's map and location screens
    # both call changeWorld with no argument, so the direction is decided here.
    c.send("chWorld;")
    got = c.frames()
    check("button toggles back into the location",
          [f.split(";")[0] for f in got], ["cmdAck", "lcall"])
    # and the cell the settlement occupies rides packed into g_id
    check("map cell packed into g_id", "g_id=48891583;" in got[1], True)
    c.send("lenter;accept=1;")
    c.frames()
    c.send("chWorld;")
    c.frames()''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
