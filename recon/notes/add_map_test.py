import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
block = '''
    # --- the global map ---------------------------------------------------
    c.send("chWorld;")
    got = c.frames()
    check("leaving for the map", [f.split(";")[0] for f in got],
          ["cmdAck", "gmap"])
    check("map position sent", "x=5968;y=1727;" in got[1], True)

    # Offsets there are hundredths of a cell. moveAck only sets a velocity, so
    # the client extrapolates and the server has to time the arrival itself and
    # confirm it with a zero-speed frame.
    c.send("moveTo;dy=0;dx=-100;")
    got = c.frames()
    check("travel acknowledged", got[0].split(";")[0], "moveAck")
    check("velocity not position", "vx=" in got[0] and "dx=" not in got[0], True)

    got = c.frames(wait=5)
    check("arrival confirmed", got and got[0].split(";")[0] == "userMove", True)
    check("stopped on arrival", "vx=0;vy=0;" in got[0], True)
    check("moved one cell west", "dx=5967;" in got[0], True)

    # Coming back onto the settlement's own cell drops the player into it.
    c.send("moveTo;dy=0;dx=100;")
    c.frames()
    got = c.frames(wait=6)
    names = [f.split(";")[0] for f in got]
    check("returning enters the location", names, ["userMove", "lcall"])

    c.send("logout;")
'''
s = s.replace('    c.send("logout;")\n', block, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
