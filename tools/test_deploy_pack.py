"""The real deploy pack omits release docs and preserves runtime files.

Runs only local rsync/tar against a temporary tree; no SSH, DB or containers.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('rsync')
                     and shutil.which('bash'), 'Requires Linux bash and rsync')
class DeployPack(unittest.TestCase):
    def pack(self, extras):
        with tempfile.TemporaryDirectory(prefix='lava-pack-test-') as temp:
            work = Path(temp)
            tree = work / 'tree'
            files = {
                'server/server.py': b'# runtime',
                'data/runtime.json': b'{}',
                'tools/custom_objects.py': b'# client builder',
                'client/keys/resource.keys': b'resource-key',
                'client/keys/launcher.keys': b'launcher-key',
                'launcher/Program.cs': b'// launcher',
                'docker-compose.yml': b'services: {}',
                'README.md': b'deploy instructions',
                # A root-only docs exclusion must not hide nested runtime paths.
                'data/releases/runtime.json': b'{"keep": true}',
                'deploy/rsync.filter': (ROOT / 'deploy/rsync.filter').read_bytes(),
            }
            files.update(extras)
            for name, body in files.items():
                dest = tree / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(body)
            archive = work / 'deploy.tgz'
            subprocess.run(['bash', str(ROOT / 'deploy/ci/pack.sh'),
                            str(archive), str(tree)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            with tarfile.open(archive, 'r:gz') as packed:
                return {m.name.removeprefix('./'): packed.extractfile(m).read()
                        for m in packed.getmembers() if m.isfile()}

    def test_release_docs_do_not_enter_deployment(self):
        packed = self.pack({
            'releases/2026-10-27/PLAN.md': b'private release notes',
            'releases/2026-10-27/checklist.txt': b'checklist',
            'releases/nested/preview.png': b'local preview',
        })
        self.assertFalse(any(n.startswith('releases/') for n in packed))
        self.assertEqual({n.split('/')[0] for n in packed if '/' in n},
                         {'server', 'data', 'tools', 'client', 'launcher', 'deploy'})
        self.assertEqual(packed['server/server.py'], b'# runtime')
        self.assertEqual(packed['client/keys/resource.keys'], b'resource-key')
        self.assertEqual(packed['client/keys/launcher.keys'], b'launcher-key')
        self.assertEqual(packed['data/releases/runtime.json'], b'{"keep": true}')

    def test_existing_local_exclusions_stay_excluded(self):
        excluded = {
            '.env': b'private', 'res/main.swf': b'game assets',
            'dist/tester/state/tester.sqlite': b'local database',
            'logs/debug.txt': b'local log', 'recon/code.as': b'decompiled code',
            '.github/workflows/ci.yml': b'workflow',
            'tools/tester_runtime.py': b'local tester',
            'client/dev/main.swf': b'development client',
        }
        packed = self.pack(excluded)
        self.assertTrue(set(packed).isdisjoint(excluded))
        self.assertIn('docker-compose.yml', packed)
        self.assertIn('README.md', packed)


if __name__ == '__main__':
    unittest.main()
