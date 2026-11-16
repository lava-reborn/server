"""Eden map labels recover from both original and already-trimmed clients."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import map_cells
import map_labels
from test_eden_region import EXPECTED_CELLS
from testkit import run_cases


HISTORICAL = {(5858, 1929): 'Плантация "Эдем"',
              (5857, 1928): 'Сортировщик гнилых бананов',
              (5857, 1930): 'Сортировщик хороших бананов',
              (5859, 1930): 'Сортировщик зеленых бананов'}
PREVIOUS = {(5858, 1929): 'Плантация Эдем<br>Городишко',
            (5857, 1928): 'Плантация Эдем<br>Сортировщик гнилых бананов',
            (5857, 1930): 'Плантация Эдем<br>Сортировщик зрелых бананов',
            (5859, 1930): 'Плантация Эдем<br>Сортировщик зелёных бананов'}
SORTER = 'Плантация Эдем<br>Сортировщик бананов'
VISIBLE = {(5858, 1929): 'Плантация Эдем<br>Городишко',
           (5857, 1929): 'Плантация Эдем<br>Сортировщик гнилых бананов',
           (5858, 1930): 'Плантация Эдем<br>Сортировщик зрелых бананов',
           (5859, 1929): 'Плантация Эдем<br>Сортировщик зелёных бананов'}
EDEN_CELLS = set(HISTORICAL) | set(VISIBLE)


def row(x, y, text):
    return ('<location x="%d" y="%d" text="%s" />\n' %
            (x, y, map_labels.escape(text))).encode('utf-8')


class EdenMapLabelTests(unittest.TestCase):
    def test_original_and_previously_removed_eden_rows_produce_identical_unique_labels(self):
        edits = [edit for edit in map_labels.load() if edit[:2] in EDEN_CELLS]
        self.assertEqual(len(edits), 17)
        self.assertEqual({edit[:2]: edit[3] for edit in edits if edit[2] is None}, VISIBLE)
        self.assertEqual({edit[:2]: edit[3] for edit in edits
                          if edit[2] is not None and edit[2] == HISTORICAL.get(edit[:2])},
                         {cell: VISIBLE.get(cell) for cell in HISTORICAL})
        ordinary = row(6000, 1700, 'Другой город & его подпись')
        common_previous = {cell: text if cell == (5858, 1929) else SORTER
                           for cell, text in PREVIOUS.items()}
        common_current = {cell: text if cell == (5858, 1929) else SORTER
                          for cell, text in VISIBLE.items()}
        for source, changed_count in (({}, 4), (HISTORICAL, 7), (PREVIOUS, 6),
                                      (common_previous, 6), (common_current, 3), (VISIBLE, 0)):
            with self.subTest(source_labels=source):
                initial = b'<?xml version="1.0"?><data>\n' + ordinary
                initial += b''.join(row(*cell, text) for cell, text in source.items())
                initial += b'</data>'
                result, changed = map_labels.apply(initial, edits)
                self.assertEqual(changed, changed_count)
                parsed = [map_labels._key(match.group(0))
                          for match in map_labels.ROW.finditer(result)]
                self.assertEqual(len(parsed), 5)
                self.assertIn(ordinary, result)
                self.assertEqual({cell: [text for x, y, text in parsed if (x, y) == cell]
                                  for cell in VISIBLE},
                                 {cell: [text] for cell, text in VISIBLE.items()})
                self.assertFalse(any((x, y) in set(HISTORICAL) - set(VISIBLE)
                                     for x, y, _text in parsed))
                self.assertEqual(map_labels.apply(result, edits), (result, 0))

    def test_mixed_original_missing_and_canonical_labels_recover_once_in_either_rule_order(self):
        edits = [edit for edit in map_labels.load() if edit[:2] in EDEN_CELLS]
        cells = sorted(set(HISTORICAL) - {(5858, 1929)})
        unrelated = row(6000, 1700, 'Другая подпись <BR> & "кавычки"')
        # Historical, previous and transient generic overlays all migrate
        # from the old corners to west/south/east, leaving no obsolete label.
        initial = (b'<data>\r\n' + unrelated.replace(b'\n', b'\r\n')
                   + row(*cells[0], HISTORICAL[cells[0]]).replace(b'\n', b'\r\n')
                   + row(*cells[1], PREVIOUS[cells[1]]).replace(b'\n', b'\r\n')
                   + row(*cells[2], SORTER).replace(b'\n', b'\r\n')
                   + row(5858, 1929, VISIBLE[(5858, 1929)]).replace(b'\n', b'\r\n')
                   + b'</data>\r\n')
        expected_rows = sorted([(*cell, text) for cell, text in VISIBLE.items()]
                               + [(6000, 1700, 'Другая подпись <BR> & "кавычки"')])
        for ordered in (edits, list(reversed(edits)), edits + edits):
            with self.subTest(rule_order=ordered):
                result, changed = map_labels.apply(initial, ordered)
                parsed = [map_labels._key(match.group(0))
                          for match in map_labels.ROW.finditer(result)]
                self.assertEqual(changed, 6)
                self.assertEqual(sorted(parsed), expected_rows)
                self.assertEqual(len(parsed), len(set(parsed)))
                self.assertIn(unrelated.replace(b'\n', b'\r\n'), result)
                self.assertNotIn(b'\n', result.replace(b'\r\n', b''))
                self.assertEqual(map_labels.apply(result, ordered), (result, 0))

    def test_only_eden_town_gets_green_marker_and_work_map_artwork_is_not_painted(self):
        plan = map_cells.load()
        cells = EXPECTED_CELLS
        self.assertTrue(cells.isdisjoint(plan.cells))
        self.assertTrue(cells.isdisjoint(plan.bare))
        self.assertTrue(cells.isdisjoint(plan.keep))
        self.assertEqual({cell: colour for cell, (colour, _why) in plan.paint.items()
                          if cell in cells}, {(5858, 1929): 'green'})
        self.assertTrue((cells - {(5858, 1929)}).isdisjoint(plan.paint))
        just_eden = map_cells.Plan({}, [], {}, paint={
            (5858, 1929): plan.paint[(5858, 1929)]})
        self.assertEqual(just_eden.tiles(), [15543])


if __name__ == '__main__':
    run_cases(EdenMapLabelTests)
