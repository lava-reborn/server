"""Reviewed content and layout choices; loaded only by the optional range."""
from functools import lru_cache
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / 'data/training_content.json'


@lru_cache(maxsize=1)
def data():
    raw = json.loads(PATH.read_text(encoding='utf-8'))
    if raw.get('version') != 1 or not raw.get('why'):
        raise ValueError('Invalid training content version or rationale')
    return raw


def location(type_id):
    return data()['locations'][str(type_id)]


def validate():
    import items
    import world
    raw = data()
    source_ids = (set(raw['extra_sources']) | set(raw['archive_sources']) | set(map(int, raw['labels']))
                  | set(raw.get('simulator_sources', ())))
    if not source_ids <= items.catalogue().keys():
        raise ValueError('Training content refers to an unknown item')
    if any(items.root_of(source) != raw['source_roots'][str(source)] for source in source_ids):
        raise ValueError('Training source item changed its root class')
    for key, record in raw['labels'].items():
        if not record.get('why') or not record.get('name') or '_' in record['name']:
            raise ValueError('Invalid training item label: ' + key)
    posts = raw['posts']
    if len({post['key'] for post in posts}) != len(posts):
        raise ValueError('Duplicate training post')
    if any(post['resource'] not in world.mob_types() for post in posts):
        raise ValueError('Training post refers to an unknown resource')
    if any(world.mob_types()[post['resource']][0] != raw['resource_roots'][str(post['resource'])] for post in posts):
        raise ValueError('Training resource changed its root class')
