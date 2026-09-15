import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    # ie=0 in lcall means the client confirms once its assets have loaded.
    c.send("lenter;accept=1;")
    got = c.frames()
    check("lenter acked then positioned", [f.split(";")[0] for f in got],
          ["cmdAck", "lenter"])
    check("spawn cell sent", "pos=490;" in got[1], True)''',
'''    # ie=0 in lcall means the client confirms once its assets have loaded.
    # The location's own inhabitants follow immediately, one lch frame each.
    c.send("lenter;accept=1;")
    got = c.frames()
    names = [f.split(";")[0] for f in got]
    check("lenter acked then positioned", names[:2], ["cmdAck", "lenter"])
    check("spawn cell sent", "pos=" in got[1], True)
    check("inhabitants placed", len(got) > 2 and set(names[2:]) == {"lch"}, True)
    first_npc = got[2]
    check("inhabitant carries a class", "rtype=" in first_npc, True)

    # Their details are pulled one at a time with getInfo type=1.
    npc_id = int(first_npc.split("newUser=")[1].split(";")[0])
    c.send("getInfo;lvl=0;id=%d;type=1;" % npc_id)
    got = c.frames()
    check("inhabitant described", got[0].split(";")[0].startswith("userInfo"), True)
    # res must be the art folder name, not the numeric type id, or the
    # creature is placed but never drawn.
    check("art folder sent as a string", "res=@" in got[0], True)''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
