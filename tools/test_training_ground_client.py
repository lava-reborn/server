"""Small build-time contracts for native training-window hooks."""
import re
from pathlib import Path
import unittest

import training_ground_client as client
import widescreen


class TrainingClient(unittest.TestCase):
    def test_all_prototype_hooks_match_existing_game_methods(self):
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        root = Path(__file__).resolve().parents[1] / 'recon/as-src/lol'
        for path, method, _, params, body in package['wraps']:
            with self.subTest(path=path, method=method):
                source = (root.joinpath(*path).with_suffix('.as')).read_text(encoding='utf-8')
                match = re.search(r'function\s+' + re.escape(method) + r'\(([^)]*)\)', source)
                self.assertIsNotNone(match)
                native = [part for part in match[1].split(',') if part.strip()]
                self.assertEqual(len(params), len(native))
                self.assertTrue(body.assemble())

    def test_whole_client_injection_builds_with_new_helpers(self):
        payload = widescreen.injected()
        self.assertIn(b'__tgInstall', payload)
        self.assertIn(b'__tgForgetItems', payload)
        self.assertIn('Учебный центр'.encode('utf-8'), payload)
        # A native DoAction is used; no browser or command-line UI dependency.
        self.assertNotIn(b'ExternalInterface', client.SOURCE.encode('utf-8'))


    def test_compiled_copy_guard_never_labels_normal_items_or_prototypes(self):
        from avm_test import execute
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        _, _, body = next(row for row in package['globals'] if row[0] == '__tgIsCopy')
        for item, expected in ((None, False), ({'id': 0, 'typeID': 54000}, False),
                               ({'id': 'abcd65db00', 'uID': float('nan'), 'typeID': 26075}, False),
                               ({'id': '10000000000d2f000', 'typeID': 54000}, True)):
            env = dict(item=item, Boolean=bool, _global={'__tgCopies': {54000: 26075}})
            self.assertEqual(execute(body.assemble(), env), expected)


if __name__ == '__main__':
    unittest.main()
