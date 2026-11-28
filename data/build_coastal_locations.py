"""Keep native coast populations; place them only after explicit bank review.

Only data/coastal_locations.json owns the regional choices. The ordinary
settlement placer and spawn builder reproduce the generated rows afterwards.
Run with LAVA_RES pointing at the original client resources.
"""
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'server'))
import world


def document():
    return json.loads((HERE / 'coastal_locations.json').read_text(encoding='utf-8'))


def placement_rows(doc):
    """Draft coordinates must never become game bindings implicitly."""
    return doc['locations'] if doc.get('global_bindings_enabled') is True else {}


def river_distance(point, trace):
    """Distance to the photo-reviewed Nile axis, in global map cells."""
    x,y = point
    values = []
    for (ax,ay),(bx,by) in zip(trace,trace[1:]):
        dx,dy = bx-ax,by-ay
        fraction = max(0,min(1,((x-ax)*dx+(y-ay)*dy)/max(1,dx*dx+dy*dy)))
        values.append(math.hypot(x-ax-fraction*dx,y-ay-fraction*dy))
    return min(values)


def fill_rows():
    doc = document()
    meta = json.loads((HERE / 'mob_types.json').read_text(encoding='utf-8'))['types']
    rows = {}
    for key, row in doc['locations'].items():
        loc = world.location(int(key))
        mob = doc['cities'][row['city']]['mob']
        level = doc['cities'][row['city']]['level']
        if not loc.war or meta[str(mob)]['role'] != 'animal' or meta[str(mob)]['resource'] != 'crocodile':
            raise ValueError('Coast population must be a crocodile in a combat location')
        if not loc.spawns or any(t != 0 for _, t in loc.spawns):
            raise ValueError('Coast fill may only populate existing empty nests')
        native = {cell for cell, _ in loc.spawns}
        moves = {int(a): b for a, b in row.get('spawn_moves', {}).items()}
        actual = [moves.get(cell, cell) for cell in native]
        if (not moves.keys() <= native or len(set(actual)) != len(actual)
                or any(type(c) is not int or not 0 <= c < loc.width*loc.height
                       or c in loc.obstacles for c in actual)):
            raise ValueError('Invalid coastal spawn relocation')
        why = ('DESIGNED 2026-11-27: restore %s coast with the original %s geometry '
               'and its %d empty nests; coastal level-%d profile of crocodile %d, natural respawn, no loot. '
               'Regional placement is not a recovered server table.'
               % (row['city'], loc.fn, len(loc.spawns), level, mob))
        rows[int(key)] = (None, (level, level), [mob] * len(loc.spawns), why)
    return rows


def write_json(name, doc):
    (HERE / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n',
                            encoding='utf-8', newline='\n')


def main():
    doc = document()
    fixed = json.loads((HERE / 'settlements_verified.json').read_text(encoding='utf-8'))
    table = json.loads((HERE / 'settlements.json').read_text(encoding='utf-8'))
    fill = json.loads((HERE / 'camp_fill.json').read_text(encoding='utf-8'))
    owned = {int(key) for key in doc['locations']}
    # Withdraw previous bindings by ownership, without touching other locations.
    for cell, loc_id in list(table['cells'].items()):
        if loc_id in owned:
            del table['cells'][cell]
    for cell, loc_id in list(fixed['cells'].items()):
        if loc_id in owned:
            del fixed['cells'][cell]
            fixed['why'].pop(cell, None)
    for key, row in placement_rows(doc).items():
        loc_id = int(key)
        x, y = row['cell']
        cell = '%d,%d' % (x, y)
        if not world.passable(x, y):
            raise ValueError('Coast cell is not reachable land: ' + cell)
        if river_distance((x,y), doc['cities'][row['city']]['river_trace']) > 6:
            raise ValueError('Coast is too far from the photo-reviewed Nile: ' + cell)
        if cell in table['cells'] and table['cells'][cell] != loc_id:
            raise ValueError('Coast would replace an existing settlement: ' + cell)
        if cell in fixed['cells'] and fixed['cells'][cell] != loc_id:
            raise ValueError('Coast would replace a verified cell: ' + cell)
        fixed['cells'][cell] = table['cells'][cell] = loc_id
        fixed['why'][cell] = ('DESIGNED 2026-11-27: %s coast, original tile %s; '
                              'bank reviewed on the original satellite tiles, native exits lead to reachable land. '
                              'The original global placement is unknown.' % (row['city'], loc_id))
    for loc_id, (faction, band, types, why) in fill_rows().items():
        fill['fill'][str(loc_id)] = dict(fn=world.location(loc_id).fn, faction=faction,
                                         band=list(band), types=types, why=why)
    write_json('settlements_verified.json', fixed)
    write_json('settlements.json', table)
    write_json('camp_fill.json', fill)
    labels = json.loads((HERE / 'map_labels.json').read_text(encoding='utf-8'))
    active = {int(key) for key in placement_rows(doc)}
    labels['labels'] = [e for e in labels['labels'] if 'coastal_location' not in e
                        and e.get('withdrawn_coastal_location') not in active]
    for key,row in placement_rows(doc).items():
        city = doc['cities'][row['city']]
        labels['labels'].append(dict(x=row['cell'][0], y=row['cell'][1], add=True,
            text='Побережье: %s<br>Крокодилы, %d ур.<br>Охота за опытом. Без добычи предметов.'
                 % (row['city'],city['level']), coastal_location=int(key),
            why='DESIGNED 2026-11-27: label for the restored, photo-reviewed Nile coast.'))
    write_json('map_labels.json', labels)
    print('Kept %d native coast maps and %d crocodile nests; global placement requires approval' %
          (len(doc['locations']), sum(len(r[2]) for r in fill_rows().values())))


if __name__ == '__main__':
    main()
