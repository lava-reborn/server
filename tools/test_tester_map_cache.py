"""Derived-map cache: equivalence, invalidation and recovery, no account database."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile
import tester_map_cache as cache

class Cache(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'res').mkdir()
        (self.root / 'state').mkdir()
        (self.root / 'res' / 'source.jpg').write_bytes(b'original')
        self.tile = 'globalmap/full/0_0.jpg'
        self.plan = {'version': 1}

        def apply(reader, plan, progress):
            data = reader('source.jpg')
            reader('missing.jpg')
            return ({self.tile: data + b'-painted'}, ['ok'])
        maps = SimpleNamespace(load=lambda: self.plan, Served=lambda *args, **kwargs: SimpleNamespace(_tiles=kwargs.get('prepared_tiles')), reader=lambda root: lambda name: (Path(root) / name).read_bytes() if (Path(root) / name).exists() else None, apply=Mock(side_effect=apply))
        self.web = SimpleNamespace(RES_ROOT=self.root / 'res', map_cells=maps)
        self.progress = Mock()

    def prepare(self):
        return cache.prepare(self.web, self.root, self.progress)

    def test_warm_start_has_identical_tiles_without_painter(self):
        self.assertEqual(self.prepare(), 'built')
        expected = self.web.MAP_TILES._tiles.copy()
        self.assertEqual(self.prepare(), 'hit')
        self.assertEqual(expected, self.web.MAP_TILES._tiles)
        self.assertEqual(self.web.map_cells.apply.call_count, 1)
        self.progress.assert_called_with(100, 'cached')

    def test_changed_source_and_new_previously_missing_source_invalidate(self):
        self.prepare()
        (self.root / 'res' / 'source.jpg').write_bytes(b'changed')
        self.assertEqual(self.prepare(), 'built')
        (self.root / 'res' / 'missing.jpg').write_bytes(b'new')
        self.assertEqual(self.prepare(), 'built')

    def test_changed_plan_file_invalidates(self):
        self.prepare()
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'map_cells.json').write_text('{}')
        self.assertEqual(self.prepare(), 'built')

    def test_changed_painter_code_invalidates(self):
        self.prepare()
        (self.root / 'server').mkdir()
        (self.root / 'server/map_cells.py').write_text('# updated painter')
        self.assertEqual(self.prepare(), 'built')

    def test_corruption_recovers(self):
        self.prepare()
        (self.root / 'state' / 'map-cache.zip').write_bytes(b'bad')
        self.assertEqual(self.prepare(), 'built')

    def test_invalid_manifest_shapes_and_escape_recover(self):
        for manifest in ([], dict(version=1, inputs=cache.key(self.root), sources=[], tiles={}), dict(version=1, inputs=cache.key(self.root), sources={}, tiles=[]), dict(version=1, inputs=cache.key(self.root), sources={'../escape': None}, tiles={})):
            with self.subTest(manifest=manifest):
                with zipfile.ZipFile(self.root / 'state' / 'map-cache.zip', 'w') as archive:
                    archive.writestr('manifest.json', json.dumps(manifest))
                self.assertEqual(self.prepare(), 'built')

    def test_broken_deflate_stream_recovers(self):
        self.prepare()
        path = self.root / 'state/map-cache.zip'
        with zipfile.ZipFile(path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('manifest.json')
        data = bytearray(path.read_bytes())
        import struct
        name_len, extra_len = struct.unpack_from('<HH', data, info.header_offset + 26)
        data[info.header_offset + 30 + name_len + extra_len] = 7
        path.write_bytes(data)
        self.assertEqual(self.prepare(), 'built')
        self.assertEqual(self.prepare(), 'hit')

    def test_cache_save_or_cleanup_failure_does_not_block_prepared_map(self):
        with patch.object(cache.os, 'replace', side_effect=PermissionError('locked cache')):
            with patch.object(Path, 'unlink', side_effect=PermissionError('locked temporary')):
                self.assertEqual(self.prepare(), 'built')
                self.assertEqual(self.web.MAP_TILES._tiles[self.tile], b'original-painted')

    def test_tampered_tile_rebuilds(self):
        self.prepare()
        path = self.root / 'state' / 'map-cache.zip'
        with zipfile.ZipFile(path) as archive:
            manifest = archive.read('manifest.json')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', manifest)
            archive.writestr(self.tile, b'tampered')
        self.assertEqual(self.prepare(), 'built')
if __name__ == '__main__':
    unittest.main()
