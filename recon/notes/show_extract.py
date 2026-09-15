import json, subprocess, sys
sys.path.insert(0, "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/data")
import wiki_extract as W
d = W.extract("Самодельный автомат")
print("статья:", d["title"])
print("таблиц:", len(d["tables"]))
for i, t in enumerate(d["tables"]):
    print(" таблица %d  колонки=%s  секций=%d" % (i, t["columns"], len(t["sections"])))
    for sec, params in t["sections"].items():
        print("   [%s] %d параметров" % (sec, len(params)))
        for k, v in list(params.items())[:4]:
            print("      %-26s %s" % (k, v))
