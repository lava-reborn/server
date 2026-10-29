"""Camp boss recovery rates, quiet time and non-camp isolation; no sockets or DB."""
import copy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import bosses
import combat
import mobs


class BossRecovery(unittest.TestCase):
    def fixture(self, type_id=269, loc_id=82):
        rc = combat.RoomCombat.__new__(combat.RoomCombat)
        rc.room = NS(loc=NS(id=loc_id), ws=False)
        frames = []
        rc.push_vitals = lambda mob: frames.append(mob.vitals())
        mob = mobs.Mob(1, type_id, 0)
        mob.stats = copy.copy(mob.stats)
        mob.stats.hp_max = mob.stats.sp_max = 5000
        mob.hp, mob.sp = 100, 200
        mob.capture_harm = {123: 50}
        mob.regen_at = 160.0
        return rc, mob, frames

    def test_scope_is_exactly_the_twenty_camp_bosses(self):
        self.assertEqual(len(bosses.CAMP_BOSSES), 20)
        self.assertTrue(set(bosses.BLUEPRINTS) < bosses.CAMP_BOSSES)
        for (loc_id, type_id) in bosses.CAMP_BOSSES:
            with self.subTest(location=loc_id, boss=type_id):
                self.assertTrue(bosses.is_camp_boss(loc_id, type_id))
                self.assertTrue(any(t in combat.items.GOLD_INGOTS
                                    for t, chance, valuable in mobs.loot_table(type_id)))
        for loc_id, type_id in ((111, 7448), (646, 2173), (186, 2103),
                                (168, 8620), (168, 1037), (82, 82)):
            self.assertFalse(bosses.is_camp_boss(loc_id, type_id))

    def test_bosses_without_high_level_blueprints_keep_camp_recovery(self):
        for loc, kind in ((132, 777), (274, 1038), (263, 1037)):
            with self.subTest(boss=kind):
                rc, mob, frames = self.fixture(kind, loc)
                self.assertIsNone(bosses.blueprint_for(loc, kind))
                rc.mob_recover(mob)
                self.assertEqual((mob.hp, mob.sp), (100, 200))
                gain = 50 + 15 * (mob.level - 1)
                rc.regen_mob(mob, 160)
                self.assertEqual((mob.hp, mob.sp), (100 + gain, 200 + gain))

    def test_return_home_keeps_camp_boss_damage_and_capture_credit(self):
        rc, mob, frames = self.fixture()
        mob.homing = True
        rc.mob_recover(mob)
        self.assertEqual((mob.hp, mob.sp, mob.capture_harm), (100, 200, {123: 50}))
        self.assertFalse(mob.homing)
        self.assertEqual(frames, [])

    def test_exact_minute_boundary_and_rates(self):
        for level, gain in ((1, 50), (2, 65), (3, 80), (10, 185), (16, 275), (20, 335)):
            with self.subTest(level=level):
                rc, mob, frames = self.fixture()
                mob.stats.level = level
                rc.regen_mob(mob, 159.999)
                self.assertEqual((mob.hp, mob.sp, frames), (100, 200, []))
                rc.regen_mob(mob, 160)
                self.assertEqual((mob.hp, mob.sp), (100 + gain, 200 + gain))
                self.assertEqual(mob.regen_at, 220)
                rc.regen_mob(mob, 160)
                self.assertEqual(len(frames), 1)
                self.assertEqual(mob.capture_harm, {123: 50})

    def test_empty_room_elapsed_minutes_are_applied_once_before_new_aggro(self):
        rc, mob, frames = self.fixture()
        mob.stats.level = 1
        rc.mobs = {mob.eid: mob}
        rc.keep_hours = lambda: None
        rc.fighters = lambda: []
        rc.calm = lambda t: None
        observed = []
        def think(room_combat, t):
            observed.append((mob.hp, mob.sp))
            mob.target = object()
        mob.think = think
        with patch.object(combat, 'now', return_value=280):
            rc._step()
            rc._step()
        self.assertEqual(observed, [(250, 350), (250, 350)])
        self.assertEqual(len(frames), 1)
        self.assertEqual(mob.regen_at, 340)

    def test_fighting_does_not_bank_regeneration(self):
        rc, mob, frames = self.fixture()
        mob.stats.level = 1
        mob.target = object()
        rc.regen_mob(mob, 1000)
        self.assertEqual((mob.hp, mob.sp), (100, 200))
        with patch.object(combat, 'now', return_value=1000):
            rc.mob_release(mob)
        self.assertEqual(mob.regen_at, 1060)
        rc.regen_mob(mob, 1059)
        self.assertEqual(frames, [])
        rc.regen_mob(mob, 1060)
        self.assertEqual((mob.hp, mob.sp), (150, 250))

    def test_camp_boss_can_regenerate_on_the_way_home_without_full_heal(self):
        rc, mob, frames = self.fixture()
        mob.stats.level = 1
        mob.homing = True
        rc.regen_mob(mob, 160)
        self.assertEqual((mob.hp, mob.sp), (150, 250))
        self.assertTrue(mob.homing)

    def test_full_recovery_caps_pools_and_only_then_clears_capture_credit(self):
        rc, mob, frames = self.fixture()
        mob.hp, mob.sp = mob.hp_max - 10, mob.sp_max - 1000
        rc.regen_mob(mob, 160)
        self.assertEqual(mob.hp, mob.hp_max)
        self.assertEqual(mob.capture_harm, {123: 50})
        rc.regen_mob(mob, 4000)
        self.assertEqual((mob.hp, mob.sp, mob.capture_harm),
                         (mob.hp_max, mob.sp_max, {}))

    def test_dead_or_away_boss_does_not_regenerate(self):
        rc, mob, frames = self.fixture()
        mob.alive, mob.away = False, True
        rc.regen_mob(mob, 4000)
        self.assertEqual((mob.hp, mob.sp, frames), (100, 200, []))

    def test_new_spawn_gets_full_pools_and_a_fresh_clock(self):
        rc, mob, frames = self.fixture()
        mob.regen_at = 20
        mob.reset()
        self.assertEqual((mob.hp, mob.sp, mob.regen_at),
                         (mob.hp_max, mob.sp_max, 0))
        mob.hp -= 100
        rc.regen_mob(mob, 500)
        self.assertEqual((mob.hp, mob.regen_at), (mob.hp_max - 100, 560))
        self.assertEqual(frames, [])

    def test_ordinary_warehouse_prison_and_valley_recover_fully_at_home(self):
        for loc_id, type_id in ((100, 82), (111, 7448), (646, 2173), (186, 2103)):
            with self.subTest(location=loc_id, boss=type_id):
                rc, mob, frames = self.fixture(type_id, loc_id)
                mob.homing = True
                rc.mob_recover(mob)
                self.assertEqual((mob.hp, mob.sp, mob.capture_harm),
                                 (mob.hp_max, mob.sp_max, {}))
                self.assertEqual(len(frames), 1)

    def test_non_camp_regeneration_keeps_old_amount_and_no_catchup(self):
        for loc_id, type_id in ((100, 82), (111, 7448), (646, 2173), (186, 2103)):
            with self.subTest(location=loc_id, boss=type_id):
                rc, mob, frames = self.fixture(type_id, loc_id)
                rc.regen_mob(mob, 4000)
                self.assertEqual((mob.hp, mob.sp), (101 + mob.level, 201))
                self.assertEqual(mob.regen_at, 4060)
                mob.homing = True
                rc.regen_mob(mob, 5000)
                self.assertEqual(len(frames), 1)


if __name__ == '__main__':
    unittest.main()
