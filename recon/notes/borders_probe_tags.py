import re
from collections import Counter

p = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/1.xml'
s = open(p, encoding='utf-8').read()
print(Counter(re.findall(r'<(/?[A-Za-z_][\w-]*)', s)))
print('len', len(s))
