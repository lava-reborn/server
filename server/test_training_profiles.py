"""Small selector/provenance checks, without loading simulation battles."""
import unittest
from dataclasses import replace
from training import catalog as range_catalog
from training import session as training_ground
from training import profiles as profiles
from training import items as training_items
from training import supply as training_supply
from training import formulas as training_formulas
import items
from training.rules import Rules

class Profiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        training_ground.preload()

    def test_catalogue_selectors_roundtrip_without_mutating_other_profiles(self):
        records=profiles.catalogue()
        self.assertEqual(len(records),2)
        self.assertEqual(len({p.key for p in records}),2)
        for p in records:
            resolved=profiles.resolve(p.rules.values(),p.key)
            self.assertEqual(profiles.selected(resolved),p)
            self.assertEqual(resolved.revision,p.key)
            altered=replace(resolved,armour=2,attributes=(1,2,1,1,1))
            self.assertEqual(profiles.selected(altered),p)
            self.assertEqual(p.rules.armour,1)
        with self.assertRaises(ValueError):
            profiles.resolve(records[1].rules.values(),'simulator-c4f3018')
        with self.assertRaises(ValueError):
            profiles.resolve(records[0].rules.values(),records[1].key)

    def test_notes_and_flat_payload_are_bounded_and_show_current_revision(self):
        records=profiles.catalogue()
        data=profiles.payload(records[1].rules)
        self.assertEqual(data['profile_selected'],1)
        self.assertIn(training_formulas.data()['source_commit'][:7], records[1].notes[0])
        for i,p in enumerate(records):
            start=data['profile_offsets'][i]
            self.assertEqual(data['profile_counts'][i],len(p.notes))
            self.assertEqual(len(data['profile_notes'][start:start+len(p.notes)]),len(p.notes))
            self.assertTrue(all(isinstance(note,str) and len(note)<800 for note in p.notes))
        self.assertLess(len(data['profile_notes']),50)

    def test_profile_requirements_change_filter_but_not_original_AK(self):
        training_items.prepare(range_catalog.item_catalogue())
        old=items.params_of(26242).copy()
        self.assertEqual(training_supply.index(True)[26242].level,12)
        self.assertEqual(training_supply.index(False)[26242].level,1)
        self.assertEqual(items.params_of(26242),old)

    def test_recovered_emitters_do_not_revert_to_simulator_placeholders(self):
        training_items.prepare(range_catalog.item_catalogue())
        for source in training_formulas.data()['preserved_sources']:
            self.assertNotIn(str(source),training_formulas.data()['equipment'])
            self.assertNotIn(str(source),training_formulas.data()['weapon_bases'])
            self.assertEqual(training_items.copy_type(source,True),training_items.copy_type(source,False))
        p=items.params_of(training_items.copy_type(1569,True))
        self.assertEqual(p['h_damage_min'][0],200)
        self.assertEqual(p['clip_size'],10)


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(Profiles)
