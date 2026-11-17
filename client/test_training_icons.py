"""Missing range icons stop a release build before the game is restarted."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'client'), str(ROOT / 'server')]
from build import Build


class TrainingIconBuild(unittest.TestCase):
    def test_missing_or_empty_metadata_cannot_bypass_the_release_guard(self):
        with tempfile.TemporaryDirectory(prefix='icon-build-') as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/training_content.json').write_text('{}')
            metadata = root / 'data/training_icons.json'
            build = Build(tmp, None, None, str(root / 'out'))
            self.addCleanup(shutil.rmtree, build.tmp, ignore_errors=True)
            with self.assertRaisesRegex(SystemExit, 'Missing training icon catalogue'):
                build.check_training_icons()
            for sources in ({}, [], None):
                with self.subTest(sources=sources):
                    metadata.write_text(json.dumps({'version': 1, 'sources': sources}))
                    with self.assertRaisesRegex(SystemExit, 'Empty or invalid training icon catalogue'):
                        build.check_training_icons()

    def test_release_keeps_only_verified_icons_and_refuses_unknown_or_removed_ones(self):
        with tempfile.TemporaryDirectory(prefix='icon-build-') as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            metadata = root / 'data/training_icons.json'
            build = Build(tmp, None, None, str(root / 'out'))
            self.addCleanup(shutil.rmtree, build.tmp, ignore_errors=True)
            build.original = Mock(return_value=b'<object type_id="36866" root_type_id="0" name="lamantin_shotgun_10_Blackwater" />')
            icon_path = 'classes/FireArm/lamantin_shotgun_10_Blackwater/ico.swf'
            metadata.write_text(json.dumps({'version': 1, 'sources': {'36866': 36866}}))
            build.files = {icon_path: ('unused-hash', 1)}
            build.check_training_icons()
            build.files = {}
            with self.assertRaisesRegex(SystemExit, 'missing client icon'):
                build.check_training_icons()
            metadata.write_text(json.dumps({'version': 1, 'sources': {'36866': 999999}}))
            with self.assertRaisesRegex(SystemExit, 'unknown icon type'):
                build.check_training_icons()
            metadata.write_text(json.dumps({'version': 2, 'sources': {}}))
            with self.assertRaisesRegex(SystemExit, 'Unsupported training icon catalogue'):
                build.check_training_icons()

    def test_own_item_icon_is_generated_from_its_original_and_required_in_the_release(self):
        with tempfile.TemporaryDirectory(prefix='icon-build-') as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/own_items.json').write_text(json.dumps({
                'items': {'60000': {'name': 'own_shotgun', 'like': 36866}}}))
            (root / 'data/training_icons.json').write_text(json.dumps({
                'version': 1, 'sources': {'60000': 60000}}))
            original_icon = 'classes/FireArm/lamantin_shotgun_10_Blackwater/ico.swf'
            generated_icon = 'classes/FireArm/own_shotgun/ico.swf'
            original = {
                'database/objects.xml': b'<data><object type_id="36866" root_type_id="0" name="lamantin_shotgun_10_Blackwater" /></data>',
                original_icon: b'FWS-original-icon',
            }
            build = Build(tmp, None, None, str(root / 'out'))
            self.addCleanup(shutil.rmtree, build.tmp, ignore_errors=True)
            build.original = Mock(side_effect=original.__getitem__)
            generated, _lines = build.gen_own_items(original)
            self.assertEqual(generated[generated_icon], original[original_icon])
            build.files = {path: ('unused-hash', len(data))
                           for path, data in {**original, **generated}.items()}
            build.check_training_icons()
            del build.files[generated_icon]
            with self.assertRaisesRegex(SystemExit, 'missing client icon'):
                build.check_training_icons()


if __name__ == '__main__':
    unittest.main()
