"""Archived classic emitter data and compact vendor geometry, without sockets."""
import copy
import unittest
import inventory
import items
import training_ground as training
import training_items as copies
import training_legacy as legacy
import training_layout as layout


class LegacyTraining(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before={source:copy.deepcopy(items.params_of(source)) for source in legacy.CLASSIC}
        training.preload()

    def params(self,source):
        return items.params_of(copies.copy_type(source))

    def test_classic_pistol_uses_battery_and_archived_damage_in_single_active_mode(self):
        p=self.params(legacy.PISTOL)
        self.assertEqual(p['h_damage_min'],[200,0,0])
        self.assertEqual(p['h_damage_max'],[600,0,0])
        self.assertEqual(p['fire_mods'],[1,0,0])
        self.assertEqual(p['fire_costs'][0],11)
        self.assertEqual(p['fire_times'][0],500)
        self.assertEqual(p['clip_size'],10)
        self.assertEqual(p['comp_array'],[copies.copy_type(legacy.BATTERY)])
        self.assertAlmostEqual(p['target_size'][0]*100/p['max_range'][0],5.7)

    def test_shotgun_modes_and_battery_match_archive(self):
        p=self.params(legacy.SHOTGUN)
        self.assertEqual(p['h_damage_min'],[300,250,200])
        self.assertEqual(p['h_damage_max'],[300,250,200])
        self.assertEqual(p['fire_mods'],[3,6,9])
        self.assertEqual(p['fire_costs'],[11,20,30])
        self.assertEqual(p['comp_array'],[copies.copy_type(legacy.BATTERY)])

    def test_knife_and_healer_match_known_values_without_fabricating_missing_timings(self):
        knife=self.params(legacy.KNIFE);heal=self.params(legacy.HEALER)
        self.assertEqual((knife['h_damage_min'],knife['h_damage_max'],knife['strike_cost']),(0,200,0))
        self.assertEqual(knife['max_break_abs'],10000)
        self.assertEqual((heal['min_h_rest'],heal['max_h_rest'],heal['use_count']),(500,500,7000))
        self.assertEqual(inventory.new_fields(copies.copy_type(legacy.HEALER),1)['use_count'],7000)
        self.assertEqual(knife['strike_time'],self.before[legacy.KNIFE]['strike_time'])
        self.assertEqual(heal['heal_time'],self.before[legacy.HEALER]['heal_time'])

    def test_classic_forms_are_unique_nonpremium_free_copies_and_originals_unchanged(self):
        for source in legacy.CLASSIC:
            with self.subTest(source=source):
                self.assertIn(source,training.item_catalogue())
                self.assertEqual(training.item_line(source),'A')
                p=self.params(source)
                self.assertEqual((p['premium'],p['cost'],p['g_cost'],p['exchang']),(0,0,0,0))
                self.assertEqual(copies.REFERENCE_PRICES[source][:2],(12000,0))
                self.assertEqual(items.params_of(source),self.before[source])
        self.assertTrue(legacy.UNCONFIRMED.isdisjoint(training.item_catalogue()))

    def test_battery_reference_price_is_per_piece_not_per_twenty_pack(self):
        afro,gold,pack=copies.REFERENCE_PRICES[legacy.BATTERY]
        self.assertEqual((afro/pack,gold),(10000,0))
        self.assertEqual(self.params(legacy.BATTERY)['cost'],0)

    def test_six_supply_services_keep_free_approaches(self):
        posts = [post for post in layout.POSTS if post.line]
        self.assertEqual(len(posts), 6)
        self.assertTrue(all(post.line == 'all' for post in posts))
        self.assertEqual(len({post.y for post in posts}), 1)
        self.assertEqual([post.x for post in posts], sorted(post.x for post in posts))
        cells={post.cell(training.ARENA_WIDTH) for post in layout.POSTS}
        self.assertEqual(len(cells),len(layout.POSTS))
        for cell in cells:
            self.assertTrue(any(c not in cells for c in training.progression.hex_neighbours(
                cell,training.ARENA_WIDTH,training.ARENA_HEIGHT)))

    def test_instructor_and_computer_are_centered_together_above_vendor_rows(self):
        computer,instructor=layout.BY_KEY['computer'],layout.BY_KEY['player']
        vendors=[p for p in layout.POSTS if p.line]
        self.assertEqual(computer.y,instructor.y)
        self.assertLess(computer.y,min(p.y for p in vendors))
        self.assertEqual(computer.x+instructor.x,min(p.x for p in vendors)+max(p.x for p in vendors))
        self.assertGreaterEqual(abs(computer.x-instructor.x),6)
        for location in training.LOCATIONS:
            self.assertEqual(training.LOCATIONS[location][0],computer.cell(training.ARENA_WIDTH))
            self.assertTrue(training.progression.within_reach(training.control_cell(location),
                computer.cell(training.ARENA_WIDTH),training.ARENA_WIDTH,training.ARENA_HEIGHT))


if __name__ == '__main__':
    from testkit import run_cases
    run_cases(LegacyTraining)
