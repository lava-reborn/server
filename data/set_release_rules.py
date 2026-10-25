"""Explicit release corrections applied after generation, without rebalance."""


def apply(table):
    for key, rec in table.items():
        key = int(key)
        level = {11002: 17, 11004: 17, 11125: 18, 60005: 18}.get(key)
        if level is not None:
            old = rec['level']
            rec['level'] = level
            rec['name'] = rec['name'].replace('[%d]' % old, '[%d]' % level)
            for piece in rec['members'].values():
                piece['name'] = piece['name'].replace('[%d]' % old, '[%d]' % level)
                piece['need']['Стрельба'] = level
            note = ('Release 2026-10-25: equip level %d, checked against the highest '
                    'base skill; armour numbers and prices retained' % level)
            rec['_designed'] = [s for s in rec.get('_designed', [])
                                if not s.startswith('Стрельба ')]
            if note not in rec['_designed']:
                rec['_designed'].append(note)
        if key in (10961, 10965):
            for bonus in rec.get('bonus', {}).values():
                bonus.pop('Стрельба', None)
            note = 'Release 2026-10-25: shooting skill bonus removed, A and G'
            if note not in rec['_designed']:
                rec['_designed'].append(note)
