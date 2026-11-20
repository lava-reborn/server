"""Independently recorded, reviewed cell mask of the user's Eden outline."""
import unittest

import eden_map
from testkit import run_cases


# From the user screenshot, aligned 1:1 to globalmap/full/15543.jpg at
# screenshot pixel (241,142). Cell-center interpretation reviewed and approved
# 2026-11-16. These expectations intentionally do not read the generated data.
EXPECTED_ROWS = {
    1927: (5858, 5860, 5861, 5862),
    1928: tuple(range(5856, 5865)),
    1929: tuple(range(5853, 5867)),
    1930: tuple(range(5854, 5866)),
    1931: tuple(range(5854, 5865)),
    1932: tuple(range(5854, 5864)),
    1933: (5861, 5862),
}
EXPECTED_CELLS = frozenset((x, y) for y, xs in EXPECTED_ROWS.items() for x in xs)
RECOVERED = {(5857, 1928): 264, (5857, 1930): 265,
             (5859, 1930): 266, (5858, 1929): 267}
INITIAL_CONNECTORS = {(5858, 1928): 1381, (5859, 1928): 1382,
                      (5857, 1929): 1383, (5859, 1929): 1384, (5858, 1930): 1385}


class EdenRegionTests(unittest.TestCase):
    def test_mapping_matches_the_reviewed_outline_without_extra_or_missing_cells(self):
        self.assertEqual(len(EXPECTED_CELLS), 62)
        self.assertEqual(set(eden_map.CELL_TO_LOC), EXPECTED_CELLS)
        self.assertEqual(len(eden_map.LOC_TO_CELL), len(EXPECTED_CELLS))
        self.assertEqual({loc: cell for cell, loc in eden_map.CELL_TO_LOC.items()},
                         eden_map.LOC_TO_CELL)

    def test_existing_nine_ids_remain_stable_and_added_ids_are_unique_small_static_ids(self):
        for cell, loc in (RECOVERED | INITIAL_CONNECTORS).items():
            self.assertEqual(eden_map.CELL_TO_LOC[cell], loc)
        new_cells = EXPECTED_CELLS - set(RECOVERED) - set(INITIAL_CONNECTORS)
        self.assertEqual({eden_map.CELL_TO_LOC[cell] for cell in new_cells}, set(range(1386, 1439)))
        self.assertTrue(all(0 <= loc < 8192 for loc in eden_map.LOC_TO_CELL))

    def test_reviewed_mask_is_cardinally_connected_and_keeps_sorters_next_to_town(self):
        seen, pending = {(5858, 1929)}, [(5858, 1929)]
        while pending:
            x, y = pending.pop()
            for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if cell in EXPECTED_CELLS and cell not in seen:
                    seen.add(cell)
                    pending.append(cell)
        self.assertEqual(seen, EXPECTED_CELLS)
        self.assertEqual({loc: eden_map.LOC_TO_CELL[loc] for loc in (1383, 1385, 1384)},
                         {1383: (5857, 1929), 1385: (5858, 1930), 1384: (5859, 1929)})


if __name__ == '__main__':
    run_cases(EdenRegionTests)
