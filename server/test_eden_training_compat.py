"""A new local quest reward must not break optional range text publication."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

from testkit import run_cases


class EdenTrainingCompatibility(unittest.TestCase):
    def test_cold_export_preserves_both_profiles_without_local_work_items(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import copy, json
import eden, items, names
from training import api, catalog, content, items as copies

registry_path = copies.PATH.with_name('training_item_ids.json')
registry_before = registry_path.read_bytes()
registry = json.loads(registry_before)
ordinary_before = dict(items.catalogue())
local_before = {t: copy.deepcopy(items.static_info(t)) for t in eden.LOCAL_ITEMS}
assert eden.BASKET in catalog.obtainable_sources()[1], 'Regression requires the actual craft reward'
excluded = eden.LOCAL_ITEMS | set(range(60022, 60027))
assert set(map(int, content.data()['excluded_sources'])) == excluded
assert excluded.isdisjoint(catalog.item_catalogue())

# Exercise the failing packaging entry point, not a manually prepared registry.
import export_texts
blob = export_texts.document_bytes()
assert export_texts.verify(blob) == ([], [])
assert api.enabled(), 'The optional range must stay enabled'
api.preload()
content.validate()
assert copies.COPIES and copies.SIMULATOR_COPIES
for namespace, mapping in (('baseline', copies.COPIES), ('simulator', copies.SIMULATOR_COPIES)):
    assert excluded.isdisjoint(mapping), namespace
    for source, target in mapping.items():
        if source in copies.PROTOTYPES:
            continue
        # Unchanged simulator equipment deliberately reuses its baseline copy.
        assigned = registry[namespace].get(str(source))
        assert target in (registry['baseline'].get(str(source)), assigned), (namespace, source, target)
assert eden.LOCAL_ITEMS.isdisjoint(copies.SOURCES.values())
assert registry_path.read_bytes() == registry_before
assert items.catalogue() == ordinary_before
for t, before in local_before.items():
    assert items.static_info(t) == before, t
    for field in ('name', 'desc'):
        sid = before[1].get(field)
        if sid:
            assert names.known(sid), (t, field, sid)
assert export_texts.verify(export_texts.document_bytes()) == ([], [])
'''
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root / 'server'), str(root / 'tools'))),
                   LAVA_TRAINING_GROUND='1', LAVA_DB=':memory:', LAVA_DB_URL='')
        result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    run_cases(EdenTrainingCompatibility)
