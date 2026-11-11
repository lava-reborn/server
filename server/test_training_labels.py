"""Human names for every offered range item; ordinary names stay untouched."""
import re
import unittest

import items
import names
from training import catalog as range_catalog
from training import session as training
from training import labels as labels
from training import items as training_items


class TrainingLabels(unittest.TestCase):
    def test_no_offered_label_is_a_raw_catalogue_filename(self):
        for source, (_category, _level, label) in range_catalog.item_catalogue().items():
            with self.subTest(source=source):
                self.assertNotIn(items.catalogue()[training_items.source_type(source)][1].casefold(), label.casefold())
                self.assertIsNone(re.search(r'\b[A-Za-z0-9]+_[A-Za-z0-9_]+', label))

    def test_dreadnought_pieces_reuse_piece_name_and_keep_premium_marker(self):
        for source in range(11479, 11484):
            label = range_catalog.item_catalogue()[source][2]
            self.assertIn('Дредноут', label)
            self.assertIn('(P)', label)
            self.assertIn('18 ур.', label)
        self.assertIn('Шлем', labels.title(11479))

    def test_modified_machineguns_keep_model_variant_and_upgrade(self):
        for source, line in ((40276, 'A'), (40277, 'P'), (40278, 'G')):
            label = labels.title(source)
            self.assertIn('(' + line + ')', label)
            self.assertIn('Урон и размер обоймы', label)
            self.assertNotIn('machine_gun', label)

    def test_regular_display_names_are_unchanged(self):
        for source in (11469, 11479, 40276, 26075):
            name_id = items.STRING_ID_OFFSET + source
            before = names.text(name_id)
            labels.title(source)
            self.assertEqual(names.text(name_id), before)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(TrainingLabels)
