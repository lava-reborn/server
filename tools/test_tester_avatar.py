"""Tester portrait compatibility without touching account or game databases."""
from pathlib import Path
import tempfile
import unittest
from build_tester_bundle import ensure_tester_avatar

class Avatar(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'avatars').mkdir()
        self.path = self.root / 'avatars/list.xml'
        self.path.write_text("<data><avatars><a id='45676' sex='0' buy='free'>Original</a></avatars></data>")

    def test_legacy_alias_and_second_update_are_safe(self):
        (self.root / 'avatars/1_1.png').write_bytes(b'image')
        self.assertTrue(ensure_tester_avatar(self.root))
        first = self.path.read_bytes()
        self.assertIn(b"id='45676'", first)
        self.assertIn(b"id='1' sex='0'", first)
        self.assertFalse(ensure_tester_avatar(self.root))
        self.assertEqual(first, self.path.read_bytes())

    def test_missing_picture_is_reported_before_writing_list(self):
        first = self.path.read_bytes()
        with self.assertRaises(RuntimeError):
            ensure_tester_avatar(self.root)
        self.assertEqual(first, self.path.read_bytes())
if __name__ == '__main__':
    unittest.main()
