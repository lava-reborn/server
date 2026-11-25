"""Camp armour is one 1% category, with native tiers and strict site scope."""
import os
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')

import camp_loot
import item_templates
import items
import mobs
import sets
import world
from testkit import run_cases


class FixedRandom:
    def __init__(self, value=0, part=0):
        self.value = value
        self.part = part
        self.calls = []

    def random(self):
        self.calls.append('random')
        return self.value

    def choice(self, parts):
        self.calls.append(tuple(parts))
        return parts[self.part]


class CampArmourLoot(unittest.TestCase):
    def stats(self, level=14, *, role='mob', body='man', can_attack=True):
        # A native humanoid identity, independent of the chosen level fixture.
        type_id = next(int(t) for t, row in mobs.TYPES.items() if row.get('body') == body)
        return NS(type_id=type_id, level=level, role=role, can_attack=can_attack)

    def test_every_centre_and_side_uses_its_parent_camp(self):
        for camp in camp_loot.CENTRES:
            self.assertEqual(camp_loot.camp_for(camp), camp)
        for camp, side in camp_loot.SIDES.items():
            self.assertEqual(camp_loot.camp_for(side), camp)

    def test_actual_patrols_are_recognised_but_static_sites_cannot_use_ambush_override(self):
        for loc_id, rows in world.placements().items():
            camps = {row['patrol'] for row in rows if row.get('patrol') in camp_loot.CENTRES}
            if len(camps) == 1:
                self.assertEqual(camp_loot.camp_for(loc_id), next(iter(camps)))
        self.assertIsNone(camp_loot.camp_for(1, 263))
        self.assertIsNone(camp_loot.camp_for(None, 263))
        loc_id = world.pack(6000, 2000)
        self.assertIsNone(camp_loot.camp_for(loc_id))
        self.assertEqual(camp_loot.camp_for(loc_id, 263), 263)
        self.assertIsNone(camp_loot.camp_for(loc_id, 9999))

    def test_nearest_lower_active_native_set_and_no_level_17_tier(self):
        expected = {0: None, 1: 1, 3: 2, 5: 4, 7: 6, 9: 8,
                    11: 10, 12: 12, 13: 13, 15: 14, 16: 14, 17: 14, 20: 14}
        for level, tier in expected.items():
            with self.subTest(level=level):
                record = camp_loot.eligible_set(self.stats(level), 132)
                self.assertEqual(record['level'] if record else None, tier)
                for type_id in camp_loot.piece_types(self.stats(level), 132):
                    self.assertEqual(sets.variant_of(type_id), 'A')
                    self.assertFalse(items.out_of_game(type_id))
                    self.assertFalse(items.acquisition_blocked(type_id))

    def test_echo_is_only_northern_base_side_patrol_and_its_encounters(self):
        locations = camp_loot._camp_locations()
        northern = [loc_id for loc_id, camp in locations.items() if camp == 263]
        self.assertIn(263, northern)
        self.assertIn(274, northern)
        self.assertGreater(len(northern), 2)
        for loc_id in northern:
            self.assertEqual(camp_loot.eligible_set(self.stats(20), loc_id)['level'], 16)
        for camp in camp_loot.CENTRES - {263}:
            self.assertEqual(camp_loot.eligible_set(self.stats(20), camp)['level'], 14)
        for camp, side in camp_loot.SIDES.items():
            if camp != 263:
                self.assertEqual(camp_loot.eligible_set(self.stats(20), side)['level'], 14)
        encounter = world.pack(6000, 2000)
        self.assertEqual(camp_loot.eligible_set(self.stats(20), encounter, 263)['level'], 16)
        self.assertEqual(camp_loot.eligible_set(self.stats(20), encounter, 168)['level'], 14)

    def test_no_animal_service_turret_resource_or_unrecognised_site_drop(self):
        for role in ('animal', 'turret', 'object', 'service'):
            self.assertIsNone(camp_loot.eligible_set(self.stats(role=role), 263))
        self.assertIsNone(camp_loot.eligible_set(self.stats(can_attack=False), 263))
        self.assertIsNone(camp_loot.eligible_set(self.stats(body='dog', role='boss'), 263))
        for loc_id in (None, 1, 57):
            self.assertEqual(camp_loot.roll(self.stats(), FixedRandom(), loc_id=loc_id), [])
        unknown = self.stats()
        unknown.type_id = -1
        self.assertIsNone(camp_loot.eligible_set(unknown, 263))

    def test_legacy_human_models_without_body_metadata_include_actual_dsr(self):
        for type_id, source in mobs.TYPES.items():
            if (source.get('body') is None
                    and source.get('resource') in camp_loot.LEGACY_HUMAN_MODELS
                    and source.get('role') in ('mob', 'boss')):
                stats = NS(type_id=int(type_id), level=14, role=source['role'], can_attack=True)
                self.assertEqual(camp_loot.eligible_set(stats, 93)['level'], 14)
        for type_id in (362, 365, 368, 373, 592):
            stats = mobs.stats(type_id)
            self.assertIsNone(mobs.TYPES[str(type_id)]['body'])
            self.assertEqual(camp_loot.eligible_set(stats, 93)['level'], stats.level)
        stats = self.stats()
        for body, resource in (('dog', 'patriot'), ('none', 'patriot'), (None, ''),
                               (None, 'unknown_model')):
            with patch.dict(mobs.TYPES, {str(stats.type_id): dict(body=body, resource=resource)}):
                self.assertIsNone(camp_loot.eligible_set(stats, 93))

    def test_one_percent_is_one_roll_not_one_roll_per_slot(self):
        stats = self.stats()
        parts = camp_loot.piece_types(stats, 98)
        self.assertEqual(len(parts), 5)
        for index, part in enumerate(parts):
            rng = FixedRandom(.009999, index)
            self.assertEqual(camp_loot.roll(stats, rng, loc_id=98), [(part, 1)])
            self.assertEqual(rng.calls, ['random', parts])
        rng = FixedRandom(.01)
        self.assertEqual(camp_loot.roll(stats, rng, loc_id=98), [])
        self.assertEqual(rng.calls, ['random'])

    def test_level_scanner_factor_is_applied_once_and_capped(self):
        for factor, chance in ((0, 0), (.25, .0025), (.95, .0095),
                               (1, .01), (1.25, .0125), (3.75, .0375), (3.9, .039), (100, .039)):
            self.assertAlmostEqual(camp_loot.drop_chance(factor), chance)
        for factor in (-1, 0, float('nan'), float('inf')):
            rng = FixedRandom()
            self.assertEqual(camp_loot.roll(self.stats(), rng, loc_id=98, multiplier=factor), [])
            self.assertEqual(rng.calls, [])
        self.assertEqual(len(camp_loot.roll(self.stats(), FixedRandom(.037499),
                                           loc_id=98, multiplier=3.75)), 1)
        self.assertEqual(camp_loot.roll(self.stats(), FixedRandom(.0375),
                                        loc_id=98, multiplier=3.75), [])

    def test_legacy_all_a_tiers_are_suppressed_but_g_and_other_items_survive(self):
        afro = [record for record in sets.records() if record['variant'] == 'A']
        gold = next(record for record in sets.records() if record['variant'] == 'G')
        gold_type = gold['members']['armor']
        self.assertTrue(any(record['level'] == 17 for record in afro))
        for record in afro:
            for type_id in record['members'].values():
                self.assertTrue(camp_loot.is_afro_set_piece(type_id))
                self.assertEqual(camp_loot.without_armour([(type_id, 2), (gold_type, 1), (41, 3)]),
                                 [(gold_type, 1), (41, 3)])
        with patch.object(item_templates, 'source_type', return_value=afro[0]['members']['helm']):
            self.assertTrue(camp_loot.is_afro_set_piece(999999999))

    def test_personal_quest_armour_has_priority_over_new_part(self):
        part = camp_loot.piece_types(self.stats(), 98)[0]
        rng = FixedRandom()
        self.assertEqual(camp_loot.roll(self.stats(), rng, loc_id=98, protected=[(part, 1)]), [])
        self.assertEqual(rng.calls, [])
        gold = next(record for record in sets.records() if record['variant'] == 'G')
        self.assertEqual(len(camp_loot.roll(self.stats(), FixedRandom(), loc_id=98,
                                           protected=[(gold['members']['armor'], 1)])), 1)


if __name__ == '__main__':
    run_cases(CampArmourLoot)
