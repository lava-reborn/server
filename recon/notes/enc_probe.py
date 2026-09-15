import os
R = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res"
for rel in ("xmldocs/help.xml", "xmldocs/spec.xml", "database/locations.xml",
            "avatars/list.xml"):
    raw = open(os.path.join(R, rel), "rb").read()
    head = raw[:120].decode("ascii", "replace").replace("\n", " ")
    try:
        raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        enc = "cp1251"
    print("  %-26s фактически %-7s | объявлено: %s" % (rel, enc, head[:70]))
