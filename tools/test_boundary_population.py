"""Population audit accepts both an editor preview and its saved manual draft."""
import unittest
from audit_boundary_population import draft_choices


class PopulationDrafts(unittest.TestCase):
    def test_preview_keeps_resolved_native_template_ids(self):
        self.assertEqual(draft_choices(dict(boundary_preview=dict(placements={
            '1,2': dict(template=17, allowed_exits=['N'])}))), {'1,2': 17})

    def test_saved_marks_are_read_without_repainting_or_recalculating_the_draft(self):
        marks={'1,2': 'coast', '2,2': 'rocks'}
        doc=dict(scene_edits=marks, blocked=['3,2'])
        self.assertEqual(draft_choices(doc), marks)
        self.assertEqual(doc, dict(scene_edits=marks, blocked=['3,2']))

    def test_missing_roster_is_not_silently_treated_as_an_empty_draft(self):
        with self.assertRaises(ValueError):
            draft_choices(dict(blocked=[]))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(PopulationDrafts)
