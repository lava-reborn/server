import sys, re
sys.path.insert(0, "/mnt/c/Users/gmkrt/OneDrive/Desktop/claude/lava-server/data")
import wiki_extract as W
txt = W.wikitext("Самодельный автомат")
blocks = W.TABLE.findall(txt)
print("найдено блоков {|...|}:", len(blocks))
print("всего '{|' в тексте:", txt.count("{|"), "  '|}':", txt.count("|}"))
b = blocks[0]
rows = re.split(r"\n\|-", b)
print("строк в блоке 0:", len(rows))
for i, r in enumerate(rows[:6]):
    print("--- row %d ---" % i)
    print(repr(r[:180]))
