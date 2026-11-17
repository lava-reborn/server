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


if __name__ == '__main__':
    unittest.main()
