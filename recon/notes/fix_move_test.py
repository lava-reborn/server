import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
old = '''    # Nothing moves until the server echoes the path back.
    c.send("moveTo;path=|490|491|492|;")
    got = c.frames()
    check("movement echoed", got[0], "userMove;id=0;path=|490|491|492|;")'''
new = '''    # Nothing moves until the server echoes the path back, and every step also
    # registers a handler on the client's acknowledgement queue. That queue is
    # strictly ordered, so an unanswered move hands each later reply to a stale
    # mover and quietly breaks whatever asked for it.
    c.send("moveTo;path=|490|491|492|;")
    got = c.frames()
    check("movement acknowledged", got[0], "cmdAck;res=0;")
    check("movement echoed", got[1], "userMove;id=0;path=|490|491|492|;")

    # Mail is asked for the moment a location opens, and it expects an
    # acknowledgement of its own.
    c.send("chkml;mode=0;")
    check("mail answered", c.names(), ["cmdAck", "lsml"])

    # An unimplemented command that registers a handler must still be refused,
    # not ignored, or the same desynchronisation follows.
    c.send("ah_search;target=0;page=0;")
    got = c.frames()
    check("unimplemented but acknowledged", got[0].split(";")[0], "cmdAck")
    check("and refused rather than accepted", "res=0;" in got[0], False)'''
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")
