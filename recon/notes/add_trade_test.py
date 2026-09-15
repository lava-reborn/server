import io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server/test_world.py"
s = io.open(p, encoding="utf-8").read()
block = '''
    # --- a trader's stock -------------------------------------------------
    # The price list rides in userInfo as type_list, and the client refers to a
    # purchase by its index in that list rather than by the item's own id.
    c.send("getInfo;lvl=0;id=105;type=1;")
    got = c.frames()
    trader = got[0]
    check("trader carries a price list", "type_list=|" in trader, True)
    first = int(trader.split("type_list=|")[1].split("|")[0])

    c.send("ss_create;s_type=1;target=105;")
    check("trade session opens", c.names(), ["cmdAck"])

    # ItemFactory keeps five of these in flight and frees a slot only when the
    # answer lands, so an unanswered one leaves the shop empty for good.
    c.send("ss_get_si;type=%d;" % first)
    got = c.frames()
    check("item described", got[0].split(";")[0], "ss_si_firearm")
    check("described item is the one asked for",
          "type=%d;" % first in got[0], True)
    # Fields the client divides by: a zero in either is a broken item, not a
    # weak one.
    check("range is non-zero", "max_range=|0|" not in got[0], True)
    check("target size is non-zero", "target_size=|0|" not in got[0], True)
    # fire_mods doubles as the burst length, and at least one mode must be on.
    modes = got[0].split("fire_mods=|")[1].split("|;")[0].split("|")
    check("at least one fire mode enabled", any(m != "0" for m in modes), True)

'''
s = s.replace("\n    # --- the global map ---", block + "    # --- the global map ---", 1)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
