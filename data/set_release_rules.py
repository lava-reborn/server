"""Explicit release corrections applied after set generation."""


# Owner's live targets: Echo bonuses and the armour of Echo/Sturm.
# Piece columns: HP, stamina, armour, AP, crit, anti-crit. Slots follow sets.SLOTS.
LATE_SETS = {
    10961: (((26, 73, 36, 8, 4, 3),
             (26, 124, 29, 8, 3, 3),
             (26, 78, 350, 8, 3, 3),
             (26, 120, 29, 7, 3, 4),
             (25, 41, 16, 7, 3, 3)),
            {'2': {'hp': 32, 'st': 59},
             '3': {'st': 84, 'Сила': 1, 'Ближний бой': 1},
             '4': {'hp': 54, 'od': 12, 'ce': 16, 'Восприятие': 1},
             '5': {'st': 151, 'cp': 16, 'Телосложение': 2, 'Интеллект': 2}}),
    10965: (((28, 81, 41, 8, 4, 3),
             (28, 139, 37, 8, 3, 3),
             (28, 86, 417, 8, 4, 4),
             (27, 131, 37, 8, 3, 4),
             (27, 46, 20, 8, 3, 3)),
            {'2': {'hp': 43, 'st': 62},
             '3': {'st': 108, 'Сила': 1, 'Ближний бой': 2},
             '4': {'hp': 54, 'od': 15, 'ce': 18, 'Восприятие': 1},
             '5': {'st': 192, 'cp': 18, 'Телосложение': 2, 'Интеллект': 2}}),
    11002: (((28, 80, 42, 9, 4, 3),
             (28, 135, 44, 9, 3, 3),
             (28, 85, 458, 9, 4, 4),
             (28, 130, 44, 9, 3, 4),
             (28, 45, 22, 9, 3, 3)),
            {'2': {'hp': 50, 'st': 20},
             '3': {'st': 55, 'od': 20, 'Ловкость': 1},
             '4': {'hp': 60, 'st': 100, 'ce': 17, 'Интеллект': 1},
             '5': {'st': 200, 'cp': 17, 'Сила': 2, 'Телосложение': 3, 'Восприятие': 2}}),
    11004: (((30, 84, 47, 10, 4, 4),
             (30, 144, 54, 10, 4, 3),
             (30, 89, 532, 10, 5, 5),
             (30, 136, 53, 10, 3, 4),
             (30, 47, 24, 10, 3, 3)),
            {'2': {'hp': 55, 'st': 28},
             '3': {'st': 75, 'od': 25, 'Ловкость': 2},
             '4': {'hp': 65, 'st': 150, 'ce': 19, 'Интеллект': 2},
             '5': {'st': 200, 'cp': 19, 'Сила': 3, 'Телосложение': 4, 'Восприятие': 3}}),
}


# These wiki pages have a single stat column, which made the sold G sets
# identical to A. Keep the original prices/requirements and a modest G step.
EARLY_GOLD = {
    11221: (((0, 6, 4, 0, 1, 0),
             (0, 54, 1, 0, 0, 0),
             (0, 6, 9, 0, 0, 1),
             (0, 12, 1, 0, 0, 0),
             (0, 6, 1, 0, 0, 0)), {}),
    11193: (((3, 12, 10, 0, 1, 0),
             (2, 27, 2, 0, 1, 0),
             (3, 14, 36, 0, 1, 1),
             (2, 24, 3, 0, 0, 1),
             (2, 10, 2, 0, 0, 1)),
            {'2': {'hp': 2, 'st': 2},
             '3': {'st': 6, 'od': 2, 'Сила': 1},
             '4': {'st': 10, 'od': 4, 'ce': 3, 'Ловкость': 1},
             '5': {'st': 14, 'cp': 3, 'Телосложение': 1,
                   'Восприятие': 1, 'Интеллект': 1}}),
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
        if key in EARLY_GOLD:
            pieces, bonuses = EARLY_GOLD[key]
            fields = ('bonus_hp', 'bonus_st', 'armor_class', 'bonus_od', 'bonus_cp', 'bonus_ce')
            for slot, values in zip(('helm', 'shirt', 'armor', 'pants', 'boots'), pieces):
                piece = rec['members'][slot]
                piece.update((field, value) for field, value in zip(fields, values)
                             if value or field in piece)
            rec['bonus'] = {k: dict(v) for k, v in bonuses.items()}
            note = ('Release 2026-11-23: early G stats differentiated from the '
                    'single-column A source; prices, requirements and durability retained')
            if note not in rec.setdefault('_designed', []):
                rec['_designed'].append(note)
