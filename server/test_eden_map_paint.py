"""Eden has one standard green town marker; work-map artwork remains unpainted."""
import hashlib
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import map_cells as M
import jpeg_blocks as J
from test_eden_region import EXPECTED_CELLS
from testkit import run_cases


CENTER = (5858, 1929)
TOWN = M.tile_path(15543)
OTHER = M.tile_path(15542)


def eden_plan():
    configured = M.load()
    return M.Plan({}, [], {}, paint={CENTER: configured.paint[CENTER]})


def plain_tile():
    sample = M.ycc((145, 122, 91))
    planes = ([[[round(sample[0])] * 256 for _ in range(256)]]
              + [[[round(sample[ci])] * 128 for _ in range(128)] for ci in (1, 2)])
    # The source Eden tile uses high-quality quantizers in the 1..3 range.
    fine = tuple(tuple(max(1, (q + 20) // 40) for q in table)
                 for table in (J.STD_LUMA, J.STD_CHROMA))
    return J.make(256, 256, planes, sampling=(2, 2), qtables=fine)


class EdenMapPaintTests(unittest.TestCase):
    def assert_town_blocks_only(self, original, marked):
        before, after = J.Jpeg(original), J.Jpeg(marked)
        self.assertEqual((before.width, before.height, before.hmax, before.vmax),
                         (after.width, after.height, after.hmax, after.vmax))
        pixels = M.square(*CENTER, M.PALETTE['green'])
        changed = 0
        for ci, component in enumerate(before.comps):
            allowed = {(int((x % M.TILE) * component.h // before.hmax) // 8,
                        int((y % M.TILE) * component.v // before.vmax) // 8)
                       for x, y in pixels}
            actual = {(index % component.bw, index // component.bw)
                      for index, (old, new) in enumerate(zip(component.blocks, after.comps[ci].blocks))
                      if old != new}
            self.assertTrue(actual <= allowed, (ci, actual - allowed))
            changed += len(actual)
        self.assertGreater(changed, 0)

    def test_only_town_is_green_and_sixty_one_work_cells_have_no_image_edits(self):
        plan = M.load()
        self.assertEqual({cell: colour for cell, (colour, _why) in plan.paint.items()
                          if cell in EXPECTED_CELLS}, {CENTER: 'green'})
        for operation in (plan.cells, plan.bare, plan.keep):
            self.assertTrue(EXPECTED_CELLS.isdisjoint(operation))
        self.assertEqual(eden_plan().tiles(), [15543])
        self.assertNotIn(15542, plan.tiles())

    def test_standard_green_pipeline_is_idempotent_and_preserves_other_jpeg_blocks(self):
        original = plain_tile()
        read = lambda path: original if path == TOWN else None
        tiles, _report = M.apply(read, eden_plan())
        self.assertEqual(set(tiles), {TOWN})
        after_read = lambda path: tiles.get(path) or read(path)
        square = M.Squares(M.Canvas(after_read)).at(*CENTER)
        self.assertIsNotNone(square)
        self.assertIn('green', square[2])
        self.assert_town_blocks_only(original, tiles[TOWN])
        self.assertEqual(M.apply(after_read, eden_plan())[0], {})

    def test_http_and_release_use_identical_town_bytes_without_touching_other_tile(self):
        original = plain_tile()
        read = lambda path: original if path == TOWN else None
        release, _report = M.apply(read, eden_plan())
        with patch.object(M, 'reader', return_value=read):
            http = M.Served('read-only fixture', eden_plan())
            self.assertIsNone(http.get(OTHER))
            self.assertIsNone(http._tiles)
            self.assertEqual(http.get(TOWN), release[TOWN])
            self.assertEqual(http.get(TOWN), release[TOWN])
        after_read = lambda path: release.get(path) or read(path)
        with patch.object(M, 'reader', return_value=after_read):
            installed = M.Served('already generated release', eden_plan())
            self.assertIsNone(installed.get(TOWN))
            self.assertEqual(installed._tiles, {})

    def test_real_original_jpegs_keep_only_one_green_town_and_do_not_reencode_twice(self):
        res = Path(os.environ.get('LAVA_RES', ''))
        paths = (TOWN, OTHER)
        if not all((res / path).is_file() for path in paths):
            self.skipTest('The two original global-map JPEG resources are not available')
        base = Path(__file__).resolve().parent.parent / 'client/base.txt'
        originals = {path: (res / path).read_bytes() for path in paths}
        hashes = {parts[2]: parts[0] for line in base.read_text(encoding='utf-8').splitlines()
                  if len(parts := line.split('\t')) == 3}
        if any(hashlib.sha256(raw).hexdigest() != hashes[path] for path, raw in originals.items()):
            self.skipTest('LAVA_RES contains modified images rather than original release resources')
        read = lambda path: originals.get(path)
        tiles, _report = M.apply(read, eden_plan())
        self.assertEqual(set(tiles), {TOWN})
        self.assert_town_blocks_only(originals[TOWN], tiles[TOWN])
        after_read = lambda path: tiles.get(path) or read(path)
        self.assertEqual(after_read(OTHER), originals[OTHER])
        self.assertEqual(M.apply(after_read, eden_plan())[0], {})
        self.assertEqual({path: (res / path).read_bytes() for path in paths}, originals)


if __name__ == '__main__':
    run_cases(EdenMapPaintTests)
