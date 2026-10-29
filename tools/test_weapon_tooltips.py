"""Deferred AVM checks: show zero spec requirements without changing bonuses."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import widescreen as w
from avm_test import execute, get


class Sparse:
    """Array identity matches Flash objects; equal fields are not equal arrays."""
    def __init__(self, values, size):
        self.length = size
        for i, value in values.items():
            setattr(self, str(i), value)


def sparse(values, size=15):
    return Sparse(values, size)


class RequirementTooltips(unittest.TestCase):
    def render(self, required, shown=None, titles=None):
        spec_titles = sparse({6: 'Ручные пулеметы', 5: 'Винтовки'})
        panel = NS(specTitle=spec_titles, item=NS(getProp=lambda key: required))
        def original(arr, title_arr):
            lines = [str(get(title_arr, i)) + ' ' + str(get(arr, i)) + '\r'
                     for i in range(get(arr, 'length')) if get(arr, i)]
            return ''.join(lines) or None
        setattr(panel, '__requirementsReadOrig', original)
        return execute(w.fn_annotation_requirements_read().assemble(), dict(
            this=panel, arr=required if shown is None else shown,
            titleArr=spec_titles if titles is None else titles))

    def test_declared_zero_is_visible_in_the_original_format(self):
        self.assertEqual(self.render(sparse({6: 0})), 'Ручные пулеметы 0\r')

    def test_positive_requirement_and_sparse_holes_are_unchanged(self):
        self.assertEqual(self.render(sparse({6: 1})), 'Ручные пулеметы 1\r')
        self.assertIsNone(self.render(sparse({})))

    def test_zero_bonus_does_not_become_a_requirement(self):
        self.assertIsNone(self.render(sparse({6: 0}), shown=sparse({6: 0})))

    def test_mixed_requirements_retain_positive_lines_and_add_zero(self):
        self.assertEqual(self.render(sparse({5: 2, 6: 0})),
                         'Винтовки 2\rРучные пулеметы 0\r')


if __name__ == '__main__':
    unittest.main()
