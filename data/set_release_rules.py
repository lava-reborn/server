"""Explicit release corrections applied after set generation."""


# Echo closes the level-16/17 gap; Sturm retains its original numeric stats.
# Piece columns: HP, stamina, armour, AP, crit, anti-crit. Slots follow sets.SLOTS.
LATE_SETS = {
    10961: (((28, 78, 43, 9, 4, 3),
             (28, 133, 35, 9, 3, 3),
             (28, 83, 418, 9, 3, 3),
             (28, 128, 35, 9, 3, 4),
             (27, 44, 19, 9, 3, 3)),
            {'2': {'hp': 34, 'st': 63},
             '3': {'st': 90, 'Сила': 1, 'Ближний бой': 1},
             '4': {'hp': 57, 'od': 15, 'ce': 16, 'Восприятие': 1},
             '5': {'st': 161, 'cp': 16, 'Телосложение': 2, 'Интеллект': 2}}),
    10965: (((30, 84, 48, 10, 4, 3),
             (29, 144, 44, 10, 3, 3),
             (29, 89, 491, 10, 4, 4),
             (29, 136, 44, 10, 3, 4),
             (29, 47, 23, 10, 3, 3)),
            {'2': {'hp': 45, 'st': 64},
             '3': {'st': 112, 'Сила': 1, 'Ближний бой': 2},
             '4': {'hp': 57, 'od': 20, 'ce': 18, 'Восприятие': 1},
             '5': {'st': 199, 'cp': 18, 'Телосложение': 2, 'Интеллект': 2}}),
    11002: (((28, 80, 43, 9, 4, 3),
             (28, 135, 45, 9, 3, 3),
             (28, 85, 469, 9, 4, 4),
             (28, 130, 45, 9, 3, 4),
             (28, 45, 22, 9, 3, 3)),
            {'2': {'hp': 50, 'st': 20},
             '3': {'st': 55, 'od': 20, 'Ловкость': 1},
             '4': {'hp': 60, 'st': 100, 'ce': 17, 'Интеллект': 1},
             '5': {'st': 200, 'cp': 17, 'Сила': 2, 'Телосложение': 3, 'Восприятие': 2}}),
    11004: (((30, 84, 48, 10, 4, 4),
             (30, 144, 55, 10, 4, 3),
             (30, 89, 547, 10, 5, 5),
             (30, 136, 55, 10, 3, 4),
             (30, 47, 25, 10, 3, 3)),
            {'2': {'hp': 55, 'st': 28},
             '3': {'st': 75, 'od': 25, 'Ловкость': 2},
             '4': {'hp': 65, 'st': 150, 'ce': 19, 'Интеллект': 2},
             '5': {'st': 200, 'cp': 19, 'Сила': 3, 'Телосложение': 4, 'Восприятие': 3}}),
}

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
        if key in LATE_SETS:
            pieces, bonuses = LATE_SETS[key]
            fields = ('bonus_hp', 'bonus_st', 'armor_class', 'bonus_od', 'bonus_cp', 'bonus_ce')
            for slot, values in zip(('helm', 'shirt', 'armor', 'pants', 'boots'), pieces):
                rec['members'][slot].update(zip(fields, values))
            rec['bonus'] = {k: dict(v) for k, v in bonuses.items()}
