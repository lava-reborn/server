"""One immutable display payload per process; no inventory or account state."""
from functools import lru_cache
import hashlib
import json
from protocol import Str
from training import items, display
from training.catalog import item_catalogue, item_line


@lru_cache(maxsize=1)
def payload():
    rows = []
    catalogue = item_catalogue()
    for type_id, source in items.SOURCES.items():
        profile_source = items.profile_source(type_id)
        cost, gold, pack = items.REFERENCE_PRICES[profile_source]
        rows.append((type_id, profile_source, item_line(source),
                     display.icon_source(profile_source), cost, gold, pack, catalogue[profile_source][2]))
    fields = ('copies', 'sources', 'lines', 'icons', 'costs', 'gold_costs', 'price_packs', 'labels')
    result = {key: list(values) for key, values in zip(fields, zip(*rows))}
    digest = hashlib.sha256((items.PATH.parent / 'training_item_ids.json').read_bytes())
    digest.update(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8'))
    result['version'] = digest.hexdigest()
    return result


def announce(owner, *, full=False):
    data = payload()
    if not full and getattr(owner, 'training_types_version', None) == data['version']:
        owner.send('tg', op='types_cached', version=Str(data['version']))
    else:
        owner.send('tg', op='types', **dict(data, version=Str(data['version'])))
