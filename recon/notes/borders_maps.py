"""Emit the ASCII schematics of the rock kit as a markdown appendix.

Used to append the plate section to recon/analysis/borders.md:

    python3 recon/notes/borders_maps.py >> recon/analysis/borders.md
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import borders_loc_geom as G  # noqa: E402

ORDER = [
    (12, 'W', 'западная стена: скала слева (x-min)'),
    (13, 'W', 'то же, второй вариант'),
    (1, 'E', 'восточная стена: скала справа (x-max)'),
    (2, 'E', 'то же, второй вариант'),
    (10, 'N', 'северная стена: скала сверху (y-min)'),
    (11, 'N', 'то же, второй вариант'),
    (15, 'S', 'южная стена: скала снизу (y-max)'),
    (16, 'S', 'то же, второй вариант'),
    (3, 'WN', 'северо-западный угол: стены слева и сверху'),
    (9, 'EN', 'северо-восточный угол'),
    (0, 'WS', 'юго-западный угол'),
    (8, 'ES', 'юго-восточный угол'),
    (5, 'NS', 'проход поперёк меридиональной гряды (открыт W и E)'),
    (6, 'WE', 'проход вдоль гряды (открыт N и S)'),
    (14, 'NES', 'карман, вход только с запада'),
    (40, 'WES', 'карман, вход только с севера'),
    (4, 'WNS', 'карман, вход только с востока (файл без fn)'),
    (7, 'WNE', 'карман, вход только с юга'),
    (51, '-', 'остров: скала посередине, все четыре стороны открыты'),
    (428, '-', 'копия острова, "test"'),
    (218, 'N', 'копия 10 под другим именем (B_DownSide_Out)'),
    (1298, 'WNES', 'озеро/«Засада»: выходов нет вообще'),
    (178, 'S', 'копия 15 с pvp=0'),
    (179, 'S', 'копия 16 с pvp=0'),
    (180, 'E', 'копия 2 с pvp=0'),
]

CODE = {'1': 'W', '2': 'N', '3': 'E', '4': 'S'}

print()
print('Легенда: `.` проходимо, `+` частично скала, `#` сплошная скала,')
print('цифра — клетка выхода с её кодом стороны (`1`=W, `2`=N, `3`=E, `4`=S),')
print('`I` клетка входа, `z` зона выхода без кода. Один знак = 2x4 клетки')
print('сетки 64x128; строка сверху — север, столбец слева — запад.')
print()
for lid, wall, note in ORDER:
    r = G.parse(lid)
    h = r['hdr']
    codes = sorted({e for _, _, e in (r['outzones'] or [])})
    print('### %d — `%s` — %s' % (lid, h.get('fn') or '(без fn)', note))
    print()
    print('    title=%s  library=%s  pvp=%s  war=%s  %sx%s'
          % (h.get('title'), h.get('library'), h.get('pvp'), h.get('war'),
             r['w'], r['h']))
    print('    выходы: %s      стена(ы): %s'
          % (', '.join('%s=%s' % (c, CODE.get(c, c)) for c in codes) or 'нет',
             wall))
    print('    obstacles=%d  zones=%d  inzones=%d  warinzones=%d'
          % (len(r['obstacles'] or []), len(r['zones'] or []),
             len(r['inzones'] or []), len(r['warinzones'] or [])))
    print()
    print('```')
    for line in G.compress(r):
        print(line)
    print('```')
    print()
