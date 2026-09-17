import re
import sys

base = '/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/locations/static/'
lid = sys.argv[1] if len(sys.argv) > 1 else '1'
s = open(base + lid + '.xml', encoding='utf-8').read()

# header
m = re.search(r'<location[^>]*>', s)
print('HEADER:', m.group(0))
print()
for tag in ('obstacles', 'zones', 'warinzones', 'inzones', 'outzones', 'mobs', 'serverdata'):
    mm = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (tag, tag), s, re.S)
    if not mm:
        print(tag.upper(), '-> MISSING')
        continue
    body = mm.group(1)
    print('%s len=%d' % (tag.upper(), len(body)))
    print(repr(body[:1500]))
    print('---')
