"""Camp armour reaches real corpse creation once, with native exceptions."""
import os
from contextlib import nullcontext
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

os.environ.pop('LAVA_DB_URL', None)
os.environ['LAVA_DB'] = ':memory:'

import bosses
import camp_loot
import mob_equipment_loot
import combat
import events
import items
import mobs
import production
import sets
import world
from testkit import run_cases


class FixedRandom:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value

    def choice(self, values):
        return values[0]


class CampLootIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = next(rec['members']['helm'] for rec in sets.SETS.values()
                     if rec['variant'] == 'A' and rec['level'] == 1)
        cls.g = next(rec['members']['helm'] for rec in sets.SETS.values()
                     if rec['variant'] == 'G' and rec['level'] == 1)
        cls.sturm = next(rec['members']['helm'] for rec in sets.SETS.values()
                         if rec['variant'] == 'A' and rec['level'] == 17)

    def test_native_armour_is_replaced_once_and_server_camp_context_is_forwarded(self):
        stats = NS(role='mob', level=1, type_id=258)
        rng = FixedRandom(0)
        with patch.object(mobs, 'carried', return_value=[(self.a, 4), (self.g, 1)]), \
                patch.object(mobs, 'roll_table', return_value=[(self.sturm, 20), (41, 1)]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None), \
                patch.object(mob_equipment_loot, 'roll', return_value=[(self.a, 1)]) as armour:
            drops = mobs.loot_for(stats, rng, loc_id=123456, ambush_camp=80,
                                  killer_level=1, multiplier=3.75)
        self.assertEqual(drops, [(self.g, 1), (41, 1), (self.a, 1)])
        armour.assert_called_once_with(stats, rng, loc_id=123456, ambush_camp=80,
                                       multiplier=3.75, protected=[])

    def test_active_armour_quest_is_preserved_and_suppresses_the_extra_part(self):
        stats = NS(role='mob', level=1, type_id=258)
        with patch.object(mobs, 'carried', return_value=[(self.sturm, 4)]), \
                patch.object(mobs, 'roll_table', return_value=[(self.a, 2)]), \
                patch.object(mobs, 'quest_roll', return_value=[(self.a, 1)]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            drops = mobs.loot_for(stats, FixedRandom(0), {self.a}, loc_id=80,
                                  killer_level=1, multiplier=3.75)
        self.assertEqual(drops, [(self.a, 1)])

    def test_actual_camp_roll_has_one_scaled_boundary_in_centre_side_and_encounter(self):
        stats = mobs.stats(259)
        for loc_id, ambush_camp in ((80, None), (82, None), (world.pack(6000, 2000), 80)):
            for multiplier in (.25, .95, 1, 1.25, 3.75):
                chance = .01 * multiplier
                for value, expected in ((chance - .000001, [(self.a, 1)]), (.02 * multiplier, [])):
                    with self.subTest(loc_id=loc_id, multiplier=multiplier, value=value), \
                            patch.object(mobs, 'carried', return_value=[]), \
                            patch.object(mobs, 'roll_table', return_value=[]), \
                            patch.object(mobs, 'quest_roll', return_value=[]), \
                            patch.object(bosses, 'blueprint_for', return_value=None):
                        drops = mobs.loot_for(stats, FixedRandom(value), loc_id=loc_id,
                                              ambush_camp=ambush_camp, killer_level=stats.level,
                                              multiplier=multiplier)
                    self.assertEqual(drops, expected)

    def test_cutoff_keeps_personal_quest_armour_but_never_rolls_a_camp_reward(self):
        stats = NS(role='mob', level=1, type_id=258)
        with patch.object(mobs, 'personal_quest_item', return_value=True), \
                patch.object(mobs, 'quest_roll', return_value=[(self.a, 1)]), \
                patch.object(mob_equipment_loot, 'roll') as armour, \
                patch.object(mobs, 'carried') as carried:
            self.assertEqual(mobs.loot_for(stats, FixedRandom(0), {self.a}, loc_id=80,
                                          killer_level=6, multiplier=3.75), [(self.a, 1)])
        armour.assert_not_called()
        carried.assert_not_called()

    def test_noncamp_corpses_cannot_keep_legacy_armour_even_from_certain_rows(self):
        stats = NS(role='mob', level=17, type_id=258)
        with patch.object(mobs, 'carried', return_value=[(self.sturm, 5)]), \
                patch.object(mobs, 'roll_table', return_value=[(self.a, 20), (self.g, 1)]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(0), loc_id=None,
                                          killer_level=17), [(self.g, 1)])

    def test_corpse_creation_passes_ambush_and_filters_supplementary_armour_sources(self):
        made = []

        def create(owner, type_id, root, **fields):
            row = dict(type_id=type_id, root=root, char_id=owner, **fields)
            made.append(row)
            return row

        room = NS(loc=NS(id=123456), ambush=80)
        rc = NS(room=room, store=NS(create_item=create))
        mob = NS(type_id=258, stats=NS(role='mob'), quest_wants=(),
                 blueprint_killer_level=1, loot_multiplier=1.05, gold_loot_multiplier=1.05)
        with patch.object(mobs, 'loot_for', return_value=[(self.a, 1)]) as native, \
                patch.object(events, 'loot', return_value=[(self.sturm, 10), (self.g, 1)]), \
                patch.object(production, 'yield_of', return_value=[(self.a, 20)]):
            rows = combat.RoomCombat.drop_loot(rc, mob)
        self.assertEqual([r['type_id'] for r in rows], [self.a, self.g])
        self.assertEqual(native.call_args.kwargs['ambush_camp'], 80)
        self.assertEqual(native.call_args.kwargs['loc_id'], 123456)
        self.assertEqual(native.call_args.kwargs['multiplier'], 1.05)
        self.assertLess(rows[0]['max_break_cur'], items.params_of(self.a)['max_break_abs'])
        self.assertGreaterEqual(2 * rows[0]['brk'], rows[0]['max_break_cur'])

    def test_fixed_object_rewards_are_not_ordinary_creature_equipment_rolls(self):
        stats = NS(role='object', level=1, type_id=258)
        with patch.object(mobs, 'carried', return_value=[]), \
                patch.object(mobs, 'roll_table', return_value=[(self.a, 1), (3577, 1)]), \
                patch.object(mobs, 'quest_roll', return_value=[]), \
                patch.object(bosses, 'blueprint_for', return_value=None):
            self.assertEqual(mobs.loot_for(stats, FixedRandom(0), loc_id=80), [(self.a, 1), (3577, 1)])

    def test_repeated_materialization_does_not_repeat_a_drop_or_roll(self):
        loot = [dict(uniq=987, type_id=self.a)]
        rc = NS(store=NS(db=None, lay_down=Mock()), drop_loot=Mock(return_value=loot),
                place=80, add_to_bag=Mock())
        mob = NS(cell=123)
        with patch.object(combat.storage, 'atomic', return_value=nullcontext()):
            combat.RoomCombat.materialize_loot(rc, mob)
            combat.RoomCombat.materialize_loot(rc, mob)
        rc.drop_loot.assert_called_once_with(mob)
        rc.store.lay_down.assert_called_once()
        rc.add_to_bag.assert_called_once()
        self.assertTrue(mob._loot_materialized)


if __name__ == '__main__':
    run_cases(CampLootIntegration)
