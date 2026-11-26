"""Place recovered coast tiles and populate their existing empty nests.

Only data/coastal_locations.json owns the regional choices. The ordinary
settlement placer and spawn builder reproduce the generated rows afterwards.
Run with LAVA_RES pointing at the original client resources.
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'server'))
import world


def document():
    return json.loads((HERE / 'coastal_locations.json').read_text(encoding='utf-8'))


def fill_rows():
    doc = document()
    meta = json.loads((HERE / 'mob_types.json').read_text(encoding='utf-8'))['types']
    rows = {}
    for key, row in doc['locations'].items():
        loc = world.location(int(key))
        mob = doc['cities'][row['city']]['mob']
        level = meta[str(mob)]['level']
        if not loc.war or meta[str(mob)]['role'] != 'animal' or meta[str(mob)]['resource'] != 'crocodile':
            raise ValueError('Coast population must be a crocodile in a combat location')
        if not loc.spawns or any(t != 0 for _, t in loc.spawns):
            raise ValueError('Coast fill may only populate existing empty nests')
        why = ('DESIGNED 2026-11-27: restore %s coast with the original %s geometry '
               'and its %d empty nests; existing level-%d crocodile %d, natural respawn. '
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
    for key, row in doc['locations'].items():
        loc_id = int(key)
        x, y = row['cell']
        cell = '%d,%d' % (x, y)
        if not world.passable(x, y):
            raise ValueError('Coast cell is not reachable land: ' + cell)
        if cell in table['cells'] and table['cells'][cell] != loc_id:
            raise ValueError('Coast would replace an existing settlement: ' + cell)
        if cell in fixed['cells'] and fixed['cells'][cell] != loc_id:
            raise ValueError('Coast would replace a verified cell: ' + cell)
        fixed['cells'][cell] = table['cells'][cell] = loc_id
        fixed['why'][cell] = ('DESIGNED 2026-11-27: %s coast, original tile %s; '
                              'dry reachable bank, native exits agree with land neighbours. '
                              'The original global placement is unknown.' % (row['city'], loc_id))
    for loc_id, (faction, band, types, why) in fill_rows().items():
        fill['fill'][str(loc_id)] = dict(fn=world.location(loc_id).fn, faction=faction,
                                         band=list(band), types=types, why=why)
    write_json('settlements_verified.json', fixed)
    write_json('settlements.json', table)
    write_json('camp_fill.json', fill)
    print('Restored %d coast maps and %d crocodile nests' %
          (len(doc['locations']), sum(len(r[2]) for r in fill_rows().values())))


if __name__ == '__main__':
    main()
