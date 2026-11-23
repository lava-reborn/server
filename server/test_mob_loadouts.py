"""Ordinary sniper roles and corpse ammo, without simulated battles."""
import copy
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('LAVA_DB', ':memory:')

import battle_balance
import camp_loot
import inventory
import items
import mob_loadouts
import mobs
import rooms
import world
from testkit import run_cases


class FixedRandom:
    def random(self):
        return 0

    def randint(self, low, high):
        return high

    def choice(self, rows):
        return rows[0]


class MobLoadouts(unittest.TestCase):
    def test_all_camp_scopes_have_at_most_one_actual_rifle_type(self):
        catalogue = world.mob_types()
        camps, _rifles = mob_loadouts.policy()
        self.assertEqual(set(camps), set(camp_loot.CENTRES))
        for camp, (members, sniper) in camps.items():
            actual = {t for t in members if mobs.stats(t).ranged
                      and mobs.stats(t).weapon_class == 'rifle'}
            self.assertEqual(actual, set() if sniper is None else {sniper}, camp)
            for loc_id, owner in camp_loot._camp_locations().items():
                if owner != camp:
                    continue
                room = rooms.Room(world.location(loc_id), rooms.IdAllocator(), catalogue)
                present = {npc.type_id for npc in room.npcs.values()
                           if mobs.TYPES.get(str(npc.type_id), {}).get('role') in ('mob', 'boss')}
                self.assertLessEqual(present, members, (camp, loc_id))
                self.assertLessEqual({t for t in present if mobs.stats(t).weapon_class == 'rifle'}, actual)
            # The same type policy applies to the camp's generated encounters.
            self.assertLessEqual(set(world.camp_fill(camp)), members)

    def test_real_named_snipers_win_and_generic_shooters_do_not_multiply_them(self):
        for type_id in (404, 1036, 1731):
            self.assertEqual(mobs.stats(type_id).weapon_class, 'rifle')
        for type_id in (396, 400, 1032, 1733, 1735, 2319):
            self.assertNotEqual(mobs.stats(type_id).weapon_class, 'rifle')
        for type_id in (919, 1045, 1051, 1834):
            self.assertEqual(mobs.stats(type_id).weapon_class, 'rifle')

    def test_no_rifle_is_created_by_an_unrelated_class_gap(self):
        for level in range(21):
            for original in ('pistol', 'smg', 'shotgun', 'assault_rifle', 'machine_gun', 'rifle'):
                stats = mobs.MobStats(367, balanced=False)
                stats.level, stats.weapon_class, stats.ranged = level, original, True
                self.assertTrue(battle_balance.equip_mob(stats, 1), (level, original))
                self.assertNotEqual(stats.weapon_class, 'rifle', (level, original))
                self.assertLessEqual(inventory.item_level(stats.weapon_type_id), level)

    def test_early_camps_and_missing_sniper_tiers_use_existing_junior_items(self):
        for camp in (34, 80, 81):
            self.assertIsNone(mob_loadouts.policy()[0][camp][1])
        for level, expected in ((2, 'pistol'), (5, 'pistol'), (9, 'rifle'), (17, 'rifle')):
            stats = mobs.MobStats(1057, balanced=False)
            stats.level = level
            self.assertTrue(battle_balance.equip_mob(stats, 1))
            self.assertEqual(stats.weapon_class, expected)
            self.assertLessEqual(inventory.item_level(stats.weapon_type_id), level)

    def test_site_room_copies_and_melee_do_not_consult_ordinary_class_policy(self):
        stats = mobs.MobStats(1034, balanced=False)
        with patch.object(mob_loadouts, 'weapon_class', side_effect=AssertionError('ordinary policy')):
            self.assertTrue(battle_balance.equip_mob(stats, 1, site=True))
            melee = mobs.MobStats(765, balanced=False)
            self.assertTrue(battle_balance.equip_mob(melee, 1))
            self.assertEqual(items.root_of(melee.weapon_type_id), items.COLD_ARM)

    def test_every_native_ks_calibre_maps_to_standard_with_exact_count(self):
        catalogue = items.catalogue()
        ks = {t for t, (root, name) in catalogue.items()
              if root == items.AMMO and name.endswith('_KS')}
        replacements = mobs.standard_ammunition_types()
        self.assertEqual(set(replacements), ks)
        for original, standard in replacements.items():
            self.assertEqual(catalogue[standard][1], catalogue[original][1][:-3] + '_ST')
            self.assertEqual(mobs.standard_ammunition([(original, 317)]), [(standard, 317)])
        other = [(t, 23) for t, (root, name) in catalogue.items()
                 if root == items.AMMO and not name.endswith('_KS')]
        self.assertEqual(mobs.standard_ammunition(other), other)

    def test_carried_loot_is_standard_while_firing_stays_makeshift(self):
        stats = mobs.stats(367)
        before = copy.deepcopy(vars(stats))
        ks = stats.loot_ammo_type
        self.assertTrue(items.catalogue()[ks][1].endswith('_KS'))
        drops = mobs.carried(stats, FixedRandom())
        self.assertIn((mobs.standard_ammunition_types()[ks], stats.loot_ammo_count[1]), drops)
        self.assertEqual(vars(stats), before)
        for configured in (items.AMMO_9MM[1], items.AMMO_9MM[2]):
            local = copy.copy(stats)
            local.loot_ammo_type = configured
            self.assertIn((configured, stats.loot_ammo_count[1]), mobs.carried(local, FixedRandom()))

    def test_native_table_ammo_quality_changes_without_extra_rewards_or_rolls(self):
        ks, standard, selected = items.AMMO_9MM
        table = [(ks, mobs.SURE, False), (standard, mobs.SURE, False), (selected, mobs.SURE, False)]
        with patch.object(mobs, 'loot_table', return_value=table), \
                patch.object(mobs, 'independent_loot', return_value=set()), \
                patch.object(mobs, 'one_of_groups', return_value=[]), \
                patch.object(mobs, 'count_of', side_effect=lambda _t, ammo: {ks: 7, standard: 11, selected: 13}[ammo]):
            # A SURE row and its original quantity require no additional die.
            self.assertEqual(mobs.roll_table(367, object()), [(standard, 7), (standard, 11), (selected, 13)])


if __name__ == '__main__':
    raise SystemExit(run_cases(MobLoadouts))
