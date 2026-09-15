import os, sys
sys.path.insert(0, "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/server")
import items, world
ROOT_DIR = {0: "FireArm", 1: "WearItem", 2: "Heal_Item", 3: "Ammo",
            4: "SimpleObject", 5: "ColdArm", 6: "Trophy"}
cat = items.catalogue()
missing = 0
for trader, stock in sorted(items.STOCK.items()):
    print("торговец %d:" % trader)
    for t in stock:
        root, name = cat.get(t, (-1, "?"))
        folder = os.path.join(world.RES, "classes", ROOT_DIR.get(root, "?"),
                              name, "ico.swf")
        ok = os.path.isfile(folder)
        if not ok:
            missing += 1
        print("   type=%-6d root=%d %-14s иконка: %s" %
              (t, root, name, "есть" if ok else "НЕТ"))
print("\nбез иконки: %d" % missing)
