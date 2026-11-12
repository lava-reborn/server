"""Independent range set ids and bonuses; A/P/G share the A reference."""
import copy
from functools import lru_cache
import re

FIRST = 80000
SIMULATOR_OFFSET = 1000


@lru_cache(maxsize=1)
def records():
    import items
    import sets
    from training import balance as balance
    names = {name: type_id for type_id, (_root, name) in items.catalogue().items()}
    result = {}
    for original_id, base in sorted(sets.SETS.items()):
        if base['variant'] != 'A':
            continue
        for line in ('A', 'P', 'G'):
            corresponding = next((record for record in sets.SETS.values()
                                  if record['family'] == base['family'] and record['level'] == base['level']
                                  and record['variant'] == line), None)
            if corresponding is not None:
                members = corresponding['members']
            else:
                def counterpart(type_id):
                    raw = items.catalogue()[type_id][1]
                    target = raw.replace('_A_mod', '_' + line + '_mod')
                    if target == raw and '_Q_mod' in raw:
                        target = raw.replace('_U_', '_M_').replace('_Q_mod', '_' + line + '_mod')
                        target = re.sub(r'_LVL_\d+_', '_LVL_%d_' % base['level'], target)
                    return names.get(target) if target != raw else None
                members = {slot: counterpart(type_id) for slot, type_id in base['members'].items()}
                if not all(members.values()):
                    continue
            record = copy.deepcopy(base)
            record['variant'], record['members'] = line, dict(members)
            record['name'] = base['name'] + (' (' + line + ')' if line != 'A' else '')
            if corresponding is not None:
                record['res'] = corresponding['res']
            for bonus in record['bonus'].values():
                for key, value in bonus.items():
                    bonus[key] = balance.scaled(value, balance.RATIOS[line])
            result[FIRST + len(result)] = record
    # Separate ids prevent another participant/profile from changing a cached
    # set tooltip. P retains the sandbox model: the source has no usable P sets.
    from training import formulas as training_formulas
    source_bonuses = training_formulas.data().get('sets', {}) if training_formulas.available() else {}
    for key, original in tuple(result.items()):
        source = next((s for s, r in sets.SETS.items()
                       if r['family'] == original['family'] and r['level'] == original['level']
                       and r['variant'] == original['variant']), None)
        if str(source) not in source_bonuses:
            continue
        record = copy.deepcopy(original)
        record['bonus'] = {int(k): copy.deepcopy(v) for k, v in source_bonuses[str(source)].items()}
        record['simulator'] = True
        result[key + SIMULATOR_OFFSET] = record
    return result


@lru_cache(maxsize=1)
def by_source():
    return {source: (set_id, record) for set_id, record in records().items() if not record.get('simulator')
            for source in record['members'].values()}


def for_source(source, simulator=False):
    import setcraft
    result = by_source().get(source) or by_source().get(setcraft.base_of(source))
    if simulator and result and result[0] + SIMULATOR_OFFSET in records():
        key = result[0] + SIMULATOR_OFFSET
        return key, records()[key]
    return result


def document(copies, simulator_copies):
    """Build metadata against local indexes, before the startup batch is published."""
    import sets
    documents = {}
    for key, record in records().items():
        simulator = bool(record.get('simulator'))
        index = simulator_copies if simulator else copies
        members = {slot: dict(type=index[source])
                   for slot, source in record['members'].items() if source in index}
        if len(members) != len(record['members']):
            continue
        bonuses = {}
        for count, bonus in record['bonus'].items():
            fields = {name: bonus[name] for name in sets.SCALARS if bonus[name]}
            for kind, labels in sets.LISTS:
                fields.update({label: value for label, value in zip(labels, bonus[kind]) if value})
            bonuses[str(count)] = fields
        documents[str(key)] = dict(name=record['name'], desc=record['desc'], family=record['family'],
                                   level=record['level'], variant=record['variant'], res=record['res'],
                                   members=members, bonus=bonuses)
    return {'sets': documents}


def strings():
    import sets
    return {offset + key: record[field] for key, record in records().items()
            for offset, field in ((sets.NAME_ID_OFFSET, 'name'), (sets.DESC_ID_OFFSET, 'desc'))}
