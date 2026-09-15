import io, re, collections
P = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/database/objects.xml"
txt = open(P, "rb").read().decode("utf-8", "replace")
rows = [(int(m.group(1)), int(m.group(2)), m.group(3))
        for m in re.finditer(r'<object type_id="(\d+)" root_type_id=\s*"(\d+)" name="([^"]*)"', txt)]
OUT = "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/logs/items.txt"
by_root = collections.Counter(r[1] for r in rows)
ROOTS = {0: "FireArm", 1: "Wear", 2: "Heal", 3: "Ammo", 4: "Trash",
         5: "ColdArm", 6: "Trophy"}
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("предметов: %d\n\n" % len(rows))
    for r, n in sorted(by_root.items()):
        f.write("  root=%d %-9s %6d\n" % (r, ROOTS.get(r, "?"), n))
    f.write("\n")
    for needle, label in [("Pistol", "пистолеты"), ("Shotgun", "дробовики"),
                          ("AssRifle", "автоматы"), ("Rifle", "винтовки"),
                          ("Ammo_9", "патроны 9мм"), ("knife", "ножи")]:
        hits = [r for r in rows if needle.lower() in r[2].lower()]
        f.write("%s (%s): %d\n" % (label, needle, len(hits)))
        for t, root, name in hits[:8]:
            f.write("   type=%-6d root=%d  %s\n" % (t, root, name))
        f.write("\n")
print("готово")
