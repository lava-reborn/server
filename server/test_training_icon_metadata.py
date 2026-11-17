"""Range pictures belong to the client; production has only an XML slice."""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import world
from training import display

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import training_icons

logging.disable(logging.CRITICAL)


class TrainingIconMetadata(unittest.TestCase):
    def tearDown(self):
        display.icon_source.cache_clear()
        display.icon_catalogue.cache_clear()

    def test_every_mapping_matches_the_client_manifest_and_exact_model(self):
        expected = training_icons.document()
        self.assertEqual(json.loads(training_icons.PATH.read_text(encoding='utf-8')), expected)
        for source, icon in expected['sources'].items():
            with self.subTest(source=source):
                self.assertEqual(display.icon_source(int(source)), icon)
        self.assertEqual(display.icon_source(36866), 36866)

    def test_missing_or_different_model_metadata_is_refused(self):
        training_icons.document()
        for table in ({}, {36866: 1492}, {36866: 1534}, {36866: 999999}):
            display.icon_source.cache_clear()
            with patch.object(display, 'icon_catalogue', return_value=table):
                with self.assertRaisesRegex(ValueError, 'No matching model icon'):
                    display.icon_source(36866)
        display.icon_source.cache_clear()

    def test_invalid_or_empty_metadata_is_refused(self):
        for document, error in (({'version': 2}, 'Unsupported training icon catalogue'),
                                ({'version': 1}, 'Empty or invalid training icon catalogue'),
                                *[({'version': 1, 'sources': sources},
                                   'Empty or invalid training icon catalogue')
                                  for sources in ({}, [], None)]):
            with self.subTest(document=document):
                display.icon_catalogue.cache_clear()
                with patch.object(Path, 'read_text', return_value=json.dumps(document)):
                    with self.assertRaisesRegex(ValueError, error):
                        display.icon_catalogue()

    def test_cold_preload_and_type_payload_work_with_only_production_xml(self):
        with tempfile.TemporaryDirectory(prefix='training-xml-') as tmp:
            target = Path(tmp)
            source = Path(world.RES)
            for name in ('database/mobs.xml', 'database/objects.xml', 'avatars/list.xml'):
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, destination)
            for folder in ('locations/static', 'locations/deadloc', 'locations/desert'):
                origin = source / folder
                destination = target / folder
                destination.mkdir(parents=True)
                for path in origin.glob('*.xml'):
                    shutil.copyfile(path, destination / path.name)
            self.assertFalse((target / 'classes').exists())
            self.assertEqual({p.name for p in (target / 'database').iterdir()}, {'mobs.xml', 'objects.xml'})
            code = '''
from training import api, catalog, display, items
from training.type_metadata import payload
api.preload()
assert display.icon_source(36866) == 36866
assert all(display.icon_source(source) for source in catalog.item_catalogue())
assert payload()['icons']
assert len(payload()['icons']) == len(items.SOURCES)
print('Production XML-only preload and complete type payload OK')
'''
            env = dict(os.environ, LAVA_RES=str(target), LAVA_TRAINING_GROUND='1',
                       LAVA_DB=':memory:', LAVA_DB_URL='', PYTHONPATH=str(ROOT / 'server'))
            result = subprocess.run([sys.executable, '-B', '-c', code], env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingIconMetadata)
