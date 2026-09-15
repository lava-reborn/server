import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    c.send("lenter;accept=1;")
    got = c.frames()
    names = [f.split(";")[0] for f in got]
    check("lenter acked then positioned", names[:2], ["cmdAck", "lenter"])''',
'''    c.send("lenter;accept=1;")
    got = c.frames(wait=2)
    names = [f.split(";")[0] for f in got]
    # No acknowledgement on success: the client cancels the one it registered
    # as soon as the lenter frame arrives.
    check("positioned without an ack", names[0], "lenter")''')
s = s.replace('    check("spawn cell sent", "pos=" in got[1], True)',
              '    check("spawn cell sent", "pos=" in got[0], True)')
s = s.replace('''    check("inhabitants placed", names.count("lch") > 0, True)''',
              '''    check("inhabitants placed", names.count("lch") > 0, True)''')
s = s.replace('''    c.send("lenter;accept=1;")
    c.frames()
    c.send("chWorld;")
    c.frames()''',
'''    c.send("lenter;accept=1;")
    c.frames(wait=2)
    c.send("chWorld;")
    c.frames()''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
